"""
Project Aura - Test Fixtures

Centralized test fixtures and mock factories for consistent, reusable test infrastructure.

Modules:
    mock_factories: Reusable mock factories for external dependencies (aiohttp, httpx, etc.)

Usage:
    from tests.fixtures.mock_factories import create_aiohttp_session_mock

    @patch("src.services.crowdstrike_connector.aiohttp.ClientSession")
    def test_something(mock_session_class):
        mock_session_class.return_value = create_aiohttp_session_mock(
            response_status=200,
            response_body={"data": "test"}
        )
"""

from tests.fixtures.mock_factories import (
    create_aiohttp_multi_response_mock,
    create_aiohttp_session_mock,
    create_httpx_client_mock,
)

__all__ = [
    "create_aiohttp_session_mock",
    "create_aiohttp_multi_response_mock",
    "create_httpx_client_mock",
]
