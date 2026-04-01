"""
Tests for Onboarding API Endpoints.

Tests FastAPI endpoints for onboarding state management including:
- State retrieval and updates
- Tour operations
- Checklist operations
- Tooltip dismissal
- Video progress
"""

import platform
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Run tests in isolated subprocesses to prevent state pollution on macOS
# pytest-forked has issues on Linux CI, so only use it on macOS
if platform.system() == "Darwin":
    pytestmark = pytest.mark.forked

# Clear any cached modules to ensure fresh router state
for mod in list(sys.modules.keys()):
    if mod.startswith("src.api.onboarding") or mod.startswith(
        "src.services.onboarding"
    ):
        del sys.modules[mod]

from src.api.onboarding_endpoints import router
from src.services.onboarding_service import (
    VIDEO_CATALOG,
    OnboardingService,
    set_onboarding_service,
)

# =============================================================================
# Test App Setup
# =============================================================================


@pytest.fixture
def mock_service():
    """Create a mock onboarding service."""
    service = MagicMock(spec=OnboardingService)

    # Default state
    default_state = {
        "user_id": "test-user-001",
        "organization_id": "test-org-001",
        "welcome_modal_dismissed": False,
        "welcome_modal_dismissed_at": None,
        "tour_completed": False,
        "tour_step": 0,
        "tour_started_at": None,
        "tour_completed_at": None,
        "tour_skipped": False,
        "checklist_dismissed": False,
        "checklist_steps": {
            "connect_repository": False,
            "configure_analysis": False,
            "run_first_scan": False,
            "review_vulnerabilities": False,
            "invite_team_member": False,
        },
        "checklist_started_at": None,
        "checklist_completed_at": None,
        "dismissed_tooltips": [],
        "video_progress": {},
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    }

    service.get_state = AsyncMock(return_value=default_state)
    service.update_state = AsyncMock(return_value=default_state)
    service.dismiss_modal = AsyncMock()
    service.start_tour = AsyncMock()
    service.complete_tour_step = AsyncMock()
    service.complete_tour = AsyncMock()
    service.skip_tour = AsyncMock()
    service.dismiss_tooltip = AsyncMock()
    service.complete_checklist_item = AsyncMock(return_value=False)
    service.dismiss_checklist = AsyncMock()
    service.update_video_progress = AsyncMock()
    service.get_video_catalog = AsyncMock(return_value=VIDEO_CATALOG)
    service.reset_state = AsyncMock()

    return service


@pytest.fixture
def app(mock_service):
    """Create test FastAPI app with mocked service."""
    test_app = FastAPI()
    test_app.include_router(router)

    # Override the service dependency
    set_onboarding_service(mock_service)

    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# =============================================================================
# State Endpoint Tests
# =============================================================================


class TestStateEndpoints:
    """Test state-related endpoints."""

    def test_get_state(self, client, mock_service):
        """Test getting onboarding state."""
        response = client.get("/api/v1/onboarding/state")

        assert response.status_code == 200
        data = response.json()
        assert data["welcome_modal_dismissed"] is False
        assert data["tour_completed"] is False
        mock_service.get_state.assert_called_once()

    def test_update_state(self, client, mock_service):
        """Test updating onboarding state."""
        updated_state = {
            "user_id": "test-user-001",
            "organization_id": "test-org-001",
            "welcome_modal_dismissed": True,
            "tour_step": 2,
            "tour_completed": False,
            "tour_skipped": False,
            "checklist_dismissed": False,
            "checklist_steps": {
                "connect_repository": False,
                "configure_analysis": False,
                "run_first_scan": False,
                "review_vulnerabilities": False,
                "invite_team_member": False,
            },
            "dismissed_tooltips": [],
            "video_progress": {},
            "created_at": "2025-01-01T00:00:00+00:00",
            "updated_at": "2025-01-01T00:00:00+00:00",
        }
        mock_service.update_state.return_value = updated_state

        response = client.patch(
            "/api/v1/onboarding/state",
            json={"welcome_modal_dismissed": True, "tour_step": 2},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["welcome_modal_dismissed"] is True
        mock_service.update_state.assert_called_once()


# =============================================================================
# Modal Endpoint Tests
# =============================================================================


class TestModalEndpoints:
    """Test modal-related endpoints."""

    def test_dismiss_modal(self, client, mock_service):
        """Test dismissing the welcome modal."""
        response = client.post("/api/v1/onboarding/modal/dismiss")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_service.dismiss_modal.assert_called_once()


# =============================================================================
# Tour Endpoint Tests
# =============================================================================


class TestTourEndpoints:
    """Test tour-related endpoints."""

    def test_start_tour(self, client, mock_service):
        """Test starting the tour."""
        response = client.post("/api/v1/onboarding/tour/start")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_service.start_tour.assert_called_once()

    def test_complete_tour_step(self, client, mock_service):
        """Test completing a tour step."""
        response = client.post("/api/v1/onboarding/tour/step", json={"step": 3})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "step 3" in data["message"].lower()
        mock_service.complete_tour_step.assert_called_once()

    def test_complete_tour_step_negative(self, client, mock_service):
        """Test completing tour step with negative value."""
        response = client.post("/api/v1/onboarding/tour/step", json={"step": -1})

        # Should fail validation
        assert response.status_code == 422

    def test_complete_tour(self, client, mock_service):
        """Test marking tour as complete."""
        response = client.post("/api/v1/onboarding/tour/complete")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_service.complete_tour.assert_called_once()

    def test_skip_tour(self, client, mock_service):
        """Test skipping the tour."""
        response = client.post("/api/v1/onboarding/tour/skip")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_service.skip_tour.assert_called_once()


# =============================================================================
# Tooltip Endpoint Tests
# =============================================================================


class TestTooltipEndpoints:
    """Test tooltip-related endpoints."""

    def test_dismiss_tooltip(self, client, mock_service):
        """Test dismissing a tooltip."""
        response = client.post("/api/v1/onboarding/tooltip/graphrag-toggle/dismiss")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_service.dismiss_tooltip.assert_called_once()

    def test_dismiss_tooltip_special_chars(self, client, mock_service):
        """Test dismissing tooltip with special characters in ID."""
        response = client.post("/api/v1/onboarding/tooltip/feature-123_test/dismiss")

        assert response.status_code == 200
        mock_service.dismiss_tooltip.assert_called()


# =============================================================================
# Checklist Endpoint Tests
# =============================================================================


class TestChecklistEndpoints:
    """Test checklist-related endpoints."""

    def test_complete_checklist_item(self, client, mock_service):
        """Test completing a checklist item."""
        response = client.post(
            "/api/v1/onboarding/checklist/connect_repository/complete"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_service.complete_checklist_item.assert_called_once()

    def test_complete_checklist_item_all_done(self, client, mock_service):
        """Test completing last checklist item."""
        mock_service.complete_checklist_item.return_value = True

        response = client.post(
            "/api/v1/onboarding/checklist/invite_team_member/complete"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_dismiss_checklist(self, client, mock_service):
        """Test dismissing the checklist."""
        response = client.post("/api/v1/onboarding/checklist/dismiss")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_service.dismiss_checklist.assert_called_once()


# =============================================================================
# Video Endpoint Tests
# =============================================================================


class TestVideoEndpoints:
    """Test video-related endpoints."""

    def test_update_video_progress(self, client, mock_service):
        """Test updating video progress."""
        response = client.post(
            "/api/v1/onboarding/video/platform-overview/progress",
            json={"progress": 50.0, "completed": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_service.update_video_progress.assert_called_once()

    def test_update_video_progress_completed(self, client, mock_service):
        """Test marking video as completed."""
        response = client.post(
            "/api/v1/onboarding/video/platform-overview/progress",
            json={"progress": 100.0, "completed": True},
        )

        assert response.status_code == 200
        mock_service.update_video_progress.assert_called()
        # Check completed flag was passed
        call_args = mock_service.update_video_progress.call_args
        assert call_args[0][-1] is True or call_args.kwargs.get("completed") is True

    def test_update_video_progress_invalid(self, client, mock_service):
        """Test updating video with invalid progress."""
        response = client.post(
            "/api/v1/onboarding/video/platform-overview/progress",
            json={"progress": 150.0, "completed": False},
        )

        # Should fail validation (progress > 100)
        assert response.status_code == 422

    def test_update_video_progress_negative(self, client, mock_service):
        """Test updating video with negative progress."""
        response = client.post(
            "/api/v1/onboarding/video/platform-overview/progress",
            json={"progress": -10.0, "completed": False},
        )

        # Should fail validation (progress < 0)
        assert response.status_code == 422

    def test_get_video_catalog(self, client, mock_service):
        """Test getting video catalog."""
        response = client.get("/api/v1/onboarding/videos")

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert data[0]["id"] == "platform-overview"

    def test_video_catalog_structure(self, client, mock_service):
        """Test video catalog has required fields."""
        response = client.get("/api/v1/onboarding/videos")

        assert response.status_code == 200
        data = response.json()

        for video in data:
            assert "id" in video
            assert "title" in video
            assert "description" in video
            assert "duration" in video
            assert "video_url" in video
            assert "chapters" in video


# =============================================================================
# Reset Endpoint Tests
# =============================================================================


class TestResetEndpoint:
    """Test reset endpoint."""

    def test_reset_state(self, client, mock_service):
        """Test resetting onboarding state."""
        response = client.post("/api/v1/onboarding/reset")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_service.reset_state.assert_called_once()


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling in endpoints."""

    def test_invalid_json_body(self, client, mock_service):
        """Test handling of invalid JSON body."""
        response = client.patch(
            "/api/v1/onboarding/state",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_missing_required_field(self, client, mock_service):
        """Test handling of missing required field."""
        response = client.post(
            "/api/v1/onboarding/tour/step", json={}  # Missing "step" field
        )

        assert response.status_code == 422


# =============================================================================
# Response Model Tests
# =============================================================================


class TestResponseModels:
    """Test response model validation."""

    def test_state_response_model(self, client, mock_service):
        """Test state response matches expected model."""
        response = client.get("/api/v1/onboarding/state")

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "welcome_modal_dismissed" in data
        assert "tour_completed" in data
        assert "tour_step" in data
        assert "checklist_steps" in data
        assert "dismissed_tooltips" in data

    def test_success_response_model(self, client, mock_service):
        """Test success response matches expected model."""
        response = client.post("/api/v1/onboarding/modal/dismiss")

        assert response.status_code == 200
        data = response.json()

        assert "success" in data
        assert data["success"] is True

    def test_video_response_model(self, client, mock_service):
        """Test video response matches expected model."""
        response = client.get("/api/v1/onboarding/videos")

        assert response.status_code == 200
        data = response.json()

        # Check first video has required fields
        video = data[0]
        assert "id" in video
        assert "title" in video
        assert "duration" in video
        assert isinstance(video["duration"], int)
        assert "chapters" in video
        assert isinstance(video["chapters"], list)
