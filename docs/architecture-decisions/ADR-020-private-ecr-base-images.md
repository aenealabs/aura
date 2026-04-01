# ADR-020: Private ECR Base Images for Controlled Container Supply Chain

**Status:** Deployed
**Date:** 2025-12-04
**Decision Makers:** Project Aura Team

## Context

Project Aura builds container images for deployment to EKS. These images require base images (e.g., Alpine Linux) sourced from external registries. During CI/CD execution, the Application layer encountered Docker Hub rate limiting (HTTP 429), blocking container builds.

**Problem Statement:**
- Docker Hub imposes rate limits (100 pulls/6 hours for anonymous, 200 for authenticated)
- CI/CD builds fail unpredictably when limits are exceeded
- External registry dependencies create supply chain risks
- CMMC Level 3 requires controlled supply chain for software components

**Options Evaluated:**
1. Docker Hub (public) - Current approach, rate limited
2. Docker Hub (authenticated) - Higher limits, still external dependency
3. ECR Public Gallery - AWS-hosted, no rate limits, but still external
4. Private ECR - Full control, scanning, compliance-ready

## Decision

We chose **Private ECR Base Images** with a bootstrap pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Container Supply Chain                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     Bootstrap      ┌──────────────────────┐  │
│  │ ECR Public   │ ─────────────────> │ Private ECR          │  │
│  │ Gallery      │   (one-time)       │ aura-base-images/    │  │
│  │ alpine:3.19  │                    │ alpine:3.19          │  │
│  └──────────────┘                    └──────────┬───────────┘  │
│                                                  │              │
│                                      CI/CD Build │              │
│                                                  ▼              │
│                                      ┌──────────────────────┐  │
│                                      │ Application Images   │  │
│                                      │ aura-dnsmasq:v1.0.x  │  │
│                                      │ aura-api:v1.0.x      │  │
│                                      └──────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation Components:**

| Component | Purpose |
|-----------|---------|
| `ecr-base-images.yaml` | CloudFormation stack for base image repository |
| `bootstrap-base-images.sh` | One-time script to populate from ECR Public Gallery |
| `Dockerfile.alpine` | ARG-based base image with fallback pattern |
| `buildspec-application.yml` | Retrieves base image URI from stack outputs |

**Base Image Strategy:**
- Source from ECR Public Gallery (AWS-hosted, no rate limits)
- Push to private ECR with immutable tags
- Enable vulnerability scanning on push
- Version pin (e.g., `alpine:3.19`) for reproducibility

## Alternatives Considered

### Alternative 1: Docker Hub with Authentication

Configure Docker Hub credentials in CodeBuild for higher rate limits.

**Pros:**
- Higher limits (200 pulls/6 hours)
- No infrastructure changes needed
- Familiar workflow

**Cons:**
- Still subject to rate limits during high activity
- External dependency on Docker Inc.
- Credentials management complexity
- No vulnerability scanning integration
- **Not compliant with CMMC controlled supply chain requirements**

### Alternative 2: ECR Public Gallery (Direct Use)

Pull directly from `public.ecr.aws` in Dockerfiles.

**Pros:**
- No rate limits (AWS-hosted)
- No infrastructure needed
- Always latest images available

**Cons:**
- Still external dependency (no control over image contents)
- No vulnerability scanning before use
- Cannot enforce immutable tags
- Supply chain not "controlled" for compliance purposes
- Potential for upstream image changes breaking builds

### Alternative 3: Mirror All Images to Private ECR

Automatically sync all base images from multiple registries.

**Pros:**
- Comprehensive coverage
- Automated updates

**Cons:**
- Complex automation required
- Storage costs for unused images
- Over-engineered for current needs (only Alpine required)
- Harder to audit which images are approved

### Alternative 4: Vendor-Managed Container Registry

Use a third-party registry service (e.g., JFrog Artifactory, Harbor).

**Pros:**
- Rich features (proxying, caching, scanning)
- Multi-registry aggregation

**Cons:**
- Additional vendor dependency
- Cost ($100-500/month)
- Not AWS-native (GovCloud integration concerns)
- Overkill for current scale

## Consequences

### Positive

1. **Reliability**
   - No external rate limits during CI/CD
   - Builds succeed consistently regardless of Docker Hub status
   - Reduced dependency on external infrastructure

2. **Security & Compliance**
   - Vulnerability scanning on push (ECR native)
   - Immutable tags prevent tampering
   - Controlled supply chain for CMMC Level 3
   - Audit trail of image provenance

3. **Cost Efficiency**
   - ECR storage: ~$0.10/GB/month (Alpine ~7MB = negligible)
   - No Docker Hub subscription needed
   - Reduced build failures = less CI/CD re-runs

4. **Operational Control**
   - Explicit version pinning
   - Controlled update cadence for base images
   - Can test new base image versions before adoption

5. **GovCloud Ready**
   - Same pattern works in Commercial and GovCloud
   - No external registry access required from GovCloud
   - Meets FedRAMP supply chain requirements

### Negative

1. **Bootstrap Requirement**
   - One-time script must run after Foundation layer deployment
   - New base image versions require manual bootstrap
   - Additional operational step in environment setup

2. **Version Management**
   - Must manually update when new Alpine versions needed
   - Security patches in base image require re-bootstrap
   - Could lag behind upstream if not monitored

3. **Storage Costs**
   - Minimal but non-zero (~$0.01/month for Alpine)
   - Grows with additional base images

### Mitigation

- **Automated CVE Monitoring:** ECR scanning alerts on vulnerabilities
- **Runbook Documentation:** Bootstrap steps in `DEPLOYMENT_GUIDE.md`
- **Fallback Pattern:** Dockerfiles include public ECR fallback for local development
- **Version Tracking:** Base image versions documented in `CHANGELOG.md`

## Implementation Details

### Bootstrap Process

```bash
# One-time setup after Foundation layer deployment
./deploy/scripts/bootstrap-base-images.sh dev

# Force update (overwrites existing - use for security patches)
./deploy/scripts/bootstrap-base-images.sh dev --force
```

### Dockerfile Pattern

```dockerfile
# Fallback to public ECR for local dev without bootstrap
ARG BASE_IMAGE_URI=public.ecr.aws/docker/library/alpine:3.19
FROM ${BASE_IMAGE_URI}

# ... rest of Dockerfile
```

### CI/CD Integration

```yaml
# In buildspec-application.yml
build:
  commands:
    - BASE_IMAGES_STACK="${PROJECT_NAME}-ecr-base-images-${ENVIRONMENT}"
    - BASE_IMAGE_URI=$(aws cloudformation describe-stacks \
        --stack-name $BASE_IMAGES_STACK \
        --query 'Stacks[0].Outputs[?OutputKey==`AlpineRepositoryUri`].OutputValue' \
        --output text):3.19
    - docker build --build-arg BASE_IMAGE_URI=${BASE_IMAGE_URI} ...
```

## Security Considerations

1. **Image Provenance**
   - Source only from ECR Public Gallery (AWS-vetted)
   - Document image digests in bootstrap logs
   - Immutable tags prevent post-push modification

2. **Vulnerability Scanning**
   - ECR scans on push (enabled in CloudFormation)
   - Critical/High findings should block production deployment
   - Scan results visible in AWS Console and CLI

3. **Access Control**
   - Only Foundation CodeBuild role can push to base-images repo
   - Application layer has read-only access
   - IAM policies scoped to specific repositories

## Cost Analysis

| Component | Monthly Cost |
|-----------|--------------|
| ECR Storage (Alpine 7MB) | $0.01 |
| ECR Data Transfer (within region) | $0.00 |
| Vulnerability Scanning | Free (basic) |
| **TOTAL** | **~$0.01/month** |

## References

- `deploy/cloudformation/ecr-base-images.yaml` - ECR repository stack
- `deploy/scripts/bootstrap-base-images.sh` - Bootstrap script
- `deploy/docker/dnsmasq/Dockerfile.alpine` - Example Dockerfile with ARG pattern
- `deploy/buildspecs/buildspec-application.yml` - CI/CD integration
- `DEPLOYMENT_GUIDE.md` - Bootstrap documentation
- [AWS ECR Pricing](https://aws.amazon.com/ecr/pricing/)
- [CMMC Level 3 - Supply Chain Risk Management](https://dodcio.defense.gov/CMMC/)
