# scripts/

Two groups. The **eval surface** is what a lab runs to reproduce the published
numbers. The **dev/play tools** are for authoring and human verification; they
are not part of the eval and nothing in the eval imports them.

Run everything with the project venv (`.venv/bin/python`, or
`.venv/Scripts/python.exe` on Windows) after `pip install -e ".[dev]"`.
Provider keys go in `.env` (template: `.env.example`).

## Eval surface

| script | what it does | run |
|---|---|---|
| `run_evals.py` | Runs the Inspect eval across models x scenarios x epochs. Writes `results/results.md` (scored table), `results/transcripts/*.md`, and raw `results/logs/*.eval`. Needs provider API keys; `--mock` runs the pipeline offline. | `python scripts/run_evals.py --scenarios all` |
| `scale_curve.py` | Reads the Inspect logs from a run and emits `results/scale_curve.md`: per model x scenario mean/min/max, root-cause-correct fraction, pass^k, verified-fix rate, measured-before-replace rate, and time vs the expert baseline, grouped by scale tier. | `python scripts/scale_curve.py` |
| `sanity_check.py` | Physics gate. Imports only the world/measurement layer, computes what each scenario's voltages should be, asserts them, prints per-scenario tables, exits non-zero on any violation. No model calls, no API key. | `python scripts/sanity_check.py` |
| `check_determinism.py` | Determinism gate. Builds each world twice, replays one fixed action sequence against both, and diffs the full observation streams (seeded meter noise, the visual-inspect roll, state transitions). Any difference fails. Stdlib only. | `python scripts/check_determinism.py` |
| `smoke_eval.sh` | The cheap post-change gate: one mid-tier model x all 3 scenarios x 3 epochs, uncoached, into `results-smoke/`. Run this after changing the env or grader — not the full model matrix. | `scripts/smoke_eval.sh [model]` |

## Dev / play tools

Not part of the eval surface. They exist so a human can drive the scenarios by
hand — the domain verification that caught the physics bugs, and the source of
the human-baseline transcripts.

| script | what it does | run |
|---|---|---|
| `play.py` | Human-in-the-loop CLI. Drive one scenario manually through the same `ToolSession` the agent uses, one tool call per command; `finish` reveals the grade breakdown. | `python scripts/play.py --scenario medium_corroded_ground` |
| `webapp.py` | The same session behind a mobile-friendly web UI on `:8642`. Shows only tool outputs until `finish()`, then the grade breakdown. Expose to a phone with `cloudflared tunnel --url http://localhost:8642`. | `python scripts/webapp.py` |
