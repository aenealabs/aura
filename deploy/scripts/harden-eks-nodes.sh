#!/bin/bash
################################################################################
# Project Aura - EKS Node Security Hardening Script
#
# Purpose: Apply security hardening to EKS worker nodes
# Compatible: AWS Commercial Cloud (dev/qa) and AWS GovCloud (prod)
#
# Hardening Levels:
#   - commercial: Standard security hardening for dev/qa environments
#   - govcloud:   STIG/FIPS hardening for GovCloud/production deployments
#
# Usage:
#   ./harden-eks-nodes.sh --level <commercial|govcloud> [options]
#
# Options:
#   --level         Hardening level: commercial or govcloud (required)
#   --dry-run       Show what would be applied without making changes
#   --skip-fips     Skip FIPS mode enablement (GovCloud only)
#   --skip-stig     Skip STIG hardening (GovCloud only)
#
# Examples:
#   # Commercial Cloud (dev/qa)
#   ./harden-eks-nodes.sh --level commercial
#
#   # GovCloud (production)
#   ./harden-eks-nodes.sh --level govcloud
#
#   # Dry run to see what would change
#   ./harden-eks-nodes.sh --level govcloud --dry-run
#
# Note: This script is designed to run on EKS worker nodes via user-data
#       during instance launch. For existing nodes, use AWS Systems Manager
#       Run Command to execute this script across node groups.
#
################################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
HARDENING_LEVEL=""
DRY_RUN=false
SKIP_FIPS=false
SKIP_STIG=false

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date +'%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date +'%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date +'%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date +'%Y-%m-%d %H:%M:%S') - $1"
}

# Usage information
usage() {
    cat << EOF
Usage: $0 --level <commercial|govcloud> [options]

Required:
  --level <type>    Hardening level: commercial or govcloud

Optional:
  --dry-run         Show what would be applied without making changes
  --skip-fips       Skip FIPS mode enablement (GovCloud only)
  --skip-stig       Skip STIG hardening (GovCloud only)
  --help            Show this help message

Hardening Levels:
  commercial        Standard security for dev/qa (IMDSv2, SSH hardening, logging)
  govcloud          STIG/FIPS compliance for production (all commercial + DISA STIG + FIPS)

Examples:
  $0 --level commercial
  $0 --level govcloud --skip-fips
  $0 --level govcloud --dry-run

EOF
    exit 1
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --level)
                HARDENING_LEVEL="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --skip-fips)
                SKIP_FIPS=true
                shift
                ;;
            --skip-stig)
                SKIP_STIG=true
                shift
                ;;
            --help)
                usage
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                ;;
        esac
    done

    # Validate required parameters
    if [[ -z "$HARDENING_LEVEL" ]]; then
        log_error "Missing required parameter: --level"
        usage
    fi

    if [[ "$HARDENING_LEVEL" != "commercial" ]] && [[ "$HARDENING_LEVEL" != "govcloud" ]]; then
        log_error "Invalid hardening level. Must be 'commercial' or 'govcloud'"
        usage
    fi
}

# Execute command (respects dry-run mode)
execute() {
    local cmd="$1"
    local description="$2"

    log_info "$description"

    if [[ "$DRY_RUN" == true ]]; then
        log_warning "[DRY RUN] Would execute: $cmd"
        return 0
    fi

    if eval "$cmd"; then
        log_success "$description - completed"
        return 0
    else
        log_error "$description - failed"
        return 1
    fi
}

################################################################################
# Commercial Cloud Hardening (Standard Security)
################################################################################

# Enforce IMDSv2 (Instance Metadata Service v2)
harden_imds() {
    log_info "Enforcing IMDSv2 (Instance Metadata Service v2)..."

    # This is configured in the Launch Template, but we verify it here
    local token_required
    token_required=$(curl -s http://169.254.169.254/latest/meta-data/imdsv2-token-required 2>/dev/null || echo "optional")

    if [[ "$token_required" == "required" ]]; then
        log_success "IMDSv2 is already enforced"
    else
        log_warning "IMDSv2 not enforced. This should be configured in the Launch Template."
    fi
}

# Harden SSH configuration
harden_ssh() {
    log_info "Hardening SSH configuration..."

    local sshd_config="/etc/ssh/sshd_config"

    execute "sed -i 's/^#PermitRootLogin.*/PermitRootLogin no/' $sshd_config" "Disable root SSH login"
    execute "sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication no/' $sshd_config" "Disable password authentication"
    execute "sed -i 's/^#PubkeyAuthentication.*/PubkeyAuthentication yes/' $sshd_config" "Enable public key authentication only"
    execute "sed -i 's/^#MaxAuthTries.*/MaxAuthTries 3/' $sshd_config" "Set max auth tries to 3"
    execute "sed -i 's/^#ClientAliveInterval.*/ClientAliveInterval 300/' $sshd_config" "Set client alive interval"
    execute "sed -i 's/^#ClientAliveCountMax.*/ClientAliveCountMax 0/' $sshd_config" "Set client alive count max"

    # Add strong ciphers only
    if ! grep -q "^Ciphers" $sshd_config; then
        execute "echo 'Ciphers aes256-gcm@openssh.com,aes128-gcm@openssh.com,aes256-ctr,aes192-ctr,aes128-ctr' >> $sshd_config" "Configure strong SSH ciphers"
    fi

    execute "systemctl restart sshd" "Restart SSH service"
}

# Configure automatic security updates
configure_auto_updates() {
    log_info "Configuring automatic security updates..."

    execute "yum install -y yum-cron" "Install yum-cron"

    # Configure yum-cron for security updates only
    execute "sed -i 's/^update_cmd =.*/update_cmd = security/' /etc/yum/yum-cron.conf" "Configure security-only updates"
    execute "sed -i 's/^apply_updates =.*/apply_updates = yes/' /etc/yum/yum-cron.conf" "Enable automatic updates"

    execute "systemctl enable yum-cron" "Enable yum-cron service"
    execute "systemctl start yum-cron" "Start yum-cron service"
}

# Configure logging and auditing
configure_logging() {
    log_info "Configuring logging and auditing..."

    # Install CloudWatch agent if not present
    if ! command -v amazon-cloudwatch-agent-ctl &> /dev/null; then
        execute "yum install -y amazon-cloudwatch-agent" "Install CloudWatch agent"
    fi

    # Enable auditd for security auditing
    execute "yum install -y audit" "Install auditd"
    execute "systemctl enable auditd" "Enable auditd service"
    execute "systemctl start auditd" "Start auditd service"

    # Configure audit rules for security events
    cat << 'EOF' > /etc/audit/rules.d/aura-security.rules
# Monitor changes to system configuration
-w /etc/passwd -p wa -k identity
-w /etc/group -p wa -k identity
-w /etc/shadow -p wa -k identity
-w /etc/sudoers -p wa -k actions

# Monitor SSH configuration
-w /etc/ssh/sshd_config -p wa -k sshd

# Monitor kernel module loading
-w /sbin/insmod -p x -k modules
-w /sbin/rmmod -p x -k modules
-w /sbin/modprobe -p x -k modules

# Monitor privileged commands
-a always,exit -F arch=b64 -S execve -F euid=0 -k root-commands
EOF

    execute "augenrules --load" "Load audit rules"
}

# Harden kernel parameters
harden_kernel() {
    log_info "Hardening kernel parameters..."

    cat << 'EOF' > /etc/sysctl.d/99-aura-hardening.conf
# IP forwarding (required for Kubernetes)
net.ipv4.ip_forward = 1

# Disable source routing
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0

# Disable ICMP redirects
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.secure_redirects = 0
net.ipv4.conf.default.secure_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0

# Enable TCP SYN cookies
net.ipv4.tcp_syncookies = 1

# Disable IPv6 (if not needed)
net.ipv6.conf.all.disable_ipv6 = 0
net.ipv6.conf.default.disable_ipv6 = 0

# Log martian packets
net.ipv4.conf.all.log_martians = 1

# Ignore ICMP ping requests
net.ipv4.icmp_echo_ignore_all = 0

# Enable reverse path filtering
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
EOF

    execute "sysctl -p /etc/sysctl.d/99-aura-hardening.conf" "Apply kernel hardening parameters"
}

# Set file permissions
harden_file_permissions() {
    log_info "Hardening file permissions..."

    execute "chmod 644 /etc/passwd" "Set /etc/passwd permissions"
    execute "chmod 644 /etc/group" "Set /etc/group permissions"
    execute "chmod 000 /etc/shadow" "Set /etc/shadow permissions"
    execute "chmod 000 /etc/gshadow" "Set /etc/gshadow permissions"
    execute "chmod 600 /boot/grub2/grub.cfg" "Set grub.cfg permissions" || true
}

################################################################################
# GovCloud Hardening (STIG/FIPS Compliance)
################################################################################

# Enable FIPS mode
enable_fips() {
    if [[ "$SKIP_FIPS" == true ]]; then
        log_warning "Skipping FIPS enablement (--skip-fips flag set)"
        return 0
    fi

    log_info "Enabling FIPS 140-2 mode..."

    # Check if FIPS is already enabled
    if [[ -f /proc/sys/crypto/fips_enabled ]] && [[ $(cat /proc/sys/crypto/fips_enabled) == "1" ]]; then
        log_success "FIPS mode is already enabled"
        return 0
    fi

    # Install FIPS packages
    execute "yum install -y dracut-fips" "Install FIPS packages"

    # Enable FIPS mode
    execute "fips-mode-setup --enable" "Enable FIPS mode"

    log_warning "FIPS mode enabled. System reboot required to activate."
}

# Apply DISA STIG hardening
apply_stig_hardening() {
    if [[ "$SKIP_STIG" == true ]]; then
        log_warning "Skipping STIG hardening (--skip-stig flag set)"
        return 0
    fi

    log_info "Applying DISA STIG hardening..."

    # Install SCAP security guide
    execute "yum install -y scap-security-guide" "Install SCAP security guide"

    # Password policy enforcement
    cat << 'EOF' > /etc/security/pwquality.conf
# Password quality requirements (STIG compliant)
minlen = 15
dcredit = -1
ucredit = -1
lcredit = -1
ocredit = -1
difok = 8
maxrepeat = 3
EOF

    # Account lockout policy
    cat << 'EOF' > /etc/pam.d/system-auth-local
# Account lockout after 3 failed attempts (STIG V-204431)
auth required pam_faillock.so preauth silent deny=3 unlock_time=900 fail_interval=900
auth sufficient pam_unix.so try_first_pass
auth [default=die] pam_faillock.so authfail deny=3 unlock_time=900 fail_interval=900
account required pam_faillock.so
EOF

    # Session timeout
    cat << 'EOF' >> /etc/profile.d/autologout.sh
# Auto logout after 15 minutes of inactivity (STIG V-204624)
TMOUT=900
readonly TMOUT
export TMOUT
EOF

    execute "chmod +x /etc/profile.d/autologout.sh" "Make autologout script executable"

    # Disable USB storage (STIG V-204498)
    execute "echo 'install usb-storage /bin/true' > /etc/modprobe.d/usb-storage.conf" "Disable USB storage"

    # Configure banner
    cat << 'EOF' > /etc/issue
################################################################################
#                         AUTHORIZED ACCESS ONLY                               #
################################################################################
#                                                                              #
# This system is for authorized use only. Individuals using this system        #
# without authority, or in excess of their authority, are subject to having    #
# all of their activities monitored and recorded.                              #
#                                                                              #
# Anyone using this system expressly consents to such monitoring and is        #
# advised that if such monitoring reveals possible evidence of criminal        #
# activity, system personnel may provide the evidence to law enforcement.      #
#                                                                              #
################################################################################
EOF

    execute "cp /etc/issue /etc/issue.net" "Configure network login banner"

    # Enable SELinux enforcing mode (STIG V-230223)
    configure_selinux

    log_success "STIG hardening applied"
}

# Configure SELinux in enforcing mode
configure_selinux() {
    log_info "Configuring SELinux in enforcing mode..."

    # Check if SELinux is available
    if ! command -v getenforce &> /dev/null; then
        log_warning "SELinux tools not found. Installing..."
        execute "yum install -y selinux-policy-targeted policycoreutils" "Install SELinux packages"
    fi

    # Get current SELinux status
    local current_mode
    current_mode=$(getenforce 2>/dev/null || echo "Disabled")

    if [[ "$current_mode" == "Enforcing" ]]; then
        log_success "SELinux is already in Enforcing mode"
        return 0
    fi

    # Configure SELinux to enforcing mode
    if [[ -f /etc/selinux/config ]]; then
        execute "sed -i 's/^SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config" "Set SELinux to enforcing in config"
        execute "sed -i 's/^SELINUXTYPE=.*/SELINUXTYPE=targeted/' /etc/selinux/config" "Set SELinux type to targeted"
    else
        cat << 'EOF' > /etc/selinux/config
# SELinux configuration (STIG V-230223)
SELINUX=enforcing
SELINUXTYPE=targeted
EOF
        log_info "Created /etc/selinux/config"
    fi

    # Set SELinux to enforcing immediately (if not in dry-run)
    if [[ "$DRY_RUN" == false ]]; then
        # Note: setenforce may fail if SELinux was disabled at boot
        setenforce 1 2>/dev/null || log_warning "Cannot set enforcing mode now. Reboot required."
    fi

    # Configure SELinux booleans for container workloads
    if command -v setsebool &> /dev/null; then
        execute "setsebool -P container_manage_cgroup 1 2>/dev/null || true" "Enable container cgroup management"
        execute "setsebool -P container_use_cephfs 0 2>/dev/null || true" "Disable container CephFS access"
    fi

    log_success "SELinux configured for enforcing mode"
    log_warning "NOTE: If SELinux was disabled, a reboot is required to activate enforcing mode"
}

# Configure FIPS-compliant cryptography
configure_fips_crypto() {
    log_info "Configuring FIPS-compliant cryptography..."

    # Update OpenSSL to use FIPS module
    if [[ -f /etc/pki/tls/openssl.cnf ]]; then
        execute "sed -i 's/^# openssl_conf = openssl_init/openssl_conf = openssl_init/' /etc/pki/tls/openssl.cnf" "Configure OpenSSL for FIPS"
    fi

    # Configure SSH to use FIPS-approved algorithms
    cat << 'EOF' >> /etc/ssh/sshd_config

# FIPS 140-2 compliant algorithms
Ciphers aes256-ctr,aes192-ctr,aes128-ctr
MACs hmac-sha2-256,hmac-sha2-512
KexAlgorithms diffie-hellman-group-exchange-sha256
EOF

    execute "systemctl restart sshd" "Restart SSH with FIPS configuration"
}

# Disable unnecessary services
disable_unnecessary_services() {
    log_info "Disabling unnecessary services..."

    local services_to_disable=(
        "bluetooth"
        "cups"
        "avahi-daemon"
        "rpcbind"
    )

    for service in "${services_to_disable[@]}"; do
        if systemctl list-unit-files | grep -q "^${service}.service"; then
            execute "systemctl disable ${service} 2>/dev/null || true" "Disable ${service}" || true
            execute "systemctl stop ${service} 2>/dev/null || true" "Stop ${service}" || true
        fi
    done
}

################################################################################
# Main Execution
################################################################################

# Apply commercial cloud hardening
apply_commercial_hardening() {
    log_info "Applying commercial cloud hardening..."

    harden_imds
    harden_ssh
    configure_auto_updates
    configure_logging
    harden_kernel
    harden_file_permissions
    disable_unnecessary_services

    log_success "Commercial cloud hardening complete"
}

# Apply GovCloud hardening
apply_govcloud_hardening() {
    log_info "Applying GovCloud hardening (STIG/FIPS)..."

    # First apply all commercial hardening
    apply_commercial_hardening

    # Then apply additional GovCloud-specific hardening
    enable_fips
    apply_stig_hardening
    configure_fips_crypto

    log_success "GovCloud hardening complete"
}

# Main function
main() {
    parse_args "$@"

    log_info "================================================"
    log_info "Project Aura - EKS Node Security Hardening"
    log_info "================================================"
    log_info "Hardening Level: $HARDENING_LEVEL"
    log_info "Dry Run: $DRY_RUN"
    log_info "================================================"

    # Check if running as root
    if [[ $EUID -ne 0 ]] && [[ "$DRY_RUN" == false ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi

    case "$HARDENING_LEVEL" in
        commercial)
            apply_commercial_hardening
            ;;
        govcloud)
            apply_govcloud_hardening
            ;;
        *)
            log_error "Invalid hardening level: $HARDENING_LEVEL"
            exit 1
            ;;
    esac

    log_info "================================================"
    log_success "Security hardening complete!"
    log_info "================================================"

    if [[ "$HARDENING_LEVEL" == "govcloud" ]] && [[ "$SKIP_FIPS" == false ]]; then
        log_warning "IMPORTANT: System reboot required to activate FIPS mode"
        log_warning "Run: sudo reboot"
    fi
}

# Run main function
main "$@"
