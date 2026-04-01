"""
Data Flow Type Definitions
==========================

ADR-056 Phase 3: Data Flow Analysis

Type definitions for data flow analysis including database connections,
message queues, API endpoints, and PII classification.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DataFlowType(Enum):
    """Types of data flow in the system."""

    DATABASE_READ = "database_read"
    DATABASE_WRITE = "database_write"
    QUEUE_PRODUCE = "queue_produce"
    QUEUE_CONSUME = "queue_consume"
    API_CALL = "api_call"
    API_RECEIVE = "api_receive"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    CACHE_READ = "cache_read"
    CACHE_WRITE = "cache_write"
    EVENT_EMIT = "event_emit"
    EVENT_LISTEN = "event_listen"


class DatabaseType(Enum):
    """Supported database types."""

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    DYNAMODB = "dynamodb"
    MONGODB = "mongodb"
    REDIS = "redis"
    NEPTUNE = "neptune"
    OPENSEARCH = "opensearch"
    ELASTICSEARCH = "elasticsearch"
    SQLITE = "sqlite"
    SQLSERVER = "sqlserver"
    ORACLE = "oracle"
    CASSANDRA = "cassandra"
    UNKNOWN = "unknown"

    @classmethod
    def from_connection_string(cls, conn_str: str) -> "DatabaseType":
        """Detect database type from connection string.

        Args:
            conn_str: Database connection string or URL

        Returns:
            Detected DatabaseType
        """
        conn_lower = conn_str.lower()

        if "postgresql" in conn_lower or "postgres" in conn_lower:
            return cls.POSTGRESQL
        elif "mysql" in conn_lower or "mariadb" in conn_lower:
            return cls.MYSQL
        elif "dynamodb" in conn_lower:
            return cls.DYNAMODB
        elif "mongodb" in conn_lower or "mongo://" in conn_lower:
            return cls.MONGODB
        elif "redis" in conn_lower:
            return cls.REDIS
        elif "neptune" in conn_lower:
            return cls.NEPTUNE
        elif "opensearch" in conn_lower or "es://" in conn_lower:
            return cls.OPENSEARCH
        elif "elasticsearch" in conn_lower:
            return cls.ELASTICSEARCH
        elif "sqlite" in conn_lower:
            return cls.SQLITE
        elif "sqlserver" in conn_lower or "mssql" in conn_lower:
            return cls.SQLSERVER
        elif "oracle" in conn_lower:
            return cls.ORACLE
        elif "cassandra" in conn_lower:
            return cls.CASSANDRA
        else:
            return cls.UNKNOWN


class QueueType(Enum):
    """Supported message queue types."""

    SQS = "sqs"
    SNS = "sns"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    KINESIS = "kinesis"
    EVENTBRIDGE = "eventbridge"
    REDIS_PUBSUB = "redis_pubsub"
    CELERY = "celery"
    UNKNOWN = "unknown"

    @classmethod
    def from_import(cls, import_path: str) -> "QueueType":
        """Detect queue type from import statement.

        Args:
            import_path: Python import path

        Returns:
            Detected QueueType
        """
        import_lower = import_path.lower()

        if "boto3" in import_lower and "sqs" in import_lower:
            return cls.SQS
        elif "boto3" in import_lower and "sns" in import_lower:
            return cls.SNS
        elif "kafka" in import_lower:
            return cls.KAFKA
        elif "pika" in import_lower or "rabbitmq" in import_lower:
            return cls.RABBITMQ
        elif "kinesis" in import_lower:
            return cls.KINESIS
        elif "eventbridge" in import_lower or "events" in import_lower:
            return cls.EVENTBRIDGE
        elif "celery" in import_lower:
            return cls.CELERY
        elif "redis" in import_lower and (
            "pubsub" in import_lower or "publish" in import_lower
        ):
            return cls.REDIS_PUBSUB
        else:
            return cls.UNKNOWN


class PIICategory(Enum):
    """Categories of Personally Identifiable Information."""

    # Direct identifiers
    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"

    # Indirect identifiers
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    GENDER = "gender"
    NATIONALITY = "nationality"
    IP_ADDRESS = "ip_address"

    # Financial
    CREDIT_CARD = "credit_card"
    BANK_ACCOUNT = "bank_account"
    TAX_ID = "tax_id"

    # Health
    MEDICAL_RECORD = "medical_record"
    HEALTH_INSURANCE_ID = "health_insurance_id"
    DIAGNOSIS = "diagnosis"
    PRESCRIPTION = "prescription"

    # Authentication
    PASSWORD = "password"
    API_KEY = "api_key"
    SECRET_TOKEN = "secret_token"
    BIOMETRIC = "biometric"

    # Other
    LOCATION = "location"
    DEVICE_ID = "device_id"
    PHOTO = "photo"
    UNKNOWN = "unknown"


class ComplianceFramework(Enum):
    """Compliance frameworks for data classification."""

    GDPR = "gdpr"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    SOX = "sox"
    CCPA = "ccpa"
    FERPA = "ferpa"
    NIST_800_53 = "nist_800_53"
    CMMC = "cmmc"


class DataClassification(Enum):
    """Data sensitivity classification levels."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


@dataclass
class DatabaseConnection:
    """Represents a database connection detected in code.

    Attributes:
        connection_id: Unique identifier for this connection
        database_type: Type of database (PostgreSQL, DynamoDB, etc.)
        source_file: File where connection was detected
        source_line: Line number in source file
        connection_string_pattern: Sanitized connection pattern (no secrets)
        tables_accessed: List of tables/collections accessed
        is_read: True if connection is used for reading
        is_write: True if connection is used for writing
        pool_config: Connection pool configuration if detected
        properties: Additional properties
        confidence: Detection confidence (0.0-1.0)
    """

    connection_id: str
    database_type: DatabaseType
    source_file: str
    source_line: int
    connection_string_pattern: str = ""
    tables_accessed: list[str] = field(default_factory=list)
    is_read: bool = True
    is_write: bool = False
    pool_config: dict[str, Any] = field(default_factory=dict)
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    def __post_init__(self) -> None:
        """Validate confidence score."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass
class QueueConnection:
    """Represents a message queue connection detected in code.

    Attributes:
        connection_id: Unique identifier for this connection
        queue_type: Type of queue (SQS, Kafka, etc.)
        queue_name: Name or ARN of the queue
        source_file: File where connection was detected
        source_line: Line number in source file
        is_producer: True if code produces to this queue
        is_consumer: True if code consumes from this queue
        message_schema: Detected message schema if available
        dlq_name: Dead letter queue name if configured
        properties: Additional properties
        confidence: Detection confidence (0.0-1.0)
    """

    connection_id: str
    queue_type: QueueType
    queue_name: str
    source_file: str
    source_line: int
    is_producer: bool = False
    is_consumer: bool = False
    message_schema: dict[str, Any] = field(default_factory=dict)
    dlq_name: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    def __post_init__(self) -> None:
        """Validate confidence score."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass
class APIEndpoint:
    """Represents an API endpoint detected in code.

    Attributes:
        endpoint_id: Unique identifier for this endpoint
        url_pattern: URL pattern or template
        method: HTTP method (GET, POST, etc.)
        source_file: File where endpoint was detected
        source_line: Line number in source file
        is_internal: True if endpoint is internal to the system
        is_external: True if endpoint calls external services
        request_schema: Request body schema if detected
        response_schema: Response schema if detected
        rate_limit: Rate limit configuration if detected
        timeout_ms: Timeout configuration in milliseconds
        auth_type: Authentication type if detected
        properties: Additional properties
        confidence: Detection confidence (0.0-1.0)
    """

    endpoint_id: str
    url_pattern: str
    method: str
    source_file: str
    source_line: int
    is_internal: bool = True
    is_external: bool = False
    request_schema: dict[str, Any] = field(default_factory=dict)
    response_schema: dict[str, Any] = field(default_factory=dict)
    rate_limit: dict[str, Any] | None = None
    timeout_ms: int | None = None
    auth_type: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    def __post_init__(self) -> None:
        """Validate confidence score."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass
class PIIField:
    """Represents a detected PII field in code or data.

    Attributes:
        field_id: Unique identifier for this field
        field_name: Name of the field
        pii_category: Category of PII
        source_file: File where field was detected
        source_line: Line number in source file
        entity_name: Name of containing entity (class, table, etc.)
        compliance_tags: Applicable compliance frameworks
        classification: Data classification level
        is_encrypted: True if field is encrypted
        is_masked: True if field is masked in logs
        pattern_matched: Pattern that matched this field
        confidence: Detection confidence (0.0-1.0)
    """

    field_id: str
    field_name: str
    pii_category: PIICategory
    source_file: str
    source_line: int
    entity_name: str = ""
    compliance_tags: list[ComplianceFramework] = field(default_factory=list)
    classification: DataClassification = DataClassification.CONFIDENTIAL
    is_encrypted: bool = False
    is_masked: bool = False
    pattern_matched: str = ""
    confidence: float = 1.0

    def __post_init__(self) -> None:
        """Validate confidence score."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass
class DataFlow:
    """Represents a data flow between two entities.

    Attributes:
        flow_id: Unique identifier for this flow
        flow_type: Type of data flow
        source_entity: Source entity (service, function, table)
        target_entity: Target entity
        source_file: File where flow was detected
        source_line: Line number in source file
        data_fields: Fields being transferred
        pii_fields: PII fields in the flow
        is_cross_boundary: True if flow crosses service boundaries
        is_cross_region: True if flow crosses region boundaries
        encryption_in_transit: True if data is encrypted in transit
        properties: Additional properties
        confidence: Detection confidence (0.0-1.0)
    """

    flow_id: str
    flow_type: DataFlowType
    source_entity: str
    target_entity: str
    source_file: str
    source_line: int
    data_fields: list[str] = field(default_factory=list)
    pii_fields: list[str] = field(default_factory=list)
    is_cross_boundary: bool = False
    is_cross_region: bool = False
    encryption_in_transit: bool = True
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    def __post_init__(self) -> None:
        """Validate confidence score."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass
class DataFlowResult:
    """Result of data flow analysis.

    Attributes:
        repository_id: Repository that was analyzed
        database_connections: Detected database connections
        queue_connections: Detected queue connections
        api_endpoints: Detected API endpoints
        pii_fields: Detected PII fields
        data_flows: Detected data flows
        analysis_time_ms: Time taken for analysis in milliseconds
        analyzed_at: Timestamp of analysis
        files_analyzed: Number of files analyzed
        warnings: Any warnings generated during analysis
        errors: Any errors encountered during analysis
    """

    repository_id: str
    database_connections: list[DatabaseConnection] = field(default_factory=list)
    queue_connections: list[QueueConnection] = field(default_factory=list)
    api_endpoints: list[APIEndpoint] = field(default_factory=list)
    pii_fields: list[PIIField] = field(default_factory=list)
    data_flows: list[DataFlow] = field(default_factory=list)
    analysis_time_ms: float = 0.0
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    files_analyzed: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_connections(self) -> int:
        """Total number of connections detected."""
        return len(self.database_connections) + len(self.queue_connections)

    @property
    def total_pii_fields(self) -> int:
        """Total number of PII fields detected."""
        return len(self.pii_fields)

    @property
    def cross_boundary_flows(self) -> list[DataFlow]:
        """Data flows that cross service boundaries."""
        return [f for f in self.data_flows if f.is_cross_boundary]

    @property
    def pii_data_flows(self) -> list[DataFlow]:
        """Data flows containing PII."""
        return [f for f in self.data_flows if f.pii_fields]


@dataclass
class DataFlowReport:
    """Generated data flow report.

    Attributes:
        report_id: Unique report identifier
        repository_id: Repository the report is for
        title: Report title
        generated_at: When the report was generated
        summary: Executive summary
        database_section: Database connection analysis
        queue_section: Queue/event flow analysis
        api_section: API call chain analysis
        pii_section: PII detection results
        compliance_section: Compliance analysis
        diagrams: Generated diagrams (Mermaid format)
        recommendations: Security and architecture recommendations
        export_format: Format of the report (markdown, pdf, html)
        content: Full report content
    """

    report_id: str
    repository_id: str
    title: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    summary: str = ""
    database_section: str = ""
    queue_section: str = ""
    api_section: str = ""
    pii_section: str = ""
    compliance_section: str = ""
    diagrams: dict[str, str] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    export_format: str = "markdown"
    content: str = ""
