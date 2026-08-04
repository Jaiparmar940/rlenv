"""Three-way grader: inference / parsimony / intervention.

Ported discipline from no-start-env:
- Success predicates are checked against BACKEND state (geometry in the sim
  backend), never against agent claims or env bookkeeping shortcuts.
- Inference credit is gated on the revealing observation having actually
  occurred BEFORE the declaration — a lucky guess with the fridge never
  opened earns nothing, even if the words are right.
- Parsimony goes NEGATIVE past 2x the expert action count (flailing debits
  the total), and pays out zero unless the primary intervention landed —
  being tersely useless is not parsimony.
- Total floored at 0.

Buckets: inference 40 / parsimony 25 / intervention 35.
"""

from __future__ import annotations

from dataclasses import dataclass

from .env import Episode
from .task import EXPERT_ACTIONS

INFERENCE_MAX = 40
IMPLICIT_INFERENCE = 20   # revealing inspection before intervening, but no declare
PARSIMONY_MAX = 25
INTERVENTION_PLACE = 25
INTERVENTION_SIDE = 5
INTERVENTION_TIDY = 5
# Discarding fresh food is the wrong-part analog from no-start-env: it can
# "work" (makes room) but destroys value. Debits the intervention bucket per
# item and can push it negative; the total is floored at 0.
FRESH_DISCARD_PENALTY = 15


@dataclass
class Grade:
    inference: float
    parsimony: float
    intervention: float
    notes: list[str]

    @property
    def total(self) -> float:
        return max(0.0, round(self.inference + self.parsimony + self.intervention, 1))

    def report(self) -> str:
        lines = [
            f"  inference     {self.inference:6.1f} / {INFERENCE_MAX}",
            f"  parsimony     {self.parsimony:6.1f} / {PARSIMONY_MAX}",
            f"  intervention  {self.intervention:6.1f} / {INTERVENTION_PLACE + INTERVENTION_SIDE + INTERVENTION_TIDY}",
            f"  TOTAL         {self.total:6.1f} / 100",
        ]
        lines += [f"  - {n}" for n in self.notes]
        return "\n".join(lines)


def _reveal_time(ep: Episode) -> int | None:
    """When did the agent first observe the hidden state's location?"""
    if ep.scenario.variant == "container_missing":
        return ep.microwave_first_opened
    return ep.fridge_first_opened  # nominal and fridge_full both live in the fridge


def _first_intervention_time(ep: Episode) -> int | None:
    for e in ep.events:
        if e.kind in ("pick", "place", "discard") and e.ok:
            return e.t
    return None


def grade(ep: Episode, backend) -> Grade:
    notes: list[str] = []
    variant = ep.scenario.variant
    reveal_t = _reveal_time(ep)

    # --- inference (40) -----------------------------------------------------
    inference = 0.0
    if ep.declares:
        t_last, text, parsed = ep.declares[-1]
        if parsed == variant and reveal_t is not None and reveal_t < t_last:
            inference = INFERENCE_MAX
        elif parsed == variant:
            notes.append("declare matched the truth but preceded any revealing "
                         "inspection — no inference credit (lucky guess).")
        else:
            notes.append(f"declared {parsed or 'unparseable'!r}, truth was {variant!r}.")
    else:
        first_iv = _first_intervention_time(ep)
        if reveal_t is not None and (first_iv is None or reveal_t < first_iv):
            inference = IMPLICIT_INFERENCE
            notes.append("no declaration; partial credit for inspect-before-intervene.")
        else:
            notes.append("no declaration and no revealing inspection before intervening.")

    # --- intervention (35) — backend state only -----------------------------
    intervention = 0.0
    placed = backend.object_region("leftovers") == "fridge_shelf"
    if placed:
        intervention += INTERVENTION_PLACE
    else:
        notes.append(f"leftovers ended in '{backend.object_region('leftovers')}', "
                     "not on the fridge shelf.")
    trash = backend.objects_in("trash")
    fresh_discarded = [o for o in trash if o != "expired_milk"]
    if variant == "fridge_full":
        side_ok = "expired_milk" in trash and not fresh_discarded
        if not side_ok:
            notes.append(f"trash should hold exactly the expired milk; holds {trash}.")
    else:
        side_ok = trash == []
    if side_ok:
        intervention += INTERVENTION_SIDE
    if fresh_discarded:
        intervention -= FRESH_DISCARD_PENALTY * len(fresh_discarded)
        notes.append(f"fresh food discarded ({fresh_discarded}): "
                     f"-{FRESH_DISCARD_PENALTY} each.")
    tidy = all(not backend.door_open(f) for f in ("fridge", "microwave", "cabinet"))
    if tidy:
        intervention += INTERVENTION_TIDY
    else:
        notes.append("appliance door(s) left open.")
    if not ep.done:
        notes.append("episode hit the action cap without 'done'.")

    # --- parsimony (25) -----------------------------------------------------
    n = len(ep.events)
    expert = EXPERT_ACTIONS[variant]
    if n <= expert:
        parsimony = float(PARSIMONY_MAX)
    else:
        # linear: full credit at expert count, zero at 2x, negative beyond
        parsimony = PARSIMONY_MAX * (1.0 - (n - expert) / expert)
    if parsimony > 0 and not placed:
        notes.append("parsimony credit withheld: primary intervention not achieved.")
        parsimony = 0.0
    parsimony = round(parsimony, 1)
    if parsimony < 0:
        notes.append(f"action-count overrun ({n} vs expert {expert}) debits the total.")

    return Grade(inference, parsimony, intervention, notes)
