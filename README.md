# Debit Card Management Agent

A chat-driven way for a NetX360 advisor to manage a client's Corestone debit
card. Six actions: lock, unlock, replace, close permanently, report lost or
stolen, travel notice.

Built as **a skill with a guardrail layer**, not a standalone agent, and shaped
so the agent version can be added later without rewriting any of it.

> **Picking this up in a new chat? Read `PROJECT-CONTEXT-HANDOFF.md` first.**
> It covers the project, the people, every file, and what needs AI, what needs
> the (not yet built) agent, and what is plain code.

## Run the demo (chat with it)

You need Python 3.10 or newer and an OpenAI API key. Nothing to install.

1. **Add your key once.** In this folder, copy `.env.example` to a new file
   named `.env` and put your key after `OPENAI_API_KEY=`. (Or set the
   `OPENAI_API_KEY` environment variable instead.) Never commit `.env` or paste
   the key into a chat.
2. **Start the server** from this folder:
   ```bash
   python -m interfaces.a2a_server
   ```
   It prints `understanding layer: GPT-5.4`. (macOS may need `python3`.)
3. **Open http://localhost:8080** in a browser and type, for example:
   - *Can you freeze Robert Castellano's card?* (two cards: it asks which)
   - *Jane Miller is off to Georgia next month for a couple of weeks*
   - *Jane lost her wallet*  ·  *Cancel Jane Miller's card*  ·  *Unlock Sarah Chen's card*
   - *What's Jane's balance?* (not one of the six actions: a fixed reply)
4. Switch advisor in the header to show that ADV-5678 cannot see Jane Miller.
   Restart the server to reset the mock cards. `http://localhost:8080/api/audit`
   shows the audit trail.

With no key, the same page runs on the keyword stand-in (no AI) and says so
under the header.

## Share it with the team (hosted on Vercel + Convex)

See **`DEPLOY.md`**: one link, a team passcode, GPT-5.4, shared data in Convex,
and a demo-only **Reset demo data** button above the chat. The product code is
the same; only where changes are stored differs (`config/settings.py`
`active_store()`: memory locally, Convex when `CONVEX_URL` is set).

## Run the checks

```bash
python -m tests.test_guardrails    # the cases worth showing BNY
python -m tests.test_skills        # the skill split stays consistent
python -m tests.test_choices       # typed answers to "which card / which client?"
python -m tests.test_llm_runtime   # the code around GPT-5.4, with a scripted model
python -m tests.test_hosting       # save/restore between messages, passcode, reset
python -m demo.run_demo            # a scripted conversation (keyword stand-in)
```

The checks need no key and no network.

**New to this? Read `HOW-IT-FITS-TOGETHER.md` first.** It follows one request
through every file in about fifteen minutes.

## The idea in one paragraph

The advisor types a sentence. GPT-5.4 routes it to one of six skills — one per
action — then reads that skill plus the shared rules and fills in its single
tool's form. That is the only AI. The form is checked against its schema, then
our code - not the model - decides whether the action happens: is this advisor
entitled to this action, does the card belong to that client, has the advisor
confirmed. Only then does the card system get called, and the attempt is logged.

## Where everything lives

```
HOW-IT-FITS-TOGETHER.md        start here - one request, file by file
skills/debit-card/             one skill per action, plus _shared.md
core/skills.py                 the skill registry: routing, prompts, tool lists
tools/*.json                   eight tool schemas; the forms the model fills in
core/guardrails.py             THE IMPORTANT ONE - the steps, in order
core/handlers.py               what differs between the six actions
core/schemas.py                loads and validates the forms
core/cards.py                  the A2UI card payloads, plus a text fallback
core/audit.py                  the permanent record
core/models.py                 Session, Client, Card, ToolResponse
core/errors.py                 the error codes we return
config/settings.py             mock or live, and the safety limits
integrations/ports.py          the three interfaces to the outside world
integrations/mock/data/*.csv   the mock dataset - edit in Excel, no code change
integrations/mock/              the fake systems that read it
integrations/bny/services.py   TEMPLATE for the real ones - see INTEGRATION.md
interfaces/a2a_server.py       the front door BNY's orchestrator calls; also serves the demo chat
interfaces/threads.py          where conversations are kept between messages (memory or Convex)
web/index.html              the mock NetX AI chat panel (display only, no decisions)
interfaces/llm_runtime.py      THE AI LAYER - GPT-5.4 picks the skill and fills its form
interfaces/llm_client.py       the one place that calls the OpenAI API (standard library)
interfaces/local_runtime.py    keyword stand-in for GPT-5.4, used when there is no key
interfaces/a2a_agent_card.json how we describe ourselves to the agent registry
interfaces/mcp_server.py       optional packaging only - not in the request path
agent/README.md                the agent layer, described but NOT built
.env.example                   where your OpenAI key goes (copy to .env)
tests/ demo/                   proof it works, and something to show people
deliverables/                  the decks, and the script that builds the skills deck
PROJECT-CONTEXT-HANDOFF.md     full project context for a new chat
PLAN-AGENT-DECLINED-CARD.md    plan for the first agent job (not built yet)
DEPLOY.md                      how to host the team demo on Vercel + Convex
app.py, vercel.json            Vercel entry point (hands off to a2a_server.route)
integrations/convex_store/     the card system and audit stored in Convex (hosted demo)
convex-demo-db/                the Convex tables and functions, incl. saved default state + reset
demo_tools/, web/demo-tools.js   DEMO ONLY: passcode screen and reset button
```

## What we assumed

We have no API names, no real data and no test environment yet, so:

- Each card action already exists as its own call. Today's screens do exactly
  these six things, so the endpoints must exist in some form.
- Field names are conventional: client id, account last four, card last four,
  holder name, status, address on file.
- BNY's orchestrator authenticates the advisor, may resolve the client name to
  an id, and routes the request to us over A2A.
- Entitlement is checked by BNY's orchestrator before anything reaches us, and
  only approved requests are routed to us. We trust that by default
  (`TRUST_UPSTREAM_ENTITLEMENT` in `config/settings.py`) and record in the audit
  that the check was made upstream. The flag turns on a second check here if
  the upstream one proves to be coarser than our actions are.
- The chat surface can render simple cards. If it cannot, every card has a
  plain-text equivalent and nothing breaks.

Each assumption is marked in the code where it bites. See `INTEGRATION.md`.

## What is deliberately not here

- No production UI. The chat panel is BNY's; we return card payloads for it to
  render. `web/index.html` is a demo mock of it.
- No multi-step agent. See `agent/README.md` for exactly what that would add.
- No retries. Re-running a write without the advisor asking is not our call.

## The mock dataset

`integrations/mock/data/` holds three CSVs: clients, cards and entitlements.
20 clients, 21 cards, 3 advisors. Open them in Excel and edit; nothing in the
code needs to change. See that folder's `README.md` for the column meanings and
which rows the tests rely on.
