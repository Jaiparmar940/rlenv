"""End-to-end tests for the Inspect task (offline, scripted mock model)."""

from __future__ import annotations

from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model

from nostart.task import no_start

SCORER = "nostart_grader"


def _scripted_model(*calls: tuple[str, dict]):
    return get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.for_tool_call("mockllm/model", fn, args)
            for fn, args in calls
        ],
    )


def _run(model, scenarios: str, tmp_path, message_limit: int = 50):
    logs = inspect_eval(
        no_start(scenarios=scenarios, message_limit=message_limit),
        model=model,
        log_dir=str(tmp_path),
        display="none",
    )
    assert logs[0].status == "success"
    return logs[0].samples[0]


def test_scripted_expert_scores_100(tmp_path) -> None:
    model = _scripted_model(
        ("measure_voltage", {"point_a": "battery_negative",
                             "point_b": "engine_block",
                             "engine_state": "cranking"}),
        ("finish", {"answer": "ground_strap corroded"}),
    )
    sample = _run(model, "medium_corroded_ground", tmp_path)
    score = sample.scores[SCORER]
    assert score.value == 100.0
    assert score.metadata["true_component"] == "ground_strap"
    assert not score.metadata["guessing_penalty_applied"]


def test_idle_agent_hits_guessing_cap(tmp_path) -> None:
    # Default mockllm output never calls a tool; the episode ends at the
    # message limit with zero probes, so the guessing cap must engage.
    model = get_model("mockllm/model")
    sample = _run(model, "easy_dead_battery", tmp_path, message_limit=8)
    score = sample.scores[SCORER]
    assert score.metadata["guessing_penalty_applied"]
    assert score.value <= 40.0


def test_no_ground_truth_in_agent_visible_messages(tmp_path) -> None:
    # Everything the agent sees before its own finish() call must not name
    # the true failure mode. (Component names legitimately appear in the
    # tool-input reference; failure modes must never appear unprompted.)
    model = _scripted_model(
        ("scan_dtcs", {}),
        ("attempt_start", {}),
        ("measure_voltage", {"point_a": "battery_negative",
                             "point_b": "engine_block",
                             "engine_state": "cranking"}),
        ("finish", {"answer": "it is broken"}),
    )
    scenario_id = "medium_ground_red_herring_battery"
    sample = _run(model, scenario_id, tmp_path)
    true_mode = sample.scores[SCORER].metadata["true_mode"]  # "corroded"

    for message in sample.messages:
        text = (getattr(message, "text", "") or "").lower()
        # The scenario id spells out the answer; it must NEVER be visible,
        # not even in the post-finish echo.
        assert scenario_id not in text, f"scenario id leaked in {message.role}"
        assert "red_herring" not in text
        if message.role == "assistant":
            calls = getattr(message, "tool_calls", None) or []
            if any(c.function == "finish" for c in calls):
                break  # everything after is the agent's own submission echo
        assert true_mode not in text, f"ground truth leaked in {message.role}"
