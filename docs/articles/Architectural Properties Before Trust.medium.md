## Architectural Properties Before Trust

*Enterprise AI isn't just about orchestrating agents. It starts with the architectural properties that make trust possible.*

#### Why trustworthy multi-agent orchestration is an architectural problem, not an AI one.

The first time I watched two agents work on the same task, the single-agent version of this problem hadn't prepared me for what went wrong.

A single ReAct agent is an easy system to reason about. Whatever it gets wrong stays inside one conversation: you see the mess, you fix the prompt, you move on. The moment a second agent enters the picture, that stops being true. Now one agent's output becomes another agent's input, and nobody ever asked the question that actually matters: can the second agent trust what the first one handed it?

That question isn't about intelligence. A smarter model doesn't answer it. It's an architectural problem, and it's the one this article is about.

This is not a whiteboard argument. The [four-layer architecture from the previous article](https://medium.com/towards-artificial-intelligence/toward-a-four-layer-architecture-for-self-hosted-enterprise-ai-harnesses-a960e9fe6a24) partially runs: three of four layers deployed on a local Kubernetes cluster, two tenants isolated from each other, one request traveling end to end through every boundary.

Identity deliberately remains outside the scope of this implementation. This article is about the architectural properties that have to exist before identity, policy, audit, and trust can emerge. The code is public: [github.com/vasiache/enterprise-ai-harness](https://github.com/vasiache/enterprise-ai-harness). What follows explains why those boundaries come first, and what they already prove.

The first article described the architecture in terms of layers. This one looks at the same architecture through a different lens: the architectural properties those layers are expected to guarantee.

Two terms govern the rest of this article.

> **Architectural trust**: the ability to rely on execution guarantees that hold independently of the model's correctness.
>
> **Enterprise AI Harness**: the architectural environment in which multi-agent systems become secure, governable, and engineering-ready.

---

![From Architecture to Architectural Properties](../diagrams/From%20Architecture%20to%20Architectural%20Properties.png)

### The industry is discussing components, not properties

Look at what the field argues about. Models. Prompts. Tools. Frameworks. MCP. Graph libraries. Which agent runtime is faster.

These are component choices. The question almost nobody asks is different: what architectural properties must hold for a graph of agents to be trustworthy at all, independent of which model, which framework, which protocol is plugged in?

Components are replaceable. Properties are not. So why does the conversation about enterprise AI still feel shallow to me, even when the components being discussed are genuinely good? Because it debates what to install, not what has to remain true after you install it.

---

### What we expect from a boundary

Authentication checks who's asking. A boundary is a stronger claim: it holds regardless of whether the code asking is correct. If the code is wrong, if a developer forgets a check, if an agent gets tricked, the boundary is supposed to not care. That's the whole point of calling it a boundary instead of a convention.

If a guarantee disappears the moment someone makes a mistake, it was never a boundary. It was a convention everyone happened to follow until they didn't.

---

### Graph Engineering and the harness

Lately the field compares "harness engineering" with "graph engineering" as if they were alternatives. Strange comparison? Not really, once you notice it's like asking whether a city needs roads infrastructure or traffic rules.

The industry is moving toward graph execution as the standard. The [2026 Agentic Coding Trends Report](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf) predicts multi-agent systems replacing single-agent workflows: an orchestrator coordinates specialized agents working in parallel, each with dedicated context. One node clarifies. Another implements. A third verifies. A fourth decides.

Graph Engineering designs the traffic plan. A harness is the road beneath it: the asphalt, the cameras, the lights, the signs. Agents are the cars. Where to place the light is a graph decision. The light itself, the camera, the lane divider. That is the harness.

When the infrastructure is complete, the traffic flows. When something is missing (no signs at the merge, no lane markings), agents collide or loop. The graph does not fail because the graph is wrong. It fails because the road does not support the route.

What does the harness guarantee? Four things, in two stages. Two hold at the boundary stage: capabilities are bounded per node, and tenant data cannot cross into another tenant's context. Two arrive with identity: identity survives from initiator to last tool call, and every action is attributable to a principal. The six boundaries below are the mechanisms that hold the two boundary-stage guarantees. The two identity-stage guarantees arrive with the layer this article leaves for next.

A harness is more than boundaries. A boundary keeps traffic in lanes. Identity tells you who is driving. Policy tells them where they may turn. Audit records every intersection. Boundaries are the foundation. A harness is the full road. A bounded agent is also the first agent you can bring to review: a named, scoped object instead of a live process you trust on faith.

![Graph Engineering in Harness](../diagrams/Graph%20Engineering%20in%20Harness.png)

---

### Boundaries before identity

Identity is not the first architectural layer. It is the layer that strengthens boundaries that already exist. Consider what happens if you deploy identity on top of nothing: you validate a token at the edge, and then the request enters a space where any agent can call any other agent, where one pod's compromise reads every tenant's rows.

First you draw the boundaries: runtime, network, data, agent, secrets. Then you add identity to make the trust attributable.

Identity without boundaries is a signature on a napkin. The signature is real. The contract is not.

Boundaries first. Identity later.

---

### The implementation is evidence

The rest of this article is supported by a running reference implementation: a local Kubernetes cluster, three of four architectural layers deployed, two tenants isolated from each other, one request traveling end to end.

The implementation is evidence. It is not the claim.

It is also scoped. The public reference implementation demonstrates the boundary stage: identity out of scope. The purpose is to show that architectural boundaries can be enforced and evaluated before identity exists: that trustworthy execution begins with boundaries, not with authentication.

The purpose is not to demonstrate Kubernetes. It is to demonstrate that Enterprise AI Harness is implementable: that the boundary stage of the model already runs.

The complete walkthrough, deployment instructions, and source code are in the public repository: [github.com/vasiache/enterprise-ai-harness/isolation](https://github.com/vasiache/enterprise-ai-harness/tree/main/isolation).

I describe it only enough to validate the architectural ideas. The technologies in it are one way to hold the properties, not the properties themselves. If Kubernetes disappeared tomorrow, the properties would still need to hold. The implementation would change. The architecture would not.

With that framing, here is what the implementation actually holds.

---

### Six architectural boundaries

Read each of these as a property, not as a technology. The technology is the mechanism. The property is the guarantee. Each one is what lets a graph node consume another node's output without re-validating the whole world.

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

The property: a pod that should only talk to the database cannot, by construction, talk to another tenant's pod. Isolation here is enforced, not declared. I made deny-all the default after a pod reached another tenant's service by accident; declared isolation wasn't isolation.

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

RLS alone is not enough. The application must set the context inside an explicit transaction, or `asyncpg` silently breaks it. I assumed RLS would be enough. It wasn't: asyncpg dropped the context outside an explicit transaction, and the leak took a day to find. The wrapper forces this:

```python
async with conn.transaction():
    await conn.execute(
        "SELECT set_config('app.tenant_id', $1, true)", tenant_id
    )
    return await conn.fetch(sql, *params)
```

`set_config(..., true)` is used instead of `SET LOCAL` because `SET` does not take bind parameters, so interpolating `tenant_id` into SQL text is an injection even when the value comes from config. The wrapper also disables prepared-statement caching (`statement_cache_size=0`), so RLS does not remain a checkbox.

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

The property: a data boundary that depends on a migration has that migration applied before any pool opens; a data boundary that depends on a wrapper has that wrapper on every code path. The operational boundary is the discipline that keeps the other five from being a checkbox.

Six boundaries, six guarantees. None of them authenticates anyone. All of them are required for what comes next.

| Boundary | What enforces it | What it guarantees |
|---|---|---|
| Runtime | Namespace per tenant | One compromise cannot reach another tenant's processes |
| Network | NetworkPolicy deny-all by default | A pod cannot talk to another tenant's pod by accident |
| Data | PostgreSQL RLS + TenantDB wrapper | Storage returns only this tenant's rows, even if the app asks for everything |
| Agent | `allowedNamespaces: Same` | Agents cannot be composed into another tenant's loop |
| Secret | Per-namespace secrets | Credentials never pass through shared Helm values or release history |
| Operational | Ordered deployment (migration before pool, wrapper on every path) | Boundaries hold on every code path |

> **A boundary you can test.** Deploy two tenants against the same database. Query without setting `app.tenant_id`. The result must be zero rows. If you get data, your wrapper is broken and your RLS is a checkbox.

---

### One request, end to end

One Telegram message shows what the boundaries actually do. The route crosses every boundary, and each one holds:

![One Request Through the Stack](../diagrams/One%20Request%20Through%20the%20Stack.png)

The tenant identity for the tool isn't a parameter the caller passes and could forge; it's a property of where the tool was deployed. The query returns only this tenant's rows, and would return zero rows if the context were ever forgotten.

Five boundaries get enforced along that one route, and none of them get merely checked or merely logged. The whole point is that nothing about it was exciting to watch. At no point did the request's safety depend on an agent being smart, a prompt being careful, or a developer remembering a check that day. That quietness is the actual product.

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

A graph node without its tenant, its initiator, and its policy is a leak with a nice diagram drawn around it.

The evolution is not accidental. You do not arrive at graph execution by making agents smarter. You arrive there by making the environment trustworthy enough that a graph can be allowed to run.

There's a payoff in all this boundary work that the boundaries framing was never marketed for. Once an agent is a namespaced, bounded YAML object, it stops being a live process you trust on faith and becomes something you can diff, review, and ship. Two versions of an Agent CRD are just a diff. Promoting one to production is a merge. Rolling it back is a revert.

That's boundaries doing something they were never sold on: turning an agent into the kind of thing you bring to review the same way you'd bring a pull request. "I tested it, trust me" becomes a diff a second reviewer can actually read before it ships. A reviewer can challenge a capability, an approval gate can block the promote, and the team ships the agent the same way it ships code: through a pipeline, not through a person's word.

What a full review pipeline for agent graphs looks like is a later article. For now, even this boundaries-only stage already buys you that.

---

### Where this leaves me

An enterprise AI system doesn't become trustworthy by choosing better components. It becomes trustworthy by acquiring architectural properties. Two orders matter, and both resist skipping.

**Evolution** (how a system grows toward graph execution):

```
single agent → multiple agents → cooperation → approvals → verification → graph execution
```

**Dependency** (what each stage needs underneath it):

```
architectural boundaries → identity → trust → graph execution
```

They meet at graph execution. One describes how you get there, the other describes what has to be holding when you arrive. Architectural boundaries are where the dependency chain starts, which is where the rest of it actually starts.

> The implementation behind this argument is temporary; I expect most of it to be replaced within a year. The properties it's demonstrating, I don't expect to change.

Where the earlier article framed the harness as four layers, I'm not fully settled on that framing anymore. Some days I still think in layers; other days the properties feel more real: boundary, identity, audit, whatever comes after. Both may be two ways of looking at the same thing, and I may have a cleaner answer by the next article. I'd rather say that plainly than pretend the model is more finished than it is.

What I'm sure of, in whatever order I end up drawing it:

**Graph Engineering needs trust.**

**Trust needs identity.**

**Identity needs boundaries.**

**All of it together is what I've been calling an Enterprise AI Harness.**

If you've built something like this yourself, or you'd draw these boundaries differently, I'd genuinely like to hear it: in the comments, or on the repo.