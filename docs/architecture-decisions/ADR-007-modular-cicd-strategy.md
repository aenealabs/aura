# ADR-007: Modular CI/CD with Layer-Based Deployment

**Status:** Deployed
**Date:** 2025-11-11 (Updated: 2025-12-14)
**Decision Makers:** Project Aura Team

## Context

Project Aura's infrastructure consists of multiple CloudFormation stacks across different domains:
- Foundation (VPC, Security Groups, IAM)
- Data (Neptune, OpenSearch, DynamoDB, S3)
- Compute (EKS, Node Groups)
- Application (Bedrock infrastructure)
- Observability (Secrets, Monitoring, Cost Alerts)

We needed to decide how to structure CI/CD for infrastructure deployment:
1. **Monolithic** - Single CodeBuild project deploying all stacks
2. **Per-Stack** - Separate CodeBuild project per CloudFormation stack
3. **Layer-Based** - Group stacks by domain with smart change detection

This decision impacts:
- Deployment speed (all stacks vs. changed only)
- Team scalability (single vs. multiple team ownership)
- CI/CD complexity and maintenance
- Cost of unnecessary deployments

## Decision

We chose a **Modular Layer-Based CI/CD** approach. The architecture has evolved through two phases and is now fully operational.

**Phase 2 (Current - December 2025): Multiple Projects per Layer**
- 14 CodeBuild projects deployed (8 parent layers + 6 sub-layers)
- 15 buildspecs managing all 58 CloudFormation templates
- 48 stacks deployed to dev environment
- ECR credential helper used across all buildspecs (no docker login warnings)
- Foundation role (`aura-foundation-codebuild-role-{environment}`) shared across CodeBuild projects due to IAM eventual consistency issues

**Phase 1 (Initial): Single Project with Smart Change Detection** (Archived)
- Single CodeBuild project: `aura-infra-deploy-dev`
- Python script (`detect_changes.py`) analyzed git diff
- Archived to `archive/legacy/buildspecs/buildspec-modular.yml`

**Current Layer Structure:**

| Layer | Sub-Layer | Buildspec | Stacks | Dependencies |
|-------|-----------|-----------|--------|--------------|
| 1 | Foundation | buildspec-foundation.yml | networking, security, iam, kms, vpc-endpoints, ecr-base-images | None |
| 1 | Network Services | buildspec-network-services.yml | network-services (dnsmasq) | Foundation |
| 2 | Data | buildspec-data.yml | neptune, opensearch, dynamodb, s3 | Foundation |
| 3 | Compute | buildspec-compute.yml | eks, acm-certificate, alb-controller | Foundation |
| 4 | Application | buildspec-application.yml | ecr-api, bedrock, cognito, guardrails, irsa, ecr-frontend | Foundation, Data, Compute |
| 4 | Docker Build | buildspec-docker-build.yml | Dedicated Docker/Podman builds | Foundation |
| 5 | Observability | buildspec-observability.yml | secrets, monitoring, cost-alerts, realtime-monitoring, disaster-recovery, otel-collector | Foundation, Data |
| 6 | Serverless | buildspec-serverless.yml | threat-intel, hitl-scheduler, hitl-callback, a2a, orchestrator-dispatcher, dns-blocklist, chat-assistant | Foundation, Data, Compute |
| 6 | Chat Assistant | buildspec-chat-assistant.yml | chat-assistant | Serverless |
| 6 | Runbook Agent | buildspec-runbook-agent.yml | runbook-agent | Serverless |
| 6 | Incident Response | buildspec-incident-response.yml | incident-response, incident-investigation-workflow | Serverless |
| 6 | Coordinator | buildspec-coordinator.yml | CI/CD deployment coordinator | Serverless |
| 7 | Sandbox | buildspec-sandbox.yml | sandbox, hitl-workflow | Foundation, Data, Compute, Serverless |
| 8 | Security | buildspec-security.yml | config-compliance, guardduty, drift-detection, red-team | Foundation, Data |

## Alternatives Considered

### Alternative 1: Monolithic Deployment

Single buildspec deploys all stacks on every push.

**Pros:**
- Simplest to implement
- No change detection logic needed
- Guaranteed consistency

**Cons:**
- Slow (deploys unchanged stacks)
- Wasteful (unnecessary CloudFormation API calls)
- Long feedback loop
- Risk of timeouts (>60 minutes for all stacks)

### Alternative 2: Per-Stack CodeBuild Projects

Separate CodeBuild project for each CloudFormation stack.

**Pros:**
- Maximum granularity
- Each stack deployed independently
- Clear ownership

**Cons:**
- 14+ CodeBuild projects to manage
- Complex dependency orchestration
- High maintenance overhead
- Overkill for small team

### Alternative 3: AWS CDK Pipelines

Use CDK Pipelines for self-mutating deployment.

**Pros:**
- CDK-native approach
- Self-mutating pipeline
- Built-in wave support

**Cons:**
- Requires migrating from CloudFormation to CDK
- Significant refactoring effort
- Team expertise in CloudFormation, not CDK
- Lock-in to CDK patterns

### Alternative 4: External CI/CD (GitHub Actions)

Use GitHub Actions instead of CodeBuild.

**Pros:**
- Rich ecosystem
- Familiar to developers
- Free for public repos

**Cons:**
- IAM credential management complexity
- Less integrated with AWS services
- Network connectivity to private VPC resources
- Security concerns for GovCloud

## Consequences

### Positive

1. **Fast Deployments**
   - Only changed layers deploy (~5-10 min vs 60+ min)
   - Immediate feedback on infrastructure changes
   - Reduced CloudFormation API usage

2. **Cost Efficiency**
   - Fewer CodeBuild minutes consumed
   - No unnecessary stack updates
   - Lower CloudFormation drift detection costs

3. **Team Scalability**
   - Phase 2 enables team-owned layers
   - Clear boundaries for infrastructure ownership
   - Parallel deployments possible

4. **Safety**
   - Dependencies prevent invalid deployment order
   - Single source of truth (CodeBuild is authoritative)
   - Easy rollback per layer

5. **Audit Trail**
   - CloudWatch Logs per layer
   - SNS notifications for build status
   - Clear attribution of changes

### Negative

1. **Complexity**
   - Change detection script to maintain
   - Layer mapping must stay current
   - Debug complexity for dependency issues

2. **Initial Setup**
   - More complex than monolithic approach
   - Requires understanding of layer dependencies

3. **Edge Cases**
   - Cross-layer changes require careful handling
   - Deleted files must be detected correctly

### Mitigation

- Comprehensive documentation in `deploy/MODULAR_DEPLOYMENT.md`
- Test change detection locally before push
- Force-all option for full deployment when needed
- CloudWatch alarms for build failures

## Implementation Notes (December 2025)

### ECR Credential Helper

All buildspecs use the ECR credential helper instead of explicit `docker login` commands to eliminate password storage warnings:

```bash
# Configure ECR credential helper (install phase of each buildspec)
./deploy/scripts/configure-ecr-credential-helper.sh
```

### IAM Role Strategy

Due to IAM eventual consistency issues discovered during ADR-035 implementation, all CodeBuild projects use the shared Foundation role (`aura-foundation-codebuild-role-{environment}`) instead of layer-specific roles. This ensures CodeConnections (GitHub) access works immediately after stack creation.

### Buildspec Size Limits

Maximum buildspec size: 600 lines. The `buildspec-application.yml` is at 599 lines. If additional deployments are needed, create a new sub-layer buildspec (see ADR-035 for pattern).

## Phase 2 Migration Complete

Phase 2 migration was completed in Q4 2025. Key changes from Phase 1:
- Separate CodeBuild projects per layer (14 total)
- Layer-specific buildspecs (15 total)
- GitHub CodeConnections triggers per layer
- Parallel deployment capability
- Sub-layer pattern for fine-grained control

## References

- `AWS_WELL_ARCHITECTED_CICD_ASSESSMENT.md` - **Comprehensive Well-Architected analysis** (1,458 lines) comparing monolithic vs modular CI/CD with detailed scoring across all 7 pillars
- `deploy/MODULAR_DEPLOYMENT.md` - Complete modular deployment guide
- `deploy/buildspecs/` - All 15 layer-specific buildspecs
- `deploy/scripts/configure-ecr-credential-helper.sh` - ECR credential helper configuration
- `deploy/cloudformation/codebuild-*.yaml` - CodeBuild project definitions (14 templates)
- `archive/legacy/buildspecs/buildspec-modular.yml` - Archived Phase 1 orchestrator buildspec
- ADR-035: Dedicated Docker-Podman Build CodeBuild Project (sub-layer pattern)
- ADR-036: Multi-Platform Container Build Strategy (build targets)
