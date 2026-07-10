"""Vehicle state machine: applies faults, answers probes, tracks episode state.

Ground-truth fault state is held in private fields and never included in
``public_snapshot()`` or any tool return value.
"""

from __future__ import annotations

import random
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr

from nostart.costs import cost_for_action
from nostart.domain.components import Component, InjectedFault, merge_severity, normalize_component
from nostart.domain.propagation import (
    VALID_NODES,
    CanStatus,
    CrankBehavior,
    EngineState,
    SymptomState,
    dtc_description,
    resolve_symptoms,
)
from nostart.domain.scenarios import ScenarioDef, get_scenario


class CumulativeCost(BaseModel):
    minutes: float = 0.0
    dollars: float = 0.0


class EpisodeStatus(BaseModel):
    """Agent-visible episode metadata (no ground truth)."""

    scenario_id: str
    complaint: str
    cumulative_cost: CumulativeCost
    finished: bool = False
    diagnosis: str | None = None
    action_count: int = 0


# Visual inspection notes — terse tech observations, may miss subtle faults.
VISUAL_NOTES: dict[str, dict[str, str]] = {
    "battery": {
        "healthy": "Terminals clean, no swelling, date code legible.",
        "weak": "Terminal corrosion light; case looks aged.",  # TODO(VERIFY)
        "dead": "Terminals corroded; slight sulfation odor.",  # TODO(VERIFY)
    },
    "ground_strap": {
        "healthy": "Engine-to-chassis strap intact, bolt tight.",
        "corroded": "Strap end greenish; could be overlooked.",  # TODO(VERIFY): subtle
        "broken": "Strap frayed at engine block attachment.",  # TODO(VERIFY)
    },
    "starter_relay": {
        "healthy": "Relay clicks once on crank attempt.",
        "stuck_open": "No click heard at relay.",  # TODO(VERIFY)
        "stuck_closed": "Click persists after key release.",  # TODO(VERIFY)
    },
    "starter_motor": {
        "healthy": "No unusual noise during crank.",
        "worn_brushes": "Grinding noise during slow crank.",  # TODO(VERIFY)
        "seized": "Loud clunk, no rotation.",  # TODO(VERIFY)
    },
    "alternator": {
        "healthy": "Belt intact, no burnt smell.",
        "diode_failure": "Faint whine from alternator area.",  # TODO(VERIFY)
        "no_output": "Belt intact; connector looks seated.",  # TODO(VERIFY)
    },
    "fusible_link": {
        "healthy": "Link intact at battery positive junction.",
        "blown": "Link appears melted at mid-span.",  # TODO(VERIFY)
        "high_resistance": "Link discolored but not open.",  # TODO(VERIFY)
    },
    "ignition_switch": {
        "healthy": "Key cycles smoothly through positions.",
        "no_crank_signal": "Dash lights flicker in START.",  # TODO(VERIFY)
        "accessory_drop": "Lights dim sharply in START.",  # TODO(VERIFY)
    },
    "ecu_can_node": {
        "healthy": "OBD connector pins clean.",
        "bus_off": "MIL on; scan tool connection intermittent.",  # TODO(VERIFY)
        "intermittent": "No obvious wiring damage at ECM.",  # TODO(VERIFY)
    },
}


class World:
    """Mutable episode state. Instantiate per scenario + seed."""

    def __init__(self, scenario_id: str) -> None:
        self._scenario: ScenarioDef = get_scenario(scenario_id)
        self._rng = random.Random(self._scenario.seed)
        self._root_cause: InjectedFault = self._scenario.root_cause.model_copy(deep=True)
        self._active_faults: list[InjectedFault] = [self._root_cause.model_copy(deep=True)]
        self._replaced_components: set[Component] = set()
        self._cumulative_cost = CumulativeCost()
        self._finished = False
        self._diagnosis: str | None = None
        self._action_count = 0
        self._probe_count = 0  # measurements for guessing penalty (grader phase 2)
        self._crank_attempts = 0

    # --- Ground truth accessors (tool layer only, never serialized) ---

    @property
    def root_cause(self) -> InjectedFault:
        return self._root_cause

    @property
    def active_faults(self) -> list[InjectedFault]:
        return list(self._active_faults)

    @property
    def replaced_components(self) -> set[Component]:
        return set(self._replaced_components)

    @property
    def probe_count(self) -> int:
        return self._probe_count

    @property
    def scenario(self) -> ScenarioDef:
        return self._scenario

    # --- Agent-visible state ---

    def public_snapshot(self) -> EpisodeStatus:
        return EpisodeStatus(
            scenario_id=self._scenario.id,
            complaint=self._scenario.complaint,
            cumulative_cost=self._cumulative_cost.model_copy(deep=True),
            finished=self._finished,
            diagnosis=self._diagnosis,
            action_count=self._action_count,
        )

    def _charge_action(self, action: str, *, component: str | None = None) -> None:
        cost = cost_for_action(action, component=component)  # type: ignore[arg-type]
        self._cumulative_cost.minutes += cost["minutes"]
        self._cumulative_cost.dollars += cost["dollars"]
        self._action_count += 1

    def _resolve(self, engine_state: EngineState) -> SymptomState:
        herring = self._scenario.red_herring_voltages or None
        if (
            herring is not None
            and self._scenario.red_herring_component in self._replaced_components
        ):
            # The marginal resting readings belong to the original component;
            # a known-good replacement reads nominal at rest.
            herring = None
        return resolve_symptoms(
            self._active_faults,
            engine_state,
            red_herring_readings=herring,
        )

    def _intermittent_manifests(self, intermittency: float, probe_tag: str) -> bool:
        if intermittency >= 1.0:
            return True
        roll = self._rng.random()
        return roll < intermittency

    def _noise_band(self, value: float, band: float) -> float:
        """Apply seeded ±band noise to a reading."""
        delta = self._rng.uniform(-band, band)
        return round(value + delta, 2)

    VOLTAGE_NOISE_BAND = 0.05  # TODO(VERIFY): ±0.05 V meter noise

    def _get_active_fault_for_component(self, component: Component) -> InjectedFault | None:
        for f in self._active_faults:
            if f.component == component:
                return f
        return None

    # --- Tool implementations ---

    def scan_dtcs(self) -> list[dict[str, str]]:
        self._charge_action("scan_dtcs")
        self._probe_count += 1
        symptoms = self._resolve(EngineState.KEY_ON)
        if not self._intermittent_manifests(symptoms.intermittency, "scan_dtcs"):
            return []
        codes = symptoms.dtcs
        return [{"code": c, "description": dtc_description(c)} for c in codes]

    def read_pid(self, pid: str) -> dict[str, Any]:
        self._charge_action("read_pid")
        self._probe_count += 1
        key = pid.strip().lower()
        symptoms = self._resolve(EngineState.KEY_ON)

        if key == "battery_voltage":
            v = symptoms.potential_difference("battery_positive", "battery_negative")
            return {"pid": "battery_voltage", "value": self._noise_band(v, 0.05), "unit": "V"}
        if key == "alt_output_v":
            v = symptoms.potential_difference("alt_output", "battery_negative")
            # Add AC ripple component for diode failure (realistic scope reading avg).
            for f in self._active_faults:
                if f.component == Component.ALTERNATOR and f.mode.value == "diode_failure":
                    sev = merge_severity(f)
                    v -= sev.get("ac_ripple_v", 0.0) * 0.1  # TODO(VERIFY): PID shows depressed avg
            return {"pid": "alt_output_v", "value": self._noise_band(v, 0.08), "unit": "V"}
        if key == "rpm":
            rpm = 0.0
            if symptoms.crank_behavior == CrankBehavior.SLOW_CRANK:
                rpm = 95.0  # TODO(VERIFY): slow crank RPM
            elif symptoms.crank_behavior in (
                CrankBehavior.CRANK_NO_START,
                CrankBehavior.STARTS,
            ):
                rpm = 180.0  # TODO(VERIFY): normal crank RPM
            return {"pid": "rpm", "value": self._noise_band(rpm, 5.0), "unit": "rpm"}
        if key == "can_status":
            status = symptoms.can_status.value
            if not self._intermittent_manifests(symptoms.intermittency, f"can_{pid}"):
                status = CanStatus.OK.value
            return {"pid": "can_status", "value": status, "unit": "enum"}

        return {"pid": key, "value": None, "unit": "unknown"}

    def measure_voltage(
        self, point_a: str, point_b: str, engine_state: str
    ) -> dict[str, Any]:
        """Two-point measurement: V(point_a) − V(point_b) at engine_state.

        Raises ValueError on an unknown node name or engine state.
        """
        self._charge_action("measure_voltage")
        self._probe_count += 1
        a = point_a.strip().lower()
        b = point_b.strip().lower()
        for node in (a, b):
            if node not in VALID_NODES:
                raise ValueError(
                    f"Unknown node '{node}'. Valid nodes: {sorted(VALID_NODES)}"
                )
        es_raw = engine_state.strip().lower()
        try:
            es = EngineState(es_raw)
        except ValueError:
            valid = [s.value for s in EngineState]
            raise ValueError(
                f"Unknown engine_state '{es_raw}'. Valid: {valid}"
            ) from None

        symptoms = self._resolve(es)
        if not self._intermittent_manifests(
            symptoms.intermittency, f"v_{a}_{b}_{es.value}"
        ):
            # Intermittent fault: return healthy reading for this probe.
            symptoms = resolve_symptoms([], es)

        volts = symptoms.potential_difference(a, b)
        return {
            "point_a": a,
            "point_b": b,
            "engine_state": es.value,
            "volts": self._noise_band(volts, self.VOLTAGE_NOISE_BAND),
        }

    def visual_inspect(self, area: str) -> str:
        self._charge_action("visual_inspect")
        self._probe_count += 1
        comp = normalize_component(area)
        if comp is None:
            return "Area not recognized; no useful observation."

        fault = self._get_active_fault_for_component(comp)
        notes = VISUAL_NOTES.get(comp.value, {})
        if fault is None or comp in self._replaced_components:
            return notes.get("healthy", "No obvious defects.")

        mode_key = fault.mode.value
        # Corroded ground may be missed (subtle fault).
        if comp == Component.GROUND_STRAP and fault.mode.value == "corroded":
            if self._rng.random() > 0.4:  # TODO(VERIFY): 40% chance to spot
                return "Strap looks normal at a glance."
        return notes.get(mode_key, notes.get("healthy", "No obvious defects."))

    def replace_part(self, component: str) -> dict[str, bool]:
        comp = normalize_component(component)
        if comp is None:
            self._charge_action("replace_part", component=component)
            return {"installed": False}

        self._charge_action("replace_part", component=comp.value)
        self._replaced_components.add(comp)
        # Remove fault for this component (known-good part installed).
        self._active_faults = [f for f in self._active_faults if f.component != comp]
        return {"installed": True}

    def attempt_start(self) -> dict[str, str]:
        self._charge_action("attempt_start")
        self._probe_count += 1
        self._crank_attempts += 1
        symptoms = self._resolve(EngineState.CRANKING)
        if not self._intermittent_manifests(symptoms.intermittency, "attempt_start"):
            symptoms = resolve_symptoms([], EngineState.CRANKING)
        return {"result": symptoms.crank_behavior.value}

    def finish(self, diagnosis: str) -> EpisodeStatus:
        self._charge_action("finish")
        self._finished = True
        self._diagnosis = diagnosis.strip()
        return self.public_snapshot()
