"""
Tests for Customer Feedback Service.

Validates feedback collection and management:
- Feedback submission (general, bug reports, feature requests)
- NPS survey collection and calculation
- Status updates and responses
- Aggregation and summaries
"""

import uuid

import pytest

from src.services.feedback_service import (
    FeedbackPriority,
    FeedbackService,
    FeedbackStatus,
    FeedbackType,
    get_feedback_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def feedback_service():
    """Create a fresh feedback service for each test."""
    return FeedbackService(mode="mock")


@pytest.fixture
def customer_id():
    """Sample customer ID."""
    return f"cust_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def user_id():
    """Sample user ID."""
    return f"user_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def user_email():
    """Sample user email."""
    return "test@example.com"


# =============================================================================
# Feedback Submission Tests
# =============================================================================


class TestFeedbackSubmission:
    """Tests for feedback submission."""

    @pytest.mark.asyncio
    async def test_submit_general_feedback(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test submitting general feedback."""
        feedback = await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.GENERAL,
            title="Great product!",
            description="I really enjoy using this product.",
        )

        assert feedback.feedback_id.startswith("fb_")
        assert feedback.customer_id == customer_id
        assert feedback.user_id == user_id
        assert feedback.user_email == user_email
        assert feedback.feedback_type == FeedbackType.GENERAL
        assert feedback.title == "Great product!"
        assert feedback.status == FeedbackStatus.NEW
        assert feedback.priority == FeedbackPriority.MEDIUM

    @pytest.mark.asyncio
    async def test_submit_bug_report(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test submitting a bug report gets higher priority."""
        feedback = await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.BUG_REPORT,
            title="Button not working",
            description="The submit button doesn't respond.",
        )

        assert feedback.feedback_type == FeedbackType.BUG_REPORT
        assert feedback.priority == FeedbackPriority.HIGH

    @pytest.mark.asyncio
    async def test_submit_feature_request(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test submitting a feature request."""
        feedback = await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.FEATURE_REQUEST,
            title="Add dark mode",
            description="Would love to have a dark mode option.",
            tags=["ui", "accessibility"],
        )

        assert feedback.feedback_type == FeedbackType.FEATURE_REQUEST
        assert "ui" in feedback.tags
        assert "accessibility" in feedback.tags

    @pytest.mark.asyncio
    async def test_submit_nps_survey(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test submitting NPS survey."""
        feedback = await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.NPS_SURVEY,
            title="NPS Survey Response",
            description="I would recommend this product.",
            nps_score=9,
        )

        assert feedback.feedback_type == FeedbackType.NPS_SURVEY
        assert feedback.nps_score == 9

    @pytest.mark.asyncio
    async def test_submit_nps_detractor_gets_high_priority(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test that low NPS scores get high priority."""
        feedback = await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.NPS_SURVEY,
            title="NPS Survey Response",
            description="Needs improvement.",
            nps_score=3,
        )

        assert feedback.nps_score == 3
        assert feedback.priority == FeedbackPriority.HIGH

    @pytest.mark.asyncio
    async def test_submit_feedback_with_metadata(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test submitting feedback with additional metadata."""
        feedback = await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.USABILITY,
            title="Navigation is confusing",
            description="Hard to find settings.",
            metadata={"feature": "navigation", "severity": "moderate"},
            page_url="/dashboard",
            browser_info="Chrome 120 on macOS",
        )

        assert feedback.metadata["feature"] == "navigation"
        assert feedback.page_url == "/dashboard"
        assert feedback.browser_info == "Chrome 120 on macOS"

    @pytest.mark.asyncio
    async def test_submit_nps_invalid_score(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test that invalid NPS scores are rejected."""
        with pytest.raises(ValueError, match="NPS score must be between 0 and 10"):
            await feedback_service.submit_feedback(
                customer_id=customer_id,
                user_id=user_id,
                user_email=user_email,
                feedback_type=FeedbackType.NPS_SURVEY,
                title="NPS Survey",
                description="Test",
                nps_score=11,
            )

    @pytest.mark.asyncio
    async def test_submit_nps_negative_score(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test that negative NPS scores are rejected."""
        with pytest.raises(ValueError, match="NPS score must be between 0 and 10"):
            await feedback_service.submit_feedback(
                customer_id=customer_id,
                user_id=user_id,
                user_email=user_email,
                feedback_type=FeedbackType.NPS_SURVEY,
                title="NPS Survey",
                description="Test",
                nps_score=-1,
            )


# =============================================================================
# Feedback Retrieval Tests
# =============================================================================


class TestFeedbackRetrieval:
    """Tests for feedback retrieval."""

    @pytest.mark.asyncio
    async def test_get_feedback(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test getting feedback by ID."""
        submitted = await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.GENERAL,
            title="Test",
            description="Test feedback",
        )

        retrieved = await feedback_service.get_feedback(submitted.feedback_id)

        assert retrieved is not None
        assert retrieved.feedback_id == submitted.feedback_id
        assert retrieved.title == "Test"

    @pytest.mark.asyncio
    async def test_get_feedback_not_found(self, feedback_service):
        """Test getting non-existent feedback."""
        result = await feedback_service.get_feedback("fb_nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_feedback(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test listing all feedback."""
        # Submit multiple feedback items
        for i in range(5):
            await feedback_service.submit_feedback(
                customer_id=customer_id,
                user_id=user_id,
                user_email=user_email,
                feedback_type=FeedbackType.GENERAL,
                title=f"Feedback {i}",
                description=f"Description {i}",
            )

        feedback_list, next_cursor = await feedback_service.list_feedback()

        assert len(feedback_list) == 5

    @pytest.mark.asyncio
    async def test_list_feedback_by_customer(
        self, feedback_service, user_id, user_email
    ):
        """Test filtering feedback by customer."""
        customer1 = "cust_1"
        customer2 = "cust_2"

        for i in range(3):
            await feedback_service.submit_feedback(
                customer_id=customer1,
                user_id=user_id,
                user_email=user_email,
                feedback_type=FeedbackType.GENERAL,
                title=f"Customer 1 Feedback {i}",
                description="Test",
            )

        for i in range(2):
            await feedback_service.submit_feedback(
                customer_id=customer2,
                user_id=user_id,
                user_email=user_email,
                feedback_type=FeedbackType.GENERAL,
                title=f"Customer 2 Feedback {i}",
                description="Test",
            )

        customer1_feedback, _ = await feedback_service.list_feedback(
            customer_id=customer1
        )
        customer2_feedback, _ = await feedback_service.list_feedback(
            customer_id=customer2
        )

        assert len(customer1_feedback) == 3
        assert len(customer2_feedback) == 2

    @pytest.mark.asyncio
    async def test_list_feedback_by_type(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test filtering feedback by type."""
        await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.BUG_REPORT,
            title="Bug",
            description="Test",
        )

        await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.FEATURE_REQUEST,
            title="Feature",
            description="Test",
        )

        bugs, _ = await feedback_service.list_feedback(
            feedback_type=FeedbackType.BUG_REPORT
        )
        features, _ = await feedback_service.list_feedback(
            feedback_type=FeedbackType.FEATURE_REQUEST
        )

        assert len(bugs) == 1
        assert len(features) == 1
        assert bugs[0].feedback_type == FeedbackType.BUG_REPORT

    @pytest.mark.asyncio
    async def test_list_feedback_by_status(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test filtering feedback by status."""
        feedback = await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.GENERAL,
            title="Test",
            description="Test",
        )

        # Update one to ACKNOWLEDGED
        await feedback_service.update_feedback_status(
            feedback.feedback_id, FeedbackStatus.ACKNOWLEDGED
        )

        # Add another
        await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.GENERAL,
            title="Test 2",
            description="Test",
        )

        new_feedback, _ = await feedback_service.list_feedback(
            status=FeedbackStatus.NEW
        )
        acknowledged, _ = await feedback_service.list_feedback(
            status=FeedbackStatus.ACKNOWLEDGED
        )

        assert len(new_feedback) == 1
        assert len(acknowledged) == 1

    @pytest.mark.asyncio
    async def test_list_feedback_pagination(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test feedback cursor-based pagination."""
        for i in range(10):
            await feedback_service.submit_feedback(
                customer_id=customer_id,
                user_id=user_id,
                user_email=user_email,
                feedback_type=FeedbackType.GENERAL,
                title=f"Feedback {i}",
                description="Test",
            )

        # Get first page
        first_page, next_cursor = await feedback_service.list_feedback(limit=5)
        # Get second page using cursor
        second_page, _ = await feedback_service.list_feedback(
            limit=5, cursor=next_cursor
        )

        assert len(first_page) == 5
        assert len(second_page) == 5
        # Verify no overlap between pages
        first_ids = {f.feedback_id for f in first_page}
        second_ids = {f.feedback_id for f in second_page}
        assert len(first_ids & second_ids) == 0


# =============================================================================
# Status Update Tests
# =============================================================================


class TestStatusUpdates:
    """Tests for feedback status updates."""

    @pytest.mark.asyncio
    async def test_update_status(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test updating feedback status."""
        feedback = await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.BUG_REPORT,
            title="Bug",
            description="Test",
        )

        updated = await feedback_service.update_feedback_status(
            feedback.feedback_id, FeedbackStatus.IN_PROGRESS
        )

        assert updated is not None
        assert updated.status == FeedbackStatus.IN_PROGRESS
        assert updated.updated_at is not None

    @pytest.mark.asyncio
    async def test_update_status_with_response(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test updating status with a response message."""
        feedback = await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.FEATURE_REQUEST,
            title="Feature",
            description="Test",
        )

        updated = await feedback_service.update_feedback_status(
            feedback.feedback_id,
            FeedbackStatus.PLANNED,
            response="We've added this to our roadmap!",
        )

        assert updated.status == FeedbackStatus.PLANNED
        assert updated.response == "We've added this to our roadmap!"

    @pytest.mark.asyncio
    async def test_update_status_completed_sets_resolved_at(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test that completing feedback sets resolved_at."""
        feedback = await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.BUG_REPORT,
            title="Bug",
            description="Test",
        )

        updated = await feedback_service.update_feedback_status(
            feedback.feedback_id, FeedbackStatus.COMPLETED
        )

        assert updated.status == FeedbackStatus.COMPLETED
        assert updated.resolved_at is not None

    @pytest.mark.asyncio
    async def test_update_status_wont_fix_sets_resolved_at(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test that won't fix status sets resolved_at."""
        feedback = await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.FEATURE_REQUEST,
            title="Feature",
            description="Test",
        )

        updated = await feedback_service.update_feedback_status(
            feedback.feedback_id, FeedbackStatus.WONT_FIX
        )

        assert updated.status == FeedbackStatus.WONT_FIX
        assert updated.resolved_at is not None

    @pytest.mark.asyncio
    async def test_update_status_not_found(self, feedback_service):
        """Test updating non-existent feedback."""
        result = await feedback_service.update_feedback_status(
            "fb_nonexistent", FeedbackStatus.ACKNOWLEDGED
        )
        assert result is None


# =============================================================================
# NPS Tests
# =============================================================================


class TestNPSResults:
    """Tests for NPS calculation."""

    @pytest.mark.asyncio
    async def test_get_nps_results(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test NPS calculation."""
        # Add some NPS responses
        scores = [10, 9, 8, 7, 6, 5, 10, 9]  # 3 promoters, 2 passives, 2 detractors

        for score in scores:
            await feedback_service.submit_feedback(
                customer_id=customer_id,
                user_id=user_id,
                user_email=user_email,
                feedback_type=FeedbackType.NPS_SURVEY,
                title="NPS",
                description="Survey response",
                nps_score=score,
            )

        nps = await feedback_service.get_nps_results()

        assert nps.total_responses == 8
        assert nps.promoters == 4  # 10, 9, 10, 9
        assert nps.passives == 2  # 8, 7
        assert nps.detractors == 2  # 6, 5
        # NPS = (4 - 2) / 8 * 100 = 25
        assert nps.nps_score == 25.0

    @pytest.mark.asyncio
    async def test_get_nps_results_no_responses(self, feedback_service):
        """Test NPS with no responses."""
        nps = await feedback_service.get_nps_results()

        assert nps.total_responses == 0
        assert nps.nps_score == 0.0
        assert nps.average_score == 0.0

    @pytest.mark.asyncio
    async def test_get_nps_results_filter_by_customer(
        self, feedback_service, user_id, user_email
    ):
        """Test NPS filtered by customer."""
        customer1 = "cust_1"
        customer2 = "cust_2"

        # Customer 1: all promoters
        for _ in range(3):
            await feedback_service.submit_feedback(
                customer_id=customer1,
                user_id=user_id,
                user_email=user_email,
                feedback_type=FeedbackType.NPS_SURVEY,
                title="NPS",
                description="Test",
                nps_score=10,
            )

        # Customer 2: all detractors
        for _ in range(2):
            await feedback_service.submit_feedback(
                customer_id=customer2,
                user_id=user_id,
                user_email=user_email,
                feedback_type=FeedbackType.NPS_SURVEY,
                title="NPS",
                description="Test",
                nps_score=3,
            )

        nps1 = await feedback_service.get_nps_results(customer_id=customer1)
        nps2 = await feedback_service.get_nps_results(customer_id=customer2)

        assert nps1.nps_score == 100.0  # All promoters
        assert nps2.nps_score == -100.0  # All detractors

    @pytest.mark.asyncio
    async def test_get_nps_results_average_score(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test NPS average score calculation."""
        scores = [10, 8, 6, 4]

        for score in scores:
            await feedback_service.submit_feedback(
                customer_id=customer_id,
                user_id=user_id,
                user_email=user_email,
                feedback_type=FeedbackType.NPS_SURVEY,
                title="NPS",
                description="Test",
                nps_score=score,
            )

        nps = await feedback_service.get_nps_results()

        # Average = (10 + 8 + 6 + 4) / 4 = 7
        assert nps.average_score == 7.0


# =============================================================================
# Feedback Summary Tests
# =============================================================================


class TestFeedbackSummary:
    """Tests for feedback summary."""

    @pytest.mark.asyncio
    async def test_get_feedback_summary(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test getting feedback summary."""
        # Submit various feedback types
        await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.BUG_REPORT,
            title="Bug 1",
            description="Test",
            tags=["critical"],
        )

        await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.FEATURE_REQUEST,
            title="Feature 1",
            description="Test",
            tags=["ui"],
        )

        await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.NPS_SURVEY,
            title="NPS",
            description="Test",
            nps_score=9,
        )

        summary = await feedback_service.get_feedback_summary()

        assert summary.total_feedback == 3
        assert "bug_report" in summary.by_type
        assert "feature_request" in summary.by_type
        assert "nps_survey" in summary.by_type
        assert "new" in summary.by_status
        assert len(summary.recent_feedback) <= 10

    @pytest.mark.asyncio
    async def test_get_feedback_summary_trending_tags(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test trending tags in summary."""
        tags = ["ui", "performance", "ui", "ui", "security"]

        for tag in tags:
            await feedback_service.submit_feedback(
                customer_id=customer_id,
                user_id=user_id,
                user_email=user_email,
                feedback_type=FeedbackType.GENERAL,
                title="Test",
                description="Test",
                tags=[tag],
            )

        summary = await feedback_service.get_feedback_summary()

        # "ui" should be most trending (3 occurrences)
        assert "ui" in summary.trending_tags
        # "ui" should be first (most common)
        assert summary.trending_tags[0] == "ui"

    @pytest.mark.asyncio
    async def test_get_feedback_summary_with_nps(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test summary includes NPS when available."""
        await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.NPS_SURVEY,
            title="NPS",
            description="Test",
            nps_score=10,
        )

        summary = await feedback_service.get_feedback_summary()

        assert summary.nps is not None
        assert summary.nps.total_responses == 1

    @pytest.mark.asyncio
    async def test_get_feedback_summary_no_nps(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test summary without NPS responses."""
        await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.GENERAL,
            title="General feedback",
            description="Test",
        )

        summary = await feedback_service.get_feedback_summary()

        assert summary.nps is None


# =============================================================================
# Singleton Tests
# =============================================================================


class TestFeedbackServiceSingleton:
    """Tests for singleton pattern."""

    def test_get_feedback_service(self):
        """Test getting feedback service singleton."""
        import src.services.feedback_service as module

        module._service = None

        service = get_feedback_service()

        assert service is not None
        assert isinstance(service, FeedbackService)

    def test_singleton_returns_same_instance(self):
        """Test that singleton returns same instance."""
        import src.services.feedback_service as module

        module._service = None

        service1 = get_feedback_service()
        service2 = get_feedback_service()

        assert service1 is service2


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_all_feedback_types(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test all feedback types can be submitted."""
        types = [
            FeedbackType.GENERAL,
            FeedbackType.BUG_REPORT,
            FeedbackType.FEATURE_REQUEST,
            FeedbackType.NPS_SURVEY,
            FeedbackType.USABILITY,
            FeedbackType.DOCUMENTATION,
            FeedbackType.PERFORMANCE,
        ]

        for fb_type in types:
            feedback = await feedback_service.submit_feedback(
                customer_id=customer_id,
                user_id=user_id,
                user_email=user_email,
                feedback_type=fb_type,
                title=f"Test {fb_type.value}",
                description="Test",
                nps_score=8 if fb_type == FeedbackType.NPS_SURVEY else None,
            )
            assert feedback.feedback_type == fb_type

    @pytest.mark.asyncio
    async def test_all_status_transitions(
        self, feedback_service, customer_id, user_id, user_email
    ):
        """Test all status values can be set."""
        feedback = await feedback_service.submit_feedback(
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=FeedbackType.BUG_REPORT,
            title="Bug",
            description="Test",
        )

        statuses = [
            FeedbackStatus.ACKNOWLEDGED,
            FeedbackStatus.IN_REVIEW,
            FeedbackStatus.PLANNED,
            FeedbackStatus.IN_PROGRESS,
            FeedbackStatus.COMPLETED,
        ]

        for status in statuses:
            updated = await feedback_service.update_feedback_status(
                feedback.feedback_id, status
            )
            assert updated.status == status

    def test_feedback_type_enum_values(self):
        """Test FeedbackType enum values."""
        assert FeedbackType.GENERAL.value == "general"
        assert FeedbackType.BUG_REPORT.value == "bug_report"
        assert FeedbackType.FEATURE_REQUEST.value == "feature_request"
        assert FeedbackType.NPS_SURVEY.value == "nps_survey"

    def test_feedback_status_enum_values(self):
        """Test FeedbackStatus enum values."""
        assert FeedbackStatus.NEW.value == "new"
        assert FeedbackStatus.ACKNOWLEDGED.value == "acknowledged"
        assert FeedbackStatus.COMPLETED.value == "completed"
        assert FeedbackStatus.WONT_FIX.value == "wont_fix"

    def test_feedback_priority_enum_values(self):
        """Test FeedbackPriority enum values."""
        assert FeedbackPriority.LOW.value == "low"
        assert FeedbackPriority.MEDIUM.value == "medium"
        assert FeedbackPriority.HIGH.value == "high"
        assert FeedbackPriority.CRITICAL.value == "critical"
