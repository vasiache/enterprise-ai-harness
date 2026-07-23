"""ping-tool - shared MCP health-check tool.

Deployed once in ns:shared-tools; any agent can call it via Declarative CRD toolServers[].

No database access, no tenant context required.

Tool:
    ping() → {status: "ok", tool: "ping-tool", timestamp: "<iso>"}
"""

import logging
from datetime import UTC, datetime

from fastmcp import FastMCP

log = logging.getLogger(__name__)

mcp = FastMCP(
    "ping-tool",
    instructions="Shared health-check tool. Call ping() to verify the MCP channel is working.",
)


@mcp.tool()
def ping() -> dict:
    """Check that the MCP channel is alive.

    Returns:
        status: "ok"
        tool: "ping-tool"
        timestamp: current UTC time in ISO 8601 format
    """
    return {
        "status": "ok",
        "tool": "ping-tool",
        "timestamp": datetime.now(UTC).isoformat(),
    }


def main() -> None:
    import uvicorn

    app = mcp.http_app(path="/mcp", stateless_http=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()

