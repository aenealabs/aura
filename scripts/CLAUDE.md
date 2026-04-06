# Scripts Development Guide

> Universal security rules are in the root `CLAUDE.md`.

---

## Credential Handling

- Scripts must fetch credentials at runtime, not embed them
- Use SSM Parameter Store (SecureString) or Secrets Manager for sensitive values
- See `scripts/rotate-dev-passwords.sh` for the canonical credential handling pattern
- Never hardcode passwords, API keys, tokens, or credentials

---

## Key Scripts

- **Kill-Switches:**
  - `dev_killswitch.py` (86 tests) - See `docs/runbooks/DEV_KILLSWITCH_RUNBOOK.md`
  - `qa_killswitch.py` (47 tests) - See `docs/runbooks/QA_KILLSWITCH_RUNBOOK.md`
- **Security Hooks:**
  - `security_hooks/secrets_hook.py` - Pre-commit secrets scanning
  - `security_hooks/config_hook.py` - Config file validation
  - `security_hooks/commit_msg_hook.py` - AI attribution stripping
- **Validation:**
  - `cfn-lint-wrapper.sh` - CloudFormation template validation
  - `validate_iam_actions.py` - IAM action validation for W3037 warnings

---

## Code Quality

- Scripts have relaxed flake8 style requirements (excluded from pre-commit flake8)
- Bandit security scanning is excluded for scripts (subprocess and random usage is intentional)
- Still follow Python type hints and docstring conventions for maintainability
