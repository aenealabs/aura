#!/bin/bash
# Integration Health Check Script
# Checks health endpoints for all Aura services

set -e

# Services with persistent Deployments and Services to health check
# Note: meta-orchestrator is a Job template (created by Lambda), not a Deployment
SERVICES="aura-api agent-orchestrator memory-service aura-frontend"
TOTAL_SERVICES=4
HEALTH_FAILURES=0
MAX_RETRIES=3
INITIAL_WAIT=2

echo "Testing service health endpoints..."

for svc in $SERVICES; do
    echo "Checking ${svc}..."

    SVC_IP=$(kubectl get svc ${svc} -o jsonpath='{.spec.clusterIP}' 2>/dev/null || echo "")

    if [ -z "$SVC_IP" ]; then
        echo "  WARNING: Service ${svc} not found"
        continue
    fi

    # Get the health port - try named port "health" or "http" first, then fall back to first port
    # memory-service has multiple ports: grpc(50051), health(8080), metrics(9090)
    SVC_PORT=$(kubectl get svc ${svc} -o jsonpath='{.spec.ports[?(@.name=="health")].port}' 2>/dev/null)
    if [ -z "$SVC_PORT" ]; then
        SVC_PORT=$(kubectl get svc ${svc} -o jsonpath='{.spec.ports[?(@.name=="http")].port}' 2>/dev/null)
    fi
    if [ -z "$SVC_PORT" ]; then
        SVC_PORT=$(kubectl get svc ${svc} -o jsonpath='{.spec.ports[0].port}' 2>/dev/null || echo "8080")
    fi

    kubectl port-forward svc/${svc} 8080:${SVC_PORT} &
    PF_PID=$!
    sleep ${INITIAL_WAIT}

    # Retry logic for transient port-forward timing issues
    HTTP_CODE="000"
    for attempt in $(seq 1 ${MAX_RETRIES}); do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://localhost:8080/health 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ]; then
            break
        fi
        if [ "$attempt" -lt "${MAX_RETRIES}" ]; then
            echo "  Retry ${attempt}/${MAX_RETRIES} for ${svc}..."
            sleep 2
        fi
    done

    kill $PF_PID 2>/dev/null || true
    wait $PF_PID 2>/dev/null || true

    if [ "$HTTP_CODE" = "200" ]; then
        echo "  OK: ${svc} healthy (HTTP ${HTTP_CODE})"
    else
        echo "  FAIL: ${svc} unhealthy (HTTP ${HTTP_CODE})"
        HEALTH_FAILURES=$((HEALTH_FAILURES + 1))
    fi
done

echo ""
echo "Health check results: $((TOTAL_SERVICES - HEALTH_FAILURES))/${TOTAL_SERVICES} services healthy"

if [ "$HEALTH_FAILURES" -gt 2 ]; then
    echo "ERROR: Too many health check failures"
    exit 1
fi

exit 0
