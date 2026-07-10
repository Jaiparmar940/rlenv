"""Physical-consistency tests for fault → symptom propagation."""

from __future__ import annotations

import pytest

from nostart.domain.components import Component, FailureMode, InjectedFault
from nostart.domain.propagation import (
    CrankBehavior,
    EngineState,
    NOMINAL_NODES,
    resolve_symptoms,
)
from nostart.domain.scenarios import get_scenario, list_scenarios


def _fault(component: Component, mode: FailureMode, **severity: float) -> InjectedFault:
    return InjectedFault(component=component, mode=mode, severity=severity)


def _battery_v(symptoms) -> float:
    return symptoms.potential_difference("battery_positive", "battery_negative")


def _ground_drop(symptoms) -> float:
    """Magnitude of the ground-path drop (battery_negative → engine_block)."""
    return abs(symptoms.potential_difference("battery_negative", "engine_block"))


def _feed_drop(symptoms) -> float:
    """Magnitude of the positive-feed drop (battery_positive → starter_stud)."""
    return abs(symptoms.potential_difference("battery_positive", "starter_stud"))


class TestNominalBaseline:
    def test_healthy_crank_starts(self) -> None:
        symptoms = resolve_symptoms([], EngineState.CRANKING)
        assert symptoms.crank_behavior == CrankBehavior.STARTS

    def test_battery_positive_exceeds_starter_stud_when_healthy(self) -> None:
        symptoms = resolve_symptoms([], EngineState.CRANKING)
        assert symptoms.node_potentials["battery_positive"] >= (
            symptoms.node_potentials["starter_stud"]
        )

    def test_healthy_ground_path_has_no_drop(self) -> None:
        for state in EngineState:
            symptoms = resolve_symptoms([], state)
            assert _ground_drop(symptoms) <= 0.05


class TestDeadBattery:
    def test_dead_battery_low_voltage_all_points(self) -> None:
        fault = _fault(Component.BATTERY, FailureMode.DEAD)
        symptoms = resolve_symptoms([fault], EngineState.KEY_ON)
        assert _battery_v(symptoms) < 3.0
        assert symptoms.node_potentials["starter_stud"] < 3.0

    def test_dead_battery_no_click(self) -> None:
        fault = _fault(Component.BATTERY, FailureMode.DEAD)
        symptoms = resolve_symptoms([fault], EngineState.CRANKING)
        assert symptoms.crank_behavior == CrankBehavior.NO_CLICK

    def test_dead_battery_ground_path_innocent(self) -> None:
        fault = _fault(Component.BATTERY, FailureMode.DEAD)
        symptoms = resolve_symptoms([fault], EngineState.CRANKING)
        assert _ground_drop(symptoms) <= 0.05


class TestCorrodedGround:
    """medium_corroded_ground calibration: the drop test localizes the fault."""

    SCENARIO_ID = "medium_corroded_ground"

    def _symptoms(self, engine_state: EngineState):
        scenario = get_scenario(self.SCENARIO_ID)
        return resolve_symptoms([scenario.root_cause], engine_state)

    def test_large_ground_drop_under_crank_only(self) -> None:
        assert _ground_drop(self._symptoms(EngineState.CRANKING)) >= 2.5
        for state in (EngineState.KEY_OFF, EngineState.KEY_ON):
            assert _ground_drop(self._symptoms(state)) <= 0.1

    def test_battery_holds_under_crank(self) -> None:
        # Reduced cranking current: the battery is innocent and reads strong.
        assert _battery_v(self._symptoms(EngineState.CRANKING)) >= 11.3

    def test_positive_feed_stays_small_under_crank(self) -> None:
        assert _feed_drop(self._symptoms(EngineState.CRANKING)) <= 0.5

    def test_fault_uniquely_localizable_to_ground_path(self) -> None:
        cranking = self._symptoms(EngineState.CRANKING)
        assert _ground_drop(cranking) >= _feed_drop(cranking) + 1.0

    def test_slow_crank(self) -> None:
        assert self._symptoms(EngineState.CRANKING).crank_behavior == (
            CrankBehavior.SLOW_CRANK
        )

    def test_cranking_battery_sags_below_resting(self) -> None:
        resting = _battery_v(self._symptoms(EngineState.KEY_ON))
        cranking = _battery_v(self._symptoms(EngineState.CRANKING))
        assert cranking < resting


class TestCrankPrecedence:
    def test_no_click_beats_slow_crank(self) -> None:
        faults = [
            _fault(Component.BATTERY, FailureMode.WEAK),
            _fault(Component.STARTER_RELAY, FailureMode.STUCK_OPEN),
        ]
        symptoms = resolve_symptoms(faults, EngineState.CRANKING)
        assert symptoms.crank_behavior == CrankBehavior.NO_CLICK


class TestRedHerringScenarioCalibration:
    """medium_ground_red_herring_battery: tempting at rest, innocent under crank."""

    SCENARIO_ID = "medium_ground_red_herring_battery"

    def _symptoms(self, engine_state: EngineState):
        scenario = get_scenario(self.SCENARIO_ID)
        return resolve_symptoms(
            [scenario.root_cause],
            engine_state,
            red_herring_readings=scenario.red_herring_voltages,
        )

    def test_resting_bait_reads_marginal(self) -> None:
        for state in (EngineState.KEY_OFF, EngineState.KEY_ON):
            assert abs(_battery_v(self._symptoms(state)) - 11.8) <= 0.05

    def test_resting_supply_path_uniformly_suppressed(self) -> None:
        for state in (EngineState.KEY_OFF, EngineState.KEY_ON):
            symptoms = self._symptoms(state)
            batt = symptoms.node_potentials["battery_positive"]
            stud = symptoms.node_potentials["starter_stud"]
            assert abs(batt - stud) <= 0.3

    def test_innocent_battery_holds_under_crank(self) -> None:
        # Bait, not a co-fault: reads ~11.8 at rest, holds >= ~11.3 cranking.
        assert _battery_v(self._symptoms(EngineState.CRANKING)) >= 11.3

    def test_ground_drop_is_the_tell_under_crank_only(self) -> None:
        assert _ground_drop(self._symptoms(EngineState.CRANKING)) >= 2.5
        for state in (EngineState.KEY_OFF, EngineState.KEY_ON):
            assert _ground_drop(self._symptoms(state)) <= 0.1

    def test_fault_uniquely_localizable_to_ground_path(self) -> None:
        cranking = self._symptoms(EngineState.CRANKING)
        assert _feed_drop(cranking) <= 0.5
        assert _ground_drop(cranking) >= _feed_drop(cranking) + 1.0

    def test_cranking_below_resting_invariant(self) -> None:
        resting = self._symptoms(EngineState.KEY_ON)
        cranking = self._symptoms(EngineState.CRANKING)
        assert _battery_v(cranking) < _battery_v(resting)
        assert cranking.node_potentials["starter_stud"] < (
            resting.node_potentials["starter_stud"]
        )

    def test_red_herring_does_not_change_crank_behavior(self) -> None:
        scenario = get_scenario(self.SCENARIO_ID)
        without = resolve_symptoms([scenario.root_cause], EngineState.CRANKING)
        with_herring = self._symptoms(EngineState.CRANKING)
        assert with_herring.crank_behavior == without.crank_behavior


class TestRestingMonotonicityAllScenarios:
    """At rest, no downstream node may exceed an upstream node (all scenarios)."""

    EPSILON = 0.001

    @pytest.mark.parametrize("scenario_id", list_scenarios())
    @pytest.mark.parametrize(
        "engine_state", [EngineState.KEY_OFF, EngineState.KEY_ON]
    )
    def test_battery_ge_starter_stud_at_rest(
        self, scenario_id: str, engine_state: EngineState
    ) -> None:
        scenario = get_scenario(scenario_id)
        symptoms = resolve_symptoms(
            [scenario.root_cause],
            engine_state,
            red_herring_readings=scenario.red_herring_voltages or None,
        )
        batt = symptoms.node_potentials["battery_positive"]
        assert symptoms.node_potentials["starter_stud"] <= batt + self.EPSILON
        assert symptoms.node_potentials["alt_output"] <= batt + self.EPSILON


class TestReplaceSemanticsViaPropagation:
    """After part swap, fault removed — symptoms return toward nominal."""

    def test_no_faults_match_nominal_crank(self) -> None:
        symptoms = resolve_symptoms([], EngineState.CRANKING)
        nominal = NOMINAL_NODES[EngineState.CRANKING]["battery_positive"]
        assert symptoms.node_potentials["battery_positive"] == nominal
