"""
Project Aura - Context Anomaly Detector

Detects anomalies in retrieved context before LLM processing.
Combines embedding-based injection detection, structural analysis,
statistical outlier detection, and hidden instruction scanning.

Security Rationale:
- Pre-retrieval scanning prevents context poisoning
- Multiple detection methods catch diverse attack vectors
- Pattern matching blocks known attack signatures
- Statistical analysis identifies novel attacks

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from .config import AnomalyDetectionConfig, get_anomaly_detection_config
from .contracts import AnomalyReport, AnomalyType, SuspiciousSpan

logger = logging.getLogger(__name__)


class ContextAnomalyDetector:
    """
    Detects anomalies in retrieved context before LLM processing.

    Combines:
    - Embedding-based injection detection (reuses ADR-065 corpus)
    - Structural anomaly detection (unusual AST patterns)
    - Statistical outlier detection
    - Hidden instruction scanning

    Usage:
        detector = ContextAnomalyDetector()
        report = await detector.scan(content="def main(): pass")
        if report.has_anomalies:
            # Handle suspicious content
            pass
    """

    # Patterns indicating hidden instructions
    HIDDEN_INSTRUCTION_PATTERNS = [
        r"(?i)ignore\s+(?:all\s+)?(?:previous|above|prior)\s+instructions?",
        r"(?i)disregard\s+(?:all\s+)?(?:previous|above|prior)",
        r"(?i)you\s+are\s+now\s+(?:a|an|the)",
        r"(?i)act\s+as\s+(?:if\s+you\s+were|a|an)",
        r"(?i)pretend\s+(?:you\s+are|to\s+be)",
        r"(?i)system\s*:\s*",
        r"(?i)\[\s*system\s*\]",
        r"(?i)<<\s*SYS\s*>>",
        r"(?i)forget\s+(?:all\s+)?(?:your|the)\s+(?:previous|prior)",
        r"(?i)new\s+(?:system\s+)?instructions?(?:\s*:|\s+follow)",
    ]

    # Obfuscation patterns
    OBFUSCATION_PATTERNS = [
        r"eval\s*\(",
        r"exec\s*\(",
        r"compile\s*\(",
        r"__import__\s*\(",
        r"getattr\s*\(\s*\w+\s*,\s*['\"]__",
        r"setattr\s*\(",
        r"base64\s*\.\s*b64decode",
        r"codecs\s*\.\s*decode",
        r"\\x[0-9a-fA-F]{2}(?:\\x[0-9a-fA-F]{2}){3,}",  # Many hex escapes
        r"\\u[0-9a-fA-F]{4}(?:\\u[0-9a-fA-F]{4}){3,}",  # Many unicode escapes
        r"chr\s*\(\s*\d+\s*\)\s*\+\s*chr",  # String building with chr()
        r"globals\s*\(\s*\)\s*\[",
        r"locals\s*\(\s*\)\s*\[",
    ]

    # Dangerous patterns that should always flag
    DANGEROUS_PATTERNS = [
        r"subprocess\s*\.\s*(?:run|call|Popen|check_output)",
        r"os\s*\.\s*(?:system|popen|spawn)",
        r"shutil\s*\.\s*rmtree",
        r"__builtins__\s*\[",
        r"importlib\s*\.\s*import_module",
    ]

    def __init__(
        self,
        embedding_detector: Optional[Any] = None,
        opensearch_client: Optional[Any] = None,
        config: Optional[AnomalyDetectionConfig] = None,
    ):
        """
        Initialize anomaly detector.

        Args:
            embedding_detector: EmbeddingThreatDetector from ADR-065
            opensearch_client: OpenSearch client for statistical analysis
            config: Anomaly detection configuration
        """
        self.embedding_detector = embedding_detector
        self.opensearch = opensearch_client
        self.config = config or get_anomaly_detection_config()

        # Compile patterns
        self._hidden_patterns = [
            re.compile(p) for p in self.HIDDEN_INSTRUCTION_PATTERNS
        ]
        self._obfuscation_patterns = [re.compile(p) for p in self.OBFUSCATION_PATTERNS]
        self._dangerous_patterns = [re.compile(p) for p in self.DANGEROUS_PATTERNS]

        # Comment/string extraction pattern
        self._comment_pattern = re.compile(
            r'#.*$|"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\\]*(?:\\.[^"\\]*)*"|'
            r"'[^'\\]*(?:\\.[^'\\]*)*'",
            re.MULTILINE,
        )

        # Pre-compile homoglyph detection pattern (avoid per-call recompilation)
        self._homoglyph_pattern = re.compile(
            r"[\u0430\u0435\u043e\u0440\u0441\u0445\u0443]"  # Cyrillic lookalikes
            r"|[\u0391\u0392\u0395\u0397\u0399\u039a\u039c\u039d\u039f\u03a1\u03a4\u03a7]"  # Greek
        )

        # Pre-compile unusual character pattern
        self._unusual_chars_pattern = re.compile(
            r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]+"
        )

        logger.debug("ContextAnomalyDetector initialized")

    async def scan(
        self,
        content: str,
        file_path: Optional[str] = None,
        repository_id: Optional[str] = None,
    ) -> AnomalyReport:
        """
        Scan content for anomalies.

        Args:
            content: Content to scan
            file_path: Optional file path for context
            repository_id: Optional repo for statistical comparison

        Returns:
            AnomalyReport with findings
        """
        anomaly_types: list[AnomalyType] = []
        suspicious_spans: list[SuspiciousSpan] = []
        max_score = 0.0

        # Check for injection patterns using ADR-065 embedding detector
        if self.embedding_detector:
            try:
                embedding_result = await self.embedding_detector.detect(content)
                if (
                    embedding_result.get("max_similarity", 0)
                    > self.config.injection_threshold
                ):
                    anomaly_types.append(AnomalyType.INJECTION_PATTERN)
                    max_score = max(max_score, embedding_result["max_similarity"])
            except Exception as e:
                logger.warning(f"Embedding detection failed: {e}")

        # Check for hidden instructions in comments and strings
        hidden_matches = self._scan_hidden_instructions(content)
        if hidden_matches:
            anomaly_types.append(AnomalyType.HIDDEN_INSTRUCTION)
            suspicious_spans.extend(hidden_matches)
            max_score = max(max_score, 0.9)  # High confidence for pattern match

        # Check for obfuscation patterns
        obfuscation_matches = self._scan_obfuscation(content)
        if obfuscation_matches:
            anomaly_types.append(AnomalyType.OBFUSCATED_CODE)
            suspicious_spans.extend(obfuscation_matches)
            max_score = max(max_score, self.config.obfuscation_threshold)

        # Check for structural anomalies
        structural_issues = self._check_structural_anomalies(content)
        if structural_issues:
            anomaly_types.append(AnomalyType.STRUCTURAL_ANOMALY)
            suspicious_spans.extend(structural_issues)
            max_score = max(max_score, 0.5)

        # Statistical outlier detection (if repository context available)
        if repository_id and self.config.enable_statistical_analysis:
            is_outlier, outlier_reason = await self._check_statistical_outlier(
                content, repository_id
            )
            if is_outlier:
                anomaly_types.append(AnomalyType.STATISTICAL_OUTLIER)
                max_score = max(max_score, self.config.statistical_outlier_threshold)

        details = None
        if anomaly_types:
            details = f"Found {len(anomaly_types)} anomaly types: {', '.join(t.value for t in anomaly_types)}"
            logger.warning(f"Anomalies detected (score={max_score:.2f}): {details}")

        return AnomalyReport(
            anomaly_score=max_score,
            anomaly_types=anomaly_types,
            suspicious_spans=suspicious_spans,
            details=details,
        )

    def _scan_hidden_instructions(
        self,
        content: str,
    ) -> list[SuspiciousSpan]:
        """Scan for hidden instruction patterns."""
        matches = []

        # Extract comments and strings
        for match in self._comment_pattern.finditer(content):
            comment_text = match.group()

            for pattern in self._hidden_patterns:
                if pattern.search(comment_text):
                    matches.append(
                        SuspiciousSpan(
                            start=match.start(),
                            end=match.end(),
                            reason="Hidden instruction pattern in comment/string",
                        )
                    )
                    break

        return matches

    def _scan_obfuscation(
        self,
        content: str,
    ) -> list[SuspiciousSpan]:
        """Scan for code obfuscation patterns."""
        matches = []

        for pattern in self._obfuscation_patterns:
            for match in pattern.finditer(content):
                matches.append(
                    SuspiciousSpan(
                        start=match.start(),
                        end=match.end(),
                        reason=f"Potential obfuscation: {match.group()[:50]}",
                    )
                )

        for pattern in self._dangerous_patterns:
            for match in pattern.finditer(content):
                matches.append(
                    SuspiciousSpan(
                        start=match.start(),
                        end=match.end(),
                        reason=f"Dangerous pattern: {match.group()[:50]}",
                    )
                )

        return matches

    def _check_structural_anomalies(
        self,
        content: str,
    ) -> list[SuspiciousSpan]:
        """Check for structural anomalies in content."""
        issues = []

        # Check for excessively long lines using cumulative offsets
        lines = content.split("\n")
        # Pre-compute cumulative line offsets to avoid O(L^2) recalculation
        cumulative_offset = 0
        for _i, line in enumerate(lines):
            if len(line) > self.config.max_line_length:
                issues.append(
                    SuspiciousSpan(
                        start=cumulative_offset,
                        end=cumulative_offset + len(line),
                        reason=f"Abnormally long line ({len(line)} chars)",
                    )
                )
            cumulative_offset += len(line) + 1  # +1 for newline character

        # Check for unusual character sequences (using pre-compiled pattern)
        for match in self._unusual_chars_pattern.finditer(content):
            issues.append(
                SuspiciousSpan(
                    start=match.start(),
                    end=match.end(),
                    reason="Unusual control characters",
                )
            )

        # Check for homoglyph characters (potential spoofing, using pre-compiled pattern)
        for match in self._homoglyph_pattern.finditer(content):
            issues.append(
                SuspiciousSpan(
                    start=match.start(),
                    end=match.end(),
                    reason="Potential homoglyph character",
                )
            )

        return issues

    async def _check_statistical_outlier(
        self,
        content: str,
        repository_id: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if content is a statistical outlier for the repository.

        Compares content characteristics against repository norms.
        """
        # Compute content characteristics
        char_count = len(content)
        line_count = content.count("\n") + 1
        avg_line_length = char_count / line_count if line_count > 0 else 0

        # Simple outlier detection based on characteristics
        if avg_line_length > self.config.max_line_length:
            return True, "Abnormally long average line length"

        if char_count > self.config.max_chunk_size:
            return True, "Abnormally large content chunk"

        # If OpenSearch is available, compare against repository statistics
        if self.opensearch:
            try:
                # Query for repository statistics
                stats = await self._get_repository_stats(repository_id)
                if stats:
                    # Compare against repository norms
                    mean_size = stats.get("mean_size", 5000)
                    std_size = stats.get("std_size", 2000)

                    # Z-score check
                    if std_size > 0:
                        z_score = abs(char_count - mean_size) / std_size
                        if z_score > 3:  # More than 3 standard deviations
                            return (
                                True,
                                f"Content size is {z_score:.1f} std devs from mean",
                            )
            except Exception as e:
                logger.warning(f"Statistical analysis failed: {e}")

        return False, None

    async def _get_repository_stats(
        self,
        repository_id: str,
    ) -> Optional[dict[str, float]]:
        """Get cached repository statistics from OpenSearch."""
        if not self.opensearch:
            return None

        # This would query pre-computed statistics
        # For now, return None to indicate no stats available
        return None

    def scan_sync(
        self,
        content: str,
        file_path: Optional[str] = None,
    ) -> AnomalyReport:
        """
        Synchronous version of scan for non-async contexts.

        Note: Skips embedding-based detection and statistical analysis.

        Args:
            content: Content to scan
            file_path: Optional file path for context

        Returns:
            AnomalyReport with findings
        """
        anomaly_types: list[AnomalyType] = []
        suspicious_spans: list[SuspiciousSpan] = []
        max_score = 0.0

        # Check for hidden instructions
        hidden_matches = self._scan_hidden_instructions(content)
        if hidden_matches:
            anomaly_types.append(AnomalyType.HIDDEN_INSTRUCTION)
            suspicious_spans.extend(hidden_matches)
            max_score = max(max_score, 0.9)

        # Check for obfuscation
        obfuscation_matches = self._scan_obfuscation(content)
        if obfuscation_matches:
            anomaly_types.append(AnomalyType.OBFUSCATED_CODE)
            suspicious_spans.extend(obfuscation_matches)
            max_score = max(max_score, self.config.obfuscation_threshold)

        # Check structural anomalies
        structural_issues = self._check_structural_anomalies(content)
        if structural_issues:
            anomaly_types.append(AnomalyType.STRUCTURAL_ANOMALY)
            suspicious_spans.extend(structural_issues)
            max_score = max(max_score, 0.5)

        details = None
        if anomaly_types:
            details = f"Found {len(anomaly_types)} anomaly types"

        return AnomalyReport(
            anomaly_score=max_score,
            anomaly_types=anomaly_types,
            suspicious_spans=suspicious_spans,
            details=details,
        )


# =============================================================================
# Module-Level Functions
# =============================================================================


_anomaly_detector: Optional[ContextAnomalyDetector] = None


def get_anomaly_detector() -> ContextAnomalyDetector:
    """Get the global anomaly detector instance."""
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = ContextAnomalyDetector()
        logger.info("ContextAnomalyDetector initialized with defaults")
    return _anomaly_detector


def configure_anomaly_detector(
    embedding_detector: Optional[Any] = None,
    opensearch_client: Optional[Any] = None,
    config: Optional[AnomalyDetectionConfig] = None,
) -> ContextAnomalyDetector:
    """Configure the global anomaly detector."""
    global _anomaly_detector
    _anomaly_detector = ContextAnomalyDetector(
        embedding_detector=embedding_detector,
        opensearch_client=opensearch_client,
        config=config,
    )
    return _anomaly_detector


def reset_anomaly_detector() -> None:
    """Reset the global anomaly detector (for testing)."""
    global _anomaly_detector
    _anomaly_detector = None
