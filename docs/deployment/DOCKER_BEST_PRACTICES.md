# Container Build Best Practices

**Project Aura - Dockerfile Standards for Clean CI/CD Builds**

**Last Updated:** January 4, 2026
**Applies To:** All Debian-based Dockerfiles (python:*-slim, debian:*)

---

## Overview

This document describes the container build standards implemented across Project Aura to ensure clean, warning-free CI/CD pipeline builds. These practices apply to both Podman (local development) and Docker (CI/CD in CodeBuild) builds, eliminating noisy log output that can obscure genuine errors and improve pipeline reliability.

### Container Runtime Strategy (ADR-049)

Per ADR-049, Project Aura uses a dual container runtime approach:

| Environment | Runtime | Rationale |
|-------------|---------|-----------|
| **Local Development** | Podman (primary) | Avoids Docker Desktop licensing fees ($5-24/user/month) |
| **CI/CD Pipelines** | Docker (CodeBuild) | Native AWS integration with buildspec commands |

**Key Points:**
- Podman and Docker use identical Dockerfile syntax
- Commands are interchangeable: `podman build` vs `docker build`
- HEALTHCHECK warnings in Podman are informational only (Kubernetes/ECS use their own health checks)
- `podman compose` reads standard `docker-compose.yml` files natively

---

## Quick Reference

All Debian-based Dockerfiles should include these patterns:

```dockerfile
# Builder stage
FROM python:3.11-slim AS builder

# Suppress debconf warnings in non-interactive builds
ENV DEBIAN_FRONTEND=noninteractive

# Pip security hardening and suppress script location warnings
ENV PIP_ROOT_USER_ACTION=ignore \
    PIP_NO_CACHE_DIR=true \
    PATH=/root/.local/bin:$PATH

# Install Python dependencies (suppress script warnings)
RUN pip install --no-cache-dir --user --no-warn-script-location -r requirements.txt
```

---

## Best Practice 1: DEBIAN_FRONTEND=noninteractive

### What It Does

Suppresses debconf fallback warnings during `apt-get install` in non-interactive (CI/CD) builds.

### The Problem

Without this setting, Docker builds using `apt-get install` produce these warnings:

```
debconf: unable to initialize frontend: Dialog
debconf: (No usable dialog-like program is installed, so the dialog based frontend cannot be used...)
debconf: falling back to frontend: Readline
debconf: falling back to frontend: Teletype
debconf: falling back to frontend: Noninteractive
```

These warnings occur because:
1. debconf attempts to use the Dialog frontend (interactive terminal UI)
2. No TTY or dialog program exists in CI/CD environments
3. debconf falls through multiple frontends before settling on Noninteractive

### The Solution

```dockerfile
# Set at the beginning of each stage that uses apt-get
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*
```

### Why Both Stages Need It

Multi-stage builds require this environment variable in each stage that runs `apt-get`:

```dockerfile
# STAGE 1: BUILDER
FROM python:3.11-slim AS builder
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y ...

# STAGE 2: RUNTIME
FROM python:3.11-slim AS runtime
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y ...
```

Environment variables do not carry between stages in multi-stage builds.

---

## Best Practice 2: pip --no-warn-script-location

### What It Does

Suppresses PATH warnings when pip installs packages with executable scripts to a non-standard location.

### The Problem

When using `pip install --user` (which installs to `/root/.local/bin`), pip generates warnings:

```
WARNING: The script uvicorn is installed in '/root/.local/bin' which is not on PATH.
WARNING: The script pytest is installed in '/root/.local/bin' which is not on PATH.
WARNING: The scripts black and blackd are installed in '/root/.local/bin' which is not on PATH.
```

These warnings are informational but:
1. Clutter CI/CD logs, making it harder to spot real errors
2. Appear repeatedly for each package with scripts
3. Are false positives when PATH is configured correctly

### The Solution

```dockerfile
# Combined with other pip environment settings
ENV PIP_ROOT_USER_ACTION=ignore \
    PIP_NO_CACHE_DIR=true \
    PATH=/root/.local/bin:$PATH

# Use --no-warn-script-location in the install command
RUN pip install --no-cache-dir --user --no-warn-script-location -r requirements.txt
```

### Why We Also Set PATH

Adding `/root/.local/bin` to PATH ensures the scripts are actually usable:

```dockerfile
ENV PATH=/root/.local/bin:$PATH
```

This makes the warning suppression valid - we are configuring the PATH correctly.

---

## Best Practice 3: Standard Python Multi-Stage Pattern

### Complete Template

This is the standard pattern for all Project Aura Python service Dockerfiles:

```dockerfile
# ============================================================================
# STAGE 1: BUILDER
# ============================================================================

FROM python:3.11-slim AS builder

# Suppress debconf warnings in non-interactive builds
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Pip security hardening and suppress script location warnings
ENV PIP_ROOT_USER_ACTION=ignore \
    PIP_NO_CACHE_DIR=true \
    PATH=/root/.local/bin:$PATH

# Copy dependency files
COPY requirements.txt .

# Install Python dependencies (suppress script warnings)
RUN pip install --no-cache-dir --user --no-warn-script-location -r requirements.txt

# ============================================================================
# STAGE 2: RUNTIME
# ============================================================================

FROM python:3.11-slim AS runtime

# Suppress debconf warnings in non-interactive builds
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (UID 1000 for Kubernetes compatibility)
RUN useradd -m -u 1000 -s /bin/bash aura

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/aura/.local

# Copy application code
COPY src/ ./src/

# Set ownership
RUN chown -R aura:aura /app

# Switch to non-root user
USER aura

# Add local bin to PATH
ENV PATH=/home/aura/.local/bin:$PATH

# Expose service port
EXPOSE 8080

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Default command
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Key Elements

| Element | Purpose |
|---------|---------|
| `DEBIAN_FRONTEND=noninteractive` | Suppress debconf warnings |
| `PIP_ROOT_USER_ACTION=ignore` | Suppress pip root user warning |
| `PIP_NO_CACHE_DIR=true` | Reduce image size (same as --no-cache-dir) |
| `PATH=/root/.local/bin:$PATH` | Make pip scripts executable |
| `--no-warn-script-location` | Suppress PATH warnings |
| `--no-install-recommends` | Minimize apt package installs |
| `rm -rf /var/lib/apt/lists/*` | Clean up apt cache |
| `useradd -m -u 1000` | Kubernetes-compatible non-root user |

---

## Dockerfiles Following These Standards

### Updated (Debian-based)

| Dockerfile | Service |
|------------|---------|
| `deploy/docker/api/Dockerfile.api` | FastAPI application |
| `deploy/docker/agents/Dockerfile.agent` | Generic agent image |
| `deploy/docker/agents/Dockerfile.orchestrator` | Agent orchestrator |
| `deploy/docker/agents/Dockerfile.runtime-incident` | Runtime incident agent |
| `deploy/docker/memory-service/Dockerfile.memory-service-cpu` | Memory service (CPU) |
| `deploy/docker/sandbox/Dockerfile` | Sandbox environment |
| `deploy/docker/sandbox/Dockerfile.test-runner` | Sandbox test runner |

### Not Updated (Different Base Images)

| Dockerfile | Base Image | Notes |
|------------|------------|-------|
| `deploy/docker/dnsmasq/Dockerfile.alpine` | Alpine Linux | Uses `apk`, not `apt-get` |
| `deploy/docker/frontend/Dockerfile.frontend` | Node.js | No Debian package manager usage |

---

## Verification

### Check for debconf Warnings

Run a container build and verify no debconf fallback messages appear:

```bash
# Podman (local development - primary per ADR-049)
podman build --platform linux/amd64 -t test-image -f deploy/docker/api/Dockerfile.api . 2>&1 | grep -i "debconf"
# Should return no results

# Docker (CI/CD fallback)
docker build -t test-image -f deploy/docker/api/Dockerfile.api . 2>&1 | grep -i "debconf"
# Should return no results
```

### Check for pip PATH Warnings

Verify no script location warnings during pip install:

```bash
# Podman (local development - primary per ADR-049)
podman build --platform linux/amd64 -t test-image -f deploy/docker/api/Dockerfile.api . 2>&1 | grep -i "not on PATH"
# Should return no results

# Docker (CI/CD fallback)
docker build -t test-image -f deploy/docker/api/Dockerfile.api . 2>&1 | grep -i "not on PATH"
# Should return no results
```

### CodeBuild Log Review

After CI/CD builds, review CloudWatch Logs for clean output:

```bash
aws logs tail /aws/codebuild/aura-application-deploy-dev --since 1h | grep -E "(debconf|not on PATH)"
# Should return no results
```

---

## Related Documentation

- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Full deployment procedures
- [CICD_SETUP_GUIDE.md](CICD_SETUP_GUIDE.md) - CI/CD pipeline configuration
- [ADR-020](../architecture-decisions/ADR-020-private-ecr-base-images.md) - Private ECR base images strategy

---

## References

- [Debian debconf documentation](https://manpages.debian.org/bullseye/debconf-doc/debconf.7.en.html)
- [pip documentation: --no-warn-script-location](https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-no-warn-script-location)
- [Docker multi-stage builds](https://docs.docker.com/build/building/multi-stage/)
