"""
OPTIONAL PACKAGING - not in the request path.

Our agent hosts the model (GPT-5.4) and owns its tools in one process, so the
model reaches them by plain tool calling (interfaces/llm_runtime.py) and MCP
has no role. This file only matters in one scenario: if BNY's platform hosts
the model itself and expects agents to publish tools as a separate MCP server.
Whether that is the case is an open question for BNY.

Install the SDK to run it:
    pip install mcp

What it does NOT do: decide anything. MCP advertises tools, validates shapes,
and routes. Entitlement, confirmation and audit stay in core/guardrails.py,
behind this layer. That ordering is the point — a model that reaches MCP has
still reached nothing.
"""

from config.settings import build_services
from core import schemas
from core.guardrails import dispatch
from core.models import Session

SERVICES = build_services()


def call_tool(tool_name: str, arguments: dict, advisor_id: str,
              confirmed: bool = False) -> dict:
    """The single function an MCP server handler should call."""
    session = Session(advisor_id=advisor_id,
                      utterance=arguments.pop("_utterance", ""))
    return dispatch(SERVICES, session, tool_name, arguments, confirmed).to_dict()


def build_server():
    """
    Registers each tools/*.json entry with an MCP server.

    advisor_id must come from the transport's authenticated context, never from
    the model's arguments. The line marked below is where BNY wires that in.
    """
    try:
        from mcp.server import Server
        from mcp.types import Tool
    except ImportError as e:                      # pragma: no cover
        raise SystemExit("MCP SDK not installed. Run: pip install mcp") from e

    server = Server("debit-card-agent")

    @server.list_tools()
    async def list_tools():
        return [Tool(name=t["name"], description=t["description"],
                     inputSchema=t["input_schema"]) for t in schemas.all_tools()]

    @server.call_tool()
    async def handle_call(name: str, arguments: dict):
        advisor_id = arguments.pop("advisor_id", None)   # <- replace with session context
        return call_tool(name, arguments, advisor_id)

    return server


if __name__ == "__main__":
    build_server()
