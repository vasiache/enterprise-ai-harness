This document provides a reference architecture to help you design and deploy a
multi-tenant agentic AI system on Google Cloud. As your
organization scales generative AI deployments, different business units require
specialized AI agents that access unique tools, follow specific operational
rules, and process sensitive data. Business units might develop fragmented
application silos within an organization, which can cause high operational
overhead, severe governance gaps, and a risk of data exposure. This architecture
shows you how to build a centralized system that lets you empower decentralized
teams with autonomous AI capabilities while you maintain unified security and
compliance.

The intended audience for this document includes architects, developers, and
administrators who build and manage enterprise-grade, multi-agent systems in the
cloud. The document assumes that you have a foundational understanding of AI,
ML, and [LLM](https://docs.cloud.google.com/docs/generative-ai/glossary#large-language-model) concepts, and
of [agentic AI](https://cloud.google.com/discover/what-is-agentic-ai).

The [deployment](https://docs.cloud.google.com/architecture/multi-tenant-agentic-ai-system#deployment) section of this document provides an
implementation strategy to help you build and deploy a multi-tenant agentic AI
system.

## Architecture

The following diagram shows an architecture for a multi-tenant agentic AI system
that follows a
[hub-and-spoke model](https://docs.cloud.google.com/architecture/deploy-hub-spoke-vpc-network-topology).
A hub-and-spoke model is a network design where a central environment, which is
known as a *hub* , connects to multiple isolated environments, which are known as
*spokes*.

![An architecture that shows a multi-tenant agentic AI system.](https://docs.cloud.google.com/static/architecture/images/multi-tenant-agentic-ai-system.svg)
![](https://docs.cloud.google.com/static/architecture/images/multi-tenant-agentic-ai-system.svg)

The architecture consists of the following components:

| Component | Description |
|---|---|
| **[VPC Service Controls](https://docs.cloud.google.com/vpc-service-controls/docs/overview)** | The architecture uses VPC Service Controls to configure a [service perimeter](https://docs.cloud.google.com/vpc-service-controls/docs/service-perimeters) at the organization level. This service perimeter provides a strict security boundary and it prevents data exfiltration. |
| **Routing hub** | The routing hub acts as the central ingress point for the architecture and it includes the following components: - **[External Application Load Balancer](https://docs.cloud.google.com/load-balancing/docs/https)**: Acts as the central ingress point for external or internal users. The load balancer ensures that only authenticated and safe traffic reaches the frontend portal. - **[Google Cloud Armor](https://docs.cloud.google.com/armor/docs/integrating-cloud-armor#https-iap)** and **[Model Armor](https://docs.cloud.google.com/model-armor/overview)** : The load balancer integrates Cloud Armor and Model Armor to inspect and scrub malicious prompts at the network edge. The routing hub uses [Service Extensions](https://docs.cloud.google.com/service-extensions/docs/lb-extensions-overview#supported-lbs) on the external Application Load Balancer to integrate [Model Armor](https://docs.cloud.google.com/model-armor/overview) directly into the request flow. - **[Identity-Aware Proxy (IAP)](https://docs.cloud.google.com/iap/docs)** : Enforces a [zero-trust model](https://docs.cloud.google.com/architecture/framework/security/implement-zero-trust) to verify user identity and context before any request reaches the application. - **Frontend portal** : A serverless [Cloud Run application](https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run) that acts as a routing engine to route requests to the appropriate isolated tenant project. |
| **Central governance and security hub** | The central governance and security hub is a dedicated Google Cloud project that provides centralized Identity and Access Management (IAM), logging, monitoring, and security for the entire platform. This hub includes the following components: - **[Security Command Center](https://docs.cloud.google.com/security-command-center/docs/security-command-center-overview)**: A service that monitors the entire multi-tenant agentic AI system for security risks. - **[IAM](https://docs.cloud.google.com/iam/docs/overview)**: An access control framework that manages identities and permissions across the shared hubs and the tenant projects. This component provides centralized governance for all human and machine identities. - **[Cloud Logging](https://docs.cloud.google.com/logging/docs/overview)**: A system that aggregates logs from the shared hubs and from the isolated tenant projects into the central governance and security hub. |
| **Tenant projects** | Each tenant project is a dedicated Google Cloud project for each business unit. Individual tenant projects are isolated environments that include the following components: - **[Principal Access Boundary Policy (PAB Policy)](https://docs.cloud.google.com/iam/docs/principal-access-boundary-policies)**: PAB Policy provides internal hard isolation between different business units and they ensure that principals can only access resources within their approved boundaries. - **[Agent Runtime on Gemini Enterprise Agent Platform](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime)** : A runtime that hosts the specific business unit agent and executes custom orchestration code that you build by using [Agent Development Kit (ADK)](https://adk.dev/). - **[Model Armor](https://docs.cloud.google.com/model-armor/overview)**: A managed security service that inspects and filters malicious prompts and responses. It protects the tenant's agent and compute resources from threats like prompt injection attacks. - **[Model Context Protocol (MCP)](https://modelcontextprotocol.io/docs/getting-started/intro) servers:** MCP server facilitates access between the tenant agent and tenant datastore. - **Tenant datastore** : A dedicated data repository, such as [BigQuery](https://docs.cloud.google.com/bigquery/docs/introduction) or [AlloyDB for PostgreSQL](https://docs.cloud.google.com/alloydb/docs/overview), that stores specific business unit data. The agent performs [retrieval-augmented generation (RAG)](https://docs.cloud.google.com/docs/generative-ai/glossary#retrieval-augmented-generation) to generate more accurate responses based on the context in the datastore. To maintain strict data sovereignty, only the tenant agents can access this data. - **Gemini models** : For inference serving, the agents in this example architecture use the latest [Gemini model](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/google-models) on [Gemini Enterprise Agent Platform](https://docs.cloud.google.com/gemini-enterprise-agent-platform/overview). |

### Agentic flow

The example multi-tenant system in the preceding architecture has the following
flow:

1. A user's request is routed through an external Application Load Balancer. Within the routing hub, these checks are completed to help ensure that only authenticated and safe traffic reaches the frontend portal:
   1. Cloud Armor applies security policies to absorb any initial Layer 4 network protocol-based [distributed denial-of-service (DDoS) attacks](https://en.wikipedia.org/wiki/Denial-of-service_attack). Cloud Armor inspects the request and filters malicious traffic, such as SQL injection (SQLi), cross-site scripting (XSS), and known bot signatures.
   2. Model Armor intercepts the payload to detect and reject prompt injection attacks or malicious intent.
   3. If any of these layers detect a threat or unauthorized access, then the load balancer drops the request at the network edge.
   4. If the security layers detect no threat and they validate the user's access, then the load balancer routes the traffic to the backend service.
2. If the request passes all checks, the load balancer routes the request to the frontend platform, which performs the following actions:
   1. Extracts the user's identity, such as the user's business unit or tenant ID.
   2. Uses IAP to verify the user's corporate identity and device health.
   3. Uses a dynamically maintained registry to identify the correct target tenant.
3. The frontend portal routes the request to the tenant. To ensure that the agent can't access other tenant projects or unauthorized Google Cloud services, Agent Runtime uses a PAB Policy to limit the resources that the agent can access.
4. Model Armor uses [Sensitive Data Protection](https://docs.cloud.google.com/sensitive-data-protection/docs/sensitive-data-protection-overview) to inspect and dynamically mask any personally identifiable information (PII) or restricted content. Model Armor performs an additional check for malicious prompt injections from the request to ensure that the agent only processes safe data.
5. Gemini performs the following tasks to generate a response:

   1. Performs an initial reasoning pass to understand the user's intent.
   2. If Gemini determines that it lacks specific facts, then it generates a plan to call the tenant's specific data tools:
      1. To verify whether a user has permission to access the data resources, the agent verifies the user's identity and IAM role bindings.
      2. To retrieve context, the agent executes a tool call through the MCP server to the tenant datastore.
      3. The agent creates a [grounded](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/grounding/overview) response by combining its internal logic with the newly retrieved, tenant-specific facts.

   If Gemini doesn't need additional facts, then it generates a
   response and sends the response to Model Armor.
6. Model Armor inspects and dynamically masks any PII or
   restricted content and sends the sanitized response to the tenant agent. This
   final inspection helps to ensure that no sensitive data leaks in the output.

7. The response is routed back to the user, from the tenant agent through the
   frontend platform and then through the load balancer.

## Products used

This reference architecture uses the following Google Cloud and
open-source products and tools, chosen for their serverless nature, scalability,
and security features:

- [VPC Service Controls](https://cloud.google.com/security/vpc-service-controls): A managed networking functionality that minimizes data exfiltration risks for your Google Cloud resources.
- [Cloud Load Balancing](https://cloud.google.com/load-balancing): A portfolio of high performance, scalable, global and regional load balancers.
- [Google Cloud Armor](https://cloud.google.com/security/products/armor): A network security service that offers web application firewall (WAF) rules and helps to protect against DDoS and application attacks.
- [Model Armor](https://cloud.google.com/security/products/model-armor): A service that provides protection for your generative and agentic AI resources against prompt injection, sensitive data leaks, and harmful content.
- [Identity-Aware Proxy (IAP)](https://cloud.google.com/security/products/iap): A service that enables a zero-trust access model for your applications and virtual machines.
- [Identity and Access Management (IAM)](https://cloud.google.com/security/products/iam): A system that lets you create and manage permissions for Google Cloud resources.
- [Cloud Run](https://cloud.google.com/run): A serverless compute platform that lets you run containers directly on top of Google's scalable infrastructure.
- [Gemini Enterprise Agent Platform](https://docs.cloud.google.com/gemini-enterprise-agent-platform/overview): A comprehensive platform that lets you build, scale, govern, and optimize enterprise‑grade AI agents.
- [Gemini](https://ai.google.dev/gemini-api/docs/models): A family of multimodal AI models developed by Google.

-
  [Model Context Protocol (MCP)](https://modelcontextprotocol.io/docs/getting-started/intro): An open-source standard for connecting AI applications to external systems.
- [Cloud Logging](https://cloud.google.com/logging): A real-time log management system with storage, search, analysis, and alerting.

## Use case

Multi-tenant agentic AI systems are suitable for enterprise organizations that
want to scale generative AI deployments beyond a single application. To identify
use cases that this architecture is suitable for, analyze your business
processes and identify different teams that require their own specialized AI
agents that access unique tools and sensitive data. This approach helps you
empower decentralized teams with autonomous AI capabilities while you maintain
unified security and corporate compliance.

The following is an example use case for a multi-tenant agentic AI system.

### Enterprise-wide customer service

You can adapt this reference architecture to provide AI-powered customer service
across distinct business divisions. For example, to support an electronics
division and a home goods division, you deploy an electronics agent and a home
goods agent as two separate agents in separate tenant projects. These
specialized AI agents act as intelligent assistants that handle
division-specific support inquiries by accessing unique technical
specifications, warranties, or return policies. This automation lets human
support teams focus on more complex customer escalations.

For this use case, the architecture provides the following benefits:

- **Strict data isolation**: The multi-tenant design ensures that the support knowledge for each division is strictly isolated. PAB Policy provides guardrails that help ensure that an agent identity in one tenant can't access data in another tenant.
- **Specialized agent knowledge**: Because each agent resides in an isolated tenant project, the agent only retrieves context from its division-specific datastore. This targeted retrieval ensures high accuracy and prevents the agent from confusing the policies of different business units.
- **Reduced cross-domain risk**: The architecture helps to eliminate the risk of data exposure between business units. Even if an agent identity is compromised, the agent can't access unauthorized Google Cloud resources.

This architecture is ideal for large retail organizations and enterprises that
manage multiple distinct brands or business units and that require strict data
sovereignty.

## Design alternatives

This section presents alternative design approaches that you can consider for
your multi-tenant agentic AI deployment in Google Cloud.

### Private access deployment

In the architecture that this document describes, users access the multi-tenant
agentic AI system over the public internet through a centrally exposed
external Application Load Balancer. If your organization requires a system that remains inaccessible
from the public internet, then you can adapt the architecture to use one of the
following private access strategies.

#### Block traffic with edge security policies

To allow traffic only from your organization's verified corporate IP addresses,
you can configure Cloud Armor security policies to deny any other
traffic. This high-priority security rule blocks all of the unauthorized
requests at the network edge. For an additional layer of security, you can use
IAP to require a valid corporate identity session and you can
configure IAM permissions for all users.

This approach lets you take advantage of
[Cloud Armor edge security policies](https://docs.cloud.google.com/armor/docs/security-policy-overview#edge-policies)
to offload DDoS
mitigation and WAF filtering, such as SQLi and XSS, and it provides a zero-trust
experience. However, the frontend IP address of the external Application Load Balancer remains
public and it might not meet the compliance requirements of some organizations.

#### Route traffic through an internal Application Load Balancer

The architecture in this document uses an external Application Load Balancer, which provides robust
Cloud Armor policies, more advanced security features, and lower
operational complexity compared to internal load balancers. However, the use of
an external load balancer means that traffic traverses the public internet.

To keep traffic entirely within the private Google network, you can use an
[internal Application Load Balancer](https://docs.cloud.google.com/load-balancing/docs/application-load-balancer#int-applb). The
use of an internal Application Load Balancer supports IAP for identity verification.
A global external Application Load Balancer evaluates IAP policies at the edge layer.
By contrast, an internal Application Load Balancer evaluates policies at the internal network layer.
Because traffic never traverses the public internet, the use of an
internal Application Load Balancer helps you to meet strict data sovereignty and zero-public IP
address requirements.

To maintain low latency and comply with regional data residency requirements,
deploy a *regional internal Application Load Balancer* in each primary region. With a
regional internal Application Load Balancer, you route traffic from on-premises environments over
[Cloud Interconnect](https://docs.cloud.google.com/network-connectivity/docs/interconnect/concepts/overview)
or over [Cloud VPN](https://docs.cloud.google.com/network-connectivity/docs/vpn/concepts/overview)
directly to the internal IP address of the load balancer. A
regional internal Application Load Balancer supports regional Cloud Armor for
internal WAF protection. However, compared to an external Application Load Balancer,
regional internal Application Load Balancers support a limited set of Cloud Armor security
policies, lack advanced security features, and increase operational complexity.

To further minimize latency and to help ensure high availability to meet your
disaster recovery requirements, you can deploy a *cross-region internal Application Load Balancer* .
With a cross-region internal Application Load Balancer, you use [Cloud DNS](https://docs.cloud.google.com/dns/docs/overview) with
[geolocation routing
policies](https://docs.cloud.google.com/dns/docs/routing-policies-overview#geolocation-policy) to resolve the
internal URL of the application to the cross-region internal Application Load Balancer in the
Google Cloud region that's closest to the user. However, a cross-regional
configuration doesn't support any Cloud Armor integration.

### Compute infrastructure

To prioritize a serverless-first approach that provides easier management and
lower operational overhead, the architecture in this document uses
Cloud Run for its compute infrastructure. You can also run
[containerized](https://cloud.google.com/discover/what-are-containerized-applications)
applications on
[GKE clusters](https://docs.cloud.google.com/kubernetes-engine/docs/get-started/cluster-lifecycle).
Google Kubernetes Engine (GKE) is a container orchestration engine that automates
the deployment, scaling, and management of containerized applications.
GKE fully supports both internal and external
Application Load Balancers. For information about how to choose a compute
service for your workloads on Google Cloud, see [Hosting Applications on
Google Cloud](https://cloud.google.com/hosting-options).

### Model Context Protocol (MCP) servers

To enable the components of your agentic system to interact, you need to
establish clear communication protocols.
[MCP](https://modelcontextprotocol.io/docs/getting-started/intro) is an open protocol that
provides a standardized interface for agents to access and use necessary tools,
data, and other services.

To connect your tenant agents to your datastore, consider your application
requirements to choose from the following MCP server deployment options. When
you choose between local and shared MCP deployments, consider the trade-offs
between data isolation and operational efficiency.

- **Local MCP server**: A local MCP server, or a tenant-specific MCP server, is
  an MCP server that you deploy within each tenant project and that provides
  agents access to datastores and tools that are specific to that business
  unit.

  The following are key features and considerations for local MCP servers:
  - **Network**: A project-level VPC Service Controls perimeter and PAB Policy provide inherent security and isolation, which helps to ensure no cross-tenant access.
  - **Management**: Individual developer and operations teams manage tenant projects independently. This isolation provides autonomy for each business unit.
  - **Security**: The fixed IAM boundaries of the tenant project help minimize lateral risk surfaces and they don't require complex identity mappings.

  Local MCP servers offer maximum isolation and they can handle highly sensitive
  or regulated data access. However, if you deploy multiple local MCP servers,
  then you increase your operational load. We recommend local MCP servers for
  applications that require restrictive access to datastores that might contain
  sensitive information.
- **Shared MCP server**: A shared MCP server, or a global MCP server, is an MCP
  server that you deploy in a shared services project. Shared MCP servers
  provide access to tools and systems that are common across multiple tenants.

  The following are key features and considerations for shared MCP servers:
  - **Network** : To ensure that traffic doesn't traverse the public internet, shared MCP servers require private connectivity, such as [Private Service Connect](https://docs.cloud.google.com/vpc/docs/private-service-connect) or [VPC Network Peering](https://docs.cloud.google.com/vpc/docs/vpc-peering).
  - **Management**: A centralized operations team manages the implementation for the entire system. This consolidated management optimizes operational efficiency and removes the requirement to duplicate local implementations across multiple tenants.
  - **Security**: You securely propagate the end-user identity from the agent in the tenant project to the shared MCP server. To help ensure that users can only access or modify data that they're permitted to, the shared MCP server uses the propagated user identity to enforce fine-grained access control on the backend system.

  Shared MCP servers centralize management for common tools, which reduces
  duplication and optimizes operational efficiency. Although shared MCP servers
  reduce management overhead, they require robust identity propagation and
  authorization logic to maintain secure access. We recommend shared MCP servers
  for interactions with common corporate systems and tools, such as expense
  reporting tools, human resources (HR) systems, corporate-wide knowledge bases,
  or attendance managers.

In this architecture, you use MCP servers to standardize the connection between
your tenant agents and your datastores. Depending on your workload
requirements, you might use other types of agent tools to connect your agents
with specific external APIs and systems. For more information about agent tool
interactions, see
[Agent tools](https://docs.cloud.google.com/architecture/choose-agentic-ai-architecture-components#agent-tools).

## Design considerations

The following sections describe design factors, best practices, and
recommendations to consider when you use this reference architecture to develop
a topology that meets your specific requirements for security, reliability,
cost, and performance. The guidance in this section isn't exhaustive. Depending
on your workload's requirements and the products and features that you use,
there might be additional design factors and trade-offs that you should
consider.

### Security, privacy, and compliance

This section describes design considerations and recommendations to design a
topology in Google Cloud that meets your workload's security, privacy, and
compliance requirements.

| Component | Design considerations and recommendations |
|---|---|
| Virtual Private Cloud (VPC) | **Tenant isolation** : In this architecture, you deploy each tenant in a dedicated Google Cloud project. To create a strict security boundary, combine tenant project-level isolation with PAB Policy and [VPC Service Controls](https://docs.cloud.google.com/vpc-service-controls/docs/overview) at the organization level. |
| IAM | **Access control** : To implement the [principle of least privilege](https://en.wikipedia.org/wiki/Principle_of_least_privilege), use a persona-based access model. For example, you can define custom IAM roles to ensure that a developer who builds an agent in one tenant can't access data in another tenant. |
| Cloud Armor | **Edge and internal WAF protection** : Cloud Armor provides security and WAF protection to defend the frontend portal against DDoS attacks and web vulnerabilities. A global external Application Load Balancer supports the full suite of advanced edge features, such as [bot management](https://docs.cloud.google.com/armor/docs/bot-management) and [Google Cloud Armor Adaptive Protection](https://docs.cloud.google.com/armor/docs/adaptive-protection-overview). If you deploy a regional internal Application Load Balancer, then Cloud Armor operates with a restricted set of standard WAF policies. The restricted set of policies are tailored for internal network boundaries and it includes policies like SQLi and XSS protection. For more information, see [Integrating Cloud Armor with other Google products](https://docs.cloud.google.com/armor/docs/integrating-cloud-armor). |
| Agent Platform | **Shared model endpoints**: To prevent abuse and ensure fair usage for shared model endpoints, implement one of the following strategies: - **Tenant-level rate limiting** : Enforce quotas in the frontend portal for each tenant before requests reach the shared endpoint. Enforce the quotas by doing the following: 1. Extract the tenant identity from the IAP context. 2. Track usage against predefined limits for each tenant by using an external store like [Memorystore for Redis](https://docs.cloud.google.com/memorystore/docs/redis/connect-redis-instance-functions). 3. Reject requests from tenants that exceed their limits. - **API Gateway** : To enforce per-tenant quotas by using API keys and usage plans, implement [API Gateway](https://docs.cloud.google.com/api-gateway/docs/about-api-gateway) before the shared endpoint. |
| Cloud Run | **Content rendering** : To enhance the security posture of the frontend portal, prioritize [server-side rendering (SSR)](https://developers.google.com/solutions/content-driven/hosting/rendering#server-side_rendering_ssr) over [client-side rendering (CSR)](https://developers.google.com/solutions/content-driven/hosting/rendering#client-side_rendering_csr). Compared to CSR, SSR offers these benefits: - Executes application logic and manages secrets within a controlled Google Cloud environment. - Reduces the client-side attack surface and prevents sensitive data leaks to the user's untrusted browser. - Limits data exposure by sending only the necessary HTML to the client. - Provides centralized output encoding to defend against cross-site scripting (XSS) attacks. |
| Security Command Center | **Centralized security monitoring** : To monitor for threats and enforce security policies such as multi-factor authentication (MFA) and data encryption, use the tools in the [Security Command Center](https://docs.cloud.google.com/security-command-center/docs/security-command-center-overview). |

#### More security recommendations

- [Google Cloud Well-Architected Framework AI and ML perspective: Security](https://docs.cloud.google.com/architecture/framework/perspectives/ai-ml/security)
- [Google's Approach for Secure AI Agents: An Introduction](https://storage.googleapis.com/gweb-research2023-media/pubtools/1018686.pdf)

### Reliability

This section describes design considerations and recommendations to build and
operate reliable infrastructure for your deployment in Google Cloud.

| Component | Design considerations and recommendations |
|---|---|
| Cloud Load Balancing | **Global routing** : A global external Application Load Balancer provides a single [Anycast](https://en.wikipedia.org/wiki/Anycast) IP address that automatically routes user traffic to the closest geographical Google edge. This configuration reduces latency through edge [Secure Sockets Layer (SSL)](https://docs.cloud.google.com/load-balancing/docs/ssl-policies-concepts) termination. It also ensures high availability if a region experiences an outage because it intelligently reroutes traffic to healthy regional backends. |
| Tenant | **Fault tolerance**: To tolerate or handle agent-level failures, deploy agents in isolated tenant projects. This isolation helps to ensure that operational issues or security incidents stay within a single business unit and don't affect other resources or business units. |
| Agent Platform | **Capacity planning** : If the number of requests to the model exceeds the allocated capacity, then the model returns [error code 429](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/deploy/error-code-429). For workloads that are business critical and that require consistently high throughput, you can reserve throughput by using [Provisioned Throughput](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/provisioned-throughput). |
| Agent Runtime | **Serverless scalability**: Agents that are deployed on Agent Runtime scale independently based on demand. A sudden spike in usage in one tenant doesn't exhaust the compute resources or affect the availability of an agent in another tenant project. **Error handling** : To handle transient errors like error code 429 rate limits, the agent orchestration logic uses [exponential backoff](https://en.wikipedia.org/wiki/Exponential_backoff). If a context deadline is exceeded, then the agent performs a [graceful shutdown](https://en.wikipedia.org/wiki/Graceful_exit) and it reports partial progress back to the user. For example, a context deadline can be exceeded due to slow tool calls, third-party API latency, processing massive datasets, or compute-intensive processing. |


For reliability principles and recommendations that are specific to AI and ML workloads, see
[AI and ML perspective: Reliability](https://docs.cloud.google.com/architecture/framework/perspectives/ai-ml/reliability)
in the Well-Architected Framework.

### Operational efficiency

This section describes the factors to consider when you use this reference
architecture to design a Google Cloud topology that you can operate
efficiently.

| Component | Design considerations and recommendations |
|---|---|
| Google Cloud Observability | **Centralized monitoring**: Logging and Monitoring let you monitor the health and performance of the entire platform. You can set up alerts to proactively detect and troubleshoot issues without allowing access to sensitive data. |
| All of the products in the architecture | **Standardized deployments** : Using Agent Platform within a standardized tenant architecture pattern lets you establish a consistent baseline when you onboard new tenants. To reduce operational burden, automate the deployment process by using [Infrastructure as Code (IaC)](https://en.wikipedia.org/wiki/Infrastructure_as_code) tools like Terraform. For Terraform code that you can use to build and deploy a multi-tenant agentic AI system, see the [Deployment](https://docs.cloud.google.com/architecture/multi-tenant-agentic-ai-system#deployment) section of this document. |


For operational excellence principles and recommendations that are specific to AI and ML workloads, see
[AI and ML perspective: Operational excellence](https://docs.cloud.google.com/architecture/framework/perspectives/ai-ml/operational-excellence)
in the Well-Architected Framework.

### Cost optimization

This section provides guidance to optimize the cost of setting up and operating
a Google Cloud topology that you build by using this reference
architecture.

| Component | Design considerations and recommendations |
|---|---|
| Agent Platform | **Token consumption**: To manage costs and prevent your AI model from exceeding context windows, use the following strategies to manage context for the AI model: - **Context summarization**: Instead of saving an entire session conversation as context, use an AI model to summarize older conversation and less critical information. - **Prune outputs**: Identify and remove less relevant or verbose parts of tool outputs or retrieved context. For example, if you only need the column names from your data, you can remove excessive metadata from a database schema fetch. This strategy requires custom logic that uses heuristics, filtering, or a small language model (SLM) to extract the most important information. - **Maximum token limit**: To help prevent infinite loops and to help control costs, enforce a session maximum token limit. **Model endpoints**: To manage API quotas and resource utilization, you can deploy Agent Platform endpoints in either a dedicated configuration or a shared configuration: - **Dedicated endpoints**: When you deploy endpoints within each tenant project, you provide inherent quota isolation. Each tenant's usage counts against its own project quotas, which prevents inter-tenant impact. Compared to shared endpoints, dedicated endpoints offer simpler quota management. However, dedicated endpoints prevent you from taking advantage of the potential cost savings of a shared endpoint. - **Shared endpoints**: To optimize costs, you can host a shared endpoint in the central governance and security hub. Because all of the tenants share the same pool of quotas, to prevent malicious attacks, you must implement mitigation strategies such as tenant-level rate limiting or quota enforcement with API Gateway. Compared to dedicated endpoints, shared endpoints are more cost-effective. However, shared endpoints require additional engineering effort and they can introduce latency and management overhead. For information about costs on Agent Platform, see [Cost of building and deploying AI models in Agent Platform](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing). |
| Cloud Run | **Instrumentation** : Instrumentation lets you monitor performance, troubleshoot issues, and track resource usage for each tenant. To identify the tenant for each request, extract the user identity from the context that IAP provides. For information about how to instrument your application, see [Choose an instrumentation approach](https://docs.cloud.google.com/stackdriver/docs/instrumentation/choose-approach#run). |
| Model Armor | **Centralized prompt filtering**: To enforce strict governance and a zero-trust posture, this architecture deploys Model Armor at two layers: in the routing hub and within each tenant project. Although this two-layered approach helps to ensure data sovereignty, it increases latency and operational costs. To reduce costs and system complexity, filter all of the prompts and responses by deploying Model Armor exclusively in the routing hub. |
| All of the products in the architecture | **Shared infrastructure**: Shared core infrastructure components, such as the frontend portal, the central governance and security hub, and Agent Platform, can reduce costs compared to when you build a separate, custom stack for each agent. **Platform overhead**: To distribute the shared costs of the central governance and security hub, use an allocation model that fits your tracking capabilities and usage patterns. We recommend that you use one of the following cost allocation models: - **Even split allocation**: An even split model allocates shared costs equally across all of the tenants. Use this model when the platform is a baseline utility or when the overhead of granular tracking outweighs the cost benefits. - **Proportional allocation** : A proportional model, or [chargeback process](https://cloud.google.com/blog/topics/cost-management/principles-for-designing-a-chargeback-process), allocates shared costs based on the proportion of direct costs that each tenant incurs. Use this model when tenant consumption varies drastically and you have robust telemetry, such as Resource Manager [labels](https://docs.cloud.google.com/resource-manager/docs/labels-overview) and log parsing, to attribute costs accurately. - **Fixed allocation**: A fixed, or tiered, model allocates shared costs based on business-defined coefficients. Use this model when tenants require different service-level agreements (SLAs). A fixed model allocation lets you charge fixed rates for premium dedicated capabilities versus standard shared capabilities. For more information about how to allocate shared services costs, see [Cloud FinOps: Shared services cost allocation](https://services.google.com/fh/files/misc/cloud_finops_shared_services_cost_allocation_whitepaper.pdf). **Centralized cost management** : To accurately track the total cost of ownership (TCO) of your agentic AI system and attribute costs to individual business units, use labels and Cloud Billing export data. For more information about how to use labels for cost awareness, see [Foster a culture of cost awareness](https://docs.cloud.google.com/architecture/framework/cost-optimization/foster-culture-cost-awareness#use_a_consistent_and_standard_set_of_labels_for_all_your_resources). |

To estimate the cost of your Google Cloud resources, use the
[Google Cloud Pricing Calculator](https://cloud.google.com/products/calculator).


For cost optimization principles and recommendations that are specific to AI and ML workloads, see
[AI and ML perspective: Cost optimization](https://docs.cloud.google.com/architecture/framework/perspectives/ai-ml/cost-optimization)
in the Well-Architected Framework.

## Deployment

To deploy this reference architecture, use the
[multi-tenant agentic AI Terraform](https://github.com/GoogleCloudPlatform/architecture-center-samples/tree/main/terraform-google-multi-tenant-agentic-ai)
example that's available in GitHub.

## What's next

- Learn more about how to [build an agent with ADK and Agents CLI in Agent Platform](https://docs.cloud.google.com/gemini-enterprise-agent-platform/agents/quickstart-adk).
- Learn how to [use the Agent Platform remote MCP server](https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/use-agent-platform-mcp).
- Learn about [best practices for enabling VPC Service Controls](https://docs.cloud.google.com/vpc-service-controls/docs/enable).
- Learn how to [manage deployed agents](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/manage-deployed-agents) on Agent Runtime.
- Learn about [best practices for scaling and high traffic](https://docs.cloud.google.com/model-armor/best-practices).
- To implement just-in-time elevation strategies, explore how to use [Privileged Access Manager](https://docs.cloud.google.com/iam/docs/pam-overview).
- For an overview of architectural principles and recommendations that are specific to AI and ML workloads in Google Cloud, see the [AI and ML perspective](https://docs.cloud.google.com/architecture/framework/perspectives/ai-ml) in the Well-Architected Framework.
- For more reference architectures, diagrams, and best practices, explore the [Cloud Architecture Center](https://docs.cloud.google.com/architecture).

## Contributors

Authors:

- [Shivank Awasthi](https://www.linkedin.com/in/shivank-awasthi/) \| Field Solutions Architect
- [Utkarsh Bhardwaj](https://www.linkedin.com/in/utkarsh-bhardwaj-935251196/) \| Technical Solutions Consultant, Agentic AI, Apps, Cloud Platforms, and Infrastructure

<br />

Other contributors:

- [Adrian Corona](https://www.linkedin.com/in/adriancorona/) \| Manager, Global Services Delivery, Security
- [Agnieszka Kołkiewicz](https://www.linkedin.com/in/agnieszka-kolkiewicz/) \| GSD AI Manager
- [Anmol Sachdeva](https://www.linkedin.com/in/greatdevaks/) \| Ads Solutions Engineer, Global Business
- [Ashish Agarwal](https://www.linkedin.com/in/ashish-agarwal-4433a315/) \| EMEA North lead, Global Services Delivery
- [Ashmita Kapoor](https://www.linkedin.com/in/ashmitakapoor/) \| JAPAC GenAI FSA, and Applied AI CE Manager
- [Ashutosh Gupta](https://www.linkedin.com/in/ashutosh-gupta-33145b6b/) \| Director, Global Service Delivery
- [Aspen Sherrill](https://www.linkedin.com/in/aspensherrill/) \| Cloud Security Architect
- [Chinmay Deshpande](https://www.linkedin.com/in/chinmay-deshpande-0282972b) \| Cloud Migration Consultant, Infrastructure
- [Gaurav Taneja](https://www.linkedin.com/in/gtaneja/) \| EMEA South Infra, Data, AI, and GDC Delivery Lead
- [Ishmeet Mehta](https://www.linkedin.com/in/ishmeet-mehta-66361623b/) \| NorthAm Platform Specialist, Apps CE
- [Joanna Nowek](https://www.linkedin.com/in/joanna-nowek/) \| AI Transformation Consultant
- [Kumar Dhanagopal](https://www.linkedin.com/in/kumardhanagopal) \| Cross-Product Solution Developer
- [Mark Schlagenhauf](https://www.linkedin.com/in/mark-schlagenhauf-63b98) \| Technical Writer, Networking
- [Matthias Ziener](https://www.linkedin.com/in/mziener/) \| Manager, Global Service Delivery
- Olu Akinrolabu \| Security Cloud Consultant
- [Paweł Tokarski](https://www.linkedin.com/in/paweltokarski/) \| EMEA South Infra, Data, AI, and GDC Delivery Lead
- [Paweł Glica](https://www.linkedin.com/in/pawelglica) \| Core EMEA Practise Lead
- [Prabha Arya](https://www.linkedin.com/in/prabha-arya/) \| Strategic Cloud Engineer
- [Samantha He](https://www.linkedin.com/in/samantha-he-05a98173) \| Technical Writer
- [Suchit Puri](https://www.linkedin.com/in/suchitpuri/) \| Global AI Practice Lead
- [Thomas Cliett](https://www.linkedin.com/in/thomascliett/) \| Director of delta AI
- [Valentín Huerta](https://www.linkedin.com/in/valentinhuerta/) \| AI Engineer

<br />