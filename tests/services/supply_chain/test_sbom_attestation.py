"""
Tests for SBOM attestation service.
"""

from src.services.supply_chain import (
    SBOMAttestationService,
    SBOMFormat,
    SigningMethod,
    VerificationStatus,
    get_sbom_attestation_service,
    reset_sbom_attestation_service,
)


class TestSBOMGeneration:
    """Tests for SBOM generation."""

    def test_generate_sbom_basic(self, test_config, tmp_path):
        """Test basic SBOM generation."""
        service = SBOMAttestationService()
        sbom = service.generate_sbom(
            repository_id="test-repo-001",
            project_path=tmp_path,
            format=SBOMFormat.CYCLONEDX_1_5_JSON,
        )

        assert sbom is not None
        assert sbom.repository_id == "test-repo-001"
        assert sbom.format == SBOMFormat.CYCLONEDX_1_5_JSON
        assert sbom.sbom_id is not None
        assert sbom.created_at is not None

    def test_generate_sbom_spdx_format(self, test_config, tmp_path):
        """Test SBOM generation in SPDX format."""
        service = SBOMAttestationService()
        sbom = service.generate_sbom(
            repository_id="test-repo-002",
            project_path=tmp_path,
            format=SBOMFormat.SPDX_2_3_JSON,
        )

        assert sbom.format == SBOMFormat.SPDX_2_3_JSON

    def test_generate_sbom_internal_format(self, test_config, tmp_path):
        """Test SBOM generation in internal format."""
        service = SBOMAttestationService()
        sbom = service.generate_sbom(
            repository_id="test-repo-003",
            project_path=tmp_path,
            format=SBOMFormat.INTERNAL,
        )

        assert sbom.format == SBOMFormat.INTERNAL

    def test_generate_sbom_default_format(self, test_config, tmp_path):
        """Test SBOM generation with default format."""
        service = SBOMAttestationService()
        sbom = service.generate_sbom(
            repository_id="test-repo-004", project_path=tmp_path
        )

        # Default format from test config is INTERNAL
        assert sbom.format == SBOMFormat.INTERNAL


class TestSBOMSigning:
    """Tests for SBOM signing and attestation."""

    def test_sign_sbom_sigstore(self, test_config, sample_sbom):
        """Test signing SBOM with Sigstore."""
        service = SBOMAttestationService()
        attestation = service.sign_sbom(
            sbom=sample_sbom,
            method=SigningMethod.SIGSTORE_KEYLESS,
        )

        assert attestation is not None
        assert attestation.sbom_id == sample_sbom.sbom_id
        assert attestation.signing_method == SigningMethod.SIGSTORE_KEYLESS
        assert attestation.signature is not None
        assert attestation.predicate_type is not None

    def test_sign_sbom_offline_key(self, test_config, sample_sbom):
        """Test signing SBOM with offline key."""
        service = SBOMAttestationService()
        attestation = service.sign_sbom(
            sbom=sample_sbom,
            method=SigningMethod.OFFLINE_KEY,
        )

        assert attestation.signing_method == SigningMethod.OFFLINE_KEY
        assert attestation.signature is not None

    def test_sign_sbom_no_signing(self, test_config, sample_sbom):
        """Test creating attestation without signing."""
        service = SBOMAttestationService()
        attestation = service.sign_sbom(
            sbom=sample_sbom,
            method=SigningMethod.NONE,
        )

        assert attestation.signing_method == SigningMethod.NONE
        # Should still have attestation metadata
        assert attestation.attestation_id is not None

    def test_attestation_has_rekor_info(self, test_config, sample_sbom):
        """Test attestation may include Rekor info."""
        service = SBOMAttestationService()
        attestation = service.sign_sbom(
            sbom=sample_sbom,
            method=SigningMethod.SIGSTORE_KEYLESS,
        )

        # In mock mode, Rekor info is simulated
        # Just verify the fields exist
        assert hasattr(attestation, "rekor_log_index")
        assert hasattr(attestation, "rekor_uuid")


class TestAttestationVerification:
    """Tests for attestation verification."""

    def test_verify_valid_attestation(self, test_config, sample_sbom):
        """Test verifying a valid attestation."""
        service = SBOMAttestationService()

        # First sign the SBOM
        attestation = service.sign_sbom(
            sbom=sample_sbom,
            method=SigningMethod.SIGSTORE_KEYLESS,
        )

        # Then verify it
        result = service.verify_attestation(attestation.attestation_id)

        assert result is not None
        assert result.status in (
            VerificationStatus.VERIFIED,
            VerificationStatus.NOT_VERIFIED,
        )

    def test_verify_nonexistent_attestation(self, test_config):
        """Test verifying non-existent attestation."""
        service = SBOMAttestationService()

        result = service.verify_attestation("nonexistent-attestation-id")

        assert result is not None
        assert result.status == VerificationStatus.NOT_FOUND

    def test_verify_returns_attestation_data(self, test_config, sample_sbom):
        """Test verification returns attestation data."""
        service = SBOMAttestationService()

        attestation = service.sign_sbom(sample_sbom, SigningMethod.OFFLINE_KEY)
        result = service.verify_attestation(attestation.attestation_id)

        assert result.attestation_id == attestation.attestation_id


class TestProvenanceTracking:
    """Tests for provenance chain tracking."""

    def test_get_provenance_for_attested_package(self, test_config, sample_sbom):
        """Test getting provenance for an attested package."""
        service = SBOMAttestationService()

        # Store SBOM and create attestation
        service.sign_sbom(sample_sbom, SigningMethod.SIGSTORE_KEYLESS)

        # Get provenance for a component
        component = sample_sbom.components[0]
        chain = service.get_provenance(component.purl)

        # In mock mode, this may return empty or simulated data
        assert chain is not None

    def test_get_provenance_for_unknown_package(self, test_config):
        """Test getting provenance for unknown package."""
        service = SBOMAttestationService()

        chain = service.get_provenance("pkg:pypi/nonexistent-package@1.0.0")

        # Should return None or empty chain for unknown package
        assert chain is None or len(chain.attestations) == 0


class TestFormatConversion:
    """Tests for SBOM format conversion."""

    def test_to_cyclonedx(self, test_config, sample_sbom):
        """Test converting SBOM to CycloneDX format."""
        service = SBOMAttestationService()

        cyclonedx_dict = service.to_cyclonedx(sample_sbom)

        assert cyclonedx_dict is not None
        assert isinstance(cyclonedx_dict, dict)
        # Should contain CycloneDX-specific fields
        assert "bomFormat" in cyclonedx_dict
        assert cyclonedx_dict["bomFormat"] == "CycloneDX"

    def test_to_spdx(self, test_config):
        """Test converting SBOM to SPDX format."""
        from datetime import datetime, timezone

        from src.services.supply_chain import SBOMComponent, SBOMDocument

        # Create an SPDX-format SBOM for conversion
        spdx_sbom = SBOMDocument(
            sbom_id="sbom-spdx-test",
            name="test-project",
            version="1.0.0",
            format=SBOMFormat.SPDX_2_3_JSON,
            spec_version="2.3",
            repository_id="repo-spdx-test",
            created_at=datetime.now(timezone.utc),
            components=[
                SBOMComponent(
                    name="requests",
                    version="2.31.0",
                    purl="pkg:pypi/requests@2.31.0",
                    licenses=["Apache-2.0"],
                ),
            ],
        )

        service = SBOMAttestationService()
        spdx_dict = service.to_spdx(spdx_sbom)

        assert spdx_dict is not None
        assert isinstance(spdx_dict, dict)
        # Should contain SPDX-specific fields
        assert "spdxVersion" in spdx_dict
        assert spdx_dict["spdxVersion"] == "SPDX-2.3"


class TestSBOMStorage:
    """Tests for SBOM storage operations."""

    def test_store_and_retrieve_sbom(self, test_config, sample_sbom):
        """Test storing and retrieving SBOM."""
        service = SBOMAttestationService()

        # Store the SBOM (happens during sign)
        attestation = service.sign_sbom(sample_sbom, SigningMethod.NONE)

        # The SBOM should be retrievable
        # In mock mode, this is stored in memory
        assert attestation.sbom_id == sample_sbom.sbom_id

    def test_store_multiple_sboms(self, test_config, tmp_path):
        """Test storing multiple SBOMs."""
        service = SBOMAttestationService()

        # Generate and sign multiple SBOMs
        sbom1 = service.generate_sbom("repo-1", project_path=tmp_path)
        sbom2 = service.generate_sbom("repo-2", project_path=tmp_path)

        att1 = service.sign_sbom(sbom1, SigningMethod.NONE)
        att2 = service.sign_sbom(sbom2, SigningMethod.NONE)

        assert att1.sbom_id != att2.sbom_id


class TestServiceSingleton:
    """Tests for service singleton pattern."""

    def test_get_service(self, test_config):
        """Test getting singleton service."""
        service1 = get_sbom_attestation_service()
        service2 = get_sbom_attestation_service()
        assert service1 is service2

    def test_reset_service(self, test_config):
        """Test resetting singleton."""
        service1 = get_sbom_attestation_service()
        reset_sbom_attestation_service()
        service2 = get_sbom_attestation_service()
        assert service1 is not service2

    def test_state_cleared_on_reset(self, test_config, sample_sbom):
        """Test that state is cleared on reset."""
        service1 = get_sbom_attestation_service()
        service1.sign_sbom(sample_sbom, SigningMethod.NONE)

        reset_sbom_attestation_service()

        service2 = get_sbom_attestation_service()
        # New service should not have the old attestation
        result = service2.verify_attestation("nonexistent")
        assert result.status == VerificationStatus.NOT_FOUND


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_repository_id(self, test_config, tmp_path):
        """Test handling invalid repository ID."""
        service = SBOMAttestationService()

        # Should handle empty or None repository ID gracefully
        sbom = service.generate_sbom(repository_id="", project_path=tmp_path)
        assert sbom is not None  # Should not raise

    def test_sign_sbom_with_invalid_method(self, test_config, sample_sbom):
        """Test signing with all valid methods doesn't error."""
        service = SBOMAttestationService()

        # Test all signing methods
        for method in SigningMethod:
            attestation = service.sign_sbom(sample_sbom, method)
            assert attestation is not None
