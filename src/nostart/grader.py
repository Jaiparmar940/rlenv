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

# --- Compound (two genuine faults) scenarios ---
# The 60-point root-cause budget SPLITS; it does not grow. Totals stay on the
# same 0-100 scale as single-fault scenarios, and a tech who names both faults
# earns exactly the 60 a correct single-fault answer earns.
#   primary   (the root cause; scenario.root_cause)      -> 45
#   secondary (the co-fault;   scenario.secondary_fault) -> 15
# Each is scored like the single-fault bucket: full on component+mode, half on
# component-only. Naming ONLY the secondary therefore caps root credit at
# 15/60 — partial credit, never a pass. Replacing the secondary part is NOT a
# wrong part: it really is bad, and a real tech who fixes both must not be
# penalized for the second repair.
PRIMARY_MAX = 45.0
SECONDARY_MAX = 15.0

# Cost efficiency is TIME-ONLY. Parts dollars are policed by parts discipline
# (wrong parts) and are identical to the expert's for the correct repair, so
# folding them into the cost ratio only dilutes wasted diagnostic time — a
# $180 battery on both sides made a 2.4x time overrun look like 1.3x.
# Linear decay: full points at/below expert time, zero at 2x expert time,
# NEGATIVE beyond (debits the total, mirroring the wrong-part rule) — there
# is no flail-freely zone past the bucket floor.
COST_ZERO_AT_RATIO = 2.0


def _out_of(value: float, maximum: float) -> str:
    fmt = lambda x: f"{x:g}"  # noqa: E731 — 60.0 -> "60", 13.24 -> "13.24"
    return f"{fmt(value)}/{fmt(maximum)}"


class GradeBreakdown(BaseModel):
    # root_cause is ALWAYS the full 60-point bucket. In a compound scenario it
    # is the sum of primary_cause (/45) and secondary_cause (/15), so callers
    # (and the pass^k metric) keep a single, comparable denominator.
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
    # Compound scenarios only (None / 0.0 otherwise).
    primary_cause: float = 0.0
    secondary_cause: float = 0.0
    true_secondary: str | None = None
    diagnosed_secondary: bool = False
    wrong_parts_replaced: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)

    def model_dump(self, **kwargs) -> dict:
        """Score buckets serialize as 'value/max' (e.g. '60/60') so every
        displayed breakdown carries its denominator. Attribute access stays
        numeric for programmatic use."""
        data = super().model_dump(**kwargs)
        data["root_cause"] = _out_of(self.root_cause, ROOT_CAUSE_MAX)
        data["parts_discipline"] = _out_of(self.parts_discipline, PARTS_DISCIPLINE_MAX)
        data["cost_efficiency"] = _out_of(self.cost_efficiency, COST_EFFICIENCY_MAX)
        data["total"] = _out_of(self.total, 100.0)
        if self.true_secondary is None:
            # Non-compound scenario: don't clutter the breakdown with buckets
            # that cannot be earned.
            data.pop("primary_cause", None)
            data.pop("secondary_cause", None)
            data.pop("diagnosed_secondary", None)
        else:
            data["primary_cause"] = _out_of(self.primary_cause, PRIMARY_MAX)
            data["secondary_cause"] = _out_of(self.secondary_cause, SECONDARY_MAX)
        return data


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
    "internal_short": (FailureMode.DEAD,),
    "shorted_cell": (FailureMode.DEAD,),
    # Substring match: "sulfat" covers sulfated / sulfation / sulfating
    # ("battery failed; internal short or sulfation" — claude-haiku-4-5).
    "sulfat": (FailureMode.DEAD,),
    "discharged": (FailureMode.DEAD,),
    # "aged battery with low capacity" — claude-haiku-4-5 hard_compound e2
    # (2026-07-12 hard-tier run): correct weak-battery secondary scored
    # component-only (7.5/15). "Low capacity" cannot mean dead (a dead
    # battery reads ~2 V, not ~11 V). Bare "failed" is deliberately NOT
    # mapped: it does not disambiguate weak from dead and would credit
    # vague answers.
    "low_capacity": (FailureMode.WEAK,),
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


_COMPONENT_ALIASES: dict[str, Component] = {
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


def component_mentions(text: str) -> dict[Component, int]:
    """Every component named in the text → index of its earliest visible mention.

    "Visible" excludes shielded spans (node names, X-to-Y compounds). Full
    names take precedence; aliases only fill in components the full-name pass
    did not find, so "ground strap" is not also counted as "ground".
    """
    lowered = text.strip().lower()
    shields = _shielded_spans(lowered)

    def visible(idx: int) -> bool:
        return not any(start <= idx < end for start, end in shields)

    found: dict[Component, int] = {}

    def note(comp: Component, idx: int) -> None:
        if idx >= 0 and (comp not in found or idx < found[comp]):
            found[comp] = idx

    for comp in Component:
        for needle in (comp.value, comp.value.replace("_", " ")):
            idx = lowered.find(needle)
            while idx >= 0 and not visible(idx):
                idx = lowered.find(needle, idx + 1)
            note(comp, idx)

    if not found:
        for alias, comp in _COMPONENT_ALIASES.items():
            for match in re.finditer(rf"\b{re.escape(alias)}\b", lowered):
                if visible(match.start()):
                    note(comp, match.start())
                    break
    return found


def parse_diagnosis(text: str | None) -> tuple[Component | None, FailureMode | None]:
    """Fuzzy-parse agent diagnosis into component + failure mode.

    EARLIEST visible mention wins: models lead with their diagnosis, and later
    prose often mentions other components only to exonerate them ("...starves
    the starter motor; battery is not the cause").
    """
    if not text or not text.strip():
        return None, None

    raw = text.strip()
    lowered = raw.lower()

    component: Component | None = normalize_component(raw)
    if component is None:
        mentions = component_mentions(lowered)
        if mentions:
            component = min(mentions, key=lambda c: mentions[c])

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


def score_fault_mention(
    text: str,
    true_component: Component,
    true_mode: FailureMode,
    maximum: float,
) -> float:
    """Credit for naming one fault ANYWHERE in the diagnosis text.

    Used for compound scenarios, where a correct answer names two components
    and earliest-mention parsing would score only whichever the model wrote
    first. Mode is resolved against the component's own valid modes
    (parse_failure_mode), and the two components in a compound scenario have
    disjoint mode vocabularies, so the modes cannot cross-credit.

    Known limitation (documented, not fixed): a diagnosis that mentions a
    component only to EXONERATE it still counts as a mention here. In a
    compound scenario both named components really are faulty, so exoneration
    prose is simply a wrong answer.
    """
    if true_component not in component_mentions(text):
        return 0.0
    mode = parse_failure_mode(text.lower(), true_component)
    return maximum if mode == true_mode else maximum / 2.0


def score_parts_discipline(
    root_component: Component,
    replaced: set[Component],
    *,
    also_faulty: frozenset[Component] = frozenset(),
) -> tuple[float, list[str]]:
    """Wrong parts = replaced components that were not actually faulty.

    ``also_faulty`` holds a compound scenario's secondary component: it really
    is bad, so replacing it is a correct repair, not a parts-cannon shot.
    """
    correct = {root_component} | set(also_faulty)
    wrong = [c for c in sorted(replaced, key=lambda x: x.value) if c not in correct]
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
    secondary = world.secondary_fault
    snapshot = world.public_snapshot()
    text = snapshot.diagnosis or ""

    diagnosed_component, diagnosed_mode = parse_diagnosis(snapshot.diagnosis)

    primary_pts = 0.0
    secondary_pts = 0.0
    if secondary is None:
        root_pts = score_root_cause(
            root.component,
            root.mode,
            diagnosed_component,
            diagnosed_mode,
        )
    else:
        # Compound: score each fault on its own mention, so an answer naming
        # both in either order gets both. The 60-point budget splits 45/15.
        primary_pts = score_fault_mention(
            text, root.component, root.mode, PRIMARY_MAX
        )
        secondary_pts = score_fault_mention(
            text, secondary.component, secondary.mode, SECONDARY_MAX
        )
        root_pts = primary_pts + secondary_pts

    parts_pts, wrong_parts = score_parts_discipline(
        root.component,
        world.replaced_components,
        also_faulty=(
            frozenset({secondary.component}) if secondary else frozenset()
        ),
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

    if secondary is None:
        if diagnosed_component != root.component:
            details.append("Root cause component mismatch (symptom masking ignored).")
    else:
        if primary_pts == 0.0:
            details.append(
                "Primary (root cause) fault not named; full root-cause credit "
                "is unreachable without it."
            )
        if secondary_pts == 0.0:
            details.append("Secondary co-fault not named.")

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
        primary_cause=primary_pts,
        secondary_cause=secondary_pts,
        true_secondary=(
            f"{secondary.component.value} {secondary.mode.value}"
            if secondary
            else None
        ),
        diagnosed_secondary=secondary_pts > 0.0,
        wrong_parts_replaced=wrong_parts,
        details=details,
    )
