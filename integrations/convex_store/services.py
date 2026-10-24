"""
The card system for the hosted demo: same behaviour as MockCardSystem, but every
change is saved in Convex, so it survives between requests on a stateless host
(Vercel) and is shared by everyone using the demo link.

Implements the CardSystem interface in integrations/ports.py, so nothing in
core/ knows or cares where the cards live.
"""

from __future__ import annotations

import hashlib
import os
import random
from typing import Optional

from core.models import Card
from integrations.convex_store.client import ConvexClient
from integrations.mock import dataset as data

_CARDS_CSV = os.path.join(os.path.dirname(data.__file__), "data", "cards.csv")
_ADDRESSES_CSV = os.path.join(os.path.dirname(data.__file__), "data", "addresses.csv")
_DEFAULTS_CHECKED = False


def default_cards() -> list[dict]:
    """The saved default state: cards.csv, exactly as committed."""
    return [dict(c) for c in data.CARDS]


def default_addresses() -> list[dict]:
    """The saved default profile addresses: addresses.csv, one row per address."""
    return [{"client_id": cid, **a} for cid, rows in data.ADDRESSES.items() for a in rows]


def defaults_version() -> str:
    h = hashlib.sha256()
    for path in (_CARDS_CSV, _ADDRESSES_CSV):
        with open(path, "rb") as f:
            h.update(f.read())
    return h.hexdigest()[:16]


def ensure_defaults(client: ConvexClient) -> dict:
    """Save the default state in Convex (once per process) and seed empty tables."""
    global _DEFAULTS_CHECKED
    result = client.mutation("ensureDefaults", version=defaults_version(),
                             cards=default_cards(), addresses=default_addresses())
    _DEFAULTS_CHECKED = True
    return result


class ConvexAddressBook:
    """Profile addresses in Convex, so a change made by one teammate is seen by all."""
    def __init__(self, client: ConvexClient):
        self.client = client

    def list(self, client_id: str) -> list[dict]:
        return [{k: d[k] for k in ("label", "address", "state", "country")}
                for d in self.client.query("listAddresses", client_id=client_id)]

    def add(self, client_id: str, row: dict) -> None:
        self.client.mutation("addAddress", client_id=client_id,
                             label=row["label"], address=row["address"],
                             state=row.get("state", ""), country=row.get("country", "US"))

    def update(self, client_id: str, label: str, row: dict) -> bool:
        return bool(self.client.mutation("updateAddress", client_id=client_id, label=label,
                                         address=row["address"], state=row.get("state", ""),
                                         country=row.get("country", "US")))


class ConvexCardSystem:
    def __init__(self, client: ConvexClient = None):
        self.client = client or ConvexClient()
        if not _DEFAULTS_CHECKED:
            ensure_defaults(self.client)

    # ---- lookups
    def get_card(self, card_id: str) -> Optional[Card]:
        doc = self.client.query("getCard", card_id=card_id)
        return Card(**doc) if doc else None

    def list_cards(self, client_id: str, include_closed: bool = False) -> list[Card]:
        out = [Card(**d) for d in self.client.query("listCards", client_id=client_id)]
        out.sort(key=lambda c: c.card_id)
        return out if include_closed else [c for c in out if c.status != "closed"]

    @property
    def travel_notices(self) -> list[dict]:
        return self.client.query("listTravelNotices")

    # ---- actions (same return shapes as MockCardSystem)
    def lock(self, card_id, advisor_id, reason=None) -> dict:
        card = self.client.mutation("setCardStatus", card_id=card_id, status="locked")
        return {"status": "locked", "message": f"Card ending {card['card_last4']} is locked."}

    def unlock(self, card_id, advisor_id) -> dict:
        card = self.client.mutation("setCardStatus", card_id=card_id, status="active")
        return {"status": "active", "message": f"Card ending {card['card_last4']} is unlocked."}

    def replace(self, card_id, advisor_id, reason, delivery_address,
                flag_transactions=False) -> dict:
        old = self.client.mutation("setCardStatus", card_id=card_id, status="closed")
        while True:                                   # a new id not already in use
            new_id = f"CARD-{random.randint(1000, 9999)}"
            if self.get_card(new_id) is None:
                break
        self.client.mutation("insertCard", card={
            "card_id": new_id, "client_id": old["client_id"], "client_name": old["client_name"],
            "card_last4": new_id[-4:], "account_last4": old["account_last4"],
            "status": "pending", "address_on_file": delivery_address})
        if flag_transactions:
            self.client.mutation("addFlag", card_id=card_id, advisor_id=advisor_id)
        extra = " Recent transactions flagged for review." if flag_transactions else ""
        return {"status": "replacement_ordered", "new_card_id": new_id,
                "message": f"Replacement ordered, delivering to {delivery_address}.{extra}"}

    def close(self, card_id, advisor_id, reason) -> dict:
        card = self.client.mutation("setCardStatus", card_id=card_id, status="closed")
        return {"status": "closed",
                "message": f"Card ending {card['card_last4']} is closed permanently."}

    def report_lost_stolen(self, card_id, advisor_id, incident_type,
                           last_known_use=None, flag_transactions=False) -> dict:
        self.client.mutation("setCardStatus", card_id=card_id, status="locked")
        if flag_transactions:
            self.client.mutation("addFlag", card_id=card_id, advisor_id=advisor_id)
        extra = " Recent transactions flagged for review." if flag_transactions else ""
        return {"status": "reported", "message": f"Card blocked and reported {incident_type}.{extra}"}

    def add_travel_notice(self, card_id, advisor_id, destination, start_date, end_date) -> dict:
        self.client.mutation("addTravelNotice", card_id=card_id, destination=list(destination),
                             start_date=start_date, end_date=end_date)
        return {"status": "travel_notice_added",
                "message": f"Travel notice added for {', '.join(destination)}, "
                           f"{start_date} to {end_date}."}
