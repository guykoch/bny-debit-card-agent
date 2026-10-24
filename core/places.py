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
