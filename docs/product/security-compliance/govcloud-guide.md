# AWS GovCloud Deployment Guide

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This guide provides comprehensive information for deploying Project Aura in AWS GovCloud regions. GovCloud deployment enables organizations to process Controlled Unclassified Information (CUI), meet FedRAMP requirements, and support Impact Level 4/5 (IL4/IL5) workloads.

Project Aura is designed with GovCloud compatibility from the ground up, with 100% of core services validated for GovCloud deployment (19/19 services).

---

## What is AWS GovCloud?

AWS GovCloud (US) is an isolated AWS region designed to host sensitive data and regulated workloads in the cloud. GovCloud enables U.S. government agencies and contractors to meet compliance requirements for FedRAMP High, CMMC, ITAR, and DoD IL4/IL5.

### Key Characteristics

| Feature | GovCloud | Commercial AWS |
|---------|----------|----------------|
| **Physical Isolation** | Dedicated infrastructure | Shared infrastructure |
| **Personnel** | U.S. persons only | Global workforce |
| **Data Residency** | U.S. only | Regional choice |
| **Compliance** | FedRAMP High, IL5 | Variable by region |
| **Account Type** | Separate partition | Standard partition |
| **ARN Format** | `arn:aws-us-gov:...` | `arn:aws:...` |

### GovCloud Regions

| Region | Location | Use Case |
|--------|----------|----------|
| **us-gov-west-1** | Oregon | Primary production |
| **us-gov-east-1** | Virginia | Disaster recovery |

---

## GovCloud Benefits

### Compliance Enablement

GovCloud deployment enables compliance with:

| Framework | Requirement | GovCloud Support |
|-----------|-------------|------------------|
| **FedRAMP High** | High-impact data processing | Native support |
| **CMMC Level 2/3** | CUI protection | Required for CUI |
| **ITAR** | Defense articles | Export control compliance |
| **DoD IL4** | CUI in DoD systems | Authorized |
| **DoD IL5** | Unclassified national security | Authorized |
| **CJIS** | Criminal justice data | Supported |
| **IRS 1075** | Federal tax information | Supported |

### Security Enhancements

| Control | Commercial AWS | GovCloud |
|---------|----------------|----------|
| Personnel screening | Standard background | U.S. persons, enhanced screening |
| Physical access | Standard data centers | FedRAMP High certified facilities |
| Network isolation | Shared backbone | Isolated network partition |
| Data residency | Region-based | Guaranteed U.S. only |
| Audit authority | AWS compliance | Government audit rights |

---

## Service Availability

### Aura Service Compatibility

Project Aura has validated all core services for GovCloud deployment.

| Service | Commercial | GovCloud | Migration Impact |
|---------|------------|----------|------------------|
| **EKS** | Available | Available | None |
| **EC2** | Available | Available | None |
| **Fargate** | Available | Available | None |
| **Lambda** | Available | Available | None |
| **Neptune (Provisioned)** | Available | Available | None |
| **OpenSearch** | Available | Available | None |
| **DynamoDB** | Available | Available | None |
| **S3** | Available | Available | None |
| **Bedrock (Claude)** | Available | Available | None |
| **KMS** | Available | Available (FIPS) | None |
| **Secrets Manager** | Available | Available | None |
| **CloudTrail** | Available | Available | None |
| **CloudWatch** | Available | Available | None |
| **GuardDuty** | Available | Available | None |
| **AWS Config** | Available | Available | None |
| **Security Hub** | Available | Available | None |
| **CloudFormation** | Available | Available | None |
| **EventBridge** | Available | Available | None |
| **Step Functions** | Available | Available | None |

**Compatibility Score:** 100% (19/19 services)

### Service Limitations

Some AWS services have limitations in GovCloud:

| Service | Limitation | Workaround |
|---------|------------|------------|
| **Route 53** | Private hosted zones only | External DNS provider for public |
| **CloudFront** | Not available | Commercial CloudFront + GovCloud origin |
| **Neptune Serverless** | Not available | Use provisioned Neptune (default) |
| **Some SageMaker features** | Limited | Use Bedrock for inference |

---

## Impact Levels

### DoD Impact Level Reference

| Level | Data Classification | Network | Examples |
|-------|---------------------|---------|----------|
| **IL2** | Public, non-CUI | Internet | Public websites |
| **IL4** | CUI | NIPRNet | DoD unclassified systems |
| **IL5** | CUI, mission-critical | NIPRNet | NSS-adjacent systems |
| **IL6** | SECRET | SIPRNet | Classified systems |

### Aura Support by Impact Level

| Impact Level | Supported | Deployment Model |
|--------------|-----------|------------------|
| IL2 | Yes | Commercial or GovCloud |
| IL4 | Yes | GovCloud required |
| IL5 | Yes | GovCloud required |
| IL6 | No | Requires classified infrastructure |

### IL4/IL5 Configuration

For IL4/IL5 workloads, additional configuration is required:

**IL4 Configuration:**
- Deploy in GovCloud region
- Enable FIPS 140-2 endpoints
- Configure VPC Flow Logs (365-day retention)
- Enable CloudTrail with integrity validation
- Use customer-managed KMS keys

**IL5 Additional Requirements:**
- Enhanced personnel security controls
- Dedicated infrastructure (available)
- Additional network isolation
- Formal authorization process

---

## Network Architecture

### GovCloud VPC Design

```
+-----------------------------------------------------------------------------+
|                        VPC (10.0.0.0/16)                                     |
|                        GovCloud Region                                       |
|                                                                              |
|   +--------------------------------------------------------------------+    |
|   | PUBLIC SUBNETS (10.0.0.0/20)                                       |    |
|   | +---------------------+    +---------------------+                 |    |
|   | | ALB                 |    | NAT Gateway         |                 |    |
|   | | (Internet-facing)   |    | (Egress only)       |                 |    |
|   | +---------------------+    +---------------------+                 |    |
|   +--------------------------------------------------------------------+    |
|                                                                              |
|   +--------------------------------------------------------------------+    |
|   | PRIVATE SUBNETS (10.0.16.0/20)                                     |    |
|   | +---------------------+    +---------------------+                 |    |
|   | | EKS Worker Nodes    |    | Application         |                 |    |
|   | | - API pods          |    | Services            |                 |    |
|   | | - Frontend          |    | - Agents            |                 |    |
|   | +---------------------+    +---------------------+                 |    |
|   +--------------------------------------------------------------------+    |
|                                                                              |
|   +--------------------------------------------------------------------+    |
|   | ISOLATED SUBNETS (10.0.32.0/20) - No Internet                      |    |
|   | +---------------------+    +---------------------+                 |    |
|   | | Neptune Cluster     |    | OpenSearch          |                 |    |
|   | | (Graph DB)          |    | (Vectors)           |                 |    |
|   | +---------------------+    +---------------------+                 |    |
|   +--------------------------------------------------------------------+    |
|                                                                              |
|   +--------------------------------------------------------------------+    |
|   | SANDBOX SUBNETS (10.0.48.0/20) - Completely Isolated               |    |
|   | +---------------------+                                            |    |
|   | | Sandbox Fargate     |    No NAT, No VPC Endpoints               |    |
|   | | (Test execution)    |    Read-only test data access             |    |
|   | +---------------------+                                            |    |
|   +--------------------------------------------------------------------+    |
|                                                                              |
|   VPC ENDPOINTS (Interface & Gateway)                                        |
|   +-----+ +-----+ +-----+ +-----+ +-----+ +-----+ +-----+ +-----+           |
|   | S3  | | ECR | | DDB | | SSM | | STS | | KMS | |Logs | |Bedrk|           |
|   +-----+ +-----+ +-----+ +-----+ +-----+ +-----+ +-----+ +-----+           |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### FedRAMP Authorization Boundary

The authorization boundary for FedRAMP includes:

**Included in Boundary:**
- All VPC components (subnets, security groups, NACLs)
- EKS cluster and worker nodes
- Neptune and OpenSearch clusters
- S3 buckets containing customer data
- KMS keys for encryption
- CloudWatch logs and metrics
- IAM roles and policies

**Inherited from AWS:**
- Physical data center security
- Hypervisor and host security
- Network backbone
- AWS managed service infrastructure

---

## FIPS 140-2 Compliance

### Overview

GovCloud deployments require FIPS 140-2 validated cryptographic modules for processing CUI.

### FIPS Configuration

**Kernel FIPS Mode:**
```bash
# Verify FIPS mode on EKS nodes
cat /proc/sys/crypto/fips_enabled
# Output: 1

# Verify OpenSSL FIPS
openssl version
# Output: OpenSSL 3.0.x (FIPS)
```

**AWS FIPS Endpoints:**

All AWS API calls use FIPS endpoints in GovCloud:

| Service | FIPS Endpoint |
|---------|---------------|
| S3 | s3-fips.us-gov-west-1.amazonaws.com |
| KMS | kms-fips.us-gov-west-1.amazonaws.com |
| STS | sts.us-gov-west-1.amazonaws.com (FIPS by default) |
| Bedrock | bedrock-fips.us-gov-west-1.amazonaws.com |

**TLS Configuration:**
```
# FIPS-approved cipher suites
Ciphers: aes256-ctr,aes192-ctr,aes128-ctr
MACs: hmac-sha2-256,hmac-sha2-512
KexAlgorithms: diffie-hellman-group-exchange-sha256
```

### STIG Hardening

GovCloud deployments include DISA STIG hardening:

| STIG ID | Control | Implementation |
|---------|---------|----------------|
| V-230223 | SELinux enforcing | `/etc/selinux/config: SELINUX=enforcing` |
| V-204431 | Account lockout | `pam_faillock.so deny=3` |
| V-204624 | Session timeout | `TMOUT=900` (15 minutes) |
| V-204498 | USB storage disabled | Kernel module blacklist |
| V-238xxx | SSH hardening | `PermitRootLogin no`, FIPS ciphers |
| V-238xxx | Password complexity | `minlen=15`, complexity requirements |
| V-238xxx | Audit logging | `auditd` with security rules |

**Enable STIG Hardening:**
```yaml
# CloudFormation parameter
Parameters:
  EnableSTIGHardening: 'true'
```

---

## Deployment Process

### Prerequisites

Before deploying to GovCloud:

1. **GovCloud Account:** Active AWS GovCloud account
2. **IAM Roles:** Cross-account roles configured (if applicable)
3. **Bedrock Access:** Model access requested and approved
4. **Network:** VPN or Direct Connect to GovCloud (optional)
5. **FIPS AMIs:** FIPS-enabled AMIs selected

### Deployment Steps

#### Step 1: Configure GovCloud Credentials

```bash
# Configure AWS CLI for GovCloud
aws configure --profile govcloud
# Region: us-gov-west-1
# Output: json

# Verify access
aws sts get-caller-identity --profile govcloud
```

#### Step 2: Request Bedrock Model Access

```bash
# GovCloud Bedrock model access requires explicit approval
# Submit request via GovCloud console
# Approval time: 1-2 business days (vs instant in commercial)
```

#### Step 3: Deploy Foundation Layer

```bash
# Deploy VPC and networking
aws cloudformation deploy \
  --profile govcloud \
  --region us-gov-west-1 \
  --template-file deploy/cloudformation/vpc.yaml \
  --stack-name aura-vpc-prod \
  --parameter-overrides \
    Environment=prod \
    EnableFIPS=true \
  --capabilities CAPABILITY_NAMED_IAM
```

#### Step 4: Deploy Data Layer

```bash
# Deploy Neptune (provisioned mode for GovCloud)
aws cloudformation deploy \
  --profile govcloud \
  --region us-gov-west-1 \
  --template-file deploy/cloudformation/neptune.yaml \
  --stack-name aura-neptune-prod \
  --parameter-overrides \
    Environment=prod \
    InstanceType=db.r5.large \
  --capabilities CAPABILITY_NAMED_IAM
```

#### Step 5: Deploy Compute Layer

```bash
# Deploy EKS cluster
aws cloudformation deploy \
  --profile govcloud \
  --region us-gov-west-1 \
  --template-file deploy/cloudformation/eks.yaml \
  --stack-name aura-eks-prod \
  --parameter-overrides \
    Environment=prod \
    EnableSTIGHardening=true \
  --capabilities CAPABILITY_NAMED_IAM
```

#### Step 6: Deploy Application Layer

```bash
# Deploy Aura application via Helm
helm install aura ./helm/aura \
  --set cloudProvider=aws \
  --set region=us-gov-west-1 \
  --set fipsEnabled=true \
  --set bedrock.endpoint=bedrock-fips.us-gov-west-1.amazonaws.com
```

### Validation Checklist

Post-deployment validation:

- [ ] FIPS mode enabled on all nodes: `cat /proc/sys/crypto/fips_enabled` returns `1`
- [ ] SELinux enforcing: `getenforce` returns `Enforcing`
- [ ] Auditd running: `systemctl is-active auditd` returns `active`
- [ ] VPC Flow Logs enabled with 365-day retention
- [ ] CloudTrail enabled with integrity validation
- [ ] KMS encryption verified for all data stores
- [ ] Bedrock connectivity verified
- [ ] Security groups validated (no 0.0.0.0/0 ingress)

---

## Migration from Commercial AWS

### Migration Overview

Organizations running Aura in commercial AWS can migrate to GovCloud when customer requirements change.

**Migration Timeline:** 2-3 weeks for full cutover

### Migration Steps

#### Week 1: Setup GovCloud Account

| Day | Activity |
|-----|----------|
| 1-2 | Request GovCloud account (if needed) |
| 2-3 | Set up IAM roles and policies |
| 3-4 | Request Bedrock model access |
| 4-5 | Configure VPC and networking |

#### Week 2: Deploy Infrastructure

| Day | Activity |
|-----|----------|
| 1-2 | Deploy Neptune cluster |
| 2-3 | Deploy OpenSearch cluster |
| 3-4 | Deploy EKS cluster |
| 4-5 | Deploy DynamoDB tables, S3 buckets |

#### Week 3: Data Migration

| Day | Activity |
|-----|----------|
| 1-2 | Export Neptune graph data |
| 2-3 | Import to GovCloud Neptune |
| 3-4 | Migrate OpenSearch indices |
| 4-5 | Copy S3 artifacts, validate integrity |

#### Week 4: Application Deployment

| Day | Activity |
|-----|----------|
| 1-2 | Update Helm values for GovCloud |
| 2-3 | Deploy Aura to GovCloud EKS |
| 3-4 | Run smoke tests, validate Bedrock |
| 4-5 | Update DNS, cutover traffic |

### Data Migration Details

**Neptune Graph Data:**
```bash
# Export from commercial
aws neptune create-db-cluster-snapshot \
  --db-cluster-identifier aura-graph-commercial \
  --db-cluster-snapshot-identifier aura-graph-export

# Copy to GovCloud (cross-partition copy requires intermediate S3)
# Export to S3 in commercial, then import in GovCloud

# Import to GovCloud
aws neptune restore-db-cluster-from-snapshot \
  --profile govcloud \
  --db-cluster-identifier aura-graph-govcloud \
  --snapshot-identifier s3://migration-bucket/neptune-export
```

**OpenSearch Indices:**
```bash
# Use OpenSearch snapshot API
# Create snapshot in commercial
# Copy to S3, then to GovCloud S3
# Restore from snapshot in GovCloud
```

---

## Cost Considerations

### Pricing Differences

GovCloud pricing is approximately 10-12% higher than commercial AWS:

| Service | Commercial | GovCloud | Difference |
|---------|------------|----------|------------|
| EKS + EC2 | $174/month | $195/month | +12% |
| Neptune | $92/month | $103/month | +12% |
| OpenSearch | $38/month | $43/month | +13% |
| Other services | $72/month | $80/month | +11% |
| **Total** | **$376/month** | **$421/month** | **+12%** |

### Cost Optimization

**Recommendations:**
- Use Reserved Instances for predictable workloads (30-40% savings)
- Right-size Neptune instances based on actual usage
- Use Spot Instances for sandbox environments (70-80% savings)
- Enable S3 Intelligent-Tiering for automatic cost optimization

---

## Operational Differences

### API Endpoint Changes

All API calls must use GovCloud endpoints:

| Service | Commercial Endpoint | GovCloud Endpoint |
|---------|---------------------|-------------------|
| EKS | eks.us-east-1.amazonaws.com | eks.us-gov-west-1.amazonaws.com |
| Neptune | *.neptune.us-east-1.amazonaws.com | *.neptune.us-gov-west-1.amazonaws.com |
| Bedrock | bedrock-runtime.us-east-1.amazonaws.com | bedrock-runtime.us-gov-west-1.amazonaws.com |
| S3 | s3.us-east-1.amazonaws.com | s3.us-gov-west-1.amazonaws.com |

### ARN Partition

GovCloud uses a different ARN partition:

```
# Commercial
arn:aws:s3:::my-bucket

# GovCloud
arn:aws-us-gov:s3:::my-bucket
```

Aura CloudFormation templates automatically detect and use the correct partition:

```yaml
# Template uses intrinsic function for partition detection
!Sub 'arn:${AWS::Partition}:s3:::${BucketName}'
```

### Support Model

| Aspect | Commercial | GovCloud |
|--------|------------|----------|
| Support plans | Business, Enterprise | Business, Enterprise |
| Response times | Same SLAs | Same SLAs |
| Support channel | Standard | U.S.-based support |
| TAM availability | Yes | Yes (U.S. persons) |

---

## Compliance Considerations

### FedRAMP Boundary

When deploying to GovCloud for FedRAMP:

- GovCloud deployment is **required** for FedRAMP High
- Authorization boundary must be clearly defined
- Interconnections with commercial systems require ISAs
- Continuous monitoring must be GovCloud-aware

### CMMC Requirements

For CMMC Level 2/3 with CUI:

- GovCloud deployment is **required** for CUI
- FCI (Federal Contract Information) can use commercial AWS
- Document system boundary in SSP
- Include GovCloud as part of authorization scope

### Audit Implications

GovCloud provides enhanced audit capabilities:

- U.S. government audit rights
- FedRAMP continuous monitoring integration
- Dedicated compliance reporting
- Enhanced CloudTrail with government templates

---

## Troubleshooting

### Common Issues

**Issue: Bedrock model access denied**
```
Error: User is not authorized to access model
```
**Resolution:** Ensure Bedrock model access is approved in GovCloud console. Approval takes 1-2 business days.

**Issue: FIPS mode not enabled**
```
cat /proc/sys/crypto/fips_enabled returns 0
```
**Resolution:** Verify AMI is FIPS-enabled. Regenerate initramfs with FIPS:
```bash
dracut -f --fips
```

**Issue: KMS key access denied**
```
Error: User is not authorized to perform kms:Decrypt
```
**Resolution:** Verify KMS key policy includes GovCloud service principals. Ensure `kms:ViaService` condition uses GovCloud endpoints.

**Issue: Cross-partition ARN errors**
```
Error: Invalid ARN format
```
**Resolution:** Verify all CloudFormation templates use `${AWS::Partition}` instead of hardcoded `aws`.

---

## Related Documentation

- [Security & Compliance Overview](./index.md)
- [Compliance Certifications](./compliance-certifications.md)
- [Data Handling](./data-handling.md)
- [Audit Logging](./audit-logging.md)
- [GovCloud Readiness Tracker](../../cloud-strategy/GOVCLOUD_READINESS_TRACKER.md)
- [STIG and FIPS Compliance](../../compliance/STIG_FIPS_COMPLIANCE.md)
- [FedRAMP High Roadmap](../../compliance/roadmaps/FEDRAMP_HIGH_ROADMAP.md)

---

## Support

### GovCloud Deployment Assistance

For GovCloud deployment assistance:

- **Email:** govcloud@aenealabs.com
- **Documentation:** [docs.aenealabs.com/govcloud](https://docs.aenealabs.com/govcloud)
- **Professional Services:** Available for migration projects

### Federal Customer Support

Federal customers receive dedicated support:

- U.S.-based support personnel
- FedRAMP-compliant support channels
- Cleared personnel available (for IL5)
- Priority escalation for government customers

---

*Last updated: January 2026 | Version 1.0*
