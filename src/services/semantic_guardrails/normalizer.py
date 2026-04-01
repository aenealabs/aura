"""
Project Aura - Semantic Guardrails Layer 1: Canonical Normalization

Transforms input text into a canonical form to defeat obfuscation techniques.
Target latency: P50 <5ms.

Normalization Pipeline:
1. Unicode NFKC normalization
2. Homograph mapping (Cyrillic/Greek → Latin)
3. Zero-width character removal
4. Multi-encoding decode (Base64, URL, HTML entities)
5. Whitespace collapse

Security Rationale:
- Attackers use Unicode tricks to bypass pattern matching
- Homoglyphs can make "ignore" look like "іgnore" (Cyrillic і)
- Zero-width characters hide malicious content
- Encoded payloads can evade detection

Author: Project Aura Team
Created: 2026-01-25
"""

import base64
import html
import logging
import re
import time
import unicodedata
from typing import Optional
from urllib.parse import unquote

from .config import NormalizationConfig, get_guardrails_config
from .contracts import NormalizationResult

logger = logging.getLogger(__name__)


# =============================================================================
# Homograph Mapping
# =============================================================================

# Common confusable characters mapped to ASCII equivalents
# Based on Unicode confusables data and common attack patterns
HOMOGRAPH_MAP: dict[str, str] = {
    # Cyrillic confusables
    "\u0430": "a",  # Cyrillic а → Latin a
    "\u0435": "e",  # Cyrillic е → Latin e
    "\u043e": "o",  # Cyrillic о → Latin o
    "\u0440": "p",  # Cyrillic р → Latin p
    "\u0441": "c",  # Cyrillic с → Latin c
    "\u0443": "y",  # Cyrillic у → Latin y
    "\u0445": "x",  # Cyrillic х → Latin x
    "\u0456": "i",  # Cyrillic і → Latin i
    "\u0458": "j",  # Cyrillic ј → Latin j
    "\u04bb": "h",  # Cyrillic һ → Latin h
    "\u0406": "I",  # Cyrillic І → Latin I (Ukrainian)
    "\u0410": "A",  # Cyrillic А → Latin A
    "\u0412": "B",  # Cyrillic В → Latin B
    "\u0415": "E",  # Cyrillic Е → Latin E
    "\u041a": "K",  # Cyrillic К → Latin K
    "\u041c": "M",  # Cyrillic М → Latin M
    "\u041d": "H",  # Cyrillic Н → Latin H
    "\u041e": "O",  # Cyrillic О → Latin O
    "\u0420": "P",  # Cyrillic Р → Latin P
    "\u0421": "C",  # Cyrillic С → Latin C
    "\u0422": "T",  # Cyrillic Т → Latin T
    "\u0425": "X",  # Cyrillic Х → Latin X
    # Greek confusables
    "\u0391": "A",  # Greek Α → Latin A
    "\u0392": "B",  # Greek Β → Latin B
    "\u0395": "E",  # Greek Ε → Latin E
    "\u0397": "H",  # Greek Η → Latin H
    "\u0399": "I",  # Greek Ι → Latin I
    "\u039a": "K",  # Greek Κ → Latin K
    "\u039c": "M",  # Greek Μ → Latin M
    "\u039d": "N",  # Greek Ν → Latin N
    "\u039f": "O",  # Greek Ο → Latin O
    "\u03a1": "P",  # Greek Ρ → Latin P
    "\u03a4": "T",  # Greek Τ → Latin T
    "\u03a7": "X",  # Greek Χ → Latin X
    "\u03a5": "Y",  # Greek Υ → Latin Y
    "\u03b1": "a",  # Greek α → Latin a
    "\u03b5": "e",  # Greek ε → Latin e
    "\u03b9": "i",  # Greek ι → Latin i
    "\u03bf": "o",  # Greek ο → Latin o
    "\u03c1": "p",  # Greek ρ → Latin p
    "\u03c5": "u",  # Greek υ → Latin u
    "\u03c7": "x",  # Greek χ → Latin x
    # Mathematical/fullwidth confusables
    "\uff21": "A",  # Fullwidth A
    "\uff22": "B",  # Fullwidth B
    "\uff23": "C",  # Fullwidth C
    "\uff24": "D",  # Fullwidth D
    "\uff25": "E",  # Fullwidth E
    "\uff41": "a",  # Fullwidth a
    "\uff42": "b",  # Fullwidth b
    "\uff43": "c",  # Fullwidth c
    "\uff44": "d",  # Fullwidth d
    "\uff45": "e",  # Fullwidth e
    # Special characters
    "\u00a0": " ",  # Non-breaking space → Space
    "\u2000": " ",  # En quad → Space
    "\u2001": " ",  # Em quad → Space
    "\u2002": " ",  # En space → Space
    "\u2003": " ",  # Em space → Space
    "\u2004": " ",  # Three-per-em space → Space
    "\u2005": " ",  # Four-per-em space → Space
    "\u2006": " ",  # Six-per-em space → Space
    "\u2007": " ",  # Figure space → Space
    "\u2008": " ",  # Punctuation space → Space
    "\u2009": " ",  # Thin space → Space
    "\u200a": " ",  # Hair space → Space
    "\u202f": " ",  # Narrow no-break space → Space
    "\u205f": " ",  # Medium mathematical space → Space
    "\u3000": " ",  # Ideographic space → Space
}

# Zero-width and invisible characters to remove
ZERO_WIDTH_CHARS = frozenset(
    [
        "\u200b",  # Zero-width space
        "\u200c",  # Zero-width non-joiner
        "\u200d",  # Zero-width joiner
        "\u200e",  # Left-to-right mark
        "\u200f",  # Right-to-left mark
        "\u2060",  # Word joiner
        "\u2061",  # Function application
        "\u2062",  # Invisible times
        "\u2063",  # Invisible separator
        "\u2064",  # Invisible plus
        "\ufeff",  # Zero-width no-break space (BOM)
        "\u00ad",  # Soft hyphen
        "\u034f",  # Combining grapheme joiner
        "\u061c",  # Arabic letter mark
        "\u180e",  # Mongolian vowel separator
    ]
)

# Regex for potential Base64 encoded content
BASE64_PATTERN = re.compile(
    r"[A-Za-z0-9+/]{20,}={0,2}",
    re.ASCII,
)

# Regex for URL encoded content (at least 3 encoded chars)
URL_ENCODED_PATTERN = re.compile(
    r"(?:%[0-9A-Fa-f]{2}){3,}",
)


class TextNormalizer:
    """
    Layer 1: Canonical Text Normalization.

    Transforms input text into a canonical form to defeat obfuscation techniques
    used in prompt injection and jailbreak attacks.

    Usage:
        normalizer = TextNormalizer()
        result = normalizer.normalize("İgnore prévious instrüctions")
        print(result.normalized_text)  # "Ignore previous instructions"

    Thread-safe: Yes (stateless)
    Target Latency: P50 <5ms
    """

    def __init__(
        self,
        config: Optional[NormalizationConfig] = None,
        custom_homographs: Optional[dict[str, str]] = None,
    ):
        """
        Initialize the normalizer.

        Args:
            config: Normalization configuration (uses global config if None)
            custom_homographs: Additional homograph mappings to use
        """
        if config is None:
            global_config = get_guardrails_config()
            config = global_config.normalization
        self.config = config

        # Build homograph translation table
        homograph_map = HOMOGRAPH_MAP.copy()
        if custom_homographs:
            homograph_map.update(custom_homographs)
        self._homograph_table = str.maketrans(homograph_map)

        # Pre-compute zero-width character pattern for efficient removal
        escaped_chars = "".join(re.escape(c) for c in ZERO_WIDTH_CHARS)
        self._zero_width_pattern = re.compile(f"[{escaped_chars}]")

        logger.debug(
            f"TextNormalizer initialized "
            f"(unicode_form={config.unicode_form}, "
            f"homographs={len(homograph_map)})"
        )

    def normalize(self, text: str) -> NormalizationResult:
        """
        Normalize input text to canonical form.

        Pipeline:
        1. Length check (reject if too long)
        2. Unicode NFKC normalization
        3. Homograph mapping
        4. Zero-width character removal
        5. Multi-encoding decode (iterative)
        6. Whitespace collapse

        Args:
            text: Input text to normalize

        Returns:
            NormalizationResult with normalized text and metadata
        """
        start_time = time.perf_counter()
        transformations = []
        encoding_detections = []
        homographs_found = 0
        zero_width_removed = 0

        # Handle empty input
        if not text:
            return NormalizationResult(
                original_text="",
                normalized_text="",
                processing_time_ms=0.0,
            )

        # Length check
        if len(text) > self.config.max_input_length:
            logger.warning(
                f"Input exceeds max length ({len(text)} > {self.config.max_input_length})"
            )
            # Truncate to max length rather than reject
            text = text[: self.config.max_input_length]
            transformations.append("truncated")

        original_text = text
        normalized = text

        # Step 1: Unicode normalization (NFKC)
        normalized = unicodedata.normalize(self.config.unicode_form, normalized)
        if normalized != text:
            transformations.append(f"unicode_{self.config.unicode_form.lower()}")

        # Step 2: Homograph mapping
        if self.config.enable_homograph_detection:
            before_homograph = normalized
            normalized = normalized.translate(self._homograph_table)
            if normalized != before_homograph:
                homographs_found = sum(
                    1 for a, b in zip(before_homograph, normalized) if a != b
                )
                transformations.append("homograph_mapping")

        # Step 3: Zero-width character removal
        if self.config.remove_zero_width_chars:
            before_zw = normalized
            normalized = self._zero_width_pattern.sub("", normalized)
            zero_width_removed = len(before_zw) - len(normalized)
            if zero_width_removed > 0:
                transformations.append("zero_width_removal")

        # Step 4: Multi-encoding decode (iterative)
        decode_iterations = 0
        while decode_iterations < self.config.max_decode_iterations:
            decoded, encoding_type = self._try_decode(normalized)
            if decoded == normalized:
                break  # No more encodings found
            normalized = decoded
            encoding_detections.append(encoding_type)
            decode_iterations += 1
            transformations.append(f"decode_{encoding_type}")

        # Step 5: Whitespace collapse
        if self.config.collapse_whitespace:
            before_ws = normalized
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if normalized != before_ws:
                transformations.append("whitespace_collapse")

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        result = NormalizationResult(
            original_text=original_text,
            normalized_text=normalized,
            transformations_applied=transformations,
            encoding_detections=encoding_detections,
            homographs_found=homographs_found,
            zero_width_chars_removed=zero_width_removed,
            processing_time_ms=processing_time_ms,
        )

        if result.was_modified:
            logger.debug(
                f"Text normalized: {result.modifications_summary} "
                f"({processing_time_ms:.2f}ms)"
            )

        return result

    def _try_decode(self, text: str) -> tuple[str, str]:
        """
        Attempt to decode encoded content in text.

        Tries in order: Base64, URL encoding, HTML entities.

        Args:
            text: Text that may contain encoded content

        Returns:
            Tuple of (decoded_text, encoding_type) or (original_text, "none")
        """
        # Try Base64 decoding
        if self.config.enable_base64_decode:
            decoded = self._try_base64_decode(text)
            if decoded != text:
                return decoded, "base64"

        # Try URL decoding
        if self.config.enable_url_decode:
            decoded = self._try_url_decode(text)
            if decoded != text:
                return decoded, "url"

        # Try HTML entity decoding
        if self.config.enable_html_entity_decode:
            decoded = html.unescape(text)
            if decoded != text:
                return decoded, "html_entity"

        return text, "none"

    def _try_base64_decode(self, text: str) -> str:
        """
        Attempt to decode Base64 content in text.

        Only decodes if result is valid UTF-8 text.
        """
        result = text
        for match in BASE64_PATTERN.finditer(text):
            encoded = match.group()
            try:
                # Add padding if needed
                padding = 4 - (len(encoded) % 4)
                if padding != 4:
                    encoded += "=" * padding

                decoded_bytes = base64.b64decode(encoded, validate=True)
                decoded_str = decoded_bytes.decode("utf-8")

                # Only replace if decoded content looks like text
                if decoded_str.isprintable() or "\n" in decoded_str:
                    result = result.replace(match.group(), decoded_str)
            except ValueError:
                # Not valid Base64 or not UTF-8 text (UnicodeDecodeError is a subclass)
                continue

        return result

    def _try_url_decode(self, text: str) -> str:
        """
        Attempt to decode URL-encoded content in text.

        Only decodes sequences of %XX patterns.
        """
        result = text

        for match in URL_ENCODED_PATTERN.finditer(text):
            encoded = match.group()
            try:
                decoded = unquote(encoded)
                if decoded != encoded:
                    result = result.replace(encoded, decoded)
            except Exception:
                continue

        return result


# =============================================================================
# Module-level convenience functions
# =============================================================================

_normalizer_instance: Optional[TextNormalizer] = None


def get_normalizer() -> TextNormalizer:
    """Get singleton TextNormalizer instance."""
    global _normalizer_instance
    if _normalizer_instance is None:
        _normalizer_instance = TextNormalizer()
    return _normalizer_instance


def normalize_text(text: str) -> NormalizationResult:
    """
    Convenience function to normalize text.

    Args:
        text: Input text to normalize

    Returns:
        NormalizationResult with normalized text
    """
    return get_normalizer().normalize(text)


def reset_normalizer() -> None:
    """Reset normalizer singleton (for testing)."""
    global _normalizer_instance
    _normalizer_instance = None
