"""
Tests for Feature Flags API Endpoints.

Comprehensive test suite covering:
- Feature listing and filtering
- Feature status retrieval
- Beta feature management
- Beta enrollment
- Admin override functionality
- Authorization and access control
"""

import platform

import pytest

# Run tests in separate processes to avoid mock pollution
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from src.api.feature_flags_endpoints import (
    BetaEnrollmentRequest,
    BetaEnrollmentResponse,
    FeatureResponse,
    FeatureStatusResponse,
    feature_to_response,
    get_user_tier,
)
from src.config.feature_flags import (
    CustomerFeatureOverrides,
    FeatureDefinition,
    FeatureStatus,
    FeatureTier,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    user = MagicMock()
    user.id = "user-123"
    user.email = "test@example.com"
    user.customer_id = "cust-456"
    user.roles = ["user"]
    user.tier = "professional"
    return user


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    user = MagicMock()
    user.id = "admin-123"
    user.email = "admin@example.com"
    user.customer_id = "cust-admin"
    user.roles = ["admin"]
    user.tier = "enterprise"
    return user


@pytest.fixture
def mock_user_no_customer():
    """Create a mock user without customer_id."""
    user = MagicMock(spec=["id", "email", "roles", "tier"])
    user.id = "user-nocust"
    user.email = "nocust@example.com"
    user.roles = ["user"]
    user.tier = "starter"
    return user


@pytest.fixture
def sample_feature():
    """Create a sample feature definition."""
    return FeatureDefinition(
        name="advanced_analytics",
        description="Advanced analytics dashboard with custom reports",
        status=FeatureStatus.GA,
        min_tier=FeatureTier.PROFESSIONAL,
        enabled_by_default=True,
        requires_consent=False,
        rollout_percentage=100,
    )


@pytest.fixture
def sample_beta_feature():
    """Create a sample beta feature."""
    return FeatureDefinition(
        name="ai_code_review",
        description="AI-powered code review suggestions",
        status=FeatureStatus.BETA,
        min_tier=FeatureTier.PROFESSIONAL,
        enabled_by_default=False,
        requires_consent=True,
        rollout_percentage=50,
    )


@pytest.fixture
def sample_alpha_feature():
    """Create a sample alpha feature."""
    return FeatureDefinition(
        name="experimental_rag",
        description="Experimental RAG improvements",
        status=FeatureStatus.ALPHA,
        min_tier=FeatureTier.ENTERPRISE,
        enabled_by_default=False,
        requires_consent=True,
        rollout_percentage=10,
    )


@pytest.fixture
def sample_customer_overrides():
    """Create sample customer overrides."""
    return CustomerFeatureOverrides(
        customer_id="cust-456",
        tier=FeatureTier.PROFESSIONAL,
        enabled_features={"ai_code_review"},
        disabled_features=set(),
        beta_participant=True,
    )


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Test helper conversion functions."""

    def test_feature_to_response_enabled(self, sample_feature):
        """Test feature to response conversion when enabled."""
        response = feature_to_response(sample_feature, enabled=True)

        assert isinstance(response, FeatureResponse)
        assert response.name == "advanced_analytics"
        assert (
            response.description == "Advanced analytics dashboard with custom reports"
        )
        assert response.status == "ga"
        assert response.min_tier == "professional"
        assert response.enabled is True
        assert response.enabled_by_default is True
        assert response.requires_consent is False
        assert response.rollout_percentage == 100

    def test_feature_to_response_disabled(self, sample_feature):
        """Test feature to response conversion when disabled."""
        response = feature_to_response(sample_feature, enabled=False)

        assert response.enabled is False

    def test_feature_to_response_beta(self, sample_beta_feature):
        """Test feature to response for beta feature."""
        response = feature_to_response(sample_beta_feature, enabled=True)

        assert response.status == "beta"
        assert response.requires_consent is True
        assert response.rollout_percentage == 50

    def test_get_user_tier_valid(self, mock_user):
        """Test getting user tier with valid tier."""
        tier = get_user_tier(mock_user)

        assert tier == FeatureTier.PROFESSIONAL

    def test_get_user_tier_starter_default(self):
        """Test default tier for user without tier attribute."""
        user = MagicMock(spec=["id", "email"])
        tier = get_user_tier(user)

        assert tier == FeatureTier.STARTER

    def test_get_user_tier_invalid(self):
        """Test handling invalid tier value."""
        user = MagicMock()
        user.tier = "invalid_tier"
        tier = get_user_tier(user)

        assert tier == FeatureTier.STARTER


# =============================================================================
# Feature Listing Tests
# =============================================================================


class TestFeatureListing:
    """Test feature listing endpoints."""

    @pytest.mark.asyncio
    async def test_list_features_all(
        self, mock_user, sample_feature, sample_beta_feature
    ):
        """Test listing all features."""
        from src.api.feature_flags_endpoints import list_features

        mock_service = MagicMock()
        mock_service.list_features.return_value = [sample_feature, sample_beta_feature]
        mock_service.is_enabled.return_value = True

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            result = await list_features(status=None, current_user=mock_user)

        assert len(result) == 2
        assert result[0].name == "advanced_analytics"
        assert result[1].name == "ai_code_review"

    @pytest.mark.asyncio
    async def test_list_features_by_status(self, mock_user, sample_beta_feature):
        """Test listing features filtered by status."""
        from src.api.feature_flags_endpoints import list_features

        mock_service = MagicMock()
        mock_service.list_features.return_value = [sample_beta_feature]
        mock_service.is_enabled.return_value = False

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            result = await list_features(status="beta", current_user=mock_user)

        assert len(result) == 1
        assert result[0].status == "beta"
        mock_service.list_features.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_features_invalid_status(self, mock_user):
        """Test listing features with invalid status filter."""
        from src.api.feature_flags_endpoints import list_features

        mock_service = MagicMock()

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await list_features(status="invalid", current_user=mock_user)

        assert exc_info.value.status_code == 400
        assert "Invalid status" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_features_service_error(self, mock_user):
        """Test handling service errors in list features."""
        from src.api.feature_flags_endpoints import list_features

        mock_service = MagicMock()
        mock_service.list_features.side_effect = Exception("Service error")

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await list_features(status=None, current_user=mock_user)

        assert exc_info.value.status_code == 500


# =============================================================================
# Feature Status Tests
# =============================================================================


class TestFeatureStatus:
    """Test feature status endpoint."""

    @pytest.mark.asyncio
    async def test_get_feature_status(self, mock_user, sample_customer_overrides):
        """Test getting feature status for user."""
        from src.api.feature_flags_endpoints import get_feature_status

        mock_service = MagicMock()
        mock_service.get_feature_flags_status.return_value = {
            "advanced_analytics": {"enabled": True, "tier": "professional"},
            "ai_code_review": {"enabled": True, "tier": "professional"},
        }
        mock_service.get_customer_overrides.return_value = sample_customer_overrides

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            result = await get_feature_status(current_user=mock_user)

        assert isinstance(result, FeatureStatusResponse)
        assert result.tier == "professional"
        assert result.beta_participant is True
        assert result.enabled_count == 2
        assert result.total_count == 2

    @pytest.mark.asyncio
    async def test_get_feature_status_no_overrides(self, mock_user):
        """Test feature status without customer overrides."""
        from src.api.feature_flags_endpoints import get_feature_status

        mock_service = MagicMock()
        mock_service.get_feature_flags_status.return_value = {
            "advanced_analytics": {"enabled": True, "tier": "professional"},
        }
        mock_service.get_customer_overrides.return_value = None

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            result = await get_feature_status(current_user=mock_user)

        assert result.beta_participant is False

    @pytest.mark.asyncio
    async def test_get_feature_status_service_error(self, mock_user):
        """Test handling service errors in feature status."""
        from src.api.feature_flags_endpoints import get_feature_status

        mock_service = MagicMock()
        mock_service.get_feature_flags_status.side_effect = Exception("DB error")

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_feature_status(current_user=mock_user)

        assert exc_info.value.status_code == 500


# =============================================================================
# Beta Features Tests
# =============================================================================


class TestBetaFeatures:
    """Test beta feature endpoints."""

    @pytest.mark.asyncio
    async def test_list_beta_features(self, mock_user, sample_beta_feature):
        """Test listing beta features."""
        from src.api.feature_flags_endpoints import list_beta_features

        mock_service = MagicMock()
        mock_service.is_enabled.return_value = False

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            with patch(
                "src.api.feature_flags_endpoints.get_beta_features",
                return_value={"ai_code_review": sample_beta_feature},
            ):
                result = await list_beta_features(current_user=mock_user)

        assert len(result) == 1
        assert result[0].name == "ai_code_review"
        assert result[0].status == "beta"

    @pytest.mark.asyncio
    async def test_list_beta_features_empty(self, mock_user):
        """Test listing beta features when none exist."""
        from src.api.feature_flags_endpoints import list_beta_features

        mock_service = MagicMock()

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            with patch(
                "src.api.feature_flags_endpoints.get_beta_features", return_value={}
            ):
                result = await list_beta_features(current_user=mock_user)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_beta_features_service_error(self, mock_user):
        """Test handling errors in list beta features."""
        from src.api.feature_flags_endpoints import list_beta_features

        mock_service = MagicMock()
        mock_service.is_enabled.side_effect = Exception("Error")

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            with patch(
                "src.api.feature_flags_endpoints.get_beta_features",
                return_value={"feature": MagicMock()},
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await list_beta_features(current_user=mock_user)

        assert exc_info.value.status_code == 500


# =============================================================================
# Beta Enrollment Tests
# =============================================================================


class TestBetaEnrollment:
    """Test beta enrollment endpoint."""

    @pytest.mark.asyncio
    async def test_enroll_in_beta_success(self, mock_user, sample_beta_feature):
        """Test successful beta enrollment."""
        from src.api.feature_flags_endpoints import enroll_in_beta

        mock_service = MagicMock()
        mock_service.enable_beta_features.return_value = None
        mock_service.list_enabled_features.return_value = ["ai_code_review"]

        request = BetaEnrollmentRequest(accept_terms=True)

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            with patch(
                "src.api.feature_flags_endpoints.get_beta_features",
                return_value={"ai_code_review": sample_beta_feature},
            ):
                result = await enroll_in_beta(request=request, current_user=mock_user)

        assert isinstance(result, BetaEnrollmentResponse)
        assert result.enrolled is True
        assert "ai_code_review" in result.enabled_features
        assert "Successfully enrolled" in result.message

    @pytest.mark.asyncio
    async def test_enroll_in_beta_terms_not_accepted(self, mock_user):
        """Test beta enrollment without accepting terms."""
        from src.api.feature_flags_endpoints import enroll_in_beta

        request = BetaEnrollmentRequest(accept_terms=False)

        with pytest.raises(HTTPException) as exc_info:
            await enroll_in_beta(request=request, current_user=mock_user)

        assert exc_info.value.status_code == 400
        assert "accept beta program terms" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_enroll_in_beta_no_customer_id(self, mock_user_no_customer):
        """Test beta enrollment without customer ID."""
        from src.api.feature_flags_endpoints import enroll_in_beta

        request = BetaEnrollmentRequest(accept_terms=True)

        with pytest.raises(HTTPException) as exc_info:
            await enroll_in_beta(request=request, current_user=mock_user_no_customer)

        assert exc_info.value.status_code == 400
        assert "Customer ID required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_enroll_in_beta_service_error(self, mock_user):
        """Test beta enrollment with service error."""
        from src.api.feature_flags_endpoints import enroll_in_beta

        mock_service = MagicMock()
        mock_service.enable_beta_features.side_effect = Exception("Enrollment failed")

        request = BetaEnrollmentRequest(accept_terms=True)

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await enroll_in_beta(request=request, current_user=mock_user)

        assert exc_info.value.status_code == 500


# =============================================================================
# Get Feature Tests
# =============================================================================


class TestGetFeature:
    """Test get single feature endpoint."""

    @pytest.mark.asyncio
    async def test_get_feature_success(self, mock_user, sample_feature):
        """Test getting a specific feature."""
        from src.api.feature_flags_endpoints import get_feature

        mock_service = MagicMock()
        mock_service.get_feature.return_value = sample_feature
        mock_service.is_enabled.return_value = True

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            result = await get_feature(
                feature_name="advanced_analytics", current_user=mock_user
            )

        assert result.name == "advanced_analytics"
        assert result.enabled is True

    @pytest.mark.asyncio
    async def test_get_feature_not_found(self, mock_user):
        """Test getting non-existent feature."""
        from src.api.feature_flags_endpoints import get_feature

        mock_service = MagicMock()
        mock_service.get_feature.return_value = None

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_feature(feature_name="nonexistent", current_user=mock_user)

        assert exc_info.value.status_code == 404
        assert "Feature not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_feature_service_error(self, mock_user):
        """Test getting feature with service error."""
        from src.api.feature_flags_endpoints import get_feature

        mock_service = MagicMock()
        mock_service.get_feature.side_effect = Exception("DB error")

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_feature(feature_name="any", current_user=mock_user)

        assert exc_info.value.status_code == 500


# =============================================================================
# Admin Override Tests
# =============================================================================


class TestAdminOverride:
    """Test admin feature override endpoint."""

    @pytest.mark.asyncio
    async def test_set_feature_override_enable(self, mock_admin_user, sample_feature):
        """Test enabling feature override."""
        from src.api.feature_flags_endpoints import set_feature_override

        mock_service = MagicMock()
        mock_service.get_feature.return_value = sample_feature
        mock_service.get_customer_overrides.return_value = None
        mock_service.set_customer_overrides.return_value = None

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            result = await set_feature_override(
                customer_id="cust-target",
                feature_name="advanced_analytics",
                enabled=True,
                current_user=mock_admin_user,
            )

        assert result["status"] == "success"
        assert result["customer_id"] == "cust-target"
        assert result["feature"] == "advanced_analytics"
        assert result["enabled"] is True
        mock_service.set_customer_overrides.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_feature_override_disable(self, mock_admin_user, sample_feature):
        """Test disabling feature override."""
        from src.api.feature_flags_endpoints import set_feature_override

        existing_overrides = CustomerFeatureOverrides(
            customer_id="cust-target",
            tier=FeatureTier.PROFESSIONAL,
            enabled_features={"advanced_analytics"},
            disabled_features=set(),
        )

        mock_service = MagicMock()
        mock_service.get_feature.return_value = sample_feature
        mock_service.get_customer_overrides.return_value = existing_overrides
        mock_service.set_customer_overrides.return_value = None

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            result = await set_feature_override(
                customer_id="cust-target",
                feature_name="advanced_analytics",
                enabled=False,
                current_user=mock_admin_user,
            )

        assert result["enabled"] is False

    @pytest.mark.asyncio
    async def test_set_feature_override_feature_not_found(self, mock_admin_user):
        """Test override for non-existent feature."""
        from src.api.feature_flags_endpoints import set_feature_override

        mock_service = MagicMock()
        mock_service.get_feature.return_value = None

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await set_feature_override(
                    customer_id="cust-target",
                    feature_name="nonexistent",
                    enabled=True,
                    current_user=mock_admin_user,
                )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_set_feature_override_service_error(
        self, mock_admin_user, sample_feature
    ):
        """Test override with service error."""
        from src.api.feature_flags_endpoints import set_feature_override

        mock_service = MagicMock()
        mock_service.get_feature.return_value = sample_feature
        mock_service.get_customer_overrides.side_effect = Exception("DB error")

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await set_feature_override(
                    customer_id="cust-target",
                    feature_name="advanced_analytics",
                    enabled=True,
                    current_user=mock_admin_user,
                )

        assert exc_info.value.status_code == 500


# =============================================================================
# Request/Response Model Tests
# =============================================================================


class TestModels:
    """Test Pydantic request/response models."""

    def test_feature_response_model(self):
        """Test FeatureResponse model."""
        response = FeatureResponse(
            name="test_feature",
            description="Test description",
            status="beta",
            min_tier="professional",
            enabled=True,
            enabled_by_default=False,
            requires_consent=True,
            rollout_percentage=50,
        )

        assert response.name == "test_feature"
        assert response.rollout_percentage == 50

    def test_feature_status_response_model(self):
        """Test FeatureStatusResponse model."""
        response = FeatureStatusResponse(
            features={"feature1": {"enabled": True}},
            tier="professional",
            beta_participant=True,
            enabled_count=1,
            total_count=5,
        )

        assert response.tier == "professional"
        assert response.beta_participant is True
        assert response.enabled_count == 1

    def test_beta_enrollment_request_defaults(self):
        """Test BetaEnrollmentRequest defaults."""
        request = BetaEnrollmentRequest()
        assert request.accept_terms is False
        assert request.features is None

    def test_beta_enrollment_request_with_features(self):
        """Test BetaEnrollmentRequest with specific features."""
        request = BetaEnrollmentRequest(
            accept_terms=True,
            features=["feature1", "feature2"],
        )
        assert request.accept_terms is True
        assert len(request.features) == 2

    def test_beta_enrollment_response_model(self):
        """Test BetaEnrollmentResponse model."""
        response = BetaEnrollmentResponse(
            enrolled=True,
            enabled_features=["feature1", "feature2"],
            message="Success",
        )

        assert response.enrolled is True
        assert len(response.enabled_features) == 2


# =============================================================================
# Tier Access Tests
# =============================================================================


class TestTierAccess:
    """Test tier-based feature access."""

    def test_starter_tier_access(self):
        """Test feature access for starter tier."""
        user = MagicMock()
        user.tier = "starter"
        tier = get_user_tier(user)

        assert tier == FeatureTier.STARTER

    def test_professional_tier_access(self):
        """Test feature access for professional tier."""
        user = MagicMock()
        user.tier = "professional"
        tier = get_user_tier(user)

        assert tier == FeatureTier.PROFESSIONAL

    def test_enterprise_tier_access(self):
        """Test feature access for enterprise tier."""
        user = MagicMock()
        user.tier = "enterprise"
        tier = get_user_tier(user)

        assert tier == FeatureTier.ENTERPRISE

    def test_government_tier_access(self):
        """Test feature access for government tier."""
        user = MagicMock()
        user.tier = "government"
        tier = get_user_tier(user)

        assert tier == FeatureTier.GOVERNMENT


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_feature_list(self, mock_user):
        """Test handling empty feature list."""
        from src.api.feature_flags_endpoints import list_features

        mock_service = MagicMock()
        mock_service.list_features.return_value = []

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            result = await list_features(status=None, current_user=mock_user)

        assert result == []

    @pytest.mark.asyncio
    async def test_user_without_tier_attribute(self, mock_user_no_customer):
        """Test handling user without tier attribute."""
        from src.api.feature_flags_endpoints import get_feature_status

        mock_service = MagicMock()
        mock_service.get_feature_flags_status.return_value = {}
        mock_service.get_customer_overrides.return_value = None

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            result = await get_feature_status(current_user=mock_user_no_customer)

        assert result.tier == "starter"

    @pytest.mark.asyncio
    async def test_override_toggle_feature_state(self, mock_admin_user, sample_feature):
        """Test toggling override state for same feature."""
        from src.api.feature_flags_endpoints import set_feature_override

        overrides = CustomerFeatureOverrides(
            customer_id="cust-target",
            tier=FeatureTier.PROFESSIONAL,
            enabled_features={"advanced_analytics"},
            disabled_features=set(),
        )

        mock_service = MagicMock()
        mock_service.get_feature.return_value = sample_feature
        mock_service.get_customer_overrides.return_value = overrides

        with patch(
            "src.api.feature_flags_endpoints.get_feature_flags",
            return_value=mock_service,
        ):
            # Disable the feature
            result = await set_feature_override(
                customer_id="cust-target",
                feature_name="advanced_analytics",
                enabled=False,
                current_user=mock_admin_user,
            )

        assert result["enabled"] is False
        # Verify the override was modified correctly
        call_args = mock_service.set_customer_overrides.call_args[0][0]
        assert "advanced_analytics" in call_args.disabled_features
        assert "advanced_analytics" not in call_args.enabled_features
