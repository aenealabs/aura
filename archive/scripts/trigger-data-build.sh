#!/bin/bash
# Quick script to trigger Data Layer build

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

export AWS_PROFILE=${AWS_PROFILE:-}
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}

ENVIRONMENT=${1:-dev}
PROJECT_NAME="aura"
CODEBUILD_PROJECT="${PROJECT_NAME}-data-deploy-${ENVIRONMENT}"

echo "=========================================="
echo "Data Layer Build Trigger"
echo "=========================================="
echo "Project: $CODEBUILD_PROJECT"
echo ""

if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo -e "${YELLOW}AWS credentials not found${NC}"
    exit 1
fi

if ! aws codebuild batch-get-projects --names $CODEBUILD_PROJECT --region $AWS_DEFAULT_REGION >/dev/null 2>&1; then
    echo -e "${YELLOW}CodeBuild project not found: $CODEBUILD_PROJECT${NC}"
    echo "Deploy Data CodeBuild first: ./deploy-data-codebuild.sh"
    exit 1
fi

echo -e "${BLUE}Triggering build...${NC}"
BUILD_ID=$(aws codebuild start-build \
    --project-name $CODEBUILD_PROJECT \
    --region $AWS_DEFAULT_REGION \
    --query 'build.id' \
    --output text)

echo -e "${GREEN}✓ Build started: $BUILD_ID${NC}"
echo ""
echo "Monitor: aws logs tail /aws/codebuild/${CODEBUILD_PROJECT} --follow --region ${AWS_DEFAULT_REGION}"
echo ""

echo -e "${YELLOW}Stream logs now? (y/n)${NC}"
read -p "> " STREAM_LOGS

if [[ "$STREAM_LOGS" =~ ^[Yy]$ ]]; then
    sleep 3
    aws logs tail /aws/codebuild/${CODEBUILD_PROJECT} --follow --region ${AWS_DEFAULT_REGION}
fi
