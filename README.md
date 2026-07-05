# Enterprise AI Harness

> **An opinionated reference architecture and implementation for building self-hosted Enterprise AI Harnesses on Kubernetes.**

Enterprise AI Harness is an engineering research project focused on designing and implementing production-grade AI agent systems for enterprise environments.

The project explores how to build secure, governable and multi-tenant AI systems by separating the responsibilities of user interaction, identity, agent reasoning and execution into well-defined architectural layers.

Rather than introducing yet another agent framework, the project focuses on the architectural boundaries required to operate AI agents safely and reliably in production.

---

## Vision

Modern LLM frameworks make it relatively easy to build an AI agent.

Building an enterprise-grade AI system is a different challenge.

Enterprise environments require:

- identity and authentication
- authorization and policy enforcement
- multi-tenancy
- auditability
- secure execution boundaries
- governance
- operational observability
- Kubernetes-native deployment

Enterprise AI Harness is an opinionated reference architecture that addresses these concerns while remaining fully self-hosted and based on open-source technologies.

---

# Architecture

The harness separates responsibilities into four independent layers:

```
Input
        │
        ▼
Identity / Policy / Audit
        │
        ▼
Agent Loop
        │
        ▼
Execution
```

This separation allows:

- Human-in-the-loop (HITL)
- Skills
- Tools
- MCP
- A2A
- Sub-agents
- Workflows

to evolve independently while preserving security and governance boundaries.

---

# Design Principles

- Self-hosted by design
- Enterprise-first architecture
- Kubernetes-native
- Security before convenience
- Multi-tenant from the beginning
- Open-source ecosystem
- Clear separation of responsibilities
- Opinionated but extensible

---

# Current Status

Active engineering research project.

The reference implementation is approximately **85% complete**.

Public documentation and selected implementation components will be released incrementally together with the accompanying article series.

---

# Article Series

This repository is accompanied by a series of articles describing the architecture and design decisions.

Planned topics include:

- Architecture Overview
- Identity, Policy & Audit
- Agent Loop
- Execution Layer
- Multi-tenancy
- Security Boundaries
- Kubernetes Deployment
- Lessons Learned

---

# Repository Structure

```
docs/              Project documentation
architecture/      Architecture concepts and ADRs
diagrams/          Architecture diagrams
articles/          Published articles
examples/          Example configurations
implementation/    Public implementation artifacts
roadmap/           Project roadmap
```

---

# Technology Stack

The current implementation is based on the Kubernetes ecosystem and integrates with modern open-source AI components, including technologies such as:

- Kubernetes
- Gateway API
- Kagent
- MCP
- A2A
- Keycloak
- PostgreSQL
- Redis
- Argo Workflows
- Helm

The implementation will continue to evolve as the ecosystem matures.

---

# License

License information will be added before the public release of implementation artifacts.
