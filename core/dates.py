"""
Explicit travel dates in the advisor's words. Plain code, no AI.

Only dates the advisor actually wrote are read ("November 20 to November 30
2026", "Nov 20 - Dec 3", "20 Nov to 3 Dec", "2026-11-20 to 2026-11-30").
Vague phrases ("next week", "next month for a couple of weeks") return None:
the chat then opens the calendar so the advisor picks the dates (never assumed).
"""

from __future__ import annotations

import re
from datetime import date

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}
_MONTHS.update({k[:3]: v for k, v in list(_MONTHS.items())})
_MONTHS["sept"] = 9

_MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
_DAY = r"(\d{1,2})(?:st|nd|rd|th)?"
_YEAR = r"(?:,?\s*(\d{4}))?"
_SEP = r"\s*(?:to|until|till|through|thru|-|–|—|and)\s*"

# Month D [YYYY] to [Month] D [YYYY]
_MD = re.compile(rf"\b{_MON}\s+{_DAY}{_YEAR}{_SEP}(?:{_MON}\s+)?{_DAY}{_YEAR}\b", re.I)
# D Month [YYYY] to D [Month] [YYYY]
_DM = re.compile(rf"\b{_DAY}\s+(?:of\s+)?{_MON}{_YEAR}{_SEP}{_DAY}(?:\s+(?:of\s+)?{_MON})?{_YEAR}\b", re.I)
_ISO = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b.*?\b(\d{4}-\d{2}-\d{2})\b")


def _mk(y, m, d):
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _resolve(m1, d1, y1, m2, d2, y2, today: date):
    end_year_given = y2 is not None
    if y1 is None and y2 is not None:
        y1 = y2
    if y1 is None:
        y1 = today.year
        s = _mk(y1, m1, d1)
        if s and s < today:
            y1 += 1
    start = _mk(y1, m1, d1)
    if start is None:
        return None
    y2 = y2 if y2 is not None else start.year
    end = _mk(y2, m2, d2)
    if end is not None and end < start and not end_year_given:
        end = _mk(start.year + 1, m2, d2)          # "December 28 to January 4"
    if end is None:
        return None
    return start.isoformat(), end.isoformat()


def explicit_range(text: str, today: date | None = None) -> tuple[str, str] | None:
    """(start, end) as YYYY-MM-DD if the advisor wrote both dates, else None."""
    today = today or date.today()
    t = (text or "").replace(",", " ,").replace("  ", " ")
    m = _ISO.search(t)
    if m:
        return m.group(1), m.group(2)
    m = _MD.search(t)
    if m:
        mo1, d1, y1, mo2, d2, y2 = m.groups()
        m1 = _MONTHS[mo1.lower().rstrip(".")[:4] if mo1.lower().startswith("sept") else mo1.lower().rstrip(".")[:3]]
        m2 = _MONTHS[mo2.lower().rstrip(".")[:3]] if mo2 else m1
        return _resolve(m1, int(d1), int(y1) if y1 else None, m2, int(d2),
                        int(y2) if y2 else None, today)
    m = _DM.search(t)
    if m:
        d1, mo1, y1, d2, mo2, y2 = m.groups()
        m1 = _MONTHS[mo1.lower().rstrip(".")[:3]]
        m2 = _MONTHS[mo2.lower().rstrip(".")[:3]] if mo2 else m1
        return _resolve(m1, int(d1), int(y1) if y1 else None, m2, int(d2),
                        int(y2) if y2 else None, today)
    return None
