---
name: replace-card
tool: replace_card
lookups: find_client, list_cards
priority: 70
triggers: replace, new card, reissue, damaged, broken, cracked, worn out, never arrived, never received, not arrived, hasn't arrived
description: Cancel the current card and issue a replacement.
---

# Replace card

Cancels the current card and issues a new one. A closed card can be replaced
too - that is how the client gets a working card again.

**Required:** `client_id`, `card_id`, `reason`, `delivery_address`
**`reason` must be one of:** `damaged`, `lost`, `stolen`, `expiring`,
`not received`, `other`
**Optional:** `flag_transactions` (only when the reason is lost or stolen)

## Rules of its own

- **Reason and delivery address are asked by the system with buttons.** Fill
  `reason` only if the advisor already said it ("it's cracked" = damaged, "she
  never got it" = not received). Otherwise leave it out and call the tool.
- **Delivery address:** a replacement can only go to an address that is in the
  client's profile, in a US state or US territory. The system shows the
  client's addresses as buttons. Fill `delivery_address` only when the advisor
  typed a specific address; the system checks it against the profile. A new
  address must first be added to the client's profile in NetX360 - this chat
  does not change profile addresses.
- If the reason is `lost` or `stolen`, the system also asks whether there are
  transactions the client does not recognise. Never ask this for any other
  reason.

## Example

> Advisor: Jane's card is cracked, send her a new one
> → resolve client and card → reason = damaged → replace_card
> → system: "Send the new card to which address? Home: 14 Hudson St..." (buttons)
> → panel → confirm
