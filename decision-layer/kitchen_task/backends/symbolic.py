"""Pure-Python backend: a kitchen state model with no simulator.

Exists for two reasons: (1) the decision layer must be testable without a
sim install, (2) it is the documented last-resort substrate under the pivot
rule. Identical interface, identical episode semantics.
"""

from __future__ import annotations

from .base import FIXTURES, REGIONS


class SymbolicBackend:
    name = "symbolic"

    def reset(self, object_regions: dict[str, str], seed: int) -> None:
        self._regions = dict(object_regions)
        self._doors = {f: False for f in FIXTURES}

    def set_door(self, fixture: str, open_: bool) -> None:
        self._doors[fixture] = open_

    def move_object(self, obj: str, region: str) -> None:
        assert region in REGIONS or region == "held", region
        self._regions[obj] = region

    def door_open(self, fixture: str) -> bool:
        return self._doors[fixture]

    def object_region(self, obj: str) -> str:
        return self._regions[obj]

    def objects_in(self, region: str) -> list[str]:
        return sorted(o for o, r in self._regions.items() if r == region)

    def render(self):
        return None
