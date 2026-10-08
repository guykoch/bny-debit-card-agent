// Functions the Python server calls over Convex's HTTP API
// (POST <CONVEX_URL>/api/query or /api/mutation, path "demo:<name>").
//
// Every function checks a shared secret, so only our server can read or change
// the demo data: set DEMO_SERVER_SECRET to the same value in the Convex
// dashboard (Settings -> Environment Variables) and in Vercel.
import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// Convex provides environment variables on process.env (set in the dashboard).
declare const process: { env: Record<string, string | undefined> };

const cardFields = {
  card_id: v.string(),
  client_id: v.string(),
  client_name: v.string(),
  card_last4: v.string(),
  account_last4: v.string(),
  status: v.string(),
  address_on_file: v.string(),
};

function checkSecret(secret: string) {
  const expected = process.env.DEMO_SERVER_SECRET;
  if (expected && secret !== expected) {
    throw new Error("Not authorised.");
  }
}

// Drop Convex's own fields (_id, _creationTime) before returning a document.
function plain<T extends Record<string, unknown>>(doc: T) {
  const out: Record<string, unknown> = {};
  for (const [k, val] of Object.entries(doc)) {
    if (!k.startsWith("_")) out[k] = val;
  }
  return out;
}

// ------------------------------------------------------------------ cards

export const getCard = query({
  args: { secret: v.string(), card_id: v.string() },
  handler: async (ctx, { secret, card_id }) => {
    checkSecret(secret);
    const doc = await ctx.db
      .query("cards")
      .withIndex("by_card", (q) => q.eq("card_id", card_id))
      .first();
    return doc ? plain(doc) : null;
  },
});

export const listCards = query({
  args: { secret: v.string(), client_id: v.string() },
  handler: async (ctx, { secret, client_id }) => {
    checkSecret(secret);
    const docs = await ctx.db
      .query("cards")
      .withIndex("by_client", (q) => q.eq("client_id", client_id))
      .collect();
    return docs.map(plain);
  },
});

export const setCardStatus = mutation({
  args: { secret: v.string(), card_id: v.string(), status: v.string() },
  handler: async (ctx, { secret, card_id, status }) => {
    checkSecret(secret);
    const doc = await ctx.db
      .query("cards")
      .withIndex("by_card", (q) => q.eq("card_id", card_id))
      .first();
    if (!doc) throw new Error(`Unknown card ${card_id}`);
    await ctx.db.patch(doc._id, { status });
    return { ...plain(doc), status };
  },
});

export const insertCard = mutation({
  args: { secret: v.string(), card: v.object(cardFields) },
  handler: async (ctx, { secret, card }) => {
    checkSecret(secret);
    await ctx.db.insert("cards", card);
    return card;
  },
});

// ------------------------------------------------------------------ travel notices, flags

export const addTravelNotice = mutation({
  args: {
    secret: v.string(),
    card_id: v.string(),
    destination: v.array(v.string()),
    start_date: v.string(),
    end_date: v.string(),
  },
  handler: async (ctx, { secret, ...notice }) => {
    checkSecret(secret);
    await ctx.db.insert("travel_notices", notice);
    return notice;
  },
});

export const listTravelNotices = query({
  args: { secret: v.string(), card_id: v.optional(v.string()) },
  handler: async (ctx, { secret, card_id }) => {
    checkSecret(secret);
    const docs = card_id
      ? await ctx.db
          .query("travel_notices")
          .withIndex("by_card", (q) => q.eq("card_id", card_id))
          .collect()
      : await ctx.db.query("travel_notices").collect();
    return docs.map(plain);
  },
});

export const addFlag = mutation({
  args: { secret: v.string(), card_id: v.string(), advisor_id: v.string() },
  handler: async (ctx, { secret, card_id, advisor_id }) => {
    checkSecret(secret);
    await ctx.db.insert("flags", { card_id, advisor_id });
    return null;
  },
});

// ------------------------------------------------------------------ conversations

export const loadConversation = query({
  args: { secret: v.string(), conversation_id: v.string() },
  handler: async (ctx, { secret, conversation_id }) => {
    checkSecret(secret);
    const doc = await ctx.db
      .query("conversations")
      .withIndex("by_conversation", (q) => q.eq("conversation_id", conversation_id))
      .first();
    return doc ? doc.state : null;
  },
});

export const saveConversation = mutation({
  args: { secret: v.string(), conversation_id: v.string(), state: v.string() },
  handler: async (ctx, { secret, conversation_id, state }) => {
    checkSecret(secret);
    const doc = await ctx.db
      .query("conversations")
      .withIndex("by_conversation", (q) => q.eq("conversation_id", conversation_id))
      .first();
    if (doc) {
      await ctx.db.patch(doc._id, { state, updated_at: Date.now() });
    } else {
      await ctx.db.insert("conversations", { conversation_id, state, updated_at: Date.now() });
    }
    return null;
  },
});

// ------------------------------------------------------------------ audit

export const addAudit = mutation({
  args: { secret: v.string(), row: v.any() },
  handler: async (ctx, { secret, row }) => {
    checkSecret(secret);
    await ctx.db.insert("audit", { row, at: Date.now() });
    return null;
  },
});

export const listAudit = query({
  args: { secret: v.string() },
  handler: async (ctx, { secret }) => {
    checkSecret(secret);
    const docs = await ctx.db.query("audit").order("asc").take(1000);
    return docs.map((d) => d.row);
  },
});

// ------------------------------------------------------------------ default state and reset

// Called by the server on start-up. Saves the default cards (from cards.csv)
// if they are missing or the CSV changed, and fills an empty `cards` table.
export const ensureDefaults = mutation({
  args: { secret: v.string(), version: v.string(), cards: v.array(v.object(cardFields)) },
  handler: async (ctx, { secret, version, cards }) => {
    checkSecret(secret);
    const saved = await ctx.db
      .query("defaults")
      .withIndex("by_key", (q) => q.eq("key", "cards"))
      .first();
    let updated = false;
    if (!saved) {
      await ctx.db.insert("defaults", { key: "cards", version, cards });
      updated = true;
    } else if (saved.version !== version) {
      await ctx.db.patch(saved._id, { version, cards });
      updated = true;
    }
    const anyCard = await ctx.db.query("cards").first();
    let seeded = false;
    if (!anyCard) {
      for (const card of cards) await ctx.db.insert("cards", card);
      seeded = true;
    }
    return { defaults_updated: updated, seeded };
  },
});

// "Reset demo data": everything back to the saved default state.
export const reset = mutation({
  args: { secret: v.string() },
  handler: async (ctx, { secret }) => {
    checkSecret(secret);
    const saved = await ctx.db
      .query("defaults")
      .withIndex("by_key", (q) => q.eq("key", "cards"))
      .first();
    if (!saved) throw new Error("No saved default state yet. Start the server once first.");
    const counts: Record<string, number> = {};
    for (const table of ["cards", "travel_notices", "flags", "conversations", "audit"] as const) {
      const docs = await ctx.db.query(table).collect();
      for (const d of docs) await ctx.db.delete(d._id);
      counts[table] = docs.length;
    }
    for (const card of saved.cards) await ctx.db.insert("cards", card);
    return { cleared: counts, restored_cards: saved.cards.length };
  },
});
