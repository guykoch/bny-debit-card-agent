"""
The small set of objects every other file passes around.

Deliberately plain. No framework, no ORM. When BNY's real field names arrive,
only `from_bny()` style conversion in integrations/bny/ needs to change — the
rest of the codebase keeps using these shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Session:
    """
    Who is asking. Supplied by BNY's orchestrator over A2A.

    IMPORTANT: advisor_id never comes from the chat message itself. It comes
    from the authenticated session upstream. Nothing a user types can change it.
    """
    advisor_id: str
    utterance: str = ""
    advisor_name: str = ""
    client_id: Optional[str] = None   # orchestrator may already have resolved it
    conversation_id: Optional[str] = None


@dataclass
class Client:
    client_id: str
    name: str
    account_last4: str
    city: str = ""                   # shown in "Which client?" to tell similar names apart
    birth_year: str = ""


@dataclass
class Address:
    """One address in the client's profile. Replacements may only go to these."""
    label: str                       # "Home", "Vacation home", ...
    address: str
    state: str = ""                  # two-letter US state / territory code
    country: str = "US"


@dataclass
class Card:
    card_id: str
    client_id: str
    client_name: str
    card_last4: str
    account_last4: str
    status: str                      # active | locked | closed | pending
    address_on_file: str = ""


@dataclass
class Account:
    """A client's account that checks are written on (AMA or Resource Checking)."""
    account_id: str
    client_id: str
    account_type: str                # "AMA" | "Resource Checking"
    account_last4: str

    @property
    def label(self) -> str:
        return f"{self.account_type} ...{self.account_last4}"


@dataclass
class Check:
    """One check written on an account."""
    account_id: str
    check_number: str
    amount: str                      # "250.00"
    date_written: str                # YYYY-MM-DD
    payee: str = ""
    status: str = "outstanding"      # outstanding | posted | stopped
    posted_date: str = ""            # YYYY-MM-DD when posted


@dataclass
class ToolResponse:
    """
    What our agent returns for one tool call.

    status is one of:
      ok                      the action ran
      awaiting_confirmation   a summary is being shown, nothing has run
      needs_input             we are missing something and asked a question
      error                   refused or failed; `message` explains it plainly
    """
    status: str
    message: str = ""
    card: Optional[dict] = None      # A2UI payload, see core/cards.py
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "card": self.card,
            "data": self.data,
        }
