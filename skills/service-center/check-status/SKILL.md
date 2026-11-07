---
name: check-status
tool: find_check
kind: lookup
lookups: find_client, list_accounts, find_check
priority: 93
triggers: cleared, cashed, clear?, gone through, go through, was check, did check, has check, check cleared, check cashed, check posted, check status, status of check, check been paid, check been cashed, been drawn, check drawn, drawn on
description: Look up one check: amount, date written, and whether it was paid (read-only).
---

# Check status (read-only)

"Was check 123 drawn on Jane's account?" shows the check: number, account (last 4),
amount, date written, status. Not paid: a Stop this payment button opens the Stop
Payment ticket with the check filled in. Paid: a Request a copy button.
