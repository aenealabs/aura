"""
Project Aura - Concrete Credential Enumerators

15 enumerators covering all credential-issuing integrations in the
Aura platform. Each checks a specific credential class for residual
active credentials held by an agent.

Based on ADR-086: Agentic Identity Lifecycle Controls (Phase 1)

Credential classes covered:
  1. aws_iam_roles         - IAM roles and trust policies
  2. aws_access_keys       - Long-lived access keys
  3. mcp_tokens            - MCP server session tokens
  4. oauth_refresh_tokens  - OAuth refresh tokens
  5. secrets_manager       - API keys in Secrets Manager
  6. ssm_parameters        - Credentials in SSM Parameter Store
  7. bedrock_sessions      - Bedrock session grants
  8. palantir_aip_tokens   - Palantir AIP tokens (ADR-074)
  9. github_oauth          - GitHub OAuth tokens (ADR-043)
  10. gitlab_oauth         - GitLab OAuth tokens (ADR-043)
  11. integration_hub      - Integration hub credentials (ADR-075)
  12. remem_grants         - ReMem read/write scope grants (ADR-080)
  13. capability_grants    - Capability registry entries (ADR-066)
  14. baseline_records     - Behavioral baseline records (ADR-083)
  15. provenance_records   - Provenance attestations (ADR-067)

Author: Project Aura Team
Created: 2026-04-06
"""

import logging
from typing import Any, Optional

from .registry import CredentialRecord, CredentialStatus, EnumerationResult

logger = logging.getLogger(__name__)


class _BaseEnumerator:
    """Base class providing common enumeration logic."""

    credential_class: str = ""

    def __init__(self, client: Optional[Any] = None) -> None:
        self._client = client

    def _make_result(
        self,
        agent_id: str,
        credentials: Optional[list[CredentialRecord]] = None,
        error: Optional[str] = None,
    ) -> EnumerationResult:
        """Build an EnumerationResult with zero_confirmed derived automatically.

        Audit finding C4: never claim ``zero_confirmed=True`` unless the
        enumerator actually executed a query. The previous default
        ``self._make_result(agent_id)`` (called when ``self._client is None``)
        falsely confirmed zero credentials when the truth was "we did not
        check". Decommission orchestration depends on this distinction; an
        empty result with no error is interpreted as "credentials revoked".
        """
        creds = credentials or []
        active = [c for c in creds if c.is_active]
        return EnumerationResult(
            credential_class=self.credential_class,
            agent_id=agent_id,
            credentials=creds,
            zero_confirmed=len(active) == 0 and error is None,
            error=error,
        )

    def _make_unchecked_result(self, agent_id: str) -> EnumerationResult:
        """Return a result indicating the enumerator could not check.

        Use this whenever the backing client is unavailable so the orchestrator
        treats it as needs-remediation rather than zero-confirmed.
        """
        return self._make_result(
            agent_id,
            error=(
                f"{self.credential_class} enumerator unavailable: "
                "no backing client configured"
            ),
        )

    def _make_credential(
        self,
        agent_id: str,
        credential_id: str,
        status: CredentialStatus = CredentialStatus.ACTIVE,
        description: str = "",
        **kwargs: Any,
    ) -> CredentialRecord:
        """Build a CredentialRecord."""
        return CredentialRecord(
            credential_class=self.credential_class,
            credential_id=credential_id,
            agent_id=agent_id,
            status=status,
            description=description,
            **kwargs,
        )


class IAMRoleEnumerator(_BaseEnumerator):
    """Enumerates IAM roles and trust policies for an agent."""

    credential_class = "aws_iam_roles"

    def enumerate(self, agent_id: str) -> EnumerationResult:
        """Check IAM roles with trust policies referencing this agent."""
        try:
            if self._client is None:
                return self._make_unchecked_result(agent_id)
            roles = self._client.list_roles_for_agent(agent_id)
            creds = [
                self._make_credential(
                    agent_id=agent_id,
                    credential_id=role["role_arn"],
                    description=f"IAM role: {role.get('role_name', 'unknown')}",
                )
                for role in roles
            ]
            return self._make_result(agent_id, creds)
        except Exception as e:
            logger.error(f"IAM role enumeration failed for {agent_id}: {e}")
            return self._make_result(agent_id, error=str(e))


class AccessKeyEnumerator(_BaseEnumerator):
    """Enumerates long-lived AWS access keys for an agent."""

    credential_class = "aws_access_keys"

    def enumerate(self, agent_id: str) -> EnumerationResult:
        try:
            if self._client is None:
                return self._make_unchecked_result(agent_id)
            keys = self._client.list_access_keys_for_agent(agent_id)
            creds = [
                self._make_credential(
                    agent_id=agent_id,
                    credential_id=key["access_key_id"],
                    description="Long-lived access key",
                )
                for key in keys
            ]
            return self._make_result(agent_id, creds)
        except Exception as e:
            logger.error(f"Access key enumeration failed for {agent_id}: {e}")
            return self._make_result(agent_id, error=str(e))


class MCPTokenEnumerator(_BaseEnumerator):
    """Enumerates MCP server session tokens for an agent."""

    credential_class = "mcp_tokens"

    def enumerate(self, agent_id: str) -> EnumerationResult:
        try:
            if self._client is None:
                return self._make_unchecked_result(agent_id)
            tokens = self._client.list_mcp_tokens(agent_id)
            creds = [
                self._make_credential(
                    agent_id=agent_id,
                    credential_id=token["token_id"],
                    description=f"MCP token for server: {token.get('server_id', 'unknown')}",
                )
                for token in tokens
            ]
            return self._make_result(agent_id, creds)
        except Exception as e:
            logger.error(f"MCP token enumeration failed for {agent_id}: {e}")
            return self._make_result(agent_id, error=str(e))


class OAuthRefreshTokenEnumerator(_BaseEnumerator):
    """Enumerates OAuth refresh tokens for an agent."""

    credential_class = "oauth_refresh_tokens"

    def enumerate(self, agent_id: str) -> EnumerationResult:
        try:
            if self._client is None:
                return self._make_unchecked_result(agent_id)
            tokens = self._client.list_oauth_tokens(agent_id)
            creds = [
                self._make_credential(
                    agent_id=agent_id,
                    credential_id=token["token_id"],
                    description=f"OAuth refresh token: {token.get('provider', 'unknown')}",
                )
                for token in tokens
            ]
            return self._make_result(agent_id, creds)
        except Exception as e:
            logger.error(f"OAuth token enumeration failed for {agent_id}: {e}")
            return self._make_result(agent_id, error=str(e))


class SecretsManagerEnumerator(_BaseEnumerator):
    """Enumerates API keys stored in Secrets Manager for an agent."""

    credential_class = "secrets_manager"

    def enumerate(self, agent_id: str) -> EnumerationResult:
        try:
            if self._client is None:
                return self._make_unchecked_result(agent_id)
            secrets = self._client.list_secrets_for_agent(agent_id)
            creds = [
                self._make_credential(
                    agent_id=agent_id,
                    credential_id=secret["secret_arn"],
                    description=f"Secret: {secret.get('name', 'unknown')}",
                )
                for secret in secrets
            ]
            return self._make_result(agent_id, creds)
        except Exception as e:
            logger.error(f"Secrets Manager enumeration failed for {agent_id}: {e}")
            return self._make_result(agent_id, error=str(e))


class SSMParameterEnumerator(_BaseEnumerator):
    """Enumerates credentials in SSM Parameter Store for an agent."""

    credential_class = "ssm_parameters"

    def enumerate(self, agent_id: str) -> EnumerationResult:
        try:
            if self._client is None:
                return self._make_unchecked_result(agent_id)
            params = self._client.list_ssm_params_for_agent(agent_id)
            creds = [
                self._make_credential(
                    agent_id=agent_id,
                    credential_id=param["name"],
                    description="SSM SecureString parameter",
                )
                for param in params
            ]
            return self._make_result(agent_id, creds)
        except Exception as e:
            logger.error(f"SSM parameter enumeration failed for {agent_id}: {e}")
            return self._make_result(agent_id, error=str(e))


class BedrockSessionEnumerator(_BaseEnumerator):
    """Enumerates Bedrock session grants for an agent."""

    credential_class = "bedrock_sessions"

    def enumerate(self, agent_id: str) -> EnumerationResult:
        try:
            if self._client is None:
                return self._make_unchecked_result(agent_id)
            sessions = self._client.list_bedrock_sessions(agent_id)
            creds = [
                self._make_credential(
                    agent_id=agent_id,
                    credential_id=session["session_id"],
                    description=f"Bedrock session: {session.get('model_id', 'unknown')}",
                )
                for session in sessions
            ]
            return self._make_result(agent_id, creds)
        except Exception as e:
            logger.error(f"Bedrock session enumeration failed for {agent_id}: {e}")
            return self._make_result(agent_id, error=str(e))


class PalantirAIPTokenEnumerator(_BaseEnumerator):
    """Enumerates Palantir AIP tokens for an agent (ADR-074)."""

    credential_class = "palantir_aip_tokens"

    def enumerate(self, agent_id: str) -> EnumerationResult:
        try:
            if self._client is None:
                return self._make_unchecked_result(agent_id)
            tokens = self._client.list_palantir_tokens(agent_id)
            creds = [
                self._make_credential(
                    agent_id=agent_id,
                    credential_id=token["token_id"],
                    description="Palantir AIP API token",
                )
                for token in tokens
            ]
            return self._make_result(agent_id, creds)
        except Exception as e:
            logger.error(f"Palantir AIP token enumeration failed for {agent_id}: {e}")
            return self._make_result(agent_id, error=str(e))


class GitHubOAuthEnumerator(_BaseEnumerator):
    """Enumerates GitHub OAuth tokens for an agent (ADR-043)."""

    credential_class = "github_oauth"

    def enumerate(self, agent_id: str) -> EnumerationResult:
        try:
            if self._client is None:
                return self._make_unchecked_result(agent_id)
            tokens = self._client.list_github_tokens(agent_id)
            creds = [
                self._make_credential(
                    agent_id=agent_id,
                    credential_id=token["token_id"],
                    description=f"GitHub OAuth: {token.get('scope', 'unknown')}",
                )
                for token in tokens
            ]
            return self._make_result(agent_id, creds)
        except Exception as e:
            logger.error(f"GitHub OAuth enumeration failed for {agent_id}: {e}")
            return self._make_result(agent_id, error=str(e))


class GitLabOAuthEnumerator(_BaseEnumerator):
    """Enumerates GitLab OAuth tokens for an agent (ADR-043)."""

    credential_class = "gitlab_oauth"

    def enumerate(self, agent_id: str) -> EnumerationResult:
        try:
            if self._client is None:
                return self._make_unchecked_result(agent_id)
            tokens = self._client.list_gitlab_tokens(agent_id)
            creds = [
                self._make_credential(
                    agent_id=agent_id,
                    credential_id=token["token_id"],
                    description=f"GitLab OAuth: {token.get('scope', 'unknown')}",
                )
                for token in tokens
            ]
            return self._make_result(agent_id, creds)
        except Exception as e:
            logger.error(f"GitLab OAuth enumeration failed for {agent_id}: {e}")
            return self._make_result(agent_id, error=str(e))


class IntegrationHubEnumerator(_BaseEnumerator):
    """Enumerates integration hub credentials for an agent (ADR-075)."""

    credential_class = "integration_hub"

    def enumerate(self, agent_id: str) -> EnumerationResult:
        try:
            if self._client is None:
                return self._make_unchecked_result(agent_id)
            cred_list = self._client.list_integration_credentials(agent_id)
            creds = [
                self._make_credential(
                    agent_id=agent_id,
                    credential_id=c["credential_id"],
                    description=f"Integration: {c.get('integration_name', 'unknown')}",
                )
                for c in cred_list
            ]
            return self._make_result(agent_id, creds)
        except Exception as e:
            logger.error(f"Integration hub enumeration failed for {agent_id}: {e}")
            return self._make_result(agent_id, error=str(e))


class ReMemGrantEnumerator(_BaseEnumerator):
    """Enumerates ReMem read/write scope grants for an agent (ADR-080)."""

    credential_class = "remem_grants"

    def enumerate(self, agent_id: str) -> EnumerationResult:
        try:
            if self._client is None:
                return self._make_unchecked_result(agent_id)
            grants = self._client.list_remem_grants(agent_id)
            creds = [
                self._make_credential(
                    agent_id=agent_id,
                    credential_id=grant["grant_id"],
                    description=f"ReMem scope: {grant.get('scope', 'unknown')}",
                )
                for grant in grants
            ]
            return self._make_result(agent_id, creds)
        except Exception as e:
            logger.error(f"ReMem grant enumeration failed for {agent_id}: {e}")
            return self._make_result(agent_id, error=str(e))


class CapabilityGrantEnumerator(_BaseEnumerator):
    """Enumerates capability registry entries for an agent (ADR-066)."""

    credential_class = "capability_grants"

    def enumerate(self, agent_id: str) -> EnumerationResult:
        try:
            if self._client is None:
                return self._make_unchecked_result(agent_id)
            grants = self._client.list_capability_grants(agent_id)
            creds = [
                self._make_credential(
                    agent_id=agent_id,
                    credential_id=grant["grant_id"],
                    description=f"Capability: {grant.get('tool_name', 'unknown')}",
                )
                for grant in grants
            ]
            return self._make_result(agent_id, creds)
        except Exception as e:
            logger.error(f"Capability grant enumeration failed for {agent_id}: {e}")
            return self._make_result(agent_id, error=str(e))


class BaselineRecordEnumerator(_BaseEnumerator):
    """Enumerates behavioral baseline records for an agent (ADR-083)."""

    credential_class = "baseline_records"

    def enumerate(self, agent_id: str) -> EnumerationResult:
        try:
            if self._client is None:
                return self._make_unchecked_result(agent_id)
            baselines = self._client.list_baselines(agent_id)
            creds = [
                self._make_credential(
                    agent_id=agent_id,
                    credential_id=b["baseline_id"],
                    description=f"Baseline: {b.get('metric_type', 'unknown')}",
                )
                for b in baselines
            ]
            return self._make_result(agent_id, creds)
        except Exception as e:
            logger.error(f"Baseline record enumeration failed for {agent_id}: {e}")
            return self._make_result(agent_id, error=str(e))


class ProvenanceRecordEnumerator(_BaseEnumerator):
    """Enumerates provenance attestations for an agent (ADR-067)."""

    credential_class = "provenance_records"

    def enumerate(self, agent_id: str) -> EnumerationResult:
        try:
            if self._client is None:
                return self._make_unchecked_result(agent_id)
            records = self._client.list_provenance_records(agent_id)
            creds = [
                self._make_credential(
                    agent_id=agent_id,
                    credential_id=r["record_id"],
                    description="Provenance attestation",
                )
                for r in records
            ]
            return self._make_result(agent_id, creds)
        except Exception as e:
            logger.error(f"Provenance record enumeration failed for {agent_id}: {e}")
            return self._make_result(agent_id, error=str(e))


# All enumerator classes for bulk registration
ALL_ENUMERATOR_CLASSES = [
    IAMRoleEnumerator,
    AccessKeyEnumerator,
    MCPTokenEnumerator,
    OAuthRefreshTokenEnumerator,
    SecretsManagerEnumerator,
    SSMParameterEnumerator,
    BedrockSessionEnumerator,
    PalantirAIPTokenEnumerator,
    GitHubOAuthEnumerator,
    GitLabOAuthEnumerator,
    IntegrationHubEnumerator,
    ReMemGrantEnumerator,
    CapabilityGrantEnumerator,
    BaselineRecordEnumerator,
    ProvenanceRecordEnumerator,
]


def register_all_enumerators(
    registry: Optional[Any] = None,
    clients: Optional[dict[str, Any]] = None,
) -> None:
    """
    Register all 15 Phase 1 enumerators in the given registry.

    Args:
        registry: EnumeratorRegistry to register into (uses global if None).
        clients: Optional dict mapping credential_class to client instances.
    """
    if registry is None:
        from .registry import get_enumerator_registry

        registry = get_enumerator_registry()

    client_map = clients or {}
    for cls in ALL_ENUMERATOR_CLASSES:
        client = client_map.get(cls.credential_class)
        enumerator = cls(client=client)
        registry.register(enumerator)

    logger.info(f"Registered {len(ALL_ENUMERATOR_CLASSES)} credential enumerators")
