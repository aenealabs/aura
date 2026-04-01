"""
Project Aura - API Anomaly Detection Triggers

Integrates API events with the AnomalyDetectionService to enable real-time
monitoring of:
- HITL approval patterns (approval rate, time-to-approve, critical rejections)
- Webhook processing (event rates, signature failures)
- API health (error rates, latency spikes)

Usage:
    from src.api.anomaly_triggers import AnomalyTriggers

    triggers = AnomalyTriggers(anomaly_detector)

    # Record HITL events
    triggers.record_approval_decision("approved", "critical", approval_time_hours=2.5)
    triggers.record_approval_decision("rejected", "high", approval_time_hours=0.5)

    # Record webhook events
    triggers.record_webhook_event(success=True, event_type="push")
    triggers.record_webhook_event(success=False, event_type="push", error="signature_invalid")

    # Record API request metrics
    await triggers.record_api_request("/api/v1/approvals", latency_ms=150, status_code=200)
"""

import logging
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)


class AnomalyTriggers:
    """
    API event triggers for anomaly detection.

    Connects API activities to the AnomalyDetectionService to detect
    anomalous patterns in real-time.
    """

    # Metric name prefixes for organization
    METRIC_PREFIX_HITL = "hitl"
    METRIC_PREFIX_WEBHOOK = "webhook"
    METRIC_PREFIX_API = "api"
    METRIC_PREFIX_SECURITY = "security"

    def __init__(self, anomaly_detector=None) -> None:
        """
        Initialize anomaly triggers.

        Args:
            anomaly_detector: AnomalyDetectionService instance (optional)
        """
        self.anomaly_detector = anomaly_detector
        self._enabled = anomaly_detector is not None

        if self._enabled:
            logger.info("AnomalyTriggers initialized with anomaly detector")
        else:
            logger.info("AnomalyTriggers initialized in passive mode (no detector)")

    def set_detector(self, anomaly_detector) -> None:
        """Set or update the anomaly detector instance."""
        self.anomaly_detector = anomaly_detector
        self._enabled = anomaly_detector is not None
        logger.info(f"AnomalyTriggers detector updated: enabled={self._enabled}")

    @property
    def enabled(self) -> bool:
        """Check if anomaly detection is enabled."""
        return self._enabled

    # =========================================================================
    # HITL Approval Metrics
    # =========================================================================

    def record_approval_decision(
        self,
        decision: str,
        severity: str,
        approval_time_hours: float | None = None,
        reviewer: str | None = None,
    ) -> None:
        """
        Record a HITL approval decision for anomaly analysis.

        Tracks:
        - Approval/rejection rates (sudden spike in rejections = anomaly)
        - Time-to-approve (critical patches taking too long = anomaly)
        - Critical patch rejections (security concern)

        Args:
            decision: "approved", "rejected", or "cancelled"
            severity: Patch severity (critical, high, medium, low)
            approval_time_hours: Time from request to decision (optional)
            reviewer: Reviewer email (optional, for pattern analysis)
        """
        if not self._enabled:
            return

        try:
            timestamp = datetime.now(timezone.utc)

            # Track decision rate (1 for approved, 0 for rejected)
            decision_value = 1.0 if decision == "approved" else 0.0
            self.anomaly_detector.record_metric(
                metric_name=f"{self.METRIC_PREFIX_HITL}.approval_rate",
                value=decision_value,
                timestamp=timestamp,
            )

            # Track by severity
            self.anomaly_detector.record_metric(
                metric_name=f"{self.METRIC_PREFIX_HITL}.approval_rate.{severity}",
                value=decision_value,
                timestamp=timestamp,
            )

            # Track time-to-approve for approved requests
            if approval_time_hours is not None and decision == "approved":
                self.anomaly_detector.record_metric(
                    metric_name=f"{self.METRIC_PREFIX_HITL}.time_to_approve",
                    value=approval_time_hours,
                    timestamp=timestamp,
                )

            # Flag critical patch rejections as security events
            if decision == "rejected" and severity == "critical":
                self._process_security_event(
                    event_type="critical_patch_rejected",
                    severity="HIGH",
                    description=f"Critical security patch rejected by {reviewer or 'unknown'}",
                    metadata={
                        "reviewer": reviewer,
                        "severity": severity,
                        "decision": decision,
                    },
                )

            logger.debug(
                f"Recorded HITL decision: {decision} (severity={severity}, "
                f"time={approval_time_hours}h)"
            )

        except Exception as e:
            logger.warning(f"Failed to record approval decision: {e}")

    def record_approval_timeout(
        self,
        approval_id: str,
        severity: str,
        pending_hours: float,
    ) -> None:
        """
        Record a HITL approval timeout (request exceeded SLA).

        Args:
            approval_id: The approval request ID
            severity: Patch severity
            pending_hours: How long the request has been pending
        """
        if not self._enabled:
            return

        try:
            # Track timeout count
            self.anomaly_detector.record_metric(
                metric_name=f"{self.METRIC_PREFIX_HITL}.timeout_count",
                value=1.0,
                timestamp=datetime.now(timezone.utc),
            )

            # Critical timeouts are security events
            if severity in ("critical", "high"):
                self._process_security_event(
                    event_type="hitl_timeout",
                    severity="MEDIUM" if severity == "high" else "HIGH",
                    description=(
                        f"HITL approval {approval_id} timed out after {pending_hours:.1f} hours"
                    ),
                    metadata={
                        "approval_id": approval_id,
                        "severity": severity,
                        "pending_hours": pending_hours,
                    },
                )

            logger.warning(
                f"Recorded HITL timeout: {approval_id} (severity={severity}, "
                f"pending={pending_hours:.1f}h)"
            )

        except Exception as e:
            logger.warning(f"Failed to record approval timeout: {e}")

    # =========================================================================
    # Webhook Event Metrics
    # =========================================================================

    def record_webhook_event(
        self,
        success: bool,
        event_type: str,
        error: str | None = None,
        processing_time_ms: float | None = None,
    ) -> None:
        """
        Record a GitHub webhook event for anomaly analysis.

        Tracks:
        - Webhook success rate (sudden failures = anomaly)
        - Event volume (traffic spikes = potential attack)
        - Signature validation failures (security concern)

        Args:
            success: Whether the webhook was processed successfully
            event_type: GitHub event type (push, pull_request, etc.)
            error: Error description if failed (optional)
            processing_time_ms: Processing time in milliseconds (optional)
        """
        if not self._enabled:
            return

        try:
            timestamp = datetime.now(timezone.utc)

            # Track success rate
            self.anomaly_detector.record_metric(
                metric_name=f"{self.METRIC_PREFIX_WEBHOOK}.success_rate",
                value=1.0 if success else 0.0,
                timestamp=timestamp,
            )

            # Track event volume (count = 1 per event)
            self.anomaly_detector.record_metric(
                metric_name=f"{self.METRIC_PREFIX_WEBHOOK}.event_count",
                value=1.0,
                timestamp=timestamp,
            )

            # Track by event type
            self.anomaly_detector.record_metric(
                metric_name=f"{self.METRIC_PREFIX_WEBHOOK}.event_count.{event_type}",
                value=1.0,
                timestamp=timestamp,
            )

            # Track processing time
            if processing_time_ms is not None:
                self.anomaly_detector.record_metric(
                    metric_name=f"{self.METRIC_PREFIX_WEBHOOK}.processing_time_ms",
                    value=processing_time_ms,
                    timestamp=timestamp,
                )

            # Signature failures are security events
            if not success and error == "signature_invalid":
                self._process_security_event(
                    event_type="webhook_signature_failure",
                    severity="HIGH",
                    description=f"GitHub webhook signature validation failed for {event_type} event",
                    metadata={
                        "event_type": event_type,
                        "error": error,
                    },
                )

            logger.debug(
                f"Recorded webhook event: {event_type} (success={success}, "
                f"time={processing_time_ms}ms)"
            )

        except Exception as e:
            logger.warning(f"Failed to record webhook event: {e}")

    # =========================================================================
    # API Request Metrics
    # =========================================================================

    async def record_api_request(
        self,
        endpoint: str,
        latency_ms: float,
        status_code: int,
        method: str = "GET",
    ) -> None:
        """
        Record an API request for anomaly analysis.

        Tracks:
        - Request latency (spikes = performance issues)
        - Error rates (5xx codes = service degradation)
        - Traffic volume (spikes = potential attack or incident)

        Args:
            endpoint: API endpoint path
            latency_ms: Request latency in milliseconds
            status_code: HTTP response status code
            method: HTTP method (GET, POST, etc.)
        """
        if not self._enabled:
            return

        try:
            timestamp = datetime.now(timezone.utc)

            # Normalize endpoint for metric names (remove IDs, special chars)
            metric_endpoint = self._normalize_endpoint(endpoint)

            # Track latency
            self.anomaly_detector.record_metric(
                metric_name=f"{self.METRIC_PREFIX_API}.latency_ms",
                value=latency_ms,
                timestamp=timestamp,
            )

            # Track latency by endpoint
            self.anomaly_detector.record_metric(
                metric_name=f"{self.METRIC_PREFIX_API}.latency_ms.{metric_endpoint}",
                value=latency_ms,
                timestamp=timestamp,
            )

            # Track error rate (5xx = error)
            is_error = status_code >= 500
            self.anomaly_detector.record_metric(
                metric_name=f"{self.METRIC_PREFIX_API}.error_rate",
                value=1.0 if is_error else 0.0,
                timestamp=timestamp,
            )

            # Track request count (for traffic analysis)
            self.anomaly_detector.record_metric(
                metric_name=f"{self.METRIC_PREFIX_API}.request_count",
                value=1.0,
                timestamp=timestamp,
            )

            logger.debug(
                f"Recorded API request: {method} {endpoint} "
                f"(latency={latency_ms}ms, status={status_code})"
            )

        except Exception as e:
            logger.warning(f"Failed to record API request: {e}")

    def record_api_error(
        self,
        endpoint: str,
        error_type: str,
        error_message: str,
        status_code: int = 500,
    ) -> None:
        """
        Record an API error for anomaly analysis.

        Args:
            endpoint: API endpoint that errored
            error_type: Type of error (e.g., "validation", "database", "timeout")
            error_message: Error message
            status_code: HTTP status code returned
        """
        if not self._enabled:
            return

        try:
            timestamp = datetime.now(timezone.utc)

            # Track error by type
            self.anomaly_detector.record_metric(
                metric_name=f"{self.METRIC_PREFIX_API}.error.{error_type}",
                value=1.0,
                timestamp=timestamp,
            )

            # Database or authentication errors may indicate security issues
            if error_type in ("database", "authentication", "authorization"):
                self._process_security_event(
                    event_type=f"api_error_{error_type}",
                    severity="MEDIUM",
                    description=f"API error on {endpoint}: {error_message}",
                    metadata={
                        "endpoint": endpoint,
                        "error_type": error_type,
                        "status_code": status_code,
                    },
                )

            logger.debug(f"Recorded API error: {endpoint} ({error_type})")

        except Exception as e:
            logger.warning(f"Failed to record API error: {e}")

    # =========================================================================
    # Security Event Integration
    # =========================================================================

    def record_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        cve_id: str | None = None,
        affected_components: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record a security event directly.

        Use this for explicit security events detected by the API layer.

        Args:
            event_type: Type of security event
            severity: CRITICAL, HIGH, MEDIUM, LOW
            description: Event description
            cve_id: CVE identifier if applicable
            affected_components: List of affected components
            metadata: Additional event metadata
        """
        self._process_security_event(
            event_type=event_type,
            severity=severity,
            description=description,
            cve_id=cve_id,
            affected_components=affected_components,
            metadata=metadata,
        )

    def _process_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        cve_id: str | None = None,
        affected_components: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Internal method to process security events via anomaly detector."""
        if not self._enabled:
            return

        try:
            import asyncio

            event = {
                "type": event_type,
                "severity": severity,
                "description": description,
                "cve_id": cve_id,
                "affected_components": affected_components or [],
                **(metadata or {}),
            }

            # Use asyncio to call the async method
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, create a task
                asyncio.create_task(self.anomaly_detector.process_security_event(event))
            else:
                # Otherwise, run synchronously
                loop.run_until_complete(
                    self.anomaly_detector.process_security_event(event)
                )

            logger.info(f"Processed security event: {event_type} (severity={severity})")

        except Exception as e:
            logger.warning(f"Failed to process security event: {e}")

    # =========================================================================
    # Middleware / Decorator Support
    # =========================================================================

    def middleware(self, endpoint_prefix: str = "/api"):
        """
        ASGI middleware for automatic request metric collection.

        Usage with FastAPI:
            from fastapi import FastAPI
            from src.api.anomaly_triggers import AnomalyTriggers

            app = FastAPI()
            triggers = AnomalyTriggers(anomaly_detector)
            app.middleware("http")(triggers.middleware("/api"))

        Args:
            endpoint_prefix: Only track endpoints starting with this prefix
        """

        async def middleware_impl(request, call_next):
            # Only track API endpoints
            if not request.url.path.startswith(endpoint_prefix):
                return await call_next(request)

            start_time = time.time()
            response = await call_next(request)
            latency_ms = (time.time() - start_time) * 1000

            # Record the request
            await self.record_api_request(
                endpoint=request.url.path,
                latency_ms=latency_ms,
                status_code=response.status_code,
                method=request.method,
            )

            return response

        return middleware_impl

    def track_request(self, endpoint: str | None = None):
        """
        Decorator for tracking individual endpoint requests.

        Usage:
            @router.get("/example")
            @triggers.track_request("/api/v1/example")
            async def example_endpoint():
                return {"status": "ok"}

        Args:
            endpoint: Override endpoint name (default: uses function name)
        """

        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                status_code = 200

                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:  # noqa: F841
                    status_code = 500
                    raise
                finally:
                    latency_ms = (time.time() - start_time) * 1000
                    endpoint_name = endpoint or func.__name__
                    await self.record_api_request(
                        endpoint=endpoint_name,
                        latency_ms=latency_ms,
                        status_code=status_code,
                    )

            return wrapper

        return decorator

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _normalize_endpoint(self, endpoint: str) -> str:
        """
        Normalize endpoint path for metric names.

        Removes IDs and special characters to group similar endpoints:
        - /api/v1/approvals/abc-123 -> approvals
        - /api/v1/settings/mode -> settings_mode

        Args:
            endpoint: Raw endpoint path

        Returns:
            Normalized metric-safe name
        """
        # Remove common prefixes
        path = endpoint
        for prefix in ["/api/v1/", "/api/", "/"]:
            if path.startswith(prefix):
                path = path[len(prefix) :]
                break

        # Split on slashes and filter
        parts = []
        for part in path.split("/"):
            # Skip UUID-like parts and numeric IDs
            if len(part) > 20 or part.isdigit():
                continue
            # Skip common path parameters
            if part.startswith("{") and part.endswith("}"):
                continue
            if part:
                parts.append(part)

        # Join with underscores
        normalized = "_".join(parts) if parts else "root"

        # Sanitize for metric names
        return normalized.replace("-", "_").lower()


# Global triggers instance (set in main.py)
_triggers: AnomalyTriggers | None = None


def get_triggers() -> AnomalyTriggers | None:
    """Get the global AnomalyTriggers instance."""
    return _triggers


def set_triggers(triggers: AnomalyTriggers) -> None:
    """Set the global AnomalyTriggers instance."""
    global _triggers
    _triggers = triggers
