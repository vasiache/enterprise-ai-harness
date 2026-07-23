"""
Shared fixtures and helpers for E2E tests.

Helpers here are used by:
  - test_ping_tool.py
  - test_agent_routing.py
  - test_parallel_execution.py
  - test_memory_multi_turn.py  (has its own context_id variant - see that file)

━━ Required port-forwards (start before any E2E suite) ━━━━━━━━━━━━━━━━━━━━━
  kubectl port-forward -n shared-tools svc/ping-tool 8000:8000 \
    --context kind-multitenant-agent-k8s &>/tmp/pf-ping.log &
  kubectl port-forward -n kagent svc/kagent-controller 8083:8083 \
    --context kind-multitenant-agent-k8s &>/tmp/pf-kagent.log &
  kubectl port-forward -n platform svc/postgres 5432:5432 \
    --context kind-multitenant-agent-k8s &>/tmp/pf-postgres.log &

  PING_URL targets port 8000 (ping-tool).
  KAGENT_URL targets port 8083 (kagent-controller, all agent tests).

━━ Run all suites ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  INTEGRATION=1 pytest tests/e2e/ -v -s

━━ A2A protocol notes ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  - Parts use "kind" not "type": {"kind": "text", "text": "..."}
  - contextId goes inside params.message (not top-level params)
  - kagent returns text either in artifacts[0].parts or in history[role=agent]
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

KAGENT_URL = os.environ.get("KAGENT_URL", "http://localhost:8083")

A2A_TIMEOUT      = int(os.environ.get("A2A_TIMEOUT",      "40"))
A2A_TIMEOUT_LONG = int(os.environ.get("A2A_TIMEOUT_LONG", "180"))

needs_cluster = pytest.mark.skipif(
    not os.environ.get("INTEGRATION"),
    reason="Requires live Kind cluster. Run with INTEGRATION=1",
)


def a2a_send(
    path: str,
    text: str,
    timeout: int = A2A_TIMEOUT,
    context_id: str | None = None,
) -> dict:
    """Send message/send to an agent, return parsed result dict.

    Args:
        path:       A2A path, e.g. '/api/a2a/tenant-alpha/echo-agent/'
        text:       User message text.
        timeout:    HTTP timeout in seconds.
        context_id: Optional contextId for multi-turn sessions.
                    Goes inside params.message per A2A spec.

    Returns:
        Parsed result dict from the A2A jsonrpc response.
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
    resp = httpx.post(KAGENT_URL + path, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    assert "result" in data, f"No 'result' in A2A response: {data}"
    return data["result"]


def extract_text(result: dict) -> str:
    """Extract concatenated text from A2A result.

    Handles two shapes:
    1. Plain text: artifacts[0].parts[kind=text]
    2. Tool calls: last role=agent message in history (LLM summary)

    Returns lowercased combined text.
    """
    parts = result.get("artifacts", [{}])[0].get("parts", [])
    texts = [p["text"] for p in parts if p.get("kind") == "text" and p.get("text")]
    if texts:
        return " ".join(texts)

    for msg in reversed(result.get("history", [])):
        if msg.get("role") == "agent":
            for part in msg.get("parts", []):
                if part.get("kind") == "text" and part.get("text"):
                    return part["text"]
    return ""


def extract_text_with_tool_data(result: dict) -> str:
    """Extended extract_text that also captures tool response content from data artifacts.

    Used by test_parallel_execution.py where tool JSON responses appear as
    artifact parts with kind='data'.
    """
    parts = result.get("artifacts", [{}])[0].get("parts", [])

    texts = [p["text"] for p in parts if p.get("kind") == "text" and p.get("text")]
    if texts:
        return " ".join(texts)

    tool_texts: list[str] = []
    for part in parts:
        if part.get("kind") == "data":
            response = part.get("data", {}).get("response", {})
            for item in response.get("content", []):
                if item.get("type") == "text" and item.get("text"):
                    tool_texts.append(item["text"])

    history_text = ""
    for msg in reversed(result.get("history", [])):
        if msg.get("role") == "agent":
            for part in msg.get("parts", []):
                if part.get("kind") == "text" and part.get("text"):
                    history_text = part["text"]
                    break
        if history_text:
            break

    return " ".join(filter(None, [history_text] + tool_texts))
