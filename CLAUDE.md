# CLAUDE.md — no-start-env

## What this is

An agentic RL environment + eval: a simulated vehicle with electrical no-start/charging faults that an LLM agent diagnoses using realistic tools, scored by a cheat-resistant grader. Built on **Inspect (inspect-ai)** so labs can run it directly. This repo is the founder's first public artifact for a company selling physical-systems environments/evals to AI labs and robotics companies — it publishes **Monday**, with a benchmark writeup showing where frontier models fail physical diagnosis. Quality bar: a lab eval engineer reads this code cold and takes the author seriously.

## Division of labor (important)

- **Cursor** executed the initial phased build (Phase 1 skeleton). Check `git status`/`git log` before touching anything — do not duplicate or clobber in-flight work from another tool. If a file was just modified, ask before rewriting it.
- **The human (Jaivir) is the domain verifier.** He has caught four physics bugs that passed the automated test suite (load-sag inversion; downstream node reading above upstream; red-herring battery drifting into genuinely-weak territory; ground-fault drop too small to characterize). When physics is uncertain, FLAG IT — never guess plausible-looking numbers. Plausible-but-wrong is the failure mode this whole product exists to prevent.
- **Claude Code (you):** implementation, tests, refactors, transcript analysis, writeup drafting. Stop at phase checkpoints for human sign-off. **Keep this file's "Current state" section up to date as work lands, and commit it with the change it describes.**

## Dev environment (this machine)

- Run everything via `.venv/bin/python` (uv-managed CPython 3.12; system python3 is 3.9 and unusable). `uv pip install -e ".[dev]"` after a fresh clone.
- Provider keys live in gitignored `.env` (template: `.env.example`); `scripts/run_evals.py` loads it.
- Mobile play UI: `scripts/webapp.py` (serves :8642; expose with `cloudflared tunnel --url http://localhost:8642`). Committed 2026-07-11 by Jaivir's call as a dev/verification tool — may be removed before/after publish.

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
- `medium_corroded_ground` (1.1 Ω strap) — good battery; cranking: battery ~11.45 V, ground drop ~2.75 V, feed ~0.2 V; slow_crank. VERIFIED by play.
- `medium_ground_red_herring_battery` (1.2 Ω strap) — resting path suppressed to ~11.8 V (bait, cleared if battery replaced); cranking: battery holds ~11.6 V, ground drop ~3.0 V is the tell. VERIFIED by play.

## Current state (updated 2026-07-11)

**DONE:**

1. **Phase 1 — environment + scenarios.** Ground-drop magnitude fix applied to spec (scenario resistances 1.1/1.2 Ω, GROUND_CURRENT_RECOVERY 0.6); red herring clears when its component (battery) is replaced. DOMAIN_TRUTH.md signed off by Jaivir 2026-07-10.
2. **`scripts/sanity_check.py` green**, thresholds pinned to the spec targets (battery ≥ 11.3, drop ≥ 2.5, feed ≤ 0.5) so a too-soft fix cannot pass.
3. **Phase 2 — grader.py + tests:** score 0–100 (root cause 60 / parts discipline 25, −8 per wrong part / cost efficiency 15 vs expert baseline, $2 ≈ 1 min). Wrong-part penalty ALSO debits the total so a measure-once parts-cannon can't ride root-cause points past 50. Anti-cheat: symptom masking ≠ success; finish() with no measurements caps at 40. Four adversarial agents defeated. CHECKPOINT DONE 2026-07-10 (29.3 / 29.3 / 40 / 15.9, all < 50; expert 100).
4. **Phase 3 — src/nostart/task.py (Inspect) + scripts/run_evals.py built and run** (3 models × 3 scenarios × 3 epochs, 2026-07-10). Real prose broke the diagnosis parser twice (length-based component match; enum-order mode match hijacked by red-herring exoneration wording) — both fixed with positional + component-valid-mode matching, regression-tested against the actual model answers. Current means: claude-sonnet-5 99.6, claude-fable-5 94.1, gpt-5.5 77.0.

**OPEN — decisions on Jaivir (block the final published table):**

- **Scores look inflated; causes identified:** (a) ~~system prompt topology hint~~ — RESOLVED on branch `calibrate/neutral-prompt-grok` (2026-07-11): hint removed, rerun gives sonnet 96.7 / fable 88.7 / gpt 75.2 (−2.9/−5.4/−1.8) — models infer topology by probing, so the hint was worth little; (b) rubric floor is high (component-only 30 + clean-hands 25 + terse 15 = 70); (c) visual_inspect reveals strap corrosion 40% of the time — electrical localization should be the only reliable tell?; (d) gpt-5.5's gap is pure mode vocabulary ("internally failed/shorted" vs dead, "high resistance" vs corroded) — accepting synonyms ≈ 97.
- **New failure mode (neutral run, fable easy e3, scored 26.6):** first wrong-component diagnosis in 54 episodes — model replaced the drained battery, then tried to VERIFY CHARGING (expert move for "fine yesterday, dead today"), read alt_output 12.4 V at key_on and called the alternator dead. Part model overreach (treated key_on as engine-running), part environment gap: there is NO running state in which a healthy alternator shows ~14.4 V. v0.2: add `running` engine state with charging physics.
- **Grok support wired** (same branch): Inspect's native provider, `grok/<model>` ids, XAI_API_KEY in .env.example — needs a key in .env to run.
- **Expert-baseline semantics inconsistent:** easy is diagnose-only (15 min/$0) while ground baselines include repair — models that repair+verify on easy lose ~13 cost points.
- **Phase 3 CHECKPOINT:** Jaivir reads `results/transcripts/`, tags failure modes. Banked so far from human play: supply-referenced readings hide ground faults; wrong ground reference frames an innocent starter.

**THEN — publish prep:** README (quickstart, results table, failure-mode taxonomy, honest known-gaps: feed drop not current-scaled, single-vehicle ground topology assumption, mode-vocabulary strictness; v0.2 notes: harder scenario set — intermittents, co-faults, more scenarios), human baseline row, repo hygiene. Publish Monday 2026-07-13.

## Definition of done (v0.1)

`pip install -e . && python scripts/sanity_check.py && python scripts/run_evals.py --scenarios all` → all checks pass, scored table generates, tests green on a clean clone. Public Monday.

## Do not

- Hand-author voltages; leak ground truth into any observation; break determinism.
- Add RL training code, Docker, or CI in v0.1. (Web-UI ban lifted 2026-07-11: `scripts/webapp.py` is committed as a dev/play tool; candidate for removal later.)
- Mark any phase done without its human checkpoint.
- Silently "fix" physics you're unsure of — surface it as a question with your best guess and the reason for doubt.
