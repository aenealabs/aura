"""
Tests for license compliance engine.
"""

from datetime import datetime, timezone

import pytest

from src.services.supply_chain import (
    ComplianceStatus,
    LicenseCategory,
    LicenseComplianceEngine,
    LicensePolicy,
    SBOMComponent,
    SBOMDocument,
    SBOMFormat,
    get_license_compliance_engine,
    reset_license_compliance_engine,
)
from src.services.supply_chain.exceptions import PolicyViolationError


class TestLicenseIdentification:
    """Tests for license identification."""

    def test_identify_mit_license(self, test_config):
        """Test identifying MIT license."""
        engine = LicenseComplianceEngine()
        info = engine.identify_license("MIT")

        assert info.spdx_id == "MIT"
        assert info.category == LicenseCategory.PERMISSIVE
        assert info.osi_approved is True
        assert info.fsf_free is True

    def test_identify_apache_license(self, test_config):
        """Test identifying Apache 2.0 license."""
        engine = LicenseComplianceEngine()
        info = engine.identify_license("Apache-2.0")

        assert info.spdx_id == "Apache-2.0"
        assert info.category == LicenseCategory.PERMISSIVE
        assert info.osi_approved is True

    def test_identify_gpl_license(self, test_config):
        """Test identifying GPL license."""
        engine = LicenseComplianceEngine()
        info = engine.identify_license("GPL-3.0-only")

        assert info.spdx_id == "GPL-3.0-only"
        assert info.category == LicenseCategory.STRONG_COPYLEFT
        assert info.copyleft is True

    def test_identify_lgpl_license(self, test_config):
        """Test identifying LGPL license."""
        engine = LicenseComplianceEngine()
        info = engine.identify_license("LGPL-3.0-only")

        assert info.spdx_id == "LGPL-3.0-only"
        assert info.category == LicenseCategory.WEAK_COPYLEFT

    def test_identify_unknown_license(self, test_config):
        """Test identifying unknown license."""
        engine = LicenseComplianceEngine()
        info = engine.identify_license("CustomLicense-1.0")

        assert info.category == LicenseCategory.UNKNOWN
        assert info.osi_approved is False

    def test_identify_none_license(self, test_config):
        """Test identifying when no license specified."""
        engine = LicenseComplianceEngine()
        info = engine.identify_license(None)

        assert info.spdx_id == "NOASSERTION"
        assert info.category == LicenseCategory.UNKNOWN

    def test_identify_license_alias(self, test_config):
        """Test identifying license from alias."""
        engine = LicenseComplianceEngine()

        # Test various aliases
        info1 = engine.identify_license("MIT License")
        assert info1.spdx_id == "MIT"

        info2 = engine.identify_license("Apache License 2.0")
        assert info2.spdx_id == "Apache-2.0"

        info3 = engine.identify_license("BSD")
        assert info3.spdx_id == "BSD-3-Clause"

    def test_identify_case_insensitive(self, test_config):
        """Test case-insensitive license lookup."""
        engine = LicenseComplianceEngine()

        info = engine.identify_license("mit")
        assert info.spdx_id == "MIT"

        info = engine.identify_license("APACHE-2.0")
        assert info.spdx_id == "Apache-2.0"


class TestLicenseExpressions:
    """Tests for SPDX license expression parsing."""

    def test_or_expression(self, test_config):
        """Test parsing OR license expression."""
        engine = LicenseComplianceEngine()
        info = engine.identify_license("MIT OR Apache-2.0")

        assert "MIT" in info.spdx_id or "Apache" in info.spdx_id
        assert info.category == LicenseCategory.PERMISSIVE
        # OR expression means choice - use most permissive

    def test_and_expression(self, test_config):
        """Test parsing AND license expression."""
        engine = LicenseComplianceEngine()
        info = engine.identify_license("MIT AND BSD-3-Clause")

        assert "MIT" in info.spdx_id or "BSD" in info.spdx_id
        assert info.category == LicenseCategory.PERMISSIVE


class TestComplianceChecking:
    """Tests for compliance checking."""

    def test_check_compliant_sbom(self, test_config, permissive_policy):
        """Test checking a compliant SBOM."""
        # Create a SBOM that only contains permissive licenses
        compliant_sbom = SBOMDocument(
            sbom_id="sbom-compliant-001",
            name="compliant-project",
            version="1.0.0",
            format=SBOMFormat.INTERNAL,
            spec_version="1.0",
            repository_id="repo-compliant",
            created_at=datetime.now(timezone.utc),
            components=[
                SBOMComponent(
                    name="requests", version="2.31.0", licenses=["Apache-2.0"]
                ),
                SBOMComponent(name="urllib3", version="2.0.7", licenses=["MIT"]),
                SBOMComponent(name="idna", version="3.6", licenses=["BSD-3-Clause"]),
            ],
        )

        engine = LicenseComplianceEngine()
        report = engine.check_compliance(compliant_sbom, permissive_policy)

        assert report.status in (ComplianceStatus.COMPLIANT, ComplianceStatus.WARNING)
        assert report.components_analyzed == len(compliant_sbom.components)

    def test_check_sbom_with_gpl(self, test_config, permissive_policy):
        """Test checking SBOM with GPL component."""
        engine = LicenseComplianceEngine()
        sbom = SBOMDocument(
            sbom_id="gpl-sbom",
            name="test",
            version="1.0.0",
            format=SBOMFormat.INTERNAL,
            spec_version="1.0",
            repository_id="repo",
            created_at=datetime.now(timezone.utc),
            components=[
                SBOMComponent(
                    name="gpl-package",
                    version="1.0.0",
                    licenses=["GPL-3.0-only"],
                ),
            ],
        )

        report = engine.check_compliance(sbom, permissive_policy)

        assert report.status == ComplianceStatus.VIOLATION
        assert report.violation_count == 1
        assert report.violations[0].detected_license == "GPL-3.0-only"

    def test_check_sbom_with_unknown_license(self, test_config, strict_policy):
        """Test checking SBOM with unknown license."""
        engine = LicenseComplianceEngine()
        sbom = SBOMDocument(
            sbom_id="unknown-sbom",
            name="test",
            version="1.0.0",
            format=SBOMFormat.INTERNAL,
            spec_version="1.0",
            repository_id="repo",
            created_at=datetime.now(timezone.utc),
            components=[
                SBOMComponent(
                    name="unknown-package",
                    version="1.0.0",
                    licenses=["CustomLicense"],
                ),
            ],
        )

        report = engine.check_compliance(sbom, strict_policy)

        # Strict policy doesn't allow unknown licenses
        assert report.status in (ComplianceStatus.VIOLATION, ComplianceStatus.WARNING)

    def test_check_empty_sbom(self, test_config, permissive_policy):
        """Test checking empty SBOM."""
        engine = LicenseComplianceEngine()
        sbom = SBOMDocument(
            sbom_id="empty-sbom",
            name="empty",
            version="1.0.0",
            format=SBOMFormat.INTERNAL,
            spec_version="1.0",
            repository_id="repo",
            created_at=datetime.now(timezone.utc),
            components=[],
        )

        report = engine.check_compliance(sbom, permissive_policy)

        assert report.status == ComplianceStatus.COMPLIANT
        assert report.components_analyzed == 0
        assert report.violation_count == 0

    def test_check_osi_requirement(self, test_config):
        """Test OSI approval requirement."""
        engine = LicenseComplianceEngine()

        # Policy requiring OSI approved
        policy = LicensePolicy(
            name="osi-only",
            allowed_categories=[LicenseCategory.PERMISSIVE],
            prohibited_licenses=[],
            require_osi_approved=True,
            allow_unknown=False,
        )

        sbom = SBOMDocument(
            sbom_id="test",
            name="test",
            version="1.0.0",
            format=SBOMFormat.INTERNAL,
            spec_version="1.0",
            repository_id="repo",
            created_at=datetime.now(timezone.utc),
            components=[
                SBOMComponent(
                    name="mit-package",
                    version="1.0.0",
                    licenses=["MIT"],  # OSI approved
                ),
            ],
        )

        report = engine.check_compliance(sbom, policy)
        assert report.status == ComplianceStatus.COMPLIANT


class TestLicenseCompatibility:
    """Tests for license compatibility checking."""

    def test_compatible_permissive_licenses(self, test_config):
        """Test compatibility of permissive licenses."""
        engine = LicenseComplianceEngine()
        result = engine.check_compatibility(["MIT", "Apache-2.0", "BSD-3-Clause"])

        assert result.compatible is True
        assert result.allows_proprietary is True

    def test_incompatible_gpl_proprietary(self, test_config):
        """Test incompatibility of GPL with proprietary."""
        engine = LicenseComplianceEngine()
        # Simulating a GPL component combined with proprietary
        result = engine.check_compatibility(["GPL-3.0-only", "Proprietary"])

        assert result.compatible is False

    def test_weak_copyleft_compatibility(self, test_config):
        """Test weak copyleft compatibility."""
        engine = LicenseComplianceEngine()
        result = engine.check_compatibility(["MIT", "LGPL-3.0-only"])

        # Weak copyleft with permissive is generally compatible
        assert result.compatible is True

    def test_empty_licenses(self, test_config):
        """Test compatibility with no licenses."""
        engine = LicenseComplianceEngine()
        result = engine.check_compatibility([])

        assert result.compatible is True
        assert result.allows_proprietary is True


class TestAttributionGeneration:
    """Tests for attribution file generation."""

    def test_generate_markdown_attribution(self, test_config, sample_sbom):
        """Test generating markdown attribution."""
        engine = LicenseComplianceEngine()
        attribution = engine.generate_attribution(sample_sbom, format="markdown")

        assert "# Third-Party Software Attribution" in attribution
        assert "requests" in attribution
        assert "Apache-2.0" in attribution

    def test_generate_text_attribution(self, test_config, sample_sbom):
        """Test generating text attribution."""
        engine = LicenseComplianceEngine()
        attribution = engine.generate_attribution(sample_sbom, format="text")

        assert "THIRD-PARTY SOFTWARE ATTRIBUTION" in attribution
        assert "requests" in attribution

    def test_generate_html_attribution(self, test_config, sample_sbom):
        """Test generating HTML attribution."""
        engine = LicenseComplianceEngine()
        attribution = engine.generate_attribution(sample_sbom, format="html")

        assert "<!DOCTYPE html>" in attribution
        assert "Third-Party Software Attribution" in attribution
        assert "<table>" in attribution
        assert "requests" in attribution

    def test_attribution_sorted_by_name(self, test_config, sample_sbom):
        """Test that attribution is sorted by component name."""
        engine = LicenseComplianceEngine()
        attribution = engine.generate_attribution(sample_sbom, format="text")

        # Components should be sorted alphabetically
        lines = attribution.split("\n")
        component_lines = [
            line
            for line in lines
            if line
            and not line.startswith(" ")
            and not line.startswith("=")
            and not line.startswith("-")
        ]
        # Filter to get component names
        names = [line.split(" (")[0] for line in component_lines if "(" in line]
        assert names == sorted(names, key=str.lower)


class TestPolicyEnforcement:
    """Tests for policy enforcement."""

    def test_enforce_policy_compliant(self, test_config, permissive_policy):
        """Test enforcing policy on compliant component."""
        engine = LicenseComplianceEngine()
        component = SBOMComponent(
            name="compliant",
            version="1.0.0",
            licenses=["MIT"],
        )

        violation = engine.enforce_policy(component, permissive_policy)
        assert violation is None

    def test_enforce_policy_violation(self, test_config, permissive_policy):
        """Test enforcing policy catches violation."""
        engine = LicenseComplianceEngine()
        component = SBOMComponent(
            name="gpl-package",
            version="1.0.0",
            licenses=["GPL-3.0-only"],
        )

        # Should raise for high severity violation
        with pytest.raises(PolicyViolationError) as exc_info:
            engine.enforce_policy(component, permissive_policy)

        assert "GPL-3.0-only" in str(exc_info.value)
        assert exc_info.value.license_id == "GPL-3.0-only"


class TestEngineSingleton:
    """Tests for engine singleton pattern."""

    def test_get_engine(self, test_config):
        """Test getting singleton engine."""
        engine1 = get_license_compliance_engine()
        engine2 = get_license_compliance_engine()
        assert engine1 is engine2

    def test_reset_engine(self, test_config):
        """Test resetting singleton."""
        engine1 = get_license_compliance_engine()
        reset_license_compliance_engine()
        engine2 = get_license_compliance_engine()
        assert engine1 is not engine2


class TestEngineDisabled:
    """Tests for disabled engine behavior."""

    def test_compliance_check_when_disabled(self, test_config):
        """Test compliance check when engine is disabled."""
        from src.services.supply_chain import set_supply_chain_config
        from src.services.supply_chain.config import SupplyChainConfig

        config = SupplyChainConfig.for_testing()
        config.license.enabled = False
        set_supply_chain_config(config)

        engine = LicenseComplianceEngine()
        sbom = SBOMDocument(
            sbom_id="test",
            name="test",
            version="1.0.0",
            format=SBOMFormat.INTERNAL,
            spec_version="1.0",
            repository_id="repo",
            created_at=datetime.now(timezone.utc),
            components=[
                SBOMComponent(name="test", version="1.0.0", licenses=["GPL-3.0-only"]),
            ],
        )

        report = engine.check_compliance(sbom)

        assert report.status == ComplianceStatus.UNKNOWN
        assert report.components_analyzed == 0


class TestLicenseCategories:
    """Tests for various license categories."""

    @pytest.mark.parametrize(
        "license_id,expected_category",
        [
            ("MIT", LicenseCategory.PERMISSIVE),
            ("Apache-2.0", LicenseCategory.PERMISSIVE),
            ("BSD-3-Clause", LicenseCategory.PERMISSIVE),
            ("ISC", LicenseCategory.PERMISSIVE),
            ("Unlicense", LicenseCategory.PUBLIC_DOMAIN),
            ("CC0-1.0", LicenseCategory.PUBLIC_DOMAIN),
            ("LGPL-3.0-only", LicenseCategory.WEAK_COPYLEFT),
            ("MPL-2.0", LicenseCategory.WEAK_COPYLEFT),
            ("GPL-3.0-only", LicenseCategory.STRONG_COPYLEFT),
            ("AGPL-3.0-only", LicenseCategory.STRONG_COPYLEFT),
            ("Proprietary", LicenseCategory.PROPRIETARY),
        ],
    )
    def test_license_categories(self, test_config, license_id, expected_category):
        """Test license category identification."""
        engine = LicenseComplianceEngine()
        info = engine.identify_license(license_id)
        assert info.category == expected_category
