"""
THE FILE THAT MATTERS.

Every request, read or write, passes through dispatch(). The five steps below
run in this order and cannot be skipped, reordered, or reached around. The
model produces a request; this decides whether it happens.

    1. entitlement   may this advisor perform THIS action on THIS account?
    2. ownership     does the card actually belong to that client?
    3. confirmation  has the advisor approved the summary? (writes only)
    4. action        one call to the card system
    5. audit         always, including refusals

On entitlement
--------------
BNY's orchestrator checks entitlement before routing, and only sends us
requests it has already approved. By default we trust that: step 1 is skipped
and the audit records that the check was made upstream.

Set TRUST_UPSTREAM_ENTITLEMENT = False in config/settings.py to have step 1 run
here as well. The one case where that matters is granularity — the upstream
check may be at client level while some of our actions differ in weight. An
advisor cleared to lock a card is not necessarily cleared to close one
permanently. Worth confirming with BNY; the flag exists so the answer is a
setting rather than a rewrite.

Either way the audit row carries `entitlement_checked_by`, so the record never
implies we verified something we did not.
"""

from __future__ import annotations

from config import settings
from core import audit, cards, schemas
from core.errors import AgentError, BadRequest, NotEntitled
from core.handlers import ACTIONS
from core.models import Session, ToolResponse


def dispatch(services, session: Session, tool_name: str,
             tool_input: dict, confirmed: bool = False) -> ToolResponse:
    """Single entry point. Interfaces call this and nothing else."""
    try:
        tool_input = schemas.validate(tool_name, tool_input)
        if schemas.is_write(tool_name):
            return _write(services, session, tool_name, tool_input, confirmed)
        return _read(services, session, tool_name, tool_input)
    except AgentError as e:
        return ToolResponse(status="error", message=e.message,
                            data={"code": e.code})


# ---------------------------------------------------------------- read path

def _read(services, session, tool_name, ti) -> ToolResponse:
    """
    Read tools never change anything, so they skip the confirmation step.
    They do NOT skip entitlement: a client this advisor cannot see must not
    appear in a list, and must not be revealed by a lookup either.
    """
    if tool_name == "find_client":
        matches = services.clients.find(ti["query"], session.advisor_id)
        if not matches:
            return ToolResponse(status="error", message="No matching client found.",
                                data={"code": "no_match"})
        if len(matches) == 1:
            c = matches[0]
            return ToolResponse(status="ok", message=f"{c.name}, account ...{c.account_last4}",
                                data={"clients": [c.__dict__]})
        card = cards.choice_card(
            "Which client?",
            f"{len(matches)} clients match that name.",
            [{"label": f"{c.name} - acct ...{c.account_last4}", "value": c.client_id}
             for c in matches])
        return ToolResponse(status="needs_input", message=cards.to_text(card),
                            card=card, data={"clients": [c.__dict__ for c in matches]})

    if tool_name == "list_cards":
        client_id = ti["client_id"]
        if (not settings.TRUST_UPSTREAM_ENTITLEMENT
                and not services.entitlements.can(session.advisor_id, client_id, "view")):
            raise NotEntitled("You do not have permission to view that account.")
        found = services.cards.list_cards(client_id, ti.get("include_closed", False))
        return ToolResponse(status="ok",
                            message=f"{len(found)} card(s) found.",
                            data={"cards": [c.__dict__ for c in found]})

    raise BadRequest(f"Unknown read tool: {tool_name}")


# ---------------------------------------------------------------- write path

def _write(services, session, tool_name, ti, confirmed) -> ToolResponse:
    spec = ACTIONS[tool_name]
    client_id, card_id = ti["client_id"], ti["card_id"]

    # 1. entitlement
    # Trusted upstream by default: BNY only routes requests it has approved.
    # The flag is in config/settings.py; the audit records which side checked.
    checked_by = "bny_orchestrator"
    if not settings.TRUST_UPSTREAM_ENTITLEMENT:
        checked_by = "agent"
        if not services.entitlements.can(session.advisor_id, client_id, tool_name):
            audit.write(session, tool_name, client_id, card_id, outcome="not_entitled",
                        model_interpretation=ti,
                        detail={"entitlement_checked_by": checked_by})
            raise NotEntitled()

    # 2. ownership
    card = services.cards.get_card(card_id)
    if card is None or card.client_id != client_id:
        raise BadRequest("That card does not belong to this client.")

    # state rules for this action (already locked, closed, bad dates, ...)
    if spec.precheck:
        spec.precheck(ti, card)

    # 3. confirmation
    if not confirmed:
        fields, warning = spec.summary(ti, card)
        card_payload = cards.confirm_card(spec.title, fields, warning, spec.confirm_label)
        return ToolResponse(status="awaiting_confirmation",
                            message=cards.to_text(card_payload),
                            card=card_payload,
                            data={"tool": tool_name, "input": ti})

    # 4. action
    result = spec.execute(services, session, ti, card)

    # 5. audit
    detail = {k: v for k, v in result.items() if k != "message"}
    detail["entitlement_checked_by"] = checked_by
    audit.write(session, tool_name, client_id, card_id,
                outcome=result.get("status", "ok"), model_interpretation=ti,
                detail=detail)

    card_payload = cards.result_card(spec.title, result["message"])
    return ToolResponse(status="ok", message=result["message"],
                        card=card_payload, data=result)
