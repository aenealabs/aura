"""
Project Aura - Diagram Git Sync Service (ADR-060 Phase 4)

Commits diagrams to GitHub/GitLab repositories with GovCloud compliance.
Supports direct commits and pull request creation.

Features:
- GitHub API integration via OAuth or GitHub App authentication
- GitLab API integration via OAuth
- GovCloud-compliant Git host allowlisting via SSM
- Direct commit and pull request workflows
- Multi-format diagram file commits (SVG, PNG, draw.io)
"""

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlparse

import boto3
import requests
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class GitProvider(Enum):
    """Supported Git providers."""

    GITHUB = "github"
    GITLAB = "gitlab"


class CommitStatus(Enum):
    """Status of a diagram commit operation."""

    SUCCESS = "success"
    PENDING = "pending"
    FAILED = "failed"
    UNAUTHORIZED = "unauthorized"
    HOST_NOT_ALLOWED = "host_not_allowed"


@dataclass
class DiagramCommitRequest:
    """Request to commit a diagram to a repository."""

    repo_owner: str
    repo_name: str
    file_path: str
    diagram_content: str
    content_type: str  # svg, png (base64), drawio
    commit_message: str
    branch: str = "main"
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    create_pr: bool = False
    pr_title: Optional[str] = None
    pr_description: Optional[str] = None
    pr_base_branch: Optional[str] = None


@dataclass
class DiagramCommitResult:
    """Result of a diagram commit operation."""

    success: bool
    status: CommitStatus
    commit_sha: Optional[str] = None
    commit_url: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    file_url: Optional[str] = None
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class GitHostConfig:
    """Configuration for a Git host."""

    host: str
    api_base_url: str
    provider: GitProvider
    enterprise: bool = False


class DiagramGitSync:
    """
    Git synchronization service for diagrams.

    Handles committing diagrams to GitHub/GitLab repositories with:
    - OAuth token-based authentication
    - GitHub App authentication support
    - GovCloud-compliant Git host restrictions
    - Direct commits and pull request creation
    """

    # Default API endpoints
    GITHUB_API_BASE = "https://api.github.com"
    GITLAB_API_BASE = "https://gitlab.com/api/v4"

    # SSM parameter paths
    SSM_ALLOWED_HOSTS = "/aura/{environment}/git/allowed-hosts"
    SSM_ENTERPRISE_HOSTS = "/aura/{environment}/git/enterprise-hosts"

    def __init__(
        self,
        oauth_service: Any = None,
        github_app_auth: Any = None,
        ssm_client: Any = None,
        environment: str | None = None,
        govcloud_mode: bool = False,
    ):
        """
        Initialize the Git sync service.

        Args:
            oauth_service: OAuthProviderService for token management
            github_app_auth: GitHubAppAuth for app-based authentication
            ssm_client: Boto3 SSM client
            environment: Deployment environment (dev, qa, prod)
            govcloud_mode: Enable GovCloud Git host restrictions
        """
        self.environment = environment or os.getenv("ENVIRONMENT", "dev")
        self.govcloud_mode = (
            govcloud_mode or os.getenv("GOVCLOUD_MODE", "").lower() == "true"
        )

        # Lazy-load services
        self._oauth_service = oauth_service
        self._github_app_auth = github_app_auth
        self._ssm_client = ssm_client

        # GovCloud host configuration
        self._allowed_git_hosts: set[str] | None = None
        self._enterprise_hosts: dict[str, GitHostConfig] = {}

        if self.govcloud_mode:
            self._load_allowed_hosts()

    @property
    def ssm_client(self):
        """Lazy SSM client initialization."""
        if self._ssm_client is None:
            self._ssm_client = boto3.client("ssm")
        return self._ssm_client

    @property
    def oauth_service(self):
        """Lazy OAuth service initialization."""
        if self._oauth_service is None:
            from src.services.oauth_provider_service import get_oauth_service

            self._oauth_service = get_oauth_service()
        return self._oauth_service

    @property
    def github_app_auth(self):
        """Lazy GitHub App auth initialization."""
        if self._github_app_auth is None:
            from src.services.github_app_auth import get_github_app_auth

            self._github_app_auth = get_github_app_auth()
        return self._github_app_auth

    def _load_allowed_hosts(self) -> None:
        """Load allowed Git hosts for GovCloud from SSM."""
        try:
            param_name = self.SSM_ALLOWED_HOSTS.format(environment=self.environment)
            response = self.ssm_client.get_parameter(Name=param_name)
            hosts_value = response["Parameter"]["Value"]
            self._allowed_git_hosts = {
                h.strip() for h in hosts_value.split(",") if h.strip()
            }
            logger.info(
                f"Loaded {len(self._allowed_git_hosts)} allowed Git hosts for GovCloud"
            )

            # Load enterprise host configurations
            self._load_enterprise_hosts()

        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                logger.warning(
                    f"GovCloud Git hosts parameter not found: {param_name}. "
                    "Using default GitHub/GitLab."
                )
                self._allowed_git_hosts = {"github.com", "gitlab.com"}
            else:
                logger.error(f"Failed to load allowed Git hosts: {e}")
                raise

    def _load_enterprise_hosts(self) -> None:
        """Load enterprise Git host configurations from SSM."""
        try:
            param_name = self.SSM_ENTERPRISE_HOSTS.format(environment=self.environment)
            response = self.ssm_client.get_parameter(Name=param_name)
            hosts_config = json.loads(response["Parameter"]["Value"])

            for host, config in hosts_config.items():
                self._enterprise_hosts[host] = GitHostConfig(
                    host=host,
                    api_base_url=config["api_base_url"],
                    provider=GitProvider(config["provider"]),
                    enterprise=True,
                )
            logger.info(
                f"Loaded {len(self._enterprise_hosts)} enterprise Git host configs"
            )

        except ClientError as e:
            if e.response["Error"]["Code"] != "ParameterNotFound":
                logger.error(f"Failed to load enterprise host configs: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid enterprise hosts JSON: {e}")

    def _extract_host(
        self, repo_owner: str, repo_name: str, clone_url: str | None = None
    ) -> str:
        """Extract the Git host from repository info."""
        if clone_url:
            parsed = urlparse(clone_url)
            return parsed.netloc

        # Default to github.com for owner/repo format
        return "github.com"

    def _validate_host(self, host: str) -> tuple[bool, str | None]:
        """
        Validate that a Git host is allowed in GovCloud mode.

        Returns:
            Tuple of (is_allowed, error_message)
        """
        if not self.govcloud_mode:
            return True, None

        if self._allowed_git_hosts is None:
            self._load_allowed_hosts()

        if host not in (self._allowed_git_hosts or set()):
            return False, f"Git host '{host}' not authorized in GovCloud mode"

        return True, None

    def _get_host_config(self, host: str) -> GitHostConfig:
        """Get configuration for a Git host."""
        # Check enterprise hosts first
        if host in self._enterprise_hosts:
            return self._enterprise_hosts[host]

        # Default configurations
        if host == "github.com" or host.endswith(".github.com"):
            return GitHostConfig(
                host=host,
                api_base_url=self.GITHUB_API_BASE,
                provider=GitProvider.GITHUB,
            )
        elif host == "gitlab.com" or host.endswith(".gitlab.com"):
            return GitHostConfig(
                host=host,
                api_base_url=self.GITLAB_API_BASE,
                provider=GitProvider.GITLAB,
            )
        else:
            # Assume GitHub Enterprise for unknown hosts
            return GitHostConfig(
                host=host,
                api_base_url=f"https://{host}/api/v3",
                provider=GitProvider.GITHUB,
                enterprise=True,
            )

    async def commit_diagram(
        self,
        request: DiagramCommitRequest,
        connection_id: str | None = None,
        access_token: str | None = None,
        use_github_app: bool = False,
    ) -> DiagramCommitResult:
        """
        Commit a diagram to a repository.

        Args:
            request: Commit request details
            connection_id: OAuth connection ID (for token lookup)
            access_token: Direct access token (alternative to connection_id)
            use_github_app: Use GitHub App authentication

        Returns:
            DiagramCommitResult with commit status
        """
        # Determine host and validate for GovCloud
        host = self._extract_host(request.repo_owner, request.repo_name)
        is_allowed, error_msg = self._validate_host(host)

        if not is_allowed:
            return DiagramCommitResult(
                success=False,
                status=CommitStatus.HOST_NOT_ALLOWED,
                error=error_msg,
            )

        # Get authentication token
        token: str | None = None
        if access_token:
            token = access_token
        elif connection_id:
            try:
                token = await self.oauth_service.get_access_token(connection_id)
            except Exception as e:
                logger.error(f"Failed to get OAuth token: {e}")
                return DiagramCommitResult(
                    success=False,
                    status=CommitStatus.UNAUTHORIZED,
                    error=f"Failed to authenticate: {e}",
                )
        elif use_github_app:
            token = self.github_app_auth.get_installation_token()
            if not token:
                return DiagramCommitResult(
                    success=False,
                    status=CommitStatus.UNAUTHORIZED,
                    error="GitHub App authentication not configured",
                )
        else:
            return DiagramCommitResult(
                success=False,
                status=CommitStatus.UNAUTHORIZED,
                error="No authentication method provided",
            )

        # Get host configuration
        host_config = self._get_host_config(host)

        # Route to appropriate provider
        if host_config.provider == GitProvider.GITHUB:
            return await self._commit_to_github(request, token, host_config)
        else:
            return await self._commit_to_gitlab(request, token, host_config)

    async def _commit_to_github(
        self,
        request: DiagramCommitRequest,
        token: str,
        host_config: GitHostConfig,
    ) -> DiagramCommitResult:
        """Commit diagram to GitHub repository."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        base_url = host_config.api_base_url
        repo_path = f"{request.repo_owner}/{request.repo_name}"

        try:
            # Get the current file SHA if it exists (required for updates)
            existing_sha = await self._get_github_file_sha(
                base_url, repo_path, request.file_path, request.branch, headers
            )

            # Prepare content (base64 encode if not already)
            content = request.diagram_content
            if request.content_type == "png":
                # PNG should already be base64 encoded
                encoded_content = content
            else:
                # Text content needs encoding
                encoded_content = base64.b64encode(content.encode()).decode()

            # Create commit via Contents API
            commit_data: dict[str, Any] = {
                "message": request.commit_message,
                "content": encoded_content,
                "branch": request.branch,
            }

            if existing_sha:
                commit_data["sha"] = existing_sha

            if request.author_name and request.author_email:
                commit_data["committer"] = {
                    "name": request.author_name,
                    "email": request.author_email,
                }

            # If creating PR, first create a new branch
            working_branch = request.branch
            if request.create_pr:
                working_branch = await self._create_github_branch(
                    base_url, repo_path, request.branch, headers
                )
                commit_data["branch"] = working_branch

            # Create/update file
            url = f"{base_url}/repos/{repo_path}/contents/{request.file_path}"
            response = requests.put(url, json=commit_data, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()

            commit_sha = result["commit"]["sha"]
            file_url = result["content"]["html_url"]

            # Create PR if requested
            pr_number = None
            pr_url = None
            if request.create_pr:
                pr_result = await self._create_github_pr(
                    base_url,
                    repo_path,
                    working_branch,
                    request.pr_base_branch or request.branch,
                    request.pr_title or f"Add diagram: {request.file_path}",
                    request.pr_description
                    or "Automated diagram commit from Project Aura",
                    headers,
                )
                pr_number = pr_result.get("number")
                pr_url = pr_result.get("html_url")

            return DiagramCommitResult(
                success=True,
                status=CommitStatus.SUCCESS,
                commit_sha=commit_sha,
                commit_url=f"https://{host_config.host}/{repo_path}/commit/{commit_sha}",
                file_url=file_url,
                pr_number=pr_number,
                pr_url=pr_url,
            )

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 0
            if status_code == 401:
                return DiagramCommitResult(
                    success=False,
                    status=CommitStatus.UNAUTHORIZED,
                    error="Authentication failed - token may be expired or invalid",
                )
            elif status_code == 404:
                return DiagramCommitResult(
                    success=False,
                    status=CommitStatus.FAILED,
                    error=f"Repository or branch not found: {repo_path}",
                )
            else:
                logger.error(f"GitHub API error: {e}")
                return DiagramCommitResult(
                    success=False,
                    status=CommitStatus.FAILED,
                    error=f"GitHub API error: {e}",
                )

        except Exception as e:
            logger.error(f"Failed to commit to GitHub: {e}")
            return DiagramCommitResult(
                success=False,
                status=CommitStatus.FAILED,
                error=str(e),
            )

    async def _get_github_file_sha(
        self,
        base_url: str,
        repo_path: str,
        file_path: str,
        branch: str,
        headers: dict[str, str],
    ) -> str | None:
        """Get the SHA of an existing file in GitHub."""
        url = f"{base_url}/repos/{repo_path}/contents/{file_path}"
        try:
            response = requests.get(
                url, params={"ref": branch}, headers=headers, timeout=30
            )
            if response.status_code == 200:
                return response.json().get("sha")
            return None
        except Exception:
            return None

    async def _create_github_branch(
        self,
        base_url: str,
        repo_path: str,
        base_branch: str,
        headers: dict[str, str],
    ) -> str:
        """Create a new branch for PR workflow."""
        # Get base branch SHA
        url = f"{base_url}/repos/{repo_path}/git/refs/heads/{base_branch}"
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        base_sha = response.json()["object"]["sha"]

        # Generate unique branch name
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        branch_name = f"diagram-update-{timestamp}"

        # Create new branch
        url = f"{base_url}/repos/{repo_path}/git/refs"
        response = requests.post(
            url,
            json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()

        return branch_name

    async def _create_github_pr(
        self,
        base_url: str,
        repo_path: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Create a pull request on GitHub."""
        url = f"{base_url}/repos/{repo_path}/pulls"
        response = requests.post(
            url,
            json={
                "title": title,
                "body": body,
                "head": head_branch,
                "base": base_branch,
            },
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    async def _commit_to_gitlab(
        self,
        request: DiagramCommitRequest,
        token: str,
        host_config: GitHostConfig,
    ) -> DiagramCommitResult:
        """Commit diagram to GitLab repository."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        base_url = host_config.api_base_url

        # URL-encode project path
        project_path = requests.utils.quote(
            f"{request.repo_owner}/{request.repo_name}", safe=""
        )

        try:
            # Prepare content
            content = request.diagram_content
            if request.content_type == "png":
                # PNG needs to be raw base64
                encoding = "base64"
            else:
                encoding = "text"

            # Check if file exists
            file_exists = await self._gitlab_file_exists(
                base_url, project_path, request.file_path, request.branch, headers
            )

            # Determine action
            action = "update" if file_exists else "create"

            # Create commit via Commits API
            commit_data = {
                "branch": request.branch,
                "commit_message": request.commit_message,
                "actions": [
                    {
                        "action": action,
                        "file_path": request.file_path,
                        "content": content,
                        "encoding": encoding,
                    }
                ],
            }

            if request.author_name and request.author_email:
                commit_data["author_name"] = request.author_name
                commit_data["author_email"] = request.author_email

            # If creating MR, create a new branch first
            working_branch = request.branch
            if request.create_pr:
                working_branch = await self._create_gitlab_branch(
                    base_url, project_path, request.branch, headers
                )
                commit_data["branch"] = working_branch

            # Create commit
            url = f"{base_url}/projects/{project_path}/repository/commits"
            response = requests.post(url, json=commit_data, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()

            commit_sha = result["id"]
            commit_url = result["web_url"]

            # Get file URL
            file_url = f"https://{host_config.host}/{request.repo_owner}/{request.repo_name}/-/blob/{working_branch}/{request.file_path}"

            # Create merge request if requested
            mr_number = None
            mr_url = None
            if request.create_pr:
                mr_result = await self._create_gitlab_mr(
                    base_url,
                    project_path,
                    working_branch,
                    request.pr_base_branch or request.branch,
                    request.pr_title or f"Add diagram: {request.file_path}",
                    request.pr_description
                    or "Automated diagram commit from Project Aura",
                    headers,
                )
                mr_number = mr_result.get("iid")
                mr_url = mr_result.get("web_url")

            return DiagramCommitResult(
                success=True,
                status=CommitStatus.SUCCESS,
                commit_sha=commit_sha,
                commit_url=commit_url,
                file_url=file_url,
                pr_number=mr_number,
                pr_url=mr_url,
            )

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 0
            if status_code == 401:
                return DiagramCommitResult(
                    success=False,
                    status=CommitStatus.UNAUTHORIZED,
                    error="Authentication failed - token may be expired or invalid",
                )
            elif status_code == 404:
                return DiagramCommitResult(
                    success=False,
                    status=CommitStatus.FAILED,
                    error=f"Project or branch not found: {request.repo_owner}/{request.repo_name}",
                )
            else:
                logger.error(f"GitLab API error: {e}")
                return DiagramCommitResult(
                    success=False,
                    status=CommitStatus.FAILED,
                    error=f"GitLab API error: {e}",
                )

        except Exception as e:
            logger.error(f"Failed to commit to GitLab: {e}")
            return DiagramCommitResult(
                success=False,
                status=CommitStatus.FAILED,
                error=str(e),
            )

    async def _gitlab_file_exists(
        self,
        base_url: str,
        project_path: str,
        file_path: str,
        branch: str,
        headers: dict[str, str],
    ) -> bool:
        """Check if a file exists in GitLab."""
        encoded_file = requests.utils.quote(file_path, safe="")
        url = f"{base_url}/projects/{project_path}/repository/files/{encoded_file}"
        try:
            response = requests.head(
                url, params={"ref": branch}, headers=headers, timeout=30
            )
            return response.status_code == 200
        except Exception:
            return False

    async def _create_gitlab_branch(
        self,
        base_url: str,
        project_path: str,
        base_branch: str,
        headers: dict[str, str],
    ) -> str:
        """Create a new branch for MR workflow."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        branch_name = f"diagram-update-{timestamp}"

        url = f"{base_url}/projects/{project_path}/repository/branches"
        response = requests.post(
            url,
            json={"branch": branch_name, "ref": base_branch},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()

        return branch_name

    async def _create_gitlab_mr(
        self,
        base_url: str,
        project_path: str,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Create a merge request on GitLab."""
        url = f"{base_url}/projects/{project_path}/merge_requests"
        response = requests.post(
            url,
            json={
                "source_branch": source_branch,
                "target_branch": target_branch,
                "title": title,
                "description": description,
            },
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    async def list_repository_diagrams(
        self,
        repo_owner: str,
        repo_name: str,
        connection_id: str | None = None,
        access_token: str | None = None,
        use_github_app: bool = False,
        path: str = "",
    ) -> list[dict[str, Any]]:
        """
        List diagrams in a repository directory.

        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            connection_id: OAuth connection ID
            access_token: Direct access token
            use_github_app: Use GitHub App auth
            path: Directory path to search

        Returns:
            List of diagram files found
        """
        # Get authentication token
        token: str | None = None
        if access_token:
            token = access_token
        elif connection_id:
            token = await self.oauth_service.get_access_token(connection_id)
        elif use_github_app:
            token = self.github_app_auth.get_installation_token()

        if not token:
            return []

        host = self._extract_host(repo_owner, repo_name)
        host_config = self._get_host_config(host)

        diagrams = []

        if host_config.provider == GitProvider.GITHUB:
            diagrams = await self._list_github_diagrams(
                host_config.api_base_url,
                f"{repo_owner}/{repo_name}",
                path,
                token,
            )
        else:
            diagrams = await self._list_gitlab_diagrams(
                host_config.api_base_url,
                f"{repo_owner}/{repo_name}",
                path,
                token,
            )

        return diagrams

    async def _list_github_diagrams(
        self,
        base_url: str,
        repo_path: str,
        path: str,
        token: str,
    ) -> list[dict[str, Any]]:
        """List diagram files from GitHub repository."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

        url = f"{base_url}/repos/{repo_path}/contents/{path}"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            contents = response.json()

            diagrams = []
            diagram_extensions = {".svg", ".png", ".drawio", ".xml"}

            if isinstance(contents, list):
                for item in contents:
                    if item["type"] == "file":
                        ext = os.path.splitext(item["name"])[1].lower()
                        if ext in diagram_extensions:
                            diagrams.append(
                                {
                                    "name": item["name"],
                                    "path": item["path"],
                                    "sha": item["sha"],
                                    "size": item["size"],
                                    "download_url": item.get("download_url"),
                                    "html_url": item.get("html_url"),
                                }
                            )

            return diagrams

        except Exception as e:
            logger.error(f"Failed to list GitHub diagrams: {e}")
            return []

    async def _list_gitlab_diagrams(
        self,
        base_url: str,
        repo_path: str,
        path: str,
        token: str,
    ) -> list[dict[str, Any]]:
        """List diagram files from GitLab repository."""
        headers = {"Authorization": f"Bearer {token}"}

        project_path = requests.utils.quote(repo_path, safe="")
        url = f"{base_url}/projects/{project_path}/repository/tree"

        try:
            response = requests.get(
                url,
                params={"path": path, "per_page": 100},
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            contents = response.json()

            diagrams = []
            diagram_extensions = {".svg", ".png", ".drawio", ".xml"}

            for item in contents:
                if item["type"] == "blob":
                    ext = os.path.splitext(item["name"])[1].lower()
                    if ext in diagram_extensions:
                        diagrams.append(
                            {
                                "name": item["name"],
                                "path": item["path"],
                                "id": item["id"],
                                "mode": item.get("mode"),
                            }
                        )

            return diagrams

        except Exception as e:
            logger.error(f"Failed to list GitLab diagrams: {e}")
            return []


# Singleton instance
_git_sync_service: DiagramGitSync | None = None


def get_diagram_git_sync(govcloud_mode: bool = False) -> DiagramGitSync:
    """Get or create diagram Git sync singleton."""
    global _git_sync_service
    if _git_sync_service is None:
        _git_sync_service = DiagramGitSync(govcloud_mode=govcloud_mode)
    return _git_sync_service
