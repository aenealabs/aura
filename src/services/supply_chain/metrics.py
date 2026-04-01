"""
Project Aura - Supply Chain Security Metrics

CloudWatch metrics publisher for SBOM attestation, dependency confusion detection,
and license compliance services.

Metrics Published:
- SBOMGenerated: Count of SBOMs generated
- SBOMGenerationLatencyMs: Time to generate SBOM
- AttestationSigned: Count of attestations created
- AttestationSigningLatencyMs: Time to sign SBOM
- AttestationVerified: Count of verification attempts
- ConfusionAnalyzed: Count of packages analyzed
- ConfusionDetected: Count of confusion issues found
- ConfusionAnalysisLatencyMs: Time to analyze package
- LicenseChecked: Count of license checks
- LicenseViolation: Count of violations detected
- LicenseCheckLatencyMs: Time to check compliance
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from .config import MetricsConfig, get_supply_chain_config
from .contracts import RiskLevel

logger = logging.getLogger(__name__)


class CloudWatchClient(Protocol):
    """Protocol for CloudWatch client."""

    def put_metric_data(self, **kwargs: Any) -> dict[str, Any]:
        """Put metric data to CloudWatch."""
        ...


class SupplyChainMetricsPublisher:
    """CloudWatch metrics publisher for supply chain services."""

    def __init__(
        self,
        cloudwatch_client: Optional[CloudWatchClient] = None,
        config: Optional[MetricsConfig] = None,
    ):
        """Initialize metrics publisher.

        Args:
            cloudwatch_client: CloudWatch client (mock mode if None)
            config: Metrics configuration
        """
        if config is None:
            config = get_supply_chain_config().metrics
        self.config = config

        self._cloudwatch = cloudwatch_client
        self._mock_mode = cloudwatch_client is None

        # Metric buffer for batch publishing
        self._metric_buffer: list[dict[str, Any]] = []

        logger.info(
            f"SupplyChainMetricsPublisher initialized "
            f"(mock_mode={self._mock_mode}, namespace={self.config.namespace})"
        )

    # -------------------------------------------------------------------------
    # SBOM Generation Metrics
    # -------------------------------------------------------------------------

    def record_sbom_generated(
        self,
        repository_id: str,
        format_type: str,
        component_count: int,
        latency_ms: float,
    ) -> None:
        """Record SBOM generation metrics."""
        if not self.config.enabled:
            return

        dimensions = {
            "RepositoryId": repository_id[:64],  # Truncate for CloudWatch
            "Format": format_type,
        }

        self._add_metric("SBOMGenerated", 1.0, dimensions=dimensions)
        self._add_metric("SBOMComponentCount", float(component_count), unit="Count")
        self._add_metric(
            "SBOMGenerationLatencyMs",
            latency_ms,
            unit="Milliseconds",
            dimensions=dimensions,
        )

    def record_sbom_generation_error(
        self,
        repository_id: str,
        error_type: str,
    ) -> None:
        """Record SBOM generation error."""
        if not self.config.enabled:
            return

        self._add_metric(
            "SBOMGenerationError",
            1.0,
            dimensions={
                "RepositoryId": repository_id[:64],
                "ErrorType": error_type,
            },
        )

    # -------------------------------------------------------------------------
    # Attestation Metrics
    # -------------------------------------------------------------------------

    def record_attestation_signed(
        self,
        signing_method: str,
        latency_ms: float,
        rekor_recorded: bool = False,
    ) -> None:
        """Record attestation signing metrics."""
        if not self.config.enabled:
            return

        dimensions = {
            "SigningMethod": signing_method,
            "RekorRecorded": str(rekor_recorded).lower(),
        }

        self._add_metric("AttestationSigned", 1.0, dimensions=dimensions)
        self._add_metric(
            "AttestationSigningLatencyMs",
            latency_ms,
            unit="Milliseconds",
            dimensions=dimensions,
        )

    def record_attestation_verified(
        self,
        verification_status: str,
        latency_ms: float,
    ) -> None:
        """Record attestation verification metrics."""
        if not self.config.enabled:
            return

        dimensions = {"VerificationStatus": verification_status}

        self._add_metric("AttestationVerified", 1.0, dimensions=dimensions)
        self._add_metric(
            "AttestationVerificationLatencyMs",
            latency_ms,
            unit="Milliseconds",
            dimensions=dimensions,
        )

    def record_signing_error(
        self,
        signing_method: str,
        error_type: str,
    ) -> None:
        """Record signing error."""
        if not self.config.enabled:
            return

        self._add_metric(
            "SigningError",
            1.0,
            dimensions={
                "SigningMethod": signing_method,
                "ErrorType": error_type,
            },
        )

    # -------------------------------------------------------------------------
    # Dependency Confusion Metrics
    # -------------------------------------------------------------------------

    def record_confusion_analysis(
        self,
        ecosystem: str,
        package_count: int,
        issues_found: int,
        latency_ms: float,
    ) -> None:
        """Record dependency confusion analysis metrics."""
        if not self.config.enabled:
            return

        dimensions = {"Ecosystem": ecosystem}

        self._add_metric(
            "ConfusionAnalyzed", float(package_count), dimensions=dimensions
        )
        self._add_metric(
            "ConfusionIssuesFound", float(issues_found), dimensions=dimensions
        )
        self._add_metric(
            "ConfusionAnalysisLatencyMs",
            latency_ms,
            unit="Milliseconds",
            dimensions=dimensions,
        )

    def record_confusion_detected(
        self,
        package_name: str,
        confusion_type: str,
        risk_level: RiskLevel,
    ) -> None:
        """Record detected confusion issue."""
        if not self.config.enabled:
            return

        self._add_metric(
            "ConfusionDetected",
            1.0,
            dimensions={
                "ConfusionType": confusion_type,
                "RiskLevel": risk_level.name,
            },
        )

    # -------------------------------------------------------------------------
    # License Compliance Metrics
    # -------------------------------------------------------------------------

    def record_license_check(
        self,
        component_count: int,
        violations_found: int,
        compliance_status: str,
        latency_ms: float,
    ) -> None:
        """Record license compliance check metrics."""
        if not self.config.enabled:
            return

        dimensions = {"ComplianceStatus": compliance_status}

        self._add_metric(
            "LicenseChecked", float(component_count), dimensions=dimensions
        )
        self._add_metric(
            "LicenseViolationsFound", float(violations_found), dimensions=dimensions
        )
        self._add_metric(
            "LicenseCheckLatencyMs",
            latency_ms,
            unit="Milliseconds",
            dimensions=dimensions,
        )

    def record_license_violation(
        self,
        license_id: str,
        violation_type: str,
        severity: RiskLevel,
    ) -> None:
        """Record license violation."""
        if not self.config.enabled:
            return

        self._add_metric(
            "LicenseViolation",
            1.0,
            dimensions={
                "LicenseId": license_id[:64],
                "ViolationType": violation_type,
                "Severity": severity.name,
            },
        )

    def record_attribution_generated(
        self,
        component_count: int,
        format_type: str,
        latency_ms: float,
    ) -> None:
        """Record attribution file generation metrics."""
        if not self.config.enabled:
            return

        self._add_metric(
            "AttributionGenerated",
            1.0,
            dimensions={"Format": format_type},
        )
        self._add_metric(
            "AttributionComponentCount", float(component_count), unit="Count"
        )
        self._add_metric(
            "AttributionGenerationLatencyMs", latency_ms, unit="Milliseconds"
        )

    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------

    def _add_metric(
        self,
        metric_name: str,
        value: float,
        dimensions: Optional[dict[str, str]] = None,
        unit: str = "Count",
    ) -> None:
        """Add metric to buffer."""
        metric = {
            "MetricName": metric_name,
            "Value": value,
            "Timestamp": datetime.now(timezone.utc),
            "Unit": unit,
            "Dimensions": [
                {"Name": k, "Value": v} for k, v in (dimensions or {}).items()
            ],
        }
        self._metric_buffer.append(metric)

        if len(self._metric_buffer) >= self.config.buffer_size:
            self.flush()

    def flush(self) -> None:
        """Publish buffered metrics to CloudWatch."""
        if not self._metric_buffer:
            return

        if self._mock_mode:
            logger.debug(f"Mock: Publishing {len(self._metric_buffer)} metrics")
            self._metric_buffer.clear()
            return

        try:
            self._cloudwatch.put_metric_data(
                Namespace=self.config.namespace,
                MetricData=self._metric_buffer,
            )
            logger.debug(f"Published {len(self._metric_buffer)} metrics")
            self._metric_buffer.clear()
        except Exception as e:
            logger.error(f"Failed to publish metrics: {e}")


# Singleton instance
_metrics_instance: Optional[SupplyChainMetricsPublisher] = None


def get_supply_chain_metrics() -> SupplyChainMetricsPublisher:
    """Get singleton metrics publisher instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = SupplyChainMetricsPublisher()
    return _metrics_instance


def reset_supply_chain_metrics() -> None:
    """Reset metrics publisher singleton (for testing)."""
    global _metrics_instance
    if _metrics_instance is not None:
        _metrics_instance.flush()
    _metrics_instance = None


class MetricsTimer:
    """Context manager for timing operations and recording latency metrics."""

    def __init__(self):
        self.start_time: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self) -> "MetricsTimer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.elapsed_ms = (time.perf_counter() - self.start_time) * 1000
