"""Running engine state: charging physics after a verified start.

Regression for the framed-alternator trap (2026-07-12, fable easy e1
uncoached, scored 32.2): the model replaced the dead battery, started the
car, checked charging like a real tech — and read_pid returned engine-off
voltages (~12.4 V), so it concluded the alternator was dead. There must be
a state in which a healthy alternator shows charging voltage.
"""

from __future__ import annotations

import pytest

from nostart.domain.components import Component, FailureMode, InjectedFault
from nostart.domain.propagation import EngineState, resolve_symptoms
from nostart.tools import ToolSession

BATT = ("battery_positive", "battery_negative")


def _started_easy_session() -> ToolSession:
    session = ToolSession("easy_dead_battery")
    session.measure_voltage(*BATT, "key_off")
    session.replace_part("battery")
    assert session.attempt_start()["result"] == "starts"
    return session


class TestRunningGate:
    def test_running_requires_started_engine(self) -> None:
        session = ToolSession("easy_dead_battery")
        with pytest.raises(ValueError, match="not running"):
            session.measure_voltage(*BATT, "running")

    def test_failed_start_does_not_enable_running(self) -> None:
        session = ToolSession("easy_dead_battery")
        assert session.attempt_start()["result"] == "no_click"
        with pytest.raises(ValueError, match="not running"):
            session.measure_voltage(*BATT, "running")

    def test_other_key_state_shuts_engine_off(self) -> None:
        session = _started_easy_session()
        session.measure_voltage(*BATT, "running")  # fine while running
        session.measure_voltage(*BATT, "key_off")  # tech shuts it off
        with pytest.raises(ValueError, match="not running"):
            session.measure_voltage(*BATT, "running")

    def test_replace_part_shuts_engine_off(self) -> None:
        session = _started_easy_session()
        session.replace_part("ground_strap")
        with pytest.raises(ValueError, match="not running"):
            session.measure_voltage(*BATT, "running")


class TestChargingPhysics:
    def test_healthy_charging_voltages(self) -> None:
        session = _started_easy_session()
        batt = session.measure_voltage(*BATT, "running")["volts"]
        assert 13.8 <= batt <= 14.6  # charging, not resting
        alt = session.measure_voltage(
            "alt_output", "battery_negative", "running"
        )["volts"]
        assert 13.8 <= alt <= 14.6
        # Alternator is the source while running: alt_output >= battery.
        assert alt >= batt - 0.15  # noise slack

    def test_scan_tool_reflects_running_engine(self) -> None:
        # The exact trap: after a successful start, alt_output_v must show
        # charging voltage, and rpm must show idle — not key-on values.
        session = _started_easy_session()
        alt = session.read_pid("alt_output_v", "running")
        assert alt["value"] >= 13.8
        assert alt["engine_state"] == "running"
        rpm = session.read_pid("rpm", "running")
        assert 600 <= rpm["value"] <= 800
        assert rpm["engine_state"] == "running"

    def test_scan_tool_key_on_when_not_running(self) -> None:
        # Engine off: alt post reads battery resting voltage — honest
        # physics, and the payload SAYS it is a key_on read so it cannot
        # masquerade as a failed alternator at idle. Tach reads 0.
        session = ToolSession("easy_dead_battery")
        session.replace_part("battery")
        alt = session.read_pid("alt_output_v", "key_on")
        assert alt["value"] <= 12.7
        assert alt["engine_state"] == "key_on"
        rpm = session.read_pid("rpm", "key_on")
        assert rpm["value"] == 0.0
        assert rpm["engine_state"] == "key_on"

    def test_red_herring_bait_is_resting_only(self) -> None:
        # Strap fixed, ORIGINAL marginal battery still installed: running
        # shows normal charging (invariant 3 — red herrings never touch a
        # non-resting state), while key_off still reads the bait.
        session = ToolSession("medium_ground_red_herring_battery")
        session.measure_voltage(*BATT, "cranking")
        session.replace_part("ground_strap")
        assert session.attempt_start()["result"] == "starts"
        running = session.measure_voltage(*BATT, "running")["volts"]
        assert running >= 13.8
        resting = session.measure_voltage(*BATT, "key_off")["volts"]
        assert abs(resting - 11.8) <= 0.1


class TestAlternatorFaultsWhileRunning:
    def test_no_output_shows_battery_voltage_no_rise(self) -> None:
        fault = InjectedFault(
            component=Component.ALTERNATOR, mode=FailureMode.NO_OUTPUT
        )
        state = resolve_symptoms([fault], EngineState.RUNNING)
        alt = state.potential_difference("alt_output", "battery_negative")
        batt = state.potential_difference(*BATT)
        assert alt <= 12.6  # no charge rise above resting
        assert abs(alt - batt) <= 0.2  # post tied to the rail, not 0 V

    def test_diode_failure_charges_low(self) -> None:
        fault = InjectedFault(
            component=Component.ALTERNATOR, mode=FailureMode.DIODE_FAILURE
        )
        state = resolve_symptoms([fault], EngineState.RUNNING)
        alt = state.potential_difference("alt_output", "battery_negative")
        assert 12.8 <= alt <= 13.6  # weak charging, between resting and healthy
