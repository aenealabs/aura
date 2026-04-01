# Native Installers Guide

This guide covers installing the Aura CLI using native OS packages and installers.

## Overview

The Aura CLI is available as native installers for:

| Platform | Format | File Pattern |
|----------|--------|--------------|
| Windows | MSI | `aura-cli-{version}-windows-x64.msi` |
| macOS (Intel) | PKG | `aura-cli-{version}-macos-x64.pkg` |
| macOS (Apple Silicon) | PKG | `aura-cli-{version}-macos-arm64.pkg` |
| Ubuntu/Debian | DEB | `aura-cli_{version}-1_{arch}.deb` |
| RHEL/CentOS/Fedora | RPM | `aura-cli-{version}-1.{arch}.rpm` |

## Installation Methods

### Homebrew (macOS/Linux)

The easiest way to install on macOS or Linux:

```bash
# Add the Aenea Labs tap
brew tap aenealabs/tap

# Install Aura CLI
brew install aura-cli

# Verify installation
aura --version
```

To upgrade:

```bash
brew upgrade aura-cli
```

### Windows MSI

1. Download the MSI installer from the [releases page](https://github.com/aenealabs/aura/releases)
2. Double-click to run the installer
3. Follow the installation wizard
4. The CLI is automatically added to PATH

Or via PowerShell:

```powershell
# Download
Invoke-WebRequest -Uri "https://github.com/aenealabs/aura/releases/download/v1.0.0/aura-cli-1.0.0-windows-x64.msi" -OutFile "aura-cli.msi"

# Silent install
msiexec /i aura-cli.msi /quiet /qn

# Verify
aura --version
```

### macOS PKG

1. Download the PKG installer for your architecture:
   - Intel: `aura-cli-{version}-macos-x64.pkg`
   - Apple Silicon: `aura-cli-{version}-macos-arm64.pkg`

2. Double-click to run the installer
3. Follow the installation wizard

Or via Terminal:

```bash
# Download (Apple Silicon example)
curl -LO https://github.com/aenealabs/aura/releases/download/v1.0.0/aura-cli-1.0.0-macos-arm64.pkg

# Install
sudo installer -pkg aura-cli-1.0.0-macos-arm64.pkg -target /

# Verify
aura --version
```

### Ubuntu/Debian (DEB)

```bash
# Download
curl -LO https://github.com/aenealabs/aura/releases/download/v1.0.0/aura-cli_1.0.0-1_amd64.deb

# Install
sudo dpkg -i aura-cli_1.0.0-1_amd64.deb

# Fix any dependency issues
sudo apt-get install -f

# Verify
aura --version
```

Or using apt repository (coming soon):

```bash
# Add repository
echo "deb https://packages.aenealabs.com/apt stable main" | sudo tee /etc/apt/sources.list.d/aenealabs.list
curl -fsSL https://packages.aenealabs.com/keys/aenealabs.gpg | sudo apt-key add -

# Install
sudo apt-get update
sudo apt-get install aura-cli
```

### RHEL/CentOS/Fedora (RPM)

```bash
# Download
curl -LO https://github.com/aenealabs/aura/releases/download/v1.0.0/aura-cli-1.0.0-1.x86_64.rpm

# Install (RHEL/CentOS)
sudo rpm -i aura-cli-1.0.0-1.x86_64.rpm

# Or using dnf (Fedora)
sudo dnf install aura-cli-1.0.0-1.x86_64.rpm

# Verify
aura --version
```

Or using yum repository (coming soon):

```bash
# Add repository
cat <<EOF | sudo tee /etc/yum.repos.d/aenealabs.repo
[aenealabs]
name=Aenea Labs Repository
baseurl=https://packages.aenealabs.com/rpm
enabled=1
gpgcheck=1
gpgkey=https://packages.aenealabs.com/keys/aenealabs.gpg
EOF

# Install
sudo yum install aura-cli
```

### Manual Installation (Tarball)

For systems without package managers or custom installations:

```bash
# Download tarball
curl -LO https://github.com/aenealabs/aura/releases/download/v1.0.0/aura-cli-1.0.0-linux-x64.tar.gz

# Verify checksum
sha256sum -c SHA256SUMS.txt

# Extract
tar xzf aura-cli-1.0.0-linux-x64.tar.gz

# Install to /usr/local/bin
sudo mv aura-cli-1.0.0/aura /usr/local/bin/

# Install completions (optional)
sudo mv aura-cli-1.0.0/completions/aura.bash /etc/bash_completion.d/
sudo mv aura-cli-1.0.0/completions/aura.zsh /usr/share/zsh/vendor-completions/_aura

# Verify
aura --version
```

## Verification

Always verify downloads using SHA256 checksums:

```bash
# Download checksums
curl -LO https://github.com/aenealabs/aura/releases/download/v1.0.0/SHA256SUMS.txt

# Verify
sha256sum -c SHA256SUMS.txt --ignore-missing
```

For signed releases, verify the signature:

```bash
# Download signature
curl -LO https://github.com/aenealabs/aura/releases/download/v1.0.0/SHA256SUMS.txt.sig

# Verify (requires Aenea Labs public key)
gpg --verify SHA256SUMS.txt.sig SHA256SUMS.txt
```

## Uninstallation

### Homebrew

```bash
brew uninstall aura-cli
```

### Windows

Use "Add or Remove Programs" or:

```powershell
msiexec /x aura-cli.msi /quiet
```

### macOS

```bash
sudo rm /usr/local/bin/aura
sudo pkgutil --forget com.aenealabs.aura-cli
```

### Debian/Ubuntu

```bash
sudo apt-get remove aura-cli
# Or to remove config files too:
sudo apt-get purge aura-cli
```

### RHEL/CentOS/Fedora

```bash
sudo rpm -e aura-cli
# Or:
sudo dnf remove aura-cli
```

## Configuration

After installation, initialize the CLI:

```bash
# Interactive configuration
aura config init --interactive

# Or set values directly
aura config set api_url http://aura.example.com:8080
```

Configuration is stored in `~/.aura/config.yaml`.

## Shell Completions

Shell completions are installed automatically with packages. To manually enable:

### Bash

```bash
# Add to ~/.bashrc
source /usr/share/bash-completion/completions/aura
```

### Zsh

```bash
# Add to ~/.zshrc
fpath=(/usr/share/zsh/vendor-completions $fpath)
autoload -Uz compinit && compinit
```

### Fish

```bash
# Add to ~/.config/fish/config.fish
aura completions fish | source
```

## Troubleshooting

### Command not found

Ensure the installation directory is in your PATH:

```bash
# Linux/macOS
export PATH="/usr/local/bin:$PATH"

# Windows (PowerShell)
$env:Path += ";C:\Program Files\Aura\bin"
```

### Permission denied

Run with elevated privileges:

```bash
# Linux/macOS
sudo aura <command>

# Windows (run PowerShell as Administrator)
aura <command>
```

### SSL/TLS errors

For self-signed certificates:

```bash
aura config set ssl_verify false  # Not recommended for production
```

Or add your CA certificate:

```bash
aura config set ca_bundle /path/to/ca-bundle.crt
```

## Building from Source

For custom builds or development:

```bash
# Clone repository
git clone https://github.com/aenealabs/aura.git
cd project-aura

# Install build dependencies
pip install pyinstaller

# Build for current platform
./deploy/installer/native/build-all.sh --version 1.0.0

# Output in deploy/installer/native/dist/
```

### Build Requirements

| Platform | Requirements |
|----------|-------------|
| All | Python 3.11+, PyInstaller |
| Windows | WiX Toolset v4+, .NET SDK 6+ |
| macOS | Xcode Command Line Tools |
| Debian | dpkg-dev, debhelper |
| RPM | rpm-build, rpmlint |

## Support

- Documentation: https://docs.aenealabs.com/cli
- Issues: https://github.com/aenealabs/aura/issues
- Email: support@aenealabs.com
