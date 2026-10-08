# How it fits together

Read this before opening the code. It follows one request all the way through,
naming the real file at each step. Fifteen minutes, and the repository will
make sense.

The example is "lock Jane Miller's card" because it is the shortest. All six
actions take exactly the same path — only the contents of `core/handlers.py`
differ between them.

---

## The four kinds of file

Everything in the repo is one of these. If you know which kind you are looking
at, you know what to expect from it.

| Kind | Where | What it is |
|---|---|---|
| Instructions | `skills/debit-card/` | One skill per action, plus `_shared.md` |
| Contracts | `tools/*.json` | The forms the model fills in |
| Our code | `core/` | Checks, decisions, the audit |
| The outside world | `integrations/` | Mocked today, BNY's systems later |

Plus two thin edges: `interfaces/` (how we are called) and `config/` (which
world we are talking to).

---

## Step 1 — The request arrives

`interfaces/a2a_server.py`

BNY's orchestrator has already authenticated the advisor, possibly resolved the
client name, and decided this request is ours. What reaches us is small:

```json
{ "advisor_id": "ADV-1234", "utterance": "Lock Jane Miller's card",
  "conversation_id": "t1" }
```

The file does almost nothing: finds or creates the conversation thread, calls
`Conversation.send()`, returns the result as JSON. Deliberately thin, because
nothing here should be able to make a decision.

**One rule worth noting.** `advisor_id` comes from the authenticated session,
never from the message text. If a message claimed to be from another advisor,
we would ignore it.

---

## Step 2 — Working out what was asked

`interfaces/local_runtime.py` + `core/skills.py` + `skills/debit-card/` + `tools/*.json`

This is the only place AI is involved — and in the prototype there is no AI at
all. `local_runtime.py` is a keyword interpreter standing in for GPT-5.4 so the
whole thing runs with no API key. It does the same job the model will do:

1. Route the sentence to one of six skills (`skills.route`), highest
   priority first — so "lost her wallet, lock it" reaches `report-lost-stolen`
   rather than `lock-card`.
2. Resolve the client — call `find_client`, and if more than one matches, ask.
3. Resolve the card — call `list_cards`, and if more than one, ask.
4. Fill in anything else that action needs.

The rules it follows are `_shared.md` plus that one skill's file: when to act,
what to ask, and what never to do. The model is given one action and three
tools, not six and eight. The shape of what it produces is fixed by `tools/lock_card.json`:

```json
{ "name": "lock_card", "access": "write",
  "input_schema": { "properties": {
      "client_id": { "type": "string", "description": "...never invent one." },
      "card_id":   { "type": "string" },
      "reason":    { "type": "string" } },
    "required": ["client_id", "card_id"] } }
```

Out comes a filled-in form:

```json
{ "client_id": "C-88210", "card_id": "CARD-4417" }
```

**This is a request, not an action.** Nothing has happened yet.

**Going live:** replace the keyword rules with a call to BNY's GPT-5.4, passing
`skills.system_prompt(skill)` and `skills.tools_for(skill)`. Nothing else in
the repo changes.

---

## Step 3 — Checking the form

`core/schemas.py`

Loads every `tools/*.json` once, then validates. A missing required field, a
field that does not exist, a value outside an allowed list — all rejected here,
before our code runs.

```
missing card_id              -> "Missing required field: card_id"
{"customer": "Jane"}         -> "Unknown field: customer"
reason: "because"            -> "reason must be one of: damaged, lost, ..."
```

In production an MCP runtime does this for you. It is implemented here anyway
so the prototype needs no dependencies, and so a reviewer can see the check
rather than taking it on trust.

---

## Step 4 — Deciding whether it happens

`core/guardrails.py` — **the file that matters**

Everything funnels through one function:

```python
dispatch(services, session, tool_name, tool_input, confirmed=False)
```

It splits by the `access` flag on the tool.

### Read tools (`find_client`, `list_cards`)

Nothing changes, so there is no confirmation step. Searches are still scoped to
the advisor's own book by the directory itself — in the mock data there are
three Sarah Chens and ADV-1234 sees two of them — because a name search spans
many clients, not just the one the orchestrator approved.

### Write tools (the six actions)

Five steps, in this order, every time:

1. **Entitlement** — skipped by default. BNY's orchestrator checks entitlement
   before routing and only sends approved requests, so we trust it and record
   `entitlement_checked_by: bny_orchestrator` in the audit. Setting
   `TRUST_UPSTREAM_ENTITLEMENT` to false in `config/settings.py` makes the agent
   check the specific action too — useful if the upstream check turns out to be
   at client level, since locking and permanently closing are not equal. When it
   does refuse, the advisor is told only that they lack permission, never why,
   because the explanation would leak that the client exists.
2. **Ownership** — `services.cards.get_card(card_id)`, then check the card
   really belongs to that client.
3. **State rules** — the action's own `precheck` from `core/handlers.py`.
   Already locked? Card closed? Travel dates backwards? Refuse now.
4. **Confirmation** — if `confirmed` is false, build a summary card and
   **return**. The function stops here. Nothing has been called.
5. **Action and audit** — only once the advisor has confirmed: one call to the
   card system, then `core/audit.py` writes the record.

So a lock is **two trips** through this file. First trip returns a card.
Second trip, carrying `confirmed=True`, does the work.

---

## Step 5 — What differs between the six actions

`core/handlers.py`

Each action is one `ActionSpec`: a title, a `precheck`, a `summary`, and an
`execute`. Everything else is shared, which is why adding a seventh action is a
small change.

| Action | Its own rule |
|---|---|
| `lock_card` | Refuses if already locked |
| `unlock_card` | Refuses if not locked; a closed card needs a replacement |
| `replace_card` | Reason from a fixed list; delivery address shown and confirmed |
| `close_card` | Warning on the card, button reads "Close permanently" |
| `report_lost_stolen` | Blocks the card and flags the account together |
| `travel_notice` | Dates validated: order, not in the past, under 90 days |

---

## Step 6 — Talking to the outside world

`integrations/`

Three interfaces in `ports.py` — client directory, entitlement service, card
system. `core/` never imports a mock directly; it receives a `Services` object
built by `config/settings.py`. That indirection is what makes the BNY swap a
single-folder change.

- `integrations/mock/data/*.csv` — 20 clients, 21 cards, 3 advisors. Editable
  in Excel.
- `integrations/mock/services.py` — flips statuses in memory.
- `integrations/bny/services.py` — the template to fill in, with a mapping
  table for the real endpoint names.

Every action returns the same two keys, which is the contract BNY must match:

```python
{"status": "locked", "message": "Card ending 4417 is locked."}
```

---

## Step 7 — What the advisor sees

`core/cards.py`

Three card kinds cover all six actions:

- **confirm** — fields, an optional warning, Confirm and Cancel
- **choice** — when we must ask: which client, which card, which Georgia
- **result** — what happened

We describe the card; BNY's chat draws it with its own components. `to_text()`
produces the same content as plain text, so if card rendering is unavailable
nothing breaks.

```
Lock debit card
  Client: Jane Miller
  Account: ...8821
  Card: ...4417
  [Confirm] [Cancel]
```

---

## The whole path, in one list

```
interfaces/a2a_server.py      the request arrives
interfaces/local_runtime.py   which tool, which client, which card   <- the only AI
   reads skills/debit-card/SKILL.md and tools/*.json
core/schemas.py               is the form well formed?
core/guardrails.py            entitled? owns it? confirmed? act. log.
   uses core/handlers.py for what differs between actions
integrations/                 the card system (mock today)
core/audit.py                 the permanent record
core/cards.py                 the reply the advisor sees
```

---

## Run it yourself

```bash
python -m demo.run_demo            # a scripted conversation
python -m tests.test_guardrails    # 17 checks, including the refusals
```

Keep this document open while the demo runs. Every printed line is one pass
down that list.

---

## Where the agent version plugs in

`agent/README.md` has the detail. In short: a runner loops over
`guardrails.dispatch` instead of calling it once, using the `access` flag
already on every tool to decide what needs confirming. The five steps do not
change. The agent is a loop around the skill, not a replacement for it.
