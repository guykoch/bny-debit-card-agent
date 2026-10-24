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

## Who fills what

Your job is the client and the card: call `find_client` and `list_cards`,
then call `travel_notice`. The destinations and dates are read by the system
from the advisor's own words. When they are missing, vague ("next month",
"a couple of weeks") or not on BNY's list, the system shows the travel card
(destinations with suggestions plus a calendar). Never propose, assume or
ask for dates or places in text.

## Rules (checked by code)

- Destinations are countries or US states from BNY's list, up to 10 per
  notice. A city ("Paris") gets buttons for the country or US state; a name
  that could be two places ("Georgia") gets buttons.
- A notice covers at most 14 days, both days counted. The system mentions
  this only when the dates are longer, and then shows the calendar again.
- The confirmation card shows the dates in editable date fields.

## Example

> Advisor: Sarah Chen is going to Japan November 20 to November 30
> → find_client → list_cards → travel_notice
> → confirmation card: Japan, Nov 20 to Nov 30 (dates editable) → Confirm
