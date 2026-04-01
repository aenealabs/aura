"""Tests for the IncidentDetector service."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.services.runbook.incident_detector import (
    ErrorSignature,
    Incident,
    IncidentDetector,
    IncidentType,
)


class TestErrorSignature:
    """Tests for ErrorSignature dataclass."""

    def test_matches_pattern(self):
        """Test pattern matching."""
        sig = ErrorSignature(
            pattern=r"exec format error",
            service="docker",
            severity="high",
            keywords=["docker", "platform"],
        )

        assert sig.matches("Error: exec format error during build")
        assert not sig.matches("Build succeeded")

    def test_matches_case_insensitive(self):
        """Test case-insensitive matching."""
        sig = ErrorSignature(
            pattern=r"accessdenied",
            service="iam",
            severity="high",
            keywords=["iam"],
        )

        assert sig.matches("AccessDenied when calling operation")
        assert sig.matches("ACCESSDENIED error occurred")

    def test_matches_multiline(self):
        """Test multiline pattern matching."""
        sig = ErrorSignature(
            pattern=r"ROLLBACK_COMPLETE",
            service="cloudformation",
            severity="high",
            keywords=["cloudformation"],
        )

        log_text = """
        Stack status changed
        Current status: ROLLBACK_COMPLETE
        Previous status: UPDATE_IN_PROGRESS
        """

        assert sig.matches(log_text)


class TestIncident:
    """Tests for Incident dataclass."""

    def test_resolution_duration(self):
        """Test resolution duration calculation."""
        incident = Incident(
            id="test-001",
            incident_type=IncidentType.DOCKER_BUILD_FIX,
            title="Test Incident",
            description="Test description",
            error_messages=["Error message"],
            error_signatures=[],
            resolution_steps=[],
            affected_services=["docker"],
            affected_resources=["resource-1"],
            root_cause="Test root cause",
            start_time=datetime(2024, 1, 1, 10, 0, 0),
            end_time=datetime(2024, 1, 1, 10, 30, 0),
            source="codebuild",
            source_id="build-123",
            confidence=0.8,
        )

        assert incident.resolution_duration_minutes == 30.0

    def test_is_high_confidence(self):
        """Test high confidence detection."""
        high_confidence = Incident(
            id="test-001",
            incident_type=IncidentType.DOCKER_BUILD_FIX,
            title="Test",
            description="Test",
            error_messages=[],
            error_signatures=[],
            resolution_steps=[],
            affected_services=[],
            affected_resources=[],
            root_cause="",
            start_time=datetime.now(),
            end_time=datetime.now(),
            source="test",
            source_id="test",
            confidence=0.85,
        )

        low_confidence = Incident(
            id="test-002",
            incident_type=IncidentType.DOCKER_BUILD_FIX,
            title="Test",
            description="Test",
            error_messages=[],
            error_signatures=[],
            resolution_steps=[],
            affected_services=[],
            affected_resources=[],
            root_cause="",
            start_time=datetime.now(),
            end_time=datetime.now(),
            source="test",
            source_id="test",
            confidence=0.5,
        )

        assert high_confidence.is_high_confidence is True
        assert low_confidence.is_high_confidence is False


class TestIncidentDetector:
    """Tests for IncidentDetector class."""

    @pytest.fixture
    def detector(self):
        """Create an IncidentDetector instance with mocked AWS clients."""
        with patch("boto3.client") as mock_client:
            mock_logs = MagicMock()
            mock_cf = MagicMock()
            mock_codebuild = MagicMock()

            def get_client(service, **kwargs):
                if service == "logs":
                    return mock_logs
                elif service == "cloudformation":
                    return mock_cf
                elif service == "codebuild":
                    return mock_codebuild
                return MagicMock()

            mock_client.side_effect = get_client

            detector = IncidentDetector(
                region="us-east-1",
                project_name="aura",
                environment="dev",
            )
            detector.logs_client = mock_logs
            detector.cf_client = mock_cf
            detector.codebuild_client = mock_codebuild

            return detector

    def test_classify_docker_incident(self, detector):
        """Test classification of Docker incidents."""
        signatures = [
            ErrorSignature(
                pattern=r"exec format error",
                service="docker",
                severity="high",
                keywords=["docker", "platform", "architecture"],
            )
        ]

        result = detector._classify_incident_type(signatures)
        assert result == IncidentType.DOCKER_BUILD_FIX

    def test_classify_iam_incident(self, detector):
        """Test classification of IAM incidents."""
        signatures = [
            ErrorSignature(
                pattern=r"AccessDenied",
                service="iam",
                severity="high",
                keywords=["iam", "permissions"],
            )
        ]

        result = detector._classify_incident_type(signatures)
        assert result == IncidentType.IAM_PERMISSION_FIX

    def test_classify_shell_incident(self, detector):
        """Test classification of shell syntax incidents."""
        signatures = [
            ErrorSignature(
                pattern=r"\[\[: not found",
                service="codebuild",
                severity="medium",
                keywords=["bash", "shell", "syntax"],
            )
        ]

        result = detector._classify_incident_type(signatures)
        assert result == IncidentType.SHELL_SYNTAX_FIX

    def test_classify_ecr_incident(self, detector):
        """Test classification of ECR incidents."""
        signatures = [
            ErrorSignature(
                pattern=r"AlreadyExists",
                service="ecr",
                severity="medium",
                keywords=["ecr", "repository"],
            )
        ]

        result = detector._classify_incident_type(signatures)
        assert result == IncidentType.ECR_CONFLICT_RESOLUTION

    def test_generate_incident_title(self, detector):
        """Test incident title generation."""
        signatures = [
            ErrorSignature(
                pattern=r"AccessDenied",
                service="bedrock",
                severity="high",
                keywords=["bedrock", "guardrails", "permissions"],
            )
        ]

        title = detector._generate_incident_title(signatures)
        assert "BEDROCK" in title
        assert "Bedrock" in title or "Guardrails" in title or "Permissions" in title

    def test_extract_error_messages(self, detector):
        """Test error message extraction from logs."""
        log_text = """
        2024-01-01 10:00:00 INFO Starting build
        2024-01-01 10:01:00 ERROR: AccessDenied when calling ListTagsForResource
        2024-01-01 10:02:00 FATAL: Build failed with exit code 1
        2024-01-01 10:03:00 An error occurred (AccessDenied): User is not authorized
        """

        messages = detector._extract_error_messages(log_text)

        assert len(messages) > 0
        assert any("AccessDenied" in msg for msg in messages)

    def test_infer_root_cause_docker(self, detector):
        """Test root cause inference for Docker issues."""
        signatures = [
            ErrorSignature(
                pattern=r"exec format error",
                service="docker",
                severity="high",
                keywords=["docker", "platform"],
            )
        ]

        cause = detector._infer_root_cause(signatures, [])
        assert "architecture" in cause.lower() or "docker" in cause.lower()

    def test_infer_root_cause_iam(self, detector):
        """Test root cause inference for IAM issues."""
        signatures = [
            ErrorSignature(
                pattern=r"AccessDenied",
                service="iam",
                severity="high",
                keywords=["iam", "permissions"],
            )
        ]

        cause = detector._infer_root_cause(signatures, [])
        assert "permission" in cause.lower() or "iam" in cause.lower()

    def test_calculate_confidence_single_signature(self, detector):
        """Test confidence calculation with single signature."""
        signatures = [
            ErrorSignature(
                pattern=r"test",
                service="test",
                severity="medium",
                keywords=["test"],
            )
        ]

        confidence = detector._calculate_confidence(signatures)
        assert 0.5 <= confidence <= 0.7

    def test_calculate_confidence_multiple_signatures(self, detector):
        """Test confidence calculation with multiple signatures."""
        signatures = [
            ErrorSignature(
                pattern=r"test1",
                service="test",
                severity="high",
                keywords=["test"],
            ),
            ErrorSignature(
                pattern=r"test2",
                service="test",
                severity="high",
                keywords=["test"],
            ),
            ErrorSignature(
                pattern=r"test3",
                service="test",
                severity="medium",
                keywords=["test"],
            ),
        ]

        confidence = detector._calculate_confidence(signatures)
        assert confidence >= 0.7

    def test_calculate_confidence_empty(self, detector):
        """Test confidence calculation with no signatures."""
        confidence = detector._calculate_confidence([])
        assert confidence == 0.3

    @pytest.mark.asyncio
    async def test_detect_from_git_commits(self, detector):
        """Test incident detection from git commits."""
        commits = [
            {
                "sha": "abc123def456",
                "message": "fix: resolve shell syntax error in buildspec",
                "timestamp": datetime.now(),
                "files": ["deploy/buildspecs/buildspec-application.yml"],
            },
            {
                "sha": "def456abc789",
                "message": "feat: add new feature",
                "timestamp": datetime.now(),
                "files": ["src/services/new_service.py"],
            },
        ]

        incidents = await detector.detect_from_git_commits(commits)

        # Should detect at least one incident from the fix commit
        assert len(incidents) >= 1
        assert any(inc.source == "git" for inc in incidents)

    def test_create_incident_from_commit(self, detector):
        """Test incident creation from a commit."""
        commit = {
            "sha": "abc123def456789",
            "message": "fix: resolve AccessDenied error in CodeBuild IAM policy",
            "timestamp": datetime.now(),
            "files": [
                "deploy/cloudformation/codebuild-application.yaml",
                "docs/runbooks/IAM_PERMISSIONS.md",
            ],
        }

        signatures = [
            ErrorSignature(
                pattern=r"^fix:",
                service="general",
                severity="medium",
                keywords=["fix", "bug"],
            )
        ]

        incident = detector._create_incident_from_commit(commit, signatures)

        assert incident is not None
        assert incident.source == "git"
        assert "abc123de" in incident.id
        assert "cloudformation" in incident.affected_services


class TestIncidentTypeEnum:
    """Tests for IncidentType enumeration."""

    def test_all_types_have_values(self):
        """Test that all incident types have string values."""
        for incident_type in IncidentType:
            assert isinstance(incident_type.value, str)
            assert len(incident_type.value) > 0

    def test_type_values_are_unique(self):
        """Test that all incident type values are unique."""
        values = [t.value for t in IncidentType]
        assert len(values) == len(set(values))
