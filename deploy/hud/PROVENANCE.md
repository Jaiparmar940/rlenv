# Rights and provenance manifest — Second Nature Labs marketplace packaging

Covers the two managed environments packaged under `deploy/hud/`:
`no-start-env` and `decision-layer-kitchen`. Prepared 2026-08-07 for
DataVendor/HUD listing; statements below describe this repository as of the
`feat/datavendor-packaging` branch.

## What Second Nature Labs owns

Second Nature Labs (Jaivir Parmar) owns the environment design and
implementation being sold:

- **no-start-env** — the resistance-network vehicle model, fault scenarios,
  physical constants and their documentation (`DOMAIN_TRUTH.md`), tools,
  prompts, cheat-resistant grader, adversarial test suite, Inspect task,
  OpenReward adapter, and the empirical evaluation (225-episode published
  benchmark, audits, determinism checks). MIT-licensed in this repository
  (`LICENSE`).
- **decision-layer kitchen task** — the task design, hidden-state variants,
  action grammar and reveal rules, three-way grader with its anti-cheat
  protections, symbolic backend, RoboCasa backend *binding* (the adapter code,
  not RoboCasa itself), scripted expert, adversarial audit, and validation
  results.
- The marketplace packaging in `deploy/hud/` (adapters, parity tests, protocol
  checks, container definitions, this manifest).

**Domain validation is human work.** The physics of no-start-env was verified
by a human domain expert (Jaivir Parmar), who caught multiple physics bugs that
had passed the automated test suite; the physics invariants encode those
catches. The adversarial grader testing and the empirical evaluation are
likewise Second Nature work products.

**Implementation was agent-assisted.** Substantial portions of the code and
documentation in this repository, including this packaging, were written with
AI coding agents operating under human direction and review. Second Nature
Labs owns and stands behind the result: the environment design, the domain
validation, the adversarial testing, and the empirical evaluation are Second
Nature's own contributions.

## Third-party components — used, not transferred

Any sale of these environments is **non-exclusive** and transfers no ownership
of any third-party dependency. Buyers receive the Second Nature code and the
right to run it; third-party components remain under their own licenses:

| Component | Role | License | Shipped in container/bundle? |
|---|---|---|---|
| [Inspect (inspect-ai)](https://github.com/UKGovernmentBEIS/inspect_ai) | eval framework the published benchmark runs on | MIT | No — dev/eval dependency only |
| [OpenReward SDK](https://openreward.ai) | ORS serving adapter (`src/nostart/openreward/`) | per its distribution | No — optional extra |
| [HUD SDK (`hud`)](https://github.com/hud-evals/hud-python) | managed-environment protocol, serving, CLI | MIT | Yes — installed from PyPI at image build |
| [FastMCP](https://github.com/jlowin/fastmcp) | MCP tool server inside each environment | Apache-2.0 | Yes — arrives with `hud` |
| pydantic | schema/validation | MIT | Yes — arrives with `hud` |
| [robosuite](https://github.com/ARISE-Initiative/robosuite) | sim framework under the RoboCasa validation backend | MIT | **No** |
| [RoboCasa](https://github.com/robocasa/robocasa) | kitchen scenes for the validation backend | MIT | **No** |
| [MuJoCo](https://github.com/google-deepmind/mujoco) | physics engine under robosuite | Apache-2.0 | **No** |
| RoboCasa kitchen assets (~10 GB download) | textures/models for the validation scenes | RoboCasa's asset terms; includes third-party model/texture sources | **No** — never bundled, never uploaded |

Notes:

- The **decision-layer managed environment contains no robosuite, RoboCasa,
  MuJoCo, or RoboCasa-asset content**. Its production backend is the pure
  standard-library symbolic model. RoboCasa/MuJoCo appear only as *validation
  evidence* (results documents, traces, a GIF rendered locally by Second
  Nature from a licensed install) and as instructions for reproducing the
  validation on the buyer's own install.
- `decision-layer/demo.gif` and `decision-layer/media/` frames were rendered by
  Second Nature from a local RoboCasa/MuJoCo scene as documentation of the
  validation run.
- Model evaluation results (`results/results.md` etc.) name third-party models
  (Anthropic, OpenAI, Google, xAI, Meta, Mistral); those are benchmark
  measurements published by Second Nature, not redistributions of any model.
- No API keys, credentials, model provider outputs beyond the published
  benchmark tables/transcript excerpts, or private untracked files are part of
  any listing bundle.

## Statement for listings

> Second Nature Labs offers this environment non-exclusively. Second Nature
> owns the environment design, domain validation, adversarial testing, and
> empirical evaluation; implementation was agent-assisted under human
> direction. The sale transfers no ownership of third-party dependencies
> (Inspect, OpenReward, HUD, FastMCP, robosuite, RoboCasa, MuJoCo, or RoboCasa
> assets), which remain under their own licenses.
