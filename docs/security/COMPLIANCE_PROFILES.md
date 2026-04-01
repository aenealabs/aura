# Compliance Profiles - Compliance-Aware Security Scanning

**Status:** Production Ready
**Version:** 1.0.0
**Last Updated:** 2025-12-06

---

## Overview

Aura's **Compliance Profiles** feature provides **compliance-aware security scanning** that automatically adjusts scanning granularity, review requirements, and audit trails based on regulatory requirements.

This makes Aura the **first autonomous security platform** with built-in compliance intelligence for:
- CMMC Level 2 & 3 (DoD contractors)
- SOX (Sarbanes-Oxley financial controls)
- PCI-DSS (payment card industry)
- NIST 800-53 (federal agencies)
- DEVELOPMENT (fast iteration with basic security)

---

## Why Compliance Profiles?

### The Problem

Traditional security scanners treat all code changes equally, leading to:

- **Over-scanning:** Documentation changes trigger full infrastructure scans (wasted CI/CD minutes)
- **Under-scanning:** Cost optimizations skip critical infrastructure files (compliance gaps)
- **No audit trail:** Can't prove to auditors what was scanned and why
- **One-size-fits-all:** Same scanning for dev environments and production deployments

### The Solution

Compliance Profiles provide **risk-based scanning** that:

1. **Adapts to compliance requirements** - CMMC L3 scans everything, DEVELOPMENT scans only code
2. **Justifies every decision** - Audit trail shows "scanned per CMMC Level 3 profile"
3. **Balances cost and security** - Optimize dev environments, harden production
4. **Integrates with HITL workflows** - Critical changes require human approval

---

## Available Profiles

### CMMC Level 3 (Advanced/Progressive)

**Use Case:** DoD contractors handling Controlled Unclassified Information (CUI)

**Scanning Behavior:**
- Scans **all file changes** (code, docs, infrastructure, tests)
- Blocks deployment on **CRITICAL or HIGH** severity findings
- Requires **2 reviewers** for security-critical changes
- Retains audit logs for **365 days**

**Control Mappings:**
- AC-3.1.1, AC-3.1.2 (Access Control)
- CA-3.12.4 (Continuous Monitoring)
- CM-3.4.7 (Configuration Management)
- RA-3.11.2 (Vulnerability Scanning)

**Example Configuration:**
```yaml
compliance:
  profile: CMMC_LEVEL_3
  enabled: true
```

**Audit Trail Output:**
```json
{
  "compliance_profile": "CMMC_LEVEL_3",
  "scan_all_changes": true,
  "block_on_high": true,
  "min_reviewers": 2,
  "control_mappings": ["AC-3.1.1", "CA-3.12.4", "CM-3.4.7"]
}
```

---

### CMMC Level 2 (Managed)

**Use Case:** Basic CUI protection for DoD supply chain

**Scanning Behavior:**
- Scans code, infrastructure, tests (skips documentation)
- Blocks deployment on **CRITICAL** only
- Requires **1 reviewer** for IAM/network changes
- Retains audit logs for **90 days**

**Example Configuration:**
```yaml
compliance:
  profile: CMMC_LEVEL_2
  enabled: true
```

---

### SOX (Sarbanes-Oxley)

**Use Case:** Public companies with financial reporting requirements

**Scanning Behavior:**
- Scans code, infrastructure, database schemas
- Blocks deployment on **CRITICAL or HIGH** (strict change control)
- Requires **2 reviewers** (segregation of duties)
- Retains audit logs for **2,555 days (7 years)**

**Manual Review Required For:**
- Database schema changes
- Financial calculation code
- Billing/reporting services

**Example Configuration:**
```yaml
compliance:
  profile: SOX
  enabled: true
```

---

### PCI-DSS (Payment Card Industry)

**Use Case:** Organizations processing credit card payments

**Scanning Behavior:**
- Scans code, infrastructure (skips documentation)
- Blocks deployment on **CRITICAL or HIGH**
- Requires **1 reviewer** for payment-related changes
- Retains audit logs for **365 days**

**Manual Review Required For:**
- Payment processing code
- Cardholder data handling
- Encryption key changes

**Example Configuration:**
```yaml
compliance:
  profile: PCI_DSS
  enabled: true
```

---

### NIST 800-53 (Federal Security Controls)

**Use Case:** Federal agencies and contractors

**Scanning Behavior:**
- Scans **all file changes** (comprehensive)
- Blocks deployment on **CRITICAL or HIGH**
- Requires **2 reviewers** for security changes
- Retains audit logs for **365 days**

**Example Configuration:**
```yaml
compliance:
  profile: NIST_800_53
  enabled: true
```

---

### DEVELOPMENT (Fast)

**Use Case:** Development environments where speed matters

**Scanning Behavior:**
- Scans **only Python code** (src/**/*.py)
- **Warns** on findings (doesn't block)
- **No manual reviews** required
- Retains audit logs for **30 days**

**Example Configuration:**
```yaml
compliance:
  profile: DEVELOPMENT
  enabled: true
```

**When to Use:**
- Local development
- Feature branches in dev environment
- Rapid prototyping

**When NOT to Use:**
- Production deployments
- Main/develop branches
- Compliance-regulated environments

---

## Configuration

### 1. Create Configuration File

Create `.aura/config.yml` in your project root:

```yaml
compliance:
  profile: CMMC_LEVEL_3
  enabled: true
  custom_overrides: {}
```

### 2. Apply Custom Overrides

Override specific profile settings while maintaining compliance:

```yaml
compliance:
  profile: CMMC_LEVEL_3
  enabled: true
  custom_overrides:
    # Increase reviewer requirement
    review.min_reviewers: 3

    # Extend audit log retention
    audit.log_retention_days: 730
```

**Valid Override Keys:**

| Key | Type | Example |
|-----|------|---------|
| `scanning.scan_all_changes` | boolean | `true` |
| `scanning.scan_infrastructure` | boolean | `true` |
| `scanning.scan_documentation` | boolean | `false` |
| `review.block_on_critical` | boolean | `true` |
| `review.block_on_high` | boolean | `true` |
| `review.min_reviewers` | integer | `3` |
| `audit.log_retention_days` | integer | `730` |

**Important:** Overrides are logged in the audit trail for transparency.

### 3. Validate Configuration

```bash
python3 -c "from src.services.compliance_config import ComplianceConfig; ComplianceConfig().load()"
```

Expected output:
```
INFO - Found Aura config at: /path/to/.aura/config.yml
INFO - Loaded configuration from /path/to/.aura/config.yml
INFO - Configuration validation passed
INFO - Loaded compliance profile: CMCC Level 3 (Advanced/Progressive)
```

---

## Usage

### Programmatic Usage

```python
from src.services.compliance_security_service import ComplianceSecurityService
from src.services.compliance_profiles import SeverityLevel

# Initialize service (auto-loads profile from .aura/config.yml)
security_service = ComplianceSecurityService()

# Check if a file should be scanned
should_scan, reason = security_service.should_scan_file("deploy/cloudformation/iam.yaml")
print(f"Scan: {should_scan}, Reason: {reason}")
# Output: Scan: True, Reason: Infrastructure scanning enabled

# Filter files for scanning
files = ["src/api/auth.py", "README.md", "deploy/cloudformation/vpc.yaml"]
to_scan, skipped, reasons = security_service.filter_files_for_scanning(files)
print(f"Scanning {len(to_scan)} files, skipped {len(skipped)}")

# Perform compliance-aware scan
result = security_service.perform_scan(to_scan)

# Check deployment decision
if result.should_block_deployment:
    print(f"Deployment BLOCKED: {result.manual_review_reasons}")
else:
    print("Deployment APPROVED")

# Generate summary
summary = security_service.format_scan_summary(result)
print(summary)
```

### GitHub Actions Integration

The `aura-security-review.yml` workflow automatically uses the configured compliance profile:

```yaml
- name: Run Aura Security Review
  run: |
    python3 -m src.services.compliance_security_service
```

The workflow will:
1. Load compliance profile from `.aura/config.yml`
2. Filter files based on profile scanning policy
3. Run Semgrep/Trivy on allowed files
4. Block deployment if critical findings detected (based on profile)
5. Create audit trail in CloudWatch Logs

---

## Audit Trail

Every compliance decision is logged with:

```json
{
  "event_id": "audit-a1b2c3d4e5f6g7h8",
  "event_type": "SCAN_COMPLETED",
  "timestamp": "2025-12-06T10:30:00Z",
  "profile_name": "CMMC_LEVEL_3",
  "profile_version": "1.0.0",
  "actor": "github-actions[bot]",
  "action": "Completed security scan: 3 findings, 1 critical, 2 high",
  "metadata": {
    "files_scanned": 42,
    "findings_count": 3,
    "critical_count": 1,
    "high_count": 2
  },
  "compliance_controls": ["CA-3.12.4", "RA-3.11.2", "SI-3.14.4"],
  "result": "COMPLETED"
}
```

### Audit Event Types

| Event Type | Description | Controls Satisfied |
|------------|-------------|-------------------|
| `SCAN_INITIATED` | Scan started | CA-3.12.4, RA-3.11.2 |
| `SCAN_COMPLETED` | Scan finished | CA-3.12.4, SI-3.14.4 |
| `FILE_SKIPPED` | File excluded from scan | CM-3.4.7 |
| `DEPLOYMENT_BLOCKED` | Deployment prevented | CM-3.4.7, SA-3.15.11 |
| `MANUAL_REVIEW_REQUIRED` | HITL approval needed | AC-3.1.2, CM-3.4.9 |
| `MANUAL_REVIEW_APPROVED` | Human approved change | AC-3.1.2, AU-3.3.1 |
| `PROFILE_LOADED` | Compliance profile activated | - |
| `PROFILE_OVERRIDE_APPLIED` | Custom override applied | CM-3.4.7 |

### Querying Audit Logs

```python
from src.services.compliance_audit_service import get_audit_service
from datetime import datetime, timedelta

audit = get_audit_service()

# Query recent deployment blocks
events = audit.query_events(
    event_type=AuditEventType.DEPLOYMENT_BLOCKED,
    start_time=datetime.utcnow() - timedelta(days=7),
    limit=50
)

# Generate compliance report
report = audit.generate_compliance_report(
    start_time=datetime.utcnow() - timedelta(days=30),
    end_time=datetime.utcnow()
)
```

---

## Comparison: With vs Without Compliance Profiles

### Scenario: Documentation-only PR

**Without Compliance Profiles:**
- ❌ Scans all files (including docs)
- ❌ Runs Semgrep/Trivy on Markdown
- ❌ Wastes 5 minutes of CI/CD time
- ❌ No justification for auditors

**With CMMC Level 3 Profile:**
- ✅ Scans documentation (security-critical)
- ✅ Logs decision: "Scanned per CMMC Level 3 - requires doc scanning"
- ✅ Auditors see compliance rationale
- ✅ Defensible in CMMC assessment

**With DEVELOPMENT Profile:**
- ✅ Skips documentation
- ✅ Logs decision: "Skipped per DEVELOPMENT profile"
- ✅ Saves 5 minutes (appropriate for dev)
- ✅ Developers can override if needed

### Scenario: IAM Policy Change

**Without Compliance Profiles:**
- ❌ Scans file (no special treatment)
- ❌ Doesn't require manual review
- ❌ No segregation of duties
- ❌ Compliance gap (CMMC requires 2 reviewers)

**With CMMC Level 3 Profile:**
- ✅ Scans file
- ✅ Requires 2 manual reviewers
- ✅ Blocks deployment until approved
- ✅ Audit trail shows compliance controls satisfied
- ✅ CMMC assessor sees AC-3.1.2 control met

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Compliance Profiles                       │
│  - CMMC L3: Scan all, block high, 2 reviewers, 365d logs   │
│  - SOX: Scan infra/DB, block high, 2 reviewers, 7y logs     │
│  - DEVELOPMENT: Scan code only, warn, 0 reviewers, 30d logs │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│           ComplianceSecurityService                          │
│  - should_scan_file(path) → (bool, reason)                  │
│  - filter_files_for_scanning(files)                         │
│  - should_block_deployment(findings)                        │
│  - requires_manual_review(changes)                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│             Audit Trail Service                              │
│  - CloudWatch Logs (real-time monitoring)                   │
│  - DynamoDB (long-term retention, queryable)                │
│  - Control mappings (CMMC, SOX, NIST controls)              │
└─────────────────────────────────────────────────────────────┘
```

---

## Best Practices

### 1. Use Strictest Profile for Production

```yaml
# .aura/config.yml (production)
compliance:
  profile: CMMC_LEVEL_3
```

### 2. Use DEVELOPMENT Profile Locally

```yaml
# .aura/config.local.yml (gitignored)
compliance:
  profile: DEVELOPMENT
  enabled: true
```

```bash
# Override config path for local development
export AURA_CONFIG_PATH=.aura/config.local.yml
```

### 3. Document Overrides

Always comment why you're overriding defaults:

```yaml
compliance:
  profile: CMMC_LEVEL_3
  custom_overrides:
    # Increased to 3 reviewers per security team policy (2025-12-01)
    review.min_reviewers: 3
```

### 4. Review Audit Logs Regularly

```bash
# Query recent deployment blocks
aws logs filter-log-events \
  --log-group-name /aura/compliance-audit \
  --filter-pattern "DEPLOYMENT_BLOCKED"
```

### 5. Test Profile Changes in Dev First

```bash
# Test new profile configuration
pytest tests/test_compliance_profiles.py -v
```

---

## Troubleshooting

### Issue: "Configuration validation failed"

**Cause:** Invalid profile name or override syntax

**Solution:**
```bash
# Check valid profile names
python3 -c "from src.services.compliance_profiles import ComplianceLevel; print([p.value for p in ComplianceLevel])"

# Validate config
python3 -m src.services.compliance_config
```

### Issue: "No .aura/config.yml found"

**Cause:** Config file doesn't exist

**Solution:**
```bash
# Create default config
python3 -c "from src.services.compliance_config import ComplianceConfig; ComplianceConfig.create_default_config()"
```

### Issue: "Deployment blocked unexpectedly"

**Cause:** Profile requires manual review for certain changes

**Solution:**
```python
# Check why review is required
from src.services.compliance_security_service import ComplianceSecurityService

service = ComplianceSecurityService()
requires_review, reasons = service.requires_manual_review(["deploy/cloudformation/iam.yaml"])
print(f"Requires review: {requires_review}")
print(f"Reasons: {reasons}")
```

---

## FAQ

**Q: Can I use different profiles for different branches?**

A: Yes! Use branch-specific config files:

```yaml
# .aura/config.main.yml (production)
compliance:
  profile: CMMC_LEVEL_3

# .aura/config.develop.yml (staging)
compliance:
  profile: CMMC_LEVEL_2
```

**Q: Does this slow down CI/CD?**

A: No - it actually speeds up development environments by skipping unnecessary scans while maintaining security for production.

**Q: Are audit logs tamper-proof?**

A: Yes - CloudWatch Logs and DynamoDB provide immutable audit trails with IAM-based access controls.

**Q: Can I create a custom profile?**

A: Not yet - request via GitHub issue. For now, use custom_overrides on an existing profile.

**Q: What happens if compliance is disabled?**

A: Set `enabled: false` to bypass compliance profiles (scans all files, no blocking). Not recommended for production.

---

## Related Documentation

- [GitHub Actions Optimization](../CLAUDE.md#efficient-context-management)
- [CMMC Readiness Tracker](./GOVCLOUD_READINESS_TRACKER.md)
- [Security Code Reviewer Agent](../agent-config/agents/security-code-reviewer.md)
- [HITL Sandbox Architecture](./HITL_SANDBOX_ARCHITECTURE.md)

---

## Support

For questions or issues:
- GitHub Issues: https://github.com/aenealabs/aura/issues
- Email: notifications@aenealabs.com
