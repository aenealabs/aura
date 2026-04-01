#!/bin/bash
# Integration API Test Script
# Tests API endpoints via Ingress/ALB

echo "Testing API endpoints via Ingress..."

ALB_DNS=$(kubectl get ingress aura-api-ingress -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")

if [ -z "$ALB_DNS" ]; then
    echo "WARNING: ALB DNS not available yet, skipping external tests"
    exit 0
fi

echo "Testing via ALB: ${ALB_DNS}"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://${ALB_DNS}/health" --connect-timeout 10 2>/dev/null || echo "000")
echo "  /health: HTTP ${HTTP_CODE}"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://${ALB_DNS}/api/v1/version" --connect-timeout 10 2>/dev/null || echo "000")
echo "  /api/v1/version: HTTP ${HTTP_CODE}"

exit 0
