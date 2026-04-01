#!/bin/bash
# =============================================================================
# Project Aura - Deployment Pipeline Infrastructure Setup
# =============================================================================
#
# Deploys the Step Functions deployment pipeline and supporting CodeBuild
# projects for automated environment deployments.
#
# USAGE:
#   ./deploy/scripts/deploy-pipeline-infrastructure.sh <environment> [region]
#
# EXAMPLES:
#   ./deploy/scripts/deploy-pipeline-infrastructure.sh qa
#   ./deploy/scripts/deploy-pipeline-infrastructure.sh qa us-east-1
#   ./deploy/scripts/deploy-pipeline-infrastructure.sh prod us-gov-west-1
#
# PREREQUISITES:
#   - AWS CLI configured with appropriate credentials
#   - Account bootstrap completed (aura-account-bootstrap-{env} stack exists)
#   - CodeBuild projects bootstrapped (run bootstrap-fresh-account.sh first)
#
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================
PROJECT_NAME="${PROJECT_NAME:-aura}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

usage() {
    cat << EOF
Usage: $0 <environment> [region]

Arguments:
  environment   Required. One of: dev, qa, prod
  region        Optional. AWS region (default: us-east-1, GovCloud: us-gov-west-1)

Examples:
  $0 qa                      # Deploy pipeline infrastructure to QA
  $0 qa us-east-1            # Deploy to QA in us-east-1
  $0 prod us-gov-west-1      # Deploy to prod in GovCloud

Prerequisites:
  1. AWS CLI configured with credentials for the target account
  2. Account bootstrap completed (aura-account-bootstrap-{env} stack)
  3. Foundation layer deployed (for CodeBuild service role)
EOF
    exit 1
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install it first."
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi

    # Get account info
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
    log_info "AWS Account ID: ${AWS_ACCOUNT_ID}"

    # Check if account bootstrap exists
    BOOTSTRAP_STACK="${PROJECT_NAME}-account-bootstrap-${ENVIRONMENT}"
    if ! aws cloudformation describe-stacks --stack-name "${BOOTSTRAP_STACK}" --region "${REGION}" &> /dev/null; then
        log_error "Account bootstrap stack not found: ${BOOTSTRAP_STACK}"
        log_error "Run account bootstrap first. See docs/deployment/MULTI_ACCOUNT_SETUP.md"
        exit 1
    fi
    log_success "Account bootstrap stack exists: ${BOOTSTRAP_STACK}"

    # Check if foundation layer exists (needed for CodeBuild role)
    FOUNDATION_STACK="${PROJECT_NAME}-iam-${ENVIRONMENT}"
    if ! aws cloudformation describe-stacks --stack-name "${FOUNDATION_STACK}" --region "${REGION}" &> /dev/null; then
        log_warning "Foundation IAM stack not found: ${FOUNDATION_STACK}"
        log_warning "Pipeline deployment may fail if CodeBuild role doesn't exist"
    else
        log_success "Foundation IAM stack exists: ${FOUNDATION_STACK}"
    fi

    # Check if docker-build project exists
    DOCKER_BUILD_PROJECT="${PROJECT_NAME}-docker-build-${ENVIRONMENT}"
    if ! aws codebuild batch-get-projects --names "${DOCKER_BUILD_PROJECT}" --region "${REGION}" --query 'projects[0].name' --output text 2>/dev/null | grep -q "${DOCKER_BUILD_PROJECT}"; then
        log_warning "Docker build project not found: ${DOCKER_BUILD_PROJECT}"
        log_warning "Run bootstrap-fresh-account.sh first to create CodeBuild projects"
    else
        log_success "Docker build project exists: ${DOCKER_BUILD_PROJECT}"
    fi

    log_success "Prerequisites check passed"
}

deploy_stack() {
    local template_file="$1"
    local stack_name="$2"
    local description="$3"
    shift 3
    local extra_params=("$@")

    log_info "Deploying ${description}..."
    log_info "  Stack: ${stack_name}"
    log_info "  Template: ${template_file}"

    if aws cloudformation deploy \
        --template-file "${REPO_ROOT}/${template_file}" \
        --stack-name "${stack_name}" \
        --parameter-overrides \
            ProjectName="${PROJECT_NAME}" \
            Environment="${ENVIRONMENT}" \
            "${extra_params[@]}" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "${REGION}" \
        --no-fail-on-empty-changeset 2>&1; then
        log_success "Deployed: ${stack_name}"
    else
        log_error "Failed to deploy: ${stack_name}"
        return 1
    fi
}

wait_for_stack() {
    local stack_name="$1"
    local timeout="${2:-300}"

    log_info "Waiting for stack ${stack_name} to complete..."

    local start_time=$(date +%s)
    while true; do
        local status=$(aws cloudformation describe-stacks \
            --stack-name "${stack_name}" \
            --region "${REGION}" \
            --query 'Stacks[0].StackStatus' \
            --output text 2>/dev/null || echo "UNKNOWN")

        case "${status}" in
            *COMPLETE)
                if [[ "${status}" == *ROLLBACK* ]]; then
                    log_error "Stack ${stack_name} rolled back: ${status}"
                    return 1
                fi
                log_success "Stack ${stack_name} completed: ${status}"
                return 0
                ;;
            *FAILED*)
                log_error "Stack ${stack_name} failed: ${status}"
                return 1
                ;;
            *IN_PROGRESS*)
                local elapsed=$(($(date +%s) - start_time))
                if [ "${elapsed}" -gt "${timeout}" ]; then
                    log_error "Timeout waiting for stack ${stack_name}"
                    return 1
                fi
                echo -n "."
                sleep 10
                ;;
            *)
                log_error "Unknown stack status: ${status}"
                return 1
                ;;
        esac
    done
}

# =============================================================================
# Main
# =============================================================================

# Parse arguments
if [ $# -lt 1 ]; then
    usage
fi

ENVIRONMENT="$1"
REGION="${2:-us-east-1}"

# Validate environment
case "${ENVIRONMENT}" in
    dev|qa|prod)
        ;;
    *)
        log_error "Invalid environment: ${ENVIRONMENT}. Must be one of: dev, qa, prod"
        exit 1
        ;;
esac

echo "=========================================="
echo "Project Aura - Pipeline Infrastructure"
echo "=========================================="
echo "Environment: ${ENVIRONMENT}"
echo "Region:      ${REGION}"
echo "Project:     ${PROJECT_NAME}"
echo "=========================================="
echo ""

# Check prerequisites
check_prerequisites

# =============================================================================
# Deploy Pipeline Infrastructure
# =============================================================================

log_info "Deploying pipeline infrastructure components..."
echo ""

# 1. Deploy K8s Deploy CodeBuild Project (Layer 3.5)
deploy_stack \
    "deploy/cloudformation/codebuild-k8s-deploy.yaml" \
    "${PROJECT_NAME}-codebuild-k8s-deploy-${ENVIRONMENT}" \
    "K8s Deployment CodeBuild Project (Layer 3.5)"

# 2. Deploy Integration Test CodeBuild Project (Layer 3.6)
deploy_stack \
    "deploy/cloudformation/codebuild-integration-test.yaml" \
    "${PROJECT_NAME}-codebuild-integration-test-${ENVIRONMENT}" \
    "Integration Test CodeBuild Project (Layer 3.6)"

# 3. Deploy Deployment Pipeline (Step Functions - Layer 6.11)
log_info "Deploying Step Functions pipeline..."
NOTIFICATION_EMAIL="${NOTIFICATION_EMAIL:-}"

PIPELINE_PARAMS=()
if [ -n "${NOTIFICATION_EMAIL}" ]; then
    PIPELINE_PARAMS+=("NotificationEmail=${NOTIFICATION_EMAIL}")
fi

deploy_stack \
    "deploy/cloudformation/deployment-pipeline.yaml" \
    "${PROJECT_NAME}-deployment-pipeline-${ENVIRONMENT}" \
    "Deployment Pipeline (Step Functions - Layer 6.11)" \
    "${PIPELINE_PARAMS[@]:-}"

# =============================================================================
# Verification
# =============================================================================

echo ""
log_info "Verifying deployment..."

# Get State Machine ARN
PIPELINE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "${PROJECT_NAME}-deployment-pipeline-${ENVIRONMENT}" \
    --region "${REGION}" \
    --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [ -n "${PIPELINE_ARN}" ]; then
    log_success "Deployment pipeline ready"
    echo ""
    echo "=========================================="
    echo "PIPELINE INFRASTRUCTURE DEPLOYED"
    echo "=========================================="
    echo ""
    echo "State Machine ARN:"
    echo "  ${PIPELINE_ARN}"
    echo ""
    echo "To trigger a full deployment:"
    echo ""
    echo "  aws stepfunctions start-execution \\"
    echo "    --state-machine-arn ${PIPELINE_ARN} \\"
    echo "    --input '{\"environment\": \"${ENVIRONMENT}\", \"region\": \"${REGION}\"}'"
    echo ""
    echo "To monitor in AWS Console:"
    echo "  Step Functions > State machines > ${PROJECT_NAME}-deployment-pipeline-${ENVIRONMENT}"
    echo ""
    echo "=========================================="
else
    log_error "Could not retrieve pipeline ARN"
    exit 1
fi

# List all deployed CodeBuild projects
echo ""
log_info "CodeBuild projects available for pipeline:"
aws codebuild list-projects --region "${REGION}" \
    --query "projects[?contains(@, '${PROJECT_NAME}') && contains(@, '${ENVIRONMENT}')]" \
    --output table 2>/dev/null || true

echo ""
log_success "Pipeline infrastructure deployment complete!"
