# Release Please - Automated Changelog & Release Management

> **Document Version:** 1.0
> **Last Updated:** December 4, 2025
> **Status:** Active
> **Related Documents:** [CONTRIBUTING.md](../CONTRIBUTING.md) | [CICD_SETUP_GUIDE.md](./CICD_SETUP_GUIDE.md)

---

## Table of Contents

1. [Overview](#overview)
2. [How It Works](#how-it-works)
3. [Conventional Commits Reference](#conventional-commits-reference)
4. [Commit Examples](#commit-examples)
5. [Configuration Files](#configuration-files)
6. [Workflow Diagram](#workflow-diagram)
7. [Release Process](#release-process)
8. [Troubleshooting](#troubleshooting)
9. [Historical Changelog Archive](#historical-changelog-archive)

---

## Overview

Project Aura uses [Release Please](https://github.com/googleapis/release-please) by Google to automate:

- **Changelog generation** from commit messages
- **Version bumping** following [Semantic Versioning](https://semver.org/)
- **GitHub Release creation** with release notes
- **Git tagging** (e.g., `v1.4.0`)

### Benefits

| Aspect | Manual Process | With Release Please |
|--------|----------------|---------------------|
| **Changelog updates** | 5-10 min/PR | Automatic |
| **Version management** | Error-prone | Consistent |
| **Release notes** | Copy/paste | Auto-generated |
| **Audit trail** | Manual tracking | Git-native |
| **Team scalability** | Merge conflicts | Zero conflicts |

### Cost

- **Software:** Free (Apache 2.0 license)
- **GitHub Actions:** ~30 seconds per run (within free tier)
- **Monthly cost:** $0

---

## How It Works

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Developer Workflow                            │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  1. Developer creates PR with conventional commit messages          │
│     Example: feat(agents): add new security scanner                 │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. PR is reviewed and merged to `main` branch                      │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. Release Please GitHub Action runs automatically                  │
│     - Analyzes all commits since last release                       │
│     - Determines version bump (major/minor/patch)                   │
│     - Creates or updates a "Release PR"                             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. Release PR contains:                                            │
│     - Updated CHANGELOG.md                                          │
│     - Version bump in .release-please-manifest.json                 │
│     - Release notes preview                                         │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  5. When Release PR is merged:                                      │
│     - Git tag created (e.g., v1.4.0)                               │
│     - GitHub Release published                                      │
│     - Changelog finalized                                           │
└─────────────────────────────────────────────────────────────────────┘
```

### Version Bump Rules

| Commit Type | Version Bump | Example |
|-------------|--------------|---------|
| `feat:` | MINOR (0.X.0) | `feat: add dashboard` → 1.3.0 → 1.4.0 |
| `fix:` | PATCH (0.0.X) | `fix: resolve timeout` → 1.3.0 → 1.3.1 |
| `feat!:` or `BREAKING CHANGE:` | MAJOR (X.0.0) | `feat!: new API` → 1.3.0 → 2.0.0 |
| `docs:`, `chore:`, etc. | No bump | Only appears in changelog |

---

## Conventional Commits Reference

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Commit Types

| Type | Description | Appears in Changelog | Changelog Section |
|------|-------------|---------------------|-------------------|
| `feat` | New feature | ✅ Yes | **Features** |
| `fix` | Bug fix | ✅ Yes | **Bug Fixes** |
| `perf` | Performance improvement | ✅ Yes | **Performance Improvements** |
| `security` | Security fix | ✅ Yes | **Security** |
| `revert` | Revert previous commit | ✅ Yes | **Reverts** |
| `docs` | Documentation only | ✅ Yes | **Documentation** |
| `style` | Formatting, whitespace | ❌ Hidden | - |
| `refactor` | Code restructuring | ❌ Hidden | - |
| `test` | Adding/updating tests | ❌ Hidden | - |
| `chore` | Maintenance tasks | ❌ Hidden | - |
| `build` | Build system changes | ❌ Hidden | - |
| `ci` | CI/CD changes | ❌ Hidden | - |

### Scopes (Optional but Recommended)

| Scope | Description | Example |
|-------|-------------|---------|
| `agents` | Agent implementations | `feat(agents): add MetaOrchestrator` |
| `api` | API endpoints | `fix(api): resolve auth timeout` |
| `hitl` | Human-in-the-loop workflow | `feat(hitl): add email notifications` |
| `iam` | IAM policies and roles | `fix(iam): add missing permissions` |
| `cicd` | CI/CD pipelines | `feat(cicd): implement Release Please` |
| `sandbox` | Sandbox environment | `fix(sandbox): resolve isolation issue` |
| `security` | Security features | `security(auth): patch JWT vulnerability` |
| `observability` | Monitoring and logging | `feat(observability): add Container Insights` |
| `infra` | Infrastructure | `fix(infra): correct VPC endpoint config` |
| `db` | Database (Neptune, OpenSearch, DynamoDB) | `perf(db): optimize Neptune queries` |

---

## Commit Examples

### Features (Appear in Changelog)

```bash
# Simple feature
git commit -m "feat: add user authentication dashboard"

# Feature with scope
git commit -m "feat(agents): add MetaOrchestrator with dynamic agent spawning"

# Feature with body
git commit -m "feat(hitl): add SNS email notifications for approvals

Subscribers receive email when:
- New approval request is created
- Approval is about to expire (75% of timeout)
- Request is escalated to backup reviewer"

# Feature with issue reference
git commit -m "feat(api): implement batch ingestion endpoint

Closes #123"
```

### Bug Fixes (Appear in Changelog)

```bash
# Simple fix
git commit -m "fix: resolve memory leak in context retrieval"

# Fix with scope
git commit -m "fix(iam): add missing tagging permissions to CodeBuild roles"

# Fix with detailed body
git commit -m "fix(sandbox): correct VPC endpoint security group rules

Added private subnet CIDRs to ingress rules:
- 10.0.3.0/24 (private-subnet-1)
- 10.0.4.0/24 (private-subnet-2)

ECS Fargate tasks can now access ECR via VPC endpoints."
```

### Breaking Changes (Trigger MAJOR Version)

```bash
# Using exclamation mark
git commit -m "feat(api)!: change authentication from API keys to OAuth2"

# Using BREAKING CHANGE footer
git commit -m "feat(api): migrate to OAuth2 authentication

BREAKING CHANGE: API keys are no longer supported. All clients must
migrate to OAuth2 tokens before upgrading to this version."

# Combining both
git commit -m "refactor(db)!: migrate from DynamoDB to Neptune for user data

BREAKING CHANGE: User data schema has changed. Run migration script
before deploying: ./scripts/migrate-users-to-neptune.sh"
```

### Documentation (Appear in Changelog)

```bash
git commit -m "docs: add ADR-018 for MetaOrchestrator architecture"

git commit -m "docs(api): update authentication guide for OAuth2"

git commit -m "docs: standardize CloudFormation template descriptions"
```

### Hidden from Changelog (But Still Tracked)

```bash
# Chores - dependency updates, config changes
git commit -m "chore: update boto3 to 1.34.0"
git commit -m "chore(deps): bump pytest from 7.4.0 to 8.0.0"

# Tests
git commit -m "test(agents): add unit tests for MetaOrchestrator"
git commit -m "test: increase coverage for sandbox service"

# Refactoring
git commit -m "refactor(api): simplify authentication middleware"
git commit -m "refactor: extract common utilities to shared module"

# Style
git commit -m "style: format code with black"
git commit -m "style: fix linting warnings"

# CI/CD
git commit -m "ci: add security scanning to PR workflow"
git commit -m "ci: optimize GitHub Actions cache"

# Build
git commit -m "build: update Dockerfile base image"
git commit -m "build: configure multi-platform builds"
```

### Multi-Line Commit Messages

```bash
# Using heredoc for complex commits
git commit -m "$(cat <<'EOF'
feat(security): implement AWS Security Agent capability parity

Closed all 4 capability gaps identified in competitive analysis:

1. GitHub PR Integration - Auto-create remediation PRs
2. Design Document Security Review - Proactive architecture analysis
3. Active Penetration Testing - Multi-step attack chains in sandbox
4. Business Logic Vulnerability Detection - Context-aware IDOR/race detection

Added 179 new tests (all passing).
Extended AgentCapability enum from 12 to 16 capabilities.

Refs: ADR-019
EOF
)"
```

---

## Configuration Files

### `.github/workflows/release-please.yml`

The GitHub Action that runs Release Please:

```yaml
name: Release Please

on:
  push:
    branches:
      - main

permissions:
  contents: write
  pull-requests: write

jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - name: Release Please Action
        uses: googleapis/release-please-action@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json
```

### `release-please-config.json`

Configuration for changelog sections and versioning:

```json
{
  "release-type": "python",
  "packages": {
    ".": {
      "component": "project-aura",
      "changelog-path": "CHANGELOG.md"
    }
  },
  "changelog-sections": [
    {"type": "feat", "section": "Features"},
    {"type": "fix", "section": "Bug Fixes"},
    {"type": "perf", "section": "Performance Improvements"},
    {"type": "security", "section": "Security"},
    {"type": "docs", "section": "Documentation"},
    {"type": "chore", "hidden": true}
  ]
}
```

### `.release-please-manifest.json`

Tracks the current version:

```json
{
  ".": "1.3.0"
}
```

---

## Workflow Diagram

```
                    ┌──────────────────────────────────────┐
                    │         DEVELOPER WORKFLOW           │
                    └──────────────────────────────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
            ▼                         ▼                         ▼
    ┌───────────────┐         ┌───────────────┐         ┌───────────────┐
    │ feat: feature │         │ fix: bug fix  │         │ docs: update  │
    └───────────────┘         └───────────────┘         └───────────────┘
            │                         │                         │
            └─────────────────────────┼─────────────────────────┘
                                      │
                                      ▼
                    ┌──────────────────────────────────────┐
                    │         MERGE TO MAIN BRANCH         │
                    └──────────────────────────────────────┘
                                      │
                                      ▼
                    ┌──────────────────────────────────────┐
                    │     RELEASE PLEASE GITHUB ACTION     │
                    │                                      │
                    │  1. Parse commits since last tag     │
                    │  2. Determine version bump           │
                    │  3. Generate changelog entries       │
                    │  4. Create/update Release PR         │
                    └──────────────────────────────────────┘
                                      │
                                      ▼
                    ┌──────────────────────────────────────┐
                    │           RELEASE PR CREATED         │
                    │                                      │
                    │  Title: "chore: release v1.4.0"      │
                    │  Contains:                           │
                    │  - CHANGELOG.md updates              │
                    │  - Version bump                      │
                    │  - Release notes preview             │
                    └──────────────────────────────────────┘
                                      │
                                      ▼
                    ┌──────────────────────────────────────┐
                    │         MERGE RELEASE PR             │
                    └──────────────────────────────────────┘
                                      │
                                      ▼
                    ┌──────────────────────────────────────┐
                    │         RELEASE PUBLISHED            │
                    │                                      │
                    │  - Git tag: v1.4.0                   │
                    │  - GitHub Release created            │
                    │  - Release notes published           │
                    └──────────────────────────────────────┘
```

---

## Release Process

### Automatic Releases (Default)

1. **Develop features** using conventional commits
2. **Merge PRs** to `main` branch
3. **Release Please creates Release PR** automatically
4. **Review** the auto-generated changelog
5. **Merge Release PR** to publish release

### Manual Release (If Needed)

```bash
# Check current version
cat .release-please-manifest.json

# View pending changes
git log $(git describe --tags --abbrev=0)..HEAD --oneline

# Force a release (rarely needed)
# Edit .release-please-manifest.json manually and push
```

### Viewing Release History

```bash
# List all releases
gh release list

# View specific release
gh release view v1.3.0

# Download release assets
gh release download v1.3.0
```

---

## Troubleshooting

### Release PR Not Created

**Symptoms:** Merged commits but no Release PR appears

**Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| No releasable commits | Use `feat:`, `fix:`, `docs:` prefixes |
| All commits hidden | Check commit types (avoid only `chore:`, `test:`) |
| Workflow not triggered | Verify push to `main` branch |
| Permissions issue | Check `GITHUB_TOKEN` permissions |

### Wrong Version Bump

**Symptoms:** Expected minor bump but got patch

**Solution:** Ensure commit follows format exactly:
```bash
# Wrong (no space after colon)
git commit -m "feat:add feature"

# Correct
git commit -m "feat: add feature"
```

### Changelog Missing Entries

**Symptoms:** Commit not appearing in changelog

**Check:**
1. Commit type is in visible list (`feat`, `fix`, `docs`, `perf`, `security`)
2. Commit was merged to `main` (not squashed incorrectly)
3. Commit message follows conventional format

### Viewing Release Please Logs

```bash
# View workflow runs
gh run list --workflow=release-please.yml

# View specific run logs
gh run view <run-id> --log
```

---

## Historical Changelog Archive

Changes from before Release Please automation (v1.0.0 through v1.2.x) are preserved in:

**Location:** [`archive/changelogs/CHANGELOG-v1.0-v1.2.md`](../archive/changelogs/CHANGELOG-v1.0-v1.2.md)

**Coverage:** November 3, 2025 - December 4, 2025

**Size:** ~1,557 lines of detailed change history

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CONVENTIONAL COMMITS CHEAT SHEET                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  VISIBLE IN CHANGELOG:                                              │
│  ────────────────────                                               │
│  feat(scope): description      → Features section                   │
│  fix(scope): description       → Bug Fixes section                  │
│  docs(scope): description      → Documentation section              │
│  perf(scope): description      → Performance section                │
│  security(scope): description  → Security section                   │
│                                                                     │
│  HIDDEN FROM CHANGELOG:                                             │
│  ─────────────────────                                              │
│  chore: description            → Maintenance                        │
│  test: description             → Tests                              │
│  refactor: description         → Code changes                       │
│  style: description            → Formatting                         │
│  ci: description               → CI/CD                              │
│  build: description            → Build system                       │
│                                                                     │
│  BREAKING CHANGES (triggers MAJOR version):                         │
│  ──────────────────────────────────────────                         │
│  feat!: description            → Exclamation mark                   │
│  fix!: description             → Before colon                       │
│                                                                     │
│  BREAKING CHANGE: explanation  → Footer (multi-line)                │
│                                                                     │
│  SCOPES (optional):                                                 │
│  ─────────────────                                                  │
│  agents, api, hitl, iam, cicd, sandbox, security,                  │
│  observability, infra, db                                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Related Documentation

- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines and commit format
- [CICD_SETUP_GUIDE.md](./CICD_SETUP_GUIDE.md) - CI/CD pipeline documentation
- [CHANGELOG.md](../CHANGELOG.md) - Auto-generated changelog
- [archive/changelogs/](../archive/changelogs/) - Historical changelog archives

---

*This document will be incorporated into comprehensive platform documentation in a future documentation consolidation effort.*
