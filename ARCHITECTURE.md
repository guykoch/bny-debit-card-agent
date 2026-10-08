# Architecture

## One request, end to end

```
advisor types in the NetX360 chat
        |
        |  BNY orchestrator: authenticates, maps the name, routes      (theirs)
        v
  A2A  ->  interfaces/a2a_server.py                                    (ours, from here down)
        |
        v
  understanding: GPT-5.4 picks the skill, then fills that skill's form
        |        (SKILL.md + tools/*.json); asks when something is unclear
        v
  core/schemas.py          rejects a malformed form
        |
        v
  core/guardrails.py       1 entitlement (trusted upstream by default)
        |                  2 the card belongs to that client
        |                  3 stop and wait for Confirm
        |                  4 one call to the card system
        |                  5 write the audit record
        v
  integrations/            mocks today, BNY's APIs later
        |
        v
  A2UI card back to the chat
```

## Why the guardrails sit where they do

The model can reach the tools. It cannot reach past the checks, because the
checks are not in its path - they are in the function the tool call lands on.
Nothing an advisor types, and nothing a model infers, changes that ordering.

Two consequences worth stating to a reviewer:

- **The model never evaluates permissions.** It does not know whether an
  advisor is entitled, and `SKILL.md` forbids it from commenting on the subject.
- **Every write stops.** `confirmed` defaults to false. A tool call alone never
  changes anything; the advisor's click is the authorisation.

## Entitlement

BNY's orchestrator checks entitlement and only routes requests it has approved.
We trust that. `TRUST_UPSTREAM_ENTITLEMENT` in `config/settings.py` is true by
default, step 1 is skipped, and the audit row records
`entitlement_checked_by: bny_orchestrator`.

The flag exists because of one question worth putting to BNY: is the upstream
check at client level, or at action level? Our six actions are not equal in
weight - locking a card is reversible, closing one is not - and an approval to
deal with a client is not obviously an approval to do either. If the answer is
client level, set the flag to false and the agent checks the specific action
too, recording `entitlement_checked_by: agent`.

`integrations/mock/data/entitlements.csv` models the action-level case, so both
settings can be demonstrated. The test suite exercises both.

Either way the audit never implies we verified something we did not.

## One skill per action, with shared rules

Each of the six actions has its own skill folder under `skills/debit-card/`,
and `_shared.md` holds everything they have in common: client resolution, card
resolution, the confirmation wording, the refusal rules, the error table.
`core/skills.py` prepends it to whichever skill is chosen.

The benefit is a smaller decision for the model. Routing happens first, so the
model is given one action and three tools rather than six actions and eight,
with a prompt to match. Each action's rules can also be reviewed and changed on
their own.

The cost is drift between six files, and the shared file is what contains it.
A skill should only hold what is true for that action and nothing else; if a
paragraph would be copied between two skills, it belongs in `_shared.md`.

Routing is a short first GPT-5.4 call that sees each skill's description and
trigger words and returns one skill name, or "none" for anything that is not
one of the six actions. Its rules keep the cross-action cases right: "She lost
her wallet, lock the card" goes to `report-lost-stolen`, and "cancel her card"
goes to `close-card`, which asks whether the advisor means lock or close. The
keyword stand-in routes with the same trigger words and priorities, in code
(`skills.route`), and is what `tests/test_skills.py` checks. See
`skills/debit-card/README.md`.

## A2A, tool calling, A2UI - and why there is no MCP

They sit at different levels and are easy to confuse.

- **A2A** is between services: BNY's orchestrator and our agent. It carries the
  advisor id, the sentence, and optionally a resolved client id. See
  `interfaces/a2a_agent_card.json`.
- **Tool calling** is between the model and its tools, inside our agent. The
  schemas in `tools/` go into the model request; the model returns a tool name
  and a filled-in form; our code runs it. See `interfaces/llm_runtime.py`.
- **A2UI** is the format of a UI panel returned inside an A2A reply. Our panels
  (`core/cards.py`) are A2UI-inspired; every one also has a plain-text form.
- **MCP** is a protocol for publishing tools as a separate server for another
  process to reach. Our agent hosts the model and owns its tools in one
  process, so MCP has no role. `interfaces/mcp_server.py` is optional packaging
  for the case where BNY's platform hosts the model instead.

## What is AI and what is not

| Part | AI? |
|---|---|
| Choosing the skill for a message | GPT-5.4 (a short routing call) |
| Filling in that skill's form, asking about anything missing or unclear | GPT-5.4 |
| Lookups, the "which client / which card" panels, id checks | Plain code |
| Schema check, ownership, state rules, entitlement | Plain code |
| Confirmation panel, the Confirm click (a replay, no model call) | Plain code |
| The card action and the audit | Plain code |
| Multi-step jobs (the agent layer) | Not built - see `agent/README.md` |

`interfaces/local_runtime.py` is a keyword stand-in for the two AI rows, so
everything runs without a model. `config/settings.py` chooses between them.

## Replaceability

Everything BNY-specific is behind three interfaces in `integrations/ports.py`.
`core/` never imports anything from `integrations/mock/`; it receives a
`Services` object built in `config/settings.py`. That is what makes the
migration a single-folder change.
