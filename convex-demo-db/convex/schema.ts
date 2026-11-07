// Tables for the hosted demo. Only data that changes during a demo lives here;
// clients and advisor entitlements stay in the repository's CSV files.
import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

const card = {
  card_id: v.string(),
  client_id: v.string(),
  client_name: v.string(),
  card_last4: v.string(),
  account_last4: v.string(),
  status: v.string(), // active | locked | closed | pending
  address_on_file: v.string(),
};

const address = {
  client_id: v.string(),
  label: v.string(), // "Home", "Vacation home", "Delivery (added 10/24/2026)"
  address: v.string(),
  state: v.string(), // two-letter US state / territory code
  country: v.string(),
};

export default defineSchema({
  // Each client's profile addresses. Replacement cards may only go to these.
  addresses: defineTable(address).index("by_client", ["client_id"]),

  // The live cards. Changed by lock, unlock, replace, report lost/stolen.
  cards: defineTable(card)
    .index("by_card", ["card_id"])
    .index("by_client", ["client_id"]),

  travel_notices: defineTable({
    card_id: v.string(),
    destination: v.array(v.string()),
    start_date: v.string(),
    end_date: v.string(),
  }).index("by_card", ["card_id"]),

  // Accounts flagged by a lost/stolen report.
  flags: defineTable({ card_id: v.string(), advisor_id: v.string() }),

  // One document per chat thread: what the chat remembers between messages.
  conversations: defineTable({
    conversation_id: v.string(),
    state: v.string(), // JSON
    updated_at: v.number(),
  }).index("by_conversation", ["conversation_id"]),

  // ---------------------------------------------------------------- AUDIT
  // Two logs side by side (they sort together in the dashboard). Both start with
  // the same columns - when (US format, Eastern time), advisor_id, conversation_id -
  // so a conversation can be followed in one log and its actions found in the other.

  // audit_actions: every card action that reached our checks, done or stopped.
  audit_actions: defineTable({
    when: v.string(), // "11/02/2026 3:45:12 PM ET"
    advisor_id: v.string(),
    conversation_id: v.string(),
    action_name: v.string(), // "Lock card", "Replace card", ...
    result: v.string(), // Completed | Refused | Not permitted
    client: v.string(), // "Jane Miller (C-88210)"
    card: v.string(), // "...4417"
    details: v.string(), // what the confirmation card showed: "Reason: Damaged | Deliver to: ..."
    message: v.string(), // the result or refusal message the advisor saw
    advisor_request: v.string(), // the advisor's own words
    at: v.number(), // sort key (milliseconds)
    record: v.any(), // technical copy: tool name, codes, what the model understood
  })
    .index("by_conversation", ["conversation_id", "at"])
    .index("by_advisor", ["advisor_id", "at"]),

  // audit_chat: every line of every conversation, in order.
  audit_chat: defineTable({
    when: v.string(),
    advisor_id: v.string(),
    conversation_id: v.string(),
    speaker: v.string(), // Advisor | NetX AI
    message: v.string(), // what was typed / clicked, or what the chat showed
    input: v.string(), // Typed | Button | Form (advisor lines only)
    card: v.string(), // the card shown, e.g. "Confirmation: Lock debit card"
    raw_input: v.string(), // the value a button sent, when it differs from its label
    at: v.number(),
  })
    .index("by_conversation", ["conversation_id", "at"])
    .index("by_advisor", ["advisor_id", "at"]),

  // ---------------------------------------------------------------- SERVICE CENTER TICKETS
  // One row per ticket sent from the chat (Stop Payment, Check Copy, Address Update,
  // Misc). Sending a ticket changes nothing else; BNY's Service Center would process it.
  tickets: defineTable({
    ticket_id: v.string(), // "SR-10234"
    draft_id: v.string(), // one per review card: the same Send twice saves one ticket
    status: v.string(), // Submitted
    advisor_id: v.string(),
    conversation_id: v.string(),
    tool: v.string(), // stop_payment | check_copy | address_update | misc_request
    ticket: v.string(), // "Stop Payment"
    category: v.string(),
    request: v.string(),
    request_type: v.string(),
    client_id: v.string(),
    client_name: v.string(),
    account: v.string(), // "AMA ...8821"
    fields: v.array(v.object({ label: v.string(), value: v.string() })),
    attachments: v.array(v.any()), // {storage_id, name, size, type}
    when: v.string(), // "11/07/2026 3:45:12 PM ET"
    at: v.number(),
  })
    .index("by_advisor", ["advisor_id", "at"])
    .index("by_draft", ["draft_id"]),

  // Small per-advisor preferences, e.g. the saved Call Back # for tickets.
  advisor_settings: defineTable({ advisor_id: v.string(), settings: v.any() }).index(
    "by_advisor",
    ["advisor_id"],
  ),

  // Old single audit table (before the split). Not written any more; Reset empties it.
  audit: defineTable({ row: v.any(), at: v.number() }),

  // THE SAVED DEFAULT STATE. Written from integrations/mock/data/cards.csv and
  // addresses.csv the first time the server starts (and whenever they change).
  // "Reset demo data" copies it back into `cards` and `addresses` and empties
  // everything else.
  defaults: defineTable({
    key: v.string(), // always "cards"
    version: v.string(), // fingerprint of the CSVs
    cards: v.array(v.object(card)),
    addresses: v.optional(v.array(v.object(address))),
  }).index("by_key", ["key"]),
});
