"""
Aura Code Intelligence Fivetran Connector

Implements the Fivetran Connector SDK specification for syncing
vulnerability findings and code patterns to data warehouses.

ADR-048 Phase 5: Fivetran Connector
"""

import logging
from typing import Any

import requests
from fivetran_connector_sdk import Connector, Operations
from fivetran_connector_sdk.protos import common_pb2

logger = logging.getLogger(__name__)


class AuraConnector(Connector):
    """
    Fivetran connector for Aura Code Intelligence Platform.

    Syncs vulnerability findings, code patterns, repositories,
    and scan history to supported data warehouses.
    """

    def __init__(self):
        super().__init__()
        self.server_url: str = ""
        self.api_key: str = ""
        self.organization_id: str = ""
        self.session: requests.Session | None = None

    def configure(self, configuration: dict[str, Any]) -> None:
        """Configure the connector with user-provided settings."""
        self.server_url = configuration.get("server_url", "").rstrip("/")
        self.api_key = configuration.get("api_key", "")
        self.organization_id = configuration.get("organization_id", "")

        if not self.server_url:
            raise ValueError("server_url is required")
        if not self.api_key:
            raise ValueError("api_key is required")
        if not self.organization_id:
            raise ValueError("organization_id is required")

        # Initialize session
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-Api-Key": self.api_key,
                "X-Organization-Id": self.organization_id,
                "Content-Type": "application/json",
            }
        )

    def test(self) -> common_pb2.TestResponse:
        """Test connectivity to the Aura API."""
        try:
            response = self.session.post(
                f"{self.server_url}/api/v1/export/fivetran/test",
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                return common_pb2.TestResponse(success=True)
            else:
                return common_pb2.TestResponse(
                    success=False,
                    failure=result.get("message", "Connection test failed"),
                )
        except requests.exceptions.RequestException as e:
            logger.error(f"Connection test failed: {e}")
            return common_pb2.TestResponse(
                success=False,
                failure=str(e),
            )

    def schema(self) -> dict[str, Any]:
        """
        Return the schema for all tables.

        This defines the structure of data that will be synced.
        """
        try:
            response = self.session.post(
                f"{self.server_url}/api/v1/export/fivetran/schema",
                timeout=30,
            )
            response.raise_for_status()
            return response.json().get("tables", {})
        except requests.exceptions.RequestException as e:
            logger.error(f"Schema discovery failed: {e}")
            # Return fallback schema
            return self._get_fallback_schema()

    def _get_fallback_schema(self) -> dict[str, Any]:
        """Return fallback schema if API call fails."""
        return {
            "findings": {
                "primary_key": ["finding_id"],
                "columns": {
                    "finding_id": {"type": "STRING", "nullable": False},
                    "file_path": {"type": "STRING", "nullable": False},
                    "line_start": {"type": "INT", "nullable": True},
                    "line_end": {"type": "INT", "nullable": True},
                    "severity": {"type": "STRING", "nullable": False},
                    "category": {"type": "STRING", "nullable": True},
                    "title": {"type": "STRING", "nullable": False},
                    "description": {"type": "STRING", "nullable": True},
                    "cwe_id": {"type": "STRING", "nullable": True},
                    "owasp_category": {"type": "STRING", "nullable": True},
                    "cvss_score": {"type": "DOUBLE", "nullable": True},
                    "has_patch": {"type": "BOOLEAN", "nullable": False},
                    "repository_id": {"type": "STRING", "nullable": False},
                    "created_at": {"type": "UTC_DATETIME", "nullable": False},
                    "updated_at": {"type": "UTC_DATETIME", "nullable": True},
                },
            },
            "code_patterns": {
                "primary_key": ["pattern_id"],
                "columns": {
                    "pattern_id": {"type": "STRING", "nullable": False},
                    "pattern_type": {"type": "STRING", "nullable": False},
                    "name": {"type": "STRING", "nullable": False},
                    "file_path": {"type": "STRING", "nullable": False},
                    "occurrences": {"type": "INT", "nullable": False},
                    "complexity_score": {"type": "DOUBLE", "nullable": True},
                    "repository_id": {"type": "STRING", "nullable": False},
                    "created_at": {"type": "UTC_DATETIME", "nullable": False},
                },
            },
            "repositories": {
                "primary_key": ["repository_id"],
                "columns": {
                    "repository_id": {"type": "STRING", "nullable": False},
                    "name": {"type": "STRING", "nullable": False},
                    "url": {"type": "STRING", "nullable": True},
                    "provider": {"type": "STRING", "nullable": False},
                    "default_branch": {"type": "STRING", "nullable": True},
                    "language": {"type": "STRING", "nullable": True},
                    "last_scan_at": {"type": "UTC_DATETIME", "nullable": True},
                    "finding_count": {"type": "INT", "nullable": True},
                    "created_at": {"type": "UTC_DATETIME", "nullable": False},
                },
            },
            "scan_history": {
                "primary_key": ["scan_id"],
                "columns": {
                    "scan_id": {"type": "STRING", "nullable": False},
                    "repository_id": {"type": "STRING", "nullable": False},
                    "status": {"type": "STRING", "nullable": False},
                    "scan_type": {"type": "STRING", "nullable": False},
                    "findings_count": {"type": "INT", "nullable": True},
                    "duration_seconds": {"type": "DOUBLE", "nullable": True},
                    "triggered_by": {"type": "STRING", "nullable": True},
                    "started_at": {"type": "UTC_DATETIME", "nullable": False},
                    "completed_at": {"type": "UTC_DATETIME", "nullable": True},
                },
            },
            "metrics": {
                "primary_key": ["metric_id"],
                "columns": {
                    "metric_id": {"type": "STRING", "nullable": False},
                    "metric_name": {"type": "STRING", "nullable": False},
                    "metric_value": {"type": "DOUBLE", "nullable": False},
                    "dimensions": {"type": "JSON", "nullable": True},
                    "repository_id": {"type": "STRING", "nullable": True},
                    "timestamp": {"type": "UTC_DATETIME", "nullable": False},
                },
            },
        }

    def update(self, state: dict[str, Any]) -> Operations:
        """
        Perform incremental sync from Aura API.

        Args:
            state: Previous sync state with cursors

        Yields:
            Operations for upserting records to destination
        """
        try:
            response = self.session.post(
                f"{self.server_url}/api/v1/export/fivetran/sync",
                json=state,
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()

            # Process insert operations for each table
            for table_name, records in result.get("insert", {}).items():
                for record in records:
                    yield Operations.upsert(table_name, record)

            # Process delete operations if any
            for table_name, records in result.get("delete", {}).items():
                for record in records:
                    yield Operations.delete(table_name, record)

            # Update state checkpoint
            new_state = result.get("state", state)
            yield Operations.checkpoint(new_state)

            # Check if more data available
            if result.get("hasMore", False):
                yield Operations.update(new_state)

        except requests.exceptions.RequestException as e:
            logger.error(f"Sync failed: {e}")
            raise


# Connector configuration schema for Fivetran UI
CONFIGURATION_SCHEMA = {
    "type": "object",
    "properties": {
        "server_url": {
            "type": "string",
            "title": "Aura Server URL",
            "description": "URL of the Aura API server (e.g., https://api.aenealabs.com)",
            "format": "uri",
        },
        "api_key": {
            "type": "string",
            "title": "API Key",
            "description": "API key for authentication",
            "format": "password",
        },
        "organization_id": {
            "type": "string",
            "title": "Organization ID",
            "description": "Your Aura organization identifier",
        },
    },
    "required": ["server_url", "api_key", "organization_id"],
}


def main():
    """Main entry point for the connector."""
    connector = AuraConnector()
    connector.run()


if __name__ == "__main__":
    main()
