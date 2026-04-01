"""
Tests for capability graph contracts (ADR-071).

Tests the dataclasses, enums, and contracts used for
capability graph analysis and visualization.
"""

from datetime import datetime, timezone

import pytest

from src.services.capability_governance import ToolClassification
from src.services.capability_governance.graph_contracts import (
    CapabilitySource,
    ConflictType,
    CoverageGap,
    EdgeType,
    EffectiveCapabilities,
    EffectiveCapability,
    EscalationPath,
    GraphEdge,
    GraphVertex,
    GraphVisualizationData,
    InheritanceNode,
    InheritanceTree,
    RiskLevel,
    ToxicCombination,
    VertexType,
)


class TestEnums:
    """Tests for graph-related enums."""

    def test_vertex_type_values(self):
        """Test VertexType enum values."""
        assert VertexType.AGENT.value == "agent"
        assert VertexType.CAPABILITY.value == "capability"
        assert VertexType.POLICY.value == "policy"
        assert VertexType.CONTEXT.value == "context"
        assert VertexType.AUDIT_EVENT.value == "audit_event"

    def test_edge_type_values(self):
        """Test EdgeType enum values."""
        assert EdgeType.HAS_CAPABILITY.value == "has_capability"
        assert EdgeType.INHERITS_FROM.value == "inherits_from"
        assert EdgeType.DELEGATES_TO.value == "delegates_to"
        assert EdgeType.REQUIRES.value == "requires"
        assert EdgeType.CONFLICTS_WITH.value == "conflicts_with"
        assert EdgeType.RESTRICTED_TO.value == "restricted_to"

    def test_risk_level_values(self):
        """Test RiskLevel enum values."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_conflict_type_values(self):
        """Test ConflictType enum values."""
        assert ConflictType.MUTUAL_EXCLUSION.value == "mutual_exclusion"
        assert ConflictType.SEPARATION_OF_DUTIES.value == "separation_of_duties"
        assert ConflictType.RESOURCE_CONTENTION.value == "resource_contention"
        assert ConflictType.PRIVILEGE_ESCALATION.value == "privilege_escalation"


class TestGraphVertex:
    """Tests for GraphVertex dataclass."""

    def test_create_agent_vertex(self):
        """Test creating an agent vertex."""
        vertex = GraphVertex(
            vertex_id="agent:CoderAgent",
            vertex_type=VertexType.AGENT,
            label="CoderAgent",
            properties=(("policy_version", "1.0"),),
        )
        assert vertex.vertex_id == "agent:CoderAgent"
        assert vertex.vertex_type == VertexType.AGENT
        assert vertex.label == "CoderAgent"

    def test_vertex_to_dict(self):
        """Test vertex serialization."""
        vertex = GraphVertex(
            vertex_id="cap:semantic_search",
            vertex_type=VertexType.CAPABILITY,
            label="semantic_search",
            properties=(("classification", "safe"),),
        )
        data = vertex.to_dict()
        assert data["vertex_id"] == "cap:semantic_search"
        assert data["vertex_type"] == "capability"
        assert data["properties"]["classification"] == "safe"

    def test_vertex_immutable(self):
        """Test that vertices are immutable."""
        vertex = GraphVertex(
            vertex_id="test",
            vertex_type=VertexType.AGENT,
            label="test",
        )
        with pytest.raises(AttributeError):
            vertex.vertex_id = "new_id"


class TestGraphEdge:
    """Tests for GraphEdge dataclass."""

    def test_create_edge(self):
        """Test creating a graph edge."""
        edge = GraphEdge(
            edge_id="edge:123",
            edge_type=EdgeType.HAS_CAPABILITY,
            source_id="agent:CoderAgent",
            target_id="cap:semantic_search",
        )
        assert edge.edge_type == EdgeType.HAS_CAPABILITY
        assert edge.source_id == "agent:CoderAgent"
        assert edge.target_id == "cap:semantic_search"

    def test_edge_to_dict(self):
        """Test edge serialization."""
        edge = GraphEdge(
            edge_id="edge:456",
            edge_type=EdgeType.INHERITS_FROM,
            source_id="agent:Child",
            target_id="agent:Parent",
            properties=(("inherited_at", "2026-01-27"),),
        )
        data = edge.to_dict()
        assert data["edge_type"] == "inherits_from"
        assert data["properties"]["inherited_at"] == "2026-01-27"


class TestEscalationPath:
    """Tests for EscalationPath dataclass."""

    def test_create_escalation_path(self):
        """Test creating an escalation path."""
        path = EscalationPath(
            path_id="path-001",
            source_agent="CoderAgent",
            target_capability="deploy_to_production",
            classification=ToolClassification.CRITICAL,
            path=("CoderAgent", "Orchestrator", "AdminAgent"),
            risk_score=0.95,
            risk_level=RiskLevel.CRITICAL,
        )
        assert path.source_agent == "CoderAgent"
        assert path.target_capability == "deploy_to_production"
        assert path.classification == ToolClassification.CRITICAL

    def test_path_length_property(self):
        """Test path_length property."""
        path = EscalationPath(
            path_id="path-002",
            source_agent="A",
            target_capability="cap",
            classification=ToolClassification.DANGEROUS,
            path=("A", "B", "C", "D"),
            risk_score=0.7,
            risk_level=RiskLevel.HIGH,
        )
        assert path.path_length == 4

    def test_is_critical_property(self):
        """Test is_critical property."""
        critical_path = EscalationPath(
            path_id="path-003",
            source_agent="Agent",
            target_capability="cap",
            classification=ToolClassification.CRITICAL,
            path=("Agent",),
            risk_score=0.9,
            risk_level=RiskLevel.CRITICAL,
        )
        assert critical_path.is_critical is True

        non_critical_path = EscalationPath(
            path_id="path-004",
            source_agent="Agent",
            target_capability="cap",
            classification=ToolClassification.DANGEROUS,
            path=("Agent",),
            risk_score=0.7,
            risk_level=RiskLevel.HIGH,
        )
        assert non_critical_path.is_critical is False

    def test_escalation_path_to_dict(self):
        """Test escalation path serialization."""
        path = EscalationPath(
            path_id="path-005",
            source_agent="Test",
            target_capability="test_cap",
            classification=ToolClassification.MONITORING,
            path=("Test",),
            risk_score=0.5,
            risk_level=RiskLevel.MEDIUM,
            description="Test path",
            mitigation_suggestion="Review policy",
        )
        data = path.to_dict()
        assert data["path_id"] == "path-005"
        assert data["classification"] == "monitoring"
        assert data["risk_level"] == "medium"
        assert "detection_time" in data


class TestCoverageGap:
    """Tests for CoverageGap dataclass."""

    def test_create_coverage_gap(self):
        """Test creating a coverage gap."""
        gap = CoverageGap(
            gap_id="gap-001",
            agent_name="CoderAgent",
            agent_type="CoderAgent",
            dangerous_capabilities=("commit_changes", "create_branch"),
            missing_capabilities=("query_audit_logs",),
            gap_type="missing_monitoring",
            risk_level=RiskLevel.HIGH,
            recommendation="Add MONITORING capabilities",
        )
        assert gap.agent_name == "CoderAgent"
        assert "commit_changes" in gap.dangerous_capabilities
        assert gap.gap_type == "missing_monitoring"

    def test_coverage_gap_to_dict(self):
        """Test coverage gap serialization."""
        gap = CoverageGap(
            gap_id="gap-002",
            agent_name="TestAgent",
            agent_type="TestAgent",
            dangerous_capabilities=("tool_a",),
            missing_capabilities=("tool_b",),
            gap_type="missing_read_operations",
            risk_level=RiskLevel.MEDIUM,
        )
        data = gap.to_dict()
        assert data["gap_id"] == "gap-002"
        assert data["gap_type"] == "missing_read_operations"
        assert isinstance(data["dangerous_capabilities"], list)


class TestToxicCombination:
    """Tests for ToxicCombination dataclass."""

    def test_create_toxic_combination(self):
        """Test creating a toxic combination."""
        combo = ToxicCombination(
            combination_id="toxic-001",
            agent_name="AdminAgent",
            capability_a="modify_iam_policy",
            capability_b="access_secrets",
            conflict_type=ConflictType.PRIVILEGE_ESCALATION,
            severity=RiskLevel.CRITICAL,
            policy_reference="ADR-066",
        )
        assert combo.capability_a == "modify_iam_policy"
        assert combo.conflict_type == ConflictType.PRIVILEGE_ESCALATION
        assert combo.severity == RiskLevel.CRITICAL

    def test_toxic_combination_to_dict(self):
        """Test toxic combination serialization."""
        combo = ToxicCombination(
            combination_id="toxic-002",
            agent_name="TestAgent",
            capability_a="cap_a",
            capability_b="cap_b",
            conflict_type=ConflictType.SEPARATION_OF_DUTIES,
            severity=RiskLevel.HIGH,
            description="Cannot hold both",
            remediation="Split across agents",
        )
        data = combo.to_dict()
        assert data["conflict_type"] == "separation_of_duties"
        assert data["severity"] == "high"
        assert data["remediation"] == "Split across agents"


class TestInheritanceTree:
    """Tests for InheritanceNode and InheritanceTree dataclasses."""

    def test_create_inheritance_node(self):
        """Test creating an inheritance node."""
        node = InheritanceNode(
            agent_name="CoderAgent",
            agent_type="CoderAgent",
            tier=0,
            direct_capabilities=["semantic_search", "query_code_graph"],
            inherited_capabilities=[],
        )
        assert node.tier == 0
        assert len(node.direct_capabilities) == 2
        assert len(node.children) == 0

    def test_inheritance_node_with_children(self):
        """Test inheritance node with children."""
        child = InheritanceNode(
            agent_name="ChildAgent",
            agent_type="CoderAgent",
            tier=1,
            direct_capabilities=["new_cap"],
            inherited_capabilities=["parent_cap"],
        )
        parent = InheritanceNode(
            agent_name="ParentAgent",
            agent_type="Orchestrator",
            tier=0,
            direct_capabilities=["parent_cap"],
            inherited_capabilities=[],
            children=[child],
        )
        assert len(parent.children) == 1
        assert parent.children[0].agent_name == "ChildAgent"

    def test_inheritance_tree(self):
        """Test creating an inheritance tree."""
        root = InheritanceNode(
            agent_name="Root",
            agent_type="Orchestrator",
            tier=0,
            direct_capabilities=["cap1", "cap2"],
            inherited_capabilities=[],
        )
        tree = InheritanceTree(
            root_agent="Root",
            root_type="Orchestrator",
            tree=root,
            depth=1,
            total_agents=1,
            total_direct_capabilities=2,
            total_inherited_capabilities=0,
        )
        assert tree.depth == 1
        assert tree.total_direct_capabilities == 2

    def test_inheritance_tree_to_dict(self):
        """Test inheritance tree serialization."""
        root = InheritanceNode(
            agent_name="Test",
            agent_type="Test",
            tier=0,
            direct_capabilities=[],
            inherited_capabilities=[],
        )
        tree = InheritanceTree(
            root_agent="Test",
            root_type="Test",
            tree=root,
            depth=1,
            total_agents=1,
            total_direct_capabilities=0,
            total_inherited_capabilities=0,
        )
        data = tree.to_dict()
        assert data["root_agent"] == "Test"
        assert "tree" in data
        assert "calculated_at" in data


class TestEffectiveCapabilities:
    """Tests for CapabilitySource, EffectiveCapability, and EffectiveCapabilities."""

    def test_create_capability_source(self):
        """Test creating a capability source."""
        source = CapabilitySource(
            source_type="policy",
            source_id="CoderAgent-policy",
            granted_at=datetime.now(timezone.utc),
        )
        assert source.source_type == "policy"
        assert source.source_id == "CoderAgent-policy"

    def test_effective_capability(self):
        """Test creating an effective capability."""
        source = CapabilitySource(
            source_type="dynamic_grant",
            source_id="grant-123",
        )
        cap = EffectiveCapability(
            tool_name="provision_sandbox",
            classification=ToolClassification.CRITICAL,
            actions=["execute"],
            source=source,
            is_temporary=True,
            context_restrictions=["sandbox"],
        )
        assert cap.tool_name == "provision_sandbox"
        assert cap.is_temporary is True
        assert "sandbox" in cap.context_restrictions

    def test_effective_capabilities(self):
        """Test creating effective capabilities collection."""
        source = CapabilitySource(source_type="policy", source_id="test")
        caps = EffectiveCapabilities(
            agent_id="agent-001",
            agent_name="TestAgent",
            agent_type="CoderAgent",
            execution_context="development",
            capabilities=[
                EffectiveCapability(
                    tool_name="semantic_search",
                    classification=ToolClassification.SAFE,
                    actions=["execute"],
                    source=source,
                ),
                EffectiveCapability(
                    tool_name="destroy_sandbox",
                    classification=ToolClassification.DANGEROUS,
                    actions=["execute"],
                    source=source,
                ),
            ],
            policy_version="1.0",
        )
        assert caps.capability_count == 2
        assert caps.has_dangerous is True
        assert caps.has_critical is False

    def test_effective_capabilities_get_by_classification(self):
        """Test filtering capabilities by classification."""
        source = CapabilitySource(source_type="policy", source_id="test")
        caps = EffectiveCapabilities(
            agent_id="test",
            agent_name="Test",
            agent_type="Test",
            execution_context="dev",
            capabilities=[
                EffectiveCapability(
                    tool_name="safe_tool",
                    classification=ToolClassification.SAFE,
                    actions=["read"],
                    source=source,
                ),
                EffectiveCapability(
                    tool_name="dangerous_tool",
                    classification=ToolClassification.DANGEROUS,
                    actions=["write"],
                    source=source,
                ),
            ],
        )
        safe_caps = caps.get_by_classification(ToolClassification.SAFE)
        assert len(safe_caps) == 1
        assert safe_caps[0].tool_name == "safe_tool"


class TestGraphVisualizationData:
    """Tests for GraphVisualizationData."""

    def test_create_visualization_data(self):
        """Test creating visualization data."""
        viz = GraphVisualizationData()
        assert len(viz.nodes) == 0
        assert len(viz.edges) == 0

    def test_add_agent_node(self):
        """Test adding an agent node."""
        viz = GraphVisualizationData()
        viz.add_agent_node(
            agent_id="CoderAgent",
            agent_type="CoderAgent",
            capabilities_count=5,
            has_escalation_risk=True,
        )
        assert len(viz.nodes) == 1
        assert viz.nodes[0]["type"] == "agent"
        assert viz.nodes[0]["color"] == "#3B82F6"
        assert viz.nodes[0]["has_escalation_risk"] is True

    def test_add_capability_node(self):
        """Test adding capability nodes with correct colors."""
        viz = GraphVisualizationData()

        viz.add_capability_node("safe_tool", ToolClassification.SAFE)
        viz.add_capability_node("monitoring_tool", ToolClassification.MONITORING)
        viz.add_capability_node("dangerous_tool", ToolClassification.DANGEROUS)
        viz.add_capability_node("critical_tool", ToolClassification.CRITICAL)

        assert len(viz.nodes) == 4
        assert viz.nodes[0]["color"] == "#10B981"  # Green for SAFE
        assert viz.nodes[1]["color"] == "#F59E0B"  # Amber for MONITORING
        assert viz.nodes[2]["color"] == "#EA580C"  # Orange for DANGEROUS
        assert viz.nodes[3]["color"] == "#DC2626"  # Red for CRITICAL

    def test_add_edge(self):
        """Test adding edges with correct styles."""
        viz = GraphVisualizationData()

        viz.add_edge("agent", "cap", EdgeType.HAS_CAPABILITY)
        viz.add_edge("child", "parent", EdgeType.INHERITS_FROM)
        viz.add_edge("parent", "child", EdgeType.DELEGATES_TO, is_escalation_path=True)

        assert len(viz.edges) == 3
        assert viz.edges[0]["style"] == "solid"
        assert viz.edges[1]["style"] == "dashed"
        assert viz.edges[2]["is_escalation_path"] is True
        assert viz.edges[2]["color"] == "#DC2626"  # Red for escalation

    def test_to_dict(self):
        """Test visualization data serialization."""
        viz = GraphVisualizationData(metadata={"test": "value"})
        viz.add_agent_node("Agent", "Agent", 3, False)
        viz.add_capability_node("cap", ToolClassification.SAFE)
        viz.add_edge("Agent", "cap_cap", EdgeType.HAS_CAPABILITY)

        data = viz.to_dict()
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1
        assert data["metadata"]["test"] == "value"
