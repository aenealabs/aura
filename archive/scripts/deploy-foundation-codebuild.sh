#!/bin/bash
#
# Project Aura - Deploy Foundation Layer CodeBuild Project
#
# This script deploys the modular Foundation Layer CodeBuild project
# Part of the AWS Well-Architected modular CI/CD architecture
#

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "Foundation Layer CodeBuild Deployment"
echo "=========================================="
echo ""

# Set AWS profile and region
# Use environment variable or prompt user
if [ -z "$AWS_PROFILE" ]; then
    echo -e "${YELLOW}AWS_PROFILE not set. Please enter your AWS SSO profile name:${NC}"
    echo "Example: AdministratorAccess-123456789012"
    read -p "AWS Profile: " AWS_PROFILE
    export AWS_PROFILE
fi

export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}

ENVIRONMENT=${1:-dev}
PROJECT_NAME="aura"
GITHUB_REPO="https://github.com/aenealabs/aura"
GITHUB_BRANCH="main"

STACK_NAME="${PROJECT_NAME}-codebuild-foundation-${ENVIRONMENT}"

echo -e "${BLUE}Configuration:${NC}"
echo "  Environment: $ENVIRONMENT"
echo "  Project: $PROJECT_NAME"
echo "  Stack Name: $STACK_NAME"
echo "  Region: $AWS_DEFAULT_REGION"
echo ""

# Verify AWS credentials
echo -e "${BLUE}Verifying AWS credentials...${NC}"
if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo -e "${RED}Error: AWS credentials expired${NC}"
    echo "Run: aws sso login --profile $AWS_PROFILE"
    exit 1
fi

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓ Account: $AWS_ACCOUNT${NC}"
echo ""

# Check if Parameter Store parameter exists
echo -e "${BLUE}Checking required Parameter Store parameters...${NC}"
if ! aws ssm get-parameter --name "/aura/dev/alert-email" --region $AWS_DEFAULT_REGION >/dev/null 2>&1; then
    echo -e "${YELLOW}Parameter /aura/dev/alert-email not found${NC}"
    read -p "Enter alert email for build notifications: " ALERT_EMAIL
    aws ssm put-parameter \
        --name "/aura/dev/alert-email" \
        --value "$ALERT_EMAIL" \
        --type String \
        --region $AWS_DEFAULT_REGION
    echo -e "${GREEN}✓ Parameter created${NC}"
else
    ALERT_EMAIL=$(aws ssm get-parameter --name "/aura/dev/alert-email" --query 'Parameter.Value' --output text --region $AWS_DEFAULT_REGION)
    echo -e "${GREEN}✓ Alert email: $ALERT_EMAIL${NC}"
fi
echo ""

# Validate CloudFormation template
echo -e "${BLUE}Validating CloudFormation template...${NC}"
aws cloudformation validate-template \
    --template-body file://deploy/cloudformation/codebuild-foundation.yaml \
    --region $AWS_DEFAULT_REGION >/dev/null

echo -e "${GREEN}✓ Template is valid${NC}"
echo ""

# Deploy CloudFormation stack
echo -e "${BLUE}Deploying Foundation Layer CodeBuild stack...${NC}"

if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_DEFAULT_REGION 2>/dev/null; then
    echo "Stack exists, updating..."
    OPERATION="update-stack"
    WAIT_CONDITION="stack-update-complete"
else
    echo "Stack does not exist, creating..."
    OPERATION="create-stack"
    WAIT_CONDITION="stack-create-complete"
fi

STACK_OUTPUT=$(aws cloudformation $OPERATION \
    --stack-name $STACK_NAME \
    --template-body file://deploy/cloudformation/codebuild-foundation.yaml \
    --parameters \
        ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
        ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
        ParameterKey=GitHubRepository,ParameterValue=$GITHUB_REPO \
        ParameterKey=GitHubBranch,ParameterValue=$GITHUB_BRANCH \
    --capabilities CAPABILITY_NAMED_IAM \
    --tags \
        Key=Project,Value=$PROJECT_NAME \
        Key=Environment,Value=$ENVIRONMENT \
        Key=Layer,Value=foundation \
        Key=ManagedBy,Value=CloudFormation \
    --region $AWS_DEFAULT_REGION \
    --no-cli-pager 2>&1)
STACK_EXIT_CODE=$?

if echo "$STACK_OUTPUT" | grep -q "No updates are to be performed"; then
    echo -e "${YELLOW}No changes detected, stack is up to date${NC}"
elif [ $STACK_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Stack operation initiated${NC}"
    echo ""
    echo -e "${BLUE}Waiting for stack operation to complete...${NC}"
    aws cloudformation wait $WAIT_CONDITION --stack-name $STACK_NAME --region $AWS_DEFAULT_REGION
    echo -e "${GREEN}✓ Stack deployment complete!${NC}"
else
    echo -e "${RED}Error deploying stack:${NC}"
    echo "$STACK_OUTPUT"
    exit 1
fi

echo ""

# Get stack outputs
echo "=========================================="
echo "Stack Outputs"
echo "=========================================="
aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue,Description]' \
    --region $AWS_DEFAULT_REGION \
    --output table

echo ""
echo "=========================================="
echo "Foundation Layer CodeBuild Ready!"
echo "=========================================="
echo ""

# Get CodeBuild project name
CODEBUILD_PROJECT=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`FoundationCodeBuildProjectName`].OutputValue' \
    --output text \
    --region $AWS_DEFAULT_REGION)

echo -e "${GREEN}CodeBuild Project: $CODEBUILD_PROJECT${NC}"
echo ""
echo "Next Steps:"
echo ""
echo "1. Trigger a Foundation Layer build:"
echo -e "   ${BLUE}aws codebuild start-build \\${NC}"
echo -e "   ${BLUE}  --project-name $CODEBUILD_PROJECT \\${NC}"
echo -e "   ${BLUE}  --region $AWS_DEFAULT_REGION${NC}"
echo ""
echo "2. Monitor the build:"
echo -e "   ${BLUE}aws logs tail /aws/codebuild/$CODEBUILD_PROJECT --follow --region $AWS_DEFAULT_REGION${NC}"
echo ""
echo "3. View build history:"
echo -e "   ${BLUE}aws codebuild list-builds-for-project \\${NC}"
echo -e "   ${BLUE}  --project-name $CODEBUILD_PROJECT \\${NC}"
echo -e "   ${BLUE}  --region $AWS_DEFAULT_REGION${NC}"
echo ""
echo "4. Or use the quick-start script:"
echo -e "   ${BLUE}./trigger-foundation-build.sh${NC}"
echo ""
