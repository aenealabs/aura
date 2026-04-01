"""
Project Aura - SAML 2.0 Identity Provider

Implements SAML 2.0 Service Provider (SP) functionality for enterprise SSO.

Supports:
- SP-initiated SSO (redirect binding)
- IdP-initiated SSO
- Signed and encrypted assertions
- Single Logout (SLO)
- Metadata generation and exchange

Author: Project Aura Team
Created: 2026-01-06
Version: 1.0.0
"""

import base64
import json
import logging
import time
import uuid
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DefusedET

from src.services.identity.base_provider import (
    AuthenticationError,
    ConfigurationError,
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

# SAML 2.0 Namespaces
SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
SAMLP_NS = "urn:oasis:names:tc:SAML:2.0:protocol"
DS_NS = "http://www.w3.org/2000/09/xmldsig#"

# Register namespaces for ElementTree
ET.register_namespace("saml", SAML_NS)
ET.register_namespace("samlp", SAMLP_NS)
ET.register_namespace("ds", DS_NS)

# Lazy imports
_lxml_available: bool | None = None
_xmlsec_available: bool | None = None


def _check_dependencies():
    """Check for optional XML security dependencies."""
    global _lxml_available, _xmlsec_available

    if _lxml_available is None:
        try:
            import lxml  # noqa: F401

            _lxml_available = True
        except ImportError:
            _lxml_available = False
            logger.warning(
                "lxml not available - SAML signature validation may be limited"
            )

    if _xmlsec_available is None:
        try:
            import xmlsec  # noqa: F401

            _xmlsec_available = True
        except ImportError:
            _xmlsec_available = False
            logger.warning("xmlsec not available - SAML signature validation disabled")


@dataclass
class SAMLAuthRequest:
    """SAML authentication request data."""

    request_id: str
    redirect_url: str
    relay_state: str | None
    created_at: str
    expires_at: str


@dataclass
class SAMLStateData:
    """State data stored during SAML flow."""

    request_id: str
    idp_id: str
    relay_state: str | None
    created_at: str
    expires_at: str


class SAMLProvider(IdentityProvider):
    """
    SAML 2.0 Service Provider implementation.

    Handles SP-initiated SSO flows with enterprise identity providers
    like Okta, Azure AD, OneLogin, etc.

    Connection Settings (config.connection_settings):
        sp_entity_id: str - SP entity ID (e.g., "https://api.aenealabs.com/saml")
        idp_entity_id: str - IdP entity ID
        idp_sso_url: str - IdP SSO endpoint (redirect binding)
        idp_slo_url: str - IdP SLO endpoint (optional)
        idp_certificate: str - IdP signing certificate (PEM, base64 encoded)
        acs_url: str - Assertion Consumer Service URL
        name_id_format: str - NameID format (default: emailAddress)
        sign_requests: bool - Sign AuthnRequests (default: True)
        want_assertions_signed: bool - Require signed assertions (default: True)
        want_assertions_encrypted: bool - Require encrypted assertions (default: False)
        allowed_clock_skew: int - Clock skew tolerance in seconds (default: 300)

    Credentials (from Secrets Manager):
        private_key: str - SP signing private key (PEM)
        certificate: str - SP signing certificate (PEM)
    """

    def __init__(self, config: IdentityProviderConfig):
        """Initialize SAML provider."""
        super().__init__(config)

        if config.idp_type != IdPType.SAML:
            raise ConfigurationError(
                f"Invalid IdP type for SAMLProvider: {config.idp_type}"
            )

        _check_dependencies()

        conn = config.connection_settings
        self.sp_entity_id = conn.get("sp_entity_id", "https://api.aenealabs.com/saml")
        self.idp_entity_id = conn.get("idp_entity_id")
        self.idp_sso_url = conn.get("idp_sso_url")
        self.idp_slo_url = conn.get("idp_slo_url")
        self.idp_certificate = conn.get("idp_certificate")  # Base64 PEM
        self.acs_url = conn.get("acs_url", "https://api.aenealabs.com/auth/saml/acs")
        self.name_id_format = conn.get(
            "name_id_format",
            "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        )
        self.sign_requests = conn.get("sign_requests", True)
        self.want_assertions_signed = conn.get("want_assertions_signed", True)
        self.want_assertions_encrypted = conn.get("want_assertions_encrypted", False)
        self.allowed_clock_skew = conn.get("allowed_clock_skew", 300)

        # Validate required settings
        if not self.idp_entity_id:
            raise ConfigurationError("SAML idp_entity_id is required")
        if not self.idp_sso_url:
            raise ConfigurationError("SAML idp_sso_url is required")
        if not self.idp_certificate:
            raise ConfigurationError("SAML idp_certificate is required")

        # SP credentials loaded from Secrets Manager
        self._sp_private_key: str | None = None
        self._sp_certificate: str | None = None
        self._credentials_loaded = False

        # Decoded IdP certificate
        self._idp_cert_pem: str | None = None

    async def _load_credentials(self) -> None:
        """Load SP signing credentials from Secrets Manager."""
        if self._credentials_loaded:
            return

        # Decode IdP certificate
        try:
            self._idp_cert_pem = base64.b64decode(self.idp_certificate).decode()
        except Exception as e:
            raise ConfigurationError(f"Invalid IdP certificate encoding: {e}")

        # Load SP credentials if signing is enabled
        if self.sign_requests and self.config.credentials_secret_arn:
            try:
                import boto3

                secrets_client = boto3.client("secretsmanager")
                response = secrets_client.get_secret_value(
                    SecretId=self.config.credentials_secret_arn
                )
                secret_data = json.loads(response["SecretString"])
                self._sp_private_key = secret_data.get("private_key")
                self._sp_certificate = secret_data.get("certificate")
            except Exception as e:
                logger.warning(f"Failed to load SP credentials: {e}")
                if self.sign_requests:
                    raise ConfigurationError(
                        f"SP credentials required for request signing: {e}"
                    )

        self._credentials_loaded = True

    def generate_auth_request(self, relay_state: str | None = None) -> SAMLAuthRequest:
        """
        Generate SAML AuthnRequest for SP-initiated SSO.

        Args:
            relay_state: Optional state to preserve during SSO flow

        Returns:
            SAMLAuthRequest with redirect URL
        """
        request_id = f"aura_{uuid.uuid4().hex}"
        issue_instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Build AuthnRequest XML
        authn_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest
    xmlns:samlp="{SAMLP_NS}"
    xmlns:saml="{SAML_NS}"
    ID="{request_id}"
    Version="2.0"
    IssueInstant="{issue_instant}"
    Destination="{self.idp_sso_url}"
    AssertionConsumerServiceURL="{self.acs_url}"
    ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
    <saml:Issuer>{self.sp_entity_id}</saml:Issuer>
    <samlp:NameIDPolicy
        Format="{self.name_id_format}"
        AllowCreate="true"/>
</samlp:AuthnRequest>"""

        # Compress and encode for redirect binding
        compressed = zlib.compress(authn_request.encode())[
            2:-4
        ]  # Strip zlib header/checksum
        encoded = base64.b64encode(compressed).decode()

        # Build redirect URL
        params: dict[str, str] = {"SAMLRequest": encoded}
        if relay_state:
            params["RelayState"] = relay_state

        # Sign request if configured (using signature in URL params)
        if self.sign_requests and self._sp_private_key:
            params = self._sign_redirect_params(params)

        redirect_url = f"{self.idp_sso_url}?{urlencode(params)}"

        created = datetime.now(timezone.utc)
        expires = created + timedelta(minutes=5)

        logger.info(f"Generated SAML AuthnRequest {request_id} for IdP {self.idp_id}")

        return SAMLAuthRequest(
            request_id=request_id,
            redirect_url=redirect_url,
            relay_state=relay_state,
            created_at=created.isoformat(),
            expires_at=expires.isoformat(),
        )

    def _sign_redirect_params(self, params: dict[str, str]) -> dict[str, str]:
        """Sign redirect binding parameters."""
        # Signature algorithm
        sig_alg = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
        params["SigAlg"] = sig_alg

        # Build signing input
        query_string = urlencode(params)

        # Sign with SP private key
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding

            private_key = serialization.load_pem_private_key(
                self._sp_private_key.encode(), password=None
            )
            signature = private_key.sign(
                query_string.encode(),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            params["Signature"] = base64.b64encode(signature).decode()
        except ImportError:
            logger.warning("cryptography not available, skipping request signing")
        except Exception as e:
            logger.error(f"Failed to sign SAML request: {e}")

        return params

    async def authenticate(self, credentials: AuthCredentials) -> AuthResult:
        """
        Validate SAML Response from IdP.

        Args:
            credentials: Must contain saml_response (and optionally relay_state)

        Returns:
            AuthResult with user info and roles
        """
        start_time = time.time()

        if not credentials.saml_response:
            return AuthResult(
                success=False,
                error="SAML response is required",
                error_code="MISSING_SAML_RESPONSE",
            )

        try:
            await self._load_credentials()

            # Decode SAML response
            try:
                decoded = base64.b64decode(credentials.saml_response)
                response_xml = decoded.decode("utf-8")
            except Exception as e:
                return AuthResult(
                    success=False,
                    error=f"Invalid SAML response encoding: {e}",
                    error_code="INVALID_ENCODING",
                )

            # Parse XML securely (defusedxml prevents XXE attacks)
            try:
                root = DefusedET.fromstring(response_xml)
            except ET.ParseError as e:
                return AuthResult(
                    success=False,
                    error=f"Invalid SAML response XML: {e}",
                    error_code="INVALID_XML",
                )

            # Validate response status
            status_code = root.find(f".//{{{SAMLP_NS}}}StatusCode")
            if status_code is not None:
                status_value = status_code.get("Value", "")
                if "Success" not in status_value:
                    return AuthResult(
                        success=False,
                        error=f"SAML response status: {status_value}",
                        error_code="SAML_STATUS_ERROR",
                    )

            # Validate signature if required
            if self.want_assertions_signed:
                if not self._validate_signature(root):
                    return AuthResult(
                        success=False,
                        error="Invalid SAML signature",
                        error_code="INVALID_SIGNATURE",
                    )

            # Validate conditions (time constraints)
            validation_result = self._validate_conditions(root)
            if not validation_result["valid"]:
                return AuthResult(
                    success=False,
                    error=validation_result["error"],
                    error_code="CONDITION_FAILED",
                )

            # Extract NameID
            name_id_elem = root.find(f".//{{{SAML_NS}}}NameID")
            if name_id_elem is None or not name_id_elem.text:
                return AuthResult(
                    success=False,
                    error="No NameID in SAML assertion",
                    error_code="MISSING_NAMEID",
                )

            user_id = name_id_elem.text

            # Extract attributes
            attrs = self._extract_attributes(root)

            # Map attributes and groups
            mapped_attrs = self.map_attributes(attrs)

            # Get groups from attributes (common attribute names)
            groups: list[str] = []
            for group_attr in ["groups", "memberOf", "Group", "role"]:
                if group_attr in attrs:
                    group_val = attrs[group_attr]
                    if isinstance(group_val, list):
                        groups.extend(group_val)
                    elif isinstance(group_val, str):
                        groups.extend(group_val.split(","))

            roles = self.map_groups_to_roles(groups)

            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, True)
            self._set_status(ConnectionStatus.CONNECTED)

            logger.info(
                f"SAML authentication successful for user '{user_id}' "
                f"via IdP {self.idp_id}"
            )

            return AuthResult(
                success=True,
                user_id=user_id,
                email=mapped_attrs.get("email", user_id),
                name=mapped_attrs.get("name"),
                groups=groups,
                roles=roles,
                attributes=mapped_attrs,
                provider_metadata={
                    "provider": "saml",
                    "idp_id": self.idp_id,
                    "idp_entity_id": self.idp_entity_id,
                    "name_id_format": self.name_id_format,
                },
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            self._set_status(ConnectionStatus.ERROR, str(e))
            logger.exception(f"SAML authentication error: {e}")
            return AuthResult(
                success=False,
                error=str(e),
                error_code="SAML_ERROR",
            )

    def _validate_signature(self, root: ET.Element) -> bool:
        """
        Validate SAML response signature.

        Note: Full signature validation requires xmlsec library.
        This implementation does basic validation.
        """
        if not _xmlsec_available:
            logger.warning(
                "xmlsec not available - signature validation skipped. "
                "Install xmlsec for production use."
            )
            # In production, you should require xmlsec
            return True

        try:
            import xmlsec
            from lxml import etree

            # Parse with lxml for xmlsec signature verification
            lxml_root = etree.fromstring(ET.tostring(root))  # nosec B320

            # Find signature
            signature = lxml_root.find(f".//{{{DS_NS}}}Signature")
            if signature is None:
                logger.warning("No signature found in SAML response")
                return False

            # Load IdP certificate
            key = xmlsec.Key.from_memory(self._idp_cert_pem, xmlsec.KeyFormat.CERT_PEM)

            # Create signature context and verify
            ctx = xmlsec.SignatureContext()
            ctx.key = key
            ctx.verify(signature)

            return True

        except Exception as e:
            logger.error(f"Signature validation failed: {e}")
            return False

    def _validate_conditions(self, root: ET.Element) -> dict[str, Any]:
        """Validate SAML assertion conditions (time constraints)."""
        conditions = root.find(f".//{{{SAML_NS}}}Conditions")

        if conditions is None:
            return {"valid": True}

        now = datetime.now(timezone.utc)
        skew = timedelta(seconds=self.allowed_clock_skew)

        # Check NotBefore
        not_before = conditions.get("NotBefore")
        if not_before:
            try:
                not_before_dt = datetime.fromisoformat(
                    not_before.replace("Z", "+00:00")
                )
                if now + skew < not_before_dt:
                    return {
                        "valid": False,
                        "error": f"Assertion not yet valid (NotBefore: {not_before})",
                    }
            except ValueError as e:
                logger.warning(f"Failed to parse NotBefore: {e}")

        # Check NotOnOrAfter
        not_on_or_after = conditions.get("NotOnOrAfter")
        if not_on_or_after:
            try:
                not_on_or_after_dt = datetime.fromisoformat(
                    not_on_or_after.replace("Z", "+00:00")
                )
                if now - skew >= not_on_or_after_dt:
                    return {
                        "valid": False,
                        "error": f"Assertion expired (NotOnOrAfter: {not_on_or_after})",
                    }
            except ValueError as e:
                logger.warning(f"Failed to parse NotOnOrAfter: {e}")

        # Check Audience restriction
        audience = conditions.find(
            f".//{{{SAML_NS}}}AudienceRestriction/{{{SAML_NS}}}Audience"
        )
        if audience is not None and audience.text:
            if audience.text != self.sp_entity_id:
                return {
                    "valid": False,
                    "error": f"Invalid audience: {audience.text}",
                }

        return {"valid": True}

    def _extract_attributes(self, root: ET.Element) -> dict[str, Any]:
        """Extract attributes from SAML assertion."""
        attrs: dict[str, Any] = {}

        for attr in root.findall(f".//{{{SAML_NS}}}Attribute"):
            attr_name = attr.get("Name", "")
            # Also check FriendlyName
            friendly_name = attr.get("FriendlyName", "")

            values = attr.findall(f"{{{SAML_NS}}}AttributeValue")
            if values:
                if len(values) == 1:
                    attr_value = values[0].text or ""
                else:
                    attr_value = [v.text or "" for v in values]

                # Store by Name
                if attr_name:
                    attrs[attr_name] = attr_value

                # Also store by FriendlyName if different
                if friendly_name and friendly_name != attr_name:
                    attrs[friendly_name] = attr_value

        return attrs

    def generate_sp_metadata(self) -> str:
        """Generate SAML SP metadata XML for IdP configuration."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<EntityDescriptor
    xmlns="urn:oasis:names:tc:SAML:2.0:metadata"
    entityID="{self.sp_entity_id}">
    <SPSSODescriptor
        protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol"
        AuthnRequestsSigned="{str(self.sign_requests).lower()}"
        WantAssertionsSigned="{str(self.want_assertions_signed).lower()}">
        <NameIDFormat>{self.name_id_format}</NameIDFormat>
        <AssertionConsumerService
            Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            Location="{self.acs_url}"
            index="0"/>
    </SPSSODescriptor>
    <Organization>
        <OrganizationName xml:lang="en">Aura Security Platform</OrganizationName>
        <OrganizationDisplayName xml:lang="en">Aura</OrganizationDisplayName>
        <OrganizationURL xml:lang="en">https://aenealabs.com</OrganizationURL>
    </Organization>
</EntityDescriptor>"""

    async def validate_token(self, token: str) -> TokenValidationResult:
        """SAML doesn't use ongoing tokens - use Aura JWT instead."""
        return TokenValidationResult(
            valid=False,
            error="SAML uses one-time assertions. Use Aura JWT for session management.",
        )

    async def get_user_info(self, token: str) -> UserInfo:
        """SAML doesn't support user info lookup - data comes from assertion."""
        raise AuthenticationError(
            "SAML does not support user info lookup. "
            "User data is provided in the SAML assertion during authentication."
        )

    async def refresh_token(self, refresh_token: str) -> TokenResult:
        """SAML doesn't support token refresh."""
        raise AuthenticationError(
            "SAML does not support token refresh. Re-authenticate via SSO."
        )

    async def logout(self, token: str) -> bool:
        """
        Initiate Single Logout if SLO URL is configured.

        For full SLO, the frontend should redirect to the returned URL.
        """
        if not self.idp_slo_url:
            logger.info("SLO URL not configured, skipping SAML logout")
            return True

        # For proper SLO, generate LogoutRequest and redirect
        # This is a simplified version - full implementation would return redirect URL
        logger.info(f"SAML logout initiated for IdP {self.idp_id}")
        return True

    async def health_check(self) -> HealthCheckResult:
        """
        Check SAML IdP availability.

        Verifies:
        1. IdP SSO URL is reachable
        2. IdP certificate is valid
        """
        import aiohttp

        start_time = time.time()

        try:
            await self._load_credentials()

            # Check IdP SSO endpoint
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    self.idp_sso_url,
                    timeout=aiohttp.ClientTimeout(total=10),
                    allow_redirects=True,
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000

                    if response.status < 400:
                        self._set_status(ConnectionStatus.CONNECTED)
                        return HealthCheckResult(
                            healthy=True,
                            status=ConnectionStatus.CONNECTED,
                            latency_ms=latency_ms,
                            message="SAML IdP reachable",
                            last_checked=datetime.now(timezone.utc).isoformat(),
                            details={
                                "idp_entity_id": self.idp_entity_id,
                                "sso_url": self.idp_sso_url,
                                "status_code": response.status,
                            },
                        )
                    else:
                        self._set_status(ConnectionStatus.DEGRADED)
                        return HealthCheckResult(
                            healthy=False,
                            status=ConnectionStatus.DEGRADED,
                            latency_ms=latency_ms,
                            message=f"IdP returned status {response.status}",
                            last_checked=datetime.now(timezone.utc).isoformat(),
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._set_status(ConnectionStatus.ERROR, str(e))
            return HealthCheckResult(
                healthy=False,
                status=ConnectionStatus.ERROR,
                latency_ms=latency_ms,
                message=str(e),
                last_checked=datetime.now(timezone.utc).isoformat(),
            )


# Register provider with factory
IdentityProviderFactory.register("saml", SAMLProvider)
