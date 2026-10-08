---
name: unlock-card
tool: unlock_card
lookups: find_client, list_cards
priority: 62
triggers: unlock, unblock, reactivate, turn the card back on, lift the lock
description: Remove a temporary lock from a client's Corestone debit card.
---

# Unlock card

Removes a temporary lock.

**Required:** `client_id`, `card_id`

## Rules of its own

- If the card was closed rather than locked, say it cannot be unlocked and that
  a replacement would be needed.
- If the card is already active, say so rather than calling the tool.

## Example

> Advisor: Jane found her wallet, unlock the card
> → resolve client and card → confirm → unlock_card
