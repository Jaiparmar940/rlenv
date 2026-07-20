# OpenReward serving validation (Phase 3)

> **2026-07-20 update:** the Part B numbers below predate the parity fixes.
> A wire-level parity diagnosis found and fixed model-visible divergences
> (tool-spec serialization, harness termination semantics, max_tokens, error
> framing); the canonical parity record — including a 20-episode two-pipeline
> re-check confirming no systematic score difference — is
> `results/parity_diag/REPORT.md`. Part A (deterministic exact-match) was
> re-verified after the fixes and still holds.

Run 2026-07-20 on the working tree that introduced the adapter
(`src/nostart/openreward/`), reproducible via
`scripts/validate_openreward.py`. The script starts the ORS server locally,
replays episodes over the real HTTP interface, and compares against direct
Inspect runs.

## Part A — deterministic expert replay (exact match required)

The five expert action scripts (`run_evals.MOCK_SCRIPTS`) replayed through
(1) the Inspect mock pipeline and (2) a live ORS HTTP session. Seeded
environment ⇒ scores must match exactly.

| scenario | inspect | ors | match |
| --- | --- | --- | --- |
| easy_dead_battery | 100.0 | 100.0 | OK |
| medium_corroded_ground | 100.0 | 100.0 | OK |
| medium_ground_red_herring_battery | 100.0 | 100.0 | OK |
| hard_intermittent_ecu_can | 100.0 | 100.0 | OK |
| hard_compound_battery_and_ground | 100.0 | 100.0 | OK |

**PASS — ORS serving is score-identical to Inspect.** Observation-level
equivalence (byte-identical tool payloads) and reward mapping
(grader total / 100) are additionally pinned by
`tests/test_openreward_adapter.py`.

## Part B — anthropic/claude-haiku-4-5, 1 epoch/scenario, both interfaces

Model sampling is stochastic, so these are comparable, not identical — the
exactness claim is Part A's. Both columns sit inside haiku's documented
high-variance range (published mean 39.9 with per-episode swings from 0 to
~80 on the same scenario; see results/scale_curve.md).

| scenario | inspect | ors |
| --- | --- | --- |
| easy_dead_battery | 85.6 | 90.4 |
| medium_corroded_ground | 0.0 | 3.3 |
| medium_ground_red_herring_battery | 0.0 | 26.2 |
| hard_intermittent_ecu_can | 0.0 | 10.4 |
| hard_compound_battery_and_ground | 0.0 | 77.5 |

## Environment health at validation time

- `scripts/sanity_check.py` — ALL CHECKS PASSED
- `pytest tests/` — 119 passed (105 pre-existing + 14 new adapter tests)
- `scripts/check_determinism.py` — 5 scenarios reproduce exactly

## Leakage check on the new surface

Scenario names / ground-truth terms in the new files appear only in:

- `src/nostart/openreward/env.py` — the server-side task-id → scenario
  mapping (never serialized to clients; `tests/test_openreward_adapter.py`
  pins that task specs, prompts, and tool specs contain no scenario names).
- `docs/openreward_card.md` — the public environment card, same exposure as
  the already-public repo README.

Note the honest limit (unchanged from the published benchmark): the repo is
public, so opaque task ids keep answers out of the *default agent context*,
not away from a determined lookup. Integrity rests on the agent-visible
surface, which is audited.
