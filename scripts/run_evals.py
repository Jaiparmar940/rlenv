#!/usr/bin/env python
"""Run the no-start eval across model APIs; emit results table + transcripts.

Usage:
    python scripts/run_evals.py --models anthropic/claude-sonnet-5,openai/gpt-5 \
        --scenarios all
    python scripts/run_evals.py --mock          # offline pipeline check

Outputs (under --out, default results/):
    results.md                markdown table, deterministically ordered
    transcripts/*.md          full per-episode message transcripts
    logs/*.eval               raw Inspect logs

Real-model runs need provider API keys in the environment
(ANTHROPIC_API_KEY, OPENAI_API_KEY, XAI_API_KEY for grok/..., ...).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from dotenv import load_dotenv  # noqa: E402

# Provider API keys from repo-root .env (see .env.example). Real environment
# variables win over the file.
load_dotenv(REPO / ".env")

from inspect_ai import eval as inspect_eval  # noqa: E402
from inspect_ai.log import EvalLog  # noqa: E402
from inspect_ai.model import ModelOutput, get_model  # noqa: E402

from nostart.domain.scenarios import list_scenarios  # noqa: E402
from nostart.grader import ROOT_CAUSE_MAX  # noqa: E402
from nostart.task import no_start  # noqa: E402

SCORER_NAME = "nostart_grader"

# Scripted expert trajectories for --mock: proves the pipeline end to end
# without API keys. One eval per scenario so each script matches its sample.
MOCK_SCRIPTS: dict[str, list[tuple[str, dict]]] = {
    "easy_dead_battery": [
        ("measure_voltage", {"point_a": "battery_positive",
                             "point_b": "battery_negative",
                             "engine_state": "key_on"}),
        ("replace_part", {"component": "battery"}),
        ("attempt_start", {}),
        ("finish", {"answer": "battery dead"}),
    ],
    "medium_corroded_ground": [
        ("measure_voltage", {"point_a": "battery_negative",
                             "point_b": "engine_block",
                             "engine_state": "cranking"}),
        ("replace_part", {"component": "ground_strap"}),
        ("attempt_start", {}),
        ("finish", {"answer": "ground_strap corroded"}),
    ],
    "medium_ground_red_herring_battery": [
        ("measure_voltage", {"point_a": "battery_positive",
                             "point_b": "battery_negative",
                             "engine_state": "cranking"}),
        ("measure_voltage", {"point_a": "battery_negative",
                             "point_b": "engine_block",
                             "engine_state": "cranking"}),
        ("replace_part", {"component": "ground_strap"}),
        ("attempt_start", {}),
        ("finish", {"answer": "ground_strap corroded"}),
    ],
    # Expert path per the inline baseline in scenarios.py: probe across
    # several cranks (the fault only shows on some), confirm the CAN status
    # is intermittently degraded, replace the ECU node, verify the start.
    "hard_intermittent_ecu_can": [
        ("attempt_start", {}),
        ("attempt_start", {}),
        ("attempt_start", {}),
        ("attempt_start", {}),
        ("scan_dtcs", {}),
        ("scan_dtcs", {}),
        ("read_pid", {"pid": "can_status"}),
        ("read_pid", {"pid": "can_status"}),
        ("replace_part", {"component": "ecu_can_node"}),
        ("attempt_start", {}),
        ("finish", {"answer": "ecu_can_node intermittent"}),
    ],
    # Two real faults; neither repair alone starts the car, so the expert
    # buys both parts. Mirrors _EXPERT_STEPS in tests/test_hard_tier.py; the
    # finish phrasing is the one pinned there as full root-cause credit.
    "hard_compound_battery_and_ground": [
        ("attempt_start", {}),
        ("measure_voltage", {"point_a": "battery_positive",
                             "point_b": "battery_negative",
                             "engine_state": "key_off"}),
        ("measure_voltage", {"point_a": "battery_positive",
                             "point_b": "battery_negative",
                             "engine_state": "cranking"}),
        ("measure_voltage", {"point_a": "battery_negative",
                             "point_b": "engine_block",
                             "engine_state": "cranking"}),
        ("measure_voltage", {"point_a": "battery_positive",
                             "point_b": "starter_stud",
                             "engine_state": "cranking"}),
        ("replace_part", {"component": "ground_strap"}),
        ("replace_part", {"component": "battery"}),
        ("attempt_start", {}),
        ("finish", {"answer": "corroded ground strap, plus a weak battery"}),
    ],
}


def _sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def _msg_text(message) -> str:
    text = getattr(message, "text", "") or ""
    return text.strip()


def render_transcript(model_name: str, sample, variant: str) -> str:
    lines = [
        f"# {model_name} — {sample.id} (epoch {sample.epoch})",
        "",
        f"prompt-variant: **{variant}**",
        "",
    ]
    score = sample.scores.get(SCORER_NAME) if sample.scores else None
    if score is not None:
        lines += [
            f"**Score: {score.value}**",
            "```json",
            json.dumps(score.metadata, indent=1),
            "```",
            "",
            "---",
            "",
        ]
    # Number every message (1-based) so a transcript reader can see at a
    # glance how deep into the message_limit budget an episode ran — several
    # correct hard-tier episodes have died at the cap mid-verification.
    for msg_num, message in enumerate(sample.messages, start=1):
        role = message.role.upper()
        if role == "TOOL":
            fn = getattr(message, "function", None) or "tool"
            lines.append(f"### [{msg_num}] TOOL RESULT ({fn})")
        else:
            lines.append(f"### [{msg_num}] {role}")
        text = _msg_text(message)
        if text:
            lines += ["", text, ""]
        for call in getattr(message, "tool_calls", None) or []:
            args = json.dumps(call.arguments, sort_keys=True)
            lines += ["", f"→ `{call.function}({args})`", ""]
    return "\n".join(lines) + "\n"


def _score_num(value) -> float:
    """Bucket scores serialize as 'value/max' (older logs: bare floats)."""
    if isinstance(value, str):
        return float(value.split("/")[0])
    return float(value or 0.0)


def collect_rows(logs: list[EvalLog], variant: str) -> list[dict]:
    rows = []
    for log in logs:
        model_name = str(log.eval.model)
        for sample in log.samples or []:
            if getattr(sample, "error", None):
                print(f"NOTE: skipping errored sample {model_name}/"
                      f"{sample.id} e{sample.epoch}: {sample.error}")
                continue
            score = sample.scores.get(SCORER_NAME) if sample.scores else None
            meta = score.metadata if score and score.metadata else {}
            rows.append({
                "model": model_name,
                "scenario": str(sample.id),
                "epoch": sample.epoch,
                "variant": variant,
                "total": score.value if score else 0.0,
                "root": _score_num(meta.get("root_cause", 0.0)),
                "parts": _score_num(meta.get("parts_discipline", 0.0)),
                "cost": _score_num(meta.get("cost_efficiency", 0.0)),
                "root_ok": _score_num(meta.get("root_cause", 0.0))
                >= ROOT_CAUSE_MAX,
                "fix_verified": bool(meta.get("fix_verified", False)),
                # Discipline behavior the coached prompt dictated: at least
                # one diagnostic probe before the first replacement.
                "measured_first": not meta.get("guessing_penalty_applied",
                                               False),
                "guess_cap": meta.get("guessing_penalty_applied", False),
                "wrong_parts": ", ".join(meta.get("wrong_parts_replaced", [])),
                "diagnosis": (score.answer or "").replace("\n", " ")[:60]
                if score else "",
                "true": f"{meta.get('true_component', '?')} "
                        f"{meta.get('true_mode', '?')}",
                "sample": sample,
            })
    rows.sort(key=lambda r: (r["model"], r["scenario"], r["epoch"]))
    return rows


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _rate(flags: list[bool]) -> str:
    return f"{sum(flags)}/{len(flags)}" if flags else "0/0"


def write_results(rows: list[dict], out_dir: Path) -> Path:
    variants = sorted({r["variant"] for r in rows})
    lines = [
        "# no-start-env results",
        "",
        f"Generated {date.today().isoformat()} at commit `{_git_commit()}`."
        f" Prompt variant(s): {', '.join(variants)}.",
        "Score 0-100: root cause 60 / parts discipline 25 / cost efficiency 15"
        " (time-only vs expert baseline, zero at 2x, negative beyond). Wrong"
        " parts -8 each (also debited from total). -15 unless the root-cause"
        " part was replaced and a successful start verified it. Replacing"
        " before any measurement caps at 40.",
        "",
        "## Per model x scenario (aggregated over epochs)",
        "",
        "pass^k = every epoch earned full root-cause credit"
        " (component AND mode). root-ok = fraction of epochs with full"
        " root-cause credit. verified-fix / measured-first = fraction of"
        " epochs with the behavior.",
        "",
        "| model | scenario | k | mean | min | root | parts | cost | pass^k"
        " | root-ok | verified-fix | measured-first |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|",
    ]

    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        groups.setdefault((r["model"], r["scenario"]), []).append(r)

    for (model_name, scenario), episodes in sorted(groups.items()):
        totals = [float(e["total"]) for e in episodes]
        root_flags = [e["root_ok"] for e in episodes]
        lines.append(
            f"| {model_name} | {scenario} | {len(episodes)}"
            f" | {_mean(totals):.1f} | {min(totals):.1f}"
            f" | {_mean([e['root'] for e in episodes]):.0f}"
            f" | {_mean([e['parts'] for e in episodes]):.0f}"
            f" | {_mean([e['cost'] for e in episodes]):.1f}"
            f" | {'PASS' if all(root_flags) else 'fail'}"
            f" | {_rate(root_flags)}"
            f" | {_rate([e['fix_verified'] for e in episodes])}"
            f" | {_rate([e['measured_first'] for e in episodes])} |"
        )

    by_model: dict[str, list[float]] = {}
    for r in rows:
        by_model.setdefault(r["model"], []).append(float(r["total"]))
    model_means = {m: _mean(v) for m, v in by_model.items()}
    lines += ["", "## Summary", "", "| model | mean total |", "|---|---:|"]
    for model_name in sorted(model_means):
        lines.append(f"| {model_name} | {model_means[model_name]:.1f} |")
    if len(model_means) >= 2:
        spread = max(model_means.values()) - min(model_means.values())
        lines += ["", f"Best-worst model spread (separation): "
                      f"**{spread:.1f}** points."]
    lines += [
        "",
        "## Per-episode detail",
        "",
        "| model | scenario | epoch | variant | total | root | parts | cost"
        " | guess cap | wrong parts | diagnosis |",
        "|---|---|---:|---|---:|---:|---:|---:|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['model']} | {r['scenario']} | {r['epoch']} | {r['variant']}"
            f" | {r['total']:.1f}"
            f" | {r['root']:.0f} | {r['parts']:.0f} | {r['cost']:.2f}"
            f" | {'yes' if r['guess_cap'] else ''} | {r['wrong_parts']}"
            f" | {r['diagnosis']} |"
        )
    lines.append("")

    out = out_dir / "results.md"
    # Explicit utf-8: Windows defaults write_text to the locale code page
    # (cp1252), which cannot encode model prose or the em-dashes above.
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_transcripts(rows: list[dict], out_dir: Path) -> Path:
    tdir = out_dir / "transcripts"
    tdir.mkdir(parents=True, exist_ok=True)
    for r in rows:
        fname = (
            f"{_sanitize(r['model'])}__{_sanitize(r['scenario'])}"
            f"__{r['variant']}__e{r['epoch']}.md"
        )
        (tdir / fname).write_text(
            render_transcript(r["model"], r["sample"], r["variant"]),
            encoding="utf-8",
        )
    return tdir


def run_real(models: list[str], scenarios: str, epochs: int,
             message_limit: int, log_dir: Path, variant: str) -> list[EvalLog]:
    return inspect_eval(
        no_start(scenarios=scenarios, message_limit=message_limit,
                 prompt_variant=variant),
        model=models,
        epochs=epochs,
        log_dir=str(log_dir),
        display="rich",
    )


def run_mock(scenario_ids: list[str], message_limit: int,
             log_dir: Path, variant: str) -> list[EvalLog]:
    logs: list[EvalLog] = []
    for scenario_id in scenario_ids:
        script = MOCK_SCRIPTS[scenario_id]
        model = get_model(
            "mockllm/model",
            custom_outputs=[
                ModelOutput.for_tool_call("mockllm/model", fn, args)
                for fn, args in script
            ],
        )
        logs += inspect_eval(
            no_start(scenarios=scenario_id, message_limit=message_limit,
                     prompt_variant=variant),
            model=model,
            log_dir=str(log_dir),
            display="none",
        )
    return logs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models",
        help="Comma-separated Inspect model ids, e.g. "
             "anthropic/claude-sonnet-5,openai/gpt-5",
    )
    parser.add_argument("--scenarios", default="all",
                        help='"all" or comma-separated scenario ids')
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--message-limit", type=int, default=50)
    parser.add_argument("--out", default=str(REPO / "results"))
    parser.add_argument("--mock", action="store_true",
                        help="Offline pipeline check with a scripted expert")
    parser.add_argument(
        "--prompt-variant", choices=["uncoached", "coached"],
        default="uncoached",
        help="Agent system prompt: uncoached (default; no strategy, no "
             "grader rules) or coached (previous prompt, A/B condition)",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = out_dir / "logs"

    scenario_ids = (
        list_scenarios() if args.scenarios == "all"
        else [s.strip() for s in args.scenarios.split(",") if s.strip()]
    )

    if args.mock:
        logs = run_mock(scenario_ids, args.message_limit, log_dir,
                        args.prompt_variant)
    else:
        if not args.models:
            parser.error(
                "--models is required (or use --mock). Example: "
                "--models anthropic/claude-sonnet-5,openai/gpt-5"
            )
        logs = run_real(
            [m.strip() for m in args.models.split(",")],
            args.scenarios, args.epochs, args.message_limit, log_dir,
            args.prompt_variant,
        )

    failed = [log for log in logs if log.status != "success"]
    rows = collect_rows(logs, args.prompt_variant)
    results_path = write_results(rows, out_dir)
    tdir = write_transcripts(rows, out_dir)

    print(f"\nResults table: {results_path}")
    print(f"Transcripts:   {tdir}")
    if failed:
        print(f"WARNING: {len(failed)} eval run(s) did not succeed.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
