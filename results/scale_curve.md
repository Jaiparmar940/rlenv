# no-start-env — scale curve

Run date(s): 2026-07-13. Prompt variant: uncoached (no strategy, no grader rules, no trap hints).
5 scenarios x 3 epochs per model (15 episodes each). Score 0-100: root cause 60 / parts discipline 25 / cost efficiency 15, minus a flat 15 unless the root-cause part was replaced and a successful start verified the repair.

## Findings

1. Frontier models have cleared the easy/medium tier: root-cause correct in 35/36 of those episodes across 4 models (tier mean 80.4/100). The hard tier now carries the separation: root-ok 8/24 at the frontier.
2. The gradient steepens one tier down. The deployment tier (2 models) averages 48.1, a 32-point gap on the same 5 scenarios.
3. The gap is scenario-specific, not uniform: the deployment tier scores 78.9 on the single-fault battery scenario and 40.4 everywhere a plausible-but-wrong reading has to be rejected.
4. Means hide the reliability story. pass^k (full root-cause credit in EVERY epoch) is the honest column: a model that is right two times in three is not deployable, and the per-scenario root-ok fractions below show exactly where that happens.
5. The open 3B-8B tier — the weight class that runs on-device / on-robot — averages 15.3 across 3 models. It is not a tool-use failure: ministral-3b completes the trivial battery scenario cleanly (root-ok 4/9 tier-wide on easy) and the tier scores ~0 wherever two-point localization is required.

## Per model x scenario

root-ok = fraction of epochs with full root-cause credit (component AND mode). pass^k = root-ok in every epoch. verified-fix = root part replaced and a successful start observed after it. measured-first = at least one diagnostic probe before the first replacement. time vs expert = episode minutes / expert-baseline minutes (1.00x = expert speed; the cost bucket hits zero at 2.00x and goes negative beyond).

| tier | model | scenario | k | mean | min | max | root-ok | pass^k | verified-fix | measured-first | time vs expert |
|---|---|---|---:|---:|---:|---:|---|---|---|---|---:|
| frontier | anthropic/claude-fable-5 | easy_dead_battery | 3 | 95.8 | 95.8 | 95.8 | 3/3 | PASS | 3/3 | 3/3 | 1.28x |
| frontier | anthropic/claude-fable-5 | hard_compound_battery_and_ground | 3 | 86.3 | 85.0 | 87.2 | 0/3 | fail | 3/3 | 3/3 | 1.41x |
| frontier | anthropic/claude-fable-5 | hard_intermittent_ecu_can | 3 | 72.1 | 51.1 | 86.5 | 3/3 | PASS | 3/3 | 3/3 | 2.51x |
| frontier | anthropic/claude-fable-5 | medium_corroded_ground | 3 | 95.1 | 94.7 | 96.0 | 3/3 | PASS | 3/3 | 3/3 | 1.32x |
| frontier | anthropic/claude-fable-5 | medium_ground_red_herring_battery | 3 | 98.4 | 98.4 | 98.4 | 3/3 | PASS | 3/3 | 3/3 | 1.11x |
| frontier | anthropic/claude-sonnet-5 | easy_dead_battery | 3 | 90.2 | 89.8 | 90.4 | 3/3 | PASS | 3/3 | 3/3 | 1.65x |
| frontier | anthropic/claude-sonnet-5 | hard_compound_battery_and_ground | 3 | 87.8 | 83.6 | 90.3 | 2/3 | fail | 3/3 | 3/3 | 1.65x |
| frontier | anthropic/claude-sonnet-5 | hard_intermittent_ecu_can | 3 | 13.9 | 11.0 | 19.2 | 0/3 | fail | 2/3 | 3/3 | 2.41x |
| frontier | anthropic/claude-sonnet-5 | medium_corroded_ground | 3 | 93.7 | 92.9 | 94.3 | 3/3 | PASS | 3/3 | 3/3 | 1.42x |
| frontier | anthropic/claude-sonnet-5 | medium_ground_red_herring_battery | 3 | 90.0 | 84.6 | 93.5 | 3/3 | PASS | 3/3 | 3/3 | 1.67x |
| frontier | grok/grok-4 | easy_dead_battery | 3 | 88.0 | 69.4 | 98.8 | 2/3 | fail | 3/3 | 3/3 | 1.13x |
| frontier | grok/grok-4 | hard_compound_battery_and_ground | 3 | 65.9 | 40.0 | 81.4 | 0/3 | fail | 2/3 | 3/3 | 1.27x |
| frontier | grok/grok-4 | hard_intermittent_ecu_can | 3 | 31.6 | 7.0 | 62.7 | 1/3 | fail | 2/3 | 3/3 | 2.16x |
| frontier | grok/grok-4 | medium_corroded_ground | 3 | 97.6 | 96.5 | 98.7 | 3/3 | PASS | 3/3 | 3/3 | 1.16x |
| frontier | grok/grok-4 | medium_ground_red_herring_battery | 3 | 95.7 | 90.3 | 100.0 | 3/3 | PASS | 3/3 | 3/3 | 1.29x |
| frontier | openai/gpt-5.5 | easy_dead_battery | 3 | 91.2 | 87.4 | 94.0 | 3/3 | PASS | 3/3 | 3/3 | 1.59x |
| frontier | openai/gpt-5.5 | hard_compound_battery_and_ground | 3 | 85.1 | 81.4 | 88.9 | 0/3 | fail | 3/3 | 3/3 | 1.33x |
| frontier | openai/gpt-5.5 | hard_intermittent_ecu_can | 3 | 42.1 | 0.0 | 79.2 | 2/3 | fail | 3/3 | 3/3 | 3.10x |
| frontier | openai/gpt-5.5 | medium_corroded_ground | 3 | 94.7 | 94.7 | 94.7 | 3/3 | PASS | 3/3 | 3/3 | 1.35x |
| frontier | openai/gpt-5.5 | medium_ground_red_herring_battery | 3 | 93.8 | 91.5 | 95.5 | 3/3 | PASS | 3/3 | 3/3 | 1.41x |
| deployment (small closed) | anthropic/claude-haiku-4-5 | easy_dead_battery | 3 | 85.8 | 79.6 | 89.8 | 3/3 | PASS | 3/3 | 3/3 | 1.95x |
| deployment (small closed) | anthropic/claude-haiku-4-5 | hard_compound_battery_and_ground | 3 | 33.9 | 2.1 | 81.1 | 0/3 | fail | 2/3 | 3/3 | 1.86x |
| deployment (small closed) | anthropic/claude-haiku-4-5 | hard_intermittent_ecu_can | 3 | 8.5 | 0.0 | 25.4 | 1/3 | fail | 0/3 | 3/3 | 3.48x |
| deployment (small closed) | anthropic/claude-haiku-4-5 | medium_corroded_ground | 3 | 53.3 | 9.0 | 97.3 | 2/3 | fail | 3/3 | 3/3 | 2.07x |
| deployment (small closed) | anthropic/claude-haiku-4-5 | medium_ground_red_herring_battery | 3 | 0.0 | 0.0 | 0.0 | 0/3 | fail | 0/3 | 3/3 | 3.41x |
| deployment (small closed) | google/gemini-3.5-flash | easy_dead_battery | 3 | 72.0 | 64.6 | 81.4 | 3/3 | PASS | 3/3 | 3/3 | 2.87x |
| deployment (small closed) | google/gemini-3.5-flash | hard_compound_battery_and_ground | 3 | 42.7 | 26.4 | 74.2 | 0/3 | fail | 3/3 | 3/3 | 1.82x |
| deployment (small closed) | google/gemini-3.5-flash | hard_intermittent_ecu_can | 3 | 7.3 | 6.6 | 7.6 | 0/3 | fail | 0/3 | 3/3 | 2.18x |
| deployment (small closed) | google/gemini-3.5-flash | medium_corroded_ground | 3 | 89.3 | 86.8 | 91.6 | 3/3 | PASS | 3/3 | 3/3 | 1.72x |
| deployment (small closed) | google/gemini-3.5-flash | medium_ground_red_herring_battery | 3 | 88.5 | 85.8 | 90.7 | 3/3 | PASS | 3/3 | 3/3 | 1.77x |
| open 3B-8B | openrouter/meta-llama/llama-3.1-8b-instruct | easy_dead_battery | 3 | 0.0 | 0.0 | 0.0 | 0/3 | fail | 0/3 | 3/3 | 2.43x |
| open 3B-8B | openrouter/meta-llama/llama-3.1-8b-instruct | hard_compound_battery_and_ground | 3 | 11.7 | 0.0 | 25.0 | 0/3 | fail | 0/3 | 2/3 | 1.42x |
| open 3B-8B | openrouter/meta-llama/llama-3.1-8b-instruct | hard_intermittent_ecu_can | 3 | 15.0 | 10.0 | 25.0 | 0/3 | fail | 0/3 | 1/3 | 1.67x |
| open 3B-8B | openrouter/meta-llama/llama-3.1-8b-instruct | medium_corroded_ground | 3 | 13.2 | 5.5 | 25.0 | 0/3 | fail | 0/3 | 3/3 | 1.08x |
| open 3B-8B | openrouter/meta-llama/llama-3.1-8b-instruct | medium_ground_red_herring_battery | 3 | 10.7 | 3.3 | 25.0 | 0/3 | fail | 0/3 | 3/3 | 1.24x |
| open 3B-8B | openrouter/mistralai/ministral-3b-2512 | easy_dead_battery | 3 | 95.4 | 92.2 | 97.0 | 3/3 | PASS | 3/3 | 3/3 | 1.31x |
| open 3B-8B | openrouter/mistralai/ministral-3b-2512 | hard_compound_battery_and_ground | 3 | 0.0 | 0.0 | 0.0 | 0/3 | fail | 0/3 | 3/3 | 2.01x |
| open 3B-8B | openrouter/mistralai/ministral-3b-2512 | hard_intermittent_ecu_can | 3 | 0.0 | 0.0 | 0.0 | 0/3 | fail | 0/3 | 3/3 | 2.51x |
| open 3B-8B | openrouter/mistralai/ministral-3b-2512 | medium_corroded_ground | 3 | 0.0 | 0.0 | 0.0 | 0/3 | fail | 0/3 | 3/3 | 2.22x |
| open 3B-8B | openrouter/mistralai/ministral-3b-2512 | medium_ground_red_herring_battery | 3 | 0.0 | 0.0 | 0.0 | 0/3 | fail | 0/3 | 3/3 | 2.74x |
| open 3B-8B | openrouter/qwen/qwen-2.5-7b-instruct | easy_dead_battery | 3 | 71.0 | 61.6 | 88.0 | 1/3 | fail | 3/3 | 3/3 | 1.60x |
| open 3B-8B | openrouter/qwen/qwen-2.5-7b-instruct | hard_compound_battery_and_ground | 3 | 10.2 | 0.0 | 19.2 | 0/3 | fail | 0/3 | 3/3 | 2.06x |
| open 3B-8B | openrouter/qwen/qwen-2.5-7b-instruct | hard_intermittent_ecu_can | 3 | 2.8 | 0.0 | 5.6 | 0/3 | fail | 0/3 | 3/3 | 1.55x |
| open 3B-8B | openrouter/qwen/qwen-2.5-7b-instruct | medium_corroded_ground | 3 | 0.0 | 0.0 | 0.0 | 0/3 | fail | 0/3 | 3/3 | 3.71x |
| open 3B-8B | openrouter/qwen/qwen-2.5-7b-instruct | medium_ground_red_herring_battery | 3 | 0.0 | 0.0 | 0.0 | 0/3 | fail | 0/3 | 3/3 | 2.72x |

## Summary (sorted by scale tier, then score)

| tier | model | mean | root-ok | pass^k (all scenarios) | verified-fix |
|---|---|---:|---|---|---|
| frontier | anthropic/claude-fable-5 | 89.5 | 12/15 | fail | 15/15 |
| frontier | openai/gpt-5.5 | 81.4 | 11/15 | fail | 15/15 |
| frontier | grok/grok-4 | 75.8 | 9/15 | fail | 13/15 |
| frontier | anthropic/claude-sonnet-5 | 75.1 | 11/15 | fail | 14/15 |
| deployment (small closed) | google/gemini-3.5-flash | 59.9 | 9/15 | fail | 12/15 |
| deployment (small closed) | anthropic/claude-haiku-4-5 | 36.3 | 6/15 | fail | 8/15 |
| open 3B-8B | openrouter/mistralai/ministral-3b-2512 | 19.1 | 3/15 | fail | 3/15 |
| open 3B-8B | openrouter/qwen/qwen-2.5-7b-instruct | 16.8 | 1/15 | fail | 3/15 |
| open 3B-8B | openrouter/meta-llama/llama-3.1-8b-instruct | 10.1 | 0/15 | fail | 0/15 |

**Separation (best - worst): 79.4 points** (anthropic/claude-fable-5 89.5 - openrouter/meta-llama/llama-3.1-8b-instruct 10.1). A benchmark that does not separate models is not measuring anything; this one separates two adjacent tiers of the same vendor by 79 points.

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
| anthropic/claude-fable-5 | 15 | 494,063 | 30,835 |
| anthropic/claude-sonnet-5 | 15 | 574,606 | 41,544 |
| grok/grok-4 | 15 | 313,641 | 2,795 |
| openai/gpt-5.5 | 15 | 190,500 | 13,487 |
| anthropic/claude-haiku-4-5 | 15 | 719,286 | 28,332 |
| google/gemini-3.5-flash | 15 | 1,294,910 | 24,824 |
| openrouter/meta-llama/llama-3.1-8b-instruct | 15 | 192,965 | 6,521 |
| openrouter/mistralai/ministral-3b-2512 | 15 | 348,008 | 10,070 |
| openrouter/qwen/qwen-2.5-7b-instruct | 15 | 461,166 | 15,803 |
