"""
Checks for the third round of live-testing fixes (pending_fixes_2.md, P2-01 to
P2-05 = tracker F-47 to F-51). Run:

    python -m tests.test_pending2

CodeOnly never calls a tool (code must drive everything); ScriptedModel replays
tool calls. No network.
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DCA_STORE"] = "memory"

import json

from config import settings
from tests.test_fixes import fresh, has_cancel, labels, values
from tests.test_llm_runtime import ScriptedModel, call, route
from tests.test_pending import CodeOnly

RESULTS: dict[str, bool] = {}
PASS, FAIL = [], []


def check(tid, label, condition, detail=""):
    RESULTS[tid] = RESULTS.get(tid, True) and bool(condition)
    (PASS if condition else FAIL).append(f"{tid} {label}")
    print(f"  {'PASS' if condition else 'FAIL'}  {tid}  {label}{(' - ' + detail) if detail else ''}")


def kind(r):
    return (r.card or {}).get("kind")


def run():
    settings.ADDRESS_PROVIDER = "sample"
    trip = "Michael Donnelly is travelling to Japan from November 20 to December 15 2026"

    print("\nP2-01 (F-47)  A named client who can't be found is said on the card")
    _, conv = fresh(CodeOnly(), "ADV-1234")
    r = conv.send(trip)
    check("T-47a", "'No client named Michael Donnelly was found.' above the field",
          kind(r) == "client_input" and r.card.get("notice") == "No client named Michael "
          "Donnelly was found." and has_cancel(r))
    m = ScriptedModel(route("travel-notice"), call("find_client", query="Michael Donnelly"))
    _, conv = fresh(m, "ADV-1234")
    r = conv.send(trip)
    check("T-47a", "same when the AI looked him up (another advisor's client: same words)",
          kind(r) == "client_input" and "Michael Donnelly was found" in r.card.get("notice", ""))
    _, conv = fresh(CodeOnly(), "ADV-9012")
    r = conv.send(trip)
    check("T-47a", "his own advisor: found, then the travel card (over 14 days)",
          kind(r) == "travel_form" and "at most 14" in r.card["message"])
    _, conv = fresh(CodeOnly())
    conv.send("__actions__")
    r = conv.send("lock-card")
    check("T-47b", "no name given: the plain field, no 'not found' line, one heading",
          kind(r) == "client_input" and not r.card.get("notice")
          and r.card["message"] != r.card["title"])

    print("\nP2-02 (F-48)  'she' right after a request: one-tap check for that client")
    _, conv = fresh(CodeOnly(), "ADV-5678")
    conv.send("Claire Beaumont's card was stolen")
    r = conv.send("So she never actually got the card and needs a replacement")
    check("T-48a", "'Is this for Claire Beaumont (...)?' Yes / Another client / Cancel",
          kind(r) == "choice" and r.card["message"].startswith("Is this for Claire Beaumont")
          and labels(r) == ["Yes, Claire Beaumont", "Another client"] and has_cancel(r))
    r = conv.send("Yes, Claire Beaumont")
    check("T-48a", "Yes: the replacement goes on (no US address -> add one)",
          labels(r) == ["Add a US delivery address"])
    _, conv = fresh(CodeOnly(), "ADV-5678")
    conv.send("Claire Beaumont's card was stolen")
    conv.send("So she never actually got the card and needs a replacement")
    r = conv.send("Another client")
    check("T-48b", "Another client: the empty client field", kind(r) == "client_input")
    _, conv = fresh(CodeOnly())
    conv.send("Lock Jane Miller's card")
    conv.send("cancel")
    conv.send("__actions__")
    r = conv.send("replace-card")
    check("T-48c", "from the Actions menu: no client offered (starts clean)",
          kind(r) == "client_input")

    print("\nP2-03 (F-49)  Apartment line after picking an address (page; server check)")
    from integrations import address_lookup
    _, conv = fresh(CodeOnly())
    conv.send("Jane Miller moved, change the address in her profile")
    conv.send("Home")
    pid = address_lookup.suggest("1 Bryant Park")["suggestions"][0]["id"]
    r = conv.send(f"address_pick:{pid}|Apt 12C")
    check("T-49a", "the unit sent with 'Use this address' is on the confirm card",
          r.status == "awaiting_confirmation" and "Apt 12C" in r.data["input"]["new_address"])

    print("\nP2-04 (F-50)  Part of a name: check the client first")
    _, conv = fresh(CodeOnly())
    r = conv.send("Jane needs a new card")
    check("T-50a", "'Is this for Jane Miller (New York, born 1979)?' Yes / Another client",
          kind(r) == "choice" and r.card["message"] == "Is this for Jane Miller (New York, "
          "born 1979)?" and values(r) == ["C-88210", "__another__"])
    r = conv.send("Yes, Jane Miller")
    check("T-50a", "Yes: then the Reason buttons", r.card["title"] == "Reason")
    m = ScriptedModel(route("lock-card"), call("find_client", query="Jane Miller"))
    _, conv = fresh(m)
    r = conv.send("Lock Jane's card")
    check("T-50b", "also when the AI expanded 'Jane' to Jane Miller",
          kind(r) == "choice" and r.card["message"].startswith("Is this for Jane Miller"))
    _, conv = fresh(CodeOnly())
    r = conv.send("Lock Jane Miller's card")
    check("T-50c", "full name written: no extra check", r.status == "awaiting_confirmation")

    print("\nP2-05 (F-51)  An address typed in the message is explained on the address card")
    _, conv = fresh(ScriptedModel(route("update-address"), {"role": "assistant", "content": "ok"}))
    r = conv.send("Add 10 Downing St, London as Jane Miller's delivery address")
    check("T-51a", "outside the US: says so above the field",
          kind(r) == "address_input" and r.card.get("notice", "").startswith(
              "10 Downing St, London is outside the US") and not r.card.get("prefill"))
    _, conv = fresh(ScriptedModel(route("update-address"), {"role": "assistant", "content": "ok"}))
    r = conv.send("Add 1100 Congress Ave, Austin as Jane Miller's delivery address")
    check("T-51b", "US address: put in the field to pick from the suggestions",
          kind(r) == "address_input" and r.card.get("prefill") == "1100 Congress Ave, Austin"
          and "Pick the address" in r.card.get("info", ""))

    print("\nP2-06 (F-52)  Capitals and small typos in the client's name")
    _, conv = fresh(CodeOnly())
    r = conv.send("LOCK JANE MILLER'S CARD")
    check("T-52a", "any capitalisation of the full name: found, no extra question",
          r.status == "awaiting_confirmation" and r.data["input"]["client_id"] == "C-88210")
    for typed in ("Lock Jnae Millre's card", "lock jane millar card", "Lock Jane Mlller's card"):
        _, conv = fresh(CodeOnly())
        r = conv.send(typed)
        check("T-52b", f"typo '{typed}': 'Did you mean Jane Miller (New York, born 1979)?'",
              kind(r) == "choice" and r.card["title"] == "Did you mean?"
              and r.card["message"] == "Did you mean Jane Miller (New York, born 1979)?"
              and values(r) == ["C-88210", "__another__"] and has_cancel(r))
    r = conv.send("Yes, Jane Miller")
    check("T-52b", "Yes: carries on with Jane Miller", r.status == "awaiting_confirmation"
          and r.data["input"]["client_id"] == "C-88210")
    m = ScriptedModel(route("lock-card"), call("find_client", query="robert castelano"))
    _, conv = fresh(m)
    r = conv.send("lock robert castelano card")
    check("T-52c", "also when the AI looked up the misspelt name",
          r.card["message"].startswith("Did you mean Robert Castellano"))
    m = ScriptedModel(route("close-card"), call("find_client", query="margaret osei-bonshu"))
    _, conv = fresh(m)
    r = conv.send("cloase margaret osei-bonshu's card permanently, she is switching banks")
    check("T-52c", "hyphenated name with a typo, lower case",
          r.card["message"] == "Did you mean Margaret Osei-Bonsu (Short Hills, born 1958)?")
    r = conv.send("Yes, Margaret Osei-Bonsu")
    check("T-52c", "Yes: then the permission refusal (no close permission)",
          r.data.get("code") == "not_entitled")
    _, conv = fresh(CodeOnly())
    r = conv.send("lock margaret osei-bonshu card")
    check("T-52c", "same when code reads the name", r.card["message"].startswith(
        "Did you mean Margaret Osei-Bonsu"))
    _, conv = fresh(CodeOnly())
    r = conv.send("lock sara chen card")
    check("T-52d", "several close names: 'Did you mean one of these?' buttons",
          r.card["title"] == "Did you mean?" and len(values(r)) == 2)
    _, conv = fresh(CodeOnly(), "ADV-5678")
    r = conv.send("Lock Jnae Millre's card")
    check("T-52e", "another advisor's client is never suggested",
          kind(r) == "client_input" and "Jane Miller" not in json.dumps(r.card))
    _, conv = fresh(CodeOnly(), "ADV-5678")
    r = conv.send("Lock Robert Castellanos's card")
    check("T-52e", "and the not-found line repeats what was typed, never the real spelling",
          r.card.get("notice") == "No client named Robert Castellanos was found.")

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
