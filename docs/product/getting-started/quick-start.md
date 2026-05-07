# Quick Start Guide

**Time to Complete:** 5 minutes
**Prerequisites:** Aura account, repository access

This guide walks you through connecting your first repository and running your initial security scan with Project Aura.

---

## Before You Begin

Ensure you have the following:

- [ ] Active Aura account (Cloud SaaS or self-hosted deployment)
- [ ] Repository access credentials (GitHub, GitLab, or Bitbucket)
- [ ] Admin or Security Engineer role in your Aura organization

If you do not have an account yet, contact your organization administrator or visit [aenealabs.com/signup](https://aenealabs.com/signup) to request access.

---

## Step 1: Sign In to Aura

1. Navigate to your Aura instance:
   - **Cloud:** `https://app.aenealabs.com`
   - **Self-hosted:** Your organization's configured URL

2. Sign in using your credentials:
   - SSO (recommended for enterprise)
   - Email and password

3. Complete MFA verification if enabled for your account.

> **Screenshot:** The Project Aura sign-in page with options to authenticate via GitHub, GitLab, or company SSO.

After successful authentication, you will land on the **Dashboard**.

---

## Step 2: Connect Your First Repository

1. From the Dashboard, click **Add Repository** in the Quick Actions section, or navigate to **Settings > Integrations**.

2. Select your source control provider:
   - GitHub
   - GitLab
   - Bitbucket
   - Azure DevOps

3. Click **Connect** and authorize Aura to access your repositories.

   For GitHub:
   - You will be redirected to GitHub
   - Review the requested permissions
   - Select **Authorize Aura**

   > **Screenshot:** GitHub OAuth authorization screen requesting read access to repositories and metadata for code analysis.

4. After authorization, select the repository you want to onboard:
   - Use the search field to filter repositories
   - Select one or more repositories
   - Click **Add Selected Repositories**

5. Configure scan settings:

   | Setting | Recommended Value | Description |
   |---------|-------------------|-------------|
   | **Default Branch** | `main` or `master` | Branch to scan by default |
   | **Auto-Scan on Push** | Enabled | Trigger scans on new commits |
   | **Scan Schedule** | Daily at 2:00 AM | Regular full scans |

6. Click **Save and Continue**.

---

## Step 3: Run Your First Scan

After connecting a repository, Aura automatically initiates an initial scan. You can also trigger a manual scan:

1. Navigate to **Projects** in the sidebar.

2. Locate your newly connected repository.

3. Click the repository name to open the project view.

4. Click **Run Scan** in the top-right corner.

5. Select the scan type:

   | Scan Type | Duration | Coverage |
   |-----------|----------|----------|
   | **Quick Scan** | 1-5 minutes | High-severity vulnerabilities only |
   | **Full Scan** | 5-30 minutes | Complete codebase analysis |
   | **Dependency Scan** | 1-3 minutes | Third-party libraries only |

6. Click **Start Scan**.

> **Screenshot:** Initial repository scan in progress, with a status bar showing files indexed, embeddings generated, and graph relationships extracted.

The scan progress indicator shows:
- Files analyzed
- Vulnerabilities detected
- Estimated time remaining

---

## Step 4: Review Scan Results

Once the scan completes, review the findings:

1. The project view displays a summary:
   - Total vulnerabilities by severity
   - Files affected
   - Recommended actions

2. Click **View All Vulnerabilities** to see the full list.

3. Each finding includes:
   - **Severity** - Critical, High, Medium, or Low
   - **Type** - SQL Injection, XSS, Outdated Dependency, etc.
   - **Location** - File path and line number
   - **CVE Reference** - If applicable

> **Screenshot:** Scan results dashboard listing detected vulnerabilities grouped by severity (Critical/High/Medium/Low), each with a CVE link and affected file.

---

## Step 5: Generate Your First Patch

Aura can automatically generate patches for many vulnerability types. To initiate patch generation:

1. From the vulnerability list, select a finding you want to remediate.

2. Click **Generate Patch** in the detail panel.

3. Aura's AI agents begin working:
   - **Context Retrieval** - Understanding related code
   - **Patch Generation** - Creating the fix
   - **Sandbox Testing** - Validating the patch

4. Monitor progress in the **Agents** panel (bottom of screen).

   Typical patch generation takes 1-5 minutes depending on complexity.

> **Screenshot:** Patch generation view showing the multi-agent workflow advancing through Plan → Context → Code → Review → Validate phases for the selected vulnerability.

---

## Step 6: Review and Approve the Patch

After sandbox testing completes successfully, the patch enters the approval queue:

1. Navigate to **Approvals** in the sidebar.

2. Locate the pending approval for your patch.

3. The approval view shows:
   - **Original Vulnerability** - Description and risk level
   - **Proposed Patch** - Syntax-highlighted diff view
   - **Sandbox Results** - Test pass/fail status
   - **Deployment Plan** - Target branch and merge strategy

   > **Screenshot:** Approval interface displaying the proposed patch as a unified diff, review-agent findings, sandbox test results, and Approve/Reject controls.

4. Review each section carefully:
   - Does the patch address the vulnerability correctly?
   - Do all tests pass?
   - Is the change scope appropriate?

5. Make your decision:
   - **Approve** - Triggers deployment to the target branch
   - **Reject** - Returns the patch with your feedback
   - **Request Changes** - Ask for specific modifications

6. For approval, click **Approve Patch** and confirm.

---

## Step 7: Verify Deployment

After approval, Aura deploys the patch:

1. The patch is committed to your repository as a pull request (or direct commit, based on configuration).

2. Your CI/CD pipeline runs automatically.

3. Monitor deployment status in the **Activity Feed** on the Dashboard.

4. Once merged, the vulnerability status updates to **Patched**.

> **Screenshot:** Deployment confirmation screen showing the merged pull request URL and a summary of remediation activity (vulnerabilities patched, tokens used, tests passed).

---

## What's Next?

Congratulations! You have completed your first vulnerability remediation with Aura. Here are recommended next steps:

### Explore the Dashboard

The Dashboard provides a comprehensive view of your security posture:
- Vulnerability trends over time
- Agent activity and health
- Pending approvals requiring attention
- Recent activity feed

### Configure Notifications

Set up notifications to stay informed:

1. Go to **Settings > Notifications**
2. Configure channels:
   - Email for critical vulnerabilities
   - Slack for approval requests
   - PagerDuty for incidents
3. Set notification preferences by severity level

### Connect Additional Repositories

Expand coverage by connecting more repositories:
1. Navigate to **Settings > Integrations**
2. Add additional repositories
3. Configure branch-specific scan settings

### Review Autonomy Settings

Adjust HITL approval requirements based on your organization's needs:

1. Go to **Settings > Security Policies**
2. Review the autonomy level:
   - **FULL_HITL** - All patches require approval
   - **HITL_CRITICAL** - Only critical/high severity require approval
3. Configure timeout and escalation settings

### Invite Team Members

Add colleagues to your Aura organization:

1. Navigate to **Settings > Team**
2. Click **Invite Member**
3. Enter email addresses
4. Assign roles:
   - **Admin** - Full configuration access
   - **Security Engineer** - Approve patches, view all data
   - **Developer** - View vulnerabilities, limited actions
   - **Viewer** - Read-only access

---

## Troubleshooting

### Repository Not Appearing After Authorization

**Symptom:** Connected source control provider, but repository list is empty.

**Solutions:**
1. Verify you have admin access to the repository
2. Check that the OAuth scope includes repository read access
3. For GitHub organizations, ensure Aura is approved in the organization's OAuth apps
4. Try disconnecting and reconnecting the integration

### Scan Stuck at 0%

**Symptom:** Scan initiated but progress remains at 0%.

**Solutions:**
1. Check the repository size - very large repositories may take longer to initialize
2. Verify the repository is not empty or archive-only
3. Check **Agents** status for any errors
4. Contact support if the issue persists beyond 15 minutes

### Patch Generation Failed

**Symptom:** Error message during patch generation.

**Common Causes:**
- Vulnerability type not supported for auto-patching
- Complex code patterns requiring manual review
- Insufficient context in the codebase

**Solutions:**
1. Review the error message for specific guidance
2. Check the **Agent Logs** for detailed failure information
3. Some vulnerability types require manual remediation

### Approval Timeout

**Symptom:** Patch moved to "Expired" status without action.

**Explanation:** Patches have configurable timeouts (default 24 hours). Expired patches can be:
1. Re-queued for approval
2. Manually reviewed and re-generated

To avoid timeouts, configure notification channels to alert reviewers promptly.

---

## Getting Help

If you encounter issues not covered in this guide:

- **Documentation:** [docs.aenealabs.com](https://docs.aenealabs.com)
- **Support Portal:** [support.aenealabs.com](https://support.aenealabs.com)
- **Email:** support@aenealabs.com
- **In-App Help:** Click the **?** icon in the top navigation

For urgent issues affecting production systems, use the **Critical Support** option in the support portal.

---

## Next Steps

- **[System Requirements](./system-requirements.md)** - Detailed environment prerequisites
- **[Installation Guide](./installation.md)** - Self-hosted deployment instructions
- **[First Project Walkthrough](./first-project.md)** - Comprehensive tutorial with sample repository
