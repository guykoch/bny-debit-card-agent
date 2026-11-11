---
name: misc-request
description: Service Center ticket (Misc. AMA/Res. Checking Issues) for any other servicing request about a client's checking account, or the advisor's office, that is not a stop, a check copy, an address change or a rollover inquiry. Examples - a checkbook, deposit slips, a deposit not showing, re-sending a statement, paper or e-statements, a fee or fee refund, adding a signer, account settings, supplies for the office.
kind: ticket
tool: misc_request
lookups: find_client, list_accounts, find_check
triggers: checkbook, check book, check order, deposit slip, deposit not showing, deposit hasn't, statement, paper statement, e-statement, overdraft fee, monthly fee, account fee, waive, fee refund, refund the fee, signer, authorized signer, overdraft protection, account-opening kit, service team, service center, misc request, other request, ask the service, servicing request, send a request
priority: 97
---

# Misc request (Service Center ticket)

## Covers
Servicing requests about a client's AMA or Resource Checking account, or about the
advisor's office, that have no form of their own:
- checkbooks and deposit slips (e.g. "order a new checkbook starting at 2101")
- a deposit that isn't showing or is on hold
- statement requests: re-send a statement, switch to paper or e-statements
- fees: why a fee was charged, asking for a refund or waiver
- signers, overdraft protection, recurring transfers and other account settings
- office requests to the service team (supplies, a question) with an IBD / Office / IP #
  and no client

## Doesn't cover
- anything not about the account ("order a new couch"): out of scope
- card actions (lock, unlock, replace, lost or stolen, travel notice): own buttons
- stopping a check, a check copy, an address or phone change, a rollover check: own tickets
- questions the chat can't answer: balances, transactions, what is on a statement

## What the ticket contains
Account (or IBD / Office / IP # for an office request), Subject and Additional
Information (both required, drafted from the advisor's words, editable), Name and
Call Back # (from the advisor's profile), optional attachments.
