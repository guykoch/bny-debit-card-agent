"""
US date and time formats, used everywhere a date is shown (cards, messages, audit).

    us_date("2026-11-20")      -> "11/20/2026"
    us_timestamp(<utc time>)   -> "11/02/2026 3:45:12 PM ET"

Times are shown in US Eastern time (BNY's New York office). Plain code: the
daylight-saving rule is computed here, so no time-zone package is needed on Vercel.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


def us_date(value) -> str:
    """'2026-11-20' or a date -> '11/20/2026'."""
    d = date.fromisoformat(value) if isinstance(value, str) else value
    return f"{d.month:02d}/{d.day:02d}/{d.year}"


def us_range(start: str, end: str) -> str:
    return f"{us_date(start)} to {us_date(end)}"


def _nth_sunday(year: int, month: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)          # first Sunday
    return d + timedelta(weeks=n - 1)


def to_eastern(utc: datetime) -> datetime:
    """UTC -> US Eastern (EDT from the 2nd Sunday of March to the 1st Sunday of November)."""
    utc = utc.astimezone(timezone.utc).replace(tzinfo=None)
    y = utc.year
    dst_start = datetime.combine(_nth_sunday(y, 3, 2), datetime.min.time()) + timedelta(hours=7)
    dst_end = datetime.combine(_nth_sunday(y, 11, 1), datetime.min.time()) + timedelta(hours=6)
    offset = -4 if dst_start <= utc < dst_end else -5
    return utc + timedelta(hours=offset)


def us_timestamp(utc: datetime | None = None) -> str:
    """'11/02/2026 3:45:12 PM ET'."""
    t = to_eastern(utc or datetime.now(timezone.utc))
    hour = t.hour % 12 or 12
    return (f"{t.month:02d}/{t.day:02d}/{t.year} {hour}:{t.minute:02d}:{t.second:02d} "
            f"{'AM' if t.hour < 12 else 'PM'} ET")
