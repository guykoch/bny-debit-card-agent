---
name: update-address
tool: update_address
lookups: find_client
priority: 55
triggers: change address, update address, change her address, change his address, update her address, update his address, moved, add an address, add a delivery address, new delivery address
description: Change an address in the client's profile, or add a new delivery address for a replacement card.
---

# Update address

Two things an advisor may want, and the system asks which with buttons:

1. **Change an address in the client's profile** (e.g. the client moved).
2. **Add a new delivery address** to the profile, so a replacement card can be
   sent there.

**Required:** `client_id`. Everything else is filled by the system:
- `mode`: asked with buttons, unless the advisor clearly said it.
- `address_label`: when the profile has more than one address, the system asks
  which one with buttons. Never choose it yourself.
- `new_address`, `new_state`, `new_country`: **never fill these.** The system
  shows an address field with suggestions (US states and territories only) and
  the advisor picks one. An address typed in the chat is not accepted.

## Rules of its own

- Find the client, then call `update_address` with just the `client_id` (and
  `mode` if the advisor said it). The system takes it from there.
- The confirmation panel is red and needs the advisor to tick that the client
  asked for the change and was verified. Nothing changes until Confirm.
- This never changes a card. After a new delivery address is added, the system
  offers to order the replacement.

## Example

> Advisor: Jane Miller moved, update her address
> → find_client → update_address(client_id)
> → system buttons: Change an address in the profile / Add a delivery address
> → system buttons: which address (Home / Vacation home)
> → address field with suggestions → panel (red, verified tick) → confirm
