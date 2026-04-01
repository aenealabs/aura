#!/bin/bash
# Aura CLI Cross-Platform Builder
# Builds native installers for all supported platforms

set -euo pipefail

# Configuration
VERSION="${VERSION:-1.0.0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-$SCRIPT_DIR/dist}"
PARALLEL="${PARALLEL:-false}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

print_header() {
    echo ""
    echo "========================================"
    echo "  Aura CLI Cross-Platform Builder"
    echo "  Version: $VERSION"
    echo "========================================"
    echo ""
}

detect_platform() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        CYGWIN*|MINGW*|MSYS*) echo "windows";;
        *)          echo "unknown";;
    esac
}

check_dependencies() {
    log_info "Checking dependencies..."

    local missing=()

    # Python 3.11+
    if ! command -v python3 &> /dev/null; then
        missing+=("python3")
    fi

    # PyInstaller
    if ! python3 -c "import PyInstaller" 2>/dev/null; then
        log_warning "PyInstaller not found, installing..."
        pip3 install pyinstaller
    fi

    # Platform-specific checks
    local platform=$(detect_platform)

    case "$platform" in
        macos)
            if ! command -v pkgbuild &> /dev/null; then
                missing+=("Xcode Command Line Tools")
            fi
            ;;
        linux)
            if ! command -v dpkg-deb &> /dev/null && ! command -v rpmbuild &> /dev/null; then
                log_warning "Neither dpkg-deb nor rpmbuild found"
            fi
            ;;
        windows)
            if ! command -v wix &> /dev/null; then
                missing+=("WiX Toolset")
            fi
            ;;
    esac

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing dependencies: ${missing[*]}"
        exit 1
    fi

    log_success "All dependencies satisfied"
}

build_standalone() {
    local platform="$1"
    local arch="$2"

    log_info "Building standalone executable for $platform-$arch..."

    local build_dir="$SCRIPT_DIR/build/$platform-$arch"
    mkdir -p "$build_dir"

    cd "$REPO_ROOT"

    python3 -m PyInstaller \
        --onefile \
        --name aura \
        --strip \
        --clean \
        --distpath "$build_dir/dist" \
        --workpath "$build_dir/work" \
        --specpath "$build_dir" \
        src/cli/main.py

    log_success "Built executable: $build_dir/dist/aura"
}

build_macos() {
    log_info "Building macOS PKG..."

    if [ -f "$SCRIPT_DIR/macos/build-pkg.sh" ]; then
        VERSION="$VERSION" OUTPUT_DIR="$OUTPUT_DIR" bash "$SCRIPT_DIR/macos/build-pkg.sh"
        log_success "macOS PKG built"
    else
        log_warning "macOS build script not found"
    fi
}

build_linux_deb() {
    log_info "Building Debian package..."

    if [ -f "$SCRIPT_DIR/linux/debian/build-deb.sh" ]; then
        VERSION="$VERSION" OUTPUT_DIR="$OUTPUT_DIR" bash "$SCRIPT_DIR/linux/debian/build-deb.sh"
        log_success "Debian package built"
    else
        log_warning "Debian build script not found"
    fi
}

build_linux_rpm() {
    log_info "Building RPM package..."

    if [ -f "$SCRIPT_DIR/linux/rpm/build-rpm.sh" ]; then
        VERSION="$VERSION" OUTPUT_DIR="$OUTPUT_DIR" bash "$SCRIPT_DIR/linux/rpm/build-rpm.sh"
        log_success "RPM package built"
    else
        log_warning "RPM build script not found"
    fi
}

build_windows() {
    log_info "Building Windows MSI..."

    if [ -f "$SCRIPT_DIR/windows/build-msi.ps1" ]; then
        if command -v pwsh &> /dev/null; then
            pwsh -File "$SCRIPT_DIR/windows/build-msi.ps1" -Version "$VERSION" -OutputDir "$OUTPUT_DIR"
            log_success "Windows MSI built"
        else
            log_warning "PowerShell not available, skipping Windows build"
        fi
    else
        log_warning "Windows build script not found"
    fi
}

create_tarball() {
    local platform="$1"
    local arch="$2"

    log_info "Creating tarball for $platform-$arch..."

    local build_dir="$SCRIPT_DIR/build/$platform-$arch"
    local tarball_dir="$build_dir/tarball/aura-cli-$VERSION"

    mkdir -p "$tarball_dir"/{completions,docs}

    # Copy binary
    if [ "$platform" = "windows" ]; then
        cp "$build_dir/dist/aura.exe" "$tarball_dir/"
    else
        cp "$build_dir/dist/aura" "$tarball_dir/"
        chmod 755 "$tarball_dir/aura"
    fi

    # Copy completions
    if [ -f "$SCRIPT_DIR/linux/debian/build-deb.sh" ]; then
        # Extract completions from build scripts
        cat > "$tarball_dir/completions/aura.bash" << 'BASH_COMP'
_aura_completions() {
    local cur prev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    local commands="status config license deploy health logs"
    COMPREPLY=( $(compgen -W "${commands}" -- ${cur}) )
}
complete -F _aura_completions aura
BASH_COMP

        cat > "$tarball_dir/completions/aura.zsh" << 'ZSH_COMP'
#compdef aura
_aura() {
    local -a commands
    commands=('status' 'config' 'license' 'deploy' 'health' 'logs')
    _describe 'command' commands
}
_aura "$@"
ZSH_COMP
    fi

    # Copy docs
    cp "$REPO_ROOT/LICENSE" "$tarball_dir/"
    cp "$REPO_ROOT/README.md" "$tarball_dir/"

    # Create man page
    cat > "$tarball_dir/docs/aura.1" << 'MANPAGE'
.TH AURA 1 "January 2026" "Version 1.0.0" "Aura CLI Manual"
.SH NAME
aura \- Project Aura Command Line Interface
.SH SYNOPSIS
.B aura
[\fIOPTIONS\fR] \fICOMMAND\fR
.SH COMMANDS
status, config, license, deploy, health, logs
.SH AUTHOR
Aenea Labs <support@aenealabs.com>
MANPAGE

    # Create tarball
    mkdir -p "$OUTPUT_DIR"
    cd "$build_dir/tarball"

    if [ "$platform" = "windows" ]; then
        zip -r "$OUTPUT_DIR/aura-cli-$VERSION-$platform-$arch.zip" "aura-cli-$VERSION"
        log_success "Created: aura-cli-$VERSION-$platform-$arch.zip"
    else
        tar czf "$OUTPUT_DIR/aura-cli-$VERSION-$platform-$arch.tar.gz" "aura-cli-$VERSION"
        log_success "Created: aura-cli-$VERSION-$platform-$arch.tar.gz"
    fi
}

generate_checksums() {
    log_info "Generating checksums..."

    cd "$OUTPUT_DIR"

    # Clear existing checksums
    > SHA256SUMS.txt

    # Generate checksums for all files
    for file in *.{tar.gz,zip,msi,pkg,deb,rpm} 2>/dev/null; do
        if [ -f "$file" ]; then
            if command -v sha256sum &> /dev/null; then
                sha256sum "$file" >> SHA256SUMS.txt
            else
                shasum -a 256 "$file" >> SHA256SUMS.txt
            fi
        fi
    done

    log_success "Checksums written to SHA256SUMS.txt"
}

update_homebrew_formula() {
    log_info "Updating Homebrew formula..."

    local formula="$SCRIPT_DIR/homebrew/aura-cli.rb"

    if [ ! -f "$formula" ]; then
        log_warning "Homebrew formula not found"
        return
    fi

    # Update version
    sed -i.bak "s/version \".*\"/version \"$VERSION\"/" "$formula"
    rm -f "$formula.bak"

    # Update checksums from SHA256SUMS.txt
    if [ -f "$OUTPUT_DIR/SHA256SUMS.txt" ]; then
        local macos_arm64_sha=$(grep "macos-arm64" "$OUTPUT_DIR/SHA256SUMS.txt" | cut -d' ' -f1 || echo "REPLACE_WITH_ARM64_SHA256")
        local macos_x64_sha=$(grep "macos-x64" "$OUTPUT_DIR/SHA256SUMS.txt" | cut -d' ' -f1 || echo "REPLACE_WITH_X64_SHA256")
        local linux_arm64_sha=$(grep "linux-arm64" "$OUTPUT_DIR/SHA256SUMS.txt" | cut -d' ' -f1 || echo "REPLACE_WITH_LINUX_ARM64_SHA256")
        local linux_x64_sha=$(grep "linux-x64" "$OUTPUT_DIR/SHA256SUMS.txt" | cut -d' ' -f1 || echo "REPLACE_WITH_LINUX_X64_SHA256")

        # Update formula (simplified - in production use proper template)
        log_info "Update Homebrew formula SHA256 values manually with:"
        echo "  macos-arm64: $macos_arm64_sha"
        echo "  macos-x64:   $macos_x64_sha"
        echo "  linux-arm64: $linux_arm64_sha"
        echo "  linux-x64:   $linux_x64_sha"
    fi

    log_success "Homebrew formula updated"
}

print_summary() {
    echo ""
    echo "========================================"
    echo "  Build Summary"
    echo "========================================"
    echo ""
    echo "Output directory: $OUTPUT_DIR"
    echo ""
    echo "Built artifacts:"
    ls -la "$OUTPUT_DIR" 2>/dev/null || echo "  (none)"
    echo ""

    if [ -f "$OUTPUT_DIR/SHA256SUMS.txt" ]; then
        echo "Checksums:"
        cat "$OUTPUT_DIR/SHA256SUMS.txt"
    fi

    echo ""
    echo "========================================"
}

main() {
    print_header
    check_dependencies

    local platform=$(detect_platform)
    local arch=$(uname -m)

    # Normalize architecture names
    case "$arch" in
        x86_64) arch="x64";;
        aarch64|arm64) arch="arm64";;
    esac

    mkdir -p "$OUTPUT_DIR"

    # Build for current platform
    log_info "Building for $platform-$arch..."

    # Build standalone executable
    build_standalone "$platform" "$arch"

    # Create tarball
    create_tarball "$platform" "$arch"

    # Platform-specific installers
    case "$platform" in
        macos)
            build_macos
            ;;
        linux)
            if command -v dpkg-deb &> /dev/null; then
                build_linux_deb
            fi
            if command -v rpmbuild &> /dev/null; then
                build_linux_rpm
            fi
            ;;
        windows)
            build_windows
            ;;
    esac

    # Generate checksums
    generate_checksums

    # Update Homebrew formula
    update_homebrew_formula

    print_summary
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --version)
            VERSION="$2"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --parallel)
            PARALLEL=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --version VERSION    Set version (default: 1.0.0)"
            echo "  --output DIR         Output directory"
            echo "  --parallel           Build platforms in parallel"
            echo "  --help               Show this help"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

main
