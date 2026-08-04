"""Backend protocol: the only surface the task/env/grader may touch.

The decision layer (task logic, observation builder, grader) is substrate-
agnostic. A backend owns the world state and answers queries about it.
Crucially, the GRADER asks the backend where things are — it never trusts
the env's bookkeeping or the agent's claims. In the simulator backend those
answers are computed from geometry (object poses vs. region bounding boxes,
door joint positions); in the symbolic backend they come from its state dict.
"""

from __future__ import annotations

from typing import Protocol

# Shared vocabulary — every backend must realize these.
FIXTURES = ("fridge", "microwave", "cabinet")
REGIONS = ("counter", "fridge_shelf", "microwave_interior", "cabinet_shelf", "trash")
# region an object lands in when placed "in" a fixture
FIXTURE_REGION = {
    "fridge": "fridge_shelf",
    "microwave": "microwave_interior",
    "cabinet": "cabinet_shelf",
}


class Backend(Protocol):
    """World substrate. All mutation is oracle: state is set directly."""

    name: str

    def reset(self, object_regions: dict[str, str], seed: int) -> None:
        """Load the scene and place each object in its region."""

    # --- oracle mutations (called by the env after validity checks) ---
    def set_door(self, fixture: str, open_: bool) -> None: ...

    def move_object(self, obj: str, region: str) -> None:
        """Teleport obj into region ('held' is a valid pseudo-region)."""

    # --- queries (called by env for observations AND by grader for truth) ---
    def door_open(self, fixture: str) -> bool: ...

    def object_region(self, obj: str) -> str:
        """Where is obj, according to the substrate's own state?"""

    def objects_in(self, region: str) -> list[str]: ...

    def render(self):  # -> np.ndarray | None
        """RGB frame for the recording, or None if headless."""
