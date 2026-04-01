# Project Aura: Platform Overview

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## What is Project Aura?

Project Aura is an autonomous AI-powered security platform that detects vulnerabilities, generates patches, and deploys fixes across enterprise codebases with minimal human intervention. Unlike traditional security scanners that only identify problems, Aura provides end-to-end remediation through a sophisticated multi-agent AI system.

Built from the ground up for regulated industries, Aura combines advanced AI capabilities with enterprise-grade compliance controls. The platform uses a hybrid graph-based architecture to understand your entire codebase, enabling context-aware security patching that traditional tools cannot match.

Organizations using Aura typically reduce their Mean Time to Remediate (MTTR) from 45 days to under 4 hours while maintaining full audit trails for compliance requirements.

---

## Who is Aura For?

### Primary Users

| Role | How Aura Helps |
|------|----------------|
| **Security Engineers** | Review AI-generated patches with full context, approve fixes in minutes instead of days |
| **DevSecOps Teams** | Automate security scanning and remediation within CI/CD pipelines |
| **Compliance Officers** | Generate audit-ready reports with immutable approval trails |
| **CISOs and Security Leadership** | Track security posture trends, measure ROI on security automation |

### Target Industries

- **Defense and Aerospace** - CMMC Level 2/3 compliance, GovCloud deployment
- **Financial Services** - SOX compliance, rapid vulnerability remediation
- **Healthcare** - HIPAA-compliant security operations
- **Government Contractors** - FedRAMP authorization path, NIST 800-53 controls
- **Enterprise Technology** - Large codebase management, multi-repository support

---

## Key Benefits

### Autonomous Remediation
Aura does not just find vulnerabilities. It generates syntactically correct, context-aware patches that can be deployed immediately after human approval. Our AI agents understand your codebase structure, coding patterns, and dependencies.

### Human-in-the-Loop Governance
Every critical change flows through configurable approval workflows. Security teams review AI-generated patches with full visibility into the original vulnerability, the proposed fix, and automated test results. This approach satisfies audit requirements while maintaining the speed of automation.

### Compliance-Ready Architecture
Built for regulated industries from day one. Aura supports CMMC Level 3, SOX Section 404, NIST 800-53, and FedRAMP High requirements. All actions are logged with 7-year retention, and the platform can deploy to AWS GovCloud for government workloads.

### Deep Code Understanding
The hybrid GraphRAG architecture combines structural analysis (call graphs, dependencies, inheritance) with semantic understanding (natural language queries, similarity search). This enables Aura to generate patches that consider the full context of your codebase.

### Isolated Testing
Every patch is validated in an isolated sandbox environment before reaching human reviewers. Automated tests verify syntax correctness, functional behavior, security posture, and performance impact. Patches that fail sandbox testing never reach the approval queue.

---

## Platform Architecture

Project Aura consists of four integrated layers that work together to provide autonomous security remediation.

### 1. Detection Layer

The platform continuously monitors your codebase and external threat feeds to identify vulnerabilities. Detection sources include:

- **Code Scanning** - SAST analysis for security vulnerabilities
- **Dependency Analysis** - SCA for third-party library risks
- **Threat Intelligence** - CVE feeds and emerging threat data
- **Runtime Monitoring** - Application behavior analysis

### 2. Intelligence Layer

The hybrid GraphRAG engine provides deep code understanding through:

- **Neptune Graph Database** - Stores structural relationships (call graphs, dependencies, inheritance hierarchies)
- **OpenSearch Vector Store** - Enables semantic search and similarity matching
- **Context Retrieval Service** - Fuses results from multiple sources for optimal context

### 3. Agent Layer

Specialized AI agents collaborate to remediate vulnerabilities:

| Agent | Responsibility |
|-------|----------------|
| **Orchestrator** | Coordinates workflow, assigns tasks, manages state |
| **Coder Agent** | Generates context-aware patches using LLM capabilities |
| **Reviewer Agent** | Validates patches against security best practices |
| **Validator Agent** | Executes sandbox tests and verifies patch quality |
| **Monitor Agent** | Tracks system health, costs, and performance |

### 4. Governance Layer

Enterprise controls ensure safe and compliant operation:

- **HITL Approval Workflows** - Configurable approval gates for different risk levels
- **Sandbox Environments** - Isolated ECS Fargate environments for patch testing
- **Audit Logging** - Immutable records of all decisions and actions
- **Notification Services** - Multi-channel alerts via email, Slack, and Teams

![Platform Architecture](../images/placeholder-architecture-overview.png)

---

## Core Capabilities

### Vulnerability Management

Aura provides centralized visibility into your security posture across all connected repositories. The platform automatically categorizes vulnerabilities by severity, tracks remediation status, and surfaces the highest-priority issues requiring attention.

**Features:**
- Unified vulnerability dashboard across repositories
- Severity-based prioritization (Critical, High, Medium, Low)
- CVE correlation and deduplication
- Remediation status tracking
- Trend analysis and reporting

### Autonomous Patch Generation

The Coder Agent generates production-ready patches using deep codebase understanding. Unlike simple find-and-replace tools, Aura considers:

- Code structure and dependencies
- Existing coding patterns and conventions
- Test coverage requirements
- Performance implications
- Backward compatibility

**Typical Patch Types:**
- Cryptographic algorithm upgrades (SHA1 to SHA256)
- SQL injection prevention
- XSS sanitization
- Dependency version updates
- Access control fixes

### Sandbox Validation

Before any patch reaches human reviewers, it is validated in an isolated environment:

| Test Category | What It Validates |
|---------------|-------------------|
| **Syntax** | Code compiles and parses correctly |
| **Unit Tests** | Existing test suite passes |
| **Security Scans** | No new vulnerabilities introduced |
| **Performance** | No latency regression |
| **Integration** | API compatibility maintained |

Patches that fail sandbox testing are automatically rejected with detailed failure reports.

### Human-in-the-Loop Approval

Aura supports four autonomy levels that organizations can configure based on their risk tolerance and compliance requirements:

| Level | Description | Use Case |
|-------|-------------|----------|
| **FULL_HITL** | All changes require approval | CMMC Level 3, maximum oversight |
| **HITL_FINAL** | Approve deployment only | SOX compliance, trust in testing |
| **HITL_CRITICAL** | Approve critical/high severity only | Balanced automation |
| **FULL_AUTONOMOUS** | No approval required | Development environments |

### Compliance Reporting

Generate audit-ready reports with complete remediation timelines:

- Vulnerability detection timestamp
- Patch generation details
- Sandbox test results
- Approver identity and decision
- Deployment confirmation
- Post-deployment verification

All records are retained for 7 years to meet SOX and other regulatory requirements.

---

## Use Cases

### Enterprise Security Team

A defense contractor with 500+ vulnerabilities in their backlog uses Aura to automate remediation. The platform generates patches for 80% of issues autonomously, allowing security engineers to focus on complex vulnerabilities that require human judgment.

**Outcome:** MTTR reduced from 45 days to 4 hours, CMMC Level 2 certification achieved.

### DevSecOps Pipeline Integration

A financial services company integrates Aura into their CI/CD pipeline. Security scanning runs on every pull request, and low-severity issues are automatically patched. High-severity findings trigger approval workflows for security team review.

**Outcome:** 90% reduction in security-related deployment delays, zero production incidents from auto-patched code.

### Regulated Industry Deployment

A healthcare SaaS provider deploys Aura in their AWS GovCloud environment. HIPAA-compliant audit trails track every remediation action, and quarterly compliance reports are generated automatically.

**Outcome:** Successful audit completion, 65% reduction in compliance documentation effort.

### Incident Response Acceleration

A technology company uses Aura's Runtime Incident Agent to accelerate root cause analysis. When production incidents occur, the agent correlates error logs with recent deployments and code changes, generating remediation hypotheses with confidence scores.

**Outcome:** Mean Time to Resolution reduced by 70%, fewer repeat incidents.

---

## Integration Ecosystem

Aura integrates with your existing development and security tools.

### Source Control
- GitHub (Cloud and Enterprise)
- GitLab (SaaS and Self-Managed)
- Bitbucket (Cloud and Data Center)
- Azure DevOps Repos

### Notification Channels
- Email (Amazon SES)
- Slack (Webhooks and App)
- Microsoft Teams
- PagerDuty

### Security Tools
- Jira (Issue Tracking)
- ServiceNow (ITSM)
- Splunk (SIEM)
- Datadog (Observability)
- CrowdStrike (EDR)

### CI/CD Platforms
- GitHub Actions
- GitLab CI
- Jenkins
- AWS CodeBuild
- Azure DevOps Pipelines

---

## Deployment Options

### Cloud (SaaS)

The fastest path to value. Aenea Labs manages the infrastructure, and your team connects repositories and configures approval workflows.

- **Setup Time:** Same day
- **Maintenance:** Fully managed
- **Best For:** Teams wanting immediate value without infrastructure overhead

### Self-Hosted (Kubernetes)

Deploy Aura in your own AWS environment, including GovCloud regions. Your team controls the infrastructure while receiving software updates from Aenea Labs.

- **Setup Time:** 1-2 weeks
- **Maintenance:** Customer-managed infrastructure, vendor-provided software
- **Best For:** Organizations with data residency requirements or existing Kubernetes clusters

### Self-Hosted (Podman)

Run Aura on individual machines or VMs without Kubernetes. Ideal for air-gapped environments or organizations without container orchestration.

- **Setup Time:** 1 day
- **Maintenance:** Customer-managed
- **Best For:** Air-gapped deployments, small teams, proof-of-concept

---

## Security and Compliance

### Data Protection

| Control | Implementation |
|---------|----------------|
| **Encryption at Rest** | AES-256 via AWS KMS customer-managed keys |
| **Encryption in Transit** | TLS 1.3 for all communications |
| **Network Isolation** | VPC endpoints, no public internet exposure |
| **Secrets Management** | AWS Secrets Manager, no hardcoded credentials |

### Access Control

- SAML/OIDC single sign-on integration
- Role-based access control (RBAC)
- Multi-factor authentication support
- Audit logging of all access events

### Compliance Certifications

| Framework | Status |
|-----------|--------|
| **SOC 2 Type II** | Audit scheduled Q2 2026 |
| **CMMC Level 2** | Certification Q4 2026 |
| **FedRAMP High** | In-process, authorization Q1 2027 |
| **NIST 800-53** | 95% controls mapped |
| **HIPAA** | BAA available |

---

## Next Steps

Ready to get started with Project Aura? Continue with these guides:

- **[Quick Start Guide](./quick-start.md)** - Get up and running in 5 minutes
- **[System Requirements](./system-requirements.md)** - Verify your environment meets prerequisites
- **[Installation Guide](./installation.md)** - Detailed setup instructions
- **[First Project Walkthrough](./first-project.md)** - Connect your first repository and run your first scan

---

## Support and Resources

- **Documentation:** [docs.aenealabs.com](https://docs.aenealabs.com)
- **Support Portal:** [support.aenealabs.com](https://support.aenealabs.com)
- **Status Page:** [status.aenealabs.com](https://status.aenealabs.com)
- **Email:** support@aenealabs.com

For enterprise support inquiries, contact your account representative or email enterprise@aenealabs.com.
