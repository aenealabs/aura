# Project Aura - EKS Cost Analysis
## EC2 Instance Type Strategy Comparison

**Date:** 2025-11-17
**Purpose:** Compare different EC2 instance type strategies for Project Aura EKS deployment
**Scope:** Commercial Cloud (dev/qa) and GovCloud (prod) deployment options

---

## Executive Summary

| Strategy | Monthly Cost | Best For | Savings vs Baseline |
|----------|-------------|----------|---------------------|
| **Dev/Testing (Recommended)** | **$652** | Development, QA testing | **-64%** |
| **Production (Recommended)** | **$1,807** | Production workloads, GovCloud | **Baseline** |
| **Production + Spot** | **$1,154** | Cost-optimized production | **-36%** |
| **High Performance** | **$3,614** | High-throughput workloads | **+100%** |

**Recommendation:**
- **Dev/QA (Commercial Cloud):** Dev/Testing Strategy ($652/month)
- **Production (GovCloud):** Production Strategy ($1,807/month)

---

## Cost Analysis Methodology

### Assumptions
- **Region:** us-east-1 (Commercial), us-gov-west-1 (GovCloud)
- **Uptime:** 730 hours/month (24/7 operation)
- **Workload:** 10 concurrent agent workloads, moderate traffic
- **EKS Control Plane:** $0.10/hour ($73/month)
- **EBS Storage:** gp3 volumes with encryption

### Pricing Sources (as of Nov 2025)
- **Commercial Cloud:** Standard AWS pricing
- **GovCloud:** ~5% premium over commercial pricing
- **Spot Instances:** ~70% discount vs On-Demand

---

## Strategy 1: Dev/Testing (Recommended for Commercial Cloud)

**Target Environment:** Development, QA, Staging
**Goal:** Minimize costs while maintaining reasonable performance

### Architecture

```
System Node Group (Cluster Add-ons):
  Instance Type: t3.small (2 vCPU, 2 GB RAM)
  Count: 2 nodes (multi-AZ HA)
  Capacity: On-Demand

Application Node Group (Agent Workloads):
  Instance Type: t3.large (2 vCPU, 8 GB RAM)
  Count: 3 nodes (auto-scaling: 3-10)
  Capacity: Spot (70% discount)

Sandbox Node Group (Test Environments):
  Instance Type: t3.medium (2 vCPU, 4 GB RAM)
  Count: 0-5 nodes (scale to zero when idle)
  Capacity: Spot (70% discount)
```

### Cost Breakdown (Commercial Cloud - us-east-1)

| Component | Spec | Unit Price | Quantity | Hours | Monthly Cost |
|-----------|------|------------|----------|-------|--------------|
| **System Nodes** | t3.small | $0.0208/hr | 2 | 730 | $30.37 |
| **Application Nodes** | t3.large (Spot) | $0.0250/hr | 3 | 730 | $54.75 |
| **Sandbox Nodes** | t3.medium (Spot) | $0.0125/hr | 2 avg | 730 | $18.25 |
| **EKS Control Plane** | - | $0.10/hr | 1 | 730 | $73.00 |
| **EBS Storage (gp3)** | System: 100 GB, App: 300 GB, Sandbox: 160 GB | $0.08/GB | 560 GB | - | $44.80 |
| **Data Transfer** | Intra-VPC (minimal) | - | - | - | $5.00 |
| **CloudWatch Logs** | 10 GB/month | $0.50/GB | 10 GB | - | $5.00 |
| | | | | **TOTAL** | **$231.17** |

**Note:** This assumes average 2 sandbox nodes. When idle (0 nodes), total = **$207.92/month**

### Annual Cost Projection
- **Monthly:** $231.17
- **Annually:** $2,774.04

---

## Strategy 2: Production (Recommended for GovCloud)

**Target Environment:** Production (GovCloud deployment)
**Goal:** Maximize reliability and compliance

### Architecture

```
System Node Group (Cluster Add-ons):
  Instance Type: t3.medium (2 vCPU, 4 GB RAM)
  Count: 3 nodes (multi-AZ HA, N+1 redundancy)
  Capacity: On-Demand

Application Node Group (Agent Workloads):
  Instance Type: m5.xlarge (4 vCPU, 16 GB RAM)
  Count: 5 nodes (auto-scaling: 5-20)
  Capacity: On-Demand

Sandbox Node Group (Test Environments):
  Instance Type: t3.large (2 vCPU, 8 GB RAM)
  Count: 0-10 nodes (scale to zero when idle)
  Capacity: On-Demand (GovCloud Spot availability varies)
```

### Cost Breakdown (GovCloud - us-gov-west-1)

| Component | Spec | Unit Price | Quantity | Hours | Monthly Cost |
|-----------|------|------------|----------|-------|--------------|
| **System Nodes** | t3.medium | $0.0464/hr | 3 | 730 | $101.64 |
| **Application Nodes** | m5.xlarge | $0.215/hr | 5 | 730 | $784.75 |
| **Sandbox Nodes** | t3.large | $0.093/hr | 3 avg | 730 | $203.49 |
| **EKS Control Plane** | - | $0.10/hr | 1 | 730 | $73.00 |
| **EBS Storage (gp3)** | System: 150 GB, App: 500 GB, Sandbox: 240 GB | $0.088/GB | 890 GB | - | $78.32 |
| **Data Transfer** | Intra-VPC | - | - | - | $10.00 |
| **CloudWatch Logs** | 50 GB/month | $0.50/GB | 50 GB | - | $25.00 |
| | | | | **TOTAL** | **$1,276.20** |

**With 3 sandbox nodes average. Idle (0 nodes) = $1,072.71/month**

### Annual Cost Projection
- **Monthly:** $1,276.20
- **Annually:** $15,314.40

### GovCloud Premium
- **Base Cost:** ~$1,200/month
- **GovCloud Premium (5%):** ~$60/month
- **STIG/FIPS Compliance Overhead:** Included in base pricing

---

## Strategy 3: Production + Spot (Cost-Optimized)

**Target Environment:** Production (Commercial Cloud only)
**Goal:** Balance cost and reliability with intelligent Spot usage

### Architecture

```
System Node Group (Cluster Add-ons):
  Instance Type: t3.medium (2 vCPU, 4 GB RAM)
  Count: 3 nodes
  Capacity: On-Demand (critical workloads)

Application Node Group (Agent Workloads):
  Instance Type: m5.xlarge (4 vCPU, 16 GB RAM)
  Count: 5 nodes (auto-scaling: 5-20)
  Capacity: 70% Spot, 30% On-Demand (mixed capacity)

Sandbox Node Group (Test Environments):
  Instance Type: t3.large (2 vCPU, 8 GB RAM)
  Count: 0-10 nodes
  Capacity: Spot (ephemeral workloads)
```

### Cost Breakdown (Commercial Cloud - us-east-1)

| Component | Spec | Unit Price | Quantity | Hours | Monthly Cost |
|-----------|------|------------|----------|-------|--------------|
| **System Nodes** | t3.medium | $0.0416/hr | 3 | 730 | $91.10 |
| **Application Nodes (Spot)** | m5.xlarge (Spot) | $0.061/hr | 3.5 | 730 | $156.69 |
| **Application Nodes (On-Demand)** | m5.xlarge | $0.192/hr | 1.5 | 730 | $210.24 |
| **Sandbox Nodes** | t3.large (Spot) | $0.025/hr | 3 avg | 730 | $54.75 |
| **EKS Control Plane** | - | $0.10/hr | 1 | 730 | $73.00 |
| **EBS Storage (gp3)** | 890 GB | $0.08/GB | 890 GB | - | $71.20 |
| **Data Transfer** | Intra-VPC | - | - | - | $10.00 |
| **CloudWatch Logs** | 40 GB/month | $0.50/GB | 40 GB | - | $20.00 |
| | | | | **TOTAL** | **$686.98** |

### Annual Cost Projection
- **Monthly:** $686.98
- **Annually:** $8,243.76
- **Savings vs On-Demand:** $589.22/month (46% reduction)

---

## Strategy 4: High Performance

**Target Environment:** High-throughput production workloads
**Goal:** Maximum performance for demanding AI/ML workloads

### Architecture

```
System Node Group (Cluster Add-ons):
  Instance Type: m5.large (2 vCPU, 8 GB RAM)
  Count: 3 nodes
  Capacity: On-Demand

Application Node Group (Agent Workloads):
  Instance Type: c5.4xlarge (16 vCPU, 32 GB RAM)
  Count: 5 nodes (auto-scaling: 5-15)
  Capacity: On-Demand

Sandbox Node Group (Test Environments):
  Instance Type: m5.xlarge (4 vCPU, 16 GB RAM)
  Count: 5 nodes
  Capacity: On-Demand
```

### Cost Breakdown (Commercial Cloud - us-east-1)

| Component | Spec | Unit Price | Quantity | Hours | Monthly Cost |
|-----------|------|------------|----------|-------|--------------|
| **System Nodes** | m5.large | $0.096/hr | 3 | 730 | $210.24 |
| **Application Nodes** | c5.4xlarge | $0.68/hr | 5 | 730 | $2,482.00 |
| **Sandbox Nodes** | m5.xlarge | $0.192/hr | 5 | 730 | $700.80 |
| **EKS Control Plane** | - | $0.10/hr | 1 | 730 | $73.00 |
| **EBS Storage (gp3)** | 1,500 GB | $0.08/GB | 1,500 GB | - | $120.00 |
| **Data Transfer** | Intra-VPC | - | - | - | $20.00 |
| **CloudWatch Logs** | 100 GB/month | $0.50/GB | 100 GB | - | $50.00 |
| | | | | **TOTAL** | **$3,656.04** |

### Annual Cost Projection
- **Monthly:** $3,656.04
- **Annually:** $43,872.48

---

## Comparative Analysis

### Total Cost of Ownership (3 Years)

| Strategy | Monthly | Annual | 3-Year TCO |
|----------|---------|--------|------------|
| Dev/Testing | $231 | $2,774 | **$8,322** |
| Production | $1,276 | $15,314 | **$45,943** |
| Production + Spot | $687 | $8,244 | **$24,732** |
| High Performance | $3,656 | $43,872 | **$131,617** |

### Cost per Agent Workload (Monthly)

Assuming 10 concurrent agent workloads:

| Strategy | Total Cost | Cost per Agent |
|----------|-----------|----------------|
| Dev/Testing | $231 | **$23.10** |
| Production | $1,276 | **$127.60** |
| Production + Spot | $687 | **$68.70** |
| High Performance | $3,656 | **$365.60** |

---

## Recommended Deployment Strategy

### Phase 1: Development (Months 1-6)
**Environment:** AWS Commercial Cloud (us-east-1)
**Strategy:** Dev/Testing
**Cost:** $231/month ($1,386 total)

**Rationale:**
- Minimal cost for initial development
- Spot instances acceptable for dev/qa workloads
- Easy to scale up as needed
- No GovCloud compliance requirements

### Phase 2: Production Preparation (Months 7-12)
**Environment:** AWS Commercial Cloud (us-east-1)
**Strategy:** Production + Spot
**Cost:** $687/month ($4,122 total)

**Rationale:**
- Test production-grade workloads
- Validate Spot instance behavior
- Optimize costs before GovCloud migration
- Build runbooks for operational procedures

### Phase 3: GovCloud Migration (Month 13+)
**Environment:** AWS GovCloud (us-gov-west-1)
**Strategy:** Production
**Cost:** $1,276/month

**Rationale:**
- Full compliance (CMMC Level 3, NIST 800-53)
- On-Demand instances for reliability
- STIG/FIPS hardening applied
- Government-approved deployment

---

## Cost Optimization Recommendations

### Immediate Actions (Dev/Testing)

1. **Enable Cluster Autoscaler**
   - Auto-scale application and sandbox node groups to zero during off-hours
   - Potential savings: **$50-100/month**

2. **Use Spot Instances Aggressively**
   - Dev/QA workloads tolerate interruptions
   - Potential savings: **$150-200/month**

3. **Schedule Non-Critical Environments**
   - Stop dev/qa clusters nights and weekends (50% uptime)
   - Potential savings: **$115/month** (50% of compute costs)

### Long-Term Actions (Production)

1. **Reserved Instances / Savings Plans**
   - 1-year commitment: 30-40% savings
   - 3-year commitment: 50-60% savings
   - **Production strategy:** $1,276/month → **$765/month** (3-year Savings Plan)

2. **Graviton2 Instances (ARM-based)**
   - 20% better price/performance vs x86
   - m6g.xlarge vs m5.xlarge: $0.154/hr vs $0.192/hr
   - Potential savings: **$150-200/month**

3. **Right-Sizing**
   - Monitor actual resource usage
   - Downsize over-provisioned nodes
   - Potential savings: **$100-300/month**

---

## Risk Analysis

### Dev/Testing Strategy Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Spot interruptions | Medium | Implement graceful shutdown, use mixed capacity |
| Insufficient capacity | Low | Auto-scale to On-Demand if Spot unavailable |
| Performance degradation | Low | Acceptable for dev/qa environments |

### Production Strategy Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Higher costs | Medium | Use Savings Plans, optimize instance sizes |
| Over-provisioning | Medium | Monitor usage, implement auto-scaling |
| GovCloud migration complexity | High | Test migration in staging first |

### Production + Spot Strategy Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Spot interruptions | High | Use diversified instance types, fallback to On-Demand |
| Stateful workload issues | High | Use On-Demand for stateful agents, Spot for stateless |
| Unpredictable costs | Medium | Set Spot price limits, use mixed capacity |

---

## Action Items

### For Development Team

1. ✅ **Deploy Dev/Testing strategy** to Commercial Cloud (us-east-1)
2. ✅ **Enable Cluster Autoscaler** for cost optimization
3. ✅ **Implement CloudWatch dashboards** to monitor costs
4. ⏳ **Schedule weekend shutdowns** for dev/qa environments
5. ⏳ **Test Spot instance interruption handling** in QA

### For Operations Team

1. ⏳ **Establish CloudWatch cost alerts** ($250, $500, $1000 thresholds)
2. ⏳ **Create runbooks** for node group management
3. ⏳ **Implement automated AMI updates** (weekly schedule)
4. ⏳ **Configure AWS Cost Explorer** reports
5. ⏳ **Plan GovCloud migration** (target: Q2 2026)

### For Leadership

1. ⏳ **Approve Dev/Testing strategy** ($231/month budget)
2. ⏳ **Review quarterly cost reports** and adjust strategy
3. ⏳ **Plan for Production budget** ($1,276/month in GovCloud)
4. ⏳ **Consider Savings Plans** for long-term cost reduction

---

## Appendix: Instance Type Reference

### T3 Family (Burstable Performance)
| Instance Type | vCPU | RAM | On-Demand (us-east-1) | Spot (70% off) | Best For |
|---------------|------|-----|----------------------|----------------|----------|
| t3.small | 2 | 2 GB | $0.0208/hr | $0.0062/hr | Dev, small workloads |
| t3.medium | 2 | 4 GB | $0.0416/hr | $0.0125/hr | Dev, moderate workloads |
| t3.large | 2 | 8 GB | $0.0832/hr | $0.0250/hr | Dev/QA, agent workloads |
| t3.xlarge | 4 | 16 GB | $0.1664/hr | $0.0499/hr | QA, larger workloads |
| t3.2xlarge | 8 | 32 GB | $0.3328/hr | $0.0998/hr | Large dev environments |

### M5 Family (General Purpose)
| Instance Type | vCPU | RAM | On-Demand (us-east-1) | Spot (70% off) | Best For |
|---------------|------|-----|----------------------|----------------|----------|
| m5.large | 2 | 8 GB | $0.096/hr | $0.029/hr | Balanced workloads |
| m5.xlarge | 4 | 16 GB | $0.192/hr | $0.058/hr | **Production agents** |
| m5.2xlarge | 8 | 32 GB | $0.384/hr | $0.115/hr | High-memory workloads |
| m5.4xlarge | 16 | 64 GB | $0.768/hr | $0.230/hr | Very large workloads |

### C5 Family (Compute Optimized)
| Instance Type | vCPU | RAM | On-Demand (us-east-1) | Spot (70% off) | Best For |
|---------------|------|-----|----------------------|----------------|----------|
| c5.large | 2 | 4 GB | $0.085/hr | $0.026/hr | CPU-intensive |
| c5.xlarge | 4 | 8 GB | $0.170/hr | $0.051/hr | High CPU workloads |
| c5.2xlarge | 8 | 16 GB | $0.340/hr | $0.102/hr | Very high CPU |
| c5.4xlarge | 16 | 32 GB | $0.680/hr | $0.204/hr | Extreme CPU |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-17 | AWS Solutions Architect | Initial cost analysis |

---

**Next Review Date:** 2026-02-17 (Quarterly review)
