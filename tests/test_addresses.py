"""
Checks the address feature (the Address Update ticket) and the
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

    print("\nF-28 (now F-56)  Address change is an Address Update ticket; the profile is not changed")
    from tests.test_pending import CodeOnly
    svc, conv = fresh(CodeOnly())
    before = [a.address for a in svc.clients.addresses("C-88210")]
    r = conv.send("Jane Miller moved, update her address")
    check("T-28a", "the ticket's address card (search, apartment line, phone)",
          r.card["kind"] == "ticket_address" and r.card["title"] == "New address")
    conv.send("ticket_address:" + json.dumps({"pick": pick_id("1 Bryant Park"), "unit": "Apt 12C",
                                               "phone": ""}))
    r = conv.send("callback_form:" + json.dumps({"kind": "US", "number": "2125550100", "ext": ""}))
    check("T-28a", "review card: Address Update, the new address with the unit",
          r.status == "awaiting_confirmation" and r.card["ticket"]["title"] == "Address Update"
          and "Apt 12C" in json.dumps(r.card["ticket"]))
    r = conv.send("confirm")
    check("T-28a", "Send saves a ticket; nothing in the profile changed",
          r.status == "ok" and r.data["ticket_id"].startswith("SR-")
          and [a.address for a in svc.clients.addresses("C-88210")] == before)
    r = conv.send("Change Hiroshi Tanaka's address")
    check("T-28b", "another advisor's client is not found", r.card["kind"] == "client_input")

    print("\nF-28  Guardrails")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Margaret Osei-Bonsu moved, change her address")
    check("T-28d", "no permission: refused before the address is asked",
          r.data.get("code") == "not_entitled")
    svc, conv = fresh(CodeOnly())
    r = conv.send("Jane Miller moved, change her address")
    r = conv.send("ticket_address:" + json.dumps({"pick": "", "unit": "", "phone": ""}))
    check("T-28e", "neither address nor phone: asked again",
          r.card["kind"] == "ticket_address" and r.status == "needs_input")

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
