#!/bin/bash
# =============================================================================
# Project Aura - Pipeline Readiness Verification
# =============================================================================
#
# Verifies that all prerequisites for running the deployment pipeline are met.
#
# USAGE:
#   ./deploy/scripts/verify-pipeline-readiness.sh <environment> [region]
#
# EXAMPLES:
#   ./deploy/scripts/verify-pipeline-readiness.sh qa
#   ./deploy/scripts/verify-pipeline-readiness.sh qa us-east-1
#
# =============================================================================

set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-aura}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

# Parse arguments
ENVIRONMENT="${1:-}"
REGION="${2:-us-east-1}"

if [ -z "${ENVIRONMENT}" ]; then
    echo "Usage: $0 <environment> [region]"
    echo "Example: $0 qa us-east-1"
    exit 1
fi

echo "=========================================="
echo "Pipeline Readiness Check - ${ENVIRONMENT}"
echo "=========================================="
echo ""

ERRORS=0
WARNINGS=0

# Check AWS credentials
log_info "Checking AWS credentials..."
if aws sts get-caller-identity &> /dev/null; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
    log_success "AWS credentials configured (Account: ${ACCOUNT_ID})"
else
    log_error "AWS credentials not configured"
    ERRORS=$((ERRORS + 1))
fi

# Check required stacks
echo ""
log_info "Checking required CloudFormation stacks..."

REQUIRED_STACKS=(
    "${PROJECT_NAME}-account-bootstrap-${ENVIRONMENT}"
    "${PROJECT_NAME}-iam-${ENVIRONMENT}"
    "${PROJECT_NAME}-networking-${ENVIRONMENT}"
    "${PROJECT_NAME}-neptune-${ENVIRONMENT}"
    "${PROJECT_NAME}-opensearch-${ENVIRONMENT}"
    "${PROJECT_NAME}-eks-cluster-${ENVIRONMENT}"
)

for stack in "${REQUIRED_STACKS[@]}"; do
    if aws cloudformation describe-stacks --stack-name "${stack}" --region "${REGION}" &> /dev/null; then
        STATUS=$(aws cloudformation describe-stacks --stack-name "${stack}" --region "${REGION}" \
            --query 'Stacks[0].StackStatus' --output text)
        if [[ "${STATUS}" == *"COMPLETE"* ]] && [[ "${STATUS}" != *"ROLLBACK"* ]]; then
            log_success "${stack} (${STATUS})"
        else
            log_error "${stack} (${STATUS})"
            ERRORS=$((ERRORS + 1))
        fi
    else
        log_error "${stack} (NOT FOUND)"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check required CodeBuild projects
echo ""
log_info "Checking required CodeBuild projects..."

REQUIRED_PROJECTS=(
    "${PROJECT_NAME}-foundation-deploy-${ENVIRONMENT}"
    "${PROJECT_NAME}-data-deploy-${ENVIRONMENT}"
    "${PROJECT_NAME}-compute-deploy-${ENVIRONMENT}"
    "${PROJECT_NAME}-application-deploy-${ENVIRONMENT}"
    "${PROJECT_NAME}-observability-deploy-${ENVIRONMENT}"
    "${PROJECT_NAME}-serverless-deploy-${ENVIRONMENT}"
    "${PROJECT_NAME}-sandbox-deploy-${ENVIRONMENT}"
    "${PROJECT_NAME}-security-deploy-${ENVIRONMENT}"
    "${PROJECT_NAME}-docker-build-${ENVIRONMENT}"
    "${PROJECT_NAME}-k8s-deploy-${ENVIRONMENT}"
    "${PROJECT_NAME}-integration-test-${ENVIRONMENT}"
)

for project in "${REQUIRED_PROJECTS[@]}"; do
    if aws codebuild batch-get-projects --names "${project}" --region "${REGION}" \
        --query 'projects[0].name' --output text 2>/dev/null | grep -q "${project}"; then
        log_success "${project}"
    else
        log_error "${project} (NOT FOUND)"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check Step Functions state machine
echo ""
log_info "Checking Step Functions pipeline..."

PIPELINE_STACK="${PROJECT_NAME}-deployment-pipeline-${ENVIRONMENT}"
if aws cloudformation describe-stacks --stack-name "${PIPELINE_STACK}" --region "${REGION}" &> /dev/null; then
    PIPELINE_ARN=$(aws cloudformation describe-stacks --stack-name "${PIPELINE_STACK}" --region "${REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' --output text)
    if [ -n "${PIPELINE_ARN}" ]; then
        log_success "Pipeline state machine: ${PIPELINE_ARN}"
    else
        log_warning "Pipeline deployed but ARN not found"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    log_warning "Pipeline not deployed yet (run deploy-pipeline-infrastructure.sh)"
    WARNINGS=$((WARNINGS + 1))
fi

# Check SSM parameters
echo ""
log_info "Checking SSM parameters..."

SSM_PARAMS=(
    "/${PROJECT_NAME}/${ENVIRONMENT}/neptune-endpoint"
    "/${PROJECT_NAME}/${ENVIRONMENT}/opensearch-endpoint"
)

for param in "${SSM_PARAMS[@]}"; do
    if aws ssm get-parameter --name "${param}" --region "${REGION}" &> /dev/null; then
        log_success "${param}"
    else
        log_warning "${param} (NOT FOUND - will be created by data layer)"
        WARNINGS=$((WARNINGS + 1))
    fi
done

# Check EKS cluster access
echo ""
log_info "Checking EKS cluster access..."

CLUSTER_NAME="${PROJECT_NAME}-cluster-${ENVIRONMENT}"
if aws eks describe-cluster --name "${CLUSTER_NAME}" --region "${REGION}" &> /dev/null; then
    CLUSTER_STATUS=$(aws eks describe-cluster --name "${CLUSTER_NAME}" --region "${REGION}" \
        --query 'cluster.status' --output text)
    if [ "${CLUSTER_STATUS}" = "ACTIVE" ]; then
        log_success "EKS cluster ${CLUSTER_NAME} is ACTIVE"
    else
        log_warning "EKS cluster ${CLUSTER_NAME} status: ${CLUSTER_STATUS}"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    log_error "EKS cluster ${CLUSTER_NAME} not found"
    ERRORS=$((ERRORS + 1))
fi

# Summary
echo ""
echo "=========================================="
echo "VERIFICATION SUMMARY"
echo "=========================================="
echo ""

if [ ${ERRORS} -eq 0 ] && [ ${WARNINGS} -eq 0 ]; then
    log_success "All checks passed! Pipeline is ready to run."
    echo ""
    echo "To trigger the deployment pipeline:"
    echo ""
    echo "  aws stepfunctions start-execution \\"
    echo "    --state-machine-arn ${PIPELINE_ARN:-'<deploy pipeline first>'} \\"
    echo "    --input '{\"environment\": \"${ENVIRONMENT}\", \"region\": \"${REGION}\"}'"
    exit 0
elif [ ${ERRORS} -eq 0 ]; then
    log_warning "${WARNINGS} warning(s) found. Pipeline may work but review warnings."
    exit 0
else
    log_error "${ERRORS} error(s) found. Fix these before running the pipeline."
    exit 1
fi
