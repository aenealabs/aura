# Performance Issues

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This document covers performance-related issues including slow response times, high resource utilization, database bottlenecks, and scaling problems. Use this guide when the system is slower than expected or experiencing resource constraints.

---

## Performance Baseline

### Expected Response Times

| Operation | Target Latency | Maximum Acceptable |
|-----------|----------------|-------------------|
| API health check | <50ms | 200ms |
| Repository list | <200ms | 1s |
| Vulnerability query | <500ms | 2s |
| Context retrieval (GraphRAG) | <200ms | 500ms |
| Patch generation (simple) | <30s | 2min |
| Patch generation (complex) | <2min | 10min |
| Sandbox test execution | <5min | 15min |

### Resource Utilization Targets

| Component | CPU Target | CPU Alert | Memory Target | Memory Alert |
|-----------|------------|-----------|---------------|--------------|
| API pods | <60% | >80% | <70% | >85% |
| Agent pods | <70% | >90% | <60% | >80% |
| Neptune | <60% | >80% | <70% | >85% |
| OpenSearch | <70% | >85% | <75% | >90% |

---

## API Response Time Issues

### AURA-PERF-001: Slow API Responses

**Symptoms:**
- API requests take longer than expected
- Timeouts on client side
- Dashboard loads slowly

**Diagnostic Steps:**

```bash
# Measure API response time
time curl -s -o /dev/null -w "%{time_total}\n" \
  -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/health

# Check API latency metrics
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/metrics | jq '.api_latency_p99'

# Self-hosted: Check pod resource usage
kubectl top pods -n aura-system -l app=aura-api

# Check for throttling
kubectl logs -n aura-system -l app=aura-api --tail=100 | grep -i throttl
```

**Performance Profiling:**

```bash
# Enable debug timing headers (if supported)
curl -v -H "Authorization: Bearer ${AURA_TOKEN}" \
  -H "X-Debug-Timing: true" \
  https://api.aenealabs.com/v1/repositories | head -50

# Example timing headers:
# X-Timing-Auth: 5ms
# X-Timing-DB: 45ms
# X-Timing-Cache: 2ms
# X-Timing-Total: 62ms
```

**Resolution by Bottleneck:**

**1. Database Queries Slow:**

```bash
# Check Neptune query performance
aws neptune describe-db-cluster-endpoints \
  --db-cluster-identifier aura-neptune-cluster-${ENV}

# Enable slow query logging (self-hosted)
kubectl patch configmap aura-api-config -n aura-system \
  --type merge -p '{"data":{"SLOW_QUERY_THRESHOLD_MS":"100"}}'
```

**2. Cache Misses:**

```bash
# Check Redis cache hit rate (if Redis is used)
kubectl exec -n aura-system redis-0 -- redis-cli INFO stats | grep hit

# Warm up cache for frequently accessed data
curl -X POST -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/cache/warm
```

**3. Resource Constraints:**

```bash
# Scale API pods horizontally
kubectl scale deployment/aura-api -n aura-system --replicas=5

# Increase pod resources
kubectl patch deployment aura-api -n aura-system --type=json \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "1000m"}]'
```

---

### AURA-PERF-002: High API Error Rate

**Symptoms:**
- 5xx errors increasing
- Error rate exceeds SLA threshold (>0.1%)
- Intermittent failures

**Diagnostic Steps:**

```bash
# Check error rate from metrics
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/metrics | jq '.error_rate_5xx'

# Self-hosted: Count errors in logs
kubectl logs -n aura-system -l app=aura-api --since=1h | \
  grep -c "HTTP/1.1 5[0-9][0-9]"

# Check for specific error patterns
kubectl logs -n aura-system -l app=aura-api --since=1h | \
  grep "ERROR" | cut -d' ' -f5- | sort | uniq -c | sort -rn | head
```

**Resolution:**

```bash
# Identify and fix upstream dependency issues
kubectl logs -n aura-system -l app=aura-api --since=1h | \
  grep -E "(timeout|connection refused|ECONNRESET)"

# Implement circuit breaker pattern (configuration)
kubectl patch configmap aura-api-config -n aura-system \
  --type merge -p '{"data":{"CIRCUIT_BREAKER_ENABLED":"true","CIRCUIT_BREAKER_THRESHOLD":"5"}}'

# Add retry logic with backoff
kubectl patch configmap aura-api-config -n aura-system \
  --type merge -p '{"data":{"RETRY_ATTEMPTS":"3","RETRY_BACKOFF_MS":"1000"}}'
```

---

## Agent Performance Issues

### AURA-PERF-003: Slow Patch Generation

**Symptoms:**
- Coder Agent takes longer than expected
- Patch generation timeouts
- Queue of pending patches growing

**Performance Factors:**

| Factor | Impact | Mitigation |
|--------|--------|------------|
| Codebase size | Linear | Scope to affected files |
| Vulnerability complexity | Variable | Break into smaller patches |
| LLM response time | ~5-30s per call | Use caching, batch prompts |
| Context retrieval | ~100-500ms | Optimize GraphRAG queries |
| Dependency graph depth | Polynomial | Limit traversal depth |

**Diagnostic Steps:**

```bash
# Check Coder Agent performance metrics
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/agents/coder/metrics | jq

# Example output:
{
  "avg_generation_time_ms": 45000,
  "p95_generation_time_ms": 120000,
  "llm_call_count_avg": 3.2,
  "context_retrieval_time_ms": 250,
  "pending_requests": 5
}

# Self-hosted: Check agent resource usage
kubectl top pods -n aura-system -l app=coder-agent

# Check for LLM throttling
kubectl logs -n aura-system -l app=coder-agent --since=1h | \
  grep -i "rate limit\|throttl"
```

**Resolution:**

**1. Optimize Context Retrieval:**

```bash
# Reduce context window size
kubectl patch configmap coder-agent-config -n aura-system \
  --type merge -p '{"data":{"MAX_CONTEXT_TOKENS":"8000"}}'

# Enable context caching
kubectl patch configmap coder-agent-config -n aura-system \
  --type merge -p '{"data":{"CONTEXT_CACHE_ENABLED":"true","CONTEXT_CACHE_TTL_SECONDS":"300"}}'
```

**2. Increase LLM Throughput:**

```bash
# Enable parallel LLM calls (if supported)
kubectl patch configmap coder-agent-config -n aura-system \
  --type merge -p '{"data":{"LLM_PARALLEL_CALLS":"3"}}'

# Use faster model for simple patches
kubectl patch configmap coder-agent-config -n aura-system \
  --type merge -p '{"data":{"SIMPLE_PATCH_MODEL":"anthropic.claude-3-haiku-20240307"}}'
```

**3. Scale Agent Capacity:**

```bash
# Scale Coder Agent replicas
kubectl scale deployment/coder-agent -n aura-system --replicas=3

# Increase agent memory for large codebases
kubectl patch deployment coder-agent -n aura-system --type=json \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "8Gi"}]'
```

---

### AURA-PERF-004: Sandbox Test Delays

**Symptoms:**
- Sandbox provisioning takes too long
- Tests queue up waiting for sandboxes
- Validator Agent timeouts

**Expected Sandbox Lifecycle:**

```
┌────────────────────────────────────────────────────────────────────┐
│                    SANDBOX LIFECYCLE TIMING                         │
└────────────────────────────────────────────────────────────────────┘

Provision    │████████████████│ 30-120s (ECS task launch)
             │
Deploy Code  │████│ 10-30s (copy and configure)
             │
Run Tests    │████████████████████████████│ 1-10min (variable)
             │
Collect      │██│ 5-15s (logs and artifacts)
             │
Teardown     │████│ 10-30s (cleanup)
             │
─────────────┼────┼────┼────┼────┼────┼────┼────┼────┼
             0   30   60   90  120  150  180  210  240  (seconds)
```

**Diagnostic Steps:**

```bash
# Check sandbox provisioning time
curl -s -H "Authorization: Bearer ${AURA_TOKEN}" \
  https://api.aenealabs.com/v1/sandboxes/metrics | jq '.provision_time_p95_seconds'

# Check ECS task launch time
aws ecs describe-tasks \
  --cluster aura-sandbox-cluster-${ENV} \
  --tasks $(aws ecs list-tasks --cluster aura-sandbox-cluster-${ENV} --query 'taskArns[0]' --output text) \
  --query 'tasks[0].[startedAt,stoppedAt,containers[0].exitCode]'

# Check for capacity issues
aws ecs describe-cluster \
  --clusters aura-sandbox-cluster-${ENV} \
  --include ATTACHMENTS,STATISTICS \
  --query 'clusters[0].[pendingTasksCount,runningTasksCount,registeredContainerInstancesCount]'
```

**Resolution:**

**1. Enable Warm Pool:**

```bash
# Pre-provision idle sandbox containers
kubectl patch configmap validator-agent-config -n aura-system \
  --type merge -p '{"data":{"SANDBOX_WARM_POOL_SIZE":"3"}}'
```

**2. Optimize Test Execution:**

```bash
# Run tests in parallel
kubectl patch configmap validator-agent-config -n aura-system \
  --type merge -p '{"data":{"TEST_PARALLEL_WORKERS":"4"}}'

# Skip long-running tests for low-risk patches
kubectl patch configmap validator-agent-config -n aura-system \
  --type merge -p '{"data":{"SKIP_INTEGRATION_TESTS_FOR_LOW_RISK":"true"}}'
```

**3. Increase Sandbox Capacity:**

```bash
# Allow more concurrent sandboxes
aws ecs put-cluster-capacity-providers \
  --cluster aura-sandbox-cluster-${ENV} \
  --capacity-providers FARGATE_SPOT \
  --default-capacity-provider-strategy capacityProvider=FARGATE_SPOT,weight=1,base=0
```

---

## Database Performance Issues

### AURA-PERF-005: Neptune Query Slowdown

**Symptoms:**
- GraphRAG queries taking >500ms
- Graph traversals timing out
- High Neptune CPU utilization

**Diagnostic Steps:**

```bash
# Check Neptune CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Neptune \
  --metric-name CPUUtilization \
  --dimensions Name=DBClusterIdentifier,Value=aura-neptune-cluster-${ENV} \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Average,Maximum

# Enable slow query logging
# (Neptune automatically logs queries >5s to CloudWatch)

# Check query execution plans (via Gremlin console)
# g.V().has('type','function').both().both().profile()
```

**Optimization Strategies:**

**1. Add Graph Indexes:**

```groovy
// Composite index for common query patterns
graph.openManagement()
  .makePropertyKey('type').dataType(String.class).cardinality(SINGLE)
  .makePropertyKey('name').dataType(String.class).cardinality(SINGLE)
  .buildCompositeIndex('byTypeAndName', Vertex.class)
    .addKey('type')
    .addKey('name')
  .buildIndex()
  .commit()
```

**2. Optimize Traversal Depth:**

```bash
# Limit graph traversal depth
kubectl patch configmap context-retrieval-config -n aura-system \
  --type merge -p '{"data":{"MAX_GRAPH_DEPTH":"3","MAX_RESULTS_PER_HOP":"50"}}'
```

**3. Scale Neptune:**

```bash
# Add read replica
aws neptune create-db-instance \
  --db-instance-identifier aura-neptune-reader-${ENV} \
  --db-instance-class db.r5.large \
  --engine neptune \
  --db-cluster-identifier aura-neptune-cluster-${ENV}

# Upgrade instance class
aws neptune modify-db-instance \
  --db-instance-identifier aura-neptune-${ENV} \
  --db-instance-class db.r5.xlarge \
  --apply-immediately
```

---

### AURA-PERF-006: OpenSearch Query Latency

**Symptoms:**
- Vector similarity searches slow
- Semantic search timeouts
- High OpenSearch CPU/memory

**Diagnostic Steps:**

```bash
# Check cluster health
curl -s -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/_cluster/health?pretty"

# Check index statistics
curl -s -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/aura-vectors/_stats?pretty" | \
  jq '.indices["aura-vectors"].primaries.search'

# Check slow query log
curl -s -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/_nodes/stats/indices/search?pretty"

# Get query profile
curl -X POST -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/aura-vectors/_search?pretty" \
  -H "Content-Type: application/json" \
  -d '{
    "profile": true,
    "query": {
      "knn": {
        "embedding": {
          "vector": [0.1, 0.2, ...],
          "k": 10
        }
      }
    }
  }'
```

**Resolution:**

**1. Optimize Index Settings:**

```bash
# Increase refresh interval for write-heavy workloads
curl -X PUT -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/aura-vectors/_settings" \
  -H "Content-Type: application/json" \
  -d '{"index": {"refresh_interval": "30s"}}'

# Force merge to reduce segment count
curl -X POST -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/aura-vectors/_forcemerge?max_num_segments=1"
```

**2. Optimize KNN Parameters:**

```bash
# Adjust KNN algorithm parameters
curl -X PUT -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/aura-vectors/_settings" \
  -H "Content-Type: application/json" \
  -d '{
    "index": {
      "knn.algo_param.ef_search": 100,
      "knn.algo_param.ef_construction": 128
    }
  }'
```

**3. Scale OpenSearch:**

```bash
# Add data nodes
aws opensearch update-domain-config \
  --domain-name aura-opensearch-${ENV} \
  --cluster-config InstanceType=r6g.large.search,InstanceCount=3
```

---

## Memory and Resource Issues

### AURA-PERF-007: Memory Exhaustion (OOMKilled)

**Symptoms:**
- Pods restarting with OOMKilled
- Sudden performance degradation
- Services becoming unresponsive

**Diagnostic Steps:**

```bash
# Check for OOMKilled pods
kubectl get pods -n aura-system -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[0].lastState.terminated.reason}{"\n"}{end}' | grep OOMKilled

# Check current memory usage
kubectl top pods -n aura-system --sort-by=memory

# Check memory limits vs usage
kubectl get pods -n aura-system -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].resources.limits.memory}{"\t"}{.spec.containers[0].resources.requests.memory}{"\n"}{end}'

# Check node memory pressure
kubectl describe nodes | grep -A5 "Allocated resources:"
```

**Memory Requirements by Component:**

| Component | Minimum | Recommended | Large Scale |
|-----------|---------|-------------|-------------|
| API | 512Mi | 1Gi | 2Gi |
| Orchestrator | 1Gi | 2Gi | 4Gi |
| Coder Agent | 2Gi | 4Gi | 8Gi |
| Reviewer Agent | 1Gi | 2Gi | 4Gi |
| Validator Agent | 2Gi | 4Gi | 8Gi |
| Context Retrieval | 1Gi | 2Gi | 4Gi |

**Resolution:**

```bash
# Increase memory limits
kubectl patch deployment ${DEPLOYMENT} -n aura-system --type=json \
  -p='[
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "4Gi"},
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "2Gi"}
  ]'

# Enable memory-efficient processing
kubectl patch configmap ${COMPONENT}-config -n aura-system \
  --type merge -p '{"data":{"STREAMING_ENABLED":"true","BATCH_SIZE":"100"}}'

# Scale horizontally instead of vertically
kubectl scale deployment/${DEPLOYMENT} -n aura-system --replicas=3
```

---

### AURA-PERF-008: CPU Saturation

**Symptoms:**
- High CPU utilization (>90%)
- Request processing delays
- Pod throttling

**Diagnostic Steps:**

```bash
# Check CPU usage
kubectl top pods -n aura-system --sort-by=cpu

# Check for CPU throttling
kubectl exec ${POD_NAME} -n aura-system -- \
  cat /sys/fs/cgroup/cpu/cpu.stat | grep throttled

# Check CPU limits vs requests
kubectl get pods -n aura-system -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].resources.limits.cpu}{"\t"}{.spec.containers[0].resources.requests.cpu}{"\n"}{end}'

# Profile CPU-intensive operations
kubectl exec ${POD_NAME} -n aura-system -- \
  python -m cProfile -s cumtime /app/profiler.py
```

**Resolution:**

```bash
# Increase CPU limits
kubectl patch deployment ${DEPLOYMENT} -n aura-system --type=json \
  -p='[
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "2000m"},
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "1000m"}
  ]'

# Enable horizontal pod autoscaling
kubectl autoscale deployment ${DEPLOYMENT} -n aura-system \
  --cpu-percent=70 --min=2 --max=10

# Offload CPU-intensive work to background jobs
kubectl patch configmap ${COMPONENT}-config -n aura-system \
  --type merge -p '{"data":{"ASYNC_PROCESSING_ENABLED":"true"}}'
```

---

## Network Performance Issues

### AURA-PERF-009: High Network Latency

**Symptoms:**
- Inter-service calls slow
- External API calls timing out
- DNS resolution delays

**Diagnostic Steps:**

```bash
# Measure inter-service latency
kubectl exec ${POD_NAME} -n aura-system -- \
  curl -o /dev/null -s -w "DNS: %{time_namelookup}s\nConnect: %{time_connect}s\nTTFB: %{time_starttransfer}s\nTotal: %{time_total}s\n" \
  http://orchestrator.aura.local:8080/health

# Check network policy impact
kubectl get networkpolicies -n aura-system

# Test external connectivity
kubectl exec ${POD_NAME} -n aura-system -- \
  curl -o /dev/null -s -w "Total: %{time_total}s\n" \
  https://bedrock-runtime.us-east-1.amazonaws.com

# Check for packet loss
kubectl exec ${POD_NAME} -n aura-system -- \
  ping -c 10 orchestrator.aura.local
```

**Resolution:**

```bash
# Enable connection pooling
kubectl patch configmap ${COMPONENT}-config -n aura-system \
  --type merge -p '{"data":{"HTTP_POOL_SIZE":"50","HTTP_KEEP_ALIVE":"true"}}'

# Optimize DNS caching
kubectl patch configmap coredns -n kube-system \
  --type merge -p '{"data":{"Corefile":"...cache 300..."}}'

# Use service mesh for better traffic management (if applicable)
kubectl apply -f istio/virtual-service-retry.yaml
```

---

## Performance Monitoring Quick Reference

### Key Metrics to Monitor

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| API p99 latency | CloudWatch/Prometheus | >2s |
| Error rate (5xx) | CloudWatch/Prometheus | >1% |
| CPU utilization | kubectl top / CloudWatch | >80% |
| Memory utilization | kubectl top / CloudWatch | >85% |
| Neptune CPU | CloudWatch | >80% |
| OpenSearch CPU | CloudWatch | >85% |
| Queue depth | CloudWatch/Prometheus | >100 items |
| LLM token rate | Bedrock metrics | Approaching quota |

### CloudWatch Dashboard Queries

```sql
-- API Latency p99
SELECT AVG(latency)
FROM aura_api_metrics
WHERE timestamp > NOW() - INTERVAL 1 HOUR
GROUP BY time(5m)

-- Error Rate
SELECT COUNT(*) FILTER (WHERE status_code >= 500) * 100.0 / COUNT(*)
FROM aura_api_metrics
WHERE timestamp > NOW() - INTERVAL 1 HOUR
GROUP BY time(5m)

-- Agent Queue Depth
SELECT MAX(queue_depth)
FROM aura_agent_metrics
WHERE agent_name = 'coder'
GROUP BY time(1m)
```

---

## Related Documentation

- [Troubleshooting Index](./index.md)
- [Common Issues](./common-issues.md)
- [Deployment Issues](./deployment-issues.md)
- [Monitoring Guide](../operations/monitoring.md)
- [Scaling Guide](../operations/scaling.md)

---

*Last updated: January 2026 | Version 1.0*
