# ORS vs Inspect parity diagnosis (branch `feat/openreward-serving`)

Run 2026-07-20. Question: is the haiku side-by-side gap (red-herring 0.0 vs
26.2, compound 0.0 vs 77.5) variance, or does the ORS serving path change what
the model experiences or how it is graded?

## FINAL VERDICT: DIVERGENCE FOUND → FIXED → PARITY CONFIRMED

Phases 1–2 found real context/harness divergences (below), all fixed on the
branch; Phase 3 (haiku × 5 epochs × both scenarios × both pipelines) then
showed **no systematic ORS inflation** — ORS came out *lower* on red-herring
(mean 6.3 vs 34.3) and statistically indistinguishable on compound (58.0 vs
61.0), with per-episode distributions bimodal and overlapping (details in the
Phase 3 section). The original 26.2/77.5 anomaly was the harness divergence
plus variance, and no longer reproduces.

## Phase 1–2 diagnosis (pre-fix): DIVERGENCE FOUND — context and harness, not grading

The grader and prompts are parity-clean. The divergence is real and lives in
two places: (1) the **model-visible tool specifications** served by the ORS
adapter differ from what Inspect serializes, and (2) the **Part-B validation
harness loop** does not replicate Inspect `basic_agent` semantics (termination,
message accounting, max_tokens, tool-result framing). Either alone could shift
model behavior; neither touches scoring of a given world state. Fixes proposed
at the end; **awaiting go before implementing. Phase 3 not run.**

Live replication during capture: compound scored **5.4 (Inspect) vs 59.0
(ORS)** in this session's episodes — the gap is not a one-off.

## Method

One haiku episode per pipeline per scenario (4 episodes total; well under
budget). Wire-level capture:

- **Inspect:** raw Anthropic API request payloads from the eval log's
  `ModelEvent.call` records (`resolve_attachments=True`) — this is the JSON
  Inspect's provider put on the wire.
- **ORS:** the exact `client.messages.create(**kwargs)` payloads of the
  validation loop (the SDK serializes these 1:1), logged before each call.

Artifacts: `<scenario>__{inspect,ors}.json`, `diff_red_herring.txt`,
`diff_compound.txt`, produced by `capture.py` / `analyze.py` in this directory.

## Phase 1 — context diff, every difference found

### Prompt placement — CLEAN

- System prompt: system role in both; text **byte-identical** in both
  scenarios. Inspect sends it as a content-block list with
  `cache_control: ephemeral` (server-side prompt caching, model-invisible);
  ORS loop sends a plain string. No text difference.
- First user message: **byte-identical** in both scenarios.

### Task-spec exposure — CLEAN

No part of the ORS task spec reaches the model context: `ns-0`, `tier`,
`task_id`, `task_spec` appear nowhere in any wire message (checked across all
captured ORS calls, both scenarios).

### Tool schemas — DIVERGENT (model-visible, every tool)

Names match (7 tools, `finish` included; the hidden `@terminal` tool does
**not** appear in the model-visible list — confirmed on the wire). But:

1. **"Returns" sections:** Inspect's docstring parser strips the `Returns:`
   section from every tool description. The ORS adapter inlined that text, so
   every ORS description carries an extra paragraph (e.g. `attempt_start` adds
   "Returns JSON with the crank result (e.g. no_click, slow_crank, starts)." —
   this literally tells the model the possible crank results in a place the
   published run did not).
2. **`finish` description:** Inspect: single line "Submit your final
   diagnosis. BEGIN your answer ... may follow." ORS: hard-wrapped across 3
   lines and appends "This ends the episode."
3. **`finish.answer` param description:** Inspect: "Submitted answer". ORS:
   the full BEGIN-your-answer text duplicated into the param.
4. **Param-description whitespace:** Inspect preserves the docstring line
   breaks ("One of: battery_positive,\nbattery_negative, ..."); ORS collapsed
   them to single lines.
5. **Schema shape:** Inspect emits `"additionalProperties": false` on every
   schema and `"required": []` on no-arg tools; the Pydantic-generated ORS
   schemas omit both.
6. SDK-level, model-invisible: ORS tools carry `type: "custom"` (Inspect omits
   the field); Inspect adds `cache_control` to the last tool and sends
   `tool_choice: auto` explicitly (the default).

### Message framing — DIVERGENT

- **Tool results:** Inspect sends `content` as a list of text blocks plus
  `is_error: false`; the ORS loop sends a bare string and no `is_error`
  (semantically equivalent for the API, but not byte-equal).
- **Tool errors:** Inspect sends invalid tool calls back as
  `is_error: true` with the bare error message
  (inspect_ai anthropic provider, `_providers/anthropic.py`). The ORS
  adapter returns a *normal* result with an `"Error: "` text prefix — the
  model sees error signaling differently.

### Generation config — DIVERGENT

`max_tokens`: Inspect 32000 (provider default for haiku) vs ORS loop 2048.
Truncation risk on long haiku turns; behavior-relevant. Temperature: unset in
both (provider default).

### Termination — DIVERGENT (the big one)

- **Inspect `basic_agent`:** a plain assistant message (no tool call) does NOT
  end the episode — it appends "Please proceed to the next step using your
  best judgement." and loops. Episodes end only on `finish()` or the
  50-message limit (limit counts *every* sample message: system, user,
  assistant, and each tool message individually).
- **ORS validation loop:** ended the episode on the FIRST plain assistant
  message and graded it via the terminal fallback; message cap counted a
  different unit (its own list, tool-result batches as one message, no
  system).

Consequence: under Inspect, a narrating model gets pushed back to work and
keeps accruing wrong-part penalties and time until the cap; under the ORS
loop the same narration ended the episode early — earlier finish, fewer
penalties, and a mid-work summary graded as the diagnosis. This is the
mechanism most consistent with ORS scoring systematically higher.

## Phase 2 — grading-path audit

Side-by-side of the captured episodes (extracted diagnosis → grader inputs):

**Red-herring (0.0 vs 0.0 this time).** Inspect: haiku never called
`finish()`; at the message cap the scorer graded the last plain completion
("Excellent! The engine started! So the issue was the **ground strap**...") →
component-only 30/60, mode None, 2 wrong parts, cost −24.3 → 0.0 after
flooring. ORS: haiku called `finish("ground_strap corroded/open connection
...")` → 60/60 root, but 5 wrong parts and cost −65.7 → 0.0.

**Compound (5.4 vs 59.0).** Inspect: cap hit mid-work; graded completion was
diagnostic narration ("The ignition switch appears functional...") → parsed
`ignition_switch`, secondary battery mention 15/60, resolution penalty, 5.4.
ORS: haiku legitimately replaced both real faults (plus an innocent
alternator), verified the start, called `finish("ground_strap corroded; ...")`
→ 52.5/60, fix verified, 59.0 — a *valid* score for that episode's actions.

**Audit result: no grading defect on either path.**

- The ORS `@terminal` fallback grades a final plain message **exactly the way
  the Inspect scorer already does** (Inspect grades `output.completion` when
  `finish()` was never called — including fuzzy component matches on rambling
  text, as the red-herring episode shows). Same grader, same parser, same
  caps; idempotence pinned by tests.
- Reward emission: ORS emits grader-total/100 only at episode end; guessing
  cap, measure-first cap, resolution penalty all fire identically for
  identical world state (Part A of the deterministic validation already pinned
  score-identity on scripted episodes).
- The score differences are fully explained by *different episodes happening*
  — which the Phase 1 context/harness differences (and model stochasticity)
  produce.

## Fixes applied (2026-07-20, after go)

All proposed fixes below were applied — adapter items 1–2 as proposed; item 3
amended: raising turned out to surface as a client-side `ToolFailed`
exception with a session-id prefix baked into the message (and an unknown
platform harness may fatal on it rather than show the model the error), so
the adapter instead returns the BARE error message (byte-identical to
Inspect's ToolError text) as a normal result with
`metadata={"is_error": True}`, which the reference harness renders as
Inspect does (`is_error: true`, bare string content). Harness items 4–7 as
proposed. New regression test
`test_tool_specs_byte_match_inspect_serialization` derives Inspect's specs
via `ToolDef` at test time and byte-compares the anthropic-format conversion
of the served specs (plus pinned `finish` strings from the capture). 120
tests green; Part A deterministic replay re-verified exact (100.0 = 100.0,
all 5 scenarios). Phase 3 results below.

## Original proposed fixes (for the record)

**Adapter (`src/nostart/openreward/env.py`) — served surface:**

1. Byte-match every tool description and param description to Inspect's
   serialization (drop the "Returns" paragraphs; restore docstring line
   breaks; `finish` description exactly the Inspect submit line; `answer`
   param description "Submitted answer"). Source of truth: the captured
   Inspect tool specs; pin with a regression test against them.
2. Match schema shape: `extra="forbid"` on all params models
   (`additionalProperties: false`) and `json_schema_extra` to emit
   `required: []` on no-arg tools.
3. Tool errors: raise instead of returning `"Error: ..."` text, so the server
   returns ORS's native `RunToolError` and a harness can render
   `is_error: true` with the bare message, as Inspect does.

**Validation harness (`scripts/validate_openreward.py` Part B):**

4. Replicate `basic_agent` semantics: on a plain assistant message, append
   "Please proceed to the next step using your best judgement." and continue;
   terminal fallback only at the cap.
5. Count messages the way Inspect does (system + user + assistant + each tool
   result individually, cap 50 checked before each generate).
6. `max_tokens` 32000 to match the provider default Inspect used.
7. Frame tool results as text-block lists; render `RunToolError` as
   `is_error: true` + bare message.

Not proposed: any change to the core environment, grader, prompts, or the
Inspect pipeline (canonical).

**Card impact:** the card's parity section was softened at the checkpoint;
after the fixes and Phase 3 it now claims exactly what is verified: prompts
AND tool specs byte-matched (regression-tested), reward mapping exact on
deterministic replay, model-level scores comparable within sampling variance.

## Phase 3 — statistical check after fixes (20 haiku episodes)

`phase3.py`; per-episode scores in `phase3_results.json`.

| scenario | pipeline | per-epoch scores | mean | root-ok |
| --- | --- | --- | --- | --- |
| red-herring | Inspect | 57.6, 56.4, 57.2, 0.0, 0.0 | 34.3 | 3/5 |
| red-herring | ORS | 0.0, 0.0, 0.0, 0.0, 31.5 | 6.3 | 1/5 |
| compound | Inspect | 80.8, 61.2, 81.7, 81.4, 0.0 | 61.0 | 1/5 |
| compound | ORS | 42.5, 80.8, 77.2, 39.4, 50.0 | 58.0 | 0/5 |

Reading:

- **No systematic ORS inflation** — the suspicious direction (ORS high)
  reversed on red-herring and vanished on compound. Both columns draw from
  the same bimodal per-episode distributions (red-herring: ~0 or ~57;
  compound: ~40–82 or 0); 3/5 vs 1/5 successes at n=5 is within binomial
  noise.
- **The termination fix is visible in the transcripts:** 4 of 5 ORS
  red-herring episodes now end via the 50-message cap (`message_cap`),
  exactly the failure mode Inspect's episodes show, instead of the pre-fix
  early plain-message grading.
- Note on the published benchmark: this fresh Inspect column itself differs
  from the published haiku cells (red-herring 0-for-5 published vs 3/5 here)
  — haiku's per-cell variance at n=5 is large in both pipelines. The parity
  question (ORS vs Inspect) is settled by the columns tracking each other;
  neither pipeline is claimed to reproduce the published point estimates.

**Residual known micro-divergences, documented not fixed:** (a) if a model
batches more tool calls after `finish` in the same assistant turn, Inspect
executes them before scoring while ORS grades at the `finish` call (not
observed in any transcript; models submit alone); (b) Inspect's
prompt-caching `cache_control` markers and `extra_headers` are
transport-level and model-invisible; (c) ORS tool specs carry
`type: "custom"` where Inspect omits the field — semantically identical to
the API.
