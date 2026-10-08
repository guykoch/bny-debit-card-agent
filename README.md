# Debit Card Management Agent

A chat-driven way for a NetX360 advisor to manage a client's Corestone debit
card. Six actions: lock, unlock, replace, close permanently, report lost or
stolen, travel notice.

Built as **a skill with a guardrail layer**, not a standalone agent, and shaped
so the agent version can be added later without rewriting any of it.

## Run it

```bash
python -m tests.test_guardrails    # the cases worth showing BNY
python -m tests.test_skills        # the skill split stays consistent
python -m demo.run_demo            # a scripted conversation
python -m interfaces.a2a_server    # serve it on localhost:8080
```

No dependencies, no API key, no network. Python 3.10+.

**New to this? Read `HOW-IT-FITS-TOGETHER.md` first.** It follows one request
through every file in about fifteen minutes.

## The idea in one paragraph

The advisor types a sentence. It is routed to one of six skills — one per
action — and the model reads that skill plus the shared rules, then fills in
its single tool's form. That form is
checked against its schema, then our code - not the model - decides whether the
action happens: is this advisor entitled to this action, does the card belong
to that client, has the advisor confirmed. Only then does the card system get
called, and the attempt is logged either way.

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
interfaces/a2a_server.py       the front door BNY's orchestrator calls
interfaces/a2a_agent_card.json how we describe ourselves to the agent registry
interfaces/mcp_server.py       the production path for exposing tools
interfaces/local_runtime.py    stand-in for GPT-5.4 so this runs with no model
agent/README.md                what to add later for the agent version
tests/ demo/                   proof it works, and something to show people
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

- No UI. The chat panel is BNY's; we return card payloads for it to render.
- No multi-step agent. See `agent/README.md` for exactly what that would add.
- No retries. Re-running a write without the advisor asking is not our call.

## The mock dataset

`integrations/mock/data/` holds three CSVs: clients, cards and entitlements.
20 clients, 21 cards, 3 advisors. Open them in Excel and edit; nothing in the
code needs to change. See that folder's `README.md` for the column meanings and
which rows the tests rely on.
