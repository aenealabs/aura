#!/bin/bash
#
# Configure ArgoCD with GitHub App Authentication
#
# This script stores GitHub App credentials in SSM and configures ArgoCD
# to use them for repository access.
#
# Prerequisites:
#   - GitHub App created with Contents:Read-only permission
#   - Private key downloaded (.pem file)
#   - App installed on the repository
#
# Usage:
#   AWS_PROFILE=<profile> ./deploy/scripts/configure-argocd-github-app.sh <app-id> <installation-id> <private-key-file>
#
# Example:
#   AWS_PROFILE=<your-profile> ./deploy/scripts/configure-argocd-github-app.sh 123456 12345678 ~/Downloads/argocd-aura.pem
#

set -euo pipefail

# AWS credentials - uses standard AWS credential chain
# Set AWS_PROFILE before running, or ensure credentials are configured
# Example: AWS_PROFILE=<your-profile> ./deploy/scripts/configure-argocd-github-app.sh ...

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Validate arguments
if [[ $# -lt 3 ]]; then
    echo "Usage: AWS_PROFILE=<your-profile> $0 <app-id> <installation-id> <private-key-file>"
    echo ""
    echo "Arguments:"
    echo "  app-id            GitHub App ID (found at top of App settings page)"
    echo "  installation-id   Installation ID (from URL after installing App)"
    echo "  private-key-file  Path to downloaded .pem file"
    echo ""
    echo "Example:"
    echo "  AWS_PROFILE=<your-profile> $0 123456 12345678 ~/Downloads/argocd-aura.pem"
    exit 1
fi

APP_ID="$1"
INSTALLATION_ID="$2"
PRIVATE_KEY_FILE="$3"
AWS_REGION="${AWS_REGION:-us-east-1}"
REPO_URL="https://github.com/aenealabs/aura"

# Validate private key file exists
if [[ ! -f "$PRIVATE_KEY_FILE" ]]; then
    log_error "Private key file not found: $PRIVATE_KEY_FILE"
    exit 1
fi

# Validate private key format
if ! grep -q "BEGIN.*PRIVATE KEY" "$PRIVATE_KEY_FILE"; then
    log_error "Invalid private key format. File should contain PEM-encoded private key."
    exit 1
fi

log_info "==========================================="
log_info "ArgoCD GitHub App Configuration"
log_info "==========================================="
log_info "AWS Profile: ${AWS_PROFILE:-<default credential chain>}"
log_info "App ID: $APP_ID"
log_info "Installation ID: $INSTALLATION_ID"
log_info "Private Key: $PRIVATE_KEY_FILE"
log_info "Repository: $REPO_URL"
log_info ""

# Step 1: Store credentials in SSM
log_info "Storing credentials in SSM Parameter Store..."

aws ssm put-parameter \
    --name /aura/global/github-app-id \
    --value "$APP_ID" \
    --type String \
    --overwrite \
    --region "$AWS_REGION" \
    --no-cli-pager

aws ssm put-parameter \
    --name /aura/global/github-app-installation-id \
    --value "$INSTALLATION_ID" \
    --type String \
    --overwrite \
    --region "$AWS_REGION" \
    --no-cli-pager

aws ssm put-parameter \
    --name /aura/global/github-app-private-key \
    --value "$(cat "$PRIVATE_KEY_FILE")" \
    --type SecureString \
    --overwrite \
    --region "$AWS_REGION" \
    --no-cli-pager

log_info "Credentials stored in SSM"

# Step 2: Create Kubernetes secret for ArgoCD
log_info "Creating ArgoCD repository secret..."

PRIVATE_KEY=$(cat "$PRIVATE_KEY_FILE")

kubectl create secret generic argocd-repo-github-app -n argocd \
    --from-literal=url="$REPO_URL" \
    --from-literal=githubAppID="$APP_ID" \
    --from-literal=githubAppInstallationID="$INSTALLATION_ID" \
    --from-literal=githubAppPrivateKey="$PRIVATE_KEY" \
    --from-literal=type=git \
    --dry-run=client -o yaml | kubectl apply -f -

kubectl label secret argocd-repo-github-app -n argocd \
    argocd.argoproj.io/secret-type=repository \
    --overwrite

log_info "ArgoCD secret created"

# Step 3: Verify configuration
log_info "Waiting for ArgoCD to pick up new credentials..."
sleep 5

log_info "Checking ArgoCD application status..."
kubectl get applications -n argocd

log_info "==========================================="
log_info "Configuration Complete!"
log_info "==========================================="
log_info ""
log_info "ArgoCD should now be able to sync from the private repository."
log_info "If sync still fails, check ArgoCD logs:"
log_info "  kubectl logs -n argocd -l app.kubernetes.io/name=argocd-repo-server"
log_info ""
log_info "To manually trigger a sync:"
log_info "  kubectl -n argocd patch application aura-frontend -p '{\"operation\": {\"sync\": {}}}' --type merge"
