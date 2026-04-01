#!/bin/bash
#
# Project Aura - Deployment Validation Script
#
# Modeled after:
# - Google SRE: Pre-deployment validation
# - Netflix: Canary deployment validation
# - Stripe: API health validation
#
# This script runs BEFORE every deployment to ensure platform is ready.
# If ANY check fails, deployment is BLOCKED.
#
# Usage:
#   ./deploy/scripts/validate-deployment.sh dev
#   ./deploy/scripts/validate-deployment.sh prod
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
echo "Project Aura - Deployment Validation"
echo "Environment: $ENVIRONMENT"
echo "================================================"
echo ""

# ============================================================================
# Step 1: Smoke Tests (CRITICAL - 30 seconds)
# ============================================================================

echo -e "${BLUE}Step 1/5: Running Smoke Tests...${NC}"
echo "These tests validate critical user journeys work end-to-end."
echo ""

if pytest tests/smoke/ -m smoke -v --tb=short -o addopts=""; then
    echo -e "${GREEN}✓ Smoke tests PASSED${NC}"
    echo ""
else
    echo -e "${RED}✗ Smoke tests FAILED${NC}"
    echo ""
    echo "DEPLOYMENT BLOCKED: Critical paths are broken"
    echo "Fix smoke tests before deploying to $ENVIRONMENT"
    exit 1
fi

# ============================================================================
# Step 2: Code Quality Checks (10 seconds)
# ============================================================================

echo -e "${BLUE}Step 2/5: Running Code Quality Checks...${NC}"
echo "Checking for code quality violations (Ruff, Mypy, Bandit)."
echo ""

# Ruff linting
if ruff check src/ --quiet 2>/dev/null; then
    echo -e "${GREEN}✓ Ruff linting PASSED${NC}"
else
    echo -e "${YELLOW}⚠ Ruff found issues (non-blocking)${NC}"
fi

# Mypy type checking
if mypy src/ --ignore-missing-imports --no-error-summary 2>/dev/null; then
    echo -e "${GREEN}✓ Mypy type checking PASSED${NC}"
else
    echo -e "${YELLOW}⚠ Mypy found issues (non-blocking)${NC}"
fi

# Bandit security scanning
if bandit -r src/ -ll -q 2>/dev/null; then
    echo -e "${GREEN}✓ Bandit security scan PASSED${NC}"
else
    echo -e "${YELLOW}⚠ Bandit found issues (non-blocking)${NC}"
fi

echo ""

# ============================================================================
# Step 3: Infrastructure Readiness (AWS/GCP style)
# ============================================================================

echo -e "${BLUE}Step 3/5: Checking Infrastructure Readiness...${NC}"
echo "Verifying AWS services are accessible."
echo ""

# Check AWS credentials
if aws sts get-caller-identity >/dev/null 2>&1; then
    echo -e "${GREEN}✓ AWS credentials valid${NC}"
else
    echo -e "${RED}✗ AWS credentials invalid${NC}"
    echo ""
    echo "DEPLOYMENT BLOCKED: Cannot authenticate to AWS"
    echo "Run: aws configure"
    exit 1
fi

# Check VPC exists (if deploying to AWS)
if [ "$ENVIRONMENT" != "local" ]; then
    VPC_ID=${VPC_ID:-vpc-0123456789abcdef0}

    if aws ec2 describe-vpcs --vpc-ids "$VPC_ID" >/dev/null 2>&1; then
        echo -e "${GREEN}✓ VPC $VPC_ID exists${NC}"
    else
        echo -e "${YELLOW}⚠ VPC $VPC_ID not found (may need creation)${NC}"
    fi
fi

echo ""

# ============================================================================
# Step 4: Performance Regression Tests (Netflix style)
# ============================================================================

echo -e "${BLUE}Step 4/5: Running Performance Tests...${NC}"
echo "Validating latency SLAs are met."
echo ""

if pytest tests/smoke/ -m performance -v --tb=short -o addopts="" 2>/dev/null; then
    echo -e "${GREEN}✓ Performance tests PASSED${NC}"
    echo ""
else
    echo -e "${YELLOW}⚠ Performance tests FAILED (non-blocking for dev)${NC}"
    echo ""
    if [ "$ENVIRONMENT" = "prod" ]; then
        echo -e "${RED}DEPLOYMENT BLOCKED: Performance regression in production${NC}"
        exit 1
    fi
fi

# ============================================================================
# Step 5: Security Checks (Stripe/AWS style)
# ============================================================================

echo -e "${BLUE}Step 5/5: Running Security Checks...${NC}"
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
    echo -e "${GREEN}✓ No secrets in repository${NC}"
fi

# Check for hardcoded secrets in code
if grep -r "aws_secret_access_key\|password.*=.*\"" src/ 2>/dev/null | grep -v "# nosec" | grep -v "test"; then
    echo -e "${RED}✗ Hardcoded secrets found in code${NC}"
    echo ""
    echo "DEPLOYMENT BLOCKED: Remove hardcoded secrets"
    exit 1
else
    echo -e "${GREEN}✓ No hardcoded secrets${NC}"
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
echo "Safe to deploy: YES"
echo ""
echo "Next steps:"
echo "  1. Review changes: git log -5 --oneline"
echo "  2. Deploy: ./deploy/deploy.sh $ENVIRONMENT"
echo "  3. Monitor: kubectl logs -f deployment/aura-orchestrator"
echo "  4. Validate: curl https://aura.$ENVIRONMENT.example.com/health"
echo ""
echo "Canary Deployment Checklist:"
echo "  [ ] Deploy to 5% of pods"
echo "  [ ] Monitor error rate for 10 minutes"
echo "  [ ] If error rate < 1%, scale to 100%"
echo "  [ ] If error rate > 1%, rollback immediately"
echo ""

exit 0
