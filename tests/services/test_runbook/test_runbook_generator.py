"""Tests for the RunbookGenerator service."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.services.runbook.incident_detector import (
    ErrorSignature,
    Incident,
    IncidentType,
    ResolutionStep,
)
from src.services.runbook.runbook_generator import GeneratedRunbook, RunbookGenerator


class TestGeneratedRunbook:
    """Tests for GeneratedRunbook dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        runbook = GeneratedRunbook(
            title="Test Runbook",
            filename="TEST_RUNBOOK.md",
            content="# Test Content",
            incident_id="inc-123",
            incident_type=IncidentType.DOCKER_BUILD_FIX,
            error_signatures=["pattern1", "pattern2"],
            services=["docker", "ecr"],
            keywords=["docker", "build", "fix"],
            confidence=0.85,
            metadata={"source": "codebuild"},
        )

        result = runbook.to_dict()

        assert result["title"] == "Test Runbook"
        assert result["filename"] == "TEST_RUNBOOK.md"
        assert result["incident_id"] == "inc-123"
        assert result["incident_type"] == "docker_build_fix"
        assert "docker" in result["services"]
        assert result["confidence"] == 0.85


class TestRunbookGenerator:
    """Tests for RunbookGenerator class."""

    @pytest.fixture
    def sample_incident(self):
        """Create a sample incident for testing."""
        return Incident(
            id="cb-build123",
            incident_type=IncidentType.DOCKER_BUILD_FIX,
            title="Docker Platform Mismatch",
            description="CodeBuild failed due to architecture mismatch",
            error_messages=[
                "exec format error",
                "exit code: 255",
            ],
            error_signatures=[
                ErrorSignature(
                    pattern=r"exec format error",
                    service="docker",
                    severity="high",
                    keywords=["docker", "platform", "architecture"],
                )
            ],
            resolution_steps=[
                ResolutionStep(
                    command="docker build --platform linux/amd64 -t image:tag .",
                    output="Build successful",
                    timestamp=datetime.now(),
                    success=True,
                    description="Build with explicit platform",
                ),
            ],
            affected_services=["docker", "ecr"],
            affected_resources=["aura-api-dev"],
            root_cause="Docker image built on ARM64 but EKS runs AMD64",
            start_time=datetime(2024, 1, 1, 10, 0, 0),
            end_time=datetime(2024, 1, 1, 10, 30, 0),
            source="codebuild",
            source_id="codebuild-123",
            confidence=0.9,
        )

    @pytest.fixture
    def generator(self, tmp_path):
        """Create a RunbookGenerator with mocked Bedrock client."""
        with patch("boto3.client") as mock_client:
            mock_bedrock = MagicMock()
            mock_client.return_value = mock_bedrock

            generator = RunbookGenerator(
                region="us-east-1",
                use_llm=False,  # Disable LLM for unit tests
                runbooks_dir=str(tmp_path),
            )

            return generator

    @pytest.fixture
    def generator_with_llm(self, tmp_path):
        """Create a RunbookGenerator with LLM enabled (mocked)."""
        with patch("boto3.client") as mock_client:
            mock_bedrock = MagicMock()

            # Mock Bedrock response
            mock_response = {"body": MagicMock()}
            mock_response["body"].read.return_value = json.dumps(
                {
                    "content": [
                        {
                            "text": "# Enhanced Runbook Content\n\nThis is enhanced content."
                        }
                    ]
                }
            ).encode()
            mock_bedrock.invoke_model.return_value = mock_response

            mock_client.return_value = mock_bedrock

            generator = RunbookGenerator(
                region="us-east-1",
                use_llm=True,
                runbooks_dir=str(tmp_path),
            )
            generator.bedrock_client = mock_bedrock

            return generator

    @pytest.mark.asyncio
    async def test_generate_runbook_basic(self, generator, sample_incident):
        """Test basic runbook generation."""
        runbook = await generator.generate_runbook(sample_incident)

        assert runbook is not None
        assert runbook.title == sample_incident.title
        assert runbook.incident_id == sample_incident.id
        assert runbook.incident_type == sample_incident.incident_type
        assert len(runbook.content) > 0

    @pytest.mark.asyncio
    async def test_generate_runbook_has_required_sections(
        self, generator, sample_incident
    ):
        """Test that generated runbook has all required sections."""
        runbook = await generator.generate_runbook(sample_incident)

        required_sections = [
            "Problem Description",
            "Symptoms",
            "Root Cause",
            "Quick Resolution",
            "Diagnostic Steps",
            "Resolution Procedures",
            "Prevention",
            "Related Documentation",
        ]

        for section in required_sections:
            assert section in runbook.content, f"Missing section: {section}"

    @pytest.mark.asyncio
    async def test_generate_runbook_includes_error_messages(
        self, generator, sample_incident
    ):
        """Test that error messages are included in runbook."""
        runbook = await generator.generate_runbook(sample_incident)

        for msg in sample_incident.error_messages:
            assert msg in runbook.content

    @pytest.mark.asyncio
    async def test_generate_runbook_includes_root_cause(
        self, generator, sample_incident
    ):
        """Test that root cause is included in runbook."""
        runbook = await generator.generate_runbook(sample_incident)

        assert sample_incident.root_cause in runbook.content

    @pytest.mark.asyncio
    async def test_generate_runbook_filename_format(self, generator, sample_incident):
        """Test that filename follows conventions."""
        runbook = await generator.generate_runbook(sample_incident)

        assert runbook.filename.endswith(".md")
        assert runbook.filename.isupper() or "_" in runbook.filename
        assert len(runbook.filename) <= 55  # 50 chars + .md extension

    @pytest.mark.asyncio
    async def test_generate_runbook_collects_keywords(self, generator, sample_incident):
        """Test that keywords are collected from incident."""
        runbook = await generator.generate_runbook(sample_incident)

        assert "docker" in runbook.keywords
        assert len(runbook.keywords) > 0

    @pytest.mark.asyncio
    async def test_generate_runbook_different_types(self, generator):
        """Test runbook generation for different incident types."""
        incident_types = [
            IncidentType.IAM_PERMISSION_FIX,
            IncidentType.CLOUDFORMATION_STACK_FIX,
            IncidentType.ECR_CONFLICT_RESOLUTION,
            IncidentType.SHELL_SYNTAX_FIX,
        ]

        for inc_type in incident_types:
            incident = Incident(
                id=f"test-{inc_type.value}",
                incident_type=inc_type,
                title=f"Test {inc_type.value}",
                description="Test description",
                error_messages=["Error message"],
                error_signatures=[],
                resolution_steps=[],
                affected_services=["test-service"],
                affected_resources=["test-resource"],
                root_cause="Test root cause",
                start_time=datetime.now(),
                end_time=datetime.now(),
                source="test",
                source_id="test-123",
                confidence=0.8,
            )

            runbook = await generator.generate_runbook(incident)
            assert runbook is not None
            assert runbook.incident_type == inc_type

    def test_format_problem_description(self, generator, sample_incident):
        """Test problem description formatting."""
        description = generator._format_problem_description(sample_incident)

        assert sample_incident.description in description
        assert "docker" in description.lower()

    def test_format_quick_resolution_with_steps(self, generator, sample_incident):
        """Test quick resolution formatting with resolution steps."""
        resolution = generator._format_quick_resolution(sample_incident)

        assert "docker build" in resolution

    def test_format_quick_resolution_docker_type(self, generator):
        """Test quick resolution for Docker incident type."""
        incident = Incident(
            id="test",
            incident_type=IncidentType.DOCKER_BUILD_FIX,
            title="Test",
            description="Test",
            error_messages=[],
            error_signatures=[],
            resolution_steps=[],  # No steps to trigger default
            affected_services=[],
            affected_resources=[],
            root_cause="",
            start_time=datetime.now(),
            end_time=datetime.now(),
            source="test",
            source_id="test",
            confidence=0.8,
        )

        resolution = generator._format_quick_resolution(incident)
        assert "platform" in resolution.lower() or "amd64" in resolution.lower()

    def test_format_prevention(self, generator, sample_incident):
        """Test prevention section formatting."""
        prevention = generator._format_prevention(sample_incident)

        assert "Prevention" in prevention or "platform" in prevention.lower()
        assert len(prevention.split("\n")) > 1

    def test_format_related_docs(self, generator, sample_incident):
        """Test related documentation formatting."""
        docs = generator._format_related_docs(sample_incident)

        assert "http" in docs or "documentation" in docs.lower()

    def test_generate_filename(self, generator, sample_incident):
        """Test filename generation from incident."""
        filename = generator._generate_filename(sample_incident)

        assert filename.endswith(".md")
        assert " " not in filename
        assert filename == filename.upper().replace(" ", "_") + ".md" or "_" in filename

    @pytest.mark.asyncio
    async def test_find_similar_runbooks_no_matches(
        self, generator, sample_incident, tmp_path
    ):
        """Test finding similar runbooks when none exist."""
        similar = await generator.find_similar_runbooks(sample_incident)
        assert len(similar) == 0

    @pytest.mark.asyncio
    async def test_find_similar_runbooks_with_match(
        self, generator, sample_incident, tmp_path
    ):
        """Test finding similar runbooks when a match exists."""
        # Create a similar runbook
        runbook_path = tmp_path / "DOCKER_PLATFORM_FIX.md"
        runbook_path.write_text("""
# Runbook: Docker Platform Fix

## Symptoms
exec format error
architecture mismatch

## Root Cause
Docker image architecture mismatch

## Resolution
Use --platform linux/amd64
""")

        similar = await generator.find_similar_runbooks(sample_incident, threshold=0.3)

        assert len(similar) > 0
        assert similar[0]["similarity"] >= 0.3

    def test_calculate_similarity_high_match(self, generator, sample_incident):
        """Test similarity calculation with high match."""
        content = """
# Docker Platform Mismatch Runbook

exec format error when running container
Docker architecture ARM64 vs AMD64
platform mismatch
"""

        score = generator._calculate_similarity(sample_incident, content)
        assert score > 0.5

    def test_calculate_similarity_low_match(self, generator, sample_incident):
        """Test similarity calculation with low match."""
        content = """
# Kubernetes Deployment Guide

How to deploy pods to EKS
kubectl apply -f deployment.yaml
"""

        score = generator._calculate_similarity(sample_incident, content)
        assert score < 0.5

    @pytest.mark.asyncio
    async def test_enhance_with_llm(self, generator_with_llm, sample_incident):
        """Test LLM enhancement of runbook content."""
        base_content = "# Basic Runbook\n\nSimple content."

        enhanced = await generator_with_llm._enhance_with_llm(
            base_content, sample_incident
        )

        assert enhanced is not None
        assert len(enhanced) > 0


class TestIncidentTemplates:
    """Tests for incident type template configurations."""

    def test_docker_template_config(self):
        """Test Docker incident template configuration."""
        config = RunbookGenerator.INCIDENT_TEMPLATES.get(IncidentType.DOCKER_BUILD_FIX)

        assert config is not None
        assert "audience" in config
        assert "estimated_time" in config
        assert "docker" in config["keywords"]

    def test_iam_template_config(self):
        """Test IAM incident template configuration."""
        config = RunbookGenerator.INCIDENT_TEMPLATES.get(
            IncidentType.IAM_PERMISSION_FIX
        )

        assert config is not None
        assert "iam" in config["keywords"]

    def test_cloudformation_template_config(self):
        """Test CloudFormation incident template configuration."""
        config = RunbookGenerator.INCIDENT_TEMPLATES.get(
            IncidentType.CLOUDFORMATION_STACK_FIX
        )

        assert config is not None
        assert "cloudformation" in config["keywords"]

    def test_all_common_types_have_templates(self):
        """Test that common incident types have templates."""
        common_types = [
            IncidentType.DOCKER_BUILD_FIX,
            IncidentType.IAM_PERMISSION_FIX,
            IncidentType.CLOUDFORMATION_STACK_FIX,
            IncidentType.ECR_CONFLICT_RESOLUTION,
            IncidentType.SHELL_SYNTAX_FIX,
        ]

        for inc_type in common_types:
            config = RunbookGenerator.INCIDENT_TEMPLATES.get(inc_type)
            assert config is not None, f"Missing template for {inc_type.value}"
