#!/bin/bash
#
# Project Aura - Deploy Network Services Layer CodeBuild Project
#
# This script deploys the CodeBuild project for the Network Services Layer (Layer 1.5).
# Run this ONCE per environment to set up the Network Services Layer CI/CD pipeline.
#
# Usage:
#   ./deploy/scripts/deploy-network-services-codebuild.sh dev
#   ./deploy/scripts/deploy-network-services-codebuild.sh qa
#   ./deploy/scripts/deploy-network-services-codebuild.sh prod
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
GITHUB_REPO="https://github.com/aenealabs/aura"
GITHUB_BRANCH="main"
AWS_REGION=${AWS_DEFAULT_REGION:-us-east-1}
PROJECT_NAME="aura"

echo "=========================================="
echo "Project Aura - Network Services Layer CodeBuild"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "Region: $AWS_REGION"
echo "GitHub Repo: $GITHUB_REPO"
echo "GitHub Branch: $GITHUB_BRANCH"
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

# Deploy CodeBuild stack
STACK_NAME="${PROJECT_NAME}-codebuild-network-services-${ENVIRONMENT}"

echo -e "${BLUE}Deploying Network Services Layer CodeBuild stack: $STACK_NAME${NC}"
echo "This will create:"
echo "  - CodeBuild project for Network Services (dnsmasq via ECS Fargate)"
echo "  - S3 bucket for artifacts"
echo "  - IAM roles with ECS/EC2/ELB/CloudWatch permissions"
echo "  - CloudWatch log group"
echo "  - Build failure alarm"
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

# Deploy stack
aws cloudformation $OPERATION \
    --stack-name $STACK_NAME \
    --template-body file://deploy/cloudformation/codebuild-network-services.yaml \
    --parameters \
        ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
        ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
        ParameterKey=GitHubRepository,ParameterValue=$GITHUB_REPO \
        ParameterKey=GitHubBranch,ParameterValue=$GITHUB_BRANCH \
    --capabilities CAPABILITY_NAMED_IAM \
    --tags \
        Key=Project,Value=$PROJECT_NAME \
        Key=Environment,Value=$ENVIRONMENT \
        Key=Layer,Value=network-services \
        Key=ManagedBy,Value=CloudFormation \
    --region $AWS_REGION \
    --no-cli-pager || {
        if [ "$OPERATION" = "update-stack" ]; then
            echo -e "${YELLOW}No updates to be performed${NC}"
        else
            echo -e "${RED}Stack deployment failed${NC}"
            exit 1
        fi
    }

# Wait for stack completion
echo ""
echo -e "${BLUE}Waiting for stack $OPERATION to complete...${NC}"
echo "This may take 2-3 minutes..."

if aws cloudformation wait $WAIT_CONDITION --stack-name $STACK_NAME --region $AWS_REGION; then
    echo -e "${GREEN}✓ Stack deployment complete!${NC}"
else
    echo -e "${RED}Stack deployment failed${NC}"
    echo "Check CloudFormation console for details"
    exit 1
fi

# Get stack outputs
echo ""
echo "=========================================="
echo "Network Services Layer CodeBuild Outputs"
echo "=========================================="

aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs' \
    --region $AWS_REGION \
    --output table

# Get CodeBuild project name
CODEBUILD_PROJECT=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`CodeBuildProjectName`].OutputValue' \
    --output text \
    --region $AWS_REGION)

ARTIFACTS_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`ArtifactsBucketName`].OutputValue' \
    --output text \
    --region $AWS_REGION)

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo -e "${GREEN}✓ CodeBuild Project: $CODEBUILD_PROJECT${NC}"
echo -e "${GREEN}✓ Artifacts Bucket: $ARTIFACTS_BUCKET${NC}"
echo ""

echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo ""
echo "1. Trigger a build manually:"
echo "   aws codebuild start-build \\"
echo "     --project-name $CODEBUILD_PROJECT \\"
echo "     --region $AWS_REGION"
echo ""
echo "2. View build logs:"
echo "   BUILD_ID=\$(aws codebuild list-builds-for-project \\"
echo "     --project-name $CODEBUILD_PROJECT \\"
echo "     --query 'ids[0]' --output text --region $AWS_REGION)"
echo "   aws codebuild batch-get-builds \\"
echo "     --ids \$BUILD_ID \\"
echo "     --region $AWS_REGION"
echo ""
echo "3. Monitor builds:"
echo "   https://console.aws.amazon.com/codesuite/codebuild/projects/$CODEBUILD_PROJECT/history?region=$AWS_REGION"
echo ""
echo "=========================================="
echo "Network Services Layer CI/CD Pipeline Ready!"
echo "=========================================="
