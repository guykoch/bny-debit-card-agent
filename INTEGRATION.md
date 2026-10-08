# Taking this to BNY

Everything BNY-specific is in one folder. This is the whole migration.

## The three things to implement

Fill in `integrations/bny/services.py`, then set `DCA_MODE=bny`. Nothing in
`core/` changes.

| Class | What it must answer |
|---|---|
| `BnyEntitlementService` | May advisor X perform action Y on account Z? Only needed if `TRUST_UPSTREAM_ENTITLEMENT` is false |
| `BnyClientDirectory` | Which clients match this name, within this advisor's book? |
| `BnyCardSystem` | The six actions, plus get a card and list a client's cards |

## The AI layer: from OpenAI's GPT-5.4 to BNY's on-prem GPT-5.4

The demo calls OpenAI's public GPT-5.4 (`gpt-5.4`) through
`interfaces/llm_client.py`. To use BNY's on-prem instance instead:

- If BNY's gateway speaks the same Chat Completions API, set `OPENAI_BASE_URL`
  and the credential in `config/settings.py` (or the environment). Nothing else
  changes.
- If it does not, rewrite `interfaces/llm_client.py` only. Its one method,
  `chat(messages, tools, response_format)`, is all the runtime uses.

The model needs tool calling and JSON-schema answers (both used in
`interfaces/llm_runtime.py`). Neither the prompts nor the guardrails change.

## What we need from BNY, in order of how much it matters

**1. Is the orchestrator's entitlement check at client level or action level?**

We assume BNY checks entitlement before routing and only sends us approved
requests, so by default we do not check again. The open question is
granularity. Our six actions differ in weight - a lock is reversible, a
permanent close is not - and an approval to deal with a client may not be an
approval to do either.

If the upstream check is at client level, set `TRUST_UPSTREAM_ENTITLEMENT` to
false and implement `BnyEntitlementService` so the agent checks the specific
action as well. If it is already at action level, leave the flag alone and that
class is never called.

**2. The six API contracts.** Endpoint names, request fields, response shape,
and the error cases. The mapping table is in `integrations/bny/services.py`.
A redacted example response is enough to get the field names right.

**3. Sample record shapes.** What a client and a card actually look like:
field names, id formats, status values. Our `core/models.py` is a guess based
on what the screens display.

**4. Screen recordings of the current flow.** For counting the real clicks, and
for matching the confirmation wording to what advisors already see.

**5. How the chat panel renders replies.** We return card payloads
(`core/cards.py`). If the surface cannot render them, every card has a text
fallback and nothing breaks - but we would rather know.

## Things we assumed, and what happens if we are wrong

| Assumption | If it is wrong |
|---|---|
| Each action is its own API call | Group them in `BnyCardSystem`; nothing above it changes |
| Entitlement is fully handled upstream | If it turns out to be client level only, flip the flag and implement `BnyEntitlementService` |
| The orchestrator passes advisor id and sentence | Adjust the two unpack functions in `interfaces/a2a_server.py` |
| The client id may already be resolved | We fall back to `find_client`; already handled |
| The chat can render cards | Text fallback already built; no code change |
| BNY's GPT-5.4 speaks the OpenAI Chat Completions API | Rewrite `interfaces/llm_client.py` only |
| Status values are active / locked / closed / pending | Map them in `BnyCardSystem`; the precheck rules in `core/handlers.py` read these names |

## Before this goes near production

- `CONFIRM_REQUIRED_FOR_WRITES` in `config/settings.py` must stay true.
- `core/audit.py` `_sink` must write to Persistent Logging, not a list.
- Agree `MAX_TRAVEL_DAYS` and any other limits with the business, not with us.
- The chat panel is read-only today. Letting it act is a permission and
  certification question, not a technical one, and it is not ours to answer.
