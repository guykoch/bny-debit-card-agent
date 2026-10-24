# Mock dataset

Four CSV files. Open them in Excel, edit, save — no code change needed.

| File | What it holds |
|---|---|
| `clients.csv` | client_id, name, account_last4, city, birth_year (city and birth year tell similar names apart in "Which client?") |
| `cards.csv` | card_id, which client owns it, last four, status, address on file |
| `addresses.csv` | every address in each client's profile: label, address, state, country. A replacement card may only go to one of these, and only in a US state or territory |
| `entitlements.csv` | which advisor may perform which actions on which client |

## entitlements.csv

One row per advisor-client pair. The `actions` column is either `ALL` or a
list separated by `|`:

```
view | lock_card | unlock_card | replace_card | close_card |
report_lost_stolen | travel_notice
```

`view` is needed for a client to appear in a search at all. With
`PERMISSION_MODEL = "all_or_nothing"` in config/settings.py, any row gives
every card action (Ben's description; decision D-01 still open). An advisor with
`view|lock_card` can lock a card but not close one — that split is real, and it
is what our guardrail checks that BNY's upstream check does not.

An advisor-client pair with no row here does not exist as far as that advisor
is concerned. They will be told no matching client was found, with no hint that
the client exists at all.

## Card statuses

`active`, `locked`, `closed`, `pending` (issued, not yet activated - e.g. a
replacement on its way). What a pending card allows is set by
`PENDING_CARD_ACTIONS` in config/settings.py (decision D-03).

## addresses.csv

Rows worth knowing for tests: Jane Miller has a second address (Miami Beach);
Priya Raghunathan has a Paris apartment (outside the US, never allowed);
Robert Castellano has a Honolulu home and a PO box; Thomas Whitfield has an
Austin office; Elena Vasquez has a San Juan, Puerto Rico apartment (a US
territory, allowed); Claire Beaumont's only address is in Montreal, so no
replacement can be sent to her until a US address is added.

## Rows the tests depend on

Edit freely, but these specific rows are what the test suite checks:

- `C-88210` Jane Miller with one active card `CARD-4417`
- `C-44090` and `C-44091`, two Sarah Chens that ADV-1234 can see
- `C-99001`, a third Sarah Chen that ADV-1234 cannot see
- ADV-1234 holding lock but not close on `C-44090`
- `CARD-3310` closed, `CARD-9902` locked

## In production

This folder disappears. `integrations/bny/services.py` reads from BNY's real
systems instead. Nothing in `core/` is aware of either.
