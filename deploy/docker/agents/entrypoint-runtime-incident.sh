#!/bin/bash
#
# RuntimeIncidentAgent Entrypoint Script
#
# This script runs as the ENTRYPOINT for the RuntimeIncidentAgent Docker container.
# It handles incident event parsing from environment variables and executes the investigation.
#
# Usage (ECS Task):
#   Environment Variables:
#     - INCIDENT_ID: UUID of the incident
#     - INCIDENT_EVENT: JSON-encoded EventBridge event
#     - ENVIRONMENT: dev/qa/prod
#
# Exit Codes:
#   0: Investigation successful
#   1: Investigation failed
#   2: Invalid arguments or configuration
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate required environment variables
validate_environment() {
    local missing=0

    if [ -z "$INCIDENT_ID" ]; then
        log_error "INCIDENT_ID environment variable not set"
        missing=1
    fi

    if [ -z "$INCIDENT_EVENT" ]; then
        log_error "INCIDENT_EVENT environment variable not set"
        missing=1
    fi

    if [ -z "$ENVIRONMENT" ]; then
        log_warning "ENVIRONMENT not set, defaulting to 'dev'"
        export ENVIRONMENT=dev
    fi

    if [ $missing -eq 1 ]; then
        log_error "Missing required environment variables"
        exit 2
    fi
}

# Main execution
main() {
    log_info "RuntimeIncidentAgent starting..."
    log_info "Incident ID: $INCIDENT_ID"
    log_info "Environment: $ENVIRONMENT"
    log_info "AWS Region: ${AWS_DEFAULT_REGION:-us-east-1}"

    # Validate environment
    validate_environment

    # Create temporary file for incident event
    INCIDENT_FILE=$(mktemp)
    echo "$INCIDENT_EVENT" > "$INCIDENT_FILE"

    log_info "Incident event written to: $INCIDENT_FILE"

    # Execute Python agent
    log_info "Starting investigation..."

    if python3 -m src.agents.runtime_incident_cli \
        --incident-id "$INCIDENT_ID" \
        --incident-file "$INCIDENT_FILE" \
        --environment "$ENVIRONMENT"; then

        log_success "Investigation completed successfully"

        # Cleanup
        rm -f "$INCIDENT_FILE"

        exit 0
    else
        EXIT_CODE=$?
        log_error "Investigation failed with exit code: $EXIT_CODE"

        # Cleanup
        rm -f "$INCIDENT_FILE"

        exit 1
    fi
}

# Handle different commands
case "${1:-investigate}" in
    investigate)
        main
        ;;
    test)
        log_info "Running test mode..."
        python3 -c "from src.agents.runtime_incident_agent import RuntimeIncidentAgent; print('✓ RuntimeIncidentAgent imported successfully')"
        log_success "Test passed"
        exit 0
        ;;
    version)
        log_info "RuntimeIncidentAgent v1.0.0 (ADR-025)"
        python3 --version
        exit 0
        ;;
    bash)
        log_info "Starting interactive bash shell..."
        exec /bin/bash
        ;;
    *)
        log_error "Unknown command: $1"
        log_info "Available commands: investigate (default), test, version, bash"
        exit 2
        ;;
esac
