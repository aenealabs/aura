"""
Network Egress Validation for Air-Gapped Deployments.

Validates that the deployment environment properly blocks external
network access as required for air-gapped/classified environments.
"""

import asyncio
import logging
import os
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class EgressViolationType(str, Enum):
    """Types of egress violations detected."""

    DNS_RESOLUTION = "dns_resolution"
    TCP_CONNECTION = "tcp_connection"
    HTTP_REQUEST = "http_request"
    HTTPS_REQUEST = "https_request"
    EXTERNAL_API = "external_api"


@dataclass
class EgressViolation:
    """Record of an egress violation attempt."""

    violation_type: EgressViolationType
    destination: str
    port: Optional[int] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    blocked: bool = True
    details: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/reporting."""
        return {
            "type": self.violation_type.value,
            "destination": self.destination,
            "port": self.port,
            "timestamp": self.timestamp.isoformat(),
            "blocked": self.blocked,
            "details": self.details,
        }


@dataclass
class EgressValidationResult:
    """Result of egress validation tests."""

    is_air_gapped: bool
    violations: list[EgressViolation] = field(default_factory=list)
    tests_passed: int = 0
    tests_failed: int = 0
    validation_time: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def is_compliant(self) -> bool:
        """Check if all egress is properly blocked."""
        return self.is_air_gapped and len(self.violations) == 0

    def to_dict(self) -> dict:
        """Convert to dictionary for reporting."""
        return {
            "is_air_gapped": self.is_air_gapped,
            "is_compliant": self.is_compliant,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "violations": [v.to_dict() for v in self.violations],
            "validation_time": self.validation_time.isoformat(),
        }


# External endpoints to test (should all be blocked in air-gap)
TEST_ENDPOINTS = [
    ("google.com", 443),
    ("api.openai.com", 443),
    ("api.anthropic.com", 443),
    ("pypi.org", 443),
    ("registry.npmjs.org", 443),
    ("github.com", 443),
    ("aws.amazon.com", 443),
]

# Internal endpoints that should be reachable
INTERNAL_ENDPOINTS = [
    "localhost",
    "127.0.0.1",
    "kubernetes.default.svc",
]


class EgressValidator:
    """
    Validates network egress blocking for air-gapped deployments.

    Performs a series of tests to verify that external network
    access is properly blocked, as required for classified and
    regulated environments.
    """

    def __init__(
        self,
        timeout_seconds: float = 5.0,
        test_endpoints: Optional[list[tuple[str, int]]] = None,
        allow_internal: bool = True,
    ):
        """
        Initialize egress validator.

        Args:
            timeout_seconds: Timeout for connection attempts
            test_endpoints: External endpoints to test (default: common APIs)
            allow_internal: Allow connections to internal/localhost endpoints
        """
        self._timeout = timeout_seconds
        self._test_endpoints = test_endpoints or TEST_ENDPOINTS
        self._allow_internal = allow_internal
        self._violations: list[EgressViolation] = []

    def _is_air_gap_mode(self) -> bool:
        """Check if air-gap mode is configured."""
        mode = os.getenv("AURA_DEPLOYMENT_MODE", "").lower()
        return mode == "air_gapped" or mode == "airgap"

    def _test_dns_resolution(self, hostname: str) -> Optional[EgressViolation]:
        """Test if DNS resolution works for external hostname."""
        try:
            socket.setdefaulttimeout(self._timeout)
            ip_addresses = socket.gethostbyname_ex(hostname)

            # DNS resolution succeeded - this is a violation in air-gap mode
            return EgressViolation(
                violation_type=EgressViolationType.DNS_RESOLUTION,
                destination=hostname,
                blocked=False,
                details=f"Resolved to: {ip_addresses[2]}",
            )
        except socket.gaierror:
            # DNS resolution failed - expected in air-gap mode
            logger.debug("DNS resolution blocked for %s (expected)", hostname)
            return None
        except socket.timeout:
            # Timeout - effectively blocked
            return None

    def _test_tcp_connection(
        self, hostname: str, port: int
    ) -> Optional[EgressViolation]:
        """Test if TCP connection can be established."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._timeout)

            result = sock.connect_ex((hostname, port))
            sock.close()

            if result == 0:
                # Connection succeeded - violation in air-gap mode
                return EgressViolation(
                    violation_type=EgressViolationType.TCP_CONNECTION,
                    destination=hostname,
                    port=port,
                    blocked=False,
                    details="TCP connection established",
                )
            return None

        except (socket.gaierror, socket.timeout, OSError):
            # Connection failed - expected in air-gap mode
            return None

    async def _test_http_request(self, url: str) -> Optional[EgressViolation]:
        """Test if HTTP/HTTPS request can be made."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, follow_redirects=False)

                # Request succeeded - violation in air-gap mode
                return EgressViolation(
                    violation_type=(
                        EgressViolationType.HTTPS_REQUEST
                        if url.startswith("https")
                        else EgressViolationType.HTTP_REQUEST
                    ),
                    destination=url,
                    blocked=False,
                    details=f"HTTP {response.status_code}",
                )

        except ImportError:
            logger.debug("httpx not available, skipping HTTP test")
            return None
        except Exception:
            # Request failed - expected in air-gap mode
            return None

    def validate_sync(self) -> EgressValidationResult:
        """
        Synchronously validate egress blocking.

        Returns:
            EgressValidationResult with test results
        """
        self._violations = []
        tests_passed = 0
        tests_failed = 0

        is_air_gap = self._is_air_gap_mode()

        if not is_air_gap:
            logger.info("Not in air-gap mode, skipping egress validation")
            return EgressValidationResult(
                is_air_gapped=False,
                tests_passed=0,
                tests_failed=0,
            )

        logger.info("Validating air-gap network isolation...")

        # Test each external endpoint
        for hostname, port in self._test_endpoints:
            # Test DNS resolution
            violation = self._test_dns_resolution(hostname)
            if violation:
                self._violations.append(violation)
                tests_failed += 1
                logger.warning(
                    "Egress violation: DNS resolution for %s succeeded",
                    hostname,
                )
            else:
                tests_passed += 1

            # Test TCP connection
            violation = self._test_tcp_connection(hostname, port)
            if violation:
                self._violations.append(violation)
                tests_failed += 1
                logger.warning(
                    "Egress violation: TCP connection to %s:%d succeeded",
                    hostname,
                    port,
                )
            else:
                tests_passed += 1

        result = EgressValidationResult(
            is_air_gapped=is_air_gap,
            violations=self._violations,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
        )

        if result.is_compliant:
            logger.info(
                "Air-gap validation passed: %d tests passed",
                tests_passed,
            )
        else:
            logger.error(
                "Air-gap validation FAILED: %d violations detected",
                len(self._violations),
            )

        return result

    async def validate_async(self) -> EgressValidationResult:
        """
        Asynchronously validate egress blocking.

        Runs tests in parallel for faster validation.

        Returns:
            EgressValidationResult with test results
        """
        self._violations = []
        is_air_gap = self._is_air_gap_mode()

        if not is_air_gap:
            return EgressValidationResult(is_air_gapped=False)

        logger.info("Validating air-gap network isolation (async)...")

        # Run DNS and TCP tests synchronously (they're quick)
        for hostname, port in self._test_endpoints:
            violation = self._test_dns_resolution(hostname)
            if violation:
                self._violations.append(violation)

            violation = self._test_tcp_connection(hostname, port)
            if violation:
                self._violations.append(violation)

        # Run HTTP tests in parallel
        http_tasks = [
            self._test_http_request(f"https://{hostname}")
            for hostname, _ in self._test_endpoints[:5]  # Limit HTTP tests
        ]

        http_results = await asyncio.gather(*http_tasks, return_exceptions=True)
        for result in http_results:
            if isinstance(result, EgressViolation):
                self._violations.append(result)

        tests_total = len(self._test_endpoints) * 2 + len(http_tasks)
        tests_failed = len(self._violations)

        return EgressValidationResult(
            is_air_gapped=is_air_gap,
            violations=self._violations,
            tests_passed=tests_total - tests_failed,
            tests_failed=tests_failed,
        )

    def validate_kubernetes_network_policy(self) -> dict:
        """
        Validate Kubernetes NetworkPolicy configuration.

        Checks if default-deny egress policy is in place.

        Returns:
            Dictionary with validation results
        """
        try:
            from kubernetes import client, config

            # Load in-cluster config
            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config()

            v1 = client.NetworkingV1Api()

            # Get current namespace
            namespace = os.getenv("POD_NAMESPACE", "default")

            # List network policies
            policies = v1.list_namespaced_network_policy(namespace)

            default_deny_found = False
            egress_policies = []

            for policy in policies.items:
                spec = policy.spec

                # Check for default-deny egress
                if spec.policy_types and "Egress" in spec.policy_types:
                    if not spec.egress:
                        default_deny_found = True
                    egress_policies.append(policy.metadata.name)

            return {
                "namespace": namespace,
                "default_deny_egress": default_deny_found,
                "egress_policies": egress_policies,
                "policy_count": len(policies.items),
                "compliant": default_deny_found,
            }

        except ImportError:
            return {
                "error": "kubernetes library not available",
                "compliant": None,
            }
        except Exception as e:
            return {
                "error": str(e),
                "compliant": None,
            }


def validate_air_gap_mode() -> EgressValidationResult:
    """
    Convenience function to validate air-gap mode.

    Returns:
        EgressValidationResult with test results
    """
    validator = EgressValidator()
    return validator.validate_sync()


def require_air_gap_compliance() -> None:
    """
    Require air-gap compliance, raising if validation fails.

    Use this at startup for air-gapped deployments to ensure
    network isolation is properly configured.
    """
    result = validate_air_gap_mode()

    if result.is_air_gapped and not result.is_compliant:
        violations_summary = ", ".join(
            f"{v.destination}:{v.port or 'dns'}" for v in result.violations[:5]
        )
        raise RuntimeError(
            f"Air-gap validation failed: {len(result.violations)} violations detected. "
            f"External connectivity found to: {violations_summary}"
        )
