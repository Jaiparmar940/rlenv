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
    expert_baseline_cost: dict[str, float] = Field(
        description="Expert baseline: minutes and dollars"
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
        expert_baseline_cost={"minutes": 15.0, "dollars": 0.0},  # TODO(VERIFY)
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
            severity={"added_resistance_ohms": 1.1},  # TODO(VERIFY)
        ),
        expert_baseline_cost={"minutes": 35.0, "dollars": 25.0},  # TODO(VERIFY): strap cost
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
            severity={"added_resistance_ohms": 1.2},  # TODO(VERIFY): slightly worse ground
        ),
        # Resting supply path uniformly suppressed as bait (NOT the root cause).
        # Under cranking the corroded ground physics naturally lets the battery
        # hold high (reduced current) while the ground-path drop appears — the tell.
        red_herring_voltages={
            "battery_positive": 11.8,  # TODO(VERIFY): marginal but not dead; resting only
        },
        red_herring_component=Component.BATTERY,
        expert_baseline_cost={"minutes": 40.0, "dollars": 25.0},  # TODO(VERIFY)
    ),
}


def get_scenario(scenario_id: str) -> ScenarioDef:
    if scenario_id not in SCENARIOS:
        available = ", ".join(sorted(SCENARIOS))
        raise KeyError(f"Unknown scenario '{scenario_id}'. Available: {available}")
    return SCENARIOS[scenario_id]


def list_scenarios() -> list[str]:
    return sorted(SCENARIOS.keys())
