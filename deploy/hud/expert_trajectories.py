"""The documented expert trajectories, read from the repository's own runner.

``scripts/run_evals.py`` holds ``MOCK_SCRIPTS`` — the expert action sequences
for all five no-start scenarios, each derived from the inline expert baseline in
``scenarios.py`` and pinned by the project's tests. Parity work must replay
*those* sequences, not a copy of them, or the parity claim decays the first time
an expert path is revised.

The module is read with ``ast``, not imported: importing it pulls in inspect-ai
and loads ``.env`` (provider API keys), neither of which a packaging check
should require or touch.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
RUN_EVALS = REPO / "scripts" / "run_evals.py"

Trajectory = list[tuple[str, dict]]


def no_start_expert_trajectories(source: Path | None = None) -> dict[str, Trajectory]:
    """``{scenario_id: [(tool_name, arguments), ...]}`` from run_evals.py."""
    path = source or RUN_EVALS
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        targets = (
            [node.target] if isinstance(node, ast.AnnAssign) else getattr(node, "targets", [])
        )
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        if "MOCK_SCRIPTS" in names and node.value is not None:
            scripts = ast.literal_eval(node.value)
            return {
                scenario: [(name, dict(args)) for name, args in steps]
                for scenario, steps in scripts.items()
            }
    raise LookupError(f"MOCK_SCRIPTS not found in {path}")
