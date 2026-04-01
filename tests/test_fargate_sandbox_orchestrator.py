"""
Project Aura - Fargate Sandbox Orchestrator Integration Tests

Tests for FargateSandboxOrchestrator ECS Fargate integration.
"""

# ruff: noqa: PLR2004

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.services.sandbox_network_service import FargateSandboxOrchestrator


@pytest.fixture
def mock_aws_clients():
    """Mock AWS clients for testing."""
    with (
        patch("boto3.client") as mock_boto_client,
        patch("boto3.resource") as mock_boto_resource,
    ):

        # Mock ECS client
        mock_ecs = Mock()
        mock_ecs.run_task.return_value = {
            "tasks": [
                {
                    "taskArn": "arn:aws:ecs:us-east-1:123456789012:task/sandbox-test",
                    "lastStatus": "PENDING",
                    "createdAt": datetime.now(),
                }
            ]
        }
        mock_ecs.describe_tasks.return_value = {
            "tasks": [
                {
                    "taskArn": "arn:aws:ecs:us-east-1:123456789012:task/sandbox-test",
                    "lastStatus": "RUNNING",
                    "containers": [
                        {
                            "name": "sandbox-runtime",
                            "exitCode": None,
                        }
                    ],
                    "createdAt": datetime.now(),
                }
            ]
        }
        mock_ecs.stop_task.return_value = {"task": {"lastStatus": "STOPPING"}}

        # Mock EC2 client
        mock_ec2 = Mock()
        mock_ec2.describe_subnets.return_value = {
            "Subnets": [
                {"SubnetId": "subnet-test1"},
                {"SubnetId": "subnet-test2"},
            ]
        }
        mock_ec2.describe_security_groups.return_value = {
            "SecurityGroups": [{"GroupId": "sg-test-sandbox"}]
        }

        # Mock CloudWatch Logs client
        mock_logs = Mock()
        mock_logs.describe_log_streams.return_value = {
            "logStreams": [{"logStreamName": "sandbox/sandbox-test/abc123"}]
        }
        mock_logs.get_log_events.return_value = {
            "events": [
                {"message": "Sandbox starting...", "timestamp": 1234567890},
                {"message": "Running tests...", "timestamp": 1234567891},
            ]
        }

        # Mock DynamoDB
        mock_dynamodb_table = Mock()
        mock_dynamodb_table.put_item.return_value = {}
        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "sandbox_id": "sandbox-test",
                "task_arn": "arn:aws:ecs:us-east-1:123456789012:task/sandbox-test",
                "status": "ACTIVE",
            }
        }
        mock_dynamodb_table.update_item.return_value = {}
        mock_dynamodb_table.scan.return_value = {
            "Items": [
                {"sandbox_id": "sandbox-1", "status": "ACTIVE"},
                {"sandbox_id": "sandbox-2", "status": "PROVISIONING"},
            ]
        }

        mock_dynamodb_resource = Mock()
        mock_dynamodb_resource.Table.return_value = mock_dynamodb_table

        # Configure boto3 mocks
        def client_side_effect(service, **kwargs):
            if service == "ecs":
                return mock_ecs
            if service == "ec2":
                return mock_ec2
            if service == "logs":
                return mock_logs
            return Mock()

        mock_boto_client.side_effect = client_side_effect
        mock_boto_resource.return_value = mock_dynamodb_resource

        yield {
            "ecs": mock_ecs,
            "ec2": mock_ec2,
            "logs": mock_logs,
            "dynamodb_table": mock_dynamodb_table,
        }


@pytest.mark.anyio
async def test_fargate_orchestrator_initialization(mock_aws_clients):
    """Test FargateSandboxOrchestrator initialization."""
    orchestrator = FargateSandboxOrchestrator(environment="dev", aws_region="us-east-1")

    assert orchestrator.environment == "dev"
    assert orchestrator.cluster_name == "aura-sandboxes-dev"
    assert orchestrator.task_definition == "sandbox-patch-test-dev"
    assert orchestrator.state_table == "aura-sandbox-state-dev"


@pytest.mark.anyio
async def test_create_sandbox(mock_aws_clients):
    """Test sandbox creation."""
    orchestrator = FargateSandboxOrchestrator(environment="dev")

    sandbox = await orchestrator.create_sandbox(
        sandbox_id="sandbox-test-001",
        patch_id="patch-abc123",
        test_suite="integration_tests",
        metadata={"reviewer": "test@example.com"},
    )

    # Verify sandbox created
    assert sandbox["sandbox_id"] == "sandbox-test-001"
    assert sandbox["status"] == "PROVISIONING"
    assert "task_arn" in sandbox
    assert sandbox["dns_name"] == "sandbox-test-001.sandbox.dev.aura.local"

    # Verify ECS run_task called
    mock_aws_clients["ecs"].run_task.assert_called_once()
    call_args = mock_aws_clients["ecs"].run_task.call_args[1]
    assert call_args["cluster"] == "aura-sandboxes-dev"
    assert call_args["taskDefinition"] == "sandbox-patch-test-dev"
    assert call_args["launchType"] == "FARGATE"

    # Verify DynamoDB state stored
    mock_aws_clients["dynamodb_table"].put_item.assert_called_once()


@pytest.mark.anyio
async def test_get_sandbox_status(mock_aws_clients):
    """Test getting sandbox status."""
    orchestrator = FargateSandboxOrchestrator(environment="dev")

    status = await orchestrator.get_sandbox_status("sandbox-test")

    assert status["sandbox_id"] == "sandbox-test"
    assert status["status"] == "ACTIVE"
    assert status["ecs_status"] == "RUNNING"
    assert status["exit_code"] is None

    # Verify ECS describe_tasks called
    mock_aws_clients["ecs"].describe_tasks.assert_called_once()


@pytest.mark.anyio
async def test_destroy_sandbox(mock_aws_clients):
    """Test sandbox destruction."""
    orchestrator = FargateSandboxOrchestrator(environment="dev")

    await orchestrator.destroy_sandbox("sandbox-test")

    # Verify ECS stop_task called
    mock_aws_clients["ecs"].stop_task.assert_called_once()
    call_args = mock_aws_clients["ecs"].stop_task.call_args[1]
    assert call_args["cluster"] == "aura-sandboxes-dev"

    # Verify DynamoDB state updated
    mock_aws_clients["dynamodb_table"].update_item.assert_called_once()


@pytest.mark.anyio
async def test_get_sandbox_logs(mock_aws_clients):
    """Test retrieving sandbox logs."""
    orchestrator = FargateSandboxOrchestrator(environment="dev")

    logs = await orchestrator.get_sandbox_logs("sandbox-test", tail=10)

    assert len(logs) == 2
    assert "Sandbox starting..." in logs[0]
    assert "Running tests..." in logs[1]

    # Verify CloudWatch Logs API calls
    mock_aws_clients["logs"].describe_log_streams.assert_called_once()
    mock_aws_clients["logs"].get_log_events.assert_called_once()


@pytest.mark.anyio
async def test_list_active_sandboxes(mock_aws_clients):
    """Test listing active sandboxes."""
    orchestrator = FargateSandboxOrchestrator(environment="dev")

    active = await orchestrator.list_active_sandboxes()

    assert len(active) == 2
    assert active[0]["sandbox_id"] == "sandbox-1"
    assert active[1]["sandbox_id"] == "sandbox-2"

    # Verify DynamoDB scan called
    mock_aws_clients["dynamodb_table"].scan.assert_called_once()


@pytest.mark.anyio
async def test_sandbox_not_found(mock_aws_clients):
    """Test error handling when sandbox not found."""
    orchestrator = FargateSandboxOrchestrator(environment="dev")

    # Mock DynamoDB to return no item
    mock_aws_clients["dynamodb_table"].get_item.return_value = {}

    with pytest.raises(ValueError, match="Sandbox not found"):
        await orchestrator.destroy_sandbox("nonexistent-sandbox")


@pytest.mark.anyio
async def test_sandbox_creation_failure(mock_aws_clients):
    """Test error handling when sandbox creation fails."""
    orchestrator = FargateSandboxOrchestrator(environment="dev")

    # Mock ECS to return empty tasks
    mock_aws_clients["ecs"].run_task.return_value = {"tasks": []}

    with pytest.raises(RuntimeError, match="Sandbox creation failed"):
        await orchestrator.create_sandbox(
            sandbox_id="sandbox-fail", patch_id="patch-123", test_suite="tests"
        )


@pytest.mark.anyio
async def test_subnet_discovery(mock_aws_clients):
    """Test automatic subnet discovery."""
    orchestrator = FargateSandboxOrchestrator(environment="dev")

    subnets = await orchestrator._get_sandbox_subnets()

    assert len(subnets) == 2
    assert "subnet-test1" in subnets
    assert "subnet-test2" in subnets

    # Verify EC2 describe_subnets called
    mock_aws_clients["ec2"].describe_subnets.assert_called_once()


@pytest.mark.anyio
async def test_security_group_discovery(mock_aws_clients):
    """Test automatic security group discovery."""
    orchestrator = FargateSandboxOrchestrator(environment="dev")

    security_groups = await orchestrator._get_sandbox_security_groups()

    assert len(security_groups) == 1
    assert security_groups[0] == "sg-test-sandbox"

    # Verify EC2 describe_security_groups called
    mock_aws_clients["ec2"].describe_security_groups.assert_called_once()


@pytest.mark.anyio
async def test_sandbox_metadata_storage(mock_aws_clients):
    """Test sandbox metadata is stored correctly."""
    orchestrator = FargateSandboxOrchestrator(environment="dev")

    await orchestrator.create_sandbox(
        sandbox_id="sandbox-meta-test",
        patch_id="patch-xyz",
        test_suite="security_tests",
        timeout_seconds=7200,
        metadata={
            "reviewer": "alice@example.com",
            "priority": "high",
            "ticket": "JIRA-123",
        },
    )

    # Verify DynamoDB put_item called with correct metadata
    call_args = mock_aws_clients["dynamodb_table"].put_item.call_args
    item = call_args[1]["Item"]

    assert item["sandbox_id"] == "sandbox-meta-test"
    assert item["patch_id"] == "patch-xyz"
    assert item["test_suite"] == "security_tests"
    assert item["reviewer"] == "alice@example.com"
    assert item["priority"] == "high"
    assert item["ticket"] == "JIRA-123"
    assert "ttl" in item  # TTL should be set


@pytest.mark.anyio
async def test_sandbox_status_mapping(mock_aws_clients):
    """Test ECS status to sandbox status mapping."""
    orchestrator = FargateSandboxOrchestrator(environment="dev")

    # Test different ECS statuses
    test_cases = [
        ("PENDING", "PROVISIONING"),
        ("RUNNING", "ACTIVE"),
        ("STOPPED", "TERMINATED"),
        ("DEPROVISIONING", "TEARING_DOWN"),
    ]

    for ecs_status, expected_sandbox_status in test_cases:
        mock_aws_clients["ecs"].describe_tasks.return_value = {
            "tasks": [
                {
                    "taskArn": "arn:aws:ecs:us-east-1:123456789012:task/test",
                    "lastStatus": ecs_status,
                    "containers": [],
                    "createdAt": datetime.now(),
                }
            ]
        }

        status = await orchestrator.get_sandbox_status("sandbox-test")
        assert status["status"] == expected_sandbox_status
        assert status["ecs_status"] == ecs_status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
