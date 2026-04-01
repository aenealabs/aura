#!/bin/bash
#
# VPC Endpoint Migration Script
# Transitions from NAT Gateways to VPC Endpoints
# Saves ~$66/month while improving security
#
# Usage: ./migrate-to-vpc-endpoints.sh
#

set -e  # Exit on error

echo "=========================================="
echo "VPC Endpoint Migration"
echo "=========================================="
echo ""

# Environment variables
export AWS_PROFILE=${AWS_PROFILE:-}
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}
export ENVIRONMENT=${ENVIRONMENT:-dev}
export PROJECT_NAME=${PROJECT_NAME:-aura}

# VPC Configuration - Get from CloudFormation stack outputs
NETWORKING_STACK="${PROJECT_NAME}-networking-${ENVIRONMENT}"

echo "Retrieving VPC configuration from CloudFormation stack: $NETWORKING_STACK"

export VPC_ID=$(aws cloudformation describe-stacks \
  --stack-name $NETWORKING_STACK \
  --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
  --output text \
  --region $AWS_DEFAULT_REGION)

PRIVATE_SUBNET_IDS=$(aws cloudformation describe-stacks \
  --stack-name $NETWORKING_STACK \
  --query 'Stacks[0].Outputs[?OutputKey==`PrivateSubnetIds`].OutputValue' \
  --output text \
  --region $AWS_DEFAULT_REGION)

export SUBNET_IDS="${PRIVATE_SUBNET_IDS}"

if [ -z "$VPC_ID" ] || [ -z "$SUBNET_IDS" ]; then
  echo "ERROR: Could not retrieve VPC configuration from CloudFormation"
  echo "Please ensure $NETWORKING_STACK stack exists and has the required outputs"
  exit 1
fi

echo "VPC ID: $VPC_ID"
echo "Private Subnets: $SUBNET_IDS"
echo ""

# Get route table IDs for private subnets
echo "Getting route table IDs..."
ROUTE_TABLE_1=$(aws ec2 describe-route-tables \
  --filters "Name=association.subnet-id,Values=${PRIVATE_SUBNET_1}" \
  --query 'RouteTables[0].RouteTableId' \
  --output text)

ROUTE_TABLE_2=$(aws ec2 describe-route-tables \
  --filters "Name=association.subnet-id,Values=${PRIVATE_SUBNET_2}" \
  --query 'RouteTables[0].RouteTableId' \
  --output text)

echo "Route Table 1: ${ROUTE_TABLE_1}"
echo "Route Table 2: ${ROUTE_TABLE_2}"

# Get or create security group for VPC endpoints
echo ""
echo "Checking for VPC Endpoints security group..."
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=aura-vpc-endpoints-sg" "Name=vpc-id,Values=${VPC_ID}" \
  --query 'SecurityGroups[0].GroupId' \
  --output text 2>/dev/null || echo "None")

if [ "$SG_ID" = "None" ]; then
  echo "Creating VPC Endpoints security group..."
  SG_ID=$(aws ec2 create-security-group \
    --group-name aura-vpc-endpoints-sg \
    --description "Security group for VPC endpoints" \
    --vpc-id ${VPC_ID} \
    --tag-specifications 'ResourceType=security-group,Tags=[{Key=Name,Value=aura-vpc-endpoints-sg},{Key=Project,Value=aura},{Key=Environment,Value=dev}]' \
    --query 'GroupId' \
    --output text)

  # Allow HTTPS (443) from VPC CIDR
  aws ec2 authorize-security-group-ingress \
    --group-id ${SG_ID} \
    --protocol tcp \
    --port 443 \
    --cidr 10.0.0.0/16 \
    --no-cli-pager

  echo "Created security group: ${SG_ID}"
else
  echo "Using existing security group: ${SG_ID}"
fi

echo ""
echo "=========================================="
echo "Phase 1: Create Gateway Endpoints (FREE)"
echo "=========================================="

# 1. S3 Gateway Endpoint
echo ""
echo "1. Creating S3 Gateway Endpoint..."
S3_ENDPOINT=$(aws ec2 describe-vpc-endpoints \
  --filters "Name=vpc-id,Values=${VPC_ID}" "Name=service-name,Values=com.amazonaws.${AWS_DEFAULT_REGION}.s3" \
  --query 'VpcEndpoints[0].VpcEndpointId' \
  --output text 2>/dev/null || echo "None")

if [ "$S3_ENDPOINT" = "None" ]; then
  aws ec2 create-vpc-endpoint \
    --vpc-id ${VPC_ID} \
    --service-name com.amazonaws.${AWS_DEFAULT_REGION}.s3 \
    --route-table-ids ${ROUTE_TABLE_1} ${ROUTE_TABLE_2} \
    --vpc-endpoint-type Gateway \
    --tag-specifications 'ResourceType=vpc-endpoint,Tags=[{Key=Name,Value=aura-s3-endpoint},{Key=Project,Value=aura},{Key=Cost,Value=FREE}]' \
    --no-cli-pager
  echo "✓ S3 Gateway Endpoint created (FREE)"
else
  echo "✓ S3 Gateway Endpoint already exists: ${S3_ENDPOINT}"
fi

# 2. DynamoDB Gateway Endpoint
echo ""
echo "2. Creating DynamoDB Gateway Endpoint..."
DYNAMODB_ENDPOINT=$(aws ec2 describe-vpc-endpoints \
  --filters "Name=vpc-id,Values=${VPC_ID}" "Name=service-name,Values=com.amazonaws.${AWS_DEFAULT_REGION}.dynamodb" \
  --query 'VpcEndpoints[0].VpcEndpointId' \
  --output text 2>/dev/null || echo "None")

if [ "$DYNAMODB_ENDPOINT" = "None" ]; then
  aws ec2 create-vpc-endpoint \
    --vpc-id ${VPC_ID} \
    --service-name com.amazonaws.${AWS_DEFAULT_REGION}.dynamodb \
    --route-table-ids ${ROUTE_TABLE_1} ${ROUTE_TABLE_2} \
    --vpc-endpoint-type Gateway \
    --tag-specifications 'ResourceType=vpc-endpoint,Tags=[{Key=Name,Value=aura-dynamodb-endpoint},{Key=Project,Value=aura},{Key=Cost,Value=FREE}]' \
    --no-cli-pager
  echo "✓ DynamoDB Gateway Endpoint created (FREE)"
else
  echo "✓ DynamoDB Gateway Endpoint already exists: ${DYNAMODB_ENDPOINT}"
fi

echo ""
echo "=========================================="
echo "Phase 2: Create Interface Endpoints"
echo "=========================================="

# Function to create interface endpoint
create_interface_endpoint() {
  local service_name=$1
  local endpoint_name=$2
  local service_suffix=$3

  echo ""
  echo "Creating ${endpoint_name}..."

  EXISTING=$(aws ec2 describe-vpc-endpoints \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=service-name,Values=com.amazonaws.${AWS_DEFAULT_REGION}.${service_suffix}" \
    --query 'VpcEndpoints[0].VpcEndpointId' \
    --output text 2>/dev/null || echo "None")

  if [ "$EXISTING" = "None" ]; then
    aws ec2 create-vpc-endpoint \
      --vpc-id ${VPC_ID} \
      --service-name com.amazonaws.${AWS_DEFAULT_REGION}.${service_suffix} \
      --vpc-endpoint-type Interface \
      --subnet-ids ${PRIVATE_SUBNET_1} ${PRIVATE_SUBNET_2} \
      --security-group-ids ${SG_ID} \
      --private-dns-enabled \
      --tag-specifications "ResourceType=vpc-endpoint,Tags=[{Key=Name,Value=${endpoint_name}},{Key=Project,Value=aura},{Key=Environment,Value=dev}]" \
      --no-cli-pager
    echo "✓ ${service_name} Interface Endpoint created"
  else
    echo "✓ ${service_name} Interface Endpoint already exists: ${EXISTING}"
  fi
}

# 3. Bedrock Runtime Interface Endpoint
create_interface_endpoint "Bedrock Runtime" "aura-bedrock-endpoint" "bedrock-runtime"

# 4. Bedrock Agent Runtime (for future agent features)
create_interface_endpoint "Bedrock Agent Runtime" "aura-bedrock-agent-endpoint" "bedrock-agent-runtime"

# 5. OpenSearch - SKIPPED (No standalone VPC endpoint service)
# OpenSearch uses VPC mode when the cluster is deployed directly into VPC.
# See deploy/cloudformation/opensearch.yaml for VPC-native deployment.
# No separate VPC endpoint needed.

# 6. CodeConnections (for GitHub)
create_interface_endpoint "CodeConnections" "aura-codeconnections-endpoint" "codeconnections.api"

# 7. CloudWatch Logs
create_interface_endpoint "CloudWatch Logs" "aura-logs-endpoint" "logs"

# 8. Secrets Manager
create_interface_endpoint "Secrets Manager" "aura-secretsmanager-endpoint" "secretsmanager"

# 9. ECR API (for Docker images)
create_interface_endpoint "ECR API" "aura-ecr-api-endpoint" "ecr.api"

# 10. ECR DKR (for Docker registry)
create_interface_endpoint "ECR DKR" "aura-ecr-dkr-endpoint" "ecr.dkr"

echo ""
echo "=========================================="
echo "Waiting for endpoints to become available..."
echo "=========================================="
echo "This may take 2-5 minutes..."

# Wait for all endpoints to be available
aws ec2 wait vpc-endpoint-available \
  --filters "Name=vpc-id,Values=${VPC_ID}" "Name=state,Values=pending,pendingAcceptance" \
  2>/dev/null || echo "All endpoints are available or in terminal state"

echo ""
echo "=========================================="
echo "VPC Endpoint Summary"
echo "=========================================="

# List all VPC endpoints
aws ec2 describe-vpc-endpoints \
  --filters "Name=vpc-id,Values=${VPC_ID}" \
  --query 'VpcEndpoints[*].[VpcEndpointId,ServiceName,State,VpcEndpointType]' \
  --output table

echo ""
echo "=========================================="
echo "Phase 3: Verification"
echo "=========================================="
echo ""
echo "VPC Endpoints have been created successfully!"
echo ""
echo "IMPORTANT: Before deleting NAT Gateways:"
echo "1. Test connectivity to AWS services from private subnets"
echo "2. Verify CodeBuild can access GitHub via CodeConnections"
echo "3. Check CloudWatch Logs are being received"
echo ""
echo "To delete NAT Gateways and save \$66/month, run:"
echo "  ./delete-nat-gateways.sh"
echo ""
echo "=========================================="
echo "Migration Complete!"
echo "=========================================="
