"""
What the advisor sees.

We return a small, declarative card rather than a paragraph of text. BNY's
chat renders it with its own components (the A2UI idea: we describe, they
draw). `to_text()` produces the same content as plain text, so the agent still
works if card rendering is unavailable.

Keep this vocabulary small. Three card kinds cover all six actions.
"""

from __future__ import annotations

from typing import Optional


def confirm_card(title: str, fields: list[tuple[str, str]],
                 warning: Optional[str] = None,
                 confirm_label: str = "Confirm",
                 extra_actions: Optional[list[dict]] = None,
                 danger: bool = False, ack: Optional[str] = None,
                 text_input: Optional[dict] = None) -> dict:
    """
    Shown before anything runs. The buttons are the advisor's authorisation.

    extra_actions: buttons between Confirm and Cancel, e.g. travel notice's
    {"label": "Change dates", "value": "change_dates"}. They never run the
    action; they send the advisor back to editing.
    danger: the action cannot be undone; the chat may draw Confirm in red.
    ack: a statement the advisor must tick before Confirm works; the chat then
    sends "confirm_ack" instead of "confirm" (checked again on the server).
    text_input: a required text box on the card, e.g. the reason for closing:
    {"name": "reason", "label": "Reason", "placeholder": "...", "value": "",
     "required": True}. Confirm then sends "confirm_with:{json}" (checked on the server).
    """
    return {
        "kind": "confirm",
        "title": title,
        "fields": [{"label": k, "value": v} for k, v in fields],
        "warning": warning,
        "danger": danger,
        "ack": ack,
        "text_input": text_input,
        "actions": (
            [{"label": confirm_label, "value": "confirm", "style": "primary"}]
            + [{**a, "style": "alternative"} for a in (extra_actions or [])]
            + [{"label": "Cancel", "value": "cancel", "style": "secondary"}]
        ),
    }


def result_card(title: str, message: str, fields: Optional[list[tuple[str, str]]] = None) -> dict:
    """Shown after the action ran."""
    return {
        "kind": "result",
        "title": title,
        "message": message,
        "fields": [{"label": k, "value": v} for k, v in (fields or [])],
    }


CANCEL = {"label": "Cancel", "value": "__cancel__", "style": "cancel"}


def choice_card(title: str, question: str, options: list[dict], cancel: bool = True) -> dict:
    """
    Shown when we must ask rather than guess — two clients with one name,
    "Georgia" the state or the country, which card.

    Each option: {"label": "Sarah Chen - acct ...4409", "value": "C-44090"}
    """
    return {
        "kind": "choice",
        "title": title,
        "message": question,
        "actions": [{**o, "style": o.get("style", "option")} for o in options]
                   + ([dict(CANCEL)] if cancel else []),
    }


def client_input_card(question: str = "Which client is this for?") -> dict:
    """A client-name field with suggestions from this advisor's own clients."""
    return {"kind": "client_input", "title": "Which client?", "message": question,
            "actions": [dict(CANCEL)]}


def travel_form_card(question: str, destinations: list[str], start: str, end: str,
                     max_days: int, max_destinations: int) -> dict:
    """Destinations (from BNY's list, with suggestions) and From / To dates."""
    return {"kind": "travel_form", "title": "Travel notice", "message": question,
            "destinations": destinations, "start": start, "end": end,
            "max_days": max_days, "max_destinations": max_destinations,
            "actions": [dict(CANCEL)]}


def text_input_card(title: str, question: str, placeholder: str, submit: str = "Continue") -> dict:
    """One required text box, e.g. "Please specify the reason"."""
    return {"kind": "text_input", "title": title, "message": question,
            "placeholder": placeholder, "submit": submit, "actions": [dict(CANCEL)]}


def address_input_card(title: str, question: str, extra: Optional[list[dict]] = None) -> dict:
    """
    An address field with suggestions as the advisor types (US and territories).
    Picking a suggestion sends "address_pick:<id>|<apt line>"; the server looks the
    full address up again - the browser never supplies the address itself.
    """
    return {
        "kind": "address_input",
        "title": title,
        "message": question,
        "actions": [{**a, "style": "secondary"} for a in (extra or [])],
    }


def to_text(card: dict) -> str:
    """Plain-text fallback. Same content, no rendering required."""
    if card is None:
        return ""
    lines = [card.get("title", "")]
    if card.get("message"):
        lines.append(card["message"])
    for f in card.get("fields", []):
        lines.append(f"  {f['label']}: {f['value']}")
    if card.get("warning"):
        lines.append(f"  ! {card['warning']}")
    if card.get("kind") == "address_input":
        lines.append("  (type the address and pick a suggestion)")
    if card.get("kind") == "client_input":
        lines.append("  (type the client's name)")
    if card.get("kind") == "travel_form":
        lines.append(f"  Destinations: {', '.join(card.get('destinations') or []) or '-'}")
        lines.append(f"  Dates: {card.get('start') or '?'} to {card.get('end') or '?'}")
    if card.get("text_input"):
        ti = card["text_input"]
        lines.append(f"  {ti.get('label', 'Text')}: {ti.get('value') or '(required)'}")
    if card.get("ack"):
        lines.append(f"  [ ] {card['ack']}")
    actions = card.get("actions", [])
    if actions:
        if card.get("kind") == "choice":
            lines += [f"  {i + 1}. {a['label']}" for i, a in enumerate(actions)]
        else:
            lines.append("  [" + "] [".join(a["label"] for a in actions) + "]")
    return "\n".join(x for x in lines if x)
