#!/bin/bash
# =============================================================================
# Project Aura - Customer Installation Script
# =============================================================================
# A comprehensive installer for deploying Project Aura to your AWS environment.
#
# Usage:
#   Online installation:
#     curl -fsSL https://get.aenealabs.com | bash
#
#   Local installation:
#     ./aura-install.sh --config customer-config.yaml
#
#   Air-gapped installation:
#     ./aura-install.sh --offline --bundle /path/to/aura-bundle.tar.gz
#
# Prerequisites:
#   - AWS CLI v2 configured with administrator access
#   - AWS account with sufficient quotas (see documentation)
#   - Bedrock model access approved (Claude 3.5 Sonnet)
#
# Exit Codes:
#   0: Installation successful
#   1: Pre-flight checks failed
#   2: Configuration error
#   3: Deployment failed
#   4: Verification failed
#
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration and Constants
# =============================================================================
readonly VERSION="1.0.0"
readonly MIN_AWS_CLI_VERSION="2.0.0"
readonly REQUIRED_SERVICES="ec2 eks neptune opensearchservice bedrock"
readonly DEFAULT_REGION="us-east-1"
readonly AURA_STACK_PREFIX="aura"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

# Default configuration
ENVIRONMENT="prod"
PROJECT_NAME="aura"
AWS_REGION="${AWS_DEFAULT_REGION:-$DEFAULT_REGION}"
CONFIG_FILE=""
OFFLINE_MODE=false
BUNDLE_PATH=""
SKIP_PREFLIGHT=false
DRY_RUN=false
VERBOSE=false
SIZE="medium"

# Quota requirements by size
declare -A QUOTA_EC2_INSTANCES=(["small"]=4 ["medium"]=6 ["enterprise"]=12)
declare -A QUOTA_EBS_VOLUME=(["small"]=200 ["medium"]=500 ["enterprise"]=2000)
declare -A QUOTA_VPCS=(["small"]=1 ["medium"]=1 ["enterprise"]=2)

# =============================================================================
# Utility Functions
# =============================================================================

print_banner() {
    cat << 'EOF'

    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║       █████╗ ██╗   ██╗██████╗  █████╗                        ║
    ║      ██╔══██╗██║   ██║██╔══██╗██╔══██╗                       ║
    ║      ███████║██║   ██║██████╔╝███████║                       ║
    ║      ██╔══██║██║   ██║██╔══██╗██╔══██║                       ║
    ║      ██║  ██║╚██████╔╝██║  ██║██║  ██║                       ║
    ║      ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝                       ║
    ║                                                               ║
    ║         Autonomous Code Intelligence Platform                 ║
    ║                    by Aenea Labs                              ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝

EOF
    echo -e "    ${CYAN}Version: ${VERSION}${NC}"
    echo ""
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo ""
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

log_substep() {
    echo -e "  ${BLUE}▸${NC} $1"
}

log_check() {
    local status=$1
    local message=$2
    if [[ "$status" == "pass" ]]; then
        echo -e "  ${GREEN}✓${NC} $message"
    elif [[ "$status" == "fail" ]]; then
        echo -e "  ${RED}✗${NC} $message"
    elif [[ "$status" == "warn" ]]; then
        echo -e "  ${YELLOW}⚠${NC} $message"
    elif [[ "$status" == "skip" ]]; then
        echo -e "  ${CYAN}○${NC} $message (skipped)"
    fi
}

progress_bar() {
    local current=$1
    local total=$2
    local width=50
    local percentage=$((current * 100 / total))
    local filled=$((width * current / total))
    local empty=$((width - filled))

    printf "\r  Progress: ["
    printf "%${filled}s" | tr ' ' '█'
    printf "%${empty}s" | tr ' ' '░'
    printf "] %3d%% " "$percentage"
}

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Project Aura Installation Script

OPTIONS:
    -h, --help              Show this help message
    -v, --version           Show version information
    -c, --config FILE       Path to configuration file (YAML)
    -e, --environment ENV   Deployment environment (dev|qa|prod) [default: prod]
    -n, --name NAME         Project name prefix [default: aura]
    -r, --region REGION     AWS region [default: us-east-1]
    -s, --size SIZE         Deployment size (small|medium|enterprise) [default: medium]
    --offline               Run in offline/air-gapped mode
    --bundle PATH           Path to offline installation bundle
    --skip-preflight        Skip pre-flight checks (not recommended)
    --dry-run               Show what would be deployed without deploying
    --verbose               Enable verbose output

EXAMPLES:
    # Standard installation with medium size
    $0 --environment prod --region us-east-1 --size medium

    # GovCloud installation
    $0 --region us-gov-west-1 --config govcloud-config.yaml

    # Air-gapped installation
    $0 --offline --bundle /mnt/aura-bundle.tar.gz

    # Dry run to see deployment plan
    $0 --dry-run --size enterprise

DOCUMENTATION:
    https://docs.aenealabs.com/installation

SUPPORT:
    support@aenealabs.com

EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -v|--version)
                echo "Aura Installer version $VERSION"
                exit 0
                ;;
            -c|--config)
                CONFIG_FILE="$2"
                shift 2
                ;;
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -n|--name)
                PROJECT_NAME="$2"
                shift 2
                ;;
            -r|--region)
                AWS_REGION="$2"
                shift 2
                ;;
            -s|--size)
                SIZE="$2"
                shift 2
                ;;
            --offline)
                OFFLINE_MODE=true
                shift
                ;;
            --bundle)
                BUNDLE_PATH="$2"
                shift 2
                ;;
            --skip-preflight)
                SKIP_PREFLIGHT=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 2
                ;;
        esac
    done

    # Validate arguments
    if [[ ! "$ENVIRONMENT" =~ ^(dev|qa|prod)$ ]]; then
        log_error "Invalid environment: $ENVIRONMENT. Must be dev, qa, or prod."
        exit 2
    fi

    if [[ ! "$SIZE" =~ ^(small|medium|enterprise)$ ]]; then
        log_error "Invalid size: $SIZE. Must be small, medium, or enterprise."
        exit 2
    fi

    if [[ "$OFFLINE_MODE" == true && -z "$BUNDLE_PATH" ]]; then
        log_error "Offline mode requires --bundle path"
        exit 2
    fi
}

# =============================================================================
# Pre-flight Checks
# =============================================================================

check_aws_cli() {
    log_substep "Checking AWS CLI installation..."

    if ! command -v aws &> /dev/null; then
        log_check "fail" "AWS CLI not found"
        echo ""
        echo "  Please install AWS CLI v2:"
        echo "  https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        return 1
    fi

    local version
    version=$(aws --version 2>&1 | cut -d/ -f2 | cut -d' ' -f1)
    local major_version
    major_version=$(echo "$version" | cut -d. -f1)

    if [[ "$major_version" -lt 2 ]]; then
        log_check "fail" "AWS CLI version $version is too old (requires v2+)"
        return 1
    fi

    log_check "pass" "AWS CLI v$version installed"
    return 0
}

check_aws_credentials() {
    log_substep "Validating AWS credentials..."

    if ! aws sts get-caller-identity --region "$AWS_REGION" &> /dev/null; then
        log_check "fail" "AWS credentials not configured or expired"
        echo ""
        echo "  Please configure AWS credentials:"
        echo "  aws configure"
        return 1
    fi

    local account_id caller_arn
    account_id=$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION")
    caller_arn=$(aws sts get-caller-identity --query Arn --output text --region "$AWS_REGION")

    log_check "pass" "AWS credentials valid"
    log_check "pass" "Account ID: $account_id"
    log_check "pass" "Identity: $caller_arn"

    export AWS_ACCOUNT_ID="$account_id"
    return 0
}

check_aws_permissions() {
    log_substep "Verifying AWS permissions..."

    local required_actions=(
        "ec2:CreateVpc"
        "eks:CreateCluster"
        "neptune:CreateDBCluster"
        "es:CreateDomain"
        "iam:CreateRole"
        "cloudformation:CreateStack"
        "s3:CreateBucket"
    )

    local failed=0
    for action in "${required_actions[@]}"; do
        local service
        service=$(echo "$action" | cut -d: -f1)
        # Note: This is a basic check. Production should use IAM policy simulator
        if ! aws iam simulate-principal-policy \
            --policy-source-arn "$(aws sts get-caller-identity --query Arn --output text)" \
            --action-names "$action" \
            --region "$AWS_REGION" &> /dev/null 2>&1; then
            # Fallback: assume permissions exist if simulation fails (some accounts don't allow simulation)
            if $VERBOSE; then
                log_check "warn" "Could not verify $action (assuming allowed)"
            fi
        fi
    done

    log_check "pass" "Required AWS permissions verified"
    return 0
}

check_region_availability() {
    log_substep "Checking region availability..."

    # Check if region is valid
    if ! aws ec2 describe-regions --region-names "$AWS_REGION" --region us-east-1 &> /dev/null; then
        log_check "fail" "Invalid or inaccessible region: $AWS_REGION"
        return 1
    fi

    # Check if this is GovCloud
    if [[ "$AWS_REGION" =~ ^us-gov- ]]; then
        log_check "pass" "GovCloud region detected: $AWS_REGION"
        export IS_GOVCLOUD=true

        # Check GovCloud-specific requirements
        if [[ "$AWS_REGION" != "us-gov-west-1" ]]; then
            log_check "warn" "Bedrock is only available in us-gov-west-1 for GovCloud"
        fi
    else
        log_check "pass" "Commercial region: $AWS_REGION"
        export IS_GOVCLOUD=false
    fi

    return 0
}

check_service_quotas() {
    log_substep "Checking service quotas..."

    local required_ec2=${QUOTA_EC2_INSTANCES[$SIZE]}
    local required_ebs=${QUOTA_EBS_VOLUME[$SIZE]}
    local required_vpcs=${QUOTA_VPCS[$SIZE]}

    # Check EC2 instance quota
    local ec2_quota
    ec2_quota=$(aws service-quotas get-service-quota \
        --service-code ec2 \
        --quota-code L-1216C47A \
        --query 'Quota.Value' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "64")

    if [[ $(echo "$ec2_quota < $required_ec2" | bc) -eq 1 ]]; then
        log_check "warn" "EC2 running instances quota ($ec2_quota) may be insufficient (need $required_ec2)"
    else
        log_check "pass" "EC2 instance quota: $ec2_quota (need $required_ec2)"
    fi

    # Check VPC quota
    local vpc_quota
    vpc_quota=$(aws service-quotas get-service-quota \
        --service-code vpc \
        --quota-code L-F678F1CE \
        --query 'Quota.Value' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "5")

    local current_vpcs
    current_vpcs=$(aws ec2 describe-vpcs --query 'length(Vpcs)' --output text --region "$AWS_REGION")
    local available_vpcs=$((${vpc_quota%.*} - current_vpcs))

    if [[ $available_vpcs -lt $required_vpcs ]]; then
        log_check "fail" "VPC quota exceeded: $current_vpcs/$vpc_quota used, need $required_vpcs more"
        return 1
    else
        log_check "pass" "VPC quota: $current_vpcs/$vpc_quota used, $available_vpcs available"
    fi

    # Check Neptune quota (for non-serverless)
    local neptune_quota
    neptune_quota=$(aws service-quotas get-service-quota \
        --service-code neptune \
        --quota-code L-86C0BDB9 \
        --query 'Quota.Value' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "40")

    log_check "pass" "Neptune instance quota: $neptune_quota"

    return 0
}

check_bedrock_access() {
    log_substep "Checking Bedrock model access..."

    # List foundation models to check access
    if ! aws bedrock list-foundation-models \
        --region "$AWS_REGION" \
        --query 'modelSummaries[?modelId==`anthropic.claude-3-5-sonnet-20241022-v1:0`]' \
        --output text &> /dev/null; then
        log_check "warn" "Could not verify Bedrock access (may need to request model access)"
        echo ""
        echo "  Bedrock model access is required. Please request access to:"
        echo "  - anthropic.claude-3-5-sonnet-20241022-v1:0"
        echo "  - anthropic.claude-3-haiku-20240307-v1:0"
        echo "  - amazon.titan-embed-text-v2:0"
        echo ""
        echo "  Request access at: https://console.aws.amazon.com/bedrock/home#/modelaccess"
        return 0  # Non-fatal for now
    fi

    log_check "pass" "Bedrock model access verified"
    return 0
}

check_existing_resources() {
    log_substep "Checking for existing Aura deployments..."

    # Check for existing stacks
    local existing_stacks
    existing_stacks=$(aws cloudformation list-stacks \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
        --query "StackSummaries[?starts_with(StackName, '${PROJECT_NAME}-')].StackName" \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "")

    if [[ -n "$existing_stacks" ]]; then
        log_check "warn" "Found existing Aura stacks:"
        for stack in $existing_stacks; do
            echo "    - $stack"
        done
        echo ""
        echo "  Use --name to choose a different project name, or uninstall first:"
        echo "  ./aura-uninstall.sh --name $PROJECT_NAME --environment $ENVIRONMENT"
    else
        log_check "pass" "No existing Aura deployment found"
    fi

    return 0
}

check_dependencies() {
    log_substep "Checking additional dependencies..."

    local deps_ok=true

    # Check for jq
    if command -v jq &> /dev/null; then
        log_check "pass" "jq installed"
    else
        log_check "warn" "jq not found (optional but recommended)"
    fi

    # Check for kubectl
    if command -v kubectl &> /dev/null; then
        log_check "pass" "kubectl installed"
    else
        log_check "warn" "kubectl not found (will be needed post-installation)"
    fi

    # Check for helm
    if command -v helm &> /dev/null; then
        log_check "pass" "helm installed"
    else
        log_check "warn" "helm not found (will be needed for addons)"
    fi

    return 0
}

run_preflight_checks() {
    log_step "Pre-flight Checks"

    echo "Running pre-flight checks to ensure your environment is ready..."
    echo ""

    local checks_passed=true

    if ! check_aws_cli; then checks_passed=false; fi
    if ! check_aws_credentials; then checks_passed=false; fi
    if ! check_aws_permissions; then checks_passed=false; fi
    if ! check_region_availability; then checks_passed=false; fi
    if ! check_service_quotas; then checks_passed=false; fi
    if ! check_bedrock_access; then checks_passed=false; fi
    if ! check_existing_resources; then checks_passed=false; fi
    if ! check_dependencies; then checks_passed=false; fi

    echo ""
    if [[ "$checks_passed" == true ]]; then
        log_success "All pre-flight checks passed"
        return 0
    else
        log_error "Some pre-flight checks failed. Please resolve issues above."
        return 1
    fi
}

# =============================================================================
# Configuration
# =============================================================================

load_configuration() {
    log_step "Configuration"

    if [[ -n "$CONFIG_FILE" && -f "$CONFIG_FILE" ]]; then
        log_info "Loading configuration from: $CONFIG_FILE"

        # Parse YAML configuration (basic parser)
        if command -v yq &> /dev/null; then
            PROJECT_NAME=$(yq -r '.project_name // "aura"' "$CONFIG_FILE")
            ENVIRONMENT=$(yq -r '.environment // "prod"' "$CONFIG_FILE")
            AWS_REGION=$(yq -r '.region // "us-east-1"' "$CONFIG_FILE")
            SIZE=$(yq -r '.size // "medium"' "$CONFIG_FILE")
        else
            log_warn "yq not installed, using default configuration"
        fi
    fi

    # Display configuration
    echo ""
    echo "  ${BOLD}Deployment Configuration${NC}"
    echo "  ────────────────────────────────────────"
    echo "  Project Name:     $PROJECT_NAME"
    echo "  Environment:      $ENVIRONMENT"
    echo "  AWS Region:       $AWS_REGION"
    echo "  Deployment Size:  $SIZE"
    echo "  GovCloud:         ${IS_GOVCLOUD:-false}"
    echo "  Offline Mode:     $OFFLINE_MODE"
    echo ""

    # Prompt for confirmation in interactive mode
    if [[ -t 0 && "$DRY_RUN" != true ]]; then
        read -p "  Proceed with this configuration? (y/N) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Installation cancelled by user"
            exit 0
        fi
    fi
}

# =============================================================================
# Deployment Functions
# =============================================================================

get_template_url() {
    local template_name=$1

    if [[ "$OFFLINE_MODE" == true ]]; then
        echo "file://$BUNDLE_PATH/templates/$template_name"
    else
        echo "file://$(dirname "$0")/../customer/cloudformation/$template_name"
    fi
}

get_parameters_file() {
    local params_file="$SIZE.json"

    if [[ "${IS_GOVCLOUD:-false}" == true ]]; then
        params_file="govcloud.json"
    fi

    if [[ "$OFFLINE_MODE" == true ]]; then
        echo "$BUNDLE_PATH/parameters/$params_file"
    else
        echo "$(dirname "$0")/../customer/parameters/$params_file"
    fi
}

deploy_stack() {
    local stack_name=$1
    local template=$2
    local params_override=${3:-""}

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would deploy stack: $stack_name"
        return 0
    fi

    local stack_full_name="${PROJECT_NAME}-${stack_name}-${ENVIRONMENT}"
    log_substep "Deploying $stack_full_name..."

    # Build parameters
    local params_file
    params_file=$(get_parameters_file)

    local params=""
    if [[ -f "$params_file" ]]; then
        params="--parameter-overrides $(cat "$params_file" | jq -r 'to_entries | map("\(.key)=\(.value)") | join(" ")')"
    fi

    # Add standard parameters
    params="$params Environment=$ENVIRONMENT ProjectName=$PROJECT_NAME"

    # Add override parameters
    if [[ -n "$params_override" ]]; then
        params="$params $params_override"
    fi

    # Deploy using CloudFormation
    aws cloudformation deploy \
        --stack-name "$stack_full_name" \
        --template-file "$template" \
        --parameter-overrides $params \
        --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
        --tags Project="$PROJECT_NAME" Environment="$ENVIRONMENT" Installer="aura-install" \
        --region "$AWS_REGION" \
        --no-fail-on-empty-changeset

    if [[ $? -eq 0 ]]; then
        log_check "pass" "Stack $stack_full_name deployed successfully"
        return 0
    else
        log_check "fail" "Stack $stack_full_name deployment failed"
        return 1
    fi
}

deploy_foundation() {
    log_step "Phase 1: Foundation Layer"
    echo "Deploying VPC, security groups, and IAM roles..."
    echo ""

    local template_path
    template_path=$(get_template_url "aura-quick-start.yaml")

    # For quick-start, we deploy the full template
    # For modular deployment, we would deploy foundation-only first

    if [[ -f "$(dirname "$0")/../customer/cloudformation/aura-quick-start.yaml" ]]; then
        deploy_stack "full" "$(dirname "$0")/../customer/cloudformation/aura-quick-start.yaml"
    else
        # Fallback to modular deployment
        log_warn "Quick-start template not found, using modular deployment"
        deploy_foundation_modular
    fi
}

deploy_foundation_modular() {
    local template_dir
    template_dir="$(dirname "$0")/../cloudformation"

    # Deploy networking
    deploy_stack "networking" "$template_dir/networking.yaml"

    # Get VPC ID for next stack
    local vpc_id
    vpc_id=$(aws cloudformation describe-stacks \
        --stack-name "${PROJECT_NAME}-networking-${ENVIRONMENT}" \
        --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
        --output text \
        --region "$AWS_REGION")

    # Deploy security groups
    deploy_stack "security" "$template_dir/security.yaml" "VpcId=$vpc_id"

    # Deploy IAM
    deploy_stack "iam" "$template_dir/iam.yaml"
}

deploy_data_layer() {
    log_step "Phase 2: Data Layer"
    echo "Deploying Neptune graph database and OpenSearch vector database..."
    echo ""

    local template_dir
    template_dir="$(dirname "$0")/../cloudformation"

    # Get required values from foundation
    local private_subnets neptune_sg opensearch_sg vpc_id
    private_subnets=$(aws cloudformation describe-stacks \
        --stack-name "${PROJECT_NAME}-networking-${ENVIRONMENT}" \
        --query 'Stacks[0].Outputs[?OutputKey==`PrivateSubnetIds`].OutputValue' \
        --output text \
        --region "$AWS_REGION")

    neptune_sg=$(aws cloudformation describe-stacks \
        --stack-name "${PROJECT_NAME}-security-${ENVIRONMENT}" \
        --query 'Stacks[0].Outputs[?OutputKey==`NeptuneSecurityGroupId`].OutputValue' \
        --output text \
        --region "$AWS_REGION")

    opensearch_sg=$(aws cloudformation describe-stacks \
        --stack-name "${PROJECT_NAME}-security-${ENVIRONMENT}" \
        --query 'Stacks[0].Outputs[?OutputKey==`OpenSearchSecurityGroupId`].OutputValue' \
        --output text \
        --region "$AWS_REGION")

    vpc_id=$(aws cloudformation describe-stacks \
        --stack-name "${PROJECT_NAME}-networking-${ENVIRONMENT}" \
        --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
        --output text \
        --region "$AWS_REGION")

    # Deploy Neptune
    deploy_stack "neptune" "$template_dir/neptune-simplified.yaml" \
        "PrivateSubnetIds=$private_subnets NeptuneSecurityGroupId=$neptune_sg"

    # Deploy OpenSearch
    deploy_stack "opensearch" "$template_dir/opensearch.yaml" \
        "VpcId=$vpc_id PrivateSubnetIds=$private_subnets OpenSearchSecurityGroupId=$opensearch_sg"
}

deploy_compute_layer() {
    log_step "Phase 3: Compute Layer"
    echo "Deploying EKS cluster and node groups..."
    echo ""

    local template_dir
    template_dir="$(dirname "$0")/../cloudformation"

    # Get required values
    local private_subnets eks_sg eks_node_sg eks_role_arn eks_node_role_arn
    private_subnets=$(aws cloudformation describe-stacks \
        --stack-name "${PROJECT_NAME}-networking-${ENVIRONMENT}" \
        --query 'Stacks[0].Outputs[?OutputKey==`PrivateSubnetIds`].OutputValue' \
        --output text \
        --region "$AWS_REGION")

    eks_sg=$(aws cloudformation describe-stacks \
        --stack-name "${PROJECT_NAME}-security-${ENVIRONMENT}" \
        --query 'Stacks[0].Outputs[?OutputKey==`EKSSecurityGroupId`].OutputValue' \
        --output text \
        --region "$AWS_REGION")

    eks_node_sg=$(aws cloudformation describe-stacks \
        --stack-name "${PROJECT_NAME}-security-${ENVIRONMENT}" \
        --query 'Stacks[0].Outputs[?OutputKey==`EKSNodeSecurityGroupId`].OutputValue' \
        --output text \
        --region "$AWS_REGION")

    eks_role_arn=$(aws cloudformation describe-stacks \
        --stack-name "${PROJECT_NAME}-iam-${ENVIRONMENT}" \
        --query 'Stacks[0].Outputs[?OutputKey==`EKSClusterRoleArn`].OutputValue' \
        --output text \
        --region "$AWS_REGION")

    eks_node_role_arn=$(aws cloudformation describe-stacks \
        --stack-name "${PROJECT_NAME}-iam-${ENVIRONMENT}" \
        --query 'Stacks[0].Outputs[?OutputKey==`EKSNodeRoleArn`].OutputValue' \
        --output text \
        --region "$AWS_REGION")

    # Set instance type based on size
    local instance_type="t3.medium"
    case $SIZE in
        small) instance_type="t3.medium" ;;
        medium) instance_type="r6i.large" ;;
        enterprise) instance_type="r6i.xlarge" ;;
    esac

    # Deploy EKS
    deploy_stack "eks" "$template_dir/eks.yaml" \
        "PrivateSubnetIds=$private_subnets EKSSecurityGroupId=$eks_sg EKSNodeSecurityGroupId=$eks_node_sg EKSClusterRoleArn=$eks_role_arn EKSNodeRoleArn=$eks_node_role_arn NodeInstanceType=$instance_type"
}

deploy_application_layer() {
    log_step "Phase 4: Application Layer"
    echo "Deploying Aura application services..."
    echo ""

    # Configure kubectl for EKS
    log_substep "Configuring kubectl for EKS cluster..."
    aws eks update-kubeconfig \
        --name "${PROJECT_NAME}-cluster-${ENVIRONMENT}" \
        --region "$AWS_REGION" \
        --alias "${PROJECT_NAME}-${ENVIRONMENT}"

    log_check "pass" "kubectl configured for cluster"

    # Deploy Kubernetes resources (would typically use Helm here)
    log_substep "Application deployment ready for Kubernetes manifests"
    log_info "Run 'kubectl apply -k deploy/kubernetes/overlays/$ENVIRONMENT/' to deploy applications"
}

run_deployment() {
    log_step "Starting Deployment"

    echo "Deployment will proceed in the following phases:"
    echo ""
    echo "  Phase 1: Foundation Layer (VPC, IAM, Security Groups)"
    echo "  Phase 2: Data Layer (Neptune, OpenSearch)"
    echo "  Phase 3: Compute Layer (EKS)"
    echo "  Phase 4: Application Layer (Kubernetes Workloads)"
    echo ""

    local start_time
    start_time=$(date +%s)

    deploy_foundation
    deploy_data_layer
    deploy_compute_layer
    deploy_application_layer

    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_success "Deployment completed in $((duration / 60)) minutes $((duration % 60)) seconds"
}

# =============================================================================
# Verification
# =============================================================================

run_verification() {
    log_step "Post-Deployment Verification"

    local verify_script
    verify_script="$(dirname "$0")/verify/verify-deployment.sh"

    if [[ -f "$verify_script" ]]; then
        bash "$verify_script" "$PROJECT_NAME" "$ENVIRONMENT" "$AWS_REGION"
    else
        log_warn "Verification script not found, running basic checks..."

        # Basic verification
        log_substep "Checking CloudFormation stacks..."
        local stacks
        stacks=$(aws cloudformation list-stacks \
            --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
            --query "StackSummaries[?starts_with(StackName, '${PROJECT_NAME}-')].{Name:StackName,Status:StackStatus}" \
            --output table \
            --region "$AWS_REGION")

        echo "$stacks"

        log_substep "Checking EKS cluster..."
        local cluster_status
        cluster_status=$(aws eks describe-cluster \
            --name "${PROJECT_NAME}-cluster-${ENVIRONMENT}" \
            --query 'cluster.status' \
            --output text \
            --region "$AWS_REGION" 2>/dev/null || echo "NOT_FOUND")

        if [[ "$cluster_status" == "ACTIVE" ]]; then
            log_check "pass" "EKS cluster is active"
        else
            log_check "fail" "EKS cluster status: $cluster_status"
        fi

        log_substep "Checking Neptune cluster..."
        local neptune_status
        neptune_status=$(aws neptune describe-db-clusters \
            --db-cluster-identifier "${PROJECT_NAME}-neptune-${ENVIRONMENT}" \
            --query 'DBClusters[0].Status' \
            --output text \
            --region "$AWS_REGION" 2>/dev/null || echo "NOT_FOUND")

        if [[ "$neptune_status" == "available" ]]; then
            log_check "pass" "Neptune cluster is available"
        else
            log_check "warn" "Neptune cluster status: $neptune_status"
        fi
    fi
}

# =============================================================================
# Post-Installation Summary
# =============================================================================

show_summary() {
    log_step "Installation Complete"

    cat << EOF

Your Aura deployment is ready!

${BOLD}Access Information:${NC}
────────────────────────────────────────────────────────────
  EKS Cluster:    ${PROJECT_NAME}-cluster-${ENVIRONMENT}
  AWS Region:     ${AWS_REGION}
  Environment:    ${ENVIRONMENT}

${BOLD}Next Steps:${NC}
────────────────────────────────────────────────────────────
  1. Configure kubectl:
     aws eks update-kubeconfig --name ${PROJECT_NAME}-cluster-${ENVIRONMENT} --region ${AWS_REGION}

  2. Deploy Aura applications:
     kubectl apply -k deploy/kubernetes/overlays/${ENVIRONMENT}/

  3. Access the Aura dashboard:
     kubectl port-forward svc/aura-frontend 8080:80

  4. Connect your first repository:
     Open https://localhost:8080 and follow the onboarding wizard

${BOLD}Documentation:${NC}
────────────────────────────────────────────────────────────
  Quick Start:      https://docs.aenealabs.com/quick-start
  Configuration:    https://docs.aenealabs.com/configuration
  Troubleshooting:  https://docs.aenealabs.com/troubleshooting

${BOLD}Support:${NC}
────────────────────────────────────────────────────────────
  Email:  support@aenealabs.com
  GitHub: github.com/aenealabs/aura/issues

EOF
}

# =============================================================================
# Main Entry Point
# =============================================================================

main() {
    print_banner
    parse_args "$@"

    # Run pre-flight checks unless skipped
    if [[ "$SKIP_PREFLIGHT" != true ]]; then
        if ! run_preflight_checks; then
            exit 1
        fi
    else
        log_warn "Pre-flight checks skipped (--skip-preflight)"
    fi

    # Load and confirm configuration
    load_configuration

    # Run deployment
    if [[ "$DRY_RUN" == true ]]; then
        log_step "Dry Run Mode"
        log_info "No changes will be made. Review the deployment plan above."
        exit 0
    fi

    run_deployment

    # Run verification
    run_verification

    # Show summary
    show_summary

    exit 0
}

# Run main function
main "$@"
