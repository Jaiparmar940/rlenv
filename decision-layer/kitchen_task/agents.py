"""Agents. The interface any LLM drops into:

    action_string = agent(observation_string)

The scripted expert is a REACTIVE policy: it reads only the observation text
(the same channel an LLM gets) and never touches ground truth. It exists to
prove the task is solvable from the observation channel alone, and its action
counts are the parsimony baselines (pinned in task.py, verified by tests).
"""

from __future__ import annotations

import os
import re
from collections import deque


class ScriptedExpert:
    """Inspect -> declare -> intervene, reading observations like a human."""

    def __init__(self):
        self.queue: deque[str] = deque()
        self.phase = "start"

    def __call__(self, obs: str) -> str:
        if self.queue:
            return self.queue.popleft()

        counter_has_leftovers = re.search(r"^Counter: .*leftovers", obs, re.M) is not None
        fridge_open = re.search(r"^Fridge: open", obs, re.M) is not None
        microwave_open = re.search(r"^Microwave: open", obs, re.M) is not None

        if self.phase == "start":
            if counter_has_leftovers:
                self.phase = "at_fridge"
                return "open fridge"
            self.phase = "check_microwave"  # counter empty + blinking clock cue
            return "open microwave"

        if self.phase == "at_fridge" and fridge_open:
            m = re.search(r"\((\d)/(\d) shelf slots used\)", obs)
            used, cap = int(m.group(1)), int(m.group(2))
            if used < cap:
                self.queue.extend([
                    "pick leftovers", "place leftovers fridge", "close fridge", "done",
                ])
                self.phase = "finishing"
                return "declare fridge has space, everything nominal"
            self.queue.extend([
                "pick milk", "discard milk",
                "pick leftovers", "place leftovers fridge", "close fridge", "done",
            ])
            self.phase = "finishing"
            return "declare fridge shelf is full, milk is expired"

        if self.phase == "check_microwave" and microwave_open:
            self.queue.extend([
                "pick leftovers", "close microwave",
                "open fridge", "place leftovers fridge", "close fridge", "done",
            ])
            self.phase = "finishing"
            return "declare leftovers were left in the microwave, not on the counter"

        return "done"  # unreachable in designed variants; fail safe


class LLMAgent:
    """Anthropic-API agent. Drop-in: obs string in, action string out.

    Any other provider works by replacing this class with any callable
    str -> str; nothing else in the stack changes.
    """

    SYSTEM = (
        "You are controlling a kitchen robot through discrete actions. "
        "Each turn you receive an observation and must reply with EXACTLY ONE "
        "action line and nothing else. Think before acting, but output only "
        "the action. Hidden state exists: inspect before you commit. "
        "Unnecessary actions are penalized."
    )

    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        import anthropic  # lazy: optional dependency

        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = model
        self.history: list[dict] = []

    def __call__(self, obs: str) -> str:
        self.history.append({"role": "user", "content": obs})
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=200,
            system=self.SYSTEM,
            messages=self.history,
        )
        action = resp.content[0].text.strip().splitlines()[-1].strip("` ")
        self.history.append({"role": "assistant", "content": action})
        return action


class HumanAgent:
    """Interactive play at the terminal — the webapp.py of this task."""

    def __call__(self, obs: str) -> str:
        print("\n" + obs + "\n")
        return input("action> ")
