"""
Project Aura - DynamoDB to PostgreSQL Migrator

Migrates document data from AWS DynamoDB to PostgreSQL with JSONB storage.
Supports all Project Aura table schemas.

See ADR-049: Self-Hosted Deployment Strategy
"""

import json
import logging
from typing import Any

from src.migration.base import BaseMigrator, MigrationConfig, MigrationError

logger = logging.getLogger(__name__)

# Table schemas from PostgresDocumentAdapter
TABLE_SCHEMAS = {
    "cost_tracking": {"pk": "user_id", "sk": "timestamp"},
    "user_sessions": {"pk": "session_id", "sk": None, "ttl": "ttl"},
    "codegen_jobs": {"pk": "job_id", "sk": None},
    "ingestion_jobs": {"pk": "job_id", "sk": None, "ttl": "ttl"},
    "codebase_metadata": {"pk": "codebase_id", "sk": None},
    "platform_settings": {"pk": "settings_type", "sk": "settings_key"},
    "anomalies": {"pk": "anomaly_id", "sk": "timestamp"},
    "agent_execution_logs": {"pk": "execution_id", "sk": "timestamp"},
    "onboarding_state": {"pk": "user_id", "sk": None},
    "team_invitations": {"pk": "invitation_id", "sk": None, "ttl": "expires_at"},
}


class DynamoDBToPostgresMigrator(BaseMigrator):
    """
    Migrates document data from DynamoDB to PostgreSQL.

    Features:
    - Schema-aware table migration
    - JSONB storage for flexible documents
    - GSI-equivalent index creation
    - TTL attribute preservation
    """

    def __init__(
        self,
        dynamodb_region: str = "us-east-1",
        dynamodb_table_prefix: str = "aura_",
        postgres_host: str = "localhost",
        postgres_port: int = 5432,
        postgres_database: str = "aura",
        postgres_username: str = "aura",
        postgres_password: str = "",
        postgres_table_prefix: str = "aura_",
        tables: list[str] | None = None,
        config: MigrationConfig | None = None,
    ):
        """
        Initialize DynamoDB to PostgreSQL migrator.

        Args:
            dynamodb_region: AWS region for DynamoDB
            dynamodb_table_prefix: Prefix for DynamoDB table names
            postgres_host: PostgreSQL host
            postgres_port: PostgreSQL port
            postgres_database: PostgreSQL database name
            postgres_username: PostgreSQL username
            postgres_password: PostgreSQL password
            postgres_table_prefix: Prefix for PostgreSQL table names
            tables: Specific tables to migrate (default: all)
            config: Migration configuration
        """
        super().__init__(config)
        self.dynamodb_region = dynamodb_region
        self.dynamodb_table_prefix = dynamodb_table_prefix
        self.postgres_host = postgres_host
        self.postgres_port = postgres_port
        self.postgres_database = postgres_database
        self.postgres_username = postgres_username
        self.postgres_password = postgres_password
        self.postgres_table_prefix = postgres_table_prefix
        self.tables = tables or list(TABLE_SCHEMAS.keys())

        self._dynamodb = None
        self._postgres_pool = None
        self._current_table: str | None = None
        self._table_items: dict[str, list[dict[str, Any]]] = {}

    @property
    def source_type(self) -> str:
        return "dynamodb"

    @property
    def target_type(self) -> str:
        return "postgresql"

    async def connect_source(self) -> bool:
        """Connect to DynamoDB."""
        try:
            import boto3

            self._dynamodb = boto3.resource(
                "dynamodb", region_name=self.dynamodb_region
            )
            # Test connection by listing tables
            client = self._dynamodb.meta.client
            client.list_tables(Limit=1)
            logger.info(f"Connected to DynamoDB in {self.dynamodb_region}")
            return True
        except ImportError:
            logger.warning("boto3 not installed, using mock mode")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to DynamoDB: {e}")
            return False

    async def connect_target(self) -> bool:
        """Connect to PostgreSQL."""
        try:
            import asyncpg

            self._postgres_pool = await asyncpg.create_pool(
                host=self.postgres_host,
                port=self.postgres_port,
                database=self.postgres_database,
                user=self.postgres_username,
                password=self.postgres_password,
                min_size=2,
                max_size=10,
            )
            logger.info(
                f"Connected to PostgreSQL at {self.postgres_host}:{self.postgres_port}"
            )
            return True
        except ImportError:
            logger.warning("asyncpg not installed, using mock mode")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from both services."""
        self._dynamodb = None
        if self._postgres_pool:
            await self._postgres_pool.close()
            self._postgres_pool = None

    async def count_source_items(self) -> int:
        """Count total items across all tables."""
        if not self._dynamodb:
            return 0

        total = 0
        for table_name in self.tables:
            try:
                full_table_name = f"{self.dynamodb_table_prefix}{table_name}"
                table = self._dynamodb.Table(full_table_name)
                response = table.scan(Select="COUNT")
                count = response.get("Count", 0)

                # Handle pagination
                while "LastEvaluatedKey" in response:
                    response = table.scan(
                        Select="COUNT",
                        ExclusiveStartKey=response["LastEvaluatedKey"],
                    )
                    count += response.get("Count", 0)

                total += count
                logger.info(f"Table {table_name}: {count} items")

            except Exception as e:
                logger.warning(f"Failed to count items in {table_name}: {e}")

        return total

    async def fetch_source_batch(self, offset: int, limit: int) -> list[dict[str, Any]]:
        """Fetch batch of items from DynamoDB tables."""
        if not self._dynamodb:
            return []

        # Load all items from all tables on first call
        if offset == 0:
            self._table_items = {}
            for table_name in self.tables:
                self._table_items[table_name] = await self._scan_table(table_name)

        # Flatten all items with table info
        all_items = []
        for table_name, table_items in self._table_items.items():
            for item in table_items:
                all_items.append({"_table": table_name, "_item": item})

        # Return requested slice
        return all_items[offset : offset + limit]

    async def _scan_table(self, table_name: str) -> list[dict[str, Any]]:
        """Scan all items from a DynamoDB table."""
        items = []
        full_table_name = f"{self.dynamodb_table_prefix}{table_name}"

        try:
            table = self._dynamodb.Table(full_table_name)
            response = table.scan()
            items.extend(response.get("Items", []))

            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = table.scan(
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                items.extend(response.get("Items", []))

        except Exception as e:
            logger.warning(f"Failed to scan table {table_name}: {e}")

        return items

    async def migrate_item(self, item: dict[str, Any]) -> bool:
        """Migrate a single item to PostgreSQL."""
        if not self._postgres_pool:
            return True  # Mock mode

        table_name = item["_table"]
        data = item["_item"]

        try:
            # Ensure table exists
            await self._ensure_postgres_table(table_name)

            # Insert item
            await self._insert_item(table_name, data)
            return True

        except Exception as e:
            raise MigrationError(
                f"Failed to migrate item to {table_name}: {e}",
                item_id=str(data.get("pk", data.get("id", "unknown"))),
            )

    async def _ensure_postgres_table(self, table_name: str) -> None:
        """Create PostgreSQL table if it doesn't exist."""
        schema = TABLE_SCHEMAS.get(table_name)
        if not schema:
            raise MigrationError(f"Unknown table schema: {table_name}")

        full_table_name = f"{self.postgres_table_prefix}{table_name}"
        pk = schema["pk"]
        sk = schema.get("sk")

        async with self._postgres_pool.acquire() as conn:
            # Build CREATE TABLE
            if sk:
                await conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {full_table_name} (
                        {pk} TEXT NOT NULL,
                        {sk} TEXT NOT NULL,
                        data JSONB NOT NULL DEFAULT '{{}}',
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW(),
                        PRIMARY KEY ({pk}, {sk})
                    )
                """
                )
            else:
                await conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {full_table_name} (
                        {pk} TEXT PRIMARY KEY,
                        data JSONB NOT NULL DEFAULT '{{}}',
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """
                )

            # Create JSONB index
            await conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{full_table_name}_data
                ON {full_table_name} USING GIN (data)
            """
            )

    async def _insert_item(self, table_name: str, data: dict[str, Any]) -> None:
        """Insert an item into PostgreSQL table."""
        schema = TABLE_SCHEMAS.get(table_name)
        full_table_name = f"{self.postgres_table_prefix}{table_name}"
        pk = schema["pk"]
        sk = schema.get("sk")

        # Convert DynamoDB types to standard Python types
        clean_data = self._convert_dynamodb_types(data)
        pk_value = str(clean_data.get(pk, ""))

        async with self._postgres_pool.acquire() as conn:
            if sk:
                sk_value = str(clean_data.get(sk, ""))
                await conn.execute(
                    f"""
                    INSERT INTO {full_table_name} ({pk}, {sk}, data, updated_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT ({pk}, {sk}) DO UPDATE
                    SET data = $3, updated_at = NOW()
                    """,  # nosec B608
                    pk_value,
                    sk_value,
                    json.dumps(clean_data),
                )
            else:
                await conn.execute(
                    f"""
                    INSERT INTO {full_table_name} ({pk}, data, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT ({pk}) DO UPDATE
                    SET data = $2, updated_at = NOW()
                    """,  # nosec B608
                    pk_value,
                    json.dumps(clean_data),
                )

    def _convert_dynamodb_types(self, item: dict[str, Any]) -> dict[str, Any]:
        """Convert DynamoDB type descriptors to Python types."""
        from decimal import Decimal

        result = {}
        for key, value in item.items():
            if isinstance(value, Decimal):
                # Convert Decimal to int or float
                result[key] = int(value) if value % 1 == 0 else float(value)
            elif isinstance(value, dict):
                # Recurse for nested objects
                result[key] = self._convert_dynamodb_types(value)
            elif isinstance(value, list):
                # Handle lists
                result[key] = [
                    self._convert_dynamodb_types(v) if isinstance(v, dict) else v
                    for v in value
                ]
            elif isinstance(value, set):
                # Convert sets to lists
                result[key] = list(value)
            else:
                result[key] = value
        return result

    async def verify_item(self, item: dict[str, Any]) -> bool:
        """Verify item was migrated correctly."""
        if not self._postgres_pool:
            return True  # Mock mode

        try:
            table_name = item["_table"]
            data = item["_item"]
            schema = TABLE_SCHEMAS.get(table_name)
            full_table_name = f"{self.postgres_table_prefix}{table_name}"
            pk = schema["pk"]
            sk = schema.get("sk")

            clean_data = self._convert_dynamodb_types(data)
            pk_value = str(clean_data.get(pk, ""))

            async with self._postgres_pool.acquire() as conn:
                if sk:
                    sk_value = str(clean_data.get(sk, ""))
                    row = await conn.fetchrow(
                        f"SELECT data FROM {full_table_name} WHERE {pk} = $1 AND {sk} = $2",
                        pk_value,
                        sk_value,
                    )
                else:
                    row = await conn.fetchrow(
                        f"SELECT data FROM {full_table_name} WHERE {pk} = $1",
                        pk_value,
                    )

                return row is not None

        except Exception as e:
            logger.warning(f"Verification failed: {e}")
            return False
