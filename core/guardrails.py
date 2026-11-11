"""
THE FILE THAT MATTERS.

Every request, read or write, passes through dispatch(). The five steps below
run in this order and cannot be skipped, reordered, or reached around. The
model produces a request; this decides whether it happens.

    1. entitlement   may this advisor perform THIS action on THIS account?
    2. ownership     does the card actually belong to that client?
    3. confirmation  has the advisor approved the summary? (writes only)
    4. action        one call to the card system
    5. audit         always, including refusals (every refusal is logged)

Two more rules run alongside them:
    - card state     already locked, closed, pending (handlers.state_check)
    - volume limit   at most N closes/replacements/reports per advisor in a
                     time window (settings.VOLUME_LIMITS)

On entitlement
--------------
BNY's orchestrator checks entitlement before routing, and only sends us
requests it has already approved. We can trust that (step 1 skipped, the audit
records that the check was made upstream) or check again ourselves.

TRUST_UPSTREAM_ENTITLEMENT is now False in config/settings.py, so step 1 runs
here as well (the demo has no BNY layer in front of it). The one case where that matters is granularity — the upstream
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
from core.errors import AgentError, BadRequest, NotEntitled, NotPossible
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
        if schemas.load().get(tool_name, {}).get("access") == "write" or e.code == "not_entitled":
            log_refusal(session, tool_name, tool_input, e, services)
        return ToolResponse(status="error", message=e.message,
                            data={"code": e.code})


def log_refusal(session, tool_name, tool_input, error: AgentError, services=None) -> None:
    """F-07: every refusal is in the audit, not only completed actions."""
    ti = tool_input if isinstance(tool_input, dict) else {}
    name, last4 = _names(services, ti.get("client_id"), ti.get("card_id"))
    audit.write(session, tool_name, ti.get("client_id"), ti.get("card_id"),
                outcome="not_entitled" if error.code == "not_entitled" else "refused",
                model_interpretation=ti or None,
                detail={"code": error.code, "message": error.message,
                        "entitlement_checked_by": _checked_by()},
                client_name=name, card_last4=last4, message=error.message)


def _names(services, client_id, card_id):
    """Client name and card last four for the audit (never raises)."""
    name = last4 = None
    try:
        if services and card_id:
            card = services.cards.get_card(card_id)
            if card:
                name, last4 = card.client_name, card.card_last4
        if services and client_id and not name:
            client = services.clients.get(client_id)
            name = client.name if client else None
    except Exception:
        pass
    return name, last4


def _checked_by() -> str:
    return "bny_orchestrator" if settings.TRUST_UPSTREAM_ENTITLEMENT else "agent"


# ---------------------------------------------------------------- early checks
# The chat calls these as soon as it knows the client / the card, so a request
# that can never go through is refused before any follow-up question. They are
# the same checks _write() runs again at the panel and at Confirm.

def check_permission(services, session, client_id: str, tool_name: str) -> None:
    """Raises NotEntitled (and logs it) when this advisor may not do this action."""
    if settings.TRUST_UPSTREAM_ENTITLEMENT:
        return
    if not services.entitlements.can(session.advisor_id, client_id, tool_name):
        e = NotEntitled()
        log_refusal(session, tool_name, {"client_id": client_id}, e, services)
        raise e


def check_card_state(services, session, tool_name: str, card) -> None:
    """Raises NotPossible (and logs it) when the card's state rules this action out."""
    spec = ACTIONS.get(tool_name)
    if spec and spec.state_check:
        try:
            spec.state_check(card)
        except AgentError as e:
            log_refusal(session, tool_name,
                        {"client_id": card.client_id, "card_id": card.card_id}, e, services)
            raise


def _check_volume(session, tool_name: str) -> None:
    limit = settings.VOLUME_LIMITS.get(tool_name)
    if not limit:
        return
    done = audit.recent_count(session.advisor_id, tool_name, settings.VOLUME_WINDOW_MINUTES)
    if done >= limit:
        what = {"replace_card": "replaced {n} cards", "stop_payment": "sent {n} stop payments",
                "check_copy": "requested {n} check copies", "misc_request": "sent {n} requests",
                "report_lost_stolen": "reported {n} cards lost or stolen",
                "address_update": "sent {n} address updates",
                "rollover_inquiry": "sent {n} deposit status inquiries"}.get(tool_name, "made {n} changes")
        raise NotPossible(
            "volume_limit",
            f"You have {what.format(n=done)} in the last {settings.VOLUME_WINDOW_MINUTES} "
            "minutes. For safety, further requests of this kind are paused for now. "
            "Please try again later or contact operations.")


# ---------------------------------------------------------------- read path

def _client_label(c) -> str:
    """F-23: city and birth year tell similar names apart."""
    bits = [c.name]
    if getattr(c, "city", ""):
        bits.append(c.city)
    if getattr(c, "birth_year", ""):
        bits.append(f"born {c.birth_year}")
    bits.append(f"acct ...{c.account_last4}")
    return " · ".join(bits)


def _read(services, session, tool_name, ti) -> ToolResponse:
    """
    Read tools never change anything, so they skip the confirmation step.
    They do NOT skip entitlement: a client this advisor cannot see must not
    appear in a list, and must not be revealed by a lookup either.
    """
    if tool_name == "find_client":
        matches = services.clients.find(ti["query"], session.advisor_id)
        similar = False
        if not matches:
            # F-24: close spellings, still limited to this advisor's clients
            finder = getattr(services.clients, "find_similar", None)
            matches = finder(ti["query"], session.advisor_id) if finder else []
            similar = bool(matches)
        if not matches:
            return ToolResponse(status="error", message="No matching client found.",
                                data={"code": "no_match"})
        if len(matches) == 1 and not similar:
            c = matches[0]
            return ToolResponse(status="ok", message=f"{c.name}, account ...{c.account_last4}",
                                data={"clients": [c.__dict__]})
        if similar:
            title = "Did you mean?"
            question = (f"No client is named exactly '{ti['query']}'. "
                        + ("Did you mean this client?" if len(matches) == 1
                           else "Did you mean one of these?"))
        else:
            title, question = "Which client?", f"{len(matches)} clients match that name."
        card = cards.choice_card(title, question,
                                 [{"label": _client_label(c), "value": c.client_id}
                                  for c in matches])
        return ToolResponse(status="needs_input", message=cards.to_text(card),
                            card=card, data={"clients": [c.__dict__ for c in matches],
                                             "similar": similar})

    if tool_name == "list_cards":
        client_id = ti["client_id"]
        if (not settings.TRUST_UPSTREAM_ENTITLEMENT
                and not services.entitlements.can(session.advisor_id, client_id, "view")):
            raise NotEntitled("You do not have permission to view that account.")
        found = services.cards.list_cards(client_id, ti.get("include_closed", False))
        return ToolResponse(status="ok",
                            message=f"{len(found)} card(s) found.",
                            data={"cards": [c.__dict__ for c in found]})

    if tool_name in ("list_accounts", "find_check"):
        client_id = ti["client_id"]
        if (not settings.TRUST_UPSTREAM_ENTITLEMENT
                and not services.entitlements.can(session.advisor_id, client_id, "view")):
            raise NotEntitled("You do not have permission to view that account.")
        accounts = services.checks.accounts(client_id)
        if tool_name == "list_accounts":
            return ToolResponse(status="ok", message=f"{len(accounts)} account(s) found.",
                                data={"accounts": [dict(a.__dict__, label=a.label)
                                                   for a in accounts]})
        if ti["account_id"] not in [a.account_id for a in accounts]:
            raise BadRequest("That account does not belong to this client.")
        chk = services.checks.find_check(ti["account_id"], ti["check_number"])
        if chk is None:
            return ToolResponse(status="error", message=f"Check {ti['check_number']} was not "
                                "found on this account.", data={"code": "check_not_found"})
        return ToolResponse(status="ok", message="Check found.", data={"check": chk.__dict__})

    raise BadRequest(f"Unknown read tool: {tool_name}")


# ---------------------------------------------------------------- write path

def _write(services, session, tool_name, ti, confirmed) -> ToolResponse:
    spec = ACTIONS[tool_name]
    client_id = ti.get("client_id") or ""
    card_id = ti.get("card_id")
    # A Misc request for the advisor's office (IBD / Office / IP #) has no client.
    office_only = (tool_name == "misc_request" and not client_id
                   and any(ti.get(k) for k in ("ibd", "office", "ip")))
    if not client_id and not office_only:
        raise BadRequest("Which client is this for?")

    # 1. entitlement
    # The audit records which side checked (setting in config/settings.py).
    checked_by = _checked_by()
    if not settings.TRUST_UPSTREAM_ENTITLEMENT and not office_only:
        if not services.entitlements.can(session.advisor_id, client_id, tool_name):
            raise NotEntitled()
    if office_only and not getattr(services.entitlements, "known_advisor", lambda a: True)(
            session.advisor_id):
        raise NotEntitled()

    if office_only:
        from core.models import Client
        from core.tickets import OFFICE_CLIENT_NAME
        target = Client(client_id="", name=OFFICE_CLIENT_NAME, account_last4="")
    elif spec.client_level:
        # Acts on the client, not a card (Service Center tickets).
        target = services.clients.get(client_id)
        if target is None:
            raise BadRequest("Unknown client.")
    else:
        # 2. ownership
        target = services.cards.get_card(card_id)
        if target is None or target.client_id != client_id:
            raise BadRequest("That card does not belong to this client.")
        # state rules for this action (already locked, closed, pending, ...)
        if spec.state_check:
            spec.state_check(target)
    # rules for the filled-in values (dates, destinations, delivery address, ...)
    if spec.precheck:
        spec.precheck(ti, target, services)
    # unusual volume (runs at the panel and again at Confirm)
    _check_volume(session, tool_name)
    # values only the advisor can give on the panel itself (e.g. the reason for closing)
    if confirmed and spec.confirm_check:
        spec.confirm_check(ti)
    if confirmed and getattr(spec, "ticket", None):
        from core import tickets
        tickets.check_attachments(services, ti)

    # 3. confirmation
    if not confirmed:
        fields, warning = (spec.summary(ti, target, services) if spec.client_level
                           else spec.summary(ti, target))
        card_payload = cards.confirm_card(spec.title, fields, warning, spec.confirm_label,
                                          extra_actions=spec.extra_actions, danger=spec.danger,
                                          ack=spec.ack,
                                          text_input=spec.text_input(ti) if spec.text_input else None)
        if getattr(spec, "ticket", None):
            from core import tickets
            card_payload["ticket"] = tickets.review(spec.ticket, ti, target, services,
                                                    session.advisor_id)
            if card_payload["ticket"]["can_edit_details"]:
                card_payload["actions"].insert(1, {"label": "Edit details",
                                                   "value": "__edit_details__",
                                                   "style": "alternative"})
        if tool_name == "travel_notice":
            # the dates are editable on the card itself (date fields, pre-filled)
            card_payload["dates"] = {"start": ti["start_date"], "end": ti["end_date"],
                                     "max_days": settings.MAX_TRAVEL_DAYS, "inline": True}
        return ToolResponse(status="awaiting_confirmation",
                            message=cards.to_text(card_payload),
                            card=card_payload,
                            data={"tool": tool_name, "input": ti})

    # 4. action (the card's summary is kept first, for the audit)
    shown, _ = (spec.summary(ti, target, services) if spec.client_level
                else spec.summary(ti, target))
    if ti.get("reason") and not any(k == "Reason" for k, _ in shown):
        shown = list(shown) + [("Reason", ti["reason"])]       # e.g. typed on the close card
    result = spec.execute(services, session, ti, target)

    # 5. audit
    detail = {k: v for k, v in result.items() if k != "message"}
    detail["entitlement_checked_by"] = checked_by
    if spec.ack:
        detail["advisor_ticked"] = spec.ack
    audit.write(session, tool_name, client_id, card_id,
                outcome=result.get("status", "ok"), model_interpretation=ti,
                detail=detail,
                client_name=getattr(target, "client_name", None) or getattr(target, "name", None),
                card_last4=getattr(target, "card_last4", None),
                summary=shown, message=result.get("message"))

    card_payload = cards.result_card(spec.title, result["message"])
    return ToolResponse(status="ok", message=result["message"],
                        card=card_payload, data=result)
