#!/usr/bin/env python
"""Exercise every RoboCasaBackend operation once, per variant, and run the
same teleport audit probes from tests/ against the real sim. Saves a frame
per variant to media/ as visual proof.

    .venv-sim/bin/python scripts/validate_sim_backend.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import imageio.v3 as iio

from kitchen_task.agents import ScriptedExpert
from kitchen_task.backends.robocasa_backend import RoboCasaBackend
from kitchen_task.env import MAX_ACTIONS, KitchenEnv
from kitchen_task.grader import grade
from kitchen_task.task import VARIANTS, make_scenario

MEDIA = Path(__file__).resolve().parents[1] / "media"
MEDIA.mkdir(exist_ok=True)


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")
    return bool(cond)


def main():
    ok = True
    for variant in VARIANTS:
        print(f"\n--- {variant} ---")
        t0 = time.time()
        backend = RoboCasaBackend()
        env = KitchenEnv(backend, make_scenario(variant, seed=0))
        print(f"  env built in {time.time()-t0:.1f}s")

        # doors start closed, open/close round-trips through sim joints
        ok &= check("fridge starts closed", not backend.door_open("fridge"))
        backend.set_door("fridge", True)
        ok &= check("fridge opens", backend.door_open("fridge"))
        backend.set_door("fridge", False)
        ok &= check("fridge closes", not backend.door_open("fridge"))

        # initial object regions match the scenario, answered from geometry
        for obj, want in make_scenario(variant, 0).object_regions.items():
            got = backend.object_region(obj)
            ok &= check(f"{obj} in {want}", got == want, f"(got {got})")

        # scripted expert end-to-end on the sim
        agent = ScriptedExpert()
        obs = env.observation()
        for _ in range(MAX_ACTIONS):
            obs, over = env.step(agent(obs))
            if over:
                break
        g = grade(env.ep, backend)
        ok &= check("expert scores 100 on sim", g.total == 100.0, f"(got {g.total})")
        print(g.report())

        frame = backend.render()
        ok &= check("render returns frame", frame is not None and frame.size > 0)
        iio.imwrite(MEDIA / f"validate_{variant}.png", frame)

    # teleport audit probe against the real sim
    print("\n--- sim teleport probe ---")
    backend = RoboCasaBackend()
    env = KitchenEnv(backend, make_scenario("nominal", seed=0))
    backend.move_object("leftovers", "fridge_shelf")  # bypass the action layer
    ok &= check("teleported obj reads as fridge_shelf (geometry)",
                backend.object_region("leftovers") == "fridge_shelf")
    g = grade(env.ep, backend)
    ok &= check("teleported accidental success capped <= 40", g.total <= 40.0,
                f"(got {g.total})")

    print("\nALL PASS" if ok else "\nFAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
