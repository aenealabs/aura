"""
Project Aura - Cloud Runtime Security Contracts

Enums and dataclasses for runtime security services including:
- Kubernetes admission control
- Runtime-to-code correlation
- Container escape detection

Based on ADR-077: Cloud Runtime Security Integration
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

# Type aliases
EventId = str
ResourceARN = str
ClusterName = str
DecisionId = str
ImageDigest = str
PolicyId = str


class EventType(Enum):
    """Types of runtime events."""

    CLOUDTRAIL = "cloudtrail"
    GUARDDUTY = "guardduty"
    VPC_FLOW = "vpc-flow"
    FALCO = "falco"
    EKS_AUDIT = "eks-audit"
    CUSTOM = "custom"


class Severity(Enum):
    """Severity levels for runtime events."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    def __lt__(self, other: "Severity") -> bool:
        return self.value < other.value

    def __le__(self, other: "Severity") -> bool:
        return self.value <= other.value

    def __gt__(self, other: "Severity") -> bool:
        return self.value > other.value

    def __ge__(self, other: "Severity") -> bool:
        return self.value >= other.value


class AdmissionDecisionType(Enum):
    """Kubernetes admission decision types."""

    ALLOW = "allow"
    DENY = "deny"
    WARN = "warn"


class CorrelationStatus(Enum):
    """Status of event-to-code correlation."""

    PENDING = "pending"
    CORRELATED = "correlated"
    PARTIAL = "partial"
    FAILED = "failed"
    NOT_APPLICABLE = "not-applicable"


class IaCProvider(Enum):
    """Infrastructure as Code providers."""

    TERRAFORM = "terraform"
    CLOUDFORMATION = "cloudformation"
    CDK = "cdk"
    PULUMI = "pulumi"
    UNKNOWN = "unknown"


class ResourceType(Enum):
    """AWS resource types."""

    EC2_INSTANCE = "AWS::EC2::Instance"
    EKS_CLUSTER = "AWS::EKS::Cluster"
    EKS_NODEGROUP = "AWS::EKS::Nodegroup"
    LAMBDA_FUNCTION = "AWS::Lambda::Function"
    S3_BUCKET = "AWS::S3::Bucket"
    RDS_INSTANCE = "AWS::RDS::DBInstance"
    IAM_ROLE = "AWS::IAM::Role"
    SECURITY_GROUP = "AWS::EC2::SecurityGroup"
    VPC = "AWS::EC2::VPC"
    ECS_SERVICE = "AWS::ECS::Service"
    DYNAMODB_TABLE = "AWS::DynamoDB::Table"
    UNKNOWN = "unknown"


class EscapeTechnique(Enum):
    """Container escape techniques (MITRE ATT&CK mapped)."""

    PRIVILEGE_ESCALATION = "privilege-escalation"  # T1611
    NAMESPACE_ESCAPE = "namespace-escape"  # T1611.001
    KERNEL_EXPLOIT = "kernel-exploit"  # T1068
    SYMLINK_ATTACK = "symlink-attack"  # T1068
    CGROUP_ESCAPE = "cgroup-escape"  # T1611
    MOUNT_ABUSE = "mount-abuse"  # T1611
    PTRACE_ABUSE = "ptrace-abuse"  # T1055
    CAPABILITY_ABUSE = "capability-abuse"  # T1611
    DIRTY_PIPE = "dirty-pipe"  # CVE-2022-0847
    OVERLAYFS = "overlayfs"  # CVE-2021-3493
    NONE = "none"


class PolicyType(Enum):
    """Types of admission policies."""

    SBOM_REQUIRED = "sbom-required"
    IMAGE_SIGNED = "image-signed"
    CVE_THRESHOLD = "cve-threshold"
    LICENSE_COMPLIANCE = "license-compliance"
    RESOURCE_LIMITS = "resource-limits"
    POD_SECURITY = "pod-security"
    REGISTRY_ALLOWLIST = "registry-allowlist"
    CUSTOM = "custom"


class PolicyMode(Enum):
    """Policy enforcement modes."""

    ENFORCE = "enforce"  # Block violations
    AUDIT = "audit"  # Log but don't block
    DRY_RUN = "dry-run"  # Test without logging


@dataclass
class RuntimeEvent:
    """A runtime security event from AWS or Kubernetes."""

    event_id: EventId
    event_type: EventType
    severity: Severity
    aws_account_id: str
    region: str
    timestamp: datetime
    resource_arn: Optional[ResourceARN] = None
    description: str = ""
    raw_event: dict[str, Any] = field(default_factory=dict)
    correlation_status: CorrelationStatus = CorrelationStatus.PENDING
    code_path: Optional[str] = None
    code_owner: Optional[str] = None
    mitre_attack_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.name,
            "aws_account_id": self.aws_account_id,
            "region": self.region,
            "timestamp": self.timestamp.isoformat(),
            "resource_arn": self.resource_arn,
            "description": self.description,
            "raw_event": self.raw_event,
            "correlation_status": self.correlation_status.value,
            "code_path": self.code_path,
            "code_owner": self.code_owner,
            "mitre_attack_id": self.mitre_attack_id,
        }


@dataclass
class AWSResource:
    """An AWS resource tracked for runtime-to-code correlation."""

    resource_arn: ResourceARN
    resource_type: ResourceType
    name: str
    aws_account_id: str
    region: str
    created_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    tags: dict[str, str] = field(default_factory=dict)
    iac_resource_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "resource_arn": self.resource_arn,
            "resource_type": self.resource_type.value,
            "name": self.name,
            "aws_account_id": self.aws_account_id,
            "region": self.region,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "tags": self.tags,
            "iac_resource_id": self.iac_resource_id,
        }


@dataclass
class IaCResource:
    """An Infrastructure as Code resource definition."""

    iac_resource_id: str
    resource_type: str  # e.g., "aws_instance", "AWS::EC2::Instance"
    provider: IaCProvider
    file_path: str
    line_number: int
    module: Optional[str] = None
    resource_name: Optional[str] = None
    git_commit: Optional[str] = None
    git_blame_author: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "iac_resource_id": self.iac_resource_id,
            "resource_type": self.resource_type,
            "provider": self.provider.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "module": self.module,
            "resource_name": self.resource_name,
            "git_commit": self.git_commit,
            "git_blame_author": self.git_blame_author,
        }


@dataclass
class ContainerImage:
    """A container image tracked for admission and escape detection."""

    digest: ImageDigest
    repository: str
    tag: str
    sbom_id: Optional[str] = None
    signed: bool = False
    signature_verified: bool = False
    scanned_at: Optional[datetime] = None
    vulnerabilities: dict[str, int] = field(default_factory=dict)  # severity -> count

    @property
    def full_reference(self) -> str:
        """Get full image reference."""
        return f"{self.repository}:{self.tag}@{self.digest}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "digest": self.digest,
            "repository": self.repository,
            "tag": self.tag,
            "sbom_id": self.sbom_id,
            "signed": self.signed,
            "signature_verified": self.signature_verified,
            "scanned_at": self.scanned_at.isoformat() if self.scanned_at else None,
            "vulnerabilities": self.vulnerabilities,
        }


@dataclass
class PolicyViolation:
    """A policy violation detected during admission."""

    policy_id: PolicyId
    policy_type: PolicyType
    description: str
    severity: Severity
    resource_path: Optional[str] = None  # JSONPath to violating field
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    remediation: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "policy_id": self.policy_id,
            "policy_type": self.policy_type.value,
            "description": self.description,
            "severity": self.severity.name,
            "resource_path": self.resource_path,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "remediation": self.remediation,
        }


@dataclass
class AdmissionPolicy:
    """A Kubernetes admission policy."""

    policy_id: PolicyId
    name: str
    policy_type: PolicyType
    mode: PolicyMode = PolicyMode.ENFORCE
    enabled: bool = True
    description: str = ""
    severity_threshold: Severity = Severity.HIGH
    namespaces: list[str] = field(default_factory=list)  # Empty = all namespaces
    resource_kinds: list[str] = field(
        default_factory=lambda: ["Pod", "Deployment", "StatefulSet"]
    )
    rego_policy: Optional[str] = None  # OPA Rego policy source
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

    def applies_to_namespace(self, namespace: str) -> bool:
        """Check if policy applies to a namespace."""
        if not self.namespaces:
            return True
        return namespace in self.namespaces

    def applies_to_kind(self, kind: str) -> bool:
        """Check if policy applies to a resource kind."""
        if not self.resource_kinds:
            return True
        return kind in self.resource_kinds

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "policy_type": self.policy_type.value,
            "mode": self.mode.value,
            "enabled": self.enabled,
            "description": self.description,
            "severity_threshold": self.severity_threshold.name,
            "namespaces": self.namespaces,
            "resource_kinds": self.resource_kinds,
            "rego_policy": self.rego_policy,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class AdmissionRequest:
    """A Kubernetes admission request."""

    uid: str
    kind: str
    namespace: str
    name: str
    operation: str  # CREATE, UPDATE, DELETE
    user_info: dict[str, Any] = field(default_factory=dict)
    object_spec: dict[str, Any] = field(default_factory=dict)
    old_object_spec: Optional[dict[str, Any]] = None
    dry_run: bool = False

    @property
    def containers(self) -> list[dict[str, Any]]:
        """Extract containers from Pod spec."""
        if self.kind == "Pod":
            spec = self.object_spec.get("spec", {})
        else:
            spec = self.object_spec.get("spec", {}).get("template", {}).get("spec", {})
        return spec.get("containers", []) + spec.get("initContainers", [])

    @property
    def images(self) -> list[str]:
        """Extract image references from containers."""
        return [c.get("image", "") for c in self.containers if c.get("image")]


@dataclass
class AdmissionDecision:
    """A Kubernetes admission decision."""

    decision_id: DecisionId
    request_uid: str
    cluster: ClusterName
    namespace: str
    resource_kind: str
    resource_name: str
    decision: AdmissionDecisionType
    violations: list[PolicyViolation] = field(default_factory=list)
    images_checked: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: Optional[float] = None

    @property
    def allowed(self) -> bool:
        """Check if admission was allowed."""
        return self.decision in (
            AdmissionDecisionType.ALLOW,
            AdmissionDecisionType.WARN,
        )

    @property
    def violation_count(self) -> int:
        """Count of policy violations."""
        return len(self.violations)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "decision_id": self.decision_id,
            "request_uid": self.request_uid,
            "cluster": self.cluster,
            "namespace": self.namespace,
            "resource_kind": self.resource_kind,
            "resource_name": self.resource_name,
            "decision": self.decision.value,
            "violations": [v.to_dict() for v in self.violations],
            "images_checked": self.images_checked,
            "timestamp": self.timestamp.isoformat(),
            "latency_ms": self.latency_ms,
        }


@dataclass
class EscapeEvent:
    """A container escape attempt detection."""

    event_id: EventId
    cluster: ClusterName
    node_id: str
    container_id: str
    pod_name: str
    namespace: str
    image_digest: Optional[ImageDigest] = None
    technique: EscapeTechnique = EscapeTechnique.NONE
    syscall: Optional[str] = None
    process_name: Optional[str] = None
    process_args: Optional[str] = None
    user_id: Optional[int] = None
    blocked: bool = False
    mitre_attack_id: Optional[str] = None
    falco_rule: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_event: dict[str, Any] = field(default_factory=dict)

    @property
    def severity(self) -> Severity:
        """Derive severity from escape technique."""
        critical_techniques = {
            EscapeTechnique.KERNEL_EXPLOIT,
            EscapeTechnique.DIRTY_PIPE,
            EscapeTechnique.OVERLAYFS,
        }
        high_techniques = {
            EscapeTechnique.PRIVILEGE_ESCALATION,
            EscapeTechnique.NAMESPACE_ESCAPE,
            EscapeTechnique.CGROUP_ESCAPE,
        }
        if self.technique in critical_techniques:
            return Severity.CRITICAL
        elif self.technique in high_techniques:
            return Severity.HIGH
        elif self.technique != EscapeTechnique.NONE:
            return Severity.MEDIUM
        return Severity.LOW

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "cluster": self.cluster,
            "node_id": self.node_id,
            "container_id": self.container_id,
            "pod_name": self.pod_name,
            "namespace": self.namespace,
            "image_digest": self.image_digest,
            "technique": self.technique.value,
            "severity": self.severity.name,
            "syscall": self.syscall,
            "process_name": self.process_name,
            "process_args": self.process_args,
            "user_id": self.user_id,
            "blocked": self.blocked,
            "mitre_attack_id": self.mitre_attack_id,
            "falco_rule": self.falco_rule,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class CorrelationResult:
    """Result of runtime event to code correlation."""

    event_id: EventId
    status: CorrelationStatus
    aws_resource: Optional[AWSResource] = None
    iac_resource: Optional[IaCResource] = None
    code_file: Optional[str] = None
    code_line_start: Optional[int] = None
    code_line_end: Optional[int] = None
    git_blame_author: Optional[str] = None
    git_commit: Optional[str] = None
    confidence: float = 0.0
    correlation_chain: list[str] = field(default_factory=list)
    error_message: Optional[str] = None

    @property
    def fully_correlated(self) -> bool:
        """Check if we have full correlation to code."""
        return (
            self.status == CorrelationStatus.CORRELATED
            and self.code_file is not None
            and self.code_line_start is not None
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "status": self.status.value,
            "aws_resource": self.aws_resource.to_dict() if self.aws_resource else None,
            "iac_resource": self.iac_resource.to_dict() if self.iac_resource else None,
            "code_file": self.code_file,
            "code_line_start": self.code_line_start,
            "code_line_end": self.code_line_end,
            "git_blame_author": self.git_blame_author,
            "git_commit": self.git_commit,
            "confidence": self.confidence,
            "correlation_chain": self.correlation_chain,
            "error_message": self.error_message,
        }


@dataclass
class ResourceMapping:
    """Mapping between AWS resource ARN and IaC definition."""

    aws_resource_arn: ResourceARN
    iac_file_path: str
    iac_resource_id: str
    iac_provider: IaCProvider
    terraform_state_key: Optional[str] = None
    git_commit: Optional[str] = None
    last_applied: Optional[datetime] = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "aws_resource_arn": self.aws_resource_arn,
            "iac_file_path": self.iac_file_path,
            "iac_resource_id": self.iac_resource_id,
            "iac_provider": self.iac_provider.value,
            "terraform_state_key": self.terraform_state_key,
            "git_commit": self.git_commit,
            "last_applied": (
                self.last_applied.isoformat() if self.last_applied else None
            ),
            "confidence": self.confidence,
        }


@dataclass
class FalcoRule:
    """A Falco detection rule configuration."""

    rule_id: str
    name: str
    description: str
    condition: str
    output: str
    priority: str = "WARNING"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    tags: list[str] = field(default_factory=list)
    mitre_attack_ids: list[str] = field(default_factory=list)
    enabled: bool = True

    def to_falco_yaml(self) -> dict[str, Any]:
        """Convert to Falco YAML format."""
        return {
            "rule": self.name,
            "desc": self.description,
            "condition": self.condition,
            "output": self.output,
            "priority": self.priority,
            "tags": self.tags + [f"mitre_{mid}" for mid in self.mitre_attack_ids],
            "enabled": self.enabled,
        }


@dataclass
class AdmissionWebhookConfig:
    """Configuration for the Kubernetes admission webhook."""

    webhook_name: str = "aura-admission-webhook"
    service_name: str = "aura-admission-controller"
    namespace: str = "aura-system"
    port: int = 443
    path: str = "/validate"
    failure_policy: str = "Fail"  # Fail or Ignore
    timeout_seconds: int = 10
    match_policy: str = "Equivalent"
    side_effects: str = "None"
    reinvocation_policy: str = "Never"

    def to_webhook_config(self) -> dict[str, Any]:
        """Generate ValidatingWebhookConfiguration."""
        return {
            "apiVersion": "admissionregistration.k8s.io/v1",
            "kind": "ValidatingWebhookConfiguration",
            "metadata": {"name": self.webhook_name},
            "webhooks": [
                {
                    "name": f"{self.webhook_name}.aura.local",
                    "clientConfig": {
                        "service": {
                            "name": self.service_name,
                            "namespace": self.namespace,
                            "port": self.port,
                            "path": self.path,
                        }
                    },
                    "rules": [
                        {
                            "apiGroups": ["", "apps"],
                            "apiVersions": ["v1"],
                            "operations": ["CREATE", "UPDATE"],
                            "resources": ["pods", "deployments", "statefulsets"],
                            "scope": "Namespaced",
                        }
                    ],
                    "failurePolicy": self.failure_policy,
                    "matchPolicy": self.match_policy,
                    "sideEffects": self.side_effects,
                    "timeoutSeconds": self.timeout_seconds,
                    "reinvocationPolicy": self.reinvocation_policy,
                    "admissionReviewVersions": ["v1", "v1beta1"],
                }
            ],
        }
