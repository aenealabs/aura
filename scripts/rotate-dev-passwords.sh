#!/bin/bash
#
# Rotate Cognito dev user passwords and store in SSM Parameter Store
#
# Usage:
#   ./scripts/rotate-dev-passwords.sh
#
# Prerequisites:
#   - AWS CLI configured with appropriate permissions
#   - cognito-idp:AdminSetUserPassword permission
#   - ssm:PutParameter permission
#
# This script will:
#   1. Generate new secure passwords for each dev user
#   2. Update the passwords in Cognito
#   3. Store the new passwords in SSM Parameter Store as SecureStrings
#

set -e

REGION="${AWS_REGION:-us-east-1}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "  Cognito Dev Password Rotation Script"
echo "========================================"
echo ""

# Get Cognito User Pool ID from SSM or environment
if [ -z "$COGNITO_USER_POOL_ID" ]; then
  echo "Fetching Cognito User Pool ID from SSM..."
  COGNITO_USER_POOL_ID=$(aws ssm get-parameter \
    --name /aura/dev/cognito/user-pool-id \
    --query Parameter.Value \
    --output text \
    --region "$REGION" 2>/dev/null || echo "")
fi

if [ -z "$COGNITO_USER_POOL_ID" ]; then
  echo -e "${RED}Error: Could not get Cognito User Pool ID${NC}" >&2
  echo "Set COGNITO_USER_POOL_ID environment variable or ensure SSM parameter exists" >&2
  exit 1
fi

echo -e "${GREEN}Using User Pool ID: $COGNITO_USER_POOL_ID${NC}"
echo ""

# Function to generate a secure password
# Requirements: 12+ chars, uppercase, lowercase, number, special char
generate_password() {
  # Generate 16 char password with mixed characters
  # Using /dev/urandom for cryptographic randomness
  # macOS compatible (no shuf dependency)

  # Ensure we have required character types
  # Note: hyphen must be last in tr character class on macOS
  local upper=$(LC_ALL=C tr -dc 'A-Z' < /dev/urandom | head -c 4)
  local lower=$(LC_ALL=C tr -dc 'a-z' < /dev/urandom | head -c 6)
  local digits=$(LC_ALL=C tr -dc '0-9' < /dev/urandom | head -c 4)
  local special=$(LC_ALL=C tr -dc '_#' < /dev/urandom | head -c 2)

  # Combine parts (shuffle using awk for macOS compatibility)
  local combined="${upper}${lower}${digits}${special}"
  local password=$(echo "$combined" | fold -w1 | awk 'BEGIN{srand()}{print rand()"\t"$0}' | sort -n | cut -f2 | tr -d '\n')

  echo "$password"
}

# Function to get Cognito username (UUID) from email
get_cognito_username() {
  local email=$1
  aws cognito-idp list-users \
    --user-pool-id "$COGNITO_USER_POOL_ID" \
    --filter "email = \"$email\"" \
    --region "$REGION" \
    --output json 2>/dev/null | jq -r '.Users[0].Username // empty'
}

# Function to rotate password for a single user
rotate_user_password() {
  local role=$1
  local email=$2
  local ssm_param=$3

  echo "----------------------------------------"
  echo -e "Rotating password for: ${YELLOW}$role${NC} ($email)"

  # Look up the Cognito username (UUID) from email
  echo "  Looking up user..."
  local cognito_username=$(get_cognito_username "$email")

  if [ -z "$cognito_username" ]; then
    echo -e "  ${RED}✗ User not found with email: $email${NC}" >&2
    echo "  Creating new user..." >&2

    # Generate new password
    local new_password=$(generate_password)

    # Create the user with email
    if aws cognito-idp admin-create-user \
      --user-pool-id "$COGNITO_USER_POOL_ID" \
      --username "$email" \
      --user-attributes Name=email,Value="$email" Name=email_verified,Value=true \
      --temporary-password "$new_password" \
      --message-action SUPPRESS \
      --region "$REGION" 2>/dev/null; then

      # Set permanent password
      aws cognito-idp admin-set-user-password \
        --user-pool-id "$COGNITO_USER_POOL_ID" \
        --username "$email" \
        --password "$new_password" \
        --permanent \
        --region "$REGION"
      echo -e "  ${GREEN}✓ User created and password set${NC}"

      # Store password in SSM
      echo "  Storing password in SSM..."
      aws ssm put-parameter \
        --name "$ssm_param" \
        --value "$new_password" \
        --type SecureString \
        --overwrite \
        --region "$REGION" >/dev/null
      echo -e "  ${GREEN}✓ Password stored in SSM: $ssm_param${NC}"
      echo ""
      return 0
    else
      echo -e "  ${RED}✗ Failed to create user${NC}" >&2
      return 1
    fi
  fi

  echo -e "  Found user: $cognito_username"

  # Generate new password
  local new_password=$(generate_password)

  # Update password in Cognito
  echo "  Updating Cognito password..."
  if aws cognito-idp admin-set-user-password \
    --user-pool-id "$COGNITO_USER_POOL_ID" \
    --username "$cognito_username" \
    --password "$new_password" \
    --permanent \
    --region "$REGION" 2>/dev/null; then
    echo -e "  ${GREEN}✓ Cognito password updated${NC}"
  else
    echo -e "  ${RED}✗ Failed to update Cognito password${NC}" >&2
    return 1
  fi

  # Store password in SSM Parameter Store
  echo "  Storing password in SSM..."
  if aws ssm put-parameter \
    --name "$ssm_param" \
    --value "$new_password" \
    --type SecureString \
    --overwrite \
    --region "$REGION" 2>/dev/null; then
    echo -e "  ${GREEN}✓ Password stored in SSM: $ssm_param${NC}"
  else
    echo -e "  ${RED}✗ Failed to store password in SSM${NC}" >&2
    return 1
  fi

  echo ""
  return 0
}

# Track success/failure
SUCCESS_COUNT=0
FAIL_COUNT=0

# Rotate passwords for all users (portable approach without associative arrays)
rotate_user_password "admin" "dev-admin@aenealabs.com" "/aura/dev/cognito/dev-admin-password" && SUCCESS_COUNT=$((SUCCESS_COUNT + 1)) || FAIL_COUNT=$((FAIL_COUNT + 1))
rotate_user_password "engineer" "dev-engineer@aenealabs.com" "/aura/dev/cognito/dev-engineer-password" && SUCCESS_COUNT=$((SUCCESS_COUNT + 1)) || FAIL_COUNT=$((FAIL_COUNT + 1))
rotate_user_password "developer" "dev-developer@aenealabs.com" "/aura/dev/cognito/dev-developer-password" && SUCCESS_COUNT=$((SUCCESS_COUNT + 1)) || FAIL_COUNT=$((FAIL_COUNT + 1))
rotate_user_password "viewer" "dev-viewer@aenealabs.com" "/aura/dev/cognito/dev-viewer-password" && SUCCESS_COUNT=$((SUCCESS_COUNT + 1)) || FAIL_COUNT=$((FAIL_COUNT + 1))

# Summary
echo "========================================"
echo "  Rotation Complete"
echo "========================================"
echo -e "  ${GREEN}Successful: $SUCCESS_COUNT${NC}"
if [ $FAIL_COUNT -gt 0 ]; then
  echo -e "  ${RED}Failed: $FAIL_COUNT${NC}"
fi
echo ""

if [ $FAIL_COUNT -gt 0 ]; then
  echo -e "${YELLOW}Warning: Some rotations failed. Check errors above.${NC}"
  exit 1
fi

echo -e "${GREEN}All passwords rotated successfully!${NC}"
echo ""
echo "You can now use the get-dev-token.sh script to authenticate:"
echo "  export TOKEN=\$(./scripts/get-dev-token.sh admin)"
echo ""
