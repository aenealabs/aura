"""
Tests for Policy Simulator.

Tests the policy simulation for ADR-070.
"""

import pytest

from src.services.capability_governance import (
    AgentCapabilityPolicy,
    PolicySimulator,
    RegressionTestCase,
    SimulationResult,
    ToolInvocation,
    get_policy_simulator,
    reset_policy_simulator,
)


class TestPolicySimulatorInit:
    """Tests for PolicySimulator initialization."""

    def test_create_simulator(self):
        """Test creating simulator."""
        simulator = PolicySimulator()
        assert simulator is not None

    def test_singleton_pattern(self):
        """Test singleton pattern."""
        reset_policy_simulator()
        s1 = get_policy_simulator()
        s2 = get_policy_simulator()
        assert s1 is s2

    def test_reset_clears_singleton(self):
        """Test reset clears singleton."""
        s1 = get_policy_simulator()
        reset_policy_simulator()
        s2 = get_policy_simulator()
        assert s1 is not s2

    def test_default_scenarios_loaded(self):
        """Test default scenarios are loaded."""
        simulator = PolicySimulator()
        scenarios = simulator.list_scenarios()
        assert "development_workflow" in scenarios
        assert "security_review" in scenarios
        assert "production_deployment" in scenarios


class TestScenarioManagement:
    """Tests for scenario management."""

    def test_get_scenario(self):
        """Test getting a predefined scenario."""
        simulator = PolicySimulator()
        workflow = simulator.get_scenario("development_workflow")
        assert workflow is not None
        assert len(workflow) > 0
        assert all(isinstance(inv, ToolInvocation) for inv in workflow)

    def test_get_nonexistent_scenario(self):
        """Test getting nonexistent scenario returns None."""
        simulator = PolicySimulator()
        workflow = simulator.get_scenario("nonexistent_scenario")
        assert workflow is None

    def test_add_custom_scenario(self):
        """Test adding a custom scenario."""
        simulator = PolicySimulator()
        custom_workflow = [
            ToolInvocation(
                agent_id="custom-001",
                agent_type="CustomAgent",
                tool_name="custom_tool",
            )
        ]
        simulator.add_scenario("custom_scenario", custom_workflow)
        retrieved = simulator.get_scenario("custom_scenario")
        assert retrieved is not None
        assert len(retrieved) == 1


class TestToolInvocation:
    """Tests for ToolInvocation dataclass."""

    def test_create_invocation(self):
        """Test creating tool invocation."""
        inv = ToolInvocation(
            agent_id="agent-001",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            context="development",
        )
        assert inv.agent_id == "agent-001"
        assert inv.tool_name == "semantic_search"

    def test_invocation_to_dict(self):
        """Test converting invocation to dictionary."""
        inv = ToolInvocation(
            agent_id="agent-001",
            agent_type="CoderAgent",
            tool_name="semantic_search",
        )
        d = inv.to_dict()
        assert d["agent_id"] == "agent-001"
        assert d["tool_name"] == "semantic_search"


class TestWorkflowSimulation:
    """Tests for workflow simulation."""

    @pytest.mark.asyncio
    async def test_simulate_allowed_workflow(self, coder_policy):
        """Test simulating a workflow that's allowed."""
        simulator = PolicySimulator()
        workflow = [
            ToolInvocation(
                agent_id="coder-001",
                agent_type="CoderAgent",
                tool_name="semantic_search",
            ),
        ]

        # Same policy for both current and proposed
        result = await simulator.simulate_workflow(workflow, coder_policy, coder_policy)

        assert isinstance(result, SimulationResult)
        assert len(result.workflow) == 1
        assert len(result.newly_denied) == 0
        assert len(result.newly_allowed) == 0

    @pytest.mark.asyncio
    async def test_simulate_denied_workflow(self, reviewer_policy):
        """Test simulating a workflow that includes denied operations."""
        simulator = PolicySimulator()
        workflow = [
            ToolInvocation(
                agent_id="reviewer-001",
                agent_type="ReviewerAgent",
                tool_name="deploy_to_production",  # Not allowed for reviewer
            ),
        ]

        result = await simulator.simulate_workflow(
            workflow, reviewer_policy, reviewer_policy
        )

        assert len(result.current_results) == 1
        assert not result.current_results[0].allowed

    @pytest.mark.asyncio
    async def test_detect_newly_denied(self, coder_policy):
        """Test detecting newly denied operations."""
        simulator = PolicySimulator()
        workflow = [
            ToolInvocation(
                agent_id="coder-001",
                agent_type="CoderAgent",
                tool_name="commit_changes",
            ),
        ]

        # Current policy that allows commit_changes
        permissive_policy = AgentCapabilityPolicy(
            agent_type="CoderAgent",
            allowed_tools={"semantic_search": ["read"], "commit_changes": ["execute"]},
        )

        # Proposed policy denies commit_changes
        restricted_policy = AgentCapabilityPolicy(
            agent_type="CoderAgent",
            allowed_tools={"semantic_search": ["read"]},
            denied_tools=["commit_changes"],
        )

        result = await simulator.simulate_workflow(
            workflow, permissive_policy, restricted_policy
        )

        # Should detect newly denied
        assert len(result.newly_denied) == 1
        assert result.newly_denied[0].change_type == "newly_denied"

    @pytest.mark.asyncio
    async def test_detect_newly_allowed(self):
        """Test detecting newly allowed operations."""
        simulator = PolicySimulator()
        workflow = [
            ToolInvocation(
                agent_id="agent-001",
                agent_type="TestAgent",
                tool_name="provision_sandbox",
            ),
        ]

        # Current policy denies
        restrictive_policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"semantic_search": ["read"]},
        )

        # Proposed policy allows
        permissive_policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={
                "semantic_search": ["read"],
                "provision_sandbox": ["execute"],
            },
        )

        result = await simulator.simulate_workflow(
            workflow, restrictive_policy, permissive_policy
        )

        assert len(result.newly_allowed) == 1
        assert result.newly_allowed[0].change_type == "newly_allowed"


class TestSimulationResult:
    """Tests for SimulationResult."""

    @pytest.mark.asyncio
    async def test_result_summary(self, coder_policy):
        """Test result includes summary."""
        simulator = PolicySimulator()
        workflow = simulator.get_scenario("development_workflow")

        result = await simulator.simulate_workflow(workflow, coder_policy, coder_policy)

        assert "total_invocations" in result.summary
        assert "newly_denied" in result.summary
        assert "newly_allowed" in result.summary

    @pytest.mark.asyncio
    async def test_result_to_dict(self, coder_policy):
        """Test converting result to dictionary."""
        simulator = PolicySimulator()
        workflow = [
            ToolInvocation(
                agent_id="coder-001",
                agent_type="CoderAgent",
                tool_name="semantic_search",
            ),
        ]

        result = await simulator.simulate_workflow(workflow, coder_policy, coder_policy)

        d = result.to_dict()
        assert "workflow" in d
        assert "current_results" in d
        assert "proposed_results" in d
        assert "summary" in d

    @pytest.mark.asyncio
    async def test_is_safe_to_deploy(self, coder_policy):
        """Test is_safe_to_deploy property."""
        simulator = PolicySimulator()
        workflow = [
            ToolInvocation(
                agent_id="coder-001",
                agent_type="CoderAgent",
                tool_name="semantic_search",
            ),
        ]

        result = await simulator.simulate_workflow(workflow, coder_policy, coder_policy)

        # No changes, should be safe
        assert result.is_safe_to_deploy


class TestImpactAssessment:
    """Tests for impact level assessment."""

    @pytest.mark.asyncio
    async def test_high_impact_detection(self):
        """Test high impact tool changes are flagged."""
        simulator = PolicySimulator()
        workflow = [
            ToolInvocation(
                agent_id="agent-001",
                agent_type="TestAgent",
                tool_name="deploy_to_production",
            ),
        ]

        current = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"deploy_to_production": ["execute"]},
        )
        proposed = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"semantic_search": ["read"]},  # Production no longer allowed
        )

        result = await simulator.simulate_workflow(workflow, current, proposed)

        assert len(result.newly_denied) == 1
        assert result.newly_denied[0].impact_level == "high"
        assert not result.is_safe_to_deploy


class TestScenarioSimulation:
    """Tests for predefined scenario simulation."""

    @pytest.mark.asyncio
    async def test_simulate_development_scenario(self, coder_policy):
        """Test simulating development workflow scenario."""
        simulator = PolicySimulator()

        result = await simulator.simulate_scenario(
            "development_workflow", coder_policy, coder_policy
        )

        assert result is not None
        assert len(result.workflow) > 0

    @pytest.mark.asyncio
    async def test_simulate_nonexistent_scenario(self, coder_policy):
        """Test simulating nonexistent scenario returns None."""
        simulator = PolicySimulator()

        result = await simulator.simulate_scenario(
            "nonexistent", coder_policy, coder_policy
        )

        assert result is None


class TestRegressionTesting:
    """Tests for regression testing capability."""

    @pytest.mark.asyncio
    async def test_run_passing_regression(self, coder_policy):
        """Test running passing regression tests."""
        simulator = PolicySimulator()

        test_case = RegressionTestCase(
            name="basic_search",
            description="Test that search is allowed",
            invocations=[
                ToolInvocation(
                    agent_id="coder-001",
                    agent_type="CoderAgent",
                    tool_name="semantic_search",
                ),
            ],
            expected_outcomes=[True],
            tags=["smoke"],
        )

        results = await simulator.run_regression_tests([test_case], coder_policy)

        assert len(results) == 1
        assert results[0].passed

    @pytest.mark.asyncio
    async def test_run_failing_regression(self, reviewer_policy):
        """Test running failing regression tests."""
        simulator = PolicySimulator()

        test_case = RegressionTestCase(
            name="production_deploy",
            description="Test production deploy is allowed",
            invocations=[
                ToolInvocation(
                    agent_id="reviewer-001",
                    agent_type="ReviewerAgent",
                    tool_name="deploy_to_production",
                ),
            ],
            expected_outcomes=[True],  # Expected allowed but will be denied
            tags=["critical"],
        )

        results = await simulator.run_regression_tests([test_case], reviewer_policy)

        assert len(results) == 1
        assert not results[0].passed
        assert len(results[0].failures) == 1

    @pytest.mark.asyncio
    async def test_multiple_regression_tests(self, coder_policy):
        """Test running multiple regression tests."""
        simulator = PolicySimulator()

        test_cases = [
            RegressionTestCase(
                name="test1",
                description="Test 1",
                invocations=[
                    ToolInvocation(
                        agent_id="coder-001",
                        agent_type="CoderAgent",
                        tool_name="semantic_search",
                    ),
                ],
                expected_outcomes=[True],
            ),
            RegressionTestCase(
                name="test2",
                description="Test 2",
                invocations=[
                    ToolInvocation(
                        agent_id="coder-001",
                        agent_type="CoderAgent",
                        tool_name="query_code_graph",
                    ),
                ],
                expected_outcomes=[True],
            ),
        ]

        results = await simulator.run_regression_tests(test_cases, coder_policy)

        assert len(results) == 2
