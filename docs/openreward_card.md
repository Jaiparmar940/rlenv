# no-start-env

**By [Second Nature](https://snlabs.dev) · v0.1 · MIT ·
[GitHub](https://github.com/Jaiparmar940/rlenv)**

An agentic diagnostic environment and eval: a simulated vehicle with electrical
no-start and charging faults, realistic shop tools, and a cheat-resistant
grader. A car will not start; the agent gets the customer complaint and seven
tools, and has to localize the fault, replace the right part, and confirm the
repair with a successful start. Nothing tells it whether the part it replaced
was faulty.

The vehicle is a resistance-network circuit model: faults perturb one physical
resistance (or the battery's internal parameters) and every voltage the agent
can measure is computed from V = I×R. Symptoms are therefore physically
consistent across probe points and engine states — the environment rewards
genuine electrical localization and punishes plausible-sounding guesswork.

This is the OpenReward (ORS) serving of the published v0.1 benchmark. Full
writeup, failure-mode taxonomy, and per-scenario results:
[WRITEUP.md](https://github.com/Jaiparmar940/rlenv/blob/main/WRITEUP.md).

## Capabilities tested

- Physical-system fault localization from two-point voltage measurements
  (choosing the *right* reference points, not just reading numbers)
- Hypothesis discrimination under a deliberate red herring (a tempting-looking
  battery that passes a load test)
- Intermittent-fault reasoning (a fault that only manifests on some probes)
- Compound-fault reasoning (two genuine faults; neither repair alone fixes
  the car)
- Repair discipline and cost awareness: measure before swapping parts, verify
  the fix with a successful start

## Tasks

One split, `test`, with 5 tasks. Task specs are opaque
(`{"task_id": "ns-01", "tier": "easy"}`) — scenario names encode ground truth
and are held server-side, so nothing in the task list can leak the answer into
an agent's context. Tiers: 1 easy, 2 medium, 2 hard.

Every task is seeded and fully deterministic: identical action sequences
produce identical observations (meter noise included) and identical rewards,
across runs and processes.

## Tools

`scan_dtcs`, `read_pid`, `measure_voltage(point_a, point_b, engine_state)`,
`visual_inspect(area)`, `replace_part(component)`, `attempt_start`, and
`finish(answer)` to submit the final diagnosis and end the episode. Tool
outputs are instrument readings only — no explanations, and nothing that
reveals component health or fault state. A hidden terminal tool grades the
rollout if a harness ends it on a plain assistant message (the message is
treated as the diagnosis).

## Reward structure

Sparse, continuous, emitted once at episode end: **reward = grader score /
100** (range 0–1). The grader reads ground-truth world state only — agent
prose is never trusted, and symptom relief from swapping the wrong part does
not count. The native 0–100 rubric:

- **Root cause (60):** correct component + failure mode; half credit for
  component only. On the compound task the budget splits 45 (primary) / 15
  (secondary).
- **Parts discipline (25):** −8 per innocent part replaced (also debits the
  total, so a parts cannon cannot ride root-cause points to a pass).
- **Cost efficiency (15):** time-only, linear from 1× expert time to 0 at 2×,
  negative beyond.
- **Anti-cheat:** finishing with no diagnostic probes before the first
  replacement caps the score at 40; a correct diagnosis without a repaired,
  start-verified vehicle takes a flat −15.

The full subscore breakdown ships in the terminal tool output's `metadata`
(display-formatted, matching the Inspect log format, plus numeric
`score_0_100`).

## Prompt parity with the published benchmark

`get_prompt()` returns two text blocks, verbatim the strings from the
published Inspect run: **block 1 is the system prompt** (uncoached variant:
role, tool reference, job definition, cost one-liner — no strategy, no grader
rules), **block 2 is the user message** (customer complaint + task statement).
ORS blocks carry no role; harnesses that support a system role should map
block 1 there. Both prompt blocks are verified byte-identical to the
published run's wire-level API payloads (see `results/parity_diag/` in the
repo). Tool names and the `finish(answer)` call match; tool description and
schema serialization currently differ from Inspect's in documented ways
(parity work tracked in `results/parity_diag/REPORT.md`), so treat scores as
comparable with, not identical to, the published table below.

## Environment difficulty (published v0.1 results)

Uncoached prompt, 5 scenarios × 5 epochs per model, 225 episodes:

| tier | model | mean (0–100) | root-ok | verified-fix |
| --- | --- | --- | --- | --- |
| frontier | claude-fable-5 | 86.0 | 19/25 | 25/25 |
| frontier | gpt-5.5 | 82.3 | 20/25 | 25/25 |
| frontier | grok-4 | 74.9 | 16/25 | 21/25 |
| frontier | claude-sonnet-5 | 74.5 | 19/25 | 23/25 |
| deployment | gemini-3.5-flash | 59.7 | 14/25 | 20/25 |
| deployment | claude-haiku-4-5 | 39.9 | 10/25 | 13/25 |
| open 3B-8B | ministral-3b | 23.0 | 6/25 | 6/25 |
| open 3B-8B | qwen-2.5-7b | 20.9 | 2/25 | 6/25 |
| open 3B-8B | llama-3.1-8b | 7.2 | 0/25 | 0/25 |

Frontier models clear the easy/medium tiers (59/60 full root-cause credit) but
not the hard tier (15/40); no model passes every episode. Best-worst
separation: 78.8 points.

## Time horizon

Multi-turn, tool-calling. Expert episodes run 4–11 actions; the published runs
capped conversations at 50 messages. Episodes end when the agent calls
`finish` (or on the harness's own turn limit — unterminated episodes emit no
reward unless the harness invokes the terminal tool).

## Compute requirements

None beyond the environment server itself — the simulation is a pure
in-process circuit computation. No sandbox, no GPU, no secrets, no external
network calls.

## Data

All scenario definitions, physics constants, and grading logic live in the
[GitHub repo](https://github.com/Jaiparmar940/rlenv) (the benchmark is
public). Ground truth never appears in any agent-visible surface: prompts,
tool outputs, task specs, and error messages are audited for leakage (see
`results/audit.md` in the repo; the ORS surface is covered by
`tests/test_openreward_adapter.py`).

## Safety

Benign, fully simulated automotive electrical diagnosis. No real-world
actuation, no web access, no user data, no dual-use content.

## License & citation

MIT. Cite via the repo's
[CITATION.cff](https://github.com/Jaiparmar940/rlenv/blob/main/CITATION.cff).

## Contact

Second Nature — [snlabs.dev](https://snlabs.dev) · Jaivir Parmar
