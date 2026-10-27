# Compliance Certifications

**Version:** 1.1
**Last Updated:** October 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

Project Aura is designed for regulated industries requiring rigorous compliance certifications. This document details our compliance framework coverage, current certification status, control mappings, and certification roadmap.

> **Status: Planned. No certification filing has been submitted (as of October 2026).** Aura holds no SOC 2, CMMC, FedRAMP, StateRAMP, DoD IL, ISO 27001, PCI-DSS, or HIPAA certification, attestation, or authorization today, and none of these assessments has been started. No Business Associate Agreement (BAA) is offered. Technical controls are aligned with NIST 800-53. Every certification, timeline, and percentage below is an internal planning target or self-assessment, not an audited result.

Our compliance program addresses requirements for defense contractors (CMMC), federal agencies (FedRAMP), financial services (SOX), healthcare (HIPAA), and general enterprise security (SOC 2, NIST 800-53).

---

## Certification Status Summary

### Current Status (October 2026)

| Certification | Level/Type | Status | Target Date | Notes |
|--------------|------------|--------|-------------|-------|
| **SOC 2 Type II** | Trust Services Criteria | Planned (no auditor engaged) | Not scheduled | Security, Availability, Confidentiality in scope when started |
| **CMMC Level 2** | 110 Controls (NIST 800-171) | Planned (not yet pursued) | Not scheduled | Internal self-assessment only; no C3PAO engaged |
| **CMMC Level 3** | 134 Controls (800-171 + 800-172) | Planned | Not scheduled | Requires Level 2 first |
| **FedRAMP High** | 421 Controls (NIST 800-53 Rev 5) | Planned (not yet pursued) | Not scheduled | No agency sponsor or 3PAO engaged |
| **NIST 800-53 Rev 5** | High Baseline | Aligned (technical controls) | Ongoing | Not independently assessed |
| **HIPAA** | Security Rule | Technical safeguards aligned (no attestation) | &mdash; | No BAA is offered |
| **ISO 27001** | ISMS | Planned | Not scheduled | After SOC 2 |

### Certification Badges

```
+------------------+  +------------------+  +------------------+
|                  |  |                  |  |                  |
|   SOC 2 Type II  |  |   CMMC Level 2   |  |  FedRAMP High    |
|                  |  |                  |  |                  |
|    [PLANNED]     |  |     [PLANNED]    |  |     [PLANNED]    |
|  Not scheduled   |  |   Not scheduled  |  |   Not scheduled  |
|                  |  |                  |  |                  |
+------------------+  +------------------+  +------------------+

+------------------+  +------------------+  +------------------+
|                  |  |                  |  |                  |
|   NIST 800-53    |  |      HIPAA       |  |   ISO 27001      |
|                  |  |                  |  |                  |
|    [ALIGNED]     |  |    [ALIGNED]     |  |    [PLANNED]     |
|     Ongoing      |  |     Ongoing      |  |  Not scheduled   |
|                  |  |                  |  |                  |
+------------------+  +------------------+  +------------------+
```

---

## CMMC (Cybersecurity Maturity Model Certification)

### Overview

CMMC is required for Department of Defense (DoD) contractors handling Federal Contract Information (FCI) or Controlled Unclassified Information (CUI). Project Aura is designed to support CMMC-aligned controls for defense contractor customers; it is not CMMC certified at any level, and no assessment has been filed.

### CMMC Level 2 (Advanced)

**Target Customers:** DoD contractors handling CUI
**Requirement:** 110 security controls from NIST SP 800-171 Rev 2
**Assessment:** Certified Third-Party Assessment Organization (C3PAO)
**Certification Validity:** 3 years

#### Control Domains

| Domain | Code | Total Controls |
|--------|------|----------------|
| Access Control | AC | 22 |
| Awareness & Training | AT | 3 |
| Audit & Accountability | AU | 9 |
| Configuration Management | CM | 9 |
| Identification & Authentication | IA | 11 |
| Incident Response | IR | 3 |
| Maintenance | MA | 6 |
| Media Protection | MP | 9 |
| Personnel Security | PS | 2 |
| Physical Protection | PE | 6 |
| Risk Assessment | RA | 3 |
| Security Assessment | CA | 4 |
| System & Communications | SC | 16 |
| System & Information Integrity | SI | 7 |
| **TOTAL** | | **110** |

#### Control Implementation Highlights

**Aligned Technical Controls (unaudited):**
- **Configuration Management (CM):** 100% Infrastructure-as-Code with CloudFormation, AWS Config rules for drift detection
- **Maintenance (MA):** AWS managed services with automated patching
- **Physical Protection (PE):** Inherited from AWS data centers (AWS's own SOC 2 reports; Aura has no SOC 2 report)

**Additional Aligned Technical Controls (unaudited):**
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

**Timeline:** CMMC Level 3 is planned after Level 2; no date is set.

---

## FedRAMP (Federal Risk and Authorization Management Program)

### Overview

FedRAMP provides a standardized approach to security assessment for cloud products serving federal agencies. Project Aura plans to pursue FedRAMP High authorization to serve agencies processing high-impact data. Status: Planned. No FedRAMP filing has been submitted, and Aura is not FedRAMP authorized at any level.

### FedRAMP Impact Levels

| Impact Level | Data Sensitivity | Example Agencies | Aura Support |
|--------------|------------------|------------------|--------------|
| Low | Publicly available data | General Services Administration | Planned |
| Moderate | Confidential, not national security | Department of Education | Planned |
| **High** | National security, critical systems | DoD, DHS, Intelligence | **Planned (primary target)** |

### FedRAMP High Authorization (Planned)

**Baseline:** NIST SP 800-53 Rev 5 High Baseline
**Total Controls:** 421 controls across 20 families
**Assessment:** FedRAMP-accredited 3PAO
**Authorization Path:** Agency Authorization (initial) with JAB P-ATO (planned)

#### Control Family Coverage

| Family | Code | Controls | Implementation |
|--------|------|----------|----------------|
| Access Control | AC | 25 | IAM, RBAC, MFA |
| Awareness & Training | AT | 5 | Training platform needed |
| Audit & Accountability | AU | 16 | CloudTrail, CloudWatch |
| Security Assessment | CA | 9 | Automated testing |
| Configuration Management | CM | 11 | IaC, AWS Config |
| Contingency Planning | CP | 13 | Multi-AZ, backups |
| Identification & Auth | IA | 12 | Cognito-managed credentials, JWT, MFA |
| Incident Response | IR | 10 | GuardDuty, alarms |
| Maintenance | MA | 6 | AWS managed |
| Media Protection | MP | 8 | KMS, S3 policies |
| Physical & Environmental | PE | 20 | AWS inherited |
| Planning | PL | 9 | Architecture docs |
| Personnel Security | PS | 8 | Process needed |
| Risk Assessment | RA | 6 | Inspector deployed |
| System & Services Acq | SA | 22 | Procurement process |
| System & Comms | SC | 44 | TLS, encryption |
| System & Info Integrity | SI | 17 | WAF, GuardDuty |
| Program Management | PM | Not counted | Enterprise program |

#### Authorization Pathway

```
+-------------+     +-------------+     +-------------+     +-------------+
|   Phase 1   | --> |   Phase 2   | --> |   Phase 3   | --> |   Phase 4   |
+-------------+     +-------------+     +-------------+     +-------------+
| Gap Analysis|     | SSP & Docs  |     | 3PAO Assess |     | Agency Auth |
| 3 months    |     | 3 months    |     | 3 months    |     | 3 months    |
+-------------+     +-------------+     +-------------+     +-------------+
```

**Current Phase:** Not started. Internal gap analysis only; no agency sponsor, 3PAO, or SSP engagement.
**Target Agency Authorization:** Not scheduled

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
| **Audit Trails** | CloudTrail and CloudWatch Logs with configurable retention (7-year target); application-level tamper evidence is planned |
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
- CloudTrail and CloudWatch audit logs (application-level tamper evidence planned)
- Configurable retention (7-year target)
- Export capabilities for external auditors
- Segregation of duties documentation

---

## NIST 800-53 Controls Mapping

### Control Mapping Overview

Project Aura maps to NIST SP 800-53 Rev 5 controls as the foundation for planned CMMC and FedRAMP certification efforts. These mappings are aligned technical controls, not an assessed or certified baseline.

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

SOC 2 Type II attestation demonstrates operational effectiveness of security controls over an audit period (typically 6-12 months). Aura has not started a SOC 2 audit.

### Trust Services Criteria

| Criteria | Scope | Status |
|----------|-------|--------|
| **Security** | Protection against unauthorized access | Controls aligned (unaudited) |
| **Availability** | System uptime and performance | Controls aligned (unaudited) |
| **Confidentiality** | Protection of confidential information | Controls aligned (unaudited) |
| Processing Integrity | Accuracy of system processing | Planned |
| Privacy | Personal information handling | Planned |

### Audit Timeline

- **Audit Period:** Not scheduled
- **Report Availability:** No report exists

The `/api/v1/compliance` evidence endpoints catalog SOC 2 controls, but their evidence collectors currently return fixed sample values rather than querying AWS, so their assessments are not audit evidence.

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

Project Aura is designed to support HIPAA-aligned technical safeguards for healthcare customers. Aura has no HIPAA attestation, and no Business Associate Agreement (BAA) is offered.

### HIPAA Safeguards

| Safeguard Type | Requirements | Aura Implementation |
|----------------|--------------|---------------------|
| **Administrative** | Security management, workforce training | Security policies, training support |
| **Physical** | Facility access, workstation security | AWS inherited controls |
| **Technical** | Access control, audit controls, encryption | IAM, CloudTrail, KMS |

### PHI Handling Controls (technical, unaudited)

| Control | Implementation |
|---------|----------------|
| Encryption | AES-256 at rest, TLS 1.3 in transit |
| Access Logging | All PHI access logged with user identity |
| Minimum Necessary | Role-based access to PHI data |
| Audit Trails | 7-year retention for PHI access logs |

---

## Certification Roadmap

**Status: Planned. No certification filing has been submitted (as of October 2026).** The timelines below were drafted in January 2026 as planning targets. None of the 2026 milestones has started; dates will be reset when a specific contract requires a certification.

### 2026 Timeline (original planning targets)

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

### 2027 Timeline (original planning targets)

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
| SOC 2 Bridge Letter | Current security posture attestation | Not available (no SOC 2 report) |
| Security White Paper | Architecture and controls overview | Public |
| Penetration Test Summary | Third-party security assessment | Not yet available (see [Penetration Testing Program](../../security/PENETRATION_TESTING_PROGRAM.md)) |
| NIST Control Mapping | Detailed control implementation | Under NDA |
| Data Processing Agreement | GDPR/privacy compliance | Upon request |

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
- Support for customers maintaining their own certifications
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

*Last updated: October 2026 | Version 1.1*
