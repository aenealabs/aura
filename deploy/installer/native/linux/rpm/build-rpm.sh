#!/bin/bash
# Aura CLI RPM Package Builder
# Requires: rpm-build, python3, pyinstaller

set -euo pipefail

# Configuration
VERSION="${VERSION:-1.0.0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
OUTPUT_DIR="${OUTPUT_DIR:-$SCRIPT_DIR/dist}"

echo "========================================"
echo "  Aura CLI RPM Package Builder"
echo "  Version: $VERSION"
echo "========================================"

# Detect architecture
ARCH=$(uname -m)
echo "Architecture: $ARCH"

# Clean previous build
echo ""
echo "[1/6] Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

# Create source tarball
echo ""
echo "[2/6] Creating source tarball..."

SOURCE_DIR="$BUILD_DIR/aura-cli-$VERSION"
mkdir -p "$SOURCE_DIR"/{src/cli,completions,docs}

# Copy source files
cp -r "$REPO_ROOT/src/cli"/* "$SOURCE_DIR/src/cli/"
cp "$REPO_ROOT/LICENSE" "$SOURCE_DIR/"
cp "$REPO_ROOT/README.md" "$SOURCE_DIR/"

# Create completions directory with placeholder files
cat > "$SOURCE_DIR/completions/aura.bash" << 'EOF'
# Bash completion for Aura CLI

_aura_completions() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    local commands="status config license deploy health logs --version --help --json --no-color"
    local config_cmds="init show set"
    local license_cmds="status activate request"
    local deploy_cmds="status upgrade"

    case "${prev}" in
        aura)
            COMPREPLY=( $(compgen -W "${commands}" -- ${cur}) )
            return 0
            ;;
        config)
            COMPREPLY=( $(compgen -W "${config_cmds}" -- ${cur}) )
            return 0
            ;;
        license)
            COMPREPLY=( $(compgen -W "${license_cmds}" -- ${cur}) )
            return 0
            ;;
        deploy)
            COMPREPLY=( $(compgen -W "${deploy_cmds}" -- ${cur}) )
            return 0
            ;;
    esac

    COMPREPLY=( $(compgen -W "${commands}" -- ${cur}) )
}

complete -F _aura_completions aura
EOF

cat > "$SOURCE_DIR/completions/aura.zsh" << 'EOF'
#compdef aura

_aura() {
    local -a commands
    commands=(
        'status:Show deployment status'
        'config:Configuration management'
        'license:License management'
        'deploy:Deployment management'
        'health:Check system health'
        'logs:View service logs'
    )

    _arguments -C \
        '--version[Show version]' \
        '--help[Show help]' \
        '--json[JSON output]' \
        '--no-color[Disable colors]' \
        '1:command:->command' \
        '*::arg:->args'

    case "$state" in
        command)
            _describe -t commands 'aura commands' commands
            ;;
    esac
}

_aura "$@"
EOF

# Create man page
cat > "$SOURCE_DIR/docs/aura.1" << 'EOF'
.TH AURA 1 "January 2026" "Version 1.0.0" "Aura CLI Manual"
.SH NAME
aura \- Project Aura Command Line Interface
.SH SYNOPSIS
.B aura
[\fIOPTIONS\fR] \fICOMMAND\fR [\fIARGS\fR]
.SH DESCRIPTION
Aura CLI is a command-line tool for managing Project Aura deployments,
licensing, and operations.
.SH COMMANDS
.TP
.B status
Show deployment status
.TP
.B config
Configuration management (init, show, set)
.TP
.B license
License management (status, activate, request)
.TP
.B deploy
Deployment management (status, upgrade)
.TP
.B health
Check system health
.TP
.B logs
View service logs
.SH OPTIONS
.TP
.B \-\-version
Show version information
.TP
.B \-\-json
Output in JSON format
.TP
.B \-\-no\-color
Disable colored output
.SH AUTHOR
Aenea Labs <support@aenealabs.com>
EOF

# Create tarball
cd "$BUILD_DIR"
tar czf "SOURCES/aura-cli-$VERSION.tar.gz" "aura-cli-$VERSION"

# Copy spec file
echo ""
echo "[3/6] Preparing spec file..."
cp "$SCRIPT_DIR/aura-cli.spec" "$BUILD_DIR/SPECS/"
sed -i "s/^Version:.*/Version:        $VERSION/" "$BUILD_DIR/SPECS/aura-cli.spec"

# Build RPM
echo ""
echo "[4/6] Building RPM package..."

rpmbuild \
    --define "_topdir $BUILD_DIR" \
    --define "version $VERSION" \
    -bb "$BUILD_DIR/SPECS/aura-cli.spec"

# Find the built RPM
RPM_FILE=$(find "$BUILD_DIR/RPMS" -name "*.rpm" -type f | head -1)

if [ -z "$RPM_FILE" ]; then
    echo "Error: RPM file not found"
    exit 1
fi

# Copy to output directory
echo ""
echo "[5/6] Copying to output directory..."
mkdir -p "$OUTPUT_DIR"
cp "$RPM_FILE" "$OUTPUT_DIR/"

# Generate checksums
echo ""
echo "[6/6] Generating checksums..."
cd "$OUTPUT_DIR"
RPM_NAME=$(basename "$RPM_FILE")
sha256sum "$RPM_NAME" >> SHA256SUMS.txt

HASH=$(sha256sum "$RPM_NAME" | cut -d' ' -f1)

echo ""
echo "========================================"
echo "  Build Complete!"
echo "  Output: $OUTPUT_DIR/$RPM_NAME"
echo "  SHA256: $HASH"
echo "========================================"
echo ""
echo "Install with: sudo rpm -i $RPM_NAME"
echo "Or: sudo dnf install $RPM_NAME"
