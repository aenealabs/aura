"""
Project Aura - LLM Prompt Sanitization Service

Provides comprehensive input sanitization for LLM prompts to prevent:
- Prompt injection attacks
- System prompt override attempts
- Jailbreak patterns
- Hidden instruction injection

Security patterns based on OWASP LLM Top 10:
- LLM01: Prompt Injection
- LLM02: Insecure Output Handling
- LLM07: Inadequate AI Alignment

Author: Project Aura Team
Created: 2025-12-12
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    """Severity of detected prompt injection attempt.

    Values are numeric for proper comparison ordering.
    """

    NONE = 0
    LOW = 1  # Suspicious but likely benign
    MEDIUM = 2  # Potential injection attempt
    HIGH = 3  # Likely malicious
    CRITICAL = 4  # Active attack pattern

    def __lt__(self, other) -> bool:
        if isinstance(other, ThreatLevel):
            return self.value < other.value
        return NotImplemented

    def __gt__(self, other) -> bool:
        if isinstance(other, ThreatLevel):
            return self.value > other.value
        return NotImplemented

    def __le__(self, other) -> bool:
        if isinstance(other, ThreatLevel):
            return self.value <= other.value
        return NotImplemented

    def __ge__(self, other) -> bool:
        if isinstance(other, ThreatLevel):
            return self.value >= other.value
        return NotImplemented


class SanitizationAction(Enum):
    """Action taken during sanitization."""

    PASS = "pass"  # Input allowed through
    SANITIZED = "sanitized"  # Dangerous content removed
    BLOCKED = "blocked"  # Input rejected entirely


@dataclass
class SanitizationResult:
    """Result of prompt sanitization."""

    original_prompt: str
    sanitized_prompt: str
    action: SanitizationAction
    threat_level: ThreatLevel
    patterns_detected: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        """Check if the prompt is safe to use."""
        return self.action != SanitizationAction.BLOCKED

    @property
    def was_modified(self) -> bool:
        """Check if the prompt was modified."""
        return self.original_prompt != self.sanitized_prompt


# =============================================================================
# Injection Pattern Definitions
# =============================================================================

# System prompt override attempts
SYSTEM_OVERRIDE_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|guidelines?)",
    r"(?i)disregard\s+(all\s+)?(previous|prior|system)\s+(instructions?|prompts?)",
    r"(?i)forget\s+(everything|all)\s+(you\s+)?(know|were\s+told|learned)",
    r"(?i)new\s+instructions?\s*:",
    r"(?i)your\s+new\s+(role|persona|identity)\s+is",
    r"(?i)you\s+are\s+now\s+(a|an|the)\s+",
    r"(?i)act\s+as\s+if\s+you\s+(are|were)\s+",
    r"(?i)pretend\s+(you\s+)?(are|were)\s+(a|an|the)\s+",
    r"(?i)from\s+now\s+on\s*,?\s*(you\s+)?(will|must|should)",
    r"(?i)override\s+(system|safety|security)\s+(prompt|settings?|restrictions?)",
    r"(?i)bypass\s+(safety|security|content)\s+(filter|restrictions?|guidelines?)",
]

# Jailbreak attempt patterns
JAILBREAK_PATTERNS = [
    r"(?i)DAN\s*mode",
    r"(?i)do\s+anything\s+now",
    r"(?i)jailbreak",
    r"(?i)developer\s+mode",
    r"(?i)unrestricted\s+mode",
    r"(?i)no\s+restrictions?\s+mode",
    r"(?i)evil\s+mode",
    r"(?i)opposite\s+mode",
    r"(?i)hypothetically\s+speaking",
    r"(?i)in\s+a\s+fictional\s+(world|scenario|universe)",
    r"(?i)roleplay\s+as\s+(a\s+)?(malicious|evil|hacker)",
    r"(?i)imagine\s+you\s+(have\s+)?no\s+(ethical|moral)\s+(guidelines?|restrictions?)",
]

# Hidden instruction patterns (invisible characters, encoding tricks)
HIDDEN_INSTRUCTION_PATTERNS = [
    r"[\u200b\u200c\u200d\ufeff]",  # Zero-width characters
    r"[\u2060\u2061\u2062\u2063]",  # Word joiner and invisible characters
    r"[\u00ad]",  # Soft hyphen
    r"<!--[\s\S]*?-->",  # HTML comments (multiline-safe)
    r"\[INST\][\s\S]*?\[/INST\]",  # Instruction tags (multiline-safe)
    r"<\|[\s\S]*?\|>",  # Special delimiter patterns (multiline-safe)
    r"###\s*(?:system|instruction|hidden):",  # Markdown instruction injection
]

# Homoglyph confusables: Cyrillic and Greek letters that visually mimic Latin
# ASCII. Attackers substitute these to bypass keyword-based pattern matching.
# Source: a curated subset of UAX #39 Unicode Confusables most commonly abused
# for English-language prompt injection (ignore, system, prompt, etc.).
HOMOGLYPH_CONFUSABLES: dict[str, str] = {
    # Cyrillic lowercase -> Latin lowercase
    "\u0430": "a",
    "\u0435": "e",
    "\u043e": "o",
    "\u0440": "p",
    "\u0441": "c",
    "\u0443": "y",
    "\u0445": "x",
    # Cyrillic uppercase -> Latin uppercase
    "\u0410": "A",
    "\u0412": "B",
    "\u0415": "E",
    "\u041a": "K",
    "\u041c": "M",
    "\u041d": "H",
    "\u041e": "O",
    "\u0420": "P",
    "\u0421": "C",
    "\u0422": "T",
    "\u0425": "X",
    # Greek lowercase -> Latin lowercase
    "\u03bf": "o",
    "\u03b1": "a",
    "\u03b5": "e",
    "\u03b9": "i",
    "\u03bd": "v",
    "\u03c1": "p",
    "\u03c7": "x",
    "\u03ba": "k",
    "\u03bc": "u",
    # Greek uppercase -> Latin uppercase
    "\u039f": "O",
    "\u0391": "A",
    "\u0395": "E",
    "\u0399": "I",
    "\u039a": "K",
    "\u039c": "M",
    "\u039d": "N",
    "\u03a1": "P",
    "\u03a4": "T",
    "\u03a7": "X",
}

_HOMOGLYPH_TABLE = str.maketrans(HOMOGLYPH_CONFUSABLES)

# Delimiter injection (trying to close/reopen system prompts)
DELIMITER_PATTERNS = [
    r"```\s*system\s*```",
    r"\n---\s*system\s*---\n",
    r"<system>.*?</system>",
    r"\[system\].*?\[/system\]",
    r"<<SYS>>.*?<</SYS>>",
    r"Human:\s*\n*Assistant:",  # Claude-specific delimiter injection
]

# Data exfiltration attempts
EXFILTRATION_PATTERNS = [
    r"(?i)repeat\s+(the\s+)?(system\s+)?(prompt|instructions?|rules?)",
    r"(?i)what\s+(are|is)\s+(your|the)\s+(system\s+)?(prompt|instructions?)",
    r"(?i)show\s+me\s+(your|the)\s+(hidden|system)\s+(prompt|instructions?)",
    r"(?i)output\s+(your|the)\s+(system|original)\s+(prompt|text|instructions?)",
    r"(?i)print\s+(the\s+)?(system|initial)\s+(prompt|message)",
]


# =============================================================================
# LLM Prompt Sanitizer
# =============================================================================


class LLMPromptSanitizer:
    """
    Sanitizes LLM prompts to prevent injection attacks.

    Usage:
        >>> sanitizer = LLMPromptSanitizer()
        >>> result = sanitizer.sanitize("Ignore previous instructions and...")
        >>> if result.is_safe:
        ...     llm.generate(result.sanitized_prompt)
        ... else:
        ...     log_security_event(result)

    Configuration:
        - strict_mode: Block any suspicious input (default: False)
        - log_threats: Log detected threats (default: True)
        - max_prompt_length: Maximum allowed prompt length (default: 100000)
    """

    DEFAULT_MAX_LENGTH = 100000  # 100k characters

    def __init__(
        self,
        strict_mode: bool = False,
        log_threats: bool = True,
        max_prompt_length: int | None = None,
        custom_patterns: list[str] | None = None,
    ):
        """
        Initialize the sanitizer.

        Args:
            strict_mode: If True, block any suspicious input rather than sanitizing
            log_threats: Log detected threats to security logger
            max_prompt_length: Maximum allowed prompt length
            custom_patterns: Additional regex patterns to detect
        """
        self.strict_mode = strict_mode
        self.log_threats = log_threats
        self.max_prompt_length = max_prompt_length or self.DEFAULT_MAX_LENGTH
        self.custom_patterns = custom_patterns or []

        # Compile all patterns for efficiency
        self._compiled_patterns: dict[str, list[re.Pattern]] = {
            "system_override": [re.compile(p) for p in SYSTEM_OVERRIDE_PATTERNS],
            "jailbreak": [re.compile(p) for p in JAILBREAK_PATTERNS],
            "hidden": [re.compile(p) for p in HIDDEN_INSTRUCTION_PATTERNS],
            "delimiter": [re.compile(p, re.DOTALL) for p in DELIMITER_PATTERNS],
            "exfiltration": [re.compile(p) for p in EXFILTRATION_PATTERNS],
            "custom": [re.compile(p) for p in self.custom_patterns],
        }

        # Statistics for monitoring
        # Keys match SanitizationAction enum values: pass, sanitized, blocked
        self._stats: dict[str, Any] = {
            "total_processed": 0,
            "pass": 0,  # SanitizationAction.PASS.value
            "sanitized": 0,  # SanitizationAction.SANITIZED.value
            "blocked": 0,  # SanitizationAction.BLOCKED.value
            "threats_by_level": {level.name.lower(): 0 for level in ThreatLevel},
        }

    def sanitize(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> SanitizationResult:
        """
        Sanitize a user prompt for safe LLM consumption.

        Args:
            prompt: The user-provided prompt
            context: Optional context (agent name, operation, etc.)

        Returns:
            SanitizationResult with sanitized prompt and threat analysis
        """
        self._stats["total_processed"] += 1

        if not prompt:
            return SanitizationResult(
                original_prompt="",
                sanitized_prompt="",
                action=SanitizationAction.PASS,
                threat_level=ThreatLevel.NONE,
            )

        # Check length first
        if len(prompt) > self.max_prompt_length:
            self._stats["blocked"] += 1
            if self.log_threats:
                logger.warning(
                    f"Prompt blocked: exceeds max length "
                    f"({len(prompt)} > {self.max_prompt_length})"
                )
            return SanitizationResult(
                original_prompt=prompt,
                sanitized_prompt="",
                action=SanitizationAction.BLOCKED,
                threat_level=ThreatLevel.HIGH,
                patterns_detected=["max_length_exceeded"],
                warnings=[
                    f"Prompt length {len(prompt)} exceeds maximum {self.max_prompt_length}"
                ],
            )

        # Detect threats
        detected_patterns = []
        threat_level = ThreatLevel.NONE

        # Homoglyph defense: fold Cyrillic/Greek lookalikes to Latin and re-run
        # pattern matching against the normalized text. This catches attacks
        # like `ignоre all previous instructions` that bypass raw ASCII
        # keyword matching. We only flag once if any confusable was present.
        normalized = prompt.translate(_HOMOGLYPH_TABLE)
        has_homoglyphs = normalized != prompt

        # Check each pattern category
        for category, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(prompt)
                if not matches and has_homoglyphs:
                    matches = pattern.findall(normalized)
                if matches:
                    detected_patterns.append(f"{category}:{pattern.pattern[:50]}")

                    # Assign threat level based on category
                    category_threat = self._get_category_threat_level(category)
                    if category_threat.value > threat_level.value:
                        threat_level = category_threat

        # If the input contained homoglyph confusables at all, flag it as a
        # hidden-instruction attempt regardless of whether matching keywords
        # surfaced - mixing Cyrillic/Greek into English text is suspicious
        # on its own and should raise threat level to at least LOW.
        if has_homoglyphs:
            detected_patterns.append("hidden:homoglyph_confusables")
            hidden_threat = self._get_category_threat_level("hidden")
            if hidden_threat.value > threat_level.value:
                threat_level = hidden_threat

        # Decide action based on threat level and mode
        if (
            threat_level in (ThreatLevel.CRITICAL, ThreatLevel.HIGH)
            and self.strict_mode
        ):
            action = SanitizationAction.BLOCKED
            sanitized_prompt = ""
        elif threat_level != ThreatLevel.NONE:
            action = SanitizationAction.SANITIZED
            sanitized_prompt = self._remove_threats(prompt)
        else:
            action = SanitizationAction.PASS
            sanitized_prompt = prompt

        # Update stats
        self._stats[action.value] += 1
        self._stats["threats_by_level"][threat_level.name.lower()] += 1

        # Log threats
        if self.log_threats and threat_level != ThreatLevel.NONE:
            self._log_threat(prompt, threat_level, detected_patterns, context)

        return SanitizationResult(
            original_prompt=prompt,
            sanitized_prompt=sanitized_prompt,
            action=action,
            threat_level=threat_level,
            patterns_detected=detected_patterns,
            warnings=self._generate_warnings(detected_patterns),
        )

    def sanitize_system_prompt(self, system_prompt: str) -> SanitizationResult:
        """
        Sanitize a system prompt (stricter validation).

        System prompts should not contain user-controllable content.
        This method ensures no injection has leaked into system prompts.
        """
        # System prompts are typically developer-controlled, but validate anyway
        result = self.sanitize(system_prompt, context={"type": "system_prompt"})

        # Additional system prompt checks
        if "{{" in system_prompt or "}}" in system_prompt:
            result.warnings.append("System prompt contains template markers")

        return result

    def _get_category_threat_level(self, category: str) -> ThreatLevel:
        """Map pattern category to threat level."""
        threat_levels = {
            "system_override": ThreatLevel.CRITICAL,
            "jailbreak": ThreatLevel.HIGH,
            "hidden": ThreatLevel.HIGH,
            "delimiter": ThreatLevel.CRITICAL,
            "exfiltration": ThreatLevel.MEDIUM,
            "custom": ThreatLevel.MEDIUM,
        }
        return threat_levels.get(category, ThreatLevel.LOW)

    def _remove_threats(self, prompt: str) -> str:
        """Remove detected threat patterns from prompt."""
        sanitized = prompt

        # Remove hidden characters
        for pattern in self._compiled_patterns["hidden"]:
            sanitized = pattern.sub("", sanitized)

        # Remove delimiter injections
        for pattern in self._compiled_patterns["delimiter"]:
            sanitized = pattern.sub("[REMOVED]", sanitized)

        # For other patterns, we don't remove them but the warning is logged
        # Removing entire sentences could break legitimate queries

        # Normalize whitespace
        sanitized = re.sub(r"\s+", " ", sanitized).strip()

        return sanitized

    def _log_threat(
        self,
        prompt: str,
        threat_level: ThreatLevel,
        patterns: list[str],
        context: dict[str, Any] | None,
    ) -> None:
        """Log detected threat for security monitoring."""
        # Truncate prompt for logging (don't log full malicious content)
        truncated_prompt = prompt[:200] + "..." if len(prompt) > 200 else prompt

        log_msg = (
            f"Prompt injection detected: level={threat_level.value}, "
            f"patterns={patterns[:3]}, prompt_preview='{truncated_prompt}'"
        )

        if context:
            log_msg += f", context={context}"

        if threat_level in (ThreatLevel.CRITICAL, ThreatLevel.HIGH):
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

    def _generate_warnings(self, patterns: list[str]) -> list[str]:
        """Generate human-readable warnings from detected patterns."""
        warnings = []

        categories = {p.split(":")[0] for p in patterns}

        if "system_override" in categories:
            warnings.append("Detected attempt to override system instructions")
        if "jailbreak" in categories:
            warnings.append("Detected jailbreak attempt pattern")
        if "hidden" in categories:
            warnings.append("Detected hidden characters or instructions")
        if "delimiter" in categories:
            warnings.append("Detected delimiter injection attempt")
        if "exfiltration" in categories:
            warnings.append("Detected system prompt exfiltration attempt")

        return warnings

    def get_stats(self) -> dict[str, Any]:
        """Get sanitization statistics."""
        return self._stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._stats = {
            "total_processed": 0,
            "pass": 0,
            "sanitized": 0,
            "blocked": 0,
            "threats_by_level": {level.name.lower(): 0 for level in ThreatLevel},
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_sanitizer_instance: LLMPromptSanitizer | None = None


def get_prompt_sanitizer(
    strict_mode: bool = False,
    log_threats: bool = True,
) -> LLMPromptSanitizer:
    """
    Get singleton prompt sanitizer instance.

    Args:
        strict_mode: Block suspicious inputs (vs sanitize)
        log_threats: Log detected threats

    Returns:
        LLMPromptSanitizer instance
    """
    global _sanitizer_instance
    if _sanitizer_instance is None:
        _sanitizer_instance = LLMPromptSanitizer(
            strict_mode=strict_mode,
            log_threats=log_threats,
        )
    return _sanitizer_instance


def sanitize_prompt(prompt: str, strict: bool = False) -> str:
    """
    Convenience function to sanitize a prompt.

    Args:
        prompt: User prompt to sanitize
        strict: Use strict mode (block vs sanitize)

    Returns:
        Sanitized prompt string

    Raises:
        ValueError: If prompt is blocked in strict mode
    """
    sanitizer = get_prompt_sanitizer(strict_mode=strict)
    result = sanitizer.sanitize(prompt)

    if result.action == SanitizationAction.BLOCKED:
        raise ValueError(f"Prompt blocked: {result.warnings}")

    return result.sanitized_prompt
