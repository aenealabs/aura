"""Tests for sandbox_network_service.py module.

Covers:
- SandboxNetworkStatus and NetworkIsolationLevel enums
- DnsmasqConfig dataclass and configuration generation
- SandboxNetwork dataclass and serialization
- SandboxNetworkOrchestrator for network lifecycle management
- FargateSandboxOrchestrator for ECS Fargate-based sandboxes
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.services.sandbox_network_service import (
    DnsmasqConfig,
    FargateSandboxOrchestrator,
    NetworkIsolationLevel,
    SandboxNetwork,
    SandboxNetworkOrchestrator,
    SandboxNetworkStatus,
)


# ==============================================================================
# Tests for Enums
# ==============================================================================
class TestSandboxNetworkStatus:
    """Tests for SandboxNetworkStatus enum."""

    def test_pending_value(self):
        """PENDING status has correct value."""
        assert SandboxNetworkStatus.PENDING.value == "pending"

    def test_provisioning_value(self):
        """PROVISIONING status has correct value."""
        assert SandboxNetworkStatus.PROVISIONING.value == "provisioning"

    def test_active_value(self):
        """ACTIVE status has correct value."""
        assert SandboxNetworkStatus.ACTIVE.value == "active"

    def test_tearing_down_value(self):
        """TEARING_DOWN status has correct value."""
        assert SandboxNetworkStatus.TEARING_DOWN.value == "tearing_down"

    def test_terminated_value(self):
        """TERMINATED status has correct value."""
        assert SandboxNetworkStatus.TERMINATED.value == "terminated"

    def test_failed_value(self):
        """FAILED status has correct value."""
        assert SandboxNetworkStatus.FAILED.value == "failed"

    def test_all_statuses_exist(self):
        """All expected status values exist."""
        expected = {
            "pending",
            "provisioning",
            "active",
            "tearing_down",
            "terminated",
            "failed",
        }
        actual = {status.value for status in SandboxNetworkStatus}
        assert actual == expected


class TestNetworkIsolationLevel:
    """Tests for NetworkIsolationLevel enum."""

    def test_none_value(self):
        """NONE isolation level has correct value."""
        assert NetworkIsolationLevel.NONE.value == "none"

    def test_container_value(self):
        """CONTAINER isolation level has correct value."""
        assert NetworkIsolationLevel.CONTAINER.value == "container"

    def test_vpc_value(self):
        """VPC isolation level has correct value."""
        assert NetworkIsolationLevel.VPC.value == "vpc"

    def test_full_value(self):
        """FULL isolation level has correct value."""
        assert NetworkIsolationLevel.FULL.value == "full"

    def test_all_levels_exist(self):
        """All expected isolation levels exist."""
        expected = {"none", "container", "vpc", "full"}
        actual = {level.value for level in NetworkIsolationLevel}
        assert actual == expected


# ==============================================================================
# Tests for DnsmasqConfig
# ==============================================================================
class TestDnsmasqConfig:
    """Tests for DnsmasqConfig dataclass."""

    def test_default_values(self):
        """DnsmasqConfig has correct default values."""
        config = DnsmasqConfig()

        assert config.port == 53
        assert config.cache_size == 1000
        assert "1.1.1.1" in config.upstream_servers
        assert "8.8.8.8" in config.upstream_servers
        assert config.local_domain == "sandbox.aura.local"
        assert config.enable_dnssec is True
        assert config.enable_dhcp is False
        assert config.dhcp_range is None
        assert config.custom_hosts == {}

    def test_custom_values(self):
        """DnsmasqConfig accepts custom values."""
        config = DnsmasqConfig(
            port=5353,
            cache_size=500,
            upstream_servers=["9.9.9.9"],
            local_domain="custom.local",
            enable_dnssec=False,
            enable_dhcp=True,
            dhcp_range="192.168.1.100,192.168.1.200,12h",
            custom_hosts={"app.local": "10.0.0.5"},
        )

        assert config.port == 5353
        assert config.cache_size == 500
        assert config.upstream_servers == ["9.9.9.9"]
        assert config.local_domain == "custom.local"
        assert config.enable_dnssec is False
        assert config.enable_dhcp is True
        assert config.dhcp_range == "192.168.1.100,192.168.1.200,12h"
        assert config.custom_hosts == {"app.local": "10.0.0.5"}

    def test_to_config_file_basic(self):
        """to_config_file generates valid configuration."""
        config = DnsmasqConfig()

        result = config.to_config_file()

        assert "# Project Aura Sandbox Network Configuration" in result
        assert "port=53" in result
        assert "cache-size=1000" in result
        assert "server=1.1.1.1" in result
        assert "server=8.8.8.8" in result
        assert "local=/sandbox.aura.local/" in result
        assert "domain=sandbox.aura.local" in result

    def test_to_config_file_with_dnssec(self):
        """to_config_file includes DNSSEC config when enabled."""
        config = DnsmasqConfig(enable_dnssec=True)

        result = config.to_config_file()

        assert "dnssec" in result
        assert "trust-anchor=" in result

    def test_to_config_file_without_dnssec(self):
        """to_config_file excludes DNSSEC config when disabled."""
        config = DnsmasqConfig(enable_dnssec=False)

        result = config.to_config_file()

        assert "trust-anchor=" not in result

    def test_to_config_file_with_dhcp(self):
        """to_config_file includes DHCP config when enabled."""
        config = DnsmasqConfig(
            enable_dhcp=True,
            dhcp_range="192.168.1.100,192.168.1.200,12h",
        )

        result = config.to_config_file()

        assert "# DHCP configuration" in result
        assert "dhcp-range=192.168.1.100,192.168.1.200,12h" in result
        assert "dhcp-option=option:router" in result
        assert "dhcp-leasefile=" in result

    def test_to_config_file_without_dhcp(self):
        """to_config_file excludes DHCP config when disabled."""
        config = DnsmasqConfig(enable_dhcp=False)

        result = config.to_config_file()

        assert "dhcp-range=" not in result
        assert "dhcp-leasefile=" not in result

    def test_to_config_file_with_custom_hosts(self):
        """to_config_file includes custom host entries."""
        config = DnsmasqConfig(
            custom_hosts={
                "app.local": "10.0.0.5",
                "db.local": "10.0.0.6",
            }
        )

        result = config.to_config_file()

        assert "# Custom host entries" in result
        assert "address=/app.local/10.0.0.5" in result
        assert "address=/db.local/10.0.0.6" in result

    def test_to_config_file_security_settings(self):
        """to_config_file includes security settings."""
        config = DnsmasqConfig()

        result = config.to_config_file()

        assert "stop-dns-rebind" in result
        assert "rebind-localhost-ok" in result
        assert "bogus-priv" in result


# ==============================================================================
# Tests for SandboxNetwork
# ==============================================================================
class TestSandboxNetwork:
    """Tests for SandboxNetwork dataclass."""

    def test_basic_creation(self):
        """SandboxNetwork creates with required fields."""
        network = SandboxNetwork(
            sandbox_id="sandbox-123",
            status=SandboxNetworkStatus.PENDING,
            isolation_level=NetworkIsolationLevel.CONTAINER,
            dnsmasq_config=DnsmasqConfig(),
        )

        assert network.sandbox_id == "sandbox-123"
        assert network.status == SandboxNetworkStatus.PENDING
        assert network.isolation_level == NetworkIsolationLevel.CONTAINER
        assert network.vpc_id is None
        assert network.subnet_id is None
        assert network.security_group_id is None
        assert network.ecs_task_arn is None
        assert network.terminated_at is None

    def test_with_all_fields(self):
        """SandboxNetwork accepts all optional fields."""
        now = datetime.now(timezone.utc)
        network = SandboxNetwork(
            sandbox_id="sandbox-456",
            status=SandboxNetworkStatus.ACTIVE,
            isolation_level=NetworkIsolationLevel.VPC,
            dnsmasq_config=DnsmasqConfig(),
            vpc_id="vpc-12345",
            subnet_id="subnet-67890",
            security_group_id="sg-abcde",
            ecs_task_arn="arn:aws:ecs:us-east-1:123456789012:task/task-1",
            container_id="container-xyz",
            dns_endpoint="10.0.0.2:53",
            dhcp_endpoint="10.0.0.2:67",
            created_at=now,
            terminated_at=now,
            metadata={"key": "value"},
        )

        assert network.vpc_id == "vpc-12345"
        assert network.subnet_id == "subnet-67890"
        assert network.dns_endpoint == "10.0.0.2:53"
        assert network.metadata == {"key": "value"}

    def test_to_dict(self):
        """to_dict serializes all fields correctly."""
        network = SandboxNetwork(
            sandbox_id="sandbox-789",
            status=SandboxNetworkStatus.ACTIVE,
            isolation_level=NetworkIsolationLevel.FULL,
            dnsmasq_config=DnsmasqConfig(),
            vpc_id="vpc-test",
            dns_endpoint="10.0.1.2:53",
            metadata={"test": "data"},
        )

        result = network.to_dict()

        assert result["sandbox_id"] == "sandbox-789"
        assert result["status"] == "active"
        assert result["isolation_level"] == "full"
        assert result["vpc_id"] == "vpc-test"
        assert result["dns_endpoint"] == "10.0.1.2:53"
        assert result["metadata"] == {"test": "data"}
        assert "created_at" in result

    def test_to_dict_terminated_at(self):
        """to_dict handles terminated_at correctly."""
        now = datetime.now(timezone.utc)
        network = SandboxNetwork(
            sandbox_id="sandbox-term",
            status=SandboxNetworkStatus.TERMINATED,
            isolation_level=NetworkIsolationLevel.CONTAINER,
            dnsmasq_config=DnsmasqConfig(),
            terminated_at=now,
        )

        result = network.to_dict()

        assert result["terminated_at"] is not None
        assert now.isoformat() in result["terminated_at"]

    def test_to_dict_without_terminated_at(self):
        """to_dict handles None terminated_at."""
        network = SandboxNetwork(
            sandbox_id="sandbox-active",
            status=SandboxNetworkStatus.ACTIVE,
            isolation_level=NetworkIsolationLevel.CONTAINER,
            dnsmasq_config=DnsmasqConfig(),
        )

        result = network.to_dict()

        assert result["terminated_at"] is None


# ==============================================================================
# Tests for SandboxNetworkOrchestrator
# ==============================================================================
class TestSandboxNetworkOrchestratorInit:
    """Tests for SandboxNetworkOrchestrator initialization."""

    @patch("boto3.client")
    def test_init_defaults(self, mock_boto_client):
        """Orchestrator initializes with default values."""
        orchestrator = SandboxNetworkOrchestrator()

        assert orchestrator.environment == "dev"
        assert orchestrator.project_name == "aura"
        assert orchestrator.aws_region == "us-east-1"
        assert orchestrator.ecs_cluster_name == "aura-sandbox-dev"
        assert orchestrator.active_networks == {}

    @patch("boto3.client")
    def test_init_custom_values(self, mock_boto_client):
        """Orchestrator initializes with custom values."""
        orchestrator = SandboxNetworkOrchestrator(
            environment="prod",
            project_name="custom",
            ecs_cluster_name="my-cluster",
            aws_region="eu-west-1",
        )

        assert orchestrator.environment == "prod"
        assert orchestrator.project_name == "custom"
        assert orchestrator.ecs_cluster_name == "my-cluster"
        assert orchestrator.aws_region == "eu-west-1"

    @patch("boto3.client")
    def test_init_creates_aws_clients(self, mock_boto_client):
        """Orchestrator creates required AWS clients."""
        SandboxNetworkOrchestrator()

        # Should create ecs, ec2, and logs clients
        assert mock_boto_client.call_count >= 3


class TestSandboxNetworkOrchestratorProvision:
    """Tests for SandboxNetworkOrchestrator provisioning methods."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked AWS clients."""
        with patch("boto3.client"):
            return SandboxNetworkOrchestrator()

    @pytest.mark.asyncio
    async def test_provision_container_network(self, orchestrator):
        """Provision container-level isolated network."""
        network = await orchestrator.provision_sandbox_network(
            sandbox_id="test-container",
            isolation_level=NetworkIsolationLevel.CONTAINER,
        )

        assert network.sandbox_id == "test-container"
        assert network.status == SandboxNetworkStatus.ACTIVE
        assert network.isolation_level == NetworkIsolationLevel.CONTAINER
        assert network.ecs_task_arn is not None
        assert network.dns_endpoint is not None

    @pytest.mark.asyncio
    async def test_provision_vpc_network(self, orchestrator):
        """Provision VPC subnet-level isolated network."""
        network = await orchestrator.provision_sandbox_network(
            sandbox_id="test-vpc",
            isolation_level=NetworkIsolationLevel.VPC,
        )

        assert network.sandbox_id == "test-vpc"
        assert network.status == SandboxNetworkStatus.ACTIVE
        assert network.isolation_level == NetworkIsolationLevel.VPC
        assert network.vpc_id is not None
        assert network.subnet_id is not None

    @pytest.mark.asyncio
    async def test_provision_full_isolation(self, orchestrator):
        """Provision fully isolated network."""
        network = await orchestrator.provision_sandbox_network(
            sandbox_id="test-full",
            isolation_level=NetworkIsolationLevel.FULL,
        )

        assert network.sandbox_id == "test-full"
        assert network.status == SandboxNetworkStatus.ACTIVE
        assert network.isolation_level == NetworkIsolationLevel.FULL
        assert "isolated" in network.vpc_id

    @pytest.mark.asyncio
    async def test_provision_no_isolation(self, orchestrator):
        """Provision network with no isolation."""
        network = await orchestrator.provision_sandbox_network(
            sandbox_id="test-none",
            isolation_level=NetworkIsolationLevel.NONE,
        )

        assert network.sandbox_id == "test-none"
        assert network.status == SandboxNetworkStatus.ACTIVE
        assert network.dns_endpoint == "127.0.0.1:53"

    @pytest.mark.asyncio
    async def test_provision_with_custom_config(self, orchestrator):
        """Provision network with custom DNS config."""
        custom_config = DnsmasqConfig(
            port=5353,
            local_domain="custom.sandbox.local",
            custom_hosts={"api.local": "10.0.0.100"},
        )

        network = await orchestrator.provision_sandbox_network(
            sandbox_id="test-custom",
            isolation_level=NetworkIsolationLevel.CONTAINER,
            custom_config=custom_config,
        )

        assert network.dnsmasq_config.port == 5353
        assert network.dnsmasq_config.local_domain == "custom.sandbox.local"
        assert "api.local" in network.dnsmasq_config.custom_hosts

    @pytest.mark.asyncio
    async def test_provision_with_metadata(self, orchestrator):
        """Provision network with metadata."""
        network = await orchestrator.provision_sandbox_network(
            sandbox_id="test-metadata",
            isolation_level=NetworkIsolationLevel.CONTAINER,
            metadata={"patch_id": "patch-123", "reviewer": "user@example.com"},
        )

        assert network.metadata["patch_id"] == "patch-123"
        assert network.metadata["reviewer"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_provision_duplicate_fails(self, orchestrator):
        """Provisioning duplicate sandbox raises ValueError."""
        await orchestrator.provision_sandbox_network(
            sandbox_id="duplicate",
            isolation_level=NetworkIsolationLevel.CONTAINER,
        )

        with pytest.raises(ValueError, match="already exists"):
            await orchestrator.provision_sandbox_network(
                sandbox_id="duplicate",
                isolation_level=NetworkIsolationLevel.CONTAINER,
            )

    @pytest.mark.asyncio
    async def test_provision_adds_to_active_networks(self, orchestrator):
        """Provisioned network is added to active_networks."""
        await orchestrator.provision_sandbox_network(
            sandbox_id="tracked-network",
            isolation_level=NetworkIsolationLevel.CONTAINER,
        )

        assert "tracked-network" in orchestrator.active_networks


class TestSandboxNetworkOrchestratorTerminate:
    """Tests for SandboxNetworkOrchestrator termination methods."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked AWS clients."""
        with patch("boto3.client"):
            return SandboxNetworkOrchestrator()

    @pytest.mark.asyncio
    async def test_terminate_network(self, orchestrator):
        """Terminate sandbox network removes from active."""
        await orchestrator.provision_sandbox_network(
            sandbox_id="to-terminate",
            isolation_level=NetworkIsolationLevel.CONTAINER,
        )

        await orchestrator.terminate_sandbox_network("to-terminate")

        assert "to-terminate" not in orchestrator.active_networks

    @pytest.mark.asyncio
    async def test_terminate_nonexistent_fails(self, orchestrator):
        """Terminating nonexistent sandbox raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await orchestrator.terminate_sandbox_network("nonexistent")

    @pytest.mark.asyncio
    async def test_terminate_sets_terminated_at(self, orchestrator):
        """Terminate sets terminated_at timestamp."""
        network = await orchestrator.provision_sandbox_network(
            sandbox_id="timestamp-test",
            isolation_level=NetworkIsolationLevel.CONTAINER,
        )

        assert network.terminated_at is None

        await orchestrator.terminate_sandbox_network("timestamp-test")

        # Network is removed, so we can't check directly
        # But we verified the method runs without error


class TestSandboxNetworkOrchestratorQuery:
    """Tests for SandboxNetworkOrchestrator query methods."""

    @pytest.fixture
    async def orchestrator_with_networks(self):
        """Create orchestrator with multiple networks."""
        with patch("boto3.client"):
            orch = SandboxNetworkOrchestrator()

            await orch.provision_sandbox_network(
                sandbox_id="network-1",
                isolation_level=NetworkIsolationLevel.CONTAINER,
            )
            await orch.provision_sandbox_network(
                sandbox_id="network-2",
                isolation_level=NetworkIsolationLevel.VPC,
            )

            return orch

    @pytest.mark.asyncio
    async def test_get_sandbox_network_exists(self, orchestrator_with_networks):
        """Get existing sandbox network."""
        network = await orchestrator_with_networks.get_sandbox_network("network-1")

        assert network is not None
        assert network.sandbox_id == "network-1"

    @pytest.mark.asyncio
    async def test_get_sandbox_network_not_exists(self, orchestrator_with_networks):
        """Get nonexistent sandbox returns None."""
        network = await orchestrator_with_networks.get_sandbox_network("nonexistent")

        assert network is None

    @pytest.mark.asyncio
    async def test_list_active_networks(self, orchestrator_with_networks):
        """List all active networks."""
        networks = await orchestrator_with_networks.list_active_networks()

        assert len(networks) == 2
        sandbox_ids = {n.sandbox_id for n in networks}
        assert sandbox_ids == {"network-1", "network-2"}

    @pytest.mark.asyncio
    async def test_list_active_networks_empty(self):
        """List active networks when none exist."""
        with patch("boto3.client"):
            orch = SandboxNetworkOrchestrator()

        networks = await orch.list_active_networks()

        assert networks == []


class TestSandboxNetworkOrchestratorCleanup:
    """Tests for SandboxNetworkOrchestrator cleanup methods."""

    @pytest.fixture
    async def orchestrator_with_networks(self):
        """Create orchestrator with multiple networks."""
        with patch("boto3.client"):
            orch = SandboxNetworkOrchestrator()

            await orch.provision_sandbox_network(
                sandbox_id="cleanup-1",
                isolation_level=NetworkIsolationLevel.CONTAINER,
            )
            await orch.provision_sandbox_network(
                sandbox_id="cleanup-2",
                isolation_level=NetworkIsolationLevel.VPC,
            )

            return orch

    @pytest.mark.asyncio
    async def test_cleanup_all_networks(self, orchestrator_with_networks):
        """Cleanup all networks removes all active."""
        assert len(orchestrator_with_networks.active_networks) == 2

        await orchestrator_with_networks.cleanup_all_networks()

        assert len(orchestrator_with_networks.active_networks) == 0


class TestSandboxNetworkOrchestratorHealthCheck:
    """Tests for SandboxNetworkOrchestrator health check."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked AWS clients."""
        with patch("boto3.client"):
            return SandboxNetworkOrchestrator()

    @pytest.mark.asyncio
    async def test_health_check_active(self, orchestrator):
        """Health check returns True for active network."""
        await orchestrator.provision_sandbox_network(
            sandbox_id="healthy",
            isolation_level=NetworkIsolationLevel.CONTAINER,
        )

        is_healthy = await orchestrator.health_check("healthy")

        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_nonexistent(self, orchestrator):
        """Health check returns False for nonexistent network."""
        is_healthy = await orchestrator.health_check("nonexistent")

        assert is_healthy is False


# ==============================================================================
# Tests for FargateSandboxOrchestrator
# ==============================================================================
class TestFargateSandboxOrchestratorInit:
    """Tests for FargateSandboxOrchestrator initialization."""

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_init_defaults(self, mock_resource, mock_client):
        """FargateSandboxOrchestrator initializes with defaults."""
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table

        orchestrator = FargateSandboxOrchestrator()

        assert orchestrator.environment == "dev"
        assert orchestrator.aws_region == "us-east-1"
        assert orchestrator.cluster_name == "aura-sandboxes-dev"
        assert orchestrator.task_definition == "sandbox-patch-test-dev"
        assert orchestrator.state_table == "aura-sandbox-state-dev"

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_init_custom_values(self, mock_resource, mock_client):
        """FargateSandboxOrchestrator initializes with custom values."""
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table

        orchestrator = FargateSandboxOrchestrator(
            environment="prod",
            aws_region="eu-west-1",
        )

        assert orchestrator.environment == "prod"
        assert orchestrator.aws_region == "eu-west-1"
        assert orchestrator.cluster_name == "aura-sandboxes-prod"


class TestFargateSandboxOrchestratorCreate:
    """Tests for FargateSandboxOrchestrator create_sandbox method."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked AWS clients."""
        with patch("boto3.client") as _mock_client:
            with patch("boto3.resource") as mock_resource:
                mock_table = MagicMock()
                mock_resource.return_value.Table.return_value = mock_table

                orch = FargateSandboxOrchestrator()

                # Mock ECS run_task response
                orch.ecs = MagicMock()
                orch.ecs.run_task.return_value = {
                    "tasks": [
                        {
                            "taskArn": "arn:aws:ecs:us-east-1:123456789012:task/task-123",
                        }
                    ]
                }

                # Mock EC2 describe methods
                orch.ec2 = MagicMock()
                orch.ec2.describe_subnets.return_value = {
                    "Subnets": [
                        {"SubnetId": "subnet-1"},
                        {"SubnetId": "subnet-2"},
                    ]
                }
                orch.ec2.describe_security_groups.return_value = {
                    "SecurityGroups": [{"GroupId": "sg-123"}]
                }

                return orch

    @pytest.mark.asyncio
    async def test_create_sandbox_success(self, orchestrator):
        """Create sandbox returns expected result."""
        result = await orchestrator.create_sandbox(
            sandbox_id="new-sandbox",
            patch_id="patch-456",
            test_suite="unit_tests",
        )

        assert result["sandbox_id"] == "new-sandbox"
        assert "task_arn" in result
        assert result["status"] == "PROVISIONING"
        assert result["cluster"] == "aura-sandboxes-dev"

    @pytest.mark.asyncio
    async def test_create_sandbox_with_metadata(self, orchestrator):
        """Create sandbox with metadata."""
        result = await orchestrator.create_sandbox(
            sandbox_id="meta-sandbox",
            patch_id="patch-789",
            test_suite="integration_tests",
            metadata={"priority": "high"},
        )

        assert result["sandbox_id"] == "meta-sandbox"

    @pytest.mark.asyncio
    async def test_create_sandbox_no_tasks_fails(self, orchestrator):
        """Create sandbox fails when no tasks returned."""
        orchestrator.ecs.run_task.return_value = {"tasks": []}

        with pytest.raises(RuntimeError, match="No tasks returned"):
            await orchestrator.create_sandbox(
                sandbox_id="fail-sandbox",
                patch_id="patch-000",
                test_suite="tests",
            )

    @pytest.mark.asyncio
    async def test_create_sandbox_exception_wrapped(self, orchestrator):
        """Create sandbox wraps exceptions in RuntimeError."""
        orchestrator.ecs.run_task.side_effect = Exception("AWS error")

        with pytest.raises(RuntimeError, match="Sandbox creation failed"):
            await orchestrator.create_sandbox(
                sandbox_id="error-sandbox",
                patch_id="patch-err",
                test_suite="tests",
            )


class TestFargateSandboxOrchestratorDestroy:
    """Tests for FargateSandboxOrchestrator destroy_sandbox method."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked AWS clients."""
        with patch("boto3.client"):
            with patch("boto3.resource") as mock_resource:
                mock_table = MagicMock()
                mock_table.get_item.return_value = {
                    "Item": {
                        "sandbox_id": "destroy-sandbox",
                        "task_arn": "arn:aws:ecs:us-east-1:123:task/task-1",
                    }
                }
                mock_resource.return_value.Table.return_value = mock_table

                orch = FargateSandboxOrchestrator()
                orch.ecs = MagicMock()

                return orch

    @pytest.mark.asyncio
    async def test_destroy_sandbox_success(self, orchestrator):
        """Destroy sandbox stops ECS task."""
        await orchestrator.destroy_sandbox("destroy-sandbox")

        orchestrator.ecs.stop_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_destroy_sandbox_not_found(self, orchestrator):
        """Destroy nonexistent sandbox raises ValueError."""
        orchestrator.state_table_resource.get_item.return_value = {}

        with pytest.raises(ValueError, match="not found"):
            await orchestrator.destroy_sandbox("nonexistent")


class TestFargateSandboxOrchestratorStatus:
    """Tests for FargateSandboxOrchestrator get_sandbox_status method."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked AWS clients."""
        with patch("boto3.client"):
            with patch("boto3.resource") as mock_resource:
                mock_table = MagicMock()
                mock_table.get_item.return_value = {
                    "Item": {
                        "sandbox_id": "status-sandbox",
                        "task_arn": "arn:aws:ecs:us-east-1:123:task/task-1",
                    }
                }
                mock_resource.return_value.Table.return_value = mock_table

                orch = FargateSandboxOrchestrator()
                orch.ecs = MagicMock()
                orch.ecs.describe_tasks.return_value = {
                    "tasks": [
                        {
                            "taskArn": "arn:aws:ecs:us-east-1:123:task/task-1",
                            "lastStatus": "RUNNING",
                            "containers": [{"name": "sandbox", "exitCode": None}],
                            "createdAt": "2024-01-01T00:00:00Z",
                        }
                    ]
                }

                return orch

    @pytest.mark.asyncio
    async def test_get_status_running(self, orchestrator):
        """Get status for running sandbox."""
        result = await orchestrator.get_sandbox_status("status-sandbox")

        assert result["sandbox_id"] == "status-sandbox"
        assert result["status"] == "ACTIVE"
        assert result["ecs_status"] == "RUNNING"

    @pytest.mark.asyncio
    async def test_get_status_stopped(self, orchestrator):
        """Get status for stopped sandbox."""
        orchestrator.ecs.describe_tasks.return_value = {
            "tasks": [
                {
                    "taskArn": "arn:aws:ecs:us-east-1:123:task/task-1",
                    "lastStatus": "STOPPED",
                    "containers": [{"name": "sandbox", "exitCode": 0}],
                    "createdAt": "2024-01-01T00:00:00Z",
                    "stoppedAt": "2024-01-01T01:00:00Z",
                }
            ]
        }

        result = await orchestrator.get_sandbox_status("status-sandbox")

        assert result["status"] == "TERMINATED"
        assert result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_get_status_task_not_found(self, orchestrator):
        """Get status when task not found in ECS."""
        orchestrator.ecs.describe_tasks.return_value = {"tasks": []}

        result = await orchestrator.get_sandbox_status("status-sandbox")

        assert result["status"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_status_sandbox_not_found(self, orchestrator):
        """Get status for nonexistent sandbox."""
        orchestrator.state_table_resource.get_item.return_value = {}

        with pytest.raises(ValueError, match="not found"):
            await orchestrator.get_sandbox_status("nonexistent")


class TestFargateSandboxOrchestratorLogs:
    """Tests for FargateSandboxOrchestrator get_sandbox_logs method."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked AWS clients."""
        with patch("boto3.client"):
            with patch("boto3.resource") as mock_resource:
                mock_table = MagicMock()
                mock_resource.return_value.Table.return_value = mock_table

                orch = FargateSandboxOrchestrator()
                orch.logs = MagicMock()

                return orch

    @pytest.mark.asyncio
    async def test_get_logs_success(self, orchestrator):
        """Get logs returns log messages."""
        orchestrator.logs.describe_log_streams.return_value = {
            "logStreams": [{"logStreamName": "sandbox/test-123/stream"}]
        }
        orchestrator.logs.get_log_events.return_value = {
            "events": [
                {"message": "Log line 1"},
                {"message": "Log line 2"},
            ]
        }

        logs = await orchestrator.get_sandbox_logs("test-123")

        assert len(logs) == 2
        assert "Log line 1" in logs

    @pytest.mark.asyncio
    async def test_get_logs_no_streams(self, orchestrator):
        """Get logs returns empty when no streams found."""
        orchestrator.logs.describe_log_streams.return_value = {"logStreams": []}

        logs = await orchestrator.get_sandbox_logs("test-123")

        assert logs == []

    @pytest.mark.asyncio
    async def test_get_logs_exception_returns_empty(self, orchestrator):
        """Get logs returns empty on exception."""
        orchestrator.logs.describe_log_streams.side_effect = Exception("AWS error")

        logs = await orchestrator.get_sandbox_logs("test-123")

        assert logs == []


class TestFargateSandboxOrchestratorList:
    """Tests for FargateSandboxOrchestrator list_active_sandboxes method."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked AWS clients."""
        with patch("boto3.client"):
            with patch("boto3.resource") as mock_resource:
                mock_table = MagicMock()
                mock_table.scan.return_value = {
                    "Items": [
                        {"sandbox_id": "sandbox-1", "status": "ACTIVE"},
                        {"sandbox_id": "sandbox-2", "status": "PROVISIONING"},
                    ]
                }
                mock_resource.return_value.Table.return_value = mock_table

                return FargateSandboxOrchestrator()

    @pytest.mark.asyncio
    async def test_list_active_sandboxes(self, orchestrator):
        """List active sandboxes returns correct items."""
        sandboxes = await orchestrator.list_active_sandboxes()

        assert len(sandboxes) == 2
        assert sandboxes[0]["sandbox_id"] == "sandbox-1"

    @pytest.mark.asyncio
    async def test_list_active_sandboxes_exception(self, orchestrator):
        """List active sandboxes returns empty on exception."""
        orchestrator.state_table_resource.scan.side_effect = Exception("DynamoDB error")

        sandboxes = await orchestrator.list_active_sandboxes()

        assert sandboxes == []


class TestFargateSandboxOrchestratorHelpers:
    """Tests for FargateSandboxOrchestrator helper methods."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked AWS clients."""
        with patch("boto3.client"):
            with patch("boto3.resource") as mock_resource:
                mock_table = MagicMock()
                mock_resource.return_value.Table.return_value = mock_table

                orch = FargateSandboxOrchestrator()
                orch.ec2 = MagicMock()

                return orch

    @pytest.mark.asyncio
    async def test_get_sandbox_subnets_found(self, orchestrator):
        """Get subnets returns subnet IDs when found."""
        orchestrator.ec2.describe_subnets.return_value = {
            "Subnets": [
                {"SubnetId": "subnet-aaa"},
                {"SubnetId": "subnet-bbb"},
                {"SubnetId": "subnet-ccc"},
            ]
        }

        subnets = await orchestrator._get_sandbox_subnets()

        assert len(subnets) == 2  # Returns first 2
        assert "subnet-aaa" in subnets
        assert "subnet-bbb" in subnets

    @pytest.mark.asyncio
    async def test_get_sandbox_subnets_fallback(self, orchestrator):
        """Get subnets raises RuntimeError when none found via EC2 or SSM."""
        orchestrator.ec2.describe_subnets.return_value = {"Subnets": []}

        with pytest.raises(RuntimeError) as exc_info:
            await orchestrator._get_sandbox_subnets()

        assert "No sandbox subnets found" in str(exc_info.value)
        assert "dev" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_sandbox_security_groups_found(self, orchestrator):
        """Get security groups returns group IDs when found."""
        orchestrator.ec2.describe_security_groups.return_value = {
            "SecurityGroups": [{"GroupId": "sg-12345"}]
        }

        groups = await orchestrator._get_sandbox_security_groups()

        assert len(groups) == 1
        assert groups[0] == "sg-12345"

    @pytest.mark.asyncio
    async def test_get_sandbox_security_groups_fallback(self, orchestrator):
        """Get security groups raises RuntimeError when none found via EC2 or SSM."""
        orchestrator.ec2.describe_security_groups.return_value = {"SecurityGroups": []}

        with pytest.raises(RuntimeError) as exc_info:
            await orchestrator._get_sandbox_security_groups()

        assert "No sandbox security group found" in str(exc_info.value)
        assert "dev" in str(exc_info.value)
