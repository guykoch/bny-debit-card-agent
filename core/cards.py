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


# ---------------------------------------------------------------- Service Center tickets

def check_form_card(title: str, question: str, rows: list[dict], max_rows: int,
                    amount_required: bool, notice: str = "") -> dict:
    """Check #, Amount, Date Written (MM/DD/YYYY) rows, with Add another check."""
    return {"kind": "check_form", "title": title, "message": question,
            "rows": rows or [{"check_number": "", "amount": "", "date_written": ""}],
            "max_rows": max_rows, "amount_required": amount_required, "notice": notice,
            "actions": [dict(CANCEL)]}


def callback_card(question: str, value: Optional[dict] = None) -> dict:
    """Call Back #: US (xxx-xxx-xxxx + ext) or Non-US. Saved for the advisor."""
    return {"kind": "callback_form", "title": "Call Back #", "message": question,
            "value": value or {"kind": "US", "number": "", "ext": ""},
            "actions": [dict(CANCEL)]}


def ticket_address_card(question: str, prefill: str = "", phone: str = "",
                        notice: str = "", info: str = "") -> dict:
    """New address (address search + apartment line) and/or New Phone #."""
    card = {"kind": "ticket_address", "title": "New address", "message": question,
            "prefill": prefill, "phone": phone, "actions": [dict(CANCEL)]}
    if notice:
        card["notice"] = notice
    if info:
        card["info"] = info
    return card


def fields_form_card(title: str, question: str, fields: list[dict], submit: str = "Continue",
                     notice: str = "") -> dict:
    """A few labelled boxes on one card: {id, label, value, required, multiline, placeholder}."""
    return {"kind": "fields_form", "title": title, "message": question, "inputs": fields,
            "submit": submit, "notice": notice, "actions": [dict(CANCEL)]}


def check_status_card(title: str, fields: list[tuple[str, str]], status_line: str,
                      actions: list[dict]) -> dict:
    """A looked-up check, with what can be done next as buttons (read-only)."""
    return {"kind": "check_status", "title": title, "message": status_line,
            "fields": [{"label": k, "value": v} for k, v in fields],
            "actions": [{**a, "style": a.get("style", "option")} for a in actions]}


def rollover_form_card(question: str, values: dict, fields: list[dict], info: str = "",
                       notice: str = "", missing: Optional[list] = None) -> dict:
    """
    The Retail Check Deposit Status Inquiry on one card, laid out like BNY's form:
    everything the chat could fill is filled; missing required fields are highlighted.
    """
    card = {"kind": "rollover_form", "title": "Check Deposit Status Inquiry", "message": question,
            "values": values, "form_fields": fields, "missing": missing or [],
            "actions": [dict(CANCEL)]}
    if info:
        card["info"] = info
    if notice:
        card["notice"] = notice
    return card


def to_text(card: dict) -> str:
    """Plain-text fallback. Same content, no rendering required."""
    if card is None:
        return ""
    lines = [card.get("title", "")]
    if card.get("ticket"):
        lines = [card["ticket"]["title"]]
        card = {**card, "fields": []}
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
    if card.get("kind") == "check_form":
        for r in card.get("rows") or []:
            lines.append(f"  Check #{r.get('check_number') or '?'}  Amount {r.get('amount') or '?'}"
                         f"  Date written {r.get('date_written') or '-'}")
    if card.get("kind") == "callback_form":
        lines.append("  (type the Call Back #)")
    if card.get("kind") == "rollover_form":
        for f in card.get("form_fields") or []:
            v = (card.get("values") or {}).get(f["id"]) or ("(required)" if f.get("required") else "-")
            lines.append(f"  {f['label']}: {v}")
    if card.get("kind") == "fields_form":
        for f in card.get("inputs") or []:
            lines.append(f"  {f['label']}: {f.get('value') or ('(required)' if f.get('required') else '-')}")
    if card.get("ticket"):
        t = card["ticket"]
        lines += [f"  {f['label']}: {f['value']}" for f in t.get("key", [])]
        cb = (t.get("editable") or {}).get("callback") or {}
        if cb.get("number"):
            lines.append(f"  Call Back #: {cb['number']}" + (f" ext {cb['ext']}" if cb.get("ext") else ""))
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
