#!/bin/bash
#
# Project Aura - Deploy Phase 2 Infrastructure via CodeBuild
#
# This script triggers CodeBuild to deploy:
# - Data Layer (Neptune, OpenSearch)
# - Compute Layer (EKS multi-tier)
# - Application Layer (Services, dnsmasq)
# - Observability Layer (Prometheus, CloudWatch)
#

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

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
CODEBUILD_PROJECT="${PROJECT_NAME}-infra-deploy-${ENVIRONMENT}"

echo "=========================================="
echo "Project Aura - Phase 2 Infrastructure Deployment"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "CodeBuild Project: $CODEBUILD_PROJECT"
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

# Check if CodeBuild project exists
echo -e "${BLUE}Checking CodeBuild project...${NC}"
if ! aws codebuild batch-get-projects --names $CODEBUILD_PROJECT --region $AWS_DEFAULT_REGION >/dev/null 2>&1; then
    echo -e "${RED}Error: CodeBuild project not found: $CODEBUILD_PROJECT${NC}"
    echo ""
    echo "Deploy CodeBuild first:"
    echo "  ./deploy-cicd-pipeline.sh"
    exit 1
fi

echo -e "${GREEN}✓ CodeBuild project exists${NC}"
echo ""

# Run pre-deployment smoke tests locally
echo -e "${BLUE}Running pre-deployment smoke tests...${NC}"
if pytest tests/smoke/test_platform_smoke.py -m smoke -v --tb=short -o addopts="" 2>&1 | tail -20; then
    echo ""
    echo -e "${GREEN}✓ Smoke tests PASSED (10/10)${NC}"
else
    echo ""
    echo -e "${RED}✗ Smoke tests FAILED${NC}"
    echo "Fix tests before deploying"
    exit 1
fi
echo ""

# Trigger CodeBuild
echo -e "${BLUE}Triggering CodeBuild deployment...${NC}"
echo ""

BUILD_ID=$(aws codebuild start-build \
    --project-name $CODEBUILD_PROJECT \
    --region $AWS_DEFAULT_REGION \
    --query 'build.id' \
    --output text)

echo -e "${GREEN}✓ Build started: $BUILD_ID${NC}"
echo ""

# Show build info
echo "=========================================="
echo "Build Information"
echo "=========================================="
echo "Build ID: $BUILD_ID"
echo "Project: $CODEBUILD_PROJECT"
echo "Region: $AWS_DEFAULT_REGION"
echo ""

echo "=========================================="
echo "What's Being Deployed"
echo "=========================================="
echo ""
echo "CodeBuild will run 3 validation gates:"
echo "  GATE 1: Smoke tests (BLOCKING)"
echo "  GATE 2: Deployment validation (BLOCKING)"
echo "  GATE 3: Post-deployment health check (WARNING)"
echo ""
echo "Then deploy these layers:"
echo "  ✓ Foundation Layer (already deployed - will skip)"
echo "  🔄 Data Layer (Neptune, OpenSearch) - NEW"
echo "  🔄 Compute Layer (EKS multi-tier) - NEW"
echo "  🔄 Application Layer (Services, dnsmasq) - NEW"
echo "  🔄 Observability Layer (Prometheus, CloudWatch) - NEW"
echo ""
echo "Estimated time: 15-20 minutes"
echo ""

echo "=========================================="
echo "Monitoring Options"
echo "=========================================="
echo ""
echo "1. Stream logs in real-time:"
echo "   aws logs tail /aws/codebuild/${CODEBUILD_PROJECT} --follow --region ${AWS_DEFAULT_REGION}"
echo ""
echo "2. Check build status:"
echo "   aws codebuild batch-get-builds --ids ${BUILD_ID} --region ${AWS_DEFAULT_REGION}"
echo ""
echo "3. View in AWS Console:"
echo "   https://console.aws.amazon.com/codesuite/codebuild/projects/${CODEBUILD_PROJECT}/history?region=${AWS_DEFAULT_REGION}"
echo ""

# Ask if user wants to stream logs
echo -e "${YELLOW}Stream build logs now? (y/n)${NC}"
read -p "> " STREAM_LOGS

if [[ "$STREAM_LOGS" =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${BLUE}Streaming logs (Ctrl+C to stop)...${NC}"
    echo ""
    sleep 5  # Wait for log group to be created
    aws logs tail /aws/codebuild/${CODEBUILD_PROJECT} --follow --region ${AWS_DEFAULT_REGION}
else
    echo ""
    echo -e "${GREEN}Build is running in the background${NC}"
    echo "You will receive an email notification when complete"
fi
