# CloudFormation Security Group Import Guide

This guide documents the process for importing orphaned security groups into CloudFormation management using the Resource Import feature.

## Situation Summary

- **Problem:** Security groups exist in AWS but are not managed by CloudFormation
- **Constraint:** Security groups have ENI attachments that prevent deletion
- **Solution:** Use CloudFormation Resource Import to adopt existing resources

## Prerequisites

1. AWS CLI v2 configured with appropriate credentials
2. The `aura-security-dev` stack must be deleted (if in ROLLBACK_COMPLETE state)
3. The orphaned security groups must exist in AWS

## Current State

| Security Group Name | Physical ID | ENIs Attached |
|---------------------|-------------|---------------|
| aura-eks-sg-dev | sg-0example000000016 | 2 |
| aura-eks-node-sg-dev | sg-0example000000013 | 6 |
| aura-neptune-sg-dev | sg-0example000000008 | 1 |
| aura-opensearch-sg-dev | sg-0example000000006 | 1 |
| aura-vpce-sg-dev | sg-0example000000009 | 0 |

## Automated Approach (Recommended)

Two scripts automate the entire process:

```bash
# Phase 1: Import existing security groups
./deploy/scripts/import-security-groups.sh

# Phase 2: Add remaining resources (ALB SG, ECS SG, Lambda SG, WAF, ingress rules)
./deploy/scripts/update-security-stack-phase2.sh
```

## Manual Step-by-Step Commands

If you prefer to run commands manually, follow these steps:

### Step 1: Delete the ROLLBACK_COMPLETE Stack

```bash
# Check current state
aws cloudformation describe-stacks \
    --region us-east-1 \
    --stack-name aura-security-dev \
    --query 'Stacks[0].StackStatus'

# Delete the failed stack (only if ROLLBACK_COMPLETE)
aws cloudformation delete-stack \
    --region us-east-1 \
    --stack-name aura-security-dev

# Wait for deletion
aws cloudformation wait stack-delete-complete \
    --region us-east-1 \
    --stack-name aura-security-dev
```

### Step 2: Get Required IDs

```bash
# Get VPC ID
VPC_ID=$(aws ec2 describe-vpcs --region us-east-1 \
    --filters "Name=tag:Name,Values=*aura*" \
    --query 'Vpcs[0].VpcId' --output text)
echo "VPC_ID: $VPC_ID"

# Get Security Group IDs
aws ec2 describe-security-groups --region us-east-1 \
    --filters "Name=group-name,Values=aura-*-dev" \
    --query 'SecurityGroups[*].[GroupName,GroupId]' \
    --output table
```

### Step 3: Create resources-to-import.json

Create `/tmp/resources-to-import.json` with the security group mappings:

```json
[
  {
    "ResourceType": "AWS::EC2::SecurityGroup",
    "LogicalResourceId": "EKSSecurityGroup",
    "ResourceIdentifier": {
      "GroupId": "sg-0example000000016"
    }
  },
  {
    "ResourceType": "AWS::EC2::SecurityGroup",
    "LogicalResourceId": "EKSNodeSecurityGroup",
    "ResourceIdentifier": {
      "GroupId": "sg-0example000000013"
    }
  },
  {
    "ResourceType": "AWS::EC2::SecurityGroup",
    "LogicalResourceId": "NeptuneSecurityGroup",
    "ResourceIdentifier": {
      "GroupId": "sg-0example000000008"
    }
  },
  {
    "ResourceType": "AWS::EC2::SecurityGroup",
    "LogicalResourceId": "OpenSearchSecurityGroup",
    "ResourceIdentifier": {
      "GroupId": "sg-0example000000006"
    }
  },
  {
    "ResourceType": "AWS::EC2::SecurityGroup",
    "LogicalResourceId": "VPCEndpointSecurityGroup",
    "ResourceIdentifier": {
      "GroupId": "sg-0example000000009"
    }
  }
]
```

**Important:** Update the `GroupId` values with your actual security group IDs.

### Step 4: Create Import-Only Template

The import must use a minimal template that only includes the resources being imported. SecurityGroupIngress/Egress resources cannot be imported.

Save to `/tmp/security-import-only.yaml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Project Aura - Layer 1 - Security Groups (Import Phase 1 - SGs Only)'

Parameters:
  Environment:
    Type: String
    Default: dev
  ProjectName:
    Type: String
    Default: aura
  VpcId:
    Type: String

Resources:
  EKSSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    DeletionPolicy: Retain
    Properties:
      GroupName: !Sub '${ProjectName}-eks-sg-${Environment}'
      GroupDescription: Security group for EKS cluster
      VpcId: !Ref VpcId
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-eks-sg-${Environment}'
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  EKSNodeSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    DeletionPolicy: Retain
    Properties:
      GroupName: !Sub '${ProjectName}-eks-node-sg-${Environment}'
      GroupDescription: Security group for EKS worker nodes
      VpcId: !Ref VpcId
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-eks-node-sg-${Environment}'
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  NeptuneSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    DeletionPolicy: Retain
    Properties:
      GroupName: !Sub '${ProjectName}-neptune-sg-${Environment}'
      GroupDescription: Security group for Neptune graph database
      VpcId: !Ref VpcId
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-neptune-sg-${Environment}'
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  OpenSearchSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    DeletionPolicy: Retain
    Properties:
      GroupName: !Sub '${ProjectName}-opensearch-sg-${Environment}'
      GroupDescription: Security group for OpenSearch domain
      VpcId: !Ref VpcId
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-opensearch-sg-${Environment}'
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  VPCEndpointSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    DeletionPolicy: Retain
    Properties:
      GroupName: !Sub '${ProjectName}-vpce-sg-${Environment}'
      GroupDescription: Security group for VPC endpoints - identity-based access control
      VpcId: !Ref VpcId
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-vpce-sg-${Environment}'
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

Outputs:
  EKSSecurityGroupId:
    Value: !Ref EKSSecurityGroup
    Export:
      Name: !Sub '${AWS::StackName}-EKSSecurityGroupId'
  EKSNodeSecurityGroupId:
    Value: !Ref EKSNodeSecurityGroup
    Export:
      Name: !Sub '${AWS::StackName}-EKSNodeSecurityGroupId'
  NeptuneSecurityGroupId:
    Value: !Ref NeptuneSecurityGroup
    Export:
      Name: !Sub '${AWS::StackName}-NeptuneSecurityGroupId'
  OpenSearchSecurityGroupId:
    Value: !Ref OpenSearchSecurityGroup
    Export:
      Name: !Sub '${AWS::StackName}-OpenSearchSecurityGroupId'
  VPCEndpointSecurityGroupId:
    Value: !Ref VPCEndpointSecurityGroup
    Export:
      Name: !Sub '${AWS::StackName}-VPCEndpointSecurityGroupId'
```

**Key Points:**
- `DeletionPolicy: Retain` prevents CloudFormation from deleting the SGs if the stack is deleted
- Only include the 5 security groups being imported
- No ingress/egress rules (they will be added in Phase 2)
- No ALB, ECS, or Lambda SGs (they will be created in Phase 2)

### Step 5: Create the Import Change Set

```bash
aws cloudformation create-change-set \
    --region us-east-1 \
    --stack-name aura-security-dev \
    --change-set-name import-security-groups \
    --change-set-type IMPORT \
    --resources-to-import file:///tmp/resources-to-import.json \
    --template-body file:///tmp/security-import-only.yaml \
    --parameters \
        ParameterKey=Environment,ParameterValue=dev \
        ParameterKey=ProjectName,ParameterValue=aura \
        ParameterKey=VpcId,ParameterValue=$VPC_ID
```

### Step 6: Wait for Change Set Creation

```bash
aws cloudformation wait change-set-create-complete \
    --region us-east-1 \
    --stack-name aura-security-dev \
    --change-set-name import-security-groups
```

### Step 7: Review the Change Set

```bash
aws cloudformation describe-change-set \
    --region us-east-1 \
    --stack-name aura-security-dev \
    --change-set-name import-security-groups \
    --query 'Changes[*].[ResourceChange.Action, ResourceChange.LogicalResourceId, ResourceChange.PhysicalResourceId]' \
    --output table
```

Expected output:
```
-----------------------------------------------------------
|                   DescribeChangeSet                     |
+--------+--------------------------+----------------------+
| Import | EKSSecurityGroup         | sg-0example000000016 |
| Import | EKSNodeSecurityGroup     | sg-0example000000013 |
| Import | NeptuneSecurityGroup     | sg-0example000000008 |
| Import | OpenSearchSecurityGroup  | sg-0example000000006 |
| Import | VPCEndpointSecurityGroup | sg-0example000000009 |
+--------+--------------------------+----------------------+
```

### Step 8: Execute the Import

```bash
aws cloudformation execute-change-set \
    --region us-east-1 \
    --stack-name aura-security-dev \
    --change-set-name import-security-groups

# Wait for completion
aws cloudformation wait stack-import-complete \
    --region us-east-1 \
    --stack-name aura-security-dev
```

### Step 9: Verify Import Success

```bash
# Check stack status
aws cloudformation describe-stacks \
    --region us-east-1 \
    --stack-name aura-security-dev \
    --query 'Stacks[0].StackStatus'

# Should return: "IMPORT_COMPLETE"

# List imported resources
aws cloudformation describe-stack-resources \
    --region us-east-1 \
    --stack-name aura-security-dev \
    --query 'StackResources[*].[LogicalResourceId, PhysicalResourceId, ResourceStatus]' \
    --output table
```

### Step 10: Update Stack with Full Template (Phase 2)

Now update the stack with the complete template to add ALB SG, ECS SG, Lambda SG, ingress rules, and WAF:

```bash
aws cloudformation deploy \
    --region us-east-1 \
    --stack-name aura-security-dev \
    --template-file deploy/cloudformation/security.yaml \
    --parameter-overrides \
        Environment=dev \
        ProjectName=aura \
        VpcId=$VPC_ID \
    --no-fail-on-empty-changeset
```

This will:
- Add ALBSecurityGroup, ECSWorkloadSecurityGroup, LambdaSecurityGroup
- Add all SecurityGroupIngress rules
- Add all SecurityGroupEgress rules
- Add WAF Web ACL and logging configuration

## Troubleshooting

### "Resource with identifier already exists"

If you see this error during import, verify the template's security group names match exactly:
- Template: `!Sub '${ProjectName}-eks-sg-${Environment}'`
- Actual: `aura-eks-sg-dev`

### "Change set status is FAILED"

Check the status reason:
```bash
aws cloudformation describe-change-set \
    --region us-east-1 \
    --stack-name aura-security-dev \
    --change-set-name import-security-groups \
    --query 'StatusReason'
```

### "Stack is in UPDATE_ROLLBACK_COMPLETE state"

The stack experienced a failed update. You may need to:
1. Fix the issue that caused the rollback
2. Run another update to get to a stable state
3. Or delete and re-import if no resources have dependencies

### Import waiter times out

The `wait stack-import-complete` may not exist in older CLI versions. Use:
```bash
aws cloudformation wait stack-create-complete --stack-name aura-security-dev
```

Or poll manually:
```bash
while true; do
    STATUS=$(aws cloudformation describe-stacks \
        --stack-name aura-security-dev \
        --query 'Stacks[0].StackStatus' --output text)
    echo "Status: $STATUS"
    if [[ "$STATUS" == *"COMPLETE"* ]] || [[ "$STATUS" == *"FAILED"* ]]; then
        break
    fi
    sleep 10
done
```

## Resource Identifier Keys Reference

For CloudFormation import, each resource type has specific identifier keys:

| Resource Type | Identifier Key |
|---------------|----------------|
| AWS::EC2::SecurityGroup | GroupId |
| AWS::EC2::VPC | VpcId |
| AWS::EC2::Subnet | SubnetId |
| AWS::RDS::DBCluster | DBClusterIdentifier |
| AWS::Neptune::DBCluster | DBClusterIdentifier |
| AWS::OpenSearchService::Domain | DomainName |

## Security Considerations

1. **DeletionPolicy: Retain** - Used during import to prevent accidental deletion. Remove after confirming stability.

2. **Existing ingress rules** - Any ingress rules already on the security groups will be preserved. CloudFormation adds its rules additively.

3. **Drift detection** - After import, run drift detection to identify any differences:
   ```bash
   aws cloudformation detect-stack-drift --stack-name aura-security-dev
   ```

4. **ENI dependencies** - Imported security groups retain their ENI attachments. This is expected and correct.

## Next Steps After Import

1. Verify all outputs are exported correctly
2. Deploy VPC endpoints stack using the security group outputs
3. Update any dependent stacks (Neptune, OpenSearch, EKS) if needed
4. Consider removing `DeletionPolicy: Retain` after confirming stability
