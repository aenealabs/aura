# Patch Approval Workflows

**Version:** 1.0
**Last Updated:** January 2026
**Time to Complete:** 20-30 minutes

---

## Overview

Patch approval workflows implement Human-in-the-Loop (HITL) governance for AI-generated security patches. This guide explains how to configure autonomy levels, review patches in the approval queue, and make informed approval decisions.

The HITL system ensures that:
- Critical changes receive appropriate human oversight
- Audit trails meet compliance requirements
- Organizations can balance automation with control

---

## Prerequisites

Before working with patch approvals, ensure you have:

- [ ] Security Engineer or Admin role in your organization
- [ ] Understanding of your organization's autonomy policy
- [ ] Familiarity with the vulnerabilities being patched

> **Note:** Viewer and Developer roles can view approval history but cannot approve or reject patches. Contact your administrator if you need approval permissions.

---

## Autonomy Levels

Aura supports four configurable autonomy levels that determine when human approval is required.

### Level Overview

| Level | Name | Approval Required | Best For |
|-------|------|-------------------|----------|
| **1** | FULL_HITL | All patches | Defense, Healthcare, Government |
| **2** | HITL_CRITICAL | Critical and High severity only | Financial Services, Enterprise |
| **3** | AUDIT_ONLY | None (logged only) | Internal Tools, Low-Risk Repos |
| **4** | FULL_AUTONOMOUS | Guardrails only | Development/Test Environments |

### FULL_HITL (Level 1)

Every patch requires human approval before deployment.

**Behavior:**
- All vulnerability remediations queue for approval
- Detection and patch generation are automated
- Human reviews every proposed change
- Maximum oversight and control

**Use cases:**
- CMMC Level 3 compliance requirements
- Healthcare (HIPAA) environments
- Government contractor systems
- Defense and aerospace codebases

**Timeout:** 24 hours default (configurable)

### HITL_CRITICAL (Level 2)

Only Critical and High severity patches require approval.

**Behavior:**
- LOW and MEDIUM severity patches auto-deploy after sandbox testing
- HIGH and CRITICAL patches queue for human review
- Reduces approval volume while maintaining oversight for serious issues

**Use cases:**
- SOX compliance environments
- Financial services applications
- Enterprise standard deployments
- Teams with limited security engineering bandwidth

**Timeout:** 24 hours for CRITICAL, 48 hours for HIGH

### AUDIT_ONLY (Level 3)

All patches deploy automatically; decisions are logged for compliance.

**Behavior:**
- No approval queue (except guardrails)
- Full audit trail of all automated decisions
- Human review happens post-deployment via logs
- Suitable for lower-risk environments

**Use cases:**
- Internal tools and utilities
- Development environments
- Low-risk repositories
- Teams with high AI confidence

**Monitoring:** Review audit logs regularly for unexpected patterns

### FULL_AUTONOMOUS (Level 4)

Maximum automation with only guardrail protections.

**Behavior:**
- All patches deploy without human intervention
- Guardrail operations still require approval (see below)
- Real-time dashboards show all activity
- Anomaly alerts notify of unusual patterns

**Use cases:**
- Test and staging environments
- Rapid iteration development
- Proof-of-concept deployments
- Organizations with mature DevSecOps

> **Warning:** FULL_AUTONOMOUS still enforces guardrails. Production deployments, credential changes, and infrastructure modifications always require approval regardless of autonomy level.

---

## Guardrails: Always-Approval Operations

Certain operations require human approval regardless of autonomy level. These guardrails cannot be disabled.

### Guardrail Operations

| Operation | Description | Why It Requires Approval |
|-----------|-------------|--------------------------|
| `production_deployment` | Deploying to production environment | High blast radius |
| `credential_modification` | Changing API keys, secrets, passwords | Security-critical |
| `access_control_change` | Modifying IAM, RBAC, permissions | Authorization boundary |
| `database_migration` | Schema changes, data modifications | Data integrity risk |
| `infrastructure_change` | Cloud resource modifications | Cost and availability |

### Guardrail Examples

Even with FULL_AUTONOMOUS level:

- Patch that changes AWS credentials = Requires approval
- Patch that modifies database schema = Requires approval
- Patch that adds production deployment config = Requires approval

> **Note:** Guardrails exist to protect against irreversible changes. They are mandated by compliance frameworks including SOX, CMMC, and HIPAA.

---

## Approval Queue

The approval queue displays all patches awaiting human review.

### Accessing the Queue

1. Click **Approvals** in the main navigation sidebar

2. Or click the **Pending Approvals** notification badge

> **Screenshot:** Approval queue with pending patches sorted by wait time, each row showing vulnerability, severity, repo, agent confidence, and a Review button.

### Queue Layout

**Left Panel: Pending Approvals**

List of patches awaiting review:

| Column | Description |
|--------|-------------|
| **Severity** | Vulnerability severity badge |
| **Type** | Vulnerability category |
| **Repository** | Source repository |
| **Age** | Time since patch was queued |
| **Timeout** | Time remaining before expiration |

**Right Panel: Approval Details**

Full context for the selected patch (see [Reviewing Patches](#reviewing-ai-generated-patches)).

### Queue Filtering

Filter the approval queue by:

- **Severity:** CRITICAL, HIGH, MEDIUM, LOW
- **Repository:** Specific repository or all
- **Age:** Recent, Today, This Week, Older
- **Assignee:** Assigned to me, Unassigned, All

### Queue Sorting

Sort by:
- **Severity (default):** Critical first
- **Age:** Oldest first
- **Timeout:** Expiring soonest first
- **Repository:** Alphabetical

---

## Reviewing AI-Generated Patches

Thorough review is essential for safe patch deployment.

### Patch Review Checklist

Before approving any patch, verify:

- [ ] Vulnerability is correctly identified
- [ ] Patch addresses the specific issue
- [ ] No unrelated code changes included
- [ ] Coding patterns match repository standards
- [ ] All sandbox tests passed
- [ ] Deployment target is correct

### Review Panel Sections

> **Screenshot:** Patch review panel with four sections: Vulnerability Context, Proposed Patch (unified diff), Sandbox Test Results, and the Approve / Reject / Request Changes action bar.

**1. Vulnerability Context**

Original vulnerability details:

```
Vulnerability: SQL Injection in User Query Handler
Severity: CRITICAL
File: src/database/queries.py
Line: 47
CVE: CVE-2024-12345
CVSS: 9.8
Detected: 2026-01-20 14:32 UTC
```

**2. Proposed Patch (Diff View)**

Side-by-side or unified diff of changes:

```diff
# src/database/queries.py

  import hashlib
+ from typing import Optional
  from sqlalchemy.orm import Session

- def get_user_by_id(user_id):
-     """Get user by ID."""
-     query = f"SELECT * FROM users WHERE id = '{user_id}'"
-     result = db.execute(query)
-     return result.fetchone()
+ def get_user_by_id(user_id: str) -> Optional[User]:
+     """
+     Get user by ID using parameterized query.
+
+     Args:
+         user_id: The unique identifier of the user.
+
+     Returns:
+         User object if found, None otherwise.
+     """
+     return db.query(User).filter(User.id == user_id).first()
```

**Review considerations:**
- Is the change minimal and focused?
- Does it preserve function signatures and behavior?
- Are type hints and documentation appropriate?
- Are there backward compatibility concerns?

**3. AI Reasoning**

Explanation from the Coder Agent:

```
Confidence: 0.94

Reasoning:
This patch addresses SQL injection by replacing string interpolation
with SQLAlchemy ORM parameterized query. The pattern matches 847
similar successful remediations in our training data with a 99.2%
success rate.

The function signature is updated to include type hints for clarity.
A docstring is added following repository conventions detected in
other files.

Related entities checked:
- src/api/user_endpoints.py - Uses return value; compatible
- tests/test_queries.py - Tests will pass with no modifications
```

**4. Sandbox Test Results**

Automated validation results:

| Test Category | Status | Details |
|---------------|--------|---------|
| **Syntax Validation** | Passed | Code parses without errors |
| **Unit Tests** | Passed | 47/47 tests pass |
| **Security Scan** | Passed | No new vulnerabilities introduced |
| **Performance** | Passed | No latency regression (< 5ms delta) |
| **Integration** | Passed | API contracts maintained |

Click **View Full Report** to see detailed test output, including:
- Individual test case results
- Security scanner output
- Performance benchmark comparisons

**5. Deployment Plan**

Where and how the patch will be applied:

| Setting | Value |
|---------|-------|
| **Target Branch** | `main` |
| **Merge Strategy** | Pull Request |
| **PR Title** | `fix(security): Remediate SQL injection in get_user_by_id` |
| **CI Required** | Yes (repository workflow) |
| **Auto-merge** | After CI passes |

**6. Impact Analysis**

Potential downstream effects:

```
Files Modified: 1
Functions Changed: 1
Callers Affected: 3
  - src/api/user_endpoints.py:get_user (line 24)
  - src/middleware/auth.py:authenticate (line 87)
  - src/services/user_service.py:fetch_user (line 156)

Tests Covering Changed Code: 12 (100% coverage maintained)
```

---

## Making Approval Decisions

### Approve

Use when the patch is correct and safe for deployment.

**To approve:**

1. Complete the review checklist

2. Click **Approve Patch**

3. Optionally add a comment:
   ```
   Reviewed patch. Parameterized query pattern is correct.
   Verified test coverage is maintained.
   ```

4. Click **Confirm Approval**

**After approval:**
- Patch is committed to target branch
- Pull request is created (if configured)
- CI/CD pipeline triggers
- Vulnerability status updates to "Remediated (Pending Merge)"

### Reject

Use when the patch is incorrect, incomplete, or inappropriate.

**To reject:**

1. Identify the issue with the patch

2. Click **Reject Patch**

3. Select rejection reason:
   - **Incorrect Fix** - Patch does not address vulnerability
   - **Incomplete** - Missing necessary changes
   - **Style Violation** - Does not match code standards
   - **Risk Too High** - Potential for regression
   - **Other** - Custom reason

4. Enter detailed feedback (required):
   ```
   The patch changes the return type but does not update callers.
   This will cause runtime errors in user_endpoints.py.

   Suggested fix: Update the return type to match existing signature
   or update all callers to handle Optional[User].
   ```

5. Click **Confirm Rejection**

**After rejection:**
- Patch is discarded
- Feedback is logged for AI improvement
- Vulnerability remains open
- Optional: Re-generate with different parameters

### Request Changes

Use when the patch is close but needs modifications.

**To request changes:**

1. Click **Request Changes**

2. Specify what changes are needed:
   ```
   The fix is correct but please:
   1. Keep the existing function signature for backward compatibility
   2. Add a TODO comment noting the type hint update for v2
   3. Update the docstring to match our standard format
   ```

3. Click **Submit Request**

**After requesting changes:**
- Patch enters "Changes Requested" state
- Coder Agent processes feedback
- New patch version is generated
- You receive notification when ready

---

## Sandbox Testing

Every patch is validated in an isolated sandbox before approval.

### Sandbox Environment

| Component | Configuration |
|-----------|---------------|
| **Runtime** | AWS ECS Fargate (isolated container) |
| **Network** | No external network access |
| **Timeout** | 5 minutes default |
| **Resources** | 2 vCPU, 4GB RAM |

### Test Categories

| Test | What It Validates |
|------|-------------------|
| **Syntax** | Code compiles/parses correctly |
| **Unit Tests** | Existing test suite passes |
| **Security Scan** | No new vulnerabilities introduced |
| **Performance** | No latency regression beyond threshold |
| **Integration** | API contracts maintained |

### Reviewing Sandbox Results

1. In the patch review panel, locate **Sandbox Results**

2. Click **View Full Report** for detailed output

3. Review each test category:

   **Unit Test Details:**
   ```
   Test Suite: tests/test_queries.py
   Total: 47  Passed: 47  Failed: 0  Skipped: 0

   test_get_user_by_id_valid .............. PASS (0.02s)
   test_get_user_by_id_invalid ............ PASS (0.01s)
   test_get_user_by_id_not_found .......... PASS (0.01s)
   ...
   ```

   **Security Scan Output:**
   ```
   Scanner: Bandit v1.7.5
   Severity: HIGH

   Findings: 0 new issues
   Previous: 1 SQL Injection (resolved by patch)
   Status: PASSED
   ```

### Failed Sandbox Tests

If sandbox tests fail:

1. Review the failure details in the report

2. The patch cannot be approved with failing tests

3. Options:
   - **Reject** with feedback for regeneration
   - **Request Changes** with specific fixes
   - Report as sandbox configuration issue if incorrect

---

## Bulk Approval

For organizations with high patch volume, bulk approval streamlines the process.

### Bulk Approval Eligibility

Bulk approval is available when:
- Multiple patches are pending
- Patches are LOW or MEDIUM severity
- All sandbox tests passed
- Your autonomy policy allows bulk operations

> **Note:** CRITICAL and HIGH severity patches cannot be bulk approved. They require individual review.

### Bulk Approval Workflow

1. In the approval queue, select multiple patches using checkboxes

2. Click **Bulk Actions > Approve Selected**

3. Review the summary:
   ```
   Bulk Approval Summary
   =====================

   Selected: 8 patches
   Eligible for bulk: 6 patches (LOW/MEDIUM severity)
   Requires individual review: 2 patches (HIGH severity)

   Eligible patches:
   - VULN-001: XSS sanitization (MEDIUM) - repo-a
   - VULN-002: Dependency update (LOW) - repo-a
   - VULN-003: Header fix (LOW) - repo-b
   - VULN-004: Input validation (MEDIUM) - repo-b
   - VULN-005: Logging fix (LOW) - repo-c
   - VULN-006: Encoding fix (MEDIUM) - repo-c

   [Cancel]  [Review HIGH Patches]  [Approve 6 Patches]
   ```

4. Click **Approve 6 Patches**

5. Add optional bulk comment:
   ```
   Bulk approved after verifying sandbox test results for low-risk patches.
   ```

6. Confirm approval

---

## Notifications and Escalation

### Notification Configuration

Configure how you receive approval notifications:

1. Navigate to **Settings > Notifications**

2. Enable approval-related notifications:

   | Notification | Channels |
   |--------------|----------|
   | New patch pending approval | Email, Slack |
   | Approval timeout warning | Email, Slack, SMS |
   | Patch deployed after approval | Email |
   | Escalation to backup reviewer | Email, Slack |

### Timeout and Escalation

Patches do not wait indefinitely. Aura implements automatic escalation.

**Timeout Thresholds:**

| Severity | Default Timeout | Warning At | Escalation |
|----------|-----------------|------------|------------|
| CRITICAL | 24 hours | 18 hours (75%) | 12 hours |
| HIGH | 24 hours | 18 hours (75%) | 12 hours |
| MEDIUM | 48 hours | 36 hours (75%) | N/A (expires) |
| LOW | 72 hours | 54 hours (75%) | N/A (expires) |

**Escalation Behavior:**

1. **Warning notification** sent at 75% of timeout
2. For CRITICAL/HIGH: **Escalation** to backup reviewers
3. For MEDIUM/LOW: **Expiration** and re-queue option

**Configure backup reviewers:**

1. Navigate to **Settings > Security Policies > Escalation**

2. Add backup reviewers:
   ```
   Primary Reviewers: security-team@company.com
   Backup Reviewers: security-lead@company.com, ciso@company.com
   ```

3. Set escalation timeout and max escalations

---

## Audit Trail

All approval decisions are logged for compliance.

### Logged Events

| Event | Data Captured |
|-------|---------------|
| Approval request created | Vulnerability, patch, sandbox results, timestamp |
| Notification sent | Recipient, channel, delivery status |
| Human decision | Approver identity, decision, comments |
| Escalation | Original reviewer, backup reviewer, reason |
| Deployment | Patch applied, environment, timestamp |
| Timeout/Expiration | Request details, final status |

### Viewing Audit History

1. Navigate to **Compliance > Audit Logs**

2. Filter by:
   - Date range
   - Action type (approval, rejection, escalation)
   - User
   - Repository

3. Export for compliance reporting

### Audit Log Retention

| Environment | Retention Period |
|-------------|------------------|
| Production | 7 years |
| Development | 90 days |
| Self-hosted | Configurable |

---

## Policy Configuration

### Viewing Current Policy

1. Navigate to **Settings > Security Policies**

2. View your organization's active policy:
   ```
   Organization: ACME Corp
   Policy: enterprise_standard (preset)
   Default Level: HITL_CRITICAL
   HITL Enabled: Yes

   Severity Overrides:
     LOW: FULL_AUTONOMOUS
     MEDIUM: AUDIT_ONLY

   Repository Overrides:
     payment-gateway: FULL_HITL
     internal-docs: FULL_AUTONOMOUS
   ```

### Modifying Policy

> **Note:** Policy changes require Admin role.

1. Click **Edit Policy**

2. Select base preset or configure custom:

   | Preset | Default Level | Target Industry |
   |--------|---------------|-----------------|
   | `defense_contractor` | FULL_HITL | Defense, Aerospace |
   | `financial_services` | FULL_HITL | Banking, Insurance |
   | `healthcare` | FULL_HITL | Hospitals, Pharma |
   | `enterprise_standard` | HITL_CRITICAL | Fortune 500 |
   | `fintech_startup` | HITL_CRITICAL | Growth Companies |
   | `internal_tools` | AUDIT_ONLY | Internal Dev Teams |

3. Configure overrides as needed

4. Click **Save Policy**

> **Warning:** Reducing oversight levels (e.g., FULL_HITL to HITL_CRITICAL) may affect compliance. Consult your compliance team before making changes.

---

## Troubleshooting

### Patch Stuck in Queue

**Symptom:** Patch remains pending despite review attempt.

**Solutions:**
1. Verify you have approval permissions
2. Check for pending sandbox tests
3. Ensure no blocking conditions (concurrent edits, etc.)
4. Contact support if issue persists

### Approval Button Disabled

**Symptom:** Cannot click Approve or Reject.

**Common causes:**

| Cause | Solution |
|-------|----------|
| Insufficient permissions | Contact admin for role upgrade |
| Sandbox tests incomplete | Wait for completion |
| Patch expired | Re-queue the patch |
| Session timeout | Refresh page and re-authenticate |

### Escalation Not Working

**Symptom:** Patches not escalating to backup reviewers.

**Solutions:**
1. Verify backup reviewers are configured
2. Check reviewer email addresses are valid
3. Ensure escalation timeout is not set too high
4. Review escalation logs in Audit Trail

---

## Related Documentation

- [Vulnerability Remediation](./vulnerability-remediation.md) - Finding and prioritizing vulnerabilities
- [Core Concepts: HITL Workflows](../core-concepts/hitl-workflows.md) - Technical details
- [Core Concepts: Sandbox Security](../core-concepts/sandbox-security.md) - Sandbox environment details
- [Team Collaboration](./team-collaboration.md) - Managing reviewer teams
