#!/bin/bash
#
# Project Aura - Deploy CodeBuild CI/CD Pipeline
#
# This script deploys the CodeBuild project that handles all infrastructure deployments.
# Run this ONCE per environment to set up the CI/CD pipeline.
#
# Usage:
#   ./deploy/scripts/deploy-codebuild.sh dev your-email@example.com
#   ./deploy/scripts/deploy-codebuild.sh qa your-email@example.com
#   ./deploy/scripts/deploy-codebuild.sh prod your-email@example.com
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
ALERT_EMAIL=${2:-""}
GITHUB_REPO="https://github.com/aenealabs/aura"
GITHUB_BRANCH="main"
AWS_REGION=${AWS_DEFAULT_REGION:-us-east-1}
PROJECT_NAME="aura"

echo "=========================================="
echo "Project Aura - CodeBuild Deployment"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "Region: $AWS_REGION"
echo "GitHub Repo: $GITHUB_REPO"
echo "GitHub Branch: $GITHUB_BRANCH"
echo ""

# Validate email parameter
if [ -z "$ALERT_EMAIL" ]; then
    echo -e "${RED}Error: Alert email is required${NC}"
    echo "Usage: $0 <environment> <alert-email>"
    echo "Example: $0 dev your-email@example.com"
    exit 1
fi

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

# Note: Alert email parameter will be created by CloudFormation stack
echo -e "${BLUE}Alert email will be stored in Parameter Store: /aura/${ENVIRONMENT}/alert-email${NC}"
echo ""

# Deploy CodeBuild stack
STACK_NAME="${PROJECT_NAME}-codebuild-${ENVIRONMENT}"

echo -e "${BLUE}Deploying CodeBuild stack: $STACK_NAME${NC}"
echo "This will create:"
echo "  - CodeBuild project for infrastructure deployment"
echo "  - S3 bucket for build artifacts"
echo "  - IAM roles for CodeBuild"
echo "  - CloudWatch log group"
echo "  - SNS topic for build notifications"
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
    --template-body file://deploy/cloudformation/codebuild.yaml \
    --parameters \
        ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
        ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
        ParameterKey=GitHubRepository,ParameterValue=$GITHUB_REPO \
        ParameterKey=GitHubBranch,ParameterValue=$GITHUB_BRANCH \
        ParameterKey=AlertEmail,ParameterValue=$ALERT_EMAIL \
    --capabilities CAPABILITY_NAMED_IAM \
    --tags \
        Key=Project,Value=$PROJECT_NAME \
        Key=Environment,Value=$ENVIRONMENT \
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
echo "CodeBuild Stack Outputs"
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
    --query 'Stacks[0].Outputs[?OutputKey==`ArtifactsBucket`].OutputValue' \
    --output text \
    --region $AWS_REGION)

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo -e "${GREEN}✓ CodeBuild Project: $CODEBUILD_PROJECT${NC}"
echo -e "${GREEN}✓ Artifacts Bucket: $ARTIFACTS_BUCKET${NC}"
echo -e "${GREEN}✓ Alert Email: $ALERT_EMAIL${NC}"
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
echo "   aws codebuild batch-get-builds \\"
echo "     --ids \$(aws codebuild list-builds-for-project \\"
echo "       --project-name $CODEBUILD_PROJECT \\"
echo "       --query 'ids[0]' --output text --region $AWS_REGION) \\"
echo "     --region $AWS_REGION"
echo ""
echo "3. Set up GitHub webhook (optional):"
echo "   - Go to: https://github.com/aenealabs/aura/settings/hooks"
echo "   - Add webhook with payload URL from CodeBuild console"
echo "   - Triggers automatic builds on push to $GITHUB_BRANCH"
echo ""
echo "4. Monitor builds:"
echo "   https://console.aws.amazon.com/codesuite/codebuild/projects/$CODEBUILD_PROJECT/history?region=$AWS_REGION"
echo ""
echo "=========================================="
echo "CI/CD Pipeline Ready!"
echo "=========================================="
