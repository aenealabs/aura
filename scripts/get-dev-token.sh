#!/bin/bash
#
# Get a Cognito JWT token for local development
#
# Usage:
#   ./scripts/get-dev-token.sh [admin|engineer|developer|viewer]
#
# Example:
#   export TOKEN=$(./scripts/get-dev-token.sh admin)
#   curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/health
#
# Prerequisites:
#   - AWS CLI configured with appropriate permissions
#   - SSM parameters set up (see docs/deployment/COGNITO_SETUP.md)
#

set -e

# Default to admin if no role specified
ROLE="${1:-admin}"

# Validate role and set username
case $ROLE in
  admin)
    USERNAME="dev-admin@aenealabs.com"
    SSM_PASSWORD_PARAM="/aura/dev/cognito/dev-admin-password"
    ;;
  engineer)
    USERNAME="dev-engineer@aenealabs.com"
    SSM_PASSWORD_PARAM="/aura/dev/cognito/dev-engineer-password"
    ;;
  developer)
    USERNAME="dev-developer@aenealabs.com"
    SSM_PASSWORD_PARAM="/aura/dev/cognito/dev-developer-password"
    ;;
  viewer)
    USERNAME="dev-viewer@aenealabs.com"
    SSM_PASSWORD_PARAM="/aura/dev/cognito/dev-viewer-password"
    ;;
  *)
    echo "Unknown role: $ROLE" >&2
    echo "Usage: $0 [admin|engineer|developer|viewer]" >&2
    exit 1
    ;;
esac

# Get configuration from SSM or environment
if [ -z "$COGNITO_USER_POOL_ID" ]; then
  COGNITO_USER_POOL_ID=$(aws ssm get-parameter --name /aura/dev/cognito/user-pool-id --query Parameter.Value --output text --region us-east-1 2>/dev/null || echo "")
fi

if [ -z "$COGNITO_CLIENT_ID" ]; then
  COGNITO_CLIENT_ID=$(aws ssm get-parameter --name /aura/dev/cognito/client-id --query Parameter.Value --output text --region us-east-1 2>/dev/null || echo "")
fi

if [ -z "$COGNITO_USER_POOL_ID" ] || [ -z "$COGNITO_CLIENT_ID" ]; then
  echo "Error: Could not get Cognito configuration from SSM" >&2
  echo "Set COGNITO_USER_POOL_ID and COGNITO_CLIENT_ID environment variables" >&2
  exit 1
fi

# Get password from SSM SecureString (never hardcode passwords)
PASSWORD=$(aws ssm get-parameter \
  --name "$SSM_PASSWORD_PARAM" \
  --with-decryption \
  --query Parameter.Value \
  --output text \
  --region us-east-1 2>/dev/null || echo "")

if [ -z "$PASSWORD" ]; then
  echo "Error: Could not get password from SSM parameter: $SSM_PASSWORD_PARAM" >&2
  echo "Ensure the SSM parameter exists and you have ssm:GetParameter permission" >&2
  exit 1
fi

# Authenticate and get token
RESULT=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id "$COGNITO_CLIENT_ID" \
  --auth-parameters USERNAME="$USERNAME",PASSWORD="$PASSWORD" \
  --region us-east-1 \
  --output json 2>&1)

if echo "$RESULT" | grep -q "IdToken"; then
  # Extract access token (or id token for testing)
  ACCESS_TOKEN=$(echo "$RESULT" | jq -r '.AuthenticationResult.AccessToken')
  echo "$ACCESS_TOKEN"
else
  echo "Authentication failed:" >&2
  echo "$RESULT" >&2
  exit 1
fi
