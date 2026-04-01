"""
Project Aura - Saviynt Connector

Implements ADR-053: Enterprise Security Integrations

Saviynt Enterprise Identity Cloud (EIC) connector for:
- User Management - identity profiles and attributes
- Entitlements - access permissions and roles
- Access Requests - approval workflow integration
- Certifications - periodic access review status
- PAM Sessions - privileged access audit trail
- Risk Analytics - user and access risk scoring

SECURITY: Only available in ENTERPRISE or HYBRID mode.

Usage:
    >>> from src.services.saviynt_connector import SaviyntConnector
    >>> saviynt = SaviyntConnector(
    ...     base_url="https://company.saviyntcloud.com",
    ...     username="api-user",
    ...     password="api-password"
    ... )
    >>> user = await saviynt.get_user("john.doe@company.com")
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import aiohttp

from src.config import require_enterprise_mode
from src.services.external_tool_connectors import (
    ConnectorResult,
    ConnectorStatus,
    ExternalToolConnector,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class SaviyntUserStatus(Enum):
    """Saviynt user status values."""

    ACTIVE = "Active"
    INACTIVE = "Inactive"
    SUSPENDED = "Suspended"
    TERMINATED = "Terminated"
    NEW = "New"


class SaviyntRiskLevel(Enum):
    """Saviynt risk levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class SaviyntAccessRequestStatus(Enum):
    """Saviynt access request status values."""

    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"
    EXPIRED = "Expired"
    COMPLETED = "Completed"


class SaviyntCertificationStatus(Enum):
    """Saviynt certification campaign status."""

    ACTIVE = "Active"
    COMPLETED = "Completed"
    EXPIRED = "Expired"
    DRAFT = "Draft"


class SaviyntEntitlementType(Enum):
    """Saviynt entitlement types."""

    ROLE = "Role"
    ENTITLEMENT = "Entitlement"
    ACCOUNT = "Account"
    ACCESS = "Access"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SaviyntUser:
    """Saviynt user identity profile."""

    user_key: str
    username: str
    email: str
    first_name: str = ""
    last_name: str = ""
    display_name: str = ""
    status: SaviyntUserStatus = SaviyntUserStatus.ACTIVE
    manager: str | None = None
    department: str | None = None
    title: str | None = None
    location: str | None = None
    risk_score: int = 0
    risk_level: SaviyntRiskLevel = SaviyntRiskLevel.NONE
    created_date: str | None = None
    last_login: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_key": self.user_key,
            "username": self.username,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "display_name": self.display_name,
            "status": self.status.value,
            "manager": self.manager,
            "department": self.department,
            "title": self.title,
            "location": self.location,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value,
            "created_date": self.created_date,
            "last_login": self.last_login,
            "attributes": self.attributes,
        }


@dataclass
class SaviyntEntitlement:
    """Saviynt entitlement/role."""

    entitlement_key: str
    entitlement_name: str
    entitlement_type: SaviyntEntitlementType
    description: str = ""
    application: str | None = None
    owner: str | None = None
    risk_score: int = 0
    sod_critical: bool = False
    requestable: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entitlement_key": self.entitlement_key,
            "entitlement_name": self.entitlement_name,
            "entitlement_type": self.entitlement_type.value,
            "description": self.description,
            "application": self.application,
            "owner": self.owner,
            "risk_score": self.risk_score,
            "sod_critical": self.sod_critical,
            "requestable": self.requestable,
            "attributes": self.attributes,
        }


@dataclass
class SaviyntAccessRequest:
    """Saviynt access request."""

    request_key: str
    requestor: str
    beneficiary: str
    status: SaviyntAccessRequestStatus
    request_type: str = ""
    entitlements: list[str] = field(default_factory=list)
    justification: str = ""
    created_date: str | None = None
    approved_date: str | None = None
    approvers: list[str] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_key": self.request_key,
            "requestor": self.requestor,
            "beneficiary": self.beneficiary,
            "status": self.status.value,
            "request_type": self.request_type,
            "entitlements": self.entitlements,
            "justification": self.justification,
            "created_date": self.created_date,
            "approved_date": self.approved_date,
            "approvers": self.approvers,
            "comments": self.comments,
        }


@dataclass
class SaviyntCertification:
    """Saviynt certification campaign."""

    certification_key: str
    certification_name: str
    status: SaviyntCertificationStatus
    owner: str
    start_date: str | None = None
    end_date: str | None = None
    total_items: int = 0
    certified_items: int = 0
    revoked_items: int = 0
    pending_items: int = 0
    completion_percentage: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "certification_key": self.certification_key,
            "certification_name": self.certification_name,
            "status": self.status.value,
            "owner": self.owner,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_items": self.total_items,
            "certified_items": self.certified_items,
            "revoked_items": self.revoked_items,
            "pending_items": self.pending_items,
            "completion_percentage": self.completion_percentage,
        }


@dataclass
class SaviyntPAMSession:
    """Saviynt privileged access session."""

    session_id: str
    user: str
    account: str
    endpoint: str
    start_time: str
    end_time: str | None = None
    status: str = "Active"
    session_type: str = ""  # RDP, SSH, Database, etc.
    actions_performed: int = 0
    risk_events: int = 0
    recording_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "user": self.user,
            "account": self.account,
            "endpoint": self.endpoint,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "session_type": self.session_type,
            "actions_performed": self.actions_performed,
            "risk_events": self.risk_events,
            "recording_url": self.recording_url,
        }


@dataclass
class SaviyntRiskScore:
    """Saviynt risk analytics score."""

    entity_type: str  # user, entitlement, account
    entity_id: str
    overall_score: int
    access_risk: int = 0
    behavior_risk: int = 0
    compliance_risk: int = 0
    risk_level: SaviyntRiskLevel = SaviyntRiskLevel.NONE
    risk_factors: list[str] = field(default_factory=list)
    last_calculated: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "overall_score": self.overall_score,
            "access_risk": self.access_risk,
            "behavior_risk": self.behavior_risk,
            "compliance_risk": self.compliance_risk,
            "risk_level": self.risk_level.value,
            "risk_factors": self.risk_factors,
            "last_calculated": self.last_calculated,
        }


# =============================================================================
# Saviynt Connector
# =============================================================================


class SaviyntConnector(ExternalToolConnector):
    """
    Saviynt Enterprise Identity Cloud connector.

    Provides integration with Saviynt IGA for:
    - User identity management
    - Entitlement/role governance
    - Access request workflows
    - Certification campaigns
    - PAM session audit
    - Risk analytics

    Authentication: Basic auth with username/password
    Rate Limits: 100 requests/minute (configurable per tenant)
    """

    RATE_LIMIT_REQUESTS_PER_MINUTE = 100
    API_VERSION = "v5"

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        govcloud: bool = False,
    ):
        """
        Initialize Saviynt connector.

        Args:
            base_url: Saviynt tenant URL (e.g., https://company.saviyntcloud.com)
            username: API username
            password: API password
            timeout_seconds: Request timeout
            max_retries: Maximum retry attempts
            govcloud: Use FedRAMP-compliant endpoints
        """
        super().__init__(name="saviynt", timeout_seconds=timeout_seconds)
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.govcloud = govcloud
        self.timeout_seconds = timeout_seconds
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.max_retries = max_retries

        # Session state
        self._token: str | None = None
        self._token_expiry: float = 0
        self._request_timestamps: list[float] = []
        self._status = ConnectorStatus.DISCONNECTED
        self._last_error: str | None = None

        # Metrics
        self._total_requests = 0
        self._failed_requests = 0
        self._total_latency_ms = 0.0

    @property
    def api_base_url(self) -> str:
        """Get API base URL."""
        return f"{self.base_url}/ECM/api/{self.API_VERSION}"

    # =========================================================================
    # Connection Management
    # =========================================================================

    @require_enterprise_mode
    async def connect(self) -> bool:
        """Establish connection and authenticate."""
        return await self._authenticate()

    async def disconnect(self) -> None:
        """Disconnect and invalidate token."""
        self._token = None
        self._token_expiry = 0
        self._status = ConnectorStatus.DISCONNECTED

    async def health_check(self) -> ConnectorResult:
        """Check connector health."""
        start_time = time.time()

        try:
            if not await self._authenticate():
                return ConnectorResult(
                    success=False,
                    error="Authentication failed",
                    latency_ms=(time.time() - start_time) * 1000,
                )

            # Test with a simple API call
            result = await self._make_request("GET", "/users", params={"max": 1})
            return ConnectorResult(
                success=result.success,
                data={"status": "healthy" if result.success else "unhealthy"},
                latency_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )

    def get_status(self) -> dict[str, Any]:
        """Get connector status and metrics."""
        avg_latency = (
            self._total_latency_ms / self._total_requests
            if self._total_requests > 0
            else 0
        )
        return {
            "status": self._status.value,
            "base_url": self.base_url,
            "govcloud": self.govcloud,
            "authenticated": self._token is not None,
            "token_valid": time.time() < self._token_expiry,
            "total_requests": self._total_requests,
            "failed_requests": self._failed_requests,
            "average_latency_ms": avg_latency,
            "last_error": self._last_error,
        }

    # =========================================================================
    # Authentication
    # =========================================================================

    async def _authenticate(self) -> bool:
        """
        Authenticate to Saviynt API.

        Returns:
            True if authentication succeeded
        """
        # Check if existing token is still valid
        if self._token and time.time() < self._token_expiry - 60:
            return True

        payload = {"username": self.username, "password": self.password}

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.api_base_url}/login",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._token = data.get("access_token") or data.get("token")
                        # Default 1 hour expiry
                        expires_in = data.get("expires_in", 3600)
                        self._token_expiry = time.time() + expires_in
                        self._status = ConnectorStatus.CONNECTED
                        logger.info("Saviynt authentication successful")
                        return True
                    else:
                        self._status = ConnectorStatus.AUTH_FAILED
                        self._last_error = f"Auth failed: {response.status}"
                        return False
        except Exception as e:
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            logger.exception(f"Saviynt authentication error: {e}")
            return False

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authorization."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }

    # =========================================================================
    # Rate Limiting
    # =========================================================================

    async def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting."""
        now = time.time()

        # Clean old timestamps
        self._request_timestamps = [
            ts for ts in self._request_timestamps if now - ts < 60
        ]

        if len(self._request_timestamps) >= self.RATE_LIMIT_REQUESTS_PER_MINUTE:
            oldest = self._request_timestamps[0]
            wait_time = 60 - (now - oldest) + 0.1
            if wait_time > 0:
                logger.warning(f"Rate limit reached, waiting {wait_time:.1f}s")
                self._status = ConnectorStatus.RATE_LIMITED
                await asyncio.sleep(wait_time)

        self._request_timestamps.append(time.time())

    # =========================================================================
    # HTTP Request Helper
    # =========================================================================

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        """Make an authenticated API request with retry logic."""
        start_time = time.time()

        if not await self._authenticate():
            return ConnectorResult(
                success=False,
                error="Authentication failed",
                latency_ms=(time.time() - start_time) * 1000,
            )

        await self._check_rate_limit()

        url = f"{self.api_base_url}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.request(
                        method,
                        url,
                        params=params,
                        json=json_data,
                        headers=self._get_headers(),
                    ) as response:
                        latency_ms = (time.time() - start_time) * 1000
                        self._record_request(latency_ms, response.status < 400)

                        if response.status == 429:
                            retry_after = int(response.headers.get("Retry-After", 60))
                            self._status = ConnectorStatus.RATE_LIMITED
                            await asyncio.sleep(retry_after)
                            continue

                        if response.status == 401:
                            self._token = None
                            if await self._authenticate():
                                continue
                            return ConnectorResult(
                                success=False,
                                error="Re-authentication failed",
                                latency_ms=latency_ms,
                            )

                        if response.status >= 400:
                            body = await response.text()
                            return ConnectorResult(
                                success=False,
                                error=f"API error {response.status}: {body}",
                                latency_ms=latency_ms,
                            )

                        data = await response.json()
                        self._status = ConnectorStatus.CONNECTED
                        return ConnectorResult(
                            success=True,
                            data=data,
                            latency_ms=latency_ms,
                        )
            except asyncio.TimeoutError:
                if attempt == self.max_retries - 1:
                    return ConnectorResult(
                        success=False,
                        error="Request timeout",
                        latency_ms=(time.time() - start_time) * 1000,
                    )
                await asyncio.sleep(2**attempt)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    self._status = ConnectorStatus.ERROR
                    self._last_error = str(e)
                    return ConnectorResult(
                        success=False,
                        error=str(e),
                        latency_ms=(time.time() - start_time) * 1000,
                    )
                await asyncio.sleep(2**attempt)

        return ConnectorResult(
            success=False,
            error="Max retries exceeded",
            latency_ms=(time.time() - start_time) * 1000,
        )

    def _record_request(self, latency_ms: float, success: bool) -> None:
        """Record request metrics."""
        self._total_requests += 1
        self._total_latency_ms += latency_ms
        if not success:
            self._failed_requests += 1

    # =========================================================================
    # User Management API
    # =========================================================================

    @require_enterprise_mode
    async def get_user(self, username: str) -> ConnectorResult:
        """
        Get user by username.

        Args:
            username: Username or email

        Returns:
            ConnectorResult with SaviyntUser data
        """
        result = await self._make_request(
            "POST",
            "/getUser",
            json_data={"username": username},
        )

        if result.success and result.data:
            user_data = result.data.get("user", result.data)
            user = SaviyntUser(
                user_key=str(user_data.get("userkey", "")),
                username=user_data.get("username", username),
                email=user_data.get("email", ""),
                first_name=user_data.get("firstname", ""),
                last_name=user_data.get("lastname", ""),
                display_name=user_data.get("displayname", ""),
                status=SaviyntUserStatus(user_data.get("statuskey", "Active")),
                manager=user_data.get("manager"),
                department=user_data.get("departmentname"),
                title=user_data.get("title"),
                location=user_data.get("location"),
                risk_score=user_data.get("riskscore", 0),
                created_date=user_data.get("createddate"),
                last_login=user_data.get("lastlogin"),
            )
            result.data = user.to_dict()

        return result

    @require_enterprise_mode
    async def search_users(
        self,
        query: str | None = None,
        department: str | None = None,
        status: SaviyntUserStatus | None = None,
        max_results: int = 100,
    ) -> ConnectorResult:
        """
        Search users.

        Args:
            query: Search query
            department: Filter by department
            status: Filter by status
            max_results: Maximum results to return

        Returns:
            ConnectorResult with list of users
        """
        filters = {}
        if query:
            filters["searchCriteria"] = query
        if department:
            filters["departmentname"] = department
        if status:
            filters["statuskey"] = status.value

        result = await self._make_request(
            "POST",
            "/getUsers",
            json_data={"max": max_results, **filters},
        )

        if result.success and result.data:
            users = []
            for user_data in result.data.get("users", []):
                user = SaviyntUser(
                    user_key=str(user_data.get("userkey", "")),
                    username=user_data.get("username", ""),
                    email=user_data.get("email", ""),
                    first_name=user_data.get("firstname", ""),
                    last_name=user_data.get("lastname", ""),
                    display_name=user_data.get("displayname", ""),
                    status=SaviyntUserStatus(user_data.get("statuskey", "Active")),
                    department=user_data.get("departmentname"),
                    risk_score=user_data.get("riskscore", 0),
                )
                users.append(user.to_dict())
            result.data = {"users": users, "total": len(users)}

        return result

    # =========================================================================
    # Entitlement API
    # =========================================================================

    @require_enterprise_mode
    async def get_entitlement(self, entitlement_key: str) -> ConnectorResult:
        """
        Get entitlement details.

        Args:
            entitlement_key: Entitlement key/ID

        Returns:
            ConnectorResult with SaviyntEntitlement data
        """
        result = await self._make_request(
            "POST",
            "/getEntitlement",
            json_data={"entitlementkey": entitlement_key},
        )

        if result.success and result.data:
            ent_data = result.data.get("entitlement", result.data)
            entitlement = SaviyntEntitlement(
                entitlement_key=str(ent_data.get("entitlementkey", "")),
                entitlement_name=ent_data.get("entitlementname", ""),
                entitlement_type=SaviyntEntitlementType(
                    ent_data.get("entitlementtype", "Entitlement")
                ),
                description=ent_data.get("description", ""),
                application=ent_data.get("application"),
                owner=ent_data.get("owner"),
                risk_score=ent_data.get("riskscore", 0),
                sod_critical=ent_data.get("sodcritical", False),
                requestable=ent_data.get("requestable", True),
            )
            result.data = entitlement.to_dict()

        return result

    @require_enterprise_mode
    async def get_user_entitlements(self, username: str) -> ConnectorResult:
        """
        Get entitlements for a user.

        Args:
            username: Username

        Returns:
            ConnectorResult with list of entitlements
        """
        result = await self._make_request(
            "POST",
            "/getUserEntitlements",
            json_data={"username": username},
        )

        if result.success and result.data:
            entitlements = []
            for ent_data in result.data.get("entitlements", []):
                entitlement = SaviyntEntitlement(
                    entitlement_key=str(ent_data.get("entitlementkey", "")),
                    entitlement_name=ent_data.get("entitlementname", ""),
                    entitlement_type=SaviyntEntitlementType(
                        ent_data.get("entitlementtype", "Entitlement")
                    ),
                    application=ent_data.get("application"),
                    risk_score=ent_data.get("riskscore", 0),
                )
                entitlements.append(entitlement.to_dict())
            result.data = {"entitlements": entitlements, "total": len(entitlements)}

        return result

    # =========================================================================
    # Access Request API
    # =========================================================================

    @require_enterprise_mode
    async def get_access_request(self, request_key: str) -> ConnectorResult:
        """
        Get access request details.

        Args:
            request_key: Request key/ID

        Returns:
            ConnectorResult with SaviyntAccessRequest data
        """
        result = await self._make_request(
            "POST",
            "/getAccessRequest",
            json_data={"requestkey": request_key},
        )

        if result.success and result.data:
            req_data = result.data.get("request", result.data)
            request = SaviyntAccessRequest(
                request_key=str(req_data.get("requestkey", "")),
                requestor=req_data.get("requestor", ""),
                beneficiary=req_data.get("beneficiary", ""),
                status=SaviyntAccessRequestStatus(req_data.get("status", "Pending")),
                request_type=req_data.get("requesttype", ""),
                entitlements=req_data.get("entitlements", []),
                justification=req_data.get("justification", ""),
                created_date=req_data.get("createddate"),
                approved_date=req_data.get("approveddate"),
                approvers=req_data.get("approvers", []),
            )
            result.data = request.to_dict()

        return result

    @require_enterprise_mode
    async def get_pending_approvals(self, approver: str) -> ConnectorResult:
        """
        Get pending approvals for an approver.

        Args:
            approver: Approver username

        Returns:
            ConnectorResult with list of pending requests
        """
        result = await self._make_request(
            "POST",
            "/getPendingApprovals",
            json_data={"approver": approver},
        )

        if result.success and result.data:
            requests = []
            for req_data in result.data.get("requests", []):
                request = SaviyntAccessRequest(
                    request_key=str(req_data.get("requestkey", "")),
                    requestor=req_data.get("requestor", ""),
                    beneficiary=req_data.get("beneficiary", ""),
                    status=SaviyntAccessRequestStatus.PENDING,
                    request_type=req_data.get("requesttype", ""),
                    justification=req_data.get("justification", ""),
                    created_date=req_data.get("createddate"),
                )
                requests.append(request.to_dict())  # nosec - list append, not HTTP
            result.data = {"requests": requests, "total": len(requests)}

        return result

    @require_enterprise_mode
    async def approve_request(
        self, request_key: str, approver: str, comments: str = ""
    ) -> ConnectorResult:
        """
        Approve an access request.

        Args:
            request_key: Request key/ID
            approver: Approver username
            comments: Approval comments

        Returns:
            ConnectorResult with approval status
        """
        return await self._make_request(
            "POST",
            "/approveRequest",
            json_data={
                "requestkey": request_key,
                "approver": approver,
                "comments": comments,
                "action": "approve",
            },
        )

    @require_enterprise_mode
    async def reject_request(
        self, request_key: str, approver: str, comments: str
    ) -> ConnectorResult:
        """
        Reject an access request.

        Args:
            request_key: Request key/ID
            approver: Approver username
            comments: Rejection reason (required)

        Returns:
            ConnectorResult with rejection status
        """
        return await self._make_request(
            "POST",
            "/rejectRequest",
            json_data={
                "requestkey": request_key,
                "approver": approver,
                "comments": comments,
                "action": "reject",
            },
        )

    # =========================================================================
    # Certification API
    # =========================================================================

    @require_enterprise_mode
    async def get_certifications(
        self,
        status: SaviyntCertificationStatus | None = None,
        owner: str | None = None,
    ) -> ConnectorResult:
        """
        Get certification campaigns.

        Args:
            status: Filter by status
            owner: Filter by owner

        Returns:
            ConnectorResult with list of certifications
        """
        filters = {}
        if status:
            filters["status"] = status.value
        if owner:
            filters["owner"] = owner

        result = await self._make_request(
            "POST",
            "/getCertifications",
            json_data=filters or None,
        )

        if result.success and result.data:
            certs = []
            for cert_data in result.data.get("certifications", []):
                cert = SaviyntCertification(
                    certification_key=str(cert_data.get("certificationkey", "")),
                    certification_name=cert_data.get("certificationname", ""),
                    status=SaviyntCertificationStatus(
                        cert_data.get("status", "Active")
                    ),
                    owner=cert_data.get("owner", ""),
                    start_date=cert_data.get("startdate"),
                    end_date=cert_data.get("enddate"),
                    total_items=cert_data.get("totalitems", 0),
                    certified_items=cert_data.get("certifieditems", 0),
                    revoked_items=cert_data.get("revokeditems", 0),
                    pending_items=cert_data.get("pendingitems", 0),
                    completion_percentage=cert_data.get("completionpercentage", 0),
                )
                certs.append(cert.to_dict())
            result.data = {"certifications": certs, "total": len(certs)}

        return result

    # =========================================================================
    # PAM Session API
    # =========================================================================

    @require_enterprise_mode
    async def get_pam_sessions(
        self,
        user: str | None = None,
        hours: int = 24,
        status: str | None = None,
    ) -> ConnectorResult:
        """
        Get PAM sessions.

        Args:
            user: Filter by user
            hours: Time window in hours
            status: Filter by status (Active, Completed)

        Returns:
            ConnectorResult with list of PAM sessions
        """
        end_time = datetime.now(timezone.utc)
        start_time = datetime.fromtimestamp(
            end_time.timestamp() - (hours * 3600), timezone.utc
        )

        filters = {
            "starttime": start_time.isoformat(),
            "endtime": end_time.isoformat(),
        }
        if user:
            filters["user"] = user
        if status:
            filters["status"] = status

        result = await self._make_request(
            "POST",
            "/privilegedSessions",
            json_data=filters,
        )

        if result.success and result.data:
            sessions = []
            for sess_data in result.data.get("sessions", []):
                session = SaviyntPAMSession(
                    session_id=str(sess_data.get("sessionid", "")),
                    user=sess_data.get("user", ""),
                    account=sess_data.get("account", ""),
                    endpoint=sess_data.get("endpoint", ""),
                    start_time=sess_data.get("starttime", ""),
                    end_time=sess_data.get("endtime"),
                    status=sess_data.get("status", "Active"),
                    session_type=sess_data.get("sessiontype", ""),
                    actions_performed=sess_data.get("actionsperformed", 0),
                    risk_events=sess_data.get("riskevents", 0),
                    recording_url=sess_data.get("recordingurl"),
                )
                sessions.append(session.to_dict())
            result.data = {"sessions": sessions, "total": len(sessions)}

        return result

    # =========================================================================
    # Risk Analytics API
    # =========================================================================

    @require_enterprise_mode
    async def get_user_risk_score(self, username: str) -> ConnectorResult:
        """
        Get risk score for a user.

        Args:
            username: Username

        Returns:
            ConnectorResult with SaviyntRiskScore data
        """
        result = await self._make_request(
            "POST",
            "/analytics/riskScores",
            json_data={"entitytype": "user", "entityid": username},
        )

        if result.success and result.data:
            risk_data = result.data.get("riskScore", result.data)
            risk = SaviyntRiskScore(
                entity_type="user",
                entity_id=username,
                overall_score=risk_data.get("overallscore", 0),
                access_risk=risk_data.get("accessrisk", 0),
                behavior_risk=risk_data.get("behaviorrisk", 0),
                compliance_risk=risk_data.get("compliancerisk", 0),
                risk_level=SaviyntRiskLevel(risk_data.get("risklevel", "none").lower()),
                risk_factors=risk_data.get("riskfactors", []),
                last_calculated=risk_data.get("lastcalculated"),
            )
            result.data = risk.to_dict()

        return result

    @require_enterprise_mode
    async def get_high_risk_users(self, threshold: int = 70) -> ConnectorResult:
        """
        Get users with high risk scores.

        Args:
            threshold: Minimum risk score threshold

        Returns:
            ConnectorResult with list of high-risk users
        """
        return await self._make_request(
            "POST",
            "/analytics/highRiskUsers",
            json_data={"threshold": threshold},
        )

    # =========================================================================
    # HITL Integration
    # =========================================================================

    @require_enterprise_mode
    async def validate_approver(
        self, username: str, action_type: str
    ) -> ConnectorResult:
        """
        Validate if a user can approve a specific action type.

        Used by HITL workflow to verify approver permissions via Saviynt IGA.

        Args:
            username: Approver username
            action_type: Type of action requiring approval

        Returns:
            ConnectorResult with validation status and entitlements
        """
        # Get user entitlements
        ent_result = await self.get_user_entitlements(username)
        if not ent_result.success:
            return ent_result

        # Get user risk score
        risk_result = await self.get_user_risk_score(username)

        entitlements = ent_result.data.get("entitlements", [])
        risk_score = (
            risk_result.data.get("overall_score", 0) if risk_result.success else 0
        )

        # Check for approval entitlements
        approval_ents = [
            e
            for e in entitlements
            if "approve" in e.get("entitlement_name", "").lower()
            or "admin" in e.get("entitlement_name", "").lower()
        ]

        return ConnectorResult(
            success=True,
            data={
                "can_approve": len(approval_ents) > 0,
                "approval_entitlements": approval_ents,
                "user_risk_score": risk_score,
                "action_type": action_type,
            },
        )
