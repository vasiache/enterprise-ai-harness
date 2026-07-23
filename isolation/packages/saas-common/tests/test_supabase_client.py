"""Tests for TenantDB RLS wrapper.

Key invariant: TenantDB must always SET LOCAL app.tenant_id inside a
transaction before executing the actual SQL. Without this, RLS policies
return 0 rows (our fail-safe), but we want the wrapper to enforce it
at the API level too.
"""

from unittest.mock import AsyncMock, MagicMock, call

import pytest
from saas_common.supabase_client import TenantDB


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = MagicMock()

    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = acquire_ctx

    txn_ctx = MagicMock()
    txn_ctx.__aenter__ = AsyncMock(return_value=None)
    txn_ctx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction.return_value = txn_ctx

    conn.fetch = AsyncMock(return_value=[{"id": "1", "tenant_id": "furnco"}])
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    return pool, conn


@pytest.mark.asyncio
async def test_query_sets_tenant_id_before_fetch(mock_pool):
    pool, conn = mock_pool
    db = TenantDB(pool)

    await db.query("SELECT * FROM rag.embeddings WHERE tenant_id = $1", ["furnco"], tenant_id="furnco")

    calls = conn.execute.call_args_list
    assert calls[0] == call("SET LOCAL app.tenant_id = $1", "furnco")


@pytest.mark.asyncio
async def test_query_uses_explicit_transaction(mock_pool):
    pool, conn = mock_pool
    db = TenantDB(pool)

    await db.query("SELECT 1", [], tenant_id="furnco")

    conn.transaction.assert_called_once()


@pytest.mark.asyncio
async def test_execute_sets_tenant_id_before_dml(mock_pool):
    pool, conn = mock_pool
    db = TenantDB(pool)

    await db.execute(
        "INSERT INTO orders.leads (tenant_id) VALUES ($1)", ["furnco"], tenant_id="furnco"
    )

    calls = conn.execute.call_args_list
    assert calls[0] == call("SET LOCAL app.tenant_id = $1", "furnco")


@pytest.mark.asyncio
async def test_query_one_returns_none_on_empty(mock_pool):
    pool, conn = mock_pool
    conn.fetch = AsyncMock(return_value=[])
    db = TenantDB(pool)

    result = await db.query_one("SELECT * FROM platform.users WHERE id = $1", ["missing"], tenant_id="furnco")

    assert result is None


@pytest.mark.asyncio
async def test_tenant_id_is_keyword_only():
    """tenant_id must be keyword-only - cannot be passed positionally."""
    db = TenantDB(MagicMock())
    with pytest.raises(TypeError):
        await db.query("SELECT 1", [], "furnco")  # type: ignore[call-arg]
