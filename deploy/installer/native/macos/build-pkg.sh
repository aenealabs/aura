#!/bin/bash
# Aura CLI macOS PKG Builder
# Requires: Xcode Command Line Tools, Python 3.11+, PyInstaller

set -euo pipefail

# Configuration
VERSION="${VERSION:-1.0.0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
OUTPUT_DIR="${OUTPUT_DIR:-$SCRIPT_DIR/dist}"

# Code signing options
SIGN="${SIGN:-false}"
DEVELOPER_ID="${DEVELOPER_ID:-}"
NOTARIZE="${NOTARIZE:-false}"
APPLE_ID="${APPLE_ID:-}"
TEAM_ID="${TEAM_ID:-}"
APP_PASSWORD="${APP_PASSWORD:-}"

echo "========================================"
echo "  Aura CLI macOS PKG Builder"
echo "  Version: $VERSION"
echo "========================================"

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    ARCH_NAME="arm64"
else
    ARCH_NAME="x64"
fi
echo "Architecture: $ARCH_NAME"

# Clean previous build
echo ""
echo "[1/7] Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"/{root/usr/local/bin,scripts,resources}

# Create PyInstaller spec
echo ""
echo "[2/7] Building executable with PyInstaller..."

cat > "$BUILD_DIR/aura.spec" << 'EOF'
# -*- mode: python ; coding: utf-8 -*-

import sys
sys.path.insert(0, '__REPO_ROOT__')

block_cipher = None

a = Analysis(
    ['__REPO_ROOT__/src/cli/main.py'],
    pathex=['__REPO_ROOT__'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'src.services.licensing',
        'src.services.licensing.license_service',
        'src.services.licensing.hardware_fingerprint',
        'src.services.licensing.offline_validator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='aura',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
EOF

# Replace placeholder with actual path
sed -i '' "s|__REPO_ROOT__|$REPO_ROOT|g" "$BUILD_DIR/aura.spec"

# Run PyInstaller
cd "$BUILD_DIR"
python3 -m PyInstaller --clean --noconfirm aura.spec

# Copy binary to package root
cp "$BUILD_DIR/dist/aura" "$BUILD_DIR/root/usr/local/bin/"
chmod 755 "$BUILD_DIR/root/usr/local/bin/aura"

# Create postinstall script
echo ""
echo "[3/7] Creating installer scripts..."

cat > "$BUILD_DIR/scripts/postinstall" << 'EOF'
#!/bin/bash
# Post-installation script for Aura CLI

# Ensure /usr/local/bin is in PATH
SHELL_RC=""
if [ -n "$BASH_VERSION" ]; then
    if [ -f "$HOME/.bash_profile" ]; then
        SHELL_RC="$HOME/.bash_profile"
    else
        SHELL_RC="$HOME/.bashrc"
    fi
elif [ -n "$ZSH_VERSION" ]; then
    SHELL_RC="$HOME/.zshrc"
fi

# Create config directory
mkdir -p "$HOME/.aura"

# Verify installation
if /usr/local/bin/aura --version > /dev/null 2>&1; then
    echo "Aura CLI installed successfully!"
    /usr/local/bin/aura --version
else
    echo "Warning: Installation completed but verification failed"
    exit 0  # Don't fail the install
fi

exit 0
EOF
chmod 755 "$BUILD_DIR/scripts/postinstall"

# Create preinstall script
cat > "$BUILD_DIR/scripts/preinstall" << 'EOF'
#!/bin/bash
# Pre-installation script for Aura CLI

# Check for existing installation
if [ -f /usr/local/bin/aura ]; then
    echo "Existing Aura CLI installation detected"
    EXISTING_VERSION=$(/usr/local/bin/aura --version 2>/dev/null | head -1 || echo "unknown")
    echo "Current version: $EXISTING_VERSION"
fi

exit 0
EOF
chmod 755 "$BUILD_DIR/scripts/preinstall"

# Create welcome text
cat > "$BUILD_DIR/resources/welcome.txt" << EOF
Welcome to the Aura CLI Installer

This will install the Aura Command Line Interface (CLI) for
managing your Project Aura deployment.

Version: $VERSION
Architecture: $ARCH_NAME

The CLI will be installed to /usr/local/bin/aura

After installation, you can use the CLI by running:
    aura --help
    aura status
    aura license status
EOF

# Create license file
cp "$REPO_ROOT/LICENSE" "$BUILD_DIR/resources/license.txt"

# Create readme
cat > "$BUILD_DIR/resources/readme.txt" << EOF
Aura CLI v$VERSION

USAGE:
    aura [OPTIONS] <COMMAND>

COMMANDS:
    status      Show deployment status
    config      Configuration management
    license     License management
    deploy      Deployment management
    health      Check system health
    logs        View service logs

EXAMPLES:
    aura status                 # Show deployment status
    aura license status         # Show license status
    aura health --verbose       # Detailed health check

SUPPORT:
    Documentation: https://docs.aenealabs.com
    Email: support@aenealabs.com
EOF

# Build component package
echo ""
echo "[4/7] Building component package..."

pkgbuild \
    --root "$BUILD_DIR/root" \
    --scripts "$BUILD_DIR/scripts" \
    --identifier "com.aenealabs.aura-cli" \
    --version "$VERSION" \
    --install-location "/" \
    "$BUILD_DIR/aura-cli-component.pkg"

# Create distribution XML
echo ""
echo "[5/7] Creating distribution package..."

cat > "$BUILD_DIR/distribution.xml" << EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>Aura CLI</title>
    <organization>com.aenealabs</organization>
    <domains enable_anywhere="false" enable_currentUserHome="false" enable_localSystem="true"/>
    <options customize="never" require-scripts="false" hostArchitectures="x86_64,arm64"/>

    <welcome file="welcome.txt"/>
    <license file="license.txt"/>
    <readme file="readme.txt"/>

    <choices-outline>
        <line choice="com.aenealabs.aura-cli"/>
    </choices-outline>

    <choice id="com.aenealabs.aura-cli" visible="false">
        <pkg-ref id="com.aenealabs.aura-cli"/>
    </choice>

    <pkg-ref id="com.aenealabs.aura-cli"
             version="$VERSION"
             onConclusion="none">aura-cli-component.pkg</pkg-ref>

    <installation-check script="installCheck()"/>
    <script>
    function installCheck() {
        if (system.compareVersions(system.version.ProductVersion, '10.15') < 0) {
            my.result.message = 'Aura CLI requires macOS 10.15 (Catalina) or later.';
            my.result.type = 'Fatal';
            return false;
        }
        return true;
    }
    </script>
</installer-gui-script>
EOF

# Build distribution package
productbuild \
    --distribution "$BUILD_DIR/distribution.xml" \
    --resources "$BUILD_DIR/resources" \
    --package-path "$BUILD_DIR" \
    "$BUILD_DIR/aura-cli-$VERSION-macos-$ARCH_NAME.pkg"

# Sign package if requested
if [ "$SIGN" = "true" ] && [ -n "$DEVELOPER_ID" ]; then
    echo ""
    echo "[6/7] Signing package..."

    productsign \
        --sign "Developer ID Installer: $DEVELOPER_ID" \
        "$BUILD_DIR/aura-cli-$VERSION-macos-$ARCH_NAME.pkg" \
        "$BUILD_DIR/aura-cli-$VERSION-macos-$ARCH_NAME-signed.pkg"

    mv "$BUILD_DIR/aura-cli-$VERSION-macos-$ARCH_NAME-signed.pkg" \
       "$BUILD_DIR/aura-cli-$VERSION-macos-$ARCH_NAME.pkg"

    # Notarize if requested
    if [ "$NOTARIZE" = "true" ] && [ -n "$APPLE_ID" ] && [ -n "$TEAM_ID" ]; then
        echo "Submitting for notarization..."

        xcrun notarytool submit \
            "$BUILD_DIR/aura-cli-$VERSION-macos-$ARCH_NAME.pkg" \
            --apple-id "$APPLE_ID" \
            --team-id "$TEAM_ID" \
            --password "$APP_PASSWORD" \
            --wait

        echo "Stapling notarization ticket..."
        xcrun stapler staple "$BUILD_DIR/aura-cli-$VERSION-macos-$ARCH_NAME.pkg"
    fi
else
    echo ""
    echo "[6/7] Skipping signing (set SIGN=true to enable)"
fi

# Copy to output directory
echo ""
echo "[7/7] Copying to output directory..."
mkdir -p "$OUTPUT_DIR"
cp "$BUILD_DIR/aura-cli-$VERSION-macos-$ARCH_NAME.pkg" "$OUTPUT_DIR/"

# Generate checksums
cd "$OUTPUT_DIR"
shasum -a 256 "aura-cli-$VERSION-macos-$ARCH_NAME.pkg" >> SHA256SUMS.txt

PKG_PATH="$OUTPUT_DIR/aura-cli-$VERSION-macos-$ARCH_NAME.pkg"
HASH=$(shasum -a 256 "$PKG_PATH" | cut -d' ' -f1)

echo ""
echo "========================================"
echo "  Build Complete!"
echo "  Output: $PKG_PATH"
echo "  SHA256: $HASH"
echo "========================================"
