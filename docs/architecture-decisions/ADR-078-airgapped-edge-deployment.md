# ADR-078: Air-Gapped and Edge Deployment Architecture

## Status

Deployed

## Date

2026-02-03

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Pending | AWS AI SaaS Architect | - | - |
| Pending | Senior Systems Architect | - | - |
| Pending | Cybersecurity Analyst | - | - |
| Pending | Test Architect | - | - |

### Review Summary

_Awaiting review._

## Context

### Market Opportunity

Air-gapped and edge deployment represents a significant untapped market for AI-powered code security. Defense contractors, critical infrastructure operators, and manufacturing facilities require security tooling that operates without internet connectivity.

**Target Markets:**
- **Anduril** - Defense autonomous systems (commercial classification)
- **Critical Infrastructure** - Energy, water, transportation (OT/ICS environments)
- **Manufacturing** - Automotive, aerospace (factory floor edge devices)
- **Government (Non-Classified)** - IL5/IL6 technical readiness (certification postponed)

**Market Opportunity:** Significant demand from defense and critical infrastructure customers

### Current State

Project Aura's self-hosted deployment (ADR-049) provides Podman-based local operation, but significant gaps remain for true air-gapped and edge scenarios:

| Current Capability | Gap | Business Impact |
|-------------------|-----|-----------------|
| Podman self-hosted | Requires periodic internet for model updates | Cannot operate in air-gapped |
| Python-based agents | Resource-intensive for edge devices | Cannot run on constrained hardware |
| Sigstore attestation | Requires Rekor transparency log access | No offline attestation verification |
| Standard SBOM analysis | No firmware/embedded support | Cannot analyze C/C++ embedded code |

### Requirements

| ID | Requirement | Source |
|----|-------------|--------|
| R1 | Complete offline operation (no internet required) | Air-gap mandate |
| R2 | Bundle packaging for secure transfer into isolated networks | DISA STIG |
| R3 | Firmware and embedded C/C++ security analysis | Critical infrastructure |
| R4 | RTOS support (FreeRTOS, VxWorks, QNX) | Anduril requirement |
| R5 | Resource-constrained operation (<2GB RAM, ARM) | Edge device limits |
| R6 | Offline SBOM signing with HSM/YubiKey | Attestation without Sigstore |
| R7 | Model quantization for edge inference | Performance requirement |
| R8 | Secure bundle integrity verification | Supply chain security |

**Note:** IL5/IL6 authorization has been postponed from this phase. Technical capabilities will be built to support future certification, but authorization activities are deferred.

## Decision

Implement an Air-Gapped and Edge Deployment architecture that enables Project Aura to operate in completely disconnected environments, analyze firmware and embedded code, and run on resource-constrained edge devices.

### Core Services

### 1. Air-Gap Orchestrator

**Responsibilities:**
- Bundle packaging for offline deployment (models, databases, configurations)
- Secure bundle creation with cryptographic signatures
- Bundle integrity verification on import
- Differential update bundles (delta transfers)
- Offline model registry management
- License activation for air-gapped environments

**Bundle Contents:**
- Quantized LLM models (ONNX/GGUF format)
- Pre-computed embeddings database
- Vulnerability databases (NVD, OSV, vendor-specific)
- SBOM component libraries
- Policy configurations
- Container images (OCI format)

### 2. Firmware Security Analyzer

**Responsibilities:**
- Binary analysis of compiled firmware images
- C/C++ source code security scanning
- Embedded library dependency extraction
- RTOS-specific vulnerability detection
- Memory safety analysis (buffer overflow, use-after-free)
- Compiler hardening verification (ASLR, stack canaries)
- Supply chain analysis for embedded components

**Supported Platforms:**
- FreeRTOS (Amazon IoT)
- VxWorks (Wind River)
- QNX (BlackBerry)
- Zephyr (Linux Foundation)
- Bare-metal embedded Linux
- Arduino/ESP32 environments

### 3. Tactical Edge Runtime

**Responsibilities:**
- Minimal footprint Aura deployment (<2GB RAM)
- ARM64 and x86 architecture support
- Quantized local LLM inference (Llama.cpp, ONNX Runtime)
- SQLite-based local storage (Neptune/OpenSearch not required)
- Offline-first synchronization when connectivity available
- Battery-aware operation for portable devices

**Deployment Targets:**
- Ruggedized laptops (Panasonic Toughbook)
- Industrial edge computers (Advantech, Dell Edge)
- ARM-based SBCs (Raspberry Pi, NVIDIA Jetson)
- Air-gapped development workstations

## Architecture

### Air-Gapped Deployment Architecture

```
+-----------------------------------------------------------------------------+
|                    Air-Gapped Deployment Architecture                        |
+-----------------------------------------------------------------------------+
|                                                                              |
|  CONNECTED ENVIRONMENT (Bundle Creation)                                    |
|  +----------------------------------------------------------------------+   |
|  |                                                                       |   |
|  |  +------------------+    +------------------+    +-----------------+  |   |
|  |  | Model Registry   |    | Vulnerability    |    | Policy          |  |   |
|  |  | (Bedrock/HF)     |    | Databases        |    | Configuration   |  |   |
|  |  +------------------+    +------------------+    +-----------------+  |   |
|  |         |                       |                       |             |   |
|  |         v                       v                       v             |   |
|  |  +----------------------------------------------------------------------+|
|  |  |                    Air-Gap Orchestrator                               ||
|  |  |                                                                       ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  |  | Bundle Creator   |  | Model Quantizer   |  | Signature Engine  |   ||
|  |  |  |                  |  |                   |  |                   |   ||
|  |  |  | - Component      |  | - GGUF/ONNX       |  | - Ed25519 signing |   ||
|  |  |  |   collection     |  | - INT8/INT4       |  | - Manifest hash   |   ||
|  |  |  | - Dependency     |  | - Knowledge       |  | - Chain of        |   ||
|  |  |  |   resolution     |  |   distillation    |  |   custody         |   ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  |                              |                                        ||
|  |  |                              v                                        ||
|  |  |                    +-----------------------+                          ||
|  |  |                    | Encrypted Bundle      |                          ||
|  |  |                    | (.aura-bundle)        |                          ||
|  |  |                    |                       |                          ||
|  |  |                    | - manifest.json       |                          ||
|  |  |                    | - models/             |                          ||
|  |  |                    | - vuln-db/            |                          ||
|  |  |                    | - signatures/         |                          ||
|  |  |                    +-----------------------+                          ||
|  |  +----------------------------------------------------------------------+|
|  +----------------------------------------------------------------------+   |
|                              |                                               |
|                              | Secure Transfer (USB/DVD/Cross-Domain)        |
|                              v                                               |
|  AIR-GAPPED ENVIRONMENT                                                      |
|  +----------------------------------------------------------------------+   |
|  |                                                                       |   |
|  |  +----------------------------------------------------------------------+|
|  |  |                    Bundle Import Service                              ||
|  |  |                                                                       ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  |  | Integrity        |  | Signature         |  | Manifest          |   ||
|  |  |  | Verification     |  | Validation        |  | Parser            |   ||
|  |  |  | (SHA-256)        |  | (Ed25519/HSM)     |  |                   |   ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  +----------------------------------------------------------------------+|
|  |         |                                                             |   |
|  |         v                                                             |   |
|  |  +----------------------------------------------------------------------+|
|  |  |                    Air-Gapped Aura Runtime                           ||
|  |  |                                                                       ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  |  | Local LLM        |  | Vulnerability     |  | Code Analysis     |   ||
|  |  |  | (Llama.cpp)      |  | Scanner           |  | Engine            |   ||
|  |  |  | (ONNX Runtime)   |  | (Offline NVD)     |  | (AST/Graph)       |   ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  |                                                                       ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  |  | SBOM Generator   |  | Offline Signer    |  | Report            |   ||
|  |  |  | (CycloneDX)      |  | (HSM/YubiKey)     |  | Generator         |   ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  +----------------------------------------------------------------------+|
|  +----------------------------------------------------------------------+   |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### Firmware Security Analyzer Architecture

```
+-----------------------------------------------------------------------------+
|                    Firmware Security Analyzer Architecture                   |
+-----------------------------------------------------------------------------+
|                                                                              |
|  Input: Firmware Image / Source Code                                        |
|  +----------------------------------------------------------------------+   |
|  |  +-------------------+  +-------------------+  +-------------------+  |   |
|  |  | Binary (.elf,     |  | Source (C/C++,    |  | SDK/HAL           |  |   |
|  |  |  .bin, .hex)      |  |  Assembly)        |  | Libraries         |  |   |
|  |  +-------------------+  +-------------------+  +-------------------+  |   |
|  +----------------------------------------------------------------------+   |
|         |                         |                       |                  |
|         v                         v                       v                  |
|  +----------------------------------------------------------------------+   |
|  |                    Firmware Extraction Layer                          |   |
|  |                                                                       |   |
|  |  +-------------------+  +-------------------+  +-------------------+  |   |
|  |  | Binwalk           |  | Ghidra/Radare2    |  | LLVM/Clang        |  |   |
|  |  | (Filesystem       |  | (Disassembly)     |  | (Source Analysis) |  |   |
|  |  |  Extraction)      |  |                   |  |                   |  |   |
|  |  +-------------------+  +-------------------+  +-------------------+  |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                    Analysis Engine                                    |   |
|  |                                                                       |   |
|  |  +---------------------------+    +---------------------------+       |   |
|  |  | Memory Safety Analyzer    |    | Dependency Extractor      |       |   |
|  |  |                           |    |                           |       |   |
|  |  | - Buffer overflow         |    | - Static linking detect   |       |   |
|  |  | - Use-after-free          |    | - Version fingerprinting  |       |   |
|  |  | - Integer overflow        |    | - Symbol analysis         |       |   |
|  |  | - Format string           |    | - License detection       |       |   |
|  |  +---------------------------+    +---------------------------+       |   |
|  |                                                                       |   |
|  |  +---------------------------+    +---------------------------+       |   |
|  |  | RTOS Analyzer             |    | Compiler Hardening Check  |       |   |
|  |  |                           |    |                           |       |   |
|  |  | - FreeRTOS patterns       |    | - Stack canaries          |       |   |
|  |  | - VxWorks syscalls        |    | - ASLR/PIE                |       |   |
|  |  | - QNX IPC                 |    | - NX/DEP                  |       |   |
|  |  | - Zephyr kernel           |    | - RELRO                   |       |   |
|  |  +---------------------------+    +---------------------------+       |   |
|  |                                                                       |   |
|  |  +---------------------------+    +---------------------------+       |   |
|  |  | Crypto Analyzer           |    | Supply Chain Validator    |       |   |
|  |  |                           |    |                           |       |   |
|  |  | - Weak algorithms         |    | - Known vulnerable libs   |       |   |
|  |  | - Hardcoded keys          |    | - Outdated components     |       |   |
|  |  | - Entropy analysis        |    | - Malicious patterns      |       |   |
|  |  +---------------------------+    +---------------------------+       |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                    Firmware SBOM Generator                            |   |
|  |                                                                       |   |
|  |  Components:                                                          |   |
|  |  - Extracted libraries with versions                                  |   |
|  |  - RTOS version and configuration                                     |   |
|  |  - Compiler toolchain                                                 |   |
|  |  - Hardware abstraction layer                                         |   |
|  |  - Third-party middleware                                             |   |
|  |                                                                       |   |
|  |  Output: CycloneDX 1.5 SBOM with firmware-specific extensions         |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                    Vulnerability Correlation                          |   |
|  |                                                                       |   |
|  |  - NVD matching                                                       |   |
|  |  - ICS-CERT advisories                                                |   |
|  |  - Vendor-specific CVEs (TI, ST, NXP, Infineon)                       |   |
|  |  - RTOS-specific vulnerabilities                                      |   |
|  |  - Memory corruption patterns                                         |   |
|  +----------------------------------------------------------------------+   |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### Tactical Edge Runtime Architecture

```
+-----------------------------------------------------------------------------+
|                    Tactical Edge Runtime Architecture                        |
+-----------------------------------------------------------------------------+
|                                                                              |
|  Edge Device (Constrained Environment)                                      |
|  +----------------------------------------------------------------------+   |
|  |  Hardware: ARM64/x86, 2-8GB RAM, 32GB+ Storage                        |   |
|  |  OS: Linux (Ubuntu/Debian), Windows 10/11                             |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                    Aura Edge Container                                |   |
|  |                                                                       |   |
|  |  +----------------------------------------------------------------------+|
|  |  |                    Quantized Inference Engine                        ||
|  |  |                                                                       ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  |  | Llama.cpp        |  | ONNX Runtime      |  | Model Cache       |   ||
|  |  |  | (GGUF Q4/Q8)     |  | (INT8 quantized)  |  | (Memory-mapped)   |   ||
|  |  |  |                  |  |                   |  |                   |   ||
|  |  |  | - Code analysis  |  | - Embedding       |  | - 1-2GB footprint |   ||
|  |  |  | - Remediation    |  | - Classification  |  | - Lazy loading    |   ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  +----------------------------------------------------------------------+|
|  |                                                                       |   |
|  |  +----------------------------------------------------------------------+|
|  |  |                    Local Storage (SQLite)                            ||
|  |  |                                                                       ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  |  | Code Graph       |  | SBOM Store        |  | Findings          |   ||
|  |  |  | (Adjacency List) |  | (JSON + Index)    |  | (Structured)      |   ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  +----------------------------------------------------------------------+|
|  |                                                                       |   |
|  |  +----------------------------------------------------------------------+|
|  |  |                    Offline Analysis Services                         ||
|  |  |                                                                       ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  |  | Static Analyzer  |  | SBOM Generator    |  | Vuln Scanner      |   ||
|  |  |  | (AST-based)      |  | (CycloneDX)       |  | (Offline DB)      |   ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  |                                                                       ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  |  | Report Generator |  | Sync Manager      |  | License Manager   |   ||
|  |  |  | (PDF/HTML)       |  | (When connected)  |  | (Offline valid)   |   ||
|  |  |  +------------------+  +-------------------+  +-------------------+   ||
|  |  +----------------------------------------------------------------------+|
|  +----------------------------------------------------------------------+   |
|                                                                              |
|  Synchronization (When Network Available)                                   |
|  +----------------------------------------------------------------------+   |
|  |  - Delta sync of findings to central Aura                             |   |
|  |  - Model/vulnerability database updates                               |   |
|  |  - Policy configuration sync                                          |   |
|  |  - License renewal check                                              |   |
|  +----------------------------------------------------------------------+   |
|                                                                              |
+-----------------------------------------------------------------------------+
```

## Data Models

### Bundle Manifest Schema

```json
{
  "$schema": "https://aura.aenealabs.com/schemas/bundle-manifest-v1.json",
  "manifest_version": "1.0",
  "bundle_id": "bundle-2026-02-03-abc123",
  "created_at": "2026-02-03T10:00:00Z",
  "expires_at": "2027-02-03T10:00:00Z",
  "created_by": "release-pipeline@aenealabs.com",
  "signature": {
    "algorithm": "Ed25519",
    "public_key_id": "aura-release-key-2026",
    "signature_value": "base64-encoded-signature"
  },
  "contents": {
    "models": [
      {
        "name": "aura-code-analyzer",
        "version": "2.1.0",
        "format": "gguf",
        "quantization": "Q4_K_M",
        "size_bytes": 4200000000,
        "sha256": "abc123..."
      }
    ],
    "databases": [
      {
        "name": "nvd-vulnerabilities",
        "version": "2026-02-03",
        "format": "sqlite",
        "size_bytes": 2100000000,
        "sha256": "def456..."
      }
    ],
    "containers": [
      {
        "name": "aura-edge-runtime",
        "tag": "v3.5.0",
        "digest": "sha256:789abc...",
        "size_bytes": 850000000
      }
    ],
    "policies": [
      {
        "name": "default-security-policy",
        "version": "1.2.0",
        "sha256": "ghi789..."
      }
    ]
  },
  "compatibility": {
    "min_aura_version": "3.0.0",
    "architectures": ["amd64", "arm64"],
    "required_features": ["offline-llm", "sqlite-graph"]
  }
}
```

### Firmware Analysis Schema

```json
{
  "firmware_id": "fw-abc123",
  "image_path": "/path/to/firmware.bin",
  "image_sha256": "sha256-hash",
  "analysis_timestamp": "2026-02-03T10:00:00Z",
  "extraction": {
    "filesystems": [
      {
        "type": "squashfs",
        "offset": 1048576,
        "size": 15728640,
        "files_count": 2847
      }
    ],
    "rtos_detected": {
      "name": "FreeRTOS",
      "version": "10.4.3",
      "kernel_config": {
        "max_priorities": 7,
        "tick_rate_hz": 1000,
        "heap_size": 131072
      }
    }
  },
  "components": [
    {
      "name": "mbedtls",
      "version": "2.28.0",
      "detection_method": "symbol_analysis",
      "confidence": 0.95,
      "license": "Apache-2.0"
    }
  ],
  "vulnerabilities": [
    {
      "cve_id": "CVE-2026-1234",
      "component": "mbedtls",
      "severity": "HIGH",
      "cvss_v3": 8.1,
      "description": "Buffer overflow in X.509 parsing"
    }
  ],
  "hardening": {
    "stack_canaries": false,
    "aslr_enabled": false,
    "nx_enabled": true,
    "relro": "partial"
  }
}
```

### Edge Runtime SQLite Schema

```sql
-- Code graph storage (simplified from Neptune)
CREATE TABLE code_nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,  -- 'file', 'function', 'class', 'dependency'
    name TEXT NOT NULL,
    file_path TEXT,
    line_start INTEGER,
    line_end INTEGER,
    metadata JSON,
    embedding BLOB  -- Quantized embedding vector
);

CREATE TABLE code_edges (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,  -- 'calls', 'imports', 'inherits', 'depends_on'
    metadata JSON,
    PRIMARY KEY (source_id, target_id, edge_type),
    FOREIGN KEY (source_id) REFERENCES code_nodes(id),
    FOREIGN KEY (target_id) REFERENCES code_nodes(id)
);

-- Vulnerability findings
CREATE TABLE findings (
    id TEXT PRIMARY KEY,
    code_node_id TEXT NOT NULL,
    vuln_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    description TEXT,
    remediation TEXT,
    created_at TEXT,
    synced_at TEXT,  -- NULL if not yet synced to central
    FOREIGN KEY (code_node_id) REFERENCES code_nodes(id)
);

-- SBOM storage
CREATE TABLE sbom_components (
    id TEXT PRIMARY KEY,
    sbom_id TEXT NOT NULL,
    name TEXT NOT NULL,
    version TEXT,
    purl TEXT,
    license TEXT,
    vulnerabilities JSON
);

-- Sync queue for when connectivity available
CREATE TABLE sync_queue (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,  -- 'finding', 'sbom', 'analysis'
    entity_id TEXT NOT NULL,
    operation TEXT NOT NULL,    -- 'create', 'update'
    payload JSON,
    created_at TEXT,
    retries INTEGER DEFAULT 0
);

-- Indexes
CREATE INDEX idx_nodes_type ON code_nodes(node_type);
CREATE INDEX idx_nodes_path ON code_nodes(file_path);
CREATE INDEX idx_edges_type ON code_edges(edge_type);
CREATE INDEX idx_findings_severity ON findings(severity);
CREATE INDEX idx_sync_created ON sync_queue(created_at);
```

## API Endpoints

### Air-Gap Orchestrator APIs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/airgap/bundle/create` | Create new offline bundle |
| GET | `/api/v1/airgap/bundle/{id}` | Get bundle metadata |
| GET | `/api/v1/airgap/bundle/{id}/download` | Download bundle file |
| POST | `/api/v1/airgap/bundle/verify` | Verify bundle signature |
| POST | `/api/v1/airgap/bundle/import` | Import bundle into air-gapped env |
| GET | `/api/v1/airgap/bundle/diff` | Calculate delta for update bundle |
| POST | `/api/v1/airgap/license/activate` | Activate offline license |
| GET | `/api/v1/airgap/license/status` | Check license validity |

### Firmware Analyzer APIs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/firmware/analyze` | Analyze firmware image |
| GET | `/api/v1/firmware/analysis/{id}` | Get analysis results |
| GET | `/api/v1/firmware/analysis/{id}/sbom` | Get firmware SBOM |
| GET | `/api/v1/firmware/analysis/{id}/vulns` | Get vulnerabilities |
| GET | `/api/v1/firmware/rtos` | List supported RTOS |
| POST | `/api/v1/firmware/source/analyze` | Analyze C/C++ source |
| GET | `/api/v1/firmware/hardening/{id}` | Get hardening report |

### Edge Runtime APIs (Local)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/edge/scan` | Scan local repository |
| GET | `/api/v1/edge/findings` | Get local findings |
| POST | `/api/v1/edge/sbom/generate` | Generate SBOM locally |
| POST | `/api/v1/edge/sync` | Trigger sync to central |
| GET | `/api/v1/edge/sync/status` | Check sync status |
| GET | `/api/v1/edge/health` | Runtime health check |
| GET | `/api/v1/edge/resources` | Resource usage stats |

## Implementation Plan

### Phase 1: Air-Gap Orchestrator (Weeks 1-4)

| Task | Effort | Deliverables |
|------|--------|--------------|
| Bundle schema and manifest format | 0.5 week | JSON schema, validation |
| Bundle creation pipeline | 1 week | Model packaging, DB bundling |
| Cryptographic signing (Ed25519) | 0.5 week | Signing service, key management |
| Bundle import and verification | 1 week | Import service, integrity checks |
| Differential update bundles | 1 week | Delta calculation, patching |

**Estimated LOC:** 5,200 lines Python
**Tests:** 160 tests

### Phase 2: Firmware Security Analyzer (Weeks 5-7)

| Task | Effort | Deliverables |
|------|--------|--------------|
| Binary extraction (Binwalk integration) | 1 week | Filesystem extraction |
| C/C++ static analysis (Clang) | 1 week | AST analysis, memory safety |
| RTOS pattern detection | 0.5 week | FreeRTOS, VxWorks, QNX |
| Dependency extraction and fingerprinting | 0.5 week | Library version detection |

**Estimated LOC:** 4,800 lines Python + 600 lines C
**Tests:** 140 tests

### Phase 3: Tactical Edge Runtime (Weeks 8-10)

| Task | Effort | Deliverables |
|------|--------|--------------|
| Quantized model integration | 1 week | Llama.cpp, ONNX Runtime |
| SQLite graph storage | 0.5 week | Schema, query engine |
| Offline analysis services | 1 week | Scanner, SBOM generator |
| Sync manager | 0.5 week | Delta sync when connected |

**Estimated LOC:** 4,200 lines Python
**Tests:** 120 tests

## Infrastructure Requirements

### CloudFormation Templates

| Template | Layer | Description |
|----------|-------|-------------|
| `airgap-bundle-storage.yaml` | 2.10 | S3 buckets, KMS keys for bundles |
| `airgap-orchestrator.yaml` | 6.11 | Lambda functions, Step Functions |
| `firmware-analyzer.yaml` | 6.12 | ECS tasks, ECR images |
| `edge-distribution.yaml` | 4.6 | CloudFront, container registry |

### On-Premises Requirements

| Component | Specification |
|-----------|---------------|
| Air-Gap Server | 8 vCPU, 32GB RAM, 500GB SSD |
| Edge Device (Minimum) | 2 vCPU, 2GB RAM, 32GB storage |
| Edge Device (Recommended) | 4 vCPU, 8GB RAM, 128GB SSD |
| HSM (Optional) | YubiHSM 2 or CloudHSM equivalent |

## Security Considerations

### Bundle Security

| Threat | Mitigation |
|--------|------------|
| Bundle tampering | Ed25519 signature verification |
| Model poisoning | Hash verification for all components |
| Stale vulnerability data | Expiration dates in manifest |
| License circumvention | Hardware-bound license tokens |
| Supply chain attack | Signed chain of custody |

### Firmware Analysis Security

| Threat | Mitigation |
|--------|------------|
| Malicious firmware execution | Sandboxed analysis (gVisor) |
| Reverse engineering exposure | Analysis-only, no execution |
| Sensitive firmware leakage | Encrypted storage, access controls |
| False negatives | Multiple detection methods |

### Edge Runtime Security

| Threat | Mitigation |
|--------|------------|
| Device compromise | Encrypted local storage |
| Model extraction | Quantized models only |
| Unauthorized sync | Mutual TLS for sync |
| Offline tampering | Signed configuration |

### Compliance Considerations

**Note:** IL5/IL6 certification has been postponed from this phase. However, the architecture is designed to support future certification:

| Technical Capability | Status |
|---------------------|--------|
| Encryption at rest (AES-256) | Included |
| Encryption in transit (TLS 1.3) | Included |
| Hardware-bound keys | Supported |
| Audit logging | Included |
| FIPS 140-2 crypto modules | Architecture supports, not implemented |
| DoD PKI integration | Architecture supports, not implemented |

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Bundle creation time | <30 minutes | End-to-end timing |
| Bundle import time | <15 minutes | Import service metrics |
| Firmware analysis time | <10 minutes per image | Analysis timing |
| Edge runtime memory | <2GB | Runtime monitoring |
| Edge inference latency | <5s per analysis | Local benchmarks |
| Offline license validity | 365 days | License management |
| Sync success rate | >99% | Sync manager metrics |

## Alternatives Considered

### Alternative 1: Partner with Existing Firmware Analyzer

Integrate with existing firmware security tools (EMBA, Firmware Analysis Toolkit).

**Pros:**
- Faster implementation
- Proven analysis capabilities
- Community support

**Cons:**
- External dependency
- Limited integration with Aura graph
- No code-to-firmware correlation

**Decision:** Hybrid approach - use Binwalk for extraction, custom analysis for Aura integration

### Alternative 2: Cloud-Only with VPN

Require VPN connectivity instead of true air-gap support.

**Pros:**
- Simpler architecture
- Always up-to-date
- No bundle management

**Cons:**
- Not acceptable for classified environments
- Network dependency
- Higher latency

**Decision:** Rejected - true air-gap is a firm customer requirement

### Alternative 3: Full LLM on Edge

Run full (non-quantized) LLM on edge devices.

**Pros:**
- Better analysis quality
- No quantization artifacts

**Cons:**
- Requires 32GB+ RAM
- Not suitable for constrained devices
- Higher power consumption

**Decision:** Quantized models for edge, full models for bundle updates

## Consequences

### Positive

1. **New Market Access** - Defense, critical infrastructure, manufacturing
2. **True Air-Gap Support** - Meets strict isolation requirements
3. **Firmware Coverage** - Unique capability for embedded security
4. **Edge Flexibility** - Portable security analysis anywhere
5. **Supply Chain Security** - Signed, verified offline updates
6. **Customer Trust** - Demonstrates commitment to secure-by-design

### Negative

1. **Complexity** - Multiple deployment modes to support
2. **Model Quality** - Quantized models have reduced accuracy
3. **Update Lag** - Air-gapped environments get delayed updates
4. **Support Burden** - Harder to troubleshoot disconnected systems
5. **Testing Matrix** - More environments to validate

### Migration Path

1. **Existing Self-Hosted** - Bundle import alongside existing Podman deployment
2. **New Air-Gap** - Fresh installation from bundle
3. **Edge Deployment** - Standalone with optional sync

## Cost Estimate

### Development Cost

| Phase | Weeks | Engineers | Total Cost |
|-------|-------|-----------|------------|
| Air-Gap Orchestrator | 4 | 2 | $80,000 |
| Firmware Analyzer | 3 | 2 | $60,000 |
| Edge Runtime | 3 | 2 | $60,000 |
| **Total** | 10 | | **$200,000** |

### Infrastructure Cost (Cloud Components)

| Component | Monthly Cost |
|-----------|--------------|
| S3 (bundle storage) | $50 |
| Lambda (orchestrator) | $25 |
| ECS (firmware analyzer) | $100 |
| CloudFront (distribution) | $75 |
| **Total** | **~$250/month** |

### Customer Deployment Cost

| Deployment Type | Hardware Cost | Notes |
|-----------------|---------------|-------|
| Air-Gap Server | $5,000-15,000 | One-time purchase |
| Edge Device | $500-2,000 | Per device |
| HSM (optional) | $650 | YubiHSM 2 |

## GovCloud Compatibility

| Service | GovCloud Available | Notes |
|---------|-------------------|-------|
| S3 | Yes | Bundle storage |
| Lambda | Yes | Orchestrator functions |
| ECS | Yes | Firmware analyzer |
| KMS | Yes | Key management |
| Step Functions | Yes | Workflow orchestration |

**GovCloud-Specific Considerations:**
- All bundles created in GovCloud for government customers
- Separate signing keys for commercial vs. government
- FIPS-validated crypto modules when required
- IL5/IL6 considerations for future certification

## References

- [Binwalk - Firmware Analysis Tool](https://github.com/ReFirmLabs/binwalk)
- [Ghidra - Reverse Engineering](https://ghidra-sre.org/)
- [Llama.cpp - Efficient LLM Inference](https://github.com/ggerganov/llama.cpp)
- [ONNX Runtime](https://onnxruntime.ai/)
- [FreeRTOS Security](https://freertos.org/security.html)
- [NIST SP 800-82 - ICS Security](https://csrc.nist.gov/publications/detail/sp/800-82/rev-3/final)
- [ICS-CERT Advisories](https://www.cisa.gov/uscert/ics)
- [ADR-049: Self-Hosted Deployment Strategy](/docs/architecture-decisions/ADR-049-self-hosted-deployment-strategy.md)
- [ADR-076: SBOM Attestation and Supply Chain Security](/docs/architecture-decisions/ADR-076-sbom-attestation-supply-chain.md)
