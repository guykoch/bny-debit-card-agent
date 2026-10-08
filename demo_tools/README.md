# demo_tools — for the hosted team demo only

Not part of the product. Remove this folder (and `web/demo-tools.js`) for the
final deliverable, or simply leave `DEMO_MODE` and `DEMO_PASSCODE` unset: then
the reset endpoint answers 404, the passcode check is off, and the chat page
never loads `demo-tools.js`.

| Piece | What it does |
|---|---|
| `web/demo-tools.js` | Passcode screen before the chat; "Demo controls" bar with **Reset demo data** above the chat panel |
| `demo_tools/web.py` | `/api/demo/check-passcode` and `/api/demo/reset` |
| `demo_tools/reset.py` | Puts all data back to the saved default state |

**Saved default state:** `integrations/mock/data/cards.csv`. On first start the
server also stores it in Convex (`defaults` table). Reset restores every card
from it and empties travel notices, flags, conversations and the audit — the
same result as restarting the local server.

**Settings:** `DEMO_MODE=true` shows the reset bar. `DEMO_PASSCODE=<word>` turns
on the passcode screen and makes every data request carry it.

Data is shared: a reset or a lock by one teammate affects everyone.
