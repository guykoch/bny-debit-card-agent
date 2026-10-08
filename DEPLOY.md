# Deploying the team demo (Vercel + Convex)

**What you get:** one link your teammates open in a browser. They enter the team
passcode, chat with the agent (GPT-5.4), and can press **Reset demo data** to put
everything back to the starting state. Everyone shares the same data.

| Piece | Service | Where it lives in the repo |
|---|---|---|
| Chat page and Python code | Vercel | `app.py` (entry), `public/`, everything else |
| Data that changes (cards, travel notices, conversations, audit) | Convex project `BNY_Debit_Card_Manager` | `convex-demo-db/` |
| Understanding the requests | OpenAI GPT-5.4 | your key, in Vercel settings |
| Passcode screen and reset button (demo only) | — | `demo_tools/`, `public/demo-tools.js` |

Clients and advisor permissions are not in the database: they come from the CSV
files in `integrations/mock/data/` and never change.

---

## One-time setup

You need Node.js (for `npx`) and a GitHub account. Run the commands in Terminal
from the `debit-card-agent` folder.

### 1. Make a server secret

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```
Copy the result. It is your `DEMO_SERVER_SECRET` (used in steps 3 and 5).

### 2. Publish the Convex functions

```bash
cd convex-demo-db
npm install
npx convex dev --once
```
When asked, log in and choose the **existing** project `BNY_Debit_Card_Manager`.
This uploads the tables and functions to your **development** copy. Then:

```bash
npx convex deploy
```
Confirm when asked. This creates the **production** copy that Vercel will use.
Then `cd ..` back to the repo folder.

### 3. Give Convex the secret

In the Convex dashboard, open the project:
- switch the top dropdown to **Production** → **Settings** → **Environment Variables**
  → add `DEMO_SERVER_SECRET` = the value from step 1;
- do the same for **Development** if you also run the demo on your laptop.

### 4. Copy the production URL

Still on **Production**, copy the **Cloud URL** (ends in `.convex.cloud`).

### 5. Vercel settings

Vercel → your project → **Settings → Environment Variables** (Production):

| Name | Value |
|---|---|
| `OPENAI_API_KEY` | your `sk-...` key |
| `CONVEX_URL` | the **production** Cloud URL from step 4 (replace the development one if you added that) |
| `DEMO_SERVER_SECRET` | the value from step 1 |
| `DEMO_MODE` | `true` |
| `DEMO_PASSCODE` | your team passcode, e.g. `corestone-amber-7429` |

### 6. Put the code on GitHub and deploy

Create a new **private** GitHub repository and push this folder to it. `.env` is
excluded automatically, so your key stays on your laptop. Then in Vercel:
**Add New → Project → Import** the repository → Framework preset **Other** → **Deploy**.
(If you already created the Vercel project, connect it to the repository instead.)

The preset does not matter: `vercel.json` tells Vercel to run `app.py` (Python)
for every address, and `app.py` serves the chat page, `/api/*` and the demo tools
through the same code as the laptop server. Each message gets up to 5 minutes on
the free plan.

### 7. Test it

Open the Vercel link → enter the passcode → try *"Lock Jane Miller's card"* →
Confirm → press **Reset demo data** → try again. The line under the chat header
should read **Understanding: GPT-5.4**. Then share the link and the passcode.

The first message after a deploy saves the default state in Convex (from
`cards.csv`) and fills the `cards` table, so the first reply may take a few
seconds longer.

---

## Everyday use

- **Reset:** the **Reset demo data** button above the chat. It affects everyone.
- **New code:** push to GitHub; Vercel redeploys by itself. If you changed anything
  in `convex-demo-db/`, also run `npx convex deploy` from that folder.
- **Changed a setting in Vercel:** redeploy (Deployments → ⋯ → Redeploy).
- **See the data:** Convex dashboard → Production → **Data** (tables `cards`,
  `travel_notices`, `conversations`, `audit`, `defaults`).
- **Change the starting state:** edit `integrations/mock/data/cards.csv`, push.
  The server notices the change and updates the saved default state; press Reset
  to apply it.

## Running it on your laptop

Nothing changes: `python3 -m interfaces.a2a_server`. Without `CONVEX_URL` in
`.env`, data lives in memory (restart = reset). With the **development**
`CONVEX_URL` and `DEMO_SERVER_SECRET` in `.env`, your laptop uses the Convex
development copy instead. Add `DEMO_MODE=true` to see the reset bar locally.

## For the final deliverable

Remove `DEMO_MODE` and `DEMO_PASSCODE` (or delete `demo_tools/` and
`public/demo-tools.js`). The reset endpoint then answers 404, there is no
passcode screen, and the chat page never loads the demo script. Nothing in the
product logic depends on any of it.

## If something goes wrong

| Symptom | Likely cause |
|---|---|
| "Keyword stand-in (no AI)" under the header | `OPENAI_API_KEY` missing in Vercel, or not redeployed |
| Every message: "Not authorised" | `DEMO_SERVER_SECRET` differs between Vercel and Convex (Production) |
| "Could not find public function" | Convex functions not deployed to that copy: run `npx convex deploy` |
| Passcode always wrong | `DEMO_PASSCODE` in Vercel has a typo or spaces; redeploy after fixing |
| Reset button missing | `DEMO_MODE` is not exactly `true`, or not redeployed |
| Build error "pattern … doesn't match any Serverless Functions" | An old `vercel.json` with a `functions` block: use the current one (`builds` + `routes` to `app.py`) |
| "500 FUNCTION_INVOCATION_FAILED" | Vercel runs an older Python (3.9); every file now starts with `from __future__ import annotations` so it works there. Other start-up errors now show as a message on the page |
| Page loads but says "Server not reachable"; `/api/info` gives 404 | Vercel served only the static page: use the current `vercel.json` and push again |
