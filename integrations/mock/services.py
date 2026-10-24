"""
Mock implementations of the three interfaces in integrations/ports.py.

Client, card and entitlement records are loaded from CSV — see
integrations/mock/data/README.md. Nothing here talks to a network. Statuses
change in memory, so a demo can run the whole flow and show a card panel
updating; restarting resets everything to what the CSVs say.
"""

from __future__ import annotations

import copy
import difflib
from typing import Optional

from config import settings
from core.models import Address, Card, Client
from integrations.mock import dataset as data


class MemoryAddressBook:
    """Each client's profile addresses, in this process (changes reset on restart)."""
    def __init__(self):
        self._rows = copy.deepcopy(data.ADDRESSES)

    def list(self, client_id: str) -> list[dict]:
        return [dict(a) for a in self._rows.get(client_id, [])]

    def add(self, client_id: str, row: dict) -> None:
        self._rows.setdefault(client_id, []).append(dict(row))

    def update(self, client_id: str, label: str, row: dict) -> bool:
        for a in self._rows.get(client_id, []):
            if a["label"] == label:
                a.update(row)
                return True
        return False


class MockClientDirectory:
    def __init__(self, entitlements, address_book=None):
        self._entitlements = entitlements
        self._clients = [Client(**c) for c in data.CLIENTS]
        self._book = address_book or MemoryAddressBook()

    def find(self, query: str, advisor_id: str) -> list[Client]:
        """Every word of the query must appear in the name, so "Sarah Chen"
        also matches "Sarah M. Chen" — the ambiguous case we must handle."""
        tokens = query.lower().split()
        matches = [c for c in self._clients
                   if all(t in c.name.lower() for t in tokens)]
        # Clients this advisor cannot see simply do not exist as far as they know.
        return [c for c in matches
                if self._entitlements.can(advisor_id, c.client_id, "view")]

    def get(self, client_id: str) -> Optional[Client]:
        return next((c for c in self._clients if c.client_id == client_id), None)

    def find_similar(self, query: str, advisor_id: str) -> list[Client]:
        """
        Close spellings, e.g. "Robert Castellanos" -> Robert Castellano. Every word of
        the query must closely match a word of the name. Same visibility rule as
        find(): clients this advisor cannot see are never suggested.
        """
        tokens = [t for t in query.lower().replace(".", " ").split() if t]
        if not tokens:
            return []

        def close(token, words):
            return any(w.startswith(token) or difflib.SequenceMatcher(None, token, w).ratio() >= 0.8
                       for w in words)

        out = []
        for c in self._clients:
            words = c.name.lower().replace(".", " ").replace("-", " ").split()
            words += [c.name.lower()]
            if all(close(t, words) for t in tokens) and \
                    self._entitlements.can(advisor_id, c.client_id, "view"):
                out.append(c)
        return out

    def addresses(self, client_id: str) -> list[Address]:
        return [Address(**a) for a in self._book.list(client_id)]

    def add_address(self, client_id: str, address: Address) -> None:
        self._book.add(client_id, address.__dict__)

    def change_address(self, client_id: str, label: str, address: Address) -> bool:
        """Replace the address under `label` (the label stays)."""
        return self._book.update(client_id, label, {"address": address.address,
                                                    "state": address.state,
                                                    "country": address.country})


class MockEntitlementService:
    def can(self, advisor_id: str, client_id: str, action: str) -> bool:
        granted = data.GRANTS.get(advisor_id, {}).get(client_id)
        if granted is None:
            return False                       # no row: the client does not exist for them
        if settings.PERMISSION_MODEL == "all_or_nothing":
            return True                        # D-01 option: any access means full access
        return action in granted


class MockCardSystem:
    def __init__(self):
        self._cards = {c["card_id"]: Card(**c) for c in copy.deepcopy(data.CARDS)}
        self.travel_notices: list[dict] = []
        self.flagged: list[dict] = []

    # ---- lookups
    def get_card(self, card_id: str) -> Optional[Card]:
        return self._cards.get(card_id)

    def list_cards(self, client_id: str, include_closed: bool = False) -> list[Card]:
        out = [c for c in self._cards.values() if c.client_id == client_id]
        return out if include_closed else [c for c in out if c.status != "closed"]

    # ---- actions
    def lock(self, card_id, advisor_id, reason=None) -> dict:
        self._cards[card_id].status = "locked"
        return {"status": "locked",
                "message": f"Card ending {self._cards[card_id].card_last4} is locked."}

    def unlock(self, card_id, advisor_id) -> dict:
        self._cards[card_id].status = "active"
        return {"status": "active",
                "message": f"Card ending {self._cards[card_id].card_last4} is unlocked."}

    def replace(self, card_id, advisor_id, reason, delivery_address,
                flag_transactions=False) -> dict:
        old = self._cards[card_id]
        old.status = "closed"
        new_id = f"CARD-{(abs(hash(card_id)) % 9000) + 1000}"
        self._cards[new_id] = Card(
            card_id=new_id, client_id=old.client_id, client_name=old.client_name,
            card_last4=new_id[-4:], account_last4=old.account_last4,
            status="pending", address_on_file=delivery_address)
        if flag_transactions:
            self.flagged.append({"card_id": card_id, "advisor_id": advisor_id})
        extra = " Recent transactions flagged for review." if flag_transactions else ""
        return {"status": "replacement_ordered", "new_card_id": new_id,
                "message": f"Replacement ordered, delivering to {delivery_address}.{extra}"}

    def close(self, card_id, advisor_id, reason) -> dict:
        self._cards[card_id].status = "closed"
        return {"status": "closed",
                "message": f"Card ending {self._cards[card_id].card_last4} is closed permanently."}

    def report_lost_stolen(self, card_id, advisor_id, incident_type,
                           last_known_use=None, flag_transactions=False) -> dict:
        self._cards[card_id].status = "locked"
        if flag_transactions:
            self.flagged.append({"card_id": card_id, "advisor_id": advisor_id})
        extra = " Recent transactions flagged for review." if flag_transactions else ""
        return {"status": "reported",
                "message": f"Card blocked and reported {incident_type}.{extra}"}

    def add_travel_notice(self, card_id, advisor_id, destination, start_date, end_date) -> dict:
        self.travel_notices.append({"card_id": card_id, "destination": destination,
                                    "start_date": start_date, "end_date": end_date})
        return {"status": "travel_notice_added",
                "message": f"Travel notice added for {', '.join(destination)}, "
                           f"{start_date} to {end_date}."}
