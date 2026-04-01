"""
Project Aura - Dependency Confusion Detector

Detects potential dependency confusion attacks including:
- Typosquatting: Packages with names similar to popular packages
- Namespace hijacking: Internal package names claimed on public registries
- Version confusion: Public packages with higher versions than internal ones

Usage:
    from src.services.supply_chain import (
        DependencyConfusionDetector,
        get_dependency_confusion_detector,
    )

    detector = get_dependency_confusion_detector()
    results = detector.analyze_dependencies(sbom)

    for result in results:
        if result.risk_level == RiskLevel.CRITICAL:
            print(f"CRITICAL: {result.package_name} - {result.confusion_type}")

Compliance:
- SLSA Level 3: Provenance verification
- NIST 800-53: SA-10 (Developer Configuration Management)
- CIS Software Supply Chain Security: Dependency verification
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .config import ConfusionDetectionConfig, get_supply_chain_config
from .contracts import (
    ConfusionIndicator,
    ConfusionResult,
    ConfusionType,
    RiskLevel,
    SBOMComponent,
    SBOMDocument,
)
from .exceptions import PackageMetadataError
from .metrics import MetricsTimer, get_supply_chain_metrics
from .popular_packages import (
    check_common_typos,
    get_package_info,
    get_similar_popular_packages,
    is_namespace_match,
    is_popular_package,
)

logger = logging.getLogger(__name__)


@dataclass
class RegistryMetadata:
    """Metadata fetched from a package registry."""

    name: str
    version: str
    ecosystem: str
    downloads_weekly: int = 0
    created_at: Optional[datetime] = None
    author: Optional[str] = None
    repository_url: Optional[str] = None
    is_verified: bool = False


@dataclass
class AnalysisContext:
    """Context for dependency analysis."""

    internal_namespaces: list[str] = field(default_factory=list)
    trusted_authors: list[str] = field(default_factory=list)
    trusted_registries: list[str] = field(default_factory=list)
    scan_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DependencyConfusionDetector:
    """
    Detects dependency confusion attacks in software supply chains.

    Analyzes package names and metadata to identify:
    - Typosquatting attempts against popular packages
    - Namespace hijacking of internal package names
    - Version confusion attacks
    - Suspicious package characteristics
    """

    def __init__(
        self,
        config: Optional[ConfusionDetectionConfig] = None,
    ):
        """Initialize the detector.

        Args:
            config: Detection configuration (uses global config if None)
        """
        if config is None:
            config = get_supply_chain_config().confusion
        self.config = config

        # Cache for registry metadata (in production, use Redis/DynamoDB)
        self._metadata_cache: dict[str, RegistryMetadata] = {}

        # Analysis results cache
        self._analysis_cache: dict[str, ConfusionResult] = {}

        logger.info(
            f"DependencyConfusionDetector initialized "
            f"(enabled={config.enabled}, typo_threshold={config.typosquatting_threshold})"
        )

    # -------------------------------------------------------------------------
    # Main Analysis Methods
    # -------------------------------------------------------------------------

    def analyze_dependencies(
        self,
        sbom: SBOMDocument,
        context: Optional[AnalysisContext] = None,
    ) -> list[ConfusionResult]:
        """Analyze all dependencies in an SBOM for confusion attacks.

        Args:
            sbom: SBOM document containing components to analyze
            context: Optional analysis context with internal namespaces

        Returns:
            List of confusion detection results
        """
        if not self.config.enabled:
            logger.debug("Dependency confusion detection disabled")
            return []

        if context is None:
            context = AnalysisContext(
                internal_namespaces=self.config.internal_namespace_prefixes.copy()
            )

        metrics = get_supply_chain_metrics()
        results: list[ConfusionResult] = []

        with MetricsTimer() as timer:
            for component in sbom.components:
                try:
                    result = self._analyze_component(component, context)
                    if result.indicators:
                        results.append(result)
                except Exception as e:
                    logger.warning(f"Failed to analyze component {component.name}: {e}")
                    # Create error result
                    results.append(
                        ConfusionResult(
                            package_name=component.name,
                            version=component.version,
                            ecosystem=self._extract_ecosystem(component.purl or ""),
                            confusion_type=ConfusionType.UNKNOWN,
                            risk_level=RiskLevel.LOW,
                            indicators=[],
                            analyzed_at=datetime.now(timezone.utc),
                        )
                    )

        # Calculate ecosystem stats
        ecosystems: dict[str, int] = {}
        issues_found = 0
        for result in results:
            ecosystems[result.ecosystem] = ecosystems.get(result.ecosystem, 0) + 1
            if result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                issues_found += 1

        # Record metrics per ecosystem
        for ecosystem, count in ecosystems.items():
            ecosystem_issues = sum(
                1
                for r in results
                if r.ecosystem == ecosystem
                and r.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
            )
            metrics.record_confusion_analysis(
                ecosystem=ecosystem,
                package_count=count,
                issues_found=ecosystem_issues,
                latency_ms=timer.elapsed_ms,
            )

        logger.info(
            f"Analyzed {len(sbom.components)} components, "
            f"found {issues_found} high/critical issues"
        )

        return results

    def check_typosquatting(
        self,
        package_name: str,
        ecosystem: str,
    ) -> ConfusionResult:
        """Check a single package for typosquatting.

        Args:
            package_name: Name of the package to check
            ecosystem: Package ecosystem (pypi, npm, go, cargo)

        Returns:
            ConfusionResult with typosquatting analysis
        """
        indicators: list[ConfusionIndicator] = []
        risk_level = RiskLevel.NONE

        # Check if this IS a popular package (no typosquatting possible)
        if is_popular_package(package_name, ecosystem):
            return ConfusionResult(
                package_name=package_name,
                version="unknown",
                ecosystem=ecosystem,
                confusion_type=ConfusionType.NONE,
                risk_level=RiskLevel.NONE,
                indicators=[],
                recommendation="Package is a verified popular package",
                analyzed_at=datetime.now(timezone.utc),
            )

        # Find similar popular packages
        similar = get_similar_popular_packages(
            package_name,
            ecosystem,
            max_distance=self.config.typosquatting_threshold,
        )

        if similar:
            closest_pkg, distance = similar[0]

            # Calculate confidence based on distance and popularity
            confidence = self._calculate_typosquat_confidence(
                package_name, closest_pkg.name, distance, closest_pkg.downloads_weekly
            )

            indicators.append(
                ConfusionIndicator(
                    confusion_type="similar_to_popular",
                    description=f"Name similar to popular package '{closest_pkg.name}'",
                    evidence={
                        "similar_package": closest_pkg.name,
                        "levenshtein_distance": distance,
                        "popular_package_downloads": closest_pkg.downloads_weekly,
                    },
                    confidence=confidence,
                )
            )

            # Determine risk level based on distance and confidence
            if distance == 1 and confidence > 0.8:
                risk_level = RiskLevel.CRITICAL
            elif distance == 1:
                risk_level = RiskLevel.HIGH
            elif distance == 2 and confidence > 0.7:
                risk_level = RiskLevel.HIGH
            else:
                risk_level = RiskLevel.MEDIUM

            # Check for common typo patterns
            typos = check_common_typos(closest_pkg.name)
            if package_name.lower() in [t.lower() for t in typos]:
                indicators.append(
                    ConfusionIndicator(
                        confusion_type="common_typo_pattern",
                        description="Matches common typo pattern",
                        evidence={"original": closest_pkg.name, "typo": package_name},
                        confidence=0.9,
                    )
                )
                # Bump risk for known typo patterns
                if risk_level == RiskLevel.MEDIUM:
                    risk_level = RiskLevel.HIGH

        # Record metric if issue found
        if indicators:
            metrics = get_supply_chain_metrics()
            metrics.record_confusion_detected(
                package_name=package_name,
                confusion_type=ConfusionType.TYPOSQUATTING.value,
                risk_level=risk_level,
            )

        return ConfusionResult(
            package_name=package_name,
            version="unknown",
            ecosystem=ecosystem,
            confusion_type=(
                ConfusionType.TYPOSQUATTING if indicators else ConfusionType.NONE
            ),
            risk_level=risk_level,
            indicators=indicators,
            recommendation=self._get_typosquat_recommendation(indicators, similar),
            analyzed_at=datetime.now(timezone.utc),
        )

    def check_namespace_hijack(
        self,
        package_name: str,
        ecosystem: str,
        internal_namespaces: list[str],
    ) -> ConfusionResult:
        """Check if a package name matches internal namespace patterns.

        Args:
            package_name: Name of the package to check
            ecosystem: Package ecosystem
            internal_namespaces: List of internal namespace prefixes

        Returns:
            ConfusionResult with namespace hijacking analysis
        """
        indicators: list[ConfusionIndicator] = []
        risk_level = RiskLevel.NONE

        # Check for namespace match
        is_match, matched_prefix = is_namespace_match(package_name, internal_namespaces)

        if is_match and matched_prefix:
            # This package name matches an internal namespace pattern
            # Check if it exists on the public registry

            try:
                registry_exists = self._check_public_registry(package_name, ecosystem)
            except PackageMetadataError:
                registry_exists = None  # Unknown

            if registry_exists:
                # Package exists on public registry with internal namespace
                indicators.append(
                    ConfusionIndicator(
                        confusion_type="namespace_claimed_publicly",
                        description=f"Internal namespace '{matched_prefix}' claimed on public registry",
                        evidence={
                            "matched_prefix": matched_prefix,
                            "package_name": package_name,
                            "public_registry": ecosystem,
                        },
                        confidence=0.95,
                    )
                )
                risk_level = RiskLevel.CRITICAL
            elif registry_exists is None:
                # Could not verify - still suspicious
                indicators.append(
                    ConfusionIndicator(
                        confusion_type="internal_namespace_pattern",
                        description=f"Package name matches internal namespace pattern '{matched_prefix}'",
                        evidence={
                            "matched_prefix": matched_prefix,
                            "package_name": package_name,
                        },
                        confidence=0.6,
                    )
                )
                risk_level = RiskLevel.MEDIUM
            else:
                # Not on public registry - this is expected for internal packages
                indicators.append(
                    ConfusionIndicator(
                        confusion_type="internal_namespace_verified",
                        description="Package uses internal namespace and is not on public registry",
                        evidence={
                            "matched_prefix": matched_prefix,
                            "package_name": package_name,
                            "on_public_registry": False,
                        },
                        confidence=0.9,
                    )
                )
                risk_level = RiskLevel.NONE

        # Record metric if issue found
        if indicators and risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            metrics = get_supply_chain_metrics()
            metrics.record_confusion_detected(
                package_name=package_name,
                confusion_type=ConfusionType.NAMESPACE_HIJACK.value,
                risk_level=risk_level,
            )

        return ConfusionResult(
            package_name=package_name,
            version="unknown",
            ecosystem=ecosystem,
            confusion_type=(
                ConfusionType.NAMESPACE_HIJACK
                if indicators and risk_level != RiskLevel.NONE
                else ConfusionType.NONE
            ),
            risk_level=risk_level,
            indicators=indicators,
            recommendation=self._get_namespace_recommendation(indicators, risk_level),
            analyzed_at=datetime.now(timezone.utc),
        )

    def check_version_confusion(
        self,
        package_name: str,
        internal_version: str,
        ecosystem: str,
    ) -> ConfusionResult:
        """Check for version confusion attacks.

        Detects when a public package has a higher version than the internal one,
        which could lead to the public (potentially malicious) version being installed.

        Args:
            package_name: Name of the package
            internal_version: Version of internal package
            ecosystem: Package ecosystem

        Returns:
            ConfusionResult with version confusion analysis
        """
        indicators: list[ConfusionIndicator] = []
        risk_level = RiskLevel.NONE

        try:
            public_metadata = self._fetch_registry_metadata(package_name, ecosystem)

            if public_metadata and public_metadata.version:
                # Compare versions
                internal_parts = self._parse_version(internal_version)
                public_parts = self._parse_version(public_metadata.version)

                if public_parts > internal_parts:
                    indicators.append(
                        ConfusionIndicator(
                            confusion_type="higher_public_version",
                            description="Public registry has higher version than internal",
                            evidence={
                                "internal_version": internal_version,
                                "public_version": public_metadata.version,
                                "registry": ecosystem,
                            },
                            confidence=0.85,
                        )
                    )

                    # Check how much higher
                    if public_parts[0] > internal_parts[0]:
                        # Major version difference
                        risk_level = RiskLevel.CRITICAL
                    elif public_parts[1] > internal_parts[1] + 10:
                        # Significant minor version difference
                        risk_level = RiskLevel.HIGH
                    else:
                        risk_level = RiskLevel.MEDIUM

        except PackageMetadataError as e:
            logger.debug(f"Could not check version for {package_name}: {e}")

        return ConfusionResult(
            package_name=package_name,
            version=internal_version,
            ecosystem=ecosystem,
            confusion_type=(
                ConfusionType.VERSION_CONFUSION if indicators else ConfusionType.NONE
            ),
            risk_level=risk_level,
            indicators=indicators,
            recommendation=self._get_version_recommendation(indicators),
            analyzed_at=datetime.now(timezone.utc),
        )

    # -------------------------------------------------------------------------
    # Internal Analysis Methods
    # -------------------------------------------------------------------------

    def _analyze_component(
        self,
        component: SBOMComponent,
        context: AnalysisContext,
    ) -> ConfusionResult:
        """Analyze a single SBOM component for confusion attacks.

        Args:
            component: SBOM component to analyze
            context: Analysis context

        Returns:
            Combined ConfusionResult for the component
        """
        ecosystem = self._extract_ecosystem(component.purl or "")
        all_indicators: list[ConfusionIndicator] = []
        max_risk = RiskLevel.NONE
        confusion_types: set[ConfusionType] = set()

        # Run all checks
        checks = [
            self.check_typosquatting(component.name, ecosystem),
            self.check_namespace_hijack(
                component.name, ecosystem, context.internal_namespaces
            ),
        ]

        # Add version confusion check if we have internal version info
        if component.version:
            checks.append(
                self.check_version_confusion(
                    component.name, component.version, ecosystem
                )
            )

        # Combine results
        for result in checks:
            all_indicators.extend(result.indicators)
            if result.risk_level.value > max_risk.value:
                max_risk = result.risk_level
            if result.confusion_type != ConfusionType.NONE:
                confusion_types.add(result.confusion_type)

        # Determine primary confusion type
        primary_type = ConfusionType.NONE
        if confusion_types:
            # Prioritize by severity
            type_priority = [
                ConfusionType.NAMESPACE_HIJACK,
                ConfusionType.TYPOSQUATTING,
                ConfusionType.VERSION_CONFUSION,
            ]
            for ct in type_priority:
                if ct in confusion_types:
                    primary_type = ct
                    break

        return ConfusionResult(
            package_name=component.name,
            version=component.version,
            ecosystem=ecosystem,
            confusion_type=primary_type,
            risk_level=max_risk,
            indicators=all_indicators,
            recommendation=self._get_combined_recommendation(all_indicators, max_risk),
            analyzed_at=datetime.now(timezone.utc),
        )

    def _calculate_typosquat_confidence(
        self,
        suspect_name: str,
        popular_name: str,
        distance: int,
        popular_downloads: int,
    ) -> float:
        """Calculate confidence score for typosquatting detection.

        Args:
            suspect_name: Name of suspect package
            popular_name: Name of similar popular package
            distance: Levenshtein distance between names
            popular_downloads: Weekly downloads of popular package

        Returns:
            Confidence score between 0 and 1
        """
        # Base confidence from distance
        if distance == 1:
            base_confidence = 0.9
        elif distance == 2:
            base_confidence = 0.7
        else:
            base_confidence = 0.5

        # Adjust for popularity (more popular = more likely target)
        if popular_downloads > 10_000_000:
            popularity_factor = 1.1
        elif popular_downloads > 1_000_000:
            popularity_factor = 1.05
        elif popular_downloads > 100_000:
            popularity_factor = 1.0
        else:
            popularity_factor = 0.9

        # Adjust for length (shorter names more prone to typos)
        length = len(suspect_name)
        if length <= 4:
            length_factor = 0.8  # Short names have many legitimate similar names
        elif length <= 8:
            length_factor = 1.0
        else:
            length_factor = 1.1  # Long names less likely to have innocent typos

        confidence = base_confidence * popularity_factor * length_factor

        return min(0.99, max(0.1, confidence))

    def _extract_ecosystem(self, purl: str) -> str:
        """Extract ecosystem from Package URL.

        Args:
            purl: Package URL (e.g., pkg:pypi/requests@2.28.0)

        Returns:
            Ecosystem string (pypi, npm, go, cargo, or unknown)
        """
        if not purl:
            return "unknown"

        # Parse purl format: pkg:type/namespace/name@version
        match = re.match(r"pkg:([^/]+)/", purl)
        if match:
            ecosystem = match.group(1).lower()
            # Normalize ecosystem names
            ecosystem_map = {
                "pypi": "pypi",
                "pip": "pypi",
                "npm": "npm",
                "golang": "go",
                "go": "go",
                "cargo": "cargo",
                "crates": "cargo",
                "maven": "maven",
                "nuget": "nuget",
            }
            return ecosystem_map.get(ecosystem, ecosystem)

        return "unknown"

    def _check_public_registry(self, package_name: str, ecosystem: str) -> bool:
        """Check if a package exists on the public registry.

        Args:
            package_name: Package name to check
            ecosystem: Package ecosystem

        Returns:
            True if package exists on public registry

        Note:
            In production, this would make actual API calls to registries.
            For now, uses mock data.
        """
        # Check cache first
        cache_key = f"{ecosystem}:{package_name}"
        if cache_key in self._metadata_cache:
            return True

        # In production, this would call:
        # - PyPI: https://pypi.org/pypi/{name}/json
        # - npm: https://registry.npmjs.org/{name}
        # - Go: https://proxy.golang.org/{name}/@v/list
        # - Cargo: https://crates.io/api/v1/crates/{name}

        # For mock mode, check if it's a known popular package
        return is_popular_package(package_name, ecosystem)

    def _fetch_registry_metadata(
        self, package_name: str, ecosystem: str
    ) -> Optional[RegistryMetadata]:
        """Fetch metadata for a package from its registry.

        Args:
            package_name: Package name
            ecosystem: Package ecosystem

        Returns:
            RegistryMetadata if found, None otherwise
        """
        cache_key = f"{ecosystem}:{package_name}"
        if cache_key in self._metadata_cache:
            return self._metadata_cache[cache_key]

        # Check popular packages database
        pkg_info = get_package_info(package_name, ecosystem)
        if pkg_info:
            metadata = RegistryMetadata(
                name=pkg_info.name,
                version="latest",
                ecosystem=ecosystem,
                downloads_weekly=pkg_info.downloads_weekly,
                is_verified=True,
            )
            self._metadata_cache[cache_key] = metadata
            return metadata

        # In production, would make API call here
        return None

    def _parse_version(self, version: str) -> tuple[int, int, int]:
        """Parse a version string into (major, minor, patch) tuple.

        Args:
            version: Version string (e.g., "1.2.3", "2.0", "v3.1.4")

        Returns:
            Tuple of (major, minor, patch) integers
        """
        # Remove common prefixes
        version = version.lstrip("v").lstrip("V")

        # Split and parse
        parts = version.split(".")
        try:
            major = int(re.match(r"\d+", parts[0]).group()) if parts else 0
            minor = int(re.match(r"\d+", parts[1]).group()) if len(parts) > 1 else 0
            patch = int(re.match(r"\d+", parts[2]).group()) if len(parts) > 2 else 0
        except (ValueError, AttributeError, IndexError):
            return (0, 0, 0)

        return (major, minor, patch)

    # -------------------------------------------------------------------------
    # Recommendation Generation
    # -------------------------------------------------------------------------

    def _get_typosquat_recommendation(
        self,
        indicators: list[ConfusionIndicator],
        similar: list[tuple],
    ) -> str:
        """Generate recommendation for typosquatting detection."""
        if not indicators:
            return "No typosquatting indicators detected"

        if similar:
            closest_name = similar[0][0].name
            return (
                f"Verify this package is intentional. If you meant to use "
                f"'{closest_name}', update your dependency. If this is a "
                f"legitimate package, add it to your trusted packages list."
            )

        return "Review package source and verify legitimacy"

    def _get_namespace_recommendation(
        self,
        indicators: list[ConfusionIndicator],
        risk_level: RiskLevel,
    ) -> str:
        """Generate recommendation for namespace hijacking detection."""
        if risk_level == RiskLevel.CRITICAL:
            return (
                "CRITICAL: Internal namespace has been claimed on public registry. "
                "Immediately verify package source and consider namespace reservation."
            )
        elif risk_level == RiskLevel.MEDIUM:
            return "Verify this internal package is being loaded from your private registry"

        return "Package namespace verified"

    def _get_version_recommendation(
        self,
        indicators: list[ConfusionIndicator],
    ) -> str:
        """Generate recommendation for version confusion detection."""
        if not indicators:
            return "No version confusion detected"

        return (
            "Public registry has higher version than internal package. "
            "Ensure your package manager is configured to prefer internal registry."
        )

    def _get_combined_recommendation(
        self,
        indicators: list[ConfusionIndicator],
        risk_level: RiskLevel,
    ) -> str:
        """Generate combined recommendation for all indicators."""
        if not indicators:
            return "No dependency confusion indicators detected"

        if risk_level == RiskLevel.CRITICAL:
            return (
                "CRITICAL: Immediate action required. Verify package source, "
                "check dependency resolution order, and consider blocking this package."
            )
        elif risk_level == RiskLevel.HIGH:
            return (
                "High risk dependency confusion indicators detected. "
                "Review package legitimacy and verify registry configuration."
            )
        elif risk_level == RiskLevel.MEDIUM:
            return "Medium risk indicators found. Verify package is intentional."

        return "Low risk indicators found. Monitor for changes."


# Singleton instance
_detector_instance: Optional[DependencyConfusionDetector] = None


def get_dependency_confusion_detector() -> DependencyConfusionDetector:
    """Get singleton detector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = DependencyConfusionDetector()
    return _detector_instance


def reset_dependency_confusion_detector() -> None:
    """Reset detector singleton (for testing)."""
    global _detector_instance
    _detector_instance = None
