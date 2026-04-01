#!/bin/bash
#
# Project Aura - Quick Deploy CI/CD Pipeline
#
# This script handles AWS SSO login and deploys the CodeBuild pipeline
#

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "Project Aura - CI/CD Pipeline Deployment"
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

echo -e "${BLUE}Step 1: Refreshing AWS SSO credentials...${NC}"
echo "This will open a browser window for authentication."
echo ""

aws sso login --profile $AWS_PROFILE

echo ""
echo -e "${GREEN}✓ AWS SSO login successful${NC}"
echo ""

# Verify credentials
echo -e "${BLUE}Step 2: Verifying AWS credentials...${NC}"
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_USER=$(aws sts get-caller-identity --query Arn --output text)

echo -e "${GREEN}✓ Account: $AWS_ACCOUNT${NC}"
echo -e "${GREEN}✓ User: $AWS_USER${NC}"
echo ""

# Get email for notifications
if [ -z "$1" ]; then
    echo -e "${YELLOW}Please provide your email for build notifications:${NC}"
    read -p "Email: " ALERT_EMAIL
else
    ALERT_EMAIL=$1
fi

echo ""
echo -e "${BLUE}Step 3: Deploying CodeBuild pipeline...${NC}"
echo ""

# Run deployment script
./deploy/scripts/deploy-codebuild.sh dev $ALERT_EMAIL

echo ""
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo ""
echo "1. Trigger your first build:"
echo "   aws codebuild start-build \\"
echo "     --project-name aura-infra-deploy-dev \\"
echo "     --region us-east-1"
echo ""
echo "2. Monitor the build:"
echo "   aws logs tail /aws/codebuild/aura-infra-deploy-dev --follow --region us-east-1"
echo ""
echo "3. Or run the automated deployment:"
echo "   ./deploy-phase2-infrastructure.sh"
echo ""
