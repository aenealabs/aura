# ArgoCD Runbook

This document provides operational procedures for managing ArgoCD in Project Aura's GitOps deployment pipeline.

## Overview

Project Aura uses ArgoCD for GitOps-based Kubernetes deployments, separating CI (CodeBuild) from CD (ArgoCD):

| Component | Responsibility |
|-----------|----------------|
| **CodeBuild** | Build images, run tests, push to ECR |
| **ArgoCD** | Sync manifests from Git to Kubernetes |

**Architecture Decision:** [ADR-022: GitOps for Kubernetes Deployment](architecture-decisions/ADR-022-gitops-kubernetes-deployment.md)

---

## Quick Reference

### Access ArgoCD UI

```bash
# Port-forward to ArgoCD server
kubectl port-forward svc/argocd-server -n argocd 8080:80

# Open browser: http://localhost:8080
# Username: admin
# Password: (retrieve with command below or use your updated password)
```

### Get Initial Admin Password

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo
```

### Check Application Status

```bash
# List all applications
kubectl get applications -n argocd

# Detailed status
kubectl get applications -n argocd -o custom-columns=\
'NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status,REVISION:.status.sync.revision'
```

---

## Applications

| Application | Path | Description | Status |
|-------------|------|-------------|--------|
| `aura-frontend` | `deploy/kubernetes/aura-frontend/` | React approval dashboard | Synced, Healthy |
| `aura-api` | `deploy/kubernetes/aura-api/` | FastAPI backend service | Synced, Healthy |
| `memory-service` | `deploy/kubernetes/memory-service/` | Titan Neural Memory service (gRPC) | Synced, Healthy |

### memory-service Details

The `memory-service` application manages the Titan Neural Memory inference service:

- **Ports:** gRPC (50051), Health (8080), Metrics (9090)
- **Sync Settings:** `prune: false`, `selfHeal: true` (safe adoption mode)
- **Protection:** `Delete=false` annotation prevents accidental deletion during sync
- **Resources Managed:**
  - ConfigMap/memory-service-config
  - Service/memory-service (ClusterIP)
  - Service/memory-service-headless (for gRPC client-side load balancing)
  - ServiceAccount/memory-service (IRSA for AWS access)
  - Deployment/memory-service
  - NetworkPolicy/memory-service-network-policy

---

## Common Operations

### View Application Details

```bash
# Describe an application
kubectl describe application aura-frontend -n argocd
kubectl describe application memory-service -n argocd

# Get application in YAML format
kubectl get application aura-frontend -n argocd -o yaml
kubectl get application memory-service -n argocd -o yaml
```

### Manual Sync

Trigger a manual sync when automated sync is disabled or for immediate deployment:

```bash
# Sync using kubectl patch
kubectl -n argocd patch application aura-frontend \
  -p '{"operation": {"initiatedBy": {"username": "admin"}, "sync": {"revision": "HEAD"}}}' \
  --type merge

# Or use argocd CLI (if installed)
argocd app sync aura-frontend
```

### Force Refresh

Refresh application state from Git without syncing:

```bash
kubectl -n argocd patch application aura-frontend \
  -p '{"metadata": {"annotations": {"argocd.argoproj.io/refresh": "hard"}}}' \
  --type merge
```

### View Sync History

```bash
kubectl get application aura-frontend -n argocd \
  -o jsonpath='{.status.history}' | python3 -m json.tool
```

---

## Rollback Procedures

### Option 1: Git Revert (Recommended)

The GitOps way - revert the commit and let ArgoCD sync:

```bash
# Revert the last commit
git revert HEAD --no-edit
git push origin main

# ArgoCD will automatically sync the reverted state (within 3 minutes)
# Or trigger immediate sync:
kubectl -n argocd patch application aura-frontend \
  -p '{"operation": {"sync": {}}}' --type merge
```

### Option 2: ArgoCD Rollback

Rollback to a previous sync revision:

```bash
# View sync history
kubectl get application aura-frontend -n argocd \
  -o jsonpath='{range .status.history[*]}{.id}: {.revision} ({.deployedAt}){"\n"}{end}'

# Rollback to specific revision (replace REVISION_ID)
kubectl -n argocd patch application aura-frontend \
  -p '{"operation": {"sync": {"revision": "PREVIOUS_COMMIT_SHA"}}}' \
  --type merge
```

### Option 3: Emergency - Direct kubectl

For critical situations, bypass ArgoCD temporarily:

```bash
# Scale down problematic deployment
kubectl scale deployment aura-frontend --replicas=0

# Rollback to previous revision
kubectl rollout undo deployment/aura-frontend

# Note: ArgoCD will detect drift and may re-sync
# Disable auto-sync if needed (see Troubleshooting)
```

---

## Troubleshooting

### Application Stuck in "Syncing"

```bash
# Check sync status and errors
kubectl describe application aura-frontend -n argocd | grep -A 10 "Status:"

# Check repo-server logs (manifest generation)
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-repo-server --tail=50

# Check application-controller logs (sync operations)
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller --tail=50
```

### Application Shows "Unknown" Sync Status

Usually indicates Git authentication issues:

```bash
# Check if repo credentials are configured
kubectl get secrets -n argocd -l argocd.argoproj.io/secret-type=repository

# View repo-server logs for auth errors
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-repo-server | grep -i "auth\|error"

# Re-run GitHub App configuration if needed
AWS_PROFILE=<your-profile> ./deploy/scripts/configure-argocd-github-app.sh <app-id> <installation-id> <key.pem>
```

### Disable Auto-Sync (Emergency)

Temporarily disable auto-sync to prevent ArgoCD from overwriting manual changes:

```bash
# Disable auto-sync
kubectl -n argocd patch application aura-frontend \
  -p '{"spec": {"syncPolicy": {"automated": null}}}' --type merge

# Re-enable auto-sync
kubectl -n argocd patch application aura-frontend \
  -p '{"spec": {"syncPolicy": {"automated": {"prune": true, "selfHeal": true}}}}' --type merge
```

### Application Health Degraded

```bash
# Check which resources are unhealthy
kubectl get application aura-frontend -n argocd \
  -o jsonpath='{range .status.resources[?(@.health.status!="Healthy")]}{.kind}/{.name}: {.health.status} - {.health.message}{"\n"}{end}'

# Check pod status directly
kubectl get pods -l app=aura-frontend -o wide
kubectl describe pod -l app=aura-frontend | grep -A 10 "Events:"
```

### Port-Forward Issues

If `kubectl port-forward` fails with connection errors:

```bash
# Restart the ArgoCD server pod
kubectl rollout restart deployment/argocd-server -n argocd
kubectl rollout status deployment/argocd-server -n argocd

# Try again with new pod
kubectl port-forward svc/argocd-server -n argocd 8080:80
```

---

## Configuration

### ArgoCD Components

| Component | Purpose | Resource Limits |
|-----------|---------|-----------------|
| argocd-server | API server & UI | 200m CPU, 256Mi RAM |
| argocd-repo-server | Git operations, manifest generation | 200m CPU, 256Mi RAM |
| argocd-application-controller | Sync & health monitoring | Default |
| argocd-applicationset-controller | ApplicationSet management | 100m CPU, 128Mi RAM |
| argocd-redis | Caching | Default |

### Sync Policy Settings

Current sync policy for Aura applications:

```yaml
syncPolicy:
  automated:
    prune: true      # Delete resources removed from Git
    selfHeal: true   # Revert manual changes
  syncOptions:
    - CreateNamespace=true
    - Validate=true
    - PruneLast=true
  retry:
    limit: 5
    backoff:
      duration: 5s
      factor: 2
      maxDuration: 3m
```

---

## Security

### GitHub App Authentication

ArgoCD uses a GitHub App for repository access (more secure than PAT):

| Credential | SSM Path | Purpose |
|------------|----------|---------|
| App ID | `/aura/global/github-app-id` | GitHub App identifier |
| Installation ID | `/aura/global/github-app-installation-id` | Repo installation |
| Private Key | `/aura/global/github-app-private-key` | Authentication |

### RBAC

ArgoCD Project `aura` restricts deployments to:

- **Namespaces:** `default`, `argocd`, `kube-system`
- **Cluster-scoped resources:** Namespace, ClusterRole, ClusterRoleBinding
- **Source repos:** `https://github.com/aenealabs/aura`

### Post-Setup Security

After changing the admin password, delete the initial secret:

```bash
kubectl delete secret argocd-initial-admin-secret -n argocd
```

---

## Monitoring

### Key Metrics

ArgoCD exposes Prometheus metrics at `argocd-metrics:8082`:

| Metric | Description |
|--------|-------------|
| `argocd_app_info` | Application metadata |
| `argocd_app_sync_total` | Sync operation count |
| `argocd_app_health_status` | Health status by app |
| `argocd_repo_pending_request_total` | Git operations queue |

### Health Checks

```bash
# Check all ArgoCD pods are running
kubectl get pods -n argocd

# Verify applications are synced
kubectl get applications -n argocd -o custom-columns='NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status'
```

---

## Argo Rollouts (Progressive Delivery)

Project Aura uses Argo Rollouts for canary deployments with automated rollback. Both `aura-frontend` and `aura-api` use Rollouts instead of standard Deployments.

### Rollout Status

```bash
# List all Rollouts
kubectl get rollouts -n default

# Detailed status with revision info
kubectl get rollouts -n default -o custom-columns=\
'NAME:.metadata.name,DESIRED:.spec.replicas,CURRENT:.status.replicas,READY:.status.availableReplicas,PHASE:.status.phase'
```

### Canary Deployment Steps

Both applications use a 4-step canary strategy:

| Step | Weight | Action |
|------|--------|--------|
| 1 | 10% | Manual pause (verification) |
| 2 | 25% | Pod health analysis (2 min) |
| 3 | 50% | HTTP benchmark analysis (3 min) |
| 4 | 100% | Full promotion |

### Promote Canary (Step 1 Pause)

When a new version is deployed, it pauses at 10% for manual verification:

```bash
# Promote to next step (continue canary rollout)
kubectl patch rollout aura-frontend -n default \
  -p '{"status":{"pauseConditions":null}}' --type=merge

# Or use argo-rollouts kubectl plugin (if installed)
kubectl argo rollouts promote aura-frontend -n default
```

### Abort Rollout

If issues are detected during canary:

```bash
# Abort rollout - reverts to previous stable version
kubectl patch rollout aura-frontend -n default \
  -p '{"spec":{"paused":true}}' --type=merge

# Then scale down canary replicas
kubectl scale rollout aura-frontend --replicas=0 -n default
kubectl scale rollout aura-frontend --replicas=2 -n default
```

### View Analysis Results

```bash
# List analysis runs
kubectl get analysisrun -n default

# View analysis details
kubectl describe analysisrun -n default -l rollouts-pod-template-hash
```

### ClusterAnalysisTemplates

| Template | Purpose | Success Criteria |
|----------|---------|------------------|
| `pod-health` | Pod readiness check | 80% pods ready |
| `http-benchmark` | HTTP endpoint health | HTTP 200 response |
| `success-rate` | Prometheus success rate | 95% success rate |
| `latency-check` | P99 latency | Under threshold (500ms) |

```bash
# List ClusterAnalysisTemplates
kubectl get clusteranalysistemplate
```

### Troubleshooting Rollouts

```bash
# Check Rollout status and conditions
kubectl describe rollout aura-frontend -n default

# View Argo Rollouts controller logs
kubectl logs -n argo-rollouts -l app.kubernetes.io/name=argo-rollouts

# Check if analysis failed
kubectl get analysisrun -n default -o wide | grep -i failed
```

---

## Related Documentation

- [ADR-022: GitOps for Kubernetes Deployment](architecture-decisions/ADR-022-gitops-kubernetes-deployment.md)
- [CI/CD Setup Guide](CICD_SETUP_GUIDE.md)
- [ArgoCD Official Docs](https://argo-cd.readthedocs.io/)
- [Argo Rollouts Documentation](https://argo-rollouts.readthedocs.io/)
