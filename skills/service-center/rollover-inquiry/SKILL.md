---
name: rollover-inquiry
description: Service Center ticket (Retail Check Deposit Status Inquiry) for a rollover check mailed to a Pershing desk - e.g. a 401(k) rollover from ADP, Voya or Fidelity. Also answers whether such a check has arrived. Not for checks the client wrote (those are stop-payment, check-copy, check-status).
kind: ticket
tool: rollover_inquiry
lookups: find_client, list_accounts
triggers: rollover, roll over check, 401(k), 401k, deposit status, retail check deposit, check deposit status, lockbox, money desk, incoming check
priority: 98
---

# Rollover check inquiry (Service Center ticket)

## Covers
A check sent to Pershing for the client (usually a retirement-plan rollover) that must be
credited to the client's account: "has the rollover check from Voya come in?", "the
Fidelity check for Robert went to Pittsburgh last week, check on it".

## How it works
1. Code looks first at the checks received at the money desks.
2. Received and credited: the chat says so. No ticket is needed.
3. Received but not credited (the check doesn't carry enough to identify the account), or not
   received yet: one form card like BNY's, filled from the advisor's words (and from the
   received check), missing required fields highlighted. Then the review card and Send.

## Doesn't cover
- checks the client wrote (stop, copy, look-up): own skills
- anything not about the account

## What the ticket contains
Account, Amount, Check #, Method of Delivery (Regular mail / Overnight + Tracking #), Date
Sent, Sent From, Destination (Jersey City / Pittsburgh / Lake Mary), Lockbox, Additional
Information, attachments (copy of the check, mailing label, shipping confirmation, split
breakdown), Name and Call Back #.
