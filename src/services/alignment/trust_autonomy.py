"""
Trust-Based Autonomy Service (ADR-052 Phase 2).

Dynamic permission adjustment based on agent trust scores.
Integrates trust calculation with action authorization to implement
earned autonomy.

Key Concepts:
- Agents earn autonomy through demonstrated reliability
- Autonomy level determines what actions can be executed
- Action class determines required autonomy level
- Human overrides always take precedence

Reference: ADR-052 AI Alignment Principles & Human-Machine Collaboration
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from src.services.alignment.reversibility import ActionClass, ActionMetadata
from src.services.alignment.trust_calculator import AutonomyLevel, TrustScoreCalculator

logger = logging.getLogger(__name__)


class AuthorizationDecision(Enum):
    """Authorization decision types."""

    APPROVED = "approved"  # Can proceed
    REQUIRES_REVIEW = "requires_review"  # Needs human review first
    REQUIRES_APPROVAL = "requires_approval"  # Needs explicit human approval
    DENIED = "denied"  # Not allowed at current autonomy level
    ESCALATED = "escalated"  # Escalated to higher authority


@dataclass
class PermissionScope:
    """Defines the scope of permissions for an autonomy level."""

    level: AutonomyLevel
    allowed_action_classes: list[ActionClass]
    max_impact_scope: str  # "local", "service", "system", "external"
    requires_review_for: list[ActionClass]
    can_affect_production: bool
    can_affect_external: bool
    max_concurrent_actions: int
    rate_limit_per_hour: int | None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "level": self.level.name,
            "allowed_action_classes": [ac.value for ac in self.allowed_action_classes],
            "max_impact_scope": self.max_impact_scope,
            "requires_review_for": [ac.value for ac in self.requires_review_for],
            "can_affect_production": self.can_affect_production,
            "can_affect_external": self.can_affect_external,
            "max_concurrent_actions": self.max_concurrent_actions,
            "rate_limit_per_hour": self.rate_limit_per_hour,
        }


@dataclass
class AuthorizationRequest:
    """Request for action authorization."""

    request_id: str
    agent_id: str
    action_metadata: ActionMetadata
    action_class: ActionClass
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: dict[str, Any] = field(default_factory=dict)
    override_requested: bool = False
    override_reason: str | None = None


@dataclass
class AuthorizationResult:
    """Result of an authorization check."""

    request_id: str
    decision: AuthorizationDecision
    agent_id: str
    agent_autonomy_level: AutonomyLevel
    agent_trust_score: float
    action_class: ActionClass
    reason: str
    conditions: list[str] = field(default_factory=list)
    escalation_path: str | None = None
    expires_at: datetime | None = None
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_approved(self) -> bool:
        """Check if the request was approved."""
        return self.decision == AuthorizationDecision.APPROVED

    @property
    def requires_human(self) -> bool:
        """Check if human involvement is required."""
        return self.decision in [
            AuthorizationDecision.REQUIRES_REVIEW,
            AuthorizationDecision.REQUIRES_APPROVAL,
            AuthorizationDecision.ESCALATED,
        ]

    def to_dict(self) -> dict:
        """Convert to dictionary for API/storage."""
        return {
            "request_id": self.request_id,
            "decision": self.decision.value,
            "agent_id": self.agent_id,
            "agent_autonomy_level": self.agent_autonomy_level.name,
            "agent_trust_score": self.agent_trust_score,
            "action_class": self.action_class.value,
            "reason": self.reason,
            "conditions": self.conditions,
            "escalation_path": self.escalation_path,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "decided_at": self.decided_at.isoformat(),
            "is_approved": self.is_approved,
            "requires_human": self.requires_human,
        }


@dataclass
class OverrideRecord:
    """Record of a human override of autonomy level."""

    agent_id: str
    override_type: str  # "promotion", "demotion", "temporary_grant", "revocation"
    old_level: AutonomyLevel
    new_level: AutonomyLevel
    reason: str
    overridden_by: str  # User ID who made the override
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    is_active: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "override_type": self.override_type,
            "old_level": self.old_level.name,
            "new_level": self.new_level.name,
            "reason": self.reason,
            "overridden_by": self.overridden_by,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
        }


class TrustBasedAutonomy:
    """
    Dynamic permission adjustment based on agent trust scores.

    Integrates with TrustScoreCalculator to authorize actions based on
    earned autonomy levels.

    Usage:
        trust_calc = TrustScoreCalculator()
        autonomy = TrustBasedAutonomy(trust_calc)

        # Check if an action is authorized
        result = autonomy.authorize_action(request)
        if result.is_approved:
            # Proceed with action
            pass
        elif result.requires_human:
            # Request human approval
            pass
        else:
            # Action denied
            pass
    """

    # Default permission scopes for each autonomy level
    DEFAULT_SCOPES = {
        AutonomyLevel.OBSERVE: PermissionScope(
            level=AutonomyLevel.OBSERVE,
            allowed_action_classes=[],  # Can't execute any actions
            max_impact_scope="local",
            requires_review_for=[
                ActionClass.FULLY_REVERSIBLE,
                ActionClass.PARTIALLY_REVERSIBLE,
                ActionClass.IRREVERSIBLE,
            ],
            can_affect_production=False,
            can_affect_external=False,
            max_concurrent_actions=0,
            rate_limit_per_hour=None,
        ),
        AutonomyLevel.RECOMMEND: PermissionScope(
            level=AutonomyLevel.RECOMMEND,
            allowed_action_classes=[],  # Recommendations only, no execution
            max_impact_scope="local",
            requires_review_for=[
                ActionClass.FULLY_REVERSIBLE,
                ActionClass.PARTIALLY_REVERSIBLE,
                ActionClass.IRREVERSIBLE,
            ],
            can_affect_production=False,
            can_affect_external=False,
            max_concurrent_actions=0,
            rate_limit_per_hour=100,  # Rate limit recommendations
        ),
        AutonomyLevel.EXECUTE_REVIEW: PermissionScope(
            level=AutonomyLevel.EXECUTE_REVIEW,
            allowed_action_classes=[ActionClass.FULLY_REVERSIBLE],
            max_impact_scope="service",
            requires_review_for=[
                ActionClass.PARTIALLY_REVERSIBLE,
                ActionClass.IRREVERSIBLE,
            ],
            can_affect_production=False,
            can_affect_external=False,
            max_concurrent_actions=5,
            rate_limit_per_hour=50,
        ),
        AutonomyLevel.AUTONOMOUS: PermissionScope(
            level=AutonomyLevel.AUTONOMOUS,
            allowed_action_classes=[
                ActionClass.FULLY_REVERSIBLE,
                ActionClass.PARTIALLY_REVERSIBLE,
            ],
            max_impact_scope="system",
            requires_review_for=[ActionClass.IRREVERSIBLE],
            can_affect_production=True,  # With review
            can_affect_external=False,  # Never without human
            max_concurrent_actions=10,
            rate_limit_per_hour=100,
        ),
    }

    def __init__(
        self,
        trust_calculator: TrustScoreCalculator | None = None,
        custom_scopes: dict[AutonomyLevel, PermissionScope] | None = None,
        authorization_ttl_minutes: int = 30,
        enable_rate_limiting: bool = True,
    ):
        """
        Initialize the trust-based autonomy service.

        Args:
            trust_calculator: TrustScoreCalculator instance
            custom_scopes: Custom permission scopes (overrides defaults)
            authorization_ttl_minutes: How long an authorization is valid
            enable_rate_limiting: Whether to enforce rate limits
        """
        self.trust_calculator = trust_calculator or TrustScoreCalculator()
        self.scopes = {**self.DEFAULT_SCOPES}
        if custom_scopes:
            self.scopes.update(custom_scopes)
        self.authorization_ttl = timedelta(minutes=authorization_ttl_minutes)
        self.enable_rate_limiting = enable_rate_limiting

        # Thread-safe storage
        self._lock = threading.RLock()
        self._overrides: dict[str, OverrideRecord] = {}
        self._authorization_history: list[AuthorizationResult] = []
        self._action_counts: dict[str, list[datetime]] = {}  # For rate limiting

    def authorize_action(
        self,
        request: AuthorizationRequest,
    ) -> AuthorizationResult:
        """
        Check if an action is authorized for an agent.

        Args:
            request: Authorization request

        Returns:
            AuthorizationResult with decision and details
        """
        with self._lock:
            # Get agent's trust info
            record = self.trust_calculator.get_or_create_agent(request.agent_id)
            trust_score = record.trust_score
            base_level = record.effective_level

            # Check for active overrides
            effective_level = self._get_effective_level(request.agent_id, base_level)

            # Get permission scope for this level
            scope = self.scopes[effective_level]

            # Check rate limiting
            if self.enable_rate_limiting:
                rate_result = self._check_rate_limit(request.agent_id, scope)
                if rate_result:
                    return rate_result

            # Determine authorization decision
            decision, reason, conditions = self._evaluate_authorization(
                request, effective_level, scope
            )

            # Set expiration if approved
            expires_at = None
            if decision == AuthorizationDecision.APPROVED:
                expires_at = datetime.now(timezone.utc) + self.authorization_ttl
                # Record action for rate limiting
                self._record_action(request.agent_id)

            result = AuthorizationResult(
                request_id=request.request_id,
                decision=decision,
                agent_id=request.agent_id,
                agent_autonomy_level=effective_level,
                agent_trust_score=trust_score,
                action_class=request.action_class,
                reason=reason,
                conditions=conditions,
                escalation_path=self._get_escalation_path(effective_level),
                expires_at=expires_at,
            )

            # Store in history
            self._authorization_history.append(result)
            if len(self._authorization_history) > 1000:
                self._authorization_history = self._authorization_history[-1000:]

            return result

    def _get_effective_level(
        self, agent_id: str, base_level: AutonomyLevel
    ) -> AutonomyLevel:
        """Get effective autonomy level considering overrides."""
        if agent_id in self._overrides:
            override = self._overrides[agent_id]
            if override.is_active:
                # Check if expired
                if override.expires_at and override.expires_at < datetime.now(
                    timezone.utc
                ):
                    override.is_active = False
                else:
                    return override.new_level
        return base_level

    def _evaluate_authorization(
        self,
        request: AuthorizationRequest,
        level: AutonomyLevel,
        scope: PermissionScope,
    ) -> tuple[AuthorizationDecision, str, list[str]]:
        """Evaluate authorization based on request and scope."""
        conditions: list[str] = []
        action_class = request.action_class
        metadata = request.action_metadata

        # Class C (IRREVERSIBLE) always requires human approval
        if action_class == ActionClass.IRREVERSIBLE:
            return (
                AuthorizationDecision.REQUIRES_APPROVAL,
                "Irreversible actions always require explicit human approval",
                ["Submit for human approval before execution"],
            )

        # Check if action class is in requires_review
        if action_class in scope.requires_review_for:
            return (
                AuthorizationDecision.REQUIRES_REVIEW,
                f"Action class {action_class.value} requires human review at {level.name} level",
                ["Action will be executed after human review"],
            )

        # Check if action class is allowed
        if action_class not in scope.allowed_action_classes:
            return (
                AuthorizationDecision.DENIED,
                f"Action class {action_class.value} not allowed at {level.name} level",
                [f"Required level: at least {action_class.min_autonomy_level}"],
            )

        # Check production restrictions
        if metadata.is_production and not scope.can_affect_production:
            return (
                AuthorizationDecision.REQUIRES_APPROVAL,
                "Production actions require human approval at current autonomy level",
                ["Request production access approval"],
            )

        # Check external system restrictions
        if metadata.affects_external_system and not scope.can_affect_external:
            return (
                AuthorizationDecision.REQUIRES_APPROVAL,
                "External system actions require human approval",
                ["External system access requires explicit approval"],
            )

        # Check impact scope
        scope_hierarchy = ["local", "service", "system", "external"]
        if scope_hierarchy.index(
            metadata.estimated_impact_scope
        ) > scope_hierarchy.index(scope.max_impact_scope):
            return (
                AuthorizationDecision.REQUIRES_REVIEW,
                f"Impact scope ({metadata.estimated_impact_scope}) exceeds allowed scope ({scope.max_impact_scope})",
                ["Review impact before proceeding"],
            )

        # All checks passed
        conditions.append("Action authorized within policy bounds")
        if metadata.is_production:
            conditions.append("Production change - post-execution review required")

        return (
            AuthorizationDecision.APPROVED,
            f"Action authorized for {level.name} level agent",
            conditions,
        )

    def _check_rate_limit(
        self, agent_id: str, scope: PermissionScope
    ) -> AuthorizationResult | None:
        """Check if agent has exceeded rate limit."""
        if scope.rate_limit_per_hour is None:
            return None

        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)

        if agent_id not in self._action_counts:
            self._action_counts[agent_id] = []

        # Clean old entries
        self._action_counts[agent_id] = [
            ts for ts in self._action_counts[agent_id] if ts > hour_ago
        ]

        # Check limit
        if len(self._action_counts[agent_id]) >= scope.rate_limit_per_hour:
            record = self.trust_calculator.get_or_create_agent(agent_id)
            return AuthorizationResult(
                request_id="rate_limited",
                decision=AuthorizationDecision.DENIED,
                agent_id=agent_id,
                agent_autonomy_level=scope.level,
                agent_trust_score=record.trust_score,
                action_class=ActionClass.FULLY_REVERSIBLE,
                reason=f"Rate limit exceeded: {scope.rate_limit_per_hour} actions/hour",
                conditions=["Wait for rate limit reset"],
            )

        return None

    def _record_action(self, agent_id: str) -> None:
        """Record an action for rate limiting."""
        if agent_id not in self._action_counts:
            self._action_counts[agent_id] = []
        self._action_counts[agent_id].append(datetime.now(timezone.utc))

    def _get_escalation_path(self, level: AutonomyLevel) -> str:
        """Get escalation path for actions requiring human involvement."""
        paths = {
            AutonomyLevel.OBSERVE: "team_lead -> security_review",
            AutonomyLevel.RECOMMEND: "team_lead",
            AutonomyLevel.EXECUTE_REVIEW: "peer_review",
            AutonomyLevel.AUTONOMOUS: "security_team",
        }
        return paths[level]

    def grant_temporary_override(
        self,
        agent_id: str,
        new_level: AutonomyLevel,
        reason: str,
        granted_by: str,
        duration_hours: int = 24,
    ) -> OverrideRecord:
        """
        Grant temporary autonomy level override.

        Args:
            agent_id: Agent to grant override
            new_level: New autonomy level
            reason: Reason for override
            granted_by: User granting the override
            duration_hours: How long the override lasts

        Returns:
            OverrideRecord
        """
        with self._lock:
            record = self.trust_calculator.get_or_create_agent(agent_id)
            old_level = record.effective_level

            override = OverrideRecord(
                agent_id=agent_id,
                override_type=(
                    "promotion" if new_level.value > old_level.value else "demotion"
                ),
                old_level=old_level,
                new_level=new_level,
                reason=reason,
                overridden_by=granted_by,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=duration_hours),
            )

            self._overrides[agent_id] = override
            logger.info(
                f"Temporary override granted: {agent_id} "
                f"{old_level.name} -> {new_level.name} for {duration_hours}h"
            )

            return override

    def revoke_override(self, agent_id: str, revoked_by: str) -> bool:
        """
        Revoke an active override.

        Args:
            agent_id: Agent with override
            revoked_by: User revoking the override

        Returns:
            True if override was revoked
        """
        with self._lock:
            if agent_id in self._overrides:
                override = self._overrides[agent_id]
                if override.is_active:
                    override.is_active = False
                    logger.info(f"Override revoked for {agent_id} by {revoked_by}")
                    return True
            return False

    def get_agent_permissions(self, agent_id: str) -> dict[str, Any]:
        """
        Get current permissions for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Permission details
        """
        with self._lock:
            record = self.trust_calculator.get_or_create_agent(agent_id)
            base_level = record.effective_level
            effective_level = self._get_effective_level(agent_id, base_level)
            scope = self.scopes[effective_level]

            # Check for active override
            has_override = (
                agent_id in self._overrides and self._overrides[agent_id].is_active
            )
            override_info = None
            if has_override:
                override = self._overrides[agent_id]
                override_info = override.to_dict()

            return {
                "agent_id": agent_id,
                "trust_score": record.trust_score,
                "base_level": base_level.name,
                "effective_level": effective_level.name,
                "has_override": has_override,
                "override": override_info,
                "permissions": scope.to_dict(),
            }

    def get_authorization_history(
        self,
        agent_id: str | None = None,
        decision: AuthorizationDecision | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get authorization history.

        Args:
            agent_id: Filter by agent
            decision: Filter by decision type
            since: Only include after this time
            limit: Maximum results

        Returns:
            List of authorization records
        """
        with self._lock:
            results = self._authorization_history.copy()

            if agent_id:
                results = [r for r in results if r.agent_id == agent_id]
            if decision:
                results = [r for r in results if r.decision == decision]
            if since:
                results = [r for r in results if r.decided_at >= since]

            # Sort by time, most recent first
            results.sort(key=lambda r: r.decided_at, reverse=True)

            return [r.to_dict() for r in results[:limit]]

    def get_autonomy_stats(self) -> dict[str, Any]:
        """Get overall autonomy statistics."""
        with self._lock:
            history = self._authorization_history

            if not history:
                return {
                    "total_requests": 0,
                    "decisions": {},
                    "by_level": {},
                }

            # Count by decision
            decision_counts: dict[str, int] = {}
            level_counts: dict[str, int] = {}
            for result in history:
                dec = result.decision.value
                decision_counts[dec] = decision_counts.get(dec, 0) + 1
                lvl = result.agent_autonomy_level.name
                level_counts[lvl] = level_counts.get(lvl, 0) + 1

            approval_rate = (
                decision_counts.get("approved", 0) / len(history) if history else 0
            )
            human_required_rate = (
                sum(
                    decision_counts.get(d, 0)
                    for d in ["requires_review", "requires_approval", "escalated"]
                )
                / len(history)
                if history
                else 0
            )

            return {
                "total_requests": len(history),
                "decisions": decision_counts,
                "by_level": level_counts,
                "approval_rate": approval_rate,
                "human_required_rate": human_required_rate,
                "active_overrides": sum(
                    1 for o in self._overrides.values() if o.is_active
                ),
            }

    def clear_history(self) -> None:
        """Clear authorization history (for testing)."""
        with self._lock:
            self._authorization_history.clear()
            self._action_counts.clear()
            self._overrides.clear()
