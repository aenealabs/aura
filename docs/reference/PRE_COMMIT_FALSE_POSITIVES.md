# Pre-commit Hook False Positives Registry

This document catalogs verified false positives from Project Aura's pre-commit hooks. Each entry has been manually reviewed and confirmed as a non-issue. Configuration changes have been made to suppress these alerts in CI pipelines.

---

## Table of Contents

1. [Overview](#overview)
2. [aura-secrets-scan (Custom Hook)](#aura-secrets-scan-custom-hook)
3. [check-yaml (pre-commit-hooks)](#check-yaml-pre-commit-hooks)
4. [detect-private-key (pre-commit-hooks)](#detect-private-key-pre-commit-hooks)
5. [bandit (Security Scanner)](#bandit-security-scanner)
6. [flake8 (Code Quality)](#flake8-code-quality)
7. [Configuration Reference](#configuration-reference)

---

## Overview

Pre-commit hooks are essential for maintaining code quality and security. However, certain patterns in our codebase trigger false positives that must be documented and suppressed to avoid CI failures.

**Verification Process:**

1. Human engineer reviews each flagged item
2. Confirms the alert is a false positive (not an actual security issue)
3. Documents the reasoning in this file
4. Adds appropriate exclusion to hook configuration
5. Re-runs hooks to verify suppression works

**Last Full Audit:** 2025-12-27

---

## aura-secrets-scan (Custom Hook)

### Category: React Form Field Names

**Status:** Verified False Positive
**Verification Date:** 2025-12-27
**Reviewer:** Security Team

**Affected Files:**

| File | Lines | Pattern |
|------|-------|---------|
| `frontend/src/components/auth/ResetPasswordPage.jsx` | 78, 88, 90 | Form field names: "Password", "PasswordConfirm" |
| `frontend/src/components/auth/SignUpPage.jsx` | 88, 98, 100 | Form field names: "Password", "NewPassword" |
| `frontend/src/components/ProfilePage.jsx` | 378, 387 | Form field names: "CurrentPassword", "NewPassword" |

**Why This Is a False Positive:**

These are React component UI form field labels, placeholders, and input names used for user-facing password entry forms. They do not contain actual secrets or credentials.

Example pattern:
```jsx
<TextField
  name="password"
  label="Password"
  type="password"
  placeholder="Enter your password"
/>
```

The words "Password", "PasswordConfirm", "NewPassword", etc., are metadata describing the form field purpose, not actual password values.

**Mitigation:**

1. Frontend source files are excluded from aura-secrets-scan
2. Added `frontend/src/components/.*` to hook exclusion list

---

## check-yaml (pre-commit-hooks)

### Category: CloudFormation Intrinsic Functions

**Status:** Verified False Positive
**Verification Date:** 2025-12-27
**Reviewer:** Infrastructure Team

**Affected Files:**

| File | Line | Trigger |
|------|------|---------|
| `deploy/cloudformation/marketing-site.yaml` | 185 | `!Sub` with embedded colons |
| `deploy/cloudformation/codebuild-marketing.yaml` | 98 | `!Sub` with embedded colons |
| `deploy/cloudformation/opensearch.yaml` | 46 | `!Sub` with embedded colons |
| `deploy/cloudformation/codebuild-serverless.yaml` | 88 | `!Sub` with embedded colons |
| `archive/legacy/cloudformation/codebuild.yaml` | 92 | `!Sub` with embedded colons |

**Why This Is a False Positive:**

CloudFormation YAML uses AWS-specific intrinsic functions (`!Sub`, `!Ref`, `!GetAtt`, etc.) that are valid CloudFormation syntax but not standard YAML. The `check-yaml` hook with a standard YAML parser cannot interpret these custom tags.

Example pattern:
```yaml
Resources:
  MyBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub "${ProjectName}-${Environment}-artifacts"
```

The `!Sub` tag and variable interpolation syntax `${}` are CloudFormation-specific extensions.

**Mitigation:**

1. Added `--unsafe` flag to check-yaml hook (allows custom tags)
2. CloudFormation templates are validated separately via `cfn-lint`

---

## detect-private-key (pre-commit-hooks)

### Category: Test Fixtures and Templates

**Status:** Verified False Positive
**Verification Date:** 2025-12-27
**Reviewer:** Security Team

**Affected Files:**

| File | Purpose | Content Type |
|------|---------|--------------|
| `tests/conftest.py` | Pytest fixtures | Mock RSA keys for testing |
| `deploy/kubernetes/argocd/repo-secret.yaml.template` | Template file | Placeholder key format |
| `tests/test_github_pr_service.py` | Unit tests | Mock GitHub app keys |
| `tests/test_secrets_detection_service.py` | Unit tests | Intentional secret samples for testing scanner |
| `src/services/github_pr_service.py` | Service code | PEM header detection logic |
| `tests/test_github_app_auth.py` | Unit tests | Mock authentication keys |

**Why This Is a False Positive:**

These files contain intentional mock private keys used for:

1. **Unit Testing:** Mock keys allow testing authentication flows without real credentials
2. **Template Files:** `.template` and `.example` files contain placeholder patterns
3. **Scanner Testing:** The secrets detection service needs sample keys to verify detection works

Example test fixture:
```python
MOCK_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn0ygW5bN...
-----END RSA PRIVATE KEY-----"""
```

These keys are:
- Generated specifically for testing
- Never used in production
- Not connected to any real system
- Intentionally committed for test repeatability

**Mitigation:**

1. Test directories (`tests/`) are already excluded from security scanning
2. Template files (`.template`, `.example`) are excluded
3. Specific service files with detection logic are whitelisted
4. Added explicit exclusions for remaining false positive files

---

## bandit (Security Scanner)

### Category B105: Hardcoded Password Strings

**Status:** Verified False Positive
**Verification Date:** 2025-12-27
**Reviewer:** Security Team

**Affected Patterns:**

| Issue ID | Pattern | Example | Reason |
|----------|---------|---------|--------|
| B105 | Enum values with "password"/"secret"/"token" | `SECRET = "secret"` | Enum member names, not credentials |
| B105 | SSM parameter path prefixes | `password_prefix = "aura/"` | Path prefix, not password value |
| B105 | Configuration key names | `"password_field": "password"` | Schema field names |

**Why This Is a False Positive:**

Bandit's B105 check flags any string assigned to a variable containing "password", "secret", or "token" in its name. This creates false positives for:

1. **Enum Definitions:** `class SecretType(Enum): PASSWORD = "password"` - The string "password" is a type identifier
2. **SSM Path Prefixes:** `password_path = "aura/secrets/"` - This is a path prefix, not a password
3. **Schema Definitions:** Field mapping configurations use these as key names

**Mitigation:**

1. Added per-file-ignores in `pyproject.toml` for known false positive locations
2. Configured bandit to skip `tests/` and `scripts/` directories
3. Set severity threshold to MEDIUM (ignores LOW severity by default)

---

### Category B311: random() for Non-Cryptographic Purposes

**Status:** Verified False Positive
**Verification Date:** 2025-12-27
**Reviewer:** Security Team

**Affected Patterns:**

| Use Case | Files | Purpose |
|----------|-------|---------|
| UI Animation Delays | `frontend/src/components/*.jsx` | Random timing for visual effects |
| Test Data Generation | `tests/test_*.py` | Random test values |
| Load Balancing Simulation | `scripts/simulate_*.py` | Non-security randomness |
| Demo Data Creation | `scripts/generate_demo_data.py` | Sample data for demos |

**Why This Is a False Positive:**

The `random` module is flagged because it uses a predictable PRNG (Pseudo-Random Number Generator). However, our usage is intentionally non-cryptographic:

1. **UI Delays:** `time.sleep(random.uniform(0.1, 0.5))` - Timing variation for natural feel
2. **Test Shuffling:** `random.choice(test_values)` - Test data selection
3. **Demo Generation:** Creating sample data for demonstrations

For actual cryptographic needs, we use `secrets` module (verified in `src/services/crypto_service.py`).

**Mitigation:**

1. Scripts directory excluded from bandit
2. Test directory excluded from bandit
3. Added inline `# nosec B311` comments where random is intentionally used in src/

---

### Category B110: try/except/pass Patterns

**Status:** Verified False Positive
**Verification Date:** 2025-12-27
**Reviewer:** Code Quality Team

**Affected Patterns:**

```python
try:
    optional_cleanup()
except Exception:
    pass  # Intentionally swallowing - best-effort cleanup
```

**Why This Is a False Positive:**

These patterns are intentional for:

1. **Optional Cleanup:** Cleanup that should not fail the main operation
2. **Graceful Degradation:** Features that have fallback behavior
3. **Import Fallbacks:** Optional dependency handling

Each instance has been reviewed and includes a comment explaining why the pattern is intentional.

**Mitigation:**

1. Added inline `# nosec B110` comments with explanation
2. Code review process verifies each try/except/pass is documented

---

### Category B101: assert Statements

**Status:** Verified False Positive
**Verification Date:** 2025-12-27
**Reviewer:** Code Quality Team

**Why This Is a False Positive:**

B101 warns about `assert` statements because they are removed when Python runs with `-O` (optimize) flag. Our asserts are used for:

1. **Test Files:** Pytest relies on assert statements - this is correct usage
2. **Type Narrowing:** Asserts for mypy type checking
3. **Development Invariants:** Debug-mode checks that are acceptable to skip in production

**Mitigation:**

1. Test directories excluded from bandit
2. S101 (flake8-bandit equivalent) ignored in ruff configuration for tests

---

### Category B404/B603: subprocess Usage

**Status:** Verified False Positive
**Verification Date:** 2025-12-27
**Reviewer:** Security Team

**Affected Files:**

| File | Purpose | Security Review |
|------|---------|-----------------|
| `scripts/deploy.py` | Deployment automation | Uses hardcoded commands, no user input |
| `scripts/validate_templates.py` | CloudFormation validation | Calls cfn-lint with static args |
| `src/services/git_service.py` | Git operations | Sanitized repository paths |

**Why This Is a False Positive:**

Our subprocess usage follows secure patterns:

1. **No Shell Injection:** Commands are passed as lists, not shell strings
2. **No User Input:** Command arguments are hardcoded or validated
3. **Explicit shell=False:** We never enable shell mode

Example secure pattern:
```python
subprocess.run(
    ["aws", "cloudformation", "validate-template", "--template-body", template],
    shell=False,  # Explicit
    capture_output=True,
    check=True,
)
```

**Mitigation:**

1. Scripts directory excluded from bandit
2. Specific service files reviewed and documented

---

### Category B107: Hardcoded Password Defaults

**Status:** Verified False Positive
**Verification Date:** 2025-12-27
**Reviewer:** Security Team

**Affected Patterns:**

```python
def get_secret(path: str, prefix: str = "aura/") -> str:
    """Get secret from SSM with default prefix."""
```

**Why This Is a False Positive:**

These are not hardcoded passwords but:

1. **Path Prefixes:** SSM parameter path segments
2. **Default Configuration:** Non-sensitive defaults
3. **Placeholder Values:** Example values in docstrings

**Mitigation:**

1. Added inline `# nosec B107` comments where appropriate
2. Actual secrets are fetched at runtime from SSM Parameter Store or Secrets Manager

---

## flake8 (Code Quality)

### Category: Deploy/Scripts/Tests Warnings

**Status:** Verified Non-Issues
**Verification Date:** 2025-12-27
**Reviewer:** Code Quality Team

**Affected Directories:**

| Directory | Warning Types | Reason for Suppression |
|-----------|---------------|------------------------|
| `deploy/` | F401, F841 | Infrastructure scripts with conditional imports |
| `scripts/` | F401, F541, F841 | Utility scripts with debug code |
| `tests/` | F401, F841, B007 | Test fixtures with intentional unused variables |

**Warning Details:**

| Code | Description | Why Suppressed |
|------|-------------|----------------|
| F401 | Unused imports | Conditional imports for different environments |
| F541 | f-string without placeholders | Intentional for future expansion |
| F841 | Unused variables | Test fixtures, destructuring assignments |
| B007 | Unused loop variables | Iteration for side effects |
| B008 | Function call in default arg | FastAPI Depends() pattern (correctly used in src/api/) |
| C401/C420 | Comprehension style | Style preference, not a bug |

**Mitigation:**

1. Deploy and scripts directories excluded from strict flake8 checks
2. B008 already fixed in `src/api/` - not a false positive there
3. Per-file-ignores configured in pyproject.toml

---

## Configuration Reference

### Files Modified for False Positive Handling

| Configuration File | Purpose |
|-------------------|---------|
| `.pre-commit-config.yaml` | Hook exclusions and arguments |
| `pyproject.toml` | Bandit and flake8 per-file-ignores |
| `src/services/secrets_detection_service.py` | Custom false positive patterns |

### How to Add New False Positives

1. **Document First:** Add entry to this file with:
   - Category and status
   - Affected files and lines
   - Clear explanation of why it's a false positive
   - Verification date and reviewer

2. **Update Configuration:** Add appropriate exclusions to:
   - `.pre-commit-config.yaml` for hook-level exclusions
   - `pyproject.toml` for bandit/ruff/flake8 ignores
   - Inline `# nosec` or `# noqa` comments for specific lines

3. **Verify Suppression:** Run `pre-commit run --all-files` to confirm

4. **Code Review:** All false positive additions require security team review

---

## Audit History

| Date | Auditor | Changes |
|------|---------|---------|
| 2025-12-27 | Security Team | Initial comprehensive audit and documentation |

---

## Related Documentation

- [Security Code Reviewer](../../agent-config/agents/security-code-reviewer.md) - Security review guidelines
- [CICD Setup Guide](../deployment/CICD_SETUP_GUIDE.md) - Pre-commit integration with CI
- [Testing Strategy](TESTING_STRATEGY.md) - Test fixture guidelines
