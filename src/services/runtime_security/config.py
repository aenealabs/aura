"""
Project Aura - Cloud Runtime Security Configuration

Configuration dataclasses for Kubernetes admission control, runtime-to-code
correlation, and container escape detection services.

Based on ADR-077: Cloud Runtime Security Integration
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from .contracts import PolicyMode, Severity


@dataclass
class AdmissionControllerConfig:
    """Configuration for Kubernetes admission controller."""

    enabled: bool = True
    webhook_port: int = 8443
    webhook_path: str = "/validate"
    tls_cert_path: Optional[str] = None
    tls_key_path: Optional[str] = None
    default_mode: PolicyMode = PolicyMode.ENFORCE
    severity_threshold: Severity = Severity.HIGH
    timeout_seconds: int = 10
    failure_policy: str = "Fail"  # Fail or Ignore
    require_sbom: bool = True
    require_signed_images: bool = True
    allowed_registries: list[str] = field(
        default_factory=lambda: [
            "*.dkr.ecr.*.amazonaws.com/*",
            "public.ecr.aws/aura-base-images/*",
        ]
    )
    blocked_registries: list[str] = field(default_factory=list)
    exempt_namespaces: list[str] = field(
        default_factory=lambda: ["kube-system", "kube-public", "aura-system"]
    )
    max_critical_cves: int = 0
    max_high_cves: int = 5


@dataclass
class RuntimeCorrelatorConfig:
    """Configuration for runtime-to-code correlation."""

    enabled: bool = True
    cloudtrail_enabled: bool = True
    guardduty_enabled: bool = True
    vpc_flow_logs_enabled: bool = True
    kinesis_stream_name: str = "aura-runtime-events"
    kinesis_shard_count: int = 4
    batch_size: int = 100
    batch_timeout_seconds: int = 5
    correlation_timeout_seconds: int = 30
    terraform_state_bucket: Optional[str] = None
    terraform_state_prefix: str = "terraform/"
    git_repository_path: Optional[str] = None
    cache_ttl_seconds: int = 300
    max_correlation_attempts: int = 3


@dataclass
class EscapeDetectorConfig:
    """Configuration for container escape detection."""

    enabled: bool = True
    falco_enabled: bool = True
    falco_grpc_endpoint: str = "unix:///var/run/falco/falco.sock"
    custom_ebpf_enabled: bool = False
    ebpf_ringbuf_size: int = 4096  # KB
    detection_rules_path: Optional[str] = None
    block_escapes: bool = False  # Start in detect-only mode
    alert_sns_topic: Optional[str] = None
    alert_eventbridge_bus: Optional[str] = None
    alert_slack_webhook: Optional[str] = None
    alert_pagerduty_key: Optional[str] = None
    syscalls_to_monitor: list[str] = field(
        default_factory=lambda: [
            "setuid",
            "setgid",
            "setresuid",
            "setresgid",
            "ptrace",
            "mount",
            "umount",
            "unshare",
            "clone",
            "nsenter",
        ]
    )
    capabilities_to_alert: list[str] = field(
        default_factory=lambda: [
            "CAP_SYS_ADMIN",
            "CAP_SYS_PTRACE",
            "CAP_NET_ADMIN",
            "CAP_DAC_OVERRIDE",
            "CAP_DAC_READ_SEARCH",
        ]
    )


@dataclass
class GraphIntegrationConfig:
    """Configuration for Neptune graph integration."""

    enabled: bool = True
    neptune_endpoint: Optional[str] = None
    neptune_port: int = 8182
    use_iam_auth: bool = True
    use_mock: bool = True  # Default to mock for testing
    connection_timeout_seconds: int = 30
    max_pool_size: int = 10


@dataclass
class StorageConfig:
    """Configuration for DynamoDB and OpenSearch storage."""

    runtime_events_table: str = "aura-runtime-events"
    resource_mappings_table: str = "aura-resource-mappings"
    admission_decisions_table: str = "aura-admission-decisions"
    escape_events_table: str = "aura-escape-events"
    opensearch_endpoint: Optional[str] = None
    opensearch_index_prefix: str = "aura-runtime"
    use_mock_storage: bool = True


@dataclass
class MetricsConfig:
    """Configuration for CloudWatch metrics."""

    enabled: bool = True
    namespace: str = "Aura/RuntimeSecurity"
    buffer_size: int = 20
    flush_interval_seconds: int = 60


@dataclass
class RuntimeSecurityConfig:
    """Root configuration for all runtime security services."""

    environment: str = "dev"
    enabled: bool = True
    cluster_name: str = "aura-eks-cluster"
    admission: AdmissionControllerConfig = field(
        default_factory=AdmissionControllerConfig
    )
    correlator: RuntimeCorrelatorConfig = field(default_factory=RuntimeCorrelatorConfig)
    escape_detector: EscapeDetectorConfig = field(default_factory=EscapeDetectorConfig)
    graph: GraphIntegrationConfig = field(default_factory=GraphIntegrationConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)

    def validate(self) -> list[str]:
        """Validate configuration consistency."""
        errors: list[str] = []

        if self.admission.timeout_seconds < 1:
            errors.append("admission.timeout_seconds must be >= 1")

        if self.admission.timeout_seconds > 30:
            errors.append("admission.timeout_seconds should be <= 30 for Kubernetes")

        if self.correlator.batch_size < 1:
            errors.append("correlator.batch_size must be >= 1")

        if self.correlator.correlation_timeout_seconds < 1:
            errors.append("correlator.correlation_timeout_seconds must be >= 1")

        if self.admission.max_critical_cves < 0:
            errors.append("admission.max_critical_cves cannot be negative")

        return errors

    @classmethod
    def from_environment(cls) -> "RuntimeSecurityConfig":
        """Load configuration from environment variables."""
        env = os.environ.get("ENVIRONMENT", "dev")

        # Parse severity threshold
        severity_str = os.environ.get("RUNTIME_SEVERITY_THRESHOLD", "HIGH")
        try:
            severity = Severity[severity_str]
        except KeyError:
            severity = Severity.HIGH

        # Parse policy mode
        mode_str = os.environ.get("RUNTIME_ADMISSION_MODE", "enforce")
        try:
            mode = PolicyMode(mode_str)
        except ValueError:
            mode = PolicyMode.ENFORCE

        return cls(
            environment=env,
            enabled=os.environ.get("RUNTIME_SECURITY_ENABLED", "true").lower()
            == "true",
            cluster_name=os.environ.get("EKS_CLUSTER_NAME", f"aura-eks-{env}"),
            admission=AdmissionControllerConfig(
                enabled=os.environ.get("RUNTIME_ADMISSION_ENABLED", "true").lower()
                == "true",
                webhook_port=int(os.environ.get("RUNTIME_WEBHOOK_PORT", "8443")),
                tls_cert_path=os.environ.get("RUNTIME_TLS_CERT_PATH"),
                tls_key_path=os.environ.get("RUNTIME_TLS_KEY_PATH"),
                default_mode=mode,
                severity_threshold=severity,
                timeout_seconds=int(os.environ.get("RUNTIME_WEBHOOK_TIMEOUT", "10")),
                require_sbom=os.environ.get("RUNTIME_REQUIRE_SBOM", "true").lower()
                == "true",
                require_signed_images=os.environ.get(
                    "RUNTIME_REQUIRE_SIGNED", "true"
                ).lower()
                == "true",
                max_critical_cves=int(os.environ.get("RUNTIME_MAX_CRITICAL_CVES", "0")),
                max_high_cves=int(os.environ.get("RUNTIME_MAX_HIGH_CVES", "5")),
            ),
            correlator=RuntimeCorrelatorConfig(
                enabled=os.environ.get("RUNTIME_CORRELATOR_ENABLED", "true").lower()
                == "true",
                cloudtrail_enabled=os.environ.get(
                    "RUNTIME_CLOUDTRAIL_ENABLED", "true"
                ).lower()
                == "true",
                guardduty_enabled=os.environ.get(
                    "RUNTIME_GUARDDUTY_ENABLED", "true"
                ).lower()
                == "true",
                kinesis_stream_name=os.environ.get(
                    "RUNTIME_KINESIS_STREAM", f"aura-runtime-events-{env}"
                ),
                terraform_state_bucket=os.environ.get("TERRAFORM_STATE_BUCKET"),
                git_repository_path=os.environ.get("GIT_REPOSITORY_PATH"),
            ),
            escape_detector=EscapeDetectorConfig(
                enabled=os.environ.get("RUNTIME_ESCAPE_ENABLED", "true").lower()
                == "true",
                falco_enabled=os.environ.get("RUNTIME_FALCO_ENABLED", "true").lower()
                == "true",
                custom_ebpf_enabled=os.environ.get(
                    "RUNTIME_EBPF_ENABLED", "false"
                ).lower()
                == "true",
                block_escapes=os.environ.get("RUNTIME_BLOCK_ESCAPES", "false").lower()
                == "true",
                alert_sns_topic=os.environ.get("RUNTIME_ALERT_SNS_TOPIC"),
                alert_eventbridge_bus=os.environ.get("RUNTIME_ALERT_EVENTBRIDGE"),
            ),
            graph=GraphIntegrationConfig(
                enabled=os.environ.get("RUNTIME_GRAPH_ENABLED", "true").lower()
                == "true",
                neptune_endpoint=os.environ.get("NEPTUNE_ENDPOINT"),
                use_mock=os.environ.get("RUNTIME_GRAPH_MOCK", "true").lower() == "true",
            ),
            storage=StorageConfig(
                runtime_events_table=os.environ.get(
                    "RUNTIME_EVENTS_TABLE", f"aura-runtime-events-{env}"
                ),
                resource_mappings_table=os.environ.get(
                    "RESOURCE_MAPPINGS_TABLE", f"aura-resource-mappings-{env}"
                ),
                admission_decisions_table=os.environ.get(
                    "ADMISSION_DECISIONS_TABLE", f"aura-admission-decisions-{env}"
                ),
                escape_events_table=os.environ.get(
                    "ESCAPE_EVENTS_TABLE", f"aura-escape-events-{env}"
                ),
                opensearch_endpoint=os.environ.get("OPENSEARCH_ENDPOINT"),
                use_mock_storage=os.environ.get("RUNTIME_MOCK_STORAGE", "true").lower()
                == "true",
            ),
            metrics=MetricsConfig(
                enabled=os.environ.get("RUNTIME_METRICS_ENABLED", "true").lower()
                == "true",
                namespace=os.environ.get(
                    "RUNTIME_METRICS_NAMESPACE", "Aura/RuntimeSecurity"
                ),
            ),
        )

    @classmethod
    def for_production(cls) -> "RuntimeSecurityConfig":
        """Create production-hardened configuration."""
        return cls(
            environment="prod",
            enabled=True,
            admission=AdmissionControllerConfig(
                enabled=True,
                default_mode=PolicyMode.ENFORCE,
                severity_threshold=Severity.HIGH,
                require_sbom=True,
                require_signed_images=True,
                max_critical_cves=0,
                max_high_cves=0,
                failure_policy="Fail",
            ),
            correlator=RuntimeCorrelatorConfig(
                enabled=True,
                cloudtrail_enabled=True,
                guardduty_enabled=True,
                vpc_flow_logs_enabled=True,
            ),
            escape_detector=EscapeDetectorConfig(
                enabled=True,
                falco_enabled=True,
                custom_ebpf_enabled=True,
                block_escapes=True,
            ),
            graph=GraphIntegrationConfig(
                enabled=True,
                use_mock=False,
            ),
            storage=StorageConfig(
                use_mock_storage=False,
            ),
            metrics=MetricsConfig(
                enabled=True,
            ),
        )

    @classmethod
    def for_testing(cls) -> "RuntimeSecurityConfig":
        """Create configuration for unit tests."""
        return cls(
            environment="test",
            enabled=True,
            cluster_name="test-cluster",
            admission=AdmissionControllerConfig(
                enabled=True,
                default_mode=PolicyMode.AUDIT,
                timeout_seconds=5,
                require_sbom=False,
                require_signed_images=False,
            ),
            correlator=RuntimeCorrelatorConfig(
                enabled=True,
                batch_size=10,
                correlation_timeout_seconds=5,
            ),
            escape_detector=EscapeDetectorConfig(
                enabled=True,
                falco_enabled=False,
                custom_ebpf_enabled=False,
                block_escapes=False,
            ),
            graph=GraphIntegrationConfig(
                enabled=True,
                use_mock=True,
            ),
            storage=StorageConfig(
                use_mock_storage=True,
            ),
            metrics=MetricsConfig(
                enabled=False,
            ),
        )


# Singleton instance
_config_instance: Optional[RuntimeSecurityConfig] = None


def get_runtime_security_config() -> RuntimeSecurityConfig:
    """Get singleton configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = RuntimeSecurityConfig.from_environment()
    return _config_instance


def reset_runtime_security_config() -> None:
    """Reset configuration singleton (for testing)."""
    global _config_instance
    _config_instance = None


def set_runtime_security_config(config: RuntimeSecurityConfig) -> None:
    """Set configuration singleton (for testing)."""
    global _config_instance
    _config_instance = config
