"""
Checks the Service Center tickets (Stop Payment, Check Copy, Address Update, Misc)
and the check look-up. Run:

    python -m tests.test_tickets

Send only saves a ticket: nothing else changes. No network: keyword routing stands
in for GPT-5.4, the sample list stands in for Google.
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DCA_STORE"] = "memory"

import json

from config import settings
from core import audit
from core.guardrails import dispatch
from core.models import Session
from integrations import address_lookup
from interfaces import a2a_server
from tests.test_fixes import fresh, labels, values
from tests.test_pending import CodeOnly, kind

RESULTS: dict[str, bool] = {}
PASS, FAIL = [], []
CB = "callback_form:" + json.dumps({"kind": "US", "number": "2125550100", "ext": ""})


def check(tid, label, condition, detail=""):
    RESULTS[tid] = RESULTS.get(tid, True) and bool(condition)
    (PASS if condition else FAIL).append(f"{tid} {label}")
    print(f"  {'PASS' if condition else 'FAIL'}  {tid}  {label}{(' - ' + detail) if detail else ''}")


def key(r, label):
    return next((f["value"] for f in r.card["ticket"]["key"] if f["label"] == label), "")


def run():
    settings.ADDRESS_PROVIDER = "sample"

    print("\nF-55  Stop Payment ticket")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Stop payment on Jane Miller's check 1043")
    check("T-55a", "one sentence: only the Call Back # is asked (first time)",
          kind(r) == "callback_form")
    r = conv.send(CB)
    check("T-55a", "review card: Stop Payment, check 1043 $250.00 filled from the record",
          r.status == "awaiting_confirmation" and r.card["ticket"]["title"] == "Stop Payment"
          and "1043" in json.dumps(r.card["ticket"]) and "$250.00" in json.dumps(r.card["ticket"]))
    check("T-55a", "review card: Send, Edit details, Cancel",
          [a["label"] for a in r.card["actions"]] == ["Send", "Edit details", "Cancel"])
    check("T-55a", "the 24-hour note is on the card", "24" in (r.card["ticket"].get("note") or ""))
    r = conv.send("confirm")
    check("T-55a", "Send: ticket SR-10234 saved, in the Service Center's words",
          r.status == "ok" and r.data["ticket_id"] == "SR-10234"
          and "processed by the Service Center" in r.message)
    t = svc.tickets.list_for_advisor("ADV-1234")
    check("T-55a", "the ticket is listed for the advisor (Active Tickets)",
          len(t) == 1 and t[0]["ticket"] == "Stop Payment" and t[0]["client_name"] == "Jane Miller")
    check("T-55a", "audited as 'Ticket: Stop Payment'",
          audit.LOG[-1]["action_name"] == "Ticket: Stop Payment")
    r = conv.send("Stop payment on Robert Castellano's check 3102")
    check("T-55b", "Call Back # saved: the next ticket goes straight to review",
          r.status == "awaiting_confirmation" and r.card["ticket"]["title"] == "Stop Payment")

    svc, conv = fresh(CodeOnly())
    r = conv.send("Stop payment on Jane Miller's check 1041")
    check("T-55c", "a paid check can't be stopped; a copy is offered",
          "was paid on 10/18/2026" in r.card["message"] and "Request a copy" in labels(r))
    r = conv.send("Request a copy")
    check("T-55c", "one tap starts the Check Copy ticket with the check filled in",
          conv.task["skill"].name == "check-copy" and kind(r) == "callback_form")

    svc, conv = fresh(CodeOnly())
    r = conv.send("Stop payment on Jane Miller's check 1045")
    check("T-55d", "check not found anywhere: which account (Jane has two)",
          r.card["title"] == "Which account?" and len(values(r)) == 2)
    r = conv.send(values(r)[0])
    check("T-55d", "numbers are never guessed: 'Did you mean' with nearby checks",
          "Did you mean" in r.card["message"] and "1044" in labels(r)[0]
          and any("keep" in l.lower() for l in labels(r)))
    check("T-55d", "Stop Payment suggests only unpaid checks, status on each button",
          all("Not paid yet" in l for l in labels(r)[:-1])
          and not any("1042" in l or "1041" in l for l in labels(r)))
    r = conv.send(values(r)[0])
    if kind(r) == "callback_form":
        r = conv.send(CB)
    check("T-55d", "picking 1044: the review card and the subject follow the fix",
          "1044" in json.dumps(r.card["ticket"]["key"])
          and r.card["ticket"]["editable"]["subject"].endswith("1044"))

    print("\nF-55  Check Copy, check look-up")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Jane Miller needs a copy of check 1043")
    check("T-55e", "copy of an unpaid check: offers to stop it instead",
          "Stop this payment" in labels(r))
    svc, conv = fresh(CodeOnly())
    r = conv.send("Jane Miller needs a copy of check 1040")
    r = conv.send(values(r)[0])
    check("T-55e", "Check Copy suggests only paid checks, with the date paid",
          labels(r)[:2] == ["Check 1041 · $1,200.00 · written 10/15/2026 · Paid 10/18/2026",
                            "Check 1042 · $86.40 · written 10/21/2026 · Paid 10/23/2026"]
          and not any("1043" in l or "1044" in l for l in labels(r)))
    svc, conv = fresh(CodeOnly())
    r = conv.send("Did Jane Miller's check 1043 clear?")
    check("T-55f", "look-up: amount, date in US format, status, and next steps as buttons",
          kind(r) == "check_status" and "10/28/2026" in json.dumps(r.card)
          and labels(r)[:1] == ["Stop this payment"])
    check("T-55f", "a look-up changes nothing and saves no ticket",
          svc.tickets.list_for_advisor("ADV-1234") == [])

    print("\nF-55  Address Update and Misc tickets")
    svc, conv = fresh(CodeOnly())
    hit = address_lookup.suggest("1100 Congress")["suggestions"][0]["id"]
    conv.send("Jane Miller moved, change her address")
    conv.send("ticket_address:" + json.dumps({"pick": hit, "unit": "", "phone": ""}))
    r = conv.send(CB)
    check("T-55g", "review card: no red 'phone or address required' note (already met)",
          not r.card["ticket"]["note"])
    conv.send("confirm")
    check("T-55g", "Address Update: a ticket, the profile is not changed",
          svc.tickets.list_for_advisor("ADV-1234")[0]["ticket"] == "Address Update"
          and not any("Congress" in a.address for a in svc.clients.addresses("C-88210")))
    svc, conv = fresh(CodeOnly())
    r = conv.send("Order a new checkbook for Jane Miller")
    check("T-55h", "Misc: account or IBD / Office / IP #",
          r.card["title"] == "Which account?" and "__office__" in values(r))

    print("\nF-55  Guardrails on tickets")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Stop payment on Margaret Osei-Bonsu's check 4701")
    check("T-55i", "no ticket permission: refused right away", r.data.get("code") == "not_entitled")
    adv = Session(advisor_id="ADV-1234")
    base = {"client_id": "C-88210", "account_id": "ACC-8821",
            "checks": [{"check_number": "1043", "amount": "250.00"}],
            "callback": {"kind": "US", "number": "212-555-0100"}}
    r1 = dispatch(svc, adv, "stop_payment", {**base, "draft_id": "same"}, confirmed=True)
    r2 = dispatch(svc, adv, "stop_payment", {**base, "draft_id": "same"}, confirmed=True)
    check("T-55j", "double Send: one ticket (same draft, same SR #)",
          r1.data["ticket_id"] == r2.data["ticket_id"])
    r = dispatch(svc, adv, "stop_payment", {**base, "account_id": "ACC-1022", "draft_id": "x"})
    check("T-55k", "another client's account is refused", r.status == "error")
    r = dispatch(svc, adv, "stop_payment",
                 {**base, "draft_id": "y", "additional_info": "card 4111111111111111"})
    check("T-55l", "long numbers in free text are masked",
          "4111111111111111" not in json.dumps(r.card))
    r = dispatch(svc, adv, "stop_payment",
                 {**base, "draft_id": "z", "attachments": [{"storage_id": "nope", "name": "a.pdf"}]},
                 confirmed=True)
    check("T-55m", "an attachment that was never uploaded is refused on Send",
          r.data.get("code") == "attachment_invalid")
    sid = svc.files.put(b"x" * 100, "text/plain")
    r = dispatch(svc, adv, "stop_payment",
                 {**base, "draft_id": "z2", "attachments": [{"storage_id": sid, "name": "a.txt"}]},
                 confirmed=True)
    check("T-55m", "only PDF, JPG or PNG", r.data.get("code") == "attachment_invalid")
    sid = svc.files.put(b"%PDF-1.4", "application/pdf")
    r = dispatch(svc, adv, "stop_payment",
                 {**base, "draft_id": "z3", "attachments": [{"storage_id": sid, "name": "a.pdf"}]},
                 confirmed=True)
    check("T-55m", "a PDF is attached to the ticket",
          r.status == "ok" and svc.tickets.list_for_advisor("ADV-1234")[0]["attachments"][0]["name"]
          == "a.pdf")

    print("\nF-55  Close removed; 'cancel' asks which")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Close Jane Miller's card")
    check("T-55n", "close: a card can't be closed alone; Replace / Lock buttons",
          values(r) == ["replace-card", "lock-card"])
    r = conv.send("Cancel it for Jane Miller")
    check("T-55o", "'cancel' with no check or card word: a check or the card?",
          r.card["title"] == "A check or the card?")

    print("\nF-55  Actions menu and the server endpoints")
    svc, conv = fresh(CodeOnly())
    r = conv.send("__actions__")
    check("T-55p", "two sections: Do it now / Send a ticket",
          r.card["groups"] == {"now": "Do it now", "ticket": "Send a ticket"})
    a2a_server.reset_memory()
    code, _, body = a2a_server.route("GET", "/api/tickets?advisor=ADV-1234", {}, b"")
    check("T-55q", "GET /api/tickets lists the advisor's tickets",
          code == 200 and json.loads(body)["tickets"] == [])
    code, _, _ = a2a_server.route("GET", "/api/tickets?advisor=ADV-0000", {}, b"")
    check("T-55q", "unknown advisor refused", code == 400)
    code, _, body = a2a_server.route("POST", "/api/tickets/upload",
                                     {"Content-Type": "application/pdf"}, b"%PDF")
    check("T-55r", "upload returns a storage id", code == 200 and json.loads(body)["storageId"])

    print("\nF-59  Active Tickets: View an attachment")
    a2a_server.reset_memory()
    store = a2a_server.services()
    sid = store.files.put(b"%PDF-1.4 demo", "application/pdf")
    r = dispatch(store, Session(advisor_id="ADV-1234"), "stop_payment",
                 {**base, "draft_id": "v1", "attachments": [{"storage_id": sid, "name": "letter.pdf"}]},
                 confirmed=True)
    tid = r.data["ticket_id"]
    code, _, body = a2a_server.route(
        "GET", f"/api/tickets/file?advisor=ADV-1234&ticket={tid}&id={sid}", {}, b"")
    out = json.loads(body)
    check("T-59a", "the advisor's own attachment: a link to view it",
          code == 200 and out["url"] and out["name"] == "letter.pdf")
    code, kind_, raw = a2a_server.route("GET", out["url"], {}, b"")
    check("T-59a", "the link returns the file itself", code == 200
          and kind_ == "application/pdf" and raw.startswith(b"%PDF"))
    code, _, _ = a2a_server.route(
        "GET", f"/api/tickets/file?advisor=ADV-5678&ticket={tid}&id={sid}", {}, b"")
    check("T-59b", "another advisor can't open it", code == 404)
    code, _, _ = a2a_server.route(
        "GET", f"/api/tickets/file?advisor=ADV-1234&ticket={tid}&id=local-999", {}, b"")
    check("T-59b", "a file not attached to that ticket can't be opened", code == 404)

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
