# User Management

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This guide covers user and access management in Project Aura, including creating users, configuring role-based access control (RBAC), managing teams and organizations, and handling API keys and service accounts for CI/CD integration.

---

## User Management Architecture

```
+-----------------------------------------------------------------------------+
|                         USER MANAGEMENT ARCHITECTURE                         |
+-----------------------------------------------------------------------------+

    +-------------------------+     +-------------------------+
    |     IDENTITY SOURCES    |     |    ACCESS CONTROL       |
    |  +-------------------+  |     |  +-------------------+  |
    |  |   Local Auth      |  |     |  |   RBAC Engine     |  |
    |  |   SSO (SAML/OIDC) |  |---->|  |   - Roles         |  |
    |  |   API Keys        |  |     |  |   - Permissions   |  |
    |  |   Service Accounts|  |     |  |   - Policies      |  |
    |  +-------------------+  |     |  +-------------------+  |
    +-------------------------+     +------------+------------+
                                                 |
                                                 v
    +-----------------------------------------------------------------------------+
    |                           ORGANIZATION HIERARCHY                             |
    |                                                                              |
    |  +--------------------+                                                     |
    |  |   Organization     |  (Top-level tenant)                                |
    |  +--------------------+                                                     |
    |            |                                                                |
    |    +-------+-------+                                                        |
    |    |               |                                                        |
    |    v               v                                                        |
    |  +--------+     +--------+                                                  |
    |  |  Team  |     |  Team  |  (Functional groups)                            |
    |  +--------+     +--------+                                                  |
    |       |              |                                                      |
    |   +---+---+      +---+---+                                                  |
    |   |       |      |       |                                                  |
    |   v       v      v       v                                                  |
    | [User] [User]  [User] [User]  (Individual accounts)                        |
    |                                                                              |
    +-----------------------------------------------------------------------------+
```

---

## Creating and Managing Users

### Creating Users via Dashboard

1. Navigate to **Settings > Users**
2. Click **Add User**
3. Enter user details:

   | Field | Required | Description |
   |-------|----------|-------------|
   | Email | Yes | Unique email address |
   | Name | Yes | Display name |
   | Role | Yes | Initial role assignment |
   | Teams | No | Team membership |
   | Send Invite | Yes | Email invitation to user |

4. Click **Create User**

### Creating Users via API

```bash
# Create a new user
curl -X POST https://api.aenealabs.com/v1/users \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "developer@yourcompany.com",
    "name": "Jane Developer",
    "role": "developer",
    "teams": ["engineering", "security"],
    "sendInvite": true
  }'
```

Response:

```json
{
  "id": "user-abc123",
  "email": "developer@yourcompany.com",
  "name": "Jane Developer",
  "role": "developer",
  "status": "pending",
  "teams": ["engineering", "security"],
  "createdAt": "2026-01-19T10:00:00Z",
  "inviteSentAt": "2026-01-19T10:00:01Z"
}
```

### Creating Users via CLI (Self-Hosted)

```bash
# Kubernetes deployment
kubectl exec -it deployment/aura-api -n aura-system -- \
  aura-cli user create \
    --email developer@yourcompany.com \
    --name "Jane Developer" \
    --role developer \
    --teams engineering,security

# Podman deployment
podman exec aura-api aura-cli user create \
  --email developer@yourcompany.com \
  --name "Jane Developer" \
  --role developer \
  --teams engineering,security
```

### Bulk User Import

Import multiple users from CSV:

```csv
email,name,role,teams
alice@company.com,Alice Smith,developer,"engineering,frontend"
bob@company.com,Bob Jones,security_analyst,security
carol@company.com,Carol Williams,admin,"engineering,security"
```

```bash
# Import via API
curl -X POST https://api.aenealabs.com/v1/users/import \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -F "file=@users.csv" \
  -F "sendInvites=true"

# Import via CLI
aura-cli user import --file users.csv --send-invites
```

### User Lifecycle Management

| Status | Description | Actions |
|--------|-------------|---------|
| `pending` | Invitation sent, not accepted | Resend invite, cancel invite |
| `active` | Account active and usable | Disable, modify, delete |
| `disabled` | Account suspended | Enable, delete |
| `deleted` | Account removed | (Soft delete, retained for audit) |

```bash
# Disable a user
curl -X PATCH https://api.aenealabs.com/v1/users/user-abc123 \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"status": "disabled"}'

# Re-enable a user
curl -X PATCH https://api.aenealabs.com/v1/users/user-abc123 \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"status": "active"}'

# Delete a user (soft delete)
curl -X DELETE https://api.aenealabs.com/v1/users/user-abc123 \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

---

## Role-Based Access Control (RBAC)

### Built-in Roles

Project Aura includes pre-defined roles with progressively expanding permissions:

| Role | Description | Key Permissions |
|------|-------------|-----------------|
| `viewer` | Read-only access | View repositories, vulnerabilities, patches |
| `developer` | Standard development access | Above + trigger scans, view details |
| `security_analyst` | Security-focused access | Above + approve/reject patches, manage policies |
| `team_admin` | Team management | Above + manage team members, team settings |
| `admin` | Full administrative access | Above + manage users, organization settings, integrations |
| `owner` | Organization owner | All permissions including billing and deletion |

### Permission Matrix

| Permission | Viewer | Developer | Security Analyst | Team Admin | Admin | Owner |
|------------|--------|-----------|------------------|------------|-------|-------|
| View repositories | Yes | Yes | Yes | Yes | Yes | Yes |
| View vulnerabilities | Yes | Yes | Yes | Yes | Yes | Yes |
| View patches | Yes | Yes | Yes | Yes | Yes | Yes |
| Trigger scans | - | Yes | Yes | Yes | Yes | Yes |
| View scan details | - | Yes | Yes | Yes | Yes | Yes |
| Approve patches | - | - | Yes | Yes | Yes | Yes |
| Reject patches | - | - | Yes | Yes | Yes | Yes |
| Manage HITL policies | - | - | Yes | Yes | Yes | Yes |
| Manage team members | - | - | - | Yes | Yes | Yes |
| Manage team settings | - | - | - | Yes | Yes | Yes |
| Manage all users | - | - | - | - | Yes | Yes |
| Manage integrations | - | - | - | - | Yes | Yes |
| Manage organization | - | - | - | - | Yes | Yes |
| Manage billing | - | - | - | - | - | Yes |
| Delete organization | - | - | - | - | - | Yes |

### Custom Roles (Enterprise Edition)

Enterprise Edition supports custom roles with granular permissions:

```bash
# Create a custom role
curl -X POST https://api.aenealabs.com/v1/roles \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "compliance_officer",
    "displayName": "Compliance Officer",
    "description": "Read-only access with audit log viewing",
    "permissions": [
      "repositories:read",
      "vulnerabilities:read",
      "patches:read",
      "audit_logs:read",
      "compliance_reports:read",
      "compliance_reports:export"
    ]
  }'
```

### Available Permissions

| Category | Permission | Description |
|----------|------------|-------------|
| **Repositories** | `repositories:read` | View repositories |
| | `repositories:write` | Add/modify repositories |
| | `repositories:delete` | Remove repositories |
| **Vulnerabilities** | `vulnerabilities:read` | View vulnerabilities |
| | `vulnerabilities:write` | Modify vulnerability status |
| **Patches** | `patches:read` | View patches |
| | `patches:approve` | Approve patches |
| | `patches:reject` | Reject patches |
| | `patches:deploy` | Deploy approved patches |
| **Scans** | `scans:read` | View scan results |
| | `scans:trigger` | Trigger new scans |
| | `scans:cancel` | Cancel running scans |
| **Users** | `users:read` | View users |
| | `users:write` | Create/modify users |
| | `users:delete` | Remove users |
| **Teams** | `teams:read` | View teams |
| | `teams:write` | Create/modify teams |
| | `teams:delete` | Remove teams |
| **Policies** | `policies:read` | View HITL policies |
| | `policies:write` | Modify HITL policies |
| **Integrations** | `integrations:read` | View integrations |
| | `integrations:write` | Manage integrations |
| **Audit** | `audit_logs:read` | View audit logs |
| | `audit_logs:export` | Export audit logs |
| **Admin** | `organization:manage` | Manage organization settings |
| | `billing:manage` | Manage billing |

### Assigning Roles

```bash
# Assign role to user
curl -X PATCH https://api.aenealabs.com/v1/users/user-abc123 \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"role": "security_analyst"}'

# Assign custom role (Enterprise)
curl -X PATCH https://api.aenealabs.com/v1/users/user-abc123 \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"role": "compliance_officer"}'
```

---

## Organization and Team Structure

### Organization Hierarchy

```
Organization (yourcompany)
|
+-- Team: Engineering
|   +-- User: alice@yourcompany.com (developer)
|   +-- User: bob@yourcompany.com (developer)
|
+-- Team: Security
|   +-- User: carol@yourcompany.com (security_analyst)
|   +-- User: dave@yourcompany.com (security_analyst)
|
+-- Team: Platform
|   +-- User: eve@yourcompany.com (admin)
|   +-- User: frank@yourcompany.com (developer)
```

### Creating Teams

```bash
# Create a team
curl -X POST https://api.aenealabs.com/v1/teams \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "security",
    "displayName": "Security Team",
    "description": "Security engineering and vulnerability management",
    "repositories": ["repo-123", "repo-456"],
    "defaultRole": "security_analyst"
  }'
```

Response:

```json
{
  "id": "team-sec123",
  "name": "security",
  "displayName": "Security Team",
  "description": "Security engineering and vulnerability management",
  "repositories": ["repo-123", "repo-456"],
  "defaultRole": "security_analyst",
  "memberCount": 0,
  "createdAt": "2026-01-19T10:00:00Z"
}
```

### Managing Team Membership

```bash
# Add user to team
curl -X POST https://api.aenealabs.com/v1/teams/team-sec123/members \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "user-abc123",
    "teamRole": "member"
  }'

# Remove user from team
curl -X DELETE https://api.aenealabs.com/v1/teams/team-sec123/members/user-abc123 \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"

# List team members
curl -X GET https://api.aenealabs.com/v1/teams/team-sec123/members \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

### Team Roles

| Team Role | Description |
|-----------|-------------|
| `member` | Standard team member |
| `lead` | Team lead with additional permissions |
| `admin` | Team administrator |

### Repository Access by Team

Teams can be granted access to specific repositories:

```bash
# Grant team access to repository
curl -X POST https://api.aenealabs.com/v1/repositories/repo-123/teams \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "teamId": "team-sec123",
    "accessLevel": "write"
  }'
```

| Access Level | Description |
|--------------|-------------|
| `read` | View repository, vulnerabilities, patches |
| `write` | Above + trigger scans, approve patches |
| `admin` | Above + modify repository settings |

---

## API Key Management

API keys enable programmatic access to the Aura API for automation and integrations.

### Creating API Keys

#### Via Dashboard

1. Navigate to **Settings > API Keys**
2. Click **Create API Key**
3. Configure the key:

   | Field | Description |
   |-------|-------------|
   | Name | Descriptive name for the key |
   | Scopes | Permissions granted to this key |
   | Expiration | Optional expiration date |
   | IP Restrictions | Optional IP allowlist |

4. Copy and securely store the key (shown only once)

#### Via API

```bash
# Create API key
curl -X POST https://api.aenealabs.com/v1/api-keys \
  -H "Authorization: Bearer ${USER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "CI/CD Pipeline - Production",
    "scopes": ["scans:trigger", "scans:read", "vulnerabilities:read"],
    "expiresAt": "2027-01-19T00:00:00Z",
    "ipRestrictions": ["10.0.0.0/8", "192.168.1.0/24"]
  }'
```

Response:

```json
{
  "id": "key-xyz789",
  "name": "CI/CD Pipeline - Production",
  "key": "aura_sk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "scopes": ["scans:trigger", "scans:read", "vulnerabilities:read"],
  "expiresAt": "2027-01-19T00:00:00Z",
  "ipRestrictions": ["10.0.0.0/8", "192.168.1.0/24"],
  "createdAt": "2026-01-19T10:00:00Z"
}
```

> **Security Best Practice:** API keys are shown only once upon creation. Store them securely in a secrets manager. Never commit API keys to source control.

### API Key Scopes

| Scope | Description |
|-------|-------------|
| `scans:trigger` | Trigger security scans |
| `scans:read` | Read scan results |
| `vulnerabilities:read` | Read vulnerability data |
| `patches:read` | Read patch data |
| `patches:approve` | Approve patches (use with caution) |
| `repositories:read` | List repositories |
| `webhooks:manage` | Manage webhook configurations |

### Rotating API Keys

```bash
# List API keys
curl -X GET https://api.aenealabs.com/v1/api-keys \
  -H "Authorization: Bearer ${USER_TOKEN}"

# Revoke API key
curl -X DELETE https://api.aenealabs.com/v1/api-keys/key-xyz789 \
  -H "Authorization: Bearer ${USER_TOKEN}"

# Create new key with same configuration
curl -X POST https://api.aenealabs.com/v1/api-keys \
  -H "Authorization: Bearer ${USER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "CI/CD Pipeline - Production (rotated)",
    "scopes": ["scans:trigger", "scans:read", "vulnerabilities:read"]
  }'
```

### API Key Best Practices

| Practice | Recommendation |
|----------|----------------|
| Naming | Use descriptive names including purpose and environment |
| Scopes | Grant minimum required permissions |
| Expiration | Set expiration dates for automated rotation |
| IP restrictions | Restrict to known CI/CD runner IPs |
| Monitoring | Review API key usage in audit logs |
| Rotation | Rotate keys quarterly or after personnel changes |

---

## Service Accounts for CI/CD

Service accounts are machine identities designed for CI/CD pipelines and automated systems.

### Creating Service Accounts

```bash
# Create service account
curl -X POST https://api.aenealabs.com/v1/service-accounts \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github-actions-prod",
    "description": "GitHub Actions production pipeline",
    "role": "developer",
    "repositories": ["repo-123", "repo-456"],
    "ipRestrictions": ["140.82.112.0/20"]
  }'
```

Response:

```json
{
  "id": "sa-github-prod",
  "name": "github-actions-prod",
  "description": "GitHub Actions production pipeline",
  "role": "developer",
  "repositories": ["repo-123", "repo-456"],
  "ipRestrictions": ["140.82.112.0/20"],
  "credentials": {
    "clientId": "aura_ci_xxxxxxxxxxxxxxxx",
    "clientSecret": "aura_cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  },
  "createdAt": "2026-01-19T10:00:00Z"
}
```

### Service Account Authentication

Service accounts authenticate using OAuth 2.0 client credentials flow:

```bash
# Get access token
curl -X POST https://api.aenealabs.com/v1/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=aura_ci_xxxxxxxxxxxxxxxx" \
  -d "client_secret=aura_cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

Response:

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### CI/CD Integration Examples

#### GitHub Actions

```yaml
# .github/workflows/aura-scan.yml
name: Aura Security Scan

on:
  pull_request:
    branches: [main]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Get Aura Token
        id: auth
        run: |
          TOKEN=$(curl -s -X POST https://api.aenealabs.com/v1/oauth/token \
            -H "Content-Type: application/x-www-form-urlencoded" \
            -d "grant_type=client_credentials" \
            -d "client_id=${{ secrets.AURA_CLIENT_ID }}" \
            -d "client_secret=${{ secrets.AURA_CLIENT_SECRET }}" \
            | jq -r '.access_token')
          echo "token=$TOKEN" >> $GITHUB_OUTPUT

      - name: Trigger Aura Scan
        run: |
          curl -X POST https://api.aenealabs.com/v1/scans \
            -H "Authorization: Bearer ${{ steps.auth.outputs.token }}" \
            -H "Content-Type: application/json" \
            -d '{
              "repositoryId": "${{ secrets.AURA_REPO_ID }}",
              "ref": "${{ github.head_ref }}",
              "type": "full"
            }'
```

#### GitLab CI

```yaml
# .gitlab-ci.yml
aura-scan:
  stage: test
  image: curlimages/curl:latest
  script:
    - |
      TOKEN=$(curl -s -X POST https://api.aenealabs.com/v1/oauth/token \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "grant_type=client_credentials" \
        -d "client_id=${AURA_CLIENT_ID}" \
        -d "client_secret=${AURA_CLIENT_SECRET}" \
        | jq -r '.access_token')

      curl -X POST https://api.aenealabs.com/v1/scans \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{
          \"repositoryId\": \"${AURA_REPO_ID}\",
          \"ref\": \"${CI_COMMIT_REF_NAME}\",
          \"type\": \"full\"
        }"
```

#### Jenkins

```groovy
// Jenkinsfile
pipeline {
    agent any

    environment {
        AURA_CLIENT_ID = credentials('aura-client-id')
        AURA_CLIENT_SECRET = credentials('aura-client-secret')
        AURA_REPO_ID = credentials('aura-repo-id')
    }

    stages {
        stage('Security Scan') {
            steps {
                script {
                    def tokenResponse = httpRequest(
                        url: 'https://api.aenealabs.com/v1/oauth/token',
                        httpMode: 'POST',
                        contentType: 'APPLICATION_FORM',
                        requestBody: "grant_type=client_credentials&client_id=${AURA_CLIENT_ID}&client_secret=${AURA_CLIENT_SECRET}"
                    )
                    def token = readJSON(text: tokenResponse.content).access_token

                    httpRequest(
                        url: 'https://api.aenealabs.com/v1/scans',
                        httpMode: 'POST',
                        contentType: 'APPLICATION_JSON',
                        customHeaders: [[name: 'Authorization', value: "Bearer ${token}"]],
                        requestBody: """{"repositoryId": "${AURA_REPO_ID}", "ref": "${env.GIT_BRANCH}", "type": "full"}"""
                    )
                }
            }
        }
    }
}
```

---

## Audit Logging

All user and access management activities are logged for compliance and security monitoring.

### Logged Events

| Event Category | Events |
|----------------|--------|
| Authentication | Login success, login failure, logout, MFA verification |
| User Management | User created, modified, disabled, deleted |
| Role Changes | Role assigned, role revoked, custom role created |
| Team Management | Team created, member added, member removed |
| API Keys | Key created, key revoked, key used |
| Service Accounts | Account created, credentials rotated |
| Policy Changes | RBAC policy modified, HITL policy changed |

### Viewing Audit Logs

```bash
# Query audit logs
curl -X GET "https://api.aenealabs.com/v1/audit-logs?category=authentication&startDate=2026-01-18&endDate=2026-01-19" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

Response:

```json
{
  "logs": [
    {
      "id": "log-abc123",
      "timestamp": "2026-01-19T10:15:00Z",
      "category": "authentication",
      "event": "login_success",
      "actor": {
        "id": "user-abc123",
        "email": "developer@yourcompany.com",
        "ipAddress": "10.0.1.50"
      },
      "details": {
        "method": "sso",
        "provider": "okta",
        "sessionId": "sess-xyz789"
      }
    }
  ],
  "pagination": {
    "total": 150,
    "page": 1,
    "pageSize": 50
  }
}
```

### Audit Log Retention

| Environment | Retention Period |
|-------------|------------------|
| Development | 30 days |
| Staging | 90 days |
| Production | 7 years (compliance requirement) |

### Exporting Audit Logs

```bash
# Export to CSV
curl -X POST https://api.aenealabs.com/v1/audit-logs/export \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "csv",
    "startDate": "2026-01-01",
    "endDate": "2026-01-31",
    "categories": ["authentication", "user_management"]
  }'
```

---

## Security Best Practices

### Password Policies

Configure strong password requirements:

| Setting | Recommended Value |
|---------|-------------------|
| Minimum length | 12 characters |
| Require uppercase | Yes |
| Require lowercase | Yes |
| Require numbers | Yes |
| Require special characters | Yes |
| Password history | 10 passwords |
| Maximum age | 90 days |

### MFA Enforcement

> **Security Best Practice:** Enable MFA for all users, especially those with admin or security_analyst roles.

```bash
# Require MFA for organization
curl -X PATCH https://api.aenealabs.com/v1/organizations/current \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"mfaRequired": true}'

# Require MFA for specific role
curl -X PATCH https://api.aenealabs.com/v1/roles/admin \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"mfaRequired": true}'
```

### Session Management

| Setting | Recommended Value |
|---------|-------------------|
| Session timeout | 60 minutes (inactive) |
| Maximum session duration | 8 hours |
| Concurrent sessions | 3 maximum |
| Session binding | IP address |

### Regular Access Reviews

Conduct regular access reviews:

1. **Monthly:** Review active users and their roles
2. **Quarterly:** Review API keys and service accounts
3. **Annually:** Review custom roles and permissions
4. **On termination:** Immediately revoke access for departing employees

---

## Troubleshooting

### Common Issues

| Issue | Symptom | Resolution |
|-------|---------|------------|
| Login failure | "Invalid credentials" | Verify email, reset password if needed |
| Permission denied | 403 error on API call | Check user role and permissions |
| API key rejected | 401 error | Verify key is active and not expired |
| SSO loop | Redirect to IdP repeatedly | Check SSO configuration and certificates |
| Account locked | "Account locked" message | Wait for lockout period or admin unlock |

### Unlocking User Accounts

```bash
# Unlock user account
curl -X POST https://api.aenealabs.com/v1/users/user-abc123/unlock \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

### Resetting User Password

```bash
# Trigger password reset email
curl -X POST https://api.aenealabs.com/v1/users/user-abc123/reset-password \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

---

## Related Documentation

- [Administration Guide](./index.md)
- [SSO Integration](./sso-integration.md)
- [Configuration Reference](./configuration-reference.md)
- [Security Architecture](../../support/architecture/security-architecture.md)
- [HITL Workflows](../core-concepts/hitl-workflows.md)

---

*Last updated: January 2026 | Version 1.0*
