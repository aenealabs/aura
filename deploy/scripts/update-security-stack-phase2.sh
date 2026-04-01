#!/bin/bash
# =============================================================================
# CloudFormation Security Stack Update - Phase 2
# =============================================================================
# This script updates the security stack after import to add:
# - ALB Security Group (new)
# - ECS Workload Security Group (new)
# - Lambda Security Group (new)
# - All SecurityGroupIngress rules
# - All SecurityGroupEgress rules
# - WAF Web ACL and logging configuration
#
# Prerequisites:
# 1. Phase 1 (import-security-groups.sh) completed successfully
# 2. Stack is in IMPORT_COMPLETE or UPDATE_COMPLETE state
#
# Usage: ./update-security-stack-phase2.sh
# =============================================================================

set -e

# Configuration
REGION="us-east-1"
STACK_NAME="aura-security-dev"
ENVIRONMENT="dev"
PROJECT_NAME="aura"
TEMPLATE_FILE="/path/to/project-aura/deploy/cloudformation/security.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "Security Stack Update - Phase 2"
echo "=============================================="
echo ""

# Step 1: Get VPC ID
echo -e "${YELLOW}Step 1: Getting VPC ID...${NC}"
VPC_ID=$(aws ec2 describe-vpcs --region ${REGION} \
    --filters "Name=tag:Name,Values=*aura*" \
    --query 'Vpcs[0].VpcId' --output text)

if [ -z "$VPC_ID" ] || [ "$VPC_ID" == "None" ]; then
    echo -e "${RED}ERROR: Could not find VPC with tag containing 'aura'${NC}"
    exit 1
fi
echo -e "${GREEN}Found VPC: ${VPC_ID}${NC}"

# Step 2: Verify stack is in correct state
echo ""
echo -e "${YELLOW}Step 2: Verifying stack state...${NC}"
STACK_STATUS=$(aws cloudformation describe-stacks --region ${REGION} \
    --stack-name ${STACK_NAME} \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [ "$STACK_STATUS" != "IMPORT_COMPLETE" ] && [ "$STACK_STATUS" != "UPDATE_COMPLETE" ] && [ "$STACK_STATUS" != "CREATE_COMPLETE" ]; then
    echo -e "${RED}ERROR: Stack is in state ${STACK_STATUS}${NC}"
    echo "Expected: IMPORT_COMPLETE, UPDATE_COMPLETE, or CREATE_COMPLETE"
    echo "Please run import-security-groups.sh first."
    exit 1
fi
echo -e "${GREEN}Stack is in ${STACK_STATUS} state - ready for update${NC}"

# Step 3: Remove DeletionPolicy from template for the update
# Note: The full template doesn't have DeletionPolicy: Retain, which is correct.
# We use the full security.yaml directly.

echo ""
echo -e "${YELLOW}Step 3: Validating template...${NC}"
aws cloudformation validate-template \
    --region ${REGION} \
    --template-body file://${TEMPLATE_FILE} > /dev/null

echo -e "${GREEN}Template validation passed${NC}"

# Step 4: Preview changes
echo ""
echo -e "${YELLOW}Step 4: Creating change set to preview changes...${NC}"

CHANGE_SET_NAME="phase2-update-$(date +%Y%m%d-%H%M%S)"

aws cloudformation create-change-set \
    --region ${REGION} \
    --stack-name ${STACK_NAME} \
    --change-set-name ${CHANGE_SET_NAME} \
    --template-body file://${TEMPLATE_FILE} \
    --parameters \
        ParameterKey=Environment,ParameterValue=${ENVIRONMENT} \
        ParameterKey=ProjectName,ParameterValue=${PROJECT_NAME} \
        ParameterKey=VpcId,ParameterValue=${VPC_ID}

echo "Waiting for change set creation..."
sleep 5

# Wait for change set (with timeout)
for i in {1..30}; do
    STATUS=$(aws cloudformation describe-change-set \
        --region ${REGION} \
        --stack-name ${STACK_NAME} \
        --change-set-name ${CHANGE_SET_NAME} \
        --query 'Status' --output text 2>/dev/null || echo "PENDING")

    if [ "$STATUS" == "CREATE_COMPLETE" ]; then
        break
    elif [ "$STATUS" == "FAILED" ]; then
        REASON=$(aws cloudformation describe-change-set \
            --region ${REGION} \
            --stack-name ${STACK_NAME} \
            --change-set-name ${CHANGE_SET_NAME} \
            --query 'StatusReason' --output text)
        echo -e "${RED}Change set creation failed: ${REASON}${NC}"

        # Check if it's just "no changes"
        if [[ "$REASON" == *"didn't contain changes"* ]] || [[ "$REASON" == *"No updates"* ]]; then
            echo -e "${YELLOW}No changes needed - stack is already up to date!${NC}"
            aws cloudformation delete-change-set \
                --region ${REGION} \
                --stack-name ${STACK_NAME} \
                --change-set-name ${CHANGE_SET_NAME}
            exit 0
        fi
        exit 1
    fi
    echo "  Waiting... (${i}/30)"
    sleep 2
done

echo -e "${GREEN}Change set created${NC}"

# Step 5: Show what will be added/modified
echo ""
echo -e "${YELLOW}Step 5: Changes to be applied:${NC}"
aws cloudformation describe-change-set \
    --region ${REGION} \
    --stack-name ${STACK_NAME} \
    --change-set-name ${CHANGE_SET_NAME} \
    --query 'Changes[*].[ResourceChange.Action, ResourceChange.LogicalResourceId, ResourceChange.ResourceType]' \
    --output table

CHANGE_COUNT=$(aws cloudformation describe-change-set \
    --region ${REGION} \
    --stack-name ${STACK_NAME} \
    --change-set-name ${CHANGE_SET_NAME} \
    --query 'length(Changes)' --output text)

echo ""
echo -e "${YELLOW}Total resources to add/modify: ${CHANGE_COUNT}${NC}"

# Step 6: Execute with confirmation
echo ""
read -p "Execute this update? Type 'yes' to proceed: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${RED}Update cancelled. Change set deleted.${NC}"
    aws cloudformation delete-change-set \
        --region ${REGION} \
        --stack-name ${STACK_NAME} \
        --change-set-name ${CHANGE_SET_NAME}
    exit 0
fi

echo ""
echo -e "${YELLOW}Step 6: Executing update...${NC}"
aws cloudformation execute-change-set \
    --region ${REGION} \
    --stack-name ${STACK_NAME} \
    --change-set-name ${CHANGE_SET_NAME}

echo "Waiting for update to complete (this may take several minutes for WAF)..."
aws cloudformation wait stack-update-complete \
    --region ${REGION} \
    --stack-name ${STACK_NAME}

echo -e "${GREEN}Update complete!${NC}"

# Step 7: Show final state
echo ""
echo -e "${YELLOW}Step 7: Final stack resources:${NC}"
aws cloudformation describe-stack-resources \
    --region ${REGION} \
    --stack-name ${STACK_NAME} \
    --query 'StackResources[?ResourceStatus==`CREATE_COMPLETE` || ResourceStatus==`UPDATE_COMPLETE` || ResourceStatus==`IMPORT_COMPLETE`].[LogicalResourceId, ResourceType, ResourceStatus]' \
    --output table

# Step 8: Show all outputs
echo ""
echo -e "${YELLOW}Step 8: Stack outputs (use these for dependent stacks):${NC}"
aws cloudformation describe-stacks \
    --region ${REGION} \
    --stack-name ${STACK_NAME} \
    --query 'Stacks[0].Outputs[*].[OutputKey, OutputValue]' \
    --output table

echo ""
echo "=============================================="
echo -e "${GREEN}PHASE 2 COMPLETE: Full security stack deployed!${NC}"
echo "=============================================="
echo ""
echo "NEXT STEPS:"
echo "1. Deploy VPC endpoints stack:"
echo "   aws cloudformation deploy \\"
echo "     --stack-name aura-vpce-dev \\"
echo "     --template-file deploy/cloudformation/vpc-endpoints.yaml \\"
echo "     --parameter-overrides \\"
echo "       VpcId=${VPC_ID} \\"
echo "       SecurityGroupId=<VPCEndpointSecurityGroupId from above> \\"
echo "       ..."
echo ""
