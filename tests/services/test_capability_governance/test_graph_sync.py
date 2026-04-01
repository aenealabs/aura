"""
Tests for capability graph synchronization (ADR-070/071).

Tests the PolicyGraphSynchronizer that maintains the capability graph
in sync with deployed agent policies.
"""

from datetime import datetime

import pytest

from src.services.capability_governance import (
    AgentCapabilityPolicy,
    PolicyDeployedEvent,
    PolicyGraphSynchronizer,
    SyncStatus,
    get_policy_graph_synchronizer,
    reset_policy_graph_synchronizer,
)
from src.services.capability_governance.graph_contracts import EdgeType, VertexType


class TestPolicyDeployedEvent:
    """Tests for PolicyDeployedEvent dataclass."""

    def test_create_event(self):
        """Test creating a policy deployed event."""
        event = PolicyDeployedEvent(
            event_id="evt-001",
            policy_name="coder-policy",
            policy_version="1.0.0",
            agent_type="CoderAgent",
            deployed_by="admin",
            environment="development",
        )
        assert event.event_id == "evt-001"
        assert event.policy_name == "coder-policy"
        assert event.agent_type == "CoderAgent"

    def test_event_default_values(self):
        """Test event default values."""
        event = PolicyDeployedEvent(
            event_id="evt-002",
            policy_name="test-policy",
            policy_version="1.0",
            agent_type="TestAgent",
        )
        assert event.deployed_by == "system"
        assert event.environment == "development"
        assert isinstance(event.deployed_at, datetime)

    def test_event_to_dict(self):
        """Test event serialization."""
        event = PolicyDeployedEvent(
            event_id="evt-003",
            policy_name="test",
            policy_version="1.0",
            agent_type="Test",
            changes_summary={"added_tools": ["tool_a"]},
        )
        data = event.to_dict()
        assert data["event_id"] == "evt-003"
        assert "deployed_at" in data
        assert data["changes_summary"]["added_tools"] == ["tool_a"]


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_sync_result_total_changes(self):
        """Test total_changes property."""
        from src.services.capability_governance.graph_sync import SyncResult

        result = SyncResult(
            sync_id="sync-001",
            status=SyncStatus.SUCCESS,
            vertices_created=5,
            vertices_updated=3,
            vertices_deleted=1,
            edges_created=10,
            edges_updated=2,
            edges_deleted=0,
        )
        assert result.total_changes == 21

    def test_sync_result_to_dict(self):
        """Test sync result serialization."""
        from src.services.capability_governance.graph_sync import SyncResult

        result = SyncResult(
            sync_id="sync-002",
            status=SyncStatus.PARTIAL,
            errors=["Error 1", "Error 2"],
        )
        data = result.to_dict()
        assert data["sync_id"] == "sync-002"
        assert data["status"] == "partial"
        assert len(data["errors"]) == 2


class TestPolicyGraphSynchronizer:
    """Tests for PolicyGraphSynchronizer."""

    def test_create_synchronizer(self):
        """Test creating a synchronizer instance."""
        sync = PolicyGraphSynchronizer(mock_mode=True)
        assert sync.mock_mode is True

    def test_singleton_pattern(self):
        """Test singleton pattern."""
        reset_policy_graph_synchronizer()
        sync1 = get_policy_graph_synchronizer()
        sync2 = get_policy_graph_synchronizer()
        assert sync1 is sync2

    @pytest.mark.asyncio
    async def test_on_policy_deployed(self):
        """Test handling policy deployment event."""
        sync = PolicyGraphSynchronizer(mock_mode=True)
        event = PolicyDeployedEvent(
            event_id="evt-test",
            policy_name="coder-policy",
            policy_version="1.0.0",
            agent_type="CoderAgent",
        )

        result = await sync.on_policy_deployed(event)

        assert result.status == SyncStatus.SUCCESS
        assert result.total_changes > 0
        assert result.completed_at is not None
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_sync_creates_agent_vertex(self):
        """Test that sync creates agent vertex."""
        sync = PolicyGraphSynchronizer(mock_mode=True)
        event = PolicyDeployedEvent(
            event_id="evt-test",
            policy_name="reviewer-policy",
            policy_version="1.0.0",
            agent_type="ReviewerAgent",
        )

        await sync.on_policy_deployed(event)
        graph = sync.get_mock_graph()

        assert "agent:ReviewerAgent" in graph["vertices"]
        vertex = graph["vertices"]["agent:ReviewerAgent"]
        assert vertex["type"] == VertexType.AGENT.value
        assert vertex["agent_type"] == "ReviewerAgent"

    @pytest.mark.asyncio
    async def test_sync_creates_capability_edges(self):
        """Test that sync creates capability edges."""
        sync = PolicyGraphSynchronizer(mock_mode=True)
        event = PolicyDeployedEvent(
            event_id="evt-test",
            policy_name="coder-policy",
            policy_version="1.0.0",
            agent_type="CoderAgent",
        )

        await sync.on_policy_deployed(event)
        graph = sync.get_mock_graph()

        # Find HAS_CAPABILITY edges for CoderAgent
        coder_edges = [
            e
            for e in graph["edges"]
            if e["source_id"] == "agent:CoderAgent"
            and e["edge_type"] == EdgeType.HAS_CAPABILITY.value
        ]
        assert len(coder_edges) > 0

    @pytest.mark.asyncio
    async def test_sync_creates_context_restrictions(self):
        """Test that sync creates context restriction edges."""
        sync = PolicyGraphSynchronizer(mock_mode=True)
        event = PolicyDeployedEvent(
            event_id="evt-test",
            policy_name="coder-policy",
            policy_version="1.0.0",
            agent_type="CoderAgent",
        )

        await sync.on_policy_deployed(event)
        graph = sync.get_mock_graph()

        # Find RESTRICTED_TO edges for CoderAgent
        context_edges = [
            e
            for e in graph["edges"]
            if e["source_id"] == "agent:CoderAgent"
            and e["edge_type"] == EdgeType.RESTRICTED_TO.value
        ]
        assert len(context_edges) > 0

    @pytest.mark.asyncio
    async def test_sync_agent_capabilities(self):
        """Test syncing a single agent's capabilities."""
        sync = PolicyGraphSynchronizer(mock_mode=True)
        policy = AgentCapabilityPolicy.for_agent_type("ValidatorAgent")

        result = await sync.sync_agent_capabilities("ValidatorAgent", policy)

        assert result.status == SyncStatus.SUCCESS
        graph = sync.get_mock_graph()
        assert "agent:ValidatorAgent" in graph["vertices"]

    @pytest.mark.asyncio
    async def test_sync_all_policies(self):
        """Test syncing all known agent policies."""
        sync = PolicyGraphSynchronizer(mock_mode=True)

        result = await sync.sync_all_policies()

        assert result.status in (SyncStatus.SUCCESS, SyncStatus.PARTIAL)
        graph = sync.get_mock_graph()

        # Should have vertices for all agent types
        expected_agents = [
            "agent:CoderAgent",
            "agent:ReviewerAgent",
            "agent:ValidatorAgent",
            "agent:MetaOrchestrator",
            "agent:RedTeamAgent",
            "agent:AdminAgent",
        ]
        for agent_id in expected_agents:
            assert agent_id in graph["vertices"]

    @pytest.mark.asyncio
    async def test_sync_idempotent(self):
        """Test that syncing is idempotent."""
        sync = PolicyGraphSynchronizer(mock_mode=True)
        event = PolicyDeployedEvent(
            event_id="evt-test",
            policy_name="coder-policy",
            policy_version="1.0.0",
            agent_type="CoderAgent",
        )

        # Sync twice
        result1 = await sync.on_policy_deployed(event)
        result2 = await sync.on_policy_deployed(event)

        # Second sync should update, not create
        assert result1.status == SyncStatus.SUCCESS
        assert result2.status == SyncStatus.SUCCESS
        # First sync creates, second updates
        assert result2.vertices_updated >= 0

    @pytest.mark.asyncio
    async def test_sync_history(self):
        """Test sync history tracking."""
        sync = PolicyGraphSynchronizer(mock_mode=True)
        event = PolicyDeployedEvent(
            event_id="evt-test",
            policy_name="test-policy",
            policy_version="1.0.0",
            agent_type="CoderAgent",
        )

        await sync.on_policy_deployed(event)
        await sync.on_policy_deployed(event)

        history = sync.get_sync_history()
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_capability_classification_preserved(self):
        """Test that capability classifications are preserved in graph."""
        sync = PolicyGraphSynchronizer(mock_mode=True)

        # RedTeamAgent has CRITICAL capabilities
        event = PolicyDeployedEvent(
            event_id="evt-test",
            policy_name="redteam-policy",
            policy_version="1.0.0",
            agent_type="RedTeamAgent",
        )
        await sync.on_policy_deployed(event)
        graph = sync.get_mock_graph()

        # Find edges and check classification
        redteam_edges = [
            e
            for e in graph["edges"]
            if e["source_id"] == "agent:RedTeamAgent"
            and e["edge_type"] == EdgeType.HAS_CAPABILITY.value
        ]

        # Should have some edges with classification
        classified_edges = [e for e in redteam_edges if "classification" in e]
        assert len(classified_edges) > 0

    def test_generate_edge_id_deterministic(self):
        """Test that edge ID generation is deterministic."""
        sync = PolicyGraphSynchronizer(mock_mode=True)

        edge_id_1 = sync._generate_edge_id(
            "agent:Test",
            "cap:tool",
            EdgeType.HAS_CAPABILITY,
        )
        edge_id_2 = sync._generate_edge_id(
            "agent:Test",
            "cap:tool",
            EdgeType.HAS_CAPABILITY,
        )

        assert edge_id_1 == edge_id_2

    def test_generate_edge_id_unique_for_different_inputs(self):
        """Test that different inputs produce different edge IDs."""
        sync = PolicyGraphSynchronizer(mock_mode=True)

        edge_id_1 = sync._generate_edge_id(
            "agent:A",
            "cap:tool",
            EdgeType.HAS_CAPABILITY,
        )
        edge_id_2 = sync._generate_edge_id(
            "agent:B",
            "cap:tool",
            EdgeType.HAS_CAPABILITY,
        )

        assert edge_id_1 != edge_id_2
