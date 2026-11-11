# Plan: feedback from Ben (November 11, 2026)

Status: **built** (November 11, 2026) as F-61 to F-64, see FIXES.md. Decisions: lockbox
numbers mocked; Call Back # from the advisor directory (advisors.csv); duplicates warned, not
blocked. Source: the call with Ben on 11/11 and Guy's notes on each
item. Demo script for this round: `BNY_Demo_Script.xlsx` (steps marked "Next build" need
this plan).

| # | Feature | Size | Convex deploy? |
|---|---|---|---|
| 1 | "Stop a payment" becomes "Stop a check" | Small | No |
| 2 | Call Back # prefilled per advisor, editable on the review card | Small | No |
| 3 | Check look-up answers "Paid" / "Not paid yet", with a Stop this check button | Small | No |
| 4 | Context across messages: "stop that payment" uses the check just discussed, after a one-tap confirm | Medium | No |
| 5 | Duplicate request warning: keep as is; block or warn is Brian's call | None | No |
| 6 | New ticket: Retail Check Deposit Status Inquiry (rollover checks) | Large | Yes |
| 7 | Misc boundary written down once (skill file + routing rules agree) | Small | No |

Order of work: 1, 2, 3, 7 (quick, visible), then 4, then 6.

---

## 1. Rename to "Stop a check"

- **What the advisor sees:** the Actions menu button, the buttons on other cards ("Stop this
  check") and the review card title say **Stop a check**. The form line under the title keeps
  BNY's form name: "AMA/Resource Checking · Stop Payment".
- **What it still understands:** "stop payment", "stop the payment", "cancel the check",
  "void check 1043", "put a stop on it". Only the labels change, not the routing words.
- **Where:** `ACTION_LABELS` in llm_runtime, button labels, `tickets/stop_payment.json`
  (`title` / `menu_label`), the skill's description. The ticket's `request` stays "Stop
  Payment" (BNY's field value).
- **Tests:** the labels; "stop payment on check 1044" still routes to Stop a check.

## 2. Call Back # prefilled per advisor

- **Mock data:** a new `integrations/mock/data/advisors.csv`: advisor_id, name, callback
  (kind, number, ext). For example ADV-1234 Alex Morgan, 212-555-0142 ext 204; ADV-5678 Dana
  Brooks, 312-555-0177; ADV-9012 Sam Patel, +44 20 7946 0958 (Non-US). In production this comes
  from the NetX360 sign-in profile.
- **Flow:** the separate Call Back # question goes away. Every review card shows **Call Back #:
  212-555-0142 ext 204** with a **Change** link that opens the US / Non-US fields right there.
  A changed number is saved for that advisor (as today) and used next time. The question
  card is only shown when an advisor has no number at all.
- **The form's Name field:** filled with the advisor's name from the same file (the "Name:
  DEMO USER" line on BNY's form).
- **Where:** `MockAdvisorDirectory` (or `advisor_settings` falling back to advisors.csv),
  `_ticket_step` (skip the callback card), web/index.html `renderTicketReview` (Change link).
- **Tests:** first ticket goes straight to the review card with the mock number; Change ->
  saved; an advisor with no number still gets the question.

## 3. Check look-up: a yes / no answer

- **Card:** one line on top, big: **Check 1043: Not paid yet** (or **Check 1041: Paid on
  10/18/2026**). Below it one short line: "$250.00 to City Plumbing Co, written 10/28/2026".
  No table of fields.
- **Buttons:** Not paid yet -> **Stop this check** / Done. Paid -> **Request a copy** / Done.
  A request already pending -> the line says so ("Stop pending, SR-10234") and the button is
  left out (as now).
- **Where:** `_check_status`, `cards.check_status_card`, web/index.html `renderCheckStatus`.

## 4. Context across messages (linked requests)

What happens today: after "Did Jane Miller's check 1043 clear?", typing "ok, stop that payment
then" is not understood, and "stop it" asks "a check or the card?". Two causes: (a) a new
message starts clean, so the routing does not look at the check just discussed, and (b)
only a few phrases ("it", "that check") count as a reference.

- **Conversation memory (code, per conversation):** the last client, account, check and ticket
  mentioned or shown. It is already saved between messages on Vercel; it gets used more widely.
- **References recognised by code:** it, that, that one, that check, that payment, the check,
  the same check, this one, the one we just looked at, same client, her / his account.
  Combined with a verb (stop, cancel, void, copy, a copy of).
- **Routing:** the AI gets one line of context with each message, e.g. "Just discussed: Jane
  Miller, check 1043 (not paid yet)". So "stop that payment" routes to Stop a check, and
  "stop it" right after a check no longer asks "check or card?".
- **Always confirmed:** before using the remembered check, a one-tap card: **"Stop check 1043
  for Jane Miller ($250.00)?"** Yes / Another check / Cancel. Nothing is filled silently, and
  Send is still needed on the review card.
- **Follow-up offers keep the client and card:** after a stolen-card report, "Yes, order a
  replacement" today asks "Which client?" again. The offer's button will carry the client
  and card, so it goes straight to the replacement's reason / address.
- **Also covers:** "and a copy of check 1041 too" (same client kept, asked to confirm), "her
  other account" (the second account), "send that again" (duplicate warning applies).
- **Where:** llm_runtime `_route` (context line), `_ticket_fill` (reference words),
  a new `_confirm_reference` card; the existing `last_client` / `last_check`.
- **Tests:** stolen report -> "Yes, order a replacement" -> no client question; look-up ->
  "ok, stop that payment then" -> confirm card -> review; "stop it"
  after a check -> the check, not "check or card?"; "stop it" after a card action -> card;
  a new client name -> no carry-over.

## 5. Duplicate requests

Built (F-60): warning with Send another / Cancel. Question for Brian: should a second stop
on the same check be blocked instead of warned? One setting either way.

## 6. New ticket: Retail Check Deposit Status Inquiry (rollover checks)

**What it is:** a rollover check (for example from a 401(k) at ADP, Voya or Fidelity) is
mailed to one of Pershing's desks. If the check itself does not carry enough information to
credit the right account, the money desk can't process it. The advisor's ticket gives the full
picture (account, amount, check #, sender, how and when it was sent, where to), so the desk
can match the physical check and credit it.

**The form (from Ben's screenshot):** Category Asset Movement · Request Checks · Request Type
Retail Check Deposit Status Inq.

| Field | Required | Notes |
|---|---|---|
| Account # | yes | the client's account |
| Amount | yes | dollars |
| Check # | yes | |
| Method of Delivery | yes | Regular mail / Overnight; Overnight adds Tracking # |
| Date Sent | yes | MM/DD/YYYY, not in the future |
| Sent From | no | e.g. ADP, Voya, Fidelity |
| Destination | yes | Jersey City / Pittsburgh / Lake Mary |
| Lockbox | no | list per destination (mock: e.g. Rollover Lockbox-382084 for Pittsburgh) |
| Additional Information | no | "anything that helps identify the check" |
| Attachment | no | copy of the check, mailing label, shipping confirmation, split breakdown |
| Name, Call Back # | (contact) | from item 2 |

**How the chat decides (Guy's rule):**
1. **Look first.** Mock data of checks received at the desks (`incoming_checks.csv`:
   desk, date received, amount, check #, sender, payee line, account written on it,
   status credited / unidentified).
2. **Received and credited** (all information was on the check): no ticket needed. Answer:
   "Check 4410 from Voya for $85,000.00 was received in Jersey City on 11/09/2026 and credited
   to AMA ...8821."
3. **Received but not credited** (the check is missing the account or other details): "A
   check matching this was received in Pittsburgh on 11/06/2026 but couldn't be credited: no
   account number on it. Send a deposit status inquiry so the desk can credit it to AMA
   ...1022?" -> the form card.
4. **Not received yet:** "No check matching this has been received yet. Send the inquiry now
   so the desk can match it when it arrives?" -> the form card.

**Chat or form (Ben's question):** many required fields, so the chat does not ask them one by
one. It reads what the advisor wrote, then shows **one form card** laid out like BNY's form,
with everything it could fill already in and the missing required fields highlighted. Two
paths are then easy to compare in testing: typing one sentence vs. filling the card.

- **Where:** `tickets/rollover_inquiry.json`, `tools/rollover_inquiry.json`,
  `skills/service-center/rollover-inquiry/SKILL.md`, `incoming_checks.csv` +
  `MockIncomingChecks`, `core/tickets.py` (precheck: amount, date, tracking # when overnight),
  llm_runtime (look first, then the form card), web/index.html (the form card: dropdowns for
  delivery, destination, lockbox; date field; tracking # shown only for Overnight).
- **Permissions:** a new action `rollover_inquiry` in entitlements.csv (ALL rows get it).
- **Convex:** the ticket uses the existing `tickets` table; deploy needed only for the new
  routing lookups if they move to Convex (mock data stays in CSV). Plan for one deploy.
- **Tests:** credited -> no ticket; unidentified -> form card prefilled from the received
  check; not received -> form card from the sentence; Overnight without tracking # refused;
  future Date Sent refused; ticket saved with all fields.
- **Open with Ben:** what is the Lockbox list per destination; is "Retail" the right request
  type for all rollovers; does the money desk's received-check data exist for us to look up.

## 7. Misc boundary

- The Misc skill file says plainly what is in and out (see the reorganised skill layout).
  **In:** checkbooks, deposit slips, a deposit not showing, statement requests (re-send,
  paper / e-statements), fees and fee refunds, signers, account settings, office requests
  to the service team (with IBD / Office / IP # and no client).
  **Out:** anything not about the account; card actions; stop / copy / address / rollover
  (own tickets); questions like balances or what is on a statement.
- The routing rules in llm_runtime stop listing "statements" as out of scope (statement
  *requests* are Misc, statement *questions* stay out).
- Office requests: Misc can be sent with only an IBD / Office / IP # and no client.
- All skill files reorganised the same way (description first, then settings, then Covers /
  Doesn't cover / What the ticket contains).
- **Tests:** checkbook, fee refund, statement re-send -> Misc; office kits -> Misc without a
  client; "order a new couch" -> out of scope.

---

## Open questions

| For | Question |
|---|---|
| Brian | Second request for the same check: warn (now) or block? |
| Ben | Rollover: lockbox list per destination; does received-check data exist to look up? |
| Ben | Does the NetX360 profile carry the advisor's phone (for item 2 in production)? |
