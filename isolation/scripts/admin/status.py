
"""
scripts/admin/status.py - Show status of a tenant (DB + K8s).

Commands:
  show        Full status: DB records + K8s pods/agents/bot
  db          DB only (no kubectl)
  k8s         K8s only (no DB connection needed)

Usage examples:
  python scripts/admin/status.py show --tenant alpha
  python scripts/admin/status.py db   --tenant alpha
  python scripts/admin/status.py k8s  --tenant alpha

Prerequisites:
  pip install asyncpg
  kubectl port-forward -n platform svc/postgres 5432:5432 --context kind-multitenant-agent-k8s
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import connect, list_tenants, prompt

KUBE_CTX = os.environ.get("KUBE_CONTEXT", "kind-multitenant-agent-k8s")



def kubectl(*args: str, check: bool = False) -> str:
    """Run kubectl and return stdout. Never raises by default."""
    cmd = ["kubectl", "--context", KUBE_CTX, *args]
    result = subprocess.run(cmd, capture_output=True, text=True, check=check)
    return result.stdout.strip()


def kubectl_json(*args: str) -> dict | None:
    out = kubectl(*args, "-o", "json")
    if not out:
        return None
    try:
        data = json.loads(out)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None



async def show_db(conn, tenant_id: str) -> None:
    print(f"\n{'═'*60}")
    print(f"  DB - tenant '{tenant_id}'")
    print(f"{'═'*60}")

    row = await conn.fetchrow(
        "SELECT id, plan, display_name, disabled_at, created_at "
        "FROM platform.tenants WHERE id=$1",
        tenant_id,
    )
    if not row:
        print(f"  ✗ Tenant '{tenant_id}' NOT FOUND in platform.tenants")
        return

    status = "DISABLED" if row["disabled_at"] else "active"
    print(f"\n  Tenant:  {row['id']}  [{status}]")
    print(f"  Plan:    {row['plan']}")
    print(f"  Name:    {row['display_name'] or '-'}")
    print(f"  Created: {row['created_at'].strftime('%Y-%m-%d %H:%M') if row['created_at'] else '-'}")

    orgs = await conn.fetch(
        "SELECT id, display_name, "
        "CASE WHEN tg_bot_token IS NOT NULL THEN 'SET' ELSE '-' END AS bot "
        "FROM platform.orgs WHERE tenant_id=$1 ORDER BY id",
        tenant_id,
    )
    print(f"\n  Orgs ({len(orgs)}):")
    if orgs:
        print(f"    {'ID':<20} {'BOT':<6}  DISPLAY NAME")
        print(f"    {'─'*20} {'─'*6}  {'─'*28}")
        for o in orgs:
            print(f"    {o['id']:<20} {o['bot']:<6}  {o['display_name'] or '-'}")
    else:
        print("    (none)")

    users = await conn.fetch(
        "SELECT org_id, email, tg_id, role "
        "FROM platform.users WHERE tenant_id=$1 ORDER BY org_id, email",
        tenant_id,
    )
    print(f"\n  Users ({len(users)}):")
    if users:
        print(f"    {'ORG':<20} {'EMAIL':<35} {'TG_ID':<14} ROLE")
        print(f"    {'─'*20} {'─'*35} {'─'*14} {'─'*14}")
        for u in users:
            tg = str(u["tg_id"]) if u["tg_id"] else "-"
            print(f"    {u['org_id']:<20} {u['email']:<35} {tg:<14} {u['role']}")
    else:
        print("    (none)")


def show_k8s(tenant_id: str) -> None:
    ns = f"tenant-{tenant_id}"
    print(f"\n{'═'*60}")
    print(f"  K8s - namespace '{ns}'")
    print(f"{'═'*60}")

    ns_out = kubectl("get", "namespace", ns, "--ignore-not-found")
    if not ns_out:
        print(f"  ✗ Namespace '{ns}' NOT FOUND")
        return
    print(f"\n  Namespace: {ns}  ✓")

    pods_data = kubectl_json("get", "pods", "-n", ns)
    pods = pods_data.get("items", []) if pods_data else []
    print(f"\n  Pods ({len(pods)}):")
    if pods:
        print(f"    {'NAME':<45} {'READY':<7} STATUS")
        print(f"    {'─'*45} {'─'*7} {'─'*12}")
        for pod in pods:
            name   = pod["metadata"]["name"]
            phase  = pod["status"].get("phase", "Unknown")
            cs     = pod["status"].get("containerStatuses", [])
            if cs:
                ready_count = sum(1 for c in cs if c.get("ready"))
                total_count = len(cs)
                ready = f"{ready_count}/{total_count}"
            else:
                ready = "0/0"
            print(f"    {name:<45} {ready:<7} {phase}")
    else:
        print("    (none)")

    agents_data = kubectl_json("get", "agents", "-n", ns)
    agents = agents_data.get("items", []) if agents_data else []
    print(f"\n  Agents ({len(agents)}):")
    if agents:
        print(f"    {'NAME':<30} {'READY':<7} ACCEPTED")
        print(f"    {'─'*30} {'─'*7} {'─'*8}")
        for ag in agents:
            name = ag["metadata"]["name"]
            conds = {c["type"]: c["status"] for c in ag.get("status", {}).get("conditions", [])}
            ready    = "True" if conds.get("Ready")    == "True" else "False"
            accepted = "True" if conds.get("Accepted") == "True" else "False"
            print(f"    {name:<30} {ready:<7} {accepted}")
    else:
        print("    (none)")

    mcp_data = kubectl_json("get", "remotemcpservers", "-n", ns)
    mcps = mcp_data.get("items", []) if mcp_data else []
    if mcps:
        print(f"\n  RemoteMCPServers ({len(mcps)}):")
        for m in mcps:
            name = m["metadata"]["name"]
            conds = {c["type"]: c["status"] for c in m.get("status", {}).get("conditions", [])}
            accepted = "✓" if conds.get("Accepted") == "True" else "✗"
            url = m.get("spec", {}).get("url", "")
            print(f"    {accepted} {name:<30}  {url}")

    tg_pods = [p for p in pods if "tg-bot" in p["metadata"]["name"]]
    if tg_pods:
        print(f"\n  TG Bot pods ({len(tg_pods)}):")
        for pod in tg_pods:
            name  = pod["metadata"]["name"]
            phase = pod["status"].get("phase", "Unknown")
            print(f"    {name}  [{phase}]")
            log = kubectl("logs", "-n", ns, pod["metadata"]["name"], "--tail=3")
            if log:
                for line in log.splitlines():
                    print(f"      {line}")
    else:
        print(f"\n  TG Bot: not deployed (no bot token set via set-bot-token)")

    quota_data = kubectl_json("get", "resourcequota", "-n", ns)
    quotas = quota_data.get("items", []) if quota_data else []
    if quotas:
        print(f"\n  ResourceQuota:")
        for q in quotas:
            hard  = q.get("status", {}).get("hard", {})
            used  = q.get("status", {}).get("used", {})
            for key in sorted(hard):
                h = hard[key]
                u = used.get(key, "0")
                print(f"    {key:<35} {u:>8} / {h}")



async def cmd_show(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            tenants = await list_tenants(conn)
            print(f"  Tenants: {', '.join(tenants)}")
            args.tenant = prompt("Tenant ID")
        await show_db(conn, args.tenant)
    show_k8s(args.tenant)


async def cmd_db(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            tenants = await list_tenants(conn)
            print(f"  Tenants: {', '.join(tenants)}")
            args.tenant = prompt("Tenant ID")
        await show_db(conn, args.tenant)


async def cmd_k8s(args: argparse.Namespace) -> None:
    if not args.tenant:
        args.tenant = prompt("Tenant ID")
    show_k8s(args.tenant)



COMMANDS = {
    "show": cmd_show,
    "db":   cmd_db,
    "k8s":  cmd_k8s,
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Show tenant status (DB + K8s)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("command", choices=list(COMMANDS), nargs="?", default="show")
    p.add_argument("--tenant",           help="Tenant ID")
    p.add_argument("--dsn",              help="Postgres DSN (overrides DATABASE_URL)")
    p.add_argument("--context", dest="kube_context",
                   help=f"kubectl context (default: {KUBE_CTX})")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.kube_context:
        global KUBE_CTX
        KUBE_CTX = args.kube_context

    asyncio.run(COMMANDS[args.command](args))


if __name__ == "__main__":
    main()
