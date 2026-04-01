#!/bin/bash

################################################################################
# Aura Infrastructure Deployment Script
#
# This script automates the deployment of Aura infrastructure to AWS using
# CloudFormation templates and CodeBuild for CI/CD.
#
# Usage:
#   ./deploy.sh [command] [options]
#
# Commands:
#   init        - Initial setup (CodeBuild + S3 artifacts bucket)
#   deploy      - Deploy/update main infrastructure
#   validate    - Validate CloudFormation templates
#   status      - Check deployment status
#   outputs     - Display stack outputs
#   destroy     - Tear down infrastructure
#   help        - Show this help message
################################################################################

set -e  # Exit on error

# Configuration
ENVIRONMENT="${ENVIRONMENT:-dev}"
PROJECT_NAME="${PROJECT_NAME:-aura}"
AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${PROJECT_NAME}-${ENVIRONMENT}"
CODEBUILD_STACK_NAME="${PROJECT_NAME}-codebuild-${ENVIRONMENT}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
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

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install it first."
        exit 1
    fi

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found. Please install it first."
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi

    log_success "Prerequisites check passed"
}

validate_templates() {
    log_info "Validating CloudFormation templates..."

    # Install cfn-lint if needed
    if ! command -v cfn-lint &> /dev/null; then
        log_info "Installing cfn-lint..."
        pip3 install cfn-lint --quiet
    fi

    # Validate all templates
    for template in deploy/cloudformation/*.yaml; do
        log_info "Validating $(basename "$template")..."
        cfn-lint "$template" --ignore-checks W3002 || {
            log_error "Validation failed for $template"
            exit 1
        }
    done

    log_success "All templates validated successfully"
}

init_infrastructure() {
    log_info "Initializing infrastructure..."

    check_prerequisites

    # Get alert email
    if [ -z "$ALERT_EMAIL" ]; then
        read -p "Enter alert email address: " ALERT_EMAIL
    fi

    # Get AWS account ID
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

    # Deploy CodeBuild stack
    log_info "Deploying CodeBuild pipeline..."
    aws cloudformation create-stack \
        --stack-name "$CODEBUILD_STACK_NAME" \
        --template-body file://deploy/cloudformation/codebuild.yaml \
        --parameters \
            ParameterKey=Environment,ParameterValue="$ENVIRONMENT" \
            ParameterKey=ProjectName,ParameterValue="$PROJECT_NAME" \
            ParameterKey=AlertEmail,ParameterValue="$ALERT_EMAIL" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$AWS_REGION" \
        --tags \
            Key=Project,Value="$PROJECT_NAME" \
            Key=Environment,Value="$ENVIRONMENT" \
            Key=ManagedBy,Value=Script

    log_info "Waiting for CodeBuild stack creation..."
    aws cloudformation wait stack-create-complete \
        --stack-name "$CODEBUILD_STACK_NAME" \
        --region "$AWS_REGION"

    log_success "CodeBuild pipeline deployed successfully"

    # Create S3 artifacts bucket
    ARTIFACT_BUCKET="${PROJECT_NAME}-cfn-artifacts-${AWS_ACCOUNT_ID}-${ENVIRONMENT}"

    log_info "Creating S3 artifacts bucket: $ARTIFACT_BUCKET"
    if ! aws s3 ls "s3://${ARTIFACT_BUCKET}" 2>/dev/null; then
        aws s3 mb "s3://${ARTIFACT_BUCKET}" --region "$AWS_REGION"

        # Configure encryption
        aws s3api put-bucket-encryption \
            --bucket "${ARTIFACT_BUCKET}" \
            --server-side-encryption-configuration \
                '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

        # Block public access
        aws s3api put-public-access-block \
            --bucket "${ARTIFACT_BUCKET}" \
            --public-access-block-configuration \
                "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

        log_success "Artifacts bucket created"
    else
        log_warning "Artifacts bucket already exists"
    fi

    # Upload templates
    log_info "Uploading nested templates to S3..."
    aws s3 sync deploy/cloudformation/ "s3://${ARTIFACT_BUCKET}/cloudformation/" \
        --exclude "master-stack.yaml" \
        --exclude "codebuild.yaml" \
        --region "$AWS_REGION"

    log_success "Initialization complete!"
    log_info "Next step: Run './deploy.sh deploy' to deploy infrastructure"
}

deploy_infrastructure() {
    log_info "Deploying infrastructure..."

    check_prerequisites

    # Get alert email
    if [ -z "$ALERT_EMAIL" ]; then
        read -p "Enter alert email address: " ALERT_EMAIL
    fi

    # Get AWS account ID
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    ARTIFACT_BUCKET="${PROJECT_NAME}-cfn-artifacts-${AWS_ACCOUNT_ID}-${ENVIRONMENT}"

    # Upload latest templates
    log_info "Uploading latest templates to S3..."
    aws s3 sync deploy/cloudformation/ "s3://${ARTIFACT_BUCKET}/cloudformation/" \
        --exclude "master-stack.yaml" \
        --exclude "codebuild.yaml" \
        --region "$AWS_REGION"

    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" &>/dev/null; then
        log_info "Stack exists, updating..."
        OPERATION="update-stack"
        WAIT_CONDITION="stack-update-complete"
    else
        log_info "Stack does not exist, creating..."
        OPERATION="create-stack"
        WAIT_CONDITION="stack-create-complete"
    fi

    # Deploy stack
    log_info "Deploying CloudFormation stack: $STACK_NAME"
    aws cloudformation "$OPERATION" \
        --stack-name "$STACK_NAME" \
        --template-body file://deploy/cloudformation/master-stack.yaml \
        --parameters \
            ParameterKey=Environment,ParameterValue="$ENVIRONMENT" \
            ParameterKey=ProjectName,ParameterValue="$PROJECT_NAME" \
            ParameterKey=AlertEmail,ParameterValue="$ALERT_EMAIL" \
            ParameterKey=VpcCIDR,ParameterValue=10.0.0.0/16 \
            ParameterKey=AvailabilityZones,ParameterValue="us-east-1a,us-east-1b" \
            ParameterKey=EKSNodeInstanceType,ParameterValue=t3.medium \
            ParameterKey=EKSNodeGroupMinSize,ParameterValue=2 \
            ParameterKey=EKSNodeGroupMaxSize,ParameterValue=5 \
            ParameterKey=NeptuneInstanceType,ParameterValue=db.t3.medium \
            ParameterKey=OpenSearchInstanceType,ParameterValue=t3.small.search \
            ParameterKey=DailyBudget,ParameterValue=15 \
            ParameterKey=MonthlyBudget,ParameterValue=400 \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$AWS_REGION" \
        --tags \
            Key=Project,Value="$PROJECT_NAME" \
            Key=Environment,Value="$ENVIRONMENT" \
            Key=ManagedBy,Value=Script

    log_info "Waiting for stack operation to complete (this may take 30-45 minutes)..."
    aws cloudformation wait "$WAIT_CONDITION" \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION"

    log_success "Infrastructure deployed successfully!"

    # Show outputs
    show_outputs
}

show_status() {
    log_info "Checking stack status..."

    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].[StackName,StackStatus,CreationTime,LastUpdatedTime]' \
        --output table \
        --region "$AWS_REGION"
}

show_outputs() {
    log_info "Stack outputs:"

    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].Outputs' \
        --output table \
        --region "$AWS_REGION"
}

destroy_infrastructure() {
    log_warning "This will DELETE all infrastructure!"
    read -p "Are you sure? Type 'yes' to confirm: " CONFIRM

    if [ "$CONFIRM" != "yes" ]; then
        log_info "Aborted"
        exit 0
    fi

    log_info "Deleting infrastructure stack..."
    aws cloudformation delete-stack \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION"

    log_info "Waiting for stack deletion..."
    aws cloudformation wait stack-delete-complete \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION"

    log_success "Infrastructure deleted"

    # Optionally delete CodeBuild stack
    read -p "Delete CodeBuild pipeline? (y/n): " DELETE_CODEBUILD
    if [ "$DELETE_CODEBUILD" = "y" ]; then
        log_info "Deleting CodeBuild stack..."
        aws cloudformation delete-stack \
            --stack-name "$CODEBUILD_STACK_NAME" \
            --region "$AWS_REGION"

        aws cloudformation wait stack-delete-complete \
            --stack-name "$CODEBUILD_STACK_NAME" \
            --region "$AWS_REGION"

        log_success "CodeBuild stack deleted"
    fi

    log_warning "Note: S3 buckets must be manually deleted after emptying them"
}

show_help() {
    cat << EOF
Aura Infrastructure Deployment Script

Usage:
    ./deploy.sh [command] [options]

Commands:
    init        - Initial setup (CodeBuild + S3 artifacts bucket)
    deploy      - Deploy/update main infrastructure
    validate    - Validate CloudFormation templates
    status      - Check deployment status
    outputs     - Display stack outputs
    destroy     - Tear down infrastructure
    help        - Show this help message

Environment Variables:
    ENVIRONMENT     - Environment name (default: dev)
    PROJECT_NAME    - Project name (default: aura)
    AWS_REGION      - AWS region (default: us-east-1)
    ALERT_EMAIL     - Email for alerts (required)

Examples:
    # Initial setup
    ALERT_EMAIL=you@example.com ./deploy.sh init

    # Deploy infrastructure
    ALERT_EMAIL=you@example.com ./deploy.sh deploy

    # Check status
    ./deploy.sh status

    # View outputs
    ./deploy.sh outputs

    # Validate templates
    ./deploy.sh validate
EOF
}

# Main script
case "$1" in
    init)
        init_infrastructure
        ;;
    deploy)
        deploy_infrastructure
        ;;
    validate)
        validate_templates
        ;;
    status)
        show_status
        ;;
    outputs)
        show_outputs
        ;;
    destroy)
        destroy_infrastructure
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
