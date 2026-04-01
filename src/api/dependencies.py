"""
Project Aura - FastAPI Dependency Injection

Centralized service factories using @lru_cache for singleton behavior.
Enables clean dependency injection with Depends() and easy test overrides
via app.dependency_overrides[get_service] = mock_service.

Usage in endpoints:
    from src.api.dependencies import get_hitl_service
    from fastapi import Depends

    @router.get("/approvals")
    async def list_approvals(
        service: HITLApprovalService = Depends(get_hitl_service)
    ):
        return await service.get_all_requests()

Usage in tests:
    from fastapi.testclient import TestClient
    from src.api.dependencies import get_hitl_service

    def test_approvals(app, mock_hitl_service):
        app.dependency_overrides[get_hitl_service] = lambda: mock_hitl_service
        client = TestClient(app)
        response = client.get("/api/v1/approvals")
        ...
"""

import logging
import os
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.anomaly_detection_service import AnomalyDetectionService
    from src.services.api_rate_limiter import SlidingWindowRateLimiter
    from src.services.hitl_approval_service import HITLApprovalService
    from src.services.notification_service import NotificationService
    from src.services.realtime_monitoring_integration import (
        RealTimeMonitoringIntegration,
    )

logger = logging.getLogger(__name__)


# =============================================================================
# HITL Approval Service
# =============================================================================


@lru_cache(maxsize=1)
def get_hitl_service() -> "HITLApprovalService":
    """
    Get singleton HITL approval service instance.

    Uses @lru_cache for singleton behavior. The service mode (MOCK vs AWS)
    is determined by environment variables at creation time.

    Returns:
        HITLApprovalService: Singleton service instance

    Override in tests:
        app.dependency_overrides[get_hitl_service] = lambda: mock_service
    """
    from src.services.hitl_approval_service import HITLApprovalService, HITLMode

    # Determine mode based on AWS environment
    has_dynamodb = bool(os.environ.get("AWS_REGION"))
    mode = HITLMode.AWS if has_dynamodb else HITLMode.MOCK

    logger.info(f"Creating HITLApprovalService (mode={mode.value})")
    return HITLApprovalService(mode=mode)


def clear_hitl_service_cache() -> None:
    """Clear the HITL service cache. Used for testing only."""
    get_hitl_service.cache_clear()


# =============================================================================
# Notification Service
# =============================================================================


@lru_cache(maxsize=1)
def get_notification_service() -> "NotificationService":
    """
    Get singleton notification service instance.

    Configured based on HITL_SNS_TOPIC_ARN environment variable.

    Returns:
        NotificationService: Singleton service instance
    """
    from src.services.notification_service import NotificationMode, NotificationService

    sns_topic_arn = os.environ.get("HITL_SNS_TOPIC_ARN")
    mode = NotificationMode.AWS if sns_topic_arn else NotificationMode.MOCK

    logger.info(f"Creating NotificationService (mode={mode.value})")
    return NotificationService(
        mode=mode,
        sns_topic_arn=sns_topic_arn,
        ses_sender_email=os.environ.get("SES_SENDER_EMAIL"),
        dashboard_url=os.environ.get(
            "HITL_DASHBOARD_URL", "https://app.aura.local/approvals"
        ),
    )


def clear_notification_service_cache() -> None:
    """Clear the notification service cache. Used for testing only."""
    get_notification_service.cache_clear()


# =============================================================================
# Rate Limiter
# =============================================================================

# Flag to disable rate limiting in tests
_rate_limiting_disabled: bool = False


@lru_cache(maxsize=1)
def get_rate_limiter() -> "SlidingWindowRateLimiter":
    """
    Get singleton rate limiter instance.

    Returns:
        SlidingWindowRateLimiter: Singleton rate limiter instance
    """
    from src.services.api_rate_limiter import SlidingWindowRateLimiter

    logger.info("Creating SlidingWindowRateLimiter")
    return SlidingWindowRateLimiter()


def clear_rate_limiter_cache() -> None:
    """Clear the rate limiter cache. Used for testing only."""
    get_rate_limiter.cache_clear()


def is_rate_limiting_disabled() -> bool:
    """Check if rate limiting is disabled (for tests)."""
    return _rate_limiting_disabled


def disable_rate_limiting() -> None:
    """Disable rate limiting. Used for testing only."""
    global _rate_limiting_disabled
    _rate_limiting_disabled = True


def enable_rate_limiting() -> None:
    """Re-enable rate limiting. Used for testing only."""
    global _rate_limiting_disabled
    _rate_limiting_disabled = False


# =============================================================================
# Anomaly Detection Services
# =============================================================================

# These are initialized during lifespan and stored here for access
_anomaly_detector: "AnomalyDetectionService | None" = None
_monitoring_integration: "RealTimeMonitoringIntegration | None" = None


def get_anomaly_detector() -> "AnomalyDetectionService | None":
    """Get the anomaly detector instance (set during lifespan startup)."""
    return _anomaly_detector


def set_anomaly_detector(detector: "AnomalyDetectionService | None") -> None:
    """Set the anomaly detector instance. Called during lifespan startup."""
    global _anomaly_detector
    _anomaly_detector = detector


def get_monitoring_integration() -> "RealTimeMonitoringIntegration | None":
    """Get the monitoring integration instance (set during lifespan startup)."""
    return _monitoring_integration


def set_monitoring_integration(
    integration: "RealTimeMonitoringIntegration | None",
) -> None:
    """Set the monitoring integration instance. Called during lifespan startup."""
    global _monitoring_integration
    _monitoring_integration = integration


# =============================================================================
# Test Utilities
# =============================================================================


def clear_all_caches() -> None:
    """
    Clear all service caches. Used for test isolation.

    Call this in test fixtures to ensure clean state between tests.
    """
    clear_hitl_service_cache()
    clear_notification_service_cache()
    clear_rate_limiter_cache()
    enable_rate_limiting()
