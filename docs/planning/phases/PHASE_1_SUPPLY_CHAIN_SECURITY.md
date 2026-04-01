# Phase 1: Supply Chain Security Foundation

**Duration:** Weeks 1-10
**Market Focus:** Snyk, Wiz, Defense
**Dependencies:** Existing `SBOMDetectionService`

---

## Service 1: SBOM Attestation Service

### Overview

Extends existing `SBOMDetectionService` with cryptographic attestation using Sigstore/cosign, supporting CycloneDX 1.5 and SPDX 2.3 formats with in-toto attestation predicates.

### API Contract

```python
# src/services/supply_chain/sbom_attestation_service.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import hashlib


class SBOMFormat(str, Enum):
    """Supported SBOM formats."""
    CYCLONEDX_1_5 = "cyclonedx-1.5"
    SPDX_2_3 = "spdx-2.3"


class AttestationType(str, Enum):
    """Attestation predicate types (in-toto)."""
    SLSA_PROVENANCE = "https://slsa.dev/provenance/v1"
    CYCLONEDX = "https://cyclonedx.org/bom"
    SPDX = "https://spdx.dev/Document"
    VULN_SCAN = "https://cosign.sigstore.dev/attestation/vuln/v1"


@dataclass
class SBOMComponent:
    """Individual component in SBOM."""
    name: str
    version: str
    purl: str  # Package URL (purl spec)
    ecosystem: str
    licenses: list[str] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)  # {"sha256": "..."}
    supplier: Optional[str] = None
    cpe: Optional[str] = None  # Common Platform Enumeration


@dataclass
class SBOMDocument:
    """Complete SBOM document."""
    id: str
    format: SBOMFormat
    spec_version: str
    serial_number: str
    created: datetime
    components: list[SBOMComponent]
    metadata: dict

    def content_hash(self) -> str:
        """SHA-256 of canonical SBOM content."""
        # Deterministic serialization for signing
        pass


@dataclass
class Attestation:
    """Cryptographic attestation for SBOM."""
    id: str
    sbom_id: str
    predicate_type: AttestationType
    subject_digest: str  # SHA-256 of attested artifact
    predicate: dict  # in-toto predicate content
    signature: str  # Base64-encoded signature
    certificate: Optional[str]  # Fulcio certificate (keyless signing)
    timestamp: datetime
    transparency_log_entry: Optional[str]  # Rekor log index


@dataclass
class AttestationVerificationResult:
    """Result of attestation verification."""
    valid: bool
    sbom_id: str
    signer_identity: Optional[str]
    certificate_issuer: Optional[str]
    transparency_verified: bool
    errors: list[str] = field(default_factory=list)


class SBOMAttestationService:
    """
    Service for generating and verifying SBOM attestations.

    Supports:
    - CycloneDX 1.5 and SPDX 2.3 generation
    - Sigstore keyless signing (Fulcio + Rekor)
    - Hardware key signing (YubiKey, HSM) for air-gapped
    - in-toto attestation predicates
    - VEX (Vulnerability Exploitability eXchange) documents
    """

    async def generate_sbom(
        self,
        repository_path: str,
        format: SBOMFormat = SBOMFormat.CYCLONEDX_1_5,
        include_dev_deps: bool = False,
        depth: int = -1,  # -1 = full transitive
    ) -> SBOMDocument:
        """Generate SBOM for repository."""
        pass

    async def sign_sbom(
        self,
        sbom: SBOMDocument,
        signing_method: str = "sigstore",  # or "hsm", "yubikey"
        identity_token: Optional[str] = None,  # OIDC token for keyless
    ) -> Attestation:
        """Sign SBOM and create attestation."""
        pass

    async def verify_attestation(
        self,
        attestation: Attestation,
        expected_identity: Optional[str] = None,
    ) -> AttestationVerificationResult:
        """Verify attestation signature and transparency log."""
        pass

    async def store_attestation(
        self,
        attestation: Attestation,
        sbom: SBOMDocument,
    ) -> str:
        """Store attestation in Neptune graph and OpenSearch."""
        pass

    async def query_provenance(
        self,
        component_purl: str,
    ) -> list[Attestation]:
        """Query attestation chain for a component."""
        pass
```

### FastAPI Router

```python
# src/api/supply_chain_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(prefix="/api/v1/supply-chain", tags=["supply-chain"])


class GenerateSBOMRequest(BaseModel):
    repository_id: str
    format: str = "cyclonedx-1.5"
    include_dev_deps: bool = False
    sign: bool = True


class GenerateSBOMResponse(BaseModel):
    sbom_id: str
    format: str
    component_count: int
    attestation_id: Optional[str]
    download_url: str


@router.post("/sbom/generate", response_model=GenerateSBOMResponse)
async def generate_sbom(
    request: GenerateSBOMRequest,
    background_tasks: BackgroundTasks,
    service: SBOMAttestationService = Depends(get_sbom_service),
):
    """Generate SBOM for a repository with optional signing."""
    pass


@router.get("/sbom/{sbom_id}")
async def get_sbom(sbom_id: str):
    """Retrieve SBOM document."""
    pass


@router.post("/attestation/verify")
async def verify_attestation(attestation_id: str):
    """Verify attestation signature and transparency log."""
    pass


@router.get("/provenance/{purl:path}")
async def query_provenance(purl: str):
    """Query attestation chain for package URL."""
    pass
```

### CloudFormation Template

```yaml
# deploy/cloudformation/sbom-attestation.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Project Aura - Layer 9.1 - SBOM Attestation Service Infrastructure'

Parameters:
  ProjectName:
    Type: String
    Default: aura
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]

Resources:
  # DynamoDB Table for SBOM Documents
  SBOMTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-sbom-documents-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: sbom_id
          AttributeType: S
        - AttributeName: repository_id
          AttributeType: S
        - AttributeName: created_at
          AttributeType: S
      KeySchema:
        - AttributeName: sbom_id
          KeyType: HASH
      GlobalSecondaryIndexes:
        - IndexName: repository-index
          KeySchema:
            - AttributeName: repository_id
              KeyType: HASH
            - AttributeName: created_at
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
        SSEType: KMS
        KMSMasterKeyId: !ImportValue
          Fn::Sub: '${ProjectName}-kms-key-arn-${Environment}'
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  # DynamoDB Table for Attestations
  AttestationTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-attestations-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: attestation_id
          AttributeType: S
        - AttributeName: sbom_id
          AttributeType: S
        - AttributeName: subject_digest
          AttributeType: S
      KeySchema:
        - AttributeName: attestation_id
          KeyType: HASH
      GlobalSecondaryIndexes:
        - IndexName: sbom-index
          KeySchema:
            - AttributeName: sbom_id
              KeyType: HASH
          Projection:
            ProjectionType: ALL
        - IndexName: digest-index
          KeySchema:
            - AttributeName: subject_digest
              KeyType: HASH
          Projection:
            ProjectionType: KEYS_ONLY
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
        SSEType: KMS
        KMSMasterKeyId: !ImportValue
          Fn::Sub: '${ProjectName}-kms-key-arn-${Environment}'

  # S3 Bucket for SBOM/Attestation Artifacts
  SBOMArtifactsBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub '${ProjectName}-sbom-artifacts-${Environment}-${AWS::AccountId}'
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: aws:kms
              KMSMasterKeyID: !ImportValue
                Fn::Sub: '${ProjectName}-kms-key-arn-${Environment}'
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      VersioningConfiguration:
        Status: Enabled
      LifecycleConfiguration:
        Rules:
          - Id: ExpireOldVersions
            Status: Enabled
            NoncurrentVersionExpiration:
              NoncurrentDays: 90

  # EventBridge Rule for SBOM Generation Events
  SBOMEventRule:
    Type: AWS::Events::Rule
    Properties:
      Name: !Sub '${ProjectName}-sbom-events-${Environment}'
      Description: Triggers on repository analysis completion
      EventBusName: !ImportValue
        Fn::Sub: '${ProjectName}-event-bus-${Environment}'
      EventPattern:
        source:
          - aura.repository
        detail-type:
          - RepositoryAnalysisComplete
      State: ENABLED
      Targets:
        - Id: SBOMGenerationQueue
          Arn: !GetAtt SBOMGenerationQueue.Arn

  # SQS Queue for Async SBOM Generation
  SBOMGenerationQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub '${ProjectName}-sbom-generation-${Environment}'
      VisibilityTimeout: 900  # 15 minutes for large repos
      MessageRetentionPeriod: 1209600  # 14 days
      KmsMasterKeyId: !ImportValue
        Fn::Sub: '${ProjectName}-kms-key-arn-${Environment}'
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt SBOMGenerationDLQ.Arn
        maxReceiveCount: 3

  SBOMGenerationDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub '${ProjectName}-sbom-generation-dlq-${Environment}'
      MessageRetentionPeriod: 1209600
      KmsMasterKeyId: !ImportValue
        Fn::Sub: '${ProjectName}-kms-key-arn-${Environment}'

Outputs:
  SBOMTableArn:
    Value: !GetAtt SBOMTable.Arn
    Export:
      Name: !Sub '${ProjectName}-sbom-table-arn-${Environment}'

  AttestationTableArn:
    Value: !GetAtt AttestationTable.Arn
    Export:
      Name: !Sub '${ProjectName}-attestation-table-arn-${Environment}'

  SBOMArtifactsBucketArn:
    Value: !GetAtt SBOMArtifactsBucket.Arn
    Export:
      Name: !Sub '${ProjectName}-sbom-artifacts-bucket-arn-${Environment}'
```

---

## Service 2: Dependency Confusion Detector

### Overview

Detects typosquatting, namespace hijacking, and dependency confusion attacks by analyzing package names against known-good registries and historical patterns.

### API Contract

```python
# src/services/supply_chain/dependency_confusion_detector.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ConfusionType(str, Enum):
    """Types of dependency confusion attacks."""
    TYPOSQUATTING = "typosquatting"  # Similar name (lodash vs lodahs)
    NAMESPACE_HIJACK = "namespace_hijack"  # @company/pkg on public registry
    COMBOSQUATTING = "combosquatting"  # legit-name-malicious
    REPO_JACKING = "repo_jacking"  # Abandoned repo takeover
    INTERNAL_LEAK = "internal_leak"  # Internal package on public registry


class RiskLevel(str, Enum):
    """Risk assessment levels."""
    CRITICAL = "critical"  # Active attack detected
    HIGH = "high"  # Strong indicators
    MEDIUM = "medium"  # Suspicious patterns
    LOW = "low"  # Minor concerns
    SAFE = "safe"  # No issues detected


@dataclass
class ConfusionIndicator:
    """Individual indicator of potential confusion attack."""
    type: ConfusionType
    package_name: str
    ecosystem: str
    similar_to: Optional[str]  # Legitimate package it mimics
    edit_distance: Optional[int]
    age_days: int  # How recently published
    download_count: int
    maintainer_email: Optional[str]
    details: str


@dataclass
class ConfusionAnalysisResult:
    """Result of dependency confusion analysis."""
    package_name: str
    ecosystem: str
    risk_level: RiskLevel
    indicators: list[ConfusionIndicator] = field(default_factory=list)
    recommended_action: str = ""
    safe_alternative: Optional[str] = None


class DependencyConfusionDetector:
    """
    Detects dependency confusion attacks.

    Detection methods:
    - Levenshtein distance to popular packages
    - Namespace ownership verification
    - Publication timing analysis
    - Maintainer reputation scoring
    - Historical download pattern anomalies
    """

    async def analyze_package(
        self,
        package_name: str,
        ecosystem: str,
        internal_namespaces: list[str] = None,
    ) -> ConfusionAnalysisResult:
        """Analyze single package for confusion indicators."""
        pass

    async def analyze_sbom(
        self,
        sbom_id: str,
        internal_namespaces: list[str] = None,
    ) -> list[ConfusionAnalysisResult]:
        """Analyze all packages in SBOM."""
        pass

    async def register_internal_namespace(
        self,
        namespace: str,
        ecosystem: str,
        organization_id: str,
    ) -> None:
        """Register internal namespace for hijack detection."""
        pass

    def calculate_typosquat_score(
        self,
        package_name: str,
        ecosystem: str,
    ) -> tuple[float, list[str]]:
        """
        Calculate typosquatting probability.

        Returns:
            (score, list of similar legitimate packages)
        """
        pass
```

### Detection Algorithms

```python
# src/services/supply_chain/confusion_algorithms.py

import Levenshtein
from typing import Optional


# Top 1000 packages per ecosystem (loaded from data files)
POPULAR_PACKAGES = {
    "npm": [...],
    "pip": [...],
    "go": [...],
}

# Common typosquatting patterns
TYPOSQUAT_PATTERNS = [
    ("rn", "m"),   # rn looks like m
    ("l", "1"),    # l looks like 1
    ("0", "o"),    # 0 looks like o
    ("-", "_"),    # hyphen/underscore swap
    ("js", ""),    # js suffix removal
    ("py", ""),    # py suffix removal
]


def calculate_edit_distance_score(
    name: str,
    popular_packages: list[str],
    threshold: int = 2,
) -> list[tuple[str, int, float]]:
    """
    Find similar popular packages within edit distance.

    Returns:
        List of (similar_package, edit_distance, similarity_score)
    """
    results = []
    for popular in popular_packages:
        distance = Levenshtein.distance(name.lower(), popular.lower())
        if 0 < distance <= threshold:
            similarity = 1 - (distance / max(len(name), len(popular)))
            results.append((popular, distance, similarity))

    return sorted(results, key=lambda x: x[1])


def detect_combosquatting(name: str, popular_packages: list[str]) -> Optional[str]:
    """
    Detect combosquatting (legitimate-name-suffix).

    Examples:
        - "lodash-utils" squatting on "lodash"
        - "react-native-helper" squatting on "react-native"
    """
    suffixes = ["-utils", "-helper", "-core", "-lib", "-js", "-py", "-cli"]
    prefixes = ["node-", "python-", "go-", "rust-"]

    for suffix in suffixes:
        if name.endswith(suffix):
            base = name[:-len(suffix)]
            if base in popular_packages:
                return base

    for prefix in prefixes:
        if name.startswith(prefix):
            base = name[len(prefix):]
            if base in popular_packages:
                return base

    return None


def check_namespace_hijack(
    package_name: str,
    ecosystem: str,
    internal_namespaces: list[str],
) -> bool:
    """
    Check if package uses internal namespace on public registry.

    Examples:
        - @company/internal-lib published to public npm
        - company-internal-tool published to PyPI
    """
    for namespace in internal_namespaces:
        if package_name.startswith(f"@{namespace}/"):
            return True
        if package_name.startswith(f"{namespace}-"):
            return True
        if package_name.startswith(f"{namespace}_"):
            return True

    return False
```

---

## Service 3: License Compliance Engine

### Overview

Analyzes SBOM for license compatibility, generates compliance reports, and enforces license policies.

### API Contract

```python
# src/services/supply_chain/license_compliance_engine.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LicenseCategory(str, Enum):
    """License categories by restriction level."""
    PERMISSIVE = "permissive"  # MIT, Apache-2.0, BSD
    WEAK_COPYLEFT = "weak_copyleft"  # LGPL, MPL
    STRONG_COPYLEFT = "strong_copyleft"  # GPL, AGPL
    COMMERCIAL = "commercial"  # Proprietary
    UNKNOWN = "unknown"


class ComplianceStatus(str, Enum):
    """Compliance check result."""
    COMPLIANT = "compliant"
    VIOLATION = "violation"
    WARNING = "warning"
    UNKNOWN = "unknown"


@dataclass
class LicenseInfo:
    """Information about a license."""
    spdx_id: str
    name: str
    category: LicenseCategory
    osi_approved: bool
    fsf_libre: bool
    copyleft: bool
    patent_grant: bool
    attribution_required: bool
    disclosure_required: bool


@dataclass
class LicenseViolation:
    """Detected license violation."""
    component: str
    license: str
    violation_type: str
    policy_rule: str
    severity: str
    remediation: str


@dataclass
class ComplianceReport:
    """License compliance report for SBOM."""
    sbom_id: str
    status: ComplianceStatus
    total_components: int
    components_by_category: dict[str, int]
    violations: list[LicenseViolation]
    warnings: list[str]
    generated_at: str


@dataclass
class LicensePolicy:
    """Organization license policy."""
    id: str
    name: str
    allowed_categories: list[LicenseCategory]
    denied_licenses: list[str]  # Specific SPDX IDs
    allowed_licenses: list[str]
    require_attribution_file: bool
    max_copyleft_depth: int  # How deep in deps copyleft is allowed


class LicenseComplianceEngine:
    """
    Engine for license compliance analysis.

    Features:
    - SPDX license identification
    - License compatibility checking
    - Policy enforcement
    - Attribution file generation
    - Compliance report generation
    """

    async def analyze_sbom_compliance(
        self,
        sbom_id: str,
        policy_id: Optional[str] = None,
    ) -> ComplianceReport:
        """Analyze SBOM against license policy."""
        pass

    async def check_license_compatibility(
        self,
        project_license: str,
        dependency_licenses: list[str],
    ) -> list[LicenseViolation]:
        """Check if dependency licenses are compatible with project license."""
        pass

    async def generate_attribution(
        self,
        sbom_id: str,
        format: str = "markdown",  # or "html", "txt"
    ) -> str:
        """Generate attribution/notice file from SBOM."""
        pass

    async def create_policy(
        self,
        policy: LicensePolicy,
    ) -> str:
        """Create organization license policy."""
        pass

    async def get_license_info(
        self,
        spdx_id: str,
    ) -> LicenseInfo:
        """Get detailed license information."""
        pass
```

---

## Test Strategy

### Unit Tests

```python
# tests/services/supply_chain/test_sbom_attestation_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from src.services.supply_chain.sbom_attestation_service import (
    SBOMAttestationService,
    SBOMDocument,
    SBOMComponent,
    SBOMFormat,
    Attestation,
    AttestationType,
)


class TestSBOMGeneration:
    """Tests for SBOM generation."""

    @pytest.fixture
    def service(self):
        return SBOMAttestationService(
            neptune_client=MagicMock(),
            opensearch_client=MagicMock(),
            s3_client=MagicMock(),
        )

    @pytest.mark.asyncio
    async def test_generate_sbom_cyclonedx(self, service, tmp_path):
        """Test CycloneDX SBOM generation."""
        # Create test repo with requirements.txt
        (tmp_path / "requirements.txt").write_text("requests==2.28.0\nflask==2.2.0\n")

        sbom = await service.generate_sbom(
            repository_path=str(tmp_path),
            format=SBOMFormat.CYCLONEDX_1_5,
        )

        assert sbom.format == SBOMFormat.CYCLONEDX_1_5
        assert len(sbom.components) == 2
        assert any(c.name == "requests" for c in sbom.components)

    @pytest.mark.asyncio
    async def test_generate_sbom_includes_transitive(self, service, tmp_path):
        """Test that transitive dependencies are included."""
        pass

    @pytest.mark.asyncio
    async def test_generate_sbom_with_dev_deps(self, service, tmp_path):
        """Test dev dependency inclusion flag."""
        pass


class TestAttestationSigning:
    """Tests for attestation signing."""

    @pytest.mark.asyncio
    async def test_sign_sbom_sigstore(self, service):
        """Test Sigstore keyless signing."""
        pass

    @pytest.mark.asyncio
    async def test_sign_sbom_offline_key(self, service):
        """Test offline key signing for air-gapped."""
        pass

    @pytest.mark.asyncio
    async def test_verify_valid_attestation(self, service):
        """Test verification of valid attestation."""
        pass

    @pytest.mark.asyncio
    async def test_verify_tampered_attestation(self, service):
        """Test detection of tampered attestation."""
        pass


class TestDependencyConfusion:
    """Tests for dependency confusion detection."""

    @pytest.mark.asyncio
    async def test_detect_typosquatting(self, detector):
        """Test typosquatting detection."""
        result = await detector.analyze_package("requets", "pip")

        assert result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert any(i.type == ConfusionType.TYPOSQUATTING for i in result.indicators)
        assert result.safe_alternative == "requests"

    @pytest.mark.asyncio
    async def test_detect_namespace_hijack(self, detector):
        """Test namespace hijacking detection."""
        detector.register_internal_namespace("acme", "npm", "org-123")

        result = await detector.analyze_package("@acme/internal-lib", "npm")

        assert result.risk_level == RiskLevel.CRITICAL
        assert any(i.type == ConfusionType.NAMESPACE_HIJACK for i in result.indicators)
```

### Integration Tests

```python
# tests/integration/test_supply_chain_integration.py

import pytest
from httpx import AsyncClient


class TestSBOMAPIIntegration:
    """Integration tests for SBOM API endpoints."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_generate_and_verify_flow(self, client: AsyncClient):
        """Test full SBOM generation and verification flow."""
        # Generate SBOM
        response = await client.post("/api/v1/supply-chain/sbom/generate", json={
            "repository_id": "test-repo-123",
            "format": "cyclonedx-1.5",
            "sign": True,
        })
        assert response.status_code == 200
        sbom_id = response.json()["sbom_id"]
        attestation_id = response.json()["attestation_id"]

        # Verify attestation
        response = await client.post(
            f"/api/v1/supply-chain/attestation/verify",
            params={"attestation_id": attestation_id},
        )
        assert response.status_code == 200
        assert response.json()["valid"] is True
```

---

## Deployment Checklist

### Prerequisites
- [ ] Neptune schema updated with SBOM vertex types
- [ ] OpenSearch index `aura-sbom-attestations` created
- [ ] KMS key permissions updated for SBOM service role
- [ ] Sigstore/Rekor connectivity verified (or offline keys configured)

### Infrastructure Deployment
- [ ] Deploy `sbom-attestation.yaml` to dev
- [ ] Deploy `dependency-confusion.yaml` to dev
- [ ] Deploy `license-compliance.yaml` to dev
- [ ] Verify DynamoDB tables created
- [ ] Verify S3 bucket with encryption

### Service Deployment
- [ ] Build and push service container to ECR
- [ ] Update Kubernetes deployment
- [ ] Verify health check endpoints
- [ ] Run smoke tests

### Validation
- [ ] Generate test SBOM for sample repository
- [ ] Sign attestation and verify signature
- [ ] Test dependency confusion detection
- [ ] Generate license compliance report
- [ ] Verify Neptune graph population
- [ ] Verify OpenSearch indexing

---

## Estimated Metrics

| Metric | Target |
|--------|--------|
| Lines of Code | 10,500 |
| Test Count | 1,150 |
| Test Coverage | 85%+ |
| CloudFormation Templates | 4 |
| API Endpoints | 12 |
| Neptune Vertex Types | 3 |
| OpenSearch Indices | 1 |
