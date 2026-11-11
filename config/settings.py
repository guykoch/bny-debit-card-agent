"""
One place to choose mock or live, and to hold anything environment-specific.

Going live should be a change to this file plus three classes in
integrations/bny/ — nothing else.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# ---------------------------------------------------------------- .env file
# Optional convenience for the demo: a file named `.env` at the repository root
# with lines like  OPENAI_API_KEY=sk-...  is read at start-up. Real environment
# variables win over the file. `.env` is git-ignored; never commit a key.

def _load_dotenv() -> None:
    path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


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
#     client") rather than action level ("may they replace this card")
#   - a reviewer wants our audit to show what WE verified, not only what we
#     were told
# Either way the audit records which side did the checking, so the record is
# never silent about it.
TRUST_UPSTREAM_ENTITLEMENT = False            # F-01: we check permissions ourselves too

# How permissions are read (decision D-01, still open with Ben):
#   "per_action"      each advisor-client pair lists the actions allowed
#                     (entitlements.csv), e.g. lock but not replace
#   "all_or_nothing"  any row for the pair gives every card action; no row, nothing
# Ben described access as all or nothing; switch here if he confirms it.
PERMISSION_MODEL = os.environ.get("DCA_PERMISSION_MODEL", "per_action")

# Safety limits. Agree the real numbers with BNY.
MAX_TRAVEL_DAYS = 14                           # per Ben: travel notices max out at 2 weeks
MAX_TRAVEL_DESTINATIONS = 10                   # per Ben: up to 10 destinations per notice
CONFIRM_REQUIRED_FOR_WRITES = True             # never set False in production

# Replacement delivery (decision D-02): only to an address listed in the client's
# profile, and only in a US state, DC or US territory. A new address must first be
# added to the profile in NetX360. PO boxes: still to confirm with Ben.
REPLACEMENT_ALLOW_PO_BOX = True

# Address suggestions while typing (autofill). "auto": Google Places when
# GOOGLE_MAPS_API_KEY is set, otherwise a small built-in sample list.
# The key is used only on the server; the browser never sees it.
ADDRESS_PROVIDER = os.environ.get("DCA_ADDRESS_PROVIDER", "auto")   # auto | google | sample
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# Pending cards (issued, not yet activated) - decision D-03, still open with Ben.
# Default: lock it, or order a replacement (e.g. it never arrived). Everything
# else is refused with a clear message.
PENDING_CARD_ACTIONS = {"lock_card", "replace_card"}

# Unusual volume (decision D-06, team default): at most this many completed
# actions of one kind per advisor in the time window. Agree real numbers with BNY.
VOLUME_LIMITS = {"replace_card": 5, "report_lost_stolen": 5,
                 # Service Center tickets (per advisor, per window)
                 "stop_payment": 10, "check_copy": 10, "address_update": 5, "misc_request": 10,
                 "rollover_inquiry": 10}
VOLUME_WINDOW_MINUTES = 10


# ---------------------------------------------------------------- the AI layer
# Which "understanding" runtime reads the advisor's words:
#   "gpt"     GPT-5.4 through the OpenAI API (interfaces/llm_runtime.py)
#   "keyword" the keyword stand-in, no AI at all (interfaces/local_runtime.py)
#   "auto"    gpt if OPENAI_API_KEY is set, otherwise keyword   (default)
#
# The AI only understands the request. Everything after it — checks, the
# confirmation panel, the card action, the audit — is the same plain code in
# both runtimes.
RUNTIME = os.environ.get("DCA_RUNTIME", "auto")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.environ.get("DCA_MODEL", "gpt-5.4")
# "none" is GPT-5.4's default. Raise to "low" or "medium" if understanding of
# vague requests needs more thought; it adds a little latency per message.
OPENAI_REASONING_EFFORT = os.environ.get("DCA_REASONING_EFFORT", "none")
OPENAI_TIMEOUT_SECONDS = int(os.environ.get("DCA_MODEL_TIMEOUT", "60"))

# Most model round trips allowed for one advisor message (lookups plus the
# action form). A normal request needs two or three.
MAX_MODEL_STEPS = 6


# ---------------------------------------------------------------- where changes are kept
# "memory": in this process only; a restart resets everything (local default).
# "convex": in a Convex database, so a stateless host like Vercel keeps the cards,
#           conversations and audit between requests. Used automatically when
#           CONVEX_URL is set. Clients and entitlements always come from the CSVs.
CONVEX_URL = os.environ.get("CONVEX_URL") or os.environ.get("VITE_CONVEX_URL", "")
STORE = os.environ.get("DCA_STORE", "auto")       # auto | memory | convex
# Shared secret checked by every Convex function (set the same value in Convex).
DEMO_SERVER_SECRET = os.environ.get("DEMO_SERVER_SECRET", "")


def active_store() -> str:
    if STORE == "auto":
        return "convex" if CONVEX_URL else "memory"
    return STORE


# ---------------------------------------------------------------- demo-only switches
# Nothing in the product depends on these. See demo_tools/README.md.
DEMO_MODE = os.environ.get("DEMO_MODE", "").strip().lower() in ("1", "true", "yes", "on")
DEMO_PASSCODE = os.environ.get("DEMO_PASSCODE", "")


def active_runtime() -> str:
    """Resolve "auto" to the runtime that will actually run."""
    if RUNTIME == "auto":
        return "gpt" if OPENAI_API_KEY else "keyword"
    return RUNTIME


@dataclass
class Services:
    """Everything the agent needs from outside, passed in one object."""
    clients: object
    entitlements: object
    cards: object
    checks: object = None            # accounts and checks (read-only)
    tickets: object = None           # Service Center tickets
    advisor_settings: object = None  # e.g. the saved Call Back #
    files: object = None             # ticket attachments
    advisors: object = None          # advisor directory: name, default Call Back #
    incoming_checks: object = None   # checks received at the money desks (rollover inquiry)


def build_services() -> Services:
    if MODE == "mock":
        from integrations.mock.services import (
            MemoryAdvisorSettings, MemoryFileStore, MemoryServiceCenter, MockAdvisorDirectory,
            MockCardSystem, MockCheckSystem, MockClientDirectory, MockEntitlementService,
            MockIncomingChecks)
        ent = MockEntitlementService()
        book = None
        if active_store() == "convex":
            from integrations.convex_store.services import (
                ConvexAddressBook, ConvexAdvisorSettings, ConvexCardSystem, ConvexFileStore,
                ConvexServiceCenter)
            cards = ConvexCardSystem()
            book = ConvexAddressBook(cards.client)
            tickets = ConvexServiceCenter(cards.client)
            prefs = ConvexAdvisorSettings(cards.client)
            files = ConvexFileStore(cards.client)
        else:
            cards = MockCardSystem()
            tickets, prefs, files = MemoryServiceCenter(), MemoryAdvisorSettings(), MemoryFileStore()
        return Services(clients=MockClientDirectory(ent, book), entitlements=ent, cards=cards,
                        checks=MockCheckSystem(), tickets=tickets, advisor_settings=prefs,
                        files=files, advisors=MockAdvisorDirectory(),
                        incoming_checks=MockIncomingChecks())

    if MODE == "bny":
        from integrations.bny.services import (
            BnyCardSystem, BnyClientDirectory, BnyEntitlementService)
        ent = BnyEntitlementService()
        return Services(clients=BnyClientDirectory(ent),
                        entitlements=ent,
                        cards=BnyCardSystem())

    raise ValueError(f"Unknown DCA_MODE: {MODE}")
