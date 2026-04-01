"""
Tests for runtime security contracts (enums and dataclasses).
"""

from src.services.runtime_security import (
    AdmissionDecision,
    AdmissionDecisionType,
    CorrelationResult,
    CorrelationStatus,
    EscapeEvent,
    EscapeTechnique,
    EventType,
    IaCProvider,
    PolicyMode,
    PolicyType,
    PolicyViolation,
    ResourceType,
    Severity,
)


class TestSeverityEnum:
    """Tests for Severity enum."""

    def test_severity_ordering(self):
        """Test that severity levels are ordered correctly."""
        assert Severity.LOW < Severity.MEDIUM
        assert Severity.MEDIUM < Severity.HIGH
        assert Severity.HIGH < Severity.CRITICAL

    def test_severity_values(self):
        """Test severity values."""
        assert Severity.LOW.value == 1
        assert Severity.MEDIUM.value == 2
        assert Severity.HIGH.value == 3
        assert Severity.CRITICAL.value == 4


class TestEventTypeEnum:
    """Tests for EventType enum."""

    def test_event_types(self):
        """Test event type values."""
        assert EventType.CLOUDTRAIL.value == "cloudtrail"
        assert EventType.GUARDDUTY.value == "guardduty"
        assert EventType.VPC_FLOW.value == "vpc-flow"
        assert EventType.FALCO.value == "falco"


class TestEscapeTechniqueEnum:
    """Tests for EscapeTechnique enum."""

    def test_escape_techniques(self):
        """Test escape technique values."""
        assert EscapeTechnique.PRIVILEGE_ESCALATION.value == "privilege-escalation"
        assert EscapeTechnique.NAMESPACE_ESCAPE.value == "namespace-escape"
        assert EscapeTechnique.KERNEL_EXPLOIT.value == "kernel-exploit"
        assert EscapeTechnique.DIRTY_PIPE.value == "dirty-pipe"
        assert EscapeTechnique.NONE.value == "none"


class TestResourceTypeEnum:
    """Tests for ResourceType enum."""

    def test_resource_types(self):
        """Test resource type values."""
        assert ResourceType.EC2_INSTANCE.value == "AWS::EC2::Instance"
        assert ResourceType.EKS_CLUSTER.value == "AWS::EKS::Cluster"
        assert ResourceType.LAMBDA_FUNCTION.value == "AWS::Lambda::Function"
        assert ResourceType.S3_BUCKET.value == "AWS::S3::Bucket"


class TestRuntimeEvent:
    """Tests for RuntimeEvent dataclass."""

    def test_create_runtime_event(self, sample_runtime_event):
        """Test creating a runtime event."""
        assert sample_runtime_event.event_id == "evt-test-001"
        assert sample_runtime_event.event_type == EventType.CLOUDTRAIL
        assert sample_runtime_event.severity == Severity.HIGH
        assert sample_runtime_event.aws_account_id == "123456789012"

    def test_to_dict(self, sample_runtime_event):
        """Test serialization to dictionary."""
        data = sample_runtime_event.to_dict()
        assert data["event_id"] == "evt-test-001"
        assert data["event_type"] == "cloudtrail"
        assert data["severity"] == "HIGH"


class TestAWSResource:
    """Tests for AWSResource dataclass."""

    def test_create_aws_resource(self, sample_aws_resource):
        """Test creating an AWS resource."""
        assert sample_aws_resource.resource_type == ResourceType.EC2_INSTANCE
        assert sample_aws_resource.name == "i-0abc123def"
        assert "Environment" in sample_aws_resource.tags

    def test_to_dict(self, sample_aws_resource):
        """Test serialization to dictionary."""
        data = sample_aws_resource.to_dict()
        assert data["resource_type"] == "AWS::EC2::Instance"
        assert data["region"] == "us-east-1"


class TestIaCResource:
    """Tests for IaCResource dataclass."""

    def test_create_iac_resource(self, sample_iac_resource):
        """Test creating an IaC resource."""
        assert sample_iac_resource.provider == IaCProvider.TERRAFORM
        assert sample_iac_resource.file_path == "deploy/terraform/ec2.tf"
        assert sample_iac_resource.line_number == 42

    def test_to_dict(self, sample_iac_resource):
        """Test serialization to dictionary."""
        data = sample_iac_resource.to_dict()
        assert data["provider"] == "terraform"
        assert data["module"] == "compute"


class TestContainerImage:
    """Tests for ContainerImage dataclass."""

    def test_create_container_image(self, sample_container_image):
        """Test creating a container image."""
        assert sample_container_image.signed is True
        assert sample_container_image.signature_verified is True
        assert sample_container_image.vulnerabilities["CRITICAL"] == 0

    def test_full_reference(self, sample_container_image):
        """Test full image reference property."""
        ref = sample_container_image.full_reference
        assert "aura-api" in ref
        assert "v1.0.0" in ref
        assert "sha256:" in ref

    def test_to_dict(self, sample_container_image):
        """Test serialization to dictionary."""
        data = sample_container_image.to_dict()
        assert data["tag"] == "v1.0.0"
        assert data["signed"] is True


class TestAdmissionPolicy:
    """Tests for AdmissionPolicy dataclass."""

    def test_create_policy(self, sample_admission_policy):
        """Test creating an admission policy."""
        assert sample_admission_policy.policy_type == PolicyType.CVE_THRESHOLD
        assert sample_admission_policy.mode == PolicyMode.ENFORCE
        assert sample_admission_policy.enabled is True

    def test_applies_to_namespace(self, sample_admission_policy):
        """Test namespace filtering."""
        assert sample_admission_policy.applies_to_namespace("production") is True
        assert sample_admission_policy.applies_to_namespace("staging") is True
        assert sample_admission_policy.applies_to_namespace("development") is False

    def test_applies_to_kind(self, sample_admission_policy):
        """Test resource kind filtering."""
        assert sample_admission_policy.applies_to_kind("Deployment") is True
        assert sample_admission_policy.applies_to_kind("Pod") is True
        assert sample_admission_policy.applies_to_kind("ConfigMap") is False

    def test_to_dict(self, sample_admission_policy):
        """Test serialization to dictionary."""
        data = sample_admission_policy.to_dict()
        assert data["policy_type"] == "cve-threshold"
        assert data["mode"] == "enforce"


class TestAdmissionRequest:
    """Tests for AdmissionRequest dataclass."""

    def test_create_request(self, sample_admission_request):
        """Test creating an admission request."""
        assert sample_admission_request.kind == "Deployment"
        assert sample_admission_request.namespace == "production"
        assert sample_admission_request.operation == "CREATE"

    def test_containers_property(self, sample_admission_request):
        """Test containers extraction."""
        containers = sample_admission_request.containers
        assert len(containers) == 1
        assert containers[0]["name"] == "api"

    def test_images_property(self, sample_admission_request):
        """Test images extraction."""
        images = sample_admission_request.images
        assert len(images) == 1
        assert "aura-api" in images[0]


class TestAdmissionDecision:
    """Tests for AdmissionDecision dataclass."""

    def test_create_allow_decision(self, test_config):
        """Test creating an allow decision."""
        decision = AdmissionDecision(
            decision_id="dec-001",
            request_uid="req-001",
            cluster="test-cluster",
            namespace="production",
            resource_kind="Deployment",
            resource_name="test-app",
            decision=AdmissionDecisionType.ALLOW,
            violations=[],
        )
        assert decision.allowed is True
        assert decision.violation_count == 0

    def test_create_deny_decision(self, test_config):
        """Test creating a deny decision."""
        violation = PolicyViolation(
            policy_id="policy-001",
            policy_type=PolicyType.CVE_THRESHOLD,
            description="Too many critical CVEs",
            severity=Severity.CRITICAL,
        )
        decision = AdmissionDecision(
            decision_id="dec-002",
            request_uid="req-002",
            cluster="test-cluster",
            namespace="production",
            resource_kind="Deployment",
            resource_name="test-app",
            decision=AdmissionDecisionType.DENY,
            violations=[violation],
        )
        assert decision.allowed is False
        assert decision.violation_count == 1

    def test_to_dict(self, test_config):
        """Test serialization to dictionary."""
        decision = AdmissionDecision(
            decision_id="dec-003",
            request_uid="req-003",
            cluster="test-cluster",
            namespace="default",
            resource_kind="Pod",
            resource_name="test-pod",
            decision=AdmissionDecisionType.WARN,
            violations=[],
        )
        data = decision.to_dict()
        assert data["decision"] == "warn"
        assert data["cluster"] == "test-cluster"


class TestEscapeEvent:
    """Tests for EscapeEvent dataclass."""

    def test_create_escape_event(self, sample_escape_event):
        """Test creating an escape event."""
        assert sample_escape_event.technique == EscapeTechnique.PRIVILEGE_ESCALATION
        assert sample_escape_event.syscall == "setuid"
        assert sample_escape_event.blocked is False

    def test_severity_from_technique(self, test_config):
        """Test severity derivation from technique."""
        # Critical technique
        event = EscapeEvent(
            event_id="esc-001",
            cluster="test",
            node_id="node-1",
            container_id="container-1",
            pod_name="pod",
            namespace="default",
            technique=EscapeTechnique.KERNEL_EXPLOIT,
        )
        assert event.severity == Severity.CRITICAL

        # High technique
        event.technique = EscapeTechnique.PRIVILEGE_ESCALATION
        assert event.severity == Severity.HIGH

        # None technique
        event.technique = EscapeTechnique.NONE
        assert event.severity == Severity.LOW

    def test_to_dict(self, sample_escape_event):
        """Test serialization to dictionary."""
        data = sample_escape_event.to_dict()
        assert data["technique"] == "privilege-escalation"
        assert data["severity"] == "HIGH"
        assert data["mitre_attack_id"] == "T1611"


class TestCorrelationResult:
    """Tests for CorrelationResult dataclass."""

    def test_create_result(self, sample_correlation_result):
        """Test creating a correlation result."""
        assert sample_correlation_result.status == CorrelationStatus.CORRELATED
        assert sample_correlation_result.confidence == 0.95
        assert len(sample_correlation_result.correlation_chain) == 3

    def test_fully_correlated(self, sample_correlation_result):
        """Test fully_correlated property."""
        assert sample_correlation_result.fully_correlated is True

        # Partial correlation
        partial = CorrelationResult(
            event_id="evt-001",
            status=CorrelationStatus.PARTIAL,
            code_file=None,
        )
        assert partial.fully_correlated is False

    def test_to_dict(self, sample_correlation_result):
        """Test serialization to dictionary."""
        data = sample_correlation_result.to_dict()
        assert data["status"] == "correlated"
        assert data["confidence"] == 0.95
        assert data["aws_resource"] is not None


class TestResourceMapping:
    """Tests for ResourceMapping dataclass."""

    def test_create_mapping(self, sample_resource_mapping):
        """Test creating a resource mapping."""
        assert sample_resource_mapping.iac_provider == IaCProvider.TERRAFORM
        assert sample_resource_mapping.confidence == 0.95

    def test_to_dict(self, sample_resource_mapping):
        """Test serialization to dictionary."""
        data = sample_resource_mapping.to_dict()
        assert data["iac_provider"] == "terraform"
        assert "aws_instance.web_server" in data["terraform_state_key"]
