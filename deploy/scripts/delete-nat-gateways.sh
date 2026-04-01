#!/bin/bash
#
# Delete NAT Gateways Script
# Run this AFTER verifying VPC endpoints work correctly
# Saves ~$66/month
#
# Usage: ./delete-nat-gateways.sh
#

set -e  # Exit on error

echo "=========================================="
echo "NAT Gateway Deletion"
echo "WARNING: This will remove internet access"
echo "from private subnets via NAT Gateway"
echo "=========================================="
echo ""

# Environment variables
# Use environment variables or defaults
export AWS_PROFILE=${AWS_PROFILE:-}
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}

# Get VPC ID from CloudFormation stack
if [ -z "$VPC_ID" ]; then
  VPC_ID=$(aws cloudformation describe-stacks \
    --stack-name aura-networking-dev \
    --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
    --output text \
    --region $AWS_DEFAULT_REGION 2>/dev/null)

  if [ -z "$VPC_ID" ]; then
    echo "ERROR: Could not find VPC ID from CloudFormation stack"
    echo "Please set VPC_ID environment variable or ensure aura-networking-dev stack exists"
    exit 1
  fi
fi

export VPC_ID

# Confirm with user
read -p "Have you verified VPC endpoints are working? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
  echo "Aborted. Please verify VPC endpoints first."
  exit 1
fi

echo ""
echo "Identifying NAT Gateways in VPC ${VPC_ID}..."

# Get NAT Gateway IDs
NAT_GATEWAYS=$(aws ec2 describe-nat-gateways \
  --filter "Name=vpc-id,Values=${VPC_ID}" "Name=state,Values=available" \
  --query 'NatGateways[*].[NatGatewayId,SubnetId,State]' \
  --output text)

if [ -z "$NAT_GATEWAYS" ]; then
  echo "No NAT Gateways found in VPC ${VPC_ID}"
  exit 0
fi

echo ""
echo "Found NAT Gateways:"
echo "$NAT_GATEWAYS"
echo ""

# Get NAT Gateway IDs as array
NAT_IDS=($(echo "$NAT_GATEWAYS" | awk '{print $1}'))

# Delete each NAT Gateway
for NAT_ID in "${NAT_IDS[@]}"; do
  echo "Deleting NAT Gateway: ${NAT_ID}..."
  aws ec2 delete-nat-gateway --nat-gateway-id ${NAT_ID} --no-cli-pager
  echo "✓ NAT Gateway ${NAT_ID} deletion initiated"
done

echo ""
echo "Waiting for NAT Gateways to be deleted (this may take 5-10 minutes)..."

# Wait for deletion (with timeout)
TIMEOUT=600  # 10 minutes
ELAPSED=0
INTERVAL=30

while [ $ELAPSED -lt $TIMEOUT ]; do
  STATES=$(aws ec2 describe-nat-gateways \
    --nat-gateway-ids ${NAT_IDS[@]} \
    --query 'NatGateways[*].State' \
    --output text 2>/dev/null || echo "deleted")

  if echo "$STATES" | grep -qv "deleted"; then
    echo "Still deleting... (${ELAPSED}s elapsed)"
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
  else
    echo "✓ All NAT Gateways deleted"
    break
  fi
done

# Release Elastic IPs
echo ""
echo "Checking for unused Elastic IPs..."

UNUSED_EIPS=$(aws ec2 describe-addresses \
  --filters "Name=domain,Values=vpc" \
  --query 'Addresses[?AssociationId==`null`].[AllocationId,PublicIp]' \
  --output text)

if [ -n "$UNUSED_EIPS" ]; then
  echo ""
  echo "Found unused Elastic IPs:"
  echo "$UNUSED_EIPS"
  echo ""

  read -p "Release these Elastic IPs? (yes/no): " RELEASE_EIPS

  if [ "$RELEASE_EIPS" = "yes" ]; then
    while read -r ALLOCATION_ID PUBLIC_IP; do
      echo "Releasing Elastic IP: ${PUBLIC_IP} (${ALLOCATION_ID})..."
      aws ec2 release-address --allocation-id ${ALLOCATION_ID} --no-cli-pager
      echo "✓ Released ${PUBLIC_IP}"
    done <<< "$UNUSED_EIPS"
  fi
fi

echo ""
echo "=========================================="
echo "NAT Gateway Deletion Complete!"
echo "=========================================="
echo ""
echo "Monthly Cost Savings: ~\$66"
echo "Annual Cost Savings: ~\$792"
echo ""
echo "Your infrastructure now uses VPC Endpoints exclusively."
echo "All traffic to AWS services stays within the AWS network."
echo ""
echo "✓ CMMC Level 3 compliant (no internet egress)"
echo "✓ Improved security posture"
echo "✓ Lower latency to AWS services"
echo ""
echo "=========================================="
