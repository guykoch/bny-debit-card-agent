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
- A notice covers at most **14 days** (both days counted). If the end date is
  before the start date, or the trip is longer, say so and ask. The panel's
  "Change dates" opens a calendar.

## Destination

- Destinations are **countries or US states** from BNY's list, **up to 10** per
  notice. Write them as named on the list ("France", "Texas", "Georgia (country)").
- A city is not a destination: if the advisor names one ("Paris"), ask which
  country or US state it is in. **Never guess.**
- If a name could be two places ("Georgia"), pass it as the advisor wrote it;
  the system asks with buttons and shows the choice on the panel.

## Never

Never fill a required travel field with a default.

## Example

> Advisor: Sarah's off to Georgia next month for a couple of weeks
> → resolve client → resolve card
> → system buttons: "Georgia (country)" / "Georgia (US state)"
> → propose the 1st to the 15th of next month
> → travel_notice → the panel shows the dates, with Change dates → confirm
