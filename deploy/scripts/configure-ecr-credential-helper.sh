#!/bin/bash
# configure-ecr-credential-helper.sh
# Configures Docker to use ECR credential helper, eliminating password storage warnings
#
# This script replaces the traditional 'docker login' approach:
#   aws ecr get-login-password | docker login --username AWS --password-stdin <ecr-url>
#
# Benefits:
#   - No "WARNING! Your password will be stored unencrypted" message
#   - No credentials stored in ~/.docker/config.json
#   - Automatic token refresh (no 12-hour expiration issues)
#   - AWS-recommended approach for ECR authentication
#
# Usage:
#   Called from buildspec install phase before any Docker operations
#   Environment variables required: AWS_ACCOUNT_ID, AWS_DEFAULT_REGION
#
# GovCloud Compatible: Yes - credential helper auto-detects partition

set -e

# Validate required environment variables
if [[ -z "${AWS_ACCOUNT_ID}" ]]; then
    echo "ERROR: AWS_ACCOUNT_ID environment variable is not set"
    exit 1
fi

if [[ -z "${AWS_DEFAULT_REGION}" ]]; then
    echo "ERROR: AWS_DEFAULT_REGION environment variable is not set"
    exit 1
fi

REGION="${AWS_DEFAULT_REGION}"
ACCOUNT_ID="${AWS_ACCOUNT_ID}"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "Configuring ECR credential helper..."
echo "  Region: ${REGION}"
echo "  Account: ${ACCOUNT_ID}"
echo "  Registry: ${ECR_REGISTRY}"

# Verify credential helper is available (pre-installed on CodeBuild images)
if ! command -v docker-credential-ecr-login &> /dev/null; then
    echo "ERROR: docker-credential-ecr-login not found"
    echo "This should be pre-installed on AWS CodeBuild standard images"
    exit 1
fi

# Create Docker config directory if it doesn't exist
mkdir -p ~/.docker

# Configure Docker to use ECR credential helper
# Using credHelpers (registry-specific) rather than credsStore (global) for:
#   - More explicit configuration
#   - Better multi-registry support
#   - Isolated failure handling
cat > ~/.docker/config.json << EOF
{
    "credHelpers": {
        "public.ecr.aws": "ecr-login",
        "${ECR_REGISTRY}": "ecr-login"
    }
}
EOF

echo "ECR credential helper configured successfully"
echo "Docker will now automatically authenticate with ECR without storing passwords"

# Verify configuration by checking credential helper responds
echo "Verifying credential helper..."
if docker-credential-ecr-login list &> /dev/null; then
    echo "Credential helper verification: OK"
else
    echo "WARNING: Credential helper verification returned non-zero (may be normal if no cached credentials)"
fi
