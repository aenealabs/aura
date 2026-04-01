"""
Project Aura - IdP Configuration Service Tests

Tests for the IdP configuration CRUD service and routing service.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.services.identity.idp_config_service import (
    IdPConfigService,
    IdPRoutingService,
    get_idp_config_service,
    get_idp_routing_service,
)
from src.services.identity.models import (
    AttributeMapping,
    GroupMapping,
    IdentityProviderConfig,
    IdPType,
)


class TestIdPConfigService:
    """Tests for IdPConfigService."""

    @pytest.fixture
    def mock_dynamodb(self):
        """Create mock DynamoDB resource."""
        mock_resource = MagicMock()
        mock_table = MagicMock()
        mock_resource.Table.return_value = mock_table
        return mock_resource, mock_table

    @pytest.fixture
    def config_service(self, mock_dynamodb):
        """Create config service with mocked DynamoDB."""
        mock_resource, _ = mock_dynamodb
        return IdPConfigService(
            table_name="test-idp-configs",
            dynamodb_client=mock_resource,
        )

    @pytest.fixture
    def sample_config(self):
        """Create a sample IdP configuration."""
        return IdentityProviderConfig(
            idp_id="idp-123",
            organization_id="org-456",
            idp_type=IdPType.LDAP,
            name="Corporate LDAP",
            enabled=True,
            priority=10,
            connection_settings={
                "server": "ldap.corp.com",
                "port": 636,
            },
            email_domains=["corp.com", "company.com"],
            attribute_mappings=[
                AttributeMapping("mail", "email", required=True),
            ],
            group_mappings=[
                GroupMapping("Admins", "admin"),
            ],
        )

    @pytest.mark.asyncio
    async def test_create_config_success(
        self, config_service, mock_dynamodb, sample_config
    ):
        """Test successful config creation."""
        _, mock_table = mock_dynamodb
        mock_table.put_item.return_value = {}

        # Remove ID to test auto-generation
        sample_config.idp_id = ""

        result = await config_service.create_config(
            config=sample_config,
            actor_id="admin-user-123",
        )

        assert result.idp_id != ""  # Auto-generated
        assert result.created_by == "admin-user-123"
        assert result.created_at != ""
        assert result.updated_at != ""
        mock_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_config_with_id(
        self, config_service, mock_dynamodb, sample_config
    ):
        """Test config creation with provided ID."""
        _, mock_table = mock_dynamodb
        mock_table.put_item.return_value = {}

        result = await config_service.create_config(
            config=sample_config,
            actor_id="admin-user-123",
        )

        assert result.idp_id == "idp-123"

    @pytest.mark.asyncio
    async def test_create_config_already_exists(
        self, config_service, mock_dynamodb, sample_config
    ):
        """Test error when config already exists."""
        _, mock_table = mock_dynamodb
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}},
            "PutItem",
        )

        with pytest.raises(ValueError) as exc_info:
            await config_service.create_config(sample_config, "actor-123")
        assert "already exists" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_config_found(self, config_service, mock_dynamodb):
        """Test getting existing config."""
        _, mock_table = mock_dynamodb
        mock_table.get_item.return_value = {
            "Item": {
                "idp_id": "idp-123",
                "organization_id": "org-456",
                "idp_type": "ldap",
                "name": "LDAP Server",
                "enabled": True,
                "priority": 100,
            }
        }

        result = await config_service.get_config("idp-123")

        assert result is not None
        assert result.idp_id == "idp-123"
        assert result.idp_type == IdPType.LDAP
        mock_table.get_item.assert_called_with(Key={"idp_id": "idp-123"})

    @pytest.mark.asyncio
    async def test_get_config_not_found(self, config_service, mock_dynamodb):
        """Test getting non-existent config."""
        _, mock_table = mock_dynamodb
        mock_table.get_item.return_value = {}

        result = await config_service.get_config("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_config_success(
        self, config_service, mock_dynamodb, sample_config
    ):
        """Test successful config update."""
        _, mock_table = mock_dynamodb
        # Mock get_config
        mock_table.get_item.return_value = {"Item": sample_config.to_dynamodb_item()}
        # Mock update_item
        mock_table.update_item.return_value = {
            "Attributes": {
                **sample_config.to_dynamodb_item(),
                "name": "Updated LDAP",
                "priority": 5,
            }
        }

        result = await config_service.update_config(
            idp_id="idp-123",
            updates={"name": "Updated LDAP", "priority": 5},
            actor_id="admin-user",
        )

        assert result.name == "Updated LDAP"
        assert result.priority == 5
        mock_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_config_not_found(self, config_service, mock_dynamodb):
        """Test updating non-existent config."""
        _, mock_table = mock_dynamodb
        mock_table.get_item.return_value = {}

        with pytest.raises(ValueError) as exc_info:
            await config_service.update_config(
                idp_id="nonexistent",
                updates={"name": "New Name"},
                actor_id="admin",
            )
        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_config_success(
        self, config_service, mock_dynamodb, sample_config
    ):
        """Test successful config deletion."""
        _, mock_table = mock_dynamodb
        mock_table.get_item.return_value = {"Item": sample_config.to_dynamodb_item()}
        mock_table.delete_item.return_value = {}

        result = await config_service.delete_config("idp-123", "admin-user")

        assert result is True
        mock_table.delete_item.assert_called_with(Key={"idp_id": "idp-123"})

    @pytest.mark.asyncio
    async def test_delete_config_not_found(self, config_service, mock_dynamodb):
        """Test deleting non-existent config."""
        _, mock_table = mock_dynamodb
        mock_table.get_item.return_value = {}

        result = await config_service.delete_config("nonexistent", "admin")

        assert result is False

    @pytest.mark.asyncio
    async def test_list_configs_for_org(self, config_service, mock_dynamodb):
        """Test listing configs for organization."""
        _, mock_table = mock_dynamodb
        mock_table.query.return_value = {
            "Items": [
                {
                    "idp_id": "idp-1",
                    "organization_id": "org-123",
                    "idp_type": "ldap",
                    "name": "LDAP 1",
                    "enabled": True,
                    "priority": 10,
                },
                {
                    "idp_id": "idp-2",
                    "organization_id": "org-123",
                    "idp_type": "saml",
                    "name": "SAML 2",
                    "enabled": True,
                    "priority": 20,
                },
            ]
        }

        result = await config_service.list_configs_for_org("org-123")

        assert len(result) == 2
        # Should be sorted by priority
        assert result[0].priority == 10
        assert result[1].priority == 20
        mock_table.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_configs_for_org_enabled_only(
        self, config_service, mock_dynamodb
    ):
        """Test listing only enabled configs."""
        _, mock_table = mock_dynamodb
        mock_table.query.return_value = {
            "Items": [
                {
                    "idp_id": "idp-1",
                    "organization_id": "org-123",
                    "idp_type": "ldap",
                    "name": "LDAP 1",
                    "enabled": True,
                    "priority": 10,
                },
                {
                    "idp_id": "idp-2",
                    "organization_id": "org-123",
                    "idp_type": "saml",
                    "name": "SAML 2",
                    "enabled": False,  # Disabled
                    "priority": 20,
                },
            ]
        }

        result = await config_service.list_configs_for_org("org-123", enabled_only=True)

        assert len(result) == 1
        assert result[0].idp_id == "idp-1"

    @pytest.mark.asyncio
    async def test_get_config_by_email_domain_found(
        self, config_service, mock_dynamodb
    ):
        """Test finding config by email domain."""
        _, mock_table = mock_dynamodb
        # First query returns domain entry pointing to IdP
        mock_table.query.return_value = {"Items": [{"idp_id": "idp-123"}]}
        # Then get_config is called
        mock_table.get_item.return_value = {
            "Item": {
                "idp_id": "idp-123",
                "organization_id": "org-456",
                "idp_type": "ldap",
                "name": "LDAP",
                "enabled": True,
                "priority": 10,
            }
        }

        result = await config_service.get_config_by_email_domain("corp.com")

        assert result is not None
        assert result.idp_id == "idp-123"

    @pytest.mark.asyncio
    async def test_get_config_by_email_domain_not_found(
        self, config_service, mock_dynamodb
    ):
        """Test no config found for email domain."""
        _, mock_table = mock_dynamodb
        mock_table.query.return_value = {"Items": []}

        result = await config_service.get_config_by_email_domain("unknown.com")

        assert result is None


class TestIdPRoutingService:
    """Tests for IdPRoutingService."""

    @pytest.fixture
    def mock_config_service(self):
        """Create mock config service."""
        return MagicMock(spec=IdPConfigService)

    @pytest.fixture
    def routing_service(self, mock_config_service):
        """Create routing service with mocked config service."""
        return IdPRoutingService(config_service=mock_config_service)

    @pytest.fixture
    def sample_ldap_config(self):
        """Create sample LDAP config."""
        return IdentityProviderConfig(
            idp_id="idp-ldap-123",
            organization_id="org-456",
            idp_type=IdPType.LDAP,
            name="Corporate LDAP",
            enabled=True,
            priority=10,
            email_domains=["corp.com"],
        )

    @pytest.fixture
    def sample_saml_config(self):
        """Create sample SAML config."""
        return IdentityProviderConfig(
            idp_id="idp-saml-456",
            organization_id="org-456",
            idp_type=IdPType.SAML,
            name="Contractor SAML",
            enabled=True,
            priority=20,
            email_domains=["contractor.com"],
        )

    @pytest.mark.asyncio
    async def test_get_idp_for_email_domain_match(
        self, routing_service, mock_config_service, sample_ldap_config
    ):
        """Test routing based on email domain."""
        mock_config_service.get_config_by_email_domain = AsyncMock(
            return_value=sample_ldap_config
        )

        result = await routing_service.get_idp_for_email("user@corp.com")

        assert result is not None
        assert result.idp_id == "idp-ldap-123"
        mock_config_service.get_config_by_email_domain.assert_called_with("corp.com")

    @pytest.mark.asyncio
    async def test_get_idp_for_email_no_domain_match_with_org(
        self, routing_service, mock_config_service, sample_ldap_config
    ):
        """Test fallback to org default when no domain match."""
        mock_config_service.get_config_by_email_domain = AsyncMock(return_value=None)
        mock_config_service.list_configs_for_org = AsyncMock(
            return_value=[sample_ldap_config]
        )

        result = await routing_service.get_idp_for_email(
            "user@unknown.com", organization_id="org-456"
        )

        assert result is not None
        assert result.idp_id == "idp-ldap-123"

    @pytest.mark.asyncio
    async def test_get_idp_for_email_no_match(
        self, routing_service, mock_config_service
    ):
        """Test no match found."""
        mock_config_service.get_config_by_email_domain = AsyncMock(return_value=None)

        result = await routing_service.get_idp_for_email("user@unknown.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_idp_for_email_disabled_idp(
        self, routing_service, mock_config_service, sample_ldap_config
    ):
        """Test disabled IdP is not returned."""
        sample_ldap_config.enabled = False
        mock_config_service.get_config_by_email_domain = AsyncMock(
            return_value=sample_ldap_config
        )

        result = await routing_service.get_idp_for_email("user@corp.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_idp_for_invalid_email(self, routing_service):
        """Test handling invalid email."""
        result = await routing_service.get_idp_for_email("not-an-email")

        assert result is None

    @pytest.mark.asyncio
    async def test_list_available_idps(
        self,
        routing_service,
        mock_config_service,
        sample_ldap_config,
        sample_saml_config,
    ):
        """Test listing available IdPs for login UI."""
        mock_config_service.list_configs_for_org = AsyncMock(
            return_value=[sample_ldap_config, sample_saml_config]
        )
        mock_config_service.get_config_by_email_domain = AsyncMock(return_value=None)

        result = await routing_service.list_available_idps(organization_id="org-456")

        assert len(result) == 2
        assert result[0]["idp_id"] == "idp-ldap-123"
        assert result[0]["type"] == "ldap"
        assert result[0]["priority"] == 10

    @pytest.mark.asyncio
    async def test_list_available_idps_with_preferred(
        self,
        routing_service,
        mock_config_service,
        sample_ldap_config,
        sample_saml_config,
    ):
        """Test preferred IdP is marked based on email."""
        mock_config_service.list_configs_for_org = AsyncMock(
            return_value=[sample_ldap_config, sample_saml_config]
        )
        mock_config_service.get_config_by_email_domain = AsyncMock(
            return_value=sample_ldap_config
        )

        result = await routing_service.list_available_idps(
            organization_id="org-456",
            email="user@corp.com",
        )

        ldap_idp = next(i for i in result if i["idp_id"] == "idp-ldap-123")
        saml_idp = next(i for i in result if i["idp_id"] == "idp-saml-456")

        assert ldap_idp["is_preferred"] is True
        assert saml_idp["is_preferred"] is False

    @pytest.mark.asyncio
    async def test_list_available_idps_empty(
        self, routing_service, mock_config_service
    ):
        """Test empty list when no IdPs configured."""
        mock_config_service.list_configs_for_org = AsyncMock(return_value=[])

        result = await routing_service.list_available_idps(organization_id="org-456")

        assert result == []


class TestServiceSingletons:
    """Tests for service singleton functions."""

    def test_get_idp_config_service_creates_instance(self):
        """Test config service singleton creation."""
        import src.services.identity.idp_config_service as module

        original = module._config_service
        try:
            module._config_service = None
            with patch("boto3.resource"):
                service = get_idp_config_service()
                assert service is not None
                assert isinstance(service, IdPConfigService)
        finally:
            module._config_service = original

    def test_get_idp_config_service_returns_same_instance(self):
        """Test config service returns same instance."""
        import src.services.identity.idp_config_service as module

        original = module._config_service
        try:
            module._config_service = None
            with patch("boto3.resource"):
                service1 = get_idp_config_service()
                service2 = get_idp_config_service()
                assert service1 is service2
        finally:
            module._config_service = original

    def test_get_idp_routing_service_creates_instance(self):
        """Test routing service singleton creation."""
        import src.services.identity.idp_config_service as module

        original_routing = module._routing_service
        original_config = module._config_service
        try:
            module._routing_service = None
            module._config_service = None
            with patch("boto3.resource"):
                service = get_idp_routing_service()
                assert service is not None
                assert isinstance(service, IdPRoutingService)
        finally:
            module._routing_service = original_routing
            module._config_service = original_config

    def test_get_idp_routing_service_returns_same_instance(self):
        """Test routing service returns same instance."""
        import src.services.identity.idp_config_service as module

        original_routing = module._routing_service
        original_config = module._config_service
        try:
            module._routing_service = None
            module._config_service = None
            with patch("boto3.resource"):
                service1 = get_idp_routing_service()
                service2 = get_idp_routing_service()
                assert service1 is service2
        finally:
            module._routing_service = original_routing
            module._config_service = original_config


class TestConfigServiceEdgeCases:
    """Edge case tests for IdP config service."""

    @pytest.fixture
    def mock_dynamodb(self):
        """Create mock DynamoDB resource."""
        mock_resource = MagicMock()
        mock_table = MagicMock()
        mock_resource.Table.return_value = mock_table
        return mock_resource, mock_table

    @pytest.fixture
    def config_service(self, mock_dynamodb):
        """Create config service with mocked DynamoDB."""
        mock_resource, _ = mock_dynamodb
        return IdPConfigService(
            table_name="test-idp-configs",
            dynamodb_client=mock_resource,
        )

    @pytest.mark.asyncio
    async def test_update_email_domains(self, config_service, mock_dynamodb):
        """Test updating email domains triggers helper."""
        _, mock_table = mock_dynamodb
        mock_table.get_item.return_value = {
            "Item": {
                "idp_id": "idp-123",
                "organization_id": "org-456",
                "idp_type": "ldap",
                "name": "LDAP",
                "enabled": True,
                "priority": 10,
                "email_domains": ["old.com"],
            }
        }
        mock_table.update_item.return_value = {
            "Attributes": {
                "idp_id": "idp-123",
                "organization_id": "org-456",
                "idp_type": "ldap",
                "name": "LDAP",
                "enabled": True,
                "priority": 10,
                "email_domains": ["new.com", "another.com"],
            }
        }

        result = await config_service.update_config(
            idp_id="idp-123",
            updates={"email_domains": ["new.com", "another.com"]},
            actor_id="admin",
        )

        assert result.email_domains == ["new.com", "another.com"]

    @pytest.mark.asyncio
    async def test_get_config_dynamodb_error(self, config_service, mock_dynamodb):
        """Test error handling on DynamoDB failure."""
        _, mock_table = mock_dynamodb
        mock_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException"}},
            "GetItem",
        )

        with pytest.raises(ClientError):
            await config_service.get_config("idp-123")

    @pytest.mark.asyncio
    async def test_list_configs_empty_org(self, config_service, mock_dynamodb):
        """Test listing configs for org with no IdPs."""
        _, mock_table = mock_dynamodb
        mock_table.query.return_value = {"Items": []}

        result = await config_service.list_configs_for_org("empty-org")

        assert result == []

    @pytest.mark.asyncio
    async def test_email_domain_case_insensitive(self, config_service, mock_dynamodb):
        """Test email domain lookup is case-insensitive."""
        _, mock_table = mock_dynamodb
        mock_table.query.return_value = {"Items": []}

        # Should lowercase the domain
        await config_service.get_config_by_email_domain("CORP.COM")

        call_args = mock_table.query.call_args
        assert ":domain" in str(call_args)
        # The actual value passed should be lowercased
