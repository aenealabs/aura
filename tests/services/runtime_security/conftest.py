"""
Test fixtures for runtime security services.
"""

from datetime import datetime, timezone
from typing import Any

import pytest

from src.services.runtime_security import (
    AdmissionPolicy,
    AdmissionRequest,
    AWSResource,
    ContainerImage,
    CorrelationResult,
    CorrelationStatus,
    EscapeEvent,
    EscapeTechnique,
    EventType,
    IaCProvider,
    IaCResource,
    PolicyMode,
    PolicyType,
    ResourceMapping,
    ResourceType,
    RuntimeEvent,
    RuntimeSecurityConfig,
    Severity,
    reset_admission_controller,
    reset_escape_detector,
    reset_runtime_correlator,
    reset_runtime_security_config,
    reset_runtime_security_graph_service,
    reset_runtime_security_metrics,
    set_runtime_security_config,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons before each test."""
    reset_runtime_security_config()
    reset_admission_controller()
    reset_runtime_correlator()
    reset_escape_detector()
    reset_runtime_security_graph_service()
    reset_runtime_security_metrics()
    yield
    reset_runtime_security_config()
    reset_admission_controller()
    reset_runtime_correlator()
    reset_escape_detector()
    reset_runtime_security_graph_service()
    reset_runtime_security_metrics()


@pytest.fixture
def test_config() -> RuntimeSecurityConfig:
    """Create test configuration."""
    config = RuntimeSecurityConfig.for_testing()
    set_runtime_security_config(config)
    return config


@pytest.fixture
def sample_cloudtrail_event() -> dict[str, Any]:
    """Create a sample CloudTrail event."""
    return {
        "eventID": "test-event-123",
        "eventName": "RunInstances",
        "eventSource": "ec2.amazonaws.com",
        "eventTime": "2026-01-15T10:30:00Z",
        "awsRegion": "us-east-1",
        "recipientAccountId": "123456789012",
        "userIdentity": {
            "type": "AssumedRole",
            "principalId": "AROAEXAMPLE:developer",
            "arn": "arn:aws:sts::123456789012:assumed-role/DeveloperRole/developer",
        },
        "requestParameters": {
            "instancesSet": {"items": [{"imageId": "ami-12345678"}]},
            "instanceType": "t3.medium",
        },
        "responseElements": {
            "instancesSet": {"items": [{"instanceId": "i-0abc123def456789a"}]}
        },
    }


@pytest.fixture
def sample_guardduty_finding() -> dict[str, Any]:
    """Create a sample GuardDuty finding."""
    return {
        "Id": "finding-456",
        "Type": "UnauthorizedAccess:EC2/TorRelay",
        "Severity": 8,
        "AccountId": "123456789012",
        "Region": "us-east-1",
        "CreatedAt": "2026-01-15T11:00:00Z",
        "Title": "EC2 instance communicating with Tor network",
        "Description": "EC2 instance i-0abc123def is communicating with known Tor exit nodes",
        "Resource": {
            "ResourceType": "Instance",
            "InstanceDetails": {
                "InstanceId": "i-0abc123def456789a",
                "InstanceType": "t3.medium",
            },
        },
    }


@pytest.fixture
def sample_vpc_flow_log() -> dict[str, Any]:
    """Create a sample VPC Flow Log record."""
    return {
        "account-id": "123456789012",
        "interface-id": "eni-12345678",
        "srcaddr": "10.0.1.100",
        "dstaddr": "10.0.2.50",
        "srcport": 443,
        "dstport": 8080,
        "protocol": "6",
        "action": "ACCEPT",
        "log-status": "OK",
        "region": "us-east-1",
        "start": 1705313400,
    }


@pytest.fixture
def sample_runtime_event() -> RuntimeEvent:
    """Create a sample runtime event."""
    return RuntimeEvent(
        event_id="evt-test-001",
        event_type=EventType.CLOUDTRAIL,
        severity=Severity.HIGH,
        aws_account_id="123456789012",
        region="us-east-1",
        timestamp=datetime.now(timezone.utc),
        resource_arn="arn:aws:ec2:us-east-1:123456789012:instance/i-0abc123def",
        description="RunInstances by developer",
    )


@pytest.fixture
def sample_aws_resource() -> AWSResource:
    """Create a sample AWS resource."""
    return AWSResource(
        resource_arn="arn:aws:ec2:us-east-1:123456789012:instance/i-0abc123def",
        resource_type=ResourceType.EC2_INSTANCE,
        name="i-0abc123def",
        aws_account_id="123456789012",
        region="us-east-1",
        last_seen=datetime.now(timezone.utc),
        tags={"Environment": "dev", "Application": "aura"},
    )


@pytest.fixture
def sample_iac_resource() -> IaCResource:
    """Create a sample IaC resource."""
    return IaCResource(
        iac_resource_id="aws_instance.web_server",
        resource_type="aws_instance",
        provider=IaCProvider.TERRAFORM,
        file_path="deploy/terraform/ec2.tf",
        line_number=42,
        module="compute",
        resource_name="web_server",
        git_commit="abc123def456",
        git_blame_author="developer@aenealabs.com",
    )


@pytest.fixture
def sample_container_image() -> ContainerImage:
    """Create a sample container image."""
    return ContainerImage(
        digest="sha256:abc123def456789",
        repository="123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-api",
        tag="v1.0.0",
        sbom_id="sbom-123",
        signed=True,
        signature_verified=True,
        scanned_at=datetime.now(timezone.utc),
        vulnerabilities={"CRITICAL": 0, "HIGH": 2, "MEDIUM": 5},
    )


@pytest.fixture
def sample_admission_request() -> AdmissionRequest:
    """Create a sample Kubernetes admission request."""
    return AdmissionRequest(
        uid="request-uuid-123",
        kind="Deployment",
        namespace="production",
        name="aura-api",
        operation="CREATE",
        user_info={
            "username": "developer@aenealabs.com",
            "groups": ["developers", "system:authenticated"],
        },
        object_spec={
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "api",
                                "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-api:v1.0.0",
                                "resources": {
                                    "limits": {"memory": "512Mi", "cpu": "500m"},
                                    "requests": {"memory": "256Mi", "cpu": "250m"},
                                },
                            }
                        ]
                    }
                }
            }
        },
    )


@pytest.fixture
def sample_admission_request_no_limits() -> AdmissionRequest:
    """Create an admission request without resource limits."""
    return AdmissionRequest(
        uid="request-uuid-456",
        kind="Pod",
        namespace="default",
        name="test-pod",
        operation="CREATE",
        object_spec={
            "spec": {
                "containers": [
                    {
                        "name": "app",
                        "image": "nginx:latest",
                    }
                ]
            }
        },
    )


@pytest.fixture
def sample_admission_policy() -> AdmissionPolicy:
    """Create a sample admission policy."""
    return AdmissionPolicy(
        policy_id="test-policy-001",
        name="Test Policy",
        policy_type=PolicyType.CVE_THRESHOLD,
        mode=PolicyMode.ENFORCE,
        enabled=True,
        description="Test CVE threshold policy",
        severity_threshold=Severity.HIGH,
        namespaces=["production", "staging"],
        resource_kinds=["Deployment", "Pod"],
    )


@pytest.fixture
def sample_escape_event() -> EscapeEvent:
    """Create a sample escape event."""
    return EscapeEvent(
        event_id="esc-test-001",
        cluster="aura-eks-dev",
        node_id="ip-10-0-1-100",
        container_id="abc123def456",
        pod_name="test-pod",
        namespace="default",
        image_digest="sha256:abc123",
        technique=EscapeTechnique.PRIVILEGE_ESCALATION,
        syscall="setuid",
        process_name="bash",
        process_args="su root",
        user_id=1000,
        blocked=False,
        mitre_attack_id="T1611",
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_ebpf_event() -> dict[str, Any]:
    """Create a sample eBPF event."""
    return {
        "syscall": "setuid",
        "comm": "bash",
        "container_id": "container123",
        "node_id": "node-1",
        "cluster": "test-cluster",
        "uid": 1000,
        "args": "",
        "pod_name": "test-pod",
        "namespace": "default",
    }


@pytest.fixture
def sample_falco_alert() -> dict[str, Any]:
    """Create a sample Falco alert."""
    return {
        "rule": "Container Privilege Escalation",
        "priority": "CRITICAL",
        "output": "Privilege escalation attempt (user=developer command=su root container=abc123)",
        "output_fields": {
            "container.id": "abc123def",
            "k8s.pod.name": "test-pod",
            "k8s.ns.name": "default",
            "proc.name": "su",
            "syscall.type": "setuid",
            "node": "ip-10-0-1-100",
        },
    }


@pytest.fixture
def sample_resource_mapping() -> ResourceMapping:
    """Create a sample resource mapping."""
    return ResourceMapping(
        aws_resource_arn="arn:aws:ec2:us-east-1:123456789012:instance/i-0abc123def",
        iac_file_path="deploy/terraform/ec2.tf",
        iac_resource_id="aws_instance.web_server",
        iac_provider=IaCProvider.TERRAFORM,
        terraform_state_key="module.compute.aws_instance.web_server",
        git_commit="abc123def456",
        last_applied=datetime.now(timezone.utc),
        confidence=0.95,
    )


@pytest.fixture
def sample_correlation_result(
    sample_runtime_event, sample_aws_resource, sample_iac_resource
) -> CorrelationResult:
    """Create a sample correlation result."""
    return CorrelationResult(
        event_id=sample_runtime_event.event_id,
        status=CorrelationStatus.CORRELATED,
        aws_resource=sample_aws_resource,
        iac_resource=sample_iac_resource,
        code_file=sample_iac_resource.file_path,
        code_line_start=sample_iac_resource.line_number,
        code_line_end=sample_iac_resource.line_number + 20,
        git_blame_author=sample_iac_resource.git_blame_author,
        git_commit=sample_iac_resource.git_commit,
        confidence=0.95,
        correlation_chain=[
            "AWS Resource: i-0abc123def",
            "IaC Resource: deploy/terraform/ec2.tf:42",
            "Git Blame: developer@aenealabs.com (abc123d)",
        ],
    )
