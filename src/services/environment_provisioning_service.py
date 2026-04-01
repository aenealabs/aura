"""
Project Aura - Environment Provisioning Service

Provides self-service test environment provisioning and lifecycle management.
Integrates with AutonomyPolicyService for HITL approval decisions.

Author: Project Aura Team
Created: 2025-12-14
Version: 1.0.0
"""

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, cast

logger = logging.getLogger(__name__)

# Boto3 imports (available in AWS environment)
try:
    import boto3
    from boto3.dynamodb.conditions import Key

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("Boto3 not available - using mock mode")


# ============================================================================
# Enums
# ============================================================================


class EnvironmentType(Enum):
    """Types of test environments available for provisioning."""

    QUICK = "quick"  # EKS Namespace, 4h TTL, auto-approved
    STANDARD = "standard"  # Service Catalog, 24h TTL, auto-approved
    EXTENDED = "extended"  # Service Catalog, 7d TTL, HITL required
    COMPLIANCE = "compliance"  # Dedicated VPC, 24h TTL, HITL required


class EnvironmentStatus(Enum):
    """Lifecycle status of a test environment."""

    PENDING_APPROVAL = "pending_approval"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    EXPIRING = "expiring"
    TERMINATING = "terminating"
    TERMINATED = "terminated"
    FAILED = "failed"


class PersistenceMode(Enum):
    """Operating modes for persistence service."""

    MOCK = "mock"  # In-memory storage for testing
    AWS = "aws"  # Real DynamoDB


# ============================================================================
# Exceptions
# ============================================================================


class EnvironmentProvisioningError(Exception):
    """General environment provisioning error."""


class QuotaExceededError(EnvironmentProvisioningError):
    """Raised when user quota is exceeded."""


class TemplateNotFoundError(EnvironmentProvisioningError):
    """Raised when requested template doesn't exist."""


class EnvironmentNotFoundError(EnvironmentProvisioningError):
    """Raised when environment doesn't exist."""


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class EnvironmentTemplate:
    """Definition of an environment template available for provisioning."""

    template_id: str
    name: str
    description: str
    environment_type: EnvironmentType
    default_ttl_hours: int
    max_ttl_hours: int
    cost_per_day: float
    resources: list[str]  # e.g., ["ECS Task", "DynamoDB Table", "S3 Bucket"]
    requires_approval: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "environment_type": self.environment_type.value,
            "default_ttl_hours": self.default_ttl_hours,
            "max_ttl_hours": self.max_ttl_hours,
            "cost_per_day": self.cost_per_day,
            "resources": self.resources,
            "requires_approval": self.requires_approval,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnvironmentTemplate":
        """Create from dictionary."""
        return cls(
            template_id=data["template_id"],
            name=data["name"],
            description=data["description"],
            environment_type=EnvironmentType(data["environment_type"]),
            default_ttl_hours=data["default_ttl_hours"],
            max_ttl_hours=data["max_ttl_hours"],
            cost_per_day=data["cost_per_day"],
            resources=data.get("resources", []),
            requires_approval=data.get("requires_approval", False),
        )


@dataclass
class TestEnvironment:
    """Represents a provisioned test environment."""

    environment_id: str
    user_id: str
    organization_id: str
    environment_type: EnvironmentType
    template_id: str
    display_name: str
    status: EnvironmentStatus
    created_at: str  # ISO 8601
    expires_at: str  # ISO 8601
    dns_name: str
    approval_id: str | None = None
    resources: dict[str, Any] = field(default_factory=dict)
    cost_estimate_daily: float = 0.0
    last_activity_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for DynamoDB storage."""
        return {
            "environment_id": self.environment_id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "environment_type": self.environment_type.value,
            "template_id": self.template_id,
            "display_name": self.display_name,
            "status": self.status.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "dns_name": self.dns_name,
            "approval_id": self.approval_id,
            "resources": self.resources,
            "cost_estimate_daily": self.cost_estimate_daily,
            "last_activity_at": self.last_activity_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestEnvironment":
        """Create from DynamoDB item."""
        return cls(
            environment_id=data["environment_id"],
            user_id=data["user_id"],
            organization_id=data["organization_id"],
            environment_type=EnvironmentType(data["environment_type"]),
            template_id=data["template_id"],
            display_name=data["display_name"],
            status=EnvironmentStatus(data["status"]),
            created_at=data["created_at"],
            expires_at=data["expires_at"],
            dns_name=data["dns_name"],
            approval_id=data.get("approval_id"),
            resources=data.get("resources", {}),
            cost_estimate_daily=float(data.get("cost_estimate_daily", 0.0)),
            last_activity_at=data.get("last_activity_at", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class EnvironmentConfig:
    """Configuration for creating a new environment."""

    template_id: str
    display_name: str
    description: str = ""
    ttl_hours: int | None = None  # None = use template default
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class UserQuota:
    """User's environment quota and usage."""

    user_id: str
    concurrent_limit: int = 3
    active_count: int = 0
    monthly_budget: float = 500.0
    monthly_spent: float = 0.0

    @property
    def available(self) -> int:
        """Number of environments user can still create."""
        return max(0, self.concurrent_limit - self.active_count)

    @property
    def monthly_remaining(self) -> float:
        """Remaining monthly budget."""
        return max(0.0, self.monthly_budget - self.monthly_spent)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "concurrent_limit": self.concurrent_limit,
            "active_count": self.active_count,
            "available": self.available,
            "monthly_budget": self.monthly_budget,
            "monthly_spent": self.monthly_spent,
            "monthly_remaining": self.monthly_remaining,
        }


# ============================================================================
# Default Templates
# ============================================================================

DEFAULT_TEMPLATES: list[EnvironmentTemplate] = [
    EnvironmentTemplate(
        template_id="quick-test",
        name="Quick Test Namespace",
        description="Ephemeral EKS namespace for rapid testing (4 hours)",
        environment_type=EnvironmentType.QUICK,
        default_ttl_hours=4,
        max_ttl_hours=8,
        cost_per_day=0.10,
        resources=["EKS Namespace", "ResourceQuota"],
        requires_approval=False,
    ),
    EnvironmentTemplate(
        template_id="python-fastapi",
        name="Python FastAPI",
        description="FastAPI backend with DynamoDB table (24 hours)",
        environment_type=EnvironmentType.STANDARD,
        default_ttl_hours=24,
        max_ttl_hours=72,
        cost_per_day=0.50,
        resources=["ECS Task (1 vCPU, 2GB)", "DynamoDB Table", "S3 Bucket"],
        requires_approval=False,
    ),
    EnvironmentTemplate(
        template_id="react-frontend",
        name="React Frontend",
        description="React app with CloudFront distribution (24 hours)",
        environment_type=EnvironmentType.STANDARD,
        default_ttl_hours=24,
        max_ttl_hours=72,
        cost_per_day=0.30,
        resources=["ECS Task (0.5 vCPU, 1GB)", "CloudFront Distribution", "S3 Bucket"],
        requires_approval=False,
    ),
    EnvironmentTemplate(
        template_id="full-stack",
        name="Full Stack (API + UI)",
        description="Complete stack with API, frontend, and data layer (24 hours)",
        environment_type=EnvironmentType.STANDARD,
        default_ttl_hours=24,
        max_ttl_hours=72,
        cost_per_day=1.20,
        resources=[
            "ECS Task - API (1 vCPU, 2GB)",
            "ECS Task - UI (0.5 vCPU, 1GB)",
            "DynamoDB Table",
            "S3 Bucket",
        ],
        requires_approval=False,
    ),
    EnvironmentTemplate(
        template_id="data-pipeline",
        name="Data Pipeline",
        description="Step Functions workflow with Lambda and storage (7 days)",
        environment_type=EnvironmentType.EXTENDED,
        default_ttl_hours=168,  # 7 days
        max_ttl_hours=336,  # 14 days
        cost_per_day=0.80,
        resources=["Step Functions", "Lambda Functions", "S3 Bucket", "DynamoDB Table"],
        requires_approval=True,
    ),
]


# ============================================================================
# Service Class
# ============================================================================


class EnvironmentProvisioningService:
    """
    Service for provisioning and managing self-service test environments.

    Features:
    - Create, list, and terminate test environments
    - Quota enforcement (concurrent limit, monthly budget)
    - Integration with AutonomyPolicyService for HITL decisions
    - TTL-based automatic cleanup
    - Support for both mock (testing) and AWS modes

    Usage:
        >>> service = EnvironmentProvisioningService(mode=PersistenceMode.MOCK)
        >>> config = EnvironmentConfig(template_id="python-fastapi", display_name="My Test")
        >>> env = await service.create_environment("user-123", "org-456", config)
        >>> envs = await service.list_environments(user_id="user-123")
    """

    # Configuration
    DEFAULT_CONCURRENT_LIMIT = 3
    DEFAULT_MONTHLY_BUDGET = 500.0
    TTL_BUFFER_HOURS = 24  # Extra time after expires_at before DynamoDB TTL deletes

    # Severity mapping for AutonomyPolicyService
    SEVERITY_MAP: dict[EnvironmentType, str] = {
        EnvironmentType.QUICK: "LOW",
        EnvironmentType.STANDARD: "MEDIUM",
        EnvironmentType.EXTENDED: "HIGH",
        EnvironmentType.COMPLIANCE: "CRITICAL",
    }

    def __init__(
        self,
        mode: PersistenceMode = PersistenceMode.MOCK,
        table_name: str | None = None,
        region: str | None = None,
        autonomy_service: Any | None = None,  # AutonomyPolicyService
    ):
        """
        Initialize Environment Provisioning Service.

        Args:
            mode: Operating mode (MOCK or AWS)
            table_name: DynamoDB table name (default: aura-test-env-state-{env})
            region: AWS region (default: us-east-1)
            autonomy_service: AutonomyPolicyService instance for HITL decisions
        """
        self.mode = mode
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.autonomy_service = autonomy_service

        # Determine table name
        env = os.environ.get("ENVIRONMENT", "dev")
        project = os.environ.get("PROJECT_NAME", "aura")
        self.table_name = table_name or f"{project}-test-env-state-{env}"

        # In-memory stores for mock mode
        self.mock_store: dict[str, dict[str, Any]] = {}
        self.mock_quota_store: dict[str, UserQuota] = {}

        # Template registry
        self.templates: dict[str, EnvironmentTemplate] = {
            t.template_id: t for t in DEFAULT_TEMPLATES
        }

        # Initialize DynamoDB client
        if self.mode == PersistenceMode.AWS and BOTO3_AVAILABLE:
            self._init_dynamodb_client()
        else:
            if self.mode == PersistenceMode.AWS:
                logger.warning(
                    "AWS mode requested but boto3 not available. Using MOCK mode."
                )
                self.mode = PersistenceMode.MOCK
            self._init_mock_mode()

        logger.info(
            f"EnvironmentProvisioningService initialized in {self.mode.value} mode "
            f"(table: {self.table_name})"
        )

    def _init_dynamodb_client(self) -> None:
        """Initialize DynamoDB client."""
        try:
            self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self.table = self.dynamodb.Table(self.table_name)

            # Verify table exists
            self.table.load()
            logger.info(f"Connected to DynamoDB table: {self.table_name}")

        except Exception as e:
            logger.error(f"Failed to connect to DynamoDB: {e}")
            logger.warning("Falling back to MOCK mode")
            self.mode = PersistenceMode.MOCK
            self._init_mock_mode()

    def _init_mock_mode(self) -> None:
        """Initialize mock mode."""
        logger.info("Mock mode initialized (in-memory storage)")

    # =========================================================================
    # Core Operations
    # =========================================================================

    async def create_environment(
        self,
        user_id: str,
        organization_id: str,
        config: EnvironmentConfig,
    ) -> TestEnvironment:
        """
        Create a new test environment.

        Args:
            user_id: ID of user creating the environment
            organization_id: Organization for billing/policy
            config: Environment configuration

        Returns:
            Created TestEnvironment

        Raises:
            TemplateNotFoundError: If template doesn't exist
            QuotaExceededError: If user quota is exceeded
        """
        # Validate template
        template = self.get_template(config.template_id)
        if not template:
            raise TemplateNotFoundError(f"Template not found: {config.template_id}")

        # Check quota
        quota = await self.get_user_quota(user_id)
        if quota.active_count >= quota.concurrent_limit:
            raise QuotaExceededError(
                f"Quota exceeded: {quota.active_count}/{quota.concurrent_limit} "
                "environments active"
            )

        # Determine TTL
        ttl_hours = config.ttl_hours or template.default_ttl_hours
        ttl_hours = min(ttl_hours, template.max_ttl_hours)

        # Generate IDs and timestamps
        environment_id = f"env-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        created_at = now.isoformat()
        expires_at = (
            now + __import__("datetime").timedelta(hours=ttl_hours)
        ).isoformat()

        # Calculate DynamoDB TTL (Unix timestamp)
        ttl_timestamp = int(time.time() + (ttl_hours + self.TTL_BUFFER_HOURS) * 3600)

        # Check if HITL approval is required
        requires_approval = self._check_requires_approval(
            organization_id, template.environment_type
        )

        # Determine initial status
        initial_status = (
            EnvironmentStatus.PENDING_APPROVAL
            if requires_approval
            else EnvironmentStatus.PROVISIONING
        )

        # Create environment record
        env = TestEnvironment(
            environment_id=environment_id,
            user_id=user_id,
            organization_id=organization_id,
            environment_type=template.environment_type,
            template_id=template.template_id,
            display_name=config.display_name,
            status=initial_status,
            created_at=created_at,
            expires_at=expires_at,
            dns_name=f"{environment_id}.test.aura.local",
            approval_id=None,
            resources={},
            cost_estimate_daily=template.cost_per_day,
            last_activity_at=created_at,
            metadata={
                **config.metadata,
                "description": config.description,
                "ttl_hours": ttl_hours,
            },
        )

        # Save to storage
        await self._save_environment(env, ttl_timestamp)

        logger.info(
            f"Created environment {environment_id} for user {user_id} "
            f"(type={template.environment_type.value}, status={initial_status.value})"
        )

        return env

    async def get_environment(self, environment_id: str) -> TestEnvironment | None:
        """
        Get environment by ID.

        Args:
            environment_id: Environment identifier

        Returns:
            TestEnvironment if found, None otherwise
        """
        if self.mode == PersistenceMode.MOCK:
            data = self.mock_store.get(environment_id)
            if data:
                return TestEnvironment.from_dict(data)
            return None

        try:
            response = self.table.get_item(Key={"environment_id": environment_id})
            item = response.get("Item")
            if item:
                return TestEnvironment.from_dict(item)
            return None
        except Exception as e:
            logger.error(f"Failed to get environment {environment_id}: {e}")
            return None

    async def list_environments(
        self,
        user_id: str | None = None,
        status: EnvironmentStatus | None = None,
        environment_type: EnvironmentType | None = None,
        limit: int = 100,
    ) -> list[TestEnvironment]:
        """
        List environments with optional filtering.

        Args:
            user_id: Filter by user (required for non-admin)
            status: Filter by status
            environment_type: Filter by type
            limit: Maximum results to return

        Returns:
            List of matching environments
        """
        if self.mode == PersistenceMode.MOCK:
            results = list(self.mock_store.values())

            # Apply filters
            if user_id:
                results = [r for r in results if r.get("user_id") == user_id]
            if status:
                results = [r for r in results if r.get("status") == status.value]
            if environment_type:
                results = [
                    r
                    for r in results
                    if r.get("environment_type") == environment_type.value
                ]

            # Sort by created_at descending
            results.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            return [TestEnvironment.from_dict(r) for r in results[:limit]]

        try:
            # Use appropriate GSI based on filter
            if user_id:
                response = self.table.query(
                    IndexName="user-created_at-index",
                    KeyConditionExpression=Key("user_id").eq(user_id),
                    ScanIndexForward=False,  # Newest first
                    Limit=limit,
                )
            elif status:
                response = self.table.query(
                    IndexName="status-created_at-index",
                    KeyConditionExpression=Key("status").eq(status.value),
                    ScanIndexForward=False,
                    Limit=limit,
                )
            elif environment_type:
                response = self.table.query(
                    IndexName="environment_type-created_at-index",
                    KeyConditionExpression=Key("environment_type").eq(
                        environment_type.value
                    ),
                    ScanIndexForward=False,
                    Limit=limit,
                )
            else:
                # Full scan (expensive, should be avoided)
                response = self.table.scan(Limit=limit)

            items = response.get("Items", [])
            return [TestEnvironment.from_dict(item) for item in items]

        except Exception as e:
            logger.error(f"Failed to list environments: {e}")
            return []

    async def terminate_environment(
        self,
        environment_id: str,
        terminated_by: str,
        reason: str = "",
    ) -> bool:
        """
        Terminate an environment.

        Args:
            environment_id: Environment to terminate
            terminated_by: User initiating termination
            reason: Optional reason for termination

        Returns:
            True if successful
        """
        env = await self.get_environment(environment_id)
        if not env:
            logger.warning(f"Environment not found for termination: {environment_id}")
            return False

        # Update status
        env.status = EnvironmentStatus.TERMINATING
        env.metadata["terminated_by"] = terminated_by
        env.metadata["termination_reason"] = reason
        env.metadata["terminated_at"] = datetime.now(timezone.utc).isoformat()

        await self._save_environment(env)

        logger.info(
            f"Environment {environment_id} termination initiated by {terminated_by}"
        )

        return True

    async def extend_ttl(
        self,
        environment_id: str,
        additional_hours: int,
        extended_by: str,
    ) -> TestEnvironment | None:
        """
        Extend environment TTL.

        Args:
            environment_id: Environment to extend
            additional_hours: Hours to add
            extended_by: User requesting extension

        Returns:
            Updated environment or None if failed

        Note:
            May require HITL approval if extending beyond threshold
        """
        env = await self.get_environment(environment_id)
        if not env:
            logger.warning(f"Environment not found for TTL extension: {environment_id}")
            return None

        # Get template for max TTL
        template = self.get_template(env.template_id)
        if not template:
            logger.error(f"Template not found: {env.template_id}")
            return None

        # Calculate new expiry
        current_expiry = datetime.fromisoformat(env.expires_at.replace("Z", "+00:00"))
        new_expiry = current_expiry + __import__("datetime").timedelta(
            hours=additional_hours
        )

        # Calculate total hours from creation
        created = datetime.fromisoformat(env.created_at.replace("Z", "+00:00"))
        total_hours = (new_expiry - created).total_seconds() / 3600

        # Check max TTL
        if total_hours > template.max_ttl_hours:
            logger.warning(
                f"TTL extension would exceed max ({total_hours} > {template.max_ttl_hours})"
            )
            # Cap at max
            new_expiry = created + __import__("datetime").timedelta(
                hours=template.max_ttl_hours
            )

        # Update environment
        env.expires_at = new_expiry.isoformat()
        env.metadata["last_extended_by"] = extended_by
        env.metadata["last_extended_at"] = datetime.now(timezone.utc).isoformat()

        # Recalculate DynamoDB TTL
        ttl_timestamp = int(new_expiry.timestamp()) + (self.TTL_BUFFER_HOURS * 3600)

        await self._save_environment(env, ttl_timestamp)

        logger.info(
            f"Extended environment {environment_id} TTL by {additional_hours}h "
            f"(new expiry: {env.expires_at})"
        )

        return env

    # =========================================================================
    # Template Operations
    # =========================================================================

    def get_available_templates(self) -> list[EnvironmentTemplate]:
        """Get all available environment templates."""
        return list(self.templates.values())

    def get_template(self, template_id: str) -> EnvironmentTemplate | None:
        """Get a specific template by ID."""
        return self.templates.get(template_id)

    def register_template(self, template: EnvironmentTemplate) -> None:
        """Register a new template (for extensibility)."""
        self.templates[template.template_id] = template
        logger.info(f"Registered template: {template.template_id}")

    # =========================================================================
    # Quota Operations
    # =========================================================================

    async def get_user_quota(self, user_id: str) -> UserQuota:
        """
        Get user's quota and current usage.

        Args:
            user_id: User identifier

        Returns:
            UserQuota with current usage
        """
        # Count active environments
        active_envs = await self.list_environments(user_id=user_id)
        active_count = sum(
            1
            for env in active_envs
            if env.status
            in (
                EnvironmentStatus.PENDING_APPROVAL,
                EnvironmentStatus.PROVISIONING,
                EnvironmentStatus.ACTIVE,
                EnvironmentStatus.EXPIRING,
            )
        )

        # Calculate monthly spend (simplified - in production, use cost tracking service)
        monthly_spent = sum(
            env.cost_estimate_daily
            for env in active_envs
            if env.status == EnvironmentStatus.ACTIVE
        )

        # Return quota with usage
        if self.mode == PersistenceMode.MOCK:
            base_quota = self.mock_quota_store.get(user_id)
            if base_quota:
                return UserQuota(
                    user_id=user_id,
                    concurrent_limit=base_quota.concurrent_limit,
                    active_count=active_count,
                    monthly_budget=base_quota.monthly_budget,
                    monthly_spent=monthly_spent,
                )

        return UserQuota(
            user_id=user_id,
            concurrent_limit=self.DEFAULT_CONCURRENT_LIMIT,
            active_count=active_count,
            monthly_budget=self.DEFAULT_MONTHLY_BUDGET,
            monthly_spent=monthly_spent,
        )

    async def check_quota_available(self, user_id: str) -> bool:
        """Check if user can create more environments."""
        quota = await self.get_user_quota(user_id)
        return quota.available > 0

    # =========================================================================
    # Status Updates
    # =========================================================================

    async def update_status(
        self,
        environment_id: str,
        status: EnvironmentStatus,
        resources: dict[str, Any] | None = None,
    ) -> TestEnvironment | None:
        """
        Update environment status (called by provisioning workflow).

        Args:
            environment_id: Environment to update
            status: New status
            resources: Optional resource metadata (e.g., stack ARN)

        Returns:
            Updated environment or None
        """
        env = await self.get_environment(environment_id)
        if not env:
            return None

        env.status = status
        if resources:
            env.resources.update(resources)

        await self._save_environment(env)

        logger.info(f"Updated environment {environment_id} status to {status.value}")

        return env

    async def record_activity(self, environment_id: str) -> bool:
        """
        Record activity on an environment (for idle detection).

        Args:
            environment_id: Environment with activity

        Returns:
            True if successful
        """
        env = await self.get_environment(environment_id)
        if not env:
            return False

        env.last_activity_at = datetime.now(timezone.utc).isoformat()
        await self._save_environment(env)

        return True

    # =========================================================================
    # Cleanup Queries
    # =========================================================================

    async def get_expiring_environments(
        self,
        hours_until_expiry: int = 1,
    ) -> list[TestEnvironment]:
        """
        Get environments expiring within the specified window.

        Args:
            hours_until_expiry: Hours until expiry threshold

        Returns:
            List of expiring environments
        """
        now = datetime.now(timezone.utc)
        threshold = now + __import__("datetime").timedelta(hours=hours_until_expiry)

        active_envs = await self.list_environments(status=EnvironmentStatus.ACTIVE)

        expiring = []
        for env in active_envs:
            expires = datetime.fromisoformat(env.expires_at.replace("Z", "+00:00"))
            if expires <= threshold:
                expiring.append(env)

        return expiring

    async def get_idle_environments(
        self,
        idle_hours: int = 2,
    ) -> list[TestEnvironment]:
        """
        Get active environments with no recent activity.

        Args:
            idle_hours: Hours since last activity

        Returns:
            List of idle environments
        """
        now = datetime.now(timezone.utc)
        threshold = now - __import__("datetime").timedelta(hours=idle_hours)

        active_envs = await self.list_environments(status=EnvironmentStatus.ACTIVE)

        idle = []
        for env in active_envs:
            if env.last_activity_at:
                last_activity = datetime.fromisoformat(
                    env.last_activity_at.replace("Z", "+00:00")
                )
                if last_activity < threshold:
                    idle.append(env)

        return idle

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """
        Check service health.

        Returns:
            Health status dictionary
        """
        status = {
            "service": "environment_provisioning",
            "mode": self.mode.value,
            "table_name": self.table_name,
            "region": self.region,
            "templates_count": len(self.templates),
            "healthy": True,
        }

        if self.mode == PersistenceMode.AWS:
            try:
                # Test DynamoDB connectivity
                self.table.table_status
                status["dynamodb_status"] = "connected"
            except Exception as e:
                status["dynamodb_status"] = f"error: {str(e)}"
                status["healthy"] = False

        return status

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _check_requires_approval(
        self,
        organization_id: str,
        environment_type: EnvironmentType,
    ) -> bool:
        """
        Check if HITL approval is required using AutonomyPolicyService.

        Args:
            organization_id: Organization to check policy for
            environment_type: Type of environment being created

        Returns:
            True if HITL approval is required
        """
        # If no autonomy service configured, use type-based defaults
        if not self.autonomy_service:
            # Default: extended and compliance types require approval
            return environment_type in (
                EnvironmentType.EXTENDED,
                EnvironmentType.COMPLIANCE,
            )

        # Map environment type to severity
        severity = self.SEVERITY_MAP.get(environment_type, "HIGH")

        try:
            # Get organization's policy
            # Note: This assumes AutonomyPolicyService has these methods
            policy = self.autonomy_service.get_policy_for_organization(organization_id)
            if not policy:
                # No policy = require HITL (safe default)
                return True

            # Check if HITL required for environment_provision operation
            return cast(
                bool,
                self.autonomy_service.requires_hitl_approval(
                    policy_id=policy.policy_id,
                    severity=severity,
                    operation="environment_provision",
                ),
            )
        except Exception as e:
            logger.error(f"Error checking HITL requirement: {e}")
            # On error, require approval (safe default)
            return True

    async def _save_environment(
        self,
        env: TestEnvironment,
        ttl_timestamp: int | None = None,
    ) -> None:
        """
        Save environment to storage.

        Args:
            env: Environment to save
            ttl_timestamp: Optional TTL timestamp for DynamoDB
        """
        item = env.to_dict()

        if ttl_timestamp:
            item["ttl"] = ttl_timestamp

        if self.mode == PersistenceMode.MOCK:
            self.mock_store[env.environment_id] = item
        else:
            try:
                self.table.put_item(Item=item)
            except Exception as e:
                logger.error(f"Failed to save environment {env.environment_id}: {e}")
                raise EnvironmentProvisioningError(f"Save failed: {e}")


# ============================================================================
# Factory Functions
# ============================================================================

_service_instance: EnvironmentProvisioningService | None = None


def get_environment_service() -> EnvironmentProvisioningService:
    """Get or create the environment provisioning service singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = EnvironmentProvisioningService()
    return _service_instance


def create_environment_service(
    mode: PersistenceMode = PersistenceMode.MOCK,
    table_name: str | None = None,
    autonomy_service: Any | None = None,
) -> EnvironmentProvisioningService:
    """Create a new environment provisioning service instance."""
    return EnvironmentProvisioningService(
        mode=mode,
        table_name=table_name,
        autonomy_service=autonomy_service,
    )
