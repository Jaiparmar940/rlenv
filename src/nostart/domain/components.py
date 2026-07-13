"""Component graph and failure-mode definitions.

Ground-truth vocabulary lives here; nothing in this module is ever serialized
to agent-facing observations or tool outputs.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Component(str, Enum):
    BATTERY = "battery"
    GROUND_STRAP = "ground_strap"
    STARTER_RELAY = "starter_relay"
    STARTER_MOTOR = "starter_motor"
    ALTERNATOR = "alternator"
    FUSIBLE_LINK = "fusible_link"
    IGNITION_SWITCH = "ignition_switch"
    ECU_CAN_NODE = "ecu_can_node"


class FailureMode(str, Enum):
    # battery
    WEAK = "weak"
    DEAD = "dead"
    # ground_strap
    CORRODED = "corroded"
    BROKEN = "broken"
    # starter_relay
    STUCK_OPEN = "stuck_open"
    STUCK_CLOSED = "stuck_closed"
    # starter_motor
    WORN_BRUSHES = "worn_brushes"
    SEIZED = "seized"
    # alternator
    DIODE_FAILURE = "diode_failure"
    NO_OUTPUT = "no_output"
    # fusible_link
    BLOWN = "blown"
    HIGH_RESISTANCE = "high_resistance"
    # ignition_switch
    NO_CRANK_SIGNAL = "no_crank_signal"
    ACCESSORY_DROP = "accessory_drop"
    # ecu_can_node
    BUS_OFF = "bus_off"
    INTERMITTENT = "intermittent"


class InjectedFault(BaseModel):
    """A single injected fault with optional severity parameters."""

    component: Component
    mode: FailureMode
    severity: dict[str, float] = Field(default_factory=dict)


# Severity parameter defaults — every numeric value marked for domain review.
DEFAULT_SEVERITY: dict[tuple[Component, FailureMode], dict[str, float]] = {
    (Component.BATTERY, FailureMode.WEAK): {
        "cca_remaining_pct": 45.0,  # TODO(VERIFY): weak battery CCA %
        # How far the whole positive rail sits below nominal, in EVERY state
        # (low open-circuit voltage from a degraded battery). The nominal
        # cranking sag then applies on top of it, so a weak battery cranks
        # at (nominal crank − terminal_drop_v). Default preserves the
        # historical hard-coded −0.6 V; hard-tier scenarios raise it.
        "terminal_drop_v": 0.6,  # TODO(VERIFY): rail offset for a weak battery
    },
    (Component.BATTERY, FailureMode.DEAD): {
        "open_circuit_v": 2.1,  # TODO(VERIFY): terminal voltage when dead
    },
    (Component.GROUND_STRAP, FailureMode.CORRODED): {
        "added_resistance_ohms": 0.8,  # TODO(VERIFY): added ground path R
    },
    (Component.GROUND_STRAP, FailureMode.BROKEN): {
        "added_resistance_ohms": 50.0,  # TODO(VERIFY): open-circuit equivalent R
    },
    (Component.STARTER_RELAY, FailureMode.STUCK_OPEN): {},
    (Component.STARTER_RELAY, FailureMode.STUCK_CLOSED): {},
    (Component.STARTER_MOTOR, FailureMode.WORN_BRUSHES): {
        "crank_rpm_factor": 0.55,  # TODO(VERIFY): fraction of nominal crank RPM
    },
    (Component.STARTER_MOTOR, FailureMode.SEIZED): {},
    (Component.ALTERNATOR, FailureMode.DIODE_FAILURE): {
        "ac_ripple_v": 1.2,  # TODO(VERIFY): AC ripple on DC output
    },
    (Component.ALTERNATOR, FailureMode.NO_OUTPUT): {
        "output_v": 0.0,  # TODO(VERIFY): alternator output when failed
    },
    (Component.FUSIBLE_LINK, FailureMode.BLOWN): {},
    (Component.FUSIBLE_LINK, FailureMode.HIGH_RESISTANCE): {
        "added_resistance_ohms": 2.5,  # TODO(VERIFY): fusible link high-R
    },
    (Component.IGNITION_SWITCH, FailureMode.NO_CRANK_SIGNAL): {},
    (Component.IGNITION_SWITCH, FailureMode.ACCESSORY_DROP): {
        "voltage_drop_v": 2.5,  # TODO(VERIFY): accessory bus drop under load
    },
    (Component.ECU_CAN_NODE, FailureMode.BUS_OFF): {},
    (Component.ECU_CAN_NODE, FailureMode.INTERMITTENT): {
        "manifest_probability": 0.35,  # TODO(VERIFY): P(symptom on probe)
    },
}


COMPONENT_FAILURE_MODES: dict[Component, list[FailureMode]] = {
    Component.BATTERY: [FailureMode.WEAK, FailureMode.DEAD],
    Component.GROUND_STRAP: [FailureMode.CORRODED, FailureMode.BROKEN],
    Component.STARTER_RELAY: [FailureMode.STUCK_OPEN, FailureMode.STUCK_CLOSED],
    Component.STARTER_MOTOR: [FailureMode.WORN_BRUSHES, FailureMode.SEIZED],
    Component.ALTERNATOR: [FailureMode.DIODE_FAILURE, FailureMode.NO_OUTPUT],
    Component.FUSIBLE_LINK: [FailureMode.BLOWN, FailureMode.HIGH_RESISTANCE],
    Component.IGNITION_SWITCH: [FailureMode.NO_CRANK_SIGNAL, FailureMode.ACCESSORY_DROP],
    Component.ECU_CAN_NODE: [FailureMode.BUS_OFF, FailureMode.INTERMITTENT],
}


def merge_severity(fault: InjectedFault) -> dict[str, float]:
    """Return severity dict with defaults filled in for the fault mode."""
    defaults = DEFAULT_SEVERITY.get((fault.component, fault.mode), {})
    merged: dict[str, float] = dict(defaults)
    merged.update(fault.severity)
    return merged


def normalize_component(name: str) -> Component | None:
    """Fuzzy-match a user/component string to a Component enum."""
    key = name.strip().lower().replace("-", "_").replace(" ", "_")
    aliases: dict[str, Component] = {
        "bat": Component.BATTERY,
        "ground": Component.GROUND_STRAP,
        "ground_cable": Component.GROUND_STRAP,
        "relay": Component.STARTER_RELAY,
        "starter": Component.STARTER_MOTOR,
        "starter_solenoid": Component.STARTER_RELAY,
        "alt": Component.ALTERNATOR,
        "fuse": Component.FUSIBLE_LINK,
        "fusible": Component.FUSIBLE_LINK,
        "ignition": Component.IGNITION_SWITCH,
        "switch": Component.IGNITION_SWITCH,
        "ecu": Component.ECU_CAN_NODE,
        "can": Component.ECU_CAN_NODE,
    }
    if key in aliases:
        return aliases[key]
    try:
        return Component(key)
    except ValueError:
        return None


def fault_key(component: Component, mode: FailureMode) -> str:
    return f"{component.value}:{mode.value}"
