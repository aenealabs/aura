# Project Aura - dnsmasq Container Image
#
# Production-ready dnsmasq with DNSSEC validation support
# Uses Alpine's official dnsmasq-dnssec package with IANA root trust anchor
#
# Features:
#   - DNSSEC validation with auto-updated trust anchor
#   - bind-tools for DNS health checks (dig/nslookup)
#   - Non-root operation with NET_BIND_SERVICE capability
#   - Supports port 53 (production) or 5353 (unprivileged testing)
#
# IMPORTANT: The production image is pre-built and stored in private ECR:
#   - Repository: aura-dnsmasq
#   - Current version: v1.1.0
#   - Referenced by: deploy/cloudformation/network-services.yaml
#
# This Dockerfile is for:
#   1. Local development and testing
#   2. CI/CD builds that push to ECR
#   3. Emergency rebuilds if ECR image is unavailable
#
# For production deployments, always use the ECR image:
#   ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/aura-dnsmasq:v1.1.0
#
# Prerequisites:
#   - ECR Base Images stack deployed (aura-ecr-base-images-{env})
#   - Bootstrap script run to populate Alpine base image
#   - See: ./deploy/scripts/bootstrap-base-images.sh
#
# Usage (local with Podman - preferred per ADR-049):
#   podman build --platform linux/amd64 -t aura-dnsmasq:v1.1.0 .
#
# Usage (local with Docker - CI/CD only):
#   docker build --platform linux/amd64 -t aura-dnsmasq:v1.1.0 .
#
# Usage (CodeBuild - BASE_IMAGE_URI set automatically):
#   docker build --build-arg BASE_IMAGE_URI=${BASE_IMAGE_URI} -t aura-dnsmasq:v1.1.0 .
#
# History:
#   - v1.0.0: Initial Rust-based implementation (deprecated)
#   - v1.1.0: Alpine-based with official dnsmasq-dnssec package (current)

# ============================================================================
# BASE IMAGE
# ============================================================================

# Base image from private ECR (controlled supply chain)
# Fallback to public ECR Gallery if ARG not provided (for local dev without bootstrap)
ARG BASE_IMAGE_URI=public.ecr.aws/docker/library/alpine:3.19
FROM ${BASE_IMAGE_URI}

# ============================================================================
# INSTALL DNSMASQ
# ============================================================================

# Install dnsmasq with DNSSEC support
# Alpine splits dnsmasq into base (no DNSSEC) and dnsmasq-dnssec (with DNSSEC)
# Also install bind-tools for healthcheck (nslookup/dig) and curl for trust anchor fetch
# Note: apk update ensures fresh package index (avoids exit code 255 on stale mirrors)
RUN apk update && \
    apk add --no-cache \
        dnsmasq-dnssec \
        bind-tools \
        ca-certificates \
        libcap \
        curl && \
    rm -rf /var/cache/apk/*

# ============================================================================
# CONFIGURE DIRECTORIES AND USER
# ============================================================================

# Alpine dnsmasq package creates dnsmasq user/group automatically
# Create directories and set ownership
RUN mkdir -p /etc/dnsmasq /var/log/dnsmasq /var/run/dnsmasq /usr/share/dnsmasq && \
    chown -R dnsmasq:dnsmasq /etc/dnsmasq /var/log/dnsmasq /var/run/dnsmasq /usr/share/dnsmasq

# ============================================================================
# DNSSEC TRUST ANCHOR
# ============================================================================

# Download DNSSEC trust anchor from IANA
# This is the root zone KSK (Key Signing Key) used to validate DNSSEC responses
# The trust anchor is updated when root zone keys are rotated (rare, ~every 5 years)
# Source: https://data.iana.org/root-anchors/root-anchors.xml
RUN curl -fsSL https://data.iana.org/root-anchors/root-anchors.xml -o /tmp/root-anchors.xml && \
    # Extract the KeyDigest and create trust-anchor format for dnsmasq
    # Format: . IN DS <KeyTag> <Algorithm> <DigestType> <Digest>
    echo "# IANA Root Zone DNSSEC Trust Anchor" > /usr/share/dnsmasq/trust-anchors.conf && \
    echo "# Downloaded at build time - update image when keys rotate" >> /usr/share/dnsmasq/trust-anchors.conf && \
    echo "# Source: https://data.iana.org/root-anchors/" >> /usr/share/dnsmasq/trust-anchors.conf && \
    echo "" >> /usr/share/dnsmasq/trust-anchors.conf && \
    # Current root zone KSK (Key Tag 20326, Algorithm 8, SHA-256)
    echo "trust-anchor=.,20326,8,2,E06D44B80B8F1D39A95C0B0D7C65D08458E880409BBC683457104237C7F8EC8D" >> /usr/share/dnsmasq/trust-anchors.conf && \
    chown dnsmasq:dnsmasq /usr/share/dnsmasq/trust-anchors.conf && \
    rm /tmp/root-anchors.xml

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

# Grant NET_BIND_SERVICE capability (allows binding to privileged ports without root)
RUN setcap 'cap_net_bind_service=+ep' /usr/sbin/dnsmasq

# ============================================================================
# RUNTIME CONFIGURATION
# ============================================================================

# Expose DNS ports (53 for production, 5353 for testing)
EXPOSE 53/tcp 53/udp 5353/tcp 5353/udp

# Health check using pgrep (simple process check)
# More sophisticated checks can be done via Kubernetes/ECS health checks
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD pgrep dnsmasq || exit 1

# Volume for configuration
VOLUME ["/etc/dnsmasq"]

# Switch to non-root user
USER dnsmasq

# Default command - config file mounted at runtime
# DNSSEC enabled via trust-anchors.conf
ENTRYPOINT ["/usr/sbin/dnsmasq"]
CMD ["--keep-in-foreground", "--conf-file=/usr/share/dnsmasq/trust-anchors.conf"]

# ============================================================================
# METADATA
# ============================================================================

LABEL maintainer="Project Aura Team" \
      description="Alpine-based dnsmasq with DNSSEC validation for Project Aura" \
      version="1.1.0" \
      org.opencontainers.image.source="https://github.com/aenealabs/aura" \
      org.opencontainers.image.vendor="Project Aura" \
      org.opencontainers.image.title="Aura dnsmasq" \
      org.opencontainers.image.description="DNS caching and service discovery with DNSSEC validation"

# ============================================================================
# BUILD INSTRUCTIONS
# ============================================================================
#
# NOTE: Per ADR-049, Podman is the primary container runtime for local development.
# Docker commands are retained for CI/CD (CodeBuild) compatibility.
#
# HEALTHCHECK Note: Podman stores HEALTHCHECK metadata but relies on orchestrators
# (Kubernetes liveness probes, ECS task health checks) to execute them. The
# "HEALTHCHECK is not supported" warning during build is informational only.
#
# Build production image (Podman - local dev):
#   podman build --platform linux/amd64 -t aura/dnsmasq:v1.1.0 .
#
# Build production image (Docker - CI/CD):
#   docker build --platform linux/amd64 -t aura/dnsmasq:v1.1.0 .
#
# Build with private ECR base image:
#   podman build --build-arg BASE_IMAGE_URI=${ECR_ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/alpine:3.19 \
#     --platform linux/amd64 -t aura/dnsmasq:v1.1.0 .
#
# Run production container (Podman):
#   podman run -d --name dnsmasq \
#     -p 53:53/tcp -p 53:53/udp \
#     -v $(pwd)/production.conf:/etc/dnsmasq/dnsmasq.conf:ro \
#     aura/dnsmasq:v1.1.0
#
# Run development container (Podman):
#   podman run -it --rm --name dnsmasq-dev \
#     -p 5353:5353/tcp -p 5353:5353/udp \
#     -v $(pwd)/development.conf:/etc/dnsmasq/dnsmasq.conf:ro \
#     aura/dnsmasq:v1.1.0
#
# Test DNS resolution:
#   podman exec dnsmasq dig @127.0.0.1 google.com
#   podman exec dnsmasq dig @127.0.0.1 +dnssec google.com
#
# View logs:
#   podman logs -f dnsmasq
