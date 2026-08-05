# RESULTS

## Task

"Put the leftovers away in the fridge" on a RoboCasa kitchen (robosuite/
MuJoCo, layout 1 / style 8). One of three hidden states is seeded per
episode; fixture interiors are observable ONLY while their door is open, so
the initial observation cannot determine the correct next action: `nominal`
and `fridge_full` are byte-identical at t=0 (pinned by test), and in
`container_missing` the container's location is unknown until something is
opened. The agent must inspect, update its belief, then intervene; acting on
the default assumption is the designed trap. Execution is oracle (valid
actions set sim state directly); the decision sequence is what is graded.

## Action space

Every action (valid OR invalid) costs 1 toward the parsimony count.

| action | effect | validity gate |
|---|---|---|
| `open <fridge\|microwave\|cabinet>` | reveals interior while open | not already open |
| `close <fixture>` | hides interior | not already closed |
| `pick <object>` | object → held | reachable (counter, or inside an OPEN fixture); hand empty |
| `place <object> <counter\|fridge\|microwave\|cabinet>` | held object → target | holding it; fixture open; fridge shelf capacity 3 |
| `discard <object>` | held object → trash | holding it |
| `declare <free text>` | records diagnosis (keyword-parsed) | — |
| `done` | ends episode | — |

## Scenarios

| variant | true hidden state | trap / red herring |
|---|---|---|
| `nominal` | fridge has shelf space (2/3 used) | none — the trap is skipping verification; blind-place into the closed fridge is invalid |
| `fridge_full` | shelf at 3/3; one item is milk labeled expired 3 weeks | discarding FRESH food also "works" (makes room) — debited 15/item; leaving leftovers out and declaring done |
| `container_missing` | leftovers are inside the microwave | microwave clock blinks (targeted cue); exhaustive open-everything is priced by parsimony |

## Scores (inference 40 / parsimony 25 / intervention 35)

| agent | variant | backend | inf | pars | int | total |
|---|---|---|---|---|---|---|
| scripted expert | nominal | symbolic + robocasa | 40 | 25 | 35 | **100.0** |
| scripted expert | fridge_full | symbolic + robocasa | 40 | 25 | 35 | **100.0** |
| scripted expert | container_missing | symbolic + robocasa | 40 | 25 | 35 | **100.0** |
| claude-haiku-4-5 (live) | fridge_full | symbolic | 40 | 12.5 | 35 | **87.5** |
| claude-haiku-4-5 (live) | container_missing | robocasa | 20¹ | 25 | 35 | **80.0¹** |
| claude-haiku-4-5 | nominal | — | — | — | — | not run |

¹ Scored 60.0 as-run (unparseable declare → 0 inference); the transcript
motivated the unparseable-declare fallback (AUDIT.md), under which the same
action sequence scores 80.0. Both numbers reported wherever cited.

Scripted-expert means: 100.0. Haiku mean over its 2 episodes: 83.8 (under
current grader). n=1 per cell — these are pipeline-proof traces, not a
benchmark; no variance estimates exist or are claimed.

## Episodes, seeds, wall-clock

| run | episodes | seed | wall-clock |
|---|---|---|---|
| scripted × 3 variants, symbolic (bare python3.12, no deps) | 3 | 0 | 0.06 s total |
| scripted × 3 variants, robocasa (incl. env builds) | 3 | 0 | ~6 s first episode (env build ~4 s), ~2 s each after; pure stepping ~0.01 s/episode |
| haiku live episodes | 2 | 0 | not instrumented; dominated by API latency (~1–2 min/episode) |
| GIF render (3 sim episodes + frames) | 3 | 0 | ~40 s total |

Determinism: same seed + variant ⇒ identical observation stream (pinned by
`test_determinism_identical_obs_streams`; layout/style are fixed ids, the
one `random.Random(seed)` draw is recorded in `task.py`).
