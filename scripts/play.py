#!/usr/bin/env python3
"""Human-in-the-loop CLI: play the agent manually against a scenario."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from typing import Any

from nostart.domain.scenarios import list_scenarios
from nostart.tools import ToolSession


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def _help_text() -> str:
    return """
Commands:
  complaint              Show customer complaint
  status                 Show cumulative cost and episode state
  scan_dtcs              Scan for DTCs
  read_pid <pid>         PIDs: battery_voltage, alt_output_v, rpm, can_status
  measure_voltage <point_a> <point_b> <engine_state>
                         Reads V(point_a) - V(point_b). Nodes: battery_positive,
                         battery_negative, engine_block, starter_stud, alt_output, chassis
                         States: key_off, key_on, cranking
                         e.g. measure_voltage battery_positive battery_negative cranking
                              measure_voltage battery_negative engine_block cranking  (ground drop)
  visual_inspect <area>  Areas: battery, ground_strap, starter_relay, starter_motor,
                         alternator, fusible_link, ignition_switch, ecu_can_node
  replace_part <component>
  attempt_start          Try to start the engine
  finish <diagnosis>     End episode with your root-cause claim
  help                   Show this help
  quit                   Exit
""".strip()


def _dispatch(session: ToolSession, line: str) -> bool:
    """Returns False if the user wants to quit."""
    parts = shlex.split(line.strip())
    if not parts:
        return True

    cmd = parts[0].lower()
    args = parts[1:]

    try:
        if cmd in ("quit", "exit", "q"):
            return False
        if cmd == "help":
            print(_help_text())
        elif cmd == "complaint":
            print(session.get_complaint())
        elif cmd == "status":
            _print_json(session.get_status().model_dump())
        elif cmd == "scan_dtcs":
            _print_json(session.scan_dtcs())
        elif cmd == "read_pid":
            if len(args) != 1:
                print("Usage: read_pid <pid>")
            else:
                _print_json(session.read_pid(args[0]))
        elif cmd == "measure_voltage":
            if len(args) != 3:
                print("Usage: measure_voltage <point_a> <point_b> <engine_state>")
            else:
                _print_json(session.measure_voltage(args[0], args[1], args[2]))
        elif cmd == "visual_inspect":
            if len(args) != 1:
                print("Usage: visual_inspect <area>")
            else:
                print(session.visual_inspect(args[0]))
        elif cmd == "replace_part":
            if len(args) != 1:
                print("Usage: replace_part <component>")
            else:
                _print_json(session.replace_part(args[0]))
        elif cmd == "attempt_start":
            _print_json(session.attempt_start())
        elif cmd == "finish":
            if len(args) < 1:
                print("Usage: finish <diagnosis>")
            else:
                diagnosis = " ".join(args)
                status = session.finish(diagnosis)
                _print_json(status.model_dump())
                print("\nEpisode finished.")
        else:
            print(f"Unknown command: {cmd}. Type 'help' for commands.")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Play no-start-env manually")
    parser.add_argument(
        "--scenario",
        default="easy_dead_battery",
        help="Scenario ID (use --list to see options)",
    )
    parser.add_argument("--list", action="store_true", help="List available scenarios")
    args = parser.parse_args()

    if args.list:
        for sid in list_scenarios():
            print(sid)
        return

    session = ToolSession(args.scenario)
    print(f"Scenario: {args.scenario}")
    print(f"Complaint: {session.get_complaint()}")
    print("Type 'help' for commands.\n")

    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not _dispatch(session, line):
            break


if __name__ == "__main__":
    main()
