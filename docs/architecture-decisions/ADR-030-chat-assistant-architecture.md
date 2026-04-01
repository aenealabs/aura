# ADR-030: Chat Assistant Architecture - AI-Powered Platform Support

**Status:** Deployed
**Date:** 2025-12-08
**Deployed:** 2025-12-10
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-015 (Tiered LLM Strategy), ADR-024 (Titan Neural Memory), ADR-029 (Agent Optimization Roadmap)

---

## Executive Summary

This ADR defines the architecture for Aura Assistant, a built-in AI chat interface that provides 24/7 support to platform users. The system uses AWS Lambda for serverless compute, Bedrock Claude 3.5 Sonnet for conversational AI, DynamoDB for chat history, and ElastiCache for caching. Each user maintains isolated conversation history with access to platform metrics, documentation, and ad-hoc report generation through LLM tool use.

**Key Outcomes:**
- 24/7 AI-powered platform support without human intervention
- ~$550/month operating cost for 100 users (30% savings through optimization)
- Sub-3 second response times for typical queries
- Complete tenant isolation and CMMC compliance
- GovCloud compatible architecture
- 8 specialized tools for platform queries (metrics, docs, reports, incidents)

**Cost:** ~$792/month baseline (100 users), ~$550/month optimized
**Timeline:** 10 weeks phased implementation

---

## Context

### Current State

Project Aura provides comprehensive UI dashboards for:
- Vulnerability management and HITL approval workflows
- Agent orchestration and health monitoring
- Incident investigations and red team testing
- GraphRAG code exploration
- Integration hub and settings

**Limitations:**
- Users must navigate multiple pages to find information
- No contextual help for platform features
- Ad-hoc reporting requires dashboard exports
- Documentation search is manual
- No 24/7 support for configuration questions

### User Needs

| User Type | Primary Needs |
|-----------|---------------|
| **Security Engineers** | Quick vulnerability status checks, approval queue insights, incident summaries |
| **Operators** | Agent health monitoring, sandbox status, configuration help |
| **Analysts** | Ad-hoc report generation, trend analysis, documentation search |
| **Executives** | High-level summaries, compliance status, cost metrics |

---

## Decision

Implement Aura Assistant as a **floating chat interface** with **Lambda-based serverless backend** providing conversational access to platform data, metrics, and documentation.

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                    AURA ASSISTANT ARCHITECTURE                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────┐     ┌────────────────────────────────────────────┐  │
│  │  Frontend   │     │           Backend Services                  │  │
│  │  (React)    │     │                                            │  │
│  │             │     │  ┌──────────────┐   ┌──────────────────┐   │  │
│  │ ┌─────────┐ │────▶│  │  API Gateway │──▶│  Lambda: Chat    │   │  │
│  │ │  Chat   │ │     │  │  REST + WS   │   │  Orchestrator    │   │  │
│  │ │  Panel  │ │     │  └──────────────┘   └────────┬─────────┘   │  │
│  │ └─────────┘ │     │                              │             │  │
│  │             │     │                    ┌─────────▼─────────┐   │  │
│  │ [Olive btn] │     │                    │   Bedrock Claude  │   │  │
│  └─────────────┘     │                    │   3.5 Sonnet      │   │  │
│                      │                    └─────────┬─────────┘   │  │
│                      │                              │             │  │
│                      │                    ┌─────────▼─────────┐   │  │
│                      │                    │   8 Chat Tools:   │   │  │
│                      │                    │  - Metrics        │   │  │
│                      │                    │  - Docs Search    │   │  │
│                      │                    │  - Reports        │   │  │
│                      │                    │  - GraphRAG       │   │  │
│                      │                    └───────────────────┘   │  │
│                      └────────────────────────────────────────────┘  │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                   Data & Caching Layer                          │  │
│  │  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌─────────────┐  │  │
│  │  │DynamoDB  │  │ElastiCache│  │OpenSearch │  │ CloudWatch  │  │  │
│  │  │ Chat     │  │  Redis    │  │ Doc Index │  │  Metrics    │  │  │
│  │  │ History  │  │  Cache    │  │           │  │             │  │  │
│  │  └──────────┘  └───────────┘  └───────────┘  └─────────────┘  │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Choice | Alternatives Considered | Rationale |
|----------|--------|------------------------|-----------|
| **Compute** | AWS Lambda | ECS Fargate, EKS pods | Cost-effective ($15/month vs $50+), auto-scaling, GovCloud compatible |
| **LLM Provider** | Bedrock Claude 3.5 Sonnet | OpenAI API, self-hosted | GovCloud FedRAMP High approved, existing integration, best tool use |
| **Streaming** | API Gateway WebSocket | Server-Sent Events (SSE) | Bi-directional, native AWS support, proven pattern |
| **Chat Storage** | DynamoDB | RDS Postgres, S3 | Serverless, auto-scaling, tenant isolation via PK, KMS encryption |
| **Caching** | ElastiCache Redis | DynamoDB DAX | Flexible TTL, embedding cache, proven performance |
| **Doc Search** | OpenSearch (existing) | New Pinecone index | Reuse existing infrastructure, hybrid search capability |
| **UI Pattern** | Floating button + slide-in panel | Dedicated /chat page, sidebar | Non-disruptive, persistent across pages, familiar UX |

---

## Rationale

### Why Lambda Over ECS/EKS

**Cost Comparison (100 users, 60K requests/month):**
- Lambda: $15/month (billed per request)
- ECS Fargate (1 task, 512MB): $50/month (always running)
- EKS pod (t3.medium share): $35/month (node costs)

**Scalability:**
- Lambda: Auto-scales 0→1000 concurrent
- ECS/EKS: Requires manual scaling configuration

**GovCloud:** Lambda has full feature parity, no restrictions

### Why Bedrock Claude Over OpenAI

| Factor | Bedrock | OpenAI |
|--------|---------|--------|
| **GovCloud** | ✅ Available (us-gov-west-1) | ❌ Not available |
| **Compliance** | FedRAMP High authorized | Not FedRAMP authorized |
| **Tool Use** | Native function calling | Function calling available |
| **Cost (1M tokens)** | $3 input / $15 output | $2.50 input / $10 output |
| **Integration** | Already integrated (ADR-015) | New integration needed |
| **CMMC** | Supports compliance | External API (risk) |

### Why WebSocket Over SSE

| Factor | WebSocket | SSE |
|--------|-----------|-----|
| **Bi-directional** | ✅ Full duplex | ❌ Server → Client only |
| **AWS Support** | ✅ API Gateway native | ⚠️ Requires custom headers |
| **Connection Pooling** | ✅ Built-in | ⚠️ Limited |
| **Latency** | ~50ms | ~100ms |
| **Reconnection** | Built-in | Manual handling |

---

## Architecture Details

### DynamoDB Schema

**Table: `aura-chat-conversations-{env}`**

| Attribute | Type | Description |
|-----------|------|-------------|
| PK | String | `USER#{user_id}` |
| SK | String | `CONV#{conversation_id}` |
| conversation_id | String | UUID |
| user_id | String | Cognito sub |
| tenant_id | String | Tenant isolation |
| title | String | Auto-generated or user-edited |
| created_at | String | ISO timestamp |
| updated_at | String | ISO timestamp |
| message_count | Number | Total messages |
| total_tokens | Number | Cumulative usage |
| status | String | `active`, `archived` |
| TTL | Number | Auto-deletion (7/30/90 days) |

**GSI:** `user-conversations-index` (user_id + updated_at) - List user's conversations by recency

**Table: `aura-chat-messages-{env}`**

| Attribute | Type | Description |
|-----------|------|-------------|
| PK | String | `CONV#{conversation_id}` |
| SK | String | `MSG#{timestamp}#{message_id}` |
| message_id | String | UUID |
| role | String | `user`, `assistant` |
| content | String | Message text (max 10KB) |
| tool_calls | List | Tool invocations |
| tokens_input | Number | Input tokens |
| tokens_output | Number | Output tokens |
| model_id | String | Model used |
| latency_ms | Number | Response time |
| created_at | String | ISO timestamp |
| TTL | Number | Auto-deletion |

**GSI:** `tenant-messages-index` (tenant_id + created_at) - Audit queries

### LLM Tool Definitions (8 Tools)

1. **get_vulnerability_metrics** - Query vulnerability stats (severity, status, time range)
2. **get_agent_status** - Agent health and recent activity
3. **get_approval_queue** - Pending HITL approvals (type, priority)
4. **search_documentation** - Hybrid search docs/ADRs/guides
5. **get_incident_details** - Incident investigation data
6. **generate_report** - Ad-hoc summaries (vuln, agent, patch, incident, daily digest)
7. **query_code_graph** - GraphRAG code relationship queries
8. **get_sandbox_status** - Sandbox environment status

### Caching Strategy

| Cache Type | TTL | Purpose |
|------------|-----|---------|
| Metrics | 60s | Real-time vulnerability/agent data |
| Documentation | 1h | Doc search results |
| Embeddings | 24h | Text embedding vectors |
| Conversation Context | 5min | Recent message history |

**Cache Hit Rate Target:** > 60%

### Rate Limiting

| Tier | Requests/Minute | Tokens/Day | Cost/Month |
|------|----------------|------------|------------|
| Free | 10 | 50,000 | Included |
| Standard | 30 | 200,000 | Base tier |
| Enterprise | 100 | 1,000,000 | Custom pricing |

---

## Consequences

### Positive

✅ **User Experience:**
- Instant answers to platform questions (< 3s typical)
- Reduces support ticket volume by 40-60%
- Context-aware suggestions based on current page
- Reduces time to find information by 80%

✅ **Cost Efficiency:**
- $550/month for 100 users (optimized with caching + model routing)
- No dedicated support staff needed for common questions
- Reduces documentation search time (saves developer hours)

✅ **Scalability:**
- Lambda auto-scales 0 → 1000 concurrent executions
- Serverless = no capacity planning required
- ElastiCache provides consistent performance at scale

✅ **Compliance:**
- Full audit logging (CMMC, SOX requirements)
- Tenant isolation (row-level security)
- KMS encryption at rest
- GovCloud deployment path clear

✅ **Developer Experience:**
- Reuses existing Bedrock integration (ADR-015)
- Reuses OpenSearch for doc search (existing GraphRAG)
- FastAPI backend pattern consistent with existing APIs

### Negative

⚠️ **Complexity:**
- Adds 3 new DynamoDB tables, 3 Lambda functions, 1 ElastiCache cluster
- Requires WebSocket API Gateway (new deployment artifact)
- Increases operational monitoring surface

⚠️ **Cost Variability:**
- LLM token costs fluctuate with user activity
- Must set strict rate limits to prevent overages
- Need cost anomaly detection (CloudWatch alarms)

⚠️ **Latency Dependencies:**
- Chat quality depends on Bedrock latency (typically 1-3s)
- Tool execution adds 200-500ms per tool call
- Network latency for WebSocket connections

⚠️ **Security Surface:**
- New attack vector (prompt injection, jailbreaking)
- Must sanitize all LLM inputs/outputs
- Tool use abuse potential (excessive metric queries)

### Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **LLM cost overrun** | Medium | High | Strict rate limits, model routing, token budgets |
| **Prompt injection** | Medium | Medium | Input sanitization, Bedrock Guardrails, A2AS framework |
| **Data leakage** | Low | Critical | Row-level security, tenant isolation testing |
| **WebSocket stability** | Low | Medium | Connection health checks, auto-reconnect |
| **Cold start latency** | Medium | Low | Provisioned concurrency (10 instances) for prod |

---

## Implementation Plan

### Phase 1: Foundation (Weeks 1-2)

**Deliverables:**
- DynamoDB tables (conversations, messages, connections)
- Lambda function skeleton (chat-handler)
- Basic REST API (`POST /chat/message`, `GET /conversations`)
- Bedrock Claude integration (non-streaming)
- Cognito JWT authentication

**Success Criteria:**
- User can send message and receive response
- Conversation history persists in DynamoDB
- Authentication via Cognito works

**Cost:** ~$50 (dev environment, low usage)

### Phase 2: Tool Integration (Weeks 3-4)

**Deliverables:**
- 8 tool definitions implemented
- MetricsQueryService (DynamoDB, CloudWatch)
- DocumentationSearchService (OpenSearch hybrid search)
- Tool execution framework with error handling
- Integration tests for all tools

**Success Criteria:**
- Chat can query real vulnerability metrics
- Documentation search returns relevant results
- Tool errors handled gracefully (timeouts, retries)

**Cost:** Same as Phase 1 (incremental feature addition)

### Phase 3: Streaming & WebSocket (Weeks 5-6)

**Deliverables:**
- WebSocket API Gateway deployment
- Lambda handlers (ws-connect, ws-disconnect, ws-message)
- Streaming response implementation
- Frontend WebSocket client integration
- Connection management (DynamoDB connections table)

**Success Criteria:**
- Responses stream in real-time (< 500ms first token)
- WebSocket connections stable (1h+ session duration)
- Frontend displays streaming tokens smoothly

**Cost:** +$5/month (WebSocket API charges)

### Phase 4: Caching & Performance (Week 7)

**Deliverables:**
- ElastiCache Redis cluster (cache.t3.micro)
- Caching layer (metrics, embeddings, context)
- Rate limiting (per-user, per-tenant)
- Performance monitoring (CloudWatch dashboard)
- Load testing (100 concurrent users)

**Success Criteria:**
- P99 latency < 5s
- Cache hit rate > 60%
- Rate limiting functional (10/30/100 RPM by tier)

**Cost:** +$12/month (ElastiCache)

### Phase 5: Security & Compliance (Week 8)

**Deliverables:**
- Comprehensive audit logging (all chat interactions)
- Row-level security verification
- PII redaction in CloudWatch logs
- Prompt injection testing (A2AS framework)
- CMMC compliance documentation update

**Success Criteria:**
- All queries tenant-isolated (verified)
- Audit logs capture all interactions with timestamps
- No PII in logs (email, names redacted)
- Security review passed

**Cost:** No additional cost (configuration only)

### Phase 6: Production Readiness (Weeks 9-10)

**Deliverables:**
- CloudFormation templates (DynamoDB, Lambda, API Gateway, ElastiCache)
- CodeBuild CI/CD pipeline
- Operational runbooks (troubleshooting, scaling)
- User documentation (chat features, example queries)
- Production deployment to dev environment

**Success Criteria:**
- Full IaC deployment via CodeBuild
- Monitoring and alerting active (5 CloudWatch alarms)
- Documentation complete
- User acceptance testing passed

**Cost:** Full operational cost (~$550/month optimized)

---

## Alternatives Considered

### Alternative 1: Dedicated /chat Page

**Pros:**
- Simpler implementation (no floating button, no slide-in panel)
- Full-screen space for chat interface
- Easier to implement rich features (graph viz, reports)

**Cons:**
- User must navigate away from current work
- Loses context of current page
- Not persistent across navigation

**Rejected:** Poor UX for contextual help. Users want to ask questions without leaving their current task.

---

### Alternative 2: ECS Fargate for Chat Backend

**Pros:**
- Long-running WebSocket connections (no Lambda timeout)
- More control over runtime environment
- Easier debugging (logs, exec into container)

**Cons:**
- Higher cost ($50/month minimum vs $15/month Lambda)
- Manual scaling configuration required
- Cold start equivalent (ECS task start time)
- More complex deployment (container registry, task definitions)

**Rejected:** Lambda provides better cost/performance ratio at current scale (< 1000 users). Re-evaluate at 10K+ users.

---

### Alternative 3: OpenAI API (GPT-4)

**Pros:**
- Slightly lower cost ($2.50/$10 vs $3/$15 per 1M tokens)
- Faster response times (~1s vs 1-3s)
- More advanced reasoning for complex queries

**Cons:**
- ❌ Not GovCloud compatible (external SaaS)
- ❌ Not FedRAMP authorized (CMMC blocker)
- ❌ Requires new integration (Bedrock already integrated)
- ❌ PII sent to third-party (compliance risk)
- ❌ No tool use in us-gov region

**Rejected:** GovCloud migration is a critical requirement. OpenAI API is not available in GovCloud.

---

### Alternative 4: Fine-Tuned Model for Platform Knowledge

**Pros:**
- Better accuracy on platform-specific questions
- No documentation retrieval needed (knowledge baked in)
- Potentially faster responses (no tool calls)

**Cons:**
- High upfront cost ($10K-50K for fine-tuning)
- Stale knowledge (must re-train for updates)
- Still needs tools for real-time metrics
- Bedrock fine-tuning limited (not all models)

**Rejected:** RAG with tool use is more flexible and cost-effective. Fine-tuning considered for v2 if needed.

---

## Cost Analysis

### Baseline Costs (100 Users, 60K Messages/Month)

| Service | Calculation | Monthly Cost |
|---------|-------------|--------------|
| Bedrock Claude Input | 90M tokens x $3/1M | $270 |
| Bedrock Claude Output | 30M tokens x $15/1M | $450 |
| Bedrock Titan Embeddings | 120K queries x $0.0001/1K | $12 |
| Lambda (chat-handler) | 60K x 1.5s x 512MB | $15 |
| API Gateway (REST) | 60K requests | $0.06 |
| API Gateway (WebSocket) | 60K connections x 5 msgs | $0.30 |
| DynamoDB | 2 tables, 1M RCU/WCU | $25 |
| ElastiCache | cache.t3.micro (1 node) | $12 |
| CloudWatch Logs | 10 GB | $5 |
| KMS | 1 key + requests | $3 |
| **Total Baseline** | | **$792** |

### Optimized Costs (With Strategies)

| Optimization | Savings | Cost After |
|--------------|---------|------------|
| Model Routing (Haiku for simple) | -$140 | $652 |
| Embedding Caching (50% hit rate) | -$6 | $646 |
| Response Caching (30% hit rate) | -$90 | $556 |
| Context Summarization | -$6 | **$550** |

**Optimized: ~$550/month (30% savings)**

### Scaling Costs

| Users | Messages/Month | Baseline | Optimized | Per User |
|-------|---------------|----------|-----------|----------|
| 100 | 60K | $792 | $550 | $5.50 |
| 500 | 300K | $3,960 | $2,750 | $5.50 |
| 1,000 | 600K | $7,920 | $5,500 | $5.50 |
| 5,000 | 3M | $39,600 | $27,500 | $5.50 |

**Cost scales linearly with usage** (serverless benefit).

---

## Security & Compliance

### Tenant Isolation

All queries filtered by `tenant_id`:
```python
filter_expression = "tenant_id = :tenant_id AND created_at > :cutoff"
```

**Verification:**
- Unit tests verify tenant filter applied
- Integration tests confirm no cross-tenant data leakage
- Penetration testing includes tenant isolation checks

### Audit Logging

All chat interactions logged to CloudWatch:
- Timestamp, user_id, tenant_id, roles
- Message length (not content, for PII protection)
- Tools invoked with parameters (redacted sensitive fields)
- Tokens used, latency, model_id
- Errors and exceptions

**Retention:** 90 days (CMMC requirement)

### Data Encryption

| Data Type | At Rest | In Transit |
|-----------|---------|------------|
| DynamoDB | KMS customer-managed key | TLS 1.2+ |
| ElastiCache | In-transit encryption | TLS 1.2+ |
| Lambda environment vars | KMS | N/A |
| API Gateway | N/A | TLS 1.2+ |

### GovCloud Readiness

| Service | GovCloud Availability | Notes |
|---------|---------------------|-------|
| Lambda | ✅ Full parity | All features available |
| API Gateway | ✅ Full parity | REST + WebSocket |
| Bedrock | ✅ us-gov-west-1 | Claude 3.5 Sonnet available |
| DynamoDB | ✅ Full parity | Global Tables supported |
| ElastiCache | ✅ Full parity | Redis 7.x |
| Cognito | ✅ Full parity | MFA supported |

**Compatibility:** 100% (all services available)

---

## Monitoring & Alerting

### CloudWatch Alarms

| Alarm | Metric | Threshold | Action |
|-------|--------|-----------|--------|
| **High Error Rate** | 5XXError / Count | > 5% | SNS → PagerDuty |
| **High Latency** | Lambda Duration P99 | > 8s | SNS → Slack |
| **Rate Limit Exceeded** | 429 Count | > 100/5min | SNS → Slack |
| **Low Cache Hit Rate** | CacheHits / (Hits + Misses) | < 50% | SNS → Email |
| **High Token Usage** | OutputTokens | > 10M/day | SNS → Cost alert |

### Key Metrics Dashboard

- Chat request volume (requests/minute)
- Response latency (P50, P99, P99.9)
- Bedrock token usage (input/output)
- Tool invocation counts (by tool name)
- Cache hit rate (by cache type)
- Error rate (by error type)
- WebSocket connection count (active)

---

## Performance Targets

| Metric | Target (P50) | Target (P99) | Alert Threshold |
|--------|--------------|--------------|-----------------|
| Response Latency | < 2s | < 5s | > 8s |
| First Token Latency | < 500ms | < 1s | > 2s |
| Tool Execution | < 500ms | < 2s | > 3s |
| API Gateway Latency | < 50ms | < 200ms | > 500ms |
| Lambda Cold Start | < 1s | < 3s | > 5s |
| Error Rate | < 0.1% | < 1% | > 2% |

---

## Integration Points

### With Existing Services

| Service | Integration | Purpose |
|---------|-------------|---------|
| **Agent Orchestrator** | REST API calls | Get agent status, trigger actions |
| **Context Retrieval Service** | GraphRAG queries | Code relationship queries via tool |
| **Monitoring Service** | CloudWatch API | Platform metrics, agent health |
| **HITL Workflow** | DynamoDB queries | Approval queue status |
| **Incident Service** | DynamoDB queries | Incident details and RCA |

### Frontend Integration

Chat is integrated as a **floating button + slide-in panel**:
- Persistent across all pages
- Context-aware (knows current page)
- Non-disruptive to user workflow
- Mobile responsive (full-screen on small devices)

---

## Acceptance Criteria

### Functional Requirements

- [ ] User can send message and receive AI response within 3s
- [ ] Conversation history persists across sessions
- [ ] All 8 tools functional and return accurate data
- [ ] Documentation search returns relevant results (> 80% accuracy)
- [ ] Reports generate correctly with proper formatting
- [ ] Streaming responses display smoothly in UI
- [ ] Rate limiting prevents abuse (429 status code)
- [ ] Dark mode works throughout chat interface

### Non-Functional Requirements

- [ ] P99 latency < 5s
- [ ] Cache hit rate > 60%
- [ ] Error rate < 1%
- [ ] 99.9% uptime (3 nines)
- [ ] Tenant isolation verified (no cross-tenant leakage)
- [ ] Audit logs capture all interactions
- [ ] Cost within budget ($600/month for 100 users)
- [ ] GovCloud deployment successful (when ready)

---

## Future Enhancements (Post-V1)

| Enhancement | Timeline | Benefit |
|-------------|----------|---------|
| **Voice Input** | Q2 2026 | Hands-free queries for operators |
| **Multi-Modal** | Q3 2026 | Upload screenshots, analyze charts |
| **Proactive Suggestions** | Q2 2026 | AI suggests actions based on anomalies |
| **Collaborative Chat** | Q3 2026 | Share conversations with team |
| **Custom Agent Creation** | Q4 2026 | Users define custom tools/workflows |
| **Fine-Tuned Model** | Q4 2026 | Better platform-specific responses |

---

## Related Documentation

- **Architecture Document:** `docs/CHAT_ASSISTANT_ARCHITECTURE.md`
- **UI Components:** `frontend/src/components/chat/README.md`
- **API Specification:** See the output (OpenAPI 3.0 schema)
- **Tool Definitions:** See Section 2.3 of architecture doc

---

## Approval

**Recommended for Implementation:** ✅ Yes

**Justification:**
- Clear business value (24/7 support, reduced ticket volume)
- Cost-effective at scale (~$5.50/user/month)
- GovCloud compatible (critical for CMMC)
- Leverages existing infrastructure (Bedrock, OpenSearch)
- Low risk (serverless, auto-scaling, isolated)

**Next Action:** Begin Phase 1 implementation (DynamoDB tables, Lambda skeleton)

---

**ADR Approved:** December 8, 2025
**Implementation Start:** Q1 2026
