
"""
scripts/admin/tenant.py - Tenant and Org management.

Commands:
  create-tenant   Create a new tenant in platform.tenants
  delete-tenant   Delete tenant and all its orgs/users from DB + K8s namespace
  list-tenants    List all tenants

  create-org      Create an org inside a tenant
  delete-org      Delete an org (and its users) from a tenant
  list-orgs       List orgs of a tenant

  set-bot-token   Set or clear tg_bot_token for an org
  enable-tenant   Clear disabled_at (re-enable)
  disable-tenant  Set disabled_at = now()

  deploy          helm upgrade --install tenant-{id} (K8s namespace + agents + bot)
  undeploy        helm uninstall + kubectl delete namespace

Usage examples:
  python scripts/admin/tenant.py create-tenant --id tech-support --plan pro --name "TechSupport"
  python scripts/admin/tenant.py create-org --tenant tech-support --org support --name "Поддержка"
  python scripts/admin/tenant.py set-bot-token --tenant tech-support --org management --token "123:ABC"
  python scripts/admin/tenant.py deploy --tenant tech-support
  python scripts/admin/tenant.py delete-tenant --tenant tech-support --yes

Prerequisites:
  pip install asyncpg
  kubectl port-forward -n platform svc/postgres 5432:5432 --context kind-multitenant-agent-k8s
  helm, kubectl in PATH
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json as _json
import os
import secrets as _secrets
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import (
    ADMIN_DSN, connect, confirm,
    get_tenant, require_tenant, get_org, require_org,
    list_tenants, list_orgs, prompt, prompt_choice,
)

ROOT_DIR = Path(__file__).parent.parent.parent
HELM_DIR = ROOT_DIR / "helm" / "charts" / "tenant"

VALID_PLANS = ("free", "pro", "enterprise")
KUBE_CTX = os.environ.get("KUBE_CONTEXT", "kind-multitenant-agent-k8s")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")



def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, text=True, capture_output=False)


def _get_postgres_pod() -> str:
    """Return the name of the running postgres pod in ns:platform."""
    result = subprocess.run(
        ["kubectl", "get", "pod", "-n", "platform",
         "--context", KUBE_CTX,
         "-l", "app=postgres",
         "-o", "jsonpath={.items[0].metadata.name}"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def _psql(sql: str) -> subprocess.CompletedProcess:
    """Run a SQL statement in the postgres pod."""
    pod = _get_postgres_pod()
    if not pod:
        print("  ⚠ Could not find postgres pod - skipping SQL")
        return subprocess.CompletedProcess([], returncode=1)
    return subprocess.run(
        ["kubectl", "exec", pod, "-n", "platform",
         "--context", KUBE_CTX,
         "--", "env", f"PGPASSWORD={POSTGRES_PASSWORD}",
         "psql", "-U", "supabase_admin", "-h", "localhost", "-d", "postgres", "-c", sql],
        capture_output=True, text=True,
    )


def _copy_secret_to_namespace(secret_name: str, src_ns: str, dst_ns: str) -> None:
    """Copy a K8s Secret from src_ns to dst_ns, stripping namespace-specific metadata."""
    print(f"  Copying Secret {secret_name}: {src_ns} → {dst_ns}")
    get = subprocess.run(
        ["kubectl", "get", "secret", secret_name,
         "--namespace", src_ns, "--context", KUBE_CTX, "-o", "json"],
        capture_output=True, text=True,
    )
    if get.returncode != 0:
        print(f"  ⚠ Secret '{secret_name}' not found in ns:{src_ns} - skipping copy")
        return

    s = _json.loads(get.stdout)
    s["metadata"] = {"name": s["metadata"]["name"], "namespace": dst_ns}
    s.pop("status", None)

    apply = subprocess.run(
        ["kubectl", "apply", "--context", KUBE_CTX, "-f", "-"],
        input=_json.dumps(s), text=True, capture_output=False,
    )
    if apply.returncode != 0:
        print(f"  ⚠ Failed to copy Secret '{secret_name}' to ns:{dst_ns}")


def helm_deploy(tenant_id: str, tenant_display_name: str, extra_sets: list[str] | None = None) -> None:
    """Run helm upgrade --install for a tenant namespace."""
    openai_key          = os.environ.get("OPENAI_API_KEY", "placeholder")
    openai_model        = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    openai_base         = os.environ.get("OPENAI_BASE_URL", "")
    tg_bot_image        = os.environ.get("TG_BOT_IMAGE", "localhost:5001/tg-bot:latest")
    tenant_info_image   = os.environ.get("TENANT_INFO_IMAGE", "localhost:5001/tenant-info-tool:latest")
    order_tracker_image = os.environ.get("ORDER_TRACKER_IMAGE", "localhost:5001/order-tracker:latest")
    tg_proxy            = os.environ.get("TG_HTTPS_PROXY", "")
    pg_password         = os.environ.get("POSTGRES_PASSWORD", "postgres")
    pg_app_password     = os.environ.get("POSTGRES_APP_PASSWORD", "apppassword")
    enable_orders       = os.environ.get("ENABLE_ORDER_TRACKER", "false").lower() == "true"
    release = f"tenant-{tenant_id}"
    ns      = f"tenant-{tenant_id}"

    cmd = [
        "helm", "upgrade", "--install", release, str(HELM_DIR),
        "--namespace", ns,
        "--create-namespace",
        "--kube-context", KUBE_CTX,
        "--set", f"tenant.id={tenant_id}",
        "--set", f"tenant.displayName={tenant_display_name}",
        "--set", f"openai.apiKey={openai_key}",
        "--set", f"openai.model={openai_model}",
        "--set", f"postgres.password={pg_password}",
        "--set", f"postgres.appUserPassword={pg_app_password}",
        "--set", f"tenantInfoTool.image={tenant_info_image}",
        "--set", f"tgBot.image={tg_bot_image}",
        "--set", f"orderTracker.image={order_tracker_image}",
        "--set", f"orderTracker.enabled={'true' if enable_orders else 'false'}",
        "--timeout", "3m",
    ]
    if openai_base:
        cmd += ["--set", f"openai.baseUrl={openai_base}"]
    if tg_proxy:
        cmd += ["--set", f"tgBot.httpsProxy={tg_proxy}"]
    if extra_sets:
        for s in extra_sets:
            cmd += ["--set", s]

    subprocess.run(
        ["kubectl", "create", "namespace", ns, "--context", KUBE_CTX],
        check=False, capture_output=True,
    )
    subprocess.run(
        ["kubectl", "annotate", "namespace", ns,
         "meta.helm.sh/release-name=" + release,
         "meta.helm.sh/release-namespace=" + ns,
         "--overwrite", "--context", KUBE_CTX],
        check=False, capture_output=True,
    )
    subprocess.run(
        ["kubectl", "label", "namespace", ns,
         "app.kubernetes.io/managed-by=Helm",
         "--overwrite", "--context", KUBE_CTX],
        check=False, capture_output=True,
    )

    run_cmd(cmd)

    for label_ns in [ns, "kube-system", "kagent", "platform"]:
        run_cmd([
            "kubectl", "label", "namespace", label_ns,
            f"kubernetes.io/metadata.name={label_ns}",
            "--context", KUBE_CTX,
            "--overwrite",
        ], check=False)



async def cmd_create_tenant(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.id:
            args.id = prompt("Tenant ID (slug, e.g. tech-support)")
        if not args.plan:
            args.plan = prompt_choice("Plan", list(VALID_PLANS), default="free")
        if not args.name:
            args.name = prompt("Display name", required=False)

        existing = await get_tenant(conn, args.id)
        if existing:
            print(f"✗ Tenant '{args.id}' already exists.")
            sys.exit(1)

        await conn.execute(
            "INSERT INTO platform.tenants (id, plan, display_name) VALUES ($1, $2, $3)",
            args.id, args.plan, args.name or None,
        )
        print(f"✓ Tenant '{args.id}' created (plan={args.plan})")
        print(f"\nNext steps:")
        print(f"  python scripts/admin/tenant.py create-org --tenant {args.id} --org management")
        print(f"  python scripts/admin/tenant.py deploy      --tenant {args.id}")


async def cmd_delete_tenant(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            tenants = await list_tenants(conn)
            print(f"  Tenants: {', '.join(tenants)}")
            args.tenant = prompt("Tenant ID to delete")

        await require_tenant(conn, args.tenant)

        if not args.yes:
            if not confirm(
                f"Delete tenant '{args.tenant}' + all orgs, users AND K8s namespace?"
            ):
                print("Aborted.")
                return

        release = f"tenant-{args.tenant}"
        ns = f"tenant-{args.tenant}"
        print("\n── K8s ──────────────────────────────────────────────────")
        run_cmd(
            ["helm", "uninstall", release, "-n", ns, "--kube-context", KUBE_CTX],
            check=False,
        )
        run_cmd(
            ["kubectl", "delete", "namespace", ns,
             "--context", KUBE_CTX, "--wait=false", "--ignore-not-found"],
            check=False,
        )

        print("\n── DB ───────────────────────────────────────────────────")
        await conn.execute(
            "DELETE FROM platform.users  WHERE tenant_id = $1", args.tenant
        )
        await conn.execute(
            "DELETE FROM platform.orgs   WHERE tenant_id = $1", args.tenant
        )
        await conn.execute(
            "DELETE FROM platform.tenants WHERE id = $1", args.tenant
        )
        print(f"✓ Tenant '{args.tenant}' deleted from DB.")


async def cmd_list_tenants(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        rows = await conn.fetch(
            "SELECT id, plan, display_name, disabled_at FROM platform.tenants ORDER BY id"
        )
        if not rows:
            print("  (no tenants)")
            return
        print(f"\n  {'ID':<20} {'PLAN':<12} {'DISABLED':<10}  DISPLAY NAME")
        print(f"  {'─'*20} {'─'*12} {'─'*10}  {'─'*30}")
        for r in rows:
            dis = "yes" if r["disabled_at"] else ""
            print(f"  {r['id']:<20} {r['plan']:<12} {dis:<10}  {r['display_name'] or ''}")


async def cmd_enable_tenant(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            args.tenant = prompt("Tenant ID")
        await require_tenant(conn, args.tenant)
        await conn.execute(
            "UPDATE platform.tenants SET disabled_at = NULL WHERE id = $1", args.tenant
        )
        print(f"✓ Tenant '{args.tenant}' enabled.")


async def cmd_disable_tenant(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            args.tenant = prompt("Tenant ID")
        await require_tenant(conn, args.tenant)
        await conn.execute(
            "UPDATE platform.tenants SET disabled_at = now() WHERE id = $1", args.tenant
        )
        print(f"✓ Tenant '{args.tenant}' disabled.")


async def cmd_create_org(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            tenants = await list_tenants(conn)
            print(f"  Tenants: {', '.join(tenants)}")
            args.tenant = prompt("Tenant ID")
        await require_tenant(conn, args.tenant)

        if not args.org:
            args.org = prompt("Org ID (e.g. sales, management)")
        if not args.name:
            args.name = prompt("Display name", required=False)

        existing = await get_org(conn, args.tenant, args.org)
        if existing:
            print(f"✗ Org '{args.org}' already exists in tenant '{args.tenant}'.")
            sys.exit(1)

        await conn.execute(
            "INSERT INTO platform.orgs (tenant_id, id, display_name) VALUES ($1, $2, $3)",
            args.tenant, args.org, args.name or None,
        )
        print(f"✓ Org '{args.tenant}/{args.org}' created.")
        print(f"\nTo attach a TG Bot:")
        print(f"  python scripts/admin/tenant.py set-bot-token "
              f"--tenant {args.tenant} --org {args.org} --token YOUR_TOKEN")


async def cmd_delete_org(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            args.tenant = prompt("Tenant ID")
        if not args.org:
            orgs = await list_orgs(conn, args.tenant)
            print(f"  Orgs: {', '.join(orgs)}")
            args.org = prompt("Org ID to delete")

        await require_org(conn, args.tenant, args.org)

        if not args.yes:
            if not confirm(f"Delete org '{args.tenant}/{args.org}' and its users?"):
                print("Aborted.")
                return

        await conn.execute(
            "DELETE FROM platform.users WHERE tenant_id=$1 AND org_id=$2",
            args.tenant, args.org,
        )
        await conn.execute(
            "DELETE FROM platform.orgs WHERE tenant_id=$1 AND id=$2",
            args.tenant, args.org,
        )
        print(f"✓ Org '{args.tenant}/{args.org}' deleted.")


async def cmd_list_orgs(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            tenants = await list_tenants(conn)
            print(f"  Tenants: {', '.join(tenants)}")
            args.tenant = prompt("Tenant ID")
        await require_tenant(conn, args.tenant)

        rows = await conn.fetch(
            "SELECT id, display_name, "
            "CASE WHEN tg_bot_token IS NOT NULL THEN 'set' ELSE '-' END AS bot "
            "FROM platform.orgs WHERE tenant_id=$1 ORDER BY id",
            args.tenant,
        )
        if not rows:
            print(f"  (no orgs in tenant '{args.tenant}')")
            return
        print(f"\n  {'ORG ID':<20} {'BOT':<6}  DISPLAY NAME")
        print(f"  {'─'*20} {'─'*6}  {'─'*30}")
        for r in rows:
            print(f"  {r['id']:<20} {r['bot']:<6}  {r['display_name'] or ''}")


async def cmd_set_bot_token(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            args.tenant = prompt("Tenant ID")
        if not args.org:
            orgs = await list_orgs(conn, args.tenant)
            print(f"  Orgs: {', '.join(orgs)}")
            args.org = prompt("Org ID")

        await require_org(conn, args.tenant, args.org)

        if args.clear:
            await conn.execute(
                "UPDATE platform.orgs SET tg_bot_token=NULL WHERE tenant_id=$1 AND id=$2",
                args.tenant, args.org,
            )
            print(f"✓ Bot token cleared for '{args.tenant}/{args.org}'.")
        else:
            if not args.token:
                args.token = prompt("Bot token (from @BotFather)")
            await conn.execute(
                "UPDATE platform.orgs SET tg_bot_token=$3 WHERE tenant_id=$1 AND id=$2",
                args.tenant, args.org, args.token,
            )
            print(f"✓ Bot token set for '{args.tenant}/{args.org}'.")
            print(f"\nTo apply to K8s (restart bot pod):")
            print(f"  python scripts/admin/tenant.py deploy "
                  f"--tenant {args.tenant} --org-bot {args.org}:{args.token}")


async def cmd_deploy(args: argparse.Namespace) -> None:
    """helm upgrade --install tenant-{id}, reads bot tokens from DB."""
    async with connect(args.dsn) as conn:
        if not args.tenant:
            tenants = await list_tenants(conn)
            print(f"  Tenants: {', '.join(tenants)}")
            args.tenant = prompt("Tenant ID")

        row = await require_tenant(conn, args.tenant)
        tenant_display_name = row["display_name"] or args.tenant.capitalize()

        org_rows = await conn.fetch(
            "SELECT id, tg_bot_token FROM platform.orgs WHERE tenant_id=$1 ORDER BY id",
            args.tenant,
        )

    print(f"\n── Deploying tenant-{args.tenant} ─────────────────────────────")
    extra: list[str] = []
    ns = f"tenant-{args.tenant}"

    subprocess.run(
        ["kubectl", "create", "namespace", ns, "--context", KUBE_CTX],
        check=False, capture_output=True,
    )

    for i, org in enumerate(org_rows):
        if org["tg_bot_token"]:
            secret_name = f"tg-bot-{org['id']}-secret"
            dry_run = subprocess.run(
                [
                    "kubectl", "create", "secret", "generic", secret_name,
                    f"--from-literal=BOT_TOKEN={org['tg_bot_token']}",
                    "-n", ns, "--context", KUBE_CTX,
                    "--dry-run=client", "-o", "yaml",
                ],
                capture_output=True, text=True, check=True,
            )
            subprocess.run(
                ["kubectl", "apply", "--context", KUBE_CTX, "-f", "-"],
                input=dry_run.stdout, text=True, check=True,
            )
            print(f"  ✓ Secret {secret_name} applied in ns:{ns}")
            extra += [f"orgs[{i}].id={org['id']}",
                      f"orgs[{i}].botEnabled=true"]

    helm_deploy(args.tenant, tenant_display_name, extra)
    print(f"\n✓ Tenant '{args.tenant}' deployed.")
    print(f"\nVerify:")
    print(f"  kubectl get agents,pods -n tenant-{args.tenant} --context {KUBE_CTX}")


async def cmd_undeploy(args: argparse.Namespace) -> None:
    async with connect(args.dsn) as conn:
        if not args.tenant:
            args.tenant = prompt("Tenant ID")
        await require_tenant(conn, args.tenant)

    if not args.yes:
        if not confirm(f"Undeploy K8s namespace 'tenant-{args.tenant}'? (DB is NOT changed)"):
            print("Aborted.")
            return

    release = f"tenant-{args.tenant}"
    ns = f"tenant-{args.tenant}"
    run_cmd(["helm", "uninstall", release, "-n", ns, "--kube-context", KUBE_CTX], check=False)
    run_cmd([
        "kubectl", "delete", "namespace", ns,
        "--context", KUBE_CTX, "--wait=false", "--ignore-not-found",
    ], check=False)
    print(f"✓ Namespace 'tenant-{args.tenant}' undeployed (DB intact).")



COMMANDS = {
    "create-tenant":  cmd_create_tenant,
    "delete-tenant":  cmd_delete_tenant,
    "list-tenants":   cmd_list_tenants,
    "enable-tenant":  cmd_enable_tenant,
    "disable-tenant": cmd_disable_tenant,
    "create-org":     cmd_create_org,
    "delete-org":     cmd_delete_org,
    "list-orgs":      cmd_list_orgs,
    "set-bot-token":  cmd_set_bot_token,
    "deploy":         cmd_deploy,
    "undeploy":       cmd_undeploy,
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Tenant and Org admin",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("command", choices=list(COMMANDS), help="Command to run")
    p.add_argument("--tenant",  help="Tenant ID")
    p.add_argument("--org",     help="Org ID")
    p.add_argument("--id",      help="New tenant ID (create-tenant)")
    p.add_argument("--plan",    choices=VALID_PLANS, help="Plan (create-tenant)")
    p.add_argument("--name",    help="Display name")
    p.add_argument("--token",   help="TG Bot token (set-bot-token)")
    p.add_argument("--clear",   action="store_true", help="Clear bot token")
    p.add_argument("--yes",  "-y", action="store_true", help="Skip confirmation prompts")
    p.add_argument("--dsn",     help="Postgres DSN (overrides DATABASE_URL)")
    p.add_argument("--context", dest="kube_context", help=f"kubectl context (default: {KUBE_CTX})")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.kube_context:
        global KUBE_CTX
        KUBE_CTX = args.kube_context

    fn = COMMANDS[args.command]
    asyncio.run(fn(args))


if __name__ == "__main__":
    main()
