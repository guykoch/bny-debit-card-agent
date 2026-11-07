# Plan: Service Center tickets, Admin menu, and removing Close (final)

Status: **built** (November 7, 2026) as F-55 to F-58, see FIXES.md. Checks:
`python -m tests.test_tickets`. Based on the NetX360 Service Center screenshots
(enhancements_sheet.pdf). Open with Ben: D-05 (replacement to a new address =
Address Update ticket first).

## 1. Two kinds of features

| | Do it now (built) | Send a ticket (new) |
|---|---|---|
| Features | Lock, Unlock, Replace, Report lost or stolen, Travel notice | Stop Payment, Check Copy, Address Update, Misc request |
| What Confirm / Send does | Changes the card in the database | Saves a mock ticket for BNY's Service Center. Nothing else changes. |
| Result | "Card ending 4417 is locked." | "Stop Payment request SR-10234 sent. It will be processed by the Service Center." |

Address changes become a ticket: today's direct profile change is removed, and the
client's address on file stays until a ticket is processed.

## 2. Remove "Close the card permanently"

Replacing a card already closes the old card and issues a new one, and an account
can't be left without an active debit card.

- Removed: close skill and form, Close in the Actions menu, the red close card and
  Reason box, the "Lock for now / Close permanently" question, the close volume limit.
- If an advisor still asks ("close Jane's card"), code answers: "A debit card can't be
  closed on its own, because the account must keep an active card. You can replace it
  (the old card is closed and a new one is sent) or lock it for now." Buttons: Replace
  the card / Lock the card / Cancel.
- Card status "closed" stays (a replaced card shows as closed; the "order a
  replacement?" offer for closed cards keeps working).
- Knock-on: demo script step 9 uses "Replace Margaret Osei-Bonsu's card" for the
  no-permission refusal; guardrails slide notes drop "closing needs a real reason";
  tracker marks F-35, F-36, T-08a, T-15a, T-35a/b, T-36a/b as Retired and switches the
  volume test to replacements.

## 3. Chat screen

### 3.1 Actions button: two sections
```
DO IT NOW                      SEND A TICKET
Lock the card                  Stop a payment
Unlock the card                Request a check copy
Replace the card               Change an address
Report it lost or stolen       Other request (Misc)
Add a travel notice
                     [Cancel]
```
Note under the ticket heading: "Sends a request to the Service Center. Nothing changes
until it is processed." On a phone, "Send a ticket" collapses under one button.

### 3.2 "Admin" menu (replaces the advisor dropdown)
- Advisor ID: the advisor list; switching starts a new chat.
- Active Tickets: compact rows, newest first (SR #, ticket, client, date sent, status).
  Tapping a row shows the full ticket (every field as sent, attachment names). Only the
  selected advisor's tickets, checked on the server.

### 3.3 Fewest clicks, uncrowded cards
1. Code fills every field it can from the message first.
2. Missing required fields are asked one card per topic (at most 3 inputs per card),
   in a fixed order, skipping anything already known:
   - Account: buttons, and no card at all when the client has one account.
   - Check details: Check #, Amount, Date written on one card (Add another check).
   - New address: address search, apartment, phone on one card.
   - Subject + details (Misc): one card, both pre-drafted by the AI.
   - Call Back #: asked once per advisor, then remembered.
3. Optional fields (Date written, Subject, Additional Information when the reason is
   known, Attachments) are never asked one by one: they sit on the review card,
   pre-filled where possible, editable there.
4. Review card, kept short:
   - Always shown: client · account, the 2-3 key fields (e.g. "Check 1043 · $250.00 ·
     Lost in the mail"), call-back number, and the form's red note where it has one.
   - "Show all fields" expands the rest (Subject, Category / Request Type, Contact Name).
   - "+ Attach file" link (optional), Send, Cancel.

Clicks after typing the request (call-back already saved):

| Advisor typed | Cards | Clicks |
|---|---|---|
| "Stop check 1043 Jane Miller wrote for $250, lost in the mail" | Review | 1 |
| "Stop a payment for Jane Miller" | Check details → Review | 2-3 |
| "Change Jane Miller's address to 1 Bryant Park, apt 12C" | Review | 1 |
| Actions → Stop a payment | Client → Check details → Review | 3-4 |

### 3.4 Attachments (optional, every ticket)
PDF, JPG or PNG, 10 MB each, up to 5 per ticket. Stored in Convex file storage, linked
to the ticket, never sent to the AI. The form's note is shown: "Attached files will not
be imaged and will not appear in Online Documents."

## 4. The tickets (fields from the screenshots)

Every ticket: Account # * (lookup, last 4 only), Subject/Attention (drafted, editable),
Contact Name (sign-in), Call Back # * (US xxx-xxx-xxxx + Ext, or Non-US), Attachments
(optional). Category / Request / Request Type fixed per ticket.

| Ticket | Fields | Cards for missing fields |
|---|---|---|
| Stop Payment (AMA/Resource Checking · Stop Payment · AMA/Resource Checking Account) | Check rows (Check # *, Amount *, Date Written), Additional Information | Account → Check details → Review. Check looked up first: "already paid on 11/02/2026" stops it. Review shows the 24-hour note. |
| Check Copy (AMA Account / Resource Checking Account) | Needs the form's screenshot; likely check # / amount / date, reason | Account → Check details → Review |
| Address Update (AMA/Resource Checking · Address Update) | New Address (4 lines), New Phone # (address or phone required), Additional Information | Account → New address → Review. Address on file stays until processed. |
| Misc (AMA/Res. Checking Issues) | Select * (Account # or IBD / Office / IP #), Subject *, Additional Information * | Account → Subject + details → Review. Also the catch-all for servicing requests that fit nothing else. |

NetX360's red rule ("DO NOT key out a checking account number or debit card number")
is enforced by code: long digit runs are removed from free text before sending.

Check status, then act: "Was check 123 drawn on Jane's account?" → read-only check card
(check #, account ...last 4, amount, date written, status, posted date). Paid: "Paid on
11/02/2026." Not paid: "Stop this payment" opens the Stop Payment review card with the
check filled in. The advisor clicks each step (skill, not autonomous agent).

## 5. Database (Convex)

| Table | Contents | Written by |
|---|---|---|
| tickets (new) | SR #, ticket type, status, advisor, client, account (...last 4), fields, attachments, conversation, when (US) | Only Send on a ticket |
| File storage (new) | Attached files | Only ticket attachments |
| advisor_settings (new) | Saved call-back number | Only the call-back card |
| accounts, checks (new) | Demo accounts and checks (from CSV) | Nothing (read-only) |
| cards, addresses, travel_notices | Unchanged | Only Do it now actions |
| audit_actions / audit_chat | Unchanged | Plus "Ticket sent ..." rows with SR # |

Reset demo data clears tickets, files, saved call-back numbers and the audit logs.

## 6. Connecting to BNY later
Two connection points, same pattern as the card system:
- Service Center: send a ticket with attachments; list and read tickets (powers Active
  Tickets). Template field IDs map one-to-one to their API.
- Checks: look up a check.
Templates, cards, guardrails and audit stay the same.

Safety: per-ticket permissions, volume limits, one unique key per Send (no double
tickets), the review card before anything is sent, both audit logs with the SR number.

## 7. Questions / decisions for Ben
1. Is there an API to send tickets and read their status?
2. Is there a check lookup API?
3. Can you share the Check Copy form?
4. Call Back #: the advisor's saved number, or asked on every ticket?
5. Replacement to a new address: send the Address Update ticket and order the
   replacement later, or send the replacement as a ticket too?

## 8. Build order
1. Remove Close (plus tests, tracker, demo script, slide notes).
2. Groundwork: ticket engine and templates, new tables, file storage, card parts
   (account buttons, check details, call-back, review card, attachments).
3. Actions menu with two sections; Admin menu with Active Tickets.
4. Address Update ticket (replaces the direct change).
5. Stop Payment, then check status and the combination flow.
6. Misc.
7. Check Copy, once its screenshot arrives.

Step 2 changes Convex: run `npx convex deploy` after pushing.
