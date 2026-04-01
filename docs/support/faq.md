# Frequently Asked Questions (FAQ)

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Table of Contents

1. [General Questions](#general-questions)
2. [Account and Authentication](#account-and-authentication)
3. [Repository Management](#repository-management)
4. [Vulnerability Detection](#vulnerability-detection)
5. [Patch Generation and Approval](#patch-generation-and-approval)
6. [HITL Workflow](#hitl-workflow)
7. [API and Integration](#api-and-integration)
8. [Self-Hosted Deployment](#self-hosted-deployment)
9. [Performance and Scaling](#performance-and-scaling)
10. [Security and Compliance](#security-and-compliance)
11. [Billing and Pricing](#billing-and-pricing)

---

## General Questions

### What is Project Aura?

Project Aura is an autonomous AI SaaS platform that enables machines to reason across entire enterprise codebases through a hybrid graph-based architecture. It uses adaptive intelligence to automate security vulnerability detection, patch generation, and remediation with human-in-the-loop (HITL) approval processes.

### How does Project Aura work?

```
+-------------------------------------------------------------------------+
|                       PROJECT AURA WORKFLOW                              |
+-------------------------------------------------------------------------+

1. CONNECT          2. ANALYZE          3. DETECT           4. PATCH
+----------+       +----------+       +----------+       +----------+
| Connect  |------>| Build    |------>| Scan for |------>| Generate |
| your     |       | code     |       | vulns    |       | patches  |
| repos    |       | graph    |       | via AI   |       | via AI   |
+----------+       +----------+       +----------+       +----------+
                                                               |
                                                               v
5. VALIDATE         6. APPROVE          7. DEPLOY
+----------+       +----------+       +----------+
| Test in  |<------| Human    |------>| Deploy   |
| sandbox  |       | review   |       | to prod  |
+----------+       +----------+       +----------+
```

1. **Connect** repositories via GitHub, GitLab, or Bitbucket OAuth
2. **Analyze** code to build a comprehensive knowledge graph (functions, dependencies, call flows)
3. **Detect** vulnerabilities using AI-powered semantic analysis
4. **Generate** patches using LLM agents with full codebase context
5. **Validate** patches in isolated sandbox environments
6. **Approve** patches through configurable HITL workflows
7. **Deploy** approved patches via pull request or direct commit

### What languages and frameworks does Aura support?

| Language | Support Level | Framework Coverage |
|----------|---------------|-------------------|
| Python | Full | Django, Flask, FastAPI, SQLAlchemy |
| JavaScript/TypeScript | Full | React, Vue, Node.js, Express |
| Java | Full | Spring Boot, Hibernate, Maven |
| Go | Full | Gin, Echo, standard library |
| C# | Beta | .NET Core, ASP.NET |
| Ruby | Beta | Rails, Sinatra |
| PHP | Planned | Laravel, Symfony |
| Rust | Planned | Actix, Rocket |

### What types of vulnerabilities does Aura detect?

Aura detects vulnerabilities across multiple categories:

- **OWASP Top 10**: SQL Injection, XSS, CSRF, Authentication issues
- **CWE**: 200+ Common Weakness Enumeration categories
- **Dependency Vulnerabilities**: CVE-based detection from package managers
- **Custom Patterns**: Organization-specific security rules
- **AI-Specific Threats**: Prompt injection, model poisoning, agent confusion

---

## Account and Authentication

### How do I create an account?

1. Visit [app.aenealabs.com](https://app.aenealabs.com)
2. Click "Sign Up" and choose authentication method:
   - Email/password
   - SSO via Google, Microsoft, or GitHub
   - Enterprise SAML/OIDC (contact sales)
3. Verify your email address
4. Complete the onboarding wizard

### How do I enable two-factor authentication (2FA)?

```
1. Go to Settings > Security > Two-Factor Authentication
2. Choose your 2FA method:
   - Authenticator app (recommended)
   - SMS (less secure)
   - Hardware key (FIDO2/WebAuthn)
3. Scan the QR code with your authenticator app
4. Enter the verification code
5. Save your backup codes securely
```

### How do I configure SSO for my organization?

Enterprise customers can configure SAML 2.0 or OIDC:

1. Go to **Admin Settings > Authentication > SSO**
2. Select your identity provider (Okta, Azure AD, etc.)
3. Download our SP metadata or copy the configuration values
4. Configure your IdP with our SP details
5. Upload the IdP metadata or enter configuration values
6. Test the SSO connection
7. Enable for all users (optional)

For detailed SSO setup, see [Security Issues - SSO Authentication](./troubleshooting/security-issues.md#aura-sec-001-sso-authentication-failed).

### I forgot my password. How do I reset it?

1. Go to the login page and click "Forgot Password"
2. Enter your email address
3. Check your email for the reset link (valid for 1 hour)
4. Click the link and create a new password
5. If using SSO, contact your IT administrator

---

## Repository Management

### How do I connect a repository?

```bash
# Via UI:
1. Navigate to Repositories > Connect Repository
2. Select your Git provider (GitHub, GitLab, Bitbucket)
3. Authorize Aura to access your repositories
4. Select the repository to connect
5. Configure scan settings (branch, schedule, languages)

# Via API:
curl -X POST https://api.aenealabs.com/v1/repositories \
  -H "Authorization: Bearer ${AURA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-repo",
    "url": "https://github.com/org/my-repo",
    "default_branch": "main"
  }'
```

### What permissions does Aura need for my repository?

| Provider | Required Permissions | Purpose |
|----------|---------------------|---------|
| GitHub | `repo` (read), `pull_request` (write) | Clone code, create PRs |
| GitLab | `read_repository`, `write_repository` | Clone code, create MRs |
| Bitbucket | `repository:read`, `pullrequest:write` | Clone code, create PRs |

Aura never stores your code permanently. Code is processed in memory and only metadata (graph structure, embeddings) is persisted.

### How often does Aura scan my repository?

Default scan schedule by plan:

| Plan | Default Schedule | Minimum Interval |
|------|-----------------|------------------|
| Free | Daily (2 AM UTC) | 24 hours |
| Professional | Every 6 hours | 1 hour |
| Enterprise | Configurable | 15 minutes |

You can also trigger manual scans via the UI or API.

### Can I exclude files or directories from scanning?

Yes, create a `.aura-ignore` file in your repository root:

```
# .aura-ignore
# Ignore test fixtures
tests/fixtures/

# Ignore generated code
**/generated/
**/dist/

# Ignore specific files
legacy-code.py
vendor/

# Ignore by pattern
*.min.js
*.test.ts
```

---

## Vulnerability Detection

### How accurate is Aura's vulnerability detection?

| Metric | Value | Measurement Period |
|--------|-------|-------------------|
| True Positive Rate | 94.2% | Q4 2025 |
| False Positive Rate | 8.3% | Q4 2025 |
| Detection Coverage | 89% of OWASP Top 10 | Q4 2025 |

Aura continuously improves detection accuracy through:
- Customer feedback on false positives
- Model fine-tuning on confirmed vulnerabilities
- Expanded training on diverse codebases

### What information does Aura provide for each vulnerability?

Each vulnerability includes:

- **Severity**: Critical, High, Medium, Low (based on CVSS 3.1)
- **Title and Description**: Clear explanation of the issue
- **Location**: File path, line numbers, function name
- **CWE/CVE IDs**: Standardized weakness/vulnerability identifiers
- **Code Snippet**: Vulnerable code highlighted
- **Remediation Guidance**: Recommended fix approach
- **References**: Links to documentation and resources

### How do I mark a vulnerability as a false positive?

```bash
# Via UI:
1. Go to Vulnerability Details
2. Click "Actions" > "Mark as False Positive"
3. Select reason: false_positive, accepted_risk, not_applicable, compensating_control
4. Add a comment explaining the decision
5. Submit

# Via API:
curl -X PATCH https://api.aenealabs.com/v1/vulnerabilities/vuln-12345 \
  -H "Authorization: Bearer ${AURA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "ignored",
    "ignore_reason": "false_positive",
    "comment": "This is a test file, not production code"
  }'
```

False positive data helps improve detection accuracy for your organization.

---

## Patch Generation and Approval

### How does Aura generate patches?

Aura uses a multi-agent AI system:

1. **Coder Agent**: Analyzes vulnerability context using GraphRAG, generates fix using Claude 3.5 Sonnet
2. **Reviewer Agent**: Reviews patch for correctness, style, and side effects
3. **Validator Agent**: Tests patch in isolated sandbox (syntax, unit tests, security scans)

The system has full context of your codebase, including:
- Function call graphs
- Dependency relationships
- Type information
- Related code patterns

### How long does patch generation take?

| Vulnerability Complexity | Typical Time | Maximum Time |
|--------------------------|--------------|--------------|
| Simple (single file) | 30 seconds | 2 minutes |
| Moderate (multi-file) | 2 minutes | 10 minutes |
| Complex (architectural) | 5 minutes | 15 minutes |

Patches are generated asynchronously. You'll receive a notification when ready.

### Can I customize how patches are generated?

Yes, via patch generation settings:

```json
{
  "patch_config": {
    "style_guide": "google",
    "max_files_changed": 5,
    "preserve_comments": true,
    "prefer_stdlib": true,
    "test_generation": "optional",
    "diff_format": "unified"
  }
}
```

Enterprise customers can also provide custom prompts and examples.

### How do I approve a patch?

```
1. Navigate to the patch in the UI
2. Review the diff and sandbox test results
3. Optionally add comments
4. Click "Approve" or "Reject"

Required permissions: security_admin or organization_admin role
```

For API-based approval, see [REST API - Approve Patch](./api-reference/rest-api.md#post-patchesidapprove).

---

## HITL Workflow

### What is Human-in-the-Loop (HITL)?

HITL ensures human oversight of AI-generated patches before deployment. You can configure:

- **Which vulnerabilities require approval**: By severity, repository, team
- **Who can approve**: Roles, teams, specific users
- **Approval requirements**: Single approver vs. multiple approvers
- **Timeout behavior**: Auto-reject, auto-escalate, notify

### What HITL policy presets are available?

| Preset | Description | Auto-Deploy |
|--------|-------------|-------------|
| FULL_HITL | All patches require approval | None |
| CMMC_LEVEL_3 | Critical/High require approval | Medium/Low |
| SOX_COMPLIANCE | Critical require 2 approvers | High/Medium/Low |
| HITL_CRITICAL | Only critical require approval | High/Medium/Low |
| AUTONOMOUS | No HITL required | All |

### How do I configure HITL policies?

```bash
# Via API:
curl -X PUT https://api.aenealabs.com/v1/settings/hitl \
  -H "Authorization: Bearer ${AURA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "autonomy_level": "HITL_CRITICAL",
    "policy_preset": "SOX_COMPLIANCE",
    "approval_timeout_hours": 48,
    "auto_escalation_enabled": true,
    "notification_channels": ["email", "slack"],
    "required_approvers": {
      "critical": 2,
      "high": 1,
      "medium": 0,
      "low": 0
    }
  }'
```

### What happens if no one approves a patch?

Configurable timeout behavior:

| Action | Description |
|--------|-------------|
| `notify` | Send reminder notifications (default) |
| `escalate` | Notify higher-level approvers |
| `auto_reject` | Automatically reject the patch |
| `hold` | Keep pending indefinitely |

---

## API and Integration

### How do I get an API token?

```bash
# Option 1: Login to get temporary token
curl -X POST https://api.aenealabs.com/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "your-password"}'

# Option 2: Create API key (for automation)
# Go to Settings > API Keys > Create New Key
# Select scopes and expiration
# Copy the key (only shown once)
```

### What are the API rate limits?

| Tier | Requests/Minute | Burst | Headers |
|------|-----------------|-------|---------|
| Free | 100 | 10 | X-RateLimit-* |
| Professional | 1000 | 100 | X-RateLimit-* |
| Enterprise | 10000 | 1000 | X-RateLimit-* |

See [API Reference - Rate Limiting](./api-reference/index.md#rate-limiting) for handling 429 errors.

### Does Aura integrate with my CI/CD pipeline?

Yes, via multiple integration options:

| Integration | Use Case |
|-------------|----------|
| GitHub Actions | Trigger scans on PR, comment results |
| GitLab CI | Pipeline integration, MR comments |
| Jenkins | Plugin for scan triggers |
| CircleCI | Orb for pipeline integration |
| Webhooks | Custom integrations |

**GitHub Actions Example:**

```yaml
name: Aura Security Scan
on: [pull_request]
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: aenealabs/aura-action@v1
        with:
          api-key: ${{ secrets.AURA_API_KEY }}
          fail-on: critical,high
```

### Can I integrate Aura with Slack/Teams?

Yes, configure notifications in Settings > Integrations:

**Slack:**
1. Create a Slack app or use incoming webhook
2. Add the webhook URL to Aura
3. Select which events to send (vulnerability detected, patch approved, etc.)

**Microsoft Teams:**
1. Create an incoming webhook connector
2. Add the webhook URL to Aura
3. Configure event filters

---

## Self-Hosted Deployment

### Can I run Aura on-premises?

Yes, Aura offers self-hosted deployment for Enterprise customers:

- **Full On-Premises**: All components run in your infrastructure
- **Hybrid**: Data layer on-premises, compute in cloud
- **Air-Gapped**: No internet connectivity required

See [Self-Hosted Deployment Guide](../deployment/DEPLOYMENT_GUIDE.md) for details.

### What are the system requirements for self-hosted?

**Minimum Requirements:**

| Component | Specification |
|-----------|--------------|
| Kubernetes | 1.28+ (EKS, GKE, AKS, or vanilla) |
| Nodes | 4x m5.xlarge (or equivalent) |
| Neptune | db.r5.large (or compatible graph DB) |
| OpenSearch | r6g.large x 2 nodes |
| Storage | 500 GB SSD |
| Network | Private VPC with NAT gateway |

**For Air-Gapped:**
- Local container registry
- Local LLM (Ollama, vLLM) or on-premises Claude deployment

### How do I update my self-hosted deployment?

```bash
# 1. Check current version
kubectl get deployment aura-api -n aura-system -o jsonpath='{.spec.template.spec.containers[0].image}'

# 2. Review release notes
# https://docs.aenealabs.com/releases

# 3. Update via Helm
helm repo update aenealabs
helm upgrade aura aenealabs/aura \
  -n aura-system \
  --version 1.7.0 \
  -f values.yaml

# 4. Verify upgrade
kubectl rollout status deployment/aura-api -n aura-system
```

---

## Performance and Scaling

### How do I improve scan performance?

1. **Use `.aura-ignore`** to exclude unnecessary files
2. **Enable incremental scans** (only changed files)
3. **Optimize repository structure** (avoid monolithic repos)
4. **Upgrade plan** for parallel processing

### Why is my API slow?

Common causes and solutions:

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| All requests slow | Rate limiting | Check X-RateLimit headers |
| Specific endpoint slow | Complex query | Add filters, use pagination |
| Intermittent slowness | Backend load | Retry with backoff |
| Timeouts | Large result set | Use pagination, reduce scope |

See [Performance Issues](./troubleshooting/performance-issues.md) for detailed diagnostics.

### How does Aura handle large codebases?

Aura is designed for enterprise-scale codebases:

| Metric | Tested Limit |
|--------|--------------|
| Lines of code | 10 million+ |
| Files per repository | 100,000+ |
| Repositories per org | 1,000+ |
| Concurrent scans | 50+ |

For very large codebases, we recommend:
- Modular repository structure
- Targeted scanning (specific directories)
- Incremental scan mode

---

## Security and Compliance

### How does Aura protect my code?

- **Encryption in Transit**: TLS 1.3 for all API communication
- **Encryption at Rest**: AES-256 for stored data
- **No Code Storage**: Source code is processed in memory, not stored
- **Data Isolation**: Multi-tenant architecture with strict separation
- **Access Controls**: RBAC with audit logging

### Is Aura SOC 2 compliant?

Yes, Aura maintains SOC 2 Type II certification. Contact sales for audit reports.

### What compliance frameworks does Aura support?

| Framework | Status | Notes |
|-----------|--------|-------|
| SOC 2 Type II | Certified | Annual audit |
| ISO 27001 | Certified | Annual audit |
| HIPAA | Available | BAA required |
| GDPR | Compliant | EU data residency option |
| FedRAMP | In Progress | GovCloud deployment |
| CMMC Level 3 | Supported | Self-hosted required |

### Can I run Aura in my AWS GovCloud account?

Yes, self-hosted deployment is available for GovCloud (US) regions. Contact sales for FedRAMP-compliant deployment options.

---

## Billing and Pricing

### What plans are available?

| Plan | Repositories | Scans/Month | Users | Price |
|------|--------------|-------------|-------|-------|
| Free | 3 | 100 | 1 | $0 |
| Professional | 25 | Unlimited | 10 | $499/mo |
| Enterprise | Unlimited | Unlimited | Unlimited | Contact Sales |

### How are scans counted?

A scan is counted when:
- Scheduled scan runs (daily, hourly, etc.)
- Manual scan is triggered
- CI/CD integration triggers a scan

**Not counted:**
- Partial/incremental scans (1 full scan equivalent)
- Failed scans that don't complete
- API queries (vulnerabilities, patches, etc.)

### Can I upgrade or downgrade my plan?

Yes, you can change plans at any time:
- **Upgrade**: Effective immediately, prorated charge
- **Downgrade**: Effective at next billing cycle

To change your plan:
1. Go to Settings > Billing > Change Plan
2. Select new plan
3. Confirm changes

---

## Getting Help

### How do I contact support?

| Channel | Response Time | Best For |
|---------|---------------|----------|
| Documentation | Immediate | General questions |
| Community Forum | < 24 hours | Discussions, tips |
| Email Support | < 24 hours (business) | Account issues |
| Priority Support | < 4 hours | Enterprise, critical issues |
| Phone Support | Immediate | Enterprise, emergencies |

**Support Portal:** [support.aenealabs.com](https://support.aenealabs.com)
**Email:** support@aenealabs.com

### Where can I report a bug?

1. Check if it's a [known issue](./troubleshooting/common-issues.md)
2. Gather diagnostic information (error codes, request IDs, screenshots)
3. Submit via:
   - Support portal (preferred)
   - GitHub issues (for self-hosted)
   - Email to support@aenealabs.com

### How do I request a new feature?

1. Check the [public roadmap](https://roadmap.aenealabs.com)
2. Search for existing feature requests
3. Submit or upvote via:
   - Feature request portal
   - Customer success manager (Enterprise)
   - Community forum

---

## Related Documentation

- [Support Documentation Index](./index.md)
- [Troubleshooting Guide](./troubleshooting/index.md)
- [API Reference](./api-reference/index.md)
- [Architecture Overview](./architecture/index.md)
- [Operations Guide](./operations/index.md)

---

*Last updated: January 2026 | Version 1.0*
