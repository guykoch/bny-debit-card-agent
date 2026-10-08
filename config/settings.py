"""
One place to choose mock or live, and to hold anything environment-specific.

Going live should be a change to this file plus three classes in
integrations/bny/ — nothing else.
"""

import os
from dataclasses import dataclass

MODE = os.environ.get("DCA_MODE", "mock")      # "mock" or "bny"

# Entitlement
# -----------
# BNY's orchestrator checks entitlement before routing anything to us, and only
# sends requests it has already approved. So by default we trust that and do not
# re-check: our job starts after the gate.
#
# Set this to False to have the agent check entitlement itself as well. Two
# reasons you might:
#   - the upstream check is at client level ("may this advisor deal with this
#     client") rather than action level ("may they close this card permanently")
#   - a reviewer wants our audit to show what WE verified, not only what we
#     were told
# Either way the audit records which side did the checking, so the record is
# never silent about it.
TRUST_UPSTREAM_ENTITLEMENT = True

# Safety limits. Deliberately conservative; agree the real numbers with BNY.
MAX_TRAVEL_DAYS = 90
CONFIRM_REQUIRED_FOR_WRITES = True             # never set False in production


@dataclass
class Services:
    """Everything the agent needs from outside, passed in one object."""
    clients: object
    entitlements: object
    cards: object


def build_services() -> Services:
    if MODE == "mock":
        from integrations.mock.services import (
            MockCardSystem, MockClientDirectory, MockEntitlementService)
        ent = MockEntitlementService()
        return Services(clients=MockClientDirectory(ent),
                        entitlements=ent,
                        cards=MockCardSystem())

    if MODE == "bny":
        from integrations.bny.services import (
            BnyCardSystem, BnyClientDirectory, BnyEntitlementService)
        ent = BnyEntitlementService()
        return Services(clients=BnyClientDirectory(ent),
                        entitlements=ent,
                        cards=BnyCardSystem())

    raise ValueError(f"Unknown DCA_MODE: {MODE}")
