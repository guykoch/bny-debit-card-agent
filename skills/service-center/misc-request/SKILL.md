---
name: misc-request
description: Service Center ticket (Misc. AMA/Res. Checking Issues) for any other servicing request about a client's checking account that is not a stop, a check copy, an address change or a check deposit inquiry. Examples - a checkbook, deposit slips, a deposit not showing, re-sending a statement, paper or e-statements, a fee or fee refund, adding a signer, account settings.
kind: ticket
tool: misc_request
lookups: find_client, list_accounts, find_check
triggers: checkbook, check book, check order, deposit slip, deposit not showing, not showing, isn't showing, hasn't shown up, missing deposit, deposit hasn't, statement, paper statement, e-statement, overdraft fee, monthly fee, account fee, waive, fee refund, refund the fee, signer, authorized signer, overdraft protection, service team, service center, misc request, other request, ask the service, servicing request, send a request
priority: 97
---

# Misc request (Service Center ticket)

## Covers
Servicing requests about a client's AMA or Resource Checking account that have no form
of their own:
- checkbooks and deposit slips (e.g. "order a new checkbook starting at 2101")
- a deposit that isn't showing or is on hold
- statement requests: re-send a statement, switch to paper or e-statements
- fees: why a fee was charged, asking for a refund or waiver
- signers, overdraft protection, recurring transfers and other account settings

Every Misc request is for one of the advisor's clients. The form's IBD / Office / IP # are
optional details (what they are used for is an open question for Ben).

## Doesn't cover
- anything not about the account ("order a new couch"): out of scope
- card actions (lock, unlock, replace, lost or stolen, travel notice): own buttons
- stopping a check, a check copy, an address or phone change, a check mailed to Pershing to
  be deposited (rollover or other): own tickets
- questions the chat can't answer: balances, transactions, what is on a statement

## What the ticket contains
Account (or IBD / Office / IP #), Subject and Additional
Information (both required, drafted from the advisor's words, editable), Name and
Call Back # (from the advisor's profile), optional attachments.
