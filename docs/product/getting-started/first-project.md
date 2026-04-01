# First Project Walkthrough

**Time to Complete:** 30-45 minutes
**Skill Level:** Beginner

This tutorial walks you through a complete vulnerability remediation cycle using Project Aura. You will connect a sample repository, identify vulnerabilities, generate patches, and approve your first fix.

---

## What You Will Learn

By the end of this tutorial, you will be able to:

- Navigate the Aura dashboard and understand key metrics
- Connect a repository and configure scan settings
- Interpret vulnerability findings and severity levels
- Review AI-generated patches with full context
- Approve or reject patches through the HITL workflow
- Monitor remediation status and verify deployment

---

## Prerequisites

Before starting this tutorial, ensure you have:

- [ ] Active Aura account with Security Engineer or Admin role
- [ ] Access to a test repository (we provide a sample if needed)
- [ ] Completed the [Quick Start Guide](./quick-start.md) basic setup

---

## Part 1: Understanding the Dashboard

After signing in to Aura, you land on the Dashboard, your command center for security operations.

### Dashboard Overview

![Dashboard Overview](../images/placeholder-dashboard-overview.png)

The Dashboard displays four key sections:

**1. Metric Cards (Top Row)**

| Card | What It Shows |
|------|---------------|
| **Critical Vulnerabilities** | Count of critical-severity findings requiring immediate attention |
| **Pending Approvals** | Patches waiting for human review |
| **Agent Status** | Health of AI agents (active, idle, error) |
| **System Uptime** | Platform availability percentage |

**2. Vulnerability Trend Chart**

A 30-day line chart showing:
- Total vulnerabilities detected (gray line)
- Vulnerabilities remediated (green line)
- Net change over time

Healthy organizations show the green line trending upward relative to gray.

**3. Activity Feed**

Real-time log of platform events:
- Vulnerability detections
- Patch generation completions
- Approval decisions
- Deployment confirmations

**4. Quick Actions**

Navigation shortcuts for common tasks:
- Run Full Scan
- View Critical Vulnerabilities
- Open Approval Queue

### Exercise 1.1: Explore the Dashboard

1. Identify the number of pending approvals (if any)
2. Check the agent status, noting any agents in error state
3. Review the last 5 entries in the Activity Feed

---

## Part 2: Setting Up a Sample Project

For this tutorial, we will use a deliberately vulnerable sample repository that demonstrates common security issues.

### Option A: Use the Aura Sample Repository

Aura provides a sample repository with known vulnerabilities for training purposes.

1. Navigate to **Settings > Integrations**

2. If not already connected, connect your GitHub account

3. Click **Add Repository**

4. Search for `aenealabs/vulnerable-app-sample`

5. Select the repository and click **Add**

### Option B: Use Your Own Repository

If you prefer to use your own repository:

1. Select a non-production repository for testing
2. Ensure you have write access (for patch deployment)
3. Confirm the repository is not currently in active development

### Configure Scan Settings

After adding the repository:

1. Click on the repository name in **Projects**

2. Navigate to the **Settings** tab

3. Configure the following:

   | Setting | Recommended Value |
   |---------|-------------------|
   | **Default Branch** | `main` |
   | **Auto-Scan on Push** | Disabled (for this tutorial) |
   | **Scan Schedule** | None (manual scans only) |
   | **HITL Level** | FULL_HITL |

4. Click **Save Settings**

![Project Settings](../images/placeholder-project-settings.png)

---

## Part 3: Running Your First Scan

Now let's scan the repository for vulnerabilities.

### Initiate a Full Scan

1. From the project view, click **Run Scan**

2. Select **Full Scan** to analyze the entire codebase

3. Click **Start Scan**

### Monitor Scan Progress

The scan progress panel shows:

```
Scan Progress: 45%
==================================

Phase 1: Repository Clone         [Complete]
Phase 2: AST Parsing             [Complete]
Phase 3: Graph Construction       [In Progress]
Phase 4: Vulnerability Detection  [Pending]
Phase 5: Results Processing       [Pending]

Files Analyzed: 127 / 283
Vulnerabilities Found: 3
Estimated Time Remaining: 2 minutes
```

![Scan Progress](../images/placeholder-scan-progress-detailed.png)

### Understanding Scan Phases

| Phase | What Happens |
|-------|--------------|
| **Repository Clone** | Fetches latest code from source control |
| **AST Parsing** | Parses source files into abstract syntax trees |
| **Graph Construction** | Builds code knowledge graph (entities, relationships) |
| **Vulnerability Detection** | Runs security analyzers against the codebase |
| **Results Processing** | Deduplicates, enriches, and ranks findings |

Wait for the scan to complete before proceeding. This typically takes 5-15 minutes depending on repository size.

---

## Part 4: Interpreting Vulnerability Findings

Once the scan completes, you will see a summary of findings.

### Results Summary

![Scan Results Summary](../images/placeholder-scan-results-summary.png)

The sample repository typically contains these vulnerability types:

| Severity | Count | Example |
|----------|-------|---------|
| **Critical** | 1 | SQL Injection in user input handling |
| **High** | 2 | Weak cryptography (SHA1), hardcoded credentials |
| **Medium** | 4 | Missing input validation, outdated dependencies |
| **Low** | 3 | Informational findings, best practice suggestions |

### Examining Individual Findings

1. Click **View All Vulnerabilities**

2. The vulnerability list shows:

   | Column | Description |
   |--------|-------------|
   | **Severity** | Color-coded badge (Critical, High, Medium, Low) |
   | **Type** | Vulnerability category (SQL Injection, XSS, etc.) |
   | **Location** | File path and line number |
   | **Status** | Current state (Open, In Progress, Patched) |
   | **CVE** | Associated CVE identifier if applicable |

3. Click on any vulnerability to see details

### Vulnerability Detail View

Selecting a vulnerability opens the detail panel:

![Vulnerability Detail](../images/placeholder-vulnerability-detail.png)

**Sections:**

**1. Summary**
- Vulnerability type and severity
- Brief description of the risk
- CVSS score if applicable

**2. Affected Code**
```python
# Location: src/database/queries.py, Line 45
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"  # VULNERABLE
    return db.execute(query)
```

**3. Risk Assessment**
- Impact description (data breach, unauthorized access, etc.)
- Exploitability analysis
- OWASP category reference

**4. Remediation Guidance**
- Recommended fix approach
- Code example of secure pattern
- Related documentation links

### Exercise 4.1: Analyze a Critical Finding

1. Locate the SQL Injection vulnerability in the list
2. Open the detail view
3. Identify:
   - The exact line of code with the vulnerability
   - The function name containing the issue
   - The OWASP category (likely A03:2021 Injection)

---

## Part 5: Generating an AI Patch

Now let's have Aura generate a patch for one of the vulnerabilities.

### Select a Vulnerability for Patching

For this tutorial, we will patch the **Weak Cryptography (SHA1)** vulnerability, as it has a straightforward fix.

1. From the vulnerability list, click on the SHA1 finding

2. Review the vulnerable code:

```python
# src/utils/hashing.py, Line 12
import hashlib

def calculate_checksum(data):
    return hashlib.sha1(data.encode()).hexdigest()
```

3. Click **Generate Patch**

### Patch Generation Process

Aura's AI agents begin working:

```
Patch Generation: In Progress
==================================

[10:30:15] Orchestrator: Received patch request for VULN-2025-0042
[10:30:16] Context Service: Retrieving related code entities...
[10:30:18] Context Service: Found 12 related functions, 3 test files
[10:30:20] Coder Agent: Analyzing vulnerability pattern...
[10:30:25] Coder Agent: Generating patch...
[10:30:35] Reviewer Agent: Validating patch correctness...
[10:30:40] Sandbox Service: Provisioning test environment...
[10:31:15] Validator Agent: Executing test suite...
[10:32:00] Validator Agent: All tests passed (47/47)
[10:32:05] Orchestrator: Patch ready for approval
```

![Patch Generation Progress](../images/placeholder-patch-generation-progress.png)

### Understanding Agent Roles

| Agent | Role in This Process |
|-------|---------------------|
| **Orchestrator** | Coordinates the workflow, assigns tasks |
| **Context Service** | Retrieves related code for full understanding |
| **Coder Agent** | Generates the actual code fix |
| **Reviewer Agent** | Validates the fix against security best practices |
| **Sandbox Service** | Creates isolated environment for testing |
| **Validator Agent** | Runs automated tests on the patched code |

Wait for patch generation to complete (typically 2-5 minutes).

---

## Part 6: Reviewing the Patch

After generation completes, the patch enters the approval queue.

### Navigate to Approvals

1. Click the notification indicator, or
2. Navigate to **Approvals** in the sidebar

### Approval Dashboard Layout

![Approval Dashboard](../images/placeholder-approval-dashboard.png)

The approval dashboard uses a master-detail layout:

**Left Panel: Approval Queue**
- List of pending approvals
- Shows severity, type, and age
- Highlight indicates selected item

**Right Panel: Approval Details**
- Full context for the selected patch
- Multiple sections for comprehensive review

### Review Sections

**1. Vulnerability Context**

Overview of the original vulnerability:

| Field | Value |
|-------|-------|
| **Type** | Weak Cryptographic Hash |
| **Severity** | High |
| **File** | src/utils/hashing.py |
| **Line** | 12 |
| **CVE** | N/A (best practice violation) |

**2. Proposed Patch (Diff View)**

Side-by-side comparison:

```diff
# src/utils/hashing.py

  import hashlib

  def calculate_checksum(data):
-     return hashlib.sha1(data.encode()).hexdigest()
+     return hashlib.sha256(data.encode()).hexdigest()
```

Review considerations:
- Is the change minimal and focused?
- Does it preserve the function signature?
- Are there downstream impacts?

**3. Sandbox Test Results**

Automated validation summary:

| Test Category | Result | Details |
|---------------|--------|---------|
| **Syntax Validation** | Passed | Code compiles without errors |
| **Unit Tests** | Passed | 47/47 tests pass |
| **Security Scan** | Passed | No new vulnerabilities |
| **Performance** | Passed | No latency regression |

Click **View Full Report** for detailed test output.

**4. Code Context**

Related code entities identified by Aura:

- `src/utils/hashing.py` - Current file
- `src/services/file_processor.py` - Calls calculate_checksum()
- `tests/test_hashing.py` - Unit tests for the function

**5. Deployment Plan**

Where the patch will be applied:

| Setting | Value |
|---------|-------|
| **Target Branch** | `main` |
| **Merge Strategy** | Pull Request |
| **CI Trigger** | Yes (existing workflow) |

### Exercise 6.1: Comprehensive Review

Before approving, verify:

1. [ ] The original vulnerability is correctly identified
2. [ ] The patch addresses the specific issue
3. [ ] No unrelated code changes are included
4. [ ] All sandbox tests passed
5. [ ] The deployment target is correct

---

## Part 7: Making an Approval Decision

Based on your review, make an informed decision.

### Approval Options

**Approve**
- Confirms the patch is correct and safe
- Triggers deployment to the target branch
- Creates a pull request or direct commit

**Reject**
- Declines the patch as unsuitable
- Requires a reason for rejection
- Notifies the system to not retry automatically

**Request Changes**
- Indicates issues needing resolution
- Opens a comment form for specific feedback
- Keeps the patch in a "changes requested" state

### Approve the Patch

For this tutorial, let's approve the SHA1 to SHA256 patch:

1. After completing your review, click **Approve Patch**

2. A confirmation dialog appears:

   ```
   Confirm Approval
   ================

   You are approving patch PATCH-2025-0042 for deployment.

   Summary:
   - Vulnerability: Weak Cryptographic Hash (SHA1)
   - Change: SHA1 -> SHA256 in calculate_checksum()
   - Target: main branch via pull request

   This action will:
   - Create a pull request in the repository
   - Trigger CI/CD pipeline
   - Mark vulnerability as "Remediated"

   [Cancel]  [Confirm Approval]
   ```

3. Click **Confirm Approval**

### Post-Approval Status

After approval:

1. The patch status changes to **Approved**
2. A pull request is created in your repository
3. Your CI/CD pipeline runs automatically
4. The vulnerability status updates to **Remediated (Pending Merge)**

![Approval Confirmation](../images/placeholder-approval-confirmation.png)

---

## Part 8: Monitoring Remediation Status

Track the patch through deployment.

### Activity Feed Updates

The Dashboard Activity Feed shows progress:

```
[10:35:12] Patch PATCH-2025-0042 approved by user@company.com
[10:35:15] Pull request #142 created in aenealabs/vulnerable-app-sample
[10:35:20] CI pipeline triggered for PR #142
[10:38:45] CI pipeline passed (all checks green)
[10:38:50] Pull request ready for merge
```

### Repository Pull Request

In your source control provider:

![Pull Request](../images/placeholder-pull-request.png)

The PR includes:
- Descriptive title with vulnerability reference
- Summary of the change
- Link back to Aura for context
- Automated CI checks

### Merge the Pull Request

1. Navigate to your repository's pull request page
2. Review the PR (one final check)
3. Click **Merge Pull Request**
4. Confirm the merge

### Verify Remediation

After merging:

1. Return to Aura's vulnerability list
2. The SHA1 vulnerability now shows status: **Patched**
3. The Dashboard metrics update:
   - One fewer vulnerability in the count
   - Trend chart shows remediation progress

![Remediation Complete](../images/placeholder-remediation-complete.png)

---

## Part 9: Understanding the Complete Workflow

You have now completed a full vulnerability remediation cycle. Let's review what happened:

### Workflow Summary

```
+------------------+     +------------------+     +------------------+
|   1. Detection   | --> |   2. Analysis    | --> |  3. Generation   |
|   (Scan)         |     | (Context/Graph)  |     |  (Coder Agent)   |
+------------------+     +------------------+     +------------------+
                                                          |
                                                          v
+------------------+     +------------------+     +------------------+
|  6. Deployment   | <-- |   5. Approval    | <-- |   4. Testing     |
|   (CI/CD)        |     |  (Human Review)  |     |  (Sandbox)       |
+------------------+     +------------------+     +------------------+
                                                          |
                                                          v
                                               +------------------+
                                               |  7. Verification |
                                               |  (Audit Trail)   |
                                               +------------------+
```

### Key Touchpoints

| Step | Automation Level | Your Role |
|------|------------------|-----------|
| Detection | Fully automated | Monitor scan results |
| Analysis | Fully automated | Review context |
| Generation | Fully automated | Wait for completion |
| Testing | Fully automated | Review test results |
| Approval | Human decision | **Critical: Approve/Reject** |
| Deployment | Automated trigger | Merge PR |
| Verification | Automated | Confirm status |

### Time Savings

Compare traditional vs. Aura remediation:

| Metric | Traditional | With Aura |
|--------|-------------|-----------|
| Time to identify | 1-2 days | Minutes |
| Time to patch | 2-4 hours | 5 minutes |
| Time to test | 1-2 hours | Automated |
| Time to deploy | 30 min - 2 hours | Automated |
| **Total** | **1-3 days** | **15-30 minutes** |

---

## Part 10: Next Steps

Congratulations on completing your first vulnerability remediation with Aura! Here are recommended next steps:

### Immediate Actions

1. **Review Remaining Vulnerabilities**
   - Return to the vulnerability list
   - Generate patches for additional findings
   - Practice the approval workflow

2. **Configure Notifications**
   - Set up email alerts for critical findings
   - Configure Slack integration for approvals
   - Enable PagerDuty for incidents

3. **Invite Team Members**
   - Add security engineers to your organization
   - Assign appropriate roles
   - Document your approval policies

### Advanced Topics

| Topic | When to Explore |
|-------|-----------------|
| **Custom HITL Policies** | After establishing baseline workflow |
| **CI/CD Integration** | Ready for pipeline automation |
| **Compliance Reporting** | Preparing for audits |
| **Code Knowledge Graph** | Understanding codebase relationships |
| **Agent Monitoring** | Troubleshooting or optimization |

### Documentation References

- **[Platform Overview](./index.md)** - Comprehensive feature overview
- **[System Requirements](./system-requirements.md)** - Environment prerequisites
- **[Installation Guide](./installation.md)** - Deployment options

### Getting Help

If you encounter issues or have questions:

- **Documentation:** [docs.aenealabs.com](https://docs.aenealabs.com)
- **Support Portal:** [support.aenealabs.com](https://support.aenealabs.com)
- **Community Forum:** [community.aenealabs.com](https://community.aenealabs.com)
- **Email:** support@aenealabs.com

---

## Summary

In this tutorial, you learned to:

- Navigate the Aura dashboard and interpret key metrics
- Configure a project for security scanning
- Run a full codebase scan and interpret results
- Generate AI-powered patches for vulnerabilities
- Review patches with full context in the approval workflow
- Make informed approval decisions
- Monitor remediation through deployment
- Verify successful vulnerability resolution

The entire process, from detection to deployment, demonstrates how Aura reduces Mean Time to Remediate from days to minutes while maintaining human oversight for compliance requirements.

---

## Feedback

We are continuously improving our documentation. If you have suggestions for this tutorial:

- Click the **Feedback** button in the documentation sidebar
- Email documentation@aenealabs.com
- Create an issue in our public documentation repository

Thank you for choosing Project Aura!
