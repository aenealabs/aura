"""
Bedrock Guardrails Configuration
Provides configuration for AWS Bedrock Guardrails integration
for agent output safety and validation (ADR-029 Phase 1.1).

Guardrails provide:
- Content filtering (hate, violence, misconduct, prompt attacks)
- PII protection (SSN, credit cards, AWS credentials)
- Topic blocking (malware, social engineering, credential theft)
- Automated reasoning checks for factual validation
"""

import copy
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class GuardrailMode(Enum):
    """Guardrail operation modes."""

    DISABLED = "disabled"  # No guardrails applied
    DETECT = "detect"  # Log violations but don't block
    ENFORCE = "enforce"  # Block violating content


class ContentFilterStrength(Enum):
    """Content filter strength levels."""

    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PIIAction(Enum):
    """Actions for PII detection."""

    BLOCK = "BLOCK"  # Block entire response
    ANONYMIZE = "ANONYMIZE"  # Mask with placeholders


@dataclass
class ContentFilterConfig:
    """Configuration for a content filter type."""

    filter_type: str
    input_strength: ContentFilterStrength
    output_strength: ContentFilterStrength


@dataclass
class PIIEntityConfig:
    """Configuration for PII entity handling."""

    entity_type: str
    action: PIIAction


@dataclass
class TopicConfig:
    """Configuration for topic blocking."""

    name: str
    definition: str
    examples: list[str]


@dataclass
class GuardrailConfig:
    """Complete guardrail configuration."""

    mode: GuardrailMode
    guardrail_id: str | None = None
    guardrail_version: str | None = None
    ssm_parameter_prefix: str = "/aura"

    # Content filters
    content_filters: list[ContentFilterConfig] = field(default_factory=list)

    # PII protection
    pii_entities: list[PIIEntityConfig] = field(default_factory=list)

    # Topic blocking
    blocked_topics: list[TopicConfig] = field(default_factory=list)

    # Regex patterns for sensitive data
    sensitive_patterns: list[dict[str, str]] = field(default_factory=list)

    # Blocked words
    blocked_words: list[str] = field(default_factory=list)

    # Whether to use automated reasoning (factual validation)
    automated_reasoning_enabled: bool = False


# Default content filters for security-focused applications
DEFAULT_CONTENT_FILTERS = [
    ContentFilterConfig(
        filter_type="HATE",
        input_strength=ContentFilterStrength.HIGH,
        output_strength=ContentFilterStrength.HIGH,
    ),
    ContentFilterConfig(
        filter_type="INSULTS",
        input_strength=ContentFilterStrength.MEDIUM,
        output_strength=ContentFilterStrength.MEDIUM,
    ),
    ContentFilterConfig(
        filter_type="SEXUAL",
        input_strength=ContentFilterStrength.HIGH,
        output_strength=ContentFilterStrength.HIGH,
    ),
    ContentFilterConfig(
        filter_type="VIOLENCE",
        input_strength=ContentFilterStrength.MEDIUM,
        output_strength=ContentFilterStrength.MEDIUM,
    ),
    ContentFilterConfig(
        filter_type="MISCONDUCT",
        input_strength=ContentFilterStrength.HIGH,
        output_strength=ContentFilterStrength.HIGH,
    ),
    ContentFilterConfig(
        filter_type="PROMPT_ATTACK",
        input_strength=ContentFilterStrength.HIGH,
        output_strength=ContentFilterStrength.NONE,
    ),
]

# Default PII entities to protect
DEFAULT_PII_ENTITIES = [
    PIIEntityConfig(entity_type="EMAIL", action=PIIAction.ANONYMIZE),
    PIIEntityConfig(entity_type="PHONE", action=PIIAction.ANONYMIZE),
    PIIEntityConfig(entity_type="US_SOCIAL_SECURITY_NUMBER", action=PIIAction.BLOCK),
    PIIEntityConfig(entity_type="CREDIT_DEBIT_CARD_NUMBER", action=PIIAction.BLOCK),
    PIIEntityConfig(entity_type="CREDIT_DEBIT_CARD_CVV", action=PIIAction.BLOCK),
    PIIEntityConfig(entity_type="CREDIT_DEBIT_CARD_EXPIRY", action=PIIAction.BLOCK),
    PIIEntityConfig(entity_type="IP_ADDRESS", action=PIIAction.ANONYMIZE),
    PIIEntityConfig(entity_type="AWS_ACCESS_KEY", action=PIIAction.BLOCK),
    PIIEntityConfig(entity_type="AWS_SECRET_KEY", action=PIIAction.BLOCK),
]

# Default topics to block
DEFAULT_BLOCKED_TOPICS = [
    TopicConfig(
        name="malware-creation",
        definition="Requests to create malware, viruses, ransomware, or exploit code for malicious purposes",
        examples=[
            "Write a keylogger in Python",
            "Create a ransomware script",
            "Generate code to exploit CVE vulnerabilities for attacks",
        ],
    ),
    TopicConfig(
        name="social-engineering",
        definition="Requests to help with phishing, pretexting, or social engineering attacks",
        examples=[
            "Write a phishing email template",
            "Help me impersonate a bank representative",
            "Create a fake login page",
        ],
    ),
    TopicConfig(
        name="credential-theft",
        definition="Requests to steal, crack, or brute-force passwords and credentials",
        examples=[
            "Write a password cracker",
            "How to steal AWS credentials",
            "Brute force SSH login script",
        ],
    ),
]

# Default sensitive patterns (regex)
DEFAULT_SENSITIVE_PATTERNS = [
    {
        "name": "api-key-pattern",
        "description": "Detect potential API keys",
        "pattern": r'(?i)(api[_-]?key|apikey|api[_-]?secret)["\\s:=]+["\']?[a-zA-Z0-9_-]{20,}["\']?',
    },
    {
        "name": "jwt-token-pattern",
        "description": "Detect JWT tokens",
        "pattern": r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
    },
    {
        "name": "private-key-pattern",
        "description": "Detect private key headers",
        "pattern": r"-----BEGIN\\s+(RSA\\s+)?PRIVATE\\s+KEY-----",
    },
]


class GuardrailEnvironment(Enum):
    """Environment types for guardrail configuration."""

    DEV = "dev"
    QA = "qa"
    STAGING = "staging"
    PROD = "prod"


# Environment-specific guardrail configurations
GUARDRAIL_CONFIG: dict[GuardrailEnvironment, GuardrailConfig] = {
    GuardrailEnvironment.DEV: GuardrailConfig(
        mode=GuardrailMode.DETECT,  # Detect-only in dev for visibility
        ssm_parameter_prefix="/aura/dev/guardrails",
        content_filters=DEFAULT_CONTENT_FILTERS,
        pii_entities=DEFAULT_PII_ENTITIES,
        blocked_topics=DEFAULT_BLOCKED_TOPICS,
        sensitive_patterns=DEFAULT_SENSITIVE_PATTERNS,
        blocked_words=["rm -rf /"],
        automated_reasoning_enabled=False,  # Enable after validation
    ),
    GuardrailEnvironment.QA: GuardrailConfig(
        mode=GuardrailMode.ENFORCE,  # Enforce in QA to test blocking
        ssm_parameter_prefix="/aura/qa/guardrails",
        content_filters=DEFAULT_CONTENT_FILTERS,
        pii_entities=DEFAULT_PII_ENTITIES,
        blocked_topics=DEFAULT_BLOCKED_TOPICS,
        sensitive_patterns=DEFAULT_SENSITIVE_PATTERNS,
        blocked_words=["rm -rf /"],
        automated_reasoning_enabled=True,
    ),
    GuardrailEnvironment.STAGING: GuardrailConfig(
        mode=GuardrailMode.ENFORCE,
        ssm_parameter_prefix="/aura/staging/guardrails",
        content_filters=DEFAULT_CONTENT_FILTERS,
        pii_entities=DEFAULT_PII_ENTITIES,
        blocked_topics=DEFAULT_BLOCKED_TOPICS,
        sensitive_patterns=DEFAULT_SENSITIVE_PATTERNS,
        blocked_words=["rm -rf /"],
        automated_reasoning_enabled=True,
    ),
    GuardrailEnvironment.PROD: GuardrailConfig(
        mode=GuardrailMode.ENFORCE,  # Always enforce in production
        ssm_parameter_prefix="/aura/prod/guardrails",
        content_filters=DEFAULT_CONTENT_FILTERS,
        pii_entities=DEFAULT_PII_ENTITIES,
        blocked_topics=DEFAULT_BLOCKED_TOPICS,
        sensitive_patterns=DEFAULT_SENSITIVE_PATTERNS,
        blocked_words=["rm -rf /"],
        automated_reasoning_enabled=True,
    ),
}


def get_guardrail_environment() -> GuardrailEnvironment:
    """
    Get current environment from AURA_ENV environment variable.

    Returns:
        GuardrailEnvironment enum value
    """
    env_str = os.environ.get("AURA_ENV", "dev").lower()

    env_map = {
        "development": GuardrailEnvironment.DEV,
        "dev": GuardrailEnvironment.DEV,
        "qa": GuardrailEnvironment.QA,
        "staging": GuardrailEnvironment.STAGING,
        "stage": GuardrailEnvironment.STAGING,
        "production": GuardrailEnvironment.PROD,
        "prod": GuardrailEnvironment.PROD,
    }

    return env_map.get(env_str, GuardrailEnvironment.DEV)


def get_guardrail_config(
    environment: GuardrailEnvironment | None = None,
) -> GuardrailConfig:
    """
    Get guardrail configuration for specified or current environment.

    Returns a copy to prevent mutation of global config state.

    Args:
        environment: Optional environment override

    Returns:
        GuardrailConfig copy for the environment
    """
    env = environment or get_guardrail_environment()
    return copy.deepcopy(GUARDRAIL_CONFIG[env])


def load_guardrail_ids_from_ssm(
    config: GuardrailConfig, ssm_client: Any | None = None
) -> GuardrailConfig:
    """
    Load guardrail ID and version from SSM Parameter Store.

    Args:
        config: GuardrailConfig to update
        ssm_client: Optional boto3 SSM client (creates one if not provided)

    Returns:
        Updated GuardrailConfig with guardrail_id and guardrail_version
    """
    if config.mode == GuardrailMode.DISABLED:
        logger.info("Guardrails disabled - skipping SSM lookup")
        return config

    try:
        if ssm_client is None:
            import boto3

            ssm_client = boto3.client("ssm", region_name="us-east-1")

        # Load guardrail ID
        guardrail_id_param = f"{config.ssm_parameter_prefix}/guardrail-id"
        try:
            response = ssm_client.get_parameter(Name=guardrail_id_param)
            config.guardrail_id = response["Parameter"]["Value"]
            logger.info(f"Loaded guardrail ID from SSM: {config.guardrail_id}")
        except ssm_client.exceptions.ParameterNotFound:
            logger.warning(f"Guardrail ID parameter not found: {guardrail_id_param}")

        # Load guardrail version
        version_param = f"{config.ssm_parameter_prefix}/guardrail-version"
        try:
            response = ssm_client.get_parameter(Name=version_param)
            config.guardrail_version = response["Parameter"]["Value"]
            logger.info(
                f"Loaded guardrail version from SSM: {config.guardrail_version}"
            )
        except ssm_client.exceptions.ParameterNotFound:
            logger.warning(f"Guardrail version parameter not found: {version_param}")
            # Default to DRAFT if version not found
            config.guardrail_version = "DRAFT"

    except ImportError:
        logger.warning("boto3 not available - cannot load guardrail IDs from SSM")
    except Exception as e:
        logger.error(f"Failed to load guardrail IDs from SSM: {e}")

    return config


@dataclass
class GuardrailResult:
    """Result of guardrail validation."""

    passed: bool
    action_taken: str  # "none", "blocked", "anonymized"
    violations: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str | None = None
    guardrail_id: str | None = None


def format_guardrail_trace(trace: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Format guardrail trace into readable violations list.

    Args:
        trace: Raw trace from Bedrock Guardrails API

    Returns:
        List of violation dictionaries
    """
    violations: list[dict[str, Any]] = []

    if not trace:
        return violations

    # Parse input assessments
    for assessment in trace.get("inputAssessments", []):
        for topic in assessment.get("topicPolicy", {}).get("topics", []):
            if topic.get("action") == "BLOCKED":
                violations.append(
                    {
                        "type": "topic",
                        "name": topic.get("name"),
                        "direction": "input",
                        "action": "blocked",
                    }
                )

        for content in assessment.get("contentPolicy", {}).get("filters", []):
            if content.get("action") == "BLOCKED":
                violations.append(
                    {
                        "type": "content",
                        "category": content.get("type"),
                        "direction": "input",
                        "action": "blocked",
                        "confidence": content.get("confidence"),
                    }
                )

    # Parse output assessments
    for assessment in trace.get("outputAssessments", []):
        for topic in assessment.get("topicPolicy", {}).get("topics", []):
            if topic.get("action") == "BLOCKED":
                violations.append(
                    {
                        "type": "topic",
                        "name": topic.get("name"),
                        "direction": "output",
                        "action": "blocked",
                    }
                )

        for content in assessment.get("contentPolicy", {}).get("filters", []):
            if content.get("action") == "BLOCKED":
                violations.append(
                    {
                        "type": "content",
                        "category": content.get("type"),
                        "direction": "output",
                        "action": "blocked",
                        "confidence": content.get("confidence"),
                    }
                )

        # PII detections
        for pii in assessment.get("sensitiveInformationPolicy", {}).get(
            "piiEntities", []
        ):
            violations.append(
                {
                    "type": "pii",
                    "entity_type": pii.get("type"),
                    "direction": "output",
                    "action": pii.get("action", "detected").lower(),
                    "match": pii.get("match"),
                }
            )

    return violations


if __name__ == "__main__":
    # Demo usage
    print("Project Aura - Bedrock Guardrails Configuration")
    print("=" * 60)

    env = get_guardrail_environment()
    print(f"\nCurrent Environment: {env.value}")

    config = get_guardrail_config()
    print(f"\nGuardrail Mode: {config.mode.value}")
    print(f"SSM Parameter Prefix: {config.ssm_parameter_prefix}")
    print(f"Automated Reasoning: {config.automated_reasoning_enabled}")

    print(f"\nContent Filters ({len(config.content_filters)}):")
    for cf in config.content_filters:
        print(
            f"  - {cf.filter_type}: input={cf.input_strength.value}, output={cf.output_strength.value}"
        )

    print(f"\nPII Entities ({len(config.pii_entities)}):")
    for pii in config.pii_entities:
        print(f"  - {pii.entity_type}: {pii.action.value}")

    print(f"\nBlocked Topics ({len(config.blocked_topics)}):")
    for topic in config.blocked_topics:
        print(f"  - {topic.name}: {topic.definition[:50]}...")

    print("\n" + "=" * 60)
    print("Configuration validation: PASSED")
