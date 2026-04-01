"""
Coverage Tests for Ticketing Connectors.

This test file provides comprehensive coverage for the Zendesk and ServiceNow
stub connectors. These tests ensure that customer-facing functionality
is properly validated even for stub implementations.

NOTE: This file intentionally does NOT use pytest.mark.forked to ensure
coverage data is properly collected by pytest-cov.
"""

import logging

import pytest

from src.services.ticketing.base_connector import (
    TicketCreate,
    TicketFilters,
    TicketPriority,
    TicketStatus,
    TicketUpdate,
)
from src.services.ticketing.servicenow_connector import ServiceNowTicketConnector
from src.services.ticketing.zendesk_connector import ZendeskConnector

# =============================================================================
# Zendesk Connector Tests - Full Coverage
# =============================================================================


class TestZendeskConnectorFullCoverage:
    """
    Full coverage tests for ZendeskConnector.

    These tests exercise all code paths in the stub implementation to ensure
    proper error handling and logging behavior for customer-facing scenarios.
    """

    @pytest.fixture
    def zendesk_connector(self):
        """Create a Zendesk connector for testing."""
        return ZendeskConnector(
            subdomain="testcompany",
            email="admin@testcompany.com",
            api_token="zd_test_token_12345",
        )

    @pytest.fixture
    def sample_ticket_create(self):
        """Sample ticket creation data."""
        return TicketCreate(
            title="Critical security vulnerability detected",
            description="SQL injection vulnerability found in authentication module",
            priority=TicketPriority.CRITICAL,
            labels=["security", "critical", "vulnerability"],
            assignee="security-team",
            customer_id="customer-12345",
            metadata={"finding_id": "SEC-001", "severity": "critical"},
        )

    # -------------------------------------------------------------------------
    # Initialization Tests
    # -------------------------------------------------------------------------

    def test_zendesk_init_stores_credentials(self):
        """Test that initialization stores credentials correctly."""
        connector = ZendeskConnector(
            subdomain="mycompany",
            email="user@mycompany.com",
            api_token="my_token",
        )
        assert connector._subdomain == "mycompany"
        assert connector._email == "user@mycompany.com"
        assert connector._api_token == "my_token"

    def test_zendesk_init_constructs_base_url(self):
        """Test that initialization constructs the correct base URL."""
        connector = ZendeskConnector(
            subdomain="enterprise",
            email="admin@enterprise.com",
            api_token="token123",
        )
        assert connector._base_url == "https://enterprise.zendesk.com/api/v2"

    def test_zendesk_init_logs_initialization(self, caplog):
        """Test that initialization logs a message."""
        with caplog.at_level(logging.INFO):
            ZendeskConnector(
                subdomain="logtest",
                email="log@test.com",
                api_token="token",
            )
        assert "logtest.zendesk.com" in caplog.text
        assert "stub" in caplog.text.lower()

    # -------------------------------------------------------------------------
    # Property Tests
    # -------------------------------------------------------------------------

    def test_zendesk_provider_name(self, zendesk_connector):
        """Test provider_name returns 'zendesk'."""
        assert zendesk_connector.provider_name == "zendesk"

    def test_zendesk_provider_display_name(self, zendesk_connector):
        """Test provider_display_name returns 'Zendesk'."""
        assert zendesk_connector.provider_display_name == "Zendesk"

    # -------------------------------------------------------------------------
    # Async Method Tests - Customer-Facing Functionality
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_zendesk_test_connection_returns_false(
        self, zendesk_connector, caplog
    ):
        """Test that test_connection returns False and logs a warning."""
        with caplog.at_level(logging.WARNING):
            result = await zendesk_connector.test_connection()
        assert result is False
        assert "stub" in caplog.text.lower()
        assert "test_connection" in caplog.text

    @pytest.mark.asyncio
    async def test_zendesk_create_ticket_returns_not_implemented(
        self, zendesk_connector, sample_ticket_create, caplog
    ):
        """Test that create_ticket returns a NOT_IMPLEMENTED error."""
        with caplog.at_level(logging.WARNING):
            result = await zendesk_connector.create_ticket(sample_ticket_create)
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "not yet implemented" in result.error_message.lower()
        assert "create_ticket" in caplog.text

    @pytest.mark.asyncio
    async def test_zendesk_get_ticket_returns_none(self, zendesk_connector, caplog):
        """Test that get_ticket returns None and logs a warning."""
        with caplog.at_level(logging.WARNING):
            result = await zendesk_connector.get_ticket("ticket-12345")
        assert result is None
        assert "get_ticket" in caplog.text
        assert "stub" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_zendesk_get_ticket_by_external_id_returns_none(
        self, zendesk_connector, caplog
    ):
        """Test that get_ticket_by_external_id returns None."""
        with caplog.at_level(logging.WARNING):
            result = await zendesk_connector.get_ticket_by_external_id("ext-98765")
        assert result is None
        assert "get_ticket_by_external_id" in caplog.text

    @pytest.mark.asyncio
    async def test_zendesk_update_ticket_returns_not_implemented(
        self, zendesk_connector, caplog
    ):
        """Test that update_ticket returns a NOT_IMPLEMENTED error."""
        update = TicketUpdate(
            title="Updated ticket title",
            status=TicketStatus.IN_PROGRESS,
            priority=TicketPriority.HIGH,
        )
        with caplog.at_level(logging.WARNING):
            result = await zendesk_connector.update_ticket("ticket-123", update)
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "update_ticket" in caplog.text

    @pytest.mark.asyncio
    async def test_zendesk_list_tickets_returns_empty_list(
        self, zendesk_connector, caplog
    ):
        """Test that list_tickets returns an empty list."""
        with caplog.at_level(logging.WARNING):
            result = await zendesk_connector.list_tickets()
        assert result == []
        assert "list_tickets" in caplog.text

    @pytest.mark.asyncio
    async def test_zendesk_list_tickets_with_filters_returns_empty_list(
        self, zendesk_connector, caplog
    ):
        """Test that list_tickets with filters returns an empty list."""
        filters = TicketFilters(
            status=[TicketStatus.OPEN, TicketStatus.IN_PROGRESS],
            priority=[TicketPriority.HIGH, TicketPriority.CRITICAL],
            labels=["security"],
            assignee="security-team",
        )
        with caplog.at_level(logging.WARNING):
            result = await zendesk_connector.list_tickets(filters)
        assert result == []

    @pytest.mark.asyncio
    async def test_zendesk_add_comment_returns_not_implemented(
        self, zendesk_connector, caplog
    ):
        """Test that add_comment returns a NOT_IMPLEMENTED error."""
        with caplog.at_level(logging.WARNING):
            result = await zendesk_connector.add_comment(
                "ticket-123",
                "This is a customer-visible comment",
            )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "add_comment" in caplog.text

    @pytest.mark.asyncio
    async def test_zendesk_add_internal_comment_returns_not_implemented(
        self, zendesk_connector, caplog
    ):
        """Test that add_comment with is_internal=True returns NOT_IMPLEMENTED."""
        with caplog.at_level(logging.WARNING):
            result = await zendesk_connector.add_comment(
                "ticket-123",
                "This is an internal note for agents only",
                is_internal=True,
            )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_zendesk_close_ticket_returns_not_implemented(
        self, zendesk_connector, caplog
    ):
        """Test that close_ticket returns a NOT_IMPLEMENTED error."""
        with caplog.at_level(logging.WARNING):
            result = await zendesk_connector.close_ticket("ticket-123")
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "close_ticket" in caplog.text

    @pytest.mark.asyncio
    async def test_zendesk_close_ticket_with_resolution_returns_not_implemented(
        self, zendesk_connector, caplog
    ):
        """Test that close_ticket with resolution returns NOT_IMPLEMENTED."""
        with caplog.at_level(logging.WARNING):
            result = await zendesk_connector.close_ticket(
                "ticket-123",
                resolution="Issue resolved by applying security patch",
            )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_zendesk_reopen_ticket_returns_not_implemented(
        self, zendesk_connector, caplog
    ):
        """Test that reopen_ticket returns a NOT_IMPLEMENTED error."""
        with caplog.at_level(logging.WARNING):
            result = await zendesk_connector.reopen_ticket("ticket-123")
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "reopen_ticket" in caplog.text

    @pytest.mark.asyncio
    async def test_zendesk_reopen_ticket_with_reason_returns_not_implemented(
        self, zendesk_connector, caplog
    ):
        """Test that reopen_ticket with reason returns NOT_IMPLEMENTED."""
        with caplog.at_level(logging.WARNING):
            result = await zendesk_connector.reopen_ticket(
                "ticket-123",
                reason="Customer reported issue persists after initial fix",
            )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"


# =============================================================================
# ServiceNow Connector Tests - Full Coverage
# =============================================================================


class TestServiceNowConnectorFullCoverage:
    """
    Full coverage tests for ServiceNowTicketConnector.

    These tests exercise all code paths in the stub implementation to ensure
    proper error handling and logging behavior for enterprise ITSM scenarios.
    """

    @pytest.fixture
    def servicenow_connector(self):
        """Create a ServiceNow connector for testing."""
        return ServiceNowTicketConnector(
            instance_url="https://testcompany.service-now.com",
            username="admin",
            password="secure_password_123",
            table="incident",
        )

    @pytest.fixture
    def sample_ticket_create(self):
        """Sample ticket creation data for ServiceNow."""
        return TicketCreate(
            title="Production server down",
            description="Main production server is unresponsive since 10:00 AM",
            priority=TicketPriority.CRITICAL,
            labels=["incident", "production", "outage"],
            assignee="infrastructure-team",
            customer_id="customer-enterprise-001",
            metadata={"impact": "high", "urgency": "critical"},
        )

    # -------------------------------------------------------------------------
    # Initialization Tests
    # -------------------------------------------------------------------------

    def test_servicenow_init_stores_credentials(self):
        """Test that initialization stores credentials correctly."""
        connector = ServiceNowTicketConnector(
            instance_url="https://mycompany.service-now.com",
            username="api_user",
            password="api_password",
        )
        assert connector._instance_url == "https://mycompany.service-now.com"
        assert connector._username == "api_user"
        assert connector._password == "api_password"

    def test_servicenow_init_strips_trailing_slash(self):
        """Test that initialization strips trailing slash from instance_url."""
        connector = ServiceNowTicketConnector(
            instance_url="https://mycompany.service-now.com/",
            username="user",
            password="pass",
        )
        assert connector._instance_url == "https://mycompany.service-now.com"

    def test_servicenow_init_default_table(self):
        """Test that default table is 'incident'."""
        connector = ServiceNowTicketConnector(
            instance_url="https://test.service-now.com",
            username="user",
            password="pass",
        )
        assert connector._table == "incident"

    def test_servicenow_init_custom_table(self):
        """Test that custom table can be specified."""
        connector = ServiceNowTicketConnector(
            instance_url="https://test.service-now.com",
            username="user",
            password="pass",
            table="sc_request",
        )
        assert connector._table == "sc_request"

    def test_servicenow_init_constructs_api_url(self):
        """Test that initialization constructs the correct API URL."""
        connector = ServiceNowTicketConnector(
            instance_url="https://enterprise.service-now.com",
            username="admin",
            password="password",
            table="problem",
        )
        assert (
            connector._api_url
            == "https://enterprise.service-now.com/api/now/table/problem"
        )

    def test_servicenow_init_logs_initialization(self, caplog):
        """Test that initialization logs a message."""
        with caplog.at_level(logging.INFO):
            ServiceNowTicketConnector(
                instance_url="https://logtest.service-now.com",
                username="user",
                password="pass",
            )
        assert "logtest.service-now.com" in caplog.text
        assert "stub" in caplog.text.lower()

    # -------------------------------------------------------------------------
    # Property Tests
    # -------------------------------------------------------------------------

    def test_servicenow_provider_name(self, servicenow_connector):
        """Test provider_name returns 'servicenow'."""
        assert servicenow_connector.provider_name == "servicenow"

    def test_servicenow_provider_display_name(self, servicenow_connector):
        """Test provider_display_name returns 'ServiceNow'."""
        assert servicenow_connector.provider_display_name == "ServiceNow"

    # -------------------------------------------------------------------------
    # Async Method Tests - Enterprise ITSM Functionality
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_servicenow_test_connection_returns_false(
        self, servicenow_connector, caplog
    ):
        """Test that test_connection returns False and logs a warning."""
        with caplog.at_level(logging.WARNING):
            result = await servicenow_connector.test_connection()
        assert result is False
        assert "stub" in caplog.text.lower()
        assert "test_connection" in caplog.text

    @pytest.mark.asyncio
    async def test_servicenow_create_ticket_returns_not_implemented(
        self, servicenow_connector, sample_ticket_create, caplog
    ):
        """Test that create_ticket returns a NOT_IMPLEMENTED error."""
        with caplog.at_level(logging.WARNING):
            result = await servicenow_connector.create_ticket(sample_ticket_create)
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "not yet implemented" in result.error_message.lower()
        assert "create_ticket" in caplog.text

    @pytest.mark.asyncio
    async def test_servicenow_get_ticket_returns_none(
        self, servicenow_connector, caplog
    ):
        """Test that get_ticket returns None and logs a warning."""
        with caplog.at_level(logging.WARNING):
            result = await servicenow_connector.get_ticket("INC0012345")
        assert result is None
        assert "get_ticket" in caplog.text
        assert "stub" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_servicenow_get_ticket_by_external_id_returns_none(
        self, servicenow_connector, caplog
    ):
        """Test that get_ticket_by_external_id returns None."""
        with caplog.at_level(logging.WARNING):
            result = await servicenow_connector.get_ticket_by_external_id(
                "sys_id_abc123def456"
            )
        assert result is None
        assert "get_ticket_by_external_id" in caplog.text

    @pytest.mark.asyncio
    async def test_servicenow_update_ticket_returns_not_implemented(
        self, servicenow_connector, caplog
    ):
        """Test that update_ticket returns a NOT_IMPLEMENTED error."""
        update = TicketUpdate(
            title="Updated incident title",
            status=TicketStatus.IN_PROGRESS,
            priority=TicketPriority.HIGH,
            assignee="senior-engineer",
        )
        with caplog.at_level(logging.WARNING):
            result = await servicenow_connector.update_ticket("INC0012345", update)
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "update_ticket" in caplog.text

    @pytest.mark.asyncio
    async def test_servicenow_list_tickets_returns_empty_list(
        self, servicenow_connector, caplog
    ):
        """Test that list_tickets returns an empty list."""
        with caplog.at_level(logging.WARNING):
            result = await servicenow_connector.list_tickets()
        assert result == []
        assert "list_tickets" in caplog.text

    @pytest.mark.asyncio
    async def test_servicenow_list_tickets_with_filters_returns_empty_list(
        self, servicenow_connector, caplog
    ):
        """Test that list_tickets with filters returns an empty list."""
        filters = TicketFilters(
            status=[TicketStatus.OPEN],
            priority=[TicketPriority.CRITICAL],
            labels=["outage"],
            assignee="infrastructure-team",
            limit=100,
            offset=0,
        )
        with caplog.at_level(logging.WARNING):
            result = await servicenow_connector.list_tickets(filters)
        assert result == []

    @pytest.mark.asyncio
    async def test_servicenow_add_comment_returns_not_implemented(
        self, servicenow_connector, caplog
    ):
        """Test that add_comment returns a NOT_IMPLEMENTED error."""
        with caplog.at_level(logging.WARNING):
            result = await servicenow_connector.add_comment(
                "INC0012345",
                "Escalating to Level 2 support",
            )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "add_comment" in caplog.text

    @pytest.mark.asyncio
    async def test_servicenow_add_work_note_returns_not_implemented(
        self, servicenow_connector, caplog
    ):
        """Test that add_comment with is_internal=True (work note) returns NOT_IMPLEMENTED."""
        with caplog.at_level(logging.WARNING):
            result = await servicenow_connector.add_comment(
                "INC0012345",
                "Internal work note: Root cause analysis in progress",
                is_internal=True,
            )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_servicenow_close_ticket_returns_not_implemented(
        self, servicenow_connector, caplog
    ):
        """Test that close_ticket returns a NOT_IMPLEMENTED error."""
        with caplog.at_level(logging.WARNING):
            result = await servicenow_connector.close_ticket("INC0012345")
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "close_ticket" in caplog.text

    @pytest.mark.asyncio
    async def test_servicenow_close_ticket_with_resolution_returns_not_implemented(
        self, servicenow_connector, caplog
    ):
        """Test that close_ticket with resolution returns NOT_IMPLEMENTED."""
        with caplog.at_level(logging.WARNING):
            result = await servicenow_connector.close_ticket(
                "INC0012345",
                resolution="Root cause identified: Memory leak. Applied hotfix KB12345.",
            )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_servicenow_reopen_ticket_returns_not_implemented(
        self, servicenow_connector, caplog
    ):
        """Test that reopen_ticket returns a NOT_IMPLEMENTED error."""
        with caplog.at_level(logging.WARNING):
            result = await servicenow_connector.reopen_ticket("INC0012345")
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "reopen_ticket" in caplog.text

    @pytest.mark.asyncio
    async def test_servicenow_reopen_ticket_with_reason_returns_not_implemented(
        self, servicenow_connector, caplog
    ):
        """Test that reopen_ticket with reason returns NOT_IMPLEMENTED."""
        with caplog.at_level(logging.WARNING):
            result = await servicenow_connector.reopen_ticket(
                "INC0012345",
                reason="Issue reoccurred after initial resolution. Memory leak persists.",
            )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"


# =============================================================================
# Customer Scenario Tests
# =============================================================================


class TestCustomerScenarios:
    """
    Tests simulating real customer scenarios to ensure graceful degradation
    when attempting to use stub connectors.
    """

    @pytest.mark.asyncio
    async def test_zendesk_customer_ticket_lifecycle(self):
        """
        Test a complete customer ticket lifecycle with Zendesk connector.

        This simulates what a customer would experience if they attempted to:
        1. Create a support ticket
        2. Add a comment
        3. Close the ticket

        All operations should fail gracefully with clear error messages.
        """
        connector = ZendeskConnector(
            subdomain="customer",
            email="support@customer.com",
            api_token="token",
        )

        # Step 1: Customer creates a ticket
        ticket = TicketCreate(
            title="Cannot access dashboard",
            description="Getting 403 error when accessing the main dashboard",
            priority=TicketPriority.HIGH,
        )
        create_result = await connector.create_ticket(ticket)
        assert not create_result.success
        assert "not yet implemented" in create_result.error_message.lower()

        # Step 2: Customer tries to add a comment
        comment_result = await connector.add_comment(
            "nonexistent-ticket",
            "This is urgent, please help!",
        )
        assert not comment_result.success
        assert comment_result.error_code == "NOT_IMPLEMENTED"

        # Step 3: Customer tries to close the ticket
        close_result = await connector.close_ticket(
            "nonexistent-ticket",
            resolution="Issue resolved",
        )
        assert not close_result.success

    @pytest.mark.asyncio
    async def test_servicenow_enterprise_incident_workflow(self):
        """
        Test an enterprise incident workflow with ServiceNow connector.

        This simulates what an enterprise customer would experience when:
        1. Creating an incident
        2. Updating the incident
        3. Adding work notes
        4. Closing the incident

        All operations should fail gracefully with clear error messages.
        """
        connector = ServiceNowTicketConnector(
            instance_url="https://enterprise.service-now.com",
            username="integration_user",
            password="integration_pass",
            table="incident",
        )

        # Step 1: Create a critical incident
        incident = TicketCreate(
            title="Production database unresponsive",
            description="Oracle RAC cluster not accepting connections",
            priority=TicketPriority.CRITICAL,
            labels=["database", "production", "critical"],
        )
        create_result = await connector.create_ticket(incident)
        assert not create_result.success
        assert create_result.error_code == "NOT_IMPLEMENTED"

        # Step 2: Try to update the incident
        update = TicketUpdate(
            status=TicketStatus.IN_PROGRESS,
            assignee="dba-team",
        )
        update_result = await connector.update_ticket("INC0000001", update)
        assert not update_result.success

        # Step 3: Add a work note
        worknote_result = await connector.add_comment(
            "INC0000001",
            "DBA team investigating connection pool exhaustion",
            is_internal=True,
        )
        assert not worknote_result.success

        # Step 4: Close the incident
        close_result = await connector.close_ticket(
            "INC0000001",
            resolution="Connection pool configuration updated. Monitoring for 24 hours.",
        )
        assert not close_result.success

    @pytest.mark.asyncio
    async def test_connector_test_connection_for_ui_validation(self):
        """
        Test the test_connection method that would be used by UI 'Test Connection' button.

        Both connectors should return False since they are stubs.
        """
        zendesk = ZendeskConnector(
            subdomain="test",
            email="test@test.com",
            api_token="token",
        )
        servicenow = ServiceNowTicketConnector(
            instance_url="https://test.service-now.com",
            username="user",
            password="pass",
        )

        # Both should return False (stubs not implemented)
        assert await zendesk.test_connection() is False
        assert await servicenow.test_connection() is False


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zendesk_empty_ticket_creation(self):
        """Test creating a ticket with minimal data."""
        connector = ZendeskConnector(
            subdomain="edge",
            email="edge@test.com",
            api_token="token",
        )
        ticket = TicketCreate(
            title="",
            description="",
        )
        result = await connector.create_ticket(ticket)
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_servicenow_special_characters_in_ticket(self):
        """Test creating a ticket with special characters."""
        connector = ServiceNowTicketConnector(
            instance_url="https://edge.service-now.com",
            username="user",
            password="pass",
        )
        ticket = TicketCreate(
            title="Error: <script>alert('XSS')</script>",
            description="SQL injection attempt: ' OR '1'='1",
            priority=TicketPriority.LOW,
        )
        result = await connector.create_ticket(ticket)
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_zendesk_list_tickets_with_empty_filters(self):
        """Test listing tickets with empty filters."""
        connector = ZendeskConnector(
            subdomain="edge",
            email="edge@test.com",
            api_token="token",
        )
        filters = TicketFilters()  # All defaults
        result = await connector.list_tickets(filters)
        assert result == []

    @pytest.mark.asyncio
    async def test_servicenow_reopen_without_reason(self):
        """Test reopening ticket without providing a reason."""
        connector = ServiceNowTicketConnector(
            instance_url="https://edge.service-now.com",
            username="user",
            password="pass",
        )
        result = await connector.reopen_ticket("INC0000001", reason=None)
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_zendesk_close_without_resolution(self):
        """Test closing ticket without providing a resolution."""
        connector = ZendeskConnector(
            subdomain="edge",
            email="edge@test.com",
            api_token="token",
        )
        result = await connector.close_ticket("ticket-123", resolution=None)
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    def test_servicenow_problem_table_configuration(self):
        """Test ServiceNow connector with problem table configuration."""
        connector = ServiceNowTicketConnector(
            instance_url="https://test.service-now.com",
            username="user",
            password="pass",
            table="problem",
        )
        assert connector._table == "problem"
        assert "/api/now/table/problem" in connector._api_url

    def test_servicenow_change_request_table_configuration(self):
        """Test ServiceNow connector with change_request table configuration."""
        connector = ServiceNowTicketConnector(
            instance_url="https://test.service-now.com",
            username="user",
            password="pass",
            table="change_request",
        )
        assert connector._table == "change_request"
        assert "/api/now/table/change_request" in connector._api_url


# =============================================================================
# Linear Connector Tests - Full Coverage
# =============================================================================


class TestLinearConnectorFullCoverage:
    """
    Full coverage tests for LinearConnector.

    These tests exercise all code paths in the stub implementation to ensure
    proper error handling and logging behavior for Linear issue tracking.
    """

    @pytest.fixture
    def linear_connector(self):
        """Create a Linear connector for testing."""
        from src.services.ticketing.linear_connector import LinearConnector

        return LinearConnector(
            api_key="lin_api_test_key_12345",
            team_id="TEAM-001",
            project_id="PROJECT-001",
        )

    @pytest.fixture
    def sample_ticket_create(self):
        """Sample ticket creation data for Linear."""
        return TicketCreate(
            title="Performance degradation in API endpoints",
            description="Response times have increased by 200% in production",
            priority=TicketPriority.HIGH,
            labels=["performance", "api", "production"],
            assignee="backend-team",
            customer_id="customer-enterprise-001",
            metadata={"affected_endpoints": ["/api/v1/users", "/api/v1/orders"]},
        )

    # -------------------------------------------------------------------------
    # Initialization Tests
    # -------------------------------------------------------------------------

    def test_linear_init_stores_credentials(self):
        """Test that initialization stores credentials correctly."""
        from src.services.ticketing.linear_connector import LinearConnector

        connector = LinearConnector(
            api_key="lin_key_123",
            team_id="TEAM-ABC",
        )
        assert connector._api_key == "lin_key_123"
        assert connector._team_id == "TEAM-ABC"
        assert connector._project_id is None

    def test_linear_init_with_project_id(self):
        """Test that initialization stores project_id when provided."""
        from src.services.ticketing.linear_connector import LinearConnector

        connector = LinearConnector(
            api_key="lin_key_456",
            team_id="TEAM-XYZ",
            project_id="PROJECT-789",
        )
        assert connector._project_id == "PROJECT-789"

    def test_linear_init_constructs_graphql_url(self):
        """Test that initialization constructs the correct GraphQL URL."""
        from src.services.ticketing.linear_connector import LinearConnector

        connector = LinearConnector(
            api_key="lin_key",
            team_id="TEAM",
        )
        assert connector._graphql_url == "https://api.linear.app/graphql"

    def test_linear_init_logs_initialization(self, caplog):
        """Test that initialization logs a message."""
        from src.services.ticketing.linear_connector import LinearConnector

        with caplog.at_level(logging.INFO):
            LinearConnector(
                api_key="lin_key",
                team_id="TEAM-LOG",
            )
        assert "TEAM-LOG" in caplog.text
        assert "stub" in caplog.text.lower()

    # -------------------------------------------------------------------------
    # Property Tests
    # -------------------------------------------------------------------------

    def test_linear_provider_name(self, linear_connector):
        """Test provider_name returns 'linear'."""
        assert linear_connector.provider_name == "linear"

    def test_linear_provider_display_name(self, linear_connector):
        """Test provider_display_name returns 'Linear'."""
        assert linear_connector.provider_display_name == "Linear"

    # -------------------------------------------------------------------------
    # Async Method Tests - Full Coverage for Stub
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_linear_test_connection_returns_false(self, linear_connector, caplog):
        """Test that test_connection returns False and logs a warning."""
        with caplog.at_level(logging.WARNING):
            result = await linear_connector.test_connection()
        assert result is False
        assert "stub" in caplog.text.lower()
        assert "test_connection" in caplog.text

    @pytest.mark.asyncio
    async def test_linear_create_ticket_returns_not_implemented(
        self, linear_connector, sample_ticket_create, caplog
    ):
        """Test that create_ticket returns a NOT_IMPLEMENTED error."""
        with caplog.at_level(logging.WARNING):
            result = await linear_connector.create_ticket(sample_ticket_create)
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "not yet implemented" in result.error_message.lower()
        assert "create_ticket" in caplog.text

    @pytest.mark.asyncio
    async def test_linear_get_ticket_returns_none(self, linear_connector, caplog):
        """Test that get_ticket returns None and logs a warning."""
        with caplog.at_level(logging.WARNING):
            result = await linear_connector.get_ticket("issue-12345")
        assert result is None
        assert "get_ticket" in caplog.text
        assert "stub" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_linear_get_ticket_by_external_id_returns_none(
        self, linear_connector, caplog
    ):
        """Test that get_ticket_by_external_id returns None."""
        with caplog.at_level(logging.WARNING):
            result = await linear_connector.get_ticket_by_external_id("LIN-123")
        assert result is None
        assert "get_ticket_by_external_id" in caplog.text

    @pytest.mark.asyncio
    async def test_linear_update_ticket_returns_not_implemented(
        self, linear_connector, caplog
    ):
        """Test that update_ticket returns a NOT_IMPLEMENTED error."""
        update = TicketUpdate(
            title="Updated issue title",
            status=TicketStatus.IN_PROGRESS,
            priority=TicketPriority.CRITICAL,
        )
        with caplog.at_level(logging.WARNING):
            result = await linear_connector.update_ticket("issue-123", update)
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "update_ticket" in caplog.text

    @pytest.mark.asyncio
    async def test_linear_list_tickets_returns_empty_list(
        self, linear_connector, caplog
    ):
        """Test that list_tickets returns an empty list."""
        with caplog.at_level(logging.WARNING):
            result = await linear_connector.list_tickets()
        assert result == []
        assert "list_tickets" in caplog.text

    @pytest.mark.asyncio
    async def test_linear_list_tickets_with_filters_returns_empty_list(
        self, linear_connector, caplog
    ):
        """Test that list_tickets with filters returns an empty list."""
        filters = TicketFilters(
            status=[TicketStatus.OPEN, TicketStatus.IN_PROGRESS],
            priority=[TicketPriority.HIGH],
            labels=["performance"],
        )
        with caplog.at_level(logging.WARNING):
            result = await linear_connector.list_tickets(filters)
        assert result == []

    @pytest.mark.asyncio
    async def test_linear_add_comment_returns_not_implemented(
        self, linear_connector, caplog
    ):
        """Test that add_comment returns a NOT_IMPLEMENTED error."""
        with caplog.at_level(logging.WARNING):
            result = await linear_connector.add_comment(
                "issue-123",
                "Investigating the root cause",
            )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "add_comment" in caplog.text

    @pytest.mark.asyncio
    async def test_linear_add_internal_comment_returns_not_implemented(
        self, linear_connector, caplog
    ):
        """Test that add_comment with is_internal=True returns NOT_IMPLEMENTED."""
        with caplog.at_level(logging.WARNING):
            result = await linear_connector.add_comment(
                "issue-123",
                "Internal note: Need to escalate to senior engineer",
                is_internal=True,
            )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_linear_close_ticket_returns_not_implemented(
        self, linear_connector, caplog
    ):
        """Test that close_ticket returns a NOT_IMPLEMENTED error."""
        with caplog.at_level(logging.WARNING):
            result = await linear_connector.close_ticket("issue-123")
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "close_ticket" in caplog.text

    @pytest.mark.asyncio
    async def test_linear_close_ticket_with_resolution_returns_not_implemented(
        self, linear_connector, caplog
    ):
        """Test that close_ticket with resolution returns NOT_IMPLEMENTED."""
        with caplog.at_level(logging.WARNING):
            result = await linear_connector.close_ticket(
                "issue-123",
                resolution="Root cause identified and fixed in PR #456",
            )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_linear_reopen_ticket_returns_not_implemented(
        self, linear_connector, caplog
    ):
        """Test that reopen_ticket returns a NOT_IMPLEMENTED error."""
        with caplog.at_level(logging.WARNING):
            result = await linear_connector.reopen_ticket("issue-123")
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "reopen_ticket" in caplog.text

    @pytest.mark.asyncio
    async def test_linear_reopen_ticket_with_reason_returns_not_implemented(
        self, linear_connector, caplog
    ):
        """Test that reopen_ticket with reason returns NOT_IMPLEMENTED."""
        with caplog.at_level(logging.WARNING):
            result = await linear_connector.reopen_ticket(
                "issue-123",
                reason="Issue reoccurred after deployment",
            )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"


# =============================================================================
# Base Connector Priority Mapping Tests
# =============================================================================


class TestBaseConnectorPriorityMapping:
    """
    Tests for the _map_priority_to_labels method in the base connector.

    This ensures the priority to label mapping works correctly for all
    priority levels and edge cases.
    """

    @pytest.fixture
    def concrete_connector(self):
        """Create a concrete connector to test base class methods."""
        # Use Zendesk as it's a simple stub that inherits from base
        return ZendeskConnector(
            subdomain="test",
            email="test@test.com",
            api_token="token",
        )

    def test_map_priority_low(self, concrete_connector):
        """Test mapping LOW priority to labels."""
        labels = concrete_connector._map_priority_to_labels(TicketPriority.LOW)
        assert labels == ["priority:low"]

    def test_map_priority_medium(self, concrete_connector):
        """Test mapping MEDIUM priority to labels."""
        labels = concrete_connector._map_priority_to_labels(TicketPriority.MEDIUM)
        assert labels == ["priority:medium"]

    def test_map_priority_high(self, concrete_connector):
        """Test mapping HIGH priority to labels."""
        labels = concrete_connector._map_priority_to_labels(TicketPriority.HIGH)
        assert labels == ["priority:high"]

    def test_map_priority_critical(self, concrete_connector):
        """Test mapping CRITICAL priority to labels."""
        labels = concrete_connector._map_priority_to_labels(TicketPriority.CRITICAL)
        assert labels == ["priority:critical"]

    def test_map_priority_all_priorities(self, concrete_connector):
        """Test mapping all priorities returns expected labels."""
        expected = {
            TicketPriority.LOW: ["priority:low"],
            TicketPriority.MEDIUM: ["priority:medium"],
            TicketPriority.HIGH: ["priority:high"],
            TicketPriority.CRITICAL: ["priority:critical"],
        }
        for priority, expected_labels in expected.items():
            result = concrete_connector._map_priority_to_labels(priority)
            assert result == expected_labels, f"Failed for priority {priority}"


# =============================================================================
# Linear Customer Scenario Tests
# =============================================================================


class TestLinearCustomerScenarios:
    """
    Tests simulating real customer scenarios with Linear connector.
    """

    @pytest.mark.asyncio
    async def test_linear_agile_sprint_workflow(self):
        """
        Test an agile sprint workflow with Linear connector.

        Simulates what a development team would experience when:
        1. Creating a sprint task
        2. Updating progress
        3. Adding comments
        4. Closing the issue
        """
        from src.services.ticketing.linear_connector import LinearConnector

        connector = LinearConnector(
            api_key="lin_sprint_key",
            team_id="ENGINEERING",
            project_id="SPRINT-42",
        )

        # Step 1: Create a sprint task
        task = TicketCreate(
            title="Implement OAuth2 refresh token rotation",
            description="Add automatic token refresh with configurable TTL",
            priority=TicketPriority.HIGH,
            labels=["feature", "security", "sprint-42"],
        )
        create_result = await connector.create_ticket(task)
        assert not create_result.success
        assert create_result.error_code == "NOT_IMPLEMENTED"

        # Step 2: Update to in-progress
        update = TicketUpdate(status=TicketStatus.IN_PROGRESS)
        update_result = await connector.update_ticket("nonexistent", update)
        assert not update_result.success

        # Step 3: Add implementation notes
        comment_result = await connector.add_comment(
            "nonexistent",
            "Implementation complete, ready for code review",
        )
        assert not comment_result.success

        # Step 4: Close the issue
        close_result = await connector.close_ticket(
            "nonexistent",
            resolution="Merged in PR #789",
        )
        assert not close_result.success

    @pytest.mark.asyncio
    async def test_linear_bug_triage_workflow(self):
        """
        Test a bug triage workflow with Linear connector.

        Simulates what a QA team would experience when:
        1. Creating a bug report
        2. Getting ticket details
        3. Reopening after failed fix
        """
        from src.services.ticketing.linear_connector import LinearConnector

        connector = LinearConnector(
            api_key="lin_qa_key",
            team_id="QA",
        )

        # Step 1: Create a bug report
        bug = TicketCreate(
            title="Memory leak in background worker",
            description="Worker process consumes 500MB+ after 24h",
            priority=TicketPriority.CRITICAL,
            labels=["bug", "memory", "critical"],
        )
        create_result = await connector.create_ticket(bug)
        assert not create_result.success

        # Step 2: Try to get ticket details
        get_result = await connector.get_ticket("bug-001")
        assert get_result is None

        # Step 3: Try to get by external ID
        external_result = await connector.get_ticket_by_external_id("LIN-456")
        assert external_result is None

        # Step 4: Reopen after failed fix
        reopen_result = await connector.reopen_ticket(
            "bug-001",
            reason="Memory leak persists after patch",
        )
        assert not reopen_result.success
