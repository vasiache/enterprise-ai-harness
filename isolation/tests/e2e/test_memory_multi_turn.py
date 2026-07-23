"""
E2E: multi-turn context test for echo-agent via kagent A2A.

Tests that two consecutive A2A calls to echo-agent:
  1. Both complete successfully (state=completed)
  2. The second call preserves the contextId from the first (multi-turn session)
  3. Echo-agent response contains the tenant/org prefix

Agent path: /api/a2a/tenant-alpha/echo-agent/

Key findings (Phase 0.10 / Phase 1):
  - contextId MUST be passed inside params.message (not params.contextId)
  - A2A parts use "kind" not "type": {"kind": "text", "text": "..."}
  - echo-agent prefixes replies with "tenant=alpha org=<org> echo:"

Requirements:
  - Kind cluster running with bootstrap-data.sh applied
  - kubectl port-forward -n kagent svc/kagent-controller 8083:8083

Run:
  pytest tests/e2e/test_memory_multi_turn.py -v
"""

import uuid
import time
import httpx

from conftest import KAGENT_URL, needs_cluster

AGENT_PATH = "/api/a2a/tenant-alpha/echo-agent/"
TIMEOUT_FIRST  = 180
TIMEOUT_SECOND = 180


def a2a_send(
    text: str,
    context_id: str | None = None,
    timeout: int = TIMEOUT_FIRST,
) -> dict:
    """Send message/send to echo-agent, return parsed result dict.

    contextId is placed inside params.message (A2A spec requirement).
    On first call pass context_id=None; on subsequent calls pass the
    contextId returned in the previous result.
    """
    message: dict = {
        "role": "user",
        "parts": [{"kind": "text", "text": text}],
    }
    if context_id:
        message["contextId"] = context_id

    payload = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {"message": message},
        "id": str(uuid.uuid4()),
    }
    resp = httpx.post(
        KAGENT_URL + AGENT_PATH,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    assert "result" in data, f"No 'result' in response: {data}"
    return data["result"]


def extract_text(result: dict) -> str:
    """Pull text from A2A result artifacts or status message, lowercased.

    Tries multiple locations kagent may place the response:
      1. result.artifacts[0].parts (standard A2A)
      2. result.status.message.parts (some kagent versions)
    """
    artifacts = result.get("artifacts") or []
    for artifact in artifacts:
        parts = artifact.get("parts", [])
        texts = [p["text"] for p in parts if p.get("kind") == "text" and p.get("text")]
        if texts:
            return " ".join(texts).lower()

    msg = (result.get("status") or {}).get("message") or {}
    parts = msg.get("parts", [])
    texts = [p["text"] for p in parts if p.get("kind") == "text" and p.get("text")]
    return " ".join(texts).lower()


@needs_cluster
class TestEchoAgentMultiTurn:
    """
    Two-message conversation sharing the same contextId via echo-agent.
    Msg1: send a greeting → agent echoes it with tenant prefix.
    Msg2: send a follow-up in the SAME context → contextId must be preserved.
    """

    def setup_method(self, method):
        """Brief pause before each test - LLM may still be processing prior suite."""
        time.sleep(3)

    def test_echo_returns_tenant_prefix(self):
        """Single message: echo-agent must reply with tenant=alpha prefix."""
        result = a2a_send(
            text="Hello from test",
            context_id=None,
            timeout=TIMEOUT_FIRST,
        )
        assert result["status"]["state"] == "completed", (
            f"Expected state=completed, got: {result['status']['state']}"
        )
        text = extract_text(result)
        print(f"\n[echo] response: {text!r}")
        print(f"[echo] full result: artifacts={result.get('artifacts')}, status={result.get('status')}")

        assert "tenant=alpha" in text or "echo:" in text, (
            f"Echo prefix missing. Got: {text!r}\n"
            "Check echo-agent systemMessage in echo-agent-crd.yaml"
        )

    def test_context_preserved_across_turns(self):
        """Two-turn conversation: contextId from msg1 must appear in msg2 result."""
        result1 = a2a_send(
            text="Первое сообщение в сессии.",
            context_id=None,
            timeout=TIMEOUT_FIRST,
        )
        assert result1["status"]["state"] == "completed", (
            f"msg1: Expected state=completed, got: {result1['status']['state']}"
        )
        ctx_id = result1["contextId"]
        ans1 = extract_text(result1)
        print(f"\n[msg1] ctx={ctx_id}  answer={ans1}")

        time.sleep(2)

        result2 = a2a_send(
            text="Второе сообщение в той же сессии.",
            context_id=ctx_id,
            timeout=TIMEOUT_SECOND,
        )
        assert result2["status"]["state"] == "completed", (
            f"msg2: Expected state=completed, got: {result2['status']['state']}"
        )
        assert result2["contextId"] == ctx_id, (
            f"contextId changed between turns: {ctx_id!r} → {result2['contextId']!r}"
        )
        ans2 = extract_text(result2)
        print(f"[msg2] ctx={result2['contextId']}  answer={ans2}")
        print("✅ Multi-turn context preserved")
