#!/bin/bash
# =============================================================================
# Cross-Account ACM Certificate Deployment
# =============================================================================
# Handles ACM certificate deployment when the Route 53 hosted zone is in a
# different AWS account than where the certificate is being created.
#
# This script:
# 1. Requests an ACM certificate (pending validation)
# 2. Gets the DNS validation CNAME records
# 3. Assumes cross-account role in the account with Route 53 hosted zone
# 4. Creates DNS validation records
# 5. Waits for certificate to be issued
#
# Usage: ./deploy-acm-cross-account.sh
#
# Required environment variables:
#   ENVIRONMENT          - Environment name (dev, qa, prod)
#   PROJECT_NAME         - Project name (aura)
#   AWS_ACCOUNT_ID       - Current AWS account ID
#   AWS_DEFAULT_REGION   - AWS region
#   DEV_ACCOUNT_ID       - Account ID where Route 53 hosted zone exists
#   HOSTED_ZONE_ID       - Route 53 hosted zone ID
#   ROUTE53_CROSS_ACCOUNT_ROLE - ARN of cross-account role to assume
# =============================================================================

set -euo pipefail

DOMAIN_NAME="${DOMAIN_NAME:-aenealabs.com}"
EXTERNAL_ID="${PROJECT_NAME}-route53-validation"

echo "=========================================="
echo "Cross-Account ACM Certificate Deployment"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "Domain: $DOMAIN_NAME"
echo "Current Account: $AWS_ACCOUNT_ID"
echo "Route 53 Account: $DEV_ACCOUNT_ID"
echo "Hosted Zone: $HOSTED_ZONE_ID"

# Check if we're in the same account as Route 53
if [ "$AWS_ACCOUNT_ID" = "$DEV_ACCOUNT_ID" ]; then
    echo "Same account deployment - using standard CloudFormation flow"
    exit 0  # Let the normal buildspec handle it
fi

echo "Cross-account deployment detected"

# Check if a valid certificate already exists
EXISTING_CERT=$(aws acm list-certificates --region "$AWS_DEFAULT_REGION" \
    --query "CertificateSummaryList[?DomainName=='$DOMAIN_NAME' && Status=='ISSUED'].CertificateArn" \
    --output text 2>/dev/null || echo "")

if [ -n "$EXISTING_CERT" ] && [ "$EXISTING_CERT" != "None" ]; then
    echo "Valid ACM certificate already exists: $EXISTING_CERT"
    echo "CERTIFICATE_ARN=$EXISTING_CERT" > /tmp/acm-output.env
    exit 0
fi

# Check if certificate is pending validation
PENDING_CERT=$(aws acm list-certificates --region "$AWS_DEFAULT_REGION" \
    --query "CertificateSummaryList[?DomainName=='$DOMAIN_NAME' && Status=='PENDING_VALIDATION'].CertificateArn" \
    --output text 2>/dev/null || echo "")

if [ -n "$PENDING_CERT" ] && [ "$PENDING_CERT" != "None" ]; then
    echo "Found pending certificate: $PENDING_CERT"
    CERT_ARN="$PENDING_CERT"
else
    echo "Requesting new ACM certificate..."
    CERT_ARN=$(aws acm request-certificate \
        --domain-name "$DOMAIN_NAME" \
        --subject-alternative-names "*.$DOMAIN_NAME" \
        --validation-method DNS \
        --tags Key=Name,Value="${PROJECT_NAME}-certificate-${ENVIRONMENT}" \
               Key=Project,Value="$PROJECT_NAME" \
               Key=Environment,Value="$ENVIRONMENT" \
        --region "$AWS_DEFAULT_REGION" \
        --query 'CertificateArn' \
        --output text)
    echo "Certificate requested: $CERT_ARN"

    # Wait for certificate details to be available
    echo "Waiting for certificate details..."
    sleep 10
fi

# Get DNS validation records
echo "Getting DNS validation records..."
MAX_RETRIES=12
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    VALIDATION_RECORDS=$(aws acm describe-certificate \
        --certificate-arn "$CERT_ARN" \
        --region "$AWS_DEFAULT_REGION" \
        --query 'Certificate.DomainValidationOptions[*].ResourceRecord' \
        --output json 2>/dev/null || echo "[]")

    # Check if we have validation records
    RECORD_COUNT=$(echo "$VALIDATION_RECORDS" | jq 'length')
    if [ "$RECORD_COUNT" -gt 0 ] && [ "$(echo "$VALIDATION_RECORDS" | jq '.[0]')" != "null" ]; then
        echo "Found $RECORD_COUNT validation record(s)"
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for validation records... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 5
done

if [ "$RECORD_COUNT" -eq 0 ] || [ "$(echo "$VALIDATION_RECORDS" | jq '.[0]')" = "null" ]; then
    echo "ERROR: Could not get DNS validation records after $MAX_RETRIES attempts"
    exit 1
fi

# Assume cross-account role
echo "Assuming cross-account role for Route 53 access..."
ASSUME_ROLE_OUTPUT=$(aws sts assume-role \
    --role-arn "$ROUTE53_CROSS_ACCOUNT_ROLE" \
    --role-session-name "ACMValidation-${ENVIRONMENT}" \
    --external-id "$EXTERNAL_ID" \
    --duration-seconds 900 \
    --output json)

# Extract credentials
CROSS_ACCOUNT_ACCESS_KEY=$(echo "$ASSUME_ROLE_OUTPUT" | jq -r '.Credentials.AccessKeyId')
CROSS_ACCOUNT_SECRET_KEY=$(echo "$ASSUME_ROLE_OUTPUT" | jq -r '.Credentials.SecretAccessKey')
CROSS_ACCOUNT_SESSION_TOKEN=$(echo "$ASSUME_ROLE_OUTPUT" | jq -r '.Credentials.SessionToken')

if [ -z "$CROSS_ACCOUNT_ACCESS_KEY" ] || [ "$CROSS_ACCOUNT_ACCESS_KEY" = "null" ]; then
    echo "ERROR: Failed to assume cross-account role"
    exit 1
fi

echo "Successfully assumed cross-account role"

# Create DNS validation records
echo "Creating DNS validation records in Route 53..."

# Parse validation records and create Route 53 changes
CHANGES="["
FIRST=true

echo "$VALIDATION_RECORDS" | jq -c '.[]' | while read -r record; do
    RECORD_NAME=$(echo "$record" | jq -r '.Name')
    RECORD_VALUE=$(echo "$record" | jq -r '.Value')
    RECORD_TYPE=$(echo "$record" | jq -r '.Type')

    if [ -z "$RECORD_NAME" ] || [ "$RECORD_NAME" = "null" ]; then
        continue
    fi

    echo "Creating record: $RECORD_NAME -> $RECORD_VALUE"

    # Create Route 53 change batch for this record
    CHANGE_BATCH=$(cat <<EOF
{
    "Comment": "ACM DNS validation for ${PROJECT_NAME}-${ENVIRONMENT}",
    "Changes": [
        {
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": "$RECORD_NAME",
                "Type": "$RECORD_TYPE",
                "TTL": 300,
                "ResourceRecords": [
                    {
                        "Value": "$RECORD_VALUE"
                    }
                ]
            }
        }
    ]
}
EOF
)

    # Use assumed role credentials
    AWS_ACCESS_KEY_ID="$CROSS_ACCOUNT_ACCESS_KEY" \
    AWS_SECRET_ACCESS_KEY="$CROSS_ACCOUNT_SECRET_KEY" \
    AWS_SESSION_TOKEN="$CROSS_ACCOUNT_SESSION_TOKEN" \
    aws route53 change-resource-record-sets \
        --hosted-zone-id "$HOSTED_ZONE_ID" \
        --change-batch "$CHANGE_BATCH" \
        --output text || {
            echo "Warning: Failed to create/update DNS record $RECORD_NAME"
        }
done

echo "DNS validation records created"

# Wait for certificate to be issued
echo "Waiting for certificate validation (this may take 5-30 minutes)..."
MAX_WAIT_MINUTES=30
WAIT_INTERVAL=30
ELAPSED=0

while [ $ELAPSED -lt $((MAX_WAIT_MINUTES * 60)) ]; do
    STATUS=$(aws acm describe-certificate \
        --certificate-arn "$CERT_ARN" \
        --region "$AWS_DEFAULT_REGION" \
        --query 'Certificate.Status' \
        --output text)

    echo "Certificate status: $STATUS (elapsed: $((ELAPSED / 60))m)"

    if [ "$STATUS" = "ISSUED" ]; then
        echo "Certificate successfully issued!"
        echo "CERTIFICATE_ARN=$CERT_ARN" > /tmp/acm-output.env
        exit 0
    elif [ "$STATUS" = "FAILED" ]; then
        echo "ERROR: Certificate validation failed"
        aws acm describe-certificate \
            --certificate-arn "$CERT_ARN" \
            --region "$AWS_DEFAULT_REGION" \
            --query 'Certificate.FailureReason' \
            --output text
        exit 1
    fi

    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

echo "WARNING: Certificate still pending after $MAX_WAIT_MINUTES minutes"
echo "The certificate will continue to validate in the background"
echo "CERTIFICATE_ARN=$CERT_ARN" > /tmp/acm-output.env
echo "CERTIFICATE_STATUS=PENDING" >> /tmp/acm-output.env
exit 0
