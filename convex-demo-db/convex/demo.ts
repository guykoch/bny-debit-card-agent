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

// ------------------------------------------------------------------ profile addresses

const addressFields = {
  client_id: v.string(),
  label: v.string(),
  address: v.string(),
  state: v.string(),
  country: v.string(),
};

export const listAddresses = query({
  args: { secret: v.string(), client_id: v.string() },
  handler: async (ctx, { secret, client_id }) => {
    checkSecret(secret);
    const docs = await ctx.db
      .query("addresses")
      .withIndex("by_client", (q) => q.eq("client_id", client_id))
      .collect();
    return docs.map(plain);
  },
});

export const addAddress = mutation({
  args: { secret: v.string(), ...addressFields },
  handler: async (ctx, { secret, ...row }) => {
    checkSecret(secret);
    await ctx.db.insert("addresses", row);
    return row;
  },
});

export const updateAddress = mutation({
  args: { secret: v.string(), ...addressFields },
  handler: async (ctx, { secret, client_id, label, address, state, country }) => {
    checkSecret(secret);
    const docs = await ctx.db
      .query("addresses")
      .withIndex("by_client", (q) => q.eq("client_id", client_id))
      .collect();
    const doc = docs.find((d) => d.label === label);
    if (!doc) return false;
    await ctx.db.patch(doc._id, { address, state, country });
    return true;
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

// One row in audit_actions (a card action done or stopped).
export const addAuditAction = mutation({
  args: { secret: v.string(), row: v.any() },
  handler: async (ctx, { secret, row }) => {
    checkSecret(secret);
    const str = (x: unknown) => (x === null || x === undefined ? "" : String(x));
    await ctx.db.insert("audit_actions", {
      when: str(row.when),
      advisor_id: str(row.advisor_id),
      conversation_id: str(row.conversation_id),
      action_name: str(row.action_name),
      result: str(row.result),
      client: str(row.client),
      card: str(row.card),
      details: str(row.details),
      message: str(row.message),
      advisor_request: str(row.advisor_request),
      at: typeof row.at === "number" ? row.at : Date.now(),
      record: row.record ?? null,
    });
    return null;
  },
});

// The lines of one chat message (the advisor's line and the chat's answer).
export const addAuditChat = mutation({
  args: { secret: v.string(), rows: v.array(v.any()) },
  handler: async (ctx, { secret, rows }) => {
    checkSecret(secret);
    const str = (x: unknown) => (x === null || x === undefined ? "" : String(x));
    for (const row of rows) {
      await ctx.db.insert("audit_chat", {
        when: str(row.when),
        advisor_id: str(row.advisor_id),
        conversation_id: str(row.conversation_id),
        speaker: str(row.speaker),
        message: str(row.message),
        input: str(row.input),
        card: str(row.card),
        raw_input: str(row.raw_input),
        at: typeof row.at === "number" ? row.at : Date.now(),
      });
    }
    return null;
  },
});

// Recent action records (the server's volume limit reads these).
export const listAudit = query({
  args: { secret: v.string() },
  handler: async (ctx, { secret }) => {
    checkSecret(secret);
    const docs = await ctx.db.query("audit_actions").order("desc").take(1000);
    return docs.map((d) => d.record).reverse();
  },
});

// One conversation, in order (demo endpoint /api/audit/chat).
export const listChat = query({
  args: { secret: v.string(), conversation_id: v.optional(v.string()) },
  handler: async (ctx, { secret, conversation_id }) => {
    checkSecret(secret);
    const docs = conversation_id
      ? await ctx.db
          .query("audit_chat")
          .withIndex("by_conversation", (q) => q.eq("conversation_id", conversation_id))
          .collect()
      : await ctx.db.query("audit_chat").order("desc").take(500);
    return docs.map(plain);
  },
});

// ------------------------------------------------------------------ tickets

export const addTicket = mutation({
  args: { secret: v.string(), ticket: v.any() },
  handler: async (ctx, { secret, ticket }) => {
    checkSecret(secret);
    const str = (x: unknown) => (x === null || x === undefined ? "" : String(x));
    const same = await ctx.db
      .query("tickets")
      .withIndex("by_draft", (q) => q.eq("draft_id", str(ticket.draft_id)))
      .first();
    if (same) return { ...plain(same), duplicate: true };
    const count = (await ctx.db.query("tickets").collect()).length;
    const doc = {
      ticket_id: `SR-${10234 + count}`,
      draft_id: str(ticket.draft_id),
      status: "Submitted",
      advisor_id: str(ticket.advisor_id),
      conversation_id: str(ticket.conversation_id),
      tool: str(ticket.tool),
      ticket: str(ticket.ticket),
      category: str(ticket.category),
      request: str(ticket.request),
      request_type: str(ticket.request_type),
      client_id: str(ticket.client_id),
      client_name: str(ticket.client_name),
      account: str(ticket.account),
      account_id: str(ticket.account_id),
      check_numbers: (ticket.check_numbers ?? []).map((n: unknown) => str(n)),
      fields: (ticket.fields ?? []).map((f: { label: unknown; value: unknown }) => ({
        label: str(f.label),
        value: str(f.value),
      })),
      attachments: ticket.attachments ?? [],
      when: str(ticket.when),
      at: typeof ticket.at === "number" ? ticket.at : Date.now(),
    };
    await ctx.db.insert("tickets", doc);
    return doc;
  },
});

// Submitted Stop Payment / Check Copy tickets for one check, any advisor. The
// chat warns before a second request for the same check.
export const openTicketsForCheck = query({
  args: { secret: v.string(), account_id: v.string(), check_number: v.string(), tool: v.string() },
  handler: async (ctx, { secret, account_id, check_number, tool }) => {
    checkSecret(secret);
    const docs = await ctx.db
      .query("tickets")
      .withIndex("by_account", (q) => q.eq("account_id", account_id))
      .order("desc")
      .collect();
    return docs
      .filter((t) => t.tool === tool && t.status === "Submitted" && (t.check_numbers ?? []).includes(check_number))
      .map((t) => ({ ticket_id: t.ticket_id, advisor_id: t.advisor_id }));
  },
});

export const listTickets = query({
  args: { secret: v.string(), advisor_id: v.string() },
  handler: async (ctx, { secret, advisor_id }) => {
    checkSecret(secret);
    const docs = await ctx.db
      .query("tickets")
      .withIndex("by_advisor", (q) => q.eq("advisor_id", advisor_id))
      .order("desc")
      .take(200);
    return docs.map(plain);
  },
});

export const getAdvisorSettings = query({
  args: { secret: v.string(), advisor_id: v.string() },
  handler: async (ctx, { secret, advisor_id }) => {
    checkSecret(secret);
    const doc = await ctx.db
      .query("advisor_settings")
      .withIndex("by_advisor", (q) => q.eq("advisor_id", advisor_id))
      .first();
    return doc ? doc.settings : {};
  },
});

export const setAdvisorSetting = mutation({
  args: { secret: v.string(), advisor_id: v.string(), key: v.string(), value: v.any() },
  handler: async (ctx, { secret, advisor_id, key, value }) => {
    checkSecret(secret);
    const doc = await ctx.db
      .query("advisor_settings")
      .withIndex("by_advisor", (q) => q.eq("advisor_id", advisor_id))
      .first();
    if (doc) {
      await ctx.db.patch(doc._id, { settings: { ...(doc.settings ?? {}), [key]: value } });
    } else {
      await ctx.db.insert("advisor_settings", { advisor_id, settings: { [key]: value } });
    }
    return null;
  },
});

// Ticket attachments: the browser uploads straight to Convex file storage.
export const generateUploadUrl = mutation({
  args: { secret: v.string() },
  handler: async (ctx, { secret }) => {
    checkSecret(secret);
    return await ctx.storage.generateUploadUrl();
  },
});

export const fileMeta = query({
  args: { secret: v.string(), storage_id: v.string() },
  handler: async (ctx, { secret, storage_id }) => {
    checkSecret(secret);
    const id = ctx.db.system.normalizeId("_storage", storage_id);
    if (!id) return null;
    const doc = await ctx.db.system.get(id);
    return doc ? { size: doc.size, contentType: doc.contentType ?? "" } : null;
  },
});

// A link to one attached file, for Active Tickets -> View. The server only asks for
// it after checking that the ticket belongs to the advisor.
export const fileUrl = query({
  args: { secret: v.string(), storage_id: v.string() },
  handler: async (ctx, { secret, storage_id }) => {
    checkSecret(secret);
    const id = ctx.db.system.normalizeId("_storage", storage_id);
    if (!id) return null;
    return await ctx.storage.getUrl(id);
  },
});

// ------------------------------------------------------------------ default state and reset

// Called by the server on start-up. Saves the default cards (from cards.csv)
// if they are missing or the CSV changed, and fills an empty `cards` table.
export const ensureDefaults = mutation({
  args: {
    secret: v.string(),
    version: v.string(),
    cards: v.array(v.object(cardFields)),
    addresses: v.optional(v.array(v.object(addressFields))),
  },
  handler: async (ctx, { secret, version, cards, addresses }) => {
    checkSecret(secret);
    const saved = await ctx.db
      .query("defaults")
      .withIndex("by_key", (q) => q.eq("key", "cards"))
      .first();
    let updated = false;
    if (!saved) {
      await ctx.db.insert("defaults", { key: "cards", version, cards, addresses });
      updated = true;
    } else if (saved.version !== version) {
      await ctx.db.patch(saved._id, { version, cards, addresses });
      updated = true;
    }
    const anyCard = await ctx.db.query("cards").first();
    let seeded = false;
    if (!anyCard) {
      for (const card of cards) await ctx.db.insert("cards", card);
      seeded = true;
    }
    const anyAddress = await ctx.db.query("addresses").first();
    if (!anyAddress && addresses) {
      for (const a of addresses) await ctx.db.insert("addresses", a);
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
    // Attached files go with their tickets.
    for (const t of await ctx.db.query("tickets").collect()) {
      for (const a of t.attachments ?? []) {
        const id = ctx.db.system.normalizeId("_storage", String(a.storage_id ?? ""));
        if (id) await ctx.storage.delete(id);
      }
    }
    for (const table of ["cards", "addresses", "travel_notices", "flags", "conversations",
                       "audit_actions", "audit_chat", "audit", "tickets",
                       "advisor_settings"] as const) {
      const docs = await ctx.db.query(table).collect();
      for (const d of docs) await ctx.db.delete(d._id);
      counts[table] = docs.length;
    }
    for (const card of saved.cards) await ctx.db.insert("cards", card);
    for (const a of saved.addresses ?? []) await ctx.db.insert("addresses", a);
    return {
      cleared: counts,
      restored_cards: saved.cards.length,
      restored_addresses: (saved.addresses ?? []).length,
    };
  },
});
