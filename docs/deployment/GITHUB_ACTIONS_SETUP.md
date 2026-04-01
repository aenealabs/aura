# GitHub Actions Setup Guide

**Project Aura - Automated Code Quality and Documentation Checks**

This guide explains the GitHub Actions workflows configured for Project Aura to ensure code quality, security, and compliance from Day 1.

---

## Overview

Project Aura uses GitHub Actions for automated CI/CD workflows to:

1. **Enforce markdown documentation standards** (auto-fix on PR/push)
2. **Run Python code quality checks** (Black, Flake8, MyPy)
3. **Execute security scans** (Bandit, Trivy)
4. **Run automated tests** (pytest with coverage)

> **Note:** CloudFormation linting (cfn-lint) runs in AWS CodeBuild at deploy time, not in GitHub Actions.

**Why GitHub Actions?**
- ✅ **Compliance-ready:** Auditable logs for CMMC Level 3, NIST 800-53, SOX
- ✅ **Enforced:** Cannot bypass (unlike git hooks)
- ✅ **Centralized:** One configuration for entire team
- ✅ **Auto-fix:** Automatically commits fixes to PRs
- ✅ **Cost-effective:** 2,000 free minutes/month on public repos, 3,000 on private repos with GitHub Pro

---

## Workflows

### 1. Markdown Linting (`lint-markdown.yml`)

**Triggers:**
- Pull requests that modify `*.md` files
- Pushes to `main` or `develop` branches
- Manual trigger via workflow_dispatch

**What it does:**
1. Detects changed markdown files
2. Runs `markdownlint-cli2` to check compliance
3. **Auto-fixes** issues (MD022, MD029, MD032, MD036)
4. Commits fixes back to the PR/branch
5. Comments on PR with summary of fixes

**Fixed Issues:**
- **MD022:** Headers surrounded by blank lines
- **MD029:** Ordered list numbering consistency
- **MD032:** Lists surrounded by blank lines
- **MD036:** Emphasis used instead of heading

**Example Output:**
```
✅ Markdown files auto-fixed and committed

Changes committed:
- docs: auto-fix markdown linting issues (MD022, MD029, MD032, MD036)
```

---

### 2. Code Quality Checks (`code-quality.yml`)

**Triggers:**
- Pull requests to `main` or `develop`
- Pushes to `main` or `develop`
- Manual trigger

**Jobs:**

#### **Python Linting**
- **Black:** Code formatting check (PEP 8 compliance)
- **Flake8:** Linting for code quality issues
- **MyPy:** Type checking (optional, continues on error)
- **Bandit:** Security vulnerability scanning

#### **Python Tests**
- **pytest:** Runs all tests in `tests/` directory
- **Coverage:** Generates code coverage reports (HTML + XML)
- **Codecov:** Uploads coverage to Codecov (optional)

#### **CloudFormation Linting** *(Moved to CodeBuild)*
- cfn-lint now runs in AWS CodeBuild at deploy time
- See `docs/deployment/CICD_SETUP_GUIDE.md` for details

#### **Security Scanning**
- **Trivy:** Scans for vulnerabilities in dependencies, container images, IaC
- **SARIF Upload:** Uploads results to GitHub Security tab for review

**Artifacts:**
- Bandit security report (JSON)
- Coverage report (HTML)
- Trivy security scan results (SARIF)

---

## Setup Instructions

### 1. No Setup Required (Workflows Auto-Run)

The workflows are **already configured** and will run automatically on:
- Pull requests
- Pushes to `main`/`develop` branches

### 2. Optional: VS Code Extensions (Recommended)

Install recommended VS Code extensions for local auto-fixing:

```bash
code --install-extension davidanson.vscode-markdownlint
code --install-extension ms-python.python
code --install-extension ms-python.black-formatter
```

Or install all recommended extensions:
1. Open VS Code
2. View → Extensions
3. Filter: `@recommended`
4. Click "Install Workspace Recommended Extensions"

**With these extensions:**
- Markdown auto-fixes on save
- Python auto-formats with Black on save
- Real-time linting errors shown in editor

### 3. Optional: Local Manual Linting

You can run the same checks locally before pushing:

**Markdown:**
```bash
# Install markdownlint-cli2 globally
npm install -g markdownlint-cli2

# Lint all markdown files
markdownlint-cli2 "**/*.md"

# Auto-fix issues
markdownlint-cli2 --fix "**/*.md"

# Or use the script
./scripts/lint-markdown.sh --fix
```

**Python:**
```bash
# Install tools
pip install black flake8 mypy bandit pytest pytest-cov

# Format code
black src/ tests/

# Lint code
flake8 src/ tests/ --max-line-length=120

# Type check
mypy src/

# Security scan
bandit -r src/

# Run tests
pytest tests/ -v --cov=src
```

**CloudFormation:**
```bash
# Install cfn-lint
pip install cfn-lint

# Lint templates
cfn-lint deploy/cloudformation/*.yaml
```

---

## Workflow Permissions

The workflows require the following GitHub permissions (already configured):

```yaml
permissions:
  contents: write          # To commit auto-fixes
  pull-requests: write     # To comment on PRs
  security-events: write   # To upload security scan results
```

**Note:** These permissions are scoped to the `GITHUB_TOKEN` (automatic, no secrets needed).

---

## Branch Protection Rules (Recommended)

To enforce workflows before merging, configure branch protection:

1. **Go to:** GitHub → Settings → Branches → Branch protection rules
2. **Add rule for:** `main` and `develop`
3. **Enable:**
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - Select required checks:
     - `Lint Markdown Files`
     - `Python Linting`
     - `Python Tests`
     - `CloudFormation Linting`
     - `Security Scanning`

**Result:** PRs cannot merge until all checks pass.

---

## Compliance & Audit Trail

### CMMC Level 3 / NIST 800-53 Compliance

GitHub Actions provides audit trail for compliance:

**SA-11: Developer Security Testing**
- ✅ Automated security scanning (Bandit, Trivy)
- ✅ Logs retained in GitHub Actions history
- ✅ SARIF results uploaded to GitHub Security tab

**CM-3: Configuration Change Control**
- ✅ All code changes go through PR review
- ✅ Automated checks enforce quality standards
- ✅ Audit trail shows who approved/merged

**AU-12: Audit Generation**
- ✅ All workflow runs logged with timestamps
- ✅ Can export logs to CloudWatch for 7-year retention (future)

### SOX Compliance

- ✅ Change management controls (required status checks)
- ✅ Segregation of duties (reviewers cannot approve own PRs)
- ✅ Audit trail (GitHub Actions logs)

---

## Troubleshooting

### Workflow Fails: "No markdownlint-cli2 command found"

**Cause:** Node.js setup failed.

**Fix:** Workflow installs it automatically. If it fails, check GitHub Actions logs.

### Workflow Commits Fixes, But PR Still Shows Errors

**Cause:** Stale branch - need to pull latest changes.

**Fix:**
```bash
git pull origin <branch-name>
```

### Auto-Fixes Not Committed

**Cause:** Insufficient permissions.

**Fix:** Ensure `contents: write` permission is set in workflow (already configured).

### Security Scan False Positives

**Cause:** Trivy flags low-severity issues in dependencies.

**Fix:** Review results in GitHub Security tab → Dismiss false positives with justification.

---

## Cost Analysis

### GitHub Actions Free Tier

- **Public Repositories:** 2,000 minutes/month (free)
- **Private Repositories (Free plan):** 2,000 minutes/month
- **Private Repositories (Pro plan):** 3,000 minutes/month

### Estimated Usage for Project Aura

| Workflow | Duration | Runs/Day | Monthly Minutes |
|----------|----------|----------|-----------------|
| Markdown Linting | 1 min | 10 | 300 |
| Code Quality | 5 min | 10 | 1,500 |
| **Total** | | | **1,800 min/month** |

**Cost:** $0 (within free tier)

**Production Strategy:**
- Continue using GitHub-hosted runners with optimizations (30-40% minute reduction)
- Concurrency limits cancel stale runs automatically
- Built-in pip caching (`cache: 'pip'`) speeds up dependency installation
- Smart test selection (`pytest --lf --ff --maxfail=5`) fails fast on errors
- Estimated: Stay within free tier or minimal overage (<$10/month)

---

## Next Steps

1. ✅ **Push workflows to GitHub** (already done)
2. ✅ **Enable branch protection rules** (recommended)
3. ✅ **Install VS Code extensions** (optional, for local development)
4. 🔲 **Test workflows** - Open a PR and watch auto-fixes in action
5. 🔲 **Review Security tab** - Check Trivy scan results

---

## Additional Resources

- **GitHub Actions Documentation:** https://docs.github.com/en/actions
- **markdownlint Rules:** https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md
- **cfn-lint Documentation:** https://github.com/aws-cloudformation/cfn-lint
- **Trivy Documentation:** https://aquasecurity.github.io/trivy/

---

**Questions?** See `CLAUDE.md` for project context or open an issue on GitHub.
