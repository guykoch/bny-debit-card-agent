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
from tests.test_fixes import fresh, has_cancel, labels, values
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

    print("\nF-55 / F-61  Stop a check (BNY form: Stop Payment)")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Stop payment on Jane Miller's check 1043")
    check("T-61b", "one sentence: straight to the review card, Call Back # from the advisor directory",
          r.status == "awaiting_confirmation"
          and r.card["ticket"]["editable"]["callback"] == {"kind": "US", "number": "212-555-0142",
                                                           "ext": "204"})
    check("T-61a", "'stop payment' understood; the card says 'Stop a check', the form 'Stop Payment'",
          r.card["ticket"]["title"] == "Stop a check" and "Stop Payment" in r.card["ticket"]["form"]
          and r.card["ticket"]["editable"]["subject"] == "Stop Payment: check 1043")
    check("T-61b", "the advisor's name is on the form (Name: Alex Morgan)",
          {"label": "Name", "value": "Alex Morgan"} in r.card["ticket"]["all"])
    check("T-55a", "review card: check 1043 $250.00 filled from the record",
          r.status == "awaiting_confirmation"
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
          len(t) == 1 and t[0]["ticket"] == "Stop a check" and t[0]["client_name"] == "Jane Miller")
    check("T-55a", "audited as 'Ticket: Stop Payment'",
          audit.LOG[-1]["action_name"] == "Ticket: Stop Payment")
    conv.send("Stop payment on Robert Castellano's check 3102")
    r = conv.send("confirm_with:" + json.dumps({"callback": {"kind": "US", "number": "212-555-0142",
                                                             "ext": "310"}}))
    r = conv.send("Stop payment on Robert Castellano's check 3101")
    r = conv.send("Stop payment on Jane Miller's check 1044")
    check("T-61b", "a changed Call Back # is saved and used next time",
          r.card["ticket"]["editable"]["callback"]["ext"] == "310")
    svc2, conv2 = fresh(CodeOnly(), "ADV-5678")
    r = conv2.send("Stop payment on Claire Beaumont's check 1")
    svc2.advisors.get("ADV-5678")
    check("T-61b", "each advisor has their own number",
          svc2.advisors.get("ADV-5678")["callback"]["number"] == "312-555-0177")

    svc, conv = fresh(CodeOnly())
    r = conv.send("Stop payment on Jane Miller's check 1041")
    check("T-55c", "a paid check can't be stopped; a copy is offered",
          "was paid on 10/18/2026" in r.card["message"] and "Request a copy" in labels(r))
    r = conv.send("Request a copy")
    check("T-55c", "one tap starts the Check Copy ticket with the check filled in",
          conv.task["skill"].name == "check-copy" and r.status == "awaiting_confirmation")

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
    check("T-55d", "picking 1044: the review card and the subject follow the fix",
          "1044" in json.dumps(r.card["ticket"]["key"])
          and r.card["ticket"]["editable"]["subject"].endswith("1044"))

    print("\nF-55  Check Copy, check look-up")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Jane Miller needs a copy of check 1043")
    check("T-55e", "copy of an unpaid check: offers to stop it instead",
          "Stop this check" in labels(r))
    svc, conv = fresh(CodeOnly())
    r = conv.send("Jane Miller needs a copy of check 1040")
    r = conv.send(values(r)[0])
    check("T-55e", "Check Copy suggests only paid checks, with the date paid",
          labels(r)[:2] == ["Check 1041 · $1,200.00 · written 10/15/2026 · Paid 10/18/2026",
                            "Check 1042 · $86.40 · written 10/21/2026 · Paid 10/23/2026"]
          and not any("1043" in l or "1044" in l for l in labels(r)))
    svc, conv = fresh(CodeOnly())
    r = conv.send("Did Jane Miller's check 1043 clear?")
    check("T-61c", "look-up: the answer first ('Check 1043: Not paid yet'), one detail line",
          kind(r) == "check_status" and r.card["title"] == "Check 1043: Not paid yet"
          and r.card["message"] == "$250.00 to City Plumbing Co, written 10/28/2026 · AMA ...8821")
    check("T-61c", "not paid yet: a Stop this check button", labels(r)[:1] == ["Stop this check"])
    check("T-55f", "a look-up changes nothing and saves no ticket",
          svc.tickets.list_for_advisor("ADV-1234") == [])

    print("\nF-55  Address Update and Misc tickets")
    svc, conv = fresh(CodeOnly())
    hit = address_lookup.suggest("1100 Congress")["suggestions"][0]["id"]
    conv.send("Jane Miller moved, change her address")
    r = conv.send("ticket_address:" + json.dumps({"pick": hit, "unit": "", "phone": ""}))
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

    print("\nF-60  A request already pending for the same check")
    svc, conv = fresh(CodeOnly())
    conv.send("Stop payment on Jane Miller's check 1043")
    r = conv.send("confirm"); first = r.data["ticket_id"]
    r = conv.send("Stop payment on Jane Miller's check 1043")
    check("T-60a", "second stop payment: 'already pending (SR-...)', Send another / Cancel",
          r.card["title"] == "Already requested"
          and f"already pending ({first})" in r.card["message"]
          and labels(r) == ["Send another"] and has_cancel(r))
    r = conv.send("cancel")
    check("T-60a", "typing 'cancel' on the card cancels (like the button)",
          r.message.startswith("Cancelled"))
    r = conv.send("Stop payment on Jane Miller's check 1043")
    r = conv.send("Send another")
    check("T-60a", "Send another: the review card as usual", r.status == "awaiting_confirmation")
    r = conv.send("confirm")
    check("T-60a", "and a new ticket", r.status == "ok" and r.data["ticket_id"] != first)
    r = conv.send("Did Jane Miller's check 1043 clear?")
    check("T-60b", "look-up card: 'Stop payment pending (SR-...)', no Stop button",
          "Stop payment pending (SR-" in r.card["title"]
          and "Stop this check" not in labels(r))
    conv.send("__no__")
    conv.send("Stop payment on Jane Miller's check 1041"); conv.send("Request a copy")
    r = conv.send("confirm"); copy_id = r.data["ticket_id"]
    r = conv.send("Jane Miller needs a copy of check 1041")
    check("T-60c", "Check Copy: 'A copy of check 1041 was already requested (SR-...)'",
          f"already requested ({copy_id})" in r.card["message"])
    r = conv.send("cancel")
    check("T-60c", "Cancel: nothing sent",
          len([t for t in svc.tickets.list_for_advisor("ADV-1234") if t["tool"] == "check_copy"]) == 1)
    svc, conv = fresh(CodeOnly())
    svc.tickets.submit({"draft_id": "other", "advisor_id": "ADV-5678", "tool": "stop_payment",
                        "account_id": "ACC-8821", "check_numbers": ["1044"], "ticket": "Stop Payment"})
    r = conv.send("Stop payment on Jane Miller's check 1044")
    if kind(r) == "callback_form":
        r = conv.send(CB)
    check("T-60d", "another advisor's pending request: said, without their SR #",
          "already pending (by another advisor)" in r.card["message"]
          and "SR-" not in r.card["message"])

    print("\nF-61  Linked requests: context across messages (Ben, 11/11)")
    svc, conv = fresh(CodeOnly())
    conv.send("Did Jane Miller's check 1043 clear?")
    r = conv.send("ok, stop that payment then")
    check("T-61d", "'stop that payment' after a look-up: confirm the check with one tap",
          r.card["message"] == "Stop check 1043 for Jane Miller ($250.00)?"
          and labels(r) == ["Yes", "Another check"] and has_cancel(r))
    r = conv.send("Yes")
    check("T-61d", "Yes: the review card for check 1043 (nothing sent yet)",
          r.status == "awaiting_confirmation" and "1043" in json.dumps(r.card["ticket"]["key"])
          and svc.tickets.list_for_advisor("ADV-1234") == [])
    svc, conv = fresh(CodeOnly())
    conv.send("Was Jane Miller's check 1041 cashed?")
    r = conv.send("great, can we get a copy of it")
    check("T-61d", "'a copy of it' after a paid check: Request a copy of check 1041?",
          r.card["message"].startswith("Request a copy of check 1041 for Jane Miller"))
    r = conv.send("Another check")
    check("T-61d", "Another check: same client, the check details asked",
          kind(r) == "check_form" and conv.task["picked"]["client_id"] == "C-88210")
    svc, conv = fresh(CodeOnly())
    conv.send("Did Jane Miller's check 1043 clear?")
    conv.send("Lock Jane Miller's card"); conv.send("confirm")
    r = conv.send("stop it")
    check("T-61e", "after a card action, 'stop it' no longer means the check",
          not (r.card or {}).get("message", "").startswith("Stop check 1043"))
    svc, conv = fresh(CodeOnly())
    conv.send("Robert Castellano's wallet got stolen at the airport this morning")
    conv.send("CARD-2201"); conv.send("Yes"); conv.send("confirm")
    r = conv.send("Yes, order a replacement")
    check("T-61f", "'Yes, order a replacement' keeps the client and card: no 'Which client?'",
          r.card["title"] == "Delivery address" and conv.task["picked"]["card_id"] == "CARD-2201")
    r = conv.send(values(r)[0])
    check("T-61f", "reason Stolen and the flag carried over from the report",
          r.status == "awaiting_confirmation" and r.data["input"]["reason"] == "stolen"
          and r.data["input"]["flag_transactions"] is True)

    print("\nF-62 / F-67  Check deposit inquiry (Retail Check Deposit Status Inquiry)")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Has Jane Miller's rollover check from Voya come in yet? It's for $85,000.")
    check("T-62a", "received and credited: says so, no ticket needed",
          "received in Jersey City on 11/09/2026 and credited to AMA ...8821" in r.message
          and "No inquiry is needed" in r.message and svc.tickets.list_for_advisor("ADV-1234") == [])
    svc, conv = fresh(CodeOnly())
    r = conv.send("Robert Castellano's 401(k) rollover from Fidelity, check 77810 for $142,300, "
                  "went out to Pittsburgh last week. Can you check on it?")
    check("T-62b", "received but not credited: the form card, filled from the received check",
          kind(r) == "rollover_form" and "couldn't be credited" in r.card["info"]
          and r.card["values"]["destination"] == "Pittsburgh"
          and r.card["values"]["lockbox"] == "Rollover Lockbox-734022"
          and r.card["values"]["amount"] == "142300.00")
    check("T-62b", "missing required fields highlighted",
          r.card["missing"] == ["Method of Delivery", "Date Sent"])
    form = {**r.card["values"], "delivery_method": "Overnight", "date_sent": "2026-11-04"}
    r = conv.send("rollover_form:" + json.dumps(form))
    check("T-62c", "Overnight without a tracking # is refused on the card",
          kind(r) == "rollover_form" and "Tracking #" in r.message)
    form["delivery_method"] = "Regular mail"
    r = conv.send("rollover_form:" + json.dumps(form))
    check("T-62b", "then the review card (Account, Check, Sent, Destination, Call Back #)",
          r.status == "awaiting_confirmation" and r.card["ticket"]["title"] == "Check Deposit Status Inquiry"
          and "Retail Check Deposit Status Inq" in r.card["ticket"]["form"]
          and key(r, "Destination") == "Pittsburgh · Rollover Lockbox-734022")
    r = conv.send("confirm")
    t = svc.tickets.list_for_advisor("ADV-1234")[0]
    check("T-62b", "Send: ticket saved with every form field",
          r.status == "ok" and t["request_type"] == "Retail Check Deposit Status Inq"
          and {"label": "Amount", "value": "$142,300.00"} in t["fields"]
          and {"label": "Date Sent", "value": "11/04/2026"} in t["fields"])
    svc, conv = fresh(CodeOnly())
    r = conv.send("Retail check deposit status inquiry for Priya Raghunathan: check 55120, "
                  "$300,000.00 from ADP, sent overnight 11/10/2026, tracking 7712 3345 9901, "
                  "to Lake Mary.")
    check("T-62d", "not received yet: everything filled from one sentence, nothing missing",
          kind(r) == "rollover_form" and "No check matching this has been received" in r.card["info"]
          and r.card["missing"] == [] and r.card["values"]["tracking_number"] == "771233459901"
          and r.card["values"]["date_sent"] == "2026-11-10")
    check("T-62d", "not a rollover: the desk's retail deposit lockbox (invented demo values)",
          r.card["values"]["lockbox"] == "Retail Deposit Lockbox-852306")
    svc, conv = fresh(CodeOnly())
    r = conv.send("A $50,000 check from Jane Miller's old bank was mailed to Pershing in Jersey City, "
                  "check 8812. Has it come in?")
    check("T-62f", "any check mailed to Pershing for deposit, not only rollovers",
          conv.task and conv.task["skill"].name == "deposit-inquiry" and kind(r) == "rollover_form"
          and r.card["values"]["lockbox"] == "Retail Deposit Lockbox-610274")
    import json as _j
    t = _j.load(open(os.path.join(os.path.dirname(__file__), "..", "tickets", "deposit_inquiry.json")))
    boxes = [b for f in t["fields"] if f["id"] == "lockbox" for v in f["options_by_destination"].values() for b in v]
    check("T-62g", "no real lockbox numbers in the demo data", "382084" not in " ".join(boxes))
    adv = Session(advisor_id="ADV-1234")
    bad = {"client_id": "C-10344", "account_id": "ACC-1034", "draft_id": "rf", "amount": "100",
           "check_number": "1", "delivery_method": "Regular mail", "date_sent": "2099-01-01",
           "destination": "Lake Mary", "callback": {"kind": "US", "number": "212-555-0142"}}
    r = dispatch(svc, adv, "deposit_inquiry", bad)
    check("T-62e", "a future Date Sent is refused", r.data.get("code") == "rollover_missing")
    r = dispatch(svc, adv, "deposit_inquiry", {**bad, "date_sent": "2026-11-01",
                                                "lockbox": "Rollover Lockbox-734022"})
    check("T-62e", "a lockbox from another desk is refused", r.data.get("code") == "rollover_missing")

    print("\nF-63  Misc boundary (every request is for a client)")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Robert Castellano's $5,000 deposit from last Tuesday still isn't showing on his AMA account.")
    check("T-63a", "a deposit not showing: Misc for the client, AMA named in the message",
          r.status == "awaiting_confirmation" and key(r, "Account") == "AMA ...1022"
          and r.card["ticket"]["editable"]["subject"] == "Deposit not showing")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Send a request to the service team: office 4521 needs 20 account-opening kits.")
    check("T-63a", "every Misc request is for a client: no client named -> 'Which client?'",
          kind(r) == "client_input")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Order a new checkbook for Jane Miller's Resource Checking account, starting at check 2101.")
    check("T-63b", "the account named in the message is used (no 'Which account?')",
          r.status == "awaiting_confirmation" and key(r, "Account") == "Resource Checking ...8830")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Jane Miller got hit with a $35 overdraft fee, can we ask them to waive it?")
    check("T-63c", "a fee refund is a Misc request", conv.task and conv.task["skill"].name == "misc-request")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Elena Vasquez can't find her October statement, can they send it again?")
    check("T-63c", "re-sending a statement is a Misc request (no longer out of scope)",
          conv.task and conv.task["skill"].name == "misc-request")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Can you order a new couch for our office lobby?")
    check("T-63d", "not about the account: out of scope, nothing created",
          "I can help with" in r.message and conv.task is None)

    print("\nF-66  Send from the page (confirm_with) works for every ticket type")
    def page_send(conv, r):
        ed = r.card["ticket"]["editable"]
        extra = {"additional_info": ed["additional_info"] or "details", "callback": ed["callback"],
                 "attachments": []}
        if ed.get("has_subject", True):
            extra["subject"] = ed["subject"] or "Request"
        return conv.send("confirm_with:" + json.dumps(extra))
    cases = [("stop_payment", ["Stop payment on Jane Miller's check 1043"]),
             ("check_copy", ["Request a copy of check 1042 for Jane Miller."]),
             ("address_update", ["Jane Miller moved, change her address",
                                 "ticket_address:" + json.dumps({"pick": address_lookup.suggest(
                                     "1100 Congress")["suggestions"][0]["id"], "unit": "", "phone": ""})]),
             ("misc_request", ["Order a new checkbook for Jane Miller's AMA account"]),
             ("deposit_inquiry", ["Retail check deposit status inquiry for Priya Raghunathan: check "
                                   "55120, $300,000.00 from ADP, sent overnight 11/10/2026, tracking "
                                   "7712 3345 9901, to Lake Mary.", "__form__"])]
    for tool, msgs in cases:
        svc, conv = fresh(CodeOnly())
        for m in msgs:
            r = conv.send("rollover_form:" + json.dumps(r.card["values"]) if m == "__form__" else m)
        r = page_send(conv, r)
        check("T-66a", f"{tool}: Send with the page's fields saves the ticket",
              r.status == "ok" and r.data.get("ticket_id", "").startswith("SR-"), r.message[:80])

    print("\nF-65  'What did you do so far?': one bullet per action")
    svc, conv = fresh(CodeOnly())
    conv.send("Lock Jane Miller's card"); conv.send("confirm")
    conv.send("Stop payment on Jane Miller's check 1043"); conv.send("confirm")
    r = conv.send("what did you do so far?")
    check("T-65a", "a heading, then one line per action with the client's name",
          r.message.split("\n") == ["Done in this conversation:",
                                     "• Jane Miller: Card ending 4417 is locked.",
                                     "• Jane Miller: Stop a check request SR-10234 sent."])
    r = conv.send("can you give me a recap of what you did?")
    check("T-65a", "other phrasings too (recap)", r.message.startswith("Done in this conversation:"))

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
