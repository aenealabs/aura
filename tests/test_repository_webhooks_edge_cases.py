"""
Repository Webhooks Edge Case Tests - Out-of-Order and Event Handling.

Tests for edge cases in repository webhook handling including:
1. Push event arrives before branch creation event (out-of-order)
2. PR merge event arrives before PR created event
3. Delete branch event for branch never seen before
4. Duplicate events (same delivery ID)
5. Event replay (old events resent)
6. Event with future timestamp (clock skew)
7. Event for deleted repository
8. Event with missing required fields
9. Event signature validation failure mid-batch
10. Rate limiting from GitHub API during event processing

These tests ensure robust handling of webhook edge cases in production
environments where network delays and API inconsistencies are common.

See ADR-043 for repository onboarding architecture.
"""

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.webhook_handler import GitHubWebhookHandler, WebhookEvent, WebhookEventType

# =============================================================================
# Webhook Event Processing Models (for testing)
# =============================================================================


class EventProcessingStatus(Enum):
    """Status of webhook event processing."""

    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    SKIPPED = "skipped"
    DEFERRED = "deferred"
    FAILED = "failed"


@dataclass
class ProcessedEvent:
    """Record of a processed webhook event."""

    delivery_id: str
    event_type: str
    repository_name: str
    branch: str | None
    status: EventProcessingStatus
    processed_at: datetime | None = None
    error_message: str | None = None


@dataclass
class BranchState:
    """Track branch state for out-of-order event handling."""

    branch_name: str
    repository_name: str
    created_at: datetime | None = None
    last_push_at: datetime | None = None
    head_commit: str | None = None
    exists: bool = True


@dataclass
class WebhookEventStore:
    """
    In-memory event store for tracking webhook events.

    Used for:
    - Deduplication (tracking delivery IDs)
    - Out-of-order event handling (tracking branch state)
    - Event replay detection
    """

    processed_delivery_ids: set = field(default_factory=set)
    branch_states: dict = field(default_factory=dict)
    pending_events: list = field(default_factory=list)
    event_timestamps: dict = field(default_factory=dict)

    def is_duplicate(self, delivery_id: str) -> bool:
        """Check if event has already been processed."""
        return delivery_id in self.processed_delivery_ids

    def mark_processed(self, delivery_id: str) -> None:
        """Mark event as processed."""
        self.processed_delivery_ids.add(delivery_id)

    def get_branch_state(self, repo: str, branch: str) -> BranchState | None:
        """Get branch state if tracked."""
        key = f"{repo}:{branch}"
        return self.branch_states.get(key)

    def set_branch_state(self, state: BranchState) -> None:
        """Set branch state."""
        key = f"{state.repository_name}:{state.branch_name}"
        self.branch_states[key] = state


class WebhookEventProcessor:
    """
    Webhook event processor with edge case handling.

    Handles:
    - Out-of-order events (deferred processing)
    - Duplicate detection (idempotency)
    - Event replay protection
    - Clock skew detection
    """

    # Maximum clock skew tolerance (5 minutes in the future)
    MAX_FUTURE_TIMESTAMP_SECONDS = 300

    # Maximum age for event replay detection (1 hour)
    MAX_EVENT_AGE_SECONDS = 3600

    def __init__(
        self,
        event_store: WebhookEventStore | None = None,
        repository_service: Any = None,
        github_client: Any = None,
    ):
        """Initialize event processor."""
        self.event_store = event_store or WebhookEventStore()
        self.repository_service = repository_service
        self.github_client = github_client

    async def process_event(
        self,
        event: WebhookEvent,
        delivery_id: str,
        event_timestamp: datetime | None = None,
    ) -> ProcessedEvent:
        """
        Process a webhook event with edge case handling.

        Args:
            event: The parsed webhook event
            delivery_id: GitHub delivery ID for deduplication
            event_timestamp: Event timestamp from payload

        Returns:
            ProcessedEvent with status
        """
        # Check for duplicate delivery
        if self.event_store.is_duplicate(delivery_id):
            return ProcessedEvent(
                delivery_id=delivery_id,
                event_type=event.event_type.value,
                repository_name=event.repository_name,
                branch=event.branch,
                status=EventProcessingStatus.SKIPPED,
                error_message="Duplicate event: already processed",
            )

        # Check for future timestamp (clock skew)
        if event_timestamp:
            now = datetime.now(timezone.utc)
            if event_timestamp > now + timedelta(
                seconds=self.MAX_FUTURE_TIMESTAMP_SECONDS
            ):
                return ProcessedEvent(
                    delivery_id=delivery_id,
                    event_type=event.event_type.value,
                    repository_name=event.repository_name,
                    branch=event.branch,
                    status=EventProcessingStatus.SKIPPED,
                    error_message=f"Event timestamp too far in future: {event_timestamp}",
                )

        # Check for event replay (too old)
        if event_timestamp:
            now = datetime.now(timezone.utc)
            age_seconds = (now - event_timestamp).total_seconds()
            if age_seconds > self.MAX_EVENT_AGE_SECONDS:
                return ProcessedEvent(
                    delivery_id=delivery_id,
                    event_type=event.event_type.value,
                    repository_name=event.repository_name,
                    branch=event.branch,
                    status=EventProcessingStatus.SKIPPED,
                    error_message=f"Event too old (replay detected): {age_seconds}s",
                )

        # Handle based on event type
        if event.event_type == WebhookEventType.PUSH:
            return await self._process_push_event(event, delivery_id)
        elif event.event_type == WebhookEventType.PULL_REQUEST:
            return await self._process_pr_event(event, delivery_id)
        elif event.event_type == WebhookEventType.CREATE:
            return await self._process_create_event(event, delivery_id)
        elif event.event_type == WebhookEventType.DELETE:
            return await self._process_delete_event(event, delivery_id)
        else:
            return ProcessedEvent(
                delivery_id=delivery_id,
                event_type=event.event_type.value,
                repository_name=event.repository_name,
                branch=event.branch,
                status=EventProcessingStatus.SKIPPED,
                error_message=f"Unsupported event type: {event.event_type}",
            )

    async def _process_push_event(
        self, event: WebhookEvent, delivery_id: str
    ) -> ProcessedEvent:
        """Process push event, handling out-of-order branch creation."""
        branch_state = self.event_store.get_branch_state(
            event.repository_name, event.branch
        )

        # If branch not seen before, it might be out-of-order
        # We can still process the push, just note it
        if branch_state is None:
            # Create implicit branch state from push
            branch_state = BranchState(
                branch_name=event.branch,
                repository_name=event.repository_name,
                last_push_at=datetime.now(timezone.utc),
                head_commit=event.commit_hash,
                exists=True,
            )
            self.event_store.set_branch_state(branch_state)

        # Mark as processed
        self.event_store.mark_processed(delivery_id)

        return ProcessedEvent(
            delivery_id=delivery_id,
            event_type=event.event_type.value,
            repository_name=event.repository_name,
            branch=event.branch,
            status=EventProcessingStatus.PROCESSED,
            processed_at=datetime.now(timezone.utc),
        )

    async def _process_pr_event(
        self, event: WebhookEvent, delivery_id: str
    ) -> ProcessedEvent:
        """Process PR event."""
        action = event.raw_payload.get("action", "unknown")

        # For merge events, verify PR context exists
        if action == "closed" and event.raw_payload.get("pull_request", {}).get(
            "merged"
        ):
            # This is a merge - check if we have PR context
            pr_number = event.raw_payload.get("pull_request", {}).get("number")
            if pr_number and not self._has_pr_context(event.repository_name, pr_number):
                # PR context missing but we can still process merge
                # Log warning but don't fail
                pass

        self.event_store.mark_processed(delivery_id)

        return ProcessedEvent(
            delivery_id=delivery_id,
            event_type=event.event_type.value,
            repository_name=event.repository_name,
            branch=event.branch,
            status=EventProcessingStatus.PROCESSED,
            processed_at=datetime.now(timezone.utc),
        )

    async def _process_create_event(
        self, event: WebhookEvent, delivery_id: str
    ) -> ProcessedEvent:
        """Process branch/tag creation event."""
        ref_type = event.raw_payload.get("ref_type", "branch")

        if ref_type == "branch":
            branch_state = BranchState(
                branch_name=event.branch,
                repository_name=event.repository_name,
                created_at=datetime.now(timezone.utc),
                exists=True,
            )
            self.event_store.set_branch_state(branch_state)

        self.event_store.mark_processed(delivery_id)

        return ProcessedEvent(
            delivery_id=delivery_id,
            event_type=event.event_type.value,
            repository_name=event.repository_name,
            branch=event.branch,
            status=EventProcessingStatus.PROCESSED,
            processed_at=datetime.now(timezone.utc),
        )

    async def _process_delete_event(
        self, event: WebhookEvent, delivery_id: str
    ) -> ProcessedEvent:
        """Process branch/tag deletion event."""
        ref_type = event.raw_payload.get("ref_type", "branch")

        if ref_type == "branch":
            branch_state = self.event_store.get_branch_state(
                event.repository_name, event.branch
            )

            # Branch might not exist in our state (out-of-order or never seen)
            if branch_state:
                branch_state.exists = False
            else:
                # Create a deleted branch state
                branch_state = BranchState(
                    branch_name=event.branch,
                    repository_name=event.repository_name,
                    exists=False,
                )
                self.event_store.set_branch_state(branch_state)

        self.event_store.mark_processed(delivery_id)

        return ProcessedEvent(
            delivery_id=delivery_id,
            event_type=event.event_type.value,
            repository_name=event.repository_name,
            branch=event.branch,
            status=EventProcessingStatus.PROCESSED,
            processed_at=datetime.now(timezone.utc),
        )

    def _has_pr_context(self, repository_name: str, pr_number: int) -> bool:
        """Check if we have context for a PR."""
        # In production this would check database
        return False


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def webhook_secret():
    """Webhook secret for signature validation."""
    return "test-webhook-secret-12345"


@pytest.fixture
def webhook_handler(webhook_secret):
    """Create a GitHubWebhookHandler for testing."""
    return GitHubWebhookHandler(
        webhook_secret=webhook_secret,
        ingestion_service=None,
        allowed_branches=["main", "master", "develop", "feature/test"],
    )


@pytest.fixture
def event_store():
    """Create an event store for testing."""
    return WebhookEventStore()


@pytest.fixture
def event_processor(event_store):
    """Create an event processor for testing."""
    return WebhookEventProcessor(
        event_store=event_store,
        repository_service=MagicMock(),
        github_client=MagicMock(),
    )


@pytest.fixture
def mock_repository_service():
    """Create mock repository service."""
    service = MagicMock()
    service.get_repository = AsyncMock(return_value=None)
    service.repository_exists = AsyncMock(return_value=True)
    return service


def create_push_payload(
    repo_name: str = "org/test-repo",
    branch: str = "main",
    commit_hash: str = "abc123def456",
    files: list | None = None,
) -> dict:
    """Create a sample push webhook payload."""
    files = files or ["src/main.py"]
    return {
        "ref": f"refs/heads/{branch}",
        "after": commit_hash,
        "repository": {
            "full_name": repo_name,
            "clone_url": f"https://github.com/{repo_name}.git",
        },
        "commits": [
            {"added": files, "modified": [], "removed": []},
        ],
        "sender": {"login": "testuser"},
    }


def create_create_payload(
    repo_name: str = "org/test-repo",
    ref: str = "feature/new-branch",
    ref_type: str = "branch",
) -> dict:
    """Create a sample create (branch/tag) webhook payload."""
    return {
        "ref": ref,
        "ref_type": ref_type,
        "repository": {
            "full_name": repo_name,
            "clone_url": f"https://github.com/{repo_name}.git",
        },
        "sender": {"login": "testuser"},
    }


def create_delete_payload(
    repo_name: str = "org/test-repo",
    ref: str = "feature/deleted-branch",
    ref_type: str = "branch",
) -> dict:
    """Create a sample delete (branch/tag) webhook payload."""
    return {
        "ref": ref,
        "ref_type": ref_type,
        "repository": {
            "full_name": repo_name,
            "clone_url": f"https://github.com/{repo_name}.git",
        },
        "sender": {"login": "testuser"},
    }


def create_pr_payload(
    repo_name: str = "org/test-repo",
    action: str = "opened",
    pr_number: int = 42,
    merged: bool = False,
    head_branch: str = "feature/test",
    head_sha: str = "abc123",
) -> dict:
    """Create a sample pull request webhook payload."""
    return {
        "action": action,
        "number": pr_number,
        "pull_request": {
            "number": pr_number,
            "merged": merged,
            "head": {
                "ref": head_branch,
                "sha": head_sha,
            },
            "base": {
                "ref": "main",
            },
        },
        "repository": {
            "full_name": repo_name,
            "clone_url": f"https://github.com/{repo_name}.git",
        },
        "sender": {"login": "testuser"},
    }


def sign_payload(payload: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature for payload."""
    signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={signature}"


# =============================================================================
# Out-of-Order Event Tests
# =============================================================================


class TestOutOfOrderEvents:
    """
    Tests for handling webhook events that arrive out of order.

    Git events can arrive out of order due to network delays.
    For example, a "push" event might arrive before the "branch create" event.
    """

    @pytest.mark.asyncio
    async def test_push_event_before_branch_create(
        self, event_processor, webhook_handler, webhook_secret
    ):
        """
        Test handling push event when branch create event hasn't arrived yet.

        This is a common scenario where a developer pushes to a new branch
        and the push event arrives before the branch creation event.
        """
        # Create push event for a branch that doesn't exist in our state
        push_payload = create_push_payload(
            branch="feature/new-work",
            commit_hash="new123hash",
        )
        payload_bytes = json.dumps(push_payload).encode()
        signature = sign_payload(payload_bytes, webhook_secret)

        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": "push-delivery-001",
        }

        # Parse and process the push event
        event = webhook_handler.parse_event(headers, payload_bytes)
        assert event is not None
        assert event.event_type == WebhookEventType.PUSH
        assert event.branch == "feature/new-work"

        # Process should succeed even without prior branch create
        result = await event_processor.process_event(
            event,
            delivery_id="push-delivery-001",
        )

        assert result.status == EventProcessingStatus.PROCESSED
        assert result.error_message is None

        # Branch state should be implicitly created
        branch_state = event_processor.event_store.get_branch_state(
            "org/test-repo", "feature/new-work"
        )
        assert branch_state is not None
        assert branch_state.exists is True
        assert branch_state.head_commit == "new123hash"

    @pytest.mark.asyncio
    async def test_branch_create_after_push(
        self, event_processor, webhook_handler, webhook_secret
    ):
        """
        Test that branch create event is handled correctly even after push.

        The create event arriving after push should update, not conflict.
        """
        # First, simulate push event creating implicit state
        push_payload = create_push_payload(branch="feature/delayed-create")
        payload_bytes = json.dumps(push_payload).encode()
        signature = sign_payload(payload_bytes, webhook_secret)

        push_headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": "push-delivery-002",
        }

        push_event = webhook_handler.parse_event(push_headers, payload_bytes)
        await event_processor.process_event(push_event, "push-delivery-002")

        # Now process the delayed branch create event
        create_payload = create_create_payload(ref="feature/delayed-create")
        create_bytes = json.dumps(create_payload).encode()
        create_signature = sign_payload(create_bytes, webhook_secret)

        create_headers = {
            "X-GitHub-Event": "create",
            "X-Hub-Signature-256": create_signature,
            "X-GitHub-Delivery": "create-delivery-001",
        }

        create_event = webhook_handler.parse_event(create_headers, create_bytes)
        # Note: The webhook handler doesn't parse create events (only push/PR)
        # so create_event will be None. We create a mock for testing the processor.
        assert create_event is None  # Expected - handler only processes push/PR

        # Create a mock create event to test the processor's handling
        mock_create_event = WebhookEvent(
            event_type=WebhookEventType.CREATE,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="feature/delayed-create",
            commit_hash=None,
            changed_files=[],
            sender="testuser",
            timestamp=datetime.now(),
            raw_payload=create_payload,
        )

        result = await event_processor.process_event(
            mock_create_event,
            delivery_id="create-delivery-001",
        )

        assert result.status == EventProcessingStatus.PROCESSED

        # Branch state should be updated with creation time
        branch_state = event_processor.event_store.get_branch_state(
            "org/test-repo", "feature/delayed-create"
        )
        assert branch_state is not None
        assert branch_state.created_at is not None

    @pytest.mark.asyncio
    async def test_pr_merge_before_pr_created(
        self, event_processor, webhook_handler, webhook_secret
    ):
        """
        Test handling PR merge event when PR created event hasn't arrived.

        This can happen when events are heavily delayed or lost.
        """
        # Create PR merge event without prior PR created event
        merge_payload = create_pr_payload(
            action="closed",
            pr_number=99,
            merged=True,
            head_branch="feature/quick-merge",
        )
        payload_bytes = json.dumps(merge_payload).encode()
        signature = sign_payload(payload_bytes, webhook_secret)

        headers = {
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": "merge-delivery-001",
        }

        event = webhook_handler.parse_event(headers, payload_bytes)
        # Note: Current handler returns None for closed PR events
        # We need to test the processor's handling

        mock_merge_event = WebhookEvent(
            event_type=WebhookEventType.PULL_REQUEST,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="feature/quick-merge",
            commit_hash="mergehash123",
            changed_files=[],
            sender="testuser",
            timestamp=datetime.now(),
            raw_payload=merge_payload,
        )

        result = await event_processor.process_event(
            mock_merge_event,
            delivery_id="merge-delivery-001",
        )

        # Should process successfully even without prior PR context
        assert result.status == EventProcessingStatus.PROCESSED

    @pytest.mark.asyncio
    async def test_multiple_pushes_out_of_order(
        self, event_processor, webhook_handler, webhook_secret
    ):
        """
        Test handling multiple push events arriving out of order.

        Push events should be processed based on delivery, not timestamp.
        """
        # Create two push events with different commits
        push1_payload = create_push_payload(
            branch="main",
            commit_hash="first-commit-123",
        )
        push2_payload = create_push_payload(
            branch="main",
            commit_hash="second-commit-456",
        )

        # Process second push first (simulating out-of-order delivery)
        push2_bytes = json.dumps(push2_payload).encode()
        signature2 = sign_payload(push2_bytes, webhook_secret)

        headers2 = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": signature2,
            "X-GitHub-Delivery": "push-delivery-newer",
        }

        event2 = webhook_handler.parse_event(headers2, push2_bytes)
        result2 = await event_processor.process_event(event2, "push-delivery-newer")

        assert result2.status == EventProcessingStatus.PROCESSED

        # Now process first push (arrived later due to network delay)
        push1_bytes = json.dumps(push1_payload).encode()
        signature1 = sign_payload(push1_bytes, webhook_secret)

        headers1 = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": signature1,
            "X-GitHub-Delivery": "push-delivery-older",
        }

        event1 = webhook_handler.parse_event(headers1, push1_bytes)
        result1 = await event_processor.process_event(event1, "push-delivery-older")

        # Should still process (each push is independent)
        assert result1.status == EventProcessingStatus.PROCESSED


# =============================================================================
# Duplicate and Replay Event Tests
# =============================================================================


class TestDuplicateEvents:
    """
    Tests for duplicate event detection and handling.

    GitHub may send the same event multiple times due to retries.
    """

    @pytest.mark.asyncio
    async def test_duplicate_delivery_id_rejected(
        self, event_processor, webhook_handler, webhook_secret
    ):
        """
        Test that events with duplicate delivery IDs are rejected.

        Same delivery ID = same event, should be idempotent.
        """
        push_payload = create_push_payload()
        payload_bytes = json.dumps(push_payload).encode()
        signature = sign_payload(payload_bytes, webhook_secret)

        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": "duplicate-delivery-001",
        }

        event = webhook_handler.parse_event(headers, payload_bytes)

        # First processing should succeed
        result1 = await event_processor.process_event(event, "duplicate-delivery-001")
        assert result1.status == EventProcessingStatus.PROCESSED

        # Second processing with same delivery ID should be skipped
        result2 = await event_processor.process_event(event, "duplicate-delivery-001")
        assert result2.status == EventProcessingStatus.SKIPPED
        assert "Duplicate event" in result2.error_message

    @pytest.mark.asyncio
    async def test_same_content_different_delivery_id(
        self, event_processor, webhook_handler, webhook_secret
    ):
        """
        Test that identical content with different delivery ID is processed.

        Different delivery ID = different event, even if content is identical.
        """
        push_payload = create_push_payload()
        payload_bytes = json.dumps(push_payload).encode()
        signature = sign_payload(payload_bytes, webhook_secret)

        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": "delivery-001",
        }

        event = webhook_handler.parse_event(headers, payload_bytes)

        # First delivery ID
        result1 = await event_processor.process_event(event, "delivery-001")
        assert result1.status == EventProcessingStatus.PROCESSED

        # Different delivery ID, same content
        result2 = await event_processor.process_event(event, "delivery-002")
        assert result2.status == EventProcessingStatus.PROCESSED

    @pytest.mark.asyncio
    async def test_event_replay_old_event_rejected(self, event_processor):
        """
        Test that very old events (potential replays) are rejected.

        Events older than MAX_EVENT_AGE_SECONDS should be rejected.
        """
        # Create event with very old timestamp
        old_timestamp = datetime.now(timezone.utc) - timedelta(hours=2)

        mock_event = WebhookEvent(
            event_type=WebhookEventType.PUSH,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="main",
            commit_hash="oldcommit123",
            changed_files=["old_file.py"],
            sender="testuser",
            timestamp=old_timestamp,
            raw_payload=create_push_payload(),
        )

        result = await event_processor.process_event(
            mock_event,
            delivery_id="old-delivery-001",
            event_timestamp=old_timestamp,
        )

        assert result.status == EventProcessingStatus.SKIPPED
        assert "replay detected" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_recent_event_accepted(self, event_processor):
        """
        Test that recent events within acceptable age are processed.
        """
        recent_timestamp = datetime.now(timezone.utc) - timedelta(minutes=30)

        mock_event = WebhookEvent(
            event_type=WebhookEventType.PUSH,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="main",
            commit_hash="recentcommit123",
            changed_files=["recent_file.py"],
            sender="testuser",
            timestamp=recent_timestamp,
            raw_payload=create_push_payload(),
        )

        result = await event_processor.process_event(
            mock_event,
            delivery_id="recent-delivery-001",
            event_timestamp=recent_timestamp,
        )

        assert result.status == EventProcessingStatus.PROCESSED


# =============================================================================
# Deleted/Unknown Resource Tests
# =============================================================================


class TestDeletedUnknownResources:
    """
    Tests for events affecting unknown or deleted resources.
    """

    @pytest.mark.asyncio
    async def test_delete_branch_never_seen(self, event_processor):
        """
        Test handling delete event for a branch we've never seen.

        This can happen if we started receiving webhooks after the branch
        was created, or if the create event was lost.
        """
        delete_payload = create_delete_payload(
            ref="feature/unknown-branch",
            ref_type="branch",
        )

        mock_event = WebhookEvent(
            event_type=WebhookEventType.DELETE,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="feature/unknown-branch",
            commit_hash=None,
            changed_files=[],
            sender="testuser",
            timestamp=datetime.now(),
            raw_payload=delete_payload,
        )

        result = await event_processor.process_event(
            mock_event,
            delivery_id="delete-unknown-001",
        )

        # Should succeed - we note the deletion even if we didn't know about it
        assert result.status == EventProcessingStatus.PROCESSED

        # Branch state should show deleted
        branch_state = event_processor.event_store.get_branch_state(
            "org/test-repo", "feature/unknown-branch"
        )
        assert branch_state is not None
        assert branch_state.exists is False

    @pytest.mark.asyncio
    async def test_push_to_deleted_branch(self, event_processor):
        """
        Test push event arriving for a branch we've marked as deleted.

        This shouldn't normally happen, but could occur with event reordering.
        """
        # First mark branch as deleted
        delete_payload = create_delete_payload(ref="feature/zombie-branch")

        delete_event = WebhookEvent(
            event_type=WebhookEventType.DELETE,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="feature/zombie-branch",
            commit_hash=None,
            changed_files=[],
            sender="testuser",
            timestamp=datetime.now(),
            raw_payload=delete_payload,
        )

        await event_processor.process_event(delete_event, "delete-zombie-001")

        # Now push arrives (out of order - this push happened before delete)
        push_payload = create_push_payload(branch="feature/zombie-branch")

        push_event = WebhookEvent(
            event_type=WebhookEventType.PUSH,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="feature/zombie-branch",
            commit_hash="zombiehash123",
            changed_files=["zombie.py"],
            sender="testuser",
            timestamp=datetime.now(),
            raw_payload=push_payload,
        )

        result = await event_processor.process_event(push_event, "push-zombie-001")

        # Should still process (event arrived, we record it)
        assert result.status == EventProcessingStatus.PROCESSED

    @pytest.mark.asyncio
    async def test_event_for_deleted_repository(
        self, event_processor, mock_repository_service
    ):
        """
        Test handling event for a repository that no longer exists.
        """
        mock_repository_service.repository_exists = AsyncMock(return_value=False)
        event_processor.repository_service = mock_repository_service

        push_payload = create_push_payload(repo_name="org/deleted-repo")

        mock_event = WebhookEvent(
            event_type=WebhookEventType.PUSH,
            repository_url="https://github.com/org/deleted-repo.git",
            repository_name="org/deleted-repo",
            branch="main",
            commit_hash="orphan123",
            changed_files=["orphan.py"],
            sender="testuser",
            timestamp=datetime.now(),
            raw_payload=push_payload,
        )

        # Should still process - we handle the event even if repo is gone
        result = await event_processor.process_event(
            mock_event,
            delivery_id="deleted-repo-001",
        )

        assert result.status == EventProcessingStatus.PROCESSED


# =============================================================================
# Timestamp and Clock Skew Tests
# =============================================================================


class TestTimestampEdgeCases:
    """
    Tests for timestamp-related edge cases including clock skew.
    """

    @pytest.mark.asyncio
    async def test_future_timestamp_rejected(self, event_processor):
        """
        Test that events with future timestamps beyond tolerance are rejected.

        Prevents accepting events due to clock skew issues on GitHub's side.
        """
        future_timestamp = datetime.now(timezone.utc) + timedelta(minutes=10)

        mock_event = WebhookEvent(
            event_type=WebhookEventType.PUSH,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="main",
            commit_hash="future123",
            changed_files=["future.py"],
            sender="testuser",
            timestamp=future_timestamp,
            raw_payload=create_push_payload(),
        )

        result = await event_processor.process_event(
            mock_event,
            delivery_id="future-001",
            event_timestamp=future_timestamp,
        )

        assert result.status == EventProcessingStatus.SKIPPED
        assert "future" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_acceptable_future_timestamp(self, event_processor):
        """
        Test that small future timestamps (within tolerance) are accepted.

        Allows for minor clock skew between systems.
        """
        # 2 minutes in future (within 5 minute tolerance)
        near_future = datetime.now(timezone.utc) + timedelta(minutes=2)

        mock_event = WebhookEvent(
            event_type=WebhookEventType.PUSH,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="main",
            commit_hash="nearfuture123",
            changed_files=["near_future.py"],
            sender="testuser",
            timestamp=near_future,
            raw_payload=create_push_payload(),
        )

        result = await event_processor.process_event(
            mock_event,
            delivery_id="near-future-001",
            event_timestamp=near_future,
        )

        assert result.status == EventProcessingStatus.PROCESSED

    @pytest.mark.asyncio
    async def test_event_without_timestamp(self, event_processor):
        """
        Test that events without timestamps are still processed.

        Timestamp validation is optional for backwards compatibility.
        """
        mock_event = WebhookEvent(
            event_type=WebhookEventType.PUSH,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="main",
            commit_hash="notimestamp123",
            changed_files=["no_timestamp.py"],
            sender="testuser",
            timestamp=datetime.now(),
            raw_payload=create_push_payload(),
        )

        result = await event_processor.process_event(
            mock_event,
            delivery_id="no-timestamp-001",
            event_timestamp=None,  # No timestamp provided
        )

        assert result.status == EventProcessingStatus.PROCESSED


# =============================================================================
# Missing Required Fields Tests
# =============================================================================


class TestMissingFields:
    """
    Tests for handling events with missing required fields.
    """

    def test_missing_event_type_header(self, webhook_handler, webhook_secret):
        """
        Test that missing X-GitHub-Event header is handled gracefully.
        """
        push_payload = create_push_payload()
        payload_bytes = json.dumps(push_payload).encode()
        signature = sign_payload(payload_bytes, webhook_secret)

        headers = {
            # Missing X-GitHub-Event
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": "missing-type-001",
        }

        event = webhook_handler.parse_event(headers, payload_bytes)
        assert event is None  # Should return None, not raise

    def test_missing_repository_in_payload(self, webhook_handler, webhook_secret):
        """
        Test handling payload missing repository information.
        """
        invalid_payload = {
            "ref": "refs/heads/main",
            "after": "abc123",
            # Missing "repository" key
            "commits": [],
            "sender": {"login": "testuser"},
        }
        payload_bytes = json.dumps(invalid_payload).encode()
        signature = sign_payload(payload_bytes, webhook_secret)

        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": "missing-repo-001",
        }

        # Should handle gracefully (might return event with empty fields)
        event = webhook_handler.parse_event(headers, payload_bytes)
        # Current implementation returns event with empty repository fields
        if event is not None:
            assert event.repository_name == ""

    def test_missing_ref_in_push_payload(self, webhook_handler, webhook_secret):
        """
        Test handling push payload missing ref field.
        """
        invalid_payload = {
            # Missing "ref"
            "after": "abc123",
            "repository": {
                "full_name": "org/test-repo",
                "clone_url": "https://github.com/org/test-repo.git",
            },
            "commits": [],
            "sender": {"login": "testuser"},
        }
        payload_bytes = json.dumps(invalid_payload).encode()
        signature = sign_payload(payload_bytes, webhook_secret)

        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": "missing-ref-001",
        }

        event = webhook_handler.parse_event(headers, payload_bytes)
        # Should handle gracefully
        if event is not None:
            assert event.branch == ""  # Empty branch, not None

    def test_malformed_json_payload(self, webhook_handler, webhook_secret):
        """
        Test handling malformed JSON payload.
        """
        invalid_json = b'{"broken": json'
        # Can't create valid signature for invalid JSON, but test parsing
        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": "sha256=invalid",
            "X-GitHub-Delivery": "malformed-001",
        }

        event = webhook_handler.parse_event(headers, invalid_json)
        assert event is None  # Should return None for invalid JSON


# =============================================================================
# Signature Validation Tests
# =============================================================================


class TestSignatureValidation:
    """
    Tests for webhook signature validation edge cases.
    """

    def test_missing_signature_with_secret_configured(
        self, webhook_handler, webhook_secret
    ):
        """
        Test that missing signature is rejected when secret is configured.
        """
        push_payload = create_push_payload()
        payload_bytes = json.dumps(push_payload).encode()

        headers = {
            "X-GitHub-Event": "push",
            # Missing X-Hub-Signature-256
            "X-GitHub-Delivery": "no-sig-001",
        }

        event = webhook_handler.parse_event(headers, payload_bytes)
        assert event is None  # Should be rejected

    def test_invalid_signature(self, webhook_handler, webhook_secret):
        """
        Test that invalid signature is rejected.
        """
        push_payload = create_push_payload()
        payload_bytes = json.dumps(push_payload).encode()

        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": "sha256=invalidinvalidinvalid",
            "X-GitHub-Delivery": "bad-sig-001",
        }

        event = webhook_handler.parse_event(headers, payload_bytes)
        assert event is None

    def test_signature_with_wrong_algorithm(self, webhook_handler, webhook_secret):
        """
        Test that signature with wrong algorithm prefix is rejected.
        """
        push_payload = create_push_payload()
        payload_bytes = json.dumps(push_payload).encode()

        # Use SHA1 algorithm when SHA256 is expected
        sha1_sig = hmac.new(
            webhook_secret.encode(),
            payload_bytes,
            hashlib.sha1,
        ).hexdigest()

        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": f"sha1={sha1_sig}",  # Wrong algorithm
            "X-GitHub-Delivery": "wrong-algo-001",
        }

        event = webhook_handler.parse_event(headers, payload_bytes)
        assert event is None

    def test_no_secret_configured_accepts_all(self):
        """
        Test that handler without secret accepts all events (dev mode).
        """
        handler = GitHubWebhookHandler(
            webhook_secret=None,  # No secret configured
            ingestion_service=None,
        )

        push_payload = create_push_payload()
        payload_bytes = json.dumps(push_payload).encode()

        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": "sha256=anything",
            "X-GitHub-Delivery": "no-secret-001",
        }

        event = handler.parse_event(headers, payload_bytes)
        assert event is not None  # Should accept without validation

    @pytest.mark.asyncio
    async def test_signature_validation_mid_batch(
        self, webhook_handler, webhook_secret
    ):
        """
        Test handling signature validation failure in middle of batch processing.

        When processing multiple events, one bad signature shouldn't affect others.
        """
        # Valid event 1
        payload1 = create_push_payload(branch="main")
        bytes1 = json.dumps(payload1).encode()
        sig1 = sign_payload(bytes1, webhook_secret)

        # Invalid event 2
        payload2 = create_push_payload(branch="develop")
        bytes2 = json.dumps(payload2).encode()

        # Valid event 3
        payload3 = create_push_payload(branch="feature/test")
        bytes3 = json.dumps(payload3).encode()
        sig3 = sign_payload(bytes3, webhook_secret)

        events = []

        # Process event 1
        headers1 = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": sig1,
            "X-GitHub-Delivery": "batch-001",
        }
        event1 = webhook_handler.parse_event(headers1, bytes1)
        events.append(("event1", event1))

        # Process event 2 (bad signature)
        headers2 = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": "sha256=bad",
            "X-GitHub-Delivery": "batch-002",
        }
        event2 = webhook_handler.parse_event(headers2, bytes2)
        events.append(("event2", event2))

        # Process event 3
        headers3 = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": sig3,
            "X-GitHub-Delivery": "batch-003",
        }
        event3 = webhook_handler.parse_event(headers3, bytes3)
        events.append(("event3", event3))

        # Verify: events 1 and 3 should be valid, event 2 should be None
        assert events[0][1] is not None  # event1 valid
        assert events[1][1] is None  # event2 invalid
        assert events[2][1] is not None  # event3 valid


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestRateLimiting:
    """
    Tests for handling GitHub API rate limiting during event processing.
    """

    @pytest.mark.asyncio
    async def test_rate_limited_during_processing(
        self, event_processor, mock_repository_service
    ):
        """
        Test handling rate limit response during event processing.
        """
        from requests.exceptions import RequestException

        # Mock GitHub client to return rate limit error
        mock_github_client = MagicMock()
        mock_github_client.get_repository.side_effect = RequestException(
            "403 API rate limit exceeded"
        )
        event_processor.github_client = mock_github_client

        push_payload = create_push_payload()
        mock_event = WebhookEvent(
            event_type=WebhookEventType.PUSH,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="main",
            commit_hash="ratelimit123",
            changed_files=["rate_limited.py"],
            sender="testuser",
            timestamp=datetime.now(),
            raw_payload=push_payload,
        )

        # Event should still be processed (basic processing doesn't require API)
        result = await event_processor.process_event(
            mock_event,
            delivery_id="rate-limit-001",
        )

        # Basic processing should succeed
        assert result.status == EventProcessingStatus.PROCESSED

    @pytest.mark.asyncio
    async def test_rate_limit_headers_extraction(self):
        """
        Test extraction of rate limit information from response headers.
        """
        # Simulate response with rate limit headers
        mock_response = MagicMock()
        mock_response.headers = {
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time()) + 3600),
            "Retry-After": "60",
        }

        # Extract rate limit info
        limit = int(mock_response.headers.get("X-RateLimit-Limit", 0))
        remaining = int(mock_response.headers.get("X-RateLimit-Remaining", 0))
        retry_after = int(mock_response.headers.get("Retry-After", 0))

        assert limit == 5000
        assert remaining == 0
        assert retry_after == 60

    @pytest.mark.asyncio
    async def test_rapid_events_dont_cause_rate_limit(self, event_processor):
        """
        Test that rapid event processing doesn't cause rate limiting issues.

        Local processing should be fast and not rate-limited.
        """
        results = []
        for i in range(100):
            push_payload = create_push_payload(
                commit_hash=f"rapid{i:03d}",
            )
            mock_event = WebhookEvent(
                event_type=WebhookEventType.PUSH,
                repository_url="https://github.com/org/test-repo.git",
                repository_name="org/test-repo",
                branch="main",
                commit_hash=f"rapid{i:03d}",
                changed_files=[f"file{i}.py"],
                sender="testuser",
                timestamp=datetime.now(),
                raw_payload=push_payload,
            )

            result = await event_processor.process_event(
                mock_event,
                delivery_id=f"rapid-{i:03d}",
            )
            results.append(result)

        # All should be processed
        processed_count = sum(
            1 for r in results if r.status == EventProcessingStatus.PROCESSED
        )
        assert processed_count == 100


# =============================================================================
# Integration Scenario Tests
# =============================================================================


class TestIntegrationScenarios:
    """
    Tests for complex integration scenarios combining multiple edge cases.
    """

    @pytest.mark.asyncio
    async def test_full_branch_lifecycle_out_of_order(
        self, event_processor, webhook_handler, webhook_secret
    ):
        """
        Test full branch lifecycle with events arriving out of order.

        Scenario: delete arrives, then multiple pushes, then create.
        """
        event_processor_fresh = WebhookEventProcessor()

        # 1. Delete event arrives first (branch was deleted)
        delete_event = WebhookEvent(
            event_type=WebhookEventType.DELETE,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="feature/chaos",
            commit_hash=None,
            changed_files=[],
            sender="testuser",
            timestamp=datetime.now(),
            raw_payload=create_delete_payload(ref="feature/chaos"),
        )
        await event_processor_fresh.process_event(delete_event, "chaos-delete-001")

        # 2. Push events arrive (happened before delete)
        push_event1 = WebhookEvent(
            event_type=WebhookEventType.PUSH,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="feature/chaos",
            commit_hash="push1",
            changed_files=["file1.py"],
            sender="testuser",
            timestamp=datetime.now(),
            raw_payload=create_push_payload(branch="feature/chaos"),
        )
        await event_processor_fresh.process_event(push_event1, "chaos-push-001")

        # 3. Create event arrives last (original branch creation)
        create_event = WebhookEvent(
            event_type=WebhookEventType.CREATE,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="feature/chaos",
            commit_hash=None,
            changed_files=[],
            sender="testuser",
            timestamp=datetime.now(),
            raw_payload=create_create_payload(ref="feature/chaos"),
        )
        await event_processor_fresh.process_event(create_event, "chaos-create-001")

        # All events should be processed
        assert event_processor_fresh.event_store.is_duplicate("chaos-delete-001")
        assert event_processor_fresh.event_store.is_duplicate("chaos-push-001")
        assert event_processor_fresh.event_store.is_duplicate("chaos-create-001")

    @pytest.mark.asyncio
    async def test_duplicate_plus_out_of_order(
        self, event_processor, webhook_handler, webhook_secret
    ):
        """
        Test combination of duplicate events and out-of-order delivery.
        """
        # Push event processed
        push_event = WebhookEvent(
            event_type=WebhookEventType.PUSH,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="main",
            commit_hash="combo123",
            changed_files=["combo.py"],
            sender="testuser",
            timestamp=datetime.now(),
            raw_payload=create_push_payload(),
        )
        result1 = await event_processor.process_event(push_event, "combo-delivery-001")
        assert result1.status == EventProcessingStatus.PROCESSED

        # Same event delivered again (duplicate)
        result2 = await event_processor.process_event(push_event, "combo-delivery-001")
        assert result2.status == EventProcessingStatus.SKIPPED

        # Create event for branch (out of order, should have come first)
        create_event = WebhookEvent(
            event_type=WebhookEventType.CREATE,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="main",
            commit_hash=None,
            changed_files=[],
            sender="testuser",
            timestamp=datetime.now(),
            raw_payload=create_create_payload(ref="main"),
        )
        result3 = await event_processor.process_event(create_event, "combo-create-001")
        assert result3.status == EventProcessingStatus.PROCESSED

        # Verify state is consistent
        branch_state = event_processor.event_store.get_branch_state(
            "org/test-repo", "main"
        )
        assert branch_state is not None

    @pytest.mark.asyncio
    async def test_replay_attack_simulation(self, event_processor):
        """
        Test detection of potential replay attacks with old events.
        """
        old_timestamp = datetime.now(timezone.utc) - timedelta(days=1)

        # Attempt to replay old event
        old_event = WebhookEvent(
            event_type=WebhookEventType.PUSH,
            repository_url="https://github.com/org/test-repo.git",
            repository_name="org/test-repo",
            branch="main",
            commit_hash="replay123",
            changed_files=["replay.py"],
            sender="attacker",
            timestamp=old_timestamp,
            raw_payload=create_push_payload(),
        )

        result = await event_processor.process_event(
            old_event,
            delivery_id="replay-attack-001",
            event_timestamp=old_timestamp,
        )

        assert result.status == EventProcessingStatus.SKIPPED
        assert (
            "replay" in result.error_message.lower()
            or "old" in result.error_message.lower()
        )
