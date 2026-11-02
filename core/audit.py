"""
The permanent record, in two logs under one "audit" heading:

  audit_actions   One row per card action that reached our checks: what was done
                  (Completed) or stopped (Refused / Not permitted), for which client
                  and card, with the details shown on the confirmation card and the
                  advisor's own words.

  audit_chat      Every line of every conversation: what the advisor typed or clicked,
                  and what the chat answered (text, card, buttons), in order.

Each row starts with the same readable columns (When, Advisor, Conversation) so the
two logs line up; "When" is US format, Eastern time ("11/02/2026 3:45:12 PM ET").
A technical copy of each action row (tool name, codes, what the model understood) is
kept under "record" for reviewers.

BNY integration note: replace the sinks with writers that post to Persistent
Logging. Keep the field names; they are what a reviewer will ask for.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from core.timefmt import us_timestamp

LOG: list[dict] = []             # audit_actions (this process)
CHAT: list[dict] = []            # audit_chat (this process)
_EXTRA_SINKS: list = []          # actions -> e.g. the Convex store in the hosted demo
_CHAT_SINKS: list = []           # chat lines -> e.g. Convex
_READER = None                   # where recent action rows are read from (hosted demo: Convex)

REFUSED = ("refused", "not_entitled")

ACTION_NAMES = {
    "lock_card": "Lock card", "unlock_card": "Unlock card", "replace_card": "Replace card",
    "close_card": "Close card permanently", "report_lost_stolen": "Report lost or stolen",
    "travel_notice": "Add travel notice", "update_address": "Update address",
}


def add_sink(fn) -> None:
    """Also send every action row to fn(row)."""
    _EXTRA_SINKS.append(fn)


def add_chat_sink(fn) -> None:
    """Also send the chat lines of each message to fn(rows)."""
    _CHAT_SINKS.append(fn)


def set_reader(fn) -> None:
    """Read action rows from fn() instead of the in-process LOG (stateless hosting)."""
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


def _send(sinks, payload) -> None:
    for fn in sinks:
        try:
            fn(payload)
        except Exception:        # the audit must never break the action it records
            pass


def _result_word(outcome: str) -> str:
    if outcome == "not_entitled":
        return "Not permitted"
    if outcome == "refused":
        return "Refused"
    return "Completed"


def write(
    session,
    action: str,
    client_id: Optional[str] = None,
    card_id: Optional[str] = None,
    outcome: str = "ok",
    model_interpretation: Optional[dict] = None,
    detail: Optional[dict[str, Any]] = None,
    client_name: Optional[str] = None,
    card_last4: Optional[str] = None,
    summary: Optional[list] = None,
    message: Optional[str] = None,
) -> dict:
    """One row in audit_actions. `summary`: the (label, value) pairs shown on the card."""
    now = datetime.now(timezone.utc)
    record = {
        "timestamp": now.isoformat(timespec="seconds"),
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
    skip = {"Client", "Account", "Card"}
    details = " | ".join(f"{k}: {v}" for k, v in (summary or []) if k not in skip and v)
    row = {
        # readable columns, in the order a reviewer reads them
        "when": us_timestamp(now),
        "advisor_id": session.advisor_id,
        "conversation_id": session.conversation_id or "",
        "action_name": ACTION_NAMES.get(action, action),
        "result": _result_word(outcome),
        "client": (f"{client_name} ({client_id})" if client_name else (client_id or "")),
        "card": f"...{card_last4}" if card_last4 else (card_id or ""),
        "details": details,
        "message": message or (detail or {}).get("message", ""),
        "advisor_request": session.utterance or "",
        "at": int(now.timestamp() * 1000),
        "record": record,
    }
    LOG.append({**record, **{k: v for k, v in row.items() if k != "record"}})
    _send(_EXTRA_SINKS, row)
    return row


def chat_turn(session, advisor_text: str, raw_input: str, input_type: str,
              reply: dict) -> list[dict]:
    """Two rows in audit_chat: the advisor's line, then the chat's answer."""
    now = datetime.now(timezone.utc)
    at = int(now.timestamp() * 1000)
    base = {"when": us_timestamp(now), "advisor_id": session.advisor_id,
            "conversation_id": session.conversation_id or ""}
    rows = [
        {**base, "speaker": "Advisor", "message": advisor_text, "input": input_type,
         "card": "", "raw_input": raw_input if raw_input != advisor_text else "", "at": at},
        {**base, "speaker": "NetX AI", "message": describe_reply(reply), "input": "",
         "card": card_name(reply), "raw_input": "", "at": at + 1},
    ]
    CHAT.extend(rows)
    _send(_CHAT_SINKS, rows)
    return rows


# ---------------------------------------------------------------- readable replies

_CARD_NAMES = {"confirm": "Confirmation", "choice": "Choice", "client_input": "Client field",
               "travel_form": "Travel form", "text_input": "Text box",
               "address_input": "Address field", "result": "Result"}


def card_name(reply: dict) -> str:
    card = (reply or {}).get("card") or {}
    name = _CARD_NAMES.get(card.get("kind"), "")
    if name and card.get("title"):
        name += f": {card['title']}"
    return name


def describe_reply(reply: dict) -> str:
    """What the advisor saw, on one line (text, card fields, buttons)."""
    reply = reply or {}
    card = reply.get("card") or {}
    kind = card.get("kind")
    if not kind:
        return (reply.get("message") or "").strip()
    parts = []
    for key in ("note", "notice", "info"):
        if card.get(key):
            parts.append(str(card[key]))
    if kind == "result":
        parts.append((reply.get("message") or "").split("\n")[0])
        if card.get("follow_up"):
            parts.append(card["follow_up"])
    elif card.get("message") and card.get("message") not in parts:
        parts.append(card["message"])
    if kind == "confirm":
        parts.append("; ".join(f"{f['label']}: {f['value']}" for f in card.get("fields", [])))
        if card.get("dates"):
            parts.append(f"Dates editable on the card")
        if (card.get("text_input") or {}).get("label"):
            parts.append(f"Required box: {card['text_input']['label']}")
        if card.get("ack"):
            parts.append(f"Tick box: {card['ack']}")
        if card.get("warning"):
            parts.append(card["warning"])
    if kind == "travel_form" and card.get("destinations"):
        parts.append("Destinations: " + ", ".join(card["destinations"]))
    actions = card.get("actions") or card.get("follow_up_actions") or []
    if actions:
        parts.append("Buttons: " + " | ".join(a["label"] for a in actions))
    return " — ".join(p for p in parts if p)


def for_client(client_id: str) -> list[dict]:
    return [r for r in LOG if r["client_id"] == client_id]


def reset() -> None:
    """Tests and the demo reset."""
    LOG.clear()
    CHAT.clear()
