"""Drift detection for Environment Validator (ADR-062 Phase 2).

Compares current K8s resource state against validated baseline
to detect configuration drift that may introduce cross-environment issues.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.services.env_validator.engine import ValidationEngine
from src.services.env_validator.models import Severity, TriggerType, ValidationRun

logger = logging.getLogger(__name__)


@dataclass
class DriftEvent:
    """Represents a detected drift event."""

    event_id: str
    resource_type: str
    resource_name: str
    namespace: str
    field_path: str
    baseline_value: str
    current_value: str
    detected_at: datetime
    severity: Severity
    environment: str
    baseline_hash: str
    current_hash: str

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "resource_type": self.resource_type,
            "resource_name": self.resource_name,
            "namespace": self.namespace,
            "field_path": self.field_path,
            "baseline_value": self.baseline_value,
            "current_value": self.current_value,
            "detected_at": self.detected_at.isoformat(),
            "severity": self.severity.value,
            "environment": self.environment,
            "baseline_hash": self.baseline_hash,
            "current_hash": self.current_hash,
        }


@dataclass
class DriftReport:
    """Summary report of drift detection run."""

    run_id: str
    environment: str
    timestamp: datetime
    resources_checked: int
    drift_events: list[DriftEvent]
    validation_run: Optional[ValidationRun]

    @property
    def has_drift(self) -> bool:
        """Check if any drift was detected."""
        return len(self.drift_events) > 0

    @property
    def critical_drift_count(self) -> int:
        """Count of critical drift events."""
        return sum(1 for e in self.drift_events if e.severity == Severity.CRITICAL)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "run_id": self.run_id,
            "environment": self.environment,
            "timestamp": self.timestamp.isoformat(),
            "resources_checked": self.resources_checked,
            "has_drift": self.has_drift,
            "critical_drift_count": self.critical_drift_count,
            "drift_events": [e.to_dict() for e in self.drift_events],
            "validation_run": (
                self.validation_run.to_dict() if self.validation_run else None
            ),
        }


class DriftDetector:
    """Detects configuration drift from validated baseline."""

    def __init__(self, environment: str, baseline_manager: "BaselineManager"):
        """Initialize drift detector.

        Args:
            environment: Target environment (dev, qa, staging, prod)
            baseline_manager: Manager for baseline storage/retrieval
        """
        self.environment = environment
        self.baseline_manager = baseline_manager
        self.validation_engine = ValidationEngine(environment)

    def detect_drift(self, current_manifest: str) -> DriftReport:
        """Detect drift between current state and baseline.

        Args:
            current_manifest: Current Kubernetes manifest YAML

        Returns:
            DriftReport with detected drift events
        """
        import uuid

        import yaml

        run_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow()
        drift_events = []

        # Parse current manifest
        try:
            docs = list(yaml.safe_load_all(current_manifest))
            docs = [d for d in docs if d]  # Filter None documents
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse current manifest: {e}")
            return DriftReport(
                run_id=run_id,
                environment=self.environment,
                timestamp=timestamp,
                resources_checked=0,
                drift_events=[],
                validation_run=None,
            )

        # First, validate current manifest
        validation_run = self.validation_engine.validate_manifest(
            current_manifest, TriggerType.DRIFT_DETECTION
        )

        # Compare each resource against baseline
        for doc in docs:
            if not isinstance(doc, dict):
                continue

            kind = doc.get("kind", "Unknown")
            metadata = doc.get("metadata", {})
            name = metadata.get("name", "unknown")
            namespace = metadata.get("namespace", "default")

            # Get baseline for this resource
            baseline = self.baseline_manager.get_baseline(
                environment=self.environment,
                resource_type=kind,
                resource_name=name,
                namespace=namespace,
            )

            if baseline is None:
                # No baseline - new resource, check if it passes validation
                logger.debug(f"No baseline for {kind}/{name}, skipping drift check")
                continue

            # Compare key fields for drift
            events = self._compare_resource(
                baseline=baseline,
                current=doc,
                kind=kind,
                name=name,
                namespace=namespace,
                run_id=run_id,
            )
            drift_events.extend(events)

        return DriftReport(
            run_id=run_id,
            environment=self.environment,
            timestamp=timestamp,
            resources_checked=len(docs),
            drift_events=drift_events,
            validation_run=validation_run,
        )

    def _compare_resource(
        self,
        baseline: dict,
        current: dict,
        kind: str,
        name: str,
        namespace: str,
        run_id: str,
    ) -> list[DriftEvent]:
        """Compare a single resource against baseline.

        Args:
            baseline: Baseline resource state
            current: Current resource state
            kind: Kubernetes resource kind
            name: Resource name
            namespace: Resource namespace
            run_id: Drift detection run ID

        Returns:
            List of detected drift events
        """
        drift_events = []

        # Define critical fields to monitor by resource type
        critical_fields = self._get_critical_fields(kind)

        for field_path in critical_fields:
            baseline_value = self._get_nested_value(baseline, field_path)
            current_value = self._get_nested_value(current, field_path)

            if baseline_value != current_value:
                # Determine severity based on field
                severity = self._determine_drift_severity(kind, field_path)

                event = DriftEvent(
                    event_id=f"{run_id}-{kind}-{name}-{field_path}".replace(".", "-"),
                    resource_type=kind,
                    resource_name=name,
                    namespace=namespace,
                    field_path=field_path,
                    baseline_value=(
                        str(baseline_value) if baseline_value else "<not set>"
                    ),
                    current_value=str(current_value) if current_value else "<not set>",
                    detected_at=datetime.utcnow(),
                    severity=severity,
                    environment=self.environment,
                    baseline_hash=self._compute_hash(baseline_value),
                    current_hash=self._compute_hash(current_value),
                )
                drift_events.append(event)
                logger.warning(
                    f"Drift detected in {kind}/{name}: {field_path} "
                    f"changed from {baseline_value} to {current_value}"
                )

        return drift_events

    def _get_critical_fields(self, kind: str) -> list[str]:
        """Get list of critical fields to monitor for a resource type.

        Args:
            kind: Kubernetes resource kind

        Returns:
            List of field paths to monitor
        """
        common_fields = [
            "metadata.labels.environment",
            "metadata.labels.app",
        ]

        kind_fields = {
            "ConfigMap": [
                "data.ENVIRONMENT",
                "data.NEPTUNE_ENDPOINT",
                "data.OPENSEARCH_ENDPOINT",
                "data.JOBS_TABLE_NAME",
                "data.QUOTAS_TABLE_NAME",
                "data.APPROVAL_TABLE_NAME",
                "data.WORKFLOW_TABLE_NAME",
                "data.SNS_TOPIC_ARN",
                "data.HITL_SNS_TOPIC_ARN",
            ],
            "Deployment": [
                "spec.template.spec.containers.0.image",
                "spec.template.spec.serviceAccountName",
            ],
            "ServiceAccount": [
                # Use bracket notation for keys containing dots
                "metadata.annotations[eks.amazonaws.com/role-arn]",
            ],
            "Secret": [
                "metadata.labels.environment",
            ],
        }

        return common_fields + kind_fields.get(kind, [])

    def _determine_drift_severity(self, kind: str, field_path: str) -> Severity:
        """Determine severity of drift for a given field.

        Args:
            kind: Kubernetes resource kind
            field_path: Path to the field that drifted

        Returns:
            Severity level for the drift
        """
        # Critical drift fields
        critical_patterns = [
            "NEPTUNE_ENDPOINT",
            "OPENSEARCH_ENDPOINT",
            "TABLE_NAME",
            "SNS_TOPIC_ARN",
            "containers.0.image",
            "role-arn",
        ]

        for pattern in critical_patterns:
            if pattern in field_path:
                return Severity.CRITICAL

        # Warning drift fields
        warning_patterns = [
            "ENVIRONMENT",
            "environment",
            "serviceAccountName",
        ]

        for pattern in warning_patterns:
            if pattern in field_path:
                return Severity.WARNING

        return Severity.INFO

    def _get_nested_value(self, obj: dict, path: str):
        """Get a nested value from a dictionary using dot notation.

        Supports bracket notation for keys containing dots:
        - "data.ENVIRONMENT" -> obj["data"]["ENVIRONMENT"]
        - "metadata.annotations[eks.amazonaws.com/role-arn]" -> obj["metadata"]["annotations"]["eks.amazonaws.com/role-arn"]

        Args:
            obj: Dictionary to search
            path: Dot-separated path (e.g., "data.ENVIRONMENT")

        Returns:
            Value at path or None if not found
        """
        # Parse path with bracket notation support
        parts = []
        i = 0
        current_part = ""

        while i < len(path):
            char = path[i]

            if char == ".":
                # End of current part
                if current_part:
                    parts.append(current_part)
                    current_part = ""
            elif char == "[":
                # Start of bracketed key
                if current_part:
                    parts.append(current_part)
                    current_part = ""
                # Find matching closing bracket
                bracket_end = path.find("]", i)
                if bracket_end == -1:
                    # No closing bracket, treat rest as regular path
                    current_part = path[i:]
                    break
                # Extract bracketed key
                bracketed_key = path[i + 1 : bracket_end]
                parts.append(bracketed_key)
                i = bracket_end
            else:
                current_part += char
            i += 1

        # Don't forget the last part
        if current_part:
            parts.append(current_part)

        current = obj

        for part in parts:
            if current is None:
                return None

            # Handle array indices
            if part.isdigit():
                idx = int(part)
                if isinstance(current, list) and idx < len(current):
                    current = current[idx]
                else:
                    return None
            elif isinstance(current, dict):
                current = current.get(part)
            else:
                return None

        return current

    def _compute_hash(self, value) -> str:
        """Compute hash of a value for comparison.

        Args:
            value: Value to hash

        Returns:
            SHA256 hash of the value
        """
        if value is None:
            return "null"
        return hashlib.sha256(str(value).encode()).hexdigest()[:16]


# Import at module level to avoid circular imports
from src.services.env_validator.baseline_manager import BaselineManager  # noqa: E402
