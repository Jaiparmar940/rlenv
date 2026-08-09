# DataVendor/HUD packaging — findings, work done, verification, remaining steps

Prepared 2026-08-07/08 on branch `feat/datavendor-packaging`. Scope: package
the two Second Nature Labs environments (no-start-env, decision-layer kitchen
task) for sale as managed environments on DataVendor/HUD, adapting the existing
implementations without changing their scientific behavior.

## 1. Phase 0 conclusion: what DataVendor can attach directly

**DataVendor is HUD's marketplace** (datavendor.ai, "by HUD"; also served at
vendor.hud.ai). Its RL-environment and taskset asset kinds run on **managed
Harbor or HUD infrastructure** — environments are attached through the
**hud.ai connector**, not by pointing at an arbitrary external HTTP service.

Findings from the current official documentation and product pages
(2026-08-07):

- Supply types: "RL environments — runnable agent evaluation environments on
  managed Harbor or HUD infra, priced per environment", plus tasksets,
  codebases (GitHub connector), and zip bundles.
  Source: <https://datavendor.ai/supply-types>
- Connectors table: GitHub → codebases; **hud.ai → RL environments,
  tasksets**; file upload → zip bundles. There is **no connector for
  OpenReward** or any third-party environment host.
  Source: <https://datavendor.ai/supply-types>
- Listings attach assets in the publish flow ("Assets — attach repos,
  tasksets, environments, or zip bundles and set unit prices"); vendor orgs
  need Tier 1 access (org setup + HUD review + HUD vendor NDA).
  Source: <https://datavendor.ai/publish-listing>
- Delivery: "tasksets and environments on managed infra (Harbor or HUD)";
  samples exist only for tasksets/environments.
  Source: <https://datavendor.ai/buy-or-sample>
- The HUD environment format: an `Environment` object in `env.py` serving a
  tcp JSON-RPC control channel (`hello` → manifest → `tasks.start` →
  capabilities → `tasks.grade`), packaged by `Dockerfile.hud`, deployed with
  `hud deploy`, tasks synced with `hud sync tasks`.
  Sources: <https://docs.hud.ai/v6/guides/creating-an-environment>,
  <https://docs.hud.ai/v6/advanced/protocol>,
  <https://docs.hud.ai/v6/reference/environment>,
  <https://docs.hud.ai/v6/reference/tasks>,
  <https://docs.hud.ai/v6/reference/capabilities>,
  <https://docs.hud.ai/v6/reference/runtime>,
  <https://docs.hud.ai/v6/reference/cli>

**Decision: the existing OpenReward deployment cannot be attached directly.**
DataVendor's environment asset kind requires the environment to run on
HUD-managed (or Harbor) infrastructure via the hud.ai connector; the pinned
OpenReward deployment (`jaivir/no-start-env` on openreward.ai, serving the ORS
HTTP protocol from the `Jaiparmar940/no-start-env-serving` mirror) speaks a
different protocol on different infrastructure. It stays untouched and remains
the OpenReward listing. A **HUD-native packaging** was therefore implemented —
as the smallest possible adapter around the existing environments, mirroring
the approach (and the parity discipline) of the existing OpenReward adapter.

What *can* be attached without new code:

| Existing asset | DataVendor attachment |
|---|---|
| OpenReward deployment | Not attachable; keep as the OpenReward listing |
| GitHub repo (`Jaiparmar940/rlenv`) | Attachable as a **codebase/repo asset** via the GitHub connector (redacted file-tree preview) — optional listing add-on, human decision |
| Results/audit/writeup docs | Listing supporting material (see §6) |
| The new `deploy/hud/*` environments | The **environment + taskset assets**, via `hud deploy` + `hud sync tasks` under the vendor org's HUD account |

## 2. What was added

Everything lives in isolated deployment directories; no existing package
layout, environment file, scenario, prompt, tool, grader, task id, result, or
public claim was modified. The immutable `openreward-v0.1` branch and the
serving mirror were not touched.

```
deploy/hud/
├── README.md                   overview + one-command checks
├── PROVENANCE.md               rights/provenance manifest for listings
├── stage.py                    mirrors src/nostart and decision-layer/kitchen_task
│                               into each env dir's gitignored vendor/ (hud deploy
│                               tarballs only the env dir); --check proves byte-identity
├── expert_trajectories.py      reads MOCK_SCRIPTS out of scripts/run_evals.py (ast,
│                               no import) so parity replays the pinned expert paths
├── no-start-env/
│   ├── adapter_core.py         the whole adapter: wraps ToolSession + grade()
│   │                           unchanged; pinned Inspect tool specs; opaque ids
│   │                           ns-01..ns-05 identical to the OpenReward listing
│   ├── env.py                  HUD Environment + FastMCP server (7 tools) +
│   │                           diagnose(task_id) template; reward = total/100,
│   │                           GradeBreakdown in grade info, subscores in trace
│   ├── tasks.py / tasks.json   discoverable taskset (5 rows, tier column)
│   ├── pyproject.toml / uv.lock  deps (hud only), lock via `uv lock`
│   ├── Dockerfile.hud          python:3.12-slim; build-time health check
│   └── README.md               listing-facing docs + parity contract
├── decision-layer-kitchen/
│   ├── adapter_core.py         wraps make_scenario/KitchenEnv/grade unchanged;
│   │                           symbolic backend; opaque ids dlk-01..dlk-03
│   ├── env.py                  HUD Environment + FastMCP server (1 tool: act) +
│   │                           put_away(task_id, seed) template
│   ├── tasks.py / tasks.json   discoverable taskset (3 rows, seed column)
│   ├── pyproject.toml / uv.lock / Dockerfile.hud / README.md
├── scripts/protocol_check.py   end-to-end wire-protocol verification (local
│                               subprocess or built-image runtimes)
└── tests/                      51 parity tests, run in the project venv
```

Design decisions worth knowing:

- **No forked domain code.** Each `adapter_core.py` imports the authoritative
  package (installed, `vendor/` staged copy, or checkout source, in that
  order). `vendor/` is a gitignored build artifact; `stage.py --check` and a
  parity test assert byte-identity with the source tree.
- **no-start prompt**: HUD's `tasks.start` returns one prompt string, so the
  uncoached system prompt and complaint user message are joined with a blank
  line; `prompt_blocks()` keeps them separate for system-role harnesses. Same
  concession the OpenReward adapter documents.
- **no-start tool specs** are byte-matched to what Inspect serialized for the
  published run (descriptions with their embedded newlines, JSON schemas with
  `additionalProperties: false`, `required: []` on no-arg tools, the
  `finish` submit-tool wording) — pinned in code and tested against
  `inspect_ai.tool.ToolDef` at test time, the same regression pattern the
  OpenReward parity work established.
- **no-start invalid input** (`measure_voltage` on a bad node/state) surfaces
  as an MCP error frame carrying the bare environment message — the model-visible
  bytes Inspect shows — verified on the wire.
- **Unfinished no-start episodes**: `tasks.grade`'s answer is graded as the
  diagnosis, mirroring the Inspect scorer's `state.output.completion` fallback
  and the ORS `@terminal` tool.
- **decision-layer**: one `act(action)` tool preserving the published free-text
  grammar (invalid actions still cost an action); observations are
  `KitchenEnv.observation()` verbatim; grading queries backend state only.
  Oracle execution is described accurately in the env description, README and
  prompt framing. The agent's final message is not a grading input (findings
  are declared in-episode via `declare`).
- **decision-layer backend**: symbolic (pure stdlib) is the managed product;
  robosuite/RoboCasa/MuJoCo and the ~10 GB assets are in no container or
  bundle. The RoboCasa backend file ships in the mirror for provenance but is
  never imported and has no deps in the image.
- **Leakage**: task specs carry only opaque ids (+tier / +seed). Parity tests
  assert no scenario name, variant name, or fault vocabulary appears in task
  specs, prompts, or tool specs. no-start ids `ns-01..ns-05` are identical to
  the OpenReward listing (test-pinned against `nostart.openreward.env`).

## 3. Exact local verification results

Machine: the dev Mac (Apple Silicon, Docker Desktop 29.6.2). Project venv
`.venv` (Python 3.14.6); HUD SDK venv `.venv-hud` (Python 3.12.11, `hud`
0.6.12, `uv` 0.12.3 — `hud` pins `<3.13`, hence the second venv).

**Baseline before any edits (all green, unchanged after):**

| Check | Result |
|---|---|
| `pytest tests/` (no-start suite) | 106 passed, 1 skipped (skip = openreward not yet installed; after `pip install openreward` for parity testing: **121 passed**) |
| `pytest decision-layer/tests/` | **19 passed** |
| `scripts/sanity_check.py` | ALL CHECKS PASSED, exit 0 |
| `scripts/check_determinism.py` | DETERMINISM OK — 5 scenarios reproduce exactly (same stream sha256 prefixes as documented) |
| `decision-layer/scripts/validate_sim_backend.py` under `.venv-sim` (RoboCasa/MuJoCo) | **ALL PASS** — expert 100.0 on all three variants on the real sim; teleport probe capped at 40.0. Environment untouched. |

**After packaging (nothing regressed, everything new green):**

| Check | Result |
|---|---|
| `pytest tests/` | 121 passed |
| `pytest decision-layer/tests/` | 19 passed |
| `scripts/sanity_check.py` / `check_determinism.py` | pass / pass |
| `pytest deploy/hud/tests/` (new parity suite) | **51 passed** — includes per-scenario expert-trajectory replay (streams byte-identical, GradeBreakdown identical, reward = total/100, expert still 100.0), end-to-end Inspect-vs-managed score equality via mockllm, the pinned adversarial/haiku sequences for the kitchen task, leakage, determinism, and vendor byte-identity |
| `stage.py --check` | OK for both mirrors |
| `hud task list -s deploy/hud/no-start-env` | 5 tasks, opaque ids |
| `hud task list -s deploy/hud/decision-layer-kitchen` | 3 tasks, opaque ids |
| `protocol_check.py --runtime local` | **PROTOCOL CHECK PASSED — 233 assertions, 0 failures** (manifest/capability shape, wire tool specs byte-matched, per-call observation parity vs the in-process adapter, malformed input, unknown tool, episode termination, post-termination refusal, reward and grade-metadata checks, all 8 tasks) |
| `protocol_check.py --runtime docker` (images built `--no-cache` from clean context) | **PROTOCOL CHECK PASSED — 233 assertions, 0 failures** against `sn-no-start-env-hud:0.1.0` and `sn-decision-layer-kitchen-hud:0.1.0`; one fresh container per rollout |
| Container builds | both images build clean; each Dockerfile runs a build-time health check (import + task count + prompt construction) that fails the build on drift |

Lock files (`uv.lock`) were generated by `uv lock` (uv 0.12.3), not
hand-authored.

**What was NOT verified (and is not claimed):**

- No remote deployment of any kind was performed. `hud deploy`, `hud sync`,
  vendor registration, and listing creation all require the human account
  holder (see §4). Nothing here should be read as "deployed to HUD".
- `hud eval tasks.py claude` (a live-model rollout) was not run — the
  protocol checks use a scripted agent, so no provider spend and no provider
  outputs are included.
- The Docker runtime path was verified via the HUD SDK's `DockerRuntime`
  driving the built images; the images have not been run on HUD's actual
  platform runtime.

## 4. Remaining manual deployment steps (human only)

1. **Vendor onboarding** at datavendor.ai: create the account/org
   (Second Nature Labs), complete organization setup, HUD review, and sign the
   HUD vendor NDA (Tier 1). The Terms of Service and NDA are agreements —
   review before accepting.
2. **HUD platform**: create/log into the HUD account, `hud set HUD_API_KEY=...`.
3. **Deploy** (from this branch, after `python deploy/hud/stage.py`):
   ```
   hud deploy deploy/hud/no-start-env
   hud deploy deploy/hud/decision-layer-kitchen
   ```
4. **Sync tasksets**:
   ```
   cd deploy/hud/no-start-env        && hud sync tasks no-start-env-v0.1
   cd deploy/hud/decision-layer-kitchen && hud sync tasks decision-layer-kitchen-v0.1
   ```
5. **Smoke the hosted deployment** before listing: run the protocol check's
   trajectories against the platform (`hud eval` on the synced taskset with a
   cheap model, or `HUDRuntime`) and confirm rewards match §3.
6. **Publish the listing(s)** on DataVendor (Add supply → Publish a listing):
   attach the environment + taskset assets via the hud.ai connector, set
   per-asset pricing, paste the listing copy, submit for review.
7. Optional: attach the GitHub repo as a codebase asset (redacted-tree
   preview) if selling source access alongside the managed environments.

## 5. Exact DataVendor "Assets" selections recommended

One compound listing (or two separate listings — pricing decision):

| Asset kind | What to attach | Notes |
|---|---|---|
| **Environment** | `no-start-env` (HUD deployment from `deploy/hud/no-start-env`) | priced per environment; sampleable |
| **Taskset** | `no-start-env-v0.1` (5 tasks) | priced per task; tier column carries easy/medium/hard |
| **Environment** | `decision-layer-kitchen` (HUD deployment from `deploy/hud/decision-layer-kitchen`) | priced per environment |
| **Taskset** | `decision-layer-kitchen-v0.1` (3 tasks) | priced per task |
| *(optional)* Repo | `Jaiparmar940/rlenv` via GitHub connector | buyers see a redacted file tree pre-purchase |

## 6. Recommended supporting assets per listing

**no-start-env**: `docs/openreward_card.md` (environment card; applies almost
verbatim), `no-start-env.md`, `WRITEUP.md`, `DOMAIN_TRUTH.md`,
`results/results.md` (225-episode table), `results/audit.md` (4/4 leakage/
determinism audit), `results/scale_curve.md`, `results/clean_clone.md`,
`deploy/hud/PROVENANCE.md`.

**decision-layer-kitchen**: `decision-layer/README.md`,
`decision-layer/AUDIT.md`, `decision-layer/handoff/RESULTS.md`,
`decision-layer/handoff/LIMITS.md` (oracle/stub honesty),
`decision-layer/handoff/CLEAN_RUN.md`, `decision-layer/results/llm_traces.md`,
`decision-layer/demo.gif` (RoboCasa validation render with oracle disclaimer),
`deploy/hud/PROVENANCE.md`.

These are evidence documents, not executable ground truth: buyers run the
managed environments; the documents describe what was measured and how.

## 7. Known limitations

- **Prompt channel**: HUD delivers one prompt string; the no-start system/user
  split is a blank-line join (documented; `prompt_blocks()` preserves the
  split for custom harnesses). Harnesses that put everything in the user turn
  may score differently from the published Inspect run — the same caveat the
  OpenReward card carries.
- **Message limits are harness-side.** The published run capped episodes at 50
  messages via Inspect's `basic_agent`. HUD agents control their own step
  budget (`--max-steps`); the environment does not enforce one for no-start.
  The kitchen task's 30-action cap is environment-side and enforced.
- **Sequential episodes per environment instance.** Each env instance holds
  one live episode (matching HUD's one-held-task wire protocol). Concurrency
  comes from the runtime starting more instances, which is how HUD scales.
- **Protocol-check reward tolerance**: the wire checks assert reward equality
  against a shadow episode that includes the protocol probes (extra actions);
  the clean expert-scores-100 claim is held by the parity tests, which replay
  trajectories with nothing added.
- **`hud` SDK requires Python ≥3.11,<3.13** — a separate venv from the
  project's 3.14. Containers use 3.12 and are unaffected.
- **hud 0.6.x is a moving target** (0.6.13 released during this work; pinned
  `<0.7` in both pyprojects, lock files pin exact versions).
- **Decision-layer statistical evidence** remains two live LLM episodes of one
  model (documented in LIMITS.md); the managed packaging adds no new model
  results, and listings should not imply otherwise.
- **RoboCasa validation** was re-run locally via the untouched `.venv-sim`
  (ALL PASS) but remains single-machine, single-layout evidence, as
  LIMITS.md states.

## 8. Commands for a clean build and local test

```bash
# once: HUD toolchain venv (hud needs 3.11/3.12)
python3.12 -m venv .venv-hud && .venv-hud/bin/pip install hud uv

# stage + verify the vendor mirrors
python deploy/hud/stage.py && python deploy/hud/stage.py --check

# parity tests (project venv)
.venv/bin/python -m pytest deploy/hud/tests -q

# full existing suites + physics/determinism gates
.venv/bin/python -m pytest tests/ -q
(cd decision-layer && ../.venv/bin/python -m pytest tests/ -q)
.venv/bin/python scripts/sanity_check.py
.venv/bin/python scripts/check_determinism.py

# wire protocol, local runtime (no Docker, no keys)
.venv-hud/bin/python deploy/hud/scripts/protocol_check.py

# containers from a clean context, then the same checks against the images
(cd deploy/hud/no-start-env        && docker build --no-cache -f Dockerfile.hud -t sn-no-start-env-hud:0.1.0 .)
(cd deploy/hud/decision-layer-kitchen && docker build --no-cache -f Dockerfile.hud -t sn-decision-layer-kitchen-hud:0.1.0 .)
.venv-hud/bin/python deploy/hud/scripts/protocol_check.py --runtime docker
```
