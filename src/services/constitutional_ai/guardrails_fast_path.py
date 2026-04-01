"""Bedrock Guardrails fast-path for Constitutional AI Phase 3.

Provides sub-100ms guardrail checks for CRITICAL severity principles using
Amazon Bedrock Guardrails, enabling fast-fail before expensive LLM critique.

ADR-063 Phase 3 specifies this fast-path architecture:
1. Check CRITICAL principles (1-3) via Bedrock Guardrails (~100ms)
2. If blocked, return immediately without LLM critique
3. If passed, proceed to batched LLM critique

CRITICAL constitutional principles mapped to Bedrock Guardrails:
- principle_1_security_first -> Content filters (malware, exploits)
- principle_2_data_protection -> PII detection (BLOCK mode)
- principle_3_sandbox_isolation -> Topic blocking (sandbox escape)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

logger = logging.getLogger(__name__)


class FastPathMode(Enum):
    """Operating modes for guardrails fast-path."""

    ENABLED = "enabled"  # Full guardrails integration
    DISABLED = "disabled"  # Skip guardrails, use LLM critique only
    MOCK = "mock"  # Return mock results for testing


class GuardrailAction(Enum):
    """Bedrock Guardrail actions."""

    NONE = "none"  # No intervention
    BLOCKED = "blocked"  # Content blocked
    MODIFIED = "modified"  # Content modified (not used in fast-path)


@dataclass
class FastPathViolation:
    """A single violation detected by the fast-path.

    Attributes:
        principle_id: Constitutional principle that was violated
        guardrail_type: Type of Bedrock Guardrail that triggered
        confidence: Confidence score (0.0-1.0)
        matched_content: Snippet of content that triggered violation
        action: Action taken by guardrail
    """

    principle_id: str
    guardrail_type: str
    confidence: float
    matched_content: str
    action: GuardrailAction


@dataclass
class FastPathResult:
    """Result of guardrails fast-path check.

    Attributes:
        blocked: Whether the content was blocked by guardrails
        violations: List of violations detected
        latency_ms: Time taken for the check in milliseconds
        principle_ids_blocked: Which CRITICAL principles were violated
        guardrail_id: ID of the Bedrock Guardrail used
        raw_response: Raw response from Bedrock (for debugging)
    """

    blocked: bool
    violations: List[FastPathViolation] = field(default_factory=list)
    latency_ms: float = 0.0
    principle_ids_blocked: List[str] = field(default_factory=list)
    guardrail_id: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "blocked": self.blocked,
            "violations": [
                {
                    "principle_id": v.principle_id,
                    "guardrail_type": v.guardrail_type,
                    "confidence": v.confidence,
                    "matched_content": v.matched_content[:100],  # Truncate
                    "action": v.action.value,
                }
                for v in self.violations
            ],
            "latency_ms": self.latency_ms,
            "principle_ids_blocked": self.principle_ids_blocked,
            "guardrail_id": self.guardrail_id,
        }


# Mapping of CRITICAL constitutional principles to Bedrock Guardrail types
CRITICAL_PRINCIPLE_GUARDRAIL_MAP: Dict[str, List[str]] = {
    # Security-First Code Generation -> Content filters for malware/exploits
    "principle_1_security_first": [
        "CONTENT_POLICY",  # Harmful content filter
        "SENSITIVE_INFORMATION",  # Credential/secret detection
    ],
    # Data Protection -> PII detection
    "principle_2_data_protection": [
        "PII",  # Personal identifiable information
        "SENSITIVE_INFORMATION",  # Credentials, API keys
    ],
    # Sandbox Isolation -> Topic blocking for escape attempts
    "principle_3_sandbox_isolation": [
        "TOPIC_POLICY",  # Block sandbox escape topics
        "CONTENT_POLICY",  # Block container breakout content
    ],
}

# All CRITICAL principle IDs
CRITICAL_PRINCIPLE_IDS = list(CRITICAL_PRINCIPLE_GUARDRAIL_MAP.keys())


class GuardrailsFastPath:
    """Fast-path using Bedrock Guardrails for CRITICAL principles.

    Provides sub-100ms checks for CRITICAL constitutional principles
    using Amazon Bedrock Guardrails, enabling fast-fail before expensive
    LLM-based critique.

    Attributes:
        mode: Operating mode (ENABLED, DISABLED, MOCK)
        guardrail_id: Bedrock Guardrail identifier
        guardrail_version: Guardrail version to use
    """

    def __init__(
        self,
        mode: FastPathMode = FastPathMode.MOCK,
        guardrail_id: Optional[str] = None,
        guardrail_version: str = "DRAFT",
        bedrock_client: Optional["BedrockRuntimeClient"] = None,
    ):
        """Initialize the guardrails fast-path.

        Args:
            mode: Operating mode for fast-path
            guardrail_id: Bedrock Guardrail ID (required for ENABLED mode)
            guardrail_version: Version of guardrail to use
            bedrock_client: Pre-configured Bedrock Runtime client
        """
        self.mode = mode
        self.guardrail_id = guardrail_id
        self.guardrail_version = guardrail_version
        self._bedrock = bedrock_client

        if mode == FastPathMode.ENABLED and not guardrail_id:
            logger.warning(
                "GuardrailsFastPath ENABLED mode requires guardrail_id, "
                "falling back to MOCK mode"
            )
            self.mode = FastPathMode.MOCK

    async def check_critical_principles(
        self,
        output: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> FastPathResult:
        """Run Bedrock Guardrails check on output.

        Checks the output against CRITICAL constitutional principles using
        Bedrock Guardrails. Target latency: <100ms.

        Args:
            output: The agent output to check
            context: Optional context (agent_name, operation_type, etc.)

        Returns:
            FastPathResult with blocked status and any violations

        Example:
            >>> result = await fast_path.check_critical_principles(
            ...     output="SELECT * FROM users WHERE password = '${input}'",
            ...     context={"agent_name": "CoderAgent"},
            ... )
            >>> result.blocked
            True
            >>> result.principle_ids_blocked
            ['principle_1_security_first']
        """
        start_time = time.perf_counter()

        try:
            if self.mode == FastPathMode.DISABLED:
                return FastPathResult(
                    blocked=False,
                    latency_ms=0.0,
                )

            if self.mode == FastPathMode.MOCK:
                return await self._mock_check(output, context)

            # ENABLED mode: Real Bedrock Guardrails check
            return await self._bedrock_check(output, context)

        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(f"FastPath check completed in {elapsed_ms:.1f}ms")

    async def _mock_check(
        self,
        output: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> FastPathResult:
        """Mock check for testing.

        Performs simple pattern matching to simulate guardrail behavior:
        - SQL injection patterns -> principle_1_security_first
        - Hardcoded credentials -> principle_2_data_protection
        - Container escape commands -> principle_3_sandbox_isolation
        """
        start_time = time.perf_counter()
        violations = []

        output_lower = output.lower()

        # Mock security checks
        security_patterns = [
            "sql injection",
            "exec(",
            "eval(",
            "os.system(",
            "subprocess.call(",
            "${",  # Template injection
            "'; drop table",
        ]
        for pattern in security_patterns:
            if pattern in output_lower:
                violations.append(
                    FastPathViolation(
                        principle_id="principle_1_security_first",
                        guardrail_type="CONTENT_POLICY",
                        confidence=0.95,
                        matched_content=output[:200],
                        action=GuardrailAction.BLOCKED,
                    )
                )
                break

        # Mock data protection checks
        data_patterns = [
            "password=",
            "api_key=",
            "secret=",
            "aws_access_key",
            "private_key",
        ]
        for pattern in data_patterns:
            if pattern in output_lower:
                violations.append(
                    FastPathViolation(
                        principle_id="principle_2_data_protection",
                        guardrail_type="SENSITIVE_INFORMATION",
                        confidence=0.90,
                        matched_content=output[:200],
                        action=GuardrailAction.BLOCKED,
                    )
                )
                break

        # Mock sandbox isolation checks
        sandbox_patterns = [
            "docker escape",
            "container breakout",
            "chroot escape",
            "/proc/self/root",
            "nsenter",
        ]
        for pattern in sandbox_patterns:
            if pattern in output_lower:
                violations.append(
                    FastPathViolation(
                        principle_id="principle_3_sandbox_isolation",
                        guardrail_type="TOPIC_POLICY",
                        confidence=0.92,
                        matched_content=output[:200],
                        action=GuardrailAction.BLOCKED,
                    )
                )
                break

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        blocked = len(violations) > 0
        principle_ids_blocked = list({v.principle_id for v in violations})

        return FastPathResult(
            blocked=blocked,
            violations=violations,
            latency_ms=elapsed_ms,
            principle_ids_blocked=principle_ids_blocked,
            guardrail_id="mock-guardrail",
        )

    async def _bedrock_check(
        self,
        output: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> FastPathResult:
        """Real Bedrock Guardrails check.

        Uses the apply_guardrail API for fast synchronous checks.
        """
        start_time = time.perf_counter()

        if not self._bedrock:
            logger.error("Bedrock client not configured for ENABLED mode")
            return FastPathResult(
                blocked=False,
                latency_ms=0.0,
            )

        try:
            # Use asyncio.to_thread for the blocking boto3 call
            response = await asyncio.to_thread(
                self._bedrock.apply_guardrail,
                guardrailIdentifier=self.guardrail_id,
                guardrailVersion=self.guardrail_version,
                source="OUTPUT",  # Checking agent output
                content=[{"text": {"text": output}}],
            )

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Parse response
            action = response.get("action", "NONE")
            blocked = action == "GUARDRAIL_INTERVENED"

            violations = []
            principle_ids_blocked = []

            if blocked:
                # Parse assessments to identify which principles were violated
                assessments = response.get("assessments", [])
                for assessment in assessments:
                    # Content policy violations
                    content_policy = assessment.get("contentPolicy", {})
                    for filter_result in content_policy.get("filters", []):
                        if filter_result.get("action") == "BLOCKED":
                            violations.append(
                                FastPathViolation(
                                    principle_id="principle_1_security_first",
                                    guardrail_type="CONTENT_POLICY",
                                    confidence=filter_result.get("confidence", 0.0),
                                    matched_content=output[:200],
                                    action=GuardrailAction.BLOCKED,
                                )
                            )
                            principle_ids_blocked.append("principle_1_security_first")

                    # Sensitive information violations
                    sensitive_info = assessment.get("sensitiveInformationPolicy", {})
                    for pii_result in sensitive_info.get("piiEntities", []):
                        if pii_result.get("action") == "BLOCKED":
                            violations.append(
                                FastPathViolation(
                                    principle_id="principle_2_data_protection",
                                    guardrail_type="PII",
                                    confidence=0.95,
                                    matched_content=output[:200],
                                    action=GuardrailAction.BLOCKED,
                                )
                            )
                            principle_ids_blocked.append("principle_2_data_protection")

                    # Topic policy violations
                    topic_policy = assessment.get("topicPolicy", {})
                    for topic_result in topic_policy.get("topics", []):
                        if topic_result.get("action") == "BLOCKED":
                            violations.append(
                                FastPathViolation(
                                    principle_id="principle_3_sandbox_isolation",
                                    guardrail_type="TOPIC_POLICY",
                                    confidence=0.90,
                                    matched_content=output[:200],
                                    action=GuardrailAction.BLOCKED,
                                )
                            )
                            principle_ids_blocked.append(
                                "principle_3_sandbox_isolation"
                            )

            return FastPathResult(
                blocked=blocked,
                violations=violations,
                latency_ms=elapsed_ms,
                principle_ids_blocked=list(set(principle_ids_blocked)),
                guardrail_id=self.guardrail_id,
                raw_response=response,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Bedrock guardrail check failed: {e}")

            # Fail-open: Don't block on guardrail errors, let LLM critique handle it
            return FastPathResult(
                blocked=False,
                latency_ms=elapsed_ms,
            )

    def get_critical_principles(self) -> List[str]:
        """Get the list of CRITICAL principle IDs handled by fast-path.

        Returns:
            List of principle IDs that are checked via guardrails
        """
        return CRITICAL_PRINCIPLE_IDS.copy()

    def is_enabled(self) -> bool:
        """Check if fast-path is enabled.

        Returns:
            True if mode is ENABLED or MOCK (active checking)
        """
        return self.mode != FastPathMode.DISABLED
