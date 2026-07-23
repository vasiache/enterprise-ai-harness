"""Base helpers for declarative FastMCP tool servers.

Each shared tool server calls create_server() to get a FastMCP instance
pre-configured with tenant_id and a TenantDB pool.

Pattern (tools/<name>/server.py):

    from saas_common.mcp_base import create_server, get_db, get_tenant_id

    mcp = create_server("ping-tool")

    @mcp.tool()
    async def search(query: str) -> list[str]:
        tid = get_tenant_id()
        db  = get_db()
        rows = await db.query(SQL, [query], tenant_id=tid)
        return [r["content"] for r in rows]

    if __name__ == "__main__":
        mcp.run()

tenant_id source:
    Phase 1 declarative tools: TENANT_ID environment variable (set per pod by CRD)
    Reserved compatibility paths may still read tenant_id from pod env.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import asyncpg

from .config import get_settings
from .supabase_client import TenantDB, create_pool

if TYPE_CHECKING:
    from fastmcp import FastMCP

_pool: asyncpg.Pool | None = None
_tenant_id: str | None = None


def get_tenant_id() -> str:
    """Return the tenant_id for the current pod.

    Raises RuntimeError if called before lifespan startup.
    """
    if _tenant_id is None:
        raise RuntimeError("MCP server not started - tenant_id unavailable")
    return _tenant_id


def get_db() -> TenantDB:
    """Return TenantDB backed by the pool created during startup.

    Raises RuntimeError if called before lifespan startup.
    """
    if _pool is None:
        raise RuntimeError("MCP server not started - DB pool unavailable")
    return TenantDB(_pool)


def create_server(name: str) -> "FastMCP":
    """Create a FastMCP server with tenant context wired in.

    Starts a DB pool on startup and sets module-level tenant_id.
    The returned FastMCP instance handles lifespan automatically.

    Args:
        name: MCP server name (e.g. 'tenant-info-tool').

    Returns:
        Configured FastMCP instance - decorate tools with @mcp.tool().
    """
    global _pool, _tenant_id

    @asynccontextmanager
    async def lifespan(server: "FastMCP") -> AsyncIterator[None]:
        global _pool, _tenant_id
        settings = get_settings()
        _tenant_id = settings.tenant_id
        _pool = await create_pool(settings.database_url)
        try:
            yield
        finally:
            if _pool:
                await _pool.close()
                _pool = None

    try:
        from fastmcp import FastMCP
    except ImportError as e:
        raise ImportError("fastmcp is required: pip install saas-common[tool]") from e

    return FastMCP(name, lifespan=lifespan)
