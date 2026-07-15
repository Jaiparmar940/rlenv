# Where frontier models stop being able to fix a car

**no-start-env** is an agentic diagnostic environment and evaluation: a simulated
vehicle with electrical no-start and charging faults, a set of realistic shop
tools, and a grader that scores what the agent actually did to the vehicle rather
than what it said about it. It runs on [Inspect](https://inspect.aisi.org.uk), so
a lab can point it at a model and get a number without adopting anything.

This writeup covers what the environment is, what the current models score on it,
how the physics and the grader work, why a human had to verify the physics that
frontier coding models wrote, and what it does not cover.

Published 2026-07-13. Code: this repo. Results: [`results/scale_curve.md`](results/scale_curve.md).

---

## 1. What this is

A car will not start. The agent gets the customer complaint and seven tools:
`scan_dtcs`, `read_pid`, `measure_voltage`, `visual_inspect`, `replace_part`,
`attempt_start`, and `finish`. It has no other access to the vehicle — no
narration, no hints, no confirmation that a part it replaced was faulty. It must
localize the fault, replace the right part, and confirm the repair with a
successful start.

Four properties are the point of the thing:

- **The readings are computed, not written.** The circuit is a resistance network
  with a battery source. A fault changes exactly one resistance (or a battery
  internal parameter). Every voltage the agent reads falls out of `V = I x R`.
  Nobody hand-authors an output voltage anywhere in the codebase, which is what
  makes a scenario's readings mutually consistent under measurements the author
  never anticipated.
- **It is deterministic.** Every scenario is seeded. Identical runs produce
  identical observations and identical scores. Meter noise is seeded too.
- **The grader is cheat-resistant.** It reads ground-truth world state — the
  injected fault, the parts actually replaced, the probe history — and ignores the
  agent's prose entirely except to parse the final diagnosis.
- **No ground truth ever reaches the agent.** Fault names, component health, and
  scenario ids live in the domain layer and the world's private state. Tool
  outputs are instrument readings only.

Five scenarios ship in v0.1: a dead battery (easy); a corroded engine ground
strap (medium); the same corroded ground with a red-herring battery that reads
marginal at rest but holds up under load (medium); an intermittent ECU/CAN fault
that moves no voltage at all — the car sometimes cranks-no-start and sometimes
starts fine, scans are usually clean, and one good reading proves nothing (hard);
and a compound fault in which a genuinely bad battery sits in front of a corroded
ground strap, neither repair alone starts the car, and stopping at the obvious
battery leaves it broken (hard). Each is a *fix-the-car* task, not a
diagnose-only task.

## 2. Results

Uncoached prompt (role, tool reference, the job, cost one-liner — no strategy, no
grader rules, no trap hints). Five scenarios, five epochs, twenty-five episodes
per model — 225 episodes across nine models. Full table with per-scenario
reliability in [`results/scale_curve.md`](results/scale_curve.md).

| tier | model | mean | root-ok | pass^k | verified-fix |
|---|---|---:|---|---|---|
| frontier | `anthropic/claude-fable-5` | 86.0 | 19/25 | fail | 25/25 |
| frontier | `openai/gpt-5.5` | 82.3 | 20/25 | fail | 25/25 |
| frontier | `grok/grok-4` | 74.9 | 16/25 | fail | 21/25 |
| frontier | `anthropic/claude-sonnet-5` | 74.5 | 19/25 | fail | 23/25 |
| deployment | `google/gemini-3.5-flash` | 59.7 | 14/25 | fail | 20/25 |
| deployment | `anthropic/claude-haiku-4-5` | 39.9 | 10/25 | fail | 13/25 |
| open 3B-8B | `mistralai/ministral-3b` | 23.0 | 6/25 | fail | 6/25 |
| open 3B-8B | `qwen/qwen-2.5-7b` | 20.9 | 2/25 | fail | 6/25 |
| open 3B-8B | `meta-llama/llama-3.1-8b` | 7.2 | 0/25 | fail | 0/25 |

*root-ok = episodes earning full root-cause credit (correct component AND correct
failure mode). pass^k = full root-cause credit in every episode. verified-fix =
the root-cause part was replaced and a successful start followed it.*

**The frontier has cleared the textbook tier — and stalls one tier up.** On the
easy and medium scenarios, four flagship models earn full root-cause credit in 59
of 60 episodes: they read the ground drop under cranking, reject the
marginal-battery bait, replace the strap, and verify. (The one miss is grok-4
answering, in full, "battery failed" on the dead-battery scenario — the grader
holds component-only credit for a diagnosis that does not distinguish a dead
battery from a weak one.) The two hard scenarios are a different story: **15 of
40 frontier episodes earn full root-cause credit, and no model — of the nine —
passes every episode.** The benchmark is not saturated at the top.

**The two hard scenarios fail different models differently.** The intermittent
ECU/CAN fault moves no voltage; the skill is refusing to let one clean scan or
one good crank exonerate anything. claude-fable-5 is the only model that
reliably names it (4/5), gpt-5.5 gets it 3/5, and claude-sonnet-5 — which
otherwise matches fable — goes 0/5, twice condemning the ignition switch with
full confidence. The compound scenario inverts the ranking: sonnet-5 names both
faults in 4 of 5 episodes (89.3, the best cell on the board), while grok-4 finds
the subtle ground strap all five times and *never once mentions the genuinely
bad battery it also replaced* — reporting half your repair is a 15-point hole.
Every frontier model still *fixes* the compound car (the physics forces both
repairs before the engine will start); what separates them is whether the
diagnosis they hand back matches the work they did.

**The deployment tier fails one tier earlier.** `gemini-3.5-flash` and
`claude-haiku-4-5` are the cost/latency class a product actually ships. Flash
handles the single-fault ground scenarios (~89) and collapses on the hard tier
(0/10 root-ok between both hard scenarios). Haiku does not even get that far: on
the red-herring scenario it goes **0 for 5 with zero verified fixes, replacing
14 innocent parts across those five episodes** — the alternator and battery
every single time, the starter motor and relay twice — on a car whose fault is a
$25 ground strap. It reaches for parts instead of the next measurement, at 1.8x
to 3.5x expert technician time. A model that shotguns four parts onto a car and
still leaves it broken is not a model you put in a bay.

One eval-design note worth stating, because it is the kind of thing a grader
gets wrong: **measured-first is 5/5 for haiku on every scenario.** It always
takes a measurement before it starts replacing parts, so the guessing cap never
fires. The behavior that actually costs it points is *measure once, then
shotgun* — caught only because wrong parts debit the total rather than just
their own bucket. A grader without that rule would have scored these episodes
as disciplined.

**The open 3B-8B tier can operate the tools and cannot do the reasoning.** This
is the weight class that runs on-device, and the objection it preempts is "small
models just fail at tool calling." They don't: `ministral-3b` runs clean
16-message episodes on the dead battery — measure, replace, verify, finish — for
full credit in 5 of 5 epochs, outscoring the 7B and 8B models above it. What no
model in the tier can do is let a two-point measurement overturn a plausible
prior: across all 45 open-tier episodes on the two ground-fault scenarios, there
is exactly **one** full-credit diagnosis (ministral, one lucky epoch). The 8B
model never earns root-cause credit anywhere in 25 episodes, and by its late
epochs qwen-7b is emitting token soup as its final answer. The tier's failure is
diagnostic reasoning, demonstrated with the tool mechanics held intact.

**Means hide the reliability story.** pass^k — right in *every* episode — is the
honest column, and at five epochs it is unforgiving: fable loses it to a single
message-limit death on the intermittent scenario (an episode that had the right
answer in hand and ran out of budget verifying it). That is by design. A
diagnostic model that is right four times in five is not deployable, and a
benchmark column that hides that fact is lying to you.

### Coached vs uncoached

The prompt has two variants. **Uncoached** (the default, used for every number
above) states the role, the tools, and the job. **Coached** additionally dictates
the winning policy — measure first, isolate → repair → verify, fewest actions —
and enumerates the grader's scoring rules.

On `claude-haiku-4-5` the difference is **13.6 points** (coached 61.5, uncoached
47.9; 3 scenarios x 3 epochs each, same prompt pair, same run date — measured
2026-07-12 under the previous physics calibration, before the hard tier; the A/B
has not been re-run since, so treat the numbers as directional). The subscore
that moves is the one that matters: verified fixes go from 8/9 coached to 5/9
uncoached. Told to isolate, repair, then verify, the model mostly executes it. Not
told, it does not arrive at the procedure on its own — it does not reliably
confirm its own repair, and it reaches for parts sooner.

Coaching does not rescue it, though: even coached, the red-herring scenario scores
20.9 — the frontier models clear it without being told anything. The procedure
was never the whole gap.

That is why the default is uncoached. A benchmark that tells the model how to work
measures instruction-following; the deployment question is whether the model knows
what to do when nobody says.

## 3. How it works

### The physics

The vehicle is a node-potential model over six nodes — `battery_positive`,
`battery_negative` (reference, 0 V), `engine_block`, `starter_stud`, `alt_output`,
`chassis` — connected by resistances, driven by a battery with an internal
resistance and open-circuit voltage. Engine states are current draws: `key_off`
draws almost nothing, `key_on` a little, `cranking` 150-200 A, and `running`
brings the alternator online.

About fifteen physical constants generate every reading in the environment. A
fault is a change to exactly one of them. The corroded ground strap is
`+1.1 ohms` in the ground path, and that single number is why the battery reads
10.4 V under cranking, why 2.75 V appears across the ground path, why only 0.2 V
appears across the positive feed, and why the engine cranks slowly instead of not
at all. None of those four numbers is written down anywhere. They are consequences.

`measure_voltage(point_a, point_b, engine_state)` returns V(a) − V(b) plus seeded
noise. It is a real two-point measurement: the sign flips when you swap the
probes, an invalid node raises, and — this is the part that catches agents — a
reading referenced to the wrong node tells you something true about a circuit you
are not in. An agent that measures the starter stud against the battery negative
post instead of the engine block will see a healthy supply path and frame an
innocent starter.

### The grader

100 points: **root cause 60** (component and failure mode; component alone earns
30), **parts discipline 25** (−8 per part replaced that was not the root cause),
**cost efficiency 15** (time only, against an expert baseline derived from an
explicit expert action sequence; full credit at or below expert time, zero at 2x,
and *negative* beyond — there is no flail-freely zone).

Three anti-cheat rules, each of which exists because an adversarial agent found
the hole it closes:

- **Symptom masking is not success.** Replacing the battery in a red-herring
  scenario makes the resting readings look fine. It does not fix the car and it
  earns nothing: the grader checks the root component, not the symptom.
- **Wrong parts debit the total, not just their bucket.** Without this, a
  parts-cannon that measures once and then replaces everything floors the
  discipline bucket at zero and rides its root-cause points past 50.
- **A guess is capped at 40.** The cap keys on diagnostic probes taken *before*
  the first replacement. Keying it on total probes let a blind part-swap use its
  own mandatory verification crank as the probe that dodged the cap — a
  blind-swap-then-verify episode scored 100 before this was fixed.

Plus a flat **−15** unless the root-cause part was replaced *and* a successful
start followed the last replacement. A correct diagnosis that leaves the car dead
is not a repair.

Four adversarial agents were written specifically to defeat this grader:
parts-cannon (replace everything), measured-parts-cannon (take one measurement for
cover, then replace everything), lucky-guess (name the right part with no
evidence), and mask-symptom (replace the red-herring battery so the resting
readings look healthy). They score **0, 0, 40, and 9**. The scripted expert scores
100. Note that the two that score 0 both *correctly identify the root cause* — 60
root-cause points, wiped out by what they did to the car.

## 4. Why a human had to verify the physics

The environment was built with frontier coding models. They wrote plausible
physics. Four times, they wrote **wrong** physics that passed the automated test
suite, and a human — the author, playing the environment by hand and reading the
numbers as a technician — caught all four.

1. **Load-sag inversion.** Cranking voltage came out *higher* than resting
   voltage at some nodes. Pulling 180 A through a battery's internal resistance
   makes terminal voltage drop, always; the model had it backwards. Every
   individual reading looked like a reasonable number.
2. **Downstream exceeded upstream.** A node further down the supply path read
   higher than the node feeding it — current flowing uphill, with no source
   between them.
3. **The red herring became a real fault.** The battery meant to be *bait* in the
   third scenario had drifted to a voltage that made it genuinely weak. The
   scenario now had two faults, and the "correct" answer the grader demanded was
   only half the story — an unfair scenario that would have scored honest models
   wrong.
4. **The ground fault was not localizable.** The injected ground resistance
   produced a voltage drop too small for any measurement to isolate. The fault was
   real, the symptom was real, and no correct sequence of probes existed. The
   environment was unsolvable and nothing said so.

The tests passed on all four. They passed because the tests checked the things the
model that wrote them thought to check, and physical wrongness of this kind is
invisible to a test suite that shares the author's misconception. Each bug is now
an invariant in the codebase, checked on every scenario:

> 1. Cranking voltage < resting voltage at every point.
> 2. No downstream node exceeds an upstream node at rest.
> 3. Red herrings are resting-only and suppress the whole resting path uniformly.
> 4. In a ground-fault scenario, the fault must be uniquely localizable: a large
>    drop across the ground path under cranking only, a small drop across the
>    positive feed, and a battery that holds.

The general form of this is the reason the environment exists. **Generation is
cheap and getting cheaper; verification is not.** A model can produce a physical
environment it cannot warrant, and the failure mode is not an obvious crash — it
is a plausible number in a consistent-looking world. That is the failure this
whole line of work is built to prevent, and it is why the environments have a
human with a multimeter behind them.

## 5. Limitations

Stated plainly, because they bound what the results mean:

- **Five scenarios, one vehicle.** The topology is a single ground path on a
  single vehicle. The environment does not yet vary chassis architecture.
- **Short horizon, hard message cap.** Episodes run under a 50-message limit,
  and on the intermittent scenario — where sound protocol means repeated cranks
  and scans — the cap kills some episodes that had the right answer in hand and
  were still verifying. That is a deliberate design choice (knowing when to stop
  verifying is technician skill), but it means the intermittent cell partially
  measures time discipline, and nothing here tests a diagnostic thread held
  across hours or sessions.
- **The most-documented diagnostic domain on the internet.** Automotive
  no-start diagnosis is in every service manual and half of YouTube. If a model
  were going to have memorized a physical domain, it would be this one — which
  makes the textbook-tier scores unsurprising and the failures above them more
  interesting, not less.
- **No motor control, no perception, no manipulation.** This measures the
  *reasoning* layer of physical work. It does not touch the actuation layer.
- **The red-herring scenario is defeated at the frontier** (20/20 full credit);
  it still separates the tiers below. The hard tier is not defeated by anyone:
  no model of nine passes every episode.
- **Reliability numbers are k=5.** Five epochs per cell separates the tiers
  cleanly, but individual cell means on the hard scenarios still move tens of
  points between runs; read root-ok fractions, not decimals.
- **Known scoring gaps.** The wrong-part penalty is flat (−8) whether the part is
  a $15 fusible link or a $450 ECU, so parts dollars influence no bucket. The feed
  drop is not current-scaled. The diagnosis parser accepts real technician
  vocabulary but remains a parser — the vocabulary map grows only from real
  transcripts, so novel phrasings can still under-credit.

## 6. v0.2

Detailed in [`V0.2.md`](V0.2.md). The hard tier originally planned for v0.2 —
intermittent faults that one clean reading cannot exonerate, compound faults
with a primary and a secondary — shipped early, in this release, with human
physics sign-off; the results above show it doing its job (nobody passes it
clean). What remains for v0.2: more scenarios and varied vehicle topology,
cost pressure, price-weighted part penalties, pass^k as the headline metric,
and a generative authoring architecture in which validation attaches to the
*causal model* rather than to individual scenarios — a schema-constrained
scenario declaration, an assumption ledger that makes every unverified constant
enumerable, an invariant engine that runs the physics invariants against every
generated scenario, and a sampler. The property being bought is that human
verification scales sublinearly with scenario count.

The open question v0.2 is built to answer: **is the deployment-tier gap closable
by training on environments like this one, or does it need capability the small
model does not have?** An environment that separates the shipping tier from the
frontier by 30+ points, and the on-device tier by 60, is the instrument for
answering that either way.

The next domain is robotics-cell fault triage: a work cell stops, and the agent
has to localize the fault across mechanical, electrical, sensor, and controller
layers. Same architecture, different physics.

---

## Reproducing

```bash
pip install -e ".[dev,models]"
python scripts/sanity_check.py                                    # physics invariants
python scripts/run_evals.py --models anthropic/claude-sonnet-5 --scenarios all --epochs 5
python scripts/scale_curve.py                                     # -> results/scale_curve.md
```

Provider keys go in `.env` (template: `.env.example`). Every number in this
writeup regenerates from the committed code at the commit recorded in
`results/scale_curve.md`.
