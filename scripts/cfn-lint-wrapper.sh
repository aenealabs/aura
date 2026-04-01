#!/bin/bash
# cfn-lint wrapper script for Project Aura
# Standardizes cfn-lint exit code handling across all buildspecs
#
# Exit codes from cfn-lint:
#   0 - No errors or warnings
#   2 - Error parsing template
#   4 - Warnings found (but template is valid)
#   6 - Errors found
#   8 - Both errors and warnings found
#
# This wrapper converts warnings (exit 4) to success (exit 0) while
# preserving actual errors. This allows builds to continue when
# cfn-lint doesn't recognize valid AWS actions (W3037).
#
# Usage:
#   ./scripts/cfn-lint-wrapper.sh deploy/cloudformation/template.yaml
#   ./scripts/cfn-lint-wrapper.sh deploy/cloudformation/*.yaml
#   ./scripts/cfn-lint-wrapper.sh --ignore-checks W3037 deploy/cloudformation/template.yaml

set -o pipefail

# Colors for output
RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Check if cfn-lint is installed
if ! command -v cfn-lint &> /dev/null; then
    echo -e "${RED}[cfn-lint] ERROR: cfn-lint is not installed${NC}"
    echo "Install with: pip install cfn-lint"
    exit 1
fi

# Check if arguments were provided
if [ $# -eq 0 ]; then
    echo -e "${YELLOW}Usage: $0 [cfn-lint-options] <template-file(s)>${NC}"
    echo "Example: $0 deploy/cloudformation/networking.yaml"
    echo "Example: $0 --ignore-checks W3037 deploy/cloudformation/*.yaml"
    exit 1
fi

# Run cfn-lint with all arguments
OUTPUT=$(cfn-lint "$@" 2>&1)
EXIT_CODE=$?

# Process exit code
case $EXIT_CODE in
    0)
        # No errors or warnings
        echo -e "${GREEN}[cfn-lint] PASSED${NC}"
        exit 0
        ;;
    4)
        # Warnings only - treat as non-blocking
        echo -e "${YELLOW}[cfn-lint] WARNINGS (non-blocking):${NC}"
        echo "$OUTPUT"
        echo ""
        echo -e "${YELLOW}[cfn-lint] Templates are valid but have warnings. Build will continue.${NC}"

        # Check for W3037 warnings specifically and provide guidance
        if echo "$OUTPUT" | grep -q "W3037"; then
            echo ""
            echo -e "${YELLOW}[cfn-lint] Note: W3037 warnings indicate IAM actions not recognized by cfn-lint.${NC}"
            echo -e "${YELLOW}         These may be valid newer AWS actions. Run 'scripts/validate_iam_actions.py'${NC}"
            echo -e "${YELLOW}         to verify against the AWS IAM service database.${NC}"
        fi
        exit 0
        ;;
    2)
        # Parse error
        echo -e "${RED}[cfn-lint] PARSE ERROR:${NC}"
        echo "$OUTPUT"
        exit 2
        ;;
    6)
        # Errors found
        echo -e "${RED}[cfn-lint] ERRORS:${NC}"
        echo "$OUTPUT"
        exit 6
        ;;
    8)
        # Both errors and warnings
        echo -e "${RED}[cfn-lint] ERRORS AND WARNINGS:${NC}"
        echo "$OUTPUT"
        exit 8
        ;;
    *)
        # Unknown exit code
        echo -e "${RED}[cfn-lint] UNEXPECTED EXIT CODE: $EXIT_CODE${NC}"
        echo "$OUTPUT"
        exit $EXIT_CODE
        ;;
esac
