"""
Project Aura - Onboarding Service

Service for managing customer onboarding state and progress.
Handles persistence to DynamoDB and provides business logic.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default checklist steps
DEFAULT_CHECKLIST_STEPS = {
    "connect_repository": False,
    "configure_analysis": False,
    "run_first_scan": False,
    "review_vulnerabilities": False,
    "invite_team_member": False,
}

# Video catalog (in production, this would come from S3/CloudFront)
VIDEO_CATALOG = [
    {
        "id": "platform-overview",
        "title": "Platform Overview",
        "description": "Learn about Project Aura's core capabilities and how it helps secure your codebase.",
        "duration": 150,
        "thumbnail_url": "/assets/videos/thumbnails/platform-overview.jpg",
        "video_url": "/assets/videos/platform-overview.mp4",
        "chapters": [
            {"time": 0, "title": "Introduction"},
            {"time": 30, "title": "Dashboard Tour"},
            {"time": 60, "title": "Key Features"},
            {"time": 120, "title": "Getting Help"},
        ],
    },
    {
        "id": "connecting-repositories",
        "title": "Connecting Repositories",
        "description": "Step-by-step guide to connecting your GitHub or GitLab repositories.",
        "duration": 180,
        "thumbnail_url": "/assets/videos/thumbnails/connecting-repos.jpg",
        "video_url": "/assets/videos/connecting-repos.mp4",
        "chapters": [
            {"time": 0, "title": "OAuth Setup"},
            {"time": 45, "title": "Selecting Repositories"},
            {"time": 90, "title": "Configuration Options"},
            {"time": 150, "title": "Starting Ingestion"},
        ],
    },
    {
        "id": "security-scanning",
        "title": "Security Scanning",
        "description": "Understanding vulnerability detection and security analysis results.",
        "duration": 165,
        "thumbnail_url": "/assets/videos/thumbnails/security-scanning.jpg",
        "video_url": "/assets/videos/security-scanning.mp4",
        "chapters": [
            {"time": 0, "title": "Scan Types"},
            {"time": 40, "title": "Reading Results"},
            {"time": 90, "title": "Severity Levels"},
            {"time": 130, "title": "Taking Action"},
        ],
    },
    {
        "id": "patch-approval",
        "title": "Patch Approval Workflow",
        "description": "How to review, test, and approve AI-generated security patches.",
        "duration": 210,
        "thumbnail_url": "/assets/videos/thumbnails/patch-approval.jpg",
        "video_url": "/assets/videos/patch-approval.mp4",
        "chapters": [
            {"time": 0, "title": "HITL Overview"},
            {"time": 50, "title": "Reviewing Patches"},
            {"time": 100, "title": "Sandbox Testing"},
            {"time": 160, "title": "Approval Process"},
        ],
    },
    {
        "id": "team-management",
        "title": "Team Management",
        "description": "Inviting team members and managing roles and permissions.",
        "duration": 120,
        "thumbnail_url": "/assets/videos/thumbnails/team-management.jpg",
        "video_url": "/assets/videos/team-management.mp4",
        "chapters": [
            {"time": 0, "title": "Inviting Members"},
            {"time": 40, "title": "Role Assignment"},
            {"time": 70, "title": "Permissions"},
            {"time": 100, "title": "Activity Tracking"},
        ],
    },
]


class OnboardingService:
    """Service for managing user onboarding state."""

    def __init__(self, table_name: Optional[str] = None):
        """Initialize the onboarding service.

        Args:
            table_name: DynamoDB table name for onboarding state.
        """
        self.table_name = table_name or os.environ.get(
            "ONBOARDING_TABLE_NAME", "aura-user-onboarding-dev"
        )
        self._table = None
        self._dynamodb = None

    @property
    def table(self) -> Any:
        """Lazy-load DynamoDB table resource."""
        if self._table is None:
            try:
                import boto3

                self._dynamodb = boto3.resource("dynamodb")
                self._table = self._dynamodb.Table(self.table_name)
            except Exception as e:
                logger.warning(f"Failed to connect to DynamoDB: {e}")
                self._table = None
        return self._table

    def _get_default_state(self, user_id: str, org_id: str) -> dict[str, Any]:
        """Create default onboarding state for a new user."""
        now = datetime.now(timezone.utc).isoformat()
        return {
            "user_id": user_id,
            "organization_id": org_id,
            "welcome_modal_dismissed": False,
            "welcome_modal_dismissed_at": None,
            "tour_completed": False,
            "tour_step": 0,
            "tour_started_at": None,
            "tour_completed_at": None,
            "tour_skipped": False,
            "checklist_dismissed": False,
            "checklist_steps": DEFAULT_CHECKLIST_STEPS.copy(),
            "checklist_started_at": None,
            "checklist_completed_at": None,
            "dismissed_tooltips": [],
            "video_progress": {},
            "created_at": now,
            "updated_at": now,
        }

    async def get_state(self, user_id: str, org_id: str) -> dict[str, Any]:
        """Get onboarding state for a user.

        Args:
            user_id: The user ID.
            org_id: The organization ID.

        Returns:
            The user's onboarding state.
        """
        if self.table is None:
            # Return default state for development without DynamoDB
            return self._get_default_state(user_id, org_id)

        try:
            response = self.table.get_item(Key={"user_id": user_id})
            item = response.get("Item")

            if item:
                return item

            # Create default state for new user
            state = self._get_default_state(user_id, org_id)
            self.table.put_item(Item=state)
            return state

        except Exception as e:
            logger.error(f"Failed to get onboarding state: {e}")
            return self._get_default_state(user_id, org_id)

    async def update_state(
        self, user_id: str, org_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Update onboarding state.

        Args:
            user_id: The user ID.
            org_id: The organization ID.
            updates: Dict of fields to update.

        Returns:
            The updated state.
        """
        current_state = await self.get_state(user_id, org_id)
        now = datetime.now(timezone.utc).isoformat()

        # Merge updates
        for key, value in updates.items():
            if key in current_state:
                if isinstance(value, dict) and isinstance(current_state[key], dict):
                    current_state[key].update(value)
                else:
                    current_state[key] = value

        current_state["updated_at"] = now

        if self.table is not None:
            try:
                self.table.put_item(Item=current_state)
            except Exception as e:
                logger.error(f"Failed to update onboarding state: {e}")

        return current_state

    async def dismiss_modal(self, user_id: str, org_id: str) -> None:
        """Dismiss the welcome modal.

        Args:
            user_id: The user ID.
            org_id: The organization ID.
        """
        now = datetime.now(timezone.utc).isoformat()
        await self.update_state(
            user_id,
            org_id,
            {
                "welcome_modal_dismissed": True,
                "welcome_modal_dismissed_at": now,
            },
        )

    async def start_tour(self, user_id: str, org_id: str) -> None:
        """Start the welcome tour.

        Args:
            user_id: The user ID.
            org_id: The organization ID.
        """
        now = datetime.now(timezone.utc).isoformat()
        await self.update_state(
            user_id,
            org_id,
            {
                "tour_step": 0,
                "tour_started_at": now,
                "welcome_modal_dismissed": True,
                "welcome_modal_dismissed_at": now,
            },
        )

    async def complete_tour_step(self, user_id: str, org_id: str, step: int) -> None:
        """Complete a tour step.

        Args:
            user_id: The user ID.
            org_id: The organization ID.
            step: The step index that was completed.
        """
        await self.update_state(
            user_id,
            org_id,
            {"tour_step": step + 1},
        )

    async def complete_tour(self, user_id: str, org_id: str) -> None:
        """Mark tour as complete.

        Args:
            user_id: The user ID.
            org_id: The organization ID.
        """
        now = datetime.now(timezone.utc).isoformat()
        await self.update_state(
            user_id,
            org_id,
            {
                "tour_completed": True,
                "tour_completed_at": now,
            },
        )

    async def skip_tour(self, user_id: str, org_id: str) -> None:
        """Skip the tour.

        Args:
            user_id: The user ID.
            org_id: The organization ID.
        """
        now = datetime.now(timezone.utc).isoformat()
        await self.update_state(
            user_id,
            org_id,
            {
                "tour_skipped": True,
                "tour_completed": True,
                "tour_completed_at": now,
            },
        )

    async def dismiss_tooltip(self, user_id: str, org_id: str, tooltip_id: str) -> None:
        """Dismiss a feature tooltip.

        Args:
            user_id: The user ID.
            org_id: The organization ID.
            tooltip_id: The tooltip to dismiss.
        """
        state = await self.get_state(user_id, org_id)
        dismissed = set(state.get("dismissed_tooltips", []))
        dismissed.add(tooltip_id)

        await self.update_state(
            user_id,
            org_id,
            {"dismissed_tooltips": list(dismissed)},
        )

    async def complete_checklist_item(
        self, user_id: str, org_id: str, item_id: str
    ) -> bool:
        """Complete a checklist item.

        Args:
            user_id: The user ID.
            org_id: The organization ID.
            item_id: The checklist item ID.

        Returns:
            True if all items are now complete.
        """
        state = await self.get_state(user_id, org_id)
        checklist_steps = state.get("checklist_steps", DEFAULT_CHECKLIST_STEPS.copy())

        if item_id in checklist_steps:
            checklist_steps[item_id] = True

        # Check if first item completion
        now = datetime.now(timezone.utc).isoformat()
        updates: dict[str, Any] = {"checklist_steps": checklist_steps}

        if not state.get("checklist_started_at"):
            updates["checklist_started_at"] = now

        # Check if all complete
        all_complete = all(checklist_steps.values())
        if all_complete and not state.get("checklist_completed_at"):
            updates["checklist_completed_at"] = now

        await self.update_state(user_id, org_id, updates)
        return all_complete

    async def dismiss_checklist(self, user_id: str, org_id: str) -> None:
        """Dismiss the checklist.

        Args:
            user_id: The user ID.
            org_id: The organization ID.
        """
        await self.update_state(
            user_id,
            org_id,
            {"checklist_dismissed": True},
        )

    async def update_video_progress(
        self,
        user_id: str,
        org_id: str,
        video_id: str,
        progress: float,
        completed: bool = False,
    ) -> None:
        """Update video watch progress.

        Args:
            user_id: The user ID.
            org_id: The organization ID.
            video_id: The video ID.
            progress: Progress percentage (0-100).
            completed: Whether video is completed.
        """
        state = await self.get_state(user_id, org_id)
        video_progress = state.get("video_progress", {})

        video_progress[video_id] = {
            "percent": progress,
            "completed": completed,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        await self.update_state(
            user_id,
            org_id,
            {"video_progress": video_progress},
        )

    async def get_video_catalog(self) -> list[dict[str, Any]]:
        """Get the onboarding video catalog.

        Returns:
            List of video metadata.
        """
        return VIDEO_CATALOG

    async def reset_state(self, user_id: str, org_id: str) -> None:
        """Reset onboarding state (for development/testing).

        Args:
            user_id: The user ID.
            org_id: The organization ID.
        """
        if self.table is not None:
            try:
                self.table.delete_item(Key={"user_id": user_id})
            except Exception as e:
                logger.error(f"Failed to reset onboarding state: {e}")


# Singleton instance
_service_instance: Optional[OnboardingService] = None


def get_onboarding_service() -> OnboardingService:
    """Get the onboarding service singleton.

    Returns:
        The OnboardingService instance.
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = OnboardingService()
    return _service_instance


def set_onboarding_service(service: OnboardingService) -> None:
    """Set the onboarding service instance (for testing).

    Args:
        service: The service instance to use.
    """
    global _service_instance
    _service_instance = service
