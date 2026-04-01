#!/bin/bash
# =============================================================================
# Project Aura - Smoke Tests
# =============================================================================
# Quick smoke tests to verify basic functionality after deployment.
#
# Usage:
#   ./smoke-tests.sh [PROJECT_NAME] [ENVIRONMENT] [REGION]
#
# =============================================================================

set -euo pipefail

PROJECT_NAME="${1:-aura}"
ENVIRONMENT="${2:-prod}"
AWS_REGION="${3:-us-east-1}"

# Colors
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

PASSED=0
FAILED=0

test_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED++))
}

test_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED++))
}

echo ""
echo -e "${BLUE}Project Aura - Smoke Tests${NC}"
echo "────────────────────────────────────────"
echo ""

# =============================================================================
# Test 1: AWS Connectivity
# =============================================================================
echo -e "${BLUE}Test 1: AWS Connectivity${NC}"

if aws sts get-caller-identity --region "$AWS_REGION" &>/dev/null; then
    test_pass "AWS credentials valid"
else
    test_fail "AWS credentials invalid"
fi

# =============================================================================
# Test 2: EKS Cluster Accessible
# =============================================================================
echo -e "${BLUE}Test 2: EKS Cluster${NC}"

CLUSTER_NAME="${PROJECT_NAME}-cluster-${ENVIRONMENT}"
CLUSTER_STATUS=$(aws eks describe-cluster \
    --name "$CLUSTER_NAME" \
    --query 'cluster.status' \
    --output text \
    --region "$AWS_REGION" 2>/dev/null || echo "NOT_FOUND")

if [[ "$CLUSTER_STATUS" == "ACTIVE" ]]; then
    test_pass "EKS cluster is ACTIVE"
else
    test_fail "EKS cluster status: $CLUSTER_STATUS"
fi

# =============================================================================
# Test 3: Neptune Connectivity
# =============================================================================
echo -e "${BLUE}Test 3: Neptune Database${NC}"

NEPTUNE_ID="${PROJECT_NAME}-neptune-${ENVIRONMENT}"
NEPTUNE_STATUS=$(aws neptune describe-db-clusters \
    --db-cluster-identifier "$NEPTUNE_ID" \
    --query 'DBClusters[0].Status' \
    --output text \
    --region "$AWS_REGION" 2>/dev/null || echo "NOT_FOUND")

if [[ "$NEPTUNE_STATUS" == "available" ]]; then
    test_pass "Neptune cluster is available"
else
    test_fail "Neptune status: $NEPTUNE_STATUS"
fi

# =============================================================================
# Test 4: OpenSearch Domain
# =============================================================================
echo -e "${BLUE}Test 4: OpenSearch Domain${NC}"

OPENSEARCH_DOMAIN="${PROJECT_NAME}-${ENVIRONMENT}"
OPENSEARCH_PROCESSING=$(aws opensearch describe-domain \
    --domain-name "$OPENSEARCH_DOMAIN" \
    --query 'DomainStatus.Processing' \
    --output text \
    --region "$AWS_REGION" 2>/dev/null || echo "ERROR")

if [[ "$OPENSEARCH_PROCESSING" == "False" || "$OPENSEARCH_PROCESSING" == "false" ]]; then
    test_pass "OpenSearch domain is ready"
elif [[ "$OPENSEARCH_PROCESSING" == "ERROR" ]]; then
    test_fail "OpenSearch domain not found"
else
    test_fail "OpenSearch domain still processing"
fi

# =============================================================================
# Test 5: S3 Buckets
# =============================================================================
echo -e "${BLUE}Test 5: S3 Buckets${NC}"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ARTIFACTS_BUCKET="${PROJECT_NAME}-artifacts-${ACCOUNT_ID}-${ENVIRONMENT}"

if aws s3api head-bucket --bucket "$ARTIFACTS_BUCKET" 2>/dev/null; then
    test_pass "Artifacts bucket exists"
else
    test_fail "Artifacts bucket not found"
fi

# =============================================================================
# Test 6: Bedrock Access
# =============================================================================
echo -e "${BLUE}Test 6: Bedrock Access${NC}"

if aws bedrock list-foundation-models \
    --region "$AWS_REGION" \
    --query 'modelSummaries[0].modelId' \
    --output text &>/dev/null; then
    test_pass "Bedrock API accessible"
else
    test_fail "Bedrock API not accessible"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "────────────────────────────────────────"
echo -e "Results: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC}"
echo ""

if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}All smoke tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some smoke tests failed.${NC}"
    exit 1
fi
