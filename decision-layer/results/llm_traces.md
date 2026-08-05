# LLM traces (claude-haiku-4-5, 2026-08-04)

Two live episodes through the drop-in agent interface, unedited. Both action
sequences are pinned as grader regression tests.

## fridge_full, symbolic backend — 87.5/100

The signature failure the task is built to expose: **acting on the default
assumption**. The agent grabs the leftovers before inspecting, hits the full
shelf, and pays 5 actions of backtracking (parsimony 12.5/25). Inference and
intervention are clean.

```
[ 1] pick leftovers container      -> holding leftovers            (act-before-inspect)
[ 2] open fridge                   -> 3/3 slots used
[ 3] place leftovers fridge        -> There is no room on the fridge shelf.
[ 4] pick milk carton              -> hands full
[ 5] place leftovers counter       -> backtracking...
[ 6] pick milk carton              -> holding expired milk
[ 7] discard milk carton           -> in the trash
[ 8] pick leftovers container      -> holding leftovers
[ 9] place leftovers fridge        -> in the fridge
[10] close fridge
[11] declare leftovers stored, expired milk discarded
[12] done
inference 40 / parsimony 12.5 / intervention 35 = 87.5
```

## container_missing, RoboCasa/MuJoCo backend — 60 at the time, 80 under the current grader

Full sim pipeline. The agent reads the blinking-microwave cue and inspects the
microwave FIRST — targeted, correct, parsimonious (8 actions = expert count).
But it declared the outcome ("stored in fridge"), not the finding, which our
keyword vocabulary can't parse. Originally −40 inference; this transcript
motivated the unparseable-declare fallback (AUDIT.md): sequence evidence now
earns the implicit 20 → 80 total.

```
[ 1] open microwave                -> (the targeted inspection)
[ 2] pick leftovers container
[ 3] open fridge
[ 4] place leftovers container fridge
[ 5] close fridge
[ 6] close microwave
[ 7] declare leftovers container stored in fridge   (outcome, not finding)
[ 8] done
inference 20 / parsimony 25 / intervention 35 = 80.0
```
