# Self-Hosted NetworkPolicy Templates

**ADR-049 Phase 0 Prerequisite**
**Last Updated:** 2026-01-03

---

## Overview

This directory contains default-deny NetworkPolicy templates for Project Aura self-hosted Kubernetes deployments. These policies implement a **zero-trust network model** where all traffic is blocked by default and only explicitly allowed connections are permitted.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     DEFAULT-DENY NETWORK ARCHITECTURE                    │
│                                                                          │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                │
│  │   INGRESS   │────▶│  FRONTEND   │────▶│   API       │                │
│  │  CONTROLLER │     │   (aura)    │     │   (aura)    │                │
│  └─────────────┘     └─────────────┘     └──────┬──────┘                │
│                                                  │                       │
│         ┌────────────────────────────────────────┼────────────────┐     │
│         │                                        │                │     │
│         ▼                                        ▼                ▼     │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐              │
│  │  AGENT      │     │   MEMORY    │     │   SANDBOX   │              │
│  │ ORCHESTRATOR│────▶│   SERVICE   │     │   RUNNER    │              │
│  │   (aura)    │     │   (aura)    │     │   (aura)    │              │
│  └──────┬──────┘     └──────┬──────┘     └─────────────┘              │
│         │                   │                                          │
│    ┌────┴────────────────────┴────────────────────┐                    │
│    │                   aura-data                   │                    │
│    │  ┌────────┐  ┌────────┐  ┌────────┐  ┌─────┐ │                    │
│    │  │ Neo4j  │  │PostgreS│  │OpenSrch│  │Redis│ │                    │
│    │  │ :7687  │  │ :5432  │  │ :9200  │  │:6379│ │                    │
│    │  └────────┘  └────────┘  └────────┘  └─────┘ │                    │
│    └────────────────────────────────────────────────┘                    │
│                                                                          │
│    ┌────────────────────────────────────────────────┐                    │
│    │                   aura-llm                      │                    │
│    │  ┌────────┐  ┌────────┐  ┌────────┐           │                    │
│    │  │ vLLM   │  │  TGI   │  │ Ollama │           │                    │
│    │  │ :8000  │  │ :8080  │  │ :11434 │           │                    │
│    │  └────────┘  └────────┘  └────────┘           │                    │
│    └────────────────────────────────────────────────┘                    │
│                                                                          │
│    ┌────────────────────────────────────────────────┐                    │
│    │                aura-monitoring                  │                    │
│    │  ┌────────┐  ┌────────┐  ┌────────┐           │                    │
│    │  │Promeths│  │Grafana │  │AlertMgr│           │                    │
│    │  │ :9090  │  │ :3000  │  │ :9093  │           │                    │
│    │  └────────┘  └────────┘  └────────┘           │                    │
│    └────────────────────────────────────────────────┘                    │
│                                                                          │
│         ─────▶ = Allowed traffic (explicit NetworkPolicy)               │
│         ═════▶ = Blocked by default                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

1. **Kubernetes cluster** with a CNI plugin that supports NetworkPolicy:
   - Calico (recommended)
   - Cilium
   - Weave Net
   - Azure CNI
   - AWS VPC CNI with Calico

2. **Namespaces created** with proper labels:
   ```bash
   kubectl create namespace aura
   kubectl create namespace aura-data
   kubectl create namespace aura-llm
   kubectl create namespace aura-monitoring

   kubectl label namespace aura kubernetes.io/metadata.name=aura
   kubectl label namespace aura-data kubernetes.io/metadata.name=aura-data
   kubectl label namespace aura-llm kubernetes.io/metadata.name=aura-llm
   kubectl label namespace aura-monitoring kubernetes.io/metadata.name=aura-monitoring
   ```

### Deployment Order

**CRITICAL:** Apply policies in order. The default-deny policy MUST be applied first.

```bash
# 1. Apply default-deny baseline (blocks ALL traffic)
kubectl apply -f 00-namespace-defaults.yaml

# 2. Apply service-specific allow rules
kubectl apply -f 01-aura-api.yaml
kubectl apply -f 02-databases.yaml
kubectl apply -f 03-llm-inference.yaml
kubectl apply -f 04-agents.yaml
kubectl apply -f 05-frontend.yaml
kubectl apply -f 06-monitoring.yaml
```

### Verification

```bash
# Check policies are applied
kubectl get networkpolicy -A

# Expected output:
# NAMESPACE         NAME                              POD-SELECTOR          AGE
# aura              default-deny-all                  <none>                1m
# aura              allow-dns-egress                  <none>                1m
# aura              aura-api-ingress                  app=aura-api          1m
# aura              aura-api-egress                   app=aura-api          1m
# ...
```

---

## Policy Files

| File | Purpose | Namespaces |
|------|---------|------------|
| `00-namespace-defaults.yaml` | Default-deny + DNS egress | All |
| `01-aura-api.yaml` | API service ingress/egress | aura |
| `02-databases.yaml` | Neo4j, PostgreSQL, OpenSearch, Redis | aura-data |
| `03-llm-inference.yaml` | vLLM, TGI, Ollama, LLM Router | aura-llm |
| `04-agents.yaml` | Orchestrator, Memory, Sandbox | aura |
| `05-frontend.yaml` | Frontend, Ingress Controller | aura, ingress-nginx |
| `06-monitoring.yaml` | Prometheus, Grafana, Alertmanager | aura-monitoring |

---

## Port Reference

### Application Services (aura namespace)

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| aura-api | 8080 | TCP | REST API, WebSocket |
| aura-api | 8081 | TCP | Health check |
| aura-api | 9090 | TCP | Prometheus metrics |
| aura-frontend | 80 | TCP | HTTP (nginx) |
| aura-frontend | 3000 | TCP | Next.js dev |
| agent-orchestrator | 8080 | TCP | REST API |
| memory-service | 50051 | TCP | gRPC |
| sandbox-runner | 8080 | TCP | API |
| sandbox-runner | 8081 | TCP | Health check |

### Database Services (aura-data namespace)

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| neo4j | 7687 | TCP | Bolt protocol |
| neo4j | 7474 | TCP | HTTP/Browser |
| neo4j | 5000 | TCP | Discovery (cluster) |
| neo4j | 6000 | TCP | Transaction (cluster) |
| neo4j | 7000 | TCP | Raft (cluster) |
| postgresql | 5432 | TCP | PostgreSQL |
| opensearch | 9200 | TCP | REST API |
| opensearch | 9300 | TCP | Transport |
| redis | 6379 | TCP | Redis protocol |
| redis | 26379 | TCP | Sentinel |
| minio | 9000 | TCP | S3 API |
| minio | 9001 | TCP | Console |

### LLM Services (aura-llm namespace)

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| vLLM | 8000 | TCP | OpenAI-compatible API |
| TGI | 8080 | TCP | Inference API |
| Ollama | 11434 | TCP | Ollama API |
| llm-router | 8080 | TCP | Load balancer |

### Monitoring Services (aura-monitoring namespace)

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| prometheus | 9090 | TCP | Query API |
| grafana | 3000 | TCP | Dashboard UI |
| alertmanager | 9093 | TCP | Alert API |
| alertmanager | 9094 | TCP | Cluster |
| otel-collector | 4317 | TCP | OTLP gRPC |
| otel-collector | 4318 | TCP | OTLP HTTP |

---

## Deployment Modes

### Standard Mode (Cloud-Connected)

Default configuration. Allows outbound HTTPS for:
- Cloud LLM APIs (Bedrock, Azure OpenAI)
- Package registries
- External notification services

```bash
kubectl apply -f .
```

### Air-Gapped Mode (Maximum Isolation)

For disconnected environments (defense, classified, etc.):

1. Use air-gapped policies:
   ```bash
   # Apply standard defaults
   kubectl apply -f 00-namespace-defaults.yaml
   kubectl apply -f 01-aura-api.yaml
   kubectl apply -f 02-databases.yaml

   # Use air-gapped LLM policy instead of standard
   kubectl apply -f 03-llm-inference.yaml
   # The file includes llm-airgap-network-policy - apply only that one

   kubectl apply -f 04-agents.yaml
   # Use sandbox-runner-airgap-network-policy for sandbox

   kubectl apply -f 05-frontend.yaml
   kubectl apply -f 06-monitoring.yaml
   ```

2. Remove external egress from monitoring:
   ```bash
   kubectl patch networkpolicy alertmanager-network-policy \
     -n aura-monitoring \
     --type='json' \
     -p='[{"op": "remove", "path": "/spec/egress/0"}]'
   ```

### Sandbox Isolation Levels

| Level | Policy | External Egress | Use Case |
|-------|--------|-----------------|----------|
| Standard | `sandbox-runner-network-policy` | HTTPS (443) | Development |
| Air-Gapped | `sandbox-runner-airgap-network-policy` | None | Production/Sensitive |

---

## Security Considerations

### Metadata Service Protection

**CRITICAL:** All policies block access to the cloud metadata service:
- AWS: `169.254.169.254/32`
- Azure: `169.254.169.254/32`
- GCP: `169.254.169.254/32`, `metadata.google.internal`

This prevents SSRF attacks that could steal cloud credentials.

### DNS Resolution

DNS is allowed by default (`allow-dns-egress` policy) because:
1. Pods cannot resolve service names without DNS
2. CoreDNS is trusted infrastructure
3. Blocking DNS breaks all network communication

### Prometheus Scraping

Prometheus needs egress to scrape metrics from all namespaces. The policy allows:
- All services in aura/aura-data/aura-llm namespaces
- Node-exporter on nodes (10.0.0.0/8:9100)
- kube-state-metrics in kube-system

### External HTTPS

Standard mode allows outbound HTTPS (port 443) with exclusions:
- Private networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Metadata service (169.254.169.254/32)

For maximum security, disable external HTTPS in air-gapped mode.

---

## Troubleshooting

### Verify CNI Supports NetworkPolicy

```bash
# Check for Calico
kubectl get pods -n kube-system | grep calico

# Check for Cilium
kubectl get pods -n kube-system | grep cilium

# If neither exists, NetworkPolicies will have NO EFFECT
```

### Test Connectivity

```bash
# Test API to database connectivity
kubectl run test --rm -it --image=busybox -n aura -- \
  nc -zv neo4j.aura-data.svc.cluster.local 7687

# Test blocked traffic (should fail)
kubectl run test --rm -it --image=busybox -n aura -- \
  nc -zv 169.254.169.254 80
```

### View Denied Connections (Cilium)

```bash
kubectl logs -n kube-system -l k8s-app=cilium --tail=100 | grep -i denied
```

### View Denied Connections (Calico)

```bash
kubectl logs -n kube-system -l k8s-app=calico-node --tail=100 | grep -i denied
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| All traffic blocked | Default-deny without allow rules | Apply service-specific policies |
| DNS not working | Missing `allow-dns-egress` | Apply `00-namespace-defaults.yaml` |
| Prometheus can't scrape | Missing namespace labels | Add `kubernetes.io/metadata.name` label |
| Health checks failing | Missing ipBlock for node CIDR | Verify 10.0.0.0/8 is correct for your cluster |

---

## Customization

### Adjust Node CIDR

If your cluster uses a different node CIDR:

```bash
# Replace 10.0.0.0/8 with your node CIDR
sed -i 's|10.0.0.0/8|YOUR_CIDR|g' *.yaml
```

### Add Custom Services

Template for new services:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: my-service-network-policy
  namespace: aura
  labels:
    app.kubernetes.io/name: my-service
    app.kubernetes.io/component: network-security
    app.kubernetes.io/part-of: aura
    security.aura.io/policy-type: service-allow
spec:
  podSelector:
    matchLabels:
      app: my-service
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: allowed-caller
      ports:
        - protocol: TCP
          port: 8080
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: allowed-target
      ports:
        - protocol: TCP
          port: 8080
```

---

## Related Documentation

- [ADR-049: Self-Hosted Deployment Strategy](../../../docs/architecture-decisions/ADR-049-self-hosted-deployment-strategy.md)
- [License Validation Scheme](../../../docs/self-hosted/LICENSE_VALIDATION_SCHEME.md)
- [DynamoDB Schema Reference](../../../docs/self-hosted/DYNAMODB_SCHEMA_REFERENCE.md)
- [Query Language Strategy](../../../docs/self-hosted/QUERY_LANGUAGE_STRATEGY.md)
