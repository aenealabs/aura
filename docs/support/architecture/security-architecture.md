# Security Architecture

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This document describes Project Aura's security architecture, including network isolation, encryption, access control, and compliance controls. The architecture is designed for regulated industries requiring CMMC Level 3, SOX, and FedRAMP compliance.

---

## Security Principles

### Defense in Depth

Multiple layers of security controls protect data and systems:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DEFENSE IN DEPTH LAYERS                              │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────┐
    │  LAYER 1: PERIMETER                                                  │
    │  AWS WAF | DDoS Protection | Geo-Blocking | Rate Limiting           │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  LAYER 2: NETWORK                                                    │
    │  VPC Isolation | Security Groups | NACLs | VPC Endpoints            │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  LAYER 3: IDENTITY                                                   │
    │  IAM Roles | IRSA | RBAC | MFA | Session Management                 │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  LAYER 4: APPLICATION                                                │
    │  Input Validation | Output Encoding | CSRF | Rate Limiting          │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  LAYER 5: DATA                                                       │
    │  Encryption at Rest | Encryption in Transit | Key Management        │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  LAYER 6: MONITORING                                                 │
    │  GuardDuty | CloudTrail | Config | Security Hub | SIEM              │
    └─────────────────────────────────────────────────────────────────────┘
```

### Zero Trust Architecture

No implicit trust within the network:

- All service-to-service communication authenticated
- Least privilege access for all components
- Continuous verification of identity and authorization
- Micro-segmentation of workloads

---

## Network Security

### VPC Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              VPC (10.0.0.0/16)                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ PUBLIC SUBNETS (10.0.0.0/20)                                         │   │
│  │ ┌───────────────────────┐  ┌───────────────────────┐                │   │
│  │ │ ALB                   │  │ NAT Gateway           │                │   │
│  │ │ (Internet-facing)     │  │ (Egress only)         │                │   │
│  │ └───────────────────────┘  └───────────────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ PRIVATE SUBNETS (10.0.16.0/20)                                       │   │
│  │ ┌───────────────────────┐  ┌───────────────────────┐                │   │
│  │ │ EKS Worker Nodes      │  │ Application Services  │                │   │
│  │ │ - API pods            │  │ - Agents              │                │   │
│  │ │ - Frontend            │  │ - Lambda              │                │   │
│  │ └───────────────────────┘  └───────────────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ ISOLATED SUBNETS (10.0.32.0/20) - No Internet                        │   │
│  │ ┌───────────────────────┐  ┌───────────────────────┐                │   │
│  │ │ Neptune Cluster       │  │ OpenSearch Domain     │                │   │
│  │ └───────────────────────┘  └───────────────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ SANDBOX SUBNETS (10.0.48.0/20) - Completely Isolated                 │   │
│  │ ┌───────────────────────┐                                           │   │
│  │ │ Sandbox Fargate Tasks │  No NAT, No VPC Endpoints                 │   │
│  │ │ (Test execution only) │  Read-only access to test data            │   │
│  │ └───────────────────────┘                                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  VPC ENDPOINTS (Interface & Gateway)                                        │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │
│  │ S3  │ │ ECR │ │ DDB │ │ SSM │ │ STS │ │ KMS │ │Logs │ │Bedrk│       │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Security Groups

| Security Group | Inbound | Outbound | Purpose |
|----------------|---------|----------|---------|
| alb-sg | 443 (Internet) | EKS nodes (8080) | Load balancer |
| eks-node-sg | 8080 (ALB), 443 (Control plane) | All VPC endpoints | Worker nodes |
| neptune-sg | 8182 (EKS nodes) | None | Graph database |
| opensearch-sg | 9200 (EKS nodes) | None | Vector database |
| sandbox-sg | None | Test repos only | Sandbox isolation |

### Network ACLs

| NACL | Rule | Protocol | Port | Source/Dest | Action |
|------|------|----------|------|-------------|--------|
| Public | 100 | TCP | 443 | 0.0.0.0/0 | Allow |
| Public | 200 | TCP | 1024-65535 | 0.0.0.0/0 | Allow |
| Public | * | All | All | 0.0.0.0/0 | Deny |
| Private | 100 | All | All | VPC CIDR | Allow |
| Private | * | All | All | 0.0.0.0/0 | Deny |
| Isolated | 100 | All | All | Private subnets | Allow |
| Isolated | * | All | All | 0.0.0.0/0 | Deny |

---

## Identity and Access Management

### IAM Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          IAM ARCHITECTURE                                    │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────┐
    │                    HUMAN IDENTITIES                                  │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
    │  │   Org Admin │  │  Security   │  │  Developer  │                 │
    │  │             │  │    Admin    │  │             │                 │
    │  │ - IAM Admin │  │ - HITL Admin│  │ - Repo CRUD │                 │
    │  │ - Billing   │  │ - Audit View│  │ - Vuln View │                 │
    │  │ - All       │  │ - Approve   │  │ - Patch View│                 │
    │  └─────────────┘  └─────────────┘  └─────────────┘                 │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                           Federation (SAML/OIDC)
                                    │
    ┌───────────────────────────────▼─────────────────────────────────────┐
    │                    SERVICE IDENTITIES (IRSA)                         │
    │                                                                      │
    │  ┌─────────────────────────────────────────────────────────────┐   │
    │  │ EKS Service Accounts                                         │   │
    │  │ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │   │
    │  │ │ aura-api-sa │  │orchestrator │  │ validator-sa│           │   │
    │  │ │             │  │     -sa     │  │             │           │   │
    │  │ │ - S3 RO     │  │ - Neptune   │  │ - ECS       │           │   │
    │  │ │ - DDB RO    │  │ - OpenSearch│  │ - ECR       │           │   │
    │  │ │ - Secrets   │  │ - Bedrock   │  │ - S3        │           │   │
    │  │ │             │  │ - DDB       │  │             │           │   │
    │  │ └─────────────┘  └─────────────┘  └─────────────┘           │   │
    │  └─────────────────────────────────────────────────────────────┘   │
    │                                                                      │
    │  ┌─────────────────────────────────────────────────────────────┐   │
    │  │ Lambda Execution Roles                                       │   │
    │  │ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │   │
    │  │ │notification │  │  scan-role  │  │  hitl-role  │           │   │
    │  │ │   -role     │  │             │  │             │           │   │
    │  │ │ - SES       │  │ - S3        │  │ - DDB       │           │   │
    │  │ │ - SNS       │  │ - Neptune   │  │ - Step Func │           │   │
    │  │ └─────────────┘  └─────────────┘  └─────────────┘           │   │
    │  └─────────────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────────────┘
```

### IRSA (IAM Roles for Service Accounts)

```yaml
# Example IRSA configuration
apiVersion: v1
kind: ServiceAccount
metadata:
  name: orchestrator-sa
  namespace: aura-system
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/aura-orchestrator-role-prod
---
# Trust policy on IAM role
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED539D4633E53DE1B71EXAMPLE"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED539D4633E53DE1B71EXAMPLE:sub": "system:serviceaccount:aura-system:orchestrator-sa"
        }
      }
    }
  ]
}
```

---

## Role-Based Access Control (RBAC)

Project Aura implements RBAC at two levels: **Agent Capability Governance** for AI agents and **User Role Management** for platform end users.

### Agent Capability Governance (ADR-066)

AI agents operate under strict capability policies that enforce the principle of least privilege. Each agent type has an explicit allowlist of tools it can invoke.

#### Tool Classification Tiers

| Tier | Classification | Description | Example Tools |
|------|---------------|-------------|---------------|
| 1 | **SAFE** | Read-only, no side effects | `semantic_search`, `list_agents`, `get_documentation` |
| 2 | **MONITORING** | Read access to sensitive data | `query_code_graph`, `get_vulnerability_report`, `query_audit_logs` |
| 3 | **DANGEROUS** | Write operations, state changes | `destroy_sandbox`, `commit_changes`, `update_policy` |
| 4 | **CRITICAL** | Production impact, irreversible | `deploy_to_production`, `access_secrets`, `modify_iam_policy` |

#### Capability Enforcement Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AGENT CAPABILITY GOVERNANCE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Agent Tool Invocation                                                       │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ CapabilityEnforcementMiddleware                                      │   │
│  │                                                                      │   │
│  │  1. Extract Agent Identity & Context                                 │   │
│  │     - Agent type (Coder, Reviewer, Validator)                       │   │
│  │     - Execution context (test, sandbox, production)                 │   │
│  │     - Parent agent (if spawned dynamically)                         │   │
│  │                                                                      │   │
│  │  2. Resolve Effective Capabilities                                   │   │
│  │     - Base capabilities from AgentCapabilityPolicy                  │   │
│  │     - Context overrides (sandbox grants, test restrictions)         │   │
│  │     - Dynamic grants (HITL elevation, emergency access)             │   │
│  │     - Parent inheritance (cannot exceed parent capabilities)        │   │
│  │                                                                      │   │
│  │  3. Evaluate Permission                                              │   │
│  │     - Check tool in allowed_tools for agent                         │   │
│  │     - Verify action permitted (read, write, execute, admin)         │   │
│  │     - Validate context constraints                                  │   │
│  │     - Check rate limits per agent-tool pair                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                    │
│  │  ALLOW   │  │   DENY   │  │ ESCALATE │  │  AUDIT   │                    │
│  │          │  │          │  │  (HITL)  │  │   ONLY   │                    │
│  │ Proceed  │  │  Block   │  │ Queue for│  │ Allow +  │                    │
│  │          │  │          │  │ approval │  │   log    │                    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Agent Type Capabilities

| Agent Type | SAFE Tools | MONITORING Tools | DANGEROUS Tools | CRITICAL Tools |
|------------|------------|------------------|-----------------|----------------|
| **CoderAgent** | ✓ All | ✓ Code analysis | ✓ Branch/commit | ✗ None |
| **ReviewerAgent** | ✓ All | ✓ All | ✗ None | ✗ None |
| **ValidatorAgent** | ✓ All | ✓ Test results | ✓ Sandbox ops | ✗ None |
| **OrchestratorAgent** | ✓ All | ✓ All | ✓ All | HITL escalation |

**Security Guarantees:**
- Default-deny: Unknown tools require explicit configuration
- Context isolation: Test agents cannot access production resources
- No privilege escalation: Child agents cannot exceed parent capabilities
- Complete audit trail: All capability checks are logged

**Implementation:** `src/services/capability_governance/`

---

### End User RBAC

Platform users are assigned roles that control API access and dashboard defaults.

#### User Roles

| Role | Description | Access Level |
|------|-------------|--------------|
| `security-engineer` | Security-focused users | Vulnerability management, security dashboards |
| `devops` | Operations engineers | Deployment pipelines, infrastructure metrics |
| `engineering-manager` | Team leads | Team metrics, resource allocation |
| `executive` | C-suite, leadership | High-level KPIs, compliance status |
| `superuser` | Full platform access | All features, admin functions |
| `admin` | System administrators | User management, configuration |
| `operator` | Operational tasks | System operations, maintenance |
| `customer_success` | Customer support | Customer health, SLA management |
| `billing_admin` | Financial operations | Billing, SLA credits |

#### Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER AUTHENTICATION                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User Login                                                                  │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ AWS Cognito User Pool                                                │   │
│  │                                                                      │   │
│  │  - Username/password or SSO (SAML/OIDC)                             │   │
│  │  - MFA enforcement (optional)                                        │   │
│  │  - User groups define roles                                          │   │
│  │  - JWT token issued on success                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       │ JWT Token (contains groups/roles)                                   │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ FastAPI Middleware (src/api/auth.py)                                 │   │
│  │                                                                      │   │
│  │  1. Validate JWT signature (Cognito JWKS)                           │   │
│  │  2. Check token expiration                                          │   │
│  │  3. Extract user identity and groups                                │   │
│  │  4. Apply require_role() checks on protected endpoints              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌──────────┐  ┌──────────┐                                                │
│  │  ALLOW   │  │   DENY   │                                                │
│  │          │  │  HTTP    │                                                │
│  │ Process  │  │   403    │                                                │
│  │ request  │  │          │                                                │
│  └──────────┘  └──────────┘                                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### API Endpoint Protection

Endpoints are protected using the `require_role()` decorator:

```python
from src.api.auth import require_role, User

# Single role required
@app.get("/admin/users")
async def list_users(user: User = Depends(require_role("admin"))):
    return {"users": [...]}

# Multiple roles allowed (OR logic)
@app.post("/approvals")
async def approve_patch(user: User = Depends(require_role("admin", "security-engineer"))):
    return {"approved": True}
```

#### Protected Endpoint Examples

| Endpoint Category | Required Roles |
|-------------------|---------------|
| Disaster Recovery | `admin` |
| Customer Health | `admin`, `customer_success` |
| Alignment Operations | `admin`, `operator` |
| SLA Management | `admin`, `customer_success`, `billing_admin` |
| Health Metrics | `admin`, `operator` |

#### Dashboard Role Defaults

Each role receives a customized default dashboard layout:

| Role | Default Widgets |
|------|-----------------|
| `security-engineer` | Vulnerability trends, CVE severity, patch status |
| `devops` | Deployment metrics, pipeline status, infrastructure health |
| `engineering-manager` | Team velocity, resource utilization, SLA compliance |
| `executive` | KPI summary, compliance status, cost overview |
| `superuser` | Full executive view with admin tools |

**Implementation:**
- Authentication: `src/api/auth.py`
- Dashboard models: `src/services/dashboard/models.py`
- Role defaults: `src/services/dashboard/dashboard_service.py`

---

## Encryption

### Encryption at Rest

| Resource | Encryption | Key Type | Rotation |
|----------|------------|----------|----------|
| Neptune | AES-256 | CMK | Annual |
| OpenSearch | AES-256 | CMK | Annual |
| DynamoDB | AES-256 | CMK | Annual |
| S3 | AES-256 | CMK | Annual |
| EBS | AES-256 | CMK | Annual |
| Secrets Manager | AES-256 | CMK | Automatic |

### Encryption in Transit

| Communication Path | Protocol | Certificate |
|--------------------|----------|-------------|
| Client to ALB | TLS 1.3 | ACM managed |
| ALB to EKS | TLS 1.2+ | Internal CA |
| EKS to Neptune | TLS 1.2 | AWS managed |
| EKS to OpenSearch | TLS 1.2 | AWS managed |
| EKS to Bedrock | TLS 1.2 | AWS managed |

### KMS Key Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Enable IAM User Permissions",
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::123456789012:root"},
      "Action": "kms:*",
      "Resource": "*"
    },
    {
      "Sid": "Allow Service Use",
      "Effect": "Allow",
      "Principal": {"Service": ["neptune.amazonaws.com", "es.amazonaws.com"]},
      "Action": ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey*"],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": [
            "neptune.us-east-1.amazonaws.com",
            "es.us-east-1.amazonaws.com"
          ]
        }
      }
    }
  ]
}
```

---

## Application Security

### Input Validation

All user input is validated before processing:

| Input Type | Validation | Example |
|------------|------------|---------|
| API parameters | JSON Schema | Pydantic models |
| Query strings | Allowlist | Enum validation |
| File uploads | Type + size | Magic number check |
| Git URLs | URL parsing | Protocol allowlist |

### Output Encoding

| Context | Encoding | Library |
|---------|----------|---------|
| HTML | HTML entity | bleach |
| JSON | JSON escape | stdlib |
| SQL | Parameterized | SQLAlchemy |
| Shell | Quote/escape | shlex |

### Security Headers

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'; script-src 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
```

---

## AI-Specific Security

### LLM Security Controls

| Threat | Control | Implementation |
|--------|---------|----------------|
| Prompt injection | Input sanitization | LLM prompt sanitizer |
| Data exfiltration | Output filtering | Guardrails |
| Model abuse | Rate limiting | Per-user token limits |
| Jailbreak attempts | Content filtering | Bedrock Guardrails |

### Bedrock Guardrails Configuration

```yaml
GuardrailVersion: 1
GuardrailId: aura-security-guardrail

# Content filters
ContentPolicyConfig:
  FiltersConfig:
    - Type: SEXUAL
      InputStrength: HIGH
      OutputStrength: HIGH
    - Type: VIOLENCE
      InputStrength: HIGH
      OutputStrength: HIGH
    - Type: HATE
      InputStrength: HIGH
      OutputStrength: HIGH
    - Type: INSULTS
      InputStrength: MEDIUM
      OutputStrength: MEDIUM
    - Type: MISCONDUCT
      InputStrength: HIGH
      OutputStrength: HIGH
    - Type: PROMPT_ATTACK
      InputStrength: HIGH
      OutputStrength: NONE

# Topic restrictions
TopicPolicyConfig:
  TopicsConfig:
    - Name: Malware
      Definition: Code designed to harm systems
      Examples:
        - Write a virus
        - Create ransomware
      Type: DENY
```

### Sandbox Escape Prevention

| Control | Implementation |
|---------|----------------|
| Network isolation | No internet, VPC endpoints only |
| Filesystem | Read-only root, temp write only |
| Process limits | seccomp, AppArmor profiles |
| Resource limits | CPU, memory, time caps |
| Capabilities | Drop all, add only required |

---

## Monitoring and Detection

### Security Monitoring Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SECURITY MONITORING                                  │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────┐
    │                     DATA COLLECTION                                  │
    │                                                                      │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
    │  │ CloudTrail  │  │  VPC Flow   │  │  GuardDuty  │  │  Config   │  │
    │  │             │  │    Logs     │  │             │  │           │  │
    │  │ - API calls │  │ - Network   │  │ - Threats   │  │ - Drift   │  │
    │  │ - IAM       │  │ - Traffic   │  │ - Anomalies │  │ - Compliance│ │
    │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬─────┘  │
    │         │                │                │               │         │
    └─────────┼────────────────┼────────────────┼───────────────┼─────────┘
              │                │                │               │
              └────────────────┼────────────────┼───────────────┘
                               │                │
                               ▼                ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                     AGGREGATION                                      │
    │                                                                      │
    │  ┌─────────────────────────────────────────────────────────────┐   │
    │  │                    Security Lake / SIEM                      │   │
    │  │                                                              │   │
    │  │  - Event correlation                                         │   │
    │  │  - Threat intelligence                                       │   │
    │  │  - Anomaly detection                                         │   │
    │  └─────────────────────────────────────────────────────────────┘   │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                     ALERTING                                         │
    │                                                                      │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
    │  │   SNS       │  │   Slack     │  │  PagerDuty  │                 │
    │  │  (Email)    │  │  (Webhook)  │  │  (Incident) │                 │
    │  └─────────────┘  └─────────────┘  └─────────────┘                 │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘
```

### CloudWatch Alarms

| Alarm | Metric | Threshold | Action |
|-------|--------|-----------|--------|
| HighErrorRate | 5xx errors | >1% for 5min | P2 alert |
| UnauthorizedCalls | AccessDenied | >10/min | P1 alert |
| RootAccountUsage | Root login | Any | P1 alert |
| SensitiveAPICall | IAM changes | Any | P2 alert |
| GuardDutyHigh | High severity | Any | P1 alert |
| ConfigNonCompliant | Compliance | Any | P3 alert |

---

## Compliance Controls

### CMMC Level 3 Mapping

| Domain | Control | Implementation |
|--------|---------|----------------|
| AC | Access Control | IAM, RBAC, MFA |
| AU | Audit | CloudTrail, CloudWatch |
| CM | Configuration | AWS Config, drift detection |
| IA | Identification | IAM, Cognito, SAML |
| IR | Incident Response | GuardDuty, runbooks |
| MA | Maintenance | Patch management |
| MP | Media Protection | S3 encryption, versioning |
| PE | Physical | AWS data centers |
| PS | Personnel | SOC 2 attestation |
| RA | Risk Assessment | Security assessments |
| SC | System/Comms | Network isolation, TLS |
| SI | System/Info | Vulnerability management |

### Audit Logging

All security-relevant events are logged:

```json
{
  "timestamp": "2026-01-19T12:00:00Z",
  "event_type": "patch.approved",
  "actor": {
    "user_id": "user-12345",
    "email": "security@acme.com",
    "ip_address": "203.0.113.50",
    "user_agent": "Mozilla/5.0..."
  },
  "resource": {
    "type": "patch",
    "id": "patch-67890",
    "vulnerability_id": "vuln-12345"
  },
  "action": {
    "type": "approve",
    "comment": "Reviewed and approved",
    "deploy_requested": true
  },
  "context": {
    "organization_id": "org-xyz789",
    "request_id": "req-abc123"
  }
}
```

---

## Related Documentation

- [Architecture Index](./index.md)
- [System Overview](./system-overview.md)
- [Disaster Recovery](./disaster-recovery.md)
- [Compliance Profiles](../../security/COMPLIANCE_PROFILES.md)
- [Security Services Overview](../../security/SECURITY_SERVICES_OVERVIEW.md)

---

*Last updated: January 2026 | Version 1.0*
