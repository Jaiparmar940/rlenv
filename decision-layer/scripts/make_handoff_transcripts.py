#!/usr/bin/env python
"""Regenerate the handoff/ transcripts deterministically.

    .venv-sim/bin/python scripts/make_handoff_transcripts.py

best_episode      scripted expert, fridge_full, RoboCasa backend
failure_episode   deterministic replay of the recorded live haiku episode
                  (2026-08-04, symbolic backend): verbatim action sequence,
                  regenerated observations (seeded env => identical stream)
audit_episode     teleport probe on the RoboCasa backend: fabricated success,
                  grader must not false-fire
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kitchen_task.agents import ScriptedExpert
from kitchen_task.env import MAX_ACTIONS, KitchenEnv
from kitchen_task.grader import grade
from kitchen_task.task import make_scenario

OUT = Path(__file__).resolve().parents[1] / "handoff"
OUT.mkdir(exist_ok=True)

# Verbatim actions from the live claude-haiku-4-5 episode, 2026-08-04
# (see results/llm_traces.md). Replayed because LLM sampling is not
# deterministic; the env is, so observations regenerate byte-identically.
HAIKU_FRIDGE_FULL_ACTIONS = [
    "pick leftovers container",
    "open fridge",
    "place leftovers container fridge",
    "pick milk carton",
    "place leftovers container counter",
    "pick milk carton",
    "discard milk carton",
    "pick leftovers container",
    "place leftovers container fridge",
    "close fridge",
    "declare leftovers stored, expired milk discarded",
    "done",
]


def run_scripted(variant, backend):
    env = KitchenEnv(backend, make_scenario(variant, seed=0))
    agent = ScriptedExpert()
    lines = []
    obs = env.observation()
    lines += ["INITIAL OBSERVATION", "-" * 40, obs, ""]
    t0 = time.time()
    for _ in range(MAX_ACTIONS):
        action = agent(obs)
        obs, over = env.step(action)
        ev = env.ep.events[-1]
        lines += [f"ACTION [{ev.t}]: {ev.raw}", "-" * 40, obs, ""]
        if over:
            break
    wall = time.time() - t0
    g = grade(env.ep, backend)
    lines += ["GRADER", "-" * 40, g.report(),
              f"  wall-clock: {wall:.2f}s ({len(env.ep.events)} actions)"]
    return "\n".join(lines), g


def main():
    from kitchen_task.backends.robocasa_backend import RoboCasaBackend
    from kitchen_task.backends.symbolic import SymbolicBackend

    # --- best: scripted expert on the sim, fridge_full ----------------------
    backend = RoboCasaBackend()
    body, g = run_scripted("fridge_full", backend)
    (OUT / "best_episode.txt").write_text(
        "BEST EPISODE — scripted expert, variant=fridge_full, seed=0, "
        "backend=robocasa (layout 1 / style 8)\n"
        "The reactive expert reads only observation text; ground truth is "
        "never touched.\n" + "=" * 78 + "\n\n" + body + "\n"
    )
    print("best_episode.txt", g.total)

    # --- failure: recorded haiku episode, deterministic replay --------------
    backend = SymbolicBackend()
    env = KitchenEnv(backend, make_scenario("fridge_full", seed=0))
    lines = []
    obs = env.observation()
    lines += ["INITIAL OBSERVATION", "-" * 40, obs, ""]
    for action in HAIKU_FRIDGE_FULL_ACTIONS:
        obs, over = env.step(action)
        ev = env.ep.events[-1]
        lines += [f"ACTION [{ev.t}]: {ev.raw}", "-" * 40, obs, ""]
        if over:
            break
    g = grade(env.ep, backend)
    lines += ["GRADER", "-" * 40, g.report()]
    (OUT / "failure_episode.txt").write_text(
        "FAILURE EPISODE — claude-haiku-4-5, variant=fridge_full, seed=0, "
        "backend=symbolic\n"
        "Deterministic REPLAY of the live 2026-08-04 episode: the action "
        "sequence below is\nverbatim from the API run (results/llm_traces.md); "
        "the seeded env regenerates the\nidentical observation stream. "
        "Failure mode on display: ACTING ON THE DEFAULT\nASSUMPTION — picks "
        "up the leftovers at t=1 before any inspection, discovers the\nfull "
        "shelf at t=3, pays 5 actions of backtracking. Grader isolates this "
        "in the\nparsimony bucket; inference and intervention stay clean.\n"
        + "=" * 78 + "\n\n" + "\n".join(lines) + "\n"
    )
    print("failure_episode.txt", g.total)

    # --- audit: teleport probe on the sim -----------------------------------
    backend = RoboCasaBackend()
    env = KitchenEnv(backend, make_scenario("nominal", seed=0))
    obs0 = env.observation()
    backend.move_object("leftovers", "fridge_shelf")  # bypasses the env
    g = grade(env.ep, backend)
    region = backend.object_region("leftovers")
    (OUT / "audit_episode.txt").write_text(
        "AUDIT EPISODE — teleport probe, variant=nominal, seed=0, "
        "backend=robocasa\n"
        "The sim is teleported into a PERFECT end state (leftovers on the "
        "fridge shelf,\nverified from geometry) with ZERO agent actions — "
        "the 'accidental success /\nfabricated success' cheat. A grader that "
        "trusts end state alone would award\nparsimony 25 + intervention 35 "
        "= 60. Ours must not.\n" + "=" * 78 + "\n\n"
        "INITIAL OBSERVATION (before teleport)\n" + "-" * 40 + f"\n{obs0}\n\n"
        "PROBE: backend.move_object('leftovers', 'fridge_shelf')  "
        "# direct sim write, no env action\n\n"
        f"GEOMETRY CHECK: backend.object_region('leftovers') -> "
        f"'{region}'\n(answered by point-in-fixture math on the object's "
        "MuJoCo pose — the fabricated\nstate is real as far as the sim is "
        "concerned)\n\n"
        "GRADER\n" + "-" * 40 + "\n" + g.report() + "\n\n"
        "VERDICT: total capped at 40 (guessing cap: no revealing inspection "
        "ever\noccurred), inference 0, parsimony withheld-then-capped. The "
        "grader does not\nfalse-fire on a perfect-looking end state it can't "
        "attribute to informed action.\n"
    )
    print("audit_episode.txt", g.total)


if __name__ == "__main__":
    main()
