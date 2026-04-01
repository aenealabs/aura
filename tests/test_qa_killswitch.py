"""
Tests for QA Environment Kill-Switch Script
============================================
Unit tests covering pre-flight validation, shutdown sequencing,
restore sequencing, state file management, error handling,
idempotency, and dry-run mode.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from qa_killswitch import (
    ENVIRONMENT,
    EVENTBRIDGE_SCHEDULES,
    KMS_STACK_NAME,
    PROJECT_NAME,
    STACK_DEFINITIONS,
    DeletedStack,
    KillSwitchState,
    NeptuneSnapshotManager,
    StackManager,
    _build_deploy_configs,
    cleanup_cloudwatch_logs,
    cleanup_config_recorder,
    cleanup_orphaned_elbs,
    disable_schedules,
    enable_schedules,
    resolve_parameters,
    schedule_kms_key_deletion,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_cfn():
    """Mock CloudFormation client."""
    client = MagicMock()
    client.describe_stacks.return_value = {
        "Stacks": [{"StackStatus": "CREATE_COMPLETE", "Outputs": []}]
    }
    return client


@pytest.fixture
def mock_neptune():
    """Mock Neptune client."""
    client = MagicMock()
    client.create_db_cluster_snapshot.return_value = {}
    client.describe_db_cluster_snapshots.return_value = {
        "DBClusterSnapshots": [{"Status": "available"}]
    }
    return client


@pytest.fixture
def mock_scheduler():
    """Mock EventBridge Scheduler client."""
    client = MagicMock()
    client.get_schedule.return_value = {
        "ScheduleExpression": "cron(0 1 ? * * *)",
        "FlexibleTimeWindow": {"Mode": "OFF"},
        "Target": {
            "Arn": "arn:aws:lambda:us-east-1:123:function:test",
            "RoleArn": "arn:aws:iam::123:role/test",
        },
        "State": "ENABLED",
    }
    return client


@pytest.fixture
def stack_manager(mock_cfn):
    return StackManager(mock_cfn, "us-east-1")


@pytest.fixture
def snapshot_manager(mock_neptune):
    return NeptuneSnapshotManager(mock_neptune)


# ---------------------------------------------------------------------------
# KillSwitchState Tests
# ---------------------------------------------------------------------------


class TestKillSwitchState:
    def test_default_state(self):
        state = KillSwitchState()
        assert state.schema_version == 1
        assert state.environment == ENVIRONMENT
        assert state.status == "unknown"
        assert state.deleted_stacks == []
        assert state.disabled_schedules == []
        assert state.neptune_snapshot_id is None

    def test_state_serialization(self):
        state = KillSwitchState(
            status="shutdown",
            shutdown_timestamp="2026-02-15T14:30:00Z",
            shutdown_by="arn:aws:iam::123:user/engineer",
            neptune_snapshot_id="aura-neptune-qa-ks-20260215-143000",
            deleted_stacks=[
                {
                    "stack_name": "aura-neptune-qa",
                    "template_file": "deploy/cloudformation/neptune-simplified.yaml",
                    "deleted_at": "2026-02-15T14:30:00Z",
                }
            ],
        )
        data = json.loads(json.dumps(state.__dict__, default=str))
        assert data["status"] == "shutdown"
        assert data["neptune_snapshot_id"] == "aura-neptune-qa-ks-20260215-143000"
        assert len(data["deleted_stacks"]) == 1

    def test_state_from_dict(self):
        data = {
            "schema_version": 1,
            "environment": "qa",
            "status": "shutdown",
            "shutdown_timestamp": "2026-02-15T14:30:00Z",
            "shutdown_by": "arn:aws:iam::123:user/engineer",
            "neptune_snapshot_id": "snap-123",
            "deleted_stacks": [],
            "disabled_schedules": ["aura-qa-scale-down"],
            "restore_timestamp": None,
            "restore_by": None,
            "phases_completed": [1, 2, 3],
        }
        state = KillSwitchState(**data)
        assert state.status == "shutdown"
        assert state.phases_completed == [1, 2, 3]

    def test_state_ignores_unknown_fields(self):
        """State should be constructable even if extra fields exist."""
        data = {"status": "shutdown", "unknown_field": "value"}
        filtered = {
            k: v for k, v in data.items() if k in KillSwitchState.__dataclass_fields__
        }
        state = KillSwitchState(**filtered)
        assert state.status == "shutdown"


# ---------------------------------------------------------------------------
# StackManager Tests
# ---------------------------------------------------------------------------


class TestStackManager:
    def test_get_stack_status_exists(self, stack_manager, mock_cfn):
        mock_cfn.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE"}]
        }
        assert stack_manager.get_stack_status("aura-neptune-qa") == "CREATE_COMPLETE"

    def test_get_stack_status_not_found(self, stack_manager, mock_cfn):
        from botocore.exceptions import ClientError

        mock_cfn.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Stack does not exist"}},
            "DescribeStacks",
        )
        assert stack_manager.get_stack_status("nonexistent-stack") is None

    def test_get_stack_output(self, stack_manager, mock_cfn):
        mock_cfn.describe_stacks.return_value = {
            "Stacks": [
                {
                    "Outputs": [
                        {"OutputKey": "VpcId", "OutputValue": "vpc-123"},
                        {"OutputKey": "SubnetIds", "OutputValue": "subnet-1,subnet-2"},
                    ]
                }
            ]
        }
        assert (
            stack_manager.get_stack_output("aura-networking-qa", "VpcId") == "vpc-123"
        )
        assert stack_manager.get_stack_output("aura-networking-qa", "Missing") is None

    def test_delete_stack_dry_run(self, stack_manager, mock_cfn):
        mock_cfn.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE"}]
        }
        result = stack_manager.delete_stack("aura-neptune-qa", dry_run=True)
        assert result is True
        mock_cfn.delete_stack.assert_not_called()

    def test_delete_stack_already_deleted(self, stack_manager, mock_cfn):
        from botocore.exceptions import ClientError

        mock_cfn.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Stack does not exist"}},
            "DescribeStacks",
        )
        result = stack_manager.delete_stack("aura-neptune-qa", dry_run=False)
        assert result is True
        mock_cfn.delete_stack.assert_not_called()

    def test_delete_stack_execute(self, stack_manager, mock_cfn):
        # First call: stack exists. Subsequent: deleted
        mock_cfn.describe_stacks.side_effect = [
            {"Stacks": [{"StackStatus": "CREATE_COMPLETE"}]},  # initial check
            {"Stacks": [{"StackStatus": "DELETE_IN_PROGRESS"}]},  # first poll
            {"Stacks": [{"StackStatus": "DELETE_COMPLETE"}]},  # second poll
        ]
        result = stack_manager.delete_stack("aura-neptune-qa", dry_run=False)
        assert result is True
        mock_cfn.delete_stack.assert_called_once_with(StackName="aura-neptune-qa")

    def test_delete_stack_in_progress_waits(self, stack_manager, mock_cfn):
        mock_cfn.describe_stacks.side_effect = [
            {"Stacks": [{"StackStatus": "DELETE_IN_PROGRESS"}]},  # initial
            {"Stacks": [{"StackStatus": "DELETE_COMPLETE"}]},  # poll
        ]
        result = stack_manager.delete_stack("aura-neptune-qa", dry_run=False)
        assert result is True
        mock_cfn.delete_stack.assert_not_called()  # Already in progress

    def test_delete_stack_active_operation_fails(self, stack_manager, mock_cfn):
        mock_cfn.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "UPDATE_IN_PROGRESS"}]
        }
        result = stack_manager.delete_stack("aura-neptune-qa", dry_run=False)
        assert result is False

    def test_deploy_stack_dry_run(self, stack_manager):
        result = stack_manager.deploy_stack(
            "aura-neptune-qa",
            "deploy/cloudformation/neptune-simplified.yaml",
            {"Environment": "qa"},
            {"Layer": "data"},
            dry_run=True,
        )
        assert result is True

    @patch("qa_killswitch.subprocess.run")
    def test_deploy_stack_execute(self, mock_run, stack_manager):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = stack_manager.deploy_stack(
            "aura-neptune-qa",
            "deploy/cloudformation/neptune-simplified.yaml",
            {"Environment": "qa", "ProjectName": "aura"},
            {"Layer": "data"},
            dry_run=False,
        )
        assert result is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "aws"
        assert cmd[1] == "cloudformation"
        assert cmd[2] == "deploy"
        assert "--no-fail-on-empty-changeset" in cmd
        # Verify tags are separate args, not garbled (C3 regression test)
        tags_idx = cmd.index("--tags")
        assert cmd[tags_idx + 1].startswith("Project=")
        assert cmd[tags_idx + 2].startswith("Environment=")
        assert cmd[tags_idx + 3].startswith("Layer=")

    @patch("qa_killswitch.subprocess.run")
    def test_deploy_stack_no_changes(self, mock_run, stack_manager):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="", stderr="No updates are to be performed"
        )
        result = stack_manager.deploy_stack(
            "aura-neptune-qa",
            "deploy/cloudformation/neptune-simplified.yaml",
            {"Environment": "qa"},
            {"Layer": "data"},
            dry_run=False,
        )
        assert result is True

    @patch("qa_killswitch.subprocess.run")
    def test_deploy_stack_failure(self, mock_run, stack_manager):
        """Deploy failure returns False (H2 regression test)."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Stack creation failed"
        )
        result = stack_manager.deploy_stack(
            "aura-neptune-qa",
            "deploy/cloudformation/neptune-simplified.yaml",
            {"Environment": "qa"},
            {"Layer": "data"},
            dry_run=False,
        )
        assert result is False


# ---------------------------------------------------------------------------
# NeptuneSnapshotManager Tests
# ---------------------------------------------------------------------------


class TestNeptuneSnapshotManager:
    def test_create_snapshot_dry_run(self, snapshot_manager, mock_neptune):
        sid = snapshot_manager.create_snapshot(dry_run=True)
        assert sid is not None
        assert sid.startswith("aura-neptune-qa-ks-")
        mock_neptune.create_db_cluster_snapshot.assert_not_called()

    def test_create_snapshot_execute(self, snapshot_manager, mock_neptune):
        mock_neptune.describe_db_cluster_snapshots.return_value = {
            "DBClusterSnapshots": [{"Status": "available"}]
        }
        sid = snapshot_manager.create_snapshot(dry_run=False)
        assert sid is not None
        mock_neptune.create_db_cluster_snapshot.assert_called_once()
        call_kwargs = mock_neptune.create_db_cluster_snapshot.call_args[1]
        assert call_kwargs["DBClusterIdentifier"] == "aura-neptune-qa"
        assert "KillSwitch" in str(call_kwargs["Tags"])

    def test_create_snapshot_cluster_not_found(self, snapshot_manager, mock_neptune):
        from botocore.exceptions import ClientError

        mock_neptune.create_db_cluster_snapshot.side_effect = ClientError(
            {"Error": {"Code": "DBClusterNotFoundFault", "Message": "Not found"}},
            "CreateDBClusterSnapshot",
        )
        sid = snapshot_manager.create_snapshot(dry_run=False)
        assert sid is None

    def test_cleanup_old_snapshots_dry_run(self, snapshot_manager, mock_neptune):
        mock_neptune.describe_db_cluster_snapshots.return_value = {
            "DBClusterSnapshots": [
                {"DBClusterSnapshotIdentifier": "aura-neptune-qa-ks-20260101-000000"},
                {"DBClusterSnapshotIdentifier": "aura-neptune-qa-ks-20260215-143000"},
            ]
        }
        snapshot_manager.cleanup_old_snapshots(
            "aura-neptune-qa-ks-20260215-143000", dry_run=True
        )
        mock_neptune.delete_db_cluster_snapshot.assert_not_called()

    def test_cleanup_old_snapshots_execute(self, snapshot_manager, mock_neptune):
        mock_neptune.describe_db_cluster_snapshots.return_value = {
            "DBClusterSnapshots": [
                {"DBClusterSnapshotIdentifier": "aura-neptune-qa-ks-20260101-000000"},
                {"DBClusterSnapshotIdentifier": "aura-neptune-qa-ks-20260215-143000"},
            ]
        }
        snapshot_manager.cleanup_old_snapshots(
            "aura-neptune-qa-ks-20260215-143000", dry_run=False
        )
        mock_neptune.delete_db_cluster_snapshot.assert_called_once_with(
            DBClusterSnapshotIdentifier="aura-neptune-qa-ks-20260101-000000"
        )


# ---------------------------------------------------------------------------
# EventBridge Schedule Tests
# ---------------------------------------------------------------------------


class TestScheduleManagement:
    def test_disable_schedules_dry_run(self, mock_scheduler):
        result = disable_schedules(mock_scheduler, dry_run=True)
        assert len(result) == len(EVENTBRIDGE_SCHEDULES)
        mock_scheduler.update_schedule.assert_not_called()

    def test_disable_schedules_execute(self, mock_scheduler):
        result = disable_schedules(mock_scheduler, dry_run=False)
        assert len(result) == len(EVENTBRIDGE_SCHEDULES)
        assert mock_scheduler.update_schedule.call_count == len(EVENTBRIDGE_SCHEDULES)
        for c in mock_scheduler.update_schedule.call_args_list:
            assert c[1]["State"] == "DISABLED"

    def test_disable_schedule_not_found(self, mock_scheduler):
        from botocore.exceptions import ClientError

        mock_scheduler.get_schedule.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "GetSchedule",
        )
        result = disable_schedules(mock_scheduler, dry_run=False)
        assert len(result) == 0

    def test_enable_schedules_execute(self, mock_scheduler):
        enable_schedules(mock_scheduler, dry_run=False)
        assert mock_scheduler.update_schedule.call_count == len(EVENTBRIDGE_SCHEDULES)
        for c in mock_scheduler.update_schedule.call_args_list:
            assert c[1]["State"] == "ENABLED"


# ---------------------------------------------------------------------------
# Pre-flight Check Tests
# ---------------------------------------------------------------------------


class TestPreflightChecks:
    def test_preflight_no_credentials(self):
        from botocore.exceptions import NoCredentialsError

        sts = MagicMock()
        sts.get_caller_identity.side_effect = NoCredentialsError()
        codebuild = MagicMock()

        from qa_killswitch import pre_flight_checks

        with pytest.raises(SystemExit) as exc_info:
            pre_flight_checks(sts, codebuild, "us-east-1")
        assert exc_info.value.code == 2

    def test_preflight_success(self):
        sts = MagicMock()
        sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/engineer",
        }
        codebuild = MagicMock()
        codebuild.list_builds_for_project.return_value = {"ids": []}

        from qa_killswitch import pre_flight_checks

        result = pre_flight_checks(sts, codebuild, "us-east-1")
        assert result["account_id"] == "123456789012"
        assert "engineer" in result["caller_arn"]

    def test_preflight_codebuild_in_progress(self):
        sts = MagicMock()
        sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/engineer",
        }
        codebuild = MagicMock()
        codebuild.list_builds_for_project.return_value = {"ids": ["build-1"]}
        codebuild.batch_get_builds.return_value = {
            "builds": [{"buildStatus": "IN_PROGRESS"}]
        }

        from qa_killswitch import pre_flight_checks

        with pytest.raises(SystemExit) as exc_info:
            pre_flight_checks(sts, codebuild, "us-east-1")
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Stack Definitions Tests
# ---------------------------------------------------------------------------


class TestStackDefinitions:
    def test_all_stacks_contain_qa(self):
        """All stack names must contain -qa for safety."""
        for stack_def in STACK_DEFINITIONS:
            assert (
                f"-{ENVIRONMENT}" in stack_def["name"]
            ), f"Stack {stack_def['name']} missing '-{ENVIRONMENT}' suffix"

    def test_all_stacks_have_template(self):
        for stack_def in STACK_DEFINITIONS:
            assert stack_def["template"].endswith(
                ".yaml"
            ), f"Stack {stack_def['name']} template not .yaml"

    def test_shutdown_phases_ordered(self):
        """Phases should progress from 2 (app) through 6 (networking)."""
        phases = [s["phase"] for s in STACK_DEFINITIONS]
        assert min(phases) == 2
        assert max(phases) == 6

    def test_environment_hardcoded(self):
        assert ENVIRONMENT == "qa"
        from qa_killswitch import ALLOWED_ENVIRONMENTS

        assert "qa" in ALLOWED_ENVIRONMENTS
        assert "prod" not in ALLOWED_ENVIRONMENTS
        assert "dev" not in ALLOWED_ENVIRONMENTS

    def test_allowed_environments_excludes_prod_and_dev(self):
        """ALLOWED_ENVIRONMENTS must never include prod or dev."""
        from qa_killswitch import ALLOWED_ENVIRONMENTS

        assert "prod" not in ALLOWED_ENVIRONMENTS
        assert "dev" not in ALLOWED_ENVIRONMENTS
        assert "production" not in ALLOWED_ENVIRONMENTS
        assert len(ALLOWED_ENVIRONMENTS) == 1

    def test_expected_stack_count(self):
        """Should manage 9 stacks total."""
        assert len(STACK_DEFINITIONS) == 9

    def test_eventbridge_schedule_names(self):
        assert len(EVENTBRIDGE_SCHEDULES) == 2
        for name in EVENTBRIDGE_SCHEDULES:
            assert "qa" in name


# ---------------------------------------------------------------------------
# Deploy Config Tests
# ---------------------------------------------------------------------------


class TestDeployConfigs:
    def test_build_deploy_configs_all_stacks(self):
        params = {
            "VPC_ID": "vpc-123",
            "PRIVATE_SUBNET_IDS": "subnet-1,subnet-2",
            "PUBLIC_SUBNET_IDS": "subnet-3,subnet-4",
            "VPC_CIDR": "10.0.0.0/16",
            "PRIVATE_SUBNET_1": "subnet-1",
            "PRIVATE_SUBNET_2": "subnet-2",
            "NEPTUNE_SG": "sg-neptune",
            "OPENSEARCH_SG": "sg-opensearch",
            "EKS_SG": "sg-eks",
            "EKS_NODE_SG": "sg-eksnode",
            "VPCE_SG": "sg-vpce",
            "EKS_CLUSTER_ROLE": "arn:aws:iam::123:role/eks-cluster",
            "EKS_NODE_ROLE": "arn:aws:iam::123:role/eks-node",
            "ADMIN_ROLE_ARN": "arn:aws:iam::123:role/admin",
            "PRIVATE_RT_1": "rtb-1",
            "PRIVATE_RT_2": "rtb-2",
            "PRIVATE_ROUTE_TABLE_IDS": "rtb-1,rtb-2",
        }
        configs = _build_deploy_configs(params)

        # Should have configs for all 9 stacks
        assert len(configs) == 9

        # Verify Neptune config
        neptune_cfg = configs[f"{PROJECT_NAME}-neptune-{ENVIRONMENT}"]
        assert (
            neptune_cfg["template"] == "deploy/cloudformation/neptune-simplified.yaml"
        )
        assert neptune_cfg["params"]["NeptuneSecurityGroupId"] == "sg-neptune"
        assert neptune_cfg["params"]["InstanceType"] == "db.t3.medium"

        # Verify OpenSearch config
        os_cfg = configs[f"{PROJECT_NAME}-opensearch-{ENVIRONMENT}"]
        assert os_cfg["params"]["InstanceType"] == "t3.small.search"

        # Verify EKS config
        eks_cfg = configs[f"{PROJECT_NAME}-eks-{ENVIRONMENT}"]
        assert eks_cfg["params"]["KubernetesVersion"] == "1.34"

        # Verify node groups use correct instance types
        general_cfg = configs[f"{PROJECT_NAME}-nodegroup-general-{ENVIRONMENT}"]
        assert "t3.large" in general_cfg["params"]["InstanceTypes"]
        assert general_cfg["params"]["CapacityType"] == "SPOT"

        memory_cfg = configs[f"{PROJECT_NAME}-nodegroup-memory-{ENVIRONMENT}"]
        assert "r6i.xlarge" in memory_cfg["params"]["InstanceTypes"]

        gpu_cfg = configs[f"{PROJECT_NAME}-nodegroup-gpu-{ENVIRONMENT}"]
        assert "g5.xlarge" in gpu_cfg["params"]["InstanceTypes"]
        assert gpu_cfg["params"]["DesiredSize"] == "0"  # scale-to-zero

        # Verify network services
        ns_cfg = configs[f"{PROJECT_NAME}-network-services-{ENVIRONMENT}"]
        assert ns_cfg["params"]["VpcId"] == "vpc-123"
        assert ns_cfg["params"]["PrivateSubnet1Id"] == "subnet-1"

    def test_deploy_configs_all_have_environment(self):
        params = {
            k: "test"
            for k in [
                "VPC_ID",
                "PRIVATE_SUBNET_IDS",
                "PUBLIC_SUBNET_IDS",
                "VPC_CIDR",
                "PRIVATE_SUBNET_1",
                "PRIVATE_SUBNET_2",
                "NEPTUNE_SG",
                "OPENSEARCH_SG",
                "EKS_SG",
                "EKS_NODE_SG",
                "VPCE_SG",
                "EKS_CLUSTER_ROLE",
                "EKS_NODE_ROLE",
                "ADMIN_ROLE_ARN",
                "PRIVATE_RT_1",
                "PRIVATE_RT_2",
                "PRIVATE_ROUTE_TABLE_IDS",
            ]
        }
        configs = _build_deploy_configs(params)
        for name, cfg in configs.items():
            assert (
                cfg["params"]["Environment"] == ENVIRONMENT
            ), f"Stack {name} missing Environment parameter"
            assert (
                cfg["params"]["ProjectName"] == PROJECT_NAME
            ), f"Stack {name} missing ProjectName parameter"


# ---------------------------------------------------------------------------
# Parameter Resolution Tests
# ---------------------------------------------------------------------------


class TestParameterResolution:
    def test_resolve_parameters(self):
        mock_cfn = MagicMock()

        # Setup outputs for each foundation stack
        def describe_stacks(StackName):
            if "networking" in StackName:
                return {
                    "Stacks": [
                        {
                            "Outputs": [
                                {"OutputKey": "VpcId", "OutputValue": "vpc-123"},
                                {
                                    "OutputKey": "PrivateSubnetIds",
                                    "OutputValue": "subnet-1,subnet-2",
                                },
                                {
                                    "OutputKey": "PublicSubnetIds",
                                    "OutputValue": "subnet-3,subnet-4",
                                },
                                {"OutputKey": "VpcCidr", "OutputValue": "10.0.0.0/16"},
                                {
                                    "OutputKey": "PrivateSubnet1Id",
                                    "OutputValue": "subnet-1",
                                },
                                {
                                    "OutputKey": "PrivateSubnet2Id",
                                    "OutputValue": "subnet-2",
                                },
                            ]
                        }
                    ]
                }
            elif "security" in StackName:
                return {
                    "Stacks": [
                        {
                            "Outputs": [
                                {
                                    "OutputKey": "NeptuneSecurityGroupId",
                                    "OutputValue": "sg-nep",
                                },
                                {
                                    "OutputKey": "OpenSearchSecurityGroupId",
                                    "OutputValue": "sg-os",
                                },
                                {
                                    "OutputKey": "EKSSecurityGroupId",
                                    "OutputValue": "sg-eks",
                                },
                                {
                                    "OutputKey": "EKSNodeSecurityGroupId",
                                    "OutputValue": "sg-node",
                                },
                                {
                                    "OutputKey": "VPCEndpointSecurityGroupId",
                                    "OutputValue": "sg-vpce",
                                },
                            ]
                        }
                    ]
                }
            elif "iam" in StackName:
                return {
                    "Stacks": [
                        {
                            "Outputs": [
                                {
                                    "OutputKey": "EKSClusterRoleArn",
                                    "OutputValue": "arn:role/cluster",
                                },
                                {
                                    "OutputKey": "EKSNodeRoleArn",
                                    "OutputValue": "arn:role/node",
                                },
                            ]
                        }
                    ]
                }
            return {"Stacks": [{"Outputs": []}]}

        mock_cfn.describe_stacks.side_effect = describe_stacks

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "arn:role/admin"}}

        sm = StackManager(mock_cfn, "us-east-1")

        with patch("qa_killswitch.boto3.client") as mock_ec2_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_route_tables.return_value = {
                "RouteTables": [{"RouteTableId": "rtb-123"}]
            }
            mock_ec2_client.return_value = mock_ec2

            params = resolve_parameters(sm, mock_ssm)

        assert params["VPC_ID"] == "vpc-123"
        assert params["NEPTUNE_SG"] == "sg-nep"
        assert params["EKS_CLUSTER_ROLE"] == "arn:role/cluster"
        assert params["ADMIN_ROLE_ARN"] == "arn:role/admin"


# ---------------------------------------------------------------------------
# Integration-Style Tests (mocked at boto3 level)
# ---------------------------------------------------------------------------


class TestShutdownFlow:
    """Test the overall shutdown flow logic."""

    def test_shutdown_phases_respect_dependencies(self):
        """Node groups (phase 3) must be deleted before EKS (phase 4)."""
        phases = {}
        for s in STACK_DEFINITIONS:
            phases.setdefault(s["phase"], []).append(s["name"])

        # Phase 3 = node groups, Phase 4 = EKS
        assert 3 in phases
        assert 4 in phases
        for ng in phases[3]:
            assert "nodegroup" in ng
        for eks in phases[4]:
            assert "eks" in eks

        # Phase 5 = data stores
        assert 5 in phases
        for ds in phases[5]:
            assert any(svc in ds for svc in ["neptune", "opensearch", "elasticache"])

    def test_shutdown_vpc_endpoints_last(self):
        """VPC endpoints should be the last thing deleted (highest phase)."""
        vpce_stacks = [s for s in STACK_DEFINITIONS if "vpc-endpoints" in s["name"]]
        assert len(vpce_stacks) == 1
        max_phase = max(s["phase"] for s in STACK_DEFINITIONS)
        assert vpce_stacks[0]["phase"] == max_phase


class TestRestoreFlow:
    """Test the overall restore flow logic."""

    def test_restore_vpc_endpoints_first(self):
        """VPC endpoints should deploy before data stores."""
        # In restore, the order is reversed: vpce first, then data, then compute
        # This is enforced by the restore_order list in do_restore()
        # We verify the stack definitions support this
        vpce = [s for s in STACK_DEFINITIONS if "vpc-endpoints" in s["name"]]
        data = [s for s in STACK_DEFINITIONS if s["layer"] == "data"]
        assert len(vpce) == 1
        assert len(data) == 3  # neptune, opensearch, elasticache


class TestIdempotency:
    """Test that operations are safe to run multiple times."""

    def test_delete_already_deleted_is_noop(self, stack_manager, mock_cfn):
        from botocore.exceptions import ClientError

        mock_cfn.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "does not exist"}},
            "DescribeStacks",
        )
        result = stack_manager.delete_stack("aura-neptune-qa", dry_run=False)
        assert result is True
        mock_cfn.delete_stack.assert_not_called()

    def test_snapshot_when_cluster_gone(self, snapshot_manager, mock_neptune):
        from botocore.exceptions import ClientError

        mock_neptune.create_db_cluster_snapshot.side_effect = ClientError(
            {"Error": {"Code": "DBClusterNotFoundFault", "Message": "Not found"}},
            "CreateDBClusterSnapshot",
        )
        result = snapshot_manager.create_snapshot(dry_run=False)
        assert result is None  # Graceful handling


# ---------------------------------------------------------------------------
# CLI Argument Tests
# ---------------------------------------------------------------------------


class TestCLIArguments:
    def test_main_requires_subcommand(self):
        from qa_killswitch import main

        with patch("sys.argv", ["qa_killswitch.py"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2  # argparse error

    def test_shutdown_defaults_to_dry_run(self):
        """Shutdown without --execute should be dry-run."""
        from qa_killswitch import main

        with patch("sys.argv", ["qa_killswitch.py", "shutdown"]):
            with patch("qa_killswitch.do_shutdown") as mock_shutdown:
                mock_shutdown.return_value = 0
                main()
                args = mock_shutdown.call_args[0][0]
                assert args.execute is False

    def test_shutdown_with_execute(self):
        from qa_killswitch import main

        with patch("sys.argv", ["qa_killswitch.py", "shutdown", "--execute"]):
            with patch("qa_killswitch.do_shutdown") as mock_shutdown:
                mock_shutdown.return_value = 0
                main()
                args = mock_shutdown.call_args[0][0]
                assert args.execute is True

    def test_restore_defaults_to_dry_run(self):
        from qa_killswitch import main

        with patch("sys.argv", ["qa_killswitch.py", "restore"]):
            with patch("qa_killswitch.do_restore") as mock_restore:
                mock_restore.return_value = 0
                main()
                args = mock_restore.call_args[0][0]
                assert args.execute is False

    def test_cleanup_subcommand_parsed(self):
        """Cleanup command should be parseable by main()."""
        from qa_killswitch import main

        with patch("sys.argv", ["qa_killswitch.py", "cleanup"]):
            with patch("qa_killswitch.do_cleanup") as mock_cleanup:
                mock_cleanup.return_value = 0
                main()
                mock_cleanup.assert_called_once()

    def test_cleanup_schedule_kms_flag(self):
        """--schedule-kms-deletion flag should be parsed correctly."""
        from qa_killswitch import main

        with patch(
            "sys.argv",
            ["qa_killswitch.py", "cleanup", "--schedule-kms-deletion"],
        ):
            with patch("qa_killswitch.do_cleanup") as mock_cleanup:
                mock_cleanup.return_value = 0
                main()
                args = mock_cleanup.call_args[0][0]
                assert args.schedule_kms_deletion is True


# ---------------------------------------------------------------------------
# Cleanup Operations Tests
# ---------------------------------------------------------------------------


class TestCleanupOperations:
    """Tests for post-shutdown cost cleanup functions."""

    # -- cleanup_orphaned_elbs -----------------------------------------------

    def test_cleanup_orphaned_elbs_dry_run(self):
        """Dry-run should not call delete on any ELBs."""
        elbv2 = MagicMock()
        elb = MagicMock()

        # ELBv2 paginator returns one k8s-tagged ALB
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "LoadBalancers": [
                    {
                        "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:123:lb/app/k8s-alb/abc",
                        "LoadBalancerName": "k8s-alb",
                    }
                ]
            }
        ]
        elbv2.get_paginator.return_value = paginator
        elbv2.describe_tags.return_value = {
            "TagDescriptions": [
                {
                    "Tags": [
                        {
                            "Key": "kubernetes.io/cluster/aura-cluster-qa",
                            "Value": "owned",
                        }
                    ]
                }
            ]
        }

        # No classic ELBs
        elb.describe_load_balancers.return_value = {"LoadBalancerDescriptions": []}

        count = cleanup_orphaned_elbs(elbv2, elb, dry_run=True)
        assert count == 1
        elbv2.delete_load_balancer.assert_not_called()

    def test_cleanup_orphaned_elbs_execute(self):
        """Execute mode should delete k8s-tagged ELBv2 load balancers."""
        elbv2 = MagicMock()
        elb = MagicMock()

        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "LoadBalancers": [
                    {
                        "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:123:lb/app/k8s-alb/abc",
                        "LoadBalancerName": "k8s-alb",
                    }
                ]
            }
        ]
        elbv2.get_paginator.return_value = paginator
        elbv2.describe_tags.return_value = {
            "TagDescriptions": [
                {"Tags": [{"Key": "elbv2.k8s.aws/cluster", "Value": "aura-cluster-qa"}]}
            ]
        }
        elbv2.describe_listeners.return_value = {"Listeners": []}
        elb.describe_load_balancers.return_value = {"LoadBalancerDescriptions": []}

        count = cleanup_orphaned_elbs(elbv2, elb, dry_run=False)
        assert count == 1
        elbv2.delete_load_balancer.assert_called_once_with(
            LoadBalancerArn="arn:aws:elasticloadbalancing:us-east-1:123:lb/app/k8s-alb/abc"
        )

    def test_cleanup_orphaned_elbs_no_elbs(self):
        """No ELBs should return count 0 gracefully."""
        elbv2 = MagicMock()
        elb = MagicMock()

        paginator = MagicMock()
        paginator.paginate.return_value = [{"LoadBalancers": []}]
        elbv2.get_paginator.return_value = paginator
        elb.describe_load_balancers.return_value = {"LoadBalancerDescriptions": []}

        count = cleanup_orphaned_elbs(elbv2, elb, dry_run=True)
        assert count == 0

    # -- cleanup_config_recorder ---------------------------------------------

    def test_cleanup_config_recorder_dry_run(self):
        """Dry-run should not call stop, delete_delivery_channel, or delete_config_rule."""
        config = MagicMock()
        config.describe_configuration_recorders.return_value = {
            "ConfigurationRecorders": [{"name": "default"}]
        }
        config.describe_delivery_channels.return_value = {
            "DeliveryChannels": [{"name": "default-channel"}]
        }
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"ConfigRules": [{"ConfigRuleName": "rule-1"}]}
        ]
        config.get_paginator.return_value = paginator

        cleanup_config_recorder(config, dry_run=True)

        config.stop_configuration_recorder.assert_not_called()
        config.delete_delivery_channel.assert_not_called()
        config.delete_config_rule.assert_not_called()

    def test_cleanup_config_recorder_execute(self):
        """Execute mode should stop recorder, delete channel, and delete rules."""
        config = MagicMock()
        config.describe_configuration_recorders.return_value = {
            "ConfigurationRecorders": [{"name": "default"}]
        }
        config.describe_delivery_channels.return_value = {
            "DeliveryChannels": [{"name": "default-channel"}]
        }
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "ConfigRules": [
                    {"ConfigRuleName": "rule-1"},
                    {"ConfigRuleName": "rule-2"},
                ]
            }
        ]
        config.get_paginator.return_value = paginator

        cleanup_config_recorder(config, dry_run=False)

        config.stop_configuration_recorder.assert_called_once_with(
            ConfigurationRecorderName="default"
        )
        config.delete_delivery_channel.assert_called_once_with(
            DeliveryChannelName="default-channel"
        )
        assert config.delete_config_rule.call_count == 2
        config.delete_config_rule.assert_any_call(ConfigRuleName="rule-1")
        config.delete_config_rule.assert_any_call(ConfigRuleName="rule-2")

    def test_cleanup_config_recorder_no_recorder(self):
        """No recorder should return gracefully without errors."""
        config = MagicMock()
        config.describe_configuration_recorders.return_value = {
            "ConfigurationRecorders": []
        }

        cleanup_config_recorder(config, dry_run=False)

        config.stop_configuration_recorder.assert_not_called()
        config.delete_delivery_channel.assert_not_called()

    # -- cleanup_cloudwatch_logs ---------------------------------------------

    def test_cleanup_cloudwatch_logs_dry_run(self):
        """Dry-run should not call put_retention_policy."""
        logs = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "logGroups": [
                    {
                        "logGroupName": "/aura/api-service-qa",
                        "retentionInDays": 90,
                    }
                ]
            }
        ]
        logs.get_paginator.return_value = paginator

        count = cleanup_cloudwatch_logs(logs, dry_run=True)
        assert count >= 1
        logs.put_retention_policy.assert_not_called()

    def test_cleanup_cloudwatch_logs_execute(self):
        """Execute mode should call put_retention_policy for each log group."""
        logs = MagicMock()
        paginator = MagicMock()
        # First prefix /aura/ returns one group, second prefix /aws/ returns one group

        def paginate_side_effect(**kwargs):
            prefix = kwargs.get("logGroupNamePrefix", "")
            if prefix == "/aura/":
                return [
                    {
                        "logGroups": [
                            {
                                "logGroupName": "/aura/api-service-qa",
                                "retentionInDays": 90,
                            }
                        ]
                    }
                ]
            else:
                return [
                    {
                        "logGroups": [
                            {
                                "logGroupName": "/aws/codebuild/aura-deploy",
                                "retentionInDays": 30,
                            }
                        ]
                    }
                ]

        paginator.paginate.side_effect = paginate_side_effect
        logs.get_paginator.return_value = paginator

        count = cleanup_cloudwatch_logs(logs, dry_run=False)
        assert count == 2
        assert logs.put_retention_policy.call_count == 2

    def test_cleanup_cloudwatch_logs_already_1_day(self):
        """Log groups already at 1-day retention should be skipped."""
        logs = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "logGroups": [
                    {
                        "logGroupName": "/aura/already-short",
                        "retentionInDays": 1,
                    }
                ]
            }
        ]
        logs.get_paginator.return_value = paginator

        count = cleanup_cloudwatch_logs(logs, dry_run=False)
        assert count == 0
        logs.put_retention_policy.assert_not_called()

    # -- schedule_kms_key_deletion -------------------------------------------

    def test_schedule_kms_key_deletion_dry_run(self):
        """Dry-run should not call schedule_key_deletion."""
        kms = MagicMock()
        cfn = MagicMock()
        cfn.describe_stacks.return_value = {
            "Stacks": [
                {
                    "Outputs": [
                        {"OutputKey": "NeptuneKmsKeyId", "OutputValue": "key-1111"},
                        {"OutputKey": "OpenSearchKmsKeyId", "OutputValue": "key-2222"},
                    ]
                }
            ]
        }
        kms.describe_key.return_value = {"KeyMetadata": {"KeyState": "Enabled"}}

        count = schedule_kms_key_deletion(kms, cfn, dry_run=True)
        assert count == 2
        kms.schedule_key_deletion.assert_not_called()

    def test_schedule_kms_key_deletion_execute(self):
        """Execute mode should call schedule_key_deletion with 7-day window."""
        kms = MagicMock()
        cfn = MagicMock()
        cfn.describe_stacks.return_value = {
            "Stacks": [
                {
                    "Outputs": [
                        {"OutputKey": "NeptuneKmsKeyId", "OutputValue": "key-1111"},
                    ]
                }
            ]
        }
        kms.describe_key.return_value = {"KeyMetadata": {"KeyState": "Enabled"}}

        count = schedule_kms_key_deletion(kms, cfn, dry_run=False)
        assert count == 1
        kms.schedule_key_deletion.assert_called_once_with(
            KeyId="key-1111", PendingWindowInDays=7
        )

    def test_schedule_kms_key_deletion_no_stack(self):
        """Missing KMS stack should return 0 gracefully."""
        from botocore.exceptions import ClientError

        kms = MagicMock()
        cfn = MagicMock()
        cfn.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Stack not found"}},
            "DescribeStacks",
        )

        count = schedule_kms_key_deletion(kms, cfn, dry_run=False)
        assert count == 0
        kms.schedule_key_deletion.assert_not_called()
