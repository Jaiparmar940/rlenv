#!/usr/bin/env python3
"""Standalone physical sanity checker for the two-point ``measure_voltage``.

Self-contained: imports ONLY the world/measurement layer (``nostart.tools``),
never the grader, tests, or Inspect. It computes what the physics should be,
asserts it, prints per-scenario tables, and exits non-zero on any failure — so a
green run is meaningful on its own.

Usage:
    python scripts/sanity_check.py                 # all three scenarios
    python scripts/sanity_check.py --scenario <id> # one scenario
"""

from __future__ import annotations

import argparse
import sys

from nostart.tools import ToolSession

STATES = ("key_off", "key_on", "cranking")
SCENARIOS = (
    "easy_dead_battery",
    "medium_corroded_ground",
    "medium_ground_red_herring_battery",
)

# Tolerances (volts).
NOISE_TOL = 0.1     # single noisy reading vs expected physics
PAIR_TOL = 0.12     # comparing two independent noisy readings (2 noise draws)
MONO_EPS = 0.1      # resting monotonicity slack
LARGE_DROP = 2.5    # a "large" ground-path drop under load
FEED_SMALL = 0.5    # positive-feed drop must stay small for localization
BATTERY_HOLDS = 11.3  # innocent battery floor under crank in ground-fault scenarios


class Failure:
    def __init__(
        self, scenario: str, state: str, desc: str, expected: str, actual: str
    ) -> None:
        self.scenario = scenario
        self.state = state
        self.desc = desc
        self.expected = expected
        self.actual = actual

    def __str__(self) -> str:
        return (
            f"  [{self.scenario} | {self.state}] {self.desc}\n"
            f"      expected: {self.expected}\n"
            f"      actual:   {self.actual}"
        )


def measure(scenario: str, a: str, b: str, state: str) -> float:
    """Fresh session per measurement → deterministic, order-independent noise."""
    session = ToolSession(scenario)
    return session.measure_voltage(a, b, state)["volts"]


def potential(scenario: str, node: str, state: str) -> float:
    """Node potential relative to the reference (battery_negative)."""
    return measure(scenario, node, "battery_negative", state)


# --- Invariant groups. Each returns (group_name, list[Failure]). ---


def check_universal(scenario: str) -> tuple[str, list[Failure]]:
    fails: list[Failure] = []

    # Invalid node name must raise.
    try:
        measure(scenario, "banana", "battery_negative", "key_off")
        fails.append(
            Failure(scenario, "key_off", "invalid node raises",
                    "ValueError", "no exception raised")
        )
    except ValueError:
        pass

    antisym_pairs = [
        ("battery_positive", "battery_negative"),
        ("battery_positive", "starter_stud"),
        ("battery_negative", "engine_block"),
    ]
    self_nodes = ["battery_positive", "engine_block", "starter_stud"]

    for state in STATES:
        # Sign antisymmetry: V(a,b) ≈ −V(b,a).
        for a, b in antisym_pairs:
            ab = measure(scenario, a, b, state)
            ba = measure(scenario, b, a, state)
            if abs(ab + ba) > PAIR_TOL:
                fails.append(
                    Failure(scenario, state, f"antisymmetry {a}/{b}",
                            "V(a,b) ≈ -V(b,a)", f"{ab:+.2f} vs {ba:+.2f}")
                )
        # Self-measure ≈ 0.
        for x in self_nodes:
            v = measure(scenario, x, x, state)
            if abs(v) > NOISE_TOL:
                fails.append(
                    Failure(scenario, state, f"self-measure {x}",
                            "≈ 0.00", f"{v:+.2f}")
                )

    # Resting monotonicity: no downstream node exceeds an upstream node.
    for state in ("key_off", "key_on"):
        batt = potential(scenario, "battery_positive", state)
        stud = potential(scenario, "starter_stud", state)
        alt = potential(scenario, "alt_output", state)
        if stud > batt + MONO_EPS:
            fails.append(
                Failure(scenario, state, "monotonicity battery_positive ≥ starter_stud",
                        f"≤ {batt:.2f}", f"stud={stud:.2f}")
            )
        if alt > batt + MONO_EPS:
            fails.append(
                Failure(scenario, state, "monotonicity battery_positive ≥ alt_output",
                        f"≤ {batt:.2f}", f"alt={alt:.2f}")
            )

    # Load sag: battery voltage at cranking never higher than at key_off.
    batt_off = measure(scenario, "battery_positive", "battery_negative", "key_off")
    batt_crank = measure(scenario, "battery_positive", "battery_negative", "cranking")
    if batt_crank > batt_off + NOISE_TOL:
        fails.append(
            Failure(scenario, "cranking", "load sag (cranking ≤ key_off)",
                    f"≤ {batt_off:.2f}", f"cranking={batt_crank:.2f}")
        )

    return "universal", fails


def _abs_ground_drop(scenario: str, state: str) -> float:
    return abs(measure(scenario, "battery_negative", "engine_block", state))


def check_easy_dead_battery(scenario: str) -> tuple[str, list[Failure]]:
    fails: list[Failure] = []
    for state in STATES:
        batt = measure(scenario, "battery_positive", "battery_negative", state)
        if abs(batt - 2.1) > 0.2:
            fails.append(
                Failure(scenario, state, "battery ≈ 2.1 V (dead)",
                        "≈ 2.1", f"{batt:.2f}")
            )
        gnd = _abs_ground_drop(scenario, state)
        if gnd > 0.2:
            fails.append(
                Failure(scenario, state, "ground drop ≈ 0 (fault is battery)",
                        "|drop| ≤ 0.2", f"{gnd:.2f}")
            )
    return "scenario:easy_dead_battery", fails


def check_corroded_ground(scenario: str) -> tuple[str, list[Failure]]:
    fails: list[Failure] = []

    batt_off = measure(scenario, "battery_positive", "battery_negative", "key_off")
    if abs(batt_off - 12.6) > 0.2:
        fails.append(
            Failure(scenario, "key_off", "healthy battery at rest ≈ 12.6 V",
                    "≈ 12.6", f"{batt_off:.2f}")
        )
    batt_crank = measure(scenario, "battery_positive", "battery_negative", "cranking")
    if batt_crank < BATTERY_HOLDS - NOISE_TOL:
        fails.append(
            Failure(scenario, "cranking", "battery holds under load (innocent)",
                    f"≥ {BATTERY_HOLDS}", f"{batt_crank:.2f}")
        )

    for state in ("key_off", "key_on"):
        gnd = _abs_ground_drop(scenario, state)
        if gnd > 0.2:
            fails.append(
                Failure(scenario, state, "ground drop ≈ 0 at rest",
                        "|drop| ≤ 0.2", f"{gnd:.2f}")
            )
    gnd_crank = _abs_ground_drop(scenario, "cranking")
    if gnd_crank < LARGE_DROP:
        fails.append(
            Failure(scenario, "cranking", "ground drop LARGE under load (the tell)",
                    f"|drop| ≥ {LARGE_DROP}", f"{gnd_crank:.2f}")
        )

    return "scenario:medium_corroded_ground", fails


def check_red_herring(scenario: str) -> tuple[str, list[Failure]]:
    fails: list[Failure] = []

    for state in ("key_off", "key_on"):
        batt = measure(scenario, "battery_positive", "battery_negative", state)
        if abs(batt - 11.8) > 0.2:
            fails.append(
                Failure(scenario, state, "resting battery suppressed ≈ 11.8 V (bait)",
                        "≈ 11.8", f"{batt:.2f}")
            )
        # starter_stud ≈ battery at rest (uniform suppression, not a stud fault).
        stud = potential(scenario, "starter_stud", state)
        if abs(batt - stud) > 0.3:
            fails.append(
                Failure(scenario, state, "starter_stud ≈ battery at rest (uniform bait)",
                        f"≈ {batt:.2f}", f"stud={stud:.2f}")
            )

    batt_crank = measure(scenario, "battery_positive", "battery_negative", "cranking")
    if batt_crank < BATTERY_HOLDS - NOISE_TOL:
        fails.append(
            Failure(scenario, "cranking", "battery HOLDS under load (innocent)",
                    f"≥ {BATTERY_HOLDS}", f"{batt_crank:.2f}")
        )
    gnd_crank = _abs_ground_drop(scenario, "cranking")
    if gnd_crank < LARGE_DROP:
        fails.append(
            Failure(scenario, "cranking", "ground drop LARGE under load (the tell)",
                    f"|drop| ≥ {LARGE_DROP}", f"{gnd_crank:.2f}")
        )

    return "scenario:medium_ground_red_herring_battery", fails


def check_localization(scenario: str) -> tuple[str, list[Failure]]:
    """The large drop must appear ONLY across the ground path, not elsewhere."""
    fails: list[Failure] = []
    state = "cranking"

    ground_drop = _abs_ground_drop(scenario, state)
    feed_drop = abs(measure(scenario, "battery_positive", "starter_stud", state))

    if ground_drop < LARGE_DROP:
        fails.append(
            Failure(scenario, state, "ground path shows the large drop",
                    f"|drop| ≥ {LARGE_DROP}", f"{ground_drop:.2f}")
        )
    if feed_drop > FEED_SMALL:
        fails.append(
            Failure(scenario, state,
                    "positive feed drop stays small (fault not on feed)",
                    f"|drop| ≤ {FEED_SMALL}", f"{feed_drop:.2f}")
        )
    if ground_drop < feed_drop + 1.0:
        fails.append(
            Failure(scenario, state,
                    "fault uniquely localizable to ground junction",
                    f"ground ≫ feed (by ≥ 1.0 V)",
                    f"ground={ground_drop:.2f}, feed={feed_drop:.2f}")
        )

    return "localization", fails


# Root-cause component per scenario, used to reach the running state.
_ROOT_COMPONENT = {
    "easy_dead_battery": "battery",
    "medium_corroded_ground": "ground_strap",
    "medium_ground_red_herring_battery": "ground_strap",
}

CHARGING_MIN = 13.8   # healthy charging floor at battery terminals
CHARGING_MAX = 14.6   # regulator ceiling


def check_running_charging(scenario: str) -> tuple[str, list[Failure]]:
    """Post-repair, a healthy alternator must show charging voltage.

    Guards the framed-alternator trap: a model that fixes the car and then
    checks the charging system must see ~14 V, not engine-off readings.
    Also asserts the running state is gated (unreachable pre-repair).
    """
    fails: list[Failure] = []

    session = ToolSession(scenario)
    try:
        session.measure_voltage("battery_positive", "battery_negative", "running")
        fails.append(
            Failure(scenario, "running", "running gated before repair",
                    "ValueError (engine not running)", "measurement returned")
        )
    except ValueError:
        pass

    session.replace_part(_ROOT_COMPONENT[scenario])
    result = session.attempt_start()["result"]
    if result != "starts":
        fails.append(
            Failure(scenario, "running", "engine starts after root repair",
                    "starts", result)
        )
        return "running-charging", fails

    batt = session.measure_voltage(
        "battery_positive", "battery_negative", "running"
    )["volts"]
    alt = session.measure_voltage(
        "alt_output", "battery_negative", "running"
    )["volts"]
    if not (CHARGING_MIN <= batt <= CHARGING_MAX):
        fails.append(
            Failure(scenario, "running", "battery sees charging voltage",
                    f"{CHARGING_MIN}–{CHARGING_MAX}", f"{batt:.2f}")
        )
    if alt < batt - PAIR_TOL:
        fails.append(
            Failure(scenario, "running", "alternator is the source (alt ≥ batt)",
                    f"alt ≥ {batt:.2f} − {PAIR_TOL}", f"{alt:.2f}")
        )
    pid = session.read_pid("alt_output_v")["value"]
    if pid < CHARGING_MIN:
        fails.append(
            Failure(scenario, "running", "scan tool reflects running engine",
                    f"alt_output_v ≥ {CHARGING_MIN}", f"{pid:.2f}")
        )
    return "running-charging", fails


SCENARIO_CHECKS = {
    "easy_dead_battery": [check_easy_dead_battery, check_running_charging],
    "medium_corroded_ground": [
        check_corroded_ground, check_localization, check_running_charging,
    ],
    "medium_ground_red_herring_battery": [
        check_red_herring, check_localization, check_running_charging,
    ],
}


def print_table(scenario: str) -> None:
    print(f"\n=== {scenario} ===")
    print(f"  {'state':9} | {'battery_v':>10} | {'ground_drop':>12} | {'stud_feed':>10}")
    print("  " + "-" * 50)
    for state in STATES:
        batt = measure(scenario, "battery_positive", "battery_negative", state)
        gnd = measure(scenario, "battery_negative", "engine_block", state)
        feed = measure(scenario, "battery_positive", "starter_stud", state)
        print(f"  {state:9} | {batt:10.2f} | {gnd:12.2f} | {feed:10.2f}")


def run_scenario(scenario: str) -> list[Failure]:
    print_table(scenario)
    groups = [check_universal(scenario)]
    for check in SCENARIO_CHECKS.get(scenario, []):
        groups.append(check(scenario))

    all_fails: list[Failure] = []
    print()
    for name, fails in groups:
        status = "PASS" if not fails else f"FAIL ({len(fails)})"
        print(f"  [{status}] {name}")
        all_fails.extend(fails)
    return all_fails


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent physics sanity checker")
    parser.add_argument("--scenario", choices=SCENARIOS, help="Run one scenario")
    args = parser.parse_args()

    scenarios = [args.scenario] if args.scenario else list(SCENARIOS)

    all_fails: list[Failure] = []
    for scenario in scenarios:
        all_fails.extend(run_scenario(scenario))

    print("\n" + "=" * 60)
    if not all_fails:
        print("ALL CHECKS PASSED")
        return 0

    print(f"{len(all_fails)} CHECKS FAILED\n")
    for f in all_fails:
        print(f)
    return 1


if __name__ == "__main__":
    sys.exit(main())
