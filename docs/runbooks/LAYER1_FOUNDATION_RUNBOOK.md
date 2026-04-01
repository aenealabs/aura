# Layer 1: Foundation Runbook

**Layer:** 1 - Foundation
**CodeBuild Project:** `aura-foundation-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-foundation.yml`
**Estimated Deploy Time:** 15-20 minutes

---

## Overview

The Foundation layer establishes core AWS infrastructure that all other layers depend on. This is the first layer deployed and must complete successfully before any other layer can be deployed.

---

## Resources Deployed

| Stack Name | Template | Resources | Deploy Time |
|------------|----------|-----------|-------------|
| `aura-networking-{env}` | networking.yaml | VPC, 4 Subnets (2 public, 2 private), Route Tables, IGW, NAT Gateway | 3-5 min |
| `aura-security-{env}` | security.yaml | 8 Security Groups, AWS WAF Web ACL | 2-3 min |
| `aura-iam-{env}` | iam.yaml | 7 IAM Roles (EKS, Neptune, CodeBuild, Lambda, etc.) | 1-2 min |
| `aura-vpc-endpoints-{env}` | vpc-endpoints.yaml | 9+ VPC Endpoints (ECR, S3, CloudWatch, SSM, STS) | 5-8 min |
| `aura-ecr-base-images-{env}` | ecr-base-images.yaml | 3 ECR Repositories (Alpine, Node.js, Nginx) | 1-2 min |

---

## Dependencies

### Prerequisites (Must exist before deployment)
- SSM Parameter: `/aura/global/codeconnections-arn`
- SSM Parameter: `/aura/{env}/admin-role-arn`
- GitHub CodeConnection (created in AWS Console)

### Downstream Dependencies (Layers that depend on Foundation)
- **All other layers** depend on Foundation
- Layer 2 (Data): Requires VPC, Subnets, Security Groups
- Layer 3 (Compute): Requires VPC, Subnets, Security Groups, IAM Roles

---

## Deployment

### Trigger Deployment
```bash
aws codebuild start-build --project-name aura-foundation-deploy-dev --region us-east-1
```

### Monitor Progress
```bash
# Get latest build ID
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-foundation-deploy-dev \
  --query 'ids[0]' --output text --region us-east-1)

# Check build status
aws codebuild batch-get-builds --ids $BUILD_ID \
  --query 'builds[0].{Status:buildStatus,Phase:currentPhase,StartTime:startTime}' \
  --output table --region us-east-1

# Stream logs
aws logs tail /aws/codebuild/aura-foundation-deploy-dev --follow --region us-east-1
```

### Verify Deployment
```bash
# Check all Foundation stacks
for STACK in aura-networking-dev aura-security-dev aura-iam-dev aura-vpc-endpoints-dev aura-ecr-base-images-dev; do
  STATUS=$(aws cloudformation describe-stacks --stack-name $STACK \
    --query 'Stacks[0].StackStatus' --output text --region us-east-1 2>/dev/null || echo "NOT_FOUND")
  echo "$STACK: $STATUS"
done
```

---

## Troubleshooting

### Issue: VPC Creation Fails with CIDR Conflict

**Symptoms:**
```
CREATE_FAILED - The CIDR '10.0.0.0/16' conflicts with another VPC
```

**Root Cause:** Another VPC with the same CIDR already exists in the account.

**Resolution:**
```bash
# List existing VPCs
aws ec2 describe-vpcs --query 'Vpcs[*].[VpcId,CidrBlock,Tags[?Key==`Name`].Value|[0]]' --output table

# Option 1: Delete conflicting VPC (if unused)
aws ec2 delete-vpc --vpc-id vpc-XXXXX

# Option 2: Change CIDR in networking.yaml
# Edit deploy/cloudformation/networking.yaml, change VpcCIDR parameter
```

---

### Issue: NAT Gateway Creation Slow or Fails

**Symptoms:**
- Stack stuck in CREATE_IN_PROGRESS for >10 minutes
- NAT Gateway in "pending" state

**Root Cause:** Elastic IP allocation issues or AZ capacity.

**Resolution:**
```bash
# Check NAT Gateway status
aws ec2 describe-nat-gateways \
  --filter "Name=tag:Project,Values=aura" \
  --query 'NatGateways[*].[NatGatewayId,State,FailureMessage]' --output table

# If failed, delete and let CloudFormation recreate
aws cloudformation delete-stack --stack-name aura-networking-dev
aws cloudformation wait stack-delete-complete --stack-name aura-networking-dev
aws codebuild start-build --project-name aura-foundation-deploy-dev
```

---

### Issue: Security Group Cannot Be Deleted (ENI in use)

**Symptoms:**
```
DELETE_FAILED - resource sg-XXXXX has a dependent object
```

**Root Cause:** Network interfaces (ENIs) from EKS, Neptune, or OpenSearch are still attached.

**Resolution:**
```bash
# Find ENIs using the security group
aws ec2 describe-network-interfaces \
  --filters "Name=group-id,Values=sg-XXXXX" \
  --query 'NetworkInterfaces[*].[NetworkInterfaceId,Description,Status]' --output table

# Option 1: Delete dependent resources first (EKS, Neptune, OpenSearch)
aws eks delete-nodegroup --cluster-name aura-cluster-dev --nodegroup-name aura-system-ng-dev
aws eks delete-cluster --name aura-cluster-dev

# Option 2: Import orphaned security groups (if recreated outside CloudFormation)
# See docs/SECURITY_GROUP_IMPORT_GUIDE.md
```

---

### Issue: VPC Endpoint Creation Fails

**Symptoms:**
```
CREATE_FAILED - The VPC endpoint service com.amazonaws.us-east-1.XXX does not exist
```

**Root Cause:** Service not available in the region or typo in service name.

**Resolution:**
```bash
# List available VPC endpoint services
aws ec2 describe-vpc-endpoint-services \
  --query 'ServiceNames' --output table --region us-east-1

# Check if the specific service is available
aws ec2 describe-vpc-endpoint-services \
  --service-names com.amazonaws.us-east-1.ecr.api \
  --query 'ServiceDetails[0].ServiceName' --output text
```

---

### Issue: WAF Web ACL Association Fails

**Symptoms:**
```
CREATE_FAILED - WAFv2 WebACL already associated with resource
```

**Root Cause:** An ALB or CloudFront distribution already has a WAF association.

**Resolution:**
```bash
# List existing WAF associations
aws wafv2 list-web-acls --scope REGIONAL --region us-east-1

# Disassociate if needed
aws wafv2 disassociate-web-acl --resource-arn arn:aws:elasticloadbalancing:...
```

---

### Issue: IAM Role Creation Fails with Duplicate Name

**Symptoms:**
```
CREATE_FAILED - Role with name aura-eks-cluster-role-dev already exists
```

**Root Cause:** Role was created manually or by a previous failed deployment.

**Resolution:**
```bash
# Check if role exists
aws iam get-role --role-name aura-eks-cluster-role-dev

# Option 1: Delete the existing role (if safe)
aws iam delete-role --role-name aura-eks-cluster-role-dev

# Option 2: Import the role into CloudFormation
# Add to template: DeletionPolicy: Retain
# Then run: aws cloudformation import ...
```

---

## Recovery Procedures

### Full Layer Recovery (Delete and Recreate)

**WARNING:** This will delete all Foundation resources. Ensure downstream layers are deleted first.

```bash
# 1. Delete stacks in reverse order
aws cloudformation delete-stack --stack-name aura-ecr-base-images-dev
aws cloudformation delete-stack --stack-name aura-vpc-endpoints-dev
aws cloudformation delete-stack --stack-name aura-iam-dev
aws cloudformation delete-stack --stack-name aura-security-dev
aws cloudformation delete-stack --stack-name aura-networking-dev

# 2. Wait for all deletions
for STACK in aura-ecr-base-images-dev aura-vpc-endpoints-dev aura-iam-dev aura-security-dev aura-networking-dev; do
  echo "Waiting for $STACK to delete..."
  aws cloudformation wait stack-delete-complete --stack-name $STACK --region us-east-1
done

# 3. Redeploy
aws codebuild start-build --project-name aura-foundation-deploy-dev
```

### Partial Recovery (Single Stack)

```bash
# Delete specific stack
aws cloudformation delete-stack --stack-name aura-security-dev
aws cloudformation wait stack-delete-complete --stack-name aura-security-dev

# Redeploy entire layer (buildspec handles dependencies)
aws codebuild start-build --project-name aura-foundation-deploy-dev
```

---

## Post-Deployment Steps

### 1. Bootstrap Base Images (Required Once)

After Foundation deploys successfully, run the base images bootstrap:

```bash
./deploy/scripts/bootstrap-base-images.sh dev
```

This pulls Alpine, Node.js, and Nginx images to private ECR repositories.

### 2. Verify VPC Endpoints

```bash
aws ec2 describe-vpc-endpoints \
  --filters "Name=tag:Project,Values=aura" \
  --query 'VpcEndpoints[*].[ServiceName,State]' --output table
```

All endpoints should show `available` state.

### 3. Verify Security Groups

```bash
aws ec2 describe-security-groups \
  --filters "Name=tag:Project,Values=aura" \
  --query 'SecurityGroups[*].[GroupName,GroupId]' --output table
```

---

## Stack Outputs Reference

### aura-networking-{env}
| Output | Description | Used By |
|--------|-------------|---------|
| VpcId | VPC ID | All layers |
| PrivateSubnetIds | Private subnet IDs | Data, Compute, Sandbox |
| PublicSubnetIds | Public subnet IDs | Compute (EKS nodes) |
| VpcCIDR | VPC CIDR block | Security groups |

### aura-security-{env}
| Output | Description | Used By |
|--------|-------------|---------|
| EKSSecurityGroupId | EKS control plane SG | Compute |
| EKSNodeSecurityGroupId | EKS node SG | Compute |
| NeptuneSecurityGroupId | Neptune SG | Data |
| OpenSearchSecurityGroupId | OpenSearch SG | Data |

### aura-iam-{env}
| Output | Description | Used By |
|--------|-------------|---------|
| EKSClusterRoleArn | EKS cluster role | Compute |
| EKSNodeRoleArn | EKS node role | Compute |
| LambdaExecutionRoleArn | Lambda role | Serverless |

---

## Related Documentation

- [RESOURCE_DEPLOYMENT_AUDIT.md](../RESOURCE_DEPLOYMENT_AUDIT.md) - Full resource inventory
- [SECURITY_GROUP_IMPORT_GUIDE.md](../SECURITY_GROUP_IMPORT_GUIDE.md) - SG recovery procedures
- [PREREQUISITES_RUNBOOK.md](../PREREQUISITES_RUNBOOK.md) - Initial setup

---

**Document Version:** 1.0
**Last Updated:** 2025-12-09
