"""
Service Center tickets: the NetX360 request forms, filled in from plain language.

Each form is a template in tickets/<tool>.json (from the Service Center screenshots).
This module turns a template into an ActionSpec, so a ticket goes through the same
five guardrail steps as a card action (permission, checks, volume, review card,
audit) - but Send only saves the ticket. Nothing else in the data changes.

Also here, plain code used by the chat to fill a ticket from the advisor's words:
check numbers, amounts, dates, phone numbers, and the "no full account or card
numbers in free text" rule from the forms.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone
from typing import Optional

from core import places
from core.dates import single_date
from core.errors import BadRequest, NotPossible
from core.timefmt import us_date, us_timestamp

_DIR = os.path.join(os.path.dirname(__file__), "..", "tickets")
_TEMPLATES: dict[str, dict] = {}

MAX_ATTACHMENTS = 5
MAX_FILE_BYTES = 10 * 1024 * 1024
FILE_TYPES = {"application/pdf": "PDF", "image/jpeg": "JPG", "image/png": "PNG"}
ATTACH_NOTE = "Attached files will not be imaged and will not appear in Online Documents."


def templates() -> dict[str, dict]:
    if not _TEMPLATES:
        for name in sorted(os.listdir(_DIR)):
            if name.endswith(".json"):
                with open(os.path.join(_DIR, name), encoding="utf-8") as f:
                    t = json.load(f)
                _TEMPLATES[t["tool"]] = t
    return _TEMPLATES


def template(tool: str) -> Optional[dict]:
    return templates().get(tool)


def is_ticket(tool: str) -> bool:
    return tool in templates()


# ---------------------------------------------------------------- reading the advisor's words

_CHECK_NO = re.compile(r"(?:\bchecks?|\bcheque|\bchk|#|\bnumber|\bno\.?)\s*(?:#|no\.?|number)?\s*"
                       r"(\d{2,10})\b", re.I)
_AMOUNT = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
                     r"|\b(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s*(?:dollars|usd|bucks)\b",
                     re.I)
_PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})(?!\d)")
LONG_DIGITS = re.compile(r"\d[\d\s-]{6,}\d")


def check_numbers(text: str) -> list[str]:
    """Check numbers as written ("check 1043", "#1043", "checks 1043 and 1044")."""
    out = [m.group(1) for m in _CHECK_NO.finditer(text or "")]
    m = re.search(r"\bchecks?\s+((?:#?\d{2,10}\s*(?:,|and|&)\s*)+#?\d{2,10})", text or "", re.I)
    if m:
        out += re.findall(r"\d{2,10}", m.group(1))
    seen, res = set(), []
    for n in out:
        if n not in seen:
            seen.add(n)
            res.append(n)
    return res


def amounts(text: str) -> list[str]:
    """Dollar amounts as written ("$250", "250 dollars", "$1,250.50") -> "250.00"."""
    out = []
    for m in _AMOUNT.finditer(text or ""):
        raw = (m.group(1) or m.group(2)).replace(",", "")
        try:
            out.append(f"{float(raw):.2f}")
        except ValueError:
            pass
    return out


def money(value: str) -> str:
    try:
        return f"${float(str(value).replace(',', '').replace('$', '')):,.2f}"
    except ValueError:
        return str(value)


def amount_ok(value) -> Optional[str]:
    """The amount as "250.00", or None if it is not a positive dollar amount."""
    try:
        v = float(str(value).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None
    return f"{v:.2f}" if 0 < v < 10_000_000 else None


def phone_in(text: str) -> Optional[str]:
    m = _PHONE.search(text or "")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def date_written_in(text: str) -> Optional[str]:
    return single_date(text, past=True)


def redact(text: str) -> str:
    """The forms' rule: never key out a full account or card number in free text."""
    return LONG_DIGITS.sub("[number removed]", text or "")


def callback_text(cb: Optional[dict]) -> str:
    if not cb or not cb.get("number"):
        return ""
    s = cb["number"] + (f" ext. {cb['ext']}" if cb.get("ext") else "")
    return s if cb.get("kind", "US") == "US" else f"{s} (Non-US)"


def callback_problem(cb) -> Optional[str]:
    if not isinstance(cb, dict) or not str(cb.get("number", "")).strip():
        return "Please add a Call Back #."
    digits = re.sub(r"\D", "", cb["number"])
    if cb.get("kind", "US") == "US":
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) != 10:
            return "A US Call Back # has 10 digits, e.g. 212-555-0142."
        cb["number"] = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    elif not (6 <= len(digits) <= 15):
        return "Please check the Call Back # (6 to 15 digits)."
    if cb.get("ext") and not re.fullmatch(r"\d{1,6}", str(cb["ext"])):
        return "The extension should be digits only."
    return None


# ---------------------------------------------------------------- the ActionSpecs

def _account(services, ti):
    if not ti.get("account_id"):
        return None
    for a in services.checks.accounts(ti["client_id"]):
        if a.account_id == ti["account_id"]:
            return a
    raise BadRequest("That account does not belong to this client.")


def _request_type(t: dict, account) -> str:
    if t.get("request_type_by_account") and account is not None:
        return t["request_type_by_account"].get(account.account_type, account.account_type)
    return t.get("request_type", "")


def _clean_checks(t, ti, services, account) -> list[dict]:
    rows = ti.get("checks") or []
    if not isinstance(rows, list) or not rows:
        raise NotPossible("checks_missing", "Please add the check details.")
    col = {c["id"]: c for c in next(f for f in t["fields"] if f["id"] == "checks")["columns"]}
    if len(rows) > next(f for f in t["fields"] if f["id"] == "checks").get("max_rows", 10):
        raise NotPossible("checks_missing", "Too many checks on one ticket.")
    out = []
    for r in rows:
        num = re.sub(r"\D", "", str(r.get("check_number", "")))
        if not num or len(num) > 10:
            raise NotPossible("checks_missing", "Each check needs a check number (digits only).")
        amt = r.get("amount")
        if amt not in (None, ""):
            amt = amount_ok(amt)
            if amt is None:
                raise NotPossible("checks_missing", f"Check {num}: the amount must be a dollar "
                                                    "amount above $0.")
        elif col["amount"].get("required"):
            raise NotPossible("checks_missing", f"Check {num}: please add the amount.")
        dw = r.get("date_written") or ""
        if dw:
            try:
                if date.fromisoformat(dw) > date.today():
                    raise NotPossible("checks_missing", f"Check {num}: the date written is in "
                                                        "the future.")
            except ValueError:
                raise NotPossible("checks_missing", f"Check {num}: the date written is not valid.")
        found = services.checks.find_check(account.account_id, num) if account else None
        if t["tool"] == "stop_payment" and found and found.status == "posted":
            raise NotPossible("check_posted", f"Check {num} was paid on "
                                              f"{us_date(found.posted_date)}, so it can't be "
                                              "stopped.")
        if t["tool"] == "stop_payment" and found and found.status == "stopped":
            raise NotPossible("check_posted", f"Check {num} already has a stop payment.")
        if t["tool"] == "check_copy" and found and found.status != "posted":
            raise NotPossible("check_not_posted", f"Check {num} hasn't been paid yet, so there "
                                                  "is no copy to request. You can stop it "
                                                  "instead.")
        out.append({"check_number": num, "amount": amt or "", "date_written": dw,
                    "on_file": bool(found)})
    return out


def _precheck(t):
    def check(ti, client, services):
        if client is None:
            raise BadRequest("Unknown client.")
        account = _account(services, ti)
        office = any(ti.get(k) for k in ("ibd", "office", "ip"))
        if account is None and not (t["tool"] == "misc_request" and office):
            raise NotPossible("account_missing", "Please pick the account.")
        for k in ("subject", "additional_info"):          # free text: the forms' red rule
            if isinstance(ti.get(k), str):
                ti[k] = redact(re.sub(r"[ \t]+", " ", ti[k]).strip())[:1000]
        for k in ("ibd", "office", "ip"):
            if isinstance(ti.get(k), str):
                ti[k] = re.sub(r"[^\w-]", "", ti[k])[:20]
        if ti.get("subject") and len(ti["subject"]) > 120:
            ti["subject"] = ti["subject"][:120]
        if t["tool"] in ("stop_payment", "check_copy"):
            ti["checks"] = _clean_checks(t, ti, services, account)
        if t["tool"] == "address_update":
            lines = [l for l in (ti.get("new_address") or []) if str(l).strip()]
            phone = (ti.get("new_phone") or "").strip()
            if not lines and not phone:
                raise NotPossible("address_missing", "Please add the new address or the new "
                                                     "phone number.")
            if lines and (str(ti.get("new_country", "US")).upper() != "US"
                          or not places.us_region(str(ti.get("new_state", "")))):
                raise NotPossible("address_missing", "The new address must be in the United "
                                                     "States or a US territory.")
            if phone:
                p = phone_in(phone)
                if not p:
                    raise NotPossible("address_missing", "Please check the phone number "
                                                         "(10 digits, e.g. 212-555-0142).")
                ti["new_phone"] = p
            ti["new_address"] = lines[:4]
        if t["tool"] == "misc_request":
            if not (ti.get("subject") or "").strip():
                raise NotPossible("subject_missing", "Please add a subject.")
            if not (ti.get("additional_info") or "").strip():
                raise NotPossible("subject_missing", "Please add the details of the request.")
        problem = callback_problem(ti.get("callback"))
        if problem:
            raise NotPossible("callback_missing", problem)
        atts = ti.get("attachments") or []
        if len(atts) > MAX_ATTACHMENTS:
            raise NotPossible("attachment_invalid", f"Up to {MAX_ATTACHMENTS} attachments per "
                                                    "ticket.")
    return check


def check_attachments(services, ti) -> None:
    """On Send: every attached file exists, is PDF/JPG/PNG and at most 10 MB."""
    clean = []
    for a in ti.get("attachments") or []:
        meta = services.files.meta(str(a.get("storage_id", ""))) if services.files else None
        if not meta:
            raise NotPossible("attachment_invalid", f"{a.get('name', 'A file')} could not be "
                                                    "found. Please attach it again.")
        if meta.get("size", 0) > MAX_FILE_BYTES:
            raise NotPossible("attachment_invalid", f"{a.get('name')} is over 10 MB.")
        if meta.get("contentType") not in FILE_TYPES:
            raise NotPossible("attachment_invalid", f"{a.get('name')}: only PDF, JPG or PNG "
                                                    "files can be attached.")
        clean.append({"storage_id": a["storage_id"], "name": str(a.get("name", ""))[:120],
                      "size": meta["size"], "type": meta["contentType"]})
    ti["attachments"] = clean


def _check_line(r: dict) -> str:
    bits = [f"Check {r['check_number']}"]
    if r.get("amount"):
        bits.append(money(r["amount"]))
    if r.get("date_written"):
        bits.append(f"written {us_date(r['date_written'])}")
    return " · ".join(bits)


def ticket_fields(t: dict, ti: dict, client, account) -> list[tuple[str, str]]:
    """Every field of the form, in form order, as label -> value (what is sent)."""
    out = [("Category", t["category"]), ("Request", t["request"]),
           ("Request Type", _request_type(t, account))]
    for f in t["fields"]:
        fid = f["id"]
        if fid == "account_id":
            out.append(("Account #", account.label if account else "—"))
        elif fid == "checks":
            for r in ti.get("checks") or []:
                out.append(("Check", _check_line(r)))
        elif fid == "new_address":
            if ti.get("new_address"):
                out.append(("New Address", ", ".join(ti["new_address"])))
        elif fid == "callback":
            out.append(("Call Back #", callback_text(ti.get("callback"))))
        elif ti.get(fid):
            out.append((f["label"], str(ti[fid])))
    return out


def _summary(t):
    def summary(ti, client, services=None):
        account = _account(services, ti) if services else None
        return ticket_fields(t, ti, client, account), None
    return summary


def review(t: dict, ti: dict, client, services) -> dict:
    """The short review card: key facts up top, everything else behind 'Show all fields'."""
    account = _account(services, ti)
    key = [("Client", client.name),
           ("Account", account.label if account else
            " · ".join(f"{k.upper()} {ti[k]}" for k in ("ibd", "office", "ip") if ti.get(k)))]
    if t["tool"] in ("stop_payment", "check_copy"):
        for r in ti.get("checks") or []:
            key.append(("Check", _check_line(r)))
    if t["tool"] == "address_update":
        if ti.get("new_address"):
            key.append(("New address", ", ".join(ti["new_address"])))
        if ti.get("new_phone"):
            key.append(("New phone", ti["new_phone"]))
    if t["tool"] == "misc_request":
        key.append(("Subject", ti.get("subject", "")))
    notes = []
    for r in ti.get("checks") or []:
        if t["tool"] == "stop_payment" and not r.get("on_file") and account is not None:
            notes.append(f"Check {r['check_number']} was not found on this account. The "
                         "Service Center will check it.")
    return {
        "tool": t["tool"], "title": t["title"],
        "form": f"{t['category']} · {t['request']} · {_request_type(t, account)}",
        "key": [{"label": k, "value": v} for k, v in key if v],
        "editable": {"subject": ti.get("subject", ""),
                     "additional_info": ti.get("additional_info", ""),
                     "callback": ti.get("callback") or {},
                     "subject_required": t["tool"] == "misc_request",
                     "info_required": t["tool"] == "misc_request"},
        "all": [{"label": k, "value": v} for k, v in ticket_fields(t, ti, client, account)],
        # A note about filling in the form (e.g. "address or phone required") is already
        # satisfied by the time the review card shows, so it is left off there.
        "note": t.get("note", "") if t.get("note_on_review", True) else "",
        "rule": t.get("common_note", ""),
        "warnings": notes,
        "attachments": {"max": MAX_ATTACHMENTS, "max_mb": 10, "types": "PDF, JPG or PNG",
                        "note": ATTACH_NOTE, "files": ti.get("attachments") or []},
        "can_edit_details": t["tool"] in ("stop_payment", "check_copy", "address_update"),
    }


def _execute(t):
    def execute(svc, session, ti, client):
        account = _account(svc, ti)
        now = datetime.now(timezone.utc)
        ticket = {
            "draft_id": ti["draft_id"],
            "advisor_id": session.advisor_id,
            "conversation_id": session.conversation_id or "",
            "tool": t["tool"],
            "ticket": t["title"],
            "category": t["category"], "request": t["request"],
            "request_type": _request_type(t, account),
            "client_id": client.client_id, "client_name": client.name,
            "account": account.label if account else "",
            "fields": [{"label": k, "value": v} for k, v in ticket_fields(t, ti, client, account)],
            "attachments": ti.get("attachments") or [],
            "when": us_timestamp(now), "at": int(now.timestamp() * 1000),
        }
        saved = svc.tickets.submit(ticket)
        return {"status": "ticket_sent", "ticket_id": saved["ticket_id"],
                "message": f"{t['title']} request {saved['ticket_id']} sent. It will be "
                           "processed by the Service Center."}
    return execute


def action_specs() -> dict:
    from core.handlers import ActionSpec           # late: handlers imports this module
    out = {}
    for tool, t in templates().items():
        out[tool] = ActionSpec(
            title=t["title"], execute=_execute(t), summary=_summary(t),
            precheck=_precheck(t), confirm_label="Send", client_level=True)
        out[tool].ticket = t                        # the template, for the review card
    return out
