"""ORS adapter tests: task mapping, leakage, parity, determinism, reward.

The adapter must serve the environment unchanged — these tests pin the
agent-visible surface (prompt, tool specs, observations) and the reward
mapping against the Inspect task, and guard the opaque-task-id leakage
boundary.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("openreward")

from nostart.domain.scenarios import get_scenario, list_scenarios
from nostart.grader import grade
from nostart.openreward.env import (
    TASK_SCENARIOS,
    TASK_TIERS,
    USER_MESSAGE_TEMPLATE,
    EndOfEpisodeParams,
    FinishParams,
    MeasureVoltageParams,
    NoStartEnv,
    ReadPidParams,
    ReplacePartParams,
    VisualInspectParams,
)
from nostart.prompts import PROMPTS
from nostart.tools import ToolSession

ALL_TASK_IDS = list(TASK_SCENARIOS)


def _env(task_id: str) -> NoStartEnv:
    return NoStartEnv(task_spec={"task_id": task_id})


# --- Task mapping -----------------------------------------------------------


def test_task_mapping_covers_all_scenarios() -> None:
    # list_scenarios() is alphabetical; the task list uses the published
    # results-table order (easy -> medium -> hard). ORS only requires the
    # order to be STABLE, which test_list_tasks_stable_and_indexable pins.
    assert sorted(TASK_SCENARIOS.values()) == sorted(list_scenarios())
    assert len(TASK_SCENARIOS) == len(list_scenarios())


def test_tiers_match_scenario_defs() -> None:
    for task_id, scenario_id in TASK_SCENARIOS.items():
        assert TASK_TIERS[task_id] == get_scenario(scenario_id).tier.value


def test_list_tasks_stable_and_indexable() -> None:
    tasks = NoStartEnv.list_tasks("test")
    assert tasks == NoStartEnv.list_tasks("test")
    assert [t["task_id"] for t in tasks] == ALL_TASK_IDS


def test_unknown_split_and_task_raise() -> None:
    with pytest.raises(ValueError):
        NoStartEnv.list_tasks("train")
    with pytest.raises(ValueError):
        _env("easy_dead_battery")  # scenario ids are NOT valid task ids


# --- Leakage ----------------------------------------------------------------


def test_task_specs_contain_no_scenario_names() -> None:
    payload = json.dumps(NoStartEnv.list_tasks("test")).lower()
    for scenario_id in list_scenarios():
        assert scenario_id not in payload
    for word in ("battery", "ground", "herring", "ecu", "can", "fault"):
        assert word not in payload


def test_tool_specs_and_prompt_contain_no_ground_truth() -> None:
    spec_text = NoStartEnv.list_tools().model_dump_json().lower()
    for scenario_id in list_scenarios():
        assert scenario_id not in spec_text
    for task_id in ALL_TASK_IDS:
        prompt = _env(task_id).get_prompt()
        text = "\n".join(b.text for b in prompt).lower()
        assert "root_cause" not in text
        assert task_id not in text  # opaque id itself stays out of context
        for scenario_id in list_scenarios():
            assert scenario_id not in text


def test_grade_breakdown_only_in_terminal_metadata() -> None:
    env = _env("ns-01")
    for out in (
        env.scan_dtcs(),
        env.read_pid(ReadPidParams(pid="battery_voltage")),
    ):
        assert out.metadata is None
        assert out.reward is None
        assert out.finished is False


# --- Parity with the Inspect task ------------------------------------------


def test_prompt_matches_inspect_strings() -> None:
    env = _env("ns-02")
    blocks = env.get_prompt()
    assert blocks[0].text == PROMPTS["uncoached"]
    complaint = get_scenario("medium_corroded_ground").complaint
    assert blocks[1].text == USER_MESSAGE_TEMPLATE.format(complaint=complaint)
    assert "Customer complaint:" in blocks[1].text


def test_tool_surface_matches_inspect() -> None:
    listing = NoStartEnv.list_tools()
    names = {t.name for t in listing.tools}
    assert names == {
        "scan_dtcs",
        "read_pid",
        "measure_voltage",
        "visual_inspect",
        "replace_part",
        "attempt_start",
        "finish",
    }
    # Terminal fallback exists but is hidden from the model-facing list.
    assert listing.terminal_tool is not None
    assert listing.terminal_tool.name == "grade_final_message"
    assert "grade_final_message" not in names


def test_observations_match_toolsession_serialization() -> None:


    env = _env("ns-01")
    direct = ToolSession(TASK_SCENARIOS["ns-01"])
    out = env.measure_voltage(
        MeasureVoltageParams(
            point_a="battery_positive",
            point_b="battery_negative",
            engine_state="key_off",
        )
    )
    expected = json.dumps(
        direct.measure_voltage(
            "battery_positive", "battery_negative", "key_off"
        ),
        indent=1,
    )
    assert out.blocks[0].text == expected


def test_invalid_measure_input_is_model_visible_error_not_crash() -> None:


    env = _env("ns-01")
    out = env.measure_voltage(
        MeasureVoltageParams(
            point_a="flux_capacitor", point_b="chassis", engine_state="key_off"
        )
    )
    assert out.finished is False
    assert out.blocks[0].text.startswith("Error: ")
    assert "flux_capacitor" in out.blocks[0].text


# --- Determinism ------------------------------------------------------------


def test_identical_sessions_produce_identical_observations() -> None:


    def run(env: NoStartEnv) -> list[str]:
        stream = [env.scan_dtcs().blocks[0].text]
        stream.append(env.attempt_start().blocks[0].text)
        stream.append(
            env.measure_voltage(
                MeasureVoltageParams(
                    point_a="battery_positive",
                    point_b="battery_negative",
                    engine_state="cranking",
                )
            ).blocks[0].text
        )
        stream.append(
            env.visual_inspect(
                VisualInspectParams(area="ground_strap")
            ).blocks[0].text
        )
        return stream

    for task_id in ALL_TASK_IDS:
        assert run(_env(task_id)) == run(_env(task_id))


# --- Reward mapping ---------------------------------------------------------


def _expert_fix(env: NoStartEnv) -> None:
    """Minimal correct episode for ns-01 (dead battery): probe, fix, verify."""


    env.measure_voltage(
        MeasureVoltageParams(
            point_a="battery_positive",
            point_b="battery_negative",
            engine_state="key_off",
        )
    )
    env.replace_part(ReplacePartParams(component="battery"))
    env.attempt_start()


def test_finish_reward_is_grader_total_over_100() -> None:


    env = _env("ns-01")
    _expert_fix(env)
    out = env.finish(FinishParams(answer="battery dead"))
    assert out.finished is True
    breakdown = grade(env._session.world)
    assert out.reward == pytest.approx(breakdown.total / 100.0)
    assert out.reward is not None and out.reward > 0.5
    assert out.metadata is not None
    # metadata mirrors the Inspect Score metadata (display-formatted dump),
    # plus the numeric total.
    assert out.metadata["total"] == breakdown.model_dump()["total"]
    assert out.metadata["score_0_100"] == breakdown.total


def test_terminal_fallback_grades_plain_message_as_diagnosis() -> None:


    env = _env("ns-01")
    _expert_fix(env)
    out = env.grade_final_message(
        EndOfEpisodeParams(message="battery dead")
    )
    assert out.finished is True
    assert out.reward is not None and out.reward > 0.5
    # Idempotent if the harness calls it after finish (no double charge).
    snapshot = env._session.world.public_snapshot()
    again = env.grade_final_message(EndOfEpisodeParams(message="ignored"))
    assert env._session.world.public_snapshot() == snapshot
    assert again.reward == out.reward
