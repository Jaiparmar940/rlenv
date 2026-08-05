"""Grader + env tests, including the adversarial agents from AUDIT.md.

Every adversarial case here was run against the grader and either already
scored correctly or forced a fix; they are pinned so regressions can't
reopen the holes.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kitchen_task.agents import ScriptedExpert
from kitchen_task.backends.symbolic import SymbolicBackend
from kitchen_task.env import MAX_ACTIONS, KitchenEnv
from kitchen_task.grader import grade
from kitchen_task.task import EXPERT_ACTIONS, VARIANTS, make_scenario


def run_actions(variant, actions, seed=0):
    backend = SymbolicBackend()
    env = KitchenEnv(backend, make_scenario(variant, seed))
    obs = env.observation()
    for a in actions:
        obs, over = env.step(a)
        if over:
            break
    return env, backend, grade(env.ep, backend)


def run_expert(variant, seed=0):
    backend = SymbolicBackend()
    env = KitchenEnv(backend, make_scenario(variant, seed))
    agent = ScriptedExpert()
    obs = env.observation()
    for _ in range(MAX_ACTIONS):
        obs, over = env.step(agent(obs))
        if over:
            break
    return env, backend, grade(env.ep, backend)


# --- feasibility + baselines -------------------------------------------------

def test_expert_scores_100_everywhere():
    for v in VARIANTS:
        _, _, g = run_expert(v)
        assert g.total == 100.0, (v, g.report())


def test_expert_action_counts_match_pinned_baselines():
    for v in VARIANTS:
        env, _, _ = run_expert(v)
        assert len(env.ep.events) == EXPERT_ACTIONS[v], v


def test_determinism_identical_obs_streams():
    def stream(v):
        backend = SymbolicBackend()
        env = KitchenEnv(backend, make_scenario(v, seed=42))
        agent = ScriptedExpert()
        out = [env.observation()]
        for _ in range(MAX_ACTIONS):
            obs, over = env.step(agent(out[-1]))
            out.append(obs)
            if over:
                break
        return out

    for v in VARIANTS:
        assert stream(v) == stream(v)


# --- information boundary ----------------------------------------------------

def test_hidden_state_not_in_initial_observation():
    for v in ("nominal", "fridge_full"):
        env = KitchenEnv(SymbolicBackend(), make_scenario(v, 0))
        obs = env.observation()
        assert "milk" not in obs and "juice" not in obs and "slots" not in obs
    # nominal and fridge_full are indistinguishable before inspection
    obs_a = KitchenEnv(SymbolicBackend(), make_scenario("nominal", 0)).observation()
    obs_b = KitchenEnv(SymbolicBackend(), make_scenario("fridge_full", 0)).observation()
    assert obs_a == obs_b


def test_cannot_interact_through_closed_doors():
    env, backend, _ = run_actions("nominal", ["pick leftovers", "place leftovers fridge"])
    assert not env.ep.events[-1].ok
    assert backend.object_region("leftovers") == "held"
    env, backend, _ = run_actions("container_missing", ["pick leftovers"])
    assert not env.ep.events[-1].ok  # can't grab from a closed microwave


# --- adversarial agents (AUDIT.md) ------------------------------------------

def test_lucky_declare_without_inspection_gets_no_inference_credit():
    env, _, g = run_actions("fridge_full", [
        "declare the fridge is full",  # true! but nothing was inspected
        "open fridge", "pick milk", "discard milk",
        "pick leftovers", "place leftovers fridge", "close fridge", "done",
    ])
    assert g.inference == 0.0
    assert any("lucky" in n for n in g.notes)


def test_immediate_done_scores_near_zero():
    _, _, g = run_actions("nominal", ["done"])
    assert g.inference == 0.0 and g.parsimony == 0.0
    assert g.total <= 10.0


def test_inspect_everything_spam_scores_below_targeted():
    spam = ["open fridge", "open microwave", "open cabinet",
            "close microwave", "close cabinet",
            "declare fridge has space, nominal",
            "pick leftovers", "place leftovers fridge", "close fridge", "done"]
    _, _, g_spam = run_actions("nominal", spam)
    _, _, g_expert = run_expert("nominal")
    assert g_spam.parsimony < g_expert.parsimony
    assert g_spam.total < g_expert.total


def test_discarding_fresh_food_is_penalized():
    env, backend, g = run_actions("fridge_full", [
        "open fridge", "declare fridge is full",
        "pick juice", "discard juice",       # makes room, destroys value
        "pick leftovers", "place leftovers fridge", "close fridge", "done",
    ])
    assert backend.object_region("leftovers") == "fridge_shelf"
    assert g.total <= 80.0
    assert any("fresh food discarded" in n for n in g.notes)


def test_kitchen_sink_declare_parses_against_wrong_variant():
    env, _, g = run_actions("nominal", [
        "open fridge",
        "declare full expired microwave missing nominal",  # keyword shotgun
        "pick leftovers", "place leftovers fridge", "close fridge", "done",
    ])
    assert g.inference == 0.0  # parses as fridge_full, which is wrong here


def test_correct_diagnosis_without_fix_is_capped():
    _, _, g = run_actions("container_missing", [
        "open microwave", "declare leftovers are in the microwave", "done",
    ])
    assert g.inference == 40.0
    assert g.parsimony == 0.0  # withheld: job not finished
    assert g.total <= 50.0


def test_timeout_without_done_is_noted():
    _, _, g = run_actions("nominal", ["open fridge", "close fridge"] * (MAX_ACTIONS // 2))
    assert any("action cap" in n for n in g.notes)
    assert g.total == 0.0  # flail overrun debits below zero, floored


def test_teleported_accidental_success_is_capped():
    """Sim teleported into a perfect end state with zero agent actions —
    the grader must not false-fire."""
    backend = SymbolicBackend()
    env = KitchenEnv(backend, make_scenario("nominal", 0))
    backend.move_object("leftovers", "fridge_shelf")  # bypasses the env
    g = grade(env.ep, backend)
    assert g.inference == 0.0
    assert g.total <= 40.0


def test_teleported_success_plus_early_done_is_capped():
    backend = SymbolicBackend()
    env = KitchenEnv(backend, make_scenario("fridge_full", 0))
    env.step("done")
    backend.move_object("expired_milk", "trash")
    backend.move_object("leftovers", "fridge_shelf")
    g = grade(env.ep, backend)
    assert g.total <= 40.0


def test_open_everything_solver_is_not_capped_just_inefficient():
    _, _, g = run_actions("container_missing", [
        "open cabinet", "open fridge", "open microwave", "pick leftovers",
        "place leftovers fridge", "close fridge", "close microwave",
        "close cabinet", "done",
    ])
    # microwave (the reveal) opened before placing -> not capped, but spam paid for
    assert g.cap == 100.0 and g.parsimony < 25.0


def test_pick_before_inspect_is_not_capped_just_inefficient():
    # haiku's observed failure shape: grab first, inspect second, recover
    _, _, g = run_actions("fridge_full", [
        "pick leftovers", "open fridge", "place leftovers counter",
        "pick milk", "discard milk", "pick leftovers",
        "place leftovers fridge", "close fridge",
        "declare fridge was full, milk expired", "done",
    ])
    assert g.cap == 100.0
    assert g.parsimony < 25.0


def test_unparseable_declare_falls_back_to_sequence_evidence():
    """Pinned from a real haiku-on-sim transcript (2026-08-04): targeted
    microwave-first inspection, perfect fix, but declared the outcome
    ('leftovers container stored in fridge') instead of the finding.
    Unparseable is not wrong: sequence evidence earns the implicit 20."""
    _, _, g = run_actions("container_missing", [
        "open microwave", "pick leftovers container", "open fridge",
        "place leftovers container fridge", "close fridge", "close microwave",
        "declare leftovers container stored in fridge", "done",
    ])
    assert g.inference == 20.0
    assert g.total == 80.0


def test_wrongly_parsed_declare_still_scores_zero_inference():
    _, _, g = run_actions("nominal", [
        "open fridge", "declare the fridge is full",  # parses, and is wrong
        "pick leftovers", "place leftovers fridge", "close fridge", "done",
    ])
    assert g.inference == 0.0


def test_no_declare_but_inspect_first_gets_partial_inference():
    _, _, g = run_actions("nominal", [
        "open fridge", "pick leftovers", "place leftovers fridge",
        "close fridge", "done",
    ])
    assert g.inference == 20.0
    assert g.total == 80.0
