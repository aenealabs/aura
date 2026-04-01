"""Project Aura - Cedar Policy Engine

Real-time policy enforcement for agent tool calls using natural language
policy definitions with Cedar policy language.

Implements AWS Bedrock AgentCore Policy parity (ADR-030 Phase 1.4):
- Cedar policy language integration
- Natural language → Cedar conversion using LLM
- Real-time tool call interception
- Policy evaluation with audit logging
- Hierarchical policy inheritance

Author: Project Aura Team
Date: 2025-12-11
"""

import asyncio
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class PolicyDecision(Enum):
    """Policy evaluation decision."""

    ALLOW = "allow"
    DENY = "deny"


class PolicyEffect(Enum):
    """Cedar policy effect."""

    PERMIT = "permit"
    FORBID = "forbid"


class PolicyPriority(Enum):
    """Policy priority levels (higher = more important)."""

    SYSTEM = 1000  # System-level, cannot be overridden
    ORGANIZATION = 500  # Organization-wide policies
    TEAM = 250  # Team-level policies
    USER = 100  # User-specific policies
    DEFAULT = 0  # Default fallback policies


@dataclass
class CedarPolicy:
    """A Cedar policy definition."""

    policy_id: str
    policy_name: str
    description: str
    cedar_syntax: str
    natural_language: str | None = None
    effect: PolicyEffect = PolicyEffect.PERMIT
    priority: int = PolicyPriority.DEFAULT.value
    enabled: bool = True
    scope: str = "global"  # global, organization, team, user
    organization_id: str | None = None
    team_id: str | None = None
    user_id: str | None = None
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str | None = None

    def __hash__(self):
        return hash(self.policy_id)


@dataclass
class PolicyEvaluationRequest:
    """Request to evaluate a policy decision."""

    principal: str  # e.g., "Agent::coder-agent"
    action: str  # e.g., "Action::invoke_tool"
    resource: str  # e.g., "Tool::slack_post_message"
    context: dict[str, Any] = field(default_factory=dict)
    organization_id: str | None = None
    team_id: str | None = None
    user_id: str | None = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PolicyEvaluationResult:
    """Result of policy evaluation."""

    decision: PolicyDecision
    request_id: str
    matched_policies: list[str]
    determining_policy: str | None = None
    reasons: list[str] = field(default_factory=list)
    evaluation_time_ms: float = 0.0
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_allowed(self) -> bool:
        return self.decision == PolicyDecision.ALLOW


@dataclass
class PolicyAuditEntry:
    """Audit entry for policy decisions."""

    audit_id: str
    request: PolicyEvaluationRequest
    result: PolicyEvaluationResult
    agent_id: str | None = None
    tool_name: str | None = None
    tool_parameters: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PolicyValidationResult:
    """Result of Cedar policy syntax validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized_syntax: str | None = None


class CedarPolicyEngine:
    """
    Cedar-based policy engine for agent governance.

    Implements AWS AgentCore Policy parity:
    - Natural language policy definition
    - Cedar policy language
    - Real-time tool call interception
    - Audit logging

    Cedar Policy Language Overview:
    - permit/forbid: Allow or deny access
    - principal: Who is making the request (Agent, User)
    - action: What operation is being performed
    - resource: What is being accessed (Tool, Data)
    - when/unless: Conditions for the policy

    Example Cedar Policies:

        // Allow all agents to read public data
        permit(
            principal,
            action == Action::"read",
            resource
        ) when {
            resource.visibility == "public"
        };

        // Forbid agents from accessing PII without consent
        forbid(
            principal,
            action,
            resource
        ) when {
            resource.contains_pii == true &&
            context.user_consent != true
        };

    Example usage:
        engine = CedarPolicyEngine()

        # Create policy from natural language
        policy = await engine.create_policy_from_natural_language(
            "Agents cannot post to Slack without manager approval",
            policy_name="slack-approval-required",
        )

        # Evaluate a request
        result = await engine.evaluate(PolicyEvaluationRequest(
            principal="Agent::coder-agent",
            action="Action::invoke_tool",
            resource="Tool::slack_post_message",
            context={"has_approval": False},
        ))

        # Intercept tool call
        result = engine.intercept_tool_call(
            agent_id="coder-agent",
            tool_name="slack_post_message",
            parameters={"channel": "#general", "message": "Hello"},
        )
    """

    def __init__(
        self,
        dynamodb_client: Any | None = None,
        bedrock_client: Any | None = None,
        policy_table: str | None = None,
        audit_table: str | None = None,
        default_decision: PolicyDecision = PolicyDecision.DENY,
    ):
        """Initialize Cedar Policy Engine.

        Args:
            dynamodb_client: Boto3 DynamoDB client for policy storage
            bedrock_client: Bedrock client for NL→Cedar conversion
            policy_table: DynamoDB table for policies
            audit_table: DynamoDB table for audit logs
            default_decision: Default decision when no policies match
        """
        self.dynamodb = dynamodb_client
        self.bedrock = bedrock_client
        self.policy_table = policy_table or os.getenv(
            "AURA_POLICY_TABLE", "aura-cedar-policies"
        )
        self.audit_table = audit_table or os.getenv(
            "AURA_POLICY_AUDIT_TABLE", "aura-policy-audit"
        )
        self.default_decision = default_decision

        # In-memory policy store (replace with DynamoDB in production)
        self._policies: dict[str, CedarPolicy] = {}
        self._audit_log: list[PolicyAuditEntry] = []

        # Tool call interceptors
        self._interceptors: list[Callable] = []

        # Initialize with system policies
        self._initialize_system_policies()

        logger.info("Initialized CedarPolicyEngine")

    def _initialize_system_policies(self) -> None:
        """Initialize built-in system policies."""
        # Deny all by default (explicit allow required)
        self._policies["system-deny-default"] = CedarPolicy(
            policy_id="system-deny-default",
            policy_name="Default Deny",
            description="Deny all requests by default (explicit allow required)",
            cedar_syntax="forbid(principal, action, resource);",
            effect=PolicyEffect.FORBID,
            priority=PolicyPriority.DEFAULT.value,
            scope="global",
            tags=["system", "default"],
        )

        # Allow read-only operations by default
        self._policies["system-allow-read"] = CedarPolicy(
            policy_id="system-allow-read",
            policy_name="Allow Read Operations",
            description="Allow all read-only operations",
            cedar_syntax="""permit(
    principal,
    action == Action::"read",
    resource
);""",
            effect=PolicyEffect.PERMIT,
            priority=PolicyPriority.SYSTEM.value - 100,
            scope="global",
            tags=["system", "read"],
        )

        # Forbid dangerous operations without HITL
        self._policies["system-hitl-required"] = CedarPolicy(
            policy_id="system-hitl-required",
            policy_name="HITL Required for Dangerous Operations",
            description="Require human approval for production deployments and credential changes",
            cedar_syntax="""forbid(
    principal,
    action,
    resource
) when {
    resource.category in ["production_deployment", "credential_modification", "infrastructure_change"] &&
    context.hitl_approved != true
};""",
            effect=PolicyEffect.FORBID,
            priority=PolicyPriority.SYSTEM.value,
            scope="global",
            tags=["system", "hitl", "safety"],
        )

    # =========================================================================
    # Policy Creation
    # =========================================================================

    async def create_policy_from_natural_language(
        self,
        description: str,
        policy_name: str,
        priority: int = PolicyPriority.ORGANIZATION.value,
        scope: str = "organization",
        organization_id: str | None = None,
        team_id: str | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
    ) -> CedarPolicy:
        """Convert natural language to Cedar policy using LLM.

        Args:
            description: Natural language policy description
            policy_name: Human-readable policy name
            priority: Policy priority level
            scope: Policy scope (global, organization, team, user)
            organization_id: Organization this policy belongs to
            team_id: Team this policy belongs to
            user_id: User this policy belongs to
            tags: Optional tags

        Returns:
            Created CedarPolicy

        Example:
            policy = await engine.create_policy_from_natural_language(
                "Sales agents can only modify customer records in their region",
                policy_name="sales-region-restriction",
            )
        """
        cedar_syntax = await self._translate_to_cedar(description)

        # Validate the generated Cedar
        validation = self._validate_cedar_syntax(cedar_syntax)
        if not validation.valid:
            raise ValueError(f"Generated Cedar policy is invalid: {validation.errors}")

        # Determine effect from Cedar
        effect = (
            PolicyEffect.PERMIT if "permit(" in cedar_syntax else PolicyEffect.FORBID
        )

        policy = CedarPolicy(
            policy_id=str(uuid.uuid4()),
            policy_name=policy_name,
            description=description,
            cedar_syntax=validation.normalized_syntax or cedar_syntax,
            natural_language=description,
            effect=effect,
            priority=priority,
            scope=scope,
            organization_id=organization_id,
            team_id=team_id,
            user_id=user_id,
            tags=tags or [],
        )

        self._policies[policy.policy_id] = policy
        await self._persist_policy(policy)

        logger.info(
            f"Created policy '{policy_name}' from natural language: "
            f"{description[:50]}..."
        )

        return policy

    async def create_policy(
        self,
        policy_name: str,
        cedar_syntax: str,
        description: str | None = None,
        priority: int = PolicyPriority.ORGANIZATION.value,
        scope: str = "organization",
        organization_id: str | None = None,
        tags: list[str] | None = None,
    ) -> CedarPolicy:
        """Create policy from Cedar syntax directly.

        Args:
            policy_name: Human-readable policy name
            cedar_syntax: Cedar policy syntax
            description: Optional description
            priority: Policy priority level
            scope: Policy scope
            organization_id: Organization this policy belongs to
            tags: Optional tags

        Returns:
            Created CedarPolicy
        """
        # Validate Cedar syntax
        validation = self._validate_cedar_syntax(cedar_syntax)
        if not validation.valid:
            raise ValueError(f"Invalid Cedar syntax: {validation.errors}")

        effect = (
            PolicyEffect.PERMIT if "permit(" in cedar_syntax else PolicyEffect.FORBID
        )

        policy = CedarPolicy(
            policy_id=str(uuid.uuid4()),
            policy_name=policy_name,
            description=description or policy_name,
            cedar_syntax=validation.normalized_syntax or cedar_syntax,
            effect=effect,
            priority=priority,
            scope=scope,
            organization_id=organization_id,
            tags=tags or [],
        )

        self._policies[policy.policy_id] = policy
        await self._persist_policy(policy)

        logger.info(f"Created policy '{policy_name}' from Cedar syntax")

        return policy

    async def update_policy(
        self,
        policy_id: str,
        cedar_syntax: str | None = None,
        description: str | None = None,
        enabled: bool | None = None,
        priority: int | None = None,
    ) -> CedarPolicy | None:
        """Update an existing policy.

        Args:
            policy_id: Policy identifier
            cedar_syntax: New Cedar syntax
            description: New description
            enabled: Enable/disable policy
            priority: New priority

        Returns:
            Updated policy or None if not found
        """
        policy = self._policies.get(policy_id)
        if not policy:
            return None

        if cedar_syntax is not None:
            validation = self._validate_cedar_syntax(cedar_syntax)
            if not validation.valid:
                raise ValueError(f"Invalid Cedar syntax: {validation.errors}")
            policy.cedar_syntax = validation.normalized_syntax or cedar_syntax

        if description is not None:
            policy.description = description

        if enabled is not None:
            policy.enabled = enabled

        if priority is not None:
            policy.priority = priority

        policy.updated_at = datetime.now(timezone.utc)

        await self._persist_policy(policy)
        return policy

    async def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy.

        Args:
            policy_id: Policy identifier

        Returns:
            True if deleted, False if not found or protected
        """
        policy = self._policies.get(policy_id)
        if not policy:
            return False

        # Don't allow deletion of system policies
        if "system" in policy.tags:
            logger.warning(f"Cannot delete system policy: {policy_id}")
            return False

        del self._policies[policy_id]
        logger.info(f"Deleted policy: {policy_id}")
        return True

    async def get_policy(self, policy_id: str) -> CedarPolicy | None:
        """Get a policy by ID."""
        return self._policies.get(policy_id)

    async def list_policies(
        self,
        scope: str | None = None,
        organization_id: str | None = None,
        enabled_only: bool = True,
        tags: list[str] | None = None,
    ) -> list[CedarPolicy]:
        """List policies with optional filters.

        Args:
            scope: Filter by scope
            organization_id: Filter by organization
            enabled_only: Only return enabled policies
            tags: Filter by tags (any match)

        Returns:
            List of matching policies
        """
        policies = list(self._policies.values())

        if enabled_only:
            policies = [p for p in policies if p.enabled]

        if scope:
            policies = [p for p in policies if p.scope == scope]

        if organization_id:
            policies = [
                p
                for p in policies
                if p.organization_id == organization_id or p.scope == "global"
            ]

        if tags:
            policies = [p for p in policies if any(t in p.tags for t in tags)]

        # Sort by priority (highest first)
        policies.sort(key=lambda p: p.priority, reverse=True)

        return policies

    # =========================================================================
    # Policy Evaluation
    # =========================================================================

    async def evaluate(
        self,
        request: PolicyEvaluationRequest,
    ) -> PolicyEvaluationResult:
        """Evaluate policy decision for an action.

        Args:
            request: Policy evaluation request

        Returns:
            PolicyEvaluationResult with decision and reasoning
        """
        import time

        start_time = time.time()

        # Get applicable policies
        applicable_policies = await self._get_applicable_policies(request)

        matched_policies = []
        reasons = []
        decision = self.default_decision
        determining_policy = None

        # Evaluate policies in priority order
        for policy in applicable_policies:
            if not policy.enabled:
                continue

            match_result = self._evaluate_policy(policy, request)

            if match_result["matches"]:
                matched_policies.append(policy.policy_id)
                reasons.append(match_result["reason"])

                # First matching policy determines decision
                if determining_policy is None:
                    determining_policy = policy.policy_id
                    if policy.effect == PolicyEffect.PERMIT:
                        decision = PolicyDecision.ALLOW
                    else:
                        decision = PolicyDecision.DENY

                    # FORBID policies take precedence over PERMIT at same priority
                    # Check if there's a FORBID at same priority
                    for check_policy in applicable_policies:
                        if (
                            check_policy.priority == policy.priority
                            and check_policy.effect == PolicyEffect.FORBID
                            and self._evaluate_policy(check_policy, request)["matches"]
                        ):
                            decision = PolicyDecision.DENY
                            determining_policy = check_policy.policy_id
                            break

                    break  # First match wins (highest priority)

        evaluation_time_ms = (time.time() - start_time) * 1000

        result = PolicyEvaluationResult(
            decision=decision,
            request_id=request.request_id,
            matched_policies=matched_policies,
            determining_policy=determining_policy,
            reasons=reasons if reasons else ["No matching policy, using default"],
            evaluation_time_ms=evaluation_time_ms,
        )

        # Audit the decision
        await self.audit_decision(request, result)

        logger.debug(
            f"Policy evaluation: {request.action} on {request.resource} → "
            f"{decision.value} (policy: {determining_policy}, {evaluation_time_ms:.2f}ms)"
        )

        return result

    def _evaluate_policy(
        self,
        policy: CedarPolicy,
        request: PolicyEvaluationRequest,
    ) -> dict[str, Any]:
        """Evaluate a single policy against a request.

        Args:
            policy: Policy to evaluate
            request: Request to evaluate

        Returns:
            Dictionary with 'matches' and 'reason'
        """
        cedar = policy.cedar_syntax

        # Parse the Cedar policy (simplified parser)
        # In production, would use a proper Cedar parser library

        # Extract principal constraint
        principal_match = self._check_principal(cedar, request.principal)

        # Extract action constraint
        action_match = self._check_action(cedar, request.action)

        # Extract resource constraint
        resource_match = self._check_resource(cedar, request.resource)

        # Check when/unless conditions
        condition_match = self._check_conditions(cedar, request.context)

        matches = (
            principal_match and action_match and resource_match and condition_match
        )

        return {
            "matches": matches,
            "reason": (
                f"Policy '{policy.policy_name}' "
                f"{'matches' if matches else 'does not match'}: "
                f"principal={principal_match}, action={action_match}, "
                f"resource={resource_match}, conditions={condition_match}"
            ),
        }

    def _check_principal(self, cedar: str, principal: str) -> bool:
        """Check if principal matches policy."""
        # Match "principal" (any) or "principal == Principal::X"
        if "principal," in cedar or "principal\n" in cedar:
            return True  # Matches any principal

        # Check for specific principal
        principal_match = re.search(r'principal\s*==\s*(\w+)::"([^"]+)"', cedar)
        if principal_match:
            expected = f"{principal_match.group(1)}::{principal_match.group(2)}"
            return principal == expected or principal.endswith(principal_match.group(2))

        return True  # Default to match if no constraint

    def _check_action(self, cedar: str, action: str) -> bool:
        """Check if action matches policy."""
        if "action," in cedar or "action\n" in cedar:
            return True  # Matches any action

        action_match = re.search(r'action\s*==\s*Action::"([^"]+)"', cedar)
        if action_match:
            expected_action = action_match.group(1)
            return action == expected_action or action.endswith(expected_action)

        return True

    def _check_resource(self, cedar: str, resource: str) -> bool:
        """Check if resource matches policy."""
        if "resource)" in cedar or "resource\n" in cedar:
            return True  # Matches any resource

        resource_match = re.search(r'resource\s*==\s*(\w+)::"([^"]+)"', cedar)
        if resource_match:
            expected = f"{resource_match.group(1)}::{resource_match.group(2)}"
            return resource == expected or resource.endswith(resource_match.group(2))

        return True

    def _check_conditions(
        self,
        cedar: str,
        context: dict[str, Any],
    ) -> bool:
        """Check when/unless conditions against context.

        Args:
            cedar: Cedar policy syntax
            context: Request context

        Returns:
            True if conditions are satisfied
        """
        # Extract 'when' block
        when_match = re.search(r"when\s*\{([^}]+)\}", cedar, re.DOTALL)
        if when_match:
            condition_str = when_match.group(1).strip()
            if not self._evaluate_condition_string(condition_str, context):
                return False

        # Extract 'unless' block
        unless_match = re.search(r"unless\s*\{([^}]+)\}", cedar, re.DOTALL)
        if unless_match:
            condition_str = unless_match.group(1).strip()
            if self._evaluate_condition_string(condition_str, context):
                return False  # 'unless' means deny if condition is true

        return True

    def _evaluate_condition_string(
        self,
        condition_str: str,
        context: dict[str, Any],
    ) -> bool:
        """Evaluate a Cedar condition string.

        Args:
            condition_str: Condition expression
            context: Context to evaluate against

        Returns:
            True if condition is satisfied
        """
        # Handle common patterns
        # context.X == true/false
        context_bool_match = re.search(
            r"context\.(\w+)\s*(==|!=)\s*(true|false)", condition_str
        )
        if context_bool_match:
            key = context_bool_match.group(1)
            op = context_bool_match.group(2)
            expected = context_bool_match.group(3) == "true"
            actual = context.get(key, False)

            if op == "==":
                return bool(actual == expected)
            else:  # !=
                return bool(actual != expected)

        # resource.X == "value"
        resource_str_match = re.search(
            r'resource\.(\w+)\s*==\s*"([^"]+)"', condition_str
        )
        if resource_str_match:
            key = resource_str_match.group(1)
            expected = resource_str_match.group(2)
            actual = context.get(f"resource_{key}", "")
            return bool(actual == expected)

        # resource.X in ["a", "b", "c"]
        in_list_match = re.search(r"resource\.(\w+)\s+in\s+\[([^\]]+)\]", condition_str)
        if in_list_match:
            key = in_list_match.group(1)
            values_str = in_list_match.group(2)
            values = [v.strip().strip('"') for v in values_str.split(",")]
            actual = context.get(f"resource_{key}", "")
            return actual in values

        # Default: if we can't parse, assume true (permissive)
        return True

    async def _get_applicable_policies(
        self,
        request: PolicyEvaluationRequest,
    ) -> list[CedarPolicy]:
        """Get policies applicable to a request.

        Args:
            request: Policy evaluation request

        Returns:
            List of applicable policies sorted by priority
        """
        policies = []

        for policy in self._policies.values():
            if not policy.enabled:
                continue

            # Check scope
            if policy.scope == "global":
                policies.append(policy)
            elif policy.scope == "organization":
                if policy.organization_id == request.organization_id:
                    policies.append(policy)
            elif policy.scope == "team":
                if policy.team_id == request.team_id:
                    policies.append(policy)
            elif policy.scope == "user":
                if policy.user_id == request.user_id:
                    policies.append(policy)

        # Sort by priority (highest first)
        policies.sort(key=lambda p: p.priority, reverse=True)

        return policies

    # =========================================================================
    # Tool Call Interception
    # =========================================================================

    def intercept_tool_call(
        self,
        agent_id: str,
        tool_name: str,
        parameters: dict[str, Any],
        user_id: str | None = None,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> PolicyEvaluationResult:
        """Intercept and evaluate tool call before execution.

        This is the synchronous version for use in tool invocation pipelines.

        Args:
            agent_id: Agent making the call
            tool_name: Name of tool being called
            parameters: Tool parameters
            user_id: Optional user context
            session_id: Optional session context
            context: Additional context

        Returns:
            PolicyEvaluationResult
        """
        # Build evaluation request
        request = PolicyEvaluationRequest(
            principal=f"Agent::{agent_id}",
            action="Action::invoke_tool",
            resource=f"Tool::{tool_name}",
            context={
                **(context or {}),
                "tool_parameters": parameters,
                "session_id": session_id,
            },
            user_id=user_id,
        )

        # Run async evaluation synchronously
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self.evaluate(request))
        finally:
            loop.close()

        # Record in audit log
        audit_entry = PolicyAuditEntry(
            audit_id=str(uuid.uuid4()),
            request=request,
            result=result,
            agent_id=agent_id,
            tool_name=tool_name,
            tool_parameters=parameters,
        )
        self._audit_log.append(audit_entry)

        return result

    async def intercept_tool_call_async(
        self,
        agent_id: str,
        tool_name: str,
        parameters: dict[str, Any],
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> PolicyEvaluationResult:
        """Async version of tool call interception.

        Args:
            agent_id: Agent making the call
            tool_name: Name of tool being called
            parameters: Tool parameters
            user_id: Optional user context
            context: Additional context

        Returns:
            PolicyEvaluationResult
        """
        request = PolicyEvaluationRequest(
            principal=f"Agent::{agent_id}",
            action="Action::invoke_tool",
            resource=f"Tool::{tool_name}",
            context={
                **(context or {}),
                "tool_parameters": parameters,
            },
            user_id=user_id,
        )

        result = await self.evaluate(request)

        # Record audit
        audit_entry = PolicyAuditEntry(
            audit_id=str(uuid.uuid4()),
            request=request,
            result=result,
            agent_id=agent_id,
            tool_name=tool_name,
            tool_parameters=parameters,
        )
        self._audit_log.append(audit_entry)

        return result

    def register_interceptor(
        self,
        interceptor: Callable[[str, str, dict], PolicyEvaluationResult | None],
    ) -> None:
        """Register a custom interceptor function.

        Args:
            interceptor: Function that receives (agent_id, tool_name, params)
                        and returns PolicyEvaluationResult or None to continue
        """
        self._interceptors.append(interceptor)

    # =========================================================================
    # Audit and Compliance
    # =========================================================================

    async def audit_decision(
        self,
        request: PolicyEvaluationRequest,
        result: PolicyEvaluationResult,
    ) -> None:
        """Log policy decision for compliance audit.

        Args:
            request: The evaluation request
            result: The evaluation result
        """
        audit_entry = PolicyAuditEntry(
            audit_id=str(uuid.uuid4()),
            request=request,
            result=result,
        )

        self._audit_log.append(audit_entry)

        # Persist to DynamoDB if available
        if self.dynamodb:
            await self._persist_audit_entry(audit_entry)

    async def get_audit_log(
        self,
        agent_id: str | None = None,
        tool_name: str | None = None,
        decision: PolicyDecision | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[PolicyAuditEntry]:
        """Get audit log entries with filters.

        Args:
            agent_id: Filter by agent
            tool_name: Filter by tool
            decision: Filter by decision
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum entries

        Returns:
            List of audit entries
        """
        entries = self._audit_log

        if agent_id:
            entries = [e for e in entries if e.agent_id == agent_id]

        if tool_name:
            entries = [e for e in entries if e.tool_name == tool_name]

        if decision:
            entries = [e for e in entries if e.result.decision == decision]

        if start_time:
            entries = [e for e in entries if e.created_at >= start_time]

        if end_time:
            entries = [e for e in entries if e.created_at <= end_time]

        # Sort by time descending
        entries.sort(key=lambda e: e.created_at, reverse=True)

        return entries[:limit]

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _translate_to_cedar(self, natural_language: str) -> str:
        """Translate natural language to Cedar policy using LLM.

        Args:
            natural_language: Policy description in plain English

        Returns:
            Cedar policy syntax
        """
        if not self.bedrock:
            # Fallback to template-based translation
            return self._template_based_translation(natural_language)

        prompt = f"""Convert the following natural language policy description into Cedar policy syntax.

Natural Language Policy:
{natural_language}

Cedar Policy Language Reference:
- permit(principal, action, resource) when {{ conditions }};
- forbid(principal, action, resource) when {{ conditions }};
- principal can be: principal (any), principal == Agent::"name", principal == User::"name"
- action can be: action (any), action == Action::"action_name"
- resource can be: resource (any), resource == Tool::"tool_name", resource == Data::"data_type"
- Conditions use: context.variable == value, resource.property == value
- Use && for AND, || for OR

Output ONLY the Cedar policy syntax, no explanation:"""

        try:
            response = await asyncio.to_thread(
                self.bedrock.invoke_model,
                modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 500,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                ),
            )
            result = json.loads(response["body"].read())
            cedar_syntax = str(result["content"][0]["text"]).strip()

            # Clean up any markdown code blocks
            if cedar_syntax.startswith("```"):
                lines = cedar_syntax.split("\n")
                cedar_syntax = "\n".join(lines[1:-1])

            return cedar_syntax

        except Exception as e:
            logger.warning(f"LLM translation failed, using template: {e}")
            return self._template_based_translation(natural_language)

    def _template_based_translation(self, natural_language: str) -> str:
        """Template-based fallback for NL→Cedar translation.

        Args:
            natural_language: Policy description

        Returns:
            Cedar policy syntax
        """
        nl_lower = natural_language.lower()

        # Detect common patterns
        if "cannot" in nl_lower or "must not" in nl_lower or "forbidden" in nl_lower:
            effect = "forbid"
        else:
            effect = "permit"

        # Extract agent type if mentioned
        agent_match = re.search(r"(\w+)\s*agents?", nl_lower)
        agent_type = agent_match.group(1) if agent_match else None

        # Extract tool/action if mentioned
        tool_keywords = ["slack", "github", "jira", "database", "api", "file"]
        tool_name = None
        for kw in tool_keywords:
            if kw in nl_lower:
                tool_name = kw
                break

        # Build Cedar policy
        principal = f'Agent::"{agent_type}-agent"' if agent_type else "principal"
        resource = f'Tool::"{tool_name}"' if tool_name else "resource"

        # Check for approval requirement
        if "approval" in nl_lower or "consent" in nl_lower:
            condition = "\nwhen {\n    context.approved != true\n}"
        else:
            condition = ""

        return f"""{effect}(
    {principal},
    action,
    {resource}
){condition};"""

    def _validate_cedar_syntax(self, cedar: str) -> PolicyValidationResult:
        """Validate Cedar policy syntax.

        Args:
            cedar: Cedar policy to validate

        Returns:
            PolicyValidationResult
        """
        errors = []
        warnings = []

        # Basic structure validation
        if not re.search(r"(permit|forbid)\s*\(", cedar):
            errors.append("Policy must start with 'permit(' or 'forbid('")

        if "(" not in cedar or ")" not in cedar:
            errors.append("Policy must have balanced parentheses")

        if not cedar.strip().endswith(";"):
            warnings.append("Policy should end with semicolon")
            cedar = cedar.strip() + ";"

        # Check for required components
        if "principal" not in cedar and "action" not in cedar:
            errors.append("Policy must reference principal or action")

        return PolicyValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_syntax=cedar if not errors else None,
        )

    async def _persist_policy(self, policy: CedarPolicy) -> None:
        """Persist policy to DynamoDB."""
        if not self.dynamodb:
            return

        # DynamoDB persistence would go here

    async def _persist_audit_entry(self, entry: PolicyAuditEntry) -> None:
        """Persist audit entry to DynamoDB."""
        if not self.dynamodb:
            return

        # DynamoDB persistence would go here

    # =========================================================================
    # Metrics
    # =========================================================================

    def get_policy_metrics(self) -> dict[str, Any]:
        """Get policy engine metrics.

        Returns:
            Metrics dictionary
        """
        decisions: dict[str, int] = {}
        for entry in self._audit_log[-1000:]:  # Last 1000 entries
            dec = entry.result.decision.value
            decisions[dec] = decisions.get(dec, 0) + 1

        return {
            "total_policies": len(self._policies),
            "enabled_policies": sum(1 for p in self._policies.values() if p.enabled),
            "audit_log_size": len(self._audit_log),
            "recent_decisions": decisions,
            "policies_by_scope": {
                scope: sum(1 for p in self._policies.values() if p.scope == scope)
                for scope in ["global", "organization", "team", "user"]
            },
        }
