# Contributing to Project Aura

Thank you for your interest in contributing to Project Aura! This document covers issue management, code contributions, and release workflows.

## Developer Certificate of Origin (DCO)

By contributing to this project, you agree that your contributions are your own original work and that you have the right to submit them under the project's license ([BSL 1.1](LICENSE)). All commits must include a `Signed-off-by` line:

```bash
git commit -s -m "feat: add new validation rule"
```

This adds `Signed-off-by: Your Name <your.email@example.com>` to the commit message, certifying the [Developer Certificate of Origin](https://developercertificate.org/).

---

## Table of Contents

1. [Issue Management](#issue-management)
2. [Issue Lifecycle](#issue-lifecycle)
3. [Issue Templates](#issue-templates)
4. [Pull Request Process](#pull-request-process)
5. [Code Review Standards](#code-review-standards)
6. [Commit Message Format](#commit-message-format)
7. [Release Process](#release-process)

---

## Issue Management

### Tools

| Purpose | Tool | Location |
|---------|------|----------|
| **Active Issues** | GitHub Issues | [github.com/aenealabs/aura/issues](https://github.com/aenealabs/aura/issues) |
| **Project Board** | GitHub Projects | [github.com/aenealabs/aura/projects](https://github.com/aenealabs/aura/projects) |
| **Known Limitations** | KNOWN_ISSUES.md | [KNOWN_ISSUES.md](./KNOWN_ISSUES.md) |
| **Changelog** | CHANGELOG.md | [CHANGELOG.md](./CHANGELOG.md) |

### Local Development Setup

#### Container Runtime (Podman Recommended)

We recommend **Podman** as the container runtime for local development.

**macOS Setup:**
```bash
# Install Podman Desktop from https://podman-desktop.io
# Or via Homebrew:
brew install podman

# Initialize the Podman machine
podman machine init
podman machine start

# Add to PATH (~/.zshrc or ~/.bashrc)
export PATH="/opt/podman/bin:$PATH"

# Verify installation
podman --version
podman run --rm hello-world
```

**Docker Compatibility:** Podman Desktop includes Docker CLI compatibility mode. Once enabled, existing `docker` commands work unchanged. AWS CodeBuild continues using Docker Engine (free for CI/CD).

| Tool | Local Dev | CI/CD (CodeBuild) |
|------|-----------|-------------------|
| Container Runtime | Podman | Docker Engine |
| Compose | `podman compose` | `docker compose` |
| ECR Push/Pull | Works natively | Works natively |

#### GitHub CLI Setup (Recommended)

```bash
# Install GitHub CLI (macOS)
brew install gh

# Authenticate (opens browser for OAuth)
gh auth login

# Verify authentication
gh auth status
```

### Creating Issues via CLI (Preferred Method)

```bash
# Bug report
gh issue create \
  --title "Brief description of the bug" \
  --body "$(cat <<'EOF'
## Summary
[What is broken]

## Steps to Reproduce
1. Step one
2. Step two

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens]

## Environment
- Branch: main
- Python: 3.12
- AWS Region: us-east-1
EOF
)" \
  --label "bug"

# Feature request
gh issue create \
  --title "Add feature X" \
  --body "## Summary\n[Description]\n\n## Acceptance Criteria\n- [ ] Criterion 1" \
  --label "enhancement"

# Test failure
gh issue create \
  --title "Fix failing test: test_name" \
  --body "## Failing Test\n\`tests/path/to/test.py::test_name\`\n\n## Error\n\`\`\`\n[error message]\n\`\`\`" \
  --label "bug,tests"
```

### Issue Labels

| Label | Description | Color |
|-------|-------------|-------|
| `bug` | Something isn't working | `#d73a4a` |
| `enhancement` | New feature or request | `#a2eeef` |
| `tests` | Test-related issues | `#fbca04` |
| `documentation` | Documentation updates | `#0075ca` |
| `security` | Security vulnerabilities | `#b60205` |
| `infrastructure` | AWS/CloudFormation/EKS | `#5319e7` |
| `tech-debt` | Code quality improvements | `#c5def5` |
| `blocked` | Waiting on external dependency | `#e99695` |
| `good-first-issue` | Good for newcomers | `#7057ff` |

### Priority Labels

| Label | Description | Target Response |
|-------|-------------|-----------------|
| `P0-critical` | Production down, security breach | Immediate |
| `P1-high` | Major feature broken, compliance risk | Within days |
| `P2-medium` | Feature degraded, workaround exists | Within a release cycle |
| `P3-low` | Minor issue, nice-to-have | Backlog |

---

## Issue Lifecycle

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Triage    │───▶│  In Progress │───▶│  In Review  │───▶│   Closed    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                  │                  │
       ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Backlog   │    │   Blocked   │    │  Won't Fix  │
└─────────────┘    └─────────────┘    └─────────────┘
```

### Triage Process

1. **Review new issues** - Check [unlabeled issues](https://github.com/aenealabs/aura/issues?q=is%3Aissue+is%3Aopen+no%3Alabel)
2. **Add labels** - Priority, type, and component labels
3. **Assign owner** - Issues are assigned to maintainers or claimed by contributors
4. **Set milestone** - Link to current or future release

### When to Use KNOWN_ISSUES.md vs GitHub Issues

| Scenario | Use |
|----------|-----|
| Active bug requiring fix | GitHub Issue |
| Feature request | GitHub Issue |
| Pre-existing test failure (low priority) | KNOWN_ISSUES.md + GitHub Issue |
| Accepted platform limitation | KNOWN_ISSUES.md only |
| Deprecation warning (no action needed) | KNOWN_ISSUES.md only |
| Security vulnerability | See [SECURITY.md](SECURITY.md) — report privately via email |

---

## Issue Templates

Create these files in `.github/ISSUE_TEMPLATE/`:

### Bug Report Template

```yaml
# .github/ISSUE_TEMPLATE/bug_report.yml
name: Bug Report
description: Report a bug in Project Aura
labels: ["bug"]
body:
  - type: textarea
    id: summary
    attributes:
      label: Summary
      description: Brief description of the bug
    validations:
      required: true
  - type: textarea
    id: steps
    attributes:
      label: Steps to Reproduce
      description: How can we reproduce this?
      placeholder: |
        1. Go to '...'
        2. Click on '...'
        3. See error
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
    validations:
      required: true
  - type: textarea
    id: actual
    attributes:
      label: Actual Behavior
    validations:
      required: true
  - type: dropdown
    id: priority
    attributes:
      label: Priority
      options:
        - P0-critical (Production down)
        - P1-high (Major feature broken)
        - P2-medium (Workaround exists)
        - P3-low (Minor issue)
    validations:
      required: true
```

### Test Failure Template

```yaml
# .github/ISSUE_TEMPLATE/test_failure.yml
name: Test Failure
description: Report a failing test
labels: ["bug", "tests"]
body:
  - type: input
    id: test-path
    attributes:
      label: Failing Test
      description: Full test path
      placeholder: "tests/smoke/test_critical_paths.py::test_name"
    validations:
      required: true
  - type: textarea
    id: error
    attributes:
      label: Error Message
      description: Full error output
      render: shell
    validations:
      required: true
  - type: textarea
    id: root-cause
    attributes:
      label: Root Cause Analysis
      description: Why is this test failing?
  - type: checkboxes
    id: regression
    attributes:
      label: Is this a regression?
      options:
        - label: "Yes, this test was passing before"
        - label: "No, this is a pre-existing failure"
```

---

## Pull Request Process

### Branch Naming

```
feature/ISSUE-123-brief-description
bugfix/ISSUE-456-fix-auth-flow
hotfix/ISSUE-789-security-patch
docs/ISSUE-012-update-readme
```

### PR Checklist

- [ ] Issue linked (`Closes #123`)
- [ ] Tests pass locally (`pytest tests/`)
- [ ] Code formatted (`black src/`)
- [ ] No new linting errors (`flake8 src/`)
- [ ] Commit messages follow [Conventional Commits](#commit-message-format) (changelog auto-generated)
- [ ] Documentation updated (if applicable)

### PR Size Guidelines

| Size | Lines Changed | Review Time |
|------|---------------|-------------|
| XS | < 50 | Same day |
| S | 50-200 | 1 day |
| M | 200-500 | 2 days |
| L | 500-1000 | 3 days |
| XL | > 1000 | Split into smaller PRs |

---

## Code Review Standards

### Required Reviewers

| Change Type | Required Reviewers |
|-------------|-------------------|
| Application code | 1 engineer |
| Infrastructure (CloudFormation) | 1 engineer + platform lead |
| Security-sensitive | 1 engineer + security review |
| API changes | 1 engineer + API owner |

### Review Focus Areas

1. **Correctness** - Does the code do what it claims?
2. **Security** - OWASP Top 10, input validation, secrets handling
3. **Performance** - No N+1 queries, efficient algorithms
4. **Maintainability** - Clear naming, single responsibility
5. **Tests** - Adequate coverage, edge cases

---

## Commit Message Format

Project Aura uses [Conventional Commits](https://www.conventionalcommits.org/) to enable automated changelog generation via [Release Please](https://github.com/googleapis/release-please).

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | Description | Changelog Section |
|------|-------------|-------------------|
| `feat` | New feature | Features |
| `fix` | Bug fix | Bug Fixes |
| `perf` | Performance improvement | Performance Improvements |
| `security` | Security fix | Security |
| `docs` | Documentation only | Documentation |
| `style` | Formatting (hidden) | - |
| `refactor` | Code change (hidden) | - |
| `test` | Adding tests (hidden) | - |
| `chore` | Maintenance (hidden) | - |
| `ci` | CI/CD changes (hidden) | - |
| `build` | Build system (hidden) | - |

### Examples

```bash
# Feature (appears in changelog)
feat(agents): add MetaOrchestrator with dynamic agent spawning

# Bug fix (appears in changelog)
fix(iam): add missing tagging permissions to CodeBuild roles

# Documentation (appears in changelog)
docs: add ADR-018 for dynamic agent spawning

# Chore (hidden from changelog)
chore: update dependencies

# Breaking change (triggers major version bump)
feat(api)!: change authentication to OAuth2

BREAKING CHANGE: API now requires OAuth2 tokens instead of API keys
```

### Scopes (Optional)

| Scope | Description |
|-------|-------------|
| `agents` | Agent implementations |
| `api` | API endpoints |
| `hitl` | Human-in-the-loop workflow |
| `iam` | IAM policies and roles |
| `cicd` | CI/CD pipelines |
| `sandbox` | Sandbox environment |
| `security` | Security features |
| `observability` | Monitoring and logging |
| `infra` | Infrastructure |

### Automated Changelog

When PRs are merged to `main`, Release Please:
1. Analyzes commit messages
2. Creates/updates a release PR with changelog entries
3. When release PR is merged, creates a GitHub release with tags

**No manual CHANGELOG.md updates required!**

> **Historical Changes:** See [archive/changelogs/CHANGELOG-v1.0-v1.2.md](archive/changelogs/CHANGELOG-v1.0-v1.2.md) for changes before automation.

---

## Release Process

### Versioning

Project Aura follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0) - Breaking API changes
- **MINOR** (0.1.0) - New features, backward compatible
- **PATCH** (0.0.1) - Bug fixes, backward compatible

### Release Checklist (Automated via Release Please)

Releases are now automated. When you merge to `main`:

1. **Release Please** analyzes commits and creates a release PR
2. Review the auto-generated changelog in the release PR
3. Merge the release PR to trigger:
   - Version bump in `.release-please-manifest.json`
   - CHANGELOG.md update
   - Git tag creation (e.g., `v1.4.0`)
   - GitHub Release with release notes

**Manual steps (if needed):**

1. [ ] All tests pass on `main`
2. [ ] PROJECT_STATUS.md percentages updated (if significant milestone)
3. [ ] Security scan completed (for major releases)

### Hotfix Process

```bash
# Create hotfix branch from main
git checkout main
git checkout -b hotfix/ISSUE-XXX-description

# Fix, test, commit
git commit -m "fix: description (closes #XXX)"

# PR directly to main (expedited review)
gh pr create --base main --title "HOTFIX: description"
```

---

## Quick Reference

```bash
# View open issues
gh issue list

# View issues assigned to you
gh issue list --assignee @me

# View high-priority bugs
gh issue list --label "bug,P1-high"

# Create issue from test failure
gh issue create --title "Fix: test_name" --label "bug,tests"

# Link PR to issue
gh pr create --title "Fix: description" --body "Closes #123"

# Check CI status
gh pr checks

# View project board
gh project list
```

---

## Questions?

- **Documentation:** See `docs/` directory
- **Architecture:** See `SYSTEM_ARCHITECTURE.md`
- **Design:** See `agent-config/design-workflows/design-principles.md`
