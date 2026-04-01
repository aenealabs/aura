# Repository Onboarding

**Version:** 1.0
**Last Updated:** January 2026
**Time to Complete:** 10-15 minutes

---

## Overview

Repository onboarding connects your source code repositories to Project Aura for security analysis. This guide walks you through the 5-step onboarding wizard, from OAuth authentication to initial scan completion.

After completing this guide, your repositories will be:
- Connected via secure OAuth authentication
- Configured for automated security scanning
- Indexed in Aura's Hybrid GraphRAG system
- Ready for vulnerability detection and remediation

---

## Prerequisites

Before starting repository onboarding, ensure you have:

- [ ] Active Aura account with Admin or Security Engineer role
- [ ] Admin access to the repositories you want to connect
- [ ] OAuth authorization permissions for your GitHub or GitLab organization

> **Note:** If you use GitHub Organizations, you may need organization admin approval for OAuth apps. Contact your GitHub organization owner if you cannot authorize Aura.

---

## Supported Providers

Aura supports the following source control providers:

| Provider | Authentication | Features |
|----------|----------------|----------|
| **GitHub** | OAuth 2.0 | Full API access, webhooks, PR integration |
| **GitLab** | OAuth 2.0 | Repository access, webhooks, MR integration |
| **Manual URL** | Personal Access Token | Basic clone access, manual sync |

For enterprise deployments, GitHub Enterprise Server and GitLab Self-Managed are also supported with additional configuration.

---

## The 5-Step Onboarding Wizard

### Step 1: Connect Repository Provider

The first step establishes a secure connection between Aura and your source control provider.

![Connect Provider Step](../images/placeholder-connect-provider.png)

**To connect via OAuth:**

1. Navigate to **Settings > Integrations** or click **Add Repository** from the Dashboard

2. Select your source control provider:
   - **GitHub** - Recommended for most users
   - **GitLab** - For GitLab.com or self-managed instances
   - **Manual URL** - For unsupported providers or air-gapped environments

3. Click **Connect**

4. You will be redirected to your provider's authorization page

5. Review the requested permissions:

   **GitHub OAuth Scopes:**
   | Scope | Purpose |
   |-------|---------|
   | `repo` | Read repository contents for security analysis |
   | `admin:repo_hook` | Create webhooks for incremental updates |

   **GitLab OAuth Scopes:**
   | Scope | Purpose |
   |-------|---------|
   | `read_repository` | Read repository files |
   | `api` | Create webhooks and access project settings |

6. Click **Authorize** to grant access

7. You will be redirected back to Aura

> **Warning:** Never share your OAuth tokens or authorization codes. Aura stores all credentials securely in AWS Secrets Manager and never exposes them to the browser.

**To connect via Manual URL:**

1. Select **Manual URL + Token**

2. Enter the repository clone URL:
   ```
   https://github.com/your-org/your-repo.git
   ```

3. Generate a Personal Access Token from your provider with read access

4. Enter the token in the secure input field

5. Click **Verify Connection**

---

### Step 2: Select Repositories

After successful authentication, Aura retrieves your available repositories.

![Select Repositories Step](../images/placeholder-select-repositories.png)

**To select repositories:**

1. Browse the repository list or use the search field to filter

2. Each repository displays:
   - Repository name (organization/repository)
   - Default branch
   - Primary languages detected
   - Last activity date

3. Click the checkbox next to each repository you want to analyze

4. Selected repositories appear in the summary panel:
   ```
   Selected: 3 repositories
   Estimated ingestion time: ~8 minutes
   ```

5. Click **Continue** when ready

> **Tip:** Start with 1-3 repositories for your initial onboarding. You can add more repositories later through the same workflow.

**Repository Visibility:**

| Visibility | Displayed | Selectable |
|------------|-----------|------------|
| Public | Yes | Yes |
| Private (with access) | Yes | Yes |
| Private (no access) | No | No |
| Archived | Yes | Yes (with warning) |
| Fork | Yes | Optional |

---

### Step 3: Configure Analysis

Configure how Aura analyzes each selected repository.

![Configure Analysis Step](../images/placeholder-configure-analysis.png)

**Configuration options per repository:**

| Setting | Description | Default |
|---------|-------------|---------|
| **Branch** | Branch to analyze and monitor | `main` or `master` |
| **Languages** | Programming languages to include | Auto-detected |
| **Scan Frequency** | How often to run security scans | On push (webhook) |
| **Exclude Patterns** | Files and directories to skip | `tests/*`, `docs/*` |

**To configure a repository:**

1. Select a repository from the list

2. Choose the branch to analyze:
   - Dropdown shows all available branches
   - Default branch is pre-selected

3. Select languages to include:
   - Aura auto-detects languages based on file extensions
   - Uncheck languages you do not want to analyze
   - At least one language must be selected

4. Set the scan frequency:

   | Frequency | Behavior |
   |-----------|----------|
   | **On Push (Webhook)** | Scan triggered automatically when code changes |
   | **Daily** | Full scan runs once per day at configured time |
   | **Weekly** | Full scan runs once per week |
   | **Manual Only** | Scans only run when manually triggered |

5. Configure exclude patterns (optional):
   ```
   tests/*
   docs/*
   *.min.js
   vendor/*
   node_modules/*
   ```

6. Click **Apply to All** to copy settings to all selected repositories (optional)

7. Click **Continue** when configuration is complete

> **Note:** Exclusion patterns use glob syntax. The pattern `**/*.test.js` excludes test files in all directories.

---

### Step 4: Review Configuration

Review your selections before starting the ingestion process.

![Review Step](../images/placeholder-review-step.png)

**Review summary includes:**

```
Provider: GitHub (OAuth)
Account: @your-username

Repositories:
  - org/repo-1 (main) - Python, JavaScript
    Scan: On push via webhook
    Excludes: tests/*, docs/*

  - org/repo-2 (main) - TypeScript
    Scan: On push via webhook
    Excludes: node_modules/*

  - org/repo-3 (develop) - Go
    Scan: Daily at 2:00 AM UTC
    Excludes: vendor/*

Webhooks will be created in your repositories.
```

**To complete the review:**

1. Verify all settings are correct

2. Note the webhook creation notice:

   > **Warning:** Clicking **Start Ingestion** will create webhooks in your repositories. These webhooks send push events to Aura for incremental analysis. You can remove webhooks later from repository settings.

3. Click **Back** to modify any settings

4. Click **Start Ingestion** to begin the onboarding process

---

### Step 5: Ingestion and Completion

Aura clones, parses, and indexes your repositories.

![Completion Step](../images/placeholder-completion-step.png)

**Ingestion phases:**

| Phase | Description | Duration |
|-------|-------------|----------|
| **Clone** | Downloads repository contents | 10-60 seconds |
| **Parse** | Analyzes source files into AST | 30-120 seconds |
| **Index (Graph)** | Builds code knowledge graph in Neptune | 60-180 seconds |
| **Index (Vector)** | Generates embeddings for semantic search | 30-90 seconds |
| **Webhook** | Configures incremental update webhook | 5-10 seconds |

**Progress display:**

```
Ingesting: org/repo-1

Phase 1: Clone              [Complete]
Phase 2: Parse              [Complete]
Phase 3: Index (Graph)      [In Progress] 45%
Phase 4: Index (Vector)     [Pending]
Phase 5: Webhook Setup      [Pending]

Files processed: 234 / 347
Code entities indexed: 1,847
Estimated time remaining: 1m 23s
```

**Upon completion:**

```
Ingestion Complete!

org/repo-1
  Files processed: 347
  Code entities indexed: 2,156
  Embeddings generated: 1,892
  Duration: 2m 34s

org/repo-2
  Files processed: 156
  Code entities indexed: 1,023
  Embeddings generated: 847
  Duration: 1m 12s

[View in Dashboard]    [Onboard More Repos]    [Run Security Scan]
```

---

## Post-Onboarding Actions

After successful onboarding, consider these next steps:

### Run Initial Security Scan

1. Navigate to **Projects** and select your repository

2. Click **Run Scan** and select **Full Scan**

3. Wait for scan completion (typically 5-15 minutes)

4. Review vulnerability findings

See [Vulnerability Remediation](./vulnerability-remediation.md) for detailed guidance.

### Configure Notifications

1. Navigate to **Settings > Notifications**

2. Enable alerts for your connected repositories:
   - Critical vulnerabilities detected
   - Scan completion
   - Ingestion failures

3. Select notification channels (email, Slack, webhooks)

### Verify Webhook Operation

1. Make a small commit to your repository

2. Check Aura's Activity Feed for webhook receipt

3. Verify incremental analysis runs automatically

---

## Managing Connected Repositories

### View Repository Status

1. Navigate to **Projects** in the sidebar

2. The repository list shows:
   - Connection status (Active, Error, Archived)
   - Last scan date
   - Vulnerability count

### Update Repository Settings

1. Click on a repository name

2. Navigate to the **Settings** tab

3. Modify configuration as needed

4. Click **Save Settings**

### Disconnect a Repository

1. Navigate to **Settings > Integrations**

2. Find the repository in the connected list

3. Click the **...** menu and select **Disconnect**

4. Confirm disconnection

> **Warning:** Disconnecting a repository removes it from Aura's analysis but does not delete historical data. Vulnerability records are retained for compliance purposes.

---

## Troubleshooting

### OAuth Authorization Failed

**Symptom:** Error message during OAuth flow or redirect loop.

**Solutions:**
1. Clear browser cookies and cache
2. Verify your GitHub/GitLab account is active
3. Check that third-party OAuth apps are not blocked by your organization
4. For GitHub organizations, verify Aura is approved in OAuth app settings
5. Try using an incognito/private browser window

### Repository Not Appearing After Authorization

**Symptom:** Successfully authorized but repository list is empty.

**Solutions:**
1. Verify you have at least read access to repositories
2. Check that repositories are not archived or disabled
3. For organization repositories, ensure Aura has organization access
4. Disconnect and reconnect the OAuth integration
5. Contact support if the issue persists

### Ingestion Stuck or Failed

**Symptom:** Ingestion progress stops or shows error status.

**Common causes and solutions:**

| Cause | Solution |
|-------|----------|
| Very large repository | Allow extra time; ingestion timeout is 30 minutes |
| Binary files | Add binary extensions to exclude patterns |
| Authentication expired | Reconnect OAuth integration |
| Network timeout | Retry ingestion from repository settings |

### Webhook Not Triggering

**Symptom:** Commits to repository do not trigger automatic scans.

**Solutions:**
1. Verify webhook exists in repository settings (GitHub/GitLab)
2. Check webhook delivery logs for errors
3. Ensure the webhook URL is not blocked by firewall
4. Re-create webhook from Aura repository settings

---

## Security Considerations

### Credential Storage

- OAuth tokens are stored in AWS Secrets Manager
- Tokens are encrypted with customer-managed KMS keys
- Tokens are never exposed to the browser or frontend
- Token refresh happens automatically on the backend

### Data Access

- Aura reads repository contents for security analysis
- Source code is processed in isolated environments
- Code is not stored permanently; only metadata is retained
- You can delete repository data at any time

### Webhook Security

- Webhooks use HMAC signature verification
- Webhook secrets are unique per repository
- Invalid signatures are rejected with 401 response

---

## Related Documentation

- [Getting Started: Quick Start Guide](../getting-started/quick-start.md) - Initial Aura setup
- [Vulnerability Remediation](./vulnerability-remediation.md) - Reviewing and fixing findings
- [Core Concepts: Hybrid GraphRAG](../core-concepts/hybrid-graphrag.md) - How code indexing works
- [API Reference: Repository Endpoints](../../support/api-reference/rest-api.md) - Programmatic repository management
