"""Capture the COMPLETE wire-level model context for one episode of a scenario
through each pipeline (Inspect basic_agent vs the ORS validation loop).

Inspect side: real haiku episode via inspect_eval; the raw provider request
payloads (what went over the wire to the Anthropic API) are read from the
eval log's ModelEvent.call records. ORS side: the validation loop's exact
client.messages.create kwargs, dumped before each call (the SDK serializes
these 1:1 into the request body).

Usage:
    .venv/Scripts/python.exe results/parity_diag/capture.py medium_ground_red_herring_battery
    .venv/Scripts/python.exe results/parity_diag/capture.py hard_compound_battery_and_ground
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

OUT = REPO / "results" / "parity_diag"
MODEL_INSPECT = "anthropic/claude-haiku-4-5"
MODEL_SDK = "claude-haiku-4-5"
MESSAGE_LIMIT = 50


def capture_inspect(scenario: str, reuse_existing: bool = True) -> dict:
    from inspect_ai import eval as inspect_eval
    from inspect_ai.log import read_eval_log

    from nostart.task import no_start

    log_dir = OUT / f"inspect_logs_{scenario}"
    existing = sorted(log_dir.glob("*.eval")) if log_dir.exists() else []
    if reuse_existing and existing:
        location = str(existing[-1])
        print(f"[inspect] re-extracting from existing log {existing[-1].name}")
    else:
        logs = inspect_eval(
            no_start(scenarios=scenario, message_limit=MESSAGE_LIMIT,
                     prompt_variant="uncoached"),
            model=MODEL_INSPECT,
            epochs=1,
            log_dir=str(log_dir),
            display="none",
        )
        location = logs[0].location
    log = read_eval_log(location, resolve_attachments=True)
    sample = log.samples[0]

    calls = []
    for event in sample.events:
        if getattr(event, "event", None) == "model" and event.call is not None:
            calls.append({
                "request": event.call.request,
                "response_stop": getattr(event.output, "stop_reason", None),
            })

    score = list(sample.scores.values())[0]
    return {
        "pipeline": "inspect",
        "scenario": scenario,
        "n_api_calls": len(calls),
        "calls": calls,
        "final_completion": sample.output.completion,
        "score": float(score.value),
        "score_metadata": score.metadata,
        "n_messages_final": len(sample.messages),
    }


def capture_ors(scenario: str, port: int = 8080) -> dict:
    import anthropic

    from validate_openreward import SCENARIO_TASKS, ensure_server, _get_env

    ensure_server(port)
    env = _get_env(port)
    task_id = SCENARIO_TASKS[scenario]
    task = next(t for t in env.list_tasks(split="test")
                if t.task_spec["task_id"] == task_id)

    client = anthropic.Anthropic()
    tools = env.list_tools(format="anthropic")
    calls: list[dict] = []
    record: dict = {"pipeline": "ors", "scenario": scenario,
                    "task_spec_client_visible": dict(task.task_spec)}

    with env.session(task=task) as session:
        blocks = session.get_prompt()
        system_prompt = blocks[0].text
        messages: list[dict] = [{"role": "user", "content": blocks[1].text}]
        last_text = ""
        finished_via = None
        reward = None
        while len(messages) < MESSAGE_LIMIT:
            payload = {
                "model": MODEL_SDK,
                "max_tokens": 2048,
                "system": system_prompt,
                "tools": tools,
                "messages": messages,
            }
            calls.append({"request": json.loads(json.dumps(
                payload, default=lambda o: getattr(o, "__dict__", str(o))))})
            response = client.messages.create(**payload)
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            texts = [b.text for b in response.content if b.type == "text"]
            if texts:
                last_text = texts[-1]
            if not tool_uses:
                finished_via = "plain_message_break"
                break
            messages.append({"role": "assistant", "content": [
                b.model_dump() for b in response.content]})
            results = []
            done = False
            for call in tool_uses:
                result = session.call_tool(call.name, dict(call.input))
                output = getattr(result, "output", result)
                if getattr(output, "finished", False):
                    finished_via = f"tool:{call.name}"
                    reward = output.reward
                    record["final_metadata"] = output.metadata
                    record["finish_args"] = dict(call.input)
                    done = True
                    break
                if hasattr(output, "blocks"):
                    text_payload = "\n".join(b.text for b in output.blocks)
                else:
                    text_payload = f"Error: {getattr(output, 'error', output)}"
                results.append({"type": "tool_result",
                                "tool_use_id": call.id,
                                "content": text_payload})
            if done:
                break
            messages.append({"role": "user", "content": results})
        if reward is None:
            result = session.call_tool("grade_final_message",
                                       {"message": last_text})
            output = getattr(result, "output", result)
            reward = output.reward
            record["final_metadata"] = output.metadata
            record["terminal_fallback_message"] = last_text
            finished_via = (finished_via or "message_cap") + "->terminal_fallback"

    record.update({
        "n_api_calls": len(calls),
        "calls": calls,
        "score": (reward or 0.0) * 100.0,
        "finished_via": finished_via,
        "n_messages_final": len(messages),
    })
    return record


def main() -> None:
    scenario = sys.argv[1]
    only = sys.argv[2] if len(sys.argv) > 2 else None
    for name, fn in (("inspect", capture_inspect), ("ors", capture_ors)):
        if only and name != only:
            continue
        rec = fn(scenario)
        path = OUT / f"{scenario}__{name}.json"
        path.write_text(json.dumps(rec, indent=1, default=str),
                        encoding="utf-8")
        print(f"[{name}] score={rec['score']:.1f} "
              f"api_calls={rec['n_api_calls']} -> {path.name}")


if __name__ == "__main__":
    main()
