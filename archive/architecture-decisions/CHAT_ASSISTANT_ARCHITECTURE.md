# Project Aura Chat Assistant - Architecture Design

**Version:** 1.0
**Created:** December 8, 2025
**Architect:** Infrastructure Team
**Status:** Design Complete - Ready for Implementation

---

## Executive Summary

This document presents the architecture for Project Aura's built-in chat assistant ("Aura Assistant"). The design uses AWS Lambda for serverless compute, Bedrock Claude 3.5 Sonnet for LLM processing, DynamoDB for chat history, OpenSearch for documentation retrieval, and ElastiCache for caching. The architecture maintains CMMC Level 2/3 compliance trajectory and full GovCloud compatibility.

**Key Decisions:**
- **Compute:** Lambda-based (cost-effective, auto-scaling)
- **LLM:** Bedrock Claude 3.5 Sonnet with tool use
- **Storage:** DynamoDB with tenant isolation
- **Caching:** ElastiCache Redis (60s for metrics, 24h for embeddings)
- **Cost:** ~$792/month for 100 users (~$550 optimized)

---

## Architecture Overview

See the complete architecture document in the agent output above for:
- Component diagrams
- Data flow diagrams
- Service selection rationale
- DynamoDB schema design
- Lambda implementation patterns
- Tool definitions (8 tools for metrics, docs, reports)
- Security and compliance implementation
- Cost estimates and optimization strategies
- 10-week implementation phases
- GovCloud compatibility verification

---

## Quick Reference

### AWS Services Used

| Service | Purpose | Config |
|---------|---------|--------|
| Lambda | Chat orchestration | 512MB-1GB, 30-120s timeout |
| API Gateway | REST + WebSocket APIs | Regional, Cognito auth |
| Bedrock | Claude 3.5 Sonnet + Titan Embeddings | us-east-1 / us-gov-west-1 |
| DynamoDB | Chat conversations and messages | PAY_PER_REQUEST, encrypted |
| ElastiCache | Redis caching | cache.t3.micro → r6g.large |
| OpenSearch | Documentation search | Shared with GraphRAG |
| CloudWatch | Logs and metrics | 90-day retention |
| Cognito | JWT authentication | Existing user pool |

### Chat Tools (LLM Function Calling)

1. `get_vulnerability_metrics` - Query vulnerability stats
2. `get_agent_status` - Agent health and activity
3. `get_approval_queue` - Pending HITL approvals
4. `search_documentation` - Search docs/ADRs/guides
5. `get_incident_details` - Incident investigation data
6. `generate_report` - Ad-hoc summary reports
7. `query_code_graph` - GraphRAG code queries
8. `get_sandbox_status` - Sandbox environment status

### Cost Optimization Strategies

- **Model Routing:** Use Haiku for simple queries (10x cheaper)
- **Embedding Caching:** 24h TTL in Redis (50%+ savings)
- **Response Caching:** 60s for metrics (20-30% savings)
- **Context Summarization:** Reduce token usage for long threads

### Implementation Phases

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| 1. Foundation | 2 weeks | DynamoDB tables, basic Lambda, REST API |
| 2. Tool Integration | 2 weeks | 8 tools implemented, metrics queries |
| 3. Streaming | 2 weeks | WebSocket API, streaming responses |
| 4. Caching | 1 week | ElastiCache, performance tuning |
| 5. Security | 1 week | Audit logging, row-level security |
| 6. Production | 2 weeks | CloudFormation, CI/CD, deployment |

**Total:** 10 weeks

---

## Next Steps

1. Create ADR for chat assistant approval
2. Deploy DynamoDB tables to dev environment
3. Implement Lambda functions (Phase 1)
4. Connect frontend UI to backend API
5. Load test with 100 concurrent users
6. Security review and penetration testing
7. Deploy to production

---

**See full architecture details in the architecture output above.**
