# SSO Integration

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This guide covers Single Sign-On (SSO) integration with Project Aura. SSO enables centralized authentication through your organization's identity provider (IdP), improving security and user experience while simplifying access management.

Project Aura supports industry-standard SSO protocols:

- **SAML 2.0** - Security Assertion Markup Language
- **OIDC** - OpenID Connect (OAuth 2.0 extension)

---

## Supported Identity Providers

| Provider | SAML 2.0 | OIDC | JIT Provisioning | Group Sync |
|----------|----------|------|------------------|------------|
| Okta | Yes | Yes | Yes | Yes |
| Azure AD / Entra ID | Yes | Yes | Yes | Yes |
| Google Workspace | Yes | Yes | Yes | Yes |
| OneLogin | Yes | Yes | Yes | Yes |
| PingIdentity | Yes | Yes | Yes | Yes |
| Auth0 | Yes | Yes | Yes | Yes |
| Keycloak | Yes | Yes | Yes | Yes |
| ADFS | Yes | - | Yes | Yes |
| Custom SAML | Yes | - | Yes | Configurable |
| Custom OIDC | - | Yes | Yes | Configurable |

---

## SSO Architecture

```
+-----------------------------------------------------------------------------+
|                           SSO AUTHENTICATION FLOW                            |
+-----------------------------------------------------------------------------+

    User                    Aura                    Identity Provider
      |                       |                           |
      |  1. Access Aura       |                           |
      +---------------------->|                           |
      |                       |                           |
      |  2. Redirect to IdP   |                           |
      |<----------------------+                           |
      |                       |                           |
      |  3. Authenticate      |                           |
      +---------------------------------------------->    |
      |                       |                           |
      |  4. IdP Response (SAML Assertion / OIDC Token)   |
      |<----------------------------------------------    |
      |                       |                           |
      |  5. Submit to Aura    |                           |
      +---------------------->|                           |
      |                       |                           |
      |                       | 6. Validate Response      |
      |                       | 7. Create/Update User     |
      |                       | 8. Issue Session          |
      |                       |                           |
      |  9. Access Granted    |                           |
      |<----------------------+                           |
      |                       |                           |
```

---

## SAML 2.0 Configuration

### Aura SAML Service Provider Metadata

Use these values when configuring your Identity Provider:

| Attribute | Value |
|-----------|-------|
| **SP Entity ID** | `https://app.aenealabs.com/saml/metadata` |
| **ACS URL** | `https://app.aenealabs.com/saml/acs` |
| **SLO URL** | `https://app.aenealabs.com/saml/slo` |
| **Name ID Format** | `urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress` |

For self-hosted deployments, replace `app.aenealabs.com` with your domain:

| Attribute | Value |
|-----------|-------|
| **SP Entity ID** | `https://YOUR_DOMAIN/saml/metadata` |
| **ACS URL** | `https://YOUR_DOMAIN/saml/acs` |
| **SLO URL** | `https://YOUR_DOMAIN/saml/slo` |

### Required SAML Attributes

Configure your IdP to send these attributes in the SAML assertion:

| Attribute | Required | Description | Example |
|-----------|----------|-------------|---------|
| `email` | Yes | User's email address | `user@company.com` |
| `firstName` | Yes | User's first name | `Jane` |
| `lastName` | Yes | User's last name | `Developer` |
| `groups` | No | Group memberships | `["Engineering", "Security"]` |
| `department` | No | User's department | `Engineering` |
| `role` | No | Suggested Aura role | `developer` |

### SAML Attribute Mapping

Configure attribute mapping in Aura to match your IdP's attribute names:

```json
{
  "attributeMapping": {
    "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
    "firstName": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
    "lastName": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",
    "groups": "http://schemas.xmlsoap.org/claims/Group"
  }
}
```

---

## Provider-Specific Configuration

### Okta

#### Step 1: Create SAML Application in Okta

1. In Okta Admin Console, navigate to **Applications > Applications**
2. Click **Create App Integration**
3. Select **SAML 2.0** and click **Next**
4. Configure General Settings:
   - **App name:** Project Aura
   - **App logo:** (optional)
5. Configure SAML Settings:

   | Field | Value |
   |-------|-------|
   | Single sign-on URL | `https://app.aenealabs.com/saml/acs` |
   | Audience URI (SP Entity ID) | `https://app.aenealabs.com/saml/metadata` |
   | Name ID format | EmailAddress |
   | Application username | Email |

6. Configure Attribute Statements:

   | Name | Value |
   |------|-------|
   | email | user.email |
   | firstName | user.firstName |
   | lastName | user.lastName |

7. Configure Group Attribute Statements:

   | Name | Filter |
   |------|--------|
   | groups | Matches regex: `.*` |

8. Click **Next** and **Finish**

#### Step 2: Configure Aura

1. In Okta, go to the Sign On tab and click **View SAML setup instructions**
2. Copy the following values:
   - Identity Provider Single Sign-On URL
   - Identity Provider Issuer
   - X.509 Certificate

3. In Aura Dashboard, navigate to **Settings > Authentication > SSO**
4. Click **Configure SAML**
5. Enter the values from Okta:

```json
{
  "provider": "okta",
  "saml": {
    "entryPoint": "https://yourcompany.okta.com/app/xxxxx/sso/saml",
    "issuer": "http://www.okta.com/xxxxx",
    "certificate": "-----BEGIN CERTIFICATE-----\nMIIDp...\n-----END CERTIFICATE-----"
  },
  "attributeMapping": {
    "email": "email",
    "firstName": "firstName",
    "lastName": "lastName",
    "groups": "groups"
  }
}
```

#### Step 3: Test SSO

1. Assign users/groups to the application in Okta
2. Click **Test Connection** in Aura
3. Verify login works with a test user

---

### Azure AD / Entra ID

#### Step 1: Create Enterprise Application

1. In Azure Portal, navigate to **Microsoft Entra ID > Enterprise applications**
2. Click **New application > Create your own application**
3. Name: **Project Aura**
4. Select **Integrate any other application you don't find in the gallery (Non-gallery)**
5. Click **Create**

#### Step 2: Configure SAML SSO

1. Go to **Single sign-on > SAML**
2. Edit **Basic SAML Configuration**:

   | Field | Value |
   |-------|-------|
   | Identifier (Entity ID) | `https://app.aenealabs.com/saml/metadata` |
   | Reply URL (ACS URL) | `https://app.aenealabs.com/saml/acs` |
   | Sign on URL | `https://app.aenealabs.com` |
   | Logout URL | `https://app.aenealabs.com/saml/slo` |

3. Edit **Attributes & Claims**:

   | Claim name | Source attribute |
   |------------|------------------|
   | email | user.mail |
   | firstName | user.givenname |
   | lastName | user.surname |
   | groups | user.groups |

4. Download **Certificate (Base64)** and copy **Login URL**

#### Step 3: Configure Aura

```json
{
  "provider": "azure_ad",
  "saml": {
    "entryPoint": "https://login.microsoftonline.com/TENANT_ID/saml2",
    "issuer": "https://sts.windows.net/TENANT_ID/",
    "certificate": "-----BEGIN CERTIFICATE-----\nMIIC8D...\n-----END CERTIFICATE-----"
  },
  "attributeMapping": {
    "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
    "firstName": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
    "lastName": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",
    "groups": "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups"
  }
}
```

#### Step 4: Assign Users and Groups

1. In the Enterprise Application, go to **Users and groups**
2. Click **Add user/group**
3. Select users or groups to grant access

---

### Google Workspace

#### Step 1: Create SAML App in Google Admin

1. In Google Admin Console, go to **Apps > Web and mobile apps**
2. Click **Add App > Add custom SAML app**
3. Enter app details:
   - **App name:** Project Aura
   - **App icon:** (optional)
4. Download **IdP metadata** or copy:
   - SSO URL
   - Entity ID
   - Certificate

#### Step 2: Configure Service Provider Details

| Field | Value |
|-------|-------|
| ACS URL | `https://app.aenealabs.com/saml/acs` |
| Entity ID | `https://app.aenealabs.com/saml/metadata` |
| Start URL | `https://app.aenealabs.com` |
| Name ID format | EMAIL |
| Name ID | Basic Information > Primary email |

#### Step 3: Configure Attribute Mapping

| Google Directory attribute | App attribute |
|---------------------------|---------------|
| Primary email | email |
| First name | firstName |
| Last name | lastName |

#### Step 4: Configure Aura

```json
{
  "provider": "google",
  "saml": {
    "entryPoint": "https://accounts.google.com/o/saml2/idp?idpid=XXXXX",
    "issuer": "https://accounts.google.com/o/saml2?idpid=XXXXX",
    "certificate": "-----BEGIN CERTIFICATE-----\nMIIDd...\n-----END CERTIFICATE-----"
  },
  "attributeMapping": {
    "email": "email",
    "firstName": "firstName",
    "lastName": "lastName"
  }
}
```

#### Step 5: Enable for Users

1. In Google Admin, go to the SAML app
2. Click **User access**
3. Enable for organizational units or groups

---

### OneLogin

#### Step 1: Create SAML Connector

1. In OneLogin Admin, go to **Applications > Add App**
2. Search for **SAML Custom Connector (Advanced)**
3. Configure the connector:

   | Field | Value |
   |-------|-------|
   | Display Name | Project Aura |
   | Audience (EntityID) | `https://app.aenealabs.com/saml/metadata` |
   | ACS URL | `https://app.aenealabs.com/saml/acs` |
   | ACS URL Validator | `https://app\.aenealabs\.com/saml/acs` |

#### Step 2: Configure Parameters

Add custom parameters:

| Field name | Value |
|------------|-------|
| email | Email |
| firstName | First Name |
| lastName | Last Name |
| groups | User Roles |

#### Step 3: Configure Aura

```json
{
  "provider": "onelogin",
  "saml": {
    "entryPoint": "https://yourcompany.onelogin.com/trust/saml2/http-post/sso/XXXXX",
    "issuer": "https://app.onelogin.com/saml/metadata/XXXXX",
    "certificate": "-----BEGIN CERTIFICATE-----\nMIIEF...\n-----END CERTIFICATE-----"
  },
  "attributeMapping": {
    "email": "email",
    "firstName": "firstName",
    "lastName": "lastName",
    "groups": "groups"
  }
}
```

---

## OIDC/OAuth 2.0 Configuration

### Aura OIDC Configuration

| Attribute | Value |
|-----------|-------|
| **Redirect URI** | `https://app.aenealabs.com/auth/oidc/callback` |
| **Post-Logout Redirect URI** | `https://app.aenealabs.com/auth/logout/callback` |
| **Scopes Required** | `openid`, `profile`, `email` |

### Okta OIDC

#### Step 1: Create OIDC Application

1. In Okta Admin, go to **Applications > Create App Integration**
2. Select **OIDC - OpenID Connect**
3. Select **Web Application**
4. Configure:

   | Field | Value |
   |-------|-------|
   | App name | Project Aura |
   | Grant type | Authorization Code |
   | Sign-in redirect URIs | `https://app.aenealabs.com/auth/oidc/callback` |
   | Sign-out redirect URIs | `https://app.aenealabs.com/auth/logout/callback` |

5. Copy **Client ID** and **Client Secret**

#### Step 2: Configure Aura

```json
{
  "provider": "okta",
  "oidc": {
    "issuer": "https://yourcompany.okta.com",
    "clientId": "0oaxxxxxxxxxxxxxx",
    "clientSecret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "scopes": ["openid", "profile", "email", "groups"],
    "callbackUrl": "https://app.aenealabs.com/auth/oidc/callback"
  }
}
```

### Azure AD OIDC

#### Step 1: Register Application

1. In Azure Portal, go to **Microsoft Entra ID > App registrations**
2. Click **New registration**:

   | Field | Value |
   |-------|-------|
   | Name | Project Aura |
   | Supported account types | Single tenant |
   | Redirect URI | Web: `https://app.aenealabs.com/auth/oidc/callback` |

3. Note the **Application (client) ID** and **Directory (tenant) ID**

#### Step 2: Create Client Secret

1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Copy the secret value immediately

#### Step 3: Configure Aura

```json
{
  "provider": "azure_ad",
  "oidc": {
    "issuer": "https://login.microsoftonline.com/TENANT_ID/v2.0",
    "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "clientSecret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "scopes": ["openid", "profile", "email"],
    "callbackUrl": "https://app.aenealabs.com/auth/oidc/callback"
  }
}
```

---

## Just-in-Time (JIT) User Provisioning

JIT provisioning automatically creates user accounts in Aura when users first authenticate via SSO.

### Enable JIT Provisioning

```json
{
  "jitProvisioning": {
    "enabled": true,
    "defaultRole": "developer",
    "defaultTeams": [],
    "autoActivate": true,
    "allowedDomains": ["yourcompany.com", "subsidiary.com"]
  }
}
```

### JIT Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `enabled` | Enable JIT provisioning | `false` |
| `defaultRole` | Role assigned to new users | `viewer` |
| `defaultTeams` | Teams assigned to new users | `[]` |
| `autoActivate` | Activate accounts immediately | `true` |
| `allowedDomains` | Email domains allowed for JIT | All domains |
| `requireMfa` | Require MFA setup on first login | `false` |

### Role Assignment via IdP Claims

Map IdP groups or attributes to Aura roles:

```json
{
  "jitProvisioning": {
    "enabled": true,
    "roleMapping": {
      "Aura-Admins": "admin",
      "Aura-Security": "security_analyst",
      "Aura-Developers": "developer",
      "default": "viewer"
    }
  }
}
```

---

## Group Mapping to Roles

Synchronize IdP groups with Aura teams and roles.

### Group Sync Configuration

```json
{
  "groupSync": {
    "enabled": true,
    "syncInterval": "hourly",
    "groupMapping": {
      "Engineering": {
        "team": "engineering",
        "role": "developer"
      },
      "Security-Team": {
        "team": "security",
        "role": "security_analyst"
      },
      "Platform-Admins": {
        "team": "platform",
        "role": "admin"
      }
    },
    "removeOrphanedMemberships": true
  }
}
```

### Group Sync Behavior

| Setting | Description |
|---------|-------------|
| `syncInterval` | How often to sync groups: `realtime`, `hourly`, `daily` |
| `removeOrphanedMemberships` | Remove users from teams when removed from IdP groups |
| `createMissingTeams` | Auto-create Aura teams for unmapped IdP groups |

---

## Advanced Configuration

### Multiple Identity Providers

Configure multiple IdPs for different user populations:

```json
{
  "multipleProviders": {
    "enabled": true,
    "providers": [
      {
        "id": "corporate",
        "name": "Corporate SSO",
        "type": "saml",
        "domains": ["yourcompany.com"],
        "config": { ... }
      },
      {
        "id": "contractor",
        "name": "Contractor SSO",
        "type": "oidc",
        "domains": ["contractor-agency.com"],
        "config": { ... }
      }
    ],
    "defaultProvider": "corporate"
  }
}
```

### SSO Enforcement

Require SSO for all users (disable local authentication):

```json
{
  "enforcement": {
    "ssoRequired": true,
    "allowLocalAuth": false,
    "breakGlassAccounts": ["emergency-admin@yourcompany.com"],
    "allowApiKeyAuth": true
  }
}
```

> **Security Best Practice:** Always configure at least one break-glass account with local authentication for emergency access if SSO is unavailable.

### Session Configuration

Configure SSO session behavior:

```json
{
  "session": {
    "maxDuration": "8h",
    "idleTimeout": "1h",
    "singleLogout": true,
    "forceReauthentication": false,
    "bindToIp": true
  }
}
```

---

## Certificate Management

### Certificate Requirements

- **Format:** X.509 PEM-encoded
- **Key size:** RSA 2048-bit minimum (4096-bit recommended)
- **Signature algorithm:** SHA-256 or stronger
- **Validity:** Monitor expiration dates

### Certificate Rotation

#### Step 1: Add New Certificate to Aura

```json
{
  "saml": {
    "certificates": [
      "-----BEGIN CERTIFICATE-----\nOLD_CERT...\n-----END CERTIFICATE-----",
      "-----BEGIN CERTIFICATE-----\nNEW_CERT...\n-----END CERTIFICATE-----"
    ]
  }
}
```

#### Step 2: Update IdP with New Certificate

Update your IdP to use the new signing certificate.

#### Step 3: Remove Old Certificate from Aura

After verifying the new certificate works:

```json
{
  "saml": {
    "certificates": [
      "-----BEGIN CERTIFICATE-----\nNEW_CERT...\n-----END CERTIFICATE-----"
    ]
  }
}
```

### Certificate Expiration Monitoring

Aura monitors SSO certificate expiration:

- **30 days before:** Warning notification to admins
- **7 days before:** Critical notification
- **Expired:** SSO may fail; fallback to local auth if enabled

---

## Troubleshooting

### Common SSO Issues

| Issue | Symptoms | Resolution |
|-------|----------|------------|
| Certificate mismatch | SAML signature validation failed | Verify certificate matches IdP |
| Clock skew | Assertion expired | Sync server clocks (NTP) |
| ACS URL mismatch | IdP error on redirect | Verify ACS URL in IdP matches Aura |
| Missing attributes | User created without name | Check attribute mapping |
| Group sync failing | Users not added to teams | Verify group claim is sent by IdP |

### Debug Mode

Enable SSO debug logging:

```bash
# Environment variable
AURA_SSO_DEBUG=true

# Or via API
curl -X PATCH https://api.aenealabs.com/v1/sso/settings \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"debug": true}'
```

Debug logs include:

- Raw SAML assertions (redacted)
- OIDC token claims
- Attribute mapping results
- Group sync decisions

### SAML Assertion Inspection

Decode and inspect SAML assertions:

```bash
# Decode base64 SAML response
echo "SAML_RESPONSE_BASE64" | base64 -d | xmllint --format -
```

### Test Connection

Test SSO configuration without affecting users:

```bash
curl -X POST https://api.aenealabs.com/v1/sso/test \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "okta",
    "testUser": "test@yourcompany.com"
  }'
```

---

## API Reference

### SSO Settings Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/sso/settings` | Get current SSO configuration |
| PUT | `/v1/sso/settings` | Update SSO configuration |
| POST | `/v1/sso/test` | Test SSO connection |
| GET | `/v1/sso/metadata` | Get SP metadata (SAML) |
| POST | `/v1/sso/certificate/rotate` | Rotate signing certificate |

### Get SSO Configuration

```bash
curl -X GET https://api.aenealabs.com/v1/sso/settings \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

### Update SSO Configuration

```bash
curl -X PUT https://api.aenealabs.com/v1/sso/settings \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "okta",
    "enabled": true,
    "saml": { ... },
    "jitProvisioning": { ... }
  }'
```

---

## Security Best Practices

| Practice | Recommendation |
|----------|----------------|
| Certificate strength | Use RSA 4096-bit or ECDSA P-384 |
| Signature algorithm | SHA-256 or SHA-384 |
| Assertion encryption | Enable if IdP supports |
| Clock tolerance | Keep servers synchronized via NTP |
| Certificate monitoring | Set up expiration alerts |
| Audit logging | Enable SSO event logging |
| Break-glass accounts | Configure emergency local access |
| Regular testing | Test SSO quarterly |

---

## Related Documentation

- [Administration Guide](./index.md)
- [User Management](./user-management.md)
- [Configuration Reference](./configuration-reference.md)
- [Security Architecture](../../support/architecture/security-architecture.md)

---

*Last updated: January 2026 | Version 1.0*
