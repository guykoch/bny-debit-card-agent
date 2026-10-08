# BNY Pershing — Debit Card Management Agent
## Complete project context for a new chat (v6, 8 October 2026)

> **To the assistant reading this:** you are picking up an ongoing project mid-stream.
> This document is the single source of truth for everything decided so far. Read all
> of it before answering. The user (Guy) will ask you to edit the repository, the
> decks and the documents, so you must know how every file connects. Section 12 says
> how to work with him. Section 10 lists known gaps — do not "discover" them as new,
> and do not claim something works if that section says it does not.
>
> **This file lives at the root of the repository zip.** Guy uploads only
> `debit-card-agent.zip`; everything you need is inside it (section 0).
>
> **Before anything else, read section 4.8 — what needs AI, what needs the agent, and what
> needs neither.** Never present a plain-code step as AI or as "the agent", in code comments,
> docs, slides or answers. Guy checks this closely.
>
> **First actions in the new chat:**
> 1. Unzip `debit-card-agent.zip` and run the four test suites and the demo (section 5.9).
>    Expect 22 + 39 + 18 + 36 + 20 passing (add `test_hosting`). None needs an API key
>    or network.
> 2. Read the code you are about to change before changing it. The descriptions here
>    are accurate as of today, but the files are the truth.
> 3. Never fetch or invent BNY internals. Everything BNY-specific is assumed (section 2.4).

---

## 0. What is in the zip

Guy uploads one file, `debit-card-agent.zip`. It contains:

| Path | What it is |
|---|---|
| `PROJECT-CONTEXT-HANDOFF.md` | This document |
| everything else at the root | The repository (Python, stdlib only) — section 5 |
| `deliverables/BNY_Six_Skills.pptx` | 18-slide skills deck (light house style) |
| `deliverables/build_six_skills_deck.js` | The pptxgenjs script that generates that deck — **edit this and rebuild; do not hand-edit the pptx XML** (section 8.3) |
| `deliverables/BNY_Debit_Card_Chat_CheckIn.pptx` | 8-slide check-in deck (light house style) |
| `DEPLOY.md` | How to host the team demo on Vercel + Convex (step by step) |
| `PLAN-AGENT-DECLINED-CARD.md` | Plan for the first agent job — not implemented |

**Guy's OpenAI key is NOT in the zip** (it lives in a git-ignored `.env` on his machine). You
cannot call GPT-5.4 from your environment unless he provides a key there; test with the
scripted model in `tests/test_llm_runtime.py` instead, and never ask him to paste the key.

**Not in the zip:** the 2-slide Agent Logic deck (`BNY_Agent_Logic_2.pptx`, team's dark
template). Guy holds the latest version and has edited it since; if he wants it changed, ask
him to attach it (section 8.2). Also not included: the architecture PDF (reproducible) and the
first reflection blog post.

## 1. The engagement and the people

- **Course:** NYU Stern Tech MBA, "Tech Solutions" client project. Team project.
- **Client:** **BNY Pershing** (the Pershing business of BNY; "BNY Mellon Pershing" was renamed "BNY Pershing" in BNY's 2024 rebrand).
- **Client contact:** **Ben**. Which team or department Ben sits in is **not recorded anywhere** — do not guess it.
- **Cadence:** weekly check-ins with Ben (~1 hour, review format); a midpoint in-person visit to BNY's Lower Manhattan office; an in-person final presentation.
- **Course deliverables:** a mocked prototype (fake UI and fake APIs — there is no BNY test environment) plus documentation justifying the architecture recommendation (skill vs standalone agent). Also **three reflection blog posts (300–500 words each)** over the semester, one after the project is complete; the **first** (on the project's ethical implications) is already written.
- **Research input — interview with Jonathan**, a private wealth manager at a small private bank, previously at Citi in a similar role:
  - Managing a client's debit card today means leaning on support teams, in large and small banks alike.
  - He wants anything that reduces human error, but insists a person stays in the loop for judgement when a situation goes outside the norm.
  - **Most striking finding:** card servicing is tedious enough that advisors sometimes steer clients to open their everyday checking account at a large universal bank, just to skip the support-ticket loop. That is a firm losing the daily client relationship over servicing friction — a stronger business case than "fewer clicks".

### 1.1 Who the users are — CORRECTED

**The users are BNY's own advisors, serving BNY's own clients.** An earlier version of this
handoff said the advisors "are not BNY employees — they work at independent wealth firms and
broker-dealers that run on Pershing's platform". **That was wrong. Do not repeat it** and do
not reintroduce the "independent firms / Pershing is infrastructure for other firms" framing
in any deck, document or answer.

Why entitlements still matter under the correct framing: there are many BNY advisors, each
with their own book of clients. An advisor may act only on their own clients, and possibly
only on some actions for some clients (e.g. may lock but not close). The mock data models
exactly this: three advisors, each with a separate book (section 5.7).

---

## 2. The problem, the scope and the constraints

### 2.1 The problem
Advisors using **NetX360** (BNY Pershing's advisor platform) must click through several
screens to do routine debit card tasks for a client (search client → open account → find the
**AMA Suite** area → card section → pick card → find option → fill form → submit). The
friction drives avoidable call-centre volume. The card product is **Corestone**, BNY
Pershing's cash-management offering; the NetX360 area is the **AMA Suite** (Asset Management
Account). Equivalent self-service already exists for end investors in **NetXInvestor**; this
project builds the advisor-side equivalent, driven by chat.

### 2.2 Scope agreed with Ben — six actions
lock card · unlock card · replace card · close permanently · report lost or stolen · travel notice.
**Travel notice is the hardest**: the most fields and the vaguest inputs (relative dates, ambiguous place names).

### 2.3 Our suggested additions — NOT yet agreed with Ben
check card status · see recent card activity · track a replacement (all three read-only, no risk) ·
cancel a travel notice ("the missing half") · reset PIN · update delivery address.

### 2.4 Constraints
- **No real API names, field names or data** have been provided. We invented conventional ones and kept them swappable.
- **No access to BNY's test environment.** Everything is mocked.
- BNY runs an **on-prem GPT-5.4** instance. The demo uses OpenAI's public `gpt-5.4` with
  Guy's own API key instead; swapping to BNY's is a settings change (INTEGRATION.md).
- The existing NetX360 chat panel (**"NetX AI"**) is **read-only** today (answers questions about client data such as holdings and transactions). Ours would be the first chat that **performs actions**. Letting it act is a permission/certification question for BNY, not a technical one.
- BNY's AI tool approval process runs **July → December**.

### 2.5 What the NetX AI panel looks like (from Guy's screenshot)
Header "✧ NetX AI" (blue sparkle icon) with ⋮ and expand icons; advisor messages are
right-aligned light-blue pills; replies are plain left-aligned text with no bubble, followed
by a row of icons (copy, download, retry, speaker); a dark vertical **"Guide Me"** tab on the
right edge; an input box with "+" on the left and a mic and blue round send button on the
right; footer: "Please note: AI can make mistakes. You are responsible for verifying accuracy
of responses. All data shown here is synthetic." In the screenshot it answered "I can't assist
with that. Please ask any questions related to client data like holdings, transactions etc."
to off-topic input, and "We could not complete your request right now" to "how do I open a
debit card?". The skills deck imitates this look (section 9.3).

---

## 3. BNY's existing architecture (given to us — we do not change it)

From a diagram Ben shared:

- **NetX Portal / Wove Portal** → **FS Router** → **Orchestrator Agent** (built on **CrewAI**). The orchestrator does: entitlement check, contextualization and decomposition, entity mapping, hybrid search / agent resolution, summarization.
- An **Agent Registry** with other agents (**Client Insights, How To, ARQA**) reached over the **A2A protocol**. All existing agents appear to be read-only; ours would be the first that writes.
- **Persistent Logging** (Elasticsearch + PostgreSQL), **DASF** token validation.

**Working assumption, confirmed by Guy:** the orchestrator checks entitlement *before*
routing; only approved requests reach our agent. Everything in that diagram is a black box —
usable, not modifiable.

---

## 4. Architecture decisions and the reasoning

### 4.1 A skill, not a standalone agent
Six fixed actions, each one API call. Nothing to plan, so an agent earns nothing. A skill
reuses the platform's login, entitlements, audit and chat surface; a standalone agent would
rebuild all four and add a second chat box. The decision is cheap to reverse — the guardrails
are identical either way.

**When an agent *would* fit** (used in the decks): handling a whole lost-wallet call end to
end; opening a new Corestone account (spans days, waits on approvals); investigating why a
card was declined. **The test: you cannot list the steps in advance.**

### 4.2 No MCP in our design (this was corrected mid-project — it matters)
What makes the model fill in a JSON form is **tool calling**, a model-API feature: schemas go
into the request, the model returns a tool name and arguments. **MCP** is a protocol for
publishing tools as a *separate server* for another process to reach. Our agent hosts the
model and owns the tools in one process, so MCP has no role. `interfaces/mcp_server.py`
exists only as optional packaging for the scenario where BNY's platform hosts the model
instead. (The repo docs were corrected to say this.)

- **A2A** = between services (BNY's orchestrator ↔ our agent).
- **Tool calling** = model ↔ its tools, inside our agent.
- **A2UI** = the format of a UI panel returned inside an A2A reply (section 4.6).

### 4.3 Two trips per write action
- **Trip 1:** the sentence arrives → routed to one skill → model (stand-in today) fills the form → schema check → guardrail checks ownership and state rules → returns a **confirm panel**. **Nothing has run.**
- **Trip 2:** the Confirm click re-enters through `a2a_server.py`, which finds the thread and **replays the stored request with no model call** → the guardrail **re-runs its checks** (the card's state may have changed between trips) → only then calls the action → writes the audit.

### 4.4 Entitlement
Checked upstream by BNY's orchestrator. `TRUST_UPSTREAM_ENTITLEMENT = True` in
`config/settings.py` is the default; the audit records
`entitlement_checked_by: bny_orchestrator`. Setting it `False` turns on an **action-level**
check inside our agent (`entitlement_checked_by: agent`). Kept because of one open question:
**is BNY's check at client level or action level?** Locking is reversible; closing permanently
is not. When an entitlement check refuses, the advisor is told only "You do not have
permission…", never why — explaining would leak that the client exists.

### 4.5 One skill per action (changed late, at Guy's direction)
Six skill folders plus `_shared.md` holding every common rule. **Routing happens before the
model call**, so the model sees one action and three tools (its own action tool +
`find_client` + `list_cards`) instead of six actions and eight tools. Risk: drift between six
files; `_shared.md` contains it. Rule: if a paragraph would be copied into two skills, it
belongs in `_shared.md`.

### 4.6 A2UI — what is and is not possible (researched)
- A2UI is Google's open protocol (spec v0.9 current; **CrewAI supports v0.8** via its A2A extension). The agent sends **declarative** component descriptions; the **client renders them with its own components and styling**. No code runs on the client.
- Server→client messages: `createSurface`, `updateComponents`, `updateDataModel`, `deleteSurface`. Basic component catalog: Text, Image, Icon, Video, AudioPlayer, Row, Column, List, Card, Tabs, Divider, Modal, Button, CheckBox, TextField, DateTimeInput, ChoicePicker, Slider. A button click comes back to the agent as an `action` message — which is exactly our trip 2. Custom catalogs are allowed.
- **Consequences:** every panel in our decks is buildable (choice list = Card + List/Buttons or ChoicePicker; confirm = Card + Text + Row of Buttons; result = Card + Icon + Text). **The look is NetX360's**, not ours — the agent can only hint (e.g. a primary colour). A red "danger" button exists only if NetX360's catalog has one. The chat bubbles themselves are NetX360's chat, not A2UI.
- **Our code does not emit real A2UI yet** — `core/cards.py` returns a simplified, A2UI-inspired JSON (`{"kind": "confirm", ...}`). A translator to real A2UI messages is a contained change in that one file, matched to BNY's A2UI version. Guy has been offered this; not done.
- If NetX360 cannot render A2UI at all, every reply has a plain-text fallback (`cards.to_text()`); the advisor sees a numbered list and types "2" or "yes".
- Guy accepted that the visual design will differ; what matters is that the **behaviour** (the questions and the confirm step) is exactly as shown.

### 4.7 What is guaranteed by code vs. what relies on the model
| Behaviour | Who enforces it | Certainty |
|---|---|---|
| "Which card?" / "Which client?" when there is more than one | Code, in both runtimes (`llm_runtime._find_client/_list_cards`) | Guaranteed, tested |
| Typed answers like "2", "2202", "the one ending 2202", "the second one" mapped to the option | Code (`Conversation._match_choice`) | Guaranteed, tested |
| An action only uses ids a lookup returned | Code (`llm_runtime._action`, conversation-wide `seen` set) | Guaranteed, tested |
| A skill can only call its own action tool | Code (`llm_runtime._run_tool`) + only that tool is sent to the model | Guaranteed, tested |
| Nothing runs before Confirm | Code (`confirmed=False` default in `dispatch`) | Guaranteed |
| Re-checking card state on trip 2 | Code | Guaranteed |
| Bad dates (end before start, > 90 days, start in past) | Code (`_travel_precheck`) | Guaranteed |
| Offering a replacement after a lost/stolen report | Code (`ActionSpec.follow_up`) | Guaranteed |
| Choosing the right skill for the sentence | GPT-5.4 routing call | Very likely, **not guaranteed** |
| "Georgia: country or state?", "lock or close?" for "cancel", "lost or stolen?", "why replace?", confirming the delivery address | GPT-5.4, following the skill files | Very likely, **not guaranteed** |

The code can check a field is filled, not whether the model asked or guessed. The safety
net: the confirm panel shows every value, so the advisor can catch a guess before anything
runs. Before go-live: an evaluation set of test sentences run against GPT-5.4.

### 4.8 What needs AI, what needs the agent, and what needs neither — READ THIS

Guy's rule: **never mix the three.** Most of the system is ordinary code. AI does one job.
The agent does nothing yet, because it is not built.

**Plain code — works today, no AI, no agent:**

| Step | Where |
|---|---|
| Receiving the request, finding the conversation thread | `interfaces/a2a_server.py` |
| Looking up clients and cards (`find_client`, `list_cards`) — the model *asks* for them, code *runs* them | `core/guardrails.py` `_read()` + `integrations/` |
| Checking the filled form against its schema | `core/schemas.py` |
| Ownership and state rules (card belongs to client, already locked, bad dates, 90-day limit) | `core/guardrails.py`, `core/handlers.py` |
| Entitlement check when the flag is off | `core/guardrails.py` + `integrations/` |
| Building the confirm / choice / result panels and the text fallback | `core/cards.py` |
| **Stopping before Confirm** ("only after Confirm") | `core/guardrails.py` — `if not confirmed: return` |
| **Trip 2 — replaying the stored request on the Confirm click, with no model call** | `interfaces/llm_runtime.py` `GptConversation.send()` step 1 (and `local_runtime.py`) |
| The "which client / which card" panels, and matching the answer ("2", "2202") | `interfaces/llm_runtime.py` + `Conversation._match_choice()` |
| Refusing an action whose ids no lookup returned; a skill calling another action's tool | `interfaces/llm_runtime.py` `_action()` / `_run_tool()` |
| Cancel, "Change dates", the lost/stolen follow-up, the out-of-scope reply | fixed text in `llm_runtime.py` / `core/handlers.py` |
| Choosing a skill **when no API key is set** (keyword triggers + priority) | `core/skills.py` `route()` |
| The card action itself (one API call) | `integrations/` |
| Audit | `core/audit.py` |

**AI — GPT-5.4, one job: understanding the advisor's words** (`interfaces/llm_runtime.py`).
It does this in two calls per message:
1. **Routing call** — reads the recent conversation plus each skill's description and
   triggers; returns one skill or "none" (JSON-schema answer). Guy chose AI routing over
   keyword routing (keywords misrouted "I'm going to need you to lock…" to travel notice).
2. **Form-filling call** — gets `_shared.md` + that one SKILL.md + short runtime notes, and
   only that skill's three tools plus the presentation-only `present_options`. It calls the
   lookups, asks about anything missing or unclear, and fills in the action form.
This is **ordinary tool calling within one skill and one action** (a few lookups, then one
form, stop at the confirmation panel; max `MAX_MODEL_STEPS` = 6 round trips). It is **not**
the agent: nothing chains several actions or decides the next action from a result.
If advisors used a plain form instead of chat, no AI would be needed at all.
Without a key, `interfaces/local_runtime.py` (keywords, no AI) does the same two jobs.

**The agent — NOT built, and Guy does not want it implemented yet.** Only these would be
"the agent": a runner loop that sends each result back to the model to decide the next step
(`agent/runner.py`), job state (`agent/state.py`), workflow files (`agent/workflows/*.md`),
extra read-only tools for multi-step jobs, and an `undo` field for compensation. Only
`agent/README.md` exists, and it is documentation. **Nothing in the six actions needs the
agent**, and a full demo needs no agent (section 9).

**Rule for slides and diagrams:** amber = the advisor's confirmation path (confirm panel,
Confirm click, trip 2, "only after Confirm") — it exists today and needs neither AI nor
agent. The agent additions must use a **different** colour/style and be labelled as not
built. The AI is only ever the understanding layer (routing + filling the form).

---

## 5. The repository (`debit-card-agent/`)

Python 3.10+, **standard library only**. No API key, no network. ~3,200 lines.

### 5.1 Every file, and what it does

```
PROJECT-CONTEXT-HANDOFF.md   this document
PLAN-AGENT-DECLINED-CARD.md  plan for the first agent job — NOT implemented (see §9)
README.md                    overview, run commands, file map, assumptions
HOW-IT-FITS-TOGETHER.md      one request ("lock Jane Miller's card") followed through every file
ARCHITECTURE.md              why the pieces sit where they do; A2A / tool calling / A2UI / no MCP;
                             an "is it AI?" table
INTEGRATION.md               what BNY must supply; swapping to BNY's on-prem GPT-5.4; assumptions
requirements.txt             empty apart from comments (stdlib only; OpenAI called via urllib)
.env.example                 template for the OpenAI key (copy to .env, which is git-ignored)
.gitignore

skills/debit-card/
  _shared.md                 rules every skill inherits (prepended to each skill's body)
  README.md                  how the split works; how to add a seventh action
  lock-card/SKILL.md         frontmatter + rules for that action only
  unlock-card/SKILL.md
  replace-card/SKILL.md
  close-card/SKILL.md
  report-lost-stolen/SKILL.md
  travel-notice/SKILL.md

tools/*.json                 8 schemas (6 actions + find_client + list_cards); each has
                             "name", "access": "read"|"write", "description", "input_schema"

core/
  skills.py                  registry: load(), all_skills() (sorted by priority desc), get(),
                             for_tool(), route(utterance), system_prompt(skill), tools_for(skill)
  schemas.py                 load(), all_tools(), is_write(), validate(tool, input)
  guardrails.py              THE IMPORTANT ONE — dispatch(services, session, tool, input, confirmed=False)
  handlers.py                ActionSpec per action (title, execute, summary, precheck, confirm_label,
                             extra_actions, danger, follow_up); ACTIONS dict
  cards.py                   confirm_card(…, extra_actions, danger), result_card(), choice_card(), to_text()
  audit.py                   LOG list, _sink(row), write(...), for_client(), reset()
  models.py                  Session, Client, Card, ToolResponse dataclasses
  errors.py                  AgentError → NotEntitled, BadRequest, NotPossible, UpstreamUnavailable

config/settings.py           .env loader; MODE (DCA_MODE: mock|bny); TRUST_UPSTREAM_ENTITLEMENT=True;
                             MAX_TRAVEL_DAYS=90; CONFIRM_REQUIRED_FOR_WRITES=True;
                             RUNTIME (DCA_RUNTIME: auto|gpt|keyword), active_runtime();
                             OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL ("gpt-5.4"),
                             OPENAI_REASONING_EFFORT ("none"), OPENAI_TIMEOUT_SECONDS, MAX_MODEL_STEPS=6;
                             Services dataclass, build_services()

integrations/
  ports.py                   3 Protocols: ClientDirectory(find, get), EntitlementService(can),
                             CardSystem(get_card, list_cards, lock, unlock, replace, close,
                             report_lost_stolen, add_travel_notice)
  mock/data/clients.csv      20 clients
  mock/data/cards.csv        21 cards
  mock/data/entitlements.csv advisor-client grants (ALL or |-separated actions)
  mock/data/README.md        column meanings; which rows tests depend on
  mock/dataset.py            CSV loader with validation of action names
  mock/services.py           MockClientDirectory, MockEntitlementService, MockCardSystem (in-memory)
  bny/services.py            TEMPLATE: BnyEntitlementService, BnyClientDirectory, BnyCardSystem
                             (all raise NotImplementedError) + endpoint mapping table to fill in

interfaces/
  a2a_server.py              front door: handle(payload); _new_conversation() picks the runtime;
                             ThreadingHTTPServer on localhost:8080 (PORT env): GET / (chat page),
                             POST / and /api/chat, GET /api/info, GET /api/audit
  threads.py                 conversation state between messages: MemoryThreads / ConvexThreads
  llm_runtime.py             THE AI LAYER: GptConversation (routing call + form-filling call)
  llm_client.py              OpenAIChatClient.chat() — the only code that calls OpenAI (urllib)
  local_runtime.py           keyword stand-in: Interpreter + Conversation (+ _match_choice,
                             with_follow_up, YES/NO/CHANGE_DATES, used by both runtimes)
  a2a_agent_card.json        how we describe ourselves to BNY's Agent Registry (v0.2.0)
  mcp_server.py              optional packaging only; NOT in the request path

agent/README.md              the future agent layer — described, NOTHING built (keep it that way)
tests/test_guardrails.py     22 checks
tests/test_skills.py         39 checks
tests/test_choices.py        18 checks
tests/test_llm_runtime.py    36 checks — the code around GPT-5.4, with a scripted model
demo/run_demo.py             scripted conversations + audit dump

deliverables/                decks (not code; nothing imports from here)
  BNY_Six_Skills.pptx
  build_six_skills_deck.js   generates the deck above; appendix reads ../skills/debit-card/
  BNY_Debit_Card_Chat_CheckIn.pptx
```

### 5.2 The request path, function by function

```
interfaces/a2a_server.py  handle(payload)
   payload = {advisor_id (required, from the authenticated session), utterance,
              client_id (optional), conversation_id (optional)}
   The chat page sends the same payload; a button click sends the button's value as the
   utterance ("confirm", "cancel", "change_dates", a client/card id, or an option label).
   finds/creates a conversation per conversation_id in _THREADS via _new_conversation():
   GptConversation if settings.active_runtime() == "gpt", else Conversation (keywords).
   (_new_conversation is the seam where an agent runner would branch.)
        │
        ▼
interfaces/llm_runtime.py  GptConversation.send(text)        ← the ONLY AI (GPT-5.4)
   1. confirm panel open: "confirm"/yes → TRIP 2: dispatch(stored tool, stored input,
      confirmed=True) with NO model call, + fixed follow-up; "cancel"/no → "Cancelled.
      Nothing was changed."; "change_dates" → "What dates should the travel notice cover?"
      (code); any other text → panel dropped, message handled as new input
   2. code choice open (which client / which card): Conversation._match_choice(text)
      → note the pick → _skill_turn(); no match and ≤3 words → ask again (code)
   3. model options open: typed "1"/"2" mapped to the option label
   4. otherwise: _route()  [AI call 1, JSON answer: a skill name or "none"]
        none → fixed OUT_OF_SCOPE reply (code)
        new skill → new task; same skill → continue
      _skill_turn()  [AI call 2, repeated ≤ MAX_MODEL_STEPS]:
        system = skills.system_prompt(skill) + runtime_notes(today)
        tools  = that skill's 3 tools + present_options
        model text → shown to the advisor (a question or an explanation)
        present_options → choice panel of the model's options; turn ends
        find_client / list_cards → run by code via dispatch; several matches → CODE panel
          ("Which client?" / "Which card?") unless the advisor already gave the last four;
          results go back to the model and into "Context:" notes
        the skill's action → ids must be in self.seen → dispatch(confirmed=False)
          → confirm panel; turn ends. Refusals go back to the model to explain.
        anything else → refused ("not available for this request")
   History: user/assistant text + "Context:" developer notes (ids found, picks, panels shown,
   results), so later turns and later skills know what happened.
(interfaces/local_runtime.py Conversation.send does the same job with keyword rules.)
        │
        ▼
core/guardrails.py  dispatch(services, session, tool_name, tool_input, confirmed=False)
   schemas.validate()  → missing required / unknown field / wrong type / outside enum → BadRequest
   read tools  → _read(): find_client (directory scopes to advisor's book via "view" grant);
                          list_cards (checks "view" only if TRUST flag is False)
   write tools → _write():
      1 entitlement  (skipped by default; if flag False: entitlements.can(advisor, client, tool))
      2 ownership    (card exists and card.client_id == client_id, else BadRequest)
        state rules  (spec.precheck from handlers.py → NotPossible / BadRequest)
      3 confirmation (if not confirmed: build confirm panel, RETURN awaiting_confirmation)
      4 action       (spec.execute → integrations CardSystem method → {"status","message",...})
      5 audit        (audit.write with entitlement_checked_by)
      → result panel (cards.result_card)
   any AgentError → ToolResponse(status="error", message, data={"code": ...})
        │
        ▼
integrations/ (mock today, bny later)  →  core/audit.py  →  core/cards.py
```

**ToolResponse** (`core/models.py`): `status` ∈ `ok` (result panel) · `awaiting_confirmation`
(confirm panel) · `needs_input` (choice panel or plain question) · `error` (text, no panel);
plus `message` (always plain text), `card` (panel dict or None), `data`.

**Error codes:** `not_entitled`, `bad_request`, `card_closed`, `already_locked`, `not_locked`,
`api_unavailable`, `no_match`.

**Audit row fields** (`core/audit.py`): timestamp, advisor_id, conversation_id, channel="chat",
action, client_id, card_id, outcome, advisor_typed, model_understood, detail (free-form; holds
`entitlement_checked_by` and the action result). `_sink` appends to an in-memory list; in
production it must post to Persistent Logging and never raise.

**Data model** (`core/models.py`): `Session(advisor_id, utterance, advisor_name, client_id,
conversation_id)` — advisor_id NEVER comes from message text. `Client(client_id, name,
account_last4)`. `Card(card_id, client_id, client_name, card_last4, account_last4, status,
address_on_file)`; status ∈ active | locked | closed | pending.

### 5.3 What each action does (`core/handlers.py` + mock)

| Tool | Precheck (refuses if…) | Confirm panel shows | Mock effect / result status |
|---|---|---|---|
| `lock_card` | closed → `card_closed`; already locked → `already_locked` | client, account, card | status→locked / `locked` |
| `unlock_card` | closed → `card_closed`; active → `not_locked` | client, account, card | status→active / `active` |
| `replace_card` | closed → `card_closed` | + reason, deliver to | old→closed, new card `pending` / `replacement_ordered` |
| `close_card` | already closed | + reason; warning "This cannot be undone…"; button "Close permanently"; `danger` (red) | status→closed / `closed` |
| `report_lost_stolen` | closed → `card_closed` | + reported as, flag recent transactions | status→**locked**, optional flag list / `reported`; fixed follow-up "Would you like me to order a replacement card?" |
| `travel_notice` | closed; dates not YYYY-MM-DD; end < start; > `MAX_TRAVEL_DAYS`; start in past | + destination(s), dates shown as "6 Nov 2026 to 20 Nov 2026"; extra button **Change dates** | appended to `travel_notices` / `travel_notice_added` |

### 5.4 The eight tool schemas (`tools/*.json`)

| Tool | access | Required | Optional / enums |
|---|---|---|---|
| `find_client` | read | query | — |
| `list_cards` | read | client_id | include_closed (bool) |
| `lock_card` | write | client_id, card_id | reason |
| `unlock_card` | write | client_id, card_id | — |
| `replace_card` | write | client_id, card_id, reason, delivery_address | reason ∈ damaged, lost, stolen, expiring, other |
| `close_card` | write | client_id, card_id, reason | — |
| `report_lost_stolen` | write | client_id, card_id, incident_type | incident_type ∈ lost, stolen; last_known_use; flag_transactions (bool) |
| `travel_notice` | write | client_id, card_id, destination (array), start_date, end_date | — |

Field descriptions carry instructions to the model ("Never invent one", "Ask the advisor; do not infer").

### 5.5 The skill files

Frontmatter keys: `name`, `tool`, `lookups`, `priority`, `triggers`, `description`. Parsed by
`core/skills.py` without a YAML library (`key: value`, comma-separated lists). Routing =
**substring match on triggers, highest priority first.**

| Skill | Tool | Priority | Triggers | Own rules (summary) |
|---|---|---|---|---|
| report-lost-stolen | report_lost_stolen | 90 | lost, stolen, wallet, theft, stole, missing card, pickpocket | ask lost or stolen; ask about unrecognised transactions (sets flag_transactions), never judge which look suspicious; afterwards offer replace-card |
| travel-notice | travel_notice | 80 | travel, trip, abroad, flying, going to, overseas, holiday, vacation | track missing fields; convert relative dates and show the working; never submit an inferred date unshown; end<start or >90 days → say so and ask; ambiguous places (Georgia, Springfield) → ask; multiple countries allowed; never default a travel field |
| replace-card | replace_card | 70 | replace, new card, reissue, damaged, broken, cracked, worn out | ask reason, do not infer; show address on file and confirm, never use an address mentioned in passing; lost/stolen → offer report-lost-stolen first |
| close-card | close_card | 65 | close, close permanently, cancel the card, terminate, shut the card | stricter confirmation wording (permanence); ambiguous "cancel/stop" → ask lock or close first |
| unlock-card | unlock_card | 62 | unlock, unblock, reactivate, turn the card back on, lift the lock | closed → say replacement needed; already active → say so |
| lock-card | lock_card | 60 | lock, block the card, freeze, suspend, stop the card | lost/stolen mentioned → suggest report-lost-stolen; already locked → say so; closed → replacement needed |

`_shared.md` sections: what already happened upstream (identity fixed by session; never
comment on entitlement) · what you never do (never guess client/card/date/destination; never
call a tool until all required fields are filled and the advisor confirmed; one action tool
per confirmed request; one card at a time, refuse bulk; never invent IDs) · out of scope
(balances, transactions, statements, transfers, checks, ACH, account-level address changes,
opening/closing accounts) · finding the client (one match → use; several → list with last
four and ask; none → say so, don't suggest names) · finding the card · before acting (restate
in one line, wait) · after acting (one sentence, no speculation) · error wording table ·
how replies are shown (panels; one sentence; options one per line).

`skills.system_prompt(skill)` = `_shared.md` + `---` + skill body.
`skills.tools_for(skill)` = its own tool + its lookups.

### 5.6 Configuration (`config/settings.py`)
- `MODE` from env `DCA_MODE`, `mock` (default) or `bny`. `build_services()` returns a `Services(clients, entitlements, cards)` object; `core/` never imports a mock directly.
- `TRUST_UPSTREAM_ENTITLEMENT = True`
- `MAX_TRAVEL_DAYS = 90` — **our invented number**; to be agreed with BNY.
- `CONFIRM_REQUIRED_FOR_WRITES = True` — declared, "never set False in production". (Note: `guardrails.py` enforces confirmation via the `confirmed` argument; it does not read this flag.)
- AI layer: `RUNTIME` (`DCA_RUNTIME`: `auto` default → `gpt` if `OPENAI_API_KEY` is set, else `keyword`), `OPENAI_MODEL` (`DCA_MODEL`, default `gpt-5.4`), `OPENAI_REASONING_EFFORT` (`DCA_REASONING_EFFORT`, default `none` = GPT-5.4's default; empty string omits it), `OPENAI_BASE_URL`, `OPENAI_TIMEOUT_SECONDS` (60), `MAX_MODEL_STEPS` (6). A `.env` file at the repo root is read at start-up; real environment variables win.

### 5.7 Mock data (`integrations/mock/data/`) — built to fail usefully
- **Advisors and books:** `ADV-1234` (9 clients), `ADV-5678` (6), `ADV-9012` (5). A client with no row for an advisor does not exist for that advisor ("No matching client found", no hint).
- **Rows the tests and the decks depend on:**
  - `C-88210` **Jane Miller**, account ...8821, one active card `CARD-4417`, address "14 Hudson St, New York, NY 10013". ADV-1234: ALL.
  - **Three Sarah Chens:** `C-44090` Sarah Chen ...4409 (card `CARD-9902`, **locked**, Boston), `C-44091` Sarah M. Chen ...4410 (`CARD-8807`, active, Chicago) — both visible to ADV-1234 with `view|lock_card|unlock_card|travel_notice` (i.e. **may lock but not close**); `C-99001` Sarah Chen ...9900 belongs to ADV-5678, **invisible** to ADV-1234.
  - `C-10220` **Robert Castellano**, account ...1022, **two active cards** `CARD-2201`, `CARD-2202`. ADV-1234: ALL.
  - `C-77310` David Okafor, `CARD-3310` **closed**, belongs to ADV-5678 (used for "a client this advisor cannot see").
  - `C-12090` Thomas Whitfield, `CARD-2091` locked. `C-19006` Anne-Marie Dubois, two cards (9007 active, 9008 locked), ADV-1234 has `view` only. `C-15644` Claire Beaumont card `pending`. `C-17309` Gregory Lindqvist card closed.
- Statuses change in memory only; restart resets to the CSVs. Edit the CSVs in Excel; no code change needed.

### 5.8 The two understanding runtimes

**GPT-5.4 (`interfaces/llm_runtime.py` + `interfaces/llm_client.py`)** — see §5.2 for the flow.
- `llm_client.OpenAIChatClient.chat(messages, tools, response_format)` → POST
  `{OPENAI_BASE_URL}/chat/completions` with `model`, `messages`, optional `reasoning_effort`,
  `tools` (function format from `tool_schema_for_model`), `tool_choice: "auto"`,
  `parallel_tool_calls: false`, optional `response_format` (json_schema). Returns
  `choices[0].message`. Errors → `ModelUnavailable` → the chat says "The AI service did not
  respond, so nothing was changed." Standard library only (urllib).
- Routing prompt lists each skill's name, description and triggers, the current task, and rules:
  not-an-action → none; answers/added details → same skill; lost/stolen wins over lock;
  "cancel"/"stop" without temporary/permanent → close-card (which asks lock or close); accepting
  an offer → that offer's skill.
- `runtime_notes(today)` appended to the skill prompt: today's date; you are in NetX AI; the
  action tool only shows a confirmation panel (that is the "restate and wait" step — don't also
  ask in text); copy ids from lookups; code shows multi-match choices; use `present_options`
  for fixed choices; "Context:" notes are facts; if the advisor wants another action, say so in
  one sentence (the router handles their next message); plain text, 1–2 sentences.
- `present_options(question, options[2–4])` — presentation-only tool, not in `tools/`, never
  reaches the guardrail; renders a choice panel whose values are the labels.
- `_find_client` strips digits from the query (name search only); the advisor's digits are used
  by `_already_chosen` to pick an account or card by its last four.
- `self.seen` (conversation-wide): every id a lookup returned; actions with other ids are refused.
- Never tested against the live OpenAI API from the build environment (no key there). Tested
  with a scripted model (`tests/test_llm_runtime.py`) and end to end through HTTP and the browser
  with a fake OpenAI-compatible endpoint. **First live run is on Guy's machine.**

**Keyword stand-in (`interfaces/local_runtime.py`)** — used when no key is set, and by `demo/run_demo.py`.
- `Interpreter.intent` → `skills.route`. `name_candidates` → runs of capitalised words (and sub-runs) tried against `find_client`. `destination` → knows ambiguous Georgia/Springfield, else regex "to/in/visiting X". `dates` → "next month" = today + 30 days, else today + 7; "two weeks"/"couple of weeks" = 2 weeks, "week" = 1; otherwise asks.
- `YES = {yes, y, confirm, ok, okay, go ahead, do it, proceed}`, `NO = {no, n, cancel, stop}`, `CHANGE_DATES = "change_dates"` (keyword mode replies that changing dates needs GPT-5.4).
- `Conversation._match_choice` (shared by both runtimes): exact value or label, option number ("2"), ordinal word ("the second one"), a 4-digit group in exactly one label ("2202", "the one ending 2202"), or a unique label substring ("country"). No match or several → ask again. Never guesses.
- `with_follow_up(tool, result)` (shared): adds `ActionSpec.follow_up` after a successful action.
- On Confirm, `session.utterance` is set back to the original request so the audit records it.

### 5.9 Running it
```bash
python -m tests.test_guardrails    # 22 passed
python -m tests.test_skills        # 39 passed
python -m tests.test_choices       # 18 passed
python -m tests.test_llm_runtime   # 36 passed (scripted model, no key needed)
python -m demo.run_demo            # 5 scripted conversations + audit dump (keyword stand-in)
python -m interfaces.a2a_server    # then open http://localhost:8080 — the mock NetX AI chat
```
**Demo setup on Guy's machine:** Python 3.10+; copy `.env.example` to `.env` and set
`OPENAI_API_KEY`; run the server from the repo folder; the line under the chat header reads
"Understanding: GPT-5.4" (blue dot) or "Keyword stand-in (no AI)" (grey dot). Restarting the
server resets the mock cards. The advisor switcher (header) starts a new conversation as
ADV-1234 / ADV-5678 / ADV-9012. `GET /api/audit` shows the audit trail.
- `test_llm_runtime`: out-of-scope fixed reply; two cards → code panel, "2202" resolves without a
  routing call; Confirm makes no model call and audit keeps the real words; last four in the first
  message skips the question; invented ids refused; lock-card cannot call close_card and only sees
  its own tools; model options as buttons, "1" → label, switching skill keeps found ids; Cancel;
  travel Change dates (code) then new dates; already_locked goes back to the model; lost/stolen
  follow-up; another advisor's client not found; model down → nothing changes; trip 2 re-checks a
  changed card; the exact OpenAI request shape (endpoint, model, bearer key, function tools,
  parallel_tool_calls false).
- `test_guardrails`: nothing before Confirm; confirm runs once, second is `already_locked`; two Sarah Chens asked, third invisible; trusted entitlement + audit says `bny_orchestrator`; flag off → another advisor's client refused, lock-but-not-close refused, permitted action runs, audit says `agent`; ownership; schema rejects missing/invented/enum-violating; travel end-before-start rejected, valid window accepted; denials logged (exactly 2 `not_entitled`).
- `test_skills`: every skill wired to a real tool and lookups; one skill per write tool; a skill can't reach another action's tool; routing incl. "Jane lost her wallet, lock the card" → report-lost-stolen; unrelated sentence routes nowhere; shared rules reach every prompt.
- `test_choices`: Robert Castellano's two cards → asks; "CARD-2202", "2", "2202", "the one ending 2201", label → right card; "9999", "the new one", "3", "2201 or 2202" → asked again; recovery after a bad answer; nothing runs before "yes"; same for the Sarah Chen client choice.
- Demo scripts: Jane lock → yes; Sarah Chen travel to Georgia next month two weeks → client choice → Georgia (country) → yes; close Sarah Chen permanently → C-44090 → no (cancelled); "Jane Miller lost her wallet, lock the card" → report-lost-stolen confirm; "Lock David Okafor's card" → no match.

### 5.10 How to make common changes (cross-file map)

| Change | Files to touch |
|---|---|
| Add a 7th action | `tools/<name>.json` (access write) · `skills/debit-card/<name>/SKILL.md` (set priority deliberately) · `core/handlers.py` ActionSpec · `integrations/ports.py` + `mock/services.py` (+ `bny/services.py` stub) · `mock/dataset.py` `ALL_ACTIONS` if it needs entitlement · `tests/test_skills.py` routing cases · docs/decks that say "six" |
| Add a read-only tool (e.g. card status) | `tools/<name>.json` (access read) · `core/guardrails.py` `_read()` branch · ports + mock · the skill's `lookups` |
| Change a rule all actions share | `skills/debit-card/_shared.md` only |
| Change one action's behaviour | its `SKILL.md`; if it's a hard rule, also its `precheck` in `core/handlers.py`; keep the schema `description` consistent |
| Change confirm/choice/result panels | `core/cards.py` (+ `to_text`) — and any deck mock-ups that show them |
| Change wording of errors | `core/errors.py`, `core/handlers.py`, and the error table in `_shared.md` |
| Change routing | SKILL.md `description` and `triggers` (read by the GPT routing call) and `priority` (keyword stand-in); the routing rules in `llm_runtime._route()`; re-run `test_skills` |
| Change how GPT-5.4 is instructed | the skill files first; chat-mechanics wording in `llm_runtime.runtime_notes()`; model/effort in `.env` or `config/settings.py` |
| Change the demo chat's look | `public/index.html` only (display only; it makes no decisions) |
| Mock data | CSVs; check `mock/data/README.md` "rows the tests depend on" and the deck examples (§5.7) |
| Go live | `integrations/bny/services.py` + `DCA_MODE=bny`; real `_sink` in `audit.py`; point `OPENAI_BASE_URL`/credential at BNY's on-prem GPT-5.4 (or rewrite `llm_client.py` only); adjust `handle()` in `a2a_server.py` if BNY's A2A envelope differs |
| Add the agent layer later | see section 6 |

---

## 6. The agent layer (not built — validated as compatible)

`agent/README.md` describes five additions: read-only tools (`get_card_status`,
`get_recent_transactions`, `get_card_limits`, `get_holds`) · the `access` flag becoming
operational (reads loop freely, writes always stop for confirmation) · a job state object
(`agent/state.py`) · a runner loop with step cap, time cap and loop detector
(`agent/runner.py`) that only ever calls `guardrails.dispatch` · workflow files per
multi-step job (`agent/workflows/*.md`).

**Clean seams, no change needed:** `dispatch()` is stateless and returns a `ToolResponse`;
`access` flags exist; `_read` skips confirmation; the guardrail re-checks every call;
`audit.write(detail=…)` is free-form so a `job_id` fits.

**Three files would need small edits:** `core/skills.py` (route returns one skill and
tools_for one action tool; a job needs a workflow-level prompt and tool list — the one place
the per-action split costs extra) · `interfaces/a2a_server.py` `_new_conversation()` (chooses
GptConversation or Conversation; a runner needs a branch there) · `core/handlers.py` `ActionSpec` (no `undo`
field, needed for compensation when a chain fails halfway).

**Untouched:** guardrails, schemas, cards, audit, models, integrations, tools, six skill files.
**Guy's instruction: keep `agent/` as it is — only the README, nothing implemented.** The
GPT-5.4 runtime is not the agent (§4.8).
Two things get harder: partial failure (decide undo/retry/hand to human per workflow) and
testing (scenario tests instead of exhaustive ones).

---

## 7. Open questions for Ben

1. **Is the orchestrator's entitlement check at client level or action level?** Decides `TRUST_UPSTREAM_ENTITLEMENT`. (Related: can entitlement be called from outside the card screen at all?)
2. The real API names, fields and error cases for the six actions (mapping table in `integrations/bny/services.py`).
3. Sample client and card record shapes — field names, id formats, status values.
4. Screen recordings of today's flow, to count the real clicks and match confirmation wording.
5. Does the platform expect agents to register tools (MCP-style), or does each agent host its own model? Decides whether `mcp_server.py` matters.
6. Can the NetX AI chat render **A2UI** panels, and which version (CrewAI supports v0.8)?
7. Who grants a chat surface write authority, and what review does that trigger? (The panel is read-only and certified that way.)
8. Does the orchestrator (CrewAI) own multi-step coordination, or would we?
9. Limits we invented: `MAX_TRAVEL_DAYS = 90`; does a travel notice end on its own after the trip; can a card reported lost/stolen be reactivated or only replaced.
10. (Internal, not for Ben) Which team Ben belongs to — not recorded.

---

## 8. Deliverables produced so far

### 8.1 `BNY_Debit_Card_Chat_CheckIn.pptx` — 8 slides (the old handoff said 7; it is 8)
Light house style: navy `#14314F`, title-slide night navy `#0E2337`, gold `#C9A227`
(dark gold `#A5851F`), green `#2E7D5B`, body text `#3C4C5A`, muted `#5B6B7A`, caption
`#7E8D9B`; Cambria headings (32pt bold navy, left at x 0.6"), Calibri body, Courier New for
code; 13.33 × 7.5 in. Speaker notes on every slide.
1. Title — "Debit Card Management by Chat"; "BNY Pershing · NetX360, advisor side · First check-in"; "Lock Jane Miller's debit card — one sentence, instead of a dozen clicks"; recommendation: a skill.
2. How we are running this project — design thinking: Discover → Describe → Ideate + Prototype (WE ARE HERE) → Test → Implement.
3. The problem: too many steps for a 30-second job — 7-step click path vs one sentence.
4. The solution: teach the chat one new job — advisor types → skill reads it (only AI) → entitlement check → API call runs.
5. Why a skill now — and when an agent would make sense (+ three agent scenarios).
6. What a skill actually looks like — SKILL.md + lock_card schema → filled form → five code steps.
7. What the chat could do — six agreed tools + six suggestions.
8. What we are assuming — and what we need from BNY; "Next:" line.

### 8.2 `BNY_Agent_Logic_2.pptx` — 2 slides, team's DARK template
Background `#0B2238`; brown `#4A3510` / amber `#E8B55E` (= the confirmation path); purple
`#3E3596` (tools); dark green `#18382C` (guardrail/action); grey `#3B3B39` (integrations);
dashed green container `#4E9E7A`. Slide 1: the current structure. Slide 2: the same plus the
agent layer in dashed amber. **Guy's latest version** (seen as an image) is titled
"DEBIT CARD MANAGEMENT AGENT / LOGIC — what is built today" and labels: "A2A in — Advisor's
request" (BNY chat → a2a_server.py), "Advisor's approval" (dashed amber, into the front door
and on to the guardrail), "tool calling (no MCP)" ↔ "tools/*.json — eight forms", "the filled
form", "schemas.validate", "Guardrail — guardrails.py … builds the confirm panel and sends back
to advisor's chat", "Send confirmation request to chat" (amber, back to BNY chat), "call to
action — only after Confirm", "Action, then audit", "the one API call" → "integrations/ —
mocked today, BNY later", "A2A out [A2UI] — result panel 'Card ending 4417 is locked.'"
**Known design problem on slide 2 (agent version):** dashed amber is used for both the
confirmation path (trip 2, "only after Confirm", the confirm panel) and the agent additions
("ADDED FOR THE AGENT VERSION", the dashed loop on the right, the box listing
`agent/state.py`, `agent/runner.py`, `agent/workflows/*.md`). That wrongly suggests trip 2 and
Confirm need the agent. Agreed fix (not yet applied — Guy must attach the deck): keep amber
for the confirmation path as on slide 1; give the agent additions their own colour (e.g.
dashed light blue or white); move the "ADDED FOR THE AGENT VERSION" label onto the box of
agent files (it currently sits above "BNY chat"). See section 4.8.
Naming advice given: call the diagram a **request flow diagram** (alternatives: system
architecture diagram; architecture and request flow); suggested subtitle
"Request flow — the AI reads it, code checks it, the advisor confirms it". Not applied by us.

### 8.3 `BNY_Six_Skills.pptx` — 18 slides, built by `deliverables/build_six_skills_deck.js` (pptxgenjs)
Same light house style as the check-in deck. Rebuild with
`PPTX_SKILL=<path to the pptx skill folder> node deliverables/build_six_skills_deck.js`
(needs `pptxgenjs`, `react`, `react-dom`, `react-icons`, `sharp`, and the pptx skill's
`scripts/apply_theme.js`). Paths are relative: the appendix reads `../skills/debit-card/`,
and the deck is written next to the script — so **if a skill file changes, rebuild the deck
and the appendix updates itself.** All content (titles, examples, notes) is in the `SKILLS`
array and the slide blocks of the script; edit there and rebuild, then render and check.
1. Title (dark) — "Six skills, one chat"; subtitle "BNY Pershing · NetX360, advisor side · How each debit card action works" (Guy was offered "What each action does, asks and checks" — not applied); six skill chips.
2. Every skill follows the same five steps — Find the client → Find the card → Fill the gaps → Restate and wait → Act and report; "When it asks instead of guessing" cards (two clients share a name / two cards / vague wording / fuzzy date or place).
3–8. One slide per skill, identical layout. Left: tag pill (Reversible / Issues a new card / Cannot be undone / Blocks + flags the account / The hardest of the six), WHAT IT DOES, THE ADVISOR MIGHT SAY (trigger chips), WHAT THE CHAT NEEDS BEFORE IT ACTS (field chips), BUILT-IN SAFETY (3 bullets). Right: a NetX AI-style chat mock-up. Footer caption + speaker notes.
   - 3 **Lock** — Robert Castellano, two cards: "Which card? Robert has two." [...2201] [...2202] → advisor types "2202" → confirm → "Card ending 2202 is locked."
   - 4 **Unlock** — "Unlock Sarah Chen's card" → two clients → "4409" → "Unlock the debit card ending 9902 for Sarah Chen (account ...4409)?" → unlocked. Footer notes the invisible third Sarah Chen.
   - 5 **Replace** — Jane, "cracked" → "Send it to 14 Hudson St…, the address on file?" → Yes → confirm (reason damaged) → "Replacement ordered. The card ending 4417 is cancelled."
   - 6 **Close permanently** — "Cancel Jane Miller's card" → "Lock it for now, or close it permanently?" → "Close it, she switched banks" → red confirm "This cannot be undone…" with red "Close card" button.
   - 7 **Report lost or stolen** — "Lost, or stolen? And are there any charges she doesn't recognise?" → "Lost. No odd charges." → confirm → "Card blocked and account flagged." → "Would you like me to order a replacement?" Footer ties it to the Jonathan interview.
   - 8 **Travel notice** — "Jane Miller is off to Georgia next month for a couple of weeks" → "Georgia the country, or the US state?" → "The country" → confirm "Travel notice, card ending 4417: Georgia (country), 1–15 November?" with note "Dates read from 'next month for a couple of weeks'" and buttons **Confirm · Change dates · Cancel** → "Travel notice added."
9. The six at a glance — table: skill · can it be undone (Lock: yes with Unlock; Unlock: yes with Lock; Replace: no, a new card is mailed; Close: no, never; Lost/stolen: no, it stays blocked until replaced; Travel: ends by itself after the trip — **the last two are our assumptions**) · extra question · field count.
10. Appendix title (dark) — lists the seven files and paths.
11–18. Appendix — full text of `_shared.md` (2 slides) and each SKILL.md (one slide each), two code columns, Courier New 10pt, colour-coded (front matter green, headings navy bold, examples gold, tables grey). Hard-wrapped lines were joined so text wraps at the column width; words are unchanged (verified line by line). Footer says so.

**NetX AI mock-up spec (in `deliverables/build_six_skills_deck.js`, `const N`):** panel bg `F5F8FC`, border `D5DDE8`,
advisor pill `DCE6F4`, text `2B2F36`, header `1F2D4A`, primary blue `2F5D9A`, hint `8A93A0`,
"Guide Me" tab `1F2D4A`; icons from react-icons (HiOutlineSparkles, Feather icons).
Choice options are side-by-side buttons; the picked one is tinted `E8EFF9` with a blue border.

### 8.4 Other
- `BNY_Debit_Card_Chat_Architecture.pdf` — 5-page plain-English explainer with diagrams (WeasyPrint). Not uploaded; reproducible.
- First reflection blog post (ethics) — done.

---

## 9. Changes made in the previous chats (so you know what is new)

**Earlier:**
1. `interfaces/local_runtime.py`: typed answers to choice panels work (`_match_choice`). `tests/test_choices.py` added (18 checks).
2. `BNY_Six_Skills.pptx` and its build script built and revised (NetX AI chat style, Change dates, appendix). Repository packaged as one zip with this handoff and `deliverables/`.
3. Facts established: A2UI capabilities (§4.6); guaranteed vs model-dependent behaviour (§4.7); the 90-day limit is ours; Pershing background (CSFB clearing unit bought by Bank of New York in 2003 for ~$2B; renamed in 2024). The origin of the name "Pershing" was not confirmed — do not state one.

**Latest — GPT-5.4 made the real understanding layer, and a demo chat added.** Guy's choices:
GPT-5.4 via **his own OpenAI API key** (public model id `gpt-5.4`; BNY's on-prem copy is not
reachable); **GPT-5.4 also does the routing** (not keywords); **six actions only** (read-only
questions such as "what cards does Robert have?" get the fixed out-of-scope reply, as agreed
with Ben); an **advisor switcher** in the chat header (mock sign-in). The agent stays unbuilt.
- New: `interfaces/llm_runtime.py`, `interfaces/llm_client.py`, `public/index.html`,
  `tests/test_llm_runtime.py` (36 checks), `.env.example`.
- `interfaces/a2a_server.py`: picks the runtime, serves the chat page and `/api/*`, threaded server.
- `config/settings.py`: `.env` loader and the AI-layer settings (§5.6).
- `core/cards.py` / `core/handlers.py` / `core/guardrails.py`: confirm panels can carry extra
  buttons and a `danger` flag; travel notice has **Change dates**; close is `danger`; lost/stolen
  has a fixed follow-up offering a replacement; travel dates shown readably. Presentation only —
  no check or step changed.
- `interfaces/local_runtime.py`: audit now records the original request (not "yes"); ordinals
  ("the second one") in `_match_choice`; `change_dates` handled; shared helpers `with_follow_up`,
  `CHANGE_DATES`.
- `skills/debit-card/_shared.md`: "Before acting" now says the confirmation panel is the
  restate-and-wait step; "never call your action tool until every field is filled"; options as
  buttons. `travel-notice/SKILL.md`: inferred dates may be shown on the panel (Change dates);
  example updated. **The skills deck appendix was rebuilt to match.**
- Docs fixed: MCP wording (ARCHITECTURE, README, HOW-IT-FITS, schemas.py, mcp_server.py),
  test counts, `ports.py` path; README has the demo steps; INTEGRATION has the on-prem swap;
  ARCHITECTURE and skills/README describe AI routing.

**Latest — hosted team demo on Vercel + Convex (built, tested; not yet deployed by Guy).**
Guy's choices: Vercel for hosting; **Convex** for data (he already uses Convex in another
project; Supabase is not used); **one shared data set** for all teammates; a demo-only
**Reset demo data** button that restores a **saved default state**; a team passcode
screen; and a server secret so only our server can call the Convex functions.
- Why a database: Vercel is stateless (each message may reach a fresh process), so card
  changes, travel notices, flags, conversations and the audit live in Convex. Clients and
  entitlements stay in the CSVs. Locally, without `CONVEX_URL`, everything is in memory.
- New: `convex-demo-db/` (Convex project folder: `convex/schema.ts`, `convex/demo.ts` —
  getCard, listCards, setCardStatus, insertCard, addTravelNotice, listTravelNotices,
  addFlag, load/saveConversation, addAudit, listAudit, ensureDefaults, reset; each checks
  `DEMO_SERVER_SECRET`), `integrations/convex_store/` (stdlib HTTP client + ConvexCardSystem),
  `interfaces/threads.py`, `api/chat.py`, `api/info.py`, `api/audit.py`,
  `api/demo/reset.py`, `api/demo/check-passcode.py` (all alias `a2a_server.WebHandler`),
  `vercel.json` (output `public/`, functions `api/**/*.py`, maxDuration 60),
  `.python-version` (3.12), `.vercelignore`, `demo_tools/` (reset + passcode endpoints,
  README), `public/demo-tools.js` (passcode screen + "Demo controls" bar), `DEPLOY.md`,
  `tests/test_hosting.py` (20).
- Changed: the chat page moved to `public/index.html` (tiny demo hook: loads
  `demo-tools.js` only if `/api/info` reports demo_mode or passcode_required);
  `interfaces/a2a_server.py` (one `route()` for local and Vercel; conversation
  snapshot/restore per message, only for the same advisor and runtime; passcode check;
  `/api/demo/*` forwarded to `demo_tools`); `snapshot()`/`restore()` in both runtimes;
  `core/audit.add_sink` (audit also written to Convex); `config/settings.py`
  (`CONVEX_URL` with `VITE_CONVEX_URL` fallback, `DCA_STORE`, `DEMO_SERVER_SECRET`,
  `DEMO_MODE`, `DEMO_PASSCODE`); tests and `demo/run_demo.py` force `DCA_STORE=memory`.
- **Saved default state** = `integrations/mock/data/cards.csv`; on first start the server
  writes it to Convex's `defaults` table (with a fingerprint, refreshed when the CSV
  changes). Reset copies it back into `cards` and empties travel notices, flags,
  conversations and audit — same result as restarting the local server.
- Settings: Vercel needs `OPENAI_API_KEY`, `CONVEX_URL` (**production** Cloud URL),
  `DEMO_SERVER_SECRET`, `DEMO_MODE=true`, `DEMO_PASSCODE`; Convex (Production, and
  Development if used locally) needs `DEMO_SERVER_SECRET`. Guy's Convex project:
  `BNY_Debit_Card_Manager` (dev deployment `energetic-dachshund-985`; production not yet
  created — `npx convex deploy`). Suggested passcode: `corestone-amber-7429`.
- Verified: Convex functions type-check against the real `convex` package; their compiled
  handlers were run against an in-memory database behind Convex's HTTP API format; two
  separate Python servers shared one data set (question on one, Confirm on the other);
  wrong secret refused; passcode and reset tested in a browser. **Not yet run on real
  Vercel or real Convex** (blocked from the build sandbox) — first real run is Guy's
  deploy, following `DEPLOY.md`.
- Final deliverable: unset `DEMO_MODE`/`DEMO_PASSCODE` or delete `demo_tools/` and
  `public/demo-tools.js`; nothing in the product depends on them.
- Local SSL note: on macOS python.org installs, run "Install Certificates.command" if
  OpenAI calls fail with CERTIFICATE_VERIFY_FAILED.

**Latest — agent plan written, NOT implemented.** `PLAN-AGENT-DECLINED-CARD.md` (repo
root) is the full, checked plan for the first agent job ("why was my card declined?"):
mock data, four read-only tools, `agent/state.py`, `agent/runner.py`,
`agent/workflows/declined-card.md`, the `finish_investigation` tool, code-enforced rules,
tests, docs, examples, assumptions and build order. Guy will say when to implement it;
until then `agent/` stays README-only. Three decisions are open (plan §1).

## 10. Known gaps and inconsistencies (verified against the code — fix only when asked)

### 10.1 The keyword stand-in (no-key fallback only) still breaks some skill rules
Only matters if the demo runs without a key. In `interfaces/local_runtime.py` `_continue()`:
- `replace_card` reason defaults to `"damaged"` if "damag" appears, else `"other"` (skill says ask).
- `report_lost_stolen` incident_type defaults to `"lost"` unless "stolen/stole" appears.
- `close_card` reason defaults to `"advisor request"`; "cancel the card" never asks lock or close.
- Travel: "What are the travel dates?" is asked without saving pending state (answer lost);
  "next month" = today + 30 days; Change dates only replies that it needs GPT-5.4.
- Keyword routing misroutes "I'm going to need you to lock…" to travel notice.
GPT-5.4 mode does not use any of this.

### 10.2 GPT-5.4 mode — what is not guaranteed, and what is untested
- Asking the right questions (Georgia, lock or close, lost or stolen, reason, address) and
  choosing the right skill depend on GPT-5.4 following the prompts (§4.7). Before showing BNY,
  run a set of test sentences live and adjust the skill files or `runtime_notes()`.
- Never run against the live OpenAI API from the build environment; the first live run is on
  Guy's machine. If OpenAI rejects a parameter (e.g. `reasoning_effort`), set
  `DCA_REASONING_EFFORT=` (empty) in `.env` to omit it.
- The panel's "Dates" show what the model filled in; the deck's extra line "Dates read from
  'next month…'" is not on the real panel.
- Each message costs two to four model calls; conversation history is kept in memory per
  server run (restart to reset).

### 10.3 Audit does not fully match what the docs and slides claim
- **Fixed:** `advisor_typed` now records the original request in both runtimes.
- Still true: only **entitlement refusals (flag off)** are audited. Precheck refusals
  (`already_locked`, `card_closed`, bad dates), ownership `bad_request`, schema rejections,
  `no_match`, and **cancellations** are not written, yet `audit.py`, the README, the check-in
  deck and the Agent Logic slide say "every refusal" is logged.

### 10.4 Other stale or inaccurate text
- `core/cards.py` / `models.py` / `a2a_agent_card.json` call the payload "A2UI"; it is A2UI-inspired, not real A2UI messages (§4.6).
- `integrations/mock/data/README.md` asserts the lock-but-not-close split "is what our guardrail checks that BNY's upstream check does not" — that is an assumption (open question 1).
- `CONFIRM_REQUIRED_FOR_WRITES` is declared but not read anywhere.
- The check-in deck has 8 slides (an old handoff said 7).
- Decks describe "the only place AI is used" as the understanding step. Still true: routing is part of understanding, and both are GPT-5.4.

---

## 11. Glossary (plain English)

- **NetX360** — BNY Pershing's platform advisors log into. **NetX AI** — its built-in chat panel (read-only today). **NetXInvestor** — the end-investor equivalent.
- **Corestone** — BNY Pershing's cash-management product; the debit card belongs to it. **AMA Suite** — Asset Management Account area of NetX360.
- **Orchestrator** — BNY's CrewAI-based agent that authenticates, checks entitlement and routes requests to agents like ours.
- **A2A** — agent-to-agent protocol (how the orchestrator calls us). **A2UI** — declarative UI panels inside A2A replies. **Tool calling** — the model returns a tool name + filled-in form. **MCP** — a protocol for serving tools from a separate server (not used).
- **Skill** — instructions (SKILL.md) + one tool the model may call. **Agent** — a loop that plans several steps itself.
- **Entitlement** — whether this advisor may act on this client (and, possibly, this action).
- **Guardrail** — our code (`core/guardrails.py`) that decides whether a requested action actually runs.
- **Trip 1 / Trip 2** — the request that produces the confirm panel / the Confirm click that runs it.

---

## 12. How to work with Guy

- **Concise, plain English, short responses.** No jargon unless he asks for it.
- **Concrete examples and intuition** over technical completeness.
- He pushes back when answers are long or abstract and asks for simpler re-explanations. Expect several rounds.
- **Iterative:** drafts, variants, narrowing to a final. When he asks for content, he often wants to see it written in the chat **before** you generate slides.
- **He checks the work and catches real errors** (MCP placement, a missing arrow, duplicated content, the wrong advisor framing, missing multi-card examples). **Verify against the actual code before asserting; say plainly when something was wrong.** He asked explicitly for expert-level accuracy and double-checking of every suggestion.
- Diagrams: graphical, intuitive, **every arrow labelled**.
- Slides: match the house style of the deck he points to; render and visually check every slide before delivering; fix overflow and overlaps.
- When proposing names or wording, give a recommended pick plus a few alternatives, briefly.
- When a deck example uses data, use the mock data in §5.7 so it matches the code.
