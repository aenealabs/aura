#!/bin/bash
# Project Aura - Quick HITL Workflow Trigger
#
# Stages code to S3 and triggers the HITL patch workflow.
#
# Usage:
#   ./trigger-hitl-test.sh                    # Test with this repo
#   ./trigger-hitl-test.sh --patch-id MY-001  # Custom patch ID
#   ./trigger-hitl-test.sh --help             # Show all options

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default values
REPO_URL="${REPO_URL:-https://github.com/aenealabs/aura}"
BRANCH="${BRANCH:-main}"
PATCH_ID="${PATCH_ID:-TEST-$(date +%s)}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
TEST_SUITE="${TEST_SUITE:-unit}"
SEVERITY="${SEVERITY:-MEDIUM}"
AWS_PROFILE="${AWS_PROFILE:-aura-admin}"

# Export AWS profile
export AWS_PROFILE

# Parse arguments
TRIGGER=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --repo)
            REPO_URL="$2"
            shift 2
            ;;
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        --patch-id)
            PATCH_ID="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --test-suite)
            TEST_SUITE="$2"
            shift 2
            ;;
        --severity)
            SEVERITY="$2"
            shift 2
            ;;
        --trigger)
            TRIGGER=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --repo URL         Git repository URL (default: aura)"
            echo "  --branch BRANCH    Git branch (default: main)"
            echo "  --patch-id ID      Patch identifier (default: TEST-<timestamp>)"
            echo "  --environment ENV  Target environment (default: dev)"
            echo "  --test-suite SUITE Test suite: unit|integration|security|all (default: unit)"
            echo "  --severity SEV     Severity: LOW|MEDIUM|HIGH|CRITICAL (default: MEDIUM)"
            echo "  --trigger          Also trigger the workflow after staging"
            echo "  --help             Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Stage code only"
            echo "  $0 --trigger                          # Stage and trigger workflow"
            echo "  $0 --patch-id FIX-001 --trigger       # Custom patch ID"
            echo "  $0 --test-suite security --trigger    # Run security tests"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "Aura HITL Workflow - Code Staging"
echo "=========================================="
echo "Repository:  $REPO_URL"
echo "Branch:      $BRANCH"
echo "Patch ID:    $PATCH_ID"
echo "Environment: $ENVIRONMENT"
echo "Test Suite:  $TEST_SUITE"
echo "Severity:    $SEVERITY"
echo "Trigger:     $TRIGGER"
echo "=========================================="

# Build command
CMD="python3 $SCRIPT_DIR/stage-code-for-sandbox.py"
CMD="$CMD --repo $REPO_URL"
CMD="$CMD --branch $BRANCH"
CMD="$CMD --patch-id $PATCH_ID"
CMD="$CMD --environment $ENVIRONMENT"
CMD="$CMD --test-suite $TEST_SUITE"
CMD="$CMD --severity $SEVERITY"

if [ "$TRIGGER" = true ]; then
    CMD="$CMD --trigger"
fi

# Run staging script
$CMD

echo ""
echo "Done!"
