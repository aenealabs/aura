# Project Aura - Grafana Observability Stack

Unified observability dashboards for EKS, Neptune, OpenSearch, and application metrics.

**Issue:** #18 - Grafana dashboards for observability

## Quick Start

```bash
# Add Grafana Helm repo
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Create namespace and secret
kubectl create namespace monitoring
kubectl create secret generic grafana-admin-credentials \
  --from-literal=admin-user=admin \
  --from-literal=admin-password=<secure-password> \
  -n monitoring

# Install Grafana
helm install grafana grafana/grafana \
  -f deploy/kubernetes/grafana/values.yaml \
  -n monitoring
```

## Directory Structure

```
deploy/kubernetes/grafana/
├── README.md                    # This file
├── values.yaml                  # Helm values configuration
├── dashboards/
│   ├── api-latency-throughput.json    # API performance metrics
│   ├── eks-cluster-health.json        # EKS cluster health
│   ├── hitl-workflow-metrics.json     # HITL approval workflow
│   ├── neptune-performance.json       # Neptune graph database
│   └── opensearch-metrics.json        # OpenSearch vector search
└── provisioning/
    └── alerting/
        └── alerts.yaml          # Alerting rules
```

## Dashboards

| Dashboard | Description | Data Source |
|-----------|-------------|-------------|
| EKS Cluster Health | CPU, memory, pod status, node metrics | Prometheus |
| API Latency & Throughput | Request rates, latency percentiles, error rates | Prometheus |
| Neptune Performance | Query latency, throughput, connections | CloudWatch |
| OpenSearch Metrics | Search latency, indexing, cluster health | CloudWatch + Prometheus |
| HITL Workflow | Approval queue, SLA tracking, reviewer activity | Prometheus |

## Data Sources

The Helm values configure these data sources:

1. **Prometheus** (default) - Container and application metrics
2. **CloudWatch** - AWS service metrics (Neptune, OpenSearch, Lambda)
3. **CloudWatch Logs** - Log queries and analysis

### IRSA Configuration

Grafana uses IAM Roles for Service Accounts (IRSA) to access CloudWatch:

```yaml
serviceAccount:
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::${AWS_ACCOUNT_ID}:role/aura-grafana-role
```

Required IAM permissions:
- `cloudwatch:GetMetricData`
- `cloudwatch:ListMetrics`
- `logs:StartQuery`
- `logs:GetQueryResults`

## Alerting

Alerts route to SNS topics for integration with PagerDuty/Slack:

| Alert | Condition | Severity |
|-------|-----------|----------|
| API High Error Rate | >5% errors for 5m | Critical |
| API High Latency | P95 >2s for 5m | Warning |
| API Availability Low | <99.5% for 10m | Critical |
| EKS High CPU | >85% for 10m | Warning |
| EKS High Memory | >90% for 10m | Critical |
| Pod Restart Rate | >5 restarts/hour | Warning |
| Neptune High CPU | >80% for 10m | Warning |
| OpenSearch JVM Pressure | >85% for 10m | Critical |
| HITL Queue Buildup | >25 pending for 15m | Warning |
| HITL SLA Breach Risk | P90 >4 hours | Warning |

## Configuration

### Environment Variables

Replace these placeholders in `values.yaml`:

| Variable | Description |
|----------|-------------|
| `${AWS_ACCOUNT_ID}` | AWS account ID |
| `${CERTIFICATE_ARN}` | ACM certificate for HTTPS |

### Custom Metrics

Application metrics use the `Aura` CloudWatch namespace:

- `Aura/API` - API request metrics
- `Aura/Agents` - Agent execution metrics
- `Aura/HITL` - Approval workflow metrics

## Accessing Grafana

After deployment, access via the internal ALB:

```
https://grafana.aura.internal
```

For local development, use port-forward:

```bash
kubectl port-forward svc/grafana 3000:80 -n monitoring
# Open http://localhost:3000
```

## Adding New Dashboards

1. Create dashboard JSON in `dashboards/`
2. Add to ConfigMap in `values.yaml` under `dashboardsConfigMaps`
3. Upgrade Helm release:
   ```bash
   helm upgrade grafana grafana/grafana -f values.yaml -n monitoring
   ```

## Troubleshooting

### Dashboard not loading
- Check ConfigMap was created: `kubectl get cm -n monitoring | grep grafana`
- Verify sidecar is running: `kubectl logs -l app.kubernetes.io/name=grafana -c grafana-sc-dashboard -n monitoring`

### CloudWatch data missing
- Verify IRSA role: `kubectl describe sa grafana -n monitoring`
- Check IAM policy has required permissions
- Confirm region is correct in data source config

### Alerts not firing
- Check alert rules in Grafana UI > Alerting > Alert rules
- Verify contact points configured: Alerting > Contact points
- Check notification policies: Alerting > Notification policies
