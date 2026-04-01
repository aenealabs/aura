# ADR-036: Multi-Platform Container Build Strategy

**Status:** Deployed
**Date:** 2025-12-13
**Decision Makers:** Project Aura Team
**Relates To:** ADR-003 (EKS EC2 Nodes), ADR-020 (Private ECR Base Images), ADR-035 (Dedicated Docker Build Project)

## Context

Project Aura's memory-service requires deployment across heterogeneous compute environments:

1. **Production (EKS):** NVIDIA GPU nodes for accelerated inference (CUDA 12.1, cuDNN 8)
2. **Development (Local):** Apple Silicon Macs (ARM64) and Intel Macs (x86_64) for rapid iteration
3. **CI/CD (CodeBuild):** x86_64 Linux for automated builds

**Current Implementation:**
- `Dockerfile.memory-service` - NVIDIA CUDA base image (`nvcr.io/nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04`)
- `Dockerfile.memory-service-cpu` - Python slim base image (`python:3.11-slim`, multi-architecture)
- `buildspec-docker-build.yml` - Supports both via `BUILD_TARGET` parameter (`memory-service` or `memory-service-cpu`)

**Constraints:**
1. NVIDIA CUDA images only support NVIDIA GPUs (x86_64 only) - no Apple Silicon MPS support
2. PyTorch CUDA wheels require CUDA toolkit - incompatible with ARM64 Macs
3. Docker Hub rate limits (100 pulls/6 hours anonymous) impact CI/CD reliability
4. Apple Silicon cannot emulate CUDA - must use CPU-only PyTorch for local development
5. GovCloud compatibility required for production deployment

**Problem Statement:**
Without a clear multi-platform strategy, developers face:
- Build failures when using wrong Dockerfile on wrong platform
- Confusion about which image tag to use for which environment
- Potential Docker Hub rate limit blocks during development
- Inconsistent local vs. production behavior

## Decision

Adopt a **dual-variant container strategy** with explicit GPU/CPU image separation and platform-aware tagging:

```
                    Container Build Strategy
+------------------------------------------------------------------+
|                                                                    |
|   Source Code Repository                                          |
|   +---------------------------+  +---------------------------+    |
|   | Dockerfile.memory-service |  | Dockerfile.memory-service |    |
|   | (GPU - CUDA 12.1)         |  | -cpu (CPU-only)           |    |
|   +------------+--------------+  +------------+--------------+    |
|                |                              |                    |
|   +------------v--------------+  +------------v--------------+    |
|   | Base: nvcr.io/nvidia/cuda |  | Base: python:3.11-slim    |    |
|   | Arch: linux/amd64 only    |  | Arch: linux/amd64, arm64  |    |
|   | PyTorch: CUDA 12.1 wheels |  | PyTorch: CPU wheels       |    |
|   +------------+--------------+  +------------+--------------+    |
|                |                              |                    |
|                v                              v                    |
|   +---------------------------+  +---------------------------+    |
|   | ECR Tags:                 |  | ECR Tags:                 |    |
|   | - gpu-latest              |  | - cpu-latest              |    |
|   | - gpu-v1.2.3              |  | - cpu-v1.2.3              |    |
|   | - gpu-{commit-sha}        |  | - cpu-{commit-sha}        |    |
|   +---------------------------+  +---------------------------+    |
|                                                                    |
+------------------------------------------------------------------+
```

### Image Tagging Strategy

| Tag Pattern | Purpose | Example |
|-------------|---------|---------|
| `gpu-latest` | Latest GPU build for production | `aura-memory-service-dev:gpu-latest` |
| `cpu-latest` | Latest CPU build for dev/testing | `aura-memory-service-dev:cpu-latest` |
| `gpu-v{semver}` | Versioned GPU release | `aura-memory-service-prod:gpu-v1.2.3` |
| `cpu-v{semver}` | Versioned CPU release | `aura-memory-service-dev:cpu-v1.2.3` |
| `gpu-{sha}` | Git commit SHA (GPU) | `aura-memory-service-dev:gpu-a1b2c3d` |
| `cpu-{sha}` | Git commit SHA (CPU) | `aura-memory-service-dev:cpu-a1b2c3d` |
| `latest` | Alias to `gpu-latest` (production default) | `aura-memory-service-prod:latest` |

### Registry Selection

| Registry | Use Case | Rationale |
|----------|----------|-----------|
| `nvcr.io` (NVIDIA NGC) | CUDA base images | No rate limits, official NVIDIA support, CUDA/cuDNN pre-installed |
| `public.ecr.aws` | Python base images | AWS-hosted, no rate limits, multi-architecture support |
| Private ECR | Application images | Full control, vulnerability scanning, GovCloud compatible |

**Avoiding Docker Hub:**
- CUDA images: Use `nvcr.io/nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04` (NGC)
- Python images: Use `public.ecr.aws/docker/library/python:3.11-slim` or private ECR (ADR-020)
- Alpine images: Use private ECR base images (ADR-020)

### Build Matrix

| Environment | Build Target | Dockerfile | Platform | Tag Prefix |
|-------------|--------------|------------|----------|------------|
| Production (EKS GPU) | `memory-service` | `Dockerfile.memory-service` | `linux/amd64` | `gpu-` |
| Dev/QA (EKS CPU) | `memory-service-cpu` | `Dockerfile.memory-service-cpu` | `linux/amd64` | `cpu-` |
| Local (Apple Silicon) | `memory-service-cpu` | `Dockerfile.memory-service-cpu` | `linux/arm64` | `cpu-` |
| Local (Intel Mac) | `memory-service-cpu` | `Dockerfile.memory-service-cpu` | `linux/amd64` | `cpu-` |

## Alternatives Considered

### Alternative 1: Single Multi-Architecture Dockerfile with Build Args

Use a single Dockerfile with `ARG` to switch between CUDA and CPU base images.

```dockerfile
ARG VARIANT=gpu
FROM nvcr.io/nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 AS base-gpu
FROM python:3.11-slim AS base-cpu
FROM base-${VARIANT} AS final
```

**Pros:**
- Single Dockerfile to maintain
- Reduced code duplication
- Simpler CI/CD configuration

**Cons:**
- Docker multi-stage `FROM` with variables is limited and error-prone
- CUDA image layers (~5GB) downloaded even for CPU builds
- Build complexity increases debugging difficulty
- ARM64 builds fail if CUDA stage is evaluated

### Alternative 2: Unified CPU-Only Container for All Environments

Use CPU-only PyTorch everywhere, including production.

**Pros:**
- Simplest architecture
- Works on all platforms
- Lowest maintenance overhead

**Cons:**
- **10-100x slower inference** without GPU acceleration
- Defeats purpose of neural memory service (real-time requirements)
- Unacceptable for production latency SLAs
- Wastes GPU infrastructure investment

### Alternative 3: Docker Buildx Multi-Platform Builds

Use `docker buildx build --platform linux/amd64,linux/arm64` to create manifest lists.

**Pros:**
- Single command builds both architectures
- Automatic platform selection at pull time
- Industry-standard approach for multi-arch

**Cons:**
- **Cannot work for GPU images** - CUDA only supports x86_64
- Increases build time (parallel builds required)
- Requires buildx setup in CodeBuild
- Only solves CPU variant, not GPU/CPU split

### Alternative 4: Separate Repositories per Variant

Create distinct ECR repositories: `aura-memory-service-gpu-dev` and `aura-memory-service-cpu-dev`.

**Pros:**
- Clear separation of concerns
- Simpler tagging (no prefix needed)
- Easier IAM scoping per variant

**Cons:**
- Double the ECR repositories to manage
- Increased CloudFormation complexity
- Violates DRY principle
- Tags like `latest` become ambiguous across repos

## Consequences

### Positive

1. **Developer Experience**
   - Apple Silicon developers can build and run locally without emulation
   - Clear tagging convention eliminates confusion about which image to use
   - Fast iteration cycles (~2 min CPU build vs ~8 min GPU build)

2. **Production Performance**
   - GPU-optimized images with CUDA 12.1 and cuDNN 8 for inference
   - No CPU fallback logic overhead in production containers
   - Consistent performance characteristics per variant

3. **CI/CD Reliability**
   - No Docker Hub rate limit failures (NGC and ECR only)
   - Explicit build targets prevent accidental wrong-platform builds
   - Build matrix clearly documented for automation

4. **Registry Cost Control**
   - NVIDIA NGC: Free (no rate limits, no licensing)
   - ECR Public: Free (AWS-hosted)
   - Private ECR: ~$0.10/GB/month (minimal cost)
   - No Docker Hub Pro subscription required

5. **GovCloud Compatibility**
   - Private ECR works identically in Commercial and GovCloud
   - NGC accessible from both environments
   - No external Docker Hub dependency in production pipeline

### Negative

1. **Dual Dockerfile Maintenance**
   - Two Dockerfiles to keep synchronized
   - Risk of configuration drift between GPU and CPU variants
   - Duplicate dependency updates required

2. **Tagging Complexity**
   - Developers must remember to use correct tag prefix
   - `latest` alias could cause confusion if not documented
   - More tags to manage in ECR lifecycle policies

3. **Build Time Overhead**
   - CI/CD may need to build both variants for releases
   - GPU builds (~8 min) significantly slower than CPU (~2 min)
   - Storage for both variants in ECR

### Mitigation

1. **Dockerfile Drift Prevention**
   - Shared `requirements.txt` between both Dockerfiles
   - CI/CD validation that both Dockerfiles build successfully
   - Automated PR checks for Dockerfile changes affecting both variants

2. **Tagging Clarity**
   - Document tagging convention in `DEPLOYMENT_GUIDE.md`
   - `latest` always points to `gpu-latest` (production default)
   - Local development scripts default to `cpu-latest`

3. **ECR Lifecycle Policies**
   - Retain last 10 tagged images per variant
   - Delete untagged images after 7 days
   - Keep all semver-tagged images indefinitely

## Implementation

### CI/CD Build Commands

```bash
# Build GPU variant for production
aws codebuild start-build \
  --project-name aura-docker-build-dev \
  --environment-variables-override \
    name=BUILD_TARGET,value=memory-service \
    name=IMAGE_TAG,value=gpu-latest

# Build CPU variant for dev/testing
aws codebuild start-build \
  --project-name aura-docker-build-dev \
  --environment-variables-override \
    name=BUILD_TARGET,value=memory-service-cpu \
    name=IMAGE_TAG,value=cpu-latest

# Build versioned release (both variants)
aws codebuild start-build \
  --project-name aura-docker-build-prod \
  --environment-variables-override \
    name=BUILD_TARGET,value=memory-service \
    name=IMAGE_TAG,value=gpu-v1.2.3

aws codebuild start-build \
  --project-name aura-docker-build-prod \
  --environment-variables-override \
    name=BUILD_TARGET,value=memory-service-cpu \
    name=IMAGE_TAG,value=cpu-v1.2.3
```

### Local Development Workflow (Apple Silicon)

```bash
# Build CPU variant locally (no CodeBuild needed)
docker build \
  --platform linux/arm64 \
  -t aura-memory-service:cpu-local \
  -f deploy/docker/memory-service/Dockerfile.memory-service-cpu \
  .

# Run locally for testing
docker run --rm -p 50051:50051 -p 8080:8080 \
  -e ENVIRONMENT=local \
  aura-memory-service:cpu-local

# Alternatively, use docker-compose for full stack
docker-compose -f deploy/docker/docker-compose.dev.yml up memory-service
```

### Kubernetes Deployment (Production with GPU)

```yaml
# deploy/kubernetes/memory-service/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: memory-service
spec:
  template:
    spec:
      nodeSelector:
        # Schedule on GPU nodes only
        nvidia.com/gpu: "true"
      containers:
      - name: memory-service
        image: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/aura-memory-service-prod:gpu-latest
        resources:
          limits:
            nvidia.com/gpu: 1
            memory: "8Gi"
          requests:
            nvidia.com/gpu: 1
            memory: "4Gi"
```

### Kubernetes Deployment (Dev/QA without GPU)

```yaml
# deploy/kubernetes/memory-service/deployment-cpu.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: memory-service
spec:
  template:
    spec:
      # No node selector - runs on any node
      containers:
      - name: memory-service
        image: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/aura-memory-service-dev:cpu-latest
        resources:
          limits:
            memory: "4Gi"
            cpu: "2"
          requests:
            memory: "2Gi"
            cpu: "1"
```

### ECR Lifecycle Policy

```json
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "Keep last 10 gpu-* images",
      "selection": {
        "tagStatus": "tagged",
        "tagPrefixList": ["gpu-"],
        "countType": "imageCountMoreThan",
        "countNumber": 10
      },
      "action": { "type": "expire" }
    },
    {
      "rulePriority": 2,
      "description": "Keep last 10 cpu-* images",
      "selection": {
        "tagStatus": "tagged",
        "tagPrefixList": ["cpu-"],
        "countType": "imageCountMoreThan",
        "countNumber": 10
      },
      "action": { "type": "expire" }
    },
    {
      "rulePriority": 3,
      "description": "Delete untagged images after 7 days",
      "selection": {
        "tagStatus": "untagged",
        "countType": "sinceImagePushed",
        "countUnit": "days",
        "countNumber": 7
      },
      "action": { "type": "expire" }
    }
  ]
}
```

## Future Considerations

### Apple Silicon MPS Support

PyTorch supports Apple's Metal Performance Shaders (MPS) backend for GPU acceleration on Apple Silicon. However, this requires:

1. **macOS Host** - MPS only works on macOS, not in Linux containers
2. **No Docker Support** - Docker Desktop for Mac cannot pass MPS through to containers
3. **Native Installation** - Requires PyTorch installed directly on macOS

**When MPS becomes container-accessible:**
- Add `Dockerfile.memory-service-mps` for Apple Silicon GPU builds
- Update tagging: `mps-latest`, `mps-v{semver}`
- Add `BUILD_TARGET=memory-service-mps` to buildspec

**Current Workaround:** Developers on Apple Silicon use CPU variant for local development. MPS acceleration requires running the service natively (outside containers) during development.

### Multi-GPU Support

Production may require multi-GPU inference for larger models:

```yaml
resources:
  limits:
    nvidia.com/gpu: 4  # Request 4 GPUs
```

This requires:
- NVIDIA GPU Operator in EKS
- `p3.8xlarge` or `p4d.24xlarge` instances
- PyTorch distributed inference configuration

### AMD GPU Support (ROCm)

If AMD GPUs become cost-effective:
- Add `Dockerfile.memory-service-rocm` using `rocm/pytorch` base
- Add `rocm-` tag prefix
- Update node selectors for AMD GPU instances

## Decision Criteria Met

This ADR is appropriate because:

- [x] Affects container build and deployment strategy
- [x] Has cross-cutting impact (CI/CD, local dev, production)
- [x] Involves cost/complexity tradeoffs
- [x] Establishes patterns for future GPU-accelerated services
- [x] Documents platform compatibility constraints

## References

- ADR-003: EKS EC2 Nodes for GovCloud (GPU node group architecture)
- ADR-020: Private ECR Base Images (registry strategy)
- ADR-035: Dedicated Docker Build Project (buildspec-docker-build.yml)
- `deploy/docker/memory-service/Dockerfile.memory-service` - GPU Dockerfile
- `deploy/docker/memory-service/Dockerfile.memory-service-cpu` - CPU Dockerfile
- `deploy/buildspecs/buildspec-docker-build.yml` - CI/CD build configuration
- [NVIDIA NGC Catalog](https://catalog.ngc.nvidia.com/containers)
- [PyTorch Installation Matrix](https://pytorch.org/get-started/locally/)
- [AWS EKS GPU Support](https://docs.aws.amazon.com/eks/latest/userguide/gpu-ami.html)
