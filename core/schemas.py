"""
Loads tools/*.json and checks a filled-in form against them.

The model's tool call is checked here, in our own code, before anything else
runs - so a reviewer can see the check rather than taking it on trust. (Our
agent hosts the model and owns its tools in one process, so this is plain tool
calling; there is no MCP server in the request path.)
"""

import json
import os
from typing import Any

from core.errors import BadRequest

_DIR = os.path.join(os.path.dirname(__file__), "..", "tools")
_SCHEMAS: dict[str, dict] = {}


def load() -> dict[str, dict]:
    if not _SCHEMAS:
        for name in sorted(os.listdir(_DIR)):
            if name.endswith(".json"):
                with open(os.path.join(_DIR, name)) as f:
                    spec = json.load(f)
                _SCHEMAS[spec["name"]] = spec
    return _SCHEMAS


def all_tools() -> list[dict]:
    """What gets advertised to the model."""
    return list(load().values())


def is_write(tool_name: str) -> bool:
    return load()[tool_name].get("access") == "write"


def validate(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Raise BadRequest unless the form matches its schema exactly."""
    spec = load().get(tool_name)
    if spec is None:
        raise BadRequest(f"Unknown tool: {tool_name}")

    schema = spec["input_schema"]
    props = schema["properties"]

    for field in schema.get("required", []):
        if tool_input.get(field) in (None, "", []):
            raise BadRequest(f"Missing required field: {field}")

    for field, value in tool_input.items():
        if field not in props:
            raise BadRequest(f"Unknown field: {field}")
        expected = props[field].get("type")
        if expected == "string" and not isinstance(value, str):
            raise BadRequest(f"{field} must be text")
        if expected == "boolean" and not isinstance(value, bool):
            raise BadRequest(f"{field} must be true or false")
        if expected == "array" and not isinstance(value, list):
            raise BadRequest(f"{field} must be a list")
        allowed = props[field].get("enum")
        if allowed and value not in allowed:
            raise BadRequest(f"{field} must be one of: {', '.join(allowed)}")

    return tool_input
