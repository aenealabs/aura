"""
Project Aura - Webhook Registration Service

Manages webhook registration on customer repositories for
incremental code updates when pushes occur.

Author: Project Aura Team
Created: 2025-12-17
Version: 1.0.0
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import boto3
import requests
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class WebhookStatus:
    """Webhook status constants."""

    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"


@dataclass
class WebhookConfig:
    """Webhook configuration settings."""

    events: list[str] | None = None
    secret: str | None = None
    content_type: str = "json"
    insecure_ssl: bool = False

    def __post_init__(self) -> None:
        """Set default events if not provided."""
        if self.events is None:
            self.events = ["push", "pull_request"]


@dataclass
class WebhookRegistration:
    """Webhook registration details."""

    webhook_id: str
    provider: str
    repository_id: str
    repository_name: str
    callback_url: str
    config: WebhookConfig
    status: str
    created_at: str
    updated_at: str | None = None
    last_delivery_at: str | None = None
    error_message: str | None = None


@dataclass
class WebhookInfo:
    """Webhook information."""

    webhook_id: str
    provider: str
    repository_id: str
    callback_url: str
    events: list[str]
    active: bool
    created_at: str


class WebhookRegistrationService:
    """
    Webhook Registration Service.

    Registers webhooks on GitHub/GitLab repositories to receive
    push notifications for incremental code updates.
    """

    GITHUB_API_URL = "https://api.github.com"
    GITLAB_API_URL = "https://gitlab.com/api/v4"

    def __init__(
        self,
        dynamodb_client: Any | None = None,
        secrets_client: Any | None = None,
        environment: str | None = None,
        project_name: str = "aura",
    ):
        """Initialize webhook registration service."""
        self.environment = environment or os.getenv("ENVIRONMENT", "dev")
        self.project_name = project_name

        self.dynamodb = dynamodb_client or boto3.resource("dynamodb")
        self.secrets_client = secrets_client or boto3.client("secretsmanager")

        self.repositories_table = self.dynamodb.Table(
            f"{project_name}-repositories-{self.environment}"
        )

        self._webhook_callback_url = os.getenv(
            "WEBHOOK_CALLBACK_URL", "https://api.aura.local/api/v1/webhooks/github"
        )

    async def register_webhook(
        self,
        repository_id: str,
        provider: str,
        repo_full_name: str,
        access_token: str,
        events: list[str] | None = None,
    ) -> WebhookInfo:
        """
        Register a webhook on a repository.

        Args:
            repository_id: Internal repository ID
            provider: OAuth provider (github, gitlab)
            repo_full_name: Full repository name (org/repo)
            access_token: OAuth access token
            events: Events to subscribe to

        Returns:
            WebhookInfo object
        """
        events = events or ["push", "pull_request"]

        # Generate webhook secret
        webhook_secret = secrets.token_hex(32)

        # Store webhook secret in Secrets Manager
        secret_name = (
            f"/{self.project_name}/{self.environment}/webhooks/{repository_id}"
        )
        try:
            self.secrets_client.create_secret(
                Name=secret_name,
                SecretString=json.dumps({"secret": webhook_secret}),
                Tags=[
                    {"Key": "Project", "Value": self.project_name},
                    {"Key": "Environment", "Value": self.environment},
                    {"Key": "Component", "Value": "webhook"},
                ],
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceExistsException":
                # Update existing secret
                self.secrets_client.put_secret_value(
                    SecretId=secret_name,
                    SecretString=json.dumps({"secret": webhook_secret}),
                )
            else:
                raise

        # Register webhook with provider
        if provider == "github":
            webhook_id = await self._register_github_webhook(
                repo_full_name, access_token, webhook_secret, events
            )
        elif provider == "gitlab":
            webhook_id = await self._register_gitlab_webhook(
                repo_full_name, access_token, webhook_secret, events
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        # Update repository with webhook ID
        now = datetime.now(timezone.utc).isoformat()
        self.repositories_table.update_item(
            Key={"repository_id": repository_id},
            UpdateExpression="SET webhook_id = :wid, webhook_secret_arn = :arn, updated_at = :now",
            ExpressionAttributeValues={
                ":wid": webhook_id,
                ":arn": secret_name,
                ":now": now,
            },
        )

        logger.info(f"Registered webhook {webhook_id} for repository {repository_id}")

        return WebhookInfo(
            webhook_id=webhook_id,
            provider=provider,
            repository_id=repository_id,
            callback_url=self._webhook_callback_url,
            events=events,
            active=True,
            created_at=now,
        )

    async def _register_github_webhook(
        self,
        repo_full_name: str,
        access_token: str,
        webhook_secret: str,
        events: list[str],
    ) -> str:
        """Register webhook with GitHub."""
        url = f"{self.GITHUB_API_URL}/repos/{repo_full_name}/hooks"

        payload = {
            "name": "web",
            "active": True,
            "events": events,
            "config": {
                "url": self._webhook_callback_url,
                "content_type": "json",
                "secret": webhook_secret,
                "insecure_ssl": "0",
            },
        }

        response = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

        if response.status_code == 422:
            # Webhook might already exist
            error = response.json()
            if "already exists" in str(error).lower():
                # List existing webhooks and return matching one
                existing = await self._find_github_webhook(repo_full_name, access_token)
                if existing:
                    return existing
            raise ValueError(f"GitHub webhook error: {error}")

        response.raise_for_status()
        data = response.json()
        return str(data["id"])

    async def _find_github_webhook(
        self, repo_full_name: str, access_token: str
    ) -> str | None:
        """Find existing webhook matching our callback URL."""
        url = f"{self.GITHUB_API_URL}/repos/{repo_full_name}/hooks"

        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=30,
        )
        response.raise_for_status()

        for hook in response.json():
            config = hook.get("config", {})
            if config.get("url") == self._webhook_callback_url:
                return str(hook["id"])

        return None

    async def _register_gitlab_webhook(
        self,
        project_path: str,
        access_token: str,
        webhook_secret: str,
        events: list[str],
    ) -> str:
        """Register webhook with GitLab."""
        # URL encode the project path
        encoded_path = project_path.replace("/", "%2F")
        url = f"{self.GITLAB_API_URL}/projects/{encoded_path}/hooks"

        # Map events to GitLab format
        _gitlab_events = {  # noqa: F841
            "push": "push_events",
            "pull_request": "merge_requests_events",
            "issues": "issues_events",
        }

        payload = {
            "url": self._webhook_callback_url,
            "token": webhook_secret,
            "push_events": "push" in events,
            "merge_requests_events": "pull_request" in events,
            "enable_ssl_verification": True,
        }

        response = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return str(data["id"])

    async def delete_webhook(
        self,
        repository_id: str,
        provider: str,
        repo_full_name: str,
        access_token: str,
    ) -> None:
        """Delete webhook from repository."""
        # Get webhook ID from repository
        response = self.repositories_table.get_item(
            Key={"repository_id": repository_id}
        )
        item = response.get("Item", {})
        webhook_id_raw = item.get("webhook_id")
        webhook_secret_arn = item.get("webhook_secret_arn")

        if not webhook_id_raw:
            logger.warning(f"No webhook found for repository {repository_id}")
            return

        webhook_id = str(webhook_id_raw)

        # Delete from provider
        try:
            if provider == "github":
                await self._delete_github_webhook(
                    repo_full_name, webhook_id, access_token
                )
            elif provider == "gitlab":
                await self._delete_gitlab_webhook(
                    repo_full_name, webhook_id, access_token
                )
        except Exception as e:
            logger.warning(f"Failed to delete webhook from provider: {e}")

        # Delete secret
        if webhook_secret_arn:
            try:
                self.secrets_client.delete_secret(
                    SecretId=webhook_secret_arn,
                    ForceDeleteWithoutRecovery=True,
                )
            except ClientError as e:
                logger.warning(f"Failed to delete webhook secret: {e}")

        # Update repository
        self.repositories_table.update_item(
            Key={"repository_id": repository_id},
            UpdateExpression="REMOVE webhook_id, webhook_secret_arn SET updated_at = :now",
            ExpressionAttributeValues={":now": datetime.now(timezone.utc).isoformat()},
        )

        logger.info(f"Deleted webhook for repository {repository_id}")

    async def _delete_github_webhook(
        self, repo_full_name: str, webhook_id: str, access_token: str
    ) -> None:
        """Delete webhook from GitHub."""
        url = f"{self.GITHUB_API_URL}/repos/{repo_full_name}/hooks/{webhook_id}"
        response = requests.delete(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=30,
        )
        if response.status_code != 404:  # Ignore already deleted
            response.raise_for_status()

    async def _delete_gitlab_webhook(
        self, project_path: str, webhook_id: str, access_token: str
    ) -> None:
        """Delete webhook from GitLab."""
        encoded_path = project_path.replace("/", "%2F")
        url = f"{self.GITLAB_API_URL}/projects/{encoded_path}/hooks/{webhook_id}"
        response = requests.delete(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        if response.status_code != 404:  # Ignore already deleted
            response.raise_for_status()

    async def verify_webhook_signature(
        self,
        repository_id: str,
        signature: str,
        payload: bytes,
    ) -> bool:
        """
        Verify webhook signature.

        Args:
            repository_id: Repository ID
            signature: Signature from webhook header
            payload: Raw request body

        Returns:
            True if signature is valid
        """
        # Get repository to find webhook secret ARN
        response = self.repositories_table.get_item(
            Key={"repository_id": repository_id}
        )
        item = response.get("Item", {})
        webhook_secret_arn = item.get("webhook_secret_arn")

        if not webhook_secret_arn:
            logger.warning(f"No webhook secret for repository {repository_id}")
            return False

        # Get secret
        try:
            secret_response = self.secrets_client.get_secret_value(
                SecretId=webhook_secret_arn
            )
            secret_data = json.loads(secret_response["SecretString"])
            webhook_secret = secret_data["secret"]
        except ClientError as e:
            logger.error(f"Failed to get webhook secret: {e}")
            return False

        # Verify signature (GitHub format: sha256=...)
        if signature.startswith("sha256="):
            expected = (
                "sha256="
                + hmac.new(
                    webhook_secret.encode(),
                    payload,
                    hashlib.sha256,
                ).hexdigest()
            )
            return hmac.compare_digest(signature, expected)
        elif signature.startswith("sha1="):
            expected = (
                "sha1="
                + hmac.new(
                    webhook_secret.encode(),
                    payload,
                    hashlib.sha1,
                ).hexdigest()
            )
            return hmac.compare_digest(signature, expected)
        else:
            # GitLab uses X-Gitlab-Token header (direct comparison)
            return hmac.compare_digest(signature, webhook_secret)

    async def get_webhook_status(
        self,
        repository_id: str,
        provider: str,
        repo_full_name: str,
        access_token: str,
    ) -> dict:
        """Get webhook status from provider."""
        response = self.repositories_table.get_item(
            Key={"repository_id": repository_id}
        )
        item = response.get("Item", {})
        webhook_id_raw = item.get("webhook_id")

        if not webhook_id_raw:
            return {"status": "not_configured"}

        webhook_id = str(webhook_id_raw)

        try:
            if provider == "github":
                return await self._get_github_webhook_status(
                    repo_full_name, webhook_id, access_token
                )
            elif provider == "gitlab":
                return await self._get_gitlab_webhook_status(
                    repo_full_name, webhook_id, access_token
                )
        except Exception as e:
            logger.error(f"Failed to get webhook status: {e}")
            return {"status": "error", "error": str(e)}

        return {"status": "unknown"}

    async def _get_github_webhook_status(
        self, repo_full_name: str, webhook_id: str, access_token: str
    ) -> dict:
        """Get GitHub webhook status."""
        url = f"{self.GITHUB_API_URL}/repos/{repo_full_name}/hooks/{webhook_id}"
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        return {
            "status": "active" if data.get("active") else "inactive",
            "last_response": data.get("last_response", {}),
            "events": data.get("events", []),
        }

    async def _get_gitlab_webhook_status(
        self, project_path: str, webhook_id: str, access_token: str
    ) -> dict:
        """Get GitLab webhook status."""
        encoded_path = project_path.replace("/", "%2F")
        url = f"{self.GITLAB_API_URL}/projects/{encoded_path}/hooks/{webhook_id}"
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        events = []
        if data.get("push_events"):
            events.append("push")
        if data.get("merge_requests_events"):
            events.append("merge_request")

        return {
            "status": "active" if data.get("enable_ssl_verification") else "inactive",
            "events": events,
        }


# Singleton instance
_webhook_service: WebhookRegistrationService | None = None


def get_webhook_service() -> WebhookRegistrationService:
    """Get or create webhook service singleton."""
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = WebhookRegistrationService()
    return _webhook_service
