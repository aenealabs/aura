#!/bin/bash
#
# Build and Push SSR Container Images
#
# Builds the SSR bug-injection and bug-solving container images using
# private ECR base images and pushes them to the SSR ECR repositories.
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Podman or Docker installed
#   - ECR repositories created (aura-ssr-bug-injection, aura-ssr-bug-solving)
#   - Private base images available in ECR (aura-base-images/python)
#
# Usage:
#   ./deploy/scripts/build-ssr-images.sh [environment]
#
# Examples:
#   ./deploy/scripts/build-ssr-images.sh dev
#   ./deploy/scripts/build-ssr-images.sh prod

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENVIRONMENT="${1:-dev}"
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
PROJECT_NAME="aura"

# ECR URIs
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
PYTHON_BASE_IMAGE="${ECR_REGISTRY}/aura-base-images/python:3.11-slim"
BUG_INJECTION_REPO="${ECR_REGISTRY}/aura-ssr-bug-injection"
BUG_SOLVING_REPO="${ECR_REGISTRY}/aura-ssr-bug-solving"

# Image tag (use git commit hash for traceability)
GIT_COMMIT=$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD 2>/dev/null || echo "latest")
IMAGE_TAG="${GIT_COMMIT}"
LATEST_TAG="latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect container runtime (Podman preferred for local dev)
detect_runtime() {
    if command -v podman &> /dev/null; then
        echo "podman"
    elif command -v docker &> /dev/null; then
        echo "docker"
    else
        log_error "No container runtime found. Install Podman or Docker."
        exit 1
    fi
}

# Login to ECR
ecr_login() {
    local runtime="$1"
    log_info "Logging in to ECR..."
    aws ecr get-login-password --region "${AWS_REGION}" | \
        ${runtime} login --username AWS --password-stdin "${ECR_REGISTRY}"
}

# Build and push image
build_and_push() {
    local runtime="$1"
    local dockerfile="$2"
    local repo="$3"
    local name="$4"

    log_info "Building ${name}..."
    log_info "  Dockerfile: ${dockerfile}"
    log_info "  Base image: ${PYTHON_BASE_IMAGE}"
    log_info "  Target: ${repo}:${IMAGE_TAG}"

    # Build with private base image
    ${runtime} build \
        --platform linux/amd64 \
        --build-arg "PYTHON_BASE_IMAGE=${PYTHON_BASE_IMAGE}" \
        -f "${dockerfile}" \
        -t "${repo}:${IMAGE_TAG}" \
        -t "${repo}:${LATEST_TAG}" \
        "${PROJECT_ROOT}"

    log_info "Pushing ${name} to ECR..."
    ${runtime} push "${repo}:${IMAGE_TAG}"
    ${runtime} push "${repo}:${LATEST_TAG}"

    log_info "${name} pushed successfully: ${repo}:${IMAGE_TAG}"
}

# Verify base image exists
verify_base_image() {
    local runtime="$1"

    log_info "Verifying private base image exists..."
    if ! ${runtime} pull "${PYTHON_BASE_IMAGE}" 2>/dev/null; then
        log_error "Private base image not found: ${PYTHON_BASE_IMAGE}"
        log_error "Run ./deploy/scripts/bootstrap-base-images.sh ${ENVIRONMENT} first"
        exit 1
    fi
    log_info "Base image verified: ${PYTHON_BASE_IMAGE}"
}

# Main
main() {
    log_info "=============================================="
    log_info "SSR Container Images Build"
    log_info "=============================================="
    log_info "Environment: ${ENVIRONMENT}"
    log_info "AWS Account: ${AWS_ACCOUNT_ID}"
    log_info "AWS Region: ${AWS_REGION}"
    log_info "Git Commit: ${GIT_COMMIT}"
    log_info ""

    # Detect runtime
    RUNTIME=$(detect_runtime)
    log_info "Using container runtime: ${RUNTIME}"

    # Login to ECR
    ecr_login "${RUNTIME}"

    # Verify base image
    verify_base_image "${RUNTIME}"

    # Build and push bug-injection image
    build_and_push "${RUNTIME}" \
        "${PROJECT_ROOT}/deploy/docker/ssr/Dockerfile.bug-injection" \
        "${BUG_INJECTION_REPO}" \
        "Bug Injection Agent"

    # Build and push bug-solving image
    build_and_push "${RUNTIME}" \
        "${PROJECT_ROOT}/deploy/docker/ssr/Dockerfile.bug-solving" \
        "${BUG_SOLVING_REPO}" \
        "Bug Solving Agent"

    log_info ""
    log_info "=============================================="
    log_info "SSR Container Images Build Complete"
    log_info "=============================================="
    log_info "Bug Injection: ${BUG_INJECTION_REPO}:${IMAGE_TAG}"
    log_info "Bug Solving: ${BUG_SOLVING_REPO}:${IMAGE_TAG}"
}

main "$@"
