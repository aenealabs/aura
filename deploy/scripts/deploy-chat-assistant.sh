#!/bin/bash
#
# Deploy Chat Assistant Infrastructure
# Deploys CloudFormation stack, Lambda code, and outputs API URLs
#
# =============================================================================
# IMPORTANT: CI/CD vs Manual Deployment
# =============================================================================
# This script is for LOCAL DEVELOPMENT convenience only.
# For CI/CD deployments, use CodeBuild:
#   aws codebuild start-build --project-name aura-serverless-deploy-${ENVIRONMENT}
#
# Per CLAUDE.md guidelines:
# - CodeBuild is the ONLY authoritative deployment method for production
# - Manual deploys break audit trail and IAM consistency
# =============================================================================
#
# Usage:
#   ./deploy/scripts/deploy-chat-assistant.sh [environment]
#
# Examples:
#   ./deploy/scripts/deploy-chat-assistant.sh dev
#   ./deploy/scripts/deploy-chat-assistant.sh qa
#

set -e

# Check if running in CI/CD context - if so, recommend CodeBuild
if [ -n "$CODEBUILD_BUILD_ID" ] || [ -n "$CI" ] || [ -n "$GITHUB_ACTIONS" ]; then
    echo "============================================"
    echo "WARNING: Running in CI/CD context"
    echo "============================================"
    echo "This script should NOT be used in CI/CD pipelines."
    echo "Use CodeBuild instead:"
    echo "  aws codebuild start-build --project-name aura-serverless-deploy-\${ENVIRONMENT}"
    echo ""
    echo "Continuing anyway... (override with USE_MANUAL_DEPLOY=true)"
    if [ "$USE_MANUAL_DEPLOY" != "true" ]; then
        exit 1
    fi
fi

# Configuration
ENVIRONMENT="${1:-dev}"
PROJECT_NAME="${PROJECT_NAME:-aura}"
STACK_NAME="${PROJECT_NAME}-chat-assistant-${ENVIRONMENT}"
AWS_REGION="${AWS_REGION:-us-east-1}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "============================================"
echo "Deploying Chat Assistant Infrastructure"
echo "============================================"
echo "Environment: ${ENVIRONMENT}"
echo "Stack Name:  ${STACK_NAME}"
echo "Region:      ${AWS_REGION}"
echo "Project Root: ${PROJECT_ROOT}"
echo "============================================"

cd "${PROJECT_ROOT}"

# Step 1: Validate CloudFormation template
echo ""
echo -e "${YELLOW}Step 1: Validating CloudFormation template...${NC}"
if command -v cfn-lint &> /dev/null; then
    cfn-lint deploy/cloudformation/chat-assistant.yaml
    echo -e "${GREEN}Template validation passed${NC}"
else
    echo -e "${YELLOW}cfn-lint not installed, skipping validation${NC}"
fi

# Step 2: Deploy CloudFormation stack
echo ""
echo -e "${YELLOW}Step 2: Deploying CloudFormation stack...${NC}"
aws cloudformation deploy \
    --stack-name "${STACK_NAME}" \
    --template-file deploy/cloudformation/chat-assistant.yaml \
    --parameter-overrides \
        ProjectName="${PROJECT_NAME}" \
        Environment="${ENVIRONMENT}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset \
    --region "${AWS_REGION}"

echo -e "${GREEN}CloudFormation stack deployed${NC}"

# Step 3: Package Lambda code
echo ""
echo -e "${YELLOW}Step 3: Packaging Lambda code...${NC}"
PACKAGE_DIR=$(mktemp -d)
cp src/lambda/chat/*.py "${PACKAGE_DIR}/"
cd "${PACKAGE_DIR}"
zip -q -r chat-lambda.zip .
echo -e "${GREEN}Lambda package created: ${PACKAGE_DIR}/chat-lambda.zip${NC}"

# Step 4: Deploy Lambda functions
echo ""
echo -e "${YELLOW}Step 4: Updating Lambda functions...${NC}"

LAMBDA_FUNCTIONS=(
    "${PROJECT_NAME}-chat-handler-${ENVIRONMENT}"
    "${PROJECT_NAME}-chat-ws-connect-${ENVIRONMENT}"
    "${PROJECT_NAME}-chat-ws-disconnect-${ENVIRONMENT}"
    "${PROJECT_NAME}-chat-ws-message-${ENVIRONMENT}"
)

for FUNC in "${LAMBDA_FUNCTIONS[@]}"; do
    echo "  Updating ${FUNC}..."
    aws lambda update-function-code \
        --function-name "${FUNC}" \
        --zip-file "fileb://${PACKAGE_DIR}/chat-lambda.zip" \
        --region "${AWS_REGION}" \
        --output text \
        --query 'LastModified' > /dev/null
done

echo -e "${GREEN}All Lambda functions updated${NC}"

# Cleanup
rm -rf "${PACKAGE_DIR}"
cd "${PROJECT_ROOT}"

# Step 5: Get stack outputs
echo ""
echo -e "${YELLOW}Step 5: Retrieving API endpoints...${NC}"
echo "============================================"

REST_API_URL=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='RestApiUrl'].OutputValue" \
    --output text \
    --region "${AWS_REGION}")

WS_URL=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='WebSocketUrl'].OutputValue" \
    --output text \
    --region "${AWS_REGION}")

echo ""
echo "REST API URL: ${REST_API_URL}"
echo "WebSocket URL: ${WS_URL}"

# Step 6: Generate .env configuration (do not commit!)
echo ""
echo "============================================"
echo -e "${GREEN}Deployment complete!${NC}"
echo "============================================"
echo ""
echo "Add these to your frontend/.env.local (already gitignored):"
echo ""
echo "  VITE_CHAT_API_URL=${REST_API_URL}"
echo "  VITE_CHAT_WS_URL=${WS_URL}"
echo "  VITE_MOCK_CHAT=false"
echo ""
echo -e "${YELLOW}Security Note:${NC}"
echo "  - .env.local is gitignored and will NOT be committed"
echo "  - API Gateway uses Cognito authentication"
echo "  - WebSocket connections require valid user context"
echo ""
echo "Test the API:"
echo "  curl -X POST ${REST_API_URL}/chat/message \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -H 'X-Dev-User-Id: dev-user-123' \\"
echo "    -d '{\"message\": \"hello\"}'"
echo ""
