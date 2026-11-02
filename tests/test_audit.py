"""
Checks the two audit logs and the US date format. Run:

    python -m tests.test_audit

audit_actions: every card action that reached our checks (Completed / Refused /
Not permitted). audit_chat: every line of every conversation. No network.
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DCA_STORE"] = "memory"

import json
import re

from config import settings
settings.RUNTIME = "gpt"
settings.ADDRESS_PROVIDER = "sample"
from core import audit
from core.timefmt import us_date, us_timestamp
from datetime import datetime, timezone
import interfaces.llm_runtime as lr
from tests.test_pending import CodeOnly
lr.OpenAIChatClient = lambda: CodeOnly()
from interfaces import a2a_server

RESULTS: dict[str, bool] = {}
PASS, FAIL = [], []
WHEN = re.compile(r"^\d{2}/\d{2}/\d{4} \d{1,2}:\d{2}:\d{2} (AM|PM) ET$")


def check(tid, label, condition, detail=""):
    RESULTS[tid] = RESULTS.get(tid, True) and bool(condition)
    (PASS if condition else FAIL).append(f"{tid} {label}")
    print(f"  {'PASS' if condition else 'FAIL'}  {tid}  {label}{(' - ' + detail) if detail else ''}")


def say(text, display=None, advisor="ADV-1234", conv="c1"):
    body = {"advisor_id": advisor, "conversation_id": conv, "utterance": text}
    if display:
        body["display"] = display
    code, _, out = a2a_server.route("POST", "/api/chat", {}, json.dumps(body).encode())
    return json.loads(out)


def run():
    a2a_server.reset_memory()

    print("\nF-53  US date format everywhere")
    check("T-53a", "dates on cards and messages: MM/DD/YYYY", us_date("2026-11-20") == "11/20/2026")
    check("T-53a", "times: US format, Eastern time",
          us_timestamp(datetime(2026, 11, 2, 20, 45, 12, tzinfo=timezone.utc))
          == "11/02/2026 3:45:12 PM ET")
    r = say("Jane Miller is going to Japan from November 20 to November 30 2026", conv="t")
    dates = next(f["value"] for f in r["card"]["fields"] if f["label"] == "Dates")
    check("T-53a", "travel card shows 11/20/2026 to 11/30/2026", dates == "11/20/2026 to 11/30/2026")
    r = say("confirm", "Confirm", conv="t")
    check("T-53a", "result message in US format", "11/20/2026 to 11/30/2026" in r["message"])
    with open(os.path.join(os.path.dirname(__file__), "..", "web", "index.html")) as f:
        page = f.read()
    check("T-53a", "chat page shows dates as en-US (no en-GB left)",
          '"en-US"' in page and "en-GB" not in page)

    print("\nF-54  Audit: two logs (audit_actions, audit_chat)")
    a2a_server.reset_memory()
    say("Lock Jane Miller's card")
    say("confirm", "Confirm")
    say("Close Margaret Osei-Bonsu's card permanently, she is switching banks")
    say("What's Jane's balance?")
    acts = audit.LOG
    lock = next(r for r in acts if r["action"] == "lock_card")
    check("T-54a", "action row: readable columns",
          lock["action_name"] == "Lock card" and lock["result"] == "Completed"
          and lock["client"] == "Jane Miller (C-88210)" and lock["card"] == "...4417"
          and WHEN.match(lock["when"]) and lock["advisor_request"] == "Lock Jane Miller's card",
          json.dumps({k: lock[k] for k in ("when", "action_name", "result", "client", "card")}))
    refused = acts[-1]
    check("T-54a", "a refusal is in the action log as Not permitted, with the client's name",
          refused["result"] == "Not permitted" and refused["client"].startswith("Margaret Osei-Bonsu")
          and "permission" in refused["message"])
    check("T-54a", "a question with no action is NOT in the action log",
          all(r["action"] != "balance" for r in acts) and len(acts) == 2)
    chat = audit.CHAT
    check("T-54b", "chat log: every message, advisor and chat in turn (8 lines for 4 messages)",
          len(chat) == 8 and [r["speaker"] for r in chat] == ["Advisor", "NetX AI"] * 4)
    check("T-54b", "typed vs button, the label the advisor clicked is logged",
          chat[0]["input"] == "Typed" and chat[2]["input"] == "Button"
          and chat[2]["message"] == "Confirm")
    check("T-54b", "the chat's answer: card name, fields and buttons on one line",
          chat[1]["card"] == "Confirmation: Lock debit card"
          and "Client: Jane Miller" in chat[1]["message"] and "Buttons: Confirm | Cancel"
          in chat[1]["message"])
    check("T-54b", "result line logged", chat[3]["card"].startswith("Result")
          and "4417 is locked" in chat[3]["message"])
    check("T-54b", "out-of-scope answer logged too", "debit cards" in chat[7]["message"])
    check("T-54b", "same When / advisor / conversation columns as the action log",
          all(WHEN.match(r["when"]) and r["advisor_id"] == "ADV-1234"
              and r["conversation_id"] == "c1" for r in chat))
    code, _, out = a2a_server.route("GET", "/api/audit/chat?conversation=c1", {}, b"")
    check("T-54c", "one conversation can be read back in order", code == 200
          and len(json.loads(out)) == 8)
    say("client_pick:C-88210", "Jane Miller", conv="c2")
    check("T-54b", "a form value: the label is the message, the raw value kept apart",
          audit.CHAT[-2]["input"] == "Form" and audit.CHAT[-2]["message"] == "Jane Miller"
          and audit.CHAT[-2]["raw_input"] == "client_pick:C-88210")

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
