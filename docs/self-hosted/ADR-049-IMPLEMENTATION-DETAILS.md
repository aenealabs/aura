# ADR-049 Implementation Details

> **Parent ADR:** [ADR-049: Self-Hosted Deployment Strategy](../architecture-decisions/ADR-049-self-hosted-deployment-strategy.md)

This document contains technical specifications, expert review findings, and appendices for ADR-049.

---

## Table of Contents

1. [Technical Specification](#technical-specification)
2. [Security Architecture](#security-architecture)
3. [Database Provider Comparison](#database-provider-comparison)
4. [LLM Provider Comparison](#llm-provider-comparison)
5. [Architecture Review Findings](#architecture-review-findings)
6. [Required Documentation](#required-documentation)
7. [Support Model](#support-model)
8. [Appendices](#appendices)

---

## Technical Specification

### 1. Database Adapter Extensions (ADR-004 Enhancement)

Extend the Cloud Abstraction Layer with self-hosted database providers:

```python
# src/services/providers/graph/neo4j_adapter.py
from abc import ABC
from src.services.providers.base import GraphProvider

class Neo4jAdapter(GraphProvider):
    """Self-hosted graph database adapter using Neo4j.

    Uses Neo4j's APOC Gremlin compatibility layer for query compatibility
    with existing Neptune/Gremlin codebase.
    """

    def __init__(self, uri: str, auth: tuple, encrypted: bool = True):
        self.driver = GraphDatabase.driver(
            uri, auth=auth, encrypted=encrypted
        )

    async def create_entity(self, entity: Entity) -> str:
        async with self.driver.session() as session:
            result = await session.run(
                "CREATE (n:Entity $props) RETURN id(n)",
                props=entity.to_dict()
            )
            return str(result.single()["id(n)"])
```

### 2. LLM Provider Abstraction

```python
# src/services/providers/llm/base.py
class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    async def complete(self, prompt: str, **kwargs) -> str:
        pass

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        pass

# src/services/providers/llm/vllm_provider.py
class VLLMProvider(LLMProvider):
    """Self-hosted LLM using vLLM inference engine."""

    def __init__(self, model_name: str, api_base: str = "http://localhost:8000"):
        self.client = OpenAI(base_url=f"{api_base}/v1", api_key="dummy")
        self.model = model_name
```

### 3. Podman Compose Configuration

```yaml
# deploy/self-hosted/podman-compose.yml
version: "3.8"

services:
  aura-api:
    image: ghcr.io/aenealabs/aura-api:${VERSION}
    environment:
      - CLOUD_PROVIDER=SELF_HOSTED
      - GRAPH_DATABASE_URI=bolt+s://neo4j:7687
      - VECTOR_DATABASE_URI=https://opensearch:9200
    depends_on:
      - neo4j
      - opensearch
    networks:
      - aura-internal
    security_opt:
      - seccomp:unconfined
    cap_drop:
      - ALL
    read_only: true

  neo4j:
    image: neo4j:5-enterprise
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_ACCEPT_LICENSE_AGREEMENT=yes
      - NEO4J_dbms_ssl_policy_bolt_enabled=true
    volumes:
      - neo4j-data:/data
      - ./certs:/ssl:ro

  opensearch:
    image: opensearchproject/opensearch:2.11.0
    environment:
      - cluster.name=aura-search
      - plugins.security.ssl.http.enabled=true
    volumes:
      - opensearch-data:/usr/share/opensearch/data

networks:
  aura-internal:
    driver: bridge
    internal: true

volumes:
  neo4j-data:
  opensearch-data:
```

---

## Security Architecture

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                           CUSTOMER RESPONSIBILITY                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │  • Network security (firewalls, VPN, network segmentation)              │  │
│  │  • OS hardening and patching                                            │  │
│  │  • TLS certificate management and rotation                              │  │
│  │  • Physical security                                                    │  │
│  │  • Backup and disaster recovery                                         │  │
│  │  • User access management                                               │  │
│  │  • Compliance documentation                                             │  │
│  │  • LLM model license compliance                                         │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────────┐
│                           AURA RESPONSIBILITY                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │  • Secure default configurations (TLS everywhere)                       │  │
│  │  • Container image scanning (Trivy, Snyk)                               │  │
│  │  • SBOM generation for all images                                       │  │
│  │  • Security advisories and patch releases                               │  │
│  │  • Secure update mechanism                                              │  │
│  │  • Encryption at rest and in transit defaults                           │  │
│  │  • Secrets management guidance                                          │  │
│  │  • Inference engine security (vLLM/TGI hardening)                       │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────┘
```

### TLS Requirements (Non-Negotiable)

| Service | Protocol | Port | TLS Required |
|---------|----------|------|--------------|
| Neo4j Browser | HTTPS | 7473 | ✅ Yes |
| Neo4j Bolt | bolt+s | 7687 | ✅ Yes |
| OpenSearch | HTTPS | 9200 | ✅ Yes |
| PostgreSQL | TLS | 5432 | ✅ Yes |
| Redis | TLS | 6379 | ✅ Yes |
| Aura API | HTTPS | 443 | ✅ Yes |
| vLLM/TGI | HTTPS | 8443 | ✅ Yes |

**IMPORTANT:** HTTP is never acceptable, even for internal service-to-service communication.

### Container Security

| Control | Implementation |
|---------|----------------|
| Base Images | Distroless or Alpine-based minimal images |
| Vulnerability Scanning | Trivy in CI/CD, block HIGH/CRITICAL |
| Image Signing | Cosign with Sigstore |
| SBOM | Syft-generated SPDX/CycloneDX |
| Runtime | Read-only root filesystem, non-root user |
| Secrets | Never in images, mount at runtime |

### LLM Security Considerations

| Risk | Mitigation |
|------|------------|
| Prompt injection | Input sanitization, output filtering |
| Model theft | Encrypted model storage, access controls |
| Inference API abuse | Rate limiting, authentication required |
| Data exfiltration via prompts | Network segmentation, egress filtering |

---

## Database Provider Comparison

| Feature | Neptune (SaaS) | Neo4j (Self-Hosted) | JanusGraph |
|---------|---------------|---------------------|------------|
| Query Language | Gremlin | Cypher + Gremlin | Gremlin |
| ACID Transactions | Yes | Yes | Eventual |
| Clustering | Managed | Manual/Operator | Manual |
| Graph Algorithms | Limited | GDS Library | TinkerPop |
| TLS Support | Managed | Required config | Manual |
| Operational Overhead | None | Medium | High |
| License | AWS Service | AGPL/Commercial | Apache 2.0 |
| **Recommendation** | SaaS default | **Primary self-hosted** | Alternative |

---

## LLM Provider Comparison

| Provider | License | Commercial Use | GPU Required | Latency | Cost |
|----------|---------|----------------|--------------|---------|------|
| AWS Bedrock | Commercial | ✅ | No (managed) | Low | Per-token |
| Azure OpenAI | Commercial | ✅ | No (managed) | Low | Per-token |
| vLLM | Apache 2.0 | ✅ | Yes | Very Low | Infrastructure |
| TGI | Apache 2.0 | ✅ | Yes | Very Low | Infrastructure |

**Recommendations:**
- Enterprise (connected): Bedrock/Azure via PrivateLink
- Enterprise (air-gap): vLLM + Mistral (Apache 2.0)

---

## Architecture Review Findings

> **Review Date:** 2025-12-31
> **Reviewers:** Infrastructure Architect, Security Analyst, Senior Systems Architect

### Executive Summary

Three specialized architecture reviews were conducted. The ADR was **directionally sound** but required remediation. Critical gaps were identified in security controls, query language strategy, and migration tooling. Timeline revised from 24 weeks to 33 weeks.

### Review 1: Infrastructure Architecture

**Assessment:** Generally Sound with Gaps

| Finding | Severity | Resolution |
|---------|----------|------------|
| Query language mismatch (Gremlin vs Cypher) | Critical | Added to Phase 0 |
| Windows Server GPU limitations | High | Documented WSL2 requirement |
| macOS ARM cannot use NVIDIA GPUs | Medium | Added llama.cpp option |
| Database HA not addressed | High | Documented limitation |

#### Deployment Sizing Guide

| Tier | Users | Deployment | RAM | CPU | GPU |
|------|-------|------------|-----|-----|-----|
| Evaluation | 1-5 | Podman Compose | 32GB | 8 cores | Optional |
| Small Team | 5-20 | Podman Compose | 64GB | 16 cores | 1x T4/A10 |
| Production | 20-500 | Kubernetes | 128GB+ | 32+ cores | 2-4x GPUs |
| Enterprise | 500+ | Kubernetes HA | Cluster | Cluster | Multi-node |

#### GPU Requirements for LLM Inference

| Model Size | Minimum GPU | Recommended GPU | VRAM Required |
|------------|-------------|-----------------|---------------|
| 7B (Mistral) | T4 16GB | A10G 24GB | 14-16GB |
| 13B | A10G 24GB | A100 40GB | 26-28GB |
| 70B | 2x A100 80GB | 4x A100 80GB | 140GB+ |
| MoE 8x7B (Mixtral) | A100 40GB | A100 80GB | 45-50GB |

### Review 2: Security Analysis

**Assessment:** HIGH Risk - Requires Remediation

| Severity | Count | Key Issues |
|----------|-------|------------|
| **CRITICAL** | 4 | No default-deny NetworkPolicy, no prompt injection mitigation |
| **HIGH** | 16 | Weak secrets management, missing container security controls |
| **MEDIUM** | 14 | HTTP healthchecks, missing mTLS |
| **LOW** | 3 | Certificate pinning, security patch SLA |

#### Critical Security Requirements

1. **Default-Deny NetworkPolicy**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: aura
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

2. **Cryptographic License Validation (Ed25519)**
```
License = base64(payload || signature)
Payload = JSON {customer_id, tier, expiry, features, hardware_fingerprint}
Signature = Ed25519.sign(private_key, sha256(payload))
```

3. **Container Security Contexts**
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
  seccompProfile:
    type: RuntimeDefault
```

### Review 3: Systems Architecture

**Assessment:** Directionally Sound - Not Implementation Ready

| Finding | Severity | Resolution |
|---------|----------|------------|
| DynamoDB schema undocumented | High | Added to Phase 0 |
| No migration toolkit | High | Added Phase 1.5 |
| Feature parity testing undefined | Medium | Added tiered testing |
| Upgrade/rollback undefined | High | Added version compatibility |

### Risk Heat Map

```
                    PROBABILITY
                    Low    Medium    High
              ┌─────────┬─────────┬─────────┐
         High │         │ FIPS    │ Gremlin │
              │         │ Supply  │ Schema  │
    IMPACT    ├─────────┼─────────┼─────────┤
       Medium │         │ Air-gap │ Test    │
              │         │ Win GPU │ Matrix  │
              ├─────────┼─────────┼─────────┤
          Low │         │         │         │
              └─────────┴─────────┴─────────┘
```

---

## Required Documentation

| Document | Audience | Phase | Priority |
|----------|----------|-------|----------|
| Installation Guide | Admins | 1 | P0 |
| Configuration Reference | Admins | 1 | P0 |
| Security Hardening Guide | Security Teams | 1 | P0 |
| LLM Model Licensing Guide | Legal/Admins | 1 | P0 |
| Migration Guide (SaaS→Self-Hosted) | Admins | 1.5 | P0 |
| Upgrade/Rollback Guide | Admins | 2 | P0 |
| Troubleshooting Guide | Admins/Support | 2 | P1 |
| Backup/Restore Guide | Admins | 3 | P1 |
| FIPS 140-2 Compliance Guide | Security | 3 | P1 |
| Performance Tuning Guide | Admins | 3 | P2 |

---

## Support Model

### Support Levels

| Level | Response SLA | Availability | Channels | Edition |
|-------|--------------|--------------|----------|---------|
| Community | Best effort | GitHub Issues | Forum, GitHub | Community |
| Standard | 24 hours | Business hours | Email, Portal | Enterprise |
| Premium | 4 hours | 24/7 | Phone, Dedicated | Enterprise+ |

### Support Tooling

1. **Support Bundle Generator**
```bash
aura-cli support-bundle generate --output /tmp/support-bundle.tar.gz
# Includes: system info, logs (redacted), config (secrets redacted), health checks
```

2. **Diagnostic Endpoints**
   - `/healthz` - Kubernetes liveness probe
   - `/readyz` - Kubernetes readiness probe
   - `/debug/pprof` - Performance profiling (Enterprise only)

---

## Appendices

### Appendix A: Platform Support Matrix

| Platform | Version | Podman | K8s | Native CLI | Status |
|----------|---------|--------|-----|------------|--------|
| Ubuntu | 20.04, 22.04, 24.04 LTS | ✅ | ✅ | ✅ .deb | ✅ Complete |
| RHEL | 8.x, 9.x | ✅ | ✅ | ✅ .rpm | ✅ Complete |
| Windows Server | 2019, 2022 | ✅ | ✅ | ✅ .msi | ✅ Complete |
| macOS | 12+ (Intel/ARM) | ✅ | ✅ | ✅ .pkg | ✅ Complete |

### Appendix B: Service Port Mapping

| Service | Default Port | Protocol | Configurable |
|---------|-------------|----------|--------------|
| Aura API | 8080 | HTTPS | API_PORT |
| Aura Frontend | 3000 | HTTPS | FRONTEND_PORT |
| Neo4j Bolt | 7687 | bolt+s (TLS) | NEO4J_BOLT_PORT |
| Neo4j Browser | 7473 | HTTPS | NEO4J_HTTPS_PORT |
| OpenSearch | 9200 | HTTPS | OPENSEARCH_PORT |
| PostgreSQL | 5432 | TLS | POSTGRES_PORT |
| vLLM | 8443 | HTTPS | VLLM_PORT |

### Appendix C: Recommended LLM Models

| Use Case | Model | License | Parameters |
|----------|-------|---------|------------|
| General code intelligence | Mistral-7B-Instruct | Apache 2.0 | 7B |
| High-quality code generation | Qwen2.5-Coder-7B | Apache 2.0 | 7B |
| Enterprise (large context) | Mistral-8x7B-Instruct | Apache 2.0 | 46.7B (MoE) |
| CPU-only evaluation | Mistral-7B-Q4_K_M | Apache 2.0 | 7B (quantized) |

### Appendix D: Platform Limitations

#### Windows Server

| Limitation | Mitigation |
|------------|------------|
| Docker Desktop licensing | Document requirements |
| GPU passthrough complexity | Use WSL2 + Docker |
| Path length limits | Enable long paths |

**Recommended:** Windows Server 2022 → WSL2 (Ubuntu) → Docker/Podman

#### macOS

| Limitation | Mitigation |
|------------|------------|
| Apple Silicon no NVIDIA | Use llama.cpp or cloud LLM |
| Docker Desktop memory | Configure 16GB+ |
| No production support | Development only |

### Appendix E: Testing Tier Matrix

#### Tier 1: Every PR (Blocking, ~15 min)

| Component | Configuration |
|-----------|---------------|
| Platform | Ubuntu 22.04 |
| Deployment | Podman Compose |
| Graph DB | Neo4j 5 |
| LLM | Mock (no GPU) |

#### Tier 2: Nightly (~2 hours)

- Ubuntu + K8s (k3s + Helm)
- Ubuntu + vLLM (GPU)
- RHEL 9 + Podman
- macOS ARM + Podman

#### Tier 3: Weekly/Release (~8 hours)

- Windows Server 2022 (WSL2)
- JanusGraph, Milvus, MongoDB alternatives
- TGI inference
- Air-gapped simulation

### Appendix F: Query Language Strategy

**Decision: Neo4j Gremlin Plugin (Option A)**

Use Neo4j's APOC Gremlin compatibility layer to maintain single query language:

```python
class Neo4jGremlinAdapter(GraphProvider):
    def __init__(self, uri: str):
        self.graph = Graph().traversal().withRemote(
            DriverRemoteConnection(uri, 'g')
        )
```

**Pros:** Single query language, simpler abstraction, lower risk
**Cons:** 10-15% performance penalty vs native Cypher

### Appendix G: Air-Gap Bundle Contents

```
aura-airgap-{version}.tar.gz
├── images/
│   ├── aura-api-{version}.tar.gz
│   ├── aura-frontend-{version}.tar.gz
│   ├── neo4j-5-enterprise.tar.gz
│   ├── opensearch-2.11.0.tar.gz
│   └── vllm-openai.tar.gz
├── charts/
│   └── aura-{version}.tgz
├── models/
│   ├── mistral-7b-instruct-v0.3/
│   └── SHA256SUMS
├── scripts/
│   ├── load-images.sh
│   ├── install.sh
│   └── verify-checksums.sh
├── docs/
│   ├── INSTALL.md
│   └── TROUBLESHOOTING.md
├── SHA256SUMS
├── SHA256SUMS.sig  # Cosign signature
└── VERSION
```

---

## References

- [Parent ADR-049](../architecture-decisions/ADR-049-self-hosted-deployment-strategy.md)
- [Neo4j Operations Manual](https://neo4j.com/docs/operations-manual/)
- [vLLM Documentation](https://docs.vllm.ai/)
- [Text Generation Inference](https://huggingface.co/docs/text-generation-inference/)
- [GitLab Self-Managed](https://docs.gitlab.com/ee/install/)
- [Replicated KOTS](https://docs.replicated.com/)
