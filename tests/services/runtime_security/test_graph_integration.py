"""
Tests for runtime security graph integration service.
"""

from datetime import datetime, timezone

from src.services.runtime_security import (
    AdmissionDecision,
    AdmissionDecisionType,
    EdgeLabel,
    EscapeEvent,
    EscapeTechnique,
    EventType,
    ResourceType,
    RuntimeEvent,
    RuntimeSecurityGraphService,
    Severity,
    VertexLabel,
    escape_gremlin_string,
    get_runtime_security_graph_service,
    reset_runtime_security_graph_service,
)


class TestGraphServiceInitialization:
    """Tests for graph service initialization."""

    def test_initialize_service(self, test_config):
        """Test initializing graph service."""
        service = RuntimeSecurityGraphService()
        assert service is not None
        assert service._use_mock is True

    def test_singleton_instance(self, test_config):
        """Test getting singleton instance."""
        service1 = get_runtime_security_graph_service()
        service2 = get_runtime_security_graph_service()
        assert service1 is service2

    def test_reset_singleton(self, test_config):
        """Test resetting singleton."""
        service1 = get_runtime_security_graph_service()
        reset_runtime_security_graph_service()
        service2 = get_runtime_security_graph_service()
        assert service1 is not service2


class TestRuntimeEventOperations:
    """Tests for runtime event graph operations."""

    def test_store_runtime_event(self, test_config, sample_runtime_event):
        """Test storing a runtime event in the graph."""
        service = RuntimeSecurityGraphService()
        vertex_id = service.store_runtime_event(sample_runtime_event)

        assert vertex_id == f"event:{sample_runtime_event.event_id}"

    def test_get_runtime_event(self, test_config, sample_runtime_event):
        """Test retrieving a runtime event."""
        service = RuntimeSecurityGraphService()
        service.store_runtime_event(sample_runtime_event)

        data = service.get_runtime_event(sample_runtime_event.event_id)
        assert data is not None
        assert data["event_id"] == sample_runtime_event.event_id
        assert data["event_type"] == EventType.CLOUDTRAIL.value

    def test_get_nonexistent_event(self, test_config):
        """Test getting non-existent event."""
        service = RuntimeSecurityGraphService()
        data = service.get_runtime_event("nonexistent")
        assert data is None

    def test_delete_runtime_event(self, test_config, sample_runtime_event):
        """Test deleting a runtime event."""
        service = RuntimeSecurityGraphService()
        service.store_runtime_event(sample_runtime_event)

        result = service.delete_runtime_event(sample_runtime_event.event_id)
        assert result is True

        data = service.get_runtime_event(sample_runtime_event.event_id)
        assert data is None


class TestAWSResourceOperations:
    """Tests for AWS resource graph operations."""

    def test_store_aws_resource(self, test_config, sample_aws_resource):
        """Test storing an AWS resource."""
        service = RuntimeSecurityGraphService()
        vertex_id = service.store_aws_resource(sample_aws_resource)

        assert vertex_id == f"resource:{sample_aws_resource.resource_arn}"

    def test_get_aws_resource(self, test_config, sample_aws_resource):
        """Test retrieving an AWS resource."""
        service = RuntimeSecurityGraphService()
        service.store_aws_resource(sample_aws_resource)

        data = service.get_aws_resource(sample_aws_resource.resource_arn)
        assert data is not None
        assert data["name"] == sample_aws_resource.name
        assert data["resource_type"] == ResourceType.EC2_INSTANCE.value


class TestIaCResourceOperations:
    """Tests for IaC resource graph operations."""

    def test_store_iac_resource(self, test_config, sample_iac_resource):
        """Test storing an IaC resource."""
        service = RuntimeSecurityGraphService()
        vertex_id = service.store_iac_resource(sample_iac_resource)

        assert vertex_id == f"iac:{sample_iac_resource.iac_resource_id}"

    def test_store_iac_creates_code_edge(self, test_config, sample_iac_resource):
        """Test that storing IaC resource creates SOURCE_CODE edge."""
        service = RuntimeSecurityGraphService()
        service.store_iac_resource(sample_iac_resource)

        # Check edge was created
        source_code_edges = [
            e for e in service._mock_edges.values() if e.label == EdgeLabel.SOURCE_CODE
        ]
        assert len(source_code_edges) == 1
        assert (
            source_code_edges[0].properties.get("line_start")
            == sample_iac_resource.line_number
        )


class TestContainerImageOperations:
    """Tests for container image graph operations."""

    def test_store_container_image(self, test_config, sample_container_image):
        """Test storing a container image."""
        service = RuntimeSecurityGraphService()
        vertex_id = service.store_container_image(sample_container_image)

        assert vertex_id == f"image:{sample_container_image.digest}"

    def test_get_container_image(self, test_config, sample_container_image):
        """Test retrieving a container image."""
        service = RuntimeSecurityGraphService()
        service.store_container_image(sample_container_image)

        data = service.get_container_image(sample_container_image.digest)
        assert data is not None
        assert data["tag"] == sample_container_image.tag
        assert data["signed"] is True


class TestAdmissionDecisionOperations:
    """Tests for admission decision graph operations."""

    def test_store_admission_decision(self, test_config, sample_container_image):
        """Test storing an admission decision."""
        service = RuntimeSecurityGraphService()

        # First store the image
        service.store_container_image(sample_container_image)

        decision = AdmissionDecision(
            decision_id="dec-test-001",
            request_uid="req-001",
            cluster="test-cluster",
            namespace="production",
            resource_kind="Deployment",
            resource_name="test-app",
            decision=AdmissionDecisionType.ALLOW,
            violations=[],
            images_checked=[sample_container_image.digest],
        )

        vertex_id = service.store_admission_decision(decision)
        assert vertex_id == f"admission:{decision.decision_id}"

    def test_store_admission_creates_edges(self, test_config, sample_container_image):
        """Test that storing admission decision creates ADMISSION_FOR edges."""
        service = RuntimeSecurityGraphService()

        service.store_container_image(sample_container_image)

        decision = AdmissionDecision(
            decision_id="dec-test-002",
            request_uid="req-002",
            cluster="test-cluster",
            namespace="default",
            resource_kind="Pod",
            resource_name="test-pod",
            decision=AdmissionDecisionType.DENY,
            violations=[],
            images_checked=[sample_container_image.digest],
        )

        service.store_admission_decision(decision)

        # Check edge was created
        admission_edges = [
            e
            for e in service._mock_edges.values()
            if e.label == EdgeLabel.ADMISSION_FOR
        ]
        assert len(admission_edges) == 1

    def test_get_admission_decisions_for_image(
        self, test_config, sample_container_image
    ):
        """Test getting admission decisions for an image."""
        service = RuntimeSecurityGraphService()

        service.store_container_image(sample_container_image)

        # Create multiple decisions
        for i in range(3):
            decision = AdmissionDecision(
                decision_id=f"dec-multi-{i}",
                request_uid=f"req-{i}",
                cluster="test-cluster",
                namespace="default",
                resource_kind="Pod",
                resource_name=f"pod-{i}",
                decision=AdmissionDecisionType.ALLOW,
                violations=[],
                images_checked=[sample_container_image.digest],
            )
            service.store_admission_decision(decision)

        decisions = service.get_admission_decisions_for_image(
            sample_container_image.digest
        )
        assert len(decisions) == 3


class TestEscapeEventOperations:
    """Tests for escape event graph operations."""

    def test_store_escape_event(
        self, test_config, sample_escape_event, sample_container_image
    ):
        """Test storing an escape event."""
        service = RuntimeSecurityGraphService()

        # Store the image first
        sample_escape_event.image_digest = sample_container_image.digest
        service.store_container_image(sample_container_image)

        vertex_id = service.store_escape_event(sample_escape_event)
        assert vertex_id == f"escape:{sample_escape_event.event_id}"

    def test_store_escape_creates_edges(
        self, test_config, sample_escape_event, sample_container_image
    ):
        """Test that storing escape event creates ESCAPE_ATTEMPT_FROM edge."""
        service = RuntimeSecurityGraphService()

        sample_escape_event.image_digest = sample_container_image.digest
        service.store_container_image(sample_container_image)
        service.store_escape_event(sample_escape_event)

        # Check edge was created
        escape_edges = [
            e
            for e in service._mock_edges.values()
            if e.label == EdgeLabel.ESCAPE_ATTEMPT_FROM
        ]
        assert len(escape_edges) == 1
        assert (
            escape_edges[0].properties.get("technique")
            == EscapeTechnique.PRIVILEGE_ESCALATION.value
        )

    def test_get_escape_events_for_image(self, test_config, sample_container_image):
        """Test getting escape events for an image."""
        service = RuntimeSecurityGraphService()

        service.store_container_image(sample_container_image)

        # Create multiple escape events
        for i in range(2):
            event = EscapeEvent(
                event_id=f"esc-multi-{i}",
                cluster="test-cluster",
                node_id="node-1",
                container_id=f"container-{i}",
                pod_name="test-pod",
                namespace="default",
                image_digest=sample_container_image.digest,
                technique=EscapeTechnique.PRIVILEGE_ESCALATION,
            )
            service.store_escape_event(event)

        events = service.get_escape_events_for_image(sample_container_image.digest)
        assert len(events) == 2

    def test_delete_escape_event(self, test_config, sample_escape_event):
        """Test deleting an escape event."""
        service = RuntimeSecurityGraphService()
        service.store_escape_event(sample_escape_event)

        result = service.delete_escape_event(sample_escape_event.event_id)
        assert result is True


class TestCorrelationOperations:
    """Tests for correlation graph operations."""

    def test_store_correlation(
        self,
        test_config,
        sample_correlation_result,
    ):
        """Test storing a correlation result."""
        service = RuntimeSecurityGraphService()
        vertex_id = service.store_correlation(sample_correlation_result)

        assert "correlation" in vertex_id

    def test_correlation_creates_defined_in_edge(
        self,
        test_config,
        sample_correlation_result,
    ):
        """Test that correlation creates DEFINED_IN edge."""
        service = RuntimeSecurityGraphService()
        service.store_correlation(sample_correlation_result)

        # Check DEFINED_IN edge was created
        defined_in_edges = [
            e for e in service._mock_edges.values() if e.label == EdgeLabel.DEFINED_IN
        ]
        assert len(defined_in_edges) == 1


class TestResourceMappingOperations:
    """Tests for resource mapping operations."""

    def test_store_resource_mapping(self, test_config, sample_resource_mapping):
        """Test storing a resource mapping."""
        service = RuntimeSecurityGraphService()
        vertex_id = service.store_resource_mapping(sample_resource_mapping)

        assert "resource:" in vertex_id

    def test_get_iac_for_resource(self, test_config, sample_resource_mapping):
        """Test getting IaC for a resource."""
        service = RuntimeSecurityGraphService()
        service.store_resource_mapping(sample_resource_mapping)

        iac_data = service.get_iac_for_resource(
            sample_resource_mapping.aws_resource_arn
        )
        assert iac_data is not None
        assert iac_data["iac_resource_id"] == sample_resource_mapping.iac_resource_id


class TestEventResourceQueries:
    """Tests for event-resource queries."""

    def test_get_events_for_resource(self, test_config, sample_aws_resource):
        """Test getting events for a resource."""
        service = RuntimeSecurityGraphService()

        # Store resource
        service.store_aws_resource(sample_aws_resource)

        # Store events with edges to resource
        for i in range(3):
            event = RuntimeEvent(
                event_id=f"evt-query-{i}",
                event_type=EventType.CLOUDTRAIL,
                severity=Severity.MEDIUM,
                aws_account_id="123456789012",
                region="us-east-1",
                timestamp=datetime.now(timezone.utc),
                resource_arn=sample_aws_resource.resource_arn,
                description=f"Event {i}",
            )
            service.store_runtime_event(event)

        events = service.get_events_for_resource(sample_aws_resource.resource_arn)
        assert len(events) == 3


class TestVertexLabels:
    """Tests for vertex labels enum."""

    def test_vertex_labels(self):
        """Test vertex label values."""
        assert VertexLabel.RUNTIME_EVENT.value == "RuntimeEvent"
        assert VertexLabel.AWS_RESOURCE.value == "AWSResource"
        assert VertexLabel.IAC_RESOURCE.value == "IaCResource"
        assert VertexLabel.CONTAINER_IMAGE.value == "ContainerImage"
        assert VertexLabel.ADMISSION_DECISION.value == "AdmissionDecision"
        assert VertexLabel.ESCAPE_EVENT.value == "EscapeEvent"


class TestEdgeLabels:
    """Tests for edge labels enum."""

    def test_edge_labels(self):
        """Test edge label values."""
        assert EdgeLabel.TRIGGERED_BY.value == "TRIGGERED_BY"
        assert EdgeLabel.DEFINED_IN.value == "DEFINED_IN"
        assert EdgeLabel.SOURCE_CODE.value == "SOURCE_CODE"
        assert EdgeLabel.RUNS_IMAGE.value == "RUNS_IMAGE"
        assert EdgeLabel.ESCAPE_ATTEMPT_FROM.value == "ESCAPE_ATTEMPT_FROM"
        assert EdgeLabel.ADMISSION_FOR.value == "ADMISSION_FOR"


class TestGremlinEscaping:
    """Tests for Gremlin string escaping."""

    def test_escape_quotes(self, test_config):
        """Test escaping quotes in strings."""
        assert escape_gremlin_string("test'quote") == "test\\'quote"
        assert escape_gremlin_string("double''quote") == "double\\'\\'quote"

    def test_escape_newlines(self, test_config):
        """Test escaping newlines."""
        assert escape_gremlin_string("line1\nline2") == "line1\\nline2"
        assert escape_gremlin_string("tab\there") == "tab\\there"

    def test_escape_backslashes(self, test_config):
        """Test escaping backslashes."""
        assert escape_gremlin_string("path\\to\\file") == "path\\\\to\\\\file"

    def test_escape_empty_string(self, test_config):
        """Test escaping empty string."""
        assert escape_gremlin_string("") == ""

    def test_escape_none(self, test_config):
        """Test escaping None."""
        assert escape_gremlin_string(None) is None


class TestServiceCleanup:
    """Tests for service cleanup."""

    def test_close_service(self, test_config):
        """Test closing service."""
        service = RuntimeSecurityGraphService()

        # Should not raise
        service.close()

        # Should be safe to call twice
        service.close()
