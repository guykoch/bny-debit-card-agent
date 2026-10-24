"""
Address suggestions while the advisor types (autofill), and the full address
for the one they pick.

Two providers, chosen by ADDRESS_PROVIDER in config/settings.py:

  google   Google Places API (New): Autocomplete + Place Details, limited to the
           United States and its territories. Needs GOOGLE_MAPS_API_KEY (server
           side only - the key never reaches the browser).
  sample   A small built-in list (the demo clients' addresses plus public US
           addresses). No key, no network. Used for tests, and automatically
           when no Google key is set.

Both return the same shapes, so nothing else in the code knows which one ran:
  suggest(text, session) -> [{"id": "...", "text": "full line", "main": "...", "secondary": "..."}]
  details(id, session)   -> {"address": "500 Elm St, Austin, TX 78701", "state": "TX",
                             "country": "US"}  or None

Standard library only.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from config import settings
from core import places

# Google treats the US territories as their own regions.
US_REGION_CODES = ["us", "pr", "gu", "vi", "as", "mp"]
_TERRITORY_CODES = {"PR", "GU", "VI", "AS", "MP"}


class LookupUnavailable(Exception):
    pass


# ---------------------------------------------------------------- shared helpers

_UNIT = re.compile(r"(?i)^(apt|unit|suite|ste|#|fl|floor|room|rm)\b")


def _unit_label(unit: str) -> str:
    unit = unit.strip()
    return unit if _UNIT.match(unit) else f"Apt {unit}"


def format_address(street: str, unit: str, city: str, state: str, zip_code: str) -> str:
    line1 = street.strip() + (f", {_unit_label(unit)}" if unit.strip() else "")
    rest = ", ".join(x for x in [city.strip(), f"{state} {zip_code}".strip()] if x)
    return ", ".join(x for x in [line1, rest] if x)


def with_unit(address: dict, unit: str) -> dict:
    """Add an apartment / suite line typed by the advisor to a picked address."""
    unit = (unit or "").strip()[:40]
    if not unit:
        return address
    a = dict(address)
    parts = a["address"].split(", ", 1)
    a["address"] = f"{parts[0]}, {_unit_label(unit)}" + (f", {parts[1]}" if len(parts) > 1 else "")
    return a


def is_us(address: dict) -> bool:
    return (address.get("country", "").upper() == "US"
            and places.us_region(address.get("state", "")))


# ---------------------------------------------------------------- sample provider

_SAMPLE = [
    # public buildings and landmarks (no private homes)
    "1600 Pennsylvania Ave NW, Washington, DC 20500",
    "350 5th Ave, New York, NY 10118",
    "200 Central Park West, New York, NY 10024",
    "11 Wall St, New York, NY 10005",
    "240 Greenwich St, New York, NY 10007",
    "1 Bryant Park, New York, NY 10036",
    "233 S Wacker Dr, Chicago, IL 60606",
    "111 S Michigan Ave, Chicago, IL 60603",
    "1 Market St, San Francisco, CA 94105",
    "1 Dr Carlton B Goodlett Pl, San Francisco, CA 94102",
    "100 Universal City Plaza, Universal City, CA 91608",
    "400 Broad St, Seattle, WA 98109",
    "1 Ashburton Pl, Boston, MA 02108",
    "4 Jersey St, Boston, MA 02215",
    "1100 Congress Ave, Austin, TX 78701",
    "2401 E Randol Mill Rd, Arlington, TX 76011",
    "1 Lincoln Rd, Miami Beach, FL 33139",
    "1 Biscayne Blvd, Miami, FL 33132",
    "285 Andrew Young International Blvd NW, Atlanta, GA 30313",
    "1 Independence Mall, Philadelphia, PA 19106",
    "600 Nicollet Mall, Minneapolis, MN 55402",
    "2600 Benjamin Franklin Pkwy, Philadelphia, PA 19130",
    "3600 S Las Vegas Blvd, Las Vegas, NV 89109",
    "2005 Kalia Rd, Honolulu, HI 96815",
    "1 San Juan Bautista St, San Juan, PR 00901",
    "1 Marine Corps Dr, Tamuning, GU 96913",
    "9100 Port of Sale Mall, Charlotte Amalie, VI 00802",
    "100 Main St, Hartford, CT 06103",
    "1 Station Plaza, Greenwich, CT 06830",
    "100 Summit Ave, Short Hills, NJ 07078",
]


def _sample_rows() -> list[str]:
    rows = list(_SAMPLE)
    try:
        from integrations.mock import dataset
        for addrs in dataset.ADDRESSES.values():
            rows += [a["address"] for a in addrs]
    except Exception:
        pass
    seen, out = set(), []
    for r in rows:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _parse_us(line: str) -> dict:
    m = re.search(r",\s*([A-Z]{2})\s+(\d{5})(?:-\d{4})?\s*$", line)
    state = m.group(1) if m else ""
    return {"address": line, "state": state, "country": "US" if places.us_region(state) else ""}


class SampleLookup:
    name = "sample"

    def suggest(self, text: str, session: str = "") -> list[dict]:
        tokens = [t for t in re.split(r"[\s,]+", (text or "").lower()) if t]
        if not tokens:
            return []
        out = []
        for i, line in enumerate(_sample_rows()):
            low = line.lower()
            if all(t in low for t in tokens) and _parse_us(line)["country"] == "US":
                main, _, secondary = line.partition(", ")
                out.append({"id": f"sample:{i}", "text": line, "main": main,
                            "secondary": secondary})
            if len(out) >= 5:
                break
        return out

    def details(self, place_id: str, session: str = "") -> dict | None:
        try:
            i = int(str(place_id).split(":", 1)[1])
            return _parse_us(_sample_rows()[i])
        except (IndexError, ValueError):
            return None


# ---------------------------------------------------------------- Google Places (New)

class GoogleLookup:
    name = "google"
    AUTOCOMPLETE = "https://places.googleapis.com/v1/places:autocomplete"
    DETAILS = "https://places.googleapis.com/v1/places/{id}"

    def __init__(self, api_key: str, timeout: int = 8):
        self.key, self.timeout = api_key, timeout

    def _request(self, url: str, body: dict | None = None, field_mask: str = "") -> dict:
        headers = {"X-Goog-Api-Key": self.key}
        if field_mask:
            headers["X-Goog-FieldMask"] = field_mask
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method="POST" if body is not None else "GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise LookupUnavailable(f"Google Places HTTP {e.code}: "
                                    f"{e.read().decode('utf-8', 'replace')[:200]}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise LookupUnavailable(f"Google Places not reachable: {e}") from e

    def suggest(self, text: str, session: str = "") -> list[dict]:
        body = {"input": text, "includedRegionCodes": US_REGION_CODES,
                "includedPrimaryTypes": ["street_address", "premise", "subpremise"]}
        if session:
            body["sessionToken"] = session
        try:
            data = self._request(self.AUTOCOMPLETE, body)
        except LookupUnavailable as e:
            if "HTTP 400" not in str(e):
                raise
            body.pop("includedPrimaryTypes")                  # older projects: retry plainly
            data = self._request(self.AUTOCOMPLETE, body)
        out = []
        for s in data.get("suggestions", []):
            p = s.get("placePrediction")
            if not p:
                continue
            fmt = p.get("structuredFormat") or {}
            out.append({"id": p.get("placeId", ""),
                        "text": (p.get("text") or {}).get("text", ""),
                        "main": (fmt.get("mainText") or {}).get("text", ""),
                        "secondary": (fmt.get("secondaryText") or {}).get("text", "")})
        return [o for o in out if o["id"]][:5]

    def details(self, place_id: str, session: str = "") -> dict | None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,300}", place_id or ""):
            return None
        url = self.DETAILS.format(id=place_id)
        if session:
            url += "?" + urllib.parse.urlencode({"sessionToken": session})
        data = self._request(url, field_mask="formattedAddress,addressComponents")
        return parse_google_components(data)


def parse_google_components(data: dict) -> dict | None:
    """Google's address components -> one US-style line, state and country codes."""
    comps = {}
    for c in data.get("addressComponents") or []:
        for t in c.get("types") or []:
            comps.setdefault(t, c)
    get = lambda t, k="longText": (comps.get(t) or {}).get(k, "")
    country = get("country", "shortText").upper()
    state = get("administrative_area_level_1", "shortText").upper()
    if country in _TERRITORY_CODES:                          # Puerto Rico etc.
        state, country = country, "US"
    street = " ".join(x for x in [get("street_number"), get("route", "shortText")] if x)
    unit = get("subpremise")
    city = (get("locality") or get("postal_town") or get("sublocality_level_1")
            or get("sublocality") or get("administrative_area_level_2"))
    zip_code = get("postal_code")
    if not street:
        line = data.get("formattedAddress", "")
        line = re.sub(r",\s*(USA|United States)\s*$", "", line)
    else:
        line = format_address(street, unit, city, state, zip_code)
    if not line:
        return None
    return {"address": line, "state": state, "country": country}


# ---------------------------------------------------------------- choice

def provider():
    choice = settings.ADDRESS_PROVIDER
    if choice == "auto":
        choice = "google" if settings.GOOGLE_MAPS_API_KEY else "sample"
    if choice == "google":
        return GoogleLookup(settings.GOOGLE_MAPS_API_KEY)
    return SampleLookup()


def suggest(text: str, session: str = "") -> dict:
    """What /api/address/suggest returns."""
    p = provider()
    text = (text or "").strip()[:200]
    if len(text) < 3:
        return {"provider": p.name, "suggestions": []}
    try:
        return {"provider": p.name, "suggestions": p.suggest(text, session)}
    except LookupUnavailable as e:
        fallback = SampleLookup()
        return {"provider": fallback.name, "suggestions": fallback.suggest(text),
                "warning": str(e)}


def details(place_id: str, session: str = "") -> dict | None:
    """Full address for a picked suggestion; None when it can't be resolved."""
    pid = str(place_id or "")
    p = SampleLookup() if pid.startswith("sample:") else provider()
    try:
        return p.details(pid, session)
    except LookupUnavailable:
        return None
