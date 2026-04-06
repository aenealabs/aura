"""
Tests for the Runbook Generator Service.

Tests runbook generation from incidents using templates and LLM enhancement.
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
from src.services.runbook.runbook_generator import GeneratedRunbook, RunbookGenerator

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_bedrock_client():
    """Mock Bedrock client."""
    client = MagicMock()
    response_body = MagicMock()
    response_body.read.return_value = json.dumps(
        {"content": [{"text": "# Enhanced Runbook\n\nThis is enhanced content."}]}
    )
    client.invoke_model.return_value = {"body": response_body}
    return client


@pytest.fixture
def temp_runbooks_dir():
    """Create temporary runbooks directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def generator(mock_bedrock_client, temp_runbooks_dir):
    """Create RunbookGenerator with mocked dependencies."""
    with patch("boto3.client") as mock_boto:
        mock_boto.return_value = mock_bedrock_client

        gen = RunbookGenerator(
            region="us-east-1",
            use_llm=True,
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            runbooks_dir=temp_runbooks_dir,
        )
        gen.bedrock_client = mock_bedrock_client

        return gen


@pytest.fixture
def generator_no_llm(temp_runbooks_dir):
    """Create RunbookGenerator without LLM."""
    gen = RunbookGenerator(
        region="us-east-1",
        use_llm=False,
        runbooks_dir=temp_runbooks_dir,
    )
    return gen


@pytest.fixture
def sample_error_signature():
    """Sample error signature."""
    return ErrorSignature(
        pattern=r"exec format error",
        service="docker",
        severity="high",
        keywords=["docker", "platform", "architecture"],
    )


@pytest.fixture
def sample_resolution_step():
    """Sample resolution step."""
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
def sample_iam_incident(sample_error_signature):
    """Sample IAM permission incident."""
    return Incident(
        id="cb-iam456",
        incident_type=IncidentType.IAM_PERMISSION_FIX,
        title="IAM Permission Issue",
        description="Missing permissions for Bedrock access",
        error_messages=["AccessDenied when calling InvokeModel"],
        error_signatures=[
            ErrorSignature(
                pattern=r"AccessDenied.*bedrock",
                service="bedrock",
                severity="high",
                keywords=["bedrock", "iam", "permissions"],
            )
        ],
        resolution_steps=[],
        affected_services=["bedrock", "iam"],
        affected_resources=["codebuild-role"],
        root_cause="Missing IAM permissions for Bedrock",
        start_time=datetime.now() - timedelta(hours=1),
        end_time=datetime.now(),
        source="codebuild",
        source_id="build-789",
        confidence=0.9,
    )


# =============================================================================
# GeneratedRunbook Tests
# =============================================================================


class TestGeneratedRunbook:
    """Tests for GeneratedRunbook dataclass."""

    def test_create_generated_runbook(self, sample_error_signature):
        """Test creating a generated runbook."""
        runbook = GeneratedRunbook(
            title="Test Runbook",
            filename="TEST_RUNBOOK.md",
            content="# Test\n\nContent here.",
            incident_id="test-123",
            incident_type=IncidentType.DOCKER_BUILD_FIX,
            error_signatures=[sample_error_signature.pattern],
            services=["docker"],
            keywords=["docker", "build"],
            confidence=0.85,
        )

        assert runbook.title == "Test Runbook"
        assert runbook.filename == "TEST_RUNBOOK.md"
        assert runbook.confidence == 0.85

    def test_to_dict(self, sample_error_signature):
        """Test converting runbook to dictionary."""
        runbook = GeneratedRunbook(
            title="Test Runbook",
            filename="TEST_RUNBOOK.md",
            content="# Test",
            incident_id="test-123",
            incident_type=IncidentType.DOCKER_BUILD_FIX,
            error_signatures=["pattern1"],
            services=["docker"],
            keywords=["docker"],
            confidence=0.8,
        )

        result = runbook.to_dict()

        assert result["title"] == "Test Runbook"
        assert result["incident_type"] == "docker_build_fix"
        assert "content" not in result  # Content excluded from dict
        assert "generated_at" in result

    def test_default_generated_at(self, sample_error_signature):
        """Test default generated_at timestamp."""
        before = datetime.now()

        runbook = GeneratedRunbook(
            title="Test",
            filename="test.md",
            content="# Test",
            incident_id="123",
            incident_type=IncidentType.GENERAL_BUG_FIX,
            error_signatures=[],
            services=[],
            keywords=[],
            confidence=0.5,
        )

        after = datetime.now()
        assert before <= runbook.generated_at <= after


# =============================================================================
# RunbookGenerator Tests
# =============================================================================


class TestRunbookGenerator:
    """Tests for RunbookGenerator class."""

    def test_init_with_llm(self, generator):
        """Test initialization with LLM enabled."""
        assert generator.use_llm is True
        assert generator.bedrock_client is not None

    def test_init_without_llm(self, generator_no_llm):
        """Test initialization without LLM."""
        assert generator_no_llm.use_llm is False

    def test_template_defined(self, generator):
        """Test runbook template is defined."""
        assert generator.RUNBOOK_TEMPLATE is not None
        assert "## Problem Description" in generator.RUNBOOK_TEMPLATE
        assert "## Quick Resolution" in generator.RUNBOOK_TEMPLATE

    def test_incident_templates_defined(self, generator):
        """Test incident type templates are defined."""
        assert IncidentType.DOCKER_BUILD_FIX in generator.INCIDENT_TEMPLATES
        assert IncidentType.IAM_PERMISSION_FIX in generator.INCIDENT_TEMPLATES
        assert IncidentType.CLOUDFORMATION_STACK_FIX in generator.INCIDENT_TEMPLATES


class TestRunbookGeneration:
    """Tests for runbook generation methods."""

    @pytest.mark.asyncio
    async def test_generate_runbook_basic(self, generator_no_llm, sample_incident):
        """Test basic runbook generation without LLM."""
        runbook = await generator_no_llm.generate_runbook(sample_incident)

        assert runbook.title == sample_incident.title
        assert runbook.incident_id == sample_incident.id
        assert runbook.incident_type == sample_incident.incident_type
        assert len(runbook.content) > 0

    @pytest.mark.asyncio
    async def test_generate_runbook_with_llm(
        self, generator, sample_incident, mock_bedrock_client
    ):
        """Test runbook generation with LLM enhancement."""
        runbook = await generator.generate_runbook(sample_incident)

        mock_bedrock_client.invoke_model.assert_called_once()
        assert runbook.content is not None

    @pytest.mark.asyncio
    async def test_generate_runbook_llm_fallback(
        self, generator, sample_incident, mock_bedrock_client
    ):
        """Test fallback to template when LLM fails."""
        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeModel",
        )

        runbook = await generator.generate_runbook(sample_incident)

        # Should still generate content using template
        assert runbook.content is not None
        assert "## Problem Description" in runbook.content

    @pytest.mark.asyncio
    async def test_generate_runbook_override_llm(
        self, generator, sample_incident, mock_bedrock_client
    ):
        """Test overriding LLM usage for generation."""
        _runbook = await generator.generate_runbook(
            sample_incident, enhance_with_llm=False
        )

        mock_bedrock_client.invoke_model.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_runbook_keywords(self, generator_no_llm, sample_incident):
        """Test keyword collection in generated runbook."""
        runbook = await generator_no_llm.generate_runbook(sample_incident)

        assert "docker" in runbook.keywords
        assert len(runbook.keywords) > 0

    @pytest.mark.asyncio
    async def test_generate_runbook_services(self, generator_no_llm, sample_incident):
        """Test service collection in generated runbook."""
        runbook = await generator_no_llm.generate_runbook(sample_incident)

        assert runbook.services == sample_incident.affected_services


class TestTemplateFormatting:
    """Tests for template formatting methods."""

    def test_generate_from_template(self, generator_no_llm, sample_incident):
        """Test generating content from template."""
        template_config = generator_no_llm.INCIDENT_TEMPLATES.get(
            sample_incident.incident_type, {}
        )

        content = generator_no_llm._generate_from_template(
            sample_incident, template_config
        )

        assert sample_incident.title in content
        assert sample_incident.description in content
        assert "## Problem Description" in content
        assert "## Quick Resolution" in content

    def test_format_problem_description(self, generator_no_llm, sample_incident):
        """Test problem description formatting."""
        description = generator_no_llm._format_problem_description(sample_incident)

        assert sample_incident.description in description
        assert "docker" in description or "Affected Services" in description

    def test_format_quick_resolution_with_steps(
        self, generator_no_llm, sample_incident
    ):
        """Test quick resolution formatting with resolution steps."""
        resolution = generator_no_llm._format_quick_resolution(sample_incident)

        assert "docker build" in resolution
        assert "Step" in resolution

    def test_format_quick_resolution_docker_type(
        self, generator_no_llm, sample_incident
    ):
        """Test quick resolution for docker incident type."""
        sample_incident.resolution_steps = []  # Clear steps to use template

        resolution = generator_no_llm._format_quick_resolution(sample_incident)

        assert "platform" in resolution.lower() or "docker" in resolution.lower()

    def test_format_quick_resolution_iam_type(
        self, generator_no_llm, sample_iam_incident
    ):
        """Test quick resolution for IAM incident type."""
        resolution = generator_no_llm._format_quick_resolution(sample_iam_incident)

        assert "IAM" in resolution or "permission" in resolution.lower()

    def test_format_diagnostic_steps(self, generator_no_llm, sample_incident):
        """Test diagnostic steps formatting."""
        steps = generator_no_llm._format_diagnostic_steps(sample_incident)

        assert "Step 1" in steps
        assert sample_incident.source in steps or "codebuild" in steps

    def test_format_resolution_procedures(self, generator_no_llm, sample_incident):
        """Test resolution procedures formatting."""
        procedures = generator_no_llm._format_resolution_procedures(sample_incident)

        assert "Procedure" in procedures or "Resolution" in procedures

    def test_format_prevention_docker(self, generator_no_llm, sample_incident):
        """Test prevention formatting for docker incidents."""
        prevention = generator_no_llm._format_prevention(sample_incident)

        assert "platform" in prevention.lower() or "Prevention" in prevention

    def test_format_related_docs(self, generator_no_llm, sample_incident):
        """Test related documentation formatting."""
        docs = generator_no_llm._format_related_docs(sample_incident)

        assert "Documentation" in docs or "http" in docs or ".md" in docs

    def test_format_appendix(self, generator_no_llm, sample_incident):
        """Test appendix formatting."""
        appendix = generator_no_llm._format_appendix(sample_incident)

        assert sample_incident.id in appendix
        assert "Incident ID" in appendix
        assert "Confidence" in appendix


class TestFilenameGeneration:
    """Tests for filename generation."""

    def test_generate_filename_basic(self, generator_no_llm, sample_incident):
        """Test basic filename generation."""
        filename = generator_no_llm._generate_filename(sample_incident)

        assert filename.endswith(".md")
        assert "DOCKER" in filename
        assert len(filename) <= 60

    def test_generate_filename_special_chars(self, generator_no_llm, sample_incident):
        """Test filename generation removes special characters."""
        sample_incident.title = "Test: Issue! With @Special #Chars"
        filename = generator_no_llm._generate_filename(sample_incident)

        assert ":" not in filename
        assert "@" not in filename
        assert "#" not in filename

    def test_generate_filename_length_limit(self, generator_no_llm, sample_incident):
        """Test filename generation respects length limit."""
        sample_incident.title = "A" * 100
        filename = generator_no_llm._generate_filename(sample_incident)

        # 50 chars for title + .md extension
        assert len(filename) <= 55


class TestLLMEnhancement:
    """Tests for LLM enhancement methods."""

    @pytest.mark.asyncio
    async def test_enhance_with_llm(
        self, generator, sample_incident, mock_bedrock_client
    ):
        """Test LLM enhancement of content."""
        base_content = "# Test Runbook\n\nBase content here."

        enhanced = await generator._enhance_with_llm(base_content, sample_incident)

        mock_bedrock_client.invoke_model.assert_called_once()
        assert "Enhanced" in enhanced

    @pytest.mark.asyncio
    async def test_enhance_with_llm_error(
        self, generator, sample_incident, mock_bedrock_client
    ):
        """Test LLM enhancement error handling."""
        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ModelError", "Message": "Model error"}},
            "InvokeModel",
        )

        with pytest.raises(ClientError):
            await generator._enhance_with_llm("content", sample_incident)


class TestSimilarRunbooks:
    """Tests for finding similar runbooks."""

    @pytest.mark.asyncio
    async def test_find_similar_runbooks_empty_dir(
        self, generator_no_llm, sample_incident
    ):
        """Test finding similar runbooks in empty directory."""
        similar = await generator_no_llm.find_similar_runbooks(sample_incident)

        assert similar == []

    @pytest.mark.asyncio
    async def test_find_similar_runbooks_match(
        self, generator_no_llm, sample_incident, temp_runbooks_dir
    ):
        """Test finding similar runbooks with a match."""
        # Create a matching runbook
        runbook_path = Path(temp_runbooks_dir) / "DOCKER_FIX.md"
        runbook_path.write_text(
            """# Docker Fix

## Problem
exec format error when building

## Resolution
Use platform flag
"""
        )

        similar = await generator_no_llm.find_similar_runbooks(
            sample_incident, threshold=0.3
        )

        assert len(similar) > 0
        assert similar[0]["similarity"] > 0.3

    @pytest.mark.asyncio
    async def test_find_similar_runbooks_no_match(
        self, generator_no_llm, sample_incident, temp_runbooks_dir
    ):
        """Test finding similar runbooks with no match."""
        # Create a non-matching runbook
        runbook_path = Path(temp_runbooks_dir) / "UNRELATED.md"
        runbook_path.write_text("# Unrelated Topic\n\nNothing about docker here.")

        similar = await generator_no_llm.find_similar_runbooks(
            sample_incident, threshold=0.8
        )

        assert similar == []

    def test_calculate_similarity_high(self, generator_no_llm, sample_incident):
        """Test similarity calculation for matching content."""
        content = """
        # Docker Build Fix

        exec format error
        docker platform architecture
        codebuild failure
        """

        score = generator_no_llm._calculate_similarity(sample_incident, content)

        assert score > 0.5

    def test_calculate_similarity_low(self, generator_no_llm, sample_incident):
        """Test similarity calculation for non-matching content."""
        content = "# Unrelated Topic\n\nNothing relevant here."

        score = generator_no_llm._calculate_similarity(sample_incident, content)

        assert score < 0.3

    def test_calculate_similarity_empty(self, generator_no_llm, sample_incident):
        """Test similarity calculation with empty incident signatures."""
        sample_incident.error_signatures = []
        sample_incident.affected_services = []

        score = generator_no_llm._calculate_similarity(sample_incident, "content")

        assert score == 0.0


class TestIncidentTypeTemplates:
    """Tests for incident type specific templates."""

    @pytest.mark.asyncio
    async def test_docker_template_keywords(self, generator_no_llm, sample_incident):
        """Test Docker incident uses correct template config."""
        runbook = await generator_no_llm.generate_runbook(sample_incident)

        assert "docker" in runbook.keywords or "container" in runbook.keywords

    @pytest.mark.asyncio
    async def test_iam_template_audience(self, generator_no_llm, sample_iam_incident):
        """Test IAM incident includes security team in audience."""
        runbook = await generator_no_llm.generate_runbook(sample_iam_incident)

        assert "Security" in runbook.content or "DevOps" in runbook.content

    @pytest.mark.asyncio
    async def test_unknown_type_uses_default(self, generator_no_llm, sample_incident):
        """Test unknown incident type uses default template."""
        sample_incident.incident_type = IncidentType.GENERAL_BUG_FIX

        runbook = await generator_no_llm.generate_runbook(sample_incident)

        assert runbook.content is not None
        assert "## Problem Description" in runbook.content
