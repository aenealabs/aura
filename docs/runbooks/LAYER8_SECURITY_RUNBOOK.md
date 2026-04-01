# Layer 8: Security/Compliance Runbook

**Layer:** 8 - Security
**CodeBuild Project:** `aura-security-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-security.yml`
**Estimated Deploy Time:** 5-10 minutes

---

## Overview

The Security layer deploys AWS Config compliance rules, GuardDuty threat detection, CloudFormation drift detection, CloudTrail audit logging, and IAM security alerting for CMMC/NIST compliance.

---

## Resources Deployed

| Stack Name | Template | Resources | Deploy Time |
|------------|----------|-----------|-------------|
| `aura-config-compliance-{env}` | config-compliance.yaml | AWS Config Recorder, 18 Config Rules (CMMC/NIST), SNS Topic | 3-5 min |
| `aura-guardduty-{env}` | guardduty.yaml | GuardDuty Detector, S3/EKS/Malware Protection | 2-3 min |
| `aura-drift-detection-{env}` | drift-detection.yaml | Lambda (drift-detector), EventBridge (6hr schedule), SNS Topic, CloudWatch Alarm | 1-2 min |
| `aura-red-team-{env}` | red-team.yaml | Adversarial testing infrastructure (disabled by default) | 1-2 min |
| `aura-iam-security-alerting-{env}` | iam-security-alerting.yaml | 4 EventBridge Rules, 2 CloudWatch Alarms, SNS Topic (IAM changes) | 1-2 min |
| `aura-cloudtrail-{env}` | cloudtrail.yaml | CloudTrail Trail (multi-region), S3 Bucket, CloudWatch Log Group | 2-3 min |

---

## Dependencies

### Prerequisites
- Layer 1: VPC (for Config rules)
- Layer 5: SNS topics for alerts
- SSM Parameter: `/aura/{env}/alert-email`

### Downstream Dependencies
- None (Security is a leaf layer)

---

## Deployment

### Trigger Deployment
```bash
aws codebuild start-build --project-name aura-security-deploy-dev --region us-east-1
```

### Verify Deployment
```bash
for STACK in aura-config-compliance-dev aura-guardduty-dev aura-drift-detection-dev aura-red-team-dev aura-iam-security-alerting-dev aura-cloudtrail-dev; do
  STATUS=$(aws cloudformation describe-stacks --stack-name $STACK \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")
  echo "$STACK: $STATUS"
done
```

---

## Troubleshooting

### Issue: AWS Config Recorder Already Exists

**Symptoms:**
```
CREATE_FAILED - ConfigurationRecorder already exists
```

**Root Cause:** Only one Config Recorder allowed per region.

**Resolution:**
```bash
# Check existing recorder
aws configservice describe-configuration-recorders

# Delete existing recorder if safe
aws configservice delete-configuration-recorder \
  --configuration-recorder-name default

# Redeploy
aws codebuild start-build --project-name aura-security-deploy-dev
```

---

### Issue: GuardDuty Already Enabled

**Symptoms:**
```
CREATE_FAILED - The request is rejected because the input detectorId is not owned by the current account
```

**Root Cause:** GuardDuty detector already exists in region.

**Resolution:**
```bash
# List existing detectors
aws guardduty list-detectors

# Get detector details
DETECTOR_ID=$(aws guardduty list-detectors --query 'DetectorIds[0]' --output text)
aws guardduty get-detector --detector-id $DETECTOR_ID

# Option 1: Import existing detector
# Option 2: Delete and recreate (loses findings history)
aws guardduty delete-detector --detector-id $DETECTOR_ID
```

---

### Issue: Config Rules Non-Compliant

**Symptoms:**
- Dashboard shows NON_COMPLIANT resources
- Security findings generated

**Root Cause:** Resources don't meet compliance requirements.

**Resolution:**
```bash
# List non-compliant rules
aws configservice describe-compliance-by-config-rule \
  --query 'ComplianceByConfigRules[?Compliance.ComplianceType==`NON_COMPLIANT`].ConfigRuleName' \
  --output table

# Get details for specific rule
aws configservice get-compliance-details-by-config-rule \
  --config-rule-name encrypted-volumes \
  --compliance-types NON_COMPLIANT
```

---

### Issue: GuardDuty Findings Not Appearing

**Symptoms:**
- No findings in GuardDuty console
- Detector shows "Enabled" but no activity

**Root Cause:** No threats detected (good!) or data sources not configured.

**Resolution:**
```bash
# Check detector status
DETECTOR_ID=$(aws guardduty list-detectors --query 'DetectorIds[0]' --output text)
aws guardduty get-detector --detector-id $DETECTOR_ID \
  --query '{Status:Status,DataSources:DataSources}'

# Generate sample findings for testing
aws guardduty create-sample-findings \
  --detector-id $DETECTOR_ID \
  --finding-types "UnauthorizedAccess:EC2/SSHBruteForce"

# List findings
aws guardduty list-findings --detector-id $DETECTOR_ID
```

---

### Issue: Drift Detection Lambda Errors

**Symptoms:**
- CloudWatch Alarm `aura-drift-detector-errors-{env}` triggered
- Lambda errors in logs

**Root Cause:** Permission issues or stack naming mismatch.

**Resolution:**
```bash
# Check Lambda logs
aws logs tail /aws/lambda/aura-drift-detector-dev --since 1h

# Test Lambda manually
aws lambda invoke --function-name aura-drift-detector-dev \
  --payload '{}' /dev/stdout

# Check IAM permissions
aws iam get-role-policy --role-name aura-drift-detector-lambda-dev \
  --policy-name DriftDetectionPolicy
```

---

### Issue: Drift Alerts Not Received

**Symptoms:**
- Drift detected but no email notification
- SNS subscription pending

**Root Cause:** SNS subscription not confirmed.

**Resolution:**
```bash
# Check subscription status
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:us-east-1:123456789012:aura-drift-alerts-dev

# Resend confirmation (delete and recreate)
aws sns unsubscribe --subscription-arn <pending-arn>
aws sns subscribe --topic-arn arn:aws:sns:us-east-1:123456789012:aura-drift-alerts-dev \
  --protocol email --notification-endpoint your-email@example.com
```

---

## Recovery Procedures

### Recreate Config Rules

```bash
aws cloudformation delete-stack --stack-name aura-config-compliance-dev
aws cloudformation wait stack-delete-complete --stack-name aura-config-compliance-dev
aws codebuild start-build --project-name aura-security-deploy-dev
```

### Recreate GuardDuty

```bash
# Note: This loses findings history
aws cloudformation delete-stack --stack-name aura-guardduty-dev
aws cloudformation wait stack-delete-complete --stack-name aura-guardduty-dev
aws codebuild start-build --project-name aura-security-deploy-dev
```

### Recreate Drift Detection

```bash
aws cloudformation delete-stack --stack-name aura-drift-detection-dev
aws cloudformation wait stack-delete-complete --stack-name aura-drift-detection-dev
aws codebuild start-build --project-name aura-security-deploy-dev
# Note: Confirm SNS subscription email after deployment
```

---

## Post-Deployment Verification

### 1. Verify Config Recorder

```bash
aws configservice describe-configuration-recorder-status \
  --query 'ConfigurationRecordersStatus[*].[name,recording,lastStatus]' --output table
```

### 2. Verify Config Rules

```bash
aws configservice describe-config-rules \
  --query 'ConfigRules[?starts_with(ConfigRuleName, `aura-`)].ConfigRuleName' --output table
```

### 3. Verify GuardDuty

```bash
DETECTOR_ID=$(aws guardduty list-detectors --query 'DetectorIds[0]' --output text)
aws guardduty get-detector --detector-id $DETECTOR_ID \
  --query '{Status:Status,FindingPublishingFrequency:FindingPublishingFrequency}'
```

### 4. Check Compliance Status

```bash
aws configservice describe-compliance-by-config-rule \
  --query 'ComplianceByConfigRules[*].[ConfigRuleName,Compliance.ComplianceType]' --output table
```

---

## Compliance Rules Deployed

| Rule Name | Description | CMMC Control |
|-----------|-------------|--------------|
| encrypted-volumes | EBS volumes encrypted | SC.L2-3.13.11 |
| s3-bucket-ssl-requests-only | S3 HTTPS only | SC.L2-3.13.8 |
| vpc-flow-logs-enabled | VPC flow logs | AU.L2-3.3.1 |
| iam-user-mfa-enabled | MFA required | IA.L2-3.5.3 |
| cloudtrail-enabled | CloudTrail logging | AU.L2-3.3.1 |
| ... | (18 rules total) | ... |

---

## Related Documentation

- [CMMC_CERTIFICATION_PATHWAY.md](../CMMC_CERTIFICATION_PATHWAY.md) - Compliance roadmap
- [GOVCLOUD_READINESS_TRACKER.md](../GOVCLOUD_READINESS_TRACKER.md) - GovCloud compliance

---

**Document Version:** 1.0
**Last Updated:** 2025-12-09
