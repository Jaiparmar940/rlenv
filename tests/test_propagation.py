"""Physical-consistency tests for fault → symptom propagation."""

from __future__ import annotations

import pytest

from nostart.domain.components import Component, FailureMode, InjectedFault
from nostart.domain.propagation import (
    CrankBehavior,
    EngineState,
    NOMINAL_VOLTAGES,
    VoltagePoint,
    resolve_symptoms,
)
from nostart.domain.scenarios import get_scenario, list_scenarios


def _fault(component: Component, mode: FailureMode, **severity: float) -> InjectedFault:
    return InjectedFault(component=component, mode=mode, severity=severity)


class TestNominalBaseline:
    def test_healthy_crank_starts(self) -> None:
        symptoms = resolve_symptoms([], EngineState.CRANKING)
        assert symptoms.crank_behavior == CrankBehavior.STARTS

    def test_battery_voltage_exceeds_starter_stud_when_healthy(self) -> None:
        symptoms = resolve_symptoms([], EngineState.CRANKING)
        batt = symptoms.voltages["battery_terminals"]
        stud = symptoms.voltages["starter_stud"]
        assert batt >= stud


class TestDeadBattery:
    def test_dead_battery_low_voltage_all_points(self) -> None:
        fault = _fault(Component.BATTERY, FailureMode.DEAD)
        symptoms = resolve_symptoms([fault], EngineState.KEY_ON)
        assert symptoms.voltages["battery_terminals"] < 3.0
        assert symptoms.voltages["starter_stud"] < 3.0

    def test_dead_battery_no_click(self) -> None:
        fault = _fault(Component.BATTERY, FailureMode.DEAD)
        symptoms = resolve_symptoms([fault], EngineState.CRANKING)
        assert symptoms.crank_behavior == CrankBehavior.NO_CLICK


class TestCorrodedGround:
    def test_voltage_drop_at_starter_stud_under_crank(self) -> None:
        fault = _fault(Component.GROUND_STRAP, FailureMode.CORRODED, added_resistance_ohms=0.8)
        symptoms = resolve_symptoms([fault], EngineState.CRANKING)
        batt = symptoms.voltages["battery_terminals"]
        stud = symptoms.voltages["starter_stud"]
        assert batt - stud >= 1.5

    def test_slow_crank_with_corroded_ground(self) -> None:
        fault = _fault(Component.GROUND_STRAP, FailureMode.CORRODED)
        symptoms = resolve_symptoms([fault], EngineState.CRANKING)
        assert symptoms.crank_behavior == CrankBehavior.SLOW_CRANK

    def test_key_on_drop_smaller_than_cranking(self) -> None:
        fault = _fault(Component.GROUND_STRAP, FailureMode.CORRODED)
        key_on = resolve_symptoms([fault], EngineState.KEY_ON)
        cranking = resolve_symptoms([fault], EngineState.CRANKING)
        key_on_drop = (
            key_on.voltages["battery_terminals"] - key_on.voltages["starter_stud"]
        )
        crank_drop = (
            cranking.voltages["battery_terminals"] - cranking.voltages["starter_stud"]
        )
        assert crank_drop > key_on_drop


class TestCrankPrecedence:
    def test_no_click_beats_slow_crank(self) -> None:
        faults = [
            _fault(Component.BATTERY, FailureMode.WEAK),
            _fault(Component.STARTER_RELAY, FailureMode.STUCK_OPEN),
        ]
        symptoms = resolve_symptoms(faults, EngineState.CRANKING)
        assert symptoms.crank_behavior == CrankBehavior.NO_CLICK


class TestRedHerring:
    def test_red_herring_overrides_resting_voltage_only(self) -> None:
        fault = _fault(Component.GROUND_STRAP, FailureMode.CORRODED)
        key_on = resolve_symptoms(
            [fault],
            EngineState.KEY_ON,
            red_herring_readings={"battery_terminals": 11.8},
        )
        cranking = resolve_symptoms(
            [fault],
            EngineState.CRANKING,
            red_herring_readings={"battery_terminals": 11.8},
        )
        assert key_on.voltages["battery_terminals"] == 11.8
        assert cranking.voltages["battery_terminals"] < 11.8

    def test_cranking_below_resting_for_same_point(self) -> None:
        fault = _fault(
            Component.GROUND_STRAP, FailureMode.CORRODED, added_resistance_ohms=1.0
        )
        herring = {"battery_terminals": 11.8}
        resting = resolve_symptoms(
            [fault], EngineState.KEY_ON, red_herring_readings=herring
        )
        cranking = resolve_symptoms(
            [fault], EngineState.CRANKING, red_herring_readings=herring
        )
        assert cranking.voltages["battery_terminals"] < resting.voltages["battery_terminals"]
        assert cranking.voltages["starter_stud"] < resting.voltages["starter_stud"]

    def test_stud_drops_more_than_battery_under_crank(self) -> None:
        fault = _fault(
            Component.GROUND_STRAP, FailureMode.CORRODED, added_resistance_ohms=1.0
        )
        herring = {"battery_terminals": 11.8}
        resting = resolve_symptoms(
            [fault], EngineState.KEY_ON, red_herring_readings=herring
        )
        cranking = resolve_symptoms(
            [fault], EngineState.CRANKING, red_herring_readings=herring
        )
        batt_drop = (
            resting.voltages["battery_terminals"] - cranking.voltages["battery_terminals"]
        )
        stud_drop = resting.voltages["starter_stud"] - cranking.voltages["starter_stud"]
        assert stud_drop > batt_drop

    def test_red_herring_does_not_change_crank_behavior(self) -> None:
        fault = _fault(Component.GROUND_STRAP, FailureMode.CORRODED)
        without = resolve_symptoms([fault], EngineState.CRANKING)
        with_herring = resolve_symptoms(
            [fault],
            EngineState.CRANKING,
            red_herring_readings={"battery_terminals": 11.8},
        )
        assert with_herring.crank_behavior == without.crank_behavior


class TestRedHerringScenarioCalibration:
    """medium_ground_red_herring_battery: tempting at rest, innocent under crank."""

    SCENARIO_ID = "medium_ground_red_herring_battery"

    def _symptoms(self, engine_state: EngineState):
        scenario = get_scenario(self.SCENARIO_ID)
        return resolve_symptoms(
            [scenario.root_cause],
            engine_state,
            red_herring_readings=scenario.red_herring_voltages,
            red_herring_cranking_battery=scenario.red_herring_cranking_battery,
        )

    def test_resting_bait_unchanged(self) -> None:
        key_on = self._symptoms(EngineState.KEY_ON)
        assert key_on.voltages["battery_terminals"] == 11.8

    def test_innocent_battery_holds_under_crank(self) -> None:
        cranking = self._symptoms(EngineState.CRANKING)
        assert cranking.voltages["battery_terminals"] >= 9.8
        assert cranking.voltages["battery_terminals"] >= 10.3
        assert cranking.voltages["battery_terminals"] <= 10.8

    def test_stud_sags_hard_under_crank(self) -> None:
        cranking = self._symptoms(EngineState.CRANKING)
        assert cranking.voltages["starter_stud"] <= 7.5

    def test_key_off_supply_path_uniformly_suppressed(self) -> None:
        key_off = self._symptoms(EngineState.KEY_OFF)
        batt = key_off.voltages["battery_terminals"]
        stud = key_off.voltages["starter_stud"]
        assert abs(batt - 11.8) <= 0.15
        assert abs(stud - 11.8) <= 0.15
        assert abs(batt - stud) <= 0.15

    def test_drop_test_delta_is_diagnostic(self) -> None:
        cranking = self._symptoms(EngineState.CRANKING)
        delta = (
            cranking.voltages["battery_terminals"] - cranking.voltages["starter_stud"]
        )
        assert delta >= 2.0

    def test_cranking_below_resting_invariants(self) -> None:
        resting = self._symptoms(EngineState.KEY_ON)
        cranking = self._symptoms(EngineState.CRANKING)
        assert cranking.voltages["battery_terminals"] < resting.voltages["battery_terminals"]
        assert cranking.voltages["starter_stud"] < resting.voltages["starter_stud"]
        batt_drop = (
            resting.voltages["battery_terminals"] - cranking.voltages["battery_terminals"]
        )
        stud_drop = resting.voltages["starter_stud"] - cranking.voltages["starter_stud"]
        assert stud_drop > batt_drop


class TestRestingMonotonicityAllScenarios:
    """At rest, no downstream point may exceed an upstream point (all scenarios)."""

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
            red_herring_cranking_battery=scenario.red_herring_cranking_battery,
        )
        batt = symptoms.voltages["battery_terminals"]
        stud = symptoms.voltages["starter_stud"]
        alt = symptoms.voltages["alt_output"]
        assert stud <= batt + self.EPSILON
        assert alt <= batt + self.EPSILON


class TestReplaceSemanticsViaPropagation:
    """After part swap, fault removed — symptoms return toward nominal."""

    def test_no_faults_match_nominal_crank(self) -> None:
        symptoms = resolve_symptoms([], EngineState.CRANKING)
        nominal = NOMINAL_VOLTAGES[EngineState.CRANKING][VoltagePoint.BATTERY_TERMINALS]
        assert symptoms.voltages["battery_terminals"] == nominal
