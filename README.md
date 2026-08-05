# rlenv

Verified environments and evals for physical reasoning, built by [Second Nature Labs](https://snlabs.dev).

## Why these environments exist

Frontier coding models wrote the physics for the first environment in this repo, and four times they wrote physics that was confidently wrong and *passed the automated test suite*: load-sag inversion, a downstream node reading above its upstream node, a red-herring battery that drifted into being a second real fault, and a ground fault too small to localize. All four were caught by a human playing the environment with a technician's eye.

> Generation is cheap and getting cheaper. Verification is not. That asymmetry is the reason this repo exists.

## Environments

| Environment | What it is |
|---|---|
| [**no-start-env**](no-start-env.md) | Agentic vehicle no-start diagnosis: node-potential physics, cheat-resistant grader, Inspect-compatible, live on [OpenReward](https://openreward.ai/jaivir/no-start-env). |
| [**decision-layer**](decision-layer/) | Hidden-state kitchen task on RoboCasa/MuJoCo: inspect, infer, intervene — graded separately from motor execution (oracle by design). |

## Headline results — no-start-env

| Tier | Model | Mean |
|---|---|---:|
| Frontier | `anthropic/claude-fable-5` | 86.0 |
| Frontier | `openai/gpt-5.5` | 82.3 |
| Frontier | `grok/grok-4` | 74.9 |
| Frontier | `anthropic/claude-sonnet-5` | 74.5 |
| Deployment | `google/gemini-3.5-flash` | 59.7 |
| Deployment | `anthropic/claude-haiku-4-5` | 39.9 |
| Open 3B–8B | `mistralai/ministral-3b` | 23.0 |
| Open 3B–8B | `qwen/qwen-2.5-7b` | 20.9 |
| Open 3B–8B | `meta-llama/llama-3.1-8b` | 7.2 |

Frontier models have cleared textbook short-horizon automotive diagnosis — 59 of 60 easy/medium episodes with full root-cause credit — but the hard tier is not saturated: frontier models earn full root-cause credit on just 15 of 40 hard episodes, and no model of the nine passes every episode. The deployment tier — the cost/latency class that would actually run on a robot — fails a tier earlier: it loses the red-herring scenario most of the time, typically anchoring on the decoy battery and swapping innocent parts on a car whose fault is a $25 ground strap.

Full table, metric definitions, and methodology: [no-start-env.md](no-start-env.md).

## decision-layer

![decision-layer demo: scripted expert solving the hidden-state kitchen task](decision-layer/demo.gif)

*The arm never actuates; the decision layer is the system under test.*

## Shared discipline

Every environment ships with a multi-part grader, an adversarial audit, and a statement of what the grader does not yet catch: for no-start-env, the [audit](results/audit.md) and the [Limitations section](no-start-env.md#limitations); for decision-layer, [AUDIT.md](decision-layer/AUDIT.md) and [LIMITS.md](decision-layer/handoff/LIMITS.md).

## Contact

jaivir@snlabs.dev · [snlabs.dev](https://snlabs.dev)
