#!/bin/bash
# =============================================================================
# Project Aura - CloudFormation Deployment Helper Functions
# =============================================================================
# Shared utility functions for CloudFormation stack deployment.
# Provides idempotent create/update logic with proper error handling.
#
# USAGE:
#   source deploy/scripts/cfn-deploy-helpers.sh
#   cfn_deploy_stack "my-stack" "template.yaml" "$PARAMS" "$TAGS"
#
# FUNCTIONS:
#   cfn_deploy_stack     - Deploy (create or update) a CloudFormation stack
#   cfn_stack_exists     - Check if a stack exists
#   cfn_get_stack_output - Get a stack output value
#   cfn_wait_for_stack   - Wait for stack to reach stable state
#   cfn_cleanup_failed   - Delete failed stacks (ROLLBACK_COMPLETE, etc.)
#
# PREREQUISITES:
#   - AWS CLI configured with appropriate credentials
#   - Required environment variables: AWS_DEFAULT_REGION (or AWS_REGION)
#
# =============================================================================

# Fail on error, undefined vars, and pipe failures (unless already set)
if [[ "${CFN_HELPERS_SOURCED:-}" != "true" ]]; then
    set -o pipefail
    CFN_HELPERS_SOURCED=true
fi

# =============================================================================
# Configuration
# =============================================================================
CFN_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION:-us-east-1}}"

# Colors for output
readonly CFN_RED='\033[0;31m'
readonly CFN_GREEN='\033[0;32m'
readonly CFN_YELLOW='\033[1;33m'
readonly CFN_BLUE='\033[0;34m'
readonly CFN_NC='\033[0m'

# =============================================================================
# Logging Functions
# =============================================================================

cfn_log_info() {
    echo -e "${CFN_BLUE}[CFN]${CFN_NC} $1" >&2
}

cfn_log_success() {
    echo -e "${CFN_GREEN}[CFN]${CFN_NC} $1" >&2
}

cfn_log_warning() {
    echo -e "${CFN_YELLOW}[CFN]${CFN_NC} $1" >&2
}

cfn_log_error() {
    echo -e "${CFN_RED}[CFN]${CFN_NC} $1" >&2
}

# =============================================================================
# Stack Status Functions
# =============================================================================

# Check if a CloudFormation stack exists
# Arguments: stack_name [region]
# Returns: 0 if exists, 1 if not
cfn_stack_exists() {
    local stack_name="$1"
    local region="${2:-$CFN_REGION}"

    aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$region" \
        --output text \
        --query 'Stacks[0].StackStatus' \
        2>/dev/null && return 0 || return 1
}

# Get the current status of a CloudFormation stack
# Arguments: stack_name [region]
# Outputs: Stack status or "DOES_NOT_EXIST"
cfn_get_stack_status() {
    local stack_name="$1"
    local region="${2:-$CFN_REGION}"

    local status
    status=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$region" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null) || echo "DOES_NOT_EXIST"

    echo "$status"
}

# Get a specific output from a CloudFormation stack
# Arguments: stack_name output_key [default_value] [region]
# Outputs: Output value or default
cfn_get_stack_output() {
    local stack_name="$1"
    local output_key="$2"
    local default_value="${3:-}"
    local region="${4:-$CFN_REGION}"

    local value
    value=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --query "Stacks[0].Outputs[?OutputKey=='${output_key}'].OutputValue" \
        --output text \
        --region "$region" 2>/dev/null) || value=""

    if [[ -z "$value" || "$value" == "None" ]]; then
        echo "$default_value"
    else
        echo "$value"
    fi
}

# =============================================================================
# Stack Cleanup Functions
# =============================================================================

# Delete a failed CloudFormation stack (ROLLBACK_COMPLETE, CREATE_FAILED, etc.)
# Arguments: stack_name [region]
# Returns: 0 on success or if no cleanup needed
cfn_cleanup_failed() {
    local stack_name="$1"
    local region="${2:-$CFN_REGION}"

    local status
    status=$(cfn_get_stack_status "$stack_name" "$region")

    case "$status" in
        ROLLBACK_COMPLETE|CREATE_FAILED|DELETE_FAILED)
            cfn_log_warning "Cleaning up failed stack: $stack_name (status: $status)"
            aws cloudformation delete-stack \
                --stack-name "$stack_name" \
                --region "$region"
            aws cloudformation wait stack-delete-complete \
                --stack-name "$stack_name" \
                --region "$region"
            cfn_log_success "Cleaned up failed stack: $stack_name"
            ;;
        DOES_NOT_EXIST)
            # Nothing to clean up
            ;;
        *)
            # Stack exists and is not in failed state
            ;;
    esac

    return 0
}

# =============================================================================
# Stack Deployment Functions
# =============================================================================

# Wait for a CloudFormation stack to reach a stable state
# Arguments: stack_name operation [region]
# operation: "create" or "update"
cfn_wait_for_stack() {
    local stack_name="$1"
    local operation="$2"
    local region="${3:-$CFN_REGION}"

    cfn_log_info "Waiting for stack $operation to complete: $stack_name"

    if [[ "$operation" == "create" ]]; then
        aws cloudformation wait stack-create-complete \
            --stack-name "$stack_name" \
            --region "$region"
    else
        aws cloudformation wait stack-update-complete \
            --stack-name "$stack_name" \
            --region "$region"
    fi

    local final_status
    final_status=$(cfn_get_stack_status "$stack_name" "$region")

    case "$final_status" in
        CREATE_COMPLETE|UPDATE_COMPLETE)
            cfn_log_success "Stack $operation complete: $stack_name"
            return 0
            ;;
        *)
            cfn_log_error "Stack $operation failed: $stack_name (status: $final_status)"
            return 1
            ;;
    esac
}

# Deploy a CloudFormation stack (create or update as appropriate)
# Uses `aws cloudformation deploy` which handles create/update automatically
# Arguments:
#   stack_name      - Name of the CloudFormation stack
#   template_file   - Path to CloudFormation template file
#   parameters      - Parameter overrides (space-separated Key=Value pairs)
#   tags            - Tags (space-separated Key=Value pairs)
#   [capabilities]  - Optional IAM capabilities (default: CAPABILITY_NAMED_IAM)
#   [region]        - Optional AWS region
# Returns: 0 on success, 1 on failure
cfn_deploy_stack() {
    local stack_name="$1"
    local template_file="$2"
    local parameters="${3:-}"
    local tags="${4:-}"
    local capabilities="${5:-CAPABILITY_NAMED_IAM}"
    local region="${6:-$CFN_REGION}"

    cfn_log_info "Deploying stack: $stack_name"

    # First, clean up any failed stack
    cfn_cleanup_failed "$stack_name" "$region"

    # Build deploy command
    local cmd="aws cloudformation deploy"
    cmd+=" --stack-name $stack_name"
    cmd+=" --template-file $template_file"
    cmd+=" --region $region"
    cmd+=" --no-fail-on-empty-changeset"

    # Add capabilities if specified
    if [[ -n "$capabilities" ]]; then
        cmd+=" --capabilities $capabilities"
    fi

    # Add parameters if specified
    if [[ -n "$parameters" ]]; then
        cmd+=" --parameter-overrides $parameters"
    fi

    # Add tags if specified
    if [[ -n "$tags" ]]; then
        cmd+=" --tags $tags"
    fi

    # Execute deployment
    cfn_log_info "Running: $cmd"
    if eval "$cmd"; then
        cfn_log_success "Stack deployed: $stack_name"
        return 0
    else
        cfn_log_error "Stack deployment failed: $stack_name"
        return 1
    fi
}

# Deploy a CloudFormation stack with the legacy create/update pattern
# Use this for stacks that need explicit create vs update handling
# Arguments:
#   stack_name      - Name of the CloudFormation stack
#   template_file   - Path to CloudFormation template file
#   parameters      - AWS CLI format parameters (--parameters ParameterKey=X,ParameterValue=Y ...)
#   tags            - AWS CLI format tags (Key=X,Value=Y ...)
#   [capabilities]  - Optional IAM capabilities
#   [region]        - Optional AWS region
cfn_deploy_stack_legacy() {
    local stack_name="$1"
    local template_file="$2"
    local parameters="${3:-}"
    local tags="${4:-}"
    local capabilities="${5:-CAPABILITY_NAMED_IAM}"
    local region="${6:-$CFN_REGION}"

    cfn_log_info "Deploying stack (legacy mode): $stack_name"

    # Clean up any failed stack first
    cfn_cleanup_failed "$stack_name" "$region"

    local status
    status=$(cfn_get_stack_status "$stack_name" "$region")

    # Build base command parts
    local base_cmd="--template-body file://$template_file"
    base_cmd+=" --region $region"
    base_cmd+=" --no-cli-pager"

    if [[ -n "$capabilities" ]]; then
        base_cmd+=" --capabilities $capabilities"
    fi

    if [[ -n "$tags" ]]; then
        base_cmd+=" --tags $tags"
    fi

    case "$status" in
        CREATE_COMPLETE|UPDATE_COMPLETE|UPDATE_ROLLBACK_COMPLETE)
            # Stack exists and is in updatable state
            cfn_log_info "Updating existing stack: $stack_name"
            local update_output
            if update_output=$(aws cloudformation update-stack \
                --stack-name "$stack_name" \
                $base_cmd \
                $parameters 2>&1); then
                cfn_wait_for_stack "$stack_name" "update" "$region"
            else
                if echo "$update_output" | grep -q "No updates are to be performed"; then
                    cfn_log_info "Stack already up-to-date: $stack_name"
                else
                    cfn_log_error "Update failed: $update_output"
                    return 1
                fi
            fi
            ;;
        DOES_NOT_EXIST)
            # Create new stack
            cfn_log_info "Creating new stack: $stack_name"
            aws cloudformation create-stack \
                --stack-name "$stack_name" \
                $base_cmd \
                $parameters
            cfn_wait_for_stack "$stack_name" "create" "$region"
            ;;
        *)
            cfn_log_error "Stack in unexpected state: $stack_name ($status)"
            return 1
            ;;
    esac

    cfn_log_success "Stack ready: $stack_name"
    return 0
}

# Verify a stack is in a ready state (CREATE_COMPLETE or UPDATE_COMPLETE)
# Arguments: stack_name [region]
# Returns: 0 if ready, 1 if not
cfn_verify_stack_ready() {
    local stack_name="$1"
    local region="${2:-$CFN_REGION}"

    local status
    status=$(cfn_get_stack_status "$stack_name" "$region")

    case "$status" in
        CREATE_COMPLETE|UPDATE_COMPLETE)
            return 0
            ;;
        *)
            cfn_log_error "Stack not ready: $stack_name (status: $status)"
            return 1
            ;;
    esac
}

# =============================================================================
# Export functions for use in buildspecs
# =============================================================================
export -f cfn_log_info cfn_log_success cfn_log_warning cfn_log_error
export -f cfn_stack_exists cfn_get_stack_status cfn_get_stack_output
export -f cfn_cleanup_failed cfn_wait_for_stack
export -f cfn_deploy_stack cfn_deploy_stack_legacy cfn_verify_stack_ready
