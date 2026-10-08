"""
Vercel entry point when the project runs as one Python app (WSGI).

Vercel runs this file if it treats the repository as a Python application; it
then sends every request here, and the same route() as the local server answers
it - chat page, /api/*, and the demo tools. If Vercel instead serves public/ as
static files and runs api/*.py as separate functions, this file is unused.

Standard library only: `app` is a plain WSGI callable.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from interfaces.a2a_server import route  # noqa: E402

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
    code, kind, out = route(method if method in ("GET", "POST") else "GET",
                            path, _headers(environ), body)
    start_response(f"{code} {_REASONS.get(code, 'OK')}",
                   [("Content-Type", kind), ("Content-Length", str(len(out))),
                    ("Cache-Control", "no-store")])
    return [out]
