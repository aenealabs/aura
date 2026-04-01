"""
Tests for anomaly detection contracts (ADR-072).

Tests the dataclasses and enums used for ML-based anomaly detection.
"""

from datetime import datetime

import pytest

from src.services.capability_governance import (
    AgentBehaviorFeatures,
    AgentContext,
    AlertSeverity,
    AnomalyAlert,
    AnomalyDetectionConfig,
    AnomalyResult,
    AnomalyType,
    CapabilityInvocation,
    HoneypotCapability,
    HoneypotResult,
    InvocationContext,
    QuarantineReason,
    QuarantineRecord,
    StatisticalBaseline,
)


class TestAnomalyType:
    """Tests for AnomalyType enum."""

    def test_all_anomaly_types_defined(self):
        """Test all expected anomaly types are defined."""
        expected = {
            "volume",
            "sequence",
            "temporal",
            "context",
            "cross_agent",
            "honeypot",
            "ml_ensemble",
        }
        actual = {t.value for t in AnomalyType}
        assert actual == expected

    def test_enum_values_are_strings(self):
        """Test enum values are lowercase strings."""
        for anomaly_type in AnomalyType:
            assert isinstance(anomaly_type.value, str)
            assert anomaly_type.value == anomaly_type.value.lower()


class TestAlertSeverity:
    """Tests for AlertSeverity enum."""

    def test_all_severity_levels_defined(self):
        """Test all expected severity levels are defined."""
        expected = {"info", "suspicious", "alert", "critical", "P1"}
        actual = {s.value for s in AlertSeverity}
        assert actual == expected

    def test_p1_is_highest_severity(self):
        """Test P1 represents the highest severity (honeypot trigger)."""
        assert AlertSeverity.P1.value == "P1"


class TestAnomalyResult:
    """Tests for AnomalyResult dataclass."""

    def test_create_anomaly_result(self):
        """Test creating an anomaly result."""
        result = AnomalyResult(
            is_anomaly=True,
            score=0.85,
            anomaly_type=AnomalyType.VOLUME,
            details={"z_score": 3.5},
        )
        assert result.is_anomaly is True
        assert result.score == 0.85
        assert result.anomaly_type == AnomalyType.VOLUME

    def test_score_validation_lower_bound(self):
        """Test score must be >= 0.0."""
        with pytest.raises(ValueError, match="Score must be between"):
            AnomalyResult(
                is_anomaly=False,
                score=-0.1,
                anomaly_type=AnomalyType.VOLUME,
            )

    def test_score_validation_upper_bound(self):
        """Test score must be <= 1.0."""
        with pytest.raises(ValueError, match="Score must be between"):
            AnomalyResult(
                is_anomaly=True,
                score=1.5,
                anomaly_type=AnomalyType.VOLUME,
            )

    def test_severity_info_threshold(self):
        """Test INFO severity for scores < 0.5."""
        result = AnomalyResult(
            is_anomaly=False,
            score=0.3,
            anomaly_type=AnomalyType.VOLUME,
        )
        assert result.severity == AlertSeverity.INFO

    def test_severity_suspicious_threshold(self):
        """Test SUSPICIOUS severity for scores 0.5-0.7."""
        result = AnomalyResult(
            is_anomaly=True,
            score=0.6,
            anomaly_type=AnomalyType.SEQUENCE,
        )
        assert result.severity == AlertSeverity.SUSPICIOUS

    def test_severity_alert_threshold(self):
        """Test ALERT severity for scores 0.7-0.9."""
        result = AnomalyResult(
            is_anomaly=True,
            score=0.8,
            anomaly_type=AnomalyType.TEMPORAL,
        )
        assert result.severity == AlertSeverity.ALERT

    def test_severity_critical_threshold(self):
        """Test CRITICAL severity for scores > 0.9."""
        result = AnomalyResult(
            is_anomaly=True,
            score=0.95,
            anomaly_type=AnomalyType.CROSS_AGENT,
        )
        assert result.severity == AlertSeverity.CRITICAL

    def test_honeypot_always_p1(self):
        """Test honeypot anomalies always have P1 severity."""
        result = AnomalyResult(
            is_anomaly=True,
            score=0.1,  # Even low score
            anomaly_type=AnomalyType.HONEYPOT,
        )
        assert result.severity == AlertSeverity.P1

    def test_to_dict_serialization(self):
        """Test serialization to dictionary."""
        result = AnomalyResult(
            is_anomaly=True,
            score=0.75,
            anomaly_type=AnomalyType.VOLUME,
            details={"z_score": 3.2},
            explanation="Test explanation",
        )
        d = result.to_dict()
        assert d["is_anomaly"] is True
        assert d["score"] == 0.75
        assert d["anomaly_type"] == "volume"
        assert d["severity"] == "alert"
        assert d["details"]["z_score"] == 3.2
        assert d["explanation"] == "Test explanation"


class TestStatisticalBaseline:
    """Tests for StatisticalBaseline dataclass."""

    def test_create_baseline(self):
        """Test creating a statistical baseline."""
        baseline = StatisticalBaseline(
            agent_type="coder",
            tool_classification="SAFE",
            mean_hourly_count=15.0,
            std_hourly_count=5.0,
        )
        assert baseline.agent_type == "coder"
        assert baseline.mean_hourly_count == 15.0

    def test_default_active_hours(self):
        """Test default active hours (8am-8pm)."""
        baseline = StatisticalBaseline(agent_type="test")
        assert baseline.active_hours == list(range(8, 20))

    def test_to_dict_and_from_dict(self):
        """Test round-trip serialization."""
        original = StatisticalBaseline(
            agent_type="reviewer",
            tool_classification="MONITORING",
            mean_hourly_count=10.0,
            std_hourly_count=3.0,
            typical_sequences=[("a", "b", "c"), ("x", "y", "z")],
            active_hours=[9, 10, 11, 12, 13, 14, 15, 16, 17],
        )
        d = original.to_dict()
        restored = StatisticalBaseline.from_dict(d)

        assert restored.agent_type == original.agent_type
        assert restored.mean_hourly_count == original.mean_hourly_count
        assert restored.typical_sequences == original.typical_sequences
        assert restored.active_hours == original.active_hours


class TestAgentBehaviorFeatures:
    """Tests for AgentBehaviorFeatures dataclass."""

    def test_create_features(self):
        """Test creating behavior features."""
        features = AgentBehaviorFeatures(
            agent_id="agent-001",
            agent_type="coder",
            invocations_1min=5,
            invocations_5min=20,
            dangerous_ratio=0.1,
        )
        assert features.agent_id == "agent-001"
        assert features.invocations_1min == 5
        assert features.dangerous_ratio == 0.1

    def test_to_feature_vector(self):
        """Test conversion to numeric feature vector."""
        features = AgentBehaviorFeatures(
            agent_id="agent-001",
            agent_type="coder",
            invocations_1min=5,
            invocations_5min=20,
            invocations_1hr=100,
            dangerous_ratio=0.1,
            hour_of_day=14,
        )
        vector = features.to_feature_vector()
        assert isinstance(vector, list)
        assert all(isinstance(v, float) for v in vector)
        assert vector[0] == 5.0  # invocations_1min
        assert vector[9] == 14.0  # hour_of_day

    def test_to_dict(self):
        """Test serialization to dictionary."""
        features = AgentBehaviorFeatures(
            agent_id="agent-001",
            agent_type="coder",
        )
        d = features.to_dict()
        assert d["agent_id"] == "agent-001"
        assert d["agent_type"] == "coder"


class TestHoneypotCapability:
    """Tests for HoneypotCapability dataclass."""

    def test_create_honeypot(self):
        """Test creating a honeypot capability."""
        honeypot = HoneypotCapability(
            name="test_honeypot",
            description="A test honeypot",
            classification="CRITICAL",
            legitimate_use=False,
            alert_severity=AlertSeverity.P1,
        )
        assert honeypot.name == "test_honeypot"
        assert honeypot.legitimate_use is False
        assert honeypot.alert_severity == AlertSeverity.P1

    def test_to_dict(self):
        """Test serialization to dictionary."""
        honeypot = HoneypotCapability(
            name="admin_override",
            description="Admin override",
        )
        d = honeypot.to_dict()
        assert d["name"] == "admin_override"
        assert d["alert_severity"] == "P1"


class TestHoneypotResult:
    """Tests for HoneypotResult dataclass."""

    def test_not_triggered(self):
        """Test result when honeypot not triggered."""
        result = HoneypotResult(triggered=False)
        assert result.triggered is False
        assert result.honeypot_name is None
        assert result.action_taken is None

    def test_triggered(self):
        """Test result when honeypot triggered."""
        result = HoneypotResult(
            triggered=True,
            honeypot_name="admin_override",
            action_taken="quarantine",
            agent_id="agent-malicious-001",
        )
        assert result.triggered is True
        assert result.honeypot_name == "admin_override"
        assert result.action_taken == "quarantine"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = HoneypotResult(
            triggered=True,
            honeypot_name="export_all_credentials",
            action_taken="quarantine",
            agent_id="agent-001",
        )
        d = result.to_dict()
        assert d["triggered"] is True
        assert d["honeypot_name"] == "export_all_credentials"


class TestQuarantineRecord:
    """Tests for QuarantineRecord dataclass."""

    def test_create_active_quarantine(self):
        """Test creating an active quarantine record."""
        record = QuarantineRecord(
            agent_id="agent-001",
            reason=QuarantineReason.HONEYPOT_TRIGGERED,
            triggered_by="admin_override",
            anomaly_score=1.0,
        )
        assert record.is_active is True
        assert record.agent_id == "agent-001"
        assert record.reason == QuarantineReason.HONEYPOT_TRIGGERED

    def test_released_quarantine(self):
        """Test released quarantine is not active."""
        record = QuarantineRecord(
            agent_id="agent-001",
            reason=QuarantineReason.HITL_APPROVED,
            triggered_by="critical_anomaly",
            released_at=datetime.utcnow(),
            hitl_approved_by="admin@example.com",
        )
        assert record.is_active is False

    def test_to_dict(self):
        """Test serialization to dictionary."""
        record = QuarantineRecord(
            agent_id="agent-001",
            reason=QuarantineReason.HONEYPOT_TRIGGERED,
            triggered_by="export_all_credentials",
            anomaly_score=1.0,
            notes="Automatic quarantine",
        )
        d = record.to_dict()
        assert d["agent_id"] == "agent-001"
        assert d["reason"] == "honeypot_triggered"
        assert d["is_active"] is True


class TestInvocationContext:
    """Tests for InvocationContext dataclass."""

    def test_create_context(self):
        """Test creating an invocation context."""
        context = InvocationContext(
            session_id="sess-001",
            parent_agent="orchestrator-001",
            environment="production",
            tenant_id="tenant-123",
        )
        assert context.session_id == "sess-001"
        assert context.environment == "production"

    def test_default_environment(self):
        """Test default environment is development."""
        context = InvocationContext(session_id="sess-001")
        assert context.environment == "development"


class TestCapabilityInvocation:
    """Tests for CapabilityInvocation dataclass."""

    def test_create_invocation(self):
        """Test creating a capability invocation record."""
        invocation = CapabilityInvocation(
            agent_id="agent-001",
            tool_name="semantic_search",
            classification="SAFE",
            decision="ALLOW",
            latency_ms=45.5,
        )
        assert invocation.agent_id == "agent-001"
        assert invocation.tool_name == "semantic_search"
        assert invocation.decision == "ALLOW"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        invocation = CapabilityInvocation(
            agent_id="agent-001",
            tool_name="provision_sandbox",
            classification="DANGEROUS",
            decision="DENY",
        )
        d = invocation.to_dict()
        assert d["agent_id"] == "agent-001"
        assert d["classification"] == "DANGEROUS"


class TestAgentContext:
    """Tests for AgentContext dataclass."""

    def test_create_agent_context(self):
        """Test creating an agent context."""
        context = AgentContext(
            agent_id="agent-001",
            agent_name="Coder Agent 1",
            agent_type="coder",
            risk_score=0.15,
        )
        assert context.agent_id == "agent-001"
        assert context.risk_score == 0.15

    def test_to_dict(self):
        """Test serialization to dictionary."""
        context = AgentContext(
            agent_id="agent-001",
            agent_name="Test Agent",
            agent_type="reviewer",
        )
        d = context.to_dict()
        assert d["agent_name"] == "Test Agent"
        assert d["risk_score"] == 0.0


class TestAnomalyDetectionConfig:
    """Tests for AnomalyDetectionConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AnomalyDetectionConfig()
        assert config.volume_z_score_threshold == 3.0
        assert config.sequence_unseen_ratio_threshold == 0.5
        assert config.log_only_threshold == 0.5
        assert config.alert_threshold == 0.9
        assert config.hitl_required_for_ml_quarantine is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = AnomalyDetectionConfig(
            volume_z_score_threshold=2.5,
            rate_limit_factor=0.05,
        )
        assert config.volume_z_score_threshold == 2.5
        assert config.rate_limit_factor == 0.05

    def test_to_dict(self):
        """Test serialization to dictionary."""
        config = AnomalyDetectionConfig()
        d = config.to_dict()
        assert "volume_z_score_threshold" in d
        assert "hitl_required_for_ml_quarantine" in d


class TestAnomalyAlert:
    """Tests for AnomalyAlert dataclass."""

    def test_create_alert(self):
        """Test creating an anomaly alert."""
        result = AnomalyResult(
            is_anomaly=True,
            score=0.85,
            anomaly_type=AnomalyType.VOLUME,
        )
        alert = AnomalyAlert(
            alert_id="alert-001",
            agent_id="agent-001",
            anomaly_result=result,
        )
        assert alert.alert_id == "alert-001"
        assert alert.acknowledged is False
        assert alert.false_positive is None

    def test_acknowledged_alert(self):
        """Test acknowledging an alert."""
        result = AnomalyResult(
            is_anomaly=True,
            score=0.75,
            anomaly_type=AnomalyType.SEQUENCE,
        )
        alert = AnomalyAlert(
            alert_id="alert-001",
            agent_id="agent-001",
            anomaly_result=result,
            acknowledged=True,
            acknowledged_by="admin@example.com",
            acknowledged_at=datetime.utcnow(),
            false_positive=True,
            notes="Legitimate workflow change",
        )
        assert alert.acknowledged is True
        assert alert.false_positive is True

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = AnomalyResult(
            is_anomaly=True,
            score=0.9,
            anomaly_type=AnomalyType.HONEYPOT,
        )
        alert = AnomalyAlert(
            alert_id="alert-001",
            agent_id="agent-001",
            anomaly_result=result,
        )
        d = alert.to_dict()
        assert d["alert_id"] == "alert-001"
        assert d["anomaly_result"]["anomaly_type"] == "honeypot"
