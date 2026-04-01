# IR-003: Credential Exposure Incident Response Playbook

**Version:** 1.0
**Last Updated:** January 25, 2026
**Owner:** Security Team
**Classification:** Public

---

## 1. Overview

### 1.1 Purpose
This playbook provides procedures for responding to exposed credentials including API keys, tokens, passwords, and other secrets.

### 1.2 Scope
Applies to exposure of:
- AWS credentials (Access Keys, Secret Keys, Session Tokens)
- API tokens (GitHub, GitLab, Slack, etc.)
- Database credentials
- JWT signing keys
- SSH/TLS private keys
- OAuth client secrets
- Service account credentials

### 1.3 MITRE ATT&CK Mapping
| Technique | ID | Description |
|-----------|-----|-------------|
| Unsecured Credentials | T1552 | Credentials in files/repos |
| Valid Accounts | T1078 | Use of compromised credentials |
| Account Manipulation | T1098 | Credential modification |

---

## 2. Severity Classification

| Severity | Criteria | Response Time |
|----------|----------|---------------|
| **Critical** | Production AWS credentials or signing keys | Immediate (< 15 min) |
| **High** | Service account credentials or API tokens | < 1 hour |
| **Medium** | Development/test credentials | < 4 hours |
| **Low** | Expired or already-rotated credentials | < 24 hours |

---

## 3. Detection

### 3.1 Detection Sources

| Source | Alert Type | SNS Topic |
|--------|------------|-----------|
| SecretsDetectionService | Secret pattern detected | `aura-security-alerts-{env}` |
| Pre-commit Hook | Blocked commit with secrets | Local notification |
| GitHub Secret Scanning | Repository secret alert | GitHub notification |
| AWS GuardDuty | Compromised credentials | `aura-iam-security-alerts-{env}` |
| CloudTrail | Unusual API activity | `aura-security-alerts-{env}` |

### 3.2 Indicators of Compromise (IOCs)

**Exposure Vectors:**
- Secrets committed to git repository
- Secrets in CloudWatch logs
- Secrets in error messages/stack traces
- Secrets shared via Slack/email
- Secrets in public S3 buckets

**Compromise Indicators:**
- API calls from unexpected IP addresses
- Unusual resource creation/deletion
- Failed authentication followed by success
- Access from new geographic locations
- Off-hours activity patterns

### 3.3 Detection Commands

**Check for AWS Key Usage:**
```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=AccessKeyId,AttributeValue=${ACCESS_KEY_ID} \
  --start-time $(date -d '7 days ago' --iso-8601) \
  --query 'Events[*].{Time:EventTime,Event:EventName,Source:EventSource}'
```

**Search Logs for Secrets:**
```bash
aws logs filter-log-events \
  --log-group-name "/aura/${ENV}/application" \
  --filter-pattern "AKIA"  # AWS Access Key pattern
```

---

## 4. Containment

### 4.1 Immediate Actions (First 15 Minutes)

| Step | Action | Owner |
|------|--------|-------|
| 1 | Identify credential type and scope | On-Call Engineer |
| 2 | Disable/rotate the exposed credential | On-Call Engineer |
| 3 | Review access logs for unauthorized use | On-Call Engineer |
| 4 | Block source IP if active exploitation | On-Call Engineer |
| 5 | Preserve evidence | On-Call Engineer |

### 4.2 Credential-Specific Rotation

**AWS Access Keys:**
```bash
# Disable the compromised key
aws iam update-access-key \
  --user-name ${USER_NAME} \
  --access-key-id ${ACCESS_KEY_ID} \
  --status Inactive

# Create new key
aws iam create-access-key --user-name ${USER_NAME}

# Delete compromised key (after services updated)
aws iam delete-access-key \
  --user-name ${USER_NAME} \
  --access-key-id ${ACCESS_KEY_ID}
```

**IAM Role Session (if compromised):**
```bash
# Revoke all active sessions
aws iam put-role-policy \
  --role-name ${ROLE_NAME} \
  --policy-name DenyAllUntilRotation \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Deny",
      "Action": "*",
      "Resource": "*",
      "Condition": {
        "DateLessThan": {"aws:TokenIssueTime": "'$(date --iso-8601=seconds)'"}
      }
    }]
  }'
```

**GitHub Token:**
```bash
# Revoke via GitHub API
curl -X DELETE \
  -H "Authorization: token ${ADMIN_TOKEN}" \
  "https://api.github.com/applications/${CLIENT_ID}/token" \
  -d '{"access_token": "${COMPROMISED_TOKEN}"}'
```

**Database Credentials:**
```bash
# Rotate in Secrets Manager
aws secretsmanager rotate-secret \
  --secret-id aura/${ENV}/database-credentials
```

**JWT Signing Key:**
```bash
# Generate new key and update SSM
openssl genrsa -out new-signing-key.pem 4096
aws ssm put-parameter \
  --name "/aura/${ENV}/jwt-signing-key" \
  --value "$(cat new-signing-key.pem)" \
  --type SecureString \
  --overwrite
# Note: This will invalidate all existing JWTs
```

### 4.3 Network Containment

**Block Suspicious IP in WAF:**
```bash
aws wafv2 update-ip-set \
  --name aura-blocked-ips \
  --scope REGIONAL \
  --id ${IP_SET_ID} \
  --addresses ${MALICIOUS_IP}/32 \
  --lock-token ${LOCK_TOKEN}
```

### 4.4 Evidence Preservation

**Export CloudTrail Events:**
```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=AccessKeyId,AttributeValue=${ACCESS_KEY_ID} \
  --output json > /tmp/ir003-cloudtrail-evidence.json

aws s3 cp /tmp/ir003-cloudtrail-evidence.json \
  s3://aura-security-forensics-${ENV}/ir003/$(date +%Y%m%d)/
```

---

## 5. Eradication

### 5.1 Root Cause Analysis

| Question | Investigation Method |
|----------|---------------------|
| How was the credential exposed? | Git history, log analysis |
| Who had access to the credential? | IAM policy review |
| Was the credential used maliciously? | CloudTrail analysis |
| What resources were accessed? | Resource-level logging |
| Are other credentials at risk? | Secret scanning |

### 5.2 Clean Up Exposure

**Remove from Git History:**
```bash
# Use BFG Repo-Cleaner
java -jar bfg.jar --replace-text secrets.txt repo.git
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push (coordinate with team)
git push --force
```

**Remove from Logs:**
```bash
# Redact from CloudWatch (if possible)
# Note: Some logs may be immutable - document for compliance
```

### 5.3 Update Services

After rotation, update all services using the credential:
- [ ] Update SSM Parameter Store references
- [ ] Restart affected ECS services
- [ ] Update Lambda environment variables
- [ ] Verify CI/CD pipeline secrets
- [ ] Update Kubernetes secrets

---

## 6. Recovery

### 6.1 Service Restoration

| Step | Action | Verification |
|------|--------|--------------|
| 1 | Deploy new credentials to services | Services start successfully |
| 2 | Remove deny policies | IAM policy check |
| 3 | Verify application functionality | Health checks pass |
| 4 | Remove IP blocks (if appropriate) | WAF rule review |
| 5 | Enhanced monitoring | CloudWatch alarms |

### 6.2 Customer Notification

If customer data potentially accessed:
- [ ] Determine scope of accessed data
- [ ] Prepare customer notification
- [ ] Coordinate with legal/compliance
- [ ] Notify within required timeframes (72h GDPR)

---

## 7. Escalation Matrix

| Severity | Primary | Secondary | Executive |
|----------|---------|-----------|-----------|
| Critical | On-Call Engineer | Security Lead | CTO + Legal (within 1 hour) |
| High | On-Call Engineer | Security Lead | CTO (within 4 hours) |
| Medium | On-Call Engineer | Security Lead | Weekly report |
| Low | On-Call Engineer | - | Monthly report |

---

## 8. Post-Incident Activities

### 8.1 Incident Report
- [ ] Timeline of exposure and detection
- [ ] Credential type and scope
- [ ] Evidence of exploitation (if any)
- [ ] Actions taken
- [ ] Root cause and prevention measures

### 8.2 Prevention Measures
- [ ] Enhance pre-commit secret scanning
- [ ] Review secrets management practices
- [ ] Implement credential rotation schedule
- [ ] Add detection patterns for new secret types
- [ ] Security awareness training update

---

## Appendix A: Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│           CREDENTIAL EXPOSURE - QUICK REFERENCE             │
├─────────────────────────────────────────────────────────────┤
│ 1. IDENTIFY  - Determine credential type and exposure scope │
│ 2. DISABLE   - Immediately disable/rotate the credential    │
│ 3. AUDIT     - Check CloudTrail for unauthorized use        │
│ 4. BLOCK     - Add malicious IPs to WAF blocklist          │
│ 5. PRESERVE  - Export logs to forensics bucket              │
│ 6. CLEAN     - Remove from git history, logs, etc.          │
│ 7. UPDATE    - Deploy new credentials to all services       │
│ 8. MONITOR   - Enhanced alerting for 30 days                │
├─────────────────────────────────────────────────────────────┤
│ AWS KEYS: Disable immediately, then investigate             │
│ NEVER delete keys before preserving CloudTrail evidence     │
└─────────────────────────────────────────────────────────────┘
```

## Appendix B: Credential Rotation Quick Commands

| Credential Type | Rotation Command |
|----------------|------------------|
| AWS Access Key | `aws iam update-access-key --status Inactive` |
| Secrets Manager | `aws secretsmanager rotate-secret --secret-id` |
| SSM Parameter | `aws ssm put-parameter --overwrite` |
| GitHub Token | Revoke in GitHub Settings > Developer Settings |
| Database Password | `aws rds modify-db-instance --master-user-password` |
