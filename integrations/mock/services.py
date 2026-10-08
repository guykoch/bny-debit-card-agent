"""
Mock implementations of the three interfaces in integrations/ports.py.

Client, card and entitlement records are loaded from CSV — see
integrations/mock/data/README.md. Nothing here talks to a network. Statuses
change in memory, so a demo can run the whole flow and show a card panel
updating; restarting resets everything to what the CSVs say.
"""

import copy
from typing import Optional

from core.models import Card, Client
from integrations.mock import dataset as data


class MockClientDirectory:
    def __init__(self, entitlements):
        self._entitlements = entitlements
        self._clients = [Client(**c) for c in data.CLIENTS]

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


class MockEntitlementService:
    def can(self, advisor_id: str, client_id: str, action: str) -> bool:
        return action in data.GRANTS.get(advisor_id, {}).get(client_id, set())


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

    def replace(self, card_id, advisor_id, reason, delivery_address) -> dict:
        old = self._cards[card_id]
        old.status = "closed"
        new_id = f"CARD-{(abs(hash(card_id)) % 9000) + 1000}"
        self._cards[new_id] = Card(
            card_id=new_id, client_id=old.client_id, client_name=old.client_name,
            card_last4=new_id[-4:], account_last4=old.account_last4,
            status="pending", address_on_file=delivery_address)
        return {"status": "replacement_ordered", "new_card_id": new_id,
                "message": f"Replacement ordered, delivering to {delivery_address}."}

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
