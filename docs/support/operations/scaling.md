# Scaling Guide

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This guide covers horizontal and vertical scaling strategies for Project Aura, including auto-scaling configuration, capacity planning, and performance optimization techniques.

---

## Scaling Architecture

```
+-----------------------------------------------------------------------------+
|                           SCALING ARCHITECTURE                               |
+-----------------------------------------------------------------------------+

                          LOAD BALANCER (ALB)
                                 |
                 +---------------+---------------+
                 |               |               |
            +----v----+    +----v----+    +----v----+
            |  API    |    |  API    |    |  API    |
            | Pod 1   |    | Pod 2   |    | Pod N   |
            +---------+    +---------+    +---------+
                 |               |               |
    +------------+---------------+---------------+------------+
    |                                                          |
    |                    KUBERNETES CLUSTER                    |
    |   +------------------+  +------------------+             |
    |   | General Node     |  | GPU Node         |             |
    |   | Group (m5.xlarge)|  | Group (g4dn)     |             |
    |   | min: 2, max: 10  |  | min: 0, max: 4   |             |
    |   +------------------+  +------------------+             |
    |                                                          |
    +----------------------------------------------------------+
                 |               |               |
            +----v----+    +----v----+    +----v----+
            | Neptune |    |OpenSearch|   | DynamoDB |
            | r5.large|    | r6g.large|   | On-Demand|
            | (2 nodes)|   | (3 nodes)|   | (Auto)   |
            +---------+    +---------+    +---------+
```

---

## EKS Scaling

### Horizontal Pod Autoscaler (HPA)

HPA automatically scales pods based on CPU/memory utilization or custom metrics.

**Configuration:**

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: aura-api-hpa
  namespace: aura-system
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: aura-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
      - type: Pods
        value: 4
        periodSeconds: 15
      selectPolicy: Max
```

**Deploy HPA:**

```bash
# Apply HPA configuration
kubectl apply -f deploy/kubernetes/aura-api/hpa.yaml

# Check HPA status
kubectl get hpa -n aura-system

# Describe HPA for details
kubectl describe hpa aura-api-hpa -n aura-system
```

**HPA for Agent Services:**

| Service | Min Replicas | Max Replicas | CPU Target | Memory Target |
|---------|--------------|--------------|------------|---------------|
| aura-api | 2 | 10 | 70% | 80% |
| orchestrator | 2 | 5 | 70% | 75% |
| coder-agent | 1 | 5 | 80% | 70% |
| reviewer-agent | 1 | 3 | 80% | 70% |
| validator-agent | 1 | 3 | 75% | 80% |
| context-retrieval | 2 | 6 | 70% | 75% |

### Cluster Autoscaler

Cluster Autoscaler automatically adjusts the number of nodes in a node group.

**Configuration:**

```yaml
# Cluster Autoscaler deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cluster-autoscaler
  namespace: kube-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: cluster-autoscaler
  template:
    spec:
      containers:
      - name: cluster-autoscaler
        image: k8s.gcr.io/autoscaling/cluster-autoscaler:v1.29.0
        command:
        - ./cluster-autoscaler
        - --v=4
        - --stderrthreshold=info
        - --cloud-provider=aws
        - --skip-nodes-with-local-storage=false
        - --expander=least-waste
        - --node-group-auto-discovery=asg:tag=k8s.io/cluster-autoscaler/enabled,k8s.io/cluster-autoscaler/aura-cluster-${ENV}
        - --balance-similar-node-groups
        - --scale-down-enabled=true
        - --scale-down-delay-after-add=10m
        - --scale-down-unneeded-time=10m
```

**Node Group Scaling Limits:**

| Node Group | Instance Type | Min | Max | Labels |
|------------|---------------|-----|-----|--------|
| general | m5.xlarge | 2 | 10 | role=general |
| memory-optimized | r5.xlarge | 0 | 5 | role=memory |
| gpu | g4dn.xlarge | 0 | 4 | role=gpu |

**Manual Scaling Commands:**

```bash
# Scale node group manually (if needed)
aws eks update-nodegroup-config \
  --cluster-name aura-cluster-${ENV} \
  --nodegroup-name aura-general-${ENV} \
  --scaling-config minSize=2,maxSize=10,desiredSize=4

# Check node group status
aws eks describe-nodegroup \
  --cluster-name aura-cluster-${ENV} \
  --nodegroup-name aura-general-${ENV} \
  --query 'nodegroup.scalingConfig'

# List nodes and their utilization
kubectl top nodes
kubectl get nodes -o wide
```

### Vertical Pod Autoscaler (VPA)

VPA recommends and optionally applies resource requests/limits.

**Configuration:**

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: aura-api-vpa
  namespace: aura-system
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: aura-api
  updatePolicy:
    updateMode: "Off"  # Recommend only, do not auto-apply
  resourcePolicy:
    containerPolicies:
    - containerName: api
      minAllowed:
        cpu: 250m
        memory: 512Mi
      maxAllowed:
        cpu: 4
        memory: 8Gi
```

**Get VPA Recommendations:**

```bash
kubectl get vpa aura-api-vpa -n aura-system -o jsonpath='{.status.recommendation}'
```

---

## Database Scaling

### Neptune Scaling

**Vertical Scaling (Instance Class):**

| Workload | Instance Class | vCPU | Memory | Cost/Month |
|----------|---------------|------|--------|------------|
| Development | db.t3.medium | 2 | 4 GB | ~$90 |
| Production Small | db.r5.large | 2 | 16 GB | ~$300 |
| Production Medium | db.r5.xlarge | 4 | 32 GB | ~$600 |
| Production Large | db.r5.2xlarge | 8 | 64 GB | ~$1200 |

```bash
# Upgrade instance class
aws neptune modify-db-instance \
  --db-instance-identifier aura-neptune-${ENV} \
  --db-instance-class db.r5.xlarge \
  --apply-immediately

# Check modification status
aws neptune describe-db-instances \
  --db-instance-identifier aura-neptune-${ENV} \
  --query 'DBInstances[0].DBInstanceStatus'
```

**Horizontal Scaling (Read Replicas):**

```bash
# Add read replica
aws neptune create-db-instance \
  --db-instance-identifier aura-neptune-reader-${ENV}-01 \
  --db-instance-class db.r5.large \
  --engine neptune \
  --db-cluster-identifier aura-neptune-cluster-${ENV}

# Configure application to use reader endpoint for queries
# Writer: aura-neptune-cluster-${ENV}.cluster-xxx.us-east-1.neptune.amazonaws.com
# Reader: aura-neptune-cluster-${ENV}.cluster-ro-xxx.us-east-1.neptune.amazonaws.com
```

### OpenSearch Scaling

**Horizontal Scaling (Data Nodes):**

```bash
# Increase data nodes
aws opensearch update-domain-config \
  --domain-name aura-opensearch-${ENV} \
  --cluster-config InstanceType=r6g.large.search,InstanceCount=3

# Check update status
aws opensearch describe-domain \
  --domain-name aura-opensearch-${ENV} \
  --query 'DomainStatus.Processing'
```

**Vertical Scaling:**

| Workload | Instance Type | Storage | Data Nodes | Master Nodes |
|----------|---------------|---------|------------|--------------|
| Development | t3.small.search | 50 GB | 1 | 0 |
| Production Small | r6g.large.search | 200 GB | 2 | 0 |
| Production Medium | r6g.large.search | 500 GB | 3 | 3 |
| Production Large | r6g.xlarge.search | 1 TB | 5 | 3 |

**Index Sharding Strategy:**

```bash
# Check current shard allocation
curl -s -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/_cat/shards?v"

# Reindex with more shards for high-volume indices
curl -X PUT -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/aura-code-embeddings-v2" \
  -H "Content-Type: application/json" \
  -d '{
    "settings": {
      "number_of_shards": 5,
      "number_of_replicas": 1
    }
  }'
```

### DynamoDB Scaling

**On-Demand Capacity Mode:**

DynamoDB tables use on-demand capacity by default, automatically scaling with traffic.

```bash
# Check current capacity mode
aws dynamodb describe-table \
  --table-name aura-approval-requests-${ENV} \
  --query 'Table.BillingModeSummary.BillingMode'

# Switch to on-demand (if using provisioned)
aws dynamodb update-table \
  --table-name aura-approval-requests-${ENV} \
  --billing-mode PAY_PER_REQUEST
```

**Provisioned Capacity with Auto Scaling:**

For predictable workloads, provisioned capacity with auto-scaling is more cost-effective.

```bash
# Enable auto-scaling for read capacity
aws application-autoscaling register-scalable-target \
  --service-namespace dynamodb \
  --resource-id "table/aura-approval-requests-${ENV}" \
  --scalable-dimension "dynamodb:table:ReadCapacityUnits" \
  --min-capacity 5 \
  --max-capacity 1000

# Set scaling policy
aws application-autoscaling put-scaling-policy \
  --service-namespace dynamodb \
  --resource-id "table/aura-approval-requests-${ENV}" \
  --scalable-dimension "dynamodb:table:ReadCapacityUnits" \
  --policy-name "aura-approval-read-scaling" \
  --policy-type "TargetTrackingScaling" \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "DynamoDBReadCapacityUtilization"
    },
    "ScaleInCooldown": 60,
    "ScaleOutCooldown": 60
  }'
```

---

## Application Scaling

### API Service Scaling

**Traffic-Based Scaling Triggers:**

| Metric | Scale Out | Scale In | Cooldown |
|--------|-----------|----------|----------|
| Requests/sec | > 500 | < 100 | 3 min |
| CPU Utilization | > 70% | < 30% | 5 min |
| Response Time (p95) | > 500ms | < 100ms | 5 min |
| Error Rate | > 1% | < 0.1% | 10 min |

**Custom Metrics Scaling (KEDA):**

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: aura-api-scaler
  namespace: aura-system
spec:
  scaleTargetRef:
    name: aura-api
  minReplicaCount: 2
  maxReplicaCount: 10
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus.monitoring:9090
      metricName: http_requests_per_second
      query: sum(rate(http_requests_total{service="aura-api"}[1m]))
      threshold: "100"
  - type: aws-cloudwatch
    metadata:
      namespace: Aura/API
      dimensionName: Environment
      dimensionValue: prod
      metricName: Latency
      targetMetricValue: "500"
      minMetricValue: "100"
```

### Agent Service Scaling

Agents scale based on queue depth and processing time.

**Queue-Based Scaling:**

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: coder-agent-scaler
  namespace: aura-system
spec:
  scaleTargetRef:
    name: coder-agent
  minReplicaCount: 1
  maxReplicaCount: 5
  pollingInterval: 15
  cooldownPeriod: 300
  triggers:
  - type: aws-sqs-queue
    metadata:
      queueURL: https://sqs.us-east-1.amazonaws.com/${ACCOUNT_ID}/aura-patch-requests-${ENV}
      queueLength: "5"  # Messages per replica
      awsRegion: us-east-1
```

**Agent Resource Requirements:**

| Agent | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-------|-------------|-----------|----------------|--------------|
| orchestrator | 500m | 2000m | 1Gi | 4Gi |
| coder-agent | 1000m | 4000m | 2Gi | 8Gi |
| reviewer-agent | 500m | 2000m | 1Gi | 4Gi |
| validator-agent | 1000m | 4000m | 2Gi | 8Gi |
| context-retrieval | 500m | 2000m | 1Gi | 4Gi |

---

## Capacity Planning

### Current Capacity Assessment

```bash
#!/bin/bash
# capacity-report.sh

echo "=== Capacity Report - $(date) ==="

echo -e "\n--- EKS Nodes ---"
kubectl get nodes -o custom-columns='NAME:.metadata.name,CPU:.status.capacity.cpu,MEMORY:.status.capacity.memory,ALLOCATABLE_CPU:.status.allocatable.cpu,ALLOCATABLE_MEM:.status.allocatable.memory'

echo -e "\n--- Resource Utilization ---"
kubectl top nodes

echo -e "\n--- Pod Resource Usage ---"
kubectl top pods -n aura-system --sort-by=cpu | head -10

echo -e "\n--- Neptune Metrics ---"
aws cloudwatch get-metric-statistics \
  --namespace AWS/Neptune \
  --metric-name CPUUtilization \
  --dimensions Name=DBClusterIdentifier,Value=aura-neptune-cluster-${ENV} \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 3600 \
  --statistics Average,Maximum

echo -e "\n--- OpenSearch Cluster Health ---"
curl -s -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/_cluster/health?pretty"

echo -e "\n--- DynamoDB Capacity ---"
for TABLE in approval-requests agent-state user-sessions; do
  echo "Table: aura-${TABLE}-${ENV}"
  aws dynamodb describe-table \
    --table-name aura-${TABLE}-${ENV} \
    --query 'Table.ProvisionedThroughput'
done
```

### Growth Projections

| Metric | Current | +3 Months | +6 Months | +12 Months |
|--------|---------|-----------|-----------|------------|
| Repositories | 50 | 100 | 200 | 500 |
| Daily Scans | 200 | 500 | 1000 | 2500 |
| Patches/Day | 50 | 150 | 300 | 750 |
| API Calls/Min | 500 | 1500 | 3000 | 7500 |
| Code Embeddings | 10M | 25M | 50M | 125M |
| Graph Vertices | 50M | 125M | 250M | 625M |

### Infrastructure Scaling Recommendations

| Growth Stage | EKS Nodes | Neptune | OpenSearch | DynamoDB |
|--------------|-----------|---------|------------|----------|
| Current | 4 | db.r5.large (1) | r6g.large (2) | On-demand |
| +3 Months | 6 | db.r5.large (2) | r6g.large (3) | On-demand |
| +6 Months | 10 | db.r5.xlarge (2) | r6g.xlarge (3) | On-demand |
| +12 Months | 15 | db.r5.xlarge (3) | r6g.xlarge (5) | Provisioned + AS |

---

## Load Testing

### Load Test Configuration

**k6 Load Test Script:**

```javascript
// load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp up
    { duration: '5m', target: 100 },  // Steady state
    { duration: '2m', target: 200 },  // Peak load
    { duration: '2m', target: 100 },  // Scale down
    { duration: '1m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    http_req_failed: ['rate<0.01'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'https://api.aenealabs.com';
const TOKEN = __ENV.AURA_TOKEN;

export default function () {
  const headers = {
    'Authorization': `Bearer ${TOKEN}`,
    'Content-Type': 'application/json',
  };

  // Health check
  let healthRes = http.get(`${BASE_URL}/v1/health`);
  check(healthRes, {
    'health status is 200': (r) => r.status === 200,
  });

  // List repositories
  let reposRes = http.get(`${BASE_URL}/v1/repositories`, { headers });
  check(reposRes, {
    'repos status is 200': (r) => r.status === 200,
    'repos response time < 500ms': (r) => r.timings.duration < 500,
  });

  // List vulnerabilities
  let vulnsRes = http.get(`${BASE_URL}/v1/vulnerabilities?severity=critical`, { headers });
  check(vulnsRes, {
    'vulns status is 200': (r) => r.status === 200,
  });

  sleep(1);
}
```

**Run Load Test:**

```bash
# Install k6
brew install k6

# Run load test
BASE_URL=https://api.aenealabs.com \
AURA_TOKEN=${AURA_TOKEN} \
k6 run load-test.js --out json=results.json

# Generate HTML report
k6 run load-test.js --out influxdb=http://localhost:8086/k6
```

### Stress Testing

```bash
# High concurrency test
k6 run --vus 500 --duration 10m load-test.js

# Spike test
k6 run --vus 1000 --duration 1m load-test.js

# Soak test (long duration)
k6 run --vus 100 --duration 4h load-test.js
```

---

## Scaling Best Practices

### General Guidelines

1. **Scale Horizontally First**
   - Add pods/nodes before upgrading instance sizes
   - Horizontal scaling provides better fault tolerance

2. **Set Appropriate Limits**
   - Always set resource requests and limits
   - Leave headroom for bursts (20-30%)

3. **Use Pod Disruption Budgets**
   ```yaml
   apiVersion: policy/v1
   kind: PodDisruptionBudget
   metadata:
     name: aura-api-pdb
     namespace: aura-system
   spec:
     minAvailable: 2
     selector:
       matchLabels:
         app: aura-api
   ```

4. **Monitor Scaling Events**
   ```bash
   kubectl get events -n aura-system --field-selector reason=ScalingReplicaSet
   ```

5. **Test Scaling Behavior**
   - Regularly test scale-up and scale-down
   - Verify application handles pod restarts gracefully

### Anti-Patterns to Avoid

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| No resource limits | Noisy neighbor | Set limits on all pods |
| Aggressive scale-down | Thrashing | Use cooldown periods |
| Single replica critical services | No HA | minReplicas >= 2 |
| Undersized nodes | Pod scheduling failures | Right-size node groups |
| No PodDisruptionBudget | Availability loss during updates | Define PDBs |

---

## Troubleshooting Scaling Issues

### Pods Not Scaling

**Check HPA Status:**

```bash
kubectl describe hpa aura-api-hpa -n aura-system

# Common issues:
# - Metrics not available (check metrics-server)
# - Resource limits not set
# - Target percentage already met
```

**Check Metrics Server:**

```bash
kubectl top pods -n aura-system
kubectl get apiservice v1beta1.metrics.k8s.io -o yaml
```

### Nodes Not Scaling

**Check Cluster Autoscaler Logs:**

```bash
kubectl logs -n kube-system -l app=cluster-autoscaler --tail=100

# Common issues:
# - Pod scheduling constraints (nodeSelector, affinity)
# - ASG max size reached
# - Insufficient IAM permissions
```

**Check ASG Status:**

```bash
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names aura-general-${ENV} \
  --query 'AutoScalingGroups[0].[DesiredCapacity,MinSize,MaxSize,Instances[*].InstanceId]'
```

---

## Related Documentation

- [Operations Index](./index.md)
- [Monitoring Guide](./monitoring.md)
- [Performance Issues](../troubleshooting/performance-issues.md)
- [Architecture Overview](../architecture/system-overview.md)

---

*Last updated: January 2026 | Version 1.0*
