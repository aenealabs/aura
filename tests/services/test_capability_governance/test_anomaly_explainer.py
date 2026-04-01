"""
Tests for AnomalyExplainer (ADR-072).

Tests natural language explanation generation for anomalies.
"""

from datetime import datetime

import pytest

from src.services.capability_governance import (
    AgentContext,
    AnomalyResult,
    AnomalyType,
    CapabilityInvocation,
)
from src.services.capability_governance.anomaly_explainer import (
    AnomalyExplainer,
    get_anomaly_explainer,
    reset_anomaly_explainer,
)


class TestAnomalyExplainerFallback:
    """Tests for fallback explanation generation (no Bedrock)."""

    @pytest.mark.asyncio
    async def test_volume_anomaly_explanation(self):
        """Test explanation for volume anomaly."""
        explainer = AnomalyExplainer()  # No bedrock client = fallback mode

        anomaly = AnomalyResult(
            is_anomaly=True,
            score=0.85,
            anomaly_type=AnomalyType.VOLUME,
            details={"z_score": 3.5, "current_count": 50},
        )

        agent_context = AgentContext(
            agent_id="agent-001",
            agent_name="Coder Agent 1",
            agent_type="coder",
        )

        explanation = await explainer.explain_anomaly(anomaly, agent_context)

        assert "volume" in explanation.lower()
        assert "agent" in explanation.lower()
        assert len(explanation) > 50

    @pytest.mark.asyncio
    async def test_sequence_anomaly_explanation(self):
        """Test explanation for sequence anomaly."""
        explainer = AnomalyExplainer()

        anomaly = AnomalyResult(
            is_anomaly=True,
            score=0.7,
            anomaly_type=AnomalyType.SEQUENCE,
            details={"unseen_ratio": 0.8},
        )

        agent_context = AgentContext(
            agent_id="agent-001",
            agent_name="Reviewer Agent",
            agent_type="reviewer",
        )

        explanation = await explainer.explain_anomaly(anomaly, agent_context)

        assert "sequence" in explanation.lower()

    @pytest.mark.asyncio
    async def test_temporal_anomaly_explanation(self):
        """Test explanation for temporal anomaly."""
        explainer = AnomalyExplainer()

        anomaly = AnomalyResult(
            is_anomaly=True,
            score=1.0,
            anomaly_type=AnomalyType.TEMPORAL,
            details={"current_hour": 3, "typical_hours": [8, 9, 10, 11, 12]},
        )

        explanation = await explainer.explain_anomaly(anomaly)

        assert "temporal" in explanation.lower() or "hours" in explanation.lower()

    @pytest.mark.asyncio
    async def test_honeypot_anomaly_explanation(self):
        """Test explanation for honeypot anomaly."""
        explainer = AnomalyExplainer()

        anomaly = AnomalyResult(
            is_anomaly=True,
            score=1.0,
            anomaly_type=AnomalyType.HONEYPOT,
            details={"honeypot_name": "admin_override"},
        )

        agent_context = AgentContext(
            agent_id="agent-malicious-001",
            agent_name="Compromised Agent",
            agent_type="coder",
        )

        explanation = await explainer.explain_anomaly(anomaly, agent_context)

        assert "honeypot" in explanation.lower() or "critical" in explanation.lower()

    @pytest.mark.asyncio
    async def test_cross_agent_anomaly_explanation(self):
        """Test explanation for cross-agent anomaly."""
        explainer = AnomalyExplainer()

        anomaly = AnomalyResult(
            is_anomaly=True,
            score=0.8,
            anomaly_type=AnomalyType.CROSS_AGENT,
            details={
                "unique_agents": 5,
                "shared_resource": "sensitive_db",
                "cluster_ratio": 0.9,
            },
        )

        explanation = await explainer.explain_anomaly(anomaly)

        assert "cross" in explanation.lower() or "coordinated" in explanation.lower()

    @pytest.mark.asyncio
    async def test_ml_ensemble_anomaly_explanation(self):
        """Test explanation for ML ensemble anomaly."""
        explainer = AnomalyExplainer()

        anomaly = AnomalyResult(
            is_anomaly=True,
            score=0.75,
            anomaly_type=AnomalyType.ML_ENSEMBLE,
            details={"components_analyzed": 3},
        )

        explanation = await explainer.explain_anomaly(anomaly)

        assert "ensemble" in explanation.lower() or "anomaly" in explanation.lower()


class TestAnomalyExplainerWithHistory:
    """Tests for explanations with invocation history."""

    @pytest.mark.asyncio
    async def test_explanation_with_recent_history(self):
        """Test explanation includes recent history context."""
        explainer = AnomalyExplainer()

        anomaly = AnomalyResult(
            is_anomaly=True,
            score=0.85,
            anomaly_type=AnomalyType.VOLUME,
        )

        agent_context = AgentContext(
            agent_id="agent-001",
            agent_name="Test Agent",
            agent_type="coder",
        )

        recent_history = [
            CapabilityInvocation(
                agent_id="agent-001",
                tool_name="read_file",
                classification="SAFE",
                decision="ALLOW",
                timestamp=datetime(2026, 1, 27, 10, 0, 0),
            ),
            CapabilityInvocation(
                agent_id="agent-001",
                tool_name="write_file",
                classification="MONITORING",
                decision="ALLOW",
                timestamp=datetime(2026, 1, 27, 10, 1, 0),
            ),
        ]

        explanation = await explainer.explain_anomaly(
            anomaly, agent_context, recent_history
        )

        assert len(explanation) > 0

    @pytest.mark.asyncio
    async def test_explanation_with_empty_history(self):
        """Test explanation works with empty history."""
        explainer = AnomalyExplainer()

        anomaly = AnomalyResult(
            is_anomaly=True,
            score=0.9,
            anomaly_type=AnomalyType.SEQUENCE,
        )

        explanation = await explainer.explain_anomaly(anomaly, None, [])

        assert len(explanation) > 0


class TestAnomalyExplainerSeverity:
    """Tests for severity-based explanation content."""

    @pytest.mark.asyncio
    async def test_info_severity_explanation(self):
        """Test explanation for INFO severity anomaly."""
        explainer = AnomalyExplainer()

        anomaly = AnomalyResult(
            is_anomaly=False,
            score=0.3,
            anomaly_type=AnomalyType.VOLUME,
        )

        explanation = await explainer.explain_anomaly(anomaly)
        assert "low-severity" in explanation.lower() or "info" in explanation.lower()

    @pytest.mark.asyncio
    async def test_critical_severity_explanation(self):
        """Test explanation for CRITICAL severity anomaly."""
        explainer = AnomalyExplainer()

        anomaly = AnomalyResult(
            is_anomaly=True,
            score=0.95,
            anomaly_type=AnomalyType.VOLUME,
        )

        explanation = await explainer.explain_anomaly(anomaly)
        assert "critical" in explanation.lower()

    @pytest.mark.asyncio
    async def test_p1_severity_explanation(self):
        """Test explanation for P1 severity (honeypot) anomaly."""
        explainer = AnomalyExplainer()

        anomaly = AnomalyResult(
            is_anomaly=True,
            score=1.0,
            anomaly_type=AnomalyType.HONEYPOT,
        )

        explanation = await explainer.explain_anomaly(anomaly)
        # Should mention critical/P1 severity
        assert (
            "critical" in explanation.lower()
            or "p1" in explanation.lower()
            or "honeypot" in explanation.lower()
        )


class TestAnomalyExplainerBatch:
    """Tests for batch explanation generation."""

    @pytest.mark.asyncio
    async def test_explain_batch(self):
        """Test batch explanation of multiple anomalies."""
        explainer = AnomalyExplainer()

        anomalies = [
            (
                AnomalyResult(
                    is_anomaly=True,
                    score=0.8,
                    anomaly_type=AnomalyType.VOLUME,
                ),
                AgentContext(
                    agent_id="agent-001",
                    agent_name="Agent 1",
                    agent_type="coder",
                ),
            ),
            (
                AnomalyResult(
                    is_anomaly=True,
                    score=0.7,
                    anomaly_type=AnomalyType.SEQUENCE,
                ),
                AgentContext(
                    agent_id="agent-002",
                    agent_name="Agent 2",
                    agent_type="reviewer",
                ),
            ),
        ]

        explanations = await explainer.explain_batch(anomalies)

        assert len(explanations) == 2
        assert all(isinstance(e, str) for e in explanations)
        assert all(len(e) > 0 for e in explanations)


class TestAnomalyExplainerUnknownAgent:
    """Tests for handling unknown agent context."""

    @pytest.mark.asyncio
    async def test_explanation_without_agent_context(self):
        """Test explanation works without agent context."""
        explainer = AnomalyExplainer()

        anomaly = AnomalyResult(
            is_anomaly=True,
            score=0.85,
            anomaly_type=AnomalyType.VOLUME,
        )

        explanation = await explainer.explain_anomaly(anomaly, None)

        assert "unknown" in explanation.lower() or len(explanation) > 0

    @pytest.mark.asyncio
    async def test_explanation_with_minimal_context(self):
        """Test explanation with minimal agent context."""
        explainer = AnomalyExplainer()

        anomaly = AnomalyResult(
            is_anomaly=True,
            score=0.75,
            anomaly_type=AnomalyType.TEMPORAL,
        )

        agent_context = AgentContext(
            agent_id="agent-001",
            agent_name="Minimal Agent",
            agent_type="unknown",
        )

        explanation = await explainer.explain_anomaly(anomaly, agent_context)

        assert len(explanation) > 0


class TestAnomalyExplainerSingleton:
    """Tests for singleton pattern."""

    def test_get_singleton_returns_same_instance(self):
        """Test singleton returns same instance."""
        reset_anomaly_explainer()
        explainer1 = get_anomaly_explainer()
        explainer2 = get_anomaly_explainer()
        assert explainer1 is explainer2

    def test_reset_creates_new_instance(self):
        """Test reset creates new instance."""
        explainer1 = get_anomaly_explainer()
        reset_anomaly_explainer()
        explainer2 = get_anomaly_explainer()
        assert explainer1 is not explainer2


class TestAnomalyExplainerHistoryFormatting:
    """Tests for history formatting in prompts."""

    @pytest.mark.asyncio
    async def test_history_formatting(self):
        """Test invocation history is formatted correctly."""
        explainer = AnomalyExplainer()

        history = [
            CapabilityInvocation(
                agent_id="agent-001",
                tool_name="read_file",
                classification="SAFE",
                decision="ALLOW",
                timestamp=datetime(2026, 1, 27, 10, 0, 0),
            ),
            CapabilityInvocation(
                agent_id="agent-001",
                tool_name="dangerous_tool",
                classification="DANGEROUS",
                decision="DENY",
                timestamp=datetime(2026, 1, 27, 10, 1, 0),
            ),
        ]

        formatted = explainer._format_history(history)

        assert "read_file" in formatted
        assert "dangerous_tool" in formatted
        assert "ALLOW" in formatted
        assert "DENY" in formatted

    def test_empty_history_formatting(self):
        """Test empty history is handled gracefully."""
        explainer = AnomalyExplainer()

        formatted = explainer._format_history([])

        assert "no recent activity" in formatted.lower()

    def test_history_max_entries(self):
        """Test history respects max entries limit."""
        explainer = AnomalyExplainer()

        # Create 20 invocations
        history = [
            CapabilityInvocation(
                agent_id="agent-001",
                tool_name=f"tool_{i}",
                classification="SAFE",
                decision="ALLOW",
                timestamp=datetime(2026, 1, 27, 10, i, 0),
            )
            for i in range(20)
        ]

        formatted = explainer._format_history(history, max_entries=5)

        # Should only show last 5
        assert "tool_15" in formatted
        assert "tool_19" in formatted
        # Earlier tools should not be shown
        assert "tool_0" not in formatted
