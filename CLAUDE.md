# CLAUDE.md — no-start-env

## What this is

An agentic RL environment + eval: a simulated vehicle with electrical no-start/charging faults that an LLM agent diagnoses using realistic tools, scored by a cheat-resistant grader. Built on **Inspect (inspect-ai)** so labs can run it directly. This repo is the founder's first public artifact for a company selling physical-systems environments/evals to AI labs and robotics companies — it publishes **Monday**, with a benchmark writeup showing where frontier models fail physical diagnosis. Quality bar: a lab eval engineer reads this code cold and takes the author seriously.

## Division of labor (important)

- **Cursor** has been executing phased build prompts. Check `git status`/`git log` before touching anything — do not duplicate or clobber in-flight Cursor work. If a file was just modified, ask before rewriting it.
- **The human (Jaivir) is the domain verifier.** He has caught four physics bugs that passed the automated test suite (load-sag inversion; downstream node reading above upstream; red-herring battery drifting into genuinely-weak territory; ground-fault drop too small to characterize). When physics is uncertain, FLAG IT — never guess plausible-looking numbers. Plausible-but-wrong is the failure mode this whole product exists to prevent.
- **Claude Code (you):** implementation, tests, refactors, transcript analysis, writeup drafting. Stop at phase checkpoints for human sign-off.

## Architecture

- **Resistance-network model:** the circuit is nodes connected by resistances with a battery source. Faults = bump ONE resistance (or battery internal params). Engine states = current draws (key_off ≈ 0 A, key_on small, cranking ~150–200 A). All voltages COMPUTE via V = I×R. **Never hand-author output voltages** — change R or I so correct readings emerge. ~15 physical constants generate everything; they live in domain/ and are documented in DOMAIN_TRUTH.md.
- **Nodes:** battery_positive, battery_negative (reference, 0 V), engine_block, starter_stud, alt_output, chassis.
- **Two-point measurement:** `measure_voltage(point_a, point_b, engine_state)` returns V(a)−V(b) + seeded noise (±0.05 V). Invalid node or state RAISES. Sign flips when args swap.
- **Tools:** scan_dtcs, read_pid, measure_voltage, visual_inspect, replace_part, attempt_start, finish(diagnosis). Tool outputs are instrument readings ONLY — no explanations, and NOTHING that leaks ground truth (fault names, component health).
- **Ground truth** lives in `src/nostart/domain/` and `World._active_faults`; never serialized into observations, prompts, or tool outputs.
- **Determinism:** every scenario seeded; identical runs → identical observations and scores.

## Physics invariants (encode the four caught bugs — never violate)

1. Cranking voltage < resting voltage at every point (load sag, never inverted).
2. No downstream node exceeds an upstream node at rest (resting monotonicity down the supply path).
3. Red herrings are RESTING-ONLY overrides and suppress the whole resting supply path uniformly.
4. In ground-fault scenarios the fault must be uniquely localizable: large drop across the ground path (battery_negative→engine_block) under cranking ONLY, small drop across the positive feed (battery_positive→starter_stud), battery itself holds (innocent).
5. A red-herring battery must read tempting at rest (~11.8 V) but hold ≥ ~11.3 V under cranking — bait, not a co-fault.

## Scenarios (Phase 1 set)

- `easy_dead_battery` — battery ≈ 2.1 V all states, no_click, ground drop ≈ 0. VERIFIED by play.
- `medium_corroded_ground` — good battery; ground drop large only under cranking; slow_crank.
- `medium_ground_red_herring_battery` — resting path suppressed to ~11.8 V (bait); cranking: battery holds, ground drop is the tell.

## Current state & task queue (in order)

1. **PENDING — ground-drop magnitude fix** (prompt: cursor-fix-ground-drop-magnitude.md, may already be partially applied by Cursor — check first). Targets at cranking for both ground scenarios: battery (pos→neg) ≥ ~11.3 V; ground drop (neg→engine_block) ≥ ~2.5 V; positive feed (pos→stud) ≤ ~0.5 V. Achieve by adjusting resistances/current, not authored voltages.
2. **`scripts/sanity_check.py` green** — standalone checker (no pytest/grader/Inspect imports); asserts the invariants above incl. the localization property; exits non-zero on failure. Build it if Cursor hasn't.
3. **Phase 2 — grader.py + tests:** score 0–100 (root cause 60 / parts discipline 25, −8 per wrong part / cost efficiency 15 vs expert baseline, $2 ≈ 1 min). Wrong-part penalty ALSO debits the total (not just the clamped bucket) so a measure-once parts-cannon can't ride root-cause points past 50. Anti-cheat: symptom masking ≠ success (grader reads true world state); finish() with no measurements caps at 40. `test_grader.py` must defeat four adversarial agents: parts-cannon, measured-parts-cannon, lucky-guesser, symptom-masker. CHECKPOINT: run them in front of the human — DONE 2026-07-10 (scores 29.3 / 29.3 / 40 / 15.9, all < 50).
4. **Phase 3 — task.py (Inspect) + scripts/run_evals.py:** run ≥2 real model APIs × 3 scenarios → deterministic markdown results table + full transcripts. CHECKPOINT: human reads transcripts, tags failure modes.
5. **Publish prep:** README (quickstart, results table, failure-mode taxonomy, honest known-gaps/limitations section, v0.2 notes: direct two-point drop-test framing, more scenarios), repo hygiene, human baseline row in the table.

## Definition of done (v0.1)

`pip install -e . && python scripts/sanity_check.py && python scripts/run_evals.py --scenarios all` → all checks pass, scored table generates, tests green on a clean clone. Public Monday.

## Do not

- Hand-author voltages; leak ground truth into any observation; break determinism.
- Add RL training code, web UI, Docker, or CI in v0.1.
- Mark any phase done without its human checkpoint.
- Silently "fix" physics you're unsure of — surface it as a question with your best guess and the reason for doubt.
