---
name: check-copy
description: Service Center ticket: request a copy of a paid check.
kind: ticket
tool: check_copy
lookups: find_client, list_accounts, find_check
triggers: copy of a check, copy of the check, copy of check, check copy, image of a check, image of the check, check image, proof of payment, front and back of the check
priority: 94
---

# Check Copy (Service Center ticket)

Fills the Check Copy form (tickets/check_copy.json; placeholder fields until the
form's screenshot arrives) and sends it after the review card. Only paid checks
can be copied.
