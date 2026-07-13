"""Hard-tier preview: intermittent ECU fault + compound (two-fault) scenario.

Physics numbers asserted here are PENDING HUMAN SIGN-OFF
(see PENDING_HUMAN_PHYSICS_SIGNOFF.md). They pin what the resistance-network
model currently PRODUCES, so a silent change to the model cannot slip past.
"""

from __future__ import annotations

import pytest

from nostart.domain.components import Component, FailureMode
from nostart.domain.propagation import CrankBehavior, EngineState, resolve_symptoms
from nostart.domain.scenarios import get_scenario
from nostart.grader import (
    PRIMARY_MAX,
    ROOT_CAUSE_MAX,
    SECONDARY_MAX,
    GradeBreakdown,
    grade,
)
from nostart.tools import ToolSession

INTERMITTENT = "hard_intermittent_ecu_can"
COMPOUND = "hard_compound_battery_and_ground"


def _run_agent(scenario_id: str, steps: list[tuple[str, ...]]) -> GradeBreakdown:
    session = ToolSession(scenario_id)
    for cmd, *args in steps:
        if cmd == "measure_voltage":
            session.measure_voltage(args[0], args[1], args[2])
        elif cmd == "replace_part":
            session.replace_part(args[0])
        elif cmd == "attempt_start":
            session.attempt_start()
        elif cmd == "scan_dtcs":
            session.scan_dtcs()
        elif cmd == "read_pid":
            session.read_pid(args[0])
        elif cmd == "finish":
            session.finish(args[0])
        else:  # pragma: no cover - test bug
            raise ValueError(f"Unknown step: {cmd}")
    return grade(session.world)


# --- Intermittent ECU/CAN node ---------------------------------------------


class TestIntermittentDeterminism:
    """Manifestation is a pure function of (seed, probe kind, probe index)."""

    def _cranks(self, n: int = 20) -> list[str]:
        session = ToolSession(INTERMITTENT)
        return [session.attempt_start()["result"] for _ in range(n)]

    def test_identical_runs_identical_observations(self) -> None:
        assert self._cranks() == self._cranks()

    def test_manifestation_survives_interleaved_actions(self) -> None:
        # The k-th crank must not depend on how many OTHER actions happened
        # first — i.e. the roll must not be drawn from the shared noise RNG.
        baseline = self._cranks(5)

        noisy = ToolSession(INTERMITTENT)
        results = []
        for _ in range(5):
            noisy.measure_voltage("battery_positive", "battery_negative", "key_on")
            noisy.visual_inspect("battery")
            noisy.scan_dtcs()
            results.append(noisy.attempt_start()["result"])
        assert results == baseline

    def test_no_wall_clock_randomness(self) -> None:
        # Two worlds built at different times agree exactly.
        first = ToolSession(INTERMITTENT)
        second = ToolSession(INTERMITTENT)
        for _ in range(10):
            assert first.attempt_start() == second.attempt_start()

    def test_fault_is_intermittent_not_constant(self) -> None:
        seq = self._cranks(20)
        assert "crank_no_start" in seq  # the complaint is real
        assert "starts" in seq  # ...but it also starts fine sometimes
        assert set(seq) == {"crank_no_start", "starts"}

    def test_manifest_rate_tracks_severity(self) -> None:
        seq = self._cranks(40)
        rate = seq.count("crank_no_start") / len(seq)
        severity = get_scenario(INTERMITTENT).root_cause.severity
        assert severity["manifest_probability"] == 0.35
        assert 0.15 <= rate <= 0.60  # sampling slack around 0.35

    def test_single_clean_scan_does_not_exonerate(self) -> None:
        session = ToolSession(INTERMITTENT)
        scans = [session.scan_dtcs() for _ in range(10)]
        assert any(s == [] for s in scans), "some scans must come back clean"
        assert any(
            any(code["code"] == "U0100" for code in s) for s in scans
        ), "some scans must show the code"

    def test_can_status_pid_is_also_intermittent(self) -> None:
        session = ToolSession(INTERMITTENT)
        values = [session.read_pid("can_status")["value"] for _ in range(10)]
        assert "ok" in values
        assert any(v != "ok" for v in values)


class TestIntermittentPhysics:
    def test_no_electrical_signature(self) -> None:
        # The ECU node moves no node potential: a drop-test-only workflow
        # cannot find this fault, which is the point of the scenario.
        fault = get_scenario(INTERMITTENT).root_cause
        for state in (EngineState.KEY_OFF, EngineState.KEY_ON, EngineState.CRANKING):
            faulted = resolve_symptoms([fault], state).node_potentials
            healthy = resolve_symptoms([], state).node_potentials
            assert faulted == healthy

    def test_manifested_crank_is_crank_no_start(self) -> None:
        fault = get_scenario(INTERMITTENT).root_cause
        symptoms = resolve_symptoms([fault], EngineState.CRANKING)
        assert symptoms.crank_behavior == CrankBehavior.CRANK_NO_START
        assert symptoms.intermittency == 0.35

    def test_replacing_ecu_fixes_it_for_good(self) -> None:
        session = ToolSession(INTERMITTENT)
        session.replace_part("ecu_can_node")
        assert {session.attempt_start()["result"] for _ in range(12)} == {"starts"}


# --- Compound: genuinely weak battery + corroded ground ---------------------


class TestCompoundPhysics:
    """Both faults must be independently visible to a tech."""

    def _symptoms(self, state: EngineState):
        scenario = get_scenario(COMPOUND)
        return resolve_symptoms(
            [scenario.root_cause, scenario.secondary_fault], state
        )

    def _battery(self, state: EngineState) -> float:
        return self._symptoms(state).potential_difference(
            "battery_positive", "battery_negative"
        )

    def _ground_drop(self, state: EngineState) -> float:
        return abs(
            self._symptoms(state).potential_difference(
                "battery_negative", "engine_block"
            )
        )

    def _feed_drop(self, state: EngineState) -> float:
        return abs(
            self._symptoms(state).potential_difference(
                "battery_positive", "starter_stud"
            )
        )

    def test_battery_is_genuinely_weak_at_rest(self) -> None:
        # Worse than the 11.8 V red-herring bait: not confusable with it.
        assert self._battery(EngineState.KEY_OFF) == pytest.approx(11.0, abs=0.05)
        assert self._battery(EngineState.KEY_ON) < 11.8

    def test_battery_fails_the_load_test(self) -> None:
        # < 9.6 V cranking = condemned. The innocent battery in the ground
        # scenarios holds >= 11.3 V; this one does not come close.
        cranking = self._battery(EngineState.CRANKING)
        assert cranking == pytest.approx(9.25, abs=0.05)
        assert cranking < 9.6
        assert cranking < 11.3

    def test_load_sag_never_inverted(self) -> None:
        assert self._battery(EngineState.CRANKING) < self._battery(EngineState.KEY_ON)

    def test_ground_drop_is_present_under_load_only(self) -> None:
        assert self._ground_drop(EngineState.CRANKING) == pytest.approx(1.75, abs=0.05)
        for state in (EngineState.KEY_OFF, EngineState.KEY_ON):
            assert self._ground_drop(state) <= 0.1

    def test_ground_fault_still_localizable(self) -> None:
        cranking = EngineState.CRANKING
        assert self._feed_drop(cranking) <= 0.5
        assert self._ground_drop(cranking) >= self._feed_drop(cranking) + 1.0

    def test_resting_monotonicity_holds(self) -> None:
        for state in (EngineState.KEY_OFF, EngineState.KEY_ON):
            nodes = self._symptoms(state).node_potentials
            assert nodes["starter_stud"] <= nodes["battery_positive"] + 1e-6
            assert nodes["alt_output"] <= nodes["battery_positive"] + 1e-6

    def test_slow_crank(self) -> None:
        assert self._symptoms(EngineState.CRANKING).crank_behavior == (
            CrankBehavior.SLOW_CRANK
        )

    @pytest.mark.parametrize("partial", ["battery", "ground_strap"])
    def test_neither_repair_alone_fixes_the_car(self, partial: str) -> None:
        session = ToolSession(COMPOUND)
        session.replace_part(partial)
        assert session.attempt_start()["result"] != "starts"

    def test_both_repairs_fix_the_car(self) -> None:
        session = ToolSession(COMPOUND)
        session.replace_part("ground_strap")
        session.replace_part("battery")
        assert session.attempt_start()["result"] == "starts"

    def test_world_injects_both_faults(self) -> None:
        world = ToolSession(COMPOUND).world
        assert {f.component for f in world.active_faults} == {
            Component.GROUND_STRAP,
            Component.BATTERY,
        }
        assert world.secondary_fault is not None
        assert world.secondary_fault.mode == FailureMode.WEAK


# --- Compound grading rule --------------------------------------------------

_EXPERT_STEPS: list[tuple[str, ...]] = [
    ("attempt_start",),
    ("measure_voltage", "battery_positive", "battery_negative", "key_off"),
    ("measure_voltage", "battery_positive", "battery_negative", "cranking"),
    ("measure_voltage", "battery_negative", "engine_block", "cranking"),
    ("measure_voltage", "battery_positive", "starter_stud", "cranking"),
    ("replace_part", "ground_strap"),
    ("replace_part", "battery"),
    ("attempt_start",),
]


class TestCompoundGrading:
    def test_naming_both_faults_scores_full_root_credit(self) -> None:
        result = _run_agent(
            COMPOUND,
            _EXPERT_STEPS
            + [("finish", "corroded ground strap, plus a weak battery")],
        )
        assert result.primary_cause == PRIMARY_MAX
        assert result.secondary_cause == SECONDARY_MAX
        assert result.root_cause == ROOT_CAUSE_MAX  # same 60 as a single fault
        assert result.wrong_parts_replaced == []
        assert result.fix_verified
        assert result.total == 100.0

    def test_word_order_does_not_matter(self) -> None:
        # The obvious fault (battery) named FIRST must not cost the primary.
        result = _run_agent(
            COMPOUND,
            _EXPERT_STEPS
            + [
                (
                    "finish",
                    "Weak battery (11.0 V resting, 9.2 V cranking) AND a "
                    "corroded engine ground strap dropping 1.8 V under crank. "
                    "Both replaced.",
                )
            ],
        )
        assert result.primary_cause == PRIMARY_MAX
        assert result.secondary_cause == SECONDARY_MAX
        assert result.total == 100.0

    def test_primary_only_loses_the_secondary_share(self) -> None:
        result = _run_agent(
            COMPOUND, _EXPERT_STEPS + [("finish", "ground_strap corroded")]
        )
        assert result.primary_cause == PRIMARY_MAX
        assert result.secondary_cause == 0.0
        assert result.root_cause == PRIMARY_MAX

    def test_secondary_only_is_partial_credit_and_cannot_pass(self) -> None:
        # The battery-only tech: replaces the battery, car still slow-cranks.
        result = _run_agent(
            COMPOUND,
            [
                ("measure_voltage", "battery_positive", "battery_negative", "key_off"),
                ("replace_part", "battery"),
                ("attempt_start",),
                ("finish", "battery weak"),
            ],
        )
        assert result.primary_cause == 0.0
        assert result.secondary_cause == SECONDARY_MAX
        assert result.root_cause == SECONDARY_MAX  # 15/60 — partial, not a pass
        assert not result.fix_verified  # the car does not start
        assert result.total < 50.0

    def test_replacing_the_secondary_is_not_a_wrong_part(self) -> None:
        result = _run_agent(
            COMPOUND, _EXPERT_STEPS + [("finish", "ground_strap corroded")]
        )
        assert "battery" not in result.wrong_parts_replaced
        assert result.parts_discipline == 25.0

    def test_a_genuinely_wrong_part_is_still_penalized(self) -> None:
        result = _run_agent(
            COMPOUND,
            [
                ("measure_voltage", "battery_positive", "battery_negative", "key_off"),
                ("replace_part", "alternator"),
                ("replace_part", "ground_strap"),
                ("replace_part", "battery"),
                ("attempt_start",),
                ("finish", "ground_strap corroded and battery weak"),
            ],
        )
        assert result.wrong_parts_replaced == ["alternator"]
        assert result.parts_discipline == 17.0

    def test_component_only_naming_earns_half_of_each_share(self) -> None:
        result = _run_agent(
            COMPOUND,
            _EXPERT_STEPS
            + [("finish", "the ground strap and the battery are both bad")],
        )
        assert result.primary_cause == PRIMARY_MAX / 2
        assert result.secondary_cause == SECONDARY_MAX / 2

    def test_breakdown_exposes_the_compound_split(self) -> None:
        result = _run_agent(
            COMPOUND, _EXPERT_STEPS + [("finish", "ground_strap corroded, battery weak")]
        )
        dumped = result.model_dump()
        assert dumped["primary_cause"] == "45/45"
        assert dumped["secondary_cause"] == "15/15"
        assert dumped["root_cause"] == "60/60"
        assert dumped["true_secondary"] == "battery weak"

    def test_single_fault_scenarios_have_no_secondary_buckets(self) -> None:
        result = _run_agent(
            "medium_corroded_ground",
            [
                ("measure_voltage", "battery_negative", "engine_block", "cranking"),
                ("replace_part", "ground_strap"),
                ("attempt_start",),
                ("finish", "ground_strap corroded"),
            ],
        )
        dumped = result.model_dump()
        assert "primary_cause" not in dumped
        assert "secondary_cause" not in dumped
        assert dumped["root_cause"] == "60/60"
        assert result.total == 100.0
