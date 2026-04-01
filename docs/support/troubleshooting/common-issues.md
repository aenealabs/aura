# Common Issues

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This document covers frequently encountered issues that affect daily operations of Project Aura. Each issue includes symptoms, causes, diagnostic steps, and resolution procedures.

---

## Authentication Issues

### AURA-AUTH-001: Invalid or Expired Token

**Symptoms:**
- HTTP 401 Unauthorized response
- Error message: "Token validation failed" or "Token expired"
- Sudden logout from UI

**Causes:**
- JWT token has exceeded its TTL (default: 1 hour)
- Token was revoked due to password change or security event
- Clock skew between client and server

**Diagnostic Steps:**

```bash
# Decode JWT token to check expiration (without verification)
echo "${AURA_TOKEN}" | cut -d. -f2 | base64 -d 2>/dev/null | jq

# Example output showing expiration
{
  "sub": "user@example.com",
  "exp": 1737288000,  # Expiration timestamp
  "iat": 1737284400,  # Issued at timestamp
  "org_id": "org-12345"
}

# Check if token is expired
TOKEN_EXP=$(echo "${AURA_TOKEN}" | cut -d. -f2 | base64 -d 2>/dev/null | jq -r '.exp')
CURRENT_TIME=$(date +%s)
if [ "$CURRENT_TIME" -gt "$TOKEN_EXP" ]; then
  echo "Token is EXPIRED"
else
  echo "Token is VALID (expires in $((TOKEN_EXP - CURRENT_TIME)) seconds)"
fi
```

**Resolution:**

1. **Refresh the token** using the refresh endpoint:
   ```bash
   curl -X POST https://api.aenealabs.com/v1/auth/refresh \
     -H "Content-Type: application/json" \
     -d '{"refresh_token": "${REFRESH_TOKEN}"}'
   ```

2. **Re-authenticate** if refresh token is also expired:
   ```bash
   curl -X POST https://api.aenealabs.com/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com", "password": "****"}'
   ```

3. **Check clock synchronization** (for self-hosted):
   ```bash
   # Check NTP synchronization
   timedatectl status

   # Force NTP sync
   sudo systemctl restart chronyd
   ```

---

### AURA-AUTH-002: Insufficient Permissions

**Symptoms:**
- HTTP 403 Forbidden response
- Error message: "Access denied" or "Insufficient permissions"
- Specific operations fail while others succeed

**Causes:**
- User role does not include required permissions
- Organization-level restrictions
- Resource-level access control denies the operation

**Diagnostic Steps:**

```bash
# Check current user's roles and permissions
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/users/me | jq '.roles, .permissions'

# Example output
{
  "roles": ["developer"],
  "permissions": [
    "repositories:read",
    "vulnerabilities:read",
    "patches:read"
  ]
}
```

**Resolution:**

1. **Verify required permissions** for the operation:

   | Operation | Required Permission |
   |-----------|---------------------|
   | View repositories | `repositories:read` |
   | Connect repository | `repositories:write` |
   | View vulnerabilities | `vulnerabilities:read` |
   | Approve patches | `patches:approve` |
   | Configure HITL | `settings:admin` |
   | Manage users | `users:admin` |

2. **Request role change** from organization admin:
   - Navigate to Settings > Users > [Your Name]
   - Request additional role assignment

3. **Verify organization membership**:
   ```bash
   curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
     https://api.aenealabs.com/v1/organizations/current | jq
   ```

---

### AURA-AUTH-003: MFA Verification Failed

**Symptoms:**
- Login succeeds but MFA challenge fails
- Error message: "Invalid MFA code"
- Code works on retry after waiting

**Causes:**
- Time-based code expired (30-second window)
- Device clock out of sync with server
- MFA device deregistered or replaced

**Resolution:**

1. **Verify device time** is synchronized:
   - Mobile: Enable automatic date/time in settings
   - Hardware token: Check battery and time sync

2. **Wait for next code rotation** (30 seconds)

3. **Use backup codes** if available:
   ```bash
   curl -X POST https://api.aenealabs.com/v1/auth/mfa/verify \
     -H "Content-Type: application/json" \
     -d '{"code": "BACKUP-CODE-12345", "use_backup": true}'
   ```

4. **Re-enroll MFA device** through account recovery:
   - Contact organization admin
   - Or use account recovery: https://app.aenealabs.com/account/recovery

---

## API Request Errors

### AURA-API-001: Rate Limit Exceeded

**Symptoms:**
- HTTP 429 Too Many Requests response
- `Retry-After` header in response
- Error message: "Rate limit exceeded"

**Rate Limits:**

| Endpoint Category | Limit | Window |
|-------------------|-------|--------|
| Authentication | 10 requests | 1 minute |
| Read operations | 1000 requests | 1 minute |
| Write operations | 100 requests | 1 minute |
| Bulk operations | 10 requests | 1 minute |
| Webhook deliveries | 1000 events | 1 minute |

**Diagnostic Steps:**

```bash
# Check rate limit headers in response
curl -i -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/repositories

# Response headers
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1737288060
Retry-After: 45
```

**Resolution:**

1. **Implement exponential backoff**:
   ```python
   import time
   import requests

   def api_call_with_retry(url, headers, max_retries=5):
       for attempt in range(max_retries):
           response = requests.get(url, headers=headers)

           if response.status_code == 429:
               retry_after = int(response.headers.get('Retry-After', 60))
               wait_time = retry_after * (2 ** attempt)  # Exponential backoff
               print(f"Rate limited. Waiting {wait_time}s before retry...")
               time.sleep(wait_time)
               continue

           return response

       raise Exception("Max retries exceeded")
   ```

2. **Batch operations** where possible:
   ```bash
   # Instead of multiple individual calls
   # Use bulk endpoint
   curl -X POST https://api.aenealabs.com/v1/repositories/bulk \
     -H "Authorization: Bearer ${AURA_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"repository_ids": ["repo-1", "repo-2", "repo-3"]}'
   ```

3. **Request rate limit increase** for enterprise accounts:
   - Contact support@aenealabs.com with usage requirements

---

### AURA-API-002: Invalid Request Payload

**Symptoms:**
- HTTP 400 Bad Request response
- Error message includes field validation details
- Request rejected before processing

**Common Causes:**

| Error Detail | Cause | Fix |
|--------------|-------|-----|
| "missing required field: X" | Required field not provided | Add the field to request |
| "invalid type for field: X" | Wrong data type | Check expected type |
| "value out of range: X" | Value exceeds limits | Adjust value within limits |
| "invalid enum value: X" | Value not in allowed set | Use allowed value |

**Diagnostic Steps:**

```bash
# Validate JSON syntax
echo '{"name": "test"}' | jq .

# Check against schema (pseudo-code)
curl -s https://api.aenealabs.com/v1/schemas/repository | jq
```

**Resolution:**

1. **Review API documentation** for required fields:
   - See [REST API Reference](../api-reference/rest-api.md)

2. **Validate payload before sending**:
   ```python
   import jsonschema

   schema = {
       "type": "object",
       "required": ["name", "url"],
       "properties": {
           "name": {"type": "string", "minLength": 1, "maxLength": 100},
           "url": {"type": "string", "format": "uri"},
           "branch": {"type": "string", "default": "main"}
       }
   }

   payload = {"name": "my-repo", "url": "https://github.com/org/repo"}
   jsonschema.validate(payload, schema)  # Raises if invalid
   ```

3. **Check content-type header**:
   ```bash
   # Ensure Content-Type is set correctly
   curl -X POST https://api.aenealabs.com/v1/repositories \
     -H "Authorization: Bearer ${AURA_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"name": "my-repo", "url": "https://github.com/org/repo"}'
   ```

---

### AURA-API-003: Resource Not Found

**Symptoms:**
- HTTP 404 Not Found response
- Error message: "Resource not found"
- Previously accessible resource returns 404

**Causes:**
- Resource ID is incorrect or malformed
- Resource was deleted
- User lost access to the resource
- Resource is in a different organization

**Diagnostic Steps:**

```bash
# Verify resource ID format
# Expected format: {type}-{uuid}
# Example: repo-a1b2c3d4-e5f6-7890-abcd-ef1234567890

# List available resources
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/repositories | jq '.[].id'

# Check if resource exists in audit log
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  "https://api.aenealabs.com/v1/audit?resource_id=repo-12345" | jq
```

**Resolution:**

1. **Verify resource ID** is correct and complete

2. **Check resource access**:
   ```bash
   # Verify you can list resources of that type
   curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
     https://api.aenealabs.com/v1/repositories | jq 'length'
   ```

3. **Check organization context**:
   ```bash
   # Verify current organization
   curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
     https://api.aenealabs.com/v1/organizations/current | jq '.id, .name'
   ```

4. **Search by name** if ID is uncertain:
   ```bash
   curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
     "https://api.aenealabs.com/v1/repositories?name=my-repo" | jq
   ```

---

## Agent Issues

### AURA-AGT-001: Agent Timeout

**Symptoms:**
- Long-running operations never complete
- Error message: "Agent execution timeout"
- Partial results returned

**Timeout Limits:**

| Agent | Default Timeout | Maximum |
|-------|-----------------|---------|
| Orchestrator | 5 minutes | 15 minutes |
| Coder Agent | 10 minutes | 30 minutes |
| Reviewer Agent | 5 minutes | 15 minutes |
| Validator Agent | 15 minutes | 60 minutes |

**Diagnostic Steps:**

```bash
# Check agent execution history
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  "https://api.aenealabs.com/v1/agents/executions?status=timeout" | jq

# Check agent health
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/health/agents | jq

# For self-hosted: Check pod resource usage
kubectl top pods -n aura-system -l app=coder-agent
```

**Resolution:**

1. **Check for complex operations** that legitimately need more time:
   - Large codebases (>100k LOC)
   - Multiple vulnerability patches
   - Complex dependency graphs

2. **Increase timeout** (if authorized):
   ```bash
   curl -X PATCH https://api.aenealabs.com/v1/settings/agents \
     -H "Authorization: Bearer ${AURA_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"coder_timeout_seconds": 1200}'  # 20 minutes
   ```

3. **Break down large operations** into smaller batches:
   - Process one directory at a time
   - Limit vulnerabilities per batch

4. **Check for resource constraints** (self-hosted):
   ```bash
   # Increase agent resources
   kubectl patch deployment coder-agent -n aura-system --type=json \
     -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "8Gi"}]'
   ```

---

### AURA-AGT-002: Agent Communication Failure

**Symptoms:**
- Error message: "Failed to reach agent" or "Agent unavailable"
- Intermittent failures followed by success
- Operations hang indefinitely

**Causes:**
- Network connectivity issues
- Agent service crashed or not running
- DNS resolution failure
- TLS certificate problems

**Diagnostic Steps:**

```bash
# Self-hosted: Check agent pod status
kubectl get pods -n aura-system -l tier=agent

# Check agent logs
kubectl logs -n aura-system -l app=orchestrator --tail=100

# Test internal DNS resolution
kubectl run -it --rm debug --image=busybox --restart=Never -- \
  nslookup orchestrator.aura.local

# Test network connectivity
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v http://orchestrator.aura.local:8080/health
```

**Resolution:**

1. **Restart affected agent** (self-hosted):
   ```bash
   kubectl rollout restart deployment/orchestrator -n aura-system
   kubectl rollout status deployment/orchestrator -n aura-system
   ```

2. **Check DNS configuration**:
   ```bash
   # Verify dnsmasq is running
   kubectl get pods -n kube-system -l app=dnsmasq

   # Check DNS resolution
   kubectl run -it --rm dns-test --image=busybox --restart=Never -- \
     cat /etc/resolv.conf
   ```

3. **Verify network policies**:
   ```bash
   kubectl get networkpolicies -n aura-system
   kubectl describe networkpolicy aura-agent-policy -n aura-system
   ```

4. **Check for service mesh issues** (if applicable):
   ```bash
   # Verify sidecar injection
   kubectl get pod -n aura-system -o jsonpath='{.items[*].spec.containers[*].name}' | tr ' ' '\n' | sort | uniq -c
   ```

---

### AURA-AGT-003: Orchestrator Unavailable

**Symptoms:**
- All agent operations fail
- Error message: "Orchestrator service unavailable"
- Health endpoint returns unhealthy status

**Diagnostic Steps:**

```bash
# Check orchestrator health
curl -s https://api.aenealabs.com/v1/health/orchestrator | jq

# Self-hosted: Check orchestrator deployment
kubectl get deployment orchestrator -n aura-system
kubectl describe deployment orchestrator -n aura-system

# Check orchestrator logs
kubectl logs -n aura-system -l app=orchestrator --tail=200 | grep -i error
```

**Resolution:**

1. **Check database connectivity** (orchestrator depends on Neptune and DynamoDB):
   ```bash
   # Test Neptune connection
   aws neptune-db describe-db-cluster-endpoints \
     --db-cluster-identifier aura-neptune-cluster-${ENV}

   # Test DynamoDB
   aws dynamodb describe-table --table-name aura-agent-state-${ENV}
   ```

2. **Restart orchestrator**:
   ```bash
   kubectl rollout restart deployment/orchestrator -n aura-system
   ```

3. **Scale up replicas** if under heavy load:
   ```bash
   kubectl scale deployment/orchestrator -n aura-system --replicas=3
   ```

4. **Check resource limits**:
   ```bash
   kubectl describe pod -n aura-system -l app=orchestrator | grep -A10 "Limits:"
   ```

---

## Repository Connection Issues

### AURA-REPO-001: Git Clone Failed

**Symptoms:**
- Repository connection fails with "Clone failed"
- Error during initial repository scan
- SSH key or token authentication error

**Causes:**
- Invalid or expired credentials
- Repository does not exist or was renamed
- Network connectivity to Git provider
- Branch does not exist

**Diagnostic Steps:**

```bash
# Test Git credentials manually
git ls-remote https://github.com/org/repo.git

# For SSH authentication
ssh -T git@github.com

# Check repository exists via API
curl -s -H "Authorization: token ${GITHUB_TOKEN}" \
  https://api.github.com/repos/org/repo | jq '.id, .full_name'
```

**Resolution:**

1. **Regenerate credentials**:
   - GitHub: Settings > Developer settings > Personal access tokens
   - GitLab: Settings > Access Tokens

2. **Update credentials in Aura**:
   ```bash
   curl -X PATCH https://api.aenealabs.com/v1/integrations/github \
     -H "Authorization: Bearer ${AURA_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"access_token": "ghp_newtoken..."}'
   ```

3. **Verify repository permissions**:
   - Ensure token has `repo` scope (GitHub)
   - Ensure token has `read_repository` scope (GitLab)

4. **Check branch existence**:
   ```bash
   git ls-remote --heads https://github.com/org/repo.git main
   ```

---

## Notification Issues

### AURA-NOTIF-001: Email Notifications Not Received

**Symptoms:**
- HITL approval emails not delivered
- Alert notifications missing
- Notification history shows "sent" but not received

**Causes:**
- Email filtered to spam/junk
- SES sending limits reached
- Email address not verified (sandbox mode)
- SMTP configuration incorrect

**Diagnostic Steps:**

```bash
# Check notification delivery status
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  "https://api.aenealabs.com/v1/notifications?status=failed" | jq

# Check SES sending statistics (self-hosted)
aws ses get-send-statistics --region us-east-1

# Verify email is registered
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/users/me | jq '.email, .email_verified'
```

**Resolution:**

1. **Check spam/junk folder** - Add noreply@aenealabs.com to safe senders

2. **Verify email address**:
   ```bash
   curl -X POST https://api.aenealabs.com/v1/users/me/verify-email \
     -H "Authorization: Bearer ${AURA_TOKEN}"
   ```

3. **Check SES configuration** (self-hosted):
   ```bash
   # Move out of SES sandbox
   aws ses get-account-sending-enabled

   # Verify sending domain
   aws ses get-identity-verification-attributes \
     --identities aenealabs.com
   ```

4. **Configure alternative channels**:
   - Enable Slack notifications
   - Enable webhook notifications

---

### AURA-NOTIF-002: Slack Notifications Failed

**Symptoms:**
- Slack messages not appearing in channel
- Error: "Webhook delivery failed"
- Partial message delivery

**Diagnostic Steps:**

```bash
# Test webhook manually
curl -X POST ${SLACK_WEBHOOK_URL} \
  -H "Content-Type: application/json" \
  -d '{"text": "Test message from Aura"}'

# Check webhook configuration
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/integrations/slack | jq
```

**Resolution:**

1. **Regenerate webhook URL** in Slack:
   - Slack > Apps > Incoming Webhooks > Regenerate URL

2. **Update webhook in Aura**:
   ```bash
   curl -X PATCH https://api.aenealabs.com/v1/integrations/slack \
     -H "Authorization: Bearer ${AURA_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"webhook_url": "https://hooks.slack.com/services/NEW/WEBHOOK/URL"}'
   ```

3. **Verify channel permissions**:
   - Ensure the Aura app is added to the target channel
   - Check channel is not archived

---

## Quick Reference: Error Code Index

| Error Code | Issue | Resolution Link |
|------------|-------|-----------------|
| AURA-AUTH-001 | Invalid/expired token | [Token refresh](#aura-auth-001-invalid-or-expired-token) |
| AURA-AUTH-002 | Insufficient permissions | [RBAC check](#aura-auth-002-insufficient-permissions) |
| AURA-AUTH-003 | MFA failed | [MFA troubleshooting](#aura-auth-003-mfa-verification-failed) |
| AURA-API-001 | Rate limit exceeded | [Rate limiting](#aura-api-001-rate-limit-exceeded) |
| AURA-API-002 | Invalid payload | [Payload validation](#aura-api-002-invalid-request-payload) |
| AURA-API-003 | Resource not found | [Resource lookup](#aura-api-003-resource-not-found) |
| AURA-AGT-001 | Agent timeout | [Timeout adjustment](#aura-agt-001-agent-timeout) |
| AURA-AGT-002 | Communication failure | [Network check](#aura-agt-002-agent-communication-failure) |
| AURA-AGT-003 | Orchestrator unavailable | [Service recovery](#aura-agt-003-orchestrator-unavailable) |

---

## Related Documentation

- [Troubleshooting Index](./index.md)
- [Deployment Issues](./deployment-issues.md)
- [Performance Issues](./performance-issues.md)
- [Security Issues](./security-issues.md)
- [API Reference](../api-reference/rest-api.md)

---

*Last updated: January 2026 | Version 1.0*
