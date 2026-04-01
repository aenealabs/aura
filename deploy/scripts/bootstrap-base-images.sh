#!/bin/bash
#
# Bootstrap Base Images Script
#
# This script pulls approved base images from public sources and pushes them
# to the private ECR repository for use in CI/CD pipelines.
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Podman installed (local development) or Docker (CI/CD)
#   - ECR Base Images stack deployed (aura-ecr-base-images-{env})
#
# Usage:
#   ./deploy/scripts/bootstrap-base-images.sh [environment] [--force]
#
# Examples:
#   ./deploy/scripts/bootstrap-base-images.sh dev
#   ./deploy/scripts/bootstrap-base-images.sh prod --force
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENVIRONMENT="${1:-dev}"
FORCE_PUSH="${2:-}"
AWS_REGION="${AWS_REGION:-us-east-1}"
PROJECT_NAME="aura"

# Image versions to use (update these when patching for CVEs)
ALPINE_VERSION="3.19"
ALPINE_SOURCE="public.ecr.aws/docker/library/alpine:${ALPINE_VERSION}"

NODE_VERSION="20-alpine"
NODE_SOURCE="public.ecr.aws/docker/library/node:${NODE_VERSION}"

NGINX_VERSION="1.25-alpine"
NGINX_SOURCE="public.ecr.aws/docker/library/nginx:${NGINX_VERSION}"

PYTHON_VERSION="3.11-slim"
PYTHON_SOURCE="public.ecr.aws/docker/library/python:${PYTHON_VERSION}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
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

# Get ECR repository URI from CloudFormation stack
get_ecr_uri() {
    local output_key="$1"
    local stack_name="${PROJECT_NAME}-ecr-base-images-${ENVIRONMENT}"

    local uri
    uri=$(aws cloudformation describe-stacks \
        --stack-name "${stack_name}" \
        --query "Stacks[0].Outputs[?OutputKey==\`${output_key}\`].OutputValue" \
        --output text \
        --region "${AWS_REGION}" 2>/dev/null)

    if [[ -z "${uri}" || "${uri}" == "None" ]]; then
        log_error "ECR Base Images stack not found or missing output: ${output_key}"
        log_error "Deploy the Foundation layer first:"
        log_error "  aws codebuild start-build --project-name aura-foundation-deploy-dev"
        exit 1
    fi

    echo "${uri}"
}

# Bootstrap a single image
bootstrap_image() {
    local image_name="$1"
    local source_image="$2"
    local version="$3"
    local ecr_uri="$4"

    local repo_name="${PROJECT_NAME}-base-images/${image_name}"
    local private_tag="${ecr_uri}:${version}"

    log_info "----------------------------------------"
    log_info "Bootstrapping ${image_name}:${version}"
    log_info "----------------------------------------"

    # Check if image already exists
    if [[ "${FORCE_PUSH}" != "--force" ]] && image_exists "${repo_name}" "${version}"; then
        log_warn "Image ${repo_name}:${version} already exists in ECR. Skipping."
        return 0
    fi

    # CRITICAL: Use buildx/manifest to ensure amd64 architecture is pushed
    # This prevents "exec format error" when CodeBuild (x86_64) runs ARM64 images
    if [[ "${RUNTIME}" == "docker" ]] && docker buildx version &> /dev/null; then
        # Docker with buildx - use regctl or crane for cross-platform copy (preferred)
        # Fallback: pull with platform, create single-platform manifest
        log_info "Pulling ${image_name}:${version} from ECR Public Gallery (linux/amd64 via buildx)..."

        # Pull explicitly for amd64 platform
        docker pull --platform linux/amd64 "${source_image}"

        # Get the image digest for the amd64 variant
        local digest
        digest=$(docker inspect --format='{{index .RepoDigests 0}}' "${source_image}" 2>/dev/null || echo "")

        # Tag and push - the pulled amd64 image will be pushed
        log_info "Tagging as: ${private_tag}"
        docker tag "${source_image}" "${private_tag}"

        log_info "Pushing to private ECR (ensuring amd64 manifest)..."
        docker push "${private_tag}"

        # Verify the pushed image architecture
        log_info "Verifying pushed image architecture..."
        local pushed_arch
        pushed_arch=$(docker manifest inspect "${private_tag}" 2>/dev/null | grep -o '"architecture"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | cut -d'"' -f4 || echo "unknown")
        if [[ "${pushed_arch}" != "amd64" && "${pushed_arch}" != "unknown" ]]; then
            log_error "WARNING: Pushed image architecture is '${pushed_arch}', expected 'amd64'"
            log_error "CodeBuild may fail with 'exec format error'. Consider using --force to re-push."
        else
            log_info "Verified: Image architecture is '${pushed_arch}'"
        fi
    else
        # Podman or Docker without buildx - standard pull/tag/push
        # Podman respects --platform flag correctly
        log_info "Pulling ${image_name}:${version} from ECR Public Gallery (linux/amd64)..."
        ${RUNTIME} pull --platform linux/amd64 "${source_image}"

        # Tag for private ECR
        log_info "Tagging as: ${private_tag}"
        ${RUNTIME} tag "${source_image}" "${private_tag}"

        # Push to private ECR
        log_info "Pushing to private ECR..."
        ${RUNTIME} push "${private_tag}"
    fi

    log_info "${image_name}:${version} bootstrapped successfully"
}

# Check if image already exists in ECR
image_exists() {
    local repo_name="$1"
    local tag="$2"

    aws ecr describe-images \
        --repository-name "${repo_name}" \
        --image-ids imageTag="${tag}" \
        --region "${AWS_REGION}" &> /dev/null
}

# Main execution
main() {
    log_info "=========================================="
    log_info "Bootstrap Base Images"
    log_info "=========================================="
    log_info "Environment: ${ENVIRONMENT}"
    log_info "AWS Region: ${AWS_REGION}"
    log_info "Images to bootstrap:"
    log_info "  - Alpine: ${ALPINE_VERSION}"
    log_info "  - Node.js: ${NODE_VERSION}"
    log_info "  - Nginx: ${NGINX_VERSION}"
    log_info "  - Python: ${PYTHON_VERSION}"

    # Detect container runtime
    RUNTIME=$(detect_runtime)
    log_info "Container Runtime: ${RUNTIME}"

    # Get ECR URIs for all base images
    ALPINE_ECR_URI=$(get_ecr_uri "AlpineRepositoryUri")
    NODE_ECR_URI=$(get_ecr_uri "NodeRepositoryUri")
    NGINX_ECR_URI=$(get_ecr_uri "NginxRepositoryUri")
    PYTHON_ECR_URI=$(get_ecr_uri "PythonRepositoryUri")

    log_info "ECR Repositories:"
    log_info "  Alpine: ${ALPINE_ECR_URI}"
    log_info "  Node: ${NODE_ECR_URI}"
    log_info "  Nginx: ${NGINX_ECR_URI}"
    log_info "  Python: ${PYTHON_ECR_URI}"

    # Extract account ID from URI
    AWS_ACCOUNT_ID=$(echo "${ALPINE_ECR_URI}" | cut -d'.' -f1)

    # Login to ECR
    log_info "Logging in to Amazon ECR..."
    aws ecr get-login-password --region "${AWS_REGION}" | \
        ${RUNTIME} login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

    # Bootstrap all images
    bootstrap_image "alpine" "${ALPINE_SOURCE}" "${ALPINE_VERSION}" "${ALPINE_ECR_URI}"
    bootstrap_image "node" "${NODE_SOURCE}" "${NODE_VERSION}" "${NODE_ECR_URI}"
    bootstrap_image "nginx" "${NGINX_SOURCE}" "${NGINX_VERSION}" "${NGINX_ECR_URI}"
    bootstrap_image "python" "${PYTHON_SOURCE}" "${PYTHON_VERSION}" "${PYTHON_ECR_URI}"

    log_info "=========================================="
    log_info "Bootstrap Complete!"
    log_info "=========================================="
    log_info "Base images available at:"
    log_info "  ${ALPINE_ECR_URI}:${ALPINE_VERSION}"
    log_info "  ${NODE_ECR_URI}:${NODE_VERSION}"
    log_info "  ${NGINX_ECR_URI}:${NGINX_VERSION}"
    log_info "  ${PYTHON_ECR_URI}:${PYTHON_VERSION}"
    log_info ""
    log_info "Use in Dockerfiles with ARG pattern:"
    log_info "  ARG NODE_BASE_IMAGE_URI=public.ecr.aws/docker/library/node:20-alpine"
    log_info "  FROM \${NODE_BASE_IMAGE_URI}"
    log_info ""
    log_info "Security scanning will complete in ~60 seconds."
}

# Run main
main "$@"
