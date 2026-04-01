"""
Queue Flow Analyzer
===================

ADR-056 Phase 3: Data Flow Analysis

Analyzes message queue and event flow patterns in code.
Supports SQS, SNS, Kafka, RabbitMQ, EventBridge, and more.
"""

import ast
import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from src.services.data_flow.types import QueueConnection, QueueType

logger = logging.getLogger(__name__)


@dataclass
class QueuePattern:
    """Pattern for detecting queue connections."""

    name: str
    queue_type: QueueType
    import_patterns: list[str]
    producer_patterns: list[str]
    consumer_patterns: list[str]
    queue_name_patterns: list[str]
    dlq_patterns: list[str]


# Queue detection patterns
QUEUE_PATTERNS: list[QueuePattern] = [
    QueuePattern(
        name="SQS",
        queue_type=QueueType.SQS,
        import_patterns=[
            r"boto3.*sqs",
            r"client\s*\(\s*['\"]sqs['\"]",
            r"resource\s*\(\s*['\"]sqs['\"]",
        ],
        producer_patterns=[
            r"send_message\s*\(",
            r"send_message_batch\s*\(",
        ],
        consumer_patterns=[
            r"receive_message\s*\(",
            r"delete_message\s*\(",
        ],
        queue_name_patterns=[
            r"QueueUrl\s*=\s*['\"]([^'\"]+)['\"]",
            r"queue_url\s*=\s*['\"]([^'\"]+)['\"]",
            r"get_queue_url.*QueueName\s*=\s*['\"]([^'\"]+)['\"]",
        ],
        dlq_patterns=[
            r"RedrivePolicy",
            r"deadLetterTargetArn",
            r"dlq",
        ],
    ),
    QueuePattern(
        name="SNS",
        queue_type=QueueType.SNS,
        import_patterns=[
            r"boto3.*sns",
            r"client\s*\(\s*['\"]sns['\"]",
        ],
        producer_patterns=[
            r"publish\s*\(",
            r"publish_batch\s*\(",
        ],
        consumer_patterns=[
            r"subscribe\s*\(",
            r"confirm_subscription\s*\(",
        ],
        queue_name_patterns=[
            r"TopicArn\s*=\s*['\"]([^'\"]+)['\"]",
            r"topic_arn\s*=\s*['\"]([^'\"]+)['\"]",
        ],
        dlq_patterns=[],
    ),
    QueuePattern(
        name="Kafka",
        queue_type=QueueType.KAFKA,
        import_patterns=[
            r"from\s+kafka",
            r"import\s+kafka",
            r"from\s+confluent_kafka",
            r"import\s+aiokafka",
        ],
        producer_patterns=[
            r"KafkaProducer\s*\(",
            r"AIOKafkaProducer\s*\(",
            r"producer\.send\s*\(",
            r"produce\s*\(",
        ],
        consumer_patterns=[
            r"KafkaConsumer\s*\(",
            r"AIOKafkaConsumer\s*\(",
            r"consumer\.poll\s*\(",
            r"subscribe\s*\(",
        ],
        queue_name_patterns=[
            r"topic\s*=\s*['\"]([^'\"]+)['\"]",
            r"topics\s*=\s*\[([^\]]+)\]",
        ],
        dlq_patterns=[
            r"dead_letter",
            r"dlq",
            r"error_topic",
        ],
    ),
    QueuePattern(
        name="RabbitMQ",
        queue_type=QueueType.RABBITMQ,
        import_patterns=[
            r"import\s+pika",
            r"from\s+pika",
            r"import\s+aio_pika",
            r"from\s+aio_pika",
        ],
        producer_patterns=[
            r"basic_publish\s*\(",
            r"publish\s*\(",
        ],
        consumer_patterns=[
            r"basic_consume\s*\(",
            r"consume\s*\(",
            r"basic_get\s*\(",
        ],
        queue_name_patterns=[
            r"queue_declare.*queue\s*=\s*['\"]([^'\"]+)['\"]",
            r"queue\s*=\s*['\"]([^'\"]+)['\"]",
            r"routing_key\s*=\s*['\"]([^'\"]+)['\"]",
        ],
        dlq_patterns=[
            r"x-dead-letter-exchange",
            r"x-dead-letter-routing-key",
        ],
    ),
    QueuePattern(
        name="EventBridge",
        queue_type=QueueType.EVENTBRIDGE,
        import_patterns=[
            r"boto3.*events",
            r"client\s*\(\s*['\"]events['\"]",
            r"eventbridge",
        ],
        producer_patterns=[
            r"put_events\s*\(",
        ],
        consumer_patterns=[
            r"put_rule\s*\(",
            r"put_targets\s*\(",
        ],
        queue_name_patterns=[
            r"EventBusName\s*=\s*['\"]([^'\"]+)['\"]",
            r"Source\s*=\s*['\"]([^'\"]+)['\"]",
        ],
        dlq_patterns=[
            r"DeadLetterConfig",
        ],
    ),
    QueuePattern(
        name="Kinesis",
        queue_type=QueueType.KINESIS,
        import_patterns=[
            r"boto3.*kinesis",
            r"client\s*\(\s*['\"]kinesis['\"]",
        ],
        producer_patterns=[
            r"put_record\s*\(",
            r"put_records\s*\(",
        ],
        consumer_patterns=[
            r"get_records\s*\(",
            r"get_shard_iterator\s*\(",
        ],
        queue_name_patterns=[
            r"StreamName\s*=\s*['\"]([^'\"]+)['\"]",
            r"stream_name\s*=\s*['\"]([^'\"]+)['\"]",
        ],
        dlq_patterns=[],
    ),
    QueuePattern(
        name="Celery",
        queue_type=QueueType.CELERY,
        import_patterns=[
            r"from\s+celery",
            r"import\s+celery",
        ],
        producer_patterns=[
            r"\.delay\s*\(",
            r"\.apply_async\s*\(",
            r"send_task\s*\(",
        ],
        consumer_patterns=[
            r"@app\.task",
            r"@celery\.task",
            r"@shared_task",
        ],
        queue_name_patterns=[
            r"queue\s*=\s*['\"]([^'\"]+)['\"]",
            r"task_routes\s*=",
        ],
        dlq_patterns=[
            r"task_reject_on_worker_lost",
            r"task_acks_late",
        ],
    ),
]


class QueueFlowAnalyzer:
    """
    Analyzes message queue and event flow patterns in code.

    Detects:
    - Queue producers and consumers
    - Message schemas from code
    - Dead letter queue configurations
    - Cross-service event flows

    Usage:
        analyzer = QueueFlowAnalyzer()
        connections = await analyzer.analyze_file("/path/to/file.py")

        # Or analyze entire directory
        connections = await analyzer.analyze_directory("/path/to/repo")
    """

    def __init__(self, use_mock: bool = False) -> None:
        """Initialize queue analyzer.

        Args:
            use_mock: Use mock mode for testing
        """
        self.use_mock = use_mock
        self._patterns = QUEUE_PATTERNS
        self._seen_connections: set[tuple[str, int, str]] = set()

    async def analyze_file(self, file_path: str) -> list[QueueConnection]:
        """Analyze a single file for queue connections.

        Args:
            file_path: Path to Python file

        Returns:
            List of detected queue connections
        """
        if self.use_mock:
            return self._get_mock_connections(file_path)

        path = Path(file_path)
        if not path.exists() or not path.suffix == ".py":
            return []

        try:
            content = path.read_text(encoding="utf-8")
            return self._analyze_content(content, str(path))
        except Exception as e:
            logger.warning(f"Failed to analyze file {file_path}: {e}")
            return []

    async def analyze_directory(
        self,
        directory: str,
        exclude_patterns: list[str] | None = None,
    ) -> list[QueueConnection]:
        """Analyze all Python files in a directory.

        Args:
            directory: Path to directory
            exclude_patterns: Glob patterns to exclude

        Returns:
            List of detected queue connections
        """
        if self.use_mock:
            return self._get_mock_connections(directory)

        exclude_patterns = exclude_patterns or [
            "**/test*",
            "**/__pycache__/*",
            "**/venv/*",
        ]
        connections: list[QueueConnection] = []

        path = Path(directory)
        if not path.exists():
            return []

        for py_file in path.rglob("*.py"):
            should_exclude = False
            for pattern in exclude_patterns:
                if py_file.match(pattern):
                    should_exclude = True
                    break

            if not should_exclude:
                file_connections = await self.analyze_file(str(py_file))
                connections.extend(file_connections)

        return connections

    def _analyze_content(self, content: str, file_path: str) -> list[QueueConnection]:
        """Analyze file content for queue connections.

        Args:
            content: File content
            file_path: Path to file

        Returns:
            List of detected connections
        """
        connections: list[QueueConnection] = []

        # Detect which queue libraries are imported
        detected_types = self._detect_imports(content)

        # Parse AST for connection patterns
        try:
            tree = ast.parse(content)
            ast_connections = self._analyze_ast(
                tree, content, file_path, detected_types
            )
            connections.extend(ast_connections)
        except SyntaxError:
            pass

        # Use regex for additional detection
        regex_connections = self._analyze_with_regex(content, file_path, detected_types)

        # Seed the seen set with AST connections so set-based dedup works correctly
        for conn in connections:
            self._seen_connections.add(
                (conn.source_file, conn.source_line, conn.queue_type.value)
            )

        # Merge and deduplicate
        for conn in regex_connections:
            if not self._is_duplicate(conn, connections):
                connections.append(conn)

        return connections

    def _detect_imports(self, content: str) -> set[QueueType]:
        """Detect queue types from import statements.

        Args:
            content: File content

        Returns:
            Set of detected queue types
        """
        detected: set[QueueType] = set()

        for pattern in self._patterns:
            for import_pattern in pattern.import_patterns:
                if re.search(import_pattern, content, re.IGNORECASE):
                    detected.add(pattern.queue_type)
                    break

        return detected

    def _analyze_ast(
        self,
        tree: ast.AST,
        content: str,
        file_path: str,
        detected_types: set[QueueType],
    ) -> list[QueueConnection]:
        """Analyze AST for queue connections.

        Args:
            tree: Parsed AST
            content: File content for context
            file_path: Path to file
            detected_types: Queue types detected from imports

        Returns:
            List of connections
        """
        connections: list[QueueConnection] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                conn = self._check_call_node(node, content, file_path, detected_types)
                if conn:
                    connections.append(conn)
            elif isinstance(node, ast.FunctionDef):
                conn = self._check_decorator_node(
                    node, content, file_path, detected_types
                )
                if conn:
                    connections.append(conn)

        return connections

    def _check_call_node(
        self,
        node: ast.Call,
        content: str,
        file_path: str,
        detected_types: set[QueueType],
    ) -> QueueConnection | None:
        """Check if a Call node represents a queue operation.

        Args:
            node: AST Call node
            content: File content
            file_path: Path to file
            detected_types: Detected queue types

        Returns:
            QueueConnection if detected, None otherwise
        """
        func_name = self._get_func_name(node)
        if not func_name:
            return None

        for pattern in self._patterns:
            if pattern.queue_type not in detected_types:
                continue

            # Check producer patterns
            is_producer = any(
                re.search(p, func_name, re.IGNORECASE)
                for p in pattern.producer_patterns
            )

            # Check consumer patterns
            is_consumer = any(
                re.search(p, func_name, re.IGNORECASE)
                for p in pattern.consumer_patterns
            )

            if is_producer or is_consumer:
                queue_name = self._extract_queue_name(node, content, pattern)
                dlq_name = self._detect_dlq(content, pattern)

                return self._create_connection(
                    node,
                    file_path,
                    pattern.queue_type,
                    queue_name,
                    is_producer,
                    is_consumer,
                    dlq_name,
                )

        return None

    def _check_decorator_node(
        self,
        node: ast.FunctionDef,
        content: str,
        file_path: str,
        detected_types: set[QueueType],
    ) -> QueueConnection | None:
        """Check if a function has queue-related decorators.

        Args:
            node: AST FunctionDef node
            content: File content
            file_path: Path to file
            detected_types: Detected queue types

        Returns:
            QueueConnection if detected, None otherwise
        """
        for decorator in node.decorator_list:
            decorator_name = self._get_decorator_name(decorator)

            for pattern in self._patterns:
                if pattern.queue_type not in detected_types:
                    continue

                # Check if decorator matches consumer pattern
                for consumer_pattern in pattern.consumer_patterns:
                    if re.search(consumer_pattern, decorator_name, re.IGNORECASE):
                        return self._create_connection(
                            node,
                            file_path,
                            pattern.queue_type,
                            node.name,  # Use function name as queue identifier
                            is_producer=False,
                            is_consumer=True,
                            dlq_name=None,
                        )

        return None

    def _get_func_name(self, node: ast.Call) -> str:
        """Get function name from Call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return ""

    def _get_decorator_name(self, decorator: ast.expr) -> str:
        """Get decorator name from decorator node."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return f"{self._get_decorator_name(decorator.value)}.{decorator.attr}"
        elif isinstance(decorator, ast.Call):
            return self._get_decorator_name(decorator.func)
        return ""

    def _extract_queue_name(
        self,
        node: ast.Call,
        content: str,
        pattern: QueuePattern,
    ) -> str:
        """Extract queue name from AST node or surrounding code.

        Args:
            node: AST Call node
            content: File content
            pattern: Queue pattern

        Returns:
            Queue name or empty string
        """
        # Try to extract from node arguments
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value

        # Try to extract from keyword arguments
        for kwarg in node.keywords:
            if kwarg.arg in ("QueueUrl", "TopicArn", "StreamName", "queue", "topic"):
                if isinstance(kwarg.value, ast.Constant):
                    return str(kwarg.value.value)

        # Fall back to regex on surrounding context
        for name_pattern in pattern.queue_name_patterns:
            matches = re.findall(name_pattern, content, re.IGNORECASE)
            if matches:
                return matches[0] if isinstance(matches[0], str) else matches[0][0]

        return "unknown"

    def _detect_dlq(self, content: str, pattern: QueuePattern) -> str | None:
        """Detect dead letter queue configuration.

        Args:
            content: File content
            pattern: Queue pattern

        Returns:
            DLQ name or None
        """
        for dlq_pattern in pattern.dlq_patterns:
            if re.search(dlq_pattern, content, re.IGNORECASE):
                # Try to extract DLQ name
                dlq_match = re.search(
                    r"(dlq|dead[-_]?letter)[-_]?(\w+)",
                    content,
                    re.IGNORECASE,
                )
                if dlq_match:
                    return dlq_match.group(0)
                return "detected"
        return None

    def _create_connection(
        self,
        node: ast.AST,
        file_path: str,
        queue_type: QueueType,
        queue_name: str,
        is_producer: bool,
        is_consumer: bool,
        dlq_name: str | None,
    ) -> QueueConnection:
        """Create a QueueConnection from detected information.

        Args:
            node: AST node
            file_path: Path to file
            queue_type: Type of queue
            queue_name: Name of queue
            is_producer: Whether this is a producer
            is_consumer: Whether this is a consumer
            dlq_name: Dead letter queue name

        Returns:
            QueueConnection instance
        """
        line_num = getattr(node, "lineno", 0)

        conn_id = hashlib.md5(  # noqa: S324
            f"{file_path}:{line_num}:{queue_type.value}:{queue_name}".encode(),
            usedforsecurity=False,
        ).hexdigest()[:12]

        return QueueConnection(
            connection_id=f"queue-{conn_id}",
            queue_type=queue_type,
            queue_name=queue_name,
            source_file=file_path,
            source_line=line_num,
            is_producer=is_producer,
            is_consumer=is_consumer,
            dlq_name=dlq_name,
            confidence=0.85,
        )

    def _analyze_with_regex(
        self,
        content: str,
        file_path: str,
        detected_types: set[QueueType],
    ) -> list[QueueConnection]:
        """Analyze content using regex patterns.

        Args:
            content: File content
            file_path: Path to file
            detected_types: Detected queue types

        Returns:
            List of connections
        """
        connections: list[QueueConnection] = []
        lines = content.split("\n")

        for pattern in self._patterns:
            if pattern.queue_type not in detected_types:
                continue

            for line_num, line in enumerate(lines, 1):
                # Check producer patterns
                is_producer = any(
                    re.search(p, line, re.IGNORECASE) for p in pattern.producer_patterns
                )

                # Check consumer patterns
                is_consumer = any(
                    re.search(p, line, re.IGNORECASE) for p in pattern.consumer_patterns
                )

                if is_producer or is_consumer:
                    # Extract queue name from line or nearby context
                    queue_name = "unknown"
                    for name_pattern in pattern.queue_name_patterns:
                        match = re.search(name_pattern, content, re.IGNORECASE)
                        if match:
                            queue_name = match.group(1)
                            break

                    dlq_name = self._detect_dlq(content, pattern)

                    conn_id = hashlib.md5(  # noqa: S324
                        f"{file_path}:{line_num}:{pattern.name}".encode(),
                        usedforsecurity=False,
                    ).hexdigest()[:12]

                    connections.append(
                        QueueConnection(
                            connection_id=f"queue-{conn_id}",
                            queue_type=pattern.queue_type,
                            queue_name=queue_name,
                            source_file=file_path,
                            source_line=line_num,
                            is_producer=is_producer,
                            is_consumer=is_consumer,
                            dlq_name=dlq_name,
                            confidence=0.75,
                        )
                    )

        return connections

    def _is_duplicate(
        self,
        conn: QueueConnection,
        existing: list[QueueConnection],
    ) -> bool:
        """Check if connection is a duplicate using set-based O(1) lookup."""
        key = (conn.source_file, conn.source_line, conn.queue_type.value)
        if key in self._seen_connections:
            return True
        self._seen_connections.add(key)
        return False

    def _get_mock_connections(self, path: str) -> list[QueueConnection]:
        """Get mock connections for testing.

        Args:
            path: File or directory path

        Returns:
            List of mock connections
        """
        return [
            QueueConnection(
                connection_id="queue-mock-sqs-producer",
                queue_type=QueueType.SQS,
                queue_name="aura-task-queue-dev",
                source_file=f"{path}/services/task_service.py",
                source_line=89,
                is_producer=True,
                is_consumer=False,
                message_schema={"task_id": "string", "payload": "object"},
                dlq_name="aura-task-queue-dlq-dev",
                confidence=0.9,
            ),
            QueueConnection(
                connection_id="queue-mock-sqs-consumer",
                queue_type=QueueType.SQS,
                queue_name="aura-task-queue-dev",
                source_file=f"{path}/workers/task_worker.py",
                source_line=45,
                is_producer=False,
                is_consumer=True,
                dlq_name="aura-task-queue-dlq-dev",
                confidence=0.9,
            ),
            QueueConnection(
                connection_id="queue-mock-sns",
                queue_type=QueueType.SNS,
                queue_name="arn:aws:sns:us-east-1:123456789012:aura-notifications",
                source_file=f"{path}/services/notification_service.py",
                source_line=67,
                is_producer=True,
                is_consumer=False,
                confidence=0.85,
            ),
            QueueConnection(
                connection_id="queue-mock-eventbridge",
                queue_type=QueueType.EVENTBRIDGE,
                queue_name="aura-events",
                source_file=f"{path}/services/event_bus.py",
                source_line=34,
                is_producer=True,
                is_consumer=False,
                message_schema={
                    "source": "string",
                    "detail-type": "string",
                    "detail": "object",
                },
                confidence=0.88,
            ),
        ]
