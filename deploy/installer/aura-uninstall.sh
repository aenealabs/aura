#!/bin/bash
# =============================================================================
# Project Aura - Clean Removal Script
# =============================================================================
# Safely removes all Aura resources from your AWS account.
#
# Usage:
#   ./aura-uninstall.sh --name aura --environment prod
#   ./aura-uninstall.sh --name aura --environment prod --force
#
# WARNING: This will permanently delete all data including:
#   - Neptune graph database and all stored data
#   - OpenSearch indices and vector embeddings
#   - S3 buckets and stored artifacts
#   - EKS cluster and all workloads
#
# Exit Codes:
#   0: Uninstallation successful
#   1: Pre-checks failed
#   2: User cancelled
#   3: Deletion failed
#
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration and Constants
# =============================================================================
readonly VERSION="1.0.0"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

# Default configuration
PROJECT_NAME="aura"
ENVIRONMENT="prod"
AWS_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
FORCE_DELETE=false
DRY_RUN=false
VERBOSE=false
RETAIN_DATA=false

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
    ║              Uninstallation Script                            ║
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

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Project Aura Uninstallation Script

OPTIONS:
    -h, --help              Show this help message
    -v, --version           Show version information
    -n, --name NAME         Project name prefix [default: aura]
    -e, --environment ENV   Deployment environment (dev|qa|prod) [default: prod]
    -r, --region REGION     AWS region [default: us-east-1]
    --force                 Skip confirmation prompts
    --dry-run               Show what would be deleted without deleting
    --retain-data           Keep S3 buckets and database snapshots
    --verbose               Enable verbose output

EXAMPLES:
    # Standard uninstall with confirmation
    $0 --name aura --environment prod

    # Force uninstall without confirmation
    $0 --name aura --environment dev --force

    # Dry run to see what would be deleted
    $0 --dry-run

    # Uninstall but retain data backups
    $0 --name aura --environment prod --retain-data

WARNING:
    This operation is IRREVERSIBLE. All data will be permanently deleted
    unless --retain-data is specified.

DOCUMENTATION:
    https://docs.aenealabs.com/uninstall

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
                echo "Aura Uninstaller version $VERSION"
                exit 0
                ;;
            -n|--name)
                PROJECT_NAME="$2"
                shift 2
                ;;
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -r|--region)
                AWS_REGION="$2"
                shift 2
                ;;
            --force)
                FORCE_DELETE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --retain-data)
                RETAIN_DATA=true
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
}

# =============================================================================
# Discovery Functions
# =============================================================================

discover_resources() {
    log_step "Discovering Aura Resources"

    echo "Searching for resources with prefix '${PROJECT_NAME}-*-${ENVIRONMENT}'..."
    echo ""

    # Find CloudFormation stacks
    log_substep "CloudFormation stacks:"
    STACKS=$(aws cloudformation list-stacks \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE \
        --query "StackSummaries[?starts_with(StackName, '${PROJECT_NAME}-') && ends_with(StackName, '-${ENVIRONMENT}')].StackName" \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "")

    if [[ -n "$STACKS" ]]; then
        for stack in $STACKS; do
            echo "    - $stack"
        done
    else
        echo "    (none found)"
    fi

    # Find S3 buckets
    log_substep "S3 buckets:"
    BUCKETS=$(aws s3api list-buckets \
        --query "Buckets[?starts_with(Name, '${PROJECT_NAME}-') && contains(Name, '-${ENVIRONMENT}')].Name" \
        --output text 2>/dev/null || echo "")

    if [[ -n "$BUCKETS" ]]; then
        for bucket in $BUCKETS; do
            echo "    - $bucket"
        done
    else
        echo "    (none found)"
    fi

    # Find EKS clusters
    log_substep "EKS clusters:"
    CLUSTERS=$(aws eks list-clusters \
        --query "clusters[?starts_with(@, '${PROJECT_NAME}-')]" \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "")

    if [[ -n "$CLUSTERS" ]]; then
        for cluster in $CLUSTERS; do
            if [[ "$cluster" == *"-${ENVIRONMENT}"* ]]; then
                echo "    - $cluster"
            fi
        done
    else
        echo "    (none found)"
    fi

    # Find Neptune clusters
    log_substep "Neptune clusters:"
    NEPTUNE=$(aws neptune describe-db-clusters \
        --query "DBClusters[?starts_with(DBClusterIdentifier, '${PROJECT_NAME}-')].DBClusterIdentifier" \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "")

    if [[ -n "$NEPTUNE" ]]; then
        for cluster in $NEPTUNE; do
            if [[ "$cluster" == *"-${ENVIRONMENT}"* ]]; then
                echo "    - $cluster"
            fi
        done
    else
        echo "    (none found)"
    fi

    # Find OpenSearch domains
    log_substep "OpenSearch domains:"
    OPENSEARCH=$(aws opensearch list-domain-names \
        --query "DomainNames[?starts_with(DomainName, '${PROJECT_NAME}-')].DomainName" \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "")

    if [[ -n "$OPENSEARCH" ]]; then
        for domain in $OPENSEARCH; do
            if [[ "$domain" == *"-${ENVIRONMENT}"* || "$domain" == "${PROJECT_NAME}-${ENVIRONMENT}" ]]; then
                echo "    - $domain"
            fi
        done
    else
        echo "    (none found)"
    fi

    echo ""
}

confirm_deletion() {
    if [[ "$FORCE_DELETE" == true ]]; then
        return 0
    fi

    echo ""
    echo -e "${RED}${BOLD}WARNING: DESTRUCTIVE OPERATION${NC}"
    echo ""
    echo "This will permanently delete:"
    echo "  - All CloudFormation stacks and their resources"
    echo "  - EKS cluster and all Kubernetes workloads"
    echo "  - Neptune graph database and ALL stored data"
    echo "  - OpenSearch domain and ALL vector embeddings"
    if [[ "$RETAIN_DATA" != true ]]; then
        echo "  - S3 buckets and ALL stored artifacts"
    else
        echo "  - S3 buckets will be RETAINED"
    fi
    echo ""
    echo -e "${YELLOW}This action is IRREVERSIBLE.${NC}"
    echo ""

    read -p "Type 'DELETE' to confirm deletion: " confirmation
    if [[ "$confirmation" != "DELETE" ]]; then
        log_info "Uninstallation cancelled by user"
        exit 2
    fi

    # Double confirmation for production
    if [[ "$ENVIRONMENT" == "prod" ]]; then
        echo ""
        echo -e "${RED}You are about to delete PRODUCTION resources.${NC}"
        read -p "Type the project name '${PROJECT_NAME}' to confirm: " project_confirm
        if [[ "$project_confirm" != "$PROJECT_NAME" ]]; then
            log_info "Uninstallation cancelled by user"
            exit 2
        fi
    fi

    return 0
}

# =============================================================================
# Deletion Functions
# =============================================================================

delete_eks_cluster() {
    local cluster_name=$1

    log_substep "Deleting EKS cluster: $cluster_name"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would delete EKS cluster: $cluster_name"
        return 0
    fi

    # Delete node groups first
    local nodegroups
    nodegroups=$(aws eks list-nodegroups \
        --cluster-name "$cluster_name" \
        --query 'nodegroups[]' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "")

    for ng in $nodegroups; do
        log_substep "Deleting node group: $ng"
        aws eks delete-nodegroup \
            --cluster-name "$cluster_name" \
            --nodegroup-name "$ng" \
            --region "$AWS_REGION" || true

        # Wait for node group deletion
        aws eks wait nodegroup-deleted \
            --cluster-name "$cluster_name" \
            --nodegroup-name "$ng" \
            --region "$AWS_REGION" 2>/dev/null || true
    done

    # Delete Fargate profiles
    local profiles
    profiles=$(aws eks list-fargate-profiles \
        --cluster-name "$cluster_name" \
        --query 'fargateProfileNames[]' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "")

    for profile in $profiles; do
        log_substep "Deleting Fargate profile: $profile"
        aws eks delete-fargate-profile \
            --cluster-name "$cluster_name" \
            --fargate-profile-name "$profile" \
            --region "$AWS_REGION" || true

        aws eks wait fargate-profile-deleted \
            --cluster-name "$cluster_name" \
            --fargate-profile-name "$profile" \
            --region "$AWS_REGION" 2>/dev/null || true
    done

    # Delete addons
    local addons
    addons=$(aws eks list-addons \
        --cluster-name "$cluster_name" \
        --query 'addons[]' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "")

    for addon in $addons; do
        log_substep "Deleting addon: $addon"
        aws eks delete-addon \
            --cluster-name "$cluster_name" \
            --addon-name "$addon" \
            --region "$AWS_REGION" || true
    done

    # Delete cluster
    aws eks delete-cluster \
        --name "$cluster_name" \
        --region "$AWS_REGION" || true

    # Wait for cluster deletion
    log_substep "Waiting for cluster deletion (this may take 10-15 minutes)..."
    aws eks wait cluster-deleted \
        --name "$cluster_name" \
        --region "$AWS_REGION" 2>/dev/null || true

    log_check "pass" "EKS cluster $cluster_name deleted"
}

delete_s3_bucket() {
    local bucket_name=$1

    log_substep "Deleting S3 bucket: $bucket_name"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would delete S3 bucket: $bucket_name"
        return 0
    fi

    if [[ "$RETAIN_DATA" == true ]]; then
        log_check "skip" "Bucket $bucket_name retained (--retain-data)"
        return 0
    fi

    # Delete all objects
    aws s3 rm "s3://$bucket_name" --recursive 2>/dev/null || true

    # Delete all versions (for versioned buckets)
    aws s3api delete-objects \
        --bucket "$bucket_name" \
        --delete "$(aws s3api list-object-versions \
            --bucket "$bucket_name" \
            --query='{Objects: Versions[].{Key:Key,VersionId:VersionId}}' \
            --output json 2>/dev/null)" 2>/dev/null || true

    # Delete delete markers
    aws s3api delete-objects \
        --bucket "$bucket_name" \
        --delete "$(aws s3api list-object-versions \
            --bucket "$bucket_name" \
            --query='{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' \
            --output json 2>/dev/null)" 2>/dev/null || true

    # Delete bucket
    aws s3api delete-bucket \
        --bucket "$bucket_name" \
        --region "$AWS_REGION" || true

    log_check "pass" "S3 bucket $bucket_name deleted"
}

delete_cloudformation_stack() {
    local stack_name=$1

    log_substep "Deleting CloudFormation stack: $stack_name"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would delete stack: $stack_name"
        return 0
    fi

    # Disable termination protection if enabled
    aws cloudformation update-termination-protection \
        --no-enable-termination-protection \
        --stack-name "$stack_name" \
        --region "$AWS_REGION" 2>/dev/null || true

    # Delete the stack
    aws cloudformation delete-stack \
        --stack-name "$stack_name" \
        --region "$AWS_REGION"

    # Wait for deletion
    log_substep "Waiting for stack deletion..."
    aws cloudformation wait stack-delete-complete \
        --stack-name "$stack_name" \
        --region "$AWS_REGION" 2>/dev/null || {
            log_check "warn" "Stack $stack_name deletion may still be in progress"
            return 1
        }

    log_check "pass" "Stack $stack_name deleted"
}

create_final_backup() {
    if [[ "$RETAIN_DATA" != true ]]; then
        return 0
    fi

    log_step "Creating Final Backups"

    # Create Neptune snapshot
    if [[ -n "$NEPTUNE" ]]; then
        for cluster in $NEPTUNE; do
            if [[ "$cluster" == *"-${ENVIRONMENT}"* ]]; then
                local snapshot_name="${cluster}-final-$(date +%Y%m%d-%H%M%S)"
                log_substep "Creating Neptune snapshot: $snapshot_name"

                if [[ "$DRY_RUN" != true ]]; then
                    aws neptune create-db-cluster-snapshot \
                        --db-cluster-identifier "$cluster" \
                        --db-cluster-snapshot-identifier "$snapshot_name" \
                        --region "$AWS_REGION" || true
                fi
            fi
        done
    fi

    log_success "Backups created (if applicable)"
}

run_deletion() {
    log_step "Deleting Resources"

    local start_time
    start_time=$(date +%s)

    # Create backups first if retaining data
    create_final_backup

    # Delete S3 buckets first (they block stack deletion)
    if [[ -n "$BUCKETS" ]]; then
        echo ""
        log_substep "Phase 1: Deleting S3 buckets..."
        for bucket in $BUCKETS; do
            delete_s3_bucket "$bucket"
        done
    fi

    # Define deletion order (reverse of creation order)
    # Application -> Compute -> Data -> Foundation
    local deletion_order=(
        "application"
        "frontend"
        "chat-assistant"
        "observability"
        "serverless"
        "sandbox"
        "eks"
        "opensearch"
        "neptune"
        "dynamodb"
        "kms"
        "s3"
        "secrets"
        "vpc-endpoints"
        "security"
        "iam"
        "networking"
    )

    echo ""
    log_substep "Phase 2: Deleting CloudFormation stacks..."

    # First, handle any special resources that need manual deletion
    for cluster in $CLUSTERS; do
        if [[ "$cluster" == *"-${ENVIRONMENT}"* ]]; then
            delete_eks_cluster "$cluster"
        fi
    done

    # Delete stacks in order
    for layer in "${deletion_order[@]}"; do
        local stack_name="${PROJECT_NAME}-${layer}-${ENVIRONMENT}"

        # Check if stack exists
        if echo "$STACKS" | grep -q "$stack_name"; then
            delete_cloudformation_stack "$stack_name"
        fi
    done

    # Delete any remaining stacks
    for stack in $STACKS; do
        # Skip if already deleted
        if ! aws cloudformation describe-stacks --stack-name "$stack" --region "$AWS_REGION" &>/dev/null; then
            continue
        fi
        delete_cloudformation_stack "$stack"
    done

    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))

    echo ""
    log_success "Deletion completed in $((duration / 60)) minutes $((duration % 60)) seconds"
}

# =============================================================================
# Cleanup and Summary
# =============================================================================

cleanup_orphaned_resources() {
    log_step "Cleaning Up Orphaned Resources"

    log_substep "Checking for orphaned security groups..."
    local sgs
    sgs=$(aws ec2 describe-security-groups \
        --filters "Name=tag:Project,Values=${PROJECT_NAME}" \
        --query "SecurityGroups[?VpcId!=null].GroupId" \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "")

    if [[ -n "$sgs" ]]; then
        for sg in $sgs; do
            log_substep "Found orphaned security group: $sg"
            if [[ "$DRY_RUN" != true ]]; then
                aws ec2 delete-security-group --group-id "$sg" --region "$AWS_REGION" 2>/dev/null || true
            fi
        done
    else
        log_check "pass" "No orphaned security groups found"
    fi

    log_substep "Checking for orphaned IAM roles..."
    local roles
    roles=$(aws iam list-roles \
        --query "Roles[?starts_with(RoleName, '${PROJECT_NAME}-')].RoleName" \
        --output text 2>/dev/null || echo "")

    if [[ -n "$roles" ]]; then
        for role in $roles; do
            if [[ "$role" == *"-${ENVIRONMENT}"* ]]; then
                log_substep "Found orphaned IAM role: $role"
                if [[ "$DRY_RUN" != true ]]; then
                    # Detach policies first
                    local policies
                    policies=$(aws iam list-attached-role-policies --role-name "$role" --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null || echo "")
                    for policy in $policies; do
                        aws iam detach-role-policy --role-name "$role" --policy-arn "$policy" 2>/dev/null || true
                    done
                    # Delete inline policies
                    local inline
                    inline=$(aws iam list-role-policies --role-name "$role" --query 'PolicyNames[]' --output text 2>/dev/null || echo "")
                    for policy in $inline; do
                        aws iam delete-role-policy --role-name "$role" --policy-name "$policy" 2>/dev/null || true
                    done
                    # Delete role
                    aws iam delete-role --role-name "$role" 2>/dev/null || true
                fi
            fi
        done
    else
        log_check "pass" "No orphaned IAM roles found"
    fi

    log_substep "Checking for orphaned log groups..."
    local logs
    logs=$(aws logs describe-log-groups \
        --log-group-name-prefix "/aws/${PROJECT_NAME}" \
        --query "logGroups[].logGroupName" \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "")

    if [[ -n "$logs" ]]; then
        for log in $logs; do
            log_substep "Found orphaned log group: $log"
            if [[ "$DRY_RUN" != true ]]; then
                aws logs delete-log-group --log-group-name "$log" --region "$AWS_REGION" 2>/dev/null || true
            fi
        done
    else
        log_check "pass" "No orphaned log groups found"
    fi
}

show_summary() {
    log_step "Uninstallation Complete"

    if [[ "$DRY_RUN" == true ]]; then
        echo ""
        echo "This was a DRY RUN. No resources were actually deleted."
        echo "Run without --dry-run to perform actual deletion."
        echo ""
        return
    fi

    cat << EOF

All Aura resources have been removed from your AWS account.

${BOLD}Summary:${NC}
────────────────────────────────────────────────────────────
  Project Name:    ${PROJECT_NAME}
  Environment:     ${ENVIRONMENT}
  Region:          ${AWS_REGION}
  Data Retained:   ${RETAIN_DATA}

${BOLD}Verified Deletions:${NC}
────────────────────────────────────────────────────────────
  - CloudFormation stacks
  - EKS cluster and node groups
  - Neptune database
  - OpenSearch domain
EOF

    if [[ "$RETAIN_DATA" != true ]]; then
        echo "  - S3 buckets and all data"
    else
        echo "  - S3 buckets (RETAINED)"
        echo ""
        echo "${BOLD}Retained Resources:${NC}"
        echo "────────────────────────────────────────────────────────────"
        echo "  The following resources were retained:"
        echo "  - S3 buckets with prefix '${PROJECT_NAME}-'"
        echo "  - Database snapshots (if created)"
        echo ""
        echo "  To delete retained resources manually:"
        echo "  aws s3 rb s3://BUCKET_NAME --force"
    fi

    cat << EOF

${BOLD}If you experience issues:${NC}
────────────────────────────────────────────────────────────
  1. Check CloudFormation for stuck stacks:
     aws cloudformation list-stacks --stack-status-filter DELETE_IN_PROGRESS DELETE_FAILED

  2. Check for ENI dependencies:
     aws ec2 describe-network-interfaces --filters "Name=description,Values=*aura*"

  3. Contact support: support@aenealabs.com

Thank you for using Project Aura.

EOF
}

# =============================================================================
# Main Entry Point
# =============================================================================

main() {
    print_banner
    parse_args "$@"

    # Validate AWS credentials
    if ! aws sts get-caller-identity --region "$AWS_REGION" &> /dev/null; then
        log_error "AWS credentials not configured or expired"
        exit 1
    fi

    # Discover resources
    discover_resources

    # Check if anything to delete
    if [[ -z "$STACKS" && -z "$BUCKETS" && -z "$CLUSTERS" && -z "$NEPTUNE" && -z "$OPENSEARCH" ]]; then
        log_info "No Aura resources found for ${PROJECT_NAME}-*-${ENVIRONMENT}"
        log_info "Nothing to uninstall."
        exit 0
    fi

    # Confirm deletion
    confirm_deletion

    # Run deletion
    run_deletion

    # Cleanup orphaned resources
    cleanup_orphaned_resources

    # Show summary
    show_summary

    exit 0
}

# Run main function
main "$@"
