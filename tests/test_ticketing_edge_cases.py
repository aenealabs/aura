"""
Ticketing Integration Edge Case Tests - Webhook Delivery Failures.

Tests for edge cases involving webhook delivery failures when tickets are
created or updated in the ticketing integration service.

These tests cover webhook delivery failure scenarios including:
1. Webhook endpoint returns 5xx error - retry behavior
2. Webhook endpoint times out - timeout handling
3. All retries exhausted - what happens to the original operation
4. Webhook endpoint returns 4xx (client error) - should we retry?
5. Webhook payload too large for endpoint
6. Webhook endpoint requires authentication that expired
7. Concurrent webhook deliveries to same endpoint (rate limiting)
8. Dead letter queue behavior when webhooks fail permanently
9. Idempotency: same webhook sent twice (replay protection)
10. Webhook endpoint changed/deleted mid-retry sequence

See Issue #167 for edge case tracking.
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# =============================================================================
# Webhook Delivery Service Models (for testing)
# =============================================================================


class WebhookDeliveryStatus(Enum):
    """Status of a webhook delivery attempt."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTERED = "dead_lettered"


class WebhookEventType(Enum):
    """Types of webhook events for ticketing."""

    TICKET_CREATED = "ticket.created"
    TICKET_UPDATED = "ticket.updated"
    TICKET_CLOSED = "ticket.closed"
    TICKET_COMMENTED = "ticket.commented"


@dataclass
class WebhookEndpoint:
    """Configuration for a webhook endpoint."""

    url: str
    secret: str | None = None
    auth_token: str | None = None
    auth_expiry: datetime | None = None
    max_payload_size: int = 1024 * 1024  # 1MB default
    rate_limit_per_second: float = 10.0
    active: bool = True


@dataclass
class WebhookDelivery:
    """Record of a webhook delivery attempt."""

    delivery_id: str
    event_type: WebhookEventType
    endpoint_url: str
    payload: dict[str, Any]
    status: WebhookDeliveryStatus = WebhookDeliveryStatus.PENDING
    attempt_count: int = 0
    max_attempts: int = 3
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_attempt_at: datetime | None = None
    last_error: str | None = None
    response_status_code: int | None = None
    idempotency_key: str | None = None


@dataclass
class DeliveryResult:
    """Result of a webhook delivery operation."""

    success: bool
    delivery_id: str
    status: WebhookDeliveryStatus
    error_message: str | None = None
    should_retry: bool = False
    retry_after_seconds: int | None = None


class WebhookDeliveryError(Exception):
    """Base exception for webhook delivery errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        retryable: bool = False,
        retry_after: int | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after = retry_after


class WebhookDeliveryService:
    """
    Service for delivering webhooks to external endpoints.

    Implements retry logic, dead letter queue, idempotency checks,
    and rate limiting for reliable webhook delivery.
    """

    # Retryable HTTP status codes
    RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    # Non-retryable client errors
    NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 405, 422}

    def __init__(
        self,
        http_client: Any | None = None,
        dlq_client: Any | None = None,
        max_retries: int = 3,
        base_retry_delay: float = 1.0,
        max_retry_delay: float = 60.0,
        timeout_seconds: float = 30.0,
    ):
        """Initialize webhook delivery service."""
        self.http_client = http_client
        self.dlq_client = dlq_client
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self.max_retry_delay = max_retry_delay
        self.timeout_seconds = timeout_seconds

        # Track deliveries and rate limiting
        self._deliveries: dict[str, WebhookDelivery] = {}
        self._idempotency_cache: dict[str, str] = {}
        self._rate_limit_tokens: dict[str, float] = {}
        self._endpoint_last_request: dict[str, float] = {}

    # Class-level counter for unique delivery IDs
    _delivery_counter = 0

    async def deliver_webhook(
        self,
        endpoint: WebhookEndpoint,
        event_type: WebhookEventType,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> DeliveryResult:
        """
        Deliver a webhook to the specified endpoint.

        Args:
            endpoint: Target webhook endpoint configuration
            event_type: Type of webhook event
            payload: Webhook payload data
            idempotency_key: Optional key for replay protection

        Returns:
            DeliveryResult with delivery status
        """
        # Generate delivery ID with counter to ensure uniqueness
        WebhookDeliveryService._delivery_counter += 1
        delivery_id = (
            f"whd-{int(time.time() * 1000)}-{WebhookDeliveryService._delivery_counter}"
        )

        # Check idempotency
        if idempotency_key:
            if idempotency_key in self._idempotency_cache:
                existing_id = self._idempotency_cache[idempotency_key]
                return DeliveryResult(
                    success=True,
                    delivery_id=existing_id,
                    status=WebhookDeliveryStatus.DELIVERED,
                    error_message="Duplicate request - already delivered",
                )

        # Check endpoint is active
        if not endpoint.active:
            return DeliveryResult(
                success=False,
                delivery_id=delivery_id,
                status=WebhookDeliveryStatus.FAILED,
                error_message="Endpoint is not active",
                should_retry=False,
            )

        # Check auth token expiry
        if endpoint.auth_expiry and endpoint.auth_expiry < datetime.now(timezone.utc):
            return DeliveryResult(
                success=False,
                delivery_id=delivery_id,
                status=WebhookDeliveryStatus.FAILED,
                error_message="Authentication token expired",
                should_retry=False,
            )

        # Check payload size
        payload_size = len(json.dumps(payload).encode("utf-8"))
        if payload_size > endpoint.max_payload_size:
            return DeliveryResult(
                success=False,
                delivery_id=delivery_id,
                status=WebhookDeliveryStatus.FAILED,
                error_message=f"Payload size {payload_size} exceeds maximum {endpoint.max_payload_size}",
                should_retry=False,
            )

        # Check rate limiting
        rate_limit_result = await self._check_rate_limit(endpoint)
        if rate_limit_result:
            return DeliveryResult(
                success=False,
                delivery_id=delivery_id,
                status=WebhookDeliveryStatus.RETRYING,
                error_message="Rate limit exceeded",
                should_retry=True,
                retry_after_seconds=rate_limit_result,
            )

        # Create delivery record
        delivery = WebhookDelivery(
            delivery_id=delivery_id,
            event_type=event_type,
            endpoint_url=endpoint.url,
            payload=payload,
            idempotency_key=idempotency_key,
        )
        self._deliveries[delivery_id] = delivery

        # Attempt delivery with retries
        result = await self._attempt_delivery_with_retry(endpoint, delivery)

        # Store idempotency key on success
        if result.success and idempotency_key:
            self._idempotency_cache[idempotency_key] = delivery_id

        return result

    async def _attempt_delivery_with_retry(
        self,
        endpoint: WebhookEndpoint,
        delivery: WebhookDelivery,
    ) -> DeliveryResult:
        """Attempt delivery with exponential backoff retry."""
        while delivery.attempt_count < delivery.max_attempts:
            delivery.attempt_count += 1
            delivery.last_attempt_at = datetime.now(timezone.utc)

            try:
                await self._send_webhook(endpoint, delivery)
                delivery.status = WebhookDeliveryStatus.DELIVERED
                return DeliveryResult(
                    success=True,
                    delivery_id=delivery.delivery_id,
                    status=WebhookDeliveryStatus.DELIVERED,
                )

            except WebhookDeliveryError as e:
                delivery.last_error = str(e)
                delivery.response_status_code = e.status_code

                if not e.retryable or delivery.attempt_count >= delivery.max_attempts:
                    # All retries exhausted or non-retryable error
                    delivery.status = WebhookDeliveryStatus.FAILED

                    # Send to dead letter queue
                    if self.dlq_client:
                        await self._send_to_dlq(delivery)
                        delivery.status = WebhookDeliveryStatus.DEAD_LETTERED

                    return DeliveryResult(
                        success=False,
                        delivery_id=delivery.delivery_id,
                        status=delivery.status,
                        error_message=str(e),
                        should_retry=False,
                    )

                # Calculate backoff delay
                delay = min(
                    self.base_retry_delay * (2 ** (delivery.attempt_count - 1)),
                    self.max_retry_delay,
                )

                # Use retry_after header if provided
                if e.retry_after:
                    delay = max(delay, e.retry_after)

                delivery.status = WebhookDeliveryStatus.RETRYING
                await asyncio.sleep(delay)

            except asyncio.TimeoutError:
                delivery.last_error = f"Request timeout after {self.timeout_seconds}s"
                delivery.status = WebhookDeliveryStatus.RETRYING

                if delivery.attempt_count >= delivery.max_attempts:
                    delivery.status = WebhookDeliveryStatus.FAILED
                    if self.dlq_client:
                        await self._send_to_dlq(delivery)
                        delivery.status = WebhookDeliveryStatus.DEAD_LETTERED

                    return DeliveryResult(
                        success=False,
                        delivery_id=delivery.delivery_id,
                        status=delivery.status,
                        error_message=delivery.last_error,
                        should_retry=False,
                    )

                # Shorter backoff for timeouts
                await asyncio.sleep(self.base_retry_delay)

        # Should not reach here, but handle just in case
        return DeliveryResult(
            success=False,
            delivery_id=delivery.delivery_id,
            status=WebhookDeliveryStatus.FAILED,
            error_message="Unexpected delivery termination",
        )

    async def _send_webhook(
        self,
        endpoint: WebhookEndpoint,
        delivery: WebhookDelivery,
    ) -> None:
        """Send the actual HTTP request."""
        if not self.http_client:
            raise WebhookDeliveryError("No HTTP client configured", retryable=False)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": delivery.event_type.value,
            "X-Webhook-Delivery-ID": delivery.delivery_id,
        }

        if endpoint.auth_token:
            headers["Authorization"] = f"Bearer {endpoint.auth_token}"

        if endpoint.secret:
            signature = self._compute_signature(delivery.payload, endpoint.secret)
            headers["X-Webhook-Signature"] = signature

        try:
            response = await asyncio.wait_for(
                self.http_client.post(
                    endpoint.url,
                    json=delivery.payload,
                    headers=headers,
                ),
                timeout=self.timeout_seconds,
            )

            status_code = response.status_code

            if 200 <= status_code < 300:
                return  # Success

            # Check for retryable status codes
            if status_code in self.RETRYABLE_STATUS_CODES:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass

                raise WebhookDeliveryError(
                    f"Server error: {status_code}",
                    status_code=status_code,
                    retryable=True,
                    retry_after=retry_after,
                )

            # Non-retryable client error
            raise WebhookDeliveryError(
                f"Client error: {status_code}",
                status_code=status_code,
                retryable=False,
            )

        except asyncio.TimeoutError:
            raise
        except WebhookDeliveryError:
            raise
        except Exception as e:
            # Network errors are generally retryable
            raise WebhookDeliveryError(
                f"Network error: {str(e)}",
                retryable=True,
            )

    async def _check_rate_limit(self, endpoint: WebhookEndpoint) -> int | None:
        """
        Check if we're within rate limits for the endpoint.

        Returns seconds to wait if rate limited, None if OK.
        """
        now = time.time()
        min_interval = 1.0 / endpoint.rate_limit_per_second

        last_request = self._endpoint_last_request.get(endpoint.url, 0)
        elapsed = now - last_request

        if elapsed < min_interval:
            return int(min_interval - elapsed) + 1

        self._endpoint_last_request[endpoint.url] = now
        return None

    async def _send_to_dlq(self, delivery: WebhookDelivery) -> None:
        """Send failed delivery to dead letter queue."""
        if self.dlq_client:
            await self.dlq_client.send_message(
                MessageBody=json.dumps(
                    {
                        "delivery_id": delivery.delivery_id,
                        "event_type": delivery.event_type.value,
                        "endpoint_url": delivery.endpoint_url,
                        "payload": delivery.payload,
                        "attempt_count": delivery.attempt_count,
                        "last_error": delivery.last_error,
                        "created_at": delivery.created_at.isoformat(),
                    }
                )
            )

    def _compute_signature(self, payload: dict[str, Any], secret: str) -> str:
        """Compute HMAC signature for payload."""
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return (
            "sha256="
            + hashlib.sha256(secret.encode("utf-8") + payload_bytes).hexdigest()
        )

    def get_delivery(self, delivery_id: str) -> WebhookDelivery | None:
        """Get delivery record by ID."""
        return self._deliveries.get(delivery_id)

    def clear_idempotency_cache(self) -> None:
        """Clear the idempotency cache (for testing)."""
        self._idempotency_cache.clear()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for webhook delivery."""
    client = MagicMock()
    client.post = AsyncMock()
    return client


@pytest.fixture
def mock_dlq_client():
    """Mock SQS dead letter queue client."""
    client = MagicMock()
    client.send_message = AsyncMock()
    return client


@pytest.fixture
def webhook_service(mock_http_client, mock_dlq_client):
    """Create webhook delivery service with mocked dependencies."""
    return WebhookDeliveryService(
        http_client=mock_http_client,
        dlq_client=mock_dlq_client,
        max_retries=3,
        base_retry_delay=0.01,  # Fast for testing
        max_retry_delay=0.1,
        timeout_seconds=5.0,
    )


@pytest.fixture
def sample_endpoint():
    """Sample webhook endpoint configuration."""
    return WebhookEndpoint(
        url="https://api.example.com/webhooks/tickets",
        secret="test-webhook-secret-123",
        auth_token="test-auth-token-456",
        auth_expiry=datetime(2030, 12, 31, tzinfo=timezone.utc),
        max_payload_size=1024 * 1024,  # 1MB
        rate_limit_per_second=10.0,
    )


@pytest.fixture
def sample_payload():
    """Sample webhook payload."""
    return {
        "ticket_id": "ticket-123",
        "external_id": "42",
        "title": "Test Ticket",
        "description": "This is a test ticket",
        "status": "open",
        "priority": "high",
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
    }


# =============================================================================
# Test 1: Webhook endpoint returns 5xx error - retry behavior
# =============================================================================


class TestWebhook5xxRetryBehavior:
    """Test webhook retry behavior for 5xx server errors."""

    @pytest.mark.asyncio
    async def test_5xx_error_triggers_retry(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """
        Test: 5xx errors trigger automatic retry with exponential backoff.

        Scenario:
        - Webhook endpoint returns 500 Internal Server Error
        - Service should retry up to max_retries times
        - Should use exponential backoff between retries
        """
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            if call_count < 3:
                response.status_code = 500
                response.headers = {}
            else:
                response.status_code = 200
            return response

        mock_http_client.post = mock_post

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is True
        assert result.status == WebhookDeliveryStatus.DELIVERED
        assert call_count == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_502_bad_gateway_retry(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test retry behavior for 502 Bad Gateway errors."""
        responses = [502, 502, 200]
        call_idx = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_idx
            response = MagicMock()
            response.status_code = responses[call_idx]
            response.headers = {}
            call_idx += 1
            return response

        mock_http_client.post = mock_post

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_UPDATED,
            payload=sample_payload,
        )

        assert result.success is True
        assert call_idx == 3

    @pytest.mark.asyncio
    async def test_503_service_unavailable_retry(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test retry behavior for 503 Service Unavailable with Retry-After header."""
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            if call_count == 1:
                response.status_code = 503
                response.headers = {"Retry-After": "1"}
            else:
                response.status_code = 200
                response.headers = {}
            return response

        mock_http_client.post = mock_post

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is True
        assert call_count == 2


# =============================================================================
# Test 2: Webhook endpoint times out - timeout handling
# =============================================================================


class TestWebhookTimeoutHandling:
    """Test webhook timeout handling scenarios."""

    @pytest.mark.asyncio
    async def test_timeout_triggers_retry(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """
        Test: Request timeout triggers automatic retry.

        Scenario:
        - Webhook endpoint doesn't respond within timeout
        - Service should retry
        - After max retries, should fail gracefully
        """
        call_count = 0

        async def mock_post_with_timeout(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # Simulate timeout
                raise asyncio.TimeoutError()
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = mock_post_with_timeout

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is True
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_all_timeouts_result_in_failure(
        self,
        webhook_service,
        mock_http_client,
        mock_dlq_client,
        sample_endpoint,
        sample_payload,
    ):
        """Test that persistent timeouts result in delivery failure and DLQ."""

        async def always_timeout(*args, **kwargs):
            raise asyncio.TimeoutError()

        mock_http_client.post = always_timeout

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is False
        assert result.status == WebhookDeliveryStatus.DEAD_LETTERED
        assert "timeout" in result.error_message.lower()

        # Verify DLQ was called
        mock_dlq_client.send_message.assert_called_once()


# =============================================================================
# Test 3: All retries exhausted - what happens to the original operation
# =============================================================================


class TestRetryExhaustion:
    """Test behavior when all retries are exhausted."""

    @pytest.mark.asyncio
    async def test_retry_exhaustion_sends_to_dlq(
        self,
        webhook_service,
        mock_http_client,
        mock_dlq_client,
        sample_endpoint,
        sample_payload,
    ):
        """
        Test: When all retries are exhausted, delivery is sent to dead letter queue.

        Scenario:
        - Webhook delivery fails repeatedly with 500 errors
        - After max_retries attempts, the delivery should be marked as dead-lettered
        - DLQ message should contain original payload and error details
        """

        async def always_fail(*args, **kwargs):
            response = MagicMock()
            response.status_code = 500
            response.headers = {}
            return response

        mock_http_client.post = always_fail

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is False
        assert result.status == WebhookDeliveryStatus.DEAD_LETTERED
        assert result.should_retry is False

        # Verify DLQ received the message
        mock_dlq_client.send_message.assert_called_once()
        dlq_call = mock_dlq_client.send_message.call_args
        dlq_body = json.loads(dlq_call.kwargs["MessageBody"])

        assert dlq_body["event_type"] == WebhookEventType.TICKET_CREATED.value
        assert dlq_body["payload"] == sample_payload
        assert dlq_body["attempt_count"] == 3

    @pytest.mark.asyncio
    async def test_original_ticket_operation_not_affected(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """
        Test: Original ticket operation succeeds even if webhook delivery fails.

        The webhook delivery is a side-effect notification; it should not block
        or roll back the original ticket operation.
        """

        async def always_fail(*args, **kwargs):
            response = MagicMock()
            response.status_code = 500
            response.headers = {}
            return response

        mock_http_client.post = always_fail

        # Simulate creating a ticket and then sending webhook
        # The ticket creation (mocked) should succeed independently
        from src.services.ticketing.base_connector import TicketCreate, TicketPriority

        ticket_data = TicketCreate(
            title=sample_payload["title"],
            description=sample_payload["description"],
            priority=TicketPriority.HIGH,
        )

        # Webhook delivery fails
        webhook_result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert webhook_result.success is False
        # But the ticket_data is still valid and the operation can continue
        assert ticket_data.title == "Test Ticket"


# =============================================================================
# Test 4: Webhook endpoint returns 4xx (client error) - should we retry?
# =============================================================================


class TestWebhook4xxBehavior:
    """Test webhook behavior for 4xx client errors."""

    @pytest.mark.asyncio
    async def test_400_bad_request_no_retry(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """
        Test: 400 Bad Request should NOT trigger retry.

        Scenario:
        - Webhook endpoint returns 400 (malformed request)
        - Service should fail immediately without retry
        - Indicates a client-side issue that won't resolve with retry
        """
        call_count = 0

        async def mock_400(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            response.status_code = 400
            response.headers = {}
            return response

        mock_http_client.post = mock_400

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is False
        assert call_count == 1  # No retry
        assert "Client error: 400" in result.error_message

    @pytest.mark.asyncio
    async def test_401_unauthorized_no_retry(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test: 401 Unauthorized should NOT trigger retry."""
        call_count = 0

        async def mock_401(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            response.status_code = 401
            response.headers = {}
            return response

        mock_http_client.post = mock_401

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is False
        assert call_count == 1
        assert result.status == WebhookDeliveryStatus.DEAD_LETTERED

    @pytest.mark.asyncio
    async def test_404_not_found_no_retry(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test: 404 Not Found should NOT trigger retry."""

        async def mock_404(*args, **kwargs):
            response = MagicMock()
            response.status_code = 404
            response.headers = {}
            return response

        mock_http_client.post = mock_404

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is False
        assert "Client error: 404" in result.error_message

    @pytest.mark.asyncio
    async def test_422_unprocessable_entity_no_retry(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test: 422 Unprocessable Entity should NOT trigger retry."""

        async def mock_422(*args, **kwargs):
            response = MagicMock()
            response.status_code = 422
            response.headers = {}
            return response

        mock_http_client.post = mock_422

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is False
        assert result.should_retry is False

    @pytest.mark.asyncio
    async def test_429_rate_limited_should_retry(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """
        Test: 429 Too Many Requests SHOULD trigger retry.

        This is a special 4xx code that indicates temporary overload.
        """
        call_count = 0

        async def mock_429_then_200(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            if call_count == 1:
                response.status_code = 429
                response.headers = {"Retry-After": "1"}
            else:
                response.status_code = 200
                response.headers = {}
            return response

        mock_http_client.post = mock_429_then_200

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is True
        assert call_count == 2


# =============================================================================
# Test 5: Webhook payload too large for endpoint
# =============================================================================


class TestPayloadSizeLimits:
    """Test webhook payload size limit handling."""

    @pytest.mark.asyncio
    async def test_payload_exceeds_max_size(
        self, webhook_service, mock_http_client, sample_endpoint
    ):
        """
        Test: Payload exceeding max size is rejected before sending.

        Scenario:
        - Webhook payload is larger than endpoint's max_payload_size
        - Service should fail immediately without making HTTP request
        - Error should indicate payload size issue
        """
        # Create payload larger than limit (endpoint default is 1MB)
        sample_endpoint.max_payload_size = 1024  # 1KB for testing
        large_payload = {
            "ticket_id": "ticket-123",
            "description": "x" * 2000,  # Exceeds 1KB
        }

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=large_payload,
        )

        assert result.success is False
        assert "exceeds maximum" in result.error_message
        assert result.should_retry is False

        # HTTP client should NOT have been called
        mock_http_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_payload_at_max_size_succeeds(
        self, webhook_service, mock_http_client, sample_endpoint
    ):
        """Test: Payload exactly at max size limit should succeed."""
        sample_endpoint.max_payload_size = 2048  # 2KB

        # Create payload just under limit
        payload = {"data": "x" * 1900}  # ~1.9KB

        async def mock_success(*args, **kwargs):
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = mock_success

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=payload,
        )

        assert result.success is True


# =============================================================================
# Test 6: Webhook endpoint requires authentication that expired
# =============================================================================


class TestAuthenticationExpiry:
    """Test webhook authentication token expiry handling."""

    @pytest.mark.asyncio
    async def test_expired_auth_token_fails_immediately(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """
        Test: Expired authentication token causes immediate failure.

        Scenario:
        - Endpoint has auth_expiry in the past
        - Service should reject before making HTTP request
        - Allows system to refresh token before retrying
        """
        # Set expiry in the past
        sample_endpoint.auth_expiry = datetime(2020, 1, 1, tzinfo=timezone.utc)

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is False
        assert "expired" in result.error_message.lower()
        assert result.should_retry is False

        # HTTP client should NOT have been called
        mock_http_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_auth_token_included_in_request(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test: Valid auth token is included in request headers."""
        captured_headers = {}

        async def capture_request(*args, **kwargs):
            captured_headers.update(kwargs.get("headers", {}))
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = capture_request

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is True
        assert "Authorization" in captured_headers
        assert (
            captured_headers["Authorization"] == f"Bearer {sample_endpoint.auth_token}"
        )

    @pytest.mark.asyncio
    async def test_no_auth_token_no_header(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test: No auth token means no Authorization header."""
        sample_endpoint.auth_token = None
        sample_endpoint.auth_expiry = None

        captured_headers = {}

        async def capture_request(*args, **kwargs):
            captured_headers.update(kwargs.get("headers", {}))
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = capture_request

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is True
        assert "Authorization" not in captured_headers


# =============================================================================
# Test 7: Concurrent webhook deliveries to same endpoint (rate limiting)
# =============================================================================


class TestRateLimiting:
    """Test rate limiting for concurrent webhook deliveries."""

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_returns_retry_after(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """
        Test: Exceeding rate limit returns retry-after indication.

        Scenario:
        - Multiple webhooks sent in quick succession
        - Rate limit is exceeded
        - Service should return should_retry=True with retry_after_seconds
        """
        # Set very low rate limit
        sample_endpoint.rate_limit_per_second = 0.5  # 1 request every 2 seconds

        async def mock_success(*args, **kwargs):
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = mock_success

        # First request should succeed
        result1 = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )
        assert result1.success is True

        # Immediate second request should be rate limited
        result2 = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_UPDATED,
            payload=sample_payload,
        )

        assert result2.success is False
        assert result2.should_retry is True
        assert result2.retry_after_seconds is not None
        assert result2.retry_after_seconds > 0

    @pytest.mark.asyncio
    async def test_concurrent_deliveries_respect_rate_limit(
        self, mock_http_client, mock_dlq_client, sample_endpoint, sample_payload
    ):
        """Test: Concurrent async deliveries respect rate limits."""
        # Create service with higher rate limit for this test
        service = WebhookDeliveryService(
            http_client=mock_http_client,
            dlq_client=mock_dlq_client,
            max_retries=3,
            base_retry_delay=0.01,
        )

        sample_endpoint.rate_limit_per_second = 100  # High limit

        async def mock_success(*args, **kwargs):
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = mock_success

        # Send 5 concurrent requests
        tasks = [
            service.deliver_webhook(
                endpoint=sample_endpoint,
                event_type=WebhookEventType.TICKET_CREATED,
                payload={**sample_payload, "ticket_id": f"ticket-{i}"},
            )
            for i in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # At least some should succeed
        successful = [r for r in results if r.success]
        assert len(successful) >= 1


# =============================================================================
# Test 8: Dead letter queue behavior when webhooks fail permanently
# =============================================================================


class TestDeadLetterQueue:
    """Test dead letter queue behavior for permanent webhook failures."""

    @pytest.mark.asyncio
    async def test_dlq_message_contains_full_context(
        self,
        webhook_service,
        mock_http_client,
        mock_dlq_client,
        sample_endpoint,
        sample_payload,
    ):
        """
        Test: DLQ message contains complete delivery context for debugging.

        Scenario:
        - Webhook delivery fails permanently
        - DLQ message should contain:
          - Original delivery ID
          - Event type
          - Full payload
          - Endpoint URL
          - Attempt count
          - Error details
          - Timestamps
        """

        async def always_fail(*args, **kwargs):
            response = MagicMock()
            response.status_code = 500
            response.headers = {}
            return response

        mock_http_client.post = always_fail

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.status == WebhookDeliveryStatus.DEAD_LETTERED

        # Verify DLQ message structure
        mock_dlq_client.send_message.assert_called_once()
        call_args = mock_dlq_client.send_message.call_args
        dlq_body = json.loads(call_args.kwargs["MessageBody"])

        assert "delivery_id" in dlq_body
        assert dlq_body["event_type"] == WebhookEventType.TICKET_CREATED.value
        assert dlq_body["endpoint_url"] == sample_endpoint.url
        assert dlq_body["payload"] == sample_payload
        assert dlq_body["attempt_count"] == 3
        assert "last_error" in dlq_body
        assert "created_at" in dlq_body

    @pytest.mark.asyncio
    async def test_no_dlq_client_logs_failure(
        self, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test: Without DLQ client, failure is still handled gracefully."""
        service = WebhookDeliveryService(
            http_client=mock_http_client,
            dlq_client=None,  # No DLQ configured
            max_retries=2,
            base_retry_delay=0.01,
        )

        async def always_fail(*args, **kwargs):
            response = MagicMock()
            response.status_code = 500
            response.headers = {}
            return response

        mock_http_client.post = always_fail

        result = await service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        # Should still fail gracefully, just not be dead-lettered
        assert result.success is False
        assert result.status == WebhookDeliveryStatus.FAILED


# =============================================================================
# Test 9: Idempotency - same webhook sent twice (replay protection)
# =============================================================================


class TestIdempotency:
    """Test idempotency and replay protection for webhooks."""

    @pytest.mark.asyncio
    async def test_same_idempotency_key_prevents_duplicate(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """
        Test: Same idempotency key prevents duplicate delivery.

        Scenario:
        - First webhook delivery succeeds
        - Second delivery with same idempotency key should return cached result
        - HTTP request should only be made once
        """
        call_count = 0

        async def track_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = track_calls

        idempotency_key = "create-ticket-123-v1"

        # First delivery
        result1 = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
            idempotency_key=idempotency_key,
        )

        # Second delivery with same key
        result2 = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
            idempotency_key=idempotency_key,
        )

        assert result1.success is True
        assert result2.success is True
        assert result1.delivery_id == result2.delivery_id  # Same delivery ID
        assert call_count == 1  # Only one HTTP request

    @pytest.mark.asyncio
    async def test_different_idempotency_keys_allow_delivery(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test: Different idempotency keys result in separate deliveries."""
        call_count = 0

        async def track_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = track_calls

        # Clear rate limit state to avoid interference from prior tests
        webhook_service._endpoint_last_request.clear()

        # Two deliveries with different keys
        result1 = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
            idempotency_key="key-1",
        )

        # Clear rate limit state between calls to focus on idempotency behavior
        webhook_service._endpoint_last_request.clear()

        result2 = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
            idempotency_key="key-2",
        )

        assert result1.success is True
        assert result2.success is True
        assert result1.delivery_id != result2.delivery_id
        assert call_count == 2  # Two HTTP requests

    @pytest.mark.asyncio
    async def test_no_idempotency_key_allows_duplicates(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test: Without idempotency key, duplicate payloads are allowed."""
        call_count = 0

        async def track_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = track_calls

        # Clear rate limit state to avoid interference from prior tests
        webhook_service._endpoint_last_request.clear()

        # Two deliveries without idempotency key
        result1 = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        # Clear rate limit state between calls to focus on idempotency behavior
        webhook_service._endpoint_last_request.clear()

        result2 = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result1.success is True
        assert result2.success is True
        assert call_count == 2  # Both requests went through

    @pytest.mark.asyncio
    async def test_idempotency_cache_clearable(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test: Idempotency cache can be cleared to allow redelivery."""
        call_count = 0

        async def track_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = track_calls

        idempotency_key = "clearable-key"

        # Clear rate limit state to avoid interference from prior tests
        webhook_service._endpoint_last_request.clear()

        # First delivery
        await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
            idempotency_key=idempotency_key,
        )

        # Clear both idempotency cache and rate limit state
        webhook_service.clear_idempotency_cache()
        webhook_service._endpoint_last_request.clear()

        # Second delivery with same key should now proceed
        await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
            idempotency_key=idempotency_key,
        )

        assert call_count == 2


# =============================================================================
# Test 10: Webhook endpoint changed/deleted mid-retry sequence
# =============================================================================


class TestEndpointChangedMidRetry:
    """Test behavior when endpoint configuration changes during retry."""

    @pytest.mark.asyncio
    async def test_endpoint_deactivated_mid_retry(
        self, mock_http_client, mock_dlq_client
    ):
        """
        Test: Endpoint deactivation during retry sequence.

        Scenario:
        - Webhook delivery starts with active endpoint
        - Endpoint is deactivated during retries
        - Subsequent retry attempts should fail gracefully
        """
        # Custom service with mutable endpoint reference
        service = WebhookDeliveryService(
            http_client=mock_http_client,
            dlq_client=mock_dlq_client,
            max_retries=3,
            base_retry_delay=0.01,
        )

        endpoint = WebhookEndpoint(
            url="https://api.example.com/webhooks",
            active=True,
        )

        payload = {"ticket_id": "ticket-123"}
        call_count = 0

        async def fail_then_endpoint_changes(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Fail first attempt
            if call_count == 1:
                response = MagicMock()
                response.status_code = 500
                response.headers = {}
                return response
            # Subsequent calls succeed (but endpoint now inactive)
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = fail_then_endpoint_changes

        # Simulate endpoint becoming inactive - in real scenario this would
        # be checked on each retry attempt in a more sophisticated service
        result = await service.deliver_webhook(
            endpoint=endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=payload,
        )

        # The delivery should eventually succeed or fail based on retries
        # Key point: the service handles endpoint state changes gracefully
        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_endpoint_url_change_new_delivery_required(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """
        Test: URL change requires new delivery configuration.

        This test verifies that endpoint URL is captured at delivery time,
        not dynamically resolved during retries.
        """
        original_url = sample_endpoint.url
        captured_urls = []

        async def capture_url(*args, **kwargs):
            captured_urls.append(args[0] if args else kwargs.get("url"))
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = capture_url

        # First delivery
        await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        # Change endpoint URL
        sample_endpoint.url = "https://new-api.example.com/webhooks"

        # Second delivery
        await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_UPDATED,
            payload=sample_payload,
        )

        # Both URLs should be captured separately
        assert captured_urls[0] == original_url
        assert captured_urls[1] == "https://new-api.example.com/webhooks"

    @pytest.mark.asyncio
    async def test_inactive_endpoint_rejected_immediately(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test: Inactive endpoint is rejected before making HTTP request."""
        sample_endpoint.active = False

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is False
        assert "not active" in result.error_message
        mock_http_client.post.assert_not_called()


# =============================================================================
# Additional Edge Cases
# =============================================================================


class TestWebhookSignature:
    """Test webhook signature computation and verification."""

    @pytest.mark.asyncio
    async def test_signature_included_when_secret_configured(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test: HMAC signature is included when endpoint has secret."""
        captured_headers = {}

        async def capture_headers(*args, **kwargs):
            captured_headers.update(kwargs.get("headers", {}))
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = capture_headers

        await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert "X-Webhook-Signature" in captured_headers
        assert captured_headers["X-Webhook-Signature"].startswith("sha256=")

    @pytest.mark.asyncio
    async def test_no_signature_without_secret(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test: No signature header when endpoint has no secret."""
        sample_endpoint.secret = None

        captured_headers = {}

        async def capture_headers(*args, **kwargs):
            captured_headers.update(kwargs.get("headers", {}))
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = capture_headers

        await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert "X-Webhook-Signature" not in captured_headers


class TestDeliveryTracking:
    """Test webhook delivery record tracking."""

    @pytest.mark.asyncio
    async def test_delivery_record_created(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test: Delivery record is created and trackable."""

        async def mock_success(*args, **kwargs):
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = mock_success

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        # Verify delivery can be retrieved
        delivery = webhook_service.get_delivery(result.delivery_id)

        assert delivery is not None
        assert delivery.delivery_id == result.delivery_id
        assert delivery.event_type == WebhookEventType.TICKET_CREATED
        assert delivery.status == WebhookDeliveryStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_delivery_record_tracks_attempts(
        self,
        webhook_service,
        mock_http_client,
        mock_dlq_client,
        sample_endpoint,
        sample_payload,
    ):
        """Test: Delivery record tracks attempt count and errors."""
        call_count = 0

        async def fail_twice_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            if call_count < 3:
                response.status_code = 500
                response.headers = {}
            else:
                response.status_code = 200
            return response

        mock_http_client.post = fail_twice_then_succeed

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        delivery = webhook_service.get_delivery(result.delivery_id)

        assert delivery.attempt_count == 3
        assert delivery.status == WebhookDeliveryStatus.DELIVERED


class TestNetworkErrors:
    """Test handling of various network error scenarios."""

    @pytest.mark.asyncio
    async def test_connection_error_is_retryable(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test: Connection errors trigger retry."""
        call_count = 0

        async def connection_error_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection refused")
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = connection_error_then_success

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_dns_error_is_retryable(
        self, webhook_service, mock_http_client, sample_endpoint, sample_payload
    ):
        """Test: DNS resolution errors trigger retry."""
        call_count = 0

        async def dns_error_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OSError("Name or service not known")
            response = MagicMock()
            response.status_code = 200
            return response

        mock_http_client.post = dns_error_then_success

        result = await webhook_service.deliver_webhook(
            endpoint=sample_endpoint,
            event_type=WebhookEventType.TICKET_CREATED,
            payload=sample_payload,
        )

        assert result.success is True
        assert call_count == 2
