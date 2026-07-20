# OpenReward integration — spec summary and plan (Phase 1)

Status: research complete, no code written. Awaiting Jaivir's go-ahead before Phase 2.

## What OpenReward is

OpenReward (openreward.ai) is General Reasoning's hosting platform for RL environments,
built on the **Open Reward Standard (ORS)** — an open, HTTP-based protocol
(openrewardstandard.io) that extends the MCP tool-calling pattern with RL primitives:
sessions (episodes), reward signals, episode termination, tasks, and deterministic
splits. 330+ environments are served through one API. Environments deploy from a GitHub
repo + Dockerfile; code stays on GitHub, and they can also be self-hosted or run
locally.

Sources: [docs.openreward.ai](https://docs.openreward.ai/), the
[ORS spec](https://openrewardstandard.io/), the
[launch post](https://www.gr.inc/releases/introducing-openreward), and the `openreward`
PyPI SDK (latest seen: 0.1.81).

## What the spec requires

An ORS environment is a Python class extending `openreward.environments.Environment`:

- `__init__(self, task_spec: JSONObject, secrets: dict)` — one instance per session
  (episode), constructed from the task spec. This is where our seeded `World` gets built.
- `list_tasks(split) -> list[JSONObject]` (classmethod) — **must return tasks in a
  stable order**; clients fetch tasks by index.
- `list_splits() -> list[Split]` (classmethod) — splits typed `train`/`validation`/`test`.
- `get_prompt() -> list[TextBlock]` — the agent-visible prompt for the task.
- Actions are methods decorated `@tool`, taking a Pydantic params model and returning
  `ToolOutput(blocks=[TextBlock...], metadata={...}, reward=float, finished=bool)`.
  Tool schemas auto-generate for OpenAI/Anthropic/Google function-calling formats.
- Serving: `Server([MyEnv]).run()` → FastAPI/Uvicorn on **port 8080**. Deployment is a
  Dockerfile exposing 8080; pushes to the connected GitHub repo auto-deploy via webhook.
- Rewards: float per tool call; no mandated range, but every documented example uses
  0.0–1.0 with the reward emitted on the terminal tool call (`finished=True`).
- Sandboxes (remote containers for agent code execution) are **optional** — for
  environments where the agent runs code. We don't need one: our tools are pure
  in-process physics computations.
- Documentation: an "environment card" README.md (description, capabilities, tasks,
  reward structure, tools, difficulty baselines, license, safety).

Local validation loop: `pip install openreward`, run `python server.py`, then hit
`http://localhost:8080` with the `OpenReward` client (`environment.session(task=...)`,
`session.get_prompt()`, `session.call_tool(...)`) — so Phase 3's side-by-side scoring
can run entirely on this machine with no account.

## How it maps onto our structure

The fit is close to 1:1 — ORS's model (episode = session, actions = tools, terminal
tool carries the reward) is the same shape as our Inspect task:

| Ours (Inspect) | ORS |
|---|---|
| `Sample` per scenario, `metadata.scenario_id` | task spec in `list_tasks("test")` |
| `init_session()` solver → `ToolSession(scenario_id)` | `Environment.__init__(task_spec)` builds the same `ToolSession` |
| 6 tools in `task.py` wrapping `ToolSession` | same 6 methods with `@tool` + Pydantic params, `reward=0, finished=False` |
| `finish` (basic_agent submit) → `nostart_grader` reads world state | a 7th `finish(diagnosis)` tool: calls `world.finish()`, runs `grade(world)`, returns `reward=total/100, finished=True` |
| system prompt (`PROMPTS["uncoached"]`) + complaint user message | `get_prompt()` blocks (see question 3 below on system-role support) |
| epochs via Inspect | repeats via harness seeds (their eval example uses `NUM_SEEDS`) |
| determinism: seeded `World` per scenario | identical — fresh seeded `World` per session |

Nothing in the core (`world.py`, `grader.py`, `domain/`, `tools.py`, `prompts.py`)
needs to change. The adapter is a new module (`src/nostart/openreward/`) that imports
`ToolSession` and `grade` exactly as `task.py` does, plus a Dockerfile and an
environment card.

**Reward mapping (explicit):** ORS reward = grader total / 100, emitted once on
`finish`. It is continuous 0–1, sparse (terminal only). All intermediate tools return
`reward=0.0`. The full `GradeBreakdown` goes in the terminal `ToolOutput.metadata` so
subscores survive without affecting the scalar. If the agent never calls `finish`, no
reward is ever emitted (harness-side treatment of unterminated episodes is their
convention — see question 5).

### Integrity notes

- **Ground-truth leakage:** the platform has a first-class server-side/agent-visible
  split ("this separation is critical: it lets your server hold ground truth data...
  that the agent in the sandbox never sees"). Since we use no sandbox, ground truth
  simply lives in the server process, same as with Inspect. However, **task specs
  returned by `list_tasks` are client-visible**, and our scenario ids encode answers
  (`easy_dead_battery`, `medium_corroded_ground`...). Whether a harness feeds the task
  spec to the model is out of our control, so the adapter will use opaque task ids
  (`ns-01`..`ns-05`, plus a tier label at most) with a server-side mapping to scenario
  ids. Defense-in-depth; also raised as question 2 for Ross.
- **The GitHub repo itself contains ground truth** (`scenarios.py`, DOMAIN_TRUTH.md) —
  unchanged from today: the benchmark is already public, and integrity rests on the
  agent context, not repo secrecy. No new exposure.
- **Grading integrity:** the grader is called unchanged on the same `World` object; no
  reimplementation, no trust in agent text beyond the diagnosis string it already parses.
- **Determinism:** `World(scenario_id)` is seeded; identical sessions produce identical
  observation streams (verified today by `scripts/check_determinism.py`). The ORS
  transport adds nothing stochastic. Phase 3 re-verifies through the HTTP interface.

## What needs to be built (scope estimate)

1. `src/nostart/openreward/env.py` (~200–300 lines): `NoStartEnv(Environment)` — task
   list (5 opaque-id tasks, single `test` split), `get_prompt()` (uncoached prompt +
   complaint), 6 `@tool` wrappers with Pydantic param models mirroring the docstrings in
   `task.py`, `finish` tool wired to `grade()`. `ValueError` from `measure_voltage` maps
   to an error `ToolOutput` (ORS has no ToolError; convention appears to be returning
   the error text as a block — verify against SDK in Phase 2).
2. `src/nostart/openreward/server.py` (~10 lines): `Server([NoStartEnv]).run()`.
3. `Dockerfile` (python:3.12-slim, `pip install -e . openreward`, expose 8080).
4. Environment card (`docs/openreward_card.md`, becomes the listing README): from their
   12-section template, drawing on README/WRITEUP — includes the v0.1 results table,
   attribution ("no-start-env by Second Nature", snlabs.dev + repo links), MIT license.
5. Phase 3 validation script (`scripts/validate_openreward.py`): drives all 5 scenarios
   through `http://localhost:8080` with one cheap model, prints OR score vs direct
   Inspect score side by side on the same seeds.
6. `openreward` added as an optional extra in `pyproject.toml` (e.g. `[openreward]`),
   keeping the core install unchanged.

No changes to environment, grader, world, scenarios, or tools. Estimated effort: one
working session for the adapter + Dockerfile, one for validation and the card.

## Open questions for Ross (not assumed)

1. **Org naming/attribution:** environments live at `openreward.ai/{username}/{env}`.
   Can we register the listing under a "Second Nature" org name rather than a personal
   username, and where do external links (snlabs.dev, GitHub) surface — card only, or
   listing metadata too?
2. **Task-spec visibility:** are task specs from `list_tasks` conventionally kept out of
   the model context by your harnesses (firehorse etc.), i.e. is `get_prompt()` the only
   agent-visible surface? We're using opaque task ids regardless — is there a platform
   convention for holding scenario labels/answers out-of-band?
3. **System prompts:** does ORS distinguish a system-role prompt from the user prompt in
   `get_prompt()` blocks, or should our (deliberately uncoached) system prompt be
   prepended to the prompt blocks? Our benchmark numbers are prompt-sensitive, so we
   want the served prompt to match the published run exactly.
4. **Versioning:** pushes auto-deploy. How do we pin the listing to v0.1 of the
   benchmark (tags/releases?) so served behavior stays in lockstep with the published
   results table?
5. **Unterminated episodes:** the platform relies on the terminal tool for reward. If a
   harness cuts an episode off (our published runs cap at 50 messages) without `finish`,
   is a 0 reward recorded, or is the episode dropped? Affects comparability of pass
   rates.
6. **Turn limits:** is there a platform- or environment-level max-actions setting, or is
   that purely the harness's job? (We can enforce a cap inside the environment if
   that's the convention.)
7. **Reward range:** confirm 0–1 continuous rewards are the expected convention for
   both eval and RL training use (our native scale is a 0–100 rubric; we map /100 and
   ship subscores in metadata).
8. **Secrets:** our environment needs zero secrets (no LLM grader, no external calls) —
   anything required anyway for hosted serving?

## Explicitly out of scope

Submission, account creation, PRs against their repos, and any publishing step — all
prep stops at a ready-to-deploy branch for Jaivir to review and submit.
