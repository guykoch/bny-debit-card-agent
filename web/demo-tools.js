// DEMO ONLY — not part of the product. See demo_tools/README.md.
// Adds (1) a team passcode screen before the chat and (2) a "Demo controls" bar
// above the chat panel with a "Reset demo data" button. Loaded by index.html
// only when the server reports demo_mode or passcode_required.
(function () {
  const KEY = "dca-demo-passcode";
  let passcode = "";
  try { passcode = localStorage.getItem(KEY) || ""; } catch (e) { /* private mode */ }

  const css = `
  #demo-slot { margin-bottom: 10px; }
  .demo-bar { display: flex; align-items: center; gap: 10px; padding: 8px 12px;
    background: #FFF7E6; border: 1.5px dashed #C9A227; border-radius: 10px;
    font: 12px "Segoe UI", Calibri, Arial, sans-serif; color: #6B5310; }
  .demo-bar b { letter-spacing: .06em; font-size: 11px; }
  .demo-bar .grow { flex: 1; }
  .demo-bar button { font: inherit; font-weight: 600; cursor: pointer; border-radius: 999px;
    padding: 5px 12px; border: 1px solid #A5851F; background: #fff; color: #6B5310; }
  .demo-bar button:disabled { opacity: .6; cursor: default; }
  .demo-bar .ask { font-weight: 600; font-size: 12.5px !important; }
  .demo-bar button.go { background: #B03030; border-color: #B03030; color: #fff; }
  .demo-toast.bad { background: #B03030; }
  .demo-toast { position: fixed; left: 50%; top: 18px; transform: translateX(-50%);
    background: #2E7D5B; color: #fff; padding: 8px 16px; border-radius: 8px;
    font: 13px "Segoe UI", Calibri, Arial, sans-serif; z-index: 1001; }
  .demo-gate { position: fixed; inset: 0; background: rgba(230,235,242,.96); z-index: 1000;
    display: grid; place-items: center; font-family: "Segoe UI", Calibri, Arial, sans-serif; }
  .demo-gate form { background: #fff; border: 1px solid #D5DDE8; border-radius: 12px;
    padding: 24px; width: min(340px, calc(100vw - 32px)); box-shadow: 0 8px 28px rgba(31,45,74,.12); }
  .demo-gate h2 { margin: 0 0 4px; font-size: 18px; color: #1F2D4A; }
  .demo-gate p { margin: 0 0 14px; font-size: 13px; color: #5B6B7A; }
  .demo-gate input { width: 100%; box-sizing: border-box; font: inherit; font-size: 14px;
    padding: 9px 12px; border: 1px solid #D5DDE8; border-radius: 8px; margin-bottom: 10px; }
  .demo-gate button { width: 100%; font: inherit; font-weight: 600; font-size: 14px; padding: 9px;
    border: 0; border-radius: 8px; background: #2F5D9A; color: #fff; cursor: pointer; }
  .demo-gate .err { color: #B03030; font-size: 12.5px; min-height: 16px; margin-bottom: 6px; }
  @media (max-width: 600px) {
    #demo-slot { margin-bottom: 6px; }
    .demo-bar { padding: 6px 10px; gap: 8px; }
    .demo-bar .grow { font-size: 0; }
    .demo-gate input { font-size: 16px; }
  }`;
  const style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  function save(p) { passcode = p; try { localStorage.setItem(KEY, p); } catch (e) {} }
  function headers() { return passcode ? { "X-Demo-Passcode": passcode } : {}; }

  async function check(p) {
    try {
      const r = await fetch("/api/demo/check-passcode", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ passcode: p }) });
      return (await r.json()).ok === true;
    } catch (e) { return false; }
  }

  function showGate() {
    return new Promise(resolve => {
      const gate = document.createElement("div");
      gate.className = "demo-gate";
      gate.innerHTML = `<form><h2>Team demo</h2>
        <p>Debit card chat · enter the team passcode</p>
        <input type="password" autocomplete="current-password" placeholder="Passcode" autofocus>
        <div class="err"></div><button type="submit">Enter</button></form>`;
      document.body.appendChild(gate);
      const form = gate.querySelector("form"), inp = gate.querySelector("input"),
            err = gate.querySelector(".err");
      inp.focus();
      form.onsubmit = async ev => {
        ev.preventDefault();
        if (await check(inp.value)) { save(inp.value); gate.remove(); resolve(); }
        else { err.textContent = "That passcode is not right."; inp.select(); }
      };
    });
  }

  function toast(text, bad) {
    const t = document.createElement("div");
    t.className = "demo-toast" + (bad ? " bad" : ""); t.textContent = text;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), bad ? 5000 : 2600);
  }

  // The confirmation happens inside the bar (no browser pop-ups: iPhone Safari
  // offers "Suppress dialogs" after the first one, which would block Reset).
  function showBar() {
    const bar = document.createElement("div");
    bar.className = "demo-bar";
    const idle = () => {
      bar.innerHTML = `<b>DEMO CONTROLS</b><span class="grow">Not part of the product · shared data</span>
        <button type="button" data-a="ask">Reset demo data</button>`;
    };
    const ask = () => {
      bar.innerHTML = `<span class="grow ask">Reset all data for everyone?</span>
        <button type="button" data-a="cancel">Cancel</button>
        <button type="button" data-a="go" class="go">Yes, reset</button>`;
    };
    const go = async () => {
      bar.querySelectorAll("button").forEach(b => b.disabled = true);
      bar.querySelector(".go").textContent = "Resetting…";
      try {
        const r = await fetch("/api/demo/reset", { method: "POST", headers: headers() });
        const out = await r.json();
        if (r.status === 401) { idle(); await showGate(); return; }
        if (out.status !== "ok") throw new Error(out.message || "Reset failed");
        toast("Demo data reset to the starting state");
        window.NetXChat.newConversation();
      } catch (e) {
        toast("Reset failed: " + e.message, true);
      }
      idle();
    };
    bar.onclick = (e) => {
      const a = e.target.closest("button")?.dataset.a;
      if (a === "ask") ask(); else if (a === "cancel") idle(); else if (a === "go") go();
    };
    idle();
    document.getElementById("demo-slot").appendChild(bar);
  }

  window.DemoTools = {
    headers,
    async init(info) {
      if (info.passcode_required && !(passcode && await check(passcode))) await showGate();
      if (info.demo_mode) showBar();
      window.NetXChat.start();
    },
    async askPasscode() { save(""); await showGate(); },
  };
})();
