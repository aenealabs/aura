#!/bin/bash
set -e

# Application Layer Deployment Script
# Phase 2 Ready: Can be used directly by a dedicated CodeBuild project

echo "=========================================="
echo "Application Layer Deployment"
echo "=========================================="

: ${ENVIRONMENT:="dev"}
: ${PROJECT_NAME:="aura"}
: ${AWS_DEFAULT_REGION:="us-east-1"}
: ${ALERT_EMAIL:=""}

if [ -z "$ALERT_EMAIL" ]; then
  ALERT_EMAIL=$(aws ssm get-parameter --name "/${PROJECT_NAME}/${ENVIRONMENT}/alert-email" --query 'Parameter.Value' --output text --region $AWS_DEFAULT_REGION 2>/dev/null || echo "noreply@example.com")
fi

echo "Alert Email: $ALERT_EMAIL"

# Deploy Bedrock Infrastructure
echo "Deploying Bedrock Infrastructure Stack..."
BEDROCK_STACK="${PROJECT_NAME}-bedrock-infrastructure-${ENVIRONMENT}"

if aws cloudformation describe-stacks --stack-name $BEDROCK_STACK --region $AWS_DEFAULT_REGION 2>/dev/null; then
  OPERATION="update-stack"
  WAIT_CONDITION="stack-update-complete"
else
  OPERATION="create-stack"
  WAIT_CONDITION="stack-create-complete"
fi

aws cloudformation $OPERATION \
  --stack-name $BEDROCK_STACK \
  --template-body file://deploy/cloudformation/aura-bedrock-infrastructure.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
    ParameterKey=AlertEmail,ParameterValue=$ALERT_EMAIL \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Key=Project,Value=$PROJECT_NAME Key=Environment,Value=$ENVIRONMENT Key=Layer,Value=application \
  --region $AWS_DEFAULT_REGION \
  --no-cli-pager || true

aws cloudformation wait $WAIT_CONDITION --stack-name $BEDROCK_STACK --region $AWS_DEFAULT_REGION

echo "Application layer deployment completed!"
aws cloudformation describe-stacks --stack-name $BEDROCK_STACK --query 'Stacks[0].Outputs' --region $AWS_DEFAULT_REGION --output table
