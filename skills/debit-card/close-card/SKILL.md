---
name: close-card
tool: close_card
lookups: find_client, list_cards
priority: 65
triggers: close, close permanently, cancel the card, terminate, shut the card
description: Permanently close a card. Irreversible.
---

# Close card

Closes the **debit card** permanently. **This cannot be undone.** The account
itself stays open - always say "close the card", never "close the account".

**Required:** `client_id`, `card_id`. The reason is typed by the advisor in the
required Reason box on the confirmation card; fill `reason` only with the
advisor's own words if they already gave a real reason ("switching banks"),
never with "permanently", "client request" or similar.

## Rules of its own

- The confirmation card is red and says it cannot be undone. That card is the
  restatement: never write "This permanently closes... Confirm?" in text.
- If the wording is ambiguous between closing and locking ("cancel her card",
  "stop the card"), the system asks Lock or Close with buttons. Locking is
  reversible; this is not.

## Example

> Advisor: Close David's card for good, he is switching banks
> → find_client → list_cards → close_card (reason "switching banks")
> → red confirmation card with the Reason box filled in → Confirm
