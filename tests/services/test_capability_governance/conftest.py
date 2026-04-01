"""
Pytest fixtures for capability governance tests.

Provides common fixtures for testing the capability governance framework.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.capability_governance import (
    AgentCapabilityPolicy,
    AuditConfig,
    CapabilityAuditService,
    CapabilityCheckResult,
    CapabilityContext,
    CapabilityDecision,
    CapabilityEnforcementMiddleware,
    CapabilityEscalationRequest,
    CapabilityRegistry,
    CapabilityScope,
    DynamicCapabilityGrant,
    DynamicGrantManager,
    GrantManagerConfig,
    MetricsConfig,
    ToolCapability,
    ToolClassification,
    reset_anomaly_explainer,
    reset_audit_service,
    reset_capability_graph_analyzer,
    reset_capability_middleware,
    reset_capability_registry,
    reset_grant_manager,
    reset_honeypot_detector,
    reset_metrics_publisher,
    reset_policy_graph_synchronizer,
    reset_policy_repository,
    reset_policy_simulator,
    reset_policy_validator,
    reset_statistical_detector,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singleton instances before each test."""
    reset_policy_repository()
    reset_capability_middleware()
    reset_audit_service()
    reset_grant_manager()
    reset_metrics_publisher()
    reset_capability_registry()
    reset_capability_graph_analyzer()
    reset_policy_graph_synchronizer()
    reset_statistical_detector()
    reset_honeypot_detector()
    reset_anomaly_explainer()
    reset_policy_validator()
    reset_policy_simulator()
    yield
    reset_policy_repository()
    reset_capability_middleware()
    reset_audit_service()
    reset_grant_manager()
    reset_metrics_publisher()
    reset_capability_registry()
    reset_capability_graph_analyzer()
    reset_policy_graph_synchronizer()
    reset_statistical_detector()
    reset_honeypot_detector()
    reset_anomaly_explainer()
    reset_policy_validator()
    reset_policy_simulator()


@pytest.fixture
def sample_coder_context() -> CapabilityContext:
    """Create a sample CoderAgent context."""
    return CapabilityContext(
        agent_id="coder-agent-001",
        agent_type="CoderAgent",
        tool_name="semantic_search",
        action="execute",
        execution_context="development",
    )


@pytest.fixture
def sample_reviewer_context() -> CapabilityContext:
    """Create a sample ReviewerAgent context."""
    return CapabilityContext(
        agent_id="reviewer-agent-001",
        agent_type="ReviewerAgent",
        tool_name="query_code_graph",
        action="read",
        execution_context="development",
    )


@pytest.fixture
def sample_orchestrator_context() -> CapabilityContext:
    """Create a sample MetaOrchestrator context."""
    return CapabilityContext(
        agent_id="orchestrator-001",
        agent_type="MetaOrchestrator",
        tool_name="index_code_embedding",
        action="execute",
        execution_context="development",
    )


@pytest.fixture
def sample_redteam_context() -> CapabilityContext:
    """Create a sample RedTeamAgent context."""
    return CapabilityContext(
        agent_id="redteam-agent-001",
        agent_type="RedTeamAgent",
        tool_name="provision_sandbox",
        action="execute",
        execution_context="sandbox",
    )


@pytest.fixture
def sample_production_context() -> CapabilityContext:
    """Create a context for production environment."""
    return CapabilityContext(
        agent_id="coder-agent-001",
        agent_type="CoderAgent",
        tool_name="deploy_to_production",
        action="execute",
        execution_context="production",
    )


@pytest.fixture
def child_agent_context() -> CapabilityContext:
    """Create a child agent context with parent."""
    return CapabilityContext(
        agent_id="child-agent-001",
        agent_type="CoderAgent",
        tool_name="semantic_search",
        action="execute",
        execution_context="development",
        parent_agent_id="parent-orchestrator-001",
    )


@pytest.fixture
def coder_policy() -> AgentCapabilityPolicy:
    """Get CoderAgent default policy."""
    return AgentCapabilityPolicy.for_agent_type("CoderAgent")


@pytest.fixture
def reviewer_policy() -> AgentCapabilityPolicy:
    """Get ReviewerAgent default policy."""
    return AgentCapabilityPolicy.for_agent_type("ReviewerAgent")


@pytest.fixture
def orchestrator_policy() -> AgentCapabilityPolicy:
    """Get MetaOrchestrator default policy."""
    return AgentCapabilityPolicy.for_agent_type("MetaOrchestrator")


@pytest.fixture
def redteam_policy() -> AgentCapabilityPolicy:
    """Get RedTeamAgent default policy."""
    return AgentCapabilityPolicy.for_agent_type("RedTeamAgent")


@pytest.fixture
def mock_audit_service() -> CapabilityAuditService:
    """Create a mock audit service."""
    service = MagicMock(spec=CapabilityAuditService)
    service.log = AsyncMock()
    service.flush = AsyncMock()
    return service


@pytest.fixture
def mock_grant_service() -> DynamicGrantManager:
    """Create a mock grant service."""
    service = MagicMock(spec=DynamicGrantManager)
    service.get_active_grants = AsyncMock(return_value=[])
    service.increment_usage = AsyncMock()
    service.store_grant = AsyncMock()
    service.revoke_grant = AsyncMock()
    return service


@pytest.fixture
def mock_metrics_publisher() -> MagicMock:
    """Create a mock metrics publisher."""
    publisher = MagicMock()
    publisher.record_check = AsyncMock()
    publisher.record_escalation = AsyncMock()
    publisher.record_violation = AsyncMock()
    return publisher


@pytest.fixture
def mock_hitl_service() -> MagicMock:
    """Create a mock HITL service."""
    service = MagicMock()
    service.notify_capability_escalation = AsyncMock()
    return service


@pytest.fixture
def middleware(
    mock_audit_service: CapabilityAuditService,
    mock_grant_service: DynamicGrantManager,
    mock_metrics_publisher: MagicMock,
) -> CapabilityEnforcementMiddleware:
    """Create a middleware with mocked dependencies."""
    return CapabilityEnforcementMiddleware(
        audit_service=mock_audit_service,
        grant_service=mock_grant_service,
        metrics_publisher=mock_metrics_publisher,
    )


@pytest.fixture
def middleware_with_hitl(
    mock_audit_service: CapabilityAuditService,
    mock_grant_service: DynamicGrantManager,
    mock_metrics_publisher: MagicMock,
    mock_hitl_service: MagicMock,
) -> CapabilityEnforcementMiddleware:
    """Create a middleware with HITL service."""
    return CapabilityEnforcementMiddleware(
        audit_service=mock_audit_service,
        grant_service=mock_grant_service,
        metrics_publisher=mock_metrics_publisher,
        hitl_service=mock_hitl_service,
    )


@pytest.fixture
def sample_grant() -> DynamicCapabilityGrant:
    """Create a sample dynamic grant."""
    now = datetime.now(timezone.utc)
    return DynamicCapabilityGrant(
        grant_id="grant-test-001",
        agent_id="coder-agent-001",
        tool_name="provision_sandbox",
        action="execute",
        scope=CapabilityScope.SESSION,
        constraints={"max_sandboxes": 1},
        granted_by="cap-esc-test-001",
        approver="admin@example.com",
        granted_at=now,
        expires_at=now + timedelta(hours=1),
    )


@pytest.fixture
def expired_grant() -> DynamicCapabilityGrant:
    """Create an expired dynamic grant."""
    now = datetime.now(timezone.utc)
    return DynamicCapabilityGrant(
        grant_id="grant-expired-001",
        agent_id="coder-agent-001",
        tool_name="provision_sandbox",
        action="execute",
        scope=CapabilityScope.SESSION,
        constraints={},
        granted_by="cap-esc-test-002",
        approver="admin@example.com",
        granted_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
    )


@pytest.fixture
def revoked_grant() -> DynamicCapabilityGrant:
    """Create a revoked dynamic grant."""
    now = datetime.now(timezone.utc)
    return DynamicCapabilityGrant(
        grant_id="grant-revoked-001",
        agent_id="coder-agent-001",
        tool_name="provision_sandbox",
        action="execute",
        scope=CapabilityScope.SESSION,
        constraints={},
        granted_by="cap-esc-test-003",
        approver="admin@example.com",
        granted_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=1),
        revoked=True,
        revoked_at=now - timedelta(minutes=30),
        revoked_reason="Security review",
    )


@pytest.fixture
def sample_escalation_request() -> CapabilityEscalationRequest:
    """Create a sample escalation request."""
    now = datetime.now(timezone.utc)
    return CapabilityEscalationRequest(
        request_id="cap-esc-sample-001",
        agent_id="coder-agent-001",
        agent_type="CoderAgent",
        requested_tool="provision_sandbox",
        requested_action="execute",
        context="development",
        justification="Need sandbox to test security patch",
        task_description="Validate CVE-2026-1234 patch",
        expires_at=now + timedelta(minutes=15),
    )


@pytest.fixture
def sample_check_result() -> CapabilityCheckResult:
    """Create a sample capability check result."""
    return CapabilityCheckResult(
        decision=CapabilityDecision.ALLOW,
        tool_name="semantic_search",
        agent_id="coder-agent-001",
        agent_type="CoderAgent",
        action="execute",
        context="development",
        reason="Allowed by CoderAgent policy",
        policy_version="1.0",
        capability_source="base",
        request_hash="abc123def456",
    )


@pytest.fixture
def sample_tool_capability() -> ToolCapability:
    """Create a sample tool capability."""
    return ToolCapability(
        tool_name="test_tool",
        classification=ToolClassification.MONITORING,
        description="A test tool for unit tests",
        allowed_actions=("read", "execute"),
        requires_context=(),
        blocked_contexts=("production",),
        rate_limit_per_minute=30,
    )


@pytest.fixture
def audit_config() -> AuditConfig:
    """Create an audit configuration."""
    return AuditConfig(
        table_name="test-capability-audit",
        batch_size=25,
        safe_sample_rate=0.1,
        monitoring_sample_rate=1.0,
        dangerous_sample_rate=1.0,
        critical_sample_rate=1.0,
    )


@pytest.fixture
def grant_config() -> GrantManagerConfig:
    """Create a grant manager configuration."""
    return GrantManagerConfig(
        table_name="test-capability-grants",
        single_use_expiry_minutes=60,
        session_expiry_hours=8,
        max_active_grants_per_agent=10,
        cleanup_interval_seconds=300,
    )


@pytest.fixture
def metrics_config() -> MetricsConfig:
    """Create a metrics configuration."""
    return MetricsConfig(
        namespace="Test/CapabilityGovernance",
        flush_interval_seconds=60,
        include_environment=True,
        include_region=True,
    )


@pytest.fixture
def capability_registry() -> CapabilityRegistry:
    """Create a capability registry."""
    return CapabilityRegistry()


@pytest.fixture
def mock_dynamodb_client() -> MagicMock:
    """Create a mock DynamoDB client."""
    client = MagicMock()
    client.batch_write_item = MagicMock(return_value={})
    client.get_item = MagicMock(return_value={"Item": {}})
    client.put_item = MagicMock(return_value={})
    client.query = MagicMock(return_value={"Items": []})
    client.update_item = MagicMock(return_value={})
    return client


@pytest.fixture
def mock_sqs_client() -> MagicMock:
    """Create a mock SQS client."""
    client = MagicMock()
    client.send_message = MagicMock(return_value={"MessageId": "test-123"})
    client.send_message_batch = MagicMock(return_value={"Successful": [], "Failed": []})
    return client


@pytest.fixture
def mock_cloudwatch_client() -> MagicMock:
    """Create a mock CloudWatch client."""
    client = MagicMock()
    client.put_metric_data = MagicMock(return_value={})
    return client
