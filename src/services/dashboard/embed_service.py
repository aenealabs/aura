"""Dashboard Embedding Service.

Enables secure embedding of dashboards in external applications via iframe/API.
Implements ADR-064 Phase 3 dashboard embedding functionality.

Features:
- Secure embed tokens with HMAC signing
- Configurable expiration (1 hour to 30 days)
- Domain restrictions for iframe security
- Multiple embed modes (full, minimal, widget-only)
- Token revocation support
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# Secret key loaded from environment variable (required in production)
DEFAULT_EMBED_SECRET = os.environ.get("AURA_EMBED_SECRET_KEY", "dev-placeholder-key")


class EmbedMode(str, Enum):
    """Dashboard embed display modes."""

    FULL = "full"  # Full dashboard with header and controls
    MINIMAL = "minimal"  # Dashboard without header/navigation
    WIDGET_ONLY = "widget_only"  # Single widget view


class EmbedTheme(str, Enum):
    """Embed color themes."""

    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"  # Follow system preference


class EmbedTokenCreate(BaseModel):
    """Request model for creating an embed token."""

    expires_in_hours: int = Field(
        default=24,
        ge=1,
        le=720,  # Max 30 days
        description="Token expiration time in hours (1-720)",
    )
    allowed_domains: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Allowed domains for iframe embedding (empty = all)",
    )
    mode: EmbedMode = Field(
        default=EmbedMode.MINIMAL,
        description="Dashboard display mode",
    )
    theme: EmbedTheme = Field(
        default=EmbedTheme.LIGHT,
        description="Color theme for embedded dashboard",
    )
    show_title: bool = Field(
        default=True,
        description="Show dashboard title",
    )
    show_refresh: bool = Field(
        default=True,
        description="Show refresh button",
    )
    show_fullscreen: bool = Field(
        default=False,
        description="Show fullscreen toggle",
    )
    widget_ids: list[str] | None = Field(
        default=None,
        description="Specific widget IDs to display (None = all widgets)",
    )
    custom_css: str | None = Field(
        default=None,
        max_length=5000,
        description="Custom CSS for styling (sanitized)",
    )

    @field_validator("allowed_domains")
    @classmethod
    def validate_domains(cls, v: list[str]) -> list[str]:
        """Validate domain format."""
        validated = []
        for domain in v:
            # Basic domain validation
            domain = domain.lower().strip()
            if domain and not domain.startswith("http"):
                validated.append(domain)
            elif domain.startswith("https://"):
                validated.append(domain.replace("https://", ""))
            elif domain.startswith("http://"):
                validated.append(domain.replace("http://", ""))
        return validated


class EmbedToken(BaseModel):
    """Embed token with metadata."""

    token_id: str = Field(..., description="Unique token identifier")
    dashboard_id: str = Field(..., description="Embedded dashboard ID")
    user_id: str = Field(..., description="Token creator user ID")
    token: str = Field(..., description="Signed embed token")
    embed_url: str = Field(..., description="Full embed URL")
    mode: EmbedMode = Field(..., description="Display mode")
    theme: EmbedTheme = Field(..., description="Color theme")
    show_title: bool = Field(..., description="Show title flag")
    show_refresh: bool = Field(..., description="Show refresh flag")
    show_fullscreen: bool = Field(..., description="Show fullscreen flag")
    widget_ids: list[str] | None = Field(..., description="Filtered widget IDs")
    allowed_domains: list[str] = Field(..., description="Allowed iframe domains")
    expires_at: datetime = Field(..., description="Token expiration time")
    created_at: datetime = Field(..., description="Token creation time")
    is_active: bool = Field(default=True, description="Token active status")
    access_count: int = Field(default=0, description="Number of accesses")
    last_accessed_at: datetime | None = Field(
        default=None, description="Last access time"
    )

    class Config:
        """Pydantic config."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class EmbedTokenUpdate(BaseModel):
    """Request model for updating an embed token."""

    is_active: bool | None = Field(default=None, description="Enable/disable token")
    allowed_domains: list[str] | None = Field(
        default=None,
        max_length=10,
        description="Update allowed domains",
    )


class EmbedValidationResult(BaseModel):
    """Result of embed token validation."""

    valid: bool = Field(..., description="Whether token is valid")
    dashboard_id: str | None = Field(default=None, description="Dashboard ID if valid")
    token_id: str | None = Field(default=None, description="Token ID if valid")
    mode: EmbedMode | None = Field(default=None, description="Display mode")
    theme: EmbedTheme | None = Field(default=None, description="Theme")
    show_title: bool = Field(default=True, description="Show title")
    show_refresh: bool = Field(default=True, description="Show refresh")
    show_fullscreen: bool = Field(default=False, description="Show fullscreen")
    widget_ids: list[str] | None = Field(default=None, description="Widget filter")
    custom_css: str | None = Field(default=None, description="Custom CSS")
    error: str | None = Field(default=None, description="Error message if invalid")


class EmbedDashboardData(BaseModel):
    """Dashboard data for embedded view."""

    dashboard_id: str = Field(..., description="Dashboard ID")
    name: str = Field(..., description="Dashboard name")
    description: str = Field(default="", description="Dashboard description")
    layout: dict = Field(..., description="Layout configuration")
    widgets: list[dict] = Field(..., description="Widget configurations")
    mode: EmbedMode = Field(..., description="Display mode")
    theme: EmbedTheme = Field(..., description="Color theme")
    show_title: bool = Field(..., description="Show title")
    show_refresh: bool = Field(..., description="Show refresh")
    show_fullscreen: bool = Field(..., description="Show fullscreen")
    custom_css: str | None = Field(default=None, description="Custom CSS")


class DashboardEmbedService:
    """Service for managing dashboard embedding.

    Provides secure token generation, validation, and management
    for embedding dashboards in external applications.
    """

    # Token limits
    MAX_TOKENS_PER_DASHBOARD = 10
    MAX_TOKENS_PER_USER = 50

    def __init__(self, secret_key: str | None = None, base_url: str | None = None):
        """Initialize the embed service.

        Args:
            secret_key: Secret key for token signing (uses default if not provided)
            base_url: Base URL for embed URLs (e.g., https://app.aura.ai)
        """
        self._secret_key = secret_key or DEFAULT_EMBED_SECRET
        self._base_url = base_url or "https://app.aura.ai"
        self._tokens: dict[str, EmbedToken] = {}
        self._dashboard_tokens: dict[str, list[str]] = {}
        self._user_tokens: dict[str, list[str]] = {}

    def create_embed_token(
        self,
        dashboard_id: str,
        user_id: str,
        token_data: EmbedTokenCreate,
    ) -> EmbedToken:
        """Create a new embed token for a dashboard.

        Args:
            dashboard_id: Dashboard to embed
            user_id: User creating the token
            token_data: Token configuration

        Returns:
            Created EmbedToken

        Raises:
            ValueError: If limits exceeded
        """
        # Check dashboard token limit
        dashboard_tokens = self._dashboard_tokens.get(dashboard_id, [])
        active_count = sum(
            1
            for tid in dashboard_tokens
            if tid in self._tokens and self._tokens[tid].is_active
        )
        if active_count >= self.MAX_TOKENS_PER_DASHBOARD:
            raise ValueError(
                f"Maximum {self.MAX_TOKENS_PER_DASHBOARD} active tokens per dashboard"
            )

        # Check user token limit
        user_tokens = self._user_tokens.get(user_id, [])
        user_active = sum(
            1
            for tid in user_tokens
            if tid in self._tokens and self._tokens[tid].is_active
        )
        if user_active >= self.MAX_TOKENS_PER_USER:
            raise ValueError(
                f"Maximum {self.MAX_TOKENS_PER_USER} active tokens per user"
            )

        # Generate token ID and timestamps
        token_id = f"emb-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=token_data.expires_in_hours)

        # Create token payload
        payload = {
            "tid": token_id,
            "did": dashboard_id,
            "uid": user_id,
            "exp": int(expires_at.timestamp()),
            "mode": token_data.mode.value,
            "theme": token_data.theme.value,
            "st": token_data.show_title,
            "sr": token_data.show_refresh,
            "sf": token_data.show_fullscreen,
            "wids": token_data.widget_ids,
            "css": token_data.custom_css,
            "doms": token_data.allowed_domains,
        }

        # Sign the token
        signed_token = self._sign_token(payload)

        # Build embed URL
        embed_url = f"{self._base_url}/embed/{signed_token}"

        embed_token = EmbedToken(
            token_id=token_id,
            dashboard_id=dashboard_id,
            user_id=user_id,
            token=signed_token,
            embed_url=embed_url,
            mode=token_data.mode,
            theme=token_data.theme,
            show_title=token_data.show_title,
            show_refresh=token_data.show_refresh,
            show_fullscreen=token_data.show_fullscreen,
            widget_ids=token_data.widget_ids,
            allowed_domains=token_data.allowed_domains,
            expires_at=expires_at,
            created_at=now,
        )

        # Store token
        self._tokens[token_id] = embed_token
        if dashboard_id not in self._dashboard_tokens:
            self._dashboard_tokens[dashboard_id] = []
        self._dashboard_tokens[dashboard_id].append(token_id)
        if user_id not in self._user_tokens:
            self._user_tokens[user_id] = []
        self._user_tokens[user_id].append(token_id)

        logger.info(
            f"Embed token created: {token_id} for dashboard {dashboard_id} "
            f"(expires: {expires_at.isoformat()})"
        )
        return embed_token

    def validate_token(
        self,
        token: str,
        requesting_domain: str | None = None,
    ) -> EmbedValidationResult:
        """Validate an embed token.

        Args:
            token: Signed embed token
            requesting_domain: Domain making the request (for domain restriction check)

        Returns:
            EmbedValidationResult with validation status
        """
        # Verify signature and decode
        payload = self._verify_token(token)
        if payload is None:
            return EmbedValidationResult(
                valid=False,
                error="Invalid token signature",
            )

        # Check expiration
        exp = payload.get("exp", 0)
        if datetime.now(timezone.utc).timestamp() > exp:
            return EmbedValidationResult(
                valid=False,
                error="Token has expired",
            )

        # Check if token exists and is active
        token_id = payload.get("tid")
        if token_id not in self._tokens:
            return EmbedValidationResult(
                valid=False,
                error="Token not found",
            )

        stored_token = self._tokens[token_id]
        if not stored_token.is_active:
            return EmbedValidationResult(
                valid=False,
                error="Token has been revoked",
            )

        # Check domain restrictions
        allowed_domains = payload.get("doms", [])
        if allowed_domains and requesting_domain:
            domain_allowed = any(requesting_domain.endswith(d) for d in allowed_domains)
            if not domain_allowed:
                return EmbedValidationResult(
                    valid=False,
                    error=f"Domain {requesting_domain} not allowed",
                )

        # Update access stats
        stored_token.access_count += 1
        stored_token.last_accessed_at = datetime.now(timezone.utc)

        return EmbedValidationResult(
            valid=True,
            dashboard_id=payload.get("did"),
            token_id=token_id,
            mode=EmbedMode(payload.get("mode", "minimal")),
            theme=EmbedTheme(payload.get("theme", "light")),
            show_title=payload.get("st", True),
            show_refresh=payload.get("sr", True),
            show_fullscreen=payload.get("sf", False),
            widget_ids=payload.get("wids"),
            custom_css=payload.get("css"),
        )

    def get_token(self, token_id: str, user_id: str) -> EmbedToken:
        """Get an embed token by ID.

        Args:
            token_id: Token ID
            user_id: Requesting user ID

        Returns:
            EmbedToken

        Raises:
            KeyError: If token not found
            PermissionError: If user doesn't own the token
        """
        if token_id not in self._tokens:
            raise KeyError(f"Embed token {token_id} not found")

        token = self._tokens[token_id]
        if token.user_id != user_id:
            raise PermissionError("Access denied to this embed token")

        return token

    def list_tokens(
        self,
        dashboard_id: str,
        user_id: str,
    ) -> list[EmbedToken]:
        """List embed tokens for a dashboard.

        Args:
            dashboard_id: Dashboard ID
            user_id: User ID (for permission filtering)

        Returns:
            List of EmbedTokens
        """
        token_ids = self._dashboard_tokens.get(dashboard_id, [])
        tokens = []

        for token_id in token_ids:
            token = self._tokens.get(token_id)
            if token and token.user_id == user_id:
                tokens.append(token)

        return tokens

    def list_user_tokens(self, user_id: str) -> list[EmbedToken]:
        """List all embed tokens for a user.

        Args:
            user_id: User ID

        Returns:
            List of EmbedTokens
        """
        token_ids = self._user_tokens.get(user_id, [])
        return [self._tokens[tid] for tid in token_ids if tid in self._tokens]

    def update_token(
        self,
        token_id: str,
        user_id: str,
        updates: EmbedTokenUpdate,
    ) -> EmbedToken:
        """Update an embed token.

        Args:
            token_id: Token ID
            user_id: User ID
            updates: Update data

        Returns:
            Updated EmbedToken

        Raises:
            KeyError: If token not found
            PermissionError: If user doesn't own the token
        """
        token = self.get_token(token_id, user_id)

        if updates.is_active is not None:
            token.is_active = updates.is_active

        if updates.allowed_domains is not None:
            token.allowed_domains = updates.allowed_domains

        logger.info(f"Embed token updated: {token_id}")
        return token

    def revoke_token(self, token_id: str, user_id: str) -> None:
        """Revoke an embed token.

        Args:
            token_id: Token ID
            user_id: User ID

        Raises:
            KeyError: If token not found
            PermissionError: If user doesn't own the token
        """
        token = self.get_token(token_id, user_id)
        token.is_active = False
        logger.info(f"Embed token revoked: {token_id}")

    def delete_token(self, token_id: str, user_id: str) -> None:
        """Delete an embed token permanently.

        Args:
            token_id: Token ID
            user_id: User ID

        Raises:
            KeyError: If token not found
            PermissionError: If user doesn't own the token
        """
        token = self.get_token(token_id, user_id)

        # Remove from all indexes
        del self._tokens[token_id]
        self._dashboard_tokens[token.dashboard_id].remove(token_id)
        self._user_tokens[user_id].remove(token_id)

        logger.info(f"Embed token deleted: {token_id}")

    def get_iframe_html(
        self,
        token: str,
        width: str = "100%",
        height: str = "600px",
    ) -> str:
        """Generate iframe HTML snippet for embedding.

        Args:
            token: Embed token
            width: iframe width (CSS value)
            height: iframe height (CSS value)

        Returns:
            HTML iframe snippet
        """
        embed_url = f"{self._base_url}/embed/{token}"
        return f"""<iframe
  src="{embed_url}"
  width="{width}"
  height="{height}"
  frameborder="0"
  allowfullscreen
  style="border: none; border-radius: 8px;"
></iframe>"""

    def _sign_token(self, payload: dict) -> str:
        """Sign a token payload using HMAC-SHA256.

        Args:
            payload: Token payload dictionary

        Returns:
            Base64url-encoded signed token
        """
        # Encode payload
        payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()

        # Create signature
        signature = hmac.new(
            self._secret_key.encode(),
            payload_b64.encode(),
            hashlib.sha256,
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

        return f"{payload_b64}.{signature_b64}"

    def _verify_token(self, token: str) -> dict | None:
        """Verify and decode a signed token.

        Args:
            token: Signed token string

        Returns:
            Decoded payload if valid, None otherwise
        """
        try:
            parts = token.split(".")
            if len(parts) != 2:
                return None

            payload_b64, signature_b64 = parts

            # Verify signature
            expected_sig = hmac.new(
                self._secret_key.encode(),
                payload_b64.encode(),
                hashlib.sha256,
            ).digest()
            expected_sig_b64 = (
                base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")
            )

            if not hmac.compare_digest(signature_b64, expected_sig_b64):
                return None

            # Decode payload
            # Add padding if needed
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding

            payload_json = base64.urlsafe_b64decode(payload_b64).decode()
            return json.loads(payload_json)

        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
            return None


# Singleton instance
_service_instance: DashboardEmbedService | None = None


def get_embed_service() -> DashboardEmbedService:
    """Get the dashboard embed service singleton.

    Returns:
        DashboardEmbedService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = DashboardEmbedService()
    return _service_instance
