# ADR-035: Dedicated Docker-Podman Build CodeBuild Project

**Status:** Deployed
**Date:** 2025-12-14
**Decision Makers:** Project Aura Team
**Relates To:** ADR-007 (Modular CI/CD with Layer-Based Deployment)

## Context

Project Aura uses CodeBuild for CI/CD with layer-based buildspecs (ADR-007). The Application layer buildspec (`buildspec-application.yml`) handles Docker/Podman image builds alongside many other tasks:

- ECR repository creation
- Container (Docker/Podman) build and push
- Bedrock infrastructure deployment
- Cognito user pool deployment
- Bedrock Guardrails deployment
- IRSA configuration
- Kubernetes manifest deployment
- OpenSearch verification

**Problem:** When developers only need to rebuild and push a container image (Docker/Podman), they must run the entire 599-line Application layer buildspec, which:

1. Takes 15-30 minutes even when only the Docker image changed
2. Deploys/updates infrastructure that hasn't changed
3. Cannot be used for rapid iteration on container changes
4. Forces unnecessary CloudFormation API calls

**Real-World Impact:** A developer with limited upload bandwidth (4 Mbps) faces a 4+ hour local container push for an 8GB image. Using CodeBuild solves this, but running the full Application buildspec adds unnecessary overhead.

**Note on Podman:** While CodeBuild uses Docker CLI, the buildspec and patterns are compatible with Podman for local development. Podman provides a daemonless, rootless container engine that is command-compatible with Docker.

## Decision

Create a **dedicated lightweight CodeBuild project** specifically for container (Docker/Podman) image builds:

- **Project Name:** `aura-docker-build-{environment}`
- **Buildspec:** `deploy/buildspecs/buildspec-docker-build.yml` (~130 lines)
- **CloudFormation:** `deploy/cloudformation/codebuild-docker.yaml`
- **Purpose:** Build and push container images only, no infrastructure deployment

**Key Features:**

1. **Multi-target support** via environment variable:
   - `api`, `frontend`, `dnsmasq`, `orchestrator`, `agent`, `sandbox`, `memory-service`

2. **Flexible tagging:**
   - Custom `IMAGE_TAG` parameter
   - Automatic commit SHA tagging
   - Build number tagging

3. **Fast execution:** 3-8 minutes vs 15-30 minutes

**Usage Pattern:**

```bash
# Build specific image with custom tag
aws codebuild start-build \
  --project-name aura-docker-build-dev \
  --environment-variables-override \
    name=BUILD_TARGET,value=frontend \
    name=IMAGE_TAG,value=v2.0.0
```

## Alternatives Considered

### Alternative 1: Continue Using Application Layer Buildspec

Use existing `buildspec-application.yml` for all Docker builds.

**Pros:**
- No new infrastructure to maintain
- Single source of truth for application deployment
- Already tested and working

**Cons:**
- 15-30 minute builds for simple image updates
- Unnecessary infrastructure churn
- Poor developer experience for rapid iteration
- Wasteful CloudFormation API usage

### Alternative 2: Local Docker/Podman Builds Only

Developers build and push images from local machines using Docker or Podman.

**Pros:**
- No CI/CD dependency
- Immediate feedback
- Full control over build process
- Podman offers rootless, daemonless operation

**Cons:**
- Upload bandwidth bottleneck (4 Mbps = 4+ hours for 8GB image)
- Inconsistent build environments
- No audit trail
- Architecture mismatch risk (ARM vs x86_64)

### Alternative 3: GitHub Actions for Container Builds

Use GitHub Actions instead of CodeBuild for container-specific builds.

**Pros:**
- Rich Docker ecosystem (docker/build-push-action)
- Familiar workflow syntax
- Caching with GitHub Actions Cache

**Cons:**
- IAM credential management for ECR access
- Less integrated with AWS services
- Network connectivity concerns for GovCloud
- Separate CI/CD system to maintain

### Alternative 4: ECR Build-on-Push

Use ECR image building capability.

**Pros:**
- Native AWS integration
- No separate build infrastructure

**Cons:**
- Limited customization options
- Less control over build process
- Not available in all regions/GovCloud

## Consequences

### Positive

1. **Fast Iteration**
   - Container-only builds complete in 3-8 minutes
   - Enables rapid container development cycles
   - Immediate feedback on image changes

2. **Resource Efficiency**
   - No unnecessary CloudFormation deployments
   - Reduced CodeBuild minutes for simple changes
   - Lower API call costs

3. **Developer Experience**
   - Simple one-liner to build any image
   - No need to understand full application deployment
   - Solves bandwidth bottleneck for remote developers

4. **Separation of Concerns**
   - Infrastructure deployment separate from image builds
   - Clearer purpose per CodeBuild project
   - Aligns with ADR-007 modular philosophy

5. **Flexibility**
   - Build any target image on demand
   - Custom tagging for releases
   - Works with existing ECR repositories

### Negative

1. **Additional Infrastructure**
   - One more CodeBuild project to maintain
   - Additional CloudFormation template
   - Slightly higher baseline cost

2. **Potential Drift**
   - Container build could use different settings than application layer
   - Must keep buildspecs aligned for consistency

3. **Coordination Overhead**
   - Developers must know when to use which project
   - May need to run both for full deployment

### Mitigation

1. **Documentation**
   - Clear usage examples in buildspec comments
   - Decision tree: when to use docker-build vs application layer

2. **Consistency**
   - Both buildspecs use same container build flags (`--platform linux/amd64`)
   - Shared ECR repository references
   - Docker CLI commands work identically with Podman via `alias docker=podman`
   - ECR credential helper used across all Docker buildspecs (eliminates password storage warnings)

3. **Cost Control**
   - Use BUILD_GENERAL1_MEDIUM (not LARGE)
   - 30-minute timeout limit
   - 30-day log retention

## Implementation

### Files Created

| File | Purpose |
|------|---------|
| `deploy/buildspecs/buildspec-docker-build.yml` | Lightweight Docker-Podman build spec |
| `deploy/cloudformation/codebuild-docker.yaml` | CodeBuild project definition |
| `deploy/scripts/configure-ecr-credential-helper.sh` | ECR credential helper configuration (shared across buildspecs) |

### Deployment

```bash
# Deploy the CodeBuild project (via Foundation layer buildspec)
# Note: codebuild-docker.yaml is now deployed as Layer 1.9 in Foundation
aws cloudformation deploy \
  --stack-name aura-codebuild-docker-dev \
  --template-file deploy/cloudformation/codebuild-docker.yaml \
  --parameter-overrides ProjectName=aura Environment=dev \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Project=aura Environment=dev Layer=1.9 \
  --region us-east-1
```

### Usage Examples

```bash
# Build API image (default)
aws codebuild start-build --project-name aura-docker-build-dev

# Build frontend with specific tag
aws codebuild start-build \
  --project-name aura-docker-build-dev \
  --environment-variables-override \
    name=BUILD_TARGET,value=frontend \
    name=IMAGE_TAG,value=v2.0.0

# Build memory service for GPU
aws codebuild start-build \
  --project-name aura-docker-build-dev \
  --environment-variables-override \
    name=BUILD_TARGET,value=memory-service \
    name=IMAGE_TAG,value=gpu-latest
```

### Implementation Notes

**IAM Eventual Consistency Issue:**

During implementation, we discovered that creating a new IAM role (DockerBuildRole) in the same CloudFormation stack as the CodeBuild project caused `OAuthProviderException` errors. The newly created role's permissions don't propagate fast enough for CodeBuild to validate the CodeConnections access during stack creation.

**Solution:** The CodeBuild project uses the existing Foundation role (`aura-foundation-codebuild-role-{environment}`) as its ServiceRole instead of the DockerBuildRole created in the same stack. The DockerBuildRole is retained in the template for reference but is not actively used. The Foundation role was updated with ECR push/pull permissions and CloudWatch Logs permissions for the docker-build log group.

**ECR Credential Helper:**

We implemented the ECR credential helper to eliminate the "WARNING! Your password will be stored unencrypted" message that appears when using explicit `docker login` commands:

- Uses `docker-credential-ecr-login` (pre-installed on CodeBuild images) instead of explicit `docker login`
- Shared script created: `deploy/scripts/configure-ecr-credential-helper.sh`
- All buildspecs updated to use the credential helper in the install phase

## Decision Criteria Met

This ADR is appropriate because:

- [x] Affects CI/CD architecture (extends ADR-007)
- [x] Has significant operational impact (4+ hours → 3-8 minutes)
- [x] Introduces new infrastructure pattern
- [x] Involves cost/time tradeoffs
- [x] Will be referenced for future similar decisions

## References

- ADR-007: Modular CI/CD with Layer-Based Deployment
- `deploy/buildspecs/buildspec-application.yml` - Full application layer buildspec
- `deploy/buildspecs/buildspec-docker-build.yml` - New lightweight buildspec
- `deploy/cloudformation/codebuild-docker.yaml` - New CodeBuild project template
- `deploy/scripts/configure-ecr-credential-helper.sh` - ECR credential helper script
- `deploy/cloudformation/codebuild-foundation.yaml` - Foundation role (used as ServiceRole)
- `docs/security/SECURITY_FIXES_QUICK_REFERENCE.md` - ECR GetAuthorizationToken security analysis
