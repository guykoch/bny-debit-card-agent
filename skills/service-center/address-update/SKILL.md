---
name: address-update
description: Service Center ticket: change the client's address or phone on the account.
kind: ticket
tool: address_update
lookups: find_client, list_accounts, find_check
triggers: address to, 's address, change address, change the address, change her address, change his address, update address, update the address, update her address, update his address, new address, moved, mailing address, change phone, new phone, phone number, home address
priority: 58
---

# Address Update (Service Center ticket)

Fills the Address Update form (New Address, 4 lines from the address search; New
Phone #; either one is required) and sends it as a ticket. The address on file does
not change until the Service Center processes it.
