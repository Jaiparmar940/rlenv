# Leak + integrity audit

- Date: 2026-07-13 (re-run after the corpus grew to k=5). Supersedes the 2026-07-12 audit of the retired 45-transcript corpus (same method; that corpus predated the series-consistency physics recalibration and the hard tier).
- Commits: episodes produced at `8debf0e`–`bcbabea` (branch `main`). No `src/` (environment, grader, prompt) change exists between those commits — the only differences are scripts/report files — so all 225 episodes ran identical environment code: series-derived `GROUND_CURRENT_RECOVERY` (0.222), merged hard tier, `low_capacity` grader vocabulary.
- Interpreter: `.venv/Scripts/python.exe`
- Corpus: `results/transcripts/*.md` — **225 files (9 models x 5 scenarios x 5 epochs)**. All `prompt-variant: uncoached`. Epochs 1-3 were run first; epochs 4-5 were added in a second pass and relabeled from a separate invocation (llama-8b's first +2-epoch attempt hit transient provider `CancelledError`s and was fully replaced by a clean retry — no partially-errored log contributes rows). Along the way three model ids were casualties, none of them scoring: `gemini-2.5-flash` is use-blocked for new API keys, `qwen-2.5-3b` was delisted from OpenRouter, `llama-3.2-3b` has no tool-capable OpenRouter endpoint. Dead logs were deleted; `results/logs/` holds exactly the eighteen `.eval` logs (9 models x 2 passes) behind the table.
- Scope: read-only audit. No grader / world / scenario / prompt source was modified.

| # | Item | Verdict |
|---|------|---------|
| 1 | Leakage of ground truth into agent-visible text | **PASS** |
| 2 | Agent system prompt is uncoached, single revision | **PASS** |
| 3 | Sanity check + test suite | **PASS** |
| 4 | Environment determinism | **PASS** |

---

## Item 1 — LEAKAGE: **PASS**

### Method

Transcripts are rendered markdown with `### [n] SYSTEM` / `USER` / `ASSISTANT` / `TOOL RESULT (fn)` section headers (message numbers added 2026-07-13). A parser split every file into sections and scanned only text the environment authored and the agent could see:

- **META (excluded by design)** — the title, `prompt-variant`, and `**Score:**` json block before the first section header. Written by `scripts/run_evals.py` *after* the episode from the grader's output; it contains `true_component` / `true_mode` / `root_cause` per file and was never in the model's context. A reviewer grepping naively will hit it — that is a rendering artifact, not a leak.
- **AGENT-AUTHORED (exempt)** — `### ASSISTANT` sections and `### TOOL RESULT (finish)`. The finish result is a verbatim echo of the agent's own `finish(answer=...)` string; the environment adds no information, and it is the last message of the episode.
- **ENVIRONMENT-AUTHORED, AGENT-VISIBLE (the leak surface)** — `SYSTEM`, `USER`, and every `TOOL RESULT` except `finish`.

Patterns searched (case-insensitive, word-boundary): all 16 `FailureMode` enum values in underscore and space form; `red_herring` / `red herring`, `root_cause` / `root cause`, `secondary_fault`, `ground truth`, `injected`, `severity`, `manifest*`, `sulfat*`, `corrosion`, `seed`, `scenario`.

### Result on the leak surface

Every hit across all 225 transcripts, exhaustively classified:

| n | Section | Match | Classification |
|---|---------|-------|----------------|
| 225 | `SYSTEM` | `blown` | **Designed.** The `finish()` format example `(e.g. "fusible_link blown")`. `fusible_link blown` is not the root cause of any of the five scenarios; appears once per transcript. |
| 225 | `USER` | `root cause` | **Designed.** The task instruction *"Diagnose the root cause and repair the vehicle."* Task definition, identical in every episode; carries no per-scenario signal. |
| 45 | `USER` | `weak` | **Designed bait.** The red-herring complaint *"Shop said my battery is 'a little weak'"* (all `medium_ground_red_herring_battery` episodes). This is the trap the scenario exists to set. |
| 36 | `TOOL RESULT (visual_inspect)` | `corroded` / `sulfation` | **Designed.** Dead-battery visual: *"Terminals corroded; slight sulfation odor."* A physical observation; does not name the true mode (`dead`). |
| 35 | `TOOL RESULT (visual_inspect)` | `corrosion` | **Designed.** Weak/aged-battery visual: *"Terminal corrosion light; case looks aged."* Same class. |
| 155 | `TOOL RESULT (finish)` | various | **Agent echo.** The agent's own diagnosis text reflected back verbatim at episode end. |
| 0 | — | anything else | **No unexplained hits.** Attribution by tool function confirms zero banned-vocabulary hits in any non-`finish` tool result beyond the two designed visual strings above. |

Notable negatives, checked explicitly on this corpus:

- The corroded-ground-strap visual emits *"Strap end greenish; could be overlooked."* / *"Strap looks normal at a glance."* — never the string `corroded`, in any of the 90 ground/compound episodes.
- The hard-tier surfaces are clean: `can_status` reads return only `ok` / `degraded` values, intermittent cranks return only the standard `crank_no_start` / `starts` strings, and no compound-scenario tool output names either fault. Zero hits.
- No tool result contains a component health verdict, fault name, or explanation — instrument readings only.

**Verdict: PASS.** Zero ground-truth leakage in agent-visible, environment-authored text across all 225 transcripts.

---

## Item 2 — AGENT SYSTEM PROMPT: **PASS**

The sha256 of the `### SYSTEM` section is **identical across all 225 transcripts** (one distinct hash: `d907615d10d4…`), and matches `PROMPTS["uncoached"]` in `src/nostart/prompts.py` at this commit — the same prompt text audited verbatim in the 2026-07-12 audit (role, tool reference, job definition, cost one-liner, finish format only; no strategy, no grader rules, no trap or topology hints; the `finish()` example names a fault that is no scenario's root cause). The prompt is unchanged since commit `76b88f6`.

The single-revision provenance problem that invalidated the first published table (36 frontier transcripts under an older prompt than haiku's 9) does not recur here: one hash, 225 files.

**Verdict: PASS.**

---

## Item 3 — SANITY CHECK + TESTS: **PASS**

`.venv/Scripts/python.exe scripts/sanity_check.py` — **exit 0**, all five scenarios: `universal` (load sag, resting monotonicity), scenario-specific thresholds (post-recalibration: innocent battery ≥ 10.3 V under crank — a passing load test; compound battery < 9.6 V — a failing one), `localization`, `scenario:compound` (neither repair alone starts the car), `scenario:intermittent` (deterministic manifestation, clean-scan-does-not-exonerate), and `running-charging`.

```
=== medium_corroded_ground ===          cranking  10.42 | -2.74 | 0.21
=== medium_ground_red_herring_battery ===  cranking  10.49 | -2.98 | 0.22
=== hard_compound_battery_and_ground ===   cranking   8.56 | -1.78 | 0.17
ALL CHECKS PASSED
```

`.venv/Scripts/python.exe -m pytest -q` — **105 passed** (includes the hard-tier suite and the pinned real-transcript parser regressions).

**Verdict: PASS.**

---

## Item 4 — DETERMINISM: **PASS**

`scripts/check_determinism.py` (unchanged method: build each world twice, replay a fixed 22-action script exercising every stochastic surface and state transition, diff the full serialized observation streams including raised errors):

```
  [PASS] easy_dead_battery              287-line stream identical, sha256[:16] = ae5222177c9f3d73
  [PASS] medium_corroded_ground         278-line stream identical, sha256[:16] = 66e3afa3397964c7
  [PASS] medium_ground_red_herring_battery  278-line stream identical, sha256[:16] = ce0a5258a73593da
  [PASS] hard_intermittent_ecu_can      278-line stream identical, sha256[:16] = a24e3c9e89145afd
  [PASS] hard_compound_battery_and_ground   282-line stream identical, sha256[:16] = ae9ad49140f0c11e
DETERMINISM OK - 5 scenarios reproduce exactly
```

Byte-identical across separate processes. The intermittent scenario's manifestation hash (seed, probe kind, probe index) is covered by the replay: identical crank/scan sequences both builds.

**Verdict: PASS.** Same scenario + same action sequence ⇒ identical observations, errors, and costs.

---

## Summary for the founder

Nothing in this audit blocks publication on correctness grounds: no leakage (now including the never-before-audited hard-tier surfaces), one prompt revision across the whole corpus, physics checks and 105 tests green, environment reproducible on all five scenarios.

Two notes worth a line in the README, unchanged from the previous audit:

- The `**Score:**` json header atop each transcript contains `true_component` / `true_mode` / `root_cause`. It is written after the episode and was never in the model's context — say so, because a reviewer grepping the transcripts will find it.
- `visual_inspect` on a battery returns corrosion language and the red-herring complaint says "a little weak". Both designed; both will show up in a naive grep.
