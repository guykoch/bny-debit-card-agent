"""
One entry per tool: what to check, what to show, what to run.

The five guardrail steps live in core/guardrails.py and are the same for every
action. This file only holds what differs between them, which is why adding a
seventh action later is a small change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

from config import settings
from core import cards
from core.errors import BadRequest, NotPossible
from core.models import Card, Session


@dataclass
class ActionSpec:
    title: str
    execute: Callable            # (services, session, tool_input, card) -> dict
    summary: Callable            # (tool_input, card) -> (fields, warning)
    precheck: Optional[Callable] = None   # (tool_input, card) -> None, raises if impossible
    confirm_label: str = "Confirm"
    # Presentation only - none of these change what runs or when.
    extra_actions: Optional[list] = None  # extra confirm-panel buttons, e.g. "Change dates"
    danger: bool = False                  # cannot be undone; drawn in red
    follow_up: Optional[str] = None       # one sentence the chat adds after success


# ---------------------------------------------------------------- shared bits

def _base_fields(card: Card) -> list[tuple[str, str]]:
    return [("Client", card.client_name),
            ("Account", f"...{card.account_last4}"),
            ("Card", f"...{card.card_last4}")]


def _reject_if_closed(card: Card) -> None:
    if card.status == "closed":
        raise NotPossible("card_closed",
                          "That card is closed and cannot be changed. A replacement would be needed.")


# ---------------------------------------------------------------- lock

def _lock_precheck(ti, card):
    _reject_if_closed(card)
    if card.status == "locked":
        raise NotPossible("already_locked", "That card is already locked.")


def _lock_execute(svc, session, ti, card):
    return svc.cards.lock(card.card_id, session.advisor_id, reason=ti.get("reason"))


# ---------------------------------------------------------------- unlock

def _unlock_precheck(ti, card):
    _reject_if_closed(card)
    if card.status == "active":
        raise NotPossible("not_locked", "That card is not locked.")


def _unlock_execute(svc, session, ti, card):
    return svc.cards.unlock(card.card_id, session.advisor_id)


# ---------------------------------------------------------------- replace

def _replace_execute(svc, session, ti, card):
    return svc.cards.replace(card.card_id, session.advisor_id,
                             reason=ti["reason"], delivery_address=ti["delivery_address"])


def _replace_summary(ti, card):
    return _base_fields(card) + [("Reason", ti["reason"]),
                                 ("Deliver to", ti["delivery_address"])], None


# ---------------------------------------------------------------- close

def _close_precheck(ti, card):
    if card.status == "closed":
        raise NotPossible("card_closed", "That card is already closed.")


def _close_execute(svc, session, ti, card):
    return svc.cards.close(card.card_id, session.advisor_id, reason=ti["reason"])


def _close_summary(ti, card):
    return (_base_fields(card) + [("Reason", ti["reason"])],
            "This cannot be undone. A new card would have to be issued.")


# ---------------------------------------------------------------- lost / stolen

def _lost_precheck(ti, card):
    _reject_if_closed(card)


def _lost_execute(svc, session, ti, card):
    return svc.cards.report_lost_stolen(
        card.card_id, session.advisor_id,
        incident_type=ti["incident_type"],
        last_known_use=ti.get("last_known_use"),
        flag_transactions=bool(ti.get("flag_transactions", False)))


def _lost_summary(ti, card):
    return _base_fields(card) + [
        ("Reported as", ti["incident_type"]),
        ("Flag recent transactions", "yes" if ti.get("flag_transactions") else "no"),
    ], None


# ---------------------------------------------------------------- travel notice

def _travel_precheck(ti, card):
    _reject_if_closed(card)
    try:
        start = date.fromisoformat(ti["start_date"])
        end = date.fromisoformat(ti["end_date"])
    except ValueError:
        raise BadRequest("Dates must be written as YYYY-MM-DD.")
    if end < start:
        raise BadRequest("The end date is before the start date.")
    if (end - start).days > settings.MAX_TRAVEL_DAYS:
        raise BadRequest(f"Travel notices cannot exceed {settings.MAX_TRAVEL_DAYS} days.")
    if start < date.today():
        raise BadRequest("The start date is in the past.")


def _travel_execute(svc, session, ti, card):
    return svc.cards.add_travel_notice(
        card.card_id, session.advisor_id,
        destination=ti["destination"],
        start_date=ti["start_date"], end_date=ti["end_date"])


def _readable(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d:%b %Y}"                      # 6 Nov 2026


def _travel_summary(ti, card):
    return _base_fields(card) + [
        ("Destination", ", ".join(ti["destination"])),
        ("Dates", f"{_readable(ti['start_date'])} to {_readable(ti['end_date'])}"),
    ], None


# ---------------------------------------------------------------- registry

ACTIONS: dict[str, ActionSpec] = {
    "lock_card": ActionSpec(
        title="Lock debit card", execute=_lock_execute,
        summary=lambda ti, card: (_base_fields(card), None),
        precheck=_lock_precheck),

    "unlock_card": ActionSpec(
        title="Unlock debit card", execute=_unlock_execute,
        summary=lambda ti, card: (_base_fields(card), None),
        precheck=_unlock_precheck),

    "replace_card": ActionSpec(
        title="Replace debit card", execute=_replace_execute,
        summary=_replace_summary,
        precheck=lambda ti, card: _reject_if_closed(card)),

    "close_card": ActionSpec(
        title="Close debit card permanently", execute=_close_execute,
        summary=_close_summary, precheck=_close_precheck,
        confirm_label="Close permanently", danger=True),

    "report_lost_stolen": ActionSpec(
        title="Report card lost or stolen", execute=_lost_execute,
        summary=_lost_summary, precheck=_lost_precheck,
        follow_up="Would you like me to order a replacement card?"),

    "travel_notice": ActionSpec(
        title="Add travel notice", execute=_travel_execute,
        summary=_travel_summary, precheck=_travel_precheck,
        extra_actions=[{"label": "Change dates", "value": "change_dates"}]),
}
