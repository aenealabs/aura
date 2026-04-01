# ADR-054: Multi-Identity Provider Authentication System

**Status:** Proposed
**Date:** 2026-01-06
**Decision Makers:** Project Aura Platform Team, Security Architecture Team
**Related:** ADR-004 (Cloud Abstraction Layer), ADR-053 (Enterprise Security Integrations)

---

## Executive Summary

This ADR establishes the architecture for a comprehensive multi-identity provider (IdP) authentication system for Project Aura. Enterprise customers should not be forced to use AWS Cognito exclusively - they should be able to use their existing enterprise identity tools including LDAP/Active Directory, SAML 2.0, OIDC, PingID, and SSO providers.

**Core Thesis:** Enterprise authentication is heterogeneous. Organizations have invested heavily in identity infrastructure (Active Directory, Okta, Azure AD, PingIdentity, etc.) and require seamless integration rather than migration to a new IdP. By abstracting authentication away from Cognito-only, Aura becomes enterprise-ready for customers with diverse identity requirements.

**Key Outcomes:**
- Support for 6 identity provider types: Cognito, LDAP/AD, SAML 2.0, OIDC, PingID, SSO
- Admin-configurable IdP settings with attribute and group mappings
- Multi-IdP support per organization (e.g., LDAP for employees, SAML for contractors)
- Token normalization to unified Aura JWT format
- Email domain-based automatic IdP routing
- GovCloud-compatible with FedRAMP-aligned providers
- ~8,500 lines of new code with 70%+ test coverage

---

## Context

### The Single-IdP Limitation

Project Aura currently uses AWS Cognito as the sole identity provider. While Cognito provides excellent OAuth/OIDC capabilities, enterprise customers have expressed critical requirements:

| Customer Segment | Identity Infrastructure | Current Blocker |
|-----------------|------------------------|-----------------|
| **Large Enterprises** | Active Directory, Okta, Azure AD | Cannot integrate with existing SSO |
| **Government/Defense** | CAC/PIV, SAML federation | Cognito doesn't support hardware tokens natively |
| **Financial Services** | PingIdentity, RSA SecurID | Compliance requires existing IGA integration |
| **Healthcare** | LDAP, SAML with MFA | HIPAA requires existing identity audit trails |

### Market Requirements

Competitor analysis shows that enterprise AI platforms universally support multi-IdP:
- **GitHub Copilot Enterprise**: SAML, OIDC, GitHub auth
- **GitLab Duo**: SAML, LDAP, OIDC, OmniAuth
- **Snyk**: SAML SSO, OIDC, Azure AD
- **SonarQube**: LDAP, SAML, OAuth2, GitHub/GitLab

### Existing Authentication Architecture

```
CURRENT STATE (Cognito-Only)
============================

┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Frontend  │────>│   Cognito    │────>│  Aura API   │
│    (SPA)    │     │  User Pool   │     │  (FastAPI)  │
└─────────────┘     └──────────────┘     └─────────────┘
                          │
                          ▼
                    ┌──────────────┐
                    │  JWKS Keys   │
                    │  (RS256)     │
                    └──────────────┘

Limitations:
- No LDAP/AD support
- No SAML federation (only via Cognito federation, complex setup)
- No PingID native support
- All users must be in Cognito pool
- No organization-level IdP configuration
```

---

## Decision

**Implement a multi-identity provider authentication abstraction layer that normalizes diverse IdP tokens into a unified Aura JWT, while preserving the existing Cognito integration as one option among many.**

### Target Architecture

```
FUTURE STATE (Multi-IdP)
========================

                              ┌─────────────────────────┐
                              │   IdP Configuration     │
                              │   (DynamoDB)            │
                              │   - org_id, idp_type    │
                              │   - endpoints, certs    │
                              │   - attribute mappings  │
                              └───────────┬─────────────┘
                                          │
┌─────────────┐                           ▼
│   Frontend  │──────────────────────────────────────────────────┐
│    (SPA)    │                                                  │
└─────────────┘                                                  │
       │                                                         │
       │ 1. GET /auth/providers?email=user@company.com           │
       ▼                                                         │
┌──────────────────────────────────────────────────────────────┐ │
│                 AUTHENTICATION GATEWAY                        │ │
│                                                              │ │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐│ │
│  │ Cognito │ │  LDAP   │ │ SAML2   │ │  OIDC   │ │ PingID  ││ │
│  │Connector│ │Connector│ │Connector│ │Connector│ │Connector││ │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘│ │
│       │          │          │          │          │         │ │
│       └──────────┴──────────┴──────────┴──────────┘         │ │
│                            │                                 │ │
│                            ▼                                 │ │
│                ┌─────────────────────┐                       │ │
│                │ Token Normalization │                       │ │
│                │ Service             │                       │ │
│                │ - Validate IdP token│                       │ │
│                │ - Extract claims    │                       │ │
│                │ - Issue Aura JWT    │                       │ │
│                └──────────┬──────────┘                       │ │
│                           │                                  │ │
└───────────────────────────┼──────────────────────────────────┘ │
                            │                                    │
                            ▼                                    │
                   ┌────────────────┐                            │
                   │   Aura JWT     │◄───────────────────────────┘
                   │   (Unified)    │   2. Use JWT for all API calls
                   └────────────────┘
```

### Supported Identity Providers

| IdP Type | Protocol | Authentication Flow | Enterprise Use Case |
|----------|----------|---------------------|---------------------|
| **Cognito** | OAuth2/OIDC | Authorization Code + PKCE | Default, cloud-native customers |
| **LDAP/AD** | LDAP v3 | Simple bind / GSSAPI | On-prem enterprises, Windows domains |
| **SAML 2.0** | SAML | SP-initiated SSO | Okta, OneLogin, Azure AD federation |
| **OIDC** | OpenID Connect | Authorization Code | Azure AD, Google Workspace, Auth0 |
| **PingID** | OAuth2 + proprietary | PingFederate integration | PingIdentity customers |
| **SSO** | Various | Redirect-based | Generic enterprise SSO |

---

## Architecture

### Data Model

```python
# src/services/identity/models.py

@dataclass
class IdentityProviderConfig:
    """Configuration for an identity provider."""

    idp_id: str                    # Unique identifier
    organization_id: str           # Organization this IdP belongs to
    idp_type: IdPType              # cognito, ldap, saml, oidc, pingid, sso
    name: str                      # Display name (e.g., "Corporate AD")
    enabled: bool                  # Whether this IdP is active
    priority: int                  # Order for multi-IdP (lower = higher priority)

    # Connection settings (type-specific)
    connection_settings: dict      # Endpoints, ports, domains

    # Authentication settings
    auth_settings: dict            # Client IDs, secrets (reference to Secrets Manager)

    # Certificate/key settings
    certificate_settings: dict     # SAML certs, LDAP TLS config

    # Attribute mapping (IdP claims -> Aura user fields)
    attribute_mappings: list[AttributeMapping]

    # Group mapping (IdP groups -> Aura roles)
    group_mappings: list[GroupMapping]

    # Email domain routing
    email_domains: list[str]       # e.g., ["company.com", "subsidiary.com"]

    # Metadata
    created_at: str
    updated_at: str
    created_by: str

@dataclass
class AttributeMapping:
    """Maps IdP attribute to Aura user attribute."""
    source_attribute: str          # IdP claim name (e.g., "mail", "displayName")
    target_attribute: str          # Aura field (e.g., "email", "name")
    transform: str | None          # Optional transform (e.g., "lowercase")
    required: bool                 # Whether this mapping is required

@dataclass
class GroupMapping:
    """Maps IdP group to Aura role."""
    source_group: str              # IdP group (e.g., "CN=Developers,OU=Groups,DC=company,DC=com")
    target_role: str               # Aura role (e.g., "developer", "admin", "security-engineer")
    priority: int                  # For multi-group membership conflicts
```

### DynamoDB Schema

```yaml
# IdP Configurations Table
Table: aura-idp-configurations-{env}
Key Schema:
  - idp_id (HASH)

Global Secondary Indexes:
  - organization-index:
      organization_id (HASH), priority (RANGE)
  - email-domain-index:
      email_domain (HASH)  # For routing lookups

Attributes:
  - idp_id: S
  - organization_id: S
  - idp_type: S (cognito|ldap|saml|oidc|pingid|sso)
  - name: S
  - enabled: BOOL
  - priority: N
  - connection_settings: M
  - auth_settings_secret_arn: S  # Reference to Secrets Manager
  - certificate_settings: M
  - attribute_mappings: L
  - group_mappings: L
  - email_domains: SS
  - created_at: S
  - updated_at: S
  - created_by: S

# IdP Audit Log Table
Table: aura-idp-audit-{env}
Key Schema:
  - audit_id (HASH)

Global Secondary Indexes:
  - idp-timestamp-index:
      idp_id (HASH), timestamp (RANGE)
  - organization-timestamp-index:
      organization_id (HASH), timestamp (RANGE)

Attributes:
  - audit_id: S
  - idp_id: S
  - organization_id: S
  - action: S (create|update|delete|auth_success|auth_failure)
  - actor_id: S
  - timestamp: S
  - details: M
  - ttl: N  # 90-day retention
```

### Service Architecture

```
src/services/identity/
├── __init__.py
├── models.py                      # Data models and enums
├── base_provider.py               # Abstract base class for IdP providers
├── providers/
│   ├── __init__.py
│   ├── cognito_provider.py        # AWS Cognito integration
│   ├── ldap_provider.py           # LDAP/Active Directory
│   ├── saml_provider.py           # SAML 2.0 federation
│   ├── oidc_provider.py           # OpenID Connect
│   ├── pingid_provider.py         # PingIdentity
│   └── sso_provider.py            # Generic SSO
├── token_service.py               # Token normalization & Aura JWT issuance
├── idp_config_service.py          # IdP configuration CRUD
├── idp_routing_service.py         # Email domain -> IdP routing
├── certificate_manager.py         # Certificate storage & validation
└── audit_service.py               # Authentication audit logging
```

---

## Implementation

### Phase 1: Infrastructure & Core Framework (Week 1-2)

| Deliverable | Description | LOC |
|-------------|-------------|-----|
| `deploy/cloudformation/idp-infrastructure.yaml` | DynamoDB tables, Secrets Manager, IAM | ~300 |
| `src/services/identity/models.py` | Data models, enums, validators | ~400 |
| `src/services/identity/base_provider.py` | Abstract IdP provider interface | ~300 |
| `src/services/identity/idp_config_service.py` | Configuration CRUD operations | ~500 |
| `src/services/identity/audit_service.py` | Audit logging service | ~250 |
| `tests/test_idp_models.py` | Model unit tests | ~300 |

**Base Provider Interface:**

```python
# src/services/identity/base_provider.py

class IdentityProvider(ABC):
    """Abstract base class for identity providers."""

    def __init__(self, config: IdentityProviderConfig):
        self.config = config
        self.name = config.name
        self.idp_type = config.idp_type

    @abstractmethod
    async def authenticate(self, credentials: AuthCredentials) -> AuthResult:
        """Authenticate user with provider-specific credentials."""
        pass

    @abstractmethod
    async def validate_token(self, token: str) -> TokenValidationResult:
        """Validate an existing token from this provider."""
        pass

    @abstractmethod
    async def get_user_info(self, token: str) -> UserInfo:
        """Get user information from the provider."""
        pass

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> TokenResult:
        """Refresh an expired token."""
        pass

    @abstractmethod
    async def logout(self, token: str) -> bool:
        """Logout user (revoke token if supported)."""
        pass

    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        """Check provider connectivity and health."""
        pass

    def map_attributes(self, provider_claims: dict) -> dict:
        """Map provider claims to Aura user attributes."""
        result = {}
        for mapping in self.config.attribute_mappings:
            if mapping.source_attribute in provider_claims:
                value = provider_claims[mapping.source_attribute]
                if mapping.transform:
                    value = self._apply_transform(value, mapping.transform)
                result[mapping.target_attribute] = value
            elif mapping.required:
                raise AttributeMappingError(
                    f"Required attribute '{mapping.source_attribute}' not found"
                )
        return result

    def map_groups_to_roles(self, provider_groups: list[str]) -> list[str]:
        """Map provider groups to Aura roles."""
        roles = set()
        for mapping in sorted(self.config.group_mappings, key=lambda m: m.priority):
            if mapping.source_group in provider_groups:
                roles.add(mapping.target_role)
        return list(roles) if roles else ["viewer"]  # Default role
```

### Phase 2: LDAP/Active Directory Provider (Week 2-3)

| Deliverable | Description | LOC |
|-------------|-------------|-----|
| `src/services/identity/providers/ldap_provider.py` | LDAP/AD authentication | ~700 |
| `tests/test_ldap_provider.py` | LDAP unit tests (mocked) | ~500 |

**LDAP Provider Implementation:**

```python
# src/services/identity/providers/ldap_provider.py

class LDAPProvider(IdentityProvider):
    """
    LDAP/Active Directory identity provider.

    Supports:
    - Simple bind authentication
    - GSSAPI/Kerberos authentication
    - TLS/StartTLS encryption
    - Group membership resolution (nested groups)
    - Attribute retrieval for user profiles
    """

    def __init__(self, config: IdentityProviderConfig):
        super().__init__(config)

        # Parse connection settings
        conn = config.connection_settings
        self.server = conn.get("server")
        self.port = conn.get("port", 389)
        self.use_ssl = conn.get("use_ssl", False)
        self.use_tls = conn.get("use_tls", True)
        self.base_dn = conn.get("base_dn")
        self.user_search_base = conn.get("user_search_base")
        self.user_search_filter = conn.get(
            "user_search_filter",
            "(sAMAccountName={username})"
        )
        self.group_search_base = conn.get("group_search_base")
        self.bind_dn = conn.get("bind_dn")  # Service account

        # Load bind password from Secrets Manager
        self._bind_password: str | None = None

    async def authenticate(self, credentials: AuthCredentials) -> AuthResult:
        """Authenticate user via LDAP bind."""
        username = credentials.username
        password = credentials.password

        try:
            # Step 1: Connect and bind with service account
            server = ldap3.Server(
                self.server,
                port=self.port,
                use_ssl=self.use_ssl,
                get_info=ldap3.ALL,
            )

            service_conn = ldap3.Connection(
                server,
                user=self.bind_dn,
                password=await self._get_bind_password(),
                auto_bind=True,
            )

            if self.use_tls and not self.use_ssl:
                service_conn.start_tls()

            # Step 2: Search for user DN
            search_filter = self.user_search_filter.format(username=username)
            service_conn.search(
                self.user_search_base,
                search_filter,
                attributes=ldap3.ALL_ATTRIBUTES,
            )

            if not service_conn.entries:
                return AuthResult(
                    success=False,
                    error="User not found",
                    error_code="USER_NOT_FOUND",
                )

            user_entry = service_conn.entries[0]
            user_dn = str(user_entry.entry_dn)

            # Step 3: Attempt bind as user
            user_conn = ldap3.Connection(
                server,
                user=user_dn,
                password=password,
            )

            if not user_conn.bind():
                return AuthResult(
                    success=False,
                    error="Invalid credentials",
                    error_code="INVALID_CREDENTIALS",
                )

            # Step 4: Get user attributes
            user_attrs = dict(user_entry.entry_attributes_as_dict)

            # Step 5: Resolve group memberships
            groups = await self._resolve_groups(service_conn, user_dn)

            # Step 6: Map to Aura format
            mapped_attrs = self.map_attributes(self._flatten_attrs(user_attrs))
            roles = self.map_groups_to_roles(groups)

            return AuthResult(
                success=True,
                user_id=user_dn,
                email=mapped_attrs.get("email"),
                name=mapped_attrs.get("name"),
                groups=groups,
                roles=roles,
                attributes=mapped_attrs,
                provider_metadata={"dn": user_dn, "provider": "ldap"},
            )

        except ldap3.core.exceptions.LDAPException as e:
            logger.error(f"LDAP authentication error: {e}")
            return AuthResult(
                success=False,
                error=str(e),
                error_code="LDAP_ERROR",
            )

    async def _resolve_groups(
        self,
        conn: ldap3.Connection,
        user_dn: str
    ) -> list[str]:
        """Resolve user's group memberships including nested groups."""
        groups = set()

        # Direct group membership
        conn.search(
            self.group_search_base,
            f"(member={user_dn})",
            attributes=["cn", "distinguishedName"],
        )

        for entry in conn.entries:
            group_dn = str(entry.entry_dn)
            groups.add(group_dn)

            # Resolve nested groups (AD-specific)
            groups.update(await self._get_nested_groups(conn, group_dn))

        return list(groups)
```

### Phase 3: SAML 2.0 Provider (Week 3-4)

| Deliverable | Description | LOC |
|-------------|-------------|-----|
| `src/services/identity/providers/saml_provider.py` | SAML 2.0 SP implementation | ~900 |
| `src/services/identity/certificate_manager.py` | X.509 certificate handling | ~400 |
| `tests/test_saml_provider.py` | SAML unit tests | ~600 |

**SAML Provider Implementation:**

```python
# src/services/identity/providers/saml_provider.py

class SAMLProvider(IdentityProvider):
    """
    SAML 2.0 Service Provider implementation.

    Supports:
    - SP-initiated SSO (redirect binding)
    - IdP-initiated SSO
    - Signed assertions
    - Encrypted assertions
    - Single Logout (SLO)
    - Metadata exchange
    """

    def __init__(self, config: IdentityProviderConfig):
        super().__init__(config)

        conn = config.connection_settings
        self.entity_id = conn.get("sp_entity_id", "https://api.aenealabs.com/saml")
        self.idp_entity_id = conn.get("idp_entity_id")
        self.idp_sso_url = conn.get("idp_sso_url")
        self.idp_slo_url = conn.get("idp_slo_url")
        self.idp_certificate = conn.get("idp_certificate")  # Base64 PEM
        self.acs_url = conn.get("acs_url", "https://api.aenealabs.com/auth/saml/acs")
        self.name_id_format = conn.get(
            "name_id_format",
            "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
        )

        # SP signing key (from Secrets Manager)
        self._sp_private_key: str | None = None
        self._sp_certificate: str | None = None

    def generate_auth_request(self, relay_state: str | None = None) -> AuthRequest:
        """Generate SAML AuthnRequest for SP-initiated SSO."""
        request_id = f"aura_{uuid.uuid4().hex}"
        issue_instant = datetime.now(timezone.utc).isoformat()

        auth_request = f"""
        <samlp:AuthnRequest
            xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
            xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
            ID="{request_id}"
            Version="2.0"
            IssueInstant="{issue_instant}"
            Destination="{self.idp_sso_url}"
            AssertionConsumerServiceURL="{self.acs_url}"
            ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
            <saml:Issuer>{self.entity_id}</saml:Issuer>
            <samlp:NameIDPolicy
                Format="{self.name_id_format}"
                AllowCreate="true"/>
        </samlp:AuthnRequest>
        """

        # Sign the request
        signed_request = self._sign_request(auth_request)

        # Encode for redirect
        encoded = base64.b64encode(
            zlib.compress(signed_request.encode())[2:-4]
        ).decode()

        params = {
            "SAMLRequest": encoded,
        }
        if relay_state:
            params["RelayState"] = relay_state

        redirect_url = f"{self.idp_sso_url}?{urlencode(params)}"

        return AuthRequest(
            request_id=request_id,
            redirect_url=redirect_url,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )

    async def validate_response(self, saml_response: str) -> AuthResult:
        """Validate SAML Response from IdP."""
        try:
            # Decode response
            decoded = base64.b64decode(saml_response)
            root = ET.fromstring(decoded)

            # Validate signature
            if not self._validate_signature(root):
                return AuthResult(
                    success=False,
                    error="Invalid SAML signature",
                    error_code="INVALID_SIGNATURE",
                )

            # Check conditions
            conditions = root.find(".//{urn:oasis:names:tc:SAML:2.0:assertion}Conditions")
            if conditions is not None:
                not_before = conditions.get("NotBefore")
                not_on_or_after = conditions.get("NotOnOrAfter")
                now = datetime.now(timezone.utc)

                if not_before and now < datetime.fromisoformat(not_before.replace("Z", "+00:00")):
                    return AuthResult(success=False, error="Assertion not yet valid")
                if not_on_or_after and now >= datetime.fromisoformat(not_on_or_after.replace("Z", "+00:00")):
                    return AuthResult(success=False, error="Assertion expired")

            # Extract NameID
            name_id = root.find(".//{urn:oasis:names:tc:SAML:2.0:assertion}NameID")
            if name_id is None:
                return AuthResult(success=False, error="No NameID in assertion")

            user_id = name_id.text

            # Extract attributes
            attrs = {}
            for attr in root.findall(".//{urn:oasis:names:tc:SAML:2.0:assertion}Attribute"):
                attr_name = attr.get("Name")
                attr_values = attr.findall("{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue")
                if attr_values:
                    attrs[attr_name] = attr_values[0].text

            # Map attributes and groups
            mapped_attrs = self.map_attributes(attrs)
            groups = attrs.get("groups", "").split(",") if attrs.get("groups") else []
            roles = self.map_groups_to_roles(groups)

            return AuthResult(
                success=True,
                user_id=user_id,
                email=mapped_attrs.get("email", user_id),
                name=mapped_attrs.get("name"),
                groups=groups,
                roles=roles,
                attributes=mapped_attrs,
                provider_metadata={"provider": "saml", "idp": self.idp_entity_id},
            )

        except Exception as e:
            logger.error(f"SAML validation error: {e}")
            return AuthResult(
                success=False,
                error=str(e),
                error_code="SAML_ERROR",
            )

    def generate_sp_metadata(self) -> str:
        """Generate SAML SP metadata XML for IdP configuration."""
        return f"""
        <EntityDescriptor
            xmlns="urn:oasis:names:tc:SAML:2.0:metadata"
            entityID="{self.entity_id}">
            <SPSSODescriptor
                protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol"
                AuthnRequestsSigned="true"
                WantAssertionsSigned="true">
                <NameIDFormat>{self.name_id_format}</NameIDFormat>
                <AssertionConsumerService
                    Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                    Location="{self.acs_url}"
                    index="0"/>
            </SPSSODescriptor>
        </EntityDescriptor>
        """
```

### Phase 4: OIDC Provider (Week 4-5)

| Deliverable | Description | LOC |
|-------------|-------------|-----|
| `src/services/identity/providers/oidc_provider.py` | Generic OIDC client | ~600 |
| `tests/test_oidc_provider.py` | OIDC unit tests | ~400 |

**OIDC Provider Implementation:**

```python
# src/services/identity/providers/oidc_provider.py

class OIDCProvider(IdentityProvider):
    """
    OpenID Connect identity provider.

    Supports:
    - Authorization Code flow with PKCE
    - Discovery via .well-known/openid-configuration
    - JWT validation (RS256, RS384, RS512)
    - UserInfo endpoint
    - Token refresh
    """

    def __init__(self, config: IdentityProviderConfig):
        super().__init__(config)

        conn = config.connection_settings
        self.issuer = conn.get("issuer")
        self.client_id = conn.get("client_id")
        self.redirect_uri = conn.get(
            "redirect_uri",
            "https://api.aenealabs.com/auth/oidc/callback"
        )
        self.scopes = conn.get("scopes", ["openid", "profile", "email"])

        # Discovery endpoints (populated from discovery document)
        self._authorization_endpoint: str | None = None
        self._token_endpoint: str | None = None
        self._userinfo_endpoint: str | None = None
        self._jwks_uri: str | None = None
        self._jwks: dict | None = None
        self._jwks_cache_time: float = 0

        # Client secret from Secrets Manager
        self._client_secret: str | None = None

    async def discover(self) -> None:
        """Fetch OIDC discovery document."""
        discovery_url = f"{self.issuer}/.well-known/openid-configuration"

        async with aiohttp.ClientSession() as session:
            async with session.get(discovery_url) as response:
                if response.status != 200:
                    raise OIDCDiscoveryError(f"Failed to fetch discovery: {response.status}")

                config = await response.json()

                self._authorization_endpoint = config["authorization_endpoint"]
                self._token_endpoint = config["token_endpoint"]
                self._userinfo_endpoint = config.get("userinfo_endpoint")
                self._jwks_uri = config["jwks_uri"]

    def generate_auth_url(self, state: str, nonce: str) -> tuple[str, str]:
        """Generate authorization URL with PKCE."""
        # Generate PKCE challenge
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip("=")

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        auth_url = f"{self._authorization_endpoint}?{urlencode(params)}"
        return auth_url, code_verifier

    async def exchange_code(
        self,
        code: str,
        code_verifier: str
    ) -> TokenResult:
        """Exchange authorization code for tokens."""
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": await self._get_client_secret(),
            "code": code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": code_verifier,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    raise OIDCTokenError(f"Token exchange failed: {error}")

                tokens = await response.json()

                return TokenResult(
                    access_token=tokens["access_token"],
                    id_token=tokens.get("id_token"),
                    refresh_token=tokens.get("refresh_token"),
                    expires_in=tokens.get("expires_in", 3600),
                    token_type=tokens.get("token_type", "Bearer"),
                )

    async def validate_id_token(self, id_token: str, nonce: str) -> AuthResult:
        """Validate and decode ID token."""
        # Fetch JWKS
        jwks = await self._get_jwks()

        # Get key ID from token header
        header = jwt.get_unverified_header(id_token)
        kid = header.get("kid")

        # Find matching key
        key = None
        for k in jwks.get("keys", []):
            if k.get("kid") == kid:
                key = k
                break

        if not key:
            return AuthResult(success=False, error="No matching key found")

        # Validate token
        try:
            claims = jwt.decode(
                id_token,
                key,
                algorithms=["RS256", "RS384", "RS512"],
                audience=self.client_id,
                issuer=self.issuer,
            )

            # Validate nonce
            if claims.get("nonce") != nonce:
                return AuthResult(success=False, error="Nonce mismatch")

            # Map to Aura format
            mapped_attrs = self.map_attributes(claims)
            groups = claims.get("groups", [])
            roles = self.map_groups_to_roles(groups)

            return AuthResult(
                success=True,
                user_id=claims.get("sub"),
                email=mapped_attrs.get("email"),
                name=mapped_attrs.get("name"),
                groups=groups,
                roles=roles,
                attributes=mapped_attrs,
                provider_metadata={"provider": "oidc", "issuer": self.issuer},
            )

        except jwt.JWTError as e:
            return AuthResult(success=False, error=str(e))
```

### Phase 5: PingID Provider (Week 5)

| Deliverable | Description | LOC |
|-------------|-------------|-----|
| `src/services/identity/providers/pingid_provider.py` | PingFederate/PingID integration | ~500 |
| `tests/test_pingid_provider.py` | PingID unit tests | ~300 |

### Phase 6: Token Normalization Service (Week 5-6)

| Deliverable | Description | LOC |
|-------------|-------------|-----|
| `src/services/identity/token_service.py` | Unified Aura JWT issuance | ~600 |
| `tests/test_token_service.py` | Token service tests | ~400 |

**Token Normalization:**

```python
# src/services/identity/token_service.py

class TokenNormalizationService:
    """
    Normalizes IdP tokens into unified Aura JWTs.

    Ensures consistent token format regardless of source IdP,
    enabling uniform authorization across the platform.
    """

    # Aura JWT claims
    AURA_CLAIMS = [
        "sub",       # User ID (unique across IdPs)
        "email",     # User email
        "name",      # Display name
        "roles",     # Aura roles (mapped from IdP groups)
        "org_id",    # Organization ID
        "idp",       # Source IdP identifier
        "idp_type",  # IdP type (cognito, ldap, saml, etc.)
    ]

    def __init__(
        self,
        signing_key_secret_arn: str,
        issuer: str = "https://api.aenealabs.com",
        access_token_ttl: int = 3600,      # 1 hour
        refresh_token_ttl: int = 2592000,  # 30 days
    ):
        self.signing_key_secret_arn = signing_key_secret_arn
        self.issuer = issuer
        self.access_token_ttl = access_token_ttl
        self.refresh_token_ttl = refresh_token_ttl

        self._signing_key: str | None = None

    async def issue_aura_tokens(
        self,
        auth_result: AuthResult,
        idp_config: IdentityProviderConfig,
    ) -> AuraTokens:
        """Issue Aura access and refresh tokens from IdP auth result."""

        now = datetime.now(timezone.utc)

        # Generate unique subject for this IdP + user combination
        # This ensures users from different IdPs don't collide
        aura_sub = self._generate_subject(
            idp_id=idp_config.idp_id,
            provider_user_id=auth_result.user_id,
        )

        # Access token claims
        access_claims = {
            "sub": aura_sub,
            "email": auth_result.email,
            "name": auth_result.name,
            "roles": auth_result.roles,
            "org_id": idp_config.organization_id,
            "idp": idp_config.idp_id,
            "idp_type": idp_config.idp_type.value,
            "iss": self.issuer,
            "aud": "aura-api",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self.access_token_ttl)).timestamp()),
            "token_type": "access",
        }

        # Sign access token
        access_token = jwt.encode(
            access_claims,
            await self._get_signing_key(),
            algorithm="RS256",
        )

        # Refresh token claims (minimal, long-lived)
        refresh_claims = {
            "sub": aura_sub,
            "org_id": idp_config.organization_id,
            "idp": idp_config.idp_id,
            "iss": self.issuer,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self.refresh_token_ttl)).timestamp()),
            "token_type": "refresh",
            "jti": secrets.token_urlsafe(32),  # Unique token ID for revocation
        }

        refresh_token = jwt.encode(
            refresh_claims,
            await self._get_signing_key(),
            algorithm="RS256",
        )

        return AuraTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=self.access_token_ttl,
            id_token=None,  # Aura doesn't issue separate ID tokens
        )

    def _generate_subject(self, idp_id: str, provider_user_id: str) -> str:
        """Generate globally unique subject for user."""
        # Hash to prevent IdP information leakage
        combined = f"{idp_id}:{provider_user_id}"
        return hashlib.sha256(combined.encode()).hexdigest()
```

### Phase 7: API Endpoints (Week 6-7)

| Deliverable | Description | LOC |
|-------------|-------------|-----|
| `src/api/identity_endpoints.py` | FastAPI routes for auth flows | ~800 |
| `src/api/idp_admin_endpoints.py` | Admin IdP configuration API | ~600 |
| `tests/test_identity_endpoints.py` | API integration tests | ~500 |

**API Endpoints:**

```python
# src/api/identity_endpoints.py

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.get("/providers")
async def get_available_providers(
    email: str | None = None,
    org_id: str | None = None,
) -> list[ProviderInfo]:
    """
    Get available identity providers for login.

    If email is provided, returns providers configured for that email domain.
    If org_id is provided, returns all providers for that organization.
    """
    ...

@router.post("/login/ldap")
async def login_ldap(
    request: LDAPLoginRequest,
    idp_id: str,
) -> TokenResponse:
    """Authenticate via LDAP/Active Directory."""
    ...

@router.get("/saml/login/{idp_id}")
async def saml_login(idp_id: str) -> RedirectResponse:
    """Initiate SAML SP-initiated SSO."""
    ...

@router.post("/saml/acs")
async def saml_assertion_consumer(
    SAMLResponse: str = Form(...),
    RelayState: str = Form(None),
) -> TokenResponse:
    """SAML Assertion Consumer Service endpoint."""
    ...

@router.get("/oidc/login/{idp_id}")
async def oidc_login(idp_id: str) -> RedirectResponse:
    """Initiate OIDC authorization code flow."""
    ...

@router.get("/oidc/callback")
async def oidc_callback(
    code: str,
    state: str,
) -> TokenResponse:
    """OIDC authorization code callback."""
    ...

@router.post("/token/refresh")
async def refresh_token(
    refresh_token: str = Body(...),
) -> TokenResponse:
    """Refresh Aura access token."""
    ...

@router.post("/logout")
async def logout(
    user: User = Depends(get_current_user),
) -> dict:
    """Logout user and revoke tokens."""
    ...
```

**Admin API Endpoints:**

```python
# src/api/idp_admin_endpoints.py

router = APIRouter(prefix="/admin/identity-providers", tags=["idp-admin"])

@router.get("/")
async def list_idp_configs(
    org_id: str,
    user: User = Depends(require_admin),
) -> list[IdPConfigResponse]:
    """List all IdP configurations for an organization."""
    ...

@router.post("/")
async def create_idp_config(
    config: IdPConfigCreate,
    user: User = Depends(require_admin),
) -> IdPConfigResponse:
    """Create new IdP configuration."""
    ...

@router.put("/{idp_id}")
async def update_idp_config(
    idp_id: str,
    config: IdPConfigUpdate,
    user: User = Depends(require_admin),
) -> IdPConfigResponse:
    """Update IdP configuration."""
    ...

@router.delete("/{idp_id}")
async def delete_idp_config(
    idp_id: str,
    user: User = Depends(require_admin),
) -> dict:
    """Delete IdP configuration."""
    ...

@router.post("/{idp_id}/test")
async def test_idp_connection(
    idp_id: str,
    credentials: TestCredentials | None = None,
    user: User = Depends(require_admin),
) -> TestResult:
    """Test IdP connectivity and optionally test authentication."""
    ...

@router.get("/{idp_id}/audit")
async def get_idp_audit_log(
    idp_id: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    user: User = Depends(require_admin),
) -> list[AuditLogEntry]:
    """Get audit log for IdP configuration changes and auth events."""
    ...
```

---

## CloudFormation Infrastructure

```yaml
# deploy/cloudformation/idp-infrastructure.yaml

AWSTemplateFormatVersion: '2010-09-09'
Description: 'Project Aura - Layer 4.5 - Identity Provider Infrastructure'

Parameters:
  Environment:
    Type: String
    Default: dev
  ProjectName:
    Type: String
    Default: aura

Resources:
  # IdP Configuration Table
  IdPConfigurationsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-idp-configurations-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: idp_id
          AttributeType: S
        - AttributeName: organization_id
          AttributeType: S
        - AttributeName: priority
          AttributeType: N
        - AttributeName: email_domain
          AttributeType: S
      KeySchema:
        - AttributeName: idp_id
          KeyType: HASH
      GlobalSecondaryIndexes:
        - IndexName: organization-priority-index
          KeySchema:
            - AttributeName: organization_id
              KeyType: HASH
            - AttributeName: priority
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
        - IndexName: email-domain-index
          KeySchema:
            - AttributeName: email_domain
              KeyType: HASH
          Projection:
            ProjectionType: ALL
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
        SSEType: KMS
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-idp-configurations-${Environment}'

  # IdP Audit Table
  IdPAuditTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-idp-audit-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: audit_id
          AttributeType: S
        - AttributeName: idp_id
          AttributeType: S
        - AttributeName: organization_id
          AttributeType: S
        - AttributeName: timestamp
          AttributeType: S
      KeySchema:
        - AttributeName: audit_id
          KeyType: HASH
      GlobalSecondaryIndexes:
        - IndexName: idp-timestamp-index
          KeySchema:
            - AttributeName: idp_id
              KeyType: HASH
            - AttributeName: timestamp
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
        - IndexName: organization-timestamp-index
          KeySchema:
            - AttributeName: organization_id
              KeyType: HASH
            - AttributeName: timestamp
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
        SSEType: KMS

  # JWT Signing Key
  JWTSigningKeySecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: !Sub '${ProjectName}/${Environment}/identity/jwt-signing-key'
      Description: RSA private key for signing Aura JWTs
      GenerateSecretString:
        SecretStringTemplate: '{}'
        GenerateStringKey: placeholder
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Component
          Value: identity

Outputs:
  IdPConfigurationsTableName:
    Value: !Ref IdPConfigurationsTable
    Export:
      Name: !Sub '${AWS::StackName}-IdPConfigurationsTableName'

  IdPAuditTableName:
    Value: !Ref IdPAuditTable
    Export:
      Name: !Sub '${AWS::StackName}-IdPAuditTableName'

  JWTSigningKeySecretArn:
    Value: !Ref JWTSigningKeySecret
    Export:
      Name: !Sub '${AWS::StackName}-JWTSigningKeySecretArn'
```

---

## Security Considerations

### Credential Storage

| Secret Type | Storage | Rotation |
|-------------|---------|----------|
| LDAP bind password | Secrets Manager | 90 days |
| SAML SP private key | Secrets Manager | Annual |
| OIDC client secret | Secrets Manager | 90 days |
| JWT signing key | Secrets Manager | Annual |
| IdP certificates | DynamoDB (encrypted) | On IdP cert rotation |

### Token Security

1. **Short-lived access tokens**: 1-hour TTL minimizes exposure window
2. **Refresh token rotation**: New refresh token on each use
3. **Revocation support**: Token JTI tracked for instant revocation
4. **Audience validation**: Tokens scoped to specific API audiences
5. **IdP binding**: Tokens tied to source IdP to prevent cross-IdP replay

### Audit Logging

All authentication events logged to CloudWatch and DynamoDB:
- Authentication attempts (success/failure)
- IdP configuration changes
- Token issuance
- Token refresh
- Logout/revocation

### Certificate Validation

- SAML certificates validated against trusted CA bundle
- Certificate expiration monitoring with SNS alerts
- Support for certificate pinning (optional)

---

## GovCloud Compatibility

| Component | Commercial AWS | GovCloud (US) | Notes |
|-----------|----------------|---------------|-------|
| DynamoDB | Available | Available | Full feature parity |
| Secrets Manager | Available | Available | Full feature parity |
| Cognito | Available | Available | Limited federation options |
| SAML providers | N/A | Must be FedRAMP | Okta GovCloud, Azure Government |
| OIDC providers | N/A | Must be FedRAMP | Azure AD Government |

**GovCloud-Approved IdPs:**
- Azure AD (Azure Government)
- Okta (Okta for Government)
- PingFederate (FedRAMP authorized)
- LDAP/AD (on-premises, customer responsibility)

---

## Settings UI Requirements (for Design Review)

### IdP Configuration Screen

**Location:** Settings > Identity Providers

**Sections:**

1. **Provider List View**
   - Table showing all configured IdPs
   - Columns: Name, Type, Status (enabled/disabled), Priority, Email Domains
   - Actions: Edit, Delete, Test Connection
   - "Add Provider" button

2. **Add/Edit Provider Modal**
   - Step 1: Provider Type Selection (radio buttons with icons)
   - Step 2: Connection Settings (type-specific fields)
   - Step 3: Attribute Mappings (source -> target table)
   - Step 4: Group Mappings (source -> target table)
   - Step 5: Review & Test

3. **Provider Type Configurations**

   **LDAP/AD:**
   - Server hostname/IP
   - Port (389/636)
   - Use SSL/TLS checkbox
   - Base DN
   - User search base
   - User search filter
   - Group search base
   - Bind DN (service account)
   - Bind password (masked)

   **SAML 2.0:**
   - IdP Entity ID
   - IdP SSO URL
   - IdP SLO URL (optional)
   - IdP Certificate (file upload or paste)
   - SP Entity ID (auto-generated, editable)
   - Download SP Metadata button

   **OIDC:**
   - Issuer URL
   - Client ID
   - Client Secret (masked)
   - Scopes (multi-select)
   - Redirect URI (auto-generated, editable)

   **PingID:**
   - PingFederate URL
   - Client ID
   - Client Secret (masked)
   - Connection ID

4. **Attribute Mapping Section**
   - Draggable table with source attribute, target attribute, transform dropdown
   - Common attributes pre-populated: email, name, groups
   - "Add Mapping" button

5. **Group Mapping Section**
   - Table with IdP group pattern, Aura role dropdown
   - Regex support for group patterns
   - Priority ordering (drag to reorder)
   - Available roles: admin, security-engineer, developer, viewer

6. **Email Domain Routing**
   - List of email domains that route to this IdP
   - Auto-suggest based on test authentication
   - Warning if domain conflicts with another IdP

7. **Test Connection**
   - Test connectivity button (no credentials needed)
   - Test authentication button (requires test credentials)
   - Results showing: connection status, attribute mapping preview, group mapping preview

---

## Success Criteria

### Quantitative

| Metric | Target |
|--------|--------|
| Test Coverage | >= 70% |
| Authentication Latency (p95) | < 500ms (OIDC/SAML), < 200ms (LDAP) |
| Configuration API Latency (p95) | < 100ms |
| Token Issuance Latency | < 50ms |

### Qualitative

| Criterion | Validation |
|-----------|------------|
| Enterprise customers can use existing IdP | Customer pilot |
| Admin can configure IdP without engineering support | User testing |
| Multi-IdP routing works seamlessly | Integration tests |
| Audit logs meet compliance requirements | Security review |

---

## Implementation Summary

| Phase | Deliverables | LOC | Duration |
|-------|--------------|-----|----------|
| 1: Infrastructure & Core | CloudFormation, models, base provider | ~2,050 | Weeks 1-2 |
| 2: LDAP Provider | LDAP/AD connector + tests | ~1,200 | Weeks 2-3 |
| 3: SAML Provider | SAML 2.0 SP + cert manager + tests | ~1,900 | Weeks 3-4 |
| 4: OIDC Provider | OIDC client + tests | ~1,000 | Weeks 4-5 |
| 5: PingID Provider | PingFederate connector + tests | ~800 | Week 5 |
| 6: Token Service | Unified JWT issuance + tests | ~1,000 | Weeks 5-6 |
| 7: API Endpoints | Auth flows + admin API + tests | ~1,900 | Weeks 6-7 |
| **Total** | | **~9,850** | **7 weeks** |

---

## Decision Outcome

**PROPOSED** - Pending implementation approval.

### Conditions for Approval

1. Security review of token normalization approach
2. Customer validation of supported IdP list
3. GovCloud IdP compatibility verification
4. UI/UX review with design review

### Next Steps

1. Deploy Phase 1 infrastructure
2. Implement LDAP provider first (highest customer demand)
3. Parallel implementation of SAML and OIDC
4. Customer pilot with one enterprise account

---

## References

1. **SAML 2.0 Technical Overview** - https://www.oasis-open.org/committees/download.php/27819/sstc-saml-tech-overview-2.0-cd-02.pdf
2. **OpenID Connect Core** - https://openid.net/specs/openid-connect-core-1_0.html
3. **LDAP v3 RFC** - https://datatracker.ietf.org/doc/html/rfc4511
4. **PingFederate Documentation** - https://docs.pingidentity.com/
5. **AWS Cognito Federation** - https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-identity-federation.html
6. **NIST 800-63B** - Digital Identity Guidelines (Authentication)
7. **FedRAMP Marketplace** - Authorized identity providers

---

## Appendix A: Data Models

See `src/services/identity/models.py` for complete data model definitions.

## Appendix B: API Schemas

See `src/api/schemas/identity_schemas.py` for OpenAPI schema definitions.
