"""
A scripted conversation, for showing people. Run:  python -m demo.run_demo

Everything is mocked. No model, no network, no API key. The point is the shape
of the interaction and the guardrails, not language understanding.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DCA_STORE"] = "memory"      # never touch the shared demo database

from config.settings import build_services
from core import audit
from core.models import Session
from interfaces.local_runtime import Conversation

SCRIPT = [
    ("The simple case", "ADV-1234", [
        "Lock Jane Miller's card",
        "yes",
    ]),
    ("Two clients share a name", "ADV-1234", [
        "Sarah Chen is going to Georgia next month for two weeks",
        "C-44090",
        "Georgia (country)",
        "yes",
    ]),
    ("An irreversible action gets a stronger warning", "ADV-1234", [
        "Close Sarah Chen's card permanently",
        "C-44090",
        "no",
    ]),
    ("Lost wallet routes to the right skill, not to lock", "ADV-1234", [
        "Jane Miller lost her wallet, lock the card",
    ]),
    ("A client this advisor cannot see", "ADV-1234", [
        "Lock David Okafor's card",
    ]),
]


def main():
    services = build_services()
    for title, advisor, lines in SCRIPT:
        print("\n" + "=" * 68)
        print(f"  {title}   (advisor {advisor})")
        print("=" * 68)
        conv = Conversation(services, Session(advisor_id=advisor))
        for line in lines:
            print(f"\n  advisor >  {line}")
            r = conv.send(line)
            for out in r.message.splitlines():
                print(f"  agent   |  {out}")

    print("\n" + "=" * 68)
    print("  Audit trail")
    print("=" * 68)
    for row in audit.LOG:
        print(f"  {row['timestamp']}  {row['advisor_id']}  "
              f"{row['action']:<20}{row['outcome']:<22}typed={row['advisor_typed']!r}")


if __name__ == "__main__":
    main()
