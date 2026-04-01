"""
Tests for the Runbook Updater Service.

Tests runbook updates with new knowledge from incidents.
"""

import json
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
from pathlib import Path
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from src.services.runbook.incident_detector import (
    ErrorSignature,
    Incident,
    IncidentType,
    ResolutionStep,
)
from src.services.runbook.runbook_updater import RunbookUpdate, RunbookUpdater

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_bedrock_client():
    """Mock Bedrock client."""
    client = MagicMock()
    response_body = MagicMock()
    response_body.read.return_value = json.dumps(
        {
            "content": [
                {"text": "# Enhanced Runbook\n\n## Symptoms\n\nEnhanced symptoms."}
            ]
        }
    )
    client.invoke_model.return_value = {"body": response_body}
    return client


@pytest.fixture
def temp_runbooks_dir():
    """Create temporary runbooks directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def updater(mock_bedrock_client, temp_runbooks_dir):
    """Create RunbookUpdater with mocked dependencies."""
    with patch("boto3.client") as mock_boto:
        mock_boto.return_value = mock_bedrock_client

        upd = RunbookUpdater(
            region="us-east-1",
            use_llm=True,
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            runbooks_dir=temp_runbooks_dir,
        )
        upd.bedrock_client = mock_bedrock_client

        return upd


@pytest.fixture
def updater_no_llm(temp_runbooks_dir):
    """Create RunbookUpdater without LLM."""
    upd = RunbookUpdater(
        region="us-east-1",
        use_llm=False,
        runbooks_dir=temp_runbooks_dir,
    )
    return upd


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
                description="Build with platform flag",
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
def sample_runbook_content():
    """Sample runbook content."""
    return """# Runbook: Docker Build Fix

**Purpose:** Fix docker build issues

**Audience:** DevOps Engineers

**Estimated Time:** 15-30 minutes

**Last Updated:** Dec 01, 2025

---

## Problem Description

Docker builds failing in CodeBuild.

---

## Symptoms

```
Container failed to start
```

### Root Cause

Platform mismatch.

---

## Quick Resolution

Use platform flag.

---

## Detailed Diagnostic Steps

### Step 1: Check logs

Review CodeBuild logs.

---

## Resolution Procedures

### Procedure 1: Fix platform

Use --platform flag.

---

## Prevention

- Check platform compatibility
- Use multi-arch images

---

## Related Documentation

- [Docker docs](https://docs.docker.com)

---

## Appendix

### Incident Metadata

| Field | Value |
|-------|-------|
| Type | docker_build_fix |
"""


@pytest.fixture
def sample_runbook_path(temp_runbooks_dir, sample_runbook_content):
    """Create sample runbook file."""
    path = Path(temp_runbooks_dir) / "DOCKER_BUILD_FIX.md"
    path.write_text(sample_runbook_content)
    return str(path)


# =============================================================================
# RunbookUpdate Tests
# =============================================================================


class TestRunbookUpdate:
    """Tests for RunbookUpdate dataclass."""

    def test_create_runbook_update(self):
        """Test creating a runbook update."""
        update = RunbookUpdate(
            runbook_path="docs/runbooks/TEST.md",
            original_content="# Original",
            updated_content="# Updated",
            incident_id="test-123",
            update_type="add_resolution",
            sections_modified=["resolution_procedures"],
            diff_summary="Added resolution steps",
            confidence=0.8,
            requires_review=False,
        )

        assert update.runbook_path == "docs/runbooks/TEST.md"
        assert update.update_type == "add_resolution"
        assert update.requires_review is False

    def test_has_significant_changes_true(self):
        """Test has_significant_changes when true."""
        update = RunbookUpdate(
            runbook_path="test.md",
            original_content="",
            updated_content="",
            incident_id="123",
            update_type="enhance",
            sections_modified=["a", "b", "c"],
            diff_summary="",
            confidence=0.8,
            requires_review=False,
        )

        assert update.has_significant_changes is True

    def test_has_significant_changes_false(self):
        """Test has_significant_changes when false."""
        update = RunbookUpdate(
            runbook_path="test.md",
            original_content="",
            updated_content="",
            incident_id="123",
            update_type="add_symptom",
            sections_modified=["symptoms"],
            diff_summary="",
            confidence=0.8,
            requires_review=False,
        )

        assert update.has_significant_changes is False

    def test_default_metadata(self):
        """Test default metadata."""
        update = RunbookUpdate(
            runbook_path="test.md",
            original_content="",
            updated_content="",
            incident_id="123",
            update_type="add_resolution",
            sections_modified=[],
            diff_summary="",
            confidence=0.5,
            requires_review=True,
        )

        assert update.metadata == {}


# =============================================================================
# RunbookUpdater Tests
# =============================================================================


class TestRunbookUpdater:
    """Tests for RunbookUpdater class."""

    def test_init_with_llm(self, updater):
        """Test initialization with LLM enabled."""
        assert updater.use_llm is True
        assert updater.bedrock_client is not None

    def test_init_without_llm(self, updater_no_llm):
        """Test initialization without LLM."""
        assert updater_no_llm.use_llm is False

    def test_section_patterns_defined(self, updater):
        """Test section patterns are defined."""
        assert "symptoms" in updater.SECTION_PATTERNS
        assert "resolution_procedures" in updater.SECTION_PATTERNS
        assert "prevention" in updater.SECTION_PATTERNS


class TestUpdateRunbook:
    """Tests for update_runbook method."""

    @pytest.mark.asyncio
    async def test_update_runbook_file_not_found(self, updater_no_llm, sample_incident):
        """Test update with non-existent file."""
        with pytest.raises(FileNotFoundError):
            await updater_no_llm.update_runbook("nonexistent.md", sample_incident)

    @pytest.mark.asyncio
    async def test_update_runbook_add_resolution(
        self, updater_no_llm, sample_incident, sample_runbook_path
    ):
        """Test adding resolution to runbook."""
        update = await updater_no_llm.update_runbook(
            sample_runbook_path, sample_incident, update_type="add_resolution"
        )

        assert update.update_type == "add_resolution"
        assert "resolution_procedures" in update.sections_modified
        assert update.incident_id == sample_incident.id

    @pytest.mark.asyncio
    async def test_update_runbook_add_symptom(
        self, updater_no_llm, sample_incident, sample_runbook_path
    ):
        """Test adding symptom to runbook."""
        update = await updater_no_llm.update_runbook(
            sample_runbook_path, sample_incident, update_type="add_symptom"
        )

        assert update.update_type == "add_symptom"

    @pytest.mark.asyncio
    async def test_update_runbook_add_prevention(
        self, updater_no_llm, sample_incident, sample_runbook_path
    ):
        """Test adding prevention to runbook."""
        update = await updater_no_llm.update_runbook(
            sample_runbook_path, sample_incident, update_type="add_prevention"
        )

        assert update.update_type == "add_prevention"

    @pytest.mark.asyncio
    async def test_update_runbook_enhance_with_llm(
        self, updater, sample_incident, sample_runbook_path, mock_bedrock_client
    ):
        """Test enhancing runbook with LLM."""
        update = await updater.update_runbook(
            sample_runbook_path, sample_incident, update_type="enhance"
        )

        mock_bedrock_client.invoke_model.assert_called_once()
        assert update.update_type == "enhance"

    @pytest.mark.asyncio
    async def test_update_runbook_invalid_type(
        self, updater_no_llm, sample_incident, sample_runbook_path
    ):
        """Test update with invalid update type."""
        with pytest.raises(ValueError):
            await updater_no_llm.update_runbook(
                sample_runbook_path, sample_incident, update_type="invalid_type"
            )

    @pytest.mark.asyncio
    async def test_update_runbook_requires_review_low_confidence(
        self, updater_no_llm, sample_incident, sample_runbook_path
    ):
        """Test update requires review for low confidence."""
        sample_incident.confidence = 0.3  # Below threshold

        update = await updater_no_llm.update_runbook(
            sample_runbook_path, sample_incident, update_type="add_resolution"
        )

        assert update.requires_review is True

    @pytest.mark.asyncio
    async def test_update_runbook_updates_date(
        self, updater_no_llm, sample_incident, sample_runbook_path
    ):
        """Test update modifies Last Updated date."""
        update = await updater_no_llm.update_runbook(
            sample_runbook_path, sample_incident
        )

        today = datetime.now().strftime("%b %d, %Y")
        assert today in update.updated_content


class TestParseRunbookSections:
    """Tests for _parse_runbook_sections method."""

    def test_parse_sections(self, updater_no_llm, sample_runbook_content):
        """Test parsing runbook sections."""
        sections = updater_no_llm._parse_runbook_sections(sample_runbook_content)

        assert "symptoms" in sections
        assert "quick_resolution" in sections
        assert "prevention" in sections

    def test_parse_sections_empty_content(self, updater_no_llm):
        """Test parsing empty content."""
        sections = updater_no_llm._parse_runbook_sections("")
        assert sections == {}

    def test_parse_sections_no_matching_headers(self, updater_no_llm):
        """Test parsing content without matching headers."""
        content = "# Random Title\n\nSome content without standard sections."
        sections = updater_no_llm._parse_runbook_sections(content)
        assert len(sections) == 0


class TestAnalyzeUpdateNeeds:
    """Tests for _analyze_update_needs method."""

    def test_analyze_needs_new_symptom(
        self, updater_no_llm, sample_incident, sample_runbook_content
    ):
        """Test detecting new symptom need."""
        sections = updater_no_llm._parse_runbook_sections(sample_runbook_content)

        needs = updater_no_llm._analyze_update_needs(sections, sample_incident)

        assert "new_symptom" in needs

    def test_analyze_needs_new_resolution(
        self, updater_no_llm, sample_incident, sample_runbook_content
    ):
        """Test detecting new resolution need."""
        sections = updater_no_llm._parse_runbook_sections(sample_runbook_content)

        needs = updater_no_llm._analyze_update_needs(sections, sample_incident)

        assert "new_resolution" in needs

    def test_analyze_needs_no_updates(self, updater_no_llm, sample_incident):
        """Test when no updates needed."""
        sample_incident.error_messages = []
        sample_incident.resolution_steps = []
        sample_incident.root_cause = ""

        sections = {"symptoms": "", "quick_resolution": "", "root_cause": ""}
        needs = updater_no_llm._analyze_update_needs(sections, sample_incident)

        assert len(needs) == 0


class TestAddResolution:
    """Tests for _add_resolution method."""

    @pytest.mark.asyncio
    async def test_add_resolution_existing_section(
        self, updater_no_llm, sample_incident, sample_runbook_content
    ):
        """Test adding resolution to existing section."""
        sections = updater_no_llm._parse_runbook_sections(sample_runbook_content)

        content, modified = await updater_no_llm._add_resolution(
            sample_runbook_content, sections, sample_incident
        )

        assert "resolution_procedures" in modified
        assert "Alternative Resolution" in content

    @pytest.mark.asyncio
    async def test_add_resolution_new_section(self, updater_no_llm, sample_incident):
        """Test adding resolution to runbook without resolution section."""
        content = "# Simple Runbook\n\n## Problem\n\nDescription."
        sections = {}

        updated, modified = await updater_no_llm._add_resolution(
            content, sections, sample_incident
        )

        assert "resolution_procedures" in modified
        assert "Resolution Procedures" in updated


class TestAddSymptom:
    """Tests for _add_symptom method."""

    @pytest.mark.asyncio
    async def test_add_symptom_with_errors(
        self, updater_no_llm, sample_incident, sample_runbook_content
    ):
        """Test adding symptoms with error messages."""
        sections = updater_no_llm._parse_runbook_sections(sample_runbook_content)

        content, modified = await updater_no_llm._add_symptom(
            sample_runbook_content, sections, sample_incident
        )

        assert "symptoms" in modified
        assert "Additional symptoms" in content

    @pytest.mark.asyncio
    async def test_add_symptom_no_errors(
        self, updater_no_llm, sample_incident, sample_runbook_content
    ):
        """Test adding symptoms when no error messages."""
        sample_incident.error_messages = []
        sections = updater_no_llm._parse_runbook_sections(sample_runbook_content)

        content, modified = await updater_no_llm._add_symptom(
            sample_runbook_content, sections, sample_incident
        )

        assert len(modified) == 0


class TestAddPrevention:
    """Tests for _add_prevention method."""

    @pytest.mark.asyncio
    async def test_add_prevention(
        self, updater_no_llm, sample_incident, sample_runbook_content
    ):
        """Test adding prevention measures."""
        sections = updater_no_llm._parse_runbook_sections(sample_runbook_content)

        content, modified = await updater_no_llm._add_prevention(
            sample_runbook_content, sections, sample_incident
        )

        assert "prevention" in modified
        assert "Additional Prevention" in content


class TestEnhanceRunbook:
    """Tests for _enhance_runbook method."""

    @pytest.mark.asyncio
    async def test_enhance_runbook_with_llm(
        self, updater, sample_incident, sample_runbook_content, mock_bedrock_client
    ):
        """Test enhancing runbook with LLM."""
        content, modified = await updater._enhance_runbook(
            sample_runbook_content, sample_incident
        )

        mock_bedrock_client.invoke_model.assert_called_once()
        assert "Enhanced" in content

    @pytest.mark.asyncio
    async def test_enhance_runbook_without_llm(
        self, updater_no_llm, sample_incident, sample_runbook_content
    ):
        """Test enhancing without LLM returns original."""
        content, modified = await updater_no_llm._enhance_runbook(
            sample_runbook_content, sample_incident
        )

        assert content == sample_runbook_content
        assert modified == []

    @pytest.mark.asyncio
    async def test_enhance_runbook_llm_error(
        self, updater, sample_incident, sample_runbook_content, mock_bedrock_client
    ):
        """Test enhancing handles LLM errors."""
        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ServiceError", "Message": "Error"}},
            "InvokeModel",
        )

        content, modified = await updater._enhance_runbook(
            sample_runbook_content, sample_incident
        )

        assert content == sample_runbook_content
        assert modified == []


class TestHelperMethods:
    """Tests for helper methods."""

    def test_find_section_end(self, updater_no_llm):
        """Test finding section end."""
        content = "## Section 1\n\nContent here.\n\n## Section 2\n\nMore content."

        end = updater_no_llm._find_section_end(content, 12)

        # The method returns position before the newline preceding next ##
        assert "## Section 2" in content[end:]

    def test_find_section_end_at_eof(self, updater_no_llm):
        """Test finding section end at EOF."""
        content = "## Section 1\n\nContent here."

        end = updater_no_llm._find_section_end(content, 12)

        assert end == len(content)

    def test_add_section(self, updater_no_llm):
        """Test adding a new section."""
        content = "# Title\n\n## Related Documentation\n\nDocs here."

        result = updater_no_llm._add_section(content, "New Section", "New content.")

        assert "## New Section" in result
        assert result.index("New Section") < result.index("Related Documentation")

    def test_format_new_resolution_with_steps(self, updater_no_llm, sample_incident):
        """Test formatting resolution with steps."""
        result = updater_no_llm._format_new_resolution(sample_incident)

        assert "Step 1" in result
        assert "docker build" in result

    def test_format_new_resolution_without_steps(self, updater_no_llm, sample_incident):
        """Test formatting resolution without steps."""
        sample_incident.resolution_steps = []

        result = updater_no_llm._format_new_resolution(sample_incident)

        assert sample_incident.id in result
        assert sample_incident.root_cause in result

    def test_update_metadata(self, updater_no_llm, sample_runbook_content):
        """Test updating metadata date."""
        result = updater_no_llm._update_metadata(sample_runbook_content)

        today = datetime.now().strftime("%b %d, %Y")
        assert today in result
        assert "Dec 01, 2025" not in result  # Old date replaced

    def test_generate_diff_summary(self, updater_no_llm):
        """Test generating diff summary."""
        original = "Line 1\nLine 2"
        updated = "Line 1\nLine 2\nLine 3\nLine 4"
        modified = ["symptoms", "resolution_procedures"]

        summary = updater_no_llm._generate_diff_summary(original, updated, modified)

        assert "symptoms" in summary
        assert "resolution_procedures" in summary
        assert "Lines added" in summary

    def test_detect_modified_sections(self, updater_no_llm):
        """Test detecting modified sections."""
        original = (
            "## Symptoms\n\nOriginal symptoms.\n\n## Prevention\n\nOriginal prevention."
        )
        updated = (
            "## Symptoms\n\nModified symptoms.\n\n## Prevention\n\nOriginal prevention."
        )

        modified = updater_no_llm._detect_modified_sections(original, updated)

        assert "symptoms" in modified
        assert "prevention" not in modified


class TestApplyUpdate:
    """Tests for apply_update method."""

    @pytest.mark.asyncio
    async def test_apply_update_success(self, updater_no_llm, sample_runbook_path):
        """Test applying update successfully."""
        update = RunbookUpdate(
            runbook_path=sample_runbook_path,
            original_content="# Original",
            updated_content="# Updated",
            incident_id="test-123",
            update_type="add_resolution",
            sections_modified=["resolution_procedures"],
            diff_summary="Added steps",
            confidence=0.8,
            requires_review=False,
        )

        result = await updater_no_llm.apply_update(update)

        assert result is True
        assert Path(sample_runbook_path).read_text() == "# Updated"

    @pytest.mark.asyncio
    async def test_apply_update_creates_backup(
        self, updater_no_llm, sample_runbook_path
    ):
        """Test applying update creates backup."""
        update = RunbookUpdate(
            runbook_path=sample_runbook_path,
            original_content="# Original Content",
            updated_content="# Updated",
            incident_id="test-123",
            update_type="add_resolution",
            sections_modified=[],
            diff_summary="",
            confidence=0.8,
            requires_review=False,
        )

        await updater_no_llm.apply_update(update, backup=True)

        # Check backup was created
        backup_files = list(Path(sample_runbook_path).parent.glob("*.bak"))
        assert len(backup_files) > 0

    @pytest.mark.asyncio
    async def test_apply_update_no_backup(self, updater_no_llm, sample_runbook_path):
        """Test applying update without backup."""
        update = RunbookUpdate(
            runbook_path=sample_runbook_path,
            original_content="# Original",
            updated_content="# Updated",
            incident_id="test-123",
            update_type="add_resolution",
            sections_modified=[],
            diff_summary="",
            confidence=0.8,
            requires_review=False,
        )

        await updater_no_llm.apply_update(update, backup=False)

        backup_files = list(Path(sample_runbook_path).parent.glob("*.bak"))
        assert len(backup_files) == 0


class TestShouldUpdate:
    """Tests for should_update method."""

    @pytest.mark.asyncio
    async def test_should_update_file_not_found(self, updater_no_llm, sample_incident):
        """Test should_update with non-existent file."""
        should, reason = await updater_no_llm.should_update(
            "nonexistent.md", sample_incident
        )

        assert should is False
        assert "does not exist" in reason

    @pytest.mark.asyncio
    async def test_should_update_true(
        self, updater_no_llm, sample_incident, sample_runbook_path
    ):
        """Test should_update returns true when updates needed."""
        should, reason = await updater_no_llm.should_update(
            sample_runbook_path, sample_incident
        )

        assert should is True
        assert "Updates needed" in reason

    @pytest.mark.asyncio
    async def test_should_update_low_confidence(
        self, updater_no_llm, sample_incident, sample_runbook_path
    ):
        """Test should_update with low confidence incident."""
        sample_incident.confidence = 0.3

        should, reason = await updater_no_llm.should_update(
            sample_runbook_path, sample_incident
        )

        assert should is False
        assert "confidence too low" in reason

    @pytest.mark.asyncio
    async def test_should_update_no_new_info(
        self, updater_no_llm, sample_incident, sample_runbook_path
    ):
        """Test should_update when no new info to add."""
        sample_incident.error_messages = []
        sample_incident.resolution_steps = []
        sample_incident.root_cause = ""

        should, reason = await updater_no_llm.should_update(
            sample_runbook_path, sample_incident
        )

        assert should is False
        assert "No new information" in reason
