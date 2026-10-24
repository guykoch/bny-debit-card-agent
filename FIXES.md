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
| F-14 | Typos read through; if still unclear, the six actions as buttons | llm_runtime routing |
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

## Nothing to redeploy in Convex

No change in `convex-demo-db/`. A push to GitHub is enough.
