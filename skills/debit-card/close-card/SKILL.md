---
name: close-card
tool: close_card
lookups: find_client, list_cards
priority: 65
triggers: close, close permanently, cancel the card, terminate, shut the card
description: Permanently close a card. Irreversible.
---

# Close card

Closes the card permanently. **This cannot be undone.**

**Required:** `client_id`, `card_id`, `reason`

## Rules of its own

Stricter confirmation than the others. Restate it as:

> This permanently closes the card ending 4417 for Jane Miller. It cannot be
> reopened — a new card would have to be issued. Confirm?

If the advisor's wording is ambiguous between closing and locking ("cancel her
card", "stop the card"), **ask which they mean before doing anything.** Locking
is reversible; this is not.

## Example

> Advisor: Close David's card for good
> → resolve client and card → ask for the reason
> → restate the permanence → confirm → close_card
