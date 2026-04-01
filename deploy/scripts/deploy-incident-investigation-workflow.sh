#!/bin/bash
#
# Project Aura - Deploy Incident Investigation Workflow (ADR-025 Phase 3)
#
# This script deploys the Step Functions workflow for RuntimeIncidentAgent:
# - ECS Fargate task definition
# - Step Functions state machine
# - EventBridge rules for CloudWatch/PagerDuty
# - IAM roles for execution
#
# Prerequisites:
#   - incident-response.yaml stack deployed (Phase 1)
#   - RuntimeIncidentAgent Docker image pushed to ECR (Phase 2)
#   - VPC and ECS cluster deployed
#
# Usage:
#   ./deploy/scripts/deploy-incident-investigation-workflow.sh dev
#   ./deploy/scripts/deploy-incident-investigation-workflow.sh qa
#   ./deploy/scripts/deploy-incident-investigation-workflow.sh prod
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parameters
ENVIRONMENT=${1:-dev}
AWS_REGION=${AWS_DEFAULT_REGION:-us-east-1}
PROJECT_NAME="aura"

echo "======================================================"
echo "Project Aura - Incident Investigation Workflow (ADR-025)"
echo "======================================================"
echo "Environment: $ENVIRONMENT"
echo "Region: $AWS_REGION"
echo ""

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|qa|prod)$ ]]; then
    echo -e "${RED}Error: Invalid environment. Must be dev, qa, or prod${NC}"
    exit 1
fi

# Check AWS credentials
echo -e "${BLUE}Checking AWS credentials...${NC}"
if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo -e "${RED}Error: AWS credentials not configured${NC}"
    echo "Run: aws configure"
    exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓ AWS Account: $AWS_ACCOUNT_ID${NC}"
echo ""

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

# Check if incident-response stack exists
INCIDENT_RESPONSE_STACK="${PROJECT_NAME}-incident-response-${ENVIRONMENT}"
if ! aws cloudformation describe-stacks --stack-name $INCIDENT_RESPONSE_STACK --region $AWS_REGION >/dev/null 2>&1; then
    echo -e "${RED}Error: Incident response stack not found: $INCIDENT_RESPONSE_STACK${NC}"
    echo "Deploy Phase 1 first: ./deploy/scripts/deploy-incident-response.sh $ENVIRONMENT"
    exit 1
fi
echo -e "${GREEN}✓ Incident response stack deployed${NC}"

# Get VPC ID from foundation stack (aura-networking-dev, not aura-vpc-dev)
VPC_STACK="${PROJECT_NAME}-networking-${ENVIRONMENT}"
if aws cloudformation describe-stacks --stack-name $VPC_STACK --region $AWS_REGION >/dev/null 2>&1; then
    VPC_ID=$(aws cloudformation describe-stacks --stack-name $VPC_STACK --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' --output text --region $AWS_REGION)
    echo -e "${GREEN}✓ VPC ID: $VPC_ID${NC}"
else
    echo -e "${YELLOW}Warning: VPC stack not found, using default VPC${NC}"
    VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text --region $AWS_REGION)
fi

# Get private subnet IDs
PRIVATE_SUBNETS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=tag:Name,Values=*private*" \
    --query 'Subnets[0:2].SubnetId' \
    --output text \
    --region $AWS_REGION | tr '\t' ',')

if [ -z "$PRIVATE_SUBNETS" ]; then
    echo -e "${YELLOW}Warning: No private subnets found, using all subnets${NC}"
    PRIVATE_SUBNETS=$(aws ec2 describe-subnets \
        --filters "Name=vpc-id,Values=$VPC_ID" \
        --query 'Subnets[0:2].SubnetId' \
        --output text \
        --region $AWS_REGION | tr '\t' ',')
fi
echo -e "${GREEN}✓ Private Subnets: $PRIVATE_SUBNETS${NC}"

# Get ECS cluster name
# ADR-025 uses the network-services cluster for RuntimeIncidentAgent
ECS_CLUSTER="${PROJECT_NAME}-network-services-${ENVIRONMENT}"
if aws ecs describe-clusters --clusters $ECS_CLUSTER --region $AWS_REGION --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    echo -e "${GREEN}✓ ECS Cluster: $ECS_CLUSTER${NC}"
else
    echo -e "${YELLOW}Warning: ECS cluster not active, will create task definition but may fail to run${NC}"
fi

# Check if Docker image exists in ECR
ECR_REPO="${PROJECT_NAME}-runtime-incident-agent"
DOCKER_IMAGE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:latest"

if aws ecr describe-images --repository-name $ECR_REPO --image-ids imageTag=latest --region $AWS_REGION >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Docker image: $DOCKER_IMAGE${NC}"
else
    echo -e "${YELLOW}Warning: Docker image not found in ECR${NC}"
    echo "Build and push image:"
    echo "  docker build --platform linux/amd64 -t $DOCKER_IMAGE -f deploy/docker/agents/Dockerfile.runtime-incident ."
    echo "  aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    echo "  docker push $DOCKER_IMAGE"
    echo ""
    read -p "Continue without Docker image? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""

# Deploy investigation workflow stack
STACK_NAME="${PROJECT_NAME}-incident-investigation-${ENVIRONMENT}"

echo -e "${BLUE}Deploying Incident Investigation Workflow: $STACK_NAME${NC}"
echo "This will create:"
echo "  - Step Functions state machine: ${PROJECT_NAME}-incident-investigation-${ENVIRONMENT}"
echo "  - ECS Fargate task definition: ${PROJECT_NAME}-runtime-incident-${ENVIRONMENT}"
echo "  - EventBridge rule for CloudWatch alarms"
echo "  - EventBridge rule for PagerDuty incidents"
echo "  - IAM roles for Step Functions, ECS execution, ECS task"
echo "  - CloudWatch log groups"
echo ""

# Check if stack exists
if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION >/dev/null 2>&1; then
    echo -e "${YELLOW}Stack exists. Updating...${NC}"
    OPERATION="update-stack"
    WAIT_CONDITION="stack-update-complete"
else
    echo -e "${BLUE}Creating new stack...${NC}"
    OPERATION="create-stack"
    WAIT_CONDITION="stack-create-complete"
fi

# Build parameters
PARAMETERS="ParameterKey=Environment,ParameterValue=${ENVIRONMENT} "
PARAMETERS+="ParameterKey=ProjectName,ParameterValue=${PROJECT_NAME} "
PARAMETERS+="ParameterKey=VpcId,ParameterValue=${VPC_ID} "
PARAMETERS+="ParameterKey=PrivateSubnetIds,ParameterValue=\"${PRIVATE_SUBNETS}\" "
PARAMETERS+="ParameterKey=ECSClusterName,ParameterValue=${ECS_CLUSTER} "
PARAMETERS+="ParameterKey=RuntimeIncidentAgentImage,ParameterValue=${DOCKER_IMAGE}"

# Deploy stack
echo -e "${BLUE}Executing CloudFormation ${OPERATION}...${NC}"
aws cloudformation $OPERATION \
    --stack-name $STACK_NAME \
    --template-body file://deploy/cloudformation/incident-investigation-workflow.yaml \
    --parameters $PARAMETERS \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $AWS_REGION \
    --tags \
        Key=Project,Value=$PROJECT_NAME \
        Key=Environment,Value=$ENVIRONMENT \
        Key=Layer,Value=6 \
        Key=ADR,Value=ADR-025

echo -e "${BLUE}Waiting for stack operation to complete...${NC}"
echo "This may take 5-8 minutes..."
echo ""

if aws cloudformation wait $WAIT_CONDITION --stack-name $STACK_NAME --region $AWS_REGION; then
    echo -e "${GREEN}✓ Stack deployment successful!${NC}"
    echo ""

    # Get stack outputs
    echo -e "${BLUE}Stack Outputs:${NC}"
    aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
        --output table \
        --region $AWS_REGION

    echo ""
    echo -e "${GREEN}==========================================${NC}"
    echo -e "${GREEN}Investigation Workflow Deployed!${NC}"
    echo -e "${GREEN}==========================================${NC}"
    echo ""
    echo "Resources created:"
    echo "  State Machine: ${PROJECT_NAME}-incident-investigation-${ENVIRONMENT}"
    echo "  Task Definition: ${PROJECT_NAME}-runtime-incident-${ENVIRONMENT}"
    echo "  EventBridge Rules: CloudWatch alarms, PagerDuty incidents"
    echo ""
    echo "Next steps:"
    echo "  1. Test with a sample CloudWatch alarm"
    echo "  2. Configure PagerDuty webhook integration"
    echo "  3. Deploy HITL Dashboard (Phase 4)"
    echo ""
    echo "Test execution:"
    echo "  aws stepfunctions start-execution \\"
    echo "    --state-machine-arn \$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`StateMachineArn\`].OutputValue' --output text) \\"
    echo "    --input '{\"id\":\"test-123\",\"source\":\"aws.cloudwatch\",\"detail\":{\"alarmName\":\"test-alarm\"}}'"
    echo ""
else
    echo -e "${RED}✗ Stack deployment failed${NC}"
    echo ""
    echo "Check CloudFormation events for details:"
    echo "  aws cloudformation describe-stack-events --stack-name $STACK_NAME --region $AWS_REGION"
    exit 1
fi
