"""
Database Connection Tracer
==========================

ADR-056 Phase 3: Data Flow Analysis

Detects and traces database connections in code using AST parsing.
Supports PostgreSQL, MySQL, DynamoDB, MongoDB, Redis, and more.
"""

import ast
import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from src.services.data_flow.types import DatabaseConnection, DatabaseType

logger = logging.getLogger(__name__)


@dataclass
class DatabasePattern:
    """Pattern for detecting database connections."""

    name: str
    database_type: DatabaseType
    import_patterns: list[str]
    connection_patterns: list[str]
    table_patterns: list[str]
    read_patterns: list[str]
    write_patterns: list[str]


# Database detection patterns
DATABASE_PATTERNS: list[DatabasePattern] = [
    DatabasePattern(
        name="PostgreSQL",
        database_type=DatabaseType.POSTGRESQL,
        import_patterns=[
            r"import\s+psycopg2",
            r"from\s+psycopg2",
            r"import\s+asyncpg",
            r"from\s+asyncpg",
            r"import\s+psycopg",
            r"from\s+sqlalchemy.*postgresql",
        ],
        connection_patterns=[
            r"psycopg2\.connect\s*\(",
            r"asyncpg\.connect\s*\(",
            r"create_engine\s*\(\s*['\"]postgresql",
            r"DATABASE_URL.*postgres",
        ],
        table_patterns=[
            r"FROM\s+(\w+)",
            r"INTO\s+(\w+)",
            r"UPDATE\s+(\w+)",
            r"JOIN\s+(\w+)",
        ],
        read_patterns=[
            r"SELECT",
            r"fetchone",
            r"fetchall",
            r"fetchmany",
            r"cursor\.execute.*SELECT",
        ],
        write_patterns=[
            r"INSERT",
            r"UPDATE",
            r"DELETE",
            r"execute.*INSERT",
            r"execute.*UPDATE",
        ],
    ),
    DatabasePattern(
        name="MySQL",
        database_type=DatabaseType.MYSQL,
        import_patterns=[
            r"import\s+mysql\.connector",
            r"from\s+mysql\.connector",
            r"import\s+pymysql",
            r"from\s+pymysql",
            r"import\s+aiomysql",
            r"from\s+sqlalchemy.*mysql",
        ],
        connection_patterns=[
            r"mysql\.connector\.connect\s*\(",
            r"pymysql\.connect\s*\(",
            r"aiomysql\.connect\s*\(",
            r"create_engine\s*\(\s*['\"]mysql",
        ],
        table_patterns=[
            r"FROM\s+(\w+)",
            r"INTO\s+(\w+)",
            r"UPDATE\s+(\w+)",
        ],
        read_patterns=[r"SELECT", r"fetchone", r"fetchall"],
        write_patterns=[r"INSERT", r"UPDATE", r"DELETE"],
    ),
    DatabasePattern(
        name="DynamoDB",
        database_type=DatabaseType.DYNAMODB,
        import_patterns=[
            r"boto3.*dynamodb",
            r"from\s+boto3\.dynamodb",
            r"import\s+aioboto3",
            r"resource\s*\(\s*['\"]dynamodb['\"]",
        ],
        connection_patterns=[
            r"boto3\.resource\s*\(\s*['\"]dynamodb['\"]",
            r"boto3\.client\s*\(\s*['\"]dynamodb['\"]",
            r"Table\s*\(\s*['\"](\w+)['\"]",
        ],
        table_patterns=[
            r"Table\s*\(\s*['\"](\w+)['\"]",
            r"table_name\s*=\s*['\"](\w+)['\"]",
        ],
        read_patterns=[r"get_item", r"query", r"scan", r"batch_get_item"],
        write_patterns=[
            r"put_item",
            r"update_item",
            r"delete_item",
            r"batch_write_item",
        ],
    ),
    DatabasePattern(
        name="MongoDB",
        database_type=DatabaseType.MONGODB,
        import_patterns=[
            r"import\s+pymongo",
            r"from\s+pymongo",
            r"import\s+motor",
            r"from\s+motor",
        ],
        connection_patterns=[
            r"MongoClient\s*\(",
            r"AsyncIOMotorClient\s*\(",
            r"mongodb://",
            r"mongodb\+srv://",
        ],
        table_patterns=[
            r"\.(\w+)\.find",
            r"\.(\w+)\.insert",
            r"\.(\w+)\.update",
            r"db\[[\'\"](\w+)[\'\"]\]",
        ],
        read_patterns=[r"find\(", r"find_one\(", r"aggregate\(", r"count_documents"],
        write_patterns=[
            r"insert_one",
            r"insert_many",
            r"update_one",
            r"update_many",
            r"delete_one",
        ],
    ),
    DatabasePattern(
        name="Redis",
        database_type=DatabaseType.REDIS,
        import_patterns=[
            r"import\s+redis",
            r"from\s+redis",
            r"import\s+aioredis",
            r"from\s+aioredis",
        ],
        connection_patterns=[
            r"redis\.Redis\s*\(",
            r"redis\.from_url\s*\(",
            r"aioredis\.from_url\s*\(",
            r"redis://",
        ],
        table_patterns=[],  # Redis doesn't have tables
        read_patterns=[r"\.get\(", r"\.hget\(", r"\.mget\(", r"\.lrange\("],
        write_patterns=[r"\.set\(", r"\.hset\(", r"\.lpush\(", r"\.rpush\("],
    ),
    DatabasePattern(
        name="Neptune",
        database_type=DatabaseType.NEPTUNE,
        import_patterns=[
            r"from\s+gremlin_python",
            r"import\s+gremlin_python",
            r"from\s+neptune",
        ],
        connection_patterns=[
            r"DriverRemoteConnection\s*\(",
            r"neptune.*8182",
            r"wss://.*neptune.*amazonaws\.com",
        ],
        table_patterns=[],
        read_patterns=[r"\.V\(", r"\.E\(", r"\.valueMap\(", r"\.toList\("],
        write_patterns=[r"\.addV\(", r"\.addE\(", r"\.drop\(", r"\.property\("],
    ),
    DatabasePattern(
        name="OpenSearch",
        database_type=DatabaseType.OPENSEARCH,
        import_patterns=[
            r"from\s+opensearchpy",
            r"import\s+opensearchpy",
            r"from\s+opensearch",
        ],
        connection_patterns=[
            r"OpenSearch\s*\(",
            r"opensearch.*9200",
            r"https://.*opensearch.*amazonaws\.com",
        ],
        table_patterns=[
            r"index\s*=\s*['\"](\w+)['\"]",
        ],
        read_patterns=[r"\.search\(", r"\.get\(", r"\.mget\("],
        write_patterns=[r"\.index\(", r"\.bulk\(", r"\.update\(", r"\.delete\("],
    ),
]


class DatabaseConnectionTracer:
    """
    Traces database connections in Python code.

    Uses AST parsing and pattern matching to detect:
    - Database connection strings
    - Tables/collections accessed
    - Read vs write operations
    - Connection pooling configurations

    Usage:
        tracer = DatabaseConnectionTracer()
        connections = await tracer.trace_file("/path/to/file.py")

        # Or trace entire directory
        connections = await tracer.trace_directory("/path/to/repo")
    """

    def __init__(self, use_mock: bool = False) -> None:
        """Initialize database tracer.

        Args:
            use_mock: Use mock mode for testing
        """
        self.use_mock = use_mock
        self._patterns = DATABASE_PATTERNS

    async def trace_file(self, file_path: str) -> list[DatabaseConnection]:
        """Trace database connections in a single file.

        Args:
            file_path: Path to Python file

        Returns:
            List of detected database connections
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
            logger.warning(f"Failed to trace file {file_path}: {e}")
            return []

    async def trace_directory(
        self,
        directory: str,
        exclude_patterns: list[str] | None = None,
    ) -> list[DatabaseConnection]:
        """Trace database connections in all Python files in a directory.

        Args:
            directory: Path to directory
            exclude_patterns: Glob patterns to exclude

        Returns:
            List of detected database connections
        """
        if self.use_mock:
            return self._get_mock_connections(directory)

        exclude_patterns = exclude_patterns or [
            "**/test*",
            "**/__pycache__/*",
            "**/venv/*",
        ]
        connections: list[DatabaseConnection] = []

        path = Path(directory)
        if not path.exists():
            return []

        for py_file in path.rglob("*.py"):
            # Check exclusions
            should_exclude = False
            for pattern in exclude_patterns:
                if py_file.match(pattern):
                    should_exclude = True
                    break

            if not should_exclude:
                file_connections = await self.trace_file(str(py_file))
                connections.extend(file_connections)

        return connections

    def _analyze_content(
        self, content: str, file_path: str
    ) -> list[DatabaseConnection]:
        """Analyze file content for database connections.

        Args:
            content: File content
            file_path: Path to file

        Returns:
            List of detected connections
        """
        connections: list[DatabaseConnection] = []

        # First, detect which database libraries are imported
        detected_types = self._detect_imports(content)

        # Parse AST for connection patterns
        try:
            tree = ast.parse(content)
            ast_connections = self._analyze_ast(tree, file_path, detected_types)
            connections.extend(ast_connections)
        except SyntaxError:
            # Fall back to regex if AST parsing fails
            pass

        # Use regex patterns for additional detection
        regex_connections = self._analyze_with_regex(content, file_path, detected_types)

        # Merge and deduplicate
        for conn in regex_connections:
            if not self._is_duplicate(conn, connections):
                connections.append(conn)

        return connections

    def _detect_imports(self, content: str) -> set[DatabaseType]:
        """Detect database types from import statements.

        Args:
            content: File content

        Returns:
            Set of detected database types
        """
        detected: set[DatabaseType] = set()

        for pattern in self._patterns:
            for import_pattern in pattern.import_patterns:
                if re.search(import_pattern, content, re.IGNORECASE):
                    detected.add(pattern.database_type)
                    break

        return detected

    def _analyze_ast(
        self,
        tree: ast.AST,
        file_path: str,
        detected_types: set[DatabaseType],
    ) -> list[DatabaseConnection]:
        """Analyze AST for database connections.

        Args:
            tree: Parsed AST
            file_path: Path to file
            detected_types: Database types detected from imports

        Returns:
            List of connections
        """
        connections: list[DatabaseConnection] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                conn = self._check_call_node(node, file_path, detected_types)
                if conn:
                    connections.append(conn)

        return connections

    def _check_call_node(
        self,
        node: ast.Call,
        file_path: str,
        detected_types: set[DatabaseType],
    ) -> DatabaseConnection | None:
        """Check if a Call node represents a database connection.

        Args:
            node: AST Call node
            file_path: Path to file
            detected_types: Detected database types

        Returns:
            DatabaseConnection if detected, None otherwise
        """
        func_name = self._get_func_name(node)
        if not func_name:
            return None

        # Check for connection creation patterns
        for pattern in self._patterns:
            if pattern.database_type not in detected_types:
                continue

            for conn_pattern in pattern.connection_patterns:
                if re.search(conn_pattern, func_name, re.IGNORECASE):
                    return self._create_connection(
                        node,
                        file_path,
                        pattern.database_type,
                        func_name,
                    )

        return None

    def _get_func_name(self, node: ast.Call) -> str:
        """Get function name from Call node.

        Args:
            node: AST Call node

        Returns:
            Function name or empty string
        """
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

    def _create_connection(
        self,
        node: ast.Call,
        file_path: str,
        db_type: DatabaseType,
        func_name: str,
    ) -> DatabaseConnection:
        """Create a DatabaseConnection from an AST node.

        Args:
            node: AST Call node
            file_path: Path to file
            db_type: Database type
            func_name: Function name

        Returns:
            DatabaseConnection instance
        """
        # Generate unique ID
        conn_id = hashlib.md5(  # noqa: S324
            f"{file_path}:{node.lineno}:{func_name}".encode(),
            usedforsecurity=False,
        ).hexdigest()[:12]

        # Extract connection string pattern (sanitized)
        conn_pattern = self._extract_connection_pattern(node)

        return DatabaseConnection(
            connection_id=f"db-{conn_id}",
            database_type=db_type,
            source_file=file_path,
            source_line=node.lineno,
            connection_string_pattern=conn_pattern,
            confidence=0.9,
        )

    def _extract_connection_pattern(self, node: ast.Call) -> str:
        """Extract and sanitize connection pattern from AST node.

        Args:
            node: AST Call node

        Returns:
            Sanitized connection pattern
        """
        # Look for string arguments that might be connection strings
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return self._sanitize_connection_string(arg.value)

        # Check keyword arguments
        for kwarg in node.keywords:
            if kwarg.arg in ("dsn", "host", "url", "connection_string"):
                if isinstance(kwarg.value, ast.Constant):
                    return self._sanitize_connection_string(str(kwarg.value.value))

        return ""

    def _sanitize_connection_string(self, conn_str: str) -> str:
        """Sanitize connection string by removing sensitive data.

        Args:
            conn_str: Raw connection string

        Returns:
            Sanitized connection string
        """
        # Remove passwords
        sanitized = re.sub(
            r"(password|pwd|pass)=[^&\s]+", r"\1=***", conn_str, flags=re.IGNORECASE
        )
        # Remove usernames
        sanitized = re.sub(
            r"(user|username|uid)=[^&\s]+", r"\1=***", sanitized, flags=re.IGNORECASE
        )
        # Remove connection credentials in URL format
        sanitized = re.sub(r"://[^:]+:[^@]+@", "://***:***@", sanitized)

        return sanitized

    def _analyze_with_regex(
        self,
        content: str,
        file_path: str,
        detected_types: set[DatabaseType],
    ) -> list[DatabaseConnection]:
        """Analyze content using regex patterns.

        Args:
            content: File content
            file_path: Path to file
            detected_types: Detected database types

        Returns:
            List of connections
        """
        connections: list[DatabaseConnection] = []
        lines = content.split("\n")

        for pattern in self._patterns:
            if pattern.database_type not in detected_types:
                continue

            for line_num, line in enumerate(lines, 1):
                for conn_pattern in pattern.connection_patterns:
                    if re.search(conn_pattern, line, re.IGNORECASE):
                        # Check read/write patterns
                        is_read = any(
                            re.search(rp, content, re.IGNORECASE)
                            for rp in pattern.read_patterns
                        )
                        is_write = any(
                            re.search(wp, content, re.IGNORECASE)
                            for wp in pattern.write_patterns
                        )

                        # Extract tables
                        tables = self._extract_tables(content, pattern.table_patterns)

                        conn_id = hashlib.md5(  # noqa: S324
                            f"{file_path}:{line_num}:{pattern.name}".encode(),
                            usedforsecurity=False,
                        ).hexdigest()[:12]

                        connections.append(
                            DatabaseConnection(
                                connection_id=f"db-{conn_id}",
                                database_type=pattern.database_type,
                                source_file=file_path,
                                source_line=line_num,
                                tables_accessed=tables,
                                is_read=is_read,
                                is_write=is_write,
                                confidence=0.8,
                            )
                        )
                        break

        return connections

    def _extract_tables(self, content: str, table_patterns: list[str]) -> list[str]:
        """Extract table names from content.

        Args:
            content: File content
            table_patterns: Regex patterns for table detection

        Returns:
            List of table names
        """
        tables: set[str] = set()

        for pattern in table_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            tables.update(matches)

        return list(tables)

    def _is_duplicate(
        self,
        conn: DatabaseConnection,
        existing: list[DatabaseConnection],
    ) -> bool:
        """Check if connection is a duplicate.

        Args:
            conn: Connection to check
            existing: Existing connections

        Returns:
            True if duplicate
        """
        for ex in existing:
            if (
                ex.source_file == conn.source_file
                and ex.source_line == conn.source_line
                and ex.database_type == conn.database_type
            ):
                return True
        return False

    def _get_mock_connections(self, path: str) -> list[DatabaseConnection]:
        """Get mock connections for testing.

        Args:
            path: File or directory path

        Returns:
            List of mock connections
        """
        return [
            DatabaseConnection(
                connection_id="db-mock-postgres",
                database_type=DatabaseType.POSTGRESQL,
                source_file=f"{path}/services/user_service.py",
                source_line=45,
                connection_string_pattern="postgresql://***:***@localhost:5432/users",
                tables_accessed=["users", "profiles", "sessions"],
                is_read=True,
                is_write=True,
                pool_config={"min_size": 5, "max_size": 20},
                confidence=0.95,
            ),
            DatabaseConnection(
                connection_id="db-mock-dynamodb",
                database_type=DatabaseType.DYNAMODB,
                source_file=f"{path}/services/cache_service.py",
                source_line=23,
                tables_accessed=["cache-table", "sessions-table"],
                is_read=True,
                is_write=True,
                confidence=0.9,
            ),
            DatabaseConnection(
                connection_id="db-mock-redis",
                database_type=DatabaseType.REDIS,
                source_file=f"{path}/services/cache_service.py",
                source_line=78,
                connection_string_pattern="redis://localhost:6379",
                is_read=True,
                is_write=True,
                pool_config={"max_connections": 10},
                confidence=0.85,
            ),
        ]
