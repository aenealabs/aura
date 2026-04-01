# ADR-006: Three-Tier dnsmasq Integration for Service Discovery

**Status:** Deployed
**Date:** 2025-11-12
**Decision Makers:** Project Aura Team

## Context

Project Aura requires DNS-based service discovery for its microservices architecture:
- Agent services need to resolve endpoints like `neptune.aura.local`, `opensearch.aura.local`
- Sandbox environments need isolated DNS for testing
- VPC-wide services need centralized DNS with filtering

Options for service discovery:
1. **AWS Route 53 Resolver** - AWS-managed private DNS
2. **Kubernetes CoreDNS** - Default K8s DNS, cluster-scoped only
3. **dnsmasq** - Lightweight DNS/DHCP with extensive configurability
4. **Consul** - HashiCorp service mesh with built-in DNS

This decision impacts:
- Service endpoint resolution latency
- Network isolation for sandbox testing
- HITL workflow enablement
- Operational complexity and costs

## Decision

We chose a **Three-Tier dnsmasq Integration** architecture:

**Tier 1: EKS Service Discovery (DaemonSet)**
- Runs on every EKS EC2 node
- Local DNS caching for microservices
- Custom `.aura.local` domain resolution
- Integration with Kubernetes CoreDNS

**Tier 2: VPC Network Services (ECS Fargate)**
- Centralized DNS for entire VPC
- Conditional forwarding (AWS services, K8s, custom)
- DNS security filtering
- High availability via Network Load Balancer

**Tier 3: Sandbox Network Services (Ephemeral)**
- Isolated DNS/DHCP per sandbox instance
- Part of HITL V2.0 workflow
- Network-dependent integration testing
- Python orchestrator for lifecycle management

## Alternatives Considered

### Alternative 1: AWS Route 53 Resolver Only

Use Route 53 Private Hosted Zones for all service discovery.

**Pros:**
- AWS-managed, no infrastructure to maintain
- Integrated with VPC
- Simple DNS management via console/API

**Cons:**
- No local caching per node (higher latency)
- $0.40/month per hosted zone + query charges
- Cannot create ephemeral isolated DNS for sandboxes
- Limited filtering/security capabilities

### Alternative 2: Kubernetes CoreDNS Only

Rely on default CoreDNS for all service discovery.

**Pros:**
- Already deployed with EKS
- Standard K8s approach
- Supports custom domains via ConfigMap

**Cons:**
- Cluster-scoped only (not VPC-wide)
- No support for non-K8s services (EC2, Lambda)
- Cannot provide isolated DNS for sandboxes
- No DNSSEC validation

### Alternative 3: Consul Service Mesh

Deploy HashiCorp Consul for service discovery and mesh.

**Pros:**
- Rich service discovery features
- Health checking built-in
- Service mesh capabilities

**Cons:**
- Significant operational overhead
- Overkill for DNS-only requirements
- Complex debugging
- Higher resource footprint

### Alternative 4: dnsmasq (Single Tier)

Single dnsmasq deployment for all use cases.

**Pros:**
- Simpler architecture
- Fewer components to manage

**Cons:**
- Cannot scale independently per tier
- Sandbox isolation more complex
- Single point of failure

## Consequences

### Positive

1. **Performance**
   - 70-90% reduction in DNS query latency (local caching)
   - 5x cache capacity over CoreDNS defaults
   - Consistent sub-millisecond resolution for cached entries

2. **Flexibility**
   - Three tiers scale independently
   - Each tier optimized for its use case
   - Easy to disable tiers not needed

3. **Security**
   - DNSSEC validation prevents DNS spoofing
   - DNS-based malware filtering
   - Network isolation per sandbox
   - CMMC Level 3 compliance for DNS security

4. **HITL Enablement**
   - Tier 3 enables isolated sandbox testing
   - Mock DNS entries for testing scenarios
   - Ephemeral environments with custom DNS

5. **Cost Efficiency**
   - Reduced Route 53 query costs
   - Fargate Spot for Tier 2 (cost optimization)
   - Auto-teardown for Tier 3 sandboxes

6. **GovCloud Compatibility**
   - Tier 1: Runs on EKS EC2 nodes (compatible)
   - Tier 2: ECS Fargate (available in GovCloud)
   - Tier 3: Python service on EKS (compatible)

### Negative

1. **Operational Complexity**
   - Three tiers to manage and monitor
   - Custom configuration management
   - Additional CloudWatch dashboards needed

2. **Learning Curve**
   - Team must understand dnsmasq configuration
   - Debugging DNS issues requires expertise

3. **Build Dependency**
   - Rust dnsmasq binary must be built from source
   - Docker image must be maintained

### Mitigation

- Comprehensive documentation in `docs/integrations/DNSMASQ_INTEGRATION.md`
- Pre-built Docker images in ECR
- CloudWatch alarms for DNS service health
- Fallback to CoreDNS/VPC DNS if dnsmasq fails

## Service Discovery Endpoints

| Service | DNS Name | Purpose |
|---------|----------|---------|
| Neptune (Primary) | `neptune.aura.local` | Graph database writer |
| Neptune (Reader) | `neptune-reader.aura.local` | Graph database reader |
| OpenSearch | `opensearch.aura.local` | Vector search |
| Context Retrieval | `context-retrieval.aura.local` | RAG fusion service |
| Orchestrator | `orchestrator.aura.local` | Agent orchestrator |
| API Gateway | `api.aura.local` | REST API |

## Deployment Summary

| Tier | Deployment | GovCloud | Purpose |
|------|------------|----------|---------|
| Tier 1 | K8s DaemonSet | ✅ EKS EC2 | Local DNS cache per node |
| Tier 2 | ECS Fargate | ✅ ECS Fargate | VPC-wide DNS service |
| Tier 3 | Python service | ✅ EKS EC2 | Sandbox DNS orchestration |

## References

- `docs/integrations/DNSMASQ_INTEGRATION.md` - Complete technical guide (1,100 lines)
- `DNSMASQ_QUICK_START.md` - 5-minute deployment guide
- `deploy/kubernetes/dnsmasq-daemonset.yaml` - Tier 1 DaemonSet manifest
- `deploy/cloudformation/network-services.yaml` - Tier 2 Fargate template
- `src/services/sandbox_network_service.py` - Tier 3 Python orchestrator
