# Glossary

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This glossary provides definitions for technical terms, acronyms, and concepts used throughout Project Aura documentation. Terms are organized alphabetically with cross-references to related concepts.

---

## A

### Agent {#agent}

A specialized AI component within Project Aura that performs a specific function in the vulnerability remediation workflow. Agents collaborate through the [Orchestrator](#orchestrator) to detect, remediate, and validate security issues.

**Related:** [Coder Agent](#coder-agent), [Reviewer Agent](#reviewer-agent), [Validator Agent](#validator-agent), [Multi-Agent System](#multi-agent-system)

---

### API Rate Limit {#api-rate-limit}

The maximum number of API requests permitted within a specified time window. Rate limits protect platform stability and ensure fair resource allocation across tenants.

**See also:** [Service Limits](./service-limits.md)

---

### Artifact {#artifact}

A file or set of files produced during the vulnerability remediation process. Artifacts include generated patches, test results, audit logs, and compliance reports.

---

### Autonomy Level {#autonomy-level}

A configurable setting that determines how much human oversight is required for different types of actions. Project Aura supports four autonomy levels.

| Level | Name | Description |
|-------|------|-------------|
| 0 | Manual | Human approval required for all actions |
| 1 | Assisted | AI suggestions with human execution |
| 2 | Supervised | AI execution with human approval |
| 3 | Autonomous | AI execution with post-hoc review |

**Related:** [HITL](#hitl), [Policy Preset](#policy-preset)

---

## B

### Bedrock {#bedrock}

AWS Bedrock is the managed service that provides access to large language models (LLMs) used by Project Aura for code understanding, patch generation, and natural language processing. Bedrock is available in both commercial AWS and GovCloud regions.

---

### Blast Radius {#blast-radius}

The potential scope of impact if a security vulnerability is exploited or a patch causes unintended side effects. Aura calculates blast radius by analyzing code dependencies, call graphs, and deployment topology.

---

## C

### Call Graph {#call-graph}

A directed graph representing the calling relationships between functions or methods in a codebase. Stored in [Neptune](#neptune) and used to understand vulnerability propagation and patch impact.

---

### CMMC {#cmmc}

**Cybersecurity Maturity Model Certification** - A unified standard for implementing cybersecurity across the defense industrial base. Project Aura supports CMMC Level 2 and Level 3 compliance requirements.

| Level | Description | Control Families |
|-------|-------------|------------------|
| Level 1 | Basic Cyber Hygiene | 17 practices |
| Level 2 | Intermediate Hygiene | 110 practices |
| Level 3 | Good Cyber Hygiene | 130+ practices |

**Related:** [NIST 800-53](#nist-800-53), [FedRAMP](#fedramp)

---

### Coder Agent {#coder-agent}

The AI agent responsible for generating security patches. The Coder Agent uses [LLM](#llm) capabilities combined with code context from [GraphRAG](#graphrag) to produce syntactically correct, context-aware fixes.

**Capabilities:**
- Vulnerability analysis and understanding
- Patch generation with multiple options
- Confidence scoring for generated code
- Test case generation for patches

**Related:** [Agent](#agent), [Multi-Agent System](#multi-agent-system)

---

### Confidence Score {#confidence-score}

A numerical value (0.0 to 1.0) indicating the AI system's certainty about a prediction, classification, or generated output. Low confidence scores may trigger additional review or [HITL](#hitl) escalation.

---

### Constitutional AI {#constitutional-ai}

An AI alignment methodology that uses explicit principles to guide agent behavior through self-supervision. Project Aura implements 16 constitutional principles across six categories to ensure safe, helpful, and compliant outputs.

| Category | Principles | Purpose |
|----------|------------|---------|
| Safety | 3 | Prevent harmful actions |
| Compliance | 2 | Maintain regulatory alignment |
| Anti-Sycophancy | 2 | Ensure honest feedback |
| Transparency | 2 | Provide clear reasoning |
| Helpfulness | 2 | Deliver genuine assistance |
| Code Quality | 4 | Maintain coding standards |

**Related:** [Critique-Revision](#critique-revision), [Guardrails](#guardrails)

---

### Context Window {#context-window}

The maximum amount of text (measured in tokens) that an LLM can process in a single request. Aura's [Context Retrieval Service](#context-retrieval-service) optimizes context selection to stay within model limits while maximizing relevant information.

---

### Context Retrieval Service {#context-retrieval-service}

A core Aura service that retrieves relevant code context for agent tasks. Uses hybrid search combining [Neptune](#neptune) graph queries and [OpenSearch](#opensearch) vector similarity to provide comprehensive code understanding.

**Retrieval strategies:**
- Graph traversal (call graphs, dependencies, inheritance)
- Semantic similarity (vector embeddings)
- Three-way fusion (combining multiple sources)

---

### Critique-Revision {#critique-revision}

The two-phase process used by [Constitutional AI](#constitutional-ai) to improve agent outputs. First, the output is critiqued against constitutional principles; then, flagged outputs are revised to address identified concerns.

---

### CVE {#cve}

**Common Vulnerabilities and Exposures** - A standardized identifier for publicly known security vulnerabilities. Each CVE has a unique ID (e.g., CVE-2024-1234) used across the security industry.

**Related:** [CVSS](#cvss), [Vulnerability](#vulnerability)

---

### CVSS {#cvss}

**Common Vulnerability Scoring System** - A standardized method for rating the severity of security vulnerabilities on a 0.0 to 10.0 scale.

| Score Range | Severity | Aura Treatment |
|-------------|----------|----------------|
| 0.0 | None | Informational |
| 0.1 - 3.9 | Low | Standard processing |
| 4.0 - 6.9 | Medium | Priority queue |
| 7.0 - 8.9 | High | Expedited remediation |
| 9.0 - 10.0 | Critical | Immediate escalation |

**Related:** [CVE](#cve), [Vulnerability](#vulnerability)

---

## D

### Dashboard {#dashboard}

A customizable visual interface displaying metrics, trends, and status information. Aura supports role-based default dashboards and user-created custom layouts.

**Related:** [Widget](#widget)

---

### Dependency Graph {#dependency-graph}

A directed graph representing relationships between software components, libraries, and modules. Used for impact analysis and understanding vulnerability propagation through transitive dependencies.

---

### Drift Detection {#drift-detection}

The process of identifying configuration changes between environments or from established baselines. The [Environment Validator Agent](#environment-validator-agent) performs continuous drift detection to prevent cross-environment contamination.

---

### DynamoDB {#dynamodb}

AWS DynamoDB is a fully managed NoSQL database service used by Aura for storing metadata, session state, job queues, and dashboard configurations. Supports single-digit millisecond latency at any scale.

---

## E

### EKS {#eks}

**Amazon Elastic Kubernetes Service** - The managed Kubernetes platform used to run Aura's containerized services. EKS provides automatic scaling, security patching, and high availability.

---

### Embedding {#embedding}

A dense vector representation of text, code, or other data that captures semantic meaning. Aura uses embeddings for similarity search, code clustering, and context retrieval.

**Embedding models:**
- Code embeddings: CodeBERT, StarCoder
- Text embeddings: Amazon Titan Embeddings

---

### Environment Validator Agent {#environment-validator-agent}

An autonomous agent that validates environment consistency across deployments. Detects misconfigurations, cross-environment contamination, and configuration drift before they cause failures.

**Validation categories:**
- ConfigMap and Secret references
- Resource ARN environment alignment
- Container image registry validation
- Environment variable consistency

---

### Ephemeral Environment {#ephemeral-environment}

A temporary, isolated environment created for testing purposes and automatically destroyed after use. Aura provisions ephemeral environments in [Fargate](#fargate) for [Sandbox](#sandbox) testing.

**Lifecycle:**
1. Provisioned on demand
2. Isolated network and storage
3. Test execution
4. Results captured
5. Automatic cleanup

---

## F

### Fargate {#fargate}

AWS Fargate is a serverless compute engine for containers. Aura uses Fargate for [Sandbox](#sandbox) environments because it provides strong isolation without managing server infrastructure.

---

### FedRAMP {#fedramp}

**Federal Risk and Authorization Management Program** - A US government program providing a standardized approach to security assessment for cloud services. Aura supports FedRAMP High authorization through AWS GovCloud deployment.

| Level | Data Sensitivity | Aura Support |
|-------|------------------|--------------|
| Low | Public | Commercial AWS |
| Moderate | Controlled | Commercial AWS |
| High | Classified | GovCloud deployment |

**Related:** [CMMC](#cmmc), [GovCloud](#govcloud)

---

## G

### GovCloud {#govcloud}

AWS GovCloud (US) is an isolated AWS region designed to meet US government compliance requirements including FedRAMP High and ITAR. Aura can be deployed to GovCloud for regulated workloads.

---

### GPU Workload {#gpu-workload}

A compute task requiring graphics processing unit acceleration. Aura uses GPUs for code embedding generation, model fine-tuning, and local LLM inference.

| Workload Type | Typical Duration | GPU Memory |
|---------------|------------------|------------|
| Code Embedding | 5-60 minutes | 4-8 GB |
| Model Fine-tuning | 1-4 hours | 8-16 GB |
| Local Inference | Continuous | 8-16 GB |

---

### GraphRAG {#graphrag}

A retrieval architecture that combines graph database queries with semantic search to provide comprehensive context for AI systems. Aura's Hybrid GraphRAG uses [Neptune](#neptune) for structural queries and [OpenSearch](#opensearch) for vector similarity.

**Retrieval modes:**
- `CALL_GRAPH` - Function calling relationships
- `DEPENDENCIES` - Package and module dependencies
- `INHERITANCE` - Class hierarchy relationships
- `REFERENCES` - Symbol references and usages
- `RELATED` - Semantically similar code

**Related:** [RAG](#rag), [Neptune](#neptune), [OpenSearch](#opensearch)

---

### Guardrails {#guardrails}

Safety mechanisms that prevent AI agents from taking potentially harmful actions without human approval. Guardrails operate independently of [Autonomy Level](#autonomy-level) settings.

**Always-require-approval actions:**
- Production deployments
- Data deletion
- Security configuration changes
- Compliance-affecting changes

**Related:** [Constitutional AI](#constitutional-ai), [HITL](#hitl)

---

## H

### HIPAA {#hipaa}

**Health Insurance Portability and Accountability Act** - US legislation providing data privacy and security provisions for safeguarding medical information. Aura supports HIPAA compliance through encryption, access controls, and audit logging.

---

### HITL {#hitl}

**Human-in-the-Loop** - A workflow pattern where AI systems request human approval before executing certain actions. Aura's HITL system is configurable through [Autonomy Levels](#autonomy-level) and [Policy Presets](#policy-preset).

**HITL workflow stages:**
1. Agent generates proposed action
2. Action queued for human review
3. Human approves, rejects, or modifies
4. Approved action executed
5. Audit trail recorded

**Related:** [Autonomy Level](#autonomy-level), [Approval Queue](#approval-queue)

---

### Hybrid Search {#hybrid-search}

A search strategy combining multiple retrieval methods to improve result quality. Aura's hybrid search fuses graph-based structural queries with vector-based semantic search.

---

## I

### Idempotent {#idempotent}

An operation that produces the same result regardless of how many times it is executed. Aura's patch application is designed to be idempotent to prevent duplicate changes.

---

### Inheritance Graph {#inheritance-graph}

A directed graph representing class inheritance relationships in object-oriented code. Used to understand the full scope of changes when patching base classes.

---

## J

### Job {#job}

A unit of work in Aura's processing queue. Jobs include vulnerability scans, patch generation tasks, sandbox tests, and scheduled reports.

**Job states:**
- `PENDING` - Queued for processing
- `RUNNING` - Currently executing
- `COMPLETED` - Successfully finished
- `FAILED` - Terminated with error
- `CANCELLED` - User-cancelled

---

## K

### KMS {#kms}

**AWS Key Management Service** - A managed service for creating and controlling encryption keys. Aura uses customer-managed KMS keys for encrypting data at rest in compliance with enterprise requirements.

---

## L

### Lambda {#lambda}

AWS Lambda is a serverless compute service that runs code in response to events. Aura uses Lambda for event-driven processing including threat intelligence feeds, scheduled evaluations, and webhook handlers.

---

### LLM {#llm}

**Large Language Model** - An AI model trained on large amounts of text data capable of understanding and generating human-like text. Aura uses LLMs (via [Bedrock](#bedrock)) for code understanding, patch generation, and natural language processing.

**Models used:**
- Claude 3.5 Sonnet - Primary reasoning model
- Claude 3 Haiku - Lightweight critique tasks
- Amazon Titan - Embeddings

---

## M

### Mean Time to Remediate {#mttr}

**MTTR** - The average time from vulnerability detection to deployed fix. A key metric for measuring security operations efficiency.

| Industry Benchmark | Typical MTTR | With Aura |
|--------------------|--------------|-----------|
| Critical vulnerabilities | 15-45 days | < 4 hours |
| High vulnerabilities | 30-90 days | < 24 hours |
| Medium vulnerabilities | 60-180 days | < 72 hours |

---

### Multi-Agent System {#multi-agent-system}

An architecture where multiple specialized AI agents collaborate to accomplish complex tasks. Aura's multi-agent system includes the [Orchestrator](#orchestrator), [Coder Agent](#coder-agent), [Reviewer Agent](#reviewer-agent), and [Validator Agent](#validator-agent).

---

## N

### Neptune {#neptune}

AWS Neptune is a fully managed graph database service. Aura uses Neptune to store and query code structure including call graphs, dependency graphs, and inheritance hierarchies.

**Query languages:**
- Gremlin (primary)
- SPARQL (supported)
- openCypher (planned)

**Related:** [GraphRAG](#graphrag), [Call Graph](#call-graph)

---

### NIST 800-53 {#nist-800-53}

A catalog of security and privacy controls published by the National Institute of Standards and Technology. Provides the control framework underlying [FedRAMP](#fedramp) and [CMMC](#cmmc) requirements.

---

## O

### OpenSearch {#opensearch}

AWS OpenSearch is a managed search and analytics service. Aura uses OpenSearch as a vector store for semantic code search and similarity matching.

**Capabilities:**
- k-NN vector search for code similarity
- Full-text search for code content
- Aggregations for analytics

**Related:** [GraphRAG](#graphrag), [Embedding](#embedding)

---

### Orchestrator {#orchestrator}

The central coordination agent that manages workflows, assigns tasks to specialized agents, tracks state, and enforces governance policies. All agent activities flow through the Orchestrator.

**Responsibilities:**
- Task decomposition and assignment
- State management and persistence
- Agent health monitoring
- Policy enforcement

**Related:** [Agent](#agent), [Multi-Agent System](#multi-agent-system)

---

## P

### Patch {#patch}

A set of code changes designed to fix a [Vulnerability](#vulnerability) or other issue. Aura generates patches automatically using the [Coder Agent](#coder-agent) and validates them in [Sandbox](#sandbox) environments.

**Patch metadata:**
- Affected files and line ranges
- Vulnerability reference (CVE)
- Confidence score
- Test results
- Approval status

---

### Policy Preset {#policy-preset}

A predefined configuration of [Autonomy Levels](#autonomy-level) and [Guardrails](#guardrails) tailored for specific use cases or industries.

| Preset | Description | Autonomy |
|--------|-------------|----------|
| `STRICT_SECURITY` | Maximum oversight | Level 0-1 |
| `COMPLIANCE_FIRST` | Audit-focused | Level 1-2 |
| `BALANCED` | General purpose | Level 2 |
| `DEVELOPMENT` | Fast iteration | Level 2-3 |
| `FEDRAMP_HIGH` | Government compliance | Level 0-1 |
| `CMMC_L3` | Defense contractors | Level 1 |
| `SOX_COMPLIANT` | Financial services | Level 1-2 |

**Related:** [Autonomy Level](#autonomy-level), [HITL](#hitl)

---

## R

### RAG {#rag}

**Retrieval-Augmented Generation** - An AI architecture that combines information retrieval with text generation. RAG systems first retrieve relevant context from a knowledge base, then use that context to generate more accurate responses.

**Related:** [GraphRAG](#graphrag), [Hybrid Search](#hybrid-search)

---

### Repository {#repository}

A source code repository connected to Aura for scanning and remediation. Repositories can be connected via OAuth integration with GitHub, GitLab, or other Git providers.

---

### Reviewer Agent {#reviewer-agent}

The AI agent responsible for validating generated patches against security best practices, coding standards, and organizational policies. The Reviewer Agent identifies issues before patches reach [Sandbox](#sandbox) testing.

**Review criteria:**
- Security vulnerability coverage
- Coding standard compliance
- Backward compatibility
- Test coverage

**Related:** [Agent](#agent), [Coder Agent](#coder-agent)

---

## S

### Sandbox {#sandbox}

An isolated testing environment where patches are validated before reaching human reviewers. Aura sandboxes run in [Fargate](#fargate) with network isolation, resource limits, and automatic cleanup.

**Validation categories:**
1. Syntax validation (compiles without errors)
2. Unit test execution
3. Security regression testing
4. Performance impact assessment
5. Dependency compatibility

**Related:** [Ephemeral Environment](#ephemeral-environment), [Validator Agent](#validator-agent)

---

### SCA {#sca}

**Software Composition Analysis** - The process of identifying third-party libraries and their known vulnerabilities. Aura integrates SCA results with code analysis for comprehensive security coverage.

---

### SAST {#sast}

**Static Application Security Testing** - Security testing performed on source code without executing the application. Aura combines SAST findings with AI-powered analysis for vulnerability detection.

---

### Semantic Cache {#semantic-cache}

A caching mechanism that stores AI model responses keyed by semantic similarity rather than exact match. Reduces LLM costs by reusing similar previous responses.

---

### SOX {#sox}

**Sarbanes-Oxley Act** - US legislation establishing requirements for financial reporting and internal controls. Aura supports SOX Section 404 compliance through audit logging, change tracking, and approval workflows.

---

## T

### Tenant {#tenant}

An organization or customer isolated within Aura's multi-tenant architecture. Each tenant has separate data, configurations, and user accounts with no cross-tenant visibility.

---

### Threat Intelligence {#threat-intelligence}

Information about current and emerging security threats used to prioritize vulnerability remediation. Aura integrates threat intelligence feeds to identify actively exploited vulnerabilities.

---

### Token {#token}

The basic unit of text processing for LLMs. Tokens are word fragments, typically averaging 4 characters per token in English text and 2-3 characters per token in code.

---

## V

### Validator Agent {#validator-agent}

The AI agent responsible for testing patches in [Sandbox](#sandbox) environments. The Validator Agent executes test suites, analyzes results, and determines patch readiness for human review.

**Validation outputs:**
- Test execution results
- Coverage metrics
- Performance comparison
- Security scan results
- Approval recommendation

**Related:** [Agent](#agent), [Sandbox](#sandbox)

---

### Vector Embedding {#vector-embedding}

See [Embedding](#embedding).

---

### Vulnerability {#vulnerability}

A weakness in software that can be exploited to compromise security. Aura detects, prioritizes, and remediates vulnerabilities through its multi-agent system.

**Vulnerability sources:**
- Code scanning (SAST)
- Dependency analysis (SCA)
- External CVE feeds
- Threat intelligence

**Related:** [CVE](#cve), [CVSS](#cvss), [Patch](#patch)

---

## W

### Widget {#widget}

A configurable dashboard component displaying a specific metric, chart, or status indicator. Aura supports 15+ widget types with drag-drop layout customization.

**Widget categories:**
- Metrics (counters, gauges, sparklines)
- Charts (line, bar, pie, heatmap)
- Tables (data grids, activity feeds)
- Status (health indicators, alerts)

**Related:** [Dashboard](#dashboard)

---

## Acronym Quick Reference

| Acronym | Full Name | Category |
|---------|-----------|----------|
| API | Application Programming Interface | Technical |
| ARN | Amazon Resource Name | AWS |
| CAI | Constitutional AI | AI/ML |
| CI/CD | Continuous Integration/Continuous Deployment | DevOps |
| CMMC | Cybersecurity Maturity Model Certification | Compliance |
| CVE | Common Vulnerabilities and Exposures | Security |
| CVSS | Common Vulnerability Scoring System | Security |
| DynamoDB | Amazon DynamoDB | AWS |
| EKS | Elastic Kubernetes Service | AWS |
| FedRAMP | Federal Risk and Authorization Management Program | Compliance |
| GPU | Graphics Processing Unit | Hardware |
| GraphRAG | Graph Retrieval-Augmented Generation | AI/ML |
| HIPAA | Health Insurance Portability and Accountability Act | Compliance |
| HITL | Human-in-the-Loop | AI/ML |
| IAM | Identity and Access Management | AWS |
| KMS | Key Management Service | AWS |
| LLM | Large Language Model | AI/ML |
| MTTR | Mean Time to Remediate | Metrics |
| NIST | National Institute of Standards and Technology | Compliance |
| RAG | Retrieval-Augmented Generation | AI/ML |
| SaaS | Software as a Service | Business |
| SAST | Static Application Security Testing | Security |
| SCA | Software Composition Analysis | Security |
| SOX | Sarbanes-Oxley Act | Compliance |
| VPC | Virtual Private Cloud | AWS |

---

**Related Documentation:**
- [Core Concepts](../core-concepts/index.md) - Deep-dive into platform architecture
- [Getting Started](../getting-started/index.md) - Platform overview and setup
- [Service Limits](./service-limits.md) - Platform quotas and constraints
