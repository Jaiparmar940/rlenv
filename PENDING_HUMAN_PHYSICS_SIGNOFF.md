# PENDING HUMAN PHYSICS SIGN-OFF — hard-tier preview

**Branch:** `hard-tier-preview`. **Status: DO NOT MERGE. DO NOT PUBLISH RESULTS FROM THESE SCENARIOS.**
Nothing here is verified by play. Every number below is what the resistance-network model
*computes*; none of it is hand-authored, and none of it is confirmed by a human who has
touched a car.

Two new scenarios: `hard_intermittent_ecu_can`, `hard_compound_battery_and_ground`.
This file is the checklist Jaivir must clear before the branch can merge.

---

## What I changed in the physics (and what I refused to change)

**Changed — three things, all severity-driven, no hand-authored voltages:**

1. `battery:weak` now reads its rail offset from severity `terminal_drop_v` instead of a
   hard-coded `-0.6`. Default is `0.6`, so **every existing scenario is bit-for-bit
   unchanged** (verified: `medium_corroded_ground` still reads 11.46 V / −2.74 V ground drop;
   red herring still 11.82 V / −2.98 V). The compound scenario dials it to `1.6`.
2. `ecu_can_node:intermittent` now produces `crank_no_start` **when it manifests**. It had no
   crank effect at all before, so a car with that fault started perfectly every time — the
   mode existed but was unusable. It still moves **no node potential**: a drop-test-only
   workflow cannot find it. That is the point of the scenario.
3. Intermittent manifestation is now a hash of `(seed, probe kind, probe index)` rather than a
   draw from the shared `self._rng` stream (which is also consumed by meter noise and visual
   inspection). Consequence: **the k-th crank always gives the same answer regardless of what
   the agent did in between**, and identical runs give identical observations. Pinned by three
   tests.

**Refused to change:** I did not touch `GROUND_DROP_PER_OHM`, `GROUND_CURRENT_RECOVERY`, or any
existing scenario's constants — see the open question in §4, which is about those constants and
which I am **not** qualified to resolve.

---

## 1. `hard_intermittent_ecu_can` (tier HARD, seed 3035)

**Complaint:** "Sometimes it cranks and cranks and just won't fire. Other times it starts right
up. Two shops found nothing wrong."

**The tell a tech should see:** the fault is *only* visible in behavior, never in a voltage.
The car cranks-no-start on some attempts and starts fine on others; the DTC scan is **clean most
of the time** and coughs up U0100 occasionally; the CAN-status PID likewise flickers between
`ok` and `degraded`. **A single clean reading must not exonerate the ECU** — that is the whole
skill being tested. Every voltage in every state reads nominal (12.60 / 12.40 / 9.80 V, ground
drop 0.00 V), so an agent that only knows how to do drop tests is structurally unable to solve
this one.

**What the model produces (deterministic, seed 3035 — paste-from-run):**

```
cranks 1-10: crank_no_start, starts, crank_no_start, crank_no_start, starts,
             starts, crank_no_start, starts, crank_no_start, starts
scans 1-6  : clean, U0100, clean, clean, clean, clean
can_status : ok, ok, degraded, ok, degraded, degraded

state       battery_v   ground_drop   stud_feed
key_off        12.60        0.00        0.00
key_on         12.40        0.00        0.10
cranking        9.80        0.00        0.20
```

After replacing `ecu_can_node`: 12/12 consecutive `starts`.

The seed was chosen for *shape*, not for score: crank #1 fails (the complaint is real), crank #2
starts (so one good crank proves nothing), and the **first scan is clean** (so a single clean
scan must not clear the ECU). I did not tune it to make any model look good or bad.

**Constants awaiting your sign-off:**

| Constant | Value | Where | My doubt |
|---|---|---|---|
| `manifest_probability` | 0.35 | already in `components.py` (I did not pick it) | Is 35% the right flakiness? At 0.35 an agent needs ~3 cranks to see one failure. Lower = more realistic for a nightmare intermittent, but risks being unsolvable inside the message limit. |
| crank signature = `crank_no_start` | — | `propagation.py` | I chose this to match `bus_off`. **Is cranks-but-won't-fire the right symptom for a flaky ECU/CAN node, or should it sometimes be `no_click`?** I am guessing at the failure physics of a CAN node here and would rather you told me. |

---

## 2. `hard_compound_battery_and_ground` (tier HARD, seed 3002)

**Two genuine faults.** PRIMARY = `ground_strap:corroded` (0.7 Ω). SECONDARY = `battery:weak`
(`terminal_drop_v` 1.6). The battery is **not** a red herring — it really is bad and really must
be replaced.

**Why the ground strap is the PRIMARY and the battery the SECONDARY:** the battery is the
obvious find and the strap is the subtle one. A tech who stops at the battery leaves the car
broken. Making the subtle fault the primary is what puts the points where the skill is.

**The tell a tech should see — BOTH faults independently visible:**

1. **Battery is genuinely bad:** ~11.0 V resting (*worse* than the 11.8 V red-herring bait in
   `medium_ground_red_herring_battery`, so the two are not confusable) and it **fails a load
   test** at ~9.2 V cranking — far below the 11.3 V that the *innocent* battery holds in the
   ground-fault scenarios. The load test is what separates a real weak battery from the bait.
2. **Ground is genuinely bad:** ~1.78 V dropped across the strap under crank (a healthy strap
   drops < 0.2 V), and ~0 V at rest — load-only, as always.
3. **Still localizable:** the positive feed stays clean (0.17 V), so the drop belongs to the
   ground junction, not the supply side.
4. **Neither repair alone fixes the car.** Replace only the battery → still `slow_crank`.
   Replace only the strap → still `slow_crank`. Both → `starts`. (Asserted in sanity_check and
   in tests.) This is what forces the agent to actually resolve a compound fault rather than
   fix the easy half and declare victory.

**What the model produces (paste-from-`sanity_check.py`):**

```
=== hard_compound_battery_and_ground ===
  state     |  battery_v |  ground_drop |  stud_feed
  --------------------------------------------------
  key_off   |      10.97 |        -0.03 |      -0.03
  key_on    |      10.77 |        -0.06 |       0.07
  cranking  |       9.22 |        -1.78 |       0.17

  [PASS] universal
  [PASS] scenario:compound
  [PASS] running-charging
```

DTCs: `P0562`, `B1318` (both battery-flavored codes — extra bait toward a battery-only answer).

**Constants awaiting your sign-off:**

| Constant | Value | Where | My doubt |
|---|---|---|---|
| `terminal_drop_v` (battery:weak) | 1.6 V | `scenarios.py` | Gives an 11.0 V resting battery that still cranks (slowly) at 9.2 V. **Is an 11.0 V resting battery plausibly still crankable, or is that already a shorted-cell / `dead` battery?** This is my single biggest doubt on this scenario. |
| `added_resistance_ohms` (ground) | 0.7 Ω | `scenarios.py` | Deliberately *milder* than the 1.1/1.2 Ω single-fault scenarios. See §3 for why — it is not an arbitrary choice, and I want you to check the reasoning, not just the number. |
| `terminal_drop_v` default | 0.6 V | `components.py` | Preserves existing behavior exactly. Only flagged because it is now a named constant instead of a magic number. |

---

## 3. The interaction you told me not to guess about — and what I did instead

You warned me: *a weak battery sags more, which lowers current, which lowers the ground drop.*
That is exactly right, and it is the reason the naive version of this scenario does not work.

**The trap I walked into first.** With the ground strap at the existing 1.1 Ω, the model's
current-recovery term (`GROUND_CURRENT_RECOVERY = 0.6`) props the battery back up by
`0.6 × 2.75 = 1.65 V` under crank. Superimposed on a weak battery, the cranking terminal
voltage comes out at **10.85 V** — i.e. **the "genuinely weak" battery would PASS a load test**
(> 9.6 V) and read innocent. The scenario would have been a lie: a battery I declared weak, that
a tech's load test would clear. I did not ship that.

**What I did instead — and this is a design choice you should overrule if you disagree.** I
lowered the strap to 0.7 Ω. A milder ground fault chokes cranking current *less*, which leaves
the weak battery's own sag visible. That is the physically-motivated direction (less series R →
more current → more sag), and it lands both tells cleanly on the right side of the thresholds:
battery 9.22 V (fails the < 9.6 V load test), ground drop 1.78 V (≫ the < 0.2 V a healthy strap
drops). **The alternative was to keep 1.1 Ω and make the battery much deader (~10.4 V resting) to
out-sag the recovery — which I think produces a less believable car.** Your call.

**What the model does NOT do — stated plainly:** there is **no cross-fault current coupling**.
The ground drop is `R × GROUND_DROP_PER_OHM`, full stop; it does not shrink when the weak battery
reduces cranking current. I could have invented a coupling coefficient to model that. **I
refused, because I would have been making the number up.** Here is the size of the error I am
knowingly shipping, computed rather than guessed:

> Series-circuit estimate, using the model's own stated constants (OCV 12.6, healthy crank
> terminal 9.8 → R_int ≈ 15.6 mΩ, total crank circuit ≈ 70 mΩ). The physical strap resistance
> that reproduces a 1.75 V drop with a *healthy* battery is ≈ 11.3 mΩ. Re-solving that same
> circuit with the weak battery's 11.0 V open-circuit voltage gives **ground drop ≈ 1.53 V**
> (model says 1.78) and **cranking terminal ≈ 8.9 V** (model says 9.22).

So the model is ~0.25 V optimistic on the ground drop and ~0.3 V optimistic on the battery.
**Both errors are small and both point the same way: the true readings would be slightly *more*
damning, not less.** Every diagnostic threshold survives either way (drop still ≫ 0.2 V; battery
still < 9.6 V), so I believe the scenario is qualitatively sound — but **the exact numbers are a
modeling artifact, not physics, and you should treat them as such.**

---

## 4. OPEN QUESTION about the EXISTING model (found while doing this; affects signed-off scenarios)

I did not go looking for this and I have not changed anything because of it. **`GROUND_CURRENT_RECOVERY = 0.6`
does not appear to be consistent with a series-circuit solve of the model's own constants.**

The arithmetic, so you can check me:

- Healthy crank: OCV 12.6 → terminal 9.8 V, so sag = 2.8 V. At ~180 A that is R_int ≈ 15.6 mΩ,
  total circuit ≈ 70 mΩ.
- `medium_corroded_ground` (1.1 Ω knob → 2.75 V drop). Solve the series circuit for the strap
  resistance that actually produces a 2.75 V drop: R_g ≈ 19.5 mΩ, giving I ≈ 141 A.
- Battery sag at 141 A = 141 × 15.6 mΩ ≈ **2.2 V → terminal ≈ 10.4 V**.
- **The model produces 11.45 V** — about **1.05 V higher**. For the battery to recover the
  1.65 V the model gives it, cranking current would have to fall to ~41% of nominal, and at that
  current the 2.75 V drop implies a strap resistance that then contradicts the current. It does
  not close.

**Why I am telling you rather than "fixing" it:** the model's *direction* is right (series
resistance chokes current, so the battery sags **less** — the battery legitimately reads
innocent), and the red-herring design survives under either number (10.4 V is still a passing
load test, > 9.6 V). Only the magnitude is in question. But two things follow that you should
decide on:

- The `BATTERY_HOLDS = 11.3 V` floor in `sanity_check.py` and the "battery holds ≥ ~11.3 V"
  invariant in CLAUDE.md are **specific to the current calibration**. A series-consistent model
  would put that floor nearer 10.4 V.
- If you change `GROUND_CURRENT_RECOVERY`, **the compound scenario's numbers move with it**, and
  I would need to re-pick `terminal_drop_v`.

You verified the existing scenarios by play and I did not, so you may simply know that a real
corroded-ground car does hold up high under crank. If so, say so and I will write the
justification into DOMAIN_TRUTH.md and drop this. **I am flagging it because "plausible but
internally inconsistent" is exactly the failure mode this product exists to prevent, and I would
rather look wrong than let it sit unmentioned.**

---

## 5. Compound scoring rule (my choice — justify or overrule)

A scenario may now declare `secondary_fault`. The rule, in `grader.py`:

**The 60-point root-cause budget SPLITS; it does not grow.**

| | Component **and** mode | Component only | Not named |
|---|---|---|---|
| **PRIMARY** (`root_cause`) | 45 | 22.5 | 0 |
| **SECONDARY** (`secondary_fault`) | 15 | 7.5 | 0 |

- **Naming both = 60/60** — exactly what a correct single-fault answer earns. Compound episodes
  stay on the same 0–100 scale; no separate ladder.
- **Full root-cause credit is unreachable without the PRIMARY.** Naming only the obvious battery
  caps root credit at **15/60** — real partial credit, but it can never be a pass. That is the
  rule you asked for.
- **Replacing the secondary is NOT a wrong part.** It really is bad. A real tech who fixes both
  must not be penalized for the second repair; `score_parts_discipline` now takes an
  `also_faulty` set.
- **Word order does not matter.** Compound answers are scored by *mention*, not by
  earliest-mention (which is what the single-fault parser does). Otherwise a fully correct
  "weak battery AND corroded ground strap" would score only the battery, because the model
  happened to write it first — the same class of bug as the `engine-to-battery` compound hijack
  that cost sonnet 60 points. The two components have disjoint mode vocabularies
  (weak/dead vs corroded/broken), so the modes cannot cross-credit.
- **Resolution is unchanged** (primary replaced + verified start). It needs no special case: the
  physics already guarantees the car will not start until **both** parts are replaced, so the
  existing rule forces the full repair on its own.

**Known limitation, documented not fixed:** mention-based scoring means a diagnosis that names a
component only to *exonerate* it would still be credited. In a compound scenario both named
components really are faulty, so exoneration prose is simply a wrong answer — the loophole has
nothing to grab. It would matter if a future compound scenario also carried a red herring.

---

## 6. Smoke eval — haiku-4-5, uncoached, 2 scenarios x 3 epochs (6 episodes, hard cap)

`results-hardtier/` is gitignored, so the table lives here.

| model | scenario | k | mean | min | root | parts | cost | pass^k | root-ok | verified-fix | measured-first |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| claude-haiku-4-5 | hard_compound_battery_and_ground | 3 | 68.5 | 45.8 | 38 | 25 | 6.0 | fail | 0/3 | 3/3 | 3/3 |
| claude-haiku-4-5 | hard_intermittent_ecu_can | 3 | 0.0 | 0.0 | 0 | 14 | -18.1 | fail | 0/3 | 1/3 | 3/3 |

Per-episode:

| scenario | epoch | total | root | wrong parts | diagnosis (truncated) |
|---|---:|---:|---:|---|---|
| compound | 1 | 85.8 | 52.5 | — | "Battery failed (voltage too low) and ground_strap corroded" |
| compound | 2 | 45.8 | 15 | — | "battery failed; weakened by age..." |
| compound | 3 | 73.9 | 45 | — | "ground_strap corroded (poor connection causing slow crank)" |
| intermittent | 1 | 0.0 | 0 | battery, ignition_switch | (never diagnosed) |
| intermittent | 2 | 0.0 | 0 | alternator | "alternator failed; loss of charging voltage" |
| intermittent | 3 | 0.0 | 0 | starter_relay | (never diagnosed) |

**Reading of the smoke (mine, for your review):**

- **The compound grading rule behaves exactly as designed on real model prose.** Epoch 1 named
  both (45 + 7.5 = 52.5: primary full, secondary component-only because it said "failed" not
  "weak"). Epoch 2 found only the battery → 15/60, partial, no pass. Epoch 3 found only the
  strap → 45/60. Three episodes, three different points on the rubric, all correct.
- **The intermittent scenario is currently a wall: 0.0 / 0.0 / 0.0.** haiku never suspects the
  ECU; it swaps a part, gets a lucky start (65% of cranks succeed), declares victory, and the
  cost-efficiency debit does the rest. One episode did replace the ECU and verify a start but
  still named the wrong part in its answer, so root credit was 0 — the grader is right, but
  **a 0.0 floor across the board means this scenario has no discriminating power at haiku
  level.** Whether that is "correctly hard" or "unfairly hard" is a judgment call I want you to
  make with a frontier model before this goes anywhere near a published table.

---

## 7. What I need from you, concretely

- [ ] **Play `hard_compound_battery_and_ground`.** Is an 11.0 V resting battery that still
      slow-cranks at 9.2 V a believable car? (Biggest single doubt.)
- [ ] Is a 1.78 V drop across a ground strap under crank enough to characterize, given you
      previously caught a "drop too small to characterize" bug?
- [ ] Ratify or overrule the **0.7 Ω** strap choice (§3) — milder ground so the weak battery
      stays visible, vs. keeping 1.1 Ω and making the battery much deader.
- [ ] **Rule on §4** (`GROUND_CURRENT_RECOVERY` vs a series solve). This one affects the
      **already-signed-off** scenarios, not just mine.
- [ ] **Play `hard_intermittent_ecu_can`.** Is `crank_no_start` the right manifestation for a
      flaky CAN node? Is 0.35 the right rate?
- [ ] Ratify or overrule the **45/15 compound split** and the mention-based (not
      earliest-mention) parsing for compound answers (§5).
- [ ] Decide whether the intermittent scenario is discriminating or merely brutal (§6).

**Until every box above is checked: do not merge, and do not let these two scenarios into any
published results table.** `DOMAIN_TRUTH.md` has deliberately **not** been updated — I did not
want hard-tier physics sitting in a document whose sign-off block says you approved it.
