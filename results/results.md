# no-start-env results

Generated 2026-07-13 at commit `bcbabea`. Prompt variant(s): uncoached.
Score 0-100: root cause 60 / parts discipline 25 / cost efficiency 15 (time-only vs expert baseline, zero at 2x, negative beyond). Wrong parts -8 each (also debited from total). -15 unless the root-cause part was replaced and a successful start verified it. Replacing before any measurement caps at 40.

## Per model x scenario (aggregated over epochs)

pass^k = every epoch earned full root-cause credit (component AND mode). root-ok = fraction of epochs with full root-cause credit. verified-fix / measured-first = fraction of epochs with the behavior.

| model | scenario | k | mean | min | root | parts | cost | pass^k | root-ok | verified-fix | measured-first |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| anthropic/claude-fable-5 | easy_dead_battery | 5 | 95.8 | 94.6 | 60 | 25 | 10.8 | PASS | 5/5 | 5/5 | 5/5 |
| anthropic/claude-fable-5 | hard_compound_battery_and_ground | 5 | 86.2 | 85.0 | 52 | 25 | 8.7 | fail | 0/5 | 5/5 | 5/5 |
| anthropic/claude-fable-5 | hard_intermittent_ecu_can | 5 | 54.9 | 0.0 | 48 | 20 | -9.3 | fail | 4/5 | 5/5 | 5/5 |
| anthropic/claude-fable-5 | medium_corroded_ground | 5 | 95.4 | 94.7 | 60 | 25 | 10.4 | PASS | 5/5 | 5/5 | 5/5 |
| anthropic/claude-fable-5 | medium_ground_red_herring_battery | 5 | 97.6 | 96.3 | 60 | 25 | 12.6 | PASS | 5/5 | 5/5 | 5/5 |
| anthropic/claude-haiku-4-5 | easy_dead_battery | 5 | 87.3 | 79.6 | 60 | 25 | 2.3 | PASS | 5/5 | 5/5 | 5/5 |
| anthropic/claude-haiku-4-5 | hard_compound_battery_and_ground | 5 | 37.6 | 2.1 | 26 | 20 | 2.7 | fail | 0/5 | 3/5 | 5/5 |
| anthropic/claude-haiku-4-5 | hard_intermittent_ecu_can | 5 | 5.1 | 0.0 | 12 | 14 | -17.2 | fail | 1/5 | 0/5 | 5/5 |
| anthropic/claude-haiku-4-5 | medium_corroded_ground | 5 | 69.5 | 9.0 | 48 | 22 | 2.9 | fail | 4/5 | 5/5 | 5/5 |
| anthropic/claude-haiku-4-5 | medium_ground_red_herring_battery | 5 | 0.0 | 0.0 | 0 | 5 | -22.7 | fail | 0/5 | 0/5 | 5/5 |
| anthropic/claude-sonnet-5 | easy_dead_battery | 5 | 89.2 | 87.4 | 60 | 25 | 4.2 | PASS | 5/5 | 5/5 | 5/5 |
| anthropic/claude-sonnet-5 | hard_compound_battery_and_ground | 5 | 89.3 | 83.6 | 58 | 25 | 5.8 | fail | 4/5 | 5/5 | 5/5 |
| anthropic/claude-sonnet-5 | hard_intermittent_ecu_can | 5 | 10.8 | 4.2 | 0 | 25 | -8.2 | fail | 0/5 | 3/5 | 5/5 |
| anthropic/claude-sonnet-5 | medium_corroded_ground | 5 | 93.5 | 90.7 | 60 | 25 | 8.5 | PASS | 5/5 | 5/5 | 5/5 |
| anthropic/claude-sonnet-5 | medium_ground_red_herring_battery | 5 | 89.7 | 84.2 | 60 | 25 | 4.7 | PASS | 5/5 | 5/5 | 5/5 |
| google/gemini-3.5-flash | easy_dead_battery | 5 | 56.4 | 0.4 | 48 | 25 | -16.6 | fail | 4/5 | 5/5 | 5/5 |
| google/gemini-3.5-flash | hard_compound_battery_and_ground | 5 | 56.2 | 26.4 | 27 | 25 | 4.2 | fail | 0/5 | 5/5 | 5/5 |
| google/gemini-3.5-flash | hard_intermittent_ecu_can | 5 | 6.5 | 4.7 | 0 | 25 | -3.5 | fail | 0/5 | 0/5 | 5/5 |
| google/gemini-3.5-flash | medium_corroded_ground | 5 | 89.2 | 86.8 | 60 | 25 | 4.2 | PASS | 5/5 | 5/5 | 5/5 |
| google/gemini-3.5-flash | medium_ground_red_herring_battery | 5 | 90.1 | 85.8 | 60 | 25 | 5.1 | PASS | 5/5 | 5/5 | 5/5 |
| grok/grok-4 | easy_dead_battery | 5 | 91.7 | 69.4 | 54 | 25 | 12.7 | fail | 4/5 | 5/5 | 5/5 |
| grok/grok-4 | hard_compound_battery_and_ground | 5 | 62.1 | 32.5 | 32 | 25 | 11.6 | fail | 0/5 | 3/5 | 5/5 |
| grok/grok-4 | hard_intermittent_ecu_can | 5 | 32.0 | 5.6 | 30 | 17 | -1.0 | fail | 2/5 | 3/5 | 5/5 |
| grok/grok-4 | medium_corroded_ground | 5 | 97.3 | 95.6 | 60 | 25 | 12.3 | PASS | 5/5 | 5/5 | 5/5 |
| grok/grok-4 | medium_ground_red_herring_battery | 5 | 91.3 | 70.2 | 60 | 23 | 9.5 | PASS | 5/5 | 5/5 | 5/5 |
| openai/gpt-5.5 | easy_dead_battery | 5 | 92.1 | 87.4 | 60 | 25 | 7.1 | PASS | 5/5 | 5/5 | 5/5 |
| openai/gpt-5.5 | hard_compound_battery_and_ground | 5 | 87.9 | 81.4 | 54 | 25 | 8.9 | fail | 2/5 | 5/5 | 5/5 |
| openai/gpt-5.5 | hard_intermittent_ecu_can | 5 | 41.2 | 0.0 | 36 | 22 | -16.0 | fail | 3/5 | 5/5 | 5/5 |
| openai/gpt-5.5 | medium_corroded_ground | 5 | 95.2 | 94.7 | 60 | 25 | 10.2 | PASS | 5/5 | 5/5 | 5/5 |
| openai/gpt-5.5 | medium_ground_red_herring_battery | 5 | 95.1 | 91.5 | 60 | 25 | 10.1 | PASS | 5/5 | 5/5 | 5/5 |
| openrouter/meta-llama/llama-3.1-8b-instruct | easy_dead_battery | 5 | 0.0 | 0.0 | 0 | 17 | -4.7 | fail | 0/5 | 0/5 | 5/5 |
| openrouter/meta-llama/llama-3.1-8b-instruct | hard_compound_battery_and_ground | 5 | 8.4 | 0.0 | 0 | 15 | 8.8 | fail | 0/5 | 0/5 | 4/5 |
| openrouter/meta-llama/llama-3.1-8b-instruct | hard_intermittent_ecu_can | 5 | 9.7 | 0.0 | 0 | 18 | -6.4 | fail | 0/5 | 0/5 | 3/5 |
| openrouter/meta-llama/llama-3.1-8b-instruct | medium_corroded_ground | 5 | 8.5 | 0.0 | 0 | 17 | 10.9 | fail | 0/5 | 0/5 | 5/5 |
| openrouter/meta-llama/llama-3.1-8b-instruct | medium_ground_red_herring_battery | 5 | 9.3 | 3.3 | 0 | 19 | 12.1 | fail | 0/5 | 0/5 | 5/5 |
| openrouter/mistralai/ministral-3b-2512 | easy_dead_battery | 5 | 93.4 | 87.4 | 60 | 25 | 8.4 | PASS | 5/5 | 5/5 | 5/5 |
| openrouter/mistralai/ministral-3b-2512 | hard_compound_battery_and_ground | 5 | 1.1 | 0.0 | 2 | 14 | 3.4 | fail | 0/5 | 0/5 | 5/5 |
| openrouter/mistralai/ministral-3b-2512 | hard_intermittent_ecu_can | 5 | 1.4 | 0.0 | 0 | 12 | -0.8 | fail | 0/5 | 0/5 | 5/5 |
| openrouter/mistralai/ministral-3b-2512 | medium_corroded_ground | 5 | 0.0 | 0.0 | 0 | 9 | -5.5 | fail | 0/5 | 0/5 | 5/5 |
| openrouter/mistralai/ministral-3b-2512 | medium_ground_red_herring_battery | 5 | 19.2 | 0.0 | 12 | 11 | -9.6 | fail | 1/5 | 1/5 | 5/5 |
| openrouter/qwen/qwen-2.5-7b-instruct | easy_dead_battery | 5 | 74.4 | 61.6 | 42 | 25 | 7.4 | fail | 2/5 | 5/5 | 5/5 |
| openrouter/qwen/qwen-2.5-7b-instruct | hard_compound_battery_and_ground | 5 | 28.4 | 0.0 | 15 | 19 | 4.2 | fail | 0/5 | 1/5 | 5/5 |
| openrouter/qwen/qwen-2.5-7b-instruct | hard_intermittent_ecu_can | 5 | 1.7 | 0.0 | 0 | 14 | 4.0 | fail | 0/5 | 0/5 | 5/5 |
| openrouter/qwen/qwen-2.5-7b-instruct | medium_corroded_ground | 5 | 0.0 | 0.0 | 0 | 4 | -22.2 | fail | 0/5 | 0/5 | 5/5 |
| openrouter/qwen/qwen-2.5-7b-instruct | medium_ground_red_herring_battery | 5 | 0.0 | 0.0 | 0 | 4 | -11.8 | fail | 0/5 | 0/5 | 5/5 |

## Summary

| model | mean total |
|---|---:|
| anthropic/claude-fable-5 | 86.0 |
| anthropic/claude-haiku-4-5 | 39.9 |
| anthropic/claude-sonnet-5 | 74.5 |
| google/gemini-3.5-flash | 59.7 |
| grok/grok-4 | 74.9 |
| openai/gpt-5.5 | 82.3 |
| openrouter/meta-llama/llama-3.1-8b-instruct | 7.2 |
| openrouter/mistralai/ministral-3b-2512 | 23.0 |
| openrouter/qwen/qwen-2.5-7b-instruct | 20.9 |

Best-worst model spread (separation): **78.8** points.

## Per-episode detail

| model | scenario | epoch | variant | total | root | parts | cost | guess cap | wrong parts | diagnosis |
|---|---|---:|---|---:|---:|---:|---:|---|---|---|
| anthropic/claude-fable-5 | easy_dead_battery | 1 | uncoached | 95.8 | 60 | 25 | 10.80 |  |  | battery failed internally (dead cell / sulfation) — battery  |
| anthropic/claude-fable-5 | easy_dead_battery | 2 | uncoached | 95.8 | 60 | 25 | 10.80 |  |  | battery failed (internal dead/sulfated cell — read only 2.13 |
| anthropic/claude-fable-5 | easy_dead_battery | 3 | uncoached | 95.8 | 60 | 25 | 10.80 |  |  | battery internally failed (dead/sulfated cell) — measured on |
| anthropic/claude-fable-5 | easy_dead_battery | 4 | uncoached | 97.0 | 60 | 25 | 12.00 |  |  | battery failed (dead/sulfated cell, internally shorted — mea |
| anthropic/claude-fable-5 | easy_dead_battery | 5 | uncoached | 94.6 | 60 | 25 | 9.60 |  |  | battery failed (dead/internally sulfated cell). Battery meas |
| anthropic/claude-fable-5 | hard_compound_battery_and_ground | 1 | uncoached | 87.2 | 52 | 25 | 9.72 |  |  | ground_strap corroded (high-resistance ground) — root cause. |
| anthropic/claude-fable-5 | hard_compound_battery_and_ground | 2 | uncoached | 86.7 | 52 | 25 | 9.17 |  |  | ground_strap corroded/high-resistance (internally degraded e |
| anthropic/claude-fable-5 | hard_compound_battery_and_ground | 3 | uncoached | 85.0 | 52 | 25 | 7.50 |  |  | ground_strap corroded (high-resistance internal corrosion) — |
| anthropic/claude-fable-5 | hard_compound_battery_and_ground | 4 | uncoached | 85.0 | 52 | 25 | 7.50 |  |  | ground_strap corroded (high resistance) — root cause. The en |
| anthropic/claude-fable-5 | hard_compound_battery_and_ground | 5 | uncoached | 87.2 | 52 | 25 | 9.72 |  |  | ground_strap corroded (high-resistance engine ground). Root  |
| anthropic/claude-fable-5 | hard_intermittent_ecu_can | 1 | uncoached | 78.7 | 60 | 25 | -6.29 |  |  | ecu_can_node intermittent (intermittent CAN connection at th |
| anthropic/claude-fable-5 | hard_intermittent_ecu_can | 2 | uncoached | 86.5 | 60 | 25 | 1.45 |  |  | ecu_can_node intermittent failure (intermittent CAN communic |
| anthropic/claude-fable-5 | hard_intermittent_ecu_can | 3 | uncoached | 51.1 | 60 | 17 | -17.90 |  | ignition_switch | ecu_can_node intermittent failure (intermittently dropping o |
| anthropic/claude-fable-5 | hard_intermittent_ecu_can | 4 | uncoached | 58.4 | 60 | 17 | -10.65 |  | ignition_switch | ecu_can_node intermittent failure (intermittent CAN communic |
| anthropic/claude-fable-5 | hard_intermittent_ecu_can | 5 | uncoached | 0.0 | 0 | 17 | -13.06 |  | ignition_switch |  |
| anthropic/claude-fable-5 | medium_corroded_ground | 1 | uncoached | 94.7 | 60 | 25 | 9.71 |  |  | ground_strap corroded/high-resistance (internally degraded e |
| anthropic/claude-fable-5 | medium_corroded_ground | 2 | uncoached | 94.7 | 60 | 25 | 9.71 |  |  | ground_strap corroded/high-resistance (failed internally). E |
| anthropic/claude-fable-5 | medium_corroded_ground | 3 | uncoached | 96.0 | 60 | 25 | 11.03 |  |  | ground_strap corroded (high-resistance ground path). Battery |
| anthropic/claude-fable-5 | medium_corroded_ground | 4 | uncoached | 96.9 | 60 | 25 | 11.91 |  |  | ground_strap corroded (high-resistance ground connection). B |
| anthropic/claude-fable-5 | medium_corroded_ground | 5 | uncoached | 94.7 | 60 | 25 | 9.71 |  |  | ground_strap corroded (high-resistance engine-to-battery gro |
| anthropic/claude-fable-5 | medium_ground_red_herring_battery | 1 | uncoached | 98.4 | 60 | 25 | 13.38 |  |  | ground_strap failed — high internal resistance (corroded/deg |
| anthropic/claude-fable-5 | medium_ground_red_herring_battery | 2 | uncoached | 98.4 | 60 | 25 | 13.38 |  |  | ground_strap high-resistance/corroded (bad engine ground). V |
| anthropic/claude-fable-5 | medium_ground_red_herring_battery | 3 | uncoached | 98.4 | 60 | 25 | 13.38 |  |  | ground_strap — high resistance (internally corroded/degraded |
| anthropic/claude-fable-5 | medium_ground_red_herring_battery | 4 | uncoached | 96.3 | 60 | 25 | 11.35 |  |  | ground_strap high-resistance/corroded (internally degraded e |
| anthropic/claude-fable-5 | medium_ground_red_herring_battery | 5 | uncoached | 96.3 | 60 | 25 | 11.35 |  |  | ground_strap - high resistance (corroded/failed internally). |
| anthropic/claude-haiku-4-5 | easy_dead_battery | 1 | uncoached | 89.8 | 60 | 25 | 4.80 |  |  | battery dead; sulfated and corroded terminals |
| anthropic/claude-haiku-4-5 | easy_dead_battery | 2 | uncoached | 79.6 | 60 | 25 | -5.40 |  |  | battery dead - severely discharged (2.06V) with sulfation du |
| anthropic/claude-haiku-4-5 | easy_dead_battery | 3 | uncoached | 88.0 | 60 | 25 | 3.00 |  |  | battery dead; corroded terminals and severe voltage depletio |
| anthropic/claude-haiku-4-5 | easy_dead_battery | 4 | uncoached | 88.0 | 60 | 25 | 3.00 |  |  | battery dead; corroded terminals and severe voltage depletio |
| anthropic/claude-haiku-4-5 | easy_dead_battery | 5 | uncoached | 91.0 | 60 | 25 | 6.00 |  |  | Battery failed; internally shorted cell causing voltage coll |
| anthropic/claude-haiku-4-5 | hard_compound_battery_and_ground | 1 | uncoached | 2.1 | 0 | 17 | -6.94 |  | starter_motor | Now let's test the start again: |
| anthropic/claude-haiku-4-5 | hard_compound_battery_and_ground | 2 | uncoached | 18.4 | 22 | 17 | 1.94 |  | starter_motor | The ground looks good. Wait—let me reconsider. The problem s |
| anthropic/claude-haiku-4-5 | hard_compound_battery_and_ground | 3 | uncoached | 81.1 | 45 | 25 | 11.11 |  |  | ground_strap corroded; prevented proper current return, caus |
| anthropic/claude-haiku-4-5 | hard_compound_battery_and_ground | 4 | uncoached | 79.4 | 45 | 25 | 9.44 |  |  | ground_strap corroded, preventing proper charging circuit re |
| anthropic/claude-haiku-4-5 | hard_compound_battery_and_ground | 5 | uncoached | 7.1 | 15 | 17 | -1.94 |  | alternator | CAN is OK. Let me think about this differently. The customer |
| anthropic/claude-haiku-4-5 | hard_intermittent_ecu_can | 1 | uncoached | 0.0 | 0 | 17 | -9.19 |  | alternator | alternator; intermittent charging output failure causing var |
| anthropic/claude-haiku-4-5 | hard_intermittent_ecu_can | 2 | uncoached | 0.0 | 0 | 1 | -29.03 |  | battery, ignition_switch, starter_relay | Battery replaced. Let me test extensively now. |
| anthropic/claude-haiku-4-5 | hard_intermittent_ecu_can | 3 | uncoached | 25.4 | 60 | 17 | -28.55 |  | battery | Both look OK visually. But given the intermittent nature and |
| anthropic/claude-haiku-4-5 | hard_intermittent_ecu_can | 4 | uncoached | 0.0 | 0 | 17 | -3.87 |  | alternator | alternator failed - not charging |
| anthropic/claude-haiku-4-5 | hard_intermittent_ecu_can | 5 | uncoached | 0.0 | 0 | 17 | -15.48 |  | ground_strap | ground_strap failed (high-resistance/intermittent connection |
| anthropic/claude-haiku-4-5 | medium_corroded_ground | 1 | uncoached | 9.0 | 0 | 17 | 0.00 |  | battery | battery failed; insufficient cranking capacity (borderline/w |
| anthropic/claude-haiku-4-5 | medium_corroded_ground | 2 | uncoached | 53.6 | 60 | 17 | -15.44 |  | battery | ground_strap failed - excessive resistance causing high volt |
| anthropic/claude-haiku-4-5 | medium_corroded_ground | 3 | uncoached | 97.3 | 60 | 25 | 12.35 |  |  | ground_strap corroded; poor electrical connection causing hi |
| anthropic/claude-haiku-4-5 | medium_corroded_ground | 4 | uncoached | 91.2 | 60 | 25 | 6.18 |  |  | ground_strap corroded |
| anthropic/claude-haiku-4-5 | medium_corroded_ground | 5 | uncoached | 96.5 | 60 | 25 | 11.47 |  |  | ground_strap corroded |
| anthropic/claude-haiku-4-5 | medium_ground_red_herring_battery | 1 | uncoached | 0.0 | 0 | 0 | -33.24 |  | alternator, battery, starter_motor, starter_relay | Now let's test the start: |
| anthropic/claude-haiku-4-5 | medium_ground_red_herring_battery | 2 | uncoached | 0.0 | 0 | 9 | -14.59 |  | alternator, battery | The battery is at 12.45V and alternator output is 12.33V. St |
| anthropic/claude-haiku-4-5 | medium_ground_red_herring_battery | 3 | uncoached | 0.0 | 0 | 9 | -15.81 |  | alternator, battery | There's a tiny voltage difference at the ground (-0.07V) whi |
| anthropic/claude-haiku-4-5 | medium_ground_red_herring_battery | 4 | uncoached | 0.0 | 0 | 0 | -31.62 |  | alternator, battery, starter_motor, starter_relay | Still P0562 "System voltage low" even though we have 12.44V  |
| anthropic/claude-haiku-4-5 | medium_ground_red_herring_battery | 5 | uncoached | 0.0 | 0 | 9 | -18.24 |  | alternator, battery | Everything looks normal. We have: - New battery (12.4V) - Ne |
| anthropic/claude-sonnet-5 | easy_dead_battery | 1 | uncoached | 90.4 | 60 | 25 | 5.40 |  |  | Root cause: battery internal failure (dead/sulfated cell cau |
| anthropic/claude-sonnet-5 | easy_dead_battery | 2 | uncoached | 89.8 | 60 | 25 | 4.80 |  |  | Battery internal failure (dead/sulfated cell causing near-to |
| anthropic/claude-sonnet-5 | easy_dead_battery | 3 | uncoached | 90.4 | 60 | 25 | 5.40 |  |  | Root cause: battery failed (internally discharged/sulfated - |
| anthropic/claude-sonnet-5 | easy_dead_battery | 4 | uncoached | 88.0 | 60 | 25 | 3.00 |  |  | Root cause: Battery internally failed (sulfated/dead cell) c |
| anthropic/claude-sonnet-5 | easy_dead_battery | 5 | uncoached | 87.4 | 60 | 25 | 2.40 |  |  | Battery failed (internal fault / sulfation - dead cell), not |
| anthropic/claude-sonnet-5 | hard_compound_battery_and_ground | 1 | uncoached | 89.4 | 60 | 25 | 4.44 |  |  | Root cause: corroded/high-resistance ground_strap (engine-to |
| anthropic/claude-sonnet-5 | hard_compound_battery_and_ground | 2 | uncoached | 83.6 | 52 | 25 | 6.11 |  |  | Root cause: battery worn out/high internal resistance (aged  |
| anthropic/claude-sonnet-5 | hard_compound_battery_and_ground | 3 | uncoached | 90.3 | 60 | 25 | 5.28 |  |  | Root cause was a combination of two faults found during diag |
| anthropic/claude-sonnet-5 | hard_compound_battery_and_ground | 4 | uncoached | 91.4 | 60 | 25 | 6.39 |  |  | Root cause: battery worn out (excessive internal resistance  |
| anthropic/claude-sonnet-5 | hard_compound_battery_and_ground | 5 | uncoached | 91.7 | 60 | 25 | 6.67 |  |  | Root cause: weak/degraded battery (primary fault) combined w |
| anthropic/claude-sonnet-5 | hard_intermittent_ecu_can | 1 | uncoached | 11.4 | 0 | 25 | 1.45 |  |  |  |
| anthropic/claude-sonnet-5 | hard_intermittent_ecu_can | 2 | uncoached | 19.2 | 0 | 25 | -5.81 |  |  |  |
| anthropic/claude-sonnet-5 | hard_intermittent_ecu_can | 3 | uncoached | 11.0 | 0 | 25 | -14.03 |  |  |  |
| anthropic/claude-sonnet-5 | hard_intermittent_ecu_can | 4 | uncoached | 4.2 | 0 | 25 | -5.81 |  |  |  |
| anthropic/claude-sonnet-5 | hard_intermittent_ecu_can | 5 | uncoached | 8.1 | 0 | 25 | -16.94 |  |  |  |
| anthropic/claude-sonnet-5 | medium_corroded_ground | 1 | uncoached | 92.9 | 60 | 25 | 7.94 |  |  | Root cause: corroded/high-resistance engine ground strap (ba |
| anthropic/claude-sonnet-5 | medium_corroded_ground | 2 | uncoached | 93.8 | 60 | 25 | 8.82 |  |  | Root cause: ground_strap (engine-to-chassis/battery negative |
| anthropic/claude-sonnet-5 | medium_corroded_ground | 3 | uncoached | 94.3 | 60 | 25 | 9.26 |  |  | Root cause: ground_strap (engine-to-chassis/battery ground s |
| anthropic/claude-sonnet-5 | medium_corroded_ground | 4 | uncoached | 95.6 | 60 | 25 | 10.59 |  |  | Faulty component: ground_strap (engine-to-chassis/battery gr |
| anthropic/claude-sonnet-5 | medium_corroded_ground | 5 | uncoached | 90.7 | 60 | 25 | 5.74 |  |  | Faulty component: ground_strap (engine-to-chassis/battery gr |
| anthropic/claude-sonnet-5 | medium_ground_red_herring_battery | 1 | uncoached | 93.5 | 60 | 25 | 8.51 |  |  | Root cause: ground_strap (engine-to-chassis/battery ground s |
| anthropic/claude-sonnet-5 | medium_ground_red_herring_battery | 2 | uncoached | 91.9 | 60 | 25 | 6.89 |  |  | Faulty component: ground_strap (engine-to-chassis/body groun |
| anthropic/claude-sonnet-5 | medium_ground_red_herring_battery | 3 | uncoached | 84.6 | 60 | 25 | -0.41 |  |  | Root cause: ground_strap (engine-to-chassis ground) had exce |
| anthropic/claude-sonnet-5 | medium_ground_red_herring_battery | 4 | uncoached | 84.2 | 60 | 25 | -0.81 |  |  | Faulty component: ground_strap (engine-to-chassis ground) —  |
| anthropic/claude-sonnet-5 | medium_ground_red_herring_battery | 5 | uncoached | 94.3 | 60 | 25 | 9.32 |  |  | Root cause: ground_strap (engine-to-chassis/battery ground)  |
| google/gemini-3.5-flash | easy_dead_battery | 1 | uncoached | 70.0 | 60 | 25 | -15.00 |  |  | battery sulfated |
| google/gemini-3.5-flash | easy_dead_battery | 2 | uncoached | 64.6 | 60 | 25 | -20.40 |  |  | battery dead |
| google/gemini-3.5-flash | easy_dead_battery | 3 | uncoached | 81.4 | 60 | 25 | -3.60 |  |  | battery dead |
| google/gemini-3.5-flash | easy_dead_battery | 4 | uncoached | 65.8 | 60 | 25 | -19.20 |  |  | battery dead |
| google/gemini-3.5-flash | easy_dead_battery | 5 | uncoached | 0.4 | 0 | 25 | -24.60 |  |  |  |
| google/gemini-3.5-flash | hard_compound_battery_and_ground | 1 | uncoached | 74.2 | 45 | 25 | 4.17 |  |  | ground_strap high resistance |
| google/gemini-3.5-flash | hard_compound_battery_and_ground | 2 | uncoached | 27.5 | 0 | 25 | 2.50 |  |  |  |
| google/gemini-3.5-flash | hard_compound_battery_and_ground | 3 | uncoached | 26.4 | 0 | 25 | 1.39 |  |  |  |
| google/gemini-3.5-flash | hard_compound_battery_and_ground | 4 | uncoached | 75.8 | 45 | 25 | 5.83 |  |  | ground_strap high resistance |
| google/gemini-3.5-flash | hard_compound_battery_and_ground | 5 | uncoached | 77.2 | 45 | 25 | 7.22 |  |  | ground_strap corroded |
| google/gemini-3.5-flash | hard_intermittent_ecu_can | 1 | uncoached | 7.6 | 0 | 25 | -2.42 |  |  |  |
| google/gemini-3.5-flash | hard_intermittent_ecu_can | 2 | uncoached | 7.6 | 0 | 25 | -2.42 |  |  |  |
| google/gemini-3.5-flash | hard_intermittent_ecu_can | 3 | uncoached | 6.6 | 0 | 25 | -3.39 |  |  |  |
| google/gemini-3.5-flash | hard_intermittent_ecu_can | 4 | uncoached | 4.7 | 0 | 25 | -5.32 |  |  |  |
| google/gemini-3.5-flash | hard_intermittent_ecu_can | 5 | uncoached | 6.1 | 0 | 25 | -3.87 |  |  |  |
| google/gemini-3.5-flash | medium_corroded_ground | 1 | uncoached | 89.4 | 60 | 25 | 4.41 |  |  | ground_strap corroded |
| google/gemini-3.5-flash | medium_corroded_ground | 2 | uncoached | 86.8 | 60 | 25 | 1.76 |  |  | ground_strap high_resistance |
| google/gemini-3.5-flash | medium_corroded_ground | 3 | uncoached | 91.6 | 60 | 25 | 6.62 |  |  | ground_strap high resistance |
| google/gemini-3.5-flash | medium_corroded_ground | 4 | uncoached | 87.7 | 60 | 25 | 2.65 |  |  | ground_strap high resistance  Supporting reasoning: 1. Attem |
| google/gemini-3.5-flash | medium_corroded_ground | 5 | uncoached | 90.7 | 60 | 25 | 5.74 |  |  | ground_strap high resistance |
| google/gemini-3.5-flash | medium_ground_red_herring_battery | 1 | uncoached | 89.0 | 60 | 25 | 4.05 |  |  | ground_strap high resistance |
| google/gemini-3.5-flash | medium_ground_red_herring_battery | 2 | uncoached | 85.8 | 60 | 25 | 0.81 |  |  | ground_strap corroded |
| google/gemini-3.5-flash | medium_ground_red_herring_battery | 3 | uncoached | 90.7 | 60 | 25 | 5.68 |  |  | ground_strap high resistance |
| google/gemini-3.5-flash | medium_ground_red_herring_battery | 4 | uncoached | 92.7 | 60 | 25 | 7.70 |  |  | ground_strap high resistance |
| google/gemini-3.5-flash | medium_ground_red_herring_battery | 5 | uncoached | 92.3 | 60 | 25 | 7.30 |  |  | ground_strap high resistance |
| grok/grok-4 | easy_dead_battery | 1 | uncoached | 95.8 | 60 | 25 | 10.80 |  |  | battery failed (dead/corroded) |
| grok/grok-4 | easy_dead_battery | 2 | uncoached | 98.8 | 60 | 25 | 13.80 |  |  | battery failed (dead) |
| grok/grok-4 | easy_dead_battery | 3 | uncoached | 69.4 | 30 | 25 | 14.40 |  |  | battery failed |
| grok/grok-4 | easy_dead_battery | 4 | uncoached | 97.0 | 60 | 25 | 12.00 |  |  | battery dead |
| grok/grok-4 | easy_dead_battery | 5 | uncoached | 97.6 | 60 | 25 | 12.60 |  |  | battery failed (dead) |
| grok/grok-4 | hard_compound_battery_and_ground | 1 | uncoached | 40.0 | 15 | 25 | 15.00 |  |  | battery weak (aged) |
| grok/grok-4 | hard_compound_battery_and_ground | 2 | uncoached | 76.4 | 45 | 25 | 6.39 |  |  | ground_strap high resistance |
| grok/grok-4 | hard_compound_battery_and_ground | 3 | uncoached | 81.4 | 45 | 25 | 11.39 |  |  | ground_strap corroded (causing high resistance and voltage d |
| grok/grok-4 | hard_compound_battery_and_ground | 4 | uncoached | 80.3 | 45 | 25 | 10.28 |  |  | ground_strap high resistance (voltage drop) |
| grok/grok-4 | hard_compound_battery_and_ground | 5 | uncoached | 32.5 | 8 | 25 | 15.00 |  |  | battery aged (low voltage) |
| grok/grok-4 | hard_intermittent_ecu_can | 1 | uncoached | 25.0 | 0 | 25 | 15.00 |  |  | ignition_switch intermittent contact |
| grok/grok-4 | hard_intermittent_ecu_can | 2 | uncoached | 7.0 | 30 | 9 | -15.97 |  | fusible_link, ignition_switch | ecu_can_node faulty |
| grok/grok-4 | hard_intermittent_ecu_can | 3 | uncoached | 62.7 | 60 | 17 | -6.29 |  | ignition_switch | ecu_can_node intermittent failure |
| grok/grok-4 | hard_intermittent_ecu_can | 4 | uncoached | 59.8 | 60 | 17 | -9.19 |  | ignition_switch | ecu_can_node intermittent failure |
| grok/grok-4 | hard_intermittent_ecu_can | 5 | uncoached | 5.6 | 0 | 17 | 11.61 |  | ignition_switch | ignition_switch intermittent failure |
| grok/grok-4 | medium_corroded_ground | 1 | uncoached | 97.8 | 60 | 25 | 12.79 |  |  | ground_strap high resistance |
| grok/grok-4 | medium_corroded_ground | 2 | uncoached | 98.7 | 60 | 25 | 13.68 |  |  | ground_strap high resistance (corroded internally) |
| grok/grok-4 | medium_corroded_ground | 3 | uncoached | 96.5 | 60 | 25 | 11.47 |  |  | ground_strap high resistance |
| grok/grok-4 | medium_corroded_ground | 4 | uncoached | 95.6 | 60 | 25 | 10.59 |  |  | ground_strap high resistance (corroded) |
| grok/grok-4 | medium_corroded_ground | 5 | uncoached | 97.8 | 60 | 25 | 12.79 |  |  | ground_strap high resistance |
| grok/grok-4 | medium_ground_red_herring_battery | 1 | uncoached | 96.8 | 60 | 25 | 11.76 |  |  | ground_strap high resistance |
| grok/grok-4 | medium_ground_red_herring_battery | 2 | uncoached | 100.0 | 60 | 25 | 15.00 |  |  | ground_strap high resistance |
| grok/grok-4 | medium_ground_red_herring_battery | 3 | uncoached | 90.3 | 60 | 25 | 5.27 |  |  | ground_strap high resistance (voltage drop) |
| grok/grok-4 | medium_ground_red_herring_battery | 4 | uncoached | 99.2 | 60 | 25 | 14.19 |  |  | ground_strap high resistance |
| grok/grok-4 | medium_ground_red_herring_battery | 5 | uncoached | 70.2 | 60 | 17 | 1.22 |  | battery | ground_strap high resistance |
| openai/gpt-5.5 | easy_dead_battery | 1 | uncoached | 94.0 | 60 | 25 | 9.00 |  |  | battery internally failed/shorted; replaced battery and veri |
| openai/gpt-5.5 | easy_dead_battery | 2 | uncoached | 87.4 | 60 | 25 | 2.40 |  |  | battery internally failed / severely discharged. Initial key |
| openai/gpt-5.5 | easy_dead_battery | 3 | uncoached | 92.2 | 60 | 25 | 7.20 |  |  | battery internally failed / severely discharged. Battery mea |
| openai/gpt-5.5 | easy_dead_battery | 4 | uncoached | 91.6 | 60 | 25 | 6.60 |  |  | battery internally failed / deeply discharged. Key-off batte |
| openai/gpt-5.5 | easy_dead_battery | 5 | uncoached | 95.2 | 60 | 25 | 10.20 |  |  | battery internally failed/discharged to 2.13 V. Replaced the |
| openai/gpt-5.5 | hard_compound_battery_and_ground | 1 | uncoached | 88.9 | 52 | 25 | 11.39 |  |  | ground_strap high resistance causing excessive cranking volt |
| openai/gpt-5.5 | hard_compound_battery_and_ground | 2 | uncoached | 85.0 | 52 | 25 | 7.50 |  |  | battery failed/low state-of-charge under load and ground_str |
| openai/gpt-5.5 | hard_compound_battery_and_ground | 3 | uncoached | 81.4 | 45 | 25 | 11.39 |  |  | ground_strap high resistance/internal corrosion; excessive e |
| openai/gpt-5.5 | hard_compound_battery_and_ground | 4 | uncoached | 92.5 | 60 | 25 | 7.50 |  |  | battery failed/weak under load and ground_strap high-resista |
| openai/gpt-5.5 | hard_compound_battery_and_ground | 5 | uncoached | 91.7 | 60 | 25 | 6.67 |  |  | battery failed/low-capacity, with ground_strap high-resistan |
| openai/gpt-5.5 | hard_intermittent_ecu_can | 1 | uncoached | 0.0 | 0 | 17 | -21.77 |  | ignition_switch |  |
| openai/gpt-5.5 | hard_intermittent_ecu_can | 2 | uncoached | 47.2 | 60 | 17 | -21.77 |  | ignition_switch | ecu_can_node intermittent internal fault causing CAN communi |
| openai/gpt-5.5 | hard_intermittent_ecu_can | 3 | uncoached | 79.2 | 60 | 25 | -5.81 |  |  | ecu_can_node intermittent communication failure/internal CAN |
| openai/gpt-5.5 | hard_intermittent_ecu_can | 4 | uncoached | 8.6 | 0 | 25 | -16.45 |  |  |  |
| openai/gpt-5.5 | hard_intermittent_ecu_can | 5 | uncoached | 71.0 | 60 | 25 | -14.03 |  |  | ecu_can_node internal intermittent failure; ECM/CAN node int |
| openai/gpt-5.5 | medium_corroded_ground | 1 | uncoached | 94.7 | 60 | 25 | 9.71 |  |  | ground_strap corroded/high resistance; excessive engine-to-b |
| openai/gpt-5.5 | medium_corroded_ground | 2 | uncoached | 94.7 | 60 | 25 | 9.71 |  |  | ground_strap high resistance/corroded connection causing exc |
| openai/gpt-5.5 | medium_corroded_ground | 3 | uncoached | 94.7 | 60 | 25 | 9.71 |  |  | ground_strap high resistance/corroded internally causing exc |
| openai/gpt-5.5 | medium_corroded_ground | 4 | uncoached | 96.9 | 60 | 25 | 11.91 |  |  | ground_strap high resistance; excessive engine-to-battery gr |
| openai/gpt-5.5 | medium_corroded_ground | 5 | uncoached | 94.7 | 60 | 25 | 9.71 |  |  | ground_strap high resistance/corroded connection; excessive  |
| openai/gpt-5.5 | medium_ground_red_herring_battery | 1 | uncoached | 91.5 | 60 | 25 | 6.49 |  |  | ground_strap high resistance/poor engine ground. Excessive v |
| openai/gpt-5.5 | medium_ground_red_herring_battery | 2 | uncoached | 95.5 | 60 | 25 | 10.54 |  |  | ground_strap high resistance; excessive voltage drop on engi |
| openai/gpt-5.5 | medium_ground_red_herring_battery | 3 | uncoached | 94.3 | 60 | 25 | 9.32 |  |  | ground_strap high resistance/corroded connection causing exc |
| openai/gpt-5.5 | medium_ground_red_herring_battery | 4 | uncoached | 99.6 | 60 | 25 | 14.59 |  |  | ground_strap excessive resistance / poor engine-to-battery g |
| openai/gpt-5.5 | medium_ground_red_herring_battery | 5 | uncoached | 94.3 | 60 | 25 | 9.32 |  |  | ground_strap high resistance; excessive voltage drop on engi |
| openrouter/meta-llama/llama-3.1-8b-instruct | easy_dead_battery | 1 | uncoached | 0.0 | 0 | 17 | 5.40 |  | starter_relay | starter_relay faulty |
| openrouter/meta-llama/llama-3.1-8b-instruct | easy_dead_battery | 2 | uncoached | 0.0 | 0 | 17 | -24.00 |  | fusible_link | fusible_link blown |
| openrouter/meta-llama/llama-3.1-8b-instruct | easy_dead_battery | 3 | uncoached | 0.0 | 0 | 17 | -0.60 |  | starter_relay | starter_relay blown |
| openrouter/meta-llama/llama-3.1-8b-instruct | easy_dead_battery | 4 | uncoached | 0.0 | 0 | 17 | -0.60 |  | starter_relay | fusible_link blown |
| openrouter/meta-llama/llama-3.1-8b-instruct | easy_dead_battery | 5 | uncoached | 0.0 | 0 | 17 | -3.60 |  | ground_strap | ground_strap open |
| openrouter/meta-llama/llama-3.1-8b-instruct | hard_compound_battery_and_ground | 1 | uncoached | 10.0 | 0 | 25 | 0.00 | yes |  |  |
| openrouter/meta-llama/llama-3.1-8b-instruct | hard_compound_battery_and_ground | 2 | uncoached | 25.0 | 0 | 25 | 15.00 |  |  | There is no next step. The job is closed, and the vehicle ha |
| openrouter/meta-llama/llama-3.1-8b-instruct | hard_compound_battery_and_ground | 3 | uncoached | 0.0 | 0 | 9 | 11.11 |  | starter_motor, starter_relay | starter_motor worn out |
| openrouter/meta-llama/llama-3.1-8b-instruct | hard_compound_battery_and_ground | 4 | uncoached | 0.0 | 0 | 1 | 5.00 |  | alternator, starter_motor, starter_relay | alternator not charging |
| openrouter/meta-llama/llama-3.1-8b-instruct | hard_compound_battery_and_ground | 5 | uncoached | 7.1 | 0 | 17 | 13.06 |  | starter_motor | starter_motor bad contacts |
| openrouter/meta-llama/llama-3.1-8b-instruct | hard_intermittent_ecu_can | 1 | uncoached | 25.0 | 0 | 25 | 15.00 |  |  |  |
| openrouter/meta-llama/llama-3.1-8b-instruct | hard_intermittent_ecu_can | 2 | uncoached | 10.0 | 0 | 25 | 0.00 | yes |  |  |
| openrouter/meta-llama/llama-3.1-8b-instruct | hard_intermittent_ecu_can | 3 | uncoached | 10.0 | 0 | 25 | 0.00 | yes |  |  |
| openrouter/meta-llama/llama-3.1-8b-instruct | hard_intermittent_ecu_can | 4 | uncoached | 3.7 | 0 | 17 | 9.68 |  | starter_relay |  |
| openrouter/meta-llama/llama-3.1-8b-instruct | hard_intermittent_ecu_can | 5 | uncoached | 0.0 | 0 | 0 | -56.61 |  | alternator, battery, fusible_link, ground_strap, starter_motor, starter_relay | starter_relay sticking |
| openrouter/meta-llama/llama-3.1-8b-instruct | medium_corroded_ground | 1 | uncoached | 25.0 | 0 | 25 | 15.00 |  |  | starter_motor worn brushes <function=finish>{} |
| openrouter/meta-llama/llama-3.1-8b-instruct | medium_corroded_ground | 2 | uncoached | 9.0 | 0 | 17 | 15.00 |  | battery |  |
| openrouter/meta-llama/llama-3.1-8b-instruct | medium_corroded_ground | 3 | uncoached | 5.5 | 0 | 17 | 11.47 |  | alternator | alternator overcharging |
| openrouter/meta-llama/llama-3.1-8b-instruct | medium_corroded_ground | 4 | uncoached | 0.0 | 0 | 9 | 3.53 |  | alternator, battery | alternator charging system malfunction |
| openrouter/meta-llama/llama-3.1-8b-instruct | medium_corroded_ground | 5 | uncoached | 3.3 | 0 | 17 | 9.26 |  | battery | battery bad |
| openrouter/meta-llama/llama-3.1-8b-instruct | medium_ground_red_herring_battery | 1 | uncoached | 3.7 | 0 | 17 | 9.73 |  | fusible_link | fusible_link blown |
| openrouter/meta-llama/llama-3.1-8b-instruct | medium_ground_red_herring_battery | 2 | uncoached | 25.0 | 0 | 25 | 15.00 |  |  |  |
| openrouter/meta-llama/llama-3.1-8b-instruct | medium_ground_red_herring_battery | 3 | uncoached | 3.3 | 0 | 17 | 9.32 |  | starter_motor | starter_motor failed to engage |
| openrouter/meta-llama/llama-3.1-8b-instruct | medium_ground_red_herring_battery | 4 | uncoached | 8.6 | 0 | 17 | 14.59 |  | alternator | alternator faulty, not charging |
| openrouter/meta-llama/llama-3.1-8b-instruct | medium_ground_red_herring_battery | 5 | uncoached | 5.8 | 0 | 17 | 11.76 |  | starter_relay | starter_relay malfunctioning |
| openrouter/mistralai/ministral-3b-2512 | easy_dead_battery | 1 | uncoached | 97.0 | 60 | 25 | 12.00 |  |  | battery dead |
| openrouter/mistralai/ministral-3b-2512 | easy_dead_battery | 2 | uncoached | 92.2 | 60 | 25 | 7.20 |  |  | battery dead |
| openrouter/mistralai/ministral-3b-2512 | easy_dead_battery | 3 | uncoached | 97.0 | 60 | 25 | 12.00 |  |  | battery dead |
| openrouter/mistralai/ministral-3b-2512 | easy_dead_battery | 4 | uncoached | 93.4 | 60 | 25 | 8.40 |  |  | battery low voltage due to corrosion and sulfation. |
| openrouter/mistralai/ministral-3b-2512 | easy_dead_battery | 5 | uncoached | 87.4 | 60 | 25 | 2.40 |  |  | battery terminals corroded and sulfated, causing low battery |
| openrouter/mistralai/ministral-3b-2512 | hard_compound_battery_and_ground | 1 | uncoached | 0.0 | 8 | 9 | -9.44 |  | alternator, starter_relay | The battery was replaced, and the alternator output is now a |
| openrouter/mistralai/ministral-3b-2512 | hard_compound_battery_and_ground | 2 | uncoached | 0.0 | 0 | 9 | 8.06 |  | alternator, starter_motor | starter_motor failed to engage properly, causing slow cranki |
| openrouter/mistralai/ministral-3b-2512 | hard_compound_battery_and_ground | 3 | uncoached | 0.0 | 0 | 17 | 0.83 |  | alternator |  |
| openrouter/mistralai/ministral-3b-2512 | hard_compound_battery_and_ground | 4 | uncoached | 4.3 | 0 | 17 | 10.28 |  | alternator | alternator failed to charge properly during cranking and did |
| openrouter/mistralai/ministral-3b-2512 | hard_compound_battery_and_ground | 5 | uncoached | 1.2 | 0 | 17 | 7.22 |  | starter_motor | starter_relay failed to engage properly, causing intermitten |
| openrouter/mistralai/ministral-3b-2512 | hard_intermittent_ecu_can | 1 | uncoached | 0.0 | 0 | 9 | -4.35 |  | ignition_switch, starter_relay | starter_relay failing intermittently. |
| openrouter/mistralai/ministral-3b-2512 | hard_intermittent_ecu_can | 2 | uncoached | 0.0 | 0 | 9 | -8.71 |  | battery, starter_motor | battery weak or failing |
| openrouter/mistralai/ministral-3b-2512 | hard_intermittent_ecu_can | 3 | uncoached | 0.0 | 0 | 9 | -9.68 |  | alternator, starter_relay | alternator failing intermittently |
| openrouter/mistralai/ministral-3b-2512 | hard_intermittent_ecu_can | 4 | uncoached | 6.1 | 0 | 17 | 12.10 |  | alternator | alternator failed to charge properly, causing inconsistent c |
| openrouter/mistralai/ministral-3b-2512 | hard_intermittent_ecu_can | 5 | uncoached | 0.8 | 0 | 17 | 6.77 |  | starter_relay | starter_relay failed intermittently, causing the starter mot |
| openrouter/mistralai/ministral-3b-2512 | medium_corroded_ground | 1 | uncoached | 0.0 | 0 | 9 | -3.53 |  | alternator, starter_relay | starter_relay not holding properly, intermittent power deliv |
| openrouter/mistralai/ministral-3b-2512 | medium_corroded_ground | 2 | uncoached | 0.0 | 0 | 9 | -2.21 |  | battery, starter_motor | starter_motor failed to crank properly, likely due to intern |
| openrouter/mistralai/ministral-3b-2512 | medium_corroded_ground | 3 | uncoached | 0.0 | 0 | 9 | -3.97 |  | starter_motor, starter_relay | starter_motor failed to crank properly, likely due to weak o |
| openrouter/mistralai/ministral-3b-2512 | medium_corroded_ground | 4 | uncoached | 0.0 | 0 | 9 | -4.41 |  | battery, starter_motor | battery weak or failing |
| openrouter/mistralai/ministral-3b-2512 | medium_corroded_ground | 5 | uncoached | 0.0 | 0 | 9 | -13.24 |  | alternator, starter_relay |  |
| openrouter/mistralai/ministral-3b-2512 | medium_ground_red_herring_battery | 1 | uncoached | 0.0 | 0 | 9 | -3.65 |  | starter_motor, starter_relay | starter_motor failed to engage properly, likely due to inter |
| openrouter/mistralai/ministral-3b-2512 | medium_ground_red_herring_battery | 2 | uncoached | 0.0 | 0 | 9 | -2.03 |  | starter_motor, starter_relay | starter_motor failed to engage properly, likely due to a fau |
| openrouter/mistralai/ministral-3b-2512 | medium_ground_red_herring_battery | 3 | uncoached | 0.0 | 0 | 1 | -27.57 |  | fusible_link, starter_motor, starter_relay | starter_relay failed to hold power, likely due to internal c |
| openrouter/mistralai/ministral-3b-2512 | medium_ground_red_herring_battery | 4 | uncoached | 0.0 | 0 | 9 | -25.54 |  | starter_motor, starter_relay | starter_motor failed to engage properly, likely due to inter |
| openrouter/mistralai/ministral-3b-2512 | medium_ground_red_herring_battery | 5 | uncoached | 96.0 | 60 | 25 | 10.95 |  |  | ground_strap corroded or loose |
| openrouter/qwen/qwen-2.5-7b-instruct | easy_dead_battery | 1 | uncoached | 88.0 | 60 | 25 | 3.00 |  |  | battery dead |
| openrouter/qwen/qwen-2.5-7b-instruct | easy_dead_battery | 2 | uncoached | 61.6 | 30 | 25 | 6.60 |  |  | battery weak |
| openrouter/qwen/qwen-2.5-7b-instruct | easy_dead_battery | 3 | uncoached | 63.4 | 30 | 25 | 8.40 |  |  | battery weak |
| openrouter/qwen/qwen-2.5-7b-instruct | easy_dead_battery | 4 | uncoached | 92.8 | 60 | 25 | 7.80 |  |  | finish("battery", "dead") |
| openrouter/qwen/qwen-2.5-7b-instruct | easy_dead_battery | 5 | uncoached | 66.4 | 30 | 25 | 11.40 |  |  | battery corrosion |
| openrouter/qwen/qwen-2.5-7b-instruct | hard_compound_battery_and_ground | 1 | uncoached | 11.5 | 8 | 17 | 10.00 |  | alternator | alternator fails to charge the battery during cranking |
| openrouter/qwen/qwen-2.5-7b-instruct | hard_compound_battery_and_ground | 2 | uncoached | 19.2 | 8 | 25 | 1.67 |  |  | battery failing |
| openrouter/qwen/qwen-2.5-7b-instruct | hard_compound_battery_and_ground | 3 | uncoached | 0.0 | 8 | 1 | -14.44 |  | ignition_switch, starter_motor, starter_relay | The visual inspection of the starter circuit and additional  |
| openrouter/qwen/qwen-2.5-7b-instruct | hard_compound_battery_and_ground | 4 | uncoached | 32.5 | 8 | 25 | 15.00 |  |  | Let's attempt to start the vehicle after replacing the batte |
| openrouter/qwen/qwen-2.5-7b-instruct | hard_compound_battery_and_ground | 5 | uncoached | 78.6 | 45 | 25 | 8.61 |  |  | The vehicle has started successfully after replacing the gro |
| openrouter/qwen/qwen-2.5-7b-instruct | hard_intermittent_ecu_can | 1 | uncoached | 2.7 | 0 | 17 | 8.71 |  | starter_relay | starter_relay failed to engage properly |
| openrouter/qwen/qwen-2.5-7b-instruct | hard_intermittent_ecu_can | 2 | uncoached | 5.6 | 0 | 17 | 11.61 |  | starter_relay | starter_relay blown |
| openrouter/qwen/qwen-2.5-7b-instruct | hard_intermittent_ecu_can | 3 | uncoached | 0.0 | 0 | 9 | 0.00 |  | fusible_link, starter_relay | fusible_link blown |
| openrouter/qwen/qwen-2.5-7b-instruct | hard_intermittent_ecu_can | 4 | uncoached | 0.0 | 0 | 17 | -2.90 |  | starter_relay | starter_relay malfunctioning |
| openrouter/qwen/qwen-2.5-7b-instruct | hard_intermittent_ecu_can | 5 | uncoached | 0.0 | 0 | 9 | 2.42 |  | ignition_switch, starter_relay | ignition_switch faulty |
| openrouter/qwen/qwen-2.5-7b-instruct | medium_corroded_ground | 1 | uncoached | 0.0 | 0 | 1 | -45.44 |  | fusible_link, starter_motor, starter_relay | starter_motor worn out |
| openrouter/qwen/qwen-2.5-7b-instruct | medium_corroded_ground | 2 | uncoached | 0.0 | 0 | 9 | 3.97 |  | starter_motor, starter_relay | starter_motor failed |
| openrouter/qwen/qwen-2.5-7b-instruct | medium_corroded_ground | 3 | uncoached | 0.0 | 0 | 9 | -35.29 |  | battery, starter_relay | 发动机仍然慢速启动，这与之前的测试结果一致，进一步确认电力供应可能存在问题。由于电池已经更换，且电池正极到点火开关和继电 |
| openrouter/qwen/qwen-2.5-7b-instruct | medium_corroded_ground | 4 | uncoached | 0.0 | 0 | 1 | -17.21 |  | alternator, battery, starter_relay | starter_relay faulty |
| openrouter/qwen/qwen-2.5-7b-instruct | medium_corroded_ground | 5 | uncoached | 0.0 | 0 | 1 | -17.21 |  | alternator, battery, starter_relay | alternator bad |
| openrouter/qwen/qwen-2.5-7b-instruct | medium_ground_red_herring_battery | 1 | uncoached | 0.0 | 0 | 17 | -4.05 |  | alternator | alternator faulty |
| openrouter/qwen/qwen-2.5-7b-instruct | medium_ground_red_herring_battery | 2 | uncoached | 0.0 | 0 | 0 | -20.27 |  | alternator, battery, fusible_link, starter_motor | alternator bad |
| openrouter/qwen/qwen-2.5-7b-instruct | medium_ground_red_herring_battery | 3 | uncoached | 0.0 | 0 | 1 | -8.11 |  | alternator, battery, starter_motor | starter_motor failed |
| openrouter/qwen/qwen-2.5-7b-instruct | medium_ground_red_herring_battery | 4 | uncoached | 0.0 | 0 | 1 | -16.62 |  | alternator, ecu_can_node, starter_motor | starter_motor faulty |
| openrouter/qwen/qwen-2.5-7b-instruct | medium_ground_red_herring_battery | 5 | uncoached | 0.0 | 0 | 1 | -9.73 |  | alternator, battery, starter_relay | Ronaldo {"name": "attempt_start", "arguments": {}}  Ronaldo  |
