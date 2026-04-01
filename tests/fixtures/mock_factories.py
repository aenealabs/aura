"""
Centralized Mock Factories for Project Aura Tests

This module provides reusable mock factories for external dependencies.
Use these factories to ensure consistent, well-tested mock behavior across all tests.

Mock Factory Categories:
    - HTTP Client Mocks: aiohttp, httpx
    - AWS Service Mocks: boto3 clients (see conftest.py for moto-based mocks)
    - External API Mocks: CrowdStrike, Qualys, Splunk, Terraform Cloud, etc.

Usage:
    from tests.fixtures.mock_factories import create_aiohttp_session_mock

    @patch("src.services.crowdstrike_connector.aiohttp.ClientSession")
    def test_something(mock_session_class):
        mock_session_class.return_value = create_aiohttp_session_mock(
            response_status=200,
            response_body={"data": "test"}
        )

Design Principles:
    - Each factory returns a fully configured mock ready for use
    - Factories support common use cases with sensible defaults
    - Error simulation is explicit via parameters (raise_on_request, etc.)
    - Mocks properly implement async context managers where needed
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

# =============================================================================
# aiohttp Mock Factories
# =============================================================================


def create_aiohttp_session_mock(
    response_status: int,
    response_body: str | dict,
    *,
    raise_on_request: Exception | None = None,
    content_type: str = "application/json",
) -> MagicMock:
    """
    Create a properly mocked aiohttp session for async context managers.

    This mock handles the common pattern:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()

    Args:
        response_status: HTTP status code to return
        response_body: Response body (str for text, dict for JSON)
        raise_on_request: Optional exception to raise on request
        content_type: Content-Type header value

    Returns:
        Configured MagicMock that behaves like aiohttp.ClientSession

    Example:
        mock = create_aiohttp_session_mock(200, {"status": "ok"})
        with patch("module.aiohttp.ClientSession", return_value=mock):
            result = await service.fetch_data()
            assert result["status"] == "ok"

    Example with error simulation:
        mock = create_aiohttp_session_mock(
            500,
            {"error": "Internal Server Error"},
            raise_on_request=aiohttp.ClientError("Connection failed")
        )
    """
    mock_response = MagicMock()
    mock_response.status = response_status
    mock_response.headers = {"Content-Type": content_type}

    if isinstance(response_body, dict):
        mock_response.json = AsyncMock(return_value=response_body)
        mock_response.text = AsyncMock(return_value=json.dumps(response_body))
    else:
        mock_response.text = AsyncMock(return_value=response_body)
        mock_response.json = AsyncMock(return_value={"error": response_body})

    # Create context manager for response (async with session.get() as response)
    mock_request_context = MagicMock()

    if raise_on_request:
        mock_request_context.__aenter__ = AsyncMock(side_effect=raise_on_request)
    else:
        mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_request_context.__aexit__ = AsyncMock(return_value=None)

    # Create session instance with all HTTP methods
    mock_session_instance = MagicMock()
    mock_session_instance.get.return_value = mock_request_context
    mock_session_instance.post.return_value = mock_request_context
    mock_session_instance.put.return_value = mock_request_context
    mock_session_instance.patch.return_value = mock_request_context
    mock_session_instance.delete.return_value = mock_request_context
    mock_session_instance.head.return_value = mock_request_context
    mock_session_instance.options.return_value = mock_request_context

    # Create session context manager (async with aiohttp.ClientSession() as session)
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


def create_aiohttp_multi_response_mock(
    responses: list[tuple[int, str | dict]],
) -> MagicMock:
    """
    Create an aiohttp mock that returns different responses on successive calls.

    Useful for testing multi-step API flows like:
    1. Authentication (get token)
    2. List resources (get IDs)
    3. Get resource details

    Args:
        responses: List of (status_code, body) tuples in call order.
                  The last response is repeated if more calls are made.

    Returns:
        Configured MagicMock that cycles through responses

    Example:
        mock = create_aiohttp_multi_response_mock([
            (201, {"access_token": "abc123", "expires_in": 1800}),  # Auth
            (200, {"resources": ["id1", "id2"]}),  # List
            (200, {"device_id": "id1", "hostname": "server01"}),  # Details
        ])
        with patch("module.aiohttp.ClientSession", return_value=mock):
            await connector.authenticate()
            hosts = await connector.list_hosts()
            details = await connector.get_host("id1")
    """
    response_mocks = []
    for status, body in responses:
        resp = MagicMock()
        resp.status = status
        if isinstance(body, dict):
            resp.json = AsyncMock(return_value=body)
            resp.text = AsyncMock(return_value=json.dumps(body))
        else:
            resp.text = AsyncMock(return_value=body)
            resp.json = AsyncMock(return_value={"error": body})
        response_mocks.append(resp)

    call_count = [0]

    def get_next_response(*args: Any, **kwargs: Any) -> MagicMock:
        ctx = MagicMock()
        idx = min(call_count[0], len(response_mocks) - 1)
        ctx.__aenter__ = AsyncMock(return_value=response_mocks[idx])
        ctx.__aexit__ = AsyncMock(return_value=None)
        call_count[0] += 1
        return ctx

    mock_session_instance = MagicMock()
    mock_session_instance.get.side_effect = get_next_response
    mock_session_instance.post.side_effect = get_next_response
    mock_session_instance.put.side_effect = get_next_response
    mock_session_instance.patch.side_effect = get_next_response
    mock_session_instance.delete.side_effect = get_next_response

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


# =============================================================================
# httpx Mock Factories
# =============================================================================


def create_httpx_client_mock(
    response_status: int,
    response_body: str | dict,
    *,
    raise_on_request: Exception | None = None,
) -> MagicMock:
    """
    Create a properly mocked httpx.AsyncClient for async HTTP testing.

    This mock handles the common pattern:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()

    Args:
        response_status: HTTP status code to return
        response_body: Response body (str for text, dict for JSON)
        raise_on_request: Optional exception to raise on request

    Returns:
        Configured MagicMock that behaves like httpx.AsyncClient

    Example:
        mock = create_httpx_client_mock(200, {"cves": [...]})
        with patch("module.httpx.AsyncClient", return_value=mock):
            result = await threat_feed.fetch_nvd_cves()
    """
    mock_response = MagicMock()
    mock_response.status_code = response_status
    mock_response.is_success = 200 <= response_status < 300

    if isinstance(response_body, dict):
        mock_response.json.return_value = response_body
        mock_response.text = json.dumps(response_body)
        mock_response.content = json.dumps(response_body).encode()
    else:
        mock_response.text = response_body
        mock_response.content = response_body.encode() if response_body else b""
        mock_response.json.side_effect = json.JSONDecodeError("Not JSON", "", 0)

    # Create client instance with all HTTP methods
    mock_client_instance = MagicMock()

    if raise_on_request:
        mock_client_instance.get = AsyncMock(side_effect=raise_on_request)
        mock_client_instance.post = AsyncMock(side_effect=raise_on_request)
        mock_client_instance.put = AsyncMock(side_effect=raise_on_request)
        mock_client_instance.patch = AsyncMock(side_effect=raise_on_request)
        mock_client_instance.delete = AsyncMock(side_effect=raise_on_request)
    else:
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.put = AsyncMock(return_value=mock_response)
        mock_client_instance.patch = AsyncMock(return_value=mock_response)
        mock_client_instance.delete = AsyncMock(return_value=mock_response)

    # httpx client is also async context manager
    mock_client_instance.aclose = AsyncMock()
    mock_client_instance.is_closed = False

    # Create client context manager
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    return mock_client


# =============================================================================
# Connector-Specific Response Factories
# =============================================================================


def create_crowdstrike_auth_response() -> tuple[int, dict]:
    """
    Create a standard CrowdStrike OAuth2 token response.

    Returns:
        Tuple of (status_code, response_body) for use with mock factories.

    Example:
        mock = create_aiohttp_multi_response_mock([
            create_crowdstrike_auth_response(),
            (200, {"resources": [...]}),
        ])
    """
    return (
        201,
        {
            "access_token": "test_token_abc123",
            "token_type": "bearer",
            "expires_in": 1800,
        },
    )


def create_crowdstrike_hosts_response(
    device_ids: list[str] | None = None,
) -> tuple[int, dict]:
    """
    Create a CrowdStrike host search response.

    Args:
        device_ids: List of device IDs to include. Defaults to sample IDs.

    Returns:
        Tuple of (status_code, response_body)
    """
    if device_ids is None:
        device_ids = ["device_001", "device_002"]

    return (200, {"resources": device_ids})


def create_qualys_vulnerability_response(
    qid: int = 12345,
    severity: int = 4,
) -> tuple[int, dict]:
    """
    Create a Qualys vulnerability detail response.

    Args:
        qid: Qualys ID for the vulnerability
        severity: Severity level (1-5)

    Returns:
        Tuple of (status_code, response_body)
    """
    return (
        200,
        {
            "KNOWLEDGE_BASE_VULN_LIST_OUTPUT": {
                "RESPONSE": {
                    "VULN_LIST": {
                        "VULN": {
                            "QID": qid,
                            "TITLE": f"Test Vulnerability {qid}",
                            "SEVERITY": severity,
                            "CATEGORY": "Security",
                        }
                    }
                }
            }
        },
    )


def create_terraform_workspace_response(
    workspace_id: str = "ws-test123",
    name: str = "production",
    auto_apply: bool = False,
) -> tuple[int, dict]:
    """
    Create a Terraform Cloud workspace response.

    Args:
        workspace_id: Workspace ID
        name: Workspace name
        auto_apply: Auto-apply setting

    Returns:
        Tuple of (status_code, response_body)
    """
    return (
        200,
        {
            "data": {
                "id": workspace_id,
                "attributes": {
                    "name": name,
                    "auto-apply": auto_apply,
                    "terraform-version": "1.6.0",
                    "resource-count": 50,
                },
            }
        },
    )
