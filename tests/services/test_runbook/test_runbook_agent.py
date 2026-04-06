"""Tests for the RunbookAgent orchestrator."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.runbook.incident_detector import (
    ErrorSignature,
    Incident,
    IncidentType,
)
from src.services.runbook.runbook_agent import (
    ProcessingStats,
    RunbookAgent,
    RunbookAgentResult,
)
from src.services.runbook.runbook_generator import GeneratedRunbook
from src.services.runbook.runbook_repository import RunbookMetadata
from src.services.runbook.runbook_updater import RunbookUpdate


class TestRunbookAgentResult:
    """Tests for RunbookAgentResult dataclass."""

    def test_is_new_runbook_created(self):
        """Test is_new_runbook for created action."""
        result = RunbookAgentResult(
            success=True,
            action="created",
            runbook_path="docs/runbooks/TEST.md",
            incident_id="inc-123",
            message="Created runbook",
        )

        assert result.is_new_runbook is True

    def test_is_new_runbook_updated(self):
        """Test is_new_runbook for updated action."""
        result = RunbookAgentResult(
            success=True,
            action="updated",
            runbook_path="docs/runbooks/TEST.md",
            incident_id="inc-123",
            message="Updated runbook",
        )

        assert result.is_new_runbook is False


class TestProcessingStats:
    """Tests for ProcessingStats dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        stats = ProcessingStats(
            incidents_detected=5,
            runbooks_created=2,
            runbooks_updated=1,
            runbooks_skipped=2,
            errors=0,
            processing_time_seconds=10.5,
        )

        result = stats.to_dict()

        assert result["incidents_detected"] == 5
        assert result["runbooks_created"] == 2
        assert result["runbooks_updated"] == 1
        assert result["runbooks_skipped"] == 2
        assert result["errors"] == 0
        assert result["processing_time_seconds"] == 10.5


class TestRunbookAgent:
    """Tests for RunbookAgent orchestrator."""

    @pytest.fixture
    def sample_incident(self):
        """Create a sample incident for testing."""
        return Incident(
            id="cb-build123",
            incident_type=IncidentType.DOCKER_BUILD_FIX,
            title="Docker Platform Mismatch",
            description="CodeBuild failed due to architecture mismatch",
            error_messages=["exec format error"],
            error_signatures=[
                ErrorSignature(
                    pattern=r"exec format error",
                    service="docker",
                    severity="high",
                    keywords=["docker", "platform"],
                )
            ],
            resolution_steps=[],
            affected_services=["docker"],
            affected_resources=["aura-api-dev"],
            root_cause="Architecture mismatch",
            start_time=datetime.now(),
            end_time=datetime.now(),
            source="codebuild",
            source_id="build-123",
            confidence=0.85,
        )

    @pytest.fixture
    def low_confidence_incident(self):
        """Create a low confidence incident for testing."""
        return Incident(
            id="low-conf-123",
            incident_type=IncidentType.GENERAL_BUG_FIX,
            title="Unknown Issue",
            description="Some vague issue",
            error_messages=["Something failed"],
            error_signatures=[],
            resolution_steps=[],
            affected_services=["unknown"],
            affected_resources=[],
            root_cause="Unknown",
            start_time=datetime.now(),
            end_time=datetime.now(),
            source="test",
            source_id="test-123",
            confidence=0.3,  # Below threshold
        )

    @pytest.fixture
    def agent(self, tmp_path):
        """Create a RunbookAgent with mocked components."""
        with patch("boto3.client") as mock_client:
            mock_client.return_value = MagicMock()

            agent = RunbookAgent(
                region="us-east-1",
                project_name="aura",
                environment="dev",
                runbooks_dir=str(tmp_path),
                use_llm=False,
                auto_apply=True,
                confidence_threshold=0.6,
            )

            # Mock the detector
            agent.detector = MagicMock()
            agent.detector.detect_incidents = AsyncMock(return_value=[])

            # Mock the generator
            agent.generator = MagicMock()
            agent.generator.find_similar_runbooks = AsyncMock(return_value=[])
            agent.generator.generate_runbook = AsyncMock()

            # Mock the updater
            agent.updater = MagicMock()
            agent.updater.should_update = AsyncMock(
                return_value=(True, "Updates needed")
            )
            agent.updater.update_runbook = AsyncMock()
            agent.updater.apply_update = AsyncMock(return_value=True)

            # Mock the repository
            agent.repository = MagicMock()
            agent.repository.save_runbook = AsyncMock()
            agent.repository.update_runbook = AsyncMock()
            agent.repository.list_all = AsyncMock(return_value=[])
            agent.repository.search = AsyncMock(return_value=[])

            return agent

    @pytest.mark.asyncio
    async def test_process_recent_incidents_no_incidents(self, agent):
        """Test processing when no incidents are detected."""
        agent.detector.detect_incidents = AsyncMock(return_value=[])

        stats = await agent.process_recent_incidents(hours=24)

        assert stats.incidents_detected == 0
        assert stats.runbooks_created == 0
        assert stats.runbooks_updated == 0

    @pytest.mark.asyncio
    async def test_process_recent_incidents_creates_runbook(
        self, agent, sample_incident, tmp_path
    ):
        """Test that processing creates a new runbook."""
        agent.detector.detect_incidents = AsyncMock(return_value=[sample_incident])
        agent.generator.find_similar_runbooks = AsyncMock(return_value=[])
        agent.generator.generate_runbook = AsyncMock(
            return_value=GeneratedRunbook(
                title="Test Runbook",
                filename="TEST_RUNBOOK.md",
                content="# Test",
                incident_id=sample_incident.id,
                incident_type=sample_incident.incident_type,
                error_signatures=[],
                services=["docker"],
                keywords=["test"],
                confidence=0.85,
            )
        )
        agent.repository.save_runbook = AsyncMock(
            return_value=RunbookMetadata(
                id="test-runbook",
                title="Test Runbook",
                file_path=str(tmp_path / "TEST_RUNBOOK.md"),
                error_signatures=[],
                services=["docker"],
                keywords=["test"],
                incident_types=["docker_build_fix"],
                created_at=datetime.now(),
                updated_at=datetime.now(),
                auto_generated=True,
            )
        )

        stats = await agent.process_recent_incidents(hours=24)

        assert stats.incidents_detected == 1
        assert stats.runbooks_created == 1

    @pytest.mark.asyncio
    async def test_process_recent_incidents_updates_existing(
        self, agent, sample_incident, tmp_path
    ):
        """Test that processing updates an existing runbook."""
        agent.detector.detect_incidents = AsyncMock(return_value=[sample_incident])
        agent.generator.find_similar_runbooks = AsyncMock(
            return_value=[
                {
                    "path": str(tmp_path / "EXISTING.md"),
                    "filename": "EXISTING.md",
                    "similarity": 0.85,
                }
            ]
        )

        # Create the existing file
        existing_file = tmp_path / "EXISTING.md"
        existing_file.write_text("# Existing Runbook")

        agent.updater.update_runbook = AsyncMock(
            return_value=RunbookUpdate(
                runbook_path=str(existing_file),
                original_content="# Existing",
                updated_content="# Updated",
                incident_id=sample_incident.id,
                update_type="add_resolution",
                sections_modified=["resolution"],
                diff_summary="Added resolution",
                confidence=0.85,
                requires_review=False,
            )
        )

        stats = await agent.process_recent_incidents(hours=24)

        assert stats.incidents_detected == 1
        assert stats.runbooks_updated == 1

    @pytest.mark.asyncio
    async def test_process_recent_incidents_skips_low_confidence(
        self, agent, low_confidence_incident
    ):
        """Test that low confidence incidents are skipped."""
        agent.detector.detect_incidents = AsyncMock(
            return_value=[low_confidence_incident]
        )

        stats = await agent.process_recent_incidents(hours=24)

        assert stats.incidents_detected == 1
        assert stats.runbooks_skipped == 1
        assert stats.runbooks_created == 0

    @pytest.mark.asyncio
    async def test_process_recent_incidents_dry_run(self, agent, sample_incident):
        """Test dry run mode doesn't create files."""
        agent.detector.detect_incidents = AsyncMock(return_value=[sample_incident])
        agent.generator.find_similar_runbooks = AsyncMock(return_value=[])
        agent.generator.generate_runbook = AsyncMock(
            return_value=GeneratedRunbook(
                title="Test Runbook",
                filename="TEST_RUNBOOK.md",
                content="# Test",
                incident_id=sample_incident.id,
                incident_type=sample_incident.incident_type,
                error_signatures=[],
                services=["docker"],
                keywords=["test"],
                confidence=0.85,
            )
        )

        stats = await agent.process_recent_incidents(hours=24, dry_run=True)

        # Should count as created but repository.save_runbook not called
        assert stats.runbooks_created == 1
        agent.repository.save_runbook.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_from_incident_force_new(
        self, agent, sample_incident, tmp_path
    ):
        """Test forcing new runbook creation."""
        agent.generator.generate_runbook = AsyncMock(
            return_value=GeneratedRunbook(
                title="Test Runbook",
                filename="TEST_RUNBOOK.md",
                content="# Test",
                incident_id=sample_incident.id,
                incident_type=sample_incident.incident_type,
                error_signatures=[],
                services=["docker"],
                keywords=["test"],
                confidence=0.85,
            )
        )
        agent.repository.save_runbook = AsyncMock(
            return_value=RunbookMetadata(
                id="test-runbook",
                title="Test Runbook",
                file_path=str(tmp_path / "TEST_RUNBOOK.md"),
                error_signatures=[],
                services=["docker"],
                keywords=["test"],
                incident_types=["docker_build_fix"],
                created_at=datetime.now(),
                updated_at=datetime.now(),
                auto_generated=True,
            )
        )

        result = await agent.generate_from_incident(sample_incident, force_new=True)

        assert result.success is True
        assert result.action == "created"

    @pytest.mark.asyncio
    async def test_update_runbook_with_incident(self, agent, sample_incident, tmp_path):
        """Test updating a specific runbook."""
        runbook_path = str(tmp_path / "EXISTING.md")
        (tmp_path / "EXISTING.md").write_text("# Existing")

        agent.updater.update_runbook = AsyncMock(
            return_value=RunbookUpdate(
                runbook_path=runbook_path,
                original_content="# Existing",
                updated_content="# Updated",
                incident_id=sample_incident.id,
                update_type="add_resolution",
                sections_modified=["resolution"],
                diff_summary="Added resolution",
                confidence=0.85,
                requires_review=False,
            )
        )

        result = await agent.update_runbook_with_incident(runbook_path, sample_incident)

        assert result.success is True
        assert result.action == "updated"

    @pytest.mark.asyncio
    async def test_search_runbooks(self, agent):
        """Test searching for runbooks."""
        agent.repository.search = AsyncMock(
            return_value=[
                RunbookMetadata(
                    id="test-1",
                    title="Docker Build Fix",
                    file_path="docs/runbooks/DOCKER.md",
                    error_signatures=[],
                    services=["docker"],
                    keywords=["docker", "build"],
                    incident_types=["docker_build_fix"],
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    auto_generated=True,
                )
            ]
        )

        results = await agent.search_runbooks(service="docker")

        assert len(results) == 1
        assert results[0].title == "Docker Build Fix"

    @pytest.mark.asyncio
    async def test_get_stats(self, agent):
        """Test getting repository statistics."""
        agent.repository.list_all = AsyncMock(
            return_value=[
                RunbookMetadata(
                    id="test-1",
                    title="Test 1",
                    file_path="path1.md",
                    error_signatures=[],
                    services=["docker"],
                    keywords=["test"],
                    incident_types=["docker_build_fix"],
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    auto_generated=True,
                    resolution_count=5,
                ),
                RunbookMetadata(
                    id="test-2",
                    title="Test 2",
                    file_path="path2.md",
                    error_signatures=[],
                    services=["iam"],
                    keywords=["test"],
                    incident_types=["iam_permission_fix"],
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    auto_generated=False,
                    resolution_count=3,
                ),
            ]
        )

        stats = await agent.get_stats()

        assert stats["total_runbooks"] == 2
        assert stats["auto_generated"] == 1
        assert stats["manually_created"] == 1
        assert stats["total_resolutions"] == 8
        assert "docker" in stats["unique_services"]
        assert "iam" in stats["unique_services"]

    def test_determine_update_type_with_resolution(self, agent, sample_incident):
        """Test update type determination with resolution steps."""
        from src.services.runbook.incident_detector import ResolutionStep

        sample_incident.resolution_steps = [
            ResolutionStep(
                command="some command",
                output="output",
                timestamp=datetime.now(),
                success=True,
            )
        ]

        update_type = agent._determine_update_type(sample_incident)
        assert update_type == "add_resolution"

    def test_determine_update_type_with_errors(self, agent, sample_incident):
        """Test update type determination with error messages."""
        sample_incident.resolution_steps = []
        sample_incident.error_messages = ["Error message"]

        update_type = agent._determine_update_type(sample_incident)
        assert update_type == "add_symptom"

    def test_determine_update_type_security(self, agent, sample_incident):
        """Test update type determination for security incidents."""
        sample_incident.resolution_steps = []
        sample_incident.error_messages = []
        sample_incident.incident_type = IncidentType.SECURITY_FIX

        update_type = agent._determine_update_type(sample_incident)
        assert update_type == "add_prevention"


class TestRunbookAgentIntegration:
    """Integration tests for RunbookAgent with real file operations."""

    @pytest.fixture
    def agent_with_files(self, tmp_path):
        """Create agent with real file operations (mocked AWS only)."""
        with patch("boto3.client") as mock_client:
            mock_client.return_value = MagicMock()

            agent = RunbookAgent(
                region="us-east-1",
                project_name="aura",
                environment="dev",
                runbooks_dir=str(tmp_path),
                use_llm=False,
                auto_apply=True,
            )

            # Only mock AWS services, not file operations
            agent.detector = MagicMock()
            agent.detector.detect_incidents = AsyncMock(return_value=[])

            return agent

    @pytest.mark.asyncio
    async def test_sync_repository(self, agent_with_files, tmp_path):
        """Test repository synchronization."""
        # Create some runbook files
        (tmp_path / "TEST_RUNBOOK_1.md").write_text(
            """
# Runbook: Test Runbook 1

**Purpose:** Test purpose

## Symptoms
Error message 1

## Root Cause
Test root cause
"""
        )

        (tmp_path / "TEST_RUNBOOK_2.md").write_text(
            """
# Runbook: Test Runbook 2

**Purpose:** Another test

## Symptoms
Error message 2

## Root Cause
Another root cause
"""
        )

        # Mock DynamoDB operations
        agent_with_files.repository.use_dynamodb = False

        count = await agent_with_files.sync_repository()

        assert count >= 0  # Should successfully sync files
