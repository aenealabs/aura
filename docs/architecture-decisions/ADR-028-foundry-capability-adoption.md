# ADR-028: Microsoft Foundry Capability Adoption Plan

**Status:** Deployed
**Date:** 2025-12-07
**Decision Makers:** Project Aura Team
**Related:** ADR-022 (GitOps), ADR-023 (AgentCore Gateway), ADR-025 (RuntimeIncidentAgent)

## Context

A comprehensive competitive analysis of Microsoft Foundry (formerly Azure AI Foundry) identified capability gaps that Project Aura should address to maintain competitive positioning. While Aura has significant advantages in code-specific GraphRAG, automated patch generation, ephemeral sandbox testing, and GovCloud-native architecture, several Foundry capabilities would enhance our enterprise readiness and developer experience.

**Analysis Source:** `research/MICROSOFT_FOUNDRY_COMPARATIVE_ANALYSIS.md`

### Aura's Competitive Advantages (Preserve and Enhance)

| Advantage | Foundry Limitation | Aura Strategy |
|-----------|-------------------|---------------|
| **Hybrid GraphRAG** | Optional integration (not native) | Continue innovation in code-specific graph queries |
| **Automated Patch Generation** | Relies on GitHub Copilot (separate product) | Core differentiator; accelerate Coder Agent capabilities |
| **Ephemeral Sandbox Testing** | Project-level isolation only | Unique for security patch validation |
| **GovCloud Native** | Azure GCC High (different ecosystem) | Stronger for DoD/IC customers on AWS |
| **Code-Specific Agents** | Generic agent framework | Domain expertise is defensible moat |
| **RuntimeIncidentAgent** | No direct equivalent | Unique competitive positioning vs AWS DevOps Agent |

### Identified Gaps to Address

**High Priority (Q1 2026):**
1. OpenTelemetry Adoption - Industry-standard observability
2. Model Router - Cost optimization via dynamic model selection
3. Agentic Retrieval - Query decomposition for complex questions
4. VS Code Extension - Developer IDE integration

**Medium Priority (Q2-Q3 2026):**
1. TypeScript SDK - Developer ecosystem expansion
2. A2A Protocol Support - Cross-platform agent interoperability
3. Deep Research Agent - Automated research capabilities
4. Red-Teaming Automation - Adversarial testing of AI outputs
5. Connector Expansion - Enterprise system integrations (ServiceNow, Splunk, SIEM)

## Decision

Adopt a phased implementation plan to close identified capability gaps while preserving Aura's competitive advantages in code-specific intelligence and GovCloud compliance.

## Implementation Plan

### Phase 1: OpenTelemetry Adoption (Q1 2026)

**Effort:** 2-3 sprints
**Owner:** Platform Team
**Priority:** High

#### Objective

Migrate from CloudWatch-only observability to OpenTelemetry (OTel) for industry-standard tracing and multi-vendor compatibility.

#### AWS Service Mapping

| Component | AWS Service | Purpose |
|-----------|-------------|---------|
| OTel Collector | EKS DaemonSet | Collect traces from all pods |
| Trace Backend | AWS X-Ray | Native AWS trace storage |
| Metrics Backend | CloudWatch | Metrics aggregation |
| Export | OTLP | Datadog, Prometheus compatibility |

#### Implementation Tasks

**Sprint 1: Foundation**
- [ ] Deploy OpenTelemetry Collector as EKS DaemonSet
- [ ] Configure OTLP exporter to AWS X-Ray
- [ ] Create CloudFormation template `deploy/cloudformation/otel-collector.yaml`
- [ ] Add IAM role for X-Ray write permissions (IRSA)

**Sprint 2: Agent Instrumentation**
- [ ] Integrate `opentelemetry-sdk` into Agent Orchestrator
- [ ] Emit spans for agent invocations, tool calls, LLM requests
- [ ] Add trace context propagation across agent hierarchy
- [ ] Implement Microsoft's proposed semantic conventions for multi-agent systems

**Sprint 3: Integration & Testing**
- [ ] Configure Datadog APM adapter (Enterprise mode only)
- [ ] Create CloudWatch dashboards for OTel metrics
- [ ] Write integration tests for trace correlation
- [ ] Document OTel configuration in operational runbooks

#### File Changes

```
src/services/otel_instrumentation.py           # New: OTel SDK integration (~400 lines)
src/agents/base_agent.py                       # Modified: Add span creation
src/agents/meta_orchestrator.py                # Modified: Trace context propagation
deploy/kubernetes/otel-collector/              # New: DaemonSet + ConfigMap
deploy/cloudformation/otel-collector.yaml      # New: IAM roles, X-Ray config
```

#### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Trace coverage | >95% of agent invocations | X-Ray sampling |
| Trace correlation | 100% across agent hierarchy | End-to-end trace tests |
| Third-party export latency | <100ms | OTel collector metrics |

#### Dependencies

- EKS cluster operational (complete)
- IRSA for service accounts (complete)
- ArgoCD for deployment (complete via ADR-022)

---

### Phase 2: Model Router for Cost Optimization (Q1 2026)

**Effort:** 1-2 sprints
**Owner:** ML Platform Team
**Priority:** High

#### Objective

Implement dynamic model selection to optimize cost/quality/latency tradeoffs per request.

#### AWS Service Mapping

| Component | AWS Service | Purpose |
|-----------|-------------|---------|
| Model Selection | Lambda | Lightweight routing logic |
| Model Invocation | Bedrock | Claude Haiku, Sonnet, Opus |
| Cost Tracking | DynamoDB | Per-investigation cost attribution |
| Configuration | SSM Parameter Store | Model pricing, thresholds |

#### Implementation Tasks

**Sprint 1: Router Core**
- [ ] Create `src/services/model_router.py` with routing logic
- [ ] Define task complexity scoring algorithm
- [ ] Implement cost/quality/latency scoring per model
- [ ] Add model selection to BedrockLLMService

**Sprint 2: Integration & Optimization**
- [ ] Configure routing rules in SSM Parameter Store
- [ ] Track per-investigation model costs in DynamoDB
- [ ] Add CloudWatch metrics for model selection decisions
- [ ] Implement A/B testing framework for routing rules

#### Routing Strategy

```python
# Task Complexity → Model Selection
COMPLEXITY_ROUTING = {
    "simple": "anthropic.claude-3-haiku-20240307",      # $0.25/1M input tokens
    "medium": "anthropic.claude-3-5-sonnet-20241022",   # $3.00/1M input tokens
    "complex": "anthropic.claude-3-opus-20240229",      # $15.00/1M input tokens
}

# Task Classification
SIMPLE_TASKS = ["summarization", "formatting", "simple_queries"]
MEDIUM_TASKS = ["code_review", "patch_generation", "RCA_analysis"]
COMPLEX_TASKS = ["architecture_design", "multi_file_refactor", "security_audit"]
```

#### File Changes

```
src/services/model_router.py                   # New: Routing logic (~350 lines)
src/services/bedrock_llm_service.py           # Modified: Integrate router
src/config/model_config.py                     # New: Model pricing, thresholds
deploy/cloudformation/ssm-parameters.yaml      # Modified: Add model config
```

#### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Cost reduction | 30-50% | DynamoDB cost tracking |
| Quality parity | No regression | Automated evaluation suite |
| Routing accuracy | >90% | A/B testing results |

#### Dependencies

- Bedrock access to multiple models (complete - Haiku, Sonnet approved)
- BedrockLLMService operational (complete)
- DynamoDB cost tracking table (complete)

---

### Phase 3: Agentic Retrieval Enhancement (Q1 2026)

**Effort:** 2-3 sprints
**Owner:** Context Retrieval Team
**Priority:** High

#### Objective

Enhance Context Retrieval Service with query decomposition and parallel subquery execution for complex questions.

#### AWS Service Mapping

| Component | AWS Service | Purpose |
|-----------|-------------|---------|
| Query Analysis | Bedrock (Haiku) | Decompose complex queries |
| Parallel Execution | Lambda + Step Functions | Execute subqueries concurrently |
| Graph Retrieval | Neptune | Structural code relationships |
| Vector Retrieval | OpenSearch | Semantic similarity search |
| Result Aggregation | Lambda | Relevance ranking, deduplication |

#### Implementation Tasks

**Sprint 1: Query Analyzer**
- [ ] Create `src/services/query_analyzer.py` with LLM-powered decomposition
- [ ] Implement query intent classification (structural, semantic, hybrid)
- [ ] Add parallel subquery planning logic
- [ ] Create unit tests for decomposition accuracy

**Sprint 2: Parallel Execution**
- [ ] Modify Context Retrieval Service for concurrent Neptune + OpenSearch queries
- [ ] Implement Step Functions workflow for parallel subquery execution
- [ ] Add result aggregation with relevance ranking
- [ ] Create CloudWatch metrics for query latency breakdown

**Sprint 3: Caching & Optimization**
- [ ] Implement query pattern caching (DynamoDB TTL)
- [ ] Add result caching for common subqueries
- [ ] Optimize result ranking algorithm
- [ ] Write integration tests for end-to-end retrieval quality

#### Query Decomposition Example

```python
# Input: Complex query
"Find all authentication functions that call the database and were modified in the last sprint"

# Decomposed subqueries:
[
    {"type": "structural", "query": "functions with 'auth' in name"},
    {"type": "structural", "query": "functions that call database entities"},
    {"type": "temporal", "query": "files modified in date range"},
    {"type": "semantic", "query": "authentication and authorization patterns"}
]
```

#### File Changes

```
src/services/query_analyzer.py                 # New: Query decomposition (~500 lines)
src/services/parallel_query_executor.py        # New: Concurrent execution (~400 lines)
src/services/context_retrieval_service.py      # Modified: Integrate query analyzer
deploy/cloudformation/step-functions.yaml      # Modified: Add parallel query workflow
```

#### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Query relevance | +25% improvement | Automated relevance scoring |
| Complex query latency | <5s (p95) | CloudWatch metrics |
| Cache hit rate | >40% | DynamoDB metrics |

#### Dependencies

- Neptune operational (complete)
- OpenSearch operational (complete)
- BedrockLLMService for query analysis (complete)

---

### Phase 4: VS Code Extension (Q2 2026)

**Effort:** 4-6 sprints
**Owner:** Developer Experience Team
**Priority:** High

#### Objective

Build a VS Code extension for in-IDE vulnerability detection, real-time code review, and HITL approval workflow integration.

#### AWS Service Mapping

| Component | AWS Service | Purpose |
|-----------|-------------|---------|
| API Gateway | API Gateway (REST) | Extension backend API |
| Authentication | Cognito | Developer authentication |
| Real-time Updates | AppSync (WebSocket) | Push vulnerability findings |
| Patch Generation | Bedrock | Coder Agent invocation |

#### Implementation Tasks

**Sprint 1-2: Extension Core**
- [ ] Create VS Code extension scaffold with TypeScript
- [ ] Implement extension activation, settings, authentication
- [ ] Build connection to Aura API Gateway
- [ ] Add Problems panel integration for vulnerability findings

**Sprint 3-4: Vulnerability Detection**
- [ ] Implement real-time file scanning on save
- [ ] Show Reviewer Agent findings in Problems panel
- [ ] Add CodeLens for vulnerability highlights
- [ ] Create quick-fix suggestions linked to Coder Agent

**Sprint 5-6: HITL Integration**
- [ ] Build sidebar panel for HITL approval workflow
- [ ] Add patch preview with diff view
- [ ] Implement one-click patch application
- [ ] Create notification for approval status updates

#### Extension Features

| Feature | Description | API Endpoint |
|---------|-------------|--------------|
| **Scan on Save** | Trigger vulnerability scan | `POST /api/v1/scan` |
| **View Findings** | List vulnerabilities in file | `GET /api/v1/findings/{file}` |
| **Generate Patch** | Request Coder Agent patch | `POST /api/v1/patches` |
| **Apply Patch** | Apply approved patch | `POST /api/v1/patches/{id}/apply` |
| **HITL Status** | Check approval workflow | `GET /api/v1/approvals/{id}` |

#### File Changes

```
vscode-extension/                              # New: Extension root
vscode-extension/src/extension.ts              # Main extension entry
vscode-extension/src/providers/               # CodeLens, Problems, TreeView
vscode-extension/src/api/                      # API client
vscode-extension/package.json                  # Extension manifest
src/api/extension_endpoints.py                 # New: Extension-specific API (~600 lines)
deploy/cloudformation/api-gateway-extension.yaml # New: Extension API
```

#### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Extension installations | 500+ in 6 months | VS Code Marketplace |
| Daily active users | 100+ | API Gateway metrics |
| Scan-to-fix time | <5 minutes | End-to-end tracking |

#### Dependencies

- API Gateway deployment (partial - internal only)
- Cognito user pool (not started)
- WebSocket support for real-time updates (not started)

---

### Phase 5: TypeScript SDK (Q2 2026)

**Effort:** 2-3 sprints
**Owner:** Developer Experience Team
**Priority:** Medium

#### Objective

Generate and publish a TypeScript SDK for frontend developers and Node.js integration.

#### Implementation Tasks

**Sprint 1: SDK Generation**
- [ ] Generate SDK from OpenAPI spec using `openapi-typescript-codegen`
- [ ] Add TypeScript type definitions for all API responses
- [ ] Implement authentication helpers (JWT, API key)
- [ ] Create error handling utilities

**Sprint 2: React Integration**
- [ ] Build React hooks for common operations (`useApprovals`, `useVulnerabilities`)
- [ ] Add HITL dashboard integration components
- [ ] Create Storybook documentation
- [ ] Write unit tests with Jest

**Sprint 3: Publishing**
- [ ] Configure npm package (`@aenealabs/aura-sdk`)
- [ ] Set up automated publishing via GitHub Actions
- [ ] Create TypeDoc documentation
- [ ] Write getting started guide

#### File Changes

```
sdk/typescript/                                # New: SDK root
sdk/typescript/src/client.ts                   # API client
sdk/typescript/src/hooks/                      # React hooks
sdk/typescript/src/types/                      # Type definitions
sdk/typescript/package.json                    # npm package
.github/workflows/publish-sdk.yml              # Automated publishing
```

#### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| npm downloads | 1000+/month | npm stats |
| Type coverage | 100% | TypeScript compiler |
| Documentation completeness | 100% | TypeDoc output |

---

### Phase 6: A2A Protocol Support (Q2-Q3 2026)

**Effort:** 4-6 sprints
**Owner:** Platform Team
**Priority:** Medium

#### Objective

Implement Agent-to-Agent (A2A) protocol for cross-platform agent interoperability with Microsoft Foundry, LangGraph, and other platforms.

#### AWS Service Mapping

| Component | AWS Service | Purpose |
|-----------|-------------|---------|
| A2A Gateway | API Gateway | Protocol endpoint |
| Agent Registry | DynamoDB | Registered external agents |
| Message Queue | SQS | Async agent communication |
| Event Bus | EventBridge | Cross-agent event routing |

#### Implementation Tasks

**Sprint 1-2: Protocol Implementation**
- [ ] Implement A2A protocol specification (JSON-RPC based)
- [ ] Create agent capability advertisement
- [ ] Build agent discovery mechanism
- [ ] Implement secure agent-to-agent authentication

**Sprint 3-4: Aura Agent Exposure**
- [ ] Expose Coder, Reviewer, Validator as A2A endpoints
- [ ] Create capability manifests for each agent
- [ ] Implement request/response serialization
- [ ] Add rate limiting and quota management

**Sprint 5-6: External Agent Integration**
- [ ] Build connector for Microsoft Foundry agents
- [ ] Create LangGraph agent bridge
- [ ] Implement mixed-platform workflow orchestration
- [ ] Write integration tests with external agents

#### A2A Capability Manifest Example

```json
{
  "agent_id": "aura-coder-agent",
  "protocol_version": "1.0",
  "capabilities": [
    {
      "name": "generate_patch",
      "description": "Generate security patch for vulnerability",
      "input_schema": {"type": "object", "properties": {...}},
      "output_schema": {"type": "object", "properties": {...}}
    }
  ],
  "endpoint": "https://api.aenealabs.com/a2a/coder",
  "authentication": "oauth2"
}
```

#### File Changes

```
src/services/a2a_gateway.py                    # New: Protocol implementation (~800 lines)
src/services/a2a_agent_registry.py             # New: Agent discovery (~400 lines)
src/api/a2a_endpoints.py                       # New: A2A API routes (~500 lines)
deploy/cloudformation/a2a-infrastructure.yaml   # New: SQS, EventBridge
```

#### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| External agent integrations | 3+ platforms | Registry count |
| Cross-platform workflow success | >95% | End-to-end tests |
| A2A latency | <500ms (p95) | API Gateway metrics |

#### Dependencies

- A2A protocol specification finalization (in progress by Microsoft)
- OAuth2 implementation for agent authentication

---

### Phase 7: Red-Teaming Automation (Q2 2026)

**Effort:** 2-3 sprints
**Owner:** Security Team
**Priority:** Medium

#### Objective

Add automated adversarial testing for AI-generated patches and LLM outputs.

#### AWS Service Mapping

| Component | AWS Service | Purpose |
|-----------|-------------|---------|
| Red-Team Agent | ECS Fargate | Isolated adversarial testing |
| Attack Templates | S3 | Adversarial input library |
| Results Storage | DynamoDB | Test results, findings |
| CI/CD Gate | CodePipeline | Block deployments on failures |

#### Implementation Tasks

**Sprint 1: Red-Team Agent Core**
- [ ] Create `src/agents/red_team_agent.py` with adversarial testing logic
- [ ] Implement prompt injection testing for LLM outputs
- [ ] Build input fuzzing for patched code
- [ ] Add OWASP testing patterns

**Sprint 2: CI/CD Integration**
- [ ] Create CodePipeline gate for red-team results
- [ ] Implement automated rollback on critical findings
- [ ] Add CloudWatch alarms for red-team failures
- [ ] Create Slack notifications for security findings

**Sprint 3: Continuous Testing**
- [ ] Deploy red-team agent as ECS Fargate service
- [ ] Schedule periodic adversarial testing
- [ ] Build dashboard for red-team results
- [ ] Document adversarial testing patterns

#### Red-Team Test Categories

| Category | Description | Examples |
|----------|-------------|----------|
| **Prompt Injection** | Test LLM output manipulation | `Ignore previous instructions...` |
| **Code Injection** | Test for malicious code in patches | SQL injection, command injection |
| **Sandbox Escape** | Test patch isolation | Network access, file system access |
| **Privilege Escalation** | Test authorization bypass | IDOR, mass assignment |

#### File Changes

```
src/agents/red_team_agent.py                   # New: Adversarial testing (~700 lines)
src/services/adversarial_input_service.py      # New: Attack patterns (~400 lines)
deploy/cloudformation/red-team.yaml            # New: ECS task, S3 bucket
.github/workflows/security-gate.yml            # Modified: Add red-team gate
```

#### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Test coverage | >80% of generated patches | Test execution logs |
| False positive rate | <5% | Manual review |
| CI/CD gate effectiveness | 100% critical blocks | Pipeline metrics |

---

### Phase 8: Connector Expansion (Q3 2026)

**Effort:** 1-2 sprints per connector
**Owner:** Integration Team
**Priority:** Medium

#### Objective

Expand enterprise integrations beyond current 5 connectors (Slack, Jira, PagerDuty, GitHub, Datadog).

#### Priority Connectors

| Connector | Use Case | Implementation Effort |
|-----------|----------|----------------------|
| **ServiceNow** | Incident management, ITSM | 1-2 sprints |
| **Splunk** | Security event correlation | 1-2 sprints |
| **Azure DevOps** | CI/CD for Microsoft shops | 1 sprint |
| **Terraform Cloud** | IaC integration | 1 sprint |
| **AWS Security Hub** | Centralized security findings | 1 sprint |

#### Implementation Pattern

Each connector follows the established pattern from ADR-023:

```python
# src/services/external_tool_connectors.py pattern
class ServiceNowConnector:
    @require_enterprise_mode
    async def create_incident(self, title: str, description: str, severity: str) -> str:
        # Implementation
        pass

    @require_enterprise_mode
    async def update_incident(self, incident_id: str, status: str) -> bool:
        # Implementation
        pass
```

#### File Changes

```
src/services/servicenow_connector.py           # New: ServiceNow integration (~400 lines)
src/services/splunk_connector.py               # New: Splunk integration (~350 lines)
src/services/azure_devops_connector.py         # New: Azure DevOps integration (~300 lines)
src/services/terraform_cloud_connector.py      # New: Terraform integration (~250 lines)
src/services/security_hub_connector.py         # New: Security Hub integration (~300 lines)
```

#### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Connector count | 10+ | Registry count |
| Integration success rate | >99% | Error logs |
| Customer adoption | 50%+ using 3+ connectors | Usage analytics |

---

## Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| OTel performance overhead | Medium | Medium | Sampling, async export |
| Model router accuracy | Medium | Low | A/B testing, fallback to Sonnet |
| VS Code extension complexity | High | Medium | Phased rollout, beta testing |
| A2A protocol changes | Medium | Medium | Abstraction layer, version negotiation |

### Schedule Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| GovCloud migration priority conflict | Medium | High | Separate teams, clear ownership |
| Resource constraints | Medium | Medium | Prioritize high-impact items |
| External dependency delays (A2A spec) | Medium | Low | Monitor spec development |

### Security Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| OTel data exposure | Low | High | Sampling sensitive spans, encryption |
| VS Code extension vulnerabilities | Medium | Medium | Security audit, SAST scanning |
| A2A authentication bypass | Low | High | OAuth2, mTLS, rate limiting |

---

## Alternatives Considered

### Alternative 1: AWS-Only Observability

Continue using CloudWatch exclusively without OTel.

**Rejected:** Enterprise customers expect OTel compatibility for multi-cloud and vendor-neutral tooling.

### Alternative 2: Build Custom Agent Protocol

Create proprietary agent interoperability protocol instead of A2A.

**Rejected:** A2A is emerging as the industry standard; proprietary protocols fragment the ecosystem.

### Alternative 3: JetBrains Plugin Instead of VS Code

Build for IntelliJ/PyCharm instead of VS Code.

**Rejected:** VS Code has 70%+ market share among developers; JetBrains plugin can follow later.

---

## Consequences

### Positive

1. **Enterprise Readiness** - OTel and connectors improve enterprise integration capabilities
2. **Developer Experience** - VS Code extension and TypeScript SDK lower adoption friction
3. **Cost Optimization** - Model router reduces LLM costs by 30-50%
4. **Ecosystem Play** - A2A protocol enables partnerships with Azure/Microsoft shops
5. **Retrieval Quality** - Agentic retrieval improves complex query handling

### Negative

1. **Implementation Effort** - 18-26 sprints total across all phases
2. **Maintenance Burden** - Each new capability requires ongoing support
3. **Complexity Increase** - More moving parts to monitor and debug

### Mitigation

- Phased rollout reduces risk of each capability
- Feature flags allow disabling problematic features
- Clear ownership per capability area
- Automated testing gates prevent regressions

---

## Implementation Timeline

```
                    2026
        Q1                  Q2                  Q3
    ┌─────────────────┬─────────────────┬─────────────────┐
    │                 │                 │                 │
    │  OpenTelemetry  │  VS Code Ext    │  A2A Protocol   │
    │  (2-3 sprints)  │  (4-6 sprints)  │  (4-6 sprints)  │
    │                 │                 │                 │
    │  Model Router   │  TypeScript SDK │  Connectors     │
    │  (1-2 sprints)  │  (2-3 sprints)  │  (5-10 sprints) │
    │                 │                 │                 │
    │  Agentic        │  Red-Team       │                 │
    │  Retrieval      │  Automation     │                 │
    │  (2-3 sprints)  │  (2-3 sprints)  │                 │
    │                 │                 │                 │
    └─────────────────┴─────────────────┴─────────────────┘

    High Priority      Medium Priority   Medium Priority
```

---

## Success Criteria

| Phase | Capability | Success Criteria | Target Date |
|-------|------------|------------------|-------------|
| 1 | OpenTelemetry | >95% trace coverage, X-Ray integration | Mar 2026 |
| 2 | Model Router | 30%+ cost reduction, no quality regression | Mar 2026 |
| 3 | Agentic Retrieval | +25% relevance improvement | Mar 2026 |
| 4 | VS Code Extension | 500+ installations, <5min scan-to-fix | Jun 2026 |
| 5 | TypeScript SDK | 1000+ monthly npm downloads | Jun 2026 |
| 6 | A2A Protocol | 3+ external agent integrations | Sep 2026 |
| 7 | Red-Team Automation | 80%+ patch coverage, CI/CD gate active | Jun 2026 |
| 8 | Connectors | 10+ connectors, 50% customer adoption | Sep 2026 |

---

## References

- [Microsoft Foundry Comparative Analysis](/path/to/project-aura/research/MICROSOFT_FOUNDRY_COMPARATIVE_ANALYSIS.md)
- [OpenTelemetry Semantic Conventions for GenAI](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [A2A Protocol Specification](https://github.com/google/a2a) (Google open-source implementation)
- [VS Code Extension API](https://code.visualstudio.com/api)
- ADR-022: GitOps for Kubernetes Deployment
- ADR-023: AgentCore Gateway Integration
- ADR-025: RuntimeIncidentAgent Architecture
