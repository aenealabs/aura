#!/bin/bash
#
# Project Aura - Load Test Runner
#
# Runs k6 load tests with configurable scenarios and profiles.
#
# Issue: #13 - Implement load testing framework
#
# Usage:
#   ./tests/load/run-load-tests.sh                    # Run smoke tests
#   ./tests/load/run-load-tests.sh --profile stress   # Run stress tests
#   ./tests/load/run-load-tests.sh --scenario api     # Run API tests only
#
# Prerequisites:
#   - k6 installed: brew install k6 (macOS) or apt install k6 (Linux)
#   - API endpoint accessible

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="${SCRIPT_DIR}/results"

# Defaults
PROFILE="${PROFILE:-smoke}"
SCENARIO="${SCENARIO:-all}"
BASE_URL="${BASE_URL:-http://localhost:8000}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-json}"

# =============================================================================
# Parse Arguments
# =============================================================================

while [[ $# -gt 0 ]]; do
  case $1 in
    --profile|-p)
      PROFILE="$2"
      shift 2
      ;;
    --scenario|-s)
      SCENARIO="$2"
      shift 2
      ;;
    --url|-u)
      BASE_URL="$2"
      shift 2
      ;;
    --output|-o)
      OUTPUT_FORMAT="$2"
      shift 2
      ;;
    --help|-h)
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --profile, -p   Load profile: smoke, average, stress, spike, soak (default: smoke)"
      echo "  --scenario, -s  Test scenario: api, database, hitl, all (default: all)"
      echo "  --url, -u       Base URL for API (default: http://localhost:8000)"
      echo "  --output, -o    Output format: json, influxdb (default: json)"
      echo "  --help, -h      Show this help message"
      echo ""
      echo "Profiles:"
      echo "  smoke     - Minimal load (1 VU, 30s) - verify tests work"
      echo "  average   - Normal load (10 VUs, 9m) - typical traffic"
      echo "  stress    - High load (10-150 VUs, 19m) - find limits"
      echo "  spike     - Sudden surge (200 VUs spike) - test resilience"
      echo "  soak      - Extended (20 VUs, 40m) - detect memory leaks"
      echo ""
      echo "Examples:"
      echo "  $0 --profile stress --scenario api"
      echo "  $0 --url https://api.aura.dev --profile average"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# =============================================================================
# Validation
# =============================================================================

# Check k6 is installed
if ! command -v k6 &> /dev/null; then
  echo "Error: k6 is not installed"
  echo "Install with: brew install k6 (macOS) or apt install k6 (Linux)"
  exit 1
fi

# Validate profile
case $PROFILE in
  smoke|average|stress|spike|soak)
    ;;
  *)
    echo "Error: Invalid profile '$PROFILE'"
    echo "Valid profiles: smoke, average, stress, spike, soak"
    exit 1
    ;;
esac

# Validate scenario
case $SCENARIO in
  api|database|hitl|all)
    ;;
  *)
    echo "Error: Invalid scenario '$SCENARIO'"
    echo "Valid scenarios: api, database, hitl, all"
    exit 1
    ;;
esac

# Ensure results directory exists
mkdir -p "$RESULTS_DIR"

# =============================================================================
# Run Tests
# =============================================================================

echo "=============================================="
echo "Project Aura - Load Testing"
echo "=============================================="
echo "Profile:    $PROFILE"
echo "Scenario:   $SCENARIO"
echo "Base URL:   $BASE_URL"
echo "Results:    $RESULTS_DIR"
echo "=============================================="
echo ""

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FAILED=0

run_scenario() {
  local name=$1
  local script=$2

  echo ">>> Running $name scenario..."

  if k6 run \
    --env PROFILE="$PROFILE" \
    --env BASE_URL="$BASE_URL" \
    --out "json=${RESULTS_DIR}/${name}_${PROFILE}_${TIMESTAMP}.json" \
    "$script"; then
    echo ">>> $name completed successfully"
  else
    echo ">>> $name FAILED"
    FAILED=1
  fi

  echo ""
}

# Run selected scenarios
case $SCENARIO in
  api)
    run_scenario "api_endpoints" "${SCRIPT_DIR}/scenarios/api_endpoints.js"
    ;;
  database)
    run_scenario "database_performance" "${SCRIPT_DIR}/scenarios/database_performance.js"
    ;;
  hitl)
    run_scenario "hitl_workflow" "${SCRIPT_DIR}/scenarios/hitl_workflow.js"
    ;;
  all)
    run_scenario "api_endpoints" "${SCRIPT_DIR}/scenarios/api_endpoints.js"
    run_scenario "database_performance" "${SCRIPT_DIR}/scenarios/database_performance.js"
    run_scenario "hitl_workflow" "${SCRIPT_DIR}/scenarios/hitl_workflow.js"
    ;;
esac

# =============================================================================
# Summary
# =============================================================================

echo "=============================================="
echo "Load Testing Complete"
echo "=============================================="
echo "Results saved to: $RESULTS_DIR"
echo ""

if [ $FAILED -eq 0 ]; then
  echo "Status: ALL TESTS PASSED"
  exit 0
else
  echo "Status: SOME TESTS FAILED"
  exit 1
fi
