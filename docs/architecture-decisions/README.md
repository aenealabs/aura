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

**Qualifier "Implemented (library); not integrated":** code is merged and unit-tested but is not reachable from any entry point (API route mounted in `src/api/main.py`, agent flow, worker, Lambda, or CLI). Such an ADR is not Deployed. A Deployed status with a parenthetical qualifier means the infrastructure template exists and part of the described behavior is not yet built or wired; each ADR's dated status note gives the details (statuses reviewed against the code on 2026-10-26).

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
| [ADR-004](ADR-004-multi-cloud-architecture.md) | Cloud Abstraction Layer for Multi-Cloud | Implemented (library); not integrated -- no Azure infrastructure | 2025-12-16 |
| [ADR-005](ADR-005-hitl-sandbox-architecture.md) | HITL Sandbox Testing for Autonomous Remediation | Deployed (core HITL path; sandbox VPC, IAM approver roles, emergency bypass not built) | 2025-11-28 |
| [ADR-006](ADR-006-three-tier-dnsmasq-integration.md) | Three-Tier dnsmasq Integration | Deployed (Tiers 1-2; Tier 3 simulated) | 2025-11-12 |
| [ADR-007](ADR-007-modular-cicd-strategy.md) | Modular CI/CD with Layer-Based Deployment | Deployed | 2025-11-11 |
| [ADR-008](ADR-008-bedrock-llm-cost-controls.md) | Comprehensive Cost Controls for Bedrock LLM | Deployed | 2025-11-28 |
| [ADR-009](ADR-009-drift-protection-dual-layer.md) | Dual-Layer Drift Protection for Compliance | Deployed | 2025-11-24 |
| [ADR-010](ADR-010-autonomous-adr-generation-pipeline.md) | Autonomous ADR Generation Pipeline | Deployed (Phase 1 scheduled; Phases 2-4 library only; Phase 5 not built) | 2025-12-14 |
| [ADR-011](ADR-011-vpc-access-via-eks-deployment.md) | VPC Access via EKS Deployment | Deployed | 2025-11-29 |
| [ADR-012](ADR-012-opensearch-iam-master-user.md) | OpenSearch IAM Master User Authentication | Deployed | 2025-11-29 |
| [ADR-013](ADR-013-service-adapter-factory-pattern.md) | Service Adapter and Factory Pattern | Deployed | 2025-12-01 |
| [ADR-014](ADR-014-llm-enhanced-agent-search-pattern.md) | LLM-Enhanced Agent Search Pattern | Implemented (library); not integrated | 2025-12-01 |
| [ADR-015](ADR-015-tiered-llm-model-strategy.md) | Tiered LLM Model Strategy | Deployed | 2025-12-01 |
| [ADR-016](ADR-016-hitl-auto-escalation-strategy.md) | HITL Approval Auto-Escalation Strategy | Deployed | 2025-12-02 |
| [ADR-017](ADR-017-dynamic-sandbox-resource-allocation.md) | Dynamic Sandbox Resource Allocation | Deployed (infrastructure only; per-agent dynamic sizing not built) | 2025-12-02 |
| [ADR-018](ADR-018-meta-orchestrator-dynamic-agent-spawning.md) | Meta-Orchestrator with Dynamic Agent Spawning | Deployed (Phases 1-3; Phase 4 incomplete) | 2025-12-02 |
| [ADR-019](ADR-019-market-intelligence-agent.md) | Market Intelligence Agent | Accepted (scaffold only; data sources stubbed) | 2025-12-02 |
| [ADR-020](ADR-020-private-ecr-base-images.md) | Private ECR Base Images for Controlled Supply Chain | Deployed | 2025-12-04 |
| [ADR-021](ADR-021-guardrails-cognitive-architecture.md) | Guardrails Cognitive Architecture | Deployed (partial: no persistent memory stores) | 2025-12-04 |
| [ADR-022](ADR-022-gitops-kubernetes-deployment.md) | GitOps for Kubernetes Deployment with ArgoCD | Deployed (partial: GitOps migration incomplete) | 2025-12-04 |
| [ADR-023](ADR-023-agentcore-gateway-integration.md) | AgentCore Gateway Integration | Accepted (scaffolding; Gateway calls mocked) | 2025-12-04 |
| [ADR-024](ADR-024-titan-neural-memory.md) | Titan Neural Memory Architecture | Deployed (library implemented; service integration partial) | 2025-12-16 |
| [ADR-025](ADR-025-runtime-incident-agent.md) | Runtime Incident Agent | Deployed (code-graph correlation not wired) | 2025-12-05 |
| [ADR-026](ADR-026-bootstrap-once-update-forever.md) | Bootstrap Once, Update Forever Pattern | Deployed | 2025-12-06 |
| [ADR-027](ADR-027-security-group-management-pattern.md) | Security Group Management Pattern | Deployed | 2025-12-06 |
| [ADR-028](ADR-028-foundry-capability-adoption.md) | Foundry Capability Adoption | Deployed (partial: several components unwired) | 2025-12-07 |
| [ADR-029](ADR-029-agent-optimization-roadmap.md) | Agent Optimization Roadmap (v2.1 - Phases 1.3, 2.2, 2.3 enabled) | Deployed (Phases 1-2 except 2.1 stores; Phase 3 not started) | 2025-12-16 |
| [ADR-030](ADR-030-chat-assistant-architecture.md) | Chat Assistant Architecture | Deployed (4 of 8 chat tools hardcoded) | 2025-12-08 |
| [ADR-031](ADR-031-neptune-deployment-mode.md) | Neptune Deployment Mode Configuration | Deployed (provisioned mode only; serverless not built) | 2025-12-10 |
| [ADR-032](ADR-032-configurable-autonomy-framework.md) | Configurable Autonomy Framework | Deployed (policy service in use; REST API not mounted) | 2025-12-10 |
| [ADR-033](ADR-033-runbook-agent.md) | Runbook Agent for Automated Incident Documentation | Deployed (core agent; external integrations not built) | 2025-12-11 |
| [ADR-034](ADR-034-context-engineering-implementation.md) | Context Engineering Implementation Plan | Implemented (library); not integrated | 2025-12-14 |
| [ADR-035](ADR-035-dedicated-docker-build-project.md) | Dedicated Docker-Podman Build CodeBuild Project | Deployed | 2025-12-14 |
| [ADR-036](ADR-036-multi-platform-container-builds.md) | Multi-Platform Container Build Strategy | Deployed | 2025-12-13 |
| [ADR-037](ADR-037-aws-agent-capability-replication.md) | AWS Agent Capability Replication | Implemented (library); not integrated -- several components not built | 2025-12-16 |
| [ADR-038](ADR-038-codebuild-caching-optimization.md) | CodeBuild Caching Optimization Strategy | Deployed | 2025-12-14 |
| [ADR-039](ADR-039-self-service-test-environments.md) | Self-Service Test Environment Provisioning | Deployed (provisioning hand-off not wired) | 2025-12-15 |
| [ADR-040](ADR-040-configurable-compliance-settings.md) | Configurable Compliance Settings | Deployed | 2025-12-16 |
| [ADR-041](ADR-041-aws-required-wildcards-defense-in-depth.md) | AWS-Required Wildcards with Defense-in-Depth | Implemented | 2025-12-16 |
| [ADR-042](ADR-042-real-time-agent-intervention.md) | Real-Time Agent Intervention Architecture | Deployed (Phase 1 infrastructure; checkpoint API not mounted) | 2025-12-17 |
| [ADR-043](ADR-043-repository-onboarding-wizard.md) | Repository Onboarding Wizard with OAuth | Deployed (wizard and API; ingestion trigger not wired) | 2025-12-18 |
| [ADR-044](ADR-044-enhanced-node-detail-panel.md) | Enhanced Node Detail Panel for GraphRAG Explorer | Deployed (Phase 1 UI on mock data; Phases 2-3 planned) | 2025-12-19 |
| [ADR-045](ADR-045-external-documentation-links.md) | External Documentation Links for Code Navigation | Deployed (Phase 1 UI on mock data; Phases 2-3 planned) | 2025-12-20 |
| [ADR-046](ADR-046-support-ticketing-connectors.md) | Support Ticketing Connector Framework | Deployed (GitHub connector; configuration in-memory) | 2025-12-21 |
| [ADR-047](ADR-047-customer-onboarding-features.md) | Customer Onboarding Features | Deployed | 2025-12-22 |
| [ADR-048](ADR-048-developer-tools-data-platform-integrations.md) | Developer Tools & Data Platform Integrations | Accepted (partially implemented; backend mocked) | 2025-12-23 |
| [ADR-049](ADR-049-self-hosted-deployment-strategy.md) | Self-Hosted Deployment Strategy | Deployed (Phases 0-4 largely built; 3 items missing) | 2025-12-28 |
| [ADR-050](ADR-050-self-play-swe-rl-integration.md) | Self-Play SWE-RL Integration | Deployed (infrastructure); training loop not operational | 2026-01-02 |
| [ADR-051](ADR-051-recursive-context-and-embedding-prediction.md) | Recursive Context Scaling & Embedding Prediction | Implemented (library); not integrated | 2026-01-04 |
| [ADR-052](ADR-052-ai-alignment-principles.md) | AI Alignment Principles & Human-Machine Collaboration | Implemented (library, Phases 1-3); not integrated | 2026-01-04 |
| [ADR-053](ADR-053-enterprise-security-integrations.md) | Enterprise Security Integrations (Zscaler, Saviynt, AuditBoard) | Implemented (library, connectors); not integrated | 2026-01-06 |
| [ADR-054](ADR-054-multi-idp-authentication.md) | Multi-IdP Authentication | Implemented (library); not integrated | 2026-01-06 |
| [ADR-055](ADR-055-agent-scheduling-view.md) | Agent Scheduling View & Job Queue Management | Implemented | 2026-01-06 |
| [ADR-056](ADR-056-documentation-agent.md) | Documentation Agent for Architecture Discovery | Deployed (partial: API path uses demo graph) | 2026-01-07 |
| [ADR-057](ADR-057-public-documentation-portal.md) | Public Documentation Portal | Retired (moved out of repository, 2026-10-26) | 2026-01-08 |
| [ADR-058](ADR-058-eks-multi-node-group-architecture.md) | EKS Multi-Node Group Architecture | Deployed | 2026-01-10 |
| [ADR-059](ADR-059-aws-organization-account-restructure.md) | AWS Organization Account Restructure | Accepted | 2026-01-10 |
| [ADR-060](ADR-060-enterprise-diagram-generation.md) | Enterprise Diagram Generation with Multi-Provider Model Routing | Implemented (Phases 1-3); Phase 4 not exposed via API | 2026-01-12 |
| [ADR-061](ADR-061-gpu-workload-scheduler.md) | GPU Workload Scheduler | Deployed (partial: jobs not dispatched to Kubernetes) | 2026-01-12 |
| [ADR-062](ADR-062-environment-validator-agent.md) | Environment Validator Agent | Deployed (DEV/QA; admission webhook not built) | 2026-01-14 |
| [ADR-063](ADR-063-constitutional-ai-integration.md) | Constitutional AI Integration | Deployed (services and Lambdas; agent integration not enabled) | 2026-01-21 |
| [ADR-064](ADR-064-customizable-dashboard-widgets.md) | Customizable Dashboard Widgets | Deployed (Phases 1-2; Phase 3 stubs) | 2026-01-23 |
| [ADR-065](ADR-065-semantic-guardrails-engine.md) | Semantic Guardrails Engine | Deployed (Layers 1-2 used in ingestion; engine not invoked on agent/LLM inputs) | 2026-01-25 |
| [ADR-066](ADR-066-agent-capability-governance.md) | Agent Capability Governance | Implemented (library); not integrated | 2026-01-25 |
| [ADR-067](ADR-067-context-provenance-integrity.md) | Context Provenance and Integrity for GraphRAG | Deployed (ingestion side; retrieval verifier not on a running path) | 2026-01-25 |
| [ADR-068](ADR-068-universal-explainability-framework.md) | Universal Explainability Framework | Implemented (library); not integrated -- API serves generated data | 2026-01-25 |
| [ADR-069](ADR-069-guardrail-configuration-ui.md) | Guardrail Configuration UI | In Progress (configuration in-memory; not applied to enforcement) | 2026-01-26 |
| [ADR-070](ADR-070-policy-as-code-gitops.md) | Policy-as-Code with GitOps for Capability Governance | Implemented (library); not integrated -- pipeline not built | 2026-01-27 |
| [ADR-071](ADR-071-cross-agent-capability-graph.md) | Cross-Agent Capability Graph Analysis | Implemented (library, mock-graph mode); not integrated | 2026-01-27 |
| [ADR-072](ADR-072-ml-anomaly-detection-agents.md) | ML-Based Anomaly Detection for Agent Behavior | Implemented (library); not integrated | 2026-01-27 |
| [ADR-073](ADR-073-attribute-based-access-control.md) | Attribute-Based Access Control for Multi-Tenant User Authorization | Implemented (library); not integrated | 2026-01-27 |
| [ADR-074](ADR-074-palantir-aip-integration.md) | Palantir AIP Integration for Data-Informed Code Security | Deployed (IAM template only; API dependencies return 503) | 2026-01-29 |
| [ADR-075](ADR-075-palantir-aip-ui-enhancements.md) | Palantir AIP Integration UI Enhancements | In Progress (Phase 1-2 UI built; falls back to mock data) | 2026-01-29 |
| [ADR-076](ADR-076-sbom-attestation-supply-chain.md) | SBOM Attestation and Supply Chain Security | Implemented (library; signing simulated); not integrated | 2026-02-02 |
| [ADR-076.1](ADR-076.1-non-production-tier-classification.md) | Non-Production Tier Classification for SBOM Attestation | Accepted (labels and ECR repo built; attestation step not built) | 2026-05-15 |
| [ADR-077](ADR-077-cloud-runtime-security-integration.md) | Cloud Runtime Security Integration | Deployed (DynamoDB tables only; services not integrated) | 2026-02-03 |
| [ADR-078](ADR-078-airgapped-edge-deployment.md) | Air-Gapped and Edge Deployment Architecture | Implemented (library; mock signing and inference); not integrated | 2026-02-03 |
| [ADR-079](ADR-079-scale-ai-model-security.md) | Scale and AI Model Security | Implemented (library; partly simulated); not integrated | 2026-02-03 |
| [ADR-080](ADR-080-evo-memory-enhancements.md) | Evo-Memory Enhancements for Test-Time Memory Evolution | Implemented (library); not integrated | 2026-02-04 |
| [ADR-081](ADR-081-constraint-geometry-engine.md) | Constraint Geometry Engine | Implemented (library, Phase 1); not integrated | 2026-02-11 |
| [ADR-082](ADR-082-reserved.md) | Reserved | Reserved | 2026-05-05 |
| [ADR-083](ADR-083-runtime-agent-security-platform.md) | Runtime Agent Security Platform | Deployed (infrastructure templates); services not integrated | 2026-02-18 |
| [ADR-084](ADR-084-native-vulnerability-scanning-engine.md) | Native Vulnerability Scanning Engine | Implemented (library); not integrated -- scanner API and worker not built | 2026-02-20 |
| [ADR-085](ADR-085-deterministic-verification-envelope.md) | Deterministic Verification Envelope | Implemented (library, all 5 phases); not integrated | 2026-02-26 |
| [ADR-085.1](ADR-085.1-object-code-verification.md) | Object-Code Verification Track | Proposed (Phase 1 scaffold) | 2026-05-22 |
| [ADR-086](ADR-086-agentic-identity-lifecycle-controls.md) | Agentic Identity Lifecycle Controls | Implemented (library); not integrated | 2026-04-06 |
| [ADR-087](ADR-087-hyperscale-agent-orchestration.md) | Configurable Hyperscale Agent Orchestration | Accepted (Phase 1 settings API; Phases 2-4 not started) | 2026-05-05 |
| [ADR-088](ADR-088-continuous-model-assurance.md) | Continuous Model Assurance | Implemented (library, all 3 phases); not integrated | 2026-05-05 |
| [ADR-089](ADR-089-long-horizon-security-campaigns.md) | Long-Horizon Security Campaigns | Implemented (library, Phases 1-4 and 6); not integrated | 2026-05-07 |
| [ADR-090](ADR-090-graphrag-ingestion-edge-completeness.md) | GraphRAG Ingestion Edge Completeness | Implemented (Phases 0-5; Phase 4c.2 partial) | 2026-05-08 |
| [ADR-091](ADR-091-cognito-cross-region-disaster-recovery.md) | Cognito Cross-Region Disaster Recovery | Accepted (templates present) | 2026-05-09 |
| [ADR-092](ADR-092-cfn-deploy-role-wildcard-scoping.md) | CloudFormation Deploy Role Wildcard Scoping | Accepted (v2; Phase 2 code merged; deploy phases deferred) | 2026-05-12 |
| [ADR-093](ADR-093-neptune-cross-file-taint-resolver.md) | Neptune-Backed Cross-File Taint Resolver | Accepted (v2; Phases 0-5 library, not integrated; Phases 6-7 deferred) | 2026-05-13 |
| [ADR-094](ADR-094-scoped-dependabot-auto-merge.md) | Scoped Auto-Merge for Routine Dependabot Pull Requests | Implemented | 2026-09-28 |

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
