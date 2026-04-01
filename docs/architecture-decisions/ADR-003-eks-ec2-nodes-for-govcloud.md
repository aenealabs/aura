# ADR-003: EKS EC2 Managed Node Groups for GovCloud Compatibility

**Status:** Deployed
**Date:** 2025-11-17
**Decision Makers:** Project Aura Team

## Context

Project Aura requires Kubernetes orchestration for its multi-agent AI workloads. AWS offers two compute options for EKS:

1. **EKS on Fargate** - Serverless, AWS-managed compute
2. **EKS on EC2 Managed Node Groups** - Self-managed EC2 instances with AWS lifecycle management

**Critical Constraint:** AWS GovCloud does NOT support EKS on Fargate. While ECS on Fargate is available in GovCloud, EKS on Fargate is not.

This decision impacts:
- GovCloud migration feasibility
- Operational model (serverless vs. node management)
- Cost optimization strategies (Spot instances, Savings Plans)
- Compliance capabilities (STIG/FIPS hardening)

## Decision

We chose **EC2 Managed Node Groups for all Kubernetes workloads** with a multi-tier node group architecture:

```
┌─────────────────────────────────────────────────────────────┐
│ System Node Group (Cluster-Critical Infrastructure)        │
├─────────────────────────────────────────────────────────────┤
│ Instance Type:  t3.medium (dev) / t3.medium (prod)         │
│ Count:          2-3 nodes (multi-AZ HA)                     │
│ Capacity:       On-Demand (always)                          │
│ Purpose:        CoreDNS, dnsmasq DaemonSet, monitoring      │
│ Taints:         node-group=system:NoSchedule                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Application Node Group (Agent Workloads)                    │
├─────────────────────────────────────────────────────────────┤
│ Instance Type:  t3.large (dev) / m5.xlarge (prod)          │
│ Count:          3-20 nodes (auto-scaling)                   │
│ Capacity:       Spot (dev) / On-Demand (prod)              │
│ Purpose:        Orchestrator, Coder, Reviewer, Validator    │
│ Labels:         workload-type=agent-workloads               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Sandbox Node Group (Ephemeral Test Environments)           │
├─────────────────────────────────────────────────────────────┤
│ Instance Type:  t3.medium (dev) / t3.large (prod)          │
│ Count:          0-10 nodes (scale to zero when idle)       │
│ Capacity:       Spot (dev) / On-Demand (prod)              │
│ Purpose:        Isolated patch testing sandboxes            │
│ Taints:         node-group=sandbox:NoSchedule               │
└─────────────────────────────────────────────────────────────┘
```

## Alternatives Considered

### Alternative 1: EKS on Fargate (Commercial Cloud Only)

Use Fargate for Commercial Cloud and maintain separate architecture for GovCloud.

**Pros:**
- Serverless (no node management in Commercial Cloud)
- Per-pod billing (potentially cheaper for variable workloads)

**Cons:**
- **NOT available in GovCloud** (breaking constraint)
- Requires maintaining two different architectures
- Migration complexity when moving to GovCloud
- No support for DaemonSets (required for dnsmasq Tier 1)

### Alternative 2: ECS Instead of EKS

Replace Kubernetes with ECS (which supports Fargate in GovCloud).

**Pros:**
- Simpler architecture
- Fargate available in GovCloud for ECS

**Cons:**
- Loses Kubernetes ecosystem (Helm, operators, service mesh)
- Less portable to other clouds
- Team already has Kubernetes expertise
- Many existing tools expect K8s APIs

### Alternative 3: Self-Managed Kubernetes (kops/kubeadm)

Deploy Kubernetes manually on EC2 instances.

**Pros:**
- Complete control over cluster configuration
- No EKS control plane costs ($73/month)

**Cons:**
- Significant operational overhead
- Security patching responsibility shifts to team
- No AWS-managed integrations (OIDC, VPC CNI)
- Not recommended for CMMC compliance

## Consequences

### Positive

1. **GovCloud Compatibility**
   - Same architecture works in both Commercial and GovCloud
   - No migration complexity for compute layer
   - Tested in Commercial before GovCloud deployment

2. **Cost Optimization**
   - Spot instances in dev (70% savings: ~$54/month for 3 t3.large)
   - Savings Plans available for prod (40-50% savings)
   - Scale-to-zero for sandbox nodes (pay only when testing)

3. **Operational Control**
   - Full access to node configuration
   - Custom AMI support for STIG/FIPS hardening
   - SSH/SSM access for debugging (dev only)

4. **Compliance Enablement**
   - DISA STIG hardening in user-data scripts
   - FIPS 140-2 mode for GovCloud
   - IMDSv2 enforcement
   - Bottlerocket OS option for CMMC Level 3

5. **DaemonSet Support**
   - Required for dnsmasq Tier 1 (local DNS caching per node)
   - Fargate does not support DaemonSets

### Negative

1. **Node Management**
   - Must manage AMI updates (automated via script)
   - Capacity planning required
   - Node health monitoring needed

2. **Higher Base Cost**
   - System nodes always running (~$30/month dev)
   - Minimum 2 nodes for HA

3. **Patching Responsibility**
   - Weekly AMI update automation required
   - Security patches must be applied proactively

### Mitigation

- AMI update script: `deploy/scripts/update-eks-node-ami.sh` (weekly automation)
- Security hardening script: `deploy/scripts/harden-eks-nodes.sh` (commercial vs govcloud modes)
- Auto-scaling configured for application and sandbox nodes
- CloudWatch monitoring for node health

## Cost Analysis

### Development/QA (AWS Commercial Cloud)

| Component | Configuration | Monthly Cost |
|-----------|--------------|--------------|
| System Nodes | 2× t3.small (On-Demand) | $30.37 |
| Application Nodes | 3× t3.large (Spot 70% off) | $54.75 |
| Sandbox Nodes | 2× t3.medium (Spot, avg usage) | $18.25 |
| EKS Control Plane | Standard | $73.00 |
| **TOTAL** | | **$176.37/month** |

### Production (AWS GovCloud)

| Component | Configuration | Monthly Cost |
|-----------|--------------|--------------|
| System Nodes | 3× t3.medium (On-Demand) | $101.64 |
| Application Nodes | 5× m5.xlarge (On-Demand) | $784.75 |
| Sandbox Nodes | 3× t3.large (On-Demand, avg) | $203.49 |
| EKS Control Plane | Standard | $73.00 |
| **TOTAL** | | **$1,162.88/month** |

**With 3-Year Savings Plan:** ~$700/month (40% savings)

## References

- `docs/cloud-strategy/GOVCLOUD_MIGRATION_SUMMARY.md` - Full migration planning and timeline
- `deploy/cloudformation/eks.yaml` - EKS cluster and node group definitions
- `deploy/scripts/update-eks-node-ami.sh` - Automated AMI update script
- `deploy/scripts/harden-eks-nodes.sh` - Security hardening (commercial/govcloud)
