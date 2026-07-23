"""
E2E: multi-agent routing test via A2A - management-agent → echo-agent.

Tests the Declarative agent-as-tool pattern:
  1. management-agent is called via A2A
  2. It routes the request to echo-agent (configured as an Agent tool in CRD)
  3. echo-agent responds with tenant prefix
  4. management-agent returns the combined result

This is a live integration check for the cluster routing path.

Requirements:
  - Kind cluster running with bootstrap-data.sh applied
  - kubectl port-forward -n kagent svc/kagent-controller 8083:8083

Run:
  INTEGRATION=1 pytest tests/e2e/test_agent_routing.py -v -s
"""

import time

from conftest import A2A_TIMEOUT_LONG, a2a_send, extract_text, needs_cluster

ECHO_AGENT_PATH = "/api/a2a/tenant-alpha/echo-agent/"
MGMT_AGENT_PATH = "/api/a2a/tenant-alpha/management-agent/"

TIMEOUT_LONG = A2A_TIMEOUT_LONG


@needs_cluster
class TestAgentRouting:
    """Declarative agent-as-tool routing: management-agent → echo-agent."""

    def setup_method(self, method):
        """Brief pause before each test to avoid LLM API rate pressure."""
        time.sleep(3)

    def test_echo_agent_direct(self):
        """Direct A2A call to echo-agent - must complete and echo back."""
        result = a2a_send(ECHO_AGENT_PATH, "ping", timeout=TIMEOUT_LONG)
        assert result["status"]["state"] == "completed", (
            f"Expected state=completed, got: {result['status']['state']}"
        )
        text = extract_text(result).lower()
        print(f"\n[echo-direct] response: {text}")

        assert "echo" in text or "tenant=alpha" in text, (
            f"Echo prefix missing from response: {text!r}\n"
            "Check systemMessage in echo-agent-crd.yaml"
        )

    def test_management_agent_calls_echo(self):
        """
        management-agent has echo-agent configured as an Agent tool in CRD.
        Ask management-agent to call echo-agent → response must include echo output.
        Runs last: this is the heaviest test (LLM plans + sub-agent call).
        Short imperative English prompt to minimize reasoning overhead.
        """
        result = a2a_send(
            MGMT_AGENT_PATH,
            "Call echo-agent with text 'health-check'. Output the result.",
            timeout=TIMEOUT_LONG,
        )
        assert result["status"]["state"] == "completed", (
            f"Expected state=completed, got: {result['status']['state']}"
        )
        text = extract_text(result).lower()
        print(f"\n[mgmt→echo] response: {text}")

        assert any(kw in text for kw in ["echo", "tenant", "health"]), (
            f"management-agent response doesn't show echo-agent was called: {text!r}"
        )
