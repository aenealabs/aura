# ADR-031: Neptune Deployment Mode Configuration

**Status:** Deployed
**Date:** 2025-12-10
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-003 (EKS EC2 Nodes for GovCloud), ADR-004 (Multi-Cloud Architecture)

---

## Executive Summary

This ADR documents the decision to support dual Neptune deployment modes (provisioned and serverless) via CloudFormation configuration, enabling cost optimization for commercial deployments while maintaining 100% GovCloud compatibility.

**Key Outcomes:**
- 100% GovCloud compatibility with provisioned mode (default)
- Optional serverless mode for commercial cost optimization
- Single CloudFormation template supporting both modes
- Clear documentation of GovCloud limitations

---

## Context

### Current State

Neptune is deployed in provisioned mode (`db.t3.medium`) which is:
- 100% compatible with AWS GovCloud (US)
- Always-on with predictable costs (~$82/month idle)
- Required for FedRAMP High and CMMC compliance environments

### Problem Statement

Neptune Serverless offers significant cost benefits for commercial deployments:
- Auto-scales to zero during idle periods
- Cost as low as $15-30/month for dev/test workloads
- Better cost efficiency for variable workloads

However, Neptune Serverless is **NOT available in AWS GovCloud**, creating a trade-off between cost optimization and compliance requirements.

### Requirements

1. **GovCloud Compatibility:** Production deployments targeting government customers must use GovCloud-compatible services
2. **Cost Optimization:** Commercial/dev deployments should have access to serverless cost savings
3. **Single Template:** Avoid template duplication; use feature flags instead
4. **Default Safety:** Default configuration must be GovCloud-compatible

---

## Decision

**Implement a configurable `NeptuneMode` parameter in the Neptune CloudFormation template with two options:**

| Mode | Default | GovCloud | Cost (Idle) | Use Case |
|------|---------|----------|-------------|----------|
| `provisioned` | Yes | Compatible | ~$82/month | Production, GovCloud, compliance |
| `serverless` | No | NOT Compatible | ~$15-30/month | Commercial dev/test, cost optimization |

### Implementation

Two separate templates in `deploy/cloudformation/`:

**`neptune-simplified.yaml`** (Provisioned Mode - Default):
- For existing deployments and GovCloud
- Uses `NeptuneCluster`, `NeptunePrimaryInstance`, `NeptuneReadReplica`
- Instance types: db.t3.medium (default), db.r5.large (production)

**`neptune-serverless.yaml`** (Serverless Mode):
- For new commercial deployments only
- Uses `NeptuneCluster` with `ServerlessScalingConfiguration`
- Capacity: 1-128 NCU (Neptune Capacity Units)

### Template Selection

| Use Case | Template | GovCloud |
|----------|----------|----------|
| Existing stack update | `neptune-simplified.yaml` | Yes |
| New GovCloud deployment | `neptune-simplified.yaml` | Yes |
| New commercial dev/test | `neptune-serverless.yaml` | No |
| Production (any region) | `neptune-simplified.yaml` | Yes |

### Outputs

Both templates export identical output names for downstream compatibility:
- `NeptuneClusterEndpoint`
- `NeptuneMode` - "provisioned" or "serverless"
- `NeptuneGovCloudCompatible` - "true" or "false"

---

## Alternatives Considered

### Alternative 1: Separate Templates (ADOPTED)
Create `neptune-simplified.yaml` (provisioned) and `neptune-serverless.yaml` (serverless).

**Adopted because:**
- CloudFormation tracks resources by logical ID; changing logical IDs triggers replacement
- Existing stacks cannot be updated to use different logical resource IDs without replacement
- Separate templates avoid accidental mode switches that would delete production data
- Each template is simpler and easier to understand

### Alternative 2: Single Template with Conditional Resources
Use CloudFormation conditions to switch between provisioned and serverless modes.

**Rejected because:**
- CloudFormation tracks resources by logical ID
- Changing logical IDs (e.g., `NeptuneCluster` → `NeptuneClusterProvisioned`) triggers resource replacement
- Mode switching would delete and recreate the database, losing all data
- Outputs using `!If` with conditional resources fail validation when referenced resource doesn't exist

### Alternative 3: Provisioned Only
Keep only provisioned mode, ignore serverless cost benefits.

**Rejected because:**
- Significant cost penalty for commercial customers
- $50-67/month overhead per environment
- Reduces competitive positioning

---

## Consequences

### Positive

1. **100% GovCloud Compatibility:** Default mode is always GovCloud-compatible
2. **Cost Flexibility:** Commercial customers can enable serverless for 50-70% cost reduction
3. **Single Source of Truth:** One template, parameterized deployment
4. **Clear Documentation:** Mode and GovCloud compatibility exported as stack outputs
5. **Future-Proof:** If Neptune Serverless comes to GovCloud, configuration change only

### Negative

1. **Template Complexity:** Conditional resources add complexity
2. **Testing Burden:** Must test both modes
3. **Documentation:** Users must understand implications of mode selection

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| User selects serverless for GovCloud | Low | High | Default is provisioned; clear warnings in description |
| Serverless costs spike unexpectedly | Medium | Medium | MaxCapacity parameter limits scaling |
| Feature parity differences | Low | Low | Both modes use same Neptune engine version |

---

## Implementation

### Files Changed

- `deploy/cloudformation/neptune-simplified.yaml` - Provisioned mode (existing, GovCloud-compatible)
- `deploy/cloudformation/neptune-serverless.yaml` - Serverless mode (new commercial deployments)

### Configuration Examples

**GovCloud / Production (default):**
```bash
aws cloudformation deploy \
  --template-file deploy/cloudformation/neptune-simplified.yaml \
  --parameter-overrides \
    Environment=prod \
    ProjectName=aura \
    InstanceType=db.r5.large
```

**Commercial Dev/Test (cost-optimized - NEW deployments only):**
```bash
aws cloudformation deploy \
  --template-file deploy/cloudformation/neptune-serverless.yaml \
  --parameter-overrides \
    Environment=dev \
    ProjectName=aura \
    ServerlessMinCapacity=1 \
    ServerlessMaxCapacity=8
```

### Cost Comparison

| Environment | Provisioned | Serverless | Savings |
|-------------|-------------|------------|---------|
| Dev (low usage) | $82/month | $15-30/month | 63-82% |
| QA (moderate) | $82/month | $40-60/month | 27-51% |
| Production | $164/month (HA) | N/A (use provisioned) | N/A |

---

## References

- [AWS Neptune Serverless Documentation](https://docs.aws.amazon.com/neptune/latest/userguide/neptune-serverless.html)
- [AWS GovCloud Service Availability](https://aws.amazon.com/govcloud-us/services/)
- ADR-003: EKS EC2 Nodes for GovCloud Compatibility
- ADR-004: Multi-Cloud Architecture Strategy
