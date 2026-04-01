#!/bin/bash
################################################################################
# Project Aura - EKS Node Group AMI Update Script
#
# Purpose: Automate AMI updates for EKS managed node groups
# Compatible: AWS Commercial Cloud and AWS GovCloud (US)
#
# Usage:
#   ./update-eks-node-ami.sh --cluster <cluster-name> --nodegroup <nodegroup-name> [options]
#
# Options:
#   --cluster       EKS cluster name (required)
#   --nodegroup     Node group name (required)
#   --region        AWS region (default: us-east-1)
#   --release       Specific AMI release version (default: latest)
#   --dry-run       Show what would be updated without applying
#   --force         Skip confirmation prompts
#   --max-unavail   Max unavailable nodes during update (default: 1)
#
# Examples:
#   # Update to latest AMI (interactive)
#   ./update-eks-node-ami.sh --cluster aura-cluster-dev --nodegroup aura-system-dev
#
#   # Update all node groups in cluster
#   ./update-eks-node-ami.sh --cluster aura-cluster-dev --nodegroup all
#
#   # Dry run to see what would change
#   ./update-eks-node-ami.sh --cluster aura-cluster-dev --nodegroup all --dry-run
#
# Automation:
#   Schedule weekly via cron:
#   0 2 * * 0 /path/to/update-eks-node-ami.sh --cluster aura-cluster-dev --nodegroup all --force
#
################################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
REGION="${AWS_REGION:-us-east-1}"
DRY_RUN=false
FORCE=false
MAX_UNAVAILABLE=1
RELEASE_VERSION="latest"

# Logging functions
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

# Usage information
usage() {
    cat << EOF
Usage: $0 --cluster <cluster-name> --nodegroup <nodegroup-name> [options]

Required:
  --cluster <name>      EKS cluster name
  --nodegroup <name>    Node group name (or 'all' for all node groups)

Optional:
  --region <region>     AWS region (default: $REGION)
  --release <version>   Specific AMI release version (default: latest)
  --dry-run             Show what would be updated without applying
  --force               Skip confirmation prompts
  --max-unavail <num>   Max unavailable nodes during update (default: $MAX_UNAVAILABLE)
  --help                Show this help message

Examples:
  $0 --cluster aura-cluster-dev --nodegroup aura-system-dev
  $0 --cluster aura-cluster-dev --nodegroup all --force
  $0 --cluster aura-cluster-dev --nodegroup aura-application-dev --dry-run

EOF
    exit 1
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --cluster)
                CLUSTER_NAME="$2"
                shift 2
                ;;
            --nodegroup)
                NODEGROUP_NAME="$2"
                shift 2
                ;;
            --region)
                REGION="$2"
                shift 2
                ;;
            --release)
                RELEASE_VERSION="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --max-unavail)
                MAX_UNAVAILABLE="$2"
                shift 2
                ;;
            --help)
                usage
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                ;;
        esac
    done

    # Validate required parameters
    if [[ -z "${CLUSTER_NAME:-}" ]]; then
        log_error "Missing required parameter: --cluster"
        usage
    fi

    if [[ -z "${NODEGROUP_NAME:-}" ]]; then
        log_error "Missing required parameter: --nodegroup"
        usage
    fi
}

# Check if AWS CLI is installed and configured
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi

    if ! command -v jq &> /dev/null; then
        log_error "jq is not installed. Please install it first."
        exit 1
    fi

    # Verify AWS credentials
    if ! aws sts get-caller-identity --region "$REGION" &> /dev/null; then
        log_error "AWS credentials not configured or invalid"
        exit 1
    fi

    # Verify cluster exists
    if ! aws eks describe-cluster --name "$CLUSTER_NAME" --region "$REGION" &> /dev/null; then
        log_error "EKS cluster '$CLUSTER_NAME' not found in region '$REGION'"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Get list of node groups to update
get_node_groups() {
    log_info "Retrieving node groups..."

    if [[ "$NODEGROUP_NAME" == "all" ]]; then
        NODEGROUPS=$(aws eks list-nodegroups \
            --cluster-name "$CLUSTER_NAME" \
            --region "$REGION" \
            --query 'nodegroups' \
            --output text)

        if [[ -z "$NODEGROUPS" ]]; then
            log_error "No node groups found in cluster '$CLUSTER_NAME'"
            exit 1
        fi

        log_info "Found node groups: $NODEGROUPS"
    else
        # Verify single node group exists
        if ! aws eks describe-nodegroup \
            --cluster-name "$CLUSTER_NAME" \
            --nodegroup-name "$NODEGROUP_NAME" \
            --region "$REGION" &> /dev/null; then
            log_error "Node group '$NODEGROUP_NAME' not found in cluster '$CLUSTER_NAME'"
            exit 1
        fi
        NODEGROUPS="$NODEGROUP_NAME"
    fi
}

# Get current node group details
get_nodegroup_info() {
    local nodegroup=$1

    aws eks describe-nodegroup \
        --cluster-name "$CLUSTER_NAME" \
        --nodegroup-name "$nodegroup" \
        --region "$REGION" \
        --output json
}

# Get latest AMI version for the node group
get_latest_ami_version() {
    local nodegroup=$1
    local nodegroup_info
    nodegroup_info=$(get_nodegroup_info "$nodegroup")

    local k8s_version
    k8s_version=$(echo "$nodegroup_info" | jq -r '.nodegroup.version')

    local ami_type
    ami_type=$(echo "$nodegroup_info" | jq -r '.nodegroup.amiType')

    # Get latest AMI release version
    local release_version
    if [[ "$RELEASE_VERSION" == "latest" ]]; then
        release_version=$(aws ssm get-parameter \
            --name "/aws/service/eks/optimized-ami/$k8s_version/$ami_type/recommended/release_version" \
            --region "$REGION" \
            --query 'Parameter.Value' \
            --output text 2>/dev/null || echo "")
    else
        release_version="$RELEASE_VERSION"
    fi

    echo "$release_version"
}

# Get current AMI release version
get_current_ami_version() {
    local nodegroup=$1
    local nodegroup_info
    nodegroup_info=$(get_nodegroup_info "$nodegroup")

    echo "$nodegroup_info" | jq -r '.nodegroup.releaseVersion // "unknown"'
}

# Check if update is needed
check_update_needed() {
    local nodegroup=$1
    local current_version
    local latest_version

    current_version=$(get_current_ami_version "$nodegroup")
    latest_version=$(get_latest_ami_version "$nodegroup")

    if [[ -z "$latest_version" ]]; then
        log_warning "Could not determine latest AMI version for node group '$nodegroup'"
        return 1
    fi

    if [[ "$current_version" == "$latest_version" ]]; then
        log_info "Node group '$nodegroup' is already up to date (version: $current_version)"
        return 1
    fi

    log_info "Node group '$nodegroup': $current_version → $latest_version"
    return 0
}

# Update node group AMI
update_nodegroup() {
    local nodegroup=$1

    log_info "Updating node group '$nodegroup'..."

    if [[ "$DRY_RUN" == true ]]; then
        log_warning "[DRY RUN] Would update node group '$nodegroup'"
        return 0
    fi

    # Start the update
    local update_id
    update_id=$(aws eks update-nodegroup-version \
        --cluster-name "$CLUSTER_NAME" \
        --nodegroup-name "$nodegroup" \
        --region "$REGION" \
        --query 'update.id' \
        --output text 2>&1)

    if [[ $? -ne 0 ]]; then
        log_error "Failed to start update for node group '$nodegroup': $update_id"
        return 1
    fi

    log_success "Update started for node group '$nodegroup' (Update ID: $update_id)"

    # Wait for update to complete
    log_info "Waiting for update to complete (this may take 10-30 minutes)..."

    local status="InProgress"
    local attempts=0
    local max_attempts=60  # 60 attempts × 30s = 30 minutes max wait

    while [[ "$status" == "InProgress" ]] && [[ $attempts -lt $max_attempts ]]; do
        sleep 30
        attempts=$((attempts + 1))

        status=$(aws eks describe-update \
            --name "$CLUSTER_NAME" \
            --update-id "$update_id" \
            --region "$REGION" \
            --query 'update.status' \
            --output text)

        log_info "Update status: $status (attempt $attempts/$max_attempts)"
    done

    if [[ "$status" == "Successful" ]]; then
        log_success "Node group '$nodegroup' updated successfully"
        return 0
    elif [[ "$status" == "Failed" ]]; then
        log_error "Update failed for node group '$nodegroup'"

        # Get error details
        local errors
        errors=$(aws eks describe-update \
            --name "$CLUSTER_NAME" \
            --update-id "$update_id" \
            --region "$REGION" \
            --query 'update.errors' \
            --output json)

        log_error "Error details: $errors"
        return 1
    else
        log_warning "Update status unclear: $status"
        return 1
    fi
}

# Generate update summary
generate_summary() {
    log_info "========================================="
    log_info "AMI Update Summary"
    log_info "========================================="
    log_info "Cluster: $CLUSTER_NAME"
    log_info "Region: $REGION"
    log_info "Node Groups: ${NODEGROUPS}"
    log_info "Dry Run: $DRY_RUN"
    log_info "========================================="
}

# Confirm update
confirm_update() {
    if [[ "$FORCE" == true ]]; then
        return 0
    fi

    if [[ "$DRY_RUN" == true ]]; then
        return 0
    fi

    echo ""
    read -p "Proceed with AMI update? (yes/no): " -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log_warning "Update cancelled by user"
        exit 0
    fi
}

# Main execution
main() {
    parse_args "$@"

    log_info "Project Aura - EKS Node Group AMI Update"
    log_info "========================================="

    check_prerequisites
    get_node_groups
    generate_summary

    # Track updates needed
    local updates_needed=false
    local nodegroups_to_update=()

    # Check each node group
    for nodegroup in $NODEGROUPS; do
        if check_update_needed "$nodegroup"; then
            updates_needed=true
            nodegroups_to_update+=("$nodegroup")
        fi
    done

    if [[ "$updates_needed" == false ]]; then
        log_success "All node groups are up to date!"
        exit 0
    fi

    confirm_update

    # Perform updates
    local success_count=0
    local failure_count=0

    for nodegroup in "${nodegroups_to_update[@]}"; do
        if update_nodegroup "$nodegroup"; then
            success_count=$((success_count + 1))
        else
            failure_count=$((failure_count + 1))
        fi
    done

    # Final summary
    echo ""
    log_info "========================================="
    log_info "Update Complete"
    log_info "========================================="
    log_success "Successful updates: $success_count"
    if [[ $failure_count -gt 0 ]]; then
        log_error "Failed updates: $failure_count"
    fi
    log_info "========================================="

    if [[ $failure_count -gt 0 ]]; then
        exit 1
    fi
}

# Run main function
main "$@"
