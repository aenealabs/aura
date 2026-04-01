#!/bin/bash
# =============================================================================
# Project Aura - Kubernetes Configuration Generator
# =============================================================================
# Generates Kustomize overlays from CloudFormation stack outputs.
# This script solves the problem of hardcoded values in Kubernetes manifests.
#
# USAGE:
#   ./deploy/scripts/generate-k8s-config.sh <environment> [region]
#
# EXAMPLES:
#   ./deploy/scripts/generate-k8s-config.sh dev
#   ./deploy/scripts/generate-k8s-config.sh qa us-east-1
#   ./deploy/scripts/generate-k8s-config.sh prod us-gov-west-1
#
# PREREQUISITES:
#   - AWS CLI configured with appropriate credentials
#   - CloudFormation stacks deployed: networking, neptune, opensearch, dynamodb
#   - jq installed for JSON parsing
#
# OUTPUTS:
#   - deploy/kubernetes/aura-api/overlays/{env}/kustomization.yaml
#   - deploy/kubernetes/agent-orchestrator/overlays/{env}/kustomization.yaml
#   - SSM parameters for each endpoint
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
    echo -e "${BLUE}[INFO]${NC} $1" >&2
}

# Capitalize first letter (Bash 3.2 compatible - macOS default)
capitalize_first() {
    local str="$1"
    echo "$(echo "${str:0:1}" | tr '[:lower:]' '[:upper:]')${str:1}"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

usage() {
    cat << EOF
Usage: $0 <environment> [region]

Arguments:
  environment   Required. One of: dev, qa, prod
  region        Optional. AWS region (default: us-east-1, GovCloud: us-gov-west-1)

Examples:
  $0 dev                    # Generate configs for dev
  $0 qa us-east-1           # Generate configs for qa
  $0 prod us-gov-west-1     # Generate configs for prod (GovCloud)

Prerequisites:
  1. AWS CLI configured with credentials for the target account
  2. CloudFormation stacks deployed (foundation, data, compute layers)
  3. jq installed: brew install jq (macOS) or apt install jq (Linux)
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

    # Check jq
    if ! command -v jq &> /dev/null; then
        log_error "jq not found. Please install: brew install jq (macOS) or apt install jq (Linux)"
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi

    log_success "Prerequisites check passed"
}

get_stack_output() {
    local stack_name="$1"
    local output_key="$2"
    local default_value="${3:-}"

    local value
    value=$(aws cloudformation describe-stacks \
        --stack-name "${stack_name}" \
        --query "Stacks[0].Outputs[?OutputKey=='${output_key}'].OutputValue" \
        --output text \
        --region "${REGION}" 2>/dev/null || echo "")

    if [ -z "$value" ] || [ "$value" = "None" ]; then
        if [ -n "$default_value" ]; then
            echo "$default_value"
        else
            log_warning "Could not get ${output_key} from ${stack_name}"
            echo ""
        fi
    else
        echo "$value"
    fi
}

get_account_id() {
    aws sts get-caller-identity --query 'Account' --output text
}

collect_stack_outputs() {
    log_info "Collecting CloudFormation stack outputs..."

    # Get AWS Account ID
    AWS_ACCOUNT_ID=$(get_account_id)
    log_info "AWS Account ID: ${AWS_ACCOUNT_ID}"

    # Neptune endpoint
    NEPTUNE_STACK="${PROJECT_NAME}-neptune-${ENVIRONMENT}"
    NEPTUNE_ENDPOINT=$(get_stack_output "${NEPTUNE_STACK}" "ClusterEndpoint" "")
    if [ -z "$NEPTUNE_ENDPOINT" ]; then
        NEPTUNE_ENDPOINT=$(get_stack_output "${NEPTUNE_STACK}" "NeptuneClusterEndpoint" "")
    fi
    log_info "Neptune Endpoint: ${NEPTUNE_ENDPOINT:-NOT_DEPLOYED}"

    # OpenSearch endpoint
    OPENSEARCH_STACK="${PROJECT_NAME}-opensearch-${ENVIRONMENT}"
    OPENSEARCH_ENDPOINT=$(get_stack_output "${OPENSEARCH_STACK}" "DomainEndpoint" "")
    if [ -z "$OPENSEARCH_ENDPOINT" ]; then
        OPENSEARCH_ENDPOINT=$(get_stack_output "${OPENSEARCH_STACK}" "OpenSearchDomainEndpoint" "")
    fi
    log_info "OpenSearch Endpoint: ${OPENSEARCH_ENDPOINT:-NOT_DEPLOYED}"

    # DynamoDB table names
    DYNAMODB_STACK="${PROJECT_NAME}-dynamodb-${ENVIRONMENT}"
    APPROVAL_TABLE="${PROJECT_NAME}-approval-requests-${ENVIRONMENT}"
    WORKFLOW_TABLE="${PROJECT_NAME}-patch-workflows-${ENVIRONMENT}"
    log_info "Approval Table: ${APPROVAL_TABLE}"
    log_info "Workflow Table: ${WORKFLOW_TABLE}"

    # SNS Topic ARN for HITL notifications
    SANDBOX_STACK="${PROJECT_NAME}-sandbox-${ENVIRONMENT}"
    HITL_SNS_TOPIC_ARN=$(get_stack_output "${SANDBOX_STACK}" "HITLNotificationTopicArn" "")
    if [ -z "$HITL_SNS_TOPIC_ARN" ]; then
        # Construct if not available
        HITL_SNS_TOPIC_ARN="arn:aws:sns:${REGION}:${AWS_ACCOUNT_ID}:${PROJECT_NAME}-hitl-notifications-${ENVIRONMENT}"
    fi
    log_info "HITL SNS Topic: ${HITL_SNS_TOPIC_ARN}"

    # IRSA Role ARN
    IRSA_STACK="${PROJECT_NAME}-irsa-api-${ENVIRONMENT}"
    IRSA_ROLE_ARN=$(get_stack_output "${IRSA_STACK}" "ApiIrsaRoleArn" "")
    if [ -z "$IRSA_ROLE_ARN" ]; then
        # Construct if not available
        IRSA_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${PROJECT_NAME}-api-irsa-role-${ENVIRONMENT}"
    fi
    log_info "IRSA Role ARN: ${IRSA_ROLE_ARN}"

    # ElastiCache endpoint
    ELASTICACHE_STACK="${PROJECT_NAME}-elasticache-${ENVIRONMENT}"
    REDIS_ENDPOINT=$(get_stack_output "${ELASTICACHE_STACK}" "RedisEndpoint" "")
    log_info "Redis Endpoint: ${REDIS_ENDPOINT:-NOT_DEPLOYED}"

    # Networking outputs for ALB controller
    NETWORKING_STACK="${PROJECT_NAME}-networking-${ENVIRONMENT}"
    VPC_ID=$(get_stack_output "${NETWORKING_STACK}" "VpcId" "")
    PUBLIC_SUBNET_IDS=$(get_stack_output "${NETWORKING_STACK}" "PublicSubnetIds" "")
    log_info "VPC ID: ${VPC_ID:-NOT_DEPLOYED}"
    log_info "Public Subnets: ${PUBLIC_SUBNET_IDS:-NOT_DEPLOYED}"

    # Security outputs for ALB
    SECURITY_STACK="${PROJECT_NAME}-security-${ENVIRONMENT}"
    ALB_SECURITY_GROUP=$(get_stack_output "${SECURITY_STACK}" "AlbSecurityGroupId" "")
    log_info "ALB Security Group: ${ALB_SECURITY_GROUP:-NOT_DEPLOYED}"

    # WAF outputs
    WAF_STACK="${PROJECT_NAME}-waf-${ENVIRONMENT}"
    WAF_ACL_ARN=$(get_stack_output "${WAF_STACK}" "WebAclArn" "")
    log_info "WAF ACL ARN: ${WAF_ACL_ARN:-NOT_DEPLOYED}"

    # EKS cluster name
    EKS_CLUSTER_NAME="${PROJECT_NAME}-cluster-${ENVIRONMENT}"
    log_info "EKS Cluster: ${EKS_CLUSTER_NAME}"

    # S3 bucket for blocklist
    BLOCKLIST_BUCKET="${PROJECT_NAME}-blocklist-config-${ENVIRONMENT}"
    log_info "Blocklist Bucket: ${BLOCKLIST_BUCKET}"

    log_success "Stack outputs collected"
}

store_ssm_parameters() {
    log_info "Storing configuration in SSM Parameter Store..."

    local params_stored=0

    # Store Neptune endpoint
    if [ -n "$NEPTUNE_ENDPOINT" ]; then
        aws ssm put-parameter \
            --name "/${PROJECT_NAME}/${ENVIRONMENT}/neptune-endpoint" \
            --value "${NEPTUNE_ENDPOINT}" \
            --type String \
            --overwrite \
            --region "${REGION}" > /dev/null
        ((++params_stored))
    fi

    # Store OpenSearch endpoint
    if [ -n "$OPENSEARCH_ENDPOINT" ]; then
        aws ssm put-parameter \
            --name "/${PROJECT_NAME}/${ENVIRONMENT}/opensearch-endpoint" \
            --value "${OPENSEARCH_ENDPOINT}" \
            --type String \
            --overwrite \
            --region "${REGION}" > /dev/null
        ((++params_stored))
    fi

    # Store HITL SNS Topic ARN
    if [ -n "$HITL_SNS_TOPIC_ARN" ]; then
        aws ssm put-parameter \
            --name "/${PROJECT_NAME}/${ENVIRONMENT}/hitl-sns-topic-arn" \
            --value "${HITL_SNS_TOPIC_ARN}" \
            --type String \
            --overwrite \
            --region "${REGION}" > /dev/null
        ((++params_stored))
    fi

    # Store Redis endpoint
    if [ -n "$REDIS_ENDPOINT" ]; then
        aws ssm put-parameter \
            --name "/${PROJECT_NAME}/${ENVIRONMENT}/redis-endpoint" \
            --value "${REDIS_ENDPOINT}" \
            --type String \
            --overwrite \
            --region "${REGION}" > /dev/null
        ((++params_stored))
    fi

    # Store Account ID
    aws ssm put-parameter \
        --name "/${PROJECT_NAME}/${ENVIRONMENT}/account-id" \
        --value "${AWS_ACCOUNT_ID}" \
        --type String \
        --overwrite \
        --region "${REGION}" > /dev/null
    ((++params_stored))

    # Store Region
    aws ssm put-parameter \
        --name "/${PROJECT_NAME}/${ENVIRONMENT}/region" \
        --value "${REGION}" \
        --type String \
        --overwrite \
        --region "${REGION}" > /dev/null
    ((++params_stored))

    log_success "Stored ${params_stored} SSM parameters"
}

generate_aura_api_overlay() {
    log_info "Generating aura-api Kustomize overlay for ${ENVIRONMENT}..."

    local OVERLAY_DIR="${REPO_ROOT}/deploy/kubernetes/aura-api/overlays/${ENVIRONMENT}"
    mkdir -p "${OVERLAY_DIR}"

    # Determine dashboard URL based on environment
    local DASHBOARD_URL
    case "${ENVIRONMENT}" in
        dev)
            DASHBOARD_URL="https://aura.aenealabs.com/approvals"
            ;;
        qa)
            DASHBOARD_URL="https://qa.aura.aenealabs.com/approvals"
            ;;
        prod)
            DASHBOARD_URL="https://app.aura.aenealabs.com/approvals"
            ;;
        *)
            DASHBOARD_URL="https://${ENVIRONMENT}.aura.aenealabs.com/approvals"
            ;;
    esac

    cat > "${OVERLAY_DIR}/kustomization.yaml" << EOF
# Project Aura - API Kustomization ($(capitalize_first "${ENVIRONMENT}") Environment)
# AUTO-GENERATED by deploy/scripts/generate-k8s-config.sh
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
#
# DO NOT EDIT MANUALLY - Re-run the generation script to update values.
#
# Usage:
#   kubectl apply -k deploy/kubernetes/aura-api/overlays/${ENVIRONMENT}/

apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: default

resources:
  - ../../base

# Environment-specific labels
labels:
  - pairs:
      environment: ${ENVIRONMENT}
      project: ${PROJECT_NAME}
    includeSelectors: false

# Image override for ${ENVIRONMENT} environment
images:
  - name: aura-api
    newName: ${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${PROJECT_NAME}-api-${ENVIRONMENT}
    newTag: latest

# Patch ConfigMap with ${ENVIRONMENT}-specific values
patches:
  - target:
      kind: ConfigMap
      name: aura-api-config
    patch: |-
      - op: add
        path: /data/ENVIRONMENT
        value: "${ENVIRONMENT}"
      - op: add
        path: /data/AWS_REGION
        value: "${REGION}"
      - op: add
        path: /data/NEPTUNE_ENDPOINT
        value: "${NEPTUNE_ENDPOINT:-PENDING_DEPLOYMENT}"
      - op: add
        path: /data/NEPTUNE_PORT
        value: "8182"
      - op: add
        path: /data/OPENSEARCH_ENDPOINT
        value: "${OPENSEARCH_ENDPOINT:-PENDING_DEPLOYMENT}"
      - op: add
        path: /data/OPENSEARCH_PORT
        value: "443"
      - op: add
        path: /data/HITL_SNS_TOPIC_ARN
        value: "${HITL_SNS_TOPIC_ARN}"
      - op: add
        path: /data/HITL_DASHBOARD_URL
        value: "${DASHBOARD_URL}"
      - op: add
        path: /data/APPROVAL_TABLE_NAME
        value: "${APPROVAL_TABLE}"
      - op: add
        path: /data/WORKFLOW_TABLE_NAME
        value: "${WORKFLOW_TABLE}"
  - target:
      kind: ServiceAccount
      name: aura-api
    patch: |-
      - op: add
        path: /metadata/annotations/eks.amazonaws.com~1role-arn
        value: "${IRSA_ROLE_ARN}"
      - op: add
        path: /metadata/labels/environment
        value: "${ENVIRONMENT}"
  - target:
      kind: Rollout
      name: aura-api
    patch: |-
      - op: add
        path: /metadata/labels/environment
        value: "${ENVIRONMENT}"
      - op: add
        path: /spec/template/metadata/labels/environment
        value: "${ENVIRONMENT}"
  - target:
      kind: Service
      name: aura-api
    patch: |-
      - op: add
        path: /metadata/labels/environment
        value: "${ENVIRONMENT}"
  - target:
      kind: Service
      name: aura-api-canary
    patch: |-
      - op: add
        path: /metadata/labels/environment
        value: "${ENVIRONMENT}"
EOF

    log_success "Generated ${OVERLAY_DIR}/kustomization.yaml"
}

generate_agent_orchestrator_overlay() {
    log_info "Generating agent-orchestrator Kustomize overlay for ${ENVIRONMENT}..."

    local OVERLAY_DIR="${REPO_ROOT}/deploy/kubernetes/agent-orchestrator/overlays/${ENVIRONMENT}"
    mkdir -p "${OVERLAY_DIR}"

    cat > "${OVERLAY_DIR}/kustomization.yaml" << EOF
# Project Aura - Agent Orchestrator Kustomization ($(capitalize_first "${ENVIRONMENT}") Environment)
# AUTO-GENERATED by deploy/scripts/generate-k8s-config.sh
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
#
# DO NOT EDIT MANUALLY - Re-run the generation script to update values.
#
# Usage:
#   kubectl apply -k deploy/kubernetes/agent-orchestrator/overlays/${ENVIRONMENT}/

apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: default

resources:
  - ../../base

# Environment-specific labels
labels:
  - pairs:
      environment: ${ENVIRONMENT}
      project: ${PROJECT_NAME}
    includeSelectors: false

# Image override for ${ENVIRONMENT} environment
images:
  - name: aura-agent-orchestrator
    newName: ${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${PROJECT_NAME}-agent-orchestrator-${ENVIRONMENT}
    newTag: latest

# Patch ConfigMap with ${ENVIRONMENT}-specific values
patches:
  - target:
      kind: ConfigMap
      name: aura-agent-orchestrator-config
    patch: |-
      - op: replace
        path: /data/ENVIRONMENT
        value: "${ENVIRONMENT}"
      - op: add
        path: /data/AWS_REGION
        value: "${REGION}"
      - op: add
        path: /data/AWS_ACCOUNT_ID
        value: "${AWS_ACCOUNT_ID}"
      - op: add
        path: /data/SQS_QUEUE_URL
        value: "https://sqs.${REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/${PROJECT_NAME}-orchestrator-tasks-${ENVIRONMENT}"
      - op: replace
        path: /data/NEPTUNE_ENDPOINT
        value: "${NEPTUNE_ENDPOINT:-PENDING_DEPLOYMENT}"
      - op: replace
        path: /data/NEPTUNE_PORT
        value: "8182"
      - op: replace
        path: /data/OPENSEARCH_ENDPOINT
        value: "${OPENSEARCH_ENDPOINT:-PENDING_DEPLOYMENT}"
      - op: replace
        path: /data/OPENSEARCH_PORT
        value: "443"
      - op: replace
        path: /metadata/labels/environment
        value: "${ENVIRONMENT}"
  - target:
      kind: Deployment
      name: aura-agent-orchestrator
    patch: |-
      - op: replace
        path: /metadata/labels/environment
        value: "${ENVIRONMENT}"
      - op: replace
        path: /spec/template/metadata/labels/environment
        value: "${ENVIRONMENT}"
EOF

    log_success "Generated ${OVERLAY_DIR}/kustomization.yaml"
}

generate_integration_test_config() {
    log_info "Generating integration test ConfigMap for ${ENVIRONMENT}..."

    local CONFIG_DIR="${REPO_ROOT}/deploy/kubernetes/test-configs"
    mkdir -p "${CONFIG_DIR}"

    cat > "${CONFIG_DIR}/integration-test-config-${ENVIRONMENT}.yaml" << EOF
# Project Aura - Integration Test Configuration ($(capitalize_first "${ENVIRONMENT}") Environment)
# AUTO-GENERATED by deploy/scripts/generate-k8s-config.sh
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
#
# Usage:
#   kubectl apply -f deploy/kubernetes/test-configs/integration-test-config-${ENVIRONMENT}.yaml

apiVersion: v1
kind: ConfigMap
metadata:
  name: integration-test-config
  namespace: default
  labels:
    app: integration-tests
    environment: ${ENVIRONMENT}
    project: ${PROJECT_NAME}
data:
  ENVIRONMENT: "${ENVIRONMENT}"
  AWS_REGION: "${REGION}"
  AWS_ACCOUNT_ID: "${AWS_ACCOUNT_ID}"
  NEPTUNE_ENDPOINT: "${NEPTUNE_ENDPOINT:-PENDING_DEPLOYMENT}"
  NEPTUNE_PORT: "8182"
  OPENSEARCH_ENDPOINT: "${OPENSEARCH_ENDPOINT:-PENDING_DEPLOYMENT}"
  OPENSEARCH_PORT: "443"
  APPROVAL_TABLE_NAME: "${APPROVAL_TABLE}"
  WORKFLOW_TABLE_NAME: "${WORKFLOW_TABLE}"
  HITL_SNS_TOPIC_ARN: "${HITL_SNS_TOPIC_ARN}"
EOF

    log_success "Generated ${CONFIG_DIR}/integration-test-config-${ENVIRONMENT}.yaml"
}

generate_memory_service_overlay() {
    log_info "Generating memory-service Kustomize overlay for ${ENVIRONMENT}..."

    local OVERLAY_DIR="${REPO_ROOT}/deploy/kubernetes/memory-service/overlays/${ENVIRONMENT}"
    mkdir -p "${OVERLAY_DIR}"

    # Memory service IRSA role
    local MEMORY_IRSA_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${PROJECT_NAME}-memory-service-irsa-role-${ENVIRONMENT}"

    # Environment-specific DynamoDB table and S3 bucket
    local MEMORY_STATE_TABLE="${PROJECT_NAME}-neural-memory-${ENVIRONMENT}"
    local MODEL_S3_BUCKET="${PROJECT_NAME}-models-${ENVIRONMENT}"

    cat > "${OVERLAY_DIR}/kustomization.yaml" << EOF
# Project Aura - Memory Service Kustomization ($(capitalize_first "${ENVIRONMENT}") Environment)
# AUTO-GENERATED by deploy/scripts/generate-k8s-config.sh
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
#
# DO NOT EDIT MANUALLY - Re-run the generation script to update values.
#
# Usage:
#   kubectl apply -k deploy/kubernetes/memory-service/overlays/${ENVIRONMENT}/

apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: default

resources:
  - ../../base

labels:
  - pairs:
      environment: ${ENVIRONMENT}
      project: ${PROJECT_NAME}
    includeSelectors: false

images:
  - name: aura-memory-service
    newName: ${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${PROJECT_NAME}-memory-service-${ENVIRONMENT}
    newTag: latest

patches:
  - target:
      kind: ServiceAccount
      name: aura-memory-service
    patch: |-
      - op: replace
        path: /metadata/annotations/eks.amazonaws.com~1role-arn
        value: "${MEMORY_IRSA_ROLE_ARN}"
      - op: replace
        path: /metadata/labels/environment
        value: "${ENVIRONMENT}"
  - target:
      kind: Deployment
      name: aura-memory-service
    patch: |-
      - op: replace
        path: /metadata/labels/environment
        value: "${ENVIRONMENT}"
      - op: replace
        path: /spec/template/metadata/labels/environment
        value: "${ENVIRONMENT}"
      - op: replace
        path: /spec/template/spec/containers/0/resources/requests/memory
        value: "512Mi"
      - op: replace
        path: /spec/template/spec/containers/0/resources/limits/memory
        value: "1Gi"
      - op: replace
        path: /spec/template/spec/volumes/0/emptyDir/sizeLimit
        value: "5Gi"
      - op: replace
        path: /spec/template/spec/volumes/1/emptyDir/sizeLimit
        value: "1Gi"
      - op: replace
        path: /spec/template/spec/volumes/2/emptyDir/sizeLimit
        value: "512Mi"
  - target:
      kind: ConfigMap
      name: aura-memory-service-config
    patch: |-
      - op: replace
        path: /data/ENVIRONMENT
        value: "${ENVIRONMENT}"
      - op: replace
        path: /data/AWS_REGION
        value: "${REGION}"
      - op: replace
        path: /data/NEPTUNE_ENDPOINT
        value: "${NEPTUNE_ENDPOINT:-PENDING_DEPLOYMENT}"
      - op: replace
        path: /data/OPENSEARCH_ENDPOINT
        value: "${OPENSEARCH_ENDPOINT:-PENDING_DEPLOYMENT}"
      - op: replace
        path: /data/MEMORY_STATE_TABLE
        value: "${MEMORY_STATE_TABLE}"
      - op: replace
        path: /data/MODEL_S3_BUCKET
        value: "${MODEL_S3_BUCKET}"
      - op: replace
        path: /metadata/labels/environment
        value: "${ENVIRONMENT}"
EOF

    log_success "Generated ${OVERLAY_DIR}/kustomization.yaml"
}

generate_meta_orchestrator_overlay() {
    log_info "Generating meta-orchestrator Kustomize overlay for ${ENVIRONMENT}..."

    local OVERLAY_DIR="${REPO_ROOT}/deploy/kubernetes/meta-orchestrator/overlays/${ENVIRONMENT}"
    mkdir -p "${OVERLAY_DIR}"

    # Meta orchestrator IRSA role
    local META_IRSA_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${PROJECT_NAME}-meta-orchestrator-irsa-${ENVIRONMENT}"

    cat > "${OVERLAY_DIR}/kustomization.yaml" << EOF
# Project Aura - Meta Orchestrator Kustomization ($(capitalize_first "${ENVIRONMENT}") Environment)
# AUTO-GENERATED by deploy/scripts/generate-k8s-config.sh
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
#
# DO NOT EDIT MANUALLY - Re-run the generation script to update values.
#
# Usage:
#   kubectl apply -k deploy/kubernetes/meta-orchestrator/overlays/${ENVIRONMENT}/

apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: aura

resources:
  - ../../base

labels:
  - pairs:
      environment: ${ENVIRONMENT}
      project: ${PROJECT_NAME}
    includeSelectors: false

images:
  - name: meta-orchestrator
    newName: ${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${PROJECT_NAME}-meta-orchestrator-${ENVIRONMENT}
    newTag: latest

configMapGenerator:
  - name: meta-orchestrator-config
    behavior: replace
    literals:
      - ENVIRONMENT=${ENVIRONMENT}
      - PROJECT_NAME=${PROJECT_NAME}
      - LOG_LEVEL=INFO
      - NEPTUNE_ENDPOINT=${NEPTUNE_ENDPOINT:-neptune.aura.local}:8182
      - OPENSEARCH_ENDPOINT=${OPENSEARCH_ENDPOINT:-opensearch.aura.local}:9200
      - MAX_EXECUTION_TIME_SECONDS=1800
      - MAX_AGENTS_PER_TASK=10
      - ENABLE_METRICS=true

patches:
  - target:
      kind: ServiceAccount
      name: meta-orchestrator
    patch: |-
      - op: replace
        path: /metadata/annotations/eks.amazonaws.com~1role-arn
        value: "${META_IRSA_ROLE_ARN}"
EOF

    log_success "Generated ${OVERLAY_DIR}/kustomization.yaml"
}

generate_aura_frontend_overlay() {
    log_info "Generating aura-frontend Kustomize overlay for ${ENVIRONMENT}..."

    local OVERLAY_DIR="${REPO_ROOT}/deploy/kubernetes/aura-frontend/overlays/${ENVIRONMENT}"
    mkdir -p "${OVERLAY_DIR}"

    cat > "${OVERLAY_DIR}/kustomization.yaml" << EOF
# Project Aura - Frontend Kustomization ($(capitalize_first "${ENVIRONMENT}") Environment)
# AUTO-GENERATED by deploy/scripts/generate-k8s-config.sh
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
#
# DO NOT EDIT MANUALLY - Re-run the generation script to update values.
#
# Usage:
#   kubectl apply -k deploy/kubernetes/aura-frontend/overlays/${ENVIRONMENT}/

apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: default

resources:
  - ../../base

labels:
  - pairs:
      environment: ${ENVIRONMENT}
      project: ${PROJECT_NAME}
      tier: frontend
    includeSelectors: false

images:
  - name: aura-frontend
    newName: ${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${PROJECT_NAME}-frontend-${ENVIRONMENT}
    newTag: latest

patches:
  - target:
      kind: Rollout
      name: aura-frontend
    patch: |-
      - op: replace
        path: /metadata/labels/environment
        value: "${ENVIRONMENT}"
      - op: replace
        path: /spec/template/metadata/labels/environment
        value: "${ENVIRONMENT}"
  - target:
      kind: Deployment
      name: aura-frontend
    patch: |-
      - op: replace
        path: /metadata/labels/environment
        value: "${ENVIRONMENT}"
      - op: replace
        path: /spec/template/metadata/labels/environment
        value: "${ENVIRONMENT}"
EOF

    log_success "Generated ${OVERLAY_DIR}/kustomization.yaml"
}

generate_alb_controller_values() {
    log_info "Generating ALB controller values for ${ENVIRONMENT}..."

    local VALUES_DIR="${REPO_ROOT}/deploy/kubernetes/alb-controller/overlays/${ENVIRONMENT}"
    mkdir -p "${VALUES_DIR}"

    # ALB controller IRSA role
    local ALB_IRSA_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${PROJECT_NAME}-alb-controller-role-${ENVIRONMENT}"

    cat > "${VALUES_DIR}/values.yaml" << EOF
# AWS Load Balancer Controller Helm Values ($(capitalize_first "${ENVIRONMENT}") Environment)
# AUTO-GENERATED by deploy/scripts/generate-k8s-config.sh
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
#
# Usage:
#   helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \\
#     -n kube-system -f deploy/kubernetes/alb-controller/overlays/${ENVIRONMENT}/values.yaml

clusterName: ${EKS_CLUSTER_NAME}
region: ${REGION}
vpcId: ${VPC_ID:-PENDING_DEPLOYMENT}

serviceAccount:
  create: true
  name: aws-load-balancer-controller
  annotations:
    eks.amazonaws.com/role-arn: ${ALB_IRSA_ROLE_ARN}

replicaCount: 2

resources:
  limits:
    cpu: 200m
    memory: 256Mi
  requests:
    cpu: 100m
    memory: 128Mi

enableShield: true
enableWaf: true
enableWafv2: true

logLevel: info

podDisruptionBudget:
  maxUnavailable: 1

affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
              - key: app.kubernetes.io/name
                operator: In
                values:
                  - aws-load-balancer-controller
          topologyKey: kubernetes.io/hostname

nodeSelector:
  kubernetes.io/os: linux
EOF

    log_success "Generated ${VALUES_DIR}/values.yaml"
}

generate_dnsmasq_blocklist_overlay() {
    log_info "Generating dnsmasq-blocklist-sync overlay for ${ENVIRONMENT}..."

    local OVERLAY_DIR="${REPO_ROOT}/deploy/kubernetes/dnsmasq-blocklist-sync/overlays/${ENVIRONMENT}"
    mkdir -p "${OVERLAY_DIR}"

    # Blocklist sync IRSA role
    local BLOCKLIST_IRSA_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${PROJECT_NAME}-blocklist-sync-role-${ENVIRONMENT}"

    cat > "${OVERLAY_DIR}/kustomization.yaml" << EOF
# Project Aura - DNS Blocklist Sync ($(capitalize_first "${ENVIRONMENT}") Environment)
# AUTO-GENERATED by deploy/scripts/generate-k8s-config.sh
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
#
# Usage:
#   kubectl apply -k deploy/kubernetes/dnsmasq-blocklist-sync/overlays/${ENVIRONMENT}/

apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: aura-network-services

resources:
  - ../../base

labels:
  - pairs:
      environment: ${ENVIRONMENT}
      project: ${PROJECT_NAME}
    includeSelectors: false

patches:
  - target:
      kind: ServiceAccount
      name: blocklist-sync
    patch: |-
      - op: replace
        path: /metadata/annotations/eks.amazonaws.com~1role-arn
        value: "${BLOCKLIST_IRSA_ROLE_ARN}"
  - target:
      kind: CronJob
      name: blocklist-sync
    patch: |-
      - op: replace
        path: /spec/jobTemplate/spec/template/spec/containers/0/env/0/value
        value: "${BLOCKLIST_BUCKET}"
      - op: replace
        path: /spec/jobTemplate/spec/template/spec/containers/0/env/1/value
        value: "dnsmasq/blocklist-${ENVIRONMENT}.conf"
      - op: replace
        path: /spec/jobTemplate/spec/template/spec/containers/0/env/4/value
        value: "${REGION}"
EOF

    log_success "Generated ${OVERLAY_DIR}/kustomization.yaml"
}

print_summary() {
    echo ""
    echo "=========================================="
    echo "KUBERNETES CONFIGURATION GENERATED"
    echo "=========================================="
    echo ""
    echo "Environment: ${ENVIRONMENT}"
    echo "Region:      ${REGION}"
    echo "Account ID:  ${AWS_ACCOUNT_ID}"
    echo ""
    echo "Generated Files:"
    echo "  - deploy/kubernetes/aura-api/overlays/${ENVIRONMENT}/kustomization.yaml"
    echo "  - deploy/kubernetes/agent-orchestrator/overlays/${ENVIRONMENT}/kustomization.yaml"
    echo "  - deploy/kubernetes/memory-service/overlays/${ENVIRONMENT}/kustomization.yaml"
    echo "  - deploy/kubernetes/meta-orchestrator/overlays/${ENVIRONMENT}/kustomization.yaml"
    echo "  - deploy/kubernetes/aura-frontend/overlays/${ENVIRONMENT}/kustomization.yaml"
    echo "  - deploy/kubernetes/alb-controller/overlays/${ENVIRONMENT}/values.yaml"
    echo "  - deploy/kubernetes/dnsmasq-blocklist-sync/overlays/${ENVIRONMENT}/kustomization.yaml"
    echo "  - deploy/kubernetes/test-configs/integration-test-config-${ENVIRONMENT}.yaml"
    echo ""
    echo "SSM Parameters Created:"
    echo "  - /${PROJECT_NAME}/${ENVIRONMENT}/neptune-endpoint"
    echo "  - /${PROJECT_NAME}/${ENVIRONMENT}/opensearch-endpoint"
    echo "  - /${PROJECT_NAME}/${ENVIRONMENT}/hitl-sns-topic-arn"
    echo "  - /${PROJECT_NAME}/${ENVIRONMENT}/redis-endpoint"
    echo "  - /${PROJECT_NAME}/${ENVIRONMENT}/account-id"
    echo "  - /${PROJECT_NAME}/${ENVIRONMENT}/region"
    echo ""
    echo "Next Steps:"
    echo "  1. Review generated overlays for correctness"
    echo "  2. Apply to Kubernetes cluster:"
    echo "     kubectl apply -k deploy/kubernetes/aura-api/overlays/${ENVIRONMENT}/"
    echo "     kubectl apply -k deploy/kubernetes/agent-orchestrator/overlays/${ENVIRONMENT}/"
    echo "     kubectl apply -k deploy/kubernetes/memory-service/overlays/${ENVIRONMENT}/"
    echo "     kubectl apply -k deploy/kubernetes/meta-orchestrator/overlays/${ENVIRONMENT}/"
    echo "     kubectl apply -k deploy/kubernetes/aura-frontend/overlays/${ENVIRONMENT}/"
    echo ""
    echo "  3. Apply integration test config:"
    echo "     kubectl apply -f deploy/kubernetes/test-configs/integration-test-config-${ENVIRONMENT}.yaml"
    echo ""

    # Warn if endpoints are missing
    if [ -z "$NEPTUNE_ENDPOINT" ] || [ -z "$OPENSEARCH_ENDPOINT" ]; then
        log_warning "Some endpoints are not yet deployed. Run this script again after Data layer deployment."
    fi
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
    echo "Project Aura - Kubernetes Config Generator"
    echo "=========================================="
    echo "Environment: ${ENVIRONMENT}"
    echo "Region:      ${REGION}"
    echo "Project:     ${PROJECT_NAME}"
    echo "=========================================="
    echo ""

    # Execute generation steps
    check_prerequisites
    collect_stack_outputs
    store_ssm_parameters
    generate_aura_api_overlay
    generate_agent_orchestrator_overlay
    generate_memory_service_overlay
    generate_meta_orchestrator_overlay
    generate_aura_frontend_overlay
    generate_alb_controller_values
    generate_dnsmasq_blocklist_overlay
    generate_integration_test_config
    print_summary

    log_success "Configuration generation complete!"
}

main "$@"
