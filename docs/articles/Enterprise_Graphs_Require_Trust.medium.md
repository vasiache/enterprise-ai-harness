## Enterprise Graphs Require Trust

#### Why trustworthy multi-agent orchestration is an architectural problem, not an AI one.

A single ReAct agent is an easy system. The failure stays inside one conversation.

The difficulty appears at the second agent.

The hard problems are not about intelligence. They are about whether the result of one node can be trusted by the next. That is an architectural problem.

This is not a whiteboard argument. The [four-layer architecture from the previous article](https://medium.com/towards-artificial-intelligence/toward-a-four-layer-architecture-for-self-hosted-enterprise-ai-harnesses-a960e9fe6a24) partially runs: three of four layers deployed on a local Kubernetes cluster, two tenants isolated from each other, one request traveling end to end through every boundary.

Identity is out of scope; this is the boundaries stage, the part that has to hold before identity can mean anything. The code is public: [github.com/vasiache/enterprise-ai-harness](https://github.com/vasiache/enterprise-ai-harness). What follows explains why those boundaries come first, and what they already prove.

Two terms govern the rest of this article.

> **Architectural trust** — the ability to rely on execution guarantees that hold independently of the model's correctness.
>
> **Enterprise AI Harness** — the architecture in which a multi-agent system meets an enterprise's security requirements.

---

![From Architecture to Architectural Properties](../diagrams/From%20Architecture%20to%20Architectural%20Properties.png)

### The industry is discussing components, not properties

Look at what the field argues about. Models. Prompts. Tools. Frameworks. MCP. Graph libraries. Which agent runtime is faster.

These are component choices. The question almost nobody asks is different: what architectural properties must hold for a graph of agents to be trustworthy at all, independent of which model, which framework, which protocol is plugged in?

Components are replaceable. Properties are not. This is why the conversation about enterprise AI keeps feeling shallow. It debates what to install. It rarely debates what must remain true after you install it.

---

### Graph Engineering and the harness

Lately the field compares "harness engineering" with "graph engineering" as if they were alternatives. That is a strange comparison. It is like asking whether a city needs roads infrastructure or traffic rules.

The industry is moving toward graph execution as the standard. The [2026 Agentic Coding Trends Report](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf) predicts multi-agent systems replacing single-agent workflows: an orchestrator coordinates specialized agents working in parallel, each with dedicated context. One node clarifies. Another implements. A third verifies. A fourth decides.

Graph Engineering designs the traffic plan. A harness is the road beneath it: the asphalt, the cameras, the lights, the signs. Agents are the cars. Where to place the light is a graph decision. The light itself, the camera, the lane divider — that is the harness.

When the infrastructure is complete, the traffic flows. When something is missing (no signs at the merge, no lane markings), agents collide or loop. The graph does not fail because the graph is wrong. It fails because the road does not support the route.

What does the harness guarantee? Four things, in two stages. Two hold at the boundary stage: capabilities are bounded per node, and tenant data cannot cross into another tenant's context. Two arrive with identity: identity survives from initiator to last tool call, and every action is attributable to a principal.

A harness is more than boundaries. A boundary keeps traffic in lanes. Identity tells you who is driving. Policy tells them where they may turn. Audit records every intersection. Boundaries are the foundation. A harness is the full road.

![Graph Engineering in Harness](../diagrams/Graph%20Engineering%20in%20Harness.png)

---

### What we expect from a boundary

A boundary is not authentication. Authentication tells you who knocked on the door.

A boundary is the guarantee that, whoever knocks, the door is the only way in and the room is the only place they can reach. It holds independently of the application's correctness: if the code is wrong, if a developer forgets a check, if an agent is tricked, the boundary still holds.

If a guarantee disappears the moment a developer makes a mistake, it was never a boundary. It was a convention.

---

### Boundaries before identity

Identity is not the first architectural layer. It is the layer that strengthens boundaries that already exist. Consider what happens if you deploy identity on top of nothing: you validate a token at the front door, and then the request enters a space where any agent can call any other agent, where one pod's compromise reads every tenant's rows.

First you draw the boundaries: runtime, network, data, agent, secrets. Then you add identity to make the trust attributable.

Identity without boundaries is a signature on a napkin. The signature is real. The contract is not.

Boundaries first. Identity later.

---

### The implementation is evidence

The rest of this article is supported by a running reference implementation: a local Kubernetes cluster, three of four architectural layers deployed, two tenants isolated from each other, one request traveling end to end.

The implementation is evidence. It is not the claim.

It is also scoped. The public reference implementation demonstrates the boundaries stage: three layers deployed, identity out of scope. The purpose is to show that architectural boundaries can be enforced and evaluated before identity exists: that trustworthy execution begins with boundaries, not with authentication.

What the reference implementation holds today:

- ✔ Runtime isolation — namespace per tenant.
- ✔ Network isolation — NetworkPolicy deny-all by default.
- ✔ Data isolation — PostgreSQL row-level security, enforced through a wrapper.

The purpose is not to demonstrate Kubernetes. It is to demonstrate that Enterprise AI Harness is implementable: that the boundaries stage of the model already runs.

The complete walkthrough, deployment instructions, and source code are in the public repository: [github.com/vasiache/enterprise-ai-harness/isolation](https://github.com/vasiache/enterprise-ai-harness/tree/main/isolation).

I describe it only enough to validate the architectural ideas. The technologies in it are one way to hold the properties, not the properties themselves. If Kubernetes disappeared tomorrow, the properties would still need to hold. The implementation would change. The architecture would not.

With that framing, here is what the implementation actually holds.

---

### Six architectural boundaries

Read each of these as a property, not as a technology. The technology is the mechanism. The property is the guarantee.

**Runtime boundary.** Each tenant lives in its own Kubernetes namespace:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-alpha
  labels:
    tenant-id: alpha
```

Agents of one tenant never share a process with agents of another. The property: a compromise in one tenant's runtime cannot reach another tenant's runtime by accident.

**Network boundary.** The default is closed. `deny-all` for ingress and egress, opened only to destinations the work requires:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all
  namespace: tenant-alpha
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-platform-egress
  namespace: tenant-alpha
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: platform
```

The property: a pod that should only talk to the database cannot, by construction, talk to another tenant's pod. Isolation here is enforced, not declared.

**Data boundary.** Tenant-scoped rows are filtered at the storage layer by PostgreSQL Row-Level Security:

```sql
ALTER TABLE orders.leads ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_rls ON orders.leads
    USING (tenant_id = current_setting('app.tenant_id', true));
```

The property: even if the application asks for everything, storage returns only rows belonging to the current tenant. If the context is missing, storage returns nothing, not everything. A fail-safe ensures a forgotten context returns zero rows:

```sql
ALTER DATABASE postgres SET app.tenant_id = '';
```

RLS alone is not enough. The application must set the context inside an explicit transaction, or `asyncpg` silently breaks it. The wrapper forces this:

```python
async with conn.transaction():
    await conn.execute(
        "SELECT set_config('app.tenant_id', $1, true)", tenant_id
    )
    return await conn.fetch(sql, *params)
```

`set_config(..., true)` is used instead of `SET LOCAL` because `SET` does not take bind parameters, so interpolating `tenant_id` into SQL text is an injection even when the value comes from config. The wrapper also disables prepared-statement caching (`statement_cache_size=0`), so RLS does not remain a checkbox on paper.

> **Trade-off: a database per tenant vs. shared + RLS.** The strongest isolation is a separate database per tenant: get RLS wrong and there is no leak, because there is no RLS. The cost is N databases, N backups, N connection pools, so operational complexity grows linearly. This reference takes the compromise: one platform database, RLS, the wrapper, and the fail-safe.

![RLS Enforcement Flow](../diagrams/RLS%20Enforcement%20Flow.png)

**Agent boundary.** An agent can be invoked as a tool only from within its own namespace:

```yaml
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: echo-agent
  namespace: tenant-alpha
spec:
  allowedNamespaces:
    from: Same
```

The property: a tenant's agents cannot be composed into another tenant's loop. The agent system enforces the deny, with the network boundary as a second layer.

**Secret boundary.** Credentials live in the tenant's own namespace and never pass through the deployment's value chain. The property: a tenant's secret is not present in Helm values, release history, or any shared configuration where another tenant's process could read it. Per-tenant Vault paths arrive with the identity layer.

**Operational boundary.** The five above are only real if deployed in the right order. One command spins up the whole stack:

```makefile
up: ## Spin up Kind cluster + platform stack
    scripts/setup-kind.sh

deploy-tenant: ## Deploy a tenant
    uv run python scripts/admin/tenant.py deploy --tenant $(TENANT)
```

The property: a data boundary that depends on a migration has that migration applied before any pool opens; a data boundary that depends on a wrapper has that wrapper on every code path. The operational boundary is the discipline that keeps the other five from being a checkbox on paper.

Six boundaries, six guarantees. None of them authenticates anyone. All of them are required for what comes next.

| Boundary | What enforces it | What it guarantees |
|---|---|---|
| Runtime | Namespace per tenant | One compromise cannot reach another tenant's processes |
| Network | NetworkPolicy deny-all by default | A pod cannot talk to another tenant's pod by accident |
| Data | PostgreSQL RLS + TenantDB wrapper | Storage returns only this tenant's rows, even if the app asks for everything |
| Agent | `allowedNamespaces: Same` | Agents cannot be composed into another tenant's loop |
| Secret | Per-namespace secrets | Credentials never pass through shared Helm values or release history |
| Operational | Ordered deployment (migration before pool, wrapper on every path) | Boundaries hold on every code path, not only on paper |

> **A boundary you can test.** Deploy two tenants against the same database. Query without setting `app.tenant_id`. The result must be zero rows. If you get data, your wrapper is broken and your RLS is a checkbox.

---

### One request, end to end

One Telegram message shows what the boundaries actually do. The route crosses every boundary, and each one holds:

![One Request Through the Stack](../diagrams/One%20Request%20Through%20the%20Stack.png)

The tenant identity for the tool is not a parameter the caller passes and could forge: it is a property of where the tool was deployed. The query returns only this tenant's rows, and would return zero rows if the context were ever forgotten.

One request. Five boundaries enforced. Not checked. Not logged. Enforced. At no point did the request's safety depend on an agent being smart, a prompt being careful, or a developer remembering a check.

Trustworthy execution is quiet. Nothing dramatic happens, because nothing dramatic is allowed to.

---

### Where boundaries stop

Honesty matters more than a clean story.

These boundaries separate tenants, not roles within a tenant. A user and an admin inside the same tenant are the same principal to the system.

A pod compromised inside a tenant's scope opens everything inside that scope. Privileged containers and `hostPath` mounts escape Kubernetes-level isolation entirely.

A data boundary can fail silently. A developer deploys a hotfix on Friday evening, uses `asyncpg` directly for speed, forgets the wrapper. Monday morning the dashboard shows leads from every tenant mixed together. No error thrown, no alarm triggered. The wrapper exists because this scenario is not hypothetical.

Shared tools are a shared blast radius. A stateful, privileged component shared across tenants is a single point of compromise for all of them.

There is no audit trail yet. The system can show what happened. It cannot show who initiated it.

---

### Why identity becomes necessary

Identity is introduced because the moment a multi-agent process includes an approval, the system has to answer a question boundaries alone cannot answer: who performed this action, and were they permitted to?

Identity converts a boundary-protected space into an attributable one. It attaches a principal to every action, a policy to every capability, and a record to every decision. It does not replace the boundaries. It makes them meaningful at the level of people and rules.

---

### Why this unlocks graph engineering

The purpose of an Enterprise AI Harness is not running agents. It is enabling trustworthy enterprise orchestration: the ability to design, run, and evolve complex multi-agent processes without destroying trust between nodes.

A graph is the shape of such a process. One node clarifies a task. Another implements. A third verifies. A fourth decides whether to retry or to ship.

![From Single Agent to Multi-Agent System](../diagrams/From%20Single%20Agent%20to%20Multi-Agent%20System.png)

Each arrow in that graph is a transfer of trust. The verifier trusts that the implementer's output is what was committed. The judge trusts that the verifier actually ran. Every one of those trusts is only valid if the nodes operate inside boundaries that make forgery and cross-contamination impossible.

A graph node that does not know its tenant, its initiator, and its policy is not a node. It is a leak.

The evolution is not accidental. You do not arrive at graph execution by making agents smarter. You arrive there by making the environment trustworthy enough that a graph can be allowed to run.

---

### The conclusion the architecture was building toward

An enterprise AI system does not become trustworthy by choosing better components. It becomes trustworthy by acquiring architectural properties, in an order that cannot be skipped.

```
single agent → multiple agents → cooperation → approvals → verification → graph execution → trust → identity → architectural boundaries
```

Read it backward, and each step asks for the one beneath it. The chain ends at architectural boundaries. That is where the rest of the chain starts.

The implementation that supports this argument is temporary. The properties will not.

Where the earlier article in this series framed the harness as a four-layer architecture, the layers remain, but the focus shifts to the architectural properties that hold beneath them.

Four lines, in the order the architecture forces them:

**Graph Engineering Requires Trust.**

**Trust Requires Identity.**

**Identity Requires Boundaries.**

**All of This: Enterprise AI Harness.**