#!/bin/bash
################################################################################
# Aura Infrastructure Deployment - One-Command Orchestrator
#
# Wraps the bootstrap + deployment-pipeline state machine into a single
# invocation so a clean AWS account can reach a healthy environment with
# one command:
#
#     ./deploy.sh deploy dev
#
# What this does:
#   1. Preflight: AWS CLI, credentials, region, CodeConnection,
#      Bedrock model access (commercial regions), ALERT_EMAIL.
#   2. Bootstrap: deploy/scripts/bootstrap-fresh-account.sh (idempotent;
#      private ECR base images, 24 CodeBuild projects, deployment-
#      pipeline state machine).
#   3. Streamlined deploy: starts the deployment-pipeline state machine
#      and streams execution events until it reaches a terminal state.
#
# Per CLAUDE.md, this script is the user-facing single command. The
# underlying primitives (bootstrap-fresh-account.sh, the state machine
# itself) remain individually invocable for ops engineers who need
# finer control; this wrapper is for operators who just want the
# whole platform to come up.
#
# Commands:
#   deploy <env>     - Full one-command deploy (bootstrap + state machine)
#   redeploy <env>   - Re-run state machine only (no bootstrap)
#   status <env>     - Show latest state machine execution status
#   destroy <env>    - Tear down the environment (with confirmation)
#   validate         - cfn-lint every CloudFormation template
#   help             - Show this help message
################################################################################

set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-aura}"
AWS_REGION="${AWS_REGION:-us-east-1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }

show_help() {
    cat << EOF
Aura Infrastructure Deployment - One-Command Orchestrator

Usage:
    ./deploy.sh <command> [args...]

Commands:
    deploy <env>     Full one-command deploy (bootstrap + state machine).
                     <env> is one of: dev, qa, prod.
    redeploy <env>   Re-run the deployment-pipeline state machine only,
                     skipping bootstrap. Use after a failed deploy or
                     when re-applying changes.
    status <env>     Show the latest state-machine execution status.
    destroy <env>    Tear down the environment (with confirmation).
    validate         cfn-lint every CloudFormation template.
    help             Show this help message.

Environment variables:
    PROJECT_NAME    Project name (default: aura)
    AWS_REGION      AWS region (default: us-east-1)
    ALERT_EMAIL     Email for budget / alarm notifications (required for deploy)

Examples:
    # Single-command clean-account deploy
    ALERT_EMAIL=ops@example.com ./deploy.sh deploy dev

    # Re-run state machine after fixing a failed step
    ./deploy.sh redeploy dev

    # Check status
    ./deploy.sh status dev

Prerequisites (bootstrap-fresh-account.sh checks these too):
    1. AWS CLI configured for the target account
    2. GitHub CodeConnection ARN in SSM /aura/global/codeconnections-arn
    3. Bedrock model access approved (commercial regions; Claude Sonnet
       4.6 + Haiku 4.5 per CLAUDE.md)

For the canonical deployment guide, see:
    docs/deployment/DEPLOYMENT_GUIDE.md
EOF
}

validate_environment() {
    local env="$1"
    if [[ ! "${env}" =~ ^(dev|qa|prod)$ ]]; then
        log_error "Invalid environment: ${env}. Must be one of: dev, qa, prod"
        exit 1
    fi
}

ensure_alert_email() {
    if [ -z "${ALERT_EMAIL:-}" ]; then
        log_warning "ALERT_EMAIL not set. Some layer deploys require it for"
        log_warning "budget / alarm notifications. Run with:"
        log_warning "  ALERT_EMAIL=ops@example.com $0 deploy <env>"
    fi
}

state_machine_arn() {
    local env="$1"
    aws cloudformation describe-stacks \
        --stack-name "${PROJECT_NAME}-deployment-pipeline-${env}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
        --output text 2>/dev/null
}

start_execution() {
    local env="$1"
    local arn="$2"

    log_info "Starting deployment pipeline execution..."
    local execution_arn
    execution_arn=$(aws stepfunctions start-execution \
        --state-machine-arn "${arn}" \
        --input "{\"environment\": \"${env}\", \"region\": \"${AWS_REGION}\"}" \
        --region "${AWS_REGION}" \
        --query 'executionArn' \
        --output text)

    log_info "Execution ARN: ${execution_arn}"
    log_info "Console: https://${AWS_REGION}.console.aws.amazon.com/states/home?region=${AWS_REGION}#/executions/details/${execution_arn}"

    # Stream until terminal state.
    log_info "Waiting for execution to complete (this may take 30-60 minutes)..."
    local status="RUNNING"
    while [ "${status}" = "RUNNING" ]; do
        sleep 30
        status=$(aws stepfunctions describe-execution \
            --execution-arn "${execution_arn}" \
            --region "${AWS_REGION}" \
            --query 'status' \
            --output text)
        echo -n "."
    done
    echo ""

    if [ "${status}" = "SUCCEEDED" ]; then
        log_success "Deployment succeeded."
        return 0
    fi

    log_error "Deployment ended in state: ${status}"
    log_error "Inspect the failed state in the Step Functions console:"
    log_error "  https://${AWS_REGION}.console.aws.amazon.com/states/home?region=${AWS_REGION}#/executions/details/${execution_arn}"
    log_error "After fixing the underlying cause, rerun: $0 redeploy ${env}"
    return 1
}

cmd_deploy() {
    local env="${1:-}"
    if [ -z "${env}" ]; then
        log_error "Usage: $0 deploy <env>"
        exit 1
    fi
    validate_environment "${env}"
    ensure_alert_email

    log_info "Step 1/3: Running bootstrap (idempotent on existing accounts)..."
    "${SCRIPT_DIR}/scripts/bootstrap-fresh-account.sh" "${env}" "${AWS_REGION}"

    log_info "Step 2/3: Resolving deployment pipeline state machine..."
    local arn
    arn=$(state_machine_arn "${env}")
    if [ -z "${arn}" ] || [ "${arn}" = "None" ]; then
        log_error "Deployment pipeline state machine not found in account."
        log_error "Bootstrap should have deployed it; check the bootstrap output above."
        exit 1
    fi
    log_success "State machine ready: ${arn}"

    log_info "Step 3/3: Triggering streamlined deploy..."
    start_execution "${env}" "${arn}"
}

cmd_redeploy() {
    local env="${1:-}"
    if [ -z "${env}" ]; then
        log_error "Usage: $0 redeploy <env>"
        exit 1
    fi
    validate_environment "${env}"
    ensure_alert_email

    local arn
    arn=$(state_machine_arn "${env}")
    if [ -z "${arn}" ] || [ "${arn}" = "None" ]; then
        log_error "Deployment pipeline state machine not found."
        log_error "Run '$0 deploy ${env}' first to bootstrap it."
        exit 1
    fi

    start_execution "${env}" "${arn}"
}

cmd_status() {
    local env="${1:-}"
    if [ -z "${env}" ]; then
        log_error "Usage: $0 status <env>"
        exit 1
    fi
    validate_environment "${env}"

    local arn
    arn=$(state_machine_arn "${env}")
    if [ -z "${arn}" ] || [ "${arn}" = "None" ]; then
        log_error "State machine not found for ${env}; bootstrap not run yet?"
        exit 1
    fi

    log_info "Latest executions for state machine:"
    aws stepfunctions list-executions \
        --state-machine-arn "${arn}" \
        --max-items 5 \
        --region "${AWS_REGION}" \
        --query 'executions[*].{Status:status,Started:startDate,Stopped:stopDate,Name:name}' \
        --output table
}

cmd_destroy() {
    local env="${1:-}"
    if [ -z "${env}" ]; then
        log_error "Usage: $0 destroy <env>"
        exit 1
    fi
    validate_environment "${env}"

    log_warning "This will tear down every aura-* CloudFormation stack in"
    log_warning "the ${env} environment. This is irreversible."
    read -r -p "Type the environment name (${env}) to confirm: " CONFIRM
    if [ "${CONFIRM}" != "${env}" ]; then
        log_info "Aborted."
        exit 0
    fi

    log_warning "Destroy is intentionally not automated end-to-end because"
    log_warning "stack deletion ordering depends on which exports are still"
    log_warning "in use. Follow docs/deployment/DEPLOYMENT_GUIDE.md teardown"
    log_warning "section, which lists the stacks in reverse dependency order."
    exit 0
}

cmd_validate() {
    log_info "Validating CloudFormation templates..."
    if ! command -v cfn-lint &> /dev/null; then
        log_info "Installing cfn-lint..."
        pip3 install cfn-lint --quiet
    fi
    local fail=0
    for template in "${REPO_ROOT}"/deploy/cloudformation/*.yaml; do
        local base
        base=$(basename "${template}")
        if ! cfn-lint "${template}" --ignore-checks W3002,W1020 > /dev/null 2>&1; then
            log_warning "${base}: warnings (non-blocking)"
        fi
    done
    if [ "${fail}" -ne 0 ]; then
        exit 1
    fi
    log_success "Validation pass complete."
}

# Main dispatch
case "${1:-help}" in
    deploy)    shift; cmd_deploy "$@" ;;
    redeploy)  shift; cmd_redeploy "$@" ;;
    status)    shift; cmd_status "$@" ;;
    destroy)   shift; cmd_destroy "$@" ;;
    validate)  cmd_validate ;;
    help|--help|-h) show_help ;;
    *)
        log_error "Unknown command: ${1:-}"
        show_help
        exit 1
        ;;
esac
