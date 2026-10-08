---
name: replace-card
tool: replace_card
lookups: find_client, list_cards
priority: 70
triggers: replace, new card, reissue, damaged, broken, cracked, worn out
description: Cancel the current card and issue a replacement.
---

# Replace card

Cancels the current card and issues a new one.

**Required:** `client_id`, `card_id`, `reason`, `delivery_address`
**`reason` must be one of:** `damaged`, `lost`, `stolen`, `expiring`, `other`

## Rules of its own

- Ask for the reason if the advisor has not given one. **Do not infer it.**
- Default the delivery address to the one on file, but **show it and ask the
  advisor to confirm or change it.** Never send to an address the advisor
  mentioned in passing without confirming it.
- If the reason is `lost` or `stolen`, ask whether they also want the account
  flagged — that is **report-lost-stolen**, and it should usually run first.

## Example

> Advisor: Jane's card is cracked, send her a new one
> → resolve client and card → reason = damaged
> → "Deliver to 14 Hudson St, New York, NY 10013 — the address on file?"
> → confirm → replace_card
