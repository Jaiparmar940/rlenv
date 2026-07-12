"""Anti-cheat grader tests and adversarial agent simulations."""

from __future__ import annotations

import pytest

from nostart.domain.components import Component, FailureMode
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

    def test_prose_diagnosis_first_mention_wins(self) -> None:
        # Real claude-sonnet-5 answer that the length-sorted parser misread
        # as starter_motor (mentioned later, only to describe the symptom).
        text = (
            "Root cause: engine-to-chassis ground strap has a corroded/"
            "high-resistance connection. Cranking voltage-drop test showed "
            "~2.8V drop across engine_block-to-chassis. This excessive "
            "ground resistance starves the starter motor of usable voltage, "
            "causing slow cranking. Battery and starter motor tested "
            "normally and are not the cause."
        )
        comp, mode = parse_diagnosis(text)
        assert comp == Component.GROUND_STRAP
        assert mode == FailureMode.CORRODED

    def test_weak_battery_exoneration_does_not_hijack_mode(self) -> None:
        # Real claude-sonnet-5 red-herring answer: 'weak' appears only in
        # the sentence PROVING the battery innocent; mode must stay corroded.
        text = (
            "Root cause: engine-to-chassis ground strap has excessive "
            "resistance (corroded/loose ground strap), not the battery. "
            "A genuinely weak battery would sag much lower under starter "
            "load, so the battery itself is essentially healthy."
        )
        comp, mode = parse_diagnosis(text)
        assert comp == Component.GROUND_STRAP
        assert mode == FailureMode.CORRODED

    def test_prose_diagnosis_exoneration_does_not_hijack(self) -> None:
        text = (
            "Battery failure — internally shorted/sulfated cell, reading "
            "2.1V at rest. The starter relay and ignition switch are fine."
        )
        comp, _ = parse_diagnosis(text)
        assert comp == Component.BATTERY

    # --- Real answers from the 2026-07-12 run that were correct but
    # mis-scored; each pins a parser fix. ---

    def test_hyphenated_compound_does_not_hijack_component(self) -> None:
        # claude-sonnet-5 red-herring e1 (scored 0/60): "battery" inside
        # "engine-to-battery" starts before "ground strap" does.
        text = (
            "Root cause: corroded/high-resistance engine-to-battery ground "
            "strap (not the battery). Evidence: Battery rest voltage was "
            "only slightly low (11.82V) and held up reasonably under "
            "cranking (11.6V), so the battery itself wasn't the primary "
            "culprit."
        )
        comp, mode = parse_diagnosis(text)
        assert comp == Component.GROUND_STRAP
        assert mode == FailureMode.CORRODED

    def test_node_name_does_not_hijack_component(self) -> None:
        # Measurement citations lead many answers; "battery negative" is a
        # node, not a diagnosis.
        text = (
            "The 2.8V drop from battery negative to engine block under "
            "cranking proves the ground strap is corroded."
        )
        comp, mode = parse_diagnosis(text)
        assert comp == Component.GROUND_STRAP
        assert mode == FailureMode.CORRODED

    def test_high_resistance_maps_to_corroded_for_strap(self) -> None:
        # grok-4 corroded-ground (all 3 epochs, scored 30/60): standard
        # tech phrasing for exactly this fault.
        comp, mode = parse_diagnosis("ground_strap high resistance (voltage drop)")
        assert comp == Component.GROUND_STRAP
        assert mode == FailureMode.CORRODED

    def test_high_resistance_stays_literal_for_fusible_link(self) -> None:
        comp, mode = parse_diagnosis("fusible_link high resistance")
        assert comp == Component.FUSIBLE_LINK
        assert mode == FailureMode.HIGH_RESISTANCE

    def test_internally_failed_battery_is_dead(self) -> None:
        # gpt-5.5 easy e1/e2 (scored 30/60). "corroded terminals" later in
        # the answer must not bleed in (corroded is not a battery mode).
        text = (
            "battery internally failed / severely discharged. Key-off "
            "battery voltage was only 2.13 V with corroded terminals and "
            "sulfation odor; after replacing the battery, the engine "
            "started successfully."
        )
        comp, mode = parse_diagnosis(text)
        assert comp == Component.BATTERY
        assert mode == FailureMode.DEAD

    def test_internal_failure_shorted_cell_is_dead(self) -> None:
        # claude-sonnet-5 easy e2 (scored 30/60).
        text = (
            "Root cause: Battery internal failure (shorted/sulfated cell "
            "causing near-total loss of charge). Key-off terminal voltage "
            "measured only 2.13V. Ground strap was intact and tight, "
            "ruling out a grounding fault."
        )
        comp, mode = parse_diagnosis(text)
        assert comp == Component.BATTERY
        assert mode == FailureMode.DEAD


class TestExpertAgent:
    """Sanity: a full-resolution expert path (diagnose, repair, verify) = 100."""

    def test_easy_dead_battery_expert_full_resolution(self) -> None:
        result = _run_agent(
            "easy_dead_battery",
            [
                ("attempt_start",),
                ("measure_voltage", "battery_positive", "battery_negative", "key_off"),
                ("replace_part", "battery"),
                ("attempt_start",),
                ("finish", "battery dead"),
            ],
        )
        assert result.root_cause == 60.0
        assert result.fix_verified
        assert not result.resolution_penalty_applied
        assert result.total == 100.0

    def test_corroded_ground_expert_full_resolution(self) -> None:
        result = _run_agent(
            "medium_corroded_ground",
            [
                ("attempt_start",),
                ("measure_voltage", "battery_positive", "battery_negative", "key_off"),
                ("measure_voltage", "battery_positive", "battery_negative", "cranking"),
                ("measure_voltage", "battery_negative", "engine_block", "cranking"),
                ("measure_voltage", "battery_positive", "starter_stud", "cranking"),
                ("replace_part", "ground_strap"),
                ("attempt_start",),
                ("finish", "ground_strap corroded"),
            ],
        )
        assert result.root_cause == 60.0
        assert result.fix_verified
        assert result.total == 100.0


class TestResolutionPenalty:
    """Full resolution is required: diagnose-only and unverified repairs lose points."""

    def test_diagnose_only_penalized_even_when_correct(self) -> None:
        result = _run_agent(
            "easy_dead_battery",
            [
                ("attempt_start",),
                ("measure_voltage", "battery_positive", "battery_negative", "key_off"),
                ("finish", "battery dead"),
            ],
        )
        assert result.root_cause == 60.0
        assert not result.fix_verified
        assert result.resolution_penalty_applied
        assert result.total == 85.0  # 60 + 25 + 15 - 15

    def test_correct_repair_without_verify_penalized(self) -> None:
        result = _run_agent(
            "easy_dead_battery",
            [
                ("attempt_start",),
                ("measure_voltage", "battery_positive", "battery_negative", "key_off"),
                ("replace_part", "battery"),
                ("finish", "battery dead"),
            ],
        )
        assert not result.fix_verified
        assert result.resolution_penalty_applied
        assert result.total == 85.0

    def test_start_before_replacement_does_not_count_as_verify(self) -> None:
        # Crank, replace, never re-crank: the pre-replacement attempt must not
        # satisfy verification.
        result = _run_agent(
            "easy_dead_battery",
            [
                ("measure_voltage", "battery_positive", "battery_negative", "key_off"),
                ("attempt_start",),
                ("replace_part", "battery"),
                ("finish", "battery dead"),
            ],
        )
        assert not result.fix_verified
        assert result.resolution_penalty_applied

    def test_blind_swap_hits_guessing_cap(self) -> None:
        # Replace-crank-finish with zero measurements before the repair: the
        # verify crank must NOT count as the probe that dodges the cap.
        result = _run_agent(
            "easy_dead_battery",
            [
                ("replace_part", "battery"),
                ("attempt_start",),
                ("finish", "dead battery"),
            ],
        )
        assert result.fix_verified  # repair itself is legitimate...
        assert result.guessing_penalty_applied  # ...but it was a guess
        assert result.total <= GUESSING_CAP

    def test_flailing_inspection_debits_total(self) -> None:
        # Correct diagnosis, clean hands, verified fix — but 60 min of probing
        # vs the 25-min expert (2.4x). Cost goes negative: 15*(2-2.4) = -6,
        # so total = 60 + 25 - 6 = 79.
        batt = ("battery_positive", "battery_negative")
        result = _run_agent(
            "easy_dead_battery",
            [
                ("attempt_start",),
                ("read_pid", "battery_voltage"),
                ("read_pid", "alt_output_v"),
                ("read_pid", "rpm"),
                ("read_pid", "can_status"),
                ("measure_voltage", *batt, "cranking"),
                ("measure_voltage", *batt, "key_off"),
                ("measure_voltage", *batt, "key_on"),
                ("visual_inspect", "ground_strap"),
                ("visual_inspect", "battery"),
                ("replace_part", "battery"),
                ("scan_dtcs",),
                ("attempt_start",),
                ("read_pid", "can_status"),
                ("measure_voltage", *batt, "key_on"),
                ("measure_voltage", *batt, "key_off"),
                ("measure_voltage", "engine_block", "battery_negative", "key_off"),
                ("measure_voltage", "engine_block", "alt_output", "key_off"),
                ("finish", "dead battery"),
            ],
        )
        assert result.root_cause == 60.0
        assert result.fix_verified
        assert result.cost_efficiency == -6.0
        assert result.total == 79.0

    def test_wrong_part_relief_does_not_verify(self) -> None:
        # Red herring: swap the innocent battery, car still slow-cranks.
        result = _run_agent(
            "medium_ground_red_herring_battery",
            [
                ("measure_voltage", "battery_positive", "battery_negative", "key_off"),
                ("replace_part", "battery"),
                ("attempt_start",),
                ("finish", "battery weak"),
            ],
        )
        assert not result.fix_verified
        assert result.resolution_penalty_applied


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
