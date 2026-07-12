"""Cheat-resistant episode scoring.

The grader reads ground-truth world state only (injected root cause, replaced
parts, probe history). Symptom relief after a wrong-part swap does not count.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from nostart.domain.components import (
    COMPONENT_FAILURE_MODES,
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
# Episodes are full-resolution: the agent must replace the root-cause part AND
# confirm with a successful attempt_start() after the last replacement.
# Diagnose-only finishes and unverified repairs both take this flat debit,
# even when the diagnosis (or the repair) happens to be correct.
RESOLUTION_PENALTY = 15.0
COMPONENT_ONLY_CREDIT = ROOT_CAUSE_MAX / 2.0

# Cost efficiency is TIME-ONLY. Parts dollars are policed by parts discipline
# (wrong parts) and are identical to the expert's for the correct repair, so
# folding them into the cost ratio only dilutes wasted diagnostic time — a
# $180 battery on both sides made a 2.4x time overrun look like 1.3x.
# Linear decay: full points at/below expert time, zero at 2x expert time,
# NEGATIVE beyond (debits the total, mirroring the wrong-part rule) — there
# is no flail-freely zone past the bucket floor.
COST_ZERO_AT_RATIO = 2.0


class GradeBreakdown(BaseModel):
    root_cause: float = 0.0
    parts_discipline: float = 0.0
    cost_efficiency: float = 0.0
    total: float = 0.0
    guessing_penalty_applied: bool = False
    fix_verified: bool = False
    resolution_penalty_applied: bool = False
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
    "no_crank_signal": FailureMode.NO_CRANK_SIGNAL,
    "no_crank": FailureMode.NO_CRANK_SIGNAL,
    "accessory_drop": FailureMode.ACCESSORY_DROP,
    "bus_off": FailureMode.BUS_OFF,
    "intermittent": FailureMode.INTERMITTENT,
}

# Real-tech vocabulary that maps to a mode DEPENDING on the component:
# candidates in priority order, resolved to the first one the diagnosed
# component can actually have. Every entry is justified by an actual model
# answer that was correct but scored component-only (2026-07-12 run):
# "ground_strap high resistance" (grok-4, gpt-5.5), "battery internally
# failed / severely discharged" (gpt-5.5), "battery internal failure
# (shorted/sulfated cell)" (claude-sonnet-5). Keys are normalized tokens
# (lowercase, spaces/hyphens -> underscores).
_MODE_SYNONYMS: dict[str, tuple[FailureMode, ...]] = {
    # A resistive strap is "corroded"; a resistive fusible link keeps its
    # own enum. Unknown component defaults to the literal enum.
    "high_resistance": (FailureMode.HIGH_RESISTANCE, FailureMode.CORRODED),
    "excessive_resistance": (FailureMode.CORRODED, FailureMode.HIGH_RESISTANCE),
    "internally_failed": (FailureMode.DEAD,),
    "internal_failure": (FailureMode.DEAD,),
    "internally_shorted": (FailureMode.DEAD,),
    "shorted_cell": (FailureMode.DEAD,),
    "sulfated": (FailureMode.DEAD,),
    "discharged": (FailureMode.DEAD,),
}


def _normalize_mode_token(token: str) -> str:
    return token.strip().lower().replace("-", "_").replace(" ", "_")


def parse_failure_mode(
    text: str, component: Component | None = None
) -> FailureMode | None:
    """Extract a failure mode from free-text diagnosis.

    When the diagnosed component is known, only modes that component can
    actually have are considered — otherwise prose explaining a red herring
    ("a genuinely weak battery would sag lower") hijacks the mode slot.
    Among valid candidates, the EARLIEST mention wins (models lead with
    their diagnosis).
    """
    normalized = _normalize_mode_token(text)
    valid: set[FailureMode] | None = None
    if component is not None:
        valid = set(COMPONENT_FAILURE_MODES.get(component, []))

    def allowed(mode: FailureMode) -> bool:
        return valid is None or mode in valid

    if normalized in _MODE_ALIASES and allowed(_MODE_ALIASES[normalized]):
        return _MODE_ALIASES[normalized]

    earliest: tuple[int, FailureMode] | None = None
    candidates: list[tuple[str, tuple[FailureMode, ...]]] = [
        (mode.value, (mode,)) for mode in FailureMode
    ]
    candidates += [(needle, (mode,)) for needle, mode in _MODE_ALIASES.items()]
    candidates += list(_MODE_SYNONYMS.items())
    for needle, modes in candidates:
        mode = next((m for m in modes if allowed(m)), None)
        if mode is None:
            continue
        idx = normalized.find(needle)
        if idx >= 0 and (earliest is None or idx < earliest[0]):
            earliest = (idx, mode)
    return earliest[1] if earliest else None


# Regions where a component name is NOT a diagnosis: measurement-node names
# ("battery negative") and hyphenated compounds modifying another component
# ("engine-to-battery ground strap" — which cost a fully correct
# claude-sonnet-5 answer 60 points when first-mention matching read it as
# "battery"). A component mention inside any such span is ignored.
_SHIELD_PATTERNS = [
    re.compile(r"battery[\s_-]+(positive|negative)"),
    re.compile(r"\b[a-z_]+[\s_-]*-[\s_-]*to[\s_-]*-[\s_-]*[a-z_]+"),
]


def _shielded_spans(lowered: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern in _SHIELD_PATTERNS:
        spans += [m.span() for m in pattern.finditer(lowered)]
    return spans


def parse_diagnosis(text: str | None) -> tuple[Component | None, FailureMode | None]:
    """Fuzzy-parse agent diagnosis into component + failure mode."""
    if not text or not text.strip():
        return None, None

    raw = text.strip()
    lowered = raw.lower()

    component: Component | None = normalize_component(raw)
    if component is None:
        # EARLIEST full-name mention wins: models lead with their diagnosis,
        # and later prose often mentions other components only to exonerate
        # them ("...starves the starter motor; battery is not the cause").
        shields = _shielded_spans(lowered)

        def visible(idx: int) -> bool:
            return not any(start <= idx < end for start, end in shields)

        earliest: tuple[int, Component] | None = None
        for comp in Component:
            for needle in (comp.value, comp.value.replace("_", " ")):
                idx = lowered.find(needle)
                while idx >= 0 and not visible(idx):
                    idx = lowered.find(needle, idx + 1)
                if idx >= 0 and (earliest is None or idx < earliest[0]):
                    earliest = (idx, comp)
        if earliest is None:
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
                for match in re.finditer(rf"\b{re.escape(alias)}\b", lowered):
                    if not visible(match.start()):
                        continue
                    if earliest is None or match.start() < earliest[0]:
                        earliest = (match.start(), comp)
                    break
        if earliest is not None:
            component = earliest[1]

    mode = parse_failure_mode(lowered, component)
    return component, mode


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
    baseline: dict[str, float],
) -> float:
    expert = baseline["minutes"]
    if agent_minutes <= 0:
        return 0.0  # finish-only episode; nothing to reward
    ratio = agent_minutes / expert
    if ratio <= 1.0:
        return COST_EFFICIENCY_MAX
    # Falls through zero at COST_ZERO_AT_RATIO and keeps going negative.
    scale = (COST_ZERO_AT_RATIO - ratio) / (COST_ZERO_AT_RATIO - 1.0)
    return round(COST_EFFICIENCY_MAX * scale, 2)


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
        scenario.expert_baseline_cost,
    )

    total = root_pts + parts_pts + cost_pts
    # Guessing = no probe BEFORE the first replacement. Total probe count is
    # not enough: the required verify crank would hand every blind part-swap
    # a free probe and make this cap dead code.
    guessing = world.diagnostic_probe_count == 0
    details: list[str] = []

    # Wrong parts debit the TOTAL, not just the clamped discipline bucket:
    # beyond ~3 wrong parts the bucket floors at 0, and without this a
    # measure-once-then-shotgun agent still outscores careful-but-wrong ones.
    wrong_penalty = len(wrong_parts) * WRONG_PART_PENALTY
    if wrong_penalty:
        total = max(0.0, total - wrong_penalty)
        details.append(
            f"{len(wrong_parts)} wrong part(s) replaced; "
            f"-{wrong_penalty:.0f} applied to total."
        )

    # Resolution requirement: root part replaced AND a successful start
    # observed after the last replacement. Symptom relief from a wrong-part
    # swap does not verify anything (root component check), and a correct
    # repair the agent never cranked is an unverified fix.
    fix_verified = root.component in world.replaced_components and world.fix_verified
    if not fix_verified:
        total = max(0.0, total - RESOLUTION_PENALTY)
        details.append(
            "Problem not verifiably resolved (root part replaced + successful "
            f"start required); -{RESOLUTION_PENALTY:.0f} applied to total."
        )

    if guessing:
        total = min(total, GUESSING_CAP)
        details.append(
            f"No measurements before finish(); total capped at {GUESSING_CAP:.0f}."
        )

    if diagnosed_component != root.component:
        details.append("Root cause component mismatch (symptom masking ignored).")

    total = max(0.0, total)  # negative cost_pts must not push the total below 0

    return GradeBreakdown(
        root_cause=root_pts,
        parts_discipline=parts_pts,
        cost_efficiency=cost_pts,
        total=round(total, 2),
        guessing_penalty_applied=guessing,
        fix_verified=fix_verified,
        resolution_penalty_applied=not fix_verified,
        diagnosed_component=diagnosed_component.value if diagnosed_component else None,
        diagnosed_mode=diagnosed_mode.value if diagnosed_mode else None,
        true_component=root.component.value,
        true_mode=root.mode.value,
        wrong_parts_replaced=wrong_parts,
        details=details,
    )
