"""
Places the card system accepts: travel destinations and US delivery regions.

Plain reference data, no AI. Travel notices take US states and countries from a
fixed list (per BNY: "US state and countries ... up to 10 destinations"). A
destination the advisor typed is matched here; a name that is not on the list
(a city such as "Paris") or that means two places ("Georgia") is never
guessed - the chat asks instead.
"""

from __future__ import annotations

import re

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}
US_TERRITORIES = {
    "PR": "Puerto Rico", "GU": "Guam", "VI": "US Virgin Islands",
    "AS": "American Samoa", "MP": "Northern Mariana Islands",
}

COUNTRIES = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda",
    "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain",
    "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bermuda", "Bhutan",
    "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria",
    "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia", "Cameroon", "Canada",
    "Cayman Islands", "Central African Republic", "Chad", "Chile", "China", "Colombia",
    "Comoros", "Congo", "Costa Rica", "Cote d'Ivoire", "Croatia", "Cuba", "Curacao", "Cyprus",
    "Czechia", "Democratic Republic of the Congo", "Denmark", "Djibouti", "Dominica",
    "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea",
    "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia",
    "Georgia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea",
    "Guinea-Bissau", "Guyana", "Haiti", "Honduras", "Hong Kong", "Hungary", "Iceland", "India",
    "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan",
    "Kazakhstan", "Kenya", "Kiribati", "Kosovo", "Kuwait", "Kyrgyzstan", "Laos", "Latvia",
    "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg",
    "Macau", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta",
    "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova",
    "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia",
    "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria",
    "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Panama",
    "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar",
    "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia",
    "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe",
    "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore",
    "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Korea",
    "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland",
    "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga",
    "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu", "Uganda",
    "Ukraine", "United Arab Emirates", "United Kingdom", "Uruguay", "Uzbekistan", "Vanuatu",
    "Vatican City", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe",
]

# Names that mean the same place. Lower-case keys.
ALIASES = {
    "uk": "United Kingdom", "great britain": "United Kingdom", "britain": "United Kingdom",
    "england": "United Kingdom", "scotland": "United Kingdom", "wales": "United Kingdom",
    "northern ireland": "United Kingdom", "uae": "United Arab Emirates",
    "holland": "Netherlands", "the netherlands": "Netherlands", "czech republic": "Czechia",
    "korea": "South Korea", "republic of korea": "South Korea", "ivory coast": "Cote d'Ivoire",
    "turkiye": "Turkey", "burma": "Myanmar", "swaziland": "Eswatini", "east timor": "Timor-Leste",
    "the bahamas": "Bahamas", "washington dc": "District of Columbia",
    "washington, dc": "District of Columbia", "washington d.c.": "District of Columbia",
    "dc": "District of Columbia", "usvi": "US Virgin Islands",
    "virgin islands": "US Virgin Islands", "u.s. virgin islands": "US Virgin Islands",
}

# Names that are both a country and a US state.
BOTH = {"georgia"}


def _country_label(name: str) -> str:
    return f"{name} (country)" if name.lower() in BOTH else name


def _state_label(name: str) -> str:
    return f"{name} (US state)" if name.lower() in BOTH else name


def all_destinations() -> list[str]:
    """Every name a travel notice may carry, as it is shown and stored."""
    out = [_country_label(c) for c in COUNTRIES]
    out += [_state_label(s) for s in US_STATES.values()]
    out += list(US_TERRITORIES.values())
    return sorted(set(out))


_CANONICAL = {d.lower(): d for d in all_destinations()}


def resolve_destination(text: str) -> tuple[str, object]:
    """
    ("ok", "France")  -  ("ambiguous", ["Georgia (country)", "Georgia (US state)"])
    -  ("unknown", None)
    """
    t = re.sub(r"\s+", " ", (text or "").strip()).strip(" .")
    low = t.lower()
    if not low:
        return "unknown", None
    if low in _CANONICAL:
        return "ok", _CANONICAL[low]
    if low in BOTH:
        name = t.title()
        return "ambiguous", [_country_label(name), _state_label(name)]
    if low in ALIASES:
        return "ok", ALIASES[low]
    if t.upper() in US_STATES and len(t) == 2:
        return "ok", _state_label(US_STATES[t.upper()])
    for prefix in ("the state of ", "state of "):
        if low.startswith(prefix):
            rest = t[len(prefix):]
            if rest.lower() in BOTH:
                return "ok", _state_label(rest.title())
            return resolve_destination(rest)
    if low.endswith(" state") and low[:-6] in BOTH:
        return "ok", _state_label(t[:-6].title())
    if low.endswith(" country") and low[:-8] in BOTH:
        return "ok", _country_label(t[:-8].title())
    return "unknown", None


# ---------------------------------------------------------------- delivery addresses

def us_region(state_code: str) -> bool:
    """A US state, DC or US territory (the regions a replacement may be sent to)."""
    code = (state_code or "").upper()
    return code in US_STATES or code in US_TERRITORIES


def is_po_box(address: str) -> bool:
    return bool(re.search(r"\bp\.?\s*o\.?\s*box\b", address or "", re.I))


def normalise_address(address: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (address or "").lower()).strip()


# ---------------------------------------------------------------- from the advisor's words

# Well-known cities -> the destinations on BNY's list they most likely mean.
# Used only to suggest buttons; the advisor always picks (never assumed).
CITIES = {
    "paris": ["France", "Texas"], "london": ["United Kingdom", "Kentucky"],
    "rome": ["Italy", "Georgia (US state)"], "milan": ["Italy"], "florence": ["Italy", "South Carolina"],
    "venice": ["Italy", "Florida"], "madrid": ["Spain"], "barcelona": ["Spain"],
    "lisbon": ["Portugal"], "berlin": ["Germany"], "munich": ["Germany"],
    "amsterdam": ["Netherlands"], "brussels": ["Belgium"], "vienna": ["Austria", "Virginia"],
    "zurich": ["Switzerland"], "geneva": ["Switzerland"], "dublin": ["Ireland", "Ohio"],
    "athens": ["Greece", "Georgia (US state)"], "istanbul": ["Turkey"], "prague": ["Czechia"],
    "tokyo": ["Japan"], "kyoto": ["Japan"], "osaka": ["Japan"], "seoul": ["South Korea"],
    "beijing": ["China"], "shanghai": ["China"], "hong kong": ["Hong Kong"],
    "singapore": ["Singapore"], "bangkok": ["Thailand"], "dubai": ["United Arab Emirates"],
    "tel aviv": ["Israel"], "jerusalem": ["Israel"], "cairo": ["Egypt"],
    "sydney": ["Australia"], "melbourne": ["Australia", "Florida"], "auckland": ["New Zealand"],
    "toronto": ["Canada"], "montreal": ["Canada"], "vancouver": ["Canada", "Washington"],
    "mexico city": ["Mexico"], "cancun": ["Mexico"], "rio": ["Brazil"],
    "buenos aires": ["Argentina"], "lima": ["Peru", "Ohio"],
    "new york": ["New York"], "nyc": ["New York"], "los angeles": ["California"],
    "san francisco": ["California"], "chicago": ["Illinois"], "miami": ["Florida"],
    "boston": ["Massachusetts"], "las vegas": ["Nevada"], "honolulu": ["Hawaii"],
    "orlando": ["Florida"], "seattle": ["Washington"], "austin": ["Texas"],
    "san juan": ["Puerto Rico"], "springfield": ["Illinois", "Massachusetts", "Missouri"],
    "portland": ["Oregon", "Maine"], "birmingham": ["United Kingdom", "Alabama"],
}

_STOP_AFTER = r"(?:\s+(?:next|this|on|from|for|in\s+\w+|between|starting|until|tomorrow|today|\d)|[,.;!?]|$)"


REGIONS = {"europe", "asia", "africa", "south america", "central america", "latin america",
           "caribbean", "the caribbean", "middle east", "scandinavia", "the balkans", "oceania"}
_MONTH_WORDS = {"jan", "january", "feb", "february", "mar", "march", "apr", "april", "may",
                "jun", "june", "jul", "july", "aug", "august", "sep", "sept", "september",
                "oct", "october", "nov", "november", "dec", "december", "next", "this"}


def mentioned_destinations(texts: list[str], exclude: list[str] | None = None) -> list[str]:
    """
    Raw place names the advisor wrote, in the order written: list names, aliases,
    known cities and regions found in the text, plus capitalised words after
    "to / in / visiting" (e.g. "going to Paris"). `exclude`: client names etc.
    Returns them as written; resolve_destination / CITIES decide what they mean.
    """
    text = " ".join(texts or [])
    for x in exclude or []:
        text = re.sub(re.escape(x), " ", text, flags=re.I)
    low = re.sub(r"[^\w\s'().-]", " ", text.lower())
    hits: list[tuple[int, str]] = []

    names = sorted(set([d.lower() for d in all_destinations()] + list(ALIASES) + list(BOTH)
                       + list(CITIES) + list(REGIONS)
                       + [v.lower() for v in US_STATES.values()]
                       + [v.lower() for v in US_TERRITORIES.values()]),
                   key=len, reverse=True)
    taken = low
    for n in names:
        base = n.replace(" (country)", "").replace(" (us state)", "")
        pat = r"(?<![\w])" + re.escape(n if "(" in n else base) + r"(?![\w])"
        for m in re.finditer(pat, taken):
            if base in ("may", "georgia") and base == "may":
                continue
            hits.append((m.start(), text[m.start():m.end()]))
            taken = taken[:m.start()] + " " * (m.end() - m.start()) + taken[m.end():]
    for m in re.finditer(r"\b(?:to|in|visiting|visit)\s+([A-Z][\w'.-]*(?:\s+[A-Z][\w'.-]*){0,2})",
                         text):
        words = [w for w in m.group(1).split() if w.lower().strip(".") not in _MONTH_WORDS]
        cand = " ".join(words).strip(" .")
        if not cand or cand.lower() in ("the", "a", "an", "her", "his", "their"):
            continue
        start = m.start(1)
        if any(abs(start - p) < 2 or cand.lower() in h.lower() or h.lower() in cand.lower()
               for p, h in hits):
            continue
        hits.append((start, cand))
    hits.sort()
    out: list[str] = []
    for _, h in hits:
        if h.lower() not in [o.lower() for o in out]:
            out.append(h)
    return out


def suggest_destinations(text: str, limit: int = 8) -> list[str]:
    """Destination names on BNY's list matching what the advisor is typing."""
    t = (text or "").strip().lower()
    if not t:
        return []
    every = all_destinations()
    starts = [d for d in every if d.lower().startswith(t)]
    inner = [d for d in every if t in d.lower() and d not in starts]
    out = starts + inner
    for alias, target in ALIASES.items():
        if alias.startswith(t) and target not in out:
            out.append(target)
    for city, targets in CITIES.items():
        if city.startswith(t):
            out += [x for x in targets if x not in out]
    return out[:limit]
