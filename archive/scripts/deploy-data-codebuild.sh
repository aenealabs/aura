#!/bin/bash
#
# Project Aura - Deploy Data Layer CodeBuild Project
#

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "Data Layer CodeBuild Deployment"
echo "=========================================="

# Set AWS profile
if [ -z "$AWS_PROFILE" ]; then
    echo -e "${YELLOW}AWS_PROFILE not set. Enter your AWS SSO profile:${NC}"
    read -p "AWS Profile: " AWS_PROFILE
    export AWS_PROFILE
fi

export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}

ENVIRONMENT=${1:-dev}
PROJECT_NAME="aura"
STACK_NAME="${PROJECT_NAME}-codebuild-data-${ENVIRONMENT}"

echo "Environment: $ENVIRONMENT"
echo "Stack: $STACK_NAME"
echo ""

# Verify credentials
echo -e "${BLUE}Verifying AWS credentials...${NC}"
if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo -e "${RED}Error: AWS credentials expired${NC}"
    exit 1
fi

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓ Account: $AWS_ACCOUNT${NC}"
echo ""

# Check secrets exist
echo -e "${BLUE}Checking required secrets...${NC}"
for secret in "aura/dev/neptune" "aura/dev/opensearch"; do
    if ! aws secretsmanager describe-secret --secret-id "$secret" --region $AWS_DEFAULT_REGION >/dev/null 2>&1; then
        echo -e "${YELLOW}Secret $secret not found, creating...${NC}"
        aws secretsmanager create-secret \
            --name "$secret" \
            --secret-string '{"password":"TempPassword123!ChangeMe"}' \
            --region $AWS_DEFAULT_REGION
        echo -e "${GREEN}✓ Created $secret${NC}"
    else
        echo -e "${GREEN}✓ Secret $secret exists${NC}"
    fi
done
echo ""

# Deploy stack
echo -e "${BLUE}Deploying Data Layer CodeBuild stack...${NC}"

if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_DEFAULT_REGION 2>/dev/null; then
    OPERATION="update-stack"
    WAIT_CONDITION="stack-update-complete"
else
    OPERATION="create-stack"
    WAIT_CONDITION="stack-create-complete"
fi

STACK_OUTPUT=$(aws cloudformation $OPERATION \
    --stack-name $STACK_NAME \
    --template-body file://deploy/cloudformation/codebuild-data.yaml \
    --parameters \
        ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
        ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
        ParameterKey=GitHubRepository,ParameterValue=https://github.com/aenealabs/aura \
        ParameterKey=GitHubBranch,ParameterValue=main \
    --capabilities CAPABILITY_NAMED_IAM \
    --tags \
        Key=Project,Value=$PROJECT_NAME \
        Key=Environment,Value=$ENVIRONMENT \
        Key=Layer,Value=data \
    --region $AWS_DEFAULT_REGION \
    --no-cli-pager 2>&1)

if echo "$STACK_OUTPUT" | grep -q "No updates are to be performed"; then
    echo -e "${YELLOW}No changes detected${NC}"
elif [ $? -eq 0 ]; then
    echo -e "${BLUE}Waiting for stack...${NC}"
    aws cloudformation wait $WAIT_CONDITION --stack-name $STACK_NAME --region $AWS_DEFAULT_REGION
    echo -e "${GREEN}✓ Stack deployment complete!${NC}"
else
    echo -e "${RED}Error:${NC}"
    echo "$STACK_OUTPUT"
    exit 1
fi

echo ""
echo "=========================================="
echo "Data Layer CodeBuild Ready!"
echo "=========================================="
echo ""

CODEBUILD_PROJECT=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`DataCodeBuildProjectName`].OutputValue' \
    --output text \
    --region $AWS_DEFAULT_REGION)

echo -e "${GREEN}CodeBuild Project: $CODEBUILD_PROJECT${NC}"
echo ""
echo "Trigger a Data Layer build:"
echo -e "  ${BLUE}./trigger-data-build.sh${NC}"
echo ""
