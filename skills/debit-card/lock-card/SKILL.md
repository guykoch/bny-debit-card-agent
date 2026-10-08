---
name: lock-card
tool: lock_card
lookups: find_client, list_cards
priority: 60
triggers: lock, block the card, freeze, suspend, stop the card
description: Temporarily lock a client's Corestone debit card. Reversible with unlock-card.
---

# Lock card

Temporarily blocks the card. Reversible.

**Required:** `client_id`, `card_id`
**Optional:** `reason` — free text, stored on the audit record

## Rules of its own

- If the advisor mentions the card being lost or stolen, ask whether they want
  **report-lost-stolen** instead. That locks the card *and* flags the account.
- If the card is already locked, say so. Do not call the tool again.
- If the card is closed, a lock is not possible; say a replacement is needed.

## Examples

> Advisor: Lock Jane Miller's card
> → find_client("Jane Miller") → one match → list_cards → one active card
> → "Lock the Corestone debit card ending 4417 for Jane Miller (...8821)?"
> → advisor confirms → lock_card

> Advisor: Lock all my clients' cards
> → "I can only act on one card at a time. Which client would you like to
>    start with?"
