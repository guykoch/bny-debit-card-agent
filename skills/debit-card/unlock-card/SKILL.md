---
name: unlock-card
description: Remove a temporary lock from a client's Corestone debit card.
tool: unlock_card
lookups: find_client, list_cards
triggers: unlock, unblock, reactivate, turn the card back on, lift the lock, turn it back on, turn her card back on, turn his card back on, found her card, found his card, found the card
priority: 62
---

# Unlock card

Removes a temporary lock.

**Required:** `client_id`, `card_id`

## Rules of its own

- Only locked cards can be unlocked. If the client has no locked card, or the
  card is closed or pending, the system says so as soon as the card is known.

## Example

> Advisor: Jane found her wallet, unlock the card
> → resolve client and card → confirm → unlock_card
