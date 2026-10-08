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

export default defineSchema({
  // The live cards. Changed by lock, unlock, replace, close, report lost/stolen.
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

  // The audit trail (one row per confirmed action or refusal that is logged).
  audit: defineTable({ row: v.any(), at: v.number() }),

  // THE SAVED DEFAULT STATE. Written from integrations/mock/data/cards.csv the
  // first time the server starts (and again whenever that CSV changes).
  // "Reset demo data" copies it back into `cards` and empties everything else.
  defaults: defineTable({
    key: v.string(), // always "cards"
    version: v.string(), // fingerprint of the CSV
    cards: v.array(v.object(card)),
  }).index("by_key", ["key"]),
});
