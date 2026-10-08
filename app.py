"""
Vercel entry point when the project runs as one Python app (WSGI).

vercel.json sends every request here, and the same route() as the local server
answers it: the chat page, /api/*, and the demo tools.

Standard library only: `app` is a plain WSGI callable.
"""

from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from interfaces.a2a_server import route  # noqa: E402
    _IMPORT_ERROR = None
except BaseException:  # show why start-up failed instead of a bare Vercel 500
    import traceback
    route, _IMPORT_ERROR = None, traceback.format_exc()[-1500:]

_REASONS = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 404: "Not Found",
            500: "Internal Server Error"}


def _headers(environ) -> dict:
    """WSGI keeps headers as HTTP_X_DEMO_PASSCODE; route() expects X-Demo-Passcode."""
    out = {}
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            out["-".join(w.capitalize() for w in key[5:].split("_"))] = value
    return out


def app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/") or "/"
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    body = environ["wsgi.input"].read(length) if length else b""
    try:
        if _IMPORT_ERROR:
            raise RuntimeError(f"Server failed to start: {_IMPORT_ERROR}")
        code, kind, out = route(method if method in ("GET", "POST") else "GET",
                                path, _headers(environ), body)
    except Exception as e:
        code, kind = 500, "text/plain; charset=utf-8"
        out = f"{type(e).__name__}: {e}".encode()
    start_response(f"{code} {_REASONS.get(code, 'OK')}",
                   [("Content-Type", kind), ("Content-Length", str(len(out))),
                    ("Cache-Control", "no-store")])
    return [out]
