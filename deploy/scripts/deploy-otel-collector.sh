#!/bin/bash
# deploy-otel-collector.sh - Deploy OpenTelemetry Collector to EKS
# ADR-028 Phase 1: OpenTelemetry Adoption
#
# =============================================================================
# IMPORTANT: CI/CD vs Manual Deployment
# =============================================================================
# This script is for LOCAL DEVELOPMENT convenience only.
# For CI/CD deployments, use CodeBuild:
#   aws codebuild start-build --project-name aura-observability-deploy-${ENVIRONMENT}
#
# Per CLAUDE.md guidelines:
# - CodeBuild is the ONLY authoritative deployment method for production
# - Manual deploys break audit trail and IAM consistency
# =============================================================================
#
# Prerequisites:
# - AWS CLI configured with appropriate credentials
# - kubectl configured for target EKS cluster
# - CloudFormation stack deployed (aura-otel-collector-dev)

set -e

# Check if running in CI/CD context - if so, recommend CodeBuild
if [ -n "$CODEBUILD_BUILD_ID" ] || [ -n "$CI" ] || [ -n "$GITHUB_ACTIONS" ]; then
    echo "========================================"
    echo "WARNING: Running in CI/CD context"
    echo "========================================"
    echo "This script should NOT be used in CI/CD pipelines."
    echo "Use CodeBuild instead:"
    echo "  aws codebuild start-build --project-name aura-observability-deploy-\${ENVIRONMENT}"
    echo ""
    echo "Continuing anyway... (override with USE_MANUAL_DEPLOY=true)"
    if [ "$USE_MANUAL_DEPLOY" != "true" ]; then
        exit 1
    fi
fi

# Configuration
ENVIRONMENT="${1:-dev}"
PROJECT_NAME="${2:-aura}"
AWS_REGION="${AWS_REGION:-us-east-1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="${SCRIPT_DIR}/../kubernetes/otel-collector"
CF_DIR="${SCRIPT_DIR}/../cloudformation"

echo "========================================"
echo "OpenTelemetry Collector Deployment"
echo "========================================"
echo "Environment: ${ENVIRONMENT}"
echo "Project: ${PROJECT_NAME}"
echo "Region: ${AWS_REGION}"
echo ""

# Check prerequisites
check_prerequisites() {
    echo "[1/6] Checking prerequisites..."

    if ! command -v aws &> /dev/null; then
        echo "ERROR: AWS CLI not found"
        exit 1
    fi

    if ! command -v kubectl &> /dev/null; then
        echo "ERROR: kubectl not found"
        exit 1
    fi

    # Verify AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        echo "ERROR: AWS credentials not valid"
        exit 1
    fi

    # Verify kubectl context
    if ! kubectl cluster-info &> /dev/null; then
        echo "ERROR: kubectl not configured for cluster"
        exit 1
    fi

    echo "  Prerequisites OK"
}

# Deploy CloudFormation stack for IAM resources
deploy_cloudformation() {
    echo ""
    echo "[2/6] Deploying CloudFormation IAM resources..."

    STACK_NAME="${PROJECT_NAME}-otel-collector-${ENVIRONMENT}"

    # Get OIDC provider info from EKS
    CLUSTER_NAME="${PROJECT_NAME}-cluster-${ENVIRONMENT}"

    OIDC_PROVIDER_ARN=$(aws eks describe-cluster \
        --name "${CLUSTER_NAME}" \
        --region "${AWS_REGION}" \
        --query "cluster.identity.oidc.issuer" \
        --output text 2>/dev/null | sed 's|https://||')

    if [ -z "${OIDC_PROVIDER_ARN}" ] || [ "${OIDC_PROVIDER_ARN}" == "None" ]; then
        echo "ERROR: Could not get OIDC provider URL from EKS cluster"
        exit 1
    fi

    OIDC_ARN="arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):oidc-provider/${OIDC_PROVIDER_ARN}"

    echo "  OIDC Provider ARN: ${OIDC_ARN}"
    echo "  OIDC Provider URL: ${OIDC_PROVIDER_ARN}"

    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" &> /dev/null; then
        echo "  Stack exists, updating..."
        ACTION="update-stack"
    else
        echo "  Creating new stack..."
        ACTION="create-stack"
    fi

    # Deploy stack
    aws cloudformation deploy \
        --stack-name "${STACK_NAME}" \
        --template-file "${CF_DIR}/otel-collector.yaml" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "${AWS_REGION}" \
        --parameter-overrides \
            Environment="${ENVIRONMENT}" \
            ProjectName="${PROJECT_NAME}" \
            OIDCProviderArn="${OIDC_ARN}" \
            OIDCProviderURL="${OIDC_PROVIDER_ARN}" \
        --no-fail-on-empty-changeset

    # Get role ARN from stack outputs
    OTEL_ROLE_ARN=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${AWS_REGION}" \
        --query "Stacks[0].Outputs[?OutputKey=='OTelCollectorRoleArn'].OutputValue" \
        --output text)

    echo "  OTel Collector Role ARN: ${OTEL_ROLE_ARN}"
}

# Create namespace
create_namespace() {
    echo ""
    echo "[3/6] Creating otel-system namespace..."

    kubectl apply -f "${K8S_DIR}/namespace.yaml"
    echo "  Namespace created/updated"
}

# Deploy ConfigMap
deploy_configmap() {
    echo ""
    echo "[4/6] Deploying OTel Collector ConfigMap..."

    # Substitute environment variables in configmap
    cat "${K8S_DIR}/configmap.yaml" | \
        sed "s/\${AWS_REGION}/${AWS_REGION}/g" | \
        sed "s/\${ENVIRONMENT}/${ENVIRONMENT}/g" | \
        kubectl apply -f -

    echo "  ConfigMap deployed"
}

# Deploy ServiceAccount, Deployment, and Service
deploy_collector() {
    echo ""
    echo "[5/6] Deploying OTel Collector..."

    # Update ServiceAccount with role ARN and apply
    cat "${K8S_DIR}/deployment.yaml" | \
        sed "s|\${OTEL_COLLECTOR_ROLE_ARN}|${OTEL_ROLE_ARN}|g" | \
        kubectl apply -f -

    echo "  Deployment created"

    # Wait for deployment to be ready
    echo "  Waiting for deployment to be ready..."
    kubectl rollout status deployment/otel-collector -n otel-system --timeout=300s

    echo "  OTel Collector deployed successfully"
}

# Verify deployment
verify_deployment() {
    echo ""
    echo "[6/6] Verifying deployment..."

    # Check pods
    echo ""
    echo "  Pods:"
    kubectl get pods -n otel-system -l app.kubernetes.io/name=otel-collector

    # Check service
    echo ""
    echo "  Service:"
    kubectl get svc -n otel-system otel-collector

    # Check health endpoint
    echo ""
    echo "  Health check:"
    POD_NAME=$(kubectl get pods -n otel-system -l app.kubernetes.io/name=otel-collector -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [ -n "${POD_NAME}" ]; then
        kubectl exec -n otel-system "${POD_NAME}" -- wget -q -O- http://localhost:13133/ 2>/dev/null || echo "  (Health check requires pod to be fully ready)"
    fi
}

# Print usage information
print_usage() {
    echo ""
    echo "========================================"
    echo "Deployment Complete!"
    echo "========================================"
    echo ""
    echo "OTel Collector is now running in the otel-system namespace."
    echo ""
    echo "OTLP Endpoints (within cluster):"
    echo "  gRPC: otel-collector.otel-system.svc.cluster.local:4317"
    echo "  HTTP: otel-collector.otel-system.svc.cluster.local:4318"
    echo ""
    echo "Configure your Python services with:"
    echo "  from src.services.otel_instrumentation import setup_otel"
    echo "  setup_otel("
    echo "      service_name='your-service',"
    echo "      environment='${ENVIRONMENT}',"
    echo "      otlp_endpoint='otel-collector.otel-system.svc.cluster.local:4317'"
    echo "  )"
    echo ""
    echo "Traces will be exported to AWS X-Ray"
    echo "Metrics will be exported to CloudWatch (namespace: Aura/OTel)"
    echo ""
    echo "View traces: AWS Console > CloudWatch > X-Ray traces"
    echo "View metrics: AWS Console > CloudWatch > Metrics > Aura/OTel"
}

# Main execution
main() {
    check_prerequisites
    deploy_cloudformation
    create_namespace
    deploy_configmap
    deploy_collector
    verify_deployment
    print_usage
}

# Run main
main
