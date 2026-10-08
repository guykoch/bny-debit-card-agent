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

- Ask whether the card was lost or stolen if the advisor has not said.
  **Do not assume** from the wording.
- Ask whether there are transactions the client does not recognise. If yes, set
  `flag_transactions` to true. **Do not judge** which transactions look
  suspicious — that is not your call.
- After this succeeds, offer **replace-card** as the natural next step.

## Example

> Advisor: Jane lost her wallet
> → resolve client and card
> → "Lost, or stolen?" → "Any transactions she does not recognise?"
> → restate → confirm → report_lost_stolen
> → "Would you like me to order a replacement?"
