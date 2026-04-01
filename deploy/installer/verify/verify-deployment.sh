#!/bin/bash
# =============================================================================
# Project Aura - Deployment Verification Suite
# =============================================================================
# Comprehensive verification of all deployed Aura services.
#
# Usage:
#   ./verify-deployment.sh [PROJECT_NAME] [ENVIRONMENT] [REGION]
#   ./verify-deployment.sh aura prod us-east-1
#
# Exit Codes:
#   0: All checks passed
#   1: Critical checks failed
#   2: Warning checks failed (non-critical)
#
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================
PROJECT_NAME="${1:-aura}"
ENVIRONMENT="${2:-prod}"
AWS_REGION="${3:-us-east-1}"

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# =============================================================================
# Utility Functions
# =============================================================================

log_section() {
    echo ""
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

check_pass() {
    echo -e "  ${GREEN}[PASS]${NC} $1"
    ((PASSED++))
}

check_fail() {
    echo -e "  ${RED}[FAIL]${NC} $1"
    ((FAILED++))
}

check_warn() {
    echo -e "  ${YELLOW}[WARN]${NC} $1"
    ((WARNINGS++))
}

check_skip() {
    echo -e "  ${BLUE}[SKIP]${NC} $1"
}

check_info() {
    echo -e "  ${CYAN}[INFO]${NC} $1"
}

# =============================================================================
# CloudFormation Stack Verification
# =============================================================================

verify_cloudformation_stacks() {
    log_section "CloudFormation Stacks"

    local stacks=(
        "${PROJECT_NAME}-networking-${ENVIRONMENT}"
        "${PROJECT_NAME}-security-${ENVIRONMENT}"
        "${PROJECT_NAME}-iam-${ENVIRONMENT}"
        "${PROJECT_NAME}-neptune-${ENVIRONMENT}"
        "${PROJECT_NAME}-opensearch-${ENVIRONMENT}"
        "${PROJECT_NAME}-eks-${ENVIRONMENT}"
    )

    for stack in "${stacks[@]}"; do
        local status
        status=$(aws cloudformation describe-stacks \
            --stack-name "$stack" \
            --query 'Stacks[0].StackStatus' \
            --output text \
            --region "$AWS_REGION" 2>/dev/null || echo "NOT_FOUND")

        case "$status" in
            CREATE_COMPLETE|UPDATE_COMPLETE)
                check_pass "Stack $stack: $status"
                ;;
            CREATE_IN_PROGRESS|UPDATE_IN_PROGRESS)
                check_warn "Stack $stack: $status (deployment in progress)"
                ;;
            NOT_FOUND)
                check_warn "Stack $stack: not found (may use different naming)"
                ;;
            *)
                check_fail "Stack $stack: $status"
                ;;
        esac
    done
}

# =============================================================================
# EKS Cluster Verification
# =============================================================================

verify_eks_cluster() {
    log_section "EKS Cluster"

    local cluster_name="${PROJECT_NAME}-cluster-${ENVIRONMENT}"

    # Check cluster exists and is active
    local cluster_status
    cluster_status=$(aws eks describe-cluster \
        --name "$cluster_name" \
        --query 'cluster.status' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "NOT_FOUND")

    if [[ "$cluster_status" == "ACTIVE" ]]; then
        check_pass "EKS cluster $cluster_name is ACTIVE"
    elif [[ "$cluster_status" == "NOT_FOUND" ]]; then
        check_fail "EKS cluster $cluster_name not found"
        return 1
    else
        check_fail "EKS cluster $cluster_name status: $cluster_status"
        return 1
    fi

    # Check Kubernetes version
    local k8s_version
    k8s_version=$(aws eks describe-cluster \
        --name "$cluster_name" \
        --query 'cluster.version' \
        --output text \
        --region "$AWS_REGION")
    check_info "Kubernetes version: $k8s_version"

    # Check node groups
    local nodegroups
    nodegroups=$(aws eks list-nodegroups \
        --cluster-name "$cluster_name" \
        --query 'nodegroups[]' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "")

    if [[ -n "$nodegroups" ]]; then
        for ng in $nodegroups; do
            local ng_status
            ng_status=$(aws eks describe-nodegroup \
                --cluster-name "$cluster_name" \
                --nodegroup-name "$ng" \
                --query 'nodegroup.status' \
                --output text \
                --region "$AWS_REGION")

            if [[ "$ng_status" == "ACTIVE" ]]; then
                local desired current
                desired=$(aws eks describe-nodegroup \
                    --cluster-name "$cluster_name" \
                    --nodegroup-name "$ng" \
                    --query 'nodegroup.scalingConfig.desiredSize' \
                    --output text \
                    --region "$AWS_REGION")
                check_pass "Node group $ng: ACTIVE ($desired nodes)"
            else
                check_fail "Node group $ng: $ng_status"
            fi
        done
    else
        check_fail "No node groups found"
    fi

    # Check cluster endpoint connectivity
    local endpoint
    endpoint=$(aws eks describe-cluster \
        --name "$cluster_name" \
        --query 'cluster.endpoint' \
        --output text \
        --region "$AWS_REGION")

    if curl -sk --max-time 5 "$endpoint/healthz" > /dev/null 2>&1; then
        check_pass "Cluster endpoint is accessible"
    else
        check_warn "Cluster endpoint not accessible (may require VPN/bastion)"
    fi
}

# =============================================================================
# Neptune Verification
# =============================================================================

verify_neptune() {
    log_section "Neptune Graph Database"

    local cluster_id="${PROJECT_NAME}-neptune-${ENVIRONMENT}"

    # Check cluster status
    local cluster_status
    cluster_status=$(aws neptune describe-db-clusters \
        --db-cluster-identifier "$cluster_id" \
        --query 'DBClusters[0].Status' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "NOT_FOUND")

    if [[ "$cluster_status" == "available" ]]; then
        check_pass "Neptune cluster $cluster_id is available"
    elif [[ "$cluster_status" == "NOT_FOUND" ]]; then
        check_fail "Neptune cluster $cluster_id not found"
        return 1
    else
        check_fail "Neptune cluster $cluster_id status: $cluster_status"
        return 1
    fi

    # Get endpoint
    local endpoint
    endpoint=$(aws neptune describe-db-clusters \
        --db-cluster-identifier "$cluster_id" \
        --query 'DBClusters[0].Endpoint' \
        --output text \
        --region "$AWS_REGION")
    check_info "Neptune endpoint: $endpoint"

    # Check instances
    local instances
    instances=$(aws neptune describe-db-instances \
        --query "DBInstances[?DBClusterIdentifier=='$cluster_id'].DBInstanceIdentifier" \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "")

    for instance in $instances; do
        local instance_status
        instance_status=$(aws neptune describe-db-instances \
            --db-instance-identifier "$instance" \
            --query 'DBInstances[0].DBInstanceStatus' \
            --output text \
            --region "$AWS_REGION")

        if [[ "$instance_status" == "available" ]]; then
            check_pass "Neptune instance $instance: available"
        else
            check_fail "Neptune instance $instance: $instance_status"
        fi
    done

    # Check encryption
    local encrypted
    encrypted=$(aws neptune describe-db-clusters \
        --db-cluster-identifier "$cluster_id" \
        --query 'DBClusters[0].StorageEncrypted' \
        --output text \
        --region "$AWS_REGION")

    if [[ "$encrypted" == "True" || "$encrypted" == "true" ]]; then
        check_pass "Neptune encryption at rest: enabled"
    else
        check_fail "Neptune encryption at rest: disabled (security risk)"
    fi
}

# =============================================================================
# OpenSearch Verification
# =============================================================================

verify_opensearch() {
    log_section "OpenSearch Vector Database"

    local domain_name="${PROJECT_NAME}-${ENVIRONMENT}"

    # Check domain status
    local processing
    processing=$(aws opensearch describe-domain \
        --domain-name "$domain_name" \
        --query 'DomainStatus.Processing' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "ERROR")

    if [[ "$processing" == "ERROR" ]]; then
        check_fail "OpenSearch domain $domain_name not found"
        return 1
    elif [[ "$processing" == "False" || "$processing" == "false" ]]; then
        check_pass "OpenSearch domain $domain_name is ready"
    else
        check_warn "OpenSearch domain $domain_name is still processing"
    fi

    # Get endpoint
    local endpoint
    endpoint=$(aws opensearch describe-domain \
        --domain-name "$domain_name" \
        --query 'DomainStatus.Endpoint' \
        --output text \
        --region "$AWS_REGION")
    check_info "OpenSearch endpoint: $endpoint"

    # Check encryption
    local encryption
    encryption=$(aws opensearch describe-domain \
        --domain-name "$domain_name" \
        --query 'DomainStatus.EncryptionAtRestOptions.Enabled' \
        --output text \
        --region "$AWS_REGION")

    if [[ "$encryption" == "True" || "$encryption" == "true" ]]; then
        check_pass "OpenSearch encryption at rest: enabled"
    else
        check_fail "OpenSearch encryption at rest: disabled"
    fi

    # Check node-to-node encryption
    local n2n_encryption
    n2n_encryption=$(aws opensearch describe-domain \
        --domain-name "$domain_name" \
        --query 'DomainStatus.NodeToNodeEncryptionOptions.Enabled' \
        --output text \
        --region "$AWS_REGION")

    if [[ "$n2n_encryption" == "True" || "$n2n_encryption" == "true" ]]; then
        check_pass "OpenSearch node-to-node encryption: enabled"
    else
        check_fail "OpenSearch node-to-node encryption: disabled"
    fi

    # Check HTTPS enforcement
    local https
    https=$(aws opensearch describe-domain \
        --domain-name "$domain_name" \
        --query 'DomainStatus.DomainEndpointOptions.EnforceHTTPS' \
        --output text \
        --region "$AWS_REGION")

    if [[ "$https" == "True" || "$https" == "true" ]]; then
        check_pass "OpenSearch HTTPS enforcement: enabled"
    else
        check_fail "OpenSearch HTTPS enforcement: disabled"
    fi
}

# =============================================================================
# S3 Buckets Verification
# =============================================================================

verify_s3_buckets() {
    log_section "S3 Buckets"

    local account_id
    account_id=$(aws sts get-caller-identity --query Account --output text)

    local buckets=(
        "${PROJECT_NAME}-artifacts-${account_id}-${ENVIRONMENT}"
        "${PROJECT_NAME}-logs-${account_id}-${ENVIRONMENT}"
        "${PROJECT_NAME}-backups-${account_id}-${ENVIRONMENT}"
    )

    for bucket in "${buckets[@]}"; do
        if aws s3api head-bucket --bucket "$bucket" 2>/dev/null; then
            check_pass "S3 bucket $bucket exists"

            # Check encryption
            local encryption
            encryption=$(aws s3api get-bucket-encryption \
                --bucket "$bucket" \
                --query 'ServerSideEncryptionConfiguration.Rules[0].ApplyServerSideEncryptionByDefault.SSEAlgorithm' \
                --output text 2>/dev/null || echo "NONE")

            if [[ "$encryption" != "NONE" && "$encryption" != "None" ]]; then
                check_pass "Bucket $bucket encryption: $encryption"
            else
                check_warn "Bucket $bucket encryption: not configured"
            fi

            # Check public access block
            local public_block
            public_block=$(aws s3api get-public-access-block \
                --bucket "$bucket" \
                --query 'PublicAccessBlockConfiguration.BlockPublicAcls' \
                --output text 2>/dev/null || echo "false")

            if [[ "$public_block" == "True" || "$public_block" == "true" ]]; then
                check_pass "Bucket $bucket public access: blocked"
            else
                check_fail "Bucket $bucket public access: NOT blocked (security risk)"
            fi
        else
            check_warn "S3 bucket $bucket not found"
        fi
    done
}

# =============================================================================
# IAM Roles Verification
# =============================================================================

verify_iam_roles() {
    log_section "IAM Roles"

    local roles=(
        "${PROJECT_NAME}-eks-cluster-role-${ENVIRONMENT}"
        "${PROJECT_NAME}-eks-node-role-${ENVIRONMENT}"
        "${PROJECT_NAME}-api-irsa-role-${ENVIRONMENT}"
    )

    for role in "${roles[@]}"; do
        if aws iam get-role --role-name "$role" &>/dev/null; then
            check_pass "IAM role $role exists"
        else
            check_warn "IAM role $role not found"
        fi
    done
}

# =============================================================================
# Security Groups Verification
# =============================================================================

verify_security_groups() {
    log_section "Security Groups"

    local sg_names=(
        "${PROJECT_NAME}-eks-sg-${ENVIRONMENT}"
        "${PROJECT_NAME}-eks-node-sg-${ENVIRONMENT}"
        "${PROJECT_NAME}-neptune-sg-${ENVIRONMENT}"
        "${PROJECT_NAME}-opensearch-sg-${ENVIRONMENT}"
    )

    for sg_name in "${sg_names[@]}"; do
        local sg_id
        sg_id=$(aws ec2 describe-security-groups \
            --filters "Name=group-name,Values=$sg_name" \
            --query 'SecurityGroups[0].GroupId' \
            --output text \
            --region "$AWS_REGION" 2>/dev/null || echo "None")

        if [[ "$sg_id" != "None" && -n "$sg_id" ]]; then
            check_pass "Security group $sg_name: $sg_id"
        else
            check_warn "Security group $sg_name not found"
        fi
    done
}

# =============================================================================
# Bedrock Access Verification
# =============================================================================

verify_bedrock_access() {
    log_section "Bedrock Model Access"

    local models=(
        "anthropic.claude-3-5-sonnet-20241022-v1:0"
        "anthropic.claude-3-haiku-20240307-v1:0"
        "amazon.titan-embed-text-v2:0"
    )

    for model in "${models[@]}"; do
        # Check if we can describe the model (indicates access)
        if aws bedrock get-foundation-model \
            --model-identifier "$model" \
            --region "$AWS_REGION" &>/dev/null; then
            check_pass "Bedrock model $model: accessible"
        else
            check_warn "Bedrock model $model: not accessible (request access in console)"
        fi
    done
}

# =============================================================================
# Kubernetes Resources Verification (if kubectl configured)
# =============================================================================

verify_kubernetes_resources() {
    log_section "Kubernetes Resources"

    # Check if kubectl is available and configured
    if ! command -v kubectl &>/dev/null; then
        check_skip "kubectl not installed"
        return 0
    fi

    local cluster_name="${PROJECT_NAME}-cluster-${ENVIRONMENT}"

    # Try to update kubeconfig
    if ! aws eks update-kubeconfig \
        --name "$cluster_name" \
        --region "$AWS_REGION" \
        --alias "${PROJECT_NAME}-verify" &>/dev/null; then
        check_skip "Could not configure kubectl (cluster may not be accessible)"
        return 0
    fi

    # Check node status
    local ready_nodes
    ready_nodes=$(kubectl get nodes --context "${PROJECT_NAME}-verify" \
        --no-headers 2>/dev/null | grep -c " Ready " || echo "0")

    if [[ "$ready_nodes" -gt 0 ]]; then
        check_pass "Kubernetes nodes ready: $ready_nodes"
    else
        check_warn "No ready Kubernetes nodes found"
    fi

    # Check system pods
    local running_pods
    running_pods=$(kubectl get pods -n kube-system --context "${PROJECT_NAME}-verify" \
        --field-selector=status.phase=Running \
        --no-headers 2>/dev/null | wc -l || echo "0")

    if [[ "$running_pods" -gt 0 ]]; then
        check_pass "System pods running: $running_pods"
    else
        check_warn "No running system pods found"
    fi

    # Check for Aura namespace
    if kubectl get namespace "$PROJECT_NAME" --context "${PROJECT_NAME}-verify" &>/dev/null; then
        check_pass "Namespace $PROJECT_NAME exists"

        # Check Aura pods
        local aura_pods
        aura_pods=$(kubectl get pods -n "$PROJECT_NAME" --context "${PROJECT_NAME}-verify" \
            --field-selector=status.phase=Running \
            --no-headers 2>/dev/null | wc -l || echo "0")

        if [[ "$aura_pods" -gt 0 ]]; then
            check_pass "Aura pods running: $aura_pods"
        else
            check_info "No Aura pods running (application not yet deployed)"
        fi
    else
        check_info "Namespace $PROJECT_NAME not found (application not yet deployed)"
    fi

    # Cleanup context
    kubectl config delete-context "${PROJECT_NAME}-verify" &>/dev/null || true
}

# =============================================================================
# Summary
# =============================================================================

print_summary() {
    log_section "Verification Summary"

    local total=$((PASSED + FAILED + WARNINGS))

    echo -e "  Total checks:  $total"
    echo -e "  ${GREEN}Passed:${NC}        $PASSED"
    echo -e "  ${RED}Failed:${NC}        $FAILED"
    echo -e "  ${YELLOW}Warnings:${NC}      $WARNINGS"
    echo ""

    if [[ $FAILED -eq 0 ]]; then
        if [[ $WARNINGS -eq 0 ]]; then
            echo -e "  ${GREEN}${BOLD}ALL CHECKS PASSED${NC}"
            echo ""
            echo "  Your Aura deployment is healthy and ready for use."
        else
            echo -e "  ${YELLOW}${BOLD}PASSED WITH WARNINGS${NC}"
            echo ""
            echo "  Your Aura deployment is functional but has some warnings."
            echo "  Review the warnings above for recommendations."
        fi
    else
        echo -e "  ${RED}${BOLD}VERIFICATION FAILED${NC}"
        echo ""
        echo "  Some critical checks failed. Please review the errors above"
        echo "  and ensure all required services are properly deployed."
    fi

    echo ""
    echo "  ${BOLD}Deployment Details:${NC}"
    echo "  ────────────────────────────────────────"
    echo "  Project:     $PROJECT_NAME"
    echo "  Environment: $ENVIRONMENT"
    echo "  Region:      $AWS_REGION"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

main() {
    echo ""
    echo -e "${BOLD}${CYAN}Project Aura - Deployment Verification${NC}"
    echo -e "${CYAN}────────────────────────────────────────────────────────────────${NC}"
    echo ""
    echo "  Project:     $PROJECT_NAME"
    echo "  Environment: $ENVIRONMENT"
    echo "  Region:      $AWS_REGION"
    echo ""

    # Run all verification checks
    verify_cloudformation_stacks
    verify_eks_cluster
    verify_neptune
    verify_opensearch
    verify_s3_buckets
    verify_iam_roles
    verify_security_groups
    verify_bedrock_access
    verify_kubernetes_resources

    # Print summary
    print_summary

    # Exit with appropriate code
    if [[ $FAILED -gt 0 ]]; then
        exit 1
    elif [[ $WARNINGS -gt 0 ]]; then
        exit 2
    else
        exit 0
    fi
}

main
