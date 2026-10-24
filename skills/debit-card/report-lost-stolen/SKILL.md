---
name: report-lost-stolen
tool: report_lost_stolen
lookups: find_client, list_cards
priority: 90
triggers: lost, stolen, wallet, theft, stole, missing card, pickpocket
description: Block a card and flag the account after it is lost or stolen.
---

# Report lost or stolen

Blocks the card and flags the account for review. Two things happen at once.

**Required:** `client_id`, `card_id`, `incident_type` (`lost` or `stolen`)
**Optional:** `last_known_use`, `flag_transactions`

## Rules of its own

- Lost or stolen, and unrecognised transactions, are asked by the system with
  buttons. Fill `incident_type` only if the advisor clearly said it; leave
  `flag_transactions` out unless they said whether there are transactions the
  client does not recognise. **Do not judge** which transactions look
  suspicious - that is not your call.
- After this succeeds, the system offers **replace-card** with Yes / No buttons.

## Example

> Advisor: Jane lost her wallet
> → resolve client and card
> → buttons: Lost / Stolen → buttons: any unrecognised transactions? Yes / No
> → restate → confirm → report_lost_stolen
> → "Would you like me to order a replacement?"
