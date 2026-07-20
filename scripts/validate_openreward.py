"""Validate the ORS (OpenReward) serving against direct Inspect runs.

Two parts:

Part A (exact, no API keys): replay the deterministic expert scripts
(run_evals.MOCK_SCRIPTS) through (1) the live ORS HTTP interface and (2) the
direct Inspect mock pipeline. The environment is seeded, so the two scores
must match EXACTLY — this is the interface-equivalence proof.

Part B (--model, needs a key): run one real model through both interfaces,
1 epoch per scenario, side by side. Model sampling is stochastic, so Part B
scores are comparable, not identical; Part A carries the exactness claim.

The script starts the ORS server itself (or reuses one already listening on
--port) and never writes into results/.

Usage:
    .venv/Scripts/python.exe scripts/validate_openreward.py
    .venv/Scripts/python.exe scripts/validate_openreward.py \
        --model anthropic/claude-haiku-4-5
"""

from __future__ import annotations

import argparse
import atexit
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO / ".env")

from run_evals import MOCK_SCRIPTS, run_mock, run_real  # noqa: E402

from nostart.openreward.env import TASK_SCENARIOS  # noqa: E402

BASE_URL_TEMPLATE = "http://localhost:{port}"
SCENARIO_TASKS = {v: k for k, v in TASK_SCENARIOS.items()}
MESSAGE_LIMIT = 50  # published-run cap; mirrored in the ORS agent loop


def _port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("localhost", port)) == 0


def ensure_server(port: int) -> None:
    if _port_open(port):
        print(f"[server] reusing ORS server on :{port}")
        return
    proc = subprocess.Popen(
        [sys.executable, "-m", "nostart.openreward.server"],
        cwd=REPO,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    atexit.register(proc.kill)
    for _ in range(60):
        if _port_open(port):
            print(f"[server] started ORS server on :{port} (pid {proc.pid})")
            return
        time.sleep(0.5)
    raise RuntimeError("ORS server did not come up on port 8080")


def _get_env(port: int):
    from openreward import OpenReward

    client = OpenReward(api_key="local-dev")
    return client.environments.get(
        name="no-start-env", base_url=BASE_URL_TEMPLATE.format(port=port)
    )


def _inspect_scores(logs) -> dict[str, float]:
    """scenario_id -> score, from Inspect eval logs (1 epoch)."""
    out: dict[str, float] = {}
    for log in logs:
        for sample in log.samples or []:
            score = list(sample.scores.values())[0]
            out[str(sample.id)] = float(score.value)
    return out


# --- Part A: deterministic expert replay ------------------------------------


def ors_replay_score(env, scenario_id: str) -> float:
    """Run the scenario's expert script through a live ORS session."""
    task_id = SCENARIO_TASKS[scenario_id]
    tasks = env.list_tasks(split="test")
    task = next(t for t in tasks if t.task_spec["task_id"] == task_id)
    with env.session(task=task) as session:
        session.get_prompt()
        for tool_name, args in MOCK_SCRIPTS[scenario_id]:
            result = session.call_tool(tool_name, dict(args))
            output = getattr(result, "output", result)
            if output.finished:
                assert output.reward is not None
                return output.reward * 100.0
    raise RuntimeError(f"{scenario_id}: script ended without finished=True")


def part_a(env) -> bool:
    print("\n=== Part A: deterministic expert replay (exact match required) ===")
    with tempfile.TemporaryDirectory() as tmp:
        logs = run_mock(
            list(MOCK_SCRIPTS), MESSAGE_LIMIT, Path(tmp), "uncoached"
        )
        # EvalLog is lazy — samples load from the log file on access, so
        # extract scores before the temp dir is deleted.
        inspect_scores = _inspect_scores(logs)
    ok = True
    print(f"{'scenario':<34}{'inspect':>9}{'ors':>9}  match")
    for scenario_id in MOCK_SCRIPTS:
        ors = ors_replay_score(env, scenario_id)
        ins = inspect_scores[scenario_id]
        match = abs(ors - ins) < 1e-9
        ok &= match
        print(f"{scenario_id:<34}{ins:>9.1f}{ors:>9.1f}  "
              f"{'OK' if match else 'MISMATCH'}")
    print(f"Part A: {'PASS — ORS serving is score-identical to Inspect' if ok else 'FAIL'}")
    return ok


# --- Part B: one real model through both interfaces -------------------------


# Inspect basic_agent's continue nudge, verbatim
# (inspect_ai.solver._basic_agent.DEFAULT_CONTINUE_MESSAGE).
CONTINUE_MESSAGE = "Please proceed to the next step using your best judgement."
# Inspect's anthropic provider default max_tokens for haiku-4-5 (observed on
# the wire in results/parity_diag/).
MAX_TOKENS = 32000


def ors_model_episode(env, task, model_id: str) -> dict:
    """Agent loop over the ORS HTTP interface replicating Inspect basic_agent.

    Parity semantics (see results/parity_diag/REPORT.md):
    - A plain assistant message does NOT end the episode — the loop appends
      Inspect's continue nudge and keeps going.
    - The 50-message cap counts Inspect-style: system + every user, assistant,
      and individual tool-result message.
    - Tool results are framed as text-block lists; RunToolError becomes
      is_error: true with the bare message (how Inspect renders ToolError).
    - At the cap, the final assistant text is graded via the terminal tool —
      the Inspect scorer's output.completion fallback.
    """
    import anthropic

    client = anthropic.Anthropic()
    tools = env.list_tools(format="anthropic")
    with env.session(task=task) as session:
        blocks = session.get_prompt()
        system_prompt = blocks[0].text
        messages: list[dict] = [{"role": "user", "content": blocks[1].text}]
        n_msgs = 2  # system + first user, Inspect accounting
        completion = ""
        while n_msgs < MESSAGE_LIMIT:
            # Streamed because the SDK requires it at max_tokens=32000;
            # Inspect's provider streams too. Wire content is identical.
            with client.messages.stream(
                model=model_id,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                tools=tools,
                messages=messages,
            ) as stream:
                response = stream.get_final_message()
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            texts = [b.text for b in response.content if b.type == "text"]
            # Inspect: output.completion is the LAST assistant message's text
            # (empty if the message was pure tool calls).
            completion = "\n".join(texts)
            # Explicit dicts: model_dump() leaks SDK-internal fields (e.g.
            # parsed_output on streamed text blocks) that the API rejects.
            content: list[dict] = []
            for b in response.content:
                if b.type == "text":
                    content.append({"type": "text", "text": b.text})
                elif b.type == "tool_use":
                    content.append({"type": "tool_use", "id": b.id,
                                    "name": b.name, "input": b.input})
            messages.append({"role": "assistant", "content": content})
            n_msgs += 1
            if not tool_uses:
                # basic_agent: nudge and continue, never terminate here.
                messages.append({"role": "user", "content": CONTINUE_MESSAGE})
                n_msgs += 1
                continue
            results = []
            reward = None
            for call in tool_uses:
                result = session.call_tool(call.name, dict(call.input))
                output = getattr(result, "output", result)
                if getattr(output, "finished", False):
                    assert output.reward is not None
                    reward = output.reward
                    finish_metadata = output.metadata
                    break
                text = "\n".join(b.text for b in output.blocks)
                if (output.metadata or {}).get("is_error"):
                    # Inspect renders ToolError as is_error: true with the
                    # bare message as a plain string.
                    results.append(
                        {"type": "tool_result", "tool_use_id": call.id,
                         "content": text, "is_error": True}
                    )
                else:
                    results.append(
                        {"type": "tool_result", "tool_use_id": call.id,
                         "content": [{"type": "text", "text": text}],
                         "is_error": False}
                    )
                n_msgs += 1  # each tool result is one message, Inspect-style
            if reward is not None:
                return {"score": reward * 100.0,
                        "metadata": finish_metadata, "via": "finish"}
            messages.append({"role": "user", "content": results})
        # Message cap: grade the final assistant text as the diagnosis (the
        # Inspect scorer's fallback on state.output.completion).
        result = session.call_tool("grade_final_message",
                                   {"message": completion})
        output = getattr(result, "output", result)
        assert output.finished and output.reward is not None
        return {"score": output.reward * 100.0,
                "metadata": output.metadata, "via": "message_cap"}


def part_b(env, model: str) -> None:
    print(f"\n=== Part B: {model}, 1 epoch/scenario, both interfaces ===")
    print("(model sampling is stochastic — comparable, not identical; "
          "Part A carries the exact-match claim)")
    sdk_model = model.split("/", 1)[1] if model.startswith("anthropic/") else model
    tasks = {t.task_spec["task_id"]: t for t in env.list_tasks(split="test")}

    with tempfile.TemporaryDirectory() as tmp:
        logs = run_real([model], "all", 1, MESSAGE_LIMIT, Path(tmp),
                        "uncoached")
        inspect_scores = _inspect_scores(logs)  # lazy logs — read before rmdir

    print(f"{'scenario':<34}{'inspect':>9}{'ors':>9}")
    for scenario_id, task_id in SCENARIO_TASKS.items():
        ors = ors_model_episode(env, tasks[task_id], sdk_model)["score"]
        ins = inspect_scores.get(scenario_id, float("nan"))
        print(f"{scenario_id:<34}{ins:>9.1f}{ors:>9.1f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=None,
                        help="Inspect model id for Part B, e.g. "
                             "anthropic/claude-haiku-4-5 (omit to skip)")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    ensure_server(args.port)
    env = _get_env(args.port)

    ok = part_a(env)
    if args.model:
        part_b(env, args.model)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
