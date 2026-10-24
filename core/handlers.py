"""
One entry per tool: what to check, what to show, what to run.

The five guardrail steps live in core/guardrails.py and are the same for every
action. This file only holds what differs between them, which is why adding a
seventh action later is a small change.

Two kinds of check per action, both plain code:
- state_check(card)            is the card in a state that allows this action?
                               (already locked, closed, pending). Needs only the
                               card, so the chat can run it the moment the card
                               is known and answer before asking anything else.
- precheck(ti, card, services) are the filled-in values acceptable? (dates,
                               destinations, delivery address)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

from config import settings
from core import places
from core.errors import BadRequest, NotPossible
from core.models import Card


@dataclass
class ActionSpec:
    title: str
    execute: Callable            # (services, session, tool_input, card) -> dict
                                 # client-level actions get the Client instead of a card
    summary: Callable            # (tool_input, card) -> (fields, warning)
    state_check: Optional[Callable] = None   # (card) -> None, raises NotPossible
    precheck: Optional[Callable] = None      # (tool_input, card, services) -> None, raises
    confirm_label: str = "Confirm"
    # Presentation only - none of these change what runs or when.
    extra_actions: Optional[list] = None  # extra confirm-panel buttons, e.g. "Change dates"
    danger: bool = False                  # cannot be undone; drawn in red
    follow_up: Optional[str] = None       # one sentence the chat adds after success
    follow_up_actions: Optional[list] = None   # buttons under that sentence
    client_level: bool = False            # acts on the client's profile, not on a card
    ack: Optional[str] = None             # a box the advisor must tick before Confirm
    text_input: Optional[Callable] = None  # (tool_input) -> required text box on the panel
    confirm_check: Optional[Callable] = None  # (tool_input) -> raises; only on Confirm


# ---------------------------------------------------------------- shared bits

def _base_fields(card: Card) -> list[tuple[str, str]]:
    return [("Client", card.client_name),
            ("Account", f"...{card.account_last4}"),
            ("Card", f"...{card.card_last4}")]


CLOSED_MESSAGE = ("That card is closed, so it can't be changed. "
                  "I can order a replacement card instead.")


def _reject_if_closed(card: Card) -> None:
    if card.status == "closed":
        raise NotPossible("card_closed", CLOSED_MESSAGE)


def _pending_rule(tool: str, card: Card) -> None:
    """Decision D-03 (open with Ben): what a pending card allows. See settings."""
    if card.status == "pending" and tool not in settings.PENDING_CARD_ACTIONS:
        allowed = " or ".join(sorted(
            {"lock_card": "lock it", "replace_card": "order a replacement (for example "
             "if it never arrived)", "unlock_card": "unlock it", "close_card": "close it",
             "report_lost_stolen": "report it lost or stolen",
             "travel_notice": "add a travel notice"}[t]
            for t in settings.PENDING_CARD_ACTIONS))
        raise NotPossible("card_pending",
                          f"Card ...{card.card_last4} is pending: it has been issued but not "
                          f"activated yet." + (f" For a pending card I can {allowed}." if allowed else ""))


# ---------------------------------------------------------------- lock

def _lock_state(card):
    _reject_if_closed(card)
    _pending_rule("lock_card", card)
    if card.status == "locked":
        raise NotPossible("already_locked", f"Card ...{card.card_last4} is already locked.")


def _lock_execute(svc, session, ti, card):
    return svc.cards.lock(card.card_id, session.advisor_id, reason=ti.get("reason"))


# ---------------------------------------------------------------- unlock

def _unlock_state(card):
    _reject_if_closed(card)
    _pending_rule("unlock_card", card)
    if card.status == "active":
        raise NotPossible("not_locked", f"Card ...{card.card_last4} is not locked, so there "
                                        "is nothing to unlock.")


def _unlock_execute(svc, session, ti, card):
    return svc.cards.unlock(card.card_id, session.advisor_id)


# ---------------------------------------------------------------- replace

def _replace_state(card):
    # A closed card can be replaced: that is how the client gets a working card again.
    _pending_rule("replace_card", card)


def allowed_addresses(services, client_id: str) -> list:
    """Profile addresses a replacement may go to (decision D-02)."""
    out = []
    for a in services.clients.addresses(client_id):
        if a.country.upper() != "US" or not places.us_region(a.state):
            continue
        if places.is_po_box(a.address) and not settings.REPLACEMENT_ALLOW_PO_BOX:
            continue
        out.append(a)
    return out


def _replace_precheck(ti, card, services):
    wanted = places.normalise_address(ti["delivery_address"])
    profile = services.clients.addresses(card.client_id)
    match = next((a for a in profile if places.normalise_address(a.address) == wanted
                  or places.normalise_address(a.label) == wanted), None)
    if match is None:
        raise NotPossible(
            "address_not_in_profile",
            f"That address is not in {card.client_name}'s profile. Pick one of the "
            "addresses on file, or add a new delivery address.")
    if match.country.upper() != "US" or not places.us_region(match.state):
        raise NotPossible("address_not_us",
                          "Replacement cards can only be sent to an address in the United "
                          "States or a US territory.")
    if places.is_po_box(match.address) and not settings.REPLACEMENT_ALLOW_PO_BOX:
        raise NotPossible("address_po_box", "Replacement cards cannot be sent to a PO box.")
    ti["delivery_address"] = match.address           # always the exact profile address
    if ti.get("flag_transactions") and ti.get("reason") not in ("lost", "stolen"):
        ti["flag_transactions"] = False


def _replace_execute(svc, session, ti, card):
    return svc.cards.replace(card.card_id, session.advisor_id,
                             reason=ti["reason"], delivery_address=ti["delivery_address"],
                             flag_transactions=bool(ti.get("flag_transactions", False)))


def reason_label(ti) -> str:
    r = ti.get("reason", "")
    nice = {"not received": "Never received"}.get(r, r.capitalize())
    detail = (ti.get("reason_detail") or "").strip()
    return f"{nice}: {detail}" if detail else nice


def _replace_summary(ti, card):
    fields = _base_fields(card) + [("Reason", reason_label(ti)),
                                   ("Deliver to", ti["delivery_address"])]
    if ti.get("reason") in ("lost", "stolen"):
        fields.append(("Flag recent transactions",
                       "yes" if ti.get("flag_transactions") else "no"))
    return fields, None


# ---------------------------------------------------------------- close

def _close_state(card):
    _pending_rule("close_card", card)
    if card.status == "closed":
        raise NotPossible("card_closed", "That card is already closed.")


def _close_execute(svc, session, ti, card):
    return svc.cards.close(card.card_id, session.advisor_id, reason=ti["reason"])


# Words that only describe the closing itself - never a reason (P-06).
_NOT_REASONS = {"permanently", "permanent", "for good", "close", "closed", "closing", "cancel",
                "cancelled", "now", "please", "asap", "today", "immediately", "the card", "card",
                "it", "yes", "ok", "advisor request", "n/a", "na", "none", "-", "."}


def close_reason_problem(reason: str) -> str | None:
    """None when `reason` is a real reason; otherwise what is wrong with it."""
    r = re.sub(r"\s+", " ", (reason or "").strip())
    if not r:
        return "Please type the reason for closing the card."
    if len(r) > 200:
        return "Please keep the reason under 200 characters."
    words = [w for w in re.split(r"[^a-z']+", r.lower()) if w]
    if r.lower() in _NOT_REASONS or (words and all(w in _NOT_REASONS for w in words)):
        return f"'{r}' is not a reason. Please say why the card is being closed."
    return None


def _close_text_input(ti):
    return {"name": "reason", "label": "Reason", "required": True,
            "placeholder": "Reason for closing, e.g. switching banks",
            "value": ti.get("reason") or ""}


def _close_confirm_check(ti):
    problem = close_reason_problem(ti.get("reason", ""))
    if problem:
        raise NotPossible("reason_required", problem)
    ti["reason"] = re.sub(r"\s+", " ", ti["reason"].strip())


def _close_summary(ti, card):
    return (_base_fields(card),
            "This closes the debit card permanently and cannot be undone. The account "
            "stays open; a new card would have to be issued.")


# ---------------------------------------------------------------- lost / stolen

def _lost_state(card):
    _reject_if_closed(card)
    _pending_rule("report_lost_stolen", card)


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

def trip_days(start: date, end: date) -> int:
    """Days covered, counting both ends: 1 to 14 November is 14 days."""
    return (end - start).days + 1


def _travel_state(card):
    _reject_if_closed(card)
    _pending_rule("travel_notice", card)


def _travel_precheck(ti, card, services=None):
    try:
        start = date.fromisoformat(ti["start_date"])
        end = date.fromisoformat(ti["end_date"])
    except ValueError:
        raise NotPossible("dates_invalid", "Please pick the travel dates.")
    if end < start:
        raise NotPossible("dates_invalid", "The end date is before the start date.")
    if start < date.today():
        raise NotPossible("dates_invalid", "The start date is in the past.")
    if trip_days(start, end) > settings.MAX_TRAVEL_DAYS:
        raise NotPossible("dates_invalid",
                          f"Those dates cover {trip_days(start, end)} days, and a travel notice "
                          f"can cover at most {settings.MAX_TRAVEL_DAYS}. Please pick dates within "
                          f"{settings.MAX_TRAVEL_DAYS} days (add another notice for the rest).")

    dests = ti["destination"]
    if not dests:
        raise NotPossible("destination_invalid", "Please add at least one destination.")
    if len(dests) > settings.MAX_TRAVEL_DESTINATIONS:
        raise NotPossible("destination_invalid", f"A travel notice can list at most "
                                                 f"{settings.MAX_TRAVEL_DESTINATIONS} destinations.")
    clean = []
    for d in dests:
        kind, value = places.resolve_destination(d)
        if kind == "ambiguous":
            raise NotPossible("destination_invalid", f"'{d}' could mean {' or '.join(value)}. Which one?")
        if kind == "unknown":
            raise NotPossible("destination_invalid",
                              f"'{d}' is not a country or US state on BNY's list. "
                              "Which country or US state is it in?")
        if value not in clean:
            clean.append(value)
    ti["destination"] = clean                          # exactly as listed, e.g. "Georgia (country)"


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


# ---------------------------------------------------------------- update address (profile)

ADDRESS_ACK = "The client asked for this change and I verified their identity."


def _addr_precheck(ti, client, services):
    if client is None:
        raise BadRequest("Unknown client.")
    country, state = ti["new_country"].upper(), ti["new_state"].upper()
    if country != "US" or not places.us_region(state):
        raise NotPossible("address_not_us", "Addresses must be in the United States or a "
                                            "US territory.")
    profile = services.clients.addresses(client.client_id)
    new = places.normalise_address(ti["new_address"])
    if any(places.normalise_address(a.address) == new for a in profile):
        raise NotPossible("address_exists", "That address is already in the client's profile.")
    if ti["mode"] == "change_profile_address":
        labels = [a.label for a in profile]
        if not ti.get("address_label") and len(labels) == 1:
            ti["address_label"] = labels[0]
        if ti.get("address_label") not in labels:
            raise BadRequest("Which profile address should change?")


def _addr_summary(ti, client, services=None):
    fields = [("Client", client.name), ("Account", f"...{client.account_last4}")]
    if ti["mode"] == "change_profile_address":
        old = next((a.address for a in services.clients.addresses(client.client_id)
                    if a.label == ti["address_label"]), "") if services else ""
        fields += [("Change", ti["address_label"]), ("From", old), ("To", ti["new_address"])]
        warning = ("This changes the address in the client's profile. Cards already ordered "
                   "are not redirected.")
    else:
        fields += [("Add delivery address", ti["new_address"])]
        warning = "This adds the address to the client's profile, so replacement cards can be sent there."
    return fields, warning


def _addr_execute(svc, session, ti, client):
    from core.models import Address
    new = Address(label="", address=ti["new_address"], state=ti["new_state"].upper(),
                  country=ti["new_country"].upper())
    if ti["mode"] == "change_profile_address":
        svc.clients.change_address(client.client_id, ti["address_label"], new)
        return {"status": "address_changed", "label": ti["address_label"],
                "message": f"{client.name}'s {ti['address_label'].lower()} address is now "
                           f"{ti['new_address']}."}
    new.label = f"Delivery (added {date.today():%d %b %Y})"
    svc.clients.add_address(client.client_id, new)
    return {"status": "address_added", "label": new.label,
            "message": f"Delivery address added to {client.name}'s profile: {ti['new_address']}."}


# ---------------------------------------------------------------- registry

REPLACEMENT_OFFER = [{"label": "Yes, order a replacement", "value": "Yes, order a replacement"},
                     {"label": "No, thanks", "value": "__no__"}]

ACTIONS: dict[str, ActionSpec] = {
    "lock_card": ActionSpec(
        title="Lock debit card", execute=_lock_execute,
        summary=lambda ti, card: (_base_fields(card), None),
        state_check=_lock_state),

    "unlock_card": ActionSpec(
        title="Unlock debit card", execute=_unlock_execute,
        summary=lambda ti, card: (_base_fields(card), None),
        state_check=_unlock_state),

    "replace_card": ActionSpec(
        title="Replace debit card", execute=_replace_execute,
        summary=_replace_summary, state_check=_replace_state, precheck=_replace_precheck),

    "close_card": ActionSpec(
        title="Close debit card permanently", execute=_close_execute,
        summary=_close_summary, state_check=_close_state,
        confirm_label="Close permanently", danger=True,
        text_input=_close_text_input, confirm_check=_close_confirm_check),

    "report_lost_stolen": ActionSpec(
        title="Report card lost or stolen", execute=_lost_execute,
        summary=_lost_summary, state_check=_lost_state,
        follow_up="Would you like me to order a replacement card?",
        follow_up_actions=REPLACEMENT_OFFER),

    "travel_notice": ActionSpec(
        title="Add travel notice", execute=_travel_execute,
        summary=_travel_summary, state_check=_travel_state, precheck=_travel_precheck),

    "update_address": ActionSpec(
        title="Update client address", execute=_addr_execute,
        summary=_addr_summary, precheck=_addr_precheck,
        confirm_label="Confirm address", danger=True, client_level=True, ack=ADDRESS_ACK),
}
