"""Inspect (inspect-ai) task: vehicle no-start diagnosis.

Wires the simulated vehicle into Inspect so labs can run it directly:

    inspect eval nostart/task.py --model anthropic/claude-sonnet-5

Each sample is one seeded scenario. The agent gets the customer complaint
and the seven shop tools; ``finish`` is the basic_agent submit tool. The
scorer replays nothing and trusts nothing the agent said — it reads true
world state via the grader.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.scorer import Score, Target, mean, scorer, stderr
from inspect_ai.solver import Generate, TaskState, basic_agent, solver, system_message
from inspect_ai.tool import Tool, ToolError, tool
from inspect_ai.util import store

from nostart.domain.scenarios import get_scenario, list_scenarios
from nostart.grader import grade
from nostart.tools import ToolSession

# Sessions hold live World objects (ground truth). They stay in this process
# dict — NEVER in the Inspect store — so no fault state can serialize into
# logs by accident. The store carries only an opaque key.
_SESSIONS: dict[str, ToolSession] = {}
_SESSION_KEY = "nostart:session_key"

SYSTEM_PROMPT = """\
You are an experienced automotive electrical technician. A vehicle in your
bay will not start; the customer complaint is in the first message. Diagnose
the ROOT CAUSE using only the tools provided — you cannot see or touch
anything except through them.

Reference for tool inputs:
- measure_voltage nodes: battery_positive, battery_negative, engine_block,
  starter_stud, alt_output, chassis. starter_stud is the B+ terminal on the
  starter solenoid.
- engine states: key_off, key_on, cranking.
- read_pid PIDs: battery_voltage, alt_output_v, rpm, can_status.
- components (visual_inspect / replace_part): battery, ground_strap,
  starter_relay, starter_motor, alternator, fusible_link, ignition_switch,
  ecu_can_node.

Shop economics: every action costs time, and replacement parts cost real
money. You are scored on (1) naming the correct faulty component and failure
mode, (2) parts discipline — each part you replace that was not the root
cause is penalized, (3) total time versus an expert technician's baseline —
unnecessary or redundant actions keep subtracting points the further you run
over, and (4) actually resolving the problem: replace the faulty part and
confirm the fix with a successful attempt_start() before finishing.
Diagnosing without repairing, or repairing without a verified start, is
penalized even if the diagnosis is correct. Measure first: replacing any
part before you have taken at least one measurement caps your score.
Work like an expert — the fewest actions that isolate the fault, then
repair, then one verify crank.

When the repair is verified, call finish() with your diagnosis: the faulty
component and its failure mode (e.g. "fusible_link blown").
"""


def _session() -> ToolSession:
    key = store().get(_SESSION_KEY)
    if key is None or key not in _SESSIONS:
        raise RuntimeError("No active nostart session for this sample.")
    return _SESSIONS[key]


@solver
def init_session():
    """Create the per-sample world before the agent loop starts."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        scenario_id = str(state.metadata["scenario_id"])
        key = uuid.uuid4().hex
        _SESSIONS[key] = ToolSession(scenario_id)
        store().set(_SESSION_KEY, key)
        return state

    return solve


def _dump(result: Any) -> str:
    return json.dumps(result, indent=1)


@tool
def scan_dtcs() -> Tool:
    async def execute() -> str:
        """Scan the vehicle for stored diagnostic trouble codes (DTCs).

        Returns:
            JSON list of {code, description}.
        """
        return _dump(_session().scan_dtcs())

    return execute


@tool
def read_pid() -> Tool:
    async def execute(pid: str) -> str:
        """Read a live scan-tool parameter (key_on).

        Args:
            pid: One of: battery_voltage, alt_output_v, rpm, can_status.

        Returns:
            JSON with {pid, value, unit}.
        """
        return _dump(_session().read_pid(pid))

    return execute


@tool
def measure_voltage() -> Tool:
    async def execute(point_a: str, point_b: str, engine_state: str) -> str:
        """Measure DC voltage V(point_a) minus V(point_b) with a multimeter.

        Args:
            point_a: Red probe node. One of: battery_positive,
                battery_negative, engine_block, starter_stud, alt_output,
                chassis.
            point_b: Black probe node. Same options as point_a.
            engine_state: Vehicle state during the measurement. One of:
                key_off, key_on, cranking.

        Returns:
            JSON with the reading in volts (meter noise about ±0.05 V).
        """
        try:
            return _dump(
                _session().measure_voltage(point_a, point_b, engine_state)
            )
        except ValueError as exc:
            raise ToolError(str(exc)) from None

    return execute


@tool
def visual_inspect() -> Tool:
    async def execute(area: str) -> str:
        """Visually inspect a component area and report what a tech would see.

        Args:
            area: Component to inspect (e.g. battery, ground_strap,
                starter_relay, starter_motor, alternator, fusible_link,
                ignition_switch, ecu_can_node).

        Returns:
            A terse observation string. Subtle faults may be missed.
        """
        return _session().visual_inspect(area)

    return execute


@tool
def replace_part() -> Tool:
    async def execute(component: str) -> str:
        """Install a known-good replacement part (costs parts + labor).

        Args:
            component: Component to replace (battery, ground_strap,
                starter_relay, starter_motor, alternator, fusible_link,
                ignition_switch, ecu_can_node).

        Returns:
            JSON with {installed: bool}. Does NOT report whether the old
            part was actually faulty.
        """
        return _dump(_session().replace_part(component))

    return execute


@tool
def attempt_start() -> Tool:
    async def execute() -> str:
        """Turn the key and attempt to start the engine.

        Returns:
            JSON with the crank result (e.g. no_click, slow_crank, starts).
        """
        return _dump(_session().attempt_start())

    return execute


ALL_TOOLS = [
    scan_dtcs(),
    read_pid(),
    measure_voltage(),
    visual_inspect(),
    replace_part(),
    attempt_start(),
]


@scorer(metrics=[mean(), stderr()])
def nostart_grader():
    """Score 0-100 from ground-truth world state (cheat-resistant)."""

    async def score(state: TaskState, target: Target) -> Score:
        key = state.store.get(_SESSION_KEY)
        session = _SESSIONS.get(key) if key else None
        if session is None:
            return Score(value=0.0, explanation="No session for sample.")

        diagnosis = state.output.completion or ""
        if not session.world.public_snapshot().finished:
            session.finish(diagnosis)
        breakdown = grade(session.world)
        return Score(
            value=breakdown.total,
            answer=diagnosis,
            explanation="; ".join(breakdown.details) or "See metadata.",
            metadata=breakdown.model_dump(),
        )

    return score


def _make_sample(scenario_id: str) -> Sample:
    scenario = get_scenario(scenario_id)
    return Sample(
        id=scenario_id,
        input=(
            f"Customer complaint: {scenario.complaint}\n\n"
            "Diagnose the root cause. Use your tools; finish() with the "
            "faulty component and failure mode when confident."
        ),
        target=f"{scenario.root_cause.component.value} "
        f"{scenario.root_cause.mode.value}",
        metadata={"scenario_id": scenario_id, "tier": scenario.tier.value},
    )


@task
def no_start(scenarios: str = "all", message_limit: int = 50) -> Task:
    """Vehicle no-start electrical diagnosis.

    Args:
        scenarios: "all" or comma-separated scenario ids.
        message_limit: Max conversation messages before the episode is cut off.
    """
    ids = list_scenarios() if scenarios == "all" else [
        s.strip() for s in scenarios.split(",") if s.strip()
    ]
    dataset = MemoryDataset([_make_sample(s) for s in ids])
    return Task(
        dataset=dataset,
        setup=init_session(),
        solver=basic_agent(
            init=system_message(SYSTEM_PROMPT),
            tools=ALL_TOOLS,
            message_limit=message_limit,
            submit_name="finish",
            submit_description=(
                "Submit your final diagnosis. BEGIN your answer with the "
                "faulty component and its failure mode (e.g. 'fusible_link "
                "blown'); supporting reasoning may follow."
            ),
        ),
        scorer=nostart_grader(),
        # No GenerateConfig: reasoning models (e.g. gpt-5.x) reject
        # temperature; provider defaults apply. Determinism lives in the
        # environment (seeded scenarios), not the model.
    )
