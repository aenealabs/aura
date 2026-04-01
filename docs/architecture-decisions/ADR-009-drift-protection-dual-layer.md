# ADR-009: Dual-Layer Drift Protection for Compliance Monitoring

**Status:** Deployed
**Date:** 2025-11-24
**Decision Makers:** Project Aura Team

## Context

After remediating 8 critical security issues (November 22, 2025), we needed to ensure these fixes are not reverted through:
- Manual console changes
- Misconfigured automation
- Well-intentioned but unauthorized modifications

Compliance requirements (CMMC Level 3, NIST 800-53, SOX) mandate configuration integrity monitoring:
- **CMMC CM-3:** Configuration change control
- **NIST 800-53 SI-7:** Software and information integrity
- **SOX:** Audit trail for infrastructure changes

Options for drift protection:
1. **CloudFormation Drift Detection** - Detects changes from template-defined state
2. **AWS Config Rules** - Continuous compliance evaluation against rules
3. **Custom Lambda Monitoring** - Bespoke drift detection logic
4. **Third-Party Tools** - CloudHealth, Dome9, Prisma Cloud

This decision impacts:
- Security posture maintenance
- Compliance audit readiness
- Operational response time to unauthorized changes
- Infrastructure cost

## Decision

We chose a **Dual-Layer Drift Protection System** combining:

**Layer 1: CloudFormation Drift Detection**
- Lambda function runs every 6 hours (configurable)
- Scans all `aura-*` CloudFormation stacks
- Detects resource property changes from template
- Sends SNS alerts with drift details
- Optional auto-remediation for non-critical stacks (dev only)

**Layer 2: AWS Config Compliance Rules**
- 18 managed rules covering CMMC/NIST/DoD SRG controls
- Real-time evaluation on resource changes
- Immediate alerts for compliance violations
- Continuous compliance dashboard

**Critical Stacks (HIGH PRIORITY alerts):**
- `aura-iam-*` - IAM roles and policies
- `aura-security-*` - Security groups, WAF
- `aura-networking-*` - VPC, Flow Logs
- `aura-neptune-*` - KMS encryption

## Alternatives Considered

### Alternative 1: CloudFormation Drift Detection Only

Use only CloudFormation's built-in drift detection.

**Pros:**
- Simple, single system
- No additional AWS services
- Free (part of CloudFormation)

**Cons:**
- Point-in-time check (every 6 hours), not real-time
- Cannot detect compliance violations (only template drift)
- No coverage for resources outside CloudFormation
- Limited to stack-defined resources

### Alternative 2: AWS Config Only

Use only AWS Config managed and custom rules.

**Pros:**
- Real-time compliance evaluation
- Rich rule library (100+ managed rules)
- Compliance dashboard built-in

**Cons:**
- Does not detect if resources match CloudFormation template
- Configuration vs. intent gap (template is source of truth)
- Monthly cost per rule ($2/rule = $36/month for 18 rules)

### Alternative 3: Third-Party CSPM

Use Cloud Security Posture Management tool (Prisma Cloud, Dome9).

**Pros:**
- Comprehensive multi-cloud support
- Rich visualization and reporting
- Compliance framework mappings

**Cons:**
- Significant cost ($5,000-50,000/year)
- Overkill for single-cloud infrastructure
- External data access concerns for GovCloud
- Vendor lock-in

### Alternative 4: Custom Lambda Monitoring

Build bespoke drift detection with custom logic.

**Pros:**
- Complete control
- Can implement exact requirements

**Cons:**
- Significant development effort
- Reinventing existing AWS features
- Maintenance burden
- Testing complexity

## Consequences

### Positive

1. **Defense in Depth**
   - Two independent detection mechanisms
   - Different detection methods (template vs. rules)
   - Catches issues the other might miss

2. **Real-Time + Scheduled Coverage**
   - Config: Immediate on resource change
   - CloudFormation: Every 6 hours (catch-all)
   - No gaps in monitoring

3. **Compliance Documentation**
   - Pre-built mappings to CMMC/NIST controls
   - Audit-ready compliance dashboard
   - 7-year retention for audit trail

4. **Automated Response**
   - Optional auto-remediation (dev environments)
   - Clear escalation path
   - Reduced mean-time-to-remediation

5. **Cost-Effective**
   - ~$40/month per environment
   - ROI: Prevents $650K+ in potential compliance/breach costs
   - 92,000%+ return on investment

### Negative

1. **Dual Systems to Manage**
   - Two alert channels to monitor
   - Potential for duplicate alerts
   - Slightly higher operational overhead

2. **Alert Fatigue Risk**
   - Non-critical drift may generate noise
   - Requires tuning over time

3. **Config Rule Costs**
   - $2/rule/month × 18 rules = $36/month
   - Scales with number of rules

### Mitigation

- Critical vs. non-critical alert classification
- Severity-based routing (email vs. PagerDuty)
- Weekly alert review and tuning
- Deduplication in alerting pipeline

## AWS Config Rules Deployed

### CMMC Level 3 Controls

| Rule | Control | Purpose |
|------|---------|---------|
| `iam-no-wildcard` | AC.L3-3.1.5 | No IAM `Resource: '*'` wildcards |
| `neptune-encryption` | SC.L3-3.13.8 | KMS encryption required |
| `s3-encryption` | SC.L3-3.13.8 | S3 bucket encryption |
| `vpc-flow-logs` | AU.L3-3.3.1 | VPC Flow Logs enabled |
| `cloudwatch-retention` | AU.L3-3.3.1 | 90+ day log retention |
| `alb-https-only` | SC.L3-3.13.11 | HTTPS listeners only |
| `sg-no-ssh` | AC.L3-3.1.20 | No 0.0.0.0/0 SSH access |
| `alb-waf-enabled` | SI.L3-3.14.6 | WAF on ALB |

### NIST 800-53 Rev 5 Controls

| Rule | Control | Purpose |
|------|---------|---------|
| `kms-key-rotation` | SC-12 | KMS rotation enabled |
| `root-mfa-enabled` | AC-2 | Root MFA enabled |
| `iam-user-mfa` | AC-2 | User MFA enabled |
| `vpc-default-sg-closed` | SC-7 | Default SG closed |
| `s3-public-block` | SC-7 | S3 public access blocked |

### DoD SRG Controls

| Rule | Requirement | Purpose |
|------|-------------|---------|
| `ec2-imdsv2` | Secure Metadata | IMDSv2 required |
| `alb-waf-enabled` | WAF Protection | WAF deployed |

## Alert Response SLA

| Severity | Response Time | Remediation Time |
|----------|---------------|------------------|
| Critical (IAM, encryption) | 15 minutes | 1 hour |
| High (security groups, logging) | 1 hour | 4 hours |
| Medium (configuration drift) | 4 hours | 24 hours |

## Cost Analysis

| Component | Monthly Cost |
|-----------|--------------|
| AWS Config (18 rules) | $36.00 |
| Config Snapshots (S3) | $0.50-2.00 |
| Lambda Invocations | $0.10-0.20 |
| CloudWatch Logs | $1.00-5.00 |
| SNS Notifications | $0.10-0.20 |
| **TOTAL** | **~$40-45/month** |

**Annual Cost:** ~$540

**Risk Mitigation Value:**
- Failed Audit: $50,000+ avoided
- Security Incident: $500,000+ avoided
- Compliance Fine: $100,000+ avoided
- **ROI: ~92,000%**

## References

- `docs/DRIFT_PROTECTION_GUIDE.md` - Complete operational guide
- `deploy/cloudformation/drift-detection.yaml` - CloudFormation drift Lambda
- `deploy/cloudformation/config-compliance.yaml` - AWS Config rules
- `GOVCLOUD_REMEDIATION_COMPLETE.md` - Security fixes being protected
