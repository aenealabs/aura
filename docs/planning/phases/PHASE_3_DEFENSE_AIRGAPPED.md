# Phase 3: Defense & Classified Workloads

**Duration:** Weeks 21-30
**Market Focus:** Anduril, Defense contractors, Federal agencies
**Dependencies:** ADR-049 air-gap foundation, Phase 1-2 services

---

## Service 1: Air-Gap Orchestrator

### Overview

Extends ADR-049 self-hosted deployment with complete offline operation capability for IL5/IL6 classified environments, including offline model inference, update distribution, and license validation.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Air-Gapped Deployment Architecture                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                 UNCLASSIFIED ENVIRONMENT                         │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │    │
│  │  │ Aura Cloud  │  │ Model       │  │ CVE/Advisory            │  │    │
│  │  │ (SaaS)      │  │ Registry    │  │ Database                │  │    │
│  │  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │    │
│  │         │                │                      │                │    │
│  │         └────────────────┼──────────────────────┘                │    │
│  │                          ▼                                        │    │
│  │              ┌───────────────────────┐                           │    │
│  │              │ Offline Bundle        │                           │    │
│  │              │ Generator             │                           │    │
│  │              │                       │                           │    │
│  │              │ - Container images    │                           │    │
│  │              │ - LLM model weights   │                           │    │
│  │              │ - CVE database        │                           │    │
│  │              │ - SBOM attestations   │                           │    │
│  │              │ - License keys        │                           │    │
│  │              └───────────┬───────────┘                           │    │
│  │                          │                                        │    │
│  │                          ▼                                        │    │
│  │              ┌───────────────────────┐                           │    │
│  │              │ Signed Bundle         │                           │    │
│  │              │ (Encrypted, FIPS)     │                           │    │
│  │              │ SHA-256: abc123...    │                           │    │
│  │              └───────────┬───────────┘                           │    │
│  └──────────────────────────┼───────────────────────────────────────┘    │
│                             │                                            │
│                     ════════╪════════  AIR GAP  ════════════════         │
│                             │ (Physical media transfer)                  │
│                             ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                 CLASSIFIED ENVIRONMENT (IL5/IL6)                  │   │
│  │                                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │              Air-Gap Orchestrator                            │ │   │
│  │  │  ┌───────────────────┐  ┌───────────────────┐               │ │   │
│  │  │  │ Bundle Validator  │  │ Offline License   │               │ │   │
│  │  │  │ - Signature check │  │ Validator         │               │ │   │
│  │  │  │ - Integrity hash  │  │ - Ed25519 verify  │               │ │   │
│  │  │  │ - FIPS compliance │  │ - Expiry check    │               │ │   │
│  │  │  └───────────────────┘  └───────────────────┘               │ │   │
│  │  │                                                              │ │   │
│  │  │  ┌───────────────────┐  ┌───────────────────┐               │ │   │
│  │  │  │ Offline Model     │  │ Local CVE         │               │ │   │
│  │  │  │ Inference         │  │ Database          │               │ │   │
│  │  │  │ - vLLM/TGI        │  │ - SQLite mirror   │               │ │   │
│  │  │  │ - GPU scheduling  │  │ - Daily delta     │               │ │   │
│  │  │  └───────────────────┘  └───────────────────┘               │ │   │
│  │  │                                                              │ │   │
│  │  │  ┌───────────────────┐  ┌───────────────────┐               │ │   │
│  │  │  │ Egress Validator  │  │ Audit Logger      │               │ │   │
│  │  │  │ (existing)        │  │ (air-gap mode)    │               │ │   │
│  │  │  └───────────────────┘  └───────────────────┘               │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  │                                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │              Aura Platform (Offline Mode)                    │ │   │
│  │  │  - GraphRAG (Neo4j local)                                    │ │   │
│  │  │  - Vector Search (OpenSearch local)                          │ │   │
│  │  │  - Agent Orchestrator                                        │ │   │
│  │  │  - HITL Workflows                                            │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### API Contract

```python
# src/services/airgap/orchestrator.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
import hashlib


class BundleType(str, Enum):
    """Types of air-gap bundles."""
    FULL_INSTALL = "full_install"  # Complete platform
    UPDATE = "update"  # Incremental update
    CVE_DATABASE = "cve_database"  # CVE/Advisory only
    MODEL_WEIGHTS = "model_weights"  # LLM models only
    LICENSE = "license"  # License key renewal


class ClassificationLevel(str, Enum):
    """Data classification levels."""
    UNCLASSIFIED = "unclassified"
    CUI = "cui"  # Controlled Unclassified Information
    IL4 = "il4"  # DoD Impact Level 4
    IL5 = "il5"  # DoD Impact Level 5
    IL6 = "il6"  # DoD Impact Level 6 (classified)


@dataclass
class AirGapBundle:
    """Air-gapped deployment bundle."""
    id: str
    type: BundleType
    version: str
    created_at: datetime
    expires_at: datetime
    classification: ClassificationLevel
    sha256_hash: str
    signature: str  # Ed25519 signature
    components: list[str]
    size_bytes: int
    fips_compliant: bool


@dataclass
class BundleValidationResult:
    """Result of bundle validation."""
    valid: bool
    bundle_id: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    signature_verified: bool = False
    hash_verified: bool = False
    fips_verified: bool = False


@dataclass
class OfflineLicenseStatus:
    """Offline license validation status."""
    valid: bool
    license_id: str
    organization: str
    tier: str  # community, enterprise, government
    expires_at: datetime
    features: list[str]
    node_limit: int
    user_limit: int


class AirGapOrchestrator:
    """
    Orchestrates air-gapped deployment operations.

    Features:
    - Bundle generation and validation
    - Offline license management
    - CVE database synchronization
    - Model weight distribution
    - FIPS 140-3 compliance
    """

    def __init__(
        self,
        bundle_path: Path,
        license_validator: "OfflineLicenseValidator",
        egress_validator: "EgressValidator",
        model_manager: "OfflineModelManager",
    ):
        self.bundle_path = bundle_path
        self.license = license_validator
        self.egress = egress_validator
        self.models = model_manager

    async def validate_bundle(
        self,
        bundle_path: Path,
    ) -> BundleValidationResult:
        """Validate air-gap bundle integrity and signature."""
        pass

    async def install_bundle(
        self,
        bundle_path: Path,
        target_classification: ClassificationLevel,
    ) -> dict:
        """Install bundle to air-gapped environment."""
        pass

    async def generate_bundle(
        self,
        bundle_type: BundleType,
        components: list[str],
        target_classification: ClassificationLevel,
    ) -> AirGapBundle:
        """Generate bundle for air-gap transfer (unclassified side)."""
        pass

    async def validate_license_offline(self) -> OfflineLicenseStatus:
        """Validate license without network access."""
        pass

    async def sync_cve_database(
        self,
        bundle_path: Path,
    ) -> dict:
        """Sync CVE database from bundle."""
        pass

    async def verify_egress_blocked(self) -> bool:
        """Verify no external network access."""
        return await self.egress.validate_all()

    async def get_deployment_status(self) -> dict:
        """Get current air-gap deployment status."""
        pass


class OfflineLicenseValidator:
    """
    Validates licenses without network access.

    Uses Ed25519 signatures with embedded public key.
    License includes hardware fingerprint for binding.
    """

    def __init__(self, public_key: bytes):
        self.public_key = public_key

    def validate(
        self,
        license_token: str,
        hardware_fingerprint: str,
    ) -> OfflineLicenseStatus:
        """Validate license token offline."""
        pass

    def generate_hardware_fingerprint(self) -> str:
        """Generate hardware fingerprint for license binding."""
        pass


class OfflineModelManager:
    """
    Manages LLM models for offline inference.

    Supports:
    - vLLM for high-performance inference
    - Text Generation Inference (TGI)
    - GGUF quantized models for edge
    """

    async def load_model(
        self,
        model_path: Path,
        model_type: str,
    ) -> str:
        """Load model from bundle."""
        pass

    async def verify_model_integrity(
        self,
        model_path: Path,
        expected_hash: str,
    ) -> bool:
        """Verify model file integrity."""
        pass

    async def get_loaded_models(self) -> list[dict]:
        """Get currently loaded models."""
        pass
```

---

## Service 2: Firmware Security Analyzer

### Overview

Analyzes C/C++ embedded systems code, firmware binaries, and RTOS configurations for security vulnerabilities in defense/aerospace applications.

### API Contract

```python
# src/services/firmware/security_analyzer.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class FirmwareType(str, Enum):
    """Types of firmware/embedded systems."""
    RTOS = "rtos"  # FreeRTOS, VxWorks, QNX
    BARE_METAL = "bare_metal"
    LINUX_EMBEDDED = "linux_embedded"
    BOOTLOADER = "bootloader"
    UEFI = "uefi"


class ArchitectureType(str, Enum):
    """Target architectures."""
    ARM_CORTEX_M = "arm_cortex_m"
    ARM_CORTEX_A = "arm_cortex_a"
    ARM64 = "arm64"
    X86 = "x86"
    X86_64 = "x86_64"
    RISC_V = "risc_v"
    MIPS = "mips"


class VulnerabilityClass(str, Enum):
    """Classes of firmware vulnerabilities."""
    BUFFER_OVERFLOW = "buffer_overflow"
    INTEGER_OVERFLOW = "integer_overflow"
    USE_AFTER_FREE = "use_after_free"
    FORMAT_STRING = "format_string"
    COMMAND_INJECTION = "command_injection"
    HARDCODED_CREDENTIALS = "hardcoded_credentials"
    INSECURE_BOOT = "insecure_boot"
    WEAK_CRYPTO = "weak_crypto"
    MEMORY_CORRUPTION = "memory_corruption"
    RACE_CONDITION = "race_condition"


@dataclass
class FirmwareComponent:
    """Component within firmware."""
    name: str
    path: str
    language: str
    size_bytes: int
    compiler: Optional[str]
    compile_flags: list[str]
    dependencies: list[str]


@dataclass
class FirmwareVulnerability:
    """Detected firmware vulnerability."""
    id: str
    vuln_class: VulnerabilityClass
    severity: str
    component: str
    file_path: str
    line_number: int
    function_name: Optional[str]
    description: str
    cwe_id: str
    cve_id: Optional[str]
    mitre_attack_id: Optional[str]
    proof_of_concept: Optional[str]
    remediation: str


@dataclass
class FirmwareAnalysisResult:
    """Complete firmware analysis result."""
    firmware_id: str
    firmware_type: FirmwareType
    architecture: ArchitectureType
    components: list[FirmwareComponent]
    vulnerabilities: list[FirmwareVulnerability]
    security_score: float  # 0-100
    compliance_status: dict  # DO-178C, IEC 62443, etc.
    analysis_duration_seconds: float
    analyzed_at: datetime


class FirmwareSecurityAnalyzer:
    """
    Analyzes firmware for security vulnerabilities.

    Supports:
    - Static analysis (source code)
    - Binary analysis (reverse engineering)
    - RTOS configuration review
    - Secure boot chain verification
    - Cryptographic implementation review
    """

    async def analyze_source(
        self,
        source_path: Path,
        architecture: ArchitectureType,
        firmware_type: FirmwareType,
        compiler_flags: list[str] = None,
    ) -> FirmwareAnalysisResult:
        """Analyze firmware source code."""
        pass

    async def analyze_binary(
        self,
        binary_path: Path,
        architecture: ArchitectureType,
    ) -> FirmwareAnalysisResult:
        """Analyze compiled firmware binary."""
        pass

    async def verify_secure_boot(
        self,
        bootloader_path: Path,
        signing_key_hash: str,
    ) -> dict:
        """Verify secure boot chain integrity."""
        pass

    async def check_crypto_implementation(
        self,
        source_path: Path,
    ) -> list[dict]:
        """Check cryptographic implementations for weaknesses."""
        pass

    async def generate_compliance_report(
        self,
        analysis_result: FirmwareAnalysisResult,
        standards: list[str],  # DO-178C, IEC-62443, etc.
    ) -> dict:
        """Generate compliance report for safety standards."""
        pass
```

### Detection Rules

```python
# src/services/firmware/detection_rules.py

"""
Firmware vulnerability detection rules.

Based on:
- CERT C Coding Standard
- MISRA C:2012
- CWE Top 25
- ICS-CERT advisories
"""

BUFFER_OVERFLOW_PATTERNS = [
    # Dangerous functions
    r'\bstrcpy\s*\(',
    r'\bstrcat\s*\(',
    r'\bsprintf\s*\(',
    r'\bgets\s*\(',
    r'\bscanf\s*\(\s*"[^"]*%s',

    # Unchecked array access
    r'\[\s*[a-zA-Z_]\w*\s*\]',  # Requires dataflow analysis
]

HARDCODED_CREDENTIAL_PATTERNS = [
    r'password\s*=\s*"[^"]+"',
    r'api_key\s*=\s*"[^"]+"',
    r'secret\s*=\s*"[^"]+"',
    r'#define\s+PASSWORD\s+"[^"]+"',
    r'const\s+char\s*\*\s*password\s*=',
]

WEAK_CRYPTO_PATTERNS = [
    r'\bDES_',  # DES encryption
    r'\bMD5_',  # MD5 hashing
    r'\bRC4_',  # RC4 stream cipher
    r'\brand\s*\(\s*\)',  # Weak PRNG
    r'\bsrand\s*\(',  # Weak PRNG seed
]

COMMAND_INJECTION_PATTERNS = [
    r'\bsystem\s*\(',
    r'\bpopen\s*\(',
    r'\bexecl\s*\(',
    r'\bexecv\s*\(',
]


def analyze_c_file(file_path: str, content: str) -> list[dict]:
    """
    Analyze C source file for vulnerabilities.

    Returns list of findings with line numbers and descriptions.
    """
    findings = []

    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        # Check buffer overflow patterns
        for pattern in BUFFER_OVERFLOW_PATTERNS:
            import re
            if re.search(pattern, line):
                findings.append({
                    'file': file_path,
                    'line': i,
                    'class': 'buffer_overflow',
                    'pattern': pattern,
                    'code': line.strip(),
                })

        # Check hardcoded credentials
        for pattern in HARDCODED_CREDENTIAL_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append({
                    'file': file_path,
                    'line': i,
                    'class': 'hardcoded_credentials',
                    'pattern': pattern,
                    'code': line.strip(),
                })

    return findings
```

---

## Service 3: Tactical Edge Runtime

### Overview

Lightweight Aura deployment for resource-constrained tactical hardware (drones, sensors, field devices) operating in disconnected environments.

### API Contract

```python
# src/services/tactical/edge_runtime.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ConnectivityMode(str, Enum):
    """Network connectivity modes."""
    CONNECTED = "connected"  # Full network access
    INTERMITTENT = "intermittent"  # Periodic sync
    DISCONNECTED = "disconnected"  # Fully offline
    DENIED = "denied"  # Adversary-contested


class ResourceProfile(str, Enum):
    """Hardware resource profiles."""
    MINIMAL = "minimal"  # <1GB RAM, <10GB storage
    STANDARD = "standard"  # 4GB RAM, 50GB storage
    ENHANCED = "enhanced"  # 16GB RAM, 200GB storage


@dataclass
class EdgeDeployment:
    """Tactical edge deployment configuration."""
    id: str
    device_id: str
    device_type: str
    resource_profile: ResourceProfile
    connectivity_mode: ConnectivityMode
    last_sync: Optional[datetime]
    pending_sync_items: int
    storage_used_bytes: int
    storage_total_bytes: int


@dataclass
class EdgeScanResult:
    """Security scan result from edge device."""
    id: str
    deployment_id: str
    scanned_at: datetime
    target_type: str  # firmware, config, code
    findings_count: int
    critical_findings: int
    sync_status: str  # pending, synced, failed


class TacticalEdgeRuntime:
    """
    Lightweight runtime for tactical edge devices.

    Features:
    - Minimal resource footprint (<500MB RAM)
    - Offline-first operation
    - Store-and-forward sync
    - Quantized model inference
    - Hardware security module integration
    """

    async def initialize_deployment(
        self,
        device_id: str,
        resource_profile: ResourceProfile,
        initial_bundle_path: str,
    ) -> EdgeDeployment:
        """Initialize edge deployment on device."""
        pass

    async def run_local_scan(
        self,
        deployment_id: str,
        target_path: str,
    ) -> EdgeScanResult:
        """Run security scan locally on edge device."""
        pass

    async def queue_sync(
        self,
        deployment_id: str,
        scan_result: EdgeScanResult,
    ) -> str:
        """Queue scan result for sync when connected."""
        pass

    async def sync_when_available(
        self,
        deployment_id: str,
    ) -> dict:
        """Sync pending items when connectivity available."""
        pass

    async def get_deployment_status(
        self,
        deployment_id: str,
    ) -> EdgeDeployment:
        """Get current deployment status."""
        pass
```

---

## CloudFormation Templates

### IL5/IL6 Boundary Controls

```yaml
# deploy/cloudformation/airgap-boundary.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Project Aura - Layer 9.3 - Air-Gap Boundary Controls (GovCloud)'

Parameters:
  ProjectName:
    Type: String
    Default: aura
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]
  ClassificationLevel:
    Type: String
    AllowedValues: [IL4, IL5, IL6]
    Default: IL5

Conditions:
  IsIL6: !Equals [!Ref ClassificationLevel, 'IL6']
  IsIL5OrHigher: !Or
    - !Equals [!Ref ClassificationLevel, 'IL5']
    - !Equals [!Ref ClassificationLevel, 'IL6']

Resources:
  # VPC with no internet connectivity
  AirGapVPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: 10.200.0.0/16
      EnableDnsHostnames: true
      EnableDnsSupport: true
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-airgap-vpc-${Environment}'
        - Key: Classification
          Value: !Ref ClassificationLevel

  # Private subnets only (no public subnets)
  PrivateSubnet1:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref AirGapVPC
      CidrBlock: 10.200.1.0/24
      AvailabilityZone: !Select [0, !GetAZs '']
      MapPublicIpOnLaunch: false
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-airgap-private-1-${Environment}'

  PrivateSubnet2:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref AirGapVPC
      CidrBlock: 10.200.2.0/24
      AvailabilityZone: !Select [1, !GetAZs '']
      MapPublicIpOnLaunch: false
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-airgap-private-2-${Environment}'

  # Route table with NO internet gateway
  PrivateRouteTable:
    Type: AWS::EC2::RouteTable
    Properties:
      VpcId: !Ref AirGapVPC
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-airgap-private-rt-${Environment}'

  # NACL blocking all external traffic
  AirGapNACL:
    Type: AWS::EC2::NetworkAcl
    Properties:
      VpcId: !Ref AirGapVPC
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-airgap-nacl-${Environment}'

  # Deny all inbound from internet
  NACLDenyInbound:
    Type: AWS::EC2::NetworkAclEntry
    Properties:
      NetworkAclId: !Ref AirGapNACL
      RuleNumber: 100
      Protocol: -1
      RuleAction: deny
      Egress: false
      CidrBlock: 0.0.0.0/0

  # Allow internal VPC traffic only
  NACLAllowInternalInbound:
    Type: AWS::EC2::NetworkAclEntry
    Properties:
      NetworkAclId: !Ref AirGapNACL
      RuleNumber: 200
      Protocol: -1
      RuleAction: allow
      Egress: false
      CidrBlock: 10.200.0.0/16

  # Security Group - internal only
  AirGapSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Air-gap security group - internal traffic only
      VpcId: !Ref AirGapVPC
      SecurityGroupIngress:
        - IpProtocol: -1
          CidrIp: 10.200.0.0/16
          Description: Allow all internal VPC traffic
      SecurityGroupEgress:
        - IpProtocol: -1
          CidrIp: 10.200.0.0/16
          Description: Allow all internal VPC traffic
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-airgap-sg-${Environment}'

  # KMS Key with FIPS endpoint
  AirGapKMSKey:
    Type: AWS::KMS::Key
    Properties:
      Description: !Sub 'Air-gap encryption key for ${ClassificationLevel}'
      EnableKeyRotation: true
      KeyPolicy:
        Version: '2012-10-17'
        Statement:
          - Sid: AllowKeyManagement
            Effect: Allow
            Principal:
              AWS: !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:root'
            Action:
              - kms:Create*
              - kms:Describe*
              - kms:Enable*
              - kms:List*
              - kms:Put*
              - kms:Update*
              - kms:Revoke*
              - kms:Disable*
              - kms:Get*
              - kms:Delete*
              - kms:ScheduleKeyDeletion
              - kms:CancelKeyDeletion
            Resource: '*'
      Tags:
        - Key: Classification
          Value: !Ref ClassificationLevel

  # S3 Bucket for bundle staging (internal only)
  BundleStagingBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub '${ProjectName}-airgap-bundles-${Environment}-${AWS::AccountId}'
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: aws:kms
              KMSMasterKeyID: !Ref AirGapKMSKey
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      VersioningConfiguration:
        Status: Enabled
      LoggingConfiguration:
        DestinationBucketName: !ImportValue
          Fn::Sub: '${ProjectName}-logging-bucket-${Environment}'
        LogFilePrefix: !Sub 'airgap-bundles/${Environment}/'

Outputs:
  AirGapVPCId:
    Value: !Ref AirGapVPC
    Export:
      Name: !Sub '${ProjectName}-airgap-vpc-id-${Environment}'

  AirGapSecurityGroupId:
    Value: !Ref AirGapSecurityGroup
    Export:
      Name: !Sub '${ProjectName}-airgap-sg-id-${Environment}'

  AirGapKMSKeyArn:
    Value: !GetAtt AirGapKMSKey.Arn
    Export:
      Name: !Sub '${ProjectName}-airgap-kms-key-arn-${Environment}'
```

---

## Estimated Metrics

| Metric | Target |
|--------|--------|
| Lines of Code | 13,500 |
| Test Count | 1,520 |
| Test Coverage | 90%+ (defense requirement) |
| CloudFormation Templates | 3 |
| API Endpoints | 15 |
| FIPS 140-3 Modules | 2 |
| Supported Architectures | 6 |
