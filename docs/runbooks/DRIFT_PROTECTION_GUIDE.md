# Drift Protection and Compliance Monitoring Guide

**Version:** 1.0
**Last Updated:** November 24, 2025
**Status:** Production Ready ✅

---

## Overview

This guide covers the **dual-layer drift protection** system for Project Aura:

1. **CloudFormation Drift Detection** - Detects manual changes to stack resources
2. **AWS Config Compliance Rules** - Continuous compliance monitoring (CMMC Level 3, NIST 800-53, DoD SRG)

Together, these systems ensure infrastructure security posture is maintained and compliance violations are detected immediately.

---

## Table of Contents

- [Why Drift Protection Matters](#why-drift-protection-matters)
- [Architecture](#architecture)
- [Deployment](#deployment)
- [Drift Detection System](#drift-detection-system)
- [AWS Config Compliance](#aws-config-compliance)
- [Alert Response Procedures](#alert-response-procedures)
- [Cost Analysis](#cost-analysis)
- [Troubleshooting](#troubleshooting)

---

## Why Drift Protection Matters

### **Compliance Requirements**

| Control | Requirement | Implementation |
|---------|-------------|----------------|
| **CMMC AC.L3-3.1.5** | Least Privilege | Detects IAM wildcard reintroduction |
| **CMMC AU.L3-3.3.1** | Audit Logging | Monitors VPC Flow Logs retention |
| **CMMC SC.L3-3.13.8** | Encryption at Rest | Verifies KMS encryption enabled |
| **NIST 800-53 CM-3** | Configuration Change Control | Tracks all infrastructure changes |
| **NIST 800-53 SI-7** | Software Integrity | Ensures config integrity |
| **DoD SRG** | Web Application Firewall | Verifies WAF remains enabled |

### **Security Protection**

After fixing 8 critical security issues (November 22, 2025), drift protection ensures:

- ✅ No one manually disables Neptune KMS encryption
- ✅ No one reduces VPC Flow Logs retention from 365→7 days
- ✅ No one adds `Resource: '*'` wildcards back to IAM policies
- ✅ No one removes AWS WAF from Application Load Balancers
- ✅ No one bypasses security groups or opens 0.0.0.0/0 access
- ✅ No one disables KMS key rotation

### **GovCloud Migration Safety**

- Detects Commercial Cloud vs GovCloud ARN partition differences
- Validates STIG/FIPS hardening settings aren't reverted
- Ensures compliance requirements are maintained during migration

---

## Architecture

### **System Components**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Drift Protection System                       │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐       ┌──────────────────────────┐
│  CloudFormation Drift    │       │    AWS Config Rules      │
│      Detection           │       │  (Continuous Monitoring) │
└──────────────────────────┘       └──────────────────────────┘
           │                                    │
           │ EventBridge                        │ EventBridge
           │ (every 6 hours)                    │ (on change)
           ▼                                    ▼
┌──────────────────────────┐       ┌──────────────────────────┐
│  Lambda Function         │       │  Config Evaluations      │
│  - Detect drift          │       │  - 18 compliance rules   │
│  - Identify changes      │       │  - CMMC/NIST/DoD SRG     │
│  - Auto-remediate (opt)  │       │  - Real-time alerts      │
└──────────────────────────┘       └──────────────────────────┘
           │                                    │
           └────────────┬───────────────────────┘
                        ▼
              ┌─────────────────────┐
              │    SNS Topics       │
              │  - Drift alerts     │
              │  - Compliance       │
              └─────────────────────┘
                        │
                        ▼
              ┌─────────────────────┐
              │  Email + Slack      │
              │  (Team Alerts)      │
              └─────────────────────┘
```

### **Detection Layers**

| Layer | Purpose | Frequency | Action |
|-------|---------|-----------|--------|
| **CloudFormation Drift** | Detects manual resource changes | Every 6 hours | Alert + optional auto-fix |
| **AWS Config** | Validates compliance rules | Real-time (on change) | Immediate alert |
| **CloudWatch Alarms** | Monitors Lambda errors | Continuous | Alert if detector fails |

---

## Deployment

### **Prerequisites**

1. ✅ AWS account with CloudFormation permissions
2. ✅ IAM role with Config/Lambda permissions (already created in `iam.yaml`)
3. ✅ Email address for alerts
4. ✅ Existing CloudFormation stacks to monitor (iam, security, networking, neptune, etc.)

### **Step 1: Deploy Drift Detection Stack**

```bash
# Deploy to dev environment
aws cloudformation create-stack \
  --stack-name aura-drift-detection-dev \
  --template-body file://deploy/cloudformation/drift-detection.yaml \
  --parameters \
    ParameterKey=ProjectName,ParameterValue=aura \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=AlertEmail,ParameterValue=your-email@example.com \
    ParameterKey=DriftDetectionSchedule,ParameterValue="rate(6 hours)" \
    ParameterKey=EnableAutomaticRemediation,ParameterValue=false \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# Wait for completion
aws cloudformation wait stack-create-complete \
  --stack-name aura-drift-detection-dev \
  --region us-east-1

# Confirm email subscription
# Check your email and click the SNS confirmation link
```

### **Step 2: Deploy AWS Config Compliance Stack**

```bash
# Deploy to dev environment
aws cloudformation create-stack \
  --stack-name aura-config-compliance-dev \
  --template-body file://deploy/cloudformation/config-compliance.yaml \
  --parameters \
    ParameterKey=ProjectName,ParameterValue=aura \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=AlertEmail,ParameterValue=your-email@example.com \
    ParameterKey=ConfigSnapshotDeliveryFrequency,ParameterValue=Six_Hours \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# Wait for completion
aws cloudformation wait stack-create-complete \
  --stack-name aura-config-compliance-dev \
  --region us-east-1

# Confirm email subscription
# Check your email and click the SNS confirmation link
```

### **Step 3: Verify Deployment**

```bash
# Check drift detection Lambda
aws lambda invoke \
  --function-name aura-drift-detector-dev \
  --payload '{}' \
  --region us-east-1 \
  response.json

cat response.json

# Check AWS Config status
aws configservice describe-configuration-recorder-status \
  --configuration-recorder-names aura-config-recorder-dev \
  --region us-east-1

# Check Config rules
aws configservice describe-config-rules \
  --config-rule-names aura-iam-no-wildcard-dev aura-neptune-encryption-dev \
  --region us-east-1
```

### **Step 4: Test Drift Detection**

```bash
# Manually trigger drift detection
aws lambda invoke \
  --function-name aura-drift-detector-dev \
  --payload '{}' \
  --region us-east-1 \
  test-response.json

# Check CloudWatch logs
aws logs tail /aws/lambda/aura-drift-detector-dev --follow

# Verify SNS alert received (if drift detected)
```

---

## Drift Detection System

### **How It Works**

1. **EventBridge** triggers Lambda function every 6 hours (configurable: 1-24 hours)
2. **Lambda** scans all `aura-*` CloudFormation stacks
3. For each stack, initiates `DetectStackDrift` API call
4. Polls for completion (up to 2 minutes per stack)
5. If drift detected, retrieves resource-level details
6. Sends **SNS alert** with:
   - Stack name
   - Drifted resources (resource type, logical ID, property changes)
   - Critical vs non-critical classification
   - Link to CloudFormation console

### **Critical Stacks**

These stacks trigger **HIGH PRIORITY** alerts if drift detected:

- `aura-iam-dev` - IAM roles and policies (security impact)
- `aura-security-dev` - Security groups, WAF (security impact)
- `aura-networking-dev` - VPC, subnets, Flow Logs (compliance impact)
- `aura-neptune-dev` - KMS encryption (compliance impact)

### **Alert Format**

```
Subject: 🚨 CRITICAL Drift Detected - aura prod

CloudFormation Drift Detection Report
Project: aura
Environment: prod
Timestamp: 2025-11-24T18:30:00Z

Total Drifted Stacks: 2
Critical Stacks Drifted: 1

🚨 CRITICAL STACKS (Security/Compliance Impact):
  Stack: aura-neptune-prod
  Status: DRIFTED
  Drifted Resources: 1
    - NeptuneCluster (AWS::Neptune::DBCluster): MODIFIED, 1 properties changed

⚠️ NON-CRITICAL STACKS:
  Stack: aura-monitoring-prod
  Status: DRIFTED
  Drifted Resources: 1
    - DashboardWidget (AWS::CloudWatch::Dashboard): MODIFIED, 2 properties changed

Action Required:
1. Review drift details in CloudFormation console
2. Determine if changes were authorized
3. Update stack template if needed, or revert manual changes
4. Document resolution in change log

CloudFormation Console: https://console.aws.amazon.com/cloudformation/home?region=us-east-1
```

### **Automatic Remediation**

**WARNING:** Automatic remediation is **DISABLED by default** for safety.

#### **When to Enable:**
- ✅ Dev/QA environments (safe to auto-fix)
- ❌ Production (requires HITL approval)

#### **How It Works:**
1. Lambda detects drift in non-critical stacks
2. Calls `UpdateStack` with `UsePreviousTemplate=true`
3. CloudFormation reverts resource to template-defined state
4. Sends alert confirming remediation

#### **Safety Guardrails:**
- Only remediates **non-critical** stacks
- Never remediates production environment (hardcoded check)
- Requires `EnableAutomaticRemediation=true` parameter
- Logs all remediation attempts to CloudWatch

**To enable for dev:**
```bash
aws cloudformation update-stack \
  --stack-name aura-drift-detection-dev \
  --use-previous-template \
  --parameters \
    ParameterKey=EnableAutomaticRemediation,ParameterValue=true \
  --capabilities CAPABILITY_NAMED_IAM
```

---

## AWS Config Compliance

### **18 Managed Rules Deployed**

#### **CMMC Level 3 Controls**

| Rule | Config Rule Name | Control | Purpose |
|------|------------------|---------|---------|
| 1 | `iam-no-wildcard` | AC.L3-3.1.5 | Detects IAM `Resource: '*'` wildcards |
| 2 | `neptune-encryption` | SC.L3-3.13.8 | Verifies Neptune KMS encryption |
| 3 | `rds-snapshot-encryption` | SC.L3-3.13.8 | Verifies RDS snapshot encryption |
| 4 | `s3-encryption` | SC.L3-3.13.8 | Verifies S3 bucket encryption |
| 5 | `vpc-flow-logs` | AU.L3-3.3.1 | Verifies VPC Flow Logs enabled |
| 6 | `cloudwatch-retention` | AU.L3-3.3.1 | Verifies 90+ day log retention |
| 7 | `alb-https-only` | SC.L3-3.13.11 | Verifies HTTPS listeners only |
| 8 | `elb-tls-version` | SC.L3-3.13.11 | Verifies TLS 1.2+ |
| 9 | `sg-no-ssh` | AC.L3-3.1.20 | Blocks 0.0.0.0/0 SSH access |
| 10 | `sg-no-rdp` | AC.L3-3.1.20 | Blocks 0.0.0.0/0 RDP access |
| 11 | `alb-waf-enabled` | SI.L3-3.14.6 | Verifies WAF on ALB |

#### **NIST 800-53 Rev 5 Controls**

| Rule | Config Rule Name | Control | Purpose |
|------|------------------|---------|---------|
| 12 | `kms-key-rotation` | SC-12 | Verifies KMS rotation enabled |
| 13 | `root-mfa-enabled` | AC-2 | Verifies root MFA enabled |
| 14 | `iam-user-mfa` | AC-2 | Verifies user MFA enabled |
| 15 | `vpc-default-sg-closed` | SC-7 | Verifies default SG closed |
| 16 | `s3-public-block` | SC-7 | Verifies S3 public access blocked |

#### **DoD SRG Controls**

| Rule | Config Rule Name | Requirement | Purpose |
|------|------------------|-------------|---------|
| 17 | `ec2-imdsv2` | Secure Metadata | Verifies IMDSv2 enabled |
| 18 | `alb-waf-enabled` | WAF Protection | Verifies WAF deployed |

### **Real-Time Compliance Alerts**

AWS Config evaluates rules **immediately** when resources change:

```
Subject: 🚨 AWS Config Compliance Violation Detected

Rule: aura-iam-no-wildcard-dev
Resource Type: AWS::IAM::Policy
Resource ID: aura-coder-agent-policy-dev
Status: NON_COMPLIANT
Time: 2025-11-24T18:45:00Z

Action Required: Review and remediate this compliance violation immediately.
```

### **Compliance Dashboard**

View compliance status in AWS Console:

```bash
# Open Config dashboard
open "https://console.aws.amazon.com/config/home?region=us-east-1#/dashboard"

# View compliance rules
open "https://console.aws.amazon.com/config/home?region=us-east-1#/rules"

# View non-compliant resources
open "https://console.aws.amazon.com/config/home?region=us-east-1#/resources"
```

**Or use CLI:**

```bash
# Get compliance summary
aws configservice describe-compliance-by-config-rule \
  --region us-east-1 \
  | jq '.ComplianceByConfigRules[] | select(.Compliance.ComplianceType == "NON_COMPLIANT")'

# Get specific rule status
aws configservice get-compliance-details-by-config-rule \
  --config-rule-name aura-iam-no-wildcard-dev \
  --compliance-types NON_COMPLIANT \
  --region us-east-1
```

---

## Alert Response Procedures

### **Drift Alert Response (Priority: HIGH)**

#### **Step 1: Assess Impact**
1. Review alert email - identify drifted stack and resources
2. Determine if stack is critical (IAM, Security, Networking, Neptune)
3. Check if change was authorized (review change log, Slack history)

#### **Step 2: Investigate Drift**
```bash
# View drift details in console
open "https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/drifts"

# Or use CLI
aws cloudformation describe-stack-resource-drifts \
  --stack-name aura-neptune-dev \
  --stack-resource-drift-status-filters MODIFIED DELETED \
  --region us-east-1

# Compare expected vs actual
aws cloudformation detect-stack-drift \
  --stack-name aura-neptune-dev \
  --region us-east-1

# Get drift detection status
aws cloudformation describe-stack-drift-detection-status \
  --stack-drift-detection-id <drift-id> \
  --region us-east-1
```

#### **Step 3: Remediate**

**Option A: Revert Manual Change (Preferred)**
```bash
# Update stack to revert to template
aws cloudformation update-stack \
  --stack-name aura-neptune-dev \
  --use-previous-template \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

**Option B: Update Template (If change is intentional)**
```bash
# Edit CloudFormation template to match actual state
vim deploy/cloudformation/neptune.yaml

# Commit change
git add deploy/cloudformation/neptune.yaml
git commit -m "fix: update Neptune template to match production state"

# Update stack with new template
aws cloudformation update-stack \
  --stack-name aura-neptune-dev \
  --template-body file://deploy/cloudformation/neptune.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

#### **Step 4: Document Resolution**
```bash
# Add entry to CHANGELOG.md
echo "### Fixed
- **Drift Remediation:** Reverted manual change to Neptune KMS encryption ($(date +%Y-%m-%d))" >> CHANGELOG.md

# Commit
git add CHANGELOG.md
git commit -m "docs: document drift remediation for Neptune"
git push
```

---

### **Config Compliance Alert Response (Priority: CRITICAL)**

#### **Step 1: Assess Severity**
- **CRITICAL:** IAM wildcards, missing encryption, open security groups
- **HIGH:** Missing MFA, disabled logging, public S3 buckets
- **MEDIUM:** Log retention issues, TLS version mismatches

#### **Step 2: Investigate**
```bash
# Get resource details
aws configservice get-compliance-details-by-config-rule \
  --config-rule-name aura-iam-no-wildcard-dev \
  --compliance-types NON_COMPLIANT \
  --region us-east-1

# Get resource configuration history
aws configservice get-resource-config-history \
  --resource-type AWS::IAM::Policy \
  --resource-id aura-coder-agent-policy-dev \
  --region us-east-1
```

#### **Step 3: Remediate**

**Example: IAM Wildcard Detected**
```bash
# Find policy with wildcard
aws iam get-policy-version \
  --policy-arn arn:aws:iam::123456789012:policy/aura-coder-agent-policy-dev \
  --version-id v1

# Fix in template
vim deploy/cloudformation/iam.yaml
# Change Resource: '*' to scoped resource

# Update stack
aws cloudformation update-stack \
  --stack-name aura-iam-dev \
  --template-body file://deploy/cloudformation/iam.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

**Example: Neptune Encryption Disabled**
```bash
# Verify KMS encryption
aws neptune describe-db-clusters \
  --db-cluster-identifier aura-neptune-dev \
  | jq '.DBClusters[0] | {StorageEncrypted, KmsKeyId}'

# If encryption disabled, update stack to re-enable
aws cloudformation update-stack \
  --stack-name aura-neptune-dev \
  --use-previous-template \
  --capabilities CAPABILITY_NAMED_IAM
```

#### **Step 4: Verify Remediation**
```bash
# Wait 5 minutes for Config re-evaluation

# Check compliance status
aws configservice describe-compliance-by-config-rule \
  --config-rule-names aura-iam-no-wildcard-dev \
  --region us-east-1 \
  | jq '.ComplianceByConfigRules[0].Compliance.ComplianceType'

# Should return "COMPLIANT"
```

---

## Cost Analysis

### **Monthly Cost Breakdown**

| Component | Dev/QA | Production | Notes |
|-----------|--------|------------|-------|
| **AWS Config** | $2.00/rule | $2.00/rule | 18 rules = $36/month |
| **Config Snapshots (S3)** | $0.50/month | $2.00/month | Depends on change frequency |
| **Lambda Invocations** | $0.10/month | $0.20/month | 4 invocations/day |
| **CloudWatch Logs** | $1.00/month | $5.00/month | 90-day vs 365-day retention |
| **SNS Notifications** | $0.10/month | $0.20/month | ~10-20 alerts/month |
| **TOTAL** | **~$40/month** | **~$45/month** | Per environment |

### **Cost Optimization**

1. **Reduce Config snapshot frequency** (default: 6 hours → 24 hours for dev)
   ```bash
   aws cloudformation update-stack \
     --stack-name aura-config-compliance-dev \
     --use-previous-template \
     --parameters ParameterKey=ConfigSnapshotDeliveryFrequency,ParameterValue=TwentyFour_Hours
   ```

2. **Reduce drift detection frequency** (default: 6 hours → 12 hours for dev)
   ```bash
   aws cloudformation update-stack \
     --stack-name aura-drift-detection-dev \
     --use-previous-template \
     --parameters ParameterKey=DriftDetectionSchedule,ParameterValue="rate(12 hours)"
   ```

3. **Delete old Config snapshots** (automated via S3 lifecycle policy - already configured)

### **ROI Justification**

| Risk | Cost Without Protection | Annual Savings with Protection |
|------|-------------------------|--------------------------------|
| **Failed Audit** | $50,000+ (consultant fees) | $50,000+ |
| **Security Incident** | $500,000+ (breach response) | $500,000+ |
| **Compliance Fine** | $100,000+ (CMMC violation) | $100,000+ |
| **Total Annual Cost** | $540/year | - |
| **ROI** | **~92,492%** | - |

**Conclusion:** Drift protection costs $540/year but prevents potential $650,000+ in security/compliance costs.

---

## Troubleshooting

### **Problem: Drift detection Lambda fails**

**Symptoms:**
- CloudWatch alarm triggered
- No drift reports received

**Diagnosis:**
```bash
# Check Lambda errors
aws logs tail /aws/lambda/aura-drift-detector-dev --follow

# Check IAM permissions
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/aura-drift-detector-lambda-dev \
  --action-names cloudformation:DetectStackDrift cloudformation:DescribeStacks \
  --resource-arns arn:aws:cloudformation:us-east-1:123456789012:stack/aura-iam-dev/*
```

**Solution:**
```bash
# Update Lambda role with missing permissions
aws cloudformation update-stack \
  --stack-name aura-drift-detection-dev \
  --use-previous-template \
  --capabilities CAPABILITY_NAMED_IAM
```

---

### **Problem: Config rules show INSUFFICIENT_DATA**

**Symptoms:**
- Config dashboard shows "Insufficient Data"
- No compliance evaluations

**Diagnosis:**
```bash
# Check Config recorder status
aws configservice describe-configuration-recorder-status \
  --configuration-recorder-names aura-config-recorder-dev

# Should show "recording": true, "lastStatus": "SUCCESS"
```

**Solution:**
```bash
# Start Config recorder
aws configservice start-configuration-recorder \
  --configuration-recorder-name aura-config-recorder-dev

# Trigger manual evaluation
aws configservice start-config-rules-evaluation \
  --config-rule-names aura-iam-no-wildcard-dev
```

---

### **Problem: False positive drift alerts**

**Symptoms:**
- Drift detected for resources with expected changes
- Auto-remediation reverts intentional changes

**Solution:**
```bash
# Option 1: Update CloudFormation template to match actual state
vim deploy/cloudformation/<stack>.yaml
# Update template

aws cloudformation update-stack \
  --stack-name aura-<stack>-dev \
  --template-body file://deploy/cloudformation/<stack>.yaml \
  --capabilities CAPABILITY_NAMED_IAM

# Option 2: Exclude resource from drift detection (not recommended)
# Add DeletionPolicy: Retain to resource in template
```

---

### **Problem: SNS alerts not received**

**Symptoms:**
- Drift/compliance issues detected but no email

**Diagnosis:**
```bash
# Check SNS subscription status
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:us-east-1:123456789012:aura-drift-alerts-dev \
  | jq '.Subscriptions[] | {Endpoint, SubscriptionArn, PendingConfirmation}'
```

**Solution:**
```bash
# If PendingConfirmation: true, check email and confirm

# Re-subscribe if needed
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:aura-drift-alerts-dev \
  --protocol email \
  --notification-endpoint your-email@example.com

# Test alert
aws sns publish \
  --topic-arn arn:aws:sns:us-east-1:123456789012:aura-drift-alerts-dev \
  --subject "Test Alert" \
  --message "This is a test alert from drift detection system"
```

---

## Next Steps

### **Immediate (After Deployment)**
- [ ] Deploy drift detection stack to dev
- [ ] Deploy AWS Config stack to dev
- [ ] Confirm SNS email subscriptions
- [ ] Manually trigger drift detection test
- [ ] Review Config compliance dashboard

### **Short-Term (Next 2 Weeks)**
- [ ] Integrate alerts with Slack (create SNS → Lambda → Slack webhook)
- [ ] Create CloudWatch dashboard for drift metrics
- [ ] Document common drift scenarios and resolutions
- [ ] Set up weekly drift report automation

### **Medium-Term (Before Production)**
- [ ] Deploy drift detection to prod (without auto-remediation)
- [ ] Deploy AWS Config to prod
- [ ] Conduct drill: intentional drift injection and response
- [ ] Create runbooks for all 18 Config rules
- [ ] Set up PagerDuty integration for critical alerts

### **Long-Term (GovCloud Migration)**
- [ ] Migrate drift detection to GovCloud
- [ ] Enable additional Config rules for FedRAMP High
- [ ] Integrate with SIEM (Splunk/AWS Security Hub)
- [ ] Automate drift remediation playbooks (Ansible/Systems Manager)

---

## References

- **CloudFormation Template:** `deploy/cloudformation/drift-detection.yaml`
- **Config Template:** `deploy/cloudformation/config-compliance.yaml`
- **Security Fixes:** `GOVCLOUD_REMEDIATION_COMPLETE.md`
- **AWS Config Docs:** https://docs.aws.amazon.com/config/
- **CloudFormation Drift:** https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-drift.html
- **CMMC Level 3:** https://www.acq.osd.mil/cmmc/

---

**Document Version:** 1.0
**Last Updated:** November 24, 2025
**Next Review:** After dev deployment testing
