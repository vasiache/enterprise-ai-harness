"""TenantDB - mandatory RLS wrapper for all database access.

CRITICAL: Every query MUST go through TenantDB.
Direct asyncpg calls bypass RLS → data leak across tenants.

Why transaction() is required:
    asyncpg executes each statement in its own implicit transaction
    (autocommit). SET LOCAL is scoped to the current transaction, so
    it disappears before the next fetch() call unless both are wrapped
    in an explicit BEGIN...COMMIT block.

    Ref: https://www.postgresql.org/docs/current/sql-set.html
         "SET LOCAL lasts only till the end of the current transaction"
"""

import asyncpg


class TenantDB:
    """Wraps asyncpg.Pool and injects SET LOCAL app.tenant_id before every query."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def query(self, sql: str, params: list, *, tenant_id: str) -> list[asyncpg.Record]:
        """Run a SELECT and return rows, scoped to tenant_id."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(f"SET LOCAL \"app.tenant_id\" = '{tenant_id}'")
                return await conn.fetch(sql, *params)

    async def execute(self, sql: str, params: list, *, tenant_id: str) -> str:
        """Run an INSERT/UPDATE/DELETE, scoped to tenant_id."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(f"SET LOCAL \"app.tenant_id\" = '{tenant_id}'")
                return await conn.execute(sql, *params)

    async def query_one(
        self, sql: str, params: list, *, tenant_id: str
    ) -> asyncpg.Record | None:
        """Run a SELECT and return the first row or None."""
        rows = await self.query(sql, params, tenant_id=tenant_id)
        return rows[0] if rows else None


async def create_pool(database_url: str) -> asyncpg.Pool:
    """Create an asyncpg connection pool.

    Call once at application startup; pass the pool to TenantDB.

    statement_cache_size=0: asyncpg caches prepared statements per-connection.
    Cached statements are prepared OUTSIDE our SET LOCAL transaction, so PostgreSQL
    evaluates schema permissions as the connection role (no tenant_id set yet)
    → InsufficientPrivilegeError on schemas with RLS / restricted access.
    Disabling the cache forces asyncpg to use unprepared (simple) protocol for
    every query, ensuring SET LOCAL is always in scope.
    """
    return await asyncpg.create_pool(
        database_url,
        min_size=2,
        max_size=10,
        statement_cache_size=0,
    )
