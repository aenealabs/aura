# Resource Baselines for HPA Configuration

**Status:** Decided
**Date:** 2026-01-03
**Decision Makers:** Platform Architecture Team
**Context:** ADR-049 Phase 0 Prerequisite

---

## Executive Summary

This document defines resource baselines and HPA (Horizontal Pod Autoscaler) configurations for Project Aura self-hosted deployments. These baselines ensure proper scaling behavior while preventing resource exhaustion.

**Key Metrics:**
- **CPU Target:** 70% average utilization (industry standard)
- **Memory Target:** 80% average utilization
- **Scale-up Stabilization:** 0 seconds (react quickly to load)
- **Scale-down Stabilization:** 300 seconds (prevent thrashing)

---

## Service Resource Profiles

### Tier 1: Stateless API Services

These services handle HTTP requests and can scale horizontally without state concerns.

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit | Notes |
|---------|-------------|-----------|----------------|--------------|-------|
| **aura-api** | 250m | 1000m | 512Mi | 1Gi | Main API, high request volume |
| **aura-frontend** | 50m | 200m | 64Mi | 256Mi | Static assets + nginx proxy |
| **llm-router** | 100m | 500m | 128Mi | 512Mi | Request routing, no inference |

### Tier 2: Agent Services

These services coordinate AI workflows and require more resources for context processing.

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit | Notes |
|---------|-------------|-----------|----------------|--------------|-------|
| **agent-orchestrator** | 500m | 2000m | 1Gi | 4Gi | Workflow coordination |
| **memory-service** | 500m | 2000m | 2Gi | 8Gi | Neural memory, large context |
| **sandbox-runner** | 250m | 1000m | 512Mi | 2Gi | Code execution, isolated |

### Tier 3: LLM Inference Services

These services require GPU or significant CPU resources for model inference.

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit | GPU | Notes |
|---------|-------------|-----------|----------------|--------------|-----|-------|
| **vLLM** | 4000m | 8000m | 16Gi | 32Gi | 1x A100 (optional) | OpenAI-compatible API |
| **TGI** | 4000m | 8000m | 16Gi | 32Gi | 1x A100 (optional) | HuggingFace inference |
| **Ollama** | 2000m | 4000m | 8Gi | 16Gi | Optional | Development/eval only |

**GPU Recommendations:**
- **Enterprise (low latency):** NVIDIA A100 40GB or A10G
- **Budget:** NVIDIA T4 (slower, but cost-effective)
- **CPU-only:** Requires 4x more pods for equivalent throughput

### Tier 4: Database Services

These services are typically scaled vertically, not horizontally.

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit | Storage | Notes |
|---------|-------------|-----------|----------------|--------------|---------|-------|
| **Neo4j** | 2000m | 4000m | 4Gi | 16Gi | 100Gi SSD | Graph database |
| **PostgreSQL** | 1000m | 2000m | 2Gi | 8Gi | 50Gi SSD | Relational data |
| **OpenSearch** | 2000m | 4000m | 4Gi | 16Gi | 200Gi SSD | Vector search |
| **Redis** | 500m | 1000m | 1Gi | 4Gi | 10Gi SSD | Session cache |
| **MinIO** | 500m | 1000m | 1Gi | 2Gi | 500Gi HDD | Object storage |

### Tier 5: Monitoring Services

Observability stack with moderate resource requirements.

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit | Storage | Notes |
|---------|-------------|-----------|----------------|--------------|---------|-------|
| **Prometheus** | 500m | 2000m | 2Gi | 8Gi | 100Gi SSD | Metrics storage |
| **Grafana** | 100m | 500m | 256Mi | 1Gi | 10Gi SSD | Dashboard UI |
| **Alertmanager** | 100m | 500m | 128Mi | 512Mi | 1Gi SSD | Alert routing |
| **OTEL Collector** | 200m | 1000m | 512Mi | 2Gi | N/A | Trace collection |

---

## HPA Configuration Templates

### API Service HPA

```yaml
# deploy/self-hosted/hpa/aura-api-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: aura-api-hpa
  namespace: aura
  labels:
    app.kubernetes.io/name: aura-api
    app.kubernetes.io/component: autoscaling
    app.kubernetes.io/part-of: aura
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: aura-api
  minReplicas: 2
  maxReplicas: 20
  metrics:
    # Primary: CPU utilization
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    # Secondary: Memory utilization
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
    # Custom: Request latency (requires metrics-server + adapter)
    - type: Pods
      pods:
        metric:
          name: http_request_duration_seconds_p95
        target:
          type: AverageValue
          averageValue: "500m"  # 500ms p95 target
  behavior:
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
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
      selectPolicy: Min
```

### Agent Orchestrator HPA

```yaml
# deploy/self-hosted/hpa/agent-orchestrator-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agent-orchestrator-hpa
  namespace: aura
  labels:
    app.kubernetes.io/name: agent-orchestrator
    app.kubernetes.io/component: autoscaling
    app.kubernetes.io/part-of: aura
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agent-orchestrator
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
    # Custom: Active workflow count
    - type: Pods
      pods:
        metric:
          name: aura_active_workflows
        target:
          type: AverageValue
          averageValue: "50"  # 50 workflows per pod
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Pods
          value: 2
          periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 60
```

### Memory Service HPA

```yaml
# deploy/self-hosted/hpa/memory-service-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: memory-service-hpa
  namespace: aura
  labels:
    app.kubernetes.io/name: memory-service
    app.kubernetes.io/component: autoscaling
    app.kubernetes.io/part-of: aura
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: memory-service
  minReplicas: 2
  maxReplicas: 8
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
          averageUtilization: 75  # Lower threshold for memory-intensive
    # Custom: gRPC queue depth
    - type: Pods
      pods:
        metric:
          name: grpc_server_handling_seconds_count
        target:
          type: AverageValue
          averageValue: "100"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 600  # Longer for stateful-ish service
      policies:
        - type: Pods
          value: 1
          periodSeconds: 120
```

### LLM Inference HPA (vLLM)

```yaml
# deploy/self-hosted/hpa/vllm-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: vllm-hpa
  namespace: aura-llm
  labels:
    app.kubernetes.io/name: vllm
    app.kubernetes.io/component: autoscaling
    app.kubernetes.io/part-of: aura
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: vllm-inference
  minReplicas: 1
  maxReplicas: 4  # Limited by GPU availability
  metrics:
    # Primary: GPU utilization (requires DCGM exporter)
    - type: Pods
      pods:
        metric:
          name: DCGM_FI_DEV_GPU_UTIL
        target:
          type: AverageValue
          averageValue: "70"  # 70% GPU utilization
    # Secondary: Request queue depth
    - type: Pods
      pods:
        metric:
          name: vllm_num_requests_waiting
        target:
          type: AverageValue
          averageValue: "10"  # Scale up if >10 requests waiting
    # Fallback: CPU for non-GPU deployments
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 1
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 900  # 15 min - GPU pods are expensive to restart
      policies:
        - type: Pods
          value: 1
          periodSeconds: 300
```

### Frontend HPA

```yaml
# deploy/self-hosted/hpa/frontend-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: frontend-hpa
  namespace: aura
  labels:
    app.kubernetes.io/name: aura-frontend
    app.kubernetes.io/component: autoscaling
    app.kubernetes.io/part-of: aura
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: aura-frontend
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    # Custom: nginx active connections
    - type: Pods
      pods:
        metric:
          name: nginx_connections_active
        target:
          type: AverageValue
          averageValue: "100"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Percent
          value: 100
          periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 25
          periodSeconds: 60
```

---

## Deployment Size Recommendations

### Small (1-50 developers)

Suitable for evaluation, small teams, or development environments.

| Service | Replicas | CPU Total | Memory Total |
|---------|----------|-----------|--------------|
| aura-api | 2 | 500m-2000m | 1Gi-2Gi |
| aura-frontend | 2 | 100m-400m | 128Mi-512Mi |
| agent-orchestrator | 2 | 1000m-4000m | 2Gi-8Gi |
| memory-service | 1 | 500m-2000m | 2Gi-8Gi |
| llm-inference | 1 | 4000m-8000m | 16Gi-32Gi |
| **Total** | **8** | **~6-16 vCPU** | **~21-51Gi** |

**Recommended Node Configuration:**
- 2x m6i.2xlarge (8 vCPU, 32GB) or equivalent
- Or 1x m6i.4xlarge (16 vCPU, 64GB) for single-node

### Medium (50-200 developers)

Suitable for production workloads with moderate traffic.

| Service | Replicas | CPU Total | Memory Total |
|---------|----------|-----------|--------------|
| aura-api | 4-8 | 1-8 vCPU | 2-8Gi |
| aura-frontend | 2-4 | 100m-800m | 128Mi-1Gi |
| agent-orchestrator | 3-6 | 1.5-12 vCPU | 3-24Gi |
| memory-service | 2-4 | 1-8 vCPU | 4-32Gi |
| llm-inference | 2-3 | 8-24 vCPU | 32-96Gi |
| **Total** | **13-25** | **~12-53 vCPU** | **~41-161Gi** |

**Recommended Node Configuration:**
- 4x m6i.4xlarge (16 vCPU, 64GB) for workloads
- 1x g5.2xlarge (8 vCPU, 32GB, 1x A10G) for GPU inference

### Large (200+ developers)

Suitable for enterprise deployments with high availability requirements.

| Service | Replicas | CPU Total | Memory Total |
|---------|----------|-----------|--------------|
| aura-api | 8-20 | 2-20 vCPU | 4-20Gi |
| aura-frontend | 4-10 | 200m-2 vCPU | 256Mi-2.5Gi |
| agent-orchestrator | 6-10 | 3-20 vCPU | 6-40Gi |
| memory-service | 4-8 | 2-16 vCPU | 8-64Gi |
| llm-inference | 4-8 | 16-64 vCPU | 64-256Gi |
| **Total** | **26-56** | **~23-122 vCPU** | **~82-383Gi** |

**Recommended Node Configuration:**
- 8x m6i.4xlarge (16 vCPU, 64GB) for workloads
- 4x g5.4xlarge (16 vCPU, 64GB, 1x A10G) for GPU inference
- 3x r6i.2xlarge (8 vCPU, 64GB) for databases

---

## Scaling Thresholds and Alerts

### CPU-Based Scaling

| Threshold | Action | Alert |
|-----------|--------|-------|
| 50% avg | Normal operation | None |
| 70% avg | Begin scale-up | Info |
| 85% avg | Aggressive scale-up | Warning |
| 95% avg | Emergency scale-up | Critical |

### Memory-Based Scaling

| Threshold | Action | Alert |
|-----------|--------|-------|
| 60% avg | Normal operation | None |
| 80% avg | Begin scale-up | Info |
| 90% avg | Aggressive scale-up | Warning |
| 95% avg | OOM risk - immediate scale | Critical |

### Custom Metrics

| Metric | Target | Scale Trigger |
|--------|--------|---------------|
| `http_request_duration_seconds_p95` | < 500ms | > 1s |
| `aura_active_workflows` | < 50/pod | > 100/pod |
| `vllm_num_requests_waiting` | < 10 | > 50 |
| `grpc_server_handling_seconds_count` | < 100/s | > 500/s |

---

## Prometheus Rules for HPA Metrics

```yaml
# deploy/self-hosted/prometheus/hpa-rules.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: hpa-scaling-rules
  namespace: aura-monitoring
  labels:
    prometheus: aura
spec:
  groups:
    - name: hpa.scaling
      interval: 15s
      rules:
        # API request latency
        - record: http_request_duration_seconds_p95
          expr: |
            histogram_quantile(0.95,
              sum(rate(http_request_duration_seconds_bucket{job="aura-api"}[5m])) by (le, pod)
            )

        # Active workflows per pod
        - record: aura_active_workflows
          expr: |
            sum(aura_workflow_active{job="agent-orchestrator"}) by (pod)

        # gRPC request rate
        - record: grpc_server_handling_seconds_count
          expr: |
            sum(rate(grpc_server_handled_total{job="memory-service"}[1m])) by (pod)

    - name: hpa.alerts
      rules:
        - alert: HPAMaxReplicasReached
          expr: |
            kube_horizontalpodautoscaler_status_current_replicas
            == kube_horizontalpodautoscaler_spec_max_replicas
          for: 15m
          labels:
            severity: warning
          annotations:
            summary: "HPA {{ $labels.horizontalpodautoscaler }} at max replicas"
            description: "HPA has been at max replicas for 15 minutes. Consider increasing maxReplicas."

        - alert: HPAScalingRapidly
          expr: |
            changes(kube_horizontalpodautoscaler_status_current_replicas[15m]) > 5
          labels:
            severity: warning
          annotations:
            summary: "HPA {{ $labels.horizontalpodautoscaler }} scaling rapidly"
            description: "HPA has scaled more than 5 times in 15 minutes. May indicate instability."

        - alert: PodCPUThrottled
          expr: |
            sum(rate(container_cpu_cfs_throttled_periods_total[5m])) by (pod, namespace)
            / sum(rate(container_cpu_cfs_periods_total[5m])) by (pod, namespace)
            > 0.25
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Pod {{ $labels.pod }} is CPU throttled"
            description: "Pod is being throttled >25% of the time. Consider increasing CPU limits."

        - alert: PodMemoryNearLimit
          expr: |
            container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Pod {{ $labels.pod }} memory near limit"
            description: "Pod is using >90% of memory limit. OOM kill risk."
```

---

## Resource Quotas by Namespace

```yaml
# deploy/self-hosted/quotas/aura-quota.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: aura-quota
  namespace: aura
spec:
  hard:
    requests.cpu: "50"
    requests.memory: "100Gi"
    limits.cpu: "100"
    limits.memory: "200Gi"
    pods: "100"
    persistentvolumeclaims: "20"
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: aura-data-quota
  namespace: aura-data
spec:
  hard:
    requests.cpu: "20"
    requests.memory: "100Gi"
    limits.cpu: "40"
    limits.memory: "200Gi"
    pods: "30"
    persistentvolumeclaims: "20"
    requests.storage: "2Ti"
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: aura-llm-quota
  namespace: aura-llm
spec:
  hard:
    requests.cpu: "50"
    requests.memory: "200Gi"
    limits.cpu: "100"
    limits.memory: "400Gi"
    pods: "20"
    requests.nvidia.com/gpu: "8"
    limits.nvidia.com/gpu: "8"
```

---

## LimitRange Defaults

```yaml
# deploy/self-hosted/quotas/aura-limitrange.yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: aura-limits
  namespace: aura
spec:
  limits:
    - type: Container
      default:
        cpu: "500m"
        memory: "512Mi"
      defaultRequest:
        cpu: "100m"
        memory: "128Mi"
      min:
        cpu: "10m"
        memory: "32Mi"
      max:
        cpu: "4"
        memory: "16Gi"
    - type: PersistentVolumeClaim
      min:
        storage: "1Gi"
      max:
        storage: "100Gi"
```

---

## Vertical Pod Autoscaler (VPA) Recommendations

For services that benefit from vertical scaling (databases, LLM inference):

```yaml
# deploy/self-hosted/vpa/neo4j-vpa.yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: neo4j-vpa
  namespace: aura-data
spec:
  targetRef:
    apiVersion: apps/v1
    kind: StatefulSet
    name: neo4j
  updatePolicy:
    updateMode: "Off"  # Recommendation only - manual apply
  resourcePolicy:
    containerPolicies:
      - containerName: neo4j
        minAllowed:
          cpu: "1"
          memory: "4Gi"
        maxAllowed:
          cpu: "8"
          memory: "32Gi"
        controlledResources: ["cpu", "memory"]
```

---

## Implementation Checklist

### Prerequisites

- [ ] metrics-server installed and healthy
- [ ] Prometheus Adapter configured (for custom metrics)
- [ ] DCGM Exporter installed (for GPU metrics)
- [ ] VPA controller installed (optional)

### Deployment Order

1. Apply ResourceQuotas and LimitRanges
2. Deploy services with resource requests/limits
3. Apply HPA configurations
4. Configure Prometheus rules for custom metrics
5. Verify HPA status: `kubectl get hpa -A`

### Verification Commands

```bash
# Check HPA status
kubectl get hpa -n aura -o wide

# Describe HPA for debugging
kubectl describe hpa aura-api-hpa -n aura

# Check metrics availability
kubectl top pods -n aura

# Verify custom metrics
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1" | jq .
```

---

## References

- [Kubernetes HPA Documentation](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Prometheus Adapter](https://github.com/kubernetes-sigs/prometheus-adapter)
- [VPA Documentation](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)
- [DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter)
- ADR-049: Self-Hosted Deployment Strategy
