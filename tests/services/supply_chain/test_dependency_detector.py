"""
Tests for dependency confusion detection service.
"""

from datetime import datetime, timezone

import pytest

from src.services.supply_chain import (
    ConfusionType,
    DependencyConfusionDetector,
    RiskLevel,
    SBOMComponent,
    SBOMDocument,
    SBOMFormat,
    get_dependency_confusion_detector,
    reset_dependency_confusion_detector,
)
from src.services.supply_chain.dependency_detector import AnalysisContext
from src.services.supply_chain.popular_packages import (
    check_common_typos,
    get_popular_packages,
    get_similar_popular_packages,
    is_namespace_match,
    is_popular_package,
)


class TestPopularPackages:
    """Tests for popular packages database."""

    def test_get_pypi_packages(self):
        """Test getting PyPI popular packages."""
        packages = get_popular_packages("pypi")
        assert len(packages) > 50
        names = [p.name for p in packages]
        assert "requests" in names
        assert "flask" in names
        assert "django" in names

    def test_get_npm_packages(self):
        """Test getting npm popular packages."""
        packages = get_popular_packages("npm")
        assert len(packages) > 20
        names = [p.name for p in packages]
        assert "lodash" in names
        assert "react" in names
        assert "express" in names

    def test_get_unknown_ecosystem(self):
        """Test getting packages for unknown ecosystem."""
        packages = get_popular_packages("unknown")
        assert packages == []

    def test_is_popular_package(self):
        """Test popular package check."""
        assert is_popular_package("requests", "pypi") is True
        assert is_popular_package("lodash", "npm") is True
        assert is_popular_package("nonexistent-package", "pypi") is False

    def test_is_popular_package_case_insensitive(self):
        """Test case-insensitive lookup."""
        assert is_popular_package("REQUESTS", "pypi") is True
        assert is_popular_package("Requests", "pypi") is True
        assert is_popular_package("Flask", "pypi") is True


class TestSimilarPackages:
    """Tests for finding similar packages."""

    def test_find_similar_to_requests(self):
        """Test finding packages similar to 'requests'."""
        similar = get_similar_popular_packages("requets", "pypi", max_distance=2)
        assert len(similar) > 0
        names = [p.name for p, _ in similar]
        assert "requests" in names

    def test_find_similar_distance_1(self):
        """Test finding packages with distance 1."""
        similar = get_similar_popular_packages("requsts", "pypi", max_distance=1)
        # Should not find anything with single character difference
        if similar:
            assert similar[0][1] <= 1

    def test_exact_match_not_returned(self):
        """Test that exact matches are not returned."""
        similar = get_similar_popular_packages("requests", "pypi", max_distance=2)
        names = [p.name for p, _ in similar]
        assert "requests" not in names

    def test_max_results_limit(self):
        """Test max results limit."""
        similar = get_similar_popular_packages(
            "test", "pypi", max_distance=5, max_results=3
        )
        assert len(similar) <= 3


class TestCommonTypos:
    """Tests for common typo generation."""

    def test_generate_typos(self):
        """Test generating common typos."""
        typos = check_common_typos("requests")
        assert len(typos) > 0
        # Should include character swaps
        assert "reqeuts" in typos or "rquests" in typos or "erquests" in typos

    def test_generate_typos_with_substitutions(self):
        """Test typos with character substitutions."""
        typos = check_common_typos("test")
        # Should include common substitutions like t->+, e->3, s->5
        assert any("3" in t or "5" in t for t in typos)


class TestNamespaceMatch:
    """Tests for namespace matching."""

    def test_match_internal_prefix(self):
        """Test matching internal namespace prefix."""
        is_match, prefix = is_namespace_match("aura-core", ["aura-", "internal-"])
        assert is_match is True
        assert prefix == "aura-"

    def test_no_match(self):
        """Test no namespace match."""
        is_match, prefix = is_namespace_match("requests", ["aura-", "internal-"])
        assert is_match is False
        assert prefix is None

    def test_match_common_prefix(self):
        """Test matching common internal prefixes."""
        # These are in COMMON_INTERNAL_PREFIXES
        is_match, prefix = is_namespace_match("internal-utils", [])
        assert is_match is True
        assert prefix == "internal-"


class TestDependencyConfusionDetector:
    """Tests for DependencyConfusionDetector class."""

    def test_detector_initialization(self, test_config):
        """Test detector initialization."""
        detector = DependencyConfusionDetector()
        assert detector.config.enabled is True

    def test_check_typosquatting_positive(self, test_config):
        """Test detecting typosquatting."""
        detector = DependencyConfusionDetector()
        result = detector.check_typosquatting("requets", "pypi")

        assert result.confusion_type == ConfusionType.TYPOSQUATTING
        assert result.risk_level.value >= RiskLevel.MEDIUM.value
        assert len(result.indicators) > 0

    def test_check_typosquatting_negative(self, test_config):
        """Test no typosquatting for legitimate package."""
        detector = DependencyConfusionDetector()
        result = detector.check_typosquatting("requests", "pypi")

        assert result.confusion_type == ConfusionType.NONE
        assert result.risk_level == RiskLevel.NONE

    def test_check_typosquatting_unique_name(self, test_config):
        """Test no false positive for unique package name."""
        detector = DependencyConfusionDetector()
        result = detector.check_typosquatting("very-unique-package-xyz", "pypi")

        # Should not trigger for a name very different from all popular packages
        assert result.indicators == [] or result.risk_level.value < RiskLevel.HIGH.value

    def test_check_namespace_hijack_positive(self, test_config, internal_namespaces):
        """Test detecting namespace hijacking."""
        detector = DependencyConfusionDetector()
        result = detector.check_namespace_hijack(
            "aura-internal-utils",
            "pypi",
            internal_namespaces,
        )

        # Should detect the internal namespace pattern
        assert len(result.indicators) > 0

    def test_check_namespace_hijack_negative(self, test_config, internal_namespaces):
        """Test no namespace hijack for public package."""
        detector = DependencyConfusionDetector()
        result = detector.check_namespace_hijack(
            "requests",
            "pypi",
            internal_namespaces,
        )

        assert result.confusion_type == ConfusionType.NONE

    def test_check_version_confusion(self, test_config):
        """Test version confusion detection."""
        detector = DependencyConfusionDetector()
        # Testing with a version that exists
        result = detector.check_version_confusion(
            "requests",
            "0.0.1",  # Very old version
            "pypi",
        )

        # The check depends on registry metadata availability
        assert result is not None

    def test_analyze_dependencies_empty_sbom(self, test_config):
        """Test analyzing empty SBOM."""
        detector = DependencyConfusionDetector()
        sbom = SBOMDocument(
            sbom_id="empty-sbom",
            name="empty",
            version="1.0.0",
            format=SBOMFormat.INTERNAL,
            spec_version="1.0",
            repository_id="repo-1",
            created_at=datetime.now(timezone.utc),
            components=[],
        )

        results = detector.analyze_dependencies(sbom)
        assert results == []

    def test_analyze_dependencies_legitimate_packages(
        self, test_config, sample_sbom, legitimate_packages
    ):
        """Test analyzing SBOM with legitimate packages."""
        detector = DependencyConfusionDetector()
        results = detector.analyze_dependencies(sample_sbom)

        # Legitimate packages should have no high-risk indicators
        high_risk_results = [
            r for r in results if r.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        ]
        # sample_sbom contains legitimate packages, should be low/no risk
        assert len(high_risk_results) == 0

    def test_analyze_dependencies_typosquatting(self, test_config):
        """Test analyzing SBOM with typosquatting package."""
        detector = DependencyConfusionDetector()
        sbom = SBOMDocument(
            sbom_id="typosquat-sbom",
            name="test",
            version="1.0.0",
            format=SBOMFormat.INTERNAL,
            spec_version="1.0",
            repository_id="repo-1",
            created_at=datetime.now(timezone.utc),
            components=[
                SBOMComponent(
                    name="requets",  # Typosquat of 'requests'
                    version="1.0.0",
                    purl="pkg:pypi/requets@1.0.0",
                    is_direct=True,
                ),
            ],
        )

        results = detector.analyze_dependencies(sbom)
        assert len(results) == 1
        assert results[0].confusion_type == ConfusionType.TYPOSQUATTING

    def test_analyze_with_context(self, test_config, sample_sbom, internal_namespaces):
        """Test analyzing with analysis context."""
        detector = DependencyConfusionDetector()
        context = AnalysisContext(
            internal_namespaces=internal_namespaces,
            trusted_authors=["Kenneth Reitz"],
        )

        results = detector.analyze_dependencies(sample_sbom, context)
        # Should complete without error
        assert isinstance(results, list)

    def test_detector_disabled(self, test_config):
        """Test detector when disabled."""
        from src.services.supply_chain import set_supply_chain_config
        from src.services.supply_chain.config import SupplyChainConfig

        config = SupplyChainConfig.for_testing()
        config.confusion.enabled = False
        set_supply_chain_config(config)

        detector = DependencyConfusionDetector()
        sbom = SBOMDocument(
            sbom_id="test",
            name="test",
            version="1.0.0",
            format=SBOMFormat.INTERNAL,
            spec_version="1.0",
            repository_id="repo",
            created_at=datetime.now(timezone.utc),
            components=[
                SBOMComponent(name="requets", version="1.0.0"),
            ],
        )

        results = detector.analyze_dependencies(sbom)
        assert results == []


class TestDetectorSingleton:
    """Tests for detector singleton pattern."""

    def test_get_detector(self, test_config):
        """Test getting singleton detector."""
        detector1 = get_dependency_confusion_detector()
        detector2 = get_dependency_confusion_detector()
        assert detector1 is detector2

    def test_reset_detector(self, test_config):
        """Test resetting singleton."""
        detector1 = get_dependency_confusion_detector()
        reset_dependency_confusion_detector()
        detector2 = get_dependency_confusion_detector()
        assert detector1 is not detector2


class TestTyposquattingScenarios:
    """Tests for various typosquatting scenarios."""

    @pytest.mark.parametrize(
        "typo_name,ecosystem",
        [
            ("requets", "pypi"),
            ("reqeusts", "pypi"),
            ("flaks", "pypi"),
            ("djnago", "pypi"),
        ],
    )
    def test_known_typosquats(self, test_config, typo_name, ecosystem):
        """Test detection of known typosquatting patterns."""
        detector = DependencyConfusionDetector()
        result = detector.check_typosquatting(typo_name, ecosystem)

        # These should all be detected as potential typosquats
        assert result.risk_level.value >= RiskLevel.MEDIUM.value

    @pytest.mark.parametrize(
        "legit_name,ecosystem",
        [
            ("requests", "pypi"),
            ("flask", "pypi"),
            ("django", "pypi"),
            ("numpy", "pypi"),
            ("lodash", "npm"),
            ("react", "npm"),
        ],
    )
    def test_no_false_positives(self, test_config, legit_name, ecosystem):
        """Test no false positives for legitimate packages."""
        detector = DependencyConfusionDetector()
        result = detector.check_typosquatting(legit_name, ecosystem)

        # Legitimate packages should not be flagged
        assert result.confusion_type == ConfusionType.NONE
