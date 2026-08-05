# STATUS — deliverables checklist vs. TASK_SPEC

Verified 2026-08-05, branch `feat/decision-layer`. Evidence commands were run
on this machine; CLEAN_RUN.md re-verifies the install path from scratch.

| # | deliverable | status | evidence |
|---|---|---|---|
| 1 | Runnable task: `python run_episode.py --agent scripted` solving it correctly | **PASS** | Scripted expert scores 100.0 on all 3 variants on BOTH backends: `run_episode.py --agent scripted` (symbolic, bare python3.12, 0.06s) and `--backend robocasa` (CLEAN_RUN.md, 6.1s) |
| 2 | Agent interface: one loop, observation string in / action string out | **PASS** | `kitchen_task/agents.py` — `ScriptedExpert`, `LLMAgent`, `HumanAgent` are all plain `str -> str` callables; two live claude-haiku-4-5 episodes ran through it unmodified (`results/llm_traces.md`) |
| 3 | Grader with three-way breakdown printed per episode | **PASS** | inference/parsimony/intervention printed by every `run_episode.py` run; see any transcript in this bundle |
| 4 | Inspect actions have a cost; inspect-everything penalized | **PASS** (mechanism differs from spec) | Cost = action-count parsimony vs. expert baseline, not a per-inspect dollar meter (README "ship-today decisions"); `test_inspect_everything_spam_scores_below_targeted` and `test_open_everything_solver_is_not_capped_just_inefficient` prove spam scores strictly worse |
| 5 | Success predicates checked against sim state, not agent claims | **PASS** | Grader queries the `Backend` protocol only; RoboCasa backend answers from geometry (`point_in_fixture` on MuJoCo poses, door joints). `audit_episode.txt` shows the geometry path live |
| 6 | Adversarial audit + AUDIT.md | **PASS** | 12 probes, 5 real fixes; every probe pinned as a regression test (19 tests green). See AUDIT.md in this bundle |
| 7 | README: product framing, oracle-by-design stated plainly, install, GIF | **PASS** (install bug found & fixed during clean run) | `decision-layer/README.md`; original sim-install line (`pip install robosuite`) was broken — caught by CLEAN_RUN.md, corrected to robosuite-master-from-source |
| 8 | 60-second recording | **PASS** | `handoff/episode.gif` — 26 frames, ~52s at 2s/frame, 3.2 MB; title card + per-frame oracle disclaimer |
| 9 | One API-model trace | **PASS** | Two live traces (claude-haiku-4-5): symbolic `fridge_full` 87.5, RoboCasa `container_missing` 60-as-run / 80 under current grader (`results/llm_traces.md`); action sequences pinned as tests |
| 10 | Pushed to the rlenv repo | **PASS** (branch, not main) | `origin/feat/decision-layer` (latest push 67786b7 + this bundle); merge to main deliberately left to the founder |

## Honest caveats attached to the PASSes

- LLM coverage is 2 episodes of 1 model (haiku). No frontier sweep, no
  multi-epoch statistics. The harness needs nothing new to run one; it has
  simply not been run.
- `nominal` has no LLM episode at all.
- Item 4's "cost" is uniform per action; a `pick` costs the same as an
  `open`. Differential inspect pricing is a v0.2 decision.
- The two LLM scores were produced under two different grader versions; the
  container_missing 60→80 change is documented in AUDIT.md and both numbers
  are reported everywhere the episode is cited.
