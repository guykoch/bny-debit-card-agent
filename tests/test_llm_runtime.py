"""
Checks the GPT-5.4 runtime without calling OpenAI. Run:

    python -m tests.test_llm_runtime

The model is replaced by a script of replies, so these tests prove what OUR
code does around the model - which is the part that must never vary:

  - the model's choices only ever lead to a confirmation panel
  - "which client / which card" is asked by code when a lookup finds several
  - an action with an id no lookup returned is refused
  - a skill cannot call another action's tool
  - Confirm (trip 2) replays the stored form with no model call
  - Cancel and "Change dates" are handled by code
  - out-of-scope messages get the fixed reply
  - if the model is down, nothing changes
  - the request sent to OpenAI has the right shape

Whether GPT-5.4 asks the right questions is a separate, live evaluation.
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DCA_STORE"] = "memory"      # never touch the shared demo database

import json
from datetime import date, timedelta

from config.settings import build_services
from core import audit
from core.models import Session
from interfaces import llm_client
from interfaces.llm_client import ModelUnavailable, OpenAIChatClient
from interfaces.llm_runtime import OUT_OF_SCOPE, GptConversation

PASS, FAIL = [], []


def check(label, condition, detail=""):
    (PASS if condition else FAIL).append(label)
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{(' - ' + detail) if detail else ''}")


# ---------------------------------------------------------------- scripted model
def route(name):
    return {"role": "assistant", "content": json.dumps({"skill": name})}


def call(name, **args):
    return {"role": "assistant", "content": None,
            "tool_calls": [{"id": f"call_{name}", "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args)}}]}


def say(text):
    return {"role": "assistant", "content": text}


class ScriptedModel:
    """Returns the queued replies in order and records every request."""
    def __init__(self, *replies):
        self.queue = list(replies)
        self.requests = []

    def add(self, *replies):
        self.queue.extend(replies)

    def chat(self, messages, tools=None, response_format=None):
        self.requests.append({"messages": [dict(x) for x in messages], "tools": tools,
                              "response_format": response_format})
        if not self.queue:
            raise AssertionError("the model was called more times than scripted")
        return self.queue.pop(0)


class DownModel:
    def chat(self, *a, **k):
        raise ModelUnavailable("timed out")


def fresh(model, advisor="ADV-1234"):
    svc = build_services()
    return svc, GptConversation(svc, Session(advisor_id=advisor, conversation_id="t"), client=model)


def run():
    audit.reset()
    start = date.today() + timedelta(days=25)
    end = start + timedelta(days=14)

    print("\n1. Out-of-scope messages get the fixed reply")
    m = ScriptedModel(route("none"))
    _, conv = fresh(m)
    r = conv.send("What's Jane Miller's balance?")
    check("fixed out-of-scope message", r.message == OUT_OF_SCOPE)
    check("only the routing call was made", len(m.requests) == 1)

    print("\n2. Two cards: code asks, the model never picks")
    m = ScriptedModel(route("lock-card"),
                      call("find_client", query="Robert Castellano"),
                      call("list_cards", client_id="C-10220"))
    svc, conv = fresh(m)
    r = conv.send("Can you freeze Robert Castellano's card?")
    check("asks 'Which card?' with a code panel",
          r.status == "needs_input" and r.card and r.card.get("title") == "Which card?")
    check("both cards offered", "2201" in r.message and "2202" in r.message)
    m.add(call("lock_card", client_id="C-10220", card_id="CARD-2202"))
    calls_before = len(m.requests)
    r = conv.send("2202")
    check("typed '2202' resolves the card without a routing call",
          len(m.requests) == calls_before + 1)
    check("confirmation panel, nothing run yet",
          r.status == "awaiting_confirmation" and svc.cards.get_card("CARD-2202").status == "active")

    print("\n3. Confirm is a replay: no model call (trip 2)")
    calls_before = len(m.requests)
    r = conv.send("confirm")
    check("locked", r.status == "ok" and svc.cards.get_card("CARD-2202").status == "locked", r.message)
    check("no model call on Confirm", len(m.requests) == calls_before)
    check("audit keeps the advisor's real words",
          audit.LOG[-1]["advisor_typed"].startswith("Can you freeze Robert"))

    print("\n4. The card's last four in the first message: no question needed")
    m = ScriptedModel(route("lock-card"),
                      call("find_client", query="Robert Castellano"),
                      call("list_cards", client_id="C-10220"),
                      call("lock_card", client_id="C-10220", card_id="CARD-2201"))
    _, conv = fresh(m)
    r = conv.send("Lock Robert Castellano's card ending 2201")
    check("goes straight to confirmation", r.status == "awaiting_confirmation")

    print("\n5. Invented ids and other actions' tools are refused by code")
    m = ScriptedModel(route("lock-card"),
                      call("lock_card", client_id="C-88210", card_id="CARD-4417"),
                      say("Let me look that up first."))
    _, conv = fresh(m)
    r = conv.send("Lock Jane Miller's card")
    tool_reply = m.requests[-1]["messages"][-1]["content"]
    check("an id no lookup returned is refused", "never invent" in tool_reply)
    check("no confirmation panel", conv.pending is None)
    m = ScriptedModel(route("lock-card"),
                      call("close_card", client_id="C-88210", card_id="CARD-4417", reason="x"),
                      say("I can only lock cards here."))
    _, conv = fresh(m)
    conv.send("Lock Jane Miller's card")
    check("lock-card cannot call close_card",
          "not available" in m.requests[-1]["messages"][-1]["content"])
    check("the model only sees its own action tool",
          {t["function"]["name"] for t in m.requests[1]["tools"]}
          == {"lock_card", "find_client", "list_cards", "present_options"})

    print("\n6. Model-offered options, then a switch of skill")
    m = ScriptedModel(route("close-card"),
                      call("find_client", query="Jane Miller"),
                      call("list_cards", client_id="C-88210"),
                      call("present_options", question="Lock it for now, or close it permanently?",
                           options=["Lock (reversible)", "Close permanently"]))
    svc, conv = fresh(m)
    r = conv.send("Cancel Jane Miller's card")
    check("options shown as buttons", r.card and r.card["kind"] == "choice"
          and len(r.card["actions"]) == 2)
    m.add(route("lock-card"), call("lock_card", client_id="C-88210", card_id="CARD-4417"))
    r = conv.send("1")
    check("typed '1' becomes the label for the model",
          m.requests[-2]["messages"][-1]["content"] == "Lock (reversible)")
    check("lock-card can use the ids found under close-card", r.status == "awaiting_confirmation")
    r = conv.send("cancel")
    check("Cancel: nothing changed", r.message.startswith("Cancelled")
          and svc.cards.get_card("CARD-4417").status == "active")

    print("\n7. Travel notice: Change dates is code, new dates go back to the model")
    m = ScriptedModel(route("travel-notice"),
                      call("find_client", query="Jane Miller"),
                      call("list_cards", client_id="C-88210"),
                      call("travel_notice", client_id="C-88210", card_id="CARD-4417",
                           destination=["Georgia (country)"], start_date=str(start),
                           end_date=str(end)))
    svc, conv = fresh(m)
    r = conv.send("Jane Miller is off to Georgia, the country, next month for two weeks")
    labels = [a["label"] for a in r.card["actions"]]
    check("panel offers Confirm, Change dates, Cancel", labels == ["Confirm", "Change dates", "Cancel"])
    calls_before = len(m.requests)
    r = conv.send("change_dates")
    check("Change dates asks, with no model call",
          r.message.startswith("What dates") and len(m.requests) == calls_before)
    m.add(route("travel-notice"),
          call("travel_notice", client_id="C-88210", card_id="CARD-4417",
               destination=["Georgia (country)"], start_date=str(start + timedelta(days=2)),
               end_date=str(end + timedelta(days=2))))
    r = conv.send("make it two days later")
    check("a new panel with the new dates", r.status == "awaiting_confirmation"
          and r.data["input"]["start_date"] == str(start + timedelta(days=2)))
    r = conv.send("confirm")
    check("travel notice added", r.status == "ok" and len(svc.cards.travel_notices) == 1)

    print("\n8. A refusal from the guardrail goes back to the model to explain")
    m = ScriptedModel(route("lock-card"),
                      call("find_client", query="Sarah Chen 4409"),
                      call("list_cards", client_id="C-44090"),
                      call("lock_card", client_id="C-44090", card_id="CARD-9902"),
                      say("That card is already locked."))
    _, conv = fresh(m)
    r = conv.send("Lock Sarah Chen's card, account 4409")
    lookup = json.loads(m.requests[2]["messages"][-1]["content"])
    check("account last four picks the right Sarah Chen, no question",
          [c["client_id"] for c in lookup["clients"]] == ["C-44090"])
    check("already_locked explained", r.message == "That card is already locked.")
    check("the refusal reached the model",
          "already_locked" in m.requests[-1]["messages"][-1]["content"])

    print("\n9. Lost or stolen: the follow-up is fixed text from code")
    m = ScriptedModel(route("report-lost-stolen"),
                      call("find_client", query="Jane Miller"),
                      call("list_cards", client_id="C-88210"),
                      call("report_lost_stolen", client_id="C-88210", card_id="CARD-4417",
                           incident_type="lost"))
    _, conv = fresh(m)
    conv.send("Jane Miller lost her wallet, it was lost not stolen")
    r = conv.send("confirm")
    check("offers a replacement", r.card.get("follow_up", "").startswith("Would you like"))

    print("\n10. Another advisor's client does not exist for this advisor")
    m = ScriptedModel(route("lock-card"), call("find_client", query="Jane Miller"),
                      say("No matching client found."))
    _, conv = fresh(m, advisor="ADV-5678")
    r = conv.send("Lock Jane Miller's card")
    check("not found", "No matching client" in m.requests[-1]["messages"][-1]["content"])

    print("\n11. If the model is down, nothing changes")
    svc, conv = fresh(DownModel())
    r = conv.send("Lock Jane Miller's card")
    check("clear error", r.status == "error" and r.data.get("code") == "model_unavailable")
    check("card untouched", svc.cards.get_card("CARD-4417").status == "active")

    print("\n12. Confirm re-checks: state changed between the trips")
    m = ScriptedModel(route("lock-card"), call("find_client", query="Jane Miller"),
                      call("list_cards", client_id="C-88210"),
                      call("lock_card", client_id="C-88210", card_id="CARD-4417"))
    svc, conv = fresh(m)
    conv.send("Lock Jane Miller's card")
    svc.cards.lock("CARD-4417", "someone-else")
    r = conv.send("confirm")
    check("refused on trip 2", r.data.get("code") == "already_locked")

    print("\n13. The request sent to OpenAI")
    captured = {}

    class _Resp:
        def __init__(self, body): self.body = body
        def read(self): return self.body
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=None):
        captured["url"], captured["auth"] = req.full_url, req.get_header("Authorization")
        captured["body"] = json.loads(req.data)
        return _Resp(json.dumps({"choices": [{"message": say("ok")}]}).encode())

    real = llm_client.urllib.request.urlopen
    llm_client.urllib.request.urlopen = fake_urlopen
    try:
        client = OpenAIChatClient(api_key="sk-test", model="gpt-5.4")
        reply = client.chat([{"role": "user", "content": "hi"}],
                            tools=[llm_client.tool_schema_for_model(
                                {"name": "lock_card", "description": "d",
                                 "input_schema": {"type": "object", "properties": {}}})])
    finally:
        llm_client.urllib.request.urlopen = real
    b = captured["body"]
    check("Chat Completions endpoint", captured["url"].endswith("/v1/chat/completions"))
    check("model gpt-5.4", b["model"] == "gpt-5.4")
    check("bearer key from settings, not the message", captured["auth"] == "Bearer sk-test")
    check("function tool format", b["tools"][0]["type"] == "function"
          and b["tools"][0]["function"]["name"] == "lock_card")
    check("one tool call at a time", b["parallel_tool_calls"] is False)
    check("reply returned", reply["content"] == "ok")

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
