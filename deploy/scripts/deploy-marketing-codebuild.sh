#!/bin/bash
# =============================================================================
# Deploy Marketing CodeBuild Script
# =============================================================================
# Deploys the CodeBuild project for marketing site and docs portal builds.
#
# Usage:
#   ./deploy-marketing-codebuild.sh dev      # Deploy to dev environment
#   ./deploy-marketing-codebuild.sh prod     # Deploy to production
#
# Prerequisites:
# - AWS CLI configured with appropriate permissions
# - CodeConnections ARN stored in SSM at /aura/global/codeconnections-arn
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default values
ENVIRONMENT="${1:-dev}"
PROJECT_NAME="aura"
GITHUB_BRANCH="main"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|qa|prod)$ ]]; then
    log_error "Invalid environment: $ENVIRONMENT"
    echo "Usage: $0 [dev|qa|prod]"
    exit 1
fi

echo ""
echo "========================================================"
echo "  Aenea Labs Marketing CodeBuild Deployment"
echo "========================================================"
echo ""
echo "  Environment: $ENVIRONMENT"
echo "  Branch: $GITHUB_BRANCH"
echo ""

# Check prerequisites
log_info "Checking prerequisites..."

if ! command -v aws &> /dev/null; then
    log_error "AWS CLI is required"
    exit 1
fi

# Check CodeConnections ARN exists
if ! aws ssm get-parameter --name "/aura/global/codeconnections-arn" &> /dev/null; then
    log_error "CodeConnections ARN not found in SSM"
    log_info "Store it with: aws ssm put-parameter --name /aura/global/codeconnections-arn --value <arn> --type String"
    exit 1
fi

log_success "Prerequisites check passed"

# Validate template
log_info "Validating CloudFormation template..."
if command -v cfn-lint &> /dev/null; then
    cfn-lint "$PROJECT_ROOT/deploy/cloudformation/codebuild-marketing.yaml" --ignore-checks W3002 || echo "cfn-lint found warnings (non-blocking)"
fi

# Deploy stack
log_info "Deploying CodeBuild project..."

STACK_NAME="${PROJECT_NAME}-codebuild-marketing-${ENVIRONMENT}"
DEPLOY_TIMESTAMP=$(date +%Y%m%d-%H%M%S)

aws cloudformation deploy \
    --stack-name "$STACK_NAME" \
    --template-file "$PROJECT_ROOT/deploy/cloudformation/codebuild-marketing.yaml" \
    --parameter-overrides \
        Environment="$ENVIRONMENT" \
        ProjectName="$PROJECT_NAME" \
        GitHubBranch="$GITHUB_BRANCH" \
    --tags \
        Project="$PROJECT_NAME" \
        Environment="$ENVIRONMENT" \
        Layer=marketing \
        DeployTimestamp="$DEPLOY_TIMESTAMP" \
    --capabilities CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset

log_success "CodeBuild project deployed"

# Get outputs
CODEBUILD_PROJECT=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`MarketingCodeBuildProjectName`].OutputValue' \
    --output text)

echo ""
echo "========================================================"
echo "  Deployment Complete!"
echo "========================================================"
echo ""
echo "  CodeBuild Project: $CODEBUILD_PROJECT"
echo ""
echo "  To trigger a build:"
echo "    aws codebuild start-build --project-name $CODEBUILD_PROJECT"
echo ""
echo "  To view builds:"
echo "    aws codebuild list-builds-for-project --project-name $CODEBUILD_PROJECT"
echo ""
