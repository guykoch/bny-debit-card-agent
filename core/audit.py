"""
The permanent record.

Every attempt is written, including refusals. Beyond what today's screens log,
we also store the advisor's own words and what the model understood them to
mean. That pairing is the evidence that a human approved a specific action
rather than a model deciding on its own.

BNY integration note: replace `_sink` with a writer that posts to Persistent
Logging. Keep the field names; they are what a reviewer will ask for.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

LOG: list[dict] = []
_EXTRA_SINKS: list = []          # e.g. the Convex store in the hosted demo
_READER = None                   # where recent rows are read from (hosted demo: Convex)

REFUSED = ("refused", "not_entitled")


def add_sink(fn) -> None:
    """Also send every row to fn(row). Used by the hosted demo to keep the audit in Convex."""
    _EXTRA_SINKS.append(fn)


def set_reader(fn) -> None:
    """Read audit rows from fn() instead of the in-process LOG (stateless hosting)."""
    global _READER
    _READER = fn


def recent_count(advisor_id: str, action: str, minutes: int) -> int:
    """Completed (not refused) actions of one kind by this advisor in the last N minutes."""
    try:
        rows = _READER() if _READER else LOG
    except Exception:
        rows = LOG
    cutoff = datetime.now(timezone.utc).timestamp() - minutes * 60
    n = 0
    for r in rows or []:
        if r.get("advisor_id") != advisor_id or r.get("action") != action:
            continue
        if r.get("outcome") in REFUSED:
            continue
        try:
            if datetime.fromisoformat(r["timestamp"]).timestamp() >= cutoff:
                n += 1
        except (KeyError, ValueError):
            continue
    return n


def _sink(row: dict) -> None:
    """Replace this in production. Must never raise into the caller."""
    LOG.append(row)
    for fn in _EXTRA_SINKS:
        try:
            fn(row)
        except Exception:        # the audit must never break the action it records
            pass


def write(
    session,
    action: str,
    client_id: Optional[str] = None,
    card_id: Optional[str] = None,
    outcome: str = "ok",
    model_interpretation: Optional[dict] = None,
    detail: Optional[dict[str, Any]] = None,
) -> dict:
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "advisor_id": session.advisor_id,
        "conversation_id": session.conversation_id,
        "channel": "chat",
        "action": action,
        "client_id": client_id,
        "card_id": card_id,
        "outcome": outcome,
        "advisor_typed": session.utterance or None,
        "model_understood": model_interpretation,
        "detail": detail or {},
    }
    _sink(row)
    return row


def for_client(client_id: str) -> list[dict]:
    return [r for r in LOG if r["client_id"] == client_id]


def reset() -> None:
    """Tests only."""
    LOG.clear()
