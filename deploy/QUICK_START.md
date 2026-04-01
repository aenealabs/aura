# Project Aura - Quick Start Guide

## Deploy Complete AWS Infrastructure

This is the fastest path to get your complete Aura infrastructure running on AWS.

---

## Prerequisites (5 minutes)

1. **AWS Account** with admin access
2. **AWS CLI installed and configured**:

   ```bash
   # Install AWS CLI
   brew install awscli  # macOS
   # Or: pip install awscli

   # Configure credentials
   aws configure
   # Enter: Access Key ID, Secret Access Key, Region (us-east-1)
   ```

3. **Python 3.11+** and dependencies:

   ```bash
   cd aura
   pip install -r requirements.txt
   pip install cfn-lint  # For template validation
   ```

4. **Alert Email** for notifications

---

## Quick Deployment (30-45 minutes total)

### Step 1: Initialize CI/CD Pipeline (5 minutes)

```bash
cd aura

# Set your alert email
export ALERT_EMAIL="your-email@example.com"

# Initialize CodeBuild pipeline and S3 artifacts bucket
./deploy/deploy.sh init
```

**This creates:**
- ✅ CodeBuild CI/CD pipeline
- ✅ S3 artifacts bucket (encrypted, versioned)
- ✅ Uploads CloudFormation templates
- ✅ SNS notifications for builds

### Step 2: Deploy Complete Infrastructure (30-45 minutes)

```bash
# Deploy full Aura stack
ALERT_EMAIL="your-email@example.com" ./deploy/deploy.sh deploy
```

**This creates (11 nested stacks):**

1. **Networking** (5-10 min)
   - ✅ VPC (10.0.0.0/16)
   - ✅ Public subnets (2 AZs)
   - ✅ Private subnets (2 AZs)
   - ✅ NAT Gateways (2x)
   - ✅ Internet Gateway
   - ✅ Route tables

2. **Security** (1 min)
   - ✅ Security groups (EKS, Neptune, OpenSearch, ALB)

3. **IAM** (2 min)
   - ✅ EKS cluster role
   - ✅ EKS node role
   - ✅ Service roles (Bedrock, S3, DynamoDB)

4. **Compute & Databases** (15-25 min - parallel)
   - ✅ EKS cluster (Kubernetes 1.28)
   - ✅ EKS node group (2-5 t3.medium nodes)
   - ✅ Neptune graph database (db.t3.medium)
   - ✅ OpenSearch vector database (t3.small.search)

5. **Storage** (2 min)
   - ✅ DynamoDB tables (4 tables)
   - ✅ S3 buckets (artifacts, code, Neptune, logs)

6. **Security & Monitoring** (3 min)
   - ✅ Secrets Manager (7 secrets)
   - ✅ CloudWatch dashboards
   - ✅ CloudWatch alarms
   - ✅ AWS Budgets (daily/monthly)

### Step 3: Post-Deployment Configuration (5 minutes)

```bash
# Configure kubectl for EKS
aws eks update-kubeconfig --name aura-cluster-dev --region us-east-1

# Verify EKS nodes are ready
kubectl get nodes

# Enable Bedrock model access (in AWS Console)
open "https://console.aws.amazon.com/bedrock/"
# Click "Model access" → "Request model access"
# Enable: Anthropic Claude 3 Sonnet and Haiku

# Update API secrets in Secrets Manager
aws secretsmanager update-secret \
  --secret-id aura/dev/api-keys \
  --secret-string '{"github_token":"YOUR_TOKEN","gitlab_token":"YOUR_TOKEN","slack_webhook":"YOUR_WEBHOOK"}' \
  --region us-east-1
```

### Step 4: Validate Deployment (2 minutes)

```bash
# Run validation script
python3 deploy/validate_aws_setup.py

# View stack outputs (endpoints, URLs)
./deploy/deploy.sh outputs

# Check CloudWatch dashboard
open "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=aura-dev"
```

**Done!** 🎉 Your complete infrastructure is ready.

### What You Now Have

✅ **Production-Ready Infrastructure** (~50 AWS resources)
- VPC with multi-AZ networking
- EKS Kubernetes cluster (2-5 nodes)
- Neptune graph database
- OpenSearch vector database
- DynamoDB tables
- S3 buckets
- Complete monitoring and cost controls

✅ **Monthly Cost**: ~$376/month (infrastructure only)

✅ **Next Steps**: Deploy Aura application to EKS

---

## Option 2: Manual Deployment (AWS Console)

If you prefer clicking through the AWS Console:

### Step 1: Deploy CloudFormation Stack

1. Open CloudFormation: <https://console.aws.amazon.com/cloudformation/>
2. Click **Create Stack** → **With new resources**
3. Upload template: `deploy/cloudformation/aura-bedrock-infrastructure.yaml`
4. Fill in parameters:
   - Stack name: `aura-bedrock-infra`
   - Environment: `development`
   - Alert Email: `your-email@example.com`
   - Daily Budget: `10`
   - Monthly Budget: `100`
5. Click **Next** → **Next** → Check "I acknowledge..." → **Create Stack**
6. Wait 3-5 minutes for creation

### Step 2: Enable Bedrock (same as above)

### Step 3: Validate (same as above)

---

## Option 3: Step-by-Step Manual (No CloudFormation)

Follow the detailed guide: `deploy/AWS_SETUP_GUIDE.md`

This walks you through creating each resource individually using AWS CLI commands.

---

## What Gets Created?

| Resource | Name | Purpose | Cost |
|----------|------|---------|------|
| IAM Role | AuraBedrockServiceRole-{env} | Permissions for Bedrock access | Free |
| Instance Profile | AuraBedrockInstanceProfile-{env} | For EC2/ECS instances | Free |
| DynamoDB Table | aura-llm-costs-{env} | Cost tracking | ~$0.50/month |
| Secret | aura/{env}/bedrock | Bedrock configuration | $0.40/month |
| SNS Topic | aura-budget-alerts-{env} | Email alerts | $0.10/month |
| CloudWatch Alarms | aura-*-budget-* | Budget monitoring | $0.30/month |
| Log Group | /aws/aura/{env} | Application logs | Free tier |

**Total Infrastructure Cost: ~$1-2/month**
(Plus Bedrock API usage: ~$1-50/month depending on usage)

---

## Verify Everything Works

### Quick Test Checklist

```bash
cd /path/to/project-aura

# 1. Check AWS credentials
aws sts get-caller-identity

# 2. Check Bedrock access
aws bedrock list-foundation-models --region us-east-1 | grep claude

# 3. Run validation
python3 deploy/validate_aws_setup.py

# 4. Test LLM service (mock mode)
python3 src/services/bedrock_llm_service.py

# 5. Test LLM service (AWS mode)
export AURA_ENV=development
python3 src/services/bedrock_llm_service.py

# 6. Run tests (optional)
python3 -m pytest tests/test_bedrock_service.py -v
```

All should pass! ✓

---

## Common Issues & Solutions

### "AccessDeniedException" when calling Bedrock

**Solution:** Enable model access in Bedrock console:

```bash
open "https://console.aws.amazon.com/bedrock/"
# Model access → Request access for Claude models
```

### "No module named pytest"

**Solution:** Install dependencies:

```bash
pip install -r requirements.txt
```

### "No AWS credentials found"

**Solution:** Configure AWS CLI:

```bash
aws configure
```

### Stack creation failed

**Solution:** Check CloudFormation events:

```bash
aws cloudformation describe-stack-events \
  --stack-name aura-bedrock-infra \
  --region us-east-1 \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]' \
  --output table
```

---

## Update Infrastructure

To update your stack with new parameters:

```bash
cd deploy/cloudformation

# Update daily budget
./deploy.sh --email your-email@example.com --daily-budget 50

# The script will show you the changes and ask for confirmation
```

---

## Delete Everything (Cleanup)

To remove all infrastructure:

```bash
cd deploy/cloudformation

# Delete the stack
./deploy.sh --delete

# Or manually:
aws cloudformation delete-stack --stack-name aura-bedrock-infra --region us-east-1
```

This removes all resources except:

- Any data in DynamoDB (deleted after 7-day retention)
- CloudWatch logs (deleted based on retention period)

---

## Next Steps After Setup

1. **Integrate with Orchestrator**
   - Replace mock LLM calls with real Bedrock
   - See: `docs/BEDROCK_INTEGRATION_README.md`

2. **Set Up Monitoring Dashboard**

   ```bash
   # View metrics in CloudWatch
   open "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:"
   ```

3. **Deploy Other Infrastructure**
   - Neptune (knowledge graph)
   - OpenSearch (vector search)
   - See: `docs/deployment_plan.md`

4. **Run Integration Tests**

   ```bash
   export RUN_INTEGRATION_TESTS=1
   python3 -m pytest tests/test_bedrock_service.py::TestIntegration -v
   ```

---

## Cost Monitoring

### View Current Spend

```python
from services.bedrock_llm_service import create_llm_service

service = create_llm_service()
summary = service.get_spend_summary()

print(f"Daily: ${summary['daily_spend']:.2f} / ${summary['daily_budget']:.2f}")
print(f"Monthly: ${summary['monthly_spend']:.2f} / ${summary['monthly_budget']:.2f}")
```

### View in AWS Console

```bash
# CloudWatch metrics
open "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#metricsV2:graph=~()"

# Cost Explorer
open "https://console.aws.amazon.com/cost-management/home#/custom"
```

---

## Support & Documentation

- **Full Setup Guide:** `deploy/AWS_SETUP_GUIDE.md`
- **Integration Guide:** `docs/BEDROCK_INTEGRATION_README.md`
- **Architecture Plan:** `docs/bedrock_integration_plan.md`
- **Validation Script:** `deploy/validate_aws_setup.py`

---

## Summary: The 10-Minute Path

```bash
# 1. Install AWS CLI (if needed)
brew install awscli

# 2. Configure credentials
aws configure

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Deploy infrastructure
cd deploy/cloudformation
./deploy.sh --email your-email@example.com

# 5. Enable Bedrock models
# Go to: https://console.aws.amazon.com/bedrock/
# Request access to Claude 3.5 Sonnet and Claude 3 Haiku

# 6. Validate
python3 ../../deploy/validate_aws_setup.py

# 7. Test
python3 ../../src/services/bedrock_llm_service.py

# ✓ Done!
```

**Time:** ~10 minutes
**Cost:** ~$1-2/month infrastructure + $1-50/month API usage
**Result:** Production-ready Bedrock integration with cost controls

---

**Last Updated:** November 2025
**Tested On:** AWS US-EAST-1
**Status:** Production Ready
