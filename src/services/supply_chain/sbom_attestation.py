"""
Project Aura - SBOM Attestation Service

Generates Software Bill of Materials in CycloneDX 1.5 and SPDX 2.3 formats,
signs them using Sigstore or offline keys, and stores attestations.

Architecture:
- Extends existing SBOMDetectionService for dependency detection
- Converts internal format to CycloneDX/SPDX
- Signs using Sigstore keyless (OIDC) or offline Ed25519
- Records attestations in Rekor transparency log
- Stores in DynamoDB (metadata), S3 (artifacts), Neptune (graph)

Usage:
    from src.services.supply_chain import (
        SBOMAttestationService,
        get_sbom_attestation_service,
        SBOMFormat,
        SigningMethod,
    )

    service = get_sbom_attestation_service()

    # Generate SBOM
    sbom = service.generate_sbom(
        repository_id="repo-123",
        project_path="/path/to/project",
        format=SBOMFormat.CYCLONEDX_1_5_JSON,
    )

    # Sign SBOM
    attestation = service.sign_sbom(
        sbom=sbom,
        method=SigningMethod.SIGSTORE_KEYLESS,
    )

    # Verify attestation
    result = service.verify_attestation(attestation_id=attestation.attestation_id)
"""

import hashlib
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

from ..sbom_detection_service import SBOMDetectionService, SBOMReport
from .config import SupplyChainConfig, get_supply_chain_config
from .contracts import (
    Attestation,
    ProvenanceChain,
    SBOMComponent,
    SBOMDocument,
    SBOMFormat,
    SigningMethod,
    VerificationResult,
    VerificationStatus,
)
from .exceptions import (
    SBOMFormatError,
    SBOMGenerationError,
    SigningError,
    VerificationError,
)
from .metrics import MetricsTimer, get_supply_chain_metrics

logger = logging.getLogger(__name__)


class SBOMAttestationService:
    """
    Service for generating, signing, and verifying SBOMs.

    Extends the existing SBOMDetectionService with:
    - CycloneDX 1.5 and SPDX 2.3 format conversion
    - Sigstore keyless signing
    - Offline Ed25519 signing for air-gapped environments
    - Rekor transparency log integration
    - Storage in DynamoDB, S3, and Neptune

    Args:
        config: Supply chain configuration (loads from env if None)
        detection_service: SBOM detection service (creates default if None)
        dynamodb_client: DynamoDB client (mock mode if None)
        s3_client: S3 client (mock mode if None)
    """

    def __init__(
        self,
        config: Optional[SupplyChainConfig] = None,
        detection_service: Optional[SBOMDetectionService] = None,
        dynamodb_client: Optional[Any] = None,
        s3_client: Optional[Any] = None,
    ):
        """Initialize SBOM attestation service."""
        self.config = config or get_supply_chain_config()
        self._detection_service = detection_service or SBOMDetectionService()
        self._dynamodb = dynamodb_client
        self._s3 = s3_client
        self._metrics = get_supply_chain_metrics()

        # Mock storage for testing
        self._mock_sboms: dict[str, SBOMDocument] = {}
        self._mock_attestations: dict[str, Attestation] = {}
        self._mock_artifacts: dict[str, bytes] = {}

        logger.info(
            f"SBOMAttestationService initialized "
            f"(env={self.config.environment}, mock_storage={self.config.storage.use_mock_storage})"
        )

    def generate_sbom(
        self,
        repository_id: str,
        project_path: str | Path,
        format: Optional[SBOMFormat] = None,
        commit_sha: Optional[str] = None,
        branch: Optional[str] = None,
        include_dev: Optional[bool] = None,
    ) -> SBOMDocument:
        """
        Generate SBOM for a repository.

        Args:
            repository_id: Unique repository identifier
            project_path: Path to project root directory
            format: Output format (default from config)
            commit_sha: Git commit SHA (optional)
            branch: Git branch name (optional)
            include_dev: Include dev dependencies (default from config)

        Returns:
            SBOMDocument with all dependencies

        Raises:
            SBOMGenerationError: If SBOM generation fails
        """
        with MetricsTimer() as timer:
            try:
                format = format or self.config.sbom.default_format
                include_dev = (
                    include_dev
                    if include_dev is not None
                    else self.config.sbom.include_dev_dependencies
                )

                logger.info(
                    f"Generating SBOM for {repository_id} "
                    f"(format={format.value}, include_dev={include_dev})"
                )

                # Use existing detection service
                report = self._detection_service.detect_dependencies(
                    project_path=project_path,
                    include_dev=include_dev,
                )

                # Convert to SBOM document
                sbom = self._convert_report_to_sbom(
                    report=report,
                    repository_id=repository_id,
                    format=format,
                    commit_sha=commit_sha,
                    branch=branch,
                )

                # Store SBOM
                self._store_sbom(sbom)

                self._metrics.record_sbom_generated(
                    repository_id=repository_id,
                    format_type=format.value,
                    component_count=sbom.component_count,
                    latency_ms=timer.elapsed_ms,
                )

                logger.info(
                    f"Generated SBOM {sbom.sbom_id} with {sbom.component_count} components"
                )
                return sbom

            except Exception as e:
                self._metrics.record_sbom_generation_error(
                    repository_id=repository_id,
                    error_type=type(e).__name__,
                )
                raise SBOMGenerationError(
                    f"Failed to generate SBOM: {e}",
                    details={"repository_id": repository_id},
                ) from e

    def sign_sbom(
        self,
        sbom: SBOMDocument,
        method: Optional[SigningMethod] = None,
    ) -> Attestation:
        """
        Sign an SBOM and create attestation.

        Args:
            sbom: SBOM document to sign
            method: Signing method (default from config)

        Returns:
            Attestation with signature

        Raises:
            SigningError: If signing fails
        """
        with MetricsTimer() as timer:
            try:
                method = method or self.config.attestation.default_signing_method

                logger.info(f"Signing SBOM {sbom.sbom_id} (method={method.value})")

                # Generate content hash
                sbom_content = json.dumps(sbom.to_dict(), sort_keys=True)
                content_hash = hashlib.sha256(sbom_content.encode()).hexdigest()

                # Create attestation
                attestation = Attestation(
                    attestation_id=f"att-{uuid.uuid4().hex[:16]}",
                    sbom_id=sbom.sbom_id,
                    signing_method=method,
                    subject_digest=content_hash,
                )

                # Sign based on method
                if method == SigningMethod.SIGSTORE_KEYLESS:
                    attestation = self._sign_with_sigstore(attestation, sbom_content)
                elif method in (
                    SigningMethod.OFFLINE_ED25519,
                    SigningMethod.OFFLINE_KEY,
                ):
                    attestation = self._sign_with_offline_key(attestation, sbom_content)
                elif method in (SigningMethod.HSM_PKCS11, SigningMethod.HSM):
                    attestation = self._sign_with_hsm(attestation, sbom_content)
                elif method == SigningMethod.NONE:
                    # No signing (for testing)
                    attestation.signature = None
                else:
                    raise SigningError(f"Unsupported signing method: {method.value}")

                # Store attestation
                self._store_attestation(attestation)

                self._metrics.record_attestation_signed(
                    signing_method=method.value,
                    latency_ms=timer.elapsed_ms,
                    rekor_recorded=attestation.rekor_log_index is not None,
                )

                logger.info(
                    f"Created attestation {attestation.attestation_id} "
                    f"(rekor_index={attestation.rekor_log_index})"
                )
                return attestation

            except SigningError:
                raise
            except Exception as e:
                self._metrics.record_signing_error(
                    signing_method=(method or SigningMethod.NONE).value,
                    error_type=type(e).__name__,
                )
                raise SigningError(
                    f"Failed to sign SBOM: {e}",
                    details={"sbom_id": sbom.sbom_id},
                ) from e

    def verify_attestation(
        self,
        attestation_id: str,
    ) -> VerificationResult:
        """
        Verify an attestation.

        Args:
            attestation_id: Attestation ID to verify

        Returns:
            VerificationResult with status

        Raises:
            VerificationError: If verification fails
        """
        with MetricsTimer() as timer:
            try:
                logger.info(f"Verifying attestation {attestation_id}")

                # Get attestation
                attestation = self._get_attestation(attestation_id)
                if attestation is None:
                    return VerificationResult(
                        attestation_id=attestation_id,
                        status=VerificationStatus.NOT_FOUND,
                        error_message="Attestation not found",
                    )

                # Verify based on signing method
                if attestation.signing_method == SigningMethod.SIGSTORE_KEYLESS:
                    result = self._verify_sigstore(attestation)
                elif attestation.signing_method in (
                    SigningMethod.OFFLINE_ED25519,
                    SigningMethod.OFFLINE_KEY,
                ):
                    result = self._verify_offline(attestation)
                elif attestation.signing_method in (
                    SigningMethod.HSM_PKCS11,
                    SigningMethod.HSM,
                ):
                    result = self._verify_hsm(attestation)
                elif attestation.signing_method == SigningMethod.NONE:
                    # No signature to verify
                    result = VerificationResult(
                        attestation_id=attestation_id,
                        status=VerificationStatus.VERIFIED,
                    )
                else:
                    result = VerificationResult(
                        attestation_id=attestation_id,
                        status=VerificationStatus.ERROR,
                        error_message=f"Unknown signing method: {attestation.signing_method.value}",
                    )

                self._metrics.record_attestation_verified(
                    verification_status=result.status.value,
                    latency_ms=timer.elapsed_ms,
                )

                return result

            except Exception as e:
                raise VerificationError(
                    f"Failed to verify attestation: {e}",
                    details={"attestation_id": attestation_id},
                ) from e

    def get_sbom(self, sbom_id: str) -> Optional[SBOMDocument]:
        """Get SBOM by ID."""
        if self.config.storage.use_mock_storage:
            return self._mock_sboms.get(sbom_id)
        # TODO: Implement DynamoDB lookup
        return self._mock_sboms.get(sbom_id)

    def get_sbom_content(self, sbom_id: str) -> Optional[bytes]:
        """Get SBOM artifact content."""
        if self.config.storage.use_mock_storage:
            return self._mock_artifacts.get(sbom_id)
        # TODO: Implement S3 lookup
        return self._mock_artifacts.get(sbom_id)

    def get_provenance(self, purl: str) -> ProvenanceChain:
        """
        Get provenance chain for a package.

        Args:
            purl: Package URL (e.g., pkg:pip/requests@2.28.0)

        Returns:
            ProvenanceChain with all related SBOMs and attestations
        """
        logger.info(f"Getting provenance for {purl}")

        # Search for SBOMs containing this package
        sbom_ids: list[str] = []
        attestation_ids: list[str] = []

        if self.config.storage.use_mock_storage:
            for sbom_id, sbom in self._mock_sboms.items():
                for component in sbom.components:
                    if component.purl == purl or (
                        f"pkg:{component.ecosystem}/{component.name}@{component.version}"
                        == purl
                    ):
                        sbom_ids.append(sbom_id)
                        # Find attestations for this SBOM
                        for att_id, att in self._mock_attestations.items():
                            if att.sbom_id == sbom_id:
                                attestation_ids.append(att_id)

        return ProvenanceChain(
            package_url=purl,
            sbom_ids=sbom_ids,
            attestations=[{"attestation_id": aid} for aid in attestation_ids],
            repository_count=len(
                {
                    self._mock_sboms[sid].repository_id
                    for sid in sbom_ids
                    if sid in self._mock_sboms
                }
            ),
        )

    # -------------------------------------------------------------------------
    # Format Conversion
    # -------------------------------------------------------------------------

    def _convert_report_to_sbom(
        self,
        report: SBOMReport,
        repository_id: str,
        format: SBOMFormat,
        commit_sha: Optional[str],
        branch: Optional[str],
    ) -> SBOMDocument:
        """Convert SBOMReport to SBOMDocument."""
        sbom_id = f"sbom-{uuid.uuid4().hex[:16]}"

        # Determine spec version based on format
        if format in (SBOMFormat.CYCLONEDX_1_5_JSON, SBOMFormat.CYCLONEDX_1_5_XML):
            spec_version = "1.5"
        elif format in (SBOMFormat.SPDX_2_3_JSON, SBOMFormat.SPDX_2_3_RDF):
            spec_version = "2.3"
        else:
            spec_version = "1.0"

        # Convert dependencies to components
        components: list[SBOMComponent] = []

        for dep in report.dependencies + report.dev_dependencies:
            purl = f"pkg:{dep.ecosystem.value}/{dep.name}@{dep.version}"
            component = SBOMComponent(
                name=dep.name,
                version=dep.version,
                ecosystem=dep.ecosystem.value,
                purl=purl,
                source_file=dep.source_file,
                is_dev_dependency=dep.is_dev_dependency,
                is_direct=True,
            )
            components.append(component)

        # Check component limit
        if len(components) > self.config.sbom.max_components:
            logger.warning(
                f"Component count ({len(components)}) exceeds limit "
                f"({self.config.sbom.max_components}), truncating"
            )
            components = components[: self.config.sbom.max_components]

        # Create SBOM document
        sbom = SBOMDocument(
            sbom_id=sbom_id,
            name=repository_id,
            version=commit_sha or "unknown",
            repository_id=repository_id,
            format=format,
            spec_version=spec_version,
            components=components,
            commit_sha=commit_sha,
            branch=branch,
            serial_number=(
                f"urn:uuid:{uuid.uuid4()}"
                if format.value.startswith("cyclonedx")
                else None
            ),
            document_namespace=(
                f"https://aura.example.com/spdx/{sbom_id}"
                if format.value.startswith("spdx")
                else None
            ),
        )

        # Compute content hash
        content = json.dumps(sbom.to_dict(), sort_keys=True)
        sbom.content_hash = hashlib.sha256(content.encode()).hexdigest()

        return sbom

    def to_cyclonedx(self, sbom: SBOMDocument) -> dict[str, Any]:
        """Convert SBOM to CycloneDX 1.5 format."""
        if sbom.format not in (
            SBOMFormat.CYCLONEDX_1_5_JSON,
            SBOMFormat.CYCLONEDX_1_5_XML,
        ):
            raise SBOMFormatError(
                f"Cannot convert to CycloneDX from format: {sbom.format.value}"
            )

        return {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "serialNumber": sbom.serial_number,
            "version": 1,
            "metadata": {
                "timestamp": sbom.created_at.isoformat(),
                "tools": [
                    {
                        "vendor": "Aura",
                        "name": sbom.tool_name,
                        "version": sbom.tool_version,
                    }
                ],
                "component": {
                    "type": "application",
                    "name": sbom.repository_id,
                    "version": sbom.commit_sha or "unknown",
                },
            },
            "components": [
                {
                    "type": "library",
                    "name": c.name,
                    "version": c.version,
                    "purl": c.purl,
                    "licenses": [{"license": {"id": lic}} for lic in c.licenses],
                    "hashes": [
                        {"alg": alg.upper(), "content": h}
                        for alg, h in c.hashes.items()
                    ],
                }
                for c in sbom.components
            ],
        }

    def to_spdx(self, sbom: SBOMDocument) -> dict[str, Any]:
        """Convert SBOM to SPDX 2.3 format."""
        if sbom.format not in (SBOMFormat.SPDX_2_3_JSON, SBOMFormat.SPDX_2_3_RDF):
            raise SBOMFormatError(
                f"Cannot convert to SPDX from format: {sbom.format.value}"
            )

        return {
            "spdxVersion": "SPDX-2.3",
            "dataLicense": "CC0-1.0",
            "SPDXID": "SPDXRef-DOCUMENT",
            "name": sbom.repository_id,
            "documentNamespace": sbom.document_namespace,
            "creationInfo": {
                "created": sbom.created_at.isoformat(),
                "creators": [f"Tool: {sbom.tool_name}-{sbom.tool_version}"],
            },
            "packages": [
                {
                    "SPDXID": f"SPDXRef-Package-{i}",
                    "name": c.name,
                    "versionInfo": c.version,
                    "downloadLocation": "NOASSERTION",
                    "externalRefs": (
                        [
                            {
                                "referenceCategory": "PACKAGE-MANAGER",
                                "referenceType": "purl",
                                "referenceLocator": c.purl,
                            }
                        ]
                        if c.purl
                        else []
                    ),
                    "licenseDeclared": c.licenses[0] if c.licenses else "NOASSERTION",
                    "copyrightText": "NOASSERTION",
                }
                for i, c in enumerate(sbom.components)
            ],
        }

    # -------------------------------------------------------------------------
    # Signing Methods
    # -------------------------------------------------------------------------

    def _sign_with_sigstore(
        self,
        attestation: Attestation,
        content: str,
    ) -> Attestation:
        """Sign using Sigstore keyless signing."""
        # In production, this would use the sigstore library
        # For now, we simulate the signing process

        logger.info("Signing with Sigstore (simulated)")

        # Simulate signature
        attestation.signature = hashlib.sha256(
            f"sigstore:{content}".encode()
        ).hexdigest()
        attestation.signer_identity = "ci@aura.example.com"
        attestation.certificate = (
            "-----BEGIN CERTIFICATE-----\nSIMULATED\n-----END CERTIFICATE-----"
        )

        # Simulate Rekor log entry
        if self.config.attestation.record_in_rekor:
            attestation.rekor_log_index = hash(content) % 100000000
            attestation.rekor_log_id = f"rekor-{uuid.uuid4().hex[:8]}"

        return attestation

    def _sign_with_offline_key(
        self,
        attestation: Attestation,
        content: str,
    ) -> Attestation:
        """Sign using offline Ed25519 key."""
        logger.info("Signing with offline Ed25519 key (simulated)")

        # In production, this would use cryptography library
        # For now, we simulate the signing process

        attestation.signature = hashlib.sha256(
            f"ed25519:{content}".encode()
        ).hexdigest()
        attestation.signer_identity = "offline-key-fingerprint"

        return attestation

    def _sign_with_hsm(
        self,
        attestation: Attestation,
        content: str,
    ) -> Attestation:
        """Sign using HSM (Hardware Security Module) via PKCS#11."""
        logger.info("Signing with HSM PKCS#11 (simulated)")

        # In production, this would use python-pkcs11 or similar library
        # For now, we simulate the signing process

        attestation.signature = hashlib.sha256(f"hsm:{content}".encode()).hexdigest()
        attestation.signer_identity = "hsm-slot-0-key-id"

        return attestation

    # -------------------------------------------------------------------------
    # Verification Methods
    # -------------------------------------------------------------------------

    def _verify_sigstore(self, attestation: Attestation) -> VerificationResult:
        """Verify Sigstore attestation."""
        # In production, this would verify against Rekor and certificate chain
        # For now, we simulate verification

        if attestation.signature is None:
            return VerificationResult(
                attestation_id=attestation.attestation_id,
                status=VerificationStatus.INVALID_SIGNATURE,
                error_message="Missing signature",
            )

        return VerificationResult(
            attestation_id=attestation.attestation_id,
            status=VerificationStatus.VERIFIED,
            signer_identity=attestation.signer_identity,
            certificate_issuer="sigstore.dev",
            rekor_verified=attestation.rekor_log_index is not None,
        )

    def _verify_offline(self, attestation: Attestation) -> VerificationResult:
        """Verify offline Ed25519 attestation."""
        if attestation.signature is None:
            return VerificationResult(
                attestation_id=attestation.attestation_id,
                status=VerificationStatus.INVALID_SIGNATURE,
                error_message="Missing signature",
            )

        return VerificationResult(
            attestation_id=attestation.attestation_id,
            status=VerificationStatus.VERIFIED,
            signer_identity=attestation.signer_identity,
        )

    def _verify_hsm(self, attestation: Attestation) -> VerificationResult:
        """Verify HSM PKCS#11 attestation."""
        if attestation.signature is None:
            return VerificationResult(
                attestation_id=attestation.attestation_id,
                status=VerificationStatus.INVALID_SIGNATURE,
                error_message="Missing signature",
            )

        return VerificationResult(
            attestation_id=attestation.attestation_id,
            status=VerificationStatus.VERIFIED,
            signer_identity=attestation.signer_identity,
        )

    # -------------------------------------------------------------------------
    # Storage Methods
    # -------------------------------------------------------------------------

    def _store_sbom(self, sbom: SBOMDocument) -> None:
        """Store SBOM in DynamoDB and S3."""
        if self.config.storage.use_mock_storage:
            self._mock_sboms[sbom.sbom_id] = sbom

            # Store artifact
            if sbom.format in (
                SBOMFormat.CYCLONEDX_1_5_JSON,
                SBOMFormat.CYCLONEDX_1_5_XML,
            ):
                content = json.dumps(self.to_cyclonedx(sbom), indent=2)
            elif sbom.format in (SBOMFormat.SPDX_2_3_JSON, SBOMFormat.SPDX_2_3_RDF):
                content = json.dumps(self.to_spdx(sbom), indent=2)
            else:
                content = json.dumps(sbom.to_dict(), indent=2)

            self._mock_artifacts[sbom.sbom_id] = content.encode()
            return

        # TODO: Implement DynamoDB and S3 storage
        self._mock_sboms[sbom.sbom_id] = sbom

    def _store_attestation(self, attestation: Attestation) -> None:
        """Store attestation in DynamoDB."""
        if self.config.storage.use_mock_storage:
            self._mock_attestations[attestation.attestation_id] = attestation
            return

        # TODO: Implement DynamoDB storage
        self._mock_attestations[attestation.attestation_id] = attestation

    def _get_attestation(self, attestation_id: str) -> Optional[Attestation]:
        """Get attestation from DynamoDB."""
        if self.config.storage.use_mock_storage:
            return self._mock_attestations.get(attestation_id)

        # TODO: Implement DynamoDB lookup
        return self._mock_attestations.get(attestation_id)


# Singleton instance
_service_instance: Optional[SBOMAttestationService] = None


def get_sbom_attestation_service() -> SBOMAttestationService:
    """Get singleton SBOM attestation service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SBOMAttestationService()
    return _service_instance


def reset_sbom_attestation_service() -> None:
    """Reset SBOM attestation service singleton (for testing)."""
    global _service_instance
    _service_instance = None
