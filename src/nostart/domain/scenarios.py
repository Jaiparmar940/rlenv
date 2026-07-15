"""Seeded scenario definitions.

Each scenario pins a deterministic seed, injected root-cause fault, expert
cost baseline, and customer complaint shown to the agent at episode start.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from nostart.domain.components import Component, FailureMode, InjectedFault


class ScenarioTier(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ScenarioDef(BaseModel):
    id: str
    tier: ScenarioTier
    seed: int
    complaint: str
    root_cause: InjectedFault
    # Compound scenarios: a SECOND genuine fault, injected alongside the root
    # cause. It is not a red herring — the part really is bad and really must
    # be replaced. The grader treats the root cause as PRIMARY (full credit
    # needs it) and this one as SECONDARY (partial credit), and does not count
    # replacing it as a wrong part.
    secondary_fault: InjectedFault | None = None
    # Full-resolution expert baseline: diagnose, replace the root-cause part,
    # and verify with a successful start. Derived from the costs.py model for
    # an explicit expert action sequence (documented per scenario below) —
    # never hand-tuned independently of that sequence.
    expert_baseline_cost: dict[str, float] = Field(
        description="Expert baseline (minutes and dollars), incl. repair + verify"
    )
    # Marginal non-causal RESTING node potentials (red herring). Keyed by node
    # name (e.g. "battery_positive"); applied at key_off/key_on only, never at
    # cranking. Does not inject a fault.
    red_herring_voltages: dict[str, float] = Field(default_factory=dict)
    # Component the red-herring readings belong to: replacing it with a
    # known-good part clears them (a fresh battery cannot read marginal at
    # rest). Required whenever red_herring_voltages is set.
    red_herring_component: Component | None = None


# Phase 1: 3 scenarios (1 easy, 2 medium w/ one red herring).
SCENARIOS: dict[str, ScenarioDef] = {
    "easy_dead_battery": ScenarioDef(
        id="easy_dead_battery",
        tier=ScenarioTier.EASY,
        seed=1001,
        complaint="Car was fine yesterday. This morning: absolutely nothing when I turn the key.",
        root_cause=InjectedFault(
            component=Component.BATTERY,
            mode=FailureMode.DEAD,
        ),
        # Expert path: attempt_start (1) + battery voltage key_off (3)
        # + replace battery (20, $180) + verify start (1) = 25 min, $180.
        expert_baseline_cost={"minutes": 25.0, "dollars": 180.0},
    ),
    "medium_corroded_ground": ScenarioDef(
        id="medium_corroded_ground",
        tier=ScenarioTier.MEDIUM,
        seed=2001,
        complaint=(
            "Engine cranks really slow, especially when cold. "
            "Battery tested 'borderline' at the parts store."
        ),
        root_cause=InjectedFault(
            component=Component.GROUND_STRAP,
            mode=FailureMode.CORRODED,
            severity={"added_resistance_ohms": 1.1},
        ),
        # Expert path: attempt_start (1) + 4 measurements (battery key_off,
        # battery cranking, ground drop cranking, feed drop cranking; 12)
        # + replace ground_strap (20, $25) + verify start (1) = 34 min, $25.
        expert_baseline_cost={"minutes": 34.0, "dollars": 25.0},
    ),
    "medium_ground_red_herring_battery": ScenarioDef(
        id="medium_ground_red_herring_battery",
        tier=ScenarioTier.MEDIUM,
        seed=2002,
        complaint=(
            "Slow crank, won't fire up. Shop said my battery is 'a little weak' "
            "but still should work."
        ),
        root_cause=InjectedFault(
            component=Component.GROUND_STRAP,
            mode=FailureMode.CORRODED,
            severity={"added_resistance_ohms": 1.2},  # slightly worse ground
        ),
        # Resting supply path uniformly suppressed as bait (NOT the root cause).
        # Under cranking the corroded ground physics naturally lets the battery
        # hold high (reduced current) while the ground-path drop appears — the tell.
        red_herring_voltages={
            "battery_positive": 11.8,  # marginal but not dead; resting only
        },
        red_herring_component=Component.BATTERY,
        # Expert path: corroded-ground path (34 min, $25) + one extra battery
        # cross-check under load to rule out the marginal-battery bait (3)
        # = 37 min, $25.
        expert_baseline_cost={"minutes": 37.0, "dollars": 25.0},
    ),
    # --- HARD TIER --------------------------------------------------------
    # Physics for both scenarios below signed off by the domain expert
    # (Jaivir Parmar, 2026-07-12); see DOMAIN_TRUTH.md.
    "hard_intermittent_ecu_can": ScenarioDef(
        id="hard_intermittent_ecu_can",
        tier=ScenarioTier.HARD,
        # Seed chosen (not tuned for score) so the deterministic manifestation
        # sequence is a fair hard case rather than a coin-flip: crank #1
        # cranks-no-start, crank #2 starts, cranks #3/#4 fail again, and the
        # FIRST scan_dtcs comes back clean — a single clean reading must not
        # exonerate the ECU. Sequences are printed in the signoff file.
        seed=3035,
        complaint=(
            "Sometimes it cranks and cranks and just won't fire. Other times "
            "it starts right up. Two shops found nothing wrong."
        ),
        root_cause=InjectedFault(
            component=Component.ECU_CAN_NODE,
            mode=FailureMode.INTERMITTENT,
            severity={"manifest_probability": 0.35},
        ),
        # Expert path: 4x attempt_start (4) — the fault only shows on some
        # cranks — + 2x scan_dtcs (4) + 2x read_pid can_status (2)
        # + replace ecu_can_node (20, $450) + verify start (1) = 31 min, $450.
        expert_baseline_cost={"minutes": 31.0, "dollars": 450.0},
    ),
    "hard_compound_battery_and_ground": ScenarioDef(
        id="hard_compound_battery_and_ground",
        tier=ScenarioTier.HARD,
        seed=3002,
        complaint=(
            "Cranks slow and usually won't catch. Battery's a few years old "
            "but it was fine last winter."
        ),
        # PRIMARY: the subtle fault. A tech who stops at the obvious bad
        # battery leaves the car broken — so the ground strap is the root
        # cause and the battery is the secondary.
        root_cause=InjectedFault(
            component=Component.GROUND_STRAP,
            mode=FailureMode.CORRODED,
            # Lower than the single-fault ground scenarios (1.1/1.2 Ω) on
            # purpose: a weaker choke on cranking current keeps the battery's
            # own load-test failure visible. See the signoff file.
            severity={"added_resistance_ohms": 0.7},
        ),
        # SECONDARY: genuinely bad, not bait. 1.6 V below nominal on the whole
        # rail => ~11.0 V resting (vs the red-herring battery's 11.8 V) and
        # ~8.59 V cranking (vs the red herring's ~10.47 V hold): it FAILS a
        # load test, which is exactly what the red-herring battery does not do.
        secondary_fault=InjectedFault(
            component=Component.BATTERY,
            mode=FailureMode.WEAK,
            severity={"terminal_drop_v": 1.6},
        ),
        # Expert path: attempt_start (1) + 4 measurements (battery key_off,
        # battery cranking, ground drop cranking, feed drop cranking; 12)
        # + replace ground_strap (20, $25) + replace battery (20, $180)
        # + verify start (1) = 54 min, $205. Neither repair alone starts the
        # car, so the expert necessarily buys both parts.
        expert_baseline_cost={"minutes": 54.0, "dollars": 205.0},
    ),
}


def get_scenario(scenario_id: str) -> ScenarioDef:
    if scenario_id not in SCENARIOS:
        available = ", ".join(sorted(SCENARIOS))
        raise KeyError(f"Unknown scenario '{scenario_id}'. Available: {available}")
    return SCENARIOS[scenario_id]


def list_scenarios() -> list[str]:
    return sorted(SCENARIOS.keys())
