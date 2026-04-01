"""
Data Flow Analysis Package
==========================

ADR-056 Phase 3: Data Flow Analysis

This package provides comprehensive data flow analysis capabilities:
- Database connection tracing and mapping
- Queue/event flow analysis (SQS, SNS, Kafka, RabbitMQ)
- API call chain tracing
- PII detection and classification
- Data flow visualization and reporting

Usage:
    from src.services.data_flow import (
        DataFlowAnalyzer,
        DatabaseConnectionTracer,
        QueueFlowAnalyzer,
        APICallTracer,
        PIIDetectionService,
        DataFlowReportGenerator,
        create_data_flow_analyzer,
    )

    # Create analyzer
    analyzer = create_data_flow_analyzer(use_mock=True)

    # Analyze repository
    result = await analyzer.analyze(repository_id="repo-123")

    # Generate report
    report = await analyzer.generate_report(result)
"""

from src.services.data_flow.analyzer import DataFlowAnalyzer, create_data_flow_analyzer
from src.services.data_flow.api_tracer import APICallTracer
from src.services.data_flow.database_tracer import DatabaseConnectionTracer
from src.services.data_flow.exceptions import (
    ConnectionParseError,
    DataFlowError,
    FlowAnalysisError,
    PIIDetectionError,
    ReportGenerationError,
)
from src.services.data_flow.pii_detector import PIIDetectionService
from src.services.data_flow.queue_analyzer import QueueFlowAnalyzer
from src.services.data_flow.report_generator import DataFlowReportGenerator
from src.services.data_flow.types import (  # Enums; Dataclasses
    APIEndpoint,
    ComplianceFramework,
    DatabaseConnection,
    DatabaseType,
    DataClassification,
    DataFlow,
    DataFlowReport,
    DataFlowResult,
    DataFlowType,
    PIICategory,
    PIIField,
    QueueConnection,
    QueueType,
)

__all__ = [
    # Types
    "DataFlowType",
    "DatabaseType",
    "QueueType",
    "PIICategory",
    "ComplianceFramework",
    "DataClassification",
    "DatabaseConnection",
    "QueueConnection",
    "APIEndpoint",
    "PIIField",
    "DataFlow",
    "DataFlowResult",
    "DataFlowReport",
    # Exceptions
    "DataFlowError",
    "ConnectionParseError",
    "PIIDetectionError",
    "FlowAnalysisError",
    "ReportGenerationError",
    # Services
    "DatabaseConnectionTracer",
    "QueueFlowAnalyzer",
    "APICallTracer",
    "PIIDetectionService",
    "DataFlowReportGenerator",
    "DataFlowAnalyzer",
    "create_data_flow_analyzer",
]
