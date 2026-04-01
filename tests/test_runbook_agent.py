"""
Tests for the Runbook Agent Service.

Tests the main orchestrator that coordinates incident detection, runbook generation,
and runbook updates.
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
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from botocore.exceptions import ClientError

from src.services.runbook.incident_detector import (
    ErrorSignature,
    Incident,
    IncidentType,
    ResolutionStep,
)
from src.services.runbook.runbook_agent import (
    ProcessingStats,
    RunbookAgent,
    RunbookAgentResult,
)
from src.services.runbook.runbook_generator import GeneratedRunbook
from src.services.runbook.runbook_updater import RunbookUpdate

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_detector():
    """Mock IncidentDetector."""
    detector = MagicMock()
    detector.detect_incidents = AsyncMock(return_value=[])
    return detector


@pytest.fixture
def mock_generator():
    """Mock RunbookGenerator."""
    generator = MagicMock()
    generator.generate_runbook = AsyncMock()
    generator.find_similar_runbooks = AsyncMock(return_value=[])
    return generator


@pytest.fixture
def mock_updater():
    """Mock RunbookUpdater."""
    updater = MagicMock()
    updater.should_update = AsyncMock(return_value=(True, "Updates needed"))
    updater.update_runbook = AsyncMock()
    updater.apply_update = AsyncMock(return_value=True)
    return updater


@pytest.fixture
def mock_repository():
    """Mock RunbookRepository."""
    repository = MagicMock()
    repository.save_runbook = AsyncMock()
    repository.update_runbook = AsyncMock()
    repository.sync_index = AsyncMock(return_value=5)
    repository.search = AsyncMock(return_value=[])
    repository.find_by_error_signature = AsyncMock(return_value=[])
    repository.record_usage = AsyncMock()
    repository.list_all = AsyncMock(return_value=[])
    return repository


@pytest.fixture
def mock_eventbridge_client():
    """Mock EventBridge client."""
    return MagicMock()


@pytest.fixture
def temp_runbooks_dir():
    """Create temporary runbooks directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def agent(
    mock_detector,
    mock_generator,
    mock_updater,
    mock_repository,
    mock_eventbridge_client,
    temp_runbooks_dir,
):
    """Create RunbookAgent with mocked dependencies."""
    with patch("boto3.client") as mock_boto:
        mock_boto.return_value = mock_eventbridge_client

        agent = RunbookAgent(
            region="us-east-1",
            project_name="aura",
            environment="dev",
            runbooks_dir=temp_runbooks_dir,
            use_llm=False,
            auto_apply=False,
        )

        # Inject mocks
        agent.detector = mock_detector
        agent.generator = mock_generator
        agent.updater = mock_updater
        agent.repository = mock_repository
        agent.eventbridge_client = mock_eventbridge_client

        return agent


@pytest.fixture
def sample_error_signature():
    """Sample error signature."""
    return ErrorSignature(
        pattern=r"exec format error",
        service="docker",
        severity="high",
        keywords=["docker", "platform"],
    )


@pytest.fixture
def sample_incident(sample_error_signature):
    """Sample incident for testing."""
    return Incident(
        id="cb-test123",
        incident_type=IncidentType.DOCKER_BUILD_FIX,
        title="Docker Platform Issue",
        description="CodeBuild failed due to architecture mismatch",
        error_messages=["exec format error", "exit code 255"],
        error_signatures=[sample_error_signature],
        resolution_steps=[
            ResolutionStep(
                command="docker build --platform linux/amd64 .",
                output="Built successfully",
                timestamp=datetime.now(),
                success=True,
            )
        ],
        affected_services=["docker", "codebuild"],
        affected_resources=["aura-application-deploy-dev"],
        root_cause="Docker image architecture mismatch",
        start_time=datetime.now() - timedelta(hours=2),
        end_time=datetime.now(),
        source="codebuild",
        source_id="build-12345",
        confidence=0.85,
    )


@pytest.fixture
def sample_generated_runbook():
    """Sample generated runbook."""
    return GeneratedRunbook(
        title="Docker Platform Issue",
        filename="DOCKER_PLATFORM_ISSUE.md",
        content="# Docker Platform Issue\n\nContent here.",
        incident_id="cb-test123",
        incident_type=IncidentType.DOCKER_BUILD_FIX,
        error_signatures=["exec format error"],
        services=["docker"],
        keywords=["docker", "platform"],
        confidence=0.85,
    )


@pytest.fixture
def sample_runbook_update():
    """Sample runbook update."""
    return RunbookUpdate(
        runbook_path="docs/runbooks/DOCKER_FIX.md",
        original_content="# Original",
        updated_content="# Updated",
        incident_id="cb-test123",
        update_type="add_resolution",
        sections_modified=["resolution_procedures"],
        diff_summary="Added new resolution steps",
        confidence=0.85,
        requires_review=False,
    )


@pytest.fixture
def sample_runbook_metadata():
    """Sample runbook metadata."""
    metadata = MagicMock()
    metadata.id = "rb-123"
    metadata.file_path = "docs/runbooks/DOCKER_FIX.md"
    metadata.title = "Docker Fix"
    metadata.services = ["docker"]
    metadata.incident_types = ["docker_build_fix"]
    metadata.resolution_count = 5
    metadata.auto_generated = True
    return metadata


# =============================================================================
# RunbookAgentResult Tests
# =============================================================================


class TestRunbookAgentResult:
    """Tests for RunbookAgentResult dataclass."""

    def test_create_success_result(self):
        """Test creating a successful result."""
        result = RunbookAgentResult(
            success=True,
            action="created",
            runbook_path="docs/runbooks/TEST.md",
            incident_id="test-123",
            message="Created runbook successfully",
        )

        assert result.success is True
        assert result.action == "created"
        assert result.is_new_runbook is True

    def test_create_error_result(self):
        """Test creating an error result."""
        result = RunbookAgentResult(
            success=False,
            action="error",
            incident_id="test-123",
            message="Failed to create runbook",
        )

        assert result.success is False
        assert result.action == "error"
        assert result.is_new_runbook is False

    def test_is_new_runbook_updated(self):
        """Test is_new_runbook for updated action."""
        result = RunbookAgentResult(
            success=True,
            action="updated",
            runbook_path="docs/runbooks/TEST.md",
        )

        assert result.is_new_runbook is False

    def test_metadata_default(self):
        """Test default metadata."""
        result = RunbookAgentResult(success=True, action="skipped")
        assert result.metadata == {}


# =============================================================================
# ProcessingStats Tests
# =============================================================================


class TestProcessingStats:
    """Tests for ProcessingStats dataclass."""

    def test_create_stats(self):
        """Test creating processing stats."""
        stats = ProcessingStats(
            incidents_detected=10,
            runbooks_created=3,
            runbooks_updated=5,
            runbooks_skipped=2,
            errors=0,
            processing_time_seconds=15.5,
        )

        assert stats.incidents_detected == 10
        assert stats.runbooks_created == 3

    def test_to_dict(self):
        """Test converting stats to dictionary."""
        stats = ProcessingStats(
            incidents_detected=5,
            runbooks_created=2,
            runbooks_updated=1,
            runbooks_skipped=2,
            errors=0,
            processing_time_seconds=10.0,
        )

        result = stats.to_dict()

        assert result["incidents_detected"] == 5
        assert result["runbooks_created"] == 2
        assert result["processing_time_seconds"] == 10.0

    def test_default_values(self):
        """Test default values."""
        stats = ProcessingStats()

        assert stats.incidents_detected == 0
        assert stats.errors == 0
        assert stats.processing_time_seconds == 0.0


# =============================================================================
# RunbookAgent Tests
# =============================================================================


class TestRunbookAgent:
    """Tests for RunbookAgent class."""

    def test_init(self, agent):
        """Test agent initialization."""
        assert agent.region == "us-east-1"
        assert agent.project_name == "aura"
        assert agent.environment == "dev"
        assert agent.use_llm is False

    def test_default_thresholds(self, agent):
        """Test default threshold values."""
        assert agent.similarity_threshold == 0.7
        assert agent.confidence_threshold == 0.6


class TestProcessRecentIncidents:
    """Tests for process_recent_incidents method."""

    @pytest.mark.asyncio
    async def test_process_no_incidents(self, agent, mock_detector):
        """Test processing with no incidents."""
        mock_detector.detect_incidents.return_value = []

        stats = await agent.process_recent_incidents(hours=24)

        assert stats.incidents_detected == 0
        assert stats.runbooks_created == 0

    @pytest.mark.asyncio
    async def test_process_with_incidents(
        self,
        agent,
        mock_detector,
        mock_generator,
        sample_incident,
        sample_generated_runbook,
    ):
        """Test processing with incidents."""
        mock_detector.detect_incidents.return_value = [sample_incident]
        mock_generator.find_similar_runbooks.return_value = []
        mock_generator.generate_runbook.return_value = sample_generated_runbook

        stats = await agent.process_recent_incidents(hours=24, dry_run=True)

        assert stats.incidents_detected == 1

    @pytest.mark.asyncio
    async def test_process_skips_low_confidence(
        self, agent, mock_detector, sample_incident
    ):
        """Test processing skips low confidence incidents."""
        sample_incident.confidence = 0.3  # Below threshold
        mock_detector.detect_incidents.return_value = [sample_incident]

        stats = await agent.process_recent_incidents(hours=24)

        assert stats.runbooks_skipped == 1

    @pytest.mark.asyncio
    async def test_process_handles_detection_error(self, agent, mock_detector):
        """Test processing handles detection errors."""
        mock_detector.detect_incidents.side_effect = Exception("Detection error")

        stats = await agent.process_recent_incidents(hours=24)

        assert stats.errors == 1

    @pytest.mark.asyncio
    async def test_process_custom_sources(self, agent, mock_detector):
        """Test processing with custom sources."""
        mock_detector.detect_incidents.return_value = []

        await agent.process_recent_incidents(
            hours=24, sources=["codebuild", "cloudformation"]
        )

        mock_detector.detect_incidents.assert_called_with(
            hours=24, sources=["codebuild", "cloudformation"]
        )


class TestProcessIncident:
    """Tests for _process_incident method."""

    @pytest.mark.asyncio
    async def test_process_incident_new_runbook(
        self, agent, mock_generator, sample_incident, sample_generated_runbook
    ):
        """Test processing creates new runbook when no similar exists."""
        mock_generator.find_similar_runbooks.return_value = []
        mock_generator.generate_runbook.return_value = sample_generated_runbook

        result = await agent._process_incident(sample_incident, dry_run=True)

        assert result.action == "created"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_process_incident_update_existing(
        self,
        agent,
        mock_generator,
        mock_updater,
        sample_incident,
        sample_runbook_update,
    ):
        """Test processing updates existing runbook when similar found."""
        mock_generator.find_similar_runbooks.return_value = [
            {
                "path": "docs/runbooks/EXISTING.md",
                "filename": "EXISTING.md",
                "similarity": 0.9,
            }
        ]
        mock_updater.should_update.return_value = (True, "Updates needed")
        mock_updater.update_runbook.return_value = sample_runbook_update

        result = await agent._process_incident(sample_incident, dry_run=True)

        assert result.action == "updated"


class TestGenerateNewRunbook:
    """Tests for _generate_new_runbook method."""

    @pytest.mark.asyncio
    async def test_generate_new_runbook_dry_run(
        self, agent, mock_generator, sample_incident, sample_generated_runbook
    ):
        """Test generating new runbook in dry run mode."""
        mock_generator.generate_runbook.return_value = sample_generated_runbook

        result = await agent._generate_new_runbook(sample_incident, dry_run=True)

        assert result.success is True
        assert result.action == "created"
        assert "[DRY RUN]" in result.message

    @pytest.mark.asyncio
    async def test_generate_new_runbook_save(
        self,
        agent,
        mock_generator,
        mock_repository,
        sample_incident,
        sample_generated_runbook,
        sample_runbook_metadata,
    ):
        """Test generating and saving new runbook."""
        mock_generator.generate_runbook.return_value = sample_generated_runbook
        mock_repository.save_runbook.return_value = sample_runbook_metadata

        result = await agent._generate_new_runbook(sample_incident, dry_run=False)

        assert result.success is True
        assert result.action == "created"
        mock_repository.save_runbook.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_new_runbook_error(
        self, agent, mock_generator, sample_incident
    ):
        """Test generating runbook handles errors."""
        mock_generator.generate_runbook.side_effect = Exception("Generation error")

        result = await agent._generate_new_runbook(sample_incident)

        assert result.success is False
        assert result.action == "error"


class TestUpdateExistingRunbook:
    """Tests for _update_existing_runbook method."""

    @pytest.mark.asyncio
    async def test_update_runbook_skipped(self, agent, mock_updater, sample_incident):
        """Test update skipped when not needed."""
        mock_updater.should_update.return_value = (False, "No new information")

        result = await agent._update_existing_runbook(
            "docs/runbooks/TEST.md", sample_incident
        )

        assert result.action == "skipped"

    @pytest.mark.asyncio
    async def test_update_runbook_dry_run(
        self, agent, mock_updater, sample_incident, sample_runbook_update
    ):
        """Test update in dry run mode."""
        mock_updater.should_update.return_value = (True, "Updates needed")
        mock_updater.update_runbook.return_value = sample_runbook_update

        result = await agent._update_existing_runbook(
            "docs/runbooks/TEST.md", sample_incident, dry_run=True
        )

        assert result.action == "updated"
        assert "[DRY RUN]" in result.message

    @pytest.mark.asyncio
    async def test_update_runbook_auto_apply(
        self,
        agent,
        mock_updater,
        mock_repository,
        sample_incident,
        sample_runbook_update,
    ):
        """Test update with auto_apply enabled."""
        agent.auto_apply = True
        mock_updater.should_update.return_value = (True, "Updates needed")
        mock_updater.update_runbook.return_value = sample_runbook_update
        mock_updater.apply_update.return_value = True

        result = await agent._update_existing_runbook(
            "docs/runbooks/TEST.md", sample_incident
        )

        assert result.success is True
        assert result.action == "updated"
        mock_updater.apply_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_runbook_requires_review(
        self, agent, mock_updater, sample_incident, sample_runbook_update
    ):
        """Test update that requires review."""
        sample_runbook_update.requires_review = True
        mock_updater.should_update.return_value = (True, "Updates needed")
        mock_updater.update_runbook.return_value = sample_runbook_update

        result = await agent._update_existing_runbook(
            "docs/runbooks/TEST.md", sample_incident
        )

        assert result.action == "pending_review"

    @pytest.mark.asyncio
    async def test_update_runbook_apply_failed(
        self, agent, mock_updater, sample_incident, sample_runbook_update
    ):
        """Test update when apply fails."""
        agent.auto_apply = True
        mock_updater.should_update.return_value = (True, "Updates needed")
        mock_updater.update_runbook.return_value = sample_runbook_update
        mock_updater.apply_update.return_value = False

        result = await agent._update_existing_runbook(
            "docs/runbooks/TEST.md", sample_incident
        )

        assert result.success is False
        assert result.action == "error"


class TestDetermineUpdateType:
    """Tests for _determine_update_type method."""

    def test_determine_update_type_resolution(self, agent, sample_incident):
        """Test determining update type for resolution steps."""
        update_type = agent._determine_update_type(sample_incident)
        assert update_type == "add_resolution"

    def test_determine_update_type_symptom(self, agent, sample_incident):
        """Test determining update type for symptoms."""
        sample_incident.resolution_steps = []
        update_type = agent._determine_update_type(sample_incident)
        assert update_type == "add_symptom"

    def test_determine_update_type_prevention(self, agent, sample_incident):
        """Test determining update type for security fixes."""
        sample_incident.resolution_steps = []
        sample_incident.error_messages = []
        sample_incident.incident_type = IncidentType.SECURITY_FIX
        update_type = agent._determine_update_type(sample_incident)
        assert update_type == "add_prevention"

    def test_determine_update_type_enhance(self, agent, sample_incident):
        """Test determining update type defaults to enhance."""
        sample_incident.resolution_steps = []
        sample_incident.error_messages = []
        sample_incident.incident_type = IncidentType.GENERAL_BUG_FIX
        update_type = agent._determine_update_type(sample_incident)
        assert update_type == "enhance"


class TestAgentPublicMethods:
    """Tests for public agent methods."""

    @pytest.mark.asyncio
    async def test_generate_from_incident(
        self, agent, mock_generator, sample_incident, sample_generated_runbook
    ):
        """Test generate_from_incident method."""
        mock_generator.find_similar_runbooks.return_value = []
        mock_generator.generate_runbook.return_value = sample_generated_runbook

        result = await agent.generate_from_incident(sample_incident, force_new=False)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_generate_from_incident_force_new(
        self, agent, mock_generator, sample_incident, sample_generated_runbook
    ):
        """Test generate_from_incident with force_new."""
        mock_generator.generate_runbook.return_value = sample_generated_runbook

        _result = await agent.generate_from_incident(sample_incident, force_new=True)

        mock_generator.find_similar_runbooks.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_runbook_with_incident(
        self, agent, mock_updater, sample_incident, sample_runbook_update
    ):
        """Test update_runbook_with_incident method."""
        mock_updater.should_update.return_value = (True, "Updates needed")
        mock_updater.update_runbook.return_value = sample_runbook_update

        result = await agent.update_runbook_with_incident(
            "docs/runbooks/TEST.md", sample_incident
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_sync_repository(self, agent, mock_repository):
        """Test sync_repository method."""
        mock_repository.sync_index.return_value = 10

        count = await agent.sync_repository()

        assert count == 10
        mock_repository.sync_index.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_runbooks(self, agent, mock_repository):
        """Test search_runbooks method."""
        await agent.search_runbooks(service="docker", keyword="platform")

        mock_repository.search.assert_called_with(
            error_pattern=None,
            service="docker",
            keyword="platform",
            incident_type=None,
        )

    @pytest.mark.asyncio
    async def test_find_runbook_for_error(
        self, agent, mock_repository, sample_runbook_metadata
    ):
        """Test find_runbook_for_error method."""
        mock_repository.find_by_error_signature.return_value = [
            (sample_runbook_metadata, 0.9)
        ]

        result = await agent.find_runbook_for_error("exec format error")

        assert result is not None
        assert result[1] == 0.9

    @pytest.mark.asyncio
    async def test_find_runbook_for_error_no_match(self, agent, mock_repository):
        """Test find_runbook_for_error with no match."""
        mock_repository.find_by_error_signature.return_value = []

        result = await agent.find_runbook_for_error("unknown error")

        assert result is None

    @pytest.mark.asyncio
    async def test_record_resolution(self, agent, mock_repository):
        """Test record_resolution method."""
        await agent.record_resolution("rb-123", 15.5)

        mock_repository.record_usage.assert_called_with("rb-123", 15.5)


class TestEventBridgeSetup:
    """Tests for EventBridge setup."""

    @pytest.mark.asyncio
    async def test_setup_automated_trigger(self, agent, mock_eventbridge_client):
        """Test setting up automated trigger."""
        mock_eventbridge_client.put_rule.return_value = {
            "RuleArn": "arn:aws:events:us-east-1:123:rule/test"
        }

        arn = await agent.setup_automated_trigger()

        assert "arn:aws" in arn
        mock_eventbridge_client.put_rule.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_automated_trigger_disabled(
        self, agent, mock_eventbridge_client
    ):
        """Test setting up disabled trigger."""
        mock_eventbridge_client.put_rule.return_value = {"RuleArn": "arn:test"}

        await agent.setup_automated_trigger(enabled=False)

        call_kwargs = mock_eventbridge_client.put_rule.call_args.kwargs
        assert call_kwargs["State"] == "DISABLED"

    @pytest.mark.asyncio
    async def test_setup_automated_trigger_error(self, agent, mock_eventbridge_client):
        """Test setup handles errors."""
        mock_eventbridge_client.put_rule.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "No access"}},
            "PutRule",
        )

        with pytest.raises(ClientError):
            await agent.setup_automated_trigger()


class TestGetStats:
    """Tests for get_stats method."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, agent, mock_repository):
        """Test get_stats with empty repository."""
        mock_repository.list_all.return_value = []

        stats = await agent.get_stats()

        assert stats["total_runbooks"] == 0
        assert stats["auto_generated"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_runbooks(
        self, agent, mock_repository, sample_runbook_metadata
    ):
        """Test get_stats with runbooks."""
        mock_repository.list_all.return_value = [
            sample_runbook_metadata,
            sample_runbook_metadata,
        ]

        stats = await agent.get_stats()

        assert stats["total_runbooks"] == 2
        assert stats["auto_generated"] == 2
        assert stats["total_resolutions"] == 10  # 5 per metadata
