"""
scripts/admin/db.py - shared DB connection and helpers for admin scripts.

Connection priority:
  1. --dsn CLI argument (passed explicitly)
  2. DATABASE_URL environment variable
  3. Built from POSTGRES_PASSWORD env var (default: postgres)
     → postgresql://supabase_admin:<POSTGRES_PASSWORD>@localhost:5432/postgres
     (assumes kubectl port-forward -n platform svc/postgres 5432:5432)
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg not installed. Run: pip install asyncpg")
    sys.exit(1)

_pg_password = os.environ.get("POSTGRES_PASSWORD", "postgres")
ADMIN_DSN = os.environ.get(
    "DATABASE_URL",
    f"postgresql://supabase_admin:{_pg_password}@localhost:5432/postgres",
)

HINT = (
    "\nHint: kubectl port-forward -n platform svc/postgres 5432:5432 "
    "--context kind-multitenant-agent-k8s"
)



def resolve_dsn(dsn: str | None = None) -> str:
    if dsn:
        return dsn
    if not os.environ.get("DATABASE_URL") and not os.environ.get("POSTGRES_PASSWORD"):
        print(
            "WARNING: POSTGRES_PASSWORD not set - using dev default 'postgres'. "
            "Source .env before running admin scripts.",
            file=sys.stderr,
        )
    return ADMIN_DSN


@asynccontextmanager
async def connect(dsn: str | None = None) -> AsyncIterator[asyncpg.Connection]:
    dsn = resolve_dsn(dsn)
    host_part = dsn.split("@")[-1] if "@" in dsn else dsn
    print(f"  db → {host_part}")
    try:
        conn: asyncpg.Connection = await asyncpg.connect(dsn)
    except Exception as exc:
        print(f"\n✗ Cannot connect to postgres: {exc}{HINT}")
        sys.exit(1)
    try:
        yield conn
    finally:
        await conn.close()



async def get_tenant(conn: asyncpg.Connection, tenant_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "SELECT id, plan, display_name, disabled_at "
        "FROM platform.tenants WHERE id = $1",
        tenant_id,
    )


async def require_tenant(conn: asyncpg.Connection, tenant_id: str) -> asyncpg.Record:
    row = await get_tenant(conn, tenant_id)
    if row is None:
        print(f"✗ Tenant '{tenant_id}' not found.")
        sys.exit(1)
    return row


async def get_org(conn: asyncpg.Connection, tenant_id: str, org_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "SELECT tenant_id, id, display_name, tg_bot_token "
        "FROM platform.orgs WHERE tenant_id = $1 AND id = $2",
        tenant_id, org_id,
    )


async def require_org(conn: asyncpg.Connection, tenant_id: str, org_id: str) -> asyncpg.Record:
    row = await get_org(conn, tenant_id, org_id)
    if row is None:
        print(f"✗ Org '{org_id}' not found in tenant '{tenant_id}'.")
        sys.exit(1)
    return row


async def list_tenants(conn: asyncpg.Connection) -> list[str]:
    rows = await conn.fetch("SELECT id FROM platform.tenants ORDER BY id")
    return [r["id"] for r in rows]


async def list_orgs(conn: asyncpg.Connection, tenant_id: str) -> list[str]:
    rows = await conn.fetch(
        "SELECT id FROM platform.orgs WHERE tenant_id = $1 ORDER BY id",
        tenant_id,
    )
    return [r["id"] for r in rows]



def prompt(label: str, default: str = "", required: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"  {label}{suffix}: ").strip()
        if not val:
            val = default
        if val or not required:
            return val
        print(f"    ✗ {label} is required.")


def prompt_int(label: str, required: bool = False) -> int | None:
    while True:
        raw = input(f"  {label} [skip]: ").strip()
        if not raw:
            if required:
                print(f"    ✗ {label} is required.")
                continue
            return None
        try:
            return int(raw)
        except ValueError:
            print("    ✗ Must be an integer.")


def prompt_choice(label: str, choices: list[str], default: str = "") -> str:
    choices_str = " | ".join(choices)
    suffix = f" [{default}]" if default else f" ({choices_str})"
    while True:
        val = input(f"  {label}{suffix}: ").strip() or default
        if val in choices:
            return val
        print(f"    ✗ Choose one of: {choices_str}")


def confirm(question: str) -> bool:
    val = input(f"  {question} [y/N]: ").strip().lower()
    return val in ("y", "yes")
