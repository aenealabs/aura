"""
Project Aura - GitHub Webhook Handler

Handles GitHub webhook events for incremental ingestion updates.
Supports push events, pull request events, and repository events.

Author: Project Aura Team
Created: 2025-11-28
Version: 1.0.0
"""

import hashlib
import hmac
import json
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class WebhookEventType(Enum):
    """Supported GitHub webhook event types."""

    PUSH = "push"
    PULL_REQUEST = "pull_request"
    CREATE = "create"  # Branch/tag creation
    DELETE = "delete"  # Branch/tag deletion
    REPOSITORY = "repository"  # Repository events


@dataclass
class WebhookEvent:
    """Parsed webhook event."""

    event_type: WebhookEventType
    repository_url: str
    repository_name: str
    branch: str
    commit_hash: str | None
    changed_files: list[str]
    sender: str
    timestamp: datetime
    raw_payload: dict[str, Any]


class GitHubWebhookHandler:
    """
    GitHub Webhook Handler for Git Ingestion Pipeline.

    Validates webhook signatures, parses events, and triggers
    incremental ingestion for changed files.

    Usage:
        handler = GitHubWebhookHandler(
            webhook_secret="your-webhook-secret",
            ingestion_service=git_ingestion_service
        )

        # In FastAPI/Flask endpoint:
        event = handler.parse_event(headers, body)
        if event:
            await handler.process_event(event)
    """

    def __init__(
        self,
        webhook_secret: str | None = None,
        ingestion_service=None,
        allowed_branches: list[str] | None = None,
    ):
        """
        Initialize webhook handler.

        Args:
            webhook_secret: GitHub webhook secret for signature validation
            ingestion_service: GitIngestionService instance
            allowed_branches: List of branches to process (default: ["main", "master", "develop"])
        """
        self.webhook_secret = webhook_secret
        self.ingestion_service = ingestion_service
        self.allowed_branches = allowed_branches or ["main", "master", "develop"]

        # Event queue for async processing (bounded to prevent unbounded growth)
        self.event_queue: deque[WebhookEvent] = deque(maxlen=1000)

        logger.info("GitHubWebhookHandler initialized")

    def validate_signature(self, payload: bytes, signature: str) -> bool:
        """
        Validate GitHub webhook signature (HMAC-SHA256).

        Args:
            payload: Raw request body
            signature: X-Hub-Signature-256 header value

        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured - skipping validation")
            return True

        if not signature:
            logger.error("Missing webhook signature")
            return False

        # GitHub sends signature as "sha256=<hash>"
        if signature.startswith("sha256="):
            signature = signature[7:]

        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    def parse_event(
        self,
        headers: dict[str, str],
        body: bytes | str,
    ) -> WebhookEvent | None:
        """
        Parse and validate a GitHub webhook event.

        Args:
            headers: HTTP headers
            body: Request body (raw bytes or string)

        Returns:
            Parsed WebhookEvent or None if invalid
        """
        try:
            # Get event type
            event_type_str = headers.get(
                "X-GitHub-Event", headers.get("x-github-event")
            )
            if not event_type_str:
                logger.error("Missing X-GitHub-Event header")
                return None

            # Validate signature
            signature = headers.get(
                "X-Hub-Signature-256", headers.get("x-hub-signature-256")
            )
            payload_bytes = body if isinstance(body, bytes) else body.encode()

            if not self.validate_signature(payload_bytes, signature or ""):
                logger.error("Invalid webhook signature")
                return None

            # Parse payload
            payload = json.loads(body) if isinstance(body, (bytes, str)) else body

            # Map to event type enum
            try:
                event_type = WebhookEventType(event_type_str)
            except ValueError:
                logger.info(f"Unsupported event type: {event_type_str}")
                return None

            # Parse based on event type
            if event_type == WebhookEventType.PUSH:
                return self._parse_push_event(payload, event_type)
            elif event_type == WebhookEventType.PULL_REQUEST:
                return self._parse_pull_request_event(payload, event_type)
            else:
                logger.info(f"Event type {event_type_str} not processed")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON payload: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to parse webhook: {e}", exc_info=True)
            return None

    async def process_event(self, event: WebhookEvent) -> dict[str, Any]:
        """
        Process a webhook event by triggering ingestion.

        Args:
            event: Parsed webhook event

        Returns:
            Processing result with status and details
        """
        try:
            # Check if branch should be processed
            if event.branch not in self.allowed_branches:
                logger.info(f"Skipping branch {event.branch} (not in allowed list)")
                return {
                    "status": "skipped",
                    "reason": f"Branch {event.branch} not in allowed branches",
                }

            # Check if there are files to process
            if not event.changed_files:
                logger.info("No files changed, skipping ingestion")
                return {
                    "status": "skipped",
                    "reason": "No files changed",
                }

            # Trigger incremental ingestion
            if self.ingestion_service:
                logger.info(
                    f"Triggering ingestion for {len(event.changed_files)} files "
                    f"in {event.repository_name}/{event.branch}"
                )

                # Note: In production, this would clone/fetch first
                # For now, we assume the repository is already cloned
                result = await self.ingestion_service.ingest_changes(
                    repository_path=f"/repos/{event.repository_name}",
                    changed_files=event.changed_files,
                    commit_hash=event.commit_hash,
                )

                return {
                    "status": "success" if result.success else "failed",
                    "job_id": result.job_id,
                    "files_processed": result.files_processed,
                    "entities_indexed": result.entities_indexed,
                    "errors": result.errors,
                }
            else:
                # Queue for later processing
                self.event_queue.append(event)
                return {
                    "status": "queued",
                    "queue_position": len(self.event_queue),
                }

        except Exception as e:
            logger.error(f"Failed to process event: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
            }

    def _parse_push_event(
        self,
        payload: dict[str, Any],
        event_type: WebhookEventType,
    ) -> WebhookEvent:
        """Parse a push event payload."""
        repo = payload.get("repository", {})
        ref = payload.get("ref", "")

        # Extract branch from ref (refs/heads/main -> main)
        branch = (
            ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref
        )

        # Collect changed files from commits
        changed_files = set()
        for commit in payload.get("commits", []):
            changed_files.update(commit.get("added", []))
            changed_files.update(commit.get("modified", []))
            # Note: We could also track removed files for cleanup

        return WebhookEvent(
            event_type=event_type,
            repository_url=repo.get("clone_url", repo.get("html_url", "")),
            repository_name=repo.get("full_name", repo.get("name", "")),
            branch=branch,
            commit_hash=payload.get("after"),
            changed_files=list(changed_files),
            sender=payload.get("sender", {}).get("login", "unknown"),
            timestamp=datetime.now(),
            raw_payload=payload,
        )

    def _parse_pull_request_event(
        self,
        payload: dict[str, Any],
        event_type: WebhookEventType,
    ) -> WebhookEvent | None:
        """Parse a pull request event payload."""
        action = payload.get("action")

        # Only process opened, synchronize (new commits), or reopened
        if action not in ["opened", "synchronize", "reopened"]:
            logger.info(f"Skipping PR action: {action}")
            return None

        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        head = pr.get("head", {})

        return WebhookEvent(
            event_type=event_type,
            repository_url=repo.get("clone_url", repo.get("html_url", "")),
            repository_name=repo.get("full_name", repo.get("name", "")),
            branch=head.get("ref", ""),
            commit_hash=head.get("sha"),
            changed_files=[],  # PR events don't include file list
            sender=payload.get("sender", {}).get("login", "unknown"),
            timestamp=datetime.now(),
            raw_payload=payload,
        )

    def get_queue_status(self) -> dict[str, Any]:
        """Get the current event queue status."""
        return {
            "queue_length": len(self.event_queue),
            "events": [
                {
                    "repository": e.repository_name,
                    "branch": e.branch,
                    "files": len(e.changed_files),
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in self.event_queue
            ],
        }

    def clear_queue(self) -> int:
        """Clear the event queue. Returns number of events cleared."""
        count = len(self.event_queue)
        self.event_queue.clear()
        return count
