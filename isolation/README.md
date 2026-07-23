# isolation/: Part II — Borders Without Identity

A curated, self-contained slice of the working implementation behind the
[article series](../docs/articles/). It runs the first three layers of the
four-layer architecture, Input, Agent Loop and Execution, on a local Kind
cluster. Tenant isolation is enforced by infrastructure borders (namespace,
NetworkPolicy, PostgreSQL RLS) rather than by an Identity layer, which is not
yet present.

This directory is the companion to:
- **[DEPLOYMENT.md](DEPLOYMENT.md)**, the full deployment guide, isolation walk-through and day-2 ops.
- **[Part 1](../docs/articles/Toward%20a%20Four-Layer%20Architecture%20for%20Self-Hosted%20Enterprise%20AI%20Harnesses.md)**, the architectural frame this implements.

> This is a reference architecture, not a product. It is deliberately
> intermediate: three layers working end-to-end, identity deliberately deferred.

---

## What is here

```
scripts/
  setup-kind.sh          Orchestrator. Runs cluster/01→03→04→05→07.
  bootstrap-data.sh       Create demo tenants (alpha, beta) + orgs + users.
  build-tools.sh         Build tool/bot images, smart rebuild by source hash.
  kind-config.yaml       Kind cluster config (single control-plane, port 80/443).
  cluster/
    common.sh            Shared helpers (colors, wait_for_tcp, load_images, env).
    01_kind.sh           Cluster + local registry + namespaces + pre-pull images.
    03_platform.sh       Postgres + GoTrue (platform Helm chart).
    04_migrations.sh     Apply SQL migrations + create kagent DB/role.
    05_kagent.sh         kagent CRDs + kagent (external Postgres).
    07_tools.sh           Build + load tool images, deploy shared-tools.
  admin/
    tenant.py            Tenant/org lifecycle + helm deploy (secret bypasses Helm).
    user.py              User CRUD.
    db.py                asyncpg connection helpers.
    status.py            Cluster health snapshot.
    check_migrations.py  Migration verification.

helm/charts/
  platform/              Postgres + GoTrue (platform namespace).
  shared-tools/          ping-tool Deployment + Service + NetworkPolicy.
  tenant/                Per-tenant: Namespace, ResourceQuota, NetworkPolicy,
                         ModelConfig, echo/management Agent CRDs,
                         tenant-info-tool, order-tracker, tg-bot, RemoteMCPServers.

supabase/migrations/
  0001_init_platform.sql      tenants, users
  0002_audit_log.sql          audit_log + audit_actions
  0003_usage_daily.sql        usage_daily
  0004_orders_schema.sql      orders.leads (CRM)
  0005_rls_policies.sql        RLS on all tenant-scoped tables, app_user NOBYPASSRLS
  0006_kagent_db.sql          kagent role + database
  0007_orgs.sql               orgs (tenant sub-division), users.org_id FK
  0008_fk_tenant_scoped.sql   FK tenant_id to tenants(id) ON DELETE RESTRICT

tools/
  ping-tool/            Shared stateless MCP (health check).
  tenant-info-tool/     Per-tenant MCP. get_tenant_info / get_org_info (RLS).
  order-tracker/        Per-tenant MCP. leads lifecycle (new to qualified to sold/lost).

channels/
  tg-bot/               aiogram3 Telegram bot to A2A to kagent (one pod per org).

packages/saas-common/  Shared Python package for MCP tools + agents.
  saas_common/
    mcp_base.py        create_server(). FastMCP + tenant_id + DB pool lifespan.
    supabase_client.py TenantDB. Mandatory RLS wrapper (SET LOCAL + statement_cache_size=0).
    vault_client.py     Read secrets from Vault sidecar files.
    auth.py            JWT extraction helpers.
    logging.py         structlog.
    config.py          Settings dataclass (env).

tests/e2e/             test_ping_tool, test_memory_multi_turn, test_parallel_execution,
                       test_agent_routing (all green)
```

## What is NOT here (and why)

This is a curated public slice. The full private workspace also contains
vendored upstreams (a kagent fork, agentgateway), an Obsidian architecture vault,
and per-environment secrets. Those are intentionally excluded. What remains is
everything needed to understand and reproduce the three-layer intermediate
solution.

- No vendored upstreams. kagent and its CRDs are pulled from the OCI registry at
  install time (`05_kagent.sh`).
- No secrets. `.env.example` documents the required env vars; real `.env` is
  git-ignored.
- No `uv.lock`. Run `uv sync` to generate it for your environment.

## Quickstart

```bash
cp .env.example .env          # fill in OPENAI_API_KEY (+ optional TG tokens)
make up                       # full cluster: setup-kind.sh (01→03→04→05→07)
make bootstrap                # demo tenants alpha + beta
kubectl get agents -n tenant-alpha
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full guide.