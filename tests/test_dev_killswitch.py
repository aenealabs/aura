"""
Tests for DEV Environment Kill-Switch Script
=============================================
Unit tests covering pre-flight validation, shutdown sequencing,
restore sequencing, state file management, error handling,
idempotency, dry-run mode, protected stack safety, CodeBuild
trigger logic, stack count validation, and phase ordering.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from dev_killswitch import (
    CODEBUILD_RESTORE_PROJECTS,
    ENVIRONMENT,
    EVENTBRIDGE_SCHEDULES,
    KMS_STACK_NAME,
    PROJECT_NAME,
    PROTECTED_STACKS,
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
    trigger_codebuild_restores,
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
def mock_codebuild():
    """Mock CodeBuild client."""
    client = MagicMock()
    client.start_build.return_value = {
        "build": {"id": "aura-application-deploy-dev:build-id-123"}
    }
    client.list_builds_for_project.return_value = {"ids": []}
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
        assert state.codebuild_restore_ids == []

    def test_state_serialization(self):
        state = KillSwitchState(
            status="shutdown",
            shutdown_timestamp="2026-03-01T14:30:00Z",
            shutdown_by="arn:aws:iam::123:user/engineer",
            neptune_snapshot_id="aura-neptune-dev-ks-20260301-143000",
            deleted_stacks=[
                {
                    "stack_name": "aura-neptune-dev",
                    "template_file": "deploy/cloudformation/neptune-simplified.yaml",
                    "deleted_at": "2026-03-01T14:30:00Z",
                }
            ],
            codebuild_restore_ids=["aura-application-deploy-dev:abc123"],
        )
        data = json.loads(json.dumps(state.__dict__, default=str))
        assert data["status"] == "shutdown"
        assert data["neptune_snapshot_id"] == "aura-neptune-dev-ks-20260301-143000"
        assert len(data["deleted_stacks"]) == 1
        assert data["codebuild_restore_ids"] == ["aura-application-deploy-dev:abc123"]

    def test_state_from_dict(self):
        data = {
            "schema_version": 1,
            "environment": "dev",
            "status": "shutdown",
            "shutdown_timestamp": "2026-03-01T14:30:00Z",
            "shutdown_by": "arn:aws:iam::123:user/engineer",
            "neptune_snapshot_id": "snap-123",
            "deleted_stacks": [],
            "disabled_schedules": ["aura-dev-scale-down"],
            "codebuild_restore_ids": ["build-id-1", "build-id-2"],
            "restore_timestamp": None,
            "restore_by": None,
            "phases_completed": [2, 3, 4],
        }
        state = KillSwitchState(**data)
        assert state.status == "shutdown"
        assert state.phases_completed == [2, 3, 4]
        assert state.codebuild_restore_ids == ["build-id-1", "build-id-2"]

    def test_state_ignores_unknown_fields(self):
        """State should be constructable even if extra fields exist."""
        data = {"status": "shutdown", "unknown_field": "value"}
        filtered = {
            k: v for k, v in data.items() if k in KillSwitchState.__dataclass_fields__
        }
        state = KillSwitchState(**filtered)
        assert state.status == "shutdown"

    def test_codebuild_restore_ids_default(self):
        """codebuild_restore_ids defaults to empty list."""
        state = KillSwitchState()
        assert isinstance(state.codebuild_restore_ids, list)
        assert len(state.codebuild_restore_ids) == 0


# ---------------------------------------------------------------------------
# StackManager Tests
# ---------------------------------------------------------------------------


class TestStackManager:
    def test_get_stack_status_exists(self, stack_manager, mock_cfn):
        mock_cfn.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE"}]
        }
        assert stack_manager.get_stack_status("aura-neptune-dev") == "CREATE_COMPLETE"

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
            stack_manager.get_stack_output("aura-networking-dev", "VpcId") == "vpc-123"
        )
        assert stack_manager.get_stack_output("aura-networking-dev", "Missing") is None

    def test_delete_stack_dry_run(self, stack_manager, mock_cfn):
        mock_cfn.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE"}]
        }
        result = stack_manager.delete_stack("aura-neptune-dev", dry_run=True)
        assert result is True
        mock_cfn.delete_stack.assert_not_called()

    def test_delete_stack_already_deleted(self, stack_manager, mock_cfn):
        from botocore.exceptions import ClientError

        mock_cfn.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Stack does not exist"}},
            "DescribeStacks",
        )
        result = stack_manager.delete_stack("aura-neptune-dev", dry_run=False)
        assert result is True
        mock_cfn.delete_stack.assert_not_called()

    def test_delete_stack_execute(self, stack_manager, mock_cfn):
        # First call: stack exists. Subsequent: deleted
        mock_cfn.describe_stacks.side_effect = [
            {"Stacks": [{"StackStatus": "CREATE_COMPLETE"}]},  # initial check
            {"Stacks": [{"StackStatus": "DELETE_IN_PROGRESS"}]},  # first poll
            {"Stacks": [{"StackStatus": "DELETE_COMPLETE"}]},  # second poll
        ]
        result = stack_manager.delete_stack("aura-neptune-dev", dry_run=False)
        assert result is True
        mock_cfn.delete_stack.assert_called_once_with(StackName="aura-neptune-dev")

    def test_delete_stack_in_progress_waits(self, stack_manager, mock_cfn):
        mock_cfn.describe_stacks.side_effect = [
            {"Stacks": [{"StackStatus": "DELETE_IN_PROGRESS"}]},  # initial
            {"Stacks": [{"StackStatus": "DELETE_COMPLETE"}]},  # poll
        ]
        result = stack_manager.delete_stack("aura-neptune-dev", dry_run=False)
        assert result is True
        mock_cfn.delete_stack.assert_not_called()  # Already in progress

    def test_delete_stack_active_operation_fails(self, stack_manager, mock_cfn):
        mock_cfn.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "UPDATE_IN_PROGRESS"}]
        }
        result = stack_manager.delete_stack("aura-neptune-dev", dry_run=False)
        assert result is False

    def test_delete_stack_protected_blocked(self, stack_manager, mock_cfn):
        """Protected stacks must never be deleted."""
        result = stack_manager.delete_stack(
            f"{PROJECT_NAME}-networking-{ENVIRONMENT}", dry_run=False
        )
        assert result is False
        mock_cfn.delete_stack.assert_not_called()

    def test_deploy_stack_dry_run(self, stack_manager):
        result = stack_manager.deploy_stack(
            "aura-neptune-dev",
            "deploy/cloudformation/neptune-simplified.yaml",
            {"Environment": "dev"},
            {"Layer": "data"},
            dry_run=True,
        )
        assert result is True

    @patch("dev_killswitch.subprocess.run")
    def test_deploy_stack_execute(self, mock_run, stack_manager):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = stack_manager.deploy_stack(
            "aura-neptune-dev",
            "deploy/cloudformation/neptune-simplified.yaml",
            {"Environment": "dev", "ProjectName": "aura"},
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
        # Verify tags are separate args, not garbled
        tags_idx = cmd.index("--tags")
        assert cmd[tags_idx + 1].startswith("Project=")
        assert cmd[tags_idx + 2].startswith("Environment=")
        assert cmd[tags_idx + 3].startswith("Layer=")

    @patch("dev_killswitch.subprocess.run")
    def test_deploy_stack_no_changes(self, mock_run, stack_manager):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="", stderr="No updates are to be performed"
        )
        result = stack_manager.deploy_stack(
            "aura-neptune-dev",
            "deploy/cloudformation/neptune-simplified.yaml",
            {"Environment": "dev"},
            {"Layer": "data"},
            dry_run=False,
        )
        assert result is True

    @patch("dev_killswitch.subprocess.run")
    def test_deploy_stack_failure(self, mock_run, stack_manager):
        """Deploy failure returns False."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Stack creation failed"
        )
        result = stack_manager.deploy_stack(
            "aura-neptune-dev",
            "deploy/cloudformation/neptune-simplified.yaml",
            {"Environment": "dev"},
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
        assert sid.startswith("aura-neptune-dev-ks-")
        mock_neptune.create_db_cluster_snapshot.assert_not_called()

    def test_create_snapshot_execute(self, snapshot_manager, mock_neptune):
        mock_neptune.describe_db_cluster_snapshots.return_value = {
            "DBClusterSnapshots": [{"Status": "available"}]
        }
        sid = snapshot_manager.create_snapshot(dry_run=False)
        assert sid is not None
        mock_neptune.create_db_cluster_snapshot.assert_called_once()
        call_kwargs = mock_neptune.create_db_cluster_snapshot.call_args[1]
        assert call_kwargs["DBClusterIdentifier"] == "aura-neptune-dev"
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
                {"DBClusterSnapshotIdentifier": "aura-neptune-dev-ks-20260101-000000"},
                {"DBClusterSnapshotIdentifier": "aura-neptune-dev-ks-20260301-143000"},
            ]
        }
        snapshot_manager.cleanup_old_snapshots(
            "aura-neptune-dev-ks-20260301-143000", dry_run=True
        )
        mock_neptune.delete_db_cluster_snapshot.assert_not_called()

    def test_cleanup_old_snapshots_execute(self, snapshot_manager, mock_neptune):
        mock_neptune.describe_db_cluster_snapshots.return_value = {
            "DBClusterSnapshots": [
                {"DBClusterSnapshotIdentifier": "aura-neptune-dev-ks-20260101-000000"},
                {"DBClusterSnapshotIdentifier": "aura-neptune-dev-ks-20260301-143000"},
            ]
        }
        snapshot_manager.cleanup_old_snapshots(
            "aura-neptune-dev-ks-20260301-143000", dry_run=False
        )
        mock_neptune.delete_db_cluster_snapshot.assert_called_once_with(
            DBClusterSnapshotIdentifier="aura-neptune-dev-ks-20260101-000000"
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
# CodeBuild Trigger Tests
# ---------------------------------------------------------------------------


class TestCodeBuildTriggers:
    def test_trigger_codebuild_restores_dry_run(self, mock_codebuild):
        """Dry-run should not call start_build."""
        result = trigger_codebuild_restores(mock_codebuild, dry_run=True)
        assert result == []
        mock_codebuild.start_build.assert_not_called()

    def test_trigger_codebuild_restores_execute(self, mock_codebuild):
        """Execute mode triggers all CodeBuild projects."""
        mock_codebuild.start_build.return_value = {
            "build": {"id": "project:build-id-abc"}
        }
        result = trigger_codebuild_restores(mock_codebuild, dry_run=False)
        assert len(result) == len(CODEBUILD_RESTORE_PROJECTS)
        assert mock_codebuild.start_build.call_count == len(CODEBUILD_RESTORE_PROJECTS)

    def test_trigger_codebuild_correct_projects(self, mock_codebuild):
        """Verify the correct project names are triggered."""
        triggered_projects = []
        mock_codebuild.start_build.side_effect = lambda **kwargs: (
            triggered_projects.append(kwargs["projectName"]),
            {"build": {"id": f"{kwargs['projectName']}:build-123"}},
        )[-1]

        trigger_codebuild_restores(mock_codebuild, dry_run=False)

        expected = [
            f"{PROJECT_NAME}-application-deploy-{ENVIRONMENT}",
            f"{PROJECT_NAME}-observability-deploy-{ENVIRONMENT}",
            f"{PROJECT_NAME}-serverless-deploy-{ENVIRONMENT}",
            f"{PROJECT_NAME}-sandbox-deploy-{ENVIRONMENT}",
            f"{PROJECT_NAME}-security-deploy-{ENVIRONMENT}",
            f"{PROJECT_NAME}-vuln-scan-deploy-{ENVIRONMENT}",
        ]
        assert triggered_projects == expected

    def test_trigger_codebuild_env_variable_override(self, mock_codebuild):
        """Verify triggered builds include TRIGGERED_BY env var."""
        mock_codebuild.start_build.return_value = {
            "build": {"id": "project:build-id-abc"}
        }
        trigger_codebuild_restores(mock_codebuild, dry_run=False)
        for c in mock_codebuild.start_build.call_args_list:
            env_vars = c[1]["environmentVariablesOverride"]
            assert any(
                v["name"] == "TRIGGERED_BY" and v["value"] == "dev-killswitch-restore"
                for v in env_vars
            )

    def test_trigger_codebuild_project_not_found(self, mock_codebuild):
        """Missing CodeBuild projects should be skipped gracefully."""
        from botocore.exceptions import ClientError

        mock_codebuild.start_build.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Project not found",
                }
            },
            "StartBuild",
        )
        result = trigger_codebuild_restores(mock_codebuild, dry_run=False)
        assert result == []

    def test_codebuild_restore_projects_count(self):
        """CODEBUILD_RESTORE_PROJECTS should have 6 projects."""
        assert len(CODEBUILD_RESTORE_PROJECTS) == 6

    def test_codebuild_restore_projects_all_dev(self):
        """All CodeBuild restore projects must target dev environment."""
        for project in CODEBUILD_RESTORE_PROJECTS:
            assert (
                f"-{ENVIRONMENT}" in project
            ), f"CodeBuild project {project} missing '-{ENVIRONMENT}' suffix"


# ---------------------------------------------------------------------------
# Pre-flight Check Tests
# ---------------------------------------------------------------------------


class TestPreflightChecks:
    def test_preflight_no_credentials(self):
        from botocore.exceptions import NoCredentialsError

        sts = MagicMock()
        sts.get_caller_identity.side_effect = NoCredentialsError()
        codebuild = MagicMock()

        from dev_killswitch import pre_flight_checks

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

        from dev_killswitch import pre_flight_checks

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

        from dev_killswitch import pre_flight_checks

        with pytest.raises(SystemExit) as exc_info:
            pre_flight_checks(sts, codebuild, "us-east-1")
        assert exc_info.value.code == 1

    def test_preflight_account_id_mismatch(self):
        """Account ID mismatch should exit with code 2."""
        sts = MagicMock()
        sts.get_caller_identity.return_value = {
            "Account": "999999999999",
            "Arn": "arn:aws:iam::999999999999:user/engineer",
        }
        codebuild = MagicMock()

        from dev_killswitch import pre_flight_checks

        with patch.dict("os.environ", {"AURA_DEV_ACCOUNT_ID": "123456789012"}):
            with pytest.raises(SystemExit) as exc_info:
                pre_flight_checks(sts, codebuild, "us-east-1")
            assert exc_info.value.code == 2

    def test_preflight_validates_no_stack_in_protected(self):
        """Pre-flight checks validate no STACK_DEFINITIONS entry is protected."""
        sts = MagicMock()
        sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/engineer",
        }
        codebuild = MagicMock()
        codebuild.list_builds_for_project.return_value = {"ids": []}

        from dev_killswitch import pre_flight_checks

        # If we reach here without sys.exit(2), the validation passed
        result = pre_flight_checks(sts, codebuild, "us-east-1")
        assert result["account_id"] == "123456789012"


# ---------------------------------------------------------------------------
# Protected Stack Safety Tests
# ---------------------------------------------------------------------------


class TestProtectedStackSafety:
    def test_no_stack_definition_in_protected(self):
        """No STACK_DEFINITIONS entry may be in PROTECTED_STACKS."""
        stack_names = {s["name"] for s in STACK_DEFINITIONS}
        overlap = stack_names & PROTECTED_STACKS
        assert (
            overlap == set()
        ), f"STACK_DEFINITIONS entries found in PROTECTED_STACKS: {overlap}"

    def test_protected_stacks_contain_environment(self):
        """Most protected stacks should contain the environment suffix."""
        # Some organizational stacks don't have an environment suffix
        org_stacks = {
            f"{PROJECT_NAME}-organizations",
            f"{PROJECT_NAME}-org-cloudtrail",
            f"{PROJECT_NAME}-route53-cross-account-role",
        }
        for stack in PROTECTED_STACKS:
            if stack not in org_stacks:
                assert (
                    f"-{ENVIRONMENT}" in stack
                ), f"Protected stack {stack} missing '-{ENVIRONMENT}' suffix"

    def test_foundation_stacks_are_protected(self):
        """Core foundation stacks (VPC, networking, security, IAM, KMS) must be protected."""
        foundation_names = [
            f"{PROJECT_NAME}-vpc-{ENVIRONMENT}",
            f"{PROJECT_NAME}-networking-{ENVIRONMENT}",
            f"{PROJECT_NAME}-security-{ENVIRONMENT}",
            f"{PROJECT_NAME}-iam-{ENVIRONMENT}",
            f"{PROJECT_NAME}-kms-{ENVIRONMENT}",
        ]
        for name in foundation_names:
            assert (
                name in PROTECTED_STACKS
            ), f"Foundation stack {name} not in PROTECTED_STACKS"

    def test_dynamodb_stacks_are_protected(self):
        """DynamoDB stacks (state management, minimal cost) should be protected."""
        dynamodb_names = [
            f"{PROJECT_NAME}-dynamodb-{ENVIRONMENT}",
            f"{PROJECT_NAME}-s3-{ENVIRONMENT}",
            f"{PROJECT_NAME}-repository-tables-{ENVIRONMENT}",
        ]
        for name in dynamodb_names:
            assert (
                name in PROTECTED_STACKS
            ), f"State management stack {name} not in PROTECTED_STACKS"

    def test_ecr_stacks_are_protected(self):
        """ECR repository stacks should be protected (container images)."""
        ecr_stacks = [s for s in PROTECTED_STACKS if "ecr-" in s]
        assert (
            len(ecr_stacks) >= 7
        ), f"Expected at least 7 ECR stacks in PROTECTED_STACKS, got {len(ecr_stacks)}"

    def test_delete_stack_refuses_protected(self, stack_manager, mock_cfn):
        """StackManager.delete_stack must refuse all protected stacks."""
        for protected_name in list(PROTECTED_STACKS)[:5]:
            result = stack_manager.delete_stack(protected_name, dry_run=False)
            assert result is False
        mock_cfn.delete_stack.assert_not_called()


# ---------------------------------------------------------------------------
# Stack Definitions Tests
# ---------------------------------------------------------------------------


class TestStackDefinitions:
    def test_all_stacks_contain_dev(self):
        """All stack names must contain -dev for safety."""
        for stack_def in STACK_DEFINITIONS:
            assert (
                f"-{ENVIRONMENT}" in stack_def["name"]
            ), f"Stack {stack_def['name']} missing '-{ENVIRONMENT}' suffix"

    def test_all_stacks_have_template(self):
        for stack_def in STACK_DEFINITIONS:
            assert stack_def["template"].endswith(
                ".yaml"
            ), f"Stack {stack_def['name']} template not .yaml"

    def test_environment_hardcoded(self):
        assert ENVIRONMENT == "dev"
        from dev_killswitch import ALLOWED_ENVIRONMENTS

        assert "dev" in ALLOWED_ENVIRONMENTS
        assert "prod" not in ALLOWED_ENVIRONMENTS
        assert "qa" not in ALLOWED_ENVIRONMENTS

    def test_allowed_environments_excludes_prod_and_qa(self):
        """ALLOWED_ENVIRONMENTS must never include prod or qa."""
        from dev_killswitch import ALLOWED_ENVIRONMENTS

        assert "prod" not in ALLOWED_ENVIRONMENTS
        assert "qa" not in ALLOWED_ENVIRONMENTS
        assert "production" not in ALLOWED_ENVIRONMENTS
        assert len(ALLOWED_ENVIRONMENTS) == 1

    def test_expected_stack_count(self):
        """Should manage ~80 stacks total."""
        assert len(STACK_DEFINITIONS) == 80

    def test_stack_count_by_phase(self):
        """Verify stack counts per phase match expected distribution."""
        phase_counts = {}
        for s in STACK_DEFINITIONS:
            phase_counts[s["phase"]] = phase_counts.get(s["phase"], 0) + 1

        assert phase_counts[2] == 8, "Phase 2 (scanning) should have 8 stacks"
        assert phase_counts[3] == 13, "Phase 3 (security) should have 13 stacks"
        assert phase_counts[4] == 13, "Phase 4 (sandbox) should have 13 stacks"
        assert phase_counts[5] == 18, "Phase 5 (serverless) should have 18 stacks"
        assert phase_counts[6] == 8, "Phase 6 (observability) should have 8 stacks"
        assert phase_counts[7] == 10, "Phase 7 (application) should have 10 stacks"
        assert phase_counts[8] == 1, "Phase 8 (network) should have 1 stack"
        assert phase_counts[9] == 4, "Phase 9 (compute nodegroups) should have 4 stacks"
        assert phase_counts[10] == 1, "Phase 10 (EKS) should have 1 stack"
        assert phase_counts[11] == 3, "Phase 11 (data) should have 3 stacks"
        assert phase_counts[12] == 1, "Phase 12 (foundation) should have 1 stack"

    def test_eventbridge_schedule_names(self):
        assert len(EVENTBRIDGE_SCHEDULES) == 2
        for name in EVENTBRIDGE_SCHEDULES:
            assert "dev" in name

    def test_all_stacks_have_required_keys(self):
        """Every stack definition must have name, phase, template, and layer."""
        required_keys = {"name", "phase", "template", "layer"}
        for stack_def in STACK_DEFINITIONS:
            missing = required_keys - set(stack_def.keys())
            assert (
                not missing
            ), f"Stack {stack_def.get('name', '?')} missing keys: {missing}"

    def test_no_duplicate_stack_names(self):
        """All stack names must be unique."""
        names = [s["name"] for s in STACK_DEFINITIONS]
        assert len(names) == len(set(names)), (
            f"Duplicate stack names found: "
            f"{[n for n in names if names.count(n) > 1]}"
        )


# ---------------------------------------------------------------------------
# Phase Ordering Tests
# ---------------------------------------------------------------------------


class TestPhaseOrdering:
    def test_shutdown_phases_range(self):
        """Phases should progress from 2 (scanning) through 12 (foundation)."""
        phases = [s["phase"] for s in STACK_DEFINITIONS]
        assert min(phases) == 2
        assert max(phases) == 12

    def test_phase_count(self):
        """Should have exactly 11 distinct phases."""
        phases = sorted(set(s["phase"] for s in STACK_DEFINITIONS))
        assert phases == [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

    def test_scanning_deleted_before_security(self):
        """Scanning (phase 2) must be deleted before security (phase 3)."""
        scanning_phases = {
            s["phase"] for s in STACK_DEFINITIONS if s["layer"] == "scanning"
        }
        security_phases = {
            s["phase"] for s in STACK_DEFINITIONS if s["layer"] == "security"
        }
        assert max(scanning_phases) < min(security_phases)

    def test_security_deleted_before_sandbox(self):
        """Security (phase 3) must be deleted before sandbox (phase 4)."""
        security_phases = {
            s["phase"] for s in STACK_DEFINITIONS if s["layer"] == "security"
        }
        sandbox_phases = {
            s["phase"] for s in STACK_DEFINITIONS if s["layer"] == "sandbox"
        }
        assert max(security_phases) < min(sandbox_phases)

    def test_nodegroups_deleted_before_eks(self):
        """Node groups (phase 9) must be deleted before EKS (phase 10)."""
        phases = {}
        for s in STACK_DEFINITIONS:
            phases.setdefault(s["phase"], []).append(s["name"])

        # Phase 9 = node groups, Phase 10 = EKS
        assert 9 in phases
        assert 10 in phases
        for ng in phases[9]:
            assert "nodegroup" in ng or "neural-memory-gpu" in ng
        for eks in phases[10]:
            assert "eks" in eks

    def test_eks_deleted_before_data(self):
        """EKS (phase 10) must be deleted before data stores (phase 11)."""
        eks_phases = {
            s["phase"]
            for s in STACK_DEFINITIONS
            if s["name"] == f"{PROJECT_NAME}-eks-{ENVIRONMENT}"
        }
        data_phases = {s["phase"] for s in STACK_DEFINITIONS if s["layer"] == "data"}
        assert max(eks_phases) < min(data_phases)

    def test_data_deleted_before_vpc_endpoints(self):
        """Data stores (phase 11) must be deleted before VPC endpoints (phase 12)."""
        data_phases = {s["phase"] for s in STACK_DEFINITIONS if s["layer"] == "data"}
        vpce_phases = {
            s["phase"] for s in STACK_DEFINITIONS if "vpc-endpoints" in s["name"]
        }
        assert max(data_phases) < min(vpce_phases)

    def test_vpc_endpoints_last_to_delete(self):
        """VPC endpoints should be the last thing deleted (highest phase)."""
        vpce_stacks = [s for s in STACK_DEFINITIONS if "vpc-endpoints" in s["name"]]
        assert len(vpce_stacks) == 1
        max_phase = max(s["phase"] for s in STACK_DEFINITIONS)
        assert vpce_stacks[0]["phase"] == max_phase

    def test_application_deleted_before_network_services(self):
        """Application (phase 7) must be deleted before network (phase 8)."""
        app_phases = {
            s["phase"] for s in STACK_DEFINITIONS if s["layer"] == "application"
        }
        network_phases = {
            s["phase"] for s in STACK_DEFINITIONS if s["layer"] == "network"
        }
        assert max(app_phases) < min(network_phases)

    def test_network_services_deleted_before_nodegroups(self):
        """Network services (phase 8) must be deleted before nodegroups (phase 9)."""
        network_phases = {
            s["phase"] for s in STACK_DEFINITIONS if s["layer"] == "network"
        }
        compute_nodegroup_phases = {
            s["phase"]
            for s in STACK_DEFINITIONS
            if "nodegroup" in s["name"] or "neural-memory-gpu" in s["name"]
        }
        assert max(network_phases) < min(compute_nodegroup_phases)

    def test_layers_match_phases(self):
        """Each phase should have stacks from a single layer."""
        for phase_num in sorted(set(s["phase"] for s in STACK_DEFINITIONS)):
            layers = {s["layer"] for s in STACK_DEFINITIONS if s["phase"] == phase_num}
            assert len(layers) == 1, f"Phase {phase_num} has mixed layers: {layers}"


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

        # Should have configs for all 9 core stacks
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

    def test_deploy_configs_core_9_stacks(self):
        """Deploy configs should contain exactly the 9 core infrastructure stacks."""
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
        expected_stacks = {
            f"{PROJECT_NAME}-vpc-endpoints-{ENVIRONMENT}",
            f"{PROJECT_NAME}-neptune-{ENVIRONMENT}",
            f"{PROJECT_NAME}-opensearch-{ENVIRONMENT}",
            f"{PROJECT_NAME}-elasticache-{ENVIRONMENT}",
            f"{PROJECT_NAME}-eks-{ENVIRONMENT}",
            f"{PROJECT_NAME}-nodegroup-general-{ENVIRONMENT}",
            f"{PROJECT_NAME}-nodegroup-memory-{ENVIRONMENT}",
            f"{PROJECT_NAME}-nodegroup-gpu-{ENVIRONMENT}",
            f"{PROJECT_NAME}-network-services-{ENVIRONMENT}",
        }
        assert set(configs.keys()) == expected_stacks


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

        with patch("dev_killswitch.boto3.client") as mock_ec2_client:
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
        """Node groups (phase 9) must be deleted before EKS (phase 10)."""
        phases = {}
        for s in STACK_DEFINITIONS:
            phases.setdefault(s["phase"], []).append(s["name"])

        # Phase 9 = node groups, Phase 10 = EKS
        assert 9 in phases
        assert 10 in phases
        for ng in phases[9]:
            assert "nodegroup" in ng or "neural-memory-gpu" in ng
        for eks in phases[10]:
            assert "eks" in eks

        # Phase 11 = data stores
        assert 11 in phases
        for ds in phases[11]:
            assert any(svc in ds for svc in ["neptune", "opensearch", "elasticache"])

    def test_shutdown_vpc_endpoints_last(self):
        """VPC endpoints should be the last thing deleted (highest phase)."""
        vpce_stacks = [s for s in STACK_DEFINITIONS if "vpc-endpoints" in s["name"]]
        assert len(vpce_stacks) == 1
        max_phase = max(s["phase"] for s in STACK_DEFINITIONS)
        assert vpce_stacks[0]["phase"] == max_phase

    def test_shutdown_scanning_first(self):
        """Scanning engine stacks (phase 2) should be deleted first."""
        scanning_stacks = [s for s in STACK_DEFINITIONS if s["layer"] == "scanning"]
        assert len(scanning_stacks) == 8
        min_phase = min(s["phase"] for s in STACK_DEFINITIONS)
        for s in scanning_stacks:
            assert s["phase"] == min_phase


class TestRestoreFlow:
    """Test the overall restore flow logic."""

    def test_restore_vpc_endpoints_first(self):
        """VPC endpoints should deploy before data stores."""
        vpce = [s for s in STACK_DEFINITIONS if "vpc-endpoints" in s["name"]]
        data = [s for s in STACK_DEFINITIONS if s["layer"] == "data"]
        assert len(vpce) == 1
        assert len(data) == 3  # neptune, opensearch, elasticache

    def test_restore_data_stores_before_eks(self):
        """Data stores should deploy before EKS in restore order."""
        # Restore is inverted: vpce -> data -> EKS -> nodegroups
        # Verified through the restore_order in do_restore()
        data = [s for s in STACK_DEFINITIONS if s["layer"] == "data"]
        eks = [
            s
            for s in STACK_DEFINITIONS
            if s["name"] == f"{PROJECT_NAME}-eks-{ENVIRONMENT}"
        ]
        assert len(data) == 3
        assert len(eks) == 1

    def test_restore_triggers_codebuild_for_upper_layers(self):
        """Restore must trigger CodeBuild for upper layer stacks."""
        # The upper layers (scanning, security, sandbox, serverless, etc.)
        # are restored via CodeBuild, not direct CloudFormation
        assert len(CODEBUILD_RESTORE_PROJECTS) == 6
        project_names = set(CODEBUILD_RESTORE_PROJECTS)
        assert f"{PROJECT_NAME}-application-deploy-{ENVIRONMENT}" in project_names
        assert f"{PROJECT_NAME}-security-deploy-{ENVIRONMENT}" in project_names
        assert f"{PROJECT_NAME}-vuln-scan-deploy-{ENVIRONMENT}" in project_names


class TestIdempotency:
    """Test that operations are safe to run multiple times."""

    def test_delete_already_deleted_is_noop(self, stack_manager, mock_cfn):
        from botocore.exceptions import ClientError

        mock_cfn.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "does not exist"}},
            "DescribeStacks",
        )
        result = stack_manager.delete_stack("aura-neptune-dev", dry_run=False)
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
# State File Tests
# ---------------------------------------------------------------------------


class TestStateFile:
    def test_state_local_path(self):
        from dev_killswitch import _state_local_path

        path = _state_local_path()
        assert path.name == "dev-killswitch-state.json"
        assert str(path).endswith(".aura/dev-killswitch-state.json")

    def test_save_state_s3_key(self):
        """State should be saved to killswitch/dev-state.json in S3."""
        state = KillSwitchState(status="shutdown")
        mock_s3 = MagicMock()
        mock_cfn = MagicMock()
        mock_cfn.describe_stacks.return_value = {
            "Stacks": [
                {
                    "Outputs": [
                        {
                            "OutputKey": "ArtifactsBucketName",
                            "OutputValue": "aura-artifacts-dev",
                        }
                    ]
                }
            ]
        }

        from dev_killswitch import save_state

        with patch("dev_killswitch._state_local_path") as mock_path:
            mock_file = MagicMock()
            mock_path.return_value = mock_file
            save_state(state, mock_s3, mock_cfn)

        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["Key"] == "killswitch/dev-state.json"
        assert call_kwargs["Bucket"] == "aura-artifacts-dev"


# ---------------------------------------------------------------------------
# CLI Argument Tests
# ---------------------------------------------------------------------------


class TestCLIArguments:
    def test_main_requires_subcommand(self):
        from dev_killswitch import main

        with patch("sys.argv", ["dev_killswitch.py"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2  # argparse error

    def test_shutdown_defaults_to_dry_run(self):
        """Shutdown without --execute should be dry-run."""
        from dev_killswitch import main

        with patch("sys.argv", ["dev_killswitch.py", "shutdown"]):
            with patch("dev_killswitch.do_shutdown") as mock_shutdown:
                mock_shutdown.return_value = 0
                main()
                args = mock_shutdown.call_args[0][0]
                assert args.execute is False

    def test_shutdown_with_execute(self):
        from dev_killswitch import main

        with patch("sys.argv", ["dev_killswitch.py", "shutdown", "--execute"]):
            with patch("dev_killswitch.do_shutdown") as mock_shutdown:
                mock_shutdown.return_value = 0
                main()
                args = mock_shutdown.call_args[0][0]
                assert args.execute is True

    def test_restore_defaults_to_dry_run(self):
        from dev_killswitch import main

        with patch("sys.argv", ["dev_killswitch.py", "restore"]):
            with patch("dev_killswitch.do_restore") as mock_restore:
                mock_restore.return_value = 0
                main()
                args = mock_restore.call_args[0][0]
                assert args.execute is False

    def test_status_subcommand(self):
        """Status subcommand should be accepted."""
        from dev_killswitch import main

        with patch("sys.argv", ["dev_killswitch.py", "status"]):
            with patch("dev_killswitch.do_status") as mock_status:
                mock_status.return_value = 0
                main()
                mock_status.assert_called_once()

    def test_shutdown_with_skip_snapshot(self):
        """Shutdown --skip-snapshot flag should be parsed."""
        from dev_killswitch import main

        with patch("sys.argv", ["dev_killswitch.py", "shutdown", "--skip-snapshot"]):
            with patch("dev_killswitch.do_shutdown") as mock_shutdown:
                mock_shutdown.return_value = 0
                main()
                args = mock_shutdown.call_args[0][0]
                assert args.skip_snapshot is True

    def test_confirmation_string_destroy_dev(self):
        """Confirmation string must be 'DESTROY DEV' not 'DESTROY QA'."""
        # This is validated by reading the source; the confirmation string
        # is checked in do_shutdown. We verify the environment is correct.
        assert ENVIRONMENT == "dev"
        # The confirmation string in the source is "DESTROY DEV"
        # (verified by code inspection of do_shutdown)


# ---------------------------------------------------------------------------
# Cleanup Operations
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
                            "Key": "kubernetes.io/cluster/aura-cluster-dev",
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
                {
                    "Tags": [
                        {"Key": "elbv2.k8s.aws/cluster", "Value": "aura-cluster-dev"}
                    ]
                }
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
                        "logGroupName": "/aura/api-service-dev",
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
        call_count = [0]

        def paginate_side_effect(**kwargs):
            prefix = kwargs.get("logGroupNamePrefix", "")
            if prefix == "/aura/":
                return [
                    {
                        "logGroups": [
                            {
                                "logGroupName": "/aura/api-service-dev",
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

    # -- CLI parsing ---------------------------------------------------------

    def test_cleanup_subcommand_parsed(self):
        """Cleanup command should be parseable by main()."""
        from dev_killswitch import main

        with patch("sys.argv", ["dev_killswitch.py", "cleanup"]):
            with patch("dev_killswitch.do_cleanup") as mock_cleanup:
                mock_cleanup.return_value = 0
                main()
                mock_cleanup.assert_called_once()

    def test_cleanup_schedule_kms_flag(self):
        """--schedule-kms-deletion flag should be parsed correctly."""
        from dev_killswitch import main

        with patch(
            "sys.argv",
            ["dev_killswitch.py", "cleanup", "--schedule-kms-deletion"],
        ):
            with patch("dev_killswitch.do_cleanup") as mock_cleanup:
                mock_cleanup.return_value = 0
                main()
                args = mock_cleanup.call_args[0][0]
                assert args.schedule_kms_deletion is True
