# Plan — the first agent job: "Why was my card declined?"

**Status: PLAN ONLY. Nothing here is built.** `agent/` still holds only its README.
Implement only when Guy says so. Written 8 October 2026 against the repository as it
is today (GPT-5.4 runtime in `interfaces/llm_runtime.py`, six skills, 4 test suites).

---

## How to use this plan

These are **changes on top of the existing repository** — not a rebuild. Apply them to the
`debit-card-agent` folder Guy already has. Do not regenerate or rewrite any existing file;
edit only what §5 and §7 list, and add only the new files listed in §3, §4 and §6.

**Base version check before starting** (the plan assumes this version):
- `interfaces/llm_runtime.py`, `interfaces/llm_client.py` and `web/index.html` exist
  (the GPT-5.4 runtime and the mock NetX AI chat).
- `agent/` contains only `README.md`.
- `tools/` has 8 schemas; `integrations/mock/data/` has `clients.csv`, `cards.csv`,
  `entitlements.csv`.
- Tests pass: `test_guardrails` 22, `test_skills` 39, `test_choices` 18, `test_llm_runtime` 36,
  `test_hosting` 20.
- The hosted-demo layer exists: conversations are saved with `snapshot()` / `restore()` after
  every message (`interfaces/threads.py`; memory locally, Convex when hosted on Vercel).
If any of these differs, stop and ask Guy before changing anything.

**Summary of the file changes**

| New files | Edited files |
|---|---|
| `integrations/mock/data/declines.csv`, `travel_notices.csv`, `holds.csv`, `limits.csv` | `integrations/mock/dataset.py`, `integrations/mock/data/README.md` |
| `tools/get_recent_declines.json`, `get_travel_notices.json`, `get_holds.json`, `get_card_limits.json` | `core/schemas.py` (integer type), `core/guardrails.py` (`_read()` only) |
| `agent/state.py`, `agent/runner.py`, `agent/workflows/declined-card.md` | `integrations/ports.py`, `integrations/mock/services.py`, `integrations/bny/services.py` |
| `tests/test_agent.py` | `core/skills.py` (workflow loaders), `interfaces/llm_runtime.py` (routing + resume) |
| | `interfaces/local_runtime.py` (one message), `web/index.html` (steps), `interfaces/a2a_agent_card.json`, `agent/README.md`, docs (§9) |

## 0. In one paragraph

Add one investigation job. The advisor asks why a client's card was declined; GPT-5.4
decides which read-only checks to run, in what order, based on what each check returns,
and explains the cause. That choosing of its own steps is what makes it an agent. It can
only **read**. If it finds a fix ("add a travel notice"), it **offers** it; a "yes" hands
over to the existing skill, which still ends at the confirmation panel and the advisor's
Confirm click. The six skills, the guardrail, the Confirm step and the audit work exactly
as today.

## 1. Decisions to confirm before building

| # | Question | Plan assumes |
|---|---|---|
| 1 | First agent job | "Why was my card declined?" (read-only, lowest risk) |
| 2 | Mock data | The 7 cases in §3 |
| 3 | Show the agent's steps in the chat? | Yes — small grey lines ("Checked recent declines") above the answer |
| 4 | Fraud | Never judged by the AI; a fixed hand-over sentence from code (§6.4) |
| 5 | Limits | 6 checks per question, 60 seconds; hand over after that |

## 2. What is AI, what is the agent, what is plain code (Guy's no-mixing rule)

| Part | Type |
|---|---|
| Recognising "this is a declined-card question" | AI — the existing routing call, one new option |
| Choosing the next check from what has been found; writing the explanation | **Agent** — GPT-5.4 inside `agent/runner.py`'s loop |
| Running each check, ownership, ids, entitlement scope | Plain code — `core/guardrails.py` `_read()` |
| Step cap, time cap, tool allow-list, fraud sentence, hand-over text | Plain code — `agent/runner.py` |
| Asking "which card / which decline?" when ambiguous | Code panel (cards) or model options (declines) — same as today |
| The fix itself (e.g. add a travel notice) | The existing skill → confirm panel → Confirm. Not the agent |
| Audit of the investigation | Plain code — `core/audit.py` |

Slides: the agent pieces get their own colour; amber stays the confirmation path.

---

## 3. Mock data — new files in `integrations/mock/data/`

Dates are stored **relative to today** (`days_ago`, `days_from_now`), converted at load
time, so "yesterday" is always true whenever the demo runs.

### 3.1 `declines.csv`
```
decline_id,card_id,days_ago,merchant,amount,country,reason
D-001,CARD-4417,1,Hotel Avenida Lisbon,412.00,Portugal,location
D-002,CARD-2201,0,Apple Store Fifth Ave,1299.00,US,limit
D-003,CARD-3401,2,Whole Foods Chicago,86.40,US,hold
D-004,CARD-2091,3,Shell Wellesley,54.10,US,card_locked
D-005,CARD-2772,1,Electronics Hub Online,1840.00,US,suspected_fraud
D-006,CARD-9007,1,Amazon,230.00,US,issuer_declined
D-007,CARD-9008,4,Darien Pharmacy,38.20,US,card_locked
```
Reason codes (ours, invented): `location`, `limit`, `hold`, `card_locked`,
`suspected_fraud`, `issuer_declined` (no reason given — the unexplained case).

### 3.2 `travel_notices.csv` (seeds the store the travel-notice action already writes to)
```
card_id,destination,starts_days_from_now,ends_days_from_now
CARD-1581,Ghana,-2,10
```
Margaret Osei-Bonsu, in Ghana now — proves the check returns real data. **Jane has none.**

### 3.3 `holds.csv`
```
client_id,amount,reason,until_days_from_now
C-10344,2500.00,deposit review,4
```

### 3.4 `limits.csv`
```
card_id,daily_limit,used_today
CARD-2201,2000.00,2000.00
```
Every card not listed: daily limit 5000.00, used today 0.00 (default in code, stated in
the data README).

### 3.5 The seven cases this produces (all visible to ADV-1234)

| Client | Card | What the agent should find |
|---|---|---|
| Jane Miller (C-88210) | 4417 | Lisbon, reason location → no travel notice for Portugal → offer one |
| Robert Castellano (C-10220) | 2201 of 2201/2202 | Reason limit → limits 2,000 of 2,000 used → resets tomorrow |
| Priya Raghunathan (C-10344) | 3401 | Reason hold → $2,500 deposit-review hold, ends in 4 days |
| Thomas Whitfield (C-12090) | 2091 | Reason card_locked → card is locked → offer to unlock |
| Elena Vasquez (C-12771) | 2772 | Reason suspected_fraud → fixed hand-over to the card team |
| Anne-Marie Dubois (C-19006) | 9007 and 9008 | Two declines, different reasons → asks which one |
| Anne-Marie, decline D-006 | 9007 | issuer_declined; card active, no hold, under limit → "couldn't find the cause" |

ADV-5678 asking about Jane → "No matching client found" (existing behaviour).

### 3.6 Code for the data
- `integrations/mock/dataset.py`: load the four CSVs; validate reason codes; convert
  relative days to dates using `date.today()`.
- `integrations/mock/data/README.md`: describe the four files, reason codes, the default
  limit, and add the seven rows to "rows the tests depend on".

---

## 4. New read-only tools — `tools/*.json` (4 files)

All `"access": "read"`. Descriptions are written for the model.

| Tool | Required | Optional | Returns |
|---|---|---|---|
| `get_recent_declines` | `client_id` | `card_id`, `days` (int, default 30) | declines on that client's cards: decline_id, card_last4, date, merchant, amount, country, reason |
| `get_travel_notices` | `client_id`, `card_id` | — | active + upcoming notices: destination, start, end |
| `get_holds` | `client_id` | — | holds: amount, reason, until |
| `get_card_limits` | `client_id`, `card_id` | — | daily_limit, used_today, remaining |

Note `get_recent_declines` takes the **client**, so the agent sees declines across all the
client's cards without first asking "which card?".

`core/schemas.py` needs one addition: type `integer` in `validate()` (today it checks
string, boolean, array). Note Python treats `True` as an int — reject booleans there.

## 5. Plumbing for the tools

| File | Change |
|---|---|
| `integrations/ports.py` | `CardSystem` gains `recent_declines(client_id, card_id=None, days=30)`, `travel_notices_for(card_id)`, `holds_for(client_id)`, `limits_for(card_id)` |
| `integrations/mock/services.py` | Implement them. `MockCardSystem.travel_notices` is seeded from `travel_notices.csv`, so a notice added in the chat is seen by the agent (one store) |
| `integrations/bny/services.py` | Stubs raising `NotImplementedError`; add the four rows to the mapping table |
| `core/guardrails.py` `_read()` | One branch per tool: if `card_id` given, the card must exist and belong to `client_id` (else `bad_request`); if `TRUST_UPSTREAM_ENTITLEMENT` is false, require the `view` grant (else `not_entitled`); return `ToolResponse(status="ok", data={...})`. The write path is not touched |
| `integrations/mock/dataset.py` | Loaders (§3.6) |

---

## 6. The agent files — `agent/`

### 6.1 `agent/workflows/declined-card.md` — the briefing (full text)
```markdown
---
name: declined-card
description: Find out why a client's debit card was declined, and suggest a fix.
triggers: declined, decline, rejected, refused, didn't go through, card not working, why was
tools: find_client, list_cards, get_recent_declines, get_travel_notices, get_holds, get_card_limits
fixes: travel-notice, unlock-card
max_steps: 6
---

# Why was a card declined?

## Goal
Find the reason a client's card was declined and explain it in plain words.
You can only look. Never change anything; if there is a fix, offer it in one sentence
and stop. The advisor decides.

## Start
1. Find the client (find_client), as in the shared rules.
2. Call get_recent_declines for that client. If the advisor named a card, a merchant or a
   day, use it to pick the decline.
3. If there are several declines with different reasons and you cannot tell which one the
   advisor means, ask which one with present_options (date, merchant, card ending).
4. If there are no declines in the last 30 days, finish with cause no_declines.

## Usual causes, by reason code
- location → check get_travel_notices for that card and country.
  No notice covering the date: "No travel notice for <country>." Offer to add one.
- limit → check get_card_limits. Used up: say so; it resets tomorrow. No fix to offer.
- hold → check get_holds. Say the amount, the reason and when it ends. No fix to offer.
- card_locked → check list_cards for the card status. Locked: offer to unlock it.
  Closed: say a replacement would be needed.
- suspected_fraud → do not investigate further and do not judge. The system adds the
  hand-over sentence.
- issuer_declined, or anything else → check card status, holds and limits in turn. If
  none explains it, say you couldn't find the cause and suggest the card team.

## How to work
- One check at a time. After each, decide whether it explains the decline.
- Stop as soon as one cause explains it.
- Never guess a cause the data does not show.
- Always end by calling finish_investigation with one or two short sentences (the cause,
  then the offer if there is one), the cause code, and the offer:
  "It was declined in Lisbon yesterday because there's no travel notice for Portugal.
  Want me to add one?"  → cause location, offer travel-notice.
```

### 6.2 `agent/state.py`
```python
@dataclass
class JobState:
    job_id: str                  # "JOB-<short uuid>"
    workflow: str                # "declined-card"
    question: str                # the advisor's words
    status: str = "running"      # running | waiting | done | handed_over | failed | abandoned
    client_id: str | None = None
    card_id: str | None = None
    steps: list = field(default_factory=list)   # {"tool", "input", "summary"}
    answer: str | None = None
    cause: str | None = None     # from finish_investigation (§6.3a)
    offer: str = "none"          # none | travel-notice | unlock-card
    pending_panel: dict | None = None   # the choice panel shown while waiting
    started_at: float = field(default_factory=time.time)

    def summary_lines(self) -> list[str]   # "Checked recent declines", ... (for the chat)
    def findings_note(self) -> str          # one line for the conversation notes (§6.5)
```
Part of the conversation: `GptConversation.snapshot()` / `restore()` must include the job
(`JobState` as a plain dict), so a waiting job survives between messages when hosted on
Vercel, where each message may reach a fresh process and state lives in Convex.

### 6.3 `agent/runner.py`
```
class Runner:
    def __init__(self, conversation)            # GptConversation: model client, services,
                                                # session, history, seen-id set
    def start(self, question) -> ToolResponse   # new JobState, then _loop()
    def resume(self, advisor_reply) -> ToolResponse   # after a question; then _loop()

    _loop():
        system = skills.workflow_prompt(wf) (§7) + runtime_notes(today) + job state so far
        tools  = the workflow's tools (from its frontmatter) + present_options
                 + finish_investigation (§6.3a)
        repeat until done:
            if len(job.steps) >= max_steps or 60 s passed → hand over (fixed text)
            msg = model.chat(messages, tools)          # ModelUnavailable → failed (§6.4)
            finish_investigation → job.answer, job.offer; status done; break
            no tool call (plain text) → it is a question to the advisor:
                status waiting; return the text (resume on the next message)
            present_options → status waiting; return the choice panel (resume later)
            tool not in the workflow's list (e.g. lock_card) → refuse, tell the model
            ids must be in the conversation's seen set (as for skills)
            find_client / list_cards → same code panels as skills if several match
                                       (status waiting; resume after the pick)
            run through guardrails.dispatch(..., confirmed=False)   # all read-only
            record step (tool, input, one-line summary); add returned ids to seen
        apply code rules (§6.4), write the audit (§6.5), add the findings note
        return ToolResponse(status="needs_input" if offer else "ok",
                            message=answer,
                            data={"job_id", "workflow", "status", "offer",
                                  "steps": summary_lines})
```

### 6.3a `finish_investigation` — how the model says it is done
A presentation-only tool defined in `agent/runner.py` (not in `tools/`, never reaches the
guardrail), like `present_options`:
```
finish_investigation(answer: string,               # 1–2 sentences for the advisor
                     cause: enum[location, limit, hold, card_locked, card_closed,
                                 suspected_fraud, no_declines, unknown],
                     offer: enum[none, travel-notice, unlock-card])
```
Why: code then knows for certain whether the job ended, what the cause was (for the audit
and the fraud rule), and which fix was offered (for the findings note), instead of guessing
from free text. A plain-text reply always means "the model is asking the advisor something".
Code checks `offer` against the workflow's `fixes` list; anything else becomes `none`.

### 6.4 Rules enforced in code (not left to the model)
- **Read-only**: only the workflow's listed tools are offered and accepted; every one is
  `access: read` — the runner refuses to start if a listed tool is a write tool.
- **Caps**: 6 tool calls, 60 seconds → "I couldn't find the cause in the checks I can
  run. Please contact the card team." (status `handed_over`).
- **Fraud**: if any decline the agent looked at has reason `suspected_fraud`, or the model
  finishes with cause `suspected_fraud`, the reply is replaced by
  "This decline was flagged as suspected fraud. That is handled by the card team; I can't
  confirm or clear it." (status `handed_over`).
- **Model down**: "The AI service did not respond, so the investigation stopped. Nothing
  was changed." (status `failed`).
- **A waiting job never captures a new request**: if the advisor's next message is routed
  somewhere else, the waiting job is ended (audited as `abandoned`) and the new request
  runs normally.
- **One client per job**; the advisor-scoped directory and `seen` ids apply as for skills.

### 6.5 Audit and hand-over to a fix
- `core/audit.write(session, action="investigate:declined-card", client_id, card_id,
  outcome=<status>, model_interpretation=None, detail={"job_id", "steps": [tool names],
  "answer"})` — one row per finished job (done, handed_over or failed).
- Findings note added to the conversation history, e.g. *"Context: investigation
  JOB-3f2a found: Jane Miller (C-88210), card CARD-4417, declined yesterday at Hotel
  Avenida Lisbon, Portugal, reason location; no travel notice for Portugal."* — so when
  the advisor answers "yes", the router sends it to `travel-notice` (existing rule:
  accepting an offer → that skill) and the skill already knows the client, card and
  country. It still asks for the trip dates, then shows the confirmation panel.

### 6.6 `agent/README.md`
Rewrite from "nothing built" to: what is built (one job), the three files, the rules in
§6.4, how to add a second workflow, what is still not built (chained actions, `undo`).

---

## 7. Changes to existing files

| File | Change |
|---|---|
| `core/skills.py` | `load_workflows()` (reads `agent/workflows/*.md` with the same frontmatter parser), `get_workflow(name)`, `workflow_prompt(wf)` = `_shared.md` + the workflow body, `workflow_tools(wf)` = its listed tools from `tools/` |
| `interfaces/llm_runtime.py` | Router: add workflows to the choice list (`declined-card` with its description and triggers) and one rule: "why was a card declined / card not working" → `declined-card`. If chosen: `Runner(self).start(text)`; if a job is `waiting`, the next message goes to `runner.resume()` (unless the router picks something else, which ends the job). Keep everything else as is |
| `interfaces/local_runtime.py` | If a sentence matches the workflow triggers: "Investigations need the GPT-5.4 runtime." |
| `web/index.html` | If `data.steps` is present, draw them as small grey lines with a tick above the answer. Show a light "Investigating…" typing state |
| `interfaces/a2a_agent_card.json` | Add the job to `skills` with an example; version 0.3.0 |
| `core/handlers.py`, `core/cards.py`, write path of `core/guardrails.py`, the six SKILL.md files, `_shared.md` | **No change** |
| `interfaces/a2a_server.py` | No change (the branch lives inside `GptConversation`) |
| `interfaces/llm_runtime.py` `snapshot()`/`restore()` | Add the job state (§6.2) |
| `integrations/convex_store/services.py` + `convex-demo-db/convex/` | Hosted demo only: tables and functions for declines, travel notices, holds, limits if the agent should read the shared Convex data (travel notices already live there); include them in the saved default state and in `reset` |

## 8. Tests — `tests/test_agent.py` (scripted model, no key)

1. Jane: declines → travel notices → finish_investigation(cause=location,
   offer=travel-notice); 2 steps shown; status needs_input.
1b. A plain-text question from the model → status waiting → the next message resumes the
   same job (no new job, steps kept).
1c. finish_investigation with an offer not in the workflow's `fixes` → treated as none.
2. "yes" after the offer routes to `travel-notice` with the client and card already known.
3. A travel notice added via the skill first → the agent now sees it (one store).
4. Robert: finds the decline on 2201 without asking which card.
4b. Steps counted correctly: Jane = 3 (find client, declines, travel notices); Anne-Marie
   after picking Amazon = 5 (under the cap of 6).
5. Anne-Marie: two declines → asks which → resumes after the answer.
6. Elena: fraud sentence from code, status handed_over, whatever the model wrote.
7. Model calls `lock_card` → refused; card untouched.
8. 6 steps without an answer → hand-over text.
9. ADV-5678 → Jane not found.
10. Model down mid-job → failed message; nothing changed.
11. One audit row per job with the steps and answer.
12. `_read()` for each new tool: card of another client → `bad_request`; flag off without
    `view` → `not_entitled`.
13. All existing suites unchanged and passing (22 + 39 + 18 + 36 + 20).
13b. A waiting job survives `snapshot()` → `restore()` (as on Vercel).
14. A job left waiting, then "lock Jane's card" → the job ends, the lock skill runs.

Plus a live check list to run with the key before showing Ben (§10).

## 9. Docs to update after building

`README.md` (demo sentences, file map: 12 tool schemas, `agent/` built for one job) ·
`ARCHITECTURE.md` ("what is AI" table: agent row) · `HOW-IT-FITS-TOGETHER.md` (a short
"investigation path" section) · `INTEGRATION.md` (four new BNY endpoints to map) ·
`skills/debit-card/README.md` ("eight tools" → twelve) · `PROJECT-CONTEXT-HANDOFF.md`
(§4.8, §5, §6, §9, §10) · mock data README. Decks: "eight forms" becomes twelve; the Agent
Logic slide 2 should show the agent in its own colour (not amber).

## 10. Usage after it is built

| Advisor types | What happens |
|---|---|
| *Why was Jane Miller's card declined yesterday?* | Checked recent declines · Checked travel notices → "Declined at Hotel Avenida Lisbon yesterday: no travel notice for Portugal. Want me to add one?" → *yes* → travel-notice skill asks the dates → confirm panel |
| *Robert Castellano's card keeps getting declined* | Checked recent declines · Checked limits → "Card ending 2201 hit its $2,000 daily limit; it resets tomorrow." |
| *Why did Priya's card fail at Whole Foods?* | Declines · Holds → "A $2,500 deposit-review hold until <date>." |
| *Thomas Whitfield's card isn't working* | Declines · Card status → "The card ending 2091 is locked. Want me to unlock it?" → *yes* → unlock skill → confirm panel |
| *Why was Elena Vasquez declined?* | Declines → fixed fraud hand-over sentence |
| *Why was Anne-Marie Dubois's card declined?* | Declines → "Which one: 7 Oct Amazon (…9007) or 4 Oct Darien Pharmacy (…9008)?" → *Amazon* → status, holds, limits → "I couldn't find the cause. Please contact the card team." |

Live check list (with the key): the six rows above, plus *"what cards does Robert have?"*
(still out of scope), *"lock Jane's card"* (still the lock skill), and a misspelt name.

## 11. Assumptions

- Real decline records carry a reason; our codes are invented.
- BNY's upstream entitlement covers reading declines, holds and limits for the advisor's
  own clients (same open question 1 as today, now also for reads).
- The real systems expose declines, holds, limits and travel notices as separate reads.
- One job only. "Handle the whole lost-wallet call" needs chained actions and `undo` —
  a later plan.
- A question costs 3–7 model calls (routing + up to 6 checks): a few seconds, a few cents.
- Job state lives in memory; restarting the server ends open jobs.

## 12. Build order and done-criteria

1. Mock data + loaders + data README → `dataset` loads, dates relative.
2. Four tool schemas + `integer` in `schemas.validate` → `test_skills` still 39/39.
3. Ports, mock, BNY stubs, `_read()` branches → test 12 passes.
4. `agent/state.py`, `agent/workflows/declined-card.md`, `agent/runner.py`, `core/skills.py` loaders.
5. `llm_runtime` routing + resume; `local_runtime` message.
6. `chat.html` steps; agent card.
7. `tests/test_agent.py` (all 13) + all existing suites green.
8. End-to-end browser run with a fake model endpoint (as done for the GPT runtime).
9. Docs (§9), rebuild the skills deck only if a skill file changed (none planned).
10. Live run with the key: §10 check list. Adjust the workflow text, not the code, first.

**Done when:** all suites pass; the six example conversations behave as in §10 with a
scripted model; nothing in the write path, the six skills or the Confirm flow changed.
