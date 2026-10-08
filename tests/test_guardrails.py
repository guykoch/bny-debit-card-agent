"""
The cases worth showing BNY. Run:  python -m tests.test_guardrails

Each one proves something a reviewer will ask about:
  - nothing runs before Confirm
  - a refusal the model had no say in
  - refusals are logged, not just successes
  - a malformed request dies before our code runs
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DCA_STORE"] = "memory"      # never touch the shared demo database

from datetime import date, timedelta

from config import settings
from config.settings import build_services
from core import audit
from core.guardrails import dispatch
from core.models import Session

PASS, FAIL = [], []


def check(label, condition, detail=""):
    (PASS if condition else FAIL).append(label)
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{(' - ' + detail) if detail else ''}")


def run():
    svc = build_services()
    audit.reset()
    adv = Session(advisor_id="ADV-1234", utterance="lock Jane's card")

    print("\n1. Nothing happens before Confirm")
    r = dispatch(svc, adv, "lock_card", {"client_id": "C-88210", "card_id": "CARD-4417"})
    check("returns a confirmation card", r.status == "awaiting_confirmation")
    check("card is still active", svc.cards.get_card("CARD-4417").status == "active")

    print("\n2. Confirm runs it, twice does not")
    r = dispatch(svc, adv, "lock_card", {"client_id": "C-88210", "card_id": "CARD-4417"}, confirmed=True)
    check("locked", r.status == "ok", r.message)
    r = dispatch(svc, adv, "lock_card", {"client_id": "C-88210", "card_id": "CARD-4417"}, confirmed=True)
    check("already locked is refused", r.data.get("code") == "already_locked")

    print("\n3. Two clients share a name - we ask, never choose")
    r = dispatch(svc, adv, "find_client", {"query": "Sarah Chen"})
    check("asks which one", r.status == "needs_input")
    check("shows exactly the two this advisor may see", len(r.data["clients"]) == 2)
    check("the third Sarah Chen is invisible",
          all(c["client_id"] != "C-99001" for c in r.data["clients"]))

    print("\n4. Entitlement — trusting BNY's upstream check (the default)")
    check("flag is on by default", settings.TRUST_UPSTREAM_ENTITLEMENT)
    r = dispatch(svc, adv, "unlock_card", {"client_id": "C-12090", "card_id": "CARD-2091"},
                 confirmed=True)
    check("an approved request goes straight through", r.status == "ok", r.message)
    check("audit says who checked",
          audit.LOG[-1]["detail"].get("entitlement_checked_by") == "bny_orchestrator")

    print("\n5. Entitlement — checking it ourselves as well (flag off)")
    settings.TRUST_UPSTREAM_ENTITLEMENT = False
    try:
        r = dispatch(svc, adv, "lock_card", {"client_id": "C-77310", "card_id": "CARD-3310"},
                     confirmed=True)
        check("another advisor's client is refused", r.data.get("code") == "not_entitled")
        r = dispatch(svc, adv, "close_card",
                     {"client_id": "C-44090", "card_id": "CARD-9902", "reason": "client request"},
                     confirmed=True)
        check("may lock this client but may not close", r.data.get("code") == "not_entitled")
        r = dispatch(svc, adv, "lock_card", {"client_id": "C-10220", "card_id": "CARD-2201"},
                     confirmed=True)
        check("a permitted action still runs", r.status == "ok", r.message)
        check("audit says we checked it",
              audit.LOG[-1]["detail"].get("entitlement_checked_by") == "agent")
    finally:
        settings.TRUST_UPSTREAM_ENTITLEMENT = True

    print("\n6. Ownership")
    r = dispatch(svc, adv, "lock_card", {"client_id": "C-88210", "card_id": "CARD-8807"}, confirmed=True)
    check("card belonging to someone else is refused", r.data.get("code") == "bad_request")

    print("\n7. The schema rejects malformed requests")
    for label, payload in [("missing card_id", {"client_id": "C-88210"}),
                           ("invented field", {"client_id": "C-88210", "card_id": "CARD-4417",
                                               "customer": "Jane"})]:
        r = dispatch(svc, adv, "lock_card", payload)
        check(label + " rejected", r.status == "error", r.message)
    r = dispatch(svc, adv, "replace_card", {"client_id": "C-88210", "card_id": "CARD-4417",
                                            "reason": "because", "delivery_address": "x"})
    check("value outside the allowed list rejected", r.status == "error", r.message)

    print("\n8. Travel notice dates")
    start = date.today() + timedelta(days=20)
    r = dispatch(svc, adv, "travel_notice",
                 {"client_id": "C-44090", "card_id": "CARD-9902",
                  "destination": ["Georgia (country)"], "start_date": str(start),
                  "end_date": str(start - timedelta(days=3))}, confirmed=True)
    check("end before start rejected", r.status == "error", r.message)
    r = dispatch(svc, adv, "travel_notice",
                 {"client_id": "C-44090", "card_id": "CARD-9902",
                  "destination": ["Georgia (country)"], "start_date": str(start),
                  "end_date": str(start + timedelta(days=14))}, confirmed=True)
    check("valid window accepted", r.status == "ok", r.message)

    print("\n9. The audit records refusals too")
    outcomes = [row["outcome"] for row in audit.LOG]
    check("denials are logged", outcomes.count("not_entitled") == 2)
    check("what the advisor typed is stored",
          all(row["advisor_typed"] for row in audit.LOG))

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
