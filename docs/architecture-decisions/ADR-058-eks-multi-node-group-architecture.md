# ADR-058: EKS Multi-Node Group Architecture

| Status | Deployed |
|--------|----------|
| Date | 2026-01-10 |
| Authors | Platform Engineering |
| Reviewers | - |
| Supersedes | - |

## Context

Project Aura's workloads have significantly different resource requirements:

| Workload | Memory | CPU | Special Needs |
|----------|--------|-----|---------------|
| aura-frontend | 128-256Mi | Minimal | None |
| aura-api | 256-512Mi | Light | None |
| dnsmasq | Minimal | Minimal | Host networking |
| agent-orchestrator | 512Mi-1Gi | Moderate | None |
| memory-service | 2-4Gi + 8Gi SHM | Moderate-High | PyTorch, optional GPU |

The current single node group with t3.medium instances (4GB RAM, ~3.3GB allocatable) cannot support memory-service workloads that require 2GB+ memory plus 8GB shared memory for PyTorch operations. Simply scaling up to larger instances for all workloads wastes resources and increases costs.

### Constraints

- **GovCloud Production Target**: Solution must be fully compatible with AWS GovCloud (us-gov-west-1)
- **Karpenter Not Available**: Karpenter is not supported in GovCloud as of January 2026
- **CMMC Compliance**: Must maintain security posture for CMMC Level 2+ certification
- **Cost Efficiency**: QA environment should minimize costs while production prioritizes reliability

## Decision

Implement a **three-node-group architecture** with purpose-built instance types for each workload category:

### Node Group Architecture

```
+-------------------------------------------------------------------------+
|                         EKS Cluster                                      |
+-------------------------------------------------------------------------+
|                                                                          |
|  +---------------------+  +---------------------+  +------------------+  |
|  | general-purpose     |  | memory-optimized    |  | gpu-compute      |  |
|  |                     |  |                     |  | (future)         |  |
|  | t3.large (8GB)      |  | r6i.xlarge (32GB)   |  | g5.xlarge        |  |
|  | Min: 2, Max: 6      |  | Min: 1, Max: 3      |  | Min: 0, Max: 2   |  |
|  |                     |  |                     |  |                  |  |
|  | Workloads:          |  | Workloads:          |  | Workloads:       |  |
|  | - aura-frontend     |  | - memory-service    |  | - memory-service |  |
|  | - aura-api          |  |   (CPU mode)        |  |   (GPU mode)     |  |
|  | - agent-orchestrator|  |                     |  | - future ML      |  |
|  | - dnsmasq           |  |                     |  |                  |  |
|  |                     |  |                     |  |                  |  |
|  | Spot: 70%           |  | On-Demand: 100%     |  | Spot: 100%       |  |
|  | On-Demand: 30%      |  | (stateful)          |  | (scale-to-zero)  |  |
|  +---------------------+  +---------------------+  +------------------+  |
|                                                                          |
+-------------------------------------------------------------------------+
```

### Instance Type Selection

| Node Group | Instance | vCPU | Memory | Rationale |
|------------|----------|------|--------|-----------|
| general-purpose | t3.large | 2 | 8 GiB | Handles 4-5 lightweight pods; burstable for cost efficiency |
| memory-optimized | r6i.xlarge | 4 | 32 GiB | 8:1 memory-to-vCPU ratio for PyTorch; supports 8Gi SHM + overhead |
| gpu-compute | g5.xlarge | 4 | 16 GiB + A10G | Cost-effective GPU for inference; 24GB GPU memory |

### Workload Scheduling

- **Taints**: Memory-optimized and GPU nodes have taints to prevent general workloads from scheduling
- **Tolerations**: memory-service tolerates both memory-optimized and GPU taints
- **Node Affinity**: memory-service has required affinity for memory-optimized or GPU nodes

## Consequences

### Positive

- **Right-sized Resources**: Each workload gets appropriate instance type
- **Cost Optimization**: 70% Spot for stateless workloads saves ~60% on general-purpose nodes
- **GPU-Ready**: Architecture supports future GPU workloads without cluster changes
- **Failure Isolation**: Node group failures don't affect other workload types
- **GovCloud Compatible**: Uses EKS Managed Node Groups with Cluster Autoscaler

### Negative

- **Increased Complexity**: Three CloudFormation templates instead of one
- **Scheduling Configuration**: Workloads need taints/tolerations/affinity
- **Monitoring Overhead**: More node groups to monitor and alert on

### Cost Impact

| Environment | Current (t3.medium x2) | New Architecture | Change |
|-------------|------------------------|------------------|--------|
| QA | ~$120/month | ~$220/month | +83% |
| Production | ~$180/month | ~$370/month (optimized) | +106% |

The cost increase is justified by:
- Ability to run memory-service with full functionality
- GPU readiness for future ML inference workloads
- Production-grade reliability with On-Demand for stateful workloads

## Implementation

### Phase 1: CloudFormation Templates

Create three new templates:
- `deploy/cloudformation/eks-nodegroup-general.yaml`
- `deploy/cloudformation/eks-nodegroup-memory.yaml`
- `deploy/cloudformation/eks-nodegroup-gpu.yaml`

### Phase 2: Buildspec Updates

Update `buildspec-compute.yml` to deploy all node groups:
1. Deploy general-purpose node group
2. Deploy memory-optimized node group
3. Deploy gpu-compute node group (scale-to-zero initially)

### Phase 3: Workload Configuration

Update Kubernetes deployments:
- Add node affinity to memory-service for memory-optimized nodes
- Add tolerations for workload-type taints
- Verify scheduling behavior

### Phase 4: Cluster Autoscaler

Deploy Cluster Autoscaler with ASG-based scaling:
- Configure separate scaling for each node group
- Set appropriate scale-down delays for GPU nodes

## Alternatives Considered

### 1. Single Large Node Group (t3.xlarge)

**Rejected**: Overpaying for lightweight workloads; still insufficient for memory-service SHM requirements.

### 2. Karpenter Dynamic Provisioning

**Rejected**: Not available in GovCloud. Would require commercial AWS only, breaking production deployment target.

### 3. Manual Node Sizing

**Rejected**: Requires manual intervention for scaling; doesn't support GPU workloads without infrastructure changes.

## Related Documents

- ADR-024: Titan Neural Memory Architecture
- ADR-037: AWS Agent Parity
- ADR-049: Self-Hosted Deployment
- `docs/deployment/DEPLOYMENT_GUIDE.md`

## References

- [EKS Managed Node Groups Best Practices](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html)
- [Cluster Autoscaler on AWS](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/cloudprovider/aws/README.md)
- [GovCloud Service Availability](https://aws.amazon.com/govcloud-us/services/)
