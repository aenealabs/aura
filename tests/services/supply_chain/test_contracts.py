"""
Tests for supply chain security contracts (enums and dataclasses).
"""

from datetime import datetime, timezone

from src.services.supply_chain import (
    Attestation,
    ComplianceReport,
    ComplianceStatus,
    ConfusionIndicator,
    ConfusionResult,
    ConfusionType,
    LicenseCategory,
    LicenseViolation,
    ProvenanceChain,
    RiskLevel,
    SBOMComponent,
    SBOMDocument,
    SBOMFormat,
    SigningMethod,
    VerificationStatus,
)


class TestSBOMFormatEnum:
    """Tests for SBOMFormat enum."""

    def test_cyclonedx_formats(self):
        """Test CycloneDX format values."""
        assert SBOMFormat.CYCLONEDX_1_5_JSON.value == "cyclonedx-1.5-json"
        assert SBOMFormat.CYCLONEDX_1_5_XML.value == "cyclonedx-1.5-xml"
        assert SBOMFormat.CYCLONEDX_1_4_JSON.value == "cyclonedx-1.4-json"

    def test_spdx_formats(self):
        """Test SPDX format values."""
        assert SBOMFormat.SPDX_2_3_JSON.value == "spdx-2.3-json"
        assert SBOMFormat.SPDX_2_3_RDF.value == "spdx-2.3-rdf"

    def test_internal_format(self):
        """Test internal format value."""
        assert SBOMFormat.INTERNAL.value == "internal"


class TestSigningMethodEnum:
    """Tests for SigningMethod enum."""

    def test_sigstore_methods(self):
        """Test Sigstore signing method values."""
        assert SigningMethod.SIGSTORE_KEYLESS.value == "sigstore-keyless"

    def test_other_methods(self):
        """Test other signing method values."""
        assert SigningMethod.OFFLINE_KEY.value == "offline-key"
        assert SigningMethod.HSM.value == "hsm"
        assert SigningMethod.NONE.value == "none"


class TestConfusionTypeEnum:
    """Tests for ConfusionType enum."""

    def test_confusion_types(self):
        """Test confusion type values."""
        assert ConfusionType.TYPOSQUATTING.value == "typosquatting"
        assert ConfusionType.NAMESPACE_HIJACK.value == "namespace-hijack"
        assert ConfusionType.VERSION_CONFUSION.value == "version-confusion"
        assert ConfusionType.NONE.value == "none"


class TestLicenseCategoryEnum:
    """Tests for LicenseCategory enum."""

    def test_license_categories(self):
        """Test license category values."""
        assert LicenseCategory.PERMISSIVE.value == "permissive"
        assert LicenseCategory.WEAK_COPYLEFT.value == "weak-copyleft"
        assert LicenseCategory.STRONG_COPYLEFT.value == "strong-copyleft"
        assert LicenseCategory.PROPRIETARY.value == "proprietary"
        assert LicenseCategory.PUBLIC_DOMAIN.value == "public-domain"
        assert LicenseCategory.UNKNOWN.value == "unknown"


class TestRiskLevelEnum:
    """Tests for RiskLevel enum."""

    def test_risk_level_ordering(self):
        """Test that risk levels are ordered by severity."""
        assert RiskLevel.NONE.value < RiskLevel.LOW.value
        assert RiskLevel.LOW.value < RiskLevel.MEDIUM.value
        assert RiskLevel.MEDIUM.value < RiskLevel.HIGH.value
        assert RiskLevel.HIGH.value < RiskLevel.CRITICAL.value


class TestSBOMComponent:
    """Tests for SBOMComponent dataclass."""

    def test_create_minimal_component(self):
        """Test creating component with minimal fields."""
        component = SBOMComponent(
            name="test-package",
            version="1.0.0",
        )
        assert component.name == "test-package"
        assert component.version == "1.0.0"
        assert component.purl is None
        assert component.licenses == []
        assert component.hashes == {}
        assert component.is_direct is True

    def test_create_full_component(self):
        """Test creating component with all fields."""
        component = SBOMComponent(
            name="requests",
            version="2.31.0",
            purl="pkg:pypi/requests@2.31.0",
            component_type="library",
            supplier="Kenneth Reitz",
            licenses=["Apache-2.0"],
            hashes={"sha256": "abc123"},
            is_direct=True,
        )
        assert component.name == "requests"
        assert component.purl == "pkg:pypi/requests@2.31.0"
        assert "Apache-2.0" in component.licenses
        assert component.hashes["sha256"] == "abc123"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        component = SBOMComponent(
            name="test",
            version="1.0.0",
            licenses=["MIT"],
        )
        data = component.to_dict()
        assert data["name"] == "test"
        assert data["version"] == "1.0.0"
        assert "MIT" in data["licenses"]


class TestSBOMDocument:
    """Tests for SBOMDocument dataclass."""

    def test_create_sbom_document(self, sample_components):
        """Test creating SBOM document."""
        sbom = SBOMDocument(
            sbom_id="sbom-123",
            name="test-project",
            version="1.0.0",
            format=SBOMFormat.CYCLONEDX_1_5_JSON,
            spec_version="1.5",
            repository_id="repo-001",
            created_at=datetime.now(timezone.utc),
            components=sample_components,
        )
        assert sbom.sbom_id == "sbom-123"
        assert sbom.format == SBOMFormat.CYCLONEDX_1_5_JSON
        assert len(sbom.components) == len(sample_components)

    def test_to_dict(self, sample_sbom):
        """Test serialization to dictionary."""
        data = sample_sbom.to_dict()
        assert data["sbom_id"] == sample_sbom.sbom_id
        assert data["format"] == sample_sbom.format.value
        assert len(data["components"]) == len(sample_sbom.components)


class TestAttestation:
    """Tests for Attestation dataclass."""

    def test_create_attestation(self):
        """Test creating attestation."""
        attestation = Attestation(
            attestation_id="att-123",
            sbom_id="sbom-123",
            predicate_type="https://in-toto.io/attestation/sbom/v1",
            subject_digest="sha256:abc123",
            signature="base64-signature",
            signing_method=SigningMethod.SIGSTORE_KEYLESS,
            created_at=datetime.now(timezone.utc),
        )
        assert attestation.attestation_id == "att-123"
        assert attestation.signing_method == SigningMethod.SIGSTORE_KEYLESS
        assert attestation.rekor_log_index is None

    def test_attestation_with_rekor(self):
        """Test attestation with Rekor transparency log."""
        attestation = Attestation(
            attestation_id="att-456",
            sbom_id="sbom-123",
            predicate_type="https://in-toto.io/attestation/sbom/v1",
            subject_digest="sha256:abc123",
            signature="base64-signature",
            signing_method=SigningMethod.SIGSTORE_KEYLESS,
            created_at=datetime.now(timezone.utc),
            rekor_log_index=12345678,
            rekor_uuid="uuid-abc-123",
        )
        assert attestation.rekor_log_index == 12345678
        assert attestation.rekor_uuid == "uuid-abc-123"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        attestation = Attestation(
            attestation_id="att-789",
            sbom_id="sbom-456",
            predicate_type="test",
            subject_digest="sha256:xyz",
            signature="sig",
            signing_method=SigningMethod.OFFLINE_KEY,
            created_at=datetime.now(timezone.utc),
        )
        data = attestation.to_dict()
        assert data["attestation_id"] == "att-789"
        assert data["signing_method"] == "offline-key"


class TestConfusionResult:
    """Tests for ConfusionResult dataclass."""

    def test_create_result_no_confusion(self):
        """Test result with no confusion detected."""
        result = ConfusionResult(
            package_name="requests",
            version="2.31.0",
            ecosystem="pypi",
            risk_level=RiskLevel.NONE,
            indicators=[],
            is_safe=True,
            analyzed_at=datetime.now(timezone.utc),
        )
        assert result.risk_level == RiskLevel.NONE
        assert len(result.indicators) == 0
        assert result.is_safe is True

    def test_create_result_with_typosquatting(self):
        """Test result with typosquatting detected."""
        result = ConfusionResult(
            package_name="requets",
            version="1.0.0",
            ecosystem="pypi",
            risk_level=RiskLevel.HIGH,
            indicators=[
                ConfusionIndicator(
                    confusion_type=ConfusionType.TYPOSQUATTING,
                    description="Name similar to 'requests'",
                    evidence={"distance": 1},
                    confidence=0.9,
                    similar_package="requests",
                )
            ],
            is_safe=False,
            recommendation="Verify package is intentional",
            analyzed_at=datetime.now(timezone.utc),
        )
        assert result.risk_level == RiskLevel.HIGH
        assert len(result.indicators) == 1
        assert result.indicators[0].confidence == 0.9
        assert result.indicators[0].confusion_type == ConfusionType.TYPOSQUATTING


class TestLicenseViolation:
    """Tests for LicenseViolation dataclass."""

    def test_create_violation(self):
        """Test creating license violation."""
        violation = LicenseViolation(
            violation_id="viol-001",
            component_name="gpl-package",
            component_version="1.0.0",
            detected_license="GPL-3.0-only",
            violation_type="prohibited_license",
            severity=RiskLevel.HIGH,
            policy_rule="prohibited_licenses",
            description="GPL-3.0 is in prohibited list",
            recommendation="Remove or replace this component",
        )
        assert violation.detected_license == "GPL-3.0-only"
        assert violation.violation_type == "prohibited_license"
        assert violation.severity == RiskLevel.HIGH


class TestComplianceReport:
    """Tests for ComplianceReport dataclass."""

    def test_create_compliant_report(self):
        """Test creating compliant report."""
        report = ComplianceReport(
            report_id="report-001",
            repository_id="repo-001",
            sbom_id="sbom-001",
            status=ComplianceStatus.COMPLIANT,
            violations=[],
            components_analyzed=10,
            components_compliant=10,
        )
        assert report.status == ComplianceStatus.COMPLIANT
        assert len(report.violations) == 0
        assert report.compliance_rate == 100.0

    def test_create_violation_report(self):
        """Test creating report with violations."""
        violation = LicenseViolation(
            violation_id="viol-001",
            component_name="test",
            component_version="1.0.0",
            detected_license="GPL-3.0-only",
            violation_type="prohibited",
            severity=RiskLevel.HIGH,
            policy_rule="prohibited_licenses",
            description="Prohibited license",
            recommendation="Remove component",
        )
        report = ComplianceReport(
            report_id="report-002",
            repository_id="repo-001",
            sbom_id="sbom-001",
            status=ComplianceStatus.NON_COMPLIANT,
            violations=[violation],
            components_analyzed=10,
            components_compliant=9,
        )
        assert report.status == ComplianceStatus.NON_COMPLIANT
        assert len(report.violations) == 1


class TestProvenanceChain:
    """Tests for ProvenanceChain dataclass."""

    def test_create_provenance_chain(self):
        """Test creating provenance chain."""
        chain = ProvenanceChain(
            package_url="pkg:pypi/requests@2.31.0",
            attestations=[{"attestation_id": "att-1"}],
            sbom_ids=["sbom-1", "sbom-2"],
            verified=True,
            verification_status=VerificationStatus.VERIFIED,
            latest_attestation_id="att-1",
            latest_attestation_at=datetime.now(timezone.utc),
        )
        assert chain.verified is True
        assert len(chain.sbom_ids) == 2
        assert chain.latest_attestation_id == "att-1"
        assert chain.purl == "pkg:pypi/requests@2.31.0"

    def test_unverified_chain(self):
        """Test unverified provenance chain."""
        chain = ProvenanceChain(
            package_url="pkg:pypi/unknown@1.0.0",
            attestations=[],
            sbom_ids=[],
            verified=False,
            verification_status=VerificationStatus.NOT_VERIFIED,
        )
        assert chain.verified is False
        assert chain.verification_status == VerificationStatus.NOT_VERIFIED
        assert chain.sboms == []  # Test alias


class TestLicensePolicy:
    """Tests for LicensePolicy dataclass."""

    def test_create_permissive_policy(self, permissive_policy):
        """Test permissive policy fixture."""
        assert permissive_policy.name == "permissive-only"
        assert LicenseCategory.PERMISSIVE in permissive_policy.allowed_categories
        assert "GPL-3.0-only" in permissive_policy.prohibited_licenses

    def test_create_strict_policy(self, strict_policy):
        """Test strict policy fixture."""
        assert strict_policy.require_osi_approved is True
        assert strict_policy.allow_unknown is False
        assert len(strict_policy.prohibited_licenses) >= 6
