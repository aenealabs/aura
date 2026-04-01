#!/bin/bash
# Aura CLI Debian Package Builder
# Requires: dpkg-dev, debhelper, python3, pyinstaller

set -euo pipefail

# Configuration
VERSION="${VERSION:-1.0.0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
OUTPUT_DIR="${OUTPUT_DIR:-$SCRIPT_DIR/dist}"

echo "========================================"
echo "  Aura CLI Debian Package Builder"
echo "  Version: $VERSION"
echo "========================================"

# Detect architecture
ARCH=$(dpkg --print-architecture)
echo "Architecture: $ARCH"

# Clean previous build
echo ""
echo "[1/6] Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Create package structure
PACKAGE_NAME="aura-cli_${VERSION}-1_${ARCH}"
PKG_DIR="$BUILD_DIR/$PACKAGE_NAME"
mkdir -p "$PKG_DIR"/{DEBIAN,usr/bin,usr/share/doc/aura-cli,usr/share/man/man1}
mkdir -p "$PKG_DIR"/usr/share/{bash-completion/completions,zsh/vendor-completions}

# Build executable with PyInstaller
echo ""
echo "[2/6] Building executable with PyInstaller..."

cd "$REPO_ROOT"
python3 -m PyInstaller \
    --onefile \
    --name aura \
    --strip \
    --clean \
    --distpath "$BUILD_DIR/dist" \
    --workpath "$BUILD_DIR/work" \
    --specpath "$BUILD_DIR" \
    src/cli/main.py

# Copy binary
cp "$BUILD_DIR/dist/aura" "$PKG_DIR/usr/bin/"
chmod 755 "$PKG_DIR/usr/bin/aura"

# Create control file
echo ""
echo "[3/6] Creating package metadata..."

cat > "$PKG_DIR/DEBIAN/control" << EOF
Package: aura-cli
Version: $VERSION-1
Section: devel
Priority: optional
Architecture: $ARCH
Maintainer: Aenea Labs <support@aenealabs.com>
Homepage: https://aenealabs.com
Description: Project Aura Command Line Interface
 Aura CLI is a command-line tool for managing Project Aura deployments.
 .
 Features:
  - Deployment status and health monitoring
  - License management (online and offline)
  - Configuration management
  - Service log viewing
  - Upgrade management
EOF

# Create postinst script
cat > "$PKG_DIR/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e

if [ "$1" = "configure" ]; then
    if /usr/bin/aura --version > /dev/null 2>&1; then
        echo "Aura CLI installed successfully!"
    fi
fi

exit 0
EOF
chmod 755 "$PKG_DIR/DEBIAN/postinst"

# Create prerm script
cat > "$PKG_DIR/DEBIAN/prerm" << 'EOF'
#!/bin/bash
set -e

# Clean up user config on purge
if [ "$1" = "purge" ]; then
    rm -rf /etc/aura 2>/dev/null || true
fi

exit 0
EOF
chmod 755 "$PKG_DIR/DEBIAN/prerm"

# Create bash completion
echo ""
echo "[4/6] Creating shell completions..."

cat > "$PKG_DIR/usr/share/bash-completion/completions/aura" << 'EOF'
# Bash completion for Aura CLI

_aura_completions() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Top-level commands
    local commands="status config license deploy health logs --version --help --json --no-color"

    # Subcommands
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
        *)
            ;;
    esac

    COMPREPLY=( $(compgen -W "${commands}" -- ${cur}) )
}

complete -F _aura_completions aura
EOF

# Create zsh completion
cat > "$PKG_DIR/usr/share/zsh/vendor-completions/_aura" << 'EOF'
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

    local -a config_cmds
    config_cmds=(
        'init:Initialize configuration'
        'show:Show configuration'
        'set:Set configuration value'
    )

    local -a license_cmds
    license_cmds=(
        'status:Show license status'
        'activate:Activate license'
        'request:Generate offline license request'
    )

    local -a deploy_cmds
    deploy_cmds=(
        'status:Show deployment status'
        'upgrade:Upgrade deployment'
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
        args)
            case "$words[1]" in
                config)
                    _describe -t commands 'config commands' config_cmds
                    ;;
                license)
                    _describe -t commands 'license commands' license_cmds
                    ;;
                deploy)
                    _describe -t commands 'deploy commands' deploy_cmds
                    ;;
            esac
            ;;
    esac
}

_aura "$@"
EOF

# Create man page
cat > "$PKG_DIR/usr/share/man/man1/aura.1" << 'EOF'
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
.SH FILES
.TP
.I ~/.aura/config.yaml
User configuration file
.TP
.I ~/.aura/license.key
License key file
.SH ENVIRONMENT
.TP
.B AURA_CONFIG_DIR
Override configuration directory
.TP
.B AURA_API_URL
Override API endpoint URL
.TP
.B NO_COLOR
Disable colored output
.SH AUTHOR
Aenea Labs <support@aenealabs.com>
.SH SEE ALSO
kubectl(1), helm(1)
EOF
gzip -9 "$PKG_DIR/usr/share/man/man1/aura.1"

# Copy documentation
cp "$REPO_ROOT/LICENSE" "$PKG_DIR/usr/share/doc/aura-cli/copyright"
cp "$REPO_ROOT/README.md" "$PKG_DIR/usr/share/doc/aura-cli/"

# Build package
echo ""
echo "[5/6] Building DEB package..."

dpkg-deb --build --root-owner-group "$PKG_DIR"

# Copy to output directory
echo ""
echo "[6/6] Copying to output directory..."
mkdir -p "$OUTPUT_DIR"
mv "$BUILD_DIR/${PACKAGE_NAME}.deb" "$OUTPUT_DIR/"

# Generate checksums
cd "$OUTPUT_DIR"
sha256sum "${PACKAGE_NAME}.deb" >> SHA256SUMS.txt

DEB_PATH="$OUTPUT_DIR/${PACKAGE_NAME}.deb"
HASH=$(sha256sum "$DEB_PATH" | cut -d' ' -f1)

echo ""
echo "========================================"
echo "  Build Complete!"
echo "  Output: $DEB_PATH"
echo "  SHA256: $HASH"
echo "========================================"
echo ""
echo "Install with: sudo dpkg -i ${PACKAGE_NAME}.deb"
