"""
Customer Feedback Service.

Collects and manages customer feedback for the beta program:
- In-app feedback submissions
- NPS (Net Promoter Score) surveys
- Feature requests and bug reports
- Usage analytics aggregation

Supports both SaaS (multi-tenant) and self-hosted deployments.
"""

import base64
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """Types of feedback that can be submitted."""

    GENERAL = "general"
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"
    NPS_SURVEY = "nps_survey"
    USABILITY = "usability"
    DOCUMENTATION = "documentation"
    PERFORMANCE = "performance"


class FeedbackStatus(str, Enum):
    """Status of feedback items."""

    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    IN_REVIEW = "in_review"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WONT_FIX = "wont_fix"
    DUPLICATE = "duplicate"


class FeedbackPriority(str, Enum):
    """Priority levels for feedback."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FeedbackItem:
    """A single feedback submission."""

    feedback_id: str
    customer_id: str
    user_id: str
    user_email: str
    feedback_type: FeedbackType
    title: str
    description: str
    status: FeedbackStatus = FeedbackStatus.NEW
    priority: FeedbackPriority = FeedbackPriority.MEDIUM
    nps_score: Optional[int] = None  # 0-10 for NPS surveys
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    page_url: Optional[str] = None
    browser_info: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    response: Optional[str] = None


@dataclass
class NPSSurveyResult:
    """NPS survey aggregation result."""

    total_responses: int
    promoters: int  # 9-10
    passives: int  # 7-8
    detractors: int  # 0-6
    nps_score: float  # (promoters - detractors) / total * 100
    average_score: float
    period_start: datetime
    period_end: datetime


@dataclass
class FeedbackSummary:
    """Summary of feedback for a customer or overall."""

    total_feedback: int
    by_type: Dict[str, int]
    by_status: Dict[str, int]
    by_priority: Dict[str, int]
    nps: Optional[NPSSurveyResult]
    recent_feedback: List[FeedbackItem]
    trending_tags: List[str]


class FeedbackService:
    """
    Service for managing customer feedback.

    In production, persists to DynamoDB. In test/mock mode,
    stores feedback in memory.
    """

    def __init__(self, mode: str = "mock") -> None:
        """
        Initialize the feedback service.

        Args:
            mode: "mock" for testing, "aws" for production
        """
        self.mode = mode
        self._feedback_store: Dict[str, FeedbackItem] = {}
        self._table_name = os.getenv(
            "FEEDBACK_TABLE_NAME",
            f"aura-feedback-{os.getenv('ENVIRONMENT', 'dev')}",
        )

        if mode == "aws":
            import boto3

            self._dynamodb = boto3.resource("dynamodb")
            self._table = self._dynamodb.Table(self._table_name)

    async def submit_feedback(
        self,
        customer_id: str,
        user_id: str,
        user_email: str,
        feedback_type: FeedbackType,
        title: str,
        description: str,
        nps_score: Optional[int] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        page_url: Optional[str] = None,
        browser_info: Optional[str] = None,
    ) -> FeedbackItem:
        """
        Submit new feedback.

        Args:
            customer_id: Customer organization ID
            user_id: User who submitted feedback
            user_email: User's email for follow-up
            feedback_type: Type of feedback
            title: Short title/summary
            description: Detailed description
            nps_score: NPS score (0-10) for NPS surveys
            tags: Optional tags for categorization
            metadata: Additional metadata (feature name, etc.)
            page_url: Page where feedback was submitted
            browser_info: Browser/OS information

        Returns:
            Created FeedbackItem
        """
        feedback_id = f"fb_{uuid.uuid4().hex[:12]}"

        # Validate NPS score if provided
        if nps_score is not None and (nps_score < 0 or nps_score > 10):
            raise ValueError("NPS score must be between 0 and 10")

        # Auto-set priority based on type
        priority = FeedbackPriority.MEDIUM
        if feedback_type == FeedbackType.BUG_REPORT:
            priority = FeedbackPriority.HIGH
        elif feedback_type == FeedbackType.NPS_SURVEY and nps_score is not None:
            if nps_score <= 4:
                priority = FeedbackPriority.HIGH  # Detractor needs attention

        feedback = FeedbackItem(
            feedback_id=feedback_id,
            customer_id=customer_id,
            user_id=user_id,
            user_email=user_email,
            feedback_type=feedback_type,
            title=title,
            description=description,
            priority=priority,
            nps_score=nps_score,
            tags=tags or [],
            metadata=metadata or {},
            page_url=page_url,
            browser_info=browser_info,
        )

        await self._save_feedback(feedback)
        logger.info(
            f"Feedback submitted: {feedback_id} by {user_email} ({feedback_type.value})"
        )

        return feedback

    async def get_feedback(self, feedback_id: str) -> Optional[FeedbackItem]:
        """Get a feedback item by ID."""
        if self.mode == "mock":
            return self._feedback_store.get(feedback_id)

        try:
            response = self._table.get_item(Key={"feedback_id": feedback_id})
            if "Item" in response:
                return self._item_to_feedback(response["Item"])
            return None
        except Exception as e:
            logger.error(f"Error getting feedback {feedback_id}: {e}")
            return None

    async def list_feedback(
        self,
        customer_id: Optional[str] = None,
        feedback_type: Optional[FeedbackType] = None,
        status: Optional[FeedbackStatus] = None,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> Tuple[List[FeedbackItem], Optional[str]]:
        """
        List feedback with optional filters using cursor-based pagination.

        Industry-standard cursor pagination using DynamoDB's LastEvaluatedKey,
        eliminating wasteful over-fetching of offset-based pagination.

        Args:
            customer_id: Filter by customer
            feedback_type: Filter by type
            status: Filter by status
            limit: Max results to return
            cursor: Base64-encoded pagination cursor from previous response

        Returns:
            Tuple of (list of matching feedback items, next_cursor or None)
        """
        if self.mode == "mock":
            items = list(self._feedback_store.values())

            # Apply filters
            if customer_id:
                items = [f for f in items if f.customer_id == customer_id]
            if feedback_type:
                items = [f for f in items if f.feedback_type == feedback_type]
            if status:
                items = [f for f in items if f.status == status]

            # Sort by created_at descending
            items.sort(key=lambda x: x.created_at, reverse=True)

            # Simple cursor simulation for mock mode using index
            start_idx = 0
            if cursor:
                try:
                    start_idx = int(base64.b64decode(cursor).decode())
                except Exception:
                    start_idx = 0

            result = items[start_idx : start_idx + limit]
            next_cursor = None
            if start_idx + limit < len(items):
                next_cursor = base64.b64encode(str(start_idx + limit).encode()).decode()

            return result, next_cursor

        # AWS DynamoDB implementation with cursor-based pagination
        try:
            # Build filter expression
            filter_parts = []
            expression_values = {}

            if customer_id:
                filter_parts.append("customer_id = :cid")
                expression_values[":cid"] = customer_id
            if feedback_type:
                filter_parts.append("feedback_type = :ftype")
                expression_values[":ftype"] = feedback_type.value
            if status:
                filter_parts.append("#status = :status")
                expression_values[":status"] = status.value

            scan_kwargs: Dict[str, Any] = {"Limit": limit}

            if filter_parts:
                scan_kwargs["FilterExpression"] = " AND ".join(filter_parts)
                scan_kwargs["ExpressionAttributeValues"] = expression_values
                if status:
                    scan_kwargs["ExpressionAttributeNames"] = {"#status": "status"}

            # Apply cursor if provided
            if cursor:
                try:
                    exclusive_start_key = json.loads(base64.b64decode(cursor).decode())
                    scan_kwargs["ExclusiveStartKey"] = exclusive_start_key
                except Exception as e:
                    logger.warning(f"Invalid cursor, starting from beginning: {e}")

            response = self._table.scan(**scan_kwargs)
            items = [self._item_to_feedback(item) for item in response.get("Items", [])]
            items.sort(key=lambda x: x.created_at, reverse=True)

            # Generate next cursor if there are more results
            next_cursor = None
            if "LastEvaluatedKey" in response:
                next_cursor = base64.b64encode(
                    json.dumps(response["LastEvaluatedKey"]).encode()
                ).decode()

            return items, next_cursor

        except Exception as e:
            logger.error(f"Error listing feedback: {e}")
            return [], None

    async def update_feedback_status(
        self,
        feedback_id: str,
        status: FeedbackStatus,
        response: Optional[str] = None,
    ) -> Optional[FeedbackItem]:
        """
        Update feedback status and optionally add a response.

        Args:
            feedback_id: Feedback ID to update
            status: New status
            response: Optional response to customer

        Returns:
            Updated FeedbackItem or None if not found
        """
        feedback = await self.get_feedback(feedback_id)
        if not feedback:
            return None

        feedback.status = status
        feedback.updated_at = datetime.now(timezone.utc)

        if response:
            feedback.response = response

        if status in (FeedbackStatus.COMPLETED, FeedbackStatus.WONT_FIX):
            feedback.resolved_at = datetime.now(timezone.utc)

        await self._save_feedback(feedback)
        logger.info(f"Feedback {feedback_id} status updated to {status.value}")

        return feedback

    async def get_nps_results(
        self,
        customer_id: Optional[str] = None,
        days: int = 30,
    ) -> NPSSurveyResult:
        """
        Calculate NPS results for a time period.

        Args:
            customer_id: Optional customer filter
            days: Number of days to include

        Returns:
            NPSSurveyResult with calculated NPS
        """
        period_end = datetime.now(timezone.utc)
        period_start = period_end - timedelta(days=days)

        # Get NPS feedback
        all_feedback, _ = await self.list_feedback(
            customer_id=customer_id,
            feedback_type=FeedbackType.NPS_SURVEY,
            limit=10000,
        )

        # Filter by date range
        nps_feedback = [
            f
            for f in all_feedback
            if f.created_at >= period_start
            and f.created_at <= period_end
            and f.nps_score is not None
        ]

        if not nps_feedback:
            return NPSSurveyResult(
                total_responses=0,
                promoters=0,
                passives=0,
                detractors=0,
                nps_score=0.0,
                average_score=0.0,
                period_start=period_start,
                period_end=period_end,
            )

        # Calculate NPS (nps_score is guaranteed non-None from filter above)
        promoters = sum(
            1 for f in nps_feedback if f.nps_score is not None and f.nps_score >= 9
        )
        passives = sum(
            1 for f in nps_feedback if f.nps_score is not None and 7 <= f.nps_score <= 8
        )
        detractors = sum(
            1 for f in nps_feedback if f.nps_score is not None and f.nps_score <= 6
        )
        total = len(nps_feedback)

        nps_score = ((promoters - detractors) / total) * 100
        average_score = (
            sum(f.nps_score for f in nps_feedback if f.nps_score is not None) / total
        )

        return NPSSurveyResult(
            total_responses=total,
            promoters=promoters,
            passives=passives,
            detractors=detractors,
            nps_score=round(nps_score, 1),
            average_score=round(average_score, 1),
            period_start=period_start,
            period_end=period_end,
        )

    async def get_feedback_summary(
        self,
        customer_id: Optional[str] = None,
        days: int = 30,
    ) -> FeedbackSummary:
        """
        Get a summary of feedback.

        Args:
            customer_id: Optional customer filter
            days: Number of days to include

        Returns:
            FeedbackSummary with aggregated stats
        """
        period_start = datetime.now(timezone.utc) - timedelta(days=days)

        all_feedback, _ = await self.list_feedback(
            customer_id=customer_id,
            limit=10000,
        )

        # Filter by date
        recent = [f for f in all_feedback if f.created_at >= period_start]

        # Aggregate by type
        by_type: Dict[str, int] = {}
        for f in recent:
            by_type[f.feedback_type.value] = by_type.get(f.feedback_type.value, 0) + 1

        # Aggregate by status
        by_status: Dict[str, int] = {}
        for f in recent:
            by_status[f.status.value] = by_status.get(f.status.value, 0) + 1

        # Aggregate by priority
        by_priority: Dict[str, int] = {}
        for f in recent:
            by_priority[f.priority.value] = by_priority.get(f.priority.value, 0) + 1

        # Get trending tags
        tag_counts: Dict[str, int] = {}
        for f in recent:
            for tag in f.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        trending_tags = sorted(
            tag_counts.keys(), key=lambda t: tag_counts[t], reverse=True
        )[:10]

        # Get NPS results
        nps = await self.get_nps_results(customer_id, days)

        return FeedbackSummary(
            total_feedback=len(recent),
            by_type=by_type,
            by_status=by_status,
            by_priority=by_priority,
            nps=nps if nps.total_responses > 0 else None,
            recent_feedback=recent[:10],
            trending_tags=trending_tags,
        )

    async def _save_feedback(self, feedback: FeedbackItem) -> None:
        """Save feedback to storage."""
        if self.mode == "mock":
            self._feedback_store[feedback.feedback_id] = feedback
            return

        try:
            item: dict[str, Any] = {
                "feedback_id": feedback.feedback_id,
                "customer_id": feedback.customer_id,
                "user_id": feedback.user_id,
                "user_email": feedback.user_email,
                "feedback_type": feedback.feedback_type.value,
                "title": feedback.title,
                "description": feedback.description,
                "status": feedback.status.value,
                "priority": feedback.priority.value,
                "tags": feedback.tags,
                "metadata": feedback.metadata,
                "created_at": feedback.created_at.isoformat(),
            }

            if feedback.nps_score is not None:
                item["nps_score"] = feedback.nps_score
            if feedback.page_url:
                item["page_url"] = feedback.page_url
            if feedback.browser_info:
                item["browser_info"] = feedback.browser_info
            if feedback.updated_at:
                item["updated_at"] = feedback.updated_at.isoformat()
            if feedback.resolved_at:
                item["resolved_at"] = feedback.resolved_at.isoformat()
            if feedback.response:
                item["response"] = feedback.response

            self._table.put_item(Item=item)

        except Exception as e:
            logger.error(f"Error saving feedback: {e}")
            raise

    def _item_to_feedback(self, item: Dict[str, Any]) -> FeedbackItem:
        """Convert DynamoDB item to FeedbackItem."""
        return FeedbackItem(
            feedback_id=item["feedback_id"],
            customer_id=item["customer_id"],
            user_id=item["user_id"],
            user_email=item["user_email"],
            feedback_type=FeedbackType(item["feedback_type"]),
            title=item["title"],
            description=item["description"],
            status=FeedbackStatus(item["status"]),
            priority=FeedbackPriority(item["priority"]),
            nps_score=item.get("nps_score"),
            tags=item.get("tags", []),
            metadata=item.get("metadata", {}),
            page_url=item.get("page_url"),
            browser_info=item.get("browser_info"),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=(
                datetime.fromisoformat(item["updated_at"])
                if item.get("updated_at")
                else None
            ),
            resolved_at=(
                datetime.fromisoformat(item["resolved_at"])
                if item.get("resolved_at")
                else None
            ),
            response=item.get("response"),
        )


# =============================================================================
# Singleton Instance
# =============================================================================

_service: Optional[FeedbackService] = None


def get_feedback_service(mode: Optional[str] = None) -> FeedbackService:
    """Get the singleton feedback service instance."""
    global _service
    if _service is None:
        resolved_mode = mode or os.getenv("FEEDBACK_MODE", "mock") or "mock"
        _service = FeedbackService(mode=resolved_mode)
    return _service
