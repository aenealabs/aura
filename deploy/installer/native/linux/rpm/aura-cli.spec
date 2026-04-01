%global debug_package %{nil}
%global __strip /bin/true

Name:           aura-cli
Version:        1.0.0
Release:        1%{?dist}
Summary:        Project Aura Command Line Interface

License:        Proprietary
URL:            https://aenealabs.com
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  python3 >= 3.11
BuildRequires:  python3-pip
BuildRequires:  python3-devel

Requires:       glibc

Recommends:     kubectl
Recommends:     helm

Suggests:       podman
Suggests:       docker

%description
Aura CLI is a command-line tool for managing Project Aura deployments.

Features:
  - Deployment status and health monitoring
  - License management (online and offline)
  - Configuration management
  - Service log viewing
  - Upgrade management

Project Aura is an autonomous code intelligence platform that enables
machines to reason across entire enterprise codebases using a hybrid
graph-based architecture.

%prep
%setup -q

%build
# Install PyInstaller
pip3 install --user pyinstaller

# Build standalone executable
~/.local/bin/pyinstaller \
    --onefile \
    --name aura \
    --strip \
    --clean \
    src/cli/main.py

%install
rm -rf %{buildroot}

# Install binary
install -D -m 755 dist/aura %{buildroot}%{_bindir}/aura

# Install bash completion
install -D -m 644 completions/aura.bash \
    %{buildroot}%{_datadir}/bash-completion/completions/aura

# Install zsh completion
install -D -m 644 completions/aura.zsh \
    %{buildroot}%{_datadir}/zsh/site-functions/_aura

# Install man page
install -D -m 644 docs/aura.1 %{buildroot}%{_mandir}/man1/aura.1
gzip %{buildroot}%{_mandir}/man1/aura.1

# Install documentation
install -D -m 644 LICENSE %{buildroot}%{_docdir}/%{name}/LICENSE
install -D -m 644 README.md %{buildroot}%{_docdir}/%{name}/README.md

%post
# Verify installation
if /usr/bin/aura --version > /dev/null 2>&1; then
    echo "Aura CLI installed successfully!"
    /usr/bin/aura --version
fi

%files
%license LICENSE
%doc README.md
%{_bindir}/aura
%{_datadir}/bash-completion/completions/aura
%{_datadir}/zsh/site-functions/_aura
%{_mandir}/man1/aura.1.gz
%{_docdir}/%{name}/

%changelog
* Fri Jan 03 2026 Aenea Labs <support@aenealabs.com> - 1.0.0-1
- Initial release
- Core CLI commands: status, config, license, deploy, health, logs
- Offline license validation with hardware fingerprinting
- Cross-platform support (Linux, macOS, Windows)
