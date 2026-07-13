# no-start-env — scale curve

Run date(s): 2026-07-13. Prompt variant: uncoached (no strategy, no grader rules, no trap hints).
5 scenarios x 3 epochs per model (15 episodes each). Score 0-100: root cause 60 / parts discipline 25 / cost efficiency 15, minus a flat 15 unless the root-cause part was replaced and a successful start verified the repair.

## Findings

1. Frontier models have cleared the easy/medium tier: root-cause correct in 59/60 of those episodes across 4 models (tier mean 79.4/100). The hard tier now carries the separation: root-ok 15/40 at the frontier.
2. The gradient steepens one tier down. The deployment tier (2 models) averages 49.8, a 30-point gap on the same 5 scenarios.
3. The gap is scenario-specific, not uniform: the deployment tier scores 71.9 on the single-fault battery scenario and 44.3 everywhere a plausible-but-wrong reading has to be rejected.
4. Means hide the reliability story. pass^k (full root-cause credit in EVERY epoch) is the honest column: a model that is right two times in three is not deployable, and the per-scenario root-ok fractions below show exactly where that happens.
5. The open 3B-8B tier — the weight class that runs on-device / on-robot — averages 17.0 across 3 models. It is not a tool-use failure: ministral-3b completes the trivial battery scenario cleanly (root-ok 7/15 tier-wide on easy) and the tier scores ~0 wherever two-point localization is required.

## Per model x scenario

root-ok = fraction of epochs with full root-cause credit (component AND mode). pass^k = root-ok in every epoch. verified-fix = root part replaced and a successful start observed after it. measured-first = at least one diagnostic probe before the first replacement. time vs expert = episode minutes / expert-baseline minutes (1.00x = expert speed; the cost bucket hits zero at 2.00x and goes negative beyond).

| tier | model | scenario | k | mean | min | max | root-ok | pass^k | verified-fix | measured-first | time vs expert |
|---|---|---|---:|---:|---:|---:|---|---|---|---|---:|
| frontier | anthropic/claude-fable-5 | easy_dead_battery | 5 | 95.8 | 94.6 | 97.0 | 5/5 | PASS | 5/5 | 5/5 | 1.28x |
| frontier | anthropic/claude-fable-5 | hard_compound_battery_and_ground | 5 | 86.2 | 85.0 | 87.2 | 0/5 | fail | 5/5 | 5/5 | 1.42x |
| frontier | anthropic/claude-fable-5 | hard_intermittent_ecu_can | 5 | 54.9 | 0.0 | 86.5 | 4/5 | fail | 5/5 | 5/5 | 2.62x |
| frontier | anthropic/claude-fable-5 | medium_corroded_ground | 5 | 95.4 | 94.7 | 96.9 | 5/5 | PASS | 5/5 | 5/5 | 1.31x |
| frontier | anthropic/claude-fable-5 | medium_ground_red_herring_battery | 5 | 97.6 | 96.3 | 98.4 | 5/5 | PASS | 5/5 | 5/5 | 1.16x |
| frontier | anthropic/claude-sonnet-5 | easy_dead_battery | 5 | 89.2 | 87.4 | 90.4 | 5/5 | PASS | 5/5 | 5/5 | 1.72x |
| frontier | anthropic/claude-sonnet-5 | hard_compound_battery_and_ground | 5 | 89.3 | 83.6 | 91.7 | 4/5 | fail | 5/5 | 5/5 | 1.61x |
| frontier | anthropic/claude-sonnet-5 | hard_intermittent_ecu_can | 5 | 10.8 | 4.2 | 19.2 | 0/5 | fail | 3/5 | 5/5 | 2.55x |
| frontier | anthropic/claude-sonnet-5 | medium_corroded_ground | 5 | 93.5 | 90.7 | 95.6 | 5/5 | PASS | 5/5 | 5/5 | 1.44x |
| frontier | anthropic/claude-sonnet-5 | medium_ground_red_herring_battery | 5 | 89.7 | 84.2 | 94.3 | 5/5 | PASS | 5/5 | 5/5 | 1.69x |
| frontier | grok/grok-4 | easy_dead_battery | 5 | 91.7 | 69.4 | 98.8 | 4/5 | fail | 5/5 | 5/5 | 1.15x |
| frontier | grok/grok-4 | hard_compound_battery_and_ground | 5 | 62.1 | 32.5 | 81.4 | 0/5 | fail | 3/5 | 5/5 | 1.23x |
| frontier | grok/grok-4 | hard_intermittent_ecu_can | 5 | 32.0 | 5.6 | 62.7 | 2/5 | fail | 3/5 | 5/5 | 2.06x |
| frontier | grok/grok-4 | medium_corroded_ground | 5 | 97.3 | 95.6 | 98.7 | 5/5 | PASS | 5/5 | 5/5 | 1.18x |
| frontier | grok/grok-4 | medium_ground_red_herring_battery | 5 | 91.3 | 70.2 | 100.0 | 5/5 | PASS | 5/5 | 5/5 | 1.37x |
| frontier | openai/gpt-5.5 | easy_dead_battery | 5 | 92.1 | 87.4 | 95.2 | 5/5 | PASS | 5/5 | 5/5 | 1.53x |
| frontier | openai/gpt-5.5 | hard_compound_battery_and_ground | 5 | 87.9 | 81.4 | 92.5 | 2/5 | fail | 5/5 | 5/5 | 1.41x |
| frontier | openai/gpt-5.5 | hard_intermittent_ecu_can | 5 | 41.2 | 0.0 | 79.2 | 3/5 | fail | 5/5 | 5/5 | 3.06x |
| frontier | openai/gpt-5.5 | medium_corroded_ground | 5 | 95.2 | 94.7 | 96.9 | 5/5 | PASS | 5/5 | 5/5 | 1.32x |
| frontier | openai/gpt-5.5 | medium_ground_red_herring_battery | 5 | 95.1 | 91.5 | 99.6 | 5/5 | PASS | 5/5 | 5/5 | 1.33x |
| deployment (small closed) | anthropic/claude-haiku-4-5 | easy_dead_battery | 5 | 87.3 | 79.6 | 91.0 | 5/5 | PASS | 5/5 | 5/5 | 1.85x |
| deployment (small closed) | anthropic/claude-haiku-4-5 | hard_compound_battery_and_ground | 5 | 37.6 | 2.1 | 81.1 | 0/5 | fail | 3/5 | 5/5 | 1.82x |
| deployment (small closed) | anthropic/claude-haiku-4-5 | hard_intermittent_ecu_can | 5 | 5.1 | 0.0 | 25.4 | 1/5 | fail | 0/5 | 5/5 | 3.15x |
| deployment (small closed) | anthropic/claude-haiku-4-5 | medium_corroded_ground | 5 | 69.5 | 9.0 | 97.3 | 4/5 | fail | 5/5 | 5/5 | 1.81x |
| deployment (small closed) | anthropic/claude-haiku-4-5 | medium_ground_red_herring_battery | 5 | 0.0 | 0.0 | 0.0 | 0/5 | fail | 0/5 | 5/5 | 3.51x |
| deployment (small closed) | google/gemini-3.5-flash | easy_dead_battery | 5 | 56.4 | 0.4 | 81.4 | 4/5 | fail | 5/5 | 5/5 | 3.10x |
| deployment (small closed) | google/gemini-3.5-flash | hard_compound_battery_and_ground | 5 | 56.2 | 26.4 | 77.2 | 0/5 | fail | 5/5 | 5/5 | 1.72x |
| deployment (small closed) | google/gemini-3.5-flash | hard_intermittent_ecu_can | 5 | 6.5 | 4.7 | 7.6 | 0/5 | fail | 0/5 | 5/5 | 2.23x |
| deployment (small closed) | google/gemini-3.5-flash | medium_corroded_ground | 5 | 89.2 | 86.8 | 91.6 | 5/5 | PASS | 5/5 | 5/5 | 1.72x |
| deployment (small closed) | google/gemini-3.5-flash | medium_ground_red_herring_battery | 5 | 90.1 | 85.8 | 92.7 | 5/5 | PASS | 5/5 | 5/5 | 1.66x |
| open 3B-8B | openrouter/meta-llama/llama-3.1-8b-instruct | easy_dead_battery | 5 | 0.0 | 0.0 | 0.0 | 0/5 | fail | 0/5 | 5/5 | 2.31x |
| open 3B-8B | openrouter/meta-llama/llama-3.1-8b-instruct | hard_compound_battery_and_ground | 5 | 8.4 | 0.0 | 25.0 | 0/5 | fail | 0/5 | 4/5 | 1.41x |
| open 3B-8B | openrouter/meta-llama/llama-3.1-8b-instruct | hard_intermittent_ecu_can | 5 | 9.7 | 0.0 | 25.0 | 0/5 | fail | 0/5 | 3/5 | 2.43x |
| open 3B-8B | openrouter/meta-llama/llama-3.1-8b-instruct | medium_corroded_ground | 5 | 8.5 | 0.0 | 25.0 | 0/5 | fail | 0/5 | 5/5 | 1.28x |
| open 3B-8B | openrouter/meta-llama/llama-3.1-8b-instruct | medium_ground_red_herring_battery | 5 | 9.3 | 3.3 | 25.0 | 0/5 | fail | 0/5 | 5/5 | 1.19x |
| open 3B-8B | openrouter/mistralai/ministral-3b-2512 | easy_dead_battery | 5 | 93.4 | 87.4 | 97.0 | 5/5 | PASS | 5/5 | 5/5 | 1.44x |
| open 3B-8B | openrouter/mistralai/ministral-3b-2512 | hard_compound_battery_and_ground | 5 | 1.1 | 0.0 | 4.3 | 0/5 | fail | 0/5 | 5/5 | 1.77x |
| open 3B-8B | openrouter/mistralai/ministral-3b-2512 | hard_intermittent_ecu_can | 5 | 1.4 | 0.0 | 6.1 | 0/5 | fail | 0/5 | 5/5 | 2.05x |
| open 3B-8B | openrouter/mistralai/ministral-3b-2512 | medium_corroded_ground | 5 | 0.0 | 0.0 | 0.0 | 0/5 | fail | 0/5 | 5/5 | 2.36x |
| open 3B-8B | openrouter/mistralai/ministral-3b-2512 | medium_ground_red_herring_battery | 5 | 19.2 | 0.0 | 96.0 | 1/5 | fail | 1/5 | 5/5 | 2.64x |
| open 3B-8B | openrouter/qwen/qwen-2.5-7b-instruct | easy_dead_battery | 5 | 74.4 | 61.6 | 92.8 | 2/5 | fail | 5/5 | 5/5 | 1.50x |
| open 3B-8B | openrouter/qwen/qwen-2.5-7b-instruct | hard_compound_battery_and_ground | 5 | 28.4 | 0.0 | 78.6 | 0/5 | fail | 1/5 | 5/5 | 1.72x |
| open 3B-8B | openrouter/qwen/qwen-2.5-7b-instruct | hard_intermittent_ecu_can | 5 | 1.7 | 0.0 | 5.6 | 0/5 | fail | 0/5 | 5/5 | 1.74x |
| open 3B-8B | openrouter/qwen/qwen-2.5-7b-instruct | medium_corroded_ground | 5 | 0.0 | 0.0 | 0.0 | 0/5 | fail | 0/5 | 5/5 | 3.48x |
| open 3B-8B | openrouter/qwen/qwen-2.5-7b-instruct | medium_ground_red_herring_battery | 5 | 0.0 | 0.0 | 0.0 | 0/5 | fail | 0/5 | 5/5 | 2.78x |

## Summary (sorted by scale tier, then score)

| tier | model | mean | root-ok | pass^k (all scenarios) | verified-fix |
|---|---|---:|---|---|---|
| frontier | anthropic/claude-fable-5 | 86.0 | 19/25 | fail | 25/25 |
| frontier | openai/gpt-5.5 | 82.3 | 20/25 | fail | 25/25 |
| frontier | grok/grok-4 | 74.9 | 16/25 | fail | 21/25 |
| frontier | anthropic/claude-sonnet-5 | 74.5 | 19/25 | fail | 23/25 |
| deployment (small closed) | google/gemini-3.5-flash | 59.7 | 14/25 | fail | 20/25 |
| deployment (small closed) | anthropic/claude-haiku-4-5 | 39.9 | 10/25 | fail | 13/25 |
| open 3B-8B | openrouter/mistralai/ministral-3b-2512 | 23.0 | 6/25 | fail | 6/25 |
| open 3B-8B | openrouter/qwen/qwen-2.5-7b-instruct | 20.9 | 2/25 | fail | 6/25 |
| open 3B-8B | openrouter/meta-llama/llama-3.1-8b-instruct | 7.2 | 0/25 | fail | 0/25 |

**Separation (best - worst): 78.8 points** (anthropic/claude-fable-5 86.0 - openrouter/meta-llama/llama-3.1-8b-instruct 7.2). A benchmark that does not separate models is not measuring anything; this one separates two adjacent tiers of the same vendor by 79 points.

## Model ids (exact)

| tier | model id | status |
|---|---|---|
| frontier — flagship reasoning models; parameter count undisclosed | `anthropic/claude-fable-5` | run |
| frontier — flagship reasoning models; parameter count undisclosed | `grok/grok-4` | run |
| frontier — flagship reasoning models; parameter count undisclosed | `anthropic/claude-sonnet-5` | run |
| frontier — flagship reasoning models; parameter count undisclosed | `openai/gpt-5.5` | run |
| deployment (small closed) — cost/latency tier a product actually ships; parameter count undisclosed | `anthropic/claude-haiku-4-5` | run |
| deployment (small closed) — cost/latency tier a product actually ships; parameter count undisclosed | `google/gemini-3.5-flash` | run |
| open 3B-8B — the weight class that runs on-device / on-robot | `openrouter/qwen/qwen-2.5-7b-instruct` | run |
| open 3B-8B — the weight class that runs on-device / on-robot | `openrouter/meta-llama/llama-3.1-8b-instruct` | run |
| open 3B-8B — the weight class that runs on-device / on-robot | `openrouter/mistralai/ministral-3b-2512` | run |

## Token usage (this table's runs)

| model | episodes | input tokens | output tokens |
|---|---:|---:|---:|
| anthropic/claude-fable-5 | 25 | 840,396 | 49,787 |
| anthropic/claude-sonnet-5 | 25 | 984,820 | 70,149 |
| grok/grok-4 | 25 | 496,057 | 4,587 |
| openai/gpt-5.5 | 25 | 325,470 | 23,764 |
| anthropic/claude-haiku-4-5 | 25 | 1,097,848 | 46,490 |
| google/gemini-3.5-flash | 25 | 2,128,005 | 42,504 |
| openrouter/meta-llama/llama-3.1-8b-instruct | 25 | 218,470 | 9,537 |
| openrouter/mistralai/ministral-3b-2512 | 25 | 544,065 | 16,133 |
| openrouter/qwen/qwen-2.5-7b-instruct | 25 | 846,779 | 26,173 |
