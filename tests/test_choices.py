"""
Checks the follow-up answers to "which card?" and "which client?". Run:

    python -m tests.test_choices

When a client has two cards, or two clients share a name, the chat lists the
options and asks. Clicking a button sends the option's id. Typing must work
too: the option number, the last four digits, or the label. Anything that
matches no option, or more than one, must be asked again — never guessed.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DCA_STORE"] = "memory"      # never touch the shared demo database

from config.settings import build_services
from core.models import Session
from interfaces.local_runtime import Conversation

PASS, FAIL = [], []


def check(label, condition, detail=""):
    (PASS if condition else FAIL).append(label)
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{(' - ' + detail) if detail else ''}")


def talk(*turns):
    conv = Conversation(build_services(), Session(advisor_id="ADV-1234"))
    replies = [conv.send(t) for t in turns]
    return conv, replies


def card_picked(conv):
    p = conv.pending or {}
    return p.get("input", {}).get("card_id") if p.get("awaiting_confirm") else None


def run():
    lock = "Lock Robert Castellano's card"

    print("\n1. A client with two cards: the chat asks which")
    _, (r,) = talk(lock)
    check("asks 'Which card?'", r.status == "needs_input" and r.message.startswith("Which card?"))
    check("lists both cards", "2201" in r.message and "2202" in r.message)

    print("\n2. Every way of answering picks the right card")
    for answer, expected in [("CARD-2202", "CARD-2202"),        # button click
                             ("2", "CARD-2202"),                # option number
                             ("2202", "CARD-2202"),             # last four
                             ("the one ending 2201", "CARD-2201"),
                             ("...2201 (active)", "CARD-2201")]: # label
        conv, rs = talk(lock, answer)
        check(f"{answer!r:24} -> {expected}",
              rs[-1].status == "awaiting_confirmation" and card_picked(conv) == expected,
              f"got {rs[-1].status}: {rs[-1].message.splitlines()[0]}")

    print("\n3. An answer that matches nothing is asked again, not guessed")
    for answer in ["9999", "the new one", "3", "2201 or 2202"]:
        conv, rs = talk(lock, answer)
        check(f"{answer!r:24} -> asked again",
              rs[-1].status == "needs_input" and "pick from the list" in rs[-1].message
              and not (conv.pending or {}).get("awaiting_confirm"))
    conv, rs = talk(lock, "9999", "1")
    check("after a bad answer, a good one still works", card_picked(conv) == "CARD-2201")

    print("\n4. Nothing runs before Confirm")
    conv, rs = talk(lock, "2202")
    card = conv.services.cards.get_card("CARD-2202")
    check("card still active after picking it", card.status == "active")
    conv.send("yes")
    check("locked only after 'yes'", conv.services.cards.get_card("CARD-2202").status == "locked")

    print("\n5. Two clients with one name: typed answers work there too")
    for answer in ["1", "4409", "Sarah Chen - acct ...4409"]:
        _, rs = talk("Unlock Sarah Chen card", answer)
        check(f"{answer!r:28} -> Sarah Chen ...4409",
              rs[-1].status == "awaiting_confirmation",
              f"got {rs[-1].status}: {rs[-1].message.splitlines()[0]}")
    _, rs = talk("Unlock Sarah Chen card", "0000")
    check("'0000' -> asked again", "pick from the list" in rs[-1].message)

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
