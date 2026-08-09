"""Taskset for the decision-layer kitchen task: the three hidden-state variants.

Rows carry the opaque task id and the seed only. A variant name is the answer
the agent must ``declare``, so it never appears in a client-visible task spec —
the mapping is held server-side in ``adapter_core.TASK_VARIANTS`` and pinned by
``deploy/hud/tests/test_decision_layer_hud_parity.py``.

    hud eval tasks.py claude --all
    hud sync tasks decision-layer-kitchen-v0.1
"""

from __future__ import annotations

from adapter_core import DEFAULT_SEED, TASK_VARIANTS
from env import put_away

tasks = [
    put_away(task_id=task_id, seed=DEFAULT_SEED).model_copy(
        update={"slug": task_id, "columns": {"seed": DEFAULT_SEED}}
    )
    for task_id in TASK_VARIANTS
]
