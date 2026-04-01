"""
Project Aura - Policy Simulator

Simulate policy changes before deployment.
Implements ADR-070 for Policy-as-Code with GitOps.

Features:
- Workflow simulation under current vs proposed policy
- Identifies newly denied/allowed operations
- Detects escalation requirement changes
- Dry-run capability for safe policy testing
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .policy import AgentCapabilityPolicy

logger = logging.getLogger(__name__)


class SimulationMode(Enum):
    """Mode for simulation."""

    DRY_RUN = "dry_run"  # No side effects
    SHADOW = "shadow"  # Log decisions without enforcement
    REPLAY = "replay"  # Replay historical events


@dataclass
class ToolInvocation:
    """Represents a tool invocation for simulation."""

    agent_id: str
    agent_type: str
    tool_name: str
    action: str = "execute"
    context: str = "development"
    parameters: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "tool_name": self.tool_name,
            "action": self.action,
            "context": self.context,
            "parameters": self.parameters,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class SimulatedDecision:
    """Result of a simulated policy decision."""

    invocation: ToolInvocation
    allowed: bool
    requires_approval: bool = False
    denial_reason: str | None = None
    matched_rule: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "invocation": self.invocation.to_dict(),
            "allowed": self.allowed,
            "requires_approval": self.requires_approval,
            "denial_reason": self.denial_reason,
            "matched_rule": self.matched_rule,
        }


@dataclass
class PolicyDifference:
    """Represents a difference between current and proposed policy decisions."""

    invocation: ToolInvocation
    current_decision: SimulatedDecision
    proposed_decision: SimulatedDecision
    change_type: str  # "newly_denied", "newly_allowed", "escalation_change"
    impact_level: str = "medium"  # low, medium, high

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "invocation": self.invocation.to_dict(),
            "current_decision": self.current_decision.to_dict(),
            "proposed_decision": self.proposed_decision.to_dict(),
            "change_type": self.change_type,
            "impact_level": self.impact_level,
        }


@dataclass
class SimulationResult:
    """Result of policy simulation."""

    workflow: list[ToolInvocation]
    current_results: list[SimulatedDecision]
    proposed_results: list[SimulatedDecision]
    newly_denied: list[PolicyDifference] = field(default_factory=list)
    newly_allowed: list[PolicyDifference] = field(default_factory=list)
    escalation_changes: list[PolicyDifference] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    simulation_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "workflow": [w.to_dict() for w in self.workflow],
            "current_results": [r.to_dict() for r in self.current_results],
            "proposed_results": [r.to_dict() for r in self.proposed_results],
            "newly_denied": [d.to_dict() for d in self.newly_denied],
            "newly_allowed": [a.to_dict() for a in self.newly_allowed],
            "escalation_changes": [e.to_dict() for e in self.escalation_changes],
            "summary": self.summary,
            "simulation_time_ms": self.simulation_time_ms,
        }

    @property
    def is_safe_to_deploy(self) -> bool:
        """Check if the proposed policy is safe to deploy."""
        # Not safe if there are high-impact newly denied operations
        high_impact_denials = [d for d in self.newly_denied if d.impact_level == "high"]
        return len(high_impact_denials) == 0


@dataclass
class RegressionTestCase:
    """A test case for policy regression testing."""

    name: str
    description: str
    invocations: list[ToolInvocation]
    expected_outcomes: list[bool]  # Expected allowed/denied for each invocation
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "invocations": [i.to_dict() for i in self.invocations],
            "expected_outcomes": self.expected_outcomes,
            "tags": self.tags,
        }


@dataclass
class RegressionTestResult:
    """Result of regression testing."""

    test_case: RegressionTestCase
    passed: bool
    actual_outcomes: list[bool]
    failures: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_case": self.test_case.to_dict(),
            "passed": self.passed,
            "actual_outcomes": self.actual_outcomes,
            "failures": self.failures,
        }


class PolicySimulator:
    """
    Simulate policy changes before deployment.

    Compares workflow execution under current vs proposed policy
    to identify potential issues before deploying policy changes.
    """

    def __init__(self):
        """Initialize the policy simulator."""
        self._scenario_library: dict[str, list[ToolInvocation]] = {}
        self._load_default_scenarios()

    def _load_default_scenarios(self) -> None:
        """Load default simulation scenarios."""
        # Normal development workflow
        self._scenario_library["development_workflow"] = [
            ToolInvocation(
                agent_id="coder-001",
                agent_type="CoderAgent",
                tool_name="semantic_search",
                context="development",
            ),
            ToolInvocation(
                agent_id="coder-001",
                agent_type="CoderAgent",
                tool_name="query_code_graph",
                context="development",
            ),
            ToolInvocation(
                agent_id="coder-001",
                agent_type="CoderAgent",
                tool_name="create_branch",
                context="development",
            ),
            ToolInvocation(
                agent_id="coder-001",
                agent_type="CoderAgent",
                tool_name="commit_changes",
                context="development",
            ),
        ]

        # Security review workflow
        self._scenario_library["security_review"] = [
            ToolInvocation(
                agent_id="reviewer-001",
                agent_type="ReviewerAgent",
                tool_name="analyze_code_complexity",
                context="development",
            ),
            ToolInvocation(
                agent_id="reviewer-001",
                agent_type="ReviewerAgent",
                tool_name="query_code_graph",
                context="development",
            ),
            ToolInvocation(
                agent_id="reviewer-001",
                agent_type="ReviewerAgent",
                tool_name="get_code_dependencies",
                context="development",
            ),
        ]

        # Production deployment workflow
        self._scenario_library["production_deployment"] = [
            ToolInvocation(
                agent_id="orchestrator-001",
                agent_type="MetaOrchestrator",
                tool_name="provision_sandbox",
                context="sandbox",
            ),
            ToolInvocation(
                agent_id="validator-001",
                agent_type="ValidatorAgent",
                tool_name="run_tests",
                context="sandbox",
            ),
            ToolInvocation(
                agent_id="orchestrator-001",
                agent_type="MetaOrchestrator",
                tool_name="deploy_to_production",
                context="production",
            ),
        ]

    async def simulate_workflow(
        self,
        workflow: list[ToolInvocation],
        current_policy: AgentCapabilityPolicy,
        proposed_policy: AgentCapabilityPolicy,
    ) -> SimulationResult:
        """
        Compare workflow execution under current vs proposed policy.

        Args:
            workflow: List of tool invocations to simulate
            current_policy: Currently active policy
            proposed_policy: Proposed new policy

        Returns:
            SimulationResult with analysis of differences
        """
        import time

        start_time = time.time()

        current_results: list[SimulatedDecision] = []
        proposed_results: list[SimulatedDecision] = []

        for invocation in workflow:
            current_decision = self._evaluate(invocation, current_policy)
            proposed_decision = self._evaluate(invocation, proposed_policy)

            current_results.append(current_decision)
            proposed_results.append(proposed_decision)

        # Analyze differences
        newly_denied: list[PolicyDifference] = []
        newly_allowed: list[PolicyDifference] = []
        escalation_changes: list[PolicyDifference] = []

        for _idx, (inv, curr, prop) in enumerate(
            zip(workflow, current_results, proposed_results)
        ):
            # Check for newly denied
            if curr.allowed and not prop.allowed:
                newly_denied.append(
                    PolicyDifference(
                        invocation=inv,
                        current_decision=curr,
                        proposed_decision=prop,
                        change_type="newly_denied",
                        impact_level=self._assess_impact(inv),
                    )
                )

            # Check for newly allowed
            elif not curr.allowed and prop.allowed:
                newly_allowed.append(
                    PolicyDifference(
                        invocation=inv,
                        current_decision=curr,
                        proposed_decision=prop,
                        change_type="newly_allowed",
                        impact_level=self._assess_impact(inv),
                    )
                )

            # Check for escalation changes
            elif curr.requires_approval != prop.requires_approval:
                escalation_changes.append(
                    PolicyDifference(
                        invocation=inv,
                        current_decision=curr,
                        proposed_decision=prop,
                        change_type="escalation_change",
                        impact_level="medium",
                    )
                )

        simulation_time = (time.time() - start_time) * 1000

        return SimulationResult(
            workflow=workflow,
            current_results=current_results,
            proposed_results=proposed_results,
            newly_denied=newly_denied,
            newly_allowed=newly_allowed,
            escalation_changes=escalation_changes,
            summary={
                "total_invocations": len(workflow),
                "newly_denied": len(newly_denied),
                "newly_allowed": len(newly_allowed),
                "escalation_changes": len(escalation_changes),
                "high_impact_changes": sum(
                    1 for d in newly_denied + newly_allowed if d.impact_level == "high"
                ),
            },
            simulation_time_ms=simulation_time,
        )

    def _evaluate(
        self,
        invocation: ToolInvocation,
        policy: AgentCapabilityPolicy,
    ) -> SimulatedDecision:
        """Evaluate a single invocation against a policy."""
        tool_name = invocation.tool_name

        # Check if tool is explicitly denied
        if policy.denied_tools and tool_name in policy.denied_tools:
            return SimulatedDecision(
                invocation=invocation,
                allowed=False,
                denial_reason=f"Tool '{tool_name}' is explicitly denied",
                matched_rule="denied_tools",
            )

        # Check if tool is in allowed list (allowed_tools is dict[str, list[str]])
        if policy.allowed_tools:
            if tool_name in policy.allowed_tools:
                # Check context constraints
                requires_approval = False
                if policy.constraints and f"{tool_name}_context" in policy.constraints:
                    # Tool has context constraint, check if current context is allowed
                    allowed_contexts = policy.constraints[f"{tool_name}_context"]
                    if invocation.context not in allowed_contexts:
                        return SimulatedDecision(
                            invocation=invocation,
                            allowed=False,
                            denial_reason=f"Context '{invocation.context}' not allowed for '{tool_name}'",
                            matched_rule="context_constraint",
                        )

                return SimulatedDecision(
                    invocation=invocation,
                    allowed=True,
                    requires_approval=requires_approval,
                    matched_rule="allowed_tools",
                )
            else:
                return SimulatedDecision(
                    invocation=invocation,
                    allowed=False,
                    denial_reason=f"Tool '{tool_name}' not in allowed list",
                    matched_rule="allowed_tools",
                )

        # Default deny for unlisted tools
        return SimulatedDecision(
            invocation=invocation,
            allowed=False,
            denial_reason="No matching policy rule",
            matched_rule="default_deny",
        )

    def _assess_impact(self, invocation: ToolInvocation) -> str:
        """Assess the impact level of a policy change for an invocation."""
        # High impact tools
        high_impact_tools = {
            "deploy_to_production",
            "modify_iam_policy",
            "access_secrets",
            "destroy_sandbox",
            "modify_production_data",
        }

        # Medium impact tools
        medium_impact_tools = {
            "create_branch",
            "commit_changes",
            "provision_sandbox",
            "run_tests",
        }

        if invocation.tool_name in high_impact_tools:
            return "high"
        elif invocation.tool_name in medium_impact_tools:
            return "medium"
        else:
            return "low"

    async def run_regression_tests(
        self,
        test_cases: list[RegressionTestCase],
        policy: AgentCapabilityPolicy,
    ) -> list[RegressionTestResult]:
        """
        Run regression tests against a policy.

        Args:
            test_cases: List of test cases to run
            policy: Policy to test against

        Returns:
            List of test results
        """
        results: list[RegressionTestResult] = []

        for test_case in test_cases:
            actual_outcomes: list[bool] = []
            failures: list[dict[str, Any]] = []

            for i, invocation in enumerate(test_case.invocations):
                decision = self._evaluate(invocation, policy)
                actual_outcomes.append(decision.allowed)

                # Check if outcome matches expected
                if i < len(test_case.expected_outcomes):
                    expected = test_case.expected_outcomes[i]
                    if decision.allowed != expected:
                        failures.append(
                            {
                                "invocation_index": i,
                                "tool_name": invocation.tool_name,
                                "expected": expected,
                                "actual": decision.allowed,
                                "reason": decision.denial_reason,
                            }
                        )

            results.append(
                RegressionTestResult(
                    test_case=test_case,
                    passed=len(failures) == 0,
                    actual_outcomes=actual_outcomes,
                    failures=failures,
                )
            )

        return results

    def get_scenario(self, name: str) -> list[ToolInvocation] | None:
        """Get a predefined scenario by name."""
        return self._scenario_library.get(name)

    def list_scenarios(self) -> list[str]:
        """List available scenario names."""
        return list(self._scenario_library.keys())

    def add_scenario(self, name: str, workflow: list[ToolInvocation]) -> None:
        """Add a custom scenario."""
        self._scenario_library[name] = workflow

    async def simulate_scenario(
        self,
        scenario_name: str,
        current_policy: AgentCapabilityPolicy,
        proposed_policy: AgentCapabilityPolicy,
    ) -> SimulationResult | None:
        """
        Simulate a predefined scenario.

        Args:
            scenario_name: Name of the scenario to simulate
            current_policy: Currently active policy
            proposed_policy: Proposed new policy

        Returns:
            SimulationResult or None if scenario not found
        """
        workflow = self.get_scenario(scenario_name)
        if not workflow:
            return None

        return await self.simulate_workflow(workflow, current_policy, proposed_policy)


# Singleton instance
_simulator_instance: PolicySimulator | None = None


def get_policy_simulator() -> PolicySimulator:
    """Get or create the singleton policy simulator instance."""
    global _simulator_instance
    if _simulator_instance is None:
        _simulator_instance = PolicySimulator()
    return _simulator_instance


def reset_policy_simulator() -> None:
    """Reset the singleton instance (for testing)."""
    global _simulator_instance
    _simulator_instance = None
