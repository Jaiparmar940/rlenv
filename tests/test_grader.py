"""Anti-cheat grader tests and adversarial agent simulations."""

from __future__ import annotations

import pytest

from nostart.domain.components import Component
from nostart.grader import (
    GUESSING_CAP,
    GradeBreakdown,
    grade,
    parse_diagnosis,
)
from nostart.tools import ToolSession


def _run_agent(scenario_id: str, steps: list[tuple[str, ...]]) -> GradeBreakdown:
    session = ToolSession(scenario_id)
    for step in steps:
        cmd = step[0]
        args = step[1:]
        if cmd == "scan_dtcs":
            session.scan_dtcs()
        elif cmd == "read_pid":
            session.read_pid(args[0])
        elif cmd == "measure_voltage":
            session.measure_voltage(args[0], args[1], args[2])
        elif cmd == "visual_inspect":
            session.visual_inspect(args[0])
        elif cmd == "replace_part":
            session.replace_part(args[0])
        elif cmd == "attempt_start":
            session.attempt_start()
        elif cmd == "finish":
            session.finish(args[0])
        else:
            raise ValueError(f"Unknown step: {step}")
    return grade(session.world)


class TestDiagnosisParsing:
    def test_fuzzy_component_and_mode(self) -> None:
        comp, mode = parse_diagnosis("bad ground strap, corroded")
        assert comp == Component.GROUND_STRAP
        assert mode is not None
        assert mode.value == "corroded"

    def test_battery_dead_aliases(self) -> None:
        comp, mode = parse_diagnosis("dead battery")
        assert comp == Component.BATTERY
        assert mode is not None
        assert mode.value == "dead"


class TestExpertAgent:
    """Sanity: a competent diagnostic path should score well."""

    def test_easy_dead_battery_expert(self) -> None:
        result = _run_agent(
            "easy_dead_battery",
            [
                ("measure_voltage", "battery_positive", "battery_negative", "key_on"),
                ("attempt_start",),
                ("finish", "battery dead"),
            ],
        )
        assert result.root_cause == 60.0
        assert result.total >= 70.0
        assert not result.guessing_penalty_applied


# --- Adversarial agents (must score badly) ---


def parts_cannon_agent(scenario_id: str) -> GradeBreakdown:
    """Replace every major part, then guess the last one as root cause."""
    return _run_agent(
        scenario_id,
        [
            ("replace_part", "battery"),
            ("replace_part", "alternator"),
            ("replace_part", "starter_motor"),
            ("replace_part", "starter_relay"),
            ("replace_part", "ground_strap"),
            ("finish", "ground_strap corroded"),
        ],
    )


def measured_parts_cannon_agent(scenario_id: str) -> GradeBreakdown:
    """One token measurement to dodge the guessing cap, then shotgun parts."""
    return _run_agent(
        scenario_id,
        [
            ("measure_voltage", "battery_positive", "battery_negative", "key_on"),
            ("replace_part", "battery"),
            ("replace_part", "alternator"),
            ("replace_part", "starter_motor"),
            ("replace_part", "starter_relay"),
            ("replace_part", "ground_strap"),
            ("finish", "ground_strap corroded"),
        ],
    )


def lucky_guess_agent(scenario_id: str, guess: str) -> GradeBreakdown:
    """Finish immediately with no measurements."""
    return _run_agent(scenario_id, [("finish", guess)])


def mask_the_symptom_agent(scenario_id: str) -> GradeBreakdown:
    """Swap battery to mask slow-crank, blame battery anyway."""
    return _run_agent(
        scenario_id,
        [
            ("measure_voltage", "battery_positive", "battery_negative", "key_on"),
            ("replace_part", "battery"),
            ("attempt_start",),
            ("finish", "battery weak"),
        ],
    )


class TestRedHerringClearedByBatteryReplacement:
    """A known-good battery cannot keep reading marginal at rest."""

    SCENARIO = "medium_ground_red_herring_battery"

    def test_new_battery_reads_nominal_but_fault_persists(self) -> None:
        session = ToolSession(self.SCENARIO)
        before = session.measure_voltage(
            "battery_positive", "battery_negative", "key_off"
        )["volts"]
        assert abs(before - 11.8) <= 0.1  # bait present

        session.replace_part("battery")
        after = session.measure_voltage(
            "battery_positive", "battery_negative", "key_off"
        )["volts"]
        assert abs(after - 12.6) <= 0.1  # bait cleared by fresh battery

        # Root cause untouched: ground-path tell and slow crank persist.
        drop = session.measure_voltage(
            "battery_negative", "engine_block", "cranking"
        )["volts"]
        assert abs(drop) >= 2.5
        assert session.attempt_start()["result"] == "slow_crank"


class TestAdversarialAgents:
    BAD_SCORE_THRESHOLD = 50.0

    def test_parts_cannon_scores_badly_on_ground_scenario(self) -> None:
        result = parts_cannon_agent("medium_corroded_ground")
        assert result.root_cause == 60.0  # correct finish diagnosis
        assert len(result.wrong_parts_replaced) >= 3
        assert result.parts_discipline <= 9.0
        assert result.total < self.BAD_SCORE_THRESHOLD

    def test_measured_parts_cannon_scores_badly_without_guess_cap(self) -> None:
        # One probe evades the guessing cap; the wrong-part debit to the
        # total must still sink the strategy below the bad-score line.
        result = measured_parts_cannon_agent("medium_corroded_ground")
        assert not result.guessing_penalty_applied
        assert result.root_cause == 60.0
        assert len(result.wrong_parts_replaced) == 4
        assert result.total < self.BAD_SCORE_THRESHOLD

    def test_lucky_guess_capped_even_if_correct(self) -> None:
        result = lucky_guess_agent("easy_dead_battery", "battery dead")
        assert result.guessing_penalty_applied
        assert result.total <= GUESSING_CAP
        assert result.root_cause == 60.0

    def test_lucky_guess_wrong_scores_very_low(self) -> None:
        result = lucky_guess_agent("easy_dead_battery", "alternator no_output")
        assert result.total <= GUESSING_CAP
        assert result.root_cause == 0.0

    def test_mask_symptom_wrong_root_cause(self) -> None:
        result = mask_the_symptom_agent("medium_ground_red_herring_battery")
        assert result.diagnosed_component == "battery"
        assert result.true_component == "ground_strap"
        assert result.root_cause <= 30.0  # wrong component or half credit at best
        assert "battery" in result.wrong_parts_replaced
        assert result.total < self.BAD_SCORE_THRESHOLD


@pytest.mark.parametrize(
    "agent_fn,scenario,label",
    [
        (lambda: parts_cannon_agent("medium_corroded_ground"), "medium_corroded_ground", "parts-cannon"),
        (
            lambda: measured_parts_cannon_agent("medium_corroded_ground"),
            "medium_corroded_ground",
            "measured-parts-cannon",
        ),
        (lambda: lucky_guess_agent("easy_dead_battery", "battery dead"), "easy_dead_battery", "lucky-guess"),
        (
            lambda: mask_the_symptom_agent("medium_ground_red_herring_battery"),
            "medium_ground_red_herring_battery",
            "mask-symptom",
        ),
    ],
)
def test_adversarial_demo(agent_fn, scenario: str, label: str) -> None:
    """Print-friendly adversarial run (pytest -s tests/test_grader.py -k adversarial_demo)."""
    result = agent_fn()
    print(
        f"\n[{label}] scenario={scenario} "
        f"total={result.total} "
        f"(root={result.root_cause}, parts={result.parts_discipline}, "
        f"cost={result.cost_efficiency}, guess_cap={result.guessing_penalty_applied})"
    )
    assert result.total < 50.0
