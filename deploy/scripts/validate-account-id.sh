#!/bin/bash
# Project Aura - Account ID Validation
# Validates that the current AWS account matches the expected environment.
#
# The expected account comes from, in order:
#   1. SSM /<project>/<env>/account-id in the account being deployed (set once
#      per account during setup; keeps real account IDs out of the repository)
#   2. deploy/config/account-mapping.env (<ENV>_ACCOUNT_ID)
# The documentation placeholders 123456789012 and 234567890123 count as unset.

set -e

ENVIRONMENT="${1:-}"
AWS_ACCOUNT_ID="${2:-}"
PROJECT_NAME="${PROJECT_NAME:-aura}"

if [ -z "$ENVIRONMENT" ] || [ -z "$AWS_ACCOUNT_ID" ]; then
  echo "Usage: $0 <environment> <aws_account_id>"
  exit 1
fi

PLACEHOLDER_ACCOUNT_IDS="123456789012 234567890123"

is_placeholder() {
  local id="$1"
  for p in $PLACEHOLDER_ACCOUNT_IDS; do
    [ "$id" = "$p" ] && return 0
  done
  return 1
}

PARAM_NAME="/${PROJECT_NAME}/${ENVIRONMENT}/account-id"
EXPECTED_ACCOUNT_ID=$(aws ssm get-parameter --name "$PARAM_NAME" \
  --query Parameter.Value --output text 2>/dev/null || echo "")
SOURCE="SSM ${PARAM_NAME}"

if [ -z "$EXPECTED_ACCOUNT_ID" ] || [ "$EXPECTED_ACCOUNT_ID" = "None" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  CONFIG_FILE="${SCRIPT_DIR}/../config/account-mapping.env"
  if [ -f "$CONFIG_FILE" ]; then
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
    ENV_UPPER=$(echo "${ENVIRONMENT}" | tr '[:lower:]' '[:upper:]')
    EXPECTED_VAR="${ENV_UPPER}_ACCOUNT_ID"
    EXPECTED_ACCOUNT_ID=$(eval echo \$${EXPECTED_VAR})
    SOURCE="${CONFIG_FILE} (${EXPECTED_VAR})"
  fi
fi

if [ -z "${EXPECTED_ACCOUNT_ID}" ] || is_placeholder "${EXPECTED_ACCOUNT_ID}"; then
  echo "ERROR: No account ID configured for environment ${ENVIRONMENT}"
  echo "  Set it once in the target account:"
  echo "    aws ssm put-parameter --name ${PARAM_NAME} --value <account-id> --type String"
  exit 1
fi

if [ "${AWS_ACCOUNT_ID}" != "${EXPECTED_ACCOUNT_ID}" ] && [ "${EXPECTED_ACCOUNT_ID}" != "PENDING" ]; then
  echo "ERROR: Account ID mismatch!"
  echo "  Running in account: ${AWS_ACCOUNT_ID}"
  echo "  Expected for ${ENVIRONMENT} (from ${SOURCE}): ${EXPECTED_ACCOUNT_ID}"
  exit 1
fi

echo "Account ID validation passed for ${ENVIRONMENT} environment (source: ${SOURCE})"
