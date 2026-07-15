"""Time and money cost model per agent action.

Costs are deterministic constants; cumulative totals live in world state.
"""

from __future__ import annotations

from typing import Literal

ActionName = Literal[
    "scan_dtcs",
    "read_pid",
    "measure_voltage",
    "visual_inspect",
    "replace_part",
    "attempt_start",
    "finish",
]

# Measurement / diagnostic actions — time only.
ACTION_COSTS: dict[str, dict[str, float]] = {
    "scan_dtcs": {"minutes": 2.0, "dollars": 0.0},
    "read_pid": {"minutes": 1.0, "dollars": 0.0},
    "measure_voltage": {"minutes": 3.0, "dollars": 0.0},
    "visual_inspect": {"minutes": 5.0, "dollars": 0.0},
    "attempt_start": {"minutes": 1.0, "dollars": 0.0},
    "finish": {"minutes": 0.0, "dollars": 0.0},
}

# Part replacement prices — real-world-ish list prices.
PART_PRICES: dict[str, float] = {
    "battery": 180.0,
    "ground_strap": 25.0,
    "starter_relay": 45.0,
    "starter_motor": 280.0,
    "alternator": 350.0,
    "fusible_link": 15.0,
    "ignition_switch": 120.0,
    "ecu_can_node": 450.0,
}

REPLACE_LABOR_MINUTES = 20.0  # flat labor per replacement


def cost_for_action(action: ActionName, *, component: str | None = None) -> dict[str, float]:
    """Return {minutes, dollars} for an action."""
    base = dict(ACTION_COSTS.get(action, {"minutes": 0.0, "dollars": 0.0}))
    if action == "replace_part" and component:
        key = component.strip().lower().replace("-", "_").replace(" ", "_")
        part_price = PART_PRICES.get(key, 100.0)  # fallback price
        base["dollars"] += part_price
        base["minutes"] += REPLACE_LABOR_MINUTES
    return base
