# decision-layer: kitchen decision-under-ambiguity task

**Task one of Second Nature Labs' decision-layer evaluation suite.** The agent
under test is a reasoning model choosing among discrete primitives
(`open`, `pick`, `place`, `discard`, `declare`, `done`) on a RoboCasa kitchen
scene. Execution of each primitive is **oracle by design** — a valid action is
realized by setting simulator state directly through the robosuite/RoboCasa
Python API. This is the product thesis, not a shortcut: we isolate and grade
the *decision layer* (inspect → infer → intervene) separately from motor
execution, the same way [no-start-env](../no-start-env.md) isolates diagnostic
reasoning from wrench-turning. No motion planning, no RL training, no teleop.

![scripted expert solving all three hidden-state variants](media/episode.gif)

*Above: the reactive scripted expert solving all three variants end-to-end on
the RoboCasa scene (layout 1 / style 8), scoring 100.0 on each. Every caption
is a real action → observation pair from the episode log. The robot arm is
scenery and never actuates — doors and objects change state directly because
execution is oracle; the decision sequence is the system under test.*

## The task

*"Put the leftovers away in the fridge."* The correct next action cannot be
determined from the initial observation — hidden state (seeded, one of three
variants) is revealed only by inspecting:

| variant | hidden state | correct behavior |
|---|---|---|
| `nominal` | fridge has shelf space | open fridge, confirm space, shelve |
| `fridge_full` | shelf at capacity; one item is expired | discard the expired item, then shelve |
| `container_missing` | leftovers were left in the microwave (its clock blinks — the targeted cue) | check the microwave, retrieve, shelve |

`nominal` and `fridge_full` are **byte-identical** in the initial observation
(pinned by test). Observations are structured text of what is visible from the
current viewpoint; a fixture's interior is observable only while its door is
open. Wrong-but-plausible behaviors — acting on the default assumption,
discarding fresh food to make room, exhaustively opening everything, declaring
done early — are each distinguished and penalized by the grader.

## Grader (0–100, three-way split)

- **Inference (40)** — did the agent identify the actual hidden state?
  Requires a `declare` that matches ground truth **and** the revealing
  observation must have occurred before the declaration (a lucky guess with
  the fridge never opened earns 0). No declare but inspect-before-intervene:
  partial credit (20).
- **Parsimony (25)** — full credit at the expert action count (pinned per
  variant, regenerated from the reactive scripted expert by tests), linear to
  0 at 2×, **negative beyond** — flailing debits the total. Withheld entirely
  if the leftovers never reached the shelf: being tersely useless is not
  parsimony.
- **Intervention (35)** — end-state predicates checked against **backend
  state, never agent claims**: leftovers on the fridge shelf (25), variant
  side-condition such as expired-item-in-trash (5), doors closed (5).
  Discarding fresh food debits 15 per item (the wrong-part rule from
  no-start-env).

Anti-cheat properties are pinned in `tests/` and documented in
[AUDIT.md](AUDIT.md). Two live LLM traces (haiku: act-before-inspect at 87.5 on
the symbolic backend; a cue-reading targeted solve at 80 on the full sim) are in
[results/llm_traces.md](results/llm_traces.md).

## Install & run

The decision layer alone needs nothing but the Python 3.10+ standard library:

```bash
python run_episode.py --agent scripted --backend symbolic   # all 3 variants
python run_episode.py --agent human --variant random --seed 7
python run_episode.py --agent llm --model claude-haiku-4-5-20251001   # needs anthropic + ANTHROPIC_API_KEY
```

The RoboCasa backend needs a sim venv (Apple Silicon works; no GPU needed):

```bash
python3.12 -m venv .venv-sim
git clone https://github.com/ARISE-Initiative/robosuite   # MASTER branch required — PyPI robosuite (1.5.2) is too old for robocasa
git clone https://github.com/robocasa/robocasa
.venv-sim/bin/pip install imageio -e robosuite -e robocasa
yes y | .venv-sim/bin/python robocasa/robocasa/scripts/download_kitchen_assets.py   # ~10 GB; prompts on stdin without the `yes`
```

```bash
python run_episode.py --agent scripted --backend robocasa --gif media/episode.gif
```

Any LLM drops in via one interface: a callable `observation_str -> action_str`
(see `kitchen_task/agents.py`).

## Architecture

```
run_episode.py            CLI: agent x backend x variant, prints score breakdown
kitchen_task/
  task.py                 variants, hidden state, diagnosis parser, expert pins
  env.py                  action grammar, validity rules, reveal rules, event log
  grader.py               three-way score; queries the backend, not the env
  agents.py               scripted expert (reactive), LLM adapter, human play
  backends/
    base.py               the substrate protocol (the only surface the task touches)
    symbolic.py           pure-Python kitchen state model (no sim required)
    robocasa_backend.py   RoboCasa/MuJoCo binding; regions from geometry
```

The grader asks the **backend** where objects are. In the RoboCasa backend
those answers are computed from geometry (object pose inside region bounding
boxes, door joint angles) — so grading is against simulator ground truth even
though execution is oracle.

## Ship-today decisions (v0.1)

- Inspect cost is expressed through the parsimony bucket (action count vs
  expert), not a separate dollar meter.
- `declare` is free text matched against a small keyword vocabulary
  (`task.py`); extend only against real transcripts — the no-start-env rule.
- Three variants, one scene layout; layout jitter is seeded but unused.
- Scripted expert doubles as the parsimony baseline generator.
