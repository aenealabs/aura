"""
Data Flow Analyzer
==================

ADR-056 Phase 3: Data Flow Analysis

Main orchestrator for comprehensive data flow analysis:
- Coordinates database, queue, API, and PII analysis
- Correlates findings into unified data flows
- Generates comprehensive reports
"""

import asyncio
import hashlib
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from src.services.data_flow.api_tracer import APICallTracer
from src.services.data_flow.database_tracer import DatabaseConnectionTracer
from src.services.data_flow.pii_detector import PIIDetectionService
from src.services.data_flow.queue_analyzer import QueueFlowAnalyzer
from src.services.data_flow.report_generator import DataFlowReportGenerator
from src.services.data_flow.types import (
    APIEndpoint,
    DatabaseConnection,
    DataFlow,
    DataFlowReport,
    DataFlowResult,
    DataFlowType,
    PIIField,
    QueueConnection,
)

logger = logging.getLogger(__name__)


class DataFlowAnalyzer:
    """Main orchestrator for data flow analysis.

    Coordinates all analysis services:
    - DatabaseConnectionTracer: Database connection detection
    - QueueFlowAnalyzer: Message queue detection
    - APICallTracer: API endpoint detection
    - PIIDetectionService: PII field detection
    - DataFlowReportGenerator: Report generation

    Correlates findings into unified data flows and generates
    comprehensive reports with Mermaid diagrams.

    Attributes:
        use_mock: If True, use mock data for all services
        database_tracer: Database connection tracer
        queue_analyzer: Queue flow analyzer
        api_tracer: API call tracer
        pii_detector: PII detection service
        report_generator: Report generator
    """

    def __init__(
        self,
        use_mock: bool = False,
        database_tracer: DatabaseConnectionTracer | None = None,
        queue_analyzer: QueueFlowAnalyzer | None = None,
        api_tracer: APICallTracer | None = None,
        pii_detector: PIIDetectionService | None = None,
        report_generator: DataFlowReportGenerator | None = None,
    ) -> None:
        """Initialize DataFlowAnalyzer.

        Args:
            use_mock: If True, use mock data for all services
            database_tracer: Optional custom database tracer
            queue_analyzer: Optional custom queue analyzer
            api_tracer: Optional custom API tracer
            pii_detector: Optional custom PII detector
            report_generator: Optional custom report generator
        """
        self.use_mock = use_mock
        self.database_tracer = database_tracer or DatabaseConnectionTracer(
            use_mock=use_mock
        )
        self.queue_analyzer = queue_analyzer or QueueFlowAnalyzer(use_mock=use_mock)
        self.api_tracer = api_tracer or APICallTracer(use_mock=use_mock)
        self.pii_detector = pii_detector or PIIDetectionService(use_mock=use_mock)
        self.report_generator = report_generator or DataFlowReportGenerator(
            use_mock=use_mock
        )

    async def analyze(
        self,
        repository_id: str,
        repository_path: str | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> DataFlowResult:
        """Perform comprehensive data flow analysis.

        Args:
            repository_id: Unique identifier for the repository
            repository_path: Path to repository root (default: current directory)
            include_patterns: Glob patterns to include (default: all Python files)
            exclude_patterns: Glob patterns to exclude

        Returns:
            DataFlowResult with all detected connections and flows
        """
        start_time = time.time()

        repository_path = repository_path or "."
        exclude_patterns = exclude_patterns or [
            "**/test_*.py",
            "**/__pycache__/**",
            "**/venv/**",
            "**/.venv/**",
            "**/node_modules/**",
            "**/dist/**",
            "**/build/**",
        ]

        # Initialize result
        result = DataFlowResult(
            repository_id=repository_id,
            analyzed_at=datetime.now(timezone.utc),
        )

        try:
            # Run all analyzers concurrently
            (
                database_connections,
                queue_connections,
                api_endpoints,
                pii_fields,
                files_analyzed,
            ) = await self._run_all_analyzers(
                repository_path,
                exclude_patterns,
            )

            # Store results
            result.database_connections = database_connections
            result.queue_connections = queue_connections
            result.api_endpoints = api_endpoints
            result.pii_fields = pii_fields
            result.files_analyzed = files_analyzed

            # Correlate findings into data flows
            result.data_flows = self._correlate_data_flows(
                database_connections,
                queue_connections,
                api_endpoints,
                pii_fields,
            )

            # Add any warnings
            result.warnings = self._generate_warnings(result)

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            result.errors.append(str(e))

        # Calculate analysis time
        result.analysis_time_ms = (time.time() - start_time) * 1000

        return result

    async def _run_all_analyzers(
        self,
        repository_path: str,
        exclude_patterns: list[str],
    ) -> tuple[
        list[DatabaseConnection],
        list[QueueConnection],
        list[APIEndpoint],
        list[PIIField],
        int,
    ]:
        """Run all analyzers concurrently.

        Args:
            repository_path: Path to repository
            exclude_patterns: Patterns to exclude

        Returns:
            Tuple of (database_connections, queue_connections,
                     api_endpoints, pii_fields, files_count)
        """
        # Count files first
        path = Path(repository_path)
        files_count = sum(
            1
            for _ in path.glob("**/*.py")
            if not any(_.match(pattern) for pattern in exclude_patterns)
        )

        # Run analyzers concurrently
        results = await asyncio.gather(
            self.database_tracer.trace_directory(
                repository_path, exclude_patterns=exclude_patterns
            ),
            self.queue_analyzer.analyze_directory(
                repository_path, exclude_patterns=exclude_patterns
            ),
            self.api_tracer.trace_directory(
                repository_path, exclude_patterns=exclude_patterns
            ),
            self.pii_detector.detect_in_directory(
                repository_path, exclude_patterns=exclude_patterns
            ),
            return_exceptions=True,
        )

        # Handle results, converting exceptions to empty lists with warnings
        database_connections: list[DatabaseConnection] = []
        queue_connections: list[QueueConnection] = []
        api_endpoints: list[APIEndpoint] = []
        pii_fields: list[PIIField] = []

        if isinstance(results[0], list):
            database_connections = results[0]
        else:
            logger.warning(f"Database analysis failed: {results[0]}")

        if isinstance(results[1], list):
            queue_connections = results[1]
        else:
            logger.warning(f"Queue analysis failed: {results[1]}")

        if isinstance(results[2], list):
            api_endpoints = results[2]
        else:
            logger.warning(f"API analysis failed: {results[2]}")

        if isinstance(results[3], list):
            pii_fields = results[3]
        else:
            logger.warning(f"PII analysis failed: {results[3]}")

        return (
            database_connections,
            queue_connections,
            api_endpoints,
            pii_fields,
            files_count,
        )

    def _correlate_data_flows(
        self,
        database_connections: list[DatabaseConnection],
        queue_connections: list[QueueConnection],
        api_endpoints: list[APIEndpoint],
        pii_fields: list[PIIField],
    ) -> list[DataFlow]:
        """Correlate detected connections into data flows.

        Creates DataFlow objects representing how data moves between:
        - Services and databases
        - Services and queues
        - Services via APIs
        - Including PII field tracking

        Args:
            database_connections: Detected database connections
            queue_connections: Detected queue connections
            api_endpoints: Detected API endpoints
            pii_fields: Detected PII fields

        Returns:
            List of correlated DataFlow objects
        """
        flows: list[DataFlow] = []

        # Create PII lookup by file for correlation
        pii_by_file: dict[str, list[PIIField]] = {}
        for field in pii_fields:
            if field.source_file not in pii_by_file:
                pii_by_file[field.source_file] = []
            pii_by_file[field.source_file].append(field)

        # Create database flows
        for conn in database_connections:
            service_name = self._extract_service_name(conn.source_file)
            db_name = f"{conn.database_type.value}_db"

            # Check for PII in this file
            file_pii = pii_by_file.get(conn.source_file, [])
            pii_field_names = [f.field_name for f in file_pii]

            if conn.is_read:
                flow_id = self._generate_flow_id(db_name, service_name, "read")
                flows.append(
                    DataFlow(
                        flow_id=flow_id,
                        flow_type=DataFlowType.DATABASE_READ,
                        source_entity=db_name,
                        target_entity=service_name,
                        source_file=conn.source_file,
                        source_line=conn.source_line,
                        data_fields=conn.tables_accessed,
                        pii_fields=pii_field_names,
                        confidence=conn.confidence,
                    )
                )

            if conn.is_write:
                flow_id = self._generate_flow_id(service_name, db_name, "write")
                flows.append(
                    DataFlow(
                        flow_id=flow_id,
                        flow_type=DataFlowType.DATABASE_WRITE,
                        source_entity=service_name,
                        target_entity=db_name,
                        source_file=conn.source_file,
                        source_line=conn.source_line,
                        data_fields=conn.tables_accessed,
                        pii_fields=pii_field_names,
                        confidence=conn.confidence,
                    )
                )

        # Create queue flows
        for conn in queue_connections:
            service_name = self._extract_service_name(conn.source_file)

            # Check for PII in this file
            file_pii = pii_by_file.get(conn.source_file, [])
            pii_field_names = [f.field_name for f in file_pii]

            if conn.is_producer:
                flow_id = self._generate_flow_id(
                    service_name, conn.queue_name, "produce"
                )
                flows.append(
                    DataFlow(
                        flow_id=flow_id,
                        flow_type=DataFlowType.QUEUE_PRODUCE,
                        source_entity=service_name,
                        target_entity=conn.queue_name,
                        source_file=conn.source_file,
                        source_line=conn.source_line,
                        pii_fields=pii_field_names,
                        is_cross_boundary=True,  # Queue flows typically cross boundaries
                        confidence=conn.confidence,
                    )
                )

            if conn.is_consumer:
                flow_id = self._generate_flow_id(
                    conn.queue_name, service_name, "consume"
                )
                flows.append(
                    DataFlow(
                        flow_id=flow_id,
                        flow_type=DataFlowType.QUEUE_CONSUME,
                        source_entity=conn.queue_name,
                        target_entity=service_name,
                        source_file=conn.source_file,
                        source_line=conn.source_line,
                        pii_fields=pii_field_names,
                        is_cross_boundary=True,
                        confidence=conn.confidence,
                    )
                )

        # Create API flows
        for endpoint in api_endpoints:
            service_name = self._extract_service_name(endpoint.source_file)

            # Check for PII in this file
            file_pii = pii_by_file.get(endpoint.source_file, [])
            pii_field_names = [f.field_name for f in file_pii]

            if endpoint.is_external:
                # External API call
                external_service = self._extract_external_service(endpoint.url_pattern)
                flow_id = self._generate_flow_id(
                    service_name, external_service, "api_call"
                )
                flows.append(
                    DataFlow(
                        flow_id=flow_id,
                        flow_type=DataFlowType.API_CALL,
                        source_entity=service_name,
                        target_entity=external_service,
                        source_file=endpoint.source_file,
                        source_line=endpoint.source_line,
                        pii_fields=pii_field_names,
                        is_cross_boundary=True,
                        encryption_in_transit=endpoint.url_pattern.startswith("https"),
                        confidence=endpoint.confidence,
                    )
                )
            else:
                # Internal endpoint - receives data
                flow_id = self._generate_flow_id(
                    "client", service_name, endpoint.method
                )
                flows.append(
                    DataFlow(
                        flow_id=flow_id,
                        flow_type=DataFlowType.API_RECEIVE,
                        source_entity="client",
                        target_entity=service_name,
                        source_file=endpoint.source_file,
                        source_line=endpoint.source_line,
                        data_fields=[endpoint.url_pattern],
                        pii_fields=pii_field_names,
                        confidence=endpoint.confidence,
                    )
                )

        return flows

    def _extract_service_name(self, file_path: str) -> str:
        """Extract service name from file path.

        Args:
            file_path: Path to source file

        Returns:
            Extracted service name
        """
        path = Path(file_path)
        parts = path.parts

        # Look for common service patterns
        for i, part in enumerate(parts):
            if part in {"services", "api", "handlers", "controllers", "routes"}:
                if i + 1 < len(parts):
                    return parts[i + 1].replace(".py", "")

        # Fall back to parent directory name
        if len(parts) >= 2:
            return parts[-2]

        return path.stem

    def _extract_external_service(self, url: str) -> str:
        """Extract external service name from URL.

        Args:
            url: URL pattern

        Returns:
            External service name
        """
        if "://" in url:
            domain = url.split("://")[1].split("/")[0]
            # Extract main domain
            parts = domain.split(".")
            if len(parts) >= 2:
                # Handle api.github.com -> github
                if parts[0] in {"api", "www"}:
                    return parts[1]
                return parts[0]
            return domain
        return "external"

    def _generate_flow_id(self, source: str, target: str, operation: str) -> str:
        """Generate unique flow ID.

        Args:
            source: Source entity
            target: Target entity
            operation: Operation type

        Returns:
            Unique flow identifier
        """
        content = f"{source}:{target}:{operation}"
        return f"flow-{hashlib.sha256(content.encode()).hexdigest()[:12]}"

    def _generate_warnings(self, result: DataFlowResult) -> list[str]:
        """Generate warnings based on analysis results.

        Args:
            result: Analysis result

        Returns:
            List of warning messages
        """
        warnings: list[str] = []

        # Check for PII in cross-boundary flows
        pii_cross_boundary = sum(
            1
            for flow in result.data_flows
            if flow.is_cross_boundary and flow.pii_fields
        )
        if pii_cross_boundary > 0:
            warnings.append(
                f"PII data detected in {pii_cross_boundary} cross-boundary flows"
            )

        # Check for unencrypted external API calls
        unencrypted_api = sum(
            1
            for flow in result.data_flows
            if flow.flow_type == DataFlowType.API_CALL
            and not flow.encryption_in_transit
        )
        if unencrypted_api > 0:
            warnings.append(f"{unencrypted_api} external API calls may not use TLS")

        # Check for high PII count
        restricted_pii = sum(
            1
            for field in result.pii_fields
            if field.classification.value == "restricted"
        )
        if restricted_pii > 10:
            warnings.append(
                f"High number of restricted PII fields detected: {restricted_pii}"
            )

        return warnings

    async def generate_report(
        self,
        result: DataFlowResult,
        include_diagrams: bool = True,
        include_recommendations: bool = True,
    ) -> DataFlowReport:
        """Generate comprehensive data flow report.

        Args:
            result: DataFlowResult from analysis
            include_diagrams: If True, generate Mermaid diagrams
            include_recommendations: If True, include recommendations

        Returns:
            Generated DataFlowReport
        """
        return await self.report_generator.generate_report(
            result,
            include_diagrams=include_diagrams,
            include_recommendations=include_recommendations,
        )

    async def analyze_and_report(
        self,
        repository_id: str,
        repository_path: str | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> tuple[DataFlowResult, DataFlowReport]:
        """Perform analysis and generate report in one call.

        Convenience method that combines analyze() and generate_report().

        Args:
            repository_id: Unique identifier for the repository
            repository_path: Path to repository root
            include_patterns: Glob patterns to include
            exclude_patterns: Glob patterns to exclude

        Returns:
            Tuple of (DataFlowResult, DataFlowReport)
        """
        result = await self.analyze(
            repository_id=repository_id,
            repository_path=repository_path,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        )

        report = await self.generate_report(result)

        return result, report


def create_data_flow_analyzer(use_mock: bool = False) -> DataFlowAnalyzer:
    """Factory function to create DataFlowAnalyzer.

    Args:
        use_mock: If True, create analyzer with mock data

    Returns:
        Configured DataFlowAnalyzer instance
    """
    return DataFlowAnalyzer(use_mock=use_mock)
