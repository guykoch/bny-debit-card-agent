"""
Checks the address feature (update an address / add a delivery address) and the
address search (autofill). Run:

    python -m tests.test_addresses

No network: the built-in sample list stands in for Google, and the Google request
is checked with a fake HTTP response.
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DCA_STORE"] = "memory"

import json

from config import settings
from integrations import address_lookup
from interfaces import a2a_server
from tests.test_fixes import fresh, labels, values
from tests.test_llm_runtime import ScriptedModel, call, route

RESULTS: dict[str, bool] = {}
PASS, FAIL = [], []


def check(tid, label, condition, detail=""):
    RESULTS[tid] = RESULTS.get(tid, True) and bool(condition)
    (PASS if condition else FAIL).append(f"{tid} {label}")
    print(f"  {'PASS' if condition else 'FAIL'}  {tid}  {label}{(' - ' + detail) if detail else ''}")


def pick_id(text):
    hits = address_lookup.suggest(text)["suggestions"]
    return hits[0]["id"] if hits else None


def run():
    settings.ADDRESS_PROVIDER = "sample"

    print("\nF-28  Update address: change an address in the profile")
    m = ScriptedModel(route("update-address"), call("find_client", query="Jane Miller"),
                      call("update_address", client_id="C-88210"))
    svc, conv = fresh(m)
    r = conv.send("Jane Miller moved, update her address")
    check("T-28a", "asks what to do, as buttons",
          values(r) == ["change_profile_address", "add_delivery_address"])
    r = conv.send("change_profile_address")
    check("T-28a", "more than one address: asks which one",
          r.card["title"] == "Which address?" and values(r) == ["Home", "Vacation home"])
    r = conv.send("Home")
    check("T-28a", "then the address search field", r.card["kind"] == "address_input"
          and "14 Hudson St" in r.card["message"])
    calls = len(m.requests)
    r = conv.send(f"address_pick:{pick_id('1 Bryant Park')}|Apt 12C")
    check("T-28a", "picked address + apt on a red panel with a tick box",
          r.status == "awaiting_confirmation" and r.card["danger"] and r.card["ack"]
          and r.data["input"]["new_address"] == "1 Bryant Park, Apt 12C, New York, NY 10036")
    check("T-28a", "no model call for the buttons or the pick", len(m.requests) == calls)
    r = conv.send("confirm")
    check("T-28a", "Confirm without the tick is refused",
          r.status == "needs_input" and "tick the box" in r.message
          and svc.clients.addresses("C-88210")[0].address.startswith("14 Hudson"))
    r = conv.send("confirm_ack")
    check("T-28a", "ticked + Confirm: the Home address changed",
          r.status == "ok" and svc.clients.addresses("C-88210")[0].address.startswith("1 Bryant Park"))
    from core import audit
    check("T-28a", "audited with the tick", audit.LOG[-1]["action"] == "update_address"
          and audit.LOG[-1]["detail"].get("advisor_ticked"))

    m = ScriptedModel(route("update-address"), call("find_client", query="Hiroshi Tanaka"),
                      call("update_address", client_id="C-13402", mode="change_profile_address"))
    svc, conv = fresh(m, "ADV-5678")
    r = conv.send("Change the address in Hiroshi Tanaka's profile")
    check("T-28b", "one address: no 'which one' question, straight to the search",
          r.card["kind"] == "address_input" and "18 Kearny St" in r.card["message"])

    print("\nF-28  Update address: add a delivery address, then offer a replacement")
    m = ScriptedModel(route("update-address"), call("find_client", query="Jane Miller"),
                      call("update_address", client_id="C-88210", mode="add_delivery_address"))
    svc, conv = fresh(m)
    r = conv.send("Add a delivery address for Jane Miller")
    check("T-28c", "mode given: straight to the search", r.card["kind"] == "address_input")
    conv.send(f"address_pick:{pick_id('233 S Wacker')}|")
    r = conv.send("confirm_ack")
    check("T-28c", "added to the profile, then 'order a replacement?' Yes / No",
          any(a.address.startswith("233 S Wacker") for a in svc.clients.addresses("C-88210"))
          and labels(r) == ["Yes, order a replacement", "No, thanks"])

    print("\nF-28  Replacement -> A different address -> add it -> back to the replacement")
    m = ScriptedModel(route("replace-card"), call("find_client", query="Jane Miller"),
                      call("list_cards", client_id="C-88210"),
                      call("replace_card", client_id="C-88210", card_id="CARD-4417",
                           reason="damaged"))
    svc, conv = fresh(m)
    conv.send("Jane Miller's card is cracked, send her a new one")
    r = conv.send("A different address")
    check("T-28d", "address search opens", r.card["kind"] == "address_input")
    r = conv.send(f"address_pick:{pick_id('1100 Congress')}|")
    check("T-28d", "panel to add the address (red, tick box)",
          r.data["input"]["mode"] == "add_delivery_address" and r.card["ack"])
    r = conv.send("confirm_ack")
    check("T-28d", "then the replacement panel to that address, with a green note",
          r.status == "awaiting_confirmation" and r.data["tool"] == "replace_card"
          and r.data["input"]["delivery_address"] == "1100 Congress Ave, Austin, TX 78701"
          and "Delivery address added" in r.card.get("note", ""))
    r = conv.send("confirm")
    check("T-28d", "replacement ordered to the new address",
          r.status == "ok" and "1100 Congress Ave" in r.message)

    print("\nF-28  The same flow with save/restore between every message (as on Vercel)")
    from interfaces.llm_runtime import GptConversation
    from core.models import Session
    m = ScriptedModel(route("replace-card"), call("find_client", query="Jane Miller"),
                      call("list_cards", client_id="C-88210"),
                      call("replace_card", client_id="C-88210", card_id="CARD-4417",
                           reason="damaged"))
    svc, conv = fresh(m)

    def hop(text):
        nonlocal conv
        r = conv.send(text)
        state = json.loads(json.dumps(conv.snapshot()))          # what Convex stores
        conv = GptConversation(svc, Session(advisor_id="ADV-1234", conversation_id="t"), client=m)
        conv.restore(state)
        return r

    hop("Jane Miller's card is cracked, send her a new one")
    hop("A different address")
    hop(f"address_pick:{pick_id('1100 Congress')}|")
    r = hop("confirm_ack")
    check("T-28h", "after save/restore: back to the replacement panel, no extra model call",
          r.status == "awaiting_confirmation" and r.data["tool"] == "replace_card"
          and len(m.queue) == 0)
    r = hop("confirm")
    check("T-28h", "replacement ordered", r.status == "ok")

    print("\nF-28  Guardrails")
    m = ScriptedModel(route("update-address"), call("find_client", query="Margaret Osei-Bonsu"))
    _, conv = fresh(m)
    r = conv.send("Update Margaret Osei-Bonsu's address")
    check("T-28e", "no permission: refused right away", r.data.get("code") == "not_entitled")

    m = ScriptedModel(route("update-address"), call("find_client", query="Jane Miller"),
                      call("update_address", client_id="C-88210", mode="add_delivery_address",
                           new_address="10 Downing St, London", new_state="", new_country="GB"))
    _, conv = fresh(m)
    r = conv.send("Add 10 Downing St, London as Jane Miller's delivery address")
    check("T-28f", "an address the model typed is ignored: the search opens instead",
          r.card["kind"] == "address_input")
    orig = address_lookup.details
    address_lookup.details = lambda pid, session="": {"address": "12 Rue de Rivoli, Paris",
                                                     "state": "", "country": "FR"}
    try:
        r = conv.send("address_pick:ChIJfake123|")
    finally:
        address_lookup.details = orig
    check("T-28f", "a picked address outside the US is refused, search stays open",
          "United States" in r.message and r.card["kind"] == "address_input")
    r = conv.send("500 Elm St Austin")
    check("T-28g", "an address typed in the chat becomes suggestion buttons",
          r.card["kind"] == "choice" and values(r)[0].startswith("address_pick:"))
    r = conv.send(values(r)[0])
    check("T-28g", "picking one continues to the panel", r.status == "awaiting_confirmation")

    print("\nF-29  Address search (autofill) service")
    out = address_lookup.suggest("hudson st new york")
    check("T-29a", "sample list suggests US addresses", out["provider"] == "sample"
          and out["suggestions"][0]["text"] == "14 Hudson St, New York, NY 10013")
    check("T-29a", "non-US addresses never suggested", not address_lookup.suggest("Paris France")
          ["suggestions"] and not address_lookup.suggest("Montreal")["suggestions"])
    settings.DEMO_PASSCODE = "pw"
    try:
        code, _, _ = a2a_server.route("GET", "/api/address/suggest?q=hudson", {}, b"")
        check("T-29b", "endpoint needs the passcode", code == 401)
        code, kind, body = a2a_server.route("GET", "/api/address/suggest?q=hudson%20st",
                                            {"X-Demo-Passcode": "pw"}, b"")
        check("T-29b", "endpoint returns suggestions",
              code == 200 and json.loads(body)["suggestions"])
    finally:
        settings.DEMO_PASSCODE = ""

    # Google Places (New): request shape and parsing, with a fake HTTP response
    seen = []

    class _Resp:
        def __init__(self, body): self.body = body
        def read(self): return json.dumps(self.body).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=None):
        seen.append(req)
        if req.full_url.endswith(":autocomplete"):
            return _Resp({"suggestions": [{"placePrediction": {
                "placeId": "ChIJabc123", "text": {"text": "500 Elm St, Austin, TX, USA"},
                "structuredFormat": {"mainText": {"text": "500 Elm St"},
                                     "secondaryText": {"text": "Austin, TX, USA"}}}}]})
        return _Resp({"formattedAddress": "500 Elm St, Austin, TX 78701, USA",
                      "addressComponents": [
                          {"longText": "500", "shortText": "500", "types": ["street_number"]},
                          {"longText": "Elm Street", "shortText": "Elm St", "types": ["route"]},
                          {"longText": "Austin", "shortText": "Austin", "types": ["locality"]},
                          {"longText": "Texas", "shortText": "TX",
                           "types": ["administrative_area_level_1"]},
                          {"longText": "United States", "shortText": "US", "types": ["country"]},
                          {"longText": "78701", "shortText": "78701", "types": ["postal_code"]}]})

    real = address_lookup.urllib.request.urlopen
    address_lookup.urllib.request.urlopen = fake_urlopen
    settings.ADDRESS_PROVIDER, settings.GOOGLE_MAPS_API_KEY = "auto", "test-key"
    try:
        out = address_lookup.suggest("500 elm", session="s1")
        body = json.loads(seen[0].data)
        check("T-29c", "Google used when a key is set", out["provider"] == "google"
              and out["suggestions"][0]["id"] == "ChIJabc123")
        check("T-29c", "key sent in a header, never in the URL",
              seen[0].headers.get("X-goog-api-key") == "test-key" and "test-key" not in seen[0].full_url)
        check("T-29c", "limited to the US and its territories",
              body["includedRegionCodes"] == ["us", "pr", "gu", "vi", "as", "mp"]
              and body["sessionToken"] == "s1")
        d = address_lookup.details("ChIJabc123", "s1")
        check("T-29c", "details parsed into one US line",
              d == {"address": "500 Elm St, Austin, TX 78701", "state": "TX", "country": "US"})
        check("T-29c", "details ask only for the address fields",
              seen[-1].headers.get("X-goog-fieldmask") == "formattedAddress,addressComponents")
    finally:
        address_lookup.urllib.request.urlopen = real
        settings.ADDRESS_PROVIDER, settings.GOOGLE_MAPS_API_KEY = "sample", ""

    def down(req, timeout=None):
        raise address_lookup.urllib.error.URLError("offline")
    address_lookup.urllib.request.urlopen = down
    settings.ADDRESS_PROVIDER, settings.GOOGLE_MAPS_API_KEY = "google", "k"
    try:
        out = address_lookup.suggest("hudson st")
        check("T-29d", "Google down: falls back to the sample list",
              out["provider"] == "sample" and out["suggestions"] and "warning" in out)
    finally:
        address_lookup.urllib.request.urlopen = real
        settings.ADDRESS_PROVIDER, settings.GOOGLE_MAPS_API_KEY = "sample", ""

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
