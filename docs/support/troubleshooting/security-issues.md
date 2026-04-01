# Security Issues

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This document covers security-related issues including authentication failures, authorization problems, certificate errors, secrets management issues, and IAM permission errors. Use this guide for access control problems and security-related troubleshooting.

---

## Authentication Issues

### AURA-SEC-001: SSO Authentication Failed

**Symptoms:**
- SAML/OIDC login fails
- Redirect loop during authentication
- Error: "Authentication failed" or "Invalid SAML response"

**Common Causes:**

| Error | Cause | Resolution |
|-------|-------|------------|
| Invalid signature | Certificate mismatch | Update IdP certificate |
| Audience mismatch | Wrong client ID | Verify OIDC configuration |
| Clock skew | Time difference >5min | Sync server clocks |
| Expired assertion | SAML assertion too old | Check IdP time settings |

**Diagnostic Steps:**

```bash
# Check SAML response (from browser developer tools)
# Network tab > POST to /auth/saml/callback > Request payload

# Decode SAML response
echo "${SAML_RESPONSE}" | base64 -d | xmllint --format -

# Check key elements:
# - <saml:Issuer> matches expected IdP
# - <saml:Conditions NotBefore/NotOnOrAfter> are valid
# - <ds:SignatureValue> is present
# - <saml:Audience> matches Aura SP entity ID

# Verify OIDC configuration
curl -s https://login.microsoftonline.com/${TENANT_ID}/.well-known/openid-configuration | jq
```

**Resolution:**

**1. Update IdP Certificate:**

```bash
# Download new certificate from IdP
curl -o idp-cert.pem https://idp.example.com/certificate

# Update Aura SSO configuration
curl -X PUT -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  https://api.aenealabs.com/v1/settings/sso \
  -H "Content-Type: application/json" \
  -d "{\"idp_certificate\": \"$(cat idp-cert.pem | base64)\"}"
```

**2. Fix Audience/Entity ID Mismatch:**

```bash
# Verify Aura SP entity ID
curl -s -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  https://api.aenealabs.com/v1/settings/sso | jq '.sp_entity_id'

# Update IdP to use correct audience
# Example: https://api.aenealabs.com/saml/metadata
```

**3. Clock Synchronization:**

```bash
# Check server time
date -u

# Enable NTP synchronization
sudo timedatectl set-ntp true
sudo systemctl restart chronyd
```

---

### AURA-SEC-002: JWT Token Validation Failed

**Symptoms:**
- API calls rejected with 401
- Error: "Invalid token" or "Token signature verification failed"
- Token works in some environments but not others

**Diagnostic Steps:**

```bash
# Decode JWT header and payload (without verification)
echo "${AURA_TOKEN}" | cut -d. -f1 | base64 -d 2>/dev/null | jq
echo "${AURA_TOKEN}" | cut -d. -f2 | base64 -d 2>/dev/null | jq

# Check token structure
# Header should contain: alg (RS256), typ (JWT), kid (key ID)
# Payload should contain: sub, exp, iat, org_id, roles

# Verify expiration
TOKEN_EXP=$(echo "${AURA_TOKEN}" | cut -d. -f2 | base64 -d 2>/dev/null | jq -r '.exp')
echo "Expires: $(date -d @${TOKEN_EXP})"
echo "Current: $(date)"

# Check issuer matches expected
echo "${AURA_TOKEN}" | cut -d. -f2 | base64 -d 2>/dev/null | jq -r '.iss'
# Expected: https://auth.aenealabs.com
```

**Common Validation Failures:**

| Error | Cause | Fix |
|-------|-------|-----|
| "Token expired" | exp claim in past | Refresh token |
| "Invalid issuer" | iss claim wrong | Use correct auth endpoint |
| "Invalid audience" | aud claim wrong | Verify API endpoint |
| "Invalid signature" | Key rotation | Clear cached keys |
| "Key not found" | kid not in JWKS | Refresh JWKS cache |

**Resolution:**

```bash
# Refresh JWKS cache (self-hosted)
kubectl delete configmap jwks-cache -n aura-system --ignore-not-found
kubectl rollout restart deployment/aura-api -n aura-system

# Force new token generation
curl -X POST https://api.aenealabs.com/v1/auth/token/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "${REFRESH_TOKEN}"}'

# Verify JWKS endpoint is accessible
curl -s https://auth.aenealabs.com/.well-known/jwks.json | jq '.keys | length'
```

---

### AURA-SEC-003: Session Hijacking Detected

**Symptoms:**
- Error: "Session invalidated due to security policy"
- Forced logout with security warning
- Email notification of suspicious activity

**Security Controls Triggered:**

| Control | Trigger | Action |
|---------|---------|--------|
| IP change detection | Session used from different IP | Session terminated |
| User-agent change | Different browser/device | Session terminated |
| Geographic anomaly | Login from unusual location | MFA required |
| Concurrent sessions | Too many active sessions | Oldest terminated |

**Diagnostic Steps:**

```bash
# Check active sessions
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/users/me/sessions | jq

# Review security audit log
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  "https://api.aenealabs.com/v1/audit?event_type=security&user_id=me&limit=20" | jq
```

**Resolution:**

```bash
# If legitimate access, whitelist IP/location
curl -X POST -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/settings/security/trusted-ips \
  -H "Content-Type: application/json" \
  -d '{"ip": "203.0.113.50", "description": "Office VPN egress"}'

# Terminate all sessions and re-authenticate
curl -X DELETE -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/users/me/sessions/all

# Enable additional security controls
curl -X PATCH -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/users/me/security \
  -H "Content-Type: application/json" \
  -d '{"require_mfa_for_sensitive_actions": true}'
```

---

## Authorization Issues

### AURA-SEC-004: RBAC Permission Denied

**Symptoms:**
- HTTP 403 Forbidden on specific operations
- Error: "Action not permitted for role"
- Some features inaccessible in UI

**Aura RBAC Model:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                       AURA RBAC HIERARCHY                            │
└─────────────────────────────────────────────────────────────────────┘

Organization Admin
    │
    ├── Security Admin ─────────┐
    │   - Manage HITL policies  │
    │   - Review patches        │
    │   - Access audit logs     │
    │                           │
    ├── Developer ──────────────┤
    │   - Connect repositories  │ (Resource-level permissions
    │   - View vulnerabilities  │  within assigned projects)
    │   - View patches          │
    │                           │
    └── Viewer ─────────────────┘
        - Read-only access
        - View dashboards
```

**Permission Matrix:**

| Action | Org Admin | Security Admin | Developer | Viewer |
|--------|-----------|----------------|-----------|--------|
| Manage users | X | - | - | - |
| Configure SSO | X | - | - | - |
| Manage HITL policies | X | X | - | - |
| Approve patches | X | X | - | - |
| Connect repositories | X | X | X | - |
| View vulnerabilities | X | X | X | X |
| View audit logs | X | X | - | - |

**Diagnostic Steps:**

```bash
# Check current user roles
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/users/me | jq '.roles'

# Check effective permissions
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/users/me/permissions | jq

# Check resource-specific access
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/repositories/${REPO_ID}/access | jq

# Check role requirements for action
curl -s https://api.aenealabs.com/v1/permissions/matrix | jq '.["patches:approve"]'
```

**Resolution:**

```bash
# Request role assignment (requires admin)
# Contact organization admin to assign appropriate role

# Self-service: Request project access
curl -X POST -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/access-requests \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "repository",
    "resource_id": "repo-12345",
    "requested_role": "developer",
    "justification": "Need to review vulnerabilities for Project X"
  }'
```

---

### AURA-SEC-005: Resource Access Denied

**Symptoms:**
- Can access some resources but not others
- Error: "Resource not accessible"
- Resource visible in list but details return 403

**Diagnostic Steps:**

```bash
# Check resource ownership
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/repositories/${REPO_ID} | jq '.owner, .team'

# Check team membership
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/users/me/teams | jq '.[].name'

# Check resource permissions
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/repositories/${REPO_ID}/permissions | jq
```

**Resolution:**

```bash
# Join team that owns resource
curl -X POST -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/teams/${TEAM_ID}/membership-request \
  -H "Content-Type: application/json" \
  -d '{"justification": "Working on related project"}'

# Transfer resource ownership (requires current owner)
curl -X PATCH -H "Authorization: Bearer ${OWNER_TOKEN}" \
  https://api.aenealabs.com/v1/repositories/${REPO_ID} \
  -H "Content-Type: application/json" \
  -d '{"team_id": "team-new-owner"}'
```

---

## Certificate and TLS Issues

### AURA-SEC-006: TLS Certificate Errors

**Symptoms:**
- "Certificate verification failed"
- "SSL: CERTIFICATE_VERIFY_FAILED"
- Browser shows certificate warning

**Common Certificate Issues:**

| Error | Cause | Resolution |
|-------|-------|------------|
| Expired certificate | Cert past valid date | Renew certificate |
| Wrong hostname | Cert CN/SAN mismatch | Use correct hostname |
| Self-signed | Not trusted by client | Add to trust store |
| Incomplete chain | Missing intermediate | Include full chain |
| Revoked | Cert on CRL/OCSP | Get new certificate |

**Diagnostic Steps:**

```bash
# Check certificate details
openssl s_client -connect api.aenealabs.com:443 -servername api.aenealabs.com </dev/null 2>/dev/null | openssl x509 -noout -text | head -30

# Check certificate expiration
openssl s_client -connect api.aenealabs.com:443 -servername api.aenealabs.com </dev/null 2>/dev/null | openssl x509 -noout -dates

# Verify certificate chain
openssl s_client -connect api.aenealabs.com:443 -servername api.aenealabs.com -showcerts </dev/null 2>/dev/null

# Check for hostname match
openssl s_client -connect api.aenealabs.com:443 -servername api.aenealabs.com </dev/null 2>/dev/null | openssl x509 -noout -ext subjectAltName
```

**Resolution:**

**1. Renew Expired Certificate (ACM):**

```bash
# Request new certificate
aws acm request-certificate \
  --domain-name api.aenealabs.com \
  --validation-method DNS \
  --subject-alternative-names "*.aenealabs.com"

# Validate via DNS (create CNAME record)
aws acm describe-certificate \
  --certificate-arn ${CERT_ARN} \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord'
```

**2. Update Load Balancer Certificate:**

```bash
# List current certificates
aws elbv2 describe-listeners \
  --load-balancer-arn ${ALB_ARN} \
  --query 'Listeners[*].Certificates'

# Update to new certificate
aws elbv2 modify-listener \
  --listener-arn ${LISTENER_ARN} \
  --certificates CertificateArn=${NEW_CERT_ARN}
```

**3. Add CA to Trust Store (Self-Hosted):**

```bash
# Copy CA certificate to trust store
sudo cp custom-ca.crt /etc/pki/ca-trust/source/anchors/
sudo update-ca-trust

# For Python applications
export REQUESTS_CA_BUNDLE=/path/to/ca-bundle.crt
```

---

### AURA-SEC-007: mTLS Authentication Failed

**Symptoms:**
- Client certificate rejected
- Error: "Bad certificate" or "Certificate required"
- Connection closed during TLS handshake

**Diagnostic Steps:**

```bash
# Test with client certificate
curl -v --cert client.crt --key client.key \
  https://api.aenealabs.com/v1/health

# Verify client certificate
openssl x509 -in client.crt -noout -text | head -20

# Check certificate against CA
openssl verify -CAfile ca.crt client.crt

# Check key matches certificate
openssl x509 -in client.crt -noout -modulus | md5sum
openssl rsa -in client.key -noout -modulus | md5sum
# (Should match)
```

**Resolution:**

```bash
# Generate new client certificate (if allowed)
# Create CSR
openssl req -new -key client.key -out client.csr \
  -subj "/CN=service-account/O=aura-system"

# Submit CSR for signing (organization-specific process)
curl -X POST -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  https://api.aenealabs.com/v1/certificates/sign \
  -H "Content-Type: application/json" \
  -d "{\"csr\": \"$(cat client.csr | base64)\"}"

# Update Kubernetes secret with new cert
kubectl create secret tls client-cert -n aura-system \
  --cert=client.crt --key=client.key --dry-run=client -o yaml | \
  kubectl apply -f -
```

---

## Secrets Management Issues

### AURA-SEC-008: Secret Retrieval Failed

**Symptoms:**
- Application fails to start with "secret not found"
- Error: "Access to secret denied"
- Environment variables empty

**Diagnostic Steps:**

```bash
# Check if secret exists in Secrets Manager
aws secretsmanager describe-secret \
  --secret-id aura/${ENV}/api-keys

# Check IAM permissions for secret access
aws iam simulate-principal-policy \
  --policy-source-arn ${ROLE_ARN} \
  --action-names secretsmanager:GetSecretValue \
  --resource-arns arn:aws:secretsmanager:${REGION}:${ACCOUNT}:secret:aura/${ENV}/api-keys

# Self-hosted: Check pod service account
kubectl get pod ${POD_NAME} -n aura-system -o jsonpath='{.spec.serviceAccountName}'
kubectl describe serviceaccount ${SA_NAME} -n aura-system
```

**Resolution:**

```bash
# Grant secret access via IAM policy
aws iam put-role-policy \
  --role-name aura-api-role-${ENV} \
  --policy-name secrets-access \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "arn:aws:secretsmanager:'${REGION}':'${ACCOUNT}':secret:aura/'${ENV}'/*"
    }]
  }'

# Create missing secret
aws secretsmanager create-secret \
  --name aura/${ENV}/api-keys \
  --secret-string '{"github_token": "ghp_xxx", "slack_webhook": "https://hooks.slack.com/xxx"}'

# For Kubernetes: Create ExternalSecret
kubectl apply -f - <<EOF
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: aura-api-secrets
  namespace: aura-system
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: aura-api-secrets
  data:
  - secretKey: github-token
    remoteRef:
      key: aura/${ENV}/api-keys
      property: github_token
EOF
```

---

### AURA-SEC-009: Secret Rotation Failed

**Symptoms:**
- Secret rotation Lambda failed
- Old secret value still in use
- Error: "Previous secret version not found"

**Diagnostic Steps:**

```bash
# Check rotation status
aws secretsmanager describe-secret \
  --secret-id aura/${ENV}/database-credentials \
  --query '[RotationEnabled,RotationRules,LastRotatedDate]'

# Check rotation Lambda logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/aura-secret-rotation-${ENV} \
  --start-time $(date -d '1 hour ago' +%s000) \
  --filter-pattern "ERROR"

# Get secret version stages
aws secretsmanager list-secret-version-ids \
  --secret-id aura/${ENV}/database-credentials \
  --query 'Versions[*].[VersionId,VersionStages]'
```

**Resolution:**

```bash
# Manual rotation
aws secretsmanager rotate-secret \
  --secret-id aura/${ENV}/database-credentials

# If stuck, reset pending version
aws secretsmanager update-secret-version-stage \
  --secret-id aura/${ENV}/database-credentials \
  --version-stage AWSPENDING \
  --remove-from-version-id ${STUCK_VERSION_ID}

# Re-trigger rotation
aws secretsmanager rotate-secret \
  --secret-id aura/${ENV}/database-credentials \
  --rotation-lambda-arn arn:aws:lambda:${REGION}:${ACCOUNT}:function:aura-secret-rotation-${ENV}
```

---

## IAM Permission Issues

### AURA-SEC-010: IAM Access Denied

**Symptoms:**
- AWS API calls fail with "Access Denied"
- CloudFormation shows "Resource handler returned message: Access Denied"
- EKS pods cannot access AWS services

**Diagnostic Steps:**

```bash
# Identify which action is denied
# Check CloudTrail for AccessDenied events
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=AccessDenied \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --query 'Events[*].CloudTrailEvent' | jq -r '.[] | fromjson | .errorMessage'

# Simulate IAM policy
aws iam simulate-principal-policy \
  --policy-source-arn ${ROLE_ARN} \
  --action-names ${ACTION} \
  --resource-arns ${RESOURCE_ARN}

# Check IRSA configuration (EKS)
kubectl describe serviceaccount ${SA_NAME} -n aura-system | grep "eks.amazonaws.com/role-arn"

# Verify trust relationship
aws iam get-role --role-name ${ROLE_NAME} --query 'Role.AssumeRolePolicyDocument'
```

**Common Permission Issues:**

| Service | Common Missing Permission | Required For |
|---------|---------------------------|--------------|
| Neptune | `neptune-db:connect` | Database connection |
| OpenSearch | `es:ESHttpGet/Post` | Search queries |
| Bedrock | `bedrock:InvokeModel` | LLM calls |
| S3 | `s3:GetObject/PutObject` | File storage |
| STS | `sts:AssumeRole` | Cross-account access |
| Secrets Manager | `secretsmanager:GetSecretValue` | Secret retrieval |

**Resolution:**

```bash
# Add missing permission to IAM policy
aws iam put-role-policy \
  --role-name aura-api-role-${ENV} \
  --policy-name missing-permission \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["'${MISSING_ACTION}'"],
      "Resource": "'${RESOURCE_ARN}'"
    }]
  }'

# For IRSA, update IAM role trust policy
aws iam update-assume-role-policy \
  --role-name aura-api-role-${ENV} \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::'${ACCOUNT}':oidc-provider/'${OIDC_PROVIDER}'"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "'${OIDC_PROVIDER}':sub": "system:serviceaccount:aura-system:'${SA_NAME}'"
        }
      }
    }]
  }'
```

---

### AURA-SEC-011: Service Control Policy (SCP) Blocking

**Symptoms:**
- Actions that work in dev fail in prod
- Error: "Access denied due to SCP"
- Account-level restrictions preventing operations

**Diagnostic Steps:**

```bash
# Check effective policies
aws organizations list-policies-for-target \
  --target-id ${ACCOUNT_ID} \
  --filter SERVICE_CONTROL_POLICY

# Get SCP content
aws organizations describe-policy \
  --policy-id ${POLICY_ID} \
  --query 'Policy.Content'

# Test against SCP
aws accessanalyzer validate-policy \
  --policy-document file://policy.json \
  --policy-type SERVICE_CONTROL_POLICY
```

**Resolution:**

```bash
# Request SCP exception (requires org admin)
# Or modify application to use allowed actions

# Common SCP restrictions and workarounds:
# - Region restriction: Deploy in allowed regions
# - Service restriction: Use allowed alternatives
# - Tag requirement: Add required tags to resources
```

---

## Security Audit Quick Reference

### Security Health Check Commands

```bash
# Check for exposed secrets in logs
kubectl logs -n aura-system -l app=aura-api --since=1h | \
  grep -iE "(password|secret|key|token).*=" | head

# Verify TLS versions
nmap --script ssl-enum-ciphers -p 443 api.aenealabs.com

# Check for public S3 buckets
aws s3api get-bucket-policy-status --bucket aura-artifacts-${ENV}
aws s3api get-public-access-block --bucket aura-artifacts-${ENV}

# Verify encryption at rest
aws rds describe-db-instances --query 'DBInstances[*].[DBInstanceIdentifier,StorageEncrypted]'
aws s3api get-bucket-encryption --bucket aura-artifacts-${ENV}
```

### Compliance Verification

```bash
# Check AWS Config compliance
aws configservice get-compliance-summary-by-config-rule

# List non-compliant resources
aws configservice get-compliance-details-by-config-rule \
  --config-rule-name encrypted-volumes \
  --compliance-types NON_COMPLIANT

# GuardDuty findings
aws guardduty list-findings \
  --detector-id ${DETECTOR_ID} \
  --finding-criteria '{"Criterion":{"severity":{"Gte":7}}}'
```

---

## Related Documentation

- [Troubleshooting Index](./index.md)
- [Common Issues](./common-issues.md)
- [Security Architecture](../architecture/security-architecture.md)
- [Compliance Profiles](../../security/COMPLIANCE_PROFILES.md)
- [Developer Security Guidelines](../../security/DEVELOPER_SECURITY_GUIDELINES.md)

---

*Last updated: January 2026 | Version 1.0*
