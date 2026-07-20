"""Open Reward Standard (ORS) adapter for the no-start environment.

Thin wrapper: one ORS session = one episode = one seeded ``World`` (via
``ToolSession``), exactly as in the Inspect task (src/nostart/task.py). The
core environment, grader, and prompts are imported unchanged.

Parity decisions (mirroring the published Inspect benchmark, v0.1):

- **Prompt.** ``get_prompt()`` returns two text blocks: (1) the uncoached
  system prompt, (2) the complaint user message — verbatim the strings the
  Inspect run used. ORS blocks carry no role; harnesses that support a system
  role should map block 1 there. Documented on the environment card.
- **Tool surface.** The same six tools with the same docstring descriptions,
  plus an explicit ``finish(diagnosis)`` tool (Inspect's basic_agent submit).
  Tool results are the same ``json.dumps(..., indent=1)`` payloads the Inspect
  tools return, so observation streams are byte-identical.
- **Reward.** Emitted once, on episode end: grader total / 100 (continuous
  0-1, sparse). The full ``GradeBreakdown`` rides in ``ToolOutput.metadata``
  (post-episode only — never model-visible mid-run).
- **Unfinished episodes.** A hidden ``@terminal`` tool grades the rollout when
  a harness ends it on a plain assistant message, treating that message as the
  diagnosis — the same fallback the Inspect scorer applies to
  ``state.output.completion``.
- **Leakage.** Task specs are client-visible in ORS, and our scenario ids
  encode the answers (e.g. ``easy_dead_battery``). Tasks are therefore listed
  under opaque ids (``ns-01``..``ns-05``) with the mapping held server-side.
  Tier is included as it is non-identifying and useful for curricula.
- **Invalid tool input** (``measure_voltage`` on a bad node/state) returns the
  BARE error message (byte-identical to the text Inspect's ToolError shows the
  model) as a normal tool result with ``metadata={"is_error": True}``.
  Raising instead was rejected: the ORS server turns tool exceptions into
  client-side ``ToolFailed`` exceptions with a session-id prefix in the
  message, and an unknown harness may kill the episode on them rather than
  show the model the error. Harnesses that honor the metadata flag (like
  scripts/validate_openreward.py) can render ``is_error: true`` + the bare
  string, byte-matching Inspect's wire behavior.
- **Tool-spec serialization** is byte-matched to Inspect's wire payloads
  (descriptions without Returns sections, docstring line breaks preserved,
  ``additionalProperties: false``, ``required: []`` on no-arg tools) —
  verified against the captures in results/parity_diag/.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field

from openreward.environments import (
    Environment,
    JSONObject,
    Split,
    TextBlock,
    ToolOutput,
    terminal,
    tool,
)

from nostart.grader import GradeBreakdown, grade
from nostart.prompts import PROMPTS
from nostart.tools import ToolSession

# Opaque task ids -> scenario ids. Server-side only; task specs expose the
# opaque id (+ tier), never the scenario id. Order is the published v0.1
# scenario order and MUST stay stable — ORS clients fetch tasks by index.
# tests/test_openreward_adapter.py pins this against list_scenarios().
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

# Verbatim from the Inspect task's Sample input (task.py::_make_sample).
USER_MESSAGE_TEMPLATE = (
    "Customer complaint: {complaint}\n\n"
    "Diagnose the root cause and repair the vehicle. When it is "
    "fixed, finish() with the faulty component and failure mode."
)


class NoStartTaskSpec(BaseModel):
    task_id: str
    tier: str | None = None  # informational; ignored on input


# Every params model below is a byte-level mirror of what Inspect serializes
# for the published run (verified against wire captures in
# results/parity_diag/): extra="forbid" reproduces additionalProperties:false,
# the Field descriptions reproduce the task.py docstring Args entries
# INCLUDING their line breaks, and NoParams reproduces the empty schema with
# an explicit required:[]. Do not reflow these strings.


class NoParams(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"required": []})


class ReadPidParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pid: str = Field(
        description="One of: battery_voltage, alt_output_v, rpm, can_status."
    )


class MeasureVoltageParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    point_a: str = Field(
        description=(
            "Red probe node. One of: battery_positive,\n"
            "battery_negative, engine_block, starter_stud, alt_output,\n"
            "chassis."
        )
    )
    point_b: str = Field(description="Black probe node. Same options as point_a.")
    engine_state: str = Field(
        description=(
            "Vehicle state during the measurement. One of:\n"
            "key_off, key_on, cranking, running. The running state is\n"
            "only available while the engine is actually running (after\n"
            "a successful start attempt)."
        )
    )


class VisualInspectParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    area: str = Field(
        description=(
            "Component to inspect (e.g. battery, ground_strap,\n"
            "starter_relay, starter_motor, alternator, fusible_link,\n"
            "ignition_switch, ecu_can_node)."
        )
    )


class ReplacePartParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str = Field(
        description=(
            "Component to replace (battery, ground_strap,\n"
            "starter_relay, starter_motor, alternator, fusible_link,\n"
            "ignition_switch, ecu_can_node)."
        )
    )


class FinishParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Name AND description match the Inspect basic_agent submit tool exactly.
    answer: str = Field(description="Submitted answer")


class EndOfEpisodeParams(BaseModel):
    message: str


def _dump(result: Any) -> str:
    # Same serialization as task.py::_dump — keeps observations byte-identical.
    return json.dumps(result, indent=1)


def _text(payload: str) -> list[TextBlock]:
    return [TextBlock(text=payload)]


class NoStartEnv(Environment):
    """Vehicle no-start electrical diagnosis (no-start-env v0.1, Second Nature)."""

    def __init__(
        self, task_spec: JSONObject = {}, secrets: dict[str, str] = {}
    ) -> None:
        super().__init__(task_spec, secrets)
        spec = NoStartTaskSpec.model_validate(task_spec)
        scenario_id = TASK_SCENARIOS.get(spec.task_id)
        if scenario_id is None:
            raise ValueError(
                f"Unknown task_id '{spec.task_id}'. "
                f"Valid: {sorted(TASK_SCENARIOS)}"
            )
        self._session = ToolSession(scenario_id)

    @classmethod
    def name(cls) -> str:
        return "no-start-env"

    @classmethod
    def list_splits(cls) -> Sequence[Split]:
        return [Split(name="test", type="test")]

    @classmethod
    def list_tasks(cls, split: str) -> list[JSONObject]:
        if split != "test":
            raise ValueError(f"Unknown split: {split}")
        return [
            {"task_id": task_id, "tier": TASK_TIERS[task_id]}
            for task_id in TASK_SCENARIOS
        ]

    def get_prompt(self) -> list[TextBlock]:
        # Block 1 was the system message and block 2 the user message in the
        # published Inspect run; map block 1 to the system role if supported.
        return [
            TextBlock(text=PROMPTS["uncoached"]),
            TextBlock(
                text=USER_MESSAGE_TEMPLATE.format(
                    complaint=self._session.get_complaint()
                )
            ),
        ]

    # --- Diagnostic tools (reward 0, never terminate) ---
    #
    # Docstrings below are the DESCRIPTIONS the model sees, byte-matched to
    # what Inspect serializes for the published run: its docstring parser
    # strips the Args/Returns sections from task.py's docstrings, so no
    # Returns text may appear here. Do not reflow.

    @tool
    def scan_dtcs(self, params: NoParams) -> ToolOutput:
        """Scan the vehicle for stored diagnostic trouble codes (DTCs)."""
        return ToolOutput(blocks=_text(_dump(self._session.scan_dtcs())))

    @tool
    def read_pid(self, params: ReadPidParams) -> ToolOutput:
        """Read a live scan-tool parameter. Reflects the vehicle's current
        state: engine running if it has been started, otherwise key_on
        (engine off). The payload names the state it was read in."""
        return ToolOutput(blocks=_text(_dump(self._session.read_pid(params.pid))))

    @tool
    def measure_voltage(self, params: MeasureVoltageParams) -> ToolOutput:
        """Measure DC voltage V(point_a) minus V(point_b) with a multimeter."""
        try:
            result = self._session.measure_voltage(
                params.point_a, params.point_b, params.engine_state
            )
        except ValueError as exc:
            # Bare message (what Inspect's ToolError shows the model) + a
            # metadata flag so harnesses can frame it as is_error: true.
            return ToolOutput(blocks=_text(str(exc)),
                              metadata={"is_error": True})
        return ToolOutput(blocks=_text(_dump(result)))

    @tool
    def visual_inspect(self, params: VisualInspectParams) -> ToolOutput:
        """Visually inspect a component area and report what a tech would see."""
        return ToolOutput(
            blocks=_text(self._session.visual_inspect(params.area))
        )

    @tool
    def replace_part(self, params: ReplacePartParams) -> ToolOutput:
        """Install a known-good replacement part (costs parts + labor)."""
        return ToolOutput(
            blocks=_text(_dump(self._session.replace_part(params.component)))
        )

    @tool
    def attempt_start(self, params: NoParams) -> ToolOutput:
        """Turn the key and attempt to start the engine."""
        return ToolOutput(blocks=_text(_dump(self._session.attempt_start())))

    # --- Episode termination ---

    def _grade(self) -> ToolOutput:
        breakdown: GradeBreakdown = grade(self._session.world)
        # model_dump() serializes score fields as display strings ("60/60"),
        # matching the Inspect Score metadata; score_0_100 is the numeric
        # total for pipelines that want the native scale without parsing.
        return ToolOutput(
            blocks=_text("Diagnosis submitted. Episode finished."),
            metadata={**breakdown.model_dump(), "score_0_100": breakdown.total},
            reward=breakdown.total / 100.0,
            finished=True,
        )

    @tool
    def finish(self, params: FinishParams) -> ToolOutput:
        """Submit your final diagnosis. BEGIN your answer with the faulty component and its failure mode (e.g. 'fusible_link blown'); supporting reasoning may follow."""
        if not self._session.world.public_snapshot().finished:
            self._session.finish(params.answer)
        return self._grade()

    @terminal
    @tool
    def grade_final_message(self, params: EndOfEpisodeParams) -> ToolOutput:
        """Hidden terminal fallback (never shown to the model): grades the
        episode when the harness ends the rollout on a plain assistant
        message, treating that message as the diagnosis — the same fallback
        the Inspect scorer applies to state.output.completion when finish()
        was not called.
        """
        if not self._session.world.public_snapshot().finished:
            self._session.finish(params.message)
        return self._grade()
