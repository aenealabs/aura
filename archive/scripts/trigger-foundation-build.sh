#!/bin/bash
#
# Quick script to trigger Foundation Layer build
#

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Set AWS profile and region
export AWS_PROFILE=${AWS_PROFILE:-}
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}

ENVIRONMENT=${1:-dev}
PROJECT_NAME="aura"
CODEBUILD_PROJECT="${PROJECT_NAME}-foundation-deploy-${ENVIRONMENT}"

echo "=========================================="
echo "Foundation Layer Build Trigger"
echo "=========================================="
echo "Project: $CODEBUILD_PROJECT"
echo "Region: $AWS_DEFAULT_REGION"
echo ""

# Verify credentials
if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo -e "${YELLOW}AWS credentials not found or expired${NC}"
    echo "Please set AWS_PROFILE or run: aws sso login"
    exit 1
fi

# Check if project exists
if ! aws codebuild batch-get-projects --names $CODEBUILD_PROJECT --region $AWS_DEFAULT_REGION >/dev/null 2>&1; then
    echo -e "${YELLOW}CodeBuild project not found: $CODEBUILD_PROJECT${NC}"
    echo ""
    echo "Deploy Foundation CodeBuild first:"
    echo "  ./deploy-foundation-codebuild.sh"
    exit 1
fi

# Trigger build
echo -e "${BLUE}Triggering build...${NC}"
BUILD_ID=$(aws codebuild start-build \
    --project-name $CODEBUILD_PROJECT \
    --region $AWS_DEFAULT_REGION \
    --query 'build.id' \
    --output text)

echo -e "${GREEN}✓ Build started: $BUILD_ID${NC}"
echo ""
echo "Monitor with:"
echo "  aws logs tail /aws/codebuild/${CODEBUILD_PROJECT} --follow --region ${AWS_DEFAULT_REGION}"
echo ""

# Ask if user wants to stream logs
echo -e "${YELLOW}Stream build logs now? (y/n)${NC}"
read -p "> " STREAM_LOGS

if [[ "$STREAM_LOGS" =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${BLUE}Streaming logs (Ctrl+C to stop)...${NC}"
    echo ""
    sleep 3
    aws logs tail /aws/codebuild/${CODEBUILD_PROJECT} --follow --region ${AWS_DEFAULT_REGION}
fi
