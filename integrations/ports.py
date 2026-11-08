"""
The boundary between our agent and BNY.

Six interfaces. Everything our agent needs from the outside world goes
through them, so swapping mocks for real systems touches nothing else.

To go live, write one class per interface in integrations/bny/ and point
config/settings.py at it. See INTEGRATION.md.
"""

from __future__ import annotations

from typing import Optional, Protocol

from core.models import Account, Address, Card, Check, Client


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

    def find_similar(self, query: str, advisor_id: str) -> list[Client]:
        """Close spellings ("Castellanos" for "Castellano"), same visibility rule as find()."""
        ...

    def addresses(self, client_id: str) -> list[Address]:
        """Every address in the client's profile. Replacements may only go to one of these."""
        ...

    def add_address(self, client_id: str, address: Address) -> None:
        """Add an address to the client's profile (e.g. a new delivery address)."""
        ...

    def change_address(self, client_id: str, label: str, address: Address) -> bool:
        """Replace the profile address saved under `label`."""
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
    integrations/bny/services.py. Signatures should not need to change;
    if they do, change them here first so the rest of the code follows.
    """

    def get_card(self, card_id: str) -> Optional[Card]: ...

    def list_cards(self, client_id: str, include_closed: bool = False) -> list[Card]: ...

    def lock(self, card_id: str, advisor_id: str, reason: Optional[str] = None) -> dict: ...

    def unlock(self, card_id: str, advisor_id: str) -> dict: ...

    def replace(self, card_id: str, advisor_id: str, reason: str,
                delivery_address: str) -> dict: ...

    def report_lost_stolen(self, card_id: str, advisor_id: str, incident_type: str,
                           last_known_use: Optional[str] = None,
                           flag_transactions: bool = False) -> dict: ...

    def add_travel_notice(self, card_id: str, advisor_id: str, destination: list[str],
                          start_date: str, end_date: str) -> dict: ...


class CheckSystem(Protocol):
    """
    Accounts that checks are written on, and the checks themselves. Read-only:
    nothing in the agent changes a check (a stop payment is a ticket).

    BNY note: map to the account and check-inquiry services.
    """

    def accounts(self, client_id: str) -> list[Account]: ...

    def find_check(self, account_id: str, check_number: str) -> Optional[Check]: ...

    def checks(self, account_id: str) -> list[Check]: ...


class ServiceCenter(Protocol):
    """
    Service Center tickets (the NetX360 request forms). Sending a ticket changes
    nothing else: BNY's servicing team processes it.

    BNY note: map submit() to the Service Center request API; the ticket's
    `fields` use the form's own field names (tickets/*.json).
    """

    def submit(self, ticket: dict) -> dict:
        """Save the ticket. Same draft_id twice returns the first ticket (no duplicates)."""
        ...

    def list_for_advisor(self, advisor_id: str) -> list[dict]:
        """This advisor's tickets, newest first."""
        ...


class AdvisorSettings(Protocol):
    """Small per-advisor preferences (e.g. the Call Back # for tickets)."""

    def get(self, advisor_id: str) -> dict: ...

    def set(self, advisor_id: str, key: str, value) -> None: ...


class FileStore(Protocol):
    """Ticket attachments. Files never reach the AI."""

    def upload_target(self) -> dict:
        """Where the browser uploads one file: {"url": ...}. Returns {"storageId": ...}."""
        ...

    def meta(self, storage_id: str) -> Optional[dict]:
        """{"size": bytes, "contentType": ...} or None if there is no such file."""
        ...

    def view_url(self, storage_id: str) -> Optional[str]:
        """A link the browser can open to view the file, or None."""
        ...
