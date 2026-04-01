#!/bin/bash

################################################################################
# Project Aura - Deploy Network Services (dnsmasq)
#
# Purpose: Automated deployment script for dnsmasq network services
#
# Usage:
#   ./deploy-network-services.sh <environment> [tier]
#
# Arguments:
#   environment: dev, qa, or prod
#   tier: 1 (kubernetes), 2 (fargate), or all (default)
#
# Examples:
#   ./deploy-network-services.sh dev           # Deploy all tiers to dev
#   ./deploy-network-services.sh prod 1        # Deploy only K8s to prod
#   ./deploy-network-services.sh qa 2          # Deploy only Fargate to qa
#
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

################################################################################
# FUNCTIONS
################################################################################

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

    # Check kubectl for Tier 1
    if ! command -v kubectl &> /dev/null; then
        log_warning "kubectl not found. Tier 1 deployment will be skipped."
    else
        log_success "kubectl found: $(kubectl version --client --short 2>/dev/null || kubectl version --client)"
    fi

    # Check AWS CLI for Tier 2
    if ! command -v aws &> /dev/null; then
        log_warning "AWS CLI not found. Tier 2 deployment will be skipped."
    else
        log_success "AWS CLI found: $(aws --version)"
    fi

    # Check Docker for local testing
    if ! command -v docker &> /dev/null; then
        log_warning "Docker not found. Local testing will not be available."
    else
        log_success "Docker found: $(docker --version)"
    fi
}

deploy_tier1_kubernetes() {
    local environment=$1

    log_info "Deploying Tier 1: Kubernetes DaemonSet for $environment..."

    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Cannot deploy Tier 1."
        return 1
    fi

    # Check if EKS cluster is accessible
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot access Kubernetes cluster. Configure kubectl first."
        return 1
    fi

    local manifest="$PROJECT_ROOT/deploy/kubernetes/dnsmasq-daemonset.yaml"

    if [ ! -f "$manifest" ]; then
        log_error "Kubernetes manifest not found: $manifest"
        return 1
    fi

    # Deploy to cluster
    log_info "Applying Kubernetes manifest..."
    kubectl apply -f "$manifest"

    # Wait for DaemonSet to be ready
    log_info "Waiting for DaemonSet to be ready..."
    kubectl rollout status daemonset/dnsmasq -n aura-network-services --timeout=5m

    # Verify pods are running
    log_info "Verifying pods..."
    kubectl get pods -n aura-network-services -l app=dnsmasq

    log_success "Tier 1 (Kubernetes DaemonSet) deployed successfully!"

    # Test DNS resolution
    log_info "Testing DNS resolution..."
    POD=$(kubectl get pod -n aura-network-services -l app=dnsmasq -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [ -n "$POD" ]; then
        log_info "Testing DNS query from pod: $POD"
        kubectl exec -it "$POD" -n aura-network-services -- nslookup -port=5353 google.com 127.0.0.1 || true
    fi

    log_info "View logs with: kubectl logs -n aura-network-services -l app=dnsmasq --tail=100"
}

deploy_tier2_fargate() {
    local environment=$1

    log_info "Deploying Tier 2: Fargate Network Services for $environment..."

    # Check if AWS CLI is available
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Cannot deploy Tier 2."
        return 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure' first."
        return 1
    fi

    local template="$PROJECT_ROOT/deploy/cloudformation/network-services.yaml"

    if [ ! -f "$template" ]; then
        log_error "CloudFormation template not found: $template"
        return 1
    fi

    # Get VPC information
    log_info "Detecting VPC configuration..."

    # Try to find VPC tagged with project name
    local vpc_id=$(aws ec2 describe-vpcs \
        --filters "Name=tag:Project,Values=aura" "Name=tag:Environment,Values=$environment" \
        --query "Vpcs[0].VpcId" \
        --output text 2>/dev/null || echo "")

    if [ -z "$vpc_id" ] || [ "$vpc_id" == "None" ]; then
        log_warning "No VPC found for project=aura, environment=$environment"
        log_info "Please provide VPC ID manually or deploy VPC stack first."
        return 1
    fi

    log_success "Found VPC: $vpc_id"

    # Get private subnets
    local subnets=$(aws ec2 describe-subnets \
        --filters "Name=vpc-id,Values=$vpc_id" "Name=tag:Type,Values=private" \
        --query "Subnets[*].SubnetId" \
        --output text 2>/dev/null || echo "")

    if [ -z "$subnets" ]; then
        log_error "No private subnets found in VPC $vpc_id"
        return 1
    fi

    local subnet_array=($subnets)
    local subnet1="${subnet_array[0]}"
    local subnet2="${subnet_array[1]:-$subnet1}"

    log_info "Using subnets: $subnet1, $subnet2"

    # Get VPC CIDR
    local vpc_cidr=$(aws ec2 describe-vpcs \
        --vpc-ids "$vpc_id" \
        --query "Vpcs[0].CidrBlock" \
        --output text)

    log_info "VPC CIDR: $vpc_cidr"

    # Stack name
    local stack_name="aura-network-services-$environment"

    # Check if stack already exists
    if aws cloudformation describe-stacks --stack-name "$stack_name" &> /dev/null; then
        log_info "Stack already exists. Updating..."

        aws cloudformation update-stack \
            --stack-name "$stack_name" \
            --template-body "file://$template" \
            --parameters \
                ParameterKey=Environment,ParameterValue="$environment" \
                ParameterKey=ProjectName,ParameterValue=aura \
                ParameterKey=VpcId,ParameterValue="$vpc_id" \
                ParameterKey=PrivateSubnet1Id,ParameterValue="$subnet1" \
                ParameterKey=PrivateSubnet2Id,ParameterValue="$subnet2" \
                ParameterKey=VpcCidr,ParameterValue="$vpc_cidr" \
            --capabilities CAPABILITY_NAMED_IAM

        log_info "Waiting for stack update to complete..."
        aws cloudformation wait stack-update-complete --stack-name "$stack_name"
    else
        log_info "Creating new stack..."

        aws cloudformation create-stack \
            --stack-name "$stack_name" \
            --template-body "file://$template" \
            --parameters \
                ParameterKey=Environment,ParameterValue="$environment" \
                ParameterKey=ProjectName,ParameterValue=aura \
                ParameterKey=VpcId,ParameterValue="$vpc_id" \
                ParameterKey=PrivateSubnet1Id,ParameterValue="$subnet1" \
                ParameterKey=PrivateSubnet2Id,ParameterValue="$subnet2" \
                ParameterKey=VpcCidr,ParameterValue="$vpc_cidr" \
            --capabilities CAPABILITY_NAMED_IAM

        log_info "Waiting for stack creation to complete (this may take 5-10 minutes)..."
        aws cloudformation wait stack-create-complete --stack-name "$stack_name"
    fi

    log_success "Tier 2 (Fargate) deployed successfully!"

    # Get DNS endpoint
    local dns_endpoint=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerDnsName'].OutputValue" \
        --output text)

    log_success "DNS Server Endpoint: $dns_endpoint"
    log_info "Test with: dig @$dns_endpoint neptune.aura.local"
}

################################################################################
# MAIN
################################################################################

main() {
    local environment="${1:-}"
    local tier="${2:-all}"

    # Validate arguments
    if [ -z "$environment" ]; then
        log_error "Usage: $0 <environment> [tier]"
        log_error "  environment: dev, qa, or prod"
        log_error "  tier: 1 (kubernetes), 2 (fargate), or all (default)"
        exit 1
    fi

    if [[ ! "$environment" =~ ^(dev|qa|prod)$ ]]; then
        log_error "Invalid environment: $environment"
        log_error "Must be one of: dev, qa, prod"
        exit 1
    fi

    if [[ ! "$tier" =~ ^(1|2|all)$ ]]; then
        log_error "Invalid tier: $tier"
        log_error "Must be one of: 1 (kubernetes), 2 (fargate), all"
        exit 1
    fi

    log_info "========================================="
    log_info "Project Aura - Network Services Deployment"
    log_info "Environment: $environment"
    log_info "Tier: $tier"
    log_info "========================================="
    echo

    # Check prerequisites
    check_prerequisites
    echo

    # Deploy based on tier selection
    if [ "$tier" == "1" ] || [ "$tier" == "all" ]; then
        deploy_tier1_kubernetes "$environment" || log_warning "Tier 1 deployment failed or skipped"
        echo
    fi

    if [ "$tier" == "2" ] || [ "$tier" == "all" ]; then
        deploy_tier2_fargate "$environment" || log_warning "Tier 2 deployment failed or skipped"
        echo
    fi

    log_success "========================================="
    log_success "Deployment complete!"
    log_success "========================================="
    echo
    log_info "Next steps:"
    log_info "1. Verify services are running"
    log_info "2. Update application configurations to use .aura.local domains"
    log_info "3. Test DNS resolution from application pods"
    log_info "4. Monitor logs for any issues"
    echo
    log_info "Documentation: docs/dnsmasq_integration.md"
}

# Run main function
main "$@"
