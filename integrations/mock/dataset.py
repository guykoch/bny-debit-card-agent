"""
Loads the mock dataset from CSV.

The data lives in integrations/mock/data/*.csv so anyone on the team can edit
it in Excel without touching Python. Read that folder's README.md first.

Loaded once, at import. If you edit a CSV while something is running, restart
it.
"""

import csv
import os

_DIR = os.path.join(os.path.dirname(__file__), "data")

ALL_ACTIONS = {"view", "lock_card", "unlock_card", "replace_card", "close_card",
               "report_lost_stolen", "travel_notice"}


def _rows(filename: str) -> list[dict]:
    with open(os.path.join(_DIR, filename), newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _load_clients() -> list[dict]:
    return _rows("clients.csv")


def _load_cards() -> list[dict]:
    return _rows("cards.csv")


def _load_grants() -> dict[str, dict[str, set]]:
    """
    entitlements.csv is one row per advisor-client pair, with an `actions`
    column that is either ALL or a |-separated list. Turned into:

        {"ADV-1234": {"C-88210": {"view", "lock_card", ...}}}
    """
    grants: dict[str, dict[str, set]] = {}
    for row in _rows("entitlements.csv"):
        raw = (row.get("actions") or "").strip()
        actions = set(ALL_ACTIONS) if raw.upper() == "ALL" else {
            a.strip() for a in raw.split("|") if a.strip()}
        unknown = actions - ALL_ACTIONS
        if unknown:
            raise ValueError(
                f"entitlements.csv: unknown action(s) {sorted(unknown)} "
                f"for {row['advisor_id']} / {row['client_id']}")
        grants.setdefault(row["advisor_id"], {})[row["client_id"]] = actions
    return grants


CLIENTS = _load_clients()
CARDS = _load_cards()
GRANTS = _load_grants()


def summary() -> str:
    return (f"{len(CLIENTS)} clients, {len(CARDS)} cards, "
            f"{len(GRANTS)} advisors loaded from {os.path.relpath(_DIR)}")
