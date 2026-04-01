# Troubleshooting Guide

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This troubleshooting guide provides systematic approaches to diagnosing and resolving issues with Project Aura. The guide is organized by problem category to help you quickly find relevant solutions.

---

## Troubleshooting Philosophy

### Diagnostic Approach

When troubleshooting Project Aura issues, follow this systematic approach:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TROUBLESHOOTING WORKFLOW                          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  1. IDENTIFY THE SYMPTOM                                             │
│     - What is the error message?                                     │
│     - What operation was being performed?                            │
│     - When did the problem start?                                    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. GATHER DIAGNOSTIC DATA                                           │
│     - Collect relevant logs                                          │
│     - Check service health endpoints                                 │
│     - Review recent changes                                          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. ISOLATE THE COMPONENT                                            │
│     - Which layer is affected?                                       │
│     - Is it reproducible?                                            │
│     - Are other users affected?                                      │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. APPLY THE FIX                                                    │
│     - Follow documented resolution                                   │
│     - Verify the fix worked                                          │
│     - Document if new issue                                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Log Levels Reference

| Level | Description | When to Use |
|-------|-------------|-------------|
| DEBUG | Detailed diagnostic information | Development, deep troubleshooting |
| INFO | General operational information | Normal operations monitoring |
| WARNING | Unexpected but handled conditions | Proactive issue detection |
| ERROR | Error conditions requiring attention | Active troubleshooting |
| CRITICAL | System-level failures | Immediate action required |

---

## Quick Diagnostic Commands

### Platform Health Check

```bash
# SaaS deployment - Check API health
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/health | jq

# Expected response
{
  "status": "healthy",
  "version": "1.6.0",
  "components": {
    "api": "healthy",
    "agents": "healthy",
    "neptune": "healthy",
    "opensearch": "healthy",
    "bedrock": "healthy"
  },
  "timestamp": "2026-01-19T12:00:00Z"
}
```

### Self-Hosted Kubernetes Health

```bash
# Check all Aura pods
kubectl get pods -n aura-system -o wide

# Check for pods not in Running state
kubectl get pods -n aura-system --field-selector=status.phase!=Running

# Check recent events
kubectl get events -n aura-system --sort-by='.lastTimestamp' | tail -20

# Check node health
kubectl describe nodes | grep -A5 "Conditions:"
```

### Service Connectivity Tests

```bash
# Test Neptune connectivity
aws neptune-db describe-db-cluster-endpoints \
  --db-cluster-identifier aura-neptune-cluster-${ENV} \
  --query 'DBClusterEndpoints[*].Endpoint'

# Test OpenSearch connectivity
curl -s -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/_cluster/health" | jq

# Test Bedrock connectivity
aws bedrock-runtime invoke-model \
  --model-id anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":10,"messages":[{"role":"user","content":"test"}]}' \
  --output text --query 'body' | base64 -d | jq
```

---

## Troubleshooting Categories

### [Common Issues](./common-issues.md)

Frequently encountered problems affecting daily operations:

- Authentication and login failures
- API request errors (400, 401, 403, 500)
- Agent timeout and communication issues
- Repository connection problems
- Notification delivery failures

**Start here** if you are experiencing a general problem or are unsure of the cause.

---

### [Deployment Issues](./deployment-issues.md)

Infrastructure and deployment problems:

- CloudFormation stack failures
- EKS cluster and node issues
- Container image pull errors
- Kubernetes manifest problems
- CI/CD pipeline failures

**Use this guide** when deployments fail or infrastructure is unhealthy.

---

### [Performance Issues](./performance-issues.md)

Latency, throughput, and resource problems:

- Slow API response times
- Agent processing delays
- Database query performance
- Memory and CPU exhaustion
- Network latency issues

**Use this guide** when the system is slow or unresponsive.

---

### [Security Issues](./security-issues.md)

Security-related problems and access control:

- Authentication failures (SSO, MFA)
- Authorization and RBAC problems
- Certificate and TLS errors
- Secrets management issues
- IAM permission errors

**Use this guide** for access denied errors or security-related problems.

---

## System Component Reference

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   Web UI    │  │  REST API   │  │  GraphQL    │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                          AGENT LAYER                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
│  │Orchestrator │  │   Coder     │  │  Reviewer   │  │ Validator │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                       INTELLIGENCE LAYER                             │
│  ┌─────────────────────┐  ┌─────────────────────┐                   │
│  │  Context Retrieval  │  │   Bedrock LLM       │                   │
│  └─────────────────────┘  └─────────────────────┘                   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                          DATA LAYER                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
│  │   Neptune   │  │ OpenSearch  │  │  DynamoDB   │  │    S3     │  │
│  │   (Graph)   │  │  (Vector)   │  │   (State)   │  │  (Files)  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Service Dependencies

| Service | Depends On | Called By |
|---------|------------|-----------|
| API Gateway | IAM, WAF | External clients |
| Orchestrator | Neptune, OpenSearch, Bedrock | API Gateway |
| Coder Agent | Bedrock, Context Retrieval | Orchestrator |
| Reviewer Agent | Bedrock, Context Retrieval | Orchestrator |
| Validator Agent | Sandbox Service, Neptune | Orchestrator |
| Context Retrieval | Neptune, OpenSearch | All Agents |
| Sandbox Service | ECS Fargate, VPC | Validator Agent |
| HITL Service | DynamoDB, SNS, SES | Orchestrator |

### Port Reference

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| API Gateway | 443 | HTTPS | External API endpoint |
| Orchestrator | 8080 | HTTP | Internal agent coordination |
| Neptune | 8182 | WSS/HTTPS | Graph database |
| OpenSearch | 9200 | HTTPS | Vector search |
| dnsmasq | 53 | UDP/TCP | Internal DNS |
| Prometheus | 9090 | HTTP | Metrics collection |
| Grafana | 3000 | HTTP | Dashboards |

---

## Log Collection Reference

### CloudWatch Log Groups

| Log Group | Content | Retention |
|-----------|---------|-----------|
| /aura/api | API request/response logs | 90 days |
| /aura/agents/orchestrator | Agent coordination logs | 90 days |
| /aura/agents/coder | Patch generation logs | 90 days |
| /aura/agents/reviewer | Code review logs | 90 days |
| /aura/agents/validator | Sandbox test logs | 90 days |
| /aura/security/audit | Security audit events | 365 days |
| /aura/infrastructure | CloudFormation, EKS events | 90 days |

### Log Query Examples

```bash
# Find all errors in the last hour (CloudWatch Insights)
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 100

# Find specific error code
fields @timestamp, @message, error_code
| filter error_code = "AURA-AUTH-001"
| sort @timestamp desc

# Agent performance metrics
fields @timestamp, agent_name, execution_time_ms
| filter agent_name = "coder"
| stats avg(execution_time_ms), max(execution_time_ms), count(*) by bin(5m)
```

---

## Escalation Procedures

### When to Escalate

| Condition | Escalation Path |
|-----------|-----------------|
| System-wide outage | P1 - Critical (immediate) |
| Data loss or corruption | P1 - Critical (immediate) |
| Security breach suspected | P1 - Critical + Security Team |
| Single service failure (production) | P2 - High (4 hours) |
| Performance degradation >50% | P2 - High (4 hours) |
| Single service failure (non-prod) | P3 - Medium (1 business day) |
| Documentation or configuration issue | P4 - Low (3 business days) |

### Escalation Checklist

Before escalating, gather the following information:

- [ ] Error message and error code
- [ ] Timestamp when issue started
- [ ] Steps to reproduce
- [ ] Affected users/systems
- [ ] Recent changes (deployments, configuration)
- [ ] Log snippets showing the error
- [ ] Screenshots (if applicable)
- [ ] What troubleshooting steps have been tried

---

## Related Documentation

- [Support Documentation Index](../index.md)
- [Operations Guide](../operations/index.md)
- [Architecture Overview](../architecture/index.md)
- [API Reference](../api-reference/index.md)
- [FAQ](../faq.md)

---

*Last updated: January 2026 | Version 1.0*
