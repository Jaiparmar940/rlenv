"""Taskset for no-start-env: the five published v0.1 scenarios.

Rows carry the opaque task id only. A scenario id names its own fault
("easy_dead_battery"), so it never appears in a client-visible task spec —
the mapping is held server-side in ``adapter_core.TASK_SCENARIOS`` and pinned
by ``deploy/hud/tests/test_no_start_hud_parity.py``.

    hud eval tasks.py claude --all
    hud sync tasks no-start-env-v0.1
"""

from __future__ import annotations

from adapter_core import TASK_TIERS
from env import diagnose

tasks = [
    diagnose(task_id=task_id).model_copy(
        update={"slug": task_id, "columns": {"tier": tier}}
    )
    for task_id, tier in TASK_TIERS.items()
]
