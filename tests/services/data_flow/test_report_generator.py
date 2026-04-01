"""
Tests for Data Flow Report Generator
====================================

ADR-056 Phase 3: Data Flow Analysis

Tests for report generation.
"""

import platform

import pytest

from src.services.data_flow.report_generator import DataFlowReportGenerator
from src.services.data_flow.types import (
    APIEndpoint,
    ComplianceFramework,
    DatabaseConnection,
    DatabaseType,
    DataClassification,
    DataFlow,
    DataFlowResult,
    DataFlowType,
    PIICategory,
    PIIField,
    QueueConnection,
    QueueType,
)

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestDataFlowReportGeneratorMock:
    """Tests for DataFlowReportGenerator in mock mode."""

    @pytest.fixture
    def generator(self):
        """Create mock generator."""
        return DataFlowReportGenerator(use_mock=True)

    @pytest.mark.asyncio
    async def test_generate_report_mock(self, generator):
        """Test mock report generation."""
        result = DataFlowResult(repository_id="repo-123")
        report = await generator.generate_report(result)

        assert report.report_id is not None
        assert report.repository_id == "repo-123"
        assert report.summary is not None
        assert len(report.diagrams) > 0
        assert len(report.recommendations) > 0


class TestDataFlowReportGeneratorReal:
    """Tests for DataFlowReportGenerator with real generation."""

    @pytest.fixture
    def generator(self):
        """Create real generator."""
        return DataFlowReportGenerator(use_mock=False)

    @pytest.fixture
    def sample_result(self):
        """Create sample analysis result."""
        return DataFlowResult(
            repository_id="test-repo",
            database_connections=[
                DatabaseConnection(
                    connection_id="db-001",
                    database_type=DatabaseType.POSTGRESQL,
                    source_file="src/services/user_service.py",
                    source_line=42,
                    tables_accessed=["users", "profiles"],
                    is_read=True,
                    is_write=True,
                    confidence=0.95,
                ),
                DatabaseConnection(
                    connection_id="db-002",
                    database_type=DatabaseType.REDIS,
                    source_file="src/services/cache_service.py",
                    source_line=20,
                    is_read=True,
                    is_write=True,
                    confidence=0.9,
                ),
            ],
            queue_connections=[
                QueueConnection(
                    connection_id="q-001",
                    queue_type=QueueType.SQS,
                    queue_name="user-events",
                    source_file="src/services/event_publisher.py",
                    source_line=30,
                    is_producer=True,
                    dlq_name="user-events-dlq",
                    confidence=0.95,
                ),
                QueueConnection(
                    connection_id="q-002",
                    queue_type=QueueType.SQS,
                    queue_name="user-events",
                    source_file="src/services/event_consumer.py",
                    source_line=25,
                    is_consumer=True,
                    confidence=0.95,
                ),
            ],
            api_endpoints=[
                APIEndpoint(
                    endpoint_id="api-001",
                    url_pattern="/api/v1/users",
                    method="GET",
                    source_file="src/api/user_endpoints.py",
                    source_line=15,
                    is_internal=True,
                    auth_type="bearer",
                    rate_limit={"requests": 100, "period": "minute"},
                    confidence=0.95,
                ),
                APIEndpoint(
                    endpoint_id="api-002",
                    url_pattern="https://api.stripe.com/v1/charges",
                    method="POST",
                    source_file="src/services/payment_service.py",
                    source_line=50,
                    is_internal=False,
                    is_external=True,
                    timeout_ms=30000,
                    confidence=0.9,
                ),
            ],
            pii_fields=[
                PIIField(
                    field_id="pii-001",
                    field_name="email",
                    pii_category=PIICategory.EMAIL,
                    source_file="src/models/user.py",
                    source_line=12,
                    entity_name="User",
                    compliance_tags=[
                        ComplianceFramework.GDPR,
                        ComplianceFramework.CCPA,
                    ],
                    classification=DataClassification.CONFIDENTIAL,
                    is_encrypted=False,
                    is_masked=True,
                    confidence=0.95,
                ),
                PIIField(
                    field_id="pii-002",
                    field_name="ssn",
                    pii_category=PIICategory.SSN,
                    source_file="src/models/employee.py",
                    source_line=18,
                    entity_name="Employee",
                    compliance_tags=[
                        ComplianceFramework.NIST_800_53,
                        ComplianceFramework.SOX,
                    ],
                    classification=DataClassification.RESTRICTED,
                    is_encrypted=True,
                    is_masked=True,
                    confidence=0.95,
                ),
                PIIField(
                    field_id="pii-003",
                    field_name="credit_card",
                    pii_category=PIICategory.CREDIT_CARD,
                    source_file="src/models/payment.py",
                    source_line=22,
                    entity_name="Payment",
                    compliance_tags=[ComplianceFramework.PCI_DSS],
                    classification=DataClassification.RESTRICTED,
                    is_encrypted=False,  # Not encrypted - should trigger warning
                    is_masked=False,
                    confidence=0.95,
                ),
            ],
            data_flows=[
                DataFlow(
                    flow_id="flow-001",
                    flow_type=DataFlowType.DATABASE_READ,
                    source_entity="postgresql_db",
                    target_entity="user_service",
                    source_file="src/services/user_service.py",
                    source_line=42,
                    pii_fields=["email"],
                    is_cross_boundary=False,
                    confidence=0.95,
                ),
                DataFlow(
                    flow_id="flow-002",
                    flow_type=DataFlowType.QUEUE_PRODUCE,
                    source_entity="event_publisher",
                    target_entity="user-events",
                    source_file="src/services/event_publisher.py",
                    source_line=30,
                    pii_fields=["email"],
                    is_cross_boundary=True,
                    confidence=0.95,
                ),
                DataFlow(
                    flow_id="flow-003",
                    flow_type=DataFlowType.API_CALL,
                    source_entity="payment_service",
                    target_entity="stripe",
                    source_file="src/services/payment_service.py",
                    source_line=50,
                    pii_fields=["credit_card"],
                    is_cross_boundary=True,
                    encryption_in_transit=True,
                    confidence=0.9,
                ),
            ],
            files_analyzed=50,
            analysis_time_ms=1234.5,
            warnings=["Some warning"],
        )

    @pytest.mark.asyncio
    async def test_generate_report_basic(self, generator, sample_result):
        """Test basic report generation."""
        report = await generator.generate_report(sample_result)

        assert report.report_id is not None
        assert report.repository_id == "test-repo"
        assert report.title is not None
        assert report.export_format == "markdown"

    @pytest.mark.asyncio
    async def test_generate_report_summary(self, generator, sample_result):
        """Test summary section generation."""
        report = await generator.generate_report(sample_result)

        assert "Executive Summary" in report.summary
        assert "Database Connections" in report.summary
        assert "2" in report.summary  # 2 database connections
        assert "3" in report.summary  # 3 PII fields

    @pytest.mark.asyncio
    async def test_generate_report_database_section(self, generator, sample_result):
        """Test database section generation."""
        report = await generator.generate_report(sample_result)

        assert "Database Connections" in report.database_section
        assert (
            "Postgresql" in report.database_section
            or "POSTGRESQL" in report.database_section.upper()
        )
        assert (
            "Redis" in report.database_section
            or "REDIS" in report.database_section.upper()
        )

    @pytest.mark.asyncio
    async def test_generate_report_queue_section(self, generator, sample_result):
        """Test queue section generation."""
        report = await generator.generate_report(sample_result)

        assert "Message Queues" in report.queue_section
        assert "SQS" in report.queue_section
        assert "user-events" in report.queue_section

    @pytest.mark.asyncio
    async def test_generate_report_api_section(self, generator, sample_result):
        """Test API section generation."""
        report = await generator.generate_report(sample_result)

        assert "API Endpoints" in report.api_section
        assert "Internal Endpoints" in report.api_section
        assert "External API Calls" in report.api_section
        assert "/api/v1/users" in report.api_section
        assert "stripe" in report.api_section.lower()

    @pytest.mark.asyncio
    async def test_generate_report_pii_section(self, generator, sample_result):
        """Test PII section generation."""
        report = await generator.generate_report(sample_result)

        assert "PII Inventory" in report.pii_section
        assert "email" in report.pii_section.lower()
        assert "ssn" in report.pii_section.lower()
        assert "Restricted" in report.pii_section

    @pytest.mark.asyncio
    async def test_generate_report_compliance_section(self, generator, sample_result):
        """Test compliance section generation."""
        report = await generator.generate_report(sample_result)

        assert "Compliance Analysis" in report.compliance_section
        assert "GDPR" in report.compliance_section
        assert (
            "PCI_DSS" in report.compliance_section
            or "PCI-DSS" in report.compliance_section
        )

    @pytest.mark.asyncio
    async def test_generate_report_diagrams(self, generator, sample_result):
        """Test diagram generation."""
        report = await generator.generate_report(sample_result, include_diagrams=True)

        assert len(report.diagrams) > 0
        # Should have various diagram types
        assert (
            "database_architecture" in report.diagrams
            or "queue_flows" in report.diagrams
        )

        # Diagrams should be Mermaid format
        for diagram in report.diagrams.values():
            assert "graph" in diagram or "flowchart" in diagram

    @pytest.mark.asyncio
    async def test_generate_report_no_diagrams(self, generator, sample_result):
        """Test report generation without diagrams."""
        report = await generator.generate_report(sample_result, include_diagrams=False)

        assert len(report.diagrams) == 0

    @pytest.mark.asyncio
    async def test_generate_report_recommendations(self, generator, sample_result):
        """Test recommendations generation."""
        report = await generator.generate_report(
            sample_result, include_recommendations=True
        )

        assert len(report.recommendations) > 0
        # Should flag unencrypted credit card
        assert any(
            "CRITICAL" in rec or "encrypted" in rec.lower()
            for rec in report.recommendations
        )

    @pytest.mark.asyncio
    async def test_generate_report_no_recommendations(self, generator, sample_result):
        """Test report generation without recommendations."""
        report = await generator.generate_report(
            sample_result, include_recommendations=False
        )

        assert len(report.recommendations) == 0

    @pytest.mark.asyncio
    async def test_generate_report_content(self, generator, sample_result):
        """Test full report content assembly."""
        report = await generator.generate_report(sample_result)

        # Content should include all sections
        assert "# Data Flow Analysis Report" in report.content
        assert "Executive Summary" in report.content
        assert "Database Connections" in report.content
        assert "Message Queues" in report.content
        assert "API Endpoints" in report.content
        assert "PII Inventory" in report.content
        assert "Compliance Analysis" in report.content

    @pytest.mark.asyncio
    async def test_generate_report_empty_result(self, generator):
        """Test report generation with empty result."""
        empty_result = DataFlowResult(repository_id="empty-repo")

        report = await generator.generate_report(empty_result)

        assert report.report_id is not None
        assert "No database connections detected" in report.database_section
        assert "No message queue connections detected" in report.queue_section
        assert "No API endpoints detected" in report.api_section
        assert "No PII fields detected" in report.pii_section


class TestDataFlowReportGeneratorEdgeCases:
    """Edge case tests for DataFlowReportGenerator."""

    @pytest.fixture
    def generator(self):
        """Create real generator."""
        return DataFlowReportGenerator(use_mock=False)

    @pytest.mark.asyncio
    async def test_large_result(self, generator):
        """Test report generation with large number of items."""
        # Create result with many items
        large_result = DataFlowResult(
            repository_id="large-repo",
            database_connections=[
                DatabaseConnection(
                    connection_id=f"db-{i}",
                    database_type=DatabaseType.POSTGRESQL,
                    source_file=f"src/service_{i}.py",
                    source_line=i,
                )
                for i in range(50)
            ],
            pii_fields=[
                PIIField(
                    field_id=f"pii-{i}",
                    field_name=f"field_{i}",
                    pii_category=PIICategory.EMAIL,
                    source_file=f"src/model_{i}.py",
                    source_line=i,
                )
                for i in range(100)
            ],
        )

        report = await generator.generate_report(large_result)

        assert report.report_id is not None
        # Should handle large datasets without error
        assert "50" in report.summary  # 50 database connections

    @pytest.mark.asyncio
    async def test_special_characters_in_names(self, generator):
        """Test report generation with special characters."""
        result = DataFlowResult(
            repository_id="special-repo",
            queue_connections=[
                QueueConnection(
                    connection_id="q-001",
                    queue_type=QueueType.SQS,
                    queue_name="queue-with-special_chars.and.dots",
                    source_file="src/service.py",
                    source_line=1,
                    is_producer=True,
                ),
            ],
        )

        report = await generator.generate_report(result)

        assert report.report_id is not None
        # Should handle special characters in queue names

    @pytest.mark.asyncio
    async def test_long_url_truncation(self, generator):
        """Test that long URLs are handled properly."""
        result = DataFlowResult(
            repository_id="url-repo",
            api_endpoints=[
                APIEndpoint(
                    endpoint_id="api-001",
                    url_pattern="https://very-long-domain.example.com/api/v1/really/long/path/to/resource/with/many/segments",
                    method="GET",
                    source_file="src/client.py",
                    source_line=1,
                    is_external=True,
                ),
            ],
        )

        report = await generator.generate_report(result)

        # Should generate report without error
        assert report.api_section is not None
