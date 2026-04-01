# Project Aura Customer Installer

Production-ready installation scripts for deploying Project Aura in customer AWS environments.

## Quick Start

### Online Installation

```bash
curl -fsSL https://get.aenealabs.com | bash
```

### Local Installation

```bash
# Run the configuration wizard
./config-wizard.sh

# Install with generated config
./aura-install.sh --config aura-config.yaml
```

### Air-Gapped Installation

```bash
./aura-install.sh --offline --bundle /path/to/aura-bundle.tar.gz
```

## Installation Scripts

| Script | Purpose |
|--------|---------|
| `aura-install.sh` | Main installer with pre-flight checks and deployment orchestration |
| `aura-uninstall.sh` | Clean removal of all Aura resources |
| `config-wizard.sh` | Interactive configuration helper |

## Verification Suite

Located in `verify/`:

| Script | Purpose |
|--------|---------|
| `verify-deployment.sh` | Comprehensive verification of all deployed services |
| `smoke-tests.sh` | Quick smoke tests for basic functionality |
| `health-checks.sh` | Service health endpoint checks |
| `connectivity-tests.sh` | Network connectivity between services |

## CloudFormation Templates

Located in `../customer/cloudformation/`:

| Template | Purpose |
|----------|---------|
| `aura-quick-start.yaml` | Single-click full deployment |
| `aura-foundation-only.yaml` | VPC, IAM, and security groups only |
| `aura-data-layer.yaml` | Neptune and OpenSearch databases |
| `aura-application.yaml` | EKS cluster and application services |

## Parameter Files

Located in `../customer/parameters/`:

| File | Target | Monthly Cost |
|------|--------|--------------|
| `small.json` | 1-50 developers | ~$400 |
| `medium.json` | 50-200 developers | ~$1,200 |
| `enterprise.json` | 200+ developers | ~$3,000 |
| `govcloud.json` | GovCloud/DoD | ~$4,000+ |

## Prerequisites

### AWS Requirements

- AWS CLI v2 installed and configured
- AWS account with Administrator access (initial setup only)
- Sufficient service quotas (VPCs, EC2 instances, etc.)
- Bedrock model access approved

### Bedrock Models Required

Request access to these models before installation:
- `anthropic.claude-3-5-sonnet-20241022-v1:0`
- `anthropic.claude-3-haiku-20240307-v1:0`
- `amazon.titan-embed-text-v2:0`

### Network Requirements

- VPC CIDR block (/16 recommended)
- At least 2 Availability Zones
- Internet connectivity for initial deployment

## Deployment Options

### Option 1: Quick Start (Recommended)

Deploys everything in a single CloudFormation stack:

```bash
./aura-install.sh --size medium --region us-east-1
```

### Option 2: Modular Deployment

Deploy layers independently for custom network integration:

```bash
# 1. Foundation layer (VPC, IAM, Security Groups)
aws cloudformation deploy --template-file aura-foundation-only.yaml ...

# 2. Data layer (Neptune, OpenSearch)
aws cloudformation deploy --template-file aura-data-layer.yaml ...

# 3. Application layer (EKS, S3)
aws cloudformation deploy --template-file aura-application.yaml ...
```

### Option 3: Existing VPC

Use with existing VPC infrastructure:

```bash
./aura-install.sh \
  --config custom-config.yaml \
  --existing-vpc vpc-12345678 \
  --existing-subnets subnet-abc,subnet-def
```

## GovCloud Deployment

For AWS GovCloud (US) deployment:

```bash
./aura-install.sh \
  --region us-gov-west-1 \
  --config govcloud-config.yaml
```

**GovCloud Notes:**
- Neptune Serverless is NOT available - uses provisioned mode
- Bedrock available in us-gov-west-1 only
- All ARNs use `aws-us-gov` partition
- Extended backup retention (35 days) for CMMC compliance

## Post-Installation

### Configure kubectl

```bash
aws eks update-kubeconfig --name aura-cluster-prod --region us-east-1
```

### Deploy Applications

```bash
kubectl apply -k deploy/kubernetes/overlays/prod/
```

### Access Dashboard

```bash
kubectl port-forward svc/aura-frontend 8080:80
```

### Run Verification

```bash
./verify/verify-deployment.sh aura prod us-east-1
```

## Uninstallation

### Standard Uninstall

```bash
./aura-uninstall.sh --name aura --environment prod
```

### Retain Data Backups

```bash
./aura-uninstall.sh --name aura --environment prod --retain-data
```

## Troubleshooting

### Common Issues

1. **Pre-flight check fails: Insufficient VPC quota**
   - Request quota increase via AWS Support
   - Or delete unused VPCs

2. **Neptune deployment fails**
   - Check Neptune service quota
   - Verify security group allows port 8182

3. **EKS nodes not joining**
   - Verify IAM roles and policies
   - Check node security group rules

4. **Bedrock access denied**
   - Request model access in AWS Console
   - Wait for approval (may take 24-48 hours)

### Getting Help

- Documentation: https://docs.aenealabs.com
- Support: support@aenealabs.com
- Emergency: Contact your account manager
