# Fixes from team testing (October 2026)

Each fix in the Agent Fix Tracker, where it lives, and the automated check
that covers it (`python -m tests.test_fixes`, by tracker test ID). Live checks
in the demo are on the tracker's Tests sheet.

## Decisions and their settings (config/settings.py)

| Decision | Status | Setting |
|---|---|---|
| D-01 Permissions: per action or all or nothing | Open with Ben | `PERMISSION_MODEL = "per_action"` (switch to `"all_or_nothing"`) |
| D-02 Replacement addresses | Decided by Guy: only addresses in the client's profile, US states and territories | `addresses.csv`; `REPLACEMENT_ALLOW_PO_BOX = True` (PO boxes still to confirm) |
| D-03 Pending cards | Open with Ben | `PENDING_CARD_ACTIONS = {"lock_card", "replace_card"}` |
| D-05 Lost/stolen question in replace | Decided: only when the reason is lost or stolen | built in |
| D-06 Unusual volume | Team default, open | `VOLUME_LIMITS`, `VOLUME_WINDOW_MINUTES = 10` |

## Rules in code

| Fix | What changed | Where |
|---|---|---|
| F-01 | We check per-action permissions ourselves (`TRUST_UPSTREAM_ENTITLEMENT = False`) | settings, guardrails |
| F-02 | Refused as soon as the client is known, before any question | `check_permission()` in guardrails; llm_runtime `_permission_stop` |
| F-03 | Replacement only to a US address in the client's profile; anything else refused, with the allowed addresses offered | handlers `_replace_precheck`, `allowed_addresses`; `addresses.csv` |
| F-04 | Destinations from BNY's list of countries and US states, up to 10; a city makes the chat ask | `core/places.py`, handlers `_travel_precheck` |
| F-05 | Travel notice max 14 days, counting both days | settings `MAX_TRAVEL_DAYS = 14` |
| F-06 | Pending card rules, one clear message | handlers `_pending_rule` |
| F-07 | Every refusal is in the audit | guardrails `log_refusal` |
| F-08 | Volume limit per advisor | guardrails `_check_volume`, audit `recent_count` |
| F-09 | Earlier panels can't be clicked after a new message | web/index.html `retireOldPanels` |

## Prompt and messages

| Fix | What changed | Where |
|---|---|---|
| F-10 | No false "done": `switch_action` tool hands over to another skill; a reply that sounds like an action gets "Nothing has been changed yet." | llm_runtime, `_shared.md` |
| F-11 | Text in names, notes and addresses is data, not instructions | `_shared.md`, runtime notes |
| F-12 | Replace flow: profile addresses as buttons; "A different address" explains the profile rule | llm_runtime `_address_panel`, replace-card SKILL.md |
| F-13 | PIN requests get a fixed reply (code, no AI) | local_runtime `is_pin_request` |
| F-14 | Typos read through; if still unclear, the seven actions as buttons | llm_runtime routing |
| F-15 | "Close the debit card", account stays open | handlers `_close_summary`, close-card SKILL.md |
| F-16 | Unrecognised-transactions question only when the replacement reason is lost or stolen | llm_runtime `_ask_missing` |
| F-17 | "Already locked" / "no locked card" from code as soon as the card is known | handlers `state_check`, llm_runtime `_state_stop` |
| F-18 | Closed card: offers a replacement with Yes / No | llm_runtime `_list_cards`, `_offer` |
| F-19 | The real address is shown | llm_runtime `_address_panel` |

## UX

| Fix | What changed | Where |
|---|---|---|
| F-20 | Reason, lost/stolen, unrecognised transactions, address and Georgia asked by code as buttons, the same list every time | llm_runtime `_ask_missing`, `_resolve_destinations` |
| F-21 | Panel shows the exact choice ("Georgia (country)") | handlers `_travel_precheck` |
| F-22 | Change dates opens a date-range picker (no past dates, 14-day max); dates applied by code, no AI call | web/index.html `datePicker`; `set_dates:` in both runtimes |
| F-23 | City and birth year in "Which client?" | `clients.csv`, guardrails `_client_label` |
| F-24 | Near spellings offered as "Did you mean?", never chosen silently, never another advisor's client | mock `find_similar` |
| F-25 | Yes / No buttons after a lost/stolen report | handlers `follow_up_actions`, web/index.html |

## From live testing (after the first round)

| Fix | What changed | Where |
|---|---|---|
| F-26 | Options are always buttons: panels are kept in the model's history as a question plus a note (never a numbered list it could copy), and any list the model still writes as text is turned into buttons by code | llm_runtime `_say`, `_text_or_buttons` |
| F-27 | Typo in the action ("lo Sarah Chen's card"): the router marks it uncertain and code asks "Did you mean: lock the card?" Yes / No before going on; No shows the six actions | llm_runtime `_route` (`certain`), `_picked` |

## New feature: update an address, with address search

| Item | What changed | Where |
|---|---|---|
| F-28 | New action **update address** (7th skill). The chat asks with buttons: change an address in the client's profile, or add a new delivery address for a replacement card. With more than one profile address, it asks which one. The new address comes only from the address search; the confirm panel is red and needs the advisor to tick "The client asked for this change and I verified their identity" (logged). After adding a delivery address it offers the replacement; from inside a replacement ("A different address") it adds the address and goes straight back to the replacement panel. | `skills/debit-card/update-address/`, `tools/update_address.json`, handlers `_addr_*`, llm_runtime `_ask_missing`, `_address_answer`, `_start_new_delivery`, `_after_address` |
| F-29 | Address search (autofill) for every address entry: Google Places (New) when `GOOGLE_MAPS_API_KEY` is set, otherwise a built-in demo list; US and territories only; the key stays on the server; the picked address is looked up again on the server. Apartment / suite line optional. | `integrations/address_lookup.py`, `/api/address/suggest`, web/index.html `renderAddress` |

## Second round of live testing (pending_fixes.md P-01 to P-17)

The main change: **code decides, the model only finds the client and the card.**
The model's own text is never shown in a skill turn; whatever it wanted to ask,
code asks with a card. Model-filled values are kept only when the advisor's
words in the current request support them. Every message without an open card
is a new request. Checks: `python -m tests.test_pending` (by tracker test ID).

| Fix | Pending | What changed | Where |
|---|---|---|---|
| F-30 | P-01 | Replacement to a place that is not on file: the refusal plus the client's US addresses as buttons, plus "A different address" | llm_runtime `_delivery_from_words`, `_address_panel`; handlers message |
| F-31 | P-02 | A city gets buttons for the country or US state it may be in, plus "Somewhere else" (opens the travel card) | `places.CITIES`, llm_runtime `_travel_fields` |
| F-32 | P-03 | Dates are read only when written out ("November 20 to 30"); vague dates open the travel card's calendar, nothing is proposed | `core/dates.py`, travel-notice SKILL.md |
| F-33 | P-04 | Over 14 days, or a place not on the list: the travel card again, with the reason on it | handlers `_travel_precheck`, llm_runtime `_action` |
| F-34 | P-05 | Pending card with no US address: "Add a US delivery address" instead of a refusal; a pending card's allowed actions offered as buttons | llm_runtime `_address_panel`, `_state_stop` |
| F-35 | P-06 | Close: required Reason box on the red card, editable; "permanently", "client request" and similar are not reasons; checked again on Confirm | handlers `close_reason_problem`, `_close_text_input`, `_close_confirm_check` |
| F-36 | P-07 | Close is never restated in text; "cancel her card" asks Lock or Close with buttons | close-card SKILL.md, llm_runtime `_action` |
| F-37 | P-08 | "Did you do anything?" answered by code from what actually ran; an open card is shown again | llm_runtime `_is_status_question`, `_status_reply` |
| F-38 | P-09 | Travel details on one card: destinations with suggestions (max 10) and From / To dates | `cards.travel_form_card`, `/api/places/suggest`, web/index.html `renderTravelForm` |
| F-39 | P-10 | A new request starts clean: no reason, client, card, place or date carried over | llm_runtime `send` step 4, `_sanitize` |
| F-40 | P-11 | Reason "Other" opens a required text box; the panel shows "Other: ..." | `cards.text_input_card`, handlers `reason_label` |
| F-41 | P-12 | Cancel on every card | `cards.CANCEL`, web/index.html `cancelRow` |
| F-42 | P-13 | A different action switches by itself (same client and card, nothing reused from the old card) | llm_runtime `switch_action`, `send` |
| F-43 | P-14 | Valid trip: confirmation card with the dates editable on it; the 14-day limit mentioned only when exceeded | guardrails (`dates.inline`), web/index.html `renderConfirm` |
| F-44 | P-15 | Model text with options is never shown; the history note never lists options; typo check works with an older request open | llm_runtime `_skill_turn`, `_say`, `_client_from_words` |
| F-45 | P-16 | "Actions" button in the header: the seven actions, then "Which client?" (this advisor's clients as suggestions), then the normal cards | web/index.html, llm_runtime `_action_menu`, `_client_card`, `/api/clients/suggest` |
| F-46 | P-17 | Every follow-up from the menu is a card; no client carried over from an earlier request | llm_runtime `_advance`, `_find_client` guard |

No Convex change this round: push to GitHub and Vercel redeploys; `npx convex
deploy` is not needed (unless it was not run after F-28).

## Third round of live testing (pending_fixes_2.md P2-01 to P2-05)

Checks: `python -m tests.test_pending2` (by tracker test ID).

| Fix | Pending | What changed | Where |
|---|---|---|---|
| F-47 | P2-01 | A client the advisor named who can't be found: "No client named ... was found." above the client field. Same words whether the client doesn't exist or belongs to another advisor. One heading on the card. | llm_runtime `_ask_client`, `_written_name`, `_find_client` |
| F-48 | P2-02 | "she / his card" right after a request: "Is this for Claire Beaumont (...)?" Yes / Another client / Cancel. Nothing runs without the click; a request from the Actions menu or naming another client still starts clean. | llm_runtime `last_client` (kept in the snapshot), `_confirm_client` |
| F-49 | P2-03 | Picking an address suggestion only selects it; the Apt / suite field, then "Use this address" (or Change). | web/index.html `renderAddress` |
| F-50 | P2-04 | Part of a name ("Jane") matching one client: "Is this for Jane Miller (New York, born 1979)?" first. No check when the full name is written. | llm_runtime `_full_name_said`, `_client_from_words`, `_find_client` |
| F-51 | P2-05 | An address typed in the message: outside the US -> said above the address field; a US address -> put in the field so the suggestions show at once. | llm_runtime `_typed_address`, `_outside_us`, `_address_input`; web/index.html (`prefill`) |

Also: "never actually got the card" is now read as the reason Never received.
No Convex change: push to GitHub and Vercel redeploys.

Profile addresses now change during a demo, so they live in Convex on the hosted
demo (new `addresses` table; Reset restores them from `addresses.csv`).

## Convex

`convex-demo-db/` changed with F-28 (addresses table and functions). If
`npx convex deploy` was already run after that, nothing to do this round.
