#!/bin/bash
set -e

# Observability Layer Deployment Script
# Phase 2 Ready: Can be used directly by a dedicated CodeBuild project

echo "=========================================="
echo "Observability Layer Deployment"
echo "=========================================="

: ${ENVIRONMENT:="dev"}
: ${PROJECT_NAME:="aura"}
: ${AWS_DEFAULT_REGION:="us-east-1"}
: ${ALERT_EMAIL:=""}

if [ -z "$ALERT_EMAIL" ]; then
  ALERT_EMAIL=$(aws ssm get-parameter --name "/${PROJECT_NAME}/${ENVIRONMENT}/alert-email" --query 'Parameter.Value' --output text --region $AWS_DEFAULT_REGION 2>/dev/null || echo "noreply@example.com")
fi

# Get database endpoints (if they exist)
NEPTUNE_STACK="${PROJECT_NAME}-neptune-${ENVIRONMENT}"
OPENSEARCH_STACK="${PROJECT_NAME}-opensearch-${ENVIRONMENT}"

if aws cloudformation describe-stacks --stack-name $NEPTUNE_STACK --region $AWS_DEFAULT_REGION 2>/dev/null; then
  NEPTUNE_ENDPOINT=$(aws cloudformation describe-stacks --stack-name $NEPTUNE_STACK \
    --query 'Stacks[0].Outputs[?OutputKey==`ClusterEndpoint`].OutputValue' \
    --output text --region $AWS_DEFAULT_REGION)
else
  NEPTUNE_ENDPOINT="not-deployed-yet"
fi

if aws cloudformation describe-stacks --stack-name $OPENSEARCH_STACK --region $AWS_DEFAULT_REGION 2>/dev/null; then
  OPENSEARCH_ENDPOINT=$(aws cloudformation describe-stacks --stack-name $OPENSEARCH_STACK \
    --query 'Stacks[0].Outputs[?OutputKey==`DomainEndpoint`].OutputValue' \
    --output text --region $AWS_DEFAULT_REGION)
else
  OPENSEARCH_ENDPOINT="not-deployed-yet"
fi

echo "Neptune Endpoint: $NEPTUNE_ENDPOINT"
echo "OpenSearch Endpoint: $OPENSEARCH_ENDPOINT"

# Deploy Secrets
echo "Deploying Secrets Stack..."
SECRETS_STACK="${PROJECT_NAME}-secrets-${ENVIRONMENT}"

if aws cloudformation describe-stacks --stack-name $SECRETS_STACK --region $AWS_DEFAULT_REGION 2>/dev/null; then
  OPERATION="update-stack"
  WAIT_CONDITION="stack-update-complete"
else
  OPERATION="create-stack"
  WAIT_CONDITION="stack-create-complete"
fi

aws cloudformation $OPERATION \
  --stack-name $SECRETS_STACK \
  --template-body file://deploy/cloudformation/secrets.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
    ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
    ParameterKey=NeptuneEndpoint,ParameterValue=$NEPTUNE_ENDPOINT \
    ParameterKey=OpenSearchEndpoint,ParameterValue=$OPENSEARCH_ENDPOINT \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Key=Project,Value=$PROJECT_NAME Key=Environment,Value=$ENVIRONMENT Key=Layer,Value=observability \
  --region $AWS_DEFAULT_REGION \
  --no-cli-pager || true

aws cloudformation wait $WAIT_CONDITION --stack-name $SECRETS_STACK --region $AWS_DEFAULT_REGION

# Deploy Monitoring
echo "Deploying Monitoring Stack..."
MONITORING_STACK="${PROJECT_NAME}-monitoring-${ENVIRONMENT}"

if aws cloudformation describe-stacks --stack-name $MONITORING_STACK --region $AWS_DEFAULT_REGION 2>/dev/null; then
  OPERATION="update-stack"
  WAIT_CONDITION="stack-update-complete"
else
  OPERATION="create-stack"
  WAIT_CONDITION="stack-create-complete"
fi

aws cloudformation $OPERATION \
  --stack-name $MONITORING_STACK \
  --template-body file://deploy/cloudformation/monitoring.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
    ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
    ParameterKey=AlertEmail,ParameterValue=$ALERT_EMAIL \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Key=Project,Value=$PROJECT_NAME Key=Environment,Value=$ENVIRONMENT Key=Layer,Value=observability \
  --region $AWS_DEFAULT_REGION \
  --no-cli-pager || true

aws cloudformation wait $WAIT_CONDITION --stack-name $MONITORING_STACK --region $AWS_DEFAULT_REGION

# Deploy Cost Alerts
echo "Deploying Cost Alerts Stack..."
COST_ALERTS_STACK="${PROJECT_NAME}-cost-alerts-${ENVIRONMENT}"

if aws cloudformation describe-stacks --stack-name $COST_ALERTS_STACK --region $AWS_DEFAULT_REGION 2>/dev/null; then
  OPERATION="update-stack"
  WAIT_CONDITION="stack-update-complete"
else
  OPERATION="create-stack"
  WAIT_CONDITION="stack-create-complete"
fi

aws cloudformation $OPERATION \
  --stack-name $COST_ALERTS_STACK \
  --template-body file://deploy/cloudformation/aura-cost-alerts.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
    ParameterKey=AlertEmail,ParameterValue=$ALERT_EMAIL \
    ParameterKey=DailyBudget,ParameterValue=15 \
    ParameterKey=MonthlyBudget,ParameterValue=400 \
    ParameterKey=EnableBudgetEnforcement,ParameterValue=false \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Key=Project,Value=$PROJECT_NAME Key=Environment,Value=$ENVIRONMENT Key=Layer,Value=observability \
  --region $AWS_DEFAULT_REGION \
  --no-cli-pager || true

aws cloudformation wait $WAIT_CONDITION --stack-name $COST_ALERTS_STACK --region $AWS_DEFAULT_REGION

echo "Observability layer deployment completed!"
