# Deployment Guide: kagent with Tenant Isolation on Kind

This is the **intermediate reference implementation** that grounds the four-layer
architecture from [Part 1](../docs/articles/Toward%20a%20Four-Layer%20Architecture%20for%20Self-Hosted%20Enterprise%20AI%20Harnesses.md)
in running code. Three of the four layers are implemented end-to-end on a local
Kind cluster. The fourth, Identity, Policy & Audit, is intentionally absent and is
the subject of the next article.

> **What this is.** A reproducible, single-command local cluster where a Telegram
> message travels through Input, Agent Loop and Execution, and where two tenants
> (`tenant-alpha`, `tenant-beta`) are isolated from each other not by identity but
> by infrastructure borders: Kubernetes namespaces, NetworkPolicy, and PostgreSQL
> Row-Level Security.

> **What this is not.** Not production. Not a product. No AgentGateway, no JWT, no
> audit, no per-tenant Vault RBAC. Vault runs in dev mode. Isolation here is
> *borders without identity*: tenants are separated, but the system does not yet
> know *who* a user is within a tenant.

---

## At a glance

| Architectural layer | Status in this implementation |
|---|---|
| **Input** | ✅ Telegram bot (aiogram3) then A2A JSON-RPC then kagent |
| **Agent Loop (ReAct)** | ✅ kagent Declarative CRDs: `echo-agent`, `management-agent` (agent-as-tool) |
| **Execution** | ✅ FastMCP tools: `ping-tool` (shared), `tenant-info-tool`, `order-tracker` (per-tenant) |
| **Identity, Policy & Audit** | ❌ absent. Isolation is provided by borders (namespace + NetworkPolicy + RLS). |

---

## Prerequisites

- Docker, `kind`, `kubectl`, `helm` 3
- Python 3.12+ with [`uv`](https://docs.astral.sh/uv/)
- An OpenAI-compatible API key (any provider; `gpt-4o-mini` is the default model)

Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY` (and optionally a
Telegram bot token per tenant/org):

```bash
cp .env.example .env
# edit .env: set OPENAI_API_KEY, optionally TG_BOT_TOKEN_ALPHA_MANAGEMENT
```

---

## One-command bring-up

```bash
make up            # = bash scripts/setup-kind.sh
```

`setup-kind.sh` is an orchestrator that runs seven idempotent steps in order.
Every step is also runnable standalone (`bash scripts/cluster/04_migrations.sh`).

| Step | Script | What it does |
|---|---|---|
| 01 | `cluster/01_kind.sh` | Kind cluster (`v1.32.0`), local registry on `:5001`, containerd mirror config, namespaces (`kagent`, `platform`, `argocd`, `shared-tools`), pre-pull all images |
| 02 | `cluster/02_vault.sh` | HashiCorp Vault in **dev mode** (root token `root`, no persistence) |
| 03 | `cluster/03_platform.sh` | Platform Helm chart: Postgres 15 + GoTrue (auth) in `platform` ns, waits for `Available` |
| 04 | `cluster/04_migrations.sh` | Apply `supabase/migrations/0001–0008.sql` via `kubectl exec psql`; create `kagent` DB + role |
| 05 | `cluster/05_kagent.sh` | kagent CRDs + kagent (OCI Helm), pointed at the external Postgres (`postgres.platform.svc`) |
| 06 | `cluster/06_argocd.sh` | Argo CD (GitOps; used for tenant chart promotion) |
| 07 | `cluster/07_tools.sh` | Build tool/bot images (`build-tools.sh`, smart rebuild by source hash), load into Kind, deploy `shared-tools` |

After `make up` the platform and shared layers are up but **no tenants exist yet**.
Tenants are created and deployed separately. That is the whole point of the
onboarding flow below.

---

## Tenant onboarding (as code)

Tenants live in Postgres (`platform.tenants`, `platform.orgs`) and are deployed to
Kubernetes as one Helm release per tenant (`tenant-{id}` namespace). Onboarding is
two phases: **DB** (tenant + orgs + users), then **K8s** (helm install).

```bash
# 1. Bootstrap two demo tenants (alpha, beta) with orgs + users + bot tokens
make bootstrap         # = bash scripts/bootstrap-data.sh

# 2. Or onboard a single tenant manually:
python scripts/admin/tenant.py create-tenant --id tech-support --plan pro --name "TechSupport"
python scripts/admin/tenant.py create-org    --tenant tech-support --org management
python scripts/admin/tenant.py set-bot-token  --tenant tech-support --org management --token "123:ABC"
python scripts/admin/tenant.py deploy         --tenant tech-support
```

### Why the bot token never flows through Helm

`tenant.py deploy` creates the `tg-bot-{org}-secret` Kubernetes Secret **directly
with `kubectl create secret`** before running `helm upgrade`. Helm only receives a
boolean flag (`orgs[i].botEnabled=true`). This keeps the token out of Helm values
and release history, a small but deliberate security property that the article
calls out.

### What a tenant namespace contains

`helm/charts/tenant/` produces, per tenant:

- `Namespace` + `ResourceQuota` (cpu/mem/pods caps)
- `NetworkPolicy` set: deny-all + selective egress/ingress (see [Isolation](#isolation-borders-without-identity))
- `ModelConfig` + `tenant-openai` Secret (per-tenant model config)
- `Agent` CRDs: `echo-agent`, `management-agent` (Declarative; `allowedNamespaces.from: Same`)
- `RemoteMCPServer` + `Deployment` + `Service` + DB `Secret` for `tenant-info-tool`
- optional `order-tracker` (per-tenant CRM) and `tg-bot` (one Deployment per org with a token)

---

## Isolation: borders without identity

There is no Identity layer yet. Tenant separation is enforced by six independent
borders. Each is independently testable; together they form defense in depth.

### 1. Kubernetes namespace per tenant
One namespace per tenant (`tenant-alpha`, `tenant-beta`). Agents never share pods.
Label `multitenant-agent-k8s/tenant-ns: "true"` marks tenant namespaces for
NetworkPolicy selectors. See [namespace.yaml](helm/charts/tenant/templates/namespace.yaml).

### 2. NetworkPolicy: deny-all by default
[networkpolicy.yaml](helm/charts/tenant/templates/networkpolicy.yaml) starts from
`deny-all` (Ingress + Egress) and opens only what is needed:

- egress to `platform` ns (Postgres, GoTrue, Vault)
- egress to `kagent` ns (A2A controller)
- egress to `shared-tools` ns (ping-tool and other shared MCP servers)
- egress to `kube-system` DNS (port 53)
- egress to internet on 443/80 (LLM providers)
- ingress from `kagent` ns (A2A inbound)
- ingress and egress intra-namespace (echo-agent calls tenant-info-tool)

[shared-tools/networkpolicy.yaml](helm/charts/shared-tools/templates/networkpolicy.yaml)
allows ingress **only** from namespaces labeled
`multitenant-agent-k8s/tenant-ns: "true"` and from `kagent`. A pod in `tenant-alpha`
cannot reach a pod in `tenant-beta`.

### 3. PostgreSQL Row-Level Security
[0005_rls_policies.sql](supabase/migrations/0005_rls_policies.sql):

- Role `app_user` is `NOBYPASSRLS`. It cannot circumvent policies.
- Every tenant-scoped table has a policy
  `USING (tenant_id = current_setting('app.tenant_id', true))`.
- `current_setting(..., true)` with `missing_ok=true` is **mandatory**. Without it
  Postgres raises instead of returning zero rows.
- Fail-safe: `ALTER DATABASE postgres SET app.tenant_id = ''`. If `SET LOCAL` is
  forgotten, the query returns zero rows rather than leaking across tenants.

### 4. TenantDB: the mandatory RLS wrapper
[supabase_client.py](packages/saas-common/saas_common/supabase_client.py) wraps every
query in an explicit transaction and sets `app.tenant_id` via `SET LOCAL`:

```python
async with conn.transaction():
    await conn.execute(f"SET LOCAL \"app.tenant_id\" = '{tenant_id}'")
    return await conn.fetch(sql, *params)
```

Two non-obvious gotchas are documented in the code.

`SET LOCAL` is scoped to the current transaction. asyncpg runs each statement in
its own implicit transaction, so `SET LOCAL` vanishes before the next `fetch()`
unless both are wrapped in an explicit `BEGIN…COMMIT`.

The pool is created with `statement_cache_size=0`. asyncpg caches prepared
statements **outside** the `SET LOCAL` transaction, so Postgres evaluates schema
permissions without a tenant context and raises `InsufficientPrivilegeError` on
RLS-protected schemas.

Direct `asyncpg` calls bypass RLS and leak across tenants. **Never use them.**
All DB access goes through `TenantDB`.

### 5. kagent cross-tenant deny
Every `Agent` CRD sets `allowedNamespaces.from: Same`, so an agent can only be
called as a tool by other agents in the same namespace. This is the
controller-level deny. NetworkPolicy is the second layer.

### 6. Per-tenant secrets
Bot tokens live in `platform.orgs.tg_bot_token` (DB) and are materialized into
per-namespace Kubernetes Secrets at deploy time, bypassing Helm values entirely.
Vault is wired but runs in dev mode only in this stage. Per-tenant path RBAC is
planned with the Identity layer.

---

## One request, end to end

A Telegram message to a tenant's bot:

1. **Input.** `tg-bot` (one pod per org) receives the message, resolves the user
   via `platform.users` (RLS-scoped), and sends an A2A `message/send` to
   `kagent-controller`. Multi-turn memory is carried by `contextId` **inside**
   `params.message` (not in `params`). kagent reads it from
   `params.message.context_id`.
2. **Agent Loop.** kagent raises a session for the tenant's Declarative agent
   (`echo-agent` or `management-agent`). `management-agent` calls `echo-agent` as
   a tool (agent-as-tool pattern). Independent tool calls run in parallel in a
   single round.
3. **Execution.** The agent calls MCP tools via `RemoteMCPServer` CRDs.
   `tenant-info-tool` / `order-tracker` run in the tenant namespace, read
   `TENANT_ID` from env, and route every query through `TenantDB` to `SET LOCAL
   app.tenant_id` to RLS-scoped rows.
4. **Borders.** At every hop the six borders above constrain what the request
   can reach. A tenant-alpha agent cannot call a tenant-beta tool, cannot read
   tenant-beta rows, and cannot reach a tenant-beta pod.

---

## Day-2 operations

```bash
make test                 # uv run pytest - unit + e2e (needs port-forwards)
make lint                 # ruff check
make fmt                  # ruff format

make deploy-tenant   TENANT=alpha     # redeploy one tenant
make destroy-tenant  TENANT=alpha     # undeploy one tenant (DB intact)

python scripts/admin/tenant.py list-tenants
python scripts/admin/tenant.py list-orgs --tenant alpha
python scripts/admin/status.py                       # cluster health snapshot

make down          # kind delete cluster (registry survives, images cached)
make clean         # kind delete + remove registry (next up rebuilds all images)
```

Port-forwards (printed at the end of `setup-kind.sh`):

```bash
kubectl port-forward -n platform svc/postgres      5432:5432   # Postgres
kubectl port-forward -n platform svc/gotrue        9999:9999   # GoTrue
kubectl port-forward -n platform svc/vault         8200:8200   # Vault (token: root)
kubectl port-forward -n argocd   svc/argocd-server 8080:80     # Argo CD
kubectl port-forward -n kagent   svc/kagent-ui     3000:8080   # kagent UI
kubectl port-forward -n kagent   svc/kagent-controller 8083:8083  # A2A endpoint
```

---

## Known limits of this stage

- **No Identity layer.** No AgentGateway, no JWT validation, no CEL policy, no
  audit log propagation. A tenant is a network and DB boundary, not an identity
  boundary. `platform.audit_log` exists but is not yet written by the request path.
- **Vault is dev-mode.** Root token `root`, no persistence, no per-tenant path
  policies. Per-tenant secret isolation is currently the K8s Secret-per-namespace
  border, not Vault.
- **HITL is off.** kagent `requireApproval` is in the CRD spec but not enabled in
  this stage.
- **`latest` tag + `IfNotPresent`.** After rebuilding a tool image you must
  `kind load docker-image <img>` or pods keep using the cached old image.

These limits are deliberate. They define the scope of the next article, which
adds the Identity, Policy & Audit layer on top of these borders.

---

## Reading order

1. [Part 1: Toward a Four-Layer Architecture](../docs/articles/Toward%20a%20Four-Layer%20Architecture%20for%20Self-Hosted%20Enterprise%20AI%20Harnesses.md), the architectural frame
2. This guide, the intermediate implementation
3. `helm/charts/tenant/templates/networkpolicy.yaml`, the network borders
4. `supabase/migrations/0005_rls_policies.sql`, the data border
5. `packages/saas-common/saas_common/supabase_client.py`, why RLS needs a wrapper
6. `scripts/cluster/`, the deployment pipeline, step by step
7. `scripts/admin/tenant.py`, tenant onboarding as code