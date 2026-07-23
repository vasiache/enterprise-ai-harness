
"""Verify baseline migration invariants for local Phase 1 checks."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

sys.path.insert(0, str(Path(__file__).parent))
from db import connect

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"
OK = f"{GREEN}✓{RESET}"
FAIL = f"{RED}✗{RESET}"

CheckFn = Callable[[Any], Awaitable[str | None]]


async def check_platform_tenants_rls(conn: Any) -> str | None:
    row = await conn.fetchrow(
        """
        SELECT rowsecurity
        FROM pg_tables
        WHERE schemaname = 'platform' AND tablename = 'tenants'
        """
    )
    if row is None:
        return "platform.tenants is missing"
    if not row["rowsecurity"]:
        return "platform.tenants rowsecurity is disabled"
    return None


async def check_users_org_fk(conn: Any) -> str | None:
    row = await conn.fetchrow(
        """
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'platform.users'::regclass
          AND conname = 'users_tenant_org_fk'
        """
    )
    if row is None:
        return "users_tenant_org_fk is missing on platform.users"
    return None


async def check_no_orphan_org_refs(conn: Any) -> str | None:
    orphan_count = await conn.fetchval(
        """
        SELECT COUNT(*)::int
        FROM platform.users u
        WHERE NOT EXISTS (
            SELECT 1
            FROM platform.orgs o
            WHERE o.tenant_id = u.tenant_id AND o.id = u.org_id
        )
        """
    )
    if orphan_count != 0:
        return f"found {orphan_count} orphan platform.users org reference(s)"
    return None


async def check_fk_exists(conn: Any, conrelid: str, conname: str) -> str | None:
    """Generic: check that a named FK constraint exists on a table."""
    row = await conn.fetchrow(
        """
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = $1::regclass
          AND conname = $2
          AND contype = 'f'
        """,
        conrelid,
        conname,
    )
    if row is None:
        return f"{conname} is missing on {conrelid}"
    return None


async def check_fk_audit_log_tenant(conn: Any) -> str | None:
    return await check_fk_exists(conn, "platform.audit_log", "fk_audit_log_tenant")


async def check_fk_usage_daily_tenant(conn: Any) -> str | None:
    return await check_fk_exists(conn, "platform.usage_daily", "fk_usage_daily_tenant")


async def check_fk_leads_tenant(conn: Any) -> str | None:
    return await check_fk_exists(conn, "orders.leads", "fk_leads_tenant")


CHECKS: tuple[tuple[str, CheckFn], ...] = (
    ("platform.tenants has RLS", check_platform_tenants_rls),
    ("platform.users -> platform.orgs FK exists", check_users_org_fk),
    ("no orphan org references", check_no_orphan_org_refs),
    ("platform.audit_log -> platform.tenants FK exists", check_fk_audit_log_tenant),
    ("platform.usage_daily -> platform.tenants FK exists", check_fk_usage_daily_tenant),
    ("orders.leads -> platform.tenants FK exists", check_fk_leads_tenant),
)


async def run_checks(conn: Any) -> None:
    for label, check in CHECKS:
        error = await check(conn)
        if error is not None:
            print(f"{FAIL} {label}: {error}", file=sys.stderr)
            raise SystemExit(1)
        print(f"{OK} {label}")
    print(f"{OK} migration baseline is healthy")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify baseline migration invariants for local Phase 1 checks."
    )
    parser.add_argument("--dsn", help="Postgres DSN (overrides DATABASE_URL)")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    async with connect(args.dsn) as conn:
        await run_checks(conn)


if __name__ == "__main__":
    asyncio.run(main())
