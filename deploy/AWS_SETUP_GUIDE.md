# AWS Account Setup Guide for Project Aura

## Step-by-Step Infrastructure Deployment

**Time Required:** 45-60 minutes
**Cost:** ~$0-5/month during development
**Prerequisites:** AWS account with admin access

---

## Overview

This guide will help you set up:

1. ✅ AWS Bedrock (Claude API access)
2. ✅ IAM roles and policies (secure authentication)
3. ✅ DynamoDB (cost tracking)
4. ✅ CloudWatch (monitoring and alerts)
5. ✅ Secrets Manager (configuration storage)
6. ✅ Budget alerts (cost protection)

---

## Phase 1: AWS Account Preparation (15 min)

### Step 1.1: Verify AWS CLI Installation

```bash
# Check if AWS CLI is installed
aws --version

# If not installed:
# macOS:
brew install awscli

# Linux:
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Windows:
# Download from: https://aws.amazon.com/cli/
```

### Step 1.2: Choose Your Deployment Method

You have three options for AWS credentials. Choose the one that fits your situation:

### Option A: AWS CloudShell (Recommended for Quick Start)

**Best for:** Quick deployment, no local setup needed, most secure

```bash
# 1. Log into AWS Console: https://console.aws.amazon.com/
# 2. Click the CloudShell icon (>_) in the top-right navigation bar
# 3. Wait ~30 seconds for the shell to initialize
# 4. You're ready! Credentials are pre-configured.

# Upload this project to CloudShell:
# - Click Actions → Upload file (for individual files)
# - Or use git clone if your code is in a repository

# Skip to Phase 2 - your credentials are already configured!
```

**Pros:**

- ✅ No access keys needed (more secure)
- ✅ No local AWS CLI installation required
- ✅ Credentials automatically configured
- ✅ Free to use

**Cons:**

- ⚠️ Session times out after inactivity
- ⚠️ Files are deleted after 120 days of inactivity

---

#### Option B: Create IAM User with Access Keys (Recommended for Local Development)

**Best for:** Working from your local machine, ongoing development

### **Step B.1: Create IAM User**

1. **Log into AWS Console:** <https://console.aws.amazon.com/iam/>

2. **Navigate to IAM Users:**
   - In the left sidebar, click **"Users"**
   - Click **"Create user"** button (orange button, top right)

3. **Set User Details:**
   - **User name:** `aura-admin` (or your preferred name)
   - **Provide user access to the AWS Management Console:** ✅ Check this (optional, but useful)
     - Select "I want to create an IAM user"
     - Console password: Choose "Custom password" and enter a strong password
     - ✅ Uncheck "Users must create a new password at next sign-in"
   - Click **"Next"**

4. **Set Permissions:**
   - Select **"Attach policies directly"**
   - In the search box, type: `AdministratorAccess`
   - ✅ Check the box next to **"AdministratorAccess"**
   - Click **"Next"**

5. **Review and Create:**
   - Review the settings
   - Click **"Create user"**

**⚠️ Security Note:** `AdministratorAccess` gives full access to your AWS account. This is fine for initial setup, but you should:

- Use this user only for infrastructure setup
- Rotate credentials regularly
- Consider creating a more restricted user later for day-to-day operations

### **Step B.2: Create Access Keys**

1. **Click on the newly created user** (`aura-admin`) in the users list

2. **Go to Security Credentials tab:**
   - Scroll down to **"Access keys"** section
   - Click **"Create access key"**

3. **Select Use Case:**
   - Choose **"Command Line Interface (CLI)"**
   - ✅ Check the confirmation box: "I understand the above recommendation..."
   - Click **"Next"**

4. **Set Description (Optional):**
   - Description tag: `Aura deployment from local machine`
   - Click **"Create access key"**

5. **Download Credentials:**
   - ✅ **IMPORTANT:** Click **"Download .csv file"** and save it securely
   - ⚠️ You won't be able to see the secret access key again!
   - Copy both the **Access Key ID** and **Secret Access Key**
   - Click **"Done"**

### **Step B.3: Configure AWS CLI**

```bash
# Configure AWS CLI with your new access keys
aws configure

# You'll be prompted for:
# AWS Access Key ID: [paste from downloaded CSV]
# AWS Secret Access Key: [paste from downloaded CSV]
# Default region name: us-east-1
# Default output format: json
```

### Step B.4: Verify Configuration

```bash
# Test that credentials work
aws sts get-caller-identity

# Expected output:
# {
#     "UserId": "AIDAXXXXXXXXXXXXXXXXX",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/aura-admin"
# }
```

**Credentials Security Best Practices:**

```bash
# Store credentials securely (they're in ~/.aws/credentials)
chmod 600 ~/.aws/credentials
chmod 600 ~/.aws/config

# NEVER commit these to git!
# Add to .gitignore:
echo ".aws/" >> ~/.gitignore

# Delete the downloaded CSV after configuring AWS CLI
rm ~/Downloads/aura-admin_accessKeys.csv
```

---

### Option C: Use Root User Access Keys (NOT Recommended)

**⚠️ WARNING:** AWS strongly discourages creating access keys for your root user due to security risks.

**Only use this if:**

- You absolutely cannot create an IAM user
- This is a personal/test account with no sensitive data
- You'll delete the keys immediately after setup

**If you must use root credentials:**

1. Log in as root user
2. Go to: <https://console.aws.amazon.com/iam/home#/security_credentials>
3. Click **"Access keys"** section
4. Click **"Create access key"**
5. Acknowledge the warning
6. Download and configure as in Option B

**⚠️ DELETE these root keys immediately after initial setup!**

---

### Step 1.3: Verify AWS Access (All Options)

Regardless of which option you chose above, verify your AWS access:

```bash
# Test that you can access AWS
aws sts get-caller-identity

# Expected output (format varies by option):
# CloudShell or IAM User:
# {
#     "UserId": "AIDAXXXXXXXXXXXXXXXXX",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/aura-admin"
# }
#
# Root User (if you used Option C):
# {
#     "UserId": "123456789012",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:root"
# }
```

✅ If you see your account ID and ARN, you're ready to proceed!

❌ If you get an error:

- **"Unable to locate credentials"** → Run `aws configure` with your access keys
- **"Invalid security token"** → Your credentials are wrong, recreate them
- **"Access denied"** → Your IAM user needs AdministratorAccess policy

### Step 1.4: Set Your AWS Account ID

```bash
# Get your account ID and save it as environment variable
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Your AWS Account ID: $AWS_ACCOUNT_ID"

# Save it to your shell profile (optional, for convenience)
echo "export AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID" >> ~/.bashrc  # Linux/CloudShell
# or
echo "export AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID" >> ~/.zshrc   # macOS with zsh
```

### Step 1.5: Quick Reference - What Did You Just Create?

**If you used Option A (CloudShell):**

- ✅ No permanent credentials created
- ✅ Temporary session credentials (auto-managed by AWS)
- ✅ Nothing to clean up later

**If you used Option B (IAM User):**

- ✅ IAM User: `aura-admin` with AdministratorAccess
- ✅ Access Keys stored in `~/.aws/credentials`
- ⚠️ Remember to rotate or delete these keys later

**If you used Option C (Root Keys):**

- ⚠️ Root user access keys (high security risk!)
- ⚠️ **DELETE IMMEDIATELY after initial setup:**

  ```bash
  # List your access keys
  aws iam list-access-keys

  # Delete the key (replace with your key ID)
  aws iam delete-access-key --access-key-id AKIAXXXXXXXXXXXXX
  ```

```bash
# Get your account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Your AWS Account ID: $AWS_ACCOUNT_ID"

# Save it for later
echo "export AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID" >> ~/.bashrc
```

---

## Phase 2: Enable AWS Bedrock (5 min)

### Step 2.1: Request Model Access

**Via Console (Easiest):**

1. Go to: <https://console.aws.amazon.com/bedrock/>
2. Click **"Model access"** in left sidebar
3. Click **"Request model access"** (orange button)
4. Find and enable:
   - ✅ **Anthropic → Claude 3.5 Sonnet** (anthropic.claude-3-5-sonnet-20241022-v1:0)
   - ✅ **Anthropic → Claude 3 Haiku** (anthropic.claude-3-haiku-20240307-v1:0)
5. Click **"Request model access"**
6. Wait 1-2 minutes for approval (usually instant)

**Via AWS CLI:**

```bash
# Check available models
aws bedrock list-foundation-models --region us-east-1

# Note: Model access must be requested via console first
```

### Step 2.2: Verify Model Access

```bash
# List models you have access to
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query 'modelSummaries[?starts_with(modelId, `anthropic.claude`)].{ModelId:modelId,Name:modelName}' \
  --output table

# Should show Claude 3.5 Sonnet and Claude 3 Haiku
```

### Step 2.3: Test Bedrock API (Optional)

```bash
# Test if you can invoke Claude
aws bedrock-runtime invoke-model \
  --region us-east-1 \
  --model-id anthropic.claude-3-haiku-20240307-v1:0 \
  --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":100,"messages":[{"role":"user","content":"Say hello"}]}' \
  --cli-binary-format raw-in-base64-out \
  response.json

# Check response
cat response.json
```

**Troubleshooting:**

- **"Access denied"** → Model access not granted (go back to Step 2.1)
- **"Model not found"** → Wrong region (use us-east-1) or typo in model ID
- **"ResourceNotFoundException"** → Bedrock not available in your region

---

## Phase 3: Create IAM Role & Policies (15 min)

### Step 3.1: Create Service Role for Aura

```bash
# Create trust policy for EC2/ECS/Lambda to assume role
cat > /tmp/aura-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "ec2.amazonaws.com",
          "ecs-tasks.amazonaws.com",
          "lambda.amazonaws.com"
        ]
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create the role
aws iam create-role \
  --role-name AuraBedrockServiceRole \
  --assume-role-policy-document file:///tmp/aura-trust-policy.json \
  --description "Service role for Project Aura Bedrock integration"

echo "✓ Role created: AuraBedrockServiceRole"
```

### Step 3.2: Create Bedrock Access Policy

```bash
# Create policy for Bedrock access
cat > /tmp/aura-bedrock-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockInvokeModel",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v1:0",
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
      ]
    },
    {
      "Sid": "SecretsManagerRead",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:${AWS_ACCOUNT_ID}:secret:aura/*"
    },
    {
      "Sid": "DynamoDBCostTracking",
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:${AWS_ACCOUNT_ID}:table/aura-llm-costs",
        "arn:aws:dynamodb:us-east-1:${AWS_ACCOUNT_ID}:table/aura-llm-costs/index/*"
      ]
    },
    {
      "Sid": "CloudWatchMetrics",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "Aura/LLM"
        }
      }
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:${AWS_ACCOUNT_ID}:log-group:/aws/aura/*"
    }
  ]
}
EOF

# Create the policy
aws iam create-policy \
  --policy-name AuraBedrockPolicy \
  --policy-document file:///tmp/aura-bedrock-policy.json \
  --description "Policy for Project Aura Bedrock and infrastructure access"

echo "✓ Policy created: AuraBedrockPolicy"
```

### Step 3.3: Attach Policy to Role

```bash
# Attach the policy to the role
aws iam attach-role-policy \
  --role-name AuraBedrockServiceRole \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/AuraBedrockPolicy

echo "✓ Policy attached to role"
```

### Step 3.4: Create Instance Profile (for EC2)

```bash
# Create instance profile for EC2 instances
aws iam create-instance-profile \
  --instance-profile-name AuraBedrockInstanceProfile

# Add role to instance profile
aws iam add-role-to-instance-profile \
  --instance-profile-name AuraBedrockInstanceProfile \
  --role-name AuraBedrockServiceRole

echo "✓ Instance profile created: AuraBedrockInstanceProfile"
```

### Step 3.5: Verify IAM Setup

```bash
# List role policies
aws iam list-attached-role-policies \
  --role-name AuraBedrockServiceRole \
  --output table

# Should show AuraBedrockPolicy attached
```

---

## Phase 4: Create DynamoDB Table for Cost Tracking (10 min)

### Step 4.1: Create Cost Tracking Table

```bash
# Create DynamoDB table
aws dynamodb create-table \
  --table-name aura-llm-costs \
  --attribute-definitions \
    AttributeName=request_id,AttributeType=S \
    AttributeName=date,AttributeType=S \
    AttributeName=month,AttributeType=S \
  --key-schema \
    AttributeName=request_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --tags Key=Project,Value=Aura Key=Environment,Value=production \
  --region us-east-1

echo "✓ Table created: aura-llm-costs"
echo "⏳ Waiting for table to become active..."

# Wait for table to be ready
aws dynamodb wait table-exists --table-name aura-llm-costs --region us-east-1

echo "✓ Table is active"
```

### Step 4.2: Create Global Secondary Indexes

```bash
# Create date-based index for daily queries
aws dynamodb update-table \
  --table-name aura-llm-costs \
  --attribute-definitions AttributeName=date,AttributeType=S \
  --global-secondary-index-updates \
    "[{\"Create\":{\"IndexName\":\"date-index\",\"KeySchema\":[{\"AttributeName\":\"date\",\"KeyType\":\"HASH\"}],\"Projection\":{\"ProjectionType\":\"ALL\"}}}]" \
  --region us-east-1

echo "⏳ Creating date-index..."
sleep 10

# Create month-based index for monthly queries
aws dynamodb update-table \
  --table-name aura-llm-costs \
  --attribute-definitions AttributeName=month,AttributeType=S \
  --global-secondary-index-updates \
    "[{\"Create\":{\"IndexName\":\"month-index\",\"KeySchema\":[{\"AttributeName\":\"month\",\"KeyType\":\"HASH\"}],\"Projection\":{\"ProjectionType\":\"ALL\"}}}]" \
  --region us-east-1

echo "⏳ Creating month-index..."
echo "⏳ Waiting for indexes to become active (this takes 2-5 minutes)..."

# Wait for both indexes
aws dynamodb wait table-exists --table-name aura-llm-costs --region us-east-1

echo "✓ Indexes created successfully"
```

### Step 4.3: Enable Point-in-Time Recovery

```bash
# Enable backups
aws dynamodb update-continuous-backups \
  --table-name aura-llm-costs \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
  --region us-east-1

echo "✓ Point-in-time recovery enabled"
```

### Step 4.4: Verify Table Setup

```bash
# Describe table
aws dynamodb describe-table \
  --table-name aura-llm-costs \
  --region us-east-1 \
  --query 'Table.{Name:TableName,Status:TableStatus,Billing:BillingModeSummary.BillingMode,Indexes:GlobalSecondaryIndexes[*].IndexName}' \
  --output table
```

---

## Phase 5: Set Up CloudWatch Alerts (10 min)

### Step 5.1: Create SNS Topic for Alerts

```bash
# Create SNS topic for budget alerts
aws sns create-topic \
  --name aura-budget-alerts \
  --region us-east-1

# Get the topic ARN
TOPIC_ARN=$(aws sns list-topics --region us-east-1 --query "Topics[?contains(TopicArn, 'aura-budget-alerts')].TopicArn" --output text)

echo "✓ SNS topic created: $TOPIC_ARN"
```

### Step 5.2: Subscribe Your Email

```bash
# Subscribe your email to receive alerts
read -p "Enter your email for budget alerts: " EMAIL

aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol email \
  --notification-endpoint $EMAIL \
  --region us-east-1

echo "✓ Subscription created. Check your email and confirm the subscription!"
echo "⚠️  You must click the confirmation link in the email to receive alerts"
```

### Step 5.3: Create CloudWatch Alarms

```bash
# Daily budget warning (70%)
aws cloudwatch put-metric-alarm \
  --alarm-name aura-daily-budget-warning \
  --alarm-description "Aura LLM daily costs exceeded 70% of budget" \
  --namespace Aura/LLM \
  --metric-name CostUSD \
  --statistic Sum \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 7.0 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions $TOPIC_ARN \
  --region us-east-1

echo "✓ Daily warning alarm created (70% threshold)"

# Daily budget critical (90%)
aws cloudwatch put-metric-alarm \
  --alarm-name aura-daily-budget-critical \
  --alarm-description "Aura LLM daily costs exceeded 90% of budget" \
  --namespace Aura/LLM \
  --metric-name CostUSD \
  --statistic Sum \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 9.0 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions $TOPIC_ARN \
  --region us-east-1

echo "✓ Daily critical alarm created (90% threshold)"

# Monthly budget warning
aws cloudwatch put-metric-alarm \
  --alarm-name aura-monthly-budget-warning \
  --alarm-description "Aura LLM monthly costs exceeded 80% of budget" \
  --namespace Aura/LLM \
  --metric-name CostUSD \
  --statistic Sum \
  --period 2592000 \
  --evaluation-periods 1 \
  --threshold 80.0 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions $TOPIC_ARN \
  --region us-east-1

echo "✓ Monthly warning alarm created (80% threshold)"
```

### Step 5.4: Set Up AWS Budgets (Optional but Recommended)

```bash
# Create AWS Budget for Bedrock costs
cat > /tmp/budget.json << 'EOF'
{
  "BudgetName": "AuraBedrock",
  "BudgetLimit": {
    "Amount": "100",
    "Unit": "USD"
  },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST",
  "CostFilters": {
    "Service": ["Amazon Bedrock"]
  }
}
EOF

aws budgets create-budget \
  --account-id $AWS_ACCOUNT_ID \
  --budget file:///tmp/budget.json \
  --notifications-with-subscribers \
    Type=ACTUAL,Threshold=80,ComparisonOperator=GREATER_THAN,NotificationType=THRESHOLD,ThresholdType=PERCENTAGE,Subscribers=[{SubscriptionType=EMAIL,Address=$EMAIL}] \
  --region us-east-1 2>/dev/null || echo "Budget already exists or requires billing permissions"

echo "✓ AWS Budget created (optional)"
```

---

## Phase 6: Create Secrets in Secrets Manager (5 min)

### Step 6.1: Create Bedrock Configuration Secret

```bash
# Create secret for Bedrock configuration
cat > /tmp/bedrock-secret.json << 'EOF'
{
  "model_id_primary": "anthropic.claude-3-5-sonnet-20241022-v1:0",
  "model_id_fallback": "anthropic.claude-3-haiku-20240307-v1:0",
  "max_tokens_default": 4096,
  "temperature_default": 0.7
}
EOF

aws secretsmanager create-secret \
  --name aura/prod/bedrock \
  --description "Bedrock configuration for Project Aura production" \
  --secret-string file:///tmp/bedrock-secret.json \
  --region us-east-1

echo "✓ Secret created: aura/prod/bedrock"

# Also create for dev environment
aws secretsmanager create-secret \
  --name aura/dev/bedrock \
  --description "Bedrock configuration for Project Aura development" \
  --secret-string file:///tmp/bedrock-secret.json \
  --region us-east-1

echo "✓ Secret created: aura/dev/bedrock"
```

### Step 6.2: Verify Secrets

```bash
# List secrets
aws secretsmanager list-secrets \
  --region us-east-1 \
  --query "SecretList[?starts_with(Name, 'aura/')].{Name:Name,LastChanged:LastChangedDate}" \
  --output table
```

---

## Phase 7: Test Everything (5 min)

### Step 7.1: Run Validation Script

```bash
# Go to your project directory
cd /path/to/project-aura

# Run validation script (we'll create this next)
python3 deploy/validate_aws_setup.py
```

### Step 7.2: Test Bedrock Integration

```bash
# Set environment to use AWS mode
export AURA_ENV=development

# Test with real AWS
python3 src/services/bedrock_llm_service.py
```

Expected output:

```bash
Mode: aws
Environment: development
...
✓ Success!
Response: [Real Claude response]
Cost: $0.000XXX
```

---

## Summary & Verification Checklist

Run this checklist to verify everything is set up:

```bash
# 1. Bedrock access
echo "1. Checking Bedrock access..."
aws bedrock list-foundation-models --region us-east-1 --query 'modelSummaries[?contains(modelId, `claude`)].modelId' --output text

# 2. IAM role exists
echo "2. Checking IAM role..."
aws iam get-role --role-name AuraBedrockServiceRole --query 'Role.RoleName' --output text

# 3. DynamoDB table exists
echo "3. Checking DynamoDB table..."
aws dynamodb describe-table --table-name aura-llm-costs --region us-east-1 --query 'Table.TableStatus' --output text

# 4. Secrets exist
echo "4. Checking secrets..."
aws secretsmanager list-secrets --region us-east-1 --query "SecretList[?starts_with(Name, 'aura/')].Name" --output text

# 5. SNS topic exists
echo "5. Checking SNS topic..."
aws sns list-topics --region us-east-1 --query "Topics[?contains(TopicArn, 'aura-budget-alerts')].TopicArn" --output text

# 6. CloudWatch alarms exist
echo "6. Checking CloudWatch alarms..."
aws cloudwatch describe-alarms --region us-east-1 --alarm-name-prefix aura- --query 'MetricAlarms[*].AlarmName' --output text

echo ""
echo "✓ All AWS infrastructure is set up!"
```

---

## Cost Estimate

**Monthly costs for development:**

- DynamoDB (PAY_PER_REQUEST): ~$0.50/month
- CloudWatch alarms: $0.10/alarm × 3 = $0.30/month
- Secrets Manager: $0.40/secret × 2 = $0.80/month
- Bedrock API calls: ~$1-5/month (testing)
**Total: ~$3-7/month during development**

---

## Troubleshooting

### "Access Denied" Errors

**Problem:** IAM permissions not correct

**Solution:**

```bash
# Verify role has policy attached
aws iam list-attached-role-policies --role-name AuraBedrockServiceRole

# If missing, reattach
aws iam attach-role-policy \
  --role-name AuraBedrockServiceRole \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/AuraBedrockPolicy
```

### DynamoDB Index Creation Failed

**Problem:** Indexes already exist or table in wrong state

**Solution:**

```bash
# Check table status
aws dynamodb describe-table --table-name aura-llm-costs --query 'Table.TableStatus'

# If status is CREATING, wait 2-5 minutes
# If indexes exist, skip that step
```

### SNS Email Not Received

**Problem:** Email delivery delayed or in spam

**Solution:**

1. Check spam folder
2. Verify subscription: `aws sns list-subscriptions --region us-east-1`
3. Resend confirmation: Delete subscription and recreate

---

## Next Steps

After completing this setup:

1. ✅ **Test the integration**

   ```bash
   cd /path/to/project-aura
   python3 src/services/bedrock_llm_service.py
   ```

2. ✅ **Integrate with orchestrator**
   - Replace mock LLM calls with real Bedrock
   - See: `docs/BEDROCK_INTEGRATION_README.md`

3. ✅ **Set up monitoring dashboard**
   - CloudWatch → Dashboards → Create
   - Add widgets for Aura/LLM metrics

4. ✅ **Deploy other infrastructure**
   - Neptune (knowledge graph)
   - OpenSearch (vector search)
   - See: `docs/deployment_plan.md`

---

## Cleanup (If Needed)

To remove all resources:

```bash
# Delete DynamoDB table
aws dynamodb delete-table --table-name aura-llm-costs --region us-east-1

# Delete IAM resources
aws iam detach-role-policy --role-name AuraBedrockServiceRole --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/AuraBedrockPolicy
aws iam remove-role-from-instance-profile --instance-profile-name AuraBedrockInstanceProfile --role-name AuraBedrockServiceRole
aws iam delete-instance-profile --instance-profile-name AuraBedrockInstanceProfile
aws iam delete-role --role-name AuraBedrockServiceRole
aws iam delete-policy --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/AuraBedrockPolicy

# Delete secrets
aws secretsmanager delete-secret --secret-id aura/prod/bedrock --force-delete-without-recovery --region us-east-1
aws secretsmanager delete-secret --secret-id aura/dev/bedrock --force-delete-without-recovery --region us-east-1

# Delete SNS topic
aws sns delete-topic --topic-arn $TOPIC_ARN --region us-east-1

# Delete CloudWatch alarms
aws cloudwatch delete-alarms --alarm-names aura-daily-budget-warning aura-daily-budget-critical aura-monthly-budget-warning --region us-east-1
```

---

**Document Version:** 1.0
**Last Updated:** November 2025
**Estimated Setup Time:** 45-60 minutes
**Difficulty:** Intermediate
