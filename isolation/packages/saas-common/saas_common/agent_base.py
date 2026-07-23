"""Reserved compatibility helpers for pre-ADR-009 BYO LangGraph agents.

The active Phase 1 baseline uses declarative FastMCP tools. This module stays
importable only as a compatibility tail for pre-ADR-009 LangGraph-based agent
code and is not used by the baseline or current in-repo codepaths.

Each older agent defined its own compiled LangGraph and called create_app()
to get a ready-to-serve FastAPI application wired to the A2A protocol.

Pattern (agents/<name>/agent.py):

    from saas_common.agent_base import create_app
    from langgraph.prebuilt import create_react_agent
    ...

    graph = create_react_agent(model=llm, tools=tools, checkpointer=checkpointer)
    app = create_app(graph, name="support-agent", description="TechSupport agent")

    if __name__ == "__main__":
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8080)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from saas_common.config import _DEFAULT_KAGENT_URL

if TYPE_CHECKING:
    from a2a.types import AgentSkill
    from langgraph.graph.state import CompiledStateGraph


def create_app(
    graph: CompiledStateGraph,
    *,
    name: str,
    description: str,
    version: str = "0.1.0",
    skills: list[AgentSkill] | None = None,
) -> object:
    """Build a FastAPI A2A application from a compiled LangGraph.

    Config is read from environment variables set by the Agent CRD:
        KAGENT_URL       - kagent controller endpoint
        KAGENT_APP_NAME  - unique name used for checkpointer threading
        AGENT_URL        - public URL of this agent pod (for the AgentCard)

    Args:
        graph:       Pre-compiled LangGraph (with KAgentCheckpointer).
        name:        Human-readable agent name.
        description: Short agent description surfaced in the A2A AgentCard.
        version:     Semver string.
        skills:      Optional list of A2A Skills this agent exposes.

    Returns:
        FastAPI application - pass directly to uvicorn.run().
    """
    try:
        from a2a.types import AgentCapabilities, AgentCard
        from kagent.core import KAgentConfig
        from kagent.langgraph import KAgentApp
    except ImportError as e:
        raise ImportError("Agent deps required: pip install saas-common[agent]") from e

    kagent_config = KAgentConfig(
        url=os.environ.get("KAGENT_URL", _DEFAULT_KAGENT_URL),
        app_name=os.environ.get("KAGENT_APP_NAME", name),
    )

    agent_url = os.environ.get("AGENT_URL", "http://localhost:8080")

    agent_card = AgentCard(
        name=name,
        description=description,
        version=version,
        url=agent_url,
        capabilities=AgentCapabilities(streaming=True),
        skills=skills or [],
    )

    return KAgentApp(
        graph=graph,
        agent_card=agent_card,
        config=kagent_config,
    ).build()
