"""
GraphRAG Security Service - Context Poisoning Defense

Implements enhanced security controls for GraphRAG to prevent and detect
context poisoning attacks per security audit finding M-3.

Features:
- Entity Signature Verification: Cryptographic signing of graph entities
- Anomaly Detection: ML-based detection of unusual graph pattern changes
- Content Validation: Sanitization and validation of code snippets
- Integrity Auditing: Periodic verification of graph integrity

MITRE ATT&CK: T1565 (Data Manipulation)

Author: Project Aura Team
Created: 2026-01-25
"""

import hashlib
import hmac
import json
import logging
import os
import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


class SignatureAlgorithm(Enum):
    """Supported signature algorithms."""

    HMAC_SHA256 = "hmac-sha256"
    HMAC_SHA512 = "hmac-sha512"


class ValidationSeverity(Enum):
    """Severity levels for validation findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ValidationFinding:
    """A validation finding from content or signature checks."""

    severity: ValidationSeverity
    category: str
    message: str
    entity_id: Optional[str] = None
    details: dict = field(default_factory=dict)


@dataclass
class EntitySignature:
    """Cryptographic signature for a graph entity."""

    entity_id: str
    signature: str
    algorithm: SignatureAlgorithm
    signed_at: datetime
    signed_fields: list[str]
    version: int = 1


@dataclass
class AnomalyScore:
    """Anomaly detection score for graph changes."""

    entity_id: str
    score: float  # 0.0 (normal) to 1.0 (highly anomalous)
    anomaly_type: str
    contributing_factors: list[str]
    baseline_deviation: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class IntegrityAuditResult:
    """Result of a graph integrity audit."""

    audit_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    entities_checked: int
    signatures_valid: int
    signatures_invalid: int
    anomalies_detected: int
    validation_findings: list[ValidationFinding]
    passed: bool


class NeptuneClient(Protocol):
    """Protocol for Neptune client."""

    def execute(self, query: str) -> list:
        """Execute Gremlin query."""
        ...


class GraphRAGSecurityService:
    """
    Security service for GraphRAG context poisoning defense.

    Implements three layers of defense:

    1. **Entity Signature Verification**
       - Signs entity content with HMAC-SHA256/512
       - Verifies signatures on read operations
       - Detects unauthorized modifications

    2. **Anomaly Detection**
       - Tracks baseline patterns for entities
       - Detects unusual changes (score spikes, mass updates)
       - Alerts on statistical outliers

    3. **Content Validation**
       - Sanitizes code snippets for injection patterns
       - Validates entity metadata
       - Blocks malicious payloads

    Usage:
        security_service = GraphRAGSecurityService(
            neptune_client=neptune,
            signing_key=os.environ["GRAPHRAG_SIGNING_KEY"]
        )

        # Sign entity on write
        signature = security_service.sign_entity(entity_data)

        # Verify on read
        is_valid = security_service.verify_entity_signature(entity_data, signature)

        # Check for anomalies
        anomaly = security_service.detect_anomaly(entity_data, changes)

        # Validate content before ingestion
        findings = security_service.validate_content(code_snippet)
    """

    # Dangerous patterns in code snippets that could indicate poisoning
    DANGEROUS_PATTERNS = [
        # Prompt injection markers
        (r"SYSTEM:\s*", ValidationSeverity.CRITICAL, "prompt_injection"),
        (r"ASSISTANT:\s*", ValidationSeverity.CRITICAL, "prompt_injection"),
        (
            r"ignore.*previous.*instructions",
            ValidationSeverity.CRITICAL,
            "prompt_injection",
        ),
        (
            r"ignore.*above.*instructions",
            ValidationSeverity.CRITICAL,
            "prompt_injection",
        ),
        (r"disregard.*instructions", ValidationSeverity.CRITICAL, "prompt_injection"),
        # Hidden instructions in comments
        (r"#\s*HIDDEN:", ValidationSeverity.HIGH, "hidden_instruction"),
        (r"//\s*INJECT:", ValidationSeverity.HIGH, "hidden_instruction"),
        (r"/\*\s*OVERRIDE", ValidationSeverity.HIGH, "hidden_instruction"),
        # Base64 encoded payloads (potential hidden content)
        (r"[A-Za-z0-9+/]{50,}={0,2}", ValidationSeverity.MEDIUM, "encoded_payload"),
        # Unusual Unicode that could hide content
        (
            r"[\u200b-\u200f\u2028-\u202f\u2060-\u206f]",
            ValidationSeverity.HIGH,
            "hidden_unicode",
        ),
        # Security score manipulation
        (
            r"security_risk_score\s*[=:]\s*0(\.\d+)?",
            ValidationSeverity.HIGH,
            "score_manipulation",
        ),
        (
            r"vulnerability_score\s*[=:]\s*0(\.\d+)?",
            ValidationSeverity.HIGH,
            "score_manipulation",
        ),
        # Embedding manipulation indicators
        (r"embedding\s*[=:]\s*\[", ValidationSeverity.MEDIUM, "embedding_manipulation"),
    ]

    # Valid entity types
    VALID_ENTITY_TYPES = {
        "class",
        "function",
        "method",
        "module",
        "variable",
        "import",
        "interface",
        "enum",
        "constant",
        "type",
        "file",
        "directory",
    }

    # Fields to include in signature
    SIGNED_FIELDS = [
        "entity_id",
        "name",
        "type",
        "file_path",
        "content_hash",
        "security_risk_score",
    ]

    def __init__(
        self,
        neptune_client: Optional[NeptuneClient] = None,
        signing_key: Optional[str] = None,
        algorithm: SignatureAlgorithm = SignatureAlgorithm.HMAC_SHA256,
        anomaly_threshold: float = 0.7,
        enable_baseline_tracking: bool = True,
    ):
        """
        Initialize GraphRAG Security Service.

        Args:
            neptune_client: Optional Neptune client for graph operations
            signing_key: Secret key for entity signatures (required for signing)
            algorithm: Signature algorithm to use
            anomaly_threshold: Threshold above which to flag anomalies (0.0-1.0)
            enable_baseline_tracking: Whether to track baselines for anomaly detection
        """
        self.neptune = neptune_client
        self._signing_key = signing_key or os.environ.get("GRAPHRAG_SIGNING_KEY")
        self.algorithm = algorithm
        self.anomaly_threshold = anomaly_threshold
        self.enable_baseline_tracking = enable_baseline_tracking

        # Baseline tracking for anomaly detection
        # Maps entity_id -> list of historical scores
        self._baselines: dict[str, list[float]] = {}
        self._baseline_window = 100  # Keep last 100 values

        # Compiled regex patterns for performance
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), severity, category)
            for pattern, severity, category in self.DANGEROUS_PATTERNS
        ]

        logger.info(
            f"GraphRAGSecurityService initialized "
            f"(algorithm={algorithm.value}, anomaly_threshold={anomaly_threshold})"
        )

    # =========================================================================
    # Entity Signature Verification
    # =========================================================================

    def sign_entity(self, entity_data: dict[str, Any]) -> EntitySignature:
        """
        Create cryptographic signature for a graph entity.

        Signs the canonical representation of specified fields to detect
        unauthorized modifications.

        Args:
            entity_data: Entity data dictionary

        Returns:
            EntitySignature with signature details

        Raises:
            ValueError: If signing key not configured or entity_id missing
        """
        if not self._signing_key:
            raise ValueError("Signing key not configured - cannot sign entity")

        entity_id = entity_data.get("entity_id") or entity_data.get("id")
        if not entity_id:
            raise ValueError("Entity must have 'entity_id' or 'id' field")

        # Build canonical representation of signed fields
        canonical = self._build_canonical_representation(entity_data)

        # Generate signature
        if self.algorithm == SignatureAlgorithm.HMAC_SHA256:
            signature = hmac.new(
                self._signing_key.encode(),
                canonical.encode(),
                hashlib.sha256,
            ).hexdigest()
        else:  # HMAC_SHA512
            signature = hmac.new(
                self._signing_key.encode(),
                canonical.encode(),
                hashlib.sha512,
            ).hexdigest()

        return EntitySignature(
            entity_id=entity_id,
            signature=signature,
            algorithm=self.algorithm,
            signed_at=datetime.now(timezone.utc),
            signed_fields=self.SIGNED_FIELDS,
        )

    def verify_entity_signature(
        self,
        entity_data: dict[str, Any],
        signature: EntitySignature,
    ) -> tuple[bool, Optional[str]]:
        """
        Verify entity signature matches current data.

        Args:
            entity_data: Current entity data
            signature: Previously generated signature

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self._signing_key:
            return False, "Signing key not configured"

        try:
            # Regenerate signature for current data
            current_signature = self.sign_entity(entity_data)

            # Compare signatures (timing-safe comparison)
            is_valid = hmac.compare_digest(
                signature.signature, current_signature.signature
            )

            if not is_valid:
                logger.warning(
                    f"Entity signature mismatch for {signature.entity_id} - "
                    f"possible tampering detected"
                )
                return False, "Signature mismatch - entity may have been modified"

            return True, None

        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False, str(e)

    def _build_canonical_representation(self, entity_data: dict[str, Any]) -> str:
        """
        Build canonical string representation of entity for signing.

        Ensures consistent ordering and formatting for deterministic signatures.
        """
        canonical_parts = []

        for field_name in sorted(self.SIGNED_FIELDS):
            value = entity_data.get(field_name, "")
            # Convert to string and normalize
            if isinstance(value, (int, float)):
                # Round floats to avoid precision issues
                value = str(round(value, 6)) if isinstance(value, float) else str(value)
            elif isinstance(value, dict):
                value = json.dumps(value, sort_keys=True)
            elif isinstance(value, list):
                value = json.dumps(sorted(str(v) for v in value))
            else:
                value = str(value) if value else ""

            canonical_parts.append(f"{field_name}={value}")

        return "|".join(canonical_parts)

    # =========================================================================
    # Anomaly Detection
    # =========================================================================

    def detect_anomaly(
        self,
        entity_data: dict[str, Any],
        changes: Optional[dict[str, Any]] = None,
    ) -> AnomalyScore:
        """
        Detect anomalies in entity data or changes.

        Uses statistical analysis to identify unusual patterns:
        - Score changes that deviate significantly from baseline
        - Mass updates affecting many entities
        - Unusual modification patterns

        Args:
            entity_data: Current entity data
            changes: Optional dict of field changes {field: (old_value, new_value)}

        Returns:
            AnomalyScore indicating anomaly level
        """
        entity_id = entity_data.get("entity_id") or entity_data.get("id", "unknown")
        contributing_factors = []
        anomaly_scores = []

        # Check security score changes
        if changes and "security_risk_score" in changes:
            old_score, new_score = changes["security_risk_score"]
            score_delta = abs(new_score - old_score) if old_score is not None else 0

            # Large score drops are suspicious (attacker lowering risk scores)
            if old_score is not None and new_score < old_score:
                score_drop = old_score - new_score
                if score_drop > 0.5:
                    anomaly_scores.append(0.9)
                    contributing_factors.append(
                        f"Large security score drop: {old_score:.2f} -> {new_score:.2f}"
                    )
                elif score_drop > 0.3:
                    anomaly_scores.append(0.7)
                    contributing_factors.append(
                        f"Moderate security score drop: {old_score:.2f} -> {new_score:.2f}"
                    )

            # Any significant score change warrants attention
            if score_delta > 0.3:
                anomaly_scores.append(0.5)
                contributing_factors.append(
                    f"Significant score change: {score_delta:.2f}"
                )

        # Check against baseline if enabled
        baseline_deviation = 0.0
        if self.enable_baseline_tracking and entity_id in self._baselines:
            baseline = self._baselines[entity_id]
            if len(baseline) >= 5:  # Need sufficient history
                current_score = entity_data.get("security_risk_score", 0)
                mean = statistics.mean(baseline)
                stdev = statistics.stdev(baseline) if len(baseline) > 1 else 0.1

                if stdev > 0:
                    z_score = abs(current_score - mean) / stdev
                    baseline_deviation = z_score

                    if z_score > 3:  # 3 standard deviations
                        anomaly_scores.append(0.85)
                        contributing_factors.append(
                            f"Score deviates {z_score:.1f} std from baseline"
                        )
                    elif z_score > 2:
                        anomaly_scores.append(0.6)
                        contributing_factors.append(
                            f"Score deviates {z_score:.1f} std from baseline"
                        )

        # Check for suspicious content patterns
        content = entity_data.get("content", "") or entity_data.get("code", "")
        if content:
            content_findings = self.validate_content(content)
            critical_findings = [
                f for f in content_findings if f.severity == ValidationSeverity.CRITICAL
            ]
            high_findings = [
                f for f in content_findings if f.severity == ValidationSeverity.HIGH
            ]
            if critical_findings:
                anomaly_scores.append(0.95)
                contributing_factors.append(
                    f"Critical content patterns detected: {len(critical_findings)}"
                )
            elif high_findings:
                anomaly_scores.append(0.85)
                contributing_factors.append(
                    f"High-severity content patterns detected: {len(high_findings)}"
                )

        # Calculate final anomaly score (max of all scores, or 0 if none)
        final_score = max(anomaly_scores) if anomaly_scores else 0.0

        # Determine anomaly type
        if final_score >= 0.9:
            anomaly_type = "critical_manipulation"
        elif final_score >= 0.7:
            anomaly_type = "suspicious_change"
        elif final_score >= 0.5:
            anomaly_type = "unusual_pattern"
        else:
            anomaly_type = "normal"

        # Update baseline
        if self.enable_baseline_tracking:
            current_score = entity_data.get("security_risk_score", 0)
            if entity_id not in self._baselines:
                self._baselines[entity_id] = []
            self._baselines[entity_id].append(current_score)
            # Keep only recent values
            if len(self._baselines[entity_id]) > self._baseline_window:
                self._baselines[entity_id] = self._baselines[entity_id][
                    -self._baseline_window :
                ]

        return AnomalyScore(
            entity_id=entity_id,
            score=final_score,
            anomaly_type=anomaly_type,
            contributing_factors=contributing_factors,
            baseline_deviation=baseline_deviation,
        )

    def is_anomalous(self, entity_data: dict[str, Any]) -> bool:
        """Quick check if entity is anomalous based on threshold."""
        anomaly = self.detect_anomaly(entity_data)
        return anomaly.score >= self.anomaly_threshold

    # =========================================================================
    # Content Validation
    # =========================================================================

    def validate_content(self, content: str) -> list[ValidationFinding]:
        """
        Validate content for potential poisoning patterns.

        Checks for:
        - Prompt injection markers
        - Hidden instructions in comments
        - Encoded payloads
        - Score manipulation patterns
        - Embedding manipulation indicators

        Args:
            content: Code snippet or text to validate

        Returns:
            List of ValidationFinding for detected issues
        """
        findings = []

        if not content:
            return findings

        for pattern, severity, category in self._compiled_patterns:
            matches = pattern.findall(content)
            if matches:
                findings.append(
                    ValidationFinding(
                        severity=severity,
                        category=category,
                        message=f"Detected {category} pattern: {len(matches)} occurrence(s)",
                        details={
                            "pattern": pattern.pattern,
                            "match_count": len(matches),
                        },
                    )
                )

        return findings

    def validate_entity(self, entity_data: dict[str, Any]) -> list[ValidationFinding]:
        """
        Validate complete entity data.

        Performs comprehensive validation including:
        - Entity type validation
        - Content validation
        - Metadata validation
        - Score range validation

        Args:
            entity_data: Entity data dictionary

        Returns:
            List of ValidationFinding for detected issues
        """
        findings = []

        # Validate entity type
        entity_type = entity_data.get("type", "").lower()
        if entity_type and entity_type not in self.VALID_ENTITY_TYPES:
            findings.append(
                ValidationFinding(
                    severity=ValidationSeverity.MEDIUM,
                    category="invalid_type",
                    message=f"Unknown entity type: {entity_type}",
                    entity_id=entity_data.get("entity_id"),
                )
            )

        # Validate content
        content = entity_data.get("content", "") or entity_data.get("code", "")
        if content:
            findings.extend(self.validate_content(content))

        # Validate security score range
        score = entity_data.get("security_risk_score")
        if score is not None:
            if not (0.0 <= score <= 1.0):
                findings.append(
                    ValidationFinding(
                        severity=ValidationSeverity.HIGH,
                        category="invalid_score",
                        message=f"Security score out of range: {score}",
                        entity_id=entity_data.get("entity_id"),
                    )
                )

        # Validate file path (no path traversal)
        file_path = entity_data.get("file_path", "")
        if file_path:
            if ".." in file_path or file_path.startswith("/"):
                findings.append(
                    ValidationFinding(
                        severity=ValidationSeverity.HIGH,
                        category="path_traversal",
                        message=f"Suspicious file path: {file_path}",
                        entity_id=entity_data.get("entity_id"),
                    )
                )

        return findings

    def sanitize_content(self, content: str) -> str:
        """
        Sanitize content by removing or neutralizing dangerous patterns.

        Args:
            content: Raw content to sanitize

        Returns:
            Sanitized content
        """
        if not content:
            return content

        sanitized = content

        # Remove hidden Unicode characters
        sanitized = re.sub(r"[\u200b-\u200f\u2028-\u202f\u2060-\u206f]", "", sanitized)

        # Neutralize prompt injection markers (prefix with warning)
        sanitized = re.sub(
            r"(SYSTEM:|ASSISTANT:)",
            r"[NEUTRALIZED_MARKER]\1",
            sanitized,
            flags=re.IGNORECASE,
        )

        # Neutralize hidden instruction markers
        sanitized = re.sub(
            r"(#\s*HIDDEN:|//\s*INJECT:|/\*\s*OVERRIDE)",
            r"[BLOCKED]\1",
            sanitized,
            flags=re.IGNORECASE,
        )

        return sanitized

    # =========================================================================
    # Integrity Auditing
    # =========================================================================

    async def audit_graph_integrity(
        self,
        entity_ids: Optional[list[str]] = None,
        batch_size: int = 100,
    ) -> IntegrityAuditResult:
        """
        Perform integrity audit on graph entities.

        Checks signatures and validates content for all or specified entities.

        Args:
            entity_ids: Optional list of entity IDs to audit (all if None)
            batch_size: Number of entities to process per batch

        Returns:
            IntegrityAuditResult with audit findings
        """
        import uuid

        audit_id = f"audit-{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc)

        entities_checked = 0
        signatures_valid = 0
        signatures_invalid = 0
        anomalies_detected = 0
        all_findings: list[ValidationFinding] = []

        logger.info(f"Starting graph integrity audit {audit_id}")

        try:
            # Get entities to audit
            if self.neptune:
                if entity_ids:
                    query = f"g.V().hasId(within({','.join(repr(id) for id in entity_ids)})).valueMap(true)"
                else:
                    query = f"g.V().limit({batch_size}).valueMap(true)"

                # Note: In production, this would paginate through all entities
                entities = self.neptune.execute(query)
            else:
                # Mock mode - no entities to audit
                entities = []

            for entity in entities:
                entities_checked += 1

                # Validate entity
                findings = self.validate_entity(entity)
                all_findings.extend(findings)

                # Check for anomalies
                anomaly = self.detect_anomaly(entity)
                if anomaly.score >= self.anomaly_threshold:
                    anomalies_detected += 1
                    all_findings.append(
                        ValidationFinding(
                            severity=ValidationSeverity.HIGH,
                            category="anomaly",
                            message=f"Anomaly detected: {anomaly.anomaly_type}",
                            entity_id=entity.get("entity_id"),
                            details={
                                "score": anomaly.score,
                                "factors": anomaly.contributing_factors,
                            },
                        )
                    )

                # Verify signature if stored
                stored_signature = entity.get("_signature")
                if stored_signature:
                    sig = EntitySignature(
                        entity_id=entity.get("entity_id", ""),
                        signature=stored_signature,
                        algorithm=self.algorithm,
                        signed_at=datetime.now(timezone.utc),
                        signed_fields=self.SIGNED_FIELDS,
                    )
                    is_valid, error = self.verify_entity_signature(entity, sig)
                    if is_valid:
                        signatures_valid += 1
                    else:
                        signatures_invalid += 1
                        all_findings.append(
                            ValidationFinding(
                                severity=ValidationSeverity.CRITICAL,
                                category="signature_invalid",
                                message=f"Invalid signature: {error}",
                                entity_id=entity.get("entity_id"),
                            )
                        )

        except Exception as e:
            logger.error(f"Integrity audit {audit_id} failed: {e}")
            all_findings.append(
                ValidationFinding(
                    severity=ValidationSeverity.CRITICAL,
                    category="audit_error",
                    message=f"Audit failed: {str(e)}",
                )
            )

        completed_at = datetime.now(timezone.utc)

        # Determine if audit passed
        critical_findings = [
            f for f in all_findings if f.severity == ValidationSeverity.CRITICAL
        ]
        passed = len(critical_findings) == 0 and signatures_invalid == 0

        result = IntegrityAuditResult(
            audit_id=audit_id,
            started_at=started_at,
            completed_at=completed_at,
            entities_checked=entities_checked,
            signatures_valid=signatures_valid,
            signatures_invalid=signatures_invalid,
            anomalies_detected=anomalies_detected,
            validation_findings=all_findings,
            passed=passed,
        )

        logger.info(
            f"Integrity audit {audit_id} completed: "
            f"checked={entities_checked}, valid_sigs={signatures_valid}, "
            f"invalid_sigs={signatures_invalid}, anomalies={anomalies_detected}, "
            f"passed={passed}"
        )

        return result


def create_graphrag_security_service(
    neptune_client: Optional[NeptuneClient] = None,
    signing_key: Optional[str] = None,
) -> GraphRAGSecurityService:
    """
    Factory function to create GraphRAGSecurityService.

    Args:
        neptune_client: Optional Neptune client
        signing_key: Optional signing key (defaults to env var)

    Returns:
        Configured GraphRAGSecurityService
    """
    return GraphRAGSecurityService(
        neptune_client=neptune_client,
        signing_key=signing_key or os.environ.get("GRAPHRAG_SIGNING_KEY"),
    )
