---
name: deposit-inquiry
description: Service Center ticket (Retail Check Deposit Status Inquiry) for a check mailed to Pershing to be deposited into the client's account - a retirement rollover (401(k) from ADP, Voya, Fidelity), a transfer from another bank, an insurance or estate payout, any incoming check. Also answers whether such a check has arrived. Not for checks the client wrote to someone else (those are stop-payment, check-copy, check-status).
kind: ticket
tool: deposit_inquiry
lookups: find_client, list_accounts
triggers: rollover, roll over, 401(k), 401k, deposit status, check deposit, retail check deposit, lockbox, money desk, incoming check, check mailed to pershing, check sent to pershing, mailed to pershing, sent to pershing, check has arrived, check come in, check arrived
priority: 98
---

# Check deposit inquiry (Service Center ticket)

## Covers
A check sent to Pershing for the client, to be deposited into the client's account: "has the
rollover check from Voya come in?", "Fidelity mailed Robert's 401(k) check to Pittsburgh last
week, check on it", "a $50,000 check from her old bank was sent overnight to Lake Mary".
Rollovers are the most common case; the form covers any incoming check.

## How it works
1. Code looks first at the checks received at the money desks.
2. Received and credited: the chat says so. No ticket is needed.
3. Received but not credited (the check doesn't carry enough to identify the account), or not
   received yet: one form card like BNY's, filled from the advisor's words (and from the
   received check), missing required fields highlighted. Then the review card and Send.

## Doesn't cover
- checks the client wrote to someone else (stop, copy, look-up): own skills
- an electronic deposit not showing (no check mailed to Pershing): misc-request
- anything not about the account

## What the ticket contains
Account, Amount, Check #, Method of Delivery (Regular mail / Overnight + Tracking #), Date
Sent, Sent From, Destination (Jersey City / Pittsburgh / Lake Mary), Lockbox (invented demo
values), Additional Information, attachments (copy of the check, mailing label, shipping
confirmation, split breakdown), Name and Call Back #.
