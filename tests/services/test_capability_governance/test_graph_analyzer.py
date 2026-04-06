"""
Tests for capability graph analyzer (ADR-071).

Tests the CapabilityGraphAnalyzer that performs security analysis
on the capability graph.
"""

import pytest

from src.services.capability_governance import (
    CapabilityGraphAnalyzer,
    PolicyGraphSynchronizer,
    ToolClassification,
    get_capability_graph_analyzer,
    reset_capability_graph_analyzer,
)
from src.services.capability_governance.graph_contracts import ConflictType, RiskLevel


@pytest.fixture
def synced_graph():
    """Create a synchronizer with all policies synced."""
    sync = PolicyGraphSynchronizer(mock_mode=True)

    # Sync using the event-based approach
    import asyncio

    async def sync_all():
        await sync.sync_all_policies()

    asyncio.get_event_loop().run_until_complete(sync_all())
    return sync


@pytest.fixture
def analyzer(synced_graph):
    """Create an analyzer with a synced graph."""
    return CapabilityGraphAnalyzer(
        synchronizer=synced_graph,
        mock_mode=True,
    )


class TestCapabilityGraphAnalyzer:
    """Tests for CapabilityGraphAnalyzer."""

    def test_create_analyzer(self):
        """Test creating an analyzer instance."""
        analyzer = CapabilityGraphAnalyzer(mock_mode=True)
        assert analyzer.mock_mode is True

    def test_singleton_pattern(self):
        """Test singleton pattern."""
        reset_capability_graph_analyzer()
        analyzer1 = get_capability_graph_analyzer()
        analyzer2 = get_capability_graph_analyzer()
        assert analyzer1 is analyzer2


class TestEscalationPathDetection:
    """Tests for escalation path detection."""

    @pytest.mark.asyncio
    async def test_detect_escalation_paths(self, analyzer):
        """Test basic escalation path detection."""
        paths = await analyzer.detect_escalation_paths()
        assert isinstance(paths, list)

    @pytest.mark.asyncio
    async def test_escalation_paths_have_required_fields(self, analyzer):
        """Test that detected paths have required fields."""
        paths = await analyzer.detect_escalation_paths(min_risk_score=0.0)

        for path in paths:
            assert path.path_id is not None
            assert path.source_agent is not None
            assert path.target_capability is not None
            assert path.classification is not None
            assert path.risk_score >= 0.0
            assert path.risk_score <= 1.0
            assert path.risk_level is not None

    @pytest.mark.asyncio
    async def test_escalation_paths_respect_min_risk(self, analyzer):
        """Test that min_risk_score filters results."""
        all_paths = await analyzer.detect_escalation_paths(min_risk_score=0.0)
        high_risk_paths = await analyzer.detect_escalation_paths(min_risk_score=0.9)

        assert len(high_risk_paths) <= len(all_paths)

    @pytest.mark.asyncio
    async def test_critical_capabilities_have_high_risk(self, analyzer):
        """Test that CRITICAL capabilities produce high risk scores."""
        paths = await analyzer.detect_escalation_paths(min_risk_score=0.0)

        critical_paths = [
            p for p in paths if p.classification == ToolClassification.CRITICAL
        ]

        for path in critical_paths:
            assert path.risk_score >= 0.8
            assert path.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)

    @pytest.mark.asyncio
    async def test_escalation_path_to_dict(self, analyzer):
        """Test path serialization."""
        paths = await analyzer.detect_escalation_paths(min_risk_score=0.0)

        if paths:
            data = paths[0].to_dict()
            assert "path_id" in data
            assert "risk_score" in data
            assert "detection_time" in data


class TestCoverageGapAnalysis:
    """Tests for coverage gap analysis."""

    @pytest.mark.asyncio
    async def test_find_coverage_gaps(self, analyzer):
        """Test basic coverage gap detection."""
        gaps = await analyzer.find_coverage_gaps()
        assert isinstance(gaps, list)

    @pytest.mark.asyncio
    async def test_coverage_gaps_have_required_fields(self, analyzer):
        """Test that detected gaps have required fields."""
        gaps = await analyzer.find_coverage_gaps()

        for gap in gaps:
            assert gap.gap_id is not None
            assert gap.agent_name is not None
            assert gap.agent_type is not None
            assert gap.gap_type is not None
            assert gap.risk_level is not None

    @pytest.mark.asyncio
    async def test_coverage_gap_types(self, analyzer):
        """Test that gap types are valid."""
        gaps = await analyzer.find_coverage_gaps()

        valid_types = {
            "missing_monitoring",
            "missing_read_operations",
            "orphaned_grant",
        }
        for gap in gaps:
            assert gap.gap_type in valid_types

    @pytest.mark.asyncio
    async def test_coverage_gap_to_dict(self, analyzer):
        """Test gap serialization."""
        gaps = await analyzer.find_coverage_gaps()

        if gaps:
            data = gaps[0].to_dict()
            assert "gap_id" in data
            assert "gap_type" in data
            assert "risk_level" in data


class TestToxicCombinationDetection:
    """Tests for toxic combination detection."""

    @pytest.mark.asyncio
    async def test_detect_toxic_combinations(self, analyzer):
        """Test basic toxic combination detection."""
        combinations = await analyzer.detect_toxic_combinations()
        assert isinstance(combinations, list)

    @pytest.mark.asyncio
    async def test_toxic_combinations_have_required_fields(self, analyzer):
        """Test that detected combinations have required fields."""
        combinations = await analyzer.detect_toxic_combinations()

        for combo in combinations:
            assert combo.combination_id is not None
            assert combo.agent_name is not None
            assert combo.capability_a is not None
            assert combo.capability_b is not None
            assert combo.conflict_type is not None
            assert combo.severity is not None

    @pytest.mark.asyncio
    async def test_toxic_combination_conflict_types(self, analyzer):
        """Test that conflict types are valid."""
        combinations = await analyzer.detect_toxic_combinations()

        for combo in combinations:
            assert combo.conflict_type in ConflictType

    @pytest.mark.asyncio
    async def test_privilege_escalation_is_critical(self, analyzer):
        """Test that privilege escalation conflicts are critical."""
        combinations = await analyzer.detect_toxic_combinations()

        for combo in combinations:
            if combo.conflict_type == ConflictType.PRIVILEGE_ESCALATION:
                assert combo.severity == RiskLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_toxic_combination_to_dict(self, analyzer):
        """Test combination serialization."""
        combinations = await analyzer.detect_toxic_combinations()

        if combinations:
            data = combinations[0].to_dict()
            assert "combination_id" in data
            assert "conflict_type" in data
            assert "severity" in data


class TestInheritanceTree:
    """Tests for inheritance tree calculation."""

    @pytest.mark.asyncio
    async def test_get_inheritance_tree(self, analyzer):
        """Test getting inheritance tree for an agent."""
        tree = await analyzer.get_inheritance_tree("CoderAgent")

        assert tree.root_agent == "CoderAgent"
        assert tree.depth >= 1
        assert tree.total_agents >= 1

    @pytest.mark.asyncio
    async def test_inheritance_tree_contains_root_node(self, analyzer):
        """Test that tree contains the root node."""
        tree = await analyzer.get_inheritance_tree("ReviewerAgent")

        assert tree.tree is not None
        assert tree.tree.agent_name == "ReviewerAgent"
        assert tree.tree.tier == 0

    @pytest.mark.asyncio
    async def test_inheritance_tree_capabilities(self, analyzer):
        """Test that tree node contains capabilities."""
        tree = await analyzer.get_inheritance_tree("CoderAgent")

        # Root should have direct capabilities from policy
        assert isinstance(tree.tree.direct_capabilities, list)

    @pytest.mark.asyncio
    async def test_inheritance_tree_to_dict(self, analyzer):
        """Test tree serialization."""
        tree = await analyzer.get_inheritance_tree("CoderAgent")

        data = tree.to_dict()
        assert "root_agent" in data
        assert "tree" in data
        assert "depth" in data
        assert "calculated_at" in data

    @pytest.mark.asyncio
    async def test_unknown_agent_returns_empty_tree(self, analyzer):
        """Test handling unknown agent type."""
        tree = await analyzer.get_inheritance_tree("UnknownAgent")

        assert tree.root_agent == "UnknownAgent"
        assert tree.total_direct_capabilities == 0


class TestEffectiveCapabilities:
    """Tests for effective capabilities calculation."""

    @pytest.mark.asyncio
    async def test_calculate_effective_capabilities(self, analyzer):
        """Test calculating effective capabilities."""
        caps = await analyzer.calculate_effective_capabilities(
            agent_id="coder-001",
            agent_type="CoderAgent",
            execution_context="development",
        )

        assert caps.agent_id == "coder-001"
        assert caps.agent_type == "CoderAgent"
        assert caps.execution_context == "development"

    @pytest.mark.asyncio
    async def test_effective_capabilities_from_policy(self, analyzer):
        """Test that capabilities come from policy."""
        caps = await analyzer.calculate_effective_capabilities(
            agent_id="coder-001",
            agent_type="CoderAgent",
            execution_context="development",
        )

        # CoderAgent should have semantic_search
        tool_names = [c.tool_name for c in caps.capabilities]
        assert "semantic_search" in tool_names

    @pytest.mark.asyncio
    async def test_effective_capabilities_respects_context(self, analyzer):
        """Test that context restrictions are applied."""
        # Production context should restrict some agents
        caps = await analyzer.calculate_effective_capabilities(
            agent_id="coder-001",
            agent_type="CoderAgent",
            execution_context="production",
        )

        # CoderAgent policy doesn't allow production
        assert caps.capability_count == 0

    @pytest.mark.asyncio
    async def test_effective_capabilities_classification(self, analyzer):
        """Test capability classifications are correct."""
        caps = await analyzer.calculate_effective_capabilities(
            agent_id="redteam-001",
            agent_type="RedTeamAgent",
            execution_context="sandbox",
        )

        for cap in caps.capabilities:
            assert cap.classification is not None
            assert cap.classification in ToolClassification

    @pytest.mark.asyncio
    async def test_effective_capabilities_has_dangerous(self, analyzer):
        """Test has_dangerous property."""
        # RedTeamAgent has DANGEROUS capabilities
        caps = await analyzer.calculate_effective_capabilities(
            agent_id="redteam-001",
            agent_type="RedTeamAgent",
            execution_context="sandbox",
        )

        # RedTeam has provision_sandbox which is CRITICAL
        # Check if any dangerous or critical
        has_elevated = caps.has_dangerous or caps.has_critical
        assert has_elevated is True

    @pytest.mark.asyncio
    async def test_unknown_agent_returns_empty(self, analyzer):
        """Test handling unknown agent type."""
        caps = await analyzer.calculate_effective_capabilities(
            agent_id="unknown-001",
            agent_type="UnknownAgent",
            execution_context="development",
        )

        # Unknown agent gets empty capabilities but policy_version may vary
        assert caps.capability_count == 0
        # Policy version is either "unknown" or default "1.0" depending on error handling
        assert caps.policy_version in ("unknown", "1.0")


class TestVisualizationData:
    """Tests for visualization data generation."""

    @pytest.mark.asyncio
    async def test_get_visualization_data(self, analyzer):
        """Test getting visualization data."""
        viz = await analyzer.get_visualization_data()

        assert viz is not None
        assert isinstance(viz.nodes, list)
        assert isinstance(viz.edges, list)

    @pytest.mark.asyncio
    async def test_visualization_contains_agents(self, analyzer):
        """Test that visualization contains agent nodes."""
        viz = await analyzer.get_visualization_data()

        agent_nodes = [n for n in viz.nodes if n["type"] == "agent"]
        assert len(agent_nodes) > 0

    @pytest.mark.asyncio
    async def test_visualization_contains_capabilities(self, analyzer):
        """Test that visualization contains capability nodes."""
        viz = await analyzer.get_visualization_data()

        cap_nodes = [n for n in viz.nodes if n["type"] == "capability"]
        assert len(cap_nodes) > 0

    @pytest.mark.asyncio
    async def test_visualization_node_colors(self, analyzer):
        """Test that nodes have correct colors."""
        viz = await analyzer.get_visualization_data()

        for node in viz.nodes:
            assert "color" in node
            if node["type"] == "agent":
                assert node["color"] == "#3B82F6"  # Blue

    @pytest.mark.asyncio
    async def test_visualization_edge_styles(self, analyzer):
        """Test that edges have correct styles."""
        viz = await analyzer.get_visualization_data()

        for edge in viz.edges:
            assert "style" in edge
            assert edge["style"] in ("solid", "dashed", "dotted")

    @pytest.mark.asyncio
    async def test_visualization_metadata(self, analyzer):
        """Test that visualization includes metadata."""
        viz = await analyzer.get_visualization_data()

        assert "generated_at" in viz.metadata
        assert "node_count" in viz.metadata
        assert "edge_count" in viz.metadata

    @pytest.mark.asyncio
    async def test_visualization_to_dict(self, analyzer):
        """Test visualization serialization."""
        viz = await analyzer.get_visualization_data()

        data = viz.to_dict()
        assert "nodes" in data
        assert "edges" in data
        assert "metadata" in data


class TestFullAnalysis:
    """Tests for full analysis run."""

    @pytest.mark.asyncio
    async def test_run_full_analysis(self, analyzer):
        """Test running full analysis."""
        results = await analyzer.run_full_analysis()

        assert "analysis_id" in results
        assert "timestamp" in results
        assert "summary" in results
        assert "escalation_paths" in results
        assert "coverage_gaps" in results
        assert "toxic_combinations" in results
        assert "visualization" in results

    @pytest.mark.asyncio
    async def test_full_analysis_summary(self, analyzer):
        """Test full analysis summary metrics."""
        results = await analyzer.run_full_analysis()
        summary = results["summary"]

        assert "total_escalation_paths" in summary
        assert "total_coverage_gaps" in summary
        assert "total_toxic_combinations" in summary
        assert "critical_issues" in summary
        assert "high_issues" in summary
        assert "risk_score" in summary

    @pytest.mark.asyncio
    async def test_full_analysis_risk_score(self, analyzer):
        """Test risk score calculation."""
        results = await analyzer.run_full_analysis()

        risk_score = results["summary"]["risk_score"]
        assert risk_score >= 0.0
        assert risk_score <= 1.0


class TestSelfGovernanceEdge:
    """Tests for self-governance edge and self-modification path detection (ADR-086)."""

    def test_add_self_governance_edge(self, analyzer):
        """Test adding a SELF_GOVERNANCE edge to the graph."""
        analyzer.add_self_governance_edge(
            agent_id="coder-agent",
            artifact_id="policy-coder-permissions",
            artifact_class="iam_policy",
        )
        graph = analyzer.synchronizer.get_mock_graph()
        gov_edges = [
            e for e in graph["edges"] if e.get("edge_type") == "self_governance"
        ]
        assert len(gov_edges) >= 1
        last = gov_edges[-1]
        assert last["source_id"] == "agent:coder-agent"
        assert last["target_id"] == "policy-coder-permissions"
        assert last["artifact_class"] == "iam_policy"

    @pytest.mark.asyncio
    async def test_detect_self_modification_no_edges(self, analyzer):
        """No self-governance edges means no self-modification paths."""
        paths = await analyzer.detect_self_modification_paths()
        assert paths == []

    @pytest.mark.asyncio
    async def test_detect_self_modification_with_write_cap(self, analyzer):
        """Agent with write cap + self-governance edge is detected."""
        # Add self-governance edge
        analyzer.add_self_governance_edge(
            agent_id="CoderAgent",
            artifact_id="guardrail-coder-config",
            artifact_class="guardrail_config",
        )

        # Add a dangerous write capability directly to mock edges
        analyzer.synchronizer._mock_edges.append(
            {
                "source_id": "agent:CoderAgent",
                "target_id": "cap:write_file",
                "edge_type": "has_capability",
                "classification": "dangerous",
            }
        )

        paths = await analyzer.detect_self_modification_paths()
        assert len(paths) >= 1
        coder_paths = [p for p in paths if p["agent_id"] == "CoderAgent"]
        assert len(coder_paths) >= 1
        assert coder_paths[0]["risk_level"] == "critical"
        assert "write_file" in coder_paths[0]["write_capabilities"]

    @pytest.mark.asyncio
    async def test_self_mod_path_without_write_cap_is_not_detected(self, analyzer):
        """Agent with self-governance edge but no write cap has no path."""
        # Only add self-governance edge, no write capability
        analyzer.synchronizer._mock_edges.append(
            {
                "source_id": "agent:ReadOnlyAgent",
                "target_id": "policy-readonly",
                "edge_type": "self_governance",
                "artifact_class": "iam_policy",
            }
        )

        paths = await analyzer.detect_self_modification_paths()
        readonly_paths = [p for p in paths if p["agent_id"] == "ReadOnlyAgent"]
        assert len(readonly_paths) == 0

    @pytest.mark.asyncio
    async def test_full_analysis_includes_self_mod_paths(self, analyzer):
        """run_full_analysis includes self_modification_paths in results."""
        results = await analyzer.run_full_analysis()
        assert "self_modification_paths" in results


class TestAnalyzerCache:
    """Tests for analyzer caching."""

    def test_clear_cache(self, analyzer):
        """Test clearing the cache."""
        analyzer._escalation_paths_cache = ["cached"]
        analyzer.clear_cache()

        assert analyzer._escalation_paths_cache is None
        assert analyzer._coverage_gaps_cache is None
        assert analyzer._toxic_combinations_cache is None
