#!/usr/bin/env python
"""Run one decision-layer episode.

    python run_episode.py --agent scripted                 # all three variants
    python run_episode.py --agent scripted --variant fridge_full --seed 7
    python run_episode.py --agent human                    # play it yourself
    python run_episode.py --agent llm --model claude-haiku-4-5-20251001
    python run_episode.py --backend robocasa --gif media/episode.gif
"""

from __future__ import annotations

import argparse
import sys

from kitchen_task.env import MAX_ACTIONS, KitchenEnv
from kitchen_task.grader import grade
from kitchen_task.task import VARIANTS, make_scenario, sample_variant


def make_backend(name: str):
    if name in ("auto", "robocasa"):
        try:
            from kitchen_task.backends.robocasa_backend import RoboCasaBackend

            return RoboCasaBackend()
        except Exception as e:  # noqa: BLE001
            if name == "robocasa":
                raise
            print(f"[backend] robocasa unavailable ({type(e).__name__}), using symbolic")
    from kitchen_task.backends.symbolic import SymbolicBackend

    return SymbolicBackend()


def make_agent(args):
    if args.agent == "scripted":
        from kitchen_task.agents import ScriptedExpert

        return ScriptedExpert()
    if args.agent == "human":
        from kitchen_task.agents import HumanAgent

        return HumanAgent()
    if args.agent == "llm":
        from kitchen_task.agents import LLMAgent

        return LLMAgent(model=args.model)
    raise SystemExit(f"unknown agent {args.agent}")


def run_one(variant: str, seed: int, args) -> float:
    backend = make_backend(args.backend)
    scenario = make_scenario(variant, seed)
    env = KitchenEnv(backend, scenario)
    agent = make_agent(args)

    frames = []

    def snap():
        if args.gif:
            f = backend.render()
            if f is not None:
                frames.append(f)

    print(f"\n=== variant={variant} seed={seed} backend={backend.name} agent={args.agent} ===")
    obs = env.observation()
    snap()
    for _ in range(MAX_ACTIONS):
        action = agent(obs)
        obs, over = env.step(action)
        ev = env.ep.events[-1]
        print(f"  [{ev.t:2d}] {ev.raw:45s} -> {ev.detail}")
        snap()
        if over:
            break

    g = grade(env.ep, backend)
    print(g.report())

    if args.gif and frames:
        import imageio.v3 as iio

        iio.imwrite(args.gif, frames, duration=1200, loop=0)
        print(f"  wrote {args.gif} ({len(frames)} frames)")
    return g.total


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--agent", default="scripted", choices=["scripted", "human", "llm"])
    p.add_argument("--backend", default="auto", choices=["auto", "symbolic", "robocasa"])
    p.add_argument("--variant", default="all", choices=["all", "random", *VARIANTS])
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--model", default="claude-haiku-4-5-20251001")
    p.add_argument("--gif", default=None)
    args = p.parse_args()

    if args.variant == "all":
        variants = list(VARIANTS)
    elif args.variant == "random":
        variants = [sample_variant(args.seed)]
    else:
        variants = [args.variant]

    totals = [run_one(v, args.seed, args) for v in variants]
    if len(totals) > 1:
        print(f"\nmean total over {len(totals)} variants: {sum(totals)/len(totals):.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
