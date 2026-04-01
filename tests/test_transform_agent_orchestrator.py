"""
Tests for Transform Agent Orchestrator.

Tests the unified orchestrator for legacy code modernization workflows.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.transform.architecture_reimaginer import CloudProvider
from src.services.transform.transform_agent_orchestrator import (
    AnalysisReport,
    LegacyCodebase,
    LegacyPlatform,
    ModernizationRecommendation,
    TargetPlatform,
    TransformAgentOrchestrator,
    TransformationArtifact,
    TransformationScope,
    TransformStatus,
    TransformWorkflowResult,
    TransformWorkflowType,
    TranslationSummary,
    ValidationResult,
)

# ============================================================================
# Enum Tests
# ============================================================================


class TestTransformWorkflowType:
    """Test TransformWorkflowType enum."""

    def test_full_modernization(self):
        """Test full modernization value."""
        assert TransformWorkflowType.FULL_MODERNIZATION.value == "full_modernization"

    def test_code_translation(self):
        """Test code translation value."""
        assert TransformWorkflowType.CODE_TRANSLATION.value == "code_translation"

    def test_architecture_assessment(self):
        """Test architecture assessment value."""
        assert (
            TransformWorkflowType.ARCHITECTURE_ASSESSMENT.value
            == "architecture_assessment"
        )

    def test_incremental_migration(self):
        """Test incremental migration value."""
        assert (
            TransformWorkflowType.INCREMENTAL_MIGRATION.value == "incremental_migration"
        )

    def test_proof_of_concept(self):
        """Test proof of concept value."""
        assert TransformWorkflowType.PROOF_OF_CONCEPT.value == "proof_of_concept"

    def test_analysis_only(self):
        """Test analysis only value."""
        assert TransformWorkflowType.ANALYSIS_ONLY.value == "analysis_only"


class TestTransformStatus:
    """Test TransformStatus enum."""

    def test_pending(self):
        """Test pending status."""
        assert TransformStatus.PENDING.value == "pending"

    def test_analyzing(self):
        """Test analyzing status."""
        assert TransformStatus.ANALYZING.value == "analyzing"

    def test_translating(self):
        """Test translating status."""
        assert TransformStatus.TRANSLATING.value == "translating"

    def test_reimagining(self):
        """Test reimagining status."""
        assert TransformStatus.REIMAGINING.value == "reimagining"

    def test_validating(self):
        """Test validating status."""
        assert TransformStatus.VALIDATING.value == "validating"

    def test_completed(self):
        """Test completed status."""
        assert TransformStatus.COMPLETED.value == "completed"

    def test_failed(self):
        """Test failed status."""
        assert TransformStatus.FAILED.value == "failed"

    def test_needs_review(self):
        """Test needs review status."""
        assert TransformStatus.NEEDS_REVIEW.value == "needs_review"


class TestLegacyPlatform:
    """Test LegacyPlatform enum."""

    def test_mainframe_cobol(self):
        """Test mainframe COBOL value."""
        assert LegacyPlatform.MAINFRAME_COBOL.value == "mainframe_cobol"

    def test_dotnet_framework(self):
        """Test .NET Framework value."""
        assert LegacyPlatform.DOTNET_FRAMEWORK.value == "dotnet_framework"

    def test_java_legacy(self):
        """Test Java legacy value."""
        assert LegacyPlatform.JAVA_LEGACY.value == "java_legacy"

    def test_vb6(self):
        """Test VB6 value."""
        assert LegacyPlatform.VB6.value == "vb6"

    def test_powerbuilder(self):
        """Test PowerBuilder value."""
        assert LegacyPlatform.POWERBUILDER.value == "powerbuilder"

    def test_as400_rpg(self):
        """Test AS400 RPG value."""
        assert LegacyPlatform.AS400_RPG.value == "as400_rpg"


class TestTargetPlatform:
    """Test TargetPlatform enum."""

    def test_cloud_native(self):
        """Test cloud native value."""
        assert TargetPlatform.CLOUD_NATIVE.value == "cloud_native"

    def test_serverless(self):
        """Test serverless value."""
        assert TargetPlatform.SERVERLESS.value == "serverless"

    def test_containerized(self):
        """Test containerized value."""
        assert TargetPlatform.CONTAINERIZED.value == "containerized"

    def test_dotnet_core(self):
        """Test .NET Core value."""
        assert TargetPlatform.DOTNET_CORE.value == "dotnet_core"

    def test_java_spring(self):
        """Test Java Spring value."""
        assert TargetPlatform.JAVA_SPRING.value == "java_spring"

    def test_python(self):
        """Test Python value."""
        assert TargetPlatform.PYTHON.value == "python"

    def test_nodejs(self):
        """Test Node.js value."""
        assert TargetPlatform.NODEJS.value == "nodejs"


# ============================================================================
# Dataclass Tests
# ============================================================================


class TestTransformationScope:
    """Test TransformationScope dataclass."""

    def test_create_scope(self):
        """Test creating transformation scope."""
        scope = TransformationScope(
            name="Test Project",
            description="Test description",
            legacy_platform=LegacyPlatform.MAINFRAME_COBOL,
            target_platform=TargetPlatform.PYTHON,
        )
        assert scope.name == "Test Project"
        assert scope.description == "Test description"
        assert scope.legacy_platform == LegacyPlatform.MAINFRAME_COBOL
        assert scope.target_platform == TargetPlatform.PYTHON

    def test_scope_defaults(self):
        """Test scope default values."""
        scope = TransformationScope(
            name="Test",
            description="Test",
            legacy_platform=LegacyPlatform.MAINFRAME_COBOL,
            target_platform=TargetPlatform.PYTHON,
        )
        assert scope.cloud_provider == CloudProvider.AWS
        assert scope.include_architecture_assessment is True
        assert scope.include_code_translation is True
        assert scope.generate_tests is True
        assert scope.modernize_patterns is True


class TestLegacyCodebase:
    """Test LegacyCodebase dataclass."""

    def test_create_codebase(self):
        """Test creating legacy codebase."""
        codebase = LegacyCodebase(
            name="Legacy App",
            platform=LegacyPlatform.MAINFRAME_COBOL,
            source_files={"main.cbl": "IDENTIFICATION DIVISION."},
            total_lines=100,
        )
        assert codebase.name == "Legacy App"
        assert codebase.platform == LegacyPlatform.MAINFRAME_COBOL
        assert len(codebase.source_files) == 1
        assert codebase.total_lines == 100

    def test_codebase_defaults(self):
        """Test codebase default values."""
        codebase = LegacyCodebase(name="Test", platform=LegacyPlatform.DOTNET_FRAMEWORK)
        assert codebase.source_files == {}
        assert codebase.total_lines == 0
        assert codebase.estimated_complexity == "medium"
        assert codebase.external_dependencies == []
        assert codebase.database_dependencies == []


class TestAnalysisReport:
    """Test AnalysisReport dataclass."""

    def test_create_report(self):
        """Test creating analysis report."""
        report = AnalysisReport(
            codebase_name="Test App",
            platform=LegacyPlatform.MAINFRAME_COBOL,
            total_files=10,
            total_lines=5000,
        )
        assert report.codebase_name == "Test App"
        assert report.platform == LegacyPlatform.MAINFRAME_COBOL
        assert report.total_files == 10
        assert report.total_lines == 5000

    def test_report_defaults(self):
        """Test report default values."""
        report = AnalysisReport(
            codebase_name="Test", platform=LegacyPlatform.MAINFRAME_COBOL
        )
        assert report.total_files == 0
        assert report.total_lines == 0
        assert report.code_lines == 0
        assert report.comment_lines == 0
        assert report.complexity_metrics == {}
        assert report.language_features_used == []
        assert report.external_calls == []
        assert report.database_operations == []
        assert report.modernization_challenges == []
        assert report.estimated_effort_weeks == 0


class TestTranslationSummary:
    """Test TranslationSummary dataclass."""

    def test_create_summary(self):
        """Test creating translation summary."""
        summary = TranslationSummary(
            source_language="cobol",
            target_language="python",
            files_translated=5,
            total_source_lines=1000,
        )
        assert summary.source_language == "cobol"
        assert summary.target_language == "python"
        assert summary.files_translated == 5
        assert summary.total_source_lines == 1000

    def test_summary_defaults(self):
        """Test summary default values."""
        summary = TranslationSummary(source_language="cobol", target_language="python")
        assert summary.files_translated == 0
        assert summary.total_source_lines == 0
        assert summary.total_target_lines == 0
        assert summary.translation_ratio == 1.0
        assert summary.high_confidence_percent == 0
        assert summary.warnings_count == 0
        assert summary.manual_review_count == 0


class TestModernizationRecommendation:
    """Test ModernizationRecommendation dataclass."""

    def test_create_recommendation(self):
        """Test creating recommendation."""
        rec = ModernizationRecommendation(
            category="Architecture",
            title="Use Microservices",
            description="Decompose monolith",
            priority="high",
            effort_estimate="4 weeks",
        )
        assert rec.category == "Architecture"
        assert rec.title == "Use Microservices"
        assert rec.priority == "high"

    def test_recommendation_defaults(self):
        """Test recommendation default values."""
        rec = ModernizationRecommendation(
            category="Test",
            title="Test",
            description="Test",
            priority="medium",
            effort_estimate="1 week",
        )
        assert rec.benefits == []
        assert rec.risks == []


class TestTransformationArtifact:
    """Test TransformationArtifact dataclass."""

    def test_create_artifact(self):
        """Test creating artifact."""
        artifact = TransformationArtifact(
            artifact_type="translated_code",
            name="main.py",
            path="src/main.py",
            content="print('Hello')",
        )
        assert artifact.artifact_type == "translated_code"
        assert artifact.name == "main.py"
        assert artifact.path == "src/main.py"
        assert artifact.content == "print('Hello')"

    def test_artifact_defaults(self):
        """Test artifact default values."""
        artifact = TransformationArtifact(
            artifact_type="test", name="test", path="test", content="test"
        )
        assert artifact.metadata == {}


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_create_validation(self):
        """Test creating validation result."""
        validation = ValidationResult(passed=True, total_checks=5, passed_checks=5)
        assert validation.passed is True
        assert validation.total_checks == 5
        assert validation.passed_checks == 5

    def test_validation_defaults(self):
        """Test validation default values."""
        validation = ValidationResult(passed=True)
        assert validation.total_checks == 0
        assert validation.passed_checks == 0
        assert validation.failed_checks == 0
        assert validation.warnings == []
        assert validation.errors == []


class TestTransformWorkflowResult:
    """Test TransformWorkflowResult dataclass."""

    def test_create_result(self):
        """Test creating workflow result."""
        scope = TransformationScope(
            name="Test",
            description="Test",
            legacy_platform=LegacyPlatform.MAINFRAME_COBOL,
            target_platform=TargetPlatform.PYTHON,
        )
        result = TransformWorkflowResult(
            id="abc123",
            workflow_type=TransformWorkflowType.FULL_MODERNIZATION,
            status=TransformStatus.COMPLETED,
            scope=scope,
        )
        assert result.id == "abc123"
        assert result.workflow_type == TransformWorkflowType.FULL_MODERNIZATION
        assert result.status == TransformStatus.COMPLETED

    def test_result_defaults(self):
        """Test result default values."""
        scope = TransformationScope(
            name="Test",
            description="Test",
            legacy_platform=LegacyPlatform.MAINFRAME_COBOL,
            target_platform=TargetPlatform.PYTHON,
        )
        result = TransformWorkflowResult(
            id="abc",
            workflow_type=TransformWorkflowType.ANALYSIS_ONLY,
            status=TransformStatus.PENDING,
            scope=scope,
        )
        assert result.analysis_report is None
        assert result.translation_summary is None
        assert result.architecture_assessment is None
        assert result.recommendations == []
        assert result.artifacts == []
        assert result.validation is None
        assert result.completed_at is None
        assert result.duration_seconds == 0


# ============================================================================
# Orchestrator Initialization Tests
# ============================================================================


class TestOrchestratorInit:
    """Test TransformAgentOrchestrator initialization."""

    def test_init_creates_components(self):
        """Test initialization creates all components."""
        orchestrator = TransformAgentOrchestrator()
        assert orchestrator._cobol_parser is not None
        assert orchestrator._dotnet_parser is not None
        assert orchestrator._translator is not None
        assert orchestrator._reimaginer is not None


# ============================================================================
# Helper Method Tests
# ============================================================================


class TestGetSourceLanguage:
    """Test _get_source_language method."""

    def test_mainframe_cobol(self):
        """Test COBOL platform mapping."""
        from src.services.transform.cross_language_translator import SourceLanguage

        orchestrator = TransformAgentOrchestrator()
        result = orchestrator._get_source_language(LegacyPlatform.MAINFRAME_COBOL)
        assert result == SourceLanguage.COBOL

    def test_dotnet_framework(self):
        """Test .NET Framework platform mapping."""
        from src.services.transform.cross_language_translator import SourceLanguage

        orchestrator = TransformAgentOrchestrator()
        result = orchestrator._get_source_language(LegacyPlatform.DOTNET_FRAMEWORK)
        assert result == SourceLanguage.CSHARP

    def test_vb6(self):
        """Test VB6 platform mapping."""
        from src.services.transform.cross_language_translator import SourceLanguage

        orchestrator = TransformAgentOrchestrator()
        result = orchestrator._get_source_language(LegacyPlatform.VB6)
        assert result == SourceLanguage.VB6

    def test_java_legacy(self):
        """Test Java legacy platform mapping."""
        from src.services.transform.cross_language_translator import SourceLanguage

        orchestrator = TransformAgentOrchestrator()
        result = orchestrator._get_source_language(LegacyPlatform.JAVA_LEGACY)
        assert result == SourceLanguage.JAVA

    def test_unsupported_platform(self):
        """Test unsupported platform returns default."""
        from src.services.transform.cross_language_translator import SourceLanguage

        orchestrator = TransformAgentOrchestrator()
        result = orchestrator._get_source_language(LegacyPlatform.POWERBUILDER)
        assert result == SourceLanguage.COBOL  # Default


class TestGetTargetLanguage:
    """Test _get_target_language method."""

    def test_cloud_native(self):
        """Test cloud native target mapping."""
        from src.services.transform.cross_language_translator import TargetLanguage

        orchestrator = TransformAgentOrchestrator()
        result = orchestrator._get_target_language(TargetPlatform.CLOUD_NATIVE)
        assert result == TargetLanguage.PYTHON

    def test_serverless(self):
        """Test serverless target mapping."""
        from src.services.transform.cross_language_translator import TargetLanguage

        orchestrator = TransformAgentOrchestrator()
        result = orchestrator._get_target_language(TargetPlatform.SERVERLESS)
        assert result == TargetLanguage.PYTHON

    def test_containerized(self):
        """Test containerized target mapping."""
        from src.services.transform.cross_language_translator import TargetLanguage

        orchestrator = TransformAgentOrchestrator()
        result = orchestrator._get_target_language(TargetPlatform.CONTAINERIZED)
        assert result == TargetLanguage.JAVA

    def test_dotnet_core(self):
        """Test .NET Core target mapping."""
        from src.services.transform.cross_language_translator import TargetLanguage

        orchestrator = TransformAgentOrchestrator()
        result = orchestrator._get_target_language(TargetPlatform.DOTNET_CORE)
        assert result == TargetLanguage.CSHARP

    def test_java_spring(self):
        """Test Java Spring target mapping."""
        from src.services.transform.cross_language_translator import TargetLanguage

        orchestrator = TransformAgentOrchestrator()
        result = orchestrator._get_target_language(TargetPlatform.JAVA_SPRING)
        assert result == TargetLanguage.JAVA

    def test_python(self):
        """Test Python target mapping."""
        from src.services.transform.cross_language_translator import TargetLanguage

        orchestrator = TransformAgentOrchestrator()
        result = orchestrator._get_target_language(TargetPlatform.PYTHON)
        assert result == TargetLanguage.PYTHON

    def test_nodejs(self):
        """Test Node.js target mapping."""
        from src.services.transform.cross_language_translator import TargetLanguage

        orchestrator = TransformAgentOrchestrator()
        result = orchestrator._get_target_language(TargetPlatform.NODEJS)
        assert result == TargetLanguage.TYPESCRIPT


class TestIsTranslatableFile:
    """Test _is_translatable_file method."""

    def test_cobol_cbl(self):
        """Test COBOL .cbl file."""
        orchestrator = TransformAgentOrchestrator()
        assert (
            orchestrator._is_translatable_file(
                "main.cbl", LegacyPlatform.MAINFRAME_COBOL
            )
            is True
        )

    def test_cobol_cob(self):
        """Test COBOL .cob file."""
        orchestrator = TransformAgentOrchestrator()
        assert (
            orchestrator._is_translatable_file(
                "main.cob", LegacyPlatform.MAINFRAME_COBOL
            )
            is True
        )

    def test_cobol_cobol(self):
        """Test COBOL .cobol file."""
        orchestrator = TransformAgentOrchestrator()
        assert (
            orchestrator._is_translatable_file(
                "main.cobol", LegacyPlatform.MAINFRAME_COBOL
            )
            is True
        )

    def test_dotnet_cs(self):
        """Test .NET .cs file."""
        orchestrator = TransformAgentOrchestrator()
        assert (
            orchestrator._is_translatable_file(
                "main.cs", LegacyPlatform.DOTNET_FRAMEWORK
            )
            is True
        )

    def test_dotnet_vb(self):
        """Test .NET .vb file."""
        orchestrator = TransformAgentOrchestrator()
        assert (
            orchestrator._is_translatable_file(
                "main.vb", LegacyPlatform.DOTNET_FRAMEWORK
            )
            is True
        )

    def test_vb6_vb(self):
        """Test VB6 .vb file."""
        orchestrator = TransformAgentOrchestrator()
        assert orchestrator._is_translatable_file("main.vb", LegacyPlatform.VB6) is True

    def test_java(self):
        """Test Java .java file."""
        orchestrator = TransformAgentOrchestrator()
        assert (
            orchestrator._is_translatable_file("Main.java", LegacyPlatform.JAVA_LEGACY)
            is True
        )

    def test_non_translatable(self):
        """Test non-translatable file."""
        orchestrator = TransformAgentOrchestrator()
        assert (
            orchestrator._is_translatable_file(
                "main.py", LegacyPlatform.MAINFRAME_COBOL
            )
            is False
        )

    def test_unsupported_platform(self):
        """Test unsupported platform."""
        orchestrator = TransformAgentOrchestrator()
        assert (
            orchestrator._is_translatable_file("main.pbl", LegacyPlatform.POWERBUILDER)
            is False
        )


class TestEstimateModernizationEffort:
    """Test _estimate_modernization_effort method."""

    def test_small_codebase(self):
        """Test estimate for small codebase."""
        orchestrator = TransformAgentOrchestrator()
        report = AnalysisReport(
            codebase_name="Small",
            platform=LegacyPlatform.MAINFRAME_COBOL,
            code_lines=1000,
        )
        weeks = orchestrator._estimate_modernization_effort(report)
        assert weeks >= 2  # Minimum 2 weeks

    def test_large_codebase(self):
        """Test estimate for large codebase."""
        orchestrator = TransformAgentOrchestrator()
        report = AnalysisReport(
            codebase_name="Large",
            platform=LegacyPlatform.MAINFRAME_COBOL,
            code_lines=50000,
        )
        weeks = orchestrator._estimate_modernization_effort(report)
        assert weeks > 2

    def test_complex_codebase(self):
        """Test estimate for complex codebase."""
        orchestrator = TransformAgentOrchestrator()
        report = AnalysisReport(
            codebase_name="Complex",
            platform=LegacyPlatform.MAINFRAME_COBOL,
            code_lines=10000,
            complexity_metrics={"avg_complexity": 15},
        )
        weeks = orchestrator._estimate_modernization_effort(report)
        # Should be higher due to complexity multiplier
        assert weeks > 2

    def test_with_challenges(self):
        """Test estimate with modernization challenges."""
        orchestrator = TransformAgentOrchestrator()
        report = AnalysisReport(
            codebase_name="Challenges",
            platform=LegacyPlatform.MAINFRAME_COBOL,
            code_lines=5000,
            modernization_challenges=[
                "DB2 migration",
                "CICS redesign",
                "Complex copybooks",
            ],
        )
        weeks = orchestrator._estimate_modernization_effort(report)
        # Should add 2 weeks per challenge
        assert weeks >= 6

    def test_with_database(self):
        """Test estimate with database operations."""
        orchestrator = TransformAgentOrchestrator()
        report = AnalysisReport(
            codebase_name="DB",
            platform=LegacyPlatform.MAINFRAME_COBOL,
            code_lines=5000,
            database_operations=["SELECT", "INSERT"],
        )
        weeks = orchestrator._estimate_modernization_effort(report)
        # Should add 4 weeks for database
        assert weeks >= 5

    def test_maximum_cap(self):
        """Test estimate has maximum cap."""
        orchestrator = TransformAgentOrchestrator()
        report = AnalysisReport(
            codebase_name="Huge",
            platform=LegacyPlatform.MAINFRAME_COBOL,
            code_lines=1000000,
            complexity_metrics={"avg_complexity": 20},
            modernization_challenges=[
                "1",
                "2",
                "3",
                "4",
                "5",
                "6",
                "7",
                "8",
                "9",
                "10",
            ],
            database_operations=["lots"],
        )
        weeks = orchestrator._estimate_modernization_effort(report)
        assert weeks <= 104  # Maximum 2 years


# ============================================================================
# Get Supported Transformations Tests
# ============================================================================


class TestGetSupportedTransformations:
    """Test get_supported_transformations method."""

    @pytest.mark.asyncio
    async def test_returns_transformations(self):
        """Test returning supported transformations."""
        orchestrator = TransformAgentOrchestrator()
        transformations = await orchestrator.get_supported_transformations()
        assert len(transformations) > 0

    @pytest.mark.asyncio
    async def test_has_cobol_python(self):
        """Test COBOL to Python transformation exists."""
        orchestrator = TransformAgentOrchestrator()
        transformations = await orchestrator.get_supported_transformations()
        cobol_python = [
            t
            for t in transformations
            if t["source"] == "Mainframe COBOL" and t["target"] == "Python"
        ]
        assert len(cobol_python) == 1
        assert cobol_python[0]["quality"] == "high"

    @pytest.mark.asyncio
    async def test_has_dotnet_core(self):
        """Test .NET Framework to .NET Core transformation exists."""
        orchestrator = TransformAgentOrchestrator()
        transformations = await orchestrator.get_supported_transformations()
        dotnet = [t for t in transformations if ".NET Framework" in t["source"]]
        assert len(dotnet) >= 1


# ============================================================================
# Recommendation Generation Tests
# ============================================================================


class TestGenerateRecommendations:
    """Test _generate_recommendations method."""

    def test_large_effort_recommendation(self):
        """Test recommendation for large effort projects."""
        orchestrator = TransformAgentOrchestrator()
        analysis = AnalysisReport(
            codebase_name="Large",
            platform=LegacyPlatform.MAINFRAME_COBOL,
            estimated_effort_weeks=25,
        )
        recommendations = orchestrator._generate_recommendations(analysis, None, None)
        phased = [r for r in recommendations if "Phased" in r.title]
        assert len(phased) >= 1

    def test_challenge_recommendations(self):
        """Test recommendations for challenges."""
        orchestrator = TransformAgentOrchestrator()
        analysis = AnalysisReport(
            codebase_name="Challenging",
            platform=LegacyPlatform.MAINFRAME_COBOL,
            modernization_challenges=["DB2 requires migration"],
        )
        recommendations = orchestrator._generate_recommendations(analysis, None, None)
        # Should have challenge-based recommendations
        assert len(recommendations) >= 1

    def test_manual_review_recommendation(self):
        """Test recommendation for manual review."""
        orchestrator = TransformAgentOrchestrator()
        translation = TranslationSummary(
            source_language="cobol", target_language="python", manual_review_count=10
        )
        recommendations = orchestrator._generate_recommendations(
            None, None, translation
        )
        review_rec = [r for r in recommendations if "Manual Review" in r.title]
        assert len(review_rec) >= 1

    def test_low_confidence_recommendation(self):
        """Test recommendation for low confidence translations."""
        orchestrator = TransformAgentOrchestrator()
        translation = TranslationSummary(
            source_language="cobol",
            target_language="python",
            high_confidence_percent=50,
        )
        recommendations = orchestrator._generate_recommendations(
            None, None, translation
        )
        testing_rec = [r for r in recommendations if "Testing" in r.title]
        assert len(testing_rec) >= 1

    def test_standard_recommendations(self):
        """Test standard recommendations are always included."""
        orchestrator = TransformAgentOrchestrator()
        recommendations = orchestrator._generate_recommendations(None, None, None)
        # Should have CI/CD and Observability recommendations
        cicd = [r for r in recommendations if "CI/CD" in r.title]
        obs = [r for r in recommendations if "Observability" in r.title]
        assert len(cicd) >= 1
        assert len(obs) >= 1


# ============================================================================
# Validation Tests
# ============================================================================


class TestValidateTransformation:
    """Test _validate_transformation method."""

    @pytest.mark.asyncio
    async def test_passes_with_complete_analysis(self):
        """Test validation passes with complete analysis."""
        orchestrator = TransformAgentOrchestrator()
        scope = TransformationScope(
            name="Test",
            description="Test",
            legacy_platform=LegacyPlatform.MAINFRAME_COBOL,
            target_platform=TargetPlatform.PYTHON,
        )
        result = TransformWorkflowResult(
            id="test",
            workflow_type=TransformWorkflowType.ANALYSIS_ONLY,
            status=TransformStatus.VALIDATING,
            scope=scope,
            analysis_report=AnalysisReport(
                codebase_name="Test",
                platform=LegacyPlatform.MAINFRAME_COBOL,
                total_lines=100,
            ),
        )
        validation = await orchestrator._validate_transformation(result)
        assert validation.passed is True
        assert validation.passed_checks >= 1

    @pytest.mark.asyncio
    async def test_fails_with_empty_analysis(self):
        """Test validation fails with empty analysis."""
        orchestrator = TransformAgentOrchestrator()
        scope = TransformationScope(
            name="Test",
            description="Test",
            legacy_platform=LegacyPlatform.MAINFRAME_COBOL,
            target_platform=TargetPlatform.PYTHON,
        )
        result = TransformWorkflowResult(
            id="test",
            workflow_type=TransformWorkflowType.ANALYSIS_ONLY,
            status=TransformStatus.VALIDATING,
            scope=scope,
            analysis_report=AnalysisReport(
                codebase_name="Test",
                platform=LegacyPlatform.MAINFRAME_COBOL,
                total_lines=0,
            ),
        )
        validation = await orchestrator._validate_transformation(result)
        assert validation.passed is False
        assert len(validation.errors) > 0

    @pytest.mark.asyncio
    async def test_warns_on_low_confidence(self):
        """Test validation warns on low confidence."""
        orchestrator = TransformAgentOrchestrator()
        scope = TransformationScope(
            name="Test",
            description="Test",
            legacy_platform=LegacyPlatform.MAINFRAME_COBOL,
            target_platform=TargetPlatform.PYTHON,
        )
        result = TransformWorkflowResult(
            id="test",
            workflow_type=TransformWorkflowType.FULL_MODERNIZATION,
            status=TransformStatus.VALIDATING,
            scope=scope,
            analysis_report=AnalysisReport(
                codebase_name="Test",
                platform=LegacyPlatform.MAINFRAME_COBOL,
                total_lines=100,
            ),
            translation_summary=TranslationSummary(
                source_language="cobol",
                target_language="python",
                high_confidence_percent=50,
                files_translated=5,
            ),
        )
        validation = await orchestrator._validate_transformation(result)
        assert len(validation.warnings) >= 1

    @pytest.mark.asyncio
    async def test_fails_no_files_translated(self):
        """Test validation fails when no files translated."""
        orchestrator = TransformAgentOrchestrator()
        scope = TransformationScope(
            name="Test",
            description="Test",
            legacy_platform=LegacyPlatform.MAINFRAME_COBOL,
            target_platform=TargetPlatform.PYTHON,
        )
        result = TransformWorkflowResult(
            id="test",
            workflow_type=TransformWorkflowType.FULL_MODERNIZATION,
            status=TransformStatus.VALIDATING,
            scope=scope,
            analysis_report=AnalysisReport(
                codebase_name="Test",
                platform=LegacyPlatform.MAINFRAME_COBOL,
                total_lines=100,
            ),
            translation_summary=TranslationSummary(
                source_language="cobol", target_language="python", files_translated=0
            ),
        )
        validation = await orchestrator._validate_transformation(result)
        assert validation.passed is False
        assert "No files were translated" in validation.errors


# ============================================================================
# Summarize Translation Tests
# ============================================================================


class TestSummarizeTranslation:
    """Test _summarize_translation method."""

    def test_empty_result(self):
        """Test summarizing empty result."""
        from src.services.transform.cross_language_translator import TranslationResult

        orchestrator = TransformAgentOrchestrator()
        result = TranslationResult(status=TransformStatus.COMPLETED, files=[])
        summary = orchestrator._summarize_translation(result)
        assert summary.source_language == "unknown"
        assert summary.target_language == "unknown"
        assert summary.files_translated == 0

    def test_with_files(self):
        """Test summarizing result with files."""
        from src.services.transform.cross_language_translator import (
            ConfidenceLevel,
            SourceLanguage,
            TargetLanguage,
            TranslatedFile,
            TranslationResult,
        )

        orchestrator = TransformAgentOrchestrator()
        result = TranslationResult(
            status=TransformStatus.COMPLETED,
            files=[
                TranslatedFile(
                    source_path="main.cbl",
                    target_path="main.py",
                    source_language=SourceLanguage.COBOL,
                    target_language=TargetLanguage.PYTHON,
                    source_code="",
                    translated_code="",
                    confidence=ConfidenceLevel.HIGH,
                )
            ],
            total_source_lines=100,
            total_target_lines=80,
        )
        summary = orchestrator._summarize_translation(result)
        assert summary.source_language == "cobol"
        assert summary.target_language == "python"
        assert summary.files_translated == 1
        assert summary.total_source_lines == 100
        assert summary.total_target_lines == 80
        assert summary.translation_ratio == 0.8
        assert summary.high_confidence_percent == 100


# ============================================================================
# Create Translation Artifacts Tests
# ============================================================================


class TestCreateTranslationArtifacts:
    """Test _create_translation_artifacts method."""

    def test_empty_result(self):
        """Test creating artifacts from empty result."""
        from src.services.transform.cross_language_translator import TranslationResult

        orchestrator = TransformAgentOrchestrator()
        result = TranslationResult(
            status=TransformStatus.COMPLETED, files=[], test_cases=[]
        )
        artifacts = orchestrator._create_translation_artifacts(result)
        assert len(artifacts) == 0

    def test_with_translated_file(self):
        """Test creating artifacts from translated file."""
        from src.services.transform.cross_language_translator import (
            ConfidenceLevel,
            SourceLanguage,
            TargetLanguage,
            TranslatedFile,
            TranslationResult,
        )

        orchestrator = TransformAgentOrchestrator()
        result = TranslationResult(
            status=TransformStatus.COMPLETED,
            files=[
                TranslatedFile(
                    source_path="main.cbl",
                    target_path="src/main.py",
                    source_language=SourceLanguage.COBOL,
                    target_language=TargetLanguage.PYTHON,
                    source_code="IDENTIFICATION DIVISION.",
                    translated_code="# Main module",
                    confidence=ConfidenceLevel.HIGH,
                )
            ],
            test_cases=[],
        )
        artifacts = orchestrator._create_translation_artifacts(result)
        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == "translated_code"
        assert artifacts[0].name == "main.py"
        assert artifacts[0].path == "src/main.py"

    def test_with_test_case(self):
        """Test creating artifacts from test cases."""
        from src.services.transform.cross_language_translator import (
            TranslationResult,
            TranslationTestCase,
        )

        orchestrator = TransformAgentOrchestrator()
        result = TranslationResult(
            status=TransformStatus.COMPLETED,
            files=[],
            test_cases=[
                TranslationTestCase(
                    name="test_process_data",
                    description="Test data processing",
                    original_function="PROCESS-DATA",
                    translated_function="process_data",
                    test_code="def test_process_data(): pass",
                )
            ],
        )
        artifacts = orchestrator._create_translation_artifacts(result)
        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == "test_case"
        assert artifacts[0].name == "test_process_data"


# ============================================================================
# Execute Workflow Tests (with mocks)
# ============================================================================


class TestExecuteWorkflow:
    """Test execute_workflow method."""

    @pytest.mark.asyncio
    async def test_analysis_only_workflow(self):
        """Test analysis-only workflow."""
        orchestrator = TransformAgentOrchestrator()
        scope = TransformationScope(
            name="Test Project",
            description="Test",
            legacy_platform=LegacyPlatform.MAINFRAME_COBOL,
            target_platform=TargetPlatform.PYTHON,
        )
        codebase = LegacyCodebase(
            name="Test",
            platform=LegacyPlatform.MAINFRAME_COBOL,
            source_files={"test.cbl": "IDENTIFICATION DIVISION.\nPROGRAM-ID. TEST."},
        )

        with patch.object(
            orchestrator, "_analyze_codebase", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.return_value = AnalysisReport(
                codebase_name="Test",
                platform=LegacyPlatform.MAINFRAME_COBOL,
                total_lines=100,
            )

            result = await orchestrator.execute_workflow(
                TransformWorkflowType.ANALYSIS_ONLY, scope, codebase
            )

            assert result.status == TransformStatus.COMPLETED
            assert result.analysis_report is not None
            assert result.completed_at is not None
            assert result.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_workflow_error_handling(self):
        """Test workflow error handling."""
        orchestrator = TransformAgentOrchestrator()
        scope = TransformationScope(
            name="Test",
            description="Test",
            legacy_platform=LegacyPlatform.MAINFRAME_COBOL,
            target_platform=TargetPlatform.PYTHON,
        )
        codebase = LegacyCodebase(name="Test", platform=LegacyPlatform.MAINFRAME_COBOL)

        with patch.object(
            orchestrator, "_analyze_codebase", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.side_effect = Exception("Analysis failed")

            result = await orchestrator.execute_workflow(
                TransformWorkflowType.FULL_MODERNIZATION, scope, codebase
            )

            assert result.status == TransformStatus.FAILED
            assert len(result.recommendations) >= 1
            assert result.recommendations[0].category == "Error"


# ============================================================================
# Analyze Codebase Tests
# ============================================================================


class TestAnalyzeCodebase:
    """Test _analyze_codebase method."""

    @pytest.mark.asyncio
    async def test_generic_analysis(self):
        """Test generic codebase analysis."""
        orchestrator = TransformAgentOrchestrator()
        codebase = LegacyCodebase(
            name="Generic",
            platform=LegacyPlatform.POWERBUILDER,
            source_files={"main.pbl": "function main()\n  return 0\nend function"},
        )
        report = await orchestrator._analyze_codebase(codebase)
        assert report.codebase_name == "Generic"
        assert report.total_files == 1
        assert report.total_lines == 3
        assert report.code_lines == 3


# ============================================================================
# Analyze Single File Tests
# ============================================================================


class TestAnalyzeSingleFile:
    """Test analyze_single_file method."""

    @pytest.mark.asyncio
    async def test_unsupported_platform(self):
        """Test analyzing unsupported platform."""
        orchestrator = TransformAgentOrchestrator()
        result = await orchestrator.analyze_single_file(
            "content", "file.pbl", LegacyPlatform.POWERBUILDER
        )
        assert result["success"] is False
        assert "Unsupported platform" in result["errors"]

    @pytest.mark.asyncio
    async def test_cobol_file(self):
        """Test analyzing COBOL file."""
        orchestrator = TransformAgentOrchestrator()
        cobol_content = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTPROG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-COUNT PIC 9(5).
       PROCEDURE DIVISION.
           MOVE 1 TO WS-COUNT.
           STOP RUN.
        """
        result = await orchestrator.analyze_single_file(
            cobol_content, "test.cbl", LegacyPlatform.MAINFRAME_COBOL
        )
        # Note: Result depends on parser implementation
        assert "success" in result

    @pytest.mark.asyncio
    async def test_dotnet_file(self):
        """Test analyzing .NET file."""
        orchestrator = TransformAgentOrchestrator()
        cs_content = """
using System;
namespace Test
{
    public class Program
    {
        public static void Main()
        {
            Console.WriteLine("Hello");
        }
    }
}
        """
        result = await orchestrator.analyze_single_file(
            cs_content, "Program.cs", LegacyPlatform.DOTNET_FRAMEWORK
        )
        assert result["success"] is True
        assert result["total_lines"] > 0


# ============================================================================
# Translate Single File Tests
# ============================================================================


class TestTranslateSingleFile:
    """Test translate_single_file method."""

    @pytest.mark.asyncio
    async def test_translate_file(self):
        """Test translating a single file."""
        orchestrator = TransformAgentOrchestrator()

        with patch.object(
            orchestrator._translator, "translate", new_callable=AsyncMock
        ) as mock_translate:
            from src.services.transform.cross_language_translator import (
                ConfidenceLevel,
                SourceLanguage,
                TargetLanguage,
                TranslatedFile,
                TranslationResult,
            )

            mock_translate.return_value = TranslationResult(
                status=TransformStatus.COMPLETED,
                files=[
                    TranslatedFile(
                        source_path="main.cbl",
                        target_path="main.py",
                        source_language=SourceLanguage.COBOL,
                        target_language=TargetLanguage.PYTHON,
                        source_code="IDENTIFICATION DIVISION.",
                        translated_code="# Translated code",
                        confidence=ConfidenceLevel.HIGH,
                    )
                ],
                test_cases=[],
            )

            result = await orchestrator.translate_single_file(
                "IDENTIFICATION DIVISION.",
                "main.cbl",
                LegacyPlatform.MAINFRAME_COBOL,
                TargetPlatform.PYTHON,
            )

            assert result["success"] is True
            assert result["translated_code"] == "# Translated code"
            assert result["confidence"] == "high"

    @pytest.mark.asyncio
    async def test_translate_file_failure(self):
        """Test translating file failure."""
        orchestrator = TransformAgentOrchestrator()

        with patch.object(
            orchestrator._translator, "translate", new_callable=AsyncMock
        ) as mock_translate:
            from src.services.transform.cross_language_translator import (
                TranslationResult,
            )

            mock_translate.return_value = TranslationResult(
                status=TransformStatus.FAILED, files=[]
            )

            result = await orchestrator.translate_single_file(
                "content",
                "main.cbl",
                LegacyPlatform.MAINFRAME_COBOL,
                TargetPlatform.PYTHON,
            )

            assert result["success"] is False
            assert "Translation failed" in result["errors"]
