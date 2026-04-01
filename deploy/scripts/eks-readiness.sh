#!/bin/bash
# =============================================================================
# Project Aura - EKS Cluster Readiness Checks
# =============================================================================
# Shared utility functions for validating EKS cluster and node readiness.
# Provides checks for cluster status, node health, and addon availability.
#
# USAGE:
#   source deploy/scripts/eks-readiness.sh
#   wait_for_eks_ready "cluster-name" 300
#   wait_for_nodes_ready 2 180
#
# FUNCTIONS:
#   wait_for_eks_ready      - Wait for EKS cluster to become ACTIVE
#   wait_for_nodes_ready    - Wait for specified number of nodes to be Ready
#   check_node_health       - Verify all nodes are healthy
#   check_addon_ready       - Check if an EKS addon is ready
#   wait_for_rollout        - Wait for a Kubernetes deployment/daemonset rollout
#   verify_pod_running      - Verify pods are running for a label selector
#
# PREREQUISITES:
#   - AWS CLI configured
#   - kubectl configured with cluster access
#   - Required environment variables: AWS_DEFAULT_REGION
#
# =============================================================================

# Fail on error and pipe failures (unless already set)
if [[ "${EKS_HELPERS_SOURCED:-}" != "true" ]]; then
    set -o pipefail
    EKS_HELPERS_SOURCED=true
fi

# =============================================================================
# Configuration
# =============================================================================
EKS_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION:-us-east-1}}"
EKS_DEFAULT_TIMEOUT=300  # 5 minutes default timeout

# Colors for output
readonly EKS_RED='\033[0;31m'
readonly EKS_GREEN='\033[0;32m'
readonly EKS_YELLOW='\033[1;33m'
readonly EKS_BLUE='\033[0;34m'
readonly EKS_NC='\033[0m'

# =============================================================================
# Logging Functions
# =============================================================================

eks_log_info() {
    echo -e "${EKS_BLUE}[EKS]${EKS_NC} $1" >&2
}

eks_log_success() {
    echo -e "${EKS_GREEN}[EKS]${EKS_NC} $1" >&2
}

eks_log_warning() {
    echo -e "${EKS_YELLOW}[EKS]${EKS_NC} $1" >&2
}

eks_log_error() {
    echo -e "${EKS_RED}[EKS]${EKS_NC} $1" >&2
}

# =============================================================================
# EKS Cluster Functions
# =============================================================================

# Get EKS cluster status
# Arguments: cluster_name [region]
# Outputs: Cluster status (CREATING, ACTIVE, DELETING, FAILED, UPDATING)
get_eks_cluster_status() {
    local cluster_name="$1"
    local region="${2:-$EKS_REGION}"

    aws eks describe-cluster \
        --name "$cluster_name" \
        --query 'cluster.status' \
        --output text \
        --region "$region" 2>/dev/null || echo "NOT_FOUND"
}

# Wait for EKS cluster to become ACTIVE
# Arguments: cluster_name [timeout_seconds] [region]
# Returns: 0 if active, 1 if timeout or error
wait_for_eks_ready() {
    local cluster_name="$1"
    local timeout="${2:-$EKS_DEFAULT_TIMEOUT}"
    local region="${3:-$EKS_REGION}"

    eks_log_info "Waiting for EKS cluster to be ready: $cluster_name (timeout: ${timeout}s)"

    local start_time
    start_time=$(date +%s)

    while true; do
        local status
        status=$(get_eks_cluster_status "$cluster_name" "$region")

        case "$status" in
            ACTIVE)
                eks_log_success "EKS cluster is ACTIVE"
                return 0
                ;;
            FAILED)
                eks_log_error "EKS cluster is in FAILED state"
                return 1
                ;;
            NOT_FOUND)
                eks_log_error "EKS cluster not found: $cluster_name"
                return 1
                ;;
            CREATING|UPDATING)
                eks_log_info "Cluster status: $status (waiting...)"
                ;;
            *)
                eks_log_warning "Unexpected cluster status: $status"
                ;;
        esac

        local elapsed
        elapsed=$(($(date +%s) - start_time))
        if [[ $elapsed -ge $timeout ]]; then
            eks_log_error "Timeout waiting for cluster to be ready"
            return 1
        fi

        sleep 15
    done
}

# Configure kubectl for EKS cluster
# Arguments: cluster_name [region]
# Returns: 0 on success, 1 on failure
configure_kubectl() {
    local cluster_name="$1"
    local region="${2:-$EKS_REGION}"

    eks_log_info "Configuring kubectl for cluster: $cluster_name"

    if aws eks update-kubeconfig \
        --name "$cluster_name" \
        --region "$region"; then
        eks_log_success "kubectl configured"
        return 0
    else
        eks_log_error "Failed to configure kubectl"
        return 1
    fi
}

# =============================================================================
# Node Functions
# =============================================================================

# Get count of Ready nodes
# Outputs: Number of nodes in Ready state
get_ready_node_count() {
    kubectl get nodes \
        --no-headers \
        -o custom-columns=":status.conditions[?(@.type=='Ready')].status" 2>/dev/null | \
        grep -c "True" || echo "0"
}

# Wait for specified number of nodes to be Ready
# Arguments: min_nodes [timeout_seconds]
# Returns: 0 if ready, 1 if timeout
wait_for_nodes_ready() {
    local min_nodes="${1:-1}"
    local timeout="${2:-$EKS_DEFAULT_TIMEOUT}"

    eks_log_info "Waiting for at least $min_nodes node(s) to be Ready (timeout: ${timeout}s)"

    local start_time
    start_time=$(date +%s)

    while true; do
        local ready_count
        ready_count=$(get_ready_node_count)

        eks_log_info "Ready nodes: $ready_count / $min_nodes"

        if [[ $ready_count -ge $min_nodes ]]; then
            eks_log_success "Required nodes are Ready"
            return 0
        fi

        local elapsed
        elapsed=$(($(date +%s) - start_time))
        if [[ $elapsed -ge $timeout ]]; then
            eks_log_error "Timeout waiting for nodes to be Ready"
            return 1
        fi

        sleep 10
    done
}

# Check overall node health
# Returns: 0 if all nodes healthy, 1 if any unhealthy
check_node_health() {
    eks_log_info "Checking node health..."

    local unhealthy_nodes
    unhealthy_nodes=$(kubectl get nodes \
        --no-headers \
        -o custom-columns="NAME:.metadata.name,STATUS:.status.conditions[?(@.type=='Ready')].status" 2>/dev/null | \
        grep -v "True" | \
        wc -l | \
        tr -d ' ')

    if [[ $unhealthy_nodes -gt 0 ]]; then
        eks_log_error "Found $unhealthy_nodes unhealthy node(s)"
        kubectl get nodes -o wide
        return 1
    fi

    eks_log_success "All nodes are healthy"
    return 0
}

# Get node details for debugging
# Outputs: Node information
show_node_details() {
    eks_log_info "Node Details:"
    kubectl get nodes -o wide
    echo ""
    eks_log_info "Node Conditions:"
    kubectl get nodes -o custom-columns="\
NAME:.metadata.name,\
READY:.status.conditions[?(@.type=='Ready')].status,\
MEMORY:.status.conditions[?(@.type=='MemoryPressure')].status,\
DISK:.status.conditions[?(@.type=='DiskPressure')].status,\
PID:.status.conditions[?(@.type=='PIDPressure')].status"
}

# =============================================================================
# EKS Addon Functions
# =============================================================================

# Get EKS addon status
# Arguments: cluster_name addon_name [region]
# Outputs: Addon status
get_addon_status() {
    local cluster_name="$1"
    local addon_name="$2"
    local region="${3:-$EKS_REGION}"

    aws eks describe-addon \
        --cluster-name "$cluster_name" \
        --addon-name "$addon_name" \
        --query 'addon.status' \
        --output text \
        --region "$region" 2>/dev/null || echo "NOT_FOUND"
}

# Wait for EKS addon to be ACTIVE
# Arguments: cluster_name addon_name [timeout_seconds] [region]
# Returns: 0 if active, 1 if timeout or error
wait_for_addon_ready() {
    local cluster_name="$1"
    local addon_name="$2"
    local timeout="${3:-$EKS_DEFAULT_TIMEOUT}"
    local region="${4:-$EKS_REGION}"

    eks_log_info "Waiting for addon to be ready: $addon_name (timeout: ${timeout}s)"

    local start_time
    start_time=$(date +%s)

    while true; do
        local status
        status=$(get_addon_status "$cluster_name" "$addon_name" "$region")

        case "$status" in
            ACTIVE)
                eks_log_success "Addon is ACTIVE: $addon_name"
                return 0
                ;;
            CREATE_FAILED|DELETE_FAILED|DEGRADED)
                eks_log_error "Addon is in failed state: $addon_name ($status)"
                return 1
                ;;
            NOT_FOUND)
                eks_log_info "Addon not installed: $addon_name"
                return 0  # Not having the addon may be acceptable
                ;;
            CREATING|UPDATING)
                eks_log_info "Addon status: $status (waiting...)"
                ;;
            *)
                eks_log_warning "Unexpected addon status: $status"
                ;;
        esac

        local elapsed
        elapsed=$(($(date +%s) - start_time))
        if [[ $elapsed -ge $timeout ]]; then
            eks_log_error "Timeout waiting for addon: $addon_name"
            return 1
        fi

        sleep 10
    done
}

# =============================================================================
# Kubernetes Workload Functions
# =============================================================================

# Wait for a Deployment or DaemonSet rollout to complete
# Arguments: resource_type name [namespace] [timeout]
# Returns: 0 on success, 1 on failure
wait_for_rollout() {
    local resource_type="$1"
    local name="$2"
    local namespace="${3:-default}"
    local timeout="${4:-300}"

    eks_log_info "Waiting for $resource_type rollout: $name (namespace: $namespace, timeout: ${timeout}s)"

    if kubectl rollout status "$resource_type/$name" \
        -n "$namespace" \
        --timeout="${timeout}s" 2>/dev/null; then
        eks_log_success "Rollout complete: $resource_type/$name"
        return 0
    else
        eks_log_error "Rollout failed or timeout: $resource_type/$name"
        # Show pod status for debugging
        kubectl get pods -n "$namespace" -l "app=$name" -o wide 2>/dev/null || true
        return 1
    fi
}

# Verify pods are running for a label selector
# Arguments: label_selector [namespace] [min_ready]
# Returns: 0 if ready, 1 if not
verify_pods_running() {
    local label_selector="$1"
    local namespace="${2:-default}"
    local min_ready="${3:-1}"

    eks_log_info "Verifying pods with selector: $label_selector (min ready: $min_ready)"

    local running_count
    running_count=$(kubectl get pods \
        -n "$namespace" \
        -l "$label_selector" \
        --field-selector=status.phase=Running \
        --no-headers 2>/dev/null | wc -l | tr -d ' ')

    if [[ $running_count -ge $min_ready ]]; then
        eks_log_success "Found $running_count running pod(s)"
        return 0
    else
        eks_log_error "Not enough running pods: $running_count / $min_ready"
        kubectl get pods -n "$namespace" -l "$label_selector" -o wide 2>/dev/null || true
        return 1
    fi
}

# Get pod logs for debugging
# Arguments: label_selector [namespace] [tail_lines]
show_pod_logs() {
    local label_selector="$1"
    local namespace="${2:-default}"
    local tail_lines="${3:-50}"

    eks_log_info "Pod logs for: $label_selector"
    kubectl logs -n "$namespace" -l "$label_selector" --tail="$tail_lines" 2>/dev/null || \
        eks_log_warning "Could not retrieve logs"
}

# =============================================================================
# Composite Readiness Functions
# =============================================================================

# Full EKS readiness check
# Arguments: cluster_name min_nodes [timeout] [region]
# Returns: 0 if ready, 1 if not
full_eks_readiness_check() {
    local cluster_name="$1"
    local min_nodes="${2:-1}"
    local timeout="${3:-$EKS_DEFAULT_TIMEOUT}"
    local region="${4:-$EKS_REGION}"

    eks_log_info "=========================================="
    eks_log_info "Full EKS Readiness Check"
    eks_log_info "Cluster: $cluster_name"
    eks_log_info "Min Nodes: $min_nodes"
    eks_log_info "Timeout: ${timeout}s"
    eks_log_info "=========================================="

    local failed=0

    # Check cluster is ACTIVE
    wait_for_eks_ready "$cluster_name" "$timeout" "$region" || ((failed++))

    # Configure kubectl
    configure_kubectl "$cluster_name" "$region" || ((failed++))

    # Wait for nodes
    wait_for_nodes_ready "$min_nodes" "$timeout" || ((failed++))

    # Check node health
    check_node_health || ((failed++))

    # Check core addons
    for addon in vpc-cni coredns kube-proxy; do
        wait_for_addon_ready "$cluster_name" "$addon" 60 "$region" || eks_log_warning "Addon check skipped: $addon"
    done

    if [[ $failed -gt 0 ]]; then
        eks_log_error "=========================================="
        eks_log_error "Readiness Check FAILED ($failed issues)"
        eks_log_error "=========================================="
        show_node_details
        return 1
    fi

    eks_log_success "=========================================="
    eks_log_success "Readiness Check PASSED"
    eks_log_success "=========================================="
    return 0
}

# Quick connectivity test
# Arguments: cluster_name [region]
# Returns: 0 if connected, 1 if not
quick_connectivity_test() {
    local cluster_name="$1"
    local region="${2:-$EKS_REGION}"

    eks_log_info "Quick connectivity test for: $cluster_name"

    # Configure kubectl
    configure_kubectl "$cluster_name" "$region" || return 1

    # Test cluster info
    if kubectl cluster-info >/dev/null 2>&1; then
        eks_log_success "Cluster is accessible"

        # Get basic info
        eks_log_info "Cluster Info:"
        kubectl cluster-info

        eks_log_info "Nodes:"
        kubectl get nodes --no-headers | head -5

        return 0
    else
        eks_log_error "Cannot connect to cluster"
        return 1
    fi
}

# =============================================================================
# Export functions for use in buildspecs
# =============================================================================
export -f eks_log_info eks_log_success eks_log_warning eks_log_error
export -f get_eks_cluster_status wait_for_eks_ready configure_kubectl
export -f get_ready_node_count wait_for_nodes_ready check_node_health show_node_details
export -f get_addon_status wait_for_addon_ready
export -f wait_for_rollout verify_pods_running show_pod_logs
export -f full_eks_readiness_check quick_connectivity_test
