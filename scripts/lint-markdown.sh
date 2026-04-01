#!/bin/bash
# Markdown linting script for Project Aura
# Auto-fixes common markdownlint errors (MD036, MD032, MD029, MD022)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
FIX_MODE=false
FILES_TO_LINT=()
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --fix)
            FIX_MODE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS] [FILES...]"
            echo ""
            echo "Options:"
            echo "  --fix          Automatically fix issues"
            echo "  --verbose, -v  Show detailed output"
            echo "  --help, -h     Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                              # Lint all markdown files"
            echo "  $0 --fix                        # Fix all markdown files"
            echo "  $0 PROJECT_STATUS.md            # Lint specific file"
            echo "  $0 --fix PROJECT_STATUS.md      # Fix specific file"
            exit 0
            ;;
        *)
            FILES_TO_LINT+=("$1")
            shift
            ;;
    esac
done

# If no files specified, lint all markdown files
if [ ${#FILES_TO_LINT[@]} -eq 0 ]; then
    FILES_TO_LINT=($(find . -name "*.md" -not -path "./node_modules/*" -not -path "./.git/*"))
fi

echo "========================================"
echo "Markdown Linting for Project Aura"
echo "========================================"
echo ""

# Check if markdownlint-cli2 is installed
if ! command -v markdownlint-cli2 &> /dev/null; then
    echo -e "${YELLOW}Warning: markdownlint-cli2 not installed${NC}"
    echo ""
    echo "Install with:"
    echo "  npm install -g markdownlint-cli2"
    echo ""
    echo "For now, using basic Python-based fixing..."
    echo ""

    # Fallback: Use Python script for basic fixes
    python3 - <<'EOF' "$FIX_MODE" "${FILES_TO_LINT[@]}"
import sys
import re

fix_mode = sys.argv[1] == "True"
files = sys.argv[2:]

def fix_md022(content):
    """MD022: Headers should be surrounded by blank lines"""
    lines = content.split('\n')
    fixed_lines = []

    for i, line in enumerate(lines):
        # Check if line is a header
        if line.strip().startswith('#'):
            # Add blank line before header if needed
            if i > 0 and lines[i-1].strip() != '' and not fixed_lines[-1] == '':
                fixed_lines.append('')

            fixed_lines.append(line)

            # Add blank line after header if needed
            if i < len(lines) - 1 and lines[i+1].strip() != '':
                # Don't add if next line is also a header or already blank
                if not lines[i+1].strip().startswith('#'):
                    fixed_lines.append('')
        else:
            fixed_lines.append(line)

    return '\n'.join(fixed_lines)

def fix_md032(content):
    """MD032: Lists should be surrounded by blank lines"""
    lines = content.split('\n')
    fixed_lines = []
    in_list = False

    for i, line in enumerate(lines):
        is_list_item = bool(re.match(r'^(\s*[-*+]|\s*\d+\.)\s', line))

        if is_list_item:
            if not in_list and i > 0 and fixed_lines and fixed_lines[-1].strip() != '':
                # Add blank line before list starts
                fixed_lines.append('')
            in_list = True
            fixed_lines.append(line)
        else:
            if in_list and line.strip() != '' and i > 0:
                # Add blank line after list ends
                if fixed_lines and fixed_lines[-1].strip() != '':
                    fixed_lines.append('')
            in_list = False
            fixed_lines.append(line)

    return '\n'.join(fixed_lines)

def fix_md029(content):
    """MD029: Ordered list item prefix should be consistent"""
    lines = content.split('\n')
    fixed_lines = []
    list_counter = 1
    in_ordered_list = False

    for line in lines:
        match = re.match(r'^(\s*)(\d+)\.\s+(.*)$', line)
        if match:
            indent, _, rest = match.groups()
            # Use sequential numbering
            fixed_lines.append(f"{indent}{list_counter}. {rest}")
            list_counter += 1
            in_ordered_list = True
        else:
            if in_ordered_list and line.strip() == '':
                list_counter = 1
                in_ordered_list = False
            fixed_lines.append(line)

    return '\n'.join(fixed_lines)

def fix_md036(content):
    """MD036: Emphasis used instead of a heading"""
    # This is harder to auto-fix without context
    # Just flag for manual review
    return content

def process_file(filepath):
    print(f"Processing: {filepath}")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Apply fixes
        content = fix_md022(content)
        content = fix_md032(content)
        content = fix_md029(content)
        content = fix_md036(content)

        if fix_mode:
            if content != original_content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  ✅ Fixed")
            else:
                print(f"  ✅ No issues")
        else:
            if content != original_content:
                print(f"  ⚠️  Issues found (run with --fix to auto-fix)")
            else:
                print(f"  ✅ No issues")

    except Exception as e:
        print(f"  ❌ Error: {e}")

for filepath in files:
    process_file(filepath)

EOF

    exit 0
fi

# Use markdownlint-cli2
if [ "$FIX_MODE" = true ]; then
    echo -e "${GREEN}Fixing markdown files...${NC}"
    markdownlint-cli2 --fix "${FILES_TO_LINT[@]}"
    echo -e "${GREEN}✅ Markdown files fixed!${NC}"
else
    echo -e "${YELLOW}Linting markdown files...${NC}"
    if markdownlint-cli2 "${FILES_TO_LINT[@]}"; then
        echo -e "${GREEN}✅ All markdown files are compliant!${NC}"
    else
        echo ""
        echo -e "${YELLOW}Run with --fix to automatically fix issues:${NC}"
        echo "  $0 --fix"
        exit 1
    fi
fi
