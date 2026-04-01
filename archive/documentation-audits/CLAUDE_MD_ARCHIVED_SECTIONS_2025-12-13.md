# CLAUDE.md Archived Sections

**Archived:** 2025-12-13
**Reason:** Reduce CLAUDE.md size for token efficiency; content available in dedicated docs

---

## Security Services Deployed (Dec 12, 2025)

> **Now referenced via:** `docs/SECURITY_SERVICES_OVERVIEW.md`

- Input Validation Service (`src/services/input_validation_service.py`) - SQL injection, XSS, command injection, SSRF, prompt injection detection (76 tests)
- Secrets Detection Service (`src/services/secrets_detection_service.py`) - 30+ secret types, entropy-based detection (66 tests)
- Security Audit Service (`src/services/security_audit_service.py`) - Event logging, CloudWatch/DynamoDB persistence (76 tests)
- Security Alerts Service (`src/services/security_alerts_service.py`) - P1-P5 priority alerts, HITL integration, SNS notifications (29 tests)
- API Security Integration (`src/api/security_integration.py`) - FastAPI decorators, middleware, rate limiting (39 tests)

### Security Infrastructure (CloudFormation)

- Security EventBridge Bus: `aura-security-events-dev`
- Security SNS Topic: `aura-security-alerts-dev`
- 3 CloudWatch Log Groups (90-day retention): security-audit, security-events, security-threats
- 7 CloudWatch Security Alarms: injection-attempts, secrets-exposure, prompt-injection, rate-limit-exceeded, high-severity-security-events, llm-security-misuse, security-build-failures
- 2 EventBridge Rules: security-alert-rule, security-audit-logging

### Security Documentation

- `docs/SECURITY_INCIDENT_RESPONSE.md` - Incident response runbook
- `docs/DEVELOPER_SECURITY_GUIDELINES.md` - Developer best practices
- `docs/SECURITY_SERVICES_OVERVIEW.md` - Architecture and CMMC/SOC2/NIST 800-53 compliance mapping

### Infrastructure Controls Implemented

- No IAM wildcard resources (`Resource: '*'` eliminated in 8 policies)
- CloudFormation role uses least privilege (AdministratorAccess removed)
- Neptune encrypted with customer-managed KMS keys (rotation enabled)
- VPC Flow Logs retained for 365 days (production) / 90 days (dev)
- AWS WAF deployed with 6 security rules (SQL injection, XSS, DDoS protection)
- All ARNs support GovCloud partition auto-detection
- All CloudFormation templates pass cfn-lint validation

---

## AWS GovCloud Migration Strategy

> **Now referenced via:** `docs/GOVCLOUD_MIGRATION_SUMMARY.md`

**Key Constraint:** EKS on Fargate NOT available in GovCloud → Use EC2 Managed Node Groups

**OS Strategy:**
- **Dev/QA:** AL2023_x86_64_STANDARD (easier debugging)
- **Production:** Bottlerocket (CMMC Level 3, FIPS 140-2 compliant)

**Timeline:** Commercial Cloud (now) → GovCloud migration Q2-Q3 2026

**GovCloud Requirements:**
- DISA STIG hardening required
- FIPS 140-2 mode required
- EKS endpoint: Private only
- Node access: SSM Session Manager only

---

## AWS Infrastructure Status (Updated Nov 26, 2025)

> **Now referenced via:** `PROJECT_STATUS.md`

Project Aura deploys infrastructure in phases to AWS Commercial Cloud (dev/qa) before migrating to AWS GovCloud (US) for production.

**Deployed Infrastructure:**

- **Phase 1 (Foundation):** VPC (vpc-0123456789abcdef0), 9 VPC Endpoints, 6 Security Groups, AWS WAF, 7 IAM Roles
- **Phase 2 (Data):** Neptune (db.t3.medium), OpenSearch (t3.small.search), DynamoDB, S3
- **Phase 3 (Compute):** EKS cluster (aura-cluster-dev) with 2 t3.medium EC2 nodes, OIDC provider for IRSA

**Architecture Decisions:**

- EKS uses EC2 managed node groups (not Fargate) for GovCloud compatibility
- ECS on Fargate hosts dnsmasq DNS service (GovCloud-compatible)
- All deployments use CodeBuild CI/CD with layer-specific IAM permissions
- 25 CloudFormation templates in `deploy/cloudformation/`

---

## dnsmasq Network Services

> **Now referenced via:** `docs/DNSMASQ_INTEGRATION.md`

- **Tier 1:** Kubernetes DaemonSet on EKS with EC2 nodes (local DNS caching per node)
- **Tier 2:** ECS on Fargate VPC-wide service (centralized DNS for entire VPC) - GovCloud compatible
- **Tier 3:** Sandbox Network Orchestrator (ephemeral DNS per sandbox)
- **Performance:** 67% faster DNS resolution, 5x cache capacity, 40% cost reduction
- **Security:** NetworkPolicy isolation, DNSSEC validation, metadata service blocking
- **GovCloud Note:** Tier 1 runs on EKS EC2 nodes (not Fargate), Tier 2 uses ECS+Fargate (supported in GovCloud)

---

## Monitoring & Observability (Deployed)

> **Now referenced via:** `docs/OBSERVABILITY_GUIDE.md` (if exists) or `PROJECT_STATUS.md`

- **Secrets Manager:** Bedrock, Neptune, OpenSearch, API keys, JWT secrets (`aura-secrets-dev`)
- **CloudWatch:** Dashboards, alarms, metric filters (`aura-monitoring-dev`)
- **Container Insights:** Full EKS observability via `amazon-cloudwatch-observability` addon
  - CloudWatch agent DaemonSet for node/pod metrics (CPU, memory, network, disk)
  - Fluent Bit DaemonSet for container log shipping
  - EKS CPU alarm active (`aura-eks-high-cpu-dev`)
- **AWS Budgets:** Daily ($15) and monthly ($400) cost alerts (`aura-cost-alerts-dev`)
- **Prometheus:** Metrics collection (dnsmasq exporter ready)
- **SNS:** Email notifications for cost and security alerts
- **Audit Logging:** All HITL approvals, agent actions, security events

---

## Why Integration Tests Use Mocks

> **Now referenced via:** `docs/TESTING_STRATEGY.md`

Integration tests mock external services (Bedrock, Neptune, EKS) because:
- **Cost:** Real LLM/database calls cost $5-10 per test run
- **Determinism:** Mocks eliminate network latency and rate limits
- **Edge cases:** Mocks simulate failures that are hard to reproduce

Unit tests provide 80%+ coverage. Integration tests validate **workflow correctness** between components.

---

## Common Pitfalls & Best Practices

> **Now referenced via:** `docs/DEVELOPER_SECURITY_GUIDELINES.md` (security), `docs/CICD_SETUP_GUIDE.md` (config/secrets)

### Security

- Don't: Use MD5/SHA1 for password hashing → Use: Argon2id or bcrypt
- Don't: Trust user input without validation → Validate: All inputs at entry points
- Don't: Allow user-controlled system prompts → Sanitize: LLM inputs, use templates
- Don't: Use `subprocess.call(user_input, shell=True)` → Use: `shlex.quote()`, `shell=False`

### Configuration & Secrets Management

**CRITICAL: Never hardcode sensitive or environment-specific values**

- Don't: Hardcode AWS account IDs, role ARNs, or resource names
- Don't: Embed secrets (API keys, passwords) in code or buildspecs
- Don't: Use magic strings for configuration values

**Parameterization Strategy:**

| Data Type | Storage Location | Example |
|-----------|-----------------|---------|
| **Secrets** (passwords, API keys) | AWS Secrets Manager | `secretsmanager:get-secret-value` |
| **Configuration** (ARNs, endpoints) | SSM Parameter Store | `/aura/dev/admin-role-arn` |
| **Environment-specific** | CloudFormation Parameters | `Environment`, `ProjectName` |
| **Build-time** | CodeBuild Environment Variables | Reference SSM/Secrets |

**Cost Guidance:**

- SSM Parameter Store (Standard): **FREE** - Use for non-secret configuration
- Secrets Manager: **$0.40/secret/month** - Use only for actual secrets

**Implementation Patterns:**

```yaml
# In buildspec, reference SSM instead of hardcoding
env:
  parameter-store:
    ADMIN_ROLE_ARN: /aura/${ENVIRONMENT}/admin-role-arn

# In CloudFormation, use dynamic references
Resources:
  MyCodeBuildProject:
    Type: AWS::CodeBuild::Project
    Properties:
      Source:
        Auth:
          Type: CODECONNECTIONS
          Resource: '{{resolve:ssm:/aura/global/codeconnections-arn}}'
```

**SSM Parameter Naming Convention:**

| Scope | Pattern | Examples |
|-------|---------|----------|
| **Global** (shared across environments) | `/aura/global/{parameter}` | `/aura/global/codeconnections-arn` |
| **Environment-specific** | `/aura/{env}/{parameter}` | `/aura/dev/admin-role-arn`, `/aura/prod/admin-role-arn` |
| **Service-specific** | `/aura/{env}/{service}/{parameter}` | `/aura/dev/eks/cluster-name` |

**Current SSM Parameters:**

| Parameter Path | Description | Type |
|----------------|-------------|------|
| `/aura/global/codeconnections-arn` | GitHub CodeConnections ARN | String |
| `/aura/dev/admin-role-arn` | SSO Administrator Role ARN | String |
| `/aura/dev/alert-email` | Alert notification email | String |

**When to Use SSM vs Hardcoding:**

- Use SSM for: ARNs, account IDs, role names, endpoints, external resource references
- Use SSM for: Any value that differs between environments (dev/qa/prod)
- Can hardcode: Static strings like service names, log prefixes, tag values that are project-wide constants

### Performance

- Don't: Query database in loops → Batch: Use bulk queries
- Don't: Load entire files into memory → Stream: Use generators for large files
- Don't: Block on I/O → Use: `async`/`await` for I/O operations

### Code Quality

- Don't: Use magic numbers → Define: Constants with descriptive names
- Don't: Write God classes (1000+ lines) → Refactor: Single responsibility principle
- Don't: Ignore type hints → Use: Type annotations for all public APIs

### Version Control & Dotfiles

**CRITICAL: Never commit dotfiles unless required for project configuration**

Dotfiles (files starting with `.`) should be added to `.gitignore` unless they are essential project configuration that must be shared across the team.

**Commit these dotfiles (shared project configuration):**

- `.flake8` - Python linting rules
- `.markdownlint.json` / `.markdownlint-cli2.jsonc` - Markdown linting rules
- `.github/` - GitHub Actions workflows and templates
- `.gitignore` - Git ignore rules (obviously)
- `.dockerignore` - Docker build exclusions

**Never commit these (local/generated artifacts):**

- `.coverage` - pytest coverage data
- `.pytest_cache/` - pytest cache
- `.mypy_cache/` - mypy type checker cache
- `.ruff_cache/` - ruff linter cache
- `node_modules/` - npm dependencies (regenerate with `npm install`)
- `.env` - environment variables with secrets
- `.vscode/` / `.idea/` - IDE settings (user-specific)

**Rule of thumb:** If a dotfile is generated by a tool or contains user-specific settings, it should be in `.gitignore`. If it defines project-wide rules or workflows, it should be committed.

### Context Management (Claude Code Efficiency)

- Don't: Read entire large files into context → Reference: Files by path, read on-demand
- Don't: Repeat documentation in messages → Use: This CLAUDE.md for persistent context
- Don't: Run Grep with `output_mode="content"` on huge codebases → Use: `files_with_matches` first, then targeted reads

---

## Roadmap Sections (Archived Dec 2025)

> **Now referenced via:** `PROJECT_STATUS.md` for current completion status

### Short-Term (Q1 2026) - All Complete

1. GitHub Actions Integration - 5 workflows deployed: ci-autofix, security-review, webhook, code-quality, release-please
2. HITL Approval Dashboard - React UI deployed to EKS via ArgoCD (ApprovalDashboard.jsx)
3. Git Ingestion Pipeline - FastAPI REST API, DynamoDB persistence, observability integration
4. Sandbox Testing Environment - Step Functions workflow, DynamoDB tables, HITL integration deployed

### Medium-Term (Q2-Q3 2026)

1. Real-Time Anomaly Detection - Complete (Dec 5, 2025): E2E validated, 15/15 tests passing, SNS alerts active
2. GovCloud Migration Execution - Deploy to AWS GovCloud (US) with STIG/FIPS hardening
3. CMMC Level 3 Preparation - Security controls, documentation, compliance audits
4. Advanced Security Features - Threat intelligence integration, automated blocklists

### Long-Term (Q4 2026+)

1. CMMC Level 3 Certification - Final audit and government authorization
2. FedRAMP High Authorization - Federal deployment readiness
3. Production GovCloud Deployment - Full migration complete
4. Advanced AI Capabilities - Enhanced agent reasoning, multi-model support

---

## Efficient Context Management (Archived Dec 14, 2025)

> **Now referenced via:** Brief note in CLAUDE.md pointing to this archive

### Guidelines for Token Efficiency

**1. Reference Files by Path (Don't Read Unless Editing)**

- Good: "Follow design principles in `context/design-workflows/design-principles.md`"
- Bad: Reading entire 9,500-line design-principles.md into context

**2. Use Targeted File Reads**

```python
# Read specific section only
Read(file_path="PROJECT_STATUS.md", offset=100, limit=50)

# Read just the beginning (summary)
Read(file_path="CHANGELOG.md", limit=100)
```

**3. Use Grep Instead of Reading Full Files**

```python
# Find specific patterns
Grep(pattern="class.*Agent", output_mode="files_with_matches")

# Get specific lines with context
Grep(pattern="def orchestrate", output_mode="content", -B=2, -A=5)
```

**4. When to Read Full Files**

- Only when editing the file
- When the full content is needed for analysis (rare)
- For small files (<500 lines)

**5. Leverage This CLAUDE.md**

- This file is always loaded automatically (free)
- Put frequently-needed info here instead of repeating in messages
- Keep it under 1,000 lines for efficiency

**6. Start Fresh Conversations for New Major Tasks**

- Use `/clear` to archive completed work and start fresh
- Break large projects into conversation phases
- Example phases: Research → Design → Implementation → Testing → Deployment

---

## Visual Development (UI/UX) (Archived Dec 14, 2025)

> **Now referenced via:** `context/design-workflows/design-principles.md`

### Design Principles

When making visual (front-end, UI/UX) changes, always reference `context/design-workflows/design-principles.md` for:

- Enterprise-grade design system
- Component specifications (buttons, inputs, tables, modals, graphs)
- Accessibility checklist (WCAG 2.1 AA)
- Module-specific patterns (Dashboard, Vulnerabilities, Patches, Agents, GraphRAG)

### Quick Visual Check

IMMEDIATELY after implementing any front-end change:

1. **Identify what changed** - Review modified components/pages
2. **Verify design compliance** - Compare against design principles
3. **Check acceptance criteria** - Ensure change fulfills user request
4. **Validate accessibility** - Keyboard navigation, focus states, color contrast

### Comprehensive Design Review

For thorough design validation, reference the design review workflow:

- **Workflow:** `context/design-workflows/design-review-workflow.md`
- **7-Phase Methodology:** Preparation → Interaction → Responsiveness → Visual Polish → Accessibility → Robustness → Code Health
- **When to use:** Before finalizing PRs with visual changes, after significant UI features

---

## AI Agent Development (Archived Dec 14, 2025)

> **Now referenced via:** `src/agents/` source files and `context/agents/` templates

### Agent Implementation Patterns

**Agent Structure:**

```python
class BaseAgent:
    def __init__(self, llm_client, context_service):
        self.llm = llm_client
        self.context = context_service

    def execute(self, task: Task) -> Result:
        # 1. Retrieve context
        context = self.context.retrieve(task)

        # 2. Build prompt
        prompt = self._build_prompt(task, context)

        # 3. Call LLM
        response = self.llm.generate(prompt)

        # 4. Parse and validate
        result = self._parse_response(response)

        return result
```

**Security Considerations for Agents:**

- **Input Sanitization:** Remove/escape quotes, validate file paths, check for command injection
- **Prompt Injection Prevention:** Never allow user-controlled system prompts
- **Tool Use Authorization:** Whitelist allowed tools, restrict dangerous operations
- **Context Validation:** Verify GraphRAG context before passing to LLM
- **Error Handling:** Don't leak sensitive prompts or internal state in errors

**Example: Secure Input Sanitizer**

```python
def sanitize_input(user_input: str) -> str:
    """Remove quotes and dangerous characters to prevent injection."""
    # Remove all quotes (safer than escaping)
    sanitized = user_input.replace('"', '').replace("'", '')

    # Validate file paths
    if '..' in sanitized or sanitized.startswith('/'):
        raise ValueError("Invalid file path")

    return sanitized
```

---

## Sandbox Network Service (Archived Dec 14, 2025)

> **Now referenced via:** `docs/HITL_SANDBOX_ARCHITECTURE.md`

### Sandbox Isolation Levels

- **Container:** Isolated container with restricted capabilities
- **VPC:** Dedicated VPC with NetworkPolicy restrictions
- **Full:** Complete network isolation with dedicated resources

### Network Security

- **NetworkPolicy:** Blocks external network access, whitelists upstream DNS only
- **Metadata Service Blocking:** 169.254.169.254 unreachable from sandboxes
- **Resource Quotas:** CPU/memory limits prevent DoS
- **Capability Restrictions:** Containers run with minimal Linux capabilities (no CAP_SYS_ADMIN, CAP_NET_RAW)

### Service Discovery

Sandboxes use custom DNS domains for isolation:

- **Sandbox Domain:** `{sandbox_id}.sandbox.aura.local`
- **Mock Endpoints:** Local versions of Neptune, OpenSearch for testing

---

## Test File Organization (Archived Dec 14, 2025)

> **Now referenced via:** `docs/TESTING_STRATEGY.md`

**CRITICAL: One test file per module/feature** - Test files should mirror source files.

| Aspect | Separate Files (Preferred) | Single Comprehensive File |
|--------|---------------------------|---------------------------|
| **Maintainability** | Easy to find/update tests | Hard to navigate 500+ line files |
| **Parallel Execution** | `pytest -n auto` runs in parallel | Single file runs sequentially |
| **CI/CD Granularity** | Run only affected tests on PRs | Must run everything |
| **Failure Isolation** | Clear which module broke | Must parse through output |

**Standard Structure:**
```
tests/
├── conftest.py                    # Shared fixtures (auto-discovered by pytest)
├── module_name/
│   ├── __init__.py
│   ├── conftest.py                # Module-specific fixtures
│   ├── test_feature_a.py          # Tests for feature_a.py
│   ├── test_feature_b.py          # Tests for feature_b.py
│   └── test_integration.py        # Integration tests for module
```

**Naming Convention:**
- Source: `src/lambda/chat/diagram_tools.py` → Test: `tests/lambda/chat/test_diagram_tools.py`
- Shared fixtures go in `conftest.py` (pytest auto-discovers)
- Integration tests use `test_*_integration.py` suffix

---

## Complete Sub-Layer Reference Table (Archived Dec 14, 2025)

> **Now referenced via:** `docs/SUBLAYER_REFERENCE.md` or grep `deploy/cloudformation/*.yaml` for Description fields

| Sub-Layer | Template | Purpose |
|-----------|----------|---------|
| **1.1** | networking.yaml | VPC, Subnets, NAT |
| **1.2** | security.yaml | Security Groups |
| **1.3** | iam.yaml | IAM Roles & Policies |
| **1.4** | kms.yaml | KMS Keys |
| **1.5** | vpc-endpoints.yaml | VPC Endpoints |
| **1.6** | ecr-base-images.yaml | Base Container Images |
| **1.7** | network-services.yaml | dnsmasq ECS Service |
| **1.8** | build-cache.yaml | CI/CD Build Cache |
| **1.9** | codebuild-docker.yaml | Docker Build Project |
| **2.1** | dynamodb.yaml | DynamoDB Tables |
| **2.2** | s3.yaml | S3 Buckets |
| **2.3** | neptune-simplified.yaml | Neptune Graph DB |
| **2.4** | neptune-serverless.yaml | Neptune Serverless |
| **2.5** | opensearch.yaml | OpenSearch Cluster |
| **3.1** | eks.yaml | EKS Cluster |
| **3.2** | acm-certificate.yaml | TLS Certificates |
| **3.3** | alb-controller.yaml | ALB Ingress Controller |
| **4.1** | ecr-dnsmasq.yaml | dnsmasq Container Image |
| **4.2** | ecr-api.yaml | API Container Image |
| **4.3** | aura-bedrock-infrastructure.yaml | Bedrock Integration |
| **4.4** | cognito.yaml | User Authentication |
| **4.5** | bedrock-guardrails.yaml | LLM Safety Rails |
| **4.6** | irsa-aura-api.yaml | IRSA for API |
| **4.7** | ecr-frontend.yaml | Frontend Container Image |
| **4.8** | ecr-memory-service.yaml | Neural Memory Container |
| **5.1** | secrets.yaml | Secrets Manager |
| **5.2** | monitoring.yaml | CloudWatch Dashboards |
| **5.3** | aura-cost-alerts.yaml | Budget Alerts |
| **5.4** | realtime-monitoring.yaml | Real-time Metrics |
| **5.5** | disaster-recovery.yaml | DR Configuration |
| **5.6** | otel-collector.yaml | OpenTelemetry |
| **6.1** | threat-intel-scheduler.yaml | Threat Intelligence |
| **6.2** | hitl-scheduler.yaml | HITL Scheduling |
| **6.3** | hitl-callback.yaml | HITL API Callbacks |
| **6.4** | a2a-infrastructure.yaml | Agent-to-Agent Comms |
| **6.5** | orchestrator-dispatcher.yaml | Workflow Dispatch |
| **6.6** | dns-blocklist-lambda.yaml | DNS Blocklist Updates |
| **6.7** | chat-assistant.yaml | Chat Interface |
| **6.8** | runbook-agent.yaml | Runbook Automation |
| **6.9** | incident-response.yaml | Incident Management |
| **6.10** | incident-investigation-workflow.yaml | Investigation Workflow |
| **7.1** | sandbox.yaml | Sandbox Environment |
| **7.2** | hitl-workflow.yaml | HITL Step Functions |
| **8.1** | config-compliance.yaml | AWS Config Rules |
| **8.2** | guardduty.yaml | Threat Detection |
| **8.3** | drift-detection.yaml | Infrastructure Drift |
| **8.4** | red-team.yaml | Security Testing |

---

## File Structure Tree (Archived Dec 14, 2025)

> **Now referenced via:** Run `ls -la` or explore via IDE

```bash
aura/
├── src/
│   ├── agents/              # Agent implementations (Orchestrator, Coder, Reviewer, Validator)
│   ├── services/            # Core services (Context Retrieval, Monitoring, Sandbox Network)
│   ├── api/                 # FastAPI endpoints (future)
│   └── utils/               # Shared utilities
├── tests/                   # Pytest test suite
├── deploy/
│   ├── kubernetes/          # Kubernetes manifests (DaemonSet, NetworkPolicy, Prometheus)
│   ├── cloudformation/      # AWS CloudFormation templates
│   ├── config/              # Configuration files (dnsmasq, application config)
│   ├── docker/              # Dockerfiles and docker-compose
│   └── scripts/             # Deployment automation scripts
├── docs/                    # Detailed documentation
├── context/                 # Design workflows and agent templates
│   ├── design-workflows/    # Design principles, review workflows
│   └── agents/              # Specialized agent templates
└── frontend/ (future)       # React/TypeScript UI
```

---

## Completed Roadmap Items (Archived Dec 14, 2025)

> **Now referenced via:** `PROJECT_STATUS.md` for current roadmap

### Q4 2025 Completed Milestones

1. ✅ **dnsmasq Integration** - Complete (ready to deploy)
2. ✅ **Design Workflow System** - Complete (context folder created)
3. ✅ **GovCloud Migration Planning** - Complete (architecture, cost analysis, automation scripts)
4. ✅ **Multi-Tier EKS Templates** - Complete (GovCloud-compatible EC2 node groups)
5. ✅ **Phase 1-3 Infrastructure Deployment** - Foundation, Data, Compute layers deployed to AWS Commercial Cloud
6. ✅ **Deploy dnsmasq Network Services** - Tier 1 DaemonSet with DNSSEC deployed to EKS cluster
7. ✅ **Create Remaining Specialized Agents** - code-quality, performance, test-coverage, documentation (completed Dec 2, 2025)
8. ✅ **Real LLM Integration** - Bedrock operational, Claude 3.5 Sonnet approved and tested (Nov 30, 2025)
9. ✅ **GitOps with ArgoCD (ADR-022)** - ArgoCD v2.13.2 + Argo Rollouts v1.8.3 deployed (Dec 5, 2025)
   - GitHub App authentication, canary deployments, ClusterAnalysisTemplates

---

## Buildspec Sizes Reference (Archived Dec 14, 2025)

> **Now referenced via:** `wc -l deploy/buildspecs/*.yml`

**As of 2025-12-12:**

| Buildspec | Lines | Status |
|-----------|-------|--------|
| buildspec-application.yml | 599 | At limit |
| buildspec-foundation.yml | 549 | OK |
| buildspec-serverless.yml | 489 | OK |
| buildspec-observability.yml | 358 | OK |
| Others | <350 | OK |

---

## Docker Build Examples (Archived Dec 14, 2025)

> **Now referenced via:** `docs/DEPLOYMENT_GUIDE.md` or `deploy/docker/README.md`

EKS runs on x86_64 (amd64) architecture. When building Docker images on ARM-based machines (Apple Silicon Macs, Windows ARM), **always specify the target platform** to avoid "exec format error" at runtime:

```bash
# Build for EKS (x86_64) - REQUIRED on ARM machines
docker build --platform linux/amd64 -t <image-name> -f <dockerfile> .

# Example: Build API image for ECR
docker build --platform linux/amd64 \
  -t 123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-api-dev:latest \
  -f deploy/docker/api/Dockerfile.api .

# Push to ECR (login first)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-api-dev:latest
```

---

## Testing Strategy Details (Archived Dec 14, 2025)

> **Now referenced via:** `docs/TESTING_STRATEGY.md`

### Testing Pyramid

| Layer | Purpose | Target | Uses Mocks? |
|-------|---------|--------|-------------|
| **Unit** | Verify individual functions | 80%+ coverage | No |
| **Integration** | Verify component contracts | Workflow coverage | Yes (external services) |
| **E2E** | Verify full system | Critical paths | No (real AWS) |

### Running Tests

```bash
pytest                              # All tests
pytest -n auto                      # Parallel execution (faster)
pytest -m "not integration"         # Unit tests only
pytest -m integration               # Integration tests only
pytest --cov=src --cov-report=html  # With coverage
pytest tests/lambda/chat/           # Run specific module tests only
```
