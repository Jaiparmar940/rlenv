"""Managed-environment adapter core for the decision-layer kitchen task.

Wraps ``kitchen_task`` unchanged: ``make_scenario`` / ``KitchenEnv`` /
``grade`` are imported, never reimplemented. ``env.py`` binds this module onto
the HUD ``Environment`` object and a FastMCP tool server.

Imports nothing from hud or fastmcp, so the parity tests run on a bare
interpreter — the same zero-dependency path the task itself advertises.

Backend
-------
The managed environment runs the **symbolic** backend: a pure-Python kitchen
state model with no simulator. That is the primary product for v0.1. The
RoboCasa/MuJoCo backend is the *validation* substrate (~10 GB of kitchen
assets, robosuite master from source); it is shipped as evidence, not as a
production dependency. Both backends answer the same ``Backend`` protocol and
the grader queries only that protocol, which is what makes the substitution
sound — see ``decision-layer/handoff/RESULTS.md`` for the sim run in which the
scripted expert scores 100.0 on all three variants on *both* backends.

Parity contract with the published implementation
-------------------------------------------------
* **Action grammar** — one tool, ``act(action)``, taking the same free-text
  action line ``KitchenEnv.step`` has always taken. No new verbs, no
  structured arguments; invalid actions still cost an action and return the
  same parse-failure text.
* **Observations** — produced by ``KitchenEnv.observation`` verbatim, including
  the reveal rule (an interior is visible only while its door is open).
* **Prompt** — the LLM system framing from ``kitchen_task.agents.LLMAgent``
  followed by the initial observation, which is exactly what the published
  live traces sent.
* **Grading** — ``kitchen_task.grader.grade(episode, backend)``, queried
  against backend state. Reward is ``total / 100``.
* **Oracle execution is part of the task, not a shortcut.** A valid primitive
  is realized by setting substrate state directly; the decision sequence
  (inspect -> infer -> intervene) is the system under evaluation. This is
  stated in the prompt-facing docs, the listing card and the environment
  description.
* **Leakage** — a variant name *is* the answer the agent must ``declare``, so
  tasks are addressed by opaque ids (``dlk-01``..``dlk-03``).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _ensure_kitchen_task_importable() -> None:
    """Put the real ``kitchen_task`` package on the path: installed, else the
    staged ``vendor/`` copy, else the checkout's decision-layer directory."""
    try:
        import kitchen_task  # noqa: F401

        return
    except ImportError:
        pass

    here = Path(__file__).resolve().parent
    candidates = [here / "vendor"]
    candidates += [parent / "decision-layer" for parent in here.parents]
    for candidate in candidates:
        if (candidate / "kitchen_task" / "__init__.py").is_file():
            sys.path.insert(0, str(candidate))
            return
    raise ImportError(
        "Could not locate the 'kitchen_task' package. Run deploy/hud/stage.py "
        "to populate vendor/, or run from the rlenv checkout."
    )


_ensure_kitchen_task_importable()

from kitchen_task.agents import LLMAgent  # noqa: E402
from kitchen_task.backends.symbolic import SymbolicBackend  # noqa: E402
from kitchen_task.env import MAX_ACTIONS, KitchenEnv  # noqa: E402
from kitchen_task.grader import Grade, grade  # noqa: E402
from kitchen_task.task import VARIANTS, make_scenario  # noqa: E402

ENV_NAME = "decision-layer-kitchen"
ENV_VERSION = "0.1.0"

DEFAULT_SEED = 0

# Opaque task ids -> (variant, seed). The variant name is the hidden state the
# agent has to infer and declare, so it stays server-side. Order is the
# published variant order in decision-layer/handoff/RESULTS.md.
TASK_VARIANTS: dict[str, str] = {
    "dlk-01": "nominal",
    "dlk-02": "fridge_full",
    "dlk-03": "container_missing",
}

# The system framing the published live traces used (kitchen_task/agents.py).
SYSTEM_FRAMING = LLMAgent.SYSTEM

ACT_TOOL_NAME = "act"
ACT_TOOL_DESCRIPTION = (
    "Perform exactly one kitchen action and return the resulting observation. "
    "Actions: open <fridge|microwave|cabinet> | close <fridge|microwave|cabinet> "
    "| pick <object> | place <object> <counter|fridge|microwave|cabinet> | "
    "discard <object> | declare <short phrase> | done. Every action counts "
    "toward the action budget, including ones that fail to parse."
)
ACT_TOOL_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "description": "One action line, e.g. 'open fridge'.",
        }
    },
    "required": ["action"],
    "additionalProperties": False,
}

EPISODE_OVER_TEXT = (
    "The episode is over; no further actions are accepted. "
    "Submit your final answer."
)


@dataclass(frozen=True)
class ToolResult:
    text: str
    episode_over: bool = False


@dataclass(frozen=True)
class GradeResult:
    reward: float
    grade: Grade

    @property
    def metadata(self) -> dict[str, Any]:
        g = self.grade
        return {
            "inference": g.inference,
            "parsimony": g.parsimony,
            "intervention": g.intervention,
            "cap": g.cap,
            "total": g.total,
            "score_0_100": g.total,
            "notes": list(g.notes),
        }

    @property
    def explanation(self) -> str:
        return self.grade.report()


def list_tasks() -> list[dict[str, Any]]:
    """Client-visible task specs: opaque id + seed. No variant names."""
    return [
        {"task_id": task_id, "seed": DEFAULT_SEED} for task_id in TASK_VARIANTS
    ]


class KitchenSession:
    """One episode on the symbolic backend."""

    def __init__(self, task_id: str, seed: int = DEFAULT_SEED) -> None:
        variant = TASK_VARIANTS.get(task_id)
        if variant is None:
            raise ValueError(
                f"Unknown task_id {task_id!r}. Valid: {sorted(TASK_VARIANTS)}"
            )
        assert variant in VARIANTS, variant
        self.task_id = task_id
        self.seed = seed
        self.backend = SymbolicBackend()
        self.env = KitchenEnv(self.backend, make_scenario(variant, seed))
        self.over = False

    # --- prompt -------------------------------------------------------------

    def prompt_blocks(self) -> tuple[str, str]:
        """(system framing, initial observation) — what the published live
        traces sent, in that order."""
        return (SYSTEM_FRAMING, self.env.observation())

    def prompt(self) -> str:
        return "\n\n".join(self.prompt_blocks())

    # --- the single action tool --------------------------------------------

    def act(self, action: str) -> ToolResult:
        if self.over:
            return ToolResult(EPISODE_OVER_TEXT, episode_over=True)
        observation, over = self.env.step(action)
        self.over = over
        return ToolResult(observation, episode_over=over)

    def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if name != ACT_TOOL_NAME:
            raise ValueError(f"Unknown tool {name!r}")
        return self.act(**arguments)

    # --- grading ------------------------------------------------------------

    @property
    def actions_used(self) -> int:
        return len(self.env.ep.events)

    @property
    def actions_remaining(self) -> int:
        return MAX_ACTIONS - self.actions_used

    def grade(self) -> GradeResult:
        """Grade from backend state, never from agent claims. The agent's final
        message is deliberately not an input: findings are declared in-episode
        with the `declare` action, and end state is read off the substrate."""
        result = grade(self.env.ep, self.backend)
        return GradeResult(reward=result.total / 100.0, grade=result)
