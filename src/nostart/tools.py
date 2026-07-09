"""Agent-facing tool API — thin wrapper over World with stable signatures."""

from __future__ import annotations

from typing import Any

from nostart.world import EpisodeStatus, World


class ToolSession:
    """One episode's tool bindings. Create per scenario."""

    def __init__(self, scenario_id: str) -> None:
        self._world = World(scenario_id)

    @property
    def world(self) -> World:
        """Internal access for grader/tests (not agent-facing)."""
        return self._world

    def get_complaint(self) -> str:
        return self._world.public_snapshot().complaint

    def get_status(self) -> EpisodeStatus:
        return self._world.public_snapshot()

    def scan_dtcs(self) -> list[dict[str, str]]:
        return self._world.scan_dtcs()

    def read_pid(self, pid: str) -> dict[str, Any]:
        return self._world.read_pid(pid)

    def measure_voltage(
        self, point_a: str, point_b: str, engine_state: str
    ) -> dict[str, Any]:
        return self._world.measure_voltage(point_a, point_b, engine_state)

    def visual_inspect(self, area: str) -> str:
        return self._world.visual_inspect(area)

    def replace_part(self, component: str) -> dict[str, bool]:
        return self._world.replace_part(component)

    def attempt_start(self) -> dict[str, str]:
        return self._world.attempt_start()

    def finish(self, diagnosis: str) -> EpisodeStatus:
        return self._world.finish(diagnosis)


def make_tools(scenario_id: str) -> ToolSession:
    return ToolSession(scenario_id)
