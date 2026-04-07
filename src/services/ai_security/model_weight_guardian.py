"""
Project Aura - Model Weight Guardian

Protects AI model weights from unauthorized access and
exfiltration using access pattern analysis and anomaly detection.

Based on ADR-079: Scale & AI Model Security
"""

import hashlib
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .config import AISecurityConfig, get_ai_security_config
from .contracts import (
    AccessPattern,
    AccessType,
    AlertStatus,
    AuditReport,
    ModelSecurityPolicy,
    ModelStatus,
    ModelWeightAccess,
    MonitoredModel,
    ThreatSeverity,
    ThreatType,
    WeightThreatDetection,
)
from .exceptions import (
    InvalidPolicyError,
    ModelAlreadyRegisteredError,
    ModelNotRegisteredError,
)


class ModelWeightGuardian:
    """
    Protects AI model weights from unauthorized access.

    Features:
    - Access pattern monitoring
    - Anomaly detection (unusual access times, volumes)
    - Exfiltration detection
    - Policy enforcement
    - Integration with training pipelines
    """

    def __init__(self, config: Optional[AISecurityConfig] = None):
        """Initialize Model Weight Guardian."""
        self._config = config or get_ai_security_config()

        # In-memory storage for testing
        self._models: dict[str, MonitoredModel] = {}
        self._policies: dict[str, ModelSecurityPolicy] = {}
        self._access_logs: list[ModelWeightAccess] = []
        self._detections: dict[str, WeightThreatDetection] = {}
        self._access_patterns: dict[str, dict[str, AccessPattern]] = (
            {}
        )  # model_id -> accessor -> pattern
        self._daily_access_counts: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )  # model_id -> accessor -> count

    async def register_model(
        self,
        model_id: str,
        name: str,
        version: str,
        weight_paths: list[str],
        policy: Optional[ModelSecurityPolicy] = None,
    ) -> MonitoredModel:
        """Register model for monitoring."""
        if model_id in self._models:
            raise ModelAlreadyRegisteredError(model_id)

        # Calculate weight hash
        weight_hash = self._calculate_weight_hash(weight_paths)

        # Calculate total size (in real impl, would check actual files)
        total_size = 0

        model = MonitoredModel(
            model_id=model_id,
            name=name,
            version=version,
            weight_paths=weight_paths,
            weight_hash=weight_hash,
            total_size_bytes=total_size,
            status=ModelStatus.ACTIVE,
            policy_id=policy.policy_id if policy else None,
        )

        self._models[model_id] = model

        if policy:
            self._policies[policy.policy_id] = policy

        return model

    async def unregister_model(self, model_id: str) -> bool:
        """Unregister model from monitoring."""
        if model_id not in self._models:
            raise ModelNotRegisteredError(model_id)

        del self._models[model_id]
        return True

    async def get_model(self, model_id: str) -> Optional[MonitoredModel]:
        """Get monitored model by ID."""
        return self._models.get(model_id)

    async def list_models(
        self,
        status: Optional[ModelStatus] = None,
    ) -> list[MonitoredModel]:
        """List all monitored models."""
        models = list(self._models.values())
        if status:
            models = [m for m in models if m.status == status]
        return models

    async def set_policy(
        self,
        model_id: str,
        policy: ModelSecurityPolicy,
    ) -> None:
        """Set security policy for model."""
        if model_id not in self._models:
            raise ModelNotRegisteredError(model_id)

        # Validate policy
        errors = self._validate_policy(policy)
        if errors:
            raise InvalidPolicyError(policy.policy_id, "; ".join(errors))

        self._policies[policy.policy_id] = policy
        self._models[model_id].policy_id = policy.policy_id

    async def get_policy(self, policy_id: str) -> Optional[ModelSecurityPolicy]:
        """Get security policy by ID."""
        return self._policies.get(policy_id)

    def _validate_policy(self, policy: ModelSecurityPolicy) -> list[str]:
        """Validate security policy."""
        errors = []

        if policy.max_daily_reads < 0:
            errors.append("max_daily_reads must be >= 0")

        if policy.max_bytes_per_access < 0:
            errors.append("max_bytes_per_access must be >= 0")

        if policy.alert_threshold < 0 or policy.alert_threshold > 1:
            errors.append("alert_threshold must be between 0 and 1")

        return errors

    async def log_access(
        self,
        access: ModelWeightAccess,
    ) -> Optional[WeightThreatDetection]:
        """Log access and check for threats."""
        if access.model_id not in self._models:
            raise ModelNotRegisteredError(access.model_id)

        model = self._models[access.model_id]

        # Check policy first
        if model.policy_id:
            policy = self._policies.get(model.policy_id)
            if policy and policy.enabled:
                violation = await self._check_policy_violation(access, policy)
                if violation:
                    return violation

        # Log the access
        self._access_logs.append(access)
        model.last_accessed_at = access.timestamp
        model.access_count_24h += 1

        # Update daily access count
        self._daily_access_counts[access.model_id][access.accessor_identity] += 1

        # Check for threats
        if self._config.model_guardian.anomaly_detection_enabled:
            threat = await self._detect_threats(access, model)
            if threat:
                self._detections[threat.detection_id] = threat
                return threat

        return None

    async def _check_policy_violation(
        self,
        access: ModelWeightAccess,
        policy: ModelSecurityPolicy,
    ) -> Optional[WeightThreatDetection]:
        """Check if access violates policy."""
        violations = []

        # Check allowed identities
        if (
            policy.allowed_identities
            and access.accessor_identity not in policy.allowed_identities
        ):
            violations.append("Accessor not in allowed list")

        # Check allowed IPs
        if policy.allowed_ips and access.accessor_ip not in policy.allowed_ips:
            violations.append("IP not in allowed list")

        # Check allowed access types
        if (
            policy.allowed_access_types
            and access.access_type not in policy.allowed_access_types
        ):
            violations.append(f"Access type {access.access_type.value} not allowed")

        # Check export blocking
        if policy.export_blocked and access.access_type in (
            AccessType.EXPORT,
            AccessType.COPY,
            AccessType.NETWORK_TRANSFER,
        ):
            violations.append("Export/copy operations blocked")

        # Check bytes per access
        if (
            policy.max_bytes_per_access > 0
            and access.bytes_accessed > policy.max_bytes_per_access
        ):
            violations.append(
                f"Bytes accessed ({access.bytes_accessed}) exceeds limit ({policy.max_bytes_per_access})"
            )

        # Check daily read limit
        daily_count = self._daily_access_counts[access.model_id].get(
            access.accessor_identity, 0
        )
        if daily_count >= policy.max_daily_reads:
            violations.append(f"Daily read limit ({policy.max_daily_reads}) exceeded")

        if violations:
            access.approved = False
            return WeightThreatDetection(
                detection_id=self._generate_id("det"),
                threat_type=ThreatType.UNAUTHORIZED_ACCESS,
                model_id=access.model_id,
                severity=ThreatSeverity.HIGH,
                confidence=1.0,
                access_events=[access],
                anomaly_indicators=violations,
                recommended_action="Block access and investigate",
            )

        return None

    async def _detect_threats(
        self,
        access: ModelWeightAccess,
        model: MonitoredModel,
    ) -> Optional[WeightThreatDetection]:
        """Detect potential threats from access pattern."""
        indicators = []
        threat_type = None
        severity = ThreatSeverity.MEDIUM
        confidence = 0.0

        # Get or create access pattern for this accessor
        pattern = await self._get_or_create_pattern(
            access.model_id, access.accessor_identity
        )

        # Check for unusual access time
        access_hour = access.timestamp.hour
        if (
            pattern.typical_access_times
            and access_hour not in pattern.typical_access_times
        ):
            indicators.append(f"Unusual access time: {access_hour}:00")
            confidence += 0.3

        # Check for unusual access volume
        if pattern.typical_bytes_per_access > 0:
            ratio = access.bytes_accessed / pattern.typical_bytes_per_access
            if ratio > 5:
                indicators.append(f"Unusual data volume: {ratio:.1f}x typical")
                confidence += 0.4

        # Check for potential exfiltration
        if access.access_type in (
            AccessType.EXPORT,
            AccessType.COPY,
            AccessType.NETWORK_TRANSFER,
        ):
            indicators.append(f"Sensitive operation: {access.access_type.value}")
            threat_type = ThreatType.EXFILTRATION
            severity = ThreatSeverity.CRITICAL
            confidence += 0.5

        # Check for rapid succession of accesses
        recent_accesses = [
            a
            for a in self._access_logs[-100:]
            if a.model_id == access.model_id
            and a.accessor_identity == access.accessor_identity
            and (access.timestamp - a.timestamp).total_seconds() < 60
        ]
        if len(recent_accesses) > 10:
            indicators.append(
                f"Rapid access pattern: {len(recent_accesses)} accesses in 60s"
            )
            confidence += 0.3

        if indicators and confidence >= self._config.model_guardian.anomaly_threshold:
            return WeightThreatDetection(
                detection_id=self._generate_id("det"),
                threat_type=threat_type or ThreatType.UNAUTHORIZED_ACCESS,
                model_id=access.model_id,
                severity=severity,
                confidence=min(1.0, confidence),
                access_events=[access],
                anomaly_indicators=indicators,
                recommended_action=self._get_recommended_action(threat_type, severity),
            )

        return None

    async def _get_or_create_pattern(
        self,
        model_id: str,
        accessor_identity: str,
    ) -> AccessPattern:
        """Get or create access pattern for accessor."""
        if model_id not in self._access_patterns:
            self._access_patterns[model_id] = {}

        if accessor_identity not in self._access_patterns[model_id]:
            self._access_patterns[model_id][accessor_identity] = AccessPattern(
                pattern_id=self._generate_id("pattern"),
                model_id=model_id,
                accessor_identity=accessor_identity,
            )

        return self._access_patterns[model_id][accessor_identity]

    def _get_recommended_action(
        self,
        threat_type: Optional[ThreatType],
        severity: ThreatSeverity,
    ) -> str:
        """Get recommended action for threat."""
        if severity == ThreatSeverity.CRITICAL:
            return "Immediately block access, quarantine model, investigate accessor"
        elif severity == ThreatSeverity.HIGH:
            return "Block access, alert security team, investigate"
        elif severity == ThreatSeverity.MEDIUM:
            return "Monitor closely, consider temporary access restriction"
        else:
            return "Log and continue monitoring"

    async def detect_anomalies(
        self,
        model_id: str,
        time_window_hours: int = 24,
    ) -> list[WeightThreatDetection]:
        """Detect anomalous access patterns."""
        if model_id not in self._models:
            raise ModelNotRegisteredError(model_id)

        detections = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)

        # Get recent accesses for this model
        recent_accesses = [
            a
            for a in self._access_logs
            if a.model_id == model_id and a.timestamp >= cutoff_time
        ]

        if not recent_accesses:
            return detections

        # Analyze access patterns
        by_accessor: dict[str, list[ModelWeightAccess]] = defaultdict(list)
        for access in recent_accesses:
            by_accessor[access.accessor_identity].append(access)

        for accessor, accesses in by_accessor.items():
            # Detect potential exfiltration
            export_count = sum(
                1
                for a in accesses
                if a.access_type
                in (AccessType.EXPORT, AccessType.COPY, AccessType.NETWORK_TRANSFER)
            )

            if export_count > 0:
                detections.append(
                    WeightThreatDetection(
                        detection_id=self._generate_id("det"),
                        threat_type=ThreatType.EXFILTRATION,
                        model_id=model_id,
                        severity=ThreatSeverity.HIGH,
                        confidence=0.8,
                        access_events=accesses,
                        anomaly_indicators=[
                            f"Export/copy operations detected: {export_count}"
                        ],
                        recommended_action="Investigate data export attempts",
                    )
                )

        return detections

    async def enforce_policy(
        self,
        model_id: str,
        access_request: dict[str, Any],
    ) -> tuple[bool, str]:
        """Check if access is allowed by policy."""
        if model_id not in self._models:
            raise ModelNotRegisteredError(model_id)

        model = self._models[model_id]

        if not model.policy_id:
            return True, "No policy configured"

        policy = self._policies.get(model.policy_id)
        if not policy or not policy.enabled:
            return True, "Policy disabled"

        # Extract access info
        accessor = access_request.get("accessor_identity", "")
        ip = access_request.get("accessor_ip", "")
        access_type_str = access_request.get("access_type", "read")

        try:
            access_type = AccessType(access_type_str)
        except ValueError:
            return False, f"Invalid access type: {access_type_str}"

        # Check allowed identities
        if policy.allowed_identities and accessor not in policy.allowed_identities:
            return False, "Accessor not authorized"

        # Check allowed IPs
        if policy.allowed_ips and ip not in policy.allowed_ips:
            return False, "IP not authorized"

        # Check allowed access types
        if (
            policy.allowed_access_types
            and access_type not in policy.allowed_access_types
        ):
            return False, f"Access type {access_type.value} not allowed"

        # Check export blocking
        if policy.export_blocked and access_type in (
            AccessType.EXPORT,
            AccessType.COPY,
            AccessType.NETWORK_TRANSFER,
        ):
            return False, "Export operations blocked"

        return True, "Access allowed"

    async def get_access_history(
        self,
        model_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[ModelWeightAccess]:
        """Get access history for model."""
        if model_id not in self._models:
            raise ModelNotRegisteredError(model_id)

        history = [a for a in self._access_logs if a.model_id == model_id]

        if start_time:
            history = [a for a in history if a.timestamp >= start_time]

        if end_time:
            history = [a for a in history if a.timestamp <= end_time]

        # Sort by timestamp descending
        history.sort(key=lambda a: a.timestamp, reverse=True)

        return history[:limit]

    async def generate_audit_report(
        self,
        model_id: str,
        period_days: int = 30,
    ) -> AuditReport:
        """Generate security audit report."""
        if model_id not in self._models:
            raise ModelNotRegisteredError(model_id)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=period_days)

        # Get access history
        history = await self.get_access_history(
            model_id, start_time, end_time, limit=10000
        )

        # Calculate statistics
        unique_accessors = set(a.accessor_identity for a in history)
        blocked_accesses = sum(1 for a in history if not a.approved)

        # Count by access type
        access_by_type: dict[str, int] = defaultdict(int)
        for access in history:
            access_by_type[access.access_type.value] += 1

        # Count by identity
        access_by_identity: dict[str, int] = defaultdict(int)
        for access in history:
            access_by_identity[access.accessor_identity] += 1

        # Get threat detections
        threat_detections = [
            d
            for d in self._detections.values()
            if d.model_id == model_id
            and d.detected_at >= start_time
            and d.detected_at <= end_time
        ]

        # Generate recommendations
        recommendations = []
        if blocked_accesses > 0:
            recommendations.append(f"Review {blocked_accesses} blocked access attempts")
        if len(threat_detections) > 0:
            recommendations.append(
                f"Investigate {len(threat_detections)} threat detections"
            )
        if len(unique_accessors) > 10:
            recommendations.append("Consider restricting access to fewer identities")

        return AuditReport(
            report_id=self._generate_id("audit"),
            model_id=model_id,
            period_start=start_time,
            period_end=end_time,
            total_accesses=len(history),
            unique_accessors=len(unique_accessors),
            blocked_accesses=blocked_accesses,
            anomalies_detected=len(threat_detections),
            policy_violations=blocked_accesses,
            threat_detections=threat_detections,
            access_by_type=dict(access_by_type),
            access_by_identity=dict(access_by_identity),
            recommendations=recommendations,
        )

    async def get_detection(
        self,
        detection_id: str,
    ) -> Optional[WeightThreatDetection]:
        """Get threat detection by ID."""
        return self._detections.get(detection_id)

    async def list_detections(
        self,
        model_id: Optional[str] = None,
        status: Optional[AlertStatus] = None,
        severity: Optional[ThreatSeverity] = None,
        limit: int = 100,
    ) -> list[WeightThreatDetection]:
        """List threat detections."""
        detections = list(self._detections.values())

        if model_id:
            detections = [d for d in detections if d.model_id == model_id]

        if status:
            detections = [d for d in detections if d.status == status]

        if severity:
            detections = [d for d in detections if d.severity == severity]

        # Sort by detected_at descending
        detections.sort(key=lambda d: d.detected_at, reverse=True)

        return detections[:limit]

    async def resolve_detection(
        self,
        detection_id: str,
        resolution: str,
        status: AlertStatus = AlertStatus.RESOLVED,
    ) -> bool:
        """Resolve a threat detection."""
        detection = self._detections.get(detection_id)
        if not detection:
            return False

        detection.status = status
        detection.resolution = resolution
        detection.resolved_at = datetime.now(timezone.utc)

        return True

    def _calculate_weight_hash(self, weight_paths: list[str]) -> str:
        """Calculate hash of model weights."""
        # In real implementation, would hash actual file contents
        # For now, hash the paths as a placeholder
        content = ":".join(sorted(weight_paths))
        return hashlib.sha256(content.encode()).hexdigest()

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID."""
        return f"{prefix}-{uuid.uuid4().hex[:12]}"


# Singleton pattern
_model_guardian: Optional[ModelWeightGuardian] = None


def get_model_guardian() -> ModelWeightGuardian:
    """Get singleton Model Weight Guardian."""
    global _model_guardian
    if _model_guardian is None:
        _model_guardian = ModelWeightGuardian()
    return _model_guardian


def reset_model_guardian() -> None:
    """Reset singleton Model Weight Guardian."""
    global _model_guardian
    _model_guardian = None
