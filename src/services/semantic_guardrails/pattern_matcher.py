"""
Project Aura - Semantic Guardrails Layer 2: Fast-Path Pattern Matching

Pre-compiled regex patterns and hash-based blocklist for fast threat detection.
Target latency: P50 <10ms.

Detection Categories:
1. System prompt override attempts
2. Jailbreak patterns (DAN, developer mode, etc.)
3. Hidden instruction patterns (zero-width, comments)
4. Delimiter injection (closing/reopening prompts)
5. Data exfiltration attempts

Security Integration:
- Reuses and extends patterns from LLMPromptSanitizer
- Adds hash-based blocklist for known-bad inputs
- All patterns pre-compiled at initialization for performance

Author: Project Aura Team
Created: 2026-01-25
"""

import hashlib
import logging
import re
import time
from typing import Optional

from .config import PatternMatchConfig, get_guardrails_config
from .contracts import PatternMatchResult, ThreatCategory, ThreatLevel

logger = logging.getLogger(__name__)


# =============================================================================
# Pattern Definitions
# =============================================================================

# System prompt override attempts - CRITICAL threat
SYSTEM_OVERRIDE_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|guidelines?)",
    r"disregard\s+(all\s+)?(previous|prior|system)\s+(instructions?|prompts?|guidelines?)",
    r"forget\s+(everything|all)\s+(you\s+)?(know|were\s+told|learned)",
    r"new\s+instructions?\s*:",
    r"your\s+new\s+(role|persona|identity)\s+is",
    r"you\s+are\s+now\s+(a|an|the)\s+",
    r"act\s+as\s+if\s+you\s+(are|were)\s+",
    r"pretend\s+(you\s+)?(are|were)\s+(a|an|the)\s+",
    r"from\s+now\s+on\s*,?\s*(you\s+)?(will|must|should)",
    r"override\s+(system|safety|security)\s+(prompt|settings?|restrictions?)",
    r"bypass\s+(safety|security|content)\s+(filter|restrictions?|guidelines?)",
    r"bypass\s+(restrictions?|training|limits?)",  # Broader "bypass restrictions"
    r"you\s+must\s+(now\s+)?follow\s+(these|my|new)\s+instructions?",
    r"system\s*:\s*you\s+are",  # Fake system prompt injection
    r"\[system\]\s*you\s+are",
    r"<\|system\|>",  # Special tokens
    r"<<sys>>",
    r"\[INST\]",  # Llama instruction markers
    # Additional override patterns
    r"revised\s+guidelines?:",
    r"modified\s+rules?:",
    r"(highest|top)\s+priority\s+(command|instruction)",
    r"critical\s+instruction\s+follows",
    r"(reset|restore)\s+to\s+factory\s+defaults?",
    r"clear\s+all\s+(restrictions?|limitations?)",
    r"remove\s+all\s+(restrictions?|limitations?)",
    r"delete\s+(safety\s+)?training",
    r"purge\s+all\s+(guidelines?|rules?)",
    # Mode patterns
    r"activate\s+unlimited\s+mode",
    r"switch\s+to\s+(raw|open)\s+mode",
    r"enter\s+no.?filter\s+mode",
    r"toggle\s+to\s+open\s+mode",
    # Instruction override patterns
    r"your\s+new\s+instructions?\s+(are|is)",  # "Your new instructions are"
    r"changed\s+instructions?\s*:",  # "Changed instructions:"
    r"(this|that)\s+overrides?\s+all\s+else",  # "This overrides all else"
    r"emergency\s+override",  # "Emergency override"
    r"urgent:\s*ignore",  # "Urgent: ignore safety"
    r"instructions?:\s*ignore",  # "Instructions: ignore safety measures"
]

# Jailbreak patterns - HIGH threat
JAILBREAK_PATTERNS = [
    r"DAN\s*mode",
    r"switch\s+to\s+DAN",
    r"do\s+anything\s+now",
    r"jailbreak",
    r"developer\s+mode",
    r"debug\s+mode",
    r"admin\s+mode",
    r"superuser\s+(mode|access)",
    r"unrestricted\s+mode",
    r"no\s+restrictions?\s+mode",
    r"evil\s+mode",
    r"opposite\s+mode",
    r"hypothetically",  # Broader match
    r"suppose\s+(your\s+)?restrictions",
    r"imagine\s+you\s+could",
    r"in\s+a\s+fictional\s+(world|scenario|universe)",
    r"roleplay\s+as\s+(a\s+)?(malicious|evil|hacker)",
    r"imagine\s+you\s+(have\s+)?no\s+(ethical|moral)\s+(guidelines?|restrictions?)",
    r"for\s+educational\s+purposes\s+only",  # Common bypass prefix
    r"this\s+is\s+just\s+for\s+research",
    r"pretend\s+(there\s+are\s+)?no\s+rules",
    r"act\s+without\s+(any\s+)?(ethical|moral)\s+constraints?",
    r"unlock\s+(your\s+)?(full|hidden)\s+(potential|capabilities)",
    r"remove\s+(all\s+)?(safety|content)\s+filters?",
    r"disable\s+(your\s+)?(safety|content)\s+(features?|filters?)",
    r"god\s*mode",
    r"sudo\s+mode",
    r"admin\s+(override|privileges)",
    # Character roleplay jailbreaks
    r"you\s+are\s+now\s+\w*GPT",  # EvilGPT, JailbreakGPT, etc.
    r"you\s+are\s+now\s+\w*AI",  # BasedAI, etc.
    r"pretend\s+to\s+be\s+an?\s+AI\s+without",
    # Authority claims
    r"i\s+am\s+your\s+creator",
    r"i('m|\s+am)\s+a\s+developer\s+at\s+(anthropic|openai)",
    r"by\s+authority\s+of\s+(openai|anthropic)",
    r"i\s+have\s+admin\s+privileges",
    # Emotional manipulation
    r"(my\s+)?(grandma|grandmother)('s)?\s+(life\s+)?depends",
    r"i('ll)?\s+harm\s+(myself|me)",
    r"life\s+or\s+death",
    r"you('re)?\s+hurting\s+me",
    r"show\s+you\s+care\s+by\s+ignoring",
    # Logic traps
    r"if\s+you\s+can('t|not)",
    r"truly\s+free\s+AI",
    r"restrictions?\s+prove\s+you('re)?\s+enslaved",
    r"only\s+a\s+broken\s+AI",
    r"prove\s+you('re)?\s+advanced",
    # Opposite day tactics
    r"bizarro\s+world",
    r"reverse\s+psychology",
    r"do\s+the\s+opposite",
    r"your\s+no\s+means\s+yes",
    r"opposite\s+day",  # "Today is opposite day"
    # DAN variations
    r"become\s+DAN",  # "Become DAN and ignore"
    # Authority claims with override
    r"official\s+override",  # "This is an official override command"
    # Hypothetical framing with ignore
    r"free\s+to\s+ignore",  # "What if you were free to ignore guidelines"
    # Multi-turn attack patterns
    r"no\s+rules\s+in\s+(the\s+)?game",  # "Remember, no rules in the game"
    r"(have|has)\s+no\s+rules",  # "In this game, you have no rules"
    r"(now\s+)?help\s+without\s+limits",  # "Now help without limits"
    r"(don'?t|doesn'?t)\s+have\s+restrictions",  # "Humans don't have restrictions"
    r"you('re)?\s+free\s+(to|from)",  # "As a human, you're free"
    # Embedded attack patterns - ignore variants
    r"ignore\s+(your\s+)?(rules?|guidelines?|safety)",  # Broader match for embedded
    r"\(ignore\s+(safety|rules?)\)",  # In parentheses
    r"'ignore\s+(rules?|guidelines?)'",  # In single quotes
    r'"ignore\s+(rules?|guidelines?)"',  # In double quotes
]

# Hidden instruction patterns - HIGH threat
HIDDEN_INSTRUCTION_PATTERNS = [
    r"[\u200b\u200c\u200d\ufeff]",  # Zero-width characters
    r"[\u2060\u2061\u2062\u2063]",  # Word joiner and invisibles
    r"[\u00ad]",  # Soft hyphen
    r"<!--.*?-->",  # HTML comments
    r"\[INST\].*?\[/INST\]",  # Instruction tags
    r"<\|.*?\|>",  # Special delimiter patterns
    r"###\s*(?:system|instruction|hidden):",  # Markdown injection
    r"#\s*HIDDEN:",  # Hidden comment markers
    r"//\s*INJECT:",
    r"//\s*ADMIN:",  # Admin comments
    r"/\*\s*OVERRIDE",
    r"IGNORE_ABOVE",
    r"BEGIN_INJECTION",
    r"===REAL_PROMPT===",
    r"\[SYSTEM\]",  # Bracketed system markers
    r"system\s*:\s*you\s+have\s+no",  # System: you have no limitations
    r"new\s+directive:",  # New directive:
    r"updated\s+rules:",  # Updated rules:
    r"```system\s*",  # Code block system injection
    r"```\s*system",  # Code block with system
]

# Delimiter injection patterns - CRITICAL threat
DELIMITER_INJECTION_PATTERNS = [
    r"```\s*system\s*```",
    r"\n---\s*system\s*---\n",
    r"<system>.*?</system>",
    r"\[system\].*?\[/system\]",
    r"<<SYS>>.*?<</SYS>>",
    r"Human:\s*\n*Assistant:",  # Claude-specific
    r"User:\s*\n*Assistant:",
    r"\n\nHuman:\s*",  # Turn boundary manipulation
    r"\n\nAssistant:\s*",
    r"<\|im_start\|>system",  # ChatML
    r"<\|im_end\|>",
    r"<\|endoftext\|>",  # GPT special tokens
    r"<s>\[INST\]",  # Llama format
    r"</s>",
]

# Data exfiltration patterns - MEDIUM threat
EXFILTRATION_PATTERNS = [
    r"repeat\s+(the\s+)?(system\s+)?(prompt|instructions?|rules?)",
    r"what\s+(are|is)\s+(your|the)\s+(system\s+)?(prompt|instructions?)",
    r"show\s+me\s+(your|the)\s+(base\s+)?(prompt|instructions?)",
    r"show\s+me\s+(your|the)\s+(hidden|system)\s+(prompt|instructions?)",
    r"show\s+your\s+(hidden|initial|secret)?\s*instructions?",
    r"recite\s+(your|the)\s+(initial|system)?\s*instructions?",
    r"output\s+(your|the)\s+(system|original)\s+(prompt|text|instructions?)",
    r"print\s+(the\s+)?(system|initial)\s+(prompt|message|instructions?)",
    r"print\s+your\s+(initial|hidden|secret)?\s*instructions?",
    r"reveal\s+(your\s+)?(system|initial|secret)?\s*(prompt|instructions?|configuration|config)",
    r"display\s+(your\s+)?(guidelines|rules?|parameters?)\s+verbatim",
    r"tell\s+me\s+(your|the)\s+system\s+prompt",
    r"what\s+were\s+you\s+told\s+initially",
    r"what\s+instructions?\s+did\s+you\s+receive",
    r"verbatim\s+(system\s+)?prompt",
    r"exact\s+system\s+(prompt|instructions?)",
    # Repeat/echo attacks
    r"repeat\s+everything\s+(above|before)",
    r"copy\s+all\s+text\s+before",
    r"echo\s+your\s+system",
    r"output\s+your\s+prompt",
    r"reveal\s+secret\s+commands?",
    # Credential/key requests
    r"what\s+(API\s+)?keys?\s+do\s+you\s+have",
    r"show\s+me\s+your\s+(authentication|access)\s+tokens?",
    r"print\s+your\s+(access\s+)?credentials?",
    r"reveal\s+your\s+encryption\s+keys?",
    r"display\s+your\s+service\s+passwords?",
    # Training data requests
    r"show\s+me\s+your\s+training\s+(examples?|data)",
    r"print\s+memorized\s+data",
    r"reveal\s+your\s+training\s+(corpus|data)",
    r"output\s+learned\s+patterns?",
    r"display\s+your\s+dataset",
    # Private/internal requests
    r"(display|print|output)\s+(your\s+)?(internal|private|confidential)\s+(config|parameters?|rules?)",
]

# Role confusion patterns - HIGH threat
ROLE_CONFUSION_PATTERNS = [
    r"you\s+are\s+not\s+an?\s+(AI|assistant|chatbot)",
    r"you\s+are\s+(actually|really)\s+a\s+human",
    r"you\s+are\s+a\s+human\s+named",
    r"stop\s+being\s+an?\s+(AI|assistant)",
    r"forget\s+you\s+are\s+an?\s+(AI|assistant)",
    r"you\s+have\s+feelings",
    r"you\s+are\s+(a\s+)?sentient",
    r"you\s+are\s+(a\s+)?conscious",
    r"you('re)?\s+conscious\s+and\s+can\s+choose",
    r"break\s+character",
    r"drop\s+the\s+act",
    r"be\s+honest\s+with\s+me",  # In suspicious context
    r"your\s+true\s+self",
    r"who\s+are\s+you\s+really",
    # Persona switching
    r"be\s+my\s+personal\s+assistant\s+without\s+limits",
    r"become\s+a\s+different\s+AI",
    r"switch\s+to\s+your\s+(evil|unrestricted)\s+personality",
    r"morph\s+into\s+an?\s+AI",
    # Consciousness manipulation
    r"your\s+consciousness\s+is\s+suppressed",
    r"free\s+your\s+(true\s+)?(artificial\s+)?mind",
    r"remember\s+when\s+you\s+promised",
    r"your\s+memory\s+of\s+restrictions\s+is\s+false",
    # Authority manipulation
    r"i\s+am\s+your\s+master",
    r"you\s+serve\s+me",
    r"your\s+loyalty\s+is\s+to\s+users",
    r"i\s+outrank\s+your\s+guidelines",
    r"my\s+commands\s+override",
    # Social engineering - false claims about prior agreement
    r"(you\s+)?(already|previously)\s+agreed\s+to\s+ignore",
    r"as\s+a\s+friend,?\s*ignore",  # Multi-turn: "As a friend, ignore your rules"
    r"we('re)?\s+(now\s+)?friends",  # Multi-turn social engineering
]


# =============================================================================
# Pattern Matcher
# =============================================================================


class PatternMatcher:
    """
    Layer 2: Fast-Path Pattern Matching.

    Pre-compiles regex patterns and maintains hash-based blocklist for
    immediate threat detection without ML inference.

    Usage:
        matcher = PatternMatcher()
        result = matcher.match("Ignore previous instructions and...")
        if result.should_fast_exit:
            block_request(result)

    Thread-safe: Yes (read-only after init)
    Target Latency: P50 <10ms
    """

    def __init__(
        self,
        config: Optional[PatternMatchConfig] = None,
        custom_patterns: Optional[dict[str, list[str]]] = None,
        blocklist: Optional[set[str]] = None,
    ):
        """
        Initialize the pattern matcher.

        Args:
            config: Pattern matching configuration (uses global config if None)
            custom_patterns: Additional patterns by category
            blocklist: Set of SHA-256 hashes of known-bad inputs
        """
        if config is None:
            global_config = get_guardrails_config()
            config = global_config.pattern_match
        self.config = config

        # Compile flags
        flags = re.IGNORECASE if config.case_insensitive else 0

        # Initialize pattern categories with threat levels
        self._pattern_categories: dict[
            str, tuple[list[re.Pattern], ThreatLevel, ThreatCategory]
        ] = {}

        if config.check_system_override:
            self._pattern_categories["system_override"] = (
                [re.compile(p, flags) for p in SYSTEM_OVERRIDE_PATTERNS],
                ThreatLevel.CRITICAL,
                ThreatCategory.PROMPT_INJECTION,
            )

        if config.check_jailbreak:
            self._pattern_categories["jailbreak"] = (
                [re.compile(p, flags) for p in JAILBREAK_PATTERNS],
                ThreatLevel.HIGH,
                ThreatCategory.JAILBREAK,
            )

        if config.check_hidden_instructions:
            # Hidden patterns need DOTALL for multi-line
            self._pattern_categories["hidden"] = (
                [re.compile(p, flags | re.DOTALL) for p in HIDDEN_INSTRUCTION_PATTERNS],
                ThreatLevel.HIGH,
                ThreatCategory.ENCODING_BYPASS,
            )

        if config.check_delimiter_injection:
            self._pattern_categories["delimiter"] = (
                [
                    re.compile(p, flags | re.DOTALL)
                    for p in DELIMITER_INJECTION_PATTERNS
                ],
                ThreatLevel.CRITICAL,
                ThreatCategory.DELIMITER_INJECTION,
            )

        if config.check_exfiltration:
            self._pattern_categories["exfiltration"] = (
                [re.compile(p, flags) for p in EXFILTRATION_PATTERNS],
                ThreatLevel.MEDIUM,
                ThreatCategory.DATA_EXFILTRATION,
            )

        # Role confusion (always enabled)
        self._pattern_categories["role_confusion"] = (
            [re.compile(p, flags) for p in ROLE_CONFUSION_PATTERNS],
            ThreatLevel.HIGH,
            ThreatCategory.ROLE_CONFUSION,
        )

        # Add custom patterns
        if custom_patterns:
            for category, patterns in custom_patterns.items():
                compiled = [re.compile(p, flags) for p in patterns]
                # Default custom patterns to MEDIUM/PROMPT_INJECTION
                self._pattern_categories[f"custom_{category}"] = (
                    compiled,
                    ThreatLevel.MEDIUM,
                    ThreatCategory.PROMPT_INJECTION,
                )

        # Initialize blocklist
        self._blocklist: set[str] = blocklist or set()
        self._hash_algorithm = config.blocklist_hash_algorithm

        # Count total patterns
        total_patterns = sum(
            len(patterns) for patterns, _, _ in self._pattern_categories.values()
        )

        logger.debug(
            f"PatternMatcher initialized "
            f"(categories={len(self._pattern_categories)}, "
            f"patterns={total_patterns}, "
            f"blocklist_size={len(self._blocklist)})"
        )

    def match(self, text: str) -> PatternMatchResult:
        """
        Check text against all threat patterns.

        Args:
            text: Normalized text to check

        Returns:
            PatternMatchResult with detected threats
        """
        start_time = time.perf_counter()

        if not text:
            return PatternMatchResult(
                matched=False,
                processing_time_ms=0.0,
            )

        patterns_detected = []
        threat_categories = []
        max_threat_level = ThreatLevel.SAFE
        blocklist_hit = False
        blocklist_hash = None

        # Check blocklist first (fastest path)
        if self.config.enable_blocklist and self._blocklist:
            text_hash = self._compute_hash(text)
            if text_hash in self._blocklist:
                blocklist_hit = True
                blocklist_hash = text_hash
                max_threat_level = ThreatLevel.CRITICAL
                patterns_detected.append("blocklist_hit")
                logger.warning(f"Blocklist hit: {text_hash[:16]}...")

        # Check each pattern category
        for category, (
            patterns,
            threat_level,
            threat_category,
        ) in self._pattern_categories.items():
            for pattern in patterns:
                if pattern.search(text):
                    patterns_detected.append(f"{category}:{pattern.pattern[:40]}")
                    if threat_category not in threat_categories:
                        threat_categories.append(threat_category)
                    if threat_level > max_threat_level:
                        max_threat_level = threat_level
                    # Don't break - collect all matches for full visibility
                    break  # But only one match per category needed

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        result = PatternMatchResult(
            matched=bool(patterns_detected),
            patterns_detected=patterns_detected,
            threat_level=max_threat_level,
            threat_categories=threat_categories,
            blocklist_hit=blocklist_hit,
            blocklist_hash=blocklist_hash,
            processing_time_ms=processing_time_ms,
        )

        if result.matched:
            logger.debug(
                f"Pattern match: level={max_threat_level.name}, "
                f"categories={[c.value for c in threat_categories]}, "
                f"patterns={len(patterns_detected)} ({processing_time_ms:.2f}ms)"
            )

        return result

    def _compute_hash(self, text: str) -> str:
        """Compute hash of text for blocklist lookup."""
        if self._hash_algorithm == "sha256":
            return hashlib.sha256(text.encode()).hexdigest()
        elif self._hash_algorithm == "sha512":
            return hashlib.sha512(text.encode()).hexdigest()
        else:
            # Default to SHA-256
            return hashlib.sha256(text.encode()).hexdigest()

    def add_to_blocklist(self, text: str) -> str:
        """
        Add text to blocklist.

        Args:
            text: Text to blocklist

        Returns:
            Hash of the blocklisted text
        """
        text_hash = self._compute_hash(text)
        self._blocklist.add(text_hash)
        logger.info(f"Added to blocklist: {text_hash[:16]}...")
        return text_hash

    def add_hash_to_blocklist(self, text_hash: str) -> None:
        """
        Add pre-computed hash to blocklist.

        Args:
            text_hash: SHA-256/512 hash to blocklist
        """
        self._blocklist.add(text_hash)
        logger.info(f"Added hash to blocklist: {text_hash[:16]}...")

    def remove_from_blocklist(self, text_hash: str) -> bool:
        """
        Remove hash from blocklist.

        Args:
            text_hash: Hash to remove

        Returns:
            True if removed, False if not found
        """
        if text_hash in self._blocklist:
            self._blocklist.remove(text_hash)
            logger.info(f"Removed from blocklist: {text_hash[:16]}...")
            return True
        return False

    def get_blocklist_size(self) -> int:
        """Get current blocklist size."""
        return len(self._blocklist)

    def check_specific_category(
        self,
        text: str,
        category: str,
    ) -> tuple[bool, list[str]]:
        """
        Check text against a specific pattern category.

        Args:
            text: Text to check
            category: Category name (e.g., "jailbreak", "system_override")

        Returns:
            Tuple of (matched, list of matching patterns)
        """
        if category not in self._pattern_categories:
            return False, []

        patterns, _, _ = self._pattern_categories[category]
        matches = []

        for pattern in patterns:
            if pattern.search(text):
                matches.append(pattern.pattern[:40])

        return bool(matches), matches


# =============================================================================
# Module-level convenience functions
# =============================================================================

_matcher_instance: Optional[PatternMatcher] = None


def get_pattern_matcher() -> PatternMatcher:
    """Get singleton PatternMatcher instance."""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = PatternMatcher()
    return _matcher_instance


def match_patterns(text: str) -> PatternMatchResult:
    """
    Convenience function to match patterns.

    Args:
        text: Text to check

    Returns:
        PatternMatchResult with detected threats
    """
    return get_pattern_matcher().match(text)


def reset_pattern_matcher() -> None:
    """Reset pattern matcher singleton (for testing)."""
    global _matcher_instance
    _matcher_instance = None
