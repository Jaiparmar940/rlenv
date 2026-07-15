# DOMAIN_TRUTH.md

**Purpose:** Single-page review of every fault → symptom mapping in `no-start-env`.
**Status:** All numeric values signed off by the domain expert (Jaivir Parmar); see the sign-off checklist at the bottom. Historical `TODO(VERIFY)` tags in source predate the running-state sign-off (2026-07-14) and are stale.

## Architecture note

Ground truth lives in `src/nostart/domain/` and `World._active_faults`. Tool outputs are instrument readings only; this document is for the domain expert, not the agent.

---

## Nominal (healthy) baselines


| Engine state | battery_positive | starter_stud | engine_block / chassis | alt_output | crank  | CAN |
| ------------ | ---------------- | ------------ | ---------------------- | ---------- | ------ | --- |
| key_off      | 12.6 V           | 12.6 V       | 0.0 V                  | 12.6 V     | —      | ok  |
| key_on       | 12.4 V           | 12.3 V       | 0.0 V                  | 12.4 V     | —      | ok  |
| cranking     | 9.8 V            | 9.6 V        | 0.0 V                  | 9.5 V      | starts | ok  |


All potentials are relative to `battery_negative` (reference, 0 V); readings are two-point differences between any node pair.

Meter noise: ±0.05 V on voltage probes (seeded). All values `TODO(VERIFY)`.

### Resting supply-path monotonicity (invariant)

At rest (`key_off` / `key_on`, no crank load) voltage is **monotonic non-increasing down the supply path**: `battery_terminals >= starter_stud` and `battery_terminals >= alt_output`, with only small nominal inter-node drops. A downstream point may never read higher than the upstream source it is fed from at rest. This is enforced in `resolve_symptoms` for every scenario and fault.

Because of this, a **resting red herring suppresses the whole resting supply path uniformly**: if a red herring pulls `battery_terminals` low at rest, the same suppression flows to `starter_stud` / `alt_output` (preserving their nominal drops). The bait is a uniformly low resting circuit, not a low battery beside a normal stud (which would itself expose the anomaly). Under **cranking** this does not apply — the corroded ground-path resistance only matters under load, so the battery holds while the stud collapses.

---



## Component failure modes → symptoms



### battery


| Mode     | Severity param            | Voltage effects                                    | DTCs         | Crank behavior             | CAN | Intermittency | Visual inspect                               |
| -------- | ------------------------- | -------------------------------------------------- | ------------ | -------------------------- | --- | ------------- | -------------------------------------------- |
| **weak** | `cca_remaining_pct` = 45%; `terminal_drop_v` (default 0.6, compound scenario 1.6) | whole rail sits −`terminal_drop_v` in every state (low OCV); nominal cranking sag applies on top | P0562, B1318 | slow_crank (cranking only) | —   | 1.0           | "Terminal corrosion light; case looks aged." |
| **dead** | `open_circuit_v` = 2.1 V  | Override terminals ≈2.1 V, stud ≈2.0 V, alt ≈2.1 V | P0562, B1318 | no_click                   | —   | 1.0           | "Terminals corroded; slight sulfation odor." |




### ground_strap


| Mode         | Severity param                                   | Voltage effects                                                                                                                                                                                  | DTCs  | Crank behavior        | CAN | Intermittency | Visual inspect                                 |
| ------------ | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----- | --------------------- | --- | ------------- | ---------------------------------------------- |
| **corroded** | `added_resistance_ohms` (scenarios: 1.1 / 1.2 / 0.7 Ω) | key_on: engine_block rises +0.03 V; cranking: engine_block rises +min(R×2.5, 4.0) V (ground-path drop) AND battery/rail recovers +0.222×drop (series-derived: recovery/drop = sag/OCV = 2.8/12.6 — battery reads innocent, ~10.4 V in the 1.1/1.2 Ω scenarios, a passing load test) | P0562 | slow_crank (cranking) | —   | 1.0           | 60% chance "looks normal"; else "greenish end" |
| **broken**   | `added_resistance_ohms` = 50 Ω                   | key_on/cranking: open ground — no starter current; engine_block floats to battery_positive − 0.2 V (drop test reads ~full battery voltage)                                                       | P0562 | click_no_crank        | —   | 1.0           | "Strap frayed at engine block."                |




### starter_relay


| Mode             | Severity param | Voltage effects | DTCs         | Crank behavior      | CAN | Intermittency | Visual inspect                      |
| ---------------- | -------------- | --------------- | ------------ | ------------------- | --- | ------------- | ----------------------------------- |
| **stuck_open**   | —              | —               | P0615, P0616 | no_click            | —   | 1.0           | "No click heard at relay."          |
| **stuck_closed** | —              | —               | P0615, P0617 | slow_crank (key_on) | —   | 1.0           | "Click persists after key release." |




### starter_motor


| Mode             | Severity param            | Voltage effects            | DTCs  | Crank behavior            | CAN | Intermittency | Visual inspect                      |
| ---------------- | ------------------------- | -------------------------- | ----- | ------------------------- | --- | ------------- | ----------------------------------- |
| **worn_brushes** | `crank_rpm_factor` = 0.55 | cranking: −0.4 V terminals | P0615 | slow_crank (cranking)     | —   | 1.0           | "Grinding noise during slow crank." |
| **seized**       | —                         | cranking: −1.2 V terminals | P0615 | click_no_crank (cranking) | —   | 1.0           | "Loud clunk, no rotation."          |




### alternator


| Mode              | Severity param        | Voltage effects                                    | DTCs  | Crank behavior       | CAN | Intermittency | Visual inspect                      |
| ----------------- | --------------------- | -------------------------------------------------- | ----- | -------------------- | --- | ------------- | ----------------------------------- |
| **diode_failure** | `ac_ripple_v` = 1.2 V | −0.8 V alt_output; PID avg depressed by ripple×0.1 | P0622 | — (no-start context) | —   | 1.0           | "Faint whine from alternator area." |
| **no_output**     | `output_v` = 0.0 V    | Override alt_output = 0 V                          | P0622 | —                    | —   | 1.0           | "Belt intact; connector seated."    |




### fusible_link


| Mode                | Severity param                  | Voltage effects                        | DTCs  | Crank behavior        | CAN | Intermittency | Visual inspect                     |
| ------------------- | ------------------------------- | -------------------------------------- | ----- | --------------------- | --- | ------------- | ---------------------------------- |
| **blown**           | —                               | key_on/cranking: −12 V at starter_stud | P0562 | no_click              | —   | 1.0           | "Link appears melted at mid-span." |
| **high_resistance** | `added_resistance_ohms` = 2.5 Ω | cranking: −(min(R×1.8, 5.0)) V at stud | —     | slow_crank (cranking) | —   | 1.0           | "Link discolored but not open."    |




### ignition_switch


| Mode                | Severity param           | Voltage effects                        | DTCs  | Crank behavior | CAN | Intermittency | Visual inspect                  |
| ------------------- | ------------------------ | -------------------------------------- | ----- | -------------- | --- | ------------- | ------------------------------- |
| **no_crank_signal** | —                        | key_on: −0.5 V starter_stud            | —     | no_click       | —   | 1.0           | "Dash lights flicker in START." |
| **accessory_drop**  | `voltage_drop_v` = 2.5 V | key_on: −0.75 V terminals, −2.5 V stud | P0562 | —              | —   | 1.0           | "Lights dim sharply in START."  |




### ecu_can_node


| Mode             | Severity param                | Voltage effects | DTCs         | Crank behavior            | CAN      | Intermittency  | Visual inspect                     |
| ---------------- | ----------------------------- | --------------- | ------------ | ------------------------- | -------- | -------------- | ---------------------------------- |
| **bus_off**      | —                             | —               | U0100, U0101 | crank_no_start (cranking) | bus_off  | 1.0            | "MIL on; scan tool intermittent."  |
| **intermittent** | `manifest_probability` = 0.35 | —               | U0100        | crank_no_start (when manifesting) | degraded | 0.35 per probe, deterministic hash of (seed, probe kind, probe index) | "No obvious wiring damage at ECM." |


---



## Crank behavior precedence

When multiple faults compete, the **worst** behavior wins:

`no_click` → `click_no_crank` → `slow_crank` → `crank_no_start` → `starts`

---



## DTC code reference


| Code  | Description                     |
| ----- | ------------------------------- |
| P0562 | System voltage low              |
| P0563 | System voltage high             |
| P0615 | Starter relay circuit           |
| P0616 | Starter relay circuit low       |
| P0617 | Starter relay circuit high      |
| P0622 | Generator field control         |
| U0100 | Lost communication with ECM/PCM |
| U0101 | Lost communication with TCM     |
| U0121 | Lost communication with ABS     |
| B1318 | Battery voltage low             |


---



## Scenarios


| ID                                  | Tier   | Seed | Root cause                    | Secondary / red herring                   | Complaint                                        | Expert baseline (full resolution) |
| ----------------------------------- | ------ | ---- | ----------------------------- | ----------------------------------------- | ------------------------------------------------ | --------------- |
| `easy_dead_battery`                 | easy   | 1001 | battery:dead                  | —                                         | "Nothing when I turn the key."                   | 25 min, $180    |
| `medium_corroded_ground`            | medium | 2001 | ground_strap:corroded (1.1 Ω) | —                                         | "Slow crank, borderline battery at parts store." | 34 min, $25     |
| `medium_ground_red_herring_battery` | medium | 2002 | ground_strap:corroded (1.2 Ω) | red herring: battery_positive forced to 11.8 V at rest | "Slow crank; shop said battery 'a little weak'." | 37 min, $25     |
| `hard_intermittent_ecu_can`         | hard   | 3035 | ecu_can_node:intermittent (0.35) | —                                      | "Sometimes it just won't fire; two shops found nothing." | 31 min, $450 |
| `hard_compound_battery_and_ground`  | hard   | 3002 | ground_strap:corroded (0.7 Ω) PRIMARY | secondary GENUINE fault: battery:weak (`terminal_drop_v` 1.6 → 11.0 V rest, ~8.6 V crank, fails load test) | "Cranks slow and usually won't catch." | 54 min, $205 |

**Compound scenario semantics:** the secondary fault is genuinely bad — not bait. Neither repair alone starts the car; the 60-point root-cause budget splits 45 (primary) / 15 (secondary); replacing the secondary is not a wrong part. Signed off by Jaivir 2026-07-12.


**Red herring semantics:** `red_herring_voltages` overrides resting readings (`key_off` / `key_on`) only — e.g. `battery_positive` ≈ 11.8 V tempts a weak-battery diagnosis, and the suppression flows down the whole resting supply path uniformly (stud/alt read equally low — no false stud anomaly at rest). Under cranking the override does not apply. **Innocent red-herring batteries hold ~10.5 V under crank — a passing load test (> 9.6 V)** — this emerges from the physics, not a separate knob: the corroded ground chokes cranking current, so the battery sags ~1.3 V below its resting bait yet still clears the load-test condemnation line (bait, not a co-fault). The diagnostic tell is the **ground-path drop under cranking** (~~`battery_negative` ~~→~~ `engine_block` ~~≈ 3.0 V) while the positive feed (~~`battery_positive` ~~→~~ `starter_stud`~~) stays ≤ ~0.5 V — a two-point drop test uniquely localizes the fault to the ground junction; no single-point reading does. **Replacing the red-herring component clears the bait:** the marginal resting readings belong to the original battery (~~`red_herring_component`~~), so after a known-good battery is installed, resting readings return to nominal (~~12.6 V) while the ground-path tell and slow crank persist — a fresh battery can never read marginal at rest.

---



## replace_part behavior

Installing a known-good part removes that component's fault from `_active_faults` but does **not** reveal whether the part was faulty. Symptom masking (e.g., new battery on bad ground) is intentional — grader scores root cause, not symptom relief.

---

## Running engine state (added 2026-07-12 — NEEDS SIGN-OFF)

Added after an eval transcript showed a correct-thinking model framed for an alternator fault: it fixed the car, checked charging, and got engine-off voltages because no running state existed.

**State machine:** `attempt_start` → `starts` sets the engine running. It stays running until something implies shutting it off: `replace_part` (wrenching on the car) or a `measure_voltage` in any non-running key state. Measuring in `running` while the engine is not running RAISES. `read_pid` is passive and reflects the current state (running values after a successful start, key_on otherwise); every PID payload names the `engine_state` it was read in, so an engine-off `alt_output_v` (rail voltage) is visibly not a charging measurement. `rpm` is a live tach: 0 with the engine off, ≈ 700 idle while running (crank speed is not observable via PID — `attempt_start` reports `slow_crank` directly).

**Nominal running potentials** (alternator regulating at idle, modest charge current; signed off 2026-07-14):

| Node | V | Rationale |
| --- | --- | --- |
| alt_output | 14.4 | regulator setpoint (source node while running) |
| battery_positive | 14.3 | charging V at battery, small feed drop from alt |
| starter_stud | 14.3 | same rail, no starter draw |
| engine_block / chassis | 0.0 | healthy charge-return ground |

Resting monotonicity and resting red herrings do **not** apply at running: the alternator is the source (`alt_output ≥ battery_positive` is correct), and a marginal-battery bait reads charging voltage while being charged (bait remains at key_off/key_on only).

**Alternator faults while running** (only faults reachable in a running engine today; signed off 2026-07-14):

| Mode | Running effect | Tell |
| --- | --- | --- |
| no_output | whole rail on battery: battery_positive 12.4, alt_output 12.35 | no rise above resting; alt post ≈ battery (cable intact), NOT 0 V |
| diode_failure | rail −1.2 → ~13.2, plus AC-ripple-depressed PID avg | charges, but low |

All other fault modes prevent the engine from starting in the current scenario set, so their running-state values are unreachable (gated by the state machine, verified by `check_running_charging` in sanity_check.py).

---



## Series-consistent ground-current recovery (ruled 2026-07-12)

`GROUND_CURRENT_RECOVERY` was originally hand-tuned to 0.6. A series-circuit solve of the model's own constants showed that value inconsistent (it gave 11.45 V at the battery in `medium_corroded_ground` where the circuit arithmetic gives 10.41 V). **Jaivir ruled 2026-07-12: the model must be consistent with the series solve.** The constant is now *derived*, not tuned: in a linear series circuit, recovery/drop = R_int/R_tot = healthy_sag/OCV = (12.6 − 9.8)/12.6 ≈ 0.222, exactly, for any strap resistance. Consequences: innocent batteries in the ground-fault scenarios hold ~10.41/10.47 V under crank (previously ~11.45/11.6) — still a clearly passing load test (> 9.6 V), so every diagnostic tell is unchanged in kind; the `BATTERY_HOLDS` floor in sanity_check.py moved from 11.3 to 10.3 accordingly. Full derivation in `propagation.py` and PENDING_HUMAN_PHYSICS_SIGNOFF.md §4.

---

## Sign-off checklist

- [x] Nominal voltages realistic for 12 V system
- [x] Ground drop model (R → V) plausible
- [x] Crank behavior mapping per fault correct
- [x] DTC assignments appropriate
- [x] Red herring scenario misleads but is beatable with voltage drop test
- [x] Part prices and action times reasonable
- [x] Series-consistent `GROUND_CURRENT_RECOVERY` (derived 0.222; ruled by Jaivir 2026-07-12)
- [x] Hard tier: compound scenario physics (11.0 V rest / ~8.6 V crank weak battery, 0.7 Ω strap, 1.78 V drop), intermittent ECU/CAN (crank_no_start at 0.35, deterministic per seed), 45/15 compound scoring split — signed off by Jaivir 2026-07-12
- [x] Running-state charging physics (2026-07-12 addition: nominal 14.3/14.4 V, alternator-fault behavior, state-machine gating) — signed off by Jaivir 2026-07-14

**Expert sign-off:** Jaivir Parmar **Date:** July 10, 2026 (hard tier + recovery ruling: July 12, 2026; running-state charging physics: July 14, 2026)