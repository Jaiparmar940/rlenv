"""Vehicle state machine: applies faults, answers probes, tracks episode state.

Ground-truth fault state is held in private fields and never included in
``public_snapshot()`` or any tool return value.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr

from nostart.costs import cost_for_action
from nostart.domain.components import Component, InjectedFault, merge_severity, normalize_component
from nostart.domain.propagation import (
    IDLE_RPM,
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
        "weak": "Terminal corrosion light; case looks aged.",
        "dead": "Terminals corroded; slight sulfation odor.",
    },
    "ground_strap": {
        "healthy": "Engine-to-chassis strap intact, bolt tight.",
        "corroded": "Strap end greenish; could be overlooked.",  # subtle
        "broken": "Strap frayed at engine block attachment.",
    },
    "starter_relay": {
        "healthy": "Relay clicks once on crank attempt.",
        "stuck_open": "No click heard at relay.",
        "stuck_closed": "Click persists after key release.",
    },
    "starter_motor": {
        "healthy": "No unusual noise during crank.",
        "worn_brushes": "Grinding noise during slow crank.",
        "seized": "Loud clunk, no rotation.",
    },
    "alternator": {
        "healthy": "Belt intact, no burnt smell.",
        "diode_failure": "Faint whine from alternator area.",
        "no_output": "Belt intact; connector looks seated.",
    },
    "fusible_link": {
        "healthy": "Link intact at battery positive junction.",
        "blown": "Link appears melted at mid-span.",
        "high_resistance": "Link discolored but not open.",
    },
    "ignition_switch": {
        "healthy": "Key cycles smoothly through positions.",
        "no_crank_signal": "Dash lights flicker in START.",
        "accessory_drop": "Lights dim sharply in START.",
    },
    "ecu_can_node": {
        "healthy": "OBD connector pins clean.",
        "bus_off": "MIL on; scan tool connection intermittent.",
        "intermittent": "No obvious wiring damage at ECM.",
    },
}


class World:
    """Mutable episode state. Instantiate per scenario + seed."""

    def __init__(self, scenario_id: str) -> None:
        self._scenario: ScenarioDef = get_scenario(scenario_id)
        self._rng = random.Random(self._scenario.seed)
        self._root_cause: InjectedFault = self._scenario.root_cause.model_copy(deep=True)
        # Compound scenarios inject a second, genuinely-faulty component
        # alongside the root cause (see ScenarioDef.secondary_fault).
        self._secondary_fault: InjectedFault | None = (
            self._scenario.secondary_fault.model_copy(deep=True)
            if self._scenario.secondary_fault is not None
            else None
        )
        self._active_faults: list[InjectedFault] = [self._root_cause.model_copy(deep=True)]
        if self._secondary_fault is not None:
            self._active_faults.append(self._secondary_fault.model_copy(deep=True))
        self._replaced_components: set[Component] = set()
        # Per-probe-kind counters for intermittent faults. Manifestation is a
        # pure function of (scenario seed, probe kind, index) — see
        # _intermittent_manifests — so the k-th crank always behaves the same
        # way no matter what else the agent did in between.
        self._intermittency_counters: dict[str, int] = {}
        self._cumulative_cost = CumulativeCost()
        self._finished = False
        self._diagnosis: str | None = None
        self._action_count = 0
        self._probe_count = 0  # all probes (any time)
        # Probes taken BEFORE the first replacement. The guessing cap keys on
        # this: a blind part-swap whose verify crank is its only "probe" is
        # still guessing — diagnosis must precede repair.
        self._diagnostic_probe_count = 0
        self._crank_attempts = 0
        # True once attempt_start returns "starts" with no replacement after it.
        # Grader combines this with root-component-replaced to require a
        # verified fix (resolution penalty otherwise).
        self._fix_verified = False
        # The engine keeps running after a successful start until something
        # implies shutting it off (working on the car, or measuring in a
        # non-running key state). Gates the "running" engine_state and what
        # the scan tool (read_pid) reflects.
        self._engine_running = False

    # --- Ground truth accessors (tool layer only, never serialized) ---

    @property
    def root_cause(self) -> InjectedFault:
        return self._root_cause

    @property
    def secondary_fault(self) -> InjectedFault | None:
        """The co-fault in a compound scenario (None otherwise)."""
        return self._secondary_fault

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
    def diagnostic_probe_count(self) -> int:
        """Probes taken before any part was replaced."""
        return self._diagnostic_probe_count

    def _note_probe(self) -> None:
        self._probe_count += 1
        if not self._replaced_components:
            self._diagnostic_probe_count += 1

    @property
    def fix_verified(self) -> bool:
        """A start attempt succeeded after the most recent replacement."""
        return self._fix_verified

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
        """Does an intermittent fault show itself on THIS probe?

        Deterministic by construction: the roll is a hash of
        (scenario seed, probe kind, index-of-this-probe-kind) — no wall clock,
        and deliberately NOT drawn from ``self._rng``, whose stream is also
        consumed by meter noise and visual inspection. Two consequences that
        the tests pin:

          * identical runs produce identical observations, and
          * the k-th ``attempt_start`` gives the same answer regardless of how
            many other actions were interleaved before it.
        """
        if intermittency >= 1.0:
            return True
        index = self._intermittency_counters.get(probe_tag, 0)
        self._intermittency_counters[probe_tag] = index + 1
        payload = f"{self._scenario.seed}|{probe_tag}|{index}".encode()
        digest = hashlib.blake2b(payload, digest_size=8).digest()
        roll = int.from_bytes(digest, "big") / 2**64
        return roll < intermittency

    def _noise_band(self, value: float, band: float) -> float:
        """Apply seeded ±band noise to a reading."""
        delta = self._rng.uniform(-band, band)
        return round(value + delta, 2)

    VOLTAGE_NOISE_BAND = 0.05  # ±0.05 V meter noise

    def _get_active_fault_for_component(self, component: Component) -> InjectedFault | None:
        for f in self._active_faults:
            if f.component == component:
                return f
        return None

    # --- Tool implementations ---

    def scan_dtcs(self) -> list[dict[str, str]]:
        self._charge_action("scan_dtcs")
        self._note_probe()
        symptoms = self._resolve(EngineState.KEY_ON)
        if not self._intermittent_manifests(symptoms.intermittency, "scan_dtcs"):
            return []
        codes = symptoms.dtcs
        return [{"code": c, "description": dtc_description(c)} for c in codes]

    def read_pid(self, pid: str) -> dict[str, Any]:
        self._charge_action("read_pid")
        self._note_probe()
        key = pid.strip().lower()
        # The scan tool is passive: it reflects the vehicle's CURRENT state.
        # After a successful start the engine is running and PIDs show
        # charging-system values, not key-on ones. Every payload names the
        # state it was read in — instrument metadata, so an engine-off
        # alt_output_v (rail voltage) cannot masquerade as a failed
        # alternator at idle.
        state = EngineState.RUNNING if self._engine_running else EngineState.KEY_ON
        symptoms = self._resolve(state)
        es = state.value

        if key == "battery_voltage":
            v = symptoms.potential_difference("battery_positive", "battery_negative")
            return {"pid": "battery_voltage", "value": self._noise_band(v, 0.05),
                    "unit": "V", "engine_state": es}
        if key == "alt_output_v":
            v = symptoms.potential_difference("alt_output", "battery_negative")
            # Add AC ripple component for diode failure (realistic scope reading avg).
            for f in self._active_faults:
                if f.component == Component.ALTERNATOR and f.mode.value == "diode_failure":
                    sev = merge_severity(f)
                    v -= sev.get("ac_ripple_v", 0.0) * 0.1  # PID shows depressed avg
            return {"pid": "alt_output_v", "value": self._noise_band(v, 0.08),
                    "unit": "V", "engine_state": es}
        if key == "rpm":
            # A live tach read: 0 with the engine off, idle while running.
            # (Crank speed is not observable here — attempt_start reports
            # slow_crank directly, which carries the same information.)
            if self._engine_running:
                value = self._noise_band(IDLE_RPM, 5.0)
            else:
                value = 0.0
            return {"pid": "rpm", "value": value, "unit": "rpm", "engine_state": es}
        if key == "can_status":
            status = symptoms.can_status.value
            if not self._intermittent_manifests(symptoms.intermittency, f"can_{pid}"):
                status = CanStatus.OK.value
            return {"pid": "can_status", "value": status, "unit": "enum",
                    "engine_state": es}

        return {"pid": key, "value": None, "unit": "unknown", "engine_state": es}

    def measure_voltage(
        self, point_a: str, point_b: str, engine_state: str
    ) -> dict[str, Any]:
        """Two-point measurement: V(point_a) − V(point_b) at engine_state.

        Raises ValueError on an unknown node name or engine state.
        """
        self._charge_action("measure_voltage")
        self._note_probe()
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

        if es == EngineState.RUNNING and not self._engine_running:
            raise ValueError(
                "Engine is not running. A successful attempt_start() is "
                "required before measuring in the 'running' state."
            )
        if es != EngineState.RUNNING:
            # Putting the key in any other position shuts a running engine
            # off; it must be restarted before further running measurements.
            self._engine_running = False

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
        self._note_probe()
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
            if self._rng.random() > 0.4:  # 40% chance to spot
                return "Strap looks normal at a glance."
        return notes.get(mode_key, notes.get("healthy", "No obvious defects."))

    def replace_part(self, component: str) -> dict[str, bool]:
        comp = normalize_component(component)
        if comp is None:
            self._charge_action("replace_part", component=component)
            return {"installed": False}

        self._charge_action("replace_part", component=comp.value)
        self._replaced_components.add(comp)
        self._fix_verified = False  # any new install must be re-verified
        self._engine_running = False  # engine off to work on the car
        # Remove fault for this component (known-good part installed).
        self._active_faults = [f for f in self._active_faults if f.component != comp]
        return {"installed": True}

    def attempt_start(self) -> dict[str, str]:
        self._charge_action("attempt_start")
        self._note_probe()
        self._crank_attempts += 1
        symptoms = self._resolve(EngineState.CRANKING)
        if not self._intermittent_manifests(symptoms.intermittency, "attempt_start"):
            symptoms = resolve_symptoms([], EngineState.CRANKING)
        started = symptoms.crank_behavior == CrankBehavior.STARTS
        if started:
            self._fix_verified = True
        self._engine_running = started
        return {"result": symptoms.crank_behavior.value}

    def finish(self, diagnosis: str) -> EpisodeStatus:
        self._charge_action("finish")
        self._finished = True
        self._diagnosis = diagnosis.strip()
        return self.public_snapshot()
