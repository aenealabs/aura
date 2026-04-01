# Architecture Decision Record: VPC Connectivity Strategy

**Project Aura - Autonomous AI SaaS Platform**
**Decision Date:** November 17, 2025
**Status:** ✅ **RECOMMENDED - VPC Endpoints (Hybrid Approach)**

---

## Context

Project Aura requires private connectivity from application subnets to AWS services (Bedrock, Neptune, OpenSearch, S3, DynamoDB). We need to choose between:

1. **NAT Gateways** - Provide general internet access (including AWS services)
2. **VPC Endpoints** - Private connectivity to specific AWS services
3. **Hybrid Approach** - Combination of both

This decision impacts:
- Monthly infrastructure costs ($66-$200/month difference)
- Security posture (data never leaves AWS network with VPC endpoints)
- GovCloud migration readiness
- Operational complexity

---

## Decision

**✅ RECOMMENDED: Hybrid VPC Endpoint Strategy**

**Commercial Cloud (Dev/QA):**
- Use **VPC Endpoints** for all AWS services (Bedrock, Neptune, OpenSearch, S3, DynamoDB)
- **NO NAT Gateways** (delete existing NAT Gateways to save $66/month)
- Add NAT Gateway only if internet access to non-AWS services is required

**GovCloud (Production):**
- Use **VPC Endpoints** exclusively (mandatory for CMMC Level 3 compliance)
- Zero internet egress from private subnets
- All traffic stays within AWS network

---

## Service-Specific VPC Endpoint Availability

### ✅ Available in Both Commercial & GovCloud

| Service | Endpoint Type | Commercial | GovCloud | Monthly Cost (per AZ) |
|---------|---------------|------------|----------|----------------------|
| **Amazon Bedrock** | Interface | ✅ Yes | ✅ Yes* | $7.30 + $0.01/GB |
| **Amazon OpenSearch** | Interface | ✅ Yes | ✅ Yes (Mar 2025) | $7.30 + $0.01/GB |
| **Amazon S3** | Gateway | ✅ Yes | ✅ Yes | **FREE** |
| **Amazon DynamoDB** | Gateway | ✅ Yes | ✅ Yes | **FREE** |

*Note: Bedrock VPC endpoints are available in GovCloud via AWS PrivateLink (FedRAMP High authorized)

### ⚠️ Neptune Connectivity (Special Case)

**Neptune does NOT have VPC Endpoints** - Neptune clusters are **already VPC-native**:
- Neptune is deployed directly inside your VPC (private subnets)
- No NAT Gateway or VPC Endpoint needed
- Access via internal DNS: `neptune.aura.local:8182`

**Result:** Neptune is already private by design ✅

---

## Cost Analysis

### Current Setup (2 NAT Gateways - Multi-AZ)

| Component | Hourly Cost | Monthly Cost (730 hrs) | Annual Cost |
|-----------|-------------|------------------------|-------------|
| NAT Gateway 1 | $0.045 | $32.85 | $394.20 |
| NAT Gateway 2 | $0.045 | $32.85 | $394.20 |
| Data Processing | $0.045/GB | Variable (~$20-100/month) | Variable |
| **Total** | | **~$86-166/month** | **~$1,032-1,992/year** |

### Recommended Setup (VPC Endpoints)

| Service | Endpoint Type | Monthly Cost (1 AZ) | Monthly Cost (2 AZs) |
|---------|---------------|---------------------|----------------------|
| **S3** | Gateway | **$0** | **$0** |
| **DynamoDB** | Gateway | **$0** | **$0** |
| **Bedrock** | Interface | $7.30 + $0.01/GB | $14.60 + $0.01/GB |
| **OpenSearch** | Interface | $7.30 + $0.01/GB | $14.60 + $0.01/GB |
| **Neptune** | N/A (VPC-native) | **$0** | **$0** |
| **Total (fixed)** | | **$14.60** | **$29.20** |
| **Total (with data)** | | **~$20-30/month** | **~$35-50/month** |

### **Cost Savings**

| Metric | NAT Gateway | VPC Endpoints | Savings |
|--------|-------------|---------------|---------|
| **Monthly (Dev)** | $86-166 | $35-50 | **$36-116 (42-70%)** |
| **Annual (Dev)** | $1,032-1,992 | $420-600 | **$612-1,392** |
| **Monthly (Prod - 3 AZs)** | $130-250 | $50-75 | **$80-175 (62%)** |

**Development Environment Savings:** ~$50-100/month
**Production Environment Savings:** ~$100-175/month

---

## Security & Compliance Comparison

### NAT Gateway Security Profile

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Data Path** | ⚠️ Medium | Traffic exits VPC to internet, then back to AWS |
| **Logging** | ✅ Good | VPC Flow Logs capture traffic |
| **Attack Surface** | ⚠️ Higher | Internet egress point (potential data exfiltration) |
| **CMMC Level 3** | ❌ **NOT COMPLIANT** | Data crosses internet boundary |
| **SOX Compliance** | ⚠️ Requires justification | Audit trail needed for internet egress |
| **NIST 800-53** | ⚠️ Partial | AC-4 (Information Flow), SC-7 (Boundary Protection) concerns |

### VPC Endpoint Security Profile

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Data Path** | ✅ Excellent | Traffic **never leaves AWS network** |
| **Logging** | ✅ Excellent | VPC Flow Logs + CloudTrail API logs |
| **Attack Surface** | ✅ Minimal | No internet egress, private IP only |
| **CMMC Level 3** | ✅ **COMPLIANT** | Data stays within AWS network (SC.3.177, SC.3.191) |
| **SOX Compliance** | ✅ **COMPLIANT** | No internet egress reduces audit complexity |
| **NIST 800-53** | ✅ **COMPLIANT** | Meets AC-4, SC-7, SC-8 (encryption in transit) |
| **FedRAMP High** | ✅ **COMPLIANT** | AWS PrivateLink is FedRAMP authorized |

**Verdict:** VPC Endpoints are **mandatory** for CMMC Level 3 and **strongly recommended** for SOX/NIST compliance.

---

## Performance Comparison

### Latency

| Metric | NAT Gateway | VPC Endpoint | Winner |
|--------|-------------|--------------|--------|
| **Hops** | VPC → NAT → Internet → AWS Service | VPC → AWS Service (direct) | ✅ VPC Endpoint |
| **Typical Latency** | 5-15ms (additional) | 1-3ms | ✅ VPC Endpoint |
| **Consistency** | Variable (internet routing) | Consistent (private network) | ✅ VPC Endpoint |

### Throughput

| Metric | NAT Gateway | VPC Endpoint | Notes |
|--------|-------------|--------------|-------|
| **Bandwidth** | Up to 100 Gbps (bursts) | Up to 100 Gbps | ✅ Equivalent |
| **Sustained** | 45 Gbps per NAT Gateway | 100 Gbps (AWS backbone) | ✅ VPC Endpoint |

**Verdict:** VPC Endpoints provide **lower latency** and **more consistent performance**.

---

## Operational Complexity

### NAT Gateway Management

**Setup Complexity:** ⚠️ Medium
- Deploy 2 NAT Gateways (multi-AZ HA)
- Configure route tables (public subnets)
- Attach Elastic IPs

**Ongoing Maintenance:** ⚠️ Medium
- Monitor NAT Gateway health
- Replace failed NAT Gateways (rare)
- Manage Elastic IP allocations

**Deletion/Re-creation:** ⚠️ Complex
- Requires route table updates
- Risk of breaking connectivity

### VPC Endpoint Management

**Setup Complexity:** ✅ Low
- Create endpoint per service (1 command each)
- Auto-configures route tables (for Interface Endpoints)
- No public IPs needed

**Ongoing Maintenance:** ✅ Low
- Endpoints are managed by AWS
- Auto-scaling, auto-healing
- No health monitoring needed

**Deletion/Re-creation:** ✅ Simple
- Delete endpoint (1 command)
- No route table changes

**Verdict:** VPC Endpoints are **significantly simpler** to manage.

---

## Recommended Architecture

### Commercial Cloud (Dev/QA)

```
┌─────────────────────────────────────────────────────────┐
│                    VPC (10.0.0.0/16)                    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │         Private Subnets (10.0.1.0/24, etc)      │   │
│  │                                                 │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐     │   │
│  │  │   EKS    │  │  Agents  │  │  Lambda  │     │   │
│  │  │  Pods    │  │ (Fargate)│  │Functions │     │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘     │   │
│  │       │             │             │           │   │
│  └───────┼─────────────┼─────────────┼───────────┘   │
│          │             │             │               │
│          ▼             ▼             ▼               │
│  ┌─────────────────────────────────────────────────┐ │
│  │          VPC Endpoints (PrivateLink)            │ │
│  │                                                 │ │
│  │  • Bedrock Interface Endpoint                  │ │
│  │  • OpenSearch Interface Endpoint               │ │
│  │  • S3 Gateway Endpoint (FREE)                  │ │
│  │  • DynamoDB Gateway Endpoint (FREE)            │ │
│  │                                                 │ │
│  └───────────────────┬─────────────────────────────┘ │
│                      │                               │
└──────────────────────┼───────────────────────────────┘
                       │
                       ▼
              ┌────────────────────┐
              │   AWS Services     │
              │  (Private Network) │
              │                    │
              │  • Bedrock API     │
              │  • OpenSearch      │
              │  • S3 Buckets      │
              │  • DynamoDB        │
              └────────────────────┘

┌─────────────────────────────────────────────────────────┐
│         Neptune (Already VPC-Native)                    │
│                                                         │
│  Private Subnets → Neptune Cluster (10.0.1.X:8182)     │
│  No NAT/Endpoint needed                                │
└─────────────────────────────────────────────────────────┘

✅ Cost: ~$35-50/month (vs $86-166 with NAT)
✅ Security: Data never leaves AWS network
✅ Latency: 5-10ms faster
```

### GovCloud (Production)

**Same architecture as Commercial Cloud** with additional requirements:
- ✅ All endpoints use AWS PrivateLink (FedRAMP High)
- ✅ Zero internet egress (mandatory for CMMC Level 3)
- ✅ Enhanced logging (CloudTrail + VPC Flow Logs to S3 with encryption)
- ✅ Deploy across 3 AZs (high availability)

**Cost (3 AZs):** ~$50-75/month (vs $130-250 with NAT Gateways)

---

## Migration Plan

### Phase 1: Create VPC Endpoints (Dev Environment)

**Week 1: Deploy VPC Endpoints**

```bash
# Set environment variables (use your configured profile with AdministratorAccess)
export AWS_PROFILE=<your-aws-profile>
export AWS_REGION=us-east-1
export VPC_ID=vpc-0123456789abcdef0
export SUBNET_IDS="subnet-0aaaa00000aaaa0003,subnet-0aaaa00000aaaa0004"
export SG_ID=sg-XXXXX  # Use existing security group or create new

# 1. Create S3 Gateway Endpoint (FREE)
aws ec2 create-vpc-endpoint \
  --vpc-id $VPC_ID \
  --service-name com.amazonaws.us-east-1.s3 \
  --route-table-ids rtb-XXXXX \
  --vpc-endpoint-type Gateway \
  --tag-specifications 'ResourceType=vpc-endpoint,Tags=[{Key=Name,Value=aura-s3-endpoint},{Key=Project,Value=aura}]'

# 2. Create DynamoDB Gateway Endpoint (FREE)
aws ec2 create-vpc-endpoint \
  --vpc-id $VPC_ID \
  --service-name com.amazonaws.us-east-1.dynamodb \
  --route-table-ids rtb-XXXXX \
  --vpc-endpoint-type Gateway \
  --tag-specifications 'ResourceType=vpc-endpoint,Tags=[{Key=Name,Value=aura-dynamodb-endpoint},{Key=Project,Value=aura}]'

# 3. Create Bedrock Interface Endpoint
aws ec2 create-vpc-endpoint \
  --vpc-id $VPC_ID \
  --service-name com.amazonaws.us-east-1.bedrock-runtime \
  --vpc-endpoint-type Interface \
  --subnet-ids $SUBNET_IDS \
  --security-group-ids $SG_ID \
  --private-dns-enabled \
  --tag-specifications 'ResourceType=vpc-endpoint,Tags=[{Key=Name,Value=aura-bedrock-endpoint},{Key=Project,Value=aura}]'

# 4. Create OpenSearch Interface Endpoint
aws ec2 create-vpc-endpoint \
  --vpc-id $VPC_ID \
  --service-name com.amazonaws.us-east-1.es \
  --vpc-endpoint-type Interface \
  --subnet-ids $SUBNET_IDS \
  --security-group-ids $SG_ID \
  --private-dns-enabled \
  --tag-specifications 'ResourceType=vpc-endpoint,Tags=[{Key=Name,Value=aura-opensearch-endpoint},{Key=Project,Value=aura}]'

# 5. Verify endpoints are available
aws ec2 describe-vpc-endpoints \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'VpcEndpoints[*].[VpcEndpointId,ServiceName,State]' \
  --output table
```

**Expected Output:**
```
-----------------------------------------------------------------
|                      DescribeVpcEndpoints                     |
+----------------------+-----------------------------------+------+
| vpce-XXXXX          | com.amazonaws.us-east-1.s3        | available |
| vpce-YYYYY          | com.amazonaws.us-east-1.dynamodb  | available |
| vpce-ZZZZZ          | com.amazonaws.us-east-1.bedrock-runtime | available |
| vpce-AAAAA          | com.amazonaws.us-east-1.es        | available |
+----------------------+-----------------------------------+------+
```

### Phase 2: Test Connectivity

```bash
# Test from EC2 instance or Lambda in private subnet

# Test Bedrock connectivity
aws bedrock-runtime list-foundation-models \
  --region us-east-1 \
  --endpoint-url https://bedrock-runtime.us-east-1.amazonaws.com

# Test S3 connectivity
aws s3 ls s3://your-bucket-name

# Test DynamoDB connectivity
aws dynamodb list-tables --region us-east-1
```

### Phase 3: Delete NAT Gateways (After Validation)

**⚠️ IMPORTANT:** Only delete NAT Gateways AFTER confirming all services work via VPC endpoints

```bash
# 1. Identify NAT Gateway IDs
aws ec2 describe-nat-gateways \
  --filter "Name=vpc-id,Values=$VPC_ID" \
  --query 'NatGateways[*].[NatGatewayId,State,SubnetId]' \
  --output table

# 2. Delete NAT Gateways
aws ec2 delete-nat-gateway --nat-gateway-id nat-0example000000001
aws ec2 delete-nat-gateway --nat-gateway-id nat-0example000000002

# 3. Wait for deletion (can take 5-10 minutes)
aws ec2 describe-nat-gateways \
  --nat-gateway-ids nat-0example000000001 nat-0example000000002 \
  --query 'NatGateways[*].State'

# 4. Release Elastic IPs (after NAT Gateways are deleted)
aws ec2 describe-addresses \
  --filters "Name=domain,Values=vpc" \
  --query 'Addresses[?AssociationId==null].[AllocationId,PublicIp]' \
  --output table

aws ec2 release-address --allocation-id eipalloc-XXXXX
aws ec2 release-address --allocation-id eipalloc-YYYYY
```

**Cost Savings (immediate):** ~$66/month ($792/year)

---

## Rollback Plan

If VPC Endpoints don't work as expected:

```bash
# Recreate NAT Gateways (takes ~5 minutes)
aws ec2 create-nat-gateway \
  --subnet-id subnet-0aaaa00000aaaa0005 \
  --allocation-id eipalloc-XXXXX \
  --tag-specifications 'ResourceType=nat-gateway,Tags=[{Key=Name,Value=aura-nat-gw-1}]'

aws ec2 create-nat-gateway \
  --subnet-id subnet-0aaaa00000aaaa0006 \
  --allocation-id eipalloc-YYYYY \
  --tag-specifications 'ResourceType=nat-gateway,Tags=[{Key=Name,Value=aura-nat-gw-2}]'

# Update route tables to point back to NAT Gateways
aws ec2 create-route \
  --route-table-id rtb-XXXXX \
  --destination-cidr-block 0.0.0.0/0 \
  --nat-gateway-id nat-XXXXX
```

---

## Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **VPC Endpoint service outage** | Very Low | High | Multi-AZ deployment, AWS SLA 99.99% |
| **Endpoint configuration error** | Low | Medium | Test in dev before prod, rollback plan |
| **Need internet access later** | Low | Low | Can add NAT Gateway on-demand |
| **Cost exceeds estimate** | Very Low | Low | Gateway endpoints are free, Interface endpoints have fixed cost |

---

## Decision Summary

### ✅ **APPROVED: VPC Endpoints (Hybrid Approach)**

**Rationale:**
1. **Cost Savings:** $50-100/month in dev, $100-175/month in prod
2. **Security:** Mandatory for CMMC Level 3, improves SOX/NIST compliance
3. **Performance:** Lower latency (5-10ms improvement)
4. **GovCloud Ready:** Same architecture works in both commercial & GovCloud
5. **Operational Simplicity:** Less to manage, auto-healing

### 🔧 **Implementation:**

**Immediate (Dev/QA - Commercial Cloud):**
- [ ] Deploy VPC Endpoints for Bedrock, OpenSearch, S3, DynamoDB
- [ ] Test connectivity from private subnets
- [ ] Delete NAT Gateways (saves $66/month)

**Future (Production - GovCloud):**
- [ ] Same architecture as dev
- [ ] Deploy across 3 AZs for high availability
- [ ] Enable enhanced logging (CloudTrail + VPC Flow Logs)

### 📊 **Success Metrics:**

- [ ] Monthly infrastructure cost reduced by $50-100 (dev)
- [ ] All services accessible from private subnets via VPC endpoints
- [ ] CMMC Level 3 compliance requirement met (no internet egress)
- [ ] Latency to AWS services improved by 5-10ms

---

**Status:** ✅ **Ready for Implementation**
**Next Action:** Deploy VPC Endpoints to dev environment following migration plan

---

*Architecture Decision Record created on November 17, 2025*
*Project Aura - Autonomous AI SaaS Platform*
