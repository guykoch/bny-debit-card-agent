"""
Checks the hosted-demo plumbing without a network. Run:

    python -m tests.test_hosting

  - a conversation survives being saved and restored (what Vercel needs)
  - another advisor cannot pick up someone else's thread
  - with DEMO_MODE / DEMO_PASSCODE off, the demo tools do not exist
  - with them on, the passcode is required and Reset restores the start state
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DCA_STORE"] = "memory"      # never touch the shared demo database
os.environ["DCA_RUNTIME"] = "keyword"   # no model needed here

import json

from config import settings
from interfaces import a2a_server

PASS, FAIL = [], []


def check(label, condition, detail=""):
    (PASS if condition else FAIL).append(label)
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{(' - ' + detail) if detail else ''}")


def call(method, path, payload=None, headers=None):
    body = json.dumps(payload).encode() if payload is not None else b""
    code, kind, out = a2a_server.route(method, path, headers or {}, body)
    return code, (json.loads(out) if kind == "application/json" else out)


def chat(text, advisor="ADV-1234", conv="t1", headers=None):
    return call("POST", "/api/chat", {"advisor_id": advisor, "conversation_id": conv,
                                      "utterance": text}, headers)[1]


def run():
    settings.DEMO_MODE, settings.DEMO_PASSCODE = False, ""
    a2a_server.reset_memory()

    print("\n1. A conversation is saved after every message and restored before the next")
    r = chat("Lock Robert Castellano's card")
    check("asks which card", r["status"] == "needs_input")
    saved = a2a_server.threads().load("t1")
    check("thread saved as JSON", saved and saved["runtime"] == "keyword" and saved["pending"])
    r = chat("2202")
    check("restored thread continues: confirm panel", r["status"] == "awaiting_confirmation")
    r = chat("confirm")
    check("confirm on the restored thread runs", r["status"] == "ok", r["message"])

    print("\n2. Another advisor cannot continue someone else's thread")
    chat("Lock Jane Miller's card", conv="t2")
    r = chat("confirm", advisor="ADV-5678", conv="t2")
    check("no confirm for a different advisor", r["status"] != "ok")
    card = a2a_server.services().cards.get_card("CARD-4417")
    check("Jane's card untouched", card.status == "active")

    print("\n3. Demo tools are off by default")
    check("/api/info says off", call("GET", "/api/info")[1]["demo_mode"] is False)
    check("reset endpoint is 404", call("POST", "/api/demo/reset", {})[0] == 404)
    check("demo-tools.js is not served", call("GET", "/demo-tools.js")[0] == 404)
    check("chat needs no passcode", chat("hi", conv="t3")["status"] != "error")

    print("\n4. Demo tools on: passcode and reset")
    settings.DEMO_MODE, settings.DEMO_PASSCODE = True, "corestone-amber-7429"
    good = {"X-Demo-Passcode": "corestone-amber-7429"}
    check("chat without passcode refused", call("POST", "/api/chat",
          {"advisor_id": "ADV-1234", "utterance": "hi"})[0] == 401)
    check("reset without passcode refused", call("POST", "/api/demo/reset", {})[0] == 401)
    check("wrong passcode rejected",
          call("POST", "/api/demo/check-passcode", {"passcode": "x"})[1]["ok"] is False)
    check("right passcode accepted",
          call("POST", "/api/demo/check-passcode", {"passcode": "corestone-amber-7429"})[1]["ok"])
    check("demo-tools.js served", call("GET", "/demo-tools.js")[0] == 200)
    check("2202 locked before reset",
          a2a_server.services().cards.get_card("CARD-2202").status == "locked")
    code, out = call("POST", "/api/demo/reset", {}, good)
    check("reset ok", code == 200 and out["status"] == "ok")
    check("2202 active again", a2a_server.services().cards.get_card("CARD-2202").status == "active")
    check("audit emptied", call("GET", "/api/audit", headers=good)[1] == [])
    check("threads emptied", a2a_server.threads().load("t1") is None)

    settings.DEMO_MODE, settings.DEMO_PASSCODE = False, ""
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
