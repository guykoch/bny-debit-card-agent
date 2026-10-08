"""
TEMPLATE. Nothing here works yet — on purpose.

This is the only file that needs real BNY knowledge. Fill in the three classes,
set DCA_MODE=bny, and the rest of the agent runs unchanged.

Each method below names what we need from BNY. Where our assumption turns out
to be wrong, change it here rather than anywhere in core/.
"""

from typing import Optional

from core.models import Card, Client


class BnyEntitlementService:
    """
    Needed: a way to ask "may advisor X perform action Y on account Z".

    OPEN QUESTION FOR BNY — the single most important one in this project.
    If entitlement can only be evaluated inside the AMA Suite front end, it has
    to be exposed as a callable service before any of this can ship.

    If only a coarse check is available (may this advisor deal with this client
    at all), say so explicitly here and record the limitation in the audit, so
    a reviewer knows what was and was not verified.
    """

    def can(self, advisor_id: str, client_id: str, action: str) -> bool:
        raise NotImplementedError("Map to BNY's entitlement service.")


class BnyClientDirectory:
    """
    Needed: name search scoped to the advisor's own book, and a lookup by id.

    The orchestrator's Entity Mapping may already resolve names. Keep this
    anyway as a fallback — we cannot assume a client_id always arrives.
    """

    def __init__(self, entitlements):
        self._entitlements = entitlements

    def find(self, query: str, advisor_id: str) -> list[Client]:
        raise NotImplementedError("Map to BNY's client search.")

    def get(self, client_id: str) -> Optional[Client]:
        raise NotImplementedError("Map to BNY's client lookup.")


class BnyCardSystem:
    """
    Needed: the six card actions and two lookups, as discrete calls.

    Our assumption is that each already exists as its own endpoint, because
    today's screens perform exactly these actions. Field names are ours; map
    them here.

    Mapping table to fill in with BNY:

        ours                      theirs (endpoint / method)      notes
        ------------------------  ------------------------------  -----------------
        get_card                  ?                               by card id
        list_cards                ?                               by client id
        lock                      ?                               reversible
        unlock                    ?
        replace                   ?                               reason + address
        close                     ?                               irreversible
        report_lost_stolen        ?                               blocks + flags
        add_travel_notice         ?                               dates + places

    Every method must return a dict with at least:
        {"status": "<machine readable>", "message": "<one sentence for the advisor>"}
    Raise core.errors.UpstreamUnavailable if the call fails. Never retry here;
    retrying a write without the advisor asking is not ours to decide.
    """

    def get_card(self, card_id: str) -> Optional[Card]:
        raise NotImplementedError

    def list_cards(self, client_id: str, include_closed: bool = False) -> list[Card]:
        raise NotImplementedError

    def lock(self, card_id, advisor_id, reason=None) -> dict:
        raise NotImplementedError

    def unlock(self, card_id, advisor_id) -> dict:
        raise NotImplementedError

    def replace(self, card_id, advisor_id, reason, delivery_address) -> dict:
        raise NotImplementedError

    def close(self, card_id, advisor_id, reason) -> dict:
        raise NotImplementedError

    def report_lost_stolen(self, card_id, advisor_id, incident_type,
                           last_known_use=None, flag_transactions=False) -> dict:
        raise NotImplementedError

    def add_travel_notice(self, card_id, advisor_id, destination,
                          start_date, end_date) -> dict:
        raise NotImplementedError
