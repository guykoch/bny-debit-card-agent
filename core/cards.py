"""
What the advisor sees.

We return a small, declarative card rather than a paragraph of text. BNY's
chat renders it with its own components (the A2UI idea: we describe, they
draw). `to_text()` produces the same content as plain text, so the agent still
works if card rendering is unavailable.

Keep this vocabulary small. Three card kinds cover all six actions.
"""

from typing import Optional


def confirm_card(title: str, fields: list[tuple[str, str]],
                 warning: Optional[str] = None,
                 confirm_label: str = "Confirm") -> dict:
    """Shown before anything runs. The buttons are the advisor's authorisation."""
    return {
        "kind": "confirm",
        "title": title,
        "fields": [{"label": k, "value": v} for k, v in fields],
        "warning": warning,
        "actions": [
            {"label": confirm_label, "value": "confirm", "style": "primary"},
            {"label": "Cancel", "value": "cancel", "style": "secondary"},
        ],
    }


def result_card(title: str, message: str, fields: Optional[list[tuple[str, str]]] = None) -> dict:
    """Shown after the action ran."""
    return {
        "kind": "result",
        "title": title,
        "message": message,
        "fields": [{"label": k, "value": v} for k, v in (fields or [])],
    }


def choice_card(title: str, question: str, options: list[dict]) -> dict:
    """
    Shown when we must ask rather than guess — two clients with one name,
    "Georgia" the state or the country, which card.

    Each option: {"label": "Sarah Chen - acct ...4409", "value": "C-44090"}
    """
    return {
        "kind": "choice",
        "title": title,
        "message": question,
        "actions": [{**o, "style": "option"} for o in options],
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
    actions = card.get("actions", [])
    if actions:
        if card.get("kind") == "choice":
            lines += [f"  {i + 1}. {a['label']}" for i, a in enumerate(actions)]
        else:
            lines.append("  [" + "] [".join(a["label"] for a in actions) + "]")
    return "\n".join(x for x in lines if x)
