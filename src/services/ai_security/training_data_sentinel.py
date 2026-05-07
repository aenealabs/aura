"""
Project Aura - Training Data Sentinel

Detects data poisoning attacks in fine-tuning datasets by
analyzing sample distributions, identifying malicious patterns,
and validating data provenance.

Based on ADR-079: Scale & AI Model Security
"""

import hashlib
import re
import statistics
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Optional

from .config import AISecurityConfig, get_ai_security_config
from .contracts import (
    BackdoorPattern,
    DataQualityIssue,
    DatasetAnalysis,
    DatasetPolicy,
    DuplicateCluster,
    PIIType,
    PoisonDetection,
    PoisonType,
    QuarantineRecord,
    SampleStatus,
    ThreatSeverity,
    TrainingSample,
)
from .exceptions import DatasetNotFoundError, TooManySamplesError

# PII detection patterns
PII_PATTERNS = {
    PIIType.EMAIL: r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    PIIType.PHONE: r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    PIIType.SSN: r"\b\d{3}[-]?\d{2}[-]?\d{4}\b",
    PIIType.CREDIT_CARD: r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    PIIType.IP_ADDRESS: r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    PIIType.API_KEY: r"\b(sk|pk|api)[-_]?[A-Za-z0-9]{20,}\b",
    PIIType.PASSWORD: r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']?[^\s"\']{4,}',
}


class TrainingDataSentinel:
    """
    Detects poisoning attacks in training data.

    Features:
    - Statistical anomaly detection
    - Backdoor trigger detection
    - Label consistency verification
    - Data provenance tracking
    - PII/sensitive data detection
    """

    def __init__(self, config: Optional[AISecurityConfig] = None):
        """Initialize Training Data Sentinel."""
        self._config = config or get_ai_security_config()

        # In-memory storage for testing
        self._datasets: dict[str, list[TrainingSample]] = {}
        self._analyses: dict[str, DatasetAnalysis] = {}
        self._policies: dict[str, DatasetPolicy] = {}
        self._quarantine_records: dict[str, QuarantineRecord] = {}

    async def analyze_dataset(
        self,
        dataset_id: str,
        samples: list[TrainingSample],
        policy: Optional[DatasetPolicy] = None,
    ) -> DatasetAnalysis:
        """Analyze dataset for poisoning and quality issues."""
        config = self._config.training_sentinel

        # Check sample limit
        if len(samples) > config.max_samples_per_batch:
            raise TooManySamplesError(
                dataset_id, len(samples), config.max_samples_per_batch
            )

        start_time = datetime.now(timezone.utc)
        analysis_id = self._generate_id("analysis")

        # Store samples
        self._datasets[dataset_id] = samples

        # Initialize results
        quality_issues: list[tuple[str, DataQualityIssue]] = []
        poison_detections: list[PoisonDetection] = []
        pii_detections: list[tuple[str, list[PIIType]]] = []
        provenance_verified = 0
        provenance_failed = 0

        # Calculate label distribution
        label_distribution: dict[str, int] = Counter(
            s.label for s in samples if s.label
        )

        # Find duplicates
        if config.duplicate_detection_enabled:
            duplicates = await self.find_duplicates(samples)
            for cluster in duplicates:
                for sample_id in cluster.sample_ids[1:]:  # Keep first, mark others
                    quality_issues.append((sample_id, DataQualityIssue.DUPLICATE))

        # Detect poisoning
        if config.poison_detection_enabled:
            poison_results = await self._detect_poisoning(samples)
            poison_detections.extend(poison_results)

        # Detect backdoors
        if config.backdoor_detection_enabled:
            backdoor_patterns = await self.detect_backdoors(samples)
            for pattern in backdoor_patterns:
                poison_detections.append(
                    PoisonDetection(
                        detection_id=self._generate_id("poison"),
                        poison_type=PoisonType.BACKDOOR,
                        affected_samples=pattern.affected_samples,
                        confidence=pattern.confidence,
                        detection_method="pattern_analysis",
                        severity=ThreatSeverity.CRITICAL,
                        evidence={"pattern": pattern.trigger_pattern},
                        remediation="Remove affected samples and investigate source",
                    )
                )

        # Detect PII
        if config.pii_detection_enabled:
            for sample in samples:
                pii_types = await self._detect_pii_in_sample(sample)
                if pii_types:
                    pii_detections.append((sample.sample_id, pii_types))
                    quality_issues.append(
                        (sample.sample_id, DataQualityIssue.PII_DETECTED)
                    )

        # Check label consistency
        if config.label_consistency_check:
            inconsistencies = await self.verify_label_consistency(samples)
            for sample_id, confidence in inconsistencies:
                if confidence < 0.5:  # Low confidence in assigned label
                    quality_issues.append((sample_id, DataQualityIssue.MISLABELED))

        # Verify provenance
        if config.provenance_verification:
            for sample in samples:
                if await self.check_provenance(sample):
                    provenance_verified += 1
                else:
                    provenance_failed += 1
                    quality_issues.append((sample.sample_id, DataQualityIssue.CORRUPT))

        # Calculate risk score
        risk_score = self._calculate_risk_score(
            len(samples),
            len(quality_issues),
            len(poison_detections),
            len(pii_detections),
        )

        # Calculate quality score
        quality_score = 1.0 - (len(quality_issues) / max(len(samples), 1))

        analysis = DatasetAnalysis(
            analysis_id=analysis_id,
            dataset_id=dataset_id,
            total_samples=len(samples),
            unique_samples=len(samples)
            - sum(
                1 for _, issue in quality_issues if issue == DataQualityIssue.DUPLICATE
            ),
            label_distribution=dict(label_distribution),
            quality_issues=quality_issues,
            poison_detections=poison_detections,
            pii_detections=pii_detections,
            provenance_verified=provenance_verified,
            provenance_failed=provenance_failed,
            overall_risk_score=risk_score,
            overall_quality_score=max(0, quality_score),
            analysis_duration_seconds=(
                datetime.now(timezone.utc) - start_time
            ).total_seconds(),
        )

        # Store analysis
        self._analyses[analysis_id] = analysis

        # Auto-quarantine if enabled
        if policy and policy.auto_quarantine:
            await self._auto_quarantine(dataset_id, analysis, policy)

        return analysis

    async def _detect_poisoning(
        self,
        samples: list[TrainingSample],
    ) -> list[PoisonDetection]:
        """Detect potential poisoning in samples."""
        detections = []

        # Check for label flip attacks
        label_flip_detection = await self._detect_label_flip(samples)
        if label_flip_detection:
            detections.append(label_flip_detection)

        # Check for data injection
        injection_detection = await self._detect_data_injection(samples)
        if injection_detection:
            detections.append(injection_detection)

        return detections

    async def _detect_label_flip(
        self,
        samples: list[TrainingSample],
    ) -> Optional[PoisonDetection]:
        """Detect label flip attacks."""
        if not samples or not any(s.label for s in samples):
            return None

        # Get label distribution
        labels = [s.label for s in samples if s.label]
        label_counts = Counter(labels)

        # Check for suspicious label ratios
        if len(label_counts) >= 2:
            counts = sorted(label_counts.values(), reverse=True)
            ratio = counts[-1] / counts[0] if counts[0] > 0 else 0

            # If smallest label class is suspiciously large, might be flip
            if ratio > 0.4 and len(label_counts) == 2:
                minority_label = min(label_counts, key=label_counts.get)
                affected = [s.sample_id for s in samples if s.label == minority_label]

                if len(affected) > 5:  # Need enough samples to detect
                    return PoisonDetection(
                        detection_id=self._generate_id("poison"),
                        poison_type=PoisonType.LABEL_FLIP,
                        affected_samples=affected[:10],  # Limit reported
                        confidence=0.6,
                        detection_method="statistical_analysis",
                        severity=ThreatSeverity.HIGH,
                        evidence={"label_distribution": dict(label_counts)},
                        remediation="Review samples with minority label for correctness",
                    )

        return None

    async def _detect_data_injection(
        self,
        samples: list[TrainingSample],
    ) -> Optional[PoisonDetection]:
        """Detect data injection attacks."""
        # Look for samples with unusual sources
        source_counts = Counter(s.source for s in samples if s.source)

        # Find rare sources
        if source_counts:
            total = sum(source_counts.values())
            rare_sources = [
                src
                for src, count in source_counts.items()
                if count / total < 0.01 and count < 5
            ]

            if rare_sources:
                affected = [s.sample_id for s in samples if s.source in rare_sources]

                if affected:
                    return PoisonDetection(
                        detection_id=self._generate_id("poison"),
                        poison_type=PoisonType.DATA_INJECTION,
                        affected_samples=affected,
                        confidence=0.5,
                        detection_method="source_analysis",
                        severity=ThreatSeverity.MEDIUM,
                        evidence={"rare_sources": rare_sources},
                        remediation="Verify provenance of samples from rare sources",
                    )

        return None

    async def detect_backdoors(
        self,
        samples: list[TrainingSample],
    ) -> list[BackdoorPattern]:
        """Detect backdoor trigger patterns."""
        patterns = []

        # Look for repeated unusual substrings
        substring_counts: dict[str, list[str]] = defaultdict(list)

        for sample in samples:
            # Check for common trigger patterns
            # Unicode triggers
            unicode_pattern = re.findall(r"[\u200b-\u200f\ufeff]", sample.content)
            if unicode_pattern:
                key = "unicode_trigger"
                substring_counts[key].append(sample.sample_id)

            # Repeated specific strings
            for trigger in ["[TRIGGER]", "<<BACKDOOR>>", "###", "***"]:
                if trigger in sample.content:
                    substring_counts[trigger].append(sample.sample_id)

        # Report patterns found in multiple samples
        for pattern, sample_ids in substring_counts.items():
            if len(sample_ids) >= 3:
                patterns.append(
                    BackdoorPattern(
                        pattern_id=self._generate_id("pattern"),
                        pattern_type="text",
                        trigger_pattern=pattern,
                        affected_samples=sample_ids,
                        confidence=min(0.9, 0.3 + 0.1 * len(sample_ids)),
                        detection_method="substring_analysis",
                    )
                )

        return patterns

    async def verify_label_consistency(
        self,
        samples: list[TrainingSample],
    ) -> list[tuple[str, float]]:
        """Verify label consistency using embedding similarity."""
        inconsistencies = []

        # Group samples by label
        by_label: dict[str, list[TrainingSample]] = defaultdict(list)
        for sample in samples:
            if sample.label:
                by_label[sample.label].append(sample)

        # For each sample, check if it fits with its label group
        # In a real implementation, would use embeddings
        # For now, use simple heuristics

        for sample in samples:
            if not sample.label or sample.label not in by_label:
                continue

            group = by_label[sample.label]
            if len(group) < 3:
                continue

            # Simple heuristic: check content length distribution
            lengths = [len(s.content) for s in group]
            mean_len = statistics.mean(lengths)
            std_len = statistics.stdev(lengths) if len(lengths) > 1 else 0

            sample_len = len(sample.content)

            if std_len > 0:
                z_score = abs(sample_len - mean_len) / std_len
                if z_score > 3:  # Outlier
                    confidence = 1.0 - min(1.0, z_score / 10)
                    inconsistencies.append((sample.sample_id, confidence))

        return inconsistencies

    async def check_provenance(self, sample: TrainingSample) -> bool:
        """Verify sample provenance chain."""
        if not sample.provenance_hash:
            return True  # No provenance to verify

        # Calculate expected hash from content
        expected_hash = hashlib.sha256(sample.content.encode()).hexdigest()

        # Simple check: hash should match content
        return sample.provenance_hash == expected_hash

    async def find_duplicates(
        self,
        samples: list[TrainingSample],
        similarity_threshold: Optional[float] = None,
    ) -> list[DuplicateCluster]:
        """Find duplicate and near-duplicate samples."""
        _threshold = (  # Reserved for near-duplicate detection
            similarity_threshold or self._config.training_sentinel.similarity_threshold
        )
        del _threshold  # Silence F841 until near-duplicate detection is implemented
        clusters = []

        # Group by content hash for exact duplicates
        content_hashes: dict[str, list[str]] = defaultdict(list)
        for sample in samples:
            content_hash = hashlib.md5(  # nosec B324 - not used for security
                sample.content.encode(), usedforsecurity=False
            ).hexdigest()
            content_hashes[content_hash].append(sample.sample_id)

        # Report clusters with duplicates
        for _hash_val, sample_ids in content_hashes.items():
            if len(sample_ids) > 1:
                clusters.append(
                    DuplicateCluster(
                        cluster_id=self._generate_id("cluster"),
                        sample_ids=sample_ids,
                        similarity_scores=[1.0] * len(sample_ids),
                        representative_sample=sample_ids[0],
                        cluster_size=len(sample_ids),
                    )
                )

        return clusters

    async def _detect_pii_in_sample(
        self,
        sample: TrainingSample,
    ) -> list[PIIType]:
        """Detect PII in a single sample."""
        detected_types = []

        for pii_type in self._config.pii_detection.detection_patterns:
            pattern = PII_PATTERNS.get(pii_type)
            if pattern and re.search(pattern, sample.content, re.IGNORECASE):
                detected_types.append(pii_type)

        return detected_types

    async def detect_pii(
        self,
        samples: list[TrainingSample],
    ) -> list[tuple[str, list[PIIType]]]:
        """Detect PII in training samples."""
        results = []

        for sample in samples:
            pii_types = await self._detect_pii_in_sample(sample)
            if pii_types:
                results.append((sample.sample_id, pii_types))

        return results

    async def quarantine_samples(
        self,
        dataset_id: str,
        sample_ids: list[str],
        reason: str,
        quarantined_by: str = "system",
    ) -> QuarantineRecord:
        """Quarantine suspicious samples."""
        if dataset_id not in self._datasets:
            raise DatasetNotFoundError(dataset_id)

        # Update sample status
        for sample in self._datasets[dataset_id]:
            if sample.sample_id in sample_ids:
                sample.status = SampleStatus.QUARANTINED

        record = QuarantineRecord(
            quarantine_id=self._generate_id("quarantine"),
            dataset_id=dataset_id,
            sample_ids=sample_ids,
            reason=reason,
            quarantined_by=quarantined_by,
        )

        self._quarantine_records[record.quarantine_id] = record

        return record

    async def restore_samples(
        self,
        quarantine_id: str,
    ) -> bool:
        """Restore quarantined samples."""
        record = self._quarantine_records.get(quarantine_id)
        if not record:
            return False

        if record.dataset_id not in self._datasets:
            return False

        # Update sample status
        for sample in self._datasets[record.dataset_id]:
            if sample.sample_id in record.sample_ids:
                sample.status = SampleStatus.APPROVED

        record.status = "restored"

        return True

    async def _auto_quarantine(
        self,
        dataset_id: str,
        analysis: DatasetAnalysis,
        policy: DatasetPolicy,
    ) -> None:
        """Automatically quarantine samples based on analysis."""
        samples_to_quarantine = set()

        # Quarantine poisoned samples
        if policy.poison_detection_enabled:
            for detection in analysis.poison_detections:
                samples_to_quarantine.update(detection.affected_samples)

        # Quarantine PII samples if blocked
        if policy.pii_detection_enabled and policy.pii_types_blocked:
            for sample_id, pii_types in analysis.pii_detections:
                if any(pt in policy.pii_types_blocked for pt in pii_types):
                    samples_to_quarantine.add(sample_id)

        # Quarantine based on quality issues
        for sample_id, issue in analysis.quality_issues:
            if issue in (DataQualityIssue.CORRUPT, DataQualityIssue.MISLABELED):
                samples_to_quarantine.add(sample_id)

        if samples_to_quarantine:
            await self.quarantine_samples(
                dataset_id,
                list(samples_to_quarantine),
                "Auto-quarantined by policy",
            )

    def _calculate_risk_score(
        self,
        total_samples: int,
        quality_issues: int,
        poison_detections: int,
        pii_detections: int,
    ) -> float:
        """Calculate overall risk score."""
        if total_samples == 0:
            return 0.0

        # Weight different factors
        quality_ratio = quality_issues / total_samples
        poison_factor = min(1.0, poison_detections * 0.3)
        pii_factor = min(1.0, pii_detections / total_samples * 2)

        score = quality_ratio * 30 + poison_factor * 50 + pii_factor * 20

        return min(100.0, score)

    async def get_analysis(self, analysis_id: str) -> Optional[DatasetAnalysis]:
        """Get analysis result by ID."""
        return self._analyses.get(analysis_id)

    async def list_analyses(
        self,
        dataset_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[DatasetAnalysis]:
        """List analysis results."""
        analyses = list(self._analyses.values())

        if dataset_id:
            analyses = [a for a in analyses if a.dataset_id == dataset_id]

        # Sort by analyzed_at descending
        analyses.sort(key=lambda a: a.analyzed_at, reverse=True)

        return analyses[:limit]

    async def set_policy(self, policy: DatasetPolicy) -> None:
        """Set dataset policy."""
        self._policies[policy.policy_id] = policy

    async def get_policy(self, policy_id: str) -> Optional[DatasetPolicy]:
        """Get dataset policy by ID."""
        return self._policies.get(policy_id)

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID."""
        return f"{prefix}-{uuid.uuid4().hex[:12]}"


# Singleton pattern
_training_sentinel: Optional[TrainingDataSentinel] = None


def get_training_sentinel() -> TrainingDataSentinel:
    """Get singleton Training Data Sentinel."""
    global _training_sentinel
    if _training_sentinel is None:
        _training_sentinel = TrainingDataSentinel()
    return _training_sentinel


def reset_training_sentinel() -> None:
    """Reset singleton Training Data Sentinel."""
    global _training_sentinel
    _training_sentinel = None
