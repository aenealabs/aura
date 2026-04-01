# Archived Scripts

**Archived:** 2025-12-14
**Reason:** Obsolete after modular CI/CD implementation

---

## Scripts in This Archive

| Script | Original Date | Reason for Archival |
|--------|---------------|---------------------|
| `deploy-cicd-pipeline.sh` | Nov 24, 2025 | References old monolithic `aura-infra-deploy-dev` CodeBuild project |
| `deploy-data-codebuild.sh` | Nov 24, 2025 | Outdated duplicate; newer version in `deploy/scripts/` (Dec 5) |
| `deploy-foundation-codebuild.sh` | Nov 24, 2025 | Outdated duplicate; newer version in `deploy/scripts/` (Dec 5) |
| `deploy-phase2-infrastructure.sh` | Nov 24, 2025 | References old monolithic CodeBuild architecture |
| `trigger-data-build.sh` | Nov 24, 2025 | References old monolithic CodeBuild architecture |
| `trigger-foundation-build.sh` | Nov 24, 2025 | References old monolithic CodeBuild architecture |
| `setup_repo.sh` | Nov 11, 2025 | One-time initial repo setup; no longer needed |

---

## Current CI/CD Architecture

The project now uses **modular layer-specific CodeBuild projects** instead of the old monolithic approach:

- `aura-foundation-deploy-dev` - Foundation Layer (VPC, IAM, WAF)
- `aura-data-deploy-dev` - Data Layer (Neptune, OpenSearch, DynamoDB)
- `aura-compute-deploy-dev` - Compute Layer (EKS, Node Groups)
- `aura-application-deploy-dev` - Application Layer (API, Bedrock)
- `aura-observability-deploy-dev` - Observability Layer (CloudWatch, Secrets)
- `aura-serverless-deploy-dev` - Serverless Layer (Lambda, Step Functions)
- `aura-sandbox-deploy-dev` - Sandbox Layer (HITL Workflow)
- `aura-security-deploy-dev` - Security Layer (GuardDuty, Config)

## Current Deployment Scripts

Active deployment scripts are located in `deploy/scripts/`:

```bash
# Deploy a specific layer's CodeBuild project
./deploy/scripts/deploy-foundation-codebuild.sh dev
./deploy/scripts/deploy-data-codebuild.sh dev

# Trigger a layer deployment
aws codebuild start-build --project-name aura-data-deploy-dev
```

See `docs/CICD_SETUP_GUIDE.md` for complete documentation.
