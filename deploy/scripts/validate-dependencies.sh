#!/bin/bash
# =============================================================================
# Project Aura - Pre-Deployment Dependency Validation
# =============================================================================
# Validates required dependencies and prerequisites before deployment.
# Checks CloudFormation stacks, environment variables, and AWS resources.
#
# USAGE:
#   source deploy/scripts/validate-dependencies.sh
#   validate_cfn_stacks "stack1" "stack2" "stack3"
#   validate_env_vars "VAR1" "VAR2" "VAR3"
#
# FUNCTIONS:
#   validate_cfn_stacks      - Verify CloudFormation stacks exist and are ready
#   validate_env_vars        - Check required environment variables are set
#   validate_aws_credentials - Verify AWS credentials are configured
#   validate_eks_cluster     - Check EKS cluster exists and is accessible
#   validate_ssm_parameters  - Verify SSM parameters exist
#   validate_ecr_repos       - Check ECR repositories exist
#   validate_s3_bucket       - Verify S3 bucket exists and is accessible
#
# PREREQUISITES:
#   - AWS CLI configured
#   - Required environment variables: AWS_DEFAULT_REGION
#
# =============================================================================

# Fail on error and pipe failures (unless already set)
if [[ "${VALIDATE_HELPERS_SOURCED:-}" != "true" ]]; then
    set -o pipefail
    VALIDATE_HELPERS_SOURCED=true
fi

# =============================================================================
# Configuration
# =============================================================================
VALIDATE_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION:-us-east-1}}"

# Colors for output
readonly VALIDATE_RED='\033[0;31m'
readonly VALIDATE_GREEN='\033[0;32m'
readonly VALIDATE_YELLOW='\033[1;33m'
readonly VALIDATE_BLUE='\033[0;34m'
readonly VALIDATE_NC='\033[0m'

# =============================================================================
# Logging Functions
# =============================================================================

validate_log_info() {
    echo -e "${VALIDATE_BLUE}[VALIDATE]${VALIDATE_NC} $1" >&2
}

validate_log_success() {
    echo -e "${VALIDATE_GREEN}[VALIDATE]${VALIDATE_NC} $1" >&2
}

validate_log_warning() {
    echo -e "${VALIDATE_YELLOW}[VALIDATE]${VALIDATE_NC} $1" >&2
}

validate_log_error() {
    echo -e "${VALIDATE_RED}[VALIDATE]${VALIDATE_NC} $1" >&2
}

# =============================================================================
# Environment Validation
# =============================================================================

# Validate required environment variables are set
# Arguments: var_names... (variable names to check)
# Returns: 0 if all set, 1 if any missing
validate_env_vars() {
    local missing=()

    for var_name in "$@"; do
        if [[ -z "${!var_name:-}" ]]; then
            missing+=("$var_name")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        validate_log_error "Missing required environment variables: ${missing[*]}"
        return 1
    fi

    validate_log_success "All required environment variables are set"
    return 0
}

# Validate AWS credentials are configured and working
# Returns: 0 if valid, 1 if not
validate_aws_credentials() {
    validate_log_info "Validating AWS credentials..."

    if ! aws sts get-caller-identity --region "$VALIDATE_REGION" >/dev/null 2>&1; then
        validate_log_error "AWS credentials not configured or invalid"
        return 1
    fi

    local account_id
    account_id=$(aws sts get-caller-identity --query Account --output text --region "$VALIDATE_REGION")
    validate_log_success "AWS credentials valid (Account: $account_id)"
    return 0
}

# =============================================================================
# CloudFormation Validation
# =============================================================================

# Validate CloudFormation stacks exist and are in ready state
# Arguments: stack_names... (stack names to check)
# Returns: 0 if all ready, 1 if any not ready
validate_cfn_stacks() {
    local failed=()
    local region="${VALIDATE_REGION}"

    validate_log_info "Validating CloudFormation stacks..."

    for stack_name in "$@"; do
        local status
        status=$(aws cloudformation describe-stacks \
            --stack-name "$stack_name" \
            --query 'Stacks[0].StackStatus' \
            --output text \
            --region "$region" 2>/dev/null) || status="DOES_NOT_EXIST"

        case "$status" in
            CREATE_COMPLETE|UPDATE_COMPLETE)
                validate_log_info "  ✓ $stack_name ($status)"
                ;;
            *)
                validate_log_error "  ✗ $stack_name ($status)"
                failed+=("$stack_name")
                ;;
        esac
    done

    if [[ ${#failed[@]} -gt 0 ]]; then
        validate_log_error "Failed stacks: ${failed[*]}"
        return 1
    fi

    validate_log_success "All CloudFormation stacks are ready"
    return 0
}

# Get outputs from CloudFormation stacks
# Arguments: stack_name output_keys...
# Returns: 0 if all outputs found, 1 if any missing
validate_cfn_outputs() {
    local stack_name="$1"
    shift
    local output_keys=("$@")
    local missing=()

    validate_log_info "Validating outputs from stack: $stack_name"

    for output_key in "${output_keys[@]}"; do
        local value
        value=$(aws cloudformation describe-stacks \
            --stack-name "$stack_name" \
            --query "Stacks[0].Outputs[?OutputKey=='${output_key}'].OutputValue" \
            --output text \
            --region "$VALIDATE_REGION" 2>/dev/null) || value=""

        if [[ -z "$value" || "$value" == "None" ]]; then
            validate_log_error "  ✗ Missing output: $output_key"
            missing+=("$output_key")
        else
            validate_log_info "  ✓ $output_key = $value"
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        return 1
    fi

    return 0
}

# =============================================================================
# EKS Validation
# =============================================================================

# Validate EKS cluster exists and is accessible
# Arguments: cluster_name [region]
# Returns: 0 if accessible, 1 if not
validate_eks_cluster() {
    local cluster_name="$1"
    local region="${2:-$VALIDATE_REGION}"

    validate_log_info "Validating EKS cluster: $cluster_name"

    # Check cluster exists
    local status
    status=$(aws eks describe-cluster \
        --name "$cluster_name" \
        --query 'cluster.status' \
        --output text \
        --region "$region" 2>/dev/null) || status="NOT_FOUND"

    if [[ "$status" != "ACTIVE" ]]; then
        validate_log_error "EKS cluster not ready: $cluster_name (status: $status)"
        return 1
    fi

    validate_log_success "EKS cluster is active: $cluster_name"
    return 0
}

# Validate kubectl can connect to EKS cluster
# Arguments: cluster_name [region]
# Returns: 0 if connected, 1 if not
validate_kubectl_connectivity() {
    local cluster_name="$1"
    local region="${2:-$VALIDATE_REGION}"

    validate_log_info "Validating kubectl connectivity to: $cluster_name"

    # Update kubeconfig
    if ! aws eks update-kubeconfig \
        --name "$cluster_name" \
        --region "$region" \
        >/dev/null 2>&1; then
        validate_log_error "Failed to update kubeconfig for: $cluster_name"
        return 1
    fi

    # Test connectivity
    if ! kubectl cluster-info >/dev/null 2>&1; then
        validate_log_error "kubectl cannot connect to cluster"
        return 1
    fi

    validate_log_success "kubectl connected to cluster"
    return 0
}

# =============================================================================
# SSM Parameter Validation
# =============================================================================

# Validate SSM parameters exist
# Arguments: parameter_names... (full parameter paths)
# Returns: 0 if all exist, 1 if any missing
validate_ssm_parameters() {
    local missing=()

    validate_log_info "Validating SSM parameters..."

    for param_name in "$@"; do
        if aws ssm get-parameter \
            --name "$param_name" \
            --region "$VALIDATE_REGION" \
            >/dev/null 2>&1; then
            validate_log_info "  ✓ $param_name"
        else
            validate_log_error "  ✗ $param_name (not found)"
            missing+=("$param_name")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        return 1
    fi

    validate_log_success "All SSM parameters exist"
    return 0
}

# =============================================================================
# ECR Validation
# =============================================================================

# Validate ECR repositories exist
# Arguments: repo_names... (repository names)
# Returns: 0 if all exist, 1 if any missing
validate_ecr_repos() {
    local missing=()

    validate_log_info "Validating ECR repositories..."

    for repo_name in "$@"; do
        if aws ecr describe-repositories \
            --repository-names "$repo_name" \
            --region "$VALIDATE_REGION" \
            >/dev/null 2>&1; then
            validate_log_info "  ✓ $repo_name"
        else
            validate_log_error "  ✗ $repo_name (not found)"
            missing+=("$repo_name")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        return 1
    fi

    validate_log_success "All ECR repositories exist"
    return 0
}

# Check if ECR repository has at least one image
# Arguments: repo_name [tag]
# Returns: 0 if image exists, 1 if not
validate_ecr_image_exists() {
    local repo_name="$1"
    local tag="${2:-latest}"

    validate_log_info "Checking for image: $repo_name:$tag"

    if aws ecr describe-images \
        --repository-name "$repo_name" \
        --image-ids imageTag="$tag" \
        --region "$VALIDATE_REGION" \
        >/dev/null 2>&1; then
        validate_log_success "Image exists: $repo_name:$tag"
        return 0
    else
        validate_log_warning "Image not found: $repo_name:$tag"
        return 1
    fi
}

# =============================================================================
# S3 Validation
# =============================================================================

# Validate S3 bucket exists and is accessible
# Arguments: bucket_name
# Returns: 0 if accessible, 1 if not
validate_s3_bucket() {
    local bucket_name="$1"

    validate_log_info "Validating S3 bucket: $bucket_name"

    if aws s3api head-bucket \
        --bucket "$bucket_name" \
        --region "$VALIDATE_REGION" \
        2>/dev/null; then
        validate_log_success "S3 bucket accessible: $bucket_name"
        return 0
    else
        validate_log_error "S3 bucket not accessible: $bucket_name"
        return 1
    fi
}

# =============================================================================
# Composite Validation Functions
# =============================================================================

# Validate all Layer 1 (Foundation) prerequisites
# Arguments: project_name environment
validate_foundation_layer() {
    local project_name="$1"
    local environment="$2"

    validate_log_info "Validating Foundation Layer prerequisites..."

    local stacks=(
        "${project_name}-networking-${environment}"
        "${project_name}-iam-${environment}"
    )

    validate_cfn_stacks "${stacks[@]}"
}

# Validate all Layer 2 (Data) prerequisites
# Arguments: project_name environment
validate_data_layer() {
    local project_name="$1"
    local environment="$2"

    validate_log_info "Validating Data Layer prerequisites..."

    local stacks=(
        "${project_name}-neptune-${environment}"
        "${project_name}-opensearch-${environment}"
        "${project_name}-dynamodb-${environment}"
    )

    validate_cfn_stacks "${stacks[@]}"
}

# Validate all Layer 3 (Compute) prerequisites
# Arguments: project_name environment
validate_compute_layer() {
    local project_name="$1"
    local environment="$2"

    validate_log_info "Validating Compute Layer prerequisites..."

    # Validate EKS cluster
    local cluster_name="${project_name}-cluster-${environment}"
    validate_eks_cluster "$cluster_name"

    # Validate node groups are ready
    local node_count
    node_count=$(aws eks list-nodegroups \
        --cluster-name "$cluster_name" \
        --query 'nodegroups | length(@)' \
        --output text \
        --region "$VALIDATE_REGION" 2>/dev/null) || node_count=0

    if [[ $node_count -eq 0 ]]; then
        validate_log_error "No node groups found for cluster: $cluster_name"
        return 1
    fi

    validate_log_success "Found $node_count node group(s)"
    return 0
}

# =============================================================================
# Full Deployment Readiness Check
# =============================================================================

# Run full pre-deployment validation
# Arguments: project_name environment layer
# Returns: 0 if ready, 1 if not
validate_deployment_readiness() {
    local project_name="$1"
    local environment="$2"
    local layer="${3:-all}"

    validate_log_info "=========================================="
    validate_log_info "Pre-Deployment Validation"
    validate_log_info "Project: $project_name"
    validate_log_info "Environment: $environment"
    validate_log_info "Layer: $layer"
    validate_log_info "=========================================="

    local failed=0

    # Always validate credentials
    validate_aws_credentials || ((failed++))

    # Always validate required env vars
    validate_env_vars "PROJECT_NAME" "ENVIRONMENT" "AWS_DEFAULT_REGION" || ((failed++))

    # Layer-specific validation
    case "$layer" in
        foundation|1)
            # Foundation has no prerequisites
            ;;
        data|2)
            validate_foundation_layer "$project_name" "$environment" || ((failed++))
            ;;
        compute|3)
            validate_foundation_layer "$project_name" "$environment" || ((failed++))
            validate_data_layer "$project_name" "$environment" || ((failed++))
            ;;
        application|4)
            validate_foundation_layer "$project_name" "$environment" || ((failed++))
            validate_data_layer "$project_name" "$environment" || ((failed++))
            validate_compute_layer "$project_name" "$environment" || ((failed++))
            ;;
        all)
            # Validate everything that should already exist
            validate_foundation_layer "$project_name" "$environment" || ((failed++))
            ;;
    esac

    if [[ $failed -gt 0 ]]; then
        validate_log_error "=========================================="
        validate_log_error "Validation FAILED ($failed checks)"
        validate_log_error "=========================================="
        return 1
    fi

    validate_log_success "=========================================="
    validate_log_success "Validation PASSED"
    validate_log_success "=========================================="
    return 0
}

# =============================================================================
# Export functions for use in buildspecs
# =============================================================================
export -f validate_log_info validate_log_success validate_log_warning validate_log_error
export -f validate_env_vars validate_aws_credentials
export -f validate_cfn_stacks validate_cfn_outputs
export -f validate_eks_cluster validate_kubectl_connectivity
export -f validate_ssm_parameters
export -f validate_ecr_repos validate_ecr_image_exists
export -f validate_s3_bucket
export -f validate_foundation_layer validate_data_layer validate_compute_layer
export -f validate_deployment_readiness
