# Connector Development Guide

This guide describes patterns and best practices for developing external tool connectors in Project Aura.

## Architecture Overview

External tool connectors provide integrations with third-party services for security, DevOps, and ITSM capabilities. Each connector is an independent module that handles:

- Authentication (API keys, OAuth, tokens)
- API communication (REST, GraphQL)
- Data model transformation
- Error handling and retries
- Rate limiting

### Design Principles

1. **Independence**: Each connector is self-contained (~1000 lines). This isolation allows updates without cross-connector regression.

2. **No Tight Coupling**: Connectors share a base class for common patterns but handle their own specifics. Don't force unnecessary abstraction.

3. **Testability**: Each connector should be testable in isolation with mocked HTTP responses.

4. **Security**: Connectors are only available in ENTERPRISE or HYBRID deployment modes.

## File Structure

```
src/services/
├── external_tool_connectors.py    # Base class and common connectors
├── azure_devops_connector.py      # Azure DevOps integration
├── crowdstrike_connector.py       # CrowdStrike Falcon EDR
├── qualys_connector.py            # Qualys vulnerability scanning
├── snyk_connector.py              # Snyk security scanning
├── splunk_connector.py            # Splunk SIEM
├── terraform_cloud_connector.py   # Terraform Cloud IaC
├── servicenow_connector.py        # ServiceNow ITSM
└── connectors/
    └── __init__.py                # Registry and discovery
```

## Creating a New Connector

### Step 1: Create the Connector File

Create `src/services/{vendor}_connector.py`:

```python
"""
Project Aura - {Vendor} Connector

Implements integration with {Vendor} for {purpose}.

Usage:
    >>> from src.services.{vendor}_connector import {Vendor}Connector
    >>> connector = {Vendor}Connector(api_key="...")
    >>> await connector.health_check()
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import aiohttp

from src.services.external_tool_connectors import (
    ConnectorResult,
    ConnectorStatus,
    ExternalToolConnector,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class {Vendor}Item:
    """Data model for {Vendor} items."""

    id: str
    name: str
    # Add vendor-specific fields


class {Vendor}Status(Enum):
    """Status values for {Vendor}."""

    ACTIVE = "active"
    INACTIVE = "inactive"


# =============================================================================
# Connector Implementation
# =============================================================================


class {Vendor}Connector(ExternalToolConnector):
    """
    {Vendor} connector for {description}.

    Authentication:
        - API Key: Passed via X-API-Key header

    Rate Limits:
        - {rate limit info}

    Reference:
        {API documentation URL}
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.vendor.com",
        timeout_seconds: float = 30.0,
    ) -> None:
        super().__init__(name="{vendor}", timeout_seconds=timeout_seconds)
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def _get_headers(self) -> dict[str, str]:
        """Get common request headers."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def health_check(self) -> bool:
        """Check API connectivity and authentication."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self._base_url}/health",
                    headers=self._get_headers(),
                ) as response:
                    if response.status == 200:
                        self._status = ConnectorStatus.CONNECTED
                        return True
                    elif response.status == 401:
                        self._status = ConnectorStatus.AUTH_FAILED
                        self._last_error = "Authentication failed"
                        return False
                    else:
                        self._status = ConnectorStatus.ERROR
                        self._last_error = f"HTTP {response.status}"
                        return False
        except Exception as e:
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            logger.error(f"{Vendor} health check failed: {e}")
            return False

    async def get_items(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> ConnectorResult:
        """
        Fetch items from {Vendor}.

        Args:
            limit: Maximum items to return
            offset: Pagination offset

        Returns:
            ConnectorResult with items data
        """
        import time
        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self._base_url}/items",
                    headers=self._get_headers(),
                    params={"limit": limit, "offset": offset},
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000

                    if response.status == 200:
                        data = await response.json()
                        self._record_request(latency_ms, success=True)
                        return ConnectorResult(
                            success=True,
                            data={"items": data},
                            status_code=200,
                            latency_ms=latency_ms,
                        )
                    else:
                        error_text = await response.text()
                        self._record_request(latency_ms, success=False)
                        return ConnectorResult(
                            success=False,
                            error=error_text,
                            status_code=response.status,
                            latency_ms=latency_ms,
                        )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, success=False)
            logger.error(f"Failed to get items from {Vendor}: {e}")
            return ConnectorResult(success=False, error=str(e))
```

### Step 2: Add to Registry

Update `src/services/connectors/__init__.py`:

```python
CONNECTOR_REGISTRY: Dict[str, Dict] = {
    # ... existing connectors ...

    "{vendor}": {
        "module": "src.services.{vendor}_connector",
        "class": "{Vendor}Connector",
        "category": "security",  # or "devops", "itsm", "notifications"
        "description": "{Vendor} integration for {purpose}",
        "auth_methods": ["api_key"],
        "data_models": ["{Vendor}Item"],
    },
}
```

### Step 3: Create Tests

Create `tests/test_{vendor}_connector.py`:

```python
"""Tests for {Vendor} connector."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.{vendor}_connector import {Vendor}Connector


class Test{Vendor}Connector:
    """Tests for {Vendor}Connector."""

    @pytest.fixture
    def connector(self):
        """Create connector instance for testing."""
        return {Vendor}Connector(
            api_key="test-api-key",
            base_url="https://api.test.vendor.com",
        )

    @pytest.fixture
    def mock_response(self):
        """Create mock HTTP response."""
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(return_value={"items": []})
        response.text = AsyncMock(return_value="")
        return response

    @pytest.mark.asyncio
    async def test_health_check_success(self, connector, mock_response):
        """Test successful health check."""
        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            result = await connector.health_check()

            assert result is True
            assert connector.status.value == "connected"

    @pytest.mark.asyncio
    async def test_health_check_auth_failure(self, connector, mock_response):
        """Test health check with auth failure."""
        mock_response.status = 401

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            result = await connector.health_check()

            assert result is False
            assert connector.status.value == "auth_failed"

    @pytest.mark.asyncio
    async def test_get_items_success(self, connector, mock_response):
        """Test fetching items."""
        mock_response.json = AsyncMock(return_value=[
            {"id": "1", "name": "Item 1"},
            {"id": "2", "name": "Item 2"},
        ])

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            result = await connector.get_items(limit=10)

            assert result.success is True
            assert len(result.data["items"]) == 2
```

## Common Patterns

### Authentication

```python
# API Key in header
headers = {"X-API-Key": self._api_key}

# Bearer token
headers = {"Authorization": f"Bearer {self._token}"}

# Basic auth
import base64
credentials = base64.b64encode(f"{user}:{password}".encode()).decode()
headers = {"Authorization": f"Basic {credentials}"}

# OAuth 2.0
headers = {"Authorization": f"Bearer {self._access_token}"}
```

### Pagination

```python
async def get_all_items(self) -> list:
    """Fetch all items with pagination."""
    all_items = []
    offset = 0
    limit = 100

    while True:
        result = await self.get_items(limit=limit, offset=offset)
        if not result.success:
            break

        items = result.data.get("items", [])
        if not items:
            break

        all_items.extend(items)
        offset += limit

        # Respect rate limits
        await asyncio.sleep(0.1)

    return all_items
```

### Rate Limiting

```python
import asyncio
from datetime import datetime, timedelta

class RateLimitedConnector(ExternalToolConnector):
    def __init__(self, requests_per_minute: int = 60):
        self._rate_limit = requests_per_minute
        self._request_times: list[datetime] = []

    async def _wait_for_rate_limit(self) -> None:
        """Wait if rate limit would be exceeded."""
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)

        # Remove old requests
        self._request_times = [t for t in self._request_times if t > cutoff]

        if len(self._request_times) >= self._rate_limit:
            # Wait until oldest request expires
            wait_time = (self._request_times[0] - cutoff).total_seconds()
            await asyncio.sleep(wait_time)

        self._request_times.append(now)
```

### Error Handling

```python
async def _make_request(
    self,
    method: str,
    path: str,
    **kwargs,
) -> ConnectorResult:
    """Make HTTP request with standard error handling."""
    import time
    start_time = time.time()
    url = f"{self._base_url}{path}"

    try:
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.request(method, url, **kwargs) as response:
                latency_ms = (time.time() - start_time) * 1000

                # Handle rate limiting
                if response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    self._status = ConnectorStatus.RATE_LIMITED
                    return ConnectorResult(
                        success=False,
                        error=f"Rate limited, retry after {retry_after}s",
                        status_code=429,
                        latency_ms=latency_ms,
                    )

                # Handle auth errors
                if response.status == 401:
                    self._status = ConnectorStatus.AUTH_FAILED
                    return ConnectorResult(
                        success=False,
                        error="Authentication failed",
                        status_code=401,
                        latency_ms=latency_ms,
                    )

                # Handle success
                if 200 <= response.status < 300:
                    data = await response.json()
                    self._record_request(latency_ms, success=True)
                    return ConnectorResult(
                        success=True,
                        data=data,
                        status_code=response.status,
                        latency_ms=latency_ms,
                    )

                # Handle other errors
                error_text = await response.text()
                self._record_request(latency_ms, success=False)
                return ConnectorResult(
                    success=False,
                    error=error_text,
                    status_code=response.status,
                    latency_ms=latency_ms,
                )

    except asyncio.TimeoutError:
        return ConnectorResult(success=False, error="Request timeout")
    except aiohttp.ClientError as e:
        return ConnectorResult(success=False, error=f"Connection error: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in {self.name} connector")
        return ConnectorResult(success=False, error=str(e))
```

## Checklist

Before submitting a new connector:

- [ ] Inherits from `ExternalToolConnector`
- [ ] Implements `health_check()` method
- [ ] Uses `ConnectorResult` for all responses
- [ ] Records metrics via `_record_request()`
- [ ] Handles authentication errors (401)
- [ ] Handles rate limiting (429)
- [ ] Has comprehensive docstrings
- [ ] Added to `CONNECTOR_REGISTRY`
- [ ] Has unit tests with mocked HTTP
- [ ] Has integration test (can be skipped in CI)
- [ ] Documented rate limits and quotas

## Related Documentation

- [ADR-023: External Tool Integration](../architecture-decisions/ADR-023-external-tool-integration.md)
- [ADR-046: Support Ticketing Connectors](../architecture-decisions/ADR-046-support-ticketing-connectors.md)
- [Connector Registry](../../src/services/connectors/__init__.py)
