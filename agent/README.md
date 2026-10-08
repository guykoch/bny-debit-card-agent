# The agent layer, later

Nothing in this folder is built yet. It is here so the extension points are
visible, and so nobody has to guess what "turn this into an agent" means.

## What a skill does today

One sentence in, one action out. The model picks a tool, our guardrails decide
whether it runs. That covers all six card actions, because each is a single
call with no planning involved.

## What an agent adds

Jobs where the sequence is not known in advance:

- **Handle the whole lost-wallet call** - block the card, review recent
  transactions, flag what looks wrong, order a replacement, then warn which
  automatic payments will now fail.
- **Find out why a card was declined** - could be a hold, a limit, a missing
  travel notice, expiry, or no funds. It has to look in several places and
  follow whichever thread is live.
- **Open a new Corestone account** - spans days and waits on approvals.

## The five pieces to add

1. **Read-only tools.** `get_card_status`, `get_recent_transactions`,
   `get_card_limits`, `get_holds`. Cheapest things in the project; they write
   nothing, so they carry no entitlement risk beyond `view`.

2. **The access flag is already there.** Every schema in `tools/` carries
   `"access": "read" | "write"`. The runner uses it: reads run freely, writes
   always stop for confirmation. Do not add a flag that lets a write skip it.

3. **Job state** (`agent/state.py`). What the job is, which steps have run,
   what came back, what is still missing. Passed to the model every turn,
   because the model remembers nothing by itself. Persist it if a job can span
   days.

4. **A runner** (`agent/runner.py`). Ask the model what to do next, call
   `core.guardrails.dispatch`, feed the result back, repeat. Must have a step
   cap, a time cap, and a loop detector. It calls `dispatch` like everyone
   else - it never reaches the card system directly.

5. **Workflow files** (`agent/workflows/*.md`). One per job, written like
   `SKILL.md`: plain English guidance on the usual order of steps and when to
   stop and ask. Not rigid scripts.

## What does not change

`core/guardrails.py`. The agent is a loop around the skill, not a replacement
for it. Entitlement, ownership, confirmation and audit run exactly as they do
now, once per action, however many actions a job involves.

## Two things that get harder

- **Partial failure.** If step 2 succeeds and step 5 fails, the card is locked
  and no replacement is coming. Decide per workflow: undo, retry, or hand to a
  human with a clear note of where it stopped. Do not leave it to the model.
- **Testing.** Six actions can be tested exhaustively. A chain cannot. Move to
  scenario tests that run the same situation repeatedly and check it behaves
  the same way each time.
