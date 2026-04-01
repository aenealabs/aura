# Compliance Certifications

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

Project Aura is designed for regulated industries requiring rigorous compliance certifications. This document details our compliance framework coverage, current certification status, control mappings, and certification roadmap.

Our compliance program addresses requirements for defense contractors (CMMC), federal agencies (FedRAMP), financial services (SOX), healthcare (HIPAA), and general enterprise security (SOC 2, NIST 800-53).

---

## Certification Status Summary

### Current Status (January 2026)

| Certification | Level/Type | Status | Target Date | Notes |
|--------------|------------|--------|-------------|-------|
| **SOC 2 Type II** | Trust Services Criteria | Audit Scheduled | Q2 2026 | Security, Availability, Confidentiality |
| **CMMC Level 2** | 110 Controls (NIST 800-171) | In Progress (~55%) | Q4 2026 | C3PAO assessment planned |
| **CMMC Level 3** | 134 Controls (800-171 + 800-172) | Planned | Q2 2027 | Requires Level 2 first |
| **FedRAMP High** | 421 Controls (NIST 800-53 Rev 5) | In Process | Q1 2027 | Agency sponsor identified |
| **NIST 800-53 Rev 5** | High Baseline | 95% Mapped | Ongoing | Foundation for FedRAMP |
| **HIPAA** | Security Rule | BAA Available | Available | Technical safeguards implemented |
| **ISO 27001** | ISMS | Planned | Q3 2027 | After SOC 2 completion |

### Certification Badges

```
+------------------+  +------------------+  +------------------+
|                  |  |                  |  |                  |
|   SOC 2 Type II  |  |   CMMC Level 2   |  |  FedRAMP High    |
|                  |  |                  |  |                  |
|   [SCHEDULED]    |  |   [IN PROGRESS]  |  |   [IN PROCESS]   |
|     Q2 2026      |  |      Q4 2026     |  |      Q1 2027     |
|                  |  |                  |  |                  |
+------------------+  +------------------+  +------------------+

+------------------+  +------------------+  +------------------+
|                  |  |                  |  |                  |
|   NIST 800-53    |  |      HIPAA       |  |   ISO 27001      |
|                  |  |                  |  |                  |
|   [95% MAPPED]   |  |  [BAA AVAILABLE] |  |    [PLANNED]     |
|     Ongoing      |  |     Available    |  |      Q3 2027     |
|                  |  |                  |  |                  |
+------------------+  +------------------+  +------------------+
```

---

## CMMC (Cybersecurity Maturity Model Certification)

### Overview

CMMC is required for Department of Defense (DoD) contractors handling Federal Contract Information (FCI) or Controlled Unclassified Information (CUI). Project Aura supports CMMC Levels 1, 2, and 3 to enable defense contractor customers.

### CMMC Level 2 (Advanced)

**Target Customers:** DoD contractors handling CUI
**Requirement:** 110 security controls from NIST SP 800-171 Rev 2
**Assessment:** Certified Third-Party Assessment Organization (C3PAO)
**Certification Validity:** 3 years

#### Current Implementation Status

| Domain | Code | Total Controls | Implemented | Status |
|--------|------|----------------|-------------|--------|
| Access Control | AC | 22 | 18 | 82% |
| Awareness & Training | AT | 3 | 0 | 0% |
| Audit & Accountability | AU | 9 | 8 | 89% |
| Configuration Management | CM | 9 | 9 | 100% |
| Identification & Authentication | IA | 11 | 9 | 82% |
| Incident Response | IR | 3 | 1 | 33% |
| Maintenance | MA | 6 | 6 | 100% |
| Media Protection | MP | 9 | 8 | 89% |
| Personnel Security | PS | 2 | 0 | 0% |
| Physical Protection | PE | 6 | 6 | 100% |
| Risk Assessment | RA | 3 | 1 | 33% |
| Security Assessment | CA | 4 | 2 | 50% |
| System & Communications | SC | 16 | 14 | 88% |
| System & Information Integrity | SI | 7 | 5 | 71% |
| **TOTAL** | | **110** | **~60** | **~55%** |

#### Control Implementation Highlights

**Fully Implemented Domains:**
- **Configuration Management (CM):** 100% Infrastructure-as-Code with CloudFormation, AWS Config rules for drift detection
- **Maintenance (MA):** AWS managed services with automated patching
- **Physical Protection (PE):** Inherited from AWS data centers with SOC 2 attestation

**Strong Implementation:**
- **Audit & Accountability (AU):** CloudTrail, VPC Flow Logs (365-day retention), CloudWatch Logs
- **System & Communications (SC):** TLS 1.3, KMS encryption, VPC isolation, WAF protection
- **Media Protection (MP):** S3 encryption, versioning, lifecycle policies

**Gaps Requiring Attention:**
- **Awareness & Training (AT):** Security training program needed
- **Personnel Security (PS):** Background check process needed
- **Incident Response (IR):** Formal IR plan and procedures needed
- **Risk Assessment (RA):** Formal risk assessment program needed

### CMMC Level 3 (Expert)

**Target Customers:** DoD contractors on critical programs handling sensitive CUI
**Requirement:** 110 controls (Level 2) + 24 enhanced controls from NIST SP 800-172
**Assessment:** C3PAO + government validation (DCMA)
**Prerequisite:** CMMC Level 2 certification

#### Enhanced Control Categories

| Category | Additional Controls | Key Requirements |
|----------|---------------------|------------------|
| Access Control | 4 | Dynamic risk-based access, micro-segmentation |
| Incident Response | 4 | Insider threat program, SOC capability, CTI |
| Risk Assessment | 4 | Threat hunting, adversary emulation |
| Security Assessment | 6 | Purple team, continuous testing, developer security |
| Configuration Management | 2 | SBOM, anti-tamper protection |
| Personnel Security | 2 | Enhanced screening |
| System & Communications | 2 | Advanced encryption, enhanced isolation |

**Timeline:** CMMC Level 3 certification planned for Q2 2027 following Level 2 achievement.

---

## FedRAMP (Federal Risk and Authorization Management Program)

### Overview

FedRAMP provides a standardized approach to security assessment for cloud products serving federal agencies. Project Aura targets FedRAMP High authorization to serve agencies processing high-impact data.

### FedRAMP Impact Levels

| Impact Level | Data Sensitivity | Example Agencies | Aura Support |
|--------------|------------------|------------------|--------------|
| Low | Publicly available data | General Services Administration | Supported |
| Moderate | Confidential, not national security | Department of Education | Supported |
| **High** | National security, critical systems | DoD, DHS, Intelligence | **Primary Target** |

### FedRAMP High Authorization

**Baseline:** NIST SP 800-53 Rev 5 High Baseline
**Total Controls:** 421 controls across 20 families
**Assessment:** FedRAMP-accredited 3PAO
**Authorization Path:** Agency Authorization (initial) with JAB P-ATO (planned)

#### Control Family Coverage

| Family | Code | Controls | Implementation | Status |
|--------|------|----------|----------------|--------|
| Access Control | AC | 25 | IAM, RBAC, MFA | 85% |
| Awareness & Training | AT | 5 | Training platform needed | 0% |
| Audit & Accountability | AU | 16 | CloudTrail, CloudWatch | 90% |
| Security Assessment | CA | 9 | Automated testing | 40% |
| Configuration Management | CM | 11 | IaC, AWS Config | 95% |
| Contingency Planning | CP | 13 | Multi-AZ, backups | 70% |
| Identification & Auth | IA | 12 | Argon2id, JWT, MFA | 80% |
| Incident Response | IR | 10 | GuardDuty, alarms | 40% |
| Maintenance | MA | 6 | AWS managed | 95% |
| Media Protection | MP | 8 | KMS, S3 policies | 90% |
| Physical & Environmental | PE | 20 | AWS inherited | 100% |
| Planning | PL | 9 | Architecture docs | 60% |
| Personnel Security | PS | 8 | Process needed | 20% |
| Risk Assessment | RA | 6 | Inspector deployed | 30% |
| System & Services Acq | SA | 22 | Procurement process | 50% |
| System & Comms | SC | 44 | TLS, encryption | 85% |
| System & Info Integrity | SI | 17 | WAF, GuardDuty | 75% |
| Program Management | PM | ~30 | Enterprise program | 40% |

#### Authorization Pathway

```
+-------------+     +-------------+     +-------------+     +-------------+
|   Phase 1   | --> |   Phase 2   | --> |   Phase 3   | --> |   Phase 4   |
+-------------+     +-------------+     +-------------+     +-------------+
| Gap Analysis|     | SSP & Docs  |     | 3PAO Assess |     | Agency Auth |
| 3 months    |     | 3 months    |     | 3 months    |     | 3 months    |
+-------------+     +-------------+     +-------------+     +-------------+
```

**Current Phase:** Phase 1 - Gap Analysis and Documentation Foundation
**Target Agency Authorization:** Q1 2027

---

## SOX (Sarbanes-Oxley Act)

### Overview

SOX Section 404 requires publicly traded companies to maintain internal controls over financial reporting. Project Aura implements controls supporting SOX compliance for financial services customers.

### SOX Control Categories

| Control Category | Aura Implementation |
|------------------|---------------------|
| **Access Controls** | RBAC with least privilege, MFA enforcement, access reviews |
| **Change Management** | All changes through approval workflows, audit trails |
| **Segregation of Duties** | Role separation in approval workflows, agent isolation |
| **Audit Trails** | Immutable logs, 7-year retention capability, tamper evidence |
| **IT General Controls** | Configuration management, vulnerability management, patch management |

### SOX-Relevant Features

**Change Authorization:**
- All code changes require documented approval
- Approval workflows with configurable gates
- Complete audit trail from detection to deployment

**Access Management:**
- Role-based access control
- Quarterly access review support
- Privileged access logging

**Audit Support:**
- Immutable audit logs
- Configurable retention (default 7 years)
- Export capabilities for external auditors
- Segregation of duties documentation

---

## NIST 800-53 Controls Mapping

### Control Mapping Overview

Project Aura maps to NIST SP 800-53 Rev 5 controls as the foundation for both CMMC and FedRAMP compliance.

### High-Impact Control Families

#### Access Control (AC)

| Control | Title | Implementation |
|---------|-------|----------------|
| AC-2 | Account Management | IAM policies, automated provisioning |
| AC-3 | Access Enforcement | RBAC, security groups, NACLs |
| AC-4 | Information Flow | VPC isolation, subnet separation |
| AC-5 | Separation of Duties | Role-based workflows, approval gates |
| AC-6 | Least Privilege | Scoped IAM policies, IRSA |
| AC-7 | Unsuccessful Logon Attempts | Cognito lockout, JWT validation |
| AC-17 | Remote Access | TLS 1.3, VPN support, session management |

#### Audit and Accountability (AU)

| Control | Title | Implementation |
|---------|-------|----------------|
| AU-2 | Audit Events | CloudTrail, application logs |
| AU-3 | Content of Audit Records | Structured JSON logging |
| AU-4 | Audit Storage Capacity | CloudWatch Logs, S3 archival |
| AU-5 | Response to Audit Failures | CloudWatch alarms, SNS alerts |
| AU-6 | Audit Review | Security dashboards, SIEM integration |
| AU-9 | Protection of Audit Information | IAM controls, encryption |
| AU-11 | Audit Record Retention | 365 days production, 90 days dev |

#### System and Communications Protection (SC)

| Control | Title | Implementation |
|---------|-------|----------------|
| SC-7 | Boundary Protection | VPC, security groups, WAF |
| SC-8 | Transmission Confidentiality | TLS 1.3 all communications |
| SC-12 | Cryptographic Key Management | AWS KMS, CMK rotation |
| SC-13 | Cryptographic Protection | AES-256, FIPS endpoints (GovCloud) |
| SC-28 | Protection of Information at Rest | KMS encryption, S3 SSE |

#### System and Information Integrity (SI)

| Control | Title | Implementation |
|---------|-------|----------------|
| SI-2 | Flaw Remediation | Automated patching, Inspector |
| SI-3 | Malicious Code Protection | GuardDuty, Bedrock Guardrails |
| SI-4 | Information System Monitoring | CloudWatch, GuardDuty, Config |
| SI-5 | Security Alerts | SNS, CloudWatch alarms |
| SI-7 | Software Integrity | Code signing, immutable infrastructure |

---

## SOC 2 Type II

### Overview

SOC 2 Type II certification demonstrates operational effectiveness of security controls over an audit period (typically 6-12 months).

### Trust Services Criteria

| Criteria | Scope | Status |
|----------|-------|--------|
| **Security** | Protection against unauthorized access | Implemented |
| **Availability** | System uptime and performance | Implemented |
| **Confidentiality** | Protection of confidential information | Implemented |
| Processing Integrity | Accuracy of system processing | Planned |
| Privacy | Personal information handling | Planned |

### Audit Timeline

- **Audit Period Start:** Q1 2026
- **Audit Period End:** Q2 2026
- **Report Availability:** Q3 2026

### SOC 2 Evidence Sources

| Control Area | Evidence Source |
|--------------|-----------------|
| Access Control | IAM policies, access logs |
| Change Management | CloudFormation history, approval logs |
| Encryption | KMS key inventory, configuration |
| Monitoring | CloudWatch dashboards, alarm configurations |
| Incident Response | GuardDuty findings, response logs |
| Vendor Management | Third-party risk assessments |

---

## HIPAA (Health Insurance Portability and Accountability Act)

### Overview

Project Aura supports HIPAA compliance for healthcare customers processing Protected Health Information (PHI).

### HIPAA Safeguards

| Safeguard Type | Requirements | Aura Implementation |
|----------------|--------------|---------------------|
| **Administrative** | Security management, workforce training | Security policies, training support |
| **Physical** | Facility access, workstation security | AWS inherited controls |
| **Technical** | Access control, audit controls, encryption | IAM, CloudTrail, KMS |

### Business Associate Agreement (BAA)

Aenea Labs provides a Business Associate Agreement (BAA) for healthcare customers.

**BAA Coverage:**
- PHI processing in Aura platform
- Security incident notification
- Breach notification procedures
- Subcontractor requirements

**BAA Availability:** Contact sales@aenealabs.com

### PHI Handling

| Control | Implementation |
|---------|----------------|
| Encryption | AES-256 at rest, TLS 1.3 in transit |
| Access Logging | All PHI access logged with user identity |
| Minimum Necessary | Role-based access to PHI data |
| Audit Trails | 7-year retention for PHI access logs |

---

## Certification Roadmap

### 2026 Timeline

```
Q1 2026:
+-- SOC 2 Type II audit period begins
+-- FedRAMP gap analysis continues
+-- CMMC Level 2 gap closure

Q2 2026:
+-- SOC 2 Type II audit completes
+-- CMMC Level 2 pre-assessment
+-- FedRAMP SSP development

Q3 2026:
+-- SOC 2 Type II report available
+-- CMMC Level 2 C3PAO engagement
+-- FedRAMP 3PAO readiness assessment

Q4 2026:
+-- CMMC Level 2 C3PAO assessment
+-- CMMC Level 2 certification (target)
+-- FedRAMP full assessment begins
```

### 2027 Timeline

```
Q1 2027:
+-- FedRAMP agency authorization (target)
+-- CMMC Level 3 planning begins

Q2 2027:
+-- CMMC Level 3 implementation
+-- FedRAMP JAB P-ATO process begins

Q3 2027:
+-- ISO 27001 implementation
+-- CMMC Level 3 assessment

Q4 2027:
+-- ISO 27001 certification
+-- FedRAMP marketplace listing
```

---

## Compliance Documentation Available

### For Enterprise Customers

| Document | Description | Availability |
|----------|-------------|--------------|
| SOC 2 Bridge Letter | Current security posture attestation | Under NDA |
| Security White Paper | Architecture and controls overview | Public |
| Penetration Test Summary | Third-party security assessment | Under NDA |
| NIST Control Mapping | Detailed control implementation | Under NDA |
| Data Processing Agreement | GDPR/privacy compliance | Upon request |
| Business Associate Agreement | HIPAA compliance | Upon request |

### Requesting Documentation

Enterprise customers can request compliance documentation by contacting:

- **Email:** compliance@aenealabs.com
- **Subject:** Compliance Documentation Request - [Company Name]
- **Include:** NDA status, specific documents needed, audit timeline

---

## Compliance Support Services

### Pre-Sales Support

- Security architecture review
- Compliance gap analysis
- Control mapping assistance
- Audit preparation guidance

### Implementation Support

- Security configuration guidance
- Compliance control implementation
- Documentation templates
- Evidence collection automation

### Ongoing Support

- Quarterly compliance reviews
- Certification maintenance support
- Auditor coordination
- Control update notifications

---

## Related Documentation

- [Security & Compliance Overview](./index.md)
- [Data Handling](./data-handling.md)
- [Audit Logging](./audit-logging.md)
- [GovCloud Guide](./govcloud-guide.md)
- [CMMC Level 2 Roadmap](../../compliance/roadmaps/CMMC_LEVEL_2_ROADMAP.md)
- [FedRAMP High Roadmap](../../compliance/roadmaps/FEDRAMP_HIGH_ROADMAP.md)

---

*Last updated: January 2026 | Version 1.0*
