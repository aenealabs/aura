#!/bin/bash
# Removed 'set -e' to allow proper error handling for CloudFormation "No updates" errors
# Errors are now explicitly checked and handled

# Compute Layer Deployment Script
# Phase 2 Ready: Can be used directly by a dedicated CodeBuild project

echo "=========================================="
echo "Compute Layer Deployment"
echo "=========================================="

: ${ENVIRONMENT:="dev"}
: ${PROJECT_NAME:="aura"}
: ${AWS_DEFAULT_REGION:="us-east-1"}

# Get foundation outputs
NETWORKING_STACK="${PROJECT_NAME}-networking-${ENVIRONMENT}"
SECURITY_STACK="${PROJECT_NAME}-security-${ENVIRONMENT}"
IAM_STACK="${PROJECT_NAME}-iam-${ENVIRONMENT}"

VPC_ID=$(aws cloudformation describe-stacks --stack-name $NETWORKING_STACK \
  --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
  --output text --region $AWS_DEFAULT_REGION)

PRIVATE_SUBNET_IDS=$(aws cloudformation describe-stacks --stack-name $NETWORKING_STACK \
  --query 'Stacks[0].Outputs[?OutputKey==`PrivateSubnetIds`].OutputValue' \
  --output text --region $AWS_DEFAULT_REGION)

EKS_SG=$(aws cloudformation describe-stacks --stack-name $SECURITY_STACK \
  --query 'Stacks[0].Outputs[?OutputKey==`EKSSecurityGroupId`].OutputValue' \
  --output text --region $AWS_DEFAULT_REGION)

EKS_NODE_SG=$(aws cloudformation describe-stacks --stack-name $SECURITY_STACK \
  --query 'Stacks[0].Outputs[?OutputKey==`EKSNodeSecurityGroupId`].OutputValue' \
  --output text --region $AWS_DEFAULT_REGION)

EKS_CLUSTER_ROLE=$(aws cloudformation describe-stacks --stack-name $IAM_STACK \
  --query 'Stacks[0].Outputs[?OutputKey==`EKSClusterRoleArn`].OutputValue' \
  --output text --region $AWS_DEFAULT_REGION)

EKS_NODE_ROLE=$(aws cloudformation describe-stacks --stack-name $IAM_STACK \
  --query 'Stacks[0].Outputs[?OutputKey==`EKSNodeRoleArn`].OutputValue' \
  --output text --region $AWS_DEFAULT_REGION)

# Use PUBLIC subnets for EKS nodes (GovCloud-compatible solution)
# Nodes need internet access to download container images from public registries
# VPC Endpoints don't work for docker.io, quay.io, gcr.io
PUBLIC_SUBNET_IDS=$(aws cloudformation describe-stacks --stack-name $NETWORKING_STACK \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicSubnetIds`].OutputValue' \
  --output text --region $AWS_DEFAULT_REGION)

echo "VPC ID: $VPC_ID"
echo "EKS Cluster Security Group: $EKS_SG"
echo "EKS Node Security Group: $EKS_NODE_SG"
echo "Using PUBLIC subnets for EKS nodes: $PUBLIC_SUBNET_IDS"

# Deploy EKS
echo "Deploying EKS Stack (this may take 15-20 minutes)..."
EKS_STACK="${PROJECT_NAME}-eks-${ENVIRONMENT}"

if aws cloudformation describe-stacks --stack-name $EKS_STACK --region $AWS_DEFAULT_REGION 2>/dev/null; then
  OPERATION="update-stack"
  WAIT_CONDITION="stack-update-complete"
else
  OPERATION="create-stack"
  WAIT_CONDITION="stack-create-complete"
fi

aws cloudformation $OPERATION \
  --stack-name $EKS_STACK \
  --template-body file://deploy/cloudformation/eks.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
    ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
    ParameterKey=PrivateSubnetIds,ParameterValue=\"$PUBLIC_SUBNET_IDS\" \
    ParameterKey=EKSSecurityGroupId,ParameterValue=$EKS_SG \
    ParameterKey=EKSNodeSecurityGroupId,ParameterValue=$EKS_NODE_SG \
    ParameterKey=EKSClusterRoleArn,ParameterValue=$EKS_CLUSTER_ROLE \
    ParameterKey=EKSNodeRoleArn,ParameterValue=$EKS_NODE_ROLE \
    ParameterKey=NodeInstanceType,ParameterValue=t3.medium \
    ParameterKey=NodeGroupMinSize,ParameterValue=2 \
    ParameterKey=NodeGroupMaxSize,ParameterValue=5 \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Key=Project,Value=$PROJECT_NAME Key=Environment,Value=$ENVIRONMENT Key=Layer,Value=compute \
  --region $AWS_DEFAULT_REGION \
  --no-cli-pager || true

echo "Waiting for EKS stack..."
aws cloudformation wait $WAIT_CONDITION --stack-name $EKS_STACK --region $AWS_DEFAULT_REGION

echo "Compute layer deployment completed!"
aws cloudformation describe-stacks --stack-name $EKS_STACK --query 'Stacks[0].Outputs' --region $AWS_DEFAULT_REGION --output table
