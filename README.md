# Enterprise AI Harness

> **An opinionated reference architecture and implementation for building self-hosted Enterprise AI Harnesses on Kubernetes.**

![Kubernetes](https://img.shields.io/badge/Kubernetes-Native-326CE5?logo=kubernetes&logoColor=white)
![License](https://img.shields.io/badge/License-TBD-lightgrey)
![Status](https://img.shields.io/badge/Status-Active%20Development-blue)
![Architecture](https://img.shields.io/badge/Architecture-Enterprise%20AI%20Harness-purple)

## Scope

Enterprise AI Harness focuses on the architectural layer around AI agents rather than the agent implementation itself.

The project assumes existing agent runtimes and LLM frameworks, and concentrates on the enterprise capabilities required for production deployment—identity, governance, multi-tenancy, secure execution boundaries and observability—instead of introducing yet another agent framework.


---

# Architecture

The harness separates responsibilities into four independent architectural layers:

- **Input**
- **Identity, Policy & Audit**
- **Agent Loop (ReAct)**
- **Execution**

![Enterprise AI Harness Architecture](diagrams/enterprise-ai-harness-overview.png)

This separation allows tools, skills, sub-agents, workflows and human approvals (HITL) to evolve independently while preserving security, governance and tenant isolation.

---

# Why Enterprise AI Harness?

Building an AI agent is only one part of the problem.

Deploying AI agents in enterprise environments requires an architectural layer that is typically outside the scope of agent runtimes.

Enterprise AI Harness provides this layer by integrating identity, policy enforcement, governance, execution boundaries and multi-tenancy into a Kubernetes-native deployment model.

Core capabilities include:

- Identity and authentication
- Authorization and policy enforcement
- Audit and observability
- Multi-tenancy
- Secure execution boundaries
- Secrets management
- Governance
- Kubernetes-native deployment

Rather than replacing existing agent runtimes, Enterprise AI Harness provides the infrastructure and operational model required to run them securely in production.

---

# Design Principles

- Self-hosted by design
- Enterprise-first architecture
- Kubernetes-native
- Security before convenience
- Multi-tenant from day one
- Open-source ecosystem
- Clear architectural boundaries
- Opinionated, but extensible

---

# Article Series

This repository is accompanied by a series of articles describing the architecture and implementation.

- Part 1 — Architecture Overview
- Part 2 — Identity, Policy & Audit
- Part 3 — Agent Loop (ReAct)
- Part 4 — Execution Layer
- Part 5 — Multi-tenancy
- Part 6 — Security Boundaries
- Part 7 — Kubernetes Deployment
- Part 8 — Lessons Learned

---

# Repository Structure

```
architecture/     Architecture concepts and ADRs
articles/         Published articles
diagrams/         Architecture diagrams
docs/             Documentation
examples/         Example configurations
implementation/   Public implementation artifacts
roadmap/          Project roadmap
```

---

# Technology Foundation

The current implementation builds on the CNCF ecosystem and integrates technologies such as:

- Kubernetes
- Gateway API
- kagent
- MCP
- A2A
- Keycloak
- Vault / OpenBao
- External Secrets Operator
- OpenTelemetry
- PostgreSQL
- Redis
- Argo Workflows
- Helm

Technology choices may evolve as the ecosystem matures.

---

# Project Status

Active development.

The repository evolves together with the accompanying article series.

Documentation, implementation details and reusable components will be published incrementally.

---

# License

License information will be added before publishing implementation artifacts.