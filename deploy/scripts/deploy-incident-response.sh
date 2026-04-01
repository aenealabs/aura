#!/bin/bash
#
# Project Aura - Deploy Incident Response Infrastructure (ADR-025 Phase 1)
#
# This script deploys the RuntimeIncidentAgent foundation:
# - DynamoDB tables for deployments and investigations
# - EventBridge event bus and rules
# - Lambda function for deployment recording
# - SNS topic for incident alerts
#
# Usage:
#   ./deploy/scripts/deploy-incident-response.sh dev
#   ./deploy/scripts/deploy-incident-response.sh qa
#   ./deploy/scripts/deploy-incident-response.sh prod
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

echo "============================================"
echo "Project Aura - Incident Response (ADR-025)"
echo "============================================"
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

# Get alert email from SSM Parameter Store
echo -e "${BLUE}Retrieving alert email from SSM...${NC}"
ALERT_EMAIL=$(aws ssm get-parameter \
    --name "/aura/${ENVIRONMENT}/alert-email" \
    --query 'Parameter.Value' \
    --output text \
    --region $AWS_REGION 2>/dev/null || echo "")

if [ -z "$ALERT_EMAIL" ]; then
    echo -e "${YELLOW}Warning: No alert email configured in SSM Parameter Store${NC}"
    echo "To configure: aws ssm put-parameter --name /aura/${ENVIRONMENT}/alert-email --value your-email@example.com --type String"
else
    echo -e "${GREEN}✓ Alert Email: $ALERT_EMAIL${NC}"
fi
echo ""

# Deploy Incident Response stack
STACK_NAME="${PROJECT_NAME}-incident-response-${ENVIRONMENT}"

echo -e "${BLUE}Deploying Incident Response infrastructure: $STACK_NAME${NC}"
echo "This will create:"
echo "  - DynamoDB table: ${PROJECT_NAME}-deployments-${ENVIRONMENT} (deployment correlation)"
echo "  - DynamoDB table: ${PROJECT_NAME}-incident-investigations-${ENVIRONMENT} (RCA storage)"
echo "  - EventBridge event bus: ${PROJECT_NAME}-incident-events-${ENVIRONMENT}"
echo "  - Lambda function: ${PROJECT_NAME}-deployment-recorder-${ENVIRONMENT}"
echo "  - SNS topic: ${PROJECT_NAME}-incident-alerts-${ENVIRONMENT}"
echo "  - KMS key for encryption at rest"
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

if [ -n "$ALERT_EMAIL" ]; then
    PARAMETERS+="ParameterKey=AlertEmail,ParameterValue=${ALERT_EMAIL}"
fi

# Deploy stack
echo -e "${BLUE}Executing CloudFormation ${OPERATION}...${NC}"
aws cloudformation $OPERATION \
    --stack-name $STACK_NAME \
    --template-body file://deploy/cloudformation/incident-response.yaml \
    --parameters $PARAMETERS \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $AWS_REGION \
    --tags \
        Key=Project,Value=$PROJECT_NAME \
        Key=Environment,Value=$ENVIRONMENT \
        Key=Layer,Value=6 \
        Key=ADR,Value=ADR-025

echo -e "${BLUE}Waiting for stack operation to complete...${NC}"
echo "This may take 3-5 minutes..."
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
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Incident Response Infrastructure Ready!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Configure ArgoCD to send deployment events to EventBridge"
    echo "  2. Deploy RuntimeIncidentAgent (Phase 2)"
    echo "  3. Configure CloudWatch alarms to trigger investigations"
    echo ""
    echo "Verify deployment:"
    echo "  aws dynamodb describe-table --table-name ${PROJECT_NAME}-deployments-${ENVIRONMENT}"
    echo "  aws dynamodb describe-table --table-name ${PROJECT_NAME}-incident-investigations-${ENVIRONMENT}"
    echo "  aws lambda get-function --function-name ${PROJECT_NAME}-deployment-recorder-${ENVIRONMENT}"
    echo ""
else
    echo -e "${RED}✗ Stack deployment failed${NC}"
    echo ""
    echo "Check CloudFormation events for details:"
    echo "  aws cloudformation describe-stack-events --stack-name $STACK_NAME --region $AWS_REGION"
    exit 1
fi
