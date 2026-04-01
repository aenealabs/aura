#!/bin/bash
# =============================================================================
# Deploy Marketing Site Script
# =============================================================================
# Builds and deploys the Astro marketing site to S3/CloudFront.
#
# Usage:
#   ./deploy-marketing-site.sh dev      # Deploy to dev environment
#   ./deploy-marketing-site.sh prod     # Deploy to production
#   ./deploy-marketing-site.sh --build-only  # Build without deploying
#
# Prerequisites:
# - Node.js 18+ and npm
# - AWS CLI configured with appropriate permissions
# - Marketing site CloudFormation stack deployed
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MARKETING_DIR="$PROJECT_ROOT/marketing/site"
BUILD_DIR="$MARKETING_DIR/dist"

# Default values
ENVIRONMENT=""
BUILD_ONLY=false
SKIP_BUILD=false

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

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        dev|qa|prod)
            ENVIRONMENT="$1"
            shift
            ;;
        --build-only)
            BUILD_ONLY=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --help)
            echo "Usage: $0 [dev|qa|prod] [--build-only] [--skip-build]"
            echo ""
            echo "Options:"
            echo "  dev|qa|prod    Target environment for deployment"
            echo "  --build-only   Build site without deploying"
            echo "  --skip-build   Deploy existing build without rebuilding"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo ""
echo "========================================================"
echo "  Aenea Labs Marketing Site Deployment"
echo "========================================================"
echo ""

# Validate environment
if [ -z "$ENVIRONMENT" ] && [ "$BUILD_ONLY" = false ]; then
    log_error "Environment required. Use: $0 [dev|qa|prod]"
    exit 1
fi

# Check prerequisites
log_info "Checking prerequisites..."

if ! command -v node &> /dev/null; then
    log_error "Node.js is required but not installed"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'.' -f1 | sed 's/v//')
if [ "$NODE_VERSION" -lt 18 ]; then
    log_error "Node.js 18+ required. Found: $(node --version)"
    exit 1
fi

if [ "$BUILD_ONLY" = false ] && ! command -v aws &> /dev/null; then
    log_error "AWS CLI is required for deployment"
    exit 1
fi

log_success "Prerequisites check passed"

# Install dependencies if needed
cd "$MARKETING_DIR"

if [ ! -d "node_modules" ]; then
    log_info "Installing dependencies..."
    npm install
    log_success "Dependencies installed"
fi

# Build the site
if [ "$SKIP_BUILD" = false ]; then
    log_info "Building marketing site..."

    # Set environment-specific variables
    if [ "$ENVIRONMENT" = "prod" ]; then
        export PUBLIC_APP_URL="https://app.aenealabs.com"
        export PUBLIC_DOCS_URL="https://docs.aenealabs.com"
        export PUBLIC_API_URL="https://api.aenealabs.com"
    else
        export PUBLIC_APP_URL="https://app-${ENVIRONMENT}.aenealabs.com"
        export PUBLIC_DOCS_URL="https://docs-${ENVIRONMENT}.aenealabs.com"
        export PUBLIC_API_URL="https://api-${ENVIRONMENT}.aenealabs.com"
    fi

    # Run build
    npm run build

    if [ ! -d "$BUILD_DIR" ]; then
        log_error "Build failed - dist directory not created"
        exit 1
    fi

    FILE_COUNT=$(find "$BUILD_DIR" -type f | wc -l | tr -d ' ')
    log_success "Build complete: $FILE_COUNT files generated"
else
    if [ ! -d "$BUILD_DIR" ]; then
        log_error "No existing build found. Run without --skip-build first"
        exit 1
    fi
    log_info "Using existing build"
fi

# Stop here if build-only
if [ "$BUILD_ONLY" = true ]; then
    echo ""
    log_success "Build complete. Output: $BUILD_DIR"
    exit 0
fi

# Get bucket name from CloudFormation
log_info "Looking up S3 bucket for $ENVIRONMENT..."

BUCKET_NAME=$(aws cloudformation list-exports \
    --query "Exports[?Name=='aura-marketing-bucket-${ENVIRONMENT}'].Value" \
    --output text 2>/dev/null)

if [ -z "$BUCKET_NAME" ] || [ "$BUCKET_NAME" = "None" ]; then
    # Try default naming convention
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    BUCKET_NAME="aura-marketing-${ACCOUNT_ID}-${ENVIRONMENT}"
    log_warn "Using default bucket name: $BUCKET_NAME"
fi

# Verify bucket exists
if ! aws s3 ls "s3://${BUCKET_NAME}" &> /dev/null; then
    log_error "Bucket does not exist: $BUCKET_NAME"
    log_info "Deploy the marketing-site.yaml CloudFormation stack first"
    exit 1
fi

log_success "Found bucket: $BUCKET_NAME"

# Deploy to S3
log_info "Deploying to S3..."

# Sync static assets with long cache
aws s3 sync "$BUILD_DIR" "s3://${BUCKET_NAME}/" \
    --delete \
    --cache-control "public, max-age=31536000, immutable" \
    --exclude "*.html" \
    --exclude "*.json" \
    --exclude "*.xml"

# Sync HTML files with shorter cache
aws s3 sync "$BUILD_DIR" "s3://${BUCKET_NAME}/" \
    --exclude "*" \
    --include "*.html" \
    --cache-control "public, max-age=0, must-revalidate"

# Sync other dynamic files
aws s3 sync "$BUILD_DIR" "s3://${BUCKET_NAME}/" \
    --exclude "*" \
    --include "*.json" \
    --include "*.xml" \
    --cache-control "public, max-age=3600"

log_success "Files uploaded to S3"

# Invalidate CloudFront cache
log_info "Invalidating CloudFront cache..."

CF_DIST_ID=$(aws cloudformation list-exports \
    --query "Exports[?Name=='aura-marketing-cf-id-${ENVIRONMENT}'].Value" \
    --output text 2>/dev/null)

if [ -n "$CF_DIST_ID" ] && [ "$CF_DIST_ID" != "None" ]; then
    INVALIDATION_ID=$(aws cloudfront create-invalidation \
        --distribution-id "$CF_DIST_ID" \
        --paths "/*" \
        --query 'Invalidation.Id' \
        --output text)

    log_success "CloudFront invalidation created: $INVALIDATION_ID"

    # Wait for invalidation to complete (optional)
    log_info "Waiting for invalidation to complete..."
    aws cloudfront wait invalidation-completed \
        --distribution-id "$CF_DIST_ID" \
        --id "$INVALIDATION_ID" 2>/dev/null || true

    log_success "CloudFront cache invalidated"
else
    log_warn "CloudFront distribution not found. Skipping invalidation."
fi

# Get site URL
SITE_URL=$(aws cloudformation list-exports \
    --query "Exports[?Name=='aura-marketing-url-${ENVIRONMENT}'].Value" \
    --output text 2>/dev/null)

if [ -z "$SITE_URL" ] || [ "$SITE_URL" = "None" ]; then
    CF_DOMAIN=$(aws cloudformation list-exports \
        --query "Exports[?Name=='aura-marketing-cf-domain-${ENVIRONMENT}'].Value" \
        --output text 2>/dev/null)
    SITE_URL="https://${CF_DOMAIN}"
fi

echo ""
echo "========================================================"
echo "  Deployment Complete!"
echo "========================================================"
echo ""
echo "  Environment: $ENVIRONMENT"
echo "  S3 Bucket:   $BUCKET_NAME"
echo "  Site URL:    $SITE_URL"
echo ""

# Health check
log_info "Performing health check..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SITE_URL" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    log_success "Site is healthy (HTTP $HTTP_CODE)"
else
    log_warn "Site returned HTTP $HTTP_CODE (may take a few minutes to propagate)"
fi

echo ""
