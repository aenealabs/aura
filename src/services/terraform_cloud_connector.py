"""
Project Aura - Terraform Cloud Connector

Implements ADR-028 Phase 8: Enterprise Connector Expansion

Terraform Cloud/Enterprise REST API connector for:
- Workspace management
- Run triggers and management
- State inspection
- Variable management

SECURITY: Only available in ENTERPRISE or HYBRID mode.

Usage:
    >>> from src.services.terraform_cloud_connector import TerraformCloudConnector
    >>> tfc = TerraformCloudConnector(
    ...     organization="my-org",
    ...     token="team-or-user-token"
    ... )
    >>> await tfc.trigger_run(workspace_id="ws-xxx", message="Security patch deployment")
"""

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


class TerraformRunStatus(Enum):
    """Terraform Cloud run statuses."""

    PENDING = "pending"
    PLAN_QUEUED = "plan_queued"
    PLANNING = "planning"
    PLANNED = "planned"
    COST_ESTIMATING = "cost_estimating"
    COST_ESTIMATED = "cost_estimated"
    POLICY_CHECKING = "policy_checking"
    POLICY_OVERRIDE = "policy_override"
    POLICY_CHECKED = "policy_checked"
    CONFIRMED = "confirmed"
    APPLY_QUEUED = "apply_queued"
    APPLYING = "applying"
    APPLIED = "applied"
    DISCARDED = "discarded"
    ERRORED = "errored"
    CANCELED = "canceled"
    FORCE_CANCELED = "force_canceled"


class TerraformRunSource(Enum):
    """Terraform Cloud run sources."""

    API = "tfe-api"
    UI = "tfe-ui"
    VCS = "tfe-vcs"
    CONFIGURATION_VERSION = "tfe-configuration-version"


class VariableCategory(Enum):
    """Terraform variable categories."""

    TERRAFORM = "terraform"  # Terraform variables
    ENV = "env"  # Environment variables


@dataclass
class TerraformWorkspace:
    """Terraform Cloud workspace details."""

    id: str
    name: str
    organization: str
    auto_apply: bool = False
    terraform_version: str | None = None
    working_directory: str | None = None
    vcs_repo: str | None = None
    description: str = ""
    tags: list[str] = field(default_factory=list)
    resource_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class TerraformRun:
    """Terraform Cloud run details."""

    id: str
    status: TerraformRunStatus
    source: TerraformRunSource | None = None
    message: str = ""
    is_destroy: bool = False
    has_changes: bool = False
    auto_apply: bool = False
    plan_only: bool = False
    created_at: str | None = None
    plan_id: str | None = None
    apply_id: str | None = None
    cost_estimate_id: str | None = None


@dataclass
class TerraformVariable:
    """Terraform Cloud variable."""

    key: str
    value: str | None = None
    category: VariableCategory = VariableCategory.TERRAFORM
    hcl: bool = False
    sensitive: bool = False
    description: str = ""


# =============================================================================
# Terraform Cloud Connector
# =============================================================================


class TerraformCloudConnector(ExternalToolConnector):
    """
    Terraform Cloud/Enterprise connector for IaC integration.

    Supports:
    - Workspace management
    - Run triggers and monitoring
    - State file inspection
    - Variable management
    """

    DEFAULT_API_URL = "https://app.terraform.io/api/v2"

    def __init__(
        self,
        organization: str,
        token: str,
        api_url: str | None = None,
        timeout_seconds: float = 60.0,
    ):
        """
        Initialize Terraform Cloud connector.

        Args:
            organization: Terraform Cloud organization name
            token: API token (team or user token)
            api_url: API URL (default: https://app.terraform.io/api/v2)
            timeout_seconds: Request timeout
        """
        super().__init__("terraform_cloud", timeout_seconds)

        self.organization = organization
        self.api_url = (api_url or self.DEFAULT_API_URL).rstrip("/")
        self._token = token

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json",
        }

    # =========================================================================
    # Workspace Management
    # =========================================================================

    @require_enterprise_mode
    async def list_workspaces(
        self,
        search: str | None = None,
        tags: list[str] | None = None,
        page_size: int = 100,
    ) -> ConnectorResult:
        """
        List workspaces in the organization.

        Args:
            search: Search by workspace name
            tags: Filter by tags
            page_size: Results per page
        """
        start_time = time.time()

        params = [f"page[size]={page_size}"]
        if search:
            params.append(f"search[name]={search}")
        if tags:
            params.append(f"search[tags]={','.join(tags)}")

        url = f"{self.api_url}/organizations/{self.organization}/workspaces?{'&'.join(params)}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self._get_headers()) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        workspaces = [
                            {
                                "id": ws.get("id"),
                                "name": ws.get("attributes", {}).get("name"),
                                "auto_apply": ws.get("attributes", {}).get(
                                    "auto-apply"
                                ),
                                "terraform_version": ws.get("attributes", {}).get(
                                    "terraform-version"
                                ),
                                "resource_count": ws.get("attributes", {}).get(
                                    "resource-count", 0
                                ),
                                "updated_at": ws.get("attributes", {}).get(
                                    "updated-at"
                                ),
                            }
                            for ws in data.get("data", [])
                        ]
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "workspaces": workspaces,
                                "count": len(workspaces),
                            },
                            latency_ms=latency_ms,
                        )
                    else:
                        errors = data.get("errors", [])
                        error_msg = errors[0].get("detail") if errors else str(data)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error_msg,
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
    async def get_workspace(self, workspace_name: str) -> ConnectorResult:
        """
        Get workspace details by name.

        Args:
            workspace_name: Workspace name
        """
        start_time = time.time()

        url = f"{self.api_url}/organizations/{self.organization}/workspaces/{workspace_name}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self._get_headers()) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        ws_data = data.get("data", {})
                        attrs = ws_data.get("attributes", {})
                        workspace = TerraformWorkspace(
                            id=ws_data.get("id"),
                            name=attrs.get("name"),
                            organization=self.organization,
                            auto_apply=attrs.get("auto-apply", False),
                            terraform_version=attrs.get("terraform-version"),
                            working_directory=attrs.get("working-directory"),
                            description=attrs.get("description", ""),
                            resource_count=attrs.get("resource-count", 0),
                            created_at=attrs.get("created-at"),
                            updated_at=attrs.get("updated-at"),
                        )
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "id": workspace.id,
                                "name": workspace.name,
                                "auto_apply": workspace.auto_apply,
                                "terraform_version": workspace.terraform_version,
                                "resource_count": workspace.resource_count,
                                "description": workspace.description,
                            },
                            request_id=workspace.id,
                            latency_ms=latency_ms,
                        )
                    else:
                        errors = data.get("errors", [])
                        error_msg = errors[0].get("detail") if errors else str(data)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error_msg,
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
    # Run Management
    # =========================================================================

    @require_enterprise_mode
    async def trigger_run(
        self,
        workspace_id: str,
        message: str = "Triggered via API",
        is_destroy: bool = False,
        auto_apply: bool | None = None,
        plan_only: bool = False,
        target_addrs: list[str] | None = None,
        replace_addrs: list[str] | None = None,
        variables: list[TerraformVariable] | None = None,
    ) -> ConnectorResult:
        """
        Trigger a new run for a workspace.

        Args:
            workspace_id: Workspace ID (ws-xxx)
            message: Run message/reason
            is_destroy: Whether this is a destroy run
            auto_apply: Override workspace auto-apply setting
            plan_only: Only plan, don't apply
            target_addrs: Target specific resources
            replace_addrs: Force replace specific resources
            variables: Run-specific variables
        """
        start_time = time.time()

        payload: dict[str, Any] = {
            "data": {
                "type": "runs",
                "attributes": {
                    "message": message,
                    "is-destroy": is_destroy,
                    "plan-only": plan_only,
                },
                "relationships": {
                    "workspace": {
                        "data": {
                            "type": "workspaces",
                            "id": workspace_id,
                        }
                    }
                },
            }
        }

        if auto_apply is not None:
            payload["data"]["attributes"]["auto-apply"] = auto_apply
        if target_addrs:
            payload["data"]["attributes"]["target-addrs"] = target_addrs
        if replace_addrs:
            payload["data"]["attributes"]["replace-addrs"] = replace_addrs
        if variables:
            payload["data"]["attributes"]["variables"] = [
                {
                    "key": v.key,
                    "value": v.value,
                    "category": v.category.value,
                    "hcl": v.hcl,
                    "sensitive": v.sensitive,
                }
                for v in variables
            ]

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.api_url}/runs",
                    json=payload,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    if response.status in (200, 201):
                        self._status = ConnectorStatus.CONNECTED
                        self._record_request(latency_ms, True)
                        run_data = data.get("data", {})
                        run_id = run_data.get("id")
                        logger.info(f"Terraform run triggered: {run_id}")
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "run_id": run_id,
                                "status": run_data.get("attributes", {}).get("status"),
                                "message": message,
                                "is_destroy": is_destroy,
                            },
                            request_id=run_id,
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        errors = data.get("errors", [])
                        error_msg = errors[0].get("detail") if errors else str(data)
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
            logger.exception(f"Terraform Cloud connector error: {e}")
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def trigger_security_patch_run(
        self,
        workspace_name: str,
        cve_id: str | None = None,
        severity: str = "HIGH",
        description: str = "",
        approval_url: str | None = None,
    ) -> ConnectorResult:
        """
        Trigger a security patch run with standard formatting.

        Args:
            workspace_name: Workspace name
            cve_id: CVE identifier
            severity: CRITICAL, HIGH, MEDIUM, LOW
            description: Patch description
            approval_url: HITL approval URL
        """
        # First get the workspace ID
        ws_result: ConnectorResult = await self.get_workspace(workspace_name)
        if not ws_result.success:
            return ws_result

        workspace_id = ws_result.data.get("id") if ws_result.data else None
        if not workspace_id:
            return ConnectorResult(
                success=False,
                error=f"Workspace ID not found for workspace: {workspace_name}",
            )

        message = f"[{severity}] Security Patch"
        if cve_id:
            message += f" - {cve_id}"
        message += f"\n\n{description}"
        if approval_url:
            message += f"\n\nHITL Approval: {approval_url}"
        message += "\n\nTriggered by: Aura Security Platform"
        message += f"\nTimestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"

        result: ConnectorResult = await self.trigger_run(
            workspace_id=workspace_id,
            message=message,
            auto_apply=False,  # Require manual approval for security patches
            plan_only=True,  # Plan first, apply after review
        )
        return result

    @require_enterprise_mode
    async def get_run(self, run_id: str) -> ConnectorResult:
        """
        Get run details.

        Args:
            run_id: Run ID (run-xxx)
        """
        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.api_url}/runs/{run_id}",
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        run_data = data.get("data", {})
                        attrs = run_data.get("attributes", {})
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "id": run_data.get("id"),
                                "status": attrs.get("status"),
                                "message": attrs.get("message"),
                                "is_destroy": attrs.get("is-destroy"),
                                "has_changes": attrs.get("has-changes"),
                                "auto_apply": attrs.get("auto-apply"),
                                "created_at": attrs.get("created-at"),
                                "plan_only": attrs.get("plan-only"),
                            },
                            request_id=run_id,
                            latency_ms=latency_ms,
                        )
                    else:
                        errors = data.get("errors", [])
                        error_msg = errors[0].get("detail") if errors else str(data)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error_msg,
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
    async def apply_run(self, run_id: str, comment: str = "") -> ConnectorResult:
        """
        Apply a planned run.

        Args:
            run_id: Run ID (run-xxx)
            comment: Optional comment
        """
        start_time = time.time()

        payload = {}
        if comment:
            payload["comment"] = comment

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.api_url}/runs/{run_id}/actions/apply",
                    json=payload if payload else None,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000

                    success = response.status in (200, 202)
                    self._record_request(latency_ms, success)

                    if success:
                        logger.info(f"Terraform run applied: {run_id}")
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={"run_id": run_id, "action": "apply"},
                            request_id=run_id,
                            latency_ms=latency_ms,
                        )
                    else:
                        data = await response.json()
                        errors = data.get("errors", [])
                        error_msg = errors[0].get("detail") if errors else str(data)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error_msg,
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
    async def cancel_run(self, run_id: str, comment: str = "") -> ConnectorResult:
        """
        Cancel a run.

        Args:
            run_id: Run ID (run-xxx)
            comment: Optional comment
        """
        start_time = time.time()

        payload = {}
        if comment:
            payload["comment"] = comment

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.api_url}/runs/{run_id}/actions/cancel",
                    json=payload if payload else None,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000

                    success = response.status in (200, 202)
                    self._record_request(latency_ms, success)

                    if success:
                        logger.info(f"Terraform run cancelled: {run_id}")

                    return ConnectorResult(
                        success=success,
                        status_code=response.status,
                        data={"run_id": run_id, "action": "cancel"},
                        request_id=run_id,
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
    async def list_runs(
        self,
        workspace_id: str,
        status: TerraformRunStatus | None = None,
        page_size: int = 20,
    ) -> ConnectorResult:
        """
        List runs for a workspace.

        Args:
            workspace_id: Workspace ID
            status: Filter by status
            page_size: Results per page
        """
        start_time = time.time()

        params = [f"page[size]={page_size}"]
        if status:
            params.append(f"filter[status]={status.value}")

        url = f"{self.api_url}/workspaces/{workspace_id}/runs?{'&'.join(params)}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self._get_headers()) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        runs = [
                            {
                                "id": r.get("id"),
                                "status": r.get("attributes", {}).get("status"),
                                "message": r.get("attributes", {}).get("message"),
                                "created_at": r.get("attributes", {}).get("created-at"),
                                "has_changes": r.get("attributes", {}).get(
                                    "has-changes"
                                ),
                            }
                            for r in data.get("data", [])
                        ]
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={"runs": runs, "count": len(runs)},
                            latency_ms=latency_ms,
                        )
                    else:
                        errors = data.get("errors", [])
                        error_msg = errors[0].get("detail") if errors else str(data)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error_msg,
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
    # State Management
    # =========================================================================

    @require_enterprise_mode
    async def get_current_state(self, workspace_id: str) -> ConnectorResult:
        """
        Get the current state version for a workspace.

        Args:
            workspace_id: Workspace ID
        """
        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.api_url}/workspaces/{workspace_id}/current-state-version",
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        sv_data = data.get("data", {})
                        attrs = sv_data.get("attributes", {})
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "id": sv_data.get("id"),
                                "serial": attrs.get("serial"),
                                "terraform_version": attrs.get("terraform-version"),
                                "resource_count": attrs.get("resource-count"),
                                "created_at": attrs.get("created-at"),
                                "hosted_state_download_url": attrs.get(
                                    "hosted-state-download-url"
                                ),
                            },
                            latency_ms=latency_ms,
                        )
                    else:
                        errors = data.get("errors", [])
                        error_msg = errors[0].get("detail") if errors else str(data)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error_msg,
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
    async def get_state_outputs(self, workspace_id: str) -> ConnectorResult:
        """
        Get state outputs for a workspace.

        Args:
            workspace_id: Workspace ID
        """
        # First get the current state version
        state_result: ConnectorResult = await self.get_current_state(workspace_id)
        if not state_result.success:
            return state_result

        state_version_id = state_result.data.get("id") if state_result.data else None
        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.api_url}/state-versions/{state_version_id}/outputs",
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        outputs = {
                            o.get("attributes", {}).get("name"): {
                                "value": o.get("attributes", {}).get("value"),
                                "type": o.get("attributes", {}).get("type"),
                                "sensitive": o.get("attributes", {}).get("sensitive"),
                            }
                            for o in data.get("data", [])
                        }
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={"outputs": outputs},
                            latency_ms=latency_ms,
                        )
                    else:
                        errors = data.get("errors", [])
                        error_msg = errors[0].get("detail") if errors else str(data)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error_msg,
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
    # Variable Management
    # =========================================================================

    @require_enterprise_mode
    async def list_variables(self, workspace_id: str) -> ConnectorResult:
        """
        List variables for a workspace.

        Args:
            workspace_id: Workspace ID
        """
        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.api_url}/workspaces/{workspace_id}/vars",
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        variables = [
                            {
                                "id": v.get("id"),
                                "key": v.get("attributes", {}).get("key"),
                                "value": v.get("attributes", {}).get("value"),
                                "category": v.get("attributes", {}).get("category"),
                                "sensitive": v.get("attributes", {}).get("sensitive"),
                                "hcl": v.get("attributes", {}).get("hcl"),
                            }
                            for v in data.get("data", [])
                        ]
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={"variables": variables, "count": len(variables)},
                            latency_ms=latency_ms,
                        )
                    else:
                        errors = data.get("errors", [])
                        error_msg = errors[0].get("detail") if errors else str(data)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error_msg,
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
    async def create_variable(
        self,
        workspace_id: str,
        key: str,
        value: str,
        category: VariableCategory = VariableCategory.TERRAFORM,
        hcl: bool = False,
        sensitive: bool = False,
        description: str = "",
    ) -> ConnectorResult:
        """
        Create a workspace variable.

        Args:
            workspace_id: Workspace ID
            key: Variable name
            value: Variable value
            category: terraform or env
            hcl: Whether value is HCL
            sensitive: Whether value is sensitive
            description: Variable description
        """
        start_time = time.time()

        payload = {
            "data": {
                "type": "vars",
                "attributes": {
                    "key": key,
                    "value": value,
                    "category": category.value,
                    "hcl": hcl,
                    "sensitive": sensitive,
                    "description": description,
                },
                "relationships": {
                    "workspace": {
                        "data": {
                            "type": "workspaces",
                            "id": workspace_id,
                        }
                    }
                },
            }
        }

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.api_url}/vars",
                    json=payload,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status in (200, 201)
                    self._record_request(latency_ms, success)

                    if success:
                        var_data = data.get("data", {})
                        logger.info(f"Terraform variable created: {key}")
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "id": var_data.get("id"),
                                "key": key,
                                "category": category.value,
                            },
                            request_id=var_data.get("id"),
                            latency_ms=latency_ms,
                        )
                    else:
                        errors = data.get("errors", [])
                        error_msg = errors[0].get("detail") if errors else str(data)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error_msg,
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
        """Check if Terraform Cloud connector is healthy."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.api_url}/organizations/{self.organization}",
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
                        self._last_error = "Organization not found"
                    else:
                        self._status = ConnectorStatus.ERROR
                        self._last_error = f"HTTP {response.status}"
                    return False
        except Exception as e:
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            return False
