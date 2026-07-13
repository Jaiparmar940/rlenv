"""Fault → symptom causal propagation on a node-potential electrical model.

The system is modeled as NODES, each with a scalar potential (volts) relative
to the single reference node ``battery_negative`` = 0.000 V. Fault effects and
cranking load modify node potentials; every reading the agent takes is derived
as a potential difference between two nodes, so ANY pair is physically
consistent. The grader and world probe logic read this module; agents never see
its outputs directly.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from nostart.domain.components import (
    Component,
    FailureMode,
    InjectedFault,
    merge_severity,
)


class EngineState(str, Enum):
    KEY_OFF = "key_off"
    KEY_ON = "key_on"
    CRANKING = "cranking"
    # Engine running after a successful start: the alternator is the source
    # and the system sits at charging voltage. Only reachable through
    # World state (attempt_start must return "starts" first) — resting
    # invariants and red herrings do NOT apply here.
    RUNNING = "running"


class CrankBehavior(str, Enum):
    NO_CLICK = "no_click"
    CLICK_NO_CRANK = "click_no_crank"
    SLOW_CRANK = "slow_crank"
    CRANK_NO_START = "crank_no_start"
    STARTS = "starts"


class Node(str, Enum):
    BATTERY_POSITIVE = "battery_positive"
    BATTERY_NEGATIVE = "battery_negative"  # reference, always ~0 V
    ENGINE_BLOCK = "engine_block"          # engine / starter ground
    STARTER_STUD = "starter_stud"
    ALT_OUTPUT = "alt_output"
    CHASSIS = "chassis"


REFERENCE_NODE = Node.BATTERY_NEGATIVE.value
VALID_NODES: frozenset[str] = frozenset(n.value for n in Node)

# Positive-side supply rail: fed from the battery positive terminal. At rest,
# potential is monotonic non-increasing from source toward downstream nodes.
POSITIVE_RAIL: tuple[str, ...] = (
    Node.BATTERY_POSITIVE.value,
    Node.STARTER_STUD.value,
    Node.ALT_OUTPUT.value,
)
SUPPLY_SOURCE = Node.BATTERY_POSITIVE.value
DOWNSTREAM_OF_SOURCE: tuple[str, ...] = (
    Node.STARTER_STUD.value,
    Node.ALT_OUTPUT.value,
)
RESTING_SUPPLY_EDGES: tuple[tuple[str, str], ...] = (
    (Node.BATTERY_POSITIVE.value, Node.STARTER_STUD.value),
    (Node.BATTERY_POSITIVE.value, Node.ALT_OUTPUT.value),
)


class CanStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    BUS_OFF = "bus_off"


# Nominal healthy node potentials (V, relative to battery_negative). Cranking
# values bake in normal battery load sag. All values TODO(VERIFY).
NOMINAL_NODES: dict[EngineState, dict[str, float]] = {
    EngineState.KEY_OFF: {
        "battery_positive": 12.6,  # TODO(VERIFY)
        "battery_negative": 0.0,   # reference
        "engine_block": 0.0,       # TODO(VERIFY): healthy ground ~0
        "starter_stud": 12.6,      # TODO(VERIFY): no drop at rest
        "alt_output": 12.6,        # TODO(VERIFY)
        "chassis": 0.0,            # TODO(VERIFY): chassis ground ~0
    },
    EngineState.KEY_ON: {
        "battery_positive": 12.4,  # TODO(VERIFY)
        "battery_negative": 0.0,
        "engine_block": 0.0,       # TODO(VERIFY)
        "starter_stud": 12.3,      # TODO(VERIFY): small positive-cable drop
        "alt_output": 12.4,        # TODO(VERIFY)
        "chassis": 0.0,
    },
    EngineState.CRANKING: {
        "battery_positive": 9.8,   # TODO(VERIFY): healthy full-current sag
        "battery_negative": 0.0,
        "engine_block": 0.0,       # TODO(VERIFY): healthy ground stays ~0
        "starter_stud": 9.6,       # TODO(VERIFY): positive-cable drop under load
        "alt_output": 9.5,         # TODO(VERIFY)
        "chassis": 0.0,
    },
    # Alternator regulating at idle, modest charge current into the battery.
    # alt_output is the SOURCE here, so it sits highest; battery terminals
    # read charging voltage (typical healthy 13.8-14.6 V at idle).
    EngineState.RUNNING: {
        "battery_positive": 14.3,  # TODO(VERIFY): charging V at battery
        "battery_negative": 0.0,
        "engine_block": 0.0,       # TODO(VERIFY): charge return, healthy ~0
        "starter_stud": 14.3,      # TODO(VERIFY): same rail, no starter draw
        "alt_output": 14.4,        # TODO(VERIFY): regulator setpoint
        "chassis": 0.0,
    },
}

IDLE_RPM = 700.0  # TODO(VERIFY): warm idle speed

NOMINAL_CRANK_BEHAVIOR = CrankBehavior.STARTS
NOMINAL_CAN_STATUS = CanStatus.OK

# --- Physics coefficients (all TODO(VERIFY)) ---
GROUND_DROP_PER_OHM = 2.5          # V of ground-path drop per added ohm, under crank
GROUND_DROP_CAP = 4.0              # max modeled ground-path drop (V)
GROUND_REST_RISE = 0.03            # tiny engine_block rise at key_on for corroded ground
# A series ground resistance limits current, so the battery sags LESS than a
# healthy full-current crank. This fraction of the ground drop is "recovered"
# at the battery terminals. Derivation: healthy crank ~180 A sags the battery
# 12.6→9.8 V (internal R ≈ 15.6 mΩ). A ground fault choking current to ~half
# recovers ΔI×R_int ≈ 90×0.0156 ≈ 1.4 V against a ~2.5 V ground drop → ~0.6.
# Keeps the battery ≥ ~11.3 V under crank in ground-fault scenarios (innocent).
GROUND_CURRENT_RECOVERY = 0.6  # TODO(VERIFY)
POS_CABLE_DROP_PER_OHM = 1.8       # V of positive-cable drop per added ohm, under crank
POS_CABLE_DROP_CAP = 5.0
BROKEN_GROUND_ACROSS = 0.2         # residual V across starter with an open ground

# DTC code → human description (no fault names in descriptions).
DTC_DESCRIPTIONS: dict[str, str] = {
    "P0562": "System voltage low",  # TODO(VERIFY)
    "P0563": "System voltage high",  # TODO(VERIFY)
    "P0615": "Starter relay circuit",  # TODO(VERIFY)
    "P0616": "Starter relay circuit low",  # TODO(VERIFY)
    "P0617": "Starter relay circuit high",  # TODO(VERIFY)
    "P0622": "Generator field control",  # TODO(VERIFY)
    "U0100": "Lost communication with ECM/PCM",  # TODO(VERIFY)
    "U0101": "Lost communication with TCM",  # TODO(VERIFY)
    "U0121": "Lost communication with ABS",  # TODO(VERIFY)
    "B1318": "Battery voltage low",  # TODO(VERIFY)
}


class SymptomState(BaseModel):
    """Fully resolved observable snapshot (pre-noise)."""

    node_potentials: dict[str, float] = Field(default_factory=dict)
    dtcs: list[str] = Field(default_factory=list)
    crank_behavior: CrankBehavior = NOMINAL_CRANK_BEHAVIOR
    can_status: CanStatus = NOMINAL_CAN_STATUS
    intermittency: float = 1.0  # P(symptom manifests on a given probe)

    def potential_difference(self, point_a: str, point_b: str) -> float:
        """V(point_a) − V(point_b). Raises on unknown node names."""
        for pt in (point_a, point_b):
            if pt not in self.node_potentials:
                raise ValueError(
                    f"Unknown node '{pt}'. Valid nodes: {sorted(VALID_NODES)}"
                )
        return self.node_potentials[point_a] - self.node_potentials[point_b]


class FaultEffect(BaseModel):
    """Partial effect contributed by one fault mode (node-potential terms)."""

    node_deltas: dict[str, float] = Field(default_factory=dict)
    node_overrides: dict[str, float] = Field(default_factory=dict)
    dtcs: list[str] = Field(default_factory=list)
    crank_behavior: CrankBehavior | None = None
    can_status: CanStatus | None = None
    intermittency: float = 1.0
    # True when the starter draws ~no current (open circuit): the positive rail
    # does not sag from cranking load.
    blocks_starter_current: bool = False
    # True for an open ground: engine_block floats up to near battery positive.
    tie_engine_block_to_positive: bool = False


CRANK_PRECEDENCE: list[CrankBehavior] = [
    CrankBehavior.NO_CLICK,
    CrankBehavior.CLICK_NO_CRANK,
    CrankBehavior.SLOW_CRANK,
    CrankBehavior.CRANK_NO_START,
    CrankBehavior.STARTS,
]


def _crank_worse(a: CrankBehavior, b: CrankBehavior) -> CrankBehavior:
    return a if CRANK_PRECEDENCE.index(a) <= CRANK_PRECEDENCE.index(b) else b


def _apply_to_positive_rail(effect: FaultEffect, delta: float) -> None:
    for node in POSITIVE_RAIL:
        effect.node_deltas[node] = effect.node_deltas.get(node, 0.0) + delta


def effect_for_fault(fault: InjectedFault, engine_state: EngineState) -> FaultEffect:
    """Map a single fault to its partial node-potential effect."""
    sev = merge_severity(fault)
    effect = FaultEffect()
    c, m = fault.component, fault.mode

    if c == Component.BATTERY and m == FailureMode.WEAK:
        # A degraded battery sits low on the whole positive rail in every
        # state (reduced open-circuit voltage); the nominal cranking sag then
        # applies on top. Severity-driven so a scenario can dial "marginal"
        # vs "genuinely weak" without touching this code path.
        _apply_to_positive_rail(effect, -sev["terminal_drop_v"])
        if engine_state == EngineState.CRANKING:
            effect.crank_behavior = CrankBehavior.SLOW_CRANK
        effect.dtcs.extend(["P0562", "B1318"])

    elif c == Component.BATTERY and m == FailureMode.DEAD:
        dead_v = sev["open_circuit_v"]
        for node in POSITIVE_RAIL:
            effect.node_overrides[node] = dead_v
        effect.crank_behavior = CrankBehavior.NO_CLICK
        effect.blocks_starter_current = True
        effect.dtcs.extend(["P0562", "B1318"])

    elif c == Component.GROUND_STRAP and m == FailureMode.CORRODED:
        added_r = sev["added_resistance_ohms"]
        if engine_state == EngineState.CRANKING:
            drop = min(added_r * GROUND_DROP_PER_OHM, GROUND_DROP_CAP)
            # Ground-path resistance raises the engine-block (return) potential.
            effect.node_deltas["engine_block"] = drop
            # Reduced current → battery sags less than a healthy full-current crank.
            _apply_to_positive_rail(effect, drop * GROUND_CURRENT_RECOVERY)
            effect.crank_behavior = CrankBehavior.SLOW_CRANK
        elif engine_state == EngineState.KEY_ON:
            effect.node_deltas["engine_block"] = GROUND_REST_RISE
        effect.dtcs.append("P0562")

    elif c == Component.GROUND_STRAP and m == FailureMode.BROKEN:
        if engine_state in (EngineState.CRANKING, EngineState.KEY_ON):
            # Open ground: no return current; engine_block floats to battery+.
            effect.tie_engine_block_to_positive = True
            effect.blocks_starter_current = True
            effect.crank_behavior = CrankBehavior.CLICK_NO_CRANK
        effect.dtcs.append("P0562")

    elif c == Component.STARTER_RELAY and m == FailureMode.STUCK_OPEN:
        effect.crank_behavior = CrankBehavior.NO_CLICK
        effect.blocks_starter_current = True
        effect.dtcs.extend(["P0615", "P0616"])

    elif c == Component.STARTER_RELAY and m == FailureMode.STUCK_CLOSED:
        if engine_state == EngineState.KEY_ON:
            effect.crank_behavior = CrankBehavior.SLOW_CRANK  # TODO(VERIFY)
        effect.dtcs.extend(["P0615", "P0617"])

    elif c == Component.STARTER_MOTOR and m == FailureMode.WORN_BRUSHES:
        if engine_state == EngineState.CRANKING:
            _apply_to_positive_rail(effect, -0.4)  # TODO(VERIFY): extra draw
            effect.crank_behavior = CrankBehavior.SLOW_CRANK
        effect.dtcs.append("P0615")

    elif c == Component.STARTER_MOTOR and m == FailureMode.SEIZED:
        if engine_state == EngineState.CRANKING:
            _apply_to_positive_rail(effect, -1.2)  # TODO(VERIFY): locked-rotor sag
            effect.crank_behavior = CrankBehavior.CLICK_NO_CRANK
        effect.dtcs.append("P0615")

    elif c == Component.ALTERNATOR and m == FailureMode.DIODE_FAILURE:
        if engine_state == EngineState.RUNNING:
            # Weak charging: whole rail sits low (~13.2 V) with AC ripple
            # (ripple itself surfaces via the alt_output_v PID average).
            _apply_to_positive_rail(effect, -1.2)  # TODO(VERIFY)
        else:
            effect.node_deltas["alt_output"] = -0.8  # TODO(VERIFY)
        effect.dtcs.append("P0622")

    elif c == Component.ALTERNATOR and m == FailureMode.NO_OUTPUT:
        if engine_state == EngineState.RUNNING:
            # No charge: the system runs on the battery. The alt post is
            # still tied to the rail through the charge cable, so it reads
            # battery voltage — the tell is NO rise above resting, not 0 V.
            effect.node_overrides["battery_positive"] = 12.4  # TODO(VERIFY)
            effect.node_overrides["starter_stud"] = 12.35  # TODO(VERIFY)
            effect.node_overrides["alt_output"] = 12.35  # TODO(VERIFY)
        else:
            effect.node_overrides["alt_output"] = sev["output_v"]
        effect.dtcs.append("P0622")

    elif c == Component.FUSIBLE_LINK and m == FailureMode.BLOWN:
        if engine_state in (EngineState.CRANKING, EngineState.KEY_ON):
            # Open positive feed: starter_stud loses its supply.
            effect.node_overrides["starter_stud"] = 0.3  # TODO(VERIFY): open feed
            effect.crank_behavior = CrankBehavior.NO_CLICK
            effect.blocks_starter_current = True
        effect.dtcs.append("P0562")

    elif c == Component.FUSIBLE_LINK and m == FailureMode.HIGH_RESISTANCE:
        added_r = sev["added_resistance_ohms"]
        if engine_state == EngineState.CRANKING:
            drop = min(added_r * POS_CABLE_DROP_PER_OHM, POS_CABLE_DROP_CAP)
            # Positive-side series drop: starter_stud sags below battery positive.
            effect.node_deltas["starter_stud"] = -drop
            effect.crank_behavior = CrankBehavior.SLOW_CRANK

    elif c == Component.IGNITION_SWITCH and m == FailureMode.NO_CRANK_SIGNAL:
        effect.crank_behavior = CrankBehavior.NO_CLICK
        effect.blocks_starter_current = True
        if engine_state == EngineState.KEY_ON:
            effect.node_deltas["starter_stud"] = -0.5  # TODO(VERIFY)

    elif c == Component.IGNITION_SWITCH and m == FailureMode.ACCESSORY_DROP:
        drop = sev["voltage_drop_v"]
        if engine_state == EngineState.KEY_ON:
            effect.node_deltas["battery_positive"] = -drop * 0.3  # TODO(VERIFY)
            effect.node_deltas["starter_stud"] = -drop
        effect.dtcs.append("P0562")

    elif c == Component.ECU_CAN_NODE and m == FailureMode.BUS_OFF:
        effect.can_status = CanStatus.BUS_OFF
        effect.dtcs.extend(["U0100", "U0101"])
        if engine_state == EngineState.CRANKING:
            effect.crank_behavior = CrankBehavior.CRANK_NO_START

    elif c == Component.ECU_CAN_NODE and m == FailureMode.INTERMITTENT:
        # A flaky ECU/CAN node drops off the bus only sometimes. When it DOES
        # manifest on a given probe the engine cranks but never fires (no
        # injection/spark command) — same crank signature as bus_off, but
        # present on only ``manifest_probability`` of probes. Whether it
        # manifests is decided in World (deterministic in seed + probe index);
        # this effect describes what is seen WHEN it does. It moves no node
        # potentials at all: a purely electrical drop-test workflow cannot
        # find this fault.
        effect.can_status = CanStatus.DEGRADED
        effect.intermittency = sev["manifest_probability"]
        effect.dtcs.append("U0100")
        if engine_state == EngineState.CRANKING:
            effect.crank_behavior = CrankBehavior.CRANK_NO_START

    return effect


def _propagate_resting_red_herring(
    nodes: dict[str, float],
    engine_state: EngineState,
    red_herring_readings: dict[str, float],
) -> None:
    """A resting override that suppresses the source flows down the supply path.

    Models downstream nodes as points on the same resting supply path: if the
    battery reads low at rest, everything it feeds reads equally low (preserving
    each node's small nominal inter-node drop). Generalizes to any future
    resting red herring on the supply source.
    """
    if SUPPLY_SOURCE not in red_herring_readings:
        return
    nominal_source = NOMINAL_NODES[engine_state][SUPPLY_SOURCE]
    suppression = nominal_source - nodes[SUPPLY_SOURCE]
    if suppression <= 0:
        return
    for node in DOWNSTREAM_OF_SOURCE:
        if node not in red_herring_readings:
            nodes[node] -= suppression


def _enforce_resting_monotonicity(nodes: dict[str, float]) -> None:
    """No downstream node may exceed its upstream source at rest."""
    for upstream, downstream in RESTING_SUPPLY_EDGES:
        if nodes[downstream] > nodes[upstream]:
            nodes[downstream] = nodes[upstream]


def _base_nodes(engine_state: EngineState, blocks_current: bool) -> dict[str, float]:
    base = dict(NOMINAL_NODES[engine_state])
    if engine_state == EngineState.CRANKING and blocks_current:
        # No starter current flows → positive rail sits at no-load (key_on) level.
        for node in POSITIVE_RAIL:
            base[node] = NOMINAL_NODES[EngineState.KEY_ON][node]
    return base


def _battery_voltage(nodes: dict[str, float]) -> float:
    return nodes[Node.BATTERY_POSITIVE.value] - nodes[Node.BATTERY_NEGATIVE.value]


def resolve_symptoms(
    active_faults: list[InjectedFault],
    engine_state: EngineState,
    *,
    red_herring_readings: dict[str, float] | None = None,
) -> SymptomState:
    """Combine all active faults into a single node-potential snapshot.

    ``red_herring_readings`` are marginal resting-load node potentials
    (key_off / key_on only) that suppress the resting supply path uniformly.
    Under cranking they do not apply — load-dependent faults (e.g. a corroded
    ground) reveal themselves only under current draw.
    """
    effects = [effect_for_fault(f, engine_state) for f in active_faults]
    blocks_current = any(e.blocks_starter_current for e in effects)
    nodes = _base_nodes(engine_state, blocks_current)

    dtcs: list[str] = []
    crank = NOMINAL_CRANK_BEHAVIOR
    can = NOMINAL_CAN_STATUS
    intermittency = 1.0
    tie_engine_block = False

    for eff in effects:
        for node, delta in eff.node_deltas.items():
            nodes[node] = nodes.get(node, 0.0) + delta
        for node, override in eff.node_overrides.items():
            nodes[node] = override
        for code in eff.dtcs:
            if code not in dtcs:
                dtcs.append(code)
        if eff.crank_behavior is not None:
            crank = _crank_worse(crank, eff.crank_behavior)
        if eff.can_status is not None:
            can = eff.can_status
        intermittency = min(intermittency, eff.intermittency)
        if eff.tie_engine_block_to_positive:
            tie_engine_block = True

    # Reference node is fixed at 0 V by definition.
    nodes[REFERENCE_NODE] = 0.0

    if engine_state == EngineState.CRANKING:
        if tie_engine_block:
            # Open ground floats up to just under battery positive (drop test
            # reads ~full battery voltage; almost nothing across the starter).
            nodes["engine_block"] = nodes["battery_positive"] - BROKEN_GROUND_ACROSS
        # Battery must sag under load: cranking voltage < resting voltage. When
        # no starter current flows (open circuit), there is no load and hence no
        # sag — cranking equals resting, which is physical, so skip the clamp.
        if not blocks_current:
            resting_v = _battery_voltage(
                _resolve_nodes_only(
                    active_faults, EngineState.KEY_ON, red_herring_readings
                )
            )
            if _battery_voltage(nodes) >= resting_v:
                nodes["battery_positive"] = nodes["battery_negative"] + resting_v - 0.1
    elif engine_state != EngineState.RUNNING:
        # Resting states only (key_off / key_on). RUNNING gets neither rule:
        # red herrings are RESTING-ONLY overrides (invariant 3), and with the
        # alternator as source, alt_output legitimately exceeds
        # battery_positive — resting monotonicity does not apply.
        if red_herring_readings:
            for node, val in red_herring_readings.items():
                nodes[node] = val
            _propagate_resting_red_herring(nodes, engine_state, red_herring_readings)
        _enforce_resting_monotonicity(nodes)

    return SymptomState(
        node_potentials=nodes,
        dtcs=dtcs,
        crank_behavior=crank,
        can_status=can,
        intermittency=intermittency,
    )


def _resolve_nodes_only(
    active_faults: list[InjectedFault],
    engine_state: EngineState,
    red_herring_readings: dict[str, float] | None,
) -> dict[str, float]:
    """Resolve just the node potentials (used for resting reference in cranking)."""
    return resolve_symptoms(
        active_faults, engine_state, red_herring_readings=red_herring_readings
    ).node_potentials


def dtc_description(code: str) -> str:
    return DTC_DESCRIPTIONS.get(code, "Unknown diagnostic trouble code")
