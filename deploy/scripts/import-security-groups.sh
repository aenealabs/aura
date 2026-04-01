#!/bin/bash
# =============================================================================
# CloudFormation Resource Import Script for Security Groups
# =============================================================================
# This script imports orphaned security groups into a new CloudFormation stack.
#
# Prerequisites:
# 1. AWS CLI configured with appropriate credentials
# 2. The aura-security-dev stack in ROLLBACK_COMPLETE has been deleted
# 3. The 5 orphaned security groups exist in AWS
#
# Usage: ./import-security-groups.sh
# =============================================================================

set -e

# Configuration
REGION="us-east-1"
STACK_NAME="aura-security-dev"
ENVIRONMENT="dev"
PROJECT_NAME="aura"
TEMPLATE_DIR="/path/to/project-aura/deploy/cloudformation"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "CloudFormation Security Group Import Script"
echo "=============================================="
echo ""

# Step 1: Get VPC ID
echo -e "${YELLOW}Step 1: Getting VPC ID...${NC}"
VPC_ID=$(aws ec2 describe-vpcs --region ${REGION} \
    --filters "Name=tag:Name,Values=*aura*" \
    --query 'Vpcs[0].VpcId' --output text)

if [ -z "$VPC_ID" ] || [ "$VPC_ID" == "None" ]; then
    echo -e "${RED}ERROR: Could not find VPC with tag containing 'aura'${NC}"
    echo "Please set VPC_ID manually and re-run"
    exit 1
fi
echo -e "${GREEN}Found VPC: ${VPC_ID}${NC}"

# Step 2: Get Security Group IDs
echo ""
echo -e "${YELLOW}Step 2: Discovering orphaned security groups...${NC}"

EKS_SG_ID=$(aws ec2 describe-security-groups --region ${REGION} \
    --filters "Name=group-name,Values=${PROJECT_NAME}-eks-sg-${ENVIRONMENT}" \
    --query 'SecurityGroups[0].GroupId' --output text)
echo "  EKS SG:        ${EKS_SG_ID}"

EKS_NODE_SG_ID=$(aws ec2 describe-security-groups --region ${REGION} \
    --filters "Name=group-name,Values=${PROJECT_NAME}-eks-node-sg-${ENVIRONMENT}" \
    --query 'SecurityGroups[0].GroupId' --output text)
echo "  EKS Node SG:   ${EKS_NODE_SG_ID}"

NEPTUNE_SG_ID=$(aws ec2 describe-security-groups --region ${REGION} \
    --filters "Name=group-name,Values=${PROJECT_NAME}-neptune-sg-${ENVIRONMENT}" \
    --query 'SecurityGroups[0].GroupId' --output text)
echo "  Neptune SG:    ${NEPTUNE_SG_ID}"

OPENSEARCH_SG_ID=$(aws ec2 describe-security-groups --region ${REGION} \
    --filters "Name=group-name,Values=${PROJECT_NAME}-opensearch-sg-${ENVIRONMENT}" \
    --query 'SecurityGroups[0].GroupId' --output text)
echo "  OpenSearch SG: ${OPENSEARCH_SG_ID}"

VPCE_SG_ID=$(aws ec2 describe-security-groups --region ${REGION} \
    --filters "Name=group-name,Values=${PROJECT_NAME}-vpce-sg-${ENVIRONMENT}" \
    --query 'SecurityGroups[0].GroupId' --output text)
echo "  VPC Endpoint SG: ${VPCE_SG_ID}"

# Validate all SGs found
for SG_VAR in EKS_SG_ID EKS_NODE_SG_ID NEPTUNE_SG_ID OPENSEARCH_SG_ID VPCE_SG_ID; do
    SG_VALUE="${!SG_VAR}"
    if [ -z "$SG_VALUE" ] || [ "$SG_VALUE" == "None" ]; then
        echo -e "${RED}ERROR: Could not find security group for ${SG_VAR}${NC}"
        exit 1
    fi
done
echo -e "${GREEN}All 5 security groups found!${NC}"

# Step 3: Check if stack exists and delete if in ROLLBACK_COMPLETE
echo ""
echo -e "${YELLOW}Step 3: Checking existing stack status...${NC}"
STACK_STATUS=$(aws cloudformation describe-stacks --region ${REGION} \
    --stack-name ${STACK_NAME} \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [ "$STACK_STATUS" == "ROLLBACK_COMPLETE" ]; then
    echo -e "${YELLOW}Stack is in ROLLBACK_COMPLETE state. Deleting...${NC}"
    aws cloudformation delete-stack --region ${REGION} --stack-name ${STACK_NAME}
    echo "Waiting for stack deletion..."
    aws cloudformation wait stack-delete-complete --region ${REGION} --stack-name ${STACK_NAME}
    echo -e "${GREEN}Stack deleted successfully${NC}"
    STACK_STATUS="DOES_NOT_EXIST"
elif [ "$STACK_STATUS" != "DOES_NOT_EXIST" ]; then
    echo -e "${RED}ERROR: Stack exists in state ${STACK_STATUS}${NC}"
    echo "Only ROLLBACK_COMPLETE stacks can be deleted for re-import."
    echo "If the stack is healthy, use 'aws cloudformation update-stack' with import instead."
    exit 1
fi
echo -e "${GREEN}Ready for import (no existing stack)${NC}"

# Step 4: Create import-only template
echo ""
echo -e "${YELLOW}Step 4: Creating import-only template...${NC}"

# Create the import-only template (security groups only, no ingress rules)
cat > /tmp/security-import-only.yaml << 'TEMPLATE_EOF'
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Project Aura - Layer 1 - Security Groups (Import Phase 1 - SGs Only)'

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues:
      - dev
      - qa
      - prod
    Description: Environment name

  ProjectName:
    Type: String
    Default: aura
    Description: Project name

  VpcId:
    Type: String
    Description: VPC ID from networking stack

Resources:
  # EKS Cluster Security Group
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

  # EKS Node Security Group
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

  # Neptune Security Group
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

  # OpenSearch Security Group
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

  # VPC Endpoint Security Group
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
TEMPLATE_EOF

echo -e "${GREEN}Import template created at /tmp/security-import-only.yaml${NC}"

# Step 5: Create resources-to-import.json
echo ""
echo -e "${YELLOW}Step 5: Creating resources-to-import.json...${NC}"

cat > /tmp/resources-to-import.json << EOF
[
  {
    "ResourceType": "AWS::EC2::SecurityGroup",
    "LogicalResourceId": "EKSSecurityGroup",
    "ResourceIdentifier": {
      "Id": "${EKS_SG_ID}"
    }
  },
  {
    "ResourceType": "AWS::EC2::SecurityGroup",
    "LogicalResourceId": "EKSNodeSecurityGroup",
    "ResourceIdentifier": {
      "Id": "${EKS_NODE_SG_ID}"
    }
  },
  {
    "ResourceType": "AWS::EC2::SecurityGroup",
    "LogicalResourceId": "NeptuneSecurityGroup",
    "ResourceIdentifier": {
      "Id": "${NEPTUNE_SG_ID}"
    }
  },
  {
    "ResourceType": "AWS::EC2::SecurityGroup",
    "LogicalResourceId": "OpenSearchSecurityGroup",
    "ResourceIdentifier": {
      "Id": "${OPENSEARCH_SG_ID}"
    }
  },
  {
    "ResourceType": "AWS::EC2::SecurityGroup",
    "LogicalResourceId": "VPCEndpointSecurityGroup",
    "ResourceIdentifier": {
      "Id": "${VPCE_SG_ID}"
    }
  }
]
EOF

echo -e "${GREEN}Resources to import:${NC}"
cat /tmp/resources-to-import.json

# Step 6: Create the import change set
echo ""
echo -e "${YELLOW}Step 6: Creating import change set...${NC}"

CHANGE_SET_NAME="import-security-groups-$(date +%Y%m%d-%H%M%S)"

aws cloudformation create-change-set \
    --region ${REGION} \
    --stack-name ${STACK_NAME} \
    --change-set-name ${CHANGE_SET_NAME} \
    --change-set-type IMPORT \
    --resources-to-import file:///tmp/resources-to-import.json \
    --template-body file:///tmp/security-import-only.yaml \
    --parameters \
        ParameterKey=Environment,ParameterValue=${ENVIRONMENT} \
        ParameterKey=ProjectName,ParameterValue=${PROJECT_NAME} \
        ParameterKey=VpcId,ParameterValue=${VPC_ID}

echo "Waiting for change set to be created..."
aws cloudformation wait change-set-create-complete \
    --region ${REGION} \
    --stack-name ${STACK_NAME} \
    --change-set-name ${CHANGE_SET_NAME}

echo -e "${GREEN}Change set created: ${CHANGE_SET_NAME}${NC}"

# Step 7: Describe the change set
echo ""
echo -e "${YELLOW}Step 7: Reviewing change set...${NC}"
aws cloudformation describe-change-set \
    --region ${REGION} \
    --stack-name ${STACK_NAME} \
    --change-set-name ${CHANGE_SET_NAME} \
    --query 'Changes[*].[ResourceChange.Action, ResourceChange.LogicalResourceId, ResourceChange.PhysicalResourceId]' \
    --output table

# Step 8: Execute the change set (with confirmation)
echo ""
echo -e "${YELLOW}Step 8: Execute the change set?${NC}"
read -p "Type 'yes' to execute the import: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${RED}Import cancelled. Change set remains for manual execution.${NC}"
    echo "To execute manually:"
    echo "  aws cloudformation execute-change-set --region ${REGION} --stack-name ${STACK_NAME} --change-set-name ${CHANGE_SET_NAME}"
    exit 0
fi

echo "Executing change set..."
aws cloudformation execute-change-set \
    --region ${REGION} \
    --stack-name ${STACK_NAME} \
    --change-set-name ${CHANGE_SET_NAME}

echo "Waiting for import to complete..."
aws cloudformation wait stack-import-complete \
    --region ${REGION} \
    --stack-name ${STACK_NAME}

echo -e "${GREEN}Import complete!${NC}"

# Step 9: Verify the import
echo ""
echo -e "${YELLOW}Step 9: Verifying import...${NC}"
aws cloudformation describe-stack-resources \
    --region ${REGION} \
    --stack-name ${STACK_NAME} \
    --query 'StackResources[*].[LogicalResourceId, PhysicalResourceId, ResourceStatus]' \
    --output table

# Step 10: Show outputs
echo ""
echo -e "${YELLOW}Step 10: Stack outputs (for VPC endpoints deployment)...${NC}"
aws cloudformation describe-stacks \
    --region ${REGION} \
    --stack-name ${STACK_NAME} \
    --query 'Stacks[0].Outputs[*].[OutputKey, OutputValue]' \
    --output table

echo ""
echo "=============================================="
echo -e "${GREEN}PHASE 1 COMPLETE: Security groups imported!${NC}"
echo "=============================================="
echo ""
echo "NEXT STEPS:"
echo "1. Run Phase 2 to add remaining resources (ALB SG, ECS SG, Lambda SG, WAF, ingress rules):"
echo "   ./update-security-stack-phase2.sh"
echo ""
echo "2. After Phase 2, deploy VPC endpoints:"
echo "   aws cloudformation deploy --stack-name aura-vpce-dev --template-file ${TEMPLATE_DIR}/vpc-endpoints.yaml ..."
echo ""
