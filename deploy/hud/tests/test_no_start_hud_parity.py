"""Parity tests: HUD managed path vs. the published Inspect / OpenReward path.

The claim these tests defend is narrow and checkable: *a buyer running
no-start-env on managed HUD infra sees the same environment the published
benchmark measured.* Concretely, for every one of the five scenarios, replaying
the documented expert trajectory through the managed adapter produces

* byte-identical observation streams,
* an identical ``GradeBreakdown``,
* a reward that is exactly the published 0-100 total over 100,

and the end-to-end Inspect task, driven by the same trajectory through
``mockllm``, returns the same score.

Run:  <repo>/.venv/bin/python -m pytest deploy/hud/tests -q
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

HUD_DIR = Path(__file__).resolve().parents[1]
REPO = HUD_DIR.parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


core = _load("ns_adapter_core", HUD_DIR / "no-start-env" / "adapter_core.py")
stage = _load("hud_stage", HUD_DIR / "stage.py")
trajectories = _load("hud_expert_trajectories", HUD_DIR / "expert_trajectories.py")

from nostart.domain.scenarios import get_scenario, list_scenarios  # noqa: E402
from nostart.grader import grade  # noqa: E402
from nostart.prompts import PROMPTS  # noqa: E402
from nostart.tools import ToolSession  # noqa: E402

ALL_TASK_IDS = list(core.TASK_SCENARIOS)


def _expert_scripts() -> dict[str, list[tuple[str, dict]]]:
    """The documented expert trajectories, taken from the repo's own mock
    runner so the parity replay cannot drift from the published expert paths."""
    return trajectories.no_start_expert_trajectories()


# --- Task identity and leakage ----------------------------------------------


def test_task_mapping_covers_every_published_scenario() -> None:
    assert sorted(core.TASK_SCENARIOS.values()) == sorted(list_scenarios())
    assert len(core.TASK_SCENARIOS) == 5


def test_tiers_match_scenario_definitions() -> None:
    for task_id, scenario_id in core.TASK_SCENARIOS.items():
        assert core.TASK_TIERS[task_id] == get_scenario(scenario_id).tier.value


def test_task_ids_match_the_openreward_listing() -> None:
    """The opaque ids a buyer sees must be the same on both marketplaces."""
    pytest.importorskip("openreward")
    from nostart.openreward.env import TASK_SCENARIOS, TASK_TIERS

    assert core.TASK_SCENARIOS == TASK_SCENARIOS
    assert core.TASK_TIERS == TASK_TIERS
    assert list(core.TASK_SCENARIOS) == list(TASK_SCENARIOS)  # order is an API


def test_client_visible_task_specs_leak_no_ground_truth() -> None:
    payload = json.dumps(core.list_tasks()).lower()
    for scenario_id in list_scenarios():
        assert scenario_id not in payload
    for word in ("battery", "ground", "herring", "ecu", "can", "fault"):
        assert word not in payload


def test_prompt_and_tool_specs_leak_no_ground_truth() -> None:
    spec_text = json.dumps(
        [{"name": s.name, "description": s.description, "parameters": s.parameters}
         for s in core.TOOL_SPECS]
    ).lower()
    for scenario_id in list_scenarios():
        assert scenario_id not in spec_text

    for task_id in ALL_TASK_IDS:
        text = core.NoStartSession(task_id).prompt().lower()
        assert "root_cause" not in text
        assert task_id not in text
        for scenario_id in list_scenarios():
            assert scenario_id not in text


# --- Prompt parity ----------------------------------------------------------


def test_prompt_blocks_are_the_published_strings() -> None:
    session = core.NoStartSession("ns-02")
    system, user = session.prompt_blocks()
    assert system == PROMPTS["uncoached"]
    complaint = get_scenario("medium_corroded_ground").complaint
    assert user == core.USER_MESSAGE_TEMPLATE.format(complaint=complaint)
    # HUD's tasks.start returns one string; the join is the only concession.
    assert session.prompt() == f"{system}\n\n{user}"


def test_user_message_matches_the_inspect_sample_input() -> None:
    from nostart.task import _make_sample

    for task_id, scenario_id in core.TASK_SCENARIOS.items():
        _, user = core.NoStartSession(task_id).prompt_blocks()
        assert user == _make_sample(scenario_id).input


# --- Tool surface parity ----------------------------------------------------


def test_tool_specs_byte_match_inspect_serialization() -> None:
    """Descriptions and JSON schemas must be what Inspect put on the wire for
    the published run — including the embedded newlines."""
    from inspect_ai.tool import ToolDef

    from nostart.task import ALL_TOOLS

    by_name = core.TOOL_SPECS_BY_NAME
    for inspect_tool in ALL_TOOLS:
        td = ToolDef(inspect_tool)
        assert td.name in by_name
        assert by_name[td.name].description == td.description
        assert by_name[td.name].parameters == td.parameters.model_dump(
            exclude_none=True
        )

    # finish is basic_agent's submit tool, renamed and re-described by task.py.
    finish = by_name["finish"]
    assert finish.description == (
        "Submit your final diagnosis. BEGIN your answer with the faulty "
        "component and its failure mode (e.g. 'fusible_link blown'); "
        "supporting reasoning may follow."
    )
    assert finish.parameters == {
        "type": "object",
        "properties": {
            "answer": {"type": "string", "description": "Submitted answer"}
        },
        "required": ["answer"],
        "additionalProperties": False,
    }


def test_tool_names_and_order_match_the_inspect_agent_surface() -> None:
    from nostart.task import ALL_TOOLS
    from inspect_ai.tool import ToolDef

    expected = [ToolDef(t).name for t in ALL_TOOLS] + ["finish"]
    assert [s.name for s in core.TOOL_SPECS] == expected


# --- Trajectory parity ------------------------------------------------------


def _replay_direct(scenario_id: str, script) -> tuple[list[str], object]:
    """The published path: the same ToolSession calls and the same
    json.dumps(indent=1) serialization the Inspect tool bodies perform."""
    session = ToolSession(scenario_id)
    stream: list[str] = []
    for name, args in script:
        if name == "finish":
            session.finish(args["answer"])
            stream.append("Diagnosis submitted. Episode finished.")
            continue
        result = getattr(session, name)(**args)
        stream.append(result if isinstance(result, str) else json.dumps(result, indent=1))
    return stream, grade(session.world)


def _replay_managed(task_id: str, script) -> tuple[list[str], object, float]:
    session = core.NoStartSession(task_id)
    stream = [session.call(name, args).text for name, args in script]
    result = session.grade()
    return stream, result.breakdown, result.reward


@pytest.mark.parametrize("task_id", ALL_TASK_IDS)
def test_expert_trajectory_parity(task_id: str) -> None:
    scenario_id = core.TASK_SCENARIOS[task_id]
    script = _expert_scripts()[scenario_id]

    direct_stream, direct_grade = _replay_direct(scenario_id, script)
    managed_stream, managed_grade, reward = _replay_managed(task_id, script)

    assert managed_stream == direct_stream
    assert managed_grade.model_dump() == direct_grade.model_dump()
    assert reward == pytest.approx(direct_grade.total / 100.0)
    assert direct_grade.total == pytest.approx(100.0), (
        f"expert should still score 100 on {scenario_id}"
    )


def test_expert_trajectory_parity_with_the_inspect_task_end_to_end(
    tmp_path: Path,
) -> None:
    """Drive the real Inspect task with the same trajectory through mockllm and
    compare its Score to the managed reward."""
    inspect_ai = pytest.importorskip("inspect_ai")
    from inspect_ai.model import ModelOutput, get_model

    from nostart.task import no_start

    scripts = _expert_scripts()
    for task_id, scenario_id in core.TASK_SCENARIOS.items():
        script = scripts[scenario_id]
        model = get_model(
            "mockllm/model",
            custom_outputs=[
                ModelOutput.for_tool_call("mockllm/model", fn, args)
                for fn, args in script
            ],
        )
        (log,) = inspect_ai.eval(
            no_start(scenarios=scenario_id, prompt_variant="uncoached"),
            model=model,
            display="none",
            log_dir=str(tmp_path / "logs"),
            log_format="json",
            score=True,
        )
        assert log.status == "success", log.error
        assert log.samples is not None
        inspect_score = log.samples[0].scores["nostart_grader"]

        _, managed_grade, reward = _replay_managed(task_id, script)
        assert reward * 100.0 == pytest.approx(float(inspect_score.value))
        assert managed_grade.model_dump() == inspect_score.metadata


# --- Error, determinism, and fallback behaviour -----------------------------


def test_invalid_measure_voltage_returns_the_bare_inspect_message() -> None:
    session = core.NoStartSession("ns-01")
    result = session.measure_voltage("flux_capacitor", "chassis", "key_off")
    assert result.is_error is True
    assert result.text.startswith("Unknown node 'flux_capacitor'")
    assert not result.text.startswith("Error")

    direct = ToolSession("easy_dead_battery")
    with pytest.raises(ValueError) as excinfo:
        direct.measure_voltage("flux_capacitor", "chassis", "key_off")
    assert result.text == str(excinfo.value)


@pytest.mark.parametrize("task_id", ALL_TASK_IDS)
def test_identical_sessions_produce_identical_streams(task_id: str) -> None:
    def run() -> list[str]:
        session = core.NoStartSession(task_id)
        return [
            session.scan_dtcs().text,
            session.attempt_start().text,
            session.measure_voltage(
                "battery_positive", "battery_negative", "cranking"
            ).text,
            session.visual_inspect("ground_strap").text,
        ]

    assert run() == run()


def test_unfinished_episode_grades_the_final_message_as_the_diagnosis() -> None:
    """Mirrors the Inspect scorer's state.output.completion fallback."""
    managed = core.NoStartSession("ns-01")
    managed.measure_voltage("battery_positive", "battery_negative", "key_off")
    managed.replace_part("battery")
    managed.attempt_start()
    assert managed.finished is False
    result = managed.grade(fallback_answer="battery dead")

    direct = ToolSession("easy_dead_battery")
    direct.measure_voltage("battery_positive", "battery_negative", "key_off")
    direct.replace_part("battery")
    direct.attempt_start()
    direct.finish("battery dead")

    assert result.breakdown.model_dump() == grade(direct.world).model_dump()
    assert result.reward > 0.5


def test_grading_is_idempotent_after_finish() -> None:
    session = core.NoStartSession("ns-01")
    session.measure_voltage("battery_positive", "battery_negative", "key_off")
    session.replace_part("battery")
    session.attempt_start()
    session.finish("battery dead")
    first = session.grade()
    second = session.grade(fallback_answer="ignored")
    assert first.breakdown.model_dump() == second.breakdown.model_dump()
    assert first.reward == second.reward


def test_unknown_task_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        core.NoStartSession("easy_dead_battery")  # scenario ids are not task ids
    with pytest.raises(ValueError):
        core.NoStartSession("ns-99")


def test_unknown_tool_is_rejected() -> None:
    with pytest.raises(ValueError):
        core.NoStartSession("ns-01").call("read_the_manual", {})


# --- Packaging integrity ----------------------------------------------------


def test_vendored_source_is_a_byte_exact_mirror() -> None:
    """The container ships vendor/nostart; it must equal src/nostart."""
    source = REPO / "src" / "nostart"
    target = HUD_DIR / "no-start-env" / "vendor" / "nostart"
    if not target.exists():
        pytest.skip("vendor/ not staged (run python deploy/hud/stage.py)")
    assert stage.drift(source, target) == []
