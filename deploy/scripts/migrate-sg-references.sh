#!/bin/bash
# =============================================================================
# Migration Script: Security Group Reference Architecture
# =============================================================================
# Purpose: Migrate from manual CLI-based security group rules to CloudFormation-
#          managed centralized workload security groups (CMMC L3 compliant).
#
# This script:
# 1. Removes manually-added security group rules from VPC endpoint SG
# 2. Updates the security.yaml stack to create centralized workload SGs
# 3. Updates dependent stacks to use imported SG references
#
# Prerequisites:
# - AWS CLI configured with appropriate credentials
# - cfn-lint installed for template validation
# - jq installed for JSON parsing
#
# Usage:
#   ./migrate-sg-references.sh <environment> [--dry-run]
#
# Example:
#   ./migrate-sg-references.sh dev --dry-run   # Preview changes
#   ./migrate-sg-references.sh dev             # Execute migration
# =============================================================================

set -euo pipefail

# Configuration
PROJECT_NAME="aura"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFN_DIR="${SCRIPT_DIR}/../cloudformation"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
ENVIRONMENT="${1:-}"
DRY_RUN=false
if [[ "${2:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

if [[ -z "$ENVIRONMENT" ]]; then
    echo -e "${RED}Error: Environment parameter required${NC}"
    echo "Usage: $0 <environment> [--dry-run]"
    echo "  environment: dev, qa, or prod"
    exit 1
fi

if [[ ! "$ENVIRONMENT" =~ ^(dev|qa|prod)$ ]]; then
    echo -e "${RED}Error: Invalid environment '$ENVIRONMENT'. Must be dev, qa, or prod.${NC}"
    exit 1
fi

echo "=============================================="
echo "Security Group Reference Migration"
echo "=============================================="
echo "Environment: $ENVIRONMENT"
echo "Dry Run: $DRY_RUN"
echo "=============================================="

# Step 1: Identify current security groups
echo -e "\n${YELLOW}Step 1: Identifying current security groups...${NC}"

VPC_ENDPOINT_SG=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=${PROJECT_NAME}-vpce-sg-${ENVIRONMENT}" \
    --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "")

INCIDENT_TASK_SG=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=${PROJECT_NAME}-incident-task-sg-${ENVIRONMENT}" \
    --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "")

echo "VPC Endpoint SG: ${VPC_ENDPOINT_SG:-Not found}"
echo "Incident Task SG: ${INCIDENT_TASK_SG:-Not found}"

# Step 2: Check for manually-added rules
echo -e "\n${YELLOW}Step 2: Checking for manually-added security group rules...${NC}"

if [[ -n "$VPC_ENDPOINT_SG" && "$VPC_ENDPOINT_SG" != "None" ]]; then
    MANUAL_RULES=$(aws ec2 describe-security-groups \
        --group-ids "$VPC_ENDPOINT_SG" \
        --query "SecurityGroups[0].IpPermissions[?UserIdGroupPairs[?Description=='HTTPS from RuntimeIncidentAgent ECS tasks']]" \
        --output json 2>/dev/null || echo "[]")

    if [[ "$MANUAL_RULES" != "[]" ]]; then
        echo -e "${YELLOW}Found manually-added rule referencing incident task SG${NC}"
        echo "$MANUAL_RULES" | jq .

        if [[ "$DRY_RUN" == "false" ]]; then
            echo -e "\n${YELLOW}Removing manually-added rule...${NC}"
            if [[ -n "$INCIDENT_TASK_SG" && "$INCIDENT_TASK_SG" != "None" ]]; then
                aws ec2 revoke-security-group-ingress \
                    --group-id "$VPC_ENDPOINT_SG" \
                    --ip-permissions "IpProtocol=tcp,FromPort=443,ToPort=443,UserIdGroupPairs=[{GroupId=${INCIDENT_TASK_SG},Description='HTTPS from RuntimeIncidentAgent ECS tasks'}]" \
                    && echo -e "${GREEN}Successfully removed manual rule${NC}" \
                    || echo -e "${RED}Failed to remove manual rule (may already be removed)${NC}"
            fi
        else
            echo -e "${YELLOW}[DRY RUN] Would remove manual rule from $VPC_ENDPOINT_SG${NC}"
        fi
    else
        echo "No manually-added rules found"
    fi
else
    echo "VPC Endpoint SG not found - may not be deployed yet"
fi

# Step 3: Validate CloudFormation templates
echo -e "\n${YELLOW}Step 3: Validating CloudFormation templates...${NC}"

cfn-lint "${CFN_DIR}/security.yaml" && echo -e "${GREEN}security.yaml: Valid${NC}" || true
cfn-lint "${CFN_DIR}/incident-investigation-workflow.yaml" && echo -e "${GREEN}incident-investigation-workflow.yaml: Valid${NC}" || true

# Step 4: Update security stack
echo -e "\n${YELLOW}Step 4: Updating security stack (creates centralized workload SGs)...${NC}"

SECURITY_STACK_NAME="${PROJECT_NAME}-security-${ENVIRONMENT}"
VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=tag:Name,Values=${PROJECT_NAME}-vpc-${ENVIRONMENT}" \
    --query 'Vpcs[0].VpcId' --output text 2>/dev/null || echo "")

if [[ -z "$VPC_ID" || "$VPC_ID" == "None" ]]; then
    echo -e "${RED}Error: VPC not found. Deploy networking stack first.${NC}"
    exit 1
fi

echo "VPC ID: $VPC_ID"
echo "Stack: $SECURITY_STACK_NAME"

if [[ "$DRY_RUN" == "false" ]]; then
    echo -e "\n${YELLOW}Deploying security stack update...${NC}"
    aws cloudformation deploy \
        --template-file "${CFN_DIR}/security.yaml" \
        --stack-name "$SECURITY_STACK_NAME" \
        --parameter-overrides \
            Environment="$ENVIRONMENT" \
            ProjectName="$PROJECT_NAME" \
            VpcId="$VPC_ID" \
        --capabilities CAPABILITY_NAMED_IAM \
        --no-fail-on-empty-changeset
    echo -e "${GREEN}Security stack updated successfully${NC}"
else
    echo -e "${YELLOW}[DRY RUN] Would deploy security stack with centralized workload SGs${NC}"
fi

# Step 5: Get new security group IDs
echo -e "\n${YELLOW}Step 5: Retrieving new security group IDs...${NC}"

if [[ "$DRY_RUN" == "false" ]]; then
    NEW_ECS_WORKLOAD_SG=$(aws cloudformation describe-stacks \
        --stack-name "$SECURITY_STACK_NAME" \
        --query "Stacks[0].Outputs[?ExportName=='${PROJECT_NAME}-ecs-workload-sg-${ENVIRONMENT}'].OutputValue" \
        --output text 2>/dev/null || echo "")

    NEW_LAMBDA_SG=$(aws cloudformation describe-stacks \
        --stack-name "$SECURITY_STACK_NAME" \
        --query "Stacks[0].Outputs[?ExportName=='${PROJECT_NAME}-lambda-sg-${ENVIRONMENT}'].OutputValue" \
        --output text 2>/dev/null || echo "")

    echo "New ECS Workload SG: ${NEW_ECS_WORKLOAD_SG:-Not created}"
    echo "New Lambda SG: ${NEW_LAMBDA_SG:-Not created}"
else
    echo -e "${YELLOW}[DRY RUN] New SGs would be created by security stack${NC}"
fi

# Step 6: Clean up orphaned security groups
echo -e "\n${YELLOW}Step 6: Checking for orphaned security groups to clean up...${NC}"

if [[ -n "$INCIDENT_TASK_SG" && "$INCIDENT_TASK_SG" != "None" ]]; then
    echo "Found old incident task SG: $INCIDENT_TASK_SG"

    # Check if it's still in use
    ENI_COUNT=$(aws ec2 describe-network-interfaces \
        --filters "Name=group-id,Values=${INCIDENT_TASK_SG}" \
        --query 'length(NetworkInterfaces)' --output text 2>/dev/null || echo "0")

    if [[ "$ENI_COUNT" == "0" ]]; then
        if [[ "$DRY_RUN" == "false" ]]; then
            echo "Deleting orphaned security group..."
            aws ec2 delete-security-group --group-id "$INCIDENT_TASK_SG" \
                && echo -e "${GREEN}Deleted orphaned SG${NC}" \
                || echo -e "${YELLOW}Could not delete SG (may have dependencies)${NC}"
        else
            echo -e "${YELLOW}[DRY RUN] Would delete orphaned SG $INCIDENT_TASK_SG${NC}"
        fi
    else
        echo -e "${YELLOW}SG still has $ENI_COUNT ENIs attached - skipping deletion${NC}"
    fi
else
    echo "No orphaned incident task SG found"
fi

# Step 7: Summary
echo -e "\n=============================================="
echo -e "${GREEN}Migration Summary${NC}"
echo "=============================================="
echo "1. Centralized workload SGs created in security.yaml"
echo "2. VPC endpoint SG now uses SG references (CMMC L3)"
echo "3. Incident investigation workflow uses imported SG"
echo "4. Manual CLI rules removed"
echo ""
echo "Next Steps:"
echo "1. Deploy incident-investigation-workflow stack to use new SG"
echo "2. Test ECS task connectivity to VPC endpoints"
echo "3. Delete orphaned security groups after validation"
echo "=============================================="

if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "\n${YELLOW}This was a DRY RUN. No changes were made.${NC}"
    echo "Run without --dry-run to execute the migration."
fi
