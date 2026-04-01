"""
Tests for the Incident Detector Service.

Tests incident detection from CloudWatch, CloudFormation, CodeBuild, and Git sources.
"""

import platform

import pytest

# Run tests in separate processes to avoid mock pollution
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from src.services.runbook.incident_detector import (
    ErrorSignature,
    Incident,
    IncidentDetector,
    IncidentType,
    ResolutionStep,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_logs_client():
    """Mock CloudWatch Logs client."""
    return MagicMock()


@pytest.fixture
def mock_cf_client():
    """Mock CloudFormation client."""
    return MagicMock()


@pytest.fixture
def mock_codebuild_client():
    """Mock CodeBuild client."""
    return MagicMock()


@pytest.fixture
def detector(mock_logs_client, mock_cf_client, mock_codebuild_client):
    """Create IncidentDetector with mocked AWS clients."""
    with patch("boto3.client") as mock_boto:

        def client_factory(service, **kwargs):
            if service == "logs":
                return mock_logs_client
            elif service == "cloudformation":
                return mock_cf_client
            elif service == "codebuild":
                return mock_codebuild_client
            return MagicMock()

        mock_boto.side_effect = client_factory

        detector = IncidentDetector(
            region="us-east-1",
            project_name="aura",
            environment="dev",
        )
        detector.logs_client = mock_logs_client
        detector.cf_client = mock_cf_client
        detector.codebuild_client = mock_codebuild_client

        return detector


@pytest.fixture
def sample_error_signature():
    """Sample error signature for testing."""
    return ErrorSignature(
        pattern=r"exec format error",
        service="docker",
        severity="high",
        keywords=["docker", "platform", "architecture"],
    )


@pytest.fixture
def sample_resolution_step():
    """Sample resolution step for testing."""
    return ResolutionStep(
        command="docker build --platform linux/amd64 -t image .",
        output="Successfully built abc123",
        timestamp=datetime.now(),
        success=True,
        description="Build with explicit platform flag",
    )


@pytest.fixture
def sample_incident(sample_error_signature, sample_resolution_step):
    """Sample incident for testing."""
    return Incident(
        id="cb-test123",
        incident_type=IncidentType.DOCKER_BUILD_FIX,
        title="Docker Platform Issue",
        description="CodeBuild failed due to architecture mismatch",
        error_messages=["exec format error", "exit code 255"],
        error_signatures=[sample_error_signature],
        resolution_steps=[sample_resolution_step],
        affected_services=["docker", "codebuild"],
        affected_resources=["aura-application-deploy-dev"],
        root_cause="Docker image architecture mismatch (ARM64 vs AMD64)",
        start_time=datetime.now() - timedelta(hours=2),
        end_time=datetime.now(),
        source="codebuild",
        source_id="build-12345",
        confidence=0.85,
        metadata={"failed_build_id": "build-12344"},
    )


@pytest.fixture
def sample_failed_build():
    """Sample failed CodeBuild build."""
    return {
        "id": "aura-application-deploy-dev:build-12344",
        "projectName": "aura-application-deploy-dev",
        "buildStatus": "FAILED",
        "startTime": datetime.now().isoformat() + "Z",
        "endTime": datetime.now().isoformat() + "Z",
        "logs": {
            "groupName": "/aws/codebuild/aura-application-deploy-dev",
            "streamName": "abc123/build-12344",
        },
    }


@pytest.fixture
def sample_success_build():
    """Sample successful CodeBuild build."""
    return {
        "id": "aura-application-deploy-dev:build-12345",
        "projectName": "aura-application-deploy-dev",
        "buildStatus": "SUCCEEDED",
        "startTime": datetime.now().isoformat() + "Z",
        "endTime": datetime.now().isoformat() + "Z",
        "logs": {
            "groupName": "/aws/codebuild/aura-application-deploy-dev",
            "streamName": "abc123/build-12345",
        },
    }


# =============================================================================
# ErrorSignature Tests
# =============================================================================


class TestErrorSignature:
    """Tests for ErrorSignature dataclass."""

    def test_create_signature(self):
        """Test creating an error signature."""
        sig = ErrorSignature(
            pattern=r"AccessDenied",
            service="iam",
            severity="high",
            keywords=["iam", "permissions"],
        )

        assert sig.pattern == r"AccessDenied"
        assert sig.service == "iam"
        assert sig.severity == "high"
        assert "iam" in sig.keywords

    def test_matches_positive(self, sample_error_signature):
        """Test pattern matching succeeds for matching text."""
        text = "Error: exec format error when running container"
        assert sample_error_signature.matches(text) is True

    def test_matches_negative(self, sample_error_signature):
        """Test pattern matching fails for non-matching text."""
        text = "Build completed successfully"
        assert sample_error_signature.matches(text) is False

    def test_matches_case_insensitive(self, sample_error_signature):
        """Test pattern matching is case insensitive."""
        text = "Error: EXEC FORMAT ERROR in container"
        assert sample_error_signature.matches(text) is True

    def test_default_severity(self):
        """Test default severity is medium."""
        sig = ErrorSignature(pattern=r"test", service="test")
        assert sig.severity == "medium"

    def test_default_keywords(self):
        """Test default keywords is empty list."""
        sig = ErrorSignature(pattern=r"test", service="test")
        assert sig.keywords == []


# =============================================================================
# ResolutionStep Tests
# =============================================================================


class TestResolutionStep:
    """Tests for ResolutionStep dataclass."""

    def test_create_resolution_step(self, sample_resolution_step):
        """Test creating a resolution step."""
        assert "docker build" in sample_resolution_step.command
        assert sample_resolution_step.success is True
        assert sample_resolution_step.description != ""

    def test_resolution_step_required_fields(self):
        """Test resolution step with all required fields."""
        step = ResolutionStep(
            command="aws s3 ls",
            output="bucket-list",
            timestamp=datetime.now(),
            success=True,
        )
        assert step.command == "aws s3 ls"
        assert step.description == ""


# =============================================================================
# Incident Tests
# =============================================================================


class TestIncident:
    """Tests for Incident dataclass."""

    def test_create_incident(self, sample_incident):
        """Test creating an incident."""
        assert sample_incident.id == "cb-test123"
        assert sample_incident.incident_type == IncidentType.DOCKER_BUILD_FIX
        assert sample_incident.source == "codebuild"

    def test_resolution_duration_minutes(self, sample_incident):
        """Test calculating resolution duration."""
        duration = sample_incident.resolution_duration_minutes
        assert duration > 0
        assert duration < 180  # Less than 3 hours

    def test_is_high_confidence_true(self, sample_incident):
        """Test high confidence detection when >= 0.7."""
        assert sample_incident.is_high_confidence is True

    def test_is_high_confidence_false(self, sample_incident):
        """Test high confidence detection when < 0.7."""
        sample_incident.confidence = 0.5
        assert sample_incident.is_high_confidence is False

    def test_incident_metadata(self, sample_incident):
        """Test incident metadata access."""
        assert "failed_build_id" in sample_incident.metadata
        assert sample_incident.metadata["failed_build_id"] == "build-12344"


# =============================================================================
# IncidentType Tests
# =============================================================================


class TestIncidentType:
    """Tests for IncidentType enum."""

    def test_all_incident_types_exist(self):
        """Test all expected incident types exist."""
        expected_types = [
            "CODEBUILD_FAILURE_RECOVERY",
            "CLOUDFORMATION_ROLLBACK_RECOVERY",
            "CLOUDFORMATION_STACK_FIX",
            "DOCKER_BUILD_FIX",
            "IAM_PERMISSION_FIX",
            "ECR_CONFLICT_RESOLUTION",
            "SHELL_SYNTAX_FIX",
            "GENERAL_BUG_FIX",
            "INFRASTRUCTURE_FIX",
            "SECURITY_FIX",
        ]

        for type_name in expected_types:
            assert hasattr(IncidentType, type_name)

    def test_incident_type_values(self):
        """Test incident type string values."""
        assert IncidentType.DOCKER_BUILD_FIX.value == "docker_build_fix"
        assert IncidentType.IAM_PERMISSION_FIX.value == "iam_permission_fix"


# =============================================================================
# IncidentDetector Tests
# =============================================================================


class TestIncidentDetector:
    """Tests for IncidentDetector class."""

    def test_init(self, detector):
        """Test detector initialization."""
        assert detector.region == "us-east-1"
        assert detector.project_name == "aura"
        assert detector.environment == "dev"

    def test_error_patterns_defined(self, detector):
        """Test error patterns are defined."""
        assert "codebuild" in detector.ERROR_PATTERNS
        assert "cloudformation" in detector.ERROR_PATTERNS
        assert "git" in detector.ERROR_PATTERNS

    def test_cf_states_defined(self, detector):
        """Test CloudFormation states are defined."""
        assert "ROLLBACK_COMPLETE" in detector.CF_FAILURE_STATES
        assert "CREATE_COMPLETE" in detector.CF_SUCCESS_STATES


class TestIncidentDetectorDetection:
    """Tests for IncidentDetector detection methods."""

    @pytest.mark.asyncio
    async def test_detect_incidents_returns_list(self, detector):
        """Test detect_incidents returns a list."""
        detector.codebuild_client.list_builds_for_project.return_value = {"ids": []}

        incidents = await detector.detect_incidents(hours=24, sources=["codebuild"])
        assert isinstance(incidents, list)

    @pytest.mark.asyncio
    async def test_detect_incidents_default_sources(self, detector):
        """Test detect_incidents uses default sources."""
        detector.codebuild_client.list_builds_for_project.return_value = {"ids": []}
        detector.cf_client.get_paginator.return_value.paginate.return_value = []

        await detector.detect_incidents(hours=24)

        detector.codebuild_client.list_builds_for_project.assert_called()

    @pytest.mark.asyncio
    async def test_detect_codebuild_incidents_no_builds(self, detector):
        """Test CodeBuild detection with no builds."""
        detector.codebuild_client.list_builds_for_project.return_value = {"ids": []}

        incidents = await detector._detect_codebuild_incidents(24)
        assert incidents == []

    @pytest.mark.asyncio
    async def test_detect_codebuild_incidents_failure_recovery(
        self, detector, sample_failed_build, sample_success_build
    ):
        """Test CodeBuild detection finds failure -> success patterns."""
        detector.codebuild_client.list_builds_for_project.return_value = {
            "ids": ["build-12345", "build-12344"]
        }
        detector.codebuild_client.batch_get_builds.return_value = {
            "builds": [sample_success_build, sample_failed_build]
        }
        detector.logs_client.get_log_events.return_value = {
            "events": [
                {"message": "Error: exec format error"},
                {"message": "exit code: 255"},
            ]
        }

        incidents = await detector._detect_codebuild_incidents(24)

        assert len(incidents) == 1
        assert incidents[0].incident_type == IncidentType.DOCKER_BUILD_FIX

    @pytest.mark.asyncio
    async def test_detect_codebuild_incidents_client_error(self, detector):
        """Test CodeBuild detection handles ClientError."""
        detector.codebuild_client.list_builds_for_project.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "ListBuildsForProject",
        )

        incidents = await detector._detect_codebuild_incidents(24)
        assert incidents == []

    @pytest.mark.asyncio
    async def test_detect_cloudformation_incidents_no_stacks(self, detector):
        """Test CloudFormation detection with no matching stacks."""
        paginator = MagicMock()
        paginator.paginate.return_value = [{"StackSummaries": []}]
        detector.cf_client.get_paginator.return_value = paginator

        incidents = await detector._detect_cloudformation_incidents(24)
        assert incidents == []

    @pytest.mark.asyncio
    async def test_detect_cloudformation_incidents_recovery(self, detector):
        """Test CloudFormation detection finds rollback recovery."""
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "StackSummaries": [
                    {"StackName": "aura-data-dev", "StackStatus": "UPDATE_COMPLETE"}
                ]
            }
        ]
        detector.cf_client.get_paginator.return_value = paginator

        # Mock stack events showing failure -> success (code expects failure first in list)
        failure_time = datetime.now() - timedelta(hours=1)
        success_time = datetime.now()

        detector.cf_client.describe_stack_events.return_value = {
            "StackEvents": [
                {
                    "Timestamp": failure_time,
                    "ResourceStatus": "UPDATE_ROLLBACK_COMPLETE",
                    "ResourceStatusReason": "Resource already exists in ECR",
                    "LogicalResourceId": "TestResource",
                },
                {
                    "Timestamp": success_time,
                    "ResourceStatus": "UPDATE_COMPLETE",
                    "LogicalResourceId": "TestResource",
                },
            ]
        }

        incidents = await detector._detect_cloudformation_incidents(24)

        assert len(incidents) == 1
        assert incidents[0].source == "cloudformation"

    @pytest.mark.asyncio
    async def test_detect_cloudwatch_incidents_empty(self, detector):
        """Test CloudWatch detection returns empty list."""
        incidents = await detector._detect_cloudwatch_incidents(24)
        assert incidents == []


class TestIncidentDetectorAnalysis:
    """Tests for IncidentDetector analysis methods."""

    @pytest.mark.asyncio
    async def test_analyze_codebuild_recovery_no_logs(
        self, detector, sample_failed_build, sample_success_build
    ):
        """Test analysis with missing log info."""
        sample_failed_build["logs"] = {}

        result = await detector._analyze_codebuild_recovery(
            sample_failed_build, sample_success_build
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_codebuild_recovery_no_pattern_match(
        self, detector, sample_failed_build, sample_success_build
    ):
        """Test analysis with no matching error patterns."""
        detector.logs_client.get_log_events.return_value = {
            "events": [{"message": "Some random log message"}]
        }

        result = await detector._analyze_codebuild_recovery(
            sample_failed_build, sample_success_build
        )
        assert result is None

    def test_classify_incident_type_docker(self, detector, sample_error_signature):
        """Test incident classification for docker issues."""
        signatures = [sample_error_signature]
        incident_type = detector._classify_incident_type(signatures)
        assert incident_type == IncidentType.DOCKER_BUILD_FIX

    def test_classify_incident_type_iam(self, detector):
        """Test incident classification for IAM issues."""
        signatures = [
            ErrorSignature(
                pattern=r"AccessDenied",
                service="iam",
                keywords=["iam", "permissions"],
            )
        ]
        incident_type = detector._classify_incident_type(signatures)
        assert incident_type == IncidentType.IAM_PERMISSION_FIX

    def test_classify_incident_type_ecr(self, detector):
        """Test incident classification for ECR issues."""
        signatures = [
            ErrorSignature(
                pattern=r"AlreadyExists",
                service="ecr",
                keywords=["ecr", "repository"],
            )
        ]
        incident_type = detector._classify_incident_type(signatures)
        assert incident_type == IncidentType.ECR_CONFLICT_RESOLUTION

    def test_classify_incident_type_shell(self, detector):
        """Test incident classification for shell syntax issues."""
        signatures = [
            ErrorSignature(
                pattern=r"\[\[.*not found",
                service="codebuild",
                keywords=["bash", "shell"],
            )
        ]
        incident_type = detector._classify_incident_type(signatures)
        assert incident_type == IncidentType.SHELL_SYNTAX_FIX

    def test_classify_incident_type_default(self, detector):
        """Test incident classification defaults to general bug fix."""
        signatures = [
            ErrorSignature(
                pattern=r"unknown error",
                service="unknown",
            )
        ]
        incident_type = detector._classify_incident_type(signatures)
        assert incident_type == IncidentType.GENERAL_BUG_FIX

    def test_generate_incident_title(self, detector, sample_error_signature):
        """Test incident title generation."""
        signatures = [sample_error_signature]
        title = detector._generate_incident_title(signatures)

        assert "DOCKER" in title
        assert "Issue" in title

    def test_generate_incident_title_empty(self, detector):
        """Test incident title generation with empty signatures."""
        title = detector._generate_incident_title([])
        assert title == "Unknown Incident"

    def test_extract_error_messages(self, detector):
        """Test extracting error messages from log text."""
        log_text = """
        ERROR: Something went wrong
        FATAL: Critical failure
        AccessDenied when accessing resource
        """

        messages = detector._extract_error_messages(log_text)
        assert len(messages) > 0
        assert any("AccessDenied" in msg for msg in messages)

    def test_infer_root_cause_docker(self, detector, sample_error_signature):
        """Test root cause inference for docker issues."""
        cause = detector._infer_root_cause([sample_error_signature], [])
        assert "ARM64" in cause or "AMD64" in cause

    def test_infer_root_cause_iam(self, detector):
        """Test root cause inference for IAM issues."""
        sig = ErrorSignature(pattern=r"AccessDenied", service="iam")
        cause = detector._infer_root_cause([sig], [])
        assert "IAM" in cause or "permissions" in cause

    def test_infer_root_cause_empty(self, detector):
        """Test root cause inference with no signatures."""
        cause = detector._infer_root_cause([], [])
        assert cause == "Unknown root cause"

    def test_calculate_confidence(self, detector, sample_error_signature):
        """Test confidence calculation."""
        signatures = [sample_error_signature]  # high severity
        confidence = detector._calculate_confidence(signatures)

        assert confidence >= 0.6
        assert confidence <= 1.0

    def test_calculate_confidence_multiple_signatures(self, detector):
        """Test confidence with multiple signatures."""
        signatures = [
            ErrorSignature(pattern=r"error1", service="s1", severity="high"),
            ErrorSignature(pattern=r"error2", service="s2", severity="high"),
            ErrorSignature(pattern=r"error3", service="s3", severity="medium"),
        ]
        confidence = detector._calculate_confidence(signatures)

        assert confidence >= 0.7

    def test_calculate_confidence_no_signatures(self, detector):
        """Test confidence with no signatures."""
        confidence = detector._calculate_confidence([])
        assert confidence == 0.3


class TestIncidentDetectorGit:
    """Tests for IncidentDetector git detection methods."""

    @pytest.mark.asyncio
    async def test_detect_from_git_commits_fix_pattern(self, detector):
        """Test detecting incidents from git fix commits."""
        commits = [
            {
                "sha": "abc12345678",
                "message": "fix(docker): resolve platform mismatch issue",
                "timestamp": datetime.now(),
                "files": ["Dockerfile", "buildspec.yml"],
            }
        ]

        incidents = await detector.detect_from_git_commits(commits)

        assert len(incidents) == 1
        assert incidents[0].source == "git"
        assert incidents[0].confidence == 0.6

    @pytest.mark.asyncio
    async def test_detect_from_git_commits_hotfix_pattern(self, detector):
        """Test detecting incidents from git hotfix commits."""
        commits = [
            {
                "sha": "def987654",
                "message": "hotfix: emergency security patch",
                "timestamp": datetime.now(),
                "files": ["src/auth.py"],
            }
        ]

        incidents = await detector.detect_from_git_commits(commits)

        assert len(incidents) == 1

    @pytest.mark.asyncio
    async def test_detect_from_git_commits_no_match(self, detector):
        """Test git detection with no matching patterns."""
        commits = [
            {
                "sha": "xyz123",
                "message": "feat: add new feature",
                "timestamp": datetime.now(),
                "files": ["new_feature.py"],
            }
        ]

        incidents = await detector.detect_from_git_commits(commits)
        assert incidents == []

    def test_create_incident_from_commit(self, detector):
        """Test creating incident from commit."""
        commit = {
            "sha": "abc12345678",
            "message": "fix(cloudformation): resolve stack conflict",
            "timestamp": datetime.now(),
            "files": ["deploy/cloudformation/neptune.yaml"],
        }
        signatures = [
            ErrorSignature(pattern=r"^fix", service="general", keywords=["fix"])
        ]

        incident = detector._create_incident_from_commit(commit, signatures)

        assert incident is not None
        assert incident.id == "git-abc12345"
        assert "cloudformation" in incident.affected_services
        assert incident.source == "git"

    def test_create_incident_from_commit_service_detection(self, detector):
        """Test service detection from commit files."""
        commit = {
            "sha": "test123",
            "message": "fix: docker and iam issues",
            "timestamp": datetime.now(),
            "files": ["Dockerfile", "iam-policy.json", "buildspec.yml"],
        }
        signatures = [ErrorSignature(pattern=r"fix", service="general")]

        incident = detector._create_incident_from_commit(commit, signatures)

        assert "docker" in incident.affected_services
        assert "iam" in incident.affected_services
        assert "codebuild" in incident.affected_services
