# deploy/hud — DataVendor/HUD marketplace packaging

Isolated packaging that binds the two Second Nature Labs environments onto the
HUD v6 managed-environment protocol so they can be listed on DataVendor
(datavendor.ai, HUD's marketplace). Nothing outside `deploy/` and the docs is
touched: the environments themselves live where they always have
(`src/nostart/`, `decision-layer/kitchen_task/`) and are imported unchanged.

Read `docs/datavendor_packaging.md` first — it records what DataVendor can
attach directly, what was added here and why, the verification results, and the
remaining human-only deployment steps.

```
deploy/hud/
├── README.md                  this file
├── PROVENANCE.md              rights/provenance manifest for listings
├── stage.py                   mirror source packages into each env's vendor/
├── expert_trajectories.py     read the pinned expert scripts out of run_evals.py
├── no-start-env/              HUD environment #1 (5 tasks, ns-01..ns-05)
├── decision-layer-kitchen/    HUD environment #2 (3 tasks, dlk-01..dlk-03)
├── scripts/
│   └── protocol_check.py      end-to-end wire-protocol verification
└── tests/                     adapter parity tests (run in the project venv)
```

## The one-command checks

```bash
# 1. adapter parity (project venv; no hud dependency)
.venv/bin/python -m pytest deploy/hud/tests -q

# 2. stage vendor mirrors, verify byte-identity
python deploy/hud/stage.py && python deploy/hud/stage.py --check

# 3. wire protocol end to end (HUD SDK venv; no API keys)
.venv-hud/bin/python deploy/hud/scripts/protocol_check.py

# 4. same, against the built containers
.venv-hud/bin/python deploy/hud/scripts/protocol_check.py --runtime docker
```

The HUD SDK needs Python 3.11/3.12 (`hud` pins `<3.13`; the project venv is
3.14), hence the separate `.venv-hud`:

```bash
/opt/homebrew/bin/python3.12 -m venv .venv-hud
.venv-hud/bin/pip install hud uv
```
