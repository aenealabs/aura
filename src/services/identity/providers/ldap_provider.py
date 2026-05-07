"""
Project Aura - LDAP/Active Directory Identity Provider

Implements LDAP v3 authentication for enterprise Active Directory integration.

Supports:
- Simple bind authentication
- LDAPS (SSL) and StartTLS encryption
- Nested group membership resolution
- Custom attribute mapping
- Service account binding for user lookup

Author: Project Aura Team
Created: 2026-01-06
Version: 1.0.0
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from src.services.identity.base_provider import AuthenticationError, ConfigurationError
from src.services.identity.base_provider import ConnectionError as IdPConnectionError
from src.services.identity.base_provider import (
    IdentityProvider,
    IdentityProviderFactory,
)
from src.services.identity.models import (
    AuthCredentials,
    AuthResult,
    ConnectionStatus,
    HealthCheckResult,
    IdentityProviderConfig,
    IdPType,
    TokenResult,
    TokenValidationResult,
    UserInfo,
)

logger = logging.getLogger(__name__)

# Lazy import ldap3 - only loaded when LDAP provider is used
_ldap3_module: Any = None
_ldap3_available: bool | None = None


def _get_ldap3():
    """Lazy import of ldap3 module. Returns None if not available."""
    global _ldap3_module, _ldap3_available
    if _ldap3_available is None:
        try:
            import ldap3

            _ldap3_module = ldap3
            _ldap3_available = True
        except ImportError:
            _ldap3_available = False
            logger.warning(
                "ldap3 not available - LDAP authentication will not work. "
                "Install with: pip install ldap3"
            )
    return _ldap3_module if _ldap3_available else None


# Lazy import boto3 for Secrets Manager
_boto3_module: Any = None
_secrets_client: Any = None


def _get_secrets_client(region: str = "us-east-1"):
    """Get cached Secrets Manager client."""
    global _boto3_module, _secrets_client
    if _secrets_client is None:
        try:
            import boto3

            _boto3_module = boto3
            _secrets_client = boto3.client("secretsmanager", region_name=region)
        except ImportError:
            logger.warning("boto3 not available for Secrets Manager")
    return _secrets_client


class LDAPProvider(IdentityProvider):
    """
    LDAP/Active Directory identity provider.

    Authenticates users against LDAP directories (Active Directory, OpenLDAP, etc.)
    using bind authentication.

    Connection Settings (config.connection_settings):
        server: str - LDAP server hostname or IP
        port: int - LDAP port (389 for LDAP, 636 for LDAPS)
        use_ssl: bool - Use LDAPS (SSL/TLS on connect)
        use_tls: bool - Use StartTLS after connect
        base_dn: str - Base DN for searches (e.g., "DC=company,DC=com")
        user_search_base: str - DN to search for users (e.g., "OU=Users,DC=company,DC=com")
        user_search_filter: str - Filter template (default: "(sAMAccountName={username})")
        group_search_base: str - DN to search for groups
        bind_dn: str - Service account DN for searches
        connect_timeout: int - Connection timeout in seconds (default: 10)
        receive_timeout: int - Receive timeout in seconds (default: 30)
        resolve_nested_groups: bool - Resolve nested AD group memberships (default: True)

    Credentials (from Secrets Manager):
        bind_password: str - Service account password
    """

    def __init__(self, config: IdentityProviderConfig):
        """Initialize LDAP provider."""
        super().__init__(config)

        # Validate IdP type
        if config.idp_type != IdPType.LDAP:
            raise ConfigurationError(
                f"Invalid IdP type for LDAPProvider: {config.idp_type}"
            )

        # Parse connection settings
        conn = config.connection_settings
        self.server = conn.get("server")
        self.port = conn.get("port", 389)
        self.use_ssl = conn.get("use_ssl", False)
        self.use_tls = conn.get("use_tls", True)
        self.base_dn = conn.get("base_dn")
        self.user_search_base = conn.get("user_search_base") or self.base_dn
        self.user_search_filter = conn.get(
            "user_search_filter", "(sAMAccountName={username})"
        )
        self.group_search_base = conn.get("group_search_base") or self.base_dn
        self.bind_dn = conn.get("bind_dn")
        self.connect_timeout = conn.get("connect_timeout", 10)
        self.receive_timeout = conn.get("receive_timeout", 30)
        self.resolve_nested_groups = conn.get("resolve_nested_groups", True)

        # Validate required settings
        if not self.server:
            raise ConfigurationError("LDAP server is required")
        if not self.base_dn:
            raise ConfigurationError("LDAP base_dn is required")
        if not self.bind_dn:
            raise ConfigurationError("LDAP bind_dn is required for user searches")

        # Credentials loaded from Secrets Manager on first use
        self._bind_password: str | None = None
        self._credentials_loaded = False

    async def _load_credentials(self) -> None:
        """Load bind credentials from Secrets Manager."""
        if self._credentials_loaded:
            return

        if not self.config.credentials_secret_arn:
            raise ConfigurationError(
                "LDAP credentials_secret_arn is required for authentication"
            )

        secrets_client = _get_secrets_client()
        if not secrets_client:
            raise ConfigurationError("boto3 not available for loading LDAP credentials")

        try:
            response = secrets_client.get_secret_value(
                SecretId=self.config.credentials_secret_arn
            )
            secret_data = json.loads(response["SecretString"])
            self._bind_password = secret_data.get("bind_password")

            if not self._bind_password:
                raise ConfigurationError(
                    "bind_password not found in LDAP credentials secret"
                )

            self._credentials_loaded = True
            logger.info(f"Loaded LDAP credentials for IdP {self.idp_id}")

        except Exception as e:
            logger.error(f"Failed to load LDAP credentials: {e}")
            raise ConfigurationError(f"Failed to load LDAP credentials: {e}")

    def _create_server(self):
        """Create LDAP server object."""
        ldap3 = _get_ldap3()
        if not ldap3:
            raise ConfigurationError("ldap3 library not available")

        return ldap3.Server(
            self.server,
            port=self.port,
            use_ssl=self.use_ssl,
            get_info=ldap3.ALL,
            connect_timeout=self.connect_timeout,
        )

    def _create_service_connection(self, server):
        """Create connection using service account."""
        ldap3 = _get_ldap3()
        if not ldap3:
            raise ConfigurationError("ldap3 library not available")

        conn = ldap3.Connection(
            server,
            user=self.bind_dn,
            password=self._bind_password,
            auto_bind=False,
            receive_timeout=self.receive_timeout,
            raise_exceptions=True,
        )

        # Bind
        if not conn.bind():
            raise IdPConnectionError(
                f"Service account bind failed: {conn.result}",
                error_code="SERVICE_BIND_FAILED",
            )

        # StartTLS if configured
        if self.use_tls and not self.use_ssl:
            conn.start_tls()

        return conn

    async def authenticate(self, credentials: AuthCredentials) -> AuthResult:
        """
        Authenticate user via LDAP bind.

        Args:
            credentials: Must contain username and password

        Returns:
            AuthResult with user info and roles
        """
        start_time = time.time()

        if not credentials.username or not credentials.password:
            return AuthResult(
                success=False,
                error="Username and password are required",
                error_code="MISSING_CREDENTIALS",
            )

        ldap3 = _get_ldap3()
        if not ldap3:
            return AuthResult(
                success=False,
                error="LDAP library not available",
                error_code="LDAP_NOT_AVAILABLE",
            )

        try:
            # Load service account credentials
            await self._load_credentials()

            # Create server and service connection
            server = self._create_server()
            service_conn = self._create_service_connection(server)

            try:
                # Step 1: Search for user DN
                search_filter = self.user_search_filter.format(
                    username=credentials.username
                )
                service_conn.search(
                    self.user_search_base,
                    search_filter,
                    attributes=ldap3.ALL_ATTRIBUTES,
                    search_scope=ldap3.SUBTREE,
                )

                if not service_conn.entries:
                    latency_ms = (time.time() - start_time) * 1000
                    self._record_request(latency_ms, False)
                    return AuthResult(
                        success=False,
                        error="User not found",
                        error_code="USER_NOT_FOUND",
                    )

                user_entry = service_conn.entries[0]
                user_dn = str(user_entry.entry_dn)

                # Step 2: Attempt bind as user
                user_conn = ldap3.Connection(
                    server,
                    user=user_dn,
                    password=credentials.password,
                    auto_bind=False,
                )

                if not user_conn.bind():
                    latency_ms = (time.time() - start_time) * 1000
                    self._record_request(latency_ms, False)
                    self._set_status(ConnectionStatus.CONNECTED)  # Server is reachable
                    return AuthResult(
                        success=False,
                        error="Invalid credentials",
                        error_code="INVALID_CREDENTIALS",
                    )

                # Unbind user connection
                user_conn.unbind()

                # Step 3: Get user attributes
                user_attrs = dict(user_entry.entry_attributes_as_dict)
                flattened_attrs = self._flatten_ldap_attrs(user_attrs)

                # Step 4: Resolve group memberships
                groups = await self._resolve_groups(service_conn, user_dn)

                # Step 5: Map to Aura format
                mapped_attrs = self.map_attributes(flattened_attrs)
                roles = self.map_groups_to_roles(groups)

                latency_ms = (time.time() - start_time) * 1000
                self._record_request(latency_ms, True)
                self._set_status(ConnectionStatus.CONNECTED)

                logger.info(
                    f"LDAP authentication successful for user '{credentials.username}' "
                    f"via IdP {self.idp_id}"
                )

                return AuthResult(
                    success=True,
                    user_id=user_dn,
                    email=mapped_attrs.get("email"),
                    name=mapped_attrs.get("name"),
                    groups=groups,
                    roles=roles,
                    attributes=mapped_attrs,
                    provider_metadata={
                        "dn": user_dn,
                        "provider": "ldap",
                        "idp_id": self.idp_id,
                        "server": self.server,
                    },
                )

            finally:
                service_conn.unbind()

        except ldap3.core.exceptions.LDAPException as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            self._set_status(ConnectionStatus.ERROR, str(e))
            logger.error(f"LDAP authentication error for IdP {self.idp_id}: {e}")
            return AuthResult(
                success=False,
                error=f"LDAP error: {e}",
                error_code="LDAP_ERROR",
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            self._set_status(ConnectionStatus.ERROR, str(e))
            logger.exception(f"Unexpected error during LDAP auth: {e}")
            return AuthResult(
                success=False,
                error=str(e),
                error_code="UNEXPECTED_ERROR",
            )

    async def _resolve_groups(
        self, conn, user_dn: str, max_depth: int = 10
    ) -> list[str]:
        """
        Resolve user's group memberships.

        For Active Directory, resolves nested groups using memberOf:1.2.840.113556.1.4.1941:
        (LDAP_MATCHING_RULE_IN_CHAIN).

        Args:
            conn: LDAP connection
            user_dn: User distinguished name
            max_depth: Maximum nesting depth for non-AD directories

        Returns:
            List of group DNs
        """
        ldap3 = _get_ldap3()
        groups: set[str] = set()

        if self.resolve_nested_groups:
            # Try AD-specific nested group resolution first
            try:
                # LDAP_MATCHING_RULE_IN_CHAIN for recursive group membership
                conn.search(
                    self.group_search_base,
                    f"(member:1.2.840.113556.1.4.1941:={user_dn})",
                    attributes=["cn", "distinguishedName"],
                    search_scope=ldap3.SUBTREE,
                )

                for entry in conn.entries:
                    groups.add(str(entry.entry_dn))

                logger.debug(
                    f"Resolved {len(groups)} groups (including nested) for {user_dn}"
                )
                return list(groups)

            except Exception as e:
                logger.debug(
                    f"AD nested group query failed (possibly not AD): {e}. "
                    "Falling back to direct membership."
                )

        # Fallback: Direct group membership only
        conn.search(
            self.group_search_base,
            f"(member={user_dn})",
            attributes=["cn", "distinguishedName"],
            search_scope=ldap3.SUBTREE,
        )

        for entry in conn.entries:
            groups.add(str(entry.entry_dn))

        logger.debug(f"Resolved {len(groups)} direct groups for {user_dn}")
        return list(groups)

    async def validate_token(self, token: str) -> TokenValidationResult:
        """
        LDAP doesn't use tokens - always return invalid.

        LDAP authentication is stateless (bind per request).
        Use Aura JWT tokens for session management.
        """
        return TokenValidationResult(
            valid=False,
            error="LDAP does not use tokens. Use Aura JWT for session management.",
        )

    async def get_user_info(self, token: str) -> UserInfo:
        """
        Get user info by DN.

        For LDAP, the token parameter is the user DN.
        """
        ldap3 = _get_ldap3()
        if not ldap3:
            raise AuthenticationError("LDAP library not available")

        try:
            await self._load_credentials()
            server = self._create_server()
            conn = self._create_service_connection(server)

            try:
                # Search by DN
                conn.search(
                    token,  # DN as search base
                    "(objectClass=*)",
                    attributes=ldap3.ALL_ATTRIBUTES,
                    search_scope=ldap3.BASE,
                )

                if not conn.entries:
                    raise AuthenticationError(f"User not found: {token}")

                entry = conn.entries[0]
                attrs = self._flatten_ldap_attrs(dict(entry.entry_attributes_as_dict))
                mapped = self.map_attributes(attrs)
                groups = await self._resolve_groups(conn, token)

                return UserInfo(
                    user_id=token,
                    email=mapped.get("email"),
                    name=mapped.get("name"),
                    username=mapped.get("username"),
                    groups=groups,
                    attributes=mapped,
                )

            finally:
                conn.unbind()

        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            raise AuthenticationError(f"Failed to get user info: {e}")

    async def refresh_token(self, refresh_token: str) -> TokenResult:
        """LDAP doesn't support token refresh."""
        raise AuthenticationError(
            "LDAP does not support token refresh. Re-authenticate with credentials."
        )

    async def logout(self, token: str) -> bool:
        """LDAP doesn't have session logout - always returns True."""
        # LDAP is stateless, nothing to logout
        return True

    async def health_check(self) -> HealthCheckResult:
        """
        Check LDAP server connectivity.

        Tests:
        1. TCP connection to server
        2. TLS/SSL if configured
        3. Service account bind
        """
        start_time = time.time()
        ldap3 = _get_ldap3()

        if not ldap3:
            return HealthCheckResult(
                healthy=False,
                status=ConnectionStatus.ERROR,
                message="ldap3 library not available",
                last_checked=datetime.now(timezone.utc).isoformat(),
            )

        try:
            await self._load_credentials()
            server = self._create_server()
            conn = self._create_service_connection(server)

            try:
                # Test search
                conn.search(
                    self.base_dn,
                    "(objectClass=*)",
                    search_scope=ldap3.BASE,
                )

                latency_ms = (time.time() - start_time) * 1000
                self._set_status(ConnectionStatus.CONNECTED)

                return HealthCheckResult(
                    healthy=True,
                    status=ConnectionStatus.CONNECTED,
                    latency_ms=latency_ms,
                    message="LDAP connection successful",
                    last_checked=datetime.now(timezone.utc).isoformat(),
                    details={
                        "server": self.server,
                        "port": self.port,
                        "ssl": self.use_ssl,
                        "tls": self.use_tls,
                        "base_dn": self.base_dn,
                    },
                )

            finally:
                conn.unbind()

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._set_status(ConnectionStatus.ERROR, str(e))

            return HealthCheckResult(
                healthy=False,
                status=ConnectionStatus.ERROR,
                latency_ms=latency_ms,
                message=str(e),
                last_checked=datetime.now(timezone.utc).isoformat(),
                details={
                    "server": self.server,
                    "port": self.port,
                    "error": str(e),
                },
            )


# Register provider with factory
IdentityProviderFactory.register("ldap", LDAPProvider)
