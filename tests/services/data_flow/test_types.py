"""
Tests for Data Flow Types
=========================

ADR-056 Phase 3: Data Flow Analysis

Tests for type definitions and dataclasses.
"""

import platform
from datetime import datetime

import pytest

from src.services.data_flow.types import (
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

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestDataFlowType:
    """Tests for DataFlowType enum."""

    def test_all_flow_types_exist(self):
        """Verify all expected flow types are defined."""
        expected = [
            "DATABASE_READ",
            "DATABASE_WRITE",
            "QUEUE_PRODUCE",
            "QUEUE_CONSUME",
            "API_CALL",
            "API_RECEIVE",
            "FILE_READ",
            "FILE_WRITE",
            "CACHE_READ",
            "CACHE_WRITE",
            "EVENT_EMIT",
            "EVENT_LISTEN",
        ]
        for name in expected:
            assert hasattr(DataFlowType, name)

    def test_flow_type_values(self):
        """Verify flow type values are lowercase."""
        assert DataFlowType.DATABASE_READ.value == "database_read"
        assert DataFlowType.QUEUE_PRODUCE.value == "queue_produce"
        assert DataFlowType.API_CALL.value == "api_call"


class TestDatabaseType:
    """Tests for DatabaseType enum."""

    def test_all_database_types_exist(self):
        """Verify all expected database types are defined."""
        expected = [
            "POSTGRESQL",
            "MYSQL",
            "DYNAMODB",
            "MONGODB",
            "REDIS",
            "NEPTUNE",
            "OPENSEARCH",
            "ELASTICSEARCH",
            "SQLITE",
            "SQLSERVER",
            "ORACLE",
            "CASSANDRA",
            "UNKNOWN",
        ]
        for name in expected:
            assert hasattr(DatabaseType, name)

    def test_from_connection_string_postgresql(self):
        """Test PostgreSQL detection from connection string."""
        assert (
            DatabaseType.from_connection_string("postgresql://host:5432/db")
            == DatabaseType.POSTGRESQL
        )
        assert (
            DatabaseType.from_connection_string("postgres://host/db")
            == DatabaseType.POSTGRESQL
        )

    def test_from_connection_string_mysql(self):
        """Test MySQL detection from connection string."""
        assert (
            DatabaseType.from_connection_string("mysql://host:3306/db")
            == DatabaseType.MYSQL
        )
        assert (
            DatabaseType.from_connection_string("mariadb://host/db")
            == DatabaseType.MYSQL
        )

    def test_from_connection_string_dynamodb(self):
        """Test DynamoDB detection from connection string."""
        assert (
            DatabaseType.from_connection_string("dynamodb://localhost:8000")
            == DatabaseType.DYNAMODB
        )

    def test_from_connection_string_mongodb(self):
        """Test MongoDB detection from connection string."""
        assert (
            DatabaseType.from_connection_string("mongodb://host:27017/db")
            == DatabaseType.MONGODB
        )
        assert (
            DatabaseType.from_connection_string("mongo://host/db")
            == DatabaseType.MONGODB
        )

    def test_from_connection_string_redis(self):
        """Test Redis detection from connection string."""
        assert (
            DatabaseType.from_connection_string("redis://host:6379")
            == DatabaseType.REDIS
        )

    def test_from_connection_string_neptune(self):
        """Test Neptune detection from connection string."""
        assert (
            DatabaseType.from_connection_string(
                "wss://neptune-cluster.us-east-1.amazonaws.com:8182"
            )
            == DatabaseType.NEPTUNE
        )

    def test_from_connection_string_opensearch(self):
        """Test OpenSearch detection from connection string."""
        assert (
            DatabaseType.from_connection_string(
                "https://opensearch-domain.us-east-1.es.amazonaws.com"
            )
            == DatabaseType.OPENSEARCH
        )
        assert (
            DatabaseType.from_connection_string("es://host:9200")
            == DatabaseType.OPENSEARCH
        )

    def test_from_connection_string_elasticsearch(self):
        """Test Elasticsearch detection from connection string."""
        assert (
            DatabaseType.from_connection_string("elasticsearch://host:9200")
            == DatabaseType.ELASTICSEARCH
        )

    def test_from_connection_string_sqlite(self):
        """Test SQLite detection from connection string."""
        assert (
            DatabaseType.from_connection_string("sqlite:///path/to/db.sqlite")
            == DatabaseType.SQLITE
        )

    def test_from_connection_string_sqlserver(self):
        """Test SQL Server detection from connection string."""
        assert (
            DatabaseType.from_connection_string("sqlserver://host/db")
            == DatabaseType.SQLSERVER
        )
        assert (
            DatabaseType.from_connection_string("mssql://host/db")
            == DatabaseType.SQLSERVER
        )

    def test_from_connection_string_oracle(self):
        """Test Oracle detection from connection string."""
        assert (
            DatabaseType.from_connection_string("oracle://host:1521/db")
            == DatabaseType.ORACLE
        )

    def test_from_connection_string_cassandra(self):
        """Test Cassandra detection from connection string."""
        assert (
            DatabaseType.from_connection_string("cassandra://host:9042")
            == DatabaseType.CASSANDRA
        )

    def test_from_connection_string_unknown(self):
        """Test unknown database type detection."""
        assert (
            DatabaseType.from_connection_string("unknown://host/db")
            == DatabaseType.UNKNOWN
        )
        assert (
            DatabaseType.from_connection_string("random-string") == DatabaseType.UNKNOWN
        )


class TestQueueType:
    """Tests for QueueType enum."""

    def test_all_queue_types_exist(self):
        """Verify all expected queue types are defined."""
        expected = [
            "SQS",
            "SNS",
            "KAFKA",
            "RABBITMQ",
            "KINESIS",
            "EVENTBRIDGE",
            "REDIS_PUBSUB",
            "CELERY",
            "UNKNOWN",
        ]
        for name in expected:
            assert hasattr(QueueType, name)

    def test_from_import_sqs(self):
        """Test SQS detection from import."""
        assert QueueType.from_import("boto3.client('sqs')") == QueueType.SQS

    def test_from_import_sns(self):
        """Test SNS detection from import."""
        assert QueueType.from_import("boto3.resource('sns')") == QueueType.SNS

    def test_from_import_kafka(self):
        """Test Kafka detection from import."""
        assert (
            QueueType.from_import("from kafka import KafkaProducer") == QueueType.KAFKA
        )

    def test_from_import_rabbitmq(self):
        """Test RabbitMQ detection from import."""
        assert QueueType.from_import("import pika") == QueueType.RABBITMQ
        assert (
            QueueType.from_import("from rabbitmq import connection")
            == QueueType.RABBITMQ
        )

    def test_from_import_celery(self):
        """Test Celery detection from import."""
        assert QueueType.from_import("from celery import Celery") == QueueType.CELERY

    def test_from_import_unknown(self):
        """Test unknown queue type detection."""
        assert QueueType.from_import("import random_module") == QueueType.UNKNOWN


class TestPIICategory:
    """Tests for PIICategory enum."""

    def test_all_pii_categories_exist(self):
        """Verify all expected PII categories are defined."""
        expected = [
            "NAME",
            "EMAIL",
            "PHONE",
            "SSN",
            "PASSPORT",
            "DRIVERS_LICENSE",
            "ADDRESS",
            "DATE_OF_BIRTH",
            "CREDIT_CARD",
            "BANK_ACCOUNT",
            "MEDICAL_RECORD",
            "PASSWORD",
            "API_KEY",
            "IP_ADDRESS",
            "LOCATION",
            "DEVICE_ID",
            "BIOMETRIC",
        ]
        for name in expected:
            assert hasattr(PIICategory, name)


class TestComplianceFramework:
    """Tests for ComplianceFramework enum."""

    def test_all_frameworks_exist(self):
        """Verify all expected compliance frameworks are defined."""
        expected = [
            "GDPR",
            "HIPAA",
            "PCI_DSS",
            "SOX",
            "CCPA",
            "FERPA",
            "NIST_800_53",
            "CMMC",
        ]
        for name in expected:
            assert hasattr(ComplianceFramework, name)


class TestDataClassification:
    """Tests for DataClassification enum."""

    def test_all_classifications_exist(self):
        """Verify all expected classifications are defined."""
        expected = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "TOP_SECRET"]
        for name in expected:
            assert hasattr(DataClassification, name)


class TestDatabaseConnection:
    """Tests for DatabaseConnection dataclass."""

    def test_basic_creation(self):
        """Test basic DatabaseConnection creation."""
        conn = DatabaseConnection(
            connection_id="conn-001",
            database_type=DatabaseType.POSTGRESQL,
            source_file="src/services/user_service.py",
            source_line=42,
        )

        assert conn.connection_id == "conn-001"
        assert conn.database_type == DatabaseType.POSTGRESQL
        assert conn.source_file == "src/services/user_service.py"
        assert conn.source_line == 42
        assert conn.is_read is True
        assert conn.is_write is False
        assert conn.confidence == 1.0

    def test_with_tables_and_pool(self):
        """Test DatabaseConnection with tables and pool config."""
        conn = DatabaseConnection(
            connection_id="conn-002",
            database_type=DatabaseType.MYSQL,
            source_file="src/services/order_service.py",
            source_line=100,
            tables_accessed=["orders", "order_items"],
            is_read=True,
            is_write=True,
            pool_config={"max_connections": 10, "min_connections": 2},
            confidence=0.95,
        )

        assert len(conn.tables_accessed) == 2
        assert "orders" in conn.tables_accessed
        assert conn.is_write is True
        assert conn.pool_config["max_connections"] == 10

    def test_confidence_validation_too_high(self):
        """Test that confidence > 1.0 raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DatabaseConnection(
                connection_id="conn-003",
                database_type=DatabaseType.POSTGRESQL,
                source_file="test.py",
                source_line=1,
                confidence=1.5,
            )
        assert "Confidence must be between 0.0 and 1.0" in str(exc_info.value)

    def test_confidence_validation_too_low(self):
        """Test that confidence < 0.0 raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DatabaseConnection(
                connection_id="conn-004",
                database_type=DatabaseType.POSTGRESQL,
                source_file="test.py",
                source_line=1,
                confidence=-0.1,
            )
        assert "Confidence must be between 0.0 and 1.0" in str(exc_info.value)


class TestQueueConnection:
    """Tests for QueueConnection dataclass."""

    def test_basic_creation(self):
        """Test basic QueueConnection creation."""
        conn = QueueConnection(
            connection_id="queue-001",
            queue_type=QueueType.SQS,
            queue_name="user-events-queue",
            source_file="src/services/event_publisher.py",
            source_line=55,
            is_producer=True,
        )

        assert conn.connection_id == "queue-001"
        assert conn.queue_type == QueueType.SQS
        assert conn.queue_name == "user-events-queue"
        assert conn.is_producer is True
        assert conn.is_consumer is False

    def test_with_dlq(self):
        """Test QueueConnection with DLQ."""
        conn = QueueConnection(
            connection_id="queue-002",
            queue_type=QueueType.SQS,
            queue_name="orders-queue",
            source_file="src/services/order_processor.py",
            source_line=30,
            is_consumer=True,
            dlq_name="orders-dlq",
        )

        assert conn.dlq_name == "orders-dlq"
        assert conn.is_consumer is True


class TestAPIEndpoint:
    """Tests for APIEndpoint dataclass."""

    def test_basic_creation(self):
        """Test basic APIEndpoint creation."""
        endpoint = APIEndpoint(
            endpoint_id="api-001",
            url_pattern="/api/v1/users",
            method="GET",
            source_file="src/api/user_endpoints.py",
            source_line=25,
        )

        assert endpoint.endpoint_id == "api-001"
        assert endpoint.url_pattern == "/api/v1/users"
        assert endpoint.method == "GET"
        assert endpoint.is_internal is True
        assert endpoint.is_external is False

    def test_external_api_call(self):
        """Test external API endpoint."""
        endpoint = APIEndpoint(
            endpoint_id="api-002",
            url_pattern="https://api.stripe.com/v1/charges",
            method="POST",
            source_file="src/services/payment_service.py",
            source_line=100,
            is_internal=False,
            is_external=True,
            timeout_ms=30000,
            auth_type="api_key",
        )

        assert endpoint.is_external is True
        assert endpoint.timeout_ms == 30000
        assert endpoint.auth_type == "api_key"


class TestPIIField:
    """Tests for PIIField dataclass."""

    def test_basic_creation(self):
        """Test basic PIIField creation."""
        field = PIIField(
            field_id="pii-001",
            field_name="email",
            pii_category=PIICategory.EMAIL,
            source_file="src/models/user.py",
            source_line=15,
        )

        assert field.field_id == "pii-001"
        assert field.field_name == "email"
        assert field.pii_category == PIICategory.EMAIL
        assert field.classification == DataClassification.CONFIDENTIAL

    def test_with_compliance_tags(self):
        """Test PIIField with compliance tags."""
        field = PIIField(
            field_id="pii-002",
            field_name="ssn",
            pii_category=PIICategory.SSN,
            source_file="src/models/employee.py",
            source_line=22,
            entity_name="Employee",
            compliance_tags=[ComplianceFramework.NIST_800_53, ComplianceFramework.SOX],
            classification=DataClassification.RESTRICTED,
            is_encrypted=True,
            is_masked=True,
        )

        assert len(field.compliance_tags) == 2
        assert ComplianceFramework.NIST_800_53 in field.compliance_tags
        assert field.is_encrypted is True
        assert field.classification == DataClassification.RESTRICTED


class TestDataFlow:
    """Tests for DataFlow dataclass."""

    def test_basic_creation(self):
        """Test basic DataFlow creation."""
        flow = DataFlow(
            flow_id="flow-001",
            flow_type=DataFlowType.DATABASE_READ,
            source_entity="users_table",
            target_entity="user_service",
            source_file="src/services/user_service.py",
            source_line=50,
        )

        assert flow.flow_id == "flow-001"
        assert flow.flow_type == DataFlowType.DATABASE_READ
        assert flow.is_cross_boundary is False
        assert flow.encryption_in_transit is True

    def test_cross_boundary_flow(self):
        """Test cross-boundary data flow."""
        flow = DataFlow(
            flow_id="flow-002",
            flow_type=DataFlowType.API_CALL,
            source_entity="payment_service",
            target_entity="stripe_api",
            source_file="src/services/payment_service.py",
            source_line=100,
            pii_fields=["credit_card", "name"],
            is_cross_boundary=True,
            encryption_in_transit=True,
        )

        assert flow.is_cross_boundary is True
        assert len(flow.pii_fields) == 2
        assert "credit_card" in flow.pii_fields


class TestDataFlowResult:
    """Tests for DataFlowResult dataclass."""

    def test_basic_creation(self):
        """Test basic DataFlowResult creation."""
        result = DataFlowResult(repository_id="repo-123")

        assert result.repository_id == "repo-123"
        assert len(result.database_connections) == 0
        assert len(result.queue_connections) == 0
        assert result.total_connections == 0
        assert result.total_pii_fields == 0

    def test_computed_properties(self):
        """Test computed properties on DataFlowResult."""
        result = DataFlowResult(
            repository_id="repo-123",
            database_connections=[
                DatabaseConnection(
                    connection_id="conn-1",
                    database_type=DatabaseType.POSTGRESQL,
                    source_file="test.py",
                    source_line=1,
                ),
            ],
            queue_connections=[
                QueueConnection(
                    connection_id="queue-1",
                    queue_type=QueueType.SQS,
                    queue_name="test-queue",
                    source_file="test.py",
                    source_line=1,
                ),
            ],
            pii_fields=[
                PIIField(
                    field_id="pii-1",
                    field_name="email",
                    pii_category=PIICategory.EMAIL,
                    source_file="test.py",
                    source_line=1,
                ),
            ],
            data_flows=[
                DataFlow(
                    flow_id="flow-1",
                    flow_type=DataFlowType.DATABASE_READ,
                    source_entity="db",
                    target_entity="service",
                    source_file="test.py",
                    source_line=1,
                    is_cross_boundary=True,
                    pii_fields=["email"],
                ),
            ],
        )

        assert result.total_connections == 2
        assert result.total_pii_fields == 1
        assert len(result.cross_boundary_flows) == 1
        assert len(result.pii_data_flows) == 1


class TestDataFlowReport:
    """Tests for DataFlowReport dataclass."""

    def test_basic_creation(self):
        """Test basic DataFlowReport creation."""
        report = DataFlowReport(
            report_id="report-001",
            repository_id="repo-123",
            title="Data Flow Analysis Report",
        )

        assert report.report_id == "report-001"
        assert report.repository_id == "repo-123"
        assert report.export_format == "markdown"
        assert isinstance(report.generated_at, datetime)

    def test_with_content(self):
        """Test DataFlowReport with full content."""
        report = DataFlowReport(
            report_id="report-002",
            repository_id="repo-456",
            title="Full Report",
            summary="Executive summary here",
            database_section="Database analysis",
            queue_section="Queue analysis",
            diagrams={"architecture": "graph LR\n  A --> B"},
            recommendations=["Encrypt PII", "Add DLQ"],
            content="# Full Report Content",
        )

        assert report.summary == "Executive summary here"
        assert "architecture" in report.diagrams
        assert len(report.recommendations) == 2
