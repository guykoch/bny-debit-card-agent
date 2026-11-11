# Service Center skills

Tickets that fill a NetX360 Service Center form (tickets/*.json) instead of changing
anything: stop-payment (shown as "Stop a check"), check-copy, address-update, rollover-inquiry, misc-request. Plus check-status,
a read-only lookup that can open a ticket with the check filled in.

These skills are driven by code (the chat asks for missing fields with cards); the
AI only picks the skill. The shared rules in ../debit-card/_shared.md still apply.
