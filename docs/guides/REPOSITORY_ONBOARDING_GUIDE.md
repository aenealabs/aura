# Repository Onboarding Guide

Connect your GitHub or GitLab repositories to Aura for autonomous code intelligence, security scanning, and automated patch generation.

---

## Overview

The Repository Onboarding Wizard guides you through connecting your code repositories to the Aura Platform. Once connected, Aura continuously monitors your code for security vulnerabilities, generates intelligent patches, and helps maintain code quality.

### Why Connect Your Repositories?

| Benefit | Description |
|---------|-------------|
| **Security Scanning** | Automatic vulnerability detection using AI-powered analysis |
| **Code Intelligence** | Deep understanding of your codebase through GraphRAG indexing |
| **Automated Patching** | AI-generated security fixes with human-in-the-loop approval |
| **Continuous Monitoring** | Real-time updates via webhooks when code changes |
| **Compliance Tracking** | Track security posture across all connected repositories |

### Supported Providers

| Provider | Authentication | Features |
|----------|---------------|----------|
| **GitHub** | OAuth 2.0 | Full repository access, webhooks, organization support |
| **GitLab** | OAuth 2.0 | Repository access, webhooks, group support |

---

## Prerequisites

Before starting the onboarding process, ensure you have:

### Account Requirements

- An active Aura Platform account with repository management permissions
- A GitHub or GitLab account with access to the repositories you want to connect

### Repository Access

- **For GitHub**: You need at least read access to repositories you want to connect
- **For GitLab**: You need at least Reporter access or higher

### OAuth Permissions

When you authorize Aura, we request the following permissions:

**GitHub OAuth Scopes:**

| Scope | Purpose |
|-------|---------|
| `repo` | Read access to private repositories for code analysis |
| `admin:repo_hook` | Create webhooks for real-time sync when code changes |

**GitLab OAuth Scopes:**

| Scope | Purpose |
|-------|---------|
| `read_repository` | Read repository files for code analysis |
| `api` | API access required for webhook configuration |

> **Note**: Aura only reads your code for analysis. We never modify your repositories unless you explicitly approve a patch for deployment.

---

## Step-by-Step Walkthrough

The Repository Onboarding Wizard consists of 5 steps. Here is what to expect at each step.

### Step 1: Select Provider

Choose how you want to connect your repositories.

**To begin:**

1. Navigate to **Repositories** in the sidebar
2. Click **Connect Repository**
3. Select your provider: **GitHub** or **GitLab**

```
+------------------------------------------+
|  Connect Your Repository                 |
|                                          |
|  Choose your code hosting provider:      |
|                                          |
|  +----------------+  +----------------+  |
|  |    GitHub      |  |    GitLab      |  |
|  |  (OAuth Login) |  |  (OAuth Login) |  |
|  +----------------+  +----------------+  |
|                                          |
+------------------------------------------+
```

> **Tip**: If you have repositories on multiple providers, you can connect them separately. Complete the wizard for one provider, then start again for the other.

---

### Step 2: Authenticate

Authorize Aura to access your repositories through OAuth.

**What happens:**

1. Click your chosen provider button
2. You will be redirected to GitHub or GitLab
3. Review the permissions Aura is requesting
4. Click **Authorize** to grant access
5. You will be automatically returned to Aura

**On the provider authorization page:**

- Review the scopes being requested
- Ensure you are logged into the correct account
- For organizations: You may need admin approval for organization repositories

```
+------------------------------------------+
|  GitHub Authorization                    |
|                                          |
|  Aura Platform by Aenea Labs             |
|  wants to access your account            |
|                                          |
|  This will allow Aura to:                |
|  - Read repository contents              |
|  - Create webhooks                       |
|                                          |
|  [Cancel]  [Authorize Aura Platform]     |
|                                          |
+------------------------------------------+
```

> **Note**: Your OAuth token is securely stored in AWS Secrets Manager and is never exposed to the browser. Aura uses industry-standard encryption to protect your credentials.

**Troubleshooting Authorization:**

| Issue | Solution |
|-------|----------|
| Authorization page does not load | Check your browser pop-up blocker settings |
| "Access denied" error | Ensure you have the required permissions on the repository |
| Organization access blocked | Contact your organization admin to approve Aura |

---

### Step 3: Select Repositories

Browse and select which repositories to connect.

**What you will see:**

- A searchable list of all repositories you have access to
- Repository name, default branch, languages detected, and last update time
- Checkboxes to select multiple repositories at once

```
+--------------------------------------------------+
|  Select Repositories to Analyze                  |
|                                                  |
|  [Search repositories...]                        |
|                                                  |
|  +----------------------------------------------+|
|  | [x] acme/web-app         main   JS, TS      ||
|  | [x] acme/api-service     main   Python      ||
|  | [ ] acme/mobile-app      develop  Swift     ||
|  | [ ] acme/legacy-system   master   Java      ||
|  +----------------------------------------------+|
|                                                  |
|  Selected: 2 repositories                        |
|  Estimated ingestion time: ~5 minutes            |
|                                                  |
|  [Back]                            [Continue]    |
+--------------------------------------------------+
```

**Tips for selecting repositories:**

- Start with your most critical repositories (production code)
- Consider repository size - larger repositories take longer to index
- You can always add more repositories later

> **Note**: The estimated ingestion time depends on repository size and complexity. Large repositories with many files may take 10-15 minutes for initial indexing.

---

### Step 4: Configure Settings

Customize how Aura analyzes each repository.

**Configuration options:**

| Setting | Options | Description |
|---------|---------|-------------|
| **Branch** | Any branch | Which branch to analyze (default: main/master) |
| **Languages** | Multi-select | Which programming languages to analyze |
| **Sync Frequency** | On push, Daily, Weekly, Manual | How often to re-scan the repository |
| **Exclude Patterns** | Glob patterns | Files or directories to skip |

```
+--------------------------------------------------+
|  Configure Analysis Settings                     |
|                                                  |
|  acme/web-app                                    |
|  +----------------------------------------------+|
|  | Branch:      [main]                          ||
|  |                                              ||
|  | Languages:   [x] JavaScript  [x] TypeScript  ||
|  |              [ ] Python      [ ] Go          ||
|  |                                              ||
|  | Sync:        [On push (webhook)]             ||
|  |                                              ||
|  | Exclude:     [tests/*, node_modules/*, *.min.js]|
|  +----------------------------------------------+|
|                                                  |
|  [ ] Apply same settings to all repositories     |
|                                                  |
|  [Back]                            [Continue]    |
+--------------------------------------------------+
```

**Recommended exclude patterns:**

```
tests/*
test/*
__tests__/*
node_modules/*
vendor/*
*.min.js
*.min.css
dist/*
build/*
coverage/*
```

**Sync frequency recommendations:**

| Frequency | Best For |
|-----------|----------|
| **On push (webhook)** | Active development repositories |
| **Daily** | Moderate activity repositories |
| **Weekly** | Stable or low-activity repositories |
| **Manual** | Repositories you want to scan on-demand |

> **Tip**: Use "On push" sync for repositories with active development. This ensures Aura always has the latest code analyzed and can detect vulnerabilities in new commits immediately.

---

### Step 5: Review and Connect

Review your configuration before starting the connection process.

**The review page shows:**

- Provider and account information
- List of selected repositories with settings
- Webhook configuration notice

```
+--------------------------------------------------+
|  Review Your Configuration                       |
|                                                  |
|  Provider:  GitHub                               |
|  Account:   @your-username                       |
|                                                  |
|  Repositories:                                   |
|  - acme/web-app (main)                          |
|    Languages: JavaScript, TypeScript             |
|    Sync: On push                                 |
|                                                  |
|  - acme/api-service (main)                      |
|    Languages: Python                             |
|    Sync: On push                                 |
|                                                  |
|  [!] Webhooks will be created in these repos     |
|                                                  |
|  [Back]                     [Start Connection]   |
+--------------------------------------------------+
```

**When you click "Start Connection":**

1. Aura creates webhook configurations in your repositories
2. The initial code ingestion begins
3. A progress indicator shows the indexing status

> **Note**: Creating webhooks requires write access to repository settings. If you see an error, ensure your OAuth authorization includes the webhook scope.

---

## After Connection

### Initial Ingestion

Once you click "Start Connection", Aura begins the initial ingestion process:

```
+--------------------------------------------------+
|  Connecting Repositories...                      |
|                                                  |
|  acme/web-app                                    |
|  [=========>                    ] 45%            |
|  Processing: src/components/...                  |
|                                                  |
|  acme/api-service                               |
|  [Queued - waiting...]                          |
|                                                  |
+--------------------------------------------------+
```

**What happens during ingestion:**

1. **Cloning**: Repository code is securely cloned
2. **Parsing**: Source files are analyzed and parsed into an AST
3. **Indexing**: Code entities are indexed to the graph database (Neptune)
4. **Embedding**: Semantic embeddings are generated for intelligent search
5. **Cleanup**: Temporary files are removed

### Completion Summary

When ingestion completes, you will see a summary:

```
+--------------------------------------------------+
|  Connection Complete!                            |
|                                                  |
|  [OK] acme/web-app                              |
|       Files processed: 347                       |
|       Code entities indexed: 1,234               |
|       Duration: 2m 34s                           |
|                                                  |
|  [OK] acme/api-service                          |
|       Files processed: 156                       |
|       Code entities indexed: 567                 |
|       Duration: 1m 12s                           |
|                                                  |
|  [View Dashboard]      [Connect More Repos]      |
+--------------------------------------------------+
```

### Viewing Repository Status

After connection, you can monitor your repositories from the **Repositories** dashboard:

1. Navigate to **Repositories** in the sidebar
2. View all connected repositories in a table or card view
3. Each repository shows:
   - Connection status
   - Last sync time
   - Vulnerability count
   - Ingestion status

**Repository Status Indicators:**

| Status | Icon | Meaning |
|--------|------|---------|
| **Active** | Green circle | Repository is connected and syncing |
| **Syncing** | Spinning arrow | Ingestion or sync in progress |
| **Pending** | Yellow circle | Awaiting initial ingestion |
| **Error** | Red circle | Connection issue - click for details |

### Understanding Ingestion Status

Each repository has an ingestion status that shows the current state of code analysis:

| Status | Description |
|--------|-------------|
| **pending** | Repository added, awaiting initial scan |
| **in_progress** | Code is currently being analyzed |
| **completed** | Analysis complete, ready for scanning |
| **failed** | Ingestion encountered an error |

> **Note**: If ingestion fails, click the repository to see the error details and retry options.

### How Webhook Sync Works

For repositories configured with "On push" sync:

1. When code is pushed to your repository, GitHub/GitLab sends a webhook to Aura
2. Aura processes only the changed files (incremental update)
3. New code entities are indexed within minutes
4. You receive vulnerability alerts for any issues found in new code

---

## Managing Connected Repositories

### Viewing Connected Repositories

1. Navigate to **Repositories** in the sidebar
2. See all connected repositories with their current status
3. Use filters to sort by provider, status, or last sync time

### Updating Repository Settings

To modify settings for a connected repository:

1. Click on the repository card or row
2. Click **Settings** (gear icon)
3. Modify the settings:
   - Change the branch being monitored
   - Update language filters
   - Adjust sync frequency
   - Modify exclude patterns
4. Click **Save Changes**

### Triggering a Manual Re-sync

To manually re-sync a repository:

1. Navigate to the repository details page
2. Click **Sync Now** button
3. Aura will perform a full re-scan of the repository

> **Tip**: Use manual re-sync after major refactoring or when you want to ensure the latest code is analyzed.

### Disconnecting a Repository

To remove a repository from Aura:

1. Navigate to the repository details page
2. Click **Settings** (gear icon)
3. Scroll to the bottom and click **Disconnect Repository**
4. Confirm the disconnection

**What happens when you disconnect:**

- Webhooks are removed from your repository
- Historical vulnerability data is retained for 30 days
- You can reconnect the repository at any time

### Revoking OAuth Authorization

To completely remove Aura's access to your GitHub or GitLab account:

**For GitHub:**

1. Go to GitHub Settings > Applications > Authorized OAuth Apps
2. Find "Aura Platform" and click **Revoke**

**For GitLab:**

1. Go to GitLab Preferences > Applications
2. Find "Aura Platform" in Authorized applications
3. Click **Revoke**

> **Warning**: Revoking OAuth will disconnect ALL repositories from that provider. You will need to re-authorize to reconnect.

---

## Troubleshooting

### Common Issues and Solutions

#### OAuth Authorization Fails

| Symptom | Cause | Solution |
|---------|-------|----------|
| Redirect loop | Browser cookies blocked | Enable cookies for the provider domain |
| "Access denied" | Insufficient permissions | Request access from repository owner |
| Blank page after auth | Pop-up blocked | Allow pop-ups from Aura |
| Organization access denied | Org has restricted OAuth | Contact your org admin |

**To retry authorization:**

1. Go to **Repositories** > **Settings**
2. Click **Re-authorize** next to the provider
3. Complete the OAuth flow again

#### Repository Not Appearing in List

- **Private repositories**: Ensure your OAuth token has `repo` scope
- **Organization repositories**: You may need org admin approval
- **Recently created**: Wait 1-2 minutes and refresh the page

#### Ingestion Stuck or Failed

1. Check the error message on the repository card
2. Common causes:
   - Repository too large (>1GB)
   - Branch does not exist
   - Network timeout
3. Click **Retry Ingestion** to try again

#### Webhooks Not Working

1. Verify the webhook exists in your repository settings
2. Check webhook delivery logs in GitHub/GitLab
3. Ensure Aura's webhook URL is accessible
4. Click **Repair Webhook** in repository settings

### Getting Help

If you encounter issues not covered here:

1. Use the **Chat Assistant** (bottom-right icon) to describe your issue
2. Check the **Troubleshooting** guide for general platform issues
3. Contact your Aura administrator for account-specific problems

---

## Security and Privacy

### Data Access and Storage

| What We Access | How It Is Used | Retention |
|----------------|----------------|-----------|
| Source code | Parsed and indexed for analysis | As long as repository is connected |
| Commit metadata | Track changes and update indexes | As long as repository is connected |
| OAuth tokens | Authenticate API calls | Until revoked (encrypted at rest) |

### Token Security

Your OAuth credentials are protected with multiple layers of security:

- **Encryption**: Tokens are encrypted using AWS KMS customer-managed keys
- **Isolation**: Each user's tokens are stored separately
- **No Client Exposure**: Tokens never leave the server - your browser only sees session IDs
- **Automatic Refresh**: Tokens are refreshed automatically before expiry
- **TTL Expiry**: Session references expire after inactivity

### Data Retention

- **Active repositories**: Data retained as long as repository is connected
- **Disconnected repositories**: Vulnerability history retained for 30 days
- **Deleted accounts**: All data permanently deleted within 7 days

### Compliance

The repository onboarding system is designed to meet enterprise compliance requirements:

- **CMMC Level 2**: Server-side credential storage, audit logging
- **SOC 2 Type II**: Access controls, encryption, monitoring
- **GDPR**: Data minimization, right to deletion

---

## Quick Reference

### Navigation Paths

| Action | Navigation |
|--------|------------|
| Connect new repository | Repositories > Connect Repository |
| View repository details | Repositories > Click repository card |
| Update settings | Repository Details > Settings |
| Disconnect repository | Repository Details > Settings > Disconnect |
| Re-authorize OAuth | Repositories > Settings > Re-authorize |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + K` | Quick search repositories |
| `Ctrl/Cmd + N` | Open Connect Repository wizard |
| `Escape` | Close wizard/modal |

---

## Next Steps

Now that your repositories are connected:

1. **Review Vulnerabilities**: Navigate to **Vulnerabilities** to see detected issues
2. **Configure Alerts**: Set up notifications for new findings
3. **Enable Auto-Patching**: Configure autonomous patch generation
4. **Set Up Teams**: Assign repositories to teams for better organization

### Related Guides

| Guide | Description |
|-------|-------------|
| [Getting Started](./getting-started.md) | Platform overview and basics |
| [Security and Compliance](./security-compliance.md) | HITL workflows and compliance |
| [Integrations](./integrations.md) | External tool connections |
| [Troubleshooting](./troubleshooting.md) | Common issues and solutions |

---

## Glossary

| Term | Definition |
|------|------------|
| **Ingestion** | The process of cloning, parsing, and indexing repository code |
| **OAuth** | Open Authorization - secure delegated access protocol |
| **Webhook** | HTTP callback that notifies Aura when code changes |
| **GraphRAG** | Graph-based Retrieval-Augmented Generation for code understanding |
| **AST** | Abstract Syntax Tree - structured representation of source code |

---

**Last Updated:** December 2025

**Version:** Aura Platform v1.3
