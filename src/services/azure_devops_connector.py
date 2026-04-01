"""
Project Aura - Azure DevOps Connector

Implements ADR-028 Phase 8: Enterprise Connector Expansion

Azure DevOps REST API connector for:
- Pipeline management (trigger, status, logs)
- Work item management (create, update, query)
- Repository integration
- Build and release management

SECURITY: Only available in ENTERPRISE or HYBRID mode.

Usage:
    >>> from src.services.azure_devops_connector import AzureDevOpsConnector
    >>> ado = AzureDevOpsConnector(
    ...     organization="myorg",
    ...     project="myproject",
    ...     pat="personal-access-token"
    ... )
    >>> await ado.trigger_pipeline(pipeline_id=123)
"""

import base64
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import aiohttp

from src.config import require_enterprise_mode
from src.services.external_tool_connectors import (
    ConnectorResult,
    ConnectorStatus,
    ExternalToolConnector,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class PipelineRunState(Enum):
    """Azure DevOps pipeline run states."""

    UNKNOWN = "unknown"
    CANCELING = "canceling"
    COMPLETED = "completed"
    IN_PROGRESS = "inProgress"
    NOT_STARTED = "notStarted"


class PipelineRunResult(Enum):
    """Azure DevOps pipeline run results."""

    CANCELED = "canceled"
    FAILED = "failed"
    SUCCEEDED = "succeeded"
    UNKNOWN = "unknown"


class WorkItemType(Enum):
    """Azure DevOps work item types."""

    BUG = "Bug"
    TASK = "Task"
    USER_STORY = "User Story"
    FEATURE = "Feature"
    EPIC = "Epic"
    ISSUE = "Issue"
    IMPEDIMENT = "Impediment"


class WorkItemState(Enum):
    """Common Azure DevOps work item states."""

    NEW = "New"
    ACTIVE = "Active"
    RESOLVED = "Resolved"
    CLOSED = "Closed"
    REMOVED = "Removed"


class WorkItemSeverity(Enum):
    """Azure DevOps severity levels for bugs."""

    CRITICAL = "1 - Critical"
    HIGH = "2 - High"
    MEDIUM = "3 - Medium"
    LOW = "4 - Low"


class WorkItemPriority(Enum):
    """Azure DevOps priority levels."""

    P1 = 1
    P2 = 2
    P3 = 3
    P4 = 4


@dataclass
class WorkItem:
    """Azure DevOps work item structure."""

    title: str
    work_item_type: WorkItemType = WorkItemType.TASK
    description: str = ""
    state: WorkItemState | None = None
    assigned_to: str | None = None
    area_path: str | None = None
    iteration_path: str | None = None
    priority: WorkItemPriority | None = None
    severity: WorkItemSeverity | None = None  # For bugs
    tags: list[str] | None = None
    parent_id: int | None = None
    additional_fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineRun:
    """Azure DevOps pipeline run details."""

    run_id: int
    pipeline_id: int
    pipeline_name: str
    state: PipelineRunState
    result: PipelineRunResult | None = None
    created_date: str | None = None
    finished_date: str | None = None
    source_branch: str | None = None
    source_version: str | None = None
    url: str | None = None


# =============================================================================
# Azure DevOps Connector
# =============================================================================


class AzureDevOpsConnector(ExternalToolConnector):
    """
    Azure DevOps connector for Microsoft DevOps integration.

    Supports:
    - Pipeline management (trigger, cancel, status)
    - Work item management (create, update, query)
    - Build management
    - Repository operations
    """

    def __init__(
        self,
        organization: str,
        project: str,
        pat: str,
        api_version: str = "7.1",
        timeout_seconds: float = 30.0,
    ):
        """
        Initialize Azure DevOps connector.

        Args:
            organization: Azure DevOps organization name
            project: Project name
            pat: Personal Access Token
            api_version: API version (default: 7.1)
            timeout_seconds: Request timeout
        """
        super().__init__("azure_devops", timeout_seconds)

        self.organization = organization
        self.project = project
        self.api_version = api_version

        # Base URLs
        self.base_url = f"https://dev.azure.com/{organization}/{project}"
        self.vssps_url = f"https://vssps.dev.azure.com/{organization}"

        # Build Basic auth header (PAT with empty username)
        credentials = f":{pat}"
        self._auth_header = base64.b64encode(credentials.encode()).decode()

    def _get_headers(self, content_type: str = "application/json") -> dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Basic {self._auth_header}",
            "Content-Type": content_type,
            "Accept": "application/json",
        }

    def _get_api_url(self, path: str, area: str = "") -> str:
        """Build API URL with version."""
        base = f"{self.base_url}/_apis"
        if area:
            base = f"https://dev.azure.com/{self.organization}/_apis/{area}"
        return f"{base}/{path}?api-version={self.api_version}"

    # =========================================================================
    # Pipeline Management
    # =========================================================================

    @require_enterprise_mode
    async def trigger_pipeline(
        self,
        pipeline_id: int,
        branch: str = "main",
        variables: dict[str, str] | None = None,
        stages_to_skip: list[str] | None = None,
        template_parameters: dict[str, str] | None = None,
    ) -> ConnectorResult:
        """
        Trigger a pipeline run.

        Args:
            pipeline_id: Pipeline ID
            branch: Branch to run against
            variables: Pipeline variables to override
            stages_to_skip: Stages to skip
            template_parameters: Template parameters
        """
        start_time = time.time()

        payload: dict[str, Any] = {
            "resources": {"repositories": {"self": {"refName": f"refs/heads/{branch}"}}}
        }

        if variables:
            payload["variables"] = {k: {"value": v} for k, v in variables.items()}
        if stages_to_skip:
            payload["stagesToSkip"] = stages_to_skip
        if template_parameters:
            payload["templateParameters"] = template_parameters

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    self._get_api_url(f"pipelines/{pipeline_id}/runs"),
                    json=payload,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    if response.status in (200, 201):
                        self._status = ConnectorStatus.CONNECTED
                        self._record_request(latency_ms, True)
                        run_id = data.get("id")
                        logger.info(
                            f"Azure DevOps pipeline triggered: {pipeline_id}, run: {run_id}"
                        )
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "run_id": run_id,
                                "pipeline_id": pipeline_id,
                                "state": data.get("state"),
                                "url": data.get("_links", {})
                                .get("web", {})
                                .get("href"),
                            },
                            request_id=str(run_id),
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        error_msg = data.get("message", str(data))
                        self._last_error = error_msg
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error_msg,
                            data=data,
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            logger.exception(f"Azure DevOps connector error: {e}")
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def get_pipeline_run(self, pipeline_id: int, run_id: int) -> ConnectorResult:
        """
        Get pipeline run status.

        Args:
            pipeline_id: Pipeline ID
            run_id: Run ID
        """
        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    self._get_api_url(f"pipelines/{pipeline_id}/runs/{run_id}"),
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        run = PipelineRun(
                            run_id=data.get("id"),
                            pipeline_id=data.get("pipeline", {}).get("id"),
                            pipeline_name=data.get("pipeline", {}).get("name", ""),
                            state=PipelineRunState(data.get("state", "unknown")),
                            result=(
                                PipelineRunResult(data.get("result"))
                                if data.get("result")
                                else None
                            ),
                            created_date=data.get("createdDate"),
                            finished_date=data.get("finishedDate"),
                            source_branch=data.get("resources", {})
                            .get("repositories", {})
                            .get("self", {})
                            .get("refName"),
                            url=data.get("_links", {}).get("web", {}).get("href"),
                        )
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "run_id": run.run_id,
                                "pipeline_id": run.pipeline_id,
                                "pipeline_name": run.pipeline_name,
                                "state": run.state.value,
                                "result": run.result.value if run.result else None,
                                "created_date": run.created_date,
                                "finished_date": run.finished_date,
                                "url": run.url,
                            },
                            request_id=str(run_id),
                            latency_ms=latency_ms,
                        )
                    else:
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=data.get("message", str(data)),
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def cancel_pipeline_run(
        self, pipeline_id: int, run_id: int
    ) -> ConnectorResult:
        """
        Cancel a running pipeline.

        Args:
            pipeline_id: Pipeline ID
            run_id: Run ID
        """
        start_time = time.time()

        payload = {"state": "canceling"}

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.patch(
                    self._get_api_url(f"pipelines/{pipeline_id}/runs/{run_id}"),
                    json=payload,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        logger.info(f"Pipeline run cancelled: {run_id}")

                    return ConnectorResult(
                        success=success,
                        status_code=response.status,
                        data=data,
                        request_id=str(run_id),
                        latency_ms=latency_ms,
                        error=None if success else data.get("message", str(data)),
                    )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def list_pipelines(
        self,
        top: int = 100,
        continuation_token: str | None = None,
    ) -> ConnectorResult:
        """
        List pipelines in the project.

        Args:
            top: Maximum number to return
            continuation_token: Pagination token
        """
        start_time = time.time()

        url = self._get_api_url("pipelines")
        url += f"&$top={top}"
        if continuation_token:
            url += f"&continuationToken={continuation_token}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self._get_headers()) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        pipelines = [
                            {
                                "id": p.get("id"),
                                "name": p.get("name"),
                                "folder": p.get("folder"),
                                "revision": p.get("revision"),
                            }
                            for p in data.get("value", [])
                        ]
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "pipelines": pipelines,
                                "count": len(pipelines),
                            },
                            latency_ms=latency_ms,
                        )
                    else:
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=data.get("message", str(data)),
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    # =========================================================================
    # Work Item Management
    # =========================================================================

    @require_enterprise_mode
    async def create_work_item(
        self,
        title: str,
        work_item_type: WorkItemType = WorkItemType.TASK,
        description: str = "",
        assigned_to: str | None = None,
        area_path: str | None = None,
        iteration_path: str | None = None,
        priority: WorkItemPriority | None = None,
        severity: WorkItemSeverity | None = None,
        tags: list[str] | None = None,
        parent_id: int | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        """
        Create a work item.

        Args:
            title: Work item title
            work_item_type: Type (Bug, Task, User Story, etc.)
            description: Detailed description (HTML supported)
            assigned_to: Assigned user email or display name
            area_path: Area path
            iteration_path: Iteration path (sprint)
            priority: Priority level
            severity: Severity level (for bugs)
            tags: Tags to apply
            parent_id: Parent work item ID for linking
            additional_fields: Additional fields
        """
        start_time = time.time()

        # Build JSON Patch document
        operations: list[dict[str, Any]] = [
            {
                "op": "add",
                "path": "/fields/System.Title",
                "value": title,
            }
        ]

        if description:
            operations.append(
                {
                    "op": "add",
                    "path": "/fields/System.Description",
                    "value": description,
                }
            )

        if assigned_to:
            operations.append(
                {
                    "op": "add",
                    "path": "/fields/System.AssignedTo",
                    "value": assigned_to,
                }
            )

        if area_path:
            operations.append(
                {
                    "op": "add",
                    "path": "/fields/System.AreaPath",
                    "value": area_path,
                }
            )

        if iteration_path:
            operations.append(
                {
                    "op": "add",
                    "path": "/fields/System.IterationPath",
                    "value": iteration_path,
                }
            )

        if priority:
            operations.append(
                {
                    "op": "add",
                    "path": "/fields/Microsoft.VSTS.Common.Priority",
                    "value": priority.value,
                }
            )

        if severity and work_item_type == WorkItemType.BUG:
            operations.append(
                {
                    "op": "add",
                    "path": "/fields/Microsoft.VSTS.Common.Severity",
                    "value": severity.value,
                }
            )

        if tags:
            operations.append(
                {
                    "op": "add",
                    "path": "/fields/System.Tags",
                    "value": "; ".join(tags),
                }
            )

        if parent_id:
            operations.append(
                {
                    "op": "add",
                    "path": "/relations/-",
                    "value": {
                        "rel": "System.LinkTypes.Hierarchy-Reverse",
                        "url": f"{self.base_url}/_apis/wit/workItems/{parent_id}",
                    },
                }
            )

        if additional_fields:
            for field_path, value in additional_fields.items():
                if not field_path.startswith("/fields/"):
                    field_path = f"/fields/{field_path}"
                operations.append(
                    {
                        "op": "add",
                        "path": field_path,
                        "value": value,
                    }
                )

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    self._get_api_url(f"wit/workitems/${work_item_type.value}"),
                    json=operations,
                    headers=self._get_headers("application/json-patch+json"),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    if response.status in (200, 201):
                        self._status = ConnectorStatus.CONNECTED
                        self._record_request(latency_ms, True)
                        work_item_id = data.get("id")
                        logger.info(f"Azure DevOps work item created: {work_item_id}")
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "id": work_item_id,
                                "type": work_item_type.value,
                                "title": title,
                                "url": data.get("_links", {})
                                .get("html", {})
                                .get("href"),
                            },
                            request_id=str(work_item_id),
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        error_msg = data.get("message", str(data))
                        self._last_error = error_msg
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error_msg,
                            data=data,
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            logger.exception(f"Azure DevOps connector error: {e}")
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def create_security_bug(
        self,
        title: str,
        cve_id: str | None = None,
        severity: str = "HIGH",
        affected_file: str | None = None,
        description: str = "",
        recommendation: str | None = None,
        approval_url: str | None = None,
        area_path: str | None = None,
    ) -> ConnectorResult:
        """
        Create a security bug with standard formatting.

        Args:
            title: Bug title
            cve_id: CVE identifier
            severity: CRITICAL, HIGH, MEDIUM, LOW
            affected_file: Affected file path
            description: Detailed description
            recommendation: Recommended action
            approval_url: HITL approval URL
            area_path: Area path for the bug
        """
        severity_map = {
            "CRITICAL": WorkItemSeverity.CRITICAL,
            "HIGH": WorkItemSeverity.HIGH,
            "MEDIUM": WorkItemSeverity.MEDIUM,
            "LOW": WorkItemSeverity.LOW,
        }

        priority_map = {
            "CRITICAL": WorkItemPriority.P1,
            "HIGH": WorkItemPriority.P1,
            "MEDIUM": WorkItemPriority.P2,
            "LOW": WorkItemPriority.P3,
        }

        html_description = f"""
<h2>Security Vulnerability</h2>
<table>
<tr><td><strong>CVE:</strong></td><td>{cve_id or 'N/A'}</td></tr>
<tr><td><strong>Severity:</strong></td><td>{severity}</td></tr>
<tr><td><strong>Affected File:</strong></td><td><code>{affected_file or 'N/A'}</code></td></tr>
</table>

<h3>Description</h3>
<p>{description}</p>

<h3>Recommendation</h3>
<p>{recommendation or 'Review and apply the auto-generated patch.'}</p>

<h3>Source</h3>
<p>Detected by: <strong>Aura Security Platform</strong> (Automated Detection)<br/>
Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
"""

        if approval_url:
            html_description += f"""
<h3>HITL Approval</h3>
<p><a href="{approval_url}">Review and Approve in Aura Dashboard</a></p>
"""

        result: ConnectorResult = await self.create_work_item(
            title=f"[{severity}] Security: {title}",
            work_item_type=WorkItemType.BUG,
            description=html_description,
            severity=severity_map.get(severity.upper()),
            priority=priority_map.get(severity.upper()),
            tags=["security", "aura-generated", severity.lower()],
            area_path=area_path,
            additional_fields={
                "Microsoft.VSTS.TCM.ReproSteps": html_description,
            },
        )
        return result

    @require_enterprise_mode
    async def get_work_item(
        self, work_item_id: int, expand: str = "all"
    ) -> ConnectorResult:
        """
        Get a work item by ID.

        Args:
            work_item_id: Work item ID
            expand: Fields to expand (none, relations, fields, links, all)
        """
        start_time = time.time()

        url = self._get_api_url(f"wit/workitems/{work_item_id}")
        url += f"&$expand={expand}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self._get_headers()) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        fields = data.get("fields", {})
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "id": data.get("id"),
                                "rev": data.get("rev"),
                                "type": fields.get("System.WorkItemType"),
                                "title": fields.get("System.Title"),
                                "state": fields.get("System.State"),
                                "assigned_to": fields.get("System.AssignedTo", {}).get(
                                    "displayName"
                                ),
                                "created_date": fields.get("System.CreatedDate"),
                                "changed_date": fields.get("System.ChangedDate"),
                                "area_path": fields.get("System.AreaPath"),
                                "iteration_path": fields.get("System.IterationPath"),
                                "url": data.get("_links", {})
                                .get("html", {})
                                .get("href"),
                            },
                            request_id=str(work_item_id),
                            latency_ms=latency_ms,
                        )
                    else:
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=data.get("message", str(data)),
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def update_work_item(
        self,
        work_item_id: int,
        updates: dict[str, Any],
    ) -> ConnectorResult:
        """
        Update a work item.

        Args:
            work_item_id: Work item ID
            updates: Field updates (field_name: value)
        """
        start_time = time.time()

        operations = []
        for field_name, value in updates.items():
            if not field_name.startswith("/fields/"):
                field_name = f"/fields/{field_name}"
            operations.append(
                {
                    "op": "replace",
                    "path": field_name,
                    "value": value,
                }
            )

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.patch(
                    self._get_api_url(f"wit/workitems/{work_item_id}"),
                    json=operations,
                    headers=self._get_headers("application/json-patch+json"),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        logger.info(f"Work item updated: {work_item_id}")

                    return ConnectorResult(
                        success=success,
                        status_code=response.status,
                        data=data if success else {},
                        request_id=str(work_item_id),
                        latency_ms=latency_ms,
                        error=None if success else data.get("message", str(data)),
                    )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def add_work_item_comment(
        self, work_item_id: int, comment: str
    ) -> ConnectorResult:
        """
        Add a comment to a work item.

        Args:
            work_item_id: Work item ID
            comment: Comment text
        """
        start_time = time.time()

        payload = {"text": comment}

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    self._get_api_url(f"wit/workItems/{work_item_id}/comments"),
                    json=payload,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status in (200, 201)
                    self._record_request(latency_ms, success)

                    return ConnectorResult(
                        success=success,
                        status_code=response.status,
                        data=data if success else {},
                        request_id=str(work_item_id),
                        latency_ms=latency_ms,
                        error=None if success else data.get("message", str(data)),
                    )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def query_work_items(
        self,
        wiql: str,
        top: int = 200,
    ) -> ConnectorResult:
        """
        Query work items using WIQL.

        Args:
            wiql: Work Item Query Language query
            top: Maximum results
        """
        start_time = time.time()

        payload = {"query": wiql}

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # First, execute the query
                async with session.post(
                    self._get_api_url("wit/wiql"),
                    json=payload,
                    headers=self._get_headers(),
                ) as response:
                    query_latency = time.time() - start_time
                    data = await response.json()

                    if response.status != 200:
                        self._record_request(query_latency * 1000, False)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=data.get("message", str(data)),
                            latency_ms=query_latency * 1000,
                        )

                    work_items = data.get("workItems", [])[:top]

                    if not work_items:
                        self._record_request(query_latency * 1000, True)
                        return ConnectorResult(
                            success=True,
                            status_code=200,
                            data={"work_items": [], "count": 0},
                            latency_ms=query_latency * 1000,
                        )

                    # Get work item details
                    ids = ",".join(str(wi.get("id")) for wi in work_items)
                    async with session.get(
                        self._get_api_url("wit/workitems")
                        + f"&ids={ids}&fields=System.Id,System.Title,System.State,System.WorkItemType",
                        headers=self._get_headers(),
                    ) as details_response:
                        latency_ms = (time.time() - start_time) * 1000
                        details_data = await details_response.json()

                        self._record_request(latency_ms, True)

                        items = [
                            {
                                "id": wi.get("id"),
                                "title": wi.get("fields", {}).get("System.Title"),
                                "state": wi.get("fields", {}).get("System.State"),
                                "type": wi.get("fields", {}).get("System.WorkItemType"),
                            }
                            for wi in details_data.get("value", [])
                        ]

                        return ConnectorResult(
                            success=True,
                            status_code=200,
                            data={"work_items": items, "count": len(items)},
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> bool:
        """Check if Azure DevOps connector is healthy."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    self._get_api_url("projects"),
                    headers=self._get_headers(),
                ) as response:
                    if response.status == 200:
                        self._status = ConnectorStatus.CONNECTED
                        return True
                    elif response.status == 401:
                        self._status = ConnectorStatus.AUTH_FAILED
                        self._last_error = "Authentication failed"
                    elif response.status == 404:
                        self._status = ConnectorStatus.ERROR
                        self._last_error = "Project not found"
                    else:
                        self._status = ConnectorStatus.ERROR
                        self._last_error = f"HTTP {response.status}"
                    return False
        except Exception as e:
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            return False
