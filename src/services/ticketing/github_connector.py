"""
GitHub Issues Ticketing Connector.

Primary connector implementation using GitHub REST API v3.
Supports OAuth App authentication and Personal Access Tokens.
See ADR-046 for architecture details.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

from .base_connector import (
    Ticket,
    TicketCreate,
    TicketFilters,
    TicketingConnector,
    TicketPriority,
    TicketResult,
    TicketStatus,
    TicketUpdate,
)

logger = logging.getLogger(__name__)

# GitHub API status to internal status mapping
GITHUB_STATE_TO_STATUS = {
    "open": TicketStatus.OPEN,
    "closed": TicketStatus.CLOSED,
}

# Priority labels used in GitHub Issues
PRIORITY_LABELS = {
    "priority:critical": TicketPriority.CRITICAL,
    "priority:high": TicketPriority.HIGH,
    "priority:medium": TicketPriority.MEDIUM,
    "priority:low": TicketPriority.LOW,
    # Alternative formats
    "P0": TicketPriority.CRITICAL,
    "P1": TicketPriority.HIGH,
    "P2": TicketPriority.MEDIUM,
    "P3": TicketPriority.LOW,
}


class GitHubIssuesConnector(TicketingConnector):
    """
    GitHub Issues connector for support ticketing.

    Uses GitHub REST API v3 to create and manage issues.
    Supports both OAuth tokens and Personal Access Tokens.

    Configuration:
        - repository: GitHub repository in 'owner/repo' format
        - token: GitHub OAuth token or PAT with 'issues:write' scope
        - api_url: Optional custom API URL for GitHub Enterprise

    Example:
        connector = GitHubIssuesConnector(
            repository="aenealabs/support",
            token="ghp_xxxxxxxxxxxx",
        )
        result = await connector.create_ticket(TicketCreate(
            title="Login issue",
            description="Cannot login with SSO",
            priority=TicketPriority.HIGH,
        ))
    """

    def __init__(
        self,
        repository: str,
        token: str,
        api_url: str = "https://api.github.com",
        default_labels: Optional[List[str]] = None,
        default_assignees: Optional[List[str]] = None,
    ):
        """
        Initialize GitHub Issues connector.

        Args:
            repository: GitHub repository in 'owner/repo' format
            token: GitHub OAuth token or PAT
            api_url: GitHub API URL (for Enterprise)
            default_labels: Labels to add to all tickets
            default_assignees: Default assignees for new tickets
        """
        self._repository = repository
        self._token = token
        self._api_url = api_url.rstrip("/")
        self._default_labels = default_labels or ["support", "aura"]
        self._default_assignees = default_assignees or []

        # Parse owner and repo
        parts = repository.split("/")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid repository format: {repository}. Expected 'owner/repo'"
            )
        self._owner = parts[0]
        self._repo = parts[1]

        # HTTP client with auth headers
        self._client = httpx.AsyncClient(
            base_url=self._api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

        # In-memory ticket ID mapping (in production, use DynamoDB)
        self._ticket_mapping: Dict[str, int] = {}  # internal_id -> issue_number
        self._reverse_mapping: Dict[int, str] = {}  # issue_number -> internal_id

    @property
    def provider_name(self) -> str:
        return "github"

    @property
    def provider_display_name(self) -> str:
        return "GitHub Issues"

    async def test_connection(self) -> bool:
        """Test GitHub API connectivity and token validity."""
        try:
            response = await self._client.get(f"/repos/{self._owner}/{self._repo}")
            if response.status_code == 200:
                logger.info(f"GitHub connection test successful for {self._repository}")
                return True
            elif response.status_code == 401:
                logger.error("GitHub authentication failed: invalid token")
                return False
            elif response.status_code == 404:
                logger.error(f"GitHub repository not found: {self._repository}")
                return False
            else:
                logger.error(f"GitHub connection test failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"GitHub connection test error: {e}")
            return False

    async def create_ticket(self, ticket: TicketCreate) -> TicketResult:
        """Create a new GitHub issue."""
        try:
            # Build labels list
            labels = list(self._default_labels)
            labels.extend(ticket.labels or [])
            labels.extend(self._map_priority_to_labels(ticket.priority))

            # Build issue body with metadata
            body = ticket.description
            if ticket.customer_id:
                body += f"\n\n---\n**Customer ID:** {ticket.customer_id}"
            if ticket.metadata:
                body += f"\n**Metadata:** {ticket.metadata}"

            # Create issue
            response = await self._client.post(
                f"/repos/{self._owner}/{self._repo}/issues",
                json={
                    "title": ticket.title,
                    "body": body,
                    "labels": labels,
                    "assignees": (
                        self._default_assignees
                        if not ticket.assignee
                        else [ticket.assignee]
                    ),
                },
            )

            if response.status_code == 201:
                issue = response.json()
                internal_id = str(uuid4())
                issue_number = issue["number"]

                # Store mapping
                self._ticket_mapping[internal_id] = issue_number
                self._reverse_mapping[issue_number] = internal_id

                created_ticket = self._parse_github_issue(issue, internal_id)
                logger.info(
                    f"Created GitHub issue #{issue_number} for ticket {internal_id}"
                )

                return TicketResult(success=True, ticket=created_ticket)
            else:
                error_msg = response.json().get("message", "Unknown error")
                logger.error(f"Failed to create GitHub issue: {error_msg}")
                return TicketResult(
                    success=False,
                    error_message=f"GitHub API error: {error_msg}",
                    error_code=str(response.status_code),
                )

        except Exception as e:
            logger.exception(f"Error creating GitHub issue: {e}")
            return TicketResult(
                success=False,
                error_message=str(e),
                error_code="INTERNAL_ERROR",
            )

    async def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Get ticket by internal ID."""
        issue_number = self._ticket_mapping.get(ticket_id)
        if not issue_number:
            logger.warning(f"Ticket {ticket_id} not found in mapping")
            return None

        try:
            response = await self._client.get(
                f"/repos/{self._owner}/{self._repo}/issues/{issue_number}"
            )

            if response.status_code == 200:
                issue = response.json()
                return self._parse_github_issue(issue, ticket_id)
            elif response.status_code == 404:
                logger.warning(f"GitHub issue #{issue_number} not found")
                return None
            else:
                logger.error(f"Failed to get GitHub issue: {response.status_code}")
                return None

        except Exception as e:
            logger.exception(f"Error getting GitHub issue: {e}")
            return None

    async def get_ticket_by_external_id(self, external_id: str) -> Optional[Ticket]:
        """Get ticket by GitHub issue number."""
        try:
            issue_number = int(external_id)
        except ValueError:
            logger.error(f"Invalid GitHub issue number: {external_id}")
            return None

        try:
            response = await self._client.get(
                f"/repos/{self._owner}/{self._repo}/issues/{issue_number}"
            )

            if response.status_code == 200:
                issue = response.json()
                internal_id = self._reverse_mapping.get(issue_number, str(uuid4()))
                if issue_number not in self._reverse_mapping:
                    self._ticket_mapping[internal_id] = issue_number
                    self._reverse_mapping[issue_number] = internal_id
                return self._parse_github_issue(issue, internal_id)
            else:
                return None

        except Exception as e:
            logger.exception(f"Error getting GitHub issue by external ID: {e}")
            return None

    async def update_ticket(
        self, ticket_id: str, updates: TicketUpdate
    ) -> TicketResult:
        """Update an existing GitHub issue."""
        issue_number = self._ticket_mapping.get(ticket_id)
        if not issue_number:
            return TicketResult(
                success=False,
                error_message=f"Ticket {ticket_id} not found",
                error_code="NOT_FOUND",
            )

        try:
            update_data: Dict[str, Any] = {}

            if updates.title is not None:
                update_data["title"] = updates.title
            if updates.description is not None:
                update_data["body"] = updates.description
            if updates.status is not None:
                update_data["state"] = (
                    "open" if updates.status != TicketStatus.CLOSED else "closed"
                )
            if updates.labels is not None:
                update_data["labels"] = updates.labels
            if updates.assignee is not None:
                update_data["assignees"] = (
                    [updates.assignee] if updates.assignee else []
                )

            response = await self._client.patch(
                f"/repos/{self._owner}/{self._repo}/issues/{issue_number}",
                json=update_data,
            )

            if response.status_code == 200:
                issue = response.json()
                updated_ticket = self._parse_github_issue(issue, ticket_id)
                logger.info(f"Updated GitHub issue #{issue_number}")
                return TicketResult(success=True, ticket=updated_ticket)
            else:
                error_msg = response.json().get("message", "Unknown error")
                return TicketResult(
                    success=False,
                    error_message=f"GitHub API error: {error_msg}",
                    error_code=str(response.status_code),
                )

        except Exception as e:
            logger.exception(f"Error updating GitHub issue: {e}")
            return TicketResult(
                success=False,
                error_message=str(e),
                error_code="INTERNAL_ERROR",
            )

    async def list_tickets(
        self, filters: Optional[TicketFilters] = None
    ) -> List[Ticket]:
        """List GitHub issues with optional filters."""
        try:
            params: Dict[str, Any] = {
                "per_page": filters.limit if filters else 50,
                "page": (
                    (filters.offset // filters.limit + 1)
                    if filters and filters.limit
                    else 1
                ),
            }

            # Apply status filter
            if filters and filters.status:
                if (
                    TicketStatus.CLOSED in filters.status
                    and TicketStatus.OPEN not in filters.status
                ):
                    params["state"] = "closed"
                elif (
                    TicketStatus.OPEN in filters.status
                    and TicketStatus.CLOSED not in filters.status
                ):
                    params["state"] = "open"
                else:
                    params["state"] = "all"
            else:
                params["state"] = "all"

            # Apply label filter
            if filters and filters.labels:
                params["labels"] = ",".join(filters.labels)

            # Apply assignee filter
            if filters and filters.assignee:
                params["assignee"] = filters.assignee

            response = await self._client.get(
                f"/repos/{self._owner}/{self._repo}/issues",
                params=params,
            )

            if response.status_code == 200:
                issues = response.json()
                tickets = []
                for issue in issues:
                    # Skip pull requests (GitHub API returns them in issues endpoint)
                    if "pull_request" in issue:
                        continue

                    issue_number = issue["number"]
                    internal_id = self._reverse_mapping.get(issue_number)
                    if not internal_id:
                        internal_id = str(uuid4())
                        self._ticket_mapping[internal_id] = issue_number
                        self._reverse_mapping[issue_number] = internal_id

                    tickets.append(self._parse_github_issue(issue, internal_id))
                return tickets
            else:
                logger.error(f"Failed to list GitHub issues: {response.status_code}")
                return []

        except Exception as e:
            logger.exception(f"Error listing GitHub issues: {e}")
            return []

    async def add_comment(
        self, ticket_id: str, comment: str, is_internal: bool = False
    ) -> TicketResult:
        """Add a comment to a GitHub issue."""
        issue_number = self._ticket_mapping.get(ticket_id)
        if not issue_number:
            return TicketResult(
                success=False,
                error_message=f"Ticket {ticket_id} not found",
                error_code="NOT_FOUND",
            )

        try:
            # GitHub doesn't support internal comments, so we prefix them
            comment_body = comment
            if is_internal:
                comment_body = f"**[Internal Note]**\n\n{comment}"

            response = await self._client.post(
                f"/repos/{self._owner}/{self._repo}/issues/{issue_number}/comments",
                json={"body": comment_body},
            )

            if response.status_code == 201:
                # Fetch updated issue
                ticket = await self.get_ticket(ticket_id)
                logger.info(f"Added comment to GitHub issue #{issue_number}")
                return TicketResult(success=True, ticket=ticket)
            else:
                error_msg = response.json().get("message", "Unknown error")
                return TicketResult(
                    success=False,
                    error_message=f"GitHub API error: {error_msg}",
                    error_code=str(response.status_code),
                )

        except Exception as e:
            logger.exception(f"Error adding comment to GitHub issue: {e}")
            return TicketResult(
                success=False,
                error_message=str(e),
                error_code="INTERNAL_ERROR",
            )

    async def close_ticket(
        self, ticket_id: str, resolution: Optional[str] = None
    ) -> TicketResult:
        """Close a GitHub issue."""
        if resolution:
            # Add resolution as comment before closing
            await self.add_comment(ticket_id, f"**Resolution:** {resolution}")

        return await self.update_ticket(
            ticket_id,
            TicketUpdate(status=TicketStatus.CLOSED),
        )

    async def reopen_ticket(
        self, ticket_id: str, reason: Optional[str] = None
    ) -> TicketResult:
        """Reopen a closed GitHub issue."""
        if reason:
            await self.add_comment(ticket_id, f"**Reopening:** {reason}")

        return await self.update_ticket(
            ticket_id,
            TicketUpdate(status=TicketStatus.OPEN),
        )

    def _parse_github_issue(self, issue: Dict[str, Any], internal_id: str) -> Ticket:
        """Parse GitHub issue JSON into Ticket object."""
        # Extract priority from labels
        priority = TicketPriority.MEDIUM
        labels = []
        for label in issue.get("labels", []):
            label_name = label["name"] if isinstance(label, dict) else label
            if label_name in PRIORITY_LABELS:
                priority = PRIORITY_LABELS[label_name]
            else:
                labels.append(label_name)

        # Parse dates
        created_at = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
        updated_at = datetime.fromisoformat(issue["updated_at"].replace("Z", "+00:00"))

        # Map status
        status = GITHUB_STATE_TO_STATUS.get(issue["state"], TicketStatus.OPEN)

        # Get assignee
        assignee = None
        if issue.get("assignees"):
            assignee = issue["assignees"][0]["login"]
        elif issue.get("assignee"):
            assignee = issue["assignee"]["login"]

        return Ticket(
            id=internal_id,
            external_id=str(issue["number"]),
            title=issue["title"],
            description=issue.get("body", ""),
            status=status,
            priority=priority,
            labels=labels,
            assignee=assignee,
            reporter=issue["user"]["login"],
            created_at=created_at,
            updated_at=updated_at,
            external_url=issue["html_url"],
            comments=[],  # Comments loaded separately if needed
            metadata={
                "github_id": issue["id"],
                "repository": self._repository,
            },
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._client.aclose()
