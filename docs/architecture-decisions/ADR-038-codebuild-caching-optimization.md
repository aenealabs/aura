# ADR-038: CodeBuild Caching Optimization Strategy

**Status:** Deployed
**Date:** 2025-12-14
**Decision Makers:** Project Aura Team
**Relates To:** ADR-007 (Modular CI/CD Strategy), ADR-020 (Private ECR Base Images), ADR-035 (Dedicated Docker Build Project)

## Context

Project Aura's CI/CD pipeline consists of 14 CodeBuild projects managing 58 CloudFormation templates across 8 deployment layers. Build times have become a bottleneck for developer productivity:

**Current Build Performance Issues:**

| Build Type | Current Duration | Primary Bottleneck |
|------------|------------------|-------------------|
| Python dependency installation | 3-5 minutes | pip download from PyPI |
| Docker image builds | 8-15 minutes | Layer rebuilds, base image pulls |
| Full layer deployment | 15-25 minutes | Sequential dependency resolution |

**Key Constraints:**

1. **CMMC Level 3 Compliance:** All cached artifacts must be secured with encryption and access controls
2. **Supply Chain Security:** Cached dependencies must not persist indefinitely to ensure security updates are applied
3. **GovCloud Compatibility:** Caching infrastructure must work identically in AWS Commercial and GovCloud
4. **Cost Efficiency:** Caching infrastructure should minimize ongoing storage costs

**Problem Statement:**

Without build caching, every CodeBuild execution:
- Re-downloads all Python packages from PyPI (network I/O bottleneck)
- Rebuilds Docker layers even when source files haven't changed
- Pulls base images from registries on every build
- Results in inconsistent build times due to network variability

## Decision

Implement a **multi-tier caching strategy** for CodeBuild using:

1. **S3-based pip package caching** for Python dependencies
2. **ECR-based Docker layer caching** using BuildKit inline cache
3. **ECR image scanning** to block critical vulnerabilities
4. **7-day TTL lifecycle policy** for supply chain security

### Architecture

```
                    CodeBuild Caching Architecture
+--------------------------------------------------------------------------+
|                                                                          |
|  +-----------------------+         +---------------------------------+   |
|  |    CodeBuild Job      |         |      S3 Build Cache Bucket      |   |
|  +-----------------------+         +---------------------------------+   |
|  |                       |         |  - KMS-CMK encrypted            |   |
|  |  pip install phase:   |-------->|  - Versioning enabled           |   |
|  |  - Check S3 cache     |<--------|  - 7-day TTL lifecycle          |   |
|  |  - Restore if hit     |         |  - Public access blocked        |   |
|  |  - Save after install |         |  - VPC endpoint access only     |   |
|  |                       |         +---------------------------------+   |
|  +-----------------------+                                               |
|           |                                                              |
|           v                                                              |
|  +-----------------------+         +---------------------------------+   |
|  |   Docker Build Phase  |         |       ECR Repository            |   |
|  +-----------------------+         +---------------------------------+   |
|  |                       |         |  - BuildKit cache metadata      |   |
|  |  docker buildx:       |-------->|  - Inline cache export          |   |
|  |  - Pull cache from ECR|<--------|  - Image scanning enabled       |   |
|  |  - Build with cache   |         |  - Critical vuln blocking       |   |
|  |  - Push cache to ECR  |         |  - Lifecycle policies           |   |
|  |                       |         +---------------------------------+   |
|  +-----------------------+                                               |
|                                                                          |
+--------------------------------------------------------------------------+
```

### S3 Build Cache Configuration

**CloudFormation Template:** `deploy/cloudformation/build-cache.yaml`

```yaml
Resources:
  BuildCacheBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub '${ProjectName}-build-cache-${Environment}'
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: aws:kms
              KMSMasterKeyID: !Ref BuildCacheKMSKey
      VersioningConfiguration:
        Status: Enabled
      LifecycleConfiguration:
        Rules:
          - Id: ExpireCacheAfter7Days
            Status: Enabled
            ExpirationInDays: 7
            NoncurrentVersionExpiration:
              NoncurrentDays: 1
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
```

**Security Controls:**

| Control | Implementation | CMMC Mapping |
|---------|----------------|--------------|
| Encryption at rest | KMS-CMK with automatic rotation | SC.L2-3.13.11 |
| Encryption in transit | S3 TLS endpoints only | SC.L2-3.13.8 |
| Access logging | S3 access logs to security bucket | AU.L2-3.3.1 |
| Versioning | Enabled for audit trail | AU.L2-3.3.2 |
| Public access | Blocked at bucket level | AC.L2-3.1.22 |
| TTL expiration | 7-day lifecycle policy | SI.L2-3.14.3 |

### Buildspec Cache Configuration

**pip Cache Integration:**

```yaml
# In buildspec-*.yml files
cache:
  paths:
    - '/root/.cache/pip/**/*'

phases:
  install:
    commands:
      # Restore pip cache from S3 if exists
      - aws s3 sync s3://${CACHE_BUCKET}/pip-cache /root/.cache/pip --quiet || true

  post_build:
    commands:
      # Save pip cache to S3 for next build
      - aws s3 sync /root/.cache/pip s3://${CACHE_BUCKET}/pip-cache --quiet || true
```

### Docker BuildKit Cache Integration

**buildspec-docker-build.yml Enhancement:**

```yaml
phases:
  build:
    commands:
      # Enable BuildKit
      - export DOCKER_BUILDKIT=1

      # Build with cache-from and cache-to
      - |
        docker buildx build \
          --platform linux/amd64 \
          --cache-from type=registry,ref=${ECR_REGISTRY}/${IMAGE_NAME}:cache \
          --cache-to type=inline \
          --tag ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} \
          --push \
          -f ${DOCKERFILE_PATH} .
```

### ECR Image Scanning Configuration

**Enhanced ECR Repository Settings:**

```yaml
ECRRepository:
  Type: AWS::ECR::Repository
  Properties:
    RepositoryName: !Sub '${ProjectName}-${ServiceName}-${Environment}'
    ImageScanningConfiguration:
      ScanOnPush: true
    ImageTagMutability: IMMUTABLE
    LifecyclePolicy:
      LifecyclePolicyText: |
        {
          "rules": [
            {
              "rulePriority": 1,
              "description": "Keep last 10 cache images",
              "selection": {
                "tagStatus": "tagged",
                "tagPrefixList": ["cache"],
                "countType": "imageCountMoreThan",
                "countNumber": 10
              },
              "action": { "type": "expire" }
            }
          ]
        }
```

**Vulnerability Blocking in Buildspec:**

```yaml
phases:
  post_build:
    commands:
      # Wait for ECR scan to complete
      - |
        SCAN_STATUS="IN_PROGRESS"
        while [ "$SCAN_STATUS" = "IN_PROGRESS" ]; do
          sleep 5
          SCAN_STATUS=$(aws ecr describe-image-scan-findings \
            --repository-name ${IMAGE_NAME} \
            --image-id imageTag=${IMAGE_TAG} \
            --query 'imageScanStatus.status' --output text 2>/dev/null || echo "IN_PROGRESS")
        done

      # Check for CRITICAL vulnerabilities
      - |
        CRITICAL_COUNT=$(aws ecr describe-image-scan-findings \
          --repository-name ${IMAGE_NAME} \
          --image-id imageTag=${IMAGE_TAG} \
          --query 'imageScanFindings.findingSeverityCounts.CRITICAL' --output text 2>/dev/null || echo "0")

        if [ "$CRITICAL_COUNT" != "None" ] && [ "$CRITICAL_COUNT" -gt 0 ]; then
          echo "ERROR: Image contains $CRITICAL_COUNT CRITICAL vulnerabilities"
          exit 1
        fi
```

## Alternatives Considered

### Alternative 1: CodeBuild Local Caching Only

Use CodeBuild's built-in local caching without S3.

**Pros:**
- Simplest implementation
- No additional infrastructure
- Automatic cache management

**Cons:**
- Cache not shared across build instances
- Cache lost when build instance is replaced
- Limited to 50GB per build project
- No cache sharing between layers

**Decision:** Rejected - Cache isolation defeats purpose for multi-project CI/CD.

### Alternative 2: EFS-Based Shared Cache

Mount EFS volume for shared pip cache across builds.

**Pros:**
- Real-time cache sharing
- No S3 sync overhead
- Unlimited storage

**Cons:**
- **$0.30/GB/month** vs S3 **$0.023/GB/month** (13x more expensive)
- Requires VPC configuration for all builds
- EFS throughput can bottleneck parallel builds
- Not available in all GovCloud regions

**Decision:** Rejected - Cost prohibitive and GovCloud availability concerns.

### Alternative 3: External Cache Service (e.g., Artifactory)

Use JFrog Artifactory or Nexus as pip/Docker cache.

**Pros:**
- Enterprise-grade caching
- Advanced cache policies
- Vulnerability scanning built-in

**Cons:**
- Additional vendor dependency
- **$500+/month** licensing cost
- Requires self-hosting or SaaS integration
- Complicates GovCloud deployment

**Decision:** Rejected - Unnecessary vendor dependency and cost.

### Alternative 4: Longer TTL for Cache Artifacts

Use 30-day or 90-day TTL instead of 7 days.

**Pros:**
- Fewer cache misses
- Lower S3 PUT costs

**Cons:**
- **Security risk:** Stale dependencies may contain known vulnerabilities
- Delayed propagation of security patches
- CMMC SI.L2-3.14.3 requires timely patching

**Decision:** Rejected - 7-day TTL balances cache efficiency with security hygiene.

## Consequences

### Positive

1. **Build Time Reduction**
   - pip cache hits: **60-80% faster** dependency installation
   - Docker layer cache hits: **40-60% faster** image builds
   - Estimated total build time reduction: **30-50%**

2. **Cost Efficiency**
   - S3 storage: ~$0.023/GB/month (minimal with 7-day TTL)
   - Reduced CodeBuild minutes: ~$50-100/month savings
   - Net cost savings: ~$40-90/month

3. **Developer Productivity**
   - Faster feedback loops on PRs
   - Reduced waiting time for deployments
   - More consistent build times (less network variability)

4. **Supply Chain Security**
   - 7-day TTL ensures regular dependency refresh
   - ECR scanning blocks critical vulnerabilities
   - KMS encryption protects cached artifacts
   - Audit trail via versioning and access logs

5. **GovCloud Compatibility**
   - S3 with KMS: Available in all GovCloud regions
   - ECR with scanning: Available in GovCloud
   - BuildKit caching: Standard Docker feature
   - No external service dependencies

### Negative

1. **Cache Invalidation Complexity**
   - Developers must understand cache behavior
   - Stale cache can cause build issues
   - Manual cache clearing may be needed occasionally

2. **Infrastructure Overhead**
   - Additional CloudFormation template to manage
   - KMS key management
   - S3 bucket lifecycle monitoring

3. **Cold Start Penalty**
   - First build after cache expiry takes full time
   - Monday morning builds may be slower (weekend expiry)

### Mitigation

1. **Cache Invalidation**
   - Document cache behavior in `DEPLOYMENT_GUIDE.md`
   - Provide manual cache clear script: `scripts/clear-build-cache.sh`
   - Add cache status to build output logs

2. **Cold Start Handling**
   - Schedule weekly cache warming builds via EventBridge
   - Monitor cache hit rates in CloudWatch dashboard
   - Alert on sustained cache miss rates >50%

## Security Considerations

### CMMC Level 3 Mapping

| CMMC Practice | Control | Implementation |
|--------------|---------|----------------|
| AC.L2-3.1.1 | Limit system access | IAM policies restrict cache bucket access to CodeBuild roles |
| AC.L2-3.1.22 | Control public access | S3 public access block enabled |
| AU.L2-3.3.1 | Create audit records | S3 access logging to security bucket |
| AU.L2-3.3.2 | Audit record content | Versioning captures all cache mutations |
| SC.L2-3.13.8 | Cryptographic protection in transit | S3 TLS-only bucket policy |
| SC.L2-3.13.11 | Cryptographic protection at rest | KMS-CMK encryption |
| SI.L2-3.14.3 | Security patching | 7-day TTL ensures dependency refresh |

### IAM Policy (Least Privilege)

```yaml
BuildCachePolicy:
  Type: AWS::IAM::ManagedPolicy
  Properties:
    PolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Sid: AllowCacheBucketAccess
          Effect: Allow
          Action:
            - s3:GetObject
            - s3:PutObject
            - s3:ListBucket
          Resource:
            - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-build-cache-${Environment}'
            - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-build-cache-${Environment}/*'
        - Sid: AllowKMSDecrypt
          Effect: Allow
          Action:
            - kms:Decrypt
            - kms:GenerateDataKey
          Resource:
            - !GetAtt BuildCacheKMSKey.Arn
          Condition:
            StringEquals:
              kms:ViaService: !Sub 's3.${AWS::Region}.amazonaws.com'
```

## GovCloud Compatibility

| Component | Commercial AWS | GovCloud (US) | Notes |
|-----------|----------------|---------------|-------|
| S3 Bucket | Available | Available | Identical API |
| KMS-CMK | Available | Available | FIPS 140-2 Level 2 in GovCloud |
| S3 Lifecycle | Available | Available | Identical configuration |
| ECR Scanning | Available | Available | Basic scanning, no Inspector integration |
| BuildKit | Available | Available | Standard Docker feature |
| CodeBuild S3 Cache | Available | Available | Native integration |

**GovCloud-Specific Considerations:**

1. Use `${AWS::Partition}` for all ARNs (resolves to `aws-us-gov` in GovCloud)
2. ECR scanning in GovCloud uses basic scanning (no Inspector Advanced Scanning)
3. FIPS 140-2 mode automatically enabled in GovCloud KMS

## Implementation Plan

### Deployment Strategy: Foundation Sub-Layer (Layer 1.8)

The build-cache infrastructure is deployed as a **Foundation sub-layer** rather than being included in the main Foundation buildspec. This approach:

- Keeps the main `buildspec-foundation.yml` under the 600-line limit
- Allows independent deployment of cache infrastructure
- Maintains logical grouping with CI/CD infrastructure (Foundation manages all CodeBuild projects)

**Deployment Files:**

| File | Purpose |
|------|---------|
| `deploy/cloudformation/build-cache.yaml` | S3 bucket + KMS key (Layer 1.8) |
| `deploy/buildspecs/buildspec-foundation-cache.yml` | Sub-layer deployment buildspec |
| `deploy/cloudformation/codebuild-docker.yaml` | CodeBuild project with S3 cache configured |

**Deployment Order:**

1. Deploy `build-cache.yaml` via `buildspec-foundation-cache.yml` (creates S3 bucket + KMS key)
2. Deploy/update `codebuild-docker.yaml` via `buildspec-foundation.yml` (references the cache bucket)
3. Run docker builds via `buildspec-docker-build.yml` (uses the cache)

### Phase 1: S3 Cache Infrastructure

1. Deploy `build-cache.yaml` via Foundation sub-layer buildspec
2. IAM roles already have cache bucket permissions (added to `codebuild-foundation.yaml`)
3. KMS key policy grants access to all CodeBuild roles

### Phase 2: pip Cache Integration

1. All 15 buildspecs updated with `cache.paths: ['/root/.cache/pip/**/*']`
2. CodeBuild projects need `Cache.Type: S3` configured
3. Cache hit/miss logged in build output

### Phase 3: Docker BuildKit Cache

1. `DOCKER_BUILDKIT=1` enabled in `buildspec-docker-build.yml`
2. `--cache-from` and `--cache-to type=inline` configured
3. `:cache` tag pushed to ECR for layer reuse

### Phase 4: Vulnerability Scanning

1. ECR scan-on-push already enabled in all ECR templates
2. `buildspec-docker-build.yml` blocks on CRITICAL vulnerabilities
3. HIGH vulnerabilities logged as warnings

### Phase 5: Monitoring

1. Create CloudWatch dashboard for cache metrics
2. Set up alarms for cache miss rates
3. Document cache behavior for developers

## Cost Estimate

| Resource | Monthly Cost | Notes |
|----------|-------------|-------|
| S3 Storage | ~$0.50 | ~20GB cache with 7-day TTL |
| S3 Requests | ~$0.10 | PUT/GET for cache operations |
| KMS | $1.00 | 1 CMK + API calls |
| ECR Storage | ~$1.00 | Cache images (minimal additional) |
| **Total** | **~$2.60/month** | |
| **Savings** | **~$50-100/month** | Reduced CodeBuild minutes |
| **Net Savings** | **~$47-97/month** | |

## References

### Internal

- ADR-007: Modular CI/CD with Layer-Based Deployment
- ADR-020: Private ECR Base Images for Controlled Supply Chain
- ADR-035: Dedicated Docker-Podman Build CodeBuild Project
- `deploy/cloudformation/build-cache.yaml` - S3 bucket + KMS key (Layer 1.8)
- `deploy/buildspecs/buildspec-foundation-cache.yml` - Sub-layer deployment buildspec
- `deploy/buildspecs/buildspec-docker-build.yml` - Docker build with caching
- `deploy/cloudformation/codebuild-docker.yaml` - CodeBuild project with S3 cache
- `docs/deployment/CICD_SETUP_GUIDE.md`

### External

- [AWS CodeBuild Caching](https://docs.aws.amazon.com/codebuild/latest/userguide/build-caching.html)
- [Docker BuildKit Cache](https://docs.docker.com/build/cache/)
- [ECR Image Scanning](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-scanning.html)
- [CMMC Level 2 Practices](https://dodcio.defense.gov/CMMC/)
