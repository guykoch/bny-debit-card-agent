"""
Checks the skill split stays consistent with the tools. Run:

    python -m tests.test_skills

The risk with one skill per action is drift: a skill pointing at a tool that
does not exist, two skills claiming the same tool, an action with no skill, or
a trigger that silently shadows another skill. These tests catch all four.
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DCA_STORE"] = "memory"      # never touch the shared demo database

from core import schemas, skills

PASS, FAIL = [], []


def check(label, condition, detail=""):
    (PASS if condition else FAIL).append(label)
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{(' - ' + detail) if detail else ''}")


def run():
    schemas.load()
    every = {t["name"]: t for t in schemas.all_tools()}
    write_tools = {n for n, t in every.items() if t.get("access") == "write"}
    all_skills = skills.all_skills()

    print("\n1. Every skill is wired to a real tool")
    for sk in all_skills:
        check(f"{sk.name} -> {sk.tool}", sk.tool in every)
        check(f"{sk.name} lookups exist", all(l in every for l in sk.lookups))

    print("\n2. Exactly one skill per action, and no action left out")
    claimed = [sk.tool for sk in all_skills]
    check("no tool claimed twice", len(claimed) == len(set(claimed)))
    check("every write tool has a skill", write_tools == set(claimed),
          f"missing: {sorted(write_tools - set(claimed))}")

    print("\n3. A skill may only reach its own action")
    for sk in all_skills:
        others = write_tools - {sk.tool}
        names = {t["name"] for t in skills.tools_for(sk)}
        check(f"{sk.name} cannot reach another action", not (names & others))

    print("\n4. Routing, including the cross-action case")
    cases = [
        ("Lock Jane Miller's card", "lock-card"),
        ("unlock the card please", "unlock-card"),
        ("her card is cracked, send a new one", "replace-card"),
        ("close it permanently", "close-card"),
        ("Jane lost her wallet, lock the card", "report-lost-stolen"),
        ("Sarah is going to Portugal next month", "travel-notice"),
    ]
    for text, expected in cases:
        got = skills.route(text)
        check(f"{text[:38]!r:42} -> {expected}", got and got.name == expected,
              f"got {got.name if got else None}")
    check("an unrelated sentence routes nowhere", skills.route("what is her balance?") is None)

    print("\n5. The shared rules reach every skill")
    for sk in all_skills:
        prompt = skills.system_prompt(sk)
        check(f"{sk.name} prompt carries the shared rules",
              "Never guess" in prompt and "Finding the client" in prompt)
        check(f"{sk.name} prompt carries its own body", sk.body[:40] in prompt)

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
