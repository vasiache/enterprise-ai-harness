
"""
scripts/admin/user.py - User management for platform.users.

Commands:
  create      Create a new user (with optional tg_id)
  delete      Delete a user by email
  list        List users of a tenant (optionally filtered by org)
  set-tg      Set (or update) tg_id for an existing user
  unset-tg    Clear tg_id (detach Telegram account)
  set-role    Change user role
  move-org    Move user to a different org within the same tenant

Usage examples:
  python scripts/admin/user.py create --tenant furnco --org management \\
      --email manager@furnco.dev --tg-id 123456789 --role user

  python scripts/admin/user.py list   --tenant furnco
  python scripts/admin/user.py list   --tenant furnco --org management

  python scripts/admin/user.py set-tg   --tenant furnco --email manager@furnco.dev --tg-id 123456789
  python scripts/admin/user.py unset-tg --tenant furnco --email manager@furnco.dev

  python scripts/admin/user.py set-role --tenant furnco --email manager@furnco.dev --role org_admin
  python scripts/admin/user.py move-org --tenant furnco --email manager@furnco.dev --org sales

  python scripts/admin/user.py delete --tenant furnco --email manager@furnco.dev --yes

Prerequisites:
  pip install asyncpg
  kubectl port-forward -n platform svc/postgres 5432:5432 --context kind-multitenant-agent-k8s
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import (
    connect, confirm,
    require_tenant, require_org,
    list_tenants, list_orgs,
    prompt, prompt_int, prompt_choice,
)

VALID_ROLES = ("user", "org_admin", "tenant_admin")



async def get_user_by_email(conn, tenant_id: str, email: str):
    return await conn.fetchrow(
        "SELECT id, tenant_id, org_id, email, tg_id, role "
        "FROM platform.users WHERE tenant_id=$1 AND email=$2",
        tenant_id, email,
    )


async def require_user(conn, tenant_id: str, email: str):
    row = await get_user_by_email(conn, tenant_id, email)
    if row is None:
        print(f"✗ User '{email}' not found in tenant '{tenant_id}'.")
        sys.exit(1)
    return row



async def cmd_create(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            tenants = await list_tenants(conn)
            print(f"  Tenants: {', '.join(tenants)}")
            args.tenant = prompt("Tenant ID")
        await require_tenant(conn, args.tenant)

        if not args.org:
            orgs = await list_orgs(conn, args.tenant)
            print(f"  Orgs: {', '.join(orgs)}")
            args.org = prompt("Org ID")
        await require_org(conn, args.tenant, args.org)

        if not args.email:
            args.email = prompt("Email")

        if args.tg_id is None and not args.no_tg:
            print("  (Telegram user ID - ask user to message @userinfobot to get it)")
            args.tg_id = prompt_int("Telegram user ID (bigint)", required=False)

        if not args.role:
            args.role = prompt_choice("Role", list(VALID_ROLES), default="user")

        existing = await get_user_by_email(conn, args.tenant, args.email)
        if existing:
            print(f"✗ User '{args.email}' already exists in tenant '{args.tenant}'.")
            print(f"  Use 'set-tg' or 'set-role' to update.")
            sys.exit(1)

        row = await conn.fetchrow(
            """
            INSERT INTO platform.users (tenant_id, org, org_id, email, tg_id, role)
            VALUES ($1, $2, $2, $3, $4, $5)
            RETURNING id
            """,
            args.tenant, args.org, args.email, args.tg_id, args.role,
        )
        assert row is not None
        print(f"\n✓ User created:")
        _print_user(args.tenant, args.org, args.email, args.tg_id, args.role, str(row["id"]))


async def cmd_delete(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            args.tenant = prompt("Tenant ID")
        if not args.email:
            args.email = prompt("User email")

        row = await require_user(conn, args.tenant, args.email)

        if not args.yes:
            tg = f" tg_id={row['tg_id']}" if row["tg_id"] else ""
            if not confirm(
                f"Delete user '{args.email}' (org={row['org_id']}, role={row['role']}{tg})?"
            ):
                print("Aborted.")
                return

        await conn.execute(
            "DELETE FROM platform.users WHERE tenant_id=$1 AND email=$2",
            args.tenant, args.email,
        )
        print(f"✓ User '{args.email}' deleted from tenant '{args.tenant}'.")


async def cmd_list(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            tenants = await list_tenants(conn)
            print(f"  Tenants: {', '.join(tenants)}")
            args.tenant = prompt("Tenant ID")

        if args.org:
            rows = await conn.fetch(
                "SELECT org_id, email, tg_id, role FROM platform.users "
                "WHERE tenant_id=$1 AND org_id=$2 ORDER BY org_id, email",
                args.tenant, args.org,
            )
        else:
            rows = await conn.fetch(
                "SELECT org_id, email, tg_id, role FROM platform.users "
                "WHERE tenant_id=$1 ORDER BY org_id, email",
                args.tenant,
            )

        if not rows:
            print(f"  (no users)")
            return

        print(f"\n  {'ORG':<20} {'EMAIL':<35} {'TG_ID':<14} ROLE")
        print(f"  {'─'*20} {'─'*35} {'─'*14} {'─'*15}")
        for r in rows:
            tg = str(r["tg_id"]) if r["tg_id"] else "-"
            print(f"  {r['org_id']:<20} {r['email']:<35} {tg:<14} {r['role']}")


async def cmd_set_tg(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            args.tenant = prompt("Tenant ID")
        if not args.email:
            args.email = prompt("User email")

        row = await require_user(conn, args.tenant, args.email)

        if args.tg_id is None:
            print(f"  Current tg_id: {row['tg_id'] or '-'}")
            print("  (get Telegram ID: message @userinfobot)")
            args.tg_id = prompt_int("New Telegram user ID", required=True)

        await conn.execute(
            "UPDATE platform.users SET tg_id=$3 WHERE tenant_id=$1 AND email=$2",
            args.tenant, args.email, args.tg_id,
        )
        print(f"✓ tg_id={args.tg_id} set for '{args.email}' in tenant '{args.tenant}'.")


async def cmd_unset_tg(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            args.tenant = prompt("Tenant ID")
        if not args.email:
            args.email = prompt("User email")

        row = await require_user(conn, args.tenant, args.email)

        if not row["tg_id"]:
            print(f"  User '{args.email}' has no tg_id - nothing to do.")
            return

        if not args.yes:
            if not confirm(f"Detach tg_id={row['tg_id']} from '{args.email}'?"):
                print("Aborted.")
                return

        await conn.execute(
            "UPDATE platform.users SET tg_id=NULL WHERE tenant_id=$1 AND email=$2",
            args.tenant, args.email,
        )
        print(f"✓ tg_id cleared for '{args.email}'.")


async def cmd_set_role(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            args.tenant = prompt("Tenant ID")
        if not args.email:
            args.email = prompt("User email")

        row = await require_user(conn, args.tenant, args.email)

        if not args.role:
            print(f"  Current role: {row['role']}")
            args.role = prompt_choice("New role", list(VALID_ROLES), default=row["role"])

        await conn.execute(
            "UPDATE platform.users SET role=$3 WHERE tenant_id=$1 AND email=$2",
            args.tenant, args.email, args.role,
        )
        print(f"✓ Role set to '{args.role}' for '{args.email}'.")


async def cmd_move_org(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            args.tenant = prompt("Tenant ID")
        if not args.email:
            args.email = prompt("User email")

        row = await require_user(conn, args.tenant, args.email)

        if not args.org:
            orgs = await list_orgs(conn, args.tenant)
            print(f"  Current org: {row['org_id']}")
            print(f"  Available: {', '.join(orgs)}")
            args.org = prompt("New org ID")

        await require_org(conn, args.tenant, args.org)

        await conn.execute(
            "UPDATE platform.users SET org=$3, org_id=$3 WHERE tenant_id=$1 AND email=$2",
            args.tenant, args.email, args.org,
        )
        print(f"✓ User '{args.email}' moved to org '{args.org}' in tenant '{args.tenant}'.")



def _print_user(tenant_id, org_id, email, tg_id, role, uid=""):
    if uid:
        print(f"  id:        {uid}")
    print(f"  tenant_id: {tenant_id}")
    print(f"  org_id:    {org_id}")
    print(f"  email:     {email}")
    print(f"  tg_id:     {tg_id or '-'}")
    print(f"  role:      {role}")



COMMANDS = {
    "create":   cmd_create,
    "delete":   cmd_delete,
    "list":     cmd_list,
    "set-tg":   cmd_set_tg,
    "unset-tg": cmd_unset_tg,
    "set-role": cmd_set_role,
    "move-org": cmd_move_org,
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="User admin for platform.users",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("command", choices=list(COMMANDS))
    p.add_argument("--tenant",           help="Tenant ID")
    p.add_argument("--org",              help="Org ID")
    p.add_argument("--email",            help="User email")
    p.add_argument("--tg-id", dest="tg_id", type=int, default=None,
                   help="Telegram user ID (bigint)")
    p.add_argument("--no-tg", action="store_true",
                   help="Create user without tg_id")
    p.add_argument("--role",  choices=VALID_ROLES, help="User role")
    p.add_argument("--yes", "-y", action="store_true",
                   help="Skip confirmation prompts")
    p.add_argument("--dsn",              help="Postgres DSN (overrides DATABASE_URL)")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(COMMANDS[args.command](args))


if __name__ == "__main__":
    main()
