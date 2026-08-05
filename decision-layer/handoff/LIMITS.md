# LIMITS — what an expert reviewer will (correctly) poke

## Oracle / stubbed by design

- **No physics stepping, ever.** Actions call `mj_forward` only. Objects
  teleport; nothing falls, settles, or collides. Doors snap between open and
  closed — no partial angles, no in-swing collision.
- **No motion, grasping, or robot control.** The arm in the scene never
  actuates (stated on the GIF, in the README, and here). "Held" is a fixed
  floating pose near the gripper — a rendering convention, not a grasp.
- **Trash is a pseudo-bin**: a fixed pose below the floor plus a set in the
  backend. There is no trash fixture; "in the trash" is not geometric.
- **Fridge capacity is symbolic**: a 3-slot counter, not geometric packing.
  A RoboCasa author will notice the rendered shelf could physically hold
  more. The refusal ("no room") is a rule, not a collision result.

## Simulation fidelity gaps

- Region queries use `point_in_fixture` on the object's **center point**;
  partial-overlap edge cases untested. Anything not inside a fixture volume
  reads as "counter" — an object teleported to the floor would grade as
  on-the-counter (unreachable through env actions, reachable through the
  backend).
- `fridge_shelf` is the **whole fridge interior volume**, not a particular
  rack; the 3 "slots" don't correspond to distinct rendered shelves.
- Observations are structured text, not pixels, and "visible" is symbolic:
  the counter is always fully visible; there is no viewpoint, FOV, or
  occlusion model despite the README's "from the current viewpoint" phrasing
  being aspirational for v0.1.
- One kitchen only: layout 1 / style 8, seed-fixed. Geometry assumptions are
  unverified on the other 59 layouts/styles.

## Information-design caveats

- The microwave-blink cue appears **only** in `container_missing`, so its
  absence leaks "the container is not in the microwave." t=0
  indistinguishability holds for `nominal` vs `fridge_full` (test-pinned)
  but `container_missing` is identifiable (not localizable) at t=0.
- The `declare` vocabulary is a small keyword list; the unparseable-declare
  fallback (AUDIT.md) softens but does not eliminate parser strictness. New
  phrasings will hit it.

## Grader edges not yet exercised

See AUDIT.md "Not yet probed": declare spam, innocent-item stashing (side
condition checks only the trash), held-at-end, parser fuzzing, layout sweep,
and the expert-baseline circularity (parsimony baseline = the author's own
scripted expert, test-pinned).

## Statistical honesty

- LLM evidence is **two live episodes of one model** (claude-haiku-4-5),
  n=1 per cell, two grader versions across them (both scores reported). No
  frontier models, no epochs, no variance. The prior no-start-env work
  showed n=5 cells are already fragile; n=1 proves the pipeline
  discriminates, nothing more.
- Expert baselines and trap design were verified by the scripted expert and
  by hand-play, not by an independent domain expert.

## Reproducibility pins

- robocasa 1.0.1 (git b4684e6) + robosuite **master @ 5ce6643** (required;
  PyPI 1.5.2 is incompatible — found the hard way, see CLEAN_RUN.md).
  robosuite master is an unversioned moving target; the hash above is the
  tested state.
- Kitchen assets ~23 GB extracted (~10 GB download); the downloader prompts
  on stdin (documented in README).
- `mink 0.0.5 requires numpy<2` pip warning is expected and harmless (mink
  is IK for motor control, which this task never uses).
- macros_private.py files generated in both source trees by their
  setup_macros scripts (cosmetic warnings without them).
