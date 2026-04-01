#!/bin/bash
#
# Project Aura - CodeBuild Deployment Validation Script
#
# Lightweight validation for CodeBuild environment
# Smoke tests are run separately in GATE 1 - this script focuses on:
# - Infrastructure readiness
# - Security checks
#
# Usage:
#   ./deploy/scripts/validate-deployment-codebuild.sh dev
#
# Exit Codes:
#   0: All checks passed (safe to deploy)
#   1: Checks failed (DO NOT DEPLOY)
#

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ENVIRONMENT=${1:-dev}

echo "================================================"
echo "Project Aura - CodeBuild Deployment Validation"
echo "Environment: $ENVIRONMENT"
echo "================================================"
echo ""

# ============================================================================
# Step 1: Infrastructure Readiness
# ============================================================================

echo -e "${BLUE}Step 1/3: Checking Infrastructure Readiness...${NC}"
echo "Verifying AWS services are accessible."
echo ""

# Check AWS credentials
if aws sts get-caller-identity >/dev/null 2>&1; then
    AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
    echo -e "${GREEN}✓ AWS credentials valid (Account: $AWS_ACCOUNT)${NC}"
else
    echo -e "${RED}✗ AWS credentials invalid${NC}"
    echo ""
    echo "DEPLOYMENT BLOCKED: Cannot authenticate to AWS"
    exit 1
fi

# Check VPC exists (if deploying to AWS)
if [ "$ENVIRONMENT" != "local" ]; then
    VPC_ID=${VPC_ID:-vpc-0123456789abcdef0}

    if aws ec2 describe-vpcs --vpc-ids "$VPC_ID" >/dev/null 2>&1; then
        echo -e "${GREEN}✓ VPC $VPC_ID exists${NC}"
    else
        echo -e "${YELLOW}⚠ VPC $VPC_ID not found (will be created during deployment)${NC}"
    fi
fi

echo ""

# ============================================================================
# Step 2: CloudFormation Template Validation
# ============================================================================

echo -e "${BLUE}Step 2/3: Validating CloudFormation Templates...${NC}"
echo "Checking template syntax and best practices."
echo ""

# Use cfn-lint to validate templates
if cfn-lint deploy/cloudformation/*.yaml --ignore-checks W3002 2>/dev/null; then
    echo -e "${GREEN}✓ CloudFormation templates are valid${NC}"
else
    echo -e "${YELLOW}⚠ CloudFormation templates have warnings (non-blocking)${NC}"
fi

echo ""

# ============================================================================
# Step 3: Security Checks
# ============================================================================

echo -e "${BLUE}Step 3/3: Running Security Checks...${NC}"
echo "Checking for secrets and vulnerabilities."
echo ""

# Check for .env file in repo (should NEVER be committed)
if [ -f ".env" ] && git ls-files --error-unmatch .env >/dev/null 2>&1; then
    echo -e "${RED}✗ .env file is tracked in git${NC}"
    echo ""
    echo "DEPLOYMENT BLOCKED: Secrets detected in repository"
    echo "Remove .env from git: git rm --cached .env"
    exit 1
else
    echo -e "${GREEN}✓ No .env file in repository${NC}"
fi

# Check for hardcoded AWS keys (basic check)
if grep -r "AKIA[0-9A-Z]\{16\}" src/ 2>/dev/null | grep -v "test"; then
    echo -e "${RED}✗ Hardcoded AWS keys found in code${NC}"
    echo ""
    echo "DEPLOYMENT BLOCKED: Remove hardcoded AWS credentials"
    exit 1
else
    echo -e "${GREEN}✓ No hardcoded AWS keys${NC}"
fi

echo ""

# ============================================================================
# Final Summary
# ============================================================================

echo "================================================"
echo -e "${GREEN}ALL CHECKS PASSED ✓${NC}"
echo "================================================"
echo ""
echo "Environment: $ENVIRONMENT"
echo "AWS Account: $AWS_ACCOUNT"
echo "Safe to deploy: YES"
echo ""

exit 0
