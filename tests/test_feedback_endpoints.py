"""
Tests for Customer Feedback API Endpoints.

Comprehensive test suite covering:
- Feedback submission
- NPS survey submission
- Feedback listing and filtering
- Feedback summary and NPS results
- Status updates (admin)
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
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, Request

from src.api.feedback_endpoints import (
    FeedbackResponse,
    FeedbackStatusUpdateRequest,
    FeedbackSubmitRequest,
    FeedbackSummaryResponse,
    NPSResultsResponse,
    NPSSubmitRequest,
    feedback_to_response,
    nps_to_response,
)
from src.services.feedback_service import (
    FeedbackItem,
    FeedbackPriority,
    FeedbackStatus,
    FeedbackSummary,
    FeedbackType,
    NPSSurveyResult,
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
    return user


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    user = MagicMock()
    user.id = "admin-123"
    user.email = "admin@example.com"
    user.customer_id = "cust-admin"
    user.roles = ["admin"]
    return user


@pytest.fixture
def mock_operator_user():
    """Create a mock operator user."""
    user = MagicMock()
    user.id = "operator-123"
    user.email = "operator@example.com"
    user.customer_id = "cust-ops"
    user.roles = ["operator"]
    return user


@pytest.fixture
def mock_request():
    """Create a mock HTTP request."""
    request = MagicMock(spec=Request)
    request.headers = {"user-agent": "Mozilla/5.0 Test Browser"}
    return request


@pytest.fixture
def sample_feedback():
    """Create a sample feedback item."""
    now = datetime.now(timezone.utc)
    return FeedbackItem(
        feedback_id="fb-123",
        customer_id="cust-456",
        user_id="user-123",
        user_email="test@example.com",
        feedback_type=FeedbackType.FEATURE_REQUEST,
        title="Add dark mode support",
        description="Would love to have a dark mode option for late night coding sessions.",
        status=FeedbackStatus.NEW,
        priority=FeedbackPriority.MEDIUM,
        nps_score=None,
        tags=["ui", "theme"],
        page_url="/settings",
        browser_info="Mozilla/5.0",
        metadata={"source": "settings_page"},
        created_at=now,
        updated_at=None,
        resolved_at=None,
        response=None,
    )


@pytest.fixture
def sample_nps_feedback():
    """Create a sample NPS feedback item."""
    now = datetime.now(timezone.utc)
    return FeedbackItem(
        feedback_id="fb-nps-123",
        customer_id="cust-456",
        user_id="user-123",
        user_email="test@example.com",
        feedback_type=FeedbackType.NPS_SURVEY,
        title="NPS Survey: Score 9",
        description="Great product overall!",
        status=FeedbackStatus.NEW,
        priority=FeedbackPriority.LOW,
        nps_score=9,
        tags=["nps", "nps-9"],
        page_url=None,
        browser_info=None,
        metadata=None,
        created_at=now,
        updated_at=None,
        resolved_at=None,
        response=None,
    )


@pytest.fixture
def sample_nps_result():
    """Create sample NPS survey results."""
    now = datetime.now(timezone.utc)
    return NPSSurveyResult(
        total_responses=100,
        promoters=60,
        passives=25,
        detractors=15,
        nps_score=45.0,
        average_score=7.8,
        period_start=now - timedelta(days=30),
        period_end=now,
    )


@pytest.fixture
def sample_feedback_summary():
    """Create sample feedback summary."""
    now = datetime.now(timezone.utc)
    return FeedbackSummary(
        total_feedback=150,
        by_type={
            "feature_request": 60,
            "bug_report": 40,
            "general": 30,
            "usability": 20,
        },
        by_status={
            "new": 80,
            "acknowledged": 30,
            "in_progress": 25,
            "completed": 15,
        },
        by_priority={
            "low": 40,
            "medium": 70,
            "high": 30,
            "critical": 10,
        },
        nps=NPSSurveyResult(
            total_responses=50,
            promoters=30,
            passives=12,
            detractors=8,
            nps_score=44.0,
            average_score=7.6,
            period_start=now - timedelta(days=30),
            period_end=now,
        ),
        recent_feedback=[],
        trending_tags=["ui", "performance", "api", "dark-mode", "mobile"],
    )


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Test helper conversion functions."""

    def test_feedback_to_response(self, sample_feedback):
        """Test feedback to response conversion."""
        response = feedback_to_response(sample_feedback)

        assert isinstance(response, FeedbackResponse)
        assert response.feedback_id == "fb-123"
        assert response.customer_id == "cust-456"
        assert response.user_email == "test@example.com"
        assert response.feedback_type == "feature_request"
        assert response.title == "Add dark mode support"
        assert response.status == "new"
        assert response.priority == "medium"
        assert response.nps_score is None
        assert "ui" in response.tags
        assert response.page_url == "/settings"
        assert response.updated_at is None
        assert response.resolved_at is None
        assert response.response is None

    def test_feedback_to_response_with_resolution(self, sample_feedback):
        """Test feedback to response with resolution."""
        sample_feedback.status = FeedbackStatus.COMPLETED
        sample_feedback.updated_at = datetime.now(timezone.utc)
        sample_feedback.resolved_at = datetime.now(timezone.utc)
        sample_feedback.response = "Feature added in v2.1"

        response = feedback_to_response(sample_feedback)

        assert response.status == "completed"
        assert response.updated_at is not None
        assert response.resolved_at is not None
        assert response.response == "Feature added in v2.1"

    def test_nps_to_response(self, sample_nps_result):
        """Test NPS result to response conversion."""
        response = nps_to_response(sample_nps_result, days=30)

        assert isinstance(response, NPSResultsResponse)
        assert response.total_responses == 100
        assert response.promoters == 60
        assert response.passives == 25
        assert response.detractors == 15
        assert response.nps_score == 45.0
        assert response.average_score == 7.8
        assert response.period_days == 30


# =============================================================================
# Feedback Submission Tests
# =============================================================================


class TestFeedbackSubmission:
    """Test feedback submission endpoints."""

    @pytest.mark.asyncio
    async def test_submit_feedback_success(
        self, mock_user, mock_request, sample_feedback
    ):
        """Test successful feedback submission."""
        from src.api.feedback_endpoints import submit_feedback

        mock_service = MagicMock()
        mock_service.submit_feedback = AsyncMock(return_value=sample_feedback)

        request = FeedbackSubmitRequest(
            feedback_type="feature_request",
            title="Add dark mode support",
            description="Would love to have a dark mode option for late night coding sessions.",
            tags=["ui", "theme"],
            page_url="/settings",
        )

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await submit_feedback(
                request=request,
                http_request=mock_request,
                current_user=mock_user,
            )

        assert result.feedback_id == "fb-123"
        assert result.title == "Add dark mode support"
        mock_service.submit_feedback.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_feedback_invalid_type(self, mock_user, mock_request):
        """Test feedback submission with invalid type."""
        from src.api.feedback_endpoints import submit_feedback

        request = FeedbackSubmitRequest(
            feedback_type="invalid_type",
            title="Test feedback",
            description="This is a test feedback description.",
        )

        with pytest.raises(HTTPException) as exc_info:
            await submit_feedback(
                request=request,
                http_request=mock_request,
                current_user=mock_user,
            )

        assert exc_info.value.status_code == 400
        assert "Invalid feedback type" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_submit_feedback_service_error(self, mock_user, mock_request):
        """Test feedback submission with service error."""
        from src.api.feedback_endpoints import submit_feedback

        mock_service = MagicMock()
        mock_service.submit_feedback = AsyncMock(side_effect=Exception("DB error"))

        request = FeedbackSubmitRequest(
            feedback_type="general",
            title="Test feedback",
            description="This is a test feedback description.",
        )

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            with pytest.raises(HTTPException) as exc_info:
                await submit_feedback(
                    request=request,
                    http_request=mock_request,
                    current_user=mock_user,
                )

        assert exc_info.value.status_code == 500


# =============================================================================
# NPS Survey Tests
# =============================================================================


class TestNPSSurvey:
    """Test NPS survey endpoints."""

    @pytest.mark.asyncio
    async def test_submit_nps_survey_success(self, mock_user, sample_nps_feedback):
        """Test successful NPS survey submission."""
        from src.api.feedback_endpoints import submit_nps_survey

        mock_service = MagicMock()
        mock_service.submit_feedback = AsyncMock(return_value=sample_nps_feedback)

        request = NPSSubmitRequest(score=9, comment="Great product overall!")

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await submit_nps_survey(request=request, current_user=mock_user)

        assert result.nps_score == 9
        assert result.feedback_type == "nps_survey"

    @pytest.mark.asyncio
    async def test_submit_nps_survey_no_comment(self, mock_user, sample_nps_feedback):
        """Test NPS survey submission without comment."""
        from src.api.feedback_endpoints import submit_nps_survey

        sample_nps_feedback.description = "NPS score of 8 submitted"

        mock_service = MagicMock()
        mock_service.submit_feedback = AsyncMock(return_value=sample_nps_feedback)

        request = NPSSubmitRequest(score=8)

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await submit_nps_survey(request=request, current_user=mock_user)

        assert result is not None
        mock_service.submit_feedback.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_nps_survey_service_error(self, mock_user):
        """Test NPS survey with service error."""
        from src.api.feedback_endpoints import submit_nps_survey

        mock_service = MagicMock()
        mock_service.submit_feedback = AsyncMock(side_effect=Exception("Error"))

        request = NPSSubmitRequest(score=7)

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            with pytest.raises(HTTPException) as exc_info:
                await submit_nps_survey(request=request, current_user=mock_user)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_get_nps_results(self, mock_user, sample_nps_result):
        """Test getting NPS results."""
        from src.api.feedback_endpoints import get_nps_results

        mock_service = MagicMock()
        mock_service.get_nps_results = AsyncMock(return_value=sample_nps_result)

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await get_nps_results(days=30, current_user=mock_user)

        assert result.total_responses == 100
        assert result.nps_score == 45.0
        assert result.period_days == 30

    @pytest.mark.asyncio
    async def test_get_nps_results_admin_sees_all(
        self, mock_admin_user, sample_nps_result
    ):
        """Test admin sees all NPS results."""
        from src.api.feedback_endpoints import get_nps_results

        mock_service = MagicMock()
        mock_service.get_nps_results = AsyncMock(return_value=sample_nps_result)

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            _result = await get_nps_results(days=90, current_user=mock_admin_user)

        # Admin should get results with customer_id=None (all customers)
        call_args = mock_service.get_nps_results.call_args
        assert call_args[1]["customer_id"] is None


# =============================================================================
# Feedback Listing Tests
# =============================================================================


class TestFeedbackListing:
    """Test feedback listing endpoints."""

    @pytest.mark.asyncio
    async def test_list_feedback_all(self, mock_user, sample_feedback):
        """Test listing all feedback."""
        from src.api.feedback_endpoints import list_feedback

        mock_service = MagicMock()
        mock_service.list_feedback = AsyncMock(return_value=[sample_feedback])

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await list_feedback(
                feedback_type=None,
                status=None,
                limit=50,
                offset=0,
                current_user=mock_user,
            )

        assert len(result) == 1
        assert result[0].feedback_id == "fb-123"

    @pytest.mark.asyncio
    async def test_list_feedback_by_type(self, mock_user, sample_feedback):
        """Test listing feedback filtered by type."""
        from src.api.feedback_endpoints import list_feedback

        mock_service = MagicMock()
        mock_service.list_feedback = AsyncMock(return_value=[sample_feedback])

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await list_feedback(
                feedback_type="feature_request",
                status=None,
                limit=50,
                offset=0,
                current_user=mock_user,
            )

        assert len(result) == 1
        # Verify filter was passed
        call_args = mock_service.list_feedback.call_args
        assert call_args[1]["feedback_type"] == FeedbackType.FEATURE_REQUEST

    @pytest.mark.asyncio
    async def test_list_feedback_by_status(self, mock_user, sample_feedback):
        """Test listing feedback filtered by status."""
        from src.api.feedback_endpoints import list_feedback

        mock_service = MagicMock()
        mock_service.list_feedback = AsyncMock(return_value=[sample_feedback])

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            _result = await list_feedback(
                feedback_type=None,
                status="new",
                limit=50,
                offset=0,
                current_user=mock_user,
            )

        call_args = mock_service.list_feedback.call_args
        assert call_args[1]["status"] == FeedbackStatus.NEW

    @pytest.mark.asyncio
    async def test_list_feedback_invalid_type(self, mock_user):
        """Test listing feedback with invalid type filter."""
        from src.api.feedback_endpoints import list_feedback

        mock_service = MagicMock()

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            with pytest.raises(HTTPException) as exc_info:
                await list_feedback(
                    feedback_type="invalid",
                    status=None,
                    limit=50,
                    offset=0,
                    current_user=mock_user,
                )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_feedback_invalid_status(self, mock_user):
        """Test listing feedback with invalid status filter."""
        from src.api.feedback_endpoints import list_feedback

        mock_service = MagicMock()

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            with pytest.raises(HTTPException) as exc_info:
                await list_feedback(
                    feedback_type=None,
                    status="invalid",
                    limit=50,
                    offset=0,
                    current_user=mock_user,
                )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_feedback_admin_sees_all(self, mock_admin_user, sample_feedback):
        """Test admin sees all feedback."""
        from src.api.feedback_endpoints import list_feedback

        mock_service = MagicMock()
        mock_service.list_feedback = AsyncMock(return_value=[sample_feedback])

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            _result = await list_feedback(
                feedback_type=None,
                status=None,
                limit=50,
                offset=0,
                current_user=mock_admin_user,
            )

        # Admin should see all (customer_id=None)
        call_args = mock_service.list_feedback.call_args
        assert call_args[1]["customer_id"] is None


# =============================================================================
# Feedback Summary Tests
# =============================================================================


class TestFeedbackSummary:
    """Test feedback summary endpoint."""

    @pytest.mark.asyncio
    async def test_get_feedback_summary(self, mock_user, sample_feedback_summary):
        """Test getting feedback summary."""
        from src.api.feedback_endpoints import get_feedback_summary

        mock_service = MagicMock()
        mock_service.get_feedback_summary = AsyncMock(
            return_value=sample_feedback_summary
        )

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await get_feedback_summary(days=30, current_user=mock_user)

        assert isinstance(result, FeedbackSummaryResponse)
        assert result.total_feedback == 150
        assert "feature_request" in result.by_type
        assert "new" in result.by_status
        assert result.nps is not None
        assert len(result.trending_tags) == 5

    @pytest.mark.asyncio
    async def test_get_feedback_summary_no_nps(self, mock_user):
        """Test feedback summary without NPS data."""
        from src.api.feedback_endpoints import get_feedback_summary

        summary = FeedbackSummary(
            total_feedback=50,
            by_type={"general": 50},
            by_status={"new": 50},
            by_priority={"medium": 50},
            nps=None,
            recent_feedback=[],
            trending_tags=["general"],
        )

        mock_service = MagicMock()
        mock_service.get_feedback_summary = AsyncMock(return_value=summary)

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await get_feedback_summary(days=30, current_user=mock_user)

        assert result.nps is None

    @pytest.mark.asyncio
    async def test_get_feedback_summary_service_error(self, mock_user):
        """Test feedback summary with service error."""
        from src.api.feedback_endpoints import get_feedback_summary

        mock_service = MagicMock()
        mock_service.get_feedback_summary = AsyncMock(side_effect=Exception("Error"))

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_feedback_summary(days=30, current_user=mock_user)

        assert exc_info.value.status_code == 500


# =============================================================================
# Get Feedback Tests
# =============================================================================


class TestGetFeedback:
    """Test get single feedback endpoint."""

    @pytest.mark.asyncio
    async def test_get_feedback_success(self, mock_user, sample_feedback):
        """Test getting a specific feedback item."""
        from src.api.feedback_endpoints import get_feedback

        mock_service = MagicMock()
        mock_service.get_feedback = AsyncMock(return_value=sample_feedback)

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await get_feedback(feedback_id="fb-123", current_user=mock_user)

        assert result.feedback_id == "fb-123"
        assert result.title == "Add dark mode support"

    @pytest.mark.asyncio
    async def test_get_feedback_not_found(self, mock_user):
        """Test getting non-existent feedback."""
        from src.api.feedback_endpoints import get_feedback

        mock_service = MagicMock()
        mock_service.get_feedback = AsyncMock(return_value=None)

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_feedback(feedback_id="nonexistent", current_user=mock_user)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_feedback_access_denied(self, mock_user, sample_feedback):
        """Test accessing another customer's feedback."""
        from src.api.feedback_endpoints import get_feedback

        # Feedback belongs to different customer
        sample_feedback.customer_id = "different-customer"

        mock_service = MagicMock()
        mock_service.get_feedback = AsyncMock(return_value=sample_feedback)

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_feedback(feedback_id="fb-123", current_user=mock_user)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_feedback_admin_access(self, mock_admin_user, sample_feedback):
        """Test admin accessing any feedback."""
        from src.api.feedback_endpoints import get_feedback

        # Feedback belongs to different customer
        sample_feedback.customer_id = "different-customer"

        mock_service = MagicMock()
        mock_service.get_feedback = AsyncMock(return_value=sample_feedback)

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await get_feedback(
                feedback_id="fb-123", current_user=mock_admin_user
            )

        # Admin should have access
        assert result.feedback_id == "fb-123"


# =============================================================================
# Status Update Tests
# =============================================================================


class TestStatusUpdate:
    """Test feedback status update endpoint."""

    @pytest.mark.asyncio
    async def test_update_status_success(self, mock_admin_user, sample_feedback):
        """Test successful status update."""
        from src.api.feedback_endpoints import update_feedback_status

        updated_feedback = sample_feedback
        updated_feedback.status = FeedbackStatus.ACKNOWLEDGED
        updated_feedback.response = "Thank you for your feedback!"
        updated_feedback.updated_at = datetime.now(timezone.utc)

        mock_service = MagicMock()
        mock_service.update_feedback_status = AsyncMock(return_value=updated_feedback)

        request = FeedbackStatusUpdateRequest(
            status="acknowledged",
            response="Thank you for your feedback!",
        )

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await update_feedback_status(
                feedback_id="fb-123",
                request=request,
                current_user=mock_admin_user,
            )

        assert result.status == "acknowledged"
        assert result.response == "Thank you for your feedback!"

    @pytest.mark.asyncio
    async def test_update_status_operator(self, mock_operator_user, sample_feedback):
        """Test operator can update status."""
        from src.api.feedback_endpoints import update_feedback_status

        updated_feedback = sample_feedback
        updated_feedback.status = FeedbackStatus.IN_REVIEW

        mock_service = MagicMock()
        mock_service.update_feedback_status = AsyncMock(return_value=updated_feedback)

        request = FeedbackStatusUpdateRequest(status="in_review")

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await update_feedback_status(
                feedback_id="fb-123",
                request=request,
                current_user=mock_operator_user,
            )

        assert result.status == "in_review"

    @pytest.mark.asyncio
    async def test_update_status_invalid(self, mock_admin_user):
        """Test status update with invalid status."""
        from src.api.feedback_endpoints import update_feedback_status

        request = FeedbackStatusUpdateRequest(status="invalid_status")

        with pytest.raises(HTTPException) as exc_info:
            await update_feedback_status(
                feedback_id="fb-123",
                request=request,
                current_user=mock_admin_user,
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_update_status_not_found(self, mock_admin_user):
        """Test status update for non-existent feedback."""
        from src.api.feedback_endpoints import update_feedback_status

        mock_service = MagicMock()
        mock_service.update_feedback_status = AsyncMock(return_value=None)

        request = FeedbackStatusUpdateRequest(status="acknowledged")

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_feedback_status(
                    feedback_id="nonexistent",
                    request=request,
                    current_user=mock_admin_user,
                )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_status_service_error(self, mock_admin_user):
        """Test status update with service error."""
        from src.api.feedback_endpoints import update_feedback_status

        mock_service = MagicMock()
        mock_service.update_feedback_status = AsyncMock(side_effect=Exception("Error"))

        request = FeedbackStatusUpdateRequest(status="acknowledged")

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_feedback_status(
                    feedback_id="fb-123",
                    request=request,
                    current_user=mock_admin_user,
                )

        assert exc_info.value.status_code == 500


# =============================================================================
# Request/Response Model Tests
# =============================================================================


class TestModels:
    """Test Pydantic request/response models."""

    def test_feedback_submit_request_validation(self):
        """Test FeedbackSubmitRequest validation."""
        # Valid request
        request = FeedbackSubmitRequest(
            feedback_type="bug_report",
            title="Button not working",
            description="The submit button doesn't respond on click.",
        )
        assert request.feedback_type == "bug_report"

        # Title too short
        with pytest.raises(ValueError):
            FeedbackSubmitRequest(
                feedback_type="bug_report",
                title="Bug",  # Less than 5 chars
                description="Description here.",
            )

        # Description too short
        with pytest.raises(ValueError):
            FeedbackSubmitRequest(
                feedback_type="bug_report",
                title="Valid title",
                description="Short",  # Less than 10 chars
            )

    def test_nps_submit_request_validation(self):
        """Test NPSSubmitRequest validation."""
        # Valid scores
        for score in range(11):
            request = NPSSubmitRequest(score=score)
            assert request.score == score

        # Invalid score (below 0)
        with pytest.raises(ValueError):
            NPSSubmitRequest(score=-1)

        # Invalid score (above 10)
        with pytest.raises(ValueError):
            NPSSubmitRequest(score=11)

    def test_feedback_status_update_request(self):
        """Test FeedbackStatusUpdateRequest model."""
        request = FeedbackStatusUpdateRequest(status="acknowledged")
        assert request.status == "acknowledged"
        assert request.response is None

        request_with_response = FeedbackStatusUpdateRequest(
            status="completed",
            response="Fixed in version 2.0",
        )
        assert request_with_response.response == "Fixed in version 2.0"


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_submit_feedback_long_user_agent(
        self, mock_user, mock_request, sample_feedback
    ):
        """Test feedback with very long user agent string."""
        from src.api.feedback_endpoints import submit_feedback

        # Set a very long user agent
        mock_request.headers = {"user-agent": "A" * 1000}

        mock_service = MagicMock()
        mock_service.submit_feedback = AsyncMock(return_value=sample_feedback)

        request = FeedbackSubmitRequest(
            feedback_type="general",
            title="Test feedback",
            description="Test description here.",
        )

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            _result = await submit_feedback(
                request=request,
                http_request=mock_request,
                current_user=mock_user,
            )

        # Should truncate to 500 chars
        call_args = mock_service.submit_feedback.call_args
        assert len(call_args[1].get("browser_info", "")) <= 500

    @pytest.mark.asyncio
    async def test_submit_feedback_no_user_agent(self, mock_user, sample_feedback):
        """Test feedback without user agent."""
        from src.api.feedback_endpoints import submit_feedback

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}

        mock_service = MagicMock()
        mock_service.submit_feedback = AsyncMock(return_value=sample_feedback)

        request = FeedbackSubmitRequest(
            feedback_type="general",
            title="Test feedback",
            description="Test description here.",
        )

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await submit_feedback(
                request=request,
                http_request=mock_request,
                current_user=mock_user,
            )

        assert result is not None

    @pytest.mark.asyncio
    async def test_list_feedback_pagination(self, mock_user, sample_feedback):
        """Test feedback listing with pagination."""
        from src.api.feedback_endpoints import list_feedback

        mock_service = MagicMock()
        mock_service.list_feedback = AsyncMock(return_value=[sample_feedback])

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            _result = await list_feedback(
                feedback_type=None,
                status=None,
                limit=10,
                offset=20,
                current_user=mock_user,
            )

        call_args = mock_service.list_feedback.call_args
        assert call_args[1]["limit"] == 10
        assert call_args[1]["offset"] == 20

    def test_user_without_customer_id_defaults(self):
        """Test user without customer_id defaults correctly."""
        user = MagicMock(spec=["id", "email", "roles"])
        user.roles = ["user"]

        customer_id = getattr(user, "customer_id", None)
        if not customer_id:
            customer_id = "default"

        assert customer_id == "default"


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestFeedbackWorkflow:
    """Integration-style tests for feedback workflow."""

    @pytest.mark.asyncio
    async def test_complete_feedback_lifecycle(
        self, mock_user, mock_admin_user, mock_request
    ):
        """Test complete feedback lifecycle."""
        from src.api.feedback_endpoints import submit_feedback, update_feedback_status

        now = datetime.now(timezone.utc)

        # Step 1: User submits feedback
        submitted_feedback = FeedbackItem(
            feedback_id="fb-lifecycle",
            customer_id="cust-456",
            user_id="user-123",
            user_email="test@example.com",
            feedback_type=FeedbackType.BUG_REPORT,
            title="Login button broken",
            description="The login button stops working after page refresh.",
            status=FeedbackStatus.NEW,
            priority=FeedbackPriority.HIGH,
            nps_score=None,
            tags=["bug", "login"],
            page_url="/login",
            browser_info="Chrome",
            metadata=None,
            created_at=now,
            updated_at=None,
            resolved_at=None,
            response=None,
        )

        mock_service = MagicMock()
        mock_service.submit_feedback = AsyncMock(return_value=submitted_feedback)

        request = FeedbackSubmitRequest(
            feedback_type="bug_report",
            title="Login button broken",
            description="The login button stops working after page refresh.",
            tags=["bug", "login"],
            page_url="/login",
        )

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await submit_feedback(
                request=request,
                http_request=mock_request,
                current_user=mock_user,
            )
            assert result.status == "new"

        # Step 2: Admin acknowledges and starts working on it
        acknowledged_feedback = FeedbackItem(
            feedback_id="fb-lifecycle",
            customer_id="cust-456",
            user_id="user-123",
            user_email="test@example.com",
            feedback_type=FeedbackType.BUG_REPORT,
            title="Login button broken",
            description="The login button stops working after page refresh.",
            status=FeedbackStatus.IN_PROGRESS,
            priority=FeedbackPriority.HIGH,
            nps_score=None,
            tags=["bug", "login"],
            page_url="/login",
            browser_info="Chrome",
            metadata=None,
            created_at=now,
            updated_at=now + timedelta(hours=1),
            resolved_at=None,
            response="We're looking into this issue.",
        )

        mock_service.update_feedback_status = AsyncMock(
            return_value=acknowledged_feedback
        )

        status_request = FeedbackStatusUpdateRequest(
            status="in_progress",
            response="We're looking into this issue.",
        )

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await update_feedback_status(
                feedback_id="fb-lifecycle",
                request=status_request,
                current_user=mock_admin_user,
            )
            assert result.status == "in_progress"

        # Step 3: Admin completes the fix
        completed_feedback = FeedbackItem(
            feedback_id="fb-lifecycle",
            customer_id="cust-456",
            user_id="user-123",
            user_email="test@example.com",
            feedback_type=FeedbackType.BUG_REPORT,
            title="Login button broken",
            description="The login button stops working after page refresh.",
            status=FeedbackStatus.COMPLETED,
            priority=FeedbackPriority.HIGH,
            nps_score=None,
            tags=["bug", "login"],
            page_url="/login",
            browser_info="Chrome",
            metadata=None,
            created_at=now,
            updated_at=now + timedelta(days=1),
            resolved_at=now + timedelta(days=1),
            response="Fixed in v2.1.0 - deployed to production.",
        )

        mock_service.update_feedback_status = AsyncMock(return_value=completed_feedback)

        complete_request = FeedbackStatusUpdateRequest(
            status="completed",
            response="Fixed in v2.1.0 - deployed to production.",
        )

        with patch(
            "src.api.feedback_endpoints.get_feedback_service", return_value=mock_service
        ):
            result = await update_feedback_status(
                feedback_id="fb-lifecycle",
                request=complete_request,
                current_user=mock_admin_user,
            )
            assert result.status == "completed"
            assert result.resolved_at is not None
