"""
The front door. BNY's orchestrator calls this; nothing else does.

Deliberately thin: unpack the request, hand it to the conversation, pack the
response. All judgement lives in core/guardrails.py.

The payload shape is described in interfaces/a2a_agent_card.json. If BNY's A2A
envelope differs, change the two small functions at the bottom of this file and
nothing else.

Run it locally:
    python -m interfaces.a2a_server
    curl -s localhost:8080 -d '{"advisor_id":"ADV-1234","utterance":"lock Jane Miller card"}'
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from config.settings import build_services
from core.models import Session
from interfaces.local_runtime import Conversation

_SERVICES = build_services()
_THREADS: dict[str, Conversation] = {}        # conversation_id -> state


def handle(payload: dict) -> dict:
    """
    One request in, one response out.

    advisor_id MUST come from the authenticated upstream session. We never read
    an advisor identity out of the message text.
    """
    advisor_id = payload.get("advisor_id")
    if not advisor_id:
        return {"status": "error", "message": "Missing advisor_id.", "card": None}

    conv_id = payload.get("conversation_id") or f"{advisor_id}:default"
    conv = _THREADS.get(conv_id)
    if conv is None:
        conv = Conversation(_SERVICES, Session(advisor_id=advisor_id,
                                               conversation_id=conv_id,
                                               client_id=payload.get("client_id")))
        _THREADS[conv_id] = conv

    response = conv.send(payload.get("utterance", ""))
    return response.to_dict()


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            result = handle(payload)
            code = 200
        except Exception as e:                     # never leak a stack trace upstream
            result, code = {"status": "error", "message": str(e), "card": None}, 400
        body = json.dumps(result).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print("debit-card-agent listening on http://localhost:8080")
    HTTPServer(("localhost", 8080), _Handler).serve_forever()
