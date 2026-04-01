#!/bin/bash
# verify-ecs-vpc-connectivity.sh
# Verifies ECS Fargate tasks can reach VPC endpoints for ECR image pulls
#
# Usage: ./verify-ecs-vpc-connectivity.sh [environment]
# Example: ./verify-ecs-vpc-connectivity.sh dev

set -euo pipefail

ENVIRONMENT="${1:-dev}"
PROJECT_NAME="aura"
REGION="${AWS_REGION:-us-east-1}"

echo "=========================================="
echo "ECS VPC Endpoint Connectivity Verification"
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${REGION}"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

check_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 1. Check VPC Endpoints exist and are available
echo ""
echo "1. Checking VPC Endpoints..."

REQUIRED_ENDPOINTS=(
    "com.amazonaws.${REGION}.ecr.api"
    "com.amazonaws.${REGION}.ecr.dkr"
    "com.amazonaws.${REGION}.s3"
    "com.amazonaws.${REGION}.logs"
)

VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=tag:Name,Values=${PROJECT_NAME}-vpc-${ENVIRONMENT}" \
    --query 'Vpcs[0].VpcId' \
    --output text \
    --region "${REGION}" 2>/dev/null || echo "")

if [ -z "$VPC_ID" ] || [ "$VPC_ID" == "None" ]; then
    check_fail "VPC not found: ${PROJECT_NAME}-vpc-${ENVIRONMENT}"
    exit 1
fi

check_pass "VPC found: ${VPC_ID}"

for endpoint in "${REQUIRED_ENDPOINTS[@]}"; do
    endpoint_state=$(aws ec2 describe-vpc-endpoints \
        --filters "Name=vpc-id,Values=${VPC_ID}" "Name=service-name,Values=${endpoint}" \
        --query 'VpcEndpoints[0].State' \
        --output text \
        --region "${REGION}" 2>/dev/null || echo "not-found")

    if [ "$endpoint_state" == "available" ]; then
        check_pass "VPC Endpoint: ${endpoint} (${endpoint_state})"
    elif [ "$endpoint_state" == "not-found" ] || [ "$endpoint_state" == "None" ]; then
        check_fail "VPC Endpoint missing: ${endpoint}"
    else
        check_warn "VPC Endpoint: ${endpoint} (${endpoint_state})"
    fi
done

# 2. Check Private Subnets
echo ""
echo "2. Checking Private Subnets..."

PRIVATE_SUBNETS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=tag:Name,Values=*private*" \
    --query 'Subnets[*].[SubnetId,CidrBlock,AvailabilityZone]' \
    --output text \
    --region "${REGION}" 2>/dev/null)

if [ -z "$PRIVATE_SUBNETS" ]; then
    check_fail "No private subnets found in VPC ${VPC_ID}"
else
    echo "$PRIVATE_SUBNETS" | while read -r subnet_id cidr az; do
        check_pass "Private subnet: ${subnet_id} (${cidr}, ${az})"
    done
fi

# 3. Check VPC Endpoint Security Group
echo ""
echo "3. Checking VPC Endpoint Security Group..."

VPCE_SG=$(aws ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=group-name,Values=${PROJECT_NAME}-vpce-sg-${ENVIRONMENT}" \
    --query 'SecurityGroups[0].GroupId' \
    --output text \
    --region "${REGION}" 2>/dev/null || echo "")

if [ -z "$VPCE_SG" ] || [ "$VPCE_SG" == "None" ]; then
    check_fail "VPC Endpoint security group not found: ${PROJECT_NAME}-vpce-sg-${ENVIRONMENT}"
else
    check_pass "VPC Endpoint security group: ${VPCE_SG}"

    # Check ingress rules for private subnet CIDRs
    INGRESS_RULES=$(aws ec2 describe-security-groups \
        --group-ids "${VPCE_SG}" \
        --query 'SecurityGroups[0].IpPermissions[?FromPort==`443`].IpRanges[*].CidrIp' \
        --output text \
        --region "${REGION}" 2>/dev/null)

    if echo "$INGRESS_RULES" | grep -q "10.0"; then
        check_pass "Security group allows HTTPS from private subnets"
    else
        check_warn "Security group may not allow HTTPS from all private subnets"
    fi
fi

# 4. Check ECS Task Security Group (from incident-investigation-workflow)
echo ""
echo "4. Checking ECS Task Security Group..."

ECS_TASK_SG=$(aws ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=group-name,Values=${PROJECT_NAME}-incident-task-sg-${ENVIRONMENT}" \
    --query 'SecurityGroups[0].GroupId' \
    --output text \
    --region "${REGION}" 2>/dev/null || echo "")

if [ -z "$ECS_TASK_SG" ] || [ "$ECS_TASK_SG" == "None" ]; then
    check_warn "ECS Task security group not found (deploy incident-investigation-workflow stack first)"
else
    check_pass "ECS Task security group: ${ECS_TASK_SG}"

    # Check egress rules
    EGRESS_443=$(aws ec2 describe-security-groups \
        --group-ids "${ECS_TASK_SG}" \
        --query 'SecurityGroups[0].IpPermissionsEgress[?FromPort==`443`]' \
        --output text \
        --region "${REGION}" 2>/dev/null)

    if [ -n "$EGRESS_443" ]; then
        check_pass "Security group allows HTTPS egress (for VPC endpoints)"
    else
        check_fail "Security group missing HTTPS egress rule"
    fi
fi

# 5. Check ECS Cluster
echo ""
echo "5. Checking ECS Cluster..."

ECS_CLUSTER_ARN=$(aws ecs describe-clusters \
    --clusters "${PROJECT_NAME}-network-services-${ENVIRONMENT}" \
    --query 'clusters[0].clusterArn' \
    --output text \
    --region "${REGION}" 2>/dev/null || echo "")

if [ -z "$ECS_CLUSTER_ARN" ] || [ "$ECS_CLUSTER_ARN" == "None" ]; then
    check_fail "ECS cluster not found: ${PROJECT_NAME}-network-services-${ENVIRONMENT}"
else
    check_pass "ECS cluster found: ${ECS_CLUSTER_ARN}"
fi

# 6. Check Step Functions State Machine
echo ""
echo "6. Checking Step Functions State Machine..."

SFN_ARN=$(aws stepfunctions list-state-machines \
    --query "stateMachines[?name=='${PROJECT_NAME}-incident-investigation-${ENVIRONMENT}'].stateMachineArn" \
    --output text \
    --region "${REGION}" 2>/dev/null || echo "")

if [ -z "$SFN_ARN" ]; then
    check_warn "State machine not found (deploy incident-investigation-workflow stack first)"
else
    check_pass "State machine found: ${SFN_ARN}"
fi

# Summary
echo ""
echo "=========================================="
echo "Verification Complete"
echo "=========================================="
echo ""
echo "If all checks passed, you can test the workflow with:"
echo ""
echo "aws stepfunctions start-execution \\"
echo "  --state-machine-arn \$(aws stepfunctions list-state-machines \\"
echo "    --query \"stateMachines[?name=='${PROJECT_NAME}-incident-investigation-${ENVIRONMENT}'].stateMachineArn\" \\"
echo "    --output text) \\"
echo "  --input '{\"id\": \"test-incident-001\", \"source\": \"manual-test\", \"detail\": {\"message\": \"Test investigation\"}}'"
echo ""
