# ADR-073: Attribute-Based Access Control (ABAC) for Multi-Tenant User Authorization

## Status

Deployed

## Date

2026-01-27

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Pending | AWS AI SaaS Architect | - | - |
| Pending | Senior Systems Architect | - | - |
| Pending | Cybersecurity Analyst | - | - |
| Pending | Test Architect | - | - |

### Review Summary

_Awaiting review._

## Context

### Current State

ADR-066 implements Agent Capability Governance, but end-user authorization remains role-based only:

| Aspect | Current State | Gap |
|--------|---------------|-----|
| User authorization | RBAC via Cognito groups | Cannot express "user X can only access tenant Y resources" |
| Multi-tenant isolation | Application-level checks | No policy-based enforcement |
| Resource-level access | Not implemented | "Admin" means admin of everything |
| Context-aware decisions | Not supported | Cannot vary permissions by time, location, risk |
| Cross-organization access | Manual exception handling | No formal policy model |

### RBAC Limitations for Multi-Tenant SaaS

```text
RBAC Gaps in Multi-Tenant Context:

Role: "security-engineer"
├── Can view vulnerabilities (global capability)
├── Can approve patches (global capability)
├── Can access all tenants? ← Problem
│   ├── Tenant A: Customer owns their data
│   ├── Tenant B: Different compliance requirements
│   └── Tenant C: Competitor - must not see each other's data
│
└── RBAC cannot express:
    ├── "security-engineer for Tenant A only"
    ├── "can approve patches only in dev environment"
    ├── "can access only repositories tagged 'public'"
    └── "elevated access during business hours only"
```

### Why ABAC

ABAC (Attribute-Based Access Control) enables fine-grained authorization based on:

- **Subject attributes**: User's tenant, department, clearance level, risk score
- **Resource attributes**: Sensitivity classification, owner, creation date, tags
- **Action attributes**: Read vs write, bulk vs single, sync vs async
- **Context attributes**: Time of day, IP address, device trust, session risk

### Industry Standards

- **NIST SP 800-162**: Guide to ABAC Definition and Considerations
- **XACML**: eXtensible Access Control Markup Language (OASIS standard)
- **AWS IAM**: Native ABAC via resource tags and principal tags
- **OPA/Rego**: Cloud-native policy engine with ABAC support

## Decision

Implement Attribute-Based Access Control for end-user authorization, extending the existing RBAC system to support multi-tenant isolation, resource-level permissions, and context-aware access decisions.

## Architecture

### ABAC Model

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ABAC AUTHORIZATION MODEL                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ATTRIBUTES                                                                  │
│  ──────────                                                                  │
│                                                                              │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │  Subject Attributes │  │ Resource Attributes │  │ Context Attributes  │ │
│  │  (User/Principal)   │  │ (Target Object)     │  │ (Environment)       │ │
│  │                     │  │                     │  │                     │ │
│  │  • user_id          │  │  • resource_type    │  │  • request_time     │ │
│  │  • tenant_id        │  │  • tenant_id        │  │  • source_ip        │ │
│  │  • roles[]          │  │  • sensitivity      │  │  • device_trust     │ │
│  │  • department       │  │  • owner_id         │  │  • session_risk     │ │
│  │  • clearance_level  │  │  • classification   │  │  • mfa_verified     │ │
│  │  • risk_score       │  │  • tags{}           │  │  • location         │ │
│  │  • organization     │  │  • environment      │  │  • auth_method      │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
│                                                                              │
│  POLICY EVALUATION                                                           │
│  ─────────────────                                                           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │   permit(subject, action, resource, context) ←                      │   │
│  │       subject.tenant_id == resource.tenant_id AND                   │   │
│  │       subject.clearance_level >= resource.sensitivity AND           │   │
│  │       context.mfa_verified == true AND                              │   │
│  │       action in subject.roles[].allowed_actions                     │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Attribute Sources

```text
Attribute Flow:

┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│    Cognito       │     │    DynamoDB      │     │   Resource Tags  │
│    JWT Claims    │     │   User Profile   │     │   (S3, DDB, etc) │
└────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                        │                        │
         │  • sub (user_id)       │  • tenant_id          │  • tenant_id
         │  • cognito:groups      │  • department         │  • sensitivity
         │  • custom:tenant       │  • clearance          │  • owner
         │  • email               │  • organization       │  • classification
         │  • iat/exp             │  • risk_score         │  • environment
         │                        │  • mfa_enabled        │
         ▼                        ▼                        ▼
    ┌─────────────────────────────────────────────────────────────┐
    │              Attribute Resolution Service                    │
    │                                                             │
    │  resolve_attributes(jwt, resource_arn) → AttributeContext  │
    └─────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    OPA Policy Engine                         │
    │                                                             │
    │  evaluate(action, AttributeContext) → Decision              │
    └─────────────────────────────────────────────────────────────┘
```

### Policy Language (Rego)

```rego
# policies/abac/tenant_isolation.rego

package aura.authz

import future.keywords.if
import future.keywords.in

# Default deny
default allow := false

# Main authorization rule
allow if {
    # Basic role check (RBAC foundation)
    required_role := action_role_mapping[input.action]
    required_role in input.subject.roles

    # Tenant isolation (ABAC extension)
    tenant_match

    # Sensitivity check
    clearance_sufficient

    # Context requirements
    context_valid
}

# Tenant isolation: user can only access their tenant's resources
tenant_match if {
    input.subject.tenant_id == input.resource.tenant_id
}

# Cross-tenant access for platform admins
tenant_match if {
    "platform-admin" in input.subject.roles
    input.context.mfa_verified == true
}

# Sensitivity levels: user clearance must meet or exceed resource sensitivity
sensitivity_levels := {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
    "top-secret": 4,
}

clearance_sufficient if {
    user_level := sensitivity_levels[input.subject.clearance_level]
    resource_level := sensitivity_levels[input.resource.sensitivity]
    user_level >= resource_level
}

# Context validation
context_valid if {
    # MFA required for sensitive resources
    input.resource.sensitivity in ["confidential", "restricted", "top-secret"]
    input.context.mfa_verified == true
}

context_valid if {
    # MFA not required for lower sensitivity
    not input.resource.sensitivity in ["confidential", "restricted", "top-secret"]
}

# Time-based restrictions (optional)
context_valid if {
    # Business hours check for certain actions
    input.action in ["approve_patch", "deploy_production"]
    is_business_hours(input.context.request_time)
}

# Action to role mapping
action_role_mapping := {
    "view_vulnerabilities": ["security-engineer", "devops", "admin"],
    "approve_patch": ["security-engineer", "admin"],
    "deploy_production": ["devops", "admin"],
    "manage_users": ["admin"],
    "view_billing": ["billing_admin", "admin"],
    "access_all_tenants": ["platform-admin"],
}
```

### Authorization Service

```python
# src/services/authorization/abac_service.py

from dataclasses import dataclass
from typing import Optional
import httpx

@dataclass
class AttributeContext:
    """Resolved attributes for authorization decision."""

    subject: SubjectAttributes
    resource: ResourceAttributes
    context: ContextAttributes
    action: str

@dataclass
class SubjectAttributes:
    user_id: str
    tenant_id: str
    roles: list[str]
    department: Optional[str]
    clearance_level: str
    risk_score: float
    organization: str

@dataclass
class ResourceAttributes:
    resource_type: str
    resource_id: str
    tenant_id: str
    sensitivity: str
    owner_id: str
    classification: str
    tags: dict[str, str]
    environment: str

@dataclass
class ContextAttributes:
    request_time: str
    source_ip: str
    device_trust: str
    session_risk: float
    mfa_verified: bool
    auth_method: str

class ABACAuthorizationService:
    """Attribute-Based Access Control authorization service."""

    def __init__(
        self,
        opa_url: str,
        dynamodb_client,
        cognito_client,
    ):
        self.opa_url = opa_url
        self.dynamodb = dynamodb_client
        self.cognito = cognito_client
        self._attribute_cache = TTLCache(maxsize=10000, ttl=300)

    async def authorize(
        self,
        jwt_claims: dict,
        action: str,
        resource_arn: str,
        request_context: dict,
    ) -> AuthorizationDecision:
        """
        Evaluate authorization request against ABAC policies.

        Args:
            jwt_claims: Decoded JWT claims from Cognito
            action: The action being requested (e.g., "view_vulnerabilities")
            resource_arn: ARN of the target resource
            request_context: Additional context (IP, time, device info)

        Returns:
            AuthorizationDecision with allow/deny and explanation
        """
        # Resolve all attributes
        attr_context = await self._resolve_attributes(
            jwt_claims, resource_arn, request_context
        )

        # Evaluate against OPA
        decision = await self._evaluate_opa(action, attr_context)

        # Audit log
        await self._audit_decision(action, attr_context, decision)

        return decision

    async def _resolve_attributes(
        self,
        jwt_claims: dict,
        resource_arn: str,
        request_context: dict,
    ) -> AttributeContext:
        """Resolve all attributes from their sources."""

        # Subject attributes from JWT + DynamoDB
        subject = await self._resolve_subject(jwt_claims)

        # Resource attributes from tags/metadata
        resource = await self._resolve_resource(resource_arn)

        # Context attributes from request
        context = self._build_context(request_context, jwt_claims)

        return AttributeContext(
            subject=subject,
            resource=resource,
            context=context,
            action="",  # Set by caller
        )

    async def _resolve_subject(self, jwt_claims: dict) -> SubjectAttributes:
        """Resolve subject attributes from JWT and DynamoDB."""

        user_id = jwt_claims["sub"]

        # Check cache
        cache_key = f"subject:{user_id}"
        if cache_key in self._attribute_cache:
            return self._attribute_cache[cache_key]

        # Get extended attributes from DynamoDB
        profile = await self.dynamodb.get_item(
            TableName="UserProfiles",
            Key={"user_id": {"S": user_id}},
        )

        subject = SubjectAttributes(
            user_id=user_id,
            tenant_id=jwt_claims.get("custom:tenant_id", profile.get("tenant_id")),
            roles=jwt_claims.get("cognito:groups", []),
            department=profile.get("department"),
            clearance_level=profile.get("clearance_level", "internal"),
            risk_score=float(profile.get("risk_score", 0.0)),
            organization=profile.get("organization", ""),
        )

        self._attribute_cache[cache_key] = subject
        return subject

    async def _resolve_resource(self, resource_arn: str) -> ResourceAttributes:
        """Resolve resource attributes from tags and metadata."""

        # Parse ARN to determine resource type
        resource_type, resource_id = self._parse_arn(resource_arn)

        # Get resource tags
        tags = await self._get_resource_tags(resource_arn)

        return ResourceAttributes(
            resource_type=resource_type,
            resource_id=resource_id,
            tenant_id=tags.get("tenant_id", ""),
            sensitivity=tags.get("sensitivity", "internal"),
            owner_id=tags.get("owner_id", ""),
            classification=tags.get("classification", ""),
            tags=tags,
            environment=tags.get("environment", "production"),
        )

    async def _evaluate_opa(
        self,
        action: str,
        attr_context: AttributeContext,
    ) -> AuthorizationDecision:
        """Evaluate policy against OPA."""

        input_data = {
            "action": action,
            "subject": attr_context.subject.__dict__,
            "resource": attr_context.resource.__dict__,
            "context": attr_context.context.__dict__,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.opa_url}/v1/data/aura/authz/allow",
                json={"input": input_data},
                timeout=1.0,  # Fast timeout for authz
            )

        result = response.json()
        allowed = result.get("result", False)

        # Get explanation if denied
        explanation = None
        if not allowed:
            explanation = await self._get_denial_reason(input_data)

        return AuthorizationDecision(
            allowed=allowed,
            explanation=explanation,
            evaluated_at=datetime.utcnow().isoformat(),
            policy_version=self._get_policy_version(),
        )
```

### API Integration

```python
# src/api/middleware/abac_middleware.py

from fastapi import Request, HTTPException
from functools import wraps

def require_abac(action: str, resource_resolver: Callable):
    """
    Decorator for ABAC-protected endpoints.

    Args:
        action: The action being performed
        resource_resolver: Function to extract resource ARN from request
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Get JWT claims from request state (set by auth middleware)
            jwt_claims = request.state.jwt_claims

            # Resolve resource ARN
            resource_arn = await resource_resolver(request, *args, **kwargs)

            # Build request context
            request_context = {
                "source_ip": request.client.host,
                "request_time": datetime.utcnow().isoformat(),
                "user_agent": request.headers.get("user-agent"),
                "device_trust": request.headers.get("x-device-trust", "unknown"),
            }

            # Evaluate authorization
            abac_service = request.app.state.abac_service
            decision = await abac_service.authorize(
                jwt_claims=jwt_claims,
                action=action,
                resource_arn=resource_arn,
                request_context=request_context,
            )

            if not decision.allowed:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "Access denied",
                        "reason": decision.explanation,
                        "action": action,
                    },
                )

            return await func(request, *args, **kwargs)

        return wrapper
    return decorator


# Usage example
@router.get("/vulnerabilities/{tenant_id}")
@require_abac(
    action="view_vulnerabilities",
    resource_resolver=lambda r, tenant_id: f"arn:aws:aura:::tenant/{tenant_id}/vulnerabilities",
)
async def get_vulnerabilities(
    request: Request,
    tenant_id: str,
    severity: Optional[str] = None,
):
    """Get vulnerabilities for a tenant (ABAC-protected)."""
    return await vulnerability_service.get_by_tenant(tenant_id, severity)


@router.post("/patches/{patch_id}/approve")
@require_abac(
    action="approve_patch",
    resource_resolver=lambda r, patch_id: f"arn:aws:aura:::patch/{patch_id}",
)
async def approve_patch(
    request: Request,
    patch_id: str,
    approval: PatchApproval,
):
    """Approve a patch (ABAC-protected, requires MFA for sensitive patches)."""
    return await patch_service.approve(patch_id, approval)
```

### Dashboard Integration

```typescript
// src/frontend/hooks/useABAC.ts

interface ABACContext {
  canPerform: (action: string, resourceArn: string) => Promise<boolean>;
  getVisibleTenants: () => Promise<Tenant[]>;
  getUserClearance: () => ClearanceLevel;
}

export const useABAC = (): ABACContext => {
  const { user } = useAuth();

  const canPerform = async (action: string, resourceArn: string): Promise<boolean> => {
    const response = await fetch('/api/v1/authz/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, resource_arn: resourceArn }),
    });
    const { allowed } = await response.json();
    return allowed;
  };

  const getVisibleTenants = async (): Promise<Tenant[]> => {
    // Returns only tenants the user can access
    const response = await fetch('/api/v1/tenants/accessible');
    return response.json();
  };

  const getUserClearance = (): ClearanceLevel => {
    return user?.clearance_level || 'internal';
  };

  return { canPerform, getVisibleTenants, getUserClearance };
};


// Component usage
const VulnerabilityDashboard: React.FC = () => {
  const { canPerform, getVisibleTenants } = useABAC();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [canApprove, setCanApprove] = useState(false);

  useEffect(() => {
    // Only show tenants user can access
    getVisibleTenants().then(setTenants);

    // Check if user can approve patches
    canPerform('approve_patch', 'arn:aws:aura:::patch/*').then(setCanApprove);
  }, []);

  return (
    <div>
      <TenantSelector tenants={tenants} />
      <VulnerabilityList />
      {canApprove && <PatchApprovalPanel />}
    </div>
  );
};
```

## Implementation

### Phase 1: Attribute Infrastructure (Week 1-2)

| Task | Deliverable |
|------|-------------|
| Extend Cognito custom attributes | `tenant_id`, `clearance_level` claims |
| Create UserProfiles DynamoDB table | Extended user attributes |
| Implement AttributeResolutionService | `_resolve_subject()`, `_resolve_resource()` |
| Add resource tagging standards | S3, DynamoDB, Neptune tag schemas |

### Phase 2: OPA Integration (Week 2-3)

| Task | Deliverable |
|------|-------------|
| Deploy OPA as EKS sidecar | Helm chart, ConfigMap for policies |
| Implement base ABAC policies | `tenant_isolation.rego`, `clearance.rego` |
| Create ABACAuthorizationService | `authorize()` method |
| Build policy testing framework | `conftest` integration tests |

### Phase 3: API Integration (Week 3-4)

| Task | Deliverable |
|------|-------------|
| Implement `@require_abac` decorator | FastAPI middleware |
| Migrate critical endpoints | Vulnerabilities, patches, deployments |
| Add authorization audit logging | CloudWatch + DynamoDB audit trail |
| Create authz check API | `/api/v1/authz/check` endpoint |

### Phase 4: Dashboard & UX (Week 4-5)

| Task | Deliverable |
|------|-------------|
| Implement `useABAC` hook | Frontend authorization checks |
| Add tenant selector component | Multi-tenant navigation |
| Build permission-aware UI | Conditional rendering based on ABAC |
| Create admin policy editor | Visual policy management (optional) |

### Phase 5: Advanced Features (Week 5-6)

| Task | Deliverable |
|------|-------------|
| Time-based policies | Business hours restrictions |
| Risk-adaptive access | Dynamic permissions based on risk score |
| Cross-tenant access workflow | Approval flow for platform admins |
| Policy analytics dashboard | Usage patterns, denial reasons |

## AWS Services

| Service | Purpose |
|---------|---------|
| **Amazon Cognito** | Subject attributes (JWT claims) |
| **DynamoDB** | Extended user attributes, audit trail |
| **EKS** | OPA sidecar deployment (if OPA chosen) |
| **S3/DynamoDB Tags** | Resource attributes |
| **CloudWatch** | Authorization metrics and logging |
| **Lambda@Edge** | Optional: Edge authorization for CDN |
| **API Gateway** | Lambda authorizer alternative |
| **AWS Verified Permissions** | Alternative to OPA (see evaluation below) |

## Policy Engine Evaluation: OPA vs AWS Verified Permissions

A key architectural decision is which policy engine to use for ABAC evaluation. Both options are viable; the choice depends on operational priorities.

### Comparison Matrix

| Criterion | OPA (Open Policy Agent) | AWS Verified Permissions |
|-----------|------------------------|--------------------------|
| **Policy Language** | Rego (Datalog-based, powerful but complex) | Cedar (purpose-built, simpler) |
| **Deployment Model** | Self-managed (EKS sidecar or service) | AWS-managed (serverless) |
| **Operational Burden** | High (cluster management, upgrades, scaling) | Low (fully managed) |
| **GovCloud Support** | Yes (self-deployed) | Yes (native AWS service) |
| **Cognito Integration** | Manual (policy must parse JWT) | Native (built-in identity source) |
| **Flexibility** | Very high (arbitrary logic) | Medium (designed for authz use cases) |
| **Learning Curve** | Steep (Rego is powerful but complex) | Moderate (Cedar is more intuitive) |
| **Cost** | Compute cost for OPA pods | ~$1/million authz requests |
| **Latency** | <5ms (sidecar) | <10ms (managed service) |
| **Audit Integration** | Manual (CloudWatch/custom) | Native (CloudTrail) |

### Recommendation

**Start with AWS Verified Permissions** for these reasons:

1. **Lower operational burden**: No OPA cluster to manage, upgrade, or scale
2. **Native Cognito integration**: Simplifies subject attribute resolution
3. **GovCloud compatibility**: First-party AWS service
4. **Audit trail**: Automatic CloudTrail logging
5. **Cedar is sufficient**: ABAC use cases don't require Rego's full power

**When to consider OPA instead:**
- Need complex policy logic (aggregations, external data lookups)
- Already have OPA expertise on the team
- Multi-cloud strategy requires vendor-neutral policy engine
- Edge cases where Cedar expressiveness is limiting

### Migration Path

If starting with Verified Permissions and later needing OPA:
1. Cedar policies can be translated to Rego (not automated, but straightforward)
2. Attribute resolution service is engine-agnostic
3. `@require_abac` decorator abstracts engine choice

### Updated Implementation (Verified Permissions)

If choosing AWS Verified Permissions, Phase 2 changes to:

```python
# src/services/authorization/verified_permissions_service.py

import boto3

class VerifiedPermissionsAuthorizationService:
    """ABAC using AWS Verified Permissions with Cedar policies."""

    def __init__(self, policy_store_id: str):
        self.client = boto3.client('verifiedpermissions')
        self.policy_store_id = policy_store_id

    async def authorize(
        self,
        jwt_claims: dict,
        action: str,
        resource_arn: str,
        request_context: dict,
    ) -> AuthorizationDecision:
        """Evaluate authorization using Verified Permissions."""

        response = self.client.is_authorized_with_token(
            policyStoreId=self.policy_store_id,
            identityToken=jwt_claims['raw_token'],  # Cognito JWT
            action={
                'actionType': 'Aura::Action',
                'actionId': action,
            },
            resource={
                'entityType': 'Aura::Resource',
                'entityId': resource_arn,
            },
            context={
                'contextMap': {
                    'sourceIp': {'string': request_context['source_ip']},
                    'requestTime': {'string': request_context['request_time']},
                    'deviceTrust': {'string': request_context.get('device_trust', 'unknown')},
                }
            },
        )

        return AuthorizationDecision(
            allowed=response['decision'] == 'ALLOW',
            explanation=response.get('errors', []),
            evaluated_at=datetime.utcnow().isoformat(),
            policy_version=self.policy_store_id,
        )
```

**Cedar Policy Example:**

```cedar
// Tenant isolation policy
permit (
    principal,
    action,
    resource
)
when {
    principal.tenant_id == resource.tenant_id
};

// Clearance level policy
permit (
    principal,
    action in [Aura::Action::"view_confidential"],
    resource
)
when {
    principal.clearance_level >= resource.sensitivity_level &&
    context.mfa_verified == true
};
```

## Security Considerations

### Attribute Integrity

- JWT claims are signed by Cognito (tamper-proof)
- DynamoDB attributes require IAM authentication
- Resource tags require IAM write permissions to modify
- Cache invalidation on attribute changes

### Performance

- Attribute caching with 5-minute TTL
- OPA decision caching for repeated requests
- P99 latency target: <10ms for authorization decisions
- Fallback to RBAC if OPA unavailable

### Audit Trail

All authorization decisions logged with:
- Subject attributes (who)
- Resource attributes (what)
- Context attributes (when/where/how)
- Decision and policy version
- Denial reasons (for troubleshooting)

## Consequences

### Positive

- **True multi-tenancy**: Users only see their tenant's data
- **Fine-grained control**: Permissions at resource level, not just role level
- **Context-awareness**: Can enforce MFA, time, location requirements
- **Compliance**: Meets NIST 800-53 AC-3 (Access Enforcement) requirements
- **Auditability**: Complete decision log for compliance audits

### Negative

- **Complexity**: More moving parts than simple RBAC
- **Performance overhead**: Additional attribute resolution and policy evaluation
- **Policy maintenance**: Rego policies require specialized knowledge
- **Migration effort**: Existing endpoints need ABAC decorators

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| OPA unavailability | Graceful fallback to RBAC with alert |
| Attribute staleness | TTL-based cache, event-driven invalidation |
| Policy errors | Extensive testing, dry-run mode, gradual rollout |
| Performance degradation | Caching, async attribute resolution, circuit breaker |

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Authorization latency P99 | <10ms | CloudWatch metrics on authz endpoint |
| Tenant isolation violations | 0 | Audit log analysis for cross-tenant access |
| Policy evaluation success rate | >99.9% | Successful authz decisions / total requests |
| Attribute resolution cache hit rate | >80% | Cache hits / total resolutions |
| Fallback to RBAC rate | <0.1% | RBAC fallback invocations / total requests |

## Related ADRs

- **ADR-066**: Agent Capability Governance (inspiration for attribute model)
- **ADR-070**: Policy-as-Code (shared GitOps principles)
- **ADR-072**: ML-Based Anomaly Detection (risk_score attribute source)

## References

- [MI9: Runtime Governance Framework for Agentic AI](https://arxiv.org/abs/2508.03858) - Continuous Authorization Monitoring (CAM) for context-aware dynamic permissions
- [NIST SP 800-162: Guide to ABAC](https://csrc.nist.gov/publications/detail/sp/800-162/final)
- [AWS Verified Permissions](https://docs.aws.amazon.com/verifiedpermissions/latest/userguide/what-is-avp.html)
- [Cedar Policy Language](https://docs.cedarpolicy.com/)
- [Open Policy Agent](https://www.openpolicyagent.org/)
- [AWS IAM ABAC](https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction_attribute-based-access-control.html)
- [Rego Policy Language](https://www.openpolicyagent.org/docs/latest/policy-language/)
- [Cognito Custom Attributes](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-attributes.html)
