#!/bin/bash
# =============================================================================
# Project Aura - Service Health Checks
# =============================================================================
# Health check endpoints for all Aura services.
# Requires kubectl configured and Aura applications deployed.
#
# Usage:
#   ./health-checks.sh [NAMESPACE]
#
# =============================================================================

set -euo pipefail

NAMESPACE="${1:-aura}"

# Colors
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

HEALTHY=0
UNHEALTHY=0

check_service() {
    local name=$1
    local port=$2
    local path=${3:-/health}

    # Port-forward in background
    kubectl port-forward "svc/$name" "$port:$port" -n "$NAMESPACE" &>/dev/null &
    local pid=$!
    sleep 2

    # Check health endpoint
    local response
    response=$(curl -s --max-time 5 "http://localhost:$port$path" 2>/dev/null || echo "FAILED")

    # Kill port-forward
    kill $pid 2>/dev/null || true

    if [[ "$response" == *"healthy"* ]] || [[ "$response" == *"ok"* ]] || [[ "$response" == *"status"*":"*"UP"* ]]; then
        echo -e "${GREEN}[HEALTHY]${NC} $name"
        ((HEALTHY++))
    elif [[ "$response" == "FAILED" ]]; then
        echo -e "${RED}[DOWN]${NC} $name - service not reachable"
        ((UNHEALTHY++))
    else
        echo -e "${YELLOW}[UNKNOWN]${NC} $name - response: ${response:0:50}..."
        ((UNHEALTHY++))
    fi
}

echo ""
echo -e "${BLUE}Project Aura - Service Health Checks${NC}"
echo "────────────────────────────────────────"
echo "Namespace: $NAMESPACE"
echo ""

# Check if kubectl is available
if ! command -v kubectl &>/dev/null; then
    echo -e "${RED}kubectl not found. Please install kubectl and configure cluster access.${NC}"
    exit 1
fi

# Check if namespace exists
if ! kubectl get namespace "$NAMESPACE" &>/dev/null; then
    echo -e "${YELLOW}Namespace $NAMESPACE not found.${NC}"
    echo "Create it with: kubectl create namespace $NAMESPACE"
    exit 1
fi

# List services
echo -e "${BLUE}Checking services in namespace $NAMESPACE...${NC}"
echo ""

SERVICES=$(kubectl get svc -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")

if [[ -z "$SERVICES" ]]; then
    echo -e "${YELLOW}No services found in namespace $NAMESPACE.${NC}"
    echo "Deploy Aura applications first."
    exit 0
fi

# Check each service that has a health endpoint
for svc in $SERVICES; do
    case "$svc" in
        *api*|*orchestrator*|*context*|*agent*)
            PORT=$(kubectl get svc "$svc" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].port}')
            check_service "$svc" "$PORT" "/health"
            ;;
        *frontend*)
            PORT=$(kubectl get svc "$svc" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].port}')
            check_service "$svc" "$PORT" "/"
            ;;
        *)
            echo -e "${BLUE}[SKIP]${NC} $svc - no health check defined"
            ;;
    esac
done

# Summary
echo ""
echo "────────────────────────────────────────"
echo -e "Results: ${GREEN}$HEALTHY healthy${NC}, ${RED}$UNHEALTHY unhealthy${NC}"
echo ""

if [[ $UNHEALTHY -eq 0 ]]; then
    echo -e "${GREEN}All services are healthy!${NC}"
    exit 0
else
    echo -e "${YELLOW}Some services are unhealthy. Check logs for details.${NC}"
    exit 1
fi
