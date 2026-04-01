"""
Project Aura - A2A Agent Registry

Implements ADR-028 Phase 6: Agent Discovery and Registration

This module provides the registry for A2A-compatible agents, enabling:
- Registration of external agents
- Agent discovery and search
- Health monitoring of registered agents
- Capability matching for task routing

IMPORTANT: This registry is ONLY available in ENTERPRISE mode.
Defense/GovCloud deployments do not support external agent registration.

Usage:
    >>> from src.services.a2a_agent_registry import A2AAgentRegistry
    >>> registry = A2AAgentRegistry()
    >>> await registry.register_agent(agent_card)
    >>> agents = await registry.search_agents(capability="generate_patch")
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.config import (
    IntegrationConfig,
    get_integration_config,
    require_enterprise_mode,
)
from src.services.a2a_gateway import AgentCapability, AgentCard

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class AgentStatus(Enum):
    """Status of a registered agent."""

    ACTIVE = "active"  # Agent is healthy and accepting tasks
    DEGRADED = "degraded"  # Agent responding slowly or with errors
    INACTIVE = "inactive"  # Agent not responding
    SUSPENDED = "suspended"  # Manually suspended by admin
    PENDING = "pending"  # Registration pending verification


class AgentTrustLevel(Enum):
    """Trust level for external agents."""

    VERIFIED = "verified"  # Verified by Aura team
    TRUSTED = "trusted"  # From trusted provider
    STANDARD = "standard"  # Standard registration
    UNTRUSTED = "untrusted"  # Unverified, limited capabilities


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class RegisteredAgent:
    """
    A registered external agent in the A2A registry.

    Extends AgentCard with registration metadata, health status,
    and usage statistics.
    """

    # Agent card (from A2A spec)
    agent_card: AgentCard

    # Registration metadata
    registration_id: str = ""
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    registered_by: str = "system"

    # Status
    status: AgentStatus = AgentStatus.PENDING
    trust_level: AgentTrustLevel = AgentTrustLevel.STANDARD

    # Health monitoring
    last_health_check: datetime | None = None
    health_check_failures: int = 0
    average_latency_ms: float = 0.0

    # Usage statistics
    total_tasks_sent: int = 0
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0

    # Rate limiting
    rate_limit_per_minute: int = 100
    current_minute_requests: int = 0
    last_rate_reset: float = field(default_factory=time.time)

    # Tags for filtering
    tags: list[str] = field(default_factory=list)

    @property
    def agent_id(self) -> str:
        """Get the agent ID from the card."""
        return self.agent_card.agent_id

    @property
    def endpoint(self) -> str:
        """Get the agent endpoint from the card."""
        return self.agent_card.endpoint

    @property
    def capabilities(self) -> list[AgentCapability]:
        """Get capabilities from the card."""
        return self.agent_card.capabilities

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.total_tasks_completed + self.total_tasks_failed
        if total == 0:
            return 1.0
        return self.total_tasks_completed / total

    @property
    def is_healthy(self) -> bool:
        """Check if agent is healthy."""
        return self.status == AgentStatus.ACTIVE and self.health_check_failures < 3

    def is_rate_limited(self) -> bool:
        """Check if agent is currently rate limited."""
        current_time = time.time()
        if current_time - self.last_rate_reset >= 60:
            self.current_minute_requests = 0
            self.last_rate_reset = current_time
        return self.current_minute_requests >= self.rate_limit_per_minute

    def record_request(self) -> bool:
        """
        Record a request for rate limiting.

        Returns True if request is allowed, False if rate limited.
        """
        if self.is_rate_limited():
            return False
        current_time = time.time()
        if current_time - self.last_rate_reset >= 60:
            self.current_minute_requests = 0
            self.last_rate_reset = current_time
        self.current_minute_requests += 1
        return True

    def record_task_completion(self, success: bool, latency_ms: float) -> None:
        """Record task completion for statistics."""
        self.total_tasks_sent += 1
        if success:
            self.total_tasks_completed += 1
        else:
            self.total_tasks_failed += 1

        # Update rolling average latency
        total = self.total_tasks_completed + self.total_tasks_failed
        self.average_latency_ms = (
            self.average_latency_ms * (total - 1) + latency_ms
        ) / total

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON format."""
        return {
            "registration_id": self.registration_id,
            "agent": self.agent_card.to_dict(),
            "status": self.status.value,
            "trust_level": self.trust_level.value,
            "registered_at": self.registered_at.isoformat(),
            "last_health_check": (
                self.last_health_check.isoformat() if self.last_health_check else None
            ),
            "health_check_failures": self.health_check_failures,
            "average_latency_ms": self.average_latency_ms,
            "success_rate": self.success_rate,
            "total_tasks_sent": self.total_tasks_sent,
            "tags": self.tags,
        }


@dataclass
class AgentSearchCriteria:
    """Criteria for searching agents in the registry."""

    capability_name: str | None = None
    provider: str | None = None
    status: AgentStatus | None = None
    trust_level: AgentTrustLevel | None = None
    min_success_rate: float = 0.0
    max_latency_ms: float | None = None
    tags: list[str] = field(default_factory=list)
    limit: int = 10
    offset: int = 0


# =============================================================================
# Agent Registry
# =============================================================================


class A2AAgentRegistry:
    """
    Registry for A2A-compatible agents.

    This registry handles:
    - Agent registration and verification
    - Agent discovery and capability matching
    - Health monitoring and status tracking
    - Usage statistics and rate limiting

    SECURITY: Only available in ENTERPRISE mode. Defense deployments
    do not support external agent registration.
    """

    def __init__(
        self,
        config: IntegrationConfig | None = None,
        health_check_interval: float = 60.0,
    ):
        """
        Initialize A2A Agent Registry.

        Args:
            config: Integration configuration. If None, loads from environment.
            health_check_interval: Interval for health checks in seconds.
        """
        self._config = config or get_integration_config()

        # Validate we're in enterprise mode
        if self._config.is_defense_mode:
            raise RuntimeError(
                "A2AAgentRegistry cannot be instantiated in DEFENSE mode. "
                "External agent registration is not available for air-gapped deployments."
            )

        # Registry storage (in production, use DynamoDB)
        self._agents: dict[str, RegisteredAgent] = {}

        # Capability index for fast lookup
        self._capability_index: dict[str, set[str]] = {}  # capability -> agent_ids

        # Provider index
        self._provider_index: dict[str, set[str]] = {}  # provider -> agent_ids

        # Health check configuration
        self._health_check_interval = health_check_interval
        self._health_check_task: asyncio.Task | None = None

        # Trusted providers (agents from these providers get higher trust)
        self._trusted_providers = {
            "microsoft",
            "google",
            "anthropic",
            "langchain",
            "aenealabs",
        }

        # Metrics
        self._total_registrations = 0
        self._total_searches = 0

        logger.info(
            f"A2AAgentRegistry initialized: health_check_interval={health_check_interval}s"
        )

    # -------------------------------------------------------------------------
    # Agent Registration
    # -------------------------------------------------------------------------

    @require_enterprise_mode
    async def register_agent(
        self,
        agent_card: AgentCard,
        registered_by: str = "api",
        tags: list[str] | None = None,
        verify: bool = True,
    ) -> RegisteredAgent:
        """
        Register a new external agent.

        Args:
            agent_card: The agent's A2A Agent Card
            registered_by: User/system that registered the agent
            tags: Tags for filtering
            verify: Whether to verify the agent endpoint

        Returns:
            RegisteredAgent with registration details
        """
        # Check if already registered
        if agent_card.agent_id in self._agents:
            existing = self._agents[agent_card.agent_id]
            logger.info(
                f"Agent already registered: {agent_card.agent_id}, " f"updating card"
            )
            existing.agent_card = agent_card
            existing.status = AgentStatus.PENDING if verify else AgentStatus.ACTIVE
            return existing

        # Determine trust level
        trust_level = self._determine_trust_level(agent_card)

        # Create registration
        registration = RegisteredAgent(
            agent_card=agent_card,
            registration_id=f"reg-{agent_card.agent_id}",
            registered_by=registered_by,
            trust_level=trust_level,
            status=AgentStatus.PENDING if verify else AgentStatus.ACTIVE,
            tags=tags or [],
        )

        # Store in registry
        self._agents[agent_card.agent_id] = registration

        # Update indexes
        self._update_indexes(registration)

        self._total_registrations += 1

        logger.info(
            f"Agent registered: agent_id={agent_card.agent_id}, "
            f"trust_level={trust_level.value}, status={registration.status.value}"
        )

        # Verify endpoint if requested
        if verify:
            asyncio.create_task(self._verify_agent(registration))

        return registration

    @require_enterprise_mode
    async def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an agent.

        Args:
            agent_id: The agent to unregister

        Returns:
            True if agent was unregistered, False if not found
        """
        if agent_id not in self._agents:
            return False

        registration = self._agents[agent_id]

        # Remove from indexes
        self._remove_from_indexes(registration)

        # Remove from registry
        del self._agents[agent_id]

        logger.info(f"Agent unregistered: agent_id={agent_id}")
        return True

    @require_enterprise_mode
    async def update_agent_status(
        self, agent_id: str, status: AgentStatus, reason: str = ""
    ) -> RegisteredAgent | None:
        """
        Update an agent's status.

        Args:
            agent_id: The agent to update
            status: New status
            reason: Reason for status change

        Returns:
            Updated registration, or None if not found
        """
        if agent_id not in self._agents:
            return None

        registration = self._agents[agent_id]
        old_status = registration.status
        registration.status = status

        logger.info(
            f"Agent status updated: agent_id={agent_id}, "
            f"{old_status.value} -> {status.value}, reason={reason}"
        )

        return registration

    def _determine_trust_level(self, agent_card: AgentCard) -> AgentTrustLevel:
        """Determine trust level based on provider."""
        provider = agent_card.provider.lower()

        if provider == "aenealabs":
            return AgentTrustLevel.VERIFIED
        elif provider in self._trusted_providers:
            return AgentTrustLevel.TRUSTED
        else:
            return AgentTrustLevel.STANDARD

    def _update_indexes(self, registration: RegisteredAgent) -> None:
        """Update search indexes for an agent."""
        agent_id = registration.agent_id

        # Update capability index
        for capability in registration.capabilities:
            if capability.name not in self._capability_index:
                self._capability_index[capability.name] = set()
            self._capability_index[capability.name].add(agent_id)

        # Update provider index
        provider = registration.agent_card.provider
        if provider not in self._provider_index:
            self._provider_index[provider] = set()
        self._provider_index[provider].add(agent_id)

    def _remove_from_indexes(self, registration: RegisteredAgent) -> None:
        """Remove an agent from search indexes."""
        agent_id = registration.agent_id

        # Remove from capability index
        for capability in registration.capabilities:
            if capability.name in self._capability_index:
                self._capability_index[capability.name].discard(agent_id)

        # Remove from provider index
        provider = registration.agent_card.provider
        if provider in self._provider_index:
            self._provider_index[provider].discard(agent_id)

    # -------------------------------------------------------------------------
    # Agent Discovery
    # -------------------------------------------------------------------------

    @require_enterprise_mode
    async def get_agent(self, agent_id: str) -> RegisteredAgent | None:
        """
        Get a registered agent by ID.

        Args:
            agent_id: The agent identifier

        Returns:
            RegisteredAgent if found, None otherwise
        """
        return self._agents.get(agent_id)

    @require_enterprise_mode
    async def list_agents(
        self,
        status: AgentStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RegisteredAgent]:
        """
        List registered agents.

        Args:
            status: Filter by status (optional)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of registered agents
        """
        agents = list(self._agents.values())

        if status:
            agents = [a for a in agents if a.status == status]

        return agents[offset : offset + limit]

    @require_enterprise_mode
    async def search_agents(
        self, criteria: AgentSearchCriteria
    ) -> list[RegisteredAgent]:
        """
        Search for agents matching criteria.

        Args:
            criteria: Search criteria

        Returns:
            List of matching agents, sorted by relevance
        """
        self._total_searches += 1

        # Start with all agents or capability-filtered subset
        if criteria.capability_name:
            agent_ids = self._capability_index.get(criteria.capability_name, set())
            candidates = [self._agents[aid] for aid in agent_ids if aid in self._agents]
        else:
            candidates = list(self._agents.values())

        # Apply filters
        results = []
        for agent in candidates:
            if not self._matches_criteria(agent, criteria):
                continue
            results.append(agent)

        # Sort by relevance (health, success rate, latency)
        results.sort(
            key=lambda a: (
                a.is_healthy,  # Healthy first
                a.success_rate,  # Higher success rate
                -a.average_latency_ms,  # Lower latency
            ),
            reverse=True,
        )

        # Apply pagination
        return results[criteria.offset : criteria.offset + criteria.limit]

    @require_enterprise_mode
    async def find_agents_for_capability(
        self, capability_name: str, min_success_rate: float = 0.8
    ) -> list[RegisteredAgent]:
        """
        Find healthy agents that support a specific capability.

        Args:
            capability_name: The capability to find
            min_success_rate: Minimum required success rate

        Returns:
            List of matching healthy agents
        """
        result: list[RegisteredAgent] = await self.search_agents(
            AgentSearchCriteria(
                capability_name=capability_name,
                status=AgentStatus.ACTIVE,
                min_success_rate=min_success_rate,
            )
        )
        return result

    def _matches_criteria(
        self, agent: RegisteredAgent, criteria: AgentSearchCriteria
    ) -> bool:
        """Check if agent matches search criteria."""
        # Status filter
        if criteria.status and agent.status != criteria.status:
            return False

        # Provider filter
        if criteria.provider:
            if agent.agent_card.provider.lower() != criteria.provider.lower():
                return False

        # Trust level filter
        if criteria.trust_level and agent.trust_level != criteria.trust_level:
            return False

        # Success rate filter
        if agent.success_rate < criteria.min_success_rate:
            return False

        # Latency filter
        if criteria.max_latency_ms:
            if agent.average_latency_ms > criteria.max_latency_ms:
                return False

        # Tags filter (must have all specified tags)
        if criteria.tags:
            if not all(tag in agent.tags for tag in criteria.tags):
                return False

        return True

    # -------------------------------------------------------------------------
    # Health Monitoring
    # -------------------------------------------------------------------------

    async def start_health_monitoring(self) -> None:
        """Start background health check task."""
        if self._health_check_task is not None:
            logger.warning("Health monitoring already running")
            return

        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Health monitoring started")

    async def stop_health_monitoring(self) -> None:
        """Stop background health check task."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            logger.info("Health monitoring stopped")

    async def _health_check_loop(self) -> None:
        """Background loop for health checks."""
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")

    async def _perform_health_checks(self) -> None:
        """Perform health checks on all active agents."""
        active_agents = [
            a for a in self._agents.values() if a.status != AgentStatus.SUSPENDED
        ]

        for agent in active_agents:
            try:
                is_healthy = await self._check_agent_health(agent)

                if is_healthy:
                    agent.health_check_failures = 0
                    if agent.status != AgentStatus.ACTIVE:
                        agent.status = AgentStatus.ACTIVE
                        logger.info(f"Agent recovered: {agent.agent_id}")
                else:
                    agent.health_check_failures += 1

                    if agent.health_check_failures >= 3:
                        agent.status = AgentStatus.INACTIVE
                        logger.warning(
                            f"Agent marked inactive: {agent.agent_id}, "
                            f"failures={agent.health_check_failures}"
                        )
                    elif agent.health_check_failures >= 1:
                        agent.status = AgentStatus.DEGRADED

                agent.last_health_check = datetime.now(timezone.utc)

            except Exception as e:
                logger.error(f"Health check failed for {agent.agent_id}: {e}")
                agent.health_check_failures += 1

    async def _check_agent_health(self, agent: RegisteredAgent) -> bool:
        """
        Check if an agent is healthy.

        Args:
            agent: The agent to check

        Returns:
            True if healthy, False otherwise
        """
        # In production, ping the agent's health endpoint:
        # async with aiohttp.ClientSession() as session:
        #     try:
        #         async with session.get(
        #             f"{agent.endpoint}/health",
        #             timeout=aiohttp.ClientTimeout(total=5),
        #         ) as response:
        #             return response.status == 200
        #     except Exception:
        #         return False

        # Development mock - assume healthy
        await asyncio.sleep(0.01)
        return True

    async def _verify_agent(self, agent: RegisteredAgent) -> None:
        """
        Verify a newly registered agent.

        Args:
            agent: The agent to verify
        """
        try:
            # Verify endpoint is reachable
            is_healthy = await self._check_agent_health(agent)

            if is_healthy:
                agent.status = AgentStatus.ACTIVE
                logger.info(f"Agent verified: {agent.agent_id}")
            else:
                agent.status = AgentStatus.INACTIVE
                logger.warning(f"Agent verification failed: {agent.agent_id}")

        except Exception as e:
            logger.error(f"Agent verification error for {agent.agent_id}: {e}")
            agent.status = AgentStatus.INACTIVE

    # -------------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------------

    def get_metrics(self) -> dict[str, Any]:
        """Get registry metrics for monitoring."""
        status_counts = {}
        for status in AgentStatus:
            status_counts[status.value] = len(
                [a for a in self._agents.values() if a.status == status]
            )

        trust_counts = {}
        for trust in AgentTrustLevel:
            trust_counts[trust.value] = len(
                [a for a in self._agents.values() if a.trust_level == trust]
            )

        return {
            "total_registered_agents": len(self._agents),
            "total_registrations": self._total_registrations,
            "total_searches": self._total_searches,
            "agents_by_status": status_counts,
            "agents_by_trust": trust_counts,
            "indexed_capabilities": len(self._capability_index),
            "indexed_providers": len(self._provider_index),
        }

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    @require_enterprise_mode
    async def import_agents_from_discovery(
        self, discovery_endpoint: str
    ) -> list[RegisteredAgent]:
        """
        Import agents from a discovery endpoint.

        Args:
            discovery_endpoint: URL of the discovery service

        Returns:
            List of newly registered agents
        """
        # In production, fetch from discovery service:
        # async with aiohttp.ClientSession() as session:
        #     async with session.get(discovery_endpoint) as response:
        #         data = await response.json()
        #         agents = data.get("agents", [])

        # Development mock
        logger.info(f"Importing agents from: {discovery_endpoint}")
        await asyncio.sleep(0.1)

        return []

    @require_enterprise_mode
    async def export_registry(self) -> dict[str, Any]:
        """
        Export the full registry for backup/migration.

        Returns:
            Dict with all registry data
        """
        return {
            "agents": [a.to_dict() for a in self._agents.values()],
            "metrics": self.get_metrics(),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }


# =============================================================================
# Exceptions
# =============================================================================


class RegistryError(Exception):
    """Base exception for registry operations."""


class AgentNotFoundError(RegistryError):
    """Agent not found in registry."""


class AgentAlreadyExistsError(RegistryError):
    """Agent already registered."""


class RegistrationError(RegistryError):
    """Error during agent registration."""
