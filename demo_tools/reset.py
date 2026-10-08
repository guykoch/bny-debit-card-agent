"""
DEMO ONLY - puts all demo data back to the saved default state.

Default state = integrations/mock/data/cards.csv (also saved in Convex's
`defaults` table on first start). Reset restores every card from it and empties
travel notices, flags, conversations and the audit.
"""

from config import settings


def reset_demo_data() -> dict:
    if settings.active_store() == "convex":
        from integrations.convex_store.client import ConvexClient
        from integrations.convex_store.services import ensure_defaults
        client = ConvexClient()
        ensure_defaults(client)               # make sure the saved default state exists
        return {"store": "convex", **client.mutation("reset")}
    from interfaces import a2a_server
    a2a_server.reset_memory()
    return {"store": "memory", "restored_from": "integrations/mock/data/cards.csv"}
