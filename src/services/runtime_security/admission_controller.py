"""
Project Aura - Kubernetes Admission Controller Service

Validates Pod, Deployment, and StatefulSet resources against security policies
including SBOM attestation, image signatures, and CVE thresholds.

Based on ADR-077: Cloud Runtime Security Integration
"""

import fnmatch
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .config import RuntimeSecurityConfig, get_runtime_security_config
from .contracts import (
    AdmissionDecision,
    AdmissionDecisionType,
    AdmissionPolicy,
    AdmissionRequest,
    ContainerImage,
    PolicyMode,
    PolicyType,
    PolicyViolation,
    Severity,
)
from .metrics import get_runtime_security_metrics

logger = logging.getLogger(__name__)


class AdmissionController:
    """
    Kubernetes ValidatingWebhook implementation for security policy enforcement.

    Responsibilities:
    - Validate Pod/Deployment/StatefulSet resources
    - Enforce SBOM attestation requirements
    - Verify container image signatures (Sigstore/cosign)
    - Check CVE thresholds
    - Enforce registry allowlists
    - Apply custom OPA/Rego policies
    """

    def __init__(self, config: Optional[RuntimeSecurityConfig] = None):
        """Initialize admission controller with configuration."""
        self._config = config or get_runtime_security_config()
        self._metrics = get_runtime_security_metrics()
        self._policies: dict[str, AdmissionPolicy] = {}
        self._image_cache: dict[str, ContainerImage] = {}
        self._sbom_cache: dict[str, dict[str, Any]] = {}

        # Initialize default policies
        self._init_default_policies()

    def _init_default_policies(self) -> None:
        """Initialize default admission policies."""
        cfg = self._config.admission

        # SBOM Required Policy
        if cfg.require_sbom:
            self.add_policy(
                AdmissionPolicy(
                    policy_id="sbom-required",
                    name="SBOM Required",
                    policy_type=PolicyType.SBOM_REQUIRED,
                    mode=cfg.default_mode,
                    enabled=True,
                    description="Container images must have valid SBOM attestation",
                    severity_threshold=Severity.HIGH,
                )
            )

        # Image Signed Policy
        if cfg.require_signed_images:
            self.add_policy(
                AdmissionPolicy(
                    policy_id="image-signed",
                    name="Image Signature Required",
                    policy_type=PolicyType.IMAGE_SIGNED,
                    mode=cfg.default_mode,
                    enabled=True,
                    description="Container images must be signed with valid signature",
                    severity_threshold=Severity.HIGH,
                )
            )

        # CVE Threshold Policy
        self.add_policy(
            AdmissionPolicy(
                policy_id="cve-threshold",
                name="CVE Threshold",
                policy_type=PolicyType.CVE_THRESHOLD,
                mode=cfg.default_mode,
                enabled=True,
                description=f"Max {cfg.max_critical_cves} CRITICAL, {cfg.max_high_cves} HIGH CVEs",
                severity_threshold=cfg.severity_threshold,
            )
        )

        # Registry Allowlist Policy
        if cfg.allowed_registries:
            self.add_policy(
                AdmissionPolicy(
                    policy_id="registry-allowlist",
                    name="Registry Allowlist",
                    policy_type=PolicyType.REGISTRY_ALLOWLIST,
                    mode=cfg.default_mode,
                    enabled=True,
                    description="Images must be from approved registries",
                    severity_threshold=Severity.HIGH,
                )
            )

        # Resource Limits Policy
        self.add_policy(
            AdmissionPolicy(
                policy_id="resource-limits",
                name="Resource Limits Required",
                policy_type=PolicyType.RESOURCE_LIMITS,
                mode=PolicyMode.AUDIT,  # Start in audit mode
                enabled=True,
                description="Containers must specify resource limits",
                severity_threshold=Severity.MEDIUM,
            )
        )

    def add_policy(self, policy: AdmissionPolicy) -> None:
        """Add or update an admission policy."""
        self._policies[policy.policy_id] = policy
        logger.info(f"Added admission policy: {policy.policy_id}")

    def remove_policy(self, policy_id: str) -> bool:
        """Remove an admission policy."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            logger.info(f"Removed admission policy: {policy_id}")
            return True
        return False

    def get_policy(self, policy_id: str) -> Optional[AdmissionPolicy]:
        """Get a policy by ID."""
        return self._policies.get(policy_id)

    def list_policies(self) -> list[AdmissionPolicy]:
        """List all configured policies."""
        return list(self._policies.values())

    def validate(self, request: AdmissionRequest) -> AdmissionDecision:
        """
        Validate a Kubernetes admission request.

        Args:
            request: The admission request to validate

        Returns:
            AdmissionDecision with allow/deny/warn decision and any violations
        """
        start_time = datetime.now(timezone.utc)
        decision_id = f"adm-{uuid.uuid4().hex[:12]}"

        try:
            # Check if namespace is exempt
            if self._is_exempt_namespace(request.namespace):
                return self._create_decision(
                    decision_id=decision_id,
                    request=request,
                    decision_type=AdmissionDecisionType.ALLOW,
                    violations=[],
                    start_time=start_time,
                )

            # Collect all violations
            violations: list[PolicyViolation] = []
            images_checked: list[str] = []

            # Check each image in the request
            for image_ref in request.images:
                images_checked.append(image_ref)
                image_violations = self._validate_image(image_ref, request)
                violations.extend(image_violations)

            # Check container resource limits
            resource_violations = self._validate_resource_limits(request)
            violations.extend(resource_violations)

            # Determine final decision
            decision_type = self._determine_decision(violations)

            decision = self._create_decision(
                decision_id=decision_id,
                request=request,
                decision_type=decision_type,
                violations=violations,
                images_checked=images_checked,
                start_time=start_time,
            )

            # Record metrics
            self._record_decision_metrics(decision)

            return decision

        except Exception as e:
            logger.error(f"Error during admission validation: {e}")
            # On error, use failure policy from config
            if self._config.admission.failure_policy == "Fail":
                return self._create_decision(
                    decision_id=decision_id,
                    request=request,
                    decision_type=AdmissionDecisionType.DENY,
                    violations=[
                        PolicyViolation(
                            policy_id="error",
                            policy_type=PolicyType.CUSTOM,
                            description=f"Admission validation error: {str(e)}",
                            severity=Severity.HIGH,
                        )
                    ],
                    start_time=start_time,
                )
            else:
                return self._create_decision(
                    decision_id=decision_id,
                    request=request,
                    decision_type=AdmissionDecisionType.WARN,
                    violations=[],
                    start_time=start_time,
                )

    def _is_exempt_namespace(self, namespace: str) -> bool:
        """Check if namespace is exempt from validation."""
        return namespace in self._config.admission.exempt_namespaces

    def _validate_image(
        self, image_ref: str, request: AdmissionRequest
    ) -> list[PolicyViolation]:
        """Validate a single container image."""
        violations: list[PolicyViolation] = []

        # Parse image reference
        image = self._parse_image_reference(image_ref)

        # Check registry allowlist
        registry_violations = self._check_registry_allowlist(image, request.namespace)
        violations.extend(registry_violations)

        # Check SBOM attestation
        sbom_violations = self._check_sbom_attestation(image, request.namespace)
        violations.extend(sbom_violations)

        # Check image signature
        signature_violations = self._check_image_signature(image, request.namespace)
        violations.extend(signature_violations)

        # Check CVE thresholds
        cve_violations = self._check_cve_thresholds(image, request.namespace)
        violations.extend(cve_violations)

        return violations

    def _parse_image_reference(self, image_ref: str) -> ContainerImage:
        """Parse an image reference into a ContainerImage object."""
        # Check cache first
        if image_ref in self._image_cache:
            return self._image_cache[image_ref]

        # Parse the image reference
        # Format: registry/repo:tag@sha256:digest
        digest = ""
        tag = "latest"
        repository = image_ref

        if "@" in image_ref:
            repository, digest = image_ref.rsplit("@", 1)

        if ":" in repository and not repository.startswith("["):
            # Handle port numbers in registry (e.g., localhost:5000/image)
            parts = repository.rsplit(":", 1)
            if "/" in parts[-1] or parts[-1].isdigit():
                # This is a port number, not a tag
                pass
            else:
                repository = parts[0]
                tag = parts[1]

        # Generate digest if not provided
        if not digest:
            digest = f"sha256:{hashlib.sha256(image_ref.encode()).hexdigest()}"

        image = ContainerImage(
            digest=digest,
            repository=repository,
            tag=tag,
            signed=False,  # Will be verified
            signature_verified=False,
        )

        self._image_cache[image_ref] = image
        return image

    def _check_registry_allowlist(
        self, image: ContainerImage, namespace: str
    ) -> list[PolicyViolation]:
        """Check if image is from an allowed registry."""
        policy = self._policies.get("registry-allowlist")
        if not policy or not policy.enabled:
            return []

        if not policy.applies_to_namespace(namespace):
            return []

        allowed = self._config.admission.allowed_registries
        blocked = self._config.admission.blocked_registries

        # Check if blocked first
        for pattern in blocked:
            if fnmatch.fnmatch(image.repository, pattern):
                return [
                    PolicyViolation(
                        policy_id=policy.policy_id,
                        policy_type=policy.policy_type,
                        description=f"Image from blocked registry: {image.repository}",
                        severity=Severity.CRITICAL,
                        remediation="Use an image from an approved registry",
                    )
                ]

        # Check if allowed
        for pattern in allowed:
            if fnmatch.fnmatch(image.repository, pattern):
                return []

        # Not in allowlist
        return [
            PolicyViolation(
                policy_id=policy.policy_id,
                policy_type=policy.policy_type,
                description=f"Image not from allowed registry: {image.repository}",
                severity=Severity.HIGH,
                expected_value=", ".join(allowed),
                actual_value=image.repository,
                remediation="Use an image from an approved registry",
            )
        ]

    def _check_sbom_attestation(
        self, image: ContainerImage, namespace: str
    ) -> list[PolicyViolation]:
        """Check if image has valid SBOM attestation."""
        policy = self._policies.get("sbom-required")
        if not policy or not policy.enabled:
            return []

        if not policy.applies_to_namespace(namespace):
            return []

        # In mock mode, simulate SBOM lookup
        if self._config.storage.use_mock_storage:
            # Simulate some images having SBOMs
            has_sbom = "aura" in image.repository.lower() or "prod" in image.tag
            if has_sbom:
                image.sbom_id = f"sbom-{image.digest[:16]}"
                return []

        # Check SBOM cache
        if image.digest in self._sbom_cache:
            image.sbom_id = self._sbom_cache[image.digest].get("sbom_id")
            return []

        # Would query SBOM service here
        # For now, return violation if no SBOM found
        if not image.sbom_id:
            return [
                PolicyViolation(
                    policy_id=policy.policy_id,
                    policy_type=policy.policy_type,
                    description=f"No SBOM attestation found for image: {image.full_reference}",
                    severity=Severity.HIGH,
                    remediation="Generate and sign an SBOM for this image using the supply chain service",
                )
            ]

        return []

    def _check_image_signature(
        self, image: ContainerImage, namespace: str
    ) -> list[PolicyViolation]:
        """Check if image has valid signature."""
        policy = self._policies.get("image-signed")
        if not policy or not policy.enabled:
            return []

        if not policy.applies_to_namespace(namespace):
            return []

        # In mock mode, simulate signature verification
        if self._config.storage.use_mock_storage:
            # Simulate some images being signed
            is_signed = "aura" in image.repository.lower() or "signed" in image.tag
            if is_signed:
                image.signed = True
                image.signature_verified = True
                return []

        # Would verify signature with cosign/Sigstore here
        if not image.signature_verified:
            return [
                PolicyViolation(
                    policy_id=policy.policy_id,
                    policy_type=policy.policy_type,
                    description=f"Image signature not verified: {image.full_reference}",
                    severity=Severity.HIGH,
                    remediation="Sign the image using Sigstore cosign",
                )
            ]

        return []

    def _check_cve_thresholds(
        self, image: ContainerImage, namespace: str
    ) -> list[PolicyViolation]:
        """Check if image CVE counts exceed thresholds."""
        policy = self._policies.get("cve-threshold")
        if not policy or not policy.enabled:
            return []

        if not policy.applies_to_namespace(namespace):
            return []

        # In mock mode, simulate CVE data
        if self._config.storage.use_mock_storage:
            # Simulate vulnerability counts
            if "vulnerable" in image.tag:
                image.vulnerabilities = {"CRITICAL": 5, "HIGH": 10, "MEDIUM": 20}
            else:
                image.vulnerabilities = {"CRITICAL": 0, "HIGH": 2, "MEDIUM": 5}

        critical_count = image.vulnerabilities.get("CRITICAL", 0)
        high_count = image.vulnerabilities.get("HIGH", 0)
        max_critical = self._config.admission.max_critical_cves
        max_high = self._config.admission.max_high_cves

        violations: list[PolicyViolation] = []

        if critical_count > max_critical:
            violations.append(
                PolicyViolation(
                    policy_id=policy.policy_id,
                    policy_type=policy.policy_type,
                    description=f"Image has {critical_count} CRITICAL CVEs (max: {max_critical})",
                    severity=Severity.CRITICAL,
                    expected_value=str(max_critical),
                    actual_value=str(critical_count),
                    remediation="Update base image and dependencies to fix critical vulnerabilities",
                )
            )

        if high_count > max_high:
            violations.append(
                PolicyViolation(
                    policy_id=policy.policy_id,
                    policy_type=policy.policy_type,
                    description=f"Image has {high_count} HIGH CVEs (max: {max_high})",
                    severity=Severity.HIGH,
                    expected_value=str(max_high),
                    actual_value=str(high_count),
                    remediation="Update dependencies to fix high severity vulnerabilities",
                )
            )

        return violations

    def _validate_resource_limits(
        self, request: AdmissionRequest
    ) -> list[PolicyViolation]:
        """Validate that containers have resource limits."""
        policy = self._policies.get("resource-limits")
        if not policy or not policy.enabled:
            return []

        if not policy.applies_to_namespace(request.namespace):
            return []

        violations: list[PolicyViolation] = []

        for container in request.containers:
            container_name = container.get("name", "unknown")
            resources = container.get("resources", {})
            limits = resources.get("limits", {})

            if not limits.get("memory"):
                violations.append(
                    PolicyViolation(
                        policy_id=policy.policy_id,
                        policy_type=policy.policy_type,
                        description=f"Container '{container_name}' missing memory limit",
                        severity=Severity.MEDIUM,
                        resource_path=f"spec.containers[name={container_name}].resources.limits.memory",
                        remediation="Add memory limit to container spec",
                    )
                )

            if not limits.get("cpu"):
                violations.append(
                    PolicyViolation(
                        policy_id=policy.policy_id,
                        policy_type=policy.policy_type,
                        description=f"Container '{container_name}' missing CPU limit",
                        severity=Severity.LOW,
                        resource_path=f"spec.containers[name={container_name}].resources.limits.cpu",
                        remediation="Add CPU limit to container spec",
                    )
                )

        return violations

    def _determine_decision(
        self, violations: list[PolicyViolation]
    ) -> AdmissionDecisionType:
        """Determine the admission decision based on violations and policy modes."""
        if not violations:
            return AdmissionDecisionType.ALLOW

        # Check if any enforcing policy has violations
        has_enforced_violation = False
        has_warning = False

        for violation in violations:
            policy = self._policies.get(violation.policy_id)
            if policy:
                if policy.mode == PolicyMode.ENFORCE:
                    # Check if violation severity meets threshold
                    if violation.severity >= policy.severity_threshold:
                        has_enforced_violation = True
                elif policy.mode == PolicyMode.AUDIT:
                    has_warning = True
            else:
                # Unknown policy, treat as enforced
                has_enforced_violation = True

        if has_enforced_violation:
            return AdmissionDecisionType.DENY
        elif has_warning:
            return AdmissionDecisionType.WARN
        else:
            return AdmissionDecisionType.ALLOW

    def _create_decision(
        self,
        decision_id: str,
        request: AdmissionRequest,
        decision_type: AdmissionDecisionType,
        violations: list[PolicyViolation],
        images_checked: list[str] | None = None,
        start_time: datetime | None = None,
    ) -> AdmissionDecision:
        """Create an admission decision."""
        now = datetime.now(timezone.utc)
        latency_ms = None
        if start_time:
            latency_ms = (now - start_time).total_seconds() * 1000

        return AdmissionDecision(
            decision_id=decision_id,
            request_uid=request.uid,
            cluster=self._config.cluster_name,
            namespace=request.namespace,
            resource_kind=request.kind,
            resource_name=request.name,
            decision=decision_type,
            violations=violations,
            images_checked=images_checked or [],
            timestamp=now,
            latency_ms=latency_ms,
        )

    def _record_decision_metrics(self, decision: AdmissionDecision) -> None:
        """Record metrics for an admission decision."""
        self._metrics.record_admission_decision(
            decision=decision.decision.value,
            cluster=decision.cluster,
            namespace=decision.namespace,
            resource_kind=decision.resource_kind,
        )

        if decision.latency_ms is not None:
            self._metrics.record_admission_latency(
                latency_ms=decision.latency_ms,
                cluster=decision.cluster,
            )

        for violation in decision.violations:
            self._metrics.record_policy_violation(
                policy_type=violation.policy_type.value,
                severity=violation.severity.name,
                cluster=decision.cluster,
            )

    def to_admission_response(self, decision: AdmissionDecision) -> dict[str, Any]:
        """Convert decision to Kubernetes AdmissionReview response format."""
        response: dict[str, Any] = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": decision.request_uid,
                "allowed": decision.allowed,
            },
        }

        if not decision.allowed or decision.decision == AdmissionDecisionType.WARN:
            # Add status with violation details
            messages = [v.description for v in decision.violations]
            response["response"]["status"] = {
                "code": 403 if not decision.allowed else 200,
                "message": (
                    "; ".join(messages) if messages else "Policy violations detected"
                ),
            }

        if decision.decision == AdmissionDecisionType.WARN:
            # Add warnings
            response["response"]["warnings"] = [
                v.description for v in decision.violations
            ]

        return response


# Singleton instance
_controller_instance: Optional[AdmissionController] = None


def get_admission_controller() -> AdmissionController:
    """Get singleton admission controller instance."""
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = AdmissionController()
    return _controller_instance


def reset_admission_controller() -> None:
    """Reset admission controller singleton (for testing)."""
    global _controller_instance
    _controller_instance = None
