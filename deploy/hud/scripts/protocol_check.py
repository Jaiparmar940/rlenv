#!/usr/bin/env python
"""End-to-end check of the HUD managed protocol for both environments.

The parity tests (deploy/hud/tests/) prove the *adapter* is faithful. This
script proves the *protocol wiring* is: it stands each environment up over the
real control channel and drives one full rollout per task, exercising

    hello -> manifest (capabilities) -> tasks.start -> prompt
          -> MCP tool calls over the published capability
          -> tasks.grade -> reward

and asserting, on the wire:

* the environment advertises exactly one ``mcp`` capability;
* the advertised tool names, descriptions and input schemas byte-match the
  pinned specs (no-start: the ones Inspect published);
* every tool is callable and returns the bytes the adapter returns in-process;
* malformed input is rejected the way the published environment rejects it;
* the reward equals the published grader total over 100;
* the episode terminates and post-termination calls are refused.

Needs the HUD SDK (Python 3.11/3.12):

    .venv-hud/bin/python deploy/hud/scripts/protocol_check.py
    .venv-hud/bin/python deploy/hud/scripts/protocol_check.py --env no-start-env

No HUD API key, no Docker, and no provider key: rollouts run against a locally
served environment with a scripted agent.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

HUD_DIR = Path(__file__).resolve().parents[1]
REPO = HUD_DIR.parent.parent

from hud.agents.base import Agent  # noqa: E402
from hud.capabilities import MCPClient  # noqa: E402
from hud.eval import DockerRuntime, SubprocessRuntime, Taskset  # noqa: E402
from hud.eval.run import Run  # noqa: E402
from hud.types import Trace  # noqa: E402

FAILURES: list[str] = []

# Image tags built by the Dockerfile.hud in each environment directory.
IMAGES = {
    "no-start-env": "sn-no-start-env-hud:0.1.0",
    "decision-layer-kitchen": "sn-decision-layer-kitchen-hud:0.1.0",
}

RUNTIME = "local"


def runtime_for(env_dir: Path):
    """Where each rollout's environment runs: a child process serving the
    source, or the built image (parity with production)."""
    if RUNTIME == "docker":
        return DockerRuntime(IMAGES[env_dir.name])
    return SubprocessRuntime(str(env_dir / "env.py"))


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{label}: {detail}" if detail else label)
    return ok


def isolate(env_dir: Path) -> None:
    """Make ``env_dir`` the only environment package visible to plain imports.

    Both environments name their modules ``adapter_core`` / ``env`` / ``tasks``
    (each ships alone in its own image), so driving both in one checking
    process needs the namespace reset between them. Nothing here affects the
    deployed environments.
    """
    for name in ("adapter_core", "env", "tasks"):
        sys.modules.pop(name, None)
    other = {str(HUD_DIR / d) for d in ("no-start-env", "decision-layer-kitchen")}
    other.discard(str(env_dir))
    sys.path[:] = [p for p in sys.path if p not in other]
    sys.path.insert(0, str(env_dir))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


trajectories = load("hud_expert_trajectories", HUD_DIR / "expert_trajectories.py")


async def _open_tools(run: Run) -> MCPClient:
    """Open the environment's ``mcp`` capability, asserting the manifest."""
    manifest = run.client.manifest
    caps = list(manifest.bindings) if manifest is not None else []
    check(
        "manifest advertises exactly one mcp capability",
        [c.protocol for c in caps] == [MCPClient.protocol],
        f"got {[(c.name, c.protocol) for c in caps]}",
    )
    client = await run.client.open(MCPClient.protocol)
    assert isinstance(client, MCPClient)
    return client


def _text(result: Any) -> str:
    return "".join(
        block.text for block in result.content if getattr(block, "text", None) is not None
    )


# --------------------------------------------------------------- no-start-env


class NoStartProtocolAgent(Agent):
    """Replays the documented expert trajectory over the wire and mirrors it
    in-process through the adapter, comparing every observation."""

    def __init__(self, core: Any) -> None:
        self.core = core
        self.results: dict[str, dict[str, Any]] = {}

    async def __call__(self, run: Run) -> None:
        task_id = run._args["task_id"]
        scenario_id = self.core.TASK_SCENARIOS[task_id]
        script = trajectories.no_start_expert_trajectories()[scenario_id]
        reference = self.core.NoStartSession(task_id)

        print(f"\n--- {task_id} ---")
        tools = await _open_tools(run)

        advertised = {t.name: t for t in await tools.list_tools()}
        check(
            "tool names on the wire match the published surface",
            sorted(advertised) == sorted(s.name for s in self.core.TOOL_SPECS),
            f"got {sorted(advertised)}",
        )
        for spec in self.core.TOOL_SPECS:
            wire = advertised.get(spec.name)
            if wire is None:
                check(f"tool {spec.name} advertised", False)
                continue
            check(
                f"tool {spec.name}: description byte-matches Inspect",
                wire.description == spec.description,
                repr(wire.description),
            )
            check(
                f"tool {spec.name}: input schema byte-matches Inspect",
                wire.inputSchema == spec.parameters,
                json.dumps(wire.inputSchema),
            )

        check(
            "prompt on the wire is the published system prompt + complaint",
            run.prompt_text == reference.prompt(),
        )

        # Malformed input: an unknown node must come back as the environment's
        # own error text, flagged as an error, without ending the episode.
        bad = await tools.call_tool(
            "measure_voltage",
            {"point_a": "flux_capacitor", "point_b": "chassis", "engine_state": "key_off"},
        )
        check("malformed measure_voltage is flagged as an error", bool(bad.isError))
        check(
            "malformed measure_voltage returns the environment's bare message",
            "Unknown node 'flux_capacitor'" in _text(bad),
            _text(bad),
        )
        mirror = reference.measure_voltage("flux_capacitor", "chassis", "key_off")
        check(
            "malformed-input text matches the in-process adapter",
            _text(bad) == mirror.text,
        )

        # Unknown tool name.
        try:
            unknown = await tools.call_tool("read_the_manual", {})
            check("unknown tool is rejected", bool(unknown.isError))
        except Exception:
            check("unknown tool is rejected", True)

        answer = ""
        for name, args in script:
            wire_result = await tools.call_tool(name, args)
            local = reference.call(name, args)
            check(
                f"observation parity: {name}({json.dumps(args, sort_keys=True)})",
                _text(wire_result) == local.text,
                f"wire={_text(wire_result)!r} local={local.text!r}",
            )
            if name == "finish":
                answer = args["answer"]

        # A call after finish must not disturb the graded world. Mirrored so
        # the in-process reference stays an exact shadow of the wire episode
        # (the probes above are extra actions, and this environment prices
        # actions — the clean expert-scores-100 claim lives in the parity
        # tests, which replay the trajectory with nothing added).
        after = await tools.call_tool("scan_dtcs", {})
        check("environment still answers after finish", not after.isError)
        check(
            "post-finish observation matches the in-process adapter",
            _text(after) == reference.scan_dtcs().text,
        )

        expected = reference.grade()
        self.results[task_id] = {
            "expected_reward": expected.reward,
            "expected_total": expected.breakdown.total,
            "expected_info": expected.metadata,
        }
        run.trace = Trace(content=answer)


async def run_no_start() -> None:
    env_dir = HUD_DIR / "no-start-env"
    isolate(env_dir)
    core = load("ns_adapter_core", env_dir / "adapter_core.py")
    print("\n=== no-start-env: managed protocol ===")

    taskset = Taskset.from_file(str(env_dir / "tasks.py"))
    check("taskset discovers all five tasks", len(taskset) == 5, f"got {len(taskset)}")
    check(
        "task rows carry no scenario names",
        not any(s in json.dumps([t.model_dump() for t in taskset]).lower()
                for s in core.TASK_SCENARIOS.values()),
    )

    agent = NoStartProtocolAgent(core)
    job = await taskset.run(agent, runtime=runtime_for(env_dir), max_concurrent=1)

    for task_id, runs in sorted(job.results.items()):
        (run_result,) = runs
        expected = agent.results.get(task_id, {})
        check(
            f"{task_id}: rollout completed",
            run_result.trace.status != "error",
            str(run_result.trace.stop_reason),
        )
        check(
            f"{task_id}: reward == published grader total / 100",
            abs(run_result.reward - expected.get("expected_reward", -1)) < 1e-9,
            f"wire={run_result.reward} expected={expected.get('expected_reward')}",
        )
        check(
            f"{task_id}: expert trajectory scores in the correct-episode band",
            expected.get("expected_total", 0) >= 90.0,
            str(expected.get("expected_total")),
        )
        info = run_result.evaluation.get("info") or {}
        check(
            f"{task_id}: GradeBreakdown rides in the grade metadata",
            info.get("score_0_100") == expected.get("expected_total")
            and "root_cause" in info,
            json.dumps(info)[:200],
        )


# ------------------------------------------------------- decision-layer-kitchen


class KitchenProtocolAgent(Agent):
    """Drives the reactive scripted expert over the wire, mirroring it
    in-process through the adapter."""

    def __init__(self, core: Any) -> None:
        self.core = core
        self.results: dict[str, dict[str, Any]] = {}

    async def __call__(self, run: Run) -> None:
        from kitchen_task.agents import ScriptedExpert
        from kitchen_task.env import MAX_ACTIONS

        task_id = run._args["task_id"]
        reference = self.core.KitchenSession(task_id, run._args.get("seed", 0))

        print(f"\n--- {task_id} ---")
        tools = await _open_tools(run)

        advertised = {t.name: t for t in await tools.list_tools()}
        check(
            "exactly one action tool is advertised",
            list(advertised) == [self.core.ACT_TOOL_NAME],
            f"got {list(advertised)}",
        )
        act = advertised.get(self.core.ACT_TOOL_NAME)
        if act is not None:
            check(
                "act: description matches the published action grammar",
                act.description == self.core.ACT_TOOL_DESCRIPTION,
                repr(act.description),
            )
            check(
                "act: input schema matches",
                act.inputSchema == self.core.ACT_TOOL_PARAMETERS,
                json.dumps(act.inputSchema),
            )

        check(
            "prompt on the wire is the published framing + initial observation",
            run.prompt_text == reference.prompt(),
        )

        # Malformed action: still costs an action, still returns the help text.
        bad = await tools.call_tool("act", {"action": "please open the fridge"})
        local_bad = reference.act("please open the fridge")
        check("malformed action is not an error frame", not bad.isError)
        check(
            "malformed action returns the published parse-failure observation",
            _text(bad) == local_bad.text,
            f"wire={_text(bad)!r}",
        )

        expert = ScriptedExpert()
        observation = _text(bad)
        over = False
        for _ in range(MAX_ACTIONS):
            action = expert(observation)
            wire_result = await tools.call_tool("act", {"action": action})
            local = reference.act(action)
            check(
                f"observation parity: act({action!r})",
                _text(wire_result) == local.text,
                f"wire={_text(wire_result)!r} local={local.text!r}",
            )
            observation = _text(wire_result)
            over = local.episode_over
            if over:
                break
        check("episode terminated on 'done'", over)

        refused = await tools.call_tool("act", {"action": "open fridge"})
        check(
            "actions after the episode ends are refused",
            _text(refused) == self.core.EPISODE_OVER_TEXT,
            _text(refused),
        )

        expected = reference.grade()
        self.results[task_id] = {
            "expected_reward": expected.reward,
            "expected_total": expected.grade.total,
        }
        run.trace = Trace(content="episode complete")


async def run_decision_layer() -> None:
    env_dir = HUD_DIR / "decision-layer-kitchen"
    isolate(env_dir)
    core = load("dlk_adapter_core", env_dir / "adapter_core.py")
    print("\n=== decision-layer-kitchen: managed protocol ===")

    taskset = Taskset.from_file(str(env_dir / "tasks.py"))
    check("taskset discovers all three tasks", len(taskset) == 3, f"got {len(taskset)}")
    check(
        "task rows carry no variant names",
        not any(v in json.dumps([t.model_dump() for t in taskset]).lower()
                for v in core.TASK_VARIANTS.values()),
    )

    agent = KitchenProtocolAgent(core)
    job = await taskset.run(agent, runtime=runtime_for(env_dir), max_concurrent=1)

    for task_id, runs in sorted(job.results.items()):
        (run_result,) = runs
        expected = agent.results.get(task_id, {})
        check(
            f"{task_id}: rollout completed",
            run_result.trace.status != "error",
            str(run_result.trace.stop_reason),
        )
        check(
            f"{task_id}: reward == published grader total / 100",
            abs(run_result.reward - expected.get("expected_reward", -1)) < 1e-9,
            f"wire={run_result.reward} expected={expected.get('expected_reward')}",
        )
        check(
            f"{task_id}: scripted expert scores in the correct-episode band",
            expected.get("expected_total", 0) >= 90.0,
            str(expected.get("expected_total")),
        )
        info = run_result.evaluation.get("info") or {}
        check(
            f"{task_id}: grade breakdown rides in the grade metadata",
            {"inference", "parsimony", "intervention"} <= set(info),
            json.dumps(info)[:200],
        )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env",
        default="all",
        choices=["all", "no-start-env", "decision-layer-kitchen"],
    )
    parser.add_argument(
        "--runtime",
        default="local",
        choices=["local", "docker"],
        help="local: a child process serving env.py. docker: the built image "
             "(build it first — see this directory's README).",
    )
    args = parser.parse_args()

    global RUNTIME
    RUNTIME = args.runtime
    print(f"runtime: {RUNTIME}")

    if args.env in ("all", "no-start-env"):
        await run_no_start()
    if args.env in ("all", "decision-layer-kitchen"):
        await run_decision_layer()

    print("\n" + "=" * 60)
    if FAILURES:
        print(f"PROTOCOL CHECK FAILED — {len(FAILURES)} failing assertion(s):")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1
    print("PROTOCOL CHECK PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
