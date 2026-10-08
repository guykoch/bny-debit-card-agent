"""
The front door. BNY's orchestrator calls this; for the demo, so does the mock
NetX AI chat page - locally, or hosted on Vercel (app.py uses the same code).

Deliberately thin: unpack the request, hand it to the conversation, pack the
response. All judgement lives in core/guardrails.py.

The payload shape is described in interfaces/a2a_agent_card.json. If BNY's A2A
envelope differs, change handle() and nothing else.

Run it locally:
    python -m interfaces.a2a_server
    then open http://localhost:8080 in a browser       (the mock chat)

    or, as the orchestrator would:
    curl -s localhost:8080 -d '{"advisor_id":"ADV-1234","utterance":"lock Jane Miller card"}'

Endpoints
    POST /  or  /api/chat   one advisor message (or button click) in, one reply out
    GET  /                  the mock NetX AI chat page (web/index.html)
    GET  /api/info          which runtime is active, and the demo advisors
    GET  /api/audit         the audit trail so far (demo only)
    /api/demo/*             demo-only tools (passcode, reset) - see demo_tools/
"""

from __future__ import annotations

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from config import settings
from config.settings import build_services
from core import audit
from core.models import Session
from integrations.mock import dataset
from interfaces.local_runtime import Conversation
from interfaces.threads import build_threads

_ROOT = os.path.join(os.path.dirname(__file__), "..")
_PUBLIC = os.path.join(_ROOT, "web")  # not "public": Vercel leaves that folder out of the Python bundle
_STATIC = {"/": "index.html", "/index.html": "index.html", "/demo-tools.js": "demo-tools.js"}

_SERVICES = None
_THREADS = None


def services():
    """Built on first use (on Vercel, once per warm process)."""
    global _SERVICES, _THREADS
    if _SERVICES is None:
        _SERVICES = build_services()
        _THREADS = build_threads()
        if settings.active_store() == "convex":
            from integrations.convex_store.client import ConvexClient
            client = ConvexClient()
            audit.add_sink(lambda row: client.mutation("addAudit", row=row))
    return _SERVICES


def threads():
    services()
    return _THREADS


def reset_memory() -> None:
    """Back to the CSV starting state for the in-memory store (used by demo reset)."""
    global _SERVICES, _THREADS
    _SERVICES, _THREADS = None, None
    audit.reset()


def _new_conversation(session: Session):
    """The only place that chooses who understands the advisor: GPT-5.4 or keywords."""
    if settings.active_runtime() == "gpt":
        from interfaces.llm_runtime import GptConversation
        return GptConversation(services(), session)
    return Conversation(services(), session)


def runtime_label() -> str:
    if settings.active_runtime() == "gpt":
        return settings.OPENAI_MODEL.upper()
    return "Keyword stand-in (no AI)"


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
    conv = _new_conversation(Session(advisor_id=advisor_id, conversation_id=conv_id,
                                     client_id=payload.get("client_id")))
    state = threads().load(conv_id)
    # Restore only a thread that belongs to this advisor and this runtime.
    if (state and state.get("advisor_id") == advisor_id
            and state.get("runtime") == settings.active_runtime()):
        conv.restore(state)

    response = conv.send(payload.get("utterance", ""))
    threads().save(conv_id, conv.snapshot())
    return response.to_dict()


def info() -> dict:
    return {"runtime": settings.active_runtime(), "runtime_label": runtime_label(),
            "model": settings.OPENAI_MODEL if settings.active_runtime() == "gpt" else None,
            "store": settings.active_store(),
            "advisors": sorted(dataset.GRANTS), "default_advisor": "ADV-1234",
            # demo-only switches (see demo_tools/)
            "demo_mode": settings.DEMO_MODE,
            "passcode_required": bool(settings.DEMO_PASSCODE)}


def list_audit() -> list:
    if settings.active_store() == "convex":
        from integrations.convex_store.client import ConvexClient
        return ConvexClient().query("listAudit")
    return audit.LOG


def passcode_ok(headers) -> bool:
    """When DEMO_PASSCODE is set, every data request must carry it."""
    if not settings.DEMO_PASSCODE:
        return True
    given = headers.get("X-Demo-Passcode") or ""
    return hmac.compare_digest(given.encode(), settings.DEMO_PASSCODE.encode())


def route(method: str, path: str, headers, body: bytes):
    """All endpoints, shared by the local server and Vercel. Returns (code, type, bytes)."""
    path = path.split("?")[0].rstrip("/") or "/"

    def js(code, obj):
        return code, "application/json", json.dumps(obj).encode()

    if method == "GET" and path in _STATIC:
        name = _STATIC[path]
        if name == "demo-tools.js" and not (settings.DEMO_MODE or settings.DEMO_PASSCODE):
            return js(404, {"status": "error", "message": "Not found."})
        with open(os.path.join(_PUBLIC, name), "rb") as f:
            kind = "text/html; charset=utf-8" if name.endswith(".html") else "text/javascript"
            return 200, kind, f.read()
    if method == "GET" and path == "/api/info":
        return js(200, info())

    if path.startswith("/api/demo/"):                       # demo-only, isolated
        from demo_tools import web as demo_web
        return demo_web.route(method, path, headers, body, js)

    if not passcode_ok(headers):
        return js(401, {"status": "error", "message": "Passcode required.", "card": None})
    if method == "GET" and path == "/api/audit":
        return js(200, list_audit())
    if method == "POST" and path in ("/", "/api/chat"):
        try:
            payload = json.loads(body or b"{}")
            return js(200, handle(payload))
        except Exception as e:                              # never leak a stack trace
            return js(400, {"status": "error", "message": str(e), "card": None})
    return js(404, {"status": "error", "message": "Not found."})


class WebHandler(BaseHTTPRequestHandler):
    """Used by the local server (Vercel goes through app.py instead)."""

    def _respond(self, method: str):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b""
        code, kind, out = route(method, self.path, self.headers, body)
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(out)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):
        self._respond("GET")

    def do_POST(self):
        self._respond("POST")

    def log_message(self, *args):
        pass


def main():
    port = int(os.environ.get("PORT", "8080"))
    print(f"debit-card-agent listening on http://localhost:{port}")
    print(f"understanding layer: {runtime_label()}")
    print(f"data store: {settings.active_store()}"
          + (f" ({settings.CONVEX_URL})" if settings.active_store() == "convex" else ""))
    if settings.RUNTIME == "auto" and settings.active_runtime() == "keyword":
        print("  (no OPENAI_API_KEY found - set it, or put it in a .env file, to use GPT-5.4)")
    if settings.DEMO_MODE:
        print("demo mode: ON (reset button shown)")
    ThreadingHTTPServer(("localhost", port), WebHandler).serve_forever()


if __name__ == "__main__":
    main()
