"""
Project Aura - AuditBoard Connector

Implements ADR-053: Enterprise Security Integrations

AuditBoard REST API connector for:
- Controls - compliance control management
- Risks - enterprise risk registry
- Findings - audit findings and issues
- Evidence - audit evidence collection
- Frameworks - compliance framework mapping
- Workflows - audit workflow management

SECURITY: Only available in ENTERPRISE or HYBRID mode.

Usage:
    >>> from src.services.auditboard_connector import AuditBoardConnector
    >>> auditboard = AuditBoardConnector(
    ...     base_url="${AUDITBOARD_BASE_URL}",
    ...     api_key="${AUDITBOARD_API_KEY}",
    ...     api_secret="${AUDITBOARD_API_SECRET}"
    ... )
    >>> controls = await auditboard.get_controls(framework="SOC2")
"""

import asyncio
import hashlib
import hmac
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


class AuditBoardControlStatus(Enum):
    """AuditBoard control status values."""

    EFFECTIVE = "Effective"
    INEFFECTIVE = "Ineffective"
    NOT_TESTED = "Not Tested"
    NOT_APPLICABLE = "Not Applicable"
    IN_PROGRESS = "In Progress"


class AuditBoardRiskLevel(Enum):
    """AuditBoard risk levels."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    MINIMAL = "Minimal"


class AuditBoardFindingStatus(Enum):
    """AuditBoard finding status values."""

    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    REMEDIATED = "Remediated"
    ACCEPTED = "Accepted"
    CLOSED = "Closed"


class AuditBoardFindingSeverity(Enum):
    """AuditBoard finding severity levels."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFORMATIONAL = "Informational"


class AuditBoardEvidenceType(Enum):
    """AuditBoard evidence types."""

    DOCUMENT = "Document"
    SCREENSHOT = "Screenshot"
    REPORT = "Report"
    LOG = "Log"
    CONFIGURATION = "Configuration"
    INTERVIEW = "Interview"
    OBSERVATION = "Observation"


class AuditBoardFramework(Enum):
    """Common compliance frameworks."""

    SOC1 = "SOC 1"
    SOC2 = "SOC 2"
    ISO27001 = "ISO 27001"
    NIST_CSF = "NIST CSF"
    NIST_800_53 = "NIST 800-53"
    PCI_DSS = "PCI DSS"
    HIPAA = "HIPAA"
    GDPR = "GDPR"
    CMMC = "CMMC"
    FEDRAMP = "FedRAMP"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class AuditBoardControl:
    """AuditBoard control."""

    control_id: str
    control_name: str
    description: str = ""
    status: AuditBoardControlStatus = AuditBoardControlStatus.NOT_TESTED
    framework: str | None = None
    control_number: str | None = None
    owner: str | None = None
    last_test_date: str | None = None
    next_test_date: str | None = None
    testing_frequency: str | None = None
    evidence_count: int = 0
    findings_count: int = 0
    automation_status: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "control_id": self.control_id,
            "control_name": self.control_name,
            "description": self.description,
            "status": self.status.value,
            "framework": self.framework,
            "control_number": self.control_number,
            "owner": self.owner,
            "last_test_date": self.last_test_date,
            "next_test_date": self.next_test_date,
            "testing_frequency": self.testing_frequency,
            "evidence_count": self.evidence_count,
            "findings_count": self.findings_count,
            "automation_status": self.automation_status,
            "attributes": self.attributes,
        }


@dataclass
class AuditBoardRisk:
    """AuditBoard risk."""

    risk_id: str
    risk_name: str
    description: str = ""
    risk_level: AuditBoardRiskLevel = AuditBoardRiskLevel.MEDIUM
    category: str | None = None
    owner: str | None = None
    likelihood: int = 0  # 1-5
    impact: int = 0  # 1-5
    inherent_risk_score: int = 0
    residual_risk_score: int = 0
    controls: list[str] = field(default_factory=list)
    mitigations: list[str] = field(default_factory=list)
    last_assessment_date: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "risk_id": self.risk_id,
            "risk_name": self.risk_name,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "category": self.category,
            "owner": self.owner,
            "likelihood": self.likelihood,
            "impact": self.impact,
            "inherent_risk_score": self.inherent_risk_score,
            "residual_risk_score": self.residual_risk_score,
            "controls": self.controls,
            "mitigations": self.mitigations,
            "last_assessment_date": self.last_assessment_date,
            "attributes": self.attributes,
        }


@dataclass
class AuditBoardFinding:
    """AuditBoard finding/issue."""

    finding_id: str
    title: str
    description: str = ""
    status: AuditBoardFindingStatus = AuditBoardFindingStatus.OPEN
    severity: AuditBoardFindingSeverity = AuditBoardFindingSeverity.MEDIUM
    source: str | None = None
    control_id: str | None = None
    owner: str | None = None
    due_date: str | None = None
    identified_date: str | None = None
    remediation_date: str | None = None
    remediation_plan: str | None = None
    root_cause: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "severity": self.severity.value,
            "source": self.source,
            "control_id": self.control_id,
            "owner": self.owner,
            "due_date": self.due_date,
            "identified_date": self.identified_date,
            "remediation_date": self.remediation_date,
            "remediation_plan": self.remediation_plan,
            "root_cause": self.root_cause,
            "evidence_ids": self.evidence_ids,
            "attributes": self.attributes,
        }


@dataclass
class AuditBoardEvidence:
    """AuditBoard evidence."""

    evidence_id: str
    name: str
    evidence_type: AuditBoardEvidenceType
    description: str = ""
    control_id: str | None = None
    uploaded_by: str | None = None
    uploaded_date: str | None = None
    file_url: str | None = None
    file_size: int = 0
    status: str = "Active"
    period_start: str | None = None
    period_end: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "evidence_id": self.evidence_id,
            "name": self.name,
            "evidence_type": self.evidence_type.value,
            "description": self.description,
            "control_id": self.control_id,
            "uploaded_by": self.uploaded_by,
            "uploaded_date": self.uploaded_date,
            "file_url": self.file_url,
            "file_size": self.file_size,
            "status": self.status,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "attributes": self.attributes,
        }


@dataclass
class AuditBoardComplianceStatus:
    """AuditBoard compliance status summary."""

    framework: str
    total_controls: int
    effective_controls: int
    ineffective_controls: int
    not_tested_controls: int
    compliance_percentage: float
    open_findings: int
    overdue_findings: int
    last_assessment_date: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "framework": self.framework,
            "total_controls": self.total_controls,
            "effective_controls": self.effective_controls,
            "ineffective_controls": self.ineffective_controls,
            "not_tested_controls": self.not_tested_controls,
            "compliance_percentage": self.compliance_percentage,
            "open_findings": self.open_findings,
            "overdue_findings": self.overdue_findings,
            "last_assessment_date": self.last_assessment_date,
        }


# =============================================================================
# AuditBoard Connector
# =============================================================================


class AuditBoardConnector(ExternalToolConnector):
    """
    AuditBoard GRC connector.

    Provides integration with AuditBoard for:
    - Control management and testing
    - Risk registry management
    - Findings/issues tracking
    - Evidence collection
    - Compliance framework mapping

    Authentication: API key + secret with HMAC signature
    Rate Limits: 60 requests/minute
    """

    RATE_LIMIT_REQUESTS_PER_MINUTE = 60
    API_VERSION = "v1"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_secret: str,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        govcloud: bool = False,
    ):
        """
        Initialize AuditBoard connector.

        Args:
            base_url: AuditBoard URL (e.g., https://company.auditboardapp.com)
            api_key: API key
            api_secret: API secret for HMAC signing
            timeout_seconds: Request timeout
            max_retries: Maximum retry attempts
            govcloud: Use GovCloud-compatible deployment
        """
        super().__init__(name="auditboard", timeout_seconds=timeout_seconds)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.govcloud = govcloud
        self.timeout_seconds = timeout_seconds
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.max_retries = max_retries

        # Session state
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
        return f"{self.base_url}/api/{self.API_VERSION}"

    # =========================================================================
    # Connection Management
    # =========================================================================

    @require_enterprise_mode
    async def connect(self) -> bool:
        """Establish connection and validate credentials."""
        result = await self.health_check()
        return result.success

    async def disconnect(self) -> None:
        """Disconnect (no-op for stateless API)."""
        self._status = ConnectorStatus.DISCONNECTED

    async def health_check(self) -> ConnectorResult:
        """Check connector health."""
        start_time = time.time()

        try:
            result = await self._make_request("GET", "/health")
            if result.success:
                self._status = ConnectorStatus.CONNECTED
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
            "total_requests": self._total_requests,
            "failed_requests": self._failed_requests,
            "average_latency_ms": avg_latency,
            "last_error": self._last_error,
        }

    # =========================================================================
    # Authentication
    # =========================================================================

    def _generate_signature(self, timestamp: str, method: str, path: str) -> str:
        """
        Generate HMAC signature for request authentication.

        Args:
            timestamp: Unix timestamp string
            method: HTTP method
            path: Request path

        Returns:
            HMAC-SHA256 signature
        """
        message = f"{timestamp}{method}{path}"
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _get_headers(self, method: str, path: str) -> dict[str, str]:
        """Get request headers with authentication."""
        timestamp = str(int(time.time()))
        signature = self._generate_signature(timestamp, method, path)

        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": self.api_key,
            "X-Timestamp": timestamp,
            "X-Signature": signature,
        }

    # =========================================================================
    # Rate Limiting
    # =========================================================================

    async def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting."""
        now = time.time()

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
        await self._check_rate_limit()

        url = f"{self.api_base_url}{endpoint}"
        path = f"/api/{self.API_VERSION}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.request(
                        method,
                        url,
                        params=params,
                        json=json_data,
                        headers=self._get_headers(method, path),
                    ) as response:
                        latency_ms = (time.time() - start_time) * 1000
                        self._record_request(latency_ms, response.status < 400)

                        if response.status == 429:
                            retry_after = int(response.headers.get("Retry-After", 60))
                            self._status = ConnectorStatus.RATE_LIMITED
                            await asyncio.sleep(retry_after)
                            continue

                        if response.status == 401:
                            self._status = ConnectorStatus.AUTH_FAILED
                            self._last_error = "Authentication failed"
                            return ConnectorResult(
                                success=False,
                                error="Authentication failed",
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
    # Controls API
    # =========================================================================

    @require_enterprise_mode
    async def get_control(self, control_id: str) -> ConnectorResult:
        """
        Get control by ID.

        Args:
            control_id: Control ID

        Returns:
            ConnectorResult with AuditBoardControl data
        """
        result = await self._make_request("GET", f"/controls/{control_id}")

        if result.success and result.data:
            ctrl_data = result.data.get("control", result.data)
            control = AuditBoardControl(
                control_id=str(ctrl_data.get("id", control_id)),
                control_name=ctrl_data.get("name", ""),
                description=ctrl_data.get("description", ""),
                status=AuditBoardControlStatus(ctrl_data.get("status", "Not Tested")),
                framework=ctrl_data.get("framework"),
                control_number=ctrl_data.get("controlNumber"),
                owner=ctrl_data.get("owner"),
                last_test_date=ctrl_data.get("lastTestDate"),
                next_test_date=ctrl_data.get("nextTestDate"),
                testing_frequency=ctrl_data.get("testingFrequency"),
                evidence_count=ctrl_data.get("evidenceCount", 0),
                findings_count=ctrl_data.get("findingsCount", 0),
            )
            result.data = control.to_dict()

        return result

    @require_enterprise_mode
    async def get_controls(
        self,
        framework: str | None = None,
        status: AuditBoardControlStatus | None = None,
        owner: str | None = None,
        limit: int = 100,
    ) -> ConnectorResult:
        """
        Get controls with optional filters.

        Args:
            framework: Filter by framework
            status: Filter by status
            owner: Filter by owner
            limit: Maximum results

        Returns:
            ConnectorResult with list of controls
        """
        params: dict[str, Any] = {"limit": limit}
        if framework:
            params["framework"] = framework
        if status:
            params["status"] = status.value
        if owner:
            params["owner"] = owner

        result = await self._make_request("GET", "/controls", params=params)

        if result.success and result.data:
            controls = []
            for ctrl_data in result.data.get("controls", []):
                control = AuditBoardControl(
                    control_id=str(ctrl_data.get("id", "")),
                    control_name=ctrl_data.get("name", ""),
                    description=ctrl_data.get("description", ""),
                    status=AuditBoardControlStatus(
                        ctrl_data.get("status", "Not Tested")
                    ),
                    framework=ctrl_data.get("framework"),
                    control_number=ctrl_data.get("controlNumber"),
                    owner=ctrl_data.get("owner"),
                    evidence_count=ctrl_data.get("evidenceCount", 0),
                    findings_count=ctrl_data.get("findingsCount", 0),
                )
                controls.append(control.to_dict())
            result.data = {"controls": controls, "total": len(controls)}

        return result

    @require_enterprise_mode
    async def update_control_status(
        self,
        control_id: str,
        status: AuditBoardControlStatus,
        notes: str = "",
    ) -> ConnectorResult:
        """
        Update control status.

        Args:
            control_id: Control ID
            status: New status
            notes: Status change notes

        Returns:
            ConnectorResult with update status
        """
        return await self._make_request(
            "PATCH",
            f"/controls/{control_id}",
            json_data={"status": status.value, "notes": notes},
        )

    # =========================================================================
    # Risks API
    # =========================================================================

    @require_enterprise_mode
    async def get_risk(self, risk_id: str) -> ConnectorResult:
        """
        Get risk by ID.

        Args:
            risk_id: Risk ID

        Returns:
            ConnectorResult with AuditBoardRisk data
        """
        result = await self._make_request("GET", f"/risks/{risk_id}")

        if result.success and result.data:
            risk_data = result.data.get("risk", result.data)
            risk = AuditBoardRisk(
                risk_id=str(risk_data.get("id", risk_id)),
                risk_name=risk_data.get("name", ""),
                description=risk_data.get("description", ""),
                risk_level=AuditBoardRiskLevel(risk_data.get("riskLevel", "Medium")),
                category=risk_data.get("category"),
                owner=risk_data.get("owner"),
                likelihood=risk_data.get("likelihood", 0),
                impact=risk_data.get("impact", 0),
                inherent_risk_score=risk_data.get("inherentRiskScore", 0),
                residual_risk_score=risk_data.get("residualRiskScore", 0),
                controls=risk_data.get("controls", []),
                mitigations=risk_data.get("mitigations", []),
                last_assessment_date=risk_data.get("lastAssessmentDate"),
            )
            result.data = risk.to_dict()

        return result

    @require_enterprise_mode
    async def get_risks(
        self,
        risk_level: AuditBoardRiskLevel | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> ConnectorResult:
        """
        Get risks with optional filters.

        Args:
            risk_level: Filter by risk level
            category: Filter by category
            limit: Maximum results

        Returns:
            ConnectorResult with list of risks
        """
        params: dict[str, Any] = {"limit": limit}
        if risk_level:
            params["riskLevel"] = risk_level.value
        if category:
            params["category"] = category

        result = await self._make_request("GET", "/risks", params=params)

        if result.success and result.data:
            risks = []
            for risk_data in result.data.get("risks", []):
                risk = AuditBoardRisk(
                    risk_id=str(risk_data.get("id", "")),
                    risk_name=risk_data.get("name", ""),
                    risk_level=AuditBoardRiskLevel(
                        risk_data.get("riskLevel", "Medium")
                    ),
                    category=risk_data.get("category"),
                    owner=risk_data.get("owner"),
                    residual_risk_score=risk_data.get("residualRiskScore", 0),
                )
                risks.append(risk.to_dict())
            result.data = {"risks": risks, "total": len(risks)}

        return result

    # =========================================================================
    # Findings API
    # =========================================================================

    @require_enterprise_mode
    async def get_finding(self, finding_id: str) -> ConnectorResult:
        """
        Get finding by ID.

        Args:
            finding_id: Finding ID

        Returns:
            ConnectorResult with AuditBoardFinding data
        """
        result = await self._make_request("GET", f"/findings/{finding_id}")

        if result.success and result.data:
            find_data = result.data.get("finding", result.data)
            finding = AuditBoardFinding(
                finding_id=str(find_data.get("id", finding_id)),
                title=find_data.get("title", ""),
                description=find_data.get("description", ""),
                status=AuditBoardFindingStatus(find_data.get("status", "Open")),
                severity=AuditBoardFindingSeverity(find_data.get("severity", "Medium")),
                source=find_data.get("source"),
                control_id=find_data.get("controlId"),
                owner=find_data.get("owner"),
                due_date=find_data.get("dueDate"),
                identified_date=find_data.get("identifiedDate"),
                remediation_plan=find_data.get("remediationPlan"),
                root_cause=find_data.get("rootCause"),
                evidence_ids=find_data.get("evidenceIds", []),
            )
            result.data = finding.to_dict()

        return result

    @require_enterprise_mode
    async def get_findings(
        self,
        status: AuditBoardFindingStatus | None = None,
        severity: AuditBoardFindingSeverity | None = None,
        control_id: str | None = None,
        limit: int = 100,
    ) -> ConnectorResult:
        """
        Get findings with optional filters.

        Args:
            status: Filter by status
            severity: Filter by severity
            control_id: Filter by control
            limit: Maximum results

        Returns:
            ConnectorResult with list of findings
        """
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status.value
        if severity:
            params["severity"] = severity.value
        if control_id:
            params["controlId"] = control_id

        result = await self._make_request("GET", "/findings", params=params)

        if result.success and result.data:
            findings = []
            for find_data in result.data.get("findings", []):
                finding = AuditBoardFinding(
                    finding_id=str(find_data.get("id", "")),
                    title=find_data.get("title", ""),
                    status=AuditBoardFindingStatus(find_data.get("status", "Open")),
                    severity=AuditBoardFindingSeverity(
                        find_data.get("severity", "Medium")
                    ),
                    control_id=find_data.get("controlId"),
                    owner=find_data.get("owner"),
                    due_date=find_data.get("dueDate"),
                )
                findings.append(finding.to_dict())
            result.data = {"findings": findings, "total": len(findings)}

        return result

    @require_enterprise_mode
    async def create_finding(
        self,
        title: str,
        description: str,
        severity: AuditBoardFindingSeverity,
        control_id: str | None = None,
        source: str = "Project Aura",
        due_date: str | None = None,
    ) -> ConnectorResult:
        """
        Create a new finding.

        Args:
            title: Finding title
            description: Finding description
            severity: Finding severity
            control_id: Related control ID
            source: Finding source
            due_date: Remediation due date

        Returns:
            ConnectorResult with created finding
        """
        payload = {
            "title": title,
            "description": description,
            "severity": severity.value,
            "source": source,
            "status": AuditBoardFindingStatus.OPEN.value,
            "identifiedDate": datetime.now(timezone.utc).isoformat(),
        }
        if control_id:
            payload["controlId"] = control_id
        if due_date:
            payload["dueDate"] = due_date

        return await self._make_request("POST", "/findings", json_data=payload)

    @require_enterprise_mode
    async def update_finding_status(
        self,
        finding_id: str,
        status: AuditBoardFindingStatus,
        notes: str = "",
    ) -> ConnectorResult:
        """
        Update finding status.

        Args:
            finding_id: Finding ID
            status: New status
            notes: Status change notes

        Returns:
            ConnectorResult with update status
        """
        payload = {"status": status.value}
        if notes:
            payload["notes"] = notes
        if status == AuditBoardFindingStatus.REMEDIATED:
            payload["remediationDate"] = datetime.now(timezone.utc).isoformat()

        return await self._make_request(
            "PATCH",
            f"/findings/{finding_id}",
            json_data=payload,
        )

    # =========================================================================
    # Evidence API
    # =========================================================================

    @require_enterprise_mode
    async def get_evidence(self, evidence_id: str) -> ConnectorResult:
        """
        Get evidence by ID.

        Args:
            evidence_id: Evidence ID

        Returns:
            ConnectorResult with AuditBoardEvidence data
        """
        result = await self._make_request("GET", f"/evidence/{evidence_id}")

        if result.success and result.data:
            ev_data = result.data.get("evidence", result.data)
            evidence = AuditBoardEvidence(
                evidence_id=str(ev_data.get("id", evidence_id)),
                name=ev_data.get("name", ""),
                evidence_type=AuditBoardEvidenceType(ev_data.get("type", "Document")),
                description=ev_data.get("description", ""),
                control_id=ev_data.get("controlId"),
                uploaded_by=ev_data.get("uploadedBy"),
                uploaded_date=ev_data.get("uploadedDate"),
                file_url=ev_data.get("fileUrl"),
                file_size=ev_data.get("fileSize", 0),
                period_start=ev_data.get("periodStart"),
                period_end=ev_data.get("periodEnd"),
            )
            result.data = evidence.to_dict()

        return result

    @require_enterprise_mode
    async def get_control_evidence(
        self, control_id: str, limit: int = 100
    ) -> ConnectorResult:
        """
        Get evidence for a control.

        Args:
            control_id: Control ID
            limit: Maximum results

        Returns:
            ConnectorResult with list of evidence
        """
        result = await self._make_request(
            "GET",
            "/evidence",
            params={"controlId": control_id, "limit": limit},
        )

        if result.success and result.data:
            evidence_list = []
            for ev_data in result.data.get("evidence", []):
                evidence = AuditBoardEvidence(
                    evidence_id=str(ev_data.get("id", "")),
                    name=ev_data.get("name", ""),
                    evidence_type=AuditBoardEvidenceType(
                        ev_data.get("type", "Document")
                    ),
                    control_id=control_id,
                    uploaded_date=ev_data.get("uploadedDate"),
                )
                evidence_list.append(evidence.to_dict())
            result.data = {"evidence": evidence_list, "total": len(evidence_list)}

        return result

    @require_enterprise_mode
    async def upload_evidence(
        self,
        control_id: str,
        name: str,
        evidence_type: AuditBoardEvidenceType,
        description: str = "",
        content: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> ConnectorResult:
        """
        Upload evidence for a control.

        Args:
            control_id: Control ID
            name: Evidence name
            evidence_type: Evidence type
            description: Evidence description
            content: Evidence content (for text-based evidence)
            period_start: Evidence period start
            period_end: Evidence period end

        Returns:
            ConnectorResult with created evidence
        """
        payload = {
            "controlId": control_id,
            "name": name,
            "type": evidence_type.value,
            "description": description,
            "uploadedDate": datetime.now(timezone.utc).isoformat(),
        }
        if content:
            payload["content"] = content
        if period_start:
            payload["periodStart"] = period_start
        if period_end:
            payload["periodEnd"] = period_end

        return await self._make_request("POST", "/evidence", json_data=payload)

    # =========================================================================
    # Compliance Status API
    # =========================================================================

    @require_enterprise_mode
    async def get_compliance_status(self, framework: str) -> ConnectorResult:
        """
        Get compliance status for a framework.

        Args:
            framework: Framework name (e.g., SOC2, ISO27001)

        Returns:
            ConnectorResult with AuditBoardComplianceStatus data
        """
        result = await self._make_request(
            "GET",
            "/compliance/status",
            params={"framework": framework},
        )

        if result.success and result.data:
            status_data = result.data.get("status", result.data)
            status = AuditBoardComplianceStatus(
                framework=framework,
                total_controls=status_data.get("totalControls", 0),
                effective_controls=status_data.get("effectiveControls", 0),
                ineffective_controls=status_data.get("ineffectiveControls", 0),
                not_tested_controls=status_data.get("notTestedControls", 0),
                compliance_percentage=status_data.get("compliancePercentage", 0.0),
                open_findings=status_data.get("openFindings", 0),
                overdue_findings=status_data.get("overdueFindings", 0),
                last_assessment_date=status_data.get("lastAssessmentDate"),
            )
            result.data = status.to_dict()

        return result

    # =========================================================================
    # Aura Integration
    # =========================================================================

    @require_enterprise_mode
    async def sync_vulnerability_to_finding(
        self,
        vulnerability_id: str,
        title: str,
        description: str,
        severity: str,
        control_id: str | None = None,
    ) -> ConnectorResult:
        """
        Sync an Aura vulnerability as an AuditBoard finding.

        Used for bidirectional compliance sync.

        Args:
            vulnerability_id: Aura vulnerability ID
            title: Vulnerability title
            description: Vulnerability description
            severity: Severity (critical, high, medium, low)
            control_id: Related control ID

        Returns:
            ConnectorResult with created/updated finding
        """
        severity_map = {
            "critical": AuditBoardFindingSeverity.CRITICAL,
            "high": AuditBoardFindingSeverity.HIGH,
            "medium": AuditBoardFindingSeverity.MEDIUM,
            "low": AuditBoardFindingSeverity.LOW,
        }
        ab_severity = severity_map.get(
            severity.lower(), AuditBoardFindingSeverity.MEDIUM
        )

        # Check if finding already exists
        existing = await self._make_request(
            "GET",
            "/findings",
            params={"externalId": vulnerability_id, "source": "Project Aura"},
        )

        if existing.success and existing.data.get("findings"):
            # Update existing finding
            finding_id = existing.data["findings"][0]["id"]
            return await self._make_request(
                "PATCH",
                f"/findings/{finding_id}",
                json_data={
                    "title": title,
                    "description": description,
                    "severity": ab_severity.value,
                },
            )
        else:
            # Create new finding
            return await self.create_finding(
                title=f"[Aura-{vulnerability_id}] {title}",
                description=description,
                severity=ab_severity,
                control_id=control_id,
                source="Project Aura",
            )

    @require_enterprise_mode
    async def export_hitl_approval_as_evidence(
        self,
        control_id: str,
        approval_id: str,
        approver: str,
        action: str,
        timestamp: str,
        details: str,
    ) -> ConnectorResult:
        """
        Export HITL approval as audit evidence.

        Args:
            control_id: Related control ID
            approval_id: HITL approval ID
            approver: Approver username
            action: Action that was approved
            timestamp: Approval timestamp
            details: Approval details

        Returns:
            ConnectorResult with created evidence
        """
        content = f"""HITL Approval Evidence
====================
Approval ID: {approval_id}
Approver: {approver}
Action: {action}
Timestamp: {timestamp}

Details:
{details}

This approval was recorded by Project Aura's Human-in-the-Loop workflow.
"""

        return await self.upload_evidence(
            control_id=control_id,
            name=f"HITL Approval - {approval_id}",
            evidence_type=AuditBoardEvidenceType.LOG,
            description=f"Automated export of HITL approval {approval_id}",
            content=content,
            period_start=timestamp,
            period_end=timestamp,
        )
