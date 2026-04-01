#!/bin/bash
set -e

# Foundation Layer Deployment Script
# Phase 2 Ready: Can be used directly by a dedicated CodeBuild project

echo "=========================================="
echo "Foundation Layer Deployment"
echo "=========================================="

: ${ENVIRONMENT:="dev"}
: ${PROJECT_NAME:="aura"}
: ${AWS_DEFAULT_REGION:="us-east-1"}

# Deploy Networking Stack
echo "Deploying Networking Stack..."
NETWORKING_STACK="${PROJECT_NAME}-networking-${ENVIRONMENT}"

if aws cloudformation describe-stacks --stack-name $NETWORKING_STACK --region $AWS_DEFAULT_REGION 2>/dev/null; then
  OPERATION="update-stack"
  WAIT_CONDITION="stack-update-complete"
else
  OPERATION="create-stack"
  WAIT_CONDITION="stack-create-complete"
fi

aws cloudformation $OPERATION \
  --stack-name $NETWORKING_STACK \
  --template-body file://deploy/cloudformation/networking.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
    ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
    ParameterKey=VpcCIDR,ParameterValue=10.0.0.0/16 \
    ParameterKey=AvailabilityZones,ParameterValue="us-east-1a,us-east-1b" \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Key=Project,Value=$PROJECT_NAME Key=Environment,Value=$ENVIRONMENT Key=Layer,Value=foundation \
  --region $AWS_DEFAULT_REGION \
  --no-cli-pager || true

echo "Waiting for networking stack..."
aws cloudformation wait $WAIT_CONDITION --stack-name $NETWORKING_STACK --region $AWS_DEFAULT_REGION

# Get VPC ID for security stack
VPC_ID=$(aws cloudformation describe-stacks --stack-name $NETWORKING_STACK \
  --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
  --output text --region $AWS_DEFAULT_REGION)

echo "VPC ID: $VPC_ID"

# Deploy Security Stack
echo "Deploying Security Stack..."
SECURITY_STACK="${PROJECT_NAME}-security-${ENVIRONMENT}"

if aws cloudformation describe-stacks --stack-name $SECURITY_STACK --region $AWS_DEFAULT_REGION 2>/dev/null; then
  OPERATION="update-stack"
  WAIT_CONDITION="stack-update-complete"
else
  OPERATION="create-stack"
  WAIT_CONDITION="stack-create-complete"
fi

aws cloudformation $OPERATION \
  --stack-name $SECURITY_STACK \
  --template-body file://deploy/cloudformation/security.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
    ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
    ParameterKey=VpcId,ParameterValue=$VPC_ID \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Key=Project,Value=$PROJECT_NAME Key=Environment,Value=$ENVIRONMENT Key=Layer,Value=foundation \
  --region $AWS_DEFAULT_REGION \
  --no-cli-pager || true

echo "Waiting for security stack..."
aws cloudformation wait $WAIT_CONDITION --stack-name $SECURITY_STACK --region $AWS_DEFAULT_REGION

# Deploy IAM Stack
echo "Deploying IAM Stack..."
IAM_STACK="${PROJECT_NAME}-iam-${ENVIRONMENT}"

if aws cloudformation describe-stacks --stack-name $IAM_STACK --region $AWS_DEFAULT_REGION 2>/dev/null; then
  OPERATION="update-stack"
  WAIT_CONDITION="stack-update-complete"
else
  OPERATION="create-stack"
  WAIT_CONDITION="stack-create-complete"
fi

aws cloudformation $OPERATION \
  --stack-name $IAM_STACK \
  --template-body file://deploy/cloudformation/iam.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
    ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Key=Project,Value=$PROJECT_NAME Key=Environment,Value=$ENVIRONMENT Key=Layer,Value=foundation \
  --region $AWS_DEFAULT_REGION \
  --no-cli-pager || true

echo "Waiting for IAM stack..."
aws cloudformation wait $WAIT_CONDITION --stack-name $IAM_STACK --region $AWS_DEFAULT_REGION

echo "Foundation layer deployment completed!"
aws cloudformation describe-stacks --stack-name $NETWORKING_STACK --query 'Stacks[0].Outputs' --region $AWS_DEFAULT_REGION --output table
