"""
The AI layer: GPT-5.4 understands what the advisor typed.

This replaces the keyword stand-in in interfaces/local_runtime.py. Same job,
same inputs and outputs, real language understanding.

WHAT THE AI DOES HERE - AND NOTHING ELSE
----------------------------------------
1. Choose the skill. A short first call reads the conversation and picks one
   of the six skills, or "none" when the message is not one of the six actions.
2. Fill in that skill's form. A second call gets only that skill's rules
   (_shared.md + its SKILL.md) and only its three tools (its own action plus
   find_client and list_cards). It asks the advisor when something is missing
   or unclear, looks the client and card up, and fills in the action form.

This is ordinary tool calling inside ONE skill and ONE action: at most a few
lookups, then one action form, then it stops at the confirmation panel. It is
not the agent layer - nothing here chains several actions or decides a next
action from a result (see agent/README.md, still not built).

WHAT STAYS PLAIN CODE (identical to the keyword runtime)
--------------------------------------------------------
- Every lookup and action runs through core/guardrails.dispatch(). The model
  can only ever request an action with confirmed=False, so the most it can
  cause is a confirmation panel.
- "Which client?" / "Which card?" panels are built by code whenever a lookup
  finds more than one match, and the answer is matched by code.
- IDs: an action is refused unless its client_id and card_id came back from a
  lookup in this conversation (the "never invent an ID" rule, enforced).
- Trip 2: the Confirm click replays the stored form - no model call.
- Cancel, "Change dates", the follow-up after a lost/stolen report, and the
  reply to out-of-scope messages are fixed text from code.
"""

from __future__ import annotations

import json
import re
from datetime import date

from config import settings
from core import cards, skills
from core.guardrails import dispatch
from core.models import Session, ToolResponse
from interfaces.llm_client import ModelUnavailable, OpenAIChatClient, tool_schema_for_model
from interfaces.local_runtime import CHANGE_DATES, NO, YES, Conversation, with_follow_up

OUT_OF_SCOPE = ("I can help with your clients' debit cards: lock, unlock, replace, close "
                "permanently, report lost or stolen, and travel notices. For anything else, "
                "please use the usual NetX360 screens.")

# A presentation-only tool. It lets the model show fixed options as buttons
# (Georgia the country or the state; lock or close; lost or stolen). It reads
# and writes nothing and never reaches core/guardrails.py, which is why it is
# not one of the eight schemas in tools/.
OPTIONS_TOOL = {
    "type": "function",
    "function": {
        "name": "present_options",
        "description": ("Ask the advisor to pick one of a few fixed options, shown as buttons. "
                        "Use it instead of listing choices in text."),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "One short question."},
                "options": {"type": "array", "items": {"type": "string"},
                            "minItems": 2, "maxItems": 4,
                            "description": "Two to four short option labels."},
            },
            "required": ["question", "options"],
        },
    },
}


def runtime_notes(today: date) -> str:
    """Added after the skill's own rules. Describes this chat, not the bank."""
    return f"""

---

## How this chat works (runtime notes)

- Today is {today:%A, %d %B %Y} ({today.isoformat()}). Write dates as YYYY-MM-DD.
- You are inside NetX AI, the chat in BNY's NetX360. The advisor is already signed in; never
  ask who they are.
- Calling your action tool does NOT perform the action. It shows the advisor a confirmation
  panel listing every field, with Confirm and Cancel; nothing runs until they click Confirm.
  That panel is the "restate and wait" step in the rules above, so do not also ask
  "shall I go ahead?" in text. Call the action tool as soon as every required field is known.
- Use find_client and list_cards to get ids, and copy ids exactly. When a lookup finds several
  matches, the system shows the choices itself and tells you the advisor's pick in a note.
- When the advisor must pick between a few fixed options, call present_options.
- Notes that start with "Context:" were written by the system; treat them as facts.
- If the advisor asks for a different card action than yours, say in one short sentence that
  you will do that instead; their next message will be handled by the right skill.
- Replies: plain text, no markdown, one or two short sentences.
"""


class GptConversation:
    """
    One advisor, one thread - the GPT-5.4 counterpart of local_runtime.Conversation.
    Same entry point: send(text) -> ToolResponse.
    """

    def __init__(self, services, session: Session, client=None):
        self.services = services
        self.session = session
        self.client = client or OpenAIChatClient()
        self.history: list[dict] = []        # user / assistant text, plus "Context:" notes
        self.task: dict | None = None        # the request currently being worked on
        self.pending: dict | None = None     # confirm panel, code choice, or model options
        self.skill = None
        # Every id a lookup has returned in this conversation. An action may only use
        # these - the "never invent an ID" rule, enforced in code.
        self.seen: set[str] = {session.client_id} if session.client_id else set()

    # ------------------------------------------------------------ save / restore
    # A stateless host (Vercel) may answer each message from a fresh process, so
    # the conversation is saved after every message and restored before the next.
    def snapshot(self) -> dict:
        task = None
        if self.task:
            task = {"skill": self.task["skill"].name, "texts": self.task["texts"],
                    "picked": self.task["picked"]}
        return {"runtime": "gpt", "advisor_id": self.session.advisor_id,
                "history": self.history[-80:], "task": task, "pending": self.pending,
                "seen": sorted(self.seen), "skill": self.skill.name if self.skill else None}

    def restore(self, state: dict) -> None:
        self.history = list(state.get("history") or [])
        self.pending = state.get("pending")
        self.seen = set(state.get("seen") or [])
        if self.session.client_id:
            self.seen.add(self.session.client_id)
        self.skill = skills.get(state["skill"]) if state.get("skill") else None
        t = state.get("task")
        if t and skills.get(t["skill"]):
            self.task = {"skill": skills.get(t["skill"]), "texts": list(t.get("texts") or []),
                         "picked": dict(t.get("picked") or {})}
        else:
            self.task = None

    # ------------------------------------------------------------ helpers
    def _dispatch(self, tool, payload, confirmed=False) -> ToolResponse:
        return dispatch(self.services, self.session, tool, payload, confirmed)

    def _note(self, text: str) -> None:
        self.history.append({"role": "developer", "content": f"Context: {text}"})

    def _say(self, response: ToolResponse) -> ToolResponse:
        """Record what the advisor was shown, so the model sees it next turn."""
        if response.message:
            self.history.append({"role": "assistant", "content": response.message})
        return response

    def _new_task(self, skill) -> None:
        self.task = {"skill": skill, "texts": [], "picked": {}}
        self.skill = skill

    # ------------------------------------------------------------ entry point
    def send(self, text: str) -> ToolResponse:
        text = (text or "").strip()
        low = text.lower()
        if not text:
            return ToolResponse(status="needs_input", message="What would you like to do?")

        # 1. A confirmation panel is open. Trip 2 is a replay - no model call.
        if self.pending and self.pending["kind"] == "confirm":
            p = self.pending
            if low in YES:
                self.pending = None
                self.history.append({"role": "user", "content": "Confirm"})
                self.session.utterance = p["text"]          # audit keeps the real request
                result = with_follow_up(p["tool"],
                                        self._dispatch(p["tool"], p["input"], confirmed=True))
                self._note(f"the advisor clicked Confirm; result: {result.message}")
                self.task = None
                return self._say(result)
            if low in NO:
                self.pending, self.task = None, None
                self.history.append({"role": "user", "content": "Cancel"})
                return self._say(ToolResponse(status="ok",
                                              message="Cancelled. Nothing was changed."))
            if low == CHANGE_DATES:
                self.pending = None
                self.history.append({"role": "user", "content": "Change dates"})
                return self._say(ToolResponse(status="needs_input",
                                              message="What dates should the travel notice cover?"))
            self.pending = None
            self._note("the advisor did not click Confirm on that panel and wrote the next "
                       "message instead. Nothing has run.")

        # 2. Code asked "which client?" / "which card?" - code matches the answer.
        if self.pending and self.pending["kind"] == "choice":
            panel, field = self.pending["panel"], self.pending["field"]
            picked = Conversation._match_choice(text, panel)
            if picked is None and len(text.split()) <= 3:
                return ToolResponse(status="needs_input",
                                    message="I couldn't tell which one you meant. "
                                            "Please pick from the list.\n" + cards.to_text(panel),
                                    card=panel)
            if picked is not None:
                self.pending = None
                label = next(a["label"] for a in panel["actions"] if a["value"] == picked)
                self.history.append({"role": "user", "content": label})
                self.task["picked"][field] = picked
                self.seen.add(picked)
                self._note(f"the advisor chose {label} ({field} = {picked}).")
                self.session.utterance = text
                return self._skill_turn()
            self.pending = None                   # a longer message: treat it as new input

        # 3. The model offered buttons; map a typed "2" to the option's label.
        if self.pending and self.pending["kind"] == "options":
            picked = Conversation._match_choice(text, self.pending["panel"])
            if picked is not None:
                text = picked
            self.pending = None

        # 4. A normal message: choose the skill (AI), then fill its form (AI).
        self.history.append({"role": "user", "content": text})
        self.session.utterance = text
        try:
            skill = self._route()
        except ModelUnavailable as e:
            return self._model_down(e)
        if skill is None:
            return self._say(ToolResponse(status="needs_input", message=OUT_OF_SCOPE))
        if self.task is None or self.task["skill"].name != skill.name:
            self._new_task(skill)
        self.task["texts"].append(text)
        return self._skill_turn()

    # ------------------------------------------------------------ AI call 1: routing
    def _route(self):
        current = self.task["skill"].name if self.task else "nothing"
        lines = [f"- {s.name}: {s.description} (typical words: {', '.join(s.triggers)})"
                 for s in skills.all_skills()]
        prompt = (
            "You route messages in NetX AI, the chat BNY advisors use in NetX360, to one debit "
            "card skill. Reply with the skill name only.\n\nSkills:\n" + "\n".join(lines) + "\n\n"
            "Rules:\n"
            "- Return none when the latest message is not a request for one of these actions: "
            "greetings, what can you do, balances, transactions, statements, which cards a "
            "client has or their status, and anything else.\n"
            f"- The conversation is currently handling: {current}. If the latest message answers "
            "a question the assistant just asked, or adds details to that request, return that "
            "same skill.\n"
            "- If the advisor says a card is lost or stolen, return report-lost-stolen even if "
            "they also say lock.\n"
            "- If the advisor says cancel or stop a card without saying temporarily or "
            "permanently, return close-card; that skill asks whether they mean lock or close.\n"
            "- If the advisor accepts something the assistant just offered (for example yes to "
            "ordering a replacement), return the skill for that offer.")
        recent = [m for m in self.history if m["role"] in ("user", "assistant")][-8:]
        names = [s.name for s in skills.all_skills()] + ["none"]
        reply = self.client.chat(
            [{"role": "developer", "content": prompt}] + recent,
            response_format={"type": "json_schema", "json_schema": {
                "name": "route", "strict": True,
                "schema": {"type": "object", "additionalProperties": False,
                           "required": ["skill"],
                           "properties": {"skill": {"type": "string", "enum": names}}}}})
        try:
            name = json.loads(reply.get("content") or "{}").get("skill")
        except json.JSONDecodeError:
            name = None
        if name in (None, "none"):
            return None
        return skills.get(name)

    # ------------------------------------------------------------ AI call 2: fill the form
    def _skill_turn(self) -> ToolResponse:
        skill = self.task["skill"]
        system = skills.system_prompt(skill) + runtime_notes(date.today())
        tools = [tool_schema_for_model(t) for t in skills.tools_for(skill)] + [OPTIONS_TOOL]
        messages = [{"role": "developer", "content": system}] + self.history[-40:]

        for _ in range(settings.MAX_MODEL_STEPS):
            try:
                msg = self.client.chat(messages, tools=tools)
            except ModelUnavailable as e:
                return self._model_down(e)

            calls = msg.get("tool_calls") or []
            if not calls:
                reply = (msg.get("content") or "").strip() or "Could you say that another way?"
                return self._say(ToolResponse(status="needs_input", message=reply))

            call = calls[0]
            messages.append({"role": "assistant", "content": msg.get("content"),
                             "tool_calls": [call]})
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = None

            result, stop = self._run_tool(skill, name, args)
            if stop is not None:
                return self._say(stop)
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result)})

        return self._say(ToolResponse(status="needs_input",
                                      message="I couldn't work that out. Could you rephrase?"))

    # ------------------------------------------------------------ the tools, run by code
    def _run_tool(self, skill, name, args):
        """Returns (result for the model, None) or (None, response that ends the turn)."""
        if not isinstance(args, dict):
            return {"error": "The arguments were not valid JSON."}, None
        if name not in skill.tool_names() + ["present_options"]:
            return {"error": f"{name} is not available for this request."}, None

        if name == "present_options":
            options = [str(o) for o in (args.get("options") or [])][:4]
            if len(options) < 2:
                return {"error": "Give two to four options."}, None
            panel = cards.choice_card("", str(args.get("question", "")),
                                      [{"label": o, "value": o} for o in options])
            self.pending = {"kind": "options", "panel": panel}
            return None, ToolResponse(status="needs_input", message=cards.to_text(panel),
                                      card=panel)

        if name == "find_client":
            return self._find_client(args)
        if name == "list_cards":
            return self._list_cards(args)
        return self._action(skill, name, args)

    def _find_client(self, args):
        # Search by name only. Digits ("Sarah Chen 4409") are kept in the advisor's own
        # words, where _already_chosen uses them to pick the account.
        query = re.sub(r"\d+", " ", str(args.get("query", ""))).strip(" ,.-")
        args = {**args, "query": " ".join(query.split()) or str(args.get("query", ""))}
        r = self._dispatch("find_client", args)
        if r.status == "error":
            self._note(f"find_client({args.get('query')!r}): no matching client.")
            return {"error": r.message}, None
        found = r.data["clients"]
        self.seen.update(c["client_id"] for c in found)
        if r.status == "needs_input":                       # several clients share the name
            chosen = self._already_chosen("client_id", found, "client_id", "account_last4")
            if chosen is None:
                self.pending = {"kind": "choice", "field": "client_id", "panel": r.card}
                self._note(f"find_client({args.get('query')!r}) found {len(found)} clients; "
                           "the advisor was asked to choose.")
                return None, r
            found = [chosen]
        brief = [{"client_id": c["client_id"], "name": c["name"],
                  "account_last4": c["account_last4"]} for c in found]
        self._note(f"find_client({args.get('query')!r}) -> {brief}")
        return {"clients": brief}, None

    def _list_cards(self, args):
        if args.get("client_id") not in self.seen:
            return {"error": "Unknown client_id. Call find_client first; never invent an id."}, None
        r = self._dispatch("list_cards", args)
        if r.status == "error":
            return {"error": r.message}, None
        found = r.data["cards"]
        self.seen.update(c["card_id"] for c in found)
        open_cards = [c for c in found if c["status"] != "closed"]
        if len(open_cards) > 1:
            chosen = self._already_chosen("card_id", open_cards, "card_id", "card_last4")
            if chosen is None:
                name = open_cards[0]["client_name"]
                panel = cards.choice_card(
                    "Which card?", f"{name} has {len(open_cards)} cards.",
                    [{"label": f"...{c['card_last4']} ({c['status']})", "value": c["card_id"]}
                     for c in open_cards])
                self.pending = {"kind": "choice", "field": "card_id", "panel": panel}
                self._note(f"list_cards({args['client_id']}) found {len(open_cards)} cards; "
                           "the advisor was asked to choose.")
                return None, ToolResponse(status="needs_input", message=cards.to_text(panel),
                                          card=panel)
            found = [chosen]
        brief = [{"card_id": c["card_id"], "card_last4": c["card_last4"],
                  "status": c["status"], "address_on_file": c["address_on_file"]} for c in found]
        self._note(f"list_cards({args['client_id']}) -> {brief}")
        return {"cards": brief}, None

    def _already_chosen(self, field, candidates, id_key, last4_key):
        """Plain code: was one candidate already picked, or named by its last four digits?"""
        picked = self.task["picked"].get(field)
        for c in candidates:
            if c[id_key] == picked:
                return c
        digits = set(re.findall(r"\b\d{4}\b", " ".join(self.task["texts"])))
        hits = [c for c in candidates if c[last4_key] in digits]
        return hits[0] if len(hits) == 1 else None

    def _action(self, skill, name, args):
        seen = self.seen
        if args.get("client_id") not in seen or args.get("card_id") not in seen:
            return {"error": "Use the client_id and card_id returned by find_client and "
                             "list_cards; never invent an id."}, None
        r = self._dispatch(name, args)                     # confirmed=False: panel only
        if r.status == "awaiting_confirmation":
            self.pending = {"kind": "confirm", "tool": name, "input": r.data["input"],
                            "text": " / ".join(self.task["texts"]) or self.session.utterance}
            fields = ", ".join(f"{f['label']}: {f['value']}" for f in r.card["fields"])
            self._note(f"a confirmation panel is showing: {r.card['title']} ({fields}). "
                       "Nothing has run yet.")
            return None, r
        self._note(f"{name} was refused: {r.message}")
        return {"error": r.message, "code": r.data.get("code")}, None

    # ------------------------------------------------------------ failure
    def _model_down(self, e: Exception) -> ToolResponse:
        return ToolResponse(status="error",
                            message=f"The AI service did not respond, so nothing was changed. ({e})",
                            data={"code": "model_unavailable"})
