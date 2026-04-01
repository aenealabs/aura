# ADR-002: VPC Endpoints over NAT Gateways for AWS Service Connectivity

**Status:** Deployed
**Date:** 2025-11-17
**Decision Makers:** Project Aura Team

## Context

Project Aura requires private connectivity from application subnets to AWS services (Bedrock, Neptune, OpenSearch, S3, DynamoDB). We needed to choose between:

1. **NAT Gateways** - Provide general internet access (including AWS services)
2. **VPC Endpoints** - Private connectivity to specific AWS services
3. **Hybrid Approach** - Combination of both

This decision impacts:
- Monthly infrastructure costs ($66-$200/month difference)
- Security posture (data never leaves AWS network with VPC endpoints)
- GovCloud migration readiness
- Operational complexity

## Decision

We chose a **Hybrid VPC Endpoint Strategy**:

**Commercial Cloud (Dev/QA):**
- Use VPC Endpoints for all AWS services (Bedrock, Neptune, OpenSearch, S3, DynamoDB)
- NO NAT Gateways (delete existing NAT Gateways to save $66/month)
- Add NAT Gateway only if internet access to non-AWS services is required

**GovCloud (Production):**
- Use VPC Endpoints exclusively (mandatory for CMMC Level 3 compliance)
- Zero internet egress from private subnets
- All traffic stays within AWS network

## Alternatives Considered

### Alternative 1: NAT Gateways Only

Deploy 2 NAT Gateways (multi-AZ HA) for all outbound connectivity.

**Pros:**
- Simple architecture
- General internet access for any external dependency
- Familiar operational model

**Cons:**
- Higher monthly cost ($86-166/month vs $35-50/month with VPC Endpoints)
- Data exits VPC to internet, then back to AWS (security concern)
- NOT compliant with CMMC Level 3 (data crosses internet boundary)
- Higher latency (5-15ms additional)
- Larger attack surface (potential data exfiltration point)

### Alternative 2: VPC Endpoints Only

Use VPC Endpoints for all AWS services with no NAT Gateways.

**Pros:**
- Lowest cost (free gateway endpoints for S3/DynamoDB)
- Maximum security (traffic never leaves AWS network)
- CMMC Level 3, SOX, NIST 800-53 compliant
- Lower latency (1-3ms vs 5-15ms)

**Cons:**
- No internet access for non-AWS dependencies
- Requires planning for each AWS service needed

**This is our chosen approach for GovCloud production.**

## Consequences

### Positive

1. **Cost Savings**
   - Dev: $50-100/month savings (42-70% reduction)
   - Prod: $100-175/month savings (62% reduction)
   - Annual savings: $612-1,392 (dev), $1,200-2,100 (prod)

2. **Security Improvement**
   - Traffic never leaves AWS network (data path stays private)
   - Reduces attack surface (no internet egress point)
   - Enhanced logging (VPC Flow Logs + CloudTrail API logs)
   - Meets CMMC Level 3 controls SC.3.177, SC.3.191

3. **Compliance**
   - CMMC Level 3: Compliant (no internet egress required)
   - SOX: Compliant (reduced audit complexity)
   - NIST 800-53: Meets AC-4, SC-7, SC-8 controls
   - FedRAMP High: AWS PrivateLink is authorized

4. **Performance**
   - 5-10ms latency reduction (fewer network hops)
   - More consistent performance (no internet routing variability)
   - 100 Gbps throughput on AWS backbone

5. **Operational Simplicity**
   - Endpoints are AWS-managed (auto-scaling, auto-healing)
   - No health monitoring needed for endpoints
   - Simple deletion/recreation (1 command)

### Negative

1. **No Internet Access**
   - Cannot access non-AWS services from private subnets
   - Requires NAT Gateway if external API calls needed later

2. **Planning Required**
   - Must create endpoint for each AWS service used
   - Some services require Interface Endpoints (cost: $7.30/month/AZ)

### Mitigation

The negative consequences are acceptable because:
- All Project Aura services use AWS-native dependencies
- NAT Gateway can be added later if needed (takes ~5 minutes)
- Gateway endpoints (S3, DynamoDB) are free
- Interface endpoint costs are predictable and fixed

## Service-Specific Notes

| Service | Endpoint Type | Cost | Notes |
|---------|---------------|------|-------|
| Amazon S3 | Gateway | **FREE** | Route table integration, required for ECR layer downloads |
| Amazon DynamoDB | Gateway | **FREE** | Route table integration, HITL approval tables |
| Amazon Bedrock | Interface | $7.30/AZ/mo | PrivateLink (FedRAMP High) |
| Amazon OpenSearch | Interface | $7.30/AZ/mo | Available in GovCloud (Mar 2025) |
| Amazon Neptune | N/A | **$0** | VPC-native (already private) |
| Amazon ECR (API) | Interface | $7.30/AZ/mo | Required for ECS Fargate tasks in private subnets |
| Amazon ECR (DKR) | Interface | $7.30/AZ/mo | Docker registry operations (push/pull) |
| CloudWatch Logs | Interface | $7.30/AZ/mo | ECS task logging from private subnets |

**Neptune Note:** Neptune clusters are deployed directly inside the VPC and do not require VPC Endpoints or NAT Gateways.

**ECR Note (Added Dec 2025):** ECS Fargate tasks running in private subnets require both ECR endpoints (ecr.api and ecr.dkr) plus the S3 Gateway Endpoint for pulling container images. Without these endpoints, Fargate tasks will fail with `ResourceInitializationError: unable to pull secrets or registry auth`.

## Implementation

VPC Endpoints are deployed via CloudFormation as part of the Foundation layer:

- **Template:** `deploy/cloudformation/vpc-endpoints.yaml`
- **Buildspec:** `deploy/buildspecs/buildspec-foundation.yml`
- **CodeBuild:** `aura-foundation-deploy-dev`

## References

- `docs/ARCHITECTURE_DECISION_VPC_CONNECTIVITY.md` - Full analysis and migration plan
- `deploy/cloudformation/vpc-endpoints.yaml` - VPC Endpoint CloudFormation template
- `deploy/cloudformation/networking.yaml` - VPC and subnet configurations
- `docs/cloud-strategy/GOVCLOUD_READINESS_TRACKER.md` - GovCloud compliance tracking
