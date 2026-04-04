# Project Aura - Documentation Index

**Last Updated:** March 26, 2026
**Purpose:** Master index for all project documentation with clear organization

---

## Quick Navigation

- **Product Docs:** [product/getting-started/](product/getting-started/index.md) - Platform overview, quick start, installation
- **Core Concepts:** [product/core-concepts/](product/core-concepts/index.md) - Architecture deep-dives, HITL, sandbox security
- **Support Docs:** [support/](support/index.md) - Troubleshooting, API reference, architecture, operations
- **Customer Docs:** [customer/QUICK_START.md](customer/QUICK_START.md) - Self-hosted deployment for customers
- **Certification Roadmaps:** [compliance/roadmaps/README.md](compliance/roadmaps/README.md) - FedRAMP, CMMC L2/L3, IL5
- **User Guides:** [guides/README.md](guides/README.md) - Start here for end-user documentation
- **Getting Started:** [README.md](../README.md) → [product/getting-started/quick-start.md](product/getting-started/quick-start.md)
- **GitOps Operations:** [ARGOCD_RUNBOOK.md](runbooks/ARGOCD_RUNBOOK.md)
- **E2E Testing:** [E2E_TESTING_RUNBOOK.md](runbooks/E2E_TESTING_RUNBOOK.md)
- **For AI Assistants:** [CLAUDE.md](../CLAUDE.md) + [GUARDRAILS.md](../agent-config/GUARDRAILS.md)
- **Current Status:** [PROJECT_STATUS.md](../PROJECT_STATUS.md) + [CHANGELOG.md](../CHANGELOG.md)
- **Architecture:** [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)

---

## Customer Documentation (docs/customer/)

Customer-facing documentation for self-hosted deployment and platform operations.

### Deployment & Setup
| Document | Purpose | Lines |
|----------|---------|-------|
| [customer/QUICK_START.md](customer/QUICK_START.md) | 30-minute deployment guide | 379 |
| [customer/PREREQUISITES.md](customer/PREREQUISITES.md) | AWS requirements, quotas, cost estimates | 558 |
| [customer/ARCHITECTURE_OVERVIEW.md](customer/ARCHITECTURE_OVERVIEW.md) | System architecture for customers | 609 |
| [customer/CONFIGURATION_REFERENCE.md](customer/CONFIGURATION_REFERENCE.md) | SSM, Secrets, ConfigMaps, env vars | 578 |

### Operations & Maintenance
| Document | Purpose | Lines |
|----------|---------|-------|
| [customer/ADMIN_GUIDE.md](customer/ADMIN_GUIDE.md) | User, repo, agent management | 745 |
| [customer/TROUBLESHOOTING.md](customer/TROUBLESHOOTING.md) | Common issues and solutions | 800 |
| [customer/UPGRADE_GUIDE.md](customer/UPGRADE_GUIDE.md) | Version upgrade procedures | 570 |

### Security & Compliance
| Document | Purpose | Lines |
|----------|---------|-------|
| [customer/SECURITY_WHITEPAPER.md](customer/SECURITY_WHITEPAPER.md) | Security architecture, CMMC/SOC2/NIST mapping | 653 |

---

## Customer Installer (deploy/installer/)

Self-hosted installation scripts and CloudFormation templates.

### Installer Scripts
| File | Purpose |
|------|---------|
| [../deploy/installer/aura-install.sh](../deploy/installer/aura-install.sh) | Main installation script with pre-flight checks |
| [../deploy/installer/aura-uninstall.sh](../deploy/installer/aura-uninstall.sh) | Clean removal with data retention option |
| [../deploy/installer/config-wizard.sh](../deploy/installer/config-wizard.sh) | Interactive configuration generator |
| [../deploy/installer/README.md](../deploy/installer/README.md) | Installer documentation |

### CloudFormation Templates (deploy/customer/cloudformation/)
| Template | Purpose |
|----------|---------|
| [../deploy/customer/cloudformation/aura-quick-start.yaml](../deploy/customer/cloudformation/aura-quick-start.yaml) | Single-click full deployment |
| [../deploy/customer/cloudformation/aura-foundation-only.yaml](../deploy/customer/cloudformation/aura-foundation-only.yaml) | VPC + networking only |
| [../deploy/customer/cloudformation/aura-data-layer.yaml](../deploy/customer/cloudformation/aura-data-layer.yaml) | Neptune + OpenSearch + DynamoDB |
| [../deploy/customer/cloudformation/aura-application.yaml](../deploy/customer/cloudformation/aura-application.yaml) | EKS + application services |

### Account Management Templates (deploy/cloudformation/)
| Template | Purpose |
|----------|---------|
| [../deploy/cloudformation/organizations.yaml](../deploy/cloudformation/organizations.yaml) | Layer 0.1: AWS Organizations, OUs, SCPs |
| [../deploy/cloudformation/account-bootstrap.yaml](../deploy/cloudformation/account-bootstrap.yaml) | Layer 0.2: Per-account bootstrap (KMS, CloudTrail, GuardDuty, SNS) |

### Parameter Files (deploy/customer/parameters/)
| File | Purpose |
|------|---------|
| [../deploy/customer/parameters/small.json](../deploy/customer/parameters/small.json) | 1-50 developers (~$400/mo) |
| [../deploy/customer/parameters/medium.json](../deploy/customer/parameters/medium.json) | 50-200 developers (~$800/mo) |
| [../deploy/customer/parameters/enterprise.json](../deploy/customer/parameters/enterprise.json) | 200+ developers (~$1,200/mo) |
| [../deploy/customer/parameters/govcloud.json](../deploy/customer/parameters/govcloud.json) | GovCloud-specific settings |

### Verification Suite (deploy/installer/verify/)
| Script | Purpose |
|--------|---------|
| [../deploy/installer/verify/verify-deployment.sh](../deploy/installer/verify/verify-deployment.sh) | Comprehensive deployment verification |
| [../deploy/installer/verify/smoke-tests.sh](../deploy/installer/verify/smoke-tests.sh) | Basic functionality tests |
| [../deploy/installer/verify/health-checks.sh](../deploy/installer/verify/health-checks.sh) | Service health verification |
| [../deploy/installer/verify/connectivity-tests.sh](../deploy/installer/verify/connectivity-tests.sh) | Network connectivity tests |

---

## Self-Hosted Deployment (docs/self-hosted/)

Technical documentation for ADR-049 self-hosted deployment implementation.

### ADR-049 Reference
| Document | Purpose | Lines |
|----------|---------|-------|
| [self-hosted/ADR-049-IMPLEMENTATION-DETAILS.md](self-hosted/ADR-049-IMPLEMENTATION-DETAILS.md) | Technical specs, expert reviews, appendices (split from ADR-049) | 516 |
| [self-hosted/NATIVE_INSTALLERS_GUIDE.md](self-hosted/NATIVE_INSTALLERS_GUIDE.md) | Installation guide for MSI, DEB, RPM, PKG, Homebrew | 342 |

### Phase 0 Prerequisites
| Document | Purpose | Lines |
|----------|---------|-------|
| [self-hosted/DYNAMODB_SCHEMA_REFERENCE.md](self-hosted/DYNAMODB_SCHEMA_REFERENCE.md) | DynamoDB→PostgreSQL migration schemas for 28 tables | 654 |
| [self-hosted/QUERY_LANGUAGE_STRATEGY.md](self-hosted/QUERY_LANGUAGE_STRATEGY.md) | Gremlin vs Cypher decision (native Cypher for Neo4j) | 313 |
| [self-hosted/LICENSE_VALIDATION_SCHEME.md](self-hosted/LICENSE_VALIDATION_SCHEME.md) | Ed25519 license validation, hardware fingerprinting, feature gating | 712 |
| [self-hosted/RESOURCE_BASELINES.md](self-hosted/RESOURCE_BASELINES.md) | HPA resource baselines, scaling thresholds, deployment sizes | 580 |
| [self-hosted/FEATURE_FLAG_EDITION_MAPPING.md](self-hosted/FEATURE_FLAG_EDITION_MAPPING.md) | SaaS→Self-hosted tier mapping, edition schema, feature gating | 680 |

### HPA Templates (deploy/self-hosted/hpa/)
| File | Purpose |
|------|---------|
| [hpa-templates.yaml](../deploy/self-hosted/hpa/hpa-templates.yaml) | HPA configs for API, agents, LLM, monitoring services |
| [resource-quotas.yaml](../deploy/self-hosted/hpa/resource-quotas.yaml) | ResourceQuota and LimitRange per namespace |
| [README.md](../deploy/self-hosted/hpa/README.md) | Quick start, troubleshooting, custom metrics |

### NetworkPolicy Templates (deploy/self-hosted/network-policies/)
| File | Purpose |
|------|---------|
| [00-namespace-defaults.yaml](../deploy/self-hosted/network-policies/00-namespace-defaults.yaml) | Default-deny + DNS egress for all namespaces |
| [01-aura-api.yaml](../deploy/self-hosted/network-policies/01-aura-api.yaml) | API service ingress/egress rules |
| [02-databases.yaml](../deploy/self-hosted/network-policies/02-databases.yaml) | Neo4j, PostgreSQL, OpenSearch, Redis, MinIO |
| [03-llm-inference.yaml](../deploy/self-hosted/network-policies/03-llm-inference.yaml) | vLLM, TGI, Ollama, air-gapped mode |
| [04-agents.yaml](../deploy/self-hosted/network-policies/04-agents.yaml) | Orchestrator, Memory, Sandbox isolation |
| [05-frontend.yaml](../deploy/self-hosted/network-policies/05-frontend.yaml) | Frontend, Ingress Controller |
| [06-monitoring.yaml](../deploy/self-hosted/network-policies/06-monitoring.yaml) | Prometheus, Grafana, Alertmanager, OTEL |
| [README.md](../deploy/self-hosted/network-policies/README.md) | Deployment guide, port reference, troubleshooting |

---

## User Guides (docs/guides/)

User-friendly documentation for platform users, organized by topic.

### Core Guides
| Guide | Purpose | Audience |
|-------|---------|----------|
| [guides/README.md](guides/README.md) | Guide index and quick start path | All users |
| [guides/getting-started.md](guides/getting-started.md) | Platform overview, first steps, core concepts | New users |
| [guides/PLATFORM_CONFIGURATION_GUIDE.md](guides/PLATFORM_CONFIGURATION_GUIDE.md) | Comprehensive UI configuration walkthrough | Admins, Security |
| [guides/security-compliance.md](guides/security-compliance.md) | HITL workflows, compliance frameworks, security controls | All users |
| [guides/agent-system.md](guides/agent-system.md) | How agents work, orchestration, monitoring | Developers, Admins |
| [guides/configuration.md](guides/configuration.md) | Complete settings reference | Admins |

### Feature Guides
| Guide | Purpose | Audience |
|-------|---------|----------|
| [guides/data-context.md](guides/data-context.md) | GraphRAG, code indexing, context retrieval | Developers |
| [guides/GRAPHRAG_EXPLORER_USER_GUIDE.md](guides/GRAPHRAG_EXPLORER_USER_GUIDE.md) | Graph visualization navigation, querying, and filtering | All users |
| [guides/deployment.md](guides/deployment.md) | Test environments, sandboxes, approval workflows | Developers |
| [guides/monitoring-observability.md](guides/monitoring-observability.md) | Dashboards, alerts, metrics | Admins, DevOps |
| [user-guides/INCIDENT_MANAGEMENT.md](user-guides/INCIDENT_MANAGEMENT.md) | Incident tracking, AI-powered RCA, external ticketing integration | All users |

### Repository Guides
| Guide | Purpose | Audience |
|-------|---------|----------|
| [guides/REPOSITORY_ONBOARDING_GUIDE.md](guides/REPOSITORY_ONBOARDING_GUIDE.md) | Connect GitHub/GitLab repos via onboarding wizard | All users |

### Notification Guides
| Guide | Purpose | Audience |
|-------|---------|----------|
| [guides/NOTIFICATION_INTEGRATION_GUIDE.md](guides/NOTIFICATION_INTEGRATION_GUIDE.md) | Configure Slack, Teams, and other notification channels | Admins, DevOps |

### Reference Guides
| Guide | Purpose | Audience |
|-------|---------|----------|
| [guides/api-reference.md](guides/api-reference.md) | REST API documentation for developers | Developers |
| [guides/integrations.md](guides/integrations.md) | External tool connections (Slack, Jira, GitHub) | Admins |
| [guides/troubleshooting.md](guides/troubleshooting.md) | Common issues and solutions | All users |

### Development Guides
| Guide | Purpose | Audience |
|-------|---------|----------|
| [guides/CONNECTOR_DEVELOPMENT.md](guides/CONNECTOR_DEVELOPMENT.md) | Patterns for creating external tool connectors | Developers |

### Standards (docs/standards/)
| Document | Purpose | Audience |
|----------|---------|----------|
| [standards/LOGGING_STANDARDS.md](standards/LOGGING_STANDARDS.md) | Structured logging configuration, levels, correlation IDs | Developers |

### Load Testing (tests/load/)
| Document | Purpose | Audience |
|----------|---------|----------|
| [../tests/load/README.md](../tests/load/README.md) | k6 load testing framework, profiles, CI integration | DevOps, Developers |

---

## Product Documentation (docs/product/)

Enterprise-grade product documentation for Project Aura platform users, security engineers, and compliance officers.

### Getting Started (docs/product/getting-started/)

| Document | Purpose | Lines |
|----------|---------|-------|
| [product/getting-started/index.md](product/getting-started/index.md) | Platform overview, key benefits, architecture, use cases | 311 |
| [product/getting-started/quick-start.md](product/getting-started/quick-start.md) | 5-minute setup guide for SaaS deployment | 315 |
| [product/getting-started/system-requirements.md](product/getting-started/system-requirements.md) | Prerequisites for SaaS, Kubernetes, Podman deployments | 483 |
| [product/getting-started/installation.md](product/getting-started/installation.md) | Detailed setup for all deployment options | 970 |
| [product/getting-started/first-project.md](product/getting-started/first-project.md) | Repository onboarding walkthrough | 650 |

### Core Concepts (docs/product/core-concepts/)

| Document | Purpose | Lines |
|----------|---------|-------|
| [product/core-concepts/index.md](product/core-concepts/index.md) | Technology pillars overview, learning paths by role | 217 |
| [product/core-concepts/autonomous-code-intelligence.md](product/core-concepts/autonomous-code-intelligence.md) | LLM-powered vulnerability detection and remediation | 326 |
| [product/core-concepts/hybrid-graphrag.md](product/core-concepts/hybrid-graphrag.md) | Neptune graph + OpenSearch vector architecture | 444 |
| [product/core-concepts/multi-agent-system.md](product/core-concepts/multi-agent-system.md) | Orchestrator, Coder, Reviewer, Validator agents | 579 |
| [product/core-concepts/hitl-workflows.md](product/core-concepts/hitl-workflows.md) | 4 autonomy levels, 7 policy presets, guardrails | 773 |
| [product/core-concepts/sandbox-security.md](product/core-concepts/sandbox-security.md) | ECS Fargate isolation, 5 validation categories | 826 |

### User Guides (docs/product/user-guides/)

| Document | Purpose | Lines |
|----------|---------|-------|
| [product/user-guides/index.md](product/user-guides/index.md) | User guides overview and navigation | 166 |
| [product/user-guides/repository-onboarding.md](product/user-guides/repository-onboarding.md) | Connect GitHub/GitLab repos, configure scanning | - |
| [product/user-guides/vulnerability-remediation.md](product/user-guides/vulnerability-remediation.md) | Find, understand, and fix security vulnerabilities | - |
| [product/user-guides/patch-approval.md](product/user-guides/patch-approval.md) | HITL patch review and approval workflows | - |
| [product/user-guides/dashboard-customization.md](product/user-guides/dashboard-customization.md) | Dashboard widgets, layout editor, sharing (ADR-064) | - |
| [product/user-guides/team-collaboration.md](product/user-guides/team-collaboration.md) | Team management, permissions, notifications | - |
| [product/user-guides/capability-graph.md](product/user-guides/capability-graph.md) | Agent capability visualization, filtering, risk analysis (ADR-071) | 236 |

### Executive Summaries (docs/product/executive-summaries/)

| Document | Purpose | Lines |
|----------|---------|-------|
| [product/executive-summaries/development-assurance.md](product/executive-summaries/development-assurance.md) | Development assurance capabilities for CTOs/CIOs — 10 governance mechanisms, compliance mapping, competitive differentiation | 481 |
| [product/executive-summaries/faa-do178c-gap-analysis.md](product/executive-summaries/faa-do178c-gap-analysis.md) | FAA DO-178C gap analysis for FADEC/EEC software — DAL A/B certification requirements, DO-330 tool qualification, roadmap to compliance | 593 |

### Product Documentation (docs/product/)

---

## Support Documentation (docs/support/)

Technical documentation for developers, cybersecurity professionals, and IT administrators.

### Overview & FAQ (docs/support/)

| Document | Purpose | Lines |
|----------|---------|-------|
| [support/index.md](support/index.md) | Support documentation overview and navigation | 294 |
| [support/faq.md](support/faq.md) | Frequently Asked Questions (11 categories) | 643 |

### Troubleshooting (docs/support/troubleshooting/)

| Document | Purpose | Lines |
|----------|---------|-------|
| [support/troubleshooting/index.md](support/troubleshooting/index.md) | Troubleshooting guide overview | 327 |
| [support/troubleshooting/common-issues.md](support/troubleshooting/common-issues.md) | Frequently encountered problems with error codes | 703 |
| [support/troubleshooting/deployment-issues.md](support/troubleshooting/deployment-issues.md) | CloudFormation, EKS, container issues | 755 |
| [support/troubleshooting/performance-issues.md](support/troubleshooting/performance-issues.md) | Latency, memory, scaling problems | 678 |
| [support/troubleshooting/security-issues.md](support/troubleshooting/security-issues.md) | Auth failures, permission errors, encryption | 740 |

### API Reference (docs/support/api-reference/)

| Document | Purpose | Lines |
|----------|---------|-------|
| [support/api-reference/index.md](support/api-reference/index.md) | API documentation overview | 400 |
| [support/api-reference/rest-api.md](support/api-reference/rest-api.md) | REST endpoints, request/response formats | 1,012 |
| [support/api-reference/graphql-api.md](support/api-reference/graphql-api.md) | GraphQL schema and queries | 937 |
| [support/api-reference/webhooks.md](support/api-reference/webhooks.md) | Webhook events, payloads, retry logic | 714 |

### Architecture (docs/support/architecture/)

| Document | Purpose | Lines |
|----------|---------|-------|
| [support/architecture/index.md](support/architecture/index.md) | Architecture documentation overview | 276 |
| [support/architecture/system-overview.md](support/architecture/system-overview.md) | High-level system architecture with ASCII diagrams | 458 |
| [support/architecture/data-flow.md](support/architecture/data-flow.md) | How data moves through the system | 497 |
| [support/architecture/security-architecture.md](support/architecture/security-architecture.md) | Security controls, encryption, network isolation | 505 |
| [support/architecture/disaster-recovery.md](support/architecture/disaster-recovery.md) | Backup, recovery, RTO/RPO | 498 |

### Operations (docs/support/operations/)

| Document | Purpose | Lines |
|----------|---------|-------|
| [support/operations/index.md](support/operations/index.md) | Operations guide overview | 324 |
| [support/operations/monitoring.md](support/operations/monitoring.md) | CloudWatch, dashboards, alerts | 392 |
| [support/operations/logging.md](support/operations/logging.md) | Log formats, retention, analysis | 470 |
| [support/operations/backup-restore.md](support/operations/backup-restore.md) | Data backup and restoration procedures | 417 |
| [support/operations/scaling.md](support/operations/scaling.md) | Horizontal/vertical scaling, auto-scaling | 700 |

---

## Core Documentation (Root Directory)

### Project Overview & Status
| File | Purpose | Last Updated |
|------|---------|--------------|
| [README.md](../README.md) | Project overview, quick start | Feb 11, 2026 |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | Living status document (includes Recent Challenges section) | Mar 4, 2026 |
| [CHANGELOG.md](../CHANGELOG.md) | Version history and changes | Jan 2, 2026 |
| [CLAUDE.md](../CLAUDE.md) | AI assistant instructions & context management | Mar 4, 2026 |

### Architecture & Design
| File | Purpose | Last Updated |
|------|---------|--------------|
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | Complete system architecture | Jan 2, 2026 |

### Deployment
| File | Purpose | Last Updated |
|------|---------|--------------|
| [PREREQUISITES_RUNBOOK.md](runbooks/PREREQUISITES_RUNBOOK.md) | One-time environment setup (Phase 1) | Dec 4, 2025 |
| [MULTI_ACCOUNT_SETUP.md](deployment/MULTI_ACCOUNT_SETUP.md) | AWS Organizations & multi-environment isolation | Jan 8, 2026 |
| [QA_PROD_DEPLOYMENT_SEQUENCE.md](deployment/QA_PROD_DEPLOYMENT_SEQUENCE.md) | Fresh account deployment sequence, circular dependencies | Jan 8, 2026 |
| [DEPLOYMENT_GUIDE.md](deployment/DEPLOYMENT_GUIDE.md) | Modular CI/CD deployment procedures (Phases 2-3) | Jan 17, 2026 |
| [DEPLOYMENT_PIPELINE_ARCHITECTURE.md](deployment/DEPLOYMENT_PIPELINE_ARCHITECTURE.md) | Step Functions deployment pipeline (5-phase automation) | Jan 9, 2026 |
| [QA_DEPLOYMENT_CHECKLIST.md](deployment/QA_DEPLOYMENT_CHECKLIST.md) | Comprehensive QA deployment checklist (manual + pipeline) | Jan 9, 2026 |
| [DNSMASQ_QUICK_START.md](integrations/DNSMASQ_QUICK_START.md) | 5-minute dnsmasq deployment guide (Podman-first) | Jan 4, 2026 |

### Infrastructure & CI/CD
| File | Purpose | Last Updated |
|------|---------|--------------|
| [MODULAR_CICD_IMPLEMENTATION.md](deployment/MODULAR_CICD_IMPLEMENTATION.md) | Modular CI/CD architecture (8 layers, 8/8 deployed) | Dec 2, 2025 |
| [CICD_SETUP_GUIDE.md](deployment/CICD_SETUP_GUIDE.md) | CodeBuild + Step Functions pipeline setup (20 projects) | Jan 9, 2026 |

### Assessments (docs/assessments/)
| File | Purpose | Last Updated |
|------|---------|--------------|
| [assessments/AWS_WELL_ARCHITECTED_CICD_ASSESSMENT.md](assessments/AWS_WELL_ARCHITECTED_CICD_ASSESSMENT.md) | AWS Well-Architected CI/CD assessment | Nov 2025 |
| [assessments/AWS_WELL_ARCHITECTED_PLATFORM_ASSESSMENT.md](assessments/AWS_WELL_ARCHITECTED_PLATFORM_ASSESSMENT.md) | AWS Well-Architected Platform assessment | Dec 2025 |
| [assessments/TIME_SPACE_COMPLEXITY_AUDIT.md](assessments/TIME_SPACE_COMPLEXITY_AUDIT.md) | Codebase time/space complexity audit (87 findings, issues #701-#704) | Feb 26, 2026 |

### Planning (docs/planning/)
| File | Purpose | Last Updated |
|------|---------|--------------|
| [planning/FEATURE_BACKLOG.md](planning/FEATURE_BACKLOG.md) | Feature ideas, autonomous agent capabilities, roadmap | Dec 1, 2025 |
| [planning/INFRASTRUCTURE_REMEDIATION_PLAN.md](planning/INFRASTRUCTURE_REMEDIATION_PLAN.md) | Infrastructure remediation planning | Dec 2025 |

### Security (docs/security/)
| File | Purpose | Last Updated |
|------|---------|--------------|
| [security/SECURITY_FIXES_QUICK_REFERENCE.md](security/SECURITY_FIXES_QUICK_REFERENCE.md) | Quick reference for security fixes (current) | Nov 22, 2025 |
| [ERROR_HANDLING_AUDIT.md](reference/ERROR_HANDLING_AUDIT.md) | Memory services error handling audit and fixes | Dec 6, 2025 |

---

## docs/ Directory - Technical Documentation

### Deployment & Operations
| File | Purpose |
|------|---------|
| [CODEBUILD_BOOTSTRAP_GUIDE.md](deployment/CODEBUILD_BOOTSTRAP_GUIDE.md) | CodeBuild project deployment paths (bootstrap vs auto-deployed) |
| [DOCKER_BEST_PRACTICES.md](deployment/DOCKER_BEST_PRACTICES.md) | Container build best practices (Podman-first per ADR-049) |
| [DEPLOYMENT_METHODS.md](deployment/DEPLOYMENT_METHODS.md) | CI/CD vs Bootstrap vs GitOps deployment reference |
| [PREREQUISITES_RUNBOOK.md](runbooks/PREREQUISITES_RUNBOOK.md) | One-time environment setup before CI/CD |
| [ARGOCD_RUNBOOK.md](runbooks/ARGOCD_RUNBOOK.md) | ArgoCD GitOps operations, sync, rollback, troubleshooting |
| [E2E_TESTING_RUNBOOK.md](runbooks/E2E_TESTING_RUNBOOK.md) | E2E integration tests (Neptune, OpenSearch, Bedrock) |
| [DRIFT_PROTECTION_GUIDE.md](runbooks/DRIFT_PROTECTION_GUIDE.md) | AWS Config drift protection setup |
| [SECURITY_GROUP_IMPORT_GUIDE.md](runbooks/SECURITY_GROUP_IMPORT_GUIDE.md) | CloudFormation resource import recovery procedures |
| [PRODUCTION_DEPLOYMENT_CHECKLIST.md](deployment/PRODUCTION_DEPLOYMENT_CHECKLIST.md) | Production deployment checklist |
| [PRODUCTION_READINESS_GUIDE.md](deployment/PRODUCTION_READINESS_GUIDE.md) | Production readiness criteria |
| [KNOWN_ISSUES.md](reference/KNOWN_ISSUES.md) | Known issues tracker |
| [OPTIMIZATION_REVIEW_2025-12-28.md](reference/OPTIMIZATION_REVIEW_2025-12-28.md) | Comprehensive codebase optimization opportunities (Updated Dec 30: 11 items implemented) |

### Runbooks (Operational Procedures)
| File | Purpose |
|------|---------|
| [runbooks/LAYER1_FOUNDATION_RUNBOOK.md](runbooks/LAYER1_FOUNDATION_RUNBOOK.md) | Layer 1: VPC, Security Groups, IAM, VPC Endpoints |
| [runbooks/LAYER2_DATA_RUNBOOK.md](runbooks/LAYER2_DATA_RUNBOOK.md) | Layer 2: Neptune, OpenSearch, DynamoDB, S3 |
| [runbooks/LAYER3_COMPUTE_RUNBOOK.md](runbooks/LAYER3_COMPUTE_RUNBOOK.md) | Layer 3: EKS Cluster, Node Groups, OIDC |
| [runbooks/LAYER4_APPLICATION_RUNBOOK.md](runbooks/LAYER4_APPLICATION_RUNBOOK.md) | Layer 4: ECR, Bedrock, IRSA, K8s Workloads |
| [runbooks/LAYER5_OBSERVABILITY_RUNBOOK.md](runbooks/LAYER5_OBSERVABILITY_RUNBOOK.md) | Layer 5: Secrets, Monitoring, Cost Alerts |
| [runbooks/LAYER6_SERVERLESS_RUNBOOK.md](runbooks/LAYER6_SERVERLESS_RUNBOOK.md) | Layer 6: Lambda, EventBridge, HITL Automation |
| [runbooks/LAYER7_SANDBOX_RUNBOOK.md](runbooks/LAYER7_SANDBOX_RUNBOOK.md) | Layer 7: HITL Workflow, ECS Sandbox, Step Functions |
| [runbooks/LAYER8_SECURITY_RUNBOOK.md](runbooks/LAYER8_SECURITY_RUNBOOK.md) | Layer 8: AWS Config, GuardDuty, Drift Detection, Compliance |
| [runbooks/DYNAMODB_PITR_ENABLE.md](runbooks/DYNAMODB_PITR_ENABLE.md) | Enable PITR on existing DynamoDB tables (CloudFormation workaround) |
| [runbooks/CODECONNECTIONS_GITHUB_ACCESS.md](runbooks/CODECONNECTIONS_GITHUB_ACCESS.md) | Fix CodeConnections/codestar-connections IAM permission errors |
| [runbooks/CLOUDFORMATION_IAM_PERMISSIONS.md](runbooks/CLOUDFORMATION_IAM_PERMISSIONS.md) | Fix CloudFormation deployment AccessDenied errors |
| [runbooks/CODEBUILD_SHELL_AND_STACK_STATES.md](runbooks/CODEBUILD_SHELL_AND_STACK_STATES.md) | Fix CodeBuild bash conditionals and ROLLBACK_COMPLETE stacks |
| [runbooks/ADR039_SERVICE_CATALOG_DEPLOYMENT.md](runbooks/ADR039_SERVICE_CATALOG_DEPLOYMENT.md) | ADR-039 Phase 2 IAM troubleshooting guide |
| [runbooks/ECR_REPOSITORY_CONFLICTS.md](runbooks/ECR_REPOSITORY_CONFLICTS.md) | Fix ECR repository AlreadyExists conflicts |
| [runbooks/DOCKER_PLATFORM_MISMATCH.md](runbooks/DOCKER_PLATFORM_MISMATCH.md) | Container platform mismatch troubleshooting (Podman/Docker) |
| [runbooks/AWS_BACKUP_VAULT_CREATION.md](runbooks/AWS_BACKUP_VAULT_CREATION.md) | AWS Backup vault creation for PITR recovery |
| [runbooks/CFN_DESCRIPTION_SYNC.md](runbooks/CFN_DESCRIPTION_SYNC.md) | CloudFormation description synchronization (force description updates) |
| [runbooks/RESOURCE_TAGGING_PERMISSIONS.md](runbooks/RESOURCE_TAGGING_PERMISSIONS.md) | Resource tagging permission errors (UnauthorizedTaggingOperation) |
| [runbooks/TEST_ENVIRONMENT_RUNBOOK.md](runbooks/TEST_ENVIRONMENT_RUNBOOK.md) | Self-service test environment operations, troubleshooting, and maintenance |
| [runbooks/SANDBOX_CAPABILITY_RUNBOOK.md](runbooks/SANDBOX_CAPABILITY_RUNBOOK.md) | Comprehensive guide for replicating sandbox capability in air-gapped environments |
| [runbooks/LOG_RETENTION_SYNC_RUNBOOK.md](runbooks/LOG_RETENTION_SYNC_RUNBOOK.md) | CloudWatch log retention sync Lambda operations and troubleshooting |
| [runbooks/STEP_FUNCTIONS_ECS_INTEGRATION.md](runbooks/STEP_FUNCTIONS_ECS_INTEGRATION.md) | Step Functions ECS integration troubleshooting (sync vs async output structures) |
| [runbooks/QA_KILLSWITCH_RUNBOOK.md](runbooks/QA_KILLSWITCH_RUNBOOK.md) | QA environment kill-switch: full shutdown/restore procedure, cost savings |
| [runbooks/DEV_KILLSWITCH_RUNBOOK.md](runbooks/DEV_KILLSWITCH_RUNBOOK.md) | DEV environment kill-switch: full shutdown/restore (80 stacks, significant monthly savings) |

### Operations (docs/operations/)
| File | Purpose |
|------|---------|
| [operations/QA_SCHEDULE_GUIDE.md](operations/QA_SCHEDULE_GUIDE.md) | QA cost optimization scheduler (EKS node scaling) |
| [../deploy/cloudformation/dev-cost-scheduler.yaml](../deploy/cloudformation/dev-cost-scheduler.yaml) | Layer 5.11: DEV cost scheduler (multi-nodegroup off-hours EKS scaling) |
| [operations/SERVERLESS_DEPLOYMENT_RUNBOOK.md](operations/SERVERLESS_DEPLOYMENT_RUNBOOK.md) | Serverless deployment operations |
| [operations/LAMBDA_CONFIGURATION_STANDARDS.md](operations/LAMBDA_CONFIGURATION_STANDARDS.md) | Lambda configuration standards |
| [operations/BOOTSTRAP_GUIDE.md](operations/BOOTSTRAP_GUIDE.md) | Bootstrap guide for initial setup |
| [operations/bootstrap-exemptions.md](operations/bootstrap-exemptions.md) | Bootstrap exemption documentation |
| [operations/EVENTBRIDGE_COST_OPTIMIZATION.md](operations/EVENTBRIDGE_COST_OPTIMIZATION.md) | EventBridge cost optimization |

### Resource Audits
| File | Purpose |
|------|---------|
| [RESOURCE_DEPLOYMENT_AUDIT.md](deployment/RESOURCE_DEPLOYMENT_AUDIT.md) | Comprehensive audit of CI/CD vs manually deployed resources, dependencies, deployment sequence |

### Architecture & Planning
| File | Purpose |
|------|---------|
| [TECHNICAL_SPEC.md](TECHNICAL_SPEC.md) | Technical specifications |
| [MULTI_CLOUD_ARCHITECTURE.md](cloud-strategy/MULTI_CLOUD_ARCHITECTURE.md) | Multi-cloud deployment strategy |
| [HITL_SANDBOX_ARCHITECTURE.md](design/HITL_SANDBOX_ARCHITECTURE.md) | Human-in-the-loop sandbox design |

### AWS & Infrastructure
| File | Purpose |
|------|---------|
| [CLOUDFORMATION_DRY_AUDIT.md](infrastructure/CLOUDFORMATION_DRY_AUDIT.md) | CloudFormation template duplication analysis and consolidation strategies |
| [DNSMASQ_INTEGRATION.md](integrations/DNSMASQ_INTEGRATION.md) | Comprehensive dnsmasq technical guide (Podman-first) |
| [DNS_THREAT_INTELLIGENCE.md](security/DNS_THREAT_INTELLIGENCE.md) | DNS blocklist service, threat feeds, K8s CronJob sync |
| [AWS_NAMING_AND_TAGGING_STANDARDS.md](reference/AWS_NAMING_AND_TAGGING_STANDARDS.md) | AWS resource naming conventions |
| [ARCHITECTURE_DECISION_VPC_CONNECTIVITY.md](architecture-decisions/ARCHITECTURE_DECISION_VPC_CONNECTIVITY.md) | VPC connectivity architecture decision |

### GovCloud & Compliance
| File | Purpose |
|------|---------|
| [GOVCLOUD_READINESS_TRACKER.md](cloud-strategy/GOVCLOUD_READINESS_TRACKER.md) | AWS GovCloud service availability tracker |
| [GOVCLOUD_MIGRATION_SUMMARY.md](cloud-strategy/GOVCLOUD_MIGRATION_SUMMARY.md) | GovCloud migration strategic planning |
| [CMMC_CERTIFICATION_PATHWAY.md](security/CMMC_CERTIFICATION_PATHWAY.md) | CMMC Level 3 certification roadmap |

### Certification Roadmaps (docs/compliance/roadmaps/)

Comprehensive certification roadmaps for government and defense market access.

| File | Timeline | Investment | Purpose |
|------|----------|------------|---------|
| [compliance/roadmaps/README.md](compliance/roadmaps/README.md) | - | - | Certification hierarchy, recommended order, decision matrix |
| [compliance/roadmaps/CMMC_LEVEL_2_ROADMAP.md](compliance/roadmaps/CMMC_LEVEL_2_ROADMAP.md) | 8-12 months | $200-350K | 110 NIST 800-171 controls, C3PAO assessment |
| [compliance/roadmaps/CMMC_LEVEL_3_ROADMAP.md](compliance/roadmaps/CMMC_LEVEL_3_ROADMAP.md) | +6-12 months | +$400-650K | 24 enhanced NIST 800-172 controls, Gov validation |
| [compliance/roadmaps/FEDRAMP_HIGH_ROADMAP.md](compliance/roadmaps/FEDRAMP_HIGH_ROADMAP.md) | 9-14 months | $250-350K | 421 NIST 800-53 controls, 3PAO assessment |
| [compliance/roadmaps/IL5_CERTIFICATION_ROADMAP.md](compliance/roadmaps/IL5_CERTIFICATION_ROADMAP.md) | +2-4 months | +$100-200K | STIG, FIPS 140-2/3, DISA CAP, DoD authorization |

**Recommended Starting Path:** CMMC Level 2 → FedRAMP High → IL5 → CMMC Level 3

### Features
| File | Purpose |
|------|---------|
| [ORCHESTRATOR_MODES.md](features/ORCHESTRATOR_MODES.md) | UI-configurable orchestrator deployment modes (on-demand, warm pool, hybrid) |
| [RAPID_PROTOTYPING_CAPABILITIES.md](features/RAPID_PROTOTYPING_CAPABILITIES.md) | Self-service test environments, multi-cloud support, permission model, cost governance |

### Integration & Development
| File | Purpose |
|------|---------|
| [BEDROCK_INTEGRATION_PLAN.md](integrations/BEDROCK_INTEGRATION_PLAN.md) | AWS Bedrock integration planning |
| [BEDROCK_INTEGRATION_README.md](integrations/BEDROCK_INTEGRATION_README.md) | Bedrock integration readme |
| [BEDROCK_SETUP_SUMMARY.md](integrations/BEDROCK_SETUP_SUMMARY.md) | Bedrock setup summary |
| [API_REFERENCE.md](reference/API_REFERENCE.md) | API documentation |
| [PRE_COMMIT_FALSE_POSITIVES.md](reference/PRE_COMMIT_FALSE_POSITIVES.md) | Pre-commit hook false positive registry and suppression documentation |

### Testing & Quality
| File | Purpose |
|------|---------|
| [TEST_PLAN.md](TEST_PLAN.md) | Testing strategy and plan |
| [SECURITY_ANALYSIS.md](SECURITY_ANALYSIS.md) | Security analysis |

### CI/CD
| File | Purpose |
|------|---------|
| [CICD_SETUP_GUIDE.md](deployment/CICD_SETUP_GUIDE.md) | CI/CD setup instructions (Podman-first strategy) |
| [DOCKER_BEST_PRACTICES.md](deployment/DOCKER_BEST_PRACTICES.md) | Container build best practices (Podman-first per ADR-049) |
| [GITHUB_ACTIONS_SETUP.md](deployment/GITHUB_ACTIONS_SETUP.md) | GitHub Actions configuration |
| [RELEASE_PLEASE_GUIDE.md](deployment/RELEASE_PLEASE_GUIDE.md) | Automated changelog & release management |

### CloudFormation Validation
| File | Purpose |
|------|---------|
| [../scripts/cfn-lint-wrapper.sh](../scripts/cfn-lint-wrapper.sh) | Wrapper script for cfn-lint with standardized exit code handling |
| [../scripts/validate_iam_actions.py](../scripts/validate_iam_actions.py) | IAM action validation against AWS service database |
| [../.github/workflows/nightly-iam-validation.yml](../.github/workflows/nightly-iam-validation.yml) | Nightly validation of CloudFormation templates and IAM actions |

### Buildspecs & Deployment Scripts (deploy/buildspecs/, deploy/scripts/)

Documentation and modular buildspec architecture for CodeBuild deployments.

| File | Purpose |
|------|---------|
| [../deploy/buildspecs/README.md](../deploy/buildspecs/README.md) | Modular buildspec architecture documentation |

**Application Layer Sub-Buildspecs (Layer 4):**
| File | Purpose |
|------|---------|
| [../deploy/buildspecs/buildspec-application-ecr.yml](../deploy/buildspecs/buildspec-application-ecr.yml) | ECR repositories, dnsmasq image build (Layer 4.1) |
| [../deploy/buildspecs/buildspec-application-bedrock.yml](../deploy/buildspecs/buildspec-application-bedrock.yml) | Bedrock, Cognito, Guardrails, Onboarding (Layer 4.2) |
| [../deploy/buildspecs/buildspec-application-irsa.yml](../deploy/buildspecs/buildspec-application-irsa.yml) | IRSA roles for EKS workloads (Layer 4.3) |
| [../deploy/buildspecs/buildspec-application-k8s.yml](../deploy/buildspecs/buildspec-application-k8s.yml) | Kubernetes manifest deployments (Layer 4.4) |

**Serverless Layer Sub-Buildspecs (Layer 6):**
| File | Purpose |
|------|---------|
| [../deploy/buildspecs/buildspec-serverless-security.yml](../deploy/buildspecs/buildspec-serverless-security.yml) | Permission boundary, IAM alerting (Layer 6.0) |
| [../deploy/buildspecs/buildspec-serverless-lambdas.yml](../deploy/buildspecs/buildspec-serverless-lambdas.yml) | Lambda packaging and S3 upload (Layer 6.1) |
| [../deploy/buildspecs/buildspec-serverless-stacks.yml](../deploy/buildspecs/buildspec-serverless-stacks.yml) | All serverless CloudFormation stacks (Layer 6.2) |

**Sandbox Layer Sub-Buildspecs (Layer 7):**
| File | Purpose |
|------|---------|
| [../deploy/buildspecs/buildspec-sandbox-infrastructure.yml](../deploy/buildspecs/buildspec-sandbox-infrastructure.yml) | Core sandbox, state table, IAM roles (Layer 7.1-7.4) |
| [../deploy/buildspecs/buildspec-sandbox-catalog.yml](../deploy/buildspecs/buildspec-sandbox-catalog.yml) | Service Catalog, Approval, Monitoring, Budgets (Layer 7.4-7.7) |
| [../deploy/buildspecs/buildspec-sandbox-advanced.yml](../deploy/buildspecs/buildspec-sandbox-advanced.yml) | Scheduler, Namespace Controller, Marketplace (Layer 7.8-7.10) |

**Shared Utility Scripts (deploy/scripts/):**
| File | Purpose |
|------|---------|
| [../deploy/scripts/cfn-deploy-helpers.sh](../deploy/scripts/cfn-deploy-helpers.sh) | CloudFormation deployment utilities (cfn_deploy_stack, cfn_get_stack_output) |
| [../deploy/scripts/package-lambdas.sh](../deploy/scripts/package-lambdas.sh) | Lambda packaging with S3 upload and hash-based change detection |
| [../deploy/scripts/validate-dependencies.sh](../deploy/scripts/validate-dependencies.sh) | Pre-deployment validation for stacks, env vars, EKS, SSM |
| [../deploy/scripts/eks-readiness.sh](../deploy/scripts/eks-readiness.sh) | EKS cluster and node readiness checks |

---

## src/ Directory - Core Source Code

### Agent Orchestration (Warm Pool Architecture)
| File | Purpose |
|------|---------|
| [../src/services/orchestration_service.py](../src/services/orchestration_service.py) | Dual-mode (MOCK/AWS) orchestration job management service |
| [../src/api/orchestration_endpoints.py](../src/api/orchestration_endpoints.py) | REST API + WebSocket endpoints for job submission/tracking |
| [../src/agents/orchestrator_server.py](../src/agents/orchestrator_server.py) | HTTP server with SQS queue consumer for warm pool deployment |
| [../src/agents/agent_orchestrator.py](../src/agents/agent_orchestrator.py) | System2Orchestrator - Main agent coordination logic |

### Test Environment Services (ADR-039 Phase 4)
| File | Purpose |
|------|---------|
| [../src/lambda/scheduled_provisioner.py](../src/lambda/scheduled_provisioner.py) | Lambda handler for scheduled environment provisioning |
| [../src/lambda/namespace_controller.py](../src/lambda/namespace_controller.py) | Lambda handler for EKS namespace lifecycle management |
| [../src/lambda/marketplace_handler.py](../src/lambda/marketplace_handler.py) | Lambda handlers for template marketplace submission/approval |
| [../src/services/k8s_namespace_service.py](../src/services/k8s_namespace_service.py) | High-level EKS namespace management service |

### Infrastructure Services
| File | Purpose |
|------|---------|
| [../src/services/checkpoint_persistence_service.py](../src/services/checkpoint_persistence_service.py) | DynamoDB-backed checkpoint persistence (replaces /tmp) |
| [../src/services/redis_cache_service.py](../src/services/redis_cache_service.py) | Distributed caching with TTL, pub/sub support, ElastiCache integration |

### Context Engineering Services (ADR-034)
| File | Purpose |
|------|---------|
| [../src/services/context_scoring_service.py](../src/services/context_scoring_service.py) | Multi-factor context relevance scoring |
| [../src/services/hierarchical_tool_registry.py](../src/services/hierarchical_tool_registry.py) | Layered tool organization and discovery |
| [../src/services/context_stack_manager.py](../src/services/context_stack_manager.py) | Push/pop context management with state persistence |
| [../src/services/three_way_retrieval_service.py](../src/services/three_way_retrieval_service.py) | Combined graph, vector, and keyword retrieval |
| [../src/services/hoprag_service.py](../src/services/hoprag_service.py) | Multi-hop RAG with graph traversal (with graceful degradation) |
| [../src/services/mcp_context_manager.py](../src/services/mcp_context_manager.py) | MCP protocol context coordination |
| [../src/services/community_summarization_service.py](../src/services/community_summarization_service.py) | Graph-based community detection and summarization |

### Cloud Abstraction Layer (ADR-004)
| File | Purpose |
|------|---------|
| [../src/abstractions/__init__.py](../src/abstractions/__init__.py) | Abstractions package exports |
| [../src/abstractions/cloud_provider.py](../src/abstractions/cloud_provider.py) | CloudProvider enum, CloudConfig dataclass |
| [../src/abstractions/graph_database.py](../src/abstractions/graph_database.py) | GraphDatabaseService abstract base class |
| [../src/abstractions/vector_database.py](../src/abstractions/vector_database.py) | VectorDatabaseService abstract base class |
| [../src/abstractions/llm_service.py](../src/abstractions/llm_service.py) | LLMService abstract base class |
| [../src/abstractions/storage_service.py](../src/abstractions/storage_service.py) | StorageService abstract base class |
| [../src/abstractions/secrets_service.py](../src/abstractions/secrets_service.py) | SecretsService abstract base class |

### Cloud Service Providers (ADR-004)
| File | Purpose |
|------|---------|
| [../src/services/providers/factory.py](../src/services/providers/factory.py) | CloudServiceFactory for provider selection |
| [../src/services/providers/aws/neptune_adapter.py](../src/services/providers/aws/neptune_adapter.py) | Neptune GraphDatabaseService adapter |
| [../src/services/providers/aws/opensearch_adapter.py](../src/services/providers/aws/opensearch_adapter.py) | OpenSearch VectorDatabaseService adapter |
| [../src/services/providers/aws/bedrock_adapter.py](../src/services/providers/aws/bedrock_adapter.py) | Bedrock LLMService adapter |
| [../src/services/providers/aws/s3_adapter.py](../src/services/providers/aws/s3_adapter.py) | S3 StorageService adapter |
| [../src/services/providers/aws/secrets_manager_adapter.py](../src/services/providers/aws/secrets_manager_adapter.py) | Secrets Manager SecretsService adapter |
| [../src/services/providers/azure/cosmos_graph_service.py](../src/services/providers/azure/cosmos_graph_service.py) | Cosmos DB GraphDatabaseService implementation |
| [../src/services/providers/azure/azure_ai_search_service.py](../src/services/providers/azure/azure_ai_search_service.py) | Azure AI Search VectorDatabaseService implementation |
| [../src/services/providers/azure/azure_openai_service.py](../src/services/providers/azure/azure_openai_service.py) | Azure OpenAI LLMService implementation |
| [../src/services/providers/azure/azure_blob_service.py](../src/services/providers/azure/azure_blob_service.py) | Azure Blob StorageService implementation |
| [../src/services/providers/azure/azure_keyvault_service.py](../src/services/providers/azure/azure_keyvault_service.py) | Azure Key Vault SecretsService implementation |
| [../src/services/providers/mock/mock_graph_service.py](../src/services/providers/mock/mock_graph_service.py) | Mock GraphDatabaseService for testing |
| [../src/services/providers/mock/mock_vector_service.py](../src/services/providers/mock/mock_vector_service.py) | Mock VectorDatabaseService for testing |
| [../src/services/providers/mock/mock_llm_service.py](../src/services/providers/mock/mock_llm_service.py) | Mock LLMService for testing |
| [../src/services/providers/mock/mock_storage_service.py](../src/services/providers/mock/mock_storage_service.py) | Mock StorageService for testing |
| [../src/services/providers/mock/mock_secrets_service.py](../src/services/providers/mock/mock_secrets_service.py) | Mock SecretsService for testing |

### External Tool Connectors
| File | Purpose |
|------|---------|
| [../src/services/connectors/__init__.py](../src/services/connectors/__init__.py) | Connector registry and discovery |
| [../src/services/external_tool_connectors.py](../src/services/external_tool_connectors.py) | Base class and common connectors (Jira, Slack, PagerDuty) |
| [../src/services/integrations/slack_adapter.py](../src/services/integrations/slack_adapter.py) | Slack OAuth 2.0, webhooks, channel management (ADR-048) |
| [../src/services/azure_devops_connector.py](../src/services/azure_devops_connector.py) | Azure DevOps work items and pipelines |
| [../src/services/crowdstrike_connector.py](../src/services/crowdstrike_connector.py) | CrowdStrike Falcon EDR integration |
| [../src/services/qualys_connector.py](../src/services/qualys_connector.py) | Qualys vulnerability management |
| [../src/services/snyk_connector.py](../src/services/snyk_connector.py) | Snyk developer security scanning |
| [../src/services/splunk_connector.py](../src/services/splunk_connector.py) | Splunk SIEM integration |
| [../src/services/servicenow_connector.py](../src/services/servicenow_connector.py) | ServiceNow ITSM integration |
| [../src/services/terraform_cloud_connector.py](../src/services/terraform_cloud_connector.py) | Terraform Cloud IaC management |

### AWS Agent Capability Services (ADR-037 Phase 2)
| File | Purpose |
|------|---------|
| [../src/services/oauth_delegation_service.py](../src/services/oauth_delegation_service.py) | OAuth 2.0 PKCE with token encryption |
| [../src/agents/browser_tool_agent.py](../src/agents/browser_tool_agent.py) | Playwright-based web automation |
| [../src/agents/code_interpreter_agent.py](../src/agents/code_interpreter_agent.py) | Multi-language sandboxed execution (11 languages) |
| [../src/services/semantic_tool_search.py](../src/services/semantic_tool_search.py) | Embedding-based tool discovery |
| [../src/services/deployment_history_correlator.py](../src/services/deployment_history_correlator.py) | Incident-deployment correlation |
| [../src/services/proactive_recommendation_engine.py](../src/services/proactive_recommendation_engine.py) | Operational recommendations engine |

### Repository Onboarding Services (ADR-043)
| File | Purpose |
|------|---------|
| [../src/services/oauth_provider_service.py](../src/services/oauth_provider_service.py) | OAuth 2.0 authorization flows for GitHub/GitLab |
| [../src/services/repository_onboard_service.py](../src/services/repository_onboard_service.py) | Repository CRUD and ingestion job management |
| [../src/services/webhook_registration_service.py](../src/services/webhook_registration_service.py) | Webhook setup for incremental sync |
| [../src/api/oauth_endpoints.py](../src/api/oauth_endpoints.py) | OAuth callback handling API endpoints |
| [../src/api/repository_endpoints.py](../src/api/repository_endpoints.py) | REST API for repository onboarding |

### Agent Scheduling Services (ADR-055)
| File | Purpose |
|------|---------|
| [../src/services/scheduling/models.py](../src/services/scheduling/models.py) | Data models (JobType, Priority, ScheduleStatus, QueueStatus, TimelineEntry) |
| [../src/services/scheduling/scheduling_service.py](../src/services/scheduling/scheduling_service.py) | Core scheduling service with CRUD, queue status, timeline, dispatcher |
| [../src/api/scheduling_endpoints.py](../src/api/scheduling_endpoints.py) | REST API endpoints for scheduling and queue management |

---

## deploy/ Directory - Infrastructure & Deployment

### Kubernetes Manifests

All services follow the base/overlay Kustomize pattern. Use overlays for environment-specific deployments:
- DEV: `kubectl apply -k deploy/kubernetes/{service}/overlays/dev/`
- QA: `kubectl apply -k deploy/kubernetes/{service}/overlays/qa/`
- PROD: `kubectl apply -k deploy/kubernetes/{service}/overlays/prod/`

| File | Purpose |
|------|---------|
| [../deploy/kubernetes/aura-api/README.md](../deploy/kubernetes/aura-api/README.md) | API deployment guide |
| [../deploy/kubernetes/aura-api/kustomization.yaml](../deploy/kubernetes/aura-api/kustomization.yaml) | Root kustomization (references base) |
| [../deploy/kubernetes/aura-api/base/configmap.yaml](../deploy/kubernetes/aura-api/base/configmap.yaml) | Database endpoints configuration |
| [../deploy/kubernetes/aura-api/base/deployment.yaml](../deploy/kubernetes/aura-api/base/deployment.yaml) | API pod specification |
| [../deploy/kubernetes/aura-api/base/service.yaml](../deploy/kubernetes/aura-api/base/service.yaml) | ClusterIP service |
| [../deploy/kubernetes/aura-api/base/serviceaccount.yaml](../deploy/kubernetes/aura-api/base/serviceaccount.yaml) | IRSA service account |
| [../deploy/kubernetes/memory-service/kustomization.yaml](../deploy/kubernetes/memory-service/kustomization.yaml) | Root kustomization (references base) |
| [../deploy/kubernetes/memory-service/base/deployment.yaml](../deploy/kubernetes/memory-service/base/deployment.yaml) | Neural Memory service deployment |
| [../deploy/kubernetes/dnsmasq-daemonset.yaml](../deploy/kubernetes/dnsmasq-daemonset.yaml) | dnsmasq DaemonSet |
| [../deploy/kubernetes/dnsmasq-blocklist-sync.yaml](../deploy/kubernetes/dnsmasq-blocklist-sync.yaml) | DNS blocklist S3→ConfigMap CronJob |

### Service Configuration (Environment Variables)
| File | Purpose |
|------|---------|
| [../deploy/kubernetes/aura-service-config/base/configmap.yaml](../deploy/kubernetes/aura-service-config/base/configmap.yaml) | Centralized service environment variables |
| [../deploy/kubernetes/aura-service-config/base/kustomization.yaml](../deploy/kubernetes/aura-service-config/base/kustomization.yaml) | Kustomize base configuration |
| [../deploy/kubernetes/aura-service-config/overlays/dev/kustomization.yaml](../deploy/kubernetes/aura-service-config/overlays/dev/kustomization.yaml) | Dev environment overlay |
| [../deploy/kubernetes/aura-service-config/overlays/qa/kustomization.yaml](../deploy/kubernetes/aura-service-config/overlays/qa/kustomization.yaml) | QA environment overlay |
| [../deploy/kubernetes/aura-service-config/overlays/prod/kustomization.yaml](../deploy/kubernetes/aura-service-config/overlays/prod/kustomization.yaml) | Production environment overlay |

### ArgoCD Applications
| File | Purpose |
|------|---------|
| [../deploy/kubernetes/argocd/applications/aura-api.yaml](../deploy/kubernetes/argocd/applications/aura-api.yaml) | ArgoCD Application for API service |
| [../deploy/kubernetes/argocd/applications/aura-frontend.yaml](../deploy/kubernetes/argocd/applications/aura-frontend.yaml) | ArgoCD Application for frontend |
| [../deploy/kubernetes/argocd/applications/memory-service.yaml](../deploy/kubernetes/argocd/applications/memory-service.yaml) | ArgoCD Application for Neural Memory service (NEW) |

### Agent Orchestrator (Warm Pool & Deployment Modes)
| File | Purpose |
|------|---------|
| [../src/api/orchestrator_settings_endpoints.py](../src/api/orchestrator_settings_endpoints.py) | REST API for deployment mode configuration |
| [../src/services/orchestrator_mode_service.py](../src/services/orchestrator_mode_service.py) | Mode transition state machine service |
| [../deploy/kubernetes/agent-orchestrator/base/configmap.yaml](../deploy/kubernetes/agent-orchestrator/base/configmap.yaml) | Parameterized orchestrator configuration |
| [../deploy/kubernetes/agent-orchestrator/base/deployment.yaml](../deploy/kubernetes/agent-orchestrator/base/deployment.yaml) | Warm pool deployment with health probes |
| [../deploy/kubernetes/agent-orchestrator/base/service.yaml](../deploy/kubernetes/agent-orchestrator/base/service.yaml) | ClusterIP service for internal access |
| [../deploy/kubernetes/agent-orchestrator/base/rbac.yaml](../deploy/kubernetes/agent-orchestrator/base/rbac.yaml) | K8s RBAC for warm pool scaling |
| [../deploy/kubernetes/agent-orchestrator/kustomization.yaml](../deploy/kubernetes/agent-orchestrator/kustomization.yaml) | Kustomize wrapper |
| [../deploy/kubernetes/agent-orchestrator/overlays/dev/kustomization.yaml](../deploy/kubernetes/agent-orchestrator/overlays/dev/kustomization.yaml) | Dev environment overlay |
| [../deploy/kubernetes/agent-orchestrator/overlays/qa/kustomization.yaml](../deploy/kubernetes/agent-orchestrator/overlays/qa/kustomization.yaml) | QA environment overlay |
| [../deploy/kubernetes/agent-orchestrator/overlays/prod/kustomization.yaml](../deploy/kubernetes/agent-orchestrator/overlays/prod/kustomization.yaml) | Production environment overlay |

### Docker
| File | Purpose |
|------|---------|
| [../deploy/docker/api/Dockerfile.api](../deploy/docker/api/Dockerfile.api) | FastAPI application image |
| [../deploy/docker/agents/Dockerfile.orchestrator](../deploy/docker/agents/Dockerfile.orchestrator) | Agent orchestrator image (warm pool HTTP server) |
| [../deploy/docker/dnsmasq/Dockerfile.alpine](../deploy/docker/dnsmasq/Dockerfile.alpine) | dnsmasq with DNSSEC |

### Configuration
| File | Purpose |
|------|---------|
| [../deploy/config/.env.example](../deploy/config/.env.example) | Environment variables template |
| [configuration/DIAGRAM_SERVICE_CONFIGURATION.md](configuration/DIAGRAM_SERVICE_CONFIGURATION.md) | Diagram generation service configuration (mock vs real API mode) |

---

## frontend/ Directory - React Dashboard

### Frontend Application
| File | Purpose |
|------|---------|
| [../frontend/README.md](../frontend/README.md) | Frontend quick start and API integration guide |
| [../frontend/package.json](../frontend/package.json) | NPM dependencies (React 18, Vite 6, Tailwind) |
| [../frontend/vite.config.js](../frontend/vite.config.js) | Vite config with API proxy |
| [../frontend/src/components/ApprovalDashboard.jsx](../frontend/src/components/ApprovalDashboard.jsx) | HITL approval workflow UI |
| [../frontend/src/components/LoginPage.jsx](../frontend/src/components/LoginPage.jsx) | Cognito OAuth login page |
| [../frontend/src/components/AuthCallback.jsx](../frontend/src/components/AuthCallback.jsx) | OAuth callback handler |
| [../frontend/src/components/ProtectedRoute.jsx](../frontend/src/components/ProtectedRoute.jsx) | Route wrapper with RBAC |
| [../frontend/src/components/UserMenu.jsx](../frontend/src/components/UserMenu.jsx) | Sidebar user dropdown |
| [../frontend/src/context/AuthContext.jsx](../frontend/src/context/AuthContext.jsx) | Authentication state management |
| [../frontend/src/config/auth.js](../frontend/src/config/auth.js) | Cognito configuration |
| [../frontend/src/services/approvalApi.js](../frontend/src/services/approvalApi.js) | API client for `/api/v1/approvals/*` |
| [../frontend/src/services/environmentsApi.js](../frontend/src/services/environmentsApi.js) | API client for test environments with mock data fallback |
| [../frontend/src/components/Environments.jsx](../frontend/src/components/Environments.jsx) | Self-service test environment management page |
| [../frontend/src/components/EnvironmentDashboard.jsx](../frontend/src/components/EnvironmentDashboard.jsx) | Detailed test environment view with tabs |

### Frontend Hooks (Accessibility)
| File | Purpose |
|------|---------|
| [../frontend/src/hooks/useFocusTrap.jsx](../frontend/src/hooks/useFocusTrap.jsx) | Focus trap hook for modal accessibility (WCAG 2.1 AA compliance) |

### Repository Onboarding Components (ADR-043)
| File | Purpose |
|------|---------|
| [../frontend/src/components/repositories/RepositoriesList.jsx](../frontend/src/components/repositories/RepositoriesList.jsx) | Repository listing page |
| [../frontend/src/components/repositories/RepositoryOnboardWizard.jsx](../frontend/src/components/repositories/RepositoryOnboardWizard.jsx) | Multi-step wizard container |
| [../frontend/src/components/repositories/RepositoryCard.jsx](../frontend/src/components/repositories/RepositoryCard.jsx) | Individual repository cards |
| [../frontend/src/components/repositories/steps/ConnectProviderStep.jsx](../frontend/src/components/repositories/steps/ConnectProviderStep.jsx) | OAuth provider selection (Step 1) |
| [../frontend/src/components/repositories/steps/SelectRepositoriesStep.jsx](../frontend/src/components/repositories/steps/SelectRepositoriesStep.jsx) | Repository multi-select (Step 2) |
| [../frontend/src/components/repositories/steps/ConfigureAnalysisStep.jsx](../frontend/src/components/repositories/steps/ConfigureAnalysisStep.jsx) | Branch/language config (Step 3) |
| [../frontend/src/components/repositories/steps/ReviewStep.jsx](../frontend/src/components/repositories/steps/ReviewStep.jsx) | Configuration review (Step 4) |
| [../frontend/src/components/repositories/steps/CompletionStep.jsx](../frontend/src/components/repositories/steps/CompletionStep.jsx) | Ingestion results (Step 5) |
| [../frontend/src/context/RepositoryContext.jsx](../frontend/src/context/RepositoryContext.jsx) | Repository state management |
| [../frontend/src/services/repositoryApi.js](../frontend/src/services/repositoryApi.js) | API client for repository operations |

### Customer Onboarding Components
| File | Purpose |
|------|---------|
| [../frontend/src/components/onboarding/index.js](../frontend/src/components/onboarding/index.js) | Onboarding components barrel export |
| [../frontend/src/components/onboarding/WelcomeModal.jsx](../frontend/src/components/onboarding/WelcomeModal.jsx) | First-time user welcome modal (P0) with glass morphism design |
| [../frontend/src/components/onboarding/OnboardingChecklist.jsx](../frontend/src/components/onboarding/OnboardingChecklist.jsx) | Fixed bottom-right widget tracking 5 setup steps (P1) |
| [../frontend/src/components/onboarding/ChecklistItem.jsx](../frontend/src/components/onboarding/ChecklistItem.jsx) | Individual checklist item component |
| [../frontend/src/components/onboarding/WelcomeTour.jsx](../frontend/src/components/onboarding/WelcomeTour.jsx) | Joyride-style guided tour with 7 steps (P2) |
| [../frontend/src/components/onboarding/TourTooltip.jsx](../frontend/src/components/onboarding/TourTooltip.jsx) | Tour step tooltip component |
| [../frontend/src/components/onboarding/TourSpotlight.jsx](../frontend/src/components/onboarding/TourSpotlight.jsx) | Tour step spotlight overlay |
| [../frontend/src/components/onboarding/FeatureTooltip.jsx](../frontend/src/components/onboarding/FeatureTooltip.jsx) | In-app tooltips for complex features (P3) |
| [../frontend/src/components/onboarding/TooltipIndicator.jsx](../frontend/src/components/onboarding/TooltipIndicator.jsx) | Pulsing indicator for feature tooltips |
| [../frontend/src/components/onboarding/VideoModal.jsx](../frontend/src/components/onboarding/VideoModal.jsx) | Video catalog modal with progress tracking (P4) |
| [../frontend/src/components/onboarding/VideoPlayer.jsx](../frontend/src/components/onboarding/VideoPlayer.jsx) | Embedded video player component |
| [../frontend/src/components/onboarding/TeamInviteWizard.jsx](../frontend/src/components/onboarding/TeamInviteWizard.jsx) | Multi-step team invitation wizard (P5) |
| [../frontend/src/components/onboarding/steps/EmailEntryStep.jsx](../frontend/src/components/onboarding/steps/EmailEntryStep.jsx) | Team invite email entry step |
| [../frontend/src/components/onboarding/steps/RoleAssignmentStep.jsx](../frontend/src/components/onboarding/steps/RoleAssignmentStep.jsx) | Team invite role assignment step |
| [../frontend/src/components/onboarding/steps/InviteReviewStep.jsx](../frontend/src/components/onboarding/steps/InviteReviewStep.jsx) | Team invite review step |
| [../frontend/src/components/onboarding/steps/InviteCompletionStep.jsx](../frontend/src/components/onboarding/steps/InviteCompletionStep.jsx) | Team invite completion step |
| [../frontend/src/components/onboarding/DevToolbar.jsx](../frontend/src/components/onboarding/DevToolbar.jsx) | Developer toolbar for onboarding testing |
| [../frontend/src/context/OnboardingContext.jsx](../frontend/src/context/OnboardingContext.jsx) | Onboarding state management with localStorage fallback |
| [../frontend/src/services/onboardingApi.js](../frontend/src/services/onboardingApi.js) | API client for onboarding operations (dev mode support)

### Documentation Agent Components (ADR-056)
| File | Purpose |
|------|---------|
| [../frontend/src/components/documentation/DocumentationDashboard.jsx](../frontend/src/components/documentation/DocumentationDashboard.jsx) | Tab-based dashboard with SSE streaming for real-time generation |
| [../frontend/src/components/documentation/DiagramViewer.jsx](../frontend/src/components/documentation/DiagramViewer.jsx) | Mermaid.js rendering with zoom/pan controls |
| [../frontend/src/components/documentation/ConfidenceGauge.jsx](../frontend/src/components/documentation/ConfidenceGauge.jsx) | SVG semicircular gauge with ARIA accessibility |
| [../frontend/src/hooks/useDocumentationData.js](../frontend/src/hooks/useDocumentationData.js) | Custom hook with abort controller for documentation data |
| [../frontend/src/services/documentationApi.js](../frontend/src/services/documentationApi.js) | API client with SSE support for documentation generation |

---

## sdk/typescript/ Directory - TypeScript SDK

### SDK Package
| File | Purpose |
|------|---------|
| [../sdk/typescript/README.md](../sdk/typescript/README.md) | SDK quick start and API reference |
| [../sdk/typescript/package.json](../sdk/typescript/package.json) | NPM package `@aenealabs/aura-sdk` |
| [../sdk/typescript/tsconfig.json](../sdk/typescript/tsconfig.json) | TypeScript configuration |
| [../sdk/typescript/tsup.config.ts](../sdk/typescript/tsup.config.ts) | Build configuration (dual CJS/ESM) |
| [../sdk/typescript/vitest.config.ts](../sdk/typescript/vitest.config.ts) | Test configuration |

### SDK Source
| File | Purpose |
|------|---------|
| [../sdk/typescript/src/index.ts](../sdk/typescript/src/index.ts) | Main entry point |
| [../sdk/typescript/src/react.ts](../sdk/typescript/src/react.ts) | React hooks entry point |
| [../sdk/typescript/src/client/AuraClient.ts](../sdk/typescript/src/client/AuraClient.ts) | API client with modular APIs |
| [../sdk/typescript/src/hooks/index.ts](../sdk/typescript/src/hooks/index.ts) | React hooks (useApprovals, useVulnerabilities, etc.) |
| [../sdk/typescript/src/types/index.ts](../sdk/typescript/src/types/index.ts) | TypeScript type definitions |
| [../sdk/typescript/src/utils/index.ts](../sdk/typescript/src/utils/index.ts) | Utility functions (severity, formatting, diff parsing) |

---

## vscode-extension/ Directory - VS Code Extension

### Extension Package
| File | Purpose |
|------|---------|
| [../vscode-extension/README.md](../vscode-extension/README.md) | Extension documentation |
| [../vscode-extension/package.json](../vscode-extension/package.json) | VS Code extension manifest |
| [../vscode-extension/tsconfig.json](../vscode-extension/tsconfig.json) | TypeScript configuration |

### Extension Source
| File | Purpose |
|------|---------|
| [../vscode-extension/src/extension.ts](../vscode-extension/src/extension.ts) | Extension entry point and activation |
| [../vscode-extension/src/client.ts](../vscode-extension/src/client.ts) | API client for Aura backend |
| [../vscode-extension/src/providers/findingsProvider.ts](../vscode-extension/src/providers/findingsProvider.ts) | Findings tree view provider |
| [../vscode-extension/src/providers/patchesProvider.ts](../vscode-extension/src/providers/patchesProvider.ts) | Patches tree view provider |
| [../vscode-extension/src/providers/approvalsProvider.ts](../vscode-extension/src/providers/approvalsProvider.ts) | HITL approvals tree view provider |
| [../vscode-extension/src/providers/codeLensProvider.ts](../vscode-extension/src/providers/codeLensProvider.ts) | Inline code annotations |
| [../vscode-extension/src/providers/diagnosticsProvider.ts](../vscode-extension/src/providers/diagnosticsProvider.ts) | VS Code Problems panel integration |

---

## agent-config/ Directory - Agent Context & Schemas

### Institutional Memory
| File | Purpose |
|------|---------|
| [../agent-config/GUARDRAILS.md](../agent-config/GUARDRAILS.md) | Institutional memory for specialized agents (lessons learned) |

### Agent Templates
| File | Purpose |
|------|---------|
| [../agent-config/agents/security-code-reviewer.md](../agent-config/agents/security-code-reviewer.md) | Security code review agent template |
| [../agent-config/agents/code-quality-reviewer.md](../agent-config/agents/code-quality-reviewer.md) | Code quality review agent template |
| [../agent-config/agents/performance-reviewer.md](../agent-config/agents/performance-reviewer.md) | Performance review agent template |
| [../agent-config/agents/test-coverage-reviewer.md](../agent-config/agents/test-coverage-reviewer.md) | Test coverage review agent template |
| [../agent-config/agents/documentation-accuracy-reviewer.md](../agent-config/agents/documentation-accuracy-reviewer.md) | Documentation accuracy agent template |

### Design Workflows
| File | Purpose |
|------|---------|
| [../agent-config/design-workflows/design-principles.md](../agent-config/design-workflows/design-principles.md) | Enterprise UI/UX design system |
| [../agent-config/design-workflows/design-review-workflow.md](../agent-config/design-workflows/design-review-workflow.md) | 7-phase automated design review |
| [../agent-config/design-workflows/app-ui-blueprint.md](../agent-config/design-workflows/app-ui-blueprint.md) | User personas, workflows, screen inventory, implementation roadmap |

### Task Schemas
| File | Purpose |
|------|---------|
| [../agent-config/schemas/cicd-schema.md](../agent-config/schemas/cicd-schema.md) | CI/CD task schema for specialized agents |

---

## docs/specifications/ - Technical Specifications

Detailed technical specifications for complex architectural components.

| File | Lines | Purpose |
|------|-------|---------|
| [specifications/SEMANTIC_GUARDRAILS_ENGINE_SPEC.md](specifications/SEMANTIC_GUARDRAILS_ENGINE_SPEC.md) | ~1,900 | ADR-065 implementation spec: gRPC/REST APIs, data models, detection algorithms, threat corpus |

---

## research/ Directory - Research & Innovation

### Research Findings
| File | Purpose |
|------|---------|
| [../research/RESEARCH_FINDINGS_CI_CD_DESIGN_WORKFLOWS.md](../research/RESEARCH_FINDINGS_CI_CD_DESIGN_WORKFLOWS.md) | Research on CI/CD automation patterns |

### Competitive Analysis
| File | Purpose |
|------|---------|
| [../research/MICROSOFT_FOUNDRY_COMPARATIVE_ANALYSIS.md](../research/MICROSOFT_FOUNDRY_COMPARATIVE_ANALYSIS.md) | Microsoft Foundry feature analysis and adoption strategy |
| [../research/competitive-analysis/CLAUDE_CODE_SECURITY_VS_AURA.md](research/competitive-analysis/CLAUDE_CODE_SECURITY_VS_AURA.md) | Anthropic Claude Code Security vs Aura security platform (815 lines) |

### Neural Memory Research
| File | Purpose |
|------|---------|
| [../research/papers/neural-memory-2025/](../research/papers/neural-memory-2025/) | Titans & MIRAS analysis (test-time training, deep MLP memory) |

### Architecture Proposals
| File | Purpose |
|------|---------|
| [../research/proposals/ADR-024-TITAN-NEURAL-MEMORY.md](../research/proposals/ADR-024-TITAN-NEURAL-MEMORY.md) | Original proposal - Now deployed as ADR-024 |
| [../docs/research/proposals/RLM-JEPA-INTEGRATION-PROPOSAL.md](research/proposals/RLM-JEPA-INTEGRATION-PROPOSAL.md) | RLM + VL-JEPA integration proposal for ADR-051 (MIT CSAIL + Meta FAIR research) |
| [research/proposals/aerospace-defense-systems-engineer-agent.md](research/proposals/aerospace-defense-systems-engineer-agent.md) | PROP-2026-004: Aerospace & Defense Systems Engineer agent proposal (MBSE, DO-178C, FAA certification) |

### Titan Neural Memory Services (ADR-024)
| File | Purpose |
|------|---------|
| [../src/services/titan_memory_service.py](../src/services/titan_memory_service.py) | Core Titan memory service with TTT support |
| [../src/services/titan_cognitive_integration.py](../src/services/titan_cognitive_integration.py) | Memory agent and cognitive integration |
| [../src/services/titan_embedding_service.py](../src/services/titan_embedding_service.py) | Embedding service for memory |
| [../src/services/models/deep_mlp_memory.py](../src/services/models/deep_mlp_memory.py) | Deep MLP memory module |
| [../src/services/models/miras_config.py](../src/services/models/miras_config.py) | MIRAS configuration |
| [../src/services/memory_backends/](../src/services/memory_backends/) | CPU/GPU memory backends |
| [../src/services/memory_consolidation.py](../src/services/memory_consolidation.py) | Memory consolidation and size limiting |
| [../src/services/neural_memory_audit.py](../src/services/neural_memory_audit.py) | Audit logging for neural memory |

---

## docs/architecture-decisions/ - Architecture Decision Records

### Architecture Decision Records (ADRs)
| File | Status | Purpose |
|------|--------|---------|
| [architecture-decisions/README.md](architecture-decisions/README.md) | Index | ADR index and guidelines |
| [architecture-decisions/ADR-001-dynamodb-separate-tables.md](architecture-decisions/ADR-001-dynamodb-separate-tables.md) | Deployed | Separate DynamoDB tables for job types |
| [architecture-decisions/ADR-002-vpc-endpoints-strategy.md](architecture-decisions/ADR-002-vpc-endpoints-strategy.md) | Deployed | VPC Endpoints over NAT Gateways |
| [architecture-decisions/ADR-003-eks-ec2-nodes-for-govcloud.md](architecture-decisions/ADR-003-eks-ec2-nodes-for-govcloud.md) | Deployed | EKS EC2 Managed Node Groups |
| [architecture-decisions/ADR-004-multi-cloud-architecture.md](architecture-decisions/ADR-004-multi-cloud-architecture.md) | Deployed | Cloud Abstraction Layer for Multi-Cloud (AWS/Azure) |
| [architecture-decisions/ADR-005-hitl-sandbox-architecture.md](architecture-decisions/ADR-005-hitl-sandbox-architecture.md) | Deployed | HITL Sandbox Testing |
| [architecture-decisions/ADR-006-three-tier-dnsmasq-integration.md](architecture-decisions/ADR-006-three-tier-dnsmasq-integration.md) | Deployed | Three-Tier dnsmasq |
| [architecture-decisions/ADR-007-modular-cicd-strategy.md](architecture-decisions/ADR-007-modular-cicd-strategy.md) | Deployed | Modular CI/CD Strategy |
| [architecture-decisions/ADR-008-bedrock-llm-cost-controls.md](architecture-decisions/ADR-008-bedrock-llm-cost-controls.md) | Deployed | Bedrock LLM Cost Controls |
| [architecture-decisions/ADR-009-drift-protection-dual-layer.md](architecture-decisions/ADR-009-drift-protection-dual-layer.md) | Deployed | Dual-Layer Drift Protection |
| [architecture-decisions/ADR-010-autonomous-adr-generation-pipeline.md](architecture-decisions/ADR-010-autonomous-adr-generation-pipeline.md) | Deployed | Autonomous ADR Generation |
| [architecture-decisions/ADR-011-vpc-access-via-eks-deployment.md](architecture-decisions/ADR-011-vpc-access-via-eks-deployment.md) | Deployed | VPC Access via EKS Deployment |
| [architecture-decisions/ADR-012-opensearch-iam-master-user.md](architecture-decisions/ADR-012-opensearch-iam-master-user.md) | Deployed | OpenSearch IAM Master User Authentication |
| [architecture-decisions/ADR-013-service-adapter-factory-pattern.md](architecture-decisions/ADR-013-service-adapter-factory-pattern.md) | Deployed | Service Adapter and Factory Pattern |
| [architecture-decisions/ADR-014-llm-enhanced-agent-search-pattern.md](architecture-decisions/ADR-014-llm-enhanced-agent-search-pattern.md) | Deployed | LLM-Enhanced Agent Search Pattern |
| [architecture-decisions/ADR-015-tiered-llm-model-strategy.md](architecture-decisions/ADR-015-tiered-llm-model-strategy.md) | Deployed | Tiered LLM Model Strategy |
| [architecture-decisions/ADR-016-hitl-auto-escalation-strategy.md](architecture-decisions/ADR-016-hitl-auto-escalation-strategy.md) | Deployed | HITL Auto-Escalation Strategy |
| [architecture-decisions/ADR-017-dynamic-sandbox-resource-allocation.md](architecture-decisions/ADR-017-dynamic-sandbox-resource-allocation.md) | Deployed | Dynamic Sandbox Resource Allocation |
| [architecture-decisions/ADR-018-meta-orchestrator-dynamic-agent-spawning.md](architecture-decisions/ADR-018-meta-orchestrator-dynamic-agent-spawning.md) | Deployed | MetaOrchestrator Dynamic Agent Spawning |
| [architecture-decisions/ADR-019-market-intelligence-agent.md](architecture-decisions/ADR-019-market-intelligence-agent.md) | Deployed | AWS Security Agent Capability Parity |
| [architecture-decisions/ADR-020-private-ecr-base-images.md](architecture-decisions/ADR-020-private-ecr-base-images.md) | Deployed | Private ECR Base Images for Controlled Supply Chain |
| [architecture-decisions/ADR-021-guardrails-cognitive-architecture.md](architecture-decisions/ADR-021-guardrails-cognitive-architecture.md) | Deployed | Guardrails Cognitive Architecture for Specialized Agents |
| [architecture-decisions/ADR-022-gitops-kubernetes-deployment.md](architecture-decisions/ADR-022-gitops-kubernetes-deployment.md) | Deployed | GitOps with ArgoCD and Argo Rollouts |
| [architecture-decisions/ADR-023-agentcore-gateway-integration.md](architecture-decisions/ADR-023-agentcore-gateway-integration.md) | Deployed | Dual-Track Architecture (Defense/Enterprise Markets) |
| [architecture-decisions/ADR-024-titan-neural-memory.md](architecture-decisions/ADR-024-titan-neural-memory.md) | Deployed | Titan Neural Memory Architecture (Deep MLP, MIRAS, TTT) |
| [architecture-decisions/ADR-025-runtime-incident-agent.md](architecture-decisions/ADR-025-runtime-incident-agent.md) | Deployed | RuntimeIncidentAgent for Code-Aware Incident Response |
| [architecture-decisions/ADR-026-bootstrap-once-update-forever.md](architecture-decisions/ADR-026-bootstrap-once-update-forever.md) | Deployed | Bootstrap Once, Update Forever Pattern for Immutable Infrastructure |
| [architecture-decisions/ADR-027-security-group-management-pattern.md](architecture-decisions/ADR-027-security-group-management-pattern.md) | Deployed | Security Group Management with Separate Ingress Resources |
| [architecture-decisions/ADR-028-foundry-capability-adoption.md](architecture-decisions/ADR-028-foundry-capability-adoption.md) | Deployed | Microsoft Foundry Capability Adoption (8 phases: Model Router, OTel, Agentic Retrieval, VS Code, SDK, A2A, Red-Team, Connectors) |
| [architecture-decisions/ADR-029-agent-optimization-roadmap.md](architecture-decisions/ADR-029-agent-optimization-roadmap.md) | Deployed | Agent Optimization Roadmap - Phases 1.3, 2.2, 2.3 ENABLED BY DEFAULT (Dec 16, 2025), Phase 3 Agent0 planned H2 2026 |
| [architecture-decisions/ADR-030-chat-assistant-architecture.md](architecture-decisions/ADR-030-chat-assistant-architecture.md) | Deployed | Chat Assistant Architecture - AI-Powered Platform Support |
| [architecture-decisions/ADR-031-neptune-deployment-mode.md](architecture-decisions/ADR-031-neptune-deployment-mode.md) | Deployed | Neptune Deployment Mode Configuration (Provisioned vs Serverless) |
| [architecture-decisions/ADR-032-configurable-autonomy-framework.md](architecture-decisions/ADR-032-configurable-autonomy-framework.md) | Deployed | Configurable Autonomy Framework for 85% Autonomous Operation |
| [architecture-decisions/ADR-033-runbook-agent.md](architecture-decisions/ADR-033-runbook-agent.md) | Deployed | Runbook Agent for Automated Incident Response |
| [architecture-decisions/ADR-034-context-engineering-implementation.md](architecture-decisions/ADR-034-context-engineering-implementation.md) | Deployed | Context Engineering Implementation (7 services deployed Dec 16, 2025) |
| [architecture-decisions/ADR-035-dedicated-docker-build-project.md](architecture-decisions/ADR-035-dedicated-docker-build-project.md) | Deployed | Dedicated Docker-Podman Build CodeBuild Project for Fast Container Builds |
| [architecture-decisions/ADR-036-multi-platform-container-builds.md](architecture-decisions/ADR-036-multi-platform-container-builds.md) | Deployed | Multi-Platform Container Builds for ARM64/AMD64 |
| [architecture-decisions/ADR-037-aws-agent-capability-replication.md](architecture-decisions/ADR-037-aws-agent-capability-replication.md) | Deployed | AWS Agent Capability Replication (27 services total - Phase 2 deployed Dec 16, 2025) |
| [architecture-decisions/ADR-038-codebuild-caching-optimization.md](architecture-decisions/ADR-038-codebuild-caching-optimization.md) | Deployed | CodeBuild Caching Optimization |
| [architecture-decisions/ADR-039-self-service-test-environments.md](architecture-decisions/ADR-039-self-service-test-environments.md) | Deployed | Self-Service Test Environment Provisioning (4 phases complete) |
| [architecture-decisions/ADR-040-configurable-compliance-settings.md](architecture-decisions/ADR-040-configurable-compliance-settings.md) | Deployed | Configurable Compliance Settings (Log Retention Sync deployed to dev) |
| [architecture-decisions/ADR-041-aws-required-wildcards-defense-in-depth.md](architecture-decisions/ADR-041-aws-required-wildcards-defense-in-depth.md) | Accepted | AWS-Required Wildcards with Defense-in-Depth Compensating Controls |
| [architecture-decisions/ADR-042-real-time-agent-intervention.md](architecture-decisions/ADR-042-real-time-agent-intervention.md) | Deployed | Real-Time Agent Intervention Architecture (Phase 1: CloudTrail, IAM Alerting, Checkpoints) |
| [architecture-decisions/ADR-043-repository-onboarding-wizard.md](architecture-decisions/ADR-043-repository-onboarding-wizard.md) | Deployed | Repository Onboarding Wizard with OAuth Integration (GitHub/GitLab) |
| [architecture-decisions/ADR-044-enhanced-node-detail-panel.md](architecture-decisions/ADR-044-enhanced-node-detail-panel.md) | Deployed | Enhanced Node Detail Panel for GraphRAG Explorer |
| [architecture-decisions/ADR-045-external-documentation-links.md](architecture-decisions/ADR-045-external-documentation-links.md) | Deployed | External Documentation Links for Code Navigation |
| [architecture-decisions/ADR-046-support-ticketing-connectors.md](architecture-decisions/ADR-046-support-ticketing-connectors.md) | Deployed | Support Ticketing Connector Framework (GitHub Issues, Zendesk, Linear, ServiceNow) |
| [architecture-decisions/ADR-047-customer-onboarding-features.md](architecture-decisions/ADR-047-customer-onboarding-features.md) | Deployed | Customer Onboarding Features (Welcome Modal, Checklist, Tour, Tooltips, Videos, Team Invitations) |
| [architecture-decisions/ADR-048-developer-tools-data-platform-integrations.md](architecture-decisions/ADR-048-developer-tools-data-platform-integrations.md) | Deployed | Developer Tools & Data Platform Integrations (VSCode, PyCharm, JupyterLab, Dataiku, Fivetran) |
| [architecture-decisions/ADR-049-self-hosted-deployment-strategy.md](architecture-decisions/ADR-049-self-hosted-deployment-strategy.md) | Deployed | Self-Hosted Deployment Strategy (Podman, Hybrid LLM, Windows/Linux/macOS) |
| [architecture-decisions/ADR-050-self-play-swe-rl-integration.md](architecture-decisions/ADR-050-self-play-swe-rl-integration.md) | Deployed | Self-Play SWE-RL Integration for Agent Training (Meta FAIR research, 5 phases complete, AWS deployed Jan 2, 2026) |
| [architecture-decisions/ADR-051-recursive-context-and-embedding-prediction.md](architecture-decisions/ADR-051-recursive-context-and-embedding-prediction.md) | Deployed | Recursive Context Scaling (RLM) & Embedding Prediction (VL-JEPA) - 100x context, 2.85x efficiency |
| [architecture-decisions/ADR-052-ai-alignment-principles.md](architecture-decisions/ADR-052-ai-alignment-principles.md) | Deployed | AI Alignment Principles & Human-Machine Collaboration Framework (Phase 1-3 complete, 154 tests) |
| [architecture-decisions/ADR-053-enterprise-security-integrations.md](architecture-decisions/ADR-053-enterprise-security-integrations.md) | Deployed | Enterprise Security Integrations (Zscaler, Saviynt, AuditBoard) |
| [architecture-decisions/ADR-054-multi-idp-authentication.md](architecture-decisions/ADR-054-multi-idp-authentication.md) | Deployed | Multi-IdP Authentication (SAML, OIDC, SCIM) |
| [architecture-decisions/ADR-055-agent-scheduling-view.md](architecture-decisions/ADR-055-agent-scheduling-view.md) | Deployed | Agent Scheduling View & Job Queue Management |
| [architecture-decisions/ADR-056-documentation-agent.md](architecture-decisions/ADR-056-documentation-agent.md) | Deployed | Documentation Agent for Architecture Discovery and Diagram Generation |
| [architecture-decisions/ADR-057-public-documentation-portal.md](architecture-decisions/ADR-057-public-documentation-portal.md) | Deployed | Public Documentation Portal (docs.aenealabs.com) |
| [architecture-decisions/ADR-058-eks-multi-node-group-architecture.md](architecture-decisions/ADR-058-eks-multi-node-group-architecture.md) | Deployed | EKS Multi-Node Group Architecture (GPU, Spot, On-Demand) |
| [architecture-decisions/ADR-059-aws-organization-account-restructure.md](architecture-decisions/ADR-059-aws-organization-account-restructure.md) | Deployed | AWS Organization Account Restructure (Dev/QA Isolation) |
| [architecture-decisions/ADR-060-enterprise-diagram-generation.md](architecture-decisions/ADR-060-enterprise-diagram-generation.md) | Accepted | Enterprise Diagram Generation (Multi-Provider, Icon Library) |
| [architecture-decisions/ADR-061-gpu-workload-scheduler.md](architecture-decisions/ADR-061-gpu-workload-scheduler.md) | Deployed | GPU Workload Scheduler (Self-Service GPU Jobs, Cost Controls) |
| [architecture-decisions/ADR-062-environment-validator-agent.md](architecture-decisions/ADR-062-environment-validator-agent.md) | Deployed | Environment Validator Agent (Cross-Environment Validation, Drift Detection) |
| [architecture-decisions/ADR-063-constitutional-ai-integration.md](architecture-decisions/ADR-063-constitutional-ai-integration.md) | Deployed | Constitutional AI Integration (16 Principles, Critique Pipeline) |
| [architecture-decisions/ADR-064-customizable-dashboard-widgets.md](architecture-decisions/ADR-064-customizable-dashboard-widgets.md) | Deployed | Customizable Dashboard Widgets (Role Defaults, Drag-Drop Layout) |
| [architecture-decisions/ADR-065-semantic-guardrails-engine.md](architecture-decisions/ADR-065-semantic-guardrails-engine.md) | Deployed | Semantic Guardrails Engine (6-Layer Defense, Embedding Detection, Multi-Turn Tracking) |
| [architecture-decisions/ADR-066-agent-capability-governance.md](architecture-decisions/ADR-066-agent-capability-governance.md) | Deployed | Agent Capability Governance (Permission Matrix, Tool Classification, HITL Escalation) |
| [architecture-decisions/ADR-067-context-provenance-integrity.md](architecture-decisions/ADR-067-context-provenance-integrity.md) | Deployed | Context Provenance & Integrity (GraphRAG Verification, Trust Scoring, Quarantine) |
| [architecture-decisions/ADR-068-universal-explainability-framework.md](architecture-decisions/ADR-068-universal-explainability-framework.md) | Deployed | Universal Explainability Framework (Reasoning Chains, Alternatives, Consistency) |
| [architecture-decisions/ADR-069-guardrail-configuration-ui.md](architecture-decisions/ADR-069-guardrail-configuration-ui.md) | Deployed | Guardrail Configuration UI (Compliance Profiles, Visual Policy Editor) |
| [architecture-decisions/ADR-070-policy-as-code-gitops.md](architecture-decisions/ADR-070-policy-as-code-gitops.md) | Deployed | Policy-as-Code with GitOps (OPA Rego Validation, Policy Simulation) |
| [architecture-decisions/ADR-071-cross-agent-capability-graph.md](architecture-decisions/ADR-071-cross-agent-capability-graph.md) | Deployed | Cross-Agent Capability Graph (Neptune Analysis, Escalation Path Detection) |
| [architecture-decisions/ADR-072-ml-anomaly-detection-agents.md](architecture-decisions/ADR-072-ml-anomaly-detection-agents.md) | Deployed | ML-Based Anomaly Detection (Statistical Detector, Honeypot Capabilities) |
| [architecture-decisions/ADR-073-attribute-based-access-control.md](architecture-decisions/ADR-073-attribute-based-access-control.md) | Deployed | Attribute-Based Access Control (ABAC Multi-Tenant Authorization) |
| [architecture-decisions/ADR-074-palantir-aip-integration.md](architecture-decisions/ADR-074-palantir-aip-integration.md) | Deployed | Palantir AIP Integration (Ontology Bridge, Circuit Breaker, Event Publisher) |
| [architecture-decisions/ADR-075-palantir-aip-ui-enhancements.md](architecture-decisions/ADR-075-palantir-aip-ui-enhancements.md) | Deployed | Palantir AIP UI Enhancements (8 Dashboard Widgets, 5-Step Wizard, IntegrationHub) |
| [architecture-decisions/ADR-076-sbom-attestation-supply-chain.md](architecture-decisions/ADR-076-sbom-attestation-supply-chain.md) | Deployed | SBOM Attestation & Supply Chain Security (CycloneDX/SPDX, Sigstore, Dependency Confusion) |
| [architecture-decisions/ADR-077-cloud-runtime-security-integration.md](architecture-decisions/ADR-077-cloud-runtime-security-integration.md) | Deployed | Cloud Runtime Security Integration (K8s Admission, Container Escape Detection) |
| [architecture-decisions/ADR-078-airgapped-edge-deployment.md](architecture-decisions/ADR-078-airgapped-edge-deployment.md) | Deployed | Air-Gapped & Edge Deployment (Offline Bundles, Egress Validation, Firmware Analysis) |
| [architecture-decisions/ADR-079-scale-ai-model-security.md](architecture-decisions/ADR-079-scale-ai-model-security.md) | Deployed | Scale & AI Model Security (Streaming Analysis, Model Protection, Poisoning Detection) |
| [architecture-decisions/ADR-080-evo-memory-enhancements.md](architecture-decisions/ADR-080-evo-memory-enhancements.md) | Deployed | Evo-Memory Enhancements (ReMem Framework, 7 RefineOperations, Multi-Agent Sharing) |
| [architecture-decisions/ADR-081-constraint-geometry-engine.md](architecture-decisions/ADR-081-constraint-geometry-engine.md) | Deployed | Constraint Geometry Engine (7-Axis Coherence, Deterministic Discrimination, Policy Profiles) |
| [architecture-decisions/ADR-083-runtime-agent-security-platform.md](architecture-decisions/ADR-083-runtime-agent-security-platform.md) | Deployed | Runtime Agent Security Platform (Traffic Interception, Behavioral Baselines, Red Team, Correlation) |
| [architecture-decisions/ADR-084-native-vulnerability-scanning-engine.md](architecture-decisions/ADR-084-native-vulnerability-scanning-engine.md) | Infrastructure + UI Deployed | Native Vulnerability Scanning Engine (GraphRAG-Enhanced LLM Analysis, 4-Layer Isolation, Closed-Loop Remediation) |
| [architecture-decisions/ADR-085-deterministic-verification-envelope.md](architecture-decisions/ADR-085-deterministic-verification-envelope.md) | Proposed | Deterministic Verification Envelope (DO-178C Output Verification, N-of-M Consensus, MC/DC Coverage, Z3 Formal Verification) |
| [architecture-decisions/ADR-086-agentic-identity-lifecycle-controls.md](architecture-decisions/ADR-086-agentic-identity-lifecycle-controls.md) | Proposed | Agentic Identity Lifecycle Controls (Self-Modification Sentinel, Delegation Trust Envelope, Decommission Assurance) |

### Runtime Agent Security Platform (ADR-083)
| File | Purpose |
|------|---------|
| [../src/services/runtime_security/interceptor/traffic_interceptor.py](../src/services/runtime_security/interceptor/traffic_interceptor.py) | Async traffic capture proxy for agent-to-agent/tool/LLM traffic |
| [../src/services/runtime_security/interceptor/protocol.py](../src/services/runtime_security/interceptor/protocol.py) | Frozen dataclass message schemas (InterceptionPoint, TrafficEvent) |
| [../src/services/runtime_security/interceptor/storage.py](../src/services/runtime_security/interceptor/storage.py) | DynamoDB + S3 storage adapter for traffic events |
| [../src/services/runtime_security/discovery/agent_discovery.py](../src/services/runtime_security/discovery/agent_discovery.py) | Agent inventory and continuous discovery engine |
| [../src/services/runtime_security/discovery/shadow_detector.py](../src/services/runtime_security/discovery/shadow_detector.py) | Shadow agent detection via traffic pattern analysis |
| [../src/services/runtime_security/discovery/topology.py](../src/services/runtime_security/discovery/topology.py) | Neptune graph builder for agent topology |
| [../src/services/runtime_security/baselines/baseline_engine.py](../src/services/runtime_security/baselines/baseline_engine.py) | Per-agent behavioral profiling and deviation scoring |
| [../src/services/runtime_security/baselines/metrics.py](../src/services/runtime_security/baselines/metrics.py) | Metric definitions (MetricType, MetricWindow, BaselineMetric) |
| [../src/services/runtime_security/baselines/drift_detector.py](../src/services/runtime_security/baselines/drift_detector.py) | Behavioral drift detection (short vs long window comparison) |
| [../src/services/runtime_security/red_team/taxonomy.py](../src/services/runtime_security/red_team/taxonomy.py) | AURA-ATT&CK taxonomy (75 techniques, 8 categories) |
| [../src/services/runtime_security/red_team/engine.py](../src/services/runtime_security/red_team/engine.py) | Red team engine orchestrator for automated adversarial testing |
| [../src/services/runtime_security/correlation/correlator.py](../src/services/runtime_security/correlation/correlator.py) | Runtime-to-code correlation engine (detect → trace → fix → verify) |
| [../src/services/runtime_security/correlation/graph_tracer.py](../src/services/runtime_security/correlation/graph_tracer.py) | Neptune CALL_GRAPH traversal for source code tracing |
| [../src/services/runtime_security/correlation/vector_matcher.py](../src/services/runtime_security/correlation/vector_matcher.py) | OpenSearch knn_vector semantic vulnerability matching |
| [../src/services/runtime_security/correlation/remediation.py](../src/services/runtime_security/correlation/remediation.py) | Patch generation and HITL approval orchestrator |
| [../deploy/cloudformation/runtime-security-interceptor.yaml](../deploy/cloudformation/runtime-security-interceptor.yaml) | Layer 8.6 - DynamoDB, S3, KMS, IAM for traffic capture |
| [../deploy/cloudformation/runtime-security-discovery.yaml](../deploy/cloudformation/runtime-security-discovery.yaml) | Layer 8.7 - EventBridge, SNS for agent discovery |
| [../deploy/cloudformation/runtime-security-baselines.yaml](../deploy/cloudformation/runtime-security-baselines.yaml) | Layer 8.8 - DynamoDB, CloudWatch alarms for baselines |
| [../deploy/cloudformation/runtime-security-correlation.yaml](../deploy/cloudformation/runtime-security-correlation.yaml) | Layer 8.9 - DynamoDB, SNS, EventBridge for correlation |
| [../deploy/cloudformation/codebuild-runtime-security.yaml](../deploy/cloudformation/codebuild-runtime-security.yaml) | CodeBuild project for runtime security stack deployment |
| [../deploy/buildspecs/buildspec-runtime-security.yml](../deploy/buildspecs/buildspec-runtime-security.yml) | Buildspec for runtime security layer deployment |

### Native Vulnerability Scanning Engine (ADR-084)
| File | Purpose |
|------|---------|
| [../src/services/vulnerability_scanner/](../src/services/vulnerability_scanner/) | Foundation source code (20 files, 4,896 lines) |
| [../deploy/cloudformation/vuln-scan-infrastructure.yaml](../deploy/cloudformation/vuln-scan-infrastructure.yaml) | Layer 9.1 - DynamoDB, S3, KMS, SNS for scan data |
| [../deploy/cloudformation/vuln-scan-iam.yaml](../deploy/cloudformation/vuln-scan-iam.yaml) | Layer 9.2 - IAM roles for workers, Step Functions, Lambda |
| [../deploy/cloudformation/vuln-scan-networking.yaml](../deploy/cloudformation/vuln-scan-networking.yaml) | Layer 9.3 - ECS Fargate cluster, security groups, log groups |
| [../deploy/cloudformation/vuln-scan-workflow.yaml](../deploy/cloudformation/vuln-scan-workflow.yaml) | Layer 9.4 - Step Functions 7-stage scan pipeline |
| [../deploy/cloudformation/vuln-scan-ecr.yaml](../deploy/cloudformation/vuln-scan-ecr.yaml) | Layer 9.5 - ECR repositories for scanner containers |
| [../deploy/cloudformation/vuln-scan-monitoring.yaml](../deploy/cloudformation/vuln-scan-monitoring.yaml) | Layer 9.6 - CloudWatch dashboard and alarms |
| [../deploy/cloudformation/vuln-scan-cleanup.yaml](../deploy/cloudformation/vuln-scan-cleanup.yaml) | Layer 9.7 - Scheduled Lambda for artifact cleanup |
| [../deploy/cloudformation/vuln-scan-eventbridge.yaml](../deploy/cloudformation/vuln-scan-eventbridge.yaml) | Layer 9.8 - Custom event bus and routing rules |
| [../deploy/cloudformation/codebuild-vuln-scan.yaml](../deploy/cloudformation/codebuild-vuln-scan.yaml) | CodeBuild project for Layer 9 deployment |
| [../deploy/buildspecs/buildspec-vuln-scan.yml](../deploy/buildspecs/buildspec-vuln-scan.yml) | Buildspec for 8-stage sequential deployment |
| [../docs/research/competitive-analysis/CLAUDE_CODE_SECURITY_VS_AURA.md](research/competitive-analysis/CLAUDE_CODE_SECURITY_VS_AURA.md) | Competitive analysis vs Anthropic Claude Code Security |
| [../frontend/src/components/dashboard/widgets/scanner/](../frontend/src/components/dashboard/widgets/scanner/) | 20 dashboard widgets (P0/P1/P2) + shared components |
| [../frontend/src/components/scanner/](../frontend/src/components/scanner/) | ScanDetailPage, FindingDetailDrawer, ScanLaunchForm |
| [../frontend/src/services/vulnScannerApi.js](../frontend/src/services/vulnScannerApi.js) | API service layer (20+ endpoints) |
| [../frontend/src/services/vulnScannerMockData.js](../frontend/src/services/vulnScannerMockData.js) | Frontend mock data constants |
| [../src/services/vulnerability_scanner/mock_data.py](../src/services/vulnerability_scanner/mock_data.py) | Enterprise mock data generator (1,999 lines) |
| [../src/services/vulnerability_scanner/ui/types.ts](../src/services/vulnerability_scanner/ui/types.ts) | TypeScript interfaces for scanner API contracts |
| [../src/services/vulnerability_scanner/ui/mock-data.ts](../src/services/vulnerability_scanner/ui/mock-data.ts) | TypeScript mock data (532 findings, 50 scans) |

### Constraint Geometry Engine (ADR-081)
| File | Purpose |
|------|---------|
| [../src/services/constraint_geometry/\_\_init\_\_.py](../src/services/constraint_geometry/__init__.py) | CGE package initialization with exports |
| [../src/services/constraint_geometry/contracts.py](../src/services/constraint_geometry/contracts.py) | ConstraintAxis, CoherenceResult, CoherenceAction dataclasses |
| [../src/services/constraint_geometry/engine.py](../src/services/constraint_geometry/engine.py) | Main CGE orchestrator (hash -> cache -> resolve -> compute -> action) |
| [../src/services/constraint_geometry/coherence_calculator.py](../src/services/constraint_geometry/coherence_calculator.py) | Deterministic coherence computation (cosine similarity, weighted means) |
| [../src/services/constraint_geometry/embedding_cache.py](../src/services/constraint_geometry/embedding_cache.py) | Two-tier cache (in-process LRU + ElastiCache Redis) with SHA-256 keying |
| [../src/services/constraint_geometry/constraint_graph.py](../src/services/constraint_geometry/constraint_graph.py) | In-memory graph resolver (Phase 2 adds Neptune Gremlin) |
| [../src/services/constraint_geometry/policy_profile.py](../src/services/constraint_geometry/policy_profile.py) | 4 built-in profiles (default, dod-il5, developer-sandbox, sox-compliant) |
| [../src/services/constraint_geometry/provenance_adapter.py](../src/services/constraint_geometry/provenance_adapter.py) | ADR-067 trust score integration |
| [../src/services/constraint_geometry/metrics.py](../src/services/constraint_geometry/metrics.py) | Buffered CloudWatch metrics for CCS scores, latency, cache hits |
| [../src/services/constraint_geometry/config.py](../src/services/constraint_geometry/config.py) | CGE configuration and environment settings |
| [../docs/architecture-decisions/diagrams/cge-architecture.mmd](../docs/architecture-decisions/diagrams/cge-architecture.mmd) | Mermaid diagram source (pipeline flow + CGE internals) |
| [../docs/architecture-decisions/diagrams/cge-architecture.html](../docs/architecture-decisions/diagrams/cge-architecture.html) | Rendered architecture diagrams |

### SSR Training Infrastructure (ADR-050)
| File | Purpose |
|------|---------|
| [../src/services/ssr/__init__.py](../src/services/ssr/__init__.py) | SSR package initialization with exports |
| [../src/services/ssr/bug_artifact.py](../src/services/ssr/bug_artifact.py) | Bug artifact dataclasses and enums (BugArtifact, StageResult, ValidationPipelineResult) |
| [../src/services/ssr/artifact_storage_service.py](../src/services/ssr/artifact_storage_service.py) | S3 + DynamoDB artifact storage with KMS encryption |
| [../src/services/ssr/validation_pipeline.py](../src/services/ssr/validation_pipeline.py) | 7-stage consistency validation pipeline |
| [../src/services/ssr/training_service.py](../src/services/ssr/training_service.py) | Training orchestration: job submission, status tracking, batch training |
| [../src/services/ssr/self_play_orchestrator.py](../src/services/ssr/self_play_orchestrator.py) | Session management, round scheduling, convergence detection |
| [../src/services/ssr/training_data_pipeline.py](../src/services/ssr/training_data_pipeline.py) | Reward computation (SSR paper formula), trajectory collection, JSONL export |
| [../src/services/ssr/failure_analyzer.py](../src/services/ssr/failure_analyzer.py) | Failure mode categorization, learning signal extraction |
| [../src/services/ssr/higher_order_queue.py](../src/services/ssr/higher_order_queue.py) | Priority queue for higher-order bugs with deduplication |
| [../src/services/ssr/curriculum_scheduler.py](../src/services/ssr/curriculum_scheduler.py) | Progressive difficulty ramping, skill tracking |
| [../src/services/ssr/model_update_service.py](../src/services/ssr/model_update_service.py) | Checkpoint management, A/B testing, rollback decisions |
| [../src/services/ssr/consent_service.py](../src/services/ssr/consent_service.py) | GDPR/CCPA consent management for training data |
| [../src/services/ssr/git_analyzer.py](../src/services/ssr/git_analyzer.py) | Git history analysis for revertible bug-fix commits |
| [../src/services/ssr/history_injector.py](../src/services/ssr/history_injector.py) | History-aware bug injection with GraphRAG integration |
| [../src/agents/ssr/__init__.py](../src/agents/ssr/__init__.py) | SSR agents package initialization |
| [../src/agents/ssr/shared_policy.py](../src/agents/ssr/shared_policy.py) | Role-switching mechanism (bug injector/solver) |
| [../src/agents/ssr/bug_injection_agent.py](../src/agents/ssr/bug_injection_agent.py) | Semantic bug generation, difficulty calibration |
| [../src/agents/ssr/bug_solving_agent.py](../src/agents/ssr/bug_solving_agent.py) | GraphRAG-enhanced solving, patch extraction |
| [../deploy/cloudformation/ssr-training.yaml](../deploy/cloudformation/ssr-training.yaml) | Layer 7.2: KMS key, S3 bucket, DynamoDB table, IAM role |
| [../deploy/cloudformation/ssr-training-pipeline.yaml](../deploy/cloudformation/ssr-training-pipeline.yaml) | Layer 7.3: ECS Fargate Spot cluster, ECR repos, Step Functions, SNS |
| [../deploy/cloudformation/codebuild-ssr.yaml](../deploy/cloudformation/codebuild-ssr.yaml) | SSR CodeBuild project for CI/CD deployment |

### RLM - Recursive Language Model (ADR-051)

Core engine and security modules for REPL-based code execution enabling 100x context scaling.

| File | Purpose |
|------|---------|
| [../src/services/rlm/__init__.py](../src/services/rlm/__init__.py) | RLM package initialization with exports |
| [../src/services/rlm/recursive_context_engine.py](../src/services/rlm/recursive_context_engine.py) | RecursiveContextEngine: core decomposition engine for 10M+ token contexts |
| [../src/services/rlm/security_guard.py](../src/services/rlm/security_guard.py) | REPLSecurityGuard: code validation, AST analysis, 30+ blocked builtins, safe namespace |
| [../src/services/rlm/input_sanitizer.py](../src/services/rlm/input_sanitizer.py) | InputSanitizer: 45+ prompt injection patterns, context/task sanitization |
| [../tests/test_rlm_recursive_context_engine.py](../tests/test_rlm_recursive_context_engine.py) | 35 tests for RecursiveContextEngine |
| [../tests/test_rlm_security_guard.py](../tests/test_rlm_security_guard.py) | 39 tests for REPLSecurityGuard |
| [../tests/test_rlm_input_sanitizer.py](../tests/test_rlm_input_sanitizer.py) | 45 tests for InputSanitizer |

### JEPA - Joint Embedding Predictive Architecture (ADR-051)

Embedding prediction module for 2.85x inference efficiency through selective decoding.

| File | Purpose |
|------|---------|
| [../src/services/jepa/__init__.py](../src/services/jepa/__init__.py) | JEPA package initialization with exports |
| [../src/services/jepa/embedding_predictor.py](../src/services/jepa/embedding_predictor.py) | EmbeddingPredictor, SelectiveDecodingService, TaskType, MaskingStrategy, InfoNCE loss |
| [../tests/test_jepa_embedding_predictor.py](../tests/test_jepa_embedding_predictor.py) | 48 tests for JEPA embedding prediction |

### Alignment Services (ADR-052 Phase 1-3)

AI alignment infrastructure for human-machine collaboration with anti-sycophancy, trust calibration, reversibility, and transparency.

**Phase 1 - Foundation:**
| File | Purpose |
|------|---------|
| [../src/services/alignment/__init__.py](../src/services/alignment/__init__.py) | Alignment package initialization with exports |
| [../src/services/alignment/metrics_service.py](../src/services/alignment/metrics_service.py) | AlignmentMetricsService - core metrics collection for alignment monitoring |
| [../src/services/alignment/trust_calculator.py](../src/services/alignment/trust_calculator.py) | TrustScoreCalculator - earned autonomy through demonstrated reliability |
| [../src/services/alignment/reversibility.py](../src/services/alignment/reversibility.py) | ReversibilityClassifier - action classification and rollback infrastructure |
| [../src/services/alignment/audit_logger.py](../src/services/alignment/audit_logger.py) | DecisionAuditLogger - enhanced audit trail with reasoning chains |

**Phase 2 - Enforcement:**
| File | Purpose |
|------|---------|
| [../src/services/alignment/sycophancy_guard.py](../src/services/alignment/sycophancy_guard.py) | SycophancyGuard - pre-response validation for anti-sycophancy |
| [../src/services/alignment/trust_autonomy.py](../src/services/alignment/trust_autonomy.py) | TrustBasedAutonomy - dynamic permission adjustment based on trust |
| [../src/services/alignment/rollback_service.py](../src/services/alignment/rollback_service.py) | RollbackService - snapshot and restore capabilities |
| [../src/middleware/transparency.py](../src/middleware/transparency.py) | TransparencyMiddleware - audit requirement enforcement |

**Phase 3 - Dashboard:**
| File | Purpose |
|------|---------|
| [../src/services/alignment/analytics.py](../src/services/alignment/analytics.py) | AlignmentAnalyticsService - historical trend analysis and alerts |
| [../src/api/alignment_endpoints.py](../src/api/alignment_endpoints.py) | REST API endpoints for alignment dashboard |
| [../frontend/src/components/alignment/AlignmentDashboard.jsx](../frontend/src/components/alignment/AlignmentDashboard.jsx) | Real-time alignment health dashboard UI |
| [../frontend/src/components/alignment/OverridePanel.jsx](../frontend/src/components/alignment/OverridePanel.jsx) | Human override controls panel |
| [../frontend/src/services/alignmentApi.js](../frontend/src/services/alignmentApi.js) | Frontend API client for alignment services |
| [../deploy/cloudformation/alignment-alerts.yaml](../deploy/cloudformation/alignment-alerts.yaml) | CloudWatch alarms and SNS alerts for alignment metrics |

**Tests:**
| File | Purpose |
|------|---------|
| [../tests/test_alignment_services.py](../tests/test_alignment_services.py) | 63 tests for Phase 1 services |
| [../tests/test_alignment_phase2.py](../tests/test_alignment_phase2.py) | 60 tests for Phase 2 services |
| [../tests/test_alignment_phase3.py](../tests/test_alignment_phase3.py) | 31 tests for Phase 3 services |

### Scheduling Services (ADR-055)

Agent scheduling view and job queue management infrastructure.

| File | Purpose |
|------|---------|
| [../src/services/scheduling/__init__.py](../src/services/scheduling/__init__.py) | Scheduling package initialization |
| [../src/services/scheduling/models.py](../src/services/scheduling/models.py) | Data models (JobType, Priority, ScheduleStatus, QueueStatus, TimelineEntry) |
| [../src/services/scheduling/scheduling_service.py](../src/services/scheduling/scheduling_service.py) | Core scheduling service with CRUD, queue status, timeline, dispatcher |
| [../src/api/scheduling_endpoints.py](../src/api/scheduling_endpoints.py) | REST API endpoints for scheduling and queue management |
| [../deploy/cloudformation/scheduling-infrastructure.yaml](../deploy/cloudformation/scheduling-infrastructure.yaml) | DynamoDB table, Lambda dispatcher, EventBridge trigger, CloudWatch alarm |
| [../frontend/src/components/scheduling/SchedulingPage.jsx](../frontend/src/components/scheduling/SchedulingPage.jsx) | Main scheduling page with tabs |
| [../frontend/src/components/scheduling/JobQueueDashboard.jsx](../frontend/src/components/scheduling/JobQueueDashboard.jsx) | Real-time queue metrics display |
| [../frontend/src/components/scheduling/ScheduledJobsList.jsx](../frontend/src/components/scheduling/ScheduledJobsList.jsx) | Jobs table with reschedule/cancel actions |
| [../frontend/src/components/scheduling/ScheduleJobModal.jsx](../frontend/src/components/scheduling/ScheduleJobModal.jsx) | Form for scheduling new jobs |
| [../frontend/src/components/scheduling/JobTimelineView.jsx](../frontend/src/components/scheduling/JobTimelineView.jsx) | Calendar/Gantt timeline visualization (ADR-055 Phase 2) |
| [../frontend/src/services/schedulingApi.js](../frontend/src/services/schedulingApi.js) | Frontend API client with mock data |
| [../tests/test_scheduling_service.py](../tests/test_scheduling_service.py) | 40 tests for scheduling service |

### Documentation Agent Services (ADR-056)

Autonomous documentation generation with architecture discovery and diagram generation.

**Backend Services:**
| File | Purpose |
|------|---------|
| [../src/services/documentation/__init__.py](../src/services/documentation/__init__.py) | Documentation package initialization with exports |
| [../src/services/documentation/documentation_agent.py](../src/services/documentation/documentation_agent.py) | Main orchestrator for documentation generation |
| [../src/services/documentation/service_boundary_detector.py](../src/services/documentation/service_boundary_detector.py) | Louvain community detection for service boundaries |
| [../src/services/documentation/diagram_generator.py](../src/services/documentation/diagram_generator.py) | Mermaid.js diagram generation (architecture, data flow, dependencies) |
| [../src/services/documentation/report_generator.py](../src/services/documentation/report_generator.py) | Technical report generation with sections |
| [../src/services/documentation/confidence_calibration.py](../src/services/documentation/confidence_calibration.py) | Isotonic regression calibration with feedback learning |
| [../src/services/documentation/documentation_cache_service.py](../src/services/documentation/documentation_cache_service.py) | 3-tier caching (memory, Redis, S3) |
| [../src/services/documentation/types.py](../src/services/documentation/types.py) | Type definitions and dataclasses |
| [../src/services/documentation/exceptions.py](../src/services/documentation/exceptions.py) | Exception hierarchy for documentation agent |

**Data Flow Analysis:**
| File | Purpose |
|------|---------|
| [../src/services/data_flow/__init__.py](../src/services/data_flow/__init__.py) | Data flow package initialization |
| [../src/services/data_flow/analyzer.py](../src/services/data_flow/analyzer.py) | Main orchestrator correlating all data flows |
| [../src/services/data_flow/database_tracer.py](../src/services/data_flow/database_tracer.py) | PostgreSQL, MySQL, DynamoDB, MongoDB, Redis detection |
| [../src/services/data_flow/queue_analyzer.py](../src/services/data_flow/queue_analyzer.py) | SQS, SNS, Kafka, RabbitMQ, Celery, EventBridge detection |
| [../src/services/data_flow/api_tracer.py](../src/services/data_flow/api_tracer.py) | Internal/external API endpoint detection |
| [../src/services/data_flow/pii_detector.py](../src/services/data_flow/pii_detector.py) | PII field detection with compliance tagging (GDPR, PCI-DSS, HIPAA) |
| [../src/services/data_flow/report_generator.py](../src/services/data_flow/report_generator.py) | Data flow report generation |
| [../src/services/data_flow/types.py](../src/services/data_flow/types.py) | Data flow type definitions |
| [../src/services/data_flow/exceptions.py](../src/services/data_flow/exceptions.py) | Data flow exception hierarchy |

**Infrastructure:**
| File | Purpose |
|------|---------|
| [../deploy/cloudformation/calibration-pipeline.yaml](../deploy/cloudformation/calibration-pipeline.yaml) | DynamoDB, S3, Lambda for nightly calibration |

### Integration Hub Components (ADR-048/053)

Enterprise integration configuration modals and hub interface.

| File | Purpose |
|------|---------|
| [../frontend/src/components/integrations/IntegrationHub.jsx](../frontend/src/components/integrations/IntegrationHub.jsx) | Central integration management interface |
| [../frontend/src/components/integrations/SlackConfig.jsx](../frontend/src/components/integrations/SlackConfig.jsx) | Slack OAuth, webhooks, channel configuration |
| [../frontend/src/components/integrations/ZscalerConfig.jsx](../frontend/src/components/integrations/ZscalerConfig.jsx) | Zero Trust config (ZIA, ZPA, DLP) |
| [../frontend/src/components/integrations/SaviyntConfig.jsx](../frontend/src/components/integrations/SaviyntConfig.jsx) | Identity governance config |
| [../frontend/src/components/integrations/AuditBoardConfig.jsx](../frontend/src/components/integrations/AuditBoardConfig.jsx) | GRC/compliance config |
| [../frontend/src/components/integrations/ZendeskConfig.jsx](../frontend/src/components/integrations/ZendeskConfig.jsx) | Zendesk ticketing config |
| [../frontend/src/components/integrations/LinearConfig.jsx](../frontend/src/components/integrations/LinearConfig.jsx) | Linear project management config |
| [../frontend/src/components/integrations/ServiceNowConfig.jsx](../frontend/src/components/integrations/ServiceNowConfig.jsx) | ServiceNow ITSM config |
| [../frontend/src/components/integrations/DataikuConfig.jsx](../frontend/src/components/integrations/DataikuConfig.jsx) | Dataiku data science platform config |
| [../frontend/src/components/integrations/FivetranConfig.jsx](../frontend/src/components/integrations/FivetranConfig.jsx) | Fivetran data pipeline config |
| [../frontend/src/components/integrations/VSCodeConfig.jsx](../frontend/src/components/integrations/VSCodeConfig.jsx) | VS Code extension config |
| [../frontend/src/components/integrations/PyCharmConfig.jsx](../frontend/src/components/integrations/PyCharmConfig.jsx) | PyCharm plugin config |
| [../frontend/src/components/integrations/JupyterLabConfig.jsx](../frontend/src/components/integrations/JupyterLabConfig.jsx) | JupyterLab extension config |
| [../frontend/src/services/integrationApi.js](../frontend/src/services/integrationApi.js) | Integration API client with provider registry |

### Data Layer Infrastructure (Layer 2)

Additional CloudFormation templates for data layer services.

| File | Purpose |
|------|---------|
| [../deploy/cloudformation/elasticache.yaml](../deploy/cloudformation/elasticache.yaml) | Layer 2.4: Redis/ElastiCache cluster for distributed caching (KMS encryption, multi-AZ) |

### GPU Scheduler Services (ADR-061)

Self-service GPU workload scheduling with cost controls and queue management.

**Backend Services:**
| File | Purpose |
|------|---------|
| [../src/services/gpu_scheduler/__init__.py](../src/services/gpu_scheduler/__init__.py) | GPU scheduler package initialization with exports |
| [../src/services/gpu_scheduler/gpu_scheduler_service.py](../src/services/gpu_scheduler/gpu_scheduler_service.py) | Core GPU scheduler service with job submission, status tracking |
| [../src/services/gpu_scheduler/queue_engine.py](../src/services/gpu_scheduler/queue_engine.py) | Min-heap priority queue (HIGH > NORMAL > LOW), concurrent limits |
| [../src/services/gpu_scheduler/preemption_manager.py](../src/services/gpu_scheduler/preemption_manager.py) | HIGH preempts LOW with checkpoint coordination, Spot handling |
| [../src/services/gpu_scheduler/position_estimator.py](../src/services/gpu_scheduler/position_estimator.py) | Queue position and wait time estimation with confidence scoring |
| [../src/services/gpu_scheduler/queue_dispatcher.py](../src/services/gpu_scheduler/queue_dispatcher.py) | SQS polling, job dispatch, starvation prevention |
| [../src/services/gpu_scheduler/gpu_metrics_service.py](../src/services/gpu_scheduler/gpu_metrics_service.py) | CloudWatch metrics for job lifecycle, queue, resources, costs |
| [../src/services/gpu_scheduler/gpu_cost_service.py](../src/services/gpu_scheduler/gpu_cost_service.py) | Spot pricing from EC2 API, cost calculation, budget management |
| [../src/services/gpu_scheduler/job_template_service.py](../src/services/gpu_scheduler/job_template_service.py) | Reusable job configurations, template CRUD |
| [../src/services/gpu_scheduler/scheduled_job_service.py](../src/services/gpu_scheduler/scheduled_job_service.py) | Recurring jobs with cron schedules, pause/resume |
| [../src/services/gpu_scheduler/stalled_job_detector.py](../src/services/gpu_scheduler/stalled_job_detector.py) | Progress monitoring, alert thresholds, SNS alerts |
| [../src/services/gpu_scheduler/k8s_client.py](../src/services/gpu_scheduler/k8s_client.py) | Kubernetes job management client |
| [../src/services/gpu_scheduler/models.py](../src/services/gpu_scheduler/models.py) | Data models and enums |
| [../src/services/gpu_scheduler/exceptions.py](../src/services/gpu_scheduler/exceptions.py) | Exception hierarchy |

**Infrastructure:**
| File | Purpose |
|------|---------|
| [../deploy/cloudformation/gpu-scheduler-infrastructure.yaml](../deploy/cloudformation/gpu-scheduler-infrastructure.yaml) | Layer 6.15: SQS FIFO queue, DynamoDB tables, S3 checkpoints |
| [../deploy/cloudformation/gpu-scheduler-irsa.yaml](../deploy/cloudformation/gpu-scheduler-irsa.yaml) | Layer 4.7: IRSA role for K8s service account |
| [../deploy/cloudformation/gpu-monitoring.yaml](../deploy/cloudformation/gpu-monitoring.yaml) | Layer 5.9: CloudWatch dashboard, alarms |

### Environment Validator Services (ADR-062)

Cross-environment validation and drift detection with auto-remediation.

**Backend Services:**
| File | Purpose |
|------|---------|
| [../src/services/env_validator/__init__.py](../src/services/env_validator/__init__.py) | Environment validator package initialization with exports |
| [../src/services/env_validator/engine.py](../src/services/env_validator/engine.py) | ValidationEngine with multi-rule orchestration, severity scoring |
| [../src/services/env_validator/config.py](../src/services/env_validator/config.py) | Environment registry loader, SSM integration, YAML config |
| [../src/services/env_validator/models.py](../src/services/env_validator/models.py) | Data models (Violation, ValidationResult, ValidationRun, etc.) |
| [../src/services/env_validator/cli.py](../src/services/env_validator/cli.py) | Command-line interface for manifest validation |
| [../src/services/env_validator/remediation_engine.py](../src/services/env_validator/remediation_engine.py) | Remediation orchestrator with safety controls, rollback support |
| [../src/services/env_validator/remediation_strategies.py](../src/services/env_validator/remediation_strategies.py) | 5 concrete strategies: EnvVar, Naming, Tags, ConfigMap, HITL |
| [../src/services/env_validator/baseline_manager.py](../src/services/env_validator/baseline_manager.py) | Baseline capture and comparison for drift detection |
| [../src/services/env_validator/drift_detector.py](../src/services/env_validator/drift_detector.py) | Drift detection logic with baseline comparison |

**Validators:**
| File | Purpose |
|------|---------|
| [../src/services/env_validator/validators/__init__.py](../src/services/env_validator/validators/__init__.py) | Validators package initialization |
| [../src/services/env_validator/validators/arn.py](../src/services/env_validator/validators/arn.py) | ARN account/region validation (ENV-001 to ENV-008) |
| [../src/services/env_validator/validators/configmap.py](../src/services/env_validator/validators/configmap.py) | ConfigMap value validation (ENV-101 to ENV-104) |
| [../src/services/env_validator/validators/deployment.py](../src/services/env_validator/validators/deployment.py) | Deployment/image validation |
| [../src/services/env_validator/validators/naming.py](../src/services/env_validator/validators/naming.py) | Naming convention validation (ENV-201, ENV-202) |

**Infrastructure:**
| File | Purpose |
|------|---------|
| [../deploy/cloudformation/env-validator-infrastructure.yaml](../deploy/cloudformation/env-validator-infrastructure.yaml) | Layer 6.16: DynamoDB tables, SSM registry, CloudWatch alarms, EventBridge |
| [../deploy/cloudformation/env-validator-irsa.yaml](../deploy/cloudformation/env-validator-irsa.yaml) | Layer 4.8: IRSA role for K8s service account |

**Frontend:**
| File | Purpose |
|------|---------|
| [../frontend/src/components/EnvValidator/index.jsx](../frontend/src/components/EnvValidator/index.jsx) | Dashboard with validation history, charts, run modal |

### Guardrail Configuration Services (ADR-069)

Configuration UI and compliance profiles for guardrail management.

**Backend Services:**
| File | Purpose |
|------|---------|
| [../src/services/guardrail_config/__init__.py](../src/services/guardrail_config/__init__.py) | Guardrail config package initialization with exports |
| [../src/services/guardrail_config/contracts.py](../src/services/guardrail_config/contracts.py) | Data contracts for guardrail configuration (GuardrailConfig, ThresholdConfig, etc.) |
| [../src/services/guardrail_config/compliance_profiles.py](../src/services/guardrail_config/compliance_profiles.py) | Pre-defined compliance profiles (SOC2, CMMC L2/L3, FedRAMP Moderate/High) |
| [../src/services/guardrail_config/validation_service.py](../src/services/guardrail_config/validation_service.py) | Configuration validation against platform minimums and compliance requirements |
| [../src/services/guardrail_config/config_service.py](../src/services/guardrail_config/config_service.py) | CRUD operations, audit logging, import/export for guardrail configurations |

**Tests:**
| File | Purpose |
|------|---------|
| [../tests/services/test_guardrail_config/test_contracts.py](../tests/services/test_guardrail_config/test_contracts.py) | Contract validation tests |
| [../tests/services/test_guardrail_config/test_compliance_profiles.py](../tests/services/test_guardrail_config/test_compliance_profiles.py) | Compliance profile tests |
| [../tests/services/test_guardrail_config/test_validation_service.py](../tests/services/test_guardrail_config/test_validation_service.py) | Validation service tests |
| [../tests/services/test_guardrail_config/test_config_service.py](../tests/services/test_guardrail_config/test_config_service.py) | Config service tests |

### Capability Governance Enhancements (ADR-070 to ADR-073)

Extensions to Agent Capability Governance for policy-as-code, graph analysis, anomaly detection, and ABAC.

**ADR-070 Policy-as-Code:**
| File | Purpose |
|------|---------|
| [../src/services/capability_governance/policy_validator.py](../src/services/capability_governance/policy_validator.py) | OPA Rego policy validation with schema checking |
| [../src/services/capability_governance/policy_simulator.py](../src/services/capability_governance/policy_simulator.py) | Policy simulation for testing changes before deployment |

**ADR-071 Cross-Agent Capability Graph:**
| File | Purpose |
|------|---------|
| [../src/services/capability_governance/graph_contracts.py](../src/services/capability_governance/graph_contracts.py) | Graph data contracts for Neptune integration |
| [../src/services/capability_governance/graph_sync.py](../src/services/capability_governance/graph_sync.py) | PolicyGraphSynchronizer for Neptune sync |
| [../src/services/capability_governance/graph_analyzer.py](../src/services/capability_governance/graph_analyzer.py) | CapabilityGraphAnalyzer with 5 analysis methods |

**ADR-072 ML-Based Anomaly Detection:**
| File | Purpose |
|------|---------|
| [../src/services/capability_governance/anomaly_contracts.py](../src/services/capability_governance/anomaly_contracts.py) | Anomaly detection data contracts |
| [../src/services/capability_governance/statistical_detector.py](../src/services/capability_governance/statistical_detector.py) | Z-score, sequence n-grams, temporal pattern detection |
| [../src/services/capability_governance/honeypot_detector.py](../src/services/capability_governance/honeypot_detector.py) | Honeypot capabilities with zero false positive auto-quarantine |
| [../src/services/capability_governance/anomaly_explainer.py](../src/services/capability_governance/anomaly_explainer.py) | Natural language anomaly explanations with Bedrock integration |

**ADR-073 Attribute-Based Access Control:**
| File | Purpose |
|------|---------|
| [../src/services/capability_governance/abac_contracts.py](../src/services/capability_governance/abac_contracts.py) | ABAC data contracts (SubjectAttributes, ResourceAttributes, etc.) |
| [../src/services/capability_governance/abac_service.py](../src/services/capability_governance/abac_service.py) | ABACAuthorizationService with clearance/sensitivity hierarchies |
| [../src/services/capability_governance/abac_decorator.py](../src/services/capability_governance/abac_decorator.py) | @require_abac decorator for endpoint authorization |

### Palantir AIP Integration (ADR-074/075)

Enterprise data platform integration for threat intelligence, asset criticality, and compliance correlation.

**ADR-074 Backend Services:**
| File | Purpose |
|------|---------|
| [../src/services/palantir/types.py](../src/services/palantir/types.py) | Data models (ThreatContext, AssetContext, RemediationEvent, etc.) |
| [../src/services/palantir/base_adapter.py](../src/services/palantir/base_adapter.py) | EnterpriseDataPlatformAdapter ABC for future integrations |
| [../src/services/palantir/palantir_adapter.py](../src/services/palantir/palantir_adapter.py) | PalantirAIPAdapter with mTLS and circuit breaker |
| [../src/services/palantir/ontology_bridge.py](../src/services/palantir/ontology_bridge.py) | OntologyBridgeService for bidirectional sync |
| [../src/services/palantir/event_publisher.py](../src/services/palantir/event_publisher.py) | PalantirEventPublisher with batch support |
| [../src/services/palantir/circuit_breaker.py](../src/services/palantir/circuit_breaker.py) | Palantir-specific circuit breaker with fallback caching |
| [../src/services/palantir/api.py](../src/services/palantir/api.py) | FastAPI router with 12 endpoints |

**ADR-075 Frontend Components:**
| File | Purpose |
|------|---------|
| [../frontend/src/services/palantirApi.js](../frontend/src/services/palantirApi.js) | API service with 12+ endpoints and mock fallback |
| [../frontend/src/services/integrationApi.js](../frontend/src/services/integrationApi.js) | Integration provider definitions including `palantir_aip` |
| [../frontend/src/hooks/usePalantirSync.js](../frontend/src/hooks/usePalantirSync.js) | Custom hooks (usePalantirSync, useCircuitBreaker, usePalantirHealth) |
| [../frontend/src/components/palantir/CircuitBreakerIndicator.jsx](../frontend/src/components/palantir/CircuitBreakerIndicator.jsx) | CLOSED/HALF_OPEN/OPEN state indicator with admin actions |
| [../frontend/src/components/palantir/DataFreshnessIndicator.jsx](../frontend/src/components/palantir/DataFreshnessIndicator.jsx) | Stale data warnings with configurable thresholds |
| [../frontend/src/components/palantir/IntegrationHealthCard.jsx](../frontend/src/components/palantir/IntegrationHealthCard.jsx) | Health summary with sync status and metrics |
| [../frontend/src/components/settings/PalantirIntegrationSettings.jsx](../frontend/src/components/settings/PalantirIntegrationSettings.jsx) | 5-step configuration wizard |
| [../frontend/src/components/integrations/IntegrationHub.jsx](../frontend/src/components/integrations/IntegrationHub.jsx) | Integration management with Palantir support |
| [../frontend/src/components/dashboard/widgets/SyncStatusWidget.jsx](../frontend/src/components/dashboard/widgets/SyncStatusWidget.jsx) | Ontology sync status widget |

### Product Documentation (docs/product/)

Core product documentation.

### Reference
| File | Purpose |
|------|---------|
| [METRICS_DASHBOARD.md](reference/METRICS_DASHBOARD.md) | Metrics and KPIs |

### Capability Reference Pages (docs/*.html)

Standalone HTML documents for presenting platform capabilities to technical and business audiences.

| File | Purpose |
|------|---------|
| [architecture-decision-records.html](architecture-decision-records.html) | All 83 ADRs across 11 categories with dependency graph |
| [comprehensive-testing-overview.html](comprehensive-testing-overview.html) | 23,165+ tests, coverage config, mock infrastructure, CI/CD integration |
| [agentic-capabilities.html](agentic-capabilities.html) | 35+ agents, 6 orchestrators, tool system, memory architectures |
| [hitl-capabilities.html](hitl-capabilities.html) | 7 autonomy presets, approval service, checkpoints, sandbox workflow |
| [agent-guardrail-capabilities.html](agent-guardrail-capabilities.html) | 12 guardrail systems, 17 detection layers |
| [tools-vs-skills-architecture.html](tools-vs-skills-architecture.html) | MCP tool-based architecture trade-off analysis |
| [documentation-generation-capabilities.html](documentation-generation-capabilities.html) | 53+ generation capabilities across 16 service categories |
| [infrastructure-deployment-architecture.html](infrastructure-deployment-architecture.html) | 9-layer deployment cascade, VPC/networking, EKS, CI/CD, 38 AWS services |
| [security-architecture-compliance.html](security-architecture-compliance.html) | Defense-in-depth, 13 security ADRs, AURA-ATT&CK, compliance frameworks |
| [cicd-pipeline-deployment-automation.html](cicd-pipeline-deployment-automation.html) | 24 CodeBuild projects, 9-layer cascade, 3-gate validation, Release Please |
| [agent-architecture-multi-agent-orchestration.html](agent-architecture-multi-agent-orchestration.html) | 28+ agents, cognitive memory, HITL autonomy, constitutional AI, 13 agent ADRs |
| [memory-architecture-cognitive-systems.html](memory-architecture-cognitive-systems.html) | 5-tier cognitive memory, Titan Neural Memory, Evo-Memory, context engineering, HopRAG |
| [hybrid-graphrag-architecture.html](hybrid-graphrag-architecture.html) | Neptune graph + OpenSearch vector hybrid retrieval architecture |
| [deterministic-verification-envelope.html](deterministic-verification-envelope.html) | ADR-085 DVE: DO-178C output verification, 3 pillars, pipeline diagram, DAL profiles |

### User Guides
| File | Purpose |
|------|---------|
| [PLATFORM_DEVELOPER_GUIDE_V1.md](reference/PLATFORM_DEVELOPER_GUIDE_V1.md) | Platform developer guide |
| [PLATFORM_ENDUSER_GUIDE.md](guides/PLATFORM_ENDUSER_GUIDE.md) | End-user guide (Aura Platform v1.0) |

---

## archive/ - Historical Documentation

### Project Status Archives
| File | Period | Purpose |
|------|--------|---------|
| [../archive/status/PROJECT_STATUS-v1.0-v1.2.md](../archive/status/PROJECT_STATUS-v1.0-v1.2.md) | Nov 2024 - Nov 2025 | Historical status v1.0-v1.2 development |
| [../archive/status/PROJECT_STATUS-v1.3-dec-12-17.md](../archive/status/PROJECT_STATUS-v1.3-dec-12-17.md) | Dec 12-17, 2025 | December 2025 early development |
| [../archive/status/PROJECT_STATUS-v1.3-dec-18-31.md](../archive/status/PROJECT_STATUS-v1.3-dec-18-31.md) | Dec 18-31, 2025 | December 2025 late development |

### Session Summaries (Point-in-Time Snapshots)
| File | Date | Purpose |
|------|------|---------|
| [../archive/sessions/SESSION_SUMMARY_2025-11-18_code_quality.md](../archive/sessions/SESSION_SUMMARY_2025-11-18_code_quality.md) | Nov 18, 2025 | Code quality improvements session |
| [../archive/sessions/SESSION_SUMMARY_2025-11-18_agentic_search.md](../archive/sessions/SESSION_SUMMARY_2025-11-18_agentic_search.md) | Nov 18, 2025 | Agentic search + ECS session |

### Deployment Records
| File | Date | Purpose |
|------|------|---------|
| [../archive/deployments/PHASE1_DEPLOYMENT_SUMMARY.md](../archive/deployments/PHASE1_DEPLOYMENT_SUMMARY.md) | Nov 2025 | Phase 1 (Foundation) deployment record |
| [../archive/deployments/DEPLOYMENT_GUIDE_2025-11-11.md](../archive/deployments/DEPLOYMENT_GUIDE_2025-11-11.md) | Nov 11, 2025 | Archived deployment guide (superseded by docs/deployment/DEPLOYMENT_GUIDE.md) |

### Incident Reports
| File | Date | Purpose |
|------|------|---------|
| [../archive/incidents/phase2-neptune-opensearch-failures-2025-11-24.md](../archive/incidents/phase2-neptune-opensearch-failures-2025-11-24.md) | Nov 24, 2025 | Neptune/OpenSearch transient failure troubleshooting |

### Security Audits
| File | Date | Purpose |
|------|------|---------|
| [../archive/security-audits/SECURITY_CICD_ANALYSIS.md](../archive/security-audits/SECURITY_CICD_ANALYSIS.md) | Nov 24, 2025 | Security + CI/CD audit (superseded by SECURITY_FIXES_QUICK_REFERENCE.md) |
| [../archive/security-audits/govcloud-security-remediation-2025-11-22.md](../archive/security-audits/govcloud-security-remediation-2025-11-22.md) | Nov 22, 2025 | GovCloud security audit remediation |
| [../archive/security-audits/CKGE_SECURITY_ANALYSIS.md](../archive/security-audits/CKGE_SECURITY_ANALYSIS.md) | Nov 11, 2025 | CKGE core ingestion logic security analysis |

### Documentation Audits
| File | Date | Purpose |
|------|------|---------|
| [../archive/documentation-audits/DOCUMENTATION_REVIEW_FINDINGS_2025-11-27.md](../archive/documentation-audits/DOCUMENTATION_REVIEW_FINDINGS_2025-11-27.md) | Nov 27, 2025 | Comprehensive documentation audit (critical issues resolved, recommendations implemented) |
| [../archive/documentation-audits/CLAUDE_MD_ARCHIVED_SECTIONS_2025-12-13.md](../archive/documentation-audits/CLAUDE_MD_ARCHIVED_SECTIONS_2025-12-13.md) | Dec 13, 2025 | Archived CLAUDE.md sections for token efficiency |

### Deprecated Documentation
| File | Date | Reason |
|------|------|--------|
| [../archive/deprecated/PHASE2_IMPLEMENTATION_GUIDE.md](../archive/deprecated/PHASE2_IMPLEMENTATION_GUIDE.md) | Nov 2025 | Phase 2 is DEPLOYED (superseded by DEPLOYMENT_GUIDE.md) |
| [../archive/deprecated/PLATFORM_ENDUSER_GUIDE_CKGE_2025-12-13.md](../archive/deprecated/PLATFORM_ENDUSER_GUIDE_CKGE_2025-12-13.md) | Dec 2025 | Legacy CKGE branding (replaced with Aura Platform guide) |

### Implementation Snapshots (Completed Features)
| File | Date | Purpose |
|------|------|---------|
| [../archive/implementation-snapshots/IMPLEMENTATION_AGENTIC_SEARCH.md](../archive/implementation-snapshots/IMPLEMENTATION_AGENTIC_SEARCH.md) | Nov 18, 2025 | Agentic search implementation complete (see SYSTEM_ARCHITECTURE.md) |

### Implementation Summaries (Superseded)
| File | Date | Purpose |
|------|------|---------|
| [../archive/summaries/CORE_AI_IMPLEMENTATION_SUMMARY.md](../archive/summaries/CORE_AI_IMPLEMENTATION_SUMMARY.md) | Nov 2025 | AI implementation summary (now in PROJECT_STATUS) |
| [../archive/summaries/ECS_FARGATE_DEPLOYMENT_SUMMARY.md](../archive/summaries/ECS_FARGATE_DEPLOYMENT_SUMMARY.md) | Nov 2025 | ECS Fargate summary (now in PROJECT_STATUS) |
| [../archive/summaries/DRIFT_PROTECTION_SUMMARY.md](../archive/summaries/DRIFT_PROTECTION_SUMMARY.md) | Nov 2025 | Drift protection summary (now in MODULAR_CICD_IMPLEMENTATION) |
| [../archive/summaries/DOCUMENTATION_UPDATES_SUMMARY.md](../archive/summaries/DOCUMENTATION_UPDATES_SUMMARY.md) | Nov 22, 2025 | Documentation updates (now in CHANGELOG) |
| [../archive/summaries/PROJECT_PROGRESS_REPORT.md](../archive/summaries/PROJECT_PROGRESS_REPORT.md) | Nov 11, 2025 | Progress report (outdated) |

### Work-in-Progress (Superseded)
| File | Date | Purpose |
|------|------|---------|
| [../archive/work-in-progress/AGENTIC_SEARCH_PROGRESS.md](../archive/work-in-progress/AGENTIC_SEARCH_PROGRESS.md) | Nov 18, 2025 | Agentic search WIP (superseded by IMPLEMENTATION_AGENTIC_SEARCH) |

### Legacy (Outdated Architecture)
| File | Date | Purpose |
|------|------|---------|
| [../archive/legacy/MODULAR_CICD_MIGRATION_GUIDE.md](../archive/legacy/MODULAR_CICD_MIGRATION_GUIDE.md) | Nov 25, 2025 | Migration from monolithic to modular CI/CD (migration complete) |
| [../archive/legacy/EKS_COST_ANALYSIS.md](../archive/legacy/EKS_COST_ANALYSIS.md) | Nov 18, 2025 | EKS cost analysis (consolidated into COST_ANALYSIS_DEV_ENVIRONMENT.md) |
| [../archive/legacy/CKGE_V2_DEPLOYMENT_PLAN.md](../archive/legacy/CKGE_V2_DEPLOYMENT_PLAN.md) | Nov 11, 2025 | Old CKGE V2.0 deployment plan |

### Business & Planning (Early Stage Docs)
| File | Date | Purpose |
|------|------|---------|
| [../archive/business/ROI_CALCULATOR_GUIDE.md](../archive/business/ROI_CALCULATOR_GUIDE.md) | Nov 11, 2025 | ROI calculation methodology (early stage) |
| [../archive/business/THE_SALE.md](../archive/business/THE_SALE.md) | Nov 11, 2025 | Early project overview (archived) |
| [../archive/business/TEST_PLAN.md](../archive/business/TEST_PLAN.md) | Nov 11, 2025 | Original test plan (superseded by actual tests) |
| [../archive/business/SUMMARY_REPORT.md](../archive/business/SUMMARY_REPORT.md) | Nov 11, 2025 | Project summary (superseded by PROJECT_STATUS.md) |
| [../archive/business/CICD_AND_COST_ANALYSIS.md](../archive/business/CICD_AND_COST_ANALYSIS.md) | Nov 11, 2025 | Early CI/CD design and cost planning (superseded by modular CI/CD) |

### Archived CloudFormation Templates (Nov 29, 2025)
| File | Date | Reason |
|------|------|--------|
| [../deploy/cloudformation/archive/config-compliance.yaml](../deploy/cloudformation/archive/config-compliance.yaml) | Nov 29, 2025 | Superseded by active config-compliance.yaml |
| [../deploy/cloudformation/archive/ecs-dev-cluster.yaml](../deploy/cloudformation/archive/ecs-dev-cluster.yaml) | Nov 29, 2025 | Orphan template - not deployed by any buildspec |
| [../deploy/cloudformation/archive/ecs-dev-services.yaml](../deploy/cloudformation/archive/ecs-dev-services.yaml) | Nov 29, 2025 | Orphan template - not deployed by any buildspec |
| [../deploy/cloudformation/archive/ecs-sandbox-cluster.yaml](../deploy/cloudformation/archive/ecs-sandbox-cluster.yaml) | Nov 29, 2025 | Orphan template - not deployed by any buildspec |
| [../deploy/cloudformation/archive/ecs-scheduled-scaling.yaml](../deploy/cloudformation/archive/ecs-scheduled-scaling.yaml) | Nov 29, 2025 | Orphan template - not deployed by any buildspec |
| [../deploy/cloudformation/archive/eks-multi-tier.yaml](../deploy/cloudformation/archive/eks-multi-tier.yaml) | Nov 29, 2025 | Orphan template - not deployed by any buildspec |
| [../deploy/cloudformation/archive/master-stack.yaml](../deploy/cloudformation/archive/master-stack.yaml) | Nov 29, 2025 | Orphan template - not deployed by any buildspec |
| [../deploy/cloudformation/archive/network-services.yaml](../deploy/cloudformation/archive/network-services.yaml) | Nov 29, 2025 | Orphan template - not deployed by any buildspec |
| [../deploy/cloudformation/archive/network-services-enhanced.yaml](../deploy/cloudformation/archive/network-services-enhanced.yaml) | Nov 29, 2025 | Orphan template - not deployed by any buildspec |
| [../deploy/cloudformation/archive/opensearch-filesystem-index.yaml](../deploy/cloudformation/archive/opensearch-filesystem-index.yaml) | Nov 29, 2025 | Orphan template - not deployed by any buildspec |

---

## Documentation Naming Convention

**Pattern:** `CATEGORY_TOPIC_TYPE.md`

### Categories
- `IMPLEMENTATION_` - Implementation guides/summaries
- `DEPLOYMENT_` - Deployment guides/procedures
- `COST_ANALYSIS_` - Cost breakdowns
- `SECURITY_` - Security documentation
- `GOVCLOUD_` - GovCloud-specific docs
- `PHASE[N]_` - Phase-specific guides

### Types
- `_GUIDE.md` - How-to guides
- `_SUMMARY.md` - High-level summaries
- `_ANALYSIS.md` - Detailed analysis
- `_TRACKER.md` - Living tracking documents
- `_REFERENCE.md` - Quick references

---

## Common Documentation Tasks

### For Developers
1. **Getting Started:** ../README.md → deployment/DEPLOYMENT_GUIDE.md
2. **Architecture Understanding:** SYSTEM_ARCHITECTURE.md
3. **Development Setup:** reference/PLATFORM_DEVELOPER_GUIDE_V1.md
4. **API Reference:** reference/API_REFERENCE.md

### For DevOps/Infrastructure
1. **Deployment Methods:** deployment/DEPLOYMENT_METHODS.md (CI/CD vs Bootstrap vs GitOps)
2. **Deployment Guide:** deployment/DEPLOYMENT_GUIDE.md
3. **CI/CD:** deployment/MODULAR_CICD_IMPLEMENTATION.md → deployment/CICD_SETUP_GUIDE.md
4. **Monitoring:** runbooks/DRIFT_PROTECTION_GUIDE.md
5. **Cost Management:** See internal documentation

### For Security/Compliance
1. **Security Review:** security/SECURITY_FIXES_QUICK_REFERENCE.md
2. **GovCloud Migration:** cloud-strategy/GOVCLOUD_READINESS_TRACKER.md → cloud-strategy/GOVCLOUD_MIGRATION_SUMMARY.md
3. **Compliance:** security/CMMC_CERTIFICATION_PATHWAY.md
4. **Certification Roadmaps:** compliance/roadmaps/README.md (FedRAMP High, CMMC L2/L3, IL5)

### For AI Assistants (Claude Code)
1. **Context Loading:** ../CLAUDE.md (always loaded first)
2. **Current State:** ../PROJECT_STATUS.md
3. **Recent Changes:** ../CHANGELOG.md
4. **Institutional Memory:** ../agent-config/GUARDRAILS.md
5. **Reference Documents:** Use file paths, don't read unless editing

---

## Document Status Legend

- ✅ **Current** - Actively maintained, up-to-date
- ⏳ **Living** - Continuously updated (e.g., PROJECT_STATUS.md, CHANGELOG.md)
- 📦 **Archived** - Historical record, not actively maintained
- ⚠️ **Deprecated** - Outdated, kept for reference only

---

## Consolidation Summary (November 25, 2025)

### Changes Made
- **Archived:** 14 files (sessions, summaries, progress reports, incidents, legacy docs)
- **Deleted:** 3 duplicate files (DNSMASQ_INTEGRATION_SUMMARY, DNSMASQ_OPTIMIZATIONS, PHASE2_DEPLOYMENT_GUIDE)
- **Renamed:** 2 files to follow naming convention
- **Result:** Reduced from 29 to 15 core root files (48% reduction)

### Eliminated Duplicates
1. Session summaries → Archived
2. Agentic search (progress vs complete) → Kept IMPLEMENTATION_AGENTIC_SEARCH
3. Phase 2 deployment (3 files) → Kept PHASE2_IMPLEMENTATION_GUIDE
4. dnsmasq docs (4 files) → Kept docs/integrations/DNSMASQ_INTEGRATION + DNSMASQ_QUICK_START
5. Cost analysis (3 files) → Kept COST_ANALYSIS_DEV_ENVIRONMENT
6. Security docs → Kept SECURITY_CICD_ANALYSIS + SECURITY_FIXES_QUICK_REFERENCE

---

**Maintained by:** Project Aura Team
**Questions?** See CLAUDE.md for AI assistant documentation guidelines
