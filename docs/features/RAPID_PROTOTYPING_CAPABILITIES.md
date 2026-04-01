# Aura Platform - Rapid Prototyping Capabilities

**Last Updated:** December 16, 2025
**Status:** Production Ready
**Related ADRs:** [ADR-032](../architecture-decisions/ADR-032-configurable-autonomy-framework.md), [ADR-039](../architecture-decisions/ADR-039-self-service-test-environments.md), [ADR-004](../architecture-decisions/ADR-004-multi-cloud-architecture.md)

---

## Executive Summary

Aura provides enterprise teams with self-service rapid prototyping capabilities to spin up isolated test environments in minutes without infrastructure team intervention. The system enforces security guardrails, cost governance, and compliance requirements while enabling developer velocity.

**Key Capabilities:**
- Self-service environment provisioning (< 5 minutes)
- Pre-built templates for common use cases
- Multi-cloud support (AWS GovCloud + Azure Government)
- Configurable approval workflows based on compliance posture
- Automatic cleanup and cost governance

---

## What Can Users Provision?

### Environment Types

| Type | Time to Provision | TTL | Approval | Use Case |
|------|-------------------|-----|----------|----------|
| **Quick** | < 5 minutes | 4 hours | Auto-approved | API prototyping, unit tests |
| **Standard** | 5-15 minutes | 24 hours | Auto-approved | Full-stack application testing |
| **Extended** | 15 min + approval | 7 days | HITL required | Multi-day integration testing |
| **Compliance** | 15 min + approval | 24 hours | HITL required | Security/penetration testing |

### Pre-Built Templates

Users can instantly provision from these approved templates:

| Template | Resources Included | Est. Cost/Day |
|----------|-------------------|---------------|
| **Python FastAPI** | ECS Task (1 vCPU, 2GB), DynamoDB, S3 | $0.50 |
| **React Frontend** | ECS Task (0.5 vCPU, 1GB), CloudFront, S3 | $0.30 |
| **Full Stack** | API + UI containers, DynamoDB, S3 | $1.20 |
| **Data Pipeline** | Step Functions, Lambda, S3, DynamoDB | $0.80 |
| **ML Experiment** | SageMaker Notebook, S3 | $2.50 |

### Template Marketplace

Teams can submit custom CloudFormation templates to the marketplace. Submissions go through HITL approval before being published for organization-wide use.

---

## Multi-Cloud Support

Aura's cloud abstraction layer enables deployment to both AWS and Azure government clouds:

| Service | AWS GovCloud | Azure Government |
|---------|--------------|------------------|
| Graph Database | Amazon Neptune | Azure Cosmos DB (Gremlin) |
| Vector Database | Amazon OpenSearch | Azure AI Search |
| LLM Provider | Amazon Bedrock (Claude) | Azure OpenAI (GPT-4) |
| Object Storage | Amazon S3 | Azure Blob Storage |
| Container Orchestration | Amazon EKS | Azure AKS |
| Secrets Management | AWS Secrets Manager | Azure Key Vault |

**Cloud Selection:** Set via environment variable `CLOUD_PROVIDER=aws` or `CLOUD_PROVIDER=azure`. The platform automatically routes to the appropriate service implementations.

---

## Permission Model

### What Users CAN Do

Users with the `test-env-user-role` can:

- Provision environments from pre-approved templates
- Create EKS namespaces for quick tests
- View and manage their own environments
- Extend environment TTL (may trigger HITL approval)
- Submit custom templates to the marketplace

### What Users CANNOT Do

The permission model explicitly prevents:

- **Arbitrary resource creation** - Only pre-approved templates allowed
- **Production access** - Explicit IAM Deny policies block production resources
- **IAM privilege escalation** - Cannot create roles, attach policies, or modify permissions
- **VPC modifications** - Cannot create/delete VPCs, subnets, or network infrastructure
- **Cross-region operations** - Scoped to the configured region only
- **Cross-account access** - Isolated within the test environment account

### Resource Scoping

All test environment resources are scoped to:
- Resource prefix: `aura-testenv-*` or `aura-test-env-*`
- Mandatory tag: `TestEnvId` required on all resources
- Session duration: Maximum 4 hours per session
- Permission boundary: Attached to all test environment roles

---

## Approval Workflows

### Autonomy Policy Framework

Organizations configure their approval requirements based on compliance posture:

| Policy Preset | Default Behavior | Target Industry |
|---------------|------------------|-----------------|
| `defense_contractor` | All operations require HITL | CMMC Level 3+, GovCloud |
| `financial_services` | All operations require HITL | SOX, PCI-DSS |
| `healthcare` | All operations require HITL | HIPAA |
| `fintech_startup` | Only HIGH/CRITICAL require HITL | Growth-stage companies |
| `enterprise_standard` | Only HIGH/CRITICAL require HITL | Fortune 500 |
| `internal_tools` | Fully autonomous | Internal dev teams |
| `fully_autonomous` | Fully autonomous | Commercial dev/test |

### Unbypassable Guardrails

These operations **always** require human approval, regardless of policy settings:

- Production deployment
- Credential modification
- Access control changes
- Database migration
- Infrastructure modifications

---

## Cost Governance

### Per-User Quotas

| Control | Limit |
|---------|-------|
| Concurrent environments | 3 per user |
| Monthly budget | $500 per user |
| Session duration | 4 hours maximum |
| Idle timeout | 2 hours with no activity |

### Automatic Cleanup

- **TTL enforcement** - Environments automatically terminated at expiry
- **Idle detection** - CloudWatch metrics trigger cleanup after 2 hours of inactivity
- **Budget alerts** - SNS notifications when approaching budget limits
- **Daily cleanup Lambda** - Catches any orphaned resources

### Cost Optimization Options

- **Fargate Spot** - 60-70% cost savings for non-critical workloads
- **EKS Namespaces** - Lowest cost option for quick tests ($0.10/day)
- **Scheduled provisioning** - Pre-provision for known events, terminate when not needed

---

## API Reference

### Environment Management Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/environments` | GET | List your environments |
| `/api/v1/environments` | POST | Create new environment |
| `/api/v1/environments/{id}` | GET | Get environment details |
| `/api/v1/environments/{id}` | DELETE | Terminate environment |
| `/api/v1/environments/{id}/extend` | POST | Extend TTL (may trigger HITL) |
| `/api/v1/environments/templates` | GET | List available templates |
| `/api/v1/environments/quota` | GET | Check your quota status |
| `/api/v1/environments/health` | GET | Service health check |

### Example: Create Environment

```bash
curl -X POST https://api.aura.local/api/v1/environments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "standard",
    "template": "python-fastapi",
    "name": "my-prototype",
    "description": "Testing new API feature"
  }'
```

### Response

```json
{
  "environment_id": "env-abc123",
  "status": "PROVISIONING",
  "dns_name": "env-abc123.test.aura.local",
  "ttl_expires_at": "2025-12-17T12:00:00Z",
  "estimated_cost_per_day": 0.50
}
```

---

## Environment Lifecycle

```
PENDING_APPROVAL → PROVISIONING → ACTIVE → EXPIRING → TERMINATING → TERMINATED
     ↓                                                        ↑
     └──────────────────── FAILED ────────────────────────────┘
```

| State | Description |
|-------|-------------|
| `PENDING_APPROVAL` | Awaiting HITL decision (extended/compliance types) |
| `PROVISIONING` | CloudFormation/ECS task creation in progress |
| `ACTIVE` | Ready for use, accessible via DNS |
| `EXPIRING` | Within 1 hour of TTL, user can request extension |
| `TERMINATING` | Cleanup in progress |
| `TERMINATED` | Removed, record retained for audit |
| `FAILED` | Provisioning or cleanup failed |

---

## Security & Compliance

### Network Isolation

- Test environments deployed in isolated subnets
- Security groups block inbound from production VPCs
- Egress-only network patterns prevent lateral movement
- DNS registration via dnsmasq: `{env-id}.test.aura.local`

### Data Isolation

- **IAM Deny Policies** explicitly block:
  - Production DynamoDB tables (`*-prod`)
  - Production S3 buckets (`*-prod/*`)
  - Production secrets (`/aura/prod/*`)
  - Production Neptune/OpenSearch clusters
- **Synthetic data only** - No production data copies allowed

### Audit Trail

All provisioning events are logged:
- CloudTrail captures API calls
- DynamoDB audit table with 365-day retention
- CloudWatch Logs for Lambda executions
- Autonomy decision log tracks approval/rejection rationale

### CMMC Level 2 Alignment

| Control | Implementation |
|---------|----------------|
| AC.L2-3.1.1 | Cognito/OIDC federation, user-assumable roles |
| AC.L2-3.1.2 | Service Catalog products enforce allowed configurations |
| AU.L2-3.3.1 | CloudTrail + DynamoDB audit logging |
| CM.L2-3.4.1 | Service Catalog product versions as baselines |
| SC.L2-3.13.1 | Network isolation, security groups, explicit denies |

---

## UI Access

### Environments Page

Access via the Aura Platform UI:
1. Navigate to **Environments** in the sidebar
2. Click **New Environment**
3. Select template and configuration
4. Monitor provisioning status in real-time
5. Access environment via provided DNS name

### Environment Dashboard

Each environment has a detail dashboard with:
- **Overview tab** - Status, DNS, TTL, cost
- **Resources tab** - Deployed AWS/Azure resources
- **Logs tab** - Application and provisioning logs
- **Metrics tab** - CloudWatch metrics and alarms

---

## Advanced Features

### Scheduled Provisioning

Pre-provision environments for known events:

```bash
curl -X POST https://api.aura.local/api/v1/environments/schedule \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "template": "full-stack",
    "scheduled_at": "2025-12-20T09:00:00Z",
    "name": "demo-environment"
  }'
```

### EKS Namespace Controller

For rapid API prototyping (< 5 minute provisioning):
- Creates isolated Kubernetes namespace
- Applies ResourceQuota (2 CPU, 4GB RAM, 10 pods)
- Optional NetworkPolicy with default-deny
- ServiceAccount for workload identity

### Template Marketplace

Submit custom templates:

```bash
curl -X POST https://api.aura.local/api/v1/environments/marketplace/submit \
  -H "Authorization: Bearer $TOKEN" \
  -F "template=@my-template.yaml" \
  -F "category=backend" \
  -F "description=Custom API service template"
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Resolution |
|-------|-------|------------|
| Provisioning timeout | CloudFormation stack creation slow | Check CloudFormation events in AWS Console |
| Access denied | Permission boundary blocking | Verify resource naming follows `aura-testenv-*` pattern |
| Quota exceeded | User at concurrent limit | Terminate unused environments |
| DNS not resolving | dnsmasq sync delay | Wait 30 seconds, retry |

### Getting Help

- **Runbook:** [TEST_ENVIRONMENT_RUNBOOK.md](../runbooks/TEST_ENVIRONMENT_RUNBOOK.md)
- **Architecture:** [ADR-039](../architecture-decisions/ADR-039-self-service-test-environments.md)
- **Autonomy Framework:** [ADR-032](../architecture-decisions/ADR-032-configurable-autonomy-framework.md)

---

## Summary

Aura's rapid prototyping capabilities enable teams to move fast while maintaining security and compliance:

| Capability | Benefit |
|------------|---------|
| Self-service provisioning | No infrastructure team bottleneck |
| Pre-approved templates | Instant deployment, enforced best practices |
| Multi-cloud support | Deploy to AWS or Azure based on requirements |
| Configurable autonomy | Match approval workflow to compliance posture |
| Automatic cleanup | No orphaned resources or surprise costs |
| Permission boundaries | Prevent privilege escalation |
| Production isolation | Explicit deny policies protect production |

**Users cannot create arbitrary cloud resources.** All provisioning flows through pre-approved templates with enforced security guardrails, cost governance, and audit logging.
