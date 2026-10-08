# One skill per action

Six skills, one for each card action, plus `_shared.md` holding the rules they
all obey.

```
_shared.md                  rules every skill inherits — one copy, not six
lock-card/SKILL.md
unlock-card/SKILL.md
replace-card/SKILL.md
close-card/SKILL.md
report-lost-stolen/SKILL.md
travel-notice/SKILL.md
```

## How a skill file is put together

Frontmatter, then the rules that belong to that action alone:

```
---
name: lock-card              folder name; how the registry refers to it
tool: lock_card              the one action tool it may call
lookups: find_client, list_cards   read-only tools it may use to resolve things
priority: 60                 higher wins when several skills match
triggers: lock, freeze, suspend, stop the card
description: ...
---
```

`core/skills.py` reads these. Nothing else in the codebase knows how many
skills there are.

## How one gets chosen

With GPT-5.4 (`interfaces/llm_runtime.py`), a short routing call reads the
conversation plus each skill's `description` and `triggers` and returns one
skill name, or "none". So write descriptions and triggers for a reader, not
only for a keyword match.

Without a model, the keyword stand-in uses `skills.route(utterance)`, which
matches triggers, **highest priority first**. That
ordering is what keeps the cross-action cases right:

> "Jane lost her wallet, lock the card"

matches both `lock-card` and `report-lost-stolen`. The latter has priority 90,
so it wins — losing a card is the more consequential reading, and blocking
without flagging the account would be the wrong outcome. The skill then offers
the alternative rather than deciding silently.

If you add a skill, set its priority deliberately against the ones already
there. `tests/test_skills.py` checks the six cases that matter.

## What the model actually receives

```python
skill = <chosen by the routing call>     # or skills.route(utterance) without a model
skills.system_prompt(skill)   # _shared.md + that skill's body
skills.tools_for(skill)       # its own tool + find_client + list_cards
```

(The GPT-5.4 runtime also adds short "runtime notes" about how this chat
works - today's date, that the action tool only shows a confirmation panel -
and a presentation-only `present_options` tool for showing buttons.)

So the model sees one action and three tools, not six actions and eight. That
is the main benefit of the split: a smaller decision, and a shorter prompt.

## The cost, and how it is contained

Six files drift. Keeping every common rule in `_shared.md` is what stops that —
client resolution, card resolution, the confirmation wording, the refusal
rules and the error table exist once. A skill file should only ever contain
what is true for that action and no other.

If you find yourself copying a paragraph between two skills, it belongs in
`_shared.md`.

## Adding a seventh action

1. `tools/<name>.json` — the schema, with `"access": "write"`.
2. `skills/debit-card/<name>/SKILL.md` — frontmatter plus its own rules.
3. `core/handlers.py` — an `ActionSpec` saying what to check, show and run.
4. `integrations/ports.py` and the mock — the call itself.

Nothing in `core/skills.py`, `core/guardrails.py` or the runtime changes.
`tests/test_skills.py` will fail until steps 1 and 2 agree with each other.
