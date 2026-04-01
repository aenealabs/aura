#!/bin/bash
# Project Aura - Sandbox Test Runner Entry Point
#
# Executes patch tests in isolated environment for HITL workflow.
#
# Exit Codes:
#   0 - All tests passed
#   1 - Tests failed
#   2 - Configuration error
#   3 - Clone/setup error

set -e

# ============================================================================
# Configuration
# ============================================================================

WORKSPACE="/app/workspace"
RESULTS_DIR="/app/results"
LOG_FILE="/app/logs/test-runner.log"

# Required environment variables
: "${SANDBOX_ID:?SANDBOX_ID is required}"
: "${PATCH_ID:?PATCH_ID is required}"
: "${TEST_SUITE:=unit}"
: "${CODE_SOURCE:?CODE_SOURCE is required}"  # S3 URI (s3://...) or Git URL (https://...)
: "${BRANCH:=main}"  # Only used for git clone fallback
: "${TIMEOUT_SECONDS:=1800}"

# ============================================================================
# Logging Functions
# ============================================================================

log() {
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] ERROR: $1" | tee -a "$LOG_FILE" >&2
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    log "=========================================="
    log "Aura Sandbox Test Runner Starting"
    log "=========================================="
    log "SANDBOX_ID: $SANDBOX_ID"
    log "PATCH_ID: $PATCH_ID"
    log "TEST_SUITE: $TEST_SUITE"
    log "CODE_SOURCE: $CODE_SOURCE"
    log "BRANCH: $BRANCH"
    log "TIMEOUT: ${TIMEOUT_SECONDS}s"
    log "=========================================="

    # Step 1: Fetch code (S3 or Git)
    log "Step 1: Fetching code from $CODE_SOURCE..."
    cd "$WORKSPACE"
    mkdir -p repo

    if [[ "$CODE_SOURCE" == s3://* ]]; then
        # S3 code staging - download and extract tarball
        log "Downloading from S3 (via VPC endpoint)..."

        if ! aws s3 cp "$CODE_SOURCE" code.tar.gz 2>&1 | tee -a "$LOG_FILE"; then
            log_error "Failed to download code from S3: $CODE_SOURCE"
            exit 3
        fi

        log "Extracting code archive..."
        if ! tar -xzf code.tar.gz -C repo 2>&1 | tee -a "$LOG_FILE"; then
            log_error "Failed to extract code archive"
            exit 3
        fi

        rm -f code.tar.gz
        cd repo
        log "Code extracted successfully from S3"

        # Check if this is a git repo (for commit info)
        if [ -d ".git" ]; then
            log "Commit: $(git rev-parse HEAD 2>/dev/null || echo 'N/A')"
        fi
    else
        # Git clone fallback - for local development/testing with internet access
        log "Cloning from Git repository..."

        if ! git clone --depth 1 --branch "$BRANCH" "$CODE_SOURCE" repo_tmp 2>&1 | tee -a "$LOG_FILE"; then
            log_error "Failed to clone repository: $CODE_SOURCE"
            exit 3
        fi

        # Move contents to repo directory
        mv repo_tmp/* repo_tmp/.[!.]* repo/ 2>/dev/null || true
        rm -rf repo_tmp
        cd repo
        log "Repository cloned successfully"
        log "Commit: $(git rev-parse HEAD)"
    fi

    # Step 2: Dependencies (all pre-installed in Docker image - no network access in sandbox)
    log "Step 2: Checking dependencies..."
    log "Using pre-installed dependencies from Docker image (no network access in sandbox)"
    # NOTE: All dependencies are pre-installed in Docker image. No pip install needed.

    # Step 3: Run tests based on suite type
    log "Step 3: Running $TEST_SUITE tests..."
    TEST_EXIT_CODE=0

    case "$TEST_SUITE" in
        unit)
            log "Running unit tests with pytest..."
            timeout "$TIMEOUT_SECONDS" python -m pytest tests/ \
                -v \
                --tb=short \
                --junit-xml="$RESULTS_DIR/junit.xml" \
                -m "not integration and not e2e" \
                2>&1 | tee -a "$LOG_FILE" || TEST_EXIT_CODE=$?
            ;;
        integration)
            log "Running integration tests with pytest..."
            timeout "$TIMEOUT_SECONDS" python -m pytest tests/ \
                -v \
                --tb=short \
                --junit-xml="$RESULTS_DIR/junit.xml" \
                -m "integration" \
                2>&1 | tee -a "$LOG_FILE" || TEST_EXIT_CODE=$?
            ;;
        security)
            log "Running security tests..."
            # Run bandit security linter
            if command -v bandit &> /dev/null; then
                bandit -r src/ -f json -o "$RESULTS_DIR/bandit.json" 2>&1 | tee -a "$LOG_FILE" || true
            fi
            # Run safety check on dependencies
            if command -v safety &> /dev/null; then
                safety check --json > "$RESULTS_DIR/safety.json" 2>&1 | tee -a "$LOG_FILE" || true
            fi
            # Run pytest with security markers
            timeout "$TIMEOUT_SECONDS" python -m pytest tests/ \
                -v \
                --tb=short \
                --junit-xml="$RESULTS_DIR/junit.xml" \
                -m "security" \
                2>&1 | tee -a "$LOG_FILE" || TEST_EXIT_CODE=$?
            ;;
        all)
            log "Running all tests with pytest..."
            timeout "$TIMEOUT_SECONDS" python -m pytest tests/ \
                -v \
                --tb=short \
                --junit-xml="$RESULTS_DIR/junit.xml" \
                2>&1 | tee -a "$LOG_FILE" || TEST_EXIT_CODE=$?
            ;;
        *)
            log_error "Unknown test suite: $TEST_SUITE"
            exit 2
            ;;
    esac

    # Step 4: Report results
    log "=========================================="
    log "Test Execution Complete"
    log "=========================================="

    if [ $TEST_EXIT_CODE -eq 0 ]; then
        log "RESULT: ALL TESTS PASSED"
        echo "PASSED" > "$RESULTS_DIR/status.txt"
    elif [ $TEST_EXIT_CODE -eq 124 ]; then
        log_error "RESULT: TEST TIMEOUT"
        echo "TIMEOUT" > "$RESULTS_DIR/status.txt"
        exit 1
    else
        log_error "RESULT: TESTS FAILED (exit code: $TEST_EXIT_CODE)"
        echo "FAILED" > "$RESULTS_DIR/status.txt"
        exit 1
    fi

    # Mark as ready for health check
    touch "$WORKSPACE/.ready"

    log "Test runner completed successfully"
    exit 0
}

# Run main function
main "$@"
