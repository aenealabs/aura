# ArgoCD GitOps Configuration

GitOps deployment configuration for Project Aura using ArgoCD (ADR-022).

## Directory Structure

```
argocd/
├── kustomization.yaml          # Main Kustomize config (installs ArgoCD + apps)
├── namespace.yaml              # ArgoCD namespace
├── applications/
│   ├── aura-frontend.yaml      # Frontend dashboard application
│   ├── aura-api.yaml           # API service application
│   └── memory-service.yaml     # Neural Memory service application (NEW)
└── projects/
    └── aura.yaml               # ArgoCD Project with RBAC
```

## Installation

### Prerequisites

- EKS cluster running (aura-cluster-dev)
- kubectl configured with cluster access
- Git repository accessible from cluster

### Deploy ArgoCD

```bash
# Install ArgoCD and all applications
kubectl apply -k deploy/kubernetes/argocd/

# Wait for ArgoCD to be ready
kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=300s

# Get initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d && echo
```

### Access ArgoCD UI

```bash
# Port-forward to ArgoCD server
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Open browser: https://localhost:8080
# Username: admin
# Password: (from command above)
```

## Applications

| Application | Path | Description | Status |
|-------------|------|-------------|--------|
| aura-frontend | deploy/kubernetes/aura-frontend/ | React approval dashboard | Synced, Healthy |
| aura-api | deploy/kubernetes/aura-api/ | FastAPI backend service | Synced, Healthy |
| memory-service | deploy/kubernetes/memory-service/ | Titan Neural Memory service | Synced, Healthy |

### memory-service Application

The memory-service was added to ArgoCD management on Dec 14, 2025:

- **Sync Settings:** `prune: false`, `selfHeal: true` (safe adoption mode)
- **Protection:** `Delete=false` annotation prevents accidental resource deletion
- **Ports:** gRPC (50051), Health (8080), Metrics (9090)
- **Image Tag:** `:cpu-latest` (CPU-only mode for testing without GPU nodes)

## Sync Workflow

1. **CodeBuild** builds Docker image and pushes to ECR
2. **CodeBuild** updates image tag in kustomization.yaml
3. **ArgoCD** detects Git change (polling every 3 minutes)
4. **ArgoCD** syncs manifests to Kubernetes cluster
5. **ArgoCD** verifies deployment health

## Commands

```bash
# Check application status
kubectl get applications -n argocd

# Sync an application manually
kubectl -n argocd patch application aura-frontend -p '{"operation": {"initiatedBy": {"username": "admin"}, "sync": {"revision": "HEAD"}}}' --type merge

# Get application details
kubectl describe application aura-frontend -n argocd

# View sync history
kubectl get applications aura-frontend -n argocd -o jsonpath='{.status.history}' | jq
```

## Rollback

ArgoCD provides instant rollback via Git:

```bash
# Rollback to previous commit
git revert HEAD
git push origin main
# ArgoCD will automatically sync the reverted state

# Or rollback via ArgoCD CLI
argocd app rollback aura-frontend
```

## Troubleshooting

### Application stuck in "Syncing"

```bash
# Check sync status
kubectl describe application aura-frontend -n argocd

# Check ArgoCD logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-server
```

### Git repository not accessible

```bash
# Check repo-server logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-repo-server

# Verify network connectivity
kubectl run test --rm -it --image=alpine -- wget -qO- https://github.com
```

## Security

- ArgoCD runs with least-privilege RBAC (see `projects/aura.yaml`)
- Applications can only deploy to allowed namespaces
- Cluster-scoped resources are whitelisted explicitly
- Automated sync prevents configuration drift
