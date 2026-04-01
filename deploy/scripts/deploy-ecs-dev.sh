#!/usr/bin/env bash
#
# Project Aura - Deploy ECS Dev Environment
#
# Deploys ECS Fargate cluster and services for dev environment
#
# Usage:
#   ./deploy-ecs-dev.sh [OPTIONS]
#
# Options:
#   --region REGION          AWS region (default: us-east-1)
#   --environment ENV        Environment name (default: dev)
#   --vpc-id VPC_ID          VPC ID (default: vpc-0123456789abcdef0)
#   --subnet1 SUBNET_ID      First private subnet ID
#   --subnet2 SUBNET_ID      Second private subnet ID
#   --ecr-repo ECR_URI       ECR repository URI for container images
#   --image-tag TAG          Docker image tag (default: latest)
#   --dry-run                Show what would be deployed without deploying
#   --help                   Show this help message
#
# Example:
#   ./deploy-ecs-dev.sh --region us-east-1 --environment dev \
#     --subnet1 subnet-abc123 --subnet2 subnet-def456 \
#     --ecr-repo 123456789012.dkr.ecr.us-east-1.amazonaws.com/aura

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ENVIRONMENT="dev"
VPC_ID="${VPC_ID:-vpc-0123456789abcdef0}"
SUBNET1=""
SUBNET2=""
ECR_REPO=""
IMAGE_TAG="latest"
DRY_RUN=false

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CFN_DIR="$PROJECT_ROOT/deploy/cloudformation"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --region)
            REGION="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --vpc-id)
            VPC_ID="$2"
            shift 2
            ;;
        --subnet1)
            SUBNET1="$2"
            shift 2
            ;;
        --subnet2)
            SUBNET2="$2"
            shift 2
            ;;
        --ecr-repo)
            ECR_REPO="$2"
            shift 2
            ;;
        --image-tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            grep '^#' "$0" | grep -v '#!/usr/bin/env' | sed 's/^# *//'
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
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

    # Check AWS credentials
    if ! aws sts get-caller-identity --region "$REGION" &> /dev/null; then
        log_error "AWS credentials not configured or invalid"
        exit 1
    fi

    # Check VPC exists
    if ! aws ec2 describe-vpcs --vpc-ids "$VPC_ID" --region "$REGION" &> /dev/null; then
        log_error "VPC $VPC_ID not found in region $REGION"
        exit 1
    fi

    log_info "Prerequisites check passed"
}

get_subnets() {
    log_info "Finding private subnets in VPC $VPC_ID..."

    if [[ -z "$SUBNET1" || -z "$SUBNET2" ]]; then
        # Auto-discover private subnets
        SUBNETS=$(aws ec2 describe-subnets \
            --region "$REGION" \
            --filters "Name=vpc-id,Values=$VPC_ID" "Name=tag:Type,Values=private" \
            --query 'Subnets[*].SubnetId' \
            --output text)

        if [[ -z "$SUBNETS" ]]; then
            log_error "No private subnets found in VPC $VPC_ID"
            exit 1
        fi

        read -r SUBNET1 SUBNET2 <<< "$SUBNETS"
    fi

    log_info "Using subnets: $SUBNET1, $SUBNET2"
}

deploy_cluster_stack() {
    local STACK_NAME="aura-ecs-${ENVIRONMENT}-cluster"

    log_info "Deploying ECS cluster stack: $STACK_NAME"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "DRY RUN: Would deploy $STACK_NAME with parameters:"
        echo "  VpcId=$VPC_ID"
        echo "  PrivateSubnet1=$SUBNET1"
        echo "  PrivateSubnet2=$SUBNET2"
        echo "  Environment=$ENVIRONMENT"
        return
    fi

    aws cloudformation deploy \
        --region "$REGION" \
        --template-file "$CFN_DIR/ecs-dev-cluster.yaml" \
        --stack-name "$STACK_NAME" \
        --parameter-overrides \
            VpcId="$VPC_ID" \
            PrivateSubnet1="$SUBNET1" \
            PrivateSubnet2="$SUBNET2" \
            Environment="$ENVIRONMENT" \
        --capabilities CAPABILITY_NAMED_IAM \
        --tags \
            Project=ProjectAura \
            Environment="$ENVIRONMENT" \
            ManagedBy=CloudFormation

    log_info "Cluster stack deployed successfully"
}

build_and_push_images() {
    if [[ -z "$ECR_REPO" ]]; then
        log_warn "ECR repository not specified, skipping image build"
        return
    fi

    log_info "Building and pushing container images..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "DRY RUN: Would build and push images to $ECR_REPO:$IMAGE_TAG"
        return
    fi

    # Login to ECR
    aws ecr get-login-password --region "$REGION" | \
        docker login --username AWS --password-stdin "${ECR_REPO%%/*}"

    # Build dnsmasq image
    log_info "Building dnsmasq image..."
    docker build \
        -t "$ECR_REPO/dnsmasq:$IMAGE_TAG" \
        -f "$PROJECT_ROOT/deploy/docker/dnsmasq/Dockerfile" \
        "$PROJECT_ROOT"
    docker push "$ECR_REPO/dnsmasq:$IMAGE_TAG"

    # Build orchestrator image
    log_info "Building orchestrator image..."
    docker build \
        -t "$ECR_REPO/agent-orchestrator:$IMAGE_TAG" \
        -f "$PROJECT_ROOT/deploy/docker/agents/Dockerfile.orchestrator" \
        "$PROJECT_ROOT"
    docker push "$ECR_REPO/agent-orchestrator:$IMAGE_TAG"

    # Build coder agent
    log_info "Building coder agent image..."
    docker build \
        --build-arg AGENT_TYPE=coder \
        -t "$ECR_REPO/coder-agent:$IMAGE_TAG" \
        -f "$PROJECT_ROOT/deploy/docker/agents/Dockerfile.agent" \
        "$PROJECT_ROOT"
    docker push "$ECR_REPO/coder-agent:$IMAGE_TAG"

    # Build reviewer agent
    log_info "Building reviewer agent image..."
    docker build \
        --build-arg AGENT_TYPE=reviewer \
        -t "$ECR_REPO/reviewer-agent:$IMAGE_TAG" \
        -f "$PROJECT_ROOT/deploy/docker/agents/Dockerfile.agent" \
        "$PROJECT_ROOT"
    docker push "$ECR_REPO/reviewer-agent:$IMAGE_TAG"

    # Build validator agent
    log_info "Building validator agent image..."
    docker build \
        --build-arg AGENT_TYPE=validator \
        -t "$ECR_REPO/validator-agent:$IMAGE_TAG" \
        -f "$PROJECT_ROOT/deploy/docker/agents/Dockerfile.agent" \
        "$PROJECT_ROOT"
    docker push "$ECR_REPO/validator-agent:$IMAGE_TAG"

    log_info "All images built and pushed successfully"
}

deploy_services_stack() {
    local STACK_NAME="aura-ecs-${ENVIRONMENT}-services"
    local CLUSTER_STACK="aura-ecs-${ENVIRONMENT}-cluster"

    log_info "Deploying ECS services stack: $STACK_NAME"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "DRY RUN: Would deploy $STACK_NAME"
        return
    fi

    aws cloudformation deploy \
        --region "$REGION" \
        --template-file "$CFN_DIR/ecs-dev-services.yaml" \
        --stack-name "$STACK_NAME" \
        --parameter-overrides \
            ClusterStackName="$CLUSTER_STACK" \
            PrivateSubnet1="$SUBNET1" \
            PrivateSubnet2="$SUBNET2" \
            ECRRepositoryURI="$ECR_REPO" \
            ImageTag="$IMAGE_TAG" \
            Environment="$ENVIRONMENT" \
        --capabilities CAPABILITY_IAM \
        --tags \
            Project=ProjectAura \
            Environment="$ENVIRONMENT" \
            ManagedBy=CloudFormation

    log_info "Services stack deployed successfully"
}

deploy_scheduled_scaling() {
    local STACK_NAME="aura-ecs-${ENVIRONMENT}-scheduled-scaling"

    log_info "Deploying scheduled scaling stack: $STACK_NAME"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "DRY RUN: Would deploy $STACK_NAME"
        return
    fi

    aws cloudformation deploy \
        --region "$REGION" \
        --template-file "$CFN_DIR/ecs-scheduled-scaling.yaml" \
        --stack-name "$STACK_NAME" \
        --parameter-overrides \
            Environment="$ENVIRONMENT" \
            ScaleDownSchedule="cron(0 18 ? * MON-FRI *)" \
            ScaleUpSchedule="cron(0 8 ? * MON-FRI *)" \
        --capabilities CAPABILITY_NAMED_IAM \
        --tags \
            Project=ProjectAura \
            Environment="$ENVIRONMENT" \
            ManagedBy=CloudFormation

    log_info "Scheduled scaling deployed successfully"
}

print_summary() {
    log_info "==================================="
    log_info "Deployment Summary"
    log_info "==================================="
    echo "Environment: $ENVIRONMENT"
    echo "Region: $REGION"
    echo "VPC: $VPC_ID"
    echo "Subnets: $SUBNET1, $SUBNET2"
    echo "Image Tag: $IMAGE_TAG"
    echo ""
    log_info "ECS Cluster: aura-${ENVIRONMENT}-cluster"
    log_info "Services deployed:"
    echo "  - dnsmasq-${ENVIRONMENT}"
    echo "  - orchestrator-${ENVIRONMENT}"
    echo "  - coder-agent-${ENVIRONMENT}"
    echo "  - reviewer-agent-${ENVIRONMENT}"
    echo "  - validator-agent-${ENVIRONMENT}"
    echo ""
    log_info "Scheduled scaling: 8am-6pm weekdays (scale to 0 after hours)"
    log_info "==================================="
}

# Main execution
main() {
    log_info "Starting ECS dev environment deployment"
    log_info "Environment: $ENVIRONMENT, Region: $REGION"

    check_prerequisites
    get_subnets
    deploy_cluster_stack
    build_and_push_images
    deploy_services_stack
    deploy_scheduled_scaling
    print_summary

    log_info "Deployment complete!"
}

# Run main
main
