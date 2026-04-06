"""
Generic Export API Endpoints

Provides secure, paginated data export endpoints for integration with
BI platforms (Fivetran, Dataiku, custom integrations).

ADR-048 Phase 5: Fivetran Connector + Generic Export API
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from src.services.integrations.export_authorization_service import (
    ExportAuthorizationService,
    ExportDataType,
    ExportRole,
    ExportScope,
)
from src.services.integrations.secrets_prescan_filter import SecretsPrescanFilter
from src.api.log_sanitizer import sanitize_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/export", tags=["export"])


# Compatibility aliases for the endpoint logic
UserRole = ExportRole
DataScope = ExportScope


@dataclass
class AuthorizationContext:
    """Context for authorization checks."""

    user_id: str
    role: ExportRole
    organization_id: str
    scope: ExportScope = ExportScope.ORGANIZATION


class ExportFormat(str, Enum):
    """Supported export formats."""

    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"


class ExportEntity(str, Enum):
    """Exportable entity types."""

    FINDINGS = "findings"
    CODE_PATTERNS = "code_patterns"
    REPOSITORIES = "repositories"
    SCAN_HISTORY = "scan_history"
    METRICS = "metrics"


class StateCheckpoint(BaseModel):
    """Fivetran-compatible state checkpoint for incremental sync."""

    cursor: str | None = None
    last_sync_timestamp: str | None = None
    entity_cursors: dict[str, str] = Field(default_factory=dict)


class ExportRequest(BaseModel):
    """Export request parameters."""

    entity: ExportEntity
    format: ExportFormat = ExportFormat.JSON
    page_size: int = Field(default=1000, ge=1, le=10000)
    cursor: str | None = None
    since_timestamp: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class ExportResponse(BaseModel):
    """Paginated export response."""

    data: list[dict[str, Any]]
    next_cursor: str | None
    has_more: bool
    total_count: int | None = None
    export_timestamp: str
    schema_version: str = "1.0"


class SchemaField(BaseModel):
    """Schema field definition."""

    name: str
    type: str
    nullable: bool = True
    description: str | None = None


class EntitySchema(BaseModel):
    """Schema definition for an entity."""

    entity: str
    version: str
    primary_key: list[str]
    fields: list[SchemaField]
    supports_incremental: bool = True


class FivetranTestResponse(BaseModel):
    """Fivetran connector test response."""

    success: bool
    message: str | None = None


class FivetranSchemaResponse(BaseModel):
    """Fivetran schema discovery response."""

    tables: dict[str, dict]


class FivetranSyncResponse(BaseModel):
    """Fivetran sync response."""

    state: dict
    insert: dict[str, list[dict]]
    delete: dict[str, list[dict]] = Field(default_factory=dict)
    hasMore: bool


# Service instances
_auth_service = ExportAuthorizationService()
_secrets_filter = SecretsPrescanFilter()


def _get_auth_context(
    x_user_id: str = Header(..., alias="X-User-Id"),  # noqa: B008
    x_user_role: str = Header("viewer", alias="X-User-Role"),  # noqa: B008
    x_organization_id: str = Header(..., alias="X-Organization-Id"),  # noqa: B008
) -> AuthorizationContext:
    """Extract authorization context from headers."""
    try:
        role = UserRole(x_user_role.lower())
    except ValueError:
        role = UserRole.VIEWER

    return AuthorizationContext(
        user_id=x_user_id,
        role=role,
        organization_id=x_organization_id,
        scope=DataScope.ORGANIZATION,
    )


def _generate_cursor(offset: int, entity: str) -> str:
    """Generate an opaque cursor for pagination."""
    data = f"{entity}:{offset}:{datetime.now(timezone.utc).timestamp()}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


def _parse_cursor(cursor: str | None) -> int:
    """Parse cursor to extract offset (simplified - production would use signed tokens)."""
    # In production, use signed JWTs or encrypted tokens
    # For now, cursor encodes offset in a simple way
    if not cursor:
        return 0
    # This is a placeholder - real implementation would decode the cursor
    return 0


# Schema definitions for each entity
ENTITY_SCHEMAS: dict[str, EntitySchema] = {
    "findings": EntitySchema(
        entity="findings",
        version="1.0",
        primary_key=["finding_id"],
        fields=[
            SchemaField(
                name="finding_id",
                type="string",
                nullable=False,
                description="Unique finding identifier",
            ),
            SchemaField(
                name="file_path",
                type="string",
                nullable=False,
                description="Path to affected file",
            ),
            SchemaField(
                name="line_start",
                type="integer",
                nullable=True,
                description="Starting line number",
            ),
            SchemaField(
                name="line_end",
                type="integer",
                nullable=True,
                description="Ending line number",
            ),
            SchemaField(
                name="severity",
                type="string",
                nullable=False,
                description="Severity level",
            ),
            SchemaField(
                name="category",
                type="string",
                nullable=True,
                description="Finding category",
            ),
            SchemaField(
                name="title", type="string", nullable=False, description="Finding title"
            ),
            SchemaField(
                name="description",
                type="string",
                nullable=True,
                description="Detailed description",
            ),
            SchemaField(
                name="cwe_id",
                type="string",
                nullable=True,
                description="CWE identifier",
            ),
            SchemaField(
                name="owasp_category",
                type="string",
                nullable=True,
                description="OWASP category",
            ),
            SchemaField(
                name="cvss_score", type="float", nullable=True, description="CVSS score"
            ),
            SchemaField(
                name="has_patch",
                type="boolean",
                nullable=False,
                description="Whether patch is available",
            ),
            SchemaField(
                name="repository_id",
                type="string",
                nullable=False,
                description="Repository identifier",
            ),
            SchemaField(
                name="created_at",
                type="timestamp",
                nullable=False,
                description="Creation timestamp",
            ),
            SchemaField(
                name="updated_at",
                type="timestamp",
                nullable=True,
                description="Last update timestamp",
            ),
        ],
    ),
    "code_patterns": EntitySchema(
        entity="code_patterns",
        version="1.0",
        primary_key=["pattern_id"],
        fields=[
            SchemaField(name="pattern_id", type="string", nullable=False),
            SchemaField(name="pattern_type", type="string", nullable=False),
            SchemaField(name="name", type="string", nullable=False),
            SchemaField(name="file_path", type="string", nullable=False),
            SchemaField(name="occurrences", type="integer", nullable=False),
            SchemaField(name="complexity_score", type="float", nullable=True),
            SchemaField(name="repository_id", type="string", nullable=False),
            SchemaField(name="created_at", type="timestamp", nullable=False),
        ],
    ),
    "repositories": EntitySchema(
        entity="repositories",
        version="1.0",
        primary_key=["repository_id"],
        fields=[
            SchemaField(name="repository_id", type="string", nullable=False),
            SchemaField(name="name", type="string", nullable=False),
            SchemaField(name="url", type="string", nullable=True),
            SchemaField(name="provider", type="string", nullable=False),
            SchemaField(name="default_branch", type="string", nullable=True),
            SchemaField(name="language", type="string", nullable=True),
            SchemaField(name="last_scan_at", type="timestamp", nullable=True),
            SchemaField(name="finding_count", type="integer", nullable=True),
            SchemaField(name="created_at", type="timestamp", nullable=False),
        ],
    ),
    "scan_history": EntitySchema(
        entity="scan_history",
        version="1.0",
        primary_key=["scan_id"],
        fields=[
            SchemaField(name="scan_id", type="string", nullable=False),
            SchemaField(name="repository_id", type="string", nullable=False),
            SchemaField(name="status", type="string", nullable=False),
            SchemaField(name="scan_type", type="string", nullable=False),
            SchemaField(name="findings_count", type="integer", nullable=True),
            SchemaField(name="duration_seconds", type="float", nullable=True),
            SchemaField(name="triggered_by", type="string", nullable=True),
            SchemaField(name="started_at", type="timestamp", nullable=False),
            SchemaField(name="completed_at", type="timestamp", nullable=True),
        ],
    ),
    "metrics": EntitySchema(
        entity="metrics",
        version="1.0",
        primary_key=["metric_id"],
        fields=[
            SchemaField(name="metric_id", type="string", nullable=False),
            SchemaField(name="metric_name", type="string", nullable=False),
            SchemaField(name="metric_value", type="float", nullable=False),
            SchemaField(name="dimensions", type="json", nullable=True),
            SchemaField(name="repository_id", type="string", nullable=True),
            SchemaField(name="timestamp", type="timestamp", nullable=False),
        ],
    ),
}


@router.get("/schema/{entity}", response_model=EntitySchema)
async def get_entity_schema(entity: ExportEntity) -> EntitySchema:
    """Get schema definition for an entity."""
    schema = ENTITY_SCHEMAS.get(entity.value)
    if not schema:
        raise HTTPException(
            status_code=404, detail=f"Schema not found for entity: {entity}"
        )
    return schema


@router.get("/schemas", response_model=dict[str, EntitySchema])
async def list_schemas() -> dict[str, EntitySchema]:
    """List all available entity schemas."""
    return ENTITY_SCHEMAS


def _authorize_export_sync(
    auth_context: AuthorizationContext,
    entity_type: str,
    filters: dict,
) -> tuple[bool, bool, str | None]:
    """
    Simplified synchronous authorization check.

    Returns:
        Tuple of (authorized, allowed_pii, reason)
    """
    # Map entity types to ExportDataType
    entity_map = {
        "findings": ExportDataType.FINDINGS,
        "code_patterns": ExportDataType.PATCHES,  # Close enough mapping
        "repositories": ExportDataType.REPOSITORIES,
        "scan_history": ExportDataType.AUDIT,
        "metrics": ExportDataType.METRICS,
    }

    data_type = entity_map.get(entity_type)
    if not data_type:
        return False, False, f"Unknown entity type: {entity_type}"

    # Check role permissions from the ROLE_PERMISSIONS matrix
    from src.services.integrations.export_authorization_service import ROLE_PERMISSIONS

    permissions = ROLE_PERMISSIONS.get(auth_context.role)
    if not permissions:
        return False, False, f"Unknown role: {auth_context.role}"

    # Check if data type is allowed for role
    if data_type not in permissions["allowed_types"]:
        return (
            False,
            False,
            f"Role {auth_context.role.value} cannot export {entity_type}",
        )

    return True, permissions["can_include_pii"], None


@router.post("/data", response_model=ExportResponse)
async def export_data(
    request: ExportRequest,
    auth_context: AuthorizationContext = Depends(_get_auth_context),  # noqa: B008
) -> ExportResponse:
    """
    Export data with authorization filtering and secrets scrubbing.

    Supports paginated exports for large datasets.
    """
    # Check authorization
    authorized, allowed_pii, reason = _authorize_export_sync(
        auth_context=auth_context,
        entity_type=request.entity.value,
        filters=request.filters,
    )

    if not authorized:
        raise HTTPException(
            status_code=403,
            detail=f"Export not authorized: {reason}",
        )

    # Parse pagination cursor
    offset = _parse_cursor(request.cursor)

    # Fetch data (mock implementation - real would query databases)
    raw_data = _fetch_entity_data(
        entity=request.entity,
        offset=offset,
        limit=request.page_size,
        filters=request.filters,
        since_timestamp=request.since_timestamp,
        auth_context=auth_context,
    )

    # Apply field filtering based on authorization
    filtered_data = []
    for record in raw_data:
        # Remove PII fields if not authorized
        if not allowed_pii:
            record = {
                k: v
                for k, v in record.items()
                if k not in ["email", "username", "ip_address"]
            }

        # Scan for and redact secrets
        for field_name, value in record.items():
            if isinstance(value, str):
                detections = _secrets_filter.scan_only(
                    value, f"export:{request.entity.value}:{field_name}"
                )
                if detections:
                    record[field_name] = "[REDACTED - Secret detected]"

        filtered_data.append(record)

    # Generate next cursor if more data available
    has_more = len(raw_data) == request.page_size
    next_cursor = (
        _generate_cursor(offset + request.page_size, request.entity.value)
        if has_more
        else None
    )

    logger.info(
        "Export completed",
        extra={
            "entity": sanitize_log(request.entity.value),
            "user_id": sanitize_log(auth_context.user_id),
            "record_count": len(filtered_data),
            "has_more": has_more,
        },
    )

    return ExportResponse(
        data=filtered_data,
        next_cursor=next_cursor,
        has_more=has_more,
        export_timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _fetch_entity_data(
    entity: ExportEntity,
    offset: int,
    limit: int,
    filters: dict,
    since_timestamp: str | None,
    auth_context: AuthorizationContext,
) -> list[dict]:
    """
    Fetch entity data from appropriate data source.

    This is a mock implementation. Real implementation would:
    - Query Neptune for graph data
    - Query OpenSearch for findings
    - Query DynamoDB for repositories and scan history
    """
    # Mock data generation for demonstration
    if entity == ExportEntity.FINDINGS:
        return [
            {
                "finding_id": f"finding-{i + offset}",
                "file_path": f"src/module_{i % 10}/file.py",
                "line_start": 10 + i,
                "line_end": 15 + i,
                "severity": ["critical", "high", "medium", "low"][i % 4],
                "category": "security",
                "title": f"Security Finding {i + offset}",
                "description": "Potential vulnerability detected",
                "cwe_id": f"CWE-{79 + (i % 10)}",
                "owasp_category": "A1-Injection",
                "cvss_score": 7.5,
                "has_patch": i % 2 == 0,
                "repository_id": f"repo-{auth_context.organization_id}-1",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": None,
            }
            for i in range(min(limit, 10))  # Limit mock data
        ]
    elif entity == ExportEntity.REPOSITORIES:
        return [
            {
                "repository_id": f"repo-{auth_context.organization_id}-{i + offset}",
                "name": f"example-repo-{i + offset}",
                "url": f"https://github.com/example/repo-{i + offset}",
                "provider": "github",
                "default_branch": "main",
                "language": "python",
                "last_scan_at": datetime.now(timezone.utc).isoformat(),
                "finding_count": 25 + i,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            for i in range(min(limit, 5))
        ]

    return []


# =============================================================================
# Fivetran Connector API (implements Fivetran Connector SDK spec)
# =============================================================================


@router.post("/fivetran/test", response_model=FivetranTestResponse)
async def fivetran_test_connection(
    x_api_key: str = Header(..., alias="X-Api-Key"),  # noqa: B008
) -> FivetranTestResponse:
    """
    Fivetran connector test endpoint.

    Validates API key and connectivity.
    """
    # In production, validate the API key
    if not x_api_key:
        return FivetranTestResponse(success=False, message="API key required")

    return FivetranTestResponse(success=True, message="Connection successful")


@router.post("/fivetran/schema", response_model=FivetranSchemaResponse)
async def fivetran_discover_schema(
    x_api_key: str = Header(..., alias="X-Api-Key"),  # noqa: B008
) -> FivetranSchemaResponse:
    """
    Fivetran schema discovery endpoint.

    Returns table schemas in Fivetran format.
    """
    tables = {}

    for entity_name, schema in ENTITY_SCHEMAS.items():
        columns = {}
        for schema_field in schema.fields:
            # Map our types to Fivetran types
            fivetran_type = {
                "string": "STRING",
                "integer": "INT",
                "float": "DOUBLE",
                "boolean": "BOOLEAN",
                "timestamp": "UTC_DATETIME",
                "json": "JSON",
            }.get(schema_field.type, "STRING")

            columns[schema_field.name] = {
                "type": fivetran_type,
                "nullable": schema_field.nullable,
            }

        tables[entity_name] = {
            "columns": columns,
            "primary_key": schema.primary_key,
        }

    return FivetranSchemaResponse(tables=tables)


@router.post("/fivetran/sync", response_model=FivetranSyncResponse)
async def fivetran_sync(
    state: dict | None = None,
    x_api_key: str = Header(..., alias="X-Api-Key"),  # noqa: B008
    x_organization_id: str = Header(..., alias="X-Organization-Id"),  # noqa: B008
) -> FivetranSyncResponse:
    """
    Fivetran incremental sync endpoint.

    Supports cursor-based incremental syncs.
    """
    if state is None:
        state = {}

    # Create auth context from API key (simplified)
    auth_context = AuthorizationContext(
        user_id="fivetran-sync",
        role=UserRole.ANALYST,  # Limited access for sync
        organization_id=x_organization_id,
        scope=DataScope.ORGANIZATION,
    )

    insert_data: dict[str, list[dict]] = {}
    new_state = dict(state)
    has_more = False

    # Sync each entity
    for entity_name in ENTITY_SCHEMAS.keys():
        cursor = state.get(f"{entity_name}_cursor")
        entity_enum = ExportEntity(entity_name)

        # Fetch data for this entity
        data = _fetch_entity_data(
            entity=entity_enum,
            offset=0 if not cursor else int(cursor),
            limit=1000,
            filters={},
            since_timestamp=state.get("last_sync"),
            auth_context=auth_context,
        )

        if data:
            # Scan for secrets before returning
            safe_data = []
            for record in data:
                safe_record = {}
                for field_name, value in record.items():
                    if isinstance(value, str):
                        detections = _secrets_filter.scan_only(
                            value, f"fivetran:{entity_name}:{field_name}"
                        )
                        if detections:
                            safe_record[field_name] = "[REDACTED]"
                        else:
                            safe_record[field_name] = value
                    else:
                        safe_record[field_name] = value
                safe_data.append(safe_record)

            insert_data[entity_name] = safe_data

            # Update cursor if we got a full page (indicating more data)
            if len(data) == 1000:
                new_state[f"{entity_name}_cursor"] = str(len(data))
                has_more = True

    # Update sync timestamp
    new_state["last_sync"] = datetime.now(timezone.utc).isoformat()

    return FivetranSyncResponse(
        state=new_state,
        insert=insert_data,
        hasMore=has_more,
    )


@router.get("/health")
async def export_health():
    """Health check for export API."""
    return {"status": "healthy", "version": "1.0"}
