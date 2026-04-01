# Project Aura - Sandbox Runtime Container Image
#
# Isolated container for patch testing in ephemeral sandboxes
# Maximum security: no capabilities, no network access (except internal DNS)
#
# Usage (Podman - primary per ADR-049):
#   podman build --platform linux/amd64 -t aura/sandbox-runtime:latest -f Dockerfile ../../..
#   podman run --security-opt=no-new-privileges --cap-drop=ALL aura/sandbox-runtime:latest
#
# Usage (Docker - CI/CD fallback):
#   docker build -t aura/sandbox-runtime:latest -f Dockerfile ../../..
#   docker run --security-opt=no-new-privileges --cap-drop=ALL aura/sandbox-runtime:latest

# ============================================================================
# Base Image Configuration
# ============================================================================
# Default to ECR Public Gallery for local development
# CI/CD overrides with private ECR via --build-arg for controlled supply chain
ARG PYTHON_BASE_IMAGE=public.ecr.aws/docker/library/python:3.11-slim

# ============================================================================
# STAGE 1: BUILDER
# ============================================================================

FROM ${PYTHON_BASE_IMAGE} AS builder

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

FROM ${PYTHON_BASE_IMAGE} AS runtime

# Suppress debconf warnings in non-interactive builds
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for sandbox
RUN useradd -m -u 2000 -s /bin/bash sandbox

# Set working directory
WORKDIR /sandbox

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/sandbox/.local

# Copy sandbox runtime code
COPY src/services/sandbox_network_service.py ./
COPY deploy/config/sandbox/ ./config/

# Create necessary directories
RUN mkdir -p \
    /sandbox/workspace \
    /sandbox/logs \
    /sandbox/patches \
    && chown -R sandbox:sandbox /sandbox

# Switch to non-root user
USER sandbox

# Add local bin to PATH
ENV PATH=/home/sandbox/.local/bin:$PATH

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    SANDBOX_ID=unset \
    ISOLATION_LEVEL=container \
    MAX_RUNTIME=3600 \
    LOG_LEVEL=INFO

# No exposed ports (sandboxes are isolated)

# Health check (simple process check)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD pgrep -f python || exit 1

# Volume for patch workspace
VOLUME ["/sandbox/workspace", "/sandbox/logs"]

# Default command (run patch test)
ENTRYPOINT ["python", "sandbox_network_service.py"]
CMD ["--mode", "test"]

# Metadata
LABEL maintainer="Project Aura Team" \
      description="Isolated sandbox runtime for patch testing" \
      version="1.0.0" \
      security.level="maximum" \
      isolation.type="container" \
      org.opencontainers.image.source="https://github.com/project-aura/aura" \
      org.opencontainers.image.vendor="Project Aura" \
      org.opencontainers.image.title="Aura Sandbox Runtime"

# ============================================================================
# SECURITY NOTES
# ============================================================================
#
# This container must be run with maximum security restrictions:
#
# 1. Drop ALL Linux capabilities:
#    --cap-drop=ALL
#
# 2. No new privileges:
#    --security-opt=no-new-privileges
#
# 3. Read-only root filesystem (optional):
#    --read-only --tmpfs /tmp
#
# 4. Network isolation:
#    ECS Security Group blocks external network access
#    Only internal DNS (10.0.0.0/16) allowed
#
# 5. Resource limits:
#    CPU: 1 vCPU max
#    Memory: 2GB max
#    Runtime: 1 hour max (enforced by task timeout)
#
# Example ECS Fargate run:
#   aws ecs run-task \
#     --cluster aura-sandboxes-dev \
#     --task-definition sandbox-patch-test-dev \
#     --launch-type FARGATE \
#     --network-configuration '{
#       "awsvpcConfiguration": {
#         "subnets": ["subnet-xxx"],
#         "securityGroups": ["sg-sandbox-isolated"],
#         "assignPublicIp": "DISABLED"
#       }
#     }' \
#     --overrides '{
#       "containerOverrides": [{
#         "name": "sandbox-runtime",
#         "environment": [
#           {"name": "SANDBOX_ID", "value": "sandbox-abc123"},
#           {"name": "PATCH_ID", "value": "patch-def456"}
#         ]
#       }]
#     }'
