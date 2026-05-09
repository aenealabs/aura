#!/bin/bash
# =============================================================================
# Project Aura - Fresh Account Bootstrap Script
# =============================================================================
# This script bootstraps a fresh AWS account with all required CodeBuild
# projects for CI/CD automation.
#
# USAGE:
#   ./deploy/scripts/bootstrap-fresh-account.sh <environment> [region]
#
# EXAMPLES:
#   ./deploy/scripts/bootstrap-fresh-account.sh dev
#   ./deploy/scripts/bootstrap-fresh-account.sh qa us-east-1
#   ./deploy/scripts/bootstrap-fresh-account.sh prod us-gov-west-1
#
# PREREQUISITES:
#   1. AWS CLI configured with appropriate credentials
#   2. GitHub CodeConnection created and ARN stored in SSM:
#      /aura/global/codeconnections-arn
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
  $0 dev                    # Bootstrap dev in us-east-1
  $0 qa us-east-1           # Bootstrap qa in us-east-1
  $0 prod us-gov-west-1     # Bootstrap prod in GovCloud

Prerequisites:
  1. AWS CLI configured with credentials for the target account
  2. GitHub CodeConnection created and ARN stored in SSM:
     aws ssm put-parameter --name /aura/global/codeconnections-arn \\
       --value "arn:aws:codeconnections:us-east-1:123456789012:connection/xxx" \\
       --type String
EOF
    exit 1
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install: https://aws.amazon.com/cli/"
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi

    # Check CodeConnection SSM parameter
    if ! aws ssm get-parameter --name "/aura/global/codeconnections-arn" --region "${REGION}" &> /dev/null; then
        log_error "CodeConnection SSM parameter not found: /aura/global/codeconnections-arn"
        echo ""
        echo "Create the CodeConnection first:"
        echo "  1. Go to AWS CodeBuild > Settings > Connections"
        echo "  2. Create a GitHub connection"
        echo "  3. Store the ARN in SSM:"
        echo "     aws ssm put-parameter --name /aura/global/codeconnections-arn \\"
        echo "       --value \"arn:aws:codeconnections:${REGION}:ACCOUNT:connection/xxx\" \\"
        echo "       --type String --region ${REGION}"
        exit 1
    fi

    # Bedrock model access preflight (commercial regions only; GovCloud
    # has its own model approval flow and skips this check).
    if [[ ! "${REGION}" =~ ^us-gov- ]]; then
        if ! aws bedrock list-foundation-models --region "${REGION}" &> /dev/null; then
            log_warning "Cannot list Bedrock foundation models in ${REGION}."
            echo "    The application layer will fail at runtime if Bedrock model"
            echo "    access has not been requested in the AWS console:"
            echo "      AWS Console > Bedrock > Model access > Request access"
            echo "    Required models (per CLAUDE.md):"
            echo "      - Anthropic Claude Sonnet 4.6 (claude-sonnet-4-6)"
            echo "      - Anthropic Claude Haiku 4.5 (claude-haiku-4-5-20251001)"
            echo "    Bootstrap will continue, but plan to approve access before"
            echo "    starting the deployment-pipeline state machine."
        else
            log_success "Bedrock API reachable in ${REGION}"
        fi
    fi

    log_success "Prerequisites check passed"
}

bootstrap_ecr_base_images() {
    log_info "Bootstrapping ECR private base images..."

    # The aura-ecr-base-images-{env} stack provides the private base
    # image repositories. CLAUDE.md mandates that every container
    # build use private ECR base images, so we deploy this stack
    # before any layer build that depends on it.
    local STACK_NAME="${PROJECT_NAME}-ecr-base-images-${ENVIRONMENT}"
    local TEMPLATE_FILE="${REPO_ROOT}/deploy/cloudformation/ecr-base-images.yaml"

    if [ ! -f "${TEMPLATE_FILE}" ]; then
        log_warning "ecr-base-images.yaml not found; skipping base image bootstrap."
        log_warning "Layer builds may fail later if private base images are required."
        return 0
    fi

    # Deploy the ECR repository stack (idempotent).
    aws cloudformation deploy \
        --stack-name "${STACK_NAME}" \
        --template-file "${TEMPLATE_FILE}" \
        --parameter-overrides \
            Environment="${ENVIRONMENT}" \
            ProjectName="${PROJECT_NAME}" \
        --capabilities CAPABILITY_NAMED_IAM \
        --tags Project="${PROJECT_NAME}" Environment="${ENVIRONMENT}" Layer=bootstrap \
        --no-fail-on-empty-changeset \
        --region "${REGION}" \
        || { log_error "ECR base images stack deploy failed"; exit 1; }

    log_success "ECR base images stack deployed: ${STACK_NAME}"

    # Pull-and-push approved upstream images to the private repos.
    # bootstrap-base-images.sh handles the runtime detection (podman
    # vs docker) and the version pinning per CVE patch cycle.
    local PUSH_SCRIPT="${SCRIPT_DIR}/bootstrap-base-images.sh"
    if [ -x "${PUSH_SCRIPT}" ]; then
        log_info "Pulling and pushing approved base images to private ECR..."
        if AWS_REGION="${REGION}" "${PUSH_SCRIPT}" "${ENVIRONMENT}"; then
            log_success "Private base images populated"
        else
            log_warning "Private base image push failed; layer builds may fail."
            log_warning "Re-run manually: AWS_REGION=${REGION} ${PUSH_SCRIPT} ${ENVIRONMENT}"
        fi
    else
        log_warning "bootstrap-base-images.sh not found or not executable; skipping image push."
        log_warning "Run manually before triggering layer builds:"
        log_warning "  AWS_REGION=${REGION} ${PUSH_SCRIPT} ${ENVIRONMENT}"
    fi
}

deploy_deployment_pipeline() {
    log_info "Deploying single-trigger deployment pipeline (Layer 6.11)..."

    # The deployment-pipeline.yaml Step Functions stack is what makes
    # the streamlined deploy a single command. Bootstrap provisions
    # the CodeBuild projects; this stack provisions the orchestrator
    # that invokes them in dependency order.
    local STACK_NAME="${PROJECT_NAME}-deployment-pipeline-${ENVIRONMENT}"
    local TEMPLATE_FILE="${REPO_ROOT}/deploy/cloudformation/deployment-pipeline.yaml"

    if [ ! -f "${TEMPLATE_FILE}" ]; then
        log_warning "deployment-pipeline.yaml not found; skipping orchestrator deploy."
        log_warning "Operator must trigger each layer's CodeBuild project manually."
        return 0
    fi

    aws cloudformation deploy \
        --stack-name "${STACK_NAME}" \
        --template-file "${TEMPLATE_FILE}" \
        --parameter-overrides \
            Environment="${ENVIRONMENT}" \
            ProjectName="${PROJECT_NAME}" \
        --capabilities CAPABILITY_NAMED_IAM \
        --tags Project="${PROJECT_NAME}" Environment="${ENVIRONMENT}" Layer=serverless \
        --no-fail-on-empty-changeset \
        --region "${REGION}" \
        || { log_error "Deployment pipeline deploy failed"; exit 1; }

    log_success "Deployment pipeline deployed: ${STACK_NAME}"
}

deploy_bootstrap_stack() {
    log_info "Deploying Bootstrap CodeBuild stack..."

    local STACK_NAME="${PROJECT_NAME}-codebuild-bootstrap-${ENVIRONMENT}"
    local TEMPLATE_FILE="${REPO_ROOT}/deploy/cloudformation/codebuild-bootstrap.yaml"

    if [ ! -f "${TEMPLATE_FILE}" ]; then
        log_error "Template not found: ${TEMPLATE_FILE}"
        exit 1
    fi

    # Check for stuck states
    local STACK_STATUS
    STACK_STATUS=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${REGION}" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "DOES_NOT_EXIST")

    if [ "${STACK_STATUS}" = "ROLLBACK_COMPLETE" ] || [ "${STACK_STATUS}" = "ROLLBACK_FAILED" ]; then
        log_warning "Stack in ${STACK_STATUS} state - deleting before recreating..."
        aws cloudformation delete-stack --stack-name "${STACK_NAME}" --region "${REGION}"
        aws cloudformation wait stack-delete-complete --stack-name "${STACK_NAME}" --region "${REGION}"
    fi

    # Deploy the bootstrap stack
    aws cloudformation deploy \
        --stack-name "${STACK_NAME}" \
        --template-file "${TEMPLATE_FILE}" \
        --parameter-overrides \
            Environment="${ENVIRONMENT}" \
            ProjectName="${PROJECT_NAME}" \
        --capabilities CAPABILITY_NAMED_IAM \
        --tags Project="${PROJECT_NAME}" Environment="${ENVIRONMENT}" Layer=bootstrap BootstrapExemption=true \
        --no-fail-on-empty-changeset \
        --region "${REGION}"

    log_success "Bootstrap CodeBuild stack deployed: ${STACK_NAME}"
}

trigger_bootstrap_build() {
    log_info "Triggering Bootstrap CodeBuild project..."

    local PROJECT_NAME_CB="${PROJECT_NAME}-bootstrap-deploy-${ENVIRONMENT}"

    # Start the build
    local BUILD_ID
    BUILD_ID=$(aws codebuild start-build \
        --project-name "${PROJECT_NAME_CB}" \
        --region "${REGION}" \
        --query 'build.id' \
        --output text)

    log_info "Build started: ${BUILD_ID}"
    log_info "Monitor at: https://${REGION}.console.aws.amazon.com/codesuite/codebuild/projects/${PROJECT_NAME_CB}/build/${BUILD_ID}"
    echo ""

    # Wait for build to complete
    log_info "Waiting for build to complete (this may take 10-15 minutes)..."

    local STATUS="IN_PROGRESS"
    while [ "${STATUS}" = "IN_PROGRESS" ]; do
        sleep 30
        STATUS=$(aws codebuild batch-get-builds \
            --ids "${BUILD_ID}" \
            --region "${REGION}" \
            --query 'builds[0].buildStatus' \
            --output text)
        echo -n "."
    done
    echo ""

    if [ "${STATUS}" = "SUCCEEDED" ]; then
        log_success "Bootstrap build completed successfully!"
    else
        log_error "Bootstrap build failed with status: ${STATUS}"
        echo ""
        echo "View logs at:"
        echo "  https://${REGION}.console.aws.amazon.com/codesuite/codebuild/projects/${PROJECT_NAME_CB}/build/${BUILD_ID}/log"
        exit 1
    fi
}

print_next_steps() {
    local STATE_MACHINE_ARN
    STATE_MACHINE_ARN=$(aws cloudformation describe-stacks \
        --stack-name "${PROJECT_NAME}-deployment-pipeline-${ENVIRONMENT}" \
        --region "${REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
        --output text 2>/dev/null || echo "")

    echo ""
    echo "=========================================="
    echo "BOOTSTRAP COMPLETE - NEXT STEPS"
    echo "=========================================="
    echo ""
    echo "All 24 CodeBuild projects have been deployed."
    echo "Deployment pipeline state machine is ready."
    echo ""
    echo "STREAMLINED DEPLOY (recommended):"
    echo ""
    if [ -n "${STATE_MACHINE_ARN}" ] && [ "${STATE_MACHINE_ARN}" != "None" ]; then
        echo "  aws stepfunctions start-execution \\"
        echo "    --state-machine-arn ${STATE_MACHINE_ARN} \\"
        echo "    --input '{\"environment\": \"${ENVIRONMENT}\", \"region\": \"${REGION}\"}' \\"
        echo "    --region ${REGION}"
    else
        echo "  # State machine ARN not yet available; rerun bootstrap or"
        echo "  # check the deployment-pipeline stack outputs."
        echo "  aws stepfunctions list-state-machines --region ${REGION} \\"
        echo "    --query \"stateMachines[?contains(name, '${PROJECT_NAME}-deployment-pipeline')].stateMachineArn\""
    fi
    echo ""
    echo "Or, equivalently, use the wrapper:"
    echo "  ./deploy.sh deploy ${ENVIRONMENT}"
    echo ""
    echo "MANUAL LAYER-BY-LAYER (if the state machine is unavailable):"
    echo ""
    echo "  # Layer 1: Foundation (VPC, IAM, KMS, Security Groups)"
    echo "  aws codebuild start-build --project-name ${PROJECT_NAME}-foundation-deploy-${ENVIRONMENT} --region ${REGION}"
    echo ""
    echo "  # Layer 2: Data (Neptune, OpenSearch, DynamoDB, S3)"
    echo "  aws codebuild start-build --project-name ${PROJECT_NAME}-data-deploy-${ENVIRONMENT} --region ${REGION}"
    echo ""
    echo "  # Layer 3: Compute (EKS, ECR)"
    echo "  aws codebuild start-build --project-name ${PROJECT_NAME}-compute-deploy-${ENVIRONMENT} --region ${REGION}"
    echo ""
    echo "  # Layer 4: Application (Bedrock, IRSA)"
    echo "  aws codebuild start-build --project-name ${PROJECT_NAME}-application-deploy-${ENVIRONMENT} --region ${REGION}"
    echo "  # Layer 4 sub-layer: ADR-054 Multi-IdP infrastructure (LOUD-FAIL on error -- if this fails, re-run the full deployment pipeline rather than this project alone, so the failure surfaces at the orchestrator level for operator alarms)"
    echo "  aws codebuild start-build --project-name ${PROJECT_NAME}-application-identity-deploy-${ENVIRONMENT} --region ${REGION}"
    echo ""
    echo "  # Layer 5: Observability (Monitoring, Alerts)"
    echo "  aws codebuild start-build --project-name ${PROJECT_NAME}-observability-deploy-${ENVIRONMENT} --region ${REGION}"
    echo ""
    echo "  # Layer 6: Serverless (Lambda, Step Functions)"
    echo "  aws codebuild start-build --project-name ${PROJECT_NAME}-serverless-deploy-${ENVIRONMENT} --region ${REGION}"
    echo "  # Layer 6 sub-layer: ADR-056 Cloud Discovery + Calibration Pipeline (non-blocking on failure)"
    echo "  aws codebuild start-build --project-name ${PROJECT_NAME}-serverless-documentation-deploy-${ENVIRONMENT} --region ${REGION}"
    echo "  aws codebuild start-build --project-name ${PROJECT_NAME}-serverless-symbol-resolver-deploy-${ENVIRONMENT} --region ${REGION}"
    echo ""
    echo "  # Layer 7: Sandbox (HITL, Ephemeral Environments)"
    echo "  aws codebuild start-build --project-name ${PROJECT_NAME}-sandbox-deploy-${ENVIRONMENT} --region ${REGION}"
    echo ""
    echo "  # Layer 8: Security (GuardDuty, Config) + ADR-083 + ADR-084"
    echo "  aws codebuild start-build --project-name ${PROJECT_NAME}-security-deploy-${ENVIRONMENT} --region ${REGION}"
    echo "  aws codebuild start-build --project-name ${PROJECT_NAME}-runtime-security-deploy-${ENVIRONMENT} --region ${REGION}"
    echo "  aws codebuild start-build --project-name ${PROJECT_NAME}-vuln-scan-deploy-${ENVIRONMENT} --region ${REGION}"
    echo ""
    echo "For the full deployment guide, see:"
    echo "  docs/deployment/DEPLOYMENT_GUIDE.md (canonical)"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

main() {
    # Parse arguments
    if [ $# -lt 1 ]; then
        usage
    fi

    ENVIRONMENT="$1"
    REGION="${2:-us-east-1}"

    # Validate environment
    if [[ ! "${ENVIRONMENT}" =~ ^(dev|qa|prod)$ ]]; then
        log_error "Invalid environment: ${ENVIRONMENT}. Must be one of: dev, qa, prod"
        exit 1
    fi

    # Header
    echo "=========================================="
    echo "Project Aura - Fresh Account Bootstrap"
    echo "=========================================="
    echo "Environment: ${ENVIRONMENT}"
    echo "Region:      ${REGION}"
    echo "Project:     ${PROJECT_NAME}"
    echo "=========================================="
    echo ""

    # Execute bootstrap steps in dependency order:
    #   1. Preflight every implicit prerequisite (AWS creds,
    #      CodeConnection, Bedrock model access).
    #   2. Bootstrap private ECR base images BEFORE any layer build
    #      runs (CLAUDE.md mandates private ECR for all containers).
    #   3. Deploy the bootstrap CodeBuild stack and run it; this
    #      provisions the 24 layer CodeBuild projects.
    #   4. Deploy the deployment-pipeline state machine so the
    #      operator has a single command to drive the rest.
    #   5. Print the streamlined start-execution invocation.
    check_prerequisites
    bootstrap_ecr_base_images
    deploy_bootstrap_stack
    trigger_bootstrap_build
    deploy_deployment_pipeline
    print_next_steps

    log_success "Bootstrap complete!"
}

main "$@"
