"""
The skill registry.

One skill per action, each in its own folder under skills/debit-card/, plus
_shared.md holding the rules they all obey. This module loads them, picks the
right one for a request, and builds the system prompt and tool list for it.

Why a registry rather than six hard-coded files: the skill folder is the single
source of truth. Adding a seventh action means adding a folder and a schema —
no change here, in the runtime, or in the guardrails.

The one thing to watch with per-action skills is drift between them. Everything
common lives in _shared.md and is prepended to whichever skill is chosen, so
there is still only one copy of the client-resolution and confirmation rules.
"""

import os
import re
from dataclasses import dataclass, field

from core import schemas

_DIR = os.path.join(os.path.dirname(__file__), "..", "skills", "debit-card")
_SHARED_FILE = "_shared.md"


@dataclass
class Skill:
    name: str                       # folder name, e.g. "lock-card"
    tool: str                       # the one action tool it may call
    lookups: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    priority: int = 0               # higher wins when several match
    description: str = ""
    body: str = ""                  # the markdown below the frontmatter

    def tool_names(self) -> list[str]:
        return [self.tool] + list(self.lookups)


_SKILLS: dict[str, Skill] = {}
_SHARED: str = ""


def _parse(text: str) -> tuple[dict, str]:
    """Frontmatter is `key: value`, lists comma-separated. No YAML dependency."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2)


def load() -> dict[str, Skill]:
    global _SHARED
    if _SKILLS:
        return _SKILLS

    with open(os.path.join(_DIR, _SHARED_FILE), encoding="utf-8") as f:
        _SHARED = f.read()

    for entry in sorted(os.listdir(_DIR)):
        path = os.path.join(_DIR, entry, "SKILL.md")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            meta, body = _parse(f.read())
        _SKILLS[meta.get("name", entry)] = Skill(
            name=meta.get("name", entry),
            tool=meta.get("tool", ""),
            lookups=[x.strip() for x in meta.get("lookups", "").split(",") if x.strip()],
            triggers=[x.strip().lower() for x in meta.get("triggers", "").split(",") if x.strip()],
            priority=int(meta.get("priority", 0)),
            description=meta.get("description", ""),
            body=body.strip(),
        )
    return _SKILLS


def all_skills() -> list[Skill]:
    return sorted(load().values(), key=lambda s: -s.priority)


def get(name: str) -> Skill | None:
    return load().get(name)


def for_tool(tool_name: str) -> Skill | None:
    return next((s for s in load().values() if s.tool == tool_name), None)


def route(utterance: str) -> Skill | None:
    """
    Pick the skill whose triggers the sentence matches, highest priority first.

    Priority is what keeps the cross-action cases right: "lost her wallet, lock
    the card" matches both report-lost-stolen and lock-card, and the former wins
    because losing a card is the more consequential reading. The skill then
    offers the alternative rather than silently choosing.
    """
    low = utterance.lower()
    for skill in all_skills():
        if any(t in low for t in skill.triggers):
            return skill
    return None


def system_prompt(skill: Skill) -> str:
    """What GPT-5.4 receives: the shared rules, then this one action."""
    return f"{_SHARED}\n\n---\n\n{skill.body}"


def tools_for(skill: Skill) -> list[dict]:
    """Only this skill's own tool, plus the read-only lookups."""
    every = {t["name"]: t for t in schemas.all_tools()}
    return [every[n] for n in skill.tool_names() if n in every]
