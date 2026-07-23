"""
E2E: ping-tool health check via MCP Streamable HTTP.

Tests the ping-tool MCP server directly (no agent involved):
  1. POST /mcp initialize → get session-id
  2. POST /mcp tools/call ping → assert status=ok in result

Tool is deployed in ns:shared-tools as a Deployment + Service.

Requirements:
  - Kind cluster running with setup-kind.sh + 07_tools.sh completed
  - Port-forward for ping-tool (required, not started automatically):
      kubectl port-forward -n shared-tools svc/ping-tool 8000:8000 --context kind-multitenant-agent-k8s
  - Port-forward for kagent-controller (required for agent tests):
      kubectl port-forward -n kagent svc/kagent-controller 8083:8083 --context kind-multitenant-agent-k8s

  Start both before running any E2E suite:
      kubectl port-forward -n shared-tools svc/ping-tool 8000:8000 --context kind-multitenant-agent-k8s &>/tmp/pf-ping.log &
      kubectl port-forward -n kagent svc/kagent-controller 8083:8083 --context kind-multitenant-agent-k8s &>/tmp/pf-kagent.log &
      kubectl port-forward -n platform svc/postgres 5432:5432 --context kind-multitenant-agent-k8s &>/tmp/pf-postgres.log &

Run:
  INTEGRATION=1 pytest tests/e2e/test_ping_tool.py -v -s

Override URL:
  PING_URL=http://localhost:8000/mcp INTEGRATION=1 pytest tests/e2e/test_ping_tool.py -v -s
"""

from __future__ import annotations

import json
import os
import uuid

import httpx
import pytest

PING_URL = os.environ.get("PING_URL", "http://localhost:8000/mcp")
TIMEOUT  = int(os.environ.get("PING_TIMEOUT", "30"))

MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _parse_sse_data(raw: str) -> dict:
    """Extract the JSON object from a `data: {...}` SSE line."""
    for line in raw.splitlines():
        if line.startswith("data:"):
            return json.loads(line[len("data:"):].strip())
    return json.loads(raw)


class McpSession:
    """Minimal stateful MCP session over Streamable HTTP (FastMCP 3.x)."""

    def __init__(self, url: str, timeout: int = TIMEOUT) -> None:
        self._url = url
        self._timeout = timeout
        self._session_id: str | None = None
        self._client: httpx.Client = httpx.Client(timeout=timeout)

    def __enter__(self) -> "McpSession":
        self._initialize()
        return self

    def __exit__(self, *_: object) -> None:
        self._client.close()

    def _post(self, payload: dict) -> dict:
        headers = dict(MCP_HEADERS)
        if self._session_id:
            headers["mcp-session-id"] = self._session_id
        resp = self._client.post(self._url, json=payload, headers=headers)
        resp.raise_for_status()
        sid = resp.headers.get("mcp-session-id")
        if sid:
            self._session_id = sid
        return _parse_sse_data(resp.text)

    def _initialize(self) -> None:
        data = self._post({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "e2e-test", "version": "1.0"},
            },
            "id": 0,
        })
        assert "result" in data, f"initialize failed: {data}"
        try:
            self._post({
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            })
        except Exception:
            pass

    def call_tool(self, name: str, arguments: dict) -> object:
        """Call a MCP tool, return the unwrapped content value."""
        data = self._post({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
            "id": str(uuid.uuid4()),
        })
        assert "result" in data, f"tools/call error for {name!r}: {data}"
        content = data["result"].get("content", [])
        assert content, f"Empty content in tools/call result for {name!r}"
        raw = content[0].get("text", "")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    def list_tools(self) -> list[dict]:
        """List available tools from the MCP server."""
        data = self._post({
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": str(uuid.uuid4()),
        })
        assert "result" in data, f"tools/list failed: {data}"
        return data["result"].get("tools", [])


class TestPingTool:
    """MCP ping-tool smoke tests - no agent, direct HTTP."""

    def test_initialize_and_session_id(self):
        """MCP initialize must succeed.

        Note: ping-tool uses stateless_http=True (FastMCP), so no session-id
        is returned - each request is independent. We just verify initialize
        doesn't return an error.
        """
        with McpSession(PING_URL) as s:
            assert s._session_id is None or isinstance(s._session_id, str), (
                "Unexpected session_id type"
            )
            print(f"\n[init] session_id={s._session_id!r} (None is expected for stateless_http=True)")

    def test_tools_list_contains_ping(self):
        """tools/list must return at least the 'ping' tool."""
        with McpSession(PING_URL) as s:
            tools = s.list_tools()
            names = [t["name"] for t in tools]
            print(f"\n[tools] available: {names}")
            assert "ping" in names, (
                f"'ping' tool not found in tools/list: {names}\n"
                "Check tools/ping-tool/ping_tool/server.py"
            )

    def test_ping_returns_ok(self):
        """Call ping - must return status='ok', tool='ping-tool', and a timestamp."""
        with McpSession(PING_URL) as s:
            result = s.call_tool("ping", {})

        print(f"\n[ping] result: {result}")
        assert isinstance(result, dict), f"Expected dict result, got: {type(result)}: {result}"
        assert result.get("status") == "ok", (
            f"ping returned status != 'ok': {result}"
        )
        assert result.get("tool") == "ping-tool", (
            f"ping 'tool' field missing or wrong: {result}"
        )
        assert "timestamp" in result, (
            f"ping 'timestamp' field missing: {result}"
        )

    def test_ping_timestamp_is_iso(self):
        """Ping timestamp must be parseable as ISO 8601."""
        from datetime import datetime
        with McpSession(PING_URL) as s:
            result = s.call_tool("ping", {})

        assert isinstance(result, dict), f"Expected dict, got: {result}"
        ts = result.get("timestamp", "")
        print(f"\n[ping-ts] timestamp: {ts}")
        try:
            datetime.fromisoformat(ts)
        except (ValueError, TypeError) as e:
            pytest.fail(f"timestamp {ts!r} is not valid ISO 8601: {e}")
