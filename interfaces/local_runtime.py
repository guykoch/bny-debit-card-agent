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

import re
from datetime import date, timedelta

from core import cards, schemas, skills
from core.guardrails import dispatch
from core.handlers import ACTIONS
from core.models import Session, ToolResponse

YES = {"yes", "y", "confirm", "ok", "okay", "go ahead", "do it", "proceed"}
NO = {"no", "n", "cancel", "stop"}
CHANGE_DATES = "change_dates"          # value of the travel notice's "Change dates" button

ORDINALS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3,
            "fourth": 4, "4th": 4}


def with_follow_up(tool: str, result: ToolResponse) -> ToolResponse:
    """Plain code: after a successful action, add the action's fixed follow-up
    sentence (e.g. offer a replacement after a lost/stolen report)."""
    follow = ACTIONS[tool].follow_up if tool in ACTIONS else None
    if result.status == "ok" and follow:
        result.message = f"{result.message}\n{follow}"
        if result.card is not None:
            result.card["follow_up"] = follow
    return result

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

    # -- save / restore (for stateless hosting; see GptConversation) ----
    def snapshot(self) -> dict:
        return {"runtime": "keyword", "advisor_id": self.session.advisor_id,
                "pending": self.pending, "skill": self.skill.name if self.skill else None}

    def restore(self, state: dict) -> None:
        self.pending = state.get("pending")
        self.skill = skills.get(state["skill"]) if state.get("skill") else None

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

        # answering a confirmation (trip 2 - no interpretation, just a replay)
        if self.pending and self.pending.get("awaiting_confirm"):
            if low in YES:
                p = self.pending; self.pending = None
                # the audit should record what the advisor asked for, not "yes"
                self.session.utterance = p.get("text") or text
                return with_follow_up(p["tool"],
                                      self._dispatch(p["tool"], p["input"], confirmed=True))
            if low in NO:
                self.pending = None
                return ToolResponse(status="ok", message="Cancelled. Nothing was changed.")
            if low == CHANGE_DATES:
                self.pending = None
                return ToolResponse(
                    status="needs_input",
                    message="Changing dates needs the GPT-5.4 runtime. In keyword mode, "
                            "start the request again with the new dates.")

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
            self.pending = {"tool": tool, "input": {}, "missing": ["client_id"], "text": text,
                            "choice": client.card}
            return client

        card = self._resolve_card(client)
        if isinstance(card, ToolResponse):
            self.pending = {"tool": tool, "input": {"client_id": client},
                            "missing": ["card_id"], "text": text, "choice": card.card}
            return card

        return self._continue(tool, {"client_id": client, "card_id": card}, text)

    @staticmethod
    def _match_choice(text: str, panel: dict) -> str | None:
        """
        Map a typed answer onto one option of the choice panel we showed.

        A button click sends the option's value directly. A typed answer may be
        the option number ("2"), the last four digits ("2202", "the one ending
        2202"), or the label itself ("Georgia (country)"). Returns None unless
        exactly one option matches — we never pick between candidates.
        """
        options = panel.get("actions", []) if panel else []
        t = text.strip().lower()
        if not options or not t:
            return None
        for o in options:                                   # button click / exact
            if t in (str(o["value"]).lower(), o["label"].lower()):
                return o["value"]
        if t.isdigit() and 1 <= int(t) <= len(options):      # "2"
            return options[int(t) - 1]["value"]
        words = re.findall(r"[a-z0-9]+", t)                  # "the second one"
        nums = {ORDINALS[w] for w in words if w in ORDINALS}
        if len(nums) == 1 and not re.search(r"\d{4}", t):
            n = nums.pop()
            return options[n - 1]["value"] if n <= len(options) else None
        digits = re.findall(r"\d{4}", t)                     # "ending 2202"
        if digits:
            hits = [o for o in options if any(d in o["label"] for d in digits)]
            if len(hits) == 1:
                return hits[0]["value"]
            return None
        hits = [o for o in options if t in o["label"].lower()]   # "the country"
        return hits[0]["value"] if len(hits) == 1 else None

    def _fill(self, text: str) -> ToolResponse:
        p = self.pending
        field = p["missing"][0]
        value = text.strip()

        panel = p.get("choice")
        if panel:
            picked = self._match_choice(value, panel)
            if picked is None:                               # ask again, never guess
                return ToolResponse(
                    status="needs_input",
                    message="I couldn't tell which one you meant. Please pick from the list.\n"
                            + cards.to_text(panel),
                    card=panel)
            value = picked
            p.pop("choice", None)
        elif field == "client_id":                           # free-text answer to "which client?"
            found = self._resolve_client(value)
            if isinstance(found, ToolResponse):
                if found.card:
                    p["choice"] = found.card
                return found
            value = found

        if field == "client_id":
            p["input"]["client_id"] = value
            card = self._resolve_card(value)
            if isinstance(card, ToolResponse):
                p["missing"] = ["card_id"]
                p["choice"] = card.card
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
                    card = cards.choice_card("Which destination?",
                                             "That place name is ambiguous.",
                                             [{"label": o, "value": o} for o in options])
                    self.pending = {"tool": tool, "input": payload,
                                    "missing": ["destination"], "text": text, "choice": card}
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
            self.pending = {"tool": tool, "input": payload, "awaiting_confirm": True,
                            "text": text}
        return result
