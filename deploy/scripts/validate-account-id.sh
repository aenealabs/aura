#!/bin/bash
# Project Aura - Account ID Validation
# Validates that the current AWS account matches the expected environment

set -e

ENVIRONMENT="${1:-}"
AWS_ACCOUNT_ID="${2:-}"

if [ -z "$ENVIRONMENT" ] || [ -z "$AWS_ACCOUNT_ID" ]; then
  echo "Usage: $0 <environment> <aws_account_id>"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/account-mapping.env"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "ERROR: Account mapping config not found at $CONFIG_FILE"
  exit 1
fi

source "$CONFIG_FILE"

ENV_UPPER=$(echo "${ENVIRONMENT}" | tr '[:lower:]' '[:upper:]')
EXPECTED_VAR="${ENV_UPPER}_ACCOUNT_ID"
EXPECTED_ACCOUNT_ID=$(eval echo \$${EXPECTED_VAR})

if [ -z "${EXPECTED_ACCOUNT_ID}" ]; then
  echo "ERROR: No account ID configured for environment ${ENVIRONMENT}"
  echo "  Update deploy/config/account-mapping.env with ${EXPECTED_VAR}=<account-id>"
  exit 1
fi

if [ "${AWS_ACCOUNT_ID}" != "${EXPECTED_ACCOUNT_ID}" ] && [ "${EXPECTED_ACCOUNT_ID}" != "PENDING" ]; then
  echo "ERROR: Account ID mismatch!"
  echo "  Running in account: ${AWS_ACCOUNT_ID}"
  echo "  Expected for ${ENVIRONMENT}: ${EXPECTED_ACCOUNT_ID}"
  echo "  Update deploy/config/account-mapping.env if account has changed."
  exit 1
fi

echo "Account ID validation passed for ${ENVIRONMENT} environment"
