# no-start-env

Simulated vehicle electrical no-start/charging diagnostic environment for LLM agent evaluation (Inspect AI).

**Status:** Phase 2 — grader + tests. Phase 1 manual play via `scripts/play.py`.

## Quickstart (Phase 1)

Use the same Python 3.11+ interpreter for install and run:

```bash
python3.11 -m pip install -e ".[dev]"
python3.11 scripts/play.py --list
python3.11 scripts/play.py --scenario easy_dead_battery
```

Review fault physics in [`DOMAIN_TRUTH.md`](DOMAIN_TRUTH.md) before signing off.

## Tests (Phase 2)

```bash
python3.11 -m pytest tests/ -v
python3.11 -m pytest tests/test_grader.py -k adversarial_demo -s
```
