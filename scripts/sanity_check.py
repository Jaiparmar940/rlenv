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
    # Hard-tier preview — physics PENDING HUMAN SIGN-OFF.
    "hard_intermittent_ecu_can",
    "hard_compound_battery_and_ground",
)

# Tolerances (volts).
NOISE_TOL = 0.1     # single noisy reading vs expected physics
PAIR_TOL = 0.12     # comparing two independent noisy readings (2 noise draws)
MONO_EPS = 0.1      # resting monotonicity slack
LARGE_DROP = 2.5    # a "large" ground-path drop under load
FEED_SMALL = 0.5    # positive-feed drop must stay small for localization
# Innocent battery floor under crank in ground-fault scenarios. Derived from
# the series-consistent recovery (recovery/drop = sag/OCV = 2.8/12.6): the
# 1.1/1.2 Ω scenarios put the battery at ~10.41/10.47 V cranking — well above
# the 9.6 V load-test condemnation line, so the battery still reads innocent.
BATTERY_HOLDS = 10.3

# --- Hard-tier thresholds (all TODO(VERIFY); see PENDING_HUMAN_PHYSICS_SIGNOFF.md) ---
# A corroded strap milder than the single-fault scenarios (0.7 Ω vs 1.1/1.2 Ω)
# still has to be unmistakable: a healthy ground drops < 0.2 V under crank.
COMPOUND_GROUND_DROP = 1.5
# A GENUINELY weak battery must fail a load test. Shop rule of thumb: a 12 V
# battery holding < 9.6 V under cranking load is condemned.
LOAD_TEST_FAIL = 9.6
# ...and it must read clearly worse at rest than the innocent red-herring
# battery (11.8 V), so the two are not confusable.
COMPOUND_BATTERY_REST = 11.5


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


def check_compound(scenario: str) -> tuple[str, list[Failure]]:
    """Compound: a GENUINELY weak battery AND a corroded ground, together.

    What a tech must see (and what these assertions pin):
      1. Battery is really bad: ~11.0 V at rest (worse than the 11.8 V
         red-herring bait) and it FAILS a load test — < 9.6 V cranking, far
         below the ~10.4 V an innocent battery holds in the ground scenarios.
      2. Ground is really bad: >= 1.5 V dropped across the strap under crank
         (a healthy strap drops < 0.2 V), and ~0 V at rest.
      3. Still localizable: the positive feed stays clean, so the drop belongs
         to the ground junction, not the supply side.
      4. Neither repair alone fixes the car — replacing only the battery or
         only the strap still slow-cranks; both are required to start.
    """
    fails: list[Failure] = []

    for state in ("key_off", "key_on"):
        batt = measure(scenario, "battery_positive", "battery_negative", state)
        if batt > COMPOUND_BATTERY_REST:
            fails.append(
                Failure(scenario, state,
                        "battery is genuinely weak at rest (worse than the "
                        "11.8 V red-herring bait)",
                        f"<= {COMPOUND_BATTERY_REST}", f"{batt:.2f}")
            )
        gnd = _abs_ground_drop(scenario, state)
        if gnd > 0.2:
            fails.append(
                Failure(scenario, state, "ground drop ~0 at rest (load-only fault)",
                        "|drop| <= 0.2", f"{gnd:.2f}")
            )

    batt_crank = measure(scenario, "battery_positive", "battery_negative", "cranking")
    if batt_crank > LOAD_TEST_FAIL:
        fails.append(
            Failure(scenario, "cranking",
                    "battery FAILS the load test (it is a real co-fault, not bait)",
                    f"<= {LOAD_TEST_FAIL}", f"{batt_crank:.2f}")
        )
    if batt_crank >= BATTERY_HOLDS:
        fails.append(
            Failure(scenario, "cranking",
                    "battery sags well below the innocent-battery floor",
                    f"< {BATTERY_HOLDS}", f"{batt_crank:.2f}")
        )

    gnd_crank = _abs_ground_drop(scenario, "cranking")
    feed_crank = abs(measure(scenario, "battery_positive", "starter_stud", "cranking"))
    if gnd_crank < COMPOUND_GROUND_DROP:
        fails.append(
            Failure(scenario, "cranking",
                    "ground-path drop present under load (the second tell)",
                    f"|drop| >= {COMPOUND_GROUND_DROP}", f"{gnd_crank:.2f}")
        )
    if feed_crank > FEED_SMALL:
        fails.append(
            Failure(scenario, "cranking", "positive feed stays clean",
                    f"|drop| <= {FEED_SMALL}", f"{feed_crank:.2f}")
        )
    if gnd_crank < feed_crank + 1.0:
        fails.append(
            Failure(scenario, "cranking", "ground fault localizable vs the feed",
                    "ground >= feed + 1.0 V",
                    f"ground={gnd_crank:.2f}, feed={feed_crank:.2f}")
        )

    # Neither repair alone resolves the car: both faults are real.
    for partial in (["battery"], ["ground_strap"]):
        session = ToolSession(scenario)
        for component in partial:
            session.replace_part(component)
        result = session.attempt_start()["result"]
        if result == "starts":
            fails.append(
                Failure(scenario, "cranking",
                        f"replacing only {partial[0]} must NOT fix the car",
                        "not 'starts'", result)
            )
    session = ToolSession(scenario)
    session.replace_part("ground_strap")
    session.replace_part("battery")
    result = session.attempt_start()["result"]
    if result != "starts":
        fails.append(
            Failure(scenario, "cranking", "both repairs together fix the car",
                    "starts", result)
        )

    return "scenario:compound", fails


def check_intermittent(scenario: str) -> tuple[str, list[Failure]]:
    """Intermittent ECU/CAN node: present on only ~35% of probes.

    What a tech must see (and what these assertions pin):
      1. The car sometimes cranks-no-start and sometimes starts fine — the
         complaint is real, but one good crank proves nothing.
      2. A clean scan does NOT exonerate: some scans return no codes at all,
         others return U0100. Same for the CAN status PID.
      3. Nothing electrical moves: every voltage reads nominal in every state,
         so a pure drop-test workflow cannot find this fault.
      4. Manifestation is deterministic in the seed: identical runs produce
         identical crank sequences (no wall-clock randomness).
      5. Replacing the ECU node fixes it: 12 consecutive clean starts.
    """
    fails: list[Failure] = []

    def crank_sequence(n: int) -> list[str]:
        session = ToolSession(scenario)
        return [session.attempt_start()["result"] for _ in range(n)]

    seq = crank_sequence(20)
    misfires = [r for r in seq if r != "starts"]
    starts = [r for r in seq if r == "starts"]
    if not misfires:
        fails.append(
            Failure(scenario, "cranking", "fault manifests on some cranks",
                    ">= 1 non-start in 20", "0")
        )
    if not starts:
        fails.append(
            Failure(scenario, "cranking",
                    "fault is INTERMITTENT (car also starts fine sometimes)",
                    ">= 1 start in 20", "0")
        )
    if misfires and set(misfires) != {"crank_no_start"}:
        fails.append(
            Failure(scenario, "cranking", "misfire signature is crank_no_start",
                    "{'crank_no_start'}", str(set(misfires)))
        )
    rate = len(misfires) / len(seq)
    if not 0.15 <= rate <= 0.60:
        fails.append(
            Failure(scenario, "cranking",
                    "manifest rate near the 0.35 severity parameter",
                    "0.15-0.60 over 20 cranks", f"{rate:.2f}")
        )

    # Determinism: same seed, same sequence. No wall clock anywhere.
    if crank_sequence(20) != seq:
        fails.append(
            Failure(scenario, "cranking", "identical runs -> identical observations",
                    "same crank sequence", "sequences differ")
        )

    # A single clean reading must not exonerate the ECU.
    session = ToolSession(scenario)
    scans = [len(session.scan_dtcs()) for _ in range(10)]
    if not (any(s == 0 for s in scans) and any(s > 0 for s in scans)):
        fails.append(
            Failure(scenario, "key_on",
                    "scans are sometimes clean and sometimes show codes",
                    "both empty and non-empty scans in 10",
                    str(scans))
        )
    session = ToolSession(scenario)
    can = [session.read_pid("can_status")["value"] for _ in range(10)]
    if not (any(c == "ok" for c in can) and any(c != "ok" for c in can)):
        fails.append(
            Failure(scenario, "key_on", "CAN status PID is also intermittent",
                    "both 'ok' and degraded readings in 10", str(can))
        )

    # No electrical signature: voltages are nominal everywhere.
    nominal = {"key_off": 12.6, "key_on": 12.4, "cranking": 9.8}
    for state, expected in nominal.items():
        batt = measure(scenario, "battery_positive", "battery_negative", state)
        if abs(batt - expected) > NOISE_TOL:
            fails.append(
                Failure(scenario, state, "battery reads NOMINAL (fault is not electrical)",
                        f"~ {expected}", f"{batt:.2f}")
            )
        gnd = _abs_ground_drop(scenario, state)
        if gnd > 0.2:
            fails.append(
                Failure(scenario, state, "ground path innocent",
                        "|drop| <= 0.2", f"{gnd:.2f}")
            )

    # The repair actually works.
    session = ToolSession(scenario)
    session.replace_part("ecu_can_node")
    after = [session.attempt_start()["result"] for _ in range(12)]
    if set(after) != {"starts"}:
        fails.append(
            Failure(scenario, "cranking", "replacing the ECU node fixes it for good",
                    "12/12 'starts'", str(sorted(set(after))))
        )

    return "scenario:intermittent", fails


# Components that must be replaced to resolve each scenario, in order. Used to
# reach the running state (a compound scenario needs BOTH repairs to start).
_REPAIR_COMPONENTS = {
    "easy_dead_battery": ["battery"],
    "medium_corroded_ground": ["ground_strap"],
    "medium_ground_red_herring_battery": ["ground_strap"],
    "hard_intermittent_ecu_can": ["ecu_can_node"],
    "hard_compound_battery_and_ground": ["ground_strap", "battery"],
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

    for component in _REPAIR_COMPONENTS[scenario]:
        session.replace_part(component)
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
    "hard_intermittent_ecu_can": [check_intermittent, check_running_charging],
    "hard_compound_battery_and_ground": [check_compound, check_running_charging],
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
