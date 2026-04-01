#!/bin/bash

################################################################################
# Deploy Drift Protection & Compliance Monitoring
#
# This script deploys the dual-layer drift protection system:
# 1. CloudFormation drift detection (Lambda + EventBridge)
# 2. AWS Config compliance monitoring (18 managed rules)
#
# Usage:
#   ./deploy-drift-protection.sh <environment> <alert-email>
#
# Example:
#   ./deploy-drift-protection.sh dev your-email@example.com
#   ./deploy-drift-protection.sh prod security-team@example.com
#
# Author: Project Aura Team
# Version: 1.0
# Last Updated: 2025-11-24
################################################################################

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="aura"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Parse arguments
if [ "$#" -lt 2 ]; then
    echo -e "${RED}Error: Missing required arguments${NC}"
    echo ""
    echo "Usage: $0 <environment> <alert-email>"
    echo ""
    echo "Arguments:"
    echo "  environment   - Environment name (dev, qa, staging, prod)"
    echo "  alert-email   - Email address for drift/compliance alerts"
    echo ""
    echo "Example:"
    echo "  $0 dev your-email@example.com"
    exit 1
fi

ENVIRONMENT="$1"
ALERT_EMAIL="$2"

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|qa|staging|prod)$ ]]; then
    echo -e "${RED}Error: Invalid environment '${ENVIRONMENT}'${NC}"
    echo "Valid values: dev, qa, staging, prod"
    exit 1
fi

# Validate email format
if [[ ! "$ALERT_EMAIL" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
    echo -e "${RED}Error: Invalid email address '${ALERT_EMAIL}'${NC}"
    exit 1
fi

# Set deployment parameters based on environment
if [ "$ENVIRONMENT" == "prod" ]; then
    DRIFT_SCHEDULE="rate(6 hours)"
    AUTO_REMEDIATION="false"
    CONFIG_FREQUENCY="Six_Hours"
else
    DRIFT_SCHEDULE="rate(12 hours)"  # Less frequent for dev/qa to save costs
    AUTO_REMEDIATION="false"  # Can be enabled for dev/qa if desired
    CONFIG_FREQUENCY="Twelve_Hours"
fi

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="$(dirname "$SCRIPT_DIR")/cloudformation"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Drift Protection Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  Project:       $PROJECT_NAME"
echo "  Environment:   $ENVIRONMENT"
echo "  Region:        $AWS_REGION"
echo "  Alert Email:   $ALERT_EMAIL"
echo "  Drift Check:   $DRIFT_SCHEDULE"
echo "  Auto-Fix:      $AUTO_REMEDIATION"
echo "  Config Freq:   $CONFIG_FREQUENCY"
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI not found${NC}"
    echo "Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: AWS credentials not configured${NC}"
    echo "Run: aws configure"
    exit 1
fi

# Check templates exist
DRIFT_TEMPLATE="${TEMPLATE_DIR}/drift-detection.yaml"
CONFIG_TEMPLATE="${TEMPLATE_DIR}/config-compliance.yaml"

if [ ! -f "$DRIFT_TEMPLATE" ]; then
    echo -e "${RED}Error: Template not found: $DRIFT_TEMPLATE${NC}"
    exit 1
fi

if [ ! -f "$CONFIG_TEMPLATE" ]; then
    echo -e "${RED}Error: Template not found: $CONFIG_TEMPLATE${NC}"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Step 1: Deploy Drift Detection${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

DRIFT_STACK_NAME="${PROJECT_NAME}-drift-detection-${ENVIRONMENT}"

# Check if stack exists
if aws cloudformation describe-stacks --stack-name "$DRIFT_STACK_NAME" --region "$AWS_REGION" &> /dev/null; then
    echo -e "${YELLOW}Stack '$DRIFT_STACK_NAME' already exists. Updating...${NC}"
    ACTION="update-stack"
    WAIT_CMD="stack-update-complete"
else
    echo -e "${GREEN}Creating stack '$DRIFT_STACK_NAME'...${NC}"
    ACTION="create-stack"
    WAIT_CMD="stack-create-complete"
fi

aws cloudformation "$ACTION" \
    --stack-name "$DRIFT_STACK_NAME" \
    --template-body "file://${DRIFT_TEMPLATE}" \
    --parameters \
        ParameterKey=ProjectName,ParameterValue="$PROJECT_NAME" \
        ParameterKey=Environment,ParameterValue="$ENVIRONMENT" \
        ParameterKey=AlertEmail,ParameterValue="$ALERT_EMAIL" \
        ParameterKey=DriftDetectionSchedule,ParameterValue="$DRIFT_SCHEDULE" \
        ParameterKey=EnableAutomaticRemediation,ParameterValue="$AUTO_REMEDIATION" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$AWS_REGION" \
    --tags \
        Key=Project,Value="$PROJECT_NAME" \
        Key=Environment,Value="$ENVIRONMENT" \
        Key=ManagedBy,Value=CloudFormation \
        Key=Purpose,Value=DriftProtection

echo ""
echo -e "${YELLOW}Waiting for stack operation to complete...${NC}"
aws cloudformation wait "$WAIT_CMD" \
    --stack-name "$DRIFT_STACK_NAME" \
    --region "$AWS_REGION"

echo -e "${GREEN}✓ Drift detection stack deployed successfully${NC}"
echo ""

# Get outputs
DRIFT_TOPIC_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$DRIFT_STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`DriftAlertTopicArn`].OutputValue' \
    --output text)

DRIFT_LAMBDA_NAME=$(aws cloudformation describe-stacks \
    --stack-name "$DRIFT_STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`DriftDetectorFunctionName`].OutputValue' \
    --output text)

echo -e "${BLUE}Drift Detection Outputs:${NC}"
echo "  SNS Topic:       $DRIFT_TOPIC_ARN"
echo "  Lambda Function: $DRIFT_LAMBDA_NAME"
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Step 2: Deploy AWS Config Compliance${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

CONFIG_STACK_NAME="${PROJECT_NAME}-config-compliance-${ENVIRONMENT}"

# Check if stack exists
if aws cloudformation describe-stacks --stack-name "$CONFIG_STACK_NAME" --region "$AWS_REGION" &> /dev/null; then
    echo -e "${YELLOW}Stack '$CONFIG_STACK_NAME' already exists. Updating...${NC}"
    ACTION="update-stack"
    WAIT_CMD="stack-update-complete"
else
    echo -e "${GREEN}Creating stack '$CONFIG_STACK_NAME'...${NC}"
    ACTION="create-stack"
    WAIT_CMD="stack-create-complete"
fi

aws cloudformation "$ACTION" \
    --stack-name "$CONFIG_STACK_NAME" \
    --template-body "file://${CONFIG_TEMPLATE}" \
    --parameters \
        ParameterKey=ProjectName,ParameterValue="$PROJECT_NAME" \
        ParameterKey=Environment,ParameterValue="$ENVIRONMENT" \
        ParameterKey=AlertEmail,ParameterValue="$ALERT_EMAIL" \
        ParameterKey=ConfigSnapshotDeliveryFrequency,ParameterValue="$CONFIG_FREQUENCY" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$AWS_REGION" \
    --tags \
        Key=Project,Value="$PROJECT_NAME" \
        Key=Environment,Value="$ENVIRONMENT" \
        Key=ManagedBy,Value=CloudFormation \
        Key=Purpose,Value=ComplianceMonitoring

echo ""
echo -e "${YELLOW}Waiting for stack operation to complete...${NC}"
aws cloudformation wait "$WAIT_CMD" \
    --stack-name "$CONFIG_STACK_NAME" \
    --region "$AWS_REGION"

echo -e "${GREEN}✓ AWS Config compliance stack deployed successfully${NC}"
echo ""

# Get outputs
CONFIG_TOPIC_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$CONFIG_STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`ConfigAlertTopicArn`].OutputValue' \
    --output text)

CONFIG_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "$CONFIG_STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`ConfigBucketName`].OutputValue' \
    --output text)

CONFIG_RULES_COUNT=$(aws cloudformation describe-stacks \
    --stack-name "$CONFIG_STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`ComplianceRulesCount`].OutputValue' \
    --output text)

echo -e "${BLUE}AWS Config Outputs:${NC}"
echo "  SNS Topic:       $CONFIG_TOPIC_ARN"
echo "  S3 Bucket:       $CONFIG_BUCKET"
echo "  Config Rules:    $CONFIG_RULES_COUNT"
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Step 3: Verify Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Test drift detection Lambda
echo -e "${YELLOW}Testing drift detection Lambda...${NC}"
aws lambda invoke \
    --function-name "$DRIFT_LAMBDA_NAME" \
    --payload '{}' \
    --region "$AWS_REGION" \
    /tmp/drift-test-response.json > /dev/null

DRIFT_TEST_RESULT=$(cat /tmp/drift-test-response.json | jq -r '.statusCode')
if [ "$DRIFT_TEST_RESULT" == "200" ]; then
    echo -e "${GREEN}✓ Drift detection Lambda is working${NC}"
else
    echo -e "${RED}✗ Drift detection Lambda test failed${NC}"
    cat /tmp/drift-test-response.json
fi
rm /tmp/drift-test-response.json
echo ""

# Check Config recorder status
echo -e "${YELLOW}Checking AWS Config recorder status...${NC}"
CONFIG_RECORDER_NAME="${PROJECT_NAME}-config-recorder-${ENVIRONMENT}"
RECORDER_STATUS=$(aws configservice describe-configuration-recorder-status \
    --configuration-recorder-names "$CONFIG_RECORDER_NAME" \
    --region "$AWS_REGION" \
    --query 'ConfigurationRecordersStatus[0].recording' \
    --output text 2>/dev/null || echo "false")

if [ "$RECORDER_STATUS" == "True" ]; then
    echo -e "${GREEN}✓ AWS Config recorder is active${NC}"
else
    echo -e "${YELLOW}⚠ AWS Config recorder is not recording yet${NC}"
    echo -e "${YELLOW}  Starting recorder...${NC}"
    aws configservice start-configuration-recorder \
        --configuration-recorder-name "$CONFIG_RECORDER_NAME" \
        --region "$AWS_REGION"
    echo -e "${GREEN}✓ AWS Config recorder started${NC}"
fi
echo ""

# List Config rules
echo -e "${YELLOW}Listing AWS Config compliance rules...${NC}"
aws configservice describe-config-rules \
    --region "$AWS_REGION" \
    --query "ConfigRules[?starts_with(ConfigRuleName, '${PROJECT_NAME}-')].ConfigRuleName" \
    --output table

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deployment Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${GREEN}✓ Drift protection system deployed successfully${NC}"
echo ""
echo -e "${YELLOW}⚠ IMPORTANT: Confirm SNS email subscriptions${NC}"
echo ""
echo "You will receive 2 confirmation emails at ${ALERT_EMAIL}:"
echo "  1. Drift detection alerts"
echo "  2. AWS Config compliance alerts"
echo ""
echo "Click the confirmation links in both emails to activate alerts."
echo ""

echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo "1. Confirm SNS email subscriptions (check your inbox)"
echo "2. Review drift detection logs:"
echo "   aws logs tail /aws/lambda/${DRIFT_LAMBDA_NAME} --follow"
echo ""
echo "3. View AWS Config compliance dashboard:"
echo "   https://console.aws.amazon.com/config/home?region=${AWS_REGION}#/dashboard"
echo ""
echo "4. Manually trigger drift detection:"
echo "   aws lambda invoke --function-name ${DRIFT_LAMBDA_NAME} --payload '{}' response.json"
echo ""
echo "5. Check compliance status:"
echo "   aws configservice describe-compliance-by-config-rule --region ${AWS_REGION}"
echo ""

echo -e "${BLUE}Cost Estimate:${NC}"
echo "  Drift Detection:  ~$2-5/month (Lambda + CloudWatch)"
echo "  AWS Config:       ~$36/month (18 rules × $2/rule)"
echo "  S3 Storage:       ~$0.50-2/month"
echo "  Total:            ~$40-45/month"
echo ""

echo -e "${GREEN}Deployment script completed successfully!${NC}"
