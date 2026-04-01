# Aura Infrastructure Deployment Guide

## Overview

This guide covers deploying the complete Aura infrastructure to AWS using CloudFormation and CodeBuild for a production-quality, automated Infrastructure as Code (IaC) setup.

## Architecture

The infrastructure is organized into nested CloudFormation stacks:

1. **Master Stack** (`master-stack.yaml`) - Orchestrates all nested stacks
2. **Networking** - VPC, subnets, NAT gateways, Internet Gateway
3. **Security** - Security groups for EKS, Neptune, OpenSearch, ALB
4. **IAM** - Roles and policies for all services
5. **EKS** - Kubernetes cluster and node groups
6. **Neptune** - Graph database cluster
7. **OpenSearch** - Vector search domain
8. **DynamoDB** - Tables for cost tracking, sessions, jobs, metadata
9. **S3** - Buckets for artifacts, code, Neptune bulk loads, logs
10. **Secrets** - Secrets Manager for credentials and config
11. **Monitoring** - CloudWatch dashboards, alarms, log groups
12. **Cost Alerts** - AWS Budgets and cost monitoring

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
3. **Python 3.11+** for validation scripts
4. **Alert Email** configured for notifications

## Deployment Methods

### Method 1: Manual Deployment (First Time)

#### Step 1: Deploy CodeBuild Pipeline

```bash
# Set your alert email
export ALERT_EMAIL="your-email@example.com"

# Deploy the CodeBuild stack
aws cloudformation create-stack \
  --stack-name aura-codebuild-dev \
  --template-body file://deploy/cloudformation/codebuild.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=ProjectName,ParameterValue=aura \
    ParameterKey=AlertEmail,ParameterValue=$ALERT_EMAIL \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# Wait for completion
aws cloudformation wait stack-create-complete \
  --stack-name aura-codebuild-dev \
  --region us-east-1
```

#### Step 2: Upload Templates to S3

```bash
# Get the AWS account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ARTIFACT_BUCKET="aura-cfn-artifacts-${AWS_ACCOUNT_ID}-dev"

# Create the artifacts bucket
aws s3 mb "s3://${ARTIFACT_BUCKET}" --region us-east-1

# Configure bucket encryption
aws s3api put-bucket-encryption \
  --bucket "${ARTIFACT_BUCKET}" \
  --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Block public access
aws s3api put-public-access-block \
  --bucket "${ARTIFACT_BUCKET}" \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Upload nested templates
aws s3 sync deploy/cloudformation/ "s3://${ARTIFACT_BUCKET}/cloudformation/" \
  --exclude "master-stack.yaml" \
  --exclude "codebuild.yaml" \
  --region us-east-1
```

#### Step 3: Deploy Master Stack

```bash
# Deploy the master infrastructure stack
aws cloudformation create-stack \
  --stack-name aura-dev \
  --template-body file://deploy/cloudformation/master-stack.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=ProjectName,ParameterValue=aura \
    ParameterKey=AlertEmail,ParameterValue=$ALERT_EMAIL \
    ParameterKey=VpcCIDR,ParameterValue=10.0.0.0/16 \
    ParameterKey=AvailabilityZones,ParameterValue="us-east-1a,us-east-1b" \
    ParameterKey=EKSNodeInstanceType,ParameterValue=t3.medium \
    ParameterKey=EKSNodeGroupMinSize,ParameterValue=2 \
    ParameterKey=EKSNodeGroupMaxSize,ParameterValue=5 \
    ParameterKey=NeptuneInstanceType,ParameterValue=db.t3.medium \
    ParameterKey=OpenSearchInstanceType,ParameterValue=t3.small.search \
    ParameterKey=DailyBudget,ParameterValue=15 \
    ParameterKey=MonthlyBudget,ParameterValue=400 \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# This will take 30-45 minutes
aws cloudformation wait stack-create-complete \
  --stack-name aura-dev \
  --region us-east-1
```

### Method 2: Automated Deployment via CodeBuild

Once the CodeBuild pipeline is set up, use it for all deployments:

```bash
# Start a build
aws codebuild start-build \
  --project-name aura-infra-deploy-dev \
  --region us-east-1

# Monitor build progress
aws codebuild batch-get-builds \
  --ids <build-id> \
  --region us-east-1
```

## Post-Deployment Configuration

### 1. Configure kubectl for EKS

```bash
# Update kubeconfig
aws eks update-kubeconfig \
  --name aura-cluster-dev \
  --region us-east-1

# Verify connection
kubectl get nodes
```

### 2. Update API Keys in Secrets Manager

```bash
# Update GitHub token
aws secretsmanager update-secret \
  --secret-id aura/dev/api-keys \
  --secret-string '{"github_token":"YOUR_TOKEN","gitlab_token":"YOUR_TOKEN","slack_webhook":"YOUR_WEBHOOK"}' \
  --region us-east-1
```

### 3. Verify Infrastructure

```bash
# Run validation script
python3 deploy/validate_aws_setup.py
```

### 4. Check Costs

```bash
# View current infrastructure costs
python3 tools/aws_cost_calculator.py --scenario development
```

## Stack Outputs

After deployment, retrieve important endpoints:

```bash
aws cloudformation describe-stacks \
  --stack-name aura-dev \
  --query 'Stacks[0].Outputs' \
  --output table \
  --region us-east-1
```

Key outputs:
- **EKS Cluster Endpoint** - Kubernetes API server
- **Neptune Cluster Endpoint** - Graph database connection
- **OpenSearch Domain Endpoint** - Vector search endpoint
- **CloudWatch Dashboard URL** - Monitoring dashboard

## Updating Infrastructure

### Option 1: Via CodeBuild (Recommended)

```bash
# Make changes to CloudFormation templates
# Commit and push to repository
# CodeBuild will automatically deploy (if configured with GitHub webhook)

# Or manually trigger
aws codebuild start-build --project-name aura-infra-deploy-dev
```

### Option 2: Manual Update

```bash
# Upload updated templates
aws s3 sync deploy/cloudformation/ "s3://${ARTIFACT_BUCKET}/cloudformation/" \
  --exclude "master-stack.yaml" \
  --exclude "codebuild.yaml"

# Update stack
aws cloudformation update-stack \
  --stack-name aura-dev \
  --template-body file://deploy/cloudformation/master-stack.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=ProjectName,ParameterValue=aura \
    ParameterKey=AlertEmail,ParameterValue=$ALERT_EMAIL \
    [... other parameters ...] \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

## Cost Monitoring

### View Current Costs

```bash
# Check AWS Cost Explorer
aws ce get-cost-and-usage \
  --time-period Start=2025-01-01,End=2025-01-31 \
  --granularity DAILY \
  --metrics "UnblendedCost" \
  --filter file://cost-filter.json
```

### Budget Alerts

Budgets are automatically configured:
- **Daily**: Alert at 70%, 90%, 100% of $15/day
- **Monthly**: Alert at 50%, 80%, 100% of $400/month

## Troubleshooting

### Stack Creation Failed

```bash
# Check events
aws cloudformation describe-stack-events \
  --stack-name aura-dev \
  --max-items 20 \
  --region us-east-1

# Check specific nested stack
aws cloudformation describe-stack-events \
  --stack-name aura-dev-NetworkingStack-XXXXX \
  --region us-east-1
```

### EKS Nodes Not Joining

```bash
# Check node group status
aws eks describe-nodegroup \
  --cluster-name aura-cluster-dev \
  --nodegroup-name aura-nodegroup-dev \
  --region us-east-1

# Check worker node logs
kubectl logs -n kube-system -l k8s-app=aws-node
```

### Neptune Connection Issues

```bash
# Test connectivity from EKS pod
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- sh
# Inside pod:
curl https://<neptune-endpoint>:8182/status
```

### OpenSearch Access Issues

```bash
# Get OpenSearch endpoint
aws opensearch describe-domain \
  --domain-name aura-dev \
  --query 'DomainStatus.Endpoint' \
  --output text \
  --region us-east-1

# Test from EKS pod
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- sh
# Inside pod (use credentials from Secrets Manager):
curl -u admin:password https://<opensearch-endpoint>/_cluster/health
```

## Cleanup

To tear down the entire infrastructure:

```bash
# Delete master stack (will delete all nested stacks)
aws cloudformation delete-stack \
  --stack-name aura-dev \
  --region us-east-1

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name aura-dev \
  --region us-east-1

# Delete CodeBuild stack
aws cloudformation delete-stack \
  --stack-name aura-codebuild-dev \
  --region us-east-1

# Manually delete S3 buckets (CloudFormation won't delete non-empty buckets)
aws s3 rm "s3://aura-cfn-artifacts-${AWS_ACCOUNT_ID}-dev" --recursive
aws s3 rb "s3://aura-cfn-artifacts-${AWS_ACCOUNT_ID}-dev"

# Delete other S3 buckets created by the stack
aws s3 ls | grep aura | while read -r line; do
  bucket=$(echo $line | awk '{print $3}')
  aws s3 rm "s3://${bucket}" --recursive
  aws s3 rb "s3://${bucket}"
done
```

## Cost Estimates

### DEV Environment (Minimal)
- **Monthly Infrastructure**: ~$376
  - EKS Control Plane: $72
  - EC2 (2x t3.medium): $60
  - Neptune (1x db.t3.medium): $99
  - OpenSearch (1x t3.small): $31
  - NAT Gateway: $66
  - Other services: $48

### Production Environment (High Availability)
- **Monthly Infrastructure**: ~$1,624
  - Includes multi-AZ deployment
  - Additional replicas for Neptune and OpenSearch
  - Increased backup retention
  - Additional monitoring

**Note**: Bedrock API costs are usage-based and depend on token consumption.

## Security Best Practices

1. **Rotate Secrets Regularly**
   - Use Secrets Manager rotation for database passwords
   - Rotate API keys every 90 days

2. **Enable MFA**
   - Require MFA for AWS console access
   - Use IAM roles with temporary credentials

3. **Monitor Access**
   - Review CloudTrail logs weekly
   - Set up AWS Config rules for compliance

4. **Network Security**
   - All databases in private subnets
   - No public internet access to data stores
   - VPC Flow Logs enabled

## Support

For issues or questions:
- Check CloudWatch Logs: `/aws/codebuild/aura-infra-deploy-dev`
- Review stack events in CloudFormation console
- Run validation script: `python3 deploy/validate_aws_setup.py`
