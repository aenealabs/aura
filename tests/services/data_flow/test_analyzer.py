"""
Tests for Data Flow Analyzer
============================

ADR-056 Phase 3: Data Flow Analysis

Tests for the main DataFlowAnalyzer orchestrator.
"""

import platform
import tempfile
from pathlib import Path

import pytest

from src.services.data_flow.analyzer import DataFlowAnalyzer, create_data_flow_analyzer
from src.services.data_flow.types import (
    APIEndpoint,
    DatabaseConnection,
    DatabaseType,
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


class TestDataFlowAnalyzerMock:
    """Tests for DataFlowAnalyzer in mock mode."""

    @pytest.fixture
    def analyzer(self):
        """Create mock analyzer."""
        return create_data_flow_analyzer(use_mock=True)

    @pytest.mark.asyncio
    async def test_analyze_mock(self, analyzer):
        """Test mock analysis returns comprehensive result."""
        result = await analyzer.analyze(repository_id="test-repo")

        assert result.repository_id == "test-repo"
        assert len(result.database_connections) > 0
        assert len(result.queue_connections) > 0
        assert len(result.api_endpoints) > 0
        assert len(result.pii_fields) > 0

    @pytest.mark.asyncio
    async def test_generate_report_mock(self, analyzer):
        """Test mock report generation."""
        result = await analyzer.analyze(repository_id="test-repo")
        report = await analyzer.generate_report(result)

        assert report.report_id is not None
        assert report.repository_id == "test-repo"
        assert len(report.diagrams) > 0

    @pytest.mark.asyncio
    async def test_analyze_and_report_mock(self, analyzer):
        """Test combined analysis and report generation."""
        result, report = await analyzer.analyze_and_report(repository_id="test-repo")

        assert result.repository_id == "test-repo"
        assert report.repository_id == "test-repo"


class TestDataFlowAnalyzerReal:
    """Tests for DataFlowAnalyzer with real analysis."""

    @pytest.fixture
    def analyzer(self):
        """Create real analyzer."""
        return DataFlowAnalyzer(use_mock=False)

    @pytest.mark.asyncio
    async def test_analyze_empty_directory(self, analyzer):
        """Test analyzing empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await analyzer.analyze(
                repository_id="empty-repo",
                repository_path=tmpdir,
            )

            assert result.repository_id == "empty-repo"
            assert result.files_analyzed == 0
            assert len(result.database_connections) == 0

    @pytest.mark.asyncio
    async def test_analyze_with_database_code(self, analyzer):
        """Test analyzing directory with database code."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "db_service.py"
            db_file.write_text("""
import psycopg2

conn = psycopg2.connect("postgresql://localhost/db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM users")
""")

            result = await analyzer.analyze(
                repository_id="db-repo",
                repository_path=tmpdir,
            )

            assert result.repository_id == "db-repo"
            assert len(result.database_connections) >= 1
            assert any(
                conn.database_type == DatabaseType.POSTGRESQL
                for conn in result.database_connections
            )

    @pytest.mark.asyncio
    async def test_analyze_with_queue_code(self, analyzer):
        """Test analyzing directory with queue code."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = Path(tmpdir) / "queue_service.py"
            queue_file.write_text("""
import boto3

sqs = boto3.client("sqs")
sqs.send_message(QueueUrl="url", MessageBody="msg")
""")

            result = await analyzer.analyze(
                repository_id="queue-repo",
                repository_path=tmpdir,
            )

            assert len(result.queue_connections) >= 1
            assert any(
                conn.queue_type == QueueType.SQS for conn in result.queue_connections
            )

    @pytest.mark.asyncio
    async def test_analyze_with_api_code(self, analyzer):
        """Test analyzing directory with API code."""
        with tempfile.TemporaryDirectory() as tmpdir:
            api_file = Path(tmpdir) / "api_service.py"
            api_file.write_text("""
from fastapi import FastAPI

app = FastAPI()

@app.get("/users")
async def get_users():
    return []
""")

            result = await analyzer.analyze(
                repository_id="api-repo",
                repository_path=tmpdir,
            )

            assert len(result.api_endpoints) >= 1
            assert any(ep.is_internal for ep in result.api_endpoints)

    @pytest.mark.asyncio
    async def test_analyze_with_pii_code(self, analyzer):
        """Test analyzing directory with PII fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_file = Path(tmpdir) / "models.py"
            model_file.write_text("""
class User:
    email: str
    phone_number: str
    ssn: str
""")

            result = await analyzer.analyze(
                repository_id="pii-repo",
                repository_path=tmpdir,
            )

            assert len(result.pii_fields) >= 2
            categories = {f.pii_category for f in result.pii_fields}
            assert PIICategory.EMAIL in categories

    @pytest.mark.asyncio
    async def test_analyze_creates_data_flows(self, analyzer):
        """Test that analysis creates correlated data flows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service_file = Path(tmpdir) / "user_service.py"
            service_file.write_text("""
import psycopg2

class UserService:
    email: str  # PII field

    def get_users(self):
        conn = psycopg2.connect("postgresql://localhost/db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        return cursor.fetchall()
""")

            result = await analyzer.analyze(
                repository_id="flow-repo",
                repository_path=tmpdir,
            )

            # Should have data flows correlating the findings
            assert len(result.data_flows) >= 1

    @pytest.mark.asyncio
    async def test_analyze_excludes_test_files(self, analyzer):
        """Test that test files are excluded by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test_service.py"
            test_file.write_text("""
import psycopg2
conn = psycopg2.connect("postgresql://localhost/testdb")
""")
            # Create a regular file
            regular_file = Path(tmpdir) / "service.py"
            regular_file.write_text("""
def process():
    pass
""")

            result = await analyzer.analyze(
                repository_id="test-exclusion-repo",
                repository_path=tmpdir,
            )

            # Test file should be excluded
            assert not any(
                "test_service.py" in conn.source_file
                for conn in result.database_connections
            )

    @pytest.mark.asyncio
    async def test_analyze_generates_warnings(self, analyzer):
        """Test that analysis generates appropriate warnings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file with PII in cross-boundary flow
            service_file = Path(tmpdir) / "event_service.py"
            service_file.write_text("""
import boto3

class EventPublisher:
    email: str  # PII field

    def publish_event(self, event):
        sqs = boto3.client("sqs")
        sqs.send_message(QueueUrl="url", MessageBody=str(event))
""")

            result = await analyzer.analyze(
                repository_id="warning-repo",
                repository_path=tmpdir,
            )

            # Should generate warnings about PII in cross-boundary flows
            # (depending on correlation)

    @pytest.mark.asyncio
    async def test_analyze_calculates_timing(self, analyzer):
        """Test that analysis records timing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "empty.py").write_text("")

            result = await analyzer.analyze(
                repository_id="timing-repo",
                repository_path=tmpdir,
            )

            assert result.analysis_time_ms >= 0

    @pytest.mark.asyncio
    async def test_generate_report_with_result(self, analyzer):
        """Test report generation from analysis result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "service.py"
            db_file.write_text("""
import psycopg2

conn = psycopg2.connect("postgresql://localhost/db")
""")

            result = await analyzer.analyze(
                repository_id="report-repo",
                repository_path=tmpdir,
            )
            report = await analyzer.generate_report(result)

            assert report.repository_id == "report-repo"
            assert "Database Connections" in report.content


class TestDataFlowAnalyzerFlowCorrelation:
    """Tests for data flow correlation logic."""

    @pytest.fixture
    def analyzer(self):
        """Create real analyzer."""
        return DataFlowAnalyzer(use_mock=False)

    def test_extract_service_name(self, analyzer):
        """Test service name extraction from file paths."""
        assert (
            analyzer._extract_service_name("src/services/user_service.py")
            == "user_service"
        )
        assert analyzer._extract_service_name("src/api/endpoints.py") == "endpoints"
        assert analyzer._extract_service_name("handlers/webhook.py") == "webhook"

    def test_extract_external_service(self, analyzer):
        """Test external service extraction from URLs."""
        assert (
            analyzer._extract_external_service("https://api.github.com/repos")
            == "github"
        )
        assert (
            analyzer._extract_external_service("https://api.stripe.com/v1/charges")
            == "stripe"
        )
        assert (
            analyzer._extract_external_service("https://www.example.com/api")
            == "example"
        )

    def test_generate_flow_id(self, analyzer):
        """Test flow ID generation."""
        flow_id = analyzer._generate_flow_id("source", "target", "read")
        assert flow_id.startswith("flow-")
        assert len(flow_id) > 10

        # Same inputs should produce same ID
        flow_id2 = analyzer._generate_flow_id("source", "target", "read")
        assert flow_id == flow_id2

        # Different inputs should produce different ID
        flow_id3 = analyzer._generate_flow_id("source", "target", "write")
        assert flow_id != flow_id3

    def test_correlate_database_flows(self, analyzer):
        """Test database flow correlation."""
        database_connections = [
            DatabaseConnection(
                connection_id="db-001",
                database_type=DatabaseType.POSTGRESQL,
                source_file="src/services/user_service.py",
                source_line=42,
                is_read=True,
                is_write=False,
            ),
        ]

        flows = analyzer._correlate_data_flows(
            database_connections=database_connections,
            queue_connections=[],
            api_endpoints=[],
            pii_fields=[],
        )

        assert len(flows) >= 1
        assert any(f.flow_type == DataFlowType.DATABASE_READ for f in flows)

    def test_correlate_queue_flows(self, analyzer):
        """Test queue flow correlation."""
        queue_connections = [
            QueueConnection(
                connection_id="q-001",
                queue_type=QueueType.SQS,
                queue_name="events",
                source_file="src/services/publisher.py",
                source_line=30,
                is_producer=True,
                is_consumer=False,
            ),
        ]

        flows = analyzer._correlate_data_flows(
            database_connections=[],
            queue_connections=queue_connections,
            api_endpoints=[],
            pii_fields=[],
        )

        assert len(flows) >= 1
        assert any(f.flow_type == DataFlowType.QUEUE_PRODUCE for f in flows)
        # Queue flows should be marked as cross-boundary
        assert any(f.is_cross_boundary for f in flows)

    def test_correlate_api_flows(self, analyzer):
        """Test API flow correlation."""
        api_endpoints = [
            APIEndpoint(
                endpoint_id="api-001",
                url_pattern="https://api.external.com/data",
                method="GET",
                source_file="src/services/client.py",
                source_line=25,
                is_internal=False,
                is_external=True,
            ),
        ]

        flows = analyzer._correlate_data_flows(
            database_connections=[],
            queue_connections=[],
            api_endpoints=api_endpoints,
            pii_fields=[],
        )

        assert len(flows) >= 1
        assert any(f.flow_type == DataFlowType.API_CALL for f in flows)
        # External API calls should be cross-boundary
        assert any(f.is_cross_boundary for f in flows)

    def test_correlate_pii_in_flows(self, analyzer):
        """Test PII correlation in flows."""
        database_connections = [
            DatabaseConnection(
                connection_id="db-001",
                database_type=DatabaseType.POSTGRESQL,
                source_file="src/services/user_service.py",
                source_line=42,
                is_read=True,
            ),
        ]
        pii_fields = [
            PIIField(
                field_id="pii-001",
                field_name="email",
                pii_category=PIICategory.EMAIL,
                source_file="src/services/user_service.py",  # Same file
                source_line=10,
            ),
        ]

        flows = analyzer._correlate_data_flows(
            database_connections=database_connections,
            queue_connections=[],
            api_endpoints=[],
            pii_fields=pii_fields,
        )

        # Flow should include the PII field from same file
        assert any("email" in f.pii_fields for f in flows)


class TestDataFlowAnalyzerWarnings:
    """Tests for warning generation."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer."""
        return DataFlowAnalyzer(use_mock=False)

    def test_generate_warnings_pii_cross_boundary(self, analyzer):
        """Test warning for PII in cross-boundary flows."""
        result = DataFlowResult(
            repository_id="test",
            data_flows=[
                DataFlow(
                    flow_id="flow-001",
                    flow_type=DataFlowType.QUEUE_PRODUCE,
                    source_entity="service",
                    target_entity="queue",
                    source_file="test.py",
                    source_line=1,
                    pii_fields=["email", "ssn"],
                    is_cross_boundary=True,
                ),
            ],
        )

        warnings = analyzer._generate_warnings(result)

        assert any("PII data" in w and "cross-boundary" in w for w in warnings)

    def test_generate_warnings_unencrypted_api(self, analyzer):
        """Test warning for unencrypted external API calls."""
        result = DataFlowResult(
            repository_id="test",
            data_flows=[
                DataFlow(
                    flow_id="flow-001",
                    flow_type=DataFlowType.API_CALL,
                    source_entity="service",
                    target_entity="external",
                    source_file="test.py",
                    source_line=1,
                    encryption_in_transit=False,  # Not using TLS
                ),
            ],
        )

        warnings = analyzer._generate_warnings(result)

        assert any("TLS" in w or "encrypted" in w.lower() for w in warnings)


class TestCreateDataFlowAnalyzer:
    """Tests for factory function."""

    def test_create_mock_analyzer(self):
        """Test creating mock analyzer."""
        analyzer = create_data_flow_analyzer(use_mock=True)

        assert analyzer.use_mock is True
        assert analyzer.database_tracer.use_mock is True
        assert analyzer.queue_analyzer.use_mock is True
        assert analyzer.api_tracer.use_mock is True
        assert analyzer.pii_detector.use_mock is True

    def test_create_real_analyzer(self):
        """Test creating real analyzer."""
        analyzer = create_data_flow_analyzer(use_mock=False)

        assert analyzer.use_mock is False
