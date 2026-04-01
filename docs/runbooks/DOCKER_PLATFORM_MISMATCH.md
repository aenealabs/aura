# Runbook: Container Platform Mismatch (ARM64 vs AMD64)

**Purpose:** Resolve container build failures caused by architecture mismatch between base images and build environment

**Audience:** DevOps Engineers, Platform Team, On-call Engineers

**Estimated Time:** 15-30 minutes

**Last Updated:** January 4, 2026

---

## Container Runtime Strategy (ADR-049)

Per ADR-049, Project Aura uses a dual container runtime approach:

| Environment | Runtime | Notes |
|-------------|---------|-------|
| **Local Development** | Podman (primary) | Avoids Docker Desktop licensing fees |
| **CI/CD Pipelines** | Docker (CodeBuild) | Native AWS integration |

Commands are interchangeable: `podman build` vs `docker build`. This runbook applies to both runtimes.

---

## Problem Description

Docker builds fail with `exec format error` (exit code 255) when:
- Base images are built/pushed from ARM64 machines (Apple Silicon Macs)
- CodeBuild or EKS runs on x86_64 (AMD64) architecture

### Symptoms

```
#6 [2/5] RUN apk update && apk add --no-cache dnsmasq-dnssec...
#6 0.473 exec /bin/sh: exec format error
#6 ERROR: process "/bin/sh -c apk update..." did not complete successfully: exit code: 255

WARNING: InvalidBaseImagePlatform: Base image was pulled with platform "linux/arm64",
expected "linux/amd64" for current build
```

### Root Cause

The private ECR base image repository (`aura-base-images/alpine:3.19`) contains an ARM64 image that was pushed from an Apple Silicon Mac without specifying the target platform.

---

## Quick Resolution

### Option A: Use Public ECR Fallback (Immediate Fix)

The buildspec automatically falls back to public ECR if the private image has wrong architecture. Verify this is working:

```bash
# Check latest build logs for fallback message
aws logs tail /aws/codebuild/aura-application-deploy-dev \
  --since 30m \
  --format short | grep -i "fallback\|architecture"
```

Expected output:
```
WARNING: Private ECR base image has wrong architecture (arm64), using public ECR fallback...
Using fallback base image: public.ecr.aws/docker/library/alpine:3.19
```

### Option B: Re-bootstrap Base Images (Permanent Fix)

Re-run the bootstrap script with `--force` to replace ARM64 images with AMD64:

```bash
# From an x86_64 machine or with explicit platform flag
cd /path/to/aura

# Re-bootstrap all base images (forces re-push even if exists)
./deploy/scripts/bootstrap-base-images.sh dev --force
```

**Important:** The bootstrap script already includes `--platform linux/amd64` flags, but must be run from a machine with proper Docker/Podman support for cross-platform pulls.

---

## Detailed Diagnostic Steps

### Step 1: Identify the Failing Build

```bash
# Get the latest failed build
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-application-deploy-dev \
  --query 'ids[0]' \
  --output text)

# Check build status and failure reason
aws codebuild batch-get-builds --ids $BUILD_ID \
  --query 'builds[0].{status:buildStatus,phase:currentPhase,reason:buildStatusReason}'
```

### Step 2: Check Base Image Architecture

```bash
# Get the base image URI from CloudFormation
BASE_IMAGE_URI=$(aws cloudformation describe-stacks \
  --stack-name aura-ecr-base-images-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`AlpineRepositoryUri`].OutputValue' \
  --output text)

echo "Base Image URI: ${BASE_IMAGE_URI}:3.19"

# Check the image architecture using Docker manifest
docker manifest inspect ${BASE_IMAGE_URI}:3.19 2>/dev/null | \
  jq '.manifests[].platform' || \
  echo "Use AWS ECR to check image details"

# Alternative: Use AWS ECR to check image
aws ecr describe-images \
  --repository-name aura-base-images/alpine \
  --image-ids imageTag=3.19 \
  --query 'imageDetails[0].{digest:imageDigest,size:imageSizeInBytes}'
```

### Step 3: Verify Bootstrap Script Configuration

```bash
# Check the bootstrap script has correct platform flags
grep -n "platform" deploy/scripts/bootstrap-base-images.sh

# Expected output should show:
# --platform linux/amd64
```

---

## Resolution Procedures

### Procedure 1: Re-bootstrap from x86_64 Machine

If you have access to an x86_64 (Intel/AMD) machine:

```bash
# 1. Clone the repository
git clone https://github.com/aenealabs/aura.git
cd aura

# 2. Configure AWS credentials
aws configure  # or use SSO: aws sso login --profile aura-admin

# 3. Run bootstrap with force flag
./deploy/scripts/bootstrap-base-images.sh dev --force

# 4. Verify the pushed image architecture
aws ecr describe-images \
  --repository-name aura-base-images/alpine \
  --image-ids imageTag=3.19
```

### Procedure 2: Re-bootstrap from ARM64 Mac with Docker Desktop

Docker Desktop on Apple Silicon can build/pull for different platforms:

```bash
# 1. Ensure Docker Desktop is running with Rosetta emulation enabled
# Settings > General > Use Rosetta for x86/amd64 emulation

# 2. Verify Docker can pull amd64 images
docker pull --platform linux/amd64 alpine:3.19
docker inspect alpine:3.19 --format '{{.Architecture}}'
# Should output: amd64

# 3. Run bootstrap with force flag
./deploy/scripts/bootstrap-base-images.sh dev --force
```

### Procedure 3: Delete and Let CodeBuild Use Public ECR

If re-bootstrapping is not immediately possible:

```bash
# 1. Delete the incorrectly-tagged image from ECR
aws ecr batch-delete-image \
  --repository-name aura-base-images/alpine \
  --image-ids imageTag=3.19

# 2. Re-run CodeBuild - it will use the public ECR fallback
aws codebuild start-build --project-name aura-application-deploy-dev
```

---

## Prevention

### 1. Buildspec Safeguards (Already Implemented)

The `buildspec-application.yml` now includes:

```yaml
# Architecture verification before using private ECR
docker pull --platform linux/amd64 "${BASE_IMAGE_URI}" 2>/dev/null || USE_FALLBACK=true
ARCH=$(docker inspect "${BASE_IMAGE_URI}" --format '{{.Architecture}}')
if [[ "$ARCH" != "amd64" && "$ARCH" != "x86_64" ]]; then
  USE_FALLBACK=true
fi

# Explicit platform in Docker build
docker build --platform linux/amd64 ...
```

### 2. Bootstrap Script Safeguards (Already Implemented)

The `bootstrap-base-images.sh` includes:

```bash
# Always pull with explicit platform
${RUNTIME} pull --platform linux/amd64 "${source_image}"

# Verify pushed image architecture
pushed_arch=$(docker manifest inspect "${private_tag}" | grep -o '"architecture"...')
if [[ "${pushed_arch}" != "amd64" ]]; then
  log_error "WARNING: Pushed image architecture is '${pushed_arch}', expected 'amd64'"
fi
```

### 3. CI/CD Pipeline Check (Recommended)

Add a pre-deployment check to verify base image architecture:

```bash
# Add to buildspec pre_build phase
echo "Verifying base image architectures..."
for repo in alpine node nginx; do
  ARCH=$(aws ecr describe-images \
    --repository-name aura-base-images/$repo \
    --query 'imageDetails[0].imageScanStatus' \
    --output text 2>/dev/null || echo "not-found")
  echo "$repo: $ARCH"
done
```

---

## Related Documentation

- [Bootstrap Base Images Script](../../deploy/scripts/bootstrap-base-images.sh)
- [Application Buildspec](../../deploy/buildspecs/buildspec-application.yml)
- [ECR Base Images CloudFormation](../../deploy/cloudformation/ecr-base-images.yaml)
- [CLAUDE.md - Docker Builds Section](../../CLAUDE.md#docker-builds-important---architecture)

---

## Appendix: Architecture Reference

| Environment | Architecture | Platform Flag |
|-------------|--------------|---------------|
| CodeBuild | x86_64 | `linux/amd64` |
| EKS Nodes | x86_64 | `linux/amd64` |
| Apple Silicon Mac | ARM64 | `linux/arm64` |
| AWS Graviton | ARM64 | `linux/arm64` |

**Project Aura Standard:** All container images MUST be built for `linux/amd64` to ensure compatibility with CodeBuild and EKS.
