"""Phase 3: haiku x 5 epochs on red-herring + compound through BOTH pipelines.

Decision rule (from the parity brief): if the two columns' distributions
overlap the published benchmark's pattern for these cells (red-herring
0-for-5, compound low), parity holds; if ORS is systematically higher,
back to transcript capture.

Budget: 20 haiku episodes total.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO / ".env")

from validate_openreward import (  # noqa: E402
    MESSAGE_LIMIT,
    SCENARIO_TASKS,
    _get_env,
    ensure_server,
    ors_model_episode,
)

SCENARIOS = ["medium_ground_red_herring_battery", "hard_compound_battery_and_ground"]
EPOCHS = 5
MODEL_INSPECT = "anthropic/claude-haiku-4-5"
MODEL_SDK = "claude-haiku-4-5"
OUT = REPO / "results" / "parity_diag"


def root_ok(metadata: dict | None) -> bool:
    """Full root-cause credit (the published root-ok metric)."""
    if not metadata:
        return False
    value = str(metadata.get("root_cause", ""))
    return value.split("/")[0] in ("60", "60.0")


def run_inspect() -> dict[str, list[dict]]:
    from inspect_ai import eval as inspect_eval
    from inspect_ai.log import read_eval_log

    from nostart.task import no_start

    log_dir = OUT / "phase3_inspect_logs"
    existing = sorted(log_dir.glob("*.eval")) if log_dir.exists() else []
    if existing:
        print(f"  [inspect] reusing existing log {existing[-1].name}")
        location = str(existing[-1])
    else:
        logs = inspect_eval(
            no_start(scenarios=",".join(SCENARIOS),
                     message_limit=MESSAGE_LIMIT,
                     prompt_variant="uncoached"),
            model=MODEL_INSPECT,
            epochs=EPOCHS,
            log_dir=str(log_dir),
            display="none",
        )
        location = logs[0].location
    out: dict[str, list[dict]] = {s: [] for s in SCENARIOS}
    log = read_eval_log(location)
    for sample in log.samples:
        score = list(sample.scores.values())[0]
        out[str(sample.id)].append({
            "score": float(score.value),
            "root_ok": root_ok(score.metadata),
        })
    return out


def run_ors(port: int = 8080) -> dict[str, list[dict]]:
    ensure_server(port)
    env = _get_env(port)
    tasks = {t.task_spec["task_id"]: t for t in env.list_tasks(split="test")}
    out: dict[str, list[dict]] = {s: [] for s in SCENARIOS}
    for scenario in SCENARIOS:
        task = tasks[SCENARIO_TASKS[scenario]]
        for epoch in range(EPOCHS):
            episode = ors_model_episode(env, task, MODEL_SDK)
            out[scenario].append({
                "score": episode["score"],
                "root_ok": root_ok(episode.get("metadata")),
                "via": episode.get("via"),
            })
            print(f"  [ors] {scenario} epoch {epoch + 1}: "
                  f"{episode['score']:.1f} ({episode.get('via')})")
    return out


def main() -> None:
    print(f"Budget: {len(SCENARIOS)} scenarios x {EPOCHS} epochs x 2 pipelines "
          f"= {len(SCENARIOS) * EPOCHS * 2} haiku episodes (~50 msgs max each; "
          "rough cost low single-digit dollars). Proceeding.")
    print("\n[1/2] Inspect pipeline ...")
    ins = run_inspect()
    print("[2/2] ORS pipeline ...")
    ors = run_ors()

    (OUT / "phase3_results.json").write_text(
        json.dumps({"inspect": ins, "ors": ors}, indent=1), encoding="utf-8")

    print("\n=== Phase 3 results (haiku, 5 epochs) ===")
    for scenario in SCENARIOS:
        iscores = [e["score"] for e in ins[scenario]]
        oscores = [e["score"] for e in ors[scenario]]
        iroot = sum(e["root_ok"] for e in ins[scenario])
        oroot = sum(e["root_ok"] for e in ors[scenario])
        print(f"\n{scenario}")
        print(f"  inspect: {[f'{s:.1f}' for s in iscores]}  "
              f"mean {sum(iscores) / len(iscores):.1f}  root-ok {iroot}/5")
        print(f"  ors:     {[f'{s:.1f}' for s in oscores]}  "
              f"mean {sum(oscores) / len(oscores):.1f}  root-ok {oroot}/5")


if __name__ == "__main__":
    main()
