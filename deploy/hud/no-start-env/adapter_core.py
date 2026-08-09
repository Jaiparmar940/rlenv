"""Managed-environment adapter core for no-start-env.

This module is the *whole* adapter. It wraps ``nostart.tools.ToolSession`` and
``nostart.grader.grade`` unchanged — no domain logic is reimplemented or copied
here. ``env.py`` is a thin binding of this module onto the HUD ``Environment``
object plus a FastMCP tool server.

Deliberately imports **nothing from hud or fastmcp**, for two reasons:

1. the parity tests (deploy/hud/tests/) can then run in the project's own venv,
   against the same interpreter that runs the published Inspect suite;
2. the managed path and the published path share one implementation of the
   observation serialization and the grading call, so they cannot drift.

Parity contract with the published Inspect / OpenReward paths
-------------------------------------------------------------
* **Prompt** — the uncoached system prompt and the complaint user message,
  verbatim. HUD's ``tasks.start`` returns a single prompt string, so the two
  blocks are joined with a blank line (``prompt_blocks()`` keeps them separate
  for callers that have a system role). This is the same single-channel
  concession the OpenReward listing documents.
* **Tool surface** — the same six shop tools plus ``finish``, with descriptions
  and JSON schemas byte-matched to what Inspect serializes (``TOOL_SPECS``
  below; pinned against ``inspect_ai.tool.ToolDef`` by the parity tests).
* **Observations** — ``json.dumps(..., indent=1)`` of the same ToolSession
  return values, so observation streams are byte-identical.
* **Reward** — ``grade(world).total / 100`` emitted once, terminally. The full
  ``GradeBreakdown`` rides in the grade metadata, never in a mid-run
  observation.
* **Unfinished episodes** — if the agent never calls ``finish``, the harness's
  final answer is graded as the diagnosis. That mirrors the Inspect scorer's
  fallback to ``state.output.completion`` and the ORS ``@terminal`` tool.
* **Leakage** — scenario ids encode their own answers, so tasks are addressed
  by opaque ids (``ns-01``..``ns-05``). Tier is carried because it is
  non-identifying and useful for curricula.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _ensure_nostart_importable() -> None:
    """Put the real ``nostart`` package on the path.

    Three layouts, in priority order: already installed; the staged copy in
    ``vendor/`` (what ``stage.py`` writes and the container ships); the
    checkout's own ``src/`` when running from the repo.
    """
    try:
        import nostart  # noqa: F401

        return
    except ImportError:
        pass

    here = Path(__file__).resolve().parent
    candidates = [here / "vendor"]
    candidates += [parent / "src" for parent in here.parents]
    for candidate in candidates:
        if (candidate / "nostart" / "__init__.py").is_file():
            sys.path.insert(0, str(candidate))
            return
    raise ImportError(
        "Could not locate the 'nostart' package. Run deploy/hud/stage.py to "
        "populate vendor/, or install the no-start-env project."
    )


_ensure_nostart_importable()

from nostart.grader import GradeBreakdown, grade  # noqa: E402
from nostart.prompts import PROMPTS  # noqa: E402
from nostart.tools import ToolSession  # noqa: E402

ENV_NAME = "no-start-env"
ENV_VERSION = "0.1.0"
PROMPT_VARIANT = "uncoached"

# Opaque task ids -> scenario ids. Server-side only: a scenario id names its own
# fault, so it must never reach a client-visible task spec. Order is the
# published v0.1 scenario order and is identical to the OpenReward listing's
# (pinned by the parity tests against nostart.openreward.env when that package
# is installed).
TASK_SCENARIOS: dict[str, str] = {
    "ns-01": "easy_dead_battery",
    "ns-02": "medium_corroded_ground",
    "ns-03": "medium_ground_red_herring_battery",
    "ns-04": "hard_intermittent_ecu_can",
    "ns-05": "hard_compound_battery_and_ground",
}

TASK_TIERS: dict[str, str] = {
    "ns-01": "easy",
    "ns-02": "medium",
    "ns-03": "medium",
    "ns-04": "hard",
    "ns-05": "hard",
}

# Verbatim from the Inspect task's Sample input (nostart/task.py::_make_sample).
USER_MESSAGE_TEMPLATE = (
    "Customer complaint: {complaint}\n\n"
    "Diagnose the root cause and repair the vehicle. When it is "
    "fixed, finish() with the faulty component and failure mode."
)


@dataclass(frozen=True)
class ToolSpec:
    """One agent-visible tool: the exact description and JSON schema Inspect
    serializes for the published run. Do not reflow the descriptions — the
    embedded newlines are part of the wire bytes."""

    name: str
    description: str
    parameters: dict[str, Any]


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="scan_dtcs",
        description="Scan the vehicle for stored diagnostic trouble codes (DTCs).",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="read_pid",
        description=(
            "Read a live scan-tool parameter. Reflects the vehicle's current\n"
            "state: engine running if it has been started, otherwise key_on\n"
            "(engine off). The payload names the state it was read in."
        ),
        parameters={
            "type": "object",
            "properties": {
                "pid": {
                    "type": "string",
                    "description": (
                        "One of: battery_voltage, alt_output_v, rpm, can_status."
                    ),
                }
            },
            "required": ["pid"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="measure_voltage",
        description=(
            "Measure DC voltage V(point_a) minus V(point_b) with a multimeter."
        ),
        parameters={
            "type": "object",
            "properties": {
                "point_a": {
                    "type": "string",
                    "description": (
                        "Red probe node. One of: battery_positive,\n"
                        "battery_negative, engine_block, starter_stud, alt_output,\n"
                        "chassis."
                    ),
                },
                "point_b": {
                    "type": "string",
                    "description": "Black probe node. Same options as point_a.",
                },
                "engine_state": {
                    "type": "string",
                    "description": (
                        "Vehicle state during the measurement. One of:\n"
                        "key_off, key_on, cranking, running. The running state is\n"
                        "only available while the engine is actually running (after\n"
                        "a successful start attempt)."
                    ),
                },
            },
            "required": ["point_a", "point_b", "engine_state"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="visual_inspect",
        description=(
            "Visually inspect a component area and report what a tech would see."
        ),
        parameters={
            "type": "object",
            "properties": {
                "area": {
                    "type": "string",
                    "description": (
                        "Component to inspect (e.g. battery, ground_strap,\n"
                        "starter_relay, starter_motor, alternator, fusible_link,\n"
                        "ignition_switch, ecu_can_node)."
                    ),
                }
            },
            "required": ["area"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="replace_part",
        description="Install a known-good replacement part (costs parts + labor).",
        parameters={
            "type": "object",
            "properties": {
                "component": {
                    "type": "string",
                    "description": (
                        "Component to replace (battery, ground_strap,\n"
                        "starter_relay, starter_motor, alternator, fusible_link,\n"
                        "ignition_switch, ecu_can_node)."
                    ),
                }
            },
            "required": ["component"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="attempt_start",
        description="Turn the key and attempt to start the engine.",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    ),
    # basic_agent's submit tool, renamed to finish by nostart/task.py. Name,
    # description, and schema pinned to the wire capture of the published run.
    ToolSpec(
        name="finish",
        description=(
            "Submit your final diagnosis. BEGIN your answer with the faulty "
            "component and its failure mode (e.g. 'fusible_link blown'); "
            "supporting reasoning may follow."
        ),
        parameters={
            "type": "object",
            "properties": {
                "answer": {"type": "string", "description": "Submitted answer"}
            },
            "required": ["answer"],
            "additionalProperties": False,
        },
    ),
)

TOOL_SPECS_BY_NAME: dict[str, ToolSpec] = {spec.name: spec for spec in TOOL_SPECS}


def _dump(result: Any) -> str:
    """Same serialization as nostart/task.py::_dump — keeps observations
    byte-identical to the published run."""
    return json.dumps(result, indent=1)


@dataclass(frozen=True)
class ToolResult:
    """One tool observation. ``is_error`` marks the ToolError case, which
    Inspect renders to the model as the bare message with an error flag."""

    text: str
    is_error: bool = False


@dataclass(frozen=True)
class GradeResult:
    reward: float
    breakdown: GradeBreakdown

    @property
    def metadata(self) -> dict[str, Any]:
        # Mirrors the Inspect Score metadata (display-formatted dump), plus the
        # numeric total for pipelines that want the native 0-100 scale.
        return {**self.breakdown.model_dump(), "score_0_100": self.breakdown.total}

    @property
    def explanation(self) -> str:
        return "; ".join(self.breakdown.details) or "See metadata."


def list_tasks() -> list[dict[str, str]]:
    """Client-visible task specs: opaque id + tier, nothing else."""
    return [
        {"task_id": task_id, "tier": TASK_TIERS[task_id]} for task_id in TASK_SCENARIOS
    ]


class NoStartSession:
    """One episode. Wraps a seeded ``ToolSession``; adds nothing to the world."""

    def __init__(self, task_id: str) -> None:
        scenario_id = TASK_SCENARIOS.get(task_id)
        if scenario_id is None:
            raise ValueError(
                f"Unknown task_id {task_id!r}. Valid: {sorted(TASK_SCENARIOS)}"
            )
        self.task_id = task_id
        self._session = ToolSession(scenario_id)

    # --- prompt -------------------------------------------------------------

    def prompt_blocks(self) -> tuple[str, str]:
        """(system prompt, user message) — verbatim from the published run."""
        return (
            PROMPTS[PROMPT_VARIANT],
            USER_MESSAGE_TEMPLATE.format(complaint=self._session.get_complaint()),
        )

    def prompt(self) -> str:
        """The single prompt string HUD's ``tasks.start`` returns."""
        return "\n\n".join(self.prompt_blocks())

    # --- tools --------------------------------------------------------------
    #
    # One method per TOOL_SPECS entry. Each returns exactly the bytes the
    # Inspect tool body returns for the same call.

    def scan_dtcs(self) -> ToolResult:
        return ToolResult(_dump(self._session.scan_dtcs()))

    def read_pid(self, pid: str) -> ToolResult:
        return ToolResult(_dump(self._session.read_pid(pid)))

    def measure_voltage(
        self, point_a: str, point_b: str, engine_state: str
    ) -> ToolResult:
        try:
            reading = self._session.measure_voltage(point_a, point_b, engine_state)
        except ValueError as exc:
            # Inspect raises ToolError(str(exc)), which the model sees as the
            # bare message flagged as an error. Same bytes, same flag.
            return ToolResult(str(exc), is_error=True)
        return ToolResult(_dump(reading))

    def visual_inspect(self, area: str) -> ToolResult:
        return ToolResult(self._session.visual_inspect(area))

    def replace_part(self, component: str) -> ToolResult:
        return ToolResult(_dump(self._session.replace_part(component)))

    def attempt_start(self) -> ToolResult:
        return ToolResult(_dump(self._session.attempt_start()))

    def finish(self, answer: str) -> ToolResult:
        if not self._session.world.public_snapshot().finished:
            self._session.finish(answer)
        return ToolResult("Diagnosis submitted. Episode finished.")

    def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Dispatch by tool name — the shape the MCP server and the parity
        tests both drive."""
        if name not in TOOL_SPECS_BY_NAME:
            raise ValueError(f"Unknown tool {name!r}")
        return getattr(self, name)(**arguments)

    # --- grading ------------------------------------------------------------

    @property
    def finished(self) -> bool:
        return self._session.world.public_snapshot().finished

    def grade(self, fallback_answer: str = "") -> GradeResult:
        """Grade from true world state. If ``finish`` was never called, the
        harness's final answer is taken as the diagnosis — the Inspect scorer's
        ``state.output.completion`` fallback."""
        if not self.finished:
            self._session.finish(fallback_answer or "")
        breakdown = grade(self._session.world)
        return GradeResult(reward=breakdown.total / 100.0, breakdown=breakdown)
