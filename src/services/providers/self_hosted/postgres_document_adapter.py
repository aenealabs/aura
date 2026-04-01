"""
Project Aura - PostgreSQL Document Adapter

Adapter for PostgreSQL implementing key-value document storage.
Replaces DynamoDB for self-hosted deployments using JSONB columns.

See ADR-049: Self-Hosted Deployment Strategy
See DYNAMODB_SCHEMA_REFERENCE.md for table schemas

Environment Variables:
    POSTGRES_HOST: PostgreSQL host (default: localhost)
    POSTGRES_PORT: PostgreSQL port (default: 5432)
    POSTGRES_DATABASE: Database name (default: aura)
    POSTGRES_USERNAME: Username (default: aura)
    POSTGRES_PASSWORD: Password (required)
    POSTGRES_SSLMODE: SSL mode (default: require)
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Lazy import asyncpg
_asyncpg = None


def _get_asyncpg():
    """Lazy import asyncpg."""
    global _asyncpg
    if _asyncpg is None:
        try:
            import asyncpg

            _asyncpg = asyncpg
        except ImportError:
            raise ImportError(
                "asyncpg package not installed. Install with: pip install asyncpg"
            )
    return _asyncpg


class PostgresDocumentAdapter:
    """
    PostgreSQL adapter for document storage.

    Provides DynamoDB-compatible key-value operations using PostgreSQL
    with JSONB columns for flexible document storage.

    Features:
    - Automatic table creation with indexes
    - JSONB for document storage with GIN indexes
    - TTL support via background job
    - Composite key support (hash + range keys)
    """

    # Table definitions based on DYNAMODB_SCHEMA_REFERENCE.md
    TABLE_SCHEMAS = {
        "cost_tracking": {
            "pk": "user_id",
            "sk": "timestamp",
            "gsi": [("date", "timestamp")],
        },
        "user_sessions": {
            "pk": "session_id",
            "sk": None,
            "gsi": [("user_id", None)],
            "ttl": "ttl",
        },
        "codegen_jobs": {
            "pk": "job_id",
            "sk": None,
            "gsi": [("user_id", "created_at"), ("status", "created_at")],
        },
        "ingestion_jobs": {
            "pk": "job_id",
            "sk": None,
            "gsi": [
                ("repository_id", "created_at"),
                ("status", "created_at"),
                ("date_partition", "created_at"),
            ],
            "ttl": "ttl",
        },
        "codebase_metadata": {
            "pk": "codebase_id",
            "sk": None,
            "gsi": [("user_id", None)],
        },
        "platform_settings": {
            "pk": "settings_type",
            "sk": "settings_key",
        },
        "anomalies": {
            "pk": "anomaly_id",
            "sk": "timestamp",
            "gsi": [("severity", "timestamp"), ("source", "timestamp")],
        },
        "agent_execution_logs": {
            "pk": "execution_id",
            "sk": "timestamp",
            "gsi": [("agent_id", "timestamp"), ("status", "timestamp")],
        },
        "onboarding_state": {
            "pk": "user_id",
            "sk": None,
        },
        "team_invitations": {
            "pk": "invitation_id",
            "sk": None,
            "gsi": [("email", None), ("tenant_id", "created_at")],
            "ttl": "expires_at",
        },
    }

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        username: str | None = None,
        password: str | None = None,
        sslmode: str | None = None,
        table_prefix: str = "aura_",
    ):
        """
        Initialize PostgreSQL document adapter.

        Args:
            host: PostgreSQL host
            port: PostgreSQL port
            database: Database name
            username: Username
            password: Password
            sslmode: SSL mode
            table_prefix: Prefix for table names
        """
        self.host = host or os.environ.get("POSTGRES_HOST", "localhost")
        self.port = port or int(os.environ.get("POSTGRES_PORT", "5432"))
        self.database = database or os.environ.get("POSTGRES_DATABASE", "aura")
        self.username = username or os.environ.get("POSTGRES_USERNAME", "aura")
        self.password = password or os.environ.get("POSTGRES_PASSWORD", "")
        self.sslmode = sslmode or os.environ.get("POSTGRES_SSLMODE", "require")
        self.table_prefix = table_prefix

        self._pool = None
        self._connected = False

    async def connect(self) -> bool:
        """Establish connection pool to PostgreSQL."""
        try:
            asyncpg = _get_asyncpg()
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
                ssl=self.sslmode,
                min_size=2,
                max_size=10,
            )
            self._connected = True
            logger.info(
                f"PostgreSQL adapter connected to {self.host}:{self.port}/{self.database}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            return False

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
        self._connected = False
        logger.info("PostgreSQL adapter disconnected")

    async def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected and self._pool is not None

    def _table_name(self, table: str) -> str:
        """Get full table name with prefix."""
        return f"{self.table_prefix}{table}"

    async def ensure_table(self, table: str) -> bool:
        """Create table if it doesn't exist."""
        schema = self.TABLE_SCHEMAS.get(table)
        if not schema:
            logger.warning(f"Unknown table schema: {table}")
            return False

        table_name = self._table_name(table)
        pk = schema["pk"]
        sk = schema.get("sk")

        # Build CREATE TABLE statement
        if sk:
            create_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {pk} TEXT NOT NULL,
                {sk} TEXT NOT NULL,
                data JSONB NOT NULL DEFAULT '{{}}',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY ({pk}, {sk})
            )
            """  # nosec B608
        else:
            create_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {pk} TEXT PRIMARY KEY,
                data JSONB NOT NULL DEFAULT '{{}}',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """  # nosec B608

        async with self._pool.acquire() as conn:
            await conn.execute(create_sql)

            # Create GIN index on JSONB data
            await conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{table_name}_data
                ON {table_name} USING GIN (data)
                """,  # nosec B608
            )

            # Create GSI-equivalent indexes
            for gsi in schema.get("gsi", []):
                gsi_pk, gsi_sk = gsi if isinstance(gsi, tuple) else (gsi, None)
                if gsi_sk:
                    await conn.execute(
                        f"""
                        CREATE INDEX IF NOT EXISTS idx_{table_name}_{gsi_pk}_{gsi_sk}
                        ON {table_name} ((data->>'{gsi_pk}'), (data->>'{gsi_sk}'))
                        """,  # nosec B608
                    )
                else:
                    await conn.execute(
                        f"""
                        CREATE INDEX IF NOT EXISTS idx_{table_name}_{gsi_pk}
                        ON {table_name} ((data->>'{gsi_pk}'))
                        """,  # nosec B608
                    )

        logger.info(f"Ensured table: {table_name}")
        return True

    async def put_item(
        self,
        table: str,
        item: dict[str, Any],
    ) -> bool:
        """
        Put an item into the table.

        Args:
            table: Table name
            item: Item data (must include primary key fields)

        Returns:
            True if successful
        """
        schema = self.TABLE_SCHEMAS.get(table)
        if not schema:
            raise ValueError(f"Unknown table: {table}")

        table_name = self._table_name(table)
        pk = schema["pk"]
        sk = schema.get("sk")

        pk_value = item.get(pk)
        if not pk_value:
            raise ValueError(f"Missing primary key: {pk}")

        async with self._pool.acquire() as conn:
            if sk:
                sk_value = item.get(sk)
                if not sk_value:
                    raise ValueError(f"Missing sort key: {sk}")

                await conn.execute(
                    f"""
                    INSERT INTO {table_name} ({pk}, {sk}, data, updated_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT ({pk}, {sk}) DO UPDATE
                    SET data = $3, updated_at = NOW()
                    """,  # nosec B608
                    pk_value,
                    sk_value,
                    json.dumps(item),
                )
            else:
                await conn.execute(
                    f"""
                    INSERT INTO {table_name} ({pk}, data, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT ({pk}) DO UPDATE
                    SET data = $2, updated_at = NOW()
                    """,  # nosec B608
                    pk_value,
                    json.dumps(item),
                )

        return True

    async def get_item(
        self,
        table: str,
        key: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Get an item by key.

        Args:
            table: Table name
            key: Key fields (pk and optionally sk)

        Returns:
            Item data or None if not found
        """
        schema = self.TABLE_SCHEMAS.get(table)
        if not schema:
            raise ValueError(f"Unknown table: {table}")

        table_name = self._table_name(table)
        pk = schema["pk"]
        sk = schema.get("sk")

        pk_value = key.get(pk)
        if not pk_value:
            raise ValueError(f"Missing primary key: {pk}")

        async with self._pool.acquire() as conn:
            if sk:
                sk_value = key.get(sk)
                if not sk_value:
                    raise ValueError(f"Missing sort key: {sk}")

                row = await conn.fetchrow(
                    f"""
                    SELECT data FROM {table_name}
                    WHERE {pk} = $1 AND {sk} = $2
                    """,  # nosec B608
                    pk_value,
                    sk_value,
                )
            else:
                row = await conn.fetchrow(
                    f"""
                    SELECT data FROM {table_name}
                    WHERE {pk} = $1
                    """,  # nosec B608
                    pk_value,
                )

        if row:
            return json.loads(row["data"])
        return None

    async def delete_item(
        self,
        table: str,
        key: dict[str, Any],
    ) -> bool:
        """
        Delete an item by key.

        Args:
            table: Table name
            key: Key fields

        Returns:
            True if deleted
        """
        schema = self.TABLE_SCHEMAS.get(table)
        if not schema:
            raise ValueError(f"Unknown table: {table}")

        table_name = self._table_name(table)
        pk = schema["pk"]
        sk = schema.get("sk")

        pk_value = key.get(pk)

        async with self._pool.acquire() as conn:
            if sk:
                sk_value = key.get(sk)
                result = await conn.execute(
                    f"""
                    DELETE FROM {table_name}
                    WHERE {pk} = $1 AND {sk} = $2
                    """,  # nosec B608
                    pk_value,
                    sk_value,
                )
            else:
                result = await conn.execute(
                    f"""
                    DELETE FROM {table_name}
                    WHERE {pk} = $1
                    """,  # nosec B608
                    pk_value,
                )

        return "DELETE" in result

    async def query(
        self,
        table: str,
        key_condition: dict[str, Any],
        filter_expression: dict[str, Any] | None = None,
        limit: int = 100,
        scan_forward: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Query items by key condition.

        Args:
            table: Table name
            key_condition: Key condition (pk and optionally sk condition)
            filter_expression: Additional filters on data fields
            limit: Maximum items to return
            scan_forward: Sort order (True = ascending)

        Returns:
            List of matching items
        """
        schema = self.TABLE_SCHEMAS.get(table)
        if not schema:
            raise ValueError(f"Unknown table: {table}")

        table_name = self._table_name(table)
        pk = schema["pk"]
        sk = schema.get("sk")

        # Build WHERE clause
        conditions = []
        params = []
        param_idx = 1

        for key, value in key_condition.items():
            if isinstance(value, dict):
                # Range condition
                for op, val in value.items():
                    if key in (pk, sk):
                        col = key
                    else:
                        col = f"data->>'{key}'"

                    if op == "begins_with":
                        conditions.append(f"{col} LIKE ${param_idx}")
                        params.append(f"{val}%")
                    elif op == "between":
                        conditions.append(
                            f"{col} BETWEEN ${param_idx} AND ${param_idx + 1}"
                        )
                        params.extend(val)
                        param_idx += 1
                    elif op in ("gt", ">"):
                        conditions.append(f"{col} > ${param_idx}")
                        params.append(val)
                    elif op in ("gte", ">="):
                        conditions.append(f"{col} >= ${param_idx}")
                        params.append(val)
                    elif op in ("lt", "<"):
                        conditions.append(f"{col} < ${param_idx}")
                        params.append(val)
                    elif op in ("lte", "<="):
                        conditions.append(f"{col} <= ${param_idx}")
                        params.append(val)
                    param_idx += 1
            else:
                # Equality condition
                if key in (pk, sk):
                    conditions.append(f"{key} = ${param_idx}")
                else:
                    conditions.append(f"data->>'{key}' = ${param_idx}")
                params.append(str(value))
                param_idx += 1

        # Add filter expression
        if filter_expression:
            for key, value in filter_expression.items():
                conditions.append(f"data->>'{key}' = ${param_idx}")
                params.append(str(value))
                param_idx += 1

        where_clause = " AND ".join(conditions)
        order = "ASC" if scan_forward else "DESC"
        order_col = sk if sk else pk

        query = f"""
            SELECT data FROM {table_name}
            WHERE {where_clause}
            ORDER BY {order_col} {order}
            LIMIT {limit}
        """  # nosec B608

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [json.loads(row["data"]) for row in rows]

    async def scan(
        self,
        table: str,
        filter_expression: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Scan all items in table with optional filter.

        Args:
            table: Table name
            filter_expression: Filter conditions
            limit: Maximum items to return

        Returns:
            List of matching items
        """
        table_name = self._table_name(table)

        conditions = []
        params = []
        param_idx = 1

        if filter_expression:
            for key, value in filter_expression.items():
                conditions.append(f"data->>'{key}' = ${param_idx}")
                params.append(str(value))
                param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT data FROM {table_name}
            WHERE {where_clause}
            LIMIT {limit}
        """  # nosec B608

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [json.loads(row["data"]) for row in rows]

    async def batch_write(
        self,
        table: str,
        items: list[dict[str, Any]],
    ) -> int:
        """
        Batch write items to table.

        Args:
            table: Table name
            items: List of items to write

        Returns:
            Number of items written
        """
        count = 0
        for item in items:
            if await self.put_item(table, item):
                count += 1
        return count

    async def get_health(self) -> dict[str, Any]:
        """Get database health status."""
        try:
            if await self.is_connected():
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow("SELECT version()")
                    version = row[0] if row else "unknown"

                return {
                    "status": "healthy",
                    "connected": True,
                    "host": self.host,
                    "port": self.port,
                    "database": self.database,
                    "version": version,
                }
            else:
                return {
                    "status": "disconnected",
                    "connected": False,
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    async def get_statistics(self) -> dict[str, Any]:
        """Get database statistics."""
        stats = {}
        async with self._pool.acquire() as conn:
            for table in self.TABLE_SCHEMAS:
                table_name = self._table_name(table)
                try:
                    row = await conn.fetchrow(
                        f"""
                        SELECT COUNT(*) as count FROM {table_name}
                        """,  # nosec B608
                    )
                    stats[table] = row["count"] if row else 0
                except Exception:
                    stats[table] = "table_not_exists"

        return {
            "tables": stats,
            "database": self.database,
        }
