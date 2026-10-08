# Vercel entry point. Every api/*.py file is the same: it hands the request to
# interfaces/a2a_server.py, which routes by path (identical to the local server).
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), *[".."] * 2))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from interfaces.a2a_server import WebHandler as handler  # noqa: E402,F401
