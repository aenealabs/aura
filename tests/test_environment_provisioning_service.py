"""
Project Aura - Environment Provisioning Service Tests

Unit tests for the EnvironmentProvisioningService.

Author: Project Aura Team
Created: 2025-12-14
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.services.environment_provisioning_service import (
    DEFAULT_TEMPLATES,
    EnvironmentConfig,
    EnvironmentProvisioningService,
    EnvironmentStatus,
    EnvironmentTemplate,
    EnvironmentType,
    PersistenceMode,
    QuotaExceededError,
    TemplateNotFoundError,
    TestEnvironment,
    UserQuota,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_service():
    """Create a mock-mode service for testing."""
    with patch.dict(os.environ, {"ENVIRONMENT": "test", "PROJECT_NAME": "aura"}):
        service = EnvironmentProvisioningService(mode=PersistenceMode.MOCK)
        return service


@pytest.fixture
def sample_config():
    """Create a sample environment configuration."""
    return EnvironmentConfig(
        template_id="python-fastapi",
        display_name="My Test Environment",
        description="A test environment for API testing",
        metadata={"team": "platform", "ticket": "AURA-123"},
    )


@pytest.fixture
def sample_environment():
    """Create a sample test environment."""
    now = datetime.now(timezone.utc)
    return TestEnvironment(
        environment_id="env-abc123def456",
        user_id="user-123",
        organization_id="org-456",
        environment_type=EnvironmentType.STANDARD,
        template_id="python-fastapi",
        display_name="Test Env",
        status=EnvironmentStatus.ACTIVE,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=24)).isoformat(),
        dns_name="env-abc123def456.test.aura.local",
        cost_estimate_daily=0.50,
        last_activity_at=now.isoformat(),
    )


# ============================================================================
# TestEnvironment Dataclass Tests
# ============================================================================


class TestTestEnvironmentDataclass:
    """Tests for TestEnvironment dataclass serialization."""

    def test_to_dict(self, sample_environment):
        """Test conversion to dictionary."""
        data = sample_environment.to_dict()

        assert data["environment_id"] == "env-abc123def456"
        assert data["user_id"] == "user-123"
        assert data["environment_type"] == "standard"
        assert data["status"] == "active"
        assert data["cost_estimate_daily"] == 0.50

    def test_from_dict(self, sample_environment):
        """Test creation from dictionary."""
        data = sample_environment.to_dict()
        restored = TestEnvironment.from_dict(data)

        assert restored.environment_id == sample_environment.environment_id
        assert restored.environment_type == sample_environment.environment_type
        assert restored.status == sample_environment.status

    def test_round_trip_serialization(self, sample_environment):
        """Test that to_dict/from_dict is lossless."""
        data = sample_environment.to_dict()
        restored = TestEnvironment.from_dict(data)

        # Compare all fields
        assert restored.environment_id == sample_environment.environment_id
        assert restored.user_id == sample_environment.user_id
        assert restored.organization_id == sample_environment.organization_id
        assert restored.environment_type == sample_environment.environment_type
        assert restored.template_id == sample_environment.template_id
        assert restored.display_name == sample_environment.display_name
        assert restored.status == sample_environment.status
        assert restored.dns_name == sample_environment.dns_name


class TestEnvironmentTemplateDataclass:
    """Tests for EnvironmentTemplate dataclass."""

    def test_to_dict(self):
        """Test template conversion to dictionary."""
        template = DEFAULT_TEMPLATES[0]  # quick-test
        data = template.to_dict()

        assert data["template_id"] == "quick-test"
        assert data["environment_type"] == "quick"
        assert isinstance(data["resources"], list)

    def test_from_dict(self):
        """Test template creation from dictionary."""
        data = {
            "template_id": "test-template",
            "name": "Test Template",
            "description": "A test template",
            "environment_type": "standard",
            "default_ttl_hours": 24,
            "max_ttl_hours": 72,
            "cost_per_day": 1.0,
            "resources": ["ECS Task"],
            "requires_approval": True,
        }
        template = EnvironmentTemplate.from_dict(data)

        assert template.template_id == "test-template"
        assert template.environment_type == EnvironmentType.STANDARD
        assert template.requires_approval is True


class TestUserQuotaDataclass:
    """Tests for UserQuota dataclass."""

    def test_available_calculation(self):
        """Test available environments calculation."""
        quota = UserQuota(
            user_id="user-123",
            concurrent_limit=3,
            active_count=2,
        )
        assert quota.available == 1

    def test_available_at_limit(self):
        """Test available is 0 when at limit."""
        quota = UserQuota(
            user_id="user-123",
            concurrent_limit=3,
            active_count=3,
        )
        assert quota.available == 0

    def test_available_over_limit(self):
        """Test available doesn't go negative."""
        quota = UserQuota(
            user_id="user-123",
            concurrent_limit=3,
            active_count=5,  # Over limit (edge case)
        )
        assert quota.available == 0

    def test_monthly_remaining(self):
        """Test monthly budget remaining calculation."""
        quota = UserQuota(
            user_id="user-123",
            monthly_budget=500.0,
            monthly_spent=150.0,
        )
        assert quota.monthly_remaining == 350.0

    def test_to_dict(self):
        """Test quota to dictionary conversion."""
        quota = UserQuota(
            user_id="user-123",
            concurrent_limit=3,
            active_count=1,
            monthly_budget=500.0,
            monthly_spent=100.0,
        )
        data = quota.to_dict()

        assert data["user_id"] == "user-123"
        assert data["available"] == 2
        assert data["monthly_remaining"] == 400.0


# ============================================================================
# EnvironmentProvisioningService Tests
# ============================================================================


class TestServiceInitialization:
    """Tests for service initialization."""

    def test_init_mock_mode(self):
        """Test initialization in mock mode."""
        with patch.dict(os.environ, {"ENVIRONMENT": "test"}):
            service = EnvironmentProvisioningService(mode=PersistenceMode.MOCK)

        assert service.mode == PersistenceMode.MOCK
        assert "test-env-state" in service.table_name

    def test_init_with_custom_table_name(self):
        """Test initialization with custom table name."""
        service = EnvironmentProvisioningService(
            mode=PersistenceMode.MOCK,
            table_name="custom-table",
        )
        assert service.table_name == "custom-table"

    def test_templates_loaded(self, mock_service):
        """Test that default templates are loaded."""
        assert len(mock_service.templates) == len(DEFAULT_TEMPLATES)
        assert "python-fastapi" in mock_service.templates
        assert "quick-test" in mock_service.templates


class TestTemplateOperations:
    """Tests for template management operations."""

    def test_get_available_templates(self, mock_service):
        """Test getting all templates."""
        templates = mock_service.get_available_templates()

        assert len(templates) == len(DEFAULT_TEMPLATES)
        assert all(isinstance(t, EnvironmentTemplate) for t in templates)

    def test_get_template_exists(self, mock_service):
        """Test getting existing template."""
        template = mock_service.get_template("python-fastapi")

        assert template is not None
        assert template.template_id == "python-fastapi"
        assert template.environment_type == EnvironmentType.STANDARD

    def test_get_template_not_found(self, mock_service):
        """Test getting non-existent template."""
        template = mock_service.get_template("nonexistent-template")

        assert template is None

    def test_register_template(self, mock_service):
        """Test registering a new template."""
        new_template = EnvironmentTemplate(
            template_id="custom-template",
            name="Custom Template",
            description="A custom template",
            environment_type=EnvironmentType.STANDARD,
            default_ttl_hours=12,
            max_ttl_hours=24,
            cost_per_day=0.75,
            resources=["Lambda"],
        )

        mock_service.register_template(new_template)

        retrieved = mock_service.get_template("custom-template")
        assert retrieved is not None
        assert retrieved.name == "Custom Template"


class TestCreateEnvironment:
    """Tests for environment creation."""

    @pytest.mark.asyncio
    async def test_create_environment_success(self, mock_service, sample_config):
        """Test successful environment creation."""
        env = await mock_service.create_environment(
            user_id="user-123",
            organization_id="org-456",
            config=sample_config,
        )

        assert env is not None
        assert env.environment_id.startswith("env-")
        assert env.user_id == "user-123"
        assert env.organization_id == "org-456"
        assert env.template_id == "python-fastapi"
        assert env.display_name == "My Test Environment"
        assert env.dns_name.endswith(".test.aura.local")
        assert env.status in (
            EnvironmentStatus.PROVISIONING,
            EnvironmentStatus.PENDING_APPROVAL,
        )

    @pytest.mark.asyncio
    async def test_create_environment_quick_type(self, mock_service):
        """Test creating quick environment (auto-approved)."""
        config = EnvironmentConfig(
            template_id="quick-test",
            display_name="Quick Test",
        )

        env = await mock_service.create_environment(
            user_id="user-123",
            organization_id="org-456",
            config=config,
        )

        assert env.environment_type == EnvironmentType.QUICK
        # Quick types should be auto-approved (PROVISIONING, not PENDING_APPROVAL)
        assert env.status == EnvironmentStatus.PROVISIONING

    @pytest.mark.asyncio
    async def test_create_environment_extended_type(self, mock_service):
        """Test creating extended environment (requires approval by default)."""
        config = EnvironmentConfig(
            template_id="data-pipeline",
            display_name="Data Pipeline Test",
        )

        env = await mock_service.create_environment(
            user_id="user-123",
            organization_id="org-456",
            config=config,
        )

        assert env.environment_type == EnvironmentType.EXTENDED
        # Extended types require approval by default
        assert env.status == EnvironmentStatus.PENDING_APPROVAL

    @pytest.mark.asyncio
    async def test_create_environment_invalid_template(self, mock_service):
        """Test creation with invalid template raises error."""
        config = EnvironmentConfig(
            template_id="nonexistent-template",
            display_name="Test",
        )

        with pytest.raises(TemplateNotFoundError):
            await mock_service.create_environment(
                user_id="user-123",
                organization_id="org-456",
                config=config,
            )

    @pytest.mark.asyncio
    async def test_create_environment_quota_exceeded(self, mock_service, sample_config):
        """Test creation fails when quota exceeded."""
        # Create environments up to quota limit
        for i in range(mock_service.DEFAULT_CONCURRENT_LIMIT):
            await mock_service.create_environment(
                user_id="user-123",
                organization_id="org-456",
                config=EnvironmentConfig(
                    template_id="python-fastapi",
                    display_name=f"Test {i}",
                ),
            )

        # Next creation should fail
        with pytest.raises(QuotaExceededError):
            await mock_service.create_environment(
                user_id="user-123",
                organization_id="org-456",
                config=sample_config,
            )

    @pytest.mark.asyncio
    async def test_create_environment_custom_ttl(self, mock_service):
        """Test creation with custom TTL."""
        config = EnvironmentConfig(
            template_id="python-fastapi",
            display_name="Custom TTL Test",
            ttl_hours=12,
        )

        env = await mock_service.create_environment(
            user_id="user-123",
            organization_id="org-456",
            config=config,
        )

        # Check TTL is approximately 12 hours
        created = datetime.fromisoformat(env.created_at.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(env.expires_at.replace("Z", "+00:00"))
        ttl_hours = (expires - created).total_seconds() / 3600

        assert 11.9 < ttl_hours < 12.1  # Allow small rounding

    @pytest.mark.asyncio
    async def test_create_environment_ttl_capped_at_max(self, mock_service):
        """Test that TTL is capped at template max."""
        config = EnvironmentConfig(
            template_id="python-fastapi",  # max_ttl_hours = 72
            display_name="Over Max TTL",
            ttl_hours=200,  # Way over max
        )

        env = await mock_service.create_environment(
            user_id="user-123",
            organization_id="org-456",
            config=config,
        )

        created = datetime.fromisoformat(env.created_at.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(env.expires_at.replace("Z", "+00:00"))
        ttl_hours = (expires - created).total_seconds() / 3600

        # Should be capped at 72
        assert ttl_hours <= 72.1


class TestGetEnvironment:
    """Tests for environment retrieval."""

    @pytest.mark.asyncio
    async def test_get_environment_exists(self, mock_service, sample_config):
        """Test getting existing environment."""
        created = await mock_service.create_environment(
            user_id="user-123",
            organization_id="org-456",
            config=sample_config,
        )

        retrieved = await mock_service.get_environment(created.environment_id)

        assert retrieved is not None
        assert retrieved.environment_id == created.environment_id
        assert retrieved.display_name == created.display_name

    @pytest.mark.asyncio
    async def test_get_environment_not_found(self, mock_service):
        """Test getting non-existent environment."""
        result = await mock_service.get_environment("env-nonexistent")

        assert result is None


class TestListEnvironments:
    """Tests for listing environments."""

    @pytest.mark.asyncio
    async def test_list_environments_empty(self, mock_service):
        """Test listing with no environments."""
        envs = await mock_service.list_environments()

        assert envs == []

    @pytest.mark.asyncio
    async def test_list_environments_by_user(self, mock_service):
        """Test listing environments filtered by user."""
        # Create environments for different users
        for i in range(2):
            await mock_service.create_environment(
                user_id="user-A",
                organization_id="org-456",
                config=EnvironmentConfig(
                    template_id="python-fastapi",
                    display_name=f"User A Env {i}",
                ),
            )

        await mock_service.create_environment(
            user_id="user-B",
            organization_id="org-456",
            config=EnvironmentConfig(
                template_id="python-fastapi",
                display_name="User B Env",
            ),
        )

        # List for user A
        user_a_envs = await mock_service.list_environments(user_id="user-A")

        assert len(user_a_envs) == 2
        assert all(env.user_id == "user-A" for env in user_a_envs)

    @pytest.mark.asyncio
    async def test_list_environments_by_status(self, mock_service, sample_config):
        """Test listing environments filtered by status."""
        # Create and terminate one environment
        env = await mock_service.create_environment(
            user_id="user-123",
            organization_id="org-456",
            config=sample_config,
        )
        await mock_service.terminate_environment(env.environment_id, "user-123")

        # Create an active one
        await mock_service.create_environment(
            user_id="user-123",
            organization_id="org-456",
            config=EnvironmentConfig(
                template_id="quick-test",
                display_name="Active Env",
            ),
        )

        # List terminating
        terminating = await mock_service.list_environments(
            status=EnvironmentStatus.TERMINATING
        )

        assert len(terminating) == 1
        assert terminating[0].status == EnvironmentStatus.TERMINATING

    @pytest.mark.asyncio
    async def test_list_environments_limit(self, mock_service):
        """Test listing with limit."""
        # Create 5 environments using different users to avoid quota limits
        for i in range(5):
            await mock_service.create_environment(
                user_id=f"user-{i}",  # Different user each time
                organization_id="org-456",
                config=EnvironmentConfig(
                    template_id="quick-test",
                    display_name=f"Env {i}",
                ),
            )

        # List with limit (no user filter = all environments)
        envs = await mock_service.list_environments(limit=3)

        assert len(envs) == 3


class TestTerminateEnvironment:
    """Tests for environment termination."""

    @pytest.mark.asyncio
    async def test_terminate_environment_success(self, mock_service, sample_config):
        """Test successful termination."""
        env = await mock_service.create_environment(
            user_id="user-123",
            organization_id="org-456",
            config=sample_config,
        )

        result = await mock_service.terminate_environment(
            environment_id=env.environment_id,
            terminated_by="user-123",
            reason="Testing complete",
        )

        assert result is True

        # Verify status changed
        terminated = await mock_service.get_environment(env.environment_id)
        assert terminated.status == EnvironmentStatus.TERMINATING
        assert terminated.metadata["terminated_by"] == "user-123"
        assert terminated.metadata["termination_reason"] == "Testing complete"

    @pytest.mark.asyncio
    async def test_terminate_environment_not_found(self, mock_service):
        """Test terminating non-existent environment."""
        result = await mock_service.terminate_environment(
            environment_id="env-nonexistent",
            terminated_by="user-123",
        )

        assert result is False


class TestExtendTTL:
    """Tests for TTL extension."""

    @pytest.mark.asyncio
    async def test_extend_ttl_success(self, mock_service, sample_config):
        """Test successful TTL extension."""
        env = await mock_service.create_environment(
            user_id="user-123",
            organization_id="org-456",
            config=sample_config,
        )

        original_expiry = env.expires_at

        extended = await mock_service.extend_ttl(
            environment_id=env.environment_id,
            additional_hours=4,
            extended_by="user-123",
        )

        assert extended is not None
        assert extended.expires_at > original_expiry
        assert extended.metadata["last_extended_by"] == "user-123"

    @pytest.mark.asyncio
    async def test_extend_ttl_capped_at_max(self, mock_service):
        """Test TTL extension is capped at template max."""
        config = EnvironmentConfig(
            template_id="python-fastapi",  # max 72 hours
            display_name="Test",
            ttl_hours=70,  # Near max
        )

        env = await mock_service.create_environment(
            user_id="user-123",
            organization_id="org-456",
            config=config,
        )

        # Try to extend by 10 hours (would exceed max)
        extended = await mock_service.extend_ttl(
            environment_id=env.environment_id,
            additional_hours=10,
            extended_by="user-123",
        )

        # Calculate resulting TTL
        created = datetime.fromisoformat(extended.created_at.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(extended.expires_at.replace("Z", "+00:00"))
        total_hours = (expires - created).total_seconds() / 3600

        # Should be capped at 72
        assert total_hours <= 72.1

    @pytest.mark.asyncio
    async def test_extend_ttl_not_found(self, mock_service):
        """Test extending non-existent environment."""
        result = await mock_service.extend_ttl(
            environment_id="env-nonexistent",
            additional_hours=4,
            extended_by="user-123",
        )

        assert result is None


class TestQuotaOperations:
    """Tests for quota management."""

    @pytest.mark.asyncio
    async def test_get_user_quota_no_environments(self, mock_service):
        """Test quota for user with no environments."""
        quota = await mock_service.get_user_quota("user-123")

        assert quota.user_id == "user-123"
        assert quota.concurrent_limit == mock_service.DEFAULT_CONCURRENT_LIMIT
        assert quota.active_count == 0
        assert quota.available == mock_service.DEFAULT_CONCURRENT_LIMIT

    @pytest.mark.asyncio
    async def test_get_user_quota_with_environments(self, mock_service):
        """Test quota reflects active environments."""
        # Create 2 environments
        for i in range(2):
            await mock_service.create_environment(
                user_id="user-123",
                organization_id="org-456",
                config=EnvironmentConfig(
                    template_id="python-fastapi",
                    display_name=f"Env {i}",
                ),
            )

        quota = await mock_service.get_user_quota("user-123")

        assert quota.active_count == 2
        assert quota.available == mock_service.DEFAULT_CONCURRENT_LIMIT - 2

    @pytest.mark.asyncio
    async def test_check_quota_available(self, mock_service):
        """Test quota availability check."""
        available = await mock_service.check_quota_available("user-123")

        assert available is True

    @pytest.mark.asyncio
    async def test_check_quota_not_available(self, mock_service):
        """Test quota unavailable when at limit."""
        # Fill up quota
        for i in range(mock_service.DEFAULT_CONCURRENT_LIMIT):
            await mock_service.create_environment(
                user_id="user-123",
                organization_id="org-456",
                config=EnvironmentConfig(
                    template_id="quick-test",
                    display_name=f"Env {i}",
                ),
            )

        available = await mock_service.check_quota_available("user-123")

        assert available is False


class TestStatusUpdates:
    """Tests for status update operations."""

    @pytest.mark.asyncio
    async def test_update_status(self, mock_service, sample_config):
        """Test updating environment status."""
        env = await mock_service.create_environment(
            user_id="user-123",
            organization_id="org-456",
            config=sample_config,
        )

        updated = await mock_service.update_status(
            environment_id=env.environment_id,
            status=EnvironmentStatus.ACTIVE,
            resources={"stack_arn": "arn:aws:cloudformation:..."},
        )

        assert updated is not None
        assert updated.status == EnvironmentStatus.ACTIVE
        assert "stack_arn" in updated.resources

    @pytest.mark.asyncio
    async def test_record_activity(self, mock_service, sample_config):
        """Test recording environment activity."""
        env = await mock_service.create_environment(
            user_id="user-123",
            organization_id="org-456",
            config=sample_config,
        )

        original_activity = env.last_activity_at

        # Wait a tiny bit to ensure timestamp changes
        import time

        time.sleep(0.01)

        result = await mock_service.record_activity(env.environment_id)

        assert result is True

        updated = await mock_service.get_environment(env.environment_id)
        assert updated.last_activity_at >= original_activity


class TestCleanupQueries:
    """Tests for cleanup-related queries."""

    @pytest.mark.asyncio
    async def test_get_expiring_environments(self, mock_service):
        """Test finding expiring environments."""
        # Create an environment with very short TTL
        config = EnvironmentConfig(
            template_id="quick-test",
            display_name="Expiring Soon",
            ttl_hours=1,  # 1 hour TTL
        )

        env = await mock_service.create_environment(
            user_id="user-123",
            organization_id="org-456",
            config=config,
        )

        # Update status to ACTIVE (expiring query only checks active)
        await mock_service.update_status(
            env.environment_id,
            EnvironmentStatus.ACTIVE,
        )

        # Query for environments expiring in next 2 hours
        expiring = await mock_service.get_expiring_environments(hours_until_expiry=2)

        assert len(expiring) == 1
        assert expiring[0].environment_id == env.environment_id

    @pytest.mark.asyncio
    async def test_get_idle_environments(self, mock_service, sample_config):
        """Test finding idle environments."""
        env = await mock_service.create_environment(
            user_id="user-123",
            organization_id="org-456",
            config=sample_config,
        )

        # Update status to ACTIVE
        await mock_service.update_status(
            env.environment_id,
            EnvironmentStatus.ACTIVE,
        )

        # Manually set last_activity_at to 3 hours ago
        env_data = mock_service.mock_store[env.environment_id]
        old_time = datetime.now(timezone.utc) - timedelta(hours=3)
        env_data["last_activity_at"] = old_time.isoformat()

        # Query for idle environments (idle > 2 hours)
        idle = await mock_service.get_idle_environments(idle_hours=2)

        assert len(idle) == 1
        assert idle[0].environment_id == env.environment_id


class TestHealthCheck:
    """Tests for health check."""

    @pytest.mark.asyncio
    async def test_health_check_mock_mode(self, mock_service):
        """Test health check in mock mode."""
        health = await mock_service.health_check()

        assert health["service"] == "environment_provisioning"
        assert health["mode"] == "mock"
        assert health["healthy"] is True
        assert health["templates_count"] == len(DEFAULT_TEMPLATES)


class TestAutonomyIntegration:
    """Tests for AutonomyPolicyService integration."""

    @pytest.mark.asyncio
    async def test_check_requires_approval_no_service(self, mock_service):
        """Test approval check without autonomy service uses defaults."""
        # Without autonomy service, extended/compliance require approval
        assert (
            mock_service._check_requires_approval("org-123", EnvironmentType.QUICK)
            is False
        )
        assert (
            mock_service._check_requires_approval("org-123", EnvironmentType.STANDARD)
            is False
        )
        assert (
            mock_service._check_requires_approval("org-123", EnvironmentType.EXTENDED)
            is True
        )
        assert (
            mock_service._check_requires_approval("org-123", EnvironmentType.COMPLIANCE)
            is True
        )

    @pytest.mark.asyncio
    async def test_check_requires_approval_with_service(self):
        """Test approval check delegates to autonomy service."""
        mock_autonomy = MagicMock()
        mock_policy = MagicMock()
        mock_policy.policy_id = "policy-123"

        mock_autonomy.get_policy_for_organization.return_value = mock_policy
        mock_autonomy.requires_hitl_approval.return_value = True

        service = EnvironmentProvisioningService(
            mode=PersistenceMode.MOCK,
            autonomy_service=mock_autonomy,
        )

        result = service._check_requires_approval("org-123", EnvironmentType.STANDARD)

        assert result is True
        mock_autonomy.get_policy_for_organization.assert_called_once_with("org-123")
        mock_autonomy.requires_hitl_approval.assert_called_once_with(
            policy_id="policy-123",
            severity="MEDIUM",
            operation="environment_provision",
        )

    @pytest.mark.asyncio
    async def test_check_requires_approval_no_policy(self):
        """Test approval required when no org policy exists."""
        mock_autonomy = MagicMock()
        mock_autonomy.get_policy_for_organization.return_value = None

        service = EnvironmentProvisioningService(
            mode=PersistenceMode.MOCK,
            autonomy_service=mock_autonomy,
        )

        result = service._check_requires_approval("org-123", EnvironmentType.QUICK)

        # No policy = safe default = require approval
        assert result is True
