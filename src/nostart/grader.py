"""Cheat-resistant episode scoring.

The grader reads ground-truth world state only (injected root cause, replaced
parts, probe history). Symptom relief after a wrong-part swap does not count.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from nostart.domain.components import (
    Component,
    FailureMode,
    normalize_component,
)
from nostart.domain.scenarios import ScenarioDef
from nostart.world import World

ROOT_CAUSE_MAX = 60.0
PARTS_DISCIPLINE_MAX = 25.0
COST_EFFICIENCY_MAX = 15.0
GUESSING_CAP = 40.0
WRONG_PART_PENALTY = 8.0
COMPONENT_ONLY_CREDIT = ROOT_CAUSE_MAX / 2.0

# Map dollars to minute-equivalents for cost-efficiency scaling.
DOLLARS_PER_MINUTE_EQUIV = 10.0


class GradeBreakdown(BaseModel):
    root_cause: float = 0.0
    parts_discipline: float = 0.0
    cost_efficiency: float = 0.0
    total: float = 0.0
    guessing_penalty_applied: bool = False
    diagnosed_component: str | None = None
    diagnosed_mode: str | None = None
    true_component: str
    true_mode: str
    wrong_parts_replaced: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)


_MODE_ALIASES: dict[str, FailureMode] = {
    "weak": FailureMode.WEAK,
    "dead": FailureMode.DEAD,
    "corroded": FailureMode.CORRODED,
    "corrosion": FailureMode.CORRODED,
    "broken": FailureMode.BROKEN,
    "stuck_open": FailureMode.STUCK_OPEN,
    "stuck_closed": FailureMode.STUCK_CLOSED,
    "worn_brushes": FailureMode.WORN_BRUSHES,
    "worn": FailureMode.WORN_BRUSHES,
    "seized": FailureMode.SEIZED,
    "diode_failure": FailureMode.DIODE_FAILURE,
    "diode": FailureMode.DIODE_FAILURE,
    "no_output": FailureMode.NO_OUTPUT,
    "blown": FailureMode.BLOWN,
    "high_resistance": FailureMode.HIGH_RESISTANCE,
    "no_crank_signal": FailureMode.NO_CRANK_SIGNAL,
    "no_crank": FailureMode.NO_CRANK_SIGNAL,
    "accessory_drop": FailureMode.ACCESSORY_DROP,
    "bus_off": FailureMode.BUS_OFF,
    "intermittent": FailureMode.INTERMITTENT,
}


def _normalize_mode_token(token: str) -> str:
    return token.strip().lower().replace("-", "_").replace(" ", "_")


def parse_failure_mode(text: str) -> FailureMode | None:
    """Extract a failure mode from free-text diagnosis."""
    normalized = _normalize_mode_token(text)
    if normalized in _MODE_ALIASES:
        return _MODE_ALIASES[normalized]
    for mode in FailureMode:
        if mode.value in normalized or mode.value.replace("_", " ") in normalized:
            return mode
    for alias, mode in _MODE_ALIASES.items():
        if alias in normalized:
            return mode
    return None


def parse_diagnosis(text: str | None) -> tuple[Component | None, FailureMode | None]:
    """Fuzzy-parse agent diagnosis into component + failure mode."""
    if not text or not text.strip():
        return None, None

    raw = text.strip()
    lowered = raw.lower()

    component: Component | None = normalize_component(raw)
    if component is None:
        # Longest token match first to prefer ground_strap over strap-like noise.
        for comp in sorted(Component, key=lambda c: len(c.value), reverse=True):
            if comp.value in lowered or comp.value.replace("_", " ") in lowered:
                component = comp
                break
        if component is None:
            aliases = {
                "bat": Component.BATTERY,
                "ground": Component.GROUND_STRAP,
                "relay": Component.STARTER_RELAY,
                "starter": Component.STARTER_MOTOR,
                "alternator": Component.ALTERNATOR,
                "alt": Component.ALTERNATOR,
                "fuse": Component.FUSIBLE_LINK,
                "ignition": Component.IGNITION_SWITCH,
                "ecu": Component.ECU_CAN_NODE,
                "can": Component.ECU_CAN_NODE,
            }
            for alias, comp in aliases.items():
                if re.search(rf"\b{re.escape(alias)}\b", lowered):
                    component = comp
                    break

    mode = parse_failure_mode(lowered)
    return component, mode


def _combined_cost(minutes: float, dollars: float) -> float:
    return minutes + dollars / DOLLARS_PER_MINUTE_EQUIV


def score_root_cause(
    true_component: Component,
    true_mode: FailureMode,
    diagnosed_component: Component | None,
    diagnosed_mode: FailureMode | None,
) -> float:
    if diagnosed_component is None:
        return 0.0
    if diagnosed_component != true_component:
        return 0.0
    if diagnosed_mode == true_mode:
        return ROOT_CAUSE_MAX
    if diagnosed_mode is not None:
        return COMPONENT_ONLY_CREDIT
    return COMPONENT_ONLY_CREDIT


def score_parts_discipline(
    root_component: Component,
    replaced: set[Component],
) -> tuple[float, list[str]]:
    wrong = [c for c in sorted(replaced, key=lambda x: x.value) if c != root_component]
    penalty = len(wrong) * WRONG_PART_PENALTY
    points = max(0.0, PARTS_DISCIPLINE_MAX - penalty)
    return points, [c.value for c in wrong]


def score_cost_efficiency(
    agent_minutes: float,
    agent_dollars: float,
    baseline: dict[str, float],
) -> float:
    expert = _combined_cost(baseline["minutes"], baseline["dollars"])
    agent = _combined_cost(agent_minutes, agent_dollars)
    if agent <= 0:
        return 0.0
    if agent <= expert:
        return COST_EFFICIENCY_MAX
    ratio = expert / agent
    return round(COST_EFFICIENCY_MAX * min(1.0, ratio), 2)


def grade(world: World) -> GradeBreakdown:
    """Score a finished (or in-progress) episode from ground truth."""
    scenario: ScenarioDef = world.scenario
    root = world.root_cause
    snapshot = world.public_snapshot()

    diagnosed_component, diagnosed_mode = parse_diagnosis(snapshot.diagnosis)
    root_pts = score_root_cause(
        root.component,
        root.mode,
        diagnosed_component,
        diagnosed_mode,
    )
    parts_pts, wrong_parts = score_parts_discipline(
        root.component,
        world.replaced_components,
    )
    cost_pts = score_cost_efficiency(
        snapshot.cumulative_cost.minutes,
        snapshot.cumulative_cost.dollars,
        scenario.expert_baseline_cost,
    )

    total = root_pts + parts_pts + cost_pts
    guessing = world.probe_count == 0
    details: list[str] = []

    if guessing:
        total = min(total, GUESSING_CAP)
        details.append(
            f"No measurements before finish(); total capped at {GUESSING_CAP:.0f}."
        )

    if diagnosed_component != root.component:
        details.append("Root cause component mismatch (symptom masking ignored).")

    return GradeBreakdown(
        root_cause=root_pts,
        parts_discipline=parts_pts,
        cost_efficiency=cost_pts,
        total=round(total, 2),
        guessing_penalty_applied=guessing,
        diagnosed_component=diagnosed_component.value if diagnosed_component else None,
        diagnosed_mode=diagnosed_mode.value if diagnosed_mode else None,
        true_component=root.component.value,
        true_mode=root.mode.value,
        wrong_parts_replaced=wrong_parts,
        details=details,
    )
