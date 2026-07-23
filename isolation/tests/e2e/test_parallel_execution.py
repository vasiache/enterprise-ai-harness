"""
E2E: parallel tool execution test via A2A - echo-agent calls ping + get_tenant_info in parallel.

Tests that Declarative agents use ADK's native parallel tool call mechanism:
  - LLM returns multiple FunctionCall in a single response round
  - ADK Runner executes them concurrently (not sequentially)
  - Both results appear in the final response

Architecture:
  echo-agent has two independent MCP tools:
    - ping-tool.ping                        (ns:shared-tools)
    - tenant-info-tool.get_tenant_info      (ns:tenant-alpha)

  systemMessage instructs the agent to call independent tools in parallel.

Requirements:
  - Kind cluster running with bootstrap-data.sh applied
  - kubectl port-forward -n kagent svc/kagent-controller 8083:8083

Run:
  INTEGRATION=1 pytest tests/e2e/test_parallel_execution.py -v -s
"""

from conftest import A2A_TIMEOUT_LONG, a2a_send, extract_text_with_tool_data as extract_text, needs_cluster

ECHO_AGENT_PATH = "/api/a2a/tenant-alpha/echo-agent/"

TIMEOUT_LONG = A2A_TIMEOUT_LONG


@needs_cluster
class TestParallelToolExecution:
    """
    Verify that echo-agent calls independent tools in parallel via ADK native mechanism.
    systemMessage instructs: "call independent tools in parallel (in one request and in one round)".
    """

    def test_both_tools_called_and_results_in_response(self):
        """
        Call ping and get_tenant_info - both results must appear in response.
        Short imperative English prompt, no reasoning trigger words.
        """
        result = a2a_send(
            ECHO_AGENT_PATH,
            "ping. get_tenant_info.",
            timeout=TIMEOUT_LONG,
        )

        state = result["status"]["state"]
        assert state == "completed", (
            f"Expected state=completed, got: {state}\n"
            f"status: {result['status']}"
        )

        text = extract_text(result).lower()
        print(f"\n[parallel] response:\n{text}")

        has_ping = any(kw in text for kw in ["ok", "ping", "status", "tool"])
        has_tenant = any(kw in text for kw in ["alpha", "tenant", "org", "plan", "free"])

        assert has_ping, (
            f"Ping tool result missing from response: {text!r}\n"
            "Check ping-tool RemoteMCPServer CRD and NetworkPolicy"
        )
        assert has_tenant, (
            f"Tenant info result missing from response: {text!r}\n"
            "Check tenant-info-tool RemoteMCPServer CRD"
        )
