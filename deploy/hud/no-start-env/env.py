"""HUD managed environment: no-start-env (Second Nature Labs, v0.1).

A thin binding of ``adapter_core`` onto the HUD ``Environment`` object:

* an ``mcp`` capability serving the seven agent-facing tools (FastMCP), each
  registered with the description and JSON schema Inspect serializes for the
  published benchmark run;
* one task template, ``diagnose(task_id)``, whose first yield is the prompt and
  whose second yield is ``grade(world).total / 100``.

No domain logic lives here. Physics, scenarios, prompts, tool observations and
the grader all come from the unmodified ``nostart`` package via
``adapter_core``; see ``adapter_core`` for the parity contract and
``deploy/hud/tests/`` for the tests that hold it.

Serve locally:   hud serve env.py
List tasks:      hud task list -s .
Run an agent:    hud eval tasks.py claude
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool
from hud.capabilities import Capability
from hud.environment import Environment
from hud.graders import EvaluationResult, SubScore

import adapter_core
from adapter_core import TOOL_SPECS, NoStartSession

TOOLS_HOST = "127.0.0.1"
TOOLS_PORT = 8040

env = Environment(name=adapter_core.ENV_NAME, version=adapter_core.ENV_VERSION)

# One HUD environment instance serves one held task at a time (the wire
# protocol holds a single task between tasks.start and tasks.grade), so the
# live episode is process state. It is created by the template before the
# prompt is yielded, and the MCP tools resolve it per call.
_session: NoStartSession | None = None


def _current() -> NoStartSession:
    if _session is None:
        raise RuntimeError(
            "No active episode. Call tasks.start before using the shop tools."
        )
    return _session


# --- MCP tool server --------------------------------------------------------
#
# Each tool is registered from its pinned ToolSpec, so the description and the
# input schema on the wire are the ones the published run used. FastMCP derives
# a schema from the signature; we overwrite it with the pinned one so parity
# does not depend on FastMCP's introspection details.

server = FastMCP(name="no-start-tools")


def _emit(result: adapter_core.ToolResult) -> str:
    if result.is_error:
        # Inspect surfaces a ToolError to the model as the bare message with an
        # error flag; FastMCP's ToolError is the same thing on the MCP wire.
        raise ToolError(result.text)
    return result.text


# One function per tool. Signatures are explicit (FastMCP rejects **kwargs) and
# stay thin: every call goes straight to the adapter, which goes straight to the
# unmodified ToolSession.


async def scan_dtcs() -> str:
    return _emit(_current().scan_dtcs())


async def read_pid(pid: str) -> str:
    return _emit(_current().read_pid(pid))


async def measure_voltage(point_a: str, point_b: str, engine_state: str) -> str:
    return _emit(_current().measure_voltage(point_a, point_b, engine_state))


async def visual_inspect(area: str) -> str:
    return _emit(_current().visual_inspect(area))


async def replace_part(component: str) -> str:
    return _emit(_current().replace_part(component))


async def attempt_start() -> str:
    return _emit(_current().attempt_start())


async def finish(answer: str) -> str:
    return _emit(_current().finish(answer))


_IMPLEMENTATIONS = {
    "scan_dtcs": scan_dtcs,
    "read_pid": read_pid,
    "measure_voltage": measure_voltage,
    "visual_inspect": visual_inspect,
    "replace_part": replace_part,
    "attempt_start": attempt_start,
    "finish": finish,
}

for _spec in TOOL_SPECS:
    _tool = Tool.from_function(
        _IMPLEMENTATIONS[_spec.name],
        name=_spec.name,
        description=_spec.description,
    )
    # Publish the schema Inspect published, not FastMCP's introspected one, so
    # tool-spec parity does not depend on FastMCP's docstring/type handling.
    _tool.parameters = _spec.parameters
    server.add_tool(_tool)


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
    """Block until the tool server is accepting connections. Publishing an
    address before it binds is the classic capability race."""
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
    id="diagnose",
    description=(
        "Diagnose and repair a vehicle electrical no-start fault. One seeded "
        "episode per opaque task id; the agent drives shop tools (scan, "
        "multimeter, visual inspection, parts, start attempts) and submits a "
        "diagnosis. Reward is the 0-100 grader total, normalized."
    ),
)
async def diagnose(task_id: str = "ns-01"):
    global _session
    _session = NoStartSession(task_id)
    try:
        answer = yield _session.prompt()

        # Same fallback as the Inspect scorer: if finish() was never called,
        # grade the agent's final message as the diagnosis.
        result = _session.grade(fallback_answer=answer or "")
        yield EvaluationResult(
            reward=result.reward,
            subscores=_subscores(result.breakdown),
            info=result.metadata,
            content=result.explanation,
        )
    finally:
        _session = None


def _subscores(breakdown: Any) -> list[SubScore]:
    """Grader buckets, surfaced in the trace for legibility. Purely
    informational: the reward is the grader's own total (which applies
    penalties that can debit it), never a recombination of these."""
    return [
        SubScore(name="root_cause", value=_ratio(breakdown.root_cause, 60.0)),
        SubScore(
            name="parts_discipline",
            value=_ratio(breakdown.parts_discipline, 25.0),
        ),
        SubScore(
            name="cost_efficiency",
            value=_ratio(breakdown.cost_efficiency, 15.0),
        ),
    ]


def _ratio(value: float, maximum: float) -> float:
    return max(0.0, min(1.0, value / maximum))
