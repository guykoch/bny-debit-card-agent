"""
Where conversation state is kept between messages.

memory  - a dict in this process (local runs; a restart forgets everything)
convex  - the Convex `conversations` table (hosted demo; survives across the
          stateless processes Vercel may use for each message)

Both store the same JSON snapshot produced by Conversation.snapshot() /
GptConversation.snapshot().
"""

from __future__ import annotations

import json

from config import settings


class MemoryThreads:
    def __init__(self):
        self._data: dict[str, str] = {}

    def load(self, conversation_id: str):
        raw = self._data.get(conversation_id)
        return json.loads(raw) if raw else None

    def save(self, conversation_id: str, state: dict) -> None:
        self._data[conversation_id] = json.dumps(state)

    def clear(self) -> None:
        self._data.clear()


class ConvexThreads:
    def __init__(self, client=None):
        from integrations.convex_store.client import ConvexClient
        self.client = client or ConvexClient()

    def load(self, conversation_id: str):
        raw = self.client.query("loadConversation", conversation_id=conversation_id)
        return json.loads(raw) if raw else None

    def save(self, conversation_id: str, state: dict) -> None:
        self.client.mutation("saveConversation", conversation_id=conversation_id,
                             state=json.dumps(state))

    def clear(self) -> None:
        pass                      # the Convex reset mutation empties the table


def build_threads():
    return ConvexThreads() if settings.active_store() == "convex" else MemoryThreads()
