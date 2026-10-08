# Mock dataset

Three CSV files. Open them in Excel, edit, save — no code change needed.

| File | What it holds |
|---|---|
| `clients.csv` | client_id, name, account_last4 |
| `cards.csv` | card_id, which client owns it, last four, status, address on file |
| `entitlements.csv` | which advisor may perform which actions on which client |

## entitlements.csv

One row per advisor-client pair. The `actions` column is either `ALL` or a
list separated by `|`:

```
view | lock_card | unlock_card | replace_card | close_card |
report_lost_stolen | travel_notice
```

`view` is needed for a client to appear in a search at all. An advisor with
`view|lock_card` can lock a card but not close one — that split is real, and it
is what our guardrail checks that BNY's upstream check does not.

An advisor-client pair with no row here does not exist as far as that advisor
is concerned. They will be told no matching client was found, with no hint that
the client exists at all.

## Card statuses

`active`, `locked`, `closed`, `pending` (a replacement on its way).

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
