#!/bin/bash
# =============================================================================
# Project Aura - Connectivity Tests
# =============================================================================
# Tests connectivity between Aura services and data stores.
# Run from within the EKS cluster (kubectl exec or pod).
#
# Usage:
#   ./connectivity-tests.sh [ENVIRONMENT]
#
# =============================================================================

set -euo pipefail

ENVIRONMENT="${1:-prod}"

# Colors
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

PASSED=0
FAILED=0

test_connection() {
    local name=$1
    local host=$2
    local port=$3
    local timeout=${4:-5}

    echo -n "Testing $name ($host:$port)... "

    if timeout "$timeout" bash -c "echo > /dev/tcp/$host/$port" 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAILED${NC}"
        ((FAILED++))
    fi
}

test_http() {
    local name=$1
    local url=$2
    local expected=${3:-200}
    local timeout=${4:-5}

    echo -n "Testing $name ($url)... "

    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$timeout" "$url" 2>/dev/null || echo "000")

    if [[ "$status" == "$expected" ]]; then
        echo -e "${GREEN}OK (HTTP $status)${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAILED (HTTP $status)${NC}"
        ((FAILED++))
    fi
}

echo ""
echo -e "${BLUE}Project Aura - Connectivity Tests${NC}"
echo "────────────────────────────────────────"
echo "Environment: $ENVIRONMENT"
echo ""

# Get endpoints from environment or SSM
echo -e "${BLUE}Retrieving endpoints...${NC}"
echo ""

# Neptune endpoint
NEPTUNE_ENDPOINT=${NEPTUNE_ENDPOINT:-$(aws ssm get-parameter \
    --name "/aura/${ENVIRONMENT}/neptune-endpoint" \
    --query 'Parameter.Value' \
    --output text 2>/dev/null || echo "neptune.aura.local")}

# OpenSearch endpoint
OPENSEARCH_ENDPOINT=${OPENSEARCH_ENDPOINT:-$(aws ssm get-parameter \
    --name "/aura/${ENVIRONMENT}/opensearch-endpoint" \
    --query 'Parameter.Value' \
    --output text 2>/dev/null || echo "opensearch.aura.local")}

# =============================================================================
# Data Store Connectivity
# =============================================================================
echo -e "${BLUE}Data Store Connectivity${NC}"
echo ""

# Neptune (Gremlin WebSocket)
test_connection "Neptune" "$NEPTUNE_ENDPOINT" 8182

# OpenSearch (HTTPS)
test_connection "OpenSearch" "$OPENSEARCH_ENDPOINT" 443

# DynamoDB (via VPC endpoint)
test_connection "DynamoDB VPC Endpoint" "dynamodb.us-east-1.amazonaws.com" 443

# =============================================================================
# AWS Service Connectivity (via VPC Endpoints)
# =============================================================================
echo ""
echo -e "${BLUE}AWS Service Connectivity${NC}"
echo ""

# S3 (via VPC endpoint)
test_connection "S3 VPC Endpoint" "s3.us-east-1.amazonaws.com" 443

# ECR API
test_connection "ECR API" "api.ecr.us-east-1.amazonaws.com" 443

# Secrets Manager
test_connection "Secrets Manager" "secretsmanager.us-east-1.amazonaws.com" 443

# CloudWatch Logs
test_connection "CloudWatch Logs" "logs.us-east-1.amazonaws.com" 443

# Bedrock
test_connection "Bedrock Runtime" "bedrock-runtime.us-east-1.amazonaws.com" 443

# =============================================================================
# Internal Service Connectivity
# =============================================================================
echo ""
echo -e "${BLUE}Internal Service Connectivity${NC}"
echo ""

# These would be tested from within the cluster
if [[ -n "${KUBERNETES_SERVICE_HOST:-}" ]]; then
    # Running inside cluster
    test_connection "Kubernetes API" "$KUBERNETES_SERVICE_HOST" "$KUBERNETES_SERVICE_PORT"

    # Test internal DNS
    if host "aura-api.aura.svc.cluster.local" &>/dev/null; then
        echo -e "${GREEN}OK${NC} Internal DNS resolution working"
        ((PASSED++))
    else
        echo -e "${YELLOW}SKIP${NC} Internal DNS (services may not be deployed)"
    fi
else
    echo -e "${YELLOW}SKIP${NC} Internal services (not running in cluster)"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "────────────────────────────────────────"
echo -e "Results: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC}"
echo ""

if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}All connectivity tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some connectivity tests failed.${NC}"
    echo ""
    echo "Troubleshooting tips:"
    echo "  - Check VPC endpoint configuration"
    echo "  - Verify security group rules"
    echo "  - Ensure services are running"
    echo "  - Check DNS resolution"
    exit 1
fi
