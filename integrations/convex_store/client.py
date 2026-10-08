"""
Calls the Convex functions in convex-demo-db/convex/demo.ts over Convex's HTTP
API (POST <CONVEX_URL>/api/query or /api/mutation). Standard library only.

Every call carries DEMO_SERVER_SECRET; the Convex functions refuse calls
without it once the same value is set in the Convex dashboard.
"""

import json
import urllib.error
import urllib.request

from config import settings


class ConvexError(Exception):
    pass


class ConvexClient:
    def __init__(self, url: str = None, secret: str = None, timeout: int = 20):
        self.url = (url or settings.CONVEX_URL).rstrip("/")
        self.secret = secret if secret is not None else settings.DEMO_SERVER_SECRET
        self.timeout = timeout
        if not self.url:
            raise ConvexError("CONVEX_URL is not set.")

    def _call(self, kind: str, name: str, **args):
        body = {"path": f"demo:{name}", "args": {"secret": self.secret, **args},
                "format": "json"}
        req = urllib.request.Request(
            f"{self.url}/api/{kind}", data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ConvexError(f"Convex HTTP {e.code}: "
                              f"{e.read().decode('utf-8', 'replace')[:300]}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ConvexError(f"Could not reach Convex: {e}") from e
        if data.get("status") != "success":
            raise ConvexError(data.get("errorMessage") or str(data)[:300])
        return data.get("value")

    def query(self, name: str, **args):
        return self._call("query", name, **args)

    def mutation(self, name: str, **args):
        return self._call("mutation", name, **args)
