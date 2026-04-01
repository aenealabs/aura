#!/bin/bash
# Deploy AWS Load Balancer Controller to EKS
#
# =============================================================================
# IMPORTANT: CI/CD vs Manual Deployment
# =============================================================================
# This script is for LOCAL DEVELOPMENT convenience only.
# For CI/CD deployments, use CodeBuild:
#   aws codebuild start-build --project-name aura-compute-deploy-${ENVIRONMENT}
#
# Per CLAUDE.md guidelines:
# - CodeBuild is the ONLY authoritative deployment method for production
# - Manual deploys break audit trail and IAM consistency
# =============================================================================
#
# Usage: ./deploy-alb-controller.sh [environment]

set -euo pipefail

# Check if running in CI/CD context - if so, recommend CodeBuild
if [ -n "${CODEBUILD_BUILD_ID:-}" ] || [ -n "${CI:-}" ] || [ -n "${GITHUB_ACTIONS:-}" ]; then
    echo "=============================================="
    echo "WARNING: Running in CI/CD context"
    echo "=============================================="
    echo "This script should NOT be used in CI/CD pipelines."
    echo "Use CodeBuild instead:"
    echo "  aws codebuild start-build --project-name aura-compute-deploy-\${ENVIRONMENT}"
    echo ""
    echo "Continuing anyway... (override with USE_MANUAL_DEPLOY=true)"
    if [ "${USE_MANUAL_DEPLOY:-}" != "true" ]; then
        exit 1
    fi
fi

ENVIRONMENT="${1:-dev}"
PROJECT_NAME="aura"
AWS_REGION="us-east-1"
CLUSTER_NAME="${PROJECT_NAME}-cluster-${ENVIRONMENT}"
CONTROLLER_VERSION="v2.7.1"

echo "=============================================="
echo "AWS Load Balancer Controller Deployment"
echo "=============================================="
echo "Environment: ${ENVIRONMENT}"
echo "Cluster: ${CLUSTER_NAME}"
echo "Controller Version: ${CONTROLLER_VERSION}"
echo ""

# Check prerequisites
echo "Checking prerequisites..."
command -v aws >/dev/null 2>&1 || { echo "aws CLI required but not found"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "kubectl required but not found"; exit 1; }
command -v helm >/dev/null 2>&1 || { echo "helm required but not found"; exit 1; }

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account: ${AWS_ACCOUNT_ID}"

# Get VPC ID from EKS cluster
VPC_ID=$(aws eks describe-cluster \
    --name "${CLUSTER_NAME}" \
    --region "${AWS_REGION}" \
    --query "cluster.resourcesVpcConfig.vpcId" \
    --output text)
echo "VPC ID: ${VPC_ID}"

# Get OIDC provider URL
OIDC_PROVIDER=$(aws eks describe-cluster \
    --name "${CLUSTER_NAME}" \
    --region "${AWS_REGION}" \
    --query "cluster.identity.oidc.issuer" \
    --output text | sed 's|https://||')
echo "OIDC Provider: ${OIDC_PROVIDER}"

# Step 1: Deploy CloudFormation stack for IAM resources
echo ""
echo "Step 1: Deploying IAM resources via CloudFormation..."
STACK_NAME="${PROJECT_NAME}-alb-controller-${ENVIRONMENT}"

aws cloudformation deploy \
    --stack-name "${STACK_NAME}" \
    --template-file "$(dirname "$0")/../cloudformation/alb-controller.yaml" \
    --parameter-overrides \
        Environment="${ENVIRONMENT}" \
        ProjectName="${PROJECT_NAME}" \
        OIDCProviderArn="arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/${OIDC_PROVIDER}" \
        OIDCProviderURL="${OIDC_PROVIDER}" \
        ClusterName="${CLUSTER_NAME}" \
        VpcId="${VPC_ID}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "${AWS_REGION}" \
    --no-fail-on-empty-changeset

# Get the role ARN from CloudFormation output
ALB_CONTROLLER_ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='ALBControllerRoleArn'].OutputValue" \
    --output text)
echo "ALB Controller Role ARN: ${ALB_CONTROLLER_ROLE_ARN}"

# Step 2: Update kubeconfig
echo ""
echo "Step 2: Updating kubeconfig..."
aws eks update-kubeconfig --name "${CLUSTER_NAME}" --region "${AWS_REGION}"

# Step 3: Create service account with IRSA annotation
echo ""
echo "Step 3: Creating service account..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: aws-load-balancer-controller
  namespace: kube-system
  labels:
    app.kubernetes.io/name: aws-load-balancer-controller
    app.kubernetes.io/component: controller
  annotations:
    eks.amazonaws.com/role-arn: ${ALB_CONTROLLER_ROLE_ARN}
EOF

# Step 4: Install AWS Load Balancer Controller using Helm
echo ""
echo "Step 4: Installing AWS Load Balancer Controller via Helm..."

# Add the EKS Helm repo
helm repo add eks https://aws.github.io/eks-charts
helm repo update

# Install or upgrade the controller
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
    --namespace kube-system \
    --set clusterName="${CLUSTER_NAME}" \
    --set serviceAccount.create=false \
    --set serviceAccount.name=aws-load-balancer-controller \
    --set region="${AWS_REGION}" \
    --set vpcId="${VPC_ID}" \
    --set image.tag="${CONTROLLER_VERSION}" \
    --wait

# Step 5: Create IngressClass
echo ""
echo "Step 5: Creating IngressClass..."
kubectl apply -f "$(dirname "$0")/../kubernetes/alb-controller/ingress-class.yaml"

# Step 6: Verify deployment
echo ""
echo "Step 6: Verifying deployment..."
kubectl get deployment -n kube-system aws-load-balancer-controller
kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller

# Wait for controller to be ready
echo ""
echo "Waiting for controller pods to be ready..."
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=aws-load-balancer-controller \
    -n kube-system \
    --timeout=120s

echo ""
echo "=============================================="
echo "AWS Load Balancer Controller deployed successfully!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "1. Create ACM certificate for your domain"
echo "2. Update aura-api-ingress.yaml with certificate ARN"
echo "3. Deploy ingress: kubectl apply -f deploy/kubernetes/alb-controller/aura-api-ingress.yaml"
echo ""
echo "To verify ALB creation after deploying ingress:"
echo "  kubectl get ingress aura-api-ingress"
echo "  aws elbv2 describe-load-balancers --query 'LoadBalancers[?contains(LoadBalancerName, \`k8s-\`)].DNSName'"
