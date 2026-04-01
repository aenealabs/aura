"""
Tests for Aura Fivetran Connector.

ADR-048 Phase 5: Fivetran Connector
"""

import pytest
import responses

from src.connector import CONFIGURATION_SCHEMA, AuraConnector


class TestAuraConnectorConfiguration:
    """Tests for connector configuration."""

    def test_configure_success(self):
        """Test successful configuration."""
        connector = AuraConnector()
        config = {
            "server_url": "https://api.aenealabs.com",
            "api_key": "test-api-key",
            "organization_id": "org-123",
        }

        connector.configure(config)

        assert connector.server_url == "https://api.aenealabs.com"
        assert connector.api_key == "test-api-key"
        assert connector.organization_id == "org-123"
        assert connector.session is not None

    def test_configure_strips_trailing_slash(self):
        """Test that trailing slash is stripped from server URL."""
        connector = AuraConnector()
        config = {
            "server_url": "https://api.aenealabs.com/",
            "api_key": "test-key",
            "organization_id": "org-123",
        }

        connector.configure(config)

        assert connector.server_url == "https://api.aenealabs.com"

    def test_configure_missing_server_url(self):
        """Test configuration fails without server URL."""
        connector = AuraConnector()
        config = {
            "api_key": "test-key",
            "organization_id": "org-123",
        }

        with pytest.raises(ValueError, match="server_url is required"):
            connector.configure(config)

    def test_configure_missing_api_key(self):
        """Test configuration fails without API key."""
        connector = AuraConnector()
        config = {
            "server_url": "https://api.aenealabs.com",
            "organization_id": "org-123",
        }

        with pytest.raises(ValueError, match="api_key is required"):
            connector.configure(config)

    def test_configure_missing_organization_id(self):
        """Test configuration fails without organization ID."""
        connector = AuraConnector()
        config = {
            "server_url": "https://api.aenealabs.com",
            "api_key": "test-key",
        }

        with pytest.raises(ValueError, match="organization_id is required"):
            connector.configure(config)

    def test_session_headers_set(self):
        """Test that session headers are properly set."""
        connector = AuraConnector()
        config = {
            "server_url": "https://api.aenealabs.com",
            "api_key": "test-api-key-123",
            "organization_id": "org-456",
        }

        connector.configure(config)

        assert connector.session.headers["X-Api-Key"] == "test-api-key-123"
        assert connector.session.headers["X-Organization-Id"] == "org-456"
        assert connector.session.headers["Content-Type"] == "application/json"


class TestAuraConnectorTest:
    """Tests for connector test method."""

    @responses.activate
    def test_test_connection_success(self):
        """Test successful connection test."""
        connector = AuraConnector()
        connector.configure(
            {
                "server_url": "https://api.aenealabs.com",
                "api_key": "test-key",
                "organization_id": "org-123",
            }
        )

        responses.add(
            responses.POST,
            "https://api.aenealabs.com/api/v1/export/fivetran/test",
            json={"success": True},
            status=200,
        )

        result = connector.test()

        assert result.success is True

    @responses.activate
    def test_test_connection_failure(self):
        """Test failed connection test."""
        connector = AuraConnector()
        connector.configure(
            {
                "server_url": "https://api.aenealabs.com",
                "api_key": "invalid-key",
                "organization_id": "org-123",
            }
        )

        responses.add(
            responses.POST,
            "https://api.aenealabs.com/api/v1/export/fivetran/test",
            json={"success": False, "message": "Invalid API key"},
            status=200,
        )

        result = connector.test()

        assert result.success is False
        assert "Invalid API key" in result.failure

    @responses.activate
    def test_test_connection_network_error(self):
        """Test connection test with network error."""
        connector = AuraConnector()
        connector.configure(
            {
                "server_url": "https://api.aenealabs.com",
                "api_key": "test-key",
                "organization_id": "org-123",
            }
        )

        responses.add(
            responses.POST,
            "https://api.aenealabs.com/api/v1/export/fivetran/test",
            body=Exception("Connection refused"),
        )

        result = connector.test()

        assert result.success is False


class TestAuraConnectorSchema:
    """Tests for connector schema discovery."""

    @responses.activate
    def test_schema_discovery_success(self):
        """Test successful schema discovery."""
        connector = AuraConnector()
        connector.configure(
            {
                "server_url": "https://api.aenealabs.com",
                "api_key": "test-key",
                "organization_id": "org-123",
            }
        )

        expected_tables = {
            "findings": {
                "columns": {
                    "finding_id": {"type": "STRING", "nullable": False},
                    "severity": {"type": "STRING", "nullable": False},
                },
                "primary_key": ["finding_id"],
            }
        }

        responses.add(
            responses.POST,
            "https://api.aenealabs.com/api/v1/export/fivetran/schema",
            json={"tables": expected_tables},
            status=200,
        )

        result = connector.schema()

        assert "findings" in result
        assert result["findings"]["primary_key"] == ["finding_id"]

    @responses.activate
    def test_schema_discovery_fallback(self):
        """Test fallback schema when API fails."""
        connector = AuraConnector()
        connector.configure(
            {
                "server_url": "https://api.aenealabs.com",
                "api_key": "test-key",
                "organization_id": "org-123",
            }
        )

        responses.add(
            responses.POST,
            "https://api.aenealabs.com/api/v1/export/fivetran/schema",
            body=Exception("Server error"),
        )

        result = connector.schema()

        # Should return fallback schema
        assert "findings" in result
        assert "code_patterns" in result
        assert "repositories" in result
        assert "scan_history" in result
        assert "metrics" in result


class TestAuraConnectorUpdate:
    """Tests for connector update (sync) method."""

    @responses.activate
    def test_update_success(self):
        """Test successful incremental sync."""
        connector = AuraConnector()
        connector.configure(
            {
                "server_url": "https://api.aenealabs.com",
                "api_key": "test-key",
                "organization_id": "org-123",
            }
        )

        sync_response = {
            "state": {"last_sync": "2025-01-01T00:00:00Z"},
            "insert": {
                "findings": [
                    {
                        "finding_id": "f-1",
                        "severity": "high",
                        "title": "SQL Injection",
                    }
                ]
            },
            "delete": {},
            "hasMore": False,
        }

        responses.add(
            responses.POST,
            "https://api.aenealabs.com/api/v1/export/fivetran/sync",
            json=sync_response,
            status=200,
        )

        operations = list(connector.update({}))

        # Should have upsert and checkpoint operations
        assert len(operations) >= 2

    @responses.activate
    def test_update_with_pagination(self):
        """Test sync with pagination (hasMore=True)."""
        connector = AuraConnector()
        connector.configure(
            {
                "server_url": "https://api.aenealabs.com",
                "api_key": "test-key",
                "organization_id": "org-123",
            }
        )

        sync_response = {
            "state": {"findings_cursor": "1000"},
            "insert": {"findings": [{"finding_id": f"f-{i}"} for i in range(10)]},
            "delete": {},
            "hasMore": True,
        }

        responses.add(
            responses.POST,
            "https://api.aenealabs.com/api/v1/export/fivetran/sync",
            json=sync_response,
            status=200,
        )

        operations = list(connector.update({}))

        # Should have operations for data + checkpoint + update (for hasMore)
        assert len(operations) >= 12  # 10 upserts + checkpoint + update


class TestConfigurationSchema:
    """Tests for configuration schema validation."""

    def test_schema_has_required_fields(self):
        """Test that schema defines required fields."""
        assert "required" in CONFIGURATION_SCHEMA
        required = CONFIGURATION_SCHEMA["required"]
        assert "server_url" in required
        assert "api_key" in required
        assert "organization_id" in required

    def test_schema_properties(self):
        """Test schema property definitions."""
        props = CONFIGURATION_SCHEMA["properties"]

        assert props["server_url"]["type"] == "string"
        assert props["api_key"]["format"] == "password"
        assert props["organization_id"]["type"] == "string"
