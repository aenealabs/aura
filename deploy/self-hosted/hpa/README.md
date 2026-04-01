# HPA Configuration for Self-Hosted Deployments

**ADR-049 Phase 0 Prerequisite**
**Last Updated:** 2026-01-03

---

## Overview

This directory contains Horizontal Pod Autoscaler (HPA) configurations and resource governance policies for Project Aura self-hosted Kubernetes deployments.

## Files

| File | Purpose |
|------|---------|
| `hpa-templates.yaml` | HPA configurations for all scalable services |
| `resource-quotas.yaml` | ResourceQuota and LimitRange for each namespace |

## Quick Start

### Prerequisites

```bash
# Verify metrics-server is installed
kubectl get deployment metrics-server -n kube-system

# Check metrics are available
kubectl top nodes
kubectl top pods -A
```

### Deployment

```bash
# 1. Create namespaces (if not exists)
kubectl create namespace aura
kubectl create namespace aura-data
kubectl create namespace aura-llm
kubectl create namespace aura-monitoring

# 2. Apply resource quotas and limit ranges
kubectl apply -f resource-quotas.yaml

# 3. Deploy applications (with resource requests/limits)
# ... deploy your applications ...

# 4. Apply HPA configurations
kubectl apply -f hpa-templates.yaml

# 5. Verify HPA status
kubectl get hpa -A
```

## HPA Configuration Reference

### Scaling Thresholds

| Metric | Target | Scale-Up | Scale-Down |
|--------|--------|----------|------------|
| CPU | 70% avg | Immediate | 5 min stabilization |
| Memory | 75-80% avg | Immediate | 5 min stabilization |

### Service-Specific Settings

| Service | Min | Max | Scale-Up Speed | Scale-Down Speed |
|---------|-----|-----|----------------|------------------|
| aura-api | 2 | 20 | Fast (100%/15s) | Slow (10%/60s) |
| aura-frontend | 2 | 10 | Fast (100%/15s) | Medium (25%/60s) |
| agent-orchestrator | 2 | 10 | Medium (2 pods/30s) | Slow (1 pod/60s) |
| memory-service | 2 | 8 | Medium (2 pods/60s) | Very slow (1 pod/120s) |
| vllm-inference | 1 | 4 | Slow (1 pod/60s) | Very slow (1 pod/300s) |

### Scale-Down Stabilization

Different services have different stabilization windows to prevent thrashing:

| Service Type | Window | Reason |
|--------------|--------|--------|
| Stateless (API, Frontend) | 300s | Standard protection |
| Agent services | 300-600s | Workflow continuity |
| LLM inference | 900s | GPU restart cost |

## Resource Quotas

### Per-Namespace Limits

| Namespace | CPU Req | CPU Lim | Mem Req | Mem Lim | Pods |
|-----------|---------|---------|---------|---------|------|
| aura | 50 | 100 | 100Gi | 200Gi | 100 |
| aura-data | 20 | 40 | 100Gi | 200Gi | 30 |
| aura-llm | 50 | 100 | 200Gi | 400Gi | 20 |
| aura-monitoring | 10 | 20 | 20Gi | 40Gi | 30 |

### Container Defaults (LimitRange)

| Namespace | Default CPU | Default Mem | Max CPU | Max Mem |
|-----------|-------------|-------------|---------|---------|
| aura | 500m | 512Mi | 4 | 16Gi |
| aura-data | 1 | 2Gi | 8 | 64Gi |
| aura-llm | 2 | 8Gi | 16 | 128Gi |
| aura-monitoring | 500m | 512Mi | 4 | 16Gi |

## Troubleshooting

### HPA Not Scaling

```bash
# Check HPA events
kubectl describe hpa aura-api-hpa -n aura

# Common issues:
# - "unable to get metrics" - metrics-server not working
# - "current replicas = max" - at maxReplicas, need to increase
# - CPU/memory showing 0% - pods don't have resource requests
```

### Metrics Not Available

```bash
# Check metrics-server logs
kubectl logs -n kube-system -l k8s-app=metrics-server

# Verify API is working
kubectl get --raw "/apis/metrics.k8s.io/v1beta1/nodes"
```

### Quota Exceeded

```bash
# Check quota usage
kubectl describe resourcequota -n aura

# If exceeded, either:
# 1. Increase quota limits
# 2. Delete unused resources
# 3. Reduce resource requests on pods
```

## Custom Metrics (Optional)

For advanced scaling based on application metrics, install prometheus-adapter:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus-adapter prometheus-community/prometheus-adapter \
  --namespace aura-monitoring \
  -f prometheus-adapter-values.yaml
```

Then add custom metrics to HPA:

```yaml
metrics:
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "1000"
```

## Related Documentation

- [Resource Baselines](../../../docs/self-hosted/RESOURCE_BASELINES.md) - Detailed resource recommendations
- [NetworkPolicy Templates](../network-policies/README.md) - Network isolation
- [ADR-049](../../../docs/architecture-decisions/ADR-049-self-hosted-deployment-strategy.md) - Self-hosted strategy
