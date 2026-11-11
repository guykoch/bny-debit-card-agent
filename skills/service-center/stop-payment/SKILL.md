---
name: stop-payment
description: Service Center ticket: stop payment on one or more checks (e.g. lost in the mail).
kind: ticket
tool: stop_payment
lookups: find_client, list_accounts, find_check
triggers: stop payment, put a stop, a stop on, stop a payment, stop the payment, stop a check, stop the check, stop check, cancel a check, cancel the check, cancel check, void a check, void the check, void check, check was lost, check got lost, check lost, lost check, check in the mail
priority: 95
---

# Stop Payment (Service Center ticket)

Fills the NetX360 Service Center form *AMA/Resource Checking · Stop Payment ·
AMA/Resource Checking Account* (tickets/stop_payment.json) from the advisor's
words, asks only for what is missing, and sends it as a ticket after the review
card. Sending the ticket changes nothing else.

Filled by code: client, account, each check (Check #, Amount, Date Written), the
advisor's own words as Additional Information, the saved Call Back #. A check
already paid can't be stopped (the review is not shown). The form's red note: the
check can still clear within 24 hours.
