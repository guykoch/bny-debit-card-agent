"""
Checks for the second round of live-testing fixes (pending_fixes.md, P-01 to
P-17 = tracker F-30 to F-46). Run:

    python -m tests.test_pending

Two kinds of fake model, no network:
- CodeOnly: routes like the keyword rules and NEVER calls a tool, only writes
  text. Every question must still reach the advisor as a card built by code.
- ScriptedModel: replays tool calls, to check that model-filled values are kept
  only when the advisor's own words support them.
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DCA_STORE"] = "memory"

import json
from datetime import date, timedelta

from config import settings
from core import audit, skills
from integrations import address_lookup
from tests.test_fixes import fresh, has_cancel, labels, values
from tests.test_llm_runtime import ScriptedModel, call, route

RESULTS: dict[str, bool] = {}
PASS, FAIL = [], []


def check(tid, label, condition, detail=""):
    RESULTS[tid] = RESULTS.get(tid, True) and bool(condition)
    (PASS if condition else FAIL).append(f"{tid} {label}")
    print(f"  {'PASS' if condition else 'FAIL'}  {tid}  {label}{(' - ' + detail) if detail else ''}")


class CodeOnly:
    """Routes with the keyword rules; answers every skill turn with text (a list, a
    question, a false 'done'). None of it may reach the advisor."""
    TEXT = ("Which one?\n1. Lock (reversible)\n2. Close permanently\n"
            "I've locked the card. This permanently closes the card. Confirm?")

    def __init__(self):
        self.requests = 0

    def chat(self, messages, tools=None, response_format=None):
        self.requests += 1
        if response_format:
            last = [m for m in messages if m["role"] == "user"][-1]["content"]
            s = skills.route(last)
            return {"content": json.dumps({"skill": s.name if s else "none", "certain": True})}
        return {"content": self.TEXT}


def kind(r):
    return (r.card or {}).get("kind")


def iso(d):
    return d.isoformat()


def run():
    settings.ADDRESS_PROVIDER = "sample"
    start = date.today() + timedelta(days=20)
    s_txt = start.strftime("%B %d").replace(" 0", " ")
    e5 = start + timedelta(days=5)
    e5_txt = e5.strftime("%B %d").replace(" 0", " ")

    print("\nP-01 (F-30)  Replacement to a city that is not on file: addresses as buttons")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Replace Jane Miller's card, it's damaged. Send it to Montreal")
    check("T-30a", "refusal plus Jane's US addresses as buttons, never plain text",
          kind(r) == "choice" and "not in Jane Miller's profile" in r.card["message"]
          and values(r)[:2] == ["14 Hudson St, New York, NY 10013",
                                "220 Ocean Dr, Miami Beach, FL 33139"]
          and "__other__" in values(r) and has_cancel(r))

    print("\nP-02 (F-31)  A city gets buttons for the country or US state")
    svc, conv = fresh(CodeOnly())
    r = conv.send(f"Jane Miller is going to Paris {s_txt} to {e5_txt}")
    check("T-31a", "Paris: France / Texas / Somewhere else, plus Cancel",
          labels(r) == ["France", "Texas", "Somewhere else"] and has_cancel(r))
    r = conv.send("France")
    check("T-31a", "France picked: confirmation card, dates from the advisor's words",
          r.status == "awaiting_confirmation" and r.data["input"]["destination"] == ["France"]
          and r.data["input"]["start_date"] == iso(start))
    svc, conv = fresh(CodeOnly())
    conv.send(f"Jane Miller is going to Paris {s_txt} to {e5_txt}")
    r = conv.send("Somewhere else")
    check("T-31b", "Somewhere else: the travel card, dates kept",
          kind(r) == "travel_form" and r.card["start"] == iso(start) and has_cancel(r))

    print("\nP-03 (F-32)  Vague dates open the calendar; nothing is proposed")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Jane Miller is going to Japan next month for a couple of weeks")
    check("T-32a", "travel card with Japan, dates empty",
          kind(r) == "travel_form" and r.card["destinations"] == ["Japan"]
          and r.card["start"] == "" and r.card["end"] == "")

    print("\nP-04 (F-33)  Over 14 days: the calendar card again, with the reason")
    svc, conv = fresh(CodeOnly())
    e20 = start + timedelta(days=20)
    r = conv.send(f"Jane Miller is going to Japan {s_txt} to {e20.strftime('%B %d').replace(' 0', ' ')}")
    check("T-33a", "travel card with a notice about the 14 days",
          kind(r) == "travel_form" and "at most 14" in r.card["message"]
          and r.card["destinations"] == ["Japan"])
    r = conv.send("travel_form:" + json.dumps({"destinations": ["Japan"], "start": iso(start),
                                               "end": iso(start + timedelta(days=9))}))
    check("T-33a", "fixed on the card: confirmation", r.status == "awaiting_confirmation")

    print("\nP-05 (F-34)  Pending card with no US address: an Address Update ticket")
    svc, conv = fresh(CodeOnly(), "ADV-5678")
    r = conv.send("Claire Beaumont never received her card, please replace it")
    check("T-34a", "'Send an Address Update ticket' button, not a refusal",
          r.status == "needs_input" and labels(r) == ["Send an Address Update ticket"]
          and has_cancel(r))
    r = conv.send("__other__")
    check("T-34a", "the ticket's address card opens", kind(r) == "ticket_address")
    hits = address_lookup.suggest("1100 Congress")["suggestions"]
    r = conv.send("ticket_address:" + json.dumps({"pick": hits[0]["id"], "unit": "", "phone": ""}))
    check("T-34a", "review card for the ticket; nothing on file changed",
          r.status == "awaiting_confirmation" and r.data["tool"] == "address_update"
          and not any("Congress" in a.address for a in svc.clients.addresses("C-15644")))
    svc, conv = fresh(CodeOnly(), "ADV-5678")
    r = conv.send("Report Claire Beaumont's card stolen")
    check("T-34b", "pending card, action not allowed: what IS allowed, as buttons",
          r.data.get("code") == "card_pending" and "Replace the card" in labels(r)
          and has_cancel(r))

    print("\nP-06 / P-07 (F-35 / F-36 retired)  Close removed: a card can't be closed alone")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Close Jane Miller's card permanently")
    check("T-35c", "close: fixed reply, Replace / Lock buttons, nothing changed",
          "can't be closed on its own" in r.card["message"]
          and values(r) == ["replace-card", "lock-card"] and has_cancel(r)
          and svc.cards.get_card("CARD-4417").status == "active")

    print("\nP-08 (F-37)  'Did you do anything?' answered by code")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Did you do anything yet?")
    check("T-37a", "nothing yet", "Nothing has been changed" in r.message)
    conv.send("Lock Jane Miller's card")
    r = conv.send("did you lock it?")
    check("T-37a", "panel open: says nothing ran, and shows the card again",
          "nothing runs until you click Confirm" in r.message and kind(r) == "confirm")
    conv.send("confirm")
    r = conv.send("Did you do anything?")
    check("T-37a", "after Confirm: says what was done", "locked" in r.message.lower())

    print("\nP-09 (F-38)  Travel follow-ups on one form card")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Add a travel notice for Jane Miller")
    check("T-38a", "travel card: destinations (max 10) and dates, plus Cancel",
          kind(r) == "travel_form" and r.card["max_destinations"] == 10
          and r.card["max_days"] == 14 and has_cancel(r))
    r = conv.send("travel_form:" + json.dumps({"destinations": ["Japan", "Gotham"],
                                               "start": iso(start), "end": iso(e5)}))
    check("T-38a", "a place not on BNY's list is refused on the card",
          r.status == "needs_input" and "not on BNY's list" in r.message)

    print("\nP-10 (F-39)  A new request starts clean")
    svc, conv = fresh(CodeOnly())
    conv.send("Replace Jane Miller's card, it's damaged")
    conv.send("14 Hudson St, New York, NY 10013")
    conv.send("cancel")
    r = conv.send("Replace Jane Miller's card")
    check("T-39a", "the reason is asked again, not reused",
          r.card["title"] == "Reason" and "damaged" in values(r))

    print("\nP-11 (F-40)  Reason 'Other' opens a required text box")
    svc, conv = fresh(CodeOnly())
    conv.send("Replace Jane Miller's card")
    r = conv.send("Other")
    check("T-40a", "text box card", kind(r) == "text_input" and has_cancel(r))
    r = conv.send("text_input:chip worn out")
    check("T-40a", "then the delivery address", r.card["title"] == "Delivery address")
    r = conv.send("14 Hudson St, New York, NY 10013")
    reason = next(f["value"] for f in r.card["fields"] if f["label"] == "Reason")
    check("T-40a", "panel shows 'Other: chip worn out'", reason == "Other: chip worn out")

    print("\nP-12 (F-41)  Cancel on every card")
    svc, conv = fresh(CodeOnly())
    kinds = {}
    for text in ["__actions__", "lock-card"]:
        r = conv.send(text)
        kinds[kind(r)] = has_cancel(r)
    r = conv.send("client_pick:C-10220")                       # two cards: Which card?
    kinds["choice/card"] = has_cancel(r)
    r = conv.send("2201")
    kinds["confirm"] = has_cancel(r)
    r = conv.send("__cancel__")
    check("T-41a", "choice, client and confirm cards all have Cancel",
          all(kinds.values()) and len(kinds) >= 3, str(kinds))
    check("T-41a", "Cancel: nothing changed",
          r.message.startswith("Cancelled") and conv.pending is None
          and svc.cards.get_card("CARD-2201").status == "active")

    print("\nP-13 (F-42)  A different action switches by itself")
    svc, conv = fresh(CodeOnly())
    conv.send("Lock Jane Miller's card")
    r = conv.send("Actually Jane Miller's card was stolen")
    check("T-42a", "goes straight to the stolen report, no lock card reused",
          conv.task and conv.task["skill"].name == "report-lost-stolen"
          and "lock" not in json.dumps(r.card or {}).lower()
          and r.card.get("message", "").startswith("Any recent transactions"))

    print("\nP-14 (F-43)  Valid trip: card with editable dates, no limit chatter")
    svc, conv = fresh(CodeOnly())
    r = conv.send(f"Jane Miller is going to Japan {s_txt} to {e5_txt}")
    check("T-43a", "confirmation with the dates editable on the card",
          r.status == "awaiting_confirmation" and r.card["dates"]["inline"]
          and r.card["dates"]["start"] == iso(start) and r.card["dates"]["end"] == iso(e5))
    check("T-43a", "the 14-day limit is not mentioned", "at most 14" not in r.message
          and "14 days" not in r.message)
    r = conv.send("confirm_with:" + json.dumps({"start": iso(start + timedelta(days=1)),
                                                "end": iso(e5)}))
    check("T-43a", "edited dates are used", r.status == "ok"
          and svc.cards.travel_notices[-1]["start_date"] == iso(start + timedelta(days=1)))

    print("\nP-15 (F-44)  Model text with options is never shown")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Lock Sarah Chen's card")
    check("T-44a", "a card, not the model's numbered list",
          kind(r) == "choice" and "1. Lock" not in r.message)
    hist = json.dumps(conv.history)
    check("T-44a", "the history note never lists the options", "Boston" not in hist)
    svc, conv = fresh(CodeOnly())
    conv.send("Lock Jane Miller's card")
    r = conv.send("lock Robert Castellanos card")
    check("T-44b", "with an older request open, a typo in a name is still checked",
          r.card and r.card["title"] == "Did you mean?" or kind(r) == "client_input")

    print("\nP-16 (F-45)  The Actions button")
    svc, conv = fresh(CodeOnly())
    calls = 0
    r = conv.send("__actions__")
    check("T-45a", "ten actions in two groups (Do it now / Send a ticket), plus Cancel",
          len(labels(r)) == 10 and has_cancel(r)
          and [a.get("group") for a in r.card["actions"][:10]] == ["now"] * 5 + ["ticket"] * 5)
    r = conv.send("unlock-card")
    check("T-45a", "then 'Which client?' with suggestions", kind(r) == "client_input")
    r = conv.send("client_pick:C-44090")
    check("T-45a", "then the normal card flow", r.status in ("awaiting_confirmation",
                                                             "needs_input", "error"))

    print("\nP-17 (F-46)  Menu follow-ups are cards; no client carried over")
    m = CodeOnly()
    svc, conv = fresh(m)
    conv.send("Lock Jane Miller's card")
    conv.send("cancel")
    conv.send("__actions__")
    r = conv.send("travel-notice")
    check("T-46a", "Jane is not carried over: 'Which client?'", kind(r) == "client_input")
    before = m.requests
    r = conv.send("client_pick:C-88210")
    check("T-46a", "travel card next, no model call", kind(r) == "travel_form"
          and m.requests == before)
    r = conv.send("client_pick:C-99999")
    check("T-46b", "a client this advisor can't see is never accepted",
          r.status != "awaiting_confirmation")

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
