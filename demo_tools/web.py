"""
DEMO ONLY - the endpoints behind the passcode screen and the reset button.

    POST /api/demo/check-passcode   {"passcode": "..."} -> {"ok": true|false}
    POST /api/demo/reset            needs DEMO_MODE=true and the passcode header

The product never imports this module; interfaces/a2a_server.py forwards
/api/demo/* here and nothing else.
"""

import hmac
import json

from config import settings
from demo_tools.reset import reset_demo_data


def route(method, path, headers, body, js):
    from interfaces.a2a_server import passcode_ok

    if method == "POST" and path == "/api/demo/check-passcode":
        if not settings.DEMO_PASSCODE:
            return js(200, {"ok": True})
        try:
            given = str(json.loads(body or b"{}").get("passcode", ""))
        except json.JSONDecodeError:
            given = ""
        return js(200, {"ok": hmac.compare_digest(given.encode(),
                                                  settings.DEMO_PASSCODE.encode())})

    if method == "POST" and path == "/api/demo/reset":
        if not settings.DEMO_MODE:
            return js(404, {"status": "error", "message": "Not found."})
        if not passcode_ok(headers):
            return js(401, {"status": "error", "message": "Passcode required."})
        try:
            return js(200, {"status": "ok", **reset_demo_data()})
        except Exception as e:
            return js(500, {"status": "error", "message": f"Reset failed: {e}"})

    return js(404, {"status": "error", "message": "Not found."})
