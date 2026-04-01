"""
Transform Agent Orchestrator - AWS Transform Agent Parity

Unified orchestrator for legacy code modernization workflows.
Coordinates COBOL Parser, .NET Parser, Cross-Language Translator,
and Architecture Reimaginer for comprehensive transformation.

Reference: ADR-030 Section 5.4 Transform Agent Components
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .architecture_reimaginer import (
    ArchitectureAssessment,
    ArchitectureReimaginer,
    CloudProvider,
    CurrentArchitecture,
    ModernizationStrategy,
)
from .cobol_parser import COBOLParser, COBOLProgram
from .cross_language_translator import (
    ConfidenceLevel,
    CrossLanguageTranslator,
    SourceLanguage,
    TargetLanguage,
    TranslationConfig,
    TranslationResult,
    TranslationStatus,
    TranslationStrategy,
)
from .dotnet_parser import DotNetParser, DotNetProject


class TransformWorkflowType(str, Enum):
    """Types of transformation workflows."""

    FULL_MODERNIZATION = "full_modernization"
    CODE_TRANSLATION = "code_translation"
    ARCHITECTURE_ASSESSMENT = "architecture_assessment"
    INCREMENTAL_MIGRATION = "incremental_migration"
    PROOF_OF_CONCEPT = "proof_of_concept"
    ANALYSIS_ONLY = "analysis_only"


class TransformStatus(str, Enum):
    """Transformation workflow status."""

    PENDING = "pending"
    ANALYZING = "analyzing"
    TRANSLATING = "translating"
    REIMAGINING = "reimagining"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class LegacyPlatform(str, Enum):
    """Supported legacy platforms."""

    MAINFRAME_COBOL = "mainframe_cobol"
    DOTNET_FRAMEWORK = "dotnet_framework"
    JAVA_LEGACY = "java_legacy"
    VB6 = "vb6"
    POWERBUILDER = "powerbuilder"
    AS400_RPG = "as400_rpg"


class TargetPlatform(str, Enum):
    """Target modernization platforms."""

    CLOUD_NATIVE = "cloud_native"
    SERVERLESS = "serverless"
    CONTAINERIZED = "containerized"
    DOTNET_CORE = "dotnet_core"
    JAVA_SPRING = "java_spring"
    PYTHON = "python"
    NODEJS = "nodejs"


@dataclass
class TransformationScope:
    """Scope of transformation project."""

    name: str
    description: str
    legacy_platform: LegacyPlatform
    target_platform: TargetPlatform
    cloud_provider: CloudProvider = CloudProvider.AWS
    include_architecture_assessment: bool = True
    include_code_translation: bool = True
    generate_tests: bool = True
    modernize_patterns: bool = True


@dataclass
class LegacyCodebase:
    """Legacy codebase information."""

    name: str
    platform: LegacyPlatform
    source_files: dict[str, str] = field(default_factory=dict)
    total_lines: int = 0
    estimated_complexity: str = "medium"
    external_dependencies: list[str] = field(default_factory=list)
    database_dependencies: list[str] = field(default_factory=list)


@dataclass
class AnalysisReport:
    """Legacy code analysis report."""

    codebase_name: str
    platform: LegacyPlatform
    total_files: int = 0
    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    complexity_metrics: dict[str, Any] = field(default_factory=dict)
    language_features_used: list[str] = field(default_factory=list)
    external_calls: list[str] = field(default_factory=list)
    database_operations: list[str] = field(default_factory=list)
    modernization_challenges: list[str] = field(default_factory=list)
    estimated_effort_weeks: int = 0


@dataclass
class TranslationSummary:
    """Summary of code translation."""

    source_language: str
    target_language: str
    files_translated: int = 0
    total_source_lines: int = 0
    total_target_lines: int = 0
    translation_ratio: float = 1.0
    high_confidence_percent: float = 0
    warnings_count: int = 0
    manual_review_count: int = 0


@dataclass
class ModernizationRecommendation:
    """Modernization recommendation."""

    category: str
    title: str
    description: str
    priority: str
    effort_estimate: str
    benefits: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


@dataclass
class TransformationArtifact:
    """Generated transformation artifact."""

    artifact_type: str
    name: str
    path: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Validation result for transformed code."""

    passed: bool
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class TransformWorkflowResult:
    """Complete transformation workflow result."""

    id: str
    workflow_type: TransformWorkflowType
    status: TransformStatus
    scope: TransformationScope
    analysis_report: AnalysisReport | None = None
    translation_summary: TranslationSummary | None = None
    architecture_assessment: ArchitectureAssessment | None = None
    recommendations: list[ModernizationRecommendation] = field(default_factory=list)
    artifacts: list[TransformationArtifact] = field(default_factory=list)
    validation: ValidationResult | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    duration_seconds: float = 0


class TransformAgentOrchestrator:
    """
    Unified orchestrator for legacy code modernization.

    Coordinates multiple transform components:
    - COBOLParser: Legacy COBOL code analysis
    - DotNetParser: .NET Framework code analysis
    - CrossLanguageTranslator: Code translation between languages
    - ArchitectureReimaginer: Architecture modernization planning

    Provides end-to-end workflows for:
    - Full application modernization
    - Targeted code translation
    - Architecture assessments
    - Incremental migration planning
    """

    def __init__(self) -> None:
        """Initialize transform agent orchestrator."""
        self._cobol_parser = COBOLParser()
        self._dotnet_parser = DotNetParser()
        self._translator = CrossLanguageTranslator()
        self._reimaginer = ArchitectureReimaginer()

    async def execute_workflow(
        self,
        workflow_type: TransformWorkflowType,
        scope: TransformationScope,
        codebase: LegacyCodebase,
    ) -> TransformWorkflowResult:
        """
        Execute a transformation workflow.

        Args:
            workflow_type: Type of transformation workflow
            scope: Transformation scope and settings
            codebase: Legacy codebase to transform

        Returns:
            Complete workflow result
        """
        # Generate workflow ID
        workflow_id = hashlib.sha256(
            f"{workflow_type.value}_{scope.name}_{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:12]

        result = TransformWorkflowResult(
            id=workflow_id,
            workflow_type=workflow_type,
            status=TransformStatus.ANALYZING,
            scope=scope,
        )

        try:
            # Phase 1: Analysis
            result.analysis_report = await self._analyze_codebase(codebase)

            if workflow_type == TransformWorkflowType.ANALYSIS_ONLY:
                result.status = TransformStatus.COMPLETED
                result.completed_at = datetime.now(timezone.utc)
                result.duration_seconds = (
                    result.completed_at - result.started_at
                ).total_seconds()
                return result

            # Phase 2: Architecture Assessment (if enabled)
            if scope.include_architecture_assessment:
                result.status = TransformStatus.REIMAGINING
                result.architecture_assessment = await self._assess_architecture(
                    codebase, result.analysis_report, scope
                )

            # Phase 3: Code Translation (if enabled)
            if scope.include_code_translation:
                result.status = TransformStatus.TRANSLATING
                translation_result = await self._translate_codebase(codebase, scope)
                result.translation_summary = self._summarize_translation(
                    translation_result
                )
                result.artifacts.extend(
                    self._create_translation_artifacts(translation_result)
                )

            # Phase 4: Generate Recommendations
            result.recommendations = self._generate_recommendations(
                result.analysis_report,
                result.architecture_assessment,
                result.translation_summary,
            )

            # Phase 5: Validation
            result.status = TransformStatus.VALIDATING
            result.validation = await self._validate_transformation(result)

            # Determine final status
            if result.validation and result.validation.passed:
                result.status = TransformStatus.COMPLETED
            elif (
                result.translation_summary
                and result.translation_summary.manual_review_count > 0
            ):
                result.status = TransformStatus.NEEDS_REVIEW
            else:
                result.status = TransformStatus.COMPLETED

        except Exception as e:
            result.status = TransformStatus.FAILED
            result.recommendations.append(
                ModernizationRecommendation(
                    category="Error",
                    title="Workflow Failed",
                    description=str(e),
                    priority="critical",
                    effort_estimate="N/A",
                )
            )

        result.completed_at = datetime.now(timezone.utc)
        result.duration_seconds = (
            result.completed_at - result.started_at
        ).total_seconds()

        return result

    async def _analyze_codebase(self, codebase: LegacyCodebase) -> AnalysisReport:
        """Analyze legacy codebase."""
        report = AnalysisReport(
            codebase_name=codebase.name,
            platform=codebase.platform,
            total_files=len(codebase.source_files),
        )

        if codebase.platform == LegacyPlatform.MAINFRAME_COBOL:
            report = await self._analyze_cobol_codebase(codebase, report)
        elif codebase.platform in [LegacyPlatform.DOTNET_FRAMEWORK, LegacyPlatform.VB6]:
            report = await self._analyze_dotnet_codebase(codebase, report)
        else:
            # Generic analysis
            for _path, content in codebase.source_files.items():
                lines = content.split("\n")
                report.total_lines += len(lines)
                report.code_lines += sum(1 for line in lines if line.strip())

        # Estimate effort
        report.estimated_effort_weeks = self._estimate_modernization_effort(report)

        return report

    async def _analyze_cobol_codebase(
        self, codebase: LegacyCodebase, report: AnalysisReport
    ) -> AnalysisReport:
        """Analyze COBOL codebase."""
        programs: list[COBOLProgram] = []

        for path, content in codebase.source_files.items():
            if path.lower().endswith((".cbl", ".cob", ".cobol")):
                parse_result = await self._cobol_parser.parse(content, path)
                if parse_result.success and parse_result.program:
                    programs.append(parse_result.program)
                    report.total_lines += parse_result.program.total_lines
                    report.code_lines += parse_result.program.code_lines
                    report.comment_lines += parse_result.program.comment_lines

        # Aggregate metrics
        total_paragraphs = sum(len(p.paragraphs) for p in programs)
        total_data_items = sum(len(p.data_items) for p in programs)
        total_sql = sum(len(p.sql_statements) for p in programs)
        total_cics = sum(len(p.cics_commands) for p in programs)
        total_calls = sum(len(p.program_dependencies) for p in programs)

        report.complexity_metrics = {
            "programs": len(programs),
            "paragraphs": total_paragraphs,
            "data_items": total_data_items,
            "avg_program_size": report.code_lines / max(len(programs), 1),
            "avg_complexity": sum(
                p.cyclomatic_complexity for prog in programs for p in prog.paragraphs
            )
            / max(total_paragraphs, 1),
        }

        # Track language features
        if total_sql > 0:
            report.language_features_used.append("Embedded SQL (DB2)")
            report.database_operations.extend([f"SQL statements: {total_sql}"])

        if total_cics > 0:
            report.language_features_used.append("CICS Commands")

        if total_calls > 0:
            report.external_calls.extend(
                [
                    dep.program_name
                    for prog in programs
                    for dep in prog.program_dependencies
                ]
            )

        # Identify challenges
        if total_sql > 0:
            report.modernization_challenges.append(
                "DB2 SQL requires database migration strategy"
            )
        if total_cics > 0:
            report.modernization_challenges.append(
                "CICS commands require transaction management redesign"
            )
        if any(len(p.copybooks) > 10 for p in programs):
            report.modernization_challenges.append(
                "Complex copybook dependencies need careful refactoring"
            )

        return report

    async def _analyze_dotnet_codebase(
        self, codebase: LegacyCodebase, report: AnalysisReport
    ) -> AnalysisReport:
        """Analyze .NET codebase."""
        projects: list[DotNetProject] = []

        for path, content in codebase.source_files.items():
            if path.endswith(".csproj") or path.endswith(".vbproj"):
                parse_result = await self._dotnet_parser.parse_project(content, path)
                if parse_result.success and parse_result.project:
                    projects.append(parse_result.project)

        # Analyze source files
        for path, content in codebase.source_files.items():
            if path.endswith(".cs") or path.endswith(".vb"):
                lines = content.split("\n")
                report.total_lines += len(lines)
                for line in lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("//"):
                        report.code_lines += 1
                    elif stripped.startswith("//"):
                        report.comment_lines += 1

        # Aggregate metrics from projects
        total_types = sum(len(p.types) for p in projects)
        total_packages = sum(len(p.nuget_packages) for p in projects)

        report.complexity_metrics = {
            "projects": len(projects),
            "types": total_types,
            "nuget_packages": total_packages,
            "avg_types_per_project": total_types / max(len(projects), 1),
        }

        # Track features
        for project in projects:
            if project.framework.value == "framework":
                report.language_features_used.append(".NET Framework")
                report.modernization_challenges.append("Requires migration to .NET 6/8")

            # Check for legacy patterns
            for pattern in project.patterns:
                if hasattr(pattern.pattern, "value"):
                    report.language_features_used.append(pattern.pattern.value)

        return report

    async def _assess_architecture(
        self,
        codebase: LegacyCodebase,
        analysis: AnalysisReport,
        scope: TransformationScope,
    ) -> ArchitectureAssessment:
        """Assess architecture for modernization."""
        from .architecture_reimaginer import (
            ArchitectureStyle,
            ComponentType,
            SystemComponent,
            TechnologyStack,
        )

        # Build current architecture model from analysis
        components = []

        # Create component for main application
        tech_stack = []
        if codebase.platform == LegacyPlatform.MAINFRAME_COBOL:
            tech_stack.append(
                TechnologyStack(name="COBOL", category="language", is_legacy=True)
            )
            if "Embedded SQL" in analysis.language_features_used:
                tech_stack.append(
                    TechnologyStack(
                        name="DB2",
                        category="database",
                        is_legacy=True,
                        modern_alternative="PostgreSQL/Aurora",
                    )
                )

        elif codebase.platform == LegacyPlatform.DOTNET_FRAMEWORK:
            tech_stack.append(
                TechnologyStack(
                    name=".NET Framework",
                    category="runtime",
                    is_legacy=True,
                    modern_alternative=".NET 8",
                )
            )

        components.append(
            SystemComponent(
                id="main-app",
                name=codebase.name,
                component_type=ComponentType.BACKEND_SERVICE,
                technology_stack=tech_stack,
                responsibilities=["Core business logic"],
                estimated_lines_of_code=analysis.code_lines,
            )
        )

        current = CurrentArchitecture(
            name=codebase.name,
            style=ArchitectureStyle.MONOLITH,
            components=components,
            documentation_quality=(
                "low"
                if analysis.comment_lines / max(analysis.total_lines, 1) < 0.1
                else "medium"
            ),
        )

        # Run architecture assessment
        assessment = await self._reimaginer.analyze_architecture(
            current,
            scope.cloud_provider,
            (
                ModernizationStrategy.REFACTOR
                if scope.modernize_patterns
                else ModernizationStrategy.REPLATFORM
            ),
        )

        return assessment

    async def _translate_codebase(
        self, codebase: LegacyCodebase, scope: TransformationScope
    ) -> TranslationResult:
        """Translate codebase to target language."""
        # Determine source and target languages
        source_lang = self._get_source_language(codebase.platform)
        target_lang = self._get_target_language(scope.target_platform)

        config = TranslationConfig(
            source_language=source_lang,
            target_language=target_lang,
            strategy=(
                TranslationStrategy.IDIOMATIC
                if scope.modernize_patterns
                else TranslationStrategy.LITERAL
            ),
            generate_tests=scope.generate_tests,
            use_modern_patterns=scope.modernize_patterns,
        )

        # Aggregate translation results
        all_results: list[TranslationResult] = []

        for path, content in codebase.source_files.items():
            if self._is_translatable_file(path, codebase.platform):
                result = await self._translator.translate(content, config, path)
                all_results.append(result)

        # Combine results
        if not all_results:
            return TranslationResult(status=TranslationStatus.COMPLETED)

        combined = TranslationResult(
            status=all_results[0].status,
            files=[f for r in all_results for f in r.files],
            test_cases=[t for r in all_results for t in r.test_cases],
            type_mappings_used=all_results[0].type_mappings_used if all_results else [],
            overall_confidence=(
                all_results[0].overall_confidence
                if all_results
                else ConfidenceLevel.HIGH
            ),
            total_source_lines=sum(r.total_source_lines for r in all_results),
            total_target_lines=sum(r.total_target_lines for r in all_results),
            warnings_count=sum(r.warnings_count for r in all_results),
            manual_review_count=sum(r.manual_review_count for r in all_results),
        )

        return combined

    def _get_source_language(self, platform: LegacyPlatform) -> SourceLanguage:
        """Map platform to source language."""
        mapping = {
            LegacyPlatform.MAINFRAME_COBOL: SourceLanguage.COBOL,
            LegacyPlatform.DOTNET_FRAMEWORK: SourceLanguage.CSHARP,
            LegacyPlatform.VB6: SourceLanguage.VB6,
            LegacyPlatform.JAVA_LEGACY: SourceLanguage.JAVA,
        }
        return mapping.get(platform, SourceLanguage.COBOL)

    def _get_target_language(self, platform: TargetPlatform) -> TargetLanguage:
        """Map platform to target language."""
        mapping = {
            TargetPlatform.CLOUD_NATIVE: TargetLanguage.PYTHON,
            TargetPlatform.SERVERLESS: TargetLanguage.PYTHON,
            TargetPlatform.CONTAINERIZED: TargetLanguage.JAVA,
            TargetPlatform.DOTNET_CORE: TargetLanguage.CSHARP,
            TargetPlatform.JAVA_SPRING: TargetLanguage.JAVA,
            TargetPlatform.PYTHON: TargetLanguage.PYTHON,
            TargetPlatform.NODEJS: TargetLanguage.TYPESCRIPT,
        }
        return mapping.get(platform, TargetLanguage.PYTHON)

    def _is_translatable_file(self, path: str, platform: LegacyPlatform) -> bool:
        """Check if file should be translated."""
        path_lower = path.lower()

        if platform == LegacyPlatform.MAINFRAME_COBOL:
            return path_lower.endswith((".cbl", ".cob", ".cobol"))
        elif platform in [LegacyPlatform.DOTNET_FRAMEWORK, LegacyPlatform.VB6]:
            return path_lower.endswith((".cs", ".vb"))
        elif platform == LegacyPlatform.JAVA_LEGACY:
            return path_lower.endswith(".java")

        return False

    def _summarize_translation(self, result: TranslationResult) -> TranslationSummary:
        """Summarize translation result."""
        if not result.files:
            return TranslationSummary(
                source_language="unknown", target_language="unknown"
            )

        first_file = result.files[0]

        high_confidence = sum(1 for f in result.files if f.confidence.value == "high")

        return TranslationSummary(
            source_language=first_file.source_language.value,
            target_language=first_file.target_language.value,
            files_translated=len(result.files),
            total_source_lines=result.total_source_lines,
            total_target_lines=result.total_target_lines,
            translation_ratio=result.total_target_lines
            / max(result.total_source_lines, 1),
            high_confidence_percent=(high_confidence / max(len(result.files), 1)) * 100,
            warnings_count=result.warnings_count,
            manual_review_count=result.manual_review_count,
        )

    def _create_translation_artifacts(
        self, result: TranslationResult
    ) -> list[TransformationArtifact]:
        """Create artifacts from translation result."""
        artifacts = []

        for translated_file in result.files:
            artifacts.append(
                TransformationArtifact(
                    artifact_type="translated_code",
                    name=translated_file.target_path.split("/")[-1],
                    path=translated_file.target_path,
                    content=translated_file.translated_code,
                    metadata={
                        "source_path": translated_file.source_path,
                        "confidence": translated_file.confidence.value,
                        "warnings": len(translated_file.warnings),
                    },
                )
            )

        for test_case in result.test_cases:
            artifacts.append(
                TransformationArtifact(
                    artifact_type="test_case",
                    name=test_case.name,
                    path=f"tests/{test_case.name}.py",
                    content=test_case.test_code,
                    metadata={
                        "original_function": test_case.original_function,
                        "translated_function": test_case.translated_function,
                    },
                )
            )

        return artifacts

    def _generate_recommendations(
        self,
        analysis: AnalysisReport | None,
        assessment: ArchitectureAssessment | None,
        translation: TranslationSummary | None,
    ) -> list[ModernizationRecommendation]:
        """Generate modernization recommendations."""
        recommendations = []

        # Analysis-based recommendations
        if analysis:
            if analysis.estimated_effort_weeks > 20:
                recommendations.append(
                    ModernizationRecommendation(
                        category="Planning",
                        title="Consider Phased Approach",
                        description=f"Estimated effort of {analysis.estimated_effort_weeks} weeks suggests a phased migration approach",
                        priority="high",
                        effort_estimate="Ongoing",
                        benefits=[
                            "Reduced risk",
                            "Incremental value delivery",
                            "Learning opportunities",
                        ],
                        risks=["Longer total timeline", "Parallel system maintenance"],
                    )
                )

            for challenge in analysis.modernization_challenges:
                recommendations.append(
                    ModernizationRecommendation(
                        category="Technical",
                        title="Address Challenge",
                        description=challenge,
                        priority="medium",
                        effort_estimate="Varies",
                    )
                )

        # Architecture-based recommendations
        if assessment:
            if assessment.target_architecture.decomposition:
                svc_count = (
                    assessment.target_architecture.decomposition.estimated_total_services
                )
                recommendations.append(
                    ModernizationRecommendation(
                        category="Architecture",
                        title="Microservices Decomposition",
                        description=f"Consider decomposing into {svc_count} services",
                        priority="high",
                        effort_estimate=f"{svc_count * 4} weeks",
                        benefits=[
                            "Independent scaling",
                            "Technology flexibility",
                            "Team autonomy",
                        ],
                        risks=[
                            "Distributed system complexity",
                            "Data consistency challenges",
                        ],
                    )
                )

        # Translation-based recommendations
        if translation:
            if translation.manual_review_count > 0:
                recommendations.append(
                    ModernizationRecommendation(
                        category="Code Quality",
                        title="Manual Review Required",
                        description=f"{translation.manual_review_count} code sections need manual review",
                        priority="high",
                        effort_estimate=f"{translation.manual_review_count * 2} hours",
                        benefits=["Ensure correctness", "Validate business logic"],
                        risks=["Potential bugs if skipped"],
                    )
                )

            if translation.high_confidence_percent < 80:
                recommendations.append(
                    ModernizationRecommendation(
                        category="Code Quality",
                        title="Extensive Testing Recommended",
                        description=f"Only {translation.high_confidence_percent:.0f}% of translations are high confidence",
                        priority="high",
                        effort_estimate="2-4 weeks",
                        benefits=["Catch translation errors", "Validate functionality"],
                    )
                )

        # Standard recommendations
        recommendations.append(
            ModernizationRecommendation(
                category="Best Practices",
                title="Implement CI/CD Pipeline",
                description="Set up automated testing and deployment",
                priority="medium",
                effort_estimate="1-2 weeks",
                benefits=["Faster deployments", "Quality assurance", "Consistency"],
            )
        )

        recommendations.append(
            ModernizationRecommendation(
                category="Best Practices",
                title="Implement Observability",
                description="Add logging, metrics, and tracing",
                priority="medium",
                effort_estimate="1 week",
                benefits=["Debugging", "Performance monitoring", "Incident response"],
            )
        )

        return recommendations

    async def _validate_transformation(
        self, result: TransformWorkflowResult
    ) -> ValidationResult:
        """Validate transformation result."""
        validation = ValidationResult(passed=True, total_checks=0)

        # Check analysis completeness
        validation.total_checks += 1
        if result.analysis_report and result.analysis_report.total_lines > 0:
            validation.passed_checks += 1
        else:
            validation.failed_checks += 1
            validation.errors.append("Analysis report incomplete")

        # Check translation quality
        if result.translation_summary:
            validation.total_checks += 1
            if result.translation_summary.high_confidence_percent >= 70:
                validation.passed_checks += 1
            else:
                validation.warnings.append(
                    f"Translation confidence below threshold: {result.translation_summary.high_confidence_percent:.0f}%"
                )
                validation.passed_checks += 1  # Warning, not failure

            validation.total_checks += 1
            if result.translation_summary.files_translated > 0:
                validation.passed_checks += 1
            else:
                validation.failed_checks += 1
                validation.errors.append("No files were translated")

        # Check artifacts generated
        validation.total_checks += 1
        if result.artifacts:
            validation.passed_checks += 1
        else:
            validation.warnings.append("No artifacts generated")
            validation.passed_checks += 1  # Warning, not failure

        # Determine overall pass/fail
        validation.passed = validation.failed_checks == 0

        return validation

    def _estimate_modernization_effort(self, report: AnalysisReport) -> int:
        """Estimate modernization effort in weeks."""
        # Base estimate: 1 week per 5000 lines
        base_weeks = report.code_lines / 5000

        # Adjust for complexity
        if report.complexity_metrics.get("avg_complexity", 0) > 10:
            base_weeks *= 1.5

        # Adjust for challenges
        base_weeks += len(report.modernization_challenges) * 2

        # Adjust for database operations
        if report.database_operations:
            base_weeks += 4

        # Minimum 2 weeks, maximum reasonable cap
        return max(2, min(int(base_weeks), 104))

    async def get_supported_transformations(self) -> list[dict[str, str]]:
        """Get list of supported transformation paths."""
        return [
            {"source": "Mainframe COBOL", "target": "Python", "quality": "high"},
            {"source": "Mainframe COBOL", "target": "Java", "quality": "high"},
            {"source": ".NET Framework", "target": ".NET Core/8", "quality": "high"},
            {"source": "VB.NET", "target": "C#", "quality": "high"},
            {"source": "Java Legacy", "target": "Kotlin", "quality": "medium"},
            {"source": "Java Legacy", "target": "Python", "quality": "medium"},
        ]

    async def analyze_single_file(
        self, content: str, file_path: str, platform: LegacyPlatform
    ) -> dict[str, Any]:
        """Analyze a single source file."""
        if platform == LegacyPlatform.MAINFRAME_COBOL:
            result = await self._cobol_parser.parse(content, file_path)
            if result.success and result.program:
                metrics = await self._cobol_parser.get_program_metrics(result.program)
                return {
                    "success": True,
                    "program_id": result.program.program_id,
                    "metrics": metrics,
                    "has_db2": result.program.has_db2,
                    "has_cics": result.program.has_cics,
                    "complexity": result.program.complexity.value,
                }
            return {"success": False, "errors": [e.message for e in result.errors]}

        elif platform in [LegacyPlatform.DOTNET_FRAMEWORK, LegacyPlatform.VB6]:
            source_file = await self._dotnet_parser.parse_source_file(
                content, file_path
            )
            return {
                "success": True,
                "namespace": source_file.namespace,
                "types_count": len(source_file.types),
                "total_lines": source_file.total_lines,
                "code_lines": source_file.code_lines,
                "using_directives": len(source_file.using_directives),
            }

        return {"success": False, "errors": ["Unsupported platform"]}

    async def translate_single_file(
        self,
        content: str,
        file_path: str,
        source_platform: LegacyPlatform,
        target_platform: TargetPlatform,
    ) -> dict[str, Any]:
        """Translate a single source file."""
        source_lang = self._get_source_language(source_platform)
        target_lang = self._get_target_language(target_platform)

        config = TranslationConfig(
            source_language=source_lang,
            target_language=target_lang,
            strategy=TranslationStrategy.IDIOMATIC,
            generate_tests=True,
        )

        result = await self._translator.translate(content, config, file_path)

        if result.files:
            first_file = result.files[0]
            return {
                "success": True,
                "translated_code": first_file.translated_code,
                "confidence": first_file.confidence.value,
                "warnings": [w.message for w in first_file.warnings],
                "manual_review_items": len(first_file.manual_review_items),
                "test_cases": [tc.test_code for tc in result.test_cases],
            }

        return {"success": False, "errors": ["Translation failed"]}
