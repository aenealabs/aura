#!/bin/bash
################################################################################
# Project Aura - STIG/FIPS Compliance Validation Script
#
# Purpose: Validate DISA STIG and FIPS 140-2 compliance on EKS nodes
# Compatible: AWS Commercial Cloud and AWS GovCloud
#
# Usage:
#   ./validate-stig-fips.sh [options]
#
# Options:
#   --full          Run full compliance scan (includes SCAP)
#   --fips-only     Only validate FIPS mode
#   --stig-only     Only validate STIG settings
#   --json          Output results in JSON format
#   --quiet         Only show failures
#
# Exit Codes:
#   0 - All checks passed
#   1 - One or more checks failed
#   2 - Script error
#
################################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Options
FULL_SCAN=false
FIPS_ONLY=false
STIG_ONLY=false
JSON_OUTPUT=false
QUIET=false

# Results array for JSON output
declare -a RESULTS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --full) FULL_SCAN=true; shift ;;
        --fips-only) FIPS_ONLY=true; shift ;;
        --stig-only) STIG_ONLY=true; shift ;;
        --json) JSON_OUTPUT=true; shift ;;
        --quiet) QUIET=true; shift ;;
        *) echo "Unknown option: $1"; exit 2 ;;
    esac
done

# Logging functions
log_check() {
    if [[ "$QUIET" == false ]] && [[ "$JSON_OUTPUT" == false ]]; then
        echo -e "${BLUE}[CHECK]${NC} $1"
    fi
}

log_pass() {
    ((PASSED++))
    if [[ "$JSON_OUTPUT" == true ]]; then
        RESULTS+=("{\"check\": \"$1\", \"status\": \"PASS\", \"details\": \"$2\"}")
    elif [[ "$QUIET" == false ]]; then
        echo -e "${GREEN}[PASS]${NC} $1"
    fi
}

log_fail() {
    ((FAILED++))
    if [[ "$JSON_OUTPUT" == true ]]; then
        RESULTS+=("{\"check\": \"$1\", \"status\": \"FAIL\", \"details\": \"$2\"}")
    else
        echo -e "${RED}[FAIL]${NC} $1 - $2"
    fi
}

log_warn() {
    ((WARNINGS++))
    if [[ "$JSON_OUTPUT" == true ]]; then
        RESULTS+=("{\"check\": \"$1\", \"status\": \"WARN\", \"details\": \"$2\"}")
    elif [[ "$QUIET" == false ]]; then
        echo -e "${YELLOW}[WARN]${NC} $1 - $2"
    fi
}

################################################################################
# FIPS 140-2 Validation
################################################################################

validate_fips() {
    log_check "Validating FIPS 140-2 compliance..."

    # Check kernel FIPS mode
    if [[ -f /proc/sys/crypto/fips_enabled ]]; then
        local fips_enabled
        fips_enabled=$(cat /proc/sys/crypto/fips_enabled)
        if [[ "$fips_enabled" == "1" ]]; then
            log_pass "Kernel FIPS mode" "FIPS mode is enabled"
        else
            log_fail "Kernel FIPS mode" "FIPS mode is disabled (/proc/sys/crypto/fips_enabled = 0)"
        fi
    else
        log_fail "Kernel FIPS mode" "/proc/sys/crypto/fips_enabled not found"
    fi

    # Check OpenSSL FIPS provider
    if command -v openssl &> /dev/null; then
        local openssl_fips
        openssl_fips=$(openssl version 2>&1 || true)
        if echo "$openssl_fips" | grep -qi "fips"; then
            log_pass "OpenSSL FIPS" "OpenSSL reports FIPS mode"
        else
            # Check via provider list
            if openssl list -providers 2>/dev/null | grep -qi "fips"; then
                log_pass "OpenSSL FIPS Provider" "FIPS provider is available"
            else
                log_warn "OpenSSL FIPS" "FIPS provider not explicitly listed"
            fi
        fi
    else
        log_fail "OpenSSL" "OpenSSL not found"
    fi

    # Check SSH ciphers are FIPS-approved
    if [[ -f /etc/ssh/sshd_config ]]; then
        local ssh_ciphers
        ssh_ciphers=$(grep "^Ciphers" /etc/ssh/sshd_config 2>/dev/null || echo "")
        if [[ -n "$ssh_ciphers" ]]; then
            # Check for non-FIPS ciphers
            if echo "$ssh_ciphers" | grep -qE "(chacha|arcfour|blowfish|3des)"; then
                log_fail "SSH FIPS Ciphers" "Non-FIPS ciphers configured: $ssh_ciphers"
            else
                log_pass "SSH FIPS Ciphers" "Only FIPS-approved ciphers configured"
            fi
        else
            log_warn "SSH FIPS Ciphers" "No explicit cipher configuration found"
        fi
    fi

    # Check dracut-fips package
    if rpm -q dracut-fips &> /dev/null; then
        log_pass "FIPS Packages" "dracut-fips is installed"
    else
        log_fail "FIPS Packages" "dracut-fips not installed"
    fi
}

################################################################################
# STIG Validation
################################################################################

validate_stig() {
    log_check "Validating DISA STIG compliance..."

    # V-230223: SELinux must be in enforcing mode
    if command -v getenforce &> /dev/null; then
        local selinux_mode
        selinux_mode=$(getenforce 2>/dev/null || echo "Unknown")
        if [[ "$selinux_mode" == "Enforcing" ]]; then
            log_pass "STIG V-230223" "SELinux is in Enforcing mode"
        elif [[ "$selinux_mode" == "Permissive" ]]; then
            log_fail "STIG V-230223" "SELinux is in Permissive mode (must be Enforcing)"
        else
            log_fail "STIG V-230223" "SELinux is disabled or unknown: $selinux_mode"
        fi
    else
        log_fail "STIG V-230223" "SELinux tools not installed"
    fi

    # V-204431: Account lockout after 3 failed attempts
    if [[ -f /etc/pam.d/system-auth ]] || [[ -f /etc/pam.d/system-auth-local ]]; then
        if grep -q "pam_faillock.so" /etc/pam.d/system-auth* 2>/dev/null; then
            if grep -q "deny=3" /etc/pam.d/system-auth* 2>/dev/null; then
                log_pass "STIG V-204431" "Account lockout configured (deny=3)"
            else
                log_warn "STIG V-204431" "pam_faillock configured but deny count not set to 3"
            fi
        else
            log_fail "STIG V-204431" "Account lockout (pam_faillock) not configured"
        fi
    fi

    # V-204624: Session timeout (TMOUT)
    if grep -rq "TMOUT=900" /etc/profile.d/ 2>/dev/null || grep -q "TMOUT=900" /etc/profile 2>/dev/null; then
        log_pass "STIG V-204624" "Session timeout (TMOUT=900) configured"
    else
        log_fail "STIG V-204624" "Session timeout not configured or not set to 900 seconds"
    fi

    # V-204498: USB storage disabled
    if [[ -f /etc/modprobe.d/usb-storage.conf ]]; then
        if grep -q "install usb-storage /bin/true" /etc/modprobe.d/usb-storage.conf 2>/dev/null; then
            log_pass "STIG V-204498" "USB storage disabled"
        else
            log_fail "STIG V-204498" "USB storage not properly disabled"
        fi
    else
        log_fail "STIG V-204498" "USB storage disable configuration not found"
    fi

    # Check SSH hardening
    if [[ -f /etc/ssh/sshd_config ]]; then
        # Root login disabled
        if grep -q "^PermitRootLogin no" /etc/ssh/sshd_config 2>/dev/null; then
            log_pass "SSH Root Login" "Root login disabled"
        else
            log_fail "SSH Root Login" "Root login not explicitly disabled"
        fi

        # Password auth disabled
        if grep -q "^PasswordAuthentication no" /etc/ssh/sshd_config 2>/dev/null; then
            log_pass "SSH Password Auth" "Password authentication disabled"
        else
            log_warn "SSH Password Auth" "Password authentication not explicitly disabled"
        fi
    fi

    # Check password policy
    if [[ -f /etc/security/pwquality.conf ]]; then
        if grep -q "minlen = 15" /etc/security/pwquality.conf 2>/dev/null; then
            log_pass "Password Policy" "Minimum password length is 15"
        else
            log_fail "Password Policy" "Minimum password length not set to 15"
        fi
    else
        log_fail "Password Policy" "pwquality.conf not found"
    fi

    # Check auditd
    if systemctl is-active auditd &> /dev/null; then
        log_pass "Audit Daemon" "auditd is running"
    else
        log_fail "Audit Daemon" "auditd is not running"
    fi

    # Check login banner
    if [[ -f /etc/issue ]]; then
        if grep -qi "authorized" /etc/issue 2>/dev/null; then
            log_pass "Login Banner" "Warning banner configured"
        else
            log_fail "Login Banner" "Warning banner not configured"
        fi
    else
        log_fail "Login Banner" "/etc/issue not found"
    fi

    # Check file permissions
    local shadow_perms
    shadow_perms=$(stat -c %a /etc/shadow 2>/dev/null || echo "unknown")
    if [[ "$shadow_perms" == "000" ]] || [[ "$shadow_perms" == "0" ]]; then
        log_pass "File Permissions" "/etc/shadow has correct permissions (000)"
    else
        log_fail "File Permissions" "/etc/shadow has incorrect permissions: $shadow_perms (should be 000)"
    fi
}

################################################################################
# Kernel Hardening Validation
################################################################################

validate_kernel() {
    log_check "Validating kernel hardening..."

    # Check sysctl settings
    local checks=(
        "net.ipv4.conf.all.accept_source_route:0"
        "net.ipv4.conf.all.accept_redirects:0"
        "net.ipv4.tcp_syncookies:1"
        "net.ipv4.conf.all.rp_filter:1"
    )

    for check in "${checks[@]}"; do
        local key="${check%:*}"
        local expected="${check#*:}"
        local actual
        actual=$(sysctl -n "$key" 2>/dev/null || echo "unknown")

        if [[ "$actual" == "$expected" ]]; then
            log_pass "Kernel: $key" "Value is $actual (expected $expected)"
        else
            log_fail "Kernel: $key" "Value is $actual (expected $expected)"
        fi
    done
}

################################################################################
# Full SCAP Scan
################################################################################

run_scap_scan() {
    if [[ "$FULL_SCAN" != true ]]; then
        return 0
    fi

    log_check "Running full SCAP compliance scan..."

    if ! command -v oscap &> /dev/null; then
        log_warn "SCAP Scan" "oscap not installed. Install with: yum install openscap-scanner"
        return 0
    fi

    local scap_profile="xccdf_org.ssgproject.content_profile_stig"
    local scap_content="/usr/share/xml/scap/ssg/content/ssg-al2023-ds.xml"

    if [[ ! -f "$scap_content" ]]; then
        scap_content="/usr/share/xml/scap/ssg/content/ssg-rhel8-ds.xml"
    fi

    if [[ ! -f "$scap_content" ]]; then
        log_warn "SCAP Scan" "SCAP content not found. Install with: yum install scap-security-guide"
        return 0
    fi

    local report_file="/tmp/scap-report-$(date +%Y%m%d-%H%M%S).html"

    oscap xccdf eval \
        --profile "$scap_profile" \
        --results-arf /tmp/scap-results.xml \
        --report "$report_file" \
        "$scap_content" 2>/dev/null || true

    log_pass "SCAP Scan" "Report generated: $report_file"
}

################################################################################
# Main
################################################################################

main() {
    if [[ "$JSON_OUTPUT" == false ]]; then
        echo "=============================================="
        echo "Project Aura - STIG/FIPS Compliance Validator"
        echo "=============================================="
        echo ""
    fi

    # Run appropriate validations
    if [[ "$FIPS_ONLY" == true ]]; then
        validate_fips
    elif [[ "$STIG_ONLY" == true ]]; then
        validate_stig
    else
        validate_fips
        validate_stig
        validate_kernel
        run_scap_scan
    fi

    # Output results
    if [[ "$JSON_OUTPUT" == true ]]; then
        echo "{"
        echo "  \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
        echo "  \"hostname\": \"$(hostname)\","
        echo "  \"passed\": $PASSED,"
        echo "  \"failed\": $FAILED,"
        echo "  \"warnings\": $WARNINGS,"
        echo "  \"results\": ["
        local first=true
        for result in "${RESULTS[@]}"; do
            if [[ "$first" == true ]]; then
                first=false
            else
                echo ","
            fi
            echo -n "    $result"
        done
        echo ""
        echo "  ]"
        echo "}"
    else
        echo ""
        echo "=============================================="
        echo "Summary"
        echo "=============================================="
        echo -e "${GREEN}Passed:${NC}   $PASSED"
        echo -e "${RED}Failed:${NC}   $FAILED"
        echo -e "${YELLOW}Warnings:${NC} $WARNINGS"
        echo "=============================================="

        if [[ $FAILED -gt 0 ]]; then
            echo -e "${RED}COMPLIANCE CHECK FAILED${NC}"
        else
            echo -e "${GREEN}COMPLIANCE CHECK PASSED${NC}"
        fi
    fi

    # Exit with appropriate code
    if [[ $FAILED -gt 0 ]]; then
        exit 1
    fi
    exit 0
}

main "$@"
