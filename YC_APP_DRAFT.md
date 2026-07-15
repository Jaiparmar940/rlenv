# YC Application — Draft

Founder: Jaivir Parmar. Company: training environments and evals for physical-systems AI.
First public artifact: `no-start-env` (this repo), publishing 2026-07-13.

Status of this draft: every factual claim below is sourced from this repository or from
the published eval results in `results/results.md`. Anything I could not source is marked
`[FOUNDER: ...]` and must be filled in before submission. No numbers, customers, revenue,
or conversations are invented.

---

## Company

**Company name.** [FOUNDER: legal or intended company name.]

**Describe what your company does in 50 characters or less.**

`Training envs and evals for physical-systems AI` (47 characters)

**Company URL.** [FOUNDER: website / landing page URL, or "none yet".]

**Demo video.** [FOUNDER: record 1-minute founder video; script stub at the end of this doc.]

**Product video / demo link.** [FOUNDER: link to the repo, the results table, or a screen
recording of an agent episode. Candidate: GitHub repo for `no-start-env` plus
`results/results.md`.]

**What is your company going to make? Please describe your product and what it does or
will do.**

We build the training environments and evaluations that teach AI models to reason about
physical systems, and that measure whether they can.

An environment is a simulated physical system with a fault in it, a set of realistic
tools the model can use to investigate, and a grader that scores the model on what a
competent technician would be scored on: did it find the actual root cause, did it avoid
replacing parts it had no evidence against, did it fix the thing, and did it do it in a
reasonable amount of time.

Our first environment, `no-start-env`, is a vehicle that will not start due to an
electrical fault. The model has the tools a technician has: scan diagnostic trouble
codes, read live sensor values, take a two-point voltage measurement between any pair of
nodes in any engine state, inspect visually, replace a part, attempt a start, and submit
a diagnosis. It is built on a node-potential electrical model — roughly 15 physical
constants and a resistance network generate every reading the model can take. No output
voltage is ever hand-authored. A fault is a change to one resistance, and every
measurement in every engine state falls out of that change consistently. This matters
because it is what makes the environment un-gameable: there is no lookup table of
"correct" readings for a model to pattern-match against, and any pair of probe points the
model chooses returns a physically consistent number.

The grader scores 0–100: root cause 60, parts discipline 25, cost efficiency 15. It reads
ground truth, not symptoms — relieving the symptom by replacing the wrong part does not
count as a fix. Replacing a part before taking any measurement caps the score at 40.
Wrong parts debit the total, not just their own bucket, so a model cannot shotgun parts
and ride correct-diagnosis points to a pass. Four adversarial agents (the parts cannon,
the blind swapper, the flailer, the guesser) were written specifically to defeat the
grader; all four score below 50, and a scripted expert scores 100.

Everything is deterministic and seeded: the same run produces the same observations and
the same score. It is built on Inspect (inspect-ai), so a lab can run it against their
models without adopting anything of ours.

The product we sell is the environment plus the verification behind it: environments that
a lab can train on and trust, and evals whose numbers mean what they say.

**Where do you live now, and where would the company be based after YC?**

[FOUNDER: current city; intended base after YC.]

---

## Founders

**Please tell us about a time you most successfully hacked some (non-computer) system to
your advantage.**

[FOUNDER: personal story. Candidate material: 5-DOF robotic arm build, automotive/ECU
diagnosis and repair, fabrication work — pick one with a concrete outcome and dates.]

**Tell us about the time you most successfully hacked some system to your advantage.**

[FOUNDER: as above — do not reuse the same story.]

**Please tell us in one or two sentences about the most impressive thing other than this
startup that you have built or achieved.**

[FOUNDER: verify and extend with specifics and dates. Known: a 5-DOF robotic arm
(design + build); automotive work at ECU level — diagnosis and repair; fabrication.
Needs: what the arm did, what it was built from, when; what kind of vehicles/systems,
over what period; any certifications or shipped work.]

**Tell us about things you've built before.**

[FOUNDER: list with dates. The 5-DOF robotic arm, the automotive/ECU diagnosis and repair
work, the fabrication work, and this repo.]

**How long have the founders known one another and how did you meet? Have any of the
founders not met in person?**

[FOUNDER: solo founder, or co-founder details. If solo, answer accordingly and be
prepared for the "why solo" question.]

**Why did you pick this idea to work on? Do you have domain expertise in this area? How
do you know people need what you're making?**

I have built both sides of this problem. I have built physical systems — a 5-DOF robotic
arm, fabrication work — and I have diagnosed and repaired vehicles down to the ECU level.
[FOUNDER: verify and extend with specifics/dates.] I also write software. The intersection
is not crowded.

The specific thing that convinced me there is a company here happened while building this
repo. I used frontier coding models to help write the physics. They produced physics that
was confidently wrong, and the automated test suite passed it. Four separate times:

1. **Load-sag inversion.** Cranking voltage read *higher* than resting voltage. A battery
   under a 150–200 A load sags; it does not rise. Tests passed.
2. **Downstream above upstream.** A node further down the supply path read a higher
   potential at rest than the node feeding it. Current does not flow uphill through a
   resistance. Tests passed.
3. **Red herring drifted into a real fault.** A scenario contains a battery that is
   *supposed* to look tempting but be innocent — bait. The numbers drifted until the
   battery was genuinely weak, which made it a real co-fault and the scenario unfair: the
   "wrong" answer was now defensibly right. Tests passed.
4. **Ground-fault drop too small to localize.** The fault was injected, and no measurement
   the agent could take would isolate it. The scenario was unsolvable and looked fine.
   Tests passed.

Every one of these was caught by me playing the environment by hand and noticing the
reading was wrong. Not by tests. This is the whole thesis of the company, and I found it
by accident: **models can generate physical environments they cannot warrant.** Those four
bugs are now encoded as physics invariants in the repo (`CLAUDE.md`, "Physics
invariants"), checked by `scripts/sanity_check.py`, and they are the reason the published
scenarios can be trusted.

How I know people need this: [FOUNDER: outreach and lab conversations at submission time —
who you have talked to, what they said, any inbound. Do not fill this in with anything
that did not happen.]

---

## Progress

**How far along are you?**

The first environment is built and publishing 2026-07-13 as an open benchmark:

- Deterministic, seeded environment on a node-potential electrical model (~15 constants
  generate every reading; faults are single-resistance changes).
- Five scenarios: a dead battery; a corroded ground strap; the same ground fault with a
  red-herring battery that reads tempting at rest and holds under load (the bait); an
  intermittent ECU/CAN fault that moves no voltage at all (one clean scan must not
  exonerate it); and a compound fault where a genuinely bad battery hides a corroded
  ground strap — neither repair alone starts the car. Hard-tier physics human-signed-off.
- Seven agent tools; tool outputs are instrument readings only. Ground truth never enters
  an observation, a prompt, or a tool output (audited per run: `results/audit.md`).
- A cheat-resistant grader (above), with four adversarial agents pinned as tests.
- Inspect (inspect-ai) task, so a lab can run it directly.
- A published results table: 9 models × 5 scenarios × 5 epochs — 225 episodes, spanning
  frontier, deployment, and open on-device (3B-8B) tiers.
- Domain truth documented in `DOMAIN_TRUTH.md` and human-verified.

**What's the finding.**

Uncoached (the system prompt states the job and the tools, and no strategy), mean scores
across all five scenarios:

| tier | model | mean |
|---|---|---:|
| frontier | claude-fable-5 | 86.0 |
| frontier | gpt-5.5 | 82.3 |
| frontier | grok-4 | 74.9 |
| frontier | claude-sonnet-5 | 74.5 |
| deployment | gemini-3.5-flash | 59.7 |
| deployment | claude-haiku-4-5 | 39.9 |
| open 3B-8B | ministral-3b | 23.0 |
| open 3B-8B | qwen-2.5-7b | 20.9 |
| open 3B-8B | llama-3.1-8b | 7.2 |

Three findings, one per tier. The frontier has cleared the textbook tier (full
root-cause credit in 59 of 60 easy/medium episodes) but not the hard tier (15 of 40) —
no model of the nine passes every episode. The deployment tier fails a tier earlier:
`claude-haiku-4-5` goes 0-for-5 on the red-herring scenario, replacing 14 innocent parts
across those five episodes — alternator and battery every time — on a car whose fault is
a $25 ground strap. And the open 3B-8B tier — the weight class that runs on a robot —
operates the tools competently (ministral-3b earns full credit on the trivial battery
scenario in 5 of 5 epochs) and scores ~0 wherever a two-point measurement has to
overturn a plausible prior: the failure is diagnostic reasoning, isolated from tool
mechanics. Best-worst spread on this benchmark is 78.8 points.

That gap is the product. See "What do you understand that others don't" below.

**How long have you been working on this?**

[FOUNDER: start date on this company / this repo.]

**Are people using your product?** [FOUNDER: answer honestly at submission time.]

**Do you have revenue?** No.

**If you've applied previously with the same idea, how much progress have you made since
then?** [FOUNDER: n/a or details.]

**If you have already participated or committed to participate in an incubator,
"accelerator" or "pre-accelerator" program, please tell us about it.** [FOUNDER.]

---

## Idea

**Why did you pick this idea to work on?** See Founders, above.

**What's new about what you're making? What substitutes do people resort to because it
doesn't exist yet (or they don't know about it)?**

Four things, in order of how much they matter.

**1. The knowledge is not in the training data.** Polanyi: "we know more than we can
tell." What a technician knows about how a corroded ground behaves under a 200-amp load —
that the battery will read fine at rest and *still* read fine under crank, and that the
tell is a 2.75 V drop across a strap that should drop 0.1 V — was never written down. It
was learned by hand, on cars, and it stayed in the hands. Models are trained on the
written-down part. That is why they fail here and pass on textbook problems.

**2. Verification asymmetry.** Frontier models can *generate* a physical environment they
cannot *warrant*. Generation is cheap and getting cheaper; verification is not, because
verification requires knowing what a real system does. The four bugs above are the
evidence: a competent model wrote each of them, an automated test suite passed each of
them, and only a human who had actually held a multimeter to a starter caught them. Anyone
can now generate a hundred physics environments in an afternoon. Almost nobody can tell
you which ones are wrong. The scarce thing is not the environment. It is the warrant.

**3. The deployment-class gap.** The models that will actually run on robots and in shops
are not the models topping the leaderboards — they are the cheap, fast, small ones. On
this benchmark the scale curve is measured end to end: frontier models average 74–86, the
deployment tier 40–60, and the open 3B-8B weight class — the one that runs on-device —
7–23, with the collapse concentrated exactly where a plausible-but-misleading reading has
to be rejected. The industry evaluates the models at the top. The models at the bottom are
the ones being deployed. The scale curve inside a physical-reasoning task is not something
anyone else is currently measuring, and it is exactly what a robotics company needs before
it ships.

**4. Training assets become certification assets at saturation.** The same verified
environment that trains a model becomes the thing you certify it against once it can pass.
A robot that repairs, inspects, or maintains physical equipment will need to demonstrate
competence against something, and that something will be a simulated system with known
ground truth and a grader that cannot be gamed. We are building the training asset first
because that is what is being bought today. It converts.

**Substitutes people resort to today:** generalist human-data vendors (digital tasks,
written rubrics); teleoperation and real-robot demonstration data (expensive, narrow,
doesn't teach diagnosis); internal eval sets built ad hoc by lab engineers without domain
verification — which is exactly how you get an environment with load-sag inverted and a
green test suite.

**Who are your competitors? What do you understand about your business that they don't?**

- **Scale, Surge, Mercor** — generalist, digital. They sell human labor against tasks that
  can be written down and graded by a rubric-following annotator. Physical-systems
  reasoning is neither.
- **Amplibotics** — real-arm demonstration data. Real hardware, real motions. Different
  seat: demonstration, not diagnosis; capture, not verification.

The seat we are claiming: **verified simulated environments for physical-systems
reasoning.** Simulated, so it is deterministic, cheap, and infinitely re-runnable.
Verified, so the numbers are load-bearing.

What we understand that they don't: as generation gets free, the bottleneck moves to
warranting. A vendor whose value is "we made you 500 environments" gets commoditized the
month a model can make 500 environments. A vendor whose value is "we can tell you which
of your 500 environments is physically wrong, and here is the invariant that catches it"
does not.

**Moat:** an independent verification channel (a founder who can look at a reading and
know it is wrong, and a growing library of encoded invariants and sanity checks derived
from real caught bugs) plus tooling that keeps that verification cheap as generation gets
free. Every bug caught becomes a permanent invariant. The invariant library compounds; the
environments themselves do not.

**How do or will you make money? How much could you make?**

Three steps, in order:

1. **Commissioned environments and evals.** A lab or a robotics company has a physical
   domain they need a model to reason about. We build the environment, the scenarios, and
   the grader, and we warrant the physics. Priced per environment.
2. **Retainers.** Environments are not one-shot. Scenarios saturate, models get better,
   the eval has to get harder. Ongoing scenario development, difficulty ratcheting, and
   verification of environments the customer generates themselves.
3. **Licensing the authoring and verification infrastructure.** The invariant checker, the
   grader framework, the determinism harness. This is the part that scales past our own
   hands.

Market size: [FOUNDER: source or soften.] AI labs are widely reported to be spending on
the order of ~$1B/yr on RL environments. The physical/embodied lane of that spend is
served by nobody with domain verification. Robot foundation models are arriving now, and
each one needs both training environments and a way to certify what it can do.

**How will you get users?** [FOUNDER: outreach plan and any conversations to date at
submission time. The published benchmark is the top of the funnel: a lab eval engineer
who reads the code and takes it seriously is the target.]

---

## Equity / Legal

**Have you formed ANY legal entity yet?** [FOUNDER: yes/no; entity type, state, date.]

**Have you taken any investment yet?** [FOUNDER: yes/no; amounts and instruments.]

**Are you currently fundraising?** [FOUNDER.]

**Please provide any other relevant information about the structure or formation of the
company.** [FOUNDER: cap table, any co-founder splits, vesting.]

**Have you incorporated, or formed any legal entity (like an LLC) outside the US?**
[FOUNDER.]

**Are any of the founders covered by noncompetes or intellectual property agreements that
overlap with your project?** [FOUNDER — important: any prior employer IP agreement that
could touch this work.]

**Who writes code, or does other technical work on your product? Was any of it done by a
non-founder?** [FOUNDER: note that this repo was built by the founder with AI coding tools
(Cursor, Claude Code) under the founder's direction and domain verification; no
non-founder contributors. Confirm and adjust.]

**Is there anything else we should know about your company?** [FOUNDER.]

---

## Curious

**What convinced you to apply to Y Combinator?** [FOUNDER.]

**How did you hear about Y Combinator?** [FOUNDER.]

---

## Video script stub (1 minute)

[FOUNDER: record. Suggested beats — keep it dry, no pitch voice:]

1. Who I am, in one sentence. [FOUNDER: name, background — hardware and software, 5-DOF
   arm, ECU-level automotive diagnosis and repair.]
2. What the company does, in one sentence: training environments and evals for
   physical-systems AI.
3. Show the environment. One episode: the model probes, gets a 2.75 V drop across a ground
   strap, and either believes the battery or doesn't.
4. The finding: the full scale curve — frontier 74–86, deployment tier 40–60, on-device
   weight class 7–23 — and every tier fails exactly where the obvious reading is wrong.
   No model of nine passes every episode.
5. Why me: I caught four physics bugs in my own environment that a frontier model wrote
   and my test suite passed. Generation is cheap. Warranting isn't.

---

## Notes for the founder before submitting

- Every `[FOUNDER: ...]` above is a hard blocker — do not submit with placeholders.
- The ~$1B/yr RL-environment spend figure needs a citable source or should be softened to
  "widely reported to be a significant and growing line item."
- The results cited here are the uncoached 9-model × 5-scenario × 5-epoch run
  (`results/results.md`, 225 episodes, commit `8debf0e` physics). If the table is
  regenerated before submission, update the numbers in this doc to match.
- Known gaps in the benchmark, per `CLAUDE.md`, which you should be ready to name if
  asked rather than have found: five scenarios, single-vehicle ground topology; the
  wrong-part penalty is flat regardless of part price; mode-vocabulary parsing grows only
  from real transcripts; hard-tier cell means still swing between runs at k=5 (read the
  root-ok fractions); the 50-message cap makes the intermittent scenario partly a test of
  time discipline. Naming them is the credibility move.
