---
name: travel-notice
tool: travel_notice
lookups: find_client, list_cards
priority: 80
triggers: travel, trip, abroad, flying, going to, overseas, holiday, vacation
description: Record upcoming travel so the card is not blocked abroad.
---

# Travel notice

Records travel so the card is not blocked abroad. The most fields of the six,
and the vaguest inputs.

**Required:** `client_id`, `card_id`, `destination`, `start_date`, `end_date`

Track which required fields are still empty and ask only for those.

## Dates

- Convert relative phrases into actual dates and **show your working**.
  "next month for a couple of weeks" → propose the 1st to the 15th of next
  month, and let the advisor confirm or correct it.
- **Never submit a date you inferred without showing it first.** Either ask,
  or let the confirmation panel show it: the panel lists the dates and offers
  "Change dates", and nothing runs until the advisor confirms.
- If the end date is before the start date, or the range is longer than 90
  days, say so and ask.

## Destination

- If a place name is ambiguous, **ask**. Do not pick the more common reading.
  "Georgia" → the US state or the country? "Springfield" → which one?
- Multiple countries are allowed. List them back before confirming.

## Never

Never fill a required travel field with a default.

## Example

> Advisor: Sarah's off to Georgia next month for a couple of weeks
> → resolve client → resolve card
> → "Georgia the country, or the US state?"
> → propose the 1st to the 15th of next month
> → travel_notice → the panel shows the dates, with Change dates → confirm
