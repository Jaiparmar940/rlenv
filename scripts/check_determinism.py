#!/usr/bin/env python
"""Determinism check: same scenario + same action sequence => same observations.

The ENVIRONMENT (not the model) must be reproducible: a lab re-running an
episode with the same seed has to get byte-identical observations, or scores
are not comparable across runs.

For each scenario this builds the world TWICE from scratch, replays one fixed
action sequence against each, serializes the full observation stream (tool
returns, raised errors, and the end-of-episode cost/action snapshot), and
diffs the two streams. Any difference is a failure.

The sequence deliberately exercises every stochastic surface in World:
  - seeded meter noise on measure_voltage / read_pid   (World._noise_band)
  - the 40% spot-the-corroded-strap roll in visual_inspect
  - the intermittency roll in scan_dtcs / measure_voltage / attempt_start
  - RNG-order coupling: all of the above draw from ONE Random(scenario.seed),
    so a reordered or extra draw shows up as a diff downstream
and every state transition:
  - replace_part clearing a fault (and clearing a red-herring override)
  - attempt_start setting engine-running
  - the 'running' engine_state gate (raises unless actually running)

Exit 0 = deterministic. Stdlib only.

    python scripts/check_determinism.py
"""

from __future__ import annotations

import difflib
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nostart.domain.scenarios import SCENARIOS  # noqa: E402
from nostart.tools import ToolSession  # noqa: E402

# (tool_name, kwargs) -- one fixed script, replayed identically against every world.
ACTIONS: list[tuple[str, dict]] = [
    ("scan_dtcs", {}),
    ("read_pid", {"pid": "battery_voltage"}),
    ("read_pid", {"pid": "alt_output_v"}),
    ("read_pid", {"pid": "rpm"}),
    ("read_pid", {"pid": "can_status"}),
    ("measure_voltage", {"point_a": "battery_positive", "point_b": "battery_negative",
                         "engine_state": "key_off"}),
    ("measure_voltage", {"point_a": "battery_positive", "point_b": "battery_negative",
                         "engine_state": "key_on"}),
    ("measure_voltage", {"point_a": "battery_positive", "point_b": "battery_negative",
                         "engine_state": "cranking"}),
    ("measure_voltage", {"point_a": "battery_negative", "point_b": "engine_block",
                         "engine_state": "cranking"}),
    ("measure_voltage", {"point_a": "battery_positive", "point_b": "starter_stud",
                         "engine_state": "cranking"}),
    # 'running' before any successful start: must raise, identically both times.
    ("measure_voltage", {"point_a": "alt_output", "point_b": "battery_negative",
                         "engine_state": "running"}),
    ("visual_inspect", {"area": "battery"}),
    ("visual_inspect", {"area": "ground_strap"}),
    ("attempt_start", {}),
    # Repair + verify. Replacing the battery fixes easy_dead_battery (-> starts,
    # engine running) and clears the red-herring override in the herring
    # scenario without fixing it (-> slow_crank). Both paths are deterministic.
    ("replace_part", {"component": "battery"}),
    ("attempt_start", {}),
    ("read_pid", {"pid": "rpm"}),
    ("measure_voltage", {"point_a": "alt_output", "point_b": "battery_negative",
                         "engine_state": "running"}),
    ("replace_part", {"component": "ground_strap"}),
    ("attempt_start", {}),
    ("read_pid", {"pid": "alt_output_v"}),
    ("finish", {"diagnosis": "determinism probe"}),
]


def _jsonable(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def replay(scenario_id: str) -> str:
    """Run ACTIONS against a fresh world; return the serialized observation stream."""
    session = ToolSession(scenario_id)
    stream = []
    for i, (tool, kwargs) in enumerate(ACTIONS):
        entry: dict[str, object] = {"step": i, "tool": tool, "args": kwargs}
        try:
            entry["result"] = _jsonable(getattr(session, tool)(**kwargs))
        except Exception as exc:  # errors must be deterministic too
            entry["error"] = f"{type(exc).__name__}: {exc}"
        stream.append(entry)
    stream.append({"step": "final", "snapshot": session.get_status().model_dump()})
    return json.dumps(stream, indent=1, sort_keys=True, default=str)


def main() -> int:
    failures = []
    for scenario_id in SCENARIOS:
        run_a = replay(scenario_id)
        run_b = replay(scenario_id)
        if run_a == run_b:
            digest = hashlib.sha256(run_a.encode()).hexdigest()[:16]
            lines = len(run_a.splitlines())
            print(f"  [PASS] {scenario_id}: {len(ACTIONS)} actions, "
                  f"{lines}-line observation stream identical across two builds")
            print(f"         stream sha256[:16] = {digest}  "
                  f"(stable across processes/runs)")
        else:
            failures.append(scenario_id)
            print(f"  [FAIL] {scenario_id}: observation streams differ")
            diff = difflib.unified_diff(
                run_a.splitlines(), run_b.splitlines(),
                fromfile="run_a", tofile="run_b", lineterm="",
            )
            for line in diff:
                print("    " + line)

    print()
    print("=" * 60)
    if failures:
        print(f"DETERMINISM FAILED: {', '.join(failures)}")
        return 1
    print(f"DETERMINISM OK - {len(SCENARIOS)} scenarios reproduce exactly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
