// Six skills deck, in the house style of BNY_Debit_Card_Chat_CheckIn.pptx
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const Fi = require("react-icons/fi");

// Run from anywhere:  PPTX_SKILL=<path to the pptx skill folder> node deliverables/build_six_skills_deck.js
// Needs: pptxgenjs, react, react-dom, react-icons, sharp, and the pptx skill's scripts/apply_theme.js.
// Reads the skill files from ../skills/debit-card/ (appendix) and writes BNY_Six_Skills.pptx next to this script.
const SKILL_DIR = process.env.PPTX_SKILL;
const { applyTheme } = require(SKILL_DIR + "/scripts/apply_theme.js");

// ---- house palette (taken from the check-in deck) ----
const K = {
  navy: "14314F", night: "0E2337", nightCard: "1B3A56", nightLine: "2E5675",
  gold: "C9A227", goldDark: "A5851F", goldTint: "FDF8E8", goldLine: "E0D3A8",
  green: "2E7D5B", greenTint: "EEF4F2", greenLine: "B9D3C6",
  red: "B03030", redTint: "FBEFEF", redLine: "E3B5B5",
  body: "3C4C5A", muted: "5B6B7A", faint: "7E8D9B",
  panel: "F2F5F8", line: "C7D2DC", line2: "DBE4EC", white: "FFFFFF",
  ice: "BFD0DE",
};
const THEME = {
  name: "BNY Check-in", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: "1F2A35", lt1: "FFFFFF", dk2: K.navy, lt2: K.panel,
    accent1: K.navy, accent2: K.gold, accent3: K.green, accent4: K.red,
    accent5: K.muted, accent6: K.nightLine, hlink: K.navy, folHlink: K.muted },
};
const HEAD = "Cambria", BODY = "Calibri", MONO = "Courier New";

async function icon(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(Comp, { color: "#" + color, size: String(size) }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";            // 13.33 x 7.5, same as the check-in deck
pres.author = "NYU Stern Tech MBA team";
pres.title = "Six skills, one chat";
pres.theme = { headFontFace: HEAD, bodyFontFace: BODY };

pres.defineSlideMaster({
  title: "Dark title", background: { color: K.night },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.75, y: 1.7, w: 11.8, h: 0.9,
      fontFace: HEAD, fontSize: 42, bold: true, color: K.white, margin: 0, valign: "middle", align: "left" },
      text: "" } },
    { placeholder: { options: { name: "sub", type: "body", x: 0.75, y: 2.65, w: 11.8, h: 0.4,
      fontFace: BODY, fontSize: 17, color: K.gold, margin: 0, align: "left" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "Content", background: { color: K.white },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.34, w: 9.6, h: 0.62,
      fontFace: HEAD, fontSize: 32, bold: true, color: K.navy, margin: 0, valign: "middle", align: "left" },
      text: "" } },
    { placeholder: { options: { name: "sub", type: "body", x: 0.6, y: 1.0, w: 12.1, h: 0.34,
      fontFace: BODY, fontSize: 14, color: K.muted, margin: 0, valign: "middle", align: "left" }, text: "" } },
    { placeholder: { options: { name: "foot", type: "body", x: 0.6, y: 6.92, w: 12.1, h: 0.3,
      fontFace: BODY, fontSize: 11, italic: true, color: K.faint, margin: 0, valign: "middle" },
      text: "" } },
  ],
  slideNumber: { x: 12.13, y: 6.92, w: 0.6, h: 0.3, fontFace: BODY, fontSize: 10, color: K.faint, align: "right" },
});

// ---------- small helpers ----------
const T = (s, text, o) => s.addText(text, { isTextBox: true, margin: 0, fontFace: BODY,
  color: K.body, fontSize: 13, valign: "top", ...o });
const box = (s, o) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { rectRadius: 0.08, ...o });

// rough text height: Calibri averages ~0.5em per character
function lines(text, wIn, pt) {
  const perLine = Math.floor((wIn * 72) / (pt * 0.47));
  return text.split("\n").reduce((n, para) => n + Math.max(1, Math.ceil(para.length / perLine)), 0);
}
const lh = (pt) => (pt * 1.22) / 72;

function sectionLabel(s, img, label, x, y, color) {
  s.addShape(pres.shapes.OVAL, { x, y, w: 0.34, h: 0.34, fill: { color },
    line: { color, width: 0 }, objectName: "icon circle " + label });
  s.addImage({ data: img, x: x + 0.08, y: y + 0.08, w: 0.18, h: 0.18 });
  T(s, label, { x: x + 0.46, y: y + 0.02, w: 5, h: 0.3, fontSize: 11, bold: true,
    color, charSpacing: 1.5, valign: "middle" });
}

function chips(s, items, x, y, wMax, style) {
  // items: strings; style: {fill, line, color, dash, font}
  let cx = x, cy = y;
  const h = 0.36, gap = 0.12, pt = style.pt || 12.5;
  for (const it of items) {
    const w = it.length * pt * 0.52 / 72 + 0.34;
    if (cx + w > x + wMax) { cx = x; cy += h + 0.1; }
    box(s, { x: cx, y: cy, w, h, rectRadius: 0.18, fill: { color: style.fill },
      line: { color: style.line, width: 1, dashType: style.dash || "solid" } });
    T(s, it, { x: cx, y: cy, w, h, align: "center", valign: "middle", fontSize: pt,
      color: style.color, fontFace: style.font || BODY, italic: !!style.italic });
    cx += w + gap;
  }
  return cy + h;
}

// ---------- the chat mock-up, styled after the NetX AI panel ----------
// msgs: {who:"adv"|"bot"|"choice"|"confirm"|"done", ...}
const N = { bg: "F5F8FC", border: "D5DDE8", pill: "DCE6F4", text: "2B2F36", icon: "4A4F57",
  blue: "2F5D9A", head: "1F2D4A", card: "FFFFFF", cardLine: "D5DDE8", pick: "E8EFF9",
  hint: "8A93A0", tab: "1F2D4A" };

function iconRow(s, ico, x, y) {
  [ico.copy, ico.dl, ico.redo, ico.vol].forEach((im, i) =>
    s.addImage({ data: im, x: x + i * 0.32, y, w: 0.17, h: 0.17 }));
  return 0.27;
}

function chat(s, msgs, ico) {
  const X = 6.95, Y = 1.5, W = 5.78, H = 5.3;
  box(s, { x: X, y: Y, w: W, h: H, rectRadius: 0.1, fill: { color: N.bg },
    line: { color: N.border, width: 1 }, objectName: "NetX AI panel" });

  // header: sparkle + "NetX AI" on the left, menu + expand on the right
  s.addImage({ data: ico.spark, x: X + 0.22, y: Y + 0.15, w: 0.2, h: 0.2 });
  T(s, "NetX AI", { x: X + 0.48, y: Y + 0.11, w: 2, h: 0.28, fontSize: 13, bold: true,
    color: N.head, valign: "middle" });
  s.addImage({ data: ico.more, x: X + W - 0.78, y: Y + 0.16, w: 0.18, h: 0.18 });
  s.addImage({ data: ico.expand, x: X + W - 0.45, y: Y + 0.16, w: 0.18, h: 0.18 });

  // "Guide Me" tab on the right edge
  box(s, { x: X + W - 0.2, y: Y + 2.0, w: 0.26, h: 0.95, rectRadius: 0.05,
    fill: { color: N.tab }, line: { color: N.tab, width: 0 } });
  T(s, "Guide Me", { x: X + W - 0.555, y: Y + 2.36, w: 0.95, h: 0.24, rotate: 90, align: "center",
    valign: "middle", fontSize: 9, bold: true, color: K.white });

  // input box + disclaimer at the bottom
  const ibH = 0.42, ibY = Y + H - 0.36 - ibH;
  box(s, { x: X + 0.2, y: ibY, w: W - 0.5, h: ibH, rectRadius: 0.1, fill: { color: K.white },
    line: { color: N.border, width: 1 } });
  s.addImage({ data: ico.plus, x: X + 0.34, y: ibY + 0.12, w: 0.18, h: 0.18 });
  T(s, "Ask NetX AI", { x: X + 0.62, y: ibY, w: 3, h: ibH, fontSize: 11, color: N.hint, valign: "middle" });
  s.addImage({ data: ico.mic, x: X + W - 1.02, y: ibY + 0.12, w: 0.18, h: 0.18 });
  s.addShape(pres.shapes.OVAL, { x: X + W - 0.72, y: ibY + 0.06, w: 0.3, h: 0.3,
    fill: { color: N.blue }, line: { color: N.blue, width: 0 } });
  s.addImage({ data: ico.send, x: X + W - 0.65, y: ibY + 0.13, w: 0.16, h: 0.16 });
  T(s, "Please note: AI can make mistakes. All data shown here is synthetic.",
    { x: X + 0.2, y: ibY + ibH + 0.06, w: W - 0.5, h: 0.24, fontSize: 9, color: N.hint,
      align: "center", valign: "middle" });

  const inX = X + 0.25, inW = W - 0.62, pt = 12;
  let y = Y + 0.6;
  const G = 0.1, last = msgs.length - 1;

  msgs.forEach((m, idx) => {
    if (m.who === "adv") {
      const bw = Math.min(inW * 0.8, Math.max(0.9, m.text.length * pt * 0.48 / 72 + 0.4));
      const bh = lines(m.text, bw - 0.36, pt) * lh(pt) + 0.18;
      box(s, { x: inX + inW - bw, y, w: bw, h: bh, rectRadius: Math.min(0.17, bh / 2),
        fill: { color: N.pill }, line: { color: N.pill, width: 0 } });
      T(s, m.text, { x: inX + inW - bw + 0.18, y, w: bw - 0.36, h: bh, valign: "middle",
        fontSize: pt, color: N.text });
      y += bh + G;
    } else if (m.who === "bot") {
      const th = lines(m.text, inW, pt) * lh(pt);
      T(s, m.text, { x: inX, y, w: inW, h: th, fontSize: pt, color: N.text });
      y += th + 0.08;
      if (idx === last) y += iconRow(s, ico, inX, y);
      y += G;
    } else if (m.who === "choice") {
      const bw = inW * 0.94, rowH = 0.34;
      const bh = 0.12 + lh(pt) + 0.1 + rowH + 0.14;
      box(s, { x: inX, y, w: bw, h: bh, rectRadius: 0.08, fill: { color: N.card },
        line: { color: N.cardLine, width: 1 } });
      T(s, m.q, { x: inX + 0.15, y: y + 0.12, w: bw - 0.3, h: lh(pt), fontSize: pt, bold: true,
        color: N.head, valign: "middle" });
      const oy = y + 0.12 + lh(pt) + 0.1, ow = (bw - 0.3 - 0.12) / m.options.length;
      m.options.forEach((o, i) => {
        const picked = m.pick === i, ox = inX + 0.15 + i * (ow + 0.12);
        box(s, { x: ox, y: oy, w: ow, h: rowH, rectRadius: 0.06,
          fill: { color: picked ? N.pick : K.white },
          line: { color: picked ? N.blue : N.cardLine, width: picked ? 1.5 : 1 } });
        T(s, o, { x: ox, y: oy, w: ow, h: rowH, align: "center", valign: "middle", fontSize: 11.5,
          color: N.blue, bold: picked });
      });
      y += bh + G;
    } else if (m.who === "confirm") {
      const bw = inW * 0.94;
      const tl = lines(m.text, bw - 0.3, pt);
      const warnH = m.warn ? lines(m.warn, bw - 0.3, 11.5) * lh(11.5) + 0.04 : 0;
      const bh = 0.13 + tl * lh(pt) + warnH + 0.12 + 0.34 + 0.14;
      box(s, { x: inX, y, w: bw, h: bh, rectRadius: 0.08, fill: { color: N.card },
        line: { color: m.danger ? K.redLine : N.cardLine, width: 1 } });
      T(s, m.text, { x: inX + 0.15, y: y + 0.12, w: bw - 0.3, h: tl * lh(pt) + 0.04, fontSize: pt,
        color: N.head, bold: true });
      let by = y + 0.13 + tl * lh(pt);
      if (m.warn) {
        T(s, m.warn, { x: inX + 0.15, y: by + 0.02, w: bw - 0.3, h: warnH, fontSize: 11.5,
          color: m.danger ? K.red : K.muted, italic: true });
        by += warnH;
      }
      by += 0.12;
      const buttons = [[m.button || "Confirm", "primary"], ...(m.extra || []).map((e) => [e, "alt"]),
        ["Cancel", "plain"]];
      let bx = inX + 0.15;
      for (const [label, kind] of buttons) {
        const w = label.length * 11.5 * 0.5 / 72 + 0.4;
        const fillC = kind === "primary" ? (m.danger ? K.red : N.blue) : K.white;
        box(s, { x: bx, y: by, w, h: 0.34, rectRadius: 0.17, fill: { color: fillC },
          line: { color: kind === "plain" ? N.cardLine : (m.danger && kind === "primary" ? K.red : N.blue),
            width: 1 } });
        T(s, label, { x: bx, y: by, w, h: 0.34, align: "center", valign: "middle", fontSize: 11.5,
          bold: kind !== "plain", color: kind === "primary" ? K.white : (kind === "alt" ? N.blue : K.muted) });
        bx += w + 0.12;
      }
      if (!m.extra) T(s, "nothing has run yet", { x: bx + 0.05, y: by, w: 1.8, h: 0.34, fontSize: 10,
        italic: true, color: N.hint, valign: "middle" });
      y += bh + G;
    } else if (m.who === "done") {
      s.addImage({ data: ico.check, x: inX, y: y + 0.02, w: 0.2, h: 0.2 });
      T(s, m.text, { x: inX + 0.3, y, w: inW - 0.3, h: lh(pt), fontSize: pt, bold: true,
        color: K.green, valign: "middle" });
      y += lh(pt) + 0.08;
      if (idx === last) y += iconRow(s, ico, inX, y);
      y += G;
    }
  });
  const limit = ibY - 0.06;
  console.log(`chat ends ${y.toFixed(2)} / ${limit.toFixed(2)}`);
  if (y > limit + 0.01) console.log("OVERFLOW", msgs[0].text);
}

// ---------- one skill slide ----------
function skillSlide(sp, ico) {
  const s = pres.addSlide({ masterName: "Content", sectionTitle: "The six skills" });
  s.addText(sp.title, { placeholder: "title" });
  s.addText(sp.sub, { placeholder: "sub" });
  s.addText(sp.foot, { placeholder: "foot" });

  // tag pill, top right
  const tc = { green: [K.greenTint, K.green], red: [K.redTint, K.red], gold: [K.goldTint, K.goldDark] }[sp.tag[1]];
  const tw = sp.tag[0].length * 12 * 0.55 / 72 + 0.5;
  box(s, { x: 12.73 - tw, y: 0.46, w: tw, h: 0.4, rectRadius: 0.2, fill: { color: tc[0] },
    line: { color: tc[1], width: 1.25 } });
  T(s, sp.tag[0], { x: 12.73 - tw, y: 0.46, w: tw, h: 0.4, align: "center", valign: "middle",
    fontSize: 12, bold: true, color: tc[1] });

  const X = 0.6, W = 5.95;
  // what it does
  sectionLabel(s, ico.zap, "WHAT IT DOES", X, 1.6, K.navy);
  T(s, sp.does, { x: X, y: 2.02, w: W, h: 0.62, fontFace: HEAD, fontSize: 17, color: K.navy });

  // advisor might say  (sections flow down, so a wrapped chip row never collides)
  sectionLabel(s, ico.say, "THE ADVISOR MIGHT SAY", X, 2.78, K.goldDark);
  let cy = chips(s, sp.says.map((q) => `“${q}”`), X, 3.2, W,
    { fill: K.goldTint, line: K.goldLine, color: K.body, italic: true });

  // what the chat needs
  const needY = cy + 0.24;
  sectionLabel(s, ico.list, "WHAT THE CHAT NEEDS BEFORE IT ACTS", X, needY, K.navy);
  let ny = chips(s, sp.needs, X, needY + 0.42, W, { fill: K.white, line: K.navy, color: K.navy });
  if (sp.optional) {
    T(s, sp.optional, { x: X, y: ny + 0.06, w: W, h: 0.26, fontSize: 11, italic: true, color: K.faint });
    ny += 0.32;
  }
  if (ny > 4.95) console.log("LEFT COLUMN OVERFLOW", sp.title, ny.toFixed(2));

  // safety
  const sy = 5.02, sh = 1.72;
  box(s, { x: X, y: sy, w: W, h: sh, rectRadius: 0.1, fill: { color: K.greenTint },
    line: { color: K.greenLine, width: 1 } });
  sectionLabel(s, ico.shield, "BUILT-IN SAFETY", X + 0.2, sy + 0.16, K.green);
  const bullets = sp.safety.map((t, i) => ({ text: t, options: {
    bullet: { indent: 14 }, breakLine: i < sp.safety.length - 1, paraSpaceAfter: 5 } }));
  T(s, bullets, { x: X + 0.25, y: sy + 0.6, w: W - 0.45, h: sh - 0.7, fontSize: 13, color: K.body });

  chat(s, sp.chat, ico);
  s.addNotes(sp.notes);
}

// ================= content =================
const SKILLS = [
  {
    title: "Lock card", tag: ["Reversible", "green"],
    sub: "Freeze a card for now: the client misplaced it, or wants to pause spending.",
    does: "Temporarily blocks the card. One click on Unlock undoes it.",
    says: ["lock", "freeze", "block the card", "suspend"],
    needs: ["Client", "Card"], optional: "Optional: a reason, stored on the audit record.",
    safety: [
      "Client has two cards? It lists both and asks. It never picks one.",
      "Mentions of a lost or stolen card? It suggests Report lost or stolen instead.",
      "Already locked? It says so and does nothing.",
    ],
    chat: [
      { who: "adv", text: "Lock Robert Castellano’s card" },
      { who: "choice", q: "Which card? Robert has two.", options: ["…2201 (active)", "…2202 (active)"], pick: 1 },
      { who: "adv", text: "2202" },
      { who: "confirm", text: "Lock the debit card ending 2202 for Robert Castellano (account ...1022)?" },
      { who: "done", text: "Card ending 2202 is locked." },
    ],
    foot: "The advisor can click an option or just type “2”, “2202” or “the one ending 2202”. All three work, and anything unclear is asked again.",
    notes: "Lock is the simplest skill, so we use it to show the question every skill asks when there is more than one card. Robert Castellano has two active cards in our test data. The chat lists both and waits. It does not guess. The advisor can click or type the last four digits. Then the chat restates the action in one line, and nothing happens until Confirm. Lock is reversible, which is why its confirmation is the lightest of the six.",
  },
  {
    title: "Unlock card", tag: ["Reversible", "green"],
    sub: "Turn a locked card back on: the wallet turned up, or the pause is over.",
    does: "Removes a temporary lock, so the card works again.",
    says: ["unlock", "unblock", "reactivate", "turn it back on"],
    needs: ["Client", "Card"],
    safety: [
      "Two clients with the same name? It lists both and asks.",
      "Card closed rather than locked? It says a replacement is needed.",
      "Card not locked? It says so and does nothing.",
    ],
    chat: [
      { who: "adv", text: "Unlock Sarah Chen’s card" },
      { who: "choice", q: "Two clients match that name. Which one?", options: ["Sarah Chen …4409", "Sarah M. Chen …4410"], pick: 0 },
      { who: "adv", text: "4409" },
      { who: "confirm", text: "Unlock the debit card ending 9902 for Sarah Chen (account ...4409)?" },
      { who: "done", text: "Card ending 9902 is unlocked." },
    ],
    foot: "The list only shows clients this advisor may see. A third Sarah Chen exists in our test data but belongs to another advisor, so she never appears.",
    notes: "Unlock mirrors lock. The example shows the other common question: two clients with the same name. The chat lists both with the last four digits of the account and waits. Our test data has a third Sarah Chen who belongs to a different advisor. She is filtered out before the list is built, so this advisor never learns she exists.",
  },
  {
    title: "Replace card", tag: ["Issues a new card", "gold"],
    sub: "Damaged, worn out or expiring: cancel this card and mail a new one.",
    does: "Cancels the current card and sends a replacement to an address the advisor confirms.",
    says: ["new card", "reissue", "damaged", "cracked"],
    needs: ["Client", "Card", "Reason", "Delivery address"],
    optional: "Reason is one of: damaged, lost, stolen, expiring, other.",
    safety: [
      "It never guesses the reason. If the advisor did not say, it asks.",
      "It shows the address on file and asks before mailing anything.",
      "Lost or stolen? It offers Report lost or stolen first.",
    ],
    chat: [
      { who: "adv", text: "Jane Miller’s card is cracked, send her a new one" },
      { who: "bot", text: "Send it to 14 Hudson St, New York, NY 10013, the address on file?" },
      { who: "adv", text: "Yes" },
      { who: "confirm", text: "Replace the card ending 4417 for Jane Miller. Reason: damaged. Deliver to 14 Hudson St." },
      { who: "done", text: "Replacement ordered. The card ending 4417 is cancelled." },
    ],
    foot: "“Cracked” clearly means damaged, so the chat does not ask. If the advisor only said “send her a new card”, it would ask why.",
    notes: "Replace has four fields, so it shows how the chat collects them without a form. The client and card are found as usual. The reason is taken from the sentence only when it is explicit: cracked means damaged. The address is never assumed. The chat shows the one on file and asks the advisor to confirm or change it. A card mailed to the wrong address is a real risk, so this is a deliberate extra step.",
  },
  {
    title: "Close card permanently", tag: ["Cannot be undone", "red"],
    sub: "The client is done with this card for good.",
    does: "Shuts the card permanently. It cannot be reopened; only a new card can replace it.",
    says: ["close permanently", "terminate", "shut the card"],
    needs: ["Client", "Card", "Reason"],
    safety: [
      "Vague words like “cancel” or “stop”? It asks: lock or close?",
      "Its confirmation spells out that this cannot be undone.",
      "Already closed? It says so and does nothing.",
    ],
    chat: [
      { who: "adv", text: "Cancel Jane Miller’s card" },
      { who: "choice", q: "Lock it for now, or close it permanently?", options: ["Lock (reversible)", "Close permanently"], pick: 1 },
      { who: "adv", text: "Close it, she switched banks" },
      { who: "confirm", danger: true, button: "Close card", text: "Permanently close the card ending 4417 for Jane Miller?",
        warn: "This cannot be undone. A new card would have to be issued." },
    ],
    foot: "This is the one action that cannot be reversed, so it gets the strictest wording and the red button.",
    notes: "Close is the only irreversible action, so it is the most careful skill. Advisors and clients say 'cancel the card' loosely, and that could mean lock or close. The chat asks rather than picking the more drastic option. The confirmation panel is red and states plainly that it cannot be undone. Open question for Ben: is BNY's entitlement check at action level? An advisor may be allowed to lock but not to close.",
  },
  {
    title: "Report lost or stolen", tag: ["Blocks + flags the account", "gold"],
    sub: "The urgent call: “I’ve lost my wallet.”",
    does: "Blocks the card and flags the account for review, in one step.",
    says: ["lost", "stolen", "wallet", "pickpocket"],
    needs: ["Client", "Card", "Lost or stolen?"],
    optional: "Optional: last known use, and whether there are charges the client does not recognise.",
    safety: [
      "It never assumes lost or stolen from the wording. It asks.",
      "It does not judge which charges look suspicious. The client says.",
      "Afterwards it offers the natural next step: a replacement.",
    ],
    chat: [
      { who: "adv", text: "Jane Miller lost her wallet" },
      { who: "bot", text: "Lost, or stolen? And are there any charges she doesn’t recognise?" },
      { who: "adv", text: "Lost. No odd charges." },
      { who: "confirm", text: "Report the card ending 4417 for Jane Miller as lost and flag the account?" },
      { who: "done", text: "Card blocked and account flagged." },
      { who: "bot", text: "Would you like me to order a replacement?" },
    ],
    foot: "This is the scenario from our interview with Jonathan: the client is on the phone and wants it handled now.",
    notes: "This is the most urgent skill and the one advisors described most often. Lost and stolen are treated differently downstream, so the chat asks which rather than guessing from 'wallet'. It also asks about unrecognised charges, but it never decides which charges look suspicious. That is the client's call. When it is done, it offers the replacement. Each action is still confirmed separately, one card at a time.",
  },
  {
    title: "Travel notice", tag: ["The hardest of the six", "gold"],
    sub: "Tell the bank about a trip, so the card is not declined abroad.",
    does: "Records where and when the client is travelling.",
    says: ["travel", "trip", "going to", "abroad"],
    needs: ["Client", "Card", "Destination", "Start date", "End date"],
    safety: [
      "Ambiguous place? It asks. “Georgia” could be the US state or the country.",
      "It shows the dates it worked out before using them.",
      "End before start, or a trip over 90 days? It says so and asks.",
    ],
    chat: [
      { who: "adv", text: "Jane Miller is off to Georgia next month for a couple of weeks" },
      { who: "bot", text: "Georgia the country, or the US state?" },
      { who: "adv", text: "The country" },
      { who: "confirm", extra: ["Change dates"],
        text: "Travel notice, card ending 4417: Georgia (country), 1–15 November?",
        warn: "Dates read from “next month for a couple of weeks”." },
      { who: "done", text: "Travel notice added." },
    ],
    foot: "Dates the chat worked out are shown on the confirmation, with their source. “Change dates” lets the advisor correct them before anything runs.",
    notes: "Travel notice is the hardest skill because the inputs are vague. 'Next month for a couple of weeks' becomes real dates, and the chat shows its working instead of submitting a guess. Place names can be ambiguous: Georgia, Springfield, Victoria. The chat asks rather than picking the more common one. The confirmation shows the dates it worked out and where they came from, with a Change dates button, so the advisor can correct them before anything runs. It only asks for the fields still missing.",
  },
];

(async () => {
  const ico = {
    chat: await icon(Fi.FiMessageSquare, K.muted),
    spark: await icon(require("react-icons/hi").HiOutlineSparkles, "3A73C9"),
    more: await icon(Fi.FiMoreVertical, "2B2F36"), expand: await icon(Fi.FiMaximize2, "2B2F36"),
    copy: await icon(Fi.FiCopy, "4A4F57"), dl: await icon(Fi.FiDownload, "4A4F57"),
    redo: await icon(Fi.FiRefreshCw, "4A4F57"), vol: await icon(Fi.FiVolume2, "4A4F57"),
    plus: await icon(Fi.FiPlus, "2F5D9A"), mic: await icon(Fi.FiMicOff, "8A93A0"),
    send: await icon(Fi.FiArrowUp, "FFFFFF"),
    check: await icon(Fi.FiCheckCircle, K.green),
    zap: await icon(Fi.FiZap, K.white),
    say: await icon(Fi.FiMessageCircle, K.white),
    list: await icon(Fi.FiClipboard, K.white),
    shield: await icon(Fi.FiShield, K.white),
    lock: await icon(Fi.FiLock, K.gold), unlock: await icon(Fi.FiUnlock, K.gold),
    refresh: await icon(Fi.FiRefreshCw, K.gold), x: await icon(Fi.FiXCircle, K.gold),
    alert: await icon(Fi.FiAlertTriangle, K.gold), plane: await icon(Fi.FiGlobe, K.gold),
    users: await icon(Fi.FiUsers, K.navy), card: await icon(Fi.FiCreditCard, K.navy),
    help: await icon(Fi.FiHelpCircle, K.navy), cal: await icon(Fi.FiCalendar, K.navy),
  };

  // ---------- 1. title ----------
  pres.addSection({ title: "Introduction" });
  let s = pres.addSlide({ masterName: "Dark title", sectionTitle: "Introduction" });
  s.addText("Six skills, one chat", { placeholder: "title" });
  s.addText("BNY Pershing  ·  NetX360, advisor side  ·  How each debit card action works", { placeholder: "sub" });
  const six = [["Lock card", ico.lock], ["Unlock card", ico.unlock], ["Replace card", ico.refresh],
    ["Close permanently", ico.x], ["Report lost or stolen", ico.alert], ["Travel notice", ico.plane]];
  six.forEach(([name, im], i) => {
    const x = 0.75 + (i % 3) * 3.0, y = 3.55 + Math.floor(i / 3) * 0.85;
    box(s, { x, y, w: 2.8, h: 0.65, rectRadius: 0.08, fill: { color: K.nightCard },
      line: { color: K.nightLine, width: 1 } });
    s.addImage({ data: im, x: x + 0.2, y: y + 0.2, w: 0.25, h: 0.25 });
    T(s, name, { x: x + 0.58, y, w: 2.15, h: 0.65, valign: "middle", fontSize: 15, color: K.white });
  });
  T(s, "One skill per action. Each one knows what to ask, what to refuse, and what to confirm.",
    { x: 0.75, y: 5.6, w: 11.5, h: 0.4, fontSize: 15, italic: true, color: K.ice });
  s.addNotes("This deck takes the six actions agreed with Ben one at a time. Each slide answers the same four questions: what the skill does, what an advisor might type, what the chat needs before it acts, and what stops it from doing the wrong thing. On the right of each slide is a sample conversation using our test data.");

  // ---------- 2. shared steps ----------
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Introduction" });
  s.addText("Every skill follows the same five steps", { placeholder: "title" });
  s.addText("These rules are written once, in a shared file, so all six skills behave the same way.", { placeholder: "sub" });
  s.addText("Steps 1–3 are where the chat asks questions. Step 4 is where the advisor stays in control. Nothing reaches the card system before it.", { placeholder: "foot" });
  const steps = [
    ["Find the client", "Matches the name to one client the advisor may see"],
    ["Find the card", "Picks it automatically only if there is exactly one"],
    ["Fill the gaps", "Asks only for what is still missing"],
    ["Restate and wait", "One line, then a Confirm button"],
    ["Act and report", "One sentence back, and an audit record"],
  ];
  const colors = [K.navy, K.navy, K.navy, K.gold, K.green];
  steps.forEach(([h, d], i) => {
    const cx = 0.6 + i * 2.48, cy = 1.65;
    s.addShape(pres.shapes.OVAL, { x: cx + 0.55, y: cy, w: 1.0, h: 1.0, fill: { color: colors[i] },
      line: { color: colors[i], width: 0 } });
    T(s, String(i + 1), { x: cx + 0.55, y: cy, w: 1.0, h: 1.0, align: "center", valign: "middle",
      fontFace: HEAD, fontSize: 30, bold: true, color: K.white });
    if (i < 4) T(s, "→", { x: cx + 1.75, y: cy + 0.25, w: 0.6, h: 0.5, align: "center",
      valign: "middle", fontSize: 24, color: K.faint });
    T(s, h, { x: cx, y: cy + 1.15, w: 2.1, h: 0.35, align: "center", fontSize: 15, bold: true, color: K.navy });
    T(s, d, { x: cx, y: cy + 1.5, w: 2.1, h: 0.6, align: "center", fontSize: 12.5, color: K.muted });
  });
  T(s, "WHEN IT ASKS INSTEAD OF GUESSING", { x: 0.6, y: 4.05, w: 8, h: 0.3, fontSize: 11, bold: true,
    color: K.goldDark, charSpacing: 1.5 });
  const asks = [
    [ico.users, "Two clients share a name", "“Sarah Chen, account ...4409, or Sarah M. Chen, ...4410?”"],
    [ico.card, "The client has two cards", "“The card ending 2201 or 2202?”"],
    [ico.help, "The wording is vague", "“Cancel her card” → lock it, or close it for good?"],
    [ico.cal, "A date or place is fuzzy", "“Next month” → “1 to 15 November, correct?”"],
  ];
  asks.forEach(([im, h, d], i) => {
    const x = 0.6 + i * 3.06, y = 4.45, w = 2.88, hh = 1.95;
    box(s, { x, y, w, h: hh, rectRadius: 0.1, fill: { color: K.goldTint }, line: { color: K.goldLine, width: 1 } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.22, y: y + 0.22, w: 0.5, h: 0.5, fill: { color: K.white },
      line: { color: K.goldLine, width: 1 } });
    s.addImage({ data: im, x: x + 0.34, y: y + 0.34, w: 0.26, h: 0.26 });
    T(s, h, { x: x + 0.22, y: y + 0.88, w: w - 0.44, h: 0.32, fontSize: 14, bold: true, color: K.navy });
    T(s, d, { x: x + 0.22, y: y + 1.24, w: w - 0.44, h: 0.85, fontSize: 12.5, italic: true, color: K.body });
  });
  s.addNotes("Before the individual skills: the five steps are the same for all six, and they live in one shared file. That is what keeps six skills from drifting apart. The chat only acts on one card at a time, and nothing reaches the card system until the advisor clicks Confirm. The bottom row shows the four situations where the chat stops and asks. These are the cases a careless chatbot would guess at.");

  // ---------- 3–8. the six skills ----------
  pres.addSection({ title: "The six skills" });
  for (const sp of SKILLS) skillSlide(sp, ico);

  // ---------- 9. at a glance ----------
  pres.addSection({ title: "Summary" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Summary" });
  s.addText("The six at a glance", { placeholder: "title" });
  s.addText("Same five steps for all six. What differs is how much each one asks, and how much can be undone.", { placeholder: "sub" });
  s.addText("Every action, including refusals, is written to the audit record.", { placeholder: "foot" });
  const hdr = (t) => ({ text: t, options: { bold: true, color: K.white, fill: { color: K.navy }, fontSize: 12.5 } });
  const undo = (t, c) => ({ text: t, options: { bold: true, color: c } });
  const rows = [
    [hdr("Skill"), hdr("Can it be undone?"), hdr("Extra question it may ask"), hdr("Fields")],
    ["Lock card", undo("Yes, with Unlock", K.green), "Lost or stolen? Then report it instead", "2"],
    ["Unlock card", undo("Yes, with Lock", K.green), "None beyond client and card", "2"],
    ["Replace card", undo("No, a new card is mailed", K.goldDark), "Why? And confirm the delivery address", "4"],
    ["Close permanently", undo("No, never", K.red), "Lock it, or close it for good?", "3"],
    ["Report lost or stolen", undo("No, it stays blocked until replaced", K.goldDark), "Lost or stolen? Any charges she doesn’t recognise?", "3"],
    ["Travel notice", undo("Ends by itself after the trip", K.green), "Which place? Are these the right dates?", "5"],
  ];
  s.addTable(rows, { x: 0.6, y: 1.65, w: 12.13, colW: [2.6, 3.0, 5.33, 1.2], rowH: 0.62,
    fontFace: BODY, fontSize: 13, color: K.body, valign: "middle", margin: [0, 0.15, 0, 0.15],
    border: { type: "solid", pt: 0.75, color: K.line2 }, fill: { color: K.white } });
  s.addNotes("A summary for discussion. The two columns that matter for Ben are 'can it be undone' and the extra questions. Close permanently is the one irreversible action, which is why it has the strictest confirmation. This also connects to the open question about whether BNY checks entitlement per client or per action. Note that cancelling a travel notice is one of our suggested additions, not yet agreed.");


  // ---------- appendix: the skill files, verbatim ----------
  const fs = require("fs");
  const SK = require("path").join(__dirname, "..", "skills", "debit-card") + "/";
  const FILES = [
    ["Shared rules", "_shared.md", "Prepended to every skill before the model sees it"],
    ["Lock card", "lock-card/SKILL.md"], ["Unlock card", "unlock-card/SKILL.md"],
    ["Replace card", "replace-card/SKILL.md"], ["Close card permanently", "close-card/SKILL.md"],
    ["Report lost or stolen", "report-lost-stolen/SKILL.md"], ["Travel notice", "travel-notice/SKILL.md"],
  ];
  pres.addSection({ title: "Appendix" });
  s = pres.addSlide({ masterName: "Dark title", sectionTitle: "Appendix" });
  s.addText("Appendix", { placeholder: "title" });
  s.addText("The skill files, word for word", { placeholder: "sub" });
  FILES.forEach(([name, path], i) => {
    const y = 3.35 + i * 0.44;
    T(s, name, { x: 0.75, y, w: 3.2, h: 0.36, fontSize: 15, bold: true, color: K.white, valign: "middle" });
    T(s, "skills/debit-card/" + path, { x: 4.0, y, w: 7.5, h: 0.36, fontSize: 13, fontFace: MONO,
      color: K.ice, valign: "middle" });
  });
  s.addNotes("The appendix reproduces the seven skill files exactly as they are in the repository: the shared rules first, then one file per action. These files are the whole of the instructions the model receives.");

  const CPT = 10, CLH = (CPT * 1.18) / 72, COLW = 5.95, COLH = 5.38, CHARS = Math.floor((COLW - 0.3) * 72 / (CPT * 0.6));
  const cap = Math.floor((COLH - 0.25) / CLH);
  const wrapped = (l) => Math.max(1, Math.ceil(l.length / CHARS));
  for (const [name, path, why] of FILES) {
    const raw = fs.readFileSync(SK + path, "utf8").replace(/\s+$/, "");
    // Reflow: the files are hard-wrapped at ~80 characters. Join those continuation
    // lines so text wraps at the column width instead. Words are unchanged.
    const all = []; let fm = raw.startsWith("---") ? 0 : 2;   // 2 = no front matter, or past it
    for (const l of raw.split("\n")) {
      if (l.trim() === "---" && fm < 2) fm++;
      const prev = all.length ? all[all.length - 1] : null;
      const starts = /^\s*([-*]\s|#|>|\||---|\d+\.\s)/.test(l) || /^\*\*/.test(l);
      const prevStops = prev === null || prev.trim() === "" || /^(#|\||---)/.test(prev) || fm < 2;
      if (l.trim() !== "" && !starts && !prevStops) all[all.length - 1] = prev + " " + l.trim();
      else all.push(l);
    }
    const blocks = []; let cur = [];
    for (const l of all) { cur.push(l); if (l.trim() === "") { blocks.push(cur); cur = []; } }
    if (cur.length) blocks.push(cur);
    for (let i = blocks.length - 2; i >= 0; i--) {          // a heading travels with what follows it
      if (blocks[i].filter((l) => l.trim()).every((l) => /^#/.test(l))) {
        blocks.splice(i, 2, blocks[i].concat(blocks[i + 1]));
      }
    }
    const cols = [[]]; let used = 0;
    for (const b of blocks) {
      const h = b.reduce((n, l) => n + wrapped(l), 0);
      if (used + h > cap && cols[cols.length - 1].length) { cols.push([]); used = 0; }
      cols[cols.length - 1].push(...b); used += h;
    }
    const pages = [];
    for (let i = 0; i < cols.length; i += 2) pages.push(cols.slice(i, i + 2));
    let inFront = false, fmCount = 0;
    const styled = (l) => {
      if (l.trim() === "---" && fmCount < 2) { fmCount++; inFront = fmCount === 1; return { color: K.faint }; }
      if (inFront) return { color: K.green };
      if (/^#/.test(l)) return { color: K.navy, bold: true };
      if (/^>/.test(l)) return { color: K.goldDark };
      if (/^\|/.test(l)) return { color: K.muted };
      return { color: K.body };
    };
    pages.forEach((pg, pi) => {
      const sl = pres.addSlide({ masterName: "Content", sectionTitle: "Appendix" });
      sl.addText(`Appendix · ${name}` + (pages.length > 1 ? ` (${pi + 1} of ${pages.length})` : ""), { placeholder: "title" });
      sl.addText("skills/debit-card/" + path + (why ? `  ·  ${why}` : ""), { placeholder: "sub" });
      sl.addText("Full text from the repository, word for word. Only line breaks were adjusted to fit the columns.", { placeholder: "foot" });
      pg.forEach((col, ci) => {
        const x = 0.6 + ci * (COLW + 0.23);
        box(sl, { x, y: 1.45, w: COLW, h: COLH, rectRadius: 0.06, fill: { color: "F7F9FB" },
          line: { color: K.line2, width: 1 } });
        while (col.length && col[col.length - 1].trim() === "") col.pop();
        const runs = col.map((l, i) => ({ text: l.replace(/^ +/, (m) => " ".repeat(m.length)) || " ",
          options: { ...styled(l), breakLine: i < col.length - 1 } }));
        T(sl, runs, { x: x + 0.15, y: 1.57, w: COLW - 0.3, h: COLH - 0.2, fontFace: MONO, fontSize: CPT,
          lineSpacingMultiple: 1.0, fit: "none" });
      });
      sl.addNotes(`Full text of ${path}, page ${pi + 1} of ${pages.length}.`);
    });
  }

  const out = require("path").join(__dirname, "BNY_Six_Skills.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
})().catch((e) => { console.error(e); process.exit(1); });
