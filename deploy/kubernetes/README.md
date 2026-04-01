# Project Aura - Kubernetes Network Services

This directory contains Kubernetes manifests for deploying network services to the Project Aura EKS cluster.

## Files

- **dnsmasq-daemonset.yaml** - DNS caching and service discovery DaemonSet

## Quick Deployment

```bash
# Deploy dnsmasq DaemonSet
kubectl apply -f dnsmasq-daemonset.yaml

# Verify deployment
kubectl get daemonset -n aura-network-services
kubectl get pods -n aura-network-services

# Test DNS resolution
kubectl exec -it <pod-name> -n aura-network-services -- \
  nslookup -port=5353 google.com 127.0.0.1
```

## Configuration

The dnsmasq configuration is stored in a ConfigMap within the manifest. To update:

```bash
# Edit configuration
kubectl edit configmap dnsmasq-config -n aura-network-services

# Restart DaemonSet to apply changes
kubectl rollout restart daemonset/dnsmasq -n aura-network-services
```

## Monitoring

```bash
# View logs
kubectl logs -n aura-network-services -l app=dnsmasq --tail=100 -f

# Check pod status
kubectl describe pod <pod-name> -n aura-network-services

# View events
kubectl get events -n aura-network-services --sort-by='.lastTimestamp'
```

## Documentation

See `docs/dnsmasq_integration.md` for complete documentation.
