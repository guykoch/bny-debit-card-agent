"""
The boundary between our agent and BNY.

Three interfaces. Everything our agent needs from the outside world goes
through them, so swapping mocks for real systems touches nothing else.

To go live, write one class per interface in integrations/bny/ and point
config/settings.py at it. See INTEGRATION.md.
"""

from __future__ import annotations

from typing import Optional, Protocol

from core.models import Card, Client


class ClientDirectory(Protocol):
    """Looking up clients. Read-only."""

    def find(self, query: str, advisor_id: str) -> list[Client]:
        """
        Clients matching a name, limited to those this advisor may see.

        BNY note: the orchestrator's Entity Mapping may already have resolved
        the client. If so this is only used as a fallback, but keep it — we
        cannot assume a client_id always arrives.
        """
        ...

    def get(self, client_id: str) -> Optional[Client]:
        ...


class EntitlementService(Protocol):
    """
    Permission, at the level of a single action.

    BNY note: the orchestrator already checks that this advisor may deal with
    this client at all. This interface answers the narrower question — may
    they perform THIS action on THIS account. An advisor cleared to lock a
    card is not automatically cleared to close one permanently.
    """

    def can(self, advisor_id: str, client_id: str, action: str) -> bool:
        ...


class CardSystem(Protocol):
    """
    The six actions plus the lookups they need.

    BNY note: these names are ours. Map each one to the real endpoint in
    integrations/bny/card_system.py. Signatures should not need to change;
    if they do, change them here first so the rest of the code follows.
    """

    def get_card(self, card_id: str) -> Optional[Card]: ...

    def list_cards(self, client_id: str, include_closed: bool = False) -> list[Card]: ...

    def lock(self, card_id: str, advisor_id: str, reason: Optional[str] = None) -> dict: ...

    def unlock(self, card_id: str, advisor_id: str) -> dict: ...

    def replace(self, card_id: str, advisor_id: str, reason: str,
                delivery_address: str) -> dict: ...

    def close(self, card_id: str, advisor_id: str, reason: str) -> dict: ...

    def report_lost_stolen(self, card_id: str, advisor_id: str, incident_type: str,
                           last_known_use: Optional[str] = None,
                           flag_transactions: bool = False) -> dict: ...

    def add_travel_notice(self, card_id: str, advisor_id: str, destination: list[str],
                          start_date: str, end_date: str) -> dict: ...
