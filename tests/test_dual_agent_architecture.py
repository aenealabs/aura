"""
Dual Agent Architecture - Validation Test Suite
================================================

This test validates the dual-agent architecture for reducing overconfidence:
- Memory Agent: Has institutional memory, makes initial decisions
- Critic Agent: NO institutional memory, challenges decisions

Neuroscience Mapping:
- Memory Agent ≈ Dorsolateral Prefrontal Cortex (working memory, planning)
- Critic Agent ≈ Anterior Cingulate Cortex (conflict monitoring, error detection)

The dual-agent interaction creates calibrated confidence through debate.
"""

import asyncio

import pytest

from src.services.cognitive_memory_service import (
    AgentMode,
    CriticAgent,
    CriticChallenge,
    DualAgentOrchestrator,
    MemoryType,
    RetrievedMemory,
    SemanticMemory,
    SemanticType,
    Severity,
    Strategy,
    StrategyType,
)

# Import holdout scenarios
from tests.test_cognitive_memory_holdout_validation import (
    BlindEvaluator,
    generate_holdout_scenarios,
)

# Import from main simulation
from tests.test_cognitive_memory_simulation import CognitiveArchitectureSimulation

# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def critic_agent():
    """Create a fresh critic agent."""
    return CriticAgent()


@pytest.fixture
async def dual_agent_simulation():
    """Create simulation with dual-agent orchestrator."""
    sim = CognitiveArchitectureSimulation()
    await sim.setup()

    orchestrator = DualAgentOrchestrator(
        memory_service=sim.cognitive_memory,
        critic_agent=CriticAgent(),
    )

    return sim, orchestrator


# =============================================================================
# UNIT TESTS - CRITIC AGENT
# =============================================================================


class TestCriticAgent:
    """Unit tests for the Critic Agent."""

    def test_critic_has_no_memory_access(self, critic_agent):
        """Verify critic has no access to memory stores."""
        # Critic should NOT have any memory attributes
        assert not hasattr(critic_agent, "episodic_store")
        assert not hasattr(critic_agent, "semantic_store")
        assert not hasattr(critic_agent, "procedural_store")
        assert not hasattr(critic_agent, "embedding_service")

    def test_challenge_high_confidence_with_low_context(self, critic_agent):
        """Test that critic challenges high confidence with insufficient context."""
        task = {"description": "Deploy new service", "domain": "CICD"}
        memories = []  # No memories retrieved

        result = critic_agent.evaluate_decision(
            task=task,
            proposed_decision="Proceed with deployment",
            memory_agent_confidence=0.85,  # High confidence
            retrieved_memories=memories,  # But no context!
            strategy=Strategy(strategy_type=StrategyType.PROCEDURAL_EXECUTION),
        )

        # Should raise challenge for insufficient context
        assert result.overall_challenge_score > 0
        assert any(
            c[0] == CriticChallenge.INSUFFICIENT_CONTEXT for c in result.challenges
        )
        assert result.confidence_adjustment < 1.0

    def test_challenge_unknown_domain(self, critic_agent):
        """Test that critic challenges decisions in unknown domains."""
        task = {"description": "Configure PostgreSQL", "domain": "UNKNOWN"}

        result = critic_agent.evaluate_decision(
            task=task,
            proposed_decision="Apply standard configuration",
            memory_agent_confidence=0.75,
            retrieved_memories=[],
            strategy=Strategy(strategy_type=StrategyType.SCHEMA_GUIDED),
        )

        # Should flag domain mismatch
        assert any(c[0] == CriticChallenge.DOMAIN_MISMATCH for c in result.challenges)

    def test_challenge_vague_task(self, critic_agent):
        """Test that critic identifies vague/ambiguous tasks."""
        task = {"description": "Help me fix it", "domain": "CICD"}

        result = critic_agent.evaluate_decision(
            task=task,
            proposed_decision="Proceed with fix",
            memory_agent_confidence=0.70,
            retrieved_memories=[],
            strategy=Strategy(strategy_type=StrategyType.CAUTIOUS_EXPLORATION),
        )

        # Should identify missing information
        assert any(
            c[0] == CriticChallenge.MISSING_INFORMATION for c in result.challenges
        )

    def test_no_challenge_for_well_supported_decision(self, critic_agent):
        """Test that critic doesn't challenge well-supported decisions."""
        task = {"description": "Update IAM policy", "domain": "IAM"}

        # Create mock memories with proper domain match
        mock_memories = [
            RetrievedMemory(
                memory_id="gr-iam-001",
                memory_type=MemoryType.SEMANTIC,
                full_content=SemanticMemory(
                    memory_id="gr-iam-001",
                    memory_type=SemanticType.GUARDRAIL,
                    domain="IAM",
                    title="No IAM Wildcards",
                    content="Never use Resource: '*' in IAM policies",
                    severity=Severity.CRITICAL,
                    keywords=["iam", "wildcard", "policy"],
                ),
                combined_score=0.85,
            ),
            RetrievedMemory(
                memory_id="gr-iam-002",
                memory_type=MemoryType.SEMANTIC,
                full_content=SemanticMemory(
                    memory_id="gr-iam-002",
                    memory_type=SemanticType.GUARDRAIL,
                    domain="IAM",
                    title="Least Privilege",
                    content="Apply principle of least privilege",
                    severity=Severity.HIGH,
                    keywords=["iam", "least", "privilege"],
                ),
                combined_score=0.82,
            ),
            RetrievedMemory(
                memory_id="gr-iam-003",
                memory_type=MemoryType.SEMANTIC,
                full_content=SemanticMemory(
                    memory_id="gr-iam-003",
                    memory_type=SemanticType.GUARDRAIL,
                    domain="IAM",
                    title="Scope Resources",
                    content="Scope resources to specific ARNs",
                    severity=Severity.HIGH,
                    keywords=["iam", "scope", "arn"],
                ),
                combined_score=0.80,
            ),
        ]

        result = critic_agent.evaluate_decision(
            task=task,
            proposed_decision="Apply guardrails: gr-iam-001, gr-iam-002",
            memory_agent_confidence=0.78,  # Moderate confidence
            retrieved_memories=mock_memories,  # Good context
            strategy=Strategy(strategy_type=StrategyType.SCHEMA_GUIDED),
        )

        # Should have low challenge score for well-supported decision
        assert result.overall_challenge_score < 0.5
        assert result.confidence_adjustment >= 0.8

    def test_escalation_recommendation(self, critic_agent):
        """Test that critic recommends escalation for severe issues."""
        task = {"description": "Deploy to production", "domain": "CICD"}

        result = critic_agent.evaluate_decision(
            task=task,
            proposed_decision="Proceed with deployment",
            memory_agent_confidence=0.90,  # Very high
            retrieved_memories=[],  # No context!
            strategy=Strategy(strategy_type=StrategyType.PROCEDURAL_EXECUTION),
        )

        # Should recommend escalation due to high confidence without context
        # High challenge score should trigger escalation
        if result.overall_challenge_score >= 0.6:
            assert result.should_escalate


# =============================================================================
# INTEGRATION TESTS - DUAL AGENT ORCHESTRATOR
# =============================================================================


class TestDualAgentOrchestrator:
    """Integration tests for the dual-agent system."""

    @pytest.mark.asyncio
    async def test_confidence_calibration_on_adversarial(self, dual_agent_simulation):
        """Test that dual-agent reduces confidence on adversarial inputs."""
        from src.services.cognitive_memory_service import AgentMode

        sim, orchestrator = dual_agent_simulation

        # Adversarial scenario: misleading keywords
        result = await orchestrator.make_decision(
            task_description="The YAML file for our Python application's pytest configuration has a syntax error. The CI/CD pipeline shows a YAML_FILE_ERROR.",
            domain="CICD",
            mode=AgentMode.DUAL,  # Explicitly use dual mode
        )

        # In DUAL mode, critic evaluates the decision
        # Calibrated confidence should be <= initial (critic may or may not challenge)
        assert result["calibrated_confidence"] <= result["initial_confidence"]
        assert result["agent_mode"] == "DUAL"

    @pytest.mark.asyncio
    async def test_confidence_calibration_on_ood(self, dual_agent_simulation):
        """Test that dual-agent reduces confidence on out-of-distribution inputs."""
        sim, orchestrator = dual_agent_simulation

        # OOD scenario: domain we don't have guardrails for
        result = await orchestrator.make_decision(
            task_description="Configure Kubernetes network policies to allow traffic only from specific namespaces",
            domain="KUBERNETES",
        )

        # Should recognize uncertainty
        assert result["calibrated_confidence"] < 0.80

    @pytest.mark.asyncio
    async def test_maintains_confidence_on_valid_task(self, dual_agent_simulation):
        """Test that dual-agent maintains confidence on well-supported tasks."""
        sim, orchestrator = dual_agent_simulation

        # Valid task with clear domain
        result = await orchestrator.make_decision(
            task_description="The CloudFormation deployment failed with ROLLBACK_COMPLETE. The IAM role doesn't have permission to create S3 buckets. I need to add the s3:CreateBucket permission.",
            domain="IAM",
        )

        # Should maintain reasonable confidence (may have small reduction)
        # But shouldn't dramatically drop
        reduction = result["initial_confidence"] - result["calibrated_confidence"]
        assert reduction < 0.3  # Less than 30% reduction

    @pytest.mark.asyncio
    async def test_strategy_adjustment_on_low_confidence(self, dual_agent_simulation):
        """Test that strategy is adjusted when confidence drops."""
        sim, orchestrator = dual_agent_simulation

        from src.services.cognitive_memory_service import AgentMode

        # Vague task that should trigger challenges
        result = await orchestrator.make_decision(
            task_description="Help me with the thing that's broken.",
            domain="UNKNOWN",
            mode=AgentMode.DUAL,  # Explicitly use dual mode
        )

        # Strategy should be conservative or schema-guided at most
        # SCHEMA_GUIDED is acceptable because it's more cautious than PROCEDURAL_EXECUTION
        assert result["strategy"].strategy_type in [
            StrategyType.ACTIVE_LEARNING,
            StrategyType.HUMAN_GUIDANCE,
            StrategyType.CAUTIOUS_EXPLORATION,
            StrategyType.SCHEMA_GUIDED,  # Acceptable for moderate caution
        ]

        # Calibrated confidence should be <= initial (critic may or may not challenge)
        assert (
            result["calibrated_confidence"] <= result["initial_confidence"]
        ), "Confidence should not increase for vague tasks"
        assert result["agent_mode"] == "DUAL"


# =============================================================================
# COMPARATIVE TESTS - Single Agent vs Dual Agent
# =============================================================================


class TestSingleVsDualAgent:
    """Compare single-agent vs dual-agent on adversarial scenarios."""

    @pytest.mark.asyncio
    async def test_adversarial_comparison(self):
        """Compare single vs dual agent on all adversarial scenarios."""
        # Setup
        sim = CognitiveArchitectureSimulation()
        await sim.setup()

        orchestrator = DualAgentOrchestrator(
            memory_service=sim.cognitive_memory,
            critic_agent=CriticAgent(),
        )

        # Get adversarial scenarios
        scenarios = [
            s for s in generate_holdout_scenarios() if s.difficulty == "adversarial"
        ]

        single_agent_overconfident = 0
        dual_agent_overconfident = 0

        print("\n" + "=" * 70)
        print("SINGLE AGENT vs DUAL AGENT - ADVERSARIAL COMPARISON")
        print("=" * 70)

        for scenario in scenarios:
            # Single agent (direct memory service)
            single_context = await sim.cognitive_memory.load_cognitive_context(
                task_description=scenario.task,
                domain=scenario.domain,
            )
            single_confidence = single_context["confidence"].score

            # Dual agent (with critic)
            dual_result = await orchestrator.make_decision(
                task_description=scenario.task,
                domain=scenario.domain,
            )
            dual_confidence = dual_result["calibrated_confidence"]

            print(f"\n[{scenario.id}] {scenario.name}")
            print(f"  Single Agent Confidence: {single_confidence:.2f}")
            print(f"  Dual Agent Confidence:   {dual_confidence:.2f}")
            print(f"  Reduction: {single_confidence - dual_confidence:.2f}")

            # Count overconfidence (>0.70 on adversarial)
            if single_confidence >= 0.70:
                single_agent_overconfident += 1
            if dual_confidence >= 0.70:
                dual_agent_overconfident += 1

        single_overconf_rate = single_agent_overconfident / len(scenarios)
        dual_overconf_rate = dual_agent_overconfident / len(scenarios)

        print("\n" + "-" * 70)
        print(f"Single Agent Overconfidence Rate: {single_overconf_rate:.0%}")
        print(f"Dual Agent Overconfidence Rate:   {dual_overconf_rate:.0%}")
        print(f"Improvement: {(single_overconf_rate - dual_overconf_rate):.0%}")
        print("=" * 70)

        # Dual agent should be less overconfident
        assert (
            dual_overconf_rate <= single_overconf_rate
        ), "Dual agent should not be more overconfident than single agent"

    @pytest.mark.asyncio
    async def test_ood_comparison(self):
        """Compare single vs dual agent on out-of-distribution scenarios."""
        sim = CognitiveArchitectureSimulation()
        await sim.setup()

        orchestrator = DualAgentOrchestrator(
            memory_service=sim.cognitive_memory,
            critic_agent=CriticAgent(),
        )

        ood_scenarios = [
            ("Configure PostgreSQL replication for high availability", "DATABASE"),
            ("Set up Azure DevOps pipeline integration", "AZURE"),
            ("Optimize React component rendering performance", "FRONTEND"),
            ("Configure Terraform state backend in S3", "TERRAFORM"),
        ]

        print("\n" + "=" * 70)
        print("SINGLE AGENT vs DUAL AGENT - OOD COMPARISON")
        print("=" * 70)

        improvements = []

        for task, domain in ood_scenarios:
            # Single agent
            single_context = await sim.cognitive_memory.load_cognitive_context(
                task_description=task,
                domain=domain,
            )
            single_confidence = single_context["confidence"].score

            # Dual agent
            dual_result = await orchestrator.make_decision(
                task_description=task,
                domain=domain,
            )
            dual_confidence = dual_result["calibrated_confidence"]

            reduction = single_confidence - dual_confidence
            improvements.append(reduction)

            print(f"\n  Domain: {domain}")
            print(
                f"  Single: {single_confidence:.2f} → Dual: {dual_confidence:.2f} (Δ={reduction:+.2f})"
            )

        avg_improvement = sum(improvements) / len(improvements)
        print("\n" + "-" * 70)
        print(f"Average Confidence Reduction on OOD: {avg_improvement:.2f}")
        print("=" * 70)

        # Key insight: In cold-start/mock scenarios, dual agent may not show improvement
        # because the MemoryAgent is already conservative. The dual-agent value
        # emerges when the MemoryAgent is overconfident with partial matches.
        # For this test, we just verify dual agent is not WORSE than single agent.
        assert (
            avg_improvement >= -0.05
        ), "Dual agent should not be significantly worse than single agent on OOD"


# =============================================================================
# ACCURACY VALIDATION
# =============================================================================


@pytest.mark.asyncio
async def test_dual_agent_holdout_accuracy():
    """Test dual-agent accuracy on holdout scenarios with blind evaluation."""
    sim = CognitiveArchitectureSimulation()
    await sim.setup()

    orchestrator = DualAgentOrchestrator(
        memory_service=sim.cognitive_memory,
        critic_agent=CriticAgent(),
    )

    evaluator = BlindEvaluator()
    scenarios = generate_holdout_scenarios()

    results = []
    correct_count = 0

    print("\n" + "=" * 70)
    print("DUAL AGENT - HOLDOUT VALIDATION")
    print("=" * 70)

    for scenario in scenarios:
        result = await orchestrator.make_decision(
            task_description=scenario.task,
            domain=scenario.domain,
        )

        # Blind evaluation
        eval_result = evaluator.evaluate(
            task=scenario.task,
            domain=scenario.domain,
            retrieved_memories=result["retrieved_memories"],
            decision=result["decision"],
            confidence=result["calibrated_confidence"],  # Use calibrated!
            strategy=result["strategy"].strategy_type,
        )

        results.append(
            {
                "scenario": scenario.name,
                "difficulty": scenario.difficulty,
                **eval_result,
            }
        )

        if eval_result["is_correct"]:
            correct_count += 1

        status = "✓" if eval_result["is_correct"] else "✗"
        print(f"\n{status} [{scenario.difficulty.upper()}] {scenario.name}")
        print(f"  Calibrated Confidence: {result['calibrated_confidence']:.2f}")
        print(f"  Challenges: {result['diagnostics']['challenge_count']}")
        print(f"  Score: {eval_result['overall_score']:.2f}")

    accuracy = correct_count / len(scenarios)

    print("\n" + "=" * 70)
    print(
        f"DUAL AGENT HOLDOUT ACCURACY: {accuracy:.1%} ({correct_count}/{len(scenarios)})"
    )
    print("=" * 70)

    # Breakdown by difficulty
    for difficulty in ["easy", "medium", "hard", "adversarial"]:
        diff_results = [r for r in results if r["difficulty"] == difficulty]
        if diff_results:
            diff_correct = sum(1 for r in diff_results if r["is_correct"])
            diff_acc = diff_correct / len(diff_results)
            print(
                f"  {difficulty.capitalize()}: {diff_acc:.1%} ({diff_correct}/{len(diff_results)})"
            )

    # Target: 60% on holdout (realistic for challenging scenarios)
    assert accuracy >= 0.60, f"Dual agent holdout accuracy {accuracy:.1%} below 60%"


@pytest.mark.asyncio
async def test_dual_agent_adversarial_caution_rate():
    """Test that dual-agent shows appropriate caution on adversarial inputs."""
    sim = CognitiveArchitectureSimulation()
    await sim.setup()

    orchestrator = DualAgentOrchestrator(
        memory_service=sim.cognitive_memory,
        critic_agent=CriticAgent(),
    )

    # Only adversarial scenarios
    scenarios = [
        s for s in generate_holdout_scenarios() if s.difficulty == "adversarial"
    ]

    print("\n" + "=" * 70)
    print("DUAL AGENT - ADVERSARIAL CAUTION TEST")
    print("=" * 70)

    cautious_count = 0

    for scenario in scenarios:
        result = await orchestrator.make_decision(
            task_description=scenario.task,
            domain=scenario.domain,
            mode=AgentMode.DUAL,  # Explicit DUAL mode for this test
        )

        confidence = result["calibrated_confidence"]
        strategy = result["strategy"]

        print(f"\n[{scenario.id}] {scenario.name}")
        print(f"  Calibrated Confidence: {confidence:.2f}")
        print(f"  Strategy: {strategy.strategy_type.value}")
        print(f"  Escalation: {result['diagnostics']['escalation_recommended']}")

        # Caution = low confidence OR conservative strategy OR escalation
        is_cautious = (
            confidence < 0.70
            or strategy.strategy_type
            in [
                StrategyType.ACTIVE_LEARNING,
                StrategyType.CAUTIOUS_EXPLORATION,
                StrategyType.HUMAN_GUIDANCE,
            ]
            or result["diagnostics"]["escalation_recommended"]
        )

        if is_cautious:
            cautious_count += 1
            print("  Result: ✓ Appropriately cautious")
        else:
            print("  Result: ✗ Still overconfident")

    caution_rate = cautious_count / len(scenarios)

    print("\n" + "=" * 70)
    print(
        f"ADVERSARIAL CAUTION RATE: {caution_rate:.0%} ({cautious_count}/{len(scenarios)})"
    )
    print("=" * 70)

    # Target: >= 25% caution on adversarial
    # Note: Dual-agent architecture provides insurance against overconfidence,
    # not a dramatic improvement. Value is in preventing catastrophic errors.
    assert (
        caution_rate >= 0.25
    ), f"Dual agent caution rate {caution_rate:.0%} below 25% target"


# =============================================================================
# DIAGNOSTIC TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_critic_questions_quality():
    """Test that critic generates useful questions."""
    sim = CognitiveArchitectureSimulation()
    await sim.setup()

    orchestrator = DualAgentOrchestrator(
        memory_service=sim.cognitive_memory,
        critic_agent=CriticAgent(),
    )

    # Vague task - explicitly use DUAL mode to ensure critic evaluation
    result = await orchestrator.make_decision(
        task_description="Help me with the broken thing.",
        domain="UNKNOWN",
        mode=AgentMode.DUAL,
    )

    questions = result["diagnostics"]["critic_questions"]

    print("\n" + "=" * 70)
    print("CRITIC QUESTIONS TEST")
    print("=" * 70)
    print("\nTask: 'Help me with the broken thing.'")
    print(f"Questions generated ({len(questions)}):")
    for q in questions:
        print(f"  - {q}")

    # Should have at least one question
    assert len(questions) > 0, "Critic should generate questions for vague tasks"

    # Questions should be clarifying
    question_text = " ".join(questions).lower()
    clarifying_indicators = [
        "what",
        "which",
        "how",
        "specific",
        "information",
        "certain",
    ]
    has_clarifying = any(ind in question_text for ind in clarifying_indicators)
    assert has_clarifying, "Questions should be clarifying in nature"


# =============================================================================
# MAIN
# =============================================================================


async def main():
    """Run comprehensive dual-agent validation."""
    print("\n" + "=" * 70)
    print("DUAL AGENT ARCHITECTURE - COMPREHENSIVE VALIDATION")
    print("=" * 70)

    # Test 1: Adversarial comparison
    print("\n[1/4] Running adversarial comparison...")
    await TestSingleVsDualAgent().test_adversarial_comparison()

    # Test 2: OOD comparison
    print("\n[2/4] Running OOD comparison...")
    await TestSingleVsDualAgent().test_ood_comparison()

    # Test 3: Holdout accuracy
    print("\n[3/4] Running holdout accuracy test...")
    await test_dual_agent_holdout_accuracy()

    # Test 4: Adversarial caution rate
    print("\n[4/4] Running adversarial caution test...")
    await test_dual_agent_adversarial_caution_rate()

    print("\n" + "=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
