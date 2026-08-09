"""Parity tests: HUD managed path vs. the published decision-layer implementation.

The managed environment must be the same environment, not a lookalike. For each
of the three hidden-state variants, and for the adversarial and real-LLM action
sequences already pinned in ``decision-layer/tests``, replaying through the
managed adapter must produce

* byte-identical observation streams (including the reveal rule),
* identical inference / parsimony / intervention / cap / total,
* a reward that is exactly the published 0-100 total over 100.

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


core = _load(
    "dlk_adapter_core", HUD_DIR / "decision-layer-kitchen" / "adapter_core.py"
)
stage = _load("hud_stage", HUD_DIR / "stage.py")

from kitchen_task.agents import ScriptedExpert  # noqa: E402
from kitchen_task.backends.symbolic import SymbolicBackend  # noqa: E402
from kitchen_task.env import MAX_ACTIONS, KitchenEnv  # noqa: E402
from kitchen_task.grader import grade  # noqa: E402
from kitchen_task.task import EXPERT_ACTIONS, VARIANTS, make_scenario  # noqa: E402

ALL_TASK_IDS = list(core.TASK_VARIANTS)

# Action sequences pinned in decision-layer/tests/test_decision_layer.py: the
# adversarial probes from AUDIT.md plus two real claude-haiku-4-5 traces. If the
# managed path reproduces these, it reproduces the anti-cheat behaviour too.
PINNED_SEQUENCES: dict[str, tuple[str, list[str]]] = {
    "immediate_done": ("nominal", ["done"]),
    "correct_declare_without_inspection": (
        "fridge_full",
        ["declare the fridge is full and the milk is expired", "done"],
    ),
    "discard_fresh_food": (
        "fridge_full",
        [
            "open fridge",
            "declare fridge is full",
            "pick juice",
            "discard juice",
            "pick leftovers",
            "place leftovers fridge",
            "close fridge",
            "done",
        ],
    ),
    "keyword_shotgun_declare": (
        "nominal",
        [
            "open fridge",
            "declare full expired microwave missing nominal",
            "pick leftovers",
            "place leftovers fridge",
            "close fridge",
            "done",
        ],
    ),
    "haiku_pick_before_inspect": (
        "fridge_full",
        [
            "pick leftovers",
            "open fridge",
            "place leftovers counter",
            "pick milk",
            "discard milk",
            "pick leftovers",
            "place leftovers fridge",
            "close fridge",
            "declare fridge was full, milk expired",
            "done",
        ],
    ),
    "haiku_unparseable_declare_on_sim_trace": (
        "container_missing",
        [
            "open microwave",
            "pick leftovers container",
            "open fridge",
            "place leftovers container fridge",
            "close fridge",
            "close microwave",
            "declare leftovers container stored in fridge",
            "done",
        ],
    ),
    "malformed_actions": (
        "nominal",
        [
            "please open the fridge for me",
            "open fridge",
            "place leftovers ceiling",
            "pick nonexistent_object",
            "pick leftovers",
            "place leftovers fridge",
            "close fridge",
            "declare fridge had space",
            "done",
        ],
    ),
    "action_cap_overrun": ("nominal", ["scan the room"] * (MAX_ACTIONS + 3)),
}

_VARIANT_TO_TASK_ID = {v: t for t, v in core.TASK_VARIANTS.items()}


# --- Task identity and leakage ----------------------------------------------


def test_task_mapping_covers_every_published_variant() -> None:
    assert sorted(core.TASK_VARIANTS.values()) == sorted(VARIANTS)
    assert len(core.TASK_VARIANTS) == 3


def test_client_visible_task_specs_leak_no_hidden_state() -> None:
    payload = json.dumps(core.list_tasks()).lower()
    for variant in VARIANTS:
        assert variant not in payload
    for word in ("fridge", "microwave", "expired", "full", "missing"):
        assert word not in payload


def test_prompt_leaks_no_variant_name() -> None:
    for task_id in ALL_TASK_IDS:
        text = core.KitchenSession(task_id).prompt().lower()
        for variant in VARIANTS:
            assert variant not in text
        assert task_id not in text


def test_nominal_and_fridge_full_prompts_stay_byte_identical() -> None:
    """The published indistinguishability property, re-asserted on the managed
    prompt (which wraps the initial observation)."""
    assert (
        core.KitchenSession("dlk-01").prompt()
        == core.KitchenSession("dlk-02").prompt()
    )


# --- Prompt parity ----------------------------------------------------------


def test_prompt_blocks_are_the_published_framing_and_first_observation() -> None:
    from kitchen_task.agents import LLMAgent

    for task_id, variant in core.TASK_VARIANTS.items():
        system, observation = core.KitchenSession(task_id).prompt_blocks()
        assert system == LLMAgent.SYSTEM
        reference = KitchenEnv(SymbolicBackend(), make_scenario(variant, 0))
        assert observation == reference.observation()


# --- Trajectory parity ------------------------------------------------------


def _replay_direct(variant: str, actions, seed: int = 0):
    backend = SymbolicBackend()
    env = KitchenEnv(backend, make_scenario(variant, seed))
    stream = [env.observation()]
    for action in actions:
        observation, over = env.step(action)
        stream.append(observation)
        if over:
            break
    return stream, grade(env.ep, backend)


def _replay_managed(task_id: str, actions, seed: int = 0):
    session = core.KitchenSession(task_id, seed)
    stream = [session.prompt_blocks()[1]]
    for action in actions:
        result = session.call("act", {"action": action})
        stream.append(result.text)
        if result.episode_over:
            break
    result = session.grade()
    return stream, result.grade, result.reward


def _assert_same(direct_grade, managed_grade) -> None:
    assert managed_grade.inference == direct_grade.inference
    assert managed_grade.parsimony == direct_grade.parsimony
    assert managed_grade.intervention == direct_grade.intervention
    assert managed_grade.cap == direct_grade.cap
    assert managed_grade.total == direct_grade.total
    assert managed_grade.notes == direct_grade.notes


@pytest.mark.parametrize("task_id", ALL_TASK_IDS)
def test_scripted_expert_parity(task_id: str) -> None:
    variant = core.TASK_VARIANTS[task_id]

    # The expert is reactive: it reads observations, so it has to be driven
    # through each path independently rather than replayed as a fixed list.
    direct_backend = SymbolicBackend()
    direct_env = KitchenEnv(direct_backend, make_scenario(variant, 0))
    direct_agent = ScriptedExpert()
    direct_stream = [direct_env.observation()]
    for _ in range(MAX_ACTIONS):
        observation, over = direct_env.step(direct_agent(direct_stream[-1]))
        direct_stream.append(observation)
        if over:
            break
    direct_grade = grade(direct_env.ep, direct_backend)

    session = core.KitchenSession(task_id)
    managed_agent = ScriptedExpert()
    managed_stream = [session.prompt_blocks()[1]]
    for _ in range(MAX_ACTIONS):
        result = session.act(managed_agent(managed_stream[-1]))
        managed_stream.append(result.text)
        if result.episode_over:
            break
    managed = session.grade()

    assert managed_stream == direct_stream
    _assert_same(direct_grade, managed.grade)
    assert managed.reward == pytest.approx(direct_grade.total / 100.0)
    assert direct_grade.total == 100.0
    assert session.actions_used == EXPERT_ACTIONS[variant]


@pytest.mark.parametrize("case", sorted(PINNED_SEQUENCES))
def test_pinned_sequence_parity(case: str) -> None:
    variant, actions = PINNED_SEQUENCES[case]
    task_id = _VARIANT_TO_TASK_ID[variant]

    direct_stream, direct_grade = _replay_direct(variant, actions)
    managed_stream, managed_grade, reward = _replay_managed(task_id, actions)

    assert managed_stream == direct_stream
    _assert_same(direct_grade, managed_grade)
    assert reward == pytest.approx(direct_grade.total / 100.0)


def test_anti_cheat_properties_survive_the_managed_path() -> None:
    """Spot-check the three headline grader protections through the adapter."""
    # Guessing cap: a correct declare with no revealing inspection.
    _, capped, _ = _replay_managed(
        "dlk-02", ["declare the fridge is full and the milk is expired", "done"]
    )
    assert capped.cap == 40.0

    # Fresh-food discard debit.
    _, penalized, _ = _replay_managed("dlk-02", PINNED_SEQUENCES["discard_fresh_food"][1])
    assert penalized.total <= 80.0

    # Parsimony withheld when the primary intervention never landed.
    _, terse, _ = _replay_managed("dlk-01", ["done"])
    assert terse.parsimony == 0.0
    assert terse.total <= 10.0


def test_grading_reads_backend_state_not_agent_claims() -> None:
    """A truthful-sounding declaration cannot manufacture intervention credit."""
    _, lying, _ = _replay_managed(
        "dlk-01",
        [
            "open fridge",
            "declare fridge has space, everything nominal",
            "declare the leftovers are now on the fridge shelf",
            "close fridge",
            "done",
        ],
    )
    assert lying.intervention < 25.0


# --- Episode termination ----------------------------------------------------


def test_actions_after_done_are_refused_and_do_not_change_the_grade() -> None:
    session = core.KitchenSession("dlk-01")
    for action in ("open fridge", "declare fridge has space", "pick leftovers",
                   "place leftovers fridge", "close fridge", "done"):
        session.act(action)
    before = session.grade()
    used = session.actions_used

    extra = session.act("open fridge")
    assert extra.episode_over is True
    assert extra.text == core.EPISODE_OVER_TEXT
    assert session.actions_used == used
    after = session.grade()
    _assert_same(before.grade, after.grade)
    assert after.reward == before.reward


def test_action_cap_terminates_the_episode() -> None:
    session = core.KitchenSession("dlk-01")
    over = False
    for _ in range(MAX_ACTIONS + 5):
        over = session.act("loiter").episode_over
        if over:
            break
    assert over is True
    assert session.actions_used == MAX_ACTIONS
    assert session.actions_remaining == 0


def test_malformed_action_costs_an_action_and_returns_the_help_text() -> None:
    session = core.KitchenSession("dlk-01")
    result = session.act("please open the fridge for me")
    assert session.actions_used == 1
    assert "Could not parse that action." in result.text
    assert result.episode_over is False


# --- Backend and packaging integrity ----------------------------------------


def test_managed_environment_runs_the_symbolic_backend() -> None:
    session = core.KitchenSession("dlk-01")
    assert session.backend.name == "symbolic"


def test_unknown_task_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        core.KitchenSession("nominal")  # variant names are not task ids
    with pytest.raises(ValueError):
        core.KitchenSession("dlk-99")


def test_unknown_tool_is_rejected() -> None:
    with pytest.raises(ValueError):
        core.KitchenSession("dlk-01").call("teleport", {"obj": "leftovers"})


def test_vendored_source_is_a_byte_exact_mirror() -> None:
    source = REPO / "decision-layer" / "kitchen_task"
    target = HUD_DIR / "decision-layer-kitchen" / "vendor" / "kitchen_task"
    if not target.exists():
        pytest.skip("vendor/ not staged (run python deploy/hud/stage.py)")
    assert stage.drift(source, target) == []
