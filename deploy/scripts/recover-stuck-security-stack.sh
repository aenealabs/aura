#!/bin/bash
# ==============================================================================
# Security Stack Recovery Script
# ==============================================================================
# Purpose: Diagnose and recover from stuck CloudFormation security stack states
#
# Common issues this script addresses:
# - DELETE_IN_PROGRESS stuck due to ENI dependencies
# - DELETE_FAILED due to resources in use
# - UPDATE_ROLLBACK_COMPLETE requiring redeployment
#
# Usage: ./recover-stuck-security-stack.sh [environment]
# Example: ./recover-stuck-security-stack.sh dev
# ==============================================================================

set -e

# Configuration
ENVIRONMENT="${1:-dev}"
PROJECT_NAME="aura"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
STACK_NAME="${PROJECT_NAME}-security-${ENVIRONMENT}"

echo "=============================================="
echo "Security Stack Recovery Tool"
echo "=============================================="
echo "Stack: $STACK_NAME"
echo "Region: $REGION"
echo ""

# Check current stack status
echo "Checking current stack status..."
STACK_STATUS=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].StackStatus' \
  --output text \
  --region $REGION 2>/dev/null || echo "DOES_NOT_EXIST")

echo "Current status: $STACK_STATUS"
echo ""

case $STACK_STATUS in
  "CREATE_COMPLETE"|"UPDATE_COMPLETE")
    echo "Stack is healthy. No recovery needed."
    echo ""
    echo "To update the stack, run:"
    echo "  aws codebuild start-build --project-name aura-foundation-deploy-dev"
    exit 0
    ;;

  "UPDATE_ROLLBACK_COMPLETE")
    echo "Stack is in UPDATE_ROLLBACK_COMPLETE state."
    echo "This means a previous update failed, but the stack is in a deployable state."
    echo ""
    echo "To redeploy, run:"
    echo "  aws codebuild start-build --project-name aura-foundation-deploy-dev"
    exit 0
    ;;

  "DELETE_IN_PROGRESS")
    echo "WARNING: Stack is in DELETE_IN_PROGRESS state."
    echo ""
    echo "This typically means security groups have active ENI dependencies."
    echo "Checking for blocking resources..."
    echo ""

    # List resources that are blocking deletion
    echo "Stack resources and their status:"
    aws cloudformation describe-stack-resources \
      --stack-name $STACK_NAME \
      --query 'StackResources[*].[LogicalResourceId,ResourceStatus,ResourceType]' \
      --output table \
      --region $REGION 2>/dev/null || echo "Cannot retrieve stack resources"

    echo ""
    echo "Checking for ENIs attached to security groups..."

    # Get security group IDs from the stack (if still available)
    SG_NAMES="${PROJECT_NAME}-eks-sg-${ENVIRONMENT},${PROJECT_NAME}-neptune-sg-${ENVIRONMENT},${PROJECT_NAME}-opensearch-sg-${ENVIRONMENT},${PROJECT_NAME}-vpce-sg-${ENVIRONMENT}"

    aws ec2 describe-network-interfaces \
      --filters "Name=group-name,Values=$SG_NAMES" \
      --query 'NetworkInterfaces[*].[NetworkInterfaceId,Status,Description,Groups[0].GroupName]' \
      --output table \
      --region $REGION 2>/dev/null || echo "Cannot retrieve ENI information"

    echo ""
    echo "=============================================="
    echo "RESOLUTION OPTIONS"
    echo "=============================================="
    echo ""
    echo "Option 1: WAIT (Recommended for dev)"
    echo "  The stack may eventually delete if services are stopping."
    echo "  Check status in 10-15 minutes:"
    echo "    aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].StackStatus' --region $REGION"
    echo ""
    echo "Option 2: CANCEL DELETE (If you want to keep the stack)"
    echo "  CloudFormation delete cannot be cancelled directly."
    echo "  You must wait for it to fail (DELETE_FAILED) or complete."
    echo ""
    echo "Option 3: FORCE DELETE RESOURCES (Use with caution)"
    echo "  If the delete is truly stuck, you may need to:"
    echo "  1. Delete dependent stacks first (EKS, Neptune, OpenSearch)"
    echo "  2. Or manually remove security group rules that reference each other"
    echo ""
    echo "  WARNING: This will cause service disruption!"
    echo ""
    exit 1
    ;;

  "DELETE_FAILED")
    echo "ERROR: Stack is in DELETE_FAILED state."
    echo ""
    echo "Checking which resources failed to delete..."
    aws cloudformation describe-stack-resources \
      --stack-name $STACK_NAME \
      --query 'StackResources[?ResourceStatus==`DELETE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
      --output table \
      --region $REGION 2>/dev/null || echo "Cannot retrieve failed resources"

    echo ""
    echo "To retry deletion after resolving dependencies:"
    echo "  aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION"
    echo ""
    echo "To skip deletion and redeploy (dangerous - may leave orphaned resources):"
    echo "  aws cloudformation delete-stack --stack-name $STACK_NAME --retain-resources <resource-id> --region $REGION"
    exit 1
    ;;

  "ROLLBACK_COMPLETE"|"ROLLBACK_FAILED")
    echo "Stack is in $STACK_STATUS state from initial creation failure."
    echo "This stack can be safely deleted and recreated."
    echo ""
    echo "To delete and redeploy:"
    echo "  aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION"
    echo "  aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION"
    echo "  aws codebuild start-build --project-name aura-foundation-deploy-dev"
    exit 0
    ;;

  "DOES_NOT_EXIST")
    echo "Stack does not exist. Ready for initial deployment."
    echo ""
    echo "To deploy:"
    echo "  aws codebuild start-build --project-name aura-foundation-deploy-dev"
    exit 0
    ;;

  *)
    echo "Stack is in $STACK_STATUS state."
    echo ""

    if [[ $STACK_STATUS == *"IN_PROGRESS"* ]]; then
      echo "An operation is in progress. Wait for it to complete:"
      echo "  aws cloudformation wait stack-$( echo $STACK_STATUS | tr '[:upper:]' '[:lower:]' | sed 's/_in_progress/-complete/' ) --stack-name $STACK_NAME --region $REGION"
    else
      echo "Check the CloudFormation console for details:"
      echo "  https://${REGION}.console.aws.amazon.com/cloudformation/home?region=${REGION}#/stacks/stackinfo?stackId=${STACK_NAME}"
    fi
    exit 1
    ;;
esac
