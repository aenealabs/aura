# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) for Project Aura. ADRs document significant architectural decisions made during development, capturing the context, rationale, and trade-offs considered.

## What is an ADR?

An Architecture Decision Record is a short document that captures an important architectural decision along with its context and consequences. ADRs help future developers understand:

- **Why** a decision was made (not just what was built)
- **What alternatives** were considered
- **What trade-offs** were accepted
- **When** the decision was made

## ADR Status Lifecycle

| Status | Definition | Criteria |
|--------|------------|----------|
| **Draft** | Being written, not ready for review | Author still editing; incomplete sections |
| **Proposed** | Ready for review, awaiting decision | Complete ADR submitted for stakeholder review |
| **Rejected** | Reviewed and not accepted | Decision made not to proceed; reason documented |
| **Accepted** | Decision approved, implementation pending | Stakeholders agreed; work not yet started |
| **In Progress** | Actively being implemented | Work started but not complete |
| **Implemented** | Code/config complete, merged to main | All code merged; tests passing |
| **Deployed** | Live in dev/staging environment | CloudFormation stacks created; services running |
| **Production** | Live in production environment | Deployed to prod (GovCloud when applicable) |
| **Deprecated** | Being phased out | Still works but no longer recommended |
| **Superseded** | Replaced by another ADR | Specify: "Superseded by ADR-XXX" |

### Status Flow

```
Draft → Proposed → Accepted → In Progress → Implemented → Deployed → Production
                ↓
            Rejected

Any status → Deprecated → Superseded
```

## ADR Format

Each ADR follows this structure:

```markdown
# ADR-NNN: Title

**Status:** Draft | Proposed | Rejected | Accepted | In Progress | Implemented | Deployed | Production | Deprecated | Superseded by ADR-XXX
**Date:** YYYY-MM-DD
**Decision Makers:** Team/Individual

## Context
What situation or problem prompted this decision?

## Decision
What was decided?

## Alternatives Considered
What other options were evaluated?

## Consequences
What are the trade-offs? Pros and cons?

## References
Related documents, issues, or discussions.
```

## Index of ADRs

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-001](ADR-001-dynamodb-separate-tables.md) | Separate DynamoDB Tables for Job Types | Deployed | 2025-11-28 |
| [ADR-002](ADR-002-vpc-endpoints-strategy.md) | VPC Endpoints over NAT Gateways | Deployed | 2025-11-17 |
| [ADR-003](ADR-003-eks-ec2-nodes-for-govcloud.md) | EKS EC2 Managed Node Groups for GovCloud | Deployed | 2025-11-17 |
| [ADR-004](ADR-004-multi-cloud-architecture.md) | Cloud Abstraction Layer for Multi-Cloud | Deployed | 2025-12-16 |
| [ADR-005](ADR-005-hitl-sandbox-architecture.md) | HITL Sandbox Testing for Autonomous Remediation | Deployed | 2025-11-28 |
| [ADR-006](ADR-006-three-tier-dnsmasq-integration.md) | Three-Tier dnsmasq Integration | Deployed | 2025-11-12 |
| [ADR-007](ADR-007-modular-cicd-strategy.md) | Modular CI/CD with Layer-Based Deployment | Deployed | 2025-11-11 |
| [ADR-008](ADR-008-bedrock-llm-cost-controls.md) | Comprehensive Cost Controls for Bedrock LLM | Deployed | 2025-11-28 |
| [ADR-009](ADR-009-drift-protection-dual-layer.md) | Dual-Layer Drift Protection for Compliance | Deployed | 2025-11-24 |
| [ADR-010](ADR-010-autonomous-adr-generation-pipeline.md) | Autonomous ADR Generation Pipeline | Deployed | 2025-12-14 |
| [ADR-011](ADR-011-vpc-access-via-eks-deployment.md) | VPC Access via EKS Deployment | Deployed | 2025-11-29 |
| [ADR-012](ADR-012-opensearch-iam-master-user.md) | OpenSearch IAM Master User Authentication | Deployed | 2025-11-29 |
| [ADR-013](ADR-013-service-adapter-factory-pattern.md) | Service Adapter and Factory Pattern | Deployed | 2025-12-01 |
| [ADR-014](ADR-014-llm-enhanced-agent-search-pattern.md) | LLM-Enhanced Agent Search Pattern | Deployed | 2025-12-01 |
| [ADR-015](ADR-015-tiered-llm-model-strategy.md) | Tiered LLM Model Strategy | Deployed | 2025-12-01 |
| [ADR-016](ADR-016-hitl-auto-escalation-strategy.md) | HITL Approval Auto-Escalation Strategy | Deployed | 2025-12-02 |
| [ADR-017](ADR-017-dynamic-sandbox-resource-allocation.md) | Dynamic Sandbox Resource Allocation | Deployed | 2025-12-02 |
| [ADR-018](ADR-018-meta-orchestrator-dynamic-agent-spawning.md) | Meta-Orchestrator with Dynamic Agent Spawning | Deployed | 2025-12-02 |
| [ADR-019](ADR-019-market-intelligence-agent.md) | Market Intelligence Agent | Deployed | 2025-12-02 |
| [ADR-020](ADR-020-private-ecr-base-images.md) | Private ECR Base Images for Controlled Supply Chain | Deployed | 2025-12-04 |
| [ADR-021](ADR-021-guardrails-cognitive-architecture.md) | Guardrails Cognitive Architecture | Deployed | 2025-12-04 |
| [ADR-022](ADR-022-gitops-kubernetes-deployment.md) | GitOps for Kubernetes Deployment with ArgoCD | Deployed | 2025-12-04 |
| [ADR-023](ADR-023-agentcore-gateway-integration.md) | AgentCore Gateway Integration | Deployed | 2025-12-04 |
| [ADR-024](ADR-024-titan-neural-memory.md) | Titan Neural Memory Architecture | Deployed | 2025-12-16 |
| [ADR-025](ADR-025-runtime-incident-agent.md) | Runtime Incident Agent | Deployed | 2025-12-05 |
| [ADR-026](ADR-026-bootstrap-once-update-forever.md) | Bootstrap Once, Update Forever Pattern | Deployed | 2025-12-06 |
| [ADR-027](ADR-027-security-group-management-pattern.md) | Security Group Management Pattern | Deployed | 2025-12-06 |
| [ADR-028](ADR-028-foundry-capability-adoption.md) | Foundry Capability Adoption | Deployed | 2025-12-07 |
| [ADR-029](ADR-029-agent-optimization-roadmap.md) | Agent Optimization Roadmap (v2.1 - Phases 1.3, 2.2, 2.3 enabled) | Deployed | 2025-12-16 |
| [ADR-030](ADR-030-chat-assistant-architecture.md) | Chat Assistant Architecture | Deployed | 2025-12-08 |
| [ADR-031](ADR-031-neptune-deployment-mode.md) | Neptune Deployment Mode Configuration | Deployed | 2025-12-10 |
| [ADR-032](ADR-032-configurable-autonomy-framework.md) | Configurable Autonomy Framework | Deployed | 2025-12-10 |
| [ADR-033](ADR-033-runbook-agent.md) | Runbook Agent for Automated Incident Documentation | Deployed | 2025-12-11 |
| [ADR-034](ADR-034-context-engineering-implementation.md) | Context Engineering Implementation Plan | Deployed | 2025-12-14 |
| [ADR-035](ADR-035-dedicated-docker-build-project.md) | Dedicated Docker-Podman Build CodeBuild Project | Deployed | 2025-12-14 |
| [ADR-036](ADR-036-multi-platform-container-builds.md) | Multi-Platform Container Build Strategy | Deployed | 2025-12-13 |
| [ADR-037](ADR-037-aws-agent-capability-replication.md) | AWS Agent Capability Replication | Deployed | 2025-12-16 |
| [ADR-038](ADR-038-codebuild-caching-optimization.md) | CodeBuild Caching Optimization Strategy | Deployed | 2025-12-14 |
| [ADR-039](ADR-039-self-service-test-environments.md) | Self-Service Test Environment Provisioning | Deployed | 2025-12-15 |
| [ADR-040](ADR-040-configurable-compliance-settings.md) | Configurable Compliance Settings | Deployed | 2025-12-16 |
| [ADR-041](ADR-041-aws-required-wildcards-defense-in-depth.md) | AWS-Required Wildcards with Defense-in-Depth | Accepted | 2025-12-16 |
| [ADR-042](ADR-042-real-time-agent-intervention.md) | Real-Time Agent Intervention Architecture | Deployed | 2025-12-17 |
| [ADR-043](ADR-043-repository-onboarding-wizard.md) | Repository Onboarding Wizard with OAuth | Deployed | 2025-12-18 |
| [ADR-044](ADR-044-enhanced-node-detail-panel.md) | Enhanced Node Detail Panel for GraphRAG Explorer | Deployed | 2025-12-19 |
| [ADR-045](ADR-045-external-documentation-links.md) | External Documentation Links for Code Navigation | Deployed | 2025-12-20 |
| [ADR-046](ADR-046-support-ticketing-connectors.md) | Support Ticketing Connector Framework | Deployed | 2025-12-21 |
| [ADR-047](ADR-047-customer-onboarding-features.md) | Customer Onboarding Features | Deployed | 2025-12-22 |
| [ADR-048](ADR-048-developer-tools-data-platform-integrations.md) | Developer Tools & Data Platform Integrations | Deployed | 2025-12-23 |
| [ADR-049](ADR-049-self-hosted-deployment-strategy.md) | Self-Hosted Deployment Strategy | Deployed | 2025-12-28 |
| [ADR-050](ADR-050-self-play-swe-rl-integration.md) | Self-Play SWE-RL Integration | Deployed | 2026-01-02 |
| [ADR-051](ADR-051-recursive-context-and-embedding-prediction.md) | Recursive Context Scaling & Embedding Prediction | Deployed | 2026-01-04 |
| [ADR-052](ADR-052-ai-alignment-principles.md) | AI Alignment Principles & Human-Machine Collaboration | Deployed | 2026-01-04 |
| [ADR-053](ADR-053-enterprise-security-integrations.md) | Enterprise Security Integrations (Zscaler, Saviynt, AuditBoard) | Deployed | 2026-01-06 |
| [ADR-054](ADR-054-multi-idp-authentication.md) | Multi-IdP Authentication | Deployed | 2026-01-06 |
| [ADR-055](ADR-055-agent-scheduling-view.md) | Agent Scheduling View & Job Queue Management | Deployed | 2026-01-06 |
| [ADR-056](ADR-056-documentation-agent.md) | Documentation Agent for Architecture Discovery | Deployed | 2026-01-07 |
| [ADR-057](ADR-057-public-documentation-portal.md) | Public Documentation Portal | Deployed | 2026-01-08 |
| [ADR-058](ADR-058-eks-multi-node-group-architecture.md) | EKS Multi-Node Group Architecture | Deployed | 2026-01-10 |
| [ADR-059](ADR-059-aws-organization-account-restructure.md) | AWS Organization Account Restructure | Accepted | 2026-01-10 |

### Reference Documents (Not ADRs)

The following documents contain valuable information that is referenced from ADRs but do not themselves require formal ADR format:

- `docs/deployment/GITHUB_ACTIONS_SETUP.md` - Referenced from ADR-007
- `docs/cloud-strategy/GOVCLOUD_READINESS_TRACKER.md` - Referenced from ADR-002, ADR-003
- `docs/COST_ANALYSIS_DEV_ENVIRONMENT.md` - Referenced from multiple ADRs
- `docs/BEDROCK_SETUP_SUMMARY.md` - Referenced from ADR-008

## When to Write an ADR

Create an ADR when:

- Choosing between multiple valid architectural approaches
- Making decisions that affect multiple components or services
- Establishing patterns that will be reused across the codebase
- Deviating from common industry practices (document why)
- Making trade-offs that future developers should understand

## Contributing

When adding a new ADR:

1. Copy the template from an existing ADR
2. Use the next sequential number (ADR-NNN)
3. Set status to "Proposed" until reviewed
4. Add an entry to the index table above
5. Update CLAUDE.md if the ADR affects development guidelines
