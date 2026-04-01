# Archived Unreleased Changes (December 5-14, 2025)

> **Archive Date:** December 14, 2025
> **Reason:** Manual changelog entries replaced by Release Please automation
> **Coverage:** Changes from December 5, 2025 to December 14, 2025
> **Original Location:** CHANGELOG.md [Unreleased] section

---

## [Unreleased]

### Security

* **P1 #42:** Create centralized exception hierarchy (Dec 13, 2025)
  - New `src/exceptions.py` with 17 exception classes (571 lines)
  - Base class `AuraError` with automatic sensitive data sanitization
  - Hierarchy: ValidationError, ServiceError, SecurityError, AgentError, WorkflowError and subtypes
  - Utility functions: `safe_error_message()`, `api_error_response()`, `handle_exception()`
  - Context sanitization redacts: password, token, secret, api_key, authorization, credential, private_key, access_key, session
  - 38 comprehensive tests in `tests/test_exceptions.py`

* **P1 #41:** Audit subprocess shell=True usage (Dec 13, 2025)
  - Verified `SecureCommandExecutor` in `src/services/secure_command_executor.py` uses `shell=False`
  - No unsafe subprocess patterns found in codebase
  - Command execution properly isolated with argument list (no shell expansion)

* **P1 #40:** Apply API rate limiting to approval and settings endpoints (Dec 13, 2025)
  - `approval_endpoints.py`: `standard_rate_limit` (60/min) for list/stats/get operations
  - `approval_endpoints.py`: `critical_rate_limit` (2/min) for approve/reject operations
  - `approval_endpoints.py`: `sensitive_rate_limit` (10/min) for escalate operation
  - `settings_endpoints.py`: `admin_rate_limit` (5/min) for all PUT operations
  - Leverages existing `api_rate_limiter.py` infrastructure

* **P1 #39:** Verify LLM input sanitization layer (Dec 13, 2025)
  - Confirmed `BedrockLLMService` already integrates `llm_prompt_sanitizer.py`
  - Prompt injection detection and neutralization in place
  - No additional implementation required

* **P0 #38:** Externalize Cognito configuration (Dec 13, 2025)
  - Remove hardcoded Cognito pool ID from `chat-assistant.yaml`
  - Use `!ImportValue` for Cognito ARN (references cognito stack export)
  - Add `getRequiredEnvVar()` helper in `frontend/src/config/auth.js`
  - Production deployments now require proper env configuration (no fallbacks)
  - Update `.env.example` with required Cognito variables
  - Update `FRONTEND_DEV_MODE_RUNBOOK.md` with SSM fetch commands

* **P0 #37:** Remove dev auth bypass (Dec 13, 2025)
  - Remove `X-Dev-User-Id` header handling from `chat_handler.py`
  - Remove `X-Dev-User-Id` headers from `ChatContext.jsx` fetch calls
  - All requests now require valid Cognito JWT tokens
  - No authentication bypass possible in any environment

* **P0 #36:** HITL Auto-Approval configuration verified (Dec 13, 2025)
  - Already implemented via `AutonomyPolicyService` (per-tenant config)
  - `auto_approve_minor_patches: False` by default (secure)
  - Full audit logging via `record_autonomous_decision()`
  - Admin UI in `SettingsPage.jsx` HitlSettingsTab

### Features

* **cicd:** Add dedicated Docker-Podman build CodeBuild project (Dec 13, 2025)
  - New `aura-docker-build-{environment}` CodeBuild project for fast container image builds
  - Buildspec: `deploy/buildspecs/buildspec-docker-build.yml` (~130 lines)
  - CloudFormation: `deploy/cloudformation/codebuild-docker.yaml` (Layer 1.9)
  - Supports 7 build targets: api, frontend, dnsmasq, orchestrator, agent, sandbox, memory-service
  - Build time: 3-8 minutes vs 15-30 minutes for full Application layer
  - ADR-035 documents the architecture decision

* **refactor:** Move codebuild-docker from Layer 4.8 to Layer 1.9 (Dec 14, 2025)
  - Relocated Docker build CodeBuild project to Foundation layer for better logical grouping
  - CI/CD infrastructure belongs in Foundation (Layer 1), not Application (Layer 4)
  - Updated stack description: "Project Aura - Layer 1.9 - Docker Build CodeBuild Project"
  - Updated CodeBuild project description: "Project Aura - Layer 1.9 - Docker Build"
  - Deployment via `aura-foundation-deploy-dev` succeeded

* **frontend:** Add Security Alerts widget to Dashboard (Dec 13, 2025)
  - `SecurityAlertsWidget.jsx` - Compact dashboard widget displaying P1_CRITICAL and P2_HIGH alerts
  - Real-time badge counts connected to `SecurityAlertsContext`
  - Added to `WIDGET_REGISTRY` with responsive layouts (lg: 4 cols, md: 6 cols, sm: 12 cols)
  - Quick access to critical security alerts from main Dashboard view

* **k8s:** Wire DNS blocklist Lambda to dnsmasq DaemonSet (Dec 13, 2025)
  - Complete threat intelligence pipeline integration end-to-end
  - dnsmasq DaemonSet now mounts `dnsmasq-blocklist` ConfigMap
  - Pipeline: Lambda (6 AM UTC) -> S3 -> CronJob (7 AM UTC) -> ConfigMap -> dnsmasq reload
  - Automated malicious domain blocking across all EKS nodes
  - ConfigMap refresh ensures zero-downtime blocklist updates

* **security:** Deploy comprehensive security services infrastructure (Dec 12, 2025)
  - **Security Infrastructure (CloudFormation):**
    - Security EventBridge Bus: `aura-security-events-dev` - Routes security events for processing
    - Security SNS Topic: `aura-security-alerts-dev` - Email notifications for security alerts
    - 3 CloudWatch Log Groups (90-day retention): `/aura/dev/security-audit`, `/aura/dev/security-events`, `/aura/dev/security-threats`
    - 7 CloudWatch Security Alarms: injection-attempts, secrets-exposure, prompt-injection, rate-limit-exceeded, high-severity-security-events, llm-security-misuse, security-build-failures
    - 2 EventBridge Rules: security-alert-rule (routes to SNS), security-audit-logging (logs all events)
  - **Security Python Services (5 services, 328 tests):**
    - `input_validation_service.py` - SQL injection, XSS, command injection, SSRF, prompt injection detection (76 tests)
    - `secrets_detection_service.py` - 30+ secret types, entropy-based detection (66 tests)
    - `security_audit_service.py` - Event logging, CloudWatch/DynamoDB persistence (76 tests)
    - `security_alerts_service.py` - P1-P5 priority alerts, HITL integration, SNS notifications (29 tests)
    - `security_integration.py` (API) - FastAPI decorators, middleware, rate limiting (39 tests)
  - **IRSA Policy v6 Updates:**
    - EventBridge `events:PutEvents` for anomaly and security event buses
    - SNS `sns:Publish` for security-alerts, critical-anomalies, hitl-approvals topics
    - CloudWatch Logs permissions for `/aura/${Environment}/*`
  - **Compliance Mapping:** CMMC, SOC2, NIST 800-53 controls documented

* **security:** Add security alerts dashboard and E2E/load testing (Dec 12, 2025)
  - **E2E Security Infrastructure Tests** (15 tests):
    - EventBridge security event bus validation
    - SNS security alert topic and subscriptions
    - CloudWatch security metrics and alarms
    - CloudWatch Logs audit logging verification
    - Full security event pipeline flow test
  - **Load/Performance Tests** (11 tests):
    - Input validation: >1,000 validations/second
    - Secrets detection: >100 scans/second
    - Audit logging: >500 events/second
    - P99 latency: <10ms input validation, <50ms secrets detection
  - **Frontend Security Alerts Dashboard**:
    - `SecurityAlertsPanel.jsx` - Two-panel alert management UI
    - `SecurityAlertsContext.jsx` - React context with 30s polling, browser notifications
    - `securityAlertsApi.js` - API client (17 methods)
    - Route: `/security/alerts` (role-protected)

### Documentation

* **security:** Create security services documentation (Dec 12, 2025)
  - `docs/SECURITY_INCIDENT_RESPONSE.md` - Incident response runbook
  - `docs/DEVELOPER_SECURITY_GUIDELINES.md` - Developer best practices
  - `docs/SECURITY_SERVICES_OVERVIEW.md` - Architecture and compliance mapping

### Bug Fixes

* **cicd:** Add dual-namespace CodeConnections IAM permissions (Dec 11, 2025)
  - AWS uses both `codeconnections:` and legacy `codestar-connections:` namespaces
  - Added both namespaces to Foundation, IAM, and Runbook Agent CodeBuild roles
  - Fixed OAuthProviderException when creating CodeBuild projects with GitHub source
  - Created runbook: `docs/runbooks/CODECONNECTIONS_GITHUB_ACCESS.md`

* **cicd:** Simplify buildspec-runbook-agent.yml echo commands (Dec 11, 2025)
  - CodeBuild YAML parser interprets `=` at start of values as YAML tags
  - Removed decorative echo commands with `=` characters
  - Fixed YAML_FILE_ERROR at DOWNLOAD_SOURCE phase

* **cicd:** Add CodeBuild report group permissions to Runbook Agent (Dec 11, 2025)
  - Added `codebuild:CreateReportGroup` and related permissions
  - Fixed AccessDeniedException at UPLOAD_ARTIFACTS phase

* **docker:** Resolve dnsmasq Alpine apk exit code 255 (Dec 11, 2025)
  - Added `apk update` before `apk add` to refresh package index
  - Added fallback to public ECR when private base image unavailable
  - Prevents exit code 255 from stale mirrors or missing base images

* **deploy:** Resolve Docker platform and ECR conflicts (Dec 11, 2025)
  - Added explicit `--platform linux/amd64` to Docker build command
  - Added architecture verification for private ECR base images
  - Fallback to public ECR when private image has wrong architecture (ARM64 vs AMD64)
  - Added pre-check for existing ECR repositories before CloudFormation create
  - Skip stack creation if repository already exists to avoid AlreadyExists error

* **iam:** Add missing CloudFormation permissions for Application layer (Dec 11, 2025)
  - Added `ecr-api`, `cognito`, `bedrock-guardrails` stacks to CF permissions
  - Added Cognito User Pool management permissions (CreateUserPool, etc)
  - Added Bedrock Guardrail management permissions
  - Expanded SSM Parameter Store permissions for config storage

* **iam:** Add bedrock:ListTagsForResource for CloudFormation tag management (Dec 11, 2025)
  - CloudFormation requires ListTagsForResource to manage tags on Bedrock resources
  - Without this permission, CloudFormation fails with AccessDenied even when CRUD permissions granted
  - Updated IAM permissions runbook with Bedrock Guardrails pattern

* **serverless:** Fix comprehensive IAM permission gaps for serverless layer (Dec 12, 2025)
  - Added Lambda Function URL permissions (CreateFunctionUrlConfig, UpdateFunctionUrlConfig, DeleteFunctionUrlConfig, GetFunctionUrlConfig)
  - Added Lambda Event Source Mapping permissions (CreateEventSourceMapping, DeleteEventSourceMapping, TagResource, UntagResource)
  - Added CloudWatch alarm tagging permissions (TagResource, UntagResource, ListTagsForResource)
  - Added EC2 security group and network interface permissions for VPC-enabled Lambdas
  - Added DynamoDB table management permissions (CreateTable, DeleteTable, UpdateTable, TagResource)
  - Added SQS queue management permissions (CreateQueue, DeleteQueue, TagQueue, SetQueueAttributes)
  - Added EventBridge custom event bus permissions (CreateEventBus, DeleteEventBus, DescribeEventBus)
  - Added IRSA role pattern to IAM permissions (${ProjectName}-*-irsa-${Environment})
  - Created runbook: `docs/operations/SERVERLESS_DEPLOYMENT_RUNBOOK.md`

* **lambda:** Add missing description to calculate-threshold Lambda (Dec 12, 2025)
  - `aura-calculate-threshold-dev` was deployed without Description property
  - Added description: "Calculates budget threshold percentages for AWS cost alert notifications"
  - Created runbook: `docs/operations/LAMBDA_CONFIGURATION_STANDARDS.md`

* **iam:** Fix resource tagging permissions for serverless layer (Dec 12, 2025)
  - Added `logs:UntagResource` for CloudWatch log group rollbacks
  - Added application log group pattern `/${ProjectName}/*` (custom paths like `/aura/runbook-agent/dev`)
  - Added SNS topic management: `CreateTopic`, `DeleteTopic`, `Subscribe`, `Unsubscribe`
  - Added SNS tagging: `TagResource`, `UntagResource`, `ListTagsForResource`
  - Fixed `aura-runbook-agent-dev` stack stuck in `UPDATE_ROLLBACK_FAILED`
  - Created runbook: `docs/runbooks/RESOURCE_TAGGING_PERMISSIONS.md`

* **cfn:** Standardize CodeBuild layer numbering convention (Dec 12, 2025)
  - 8 parent CodeBuild templates use single integer: `Layer N`
  - 5 sub-layer CodeBuild templates use decimal: `Layer N.S`
  - Fixed: network-services (1.7), frontend (4.7), chat-assistant (6.7), runbook-agent (6.8), incident-response (6.9)

* **iam:** Add dns-blocklist-lambda deployment permissions (Dec 12, 2025)
  - Added CloudFormation stack permission for dns-blocklist-lambda
  - Added S3 bucket permissions including `s3:PutBucketTagging`, `s3:GetBucketTagging`
  - Added IAM role permissions: `iam:TagRole`, `iam:UntagRole`, `iam:UpdateAssumeRolePolicy`
  - Added blocklist-lambda-role and blocklist-sync-role to IAM policy scope
  - Fixed multiple UPDATE_ROLLBACK_FAILED states during iterative permission fixes
  - Updated runbook: `docs/runbooks/RESOURCE_TAGGING_PERMISSIONS.md`

* **cfn:** Force dns-blocklist-lambda description sync via DescriptionVersion tag (Dec 12, 2025)
  - CloudFormation descriptions only update when resource changes occur
  - Added `DescriptionVersion: '6.6.1'` tag to BlocklistConfigBucket to force sync
  - Stack description now shows correct `Layer 6.6` format
  - Created runbook: `docs/runbooks/CFN_DESCRIPTION_SYNC.md`

### Documentation

* **runbooks:** Create CFN_DESCRIPTION_SYNC runbook (Dec 12, 2025)
  - Documents CloudFormation description drift issue and resolution
  - Explains why descriptions don't update without resource changes
  - Provides DescriptionVersion tag technique to force sync
  - Includes layer numbering standards for CodeBuild and infrastructure templates
  - Path: `docs/runbooks/CFN_DESCRIPTION_SYNC.md`

* **runbooks:** Update RESOURCE_TAGGING_PERMISSIONS runbook (Dec 12, 2025)
  - Added dns-blocklist-lambda incident (Dec 12, 2025)
  - Added S3 bucket tagging permissions (`s3:PutBucketTagging`, `s3:GetBucketTagging`)
  - Added IAM role permissions including `iam:UpdateAssumeRolePolicy` for IRSA
  - Updated prevention checklist with S3 and IAM-specific guidance
  - Expanded ARN patterns table with S3 and IAM resources

* **cloudformation:** Standardize descriptions with consistent sub-layer numbering (Dec 12, 2025)
  - Updated 13 CodeBuild project descriptions to use sub-layer format (N.S)
  - Updated 45 CloudFormation template descriptions to use sub-layer format
  - Fixed Layer 6 inconsistency (was 6, 6.5, 6 - now 6.1, 6.2, 6.3, 6.4)
  - Updated CLAUDE.md with complete sub-layer reference table
  - Sub-layers: 1.1-1.2 (Foundation), 2.1 (Data), 3.1 (Compute), 4.1-4.2 (Application), 5.1 (Observability), 6.1-6.4 (Serverless), 7.1 (Sandbox), 8.1 (Security)

* **serverless:** Disable Lambda ReservedConcurrentExecutions due to account quota (Dec 12, 2025)
  - AWS accounts have 10 concurrent execution limit by default
  - ReservedConcurrentExecutions requires 10 unreserved, preventing reservation
  - Disabled in hitl-callback.yaml, orchestrator-dispatcher.yaml, hitl-scheduler.yaml

* **serverless:** Fix Lambda Function URL CORS invalid origin format (Dec 12, 2025)
  - Lambda URLs do not support wildcard subdomains (https://*.domain.com)
  - Changed to `*` for development environments
  - Production should use explicit origin list

* **serverless:** Fix CloudFormation export name mismatch for VPC subnets (Dec 12, 2025)
  - Changed from `aura-private-subnet-1-dev` to `aura-networking-${Environment}-PrivateSubnet1Id`
  - Fixed orchestrator-dispatcher VPC configuration

* **serverless:** Fix IAM role name mismatch in hitl-scheduler (Dec 12, 2025)
  - CodeBuild expected `hitl-expiration-processor-role` but template created `expiration-processor-role`
  - Aligned role name in hitl-scheduler.yaml with CodeBuild IAM policy

* **buildspec:** Add expiration processor Lambda packaging to serverless buildspec (Dec 12, 2025)
  - Added packaging step for expiration_processor.py Lambda
  - Added EXPIRATION_PROCESSOR_S3_KEY variable
  - Added S3 upload for expiration processor package
  - Added LambdaS3Bucket and LambdaS3Key parameters to HITL Scheduler deployment

* **iam:** Add missing serverless layer IAM permissions (Dec 11, 2025)
  - Added CloudFormation stack permissions for `hitl-callback`, `orchestrator-dispatcher`, `a2a-infrastructure` stacks
  - Added IAM role creation permissions for `approval-callback`, `orchestrator-dispatcher`, `a2a-*` roles
  - Fixed AccessDenied for CloudFormation CreateStack and iam:CreateRole operations

* **buildspec:** Use bash shell to fix [[ conditional syntax (Dec 11, 2025)
  - CodeBuild was using /bin/sh which doesn't support [[ ]] bash conditionals
  - Added `shell: bash` to env section to ensure bash is used for all commands
  - Fixed ROLLBACK_COMPLETE stack detection and auto-cleanup logic

* **buildspec:** Handle ROLLBACK_COMPLETE stacks when ECR repo exists (Dec 11, 2025)
  - Added stack status check before deciding create vs update
  - Auto-delete failed stacks (ROLLBACK_COMPLETE, CREATE_FAILED, DELETE_FAILED)
  - Clean up orphaned failed stacks when repository already exists

### Features

* **agents:** Implement AWS Agent Capability Replication - ADR-030 (Dec 11, 2025)
  - Phase 1: AgentCore services - agent_evaluation_service (13 evaluators, A/B testing), agent_runtime_service, episodic_memory_service, cedar_policy_engine
  - Phase 2: Security Agent - pr_security_scanner (SAST, SCA, IaC), dynamic_attack_planner (MITRE ATT&CK), org_standards_validator (40+ rules), security_agent_orchestrator
  - Phase 3: DevOps Agent - deployment_history_correlator (86% incident correlation), resource_topology_mapper (multi-cloud), incident_pattern_analyzer (SLO/burn rate), devops_agent_orchestrator
  - Phase 4: Transform Agent - cobol_parser (DB2/CICS), dotnet_parser (C#/VB.NET), cross_language_translator (COBOL→Python/Java), architecture_reimaginer (DDD decomposition), transform_agent_orchestrator
  - 21 new services, ~15,000 lines of Python code
  - Enterprise-ready agent framework for code modernization and DevOps automation

* **chat:** Deploy ADR-030 Chat Assistant to AWS (Dec 10, 2025)
  - All 4 Lambda functions deployed and operational (chat-handler, ws-connect, ws-disconnect, ws-message)
  - REST API Gateway with Cognito authentication active
  - WebSocket API Gateway with streaming support active
  - Fixed Bedrock message format (removed OpenAI-style `type` wrapper)
  - Updated model IDs to use Bedrock inference profiles for on-demand invocation
  - 131 tests passing

* **frontend:** Add research task state management to ChatContext (Dec 10, 2025)
  - New `researchTasks` state with localStorage persistence
  - `startResearchTask()` - initiates async research with progress tracking
  - `pollResearchStatus()` - polls API for task updates
  - `dismissResearchTask()` / `clearCompletedResearchTasks()` - task lifecycle
  - `activeResearchTasks` computed property for UI indicators
  - Automatic polling with cleanup on completion/failure
  - Mock research simulation for development mode
  - `generateMockResearchResult()` for security, architecture, and quality queries

* **chat:** Add deep research tools for async analysis tasks (Dec 10, 2025)
  - New `research_tools.py` with `DeepResearchService` class
  - Added `start_deep_research` tool (tool #10) for complex analysis tasks
  - Added `get_research_status` tool (tool #11) for task tracking
  - Supports security audits, architecture reviews, code quality analysis
  - ResearchTask dataclass with status, progress, and result tracking
  - New DynamoDB table `aura-research-tasks-{env}` with TTL and GSIs
  - User and tenant isolation via GSI indexes
  - Urgency levels: standard (async), urgent (streaming)
  - Data sources: code_graph, security_findings, agent_logs, audit_trail
  - Mock data generation for dev environments without DynamoDB

* **chat:** Add diagram generation tool with Mermaid frontend rendering (Dec 10, 2025)
  - New `diagram_tools.py` with `DiagramGenerator` class
  - Added `generate_diagram` tool to chat assistant (tool #9)
  - Supports 7 diagram types: flowchart, sequence, class, ER, state, architecture, dependency
  - 3 output formats: Mermaid (in-chat), PlantUML (server-side), draw.io (XML export)
  - Pre-built templates for agent orchestration, auth flow, chat flow, HITL workflow, data model
  - New `MermaidDiagram` React component with SVG/PNG export buttons
  - Auto-detects mermaid code blocks by language tag or diagram syntax
  - Added `mermaid` npm dependency (^11.4.0)
  - Aura-branded theme with primary (#3B82F6) and secondary (#84CC16) colors

* **chat:** Implement 3-tier intelligent model routing for chat assistant (Dec 10, 2025)
  - Added `ModelTier` enum (FAST/ACCURATE/MAXIMUM) for query classification
  - Added `ModelSpec` dataclass for multi-provider model configuration
  - Pattern-based query routing: greetings → Haiku, code analysis → Sonnet, deep research → Opus
  - New `classify_query_tier()` function with regex pattern matching
  - Enhanced `select_model()` with optional tier override
  - Added `OPUS_MODEL_ID` parameter to CloudFormation template
  - Updated Bedrock IAM permissions for all 3 model tiers
  - Cost optimization: ~8% savings vs all-Sonnet routing

* **autonomy:** Implement Configurable Autonomy Framework for 85% autonomous operation (Dec 10, 2025)
  - Created `AutonomyPolicyService` for runtime policy enforcement and persistence
  - 7 pre-built policy presets: defense_contractor, financial_services, healthcare, fintech_startup, enterprise_standard, internal_tools, fully_autonomous
  - Configurable HITL toggle at organization level
  - Granular overrides by severity, operation, and repository
  - Guardrails for critical operations (production_deployment, credential_modification, etc.)
  - 3 new DynamoDB tables: autonomy-policies, policy-audit, autonomy-decisions
  - REST API endpoints for policy management (`/api/v1/autonomy/*`)
  - 37 comprehensive tests covering all scenarios
  - ADR-032 documents the architecture decision
  - Enables commercial enterprise adoption without mandatory HITL delays

* **neptune:** Add dual deployment mode support - provisioned and serverless (Dec 10, 2025)
  - Created `neptune-serverless.yaml` for cost-optimized commercial deployments
  - Updated `neptune-simplified.yaml` with NeptuneMode and GovCloudCompatible outputs
  - Provisioned mode: 100% GovCloud-compatible, ~$82/month
  - Serverless mode: 63-82% cost savings for dev/test (NOT GovCloud-compatible)
  - Separate templates avoid CloudFormation logical ID conflicts during mode changes
  - Updated `buildspec-data.yml` to explicitly pass `NeptuneMode=provisioned`

* **docs:** Add ADR-031 Neptune Deployment Mode Configuration (Dec 10, 2025)
  - Documents dual-template approach for provisioned vs serverless Neptune
  - Explains why single-template conditional resources were rejected
  - Provides cost comparison and use case guidance

* **security:** Deploy CloudFormation drift detection infrastructure (Dec 9, 2025)
  - New stack `aura-drift-detection-dev` with Lambda-based drift monitoring
  - Lambda function `aura-drift-detector-dev` runs every 6 hours
  - SNS topic `aura-drift-alerts-dev` for email notifications
  - Critical stack monitoring: IAM, Security, Networking, Neptune
  - Auto-remediation disabled (HITL-compliant manual review)
  - Added `drift-detection.yaml` to active CloudFormation templates
  - Updated `buildspec-security.yml` to deploy drift detection
  - Fixed GovCloud ARN partition compatibility (`arn:aws` → `${AWS::Partition}`)
  - Parameterized: LambdaTimeout, LambdaMemorySize, LogRetentionDays, CriticalStacks

* **iam:** Add drift-detection permissions to security CodeBuild role (Dec 9, 2025)
  - CloudFormation: drift-detection and red-team stack permissions
  - Lambda: drift-detector function CRUD operations
  - SNS: drift-alerts topic
  - EventBridge: drift-* rules
  - CloudWatch: drift-* alarms and logs
  - IAM: drift-detector-lambda role management

* **cicd:** 100% CI/CD coverage for all CloudFormation templates (Dec 9, 2025)
  - Created 2 new CodeBuild projects for new layers:
    - `codebuild-incident-response.yaml` (Layer 6.5: Incident Tracking, RCA Workflows)
    - `codebuild-network-services.yaml` (Layer 1.5: VPC-wide DNS via ECS Fargate)
  - Created corresponding buildspecs:
    - `buildspec-incident-response.yml` - Deploys incident-response.yaml, incident-investigation-workflow.yaml
    - `buildspec-network-services.yml` - Deploys network-services.yaml
  - Updated 5 existing buildspecs to add 8 templates:
    - buildspec-compute.yml: +acm-certificate.yaml, +alb-controller.yaml
    - buildspec-application.yml: +cognito.yaml, +bedrock-guardrails.yaml
    - buildspec-observability.yml: +disaster-recovery.yaml, +otel-collector.yaml
    - buildspec-serverless.yml: +a2a-infrastructure.yaml
    - buildspec-security.yml: +red-team.yaml
  - Created deploy scripts: deploy-incident-response-codebuild.sh, deploy-network-services-codebuild.sh
  - All 49 CloudFormation templates now managed by 13 buildspecs

### Documentation

* **runbooks:** Create layer-specific operational runbooks (Dec 9, 2025)
  - 8 runbooks in `docs/runbooks/LAYER*_RUNBOOK.md`:
    - LAYER1_FOUNDATION_RUNBOOK.md (VPC, IAM, Security Groups)
    - LAYER2_DATA_RUNBOOK.md (Neptune, OpenSearch, DynamoDB, S3)
    - LAYER3_COMPUTE_RUNBOOK.md (EKS, Node Groups)
    - LAYER4_APPLICATION_RUNBOOK.md (Bedrock, ECR, K8s Deployments)
    - LAYER5_OBSERVABILITY_RUNBOOK.md (Secrets, Monitoring, Cost Alerts)
    - LAYER6_SERVERLESS_RUNBOOK.md (Lambda, EventBridge)
    - LAYER7_SANDBOX_RUNBOOK.md (HITL, Step Functions)
    - LAYER8_SECURITY_RUNBOOK.md (AWS Config, GuardDuty)
  - Each includes: resources deployed, dependencies, troubleshooting, recovery procedures

* **audit:** Create resource deployment audit documents (Dec 9, 2025)
  - `docs/RESOURCE_DEPLOYMENT_AUDIT.md` - 3-phase deployment model, 49 templates, dependency graph
  - `docs/BUILDSPEC_COMPLEXITY_ANALYSIS.md` - Timeout risk assessment, template placement decisions

### Refactors

* **cicd:** Remove hardcoded environment variables from all buildspecs (Dec 8, 2025)
  - All 11 buildspecs now follow CLAUDE.md parameterization guidelines
  - Environment variables (ENVIRONMENT, PROJECT_NAME, AWS_ACCOUNT_ID, AWS_DEFAULT_REGION) sourced from CodeBuild project CloudFormation parameters
  - Files: buildspec-chat-assistant, foundation, data, compute, application, observability, serverless, sandbox, security, orchestrator, service-frontend

### Bug Fixes

* **cicd:** Fix frontend buildspec for Argo Rollouts compatibility (Dec 8, 2025)
  - Added kubectl-argo-rollouts plugin installation to buildspec
  - Changed `kubectl set image deployment/` to `kubectl argo rollouts set image`
  - Changed `kubectl rollout restart/status` to Argo Rollouts equivalents
  - Frontend now deploys correctly via canary rollout strategy

* **iam:** Add dynamodb:UpdateContinuousBackups permission to data CodeBuild role (Dec 8, 2025)
  - CloudFormation stack updates were failing with AccessDenied when enabling PITR
  - Added `dynamodb:UpdateContinuousBackups` and `dynamodb:DescribeContinuousBackups` to `codebuild-data.yaml`

### Tests

* **chat:** Add comprehensive unit tests for enhanced chat assistant (Dec 10, 2025)
  - 131 tests across 4 test files (industry best practice: 1 file per feature)
  - `test_model_routing.py` - 39 tests: ModelTier classification, query routing, model catalog
  - `test_diagram_generation.py` - 30 tests: DiagramGenerator, templates, 3 output formats
  - `test_deep_research.py` - 34 tests: ResearchTask lifecycle, quick detection, result generation
  - `test_tools.py` - 28 tests: CHAT_TOOLS definitions, execute_tool, 11 tool implementations
  - `conftest.py` - Shared fixtures: mock AWS credentials, DynamoDB tables, Bedrock client
  - Updated `CLAUDE.md` with test file organization best practices

### Documentation

* **runbook:** Create DynamoDB PITR Enable Runbook (Dec 8, 2025)
  - New `docs/runbooks/` directory for operational runbooks
  - `docs/runbooks/DYNAMODB_PITR_ENABLE.md` - Procedure for enabling PITR on existing DynamoDB tables
  - Documents CloudFormation limitation (cannot modify PITR on existing tables)
  - Includes CLI commands, verification steps, troubleshooting for IAM issues

### Features

* **adr-029:** Agent Optimization Roadmap - Advanced AI Innovations Integration (Dec 8, 2025)
  - Phased implementation plan for 7 high-impact AI agent innovations
  - **Phase 1 (Q1 2026)**: Quick Wins - 40-70% LLM cost reduction
    - Bedrock Guardrails Automated Reasoning (99% validation accuracy)
    - Chain of Draft (CoD) prompting (92% token reduction)
    - Semantic Caching via OpenSearch (68% cache hit rate)
    - Model Context Protocol (MCP) completion
  - **Phase 2 (Q2 2026)**: Strategic Enhancements - ✅ ALL COMPLETE
    - ✅ Complete ADR-024 Titan Memory integration
    - ✅ Self-Reflection for Reviewer Agent (30% fewer false positives)
    - ✅ A2AS Security Framework (95%+ injection detection)
  - Detailed cost-benefit analysis, risk assessment, implementation timeline
  - Source: `research/ADVANCED_AI_AGENT_INNOVATIONS_2024_2025.md`

* **adr-029-phase-2.3:** Implement A2AS Security Framework (Dec 8, 2025)
  - `src/services/a2as_security_service.py` - Four-layer defense architecture (~700 lines)
    - Layer 1: `A2ASCommandVerifier` - HMAC-SHA256 command signing and verification
    - Layer 2: `A2ASSandboxEnforcer` - Block metadata service, dangerous commands, output limits
    - Layer 3: `A2ASInjectionFilter` - Pattern detection for prompt/code/SQL/path/command injection
    - Layer 4: Multi-layer validation (behavioral analysis + AI-assisted assessment)
    - `ThreatLevel` enum (NONE, LOW, MEDIUM, HIGH, CRITICAL)
    - `SecurityAssessment` dataclass for comprehensive threat reporting
    - Behavioral analysis: entropy (>4.0 suspicious), length (>10K suspicious), special char ratio
    - AI-assisted validation support for complex threats
    - HITL escalation for critical/high severity threats
  - `tests/security/test_a2as_framework.py` - 56 unit tests (all passing)
    - Injection filter tests: prompt, code, SQL, path, command injection detection
    - Command verification tests: signing, verification, replay protection
    - Sandbox enforcement tests: metadata blocking, command restrictions, output limits
    - Multi-layer validation tests: behavioral + AI analysis
    - End-to-end security assessment tests
  - Expected benefit: 95%+ injection detection rate

* **adr-029-phase-1.1:** Implement Bedrock Guardrails Automated Reasoning (Dec 8, 2025)
  - `deploy/cloudformation/bedrock-guardrails.yaml` - CloudFormation infrastructure (~250 lines)
    - Content filtering (HATE, SEXUAL, VIOLENCE, MISCONDUCT, PROMPT_ATTACK)
    - PII protection (SSN, credit cards, AWS credentials, API keys, JWT tokens)
    - Topic blocking (malware creation, social engineering, credential theft)
    - SSM parameters for runtime configuration
    - CloudWatch alarm for high block rate monitoring
  - `src/config/guardrails_config.py` - Guardrail configuration module (~400 lines)
    - Environment-based modes (DETECT for dev, ENFORCE for prod)
    - Default content filters, PII entities, blocked topics
    - SSM parameter loading for guardrail IDs
    - Trace formatting for violation analysis
  - `src/services/bedrock_llm_service.py` - Guardrails integration (~100 lines added)
    - Automatic guardrail application on model invocations
    - GuardrailViolationError for blocked content
    - Guardrail trace logging for visibility
  - 35 unit tests for guardrails configuration
  - Deployed: `aura-bedrock-guardrails-dev` stack operational

* **adr-029-phase-1.2:** Implement Chain of Draft (CoD) Prompting (Dec 8, 2025)
  - `src/prompts/cod_templates.py` - CoD/CoT templates for all agents (~500 lines)
    - Minimalist reasoning prompts (1-5 words per step)
    - 92% token reduction vs traditional Chain of Thought
    - Templates for reviewer, coder, validator, query_planner agents
    - `CoDPromptMode` enum (COD, COT, AUTO)
    - `build_cod_prompt()` for template selection
    - `estimate_token_savings()` for cost analysis
  - `src/prompts/ab_testing.py` - A/B testing framework (~400 lines)
    - `ABTestRunner` for comparing CoD vs CoT effectiveness
    - Token usage tracking, latency measurement
    - Accuracy scoring via optional callbacks
    - `ABTestSummary` with aggregate statistics
  - Agent integrations:
    - `src/agents/reviewer_agent.py` - CoD in `_review_code_llm`
    - `src/agents/coder_agent.py` - CoD in `_generate_code_llm`
    - `src/agents/validator_agent.py` - CoD in `_enhanced_analysis_llm`, `_validate_requirements_llm`
    - `src/agents/query_planning_agent.py` - CoD in `_build_planning_prompt`
  - 26 unit tests for CoD templates (all passing)
  - Graceful fallback to CoT when CoD imports fail
  - Environment variable override: `AURA_PROMPT_MODE=cod|cot|auto`

* **adr-029-phase-1.3:** Implement Semantic Caching Enhancement (Dec 8, 2025)
  - `src/services/semantic_cache_service.py` - GPTCache-style semantic cache (~600 lines)
    - OpenSearch k-NN for similarity search (HNSW algorithm, cosine similarity)
    - 0.92 similarity threshold for 97%+ hit accuracy
    - 60-70% expected cache hit rate
    - Query-type-specific TTLs (vulnerability: 24h, review: 12h, generation: 1h)
    - `CacheMode` enum (DISABLED, WRITE_ONLY, READ_WRITE, READ_ONLY)
    - `QueryType` enum for TTL determination
    - Cost savings estimation per cache hit
    - Statistics tracking (hit rate, latency, cost saved)
  - `src/services/bedrock_llm_service.py` - Semantic cache integration (~100 lines added)
    - `OPERATION_QUERY_TYPE_MAP` for operation-to-cache-type mapping
    - `async def generate()` now checks semantic cache first
    - Automatic response caching after LLM calls
    - `get_semantic_cache_stats()` method for monitoring
    - `create_llm_service(enable_semantic_cache=True)` factory option
  - 27 unit tests for semantic cache (all passing)
    - Cache entry creation, serialization, TTL expiration
    - Cache modes (disabled, read-only, write-only, read-write)
    - Hit/miss statistics tracking
    - Integration with BedrockLLMService

* **adr-029-phase-1.4:** Implement MCP Tool Server Completion (Dec 8, 2025)
  - `src/services/mcp_tool_server.py` - MCP server for internal tools (~700 lines)
    - Industry-standard MCP protocol integration (adopted by OpenAI, Microsoft, Google)
    - Tool handlers: `GraphToolHandler`, `VectorToolHandler`, `SandboxToolHandler`
    - 7 internal tools: query_code_graph, get_code_dependencies, semantic_search,
      index_code_embedding, provision_sandbox, destroy_sandbox, get_sandbox_status
    - HITL approval integration for sensitive operations (provision_sandbox)
    - Tool statistics tracking (invocations, latency, success rate)
    - `MCPToolDefinition`, `MCPToolResult`, `MCPServerStats` dataclasses
  - `src/agents/base_agent.py` - Base agent with MCP support (~500 lines)
    - `MCPToolMixin` - Composable mixin for adding tool capabilities to any agent
    - `BaseAgent` - Abstract base class with task execution and metrics
    - `MCPEnabledAgent` - Combined class for full MCP tool support
    - `invoke_tool()`, `invoke_tools_parallel()` for standardized tool access
    - `_request_hitl_approval()` for sensitive operations (auto-approve in dev)
    - `AgentTask`, `AgentResult`, `HITLApprovalRequest/Response` dataclasses
    - Tool discovery and metrics tracking
  - `src/agents/agent_orchestrator.py` - MCP integration (~80 lines added)
    - `mcp_server` and `mcp_client` parameters in __init__
    - `get_available_mcp_tools()`, `invoke_mcp_tool()`, `has_mcp_tool()` methods
    - `create_system2_orchestrator(enable_mcp=True)` factory option
  - 71 unit tests for MCP components (all passing)
    - `tests/test_mcp_tool_server.py` - 39 tests
    - `tests/test_base_agent.py` - 32 tests

* **adr-029-phase-2.1:** Implement Titan Memory Integration (Dec 8, 2025)
  - `src/agents/context_objects.py` - Added NEURAL_MEMORY context source (~10 lines)
    - `ContextSource.NEURAL_MEMORY` enum value for neural memory items
    - `HybridContext.add_memory_context()` - Integrates Titan cognitive context (~50 lines)
    - High/low confidence messaging based on neural_confidence threshold
    - Metadata tracking for surprise, latency, strategy
  - `src/agents/agent_orchestrator.py` - Titan Memory workflow integration (~100 lines)
    - `titan_memory` parameter in `__init__()` for TitanCognitiveService injection
    - New workflow phases: MEMORY (Phase 2), LEARN (Phase 8)
    - `load_cognitive_context()` call before agent tasks with domain="security_remediation"
    - `_store_experience_in_memory()` helper for surprise-driven memorization
    - Neural confidence tracking in result dict
    - `create_system2_orchestrator(enable_titan_memory=True)` factory option
  - `src/agents/coder_agent.py` - Memory-informed code generation (~15 lines)
    - Extracts neural memory signals from HybridContext
    - Adds memory guidance to LLM prompt (high/low confidence messaging)
    - Leverages past experiences for familiar patterns
  - `src/agents/reviewer_agent.py` - Memory-informed security review (~40 lines)
    - `review_code(code, context)` now accepts optional HybridContext
    - `memory_informed` flag in result dict
    - Memory guidance injection for LLM review prompt
    - Adds "Memory-Informed Review" policy when context present
  - `tests/test_titan_memory_integration.py` - 22 unit tests (all passing)
    - Tests for NEURAL_MEMORY source, add_memory_context, orchestrator integration
    - Tests for experience storage, agent memory guidance, factory function
  - Builds on ADR-024 TitanCognitiveService foundation
  - Expected benefit: 2M+ token effective context via neural memory retrieval

* **adr-029-phase-2.2:** Implement Self-Reflection for Reviewer (Dec 8, 2025)
  - `src/agents/reflection_module.py` - Self-critique module (~430 lines)
    - `ReflectionResult` dataclass with was_refined(), confidence_improved(), to_dict()
    - `ReflectionModule` class implementing Reflexion framework
    - `reflect_and_refine()` - Main loop: critique → check confidence → revise
    - `_self_critique()` - LLM-powered self-examination with fallback
    - `_revise_output()` - Output refinement based on critique
    - Configurable `max_iterations` (default: 3) and `confidence_threshold` (default: 0.9)
    - `REVIEWER_REFLECTION_PROMPT`, `CODER_REFLECTION_PROMPT` constants
    - `create_reflection_module()` factory function
  - `src/agents/reviewer_agent.py` - Self-reflection integration (~50 lines)
    - `enable_reflection` parameter in `__init__()` and factory function
    - `ReflectionModule` initialization when enabled with LLM
    - `review_code()` now includes self-reflection loop when enabled
    - New result fields: `reflection_applied`, `reflection_iterations`, `reflection_confidence`
    - Additional ~1500 tokens for reflection loop
  - `tests/test_reflection_module.py` - 29 unit tests (all passing)
    - TestReflectionResult, TestReflectionModule, TestReflectionModuleWithLLM
    - TestReviewerAgentWithReflection, TestCreateReflectionModule
    - Tests for high/low confidence, max iterations, fallback behavior
  - Expected benefit: 30% reduction in false positives

* **adr-028:** Implement Foundry capability adoption (Dec 7-8, 2025) - **Issues #22-29 CLOSED**
  - **Phase 1: Model Router** (#23) - LLM provider routing with cost/latency optimization
    - `src/services/model_router.py` - Multi-provider routing (OpenAI, Anthropic, Bedrock)
    - Task complexity analysis, provider health monitoring, cost tracking
    - 23 unit tests
  - **Phase 2: OpenTelemetry Adoption** (#22) - Distributed tracing and metrics
    - `src/services/otel_instrumentation.py` - OTel integration with CloudWatch/X-Ray
    - `deploy/cloudformation/otel-collector.yaml` - Collector infrastructure
    - 15 unit tests
  - **Phase 3: Agentic Retrieval Enhancement** (#24) - Query decomposition
    - `src/services/query_analyzer.py` - LLM-powered query decomposition
    - `src/services/parallel_query_executor.py` - Parallel subquery execution
    - 48 unit tests
  - **Phase 4: VS Code Extension** (#25) - In-IDE vulnerability scanning
    - `vscode-extension/` - Full extension with providers, commands, CodeLens
    - `src/api/extension_endpoints.py` - Scan, findings, patches, approvals API
    - 31 unit tests
  - **Phase 5: TypeScript SDK** (#26) - Frontend/Node.js integration
    - `sdk/typescript/` - Full SDK with client, React hooks, utilities
    - AuraClient, useApprovals, useVulnerabilities, useIncidents hooks
    - Type definitions for all API responses
  - **Phase 6: A2A Protocol Support** (#27) - Agent-to-Agent interoperability (Dec 7, 2025)
    - `src/services/a2a_gateway.py` - JSON-RPC 2.0 gateway with Agent Cards
    - `src/services/a2a_agent_registry.py` - External agent registration, health monitoring
    - `src/api/a2a_endpoints.py` - REST API for A2A operations
    - `deploy/cloudformation/a2a-infrastructure.yaml` - DynamoDB, SQS, EventBridge
    - 46 unit tests
  - **Phase 7: Red-Teaming Automation** (#28) - Adversarial security testing (Dec 8, 2025)
    - `src/agents/red_team_agent.py` - Prompt injection, code injection, sandbox escape detection
    - `src/services/adversarial_input_service.py` - 40+ OWASP patterns, AI-specific attacks, fuzzing
    - `deploy/cloudformation/red-team.yaml` - S3, DynamoDB, ECS, SNS infrastructure
    - 53 unit tests
  - **Phase 8: Enterprise Connectors** (#29) - External security tool integration (Dec 8, 2025)
    - 7 new connectors: ServiceNow, Splunk, Azure DevOps, Terraform Cloud, Snyk, CrowdStrike, Qualys
    - OAuth2/API key authentication, async HTTP, metrics tracking
    - ITSM, SIEM, CI/CD, IaC, SCA, EDR/XDR, vulnerability scanning integration
    - 69 unit tests
  - **Infrastructure**: ALB Ingress Controller, OTel Collector deployment configs
  - **Total**: 322 new tests, 26,000+ lines added

* **ui:** Implement Query Decomposition Panel (Dec 8, 2025) - **GitHub Issue #32 CLOSED**
  - `src/api/query_decomposition_endpoints.py` - Decompose, get, list endpoints (~310 lines)
  - `frontend/src/components/QueryDecompositionPanel.jsx` - Visual subquery flow (~350 lines)
  - Color-coded query types: Structural (Neptune), Semantic (OpenSearch), Temporal (git)
  - Confidence scores, execution time, parallel execution plan visualization
  - Integrated into CKGEConsole for real-time query analysis
  - 23 unit tests

* **ui:** Implement Red Team Dashboard (Dec 8, 2025) - **GitHub Issue #33 CLOSED**
  - `src/api/red_team_endpoints.py` - Security gate status, findings, trends API (~640 lines)
  - `frontend/src/components/RedTeamDashboard.jsx` - CI gate status, category tests, findings (~750 lines)
  - Security gate badges: PASSING/FAILING/WARNING with trend indicators
  - Test categories: Prompt Injection, Code Injection, Data Exfiltration, Sandbox Escape, Auth Bypass
  - Finding severity colors: CRITICAL, HIGH, MEDIUM, LOW
  - Route: `/security/red-team`, sidebar navigation added
  - 32 unit tests

* **ui:** Implement Integration Hub (Dec 8, 2025) - **GitHub Issue #34 CLOSED**
  - `src/api/integration_endpoints.py` - Full CRUD for integrations (~560 lines)
  - `frontend/src/components/IntegrationHub.jsx` - Connected/available integrations, wizard (~900 lines)
  - 3-step configuration wizard modal with field validation
  - 10 connectors: CrowdStrike, Qualys, GitHub, GitLab, Jira, Slack, PagerDuty, AWS, Datadog, ServiceNow
  - Category filters: Security, CI/CD, Monitoring, Cloud, Communication, Ticketing
  - Connection test panel with live status updates
  - Route: `/settings/integrations`, sidebar navigation added
  - 32 unit tests

* **ui:** Implement Agent Registry (Dec 8, 2025) - **GitHub Issue #35 CLOSED**
  - `src/api/agent_registry_endpoints.py` - Agent listing, connect/disconnect, metrics (~590 lines)
  - `frontend/src/components/AgentRegistry.jsx` - Internal/external agents, marketplace (~850 lines)
  - Internal Aura agents: Orchestrator, Coder, Reviewer, Validator (always visible)
  - External A2A agents: Connect from marketplace, health monitoring, trust levels
  - Marketplace: 8 available agents (Snyk, Datadog, SonarQube, GitHub Copilot, AWS CodeWhisperer, Semgrep, Trivy, Checkmarx)
  - Agent detail modal with metrics and connection testing
  - Route: `/agents/registry`, sidebar navigation added
  - 44 unit tests

* **design:** Add comprehensive App UI Blueprint (Dec 7, 2025)
  - Created `agent-config/design-workflows/app-ui-blueprint.md` with full UI/UX design plan
  - Defined 4 user personas: Security Engineer, DevOps Engineer, Platform Admin, Engineering Leadership
  - Mapped 3 core workflows: Vulnerability-to-Production, Incident Investigation, Code Graph Exploration
  - Inventoried 15 UI screens (6 implemented, 9 required)
  - Specified 25+ reusable UI components across 5 categories
  - Documented 4 interaction patterns: Master-Detail, Tabbed Config, HITL Approval, Progressive Disclosure
  - Created 5-phase implementation roadmap (10 weeks)

* **ui:** Add Incidents navigation to sidebar (Dec 7, 2025) - **GitHub Issue #9 CLOSED**
  - Added ExclamationTriangleIcon and Incidents link to CollapsibleSidebar.jsx

### Infrastructure

* **dr:** Implement Disaster Recovery infrastructure (Dec 8, 2025) - **GitHub Issue #14 CLOSED**
  - `deploy/cloudformation/disaster-recovery.yaml` (~320 lines) - AWS Backup vault, plans, SNS alerts
  - AWS Backup daily plan (3 AM UTC) for Neptune, DynamoDB, EBS with environment-specific retention
  - Hourly backup plan (production only) for critical DynamoDB tables
  - Cross-region backup copy to us-west-2 (production only)
  - KMS encryption for backup vault with automatic key rotation
  - CloudWatch alarms for backup failures and success monitoring
  - EventBridge rule for backup job state change notifications
  - Updated `deploy/cloudformation/opensearch.yaml` - Added automated snapshots at 2 AM UTC
  - Updated `deploy/cloudformation/dynamodb.yaml` - Enabled PITR for ALL environments (was prod-only)
  - `docs/DISASTER_RECOVERY.md` (~500 lines) - Comprehensive DR documentation
    - RTO/RPO targets per service (Neptune 4h/24h, DynamoDB 1h/1h, S3 1h/0)
    - Recovery procedures for region failure, database corruption, accidental deletion, EKS failure
    - Quarterly DR test schedule and escalation contacts

* **alb:** Deploy AWS ALB Ingress Controller for HTTPS access (Dec 8, 2025) - **GitHub Issue #12 CLOSED**
  - `deploy/cloudformation/alb-controller.yaml` - IAM role with IRSA for ALB controller
  - `deploy/cloudformation/acm-certificate.yaml` - ACM certificate template
  - ACM wildcard certificate for `*.aenealabs.com` with DNS validation
  - AWS Load Balancer Controller v2.16.0 deployed via Helm
  - `deploy/kubernetes/alb-controller/values.yaml` - Helm configuration
  - `deploy/kubernetes/alb-controller/aura-api-ingress.yaml` - API ingress (api.aenealabs.com)
  - `deploy/kubernetes/alb-controller/aura-frontend-ingress.yaml` - Frontend ingress (app.aenealabs.com)
  - Ingress group consolidates both into single ALB for cost efficiency
  - TLS 1.3 security policy, WAF ACL attached, HTTP to HTTPS redirect
  - Route 53 ALIAS records for app.aenealabs.com and api.aenealabs.com

* **auth:** Add user authentication with AWS Cognito (Dec 8, 2025) - **GitHub Issue #11 CLOSED**
  - `deploy/cloudformation/cognito.yaml` (~280 lines) - Cognito User Pool infrastructure
    - User Pool with email/password, CMMC-compliant password policy (12+ chars, mixed case, numbers, symbols)
    - User groups: admin, security-engineer, developer, viewer for RBAC
    - OAuth2 PKCE flow with callback URLs for localhost and production domains
    - SSM parameters for configuration values
  - `frontend/src/config/auth.js` - Cognito configuration with environment variables
  - `frontend/src/context/AuthContext.jsx` (~200 lines) - React Context for auth state
    - Token storage, parsing, refresh logic with JWT decoding
    - OAuth callback handling, login/logout functions
    - `useAuth` hook for component access
  - `frontend/src/components/LoginPage.jsx` (~130 lines) - Login page with Cognito hosted UI
  - `frontend/src/components/AuthCallback.jsx` (~130 lines) - OAuth callback handler
  - `frontend/src/components/ProtectedRoute.jsx` (~120 lines) - Route wrapper with RBAC
    - Role-based access control, loading spinner, access denied views
  - `frontend/src/components/UserMenu.jsx` (~130 lines) - User dropdown for sidebar
  - `src/api/auth.py` (~220 lines) - FastAPI Cognito JWT middleware
    - JWKS-based token validation, role-based access control dependencies
    - `get_current_user`, `get_optional_user`, `require_role` dependencies
  - Updated `src/api/main.py` - CORS configuration, `/api/v1/auth/me` and `/api/v1/auth/validate` endpoints
  - Updated `frontend/src/App.jsx` - AuthProvider wrapper, protected routes
  - Updated `frontend/src/components/CollapsibleSidebar.jsx` - Integrated UserMenu

* **e2e:** Full E2E test pipeline validated (Dec 7, 2025)
  - 2,786 tests collected, 2,738 passed, 48 skipped, 0 failed
  - RuntimeIncidentAgent E2E test passed in 92.68s with real Bedrock LLM
  - All Bedrock E2E tests (4/4) passed with Claude 3.5 Sonnet
  - ObservabilityMCPAdapter tests (4/4) fixed and passing

* **adr-025:** Wire up BedrockLLMService for RuntimeIncidentAgent LLM-powered RCA (Dec 7, 2025)
  - **Problem Solved**
    - RuntimeIncidentAgent was running but returning empty RCA with 0% confidence
    - Logs showed "No LLM client available, returning default RCA"
    - GitHub Issue #10 reported 15+ min execution time (actual issue was missing LLM integration)
  - **Solution**
    - Wired up BedrockLLMService initialization in `runtime_incident_cli.py`
    - Added `rca_generation` and `mitigation_planning` operations to OPERATION_MODEL_MAP
    - Fixed torch import issue with conditional imports in `src/services/__init__.py`
  - **Files Modified**:
    - `src/agents/runtime_incident_cli.py` - BedrockLLMService initialization
    - `src/services/bedrock_llm_service.py` - Added ADR-025 operations
    - `src/services/__init__.py` - Conditional torch imports
  - **Impact**: RuntimeIncidentAgent now generates LLM-powered RCA with 70%+ confidence scores

* **vpc:** Add VPC endpoints for private subnet LLM access (Dec 7, 2025)
  - **Problem Solved**
    - ECS Fargate tasks in private subnets (no NAT Gateway) couldn't reach AWS services
    - BedrockLLMService initialization hung indefinitely waiting for network connections
  - **Solution**
    - Added Bedrock Runtime VPC endpoint for LLM model invocations
    - Added Secrets Manager VPC endpoint for config loading
    - Added CloudWatch Monitoring VPC endpoint for metrics
    - Added STS VPC endpoint for IAM credential refresh
  - **Files Modified**: `deploy/cloudformation/vpc-endpoints.yaml`
  - **Cost Impact**: +$43.80/month (3 additional interface endpoints x 2 AZs)
  - **Impact**: Full AWS service connectivity from private subnets

### Bug Fixes

* **tests:** Fix ObservabilityMCPAdapter tests (Dec 7, 2025)
  - **Problem Solved**
    - 4 tests failing with "requires ENTERPRISE mode. Current mode: defense"
    - Async context manager mocking for aiohttp was incorrect
  - **Solution**
    - Created AsyncContextManagerMock helper class with proper `__aenter__`/`__aexit__`
    - Added mock_enterprise_mode fixture to patch get_integration_config
    - Updated deprecated datetime.utcnow() to datetime.now(UTC)
  - **Files Modified**: `tests/test_observability_mcp_adapters.py`
  - **Impact**: All 4 ObservabilityMCPAdapter tests now pass

* **rca:** Improve JSON parsing for LLM RCA responses (Dec 7, 2025)
  - **Problem Solved**
    - LLM responses weren't being parsed correctly, returning "Expecting value: line 1 column 1"
    - Parser didn't handle various LLM response formats (markdown blocks, extra text)
  - **Solution**
    - Added empty response detection with helpful error message
    - Added debug logging for response preview
    - Implemented 3 JSON extraction strategies: ```json blocks, ``` blocks, regex
    - Added fallback to raw text extraction if JSON parsing fails
    - Log successful parse with hypothesis preview and confidence
  - **Files Modified**: `src/agents/runtime_incident_agent.py`
  - **Impact**: RCA parsing now works reliably, extracting hypothesis with confidence scores

* **bedrock:** Use ON_DEMAND models for us-east-1 single-region deployment (Dec 7, 2025)
  - **Problem Solved**
    - Inference profile IDs (us.anthropic.claude-*) route cross-region
    - Requests were routed to us-east-2, causing IAM permission errors
  - **Solution**
    - Switch to ON_DEMAND foundation model IDs that stay in us-east-1:
      - FAST: anthropic.claude-3-haiku-20240307-v1:0
      - ACCURATE: anthropic.claude-3-5-sonnet-20240620-v1:0
      - MAXIMUM: anthropic.claude-3-5-sonnet-20240620-v1:0
  - **Files Modified**: `src/services/bedrock_llm_service.py`
  - **Impact**: All LLM invocations stay in us-east-1 region

* **iam:** Add Bedrock inference profile permissions for Claude 4.x models (Dec 7, 2025)
  - **Problem Solved**
    - IAM policy only allowed foundation-model ARNs, not inference-profile ARNs
    - Claude 4.x models require inference profiles for cross-region invocation
  - **Solution**
    - Added inference profile ARNs to IncidentAgentPolicy
    - Supports both us.anthropic.claude-* and global.anthropic.claude-* profiles
  - **Files Modified**: `deploy/cloudformation/incident-investigation-workflow.yaml`
  - **Impact**: Future-proofed for Claude 4.x when single-region profiles become available

* **sandbox:** Implement S3 code staging for HITL workflow (Dec 7, 2025)
  - **Problem Solved**
    - ECS Fargate tasks in private subnets could not reach GitHub (no NAT Gateway by design)
    - Workflow failed with "Failed to connect to github.com port 443"
  - **Solution**
    - Created `stage-code-for-sandbox.py` script to stage code from Git to S3
    - Updated `run-tests.sh` to download code from S3 via AWS CLI and VPC endpoint
    - Added S3 validation step in Step Functions workflow (validates artifact exists before running tests)
    - Added AWS CLI v2 to Docker image for S3 access
    - Fixed approval_id generation (pre-generate before PutItem to avoid JSONPath error)
    - Added S3 GetObject permission to Step Functions role
  - **Files Modified**:
    - `deploy/scripts/stage-code-for-sandbox.py` (new)
    - `deploy/scripts/trigger-hitl-test.sh` (new)
    - `deploy/docker/sandbox/run-tests.sh`
    - `deploy/docker/sandbox/Dockerfile.test-runner`
    - `deploy/cloudformation/hitl-workflow.yaml`
    - `deploy/cloudformation/sandbox.yaml`
  - **Impact**: HITL workflow now completes successfully, reaching WaitForApproval state

* **workflow:** Fix DynamoDB GetItem to Query for composite key lookup (Dec 7, 2025)
  - **Problem Solved**
    - DynamoDB table uses composite key (incident_id + timestamp), but GetInvestigationResults state used GetItem with only incident_id
    - Step Functions failed with "JsonPath argument could not be found" because Item was empty
  - **Solution**
    - Changed from `dynamodb:getItem` to `aws-sdk:dynamodb:query` resource
    - Added KeyConditionExpression, ScanIndexForward=false, Limit=1 to get latest investigation
    - Updated SendHITLNotification to use Items[0] instead of Item
    - Added `dynamodb:Query` permission to StateMachineExecutionRole
  - **Files Modified**: `deploy/cloudformation/incident-investigation-workflow.yaml`
  - **Impact**: RuntimeIncidentAgent E2E workflow now completes successfully

* **iam:** Add KMS decrypt permissions to Step Functions execution role (Dec 7, 2025)
  - **Problem Solved**
    - DynamoDB table uses KMS encryption, but Step Functions role lacked kms:Decrypt permission
    - Workflow failed with KMS AccessDeniedException when reading investigation results
  - **Solution**
    - Added kms:Decrypt and kms:GenerateDataKey to StateMachineExecutionRole
    - Used `!ImportValue` for KMS key ARN from incident-response stack
    - Added kms:ViaService condition for DynamoDB only
  - **Files Modified**: `deploy/cloudformation/incident-investigation-workflow.yaml`
  - **Impact**: Step Functions can now read/write encrypted DynamoDB tables

* **security:** Add OpenSearch HTTPS egress rule for VPC endpoint access (Dec 7, 2025)
  - **Problem Solved**
    - VPC-based OpenSearch Service uses HTTPS (443), but ECS workload SG only had port 9200 egress
    - ECS tasks could not connect to OpenSearch VPC endpoint
  - **Solution**
    - Added ECSWorkloadToOpenSearchHTTPS egress rule (port 443) to OpenSearchSecurityGroup
    - Both 443 (HTTPS) and 9200 (API) egress rules now exist for full compatibility
  - **Files Modified**: `deploy/cloudformation/security.yaml`
  - **Impact**: ECS Fargate tasks can now access OpenSearch via VPC endpoint

* **scripts:** Correct ECS cluster and VPC stack names in incident workflow deploy (Dec 7, 2025)
  - **Problem Solved**
    - Deployment script used incorrect stack names causing ClusterNotFoundException and VPC mismatch
    - ECS_CLUSTER referenced non-existent `aura-cluster-dev` instead of `aura-network-services-dev`
    - VPC_STACK referenced non-existent `aura-vpc-dev` instead of `aura-networking-dev`
  - **Solution**
    - Fixed line 102: Use `aura-network-services-dev` cluster (exists and active)
    - Fixed line 74: Use `aura-networking-dev` VPC stack (deployed in Foundation layer)
  - **Impact**: Enables correct configuration for ADR-025 RuntimeIncidentAgent deployment
  - **Related**: ADR-025 deployment session report in `docs/deployment-reports/`

* **cicd:** Implement "Bootstrap Once, Update Forever" pattern for security stack (Dec 7, 2025)
  - **Problem Solved**
    - Previous logic would blindly delete ROLLBACK_COMPLETE stacks, causing orphaned security groups
    - Security groups with ENI attachments (from EKS/Neptune/OpenSearch) cannot be deleted
    - Deletion attempts would hang indefinitely, leaving resources outside CloudFormation management
  - **Solution: ENI Dependency Check**
    - Before deleting ROLLBACK_COMPLETE stacks, check for attached ENIs
    - If ENIs exist: EXIT with actionable error message and recovery guidance
    - If no ENIs: Safe to delete and recreate (initial bootstrap scenario)
  - **State Machine Implementation** (`buildspec-foundation.yml`)
    - `DOES_NOT_EXIST` -> Create new stack
    - `*_COMPLETE` states -> Update via deploy command
    - `ROLLBACK_COMPLETE/ROLLBACK_FAILED` -> ENI check, then conditional delete
    - `*_IN_PROGRESS` states -> EXIT (wait for completion)
    - `DELETE_*` states -> EXIT (manual intervention required)
  - **Recovery Guidance**
    - Error messages include specific AWS CLI commands for diagnosis
    - References `./deploy/scripts/import-security-groups.sh` for orphaned SG recovery
    - Clear distinction between RECOMMENDED (import) and DESTRUCTIVE (delete services) options
  - **Architecture Decision Record**
    - `docs/architecture-decisions/ADR-026-bootstrap-once-update-forever.md`
  - **Impact**: Prevents orphaned security groups, maintains IaC principles, provides clear recovery path

### Security

* **network:** Implement CMMC L3 Compliant Security Group Reference Architecture (Dec 7, 2025)
  - **Problem Solved**
    - Eliminated CIDR-based VPC endpoint access rules (10.0.3.0/24, 10.0.4.0/24)
    - Replaced with identity-based security group references per Option C recommendation
    - Fixed cross-stack circular dependency issue between Foundation and Serverless layers
    - Removed manually-added CLI rule (aws ec2 authorize-security-group-ingress)
  - **Architecture Changes** (`deploy/cloudformation/security.yaml`)
    - Created centralized `ECSWorkloadSecurityGroup` for all ECS/Fargate tasks
    - Created `LambdaSecurityGroup` for VPC-attached Lambda functions
    - Updated `VPCEndpointSecurityGroup` to use SG references only (no CIDRs)
    - Added separate egress rules via `AWS::EC2::SecurityGroupEgress` resources
    - Added ingress rules for Neptune/OpenSearch from workload SGs
  - **Workload Stack Updates** (`deploy/cloudformation/incident-investigation-workflow.yaml`)
    - Removed local `ECSTaskSecurityGroup` resource (was causing circular dependency)
    - Updated Step Functions to import centralized SG via `!ImportValue`
    - Simplified template by delegating security to Foundation layer
  - **CMMC L3 Compliance Impact**
    - SC-7 (Boundary Protection): Identity-based network segmentation
    - SC-7(5) (Deny by Default): Sandbox SG explicitly excluded from VPC endpoints
    - AC-4 (Information Flow Enforcement): SG references enable audit trail
  - **Migration Tooling** (`deploy/scripts/migrate-sg-references.sh`)
    - Removes manually-added security group rules
    - Updates security stack with centralized workload SGs
    - Cleans up orphaned security groups
    - Supports `--dry-run` for preview
  - **Security Groups Exported** (for cross-stack import)
    - `${ProjectName}-ecs-workload-sg-${Environment}` - ECS/Fargate tasks
    - `${ProjectName}-lambda-sg-${Environment}` - Lambda functions

* **cloudformation:** Fix VPCEndpointSecurityGroup replacement issue (Dec 7, 2025)
  - **Root Cause**: Inline `SecurityGroupIngress` in VPCEndpointSecurityGroup triggered CloudFormation resource replacement. Since `GroupName: aura-vpce-sg-dev` already existed, CloudFormation could not create the replacement.
  - **Solution**: Refactored to use separate `AWS::EC2::SecurityGroupIngress` resources
    - `VPCEndpointIngressFromEKSNodes` - EKS node access to VPC endpoints
    - `VPCEndpointIngressFromECSWorkloads` - ECS/Fargate access to VPC endpoints
    - `VPCEndpointIngressFromLambda` - Lambda function access to VPC endpoints
  - **CloudFormation Best Practice**: Separate ingress/egress resources enable in-place updates without replacement, critical for security groups with external dependencies (VPC endpoints)
  - **Files Modified**: `deploy/cloudformation/security.yaml` (lines 227-299)

### Features

* **agents:** RuntimeIncidentAgent Architecture (ADR-025) - Code-Aware Incident Response (Dec 6, 2025)
  - **Architecture Decision Record**
    - `docs/architecture-decisions/ADR-025-runtime-incident-agent.md` - Comprehensive architecture (~800 lines)
    - Competitive response to AWS DevOps Agent (announced Dec 2025, public preview)
    - Strategic positioning: "AWS DevOps Agent for Code" with federal compliance
    - Unique differentiation: Code-aware RCA, Neptune graph correlation, OpenSearch semantic search, GovCloud availability
  - **Core Components**
    - RuntimeIncidentAgent class for autonomous incident investigation
    - Deployment correlation engine (DynamoDB table for ArgoCD sync events)
    - Investigation workflow (Step Functions orchestration with HITL approval)
    - Multi-vendor observability integration (CloudWatch, Datadog APM, Prometheus)
  - **Key Capabilities**
    - Maps runtime exceptions to Neptune code graph entities
    - Searches OpenSearch for recent code changes affecting incidents
    - Correlates incidents with deployment history (24-hour lookback)
    - Generates LLM-powered RCA hypotheses with confidence scores
    - Proposes mitigation plans with rollback strategies
  - **Database Schema**
    - `aura-deployments-{env}` - ArgoCD deployment event tracking
    - `aura-incident-investigations-{env}` - Investigation results with HITL status
    - GlobalSecondaryIndexes for by-application and by-hitl-status queries
    - TTL attributes (90 days dev, 365 days prod)
  - **Integration Points**
    - EventBridge rules for CloudWatch alarms, PagerDuty webhooks
    - MCP adapters for Datadog traces, Prometheus metrics
    - HITL Dashboard for investigation approval workflow
    - SNS notifications for critical incident alerts
  - **Implementation Status** (ALL 6 Phases Complete - Dec 6, 2025)
    - ✅ Phase 1: DynamoDB tables (`aura-deployments-dev`, `aura-incident-investigations-dev`), EventBridge bus, Lambda recorder, SNS topic - DEPLOYED
    - ✅ Phase 2: RuntimeIncidentAgent (1,100 lines), 31 unit tests (100% passing), Docker image built and pushed to ECR
    - ✅ Phase 3: Step Functions workflow (`aura-incident-investigation-dev`), ECS Fargate task definition, EventBridge rules - DEPLOYED
    - ✅ Phase 4: FastAPI endpoints (5 REST APIs), React UI (`IncidentInvestigations.jsx` with approval workflow)
    - ✅ Phase 5: Observability MCP adapters (Datadog APM traces, Prometheus metrics, CloudWatch integration)
    - ✅ Phase 6: E2E validation, VPC endpoint connectivity fix, the architectural analysis (ECS Fargate > EKS recommendation)
  - **Success Metrics**
    - Mean Time to Investigation (MTTI) <5 minutes
    - RCA Confidence Score >70% average
    - Code Correlation Rate >60%
    - Deployment Correlation Rate >40%
    - HITL Approval Rate >80%
  - **Strategic Advantage**
    - No AWS DevOps Agent competition in GovCloud (federal/defense market)
    - Complements proactive security with reactive operations
    - Full DevSecOps automation: Code → Deploy → Operate

* **compliance:** Compliance-Aware Security Scanning with Profile System (Dec 6, 2025)
  - **Compliance Profiles Module**
    - `src/services/compliance_profiles.py` - 6 predefined compliance profiles (~630 lines)
    - Profiles: CMMC L3, CMMC L2, SOX, PCI-DSS, NIST 800-53, DEVELOPMENT
    - Risk-based scanning policies (what files to scan, when to block deployments)
    - Review policies (manual HITL requirements, minimum reviewers, security approvals)
    - Audit policies (log retention, compliance control mappings)
    - Makes Aura the first autonomous security platform with compliance intelligence
  - **Configuration Management**
    - `src/services/compliance_config.py` - YAML-based configuration loader (~315 lines)
    - `.aura/config.yml` - Active configuration (CMMC Level 3 default)
    - `.aura/config.example.yml` - Example configuration with all options
    - Custom override support for profile customization
    - SSM Parameter Store integration for centralized config management
  - **Security Service Integration**
    - `src/services/compliance_security_service.py` - Compliance-aware scanning (~580 lines)
    - File filtering based on profile (scanning policies applied)
    - Deployment blocking decisions (CRITICAL/HIGH severity thresholds)
    - Manual review requirements (IAM policies, network configs, encryption keys)
    - Scan result formatting with compliance metadata
  - **Audit Trail Service**
    - `src/services/compliance_audit_service.py` - Tamper-evident audit logging (~540 lines)
    - 12 audit event types: SCAN_INITIATED, DEPLOYMENT_BLOCKED, MANUAL_REVIEW_REQUIRED, etc.
    - CloudWatch Logs integration (real-time monitoring)
    - DynamoDB integration (long-term retention, queryable)
    - CMMC/SOX/NIST control mappings in every audit event
    - Compliance report generation for auditors
  - **GitHub Actions Optimization**
    - Workflow concurrency limits (cancel in-progress runs when new commits pushed)
    - Consolidated dependency caching (setup job + shared cache)
    - Smart test selection (pytest --lf --ff --maxfail=5)
    - Estimated savings: 30-40% reduction in CI/CD minutes
  - **Documentation**
    - `docs/COMPLIANCE_PROFILES.md` - Comprehensive guide (~760 lines)
    - Profile comparison tables, usage examples, architecture diagrams
    - With/without comparison scenarios, troubleshooting, FAQ
  - **Benefits:** Addresses GitHub Actions billing concerns while maintaining CMMC Level 3 compliance - scans everything in production, optimizes dev environments, provides defensible audit trail

* **security:** Advanced Security Features - Threat Intelligence Integration Complete (Dec 6, 2025)
  - **SBOM Auto-Detection Service**
    - `src/services/sbom_detection_service.py` - Multi-ecosystem dependency scanning (~800 lines)
    - Supports: Python (requirements.txt, pyproject.toml), Node.js (package.json), Go (go.mod), Rust (Cargo.toml), Ruby (Gemfile), .NET (*.csproj)
    - Production vs dev dependency separation, deduplication, error tracking
    - Integration: `ThreatIntelligenceAgent.auto_detect_sbom()` method
    - 30 tests, 87% code coverage
  - **Multi-Ecosystem GitHub Advisory Support**
    - Expands `_fetch_github_advisories()` to query all detected ecosystems
    - Supported ecosystems: pip, npm, go, cargo, rubygems, nuget
    - Ecosystem-specific dependency matching
    - 12 new tests for multi-ecosystem functionality
  - **Real-Time GuardDuty Correlation**
    - `gather_intelligence_with_correlation()` - Enhanced intelligence gathering
    - Correlation algorithm with 4 scoring factors: time proximity (±6-24h), severity alignment, attack pattern matching (5 categories), component overlap
    - Human-readable correlation explanations
    - `get_correlated_threats_summary()` for statistics
    - 12 new tests for correlation functionality
  - **AdaptiveIntelligenceAgent Tests**
    - `tests/test_adaptive_intelligence_agent.py` - 62 comprehensive tests
    - Covers: recommendation generation, risk scoring, compliance assessment, LLM integration
  - Total: 182 new tests for security features

* **memory:** Titan neural memory architecture (ADR-024) - All 5 Phases complete (Dec 6, 2025)
  - **Phase 1-2: Core Implementation**
    - `src/services/models/deep_mlp_memory.py` - DeepMLPMemory with 3-layer MLP, persistent memory (~440 lines)
    - `src/services/models/miras_config.py` - MIRAS framework with configurable loss functions (~460 lines)
    - `src/services/titan_memory_service.py` - Main orchestrator with TTT & surprise (~870 lines)
    - Surprise-driven selective memorization (gradient magnitude metric)
    - Test-time training with configurable learning rates and bounds
    - MIRAS presets: `defense_contractor`, `enterprise_standard`, `research_lab`, `development`
  - **Phase 3: GPU Benchmarking**
    - `src/services/memory_backends/gpu_backend.py` - CUDA/MPS auto-detection backend (~400 lines)
    - `src/services/memory_backends/benchmark.py` - Comprehensive benchmarking module (~560 lines)
    - CPU vs MPS performance comparison on Apple Silicon
    - Results: MPS 1.7-2.0x faster for batched inference (batch≥8), CPU faster for backward pass
    - `research/experiments/hybrid-memory-architecture/BENCHMARK_RESULTS.md`
  - **Phase 4: Service Integration**
    - `src/services/titan_cognitive_integration.py` - Full integration (~1,220 lines)
    - `MemoryAgent` class with surprise → confidence routing
    - Confidence thresholds: ≥0.85 autonomous, ≥0.70 logging, ≥0.50 review, <0.50 escalate
    - `NeuralMemoryMetricsPublisher` for CloudWatch (`Aura/NeuralMemory` namespace)
    - Metrics: SurpriseScore, RetrievalLatency, TTTSteps, ConfidenceScore, EscalationCount
    - Dual/Auto/Single mode critic engagement for high-risk domains
  - **Phase 5: Production Hardening** (NEW)
    - `src/services/memory_consolidation.py` - Memory size limits & consolidation manager (~580 lines)
    - `src/services/neural_memory_audit.py` - Compliance-ready audit logging (~760 lines)
    - Consolidation strategies: FULL_RESET, WEIGHT_PRUNING, SLOT_REDUCTION, LAYER_RESET, WARN_ONLY
    - `MemoryPressureLevel` enum with NORMAL/WARNING/HIGH/CRITICAL levels
    - `AuditRecord` with checksum for integrity verification
    - InMemoryAuditStorage and FileAuditStorage backends
    - Correlation IDs for request tracking
    - Auto-consolidation on high memory pressure with callbacks
    - 40 production hardening tests (all passing)
  - **Architecture Clarification:** Strategy dataclass defines approach (strategy_type, guardrails, logging_level), while ConfidenceEstimate tracks confidence separately - both returned in cognitive context
  - 225 unit tests for neural memory modules (PyTorch 2.5.1 required)
  - Refs: arXiv:2501.00663 (Titans), arXiv:2504.13173 (MIRAS)
* **auth:** GitHub App authentication for private repository access (Dec 6, 2025)
  - `src/services/github_app_auth.py` - JWT-based authentication service (~242 lines)
  - SSM Parameter Store integration for secure credential storage
  - Installation token caching with automatic refresh (5-minute buffer)
  - Git Ingestion Service now uses GitHub App tokens for private repos
  - IAM policy updated with SSM permissions for GitHub App parameters
  - E2E tested: Successfully ingested 136 files, 9,389 entities from private repo
  - 12 unit tests for GitHub App auth (all passing)
* **data:** Neptune Graph Ingestion pipeline verified operational (Dec 6, 2025)
  - `src/services/neptune_graph_service.py` - Gremlin client with mock/AWS modes (~725 lines)
  - `src/services/git_ingestion_service.py` - Complete ingestion workflow (~874 lines)
  - `src/agents/ast_parser_agent.py` - Python AST and JS/TS regex parsing (~555 lines)
  - REST API endpoints: `/api/v1/ingest`, `/api/v1/jobs/{id}`, `/webhook/github`
  - Full workflow: Git clone → AST parsing → Neptune graph → OpenSearch embeddings
  - GitHub webhooks for incremental updates on push events
  - 86 tests passing (24 git ingestion + 28 AST parser + 34 Neptune service)
  - API endpoints verified in EKS cluster via ArgoCD deployment
* **agents:** Context Retrieval agents wired to Bedrock LLM (Dec 6, 2025)
  - Fixed gap: `ResultSynthesisAgent` and `FilesystemNavigatorAgent` now receive LLM client
  - `ContextRetrievalService.__init__` passes LLM to all agents
  - Added `create_context_retrieval_service()` factory function for production use
  - Verified with real Bedrock: QueryPlanningAgent generates 6 search strategies via Claude 3.5 Sonnet
  - Cost tracking: ~$0.006 per query planning request
  - 19 agentic search integration tests passing
* **security:** DNS threat intelligence and automated blocklists (Dec 5-6, 2025)
  - `src/services/dns_blocklist_service.py` - Multi-source threat aggregation (~900 lines)
  - `src/lambda/dns_blocklist_updater.py` - Automated Lambda for daily updates (~430 lines)
  - `deploy/scripts/update-dnsmasq-blocklist.sh` - Manual update script
  - `deploy/kubernetes/dnsmasq-blocklist-sync.yaml` - K8s CronJob for ConfigMap sync
  - `deploy/cloudformation/dns-blocklist-lambda.yaml` - Lambda + S3 bucket + IRSA role
  - Threat intelligence sources: NVD CVE API, CISA KEV, GitHub Advisories, URLhaus, Abuse.ch Feodo
  - Categories: malware, phishing, C2 command-and-control, cryptominer, ransomware, botnet
  - Features: whitelist support, severity filtering, deduplication, dnsmasq config generation
  - Documentation: `docs/DNS_THREAT_INTELLIGENCE.md`
  - 25 unit tests (all passing)
  - **Pipeline Operational** (Dec 6, 2025):
    - IRSA role `aura-blocklist-sync-role-dev` deployed via CloudFormation
    - K8s CronJob using `alpine/k8s:1.28.4` image (aws-cli + kubectl)
    - S3 → ConfigMap sync verified: 14 blocked domains synced
    - Lambda → S3 → K8s CronJob → ConfigMap → dnsmasq pipeline fully operational
    - Daily schedule: Lambda (6 AM UTC) → CronJob (7 AM UTC)
* **security:** SecurityTelemetryService for real AWS security integration (Dec 6, 2025)
  - `src/services/security_telemetry_service.py` - Queries GuardDuty, WAF, CloudTrail (~750 lines)
  - Real-time security findings from AWS security services
  - FindingType: GUARDDUTY, WAF_EVENT, CLOUDTRAIL_ANOMALY, VPC_FLOW_ANOMALY
  - Severity mapping aligned with CVSS scores
  - Integrated with ThreatIntelligenceAgent for internal telemetry analysis
  - Mock mode for testing, AWS mode for production
  - 29 unit tests (all passing)
* **monitoring:** Real-time monitoring pipeline fully operational (Dec 5, 2025)
  - Canary rollout completed: aura-api at 100% via Argo Rollouts (9/9 steps)
  - E2E test suite validated: 15/15 tests passing (API, CloudWatch, EventBridge, DynamoDB)
  - EventBridge rules verified: critical-anomaly, hitl-approval, security-logging, orchestrator-logging
  - CloudWatch alarms created: `aura-high-severity-security-events-dev`, `aura-detection-spike-dev`
  - SNS email subscription confirmed for `aura-critical-anomalies-dev` topic
  - kubectl argo-rollouts plugin installed for canary promotion management

### Tests

* **services:** Comprehensive test coverage for core data services (Dec 6, 2025)
  - `tests/test_neptune_graph_service.py` - 83 tests, **100% coverage** (↑ from 36%)
    - Added AWS mode tests with mocked Gremlin client
    - Delete operations (entity, relationship, subgraph)
    - Gremlin string escaping, factory function, edge cases
    - Import fallback tests for Gremlin unavailability
  - `tests/test_opensearch_vector_service.py` - 68 tests, **100% coverage** (new file, ↑ from 12%)
    - Mock mode and AWS mode with mocked OpenSearch client
    - Vector similarity search, bulk indexing, delete operations
    - Query caching, cache statistics, edge cases
    - Import fallback tests, IAM auth initialization
  - `tests/test_titan_embedding_service.py` - 58 tests, **100% coverage** (new file, ↑ from 16%)
    - Mock embeddings, AWS mode with Bedrock mocking
    - Budget tracking, rate limiting, error handling
    - Batch embedding, retry logic, fallback behavior
    - Factory function tests for all environments
  - Total: 209 tests for core services, overall test count: 1,217 → 1,483
  - Coverage exclusions configured in pyproject.toml for `__main__` blocks and import fallbacks
* **lambda:** Approval Callback Handler tests (Dec 6, 2025)
  - `tests/test_lambda_approval_callback.py` - 42 tests, **100% coverage** (new file, ↑ from 0%)
    - API Gateway routing (approve, reject, register-token endpoints)
    - Step Functions task token registration and callbacks
    - DynamoDB operations for workflow and approval tables
    - SNS notification handling with error resilience
    - Task token expiration and error handling
  - Coverage threshold raised: 50% → 70% (fail_under in pyproject.toml)
  - Total test count: 1,483 → 1,525, overall coverage: 70.70% → 71.60%
* **e2e:** AWS service connectivity E2E tests verified (Dec 6, 2025)
  - Bedrock LLM E2E: 4/4 tests PASSED (connection health, generation, code analysis, cost tracking)
  - Real Claude 3.5 Sonnet API calls verified with cost tracking ($0.006/request)
  - Neptune/OpenSearch tests correctly auto-skip when run outside VPC (by design)
  - Full test suite: `RUN_AWS_E2E_TESTS=1 pytest tests/test_aws_services_e2e.py`
  - To run VPC-dependent tests: execute from EKS pod with IRSA roles
* **network:** dnsmasq Tier 2 VPC-wide DNS service with DNSSEC deployed (Dec 6, 2025)
  - `deploy/cloudformation/network-services.yaml` - ECS Fargate with NLB
  - 2-task ECS service with UDP load balancing on port 53
  - DNS forwarding to Cloudflare (1.1.1.1) and Google (8.8.8.8)
  - Rate limiting: `--dns-forward-max=150`, `--neg-ttl=300`, `--local-ttl=300`
  - **DNSSEC validation enabled** with IANA root trust anchor (v1.1.0 image)
  - Private ECR image: `aura-dnsmasq:v1.1.0` (ADR-020 controlled supply chain)
  - Trust anchor: Root zone KSK (Key Tag 20326, Algorithm 8, SHA-256)
  - CloudWatch logging: `/aws/ecs/aura-network-services-dev`
  - Process-based health check (`pgrep dnsmasq`)
  - bind-tools included for DNS health checks (dig/nslookup)
  - **Deployed to dev**: `aura-network-services-dev` stack UPDATE_COMPLETE
* **monitoring:** Real-Time Anomaly Detection Integration
  - `src/services/cloudwatch_metrics_publisher.py` - CloudWatch metrics for anomalies (~700 lines)
  - `src/services/eventbridge_publisher.py` - EventBridge event routing (~580 lines)
  - `src/services/anomaly_persistence_service.py` - DynamoDB audit trail (~700 lines)
  - `src/services/realtime_monitoring_integration.py` - Central orchestration hub (~700 lines)
  - CloudWatch namespaces: Aura/Anomalies, Aura/Security, Aura/Orchestrator, Aura/HITL
  - EventBridge event types: anomaly.detected, security.cve_detected, orchestrator.task_*, hitl.approval_*
  - DynamoDB table with GSIs: status-created_at, severity-created_at, dedup_key
  - 37 unit tests (all passing)
* **cloudformation:** Real-time monitoring infrastructure
  - `deploy/cloudformation/realtime-monitoring.yaml` - EventBridge rules, SNS topics, CloudWatch alarms
  - Custom event bus: `aura-anomaly-events-{env}`
  - SNS topics: critical-anomalies, hitl-approvals with EventBridge integration
  - CloudWatch alarms: critical-anomaly-rate, orchestrator-failures, hitl-timeout
  - CloudWatch dashboard: `aura-anomaly-monitoring-{env}` with severity/type charts
  - Log groups for security events and orchestrator events
  - **Deployed to dev** (Dec 5, 2025): `aura-realtime-monitoring-dev` stack CREATE_COMPLETE
* **cicd:** Observability layer buildspec updated for real-time monitoring deployment
  - `buildspec-observability.yml` now deploys `realtime-monitoring.yaml`
  - CodeBuild IAM role updated: CloudFormation stack permissions, EventBridge event bus, log groups
* **dynamodb:** Anomalies audit trail table
  - `aura-anomalies-{env}` table with TTL (90 days default)
  - GSIs for status, severity, and deduplication queries
  - DynamoDB Streams enabled for event-driven processing
  - **Deployed to dev** (Dec 5, 2025): `aura-anomalies-dev` table ACTIVE
* **testing:** E2E integration test suite for real AWS services
  - `tests/test_aws_services_e2e.py` - 15 tests covering Neptune, OpenSearch, Bedrock, full pipeline
  - Neptune tests: entity CRUD, relationships, bulk ingestion, graph traversals
  - OpenSearch tests: vector indexing, semantic similarity, bulk indexing
  - Bedrock tests: text generation, code analysis, cost tracking
  - Full pipeline test: ingest → query → generate workflow
  - Environment flag: `RUN_AWS_E2E_TESTS=1` required to run
  - Socket-based connectivity checks with 5s timeout for VPC services
* **persistence:** Settings persistence to DynamoDB
  - `src/services/settings_persistence_service.py` - DynamoDB persistence layer (~740 lines)
  - `aura-platform-settings-dev` DynamoDB table deployed via CodeBuild
  - In-memory caching with TTL, fallback mode, audit logging
  - Settings endpoints (`settings_endpoints.py`) now wire to persistence service
  - 35 unit tests, 34 endpoint tests updated for async persistence
* **anomaly:** Real-time anomaly detection service
  - `src/services/anomaly_detection_service.py` - Statistical baselines, Z-score detection (~1,000 lines)
  - Security event processing with MetaOrchestrator integration
  - External notification routing (Slack/Jira/PagerDuty) with deduplication
  - Background monitoring with configurable intervals
  - 44 unit tests (all passing)
* **api:** Anomaly detection triggers integrated with API events
  - `src/api/anomaly_triggers.py` - API event integration with anomaly detection (~600 lines)
  - HITL metrics: approval rate, time-to-approve, critical rejection alerts
  - Webhook metrics: success rate, event volume, signature validation failures
  - API metrics: latency, error rates, request counts
  - Critical patch rejections trigger security events
  - Signature validation failures trigger HIGH severity alerts
  - Wired to `main.py` lifespan for automatic initialization
  - 21 unit tests (all passing)
* **integration:** External tool connectors for Slack, Jira, PagerDuty
  - `src/services/external_tool_connectors.py` - Async connectors with mode-awareness (~1,200 lines)
  - Mode-aware decorators (`@require_enterprise_mode`) block external calls in DEFENSE mode
  - Security incident workflows: escalate → create issue → trigger alert
  - 40 integration tests (all passing)
* **frontend:** Settings page with Integration Mode configuration UI
  - `SettingsPage.jsx` - Tabbed settings interface (Integration Mode, HITL, MCP, Security)
  - Defense/Enterprise/Hybrid mode selector with feature descriptions and compliance badges
  - HITL settings: approval requirements, timeout configuration, notification preferences
  - MCP settings: gateway connection, budget controls, external tool toggles
  - Security overview: compliance status (CMMC, NIST, FedRAMP), sandbox isolation levels
  - `settingsApi.js` - Frontend API service with fallback defaults for development
  - `settings_endpoints.py` - Backend REST API at `/api/v1/settings/*`
* **architecture:** AgentCore Gateway Integration for Dual-Track Architecture (ADR-023)
  - Defense Track: No external dependencies, GovCloud-ready, air-gap compatible
  - Enterprise Track: AgentCore Gateway enabled, MCP protocol, external tool integrations
  - Phase 1: `IntegrationMode` enum (DEFENSE, ENTERPRISE, HYBRID), `CustomerMCPBudget`, mode decorators
  - Phase 2: MCP Adapter Layer with `MCPGatewayClient`, `AuraToolAdapter`, `ExternalToolRegistry`
  - 6 Aura agents exposed as MCP tools: security_scanner, code_reviewer, patch_generator, architecture_analyzer, threat_intelligence, documentation_generator
  - External tools: Slack, Jira, PagerDuty, GitHub, Datadog via AgentCore Gateway
  - Unified registry with semantic search, capability-based tool selection, batch invocation
  - 100 unit tests across integration_config and mcp_adapter_layer modules
* **gitops:** ArgoCD v2.13.2 deployed to EKS cluster
  - GitHub App authentication (enterprise-grade, organization-managed)
  - Applications syncing: `aura-frontend`, `aura-api` both Healthy
  - Auto-sync with self-healing and prune enabled
  - Retry configuration for resilient deployments
* **gitops:** Argo Rollouts v1.8.3 for progressive delivery (ADR-022 Phase 3)
  - Canary deployment strategy: 10% → 25% → 50% → 100%
  - ClusterAnalysisTemplates: pod-health, http-benchmark, success-rate, latency-check
  - Automated rollback on analysis failure
  - Both `aura-frontend` and `aura-api` converted from Deployment to Rollout
* **cicd:** Frontend CodeBuild pipeline with private ECR base images
  - `deploy/buildspecs/buildspec-service-frontend.yml` - CI pipeline
  - `deploy/cloudformation/codebuild-frontend.yaml` - CodeBuild project with EKS access
  - `deploy/scripts/deploy-frontend-codebuild.sh` - Bootstrap script
* **ecr:** Private base images for controlled supply chain (ADR-020)
  - node:20-alpine, nginx:1.25-alpine bootstrapped to private ECR
  - `deploy/scripts/bootstrap-base-images.sh` - AMD64 platform for EKS/CodeBuild
  - Dockerfile ARG pattern for build-time image selection
* **architecture:** GitOps for Kubernetes Deployment with ArgoCD (ADR-022)
  - Separates CI (CodeBuild: build/test/push) from CD (ArgoCD: deploy/sync/rollback)
  - Git becomes single source of truth for Kubernetes state
  - Progressive delivery via Argo Rollouts (canary deployments for AI workloads)
  - Strengthens CMMC Level 3 compliance (AU/CM/SI domains)
* **frontend:** Add Dockerfile and Kubernetes manifests for EKS deployment
  - `deploy/docker/frontend/Dockerfile.frontend` - Multi-stage build (Node + nginx)
  - `deploy/kubernetes/aura-frontend/` - Deployment, Service, Kustomization
  - nginx config with API proxy to `aura-api.default.svc.cluster.local`
* **cicd:** Add ECR frontend repository CloudFormation template (`ecr-frontend.yaml`)
* **frontend:** Add Vite 6 build system for Approval Dashboard
  - React 18.3, Tailwind CSS, React Router 7
  - ApprovalDashboard wired to `/api/v1/approvals/*` API endpoints
  - Vite dev proxy for local development (`/api` → localhost:8000)
  - Environment configuration via `VITE_API_URL`, `VITE_REVIEWER_EMAIL`
* **frontend:** Upgrade all dependencies to latest versions
  - ESLint 9.16 with flat config (eliminates deprecated packages)
  - 0 deprecation warnings, 0 vulnerabilities
* **hitl:** Wire NotificationService to approval workflow endpoints
  - `approve_request()` and `reject_request()` now trigger SNS email notifications
  - Auto-detects AWS/MOCK mode based on `HITL_SNS_TOPIC_ARN` environment variable
  - Graceful degradation (notification failures don't block approval actions)
* **hitl:** Add hitl-callback Lambda CloudFormation template
  - Step Functions task callback integration for async approval workflow
  - Lambda Function URL with AWS_IAM authentication
  - IAM role with DynamoDB, Step Functions, SNS permissions
  - Deployed via serverless CodeBuild layer
* **hitl:** Update API ConfigMap with HITL environment variables
  - `HITL_SNS_TOPIC_ARN`, `HITL_DASHBOARD_URL` for notification routing
  - `APPROVAL_TABLE_NAME`, `WORKFLOW_TABLE_NAME` for DynamoDB tables
* **agents:** Guardrails Cognitive Architecture for institutional memory (ADR-021)
  - Neuroscience-informed design (working memory, schema activation, metacognition)
  - Three-tier architecture: Static Guardrails → Dynamic Context → Learning Loop
  - Domain-tagged retrieval for efficient context loading
* **agents:** Configurable Dual-Agent Architecture for confidence calibration
  - `AgentMode` enum: SINGLE (fast), DUAL (thorough), AUTO (risk-based selection)
  - MemoryAgent + CriticAgent debate architecture prevents overconfidence
  - AUTO mode uses risk indicators (production, security, compliance, etc.) for selection
  - Key finding: Cold-start parity - dual-agent provides insurance, not dramatic improvement
* **cicd:** ECR API repository CloudFormation template (`ecr-api.yaml`)
  - Integrates `aura-api-dev` ECR into managed infrastructure

### Bug Fixes

* **memory:** Comprehensive error handling for memory services (Dec 6, 2025)
  - `cognitive_memory_service.py`: ConsolidationPipeline async error handling with partial results
  - `cognitive_memory_service.py`: PatternCompletionRetriever graceful degradation per stage
  - `titan_memory_service.py`: TTT training loop NaN/Inf detection with model state backup/restore
  - `memory_consolidation.py`: Callback protection with separate try-except
  - `cognitive_memory_service.py`: Content size limits in `_create_semantic_memory()` (4000 char max)
  - `cognitive_memory_service.py`: Token-based WorkingMemory capacity (8000 token budget)
  - Audit: `docs/ERROR_HANDLING_AUDIT.md` documents all 6 issues and fixes
* **api:** Connect Approval Dashboard to live API (Dec 6, 2025)
  - Add `get_all_requests()` method to HITLApprovalService for listing all approvals
  - Fix nginx.conf port mismatch (8000 → 8080) for K8s service discovery
  - Remove errant await calls from sync service methods in approval_endpoints.py
  - All 17 approval endpoint tests passing
* **bedrock:** Fix `_load_secrets()` to set model IDs when secrets not found
  - Previously caused `AttributeError: 'BedrockLLMService' object has no attribute 'model_id_primary'`
  - Now falls back to config defaults when Secrets Manager secret doesn't exist
* **config:** Update dev Bedrock config to use on-demand compatible model
  - Changed from `anthropic.claude-sonnet-4-5-20250929-v1:0` (requires inference profile)
  - To `anthropic.claude-3-5-sonnet-20240620-v1:0` (on-demand available)
* **cicd:** Use explicit kubectl version in buildspec-application.yml
  - Prevents transient network failures when fetching dynamic version from k8s.io
* **async:** Fix unawaited coroutine warnings in Lambda handlers (Dec 6, 2025)
  - Replaced deprecated `asyncio.get_event_loop().run_until_complete()` with `asyncio.run()`
  - Updated `dns_blocklist_updater.py` and `threat_intelligence_processor.py`
  - Fixed test mocks to use `AsyncMock` instead of patching `asyncio.get_event_loop()`
  - All 30 Lambda tests passing with no warnings

### Refactors

* **cicd:** Standardized buildspec-application.yml to use `aws cloudformation deploy` pattern
  - Aligns with established patterns in buildspec-data.yml, buildspec-foundation.yml
  - Uses `--no-fail-on-empty-changeset` for idempotent deployments

### Documentation

* **runbook:** E2E Testing Runbook (`docs/E2E_TESTING_RUNBOOK.md`)
  - 4 environment options: EKS pod, CodeBuild, VPN, Bedrock-only
  - Service endpoints and authentication requirements
  - Troubleshooting guide for common issues
  - Cost estimates per test run
* **runbook:** ArgoCD Runbook (`docs/ARGOCD_RUNBOOK.md`)
  - Quick reference for common ArgoCD operations
  - Manual sync, rollback procedures, troubleshooting guide
  - GitHub App authentication and RBAC configuration
  - Monitoring and health check commands
* **adr:** ADR-022 GitOps for Kubernetes Deployment with ArgoCD
  - Documents enterprise-scale deployment architecture decision
  - Migration path from embedded kubectl to ArgoCD
  - CMMC Level 3 compliance impact analysis
  - Alternatives considered: CodeDeploy, Flux, Spinnaker
* **guardrails:** Created GUARDRAILS.md with 5 initial entries
  - GR-CICD-001: CodeBuild Buildspec Pattern Compliance
  - GR-IAM-001: No Wildcard Resources
  - GR-CFN-001: GovCloud ARN Partitions
  - GR-CFN-002: CloudFormation Description Standards
  - GR-SEC-001: SSM Parameter Store for Configuration
* **adr:** ADR-021 Guardrails Cognitive Architecture
  - Documents neuroscience-informed approach to agent learning
  - Defines three-phase implementation plan
* **schemas:** Created CI/CD task schema (`agent-config/schemas/cicd-schema.md`)
  - Pre-task checklist for pattern discovery
  - Implementation patterns with code examples
  - Anti-patterns and verification steps
* **runbook:** Prerequisites Runbook (`docs/PREREQUISITES_RUNBOOK.md`)
  - Documents one-time environment setup (SSM parameters, GitHub CodeConnection)
  - Clarifies three-phase deployment model (Prerequisites → Bootstrap → CI/CD)
* **standards:** Added Pattern Compliance section to CLAUDE.md
  - Enforces checking existing codebase patterns before implementing new approaches

### Tests

* **agents:** 15 dual-agent architecture tests (critic challenges, calibration, strategy adjustment)
* **bedrock:** 4 real LLM integration tests with Claude 3.5 Sonnet (MODERATE/HIGH/EXTREME complexity)
* **comparison:** Single vs dual-agent comparison test validating cold-start parity

---
