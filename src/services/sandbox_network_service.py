"""
Project Aura - Sandbox Network Service

Provides isolated network environments for sandbox testing (HITL V2.0 feature).
Orchestrates ephemeral DNS/DHCP services using dnsmasq for each sandbox instance,
enabling network-dependent integration testing of AI-generated patches.

Architecture:
    - Each sandbox gets isolated network namespace with dedicated dnsmasq instance
    - Simulates production DNS configuration for realistic testing
    - Supports network policy validation and DNS-based service discovery testing
    - Automatically provisions and tears down network resources

Author: Project Aura Team
Created: 2025-11-12
Version: 1.0.0
"""

import asyncio
import logging
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import boto3

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SandboxNetworkStatus(Enum):
    """Status of sandbox network environment."""

    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    TEARING_DOWN = "tearing_down"
    TERMINATED = "terminated"
    FAILED = "failed"


class NetworkIsolationLevel(Enum):
    """Level of network isolation for sandbox."""

    NONE = "none"  # No isolation (use host network)
    CONTAINER = "container"  # Container-level isolation
    VPC = "vpc"  # Dedicated VPC subnet
    FULL = "full"  # Completely isolated VPC


@dataclass
class DnsmasqConfig:
    """Configuration for dnsmasq instance."""

    port: int = 53
    cache_size: int = 1000
    upstream_servers: list[str] = field(default_factory=lambda: ["1.1.1.1", "8.8.8.8"])
    local_domain: str = "sandbox.aura.local"
    enable_dnssec: bool = True
    enable_dhcp: bool = False
    dhcp_range: str | None = None
    custom_hosts: dict[str, str] = field(default_factory=dict)

    def to_config_file(self) -> str:
        """Generate dnsmasq.conf content."""
        config_lines = [
            "# Project Aura Sandbox Network Configuration",
            f"# Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            "# Core settings",
            "no-resolv",
            "no-hosts",
            "listen-address=0.0.0.0",
            "bind-interfaces",
            f"port={self.port}",
            f"cache-size={self.cache_size}",
            "neg-ttl=3600",
            "",
            "# Upstream DNS servers",
        ]

        for server in self.upstream_servers:
            config_lines.append(f"server={server}")

        config_lines.extend(
            [
                "",
                "# Local domain configuration",
                f"local=/{self.local_domain}/",
                f"domain={self.local_domain}",
                "expand-hosts",
                "",
            ]
        )

        if self.enable_dnssec:
            config_lines.extend(
                [
                    "# DNSSEC validation",
                    "dnssec",
                    "trust-anchor=.,20326,8,2,E06D44B80B8F1D39A95C0B0D7C65D08458E880409BBC683457104237C7F8EC8D",
                    "",
                ]
            )

        config_lines.extend(
            [
                "# Security settings",
                "stop-dns-rebind",
                "rebind-localhost-ok",
                "bogus-priv",
                "",
            ]
        )

        if self.enable_dhcp and self.dhcp_range:
            config_lines.extend(
                [
                    "# DHCP configuration",
                    f"dhcp-range={self.dhcp_range}",
                    "dhcp-option=option:router,172.16.0.1",
                    "dhcp-option=option:dns-server,172.16.0.2",
                    "dhcp-leasefile=/var/lib/dnsmasq/dnsmasq.leases",
                    "",
                ]
            )

        if self.custom_hosts:
            config_lines.append("# Custom host entries")
            for hostname, ip in self.custom_hosts.items():
                config_lines.append(f"address=/{hostname}/{ip}")
            config_lines.append("")

        return "\n".join(config_lines)


@dataclass
class SandboxNetwork:
    """Represents an isolated sandbox network environment."""

    sandbox_id: str
    status: SandboxNetworkStatus
    isolation_level: NetworkIsolationLevel
    dnsmasq_config: DnsmasqConfig
    vpc_id: str | None = None
    subnet_id: str | None = None
    security_group_id: str | None = None
    ecs_task_arn: str | None = None
    container_id: str | None = None
    dns_endpoint: str | None = None
    dhcp_endpoint: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    terminated_at: datetime | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "sandbox_id": self.sandbox_id,
            "status": self.status.value,
            "isolation_level": self.isolation_level.value,
            "vpc_id": self.vpc_id,
            "subnet_id": self.subnet_id,
            "security_group_id": self.security_group_id,
            "ecs_task_arn": self.ecs_task_arn,
            "container_id": self.container_id,
            "dns_endpoint": self.dns_endpoint,
            "dhcp_endpoint": self.dhcp_endpoint,
            "created_at": self.created_at.isoformat(),
            "terminated_at": (
                self.terminated_at.isoformat() if self.terminated_at else None
            ),
            "metadata": self.metadata,
        }


class SandboxNetworkOrchestrator:
    """
    Orchestrates isolated network environments for sandbox testing.

    Responsibilities:
        - Provision ephemeral dnsmasq containers/tasks for each sandbox
        - Configure isolated DNS zones with custom resolution
        - Manage network lifecycle (provision, monitor, teardown)
        - Track active sandbox networks for cleanup
        - Integrate with HITL approval workflow

    Usage:
        orchestrator = SandboxNetworkOrchestrator(
            environment="dev",
            project_name="aura"
        )

        # Provision sandbox network
        network = await orchestrator.provision_sandbox_network(
            sandbox_id="sandbox-12345",
            isolation_level=NetworkIsolationLevel.CONTAINER
        )

        # Use network in tests...

        # Cleanup
        await orchestrator.terminate_sandbox_network("sandbox-12345")
    """

    def __init__(
        self,
        environment: str = "dev",
        project_name: str = "aura",
        ecs_cluster_name: str | None = None,
        aws_region: str = "us-east-1",
    ):
        """
        Initialize sandbox network orchestrator.

        Args:
            environment: Environment name (dev, qa, prod)
            project_name: Project name for resource naming
            ecs_cluster_name: ECS cluster for Fargate tasks
            aws_region: AWS region
        """
        self.environment = environment
        self.project_name = project_name
        self.ecs_cluster_name = (
            ecs_cluster_name or f"{project_name}-sandbox-{environment}"
        )
        self.aws_region = aws_region
        self._cached_account_id: str | None = None

        # AWS clients
        self.ecs_client = boto3.client("ecs", region_name=aws_region)
        self.ec2_client = boto3.client("ec2", region_name=aws_region)
        self.logs_client = boto3.client("logs", region_name=aws_region)

        # Track active sandbox networks
        self.active_networks: dict[str, SandboxNetwork] = {}

        logger.info(
            f"Initialized SandboxNetworkOrchestrator: "
            f"environment={environment}, region={aws_region}"
        )

    @property
    def aws_account_id(self) -> str:
        """Get AWS account ID from STS or environment variable."""
        import os

        if self._cached_account_id is None:
            # Try environment variable first
            self._cached_account_id = os.environ.get("AWS_ACCOUNT_ID")
            if not self._cached_account_id:
                # Fall back to STS call
                try:
                    sts = boto3.client("sts", region_name=self.aws_region)
                    self._cached_account_id = sts.get_caller_identity()["Account"]
                except Exception as e:
                    logger.warning(f"Failed to get account ID from STS: {e}")
                    # Use placeholder for local development/testing
                    self._cached_account_id = "000000000000"
        return self._cached_account_id

    async def provision_sandbox_network(
        self,
        sandbox_id: str,
        isolation_level: NetworkIsolationLevel = NetworkIsolationLevel.CONTAINER,
        custom_config: DnsmasqConfig | None = None,
        metadata: dict[str, str] | None = None,
    ) -> SandboxNetwork:
        """
        Provision isolated network environment for sandbox.

        Args:
            sandbox_id: Unique sandbox identifier
            isolation_level: Level of network isolation
            custom_config: Optional custom dnsmasq configuration
            metadata: Optional metadata for tracking

        Returns:
            SandboxNetwork instance with provisioned resources

        Raises:
            ValueError: If sandbox already exists
            RuntimeError: If provisioning fails
        """
        if sandbox_id in self.active_networks:
            raise ValueError(f"Sandbox network already exists: {sandbox_id}")

        logger.info(f"Provisioning sandbox network: {sandbox_id}")

        # Create dnsmasq config
        if custom_config is None:
            custom_config = DnsmasqConfig(
                local_domain=f"{sandbox_id}.sandbox.aura.local",
                custom_hosts={
                    "neptune.aura.local": "10.0.3.50",
                    "opensearch.aura.local": "10.0.3.51",
                    "context-retrieval.aura.local": "10.0.3.100",
                },
            )

        # Create sandbox network object
        network = SandboxNetwork(
            sandbox_id=sandbox_id,
            status=SandboxNetworkStatus.PROVISIONING,
            isolation_level=isolation_level,
            dnsmasq_config=custom_config,
            metadata=metadata or {},
        )

        self.active_networks[sandbox_id] = network

        try:
            # Provision based on isolation level
            if isolation_level == NetworkIsolationLevel.CONTAINER:
                await self._provision_container_network(network)
            elif isolation_level == NetworkIsolationLevel.VPC:
                await self._provision_vpc_network(network)
            elif isolation_level == NetworkIsolationLevel.FULL:
                await self._provision_full_isolation(network)
            else:
                # No isolation - use host network
                network.status = SandboxNetworkStatus.ACTIVE
                network.dns_endpoint = "127.0.0.1:53"

            logger.info(f"Successfully provisioned sandbox network: {sandbox_id}")
            return network

        except Exception as e:
            logger.error(f"Failed to provision sandbox network {sandbox_id}: {e}")
            network.status = SandboxNetworkStatus.FAILED
            raise RuntimeError(f"Sandbox network provisioning failed: {e}") from e

    async def _provision_container_network(self, network: SandboxNetwork) -> None:
        """
        Provision container-level isolated network (ECS Fargate task).

        Args:
            network: SandboxNetwork to provision
        """
        logger.info(f"Provisioning container network for {network.sandbox_id}")

        # Generate dnsmasq config
        config_content = network.dnsmasq_config.to_config_file()

        # Create temporary config file (would be stored in S3 in production)
        # Using TemporaryDirectory context manager ensures cleanup
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / f"dnsmasq-{network.sandbox_id}.conf"
            with config_path.open("w") as f:
                f.write(config_content)

            # In production, upload config to S3 here before temp_dir is cleaned up
            # await self._upload_config_to_s3(config_path, network.sandbox_id)

        # Define ECS task (simplified - in production, use task definition)

        # In production, this would:
        # 1. Register task definition
        # 2. Create security group
        # 3. Run task on ECS
        # 4. Wait for task to be running
        # 5. Get task IP for DNS endpoint

        # For now, simulate successful provisioning
        network.status = SandboxNetworkStatus.ACTIVE
        network.ecs_task_arn = f"arn:aws:ecs:{self.aws_region}:{self.aws_account_id}:task/sandbox-{network.sandbox_id}"
        network.dns_endpoint = (
            f"10.0.3.{100 + len(self.active_networks)}:53"  # Simulated IP
        )

        logger.info(
            f"Container network provisioned: {network.sandbox_id} at {network.dns_endpoint}"
        )

    async def _provision_vpc_network(self, network: SandboxNetwork) -> None:
        """
        Provision VPC subnet-level isolated network.

        Args:
            network: SandboxNetwork to provision
        """
        logger.info(f"Provisioning VPC network for {network.sandbox_id}")

        # In production, this would:
        # 1. Create dedicated subnet in existing VPC
        # 2. Create security group with restricted rules
        # 3. Launch Fargate task in dedicated subnet
        # 4. Configure route tables for isolation

        # For now, simulate successful provisioning
        network.status = SandboxNetworkStatus.ACTIVE
        network.vpc_id = "vpc-simulated"
        network.subnet_id = f"subnet-{network.sandbox_id}"
        network.security_group_id = f"sg-{network.sandbox_id}"
        network.dns_endpoint = f"172.16.{len(self.active_networks)}.2:53"

        logger.info(f"VPC network provisioned: {network.sandbox_id}")

    async def _provision_full_isolation(self, network: SandboxNetwork) -> None:
        """
        Provision fully isolated VPC network.

        Args:
            network: SandboxNetwork to provision
        """
        logger.info(f"Provisioning full isolation network for {network.sandbox_id}")

        # In production, this would:
        # 1. Create dedicated VPC with isolated CIDR
        # 2. Create subnets, route tables, NAT gateway
        # 3. Deploy dnsmasq in isolated VPC
        # 4. Set up VPC peering for controlled access

        # For now, simulate successful provisioning
        network.status = SandboxNetworkStatus.ACTIVE
        network.vpc_id = f"vpc-isolated-{network.sandbox_id}"
        network.subnet_id = f"subnet-isolated-{network.sandbox_id}"
        network.dns_endpoint = f"192.168.{len(self.active_networks)}.2:53"

        logger.info(f"Full isolation network provisioned: {network.sandbox_id}")

    async def terminate_sandbox_network(self, sandbox_id: str) -> None:
        """
        Terminate sandbox network and cleanup resources.

        Args:
            sandbox_id: Sandbox identifier to terminate

        Raises:
            ValueError: If sandbox not found
        """
        if sandbox_id not in self.active_networks:
            raise ValueError(f"Sandbox network not found: {sandbox_id}")

        network = self.active_networks[sandbox_id]
        logger.info(f"Terminating sandbox network: {sandbox_id}")

        network.status = SandboxNetworkStatus.TEARING_DOWN

        try:
            # Terminate based on isolation level
            if network.ecs_task_arn:
                # Stop ECS task
                logger.info(f"Stopping ECS task: {network.ecs_task_arn}")
                # In production: self.ecs_client.stop_task(...)

            if network.security_group_id:
                # Delete security group
                logger.info(f"Deleting security group: {network.security_group_id}")
                # In production: self.ec2_client.delete_security_group(...)

            if network.isolation_level == NetworkIsolationLevel.FULL and network.vpc_id:
                # Delete dedicated VPC
                logger.info(f"Deleting VPC: {network.vpc_id}")
                # In production: Full VPC teardown

            network.status = SandboxNetworkStatus.TERMINATED
            network.terminated_at = datetime.now(timezone.utc)

            # Remove from active networks
            del self.active_networks[sandbox_id]

            logger.info(f"Successfully terminated sandbox network: {sandbox_id}")

        except Exception as e:
            logger.error(f"Failed to terminate sandbox network {sandbox_id}: {e}")
            network.status = SandboxNetworkStatus.FAILED
            raise

    async def get_sandbox_network(self, sandbox_id: str) -> SandboxNetwork | None:
        """
        Get sandbox network by ID.

        Args:
            sandbox_id: Sandbox identifier

        Returns:
            SandboxNetwork if found, None otherwise
        """
        return self.active_networks.get(sandbox_id)

    async def list_active_networks(self) -> list[SandboxNetwork]:
        """
        List all active sandbox networks.

        Returns:
            List of active SandboxNetwork instances
        """
        return list(self.active_networks.values())

    async def cleanup_all_networks(self) -> None:
        """Terminate all active sandbox networks (emergency cleanup)."""
        logger.warning(f"Cleaning up all sandbox networks: {len(self.active_networks)}")

        sandbox_ids = list(self.active_networks.keys())
        for sandbox_id in sandbox_ids:
            try:
                await self.terminate_sandbox_network(sandbox_id)
            except Exception as e:
                logger.error(f"Failed to cleanup {sandbox_id}: {e}")

        logger.info("Sandbox network cleanup complete")

    async def health_check(self, sandbox_id: str) -> bool:
        """
        Check health of sandbox network.

        Args:
            sandbox_id: Sandbox identifier

        Returns:
            True if healthy, False otherwise
        """
        network = self.active_networks.get(sandbox_id)
        if not network:
            return False

        # In production, perform actual DNS query to test
        # For now, return True if status is active
        return network.status == SandboxNetworkStatus.ACTIVE


# Example usage and integration with HITL workflow
async def example_usage() -> None:
    """Example usage of SandboxNetworkOrchestrator."""
    orchestrator = SandboxNetworkOrchestrator(environment="dev", project_name="aura")

    # Provision sandbox network for test
    network = await orchestrator.provision_sandbox_network(
        sandbox_id="sandbox-test-001",
        isolation_level=NetworkIsolationLevel.CONTAINER,
        metadata={
            "test_id": "security-patch-001",
            "reviewer": "alice@example.com",
        },
    )

    print(f"Sandbox network provisioned: {network.dns_endpoint}")
    print(f"Status: {network.status.value}")
    print(f"Config:\n{network.dnsmasq_config.to_config_file()}")

    # Simulate test execution...
    await asyncio.sleep(2)

    # Check health
    is_healthy = await orchestrator.health_check("sandbox-test-001")
    print(f"Health check: {'PASS' if is_healthy else 'FAIL'}")

    # Cleanup
    await orchestrator.terminate_sandbox_network("sandbox-test-001")
    print("Sandbox network terminated")


class FargateSandboxOrchestrator:
    """
    ECS Fargate-based sandbox orchestrator for ephemeral patch testing.

    Manages lifecycle of isolated Fargate tasks for patch validation:
    - Creates ephemeral ECS tasks with maximum security restrictions
    - Tracks sandbox state in DynamoDB
    - Enforces resource limits and timeouts
    - Provides isolated network environment per sandbox

    Usage:
        orchestrator = FargateSandboxOrchestrator(environment="dev")

        # Create sandbox
        sandbox = await orchestrator.create_sandbox(
            sandbox_id="sandbox-abc123",
            patch_id="patch-def456",
            test_suite="integration_tests"
        )

        # Check status
        status = await orchestrator.get_sandbox_status("sandbox-abc123")

        # Cleanup
        await orchestrator.destroy_sandbox("sandbox-abc123")
    """

    def __init__(
        self,
        environment: str = "dev",
        aws_region: str = "us-east-1",
    ):
        """
        Initialize Fargate sandbox orchestrator.

        Args:
            environment: Environment name (dev, qa, prod)
            aws_region: AWS region
        """
        self.environment = environment
        self.aws_region = aws_region
        self.cluster_name = f"aura-sandboxes-{environment}"
        self.task_definition = f"sandbox-patch-test-{environment}"
        self.state_table = f"aura-sandbox-state-{environment}"

        # AWS clients
        self.ecs = boto3.client("ecs", region_name=aws_region)
        self.ec2 = boto3.client("ec2", region_name=aws_region)
        self.dynamodb = boto3.resource("dynamodb", region_name=aws_region)
        self.logs = boto3.client("logs", region_name=aws_region)

        # DynamoDB table for state tracking
        self.state_table_resource = self.dynamodb.Table(self.state_table)

        logger.info(
            f"Initialized FargateSandboxOrchestrator: "
            f"environment={environment}, cluster={self.cluster_name}"
        )

    async def create_sandbox(
        self,
        sandbox_id: str,
        patch_id: str,
        test_suite: str,
        isolation_level: str = "container",
        timeout_seconds: int = 3600,
        metadata: dict[str, str] | None = None,
    ) -> dict:
        """
        Launch ephemeral Fargate task for patch testing.

        Args:
            sandbox_id: Unique sandbox identifier
            patch_id: Patch to test
            test_suite: Test suite to run
            isolation_level: Isolation level (container, vpc, full)
            timeout_seconds: Maximum runtime in seconds
            metadata: Optional metadata for tracking

        Returns:
            Sandbox info dict with task ARN, IP, DNS name

        Raises:
            RuntimeError: If task launch fails
        """
        logger.info(f"Creating sandbox {sandbox_id} for patch {patch_id}")

        # Get network configuration from CloudFormation exports
        subnets = await self._get_sandbox_subnets()
        security_groups = await self._get_sandbox_security_groups()

        # Override environment variables per sandbox
        overrides = {
            "containerOverrides": [
                {
                    "name": "sandbox-runtime",
                    "environment": [
                        {"name": "SANDBOX_ID", "value": sandbox_id},
                        {"name": "PATCH_ID", "value": patch_id},
                        {"name": "TEST_SUITE", "value": test_suite},
                        {"name": "ISOLATION_LEVEL", "value": isolation_level},
                        {"name": "MAX_RUNTIME", "value": str(timeout_seconds)},
                        {"name": "ENVIRONMENT", "value": self.environment},
                    ],
                }
            ]
        }

        try:
            # Launch Fargate task (wrap sync boto3 call with asyncio.to_thread)
            response = await asyncio.to_thread(
                self.ecs.run_task,
                cluster=self.cluster_name,
                taskDefinition=self.task_definition,
                launchType="FARGATE",
                networkConfiguration={
                    "awsvpcConfiguration": {
                        "subnets": subnets,
                        "securityGroups": security_groups,
                        "assignPublicIp": "DISABLED",
                    }
                },
                overrides=overrides,
                tags=[
                    {"key": "SandboxID", "value": sandbox_id},
                    {"key": "PatchID", "value": patch_id},
                    {"key": "Environment", "value": self.environment},
                    {"key": "ManagedBy", "value": "FargateSandboxOrchestrator"},
                ],
                enableExecuteCommand=False,  # No exec access for security
            )

            if not response.get("tasks"):
                raise RuntimeError("No tasks returned from run_task")

            task = response["tasks"][0]
            task_arn = task["taskArn"]

            # Store state in DynamoDB
            await self._store_sandbox_state(
                sandbox_id=sandbox_id,
                task_arn=task_arn,
                patch_id=patch_id,
                test_suite=test_suite,
                status="PROVISIONING",
                metadata=metadata or {},
                ttl_seconds=timeout_seconds
                + 600,  # TTL: runtime + 10min cleanup buffer
            )

            logger.info(f"Sandbox {sandbox_id} created: task_arn={task_arn}")

            return {
                "sandbox_id": sandbox_id,
                "task_arn": task_arn,
                "dns_name": f"{sandbox_id}.sandbox.{self.environment}.aura.local",
                "status": "PROVISIONING",
                "cluster": self.cluster_name,
            }

        except Exception as e:
            logger.error(f"Failed to create sandbox {sandbox_id}: {e}")
            raise RuntimeError(f"Sandbox creation failed: {e}") from e

    async def destroy_sandbox(self, sandbox_id: str) -> None:
        """
        Stop Fargate task and clean up resources.

        Args:
            sandbox_id: Sandbox identifier

        Raises:
            ValueError: If sandbox not found
        """
        logger.info(f"Destroying sandbox {sandbox_id}")

        # Get task ARN from DynamoDB
        state = await self._get_sandbox_state(sandbox_id)
        if not state:
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        task_arn = state.get("task_arn")
        if not task_arn:
            logger.warning(f"No task ARN found for sandbox {sandbox_id}")
            return

        try:
            # Stop Fargate task (wrap sync boto3 call with asyncio.to_thread)
            await asyncio.to_thread(
                self.ecs.stop_task,
                cluster=self.cluster_name,
                task=task_arn,
                reason=f"Sandbox {sandbox_id} cleanup requested",
            )

            # Update state
            await self._update_sandbox_state(sandbox_id, status="TERMINATED")

            logger.info(f"Sandbox {sandbox_id} destroyed successfully")

        except Exception as e:
            logger.error(f"Failed to destroy sandbox {sandbox_id}: {e}")
            raise

    async def get_sandbox_status(self, sandbox_id: str) -> dict:
        """
        Check sandbox task status and test results.

        Args:
            sandbox_id: Sandbox identifier

        Returns:
            Status dict with task state, exit code, logs

        Raises:
            ValueError: If sandbox not found
        """
        # Get task ARN from DynamoDB
        state = await self._get_sandbox_state(sandbox_id)
        if not state:
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        task_arn = state.get("task_arn")

        try:
            # Describe task to get current status (wrap sync boto3 call)
            response = await asyncio.to_thread(
                self.ecs.describe_tasks,
                cluster=self.cluster_name,
                tasks=[task_arn],
            )

            if not response.get("tasks"):
                return {
                    "sandbox_id": sandbox_id,
                    "status": "NOT_FOUND",
                    "message": "Task not found in ECS",
                }

            task = response["tasks"][0]
            last_status = task.get("lastStatus")

            # Map ECS status to sandbox status
            status_map = {
                "PENDING": "PROVISIONING",
                "RUNNING": "ACTIVE",
                "STOPPED": "TERMINATED",
                "DEPROVISIONING": "TEARING_DOWN",
            }

            sandbox_status = status_map.get(last_status, "UNKNOWN")

            # Get exit code if stopped
            containers = task.get("containers", [])
            exit_code = None
            if containers and last_status == "STOPPED":
                exit_code = containers[0].get("exitCode")

            result = {
                "sandbox_id": sandbox_id,
                "task_arn": task_arn,
                "status": sandbox_status,
                "ecs_status": last_status,
                "exit_code": exit_code,
                "created_at": task.get("createdAt"),
                "stopped_at": task.get("stoppedAt"),
            }

            # Update state in DynamoDB
            await self._update_sandbox_state(sandbox_id, status=sandbox_status)

            return result

        except Exception as e:
            logger.error(f"Failed to get sandbox status {sandbox_id}: {e}")
            raise

    async def get_sandbox_logs(self, sandbox_id: str, tail: int = 100) -> list[str]:
        """
        Retrieve CloudWatch logs for sandbox task.

        Args:
            sandbox_id: Sandbox identifier
            tail: Number of log lines to retrieve

        Returns:
            List of log lines
        """
        log_group = f"/ecs/sandboxes-{self.environment}"
        log_stream_prefix = f"sandbox/{sandbox_id}"

        try:
            # Get log streams (wrap sync boto3 call)
            response = await asyncio.to_thread(
                self.logs.describe_log_streams,
                logGroupName=log_group,
                logStreamNamePrefix=log_stream_prefix,
                orderBy="LastEventTime",
                descending=True,
                limit=1,
            )

            if not response.get("logStreams"):
                return []

            log_stream = response["logStreams"][0]["logStreamName"]

            # Get log events (wrap sync boto3 call)
            logs_response = await asyncio.to_thread(
                self.logs.get_log_events,
                logGroupName=log_group,
                logStreamName=log_stream,
                limit=tail,
                startFromHead=False,
            )

            events = logs_response.get("events", [])
            return [event["message"] for event in events]

        except Exception as e:
            logger.error(f"Failed to get logs for sandbox {sandbox_id}: {e}")
            return []

    async def list_active_sandboxes(self) -> list[dict]:
        """
        List all active sandbox tasks.

        Returns:
            List of active sandbox dicts
        """
        try:
            # Query DynamoDB for active sandboxes (wrap sync boto3 call)
            response = await asyncio.to_thread(
                self.state_table_resource.scan,
                FilterExpression="attribute_exists(sandbox_id) AND #status IN (:provisioning, :active)",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":provisioning": "PROVISIONING",
                    ":active": "ACTIVE",
                },
            )

            items = response.get("Items", [])
            # Type annotation for mypy
            return items if isinstance(items, list) else []

        except Exception as e:
            logger.error(f"Failed to list active sandboxes: {e}")
            return []

    # Helper methods

    async def _get_sandbox_subnets(self) -> list[str]:
        """Get sandbox private subnets from VPC."""
        # In production, query from CloudFormation exports or VPC tags
        # Wrap sync boto3 call with asyncio.to_thread
        response = await asyncio.to_thread(
            self.ec2.describe_subnets,
            Filters=[
                {"Name": "tag:Environment", "Values": [self.environment]},
                {"Name": "tag:Type", "Values": ["private"]},
            ],
        )
        subnets = [subnet["SubnetId"] for subnet in response.get("Subnets", [])]

        if not subnets:
            # Query SSM for configured sandbox subnets
            try:
                import boto3

                ssm = boto3.client("ssm", region_name=self.aws_region)
                response = await asyncio.to_thread(
                    ssm.get_parameter,
                    Name=f"/aura/{self.environment}/sandbox/subnet-ids",
                )
                subnet_ids = response["Parameter"]["Value"].split(",")
                if subnet_ids:
                    return subnet_ids[:2]
            except Exception as ssm_error:
                logger.error(f"Failed to get sandbox subnets from SSM: {ssm_error}")

            # Raise error instead of using placeholders that would cause task failures
            raise RuntimeError(
                f"No sandbox subnets found for environment '{self.environment}'. "
                "Please configure private subnets with tags Environment={environment} and Type=private, "
                f"or set SSM parameter /aura/{self.environment}/sandbox/subnet-ids"
            )

        return subnets[:2]  # Return first 2 for HA

    async def _get_sandbox_security_groups(self) -> list[str]:
        """Get sandbox security group from CloudFormation exports."""
        # In production, query from CloudFormation exports
        # Wrap sync boto3 call with asyncio.to_thread
        response = await asyncio.to_thread(
            self.ec2.describe_security_groups,
            Filters=[
                {"Name": "tag:Environment", "Values": [self.environment]},
                {
                    "Name": "tag:Name",
                    "Values": [f"sg-{self.environment}-sandbox-isolated"],
                },
            ],
        )

        security_groups = [sg["GroupId"] for sg in response.get("SecurityGroups", [])]

        if not security_groups:
            # Query SSM for configured sandbox security group
            try:
                import boto3

                ssm = boto3.client("ssm", region_name=self.aws_region)
                response = await asyncio.to_thread(
                    ssm.get_parameter,
                    Name=f"/aura/{self.environment}/sandbox/security-group-id",
                )
                sg_id = response["Parameter"]["Value"]
                if sg_id:
                    return [sg_id]
            except Exception as ssm_error:
                logger.error(
                    f"Failed to get sandbox security group from SSM: {ssm_error}"
                )

            # Raise error instead of using placeholders that would cause task failures
            raise RuntimeError(
                f"No sandbox security group found for environment '{self.environment}'. "
                f"Please configure security group with tags Environment={self.environment} and "
                f"Name=sg-{self.environment}-sandbox-isolated, "
                f"or set SSM parameter /aura/{self.environment}/sandbox/security-group-id"
            )

        return [security_groups[0]]

    async def _store_sandbox_state(
        self,
        sandbox_id: str,
        task_arn: str,
        patch_id: str,
        test_suite: str,
        status: str,
        metadata: dict,
        ttl_seconds: int,
    ) -> None:
        """Store sandbox state in DynamoDB."""
        item = {
            "sandbox_id": sandbox_id,
            "task_arn": task_arn,
            "patch_id": patch_id,
            "test_suite": test_suite,
            "status": status,
            "created_at": int(time.time()),
            "ttl": int(time.time()) + ttl_seconds,
            "environment": self.environment,
            **metadata,
        }

        # Wrap sync boto3 call with asyncio.to_thread
        await asyncio.to_thread(self.state_table_resource.put_item, Item=item)
        logger.debug(f"Stored state for sandbox {sandbox_id}")

    async def _get_sandbox_state(self, sandbox_id: str) -> dict | None:
        """Get sandbox state from DynamoDB."""
        try:
            # Wrap sync boto3 call with asyncio.to_thread
            response = await asyncio.to_thread(
                self.state_table_resource.get_item,
                Key={"sandbox_id": sandbox_id},
            )
            item = response.get("Item")
            # Type guard for mypy
            return item if isinstance(item, dict) or item is None else None
        except Exception as e:
            logger.error(f"Failed to get sandbox state {sandbox_id}: {e}")
            return None

    async def _update_sandbox_state(self, sandbox_id: str, **kwargs) -> None:
        """Update sandbox state in DynamoDB."""
        update_expression = "SET " + ", ".join([f"#{k} = :{k}" for k in kwargs])
        expression_attribute_names = {f"#{k}": k for k in kwargs}
        expression_attribute_values = {f":{k}": v for k, v in kwargs.items()}

        # Wrap sync boto3 call with asyncio.to_thread
        await asyncio.to_thread(
            self.state_table_resource.update_item,
            Key={"sandbox_id": sandbox_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
        )
        logger.debug(f"Updated state for sandbox {sandbox_id}")


# Example usage for Fargate sandbox orchestrator
async def example_fargate_usage() -> None:
    """Example usage of FargateSandboxOrchestrator."""
    orchestrator = FargateSandboxOrchestrator(environment="dev")

    # Create sandbox for patch testing
    sandbox = await orchestrator.create_sandbox(
        sandbox_id="sandbox-test-fargate-001",
        patch_id="patch-sec-123",
        test_suite="security_integration_tests",
        metadata={
            "reviewer": "bob@example.com",
            "priority": "high",
        },
    )

    print(f"Sandbox created: {sandbox}")

    # Wait for task to start
    await asyncio.sleep(10)

    # Check status
    status = await orchestrator.get_sandbox_status("sandbox-test-fargate-001")
    print(f"Sandbox status: {status}")

    # Get logs
    logs = await orchestrator.get_sandbox_logs("sandbox-test-fargate-001", tail=20)
    print("Sandbox logs:\n" + "\n".join(logs))

    # List active sandboxes
    active = await orchestrator.list_active_sandboxes()
    print(f"Active sandboxes: {len(active)}")

    # Cleanup
    await orchestrator.destroy_sandbox("sandbox-test-fargate-001")
    print("Sandbox destroyed")


if __name__ == "__main__":
    # Run Fargate example (comment out if running K8s-based example)
    asyncio.run(example_fargate_usage())
