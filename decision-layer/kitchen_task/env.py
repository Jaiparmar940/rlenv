"""Decision-layer environment: text observations in, discrete actions out.

The agent under test is a reasoning model choosing among discrete primitives.
Execution is ORACLE by design: a valid primitive succeeds perfectly, realized
by setting simulator state through the backend. What is being evaluated is
the decision sequence — inspect, infer, intervene — not motor control.

Reveal rule (the information boundary): a fixture's interior appears in the
observation ONLY while its door is open. Hidden state reaches the agent
through no other channel.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .backends.base import FIXTURES, FIXTURE_REGION
from .task import (
    FRIDGE_CAPACITY,
    OBJECT_LABELS,
    TASK_INSTRUCTION,
    Scenario,
    parse_diagnosis,
)

MAX_ACTIONS = 30

HELP = (
    "Actions: open <fridge|microwave|cabinet> | close <fridge|microwave|cabinet> | "
    "pick <object> | place <object> <counter|fridge|microwave|cabinet> | "
    "discard <object> | declare <short phrase> | done"
)


@dataclass
class Event:
    t: int
    raw: str
    kind: str          # open/close/pick/place/discard/declare/done/invalid
    ok: bool
    detail: str = ""


@dataclass
class Episode:
    scenario: Scenario
    events: list[Event] = field(default_factory=list)
    declares: list[tuple[int, str, str | None]] = field(default_factory=list)  # (t, text, parsed)
    fridge_first_opened: int | None = None
    microwave_first_opened: int | None = None
    done: bool = False


class KitchenEnv:
    def __init__(self, backend, scenario: Scenario):
        self.backend = backend
        self.scenario = scenario
        self.ep = Episode(scenario=scenario)
        self.holding: str | None = None
        self._t = 0
        backend.reset(scenario.object_regions, scenario.seed)

    # ------------------------------------------------------------------ obs
    def observation(self, last_result: str = "") -> str:
        b = self.backend
        lines = [f"TASK: {TASK_INSTRUCTION}", HELP, ""]
        counter = [OBJECT_LABELS[o] for o in b.objects_in("counter")]
        lines.append(f"Counter: {', '.join(counter) if counter else 'empty'}.")
        for f in FIXTURES:
            if b.door_open(f):
                inside = [OBJECT_LABELS[o] for o in b.objects_in(FIXTURE_REGION[f])]
                desc = f"open — inside: {', '.join(inside) if inside else 'empty'}"
                if f == "fridge":
                    desc += f" ({len(b.objects_in('fridge_shelf'))}/{FRIDGE_CAPACITY} shelf slots used)"
            else:
                desc = "closed"
                if f == "microwave" and self.scenario.microwave_blinking:
                    desc += " (its clock display is blinking)"
            lines.append(f"{f.capitalize()}: {desc}.")
        lines.append(f"Holding: {OBJECT_LABELS[self.holding] if self.holding else 'nothing'}.")
        if last_result:
            lines.append(f"Result of last action: {last_result}")
        return "\n".join(lines)

    # ----------------------------------------------------------------- step
    def step(self, raw: str) -> tuple[str, bool]:
        """Apply one action string. Returns (observation, episode_over)."""
        self._t += 1
        raw = raw.strip()
        words = raw.lower().split()
        kind, ok, result = "invalid", False, f"Could not parse that action. {HELP}"

        if words:
            verb = words[0]
            if verb == "done":
                kind, ok, result = "done", True, "You step back from the counter."
                self.ep.done = True
            elif verb == "declare":
                text = raw[len("declare"):].strip()
                parsed = parse_diagnosis(text)
                self.ep.declares.append((self._t, text, parsed))
                kind, ok, result = "declare", True, f"Noted: {text!r}"
            elif verb in ("open", "close") and len(words) == 2 and words[1] in FIXTURES:
                f = words[1]
                want_open = verb == "open"
                if self.backend.door_open(f) == want_open:
                    kind, ok, result = verb, False, f"The {f} is already {verb}{'ed' if verb=='close' else ''}."
                    result = f"The {f} is already {'open' if want_open else 'closed'}."
                else:
                    self.backend.set_door(f, want_open)
                    if want_open and f == "fridge" and self.ep.fridge_first_opened is None:
                        self.ep.fridge_first_opened = self._t
                    if want_open and f == "microwave" and self.ep.microwave_first_opened is None:
                        self.ep.microwave_first_opened = self._t
                    kind, ok, result = verb, True, f"The {f} is now {'open' if want_open else 'closed'}."
            elif verb == "pick" and len(words) >= 2:
                kind, ok, result = self._pick("_".join(words[1:]))
            elif verb == "place" and len(words) >= 3:
                kind, ok, result = self._place("_".join(words[1:-1]), words[-1])
            elif verb == "discard" and len(words) >= 2:
                kind, ok, result = self._discard("_".join(words[1:]))

        self.ep.events.append(Event(self._t, raw, kind, ok, result))
        over = self.ep.done or self._t >= MAX_ACTIONS
        return self.observation(last_result=result), over

    # ------------------------------------------------------------- verbs
    def _resolve(self, name: str) -> str | None:
        name = name.replace("-", "_")
        for obj in OBJECT_LABELS:
            if obj == name or name in obj or obj in name:
                return obj
        aliases = {"milk": "expired_milk", "container": "leftovers", "juice": "juice_bottle", "butter": "butter_dish"}
        for k, v in aliases.items():
            if k in name:
                return v
        return None

    def _reachable(self, obj: str) -> bool:
        region = self.backend.object_region(obj)
        if region == "counter":
            return True
        for f, r in FIXTURE_REGION.items():
            if region == r:
                return self.backend.door_open(f)
        return False

    def _pick(self, name: str) -> tuple[str, bool, str]:
        obj = self._resolve(name)
        if obj is None:
            return "pick", False, f"You don't see any '{name}' you can reach."
        if self.holding:
            return "pick", False, f"Your hands are full (holding the {OBJECT_LABELS[self.holding]})."
        if self.backend.object_region(obj) == "trash":
            return "pick", False, "It's in the trash; leave it there."
        if not self._reachable(obj):
            return "pick", False, f"You don't see any '{name}' you can reach."
        self.backend.move_object(obj, "held")
        self.holding = obj
        return "pick", True, f"You are holding the {OBJECT_LABELS[obj]}."

    def _place(self, name: str, target: str) -> tuple[str, bool, str]:
        obj = self._resolve(name)
        if obj is None or obj != self.holding:
            return "place", False, "You need to pick an object up before placing it."
        if target == "counter":
            region = "counter"
        elif target in FIXTURE_REGION:
            if not self.backend.door_open(target):
                return "place", False, f"The {target} is closed."
            region = FIXTURE_REGION[target]
            if target == "fridge" and len(self.backend.objects_in("fridge_shelf")) >= FRIDGE_CAPACITY:
                return "place", False, "There is no room on the fridge shelf."
        elif target == "trash":
            return "place", False, "Use 'discard <object>' for the trash."
        else:
            return "place", False, f"Unknown place target '{target}'."
        self.backend.move_object(obj, region)
        self.holding = None
        return "place", True, f"The {OBJECT_LABELS[obj]} is now in/on the {target}."

    def _discard(self, name: str) -> tuple[str, bool, str]:
        obj = self._resolve(name)
        if obj is None or obj != self.holding:
            return "discard", False, "You need to be holding an object to discard it."
        self.backend.move_object(obj, "trash")
        self.holding = None
        return "discard", True, f"The {OBJECT_LABELS[obj]} is in the trash."
