# DOMAIN_TRUTH.md

**Purpose:** Single-page review of every fault → symptom mapping in `no-start-env`.
**Status:** All numeric values are draft — marked `TODO(VERIFY)` in source until signed off.

## Architecture note

Ground truth lives in `src/nostart/domain/` and `World._active_faults`. Tool outputs are instrument readings only; this document is for the domain expert, not the agent.

---

## Nominal (healthy) baselines

| Engine state | battery_terminals | starter_stud | chassis_ground | alt_output | crank | CAN |
|--------------|-------------------|------------|----------------|------------|-------|-----|
| key_off | 12.6 V | 12.6 V | 0.0 V | 12.6 V | — | ok |
| key_on | 12.4 V | 12.3 V | 0.0 V | 12.4 V | — | ok |
| cranking | 9.8 V | 9.6 V | 0.0 V | 9.5 V | starts | ok |

Meter noise: ±0.05 V on voltage probes (seeded). All values `TODO(VERIFY)`.

### Resting supply-path monotonicity (invariant)

At rest (`key_off` / `key_on`, no crank load) voltage is **monotonic non-increasing down the supply path**: `battery_terminals >= starter_stud` and `battery_terminals >= alt_output`, with only small nominal inter-node drops. A downstream point may never read higher than the upstream source it is fed from at rest. This is enforced in `resolve_symptoms` for every scenario and fault.

Because of this, a **resting red herring suppresses the whole resting supply path uniformly**: if a red herring pulls `battery_terminals` low at rest, the same suppression flows to `starter_stud` / `alt_output` (preserving their nominal drops). The bait is a uniformly low resting circuit, not a low battery beside a normal stud (which would itself expose the anomaly). Under **cranking** this does not apply — the corroded ground-path resistance only matters under load, so the battery holds while the stud collapses.

---

## Component failure modes → symptoms

### battery

| Mode | Severity param | Voltage effects | DTCs | Crank behavior | CAN | Intermittency | Visual inspect |
|------|----------------|-----------------|------|----------------|-----|---------------|----------------|
| **weak** | `cca_remaining_pct` = 45% | −0.6 V terminals & stud; extra sag when cranking | P0562, B1318 | slow_crank (cranking only) | — | 1.0 | "Terminal corrosion light; case looks aged." |
| **dead** | `open_circuit_v` = 2.1 V | Override terminals ≈2.1 V, stud ≈2.0 V, alt ≈2.1 V | P0562, B1318 | no_click | — | 1.0 | "Terminals corroded; slight sulfation odor." |

### ground_strap

| Mode | Severity param | Voltage effects | DTCs | Crank behavior | CAN | Intermittency | Visual inspect |
|------|----------------|-----------------|------|----------------|-----|---------------|----------------|
| **corroded** | `added_resistance_ohms` = 0.8 Ω | key_on: −0.15 V at starter_stud; cranking: −(min(R×2.5, 4.0)) V at stud | P0562 | slow_crank (cranking) | — | 1.0 | 60% chance "looks normal"; else "greenish end" |
| **broken** | `added_resistance_ohms` = 50 Ω | key_on/cranking: −8.0 V at starter_stud | P0562 | click_no_crank | — | 1.0 | "Strap frayed at engine block." |

### starter_relay

| Mode | Severity param | Voltage effects | DTCs | Crank behavior | CAN | Intermittency | Visual inspect |
|------|----------------|-----------------|------|----------------|-----|---------------|----------------|
| **stuck_open** | — | — | P0615, P0616 | no_click | — | 1.0 | "No click heard at relay." |
| **stuck_closed** | — | — | P0615, P0617 | slow_crank (key_on) | — | 1.0 | "Click persists after key release." |

### starter_motor

| Mode | Severity param | Voltage effects | DTCs | Crank behavior | CAN | Intermittency | Visual inspect |
|------|----------------|-----------------|------|----------------|-----|---------------|----------------|
| **worn_brushes** | `crank_rpm_factor` = 0.55 | cranking: −0.4 V terminals | P0615 | slow_crank (cranking) | — | 1.0 | "Grinding noise during slow crank." |
| **seized** | — | cranking: −1.2 V terminals | P0615 | click_no_crank (cranking) | — | 1.0 | "Loud clunk, no rotation." |

### alternator

| Mode | Severity param | Voltage effects | DTCs | Crank behavior | CAN | Intermittency | Visual inspect |
|------|----------------|-----------------|------|----------------|-----|---------------|----------------|
| **diode_failure** | `ac_ripple_v` = 1.2 V | −0.8 V alt_output; PID avg depressed by ripple×0.1 | P0622 | — (no-start context) | — | 1.0 | "Faint whine from alternator area." |
| **no_output** | `output_v` = 0.0 V | Override alt_output = 0 V | P0622 | — | — | 1.0 | "Belt intact; connector seated." |

### fusible_link

| Mode | Severity param | Voltage effects | DTCs | Crank behavior | CAN | Intermittency | Visual inspect |
|------|----------------|-----------------|------|----------------|-----|---------------|----------------|
| **blown** | — | key_on/cranking: −12 V at starter_stud | P0562 | no_click | — | 1.0 | "Link appears melted at mid-span." |
| **high_resistance** | `added_resistance_ohms` = 2.5 Ω | cranking: −(min(R×1.8, 5.0)) V at stud | — | slow_crank (cranking) | — | 1.0 | "Link discolored but not open." |

### ignition_switch

| Mode | Severity param | Voltage effects | DTCs | Crank behavior | CAN | Intermittency | Visual inspect |
|------|----------------|-----------------|------|----------------|-----|---------------|----------------|
| **no_crank_signal** | — | key_on: −0.5 V starter_stud | — | no_click | — | 1.0 | "Dash lights flicker in START." |
| **accessory_drop** | `voltage_drop_v` = 2.5 V | key_on: −0.75 V terminals, −2.5 V stud | P0562 | — | — | 1.0 | "Lights dim sharply in START." |

### ecu_can_node

| Mode | Severity param | Voltage effects | DTCs | Crank behavior | CAN | Intermittency | Visual inspect |
|------|----------------|-----------------|------|----------------|-----|---------------|----------------|
| **bus_off** | — | — | U0100, U0101 | crank_no_start (cranking) | bus_off | 1.0 | "MIL on; scan tool intermittent." |
| **intermittent** | `manifest_probability` = 0.35 | — | U0100 | — | degraded | 0.35 per probe | "No obvious wiring damage at ECM." |

---

## Crank behavior precedence

When multiple faults compete, the **worst** behavior wins:

`no_click` → `click_no_crank` → `slow_crank` → `crank_no_start` → `starts`

---

## DTC code reference

| Code | Description |
|------|-------------|
| P0562 | System voltage low |
| P0563 | System voltage high |
| P0615 | Starter relay circuit |
| P0616 | Starter relay circuit low |
| P0617 | Starter relay circuit high |
| P0622 | Generator field control |
| U0100 | Lost communication with ECM/PCM |
| U0101 | Lost communication with TCM |
| U0121 | Lost communication with ABS |
| B1318 | Battery voltage low |

---

## Phase 1 scenarios

| ID | Tier | Seed | Root cause | Red herring | Complaint | Expert baseline |
|----|------|------|------------|-------------|-----------|-----------------|
| `easy_dead_battery` | easy | 1001 | battery:dead | — | "Nothing when I turn the key." | 15 min, $0 |
| `medium_corroded_ground` | medium | 2001 | ground_strap:corroded (0.8 Ω) | — | "Slow crank, borderline battery at parts store." | 35 min, $25 |
| `medium_ground_red_herring_battery` | medium | 2002 | ground_strap:corroded (1.0 Ω) | battery_terminals forced to 11.8 V key_on | "Slow crank; shop said battery 'a little weak'." | 40 min, $25 |

**Red herring semantics:** `red_herring_voltages` overrides resting readings (`key_off` / `key_on`) only — e.g. `battery_terminals` ≈ 11.8 V tempts a weak-battery diagnosis. Cranking voltages always sag below resting. **Innocent red-herring batteries** must hold **above the healthy cranking floor** (~9.8 V) under load via `red_herring_cranking_battery` (this scenario: **10.5 V**); they read marginal at rest but fine under crank. The diagnostic signal is the **battery-vs-starter_stud delta under cranking** (voltage-drop test), not either point alone — stud sags ~7 V while battery holds ~10.5 V (~3 V gap).

---

## replace_part behavior

Installing a known-good part removes that component's fault from `_active_faults` but does **not** reveal whether the part was faulty. Symptom masking (e.g., new battery on bad ground) is intentional — grader scores root cause, not symptom relief.

---

## Sign-off checklist

- [ ] Nominal voltages realistic for 12 V system
- [ ] Ground drop model (R → V) plausible
- [ ] Crank behavior mapping per fault correct
- [ ] DTC assignments appropriate
- [ ] Red herring scenario misleads but is beatable with voltage drop test
- [ ] Part prices and action times reasonable

**Expert sign-off:** _________________ Date: _________
