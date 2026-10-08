"""
A stand-in for GPT-5.4, so the prototype runs with no model and no API key.

It does the same job the real model will do: read a sentence, choose one tool,
fill in the form, and ask when something is missing or ambiguous. It does it
with keyword rules instead of language understanding, which is enough to
demonstrate the whole flow end to end.

WHAT CHANGES IN PRODUCTION
--------------------------
Replace the keyword rules with a call to BNY's GPT-5.4 instance. There is one
skill per action, so the request is routed to a skill first and only that
skill's prompt and tools are sent:

    skill = skills.route(utterance)              # core/skills.py
    model.create(system=skills.system_prompt(skill),
                 tools=skills.tools_for(skill),  # its own tool + the lookups
                 messages=[...])

Routing before the model call is the point of splitting the skills: the model
sees one action and three tools rather than six actions and eight tools.
Everything in core/ stays as it is.

The model never decides permissions here or there — it only produces a
candidate request, which core/guardrails.py then judges.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from core import cards, schemas, skills
from core.guardrails import dispatch
from core.models import Session, ToolResponse

YES = {"yes", "y", "confirm", "ok", "okay", "go ahead", "do it", "proceed"}
NO = {"no", "n", "cancel", "stop"}

AMBIGUOUS_PLACES = {"georgia": ["Georgia (country)", "Georgia (US state)"],
                    "springfield": ["Springfield, IL", "Springfield, MA", "Springfield, MO"]}


class Interpreter:
    """Stateless rules. The conversation below holds what has been gathered."""

    def intent(self, text: str) -> str | None:
        """
        Route to a skill, then take that skill's tool.

        The triggers and their priorities live in the skill files, not here, so
        adding an action means adding a folder — nothing in this file changes.
        """
        skill = skills.route(text)
        return skill.tool if skill else None

    def name_candidates(self, text: str) -> list[str]:
        """
        Every run of capitalised words, longest first. We do not try to be
        clever about which one is the client — we try them against the
        directory and keep the one that matches. A real model does the same
        thing, just better.
        """
        cleaned = re.sub(r"[^\w\s'.]", " ", text)
        runs, run = [], []
        for w in cleaned.split():
            if w[:1].isupper():
                run.append(w.rstrip("'s").rstrip("'"))
            elif run:
                runs.append(" ".join(run)); run = []
        if run:
            runs.append(" ".join(run))
        # A sentence usually starts with a capitalised verb ("Lock Jane Miller"),
        # so also try each run without its first and without its last word.
        expanded = set()
        for r in runs:
            parts = r.split()
            expanded.add(r)
            if len(parts) > 1:
                expanded.add(" ".join(parts[1:]))
                expanded.add(" ".join(parts[:-1]))
        skip = {"i", "corestone", "netx360", "card", "debit"} | set(AMBIGUOUS_PLACES)
        expanded = {e for e in expanded if e.lower() not in skip}
        return sorted(expanded, key=len, reverse=True)

    def destination(self, text: str) -> tuple[list[str] | None, list[str] | None]:
        """Returns (destination, options_to_ask_about)."""
        low = text.lower()
        for place, options in AMBIGUOUS_PLACES.items():
            if place in low:
                return None, options
        m = re.search(r"\b(?:to|in|visiting)\s+([A-Z][\w]+(?:\s[A-Z][\w]+)?)", text)
        return ([m.group(1)], None) if m else (None, None)

    def dates(self, text: str) -> tuple[str, str] | None:
        """
        Very small set of relative phrases. The real model will handle more —
        what matters is the rule it must follow: propose, then show the
        proposal for confirmation. Never submit a silently inferred date.
        """
        low = text.lower()
        start = date.today() + timedelta(days=30 if "next month" in low else 7)
        weeks = 2 if ("two weeks" in low or "couple of weeks" in low) else None
        if weeks is None and "week" in low:
            weeks = 1
        if weeks is None:
            return None
        return start.isoformat(), (start + timedelta(weeks=weeks)).isoformat()


class Conversation:
    """
    One advisor, one thread. Holds what has been gathered so far.

    This is also the seam where the future agent layer plugs in: swap this for
    a runner that loops over several tools instead of handling one at a time.
    See agent/README.md.
    """

    def __init__(self, services, session: Session):
        self.services = services
        self.session = session
        self.interp = Interpreter()
        self.skill = None                     # the skill routed to on this turn
        self.pending: dict | None = None      # {"tool":..., "input":..., "missing":[...]}

    # -- helpers ---------------------------------------------------------
    def _dispatch(self, tool, payload, confirmed=False) -> ToolResponse:
        return dispatch(self.services, self.session, tool, payload, confirmed)

    def _resolve_client(self, text) -> ToolResponse | str:
        candidates = self.interp.name_candidates(text)
        if not candidates:
            return ToolResponse(status="needs_input", message="Which client is this for?")
        ambiguous = None
        for query in candidates:
            found = self._dispatch("find_client", {"query": query})
            if found.status == "ok":
                return found.data["clients"][0]["client_id"]
            if found.status == "needs_input":
                ambiguous = ambiguous or found     # several clients share this name
        if ambiguous:
            return ambiguous                       # ask which one; never choose
        return ToolResponse(status="error", message="No matching client found.",
                            data={"code": "no_match"})

    def _resolve_card(self, client_id) -> ToolResponse | str:
        listed = self._dispatch("list_cards", {"client_id": client_id})
        if listed.status != "ok":
            return listed
        open_cards = listed.data["cards"]
        if not open_cards:
            return ToolResponse(status="error", message="That client has no open cards.")
        if len(open_cards) == 1:
            return open_cards[0]["card_id"]
        card = cards.choice_card("Which card?", "This client has more than one card.",
                                 [{"label": f"...{c['card_last4']} ({c['status']})",
                                   "value": c["card_id"]} for c in open_cards])
        return ToolResponse(status="needs_input", message=cards.to_text(card), card=card)

    # -- main ------------------------------------------------------------
    def send(self, text: str) -> ToolResponse:
        self.session.utterance = text
        low = text.strip().lower()

        # answering a confirmation
        if self.pending and self.pending.get("awaiting_confirm"):
            if low in YES:
                p = self.pending; self.pending = None
                return self._dispatch(p["tool"], p["input"], confirmed=True)
            if low in NO:
                self.pending = None
                return ToolResponse(status="ok", message="Cancelled. Nothing was changed.")

        # answering a question we asked (a client id, a card id, a destination)
        if self.pending and self.pending.get("missing"):
            return self._fill(text)

        tool = self.interp.intent(text)
        if tool is None:
            names = ", ".join(s.name for s in skills.all_skills())
            return ToolResponse(
                status="needs_input",
                message=f"I handle debit card requests: {names}. What would you like to do?")
        self.skill = skills.for_tool(tool)      # what a real model would be given

        client = self._resolve_client(text)
        if isinstance(client, ToolResponse):
            self.pending = {"tool": tool, "input": {}, "missing": ["client_id"], "text": text}
            return client

        card = self._resolve_card(client)
        if isinstance(card, ToolResponse):
            self.pending = {"tool": tool, "input": {"client_id": client},
                            "missing": ["card_id"], "text": text}
            return card

        return self._continue(tool, {"client_id": client, "card_id": card}, text)

    def _fill(self, text: str) -> ToolResponse:
        p = self.pending
        field = p["missing"][0]
        value = text.strip()

        if field == "client_id":
            p["input"]["client_id"] = value
            card = self._resolve_card(value)
            if isinstance(card, ToolResponse):
                p["missing"] = ["card_id"]
                return card
            p["input"]["card_id"] = card
        elif field == "card_id":
            p["input"]["card_id"] = value
        elif field == "destination":
            p["input"]["destination"] = [value]
        elif field in ("reason", "incident_type", "delivery_address"):
            p["input"][field] = value

        p["missing"] = []
        self.pending = None
        return self._continue(p["tool"], p["input"], p.get("text", ""))

    def _continue(self, tool, payload, text) -> ToolResponse:
        """Fill the extra fields each action needs, asking when we must."""
        if tool == "travel_notice":
            if "destination" not in payload:
                dest, options = self.interp.destination(text)
                if options:
                    self.pending = {"tool": tool, "input": payload,
                                    "missing": ["destination"], "text": text}
                    card = cards.choice_card("Which destination?",
                                             "That place name is ambiguous.",
                                             [{"label": o, "value": o} for o in options])
                    return ToolResponse(status="needs_input", message=cards.to_text(card),
                                        card=card)
                if not dest:
                    self.pending = {"tool": tool, "input": payload,
                                    "missing": ["destination"], "text": text}
                    return ToolResponse(status="needs_input", message="Where are they travelling to?")
                payload["destination"] = dest
            if "start_date" not in payload:
                window = self.interp.dates(text)
                if not window:
                    return ToolResponse(status="needs_input",
                                        message="What are the travel dates? (YYYY-MM-DD to YYYY-MM-DD)")
                payload["start_date"], payload["end_date"] = window

        if tool == "replace_card":
            payload.setdefault("reason", "damaged" if "damag" in text.lower() else "other")
            if "delivery_address" not in payload:
                card = self.services.cards.get_card(payload["card_id"])
                payload["delivery_address"] = card.address_on_file

        if tool == "report_lost_stolen":
            payload.setdefault("incident_type",
                               "stolen" if "stolen" in text.lower() or "stole" in text.lower() else "lost")

        if tool == "close_card":
            payload.setdefault("reason", "advisor request")

        result = self._dispatch(tool, payload)
        if result.status == "awaiting_confirmation":
            self.pending = {"tool": tool, "input": payload, "awaiting_confirm": True}
        return result
