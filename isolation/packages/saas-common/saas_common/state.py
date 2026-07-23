"""Reserved compatibility state for pre-ADR-009 BYO LangGraph agents.

This module stays importable as a compatibility tail for older agent code, but
it is not part of the active declarative FastMCP baseline or current in-repo
codepaths used in Phase 1.

Older agents used BaseState as the TypedDict base and added the LangGraph
add_messages annotation locally:

    from typing import Annotated
    from langgraph.graph import add_messages
    from langchain_core.messages import BaseMessage
    from saas_common.state import BaseState

    class SalesState(BaseState):
        messages: Annotated[list[BaseMessage], add_messages]
        cart: list[str]
"""

from typing import TypedDict


class BaseState(TypedDict, total=False):
    """Minimum state carried through every pre-ADR-009 agent graph.

    Fields:
        messages:   conversation history - annotate with add_messages in subclass
        tenant_id:  isolation key - set once at graph entry, never mutated
        org:        org within the tenant (e.g. 'sales', 'management')
        user_id:    caller identity (tg_id or UUID from JWT sub)
        session_id: thread_id for kagent checkpointer
    """

    messages: list
    tenant_id: str
    org: str
    user_id: str
    session_id: str
