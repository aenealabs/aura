"""
Cloud Discovery Service
========================

ADR-056 Phase 2: Cloud Infrastructure Correlation

Main orchestration service for cloud resource discovery. This is the
primary entry point for the Documentation Agent to discover and
correlate cloud infrastructure.

Features:
- Multi-provider discovery (AWS, Azure)
- IaC correlation
- Caching with configurable TTL
- Circuit breaker integration
- Audit logging
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.services.cloud_discovery.aws_provider import AWSDiscoveryProvider
from src.services.cloud_discovery.circuit_breaker import (
    CircuitBreakerConfig,
    get_circuit_breaker_registry,
)
from src.services.cloud_discovery.credential_proxy import CredentialProxyService
from src.services.cloud_discovery.exceptions import (
    CloudDiscoveryError,
    CorrelationError,
    ProviderError,
)
from src.services.cloud_discovery.iac_correlator import IaCCorrelator
from src.services.cloud_discovery.types import (
    CloudProvider,
    CorrelationResult,
    DiscoveryResult,
)

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryRequest:
    """Request for cloud discovery.

    Attributes:
        account_id: Cloud account/subscription ID
        provider: Cloud provider (aws, azure)
        regions: Regions to discover (default: all configured)
        services: Services to discover (default: all)
        tags_filter: Optional filter by tags
        include_iac_correlation: Whether to correlate with IaC
        repository_path: Path to repository for IaC correlation
        stack_name: CloudFormation stack name for direct lookup
        timeout_seconds: Discovery timeout
    """

    account_id: str
    provider: CloudProvider = CloudProvider.AWS
    regions: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    tags_filter: dict[str, str] = field(default_factory=dict)
    include_iac_correlation: bool = True
    repository_path: str | None = None
    stack_name: str | None = None
    timeout_seconds: float = 300.0


@dataclass
class FullDiscoveryResult:
    """Complete discovery result with IaC correlation.

    Attributes:
        discovery: Raw discovery result
        correlation: IaC correlation result (if requested)
        providers_used: Providers that were queried
        cache_hit: Whether result was from cache
        discovered_at: Timestamp of discovery
        metadata: Additional metadata
    """

    discovery: DiscoveryResult
    correlation: CorrelationResult | None = None
    providers_used: list[CloudProvider] = field(default_factory=list)
    cache_hit: bool = False
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_resources(self) -> int:
        """Get total discovered resources."""
        return len(self.discovery.resources)

    @property
    def correlation_rate(self) -> float | None:
        """Get IaC correlation rate if available."""
        if self.correlation:
            return self.correlation.correlation_rate
        return None


class CloudDiscoveryService:
    """
    Main orchestration service for cloud resource discovery.

    This service coordinates:
    - Credential management (via CredentialProxyService)
    - Provider-specific discovery (AWS, Azure)
    - IaC correlation
    - Result caching
    - Circuit breaker management

    Usage:
        service = CloudDiscoveryService(
            secrets_service=secrets_service,
            organization_id='my-org',
        )
        await service.initialize()

        # Full discovery with IaC correlation
        result = await service.discover(
            request=DiscoveryRequest(
                account_id='123456789012',
                repository_path='/path/to/repo',
            )
        )

        print(f"Discovered {result.total_resources} resources")
        print(f"Correlation rate: {result.correlation_rate:.1%}")
    """

    # Cache TTL
    DEFAULT_CACHE_TTL = timedelta(hours=1)

    def __init__(
        self,
        secrets_service: Any | None = None,
        organization_id: str = "",
        region: str | None = None,
        use_mock: bool = False,
        cache_ttl: timedelta | None = None,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
    ) -> None:
        """Initialize cloud discovery service.

        Args:
            secrets_service: SecretsService for credential management
            organization_id: Organization ID for namespacing
            region: Default AWS region
            use_mock: Use mock mode for testing
            cache_ttl: Cache time-to-live
            circuit_breaker_config: Circuit breaker configuration
        """
        self.organization_id = organization_id or os.environ.get("ORGANIZATION_ID", "")
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.use_mock = use_mock
        self.cache_ttl = cache_ttl or self.DEFAULT_CACHE_TTL

        # Initialize credential proxy if secrets service provided
        self.credential_proxy: CredentialProxyService | None = None
        if secrets_service:
            self.credential_proxy = CredentialProxyService(
                secrets_service=secrets_service,
                organization_id=self.organization_id,
                region=self.region,
                use_mock=use_mock,
            )

        # Initialize providers
        self.aws_provider = AWSDiscoveryProvider(
            credential_proxy=self.credential_proxy,
            use_mock=use_mock,
            circuit_breaker_config=circuit_breaker_config,
        )

        # IaC correlator
        self.iac_correlator = IaCCorrelator(use_mock=use_mock)

        # Result cache
        self._cache: dict[str, tuple[FullDiscoveryResult, datetime]] = {}

        # Initialized flag
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the service.

        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True

        # Connect credential proxy if available
        if self.credential_proxy:
            connected = await self.credential_proxy.connect()
            if not connected:
                logger.warning("Failed to connect credential proxy")

        self._initialized = True
        logger.info(f"CloudDiscoveryService initialized for org {self.organization_id}")
        return True

    async def shutdown(self) -> None:
        """Shutdown the service and cleanup resources."""
        if self.credential_proxy:
            await self.credential_proxy.disconnect()

        self._cache.clear()
        self._initialized = False
        logger.info("CloudDiscoveryService shutdown complete")

    async def discover(
        self,
        request: DiscoveryRequest,
        use_cache: bool = True,
    ) -> FullDiscoveryResult:
        """Perform cloud resource discovery.

        Args:
            request: Discovery request
            use_cache: Whether to use cached results

        Returns:
            Full discovery result with optional IaC correlation

        Raises:
            CloudDiscoveryError: If discovery fails
        """
        if not self._initialized:
            await self.initialize()

        # Check cache
        cache_key = self._get_cache_key(request)
        if use_cache:
            cached = self._get_cached_result(cache_key)
            if cached:
                logger.debug(f"Cache hit for {cache_key}")
                cached.cache_hit = True
                return cached

        # Perform discovery
        try:
            discovery_result = await self._discover_resources(request)
        except Exception as e:
            logger.error(f"Discovery failed: {e}", exc_info=True)
            raise CloudDiscoveryError(f"Discovery failed: {e}") from e

        # Perform IaC correlation if requested
        correlation_result: CorrelationResult | None = None
        if request.include_iac_correlation and request.repository_path:
            try:
                correlation_result = await self._correlate_iac(
                    request, discovery_result
                )
            except Exception as e:
                logger.warning(f"IaC correlation failed: {e}")
                # Don't fail the whole request for correlation failure

        result = FullDiscoveryResult(
            discovery=discovery_result,
            correlation=correlation_result,
            providers_used=[request.provider],
        )

        # Cache the result
        self._cache_result(cache_key, result)

        return result

    async def _discover_resources(self, request: DiscoveryRequest) -> DiscoveryResult:
        """Perform provider-specific discovery.

        Args:
            request: Discovery request

        Returns:
            Discovery result
        """
        if request.provider == CloudProvider.AWS:
            return await self.aws_provider.discover(
                account_id=request.account_id,
                regions=request.regions or [self.region],
                services=request.services if request.services else None,
                timeout_seconds=request.timeout_seconds,
                tags_filter=request.tags_filter if request.tags_filter else None,
            )
        elif request.provider == CloudProvider.AZURE:
            # Azure provider not yet implemented
            raise ProviderError(
                "Azure discovery not yet implemented",
                provider="azure",
            )
        else:
            raise ProviderError(
                f"Unsupported provider: {request.provider.value}",
                provider=request.provider.value,
            )

    async def _correlate_iac(
        self,
        request: DiscoveryRequest,
        discovery_result: DiscoveryResult,
    ) -> CorrelationResult:
        """Correlate discovery results with IaC.

        Args:
            request: Discovery request
            discovery_result: Discovery results

        Returns:
            Correlation result
        """
        if not request.repository_path:
            raise CorrelationError(
                "Repository path required for IaC correlation",
                repository_id=request.account_id,
            )

        # Parse IaC from repository
        iac_resources = await self.iac_correlator.parse_repository(
            repo_path=Path(request.repository_path)
        )

        # Correlate with discovered resources
        return await self.iac_correlator.correlate(
            repository_id=request.repository_path,
            iac_resources=iac_resources,
            discovery_result=discovery_result,
            stack_name=request.stack_name,
        )

    def _get_cache_key(self, request: DiscoveryRequest) -> str:
        """Generate cache key for request.

        Args:
            request: Discovery request

        Returns:
            Cache key string
        """
        regions = ",".join(sorted(request.regions)) if request.regions else "default"
        services = ",".join(sorted(request.services)) if request.services else "all"
        return f"{request.provider.value}:{request.account_id}:{regions}:{services}"

    def _get_cached_result(self, cache_key: str) -> FullDiscoveryResult | None:
        """Get result from cache if valid.

        Args:
            cache_key: Cache key

        Returns:
            Cached result or None
        """
        if cache_key not in self._cache:
            return None

        result, cached_at = self._cache[cache_key]
        if datetime.now(timezone.utc) - cached_at > self.cache_ttl:
            del self._cache[cache_key]
            return None

        return result

    def _cache_result(self, cache_key: str, result: FullDiscoveryResult) -> None:
        """Cache a discovery result.

        Args:
            cache_key: Cache key
            result: Result to cache
        """
        self._cache[cache_key] = (result, datetime.now(timezone.utc))

    def clear_cache(self) -> int:
        """Clear all cached results.

        Returns:
            Number of entries cleared
        """
        count = len(self._cache)
        self._cache.clear()
        return count

    def get_circuit_breaker_status(self) -> dict[str, Any]:
        """Get status of all circuit breakers.

        Returns:
            Dict with circuit breaker states
        """
        registry = get_circuit_breaker_registry()
        return {
            "breakers": registry.get_all_states(),
            "open_circuits": registry.get_open_circuits(),
        }

    async def validate_credentials(
        self, provider: CloudProvider, account_id: str
    ) -> bool:
        """Validate cloud credentials.

        Args:
            provider: Cloud provider
            account_id: Account ID

        Returns:
            True if credentials are valid
        """
        if not self.credential_proxy:
            logger.warning("No credential proxy configured")
            return False

        return await self.credential_proxy.validate_credentials(provider, account_id)

    async def list_configured_accounts(
        self, provider: CloudProvider | None = None
    ) -> list[dict[str, Any]]:
        """List configured cloud accounts.

        Args:
            provider: Optional filter by provider

        Returns:
            List of account configurations
        """
        if not self.credential_proxy:
            return []

        configs = await self.credential_proxy.list_configured_accounts(provider)
        return [
            {
                "credential_id": c.credential_id,
                "provider": c.provider.value,
                "account_id": c.account_id,
                "description": c.description,
                "enabled": c.enabled,
                "needs_rotation": c.needs_rotation,
            }
            for c in configs
        ]


def create_cloud_discovery_service(
    secrets_service: Any | None = None,
    use_mock: bool = False,
) -> CloudDiscoveryService:
    """Factory function to create CloudDiscoveryService.

    Args:
        secrets_service: Optional SecretsService instance
        use_mock: Use mock mode for testing

    Returns:
        Configured CloudDiscoveryService instance
    """
    return CloudDiscoveryService(
        secrets_service=secrets_service,
        organization_id=os.environ.get("ORGANIZATION_ID", ""),
        region=os.environ.get("AWS_REGION", "us-east-1"),
        use_mock=use_mock,
    )
