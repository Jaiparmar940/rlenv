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


ORACLE_NOTE = "oracle execution: actions set sim state directly - the arm never moves (by design)"


def _font(size):
    try:
        from PIL import ImageFont

        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
    except Exception:  # noqa: BLE001
        return None


def _caption(frame, text):
    """Burn a two-line caption strip: the action, and the standing oracle
    disclaimer. No-op if pillow is missing."""
    try:
        import numpy as np
        from PIL import Image, ImageDraw
    except ImportError:
        return frame
    img = Image.fromarray(frame)
    draw = ImageDraw.Draw(img)
    w, h = img.size
    draw.rectangle([0, h - 46, w, h], fill=(0, 0, 0))
    draw.text((8, h - 42), text[:95], fill=(255, 255, 255), font=_font(14))
    draw.text((8, h - 22), ORACLE_NOTE, fill=(160, 160, 160), font=_font(13))
    return np.asarray(img)


def _title_card(shape):
    """Opening frame stating what the demo is (and is not) showing."""
    try:
        import numpy as np
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    h, w = shape[:2]
    img = Image.new("RGB", (w, h), (12, 12, 12))
    draw = ImageDraw.Draw(img)
    lines = [
        ("decision-layer eval: put the leftovers away", 24, (255, 255, 255)),
        ("", 16, None),
        ("The agent under test is a reasoning model choosing", 17, (220, 220, 220)),
        ("discrete actions. Hidden state forces inspect -> infer", 17, (220, 220, 220)),
        ("-> intervene; a grader scores each separately.", 17, (220, 220, 220)),
        ("", 16, None),
        ("Execution is ORACLE by design: valid actions set", 17, (255, 210, 130)),
        ("simulator state directly. The robot arm is scenery,", 17, (255, 210, 130)),
        ("not the system being evaluated - it never actuates.", 17, (255, 210, 130)),
    ]
    y = h // 2 - 110
    for text, size, color in lines:
        if color:
            draw.text((40, y), text, fill=color, font=_font(size))
        y += size + 8
    return np.asarray(img)


def run_one(variant: str, seed: int, args, frames=None) -> float:
    backend = make_backend(args.backend)
    scenario = make_scenario(variant, seed)
    env = KitchenEnv(backend, scenario)
    agent = make_agent(args)

    def snap(label):
        if args.gif and frames is not None:
            f = backend.render()
            if f is not None:
                frames.append(_caption(f, f"[{variant}] {label}"))

    print(f"\n=== variant={variant} seed={seed} backend={backend.name} agent={args.agent} ===")
    obs = env.observation()
    snap("initial state")
    for _ in range(MAX_ACTIONS):
        action = agent(obs)
        obs, over = env.step(action)
        ev = env.ep.events[-1]
        print(f"  [{ev.t:2d}] {ev.raw:45s} -> {ev.detail}")
        snap(f"{ev.raw} -> {ev.detail}")
        if over:
            break

    g = grade(env.ep, backend)
    print(g.report())
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

    frames: list = []
    totals = [run_one(v, args.seed, args, frames) for v in variants]
    if len(totals) > 1:
        print(f"\nmean total over {len(totals)} variants: {sum(totals)/len(totals):.1f}")
    if args.gif and frames:
        import imageio.v3 as iio

        card = _title_card(frames[0].shape)
        if card is not None:
            frames = [card, card] + frames  # ~4s up front
        iio.imwrite(args.gif, frames, duration=2000, loop=0)
        print(f"wrote {args.gif} ({len(frames)} frames, ~{2*len(frames)}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
