# STIG and FIPS 140-2 Compliance Guide

## Overview

This document describes the DISA STIG (Security Technical Implementation Guide) hardening and FIPS 140-2 cryptographic compliance implementation for Project Aura's GovCloud deployment.

## Compliance Requirements

### FIPS 140-2

FIPS 140-2 is a U.S. government standard that defines minimum security requirements for cryptographic modules. For GovCloud deployments, all cryptographic operations must use FIPS-approved algorithms.

**Key Requirements:**
- Kernel FIPS mode enabled (`fips=1`)
- OpenSSL FIPS provider active
- SSH using only FIPS-approved ciphers
- All data encryption using AES-256

### DISA STIG

Defense Information Systems Agency (DISA) Security Technical Implementation Guides provide security configuration standards for Department of Defense systems.

**Applicable STIGs:**
- Red Hat Enterprise Linux 8/9 STIG (for AL2023)
- Container Platform STIG (Kubernetes)
- AWS Foundational STIG

## Implementation

### 1. EKS Node Hardening

STIG/FIPS hardening is applied automatically to EKS worker nodes when `EnableSTIGHardening=true` is set in the CloudFormation deployment.

**Enable in CloudFormation:**
```yaml
Parameters:
  EnableSTIGHardening: 'true'  # Set to 'true' for GovCloud
```

**Manual hardening via script:**
```bash
# On EKS worker node
sudo ./deploy/scripts/harden-eks-nodes.sh --level govcloud

# Dry run to preview changes
sudo ./deploy/scripts/harden-eks-nodes.sh --level govcloud --dry-run
```

### 2. Validation

Use the validation script to verify compliance:

```bash
# Full compliance check
./deploy/scripts/validate-stig-fips.sh

# FIPS-only check
./deploy/scripts/validate-stig-fips.sh --fips-only

# STIG-only check
./deploy/scripts/validate-stig-fips.sh --stig-only

# JSON output for automation
./deploy/scripts/validate-stig-fips.sh --json
```

### 3. SCAP Scanning

For comprehensive compliance reporting:

```bash
# Install SCAP tools
yum install -y openscap-scanner scap-security-guide

# Run STIG scan
oscap xccdf eval \
  --profile xccdf_org.ssgproject.content_profile_stig \
  --results-arf /tmp/scap-results.xml \
  --report /tmp/stig-report.html \
  /usr/share/xml/scap/ssg/content/ssg-al2023-ds.xml
```

## STIG Controls Implemented

| STIG ID | Description | Implementation |
|---------|-------------|----------------|
| V-230223 | SELinux in enforcing mode | `/etc/selinux/config: SELINUX=enforcing` |
| V-204431 | Account lockout (3 attempts) | `pam_faillock.so deny=3` |
| V-204624 | Session timeout (15 min) | `TMOUT=900` |
| V-204498 | USB storage disabled | `/etc/modprobe.d/usb-storage.conf` |
| V-238xxx | SSH hardening | `PermitRootLogin no`, strong ciphers |
| V-238xxx | Password complexity | `minlen=15`, complexity requirements |
| V-238xxx | Audit logging | `auditd` enabled with security rules |

## FIPS-Approved Algorithms

### SSH Configuration

```
Ciphers aes256-ctr,aes192-ctr,aes128-ctr
MACs hmac-sha2-256,hmac-sha2-512
KexAlgorithms diffie-hellman-group-exchange-sha256
```

### TLS Configuration

- TLS 1.2 minimum (TLS 1.3 where supported)
- AES-256-GCM preferred
- SHA-256 or SHA-384 for signatures

## Verification Checklist

### Pre-Deployment

- [ ] GovCloud account provisioned
- [ ] FIPS-enabled AMI selected (or Bottlerocket)
- [ ] `EnableSTIGHardening=true` in parameters
- [ ] Network isolation configured

### Post-Deployment

- [ ] FIPS mode verified: `cat /proc/sys/crypto/fips_enabled` returns `1`
- [ ] SELinux enforcing: `getenforce` returns `Enforcing`
- [ ] Auditd running: `systemctl is-active auditd`
- [ ] SSH hardened: `grep "PermitRootLogin no" /etc/ssh/sshd_config`
- [ ] Validation script passes: `./validate-stig-fips.sh`
- [ ] SCAP scan passes with STIG profile

## Compliance Evidence

For audit purposes, generate and retain:

1. **SCAP Report**: HTML report from OpenSCAP scan
2. **Validation Output**: JSON output from `validate-stig-fips.sh --json`
3. **AWS Config Rules**: Compliance status from AWS Config
4. **CloudTrail Logs**: Audit trail of configuration changes

```bash
# Generate compliance evidence
./validate-stig-fips.sh --json > /evidence/stig-fips-$(date +%Y%m%d).json

oscap xccdf eval \
  --profile xccdf_org.ssgproject.content_profile_stig \
  --report /evidence/scap-report-$(date +%Y%m%d).html \
  /usr/share/xml/scap/ssg/content/ssg-al2023-ds.xml
```

## Bottlerocket Alternative

For production GovCloud deployments, consider using Bottlerocket OS:

**Advantages:**
- FIPS 140-2 built-in
- Minimal attack surface (no shell by default)
- Immutable OS with atomic updates
- Container-optimized

**Enable in CloudFormation:**
```yaml
Parameters:
  AmiType: BOTTLEROCKET_x86_64
```

## Troubleshooting

### FIPS Mode Not Enabled After Reboot

```bash
# Check boot parameters
cat /proc/cmdline | grep fips

# Regenerate initramfs with FIPS
dracut -f

# Verify FIPS is in grub config
grep fips /etc/default/grub
```

### SELinux Blocking Application

```bash
# Check for denials
ausearch -m avc -ts recent

# Generate policy module
audit2allow -a -M myapp
semodule -i myapp.pp
```

### SSH Connection Fails After Hardening

```bash
# Verify cipher compatibility
ssh -vv -o Ciphers=aes256-ctr user@host

# Check sshd config syntax
sshd -t
```

## References

- [DISA STIG Library](https://public.cyber.mil/stigs/)
- [NIST FIPS 140-2](https://csrc.nist.gov/publications/detail/fips/140/2/final)
- [AWS GovCloud Compliance](https://aws.amazon.com/compliance/govcloud/)
- [EKS Hardening Guide](https://aws.github.io/aws-eks-best-practices/security/docs/)
- [Bottlerocket Security](https://github.com/bottlerocket-os/bottlerocket/blob/develop/SECURITY_FEATURES.md)

## Related Documents

- `docs/cloud-strategy/GOVCLOUD_READINESS_TRACKER.md`
- `docs/security/CMMC_CERTIFICATION_PATHWAY.md`
- `deploy/scripts/harden-eks-nodes.sh`
- `deploy/scripts/validate-stig-fips.sh`
