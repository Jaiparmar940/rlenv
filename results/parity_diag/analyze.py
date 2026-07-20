"""Structural diff of the captured wire-level contexts (inspect vs ors)."""

from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent


def load(scenario: str, pipeline: str) -> dict:
    return json.loads(
        (OUT / f"{scenario}__{pipeline}.json").read_text(encoding="utf-8")
    )


def show_diff(label: str, a: str, b: str) -> None:
    if a == b:
        print(f"  {label}: BYTE-IDENTICAL")
        return
    print(f"  {label}: DIFFERS")
    for line in list(difflib.unified_diff(
        a.splitlines(), b.splitlines(), "inspect", "ors", lineterm="", n=1
    ))[:40]:
        print(f"    {line}")


def main() -> None:
    scenario = sys.argv[1]
    ins = load(scenario, "inspect")
    ors = load(scenario, "ors")
    ireq = ins["calls"][0]["request"]
    oreq = ors["calls"][0]["request"]

    print(f"=== {scenario}: first API request ===")
    print(f"[scores] inspect={ins['score']:.1f} ors={ors['score']:.1f}")
    print(f"[api calls] inspect={ins['n_api_calls']} ors={ors['n_api_calls']}")

    print("\n--- top-level request keys ---")
    print(f"  inspect: {sorted(ireq)}")
    print(f"  ors:     {sorted(oreq)}")
    for key in ("model", "max_tokens", "temperature"):
        print(f"  {key}: inspect={ireq.get(key)!r} ors={oreq.get(key)!r}")

    print("\n--- system prompt ---")
    isys, osys = ireq.get("system"), oreq.get("system")
    print(f"  inspect type: {type(isys).__name__}; ors type: {type(osys).__name__}")
    itext = (isys if isinstance(isys, str)
             else "\n".join(b.get("text", "") for b in isys) if isys else "")
    otext = (osys if isinstance(osys, str)
             else "\n".join(b.get("text", "") for b in osys) if osys else "")
    show_diff("system text", itext, otext)
    if not isinstance(isys, str) and isys:
        extras = [{k: v for k, v in b.items() if k != "text"} for b in isys]
        print(f"  inspect system block extras: {extras}")

    print("\n--- first user message ---")
    imsg, omsg = ireq["messages"][0], oreq["messages"][0]
    print(f"  roles: inspect={imsg['role']} ors={omsg['role']}")
    ic, oc = imsg["content"], omsg["content"]
    itext = ic if isinstance(ic, str) else "\n".join(
        b.get("text", "") for b in ic)
    otext = oc if isinstance(oc, str) else "\n".join(
        b.get("text", "") for b in oc)
    print(f"  content shape: inspect={type(ic).__name__} ors={type(oc).__name__}")
    show_diff("user text", itext, otext)

    print("\n--- tools ---")
    itools = {t["name"]: t for t in ireq["tools"]}
    otools = {t["name"]: t for t in oreq["tools"]}
    print(f"  names inspect: {sorted(itools)}")
    print(f"  names ors:     {sorted(otools)}")
    only_i, only_o = set(itools) - set(otools), set(otools) - set(itools)
    if only_i or only_o:
        print(f"  ONLY-IN-INSPECT: {sorted(only_i)}  ONLY-IN-ORS: {sorted(only_o)}")
    for name in sorted(set(itools) & set(otools)):
        it, ot = itools[name], otools[name]
        show_diff(f"tool[{name}].description",
                  it.get("description", ""), ot.get("description", ""))
        ischema = json.dumps(it.get("input_schema"), indent=1, sort_keys=True)
        oschema = json.dumps(ot.get("input_schema"), indent=1, sort_keys=True)
        show_diff(f"tool[{name}].input_schema", ischema, oschema)
        extra_keys = (set(it) | set(ot)) - {"name", "description", "input_schema"}
        if extra_keys:
            print(f"  tool[{name}] extra keys: "
                  f"inspect={ {k: it.get(k) for k in extra_keys} } "
                  f"ors={ {k: ot.get(k) for k in extra_keys} }")

    print("\n--- tool-result framing (first tool_result in each) ---")
    def first_tool_result(calls):
        for call in calls:
            for msg in call["request"]["messages"]:
                content = msg.get("content")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            return json.dumps(
                                {k: (v if k != "content" else v)
                                 for k, v in block.items()},
                                indent=1, sort_keys=True)
        return None
    itr, otr = first_tool_result(ins["calls"]), first_tool_result(ors["calls"])
    show_diff("tool_result block", itr or "(none)", otr or "(none)")

    print("\n--- assistant plain-message handling ---")
    def nudges(calls):
        count = 0
        for call in calls:
            for msg in call["request"]["messages"]:
                content = msg.get("content")
                text = content if isinstance(content, str) else "".join(
                    b.get("text", "") for b in content
                    if isinstance(b, dict) and b.get("type") == "text")
                if msg["role"] == "user" and "best judgement" in text:
                    count += 1
        return count
    last = ins["calls"][-1]["request"]["messages"]
    print(f"  inspect continue-nudges present in final context: "
          f"{nudges([ins['calls'][-1]])}")
    print(f"  ors finished_via: {ors.get('finished_via')}")
    print(f"  final message counts: inspect={ins['n_messages_final']} "
          f"ors={ors['n_messages_final']}")


if __name__ == "__main__":
    main()
