# ADR-022: GitOps for Kubernetes Deployment with ArgoCD

**Status:** Deployed
**Date:** 2025-12-04
**Decision Makers:** Project Aura Team
**Supersedes:** Portions of ADR-007 (Kubernetes deployment sections)

## Context

Project Aura's current CI/CD architecture embeds Kubernetes deployment logic within CodeBuild buildspecs. As the platform scales toward enterprise customers with CMMC/FedRAMP compliance requirements, this approach presents several challenges:

**Current State:**
- 8 CodeBuild projects with embedded `kubectl apply` commands
- `buildspec-application.yml` is 440+ lines and growing
- Adding new services (e.g., frontend) increases buildspec complexity
- No progressive deployment capability (canary, blue/green)
- Rollback requires re-running builds with previous commits
- Audit trail for Kubernetes changes is mixed with CI logs

**Enterprise Requirements:**
- Independent service deployments without affecting other services
- Progressive delivery for AI workloads (canary with automatic rollback)
- Audit trail showing what was deployed, when, and by whom
- Instant rollback capability for production incidents
- Multi-environment consistency (dev/qa/staging/prod)
- GovCloud compatibility (no external SaaS dependencies)

**Scaling Concerns:**
- Monolithic buildspec timeout risk (>30 min builds)
- Single point of failure across all services
- Team bottleneck on shared buildspec modifications
- Testing individual service deployments is difficult

## Decision

We adopt **GitOps with ArgoCD** for Kubernetes deployments, separating CI (Continuous Integration) from CD (Continuous Deployment):

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           NEW ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   GitHub Push                                                            │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐  │
│   │   CodeBuild     │     │   Git Repo      │     │    ArgoCD       │  │
│   │   (CI Only)     │────▶│ (K8s Manifests) │◀────│   (CD Only)     │  │
│   │                 │     │                 │     │                 │  │
│   │ • Build image   │     │ • Single source │     │ • Sync to K8s   │  │
│   │ • Run tests     │     │   of truth      │     │ • Drift detect  │  │
│   │ • Push to ECR   │     │ • Audit trail   │     │ • Auto-rollback │  │
│   │ • Update tag    │     │ • PR reviews    │     │ • Multi-env     │  │
│   └─────────────────┘     └─────────────────┘     └─────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key Principles:**
1. **Git is the single source of truth** for Kubernetes state
2. **CodeBuild handles CI only** (build, test, push images)
3. **ArgoCD handles CD only** (sync, deploy, rollback)
4. **Each service gets its own Application** for independent deployment

## Implementation Plan

### Phase 1: Service-Specific Buildspecs (Week 1)

Split the monolithic `buildspec-application.yml` into focused service buildspecs:

```
deploy/buildspecs/
├── buildspec-infra-application.yml    # ECR repos, IRSA, Bedrock (CloudFormation only)
├── buildspec-service-api.yml          # Build aura-api image → Push to ECR
├── buildspec-service-frontend.yml     # Build frontend image → Push to ECR
├── buildspec-service-dnsmasq.yml      # Build dnsmasq image → Push to ECR
```

Each service buildspec:
- Builds Docker image
- Pushes to ECR
- Updates image tag in K8s manifests (Kustomize)
- Triggers ArgoCD sync (Phase 2)

### Phase 2: ArgoCD Installation (Week 2)

Deploy ArgoCD to EKS cluster:

```yaml
# ArgoCD Application for aura-api
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: aura-api
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/aenealabs/aura
    targetRevision: main
    path: deploy/kubernetes/aura-api
  destination:
    server: https://kubernetes.default.svc
    namespace: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

### Phase 3: Progressive Delivery (Week 3-4)

Add Argo Rollouts for canary deployments:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: aura-api
spec:
  replicas: 3
  strategy:
    canary:
      steps:
        - setWeight: 10
        - pause: {duration: 5m}
        - analysis:
            templates:
              - templateName: success-rate
        - setWeight: 50
        - pause: {duration: 10m}
        - setWeight: 100
```

### Directory Structure

```
deploy/
├── kubernetes/
│   ├── argocd/                    # ArgoCD installation manifests
│   │   ├── install.yaml
│   │   ├── applications/          # ArgoCD Application definitions
│   │   │   ├── aura-api.yaml
│   │   │   ├── aura-frontend.yaml
│   │   │   └── dnsmasq.yaml
│   │   └── projects/
│   │       └── aura.yaml
│   ├── aura-api/
│   │   ├── base/                  # Base manifests
│   │   │   ├── deployment.yaml
│   │   │   ├── service.yaml
│   │   │   └── kustomization.yaml
│   │   └── overlays/              # Environment-specific
│   │       ├── dev/
│   │       ├── qa/
│   │       └── prod/
│   ├── aura-frontend/
│   │   ├── base/
│   │   └── overlays/
│   └── dnsmasq/
│       ├── base/
│       └── overlays/
```

## Alternatives Considered

### Alternative 1: Keep Embedded kubectl in Buildspecs

Continue current approach with `kubectl apply` in buildspecs.

**Pros:**
- No new tooling to learn
- Simpler initial setup
- Single pipeline per layer

**Cons:**
- Growing complexity as services increase
- No progressive delivery
- Rollback requires re-running builds
- No drift detection
- Audit trail mixed with CI logs
- Enterprise customers expect GitOps

**Rejected:** Does not scale for enterprise requirements.

### Alternative 2: AWS CodePipeline + CodeDeploy for EKS

Use native AWS services for deployment.

**Pros:**
- AWS-native, good IAM integration
- No additional tooling in cluster

**Cons:**
- Limited Kubernetes-specific features
- No canary deployment support for EKS
- Less community adoption for K8s
- ArgoCD is the de facto standard

**Rejected:** ArgoCD has better Kubernetes support.

### Alternative 3: Flux CD

Use Flux instead of ArgoCD for GitOps.

**Pros:**
- CNCF graduated project
- Lighter weight than ArgoCD
- Helm controller built-in

**Cons:**
- Less intuitive UI for debugging
- Smaller community than ArgoCD
- ArgoCD Rollouts more mature than Flagger

**Rejected:** ArgoCD's UI and Rollouts ecosystem is more mature.

### Alternative 4: Spinnaker

Use Spinnaker for advanced deployment pipelines.

**Pros:**
- Very powerful multi-cloud support
- Advanced deployment strategies
- Netflix-proven at scale

**Cons:**
- Very complex to operate
- Heavy resource requirements
- Overkill for current team size
- Steep learning curve

**Rejected:** Complexity not justified for current scale.

## Consequences

### Positive

1. **Separation of Concerns**
   - CodeBuild focuses on building and testing
   - ArgoCD focuses on deployment and state management
   - Clear ownership boundaries

2. **Enterprise Compliance**
   - Git commit = deployment audit trail
   - Every change has author, timestamp, approval
   - Easy to answer "what was deployed when and by whom"
   - Required for CMMC/FedRAMP

3. **Instant Rollback**
   - `git revert` + ArgoCD sync = instant rollback
   - No waiting for builds to complete
   - Reduces MTTR significantly

4. **Progressive Delivery**
   - Canary deployments for AI workloads
   - Automatic rollback on error rate increase
   - Critical for agent/LLM deployments

5. **Drift Detection**
   - ArgoCD alerts when cluster state differs from Git
   - Self-healing capability
   - No more "works on my cluster" issues

6. **Team Scalability**
   - Each team owns their service manifests
   - No central bottleneck on buildspec changes
   - Parallel deployments possible

7. **GovCloud Ready**
   - ArgoCD runs in-cluster (no external SaaS)
   - Air-gap compatible
   - FedRAMP compatible

### Negative

1. **Additional Tooling**
   - ArgoCD installation and maintenance
   - Team learning curve
   - More components to monitor

2. **Initial Migration Effort**
   - Refactor buildspecs
   - Restructure K8s manifests
   - Create ArgoCD Applications
   - ~2-3 weeks of work

3. **Operational Complexity**
   - ArgoCD cluster-admin access
   - RBAC configuration
   - Secret management for Git access

### Mitigation

- Phased migration reduces risk (frontend first)
- Comprehensive documentation and runbooks
- ArgoCD has excellent documentation and community
- Can run parallel (old + new) during transition
- ArgoCD Notifications for alerting

## Migration Checklist

### Pre-Migration
- [ ] Document current deployment flow
- [ ] Identify all services to migrate
- [ ] Plan rollback strategy if migration fails

### Phase 1: Service Buildspecs
- [ ] Create `buildspec-service-frontend.yml`
- [ ] Create `buildspec-service-api.yml`
- [ ] Create `buildspec-service-dnsmasq.yml`
- [ ] Refactor `buildspec-application.yml` to infra-only
- [ ] Create corresponding CodeBuild projects

### Phase 2: ArgoCD Installation
- [ ] Install ArgoCD to EKS cluster
- [ ] Configure RBAC and SSO
- [ ] Create ArgoCD Project for aura
- [ ] Create ArgoCD Applications for each service
- [ ] Test sync and rollback

### Phase 3: Progressive Delivery
- [ ] Install Argo Rollouts
- [ ] Convert Deployments to Rollouts
- [ ] Create AnalysisTemplates for health checks
- [ ] Test canary deployment flow

### Post-Migration
- [ ] Remove kubectl from buildspecs
- [ ] Update documentation
- [ ] Train team on ArgoCD operations
- [ ] Set up ArgoCD Notifications

## Success Metrics

| Metric | Before | Target |
|--------|--------|--------|
| Deployment time (per service) | 15-25 min | 2-5 min |
| Rollback time | 15-25 min | <1 min |
| Deployment audit clarity | Mixed with CI logs | Git commit history |
| Service deployment independence | Coupled | Independent |
| Progressive delivery | None | Canary with auto-rollback |

## References

- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Argo Rollouts Documentation](https://argoproj.github.io/argo-rollouts/)
- [GitOps Principles](https://opengitops.dev/)
- ADR-007: Modular CI/CD with Layer-Based Deployment (superseded for K8s portions)
- `deploy/kubernetes/` - Existing Kubernetes manifests
- `deploy/buildspecs/` - Current buildspec files
