"""HUD managed environment: decision-layer kitchen task (Second Nature Labs).

A thin binding of ``adapter_core`` onto the HUD ``Environment`` object:

* an ``mcp`` capability serving the one action tool, ``act(action)``, which is
  the published action grammar unchanged;
* one task template, ``put_away(task_id, seed)``, whose first yield is the
  prompt (system framing + initial observation) and whose second yield is
  ``grade(episode, backend).total / 100``.

The primary managed backend is the pure-Python symbolic kitchen. The
RoboCasa/MuJoCo backend is validation evidence, not a production dependency —
see this directory's README and ``decision-layer/handoff/``.

Serve locally:   hud serve env.py
List tasks:      hud task list -s .
Run an agent:    hud eval tasks.py claude
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools import Tool
from hud.capabilities import Capability
from hud.environment import Environment
from hud.graders import EvaluationResult, SubScore

import adapter_core
from adapter_core import (
    ACT_TOOL_DESCRIPTION,
    ACT_TOOL_NAME,
    ACT_TOOL_PARAMETERS,
    DEFAULT_SEED,
    KitchenSession,
)

TOOLS_HOST = "127.0.0.1"
TOOLS_PORT = 8041

env = Environment(name=adapter_core.ENV_NAME, version=adapter_core.ENV_VERSION)

# One held task at a time (the HUD wire protocol), so the live episode is
# process state: minted by the template before the prompt is yielded.
_session: KitchenSession | None = None


def _current() -> KitchenSession:
    if _session is None:
        raise RuntimeError(
            "No active episode. Call tasks.start before using the action tool."
        )
    return _session


# --- MCP tool server --------------------------------------------------------

server = FastMCP(name="decision-layer-tools")


async def _act(action: str) -> str:
    return _current().act(action).text


_act_tool = Tool.from_function(
    _act, name=ACT_TOOL_NAME, description=ACT_TOOL_DESCRIPTION
)
_act_tool.parameters = ACT_TOOL_PARAMETERS
server.add_tool(_act_tool)


_server_task: asyncio.Task | None = None


@env.initialize
async def _start_tools() -> None:
    global _server_task
    if _server_task is None:
        _server_task = asyncio.create_task(
            server.run_async(transport="http", host=TOOLS_HOST, port=TOOLS_PORT)
        )
        await _wait_for_port(TOOLS_HOST, TOOLS_PORT)
    env.add_capability(
        Capability.mcp(name="tools", url=f"http://{TOOLS_HOST}:{TOOLS_PORT}/mcp")
    )


@env.shutdown
async def _stop_tools() -> None:
    global _server_task, _session
    _session = None
    if _server_task is not None:
        _server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _server_task
        _server_task = None


async def _wait_for_port(host: str, port: int, timeout: float = 20.0) -> None:
    """Block until the tool server accepts connections; publishing an address
    before it binds is the classic capability race."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        try:
            _, writer = await asyncio.open_connection(host, port)
        except OSError:
            await asyncio.sleep(0.05)
            continue
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
        return
    raise RuntimeError(f"tool server did not bind {host}:{port} within {timeout}s")


# --- the task ---------------------------------------------------------------


@env.template(
    id="put_away",
    description=(
        "Put the leftovers away in a kitchen whose relevant state is hidden "
        "until inspected. The agent drives one action tool over a fixed "
        "primitive grammar; execution is oracle by design, so what is graded "
        "is the decision sequence (inspect, infer, intervene), not motor "
        "control. Reward is the 0-100 grader total, normalized."
    ),
)
async def put_away(task_id: str = "dlk-01", seed: int = DEFAULT_SEED):
    global _session
    _session = KitchenSession(task_id, seed)
    try:
        # The agent's final message is not an input to grading: findings are
        # declared in-episode and the end state is read off the backend.
        yield _session.prompt()

        result = _session.grade()
        yield EvaluationResult(
            reward=result.reward,
            subscores=_subscores(result.grade),
            info=result.metadata,
            content=result.explanation,
        )
    finally:
        _session = None


def _subscores(g: Any) -> list[SubScore]:
    """Grader buckets, surfaced in the trace for legibility. Informational
    only — the reward is the grader's own total, which applies the guessing cap
    and the negative-parsimony debit."""
    return [
        SubScore(name="inference", value=_ratio(g.inference, 40.0)),
        SubScore(name="parsimony", value=_ratio(g.parsimony, 25.0)),
        SubScore(name="intervention", value=_ratio(g.intervention, 35.0)),
    ]


def _ratio(value: float, maximum: float) -> float:
    return max(0.0, min(1.0, value / maximum))
