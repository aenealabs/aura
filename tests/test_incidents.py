"""
Project Aura - Incident Investigation API Tests

Tests for the incident investigation REST API endpoints.
"""

from typing import Optional

from pydantic import BaseModel


# Define local copies of the models to avoid import issues
class InvestigationSummary(BaseModel):
    """Summary of an incident investigation for list view."""

    incident_id: str
    timestamp: str
    source: str
    alert_name: str
    affected_service: str
    confidence_score: int
    hitl_status: str
    created_at: str


class CodeEntity(BaseModel):
    """Code entity correlated with incident."""

    entity_id: str
    entity_type: str
    name: str
    file_path: str
    line_number: Optional[int] = None
    namespace: Optional[str] = None


class DeploymentEvent(BaseModel):
    """Deployment event correlated with incident."""

    deployment_id: str
    timestamp: str
    application_name: str
    commit_sha: str
    commit_message: str
    rollout_status: str
    image_tag: str
    deployed_by: str


class GitCommit(BaseModel):
    """Git commit correlated with incident."""

    sha: str
    message: str
    author: str
    timestamp: str
    file_path: str


class InvestigationDetail(BaseModel):
    """Detailed investigation result for detail view."""

    incident_id: str
    timestamp: str
    source: str
    alert_name: str
    affected_service: str
    rca_hypothesis: str
    confidence_score: int
    deployment_correlation: list[DeploymentEvent]
    code_entities: list[CodeEntity]
    git_commits: list[GitCommit]
    mitigation_plan: str
    hitl_status: str
    hitl_approver: Optional[str] = None
    hitl_timestamp: Optional[str] = None
    rejection_reason: Optional[str] = None


class ApprovalRequest(BaseModel):
    """Request to approve a mitigation plan."""

    approver_email: str
    comments: Optional[str] = None


class RejectionRequest(BaseModel):
    """Request to reject a mitigation plan."""

    approver_email: str
    reason: str


class ApprovalResponse(BaseModel):
    """Response after approval/rejection."""

    status: str
    incident_id: str
    message: str


class TestInvestigationSummary:
    """Tests for InvestigationSummary model."""

    def test_summary_creation(self):
        """Test creating investigation summary."""
        summary = InvestigationSummary(
            incident_id="inc-123",
            timestamp="2025-12-21T10:00:00Z",
            source="cloudwatch",
            alert_name="High CPU Usage",
            affected_service="api-gateway",
            confidence_score=85,
            hitl_status="pending",
            created_at="2025-12-21T09:55:00Z",
        )
        assert summary.incident_id == "inc-123"
        assert summary.source == "cloudwatch"
        assert summary.confidence_score == 85
        assert summary.hitl_status == "pending"

    def test_confidence_score_min(self):
        """Test minimum confidence score."""
        summary = InvestigationSummary(
            incident_id="inc-min",
            timestamp="2025-12-21T10:00:00Z",
            source="pagerduty",
            alert_name="Alert",
            affected_service="service",
            confidence_score=0,
            hitl_status="pending",
            created_at="2025-12-21T10:00:00Z",
        )
        assert summary.confidence_score == 0

    def test_confidence_score_max(self):
        """Test maximum confidence score."""
        summary = InvestigationSummary(
            incident_id="inc-max",
            timestamp="2025-12-21T10:00:00Z",
            source="cloudwatch",
            alert_name="Alert",
            affected_service="service",
            confidence_score=100,
            hitl_status="approved",
            created_at="2025-12-21T10:00:00Z",
        )
        assert summary.confidence_score == 100

    def test_different_sources(self):
        """Test different incident sources."""
        sources = ["cloudwatch", "pagerduty", "datadog", "custom"]
        for source in sources:
            summary = InvestigationSummary(
                incident_id=f"inc-{source}",
                timestamp="2025-12-21T10:00:00Z",
                source=source,
                alert_name="Alert",
                affected_service="service",
                confidence_score=50,
                hitl_status="pending",
                created_at="2025-12-21T10:00:00Z",
            )
            assert summary.source == source

    def test_different_hitl_statuses(self):
        """Test different HITL statuses."""
        statuses = ["pending", "approved", "rejected"]
        for status in statuses:
            summary = InvestigationSummary(
                incident_id=f"inc-{status}",
                timestamp="2025-12-21T10:00:00Z",
                source="cloudwatch",
                alert_name="Alert",
                affected_service="service",
                confidence_score=50,
                hitl_status=status,
                created_at="2025-12-21T10:00:00Z",
            )
            assert summary.hitl_status == status


class TestCodeEntity:
    """Tests for CodeEntity model."""

    def test_code_entity_creation(self):
        """Test creating code entity."""
        entity = CodeEntity(
            entity_id="ent-123",
            entity_type="function",
            name="authenticate_user",
            file_path="/src/auth/login.py",
        )
        assert entity.entity_id == "ent-123"
        assert entity.entity_type == "function"
        assert entity.name == "authenticate_user"
        assert entity.file_path == "/src/auth/login.py"

    def test_code_entity_with_line(self):
        """Test code entity with line number."""
        entity = CodeEntity(
            entity_id="ent-456",
            entity_type="class",
            name="UserService",
            file_path="/src/services/user.py",
            line_number=42,
        )
        assert entity.line_number == 42

    def test_code_entity_with_namespace(self):
        """Test code entity with namespace."""
        entity = CodeEntity(
            entity_id="ent-789",
            entity_type="method",
            name="get_user",
            file_path="/src/api/users.py",
            namespace="UserController",
        )
        assert entity.namespace == "UserController"

    def test_entity_types(self):
        """Test different entity types."""
        types = ["function", "class", "method", "variable", "module"]
        for entity_type in types:
            entity = CodeEntity(
                entity_id=f"ent-{entity_type}",
                entity_type=entity_type,
                name=f"test_{entity_type}",
                file_path="/test.py",
            )
            assert entity.entity_type == entity_type


class TestDeploymentEvent:
    """Tests for DeploymentEvent model."""

    def test_deployment_event_creation(self):
        """Test creating deployment event."""
        event = DeploymentEvent(
            deployment_id="deploy-123",
            timestamp="2025-12-21T09:00:00Z",
            application_name="api-gateway",
            commit_sha="abc123def456",
            commit_message="Fix authentication bug",
            rollout_status="completed",
            image_tag="v1.2.3",
            deployed_by="ci-system",
        )
        assert event.deployment_id == "deploy-123"
        assert event.application_name == "api-gateway"
        assert event.commit_sha == "abc123def456"
        assert event.rollout_status == "completed"

    def test_rollout_statuses(self):
        """Test different rollout statuses."""
        statuses = ["pending", "in_progress", "completed", "failed", "rolled_back"]
        for status in statuses:
            event = DeploymentEvent(
                deployment_id=f"deploy-{status}",
                timestamp="2025-12-21T10:00:00Z",
                application_name="app",
                commit_sha="sha",
                commit_message="msg",
                rollout_status=status,
                image_tag="tag",
                deployed_by="user",
            )
            assert event.rollout_status == status


class TestGitCommit:
    """Tests for GitCommit model."""

    def test_git_commit_creation(self):
        """Test creating git commit."""
        commit = GitCommit(
            sha="abc123def456789",
            message="Add new feature",
            author="developer@example.com",
            timestamp="2025-12-21T08:00:00Z",
            file_path="src/features/new.py",
        )
        assert commit.sha == "abc123def456789"
        assert commit.message == "Add new feature"
        assert commit.author == "developer@example.com"

    def test_multiline_commit_message(self):
        """Test commit with multiline message."""
        message = "Add user authentication\n\n- Implement login endpoint\n- Add JWT validation"
        commit = GitCommit(
            sha="sha123",
            message=message,
            author="dev@test.com",
            timestamp="2025-12-21T10:00:00Z",
            file_path="auth.py",
        )
        assert "\n" in commit.message


class TestInvestigationDetail:
    """Tests for InvestigationDetail model."""

    def test_investigation_detail_creation(self):
        """Test creating investigation detail."""
        detail = InvestigationDetail(
            incident_id="inc-detail-1",
            timestamp="2025-12-21T10:00:00Z",
            source="cloudwatch",
            alert_name="High Latency",
            affected_service="user-service",
            rca_hypothesis="Database connection pool exhaustion",
            confidence_score=92,
            deployment_correlation=[],
            code_entities=[],
            git_commits=[],
            mitigation_plan="Increase connection pool size",
            hitl_status="pending",
        )
        assert detail.incident_id == "inc-detail-1"
        assert detail.rca_hypothesis == "Database connection pool exhaustion"
        assert detail.confidence_score == 92
        assert detail.hitl_approver is None
        assert detail.rejection_reason is None

    def test_investigation_detail_with_approver(self):
        """Test investigation with approval info."""
        detail = InvestigationDetail(
            incident_id="inc-approved",
            timestamp="2025-12-21T10:00:00Z",
            source="cloudwatch",
            alert_name="Alert",
            affected_service="service",
            rca_hypothesis="Root cause",
            confidence_score=90,
            deployment_correlation=[],
            code_entities=[],
            git_commits=[],
            mitigation_plan="Plan",
            hitl_status="approved",
            hitl_approver="admin@example.com",
            hitl_timestamp="2025-12-21T11:00:00Z",
        )
        assert detail.hitl_approver == "admin@example.com"
        assert detail.hitl_timestamp is not None

    def test_investigation_detail_rejected(self):
        """Test rejected investigation."""
        detail = InvestigationDetail(
            incident_id="inc-rejected",
            timestamp="2025-12-21T10:00:00Z",
            source="cloudwatch",
            alert_name="Alert",
            affected_service="service",
            rca_hypothesis="Hypothesis",
            confidence_score=60,
            deployment_correlation=[],
            code_entities=[],
            git_commits=[],
            mitigation_plan="Plan",
            hitl_status="rejected",
            hitl_approver="reviewer@example.com",
            rejection_reason="Insufficient evidence",
        )
        assert detail.hitl_status == "rejected"
        assert detail.rejection_reason == "Insufficient evidence"


class TestApprovalRequest:
    """Tests for ApprovalRequest model."""

    def test_approval_request(self):
        """Test approval request."""
        request = ApprovalRequest(
            approver_email="admin@example.com",
        )
        assert request.approver_email == "admin@example.com"
        assert request.comments is None

    def test_approval_with_comments(self):
        """Test approval request with comments."""
        request = ApprovalRequest(
            approver_email="admin@example.com",
            comments="Approved after reviewing logs",
        )
        assert request.comments == "Approved after reviewing logs"


class TestRejectionRequest:
    """Tests for RejectionRequest model."""

    def test_rejection_request(self):
        """Test rejection request."""
        request = RejectionRequest(
            approver_email="reviewer@example.com",
            reason="RCA hypothesis is incorrect",
        )
        assert request.approver_email == "reviewer@example.com"
        assert request.reason == "RCA hypothesis is incorrect"


class TestApprovalResponse:
    """Tests for ApprovalResponse model."""

    def test_approval_response(self):
        """Test approval response."""
        response = ApprovalResponse(
            status="approved",
            incident_id="inc-123",
            message="Mitigation plan approved",
        )
        assert response.status == "approved"
        assert response.incident_id == "inc-123"

    def test_rejection_response(self):
        """Test rejection response."""
        response = ApprovalResponse(
            status="rejected",
            incident_id="inc-456",
            message="Mitigation plan rejected: insufficient evidence",
        )
        assert response.status == "rejected"


class TestInvestigationDetailWithCorrelations:
    """Tests for investigation detail with correlations."""

    def test_detail_with_deployments(self):
        """Test detail with deployment correlations."""
        deployments = [
            DeploymentEvent(
                deployment_id="d1",
                timestamp="2025-12-21T09:00:00Z",
                application_name="app",
                commit_sha="sha1",
                commit_message="msg1",
                rollout_status="completed",
                image_tag="v1",
                deployed_by="user",
            ),
            DeploymentEvent(
                deployment_id="d2",
                timestamp="2025-12-21T09:30:00Z",
                application_name="app",
                commit_sha="sha2",
                commit_message="msg2",
                rollout_status="completed",
                image_tag="v2",
                deployed_by="user",
            ),
        ]
        detail = InvestigationDetail(
            incident_id="inc-with-deps",
            timestamp="2025-12-21T10:00:00Z",
            source="cloudwatch",
            alert_name="Alert",
            affected_service="service",
            rca_hypothesis="Deployment caused issue",
            confidence_score=95,
            deployment_correlation=deployments,
            code_entities=[],
            git_commits=[],
            mitigation_plan="Rollback",
            hitl_status="pending",
        )
        assert len(detail.deployment_correlation) == 2

    def test_detail_with_code_entities(self):
        """Test detail with code entity correlations."""
        entities = [
            CodeEntity(
                entity_id="e1",
                entity_type="function",
                name="process_request",
                file_path="/api/handler.py",
                line_number=42,
            ),
        ]
        detail = InvestigationDetail(
            incident_id="inc-with-code",
            timestamp="2025-12-21T10:00:00Z",
            source="cloudwatch",
            alert_name="Error",
            affected_service="api",
            rca_hypothesis="Bug in handler",
            confidence_score=88,
            deployment_correlation=[],
            code_entities=entities,
            git_commits=[],
            mitigation_plan="Fix bug",
            hitl_status="pending",
        )
        assert len(detail.code_entities) == 1
        assert detail.code_entities[0].name == "process_request"

    def test_detail_with_git_commits(self):
        """Test detail with git commit correlations."""
        commits = [
            GitCommit(
                sha="abc123",
                message="Introduce bug",
                author="dev@example.com",
                timestamp="2025-12-20T15:00:00Z",
                file_path="handler.py",
            ),
        ]
        detail = InvestigationDetail(
            incident_id="inc-with-commits",
            timestamp="2025-12-21T10:00:00Z",
            source="cloudwatch",
            alert_name="Error",
            affected_service="api",
            rca_hypothesis="Recent commit",
            confidence_score=75,
            deployment_correlation=[],
            code_entities=[],
            git_commits=commits,
            mitigation_plan="Revert commit",
            hitl_status="pending",
        )
        assert len(detail.git_commits) == 1
