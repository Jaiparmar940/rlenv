# CLEAN_RUN — venv deleted, reinstalled from README, one episode run

Performed 2026-08-05 on the build machine (macOS / Apple Silicon).
Procedure: `mv .venv-sim .venv-sim.bak`, then follow the README sim-install
verbatim. **Substitution disclosed**: the `git clone` steps reused the
existing clones at `~/sim-deps/` (robocasa b4684e6 + its 23 GB of extracted
assets) instead of re-cloning/re-downloading; the venv itself was rebuilt
from nothing.

## Finding #1 (real): README install instructions were broken

The README at the time said `pip install robosuite`. Fresh venv, verbatim
README, first episode attempt:

```
$ python3.12 -m venv .venv-sim
$ .venv-sim/bin/pip install robosuite imageio        # PyPI robosuite 1.5.2
$ .venv-sim/bin/pip install -e ~/sim-deps/robocasa
$ .venv-sim/bin/python run_episode.py --agent scripted --backend robocasa --variant nominal
...
  File ".../robocasa/environments/kitchen/kitchen.py", line 503, in __init__
    super().__init__(
TypeError: ManipulationEnv.__init__() got an unexpected keyword argument 'load_model_on_init'
```

Root cause: robocasa requires robosuite **master from source** (its own
README says so); PyPI 1.5.2 predates `load_model_on_init`. The working dev
install had robosuite-from-source, so the doc bug was invisible until this
clean run. README fixed to clone robosuite master (tested @ 5ce6643) and to
correct the asset-download size (~10 GB, not 5) and its stdin prompt.

## Re-run under the corrected README: PASS

```
$ .venv-sim/bin/pip install -e ~/sim-deps/robosuite    # master @ 5ce6643
$ .venv-sim/bin/python run_episode.py --agent scripted --backend robocasa --variant nominal

=== variant=nominal seed=0 backend=robocasa agent=scripted ===
  [ 1] open fridge                                   -> The fridge is now open.
  [ 2] declare fridge has space, everything nominal  -> Noted: 'fridge has space, everything nominal'
  [ 3] pick leftovers                                -> You are holding the leftovers container.
  [ 4] place leftovers fridge                        -> The leftovers container is now in/on the fridge.
  [ 5] close fridge                                  -> The fridge is now closed.
  [ 6] done                                          -> You step back from the counter.
  inference       40.0 / 40
  parsimony       25.0 / 25
  intervention    35.0 / 35
  TOTAL          100.0 / 100

real: 6.079 total   (3.75s user, 0.98s system — includes MuJoCo env build)
```

## Zero-dependency path: PASS

The decision layer alone, bare interpreter, no venv, no packages:

```
$ /opt/homebrew/bin/python3.12 run_episode.py --agent scripted --backend symbolic
...
  TOTAL          100.0 / 100
mean total over 3 variants: 100.0
real: 0.061 total
```

## Not verified by this clean run

- A truly cold clone (fresh `git clone` of robosuite/robocasa + full 10 GB
  asset download) — the asset step alone is hours-scale and was reused.
- Any machine other than this one (no Linux/Intel-mac run).
- The `[--agent llm]` path from a clean venv (needs `pip install anthropic`
  \+ `ANTHROPIC_API_KEY`; exercised earlier from the dev venv only).
