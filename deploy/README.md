# Aura Infrastructure Deployment

This directory contains all Infrastructure as Code (IaC) for deploying Project Aura to AWS.

## 🚀 New: Modular CI/CD Pipeline

We've implemented a **modular, layer-based deployment system** that:
- ✅ Only deploys infrastructure layers that have changed (faster builds)
- ✅ Automatically manages dependencies between layers
- ✅ Scales from 1-3 person teams to large organizations
- ✅ Ready to split into team-owned projects when you grow

**See [MODULAR_DEPLOYMENT.md](./MODULAR_DEPLOYMENT.md) for the complete guide.**

## Quick Start

### 1. Initial Setup (One-time)

```bash
# Set your alert email
export ALERT_EMAIL="your-email@example.com"

# Run initialization
./deploy/deploy.sh init
```

This will:
- Deploy CodeBuild CI/CD pipeline
- Create S3 artifacts bucket
- Upload CloudFormation templates
- Set up build notifications

### 2. Deploy Infrastructure

```bash
# Deploy the full stack
ALERT_EMAIL="your-email@example.com" ./deploy/deploy.sh deploy
```

This takes **30-45 minutes** and creates:
- VPC with public/private subnets across 2 AZs
- EKS cluster with 2-5 t3.medium nodes
- Neptune graph database (db.t3.medium)
- OpenSearch vector database (t3.small.search)
- DynamoDB tables for tracking
- S3 buckets for storage
- Secrets Manager for credentials
- CloudWatch monitoring and alarms
- Cost budgets and alerts

## Directory Structure

```
deploy/
├── cloudformation/           # CloudFormation templates
│   ├── master-stack.yaml    # Main orchestration stack
│   ├── networking.yaml      # VPC, subnets, NAT gateways
│   ├── security.yaml        # Security groups
│   ├── iam.yaml            # IAM roles and policies
│   ├── eks.yaml            # EKS cluster
│   ├── neptune.yaml        # Neptune graph database
│   ├── opensearch.yaml     # OpenSearch vector database
│   ├── dynamodb.yaml       # DynamoDB tables
│   ├── s3.yaml             # S3 buckets
│   ├── secrets.yaml        # Secrets Manager
│   ├── monitoring.yaml     # CloudWatch monitoring
│   ├── aura-cost-alerts.yaml # Cost budgets
│   └── codebuild.yaml      # CodeBuild pipeline
├── buildspec.yml           # CodeBuild build specification
├── deploy.sh               # Deployment automation script
├── validate_aws_setup.py   # Post-deployment validation
├── DEPLOYMENT_GUIDE.md     # Detailed deployment guide
├── QUICK_START.md          # Quick start guide
└── AWS_SETUP_GUIDE.md      # AWS account setup guide
```

## Architecture Overview

### Nested Stack Design

The infrastructure uses CloudFormation nested stacks for modularity:

```
master-stack.yaml
├── networking.yaml      (VPC, subnets, NAT, IGW)
├── security.yaml        (Security groups)
├── iam.yaml            (IAM roles)
├── eks.yaml            (Kubernetes cluster) [depends: networking, security, iam]
├── neptune.yaml        (Graph database) [depends: networking, security]
├── opensearch.yaml     (Vector search) [depends: networking, security]
├── dynamodb.yaml       (NoSQL tables)
├── s3.yaml             (Object storage)
├── secrets.yaml        (Credentials) [depends: neptune, opensearch]
├── monitoring.yaml     (CloudWatch)
└── aura-cost-alerts.yaml (Budgets)
```

### Network Architecture

```
VPC (10.0.0.0/16)
├── Public Subnets (2 AZs)
│   ├── 10.0.0.0/24 (us-east-1a)
│   ├── 10.0.1.0/24 (us-east-1b)
│   └── Internet Gateway
├── Private Subnets (2 AZs)
│   ├── 10.0.3.0/24 (us-east-1a) - EKS, Neptune, OpenSearch
│   ├── 10.0.4.0/24 (us-east-1b) - EKS, Neptune, OpenSearch
│   └── NAT Gateways (2x for HA)
└── VPC Flow Logs
```

## Deployment Commands

### Using deploy.sh Script (Recommended)

```bash
# Validate templates
./deploy/deploy.sh validate

# Check deployment status
./deploy/deploy.sh status

# View stack outputs
./deploy/deploy.sh outputs

# Deploy infrastructure
ALERT_EMAIL="you@example.com" ./deploy/deploy.sh deploy

# Destroy infrastructure
./deploy/deploy.sh destroy
```

### Using AWS CLI Directly

```bash
# Deploy CodeBuild pipeline
aws cloudformation create-stack \
  --stack-name aura-codebuild-dev \
  --template-body file://deploy/cloudformation/codebuild.yaml \
  --parameters ParameterKey=AlertEmail,ParameterValue=your@email.com \
  --capabilities CAPABILITY_NAMED_IAM

# Deploy main infrastructure
aws cloudformation create-stack \
  --stack-name aura-dev \
  --template-body file://deploy/cloudformation/master-stack.yaml \
  --parameters ParameterKey=AlertEmail,ParameterValue=your@email.com \
  --capabilities CAPABILITY_NAMED_IAM
```

### Using CodeBuild (CI/CD)

```bash
# Trigger build via CLI
aws codebuild start-build --project-name aura-infra-deploy-dev

# Or configure GitHub webhook for automatic builds
```

## Post-Deployment Steps

### 1. Configure kubectl

```bash
aws eks update-kubeconfig --name aura-cluster-dev --region us-east-1
kubectl get nodes
```

### 2. Update Secrets

```bash
# Update API keys
aws secretsmanager update-secret \
  --secret-id aura/dev/api-keys \
  --secret-string '{"github_token":"xxx","gitlab_token":"xxx","slack_webhook":"xxx"}'
```

### 3. Verify Deployment

```bash
python3 deploy/validate_aws_setup.py
```

### 4. Access Endpoints

```bash
# Get all endpoints
aws cloudformation describe-stacks \
  --stack-name aura-dev \
  --query 'Stacks[0].Outputs' \
  --output table
```

## Cost Management

### Monthly Cost Estimates

**DEV Environment**: ~$376/month
- EKS Control Plane: $72
- EC2 (2x t3.medium): $60
- Neptune (1x db.t3.medium): $99
- OpenSearch (1x t3.small): $31
- NAT Gateway: $66
- Other: $48

**PROD Environment**: ~$1,624/month
- Multi-AZ with replicas
- Enhanced monitoring
- Backup retention

### Cost Monitoring

Automatic budget alerts are configured:
- **Daily Budget**: $15/day (alerts at 70%, 90%, 100%)
- **Monthly Budget**: $400/month (alerts at 50%, 80%, 100%)

View costs:
```bash
python3 tools/aws_cost_calculator.py --scenario development
```

## Troubleshooting

### Template Validation Failed

```bash
# Run cfn-lint
cfn-lint deploy/cloudformation/*.yaml
```

### Stack Creation Failed

```bash
# Check events
aws cloudformation describe-stack-events \
  --stack-name aura-dev \
  --max-items 20
```

### EKS Nodes Not Ready

```bash
# Check node group
aws eks describe-nodegroup \
  --cluster-name aura-cluster-dev \
  --nodegroup-name aura-nodegroup-dev
```

### Database Connection Issues

```bash
# Test from EKS pod
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- sh

# Inside pod - test Neptune
curl https://<neptune-endpoint>:8182/status

# Test OpenSearch
curl -u admin:password https://<opensearch-endpoint>/_cluster/health
```

## Security Notes

- All databases are in private subnets (no internet access)
- VPC Flow Logs enabled for network monitoring
- All data encrypted at rest (S3, EBS, Neptune, OpenSearch, DynamoDB)
- All data encrypted in transit (TLS 1.2+)
- Secrets managed via AWS Secrets Manager
- IAM roles follow least privilege principle
- Security groups restrict access to known sources

## Updating Infrastructure

### Update via CodeBuild

1. Modify CloudFormation templates
2. Commit and push changes
3. Trigger build: `aws codebuild start-build --project-name aura-infra-deploy-dev`

### Update via CLI

1. Upload templates: `aws s3 sync deploy/cloudformation/ s3://<bucket>/cloudformation/`
2. Update stack: `aws cloudformation update-stack --stack-name aura-dev --template-body file://...`

## Stack Deletion

```bash
# Delete infrastructure
./deploy/deploy.sh destroy

# Or manually
aws cloudformation delete-stack --stack-name aura-dev
aws cloudformation wait stack-delete-complete --stack-name aura-dev

# Manually empty and delete S3 buckets
aws s3 rb s3://aura-artifacts-123456789-dev --force
```

## Parameters Reference

### Master Stack Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Environment | dev | Environment name (dev/qa/prod) |
| ProjectName | aura | Project name |
| VpcCIDR | 10.0.0.0/16 | VPC CIDR block |
| AvailabilityZones | us-east-1a,us-east-1b | List of AZs |
| EKSNodeInstanceType | t3.medium | EKS worker node type |
| EKSNodeGroupMinSize | 2 | Min EKS nodes |
| EKSNodeGroupMaxSize | 5 | Max EKS nodes |
| NeptuneInstanceType | db.t3.medium | Neptune instance type |
| OpenSearchInstanceType | t3.small.search | OpenSearch instance type |
| AlertEmail | (required) | Email for alerts |
| DailyBudget | 15 | Daily budget in USD |
| MonthlyBudget | 400 | Monthly budget in USD |

## Resources Created

### Networking
- 1 VPC
- 2-3 Public Subnets
- 2-3 Private Subnets
- 1 Internet Gateway
- 2 NAT Gateways
- 3 Route Tables
- VPC Flow Logs

### Compute
- 1 EKS Cluster
- 1 EKS Node Group (2-5 nodes)
- OIDC Provider for IRSA

### Databases
- 1 Neptune Cluster (1-2 instances)
- 1 OpenSearch Domain (1-3 nodes)
- 4 DynamoDB Tables

### Storage
- 4-5 S3 Buckets (artifacts, code, Neptune, logs, backups)

### Security
- 6 Security Groups
- 7 IAM Roles
- 7 Secrets Manager Secrets

### Monitoring
- 1 CloudWatch Dashboard
- 6 CloudWatch Alarms
- 2 CloudWatch Log Groups
- 2 Metric Filters
- 1 SNS Topic
- 2 AWS Budgets

## Support

- Full deployment guide: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- Quick start: [QUICK_START.md](QUICK_START.md)
- AWS setup: [AWS_SETUP_GUIDE.md](AWS_SETUP_GUIDE.md)
- Validation script: `python3 deploy/validate_aws_setup.py`
