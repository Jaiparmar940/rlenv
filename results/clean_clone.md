# Clean-clone verification

Proof that a lab eval engineer can clone this repo cold, install it, and run it
**with no API keys**. Every command below was executed verbatim in a fresh
`git clone` with a brand-new virtualenv (not the repo's `.venv`).

- Verified: 2026-07-12, commit `76b88f6` + the fixes listed at the bottom.
- Platform: Windows 11, CPython 3.13.5, `pip install -e ".[dev,models]"`.
- Everything below is **offline**. No provider key was present in the clean clone.

## Verified quickstart

```bash
git clone <repo-url> no-start-env
cd no-start-env

# 1. Virtualenv (>=3.11). Use whatever names your platform gives you:
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install. [dev] adds pytest; [models] adds the provider SDKs that
#    Inspect needs for real-model runs (skip it if you only want --mock).
pip install -e ".[dev,models]"

# 3. Physics self-check — computes what every reading should be and asserts it.
python scripts/sanity_check.py           # -> ALL CHECKS PASSED

# 4. Tests.
python -m pytest tests/ -q               # -> 70 passed

# 5. Play a scenario by hand (interactive REPL; 'help' lists commands).
python scripts/play.py --list
python scripts/play.py --scenario medium_corroded_ground

# 6. Offline end-to-end pipeline check: a scripted expert against all three
#    scenarios. No API key needed. Writes results/results.md + transcripts/.
python scripts/run_evals.py --mock       # -> mockllm/model scores 100.0 x3

# 7. Real models (needs keys). Copy .env.example -> .env and fill in the
#    providers you want; model ids use Inspect's provider/model form.
cp .env.example .env
python scripts/run_evals.py --models anthropic/claude-sonnet-5 --scenarios all --epochs 3
```

A non-interactive `play.py` episode (useful in a smoke script — the REPL reads
stdin, so you can just pipe it):

```bash
printf 'measure_voltage battery_negative engine_block cranking\nreplace_part ground_strap\nattempt_start\nfinish ground_strap corroded\nquit\n' \
  | python scripts/play.py --scenario medium_corroded_ground
```

## PASS/FAIL log

| # | Step | Result |
|---|---|---|
| 1 | `git clone` into empty dir | PASS |
| 2 | fresh `python -m venv .venv` (3.13.5) | PASS |
| 3 | `pip install -e ".[dev]"` | PASS (exit 0) |
| 3b | `pip install -e ".[dev,models]"` (after fix) | PASS (exit 0) |
| 4 | `python scripts/sanity_check.py` | PASS — ALL CHECKS PASSED, exit 0 |
| 5 | `python -m pytest tests/ -q` | PASS — 70 passed, exit 0 |
| 6 | `python scripts/play.py --list` | PASS — lists 3 scenarios, exit 0 |
| 7 | `play.py` scripted episode (both easy + ground) | PASS — measure/replace/start/finish all work, exit 0 |
| 8 | `python scripts/run_evals.py --help` | PASS — exit 0 |
| 9 | `python scripts/run_evals.py --mock` (**no .env present**) | PASS — exit 0; expert scores 100.0 on all 3 scenarios; results.md + 3 transcripts written |
| 10 | provider clients instantiate offline (anthropic / openai / grok / google) | FAIL before fix, PASS after |

`--mock` with **no `.env` file at all** works: `load_dotenv()` on a missing path
is a no-op, so the offline path has no undeclared env-var requirement. Good.

## Fixes applied

1. **`pyproject.toml` — declared `python-dotenv`.** `scripts/run_evals.py` does
   `from dotenv import load_dotenv` but the package was never declared. It only
   worked because `inspect-ai` happens to depend on it transitively; an
   inspect-ai release that dropped it would break the clean-clone install with
   an ImportError. Now a direct dependency.

2. **`pyproject.toml` — new `[models]` extra** (`anthropic`, `openai`,
   `google-genai`, `xai-sdk`). Inspect ships every provider's SDK as an
   *optional* dependency, so a bare `pip install -e ".[dev]"` clone could run
   `--mock` but **not a single real model** — `--models anthropic/...` died with
   `PrerequisiteError: Anthropic API requires optional dependencies`. Same for
   openai, google, and grok. All four now instantiate after
   `pip install -e ".[dev,models]"`.

3. **`scripts/smoke_eval.sh` — venv path was posix-only.** It probed
   `.venv/bin/python`, which never exists on Windows (`.venv/Scripts/python.exe`),
   so it silently fell through to system `python` — the wrong interpreter, or
   none. Now probes both layouts before falling back.

4. **`.gitignore` — un-ignored this file.** `results/` is ignored wholesale, so
   `results/clean_clone.md` would never have shipped to a cold cloner. Added a
   `!results/clean_clone.md` negation. (Jaivir: if you'd rather this live
   outside `results/`, move it — the ignore rule is why it looked absent.)

Nothing in `grader.py`, `world.py`, `scenarios.py`, `prompts.py`, or `task.py`
was touched; no install/run bug lived in them.
