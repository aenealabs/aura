# Security & Compliance

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Introduction

Security and compliance are foundational to Project Aura's architecture, not afterthoughts. Built from the ground up for regulated industries including defense, financial services, healthcare, and federal government, Aura provides enterprise-grade security controls with comprehensive audit capabilities.

This section provides detailed documentation on Aura's security architecture, compliance certifications, data handling practices, and deployment options for regulated environments.

---

## Security-First Design Philosophy

Project Aura implements a defense-in-depth security model with multiple overlapping layers of protection. Every architectural decision prioritizes security, from encrypted data storage to isolated sandbox execution environments.

### Core Security Principles

| Principle | Implementation |
|-----------|----------------|
| **Zero Trust Architecture** | No implicit trust within the network; all service-to-service communication authenticated |
| **Least Privilege Access** | IAM policies scoped to minimum required permissions; IRSA for Kubernetes workloads |
| **Defense in Depth** | Six security layers: perimeter, network, identity, application, data, monitoring |
| **Encryption Everywhere** | AES-256 encryption at rest, TLS 1.3 in transit, customer-managed KMS keys |
| **Immutable Audit Trails** | All security-relevant events logged with 365-day retention (production) |
| **Isolated Execution** | AI-generated patches validated in network-isolated sandbox environments |

### Security Architecture Overview

```
+---------------------------------------------------------------------------+
|                           DEFENSE IN DEPTH                                 |
+---------------------------------------------------------------------------+
|                                                                            |
|   Layer 1: PERIMETER                                                       |
|   AWS WAF | DDoS Protection | Geo-Blocking | Rate Limiting                 |
|                                                                            |
|   Layer 2: NETWORK                                                         |
|   VPC Isolation | Security Groups | NACLs | VPC Endpoints                  |
|                                                                            |
|   Layer 3: IDENTITY                                                        |
|   IAM Roles | IRSA | RBAC | MFA | Session Management                      |
|                                                                            |
|   Layer 4: APPLICATION                                                     |
|   Input Validation | Output Encoding | CSRF Protection | Rate Limiting    |
|                                                                            |
|   Layer 5: DATA                                                            |
|   KMS Encryption | Customer-Managed Keys | Automatic Key Rotation         |
|                                                                            |
|   Layer 6: MONITORING                                                      |
|   GuardDuty | CloudTrail | AWS Config | Security Hub | SIEM Integration   |
|                                                                            |
+---------------------------------------------------------------------------+
```

---

## Compliance Certifications Summary

Project Aura supports compliance requirements for regulated industries. Our infrastructure is designed to support controls aligned with federal and commercial standards; it is not certified against them.

### Current Certification Status

| Framework | Target | Status | Timeline |
|-----------|--------|--------|----------|
| **SOC 2 Type II** | All customers | Planned (no auditor engaged) | Not scheduled |
| **CMMC Level 2** | DoD contractors | Planned (not yet pursued) | Not scheduled |
| **CMMC Level 3** | Critical DoD programs | Planned | Not scheduled |
| **FedRAMP High** | Federal agencies | Planned (not yet pursued) | Not scheduled |
| **NIST 800-53 Rev 5** | All customers | Aligned (technical controls, not independently assessed) | Ongoing |
| **HIPAA** | Healthcare | Technical safeguards aligned (no attestation; no BAA offered) | Ongoing |
| **SOX Section 404** | Financial services | Supporting controls aligned (customer's auditor attests) | Ongoing |

Status: Planned. No certification filing has been submitted (as of October 2026). Aura holds no SOC 2, CMMC, FedRAMP, IL5, ISO 27001, PCI-DSS, or HIPAA certification, attestation, or authorization today, and no Business Associate Agreement (BAA) is offered.

### Compliance Quick Reference

| If Your Industry Is... | Frameworks Your Organization May Need | Aura Support |
|------------------------|------------------------|--------------|
| Defense / Aerospace | CMMC Level 2/3, NIST 800-171 | GovCloud-compatible templates (GovCloud production deployment planned), control mapping |
| Federal Government | FedRAMP High, NIST 800-53 | NIST 800-53 aligned controls; FedRAMP authorization on the roadmap |
| Financial Services | SOX, SOC 2 | Audit trails, change management controls |
| Healthcare | HIPAA, HITRUST | HIPAA-aligned technical safeguards (no BAA offered) |
| Critical Infrastructure | NIST CSF, CIS Controls | Control framework alignment |

[View Detailed Compliance Certifications](./compliance-certifications.md)

---

## Shared Responsibility Model

Project Aura operates under a shared responsibility model where Aenea Labs manages platform security while customers maintain responsibility for their own data and access controls.

### Aenea Labs Responsibilities

**Infrastructure Security**
- Physical security of cloud infrastructure (via AWS)
- Network isolation and segmentation
- Platform vulnerability management
- Security monitoring and incident response
- Encryption key management (platform keys)
- Compliance control maintenance (certifications planned, none held today)

**Application Security**
- Secure software development lifecycle
- Regular penetration testing
- Agent security and isolation
- Sandbox environment hardening
- API security and rate limiting
- Audit logging infrastructure

### Customer Responsibilities

**Access Management**
- User account provisioning and deprovisioning
- RBAC role assignments
- MFA enforcement policies
- SSO/SAML configuration
- API key rotation

**Data Governance**
- Classification of repository data
- Approval workflow configuration
- Data retention policy decisions
- Export and deletion requests
- Third-party integration authorization

**Compliance**
- Internal compliance program management
- Auditor coordination
- Policy documentation
- User security training
- Incident response coordination

### Shared Responsibilities

| Area | Aenea Labs | Customer |
|------|------------|----------|
| **Identity Management** | Provide SSO/SAML integration | Configure identity provider |
| **Access Control** | Implement RBAC framework | Assign appropriate roles |
| **Encryption** | Manage platform encryption keys | Manage customer-managed keys (if applicable) |
| **Audit Logs** | Generate and store logs | Review and act on findings |
| **Incident Response** | Platform incident handling | Customer data incident coordination |
| **Vulnerability Management** | Platform patching | Repository security policy |

---

## Key Security Features

### Network Isolation

All customer data is processed within dedicated VPC infrastructure with strict network controls.

| Component | Isolation Level | Network Access |
|-----------|----------------|----------------|
| Application Services | Private Subnets | VPC Endpoints only |
| Database Layer | Isolated Subnets | No internet access |
| Sandbox Environments | Container-level (see note) | No inbound, no public IP, egress limited to UDP 53 + TCP 443 |
| API Gateway | Public Subnet (ALB) | WAF-protected ingress |

**Sandbox note.** Sandbox tasks run in the platform VPC's private subnets, not
in a dedicated sandbox VPC. `container` is the strongest isolation level the
provisioning path enforces; `vpc` and `full` are declared on
`NetworkIsolationLevel` but refused with `UnsupportedIsolationLevelError`. See
`ENFORCED_ISOLATION_LEVELS` in `src/services/sandbox_network_service.py:79` and
[Sandbox Security Model](../core-concepts/sandbox-security.md).

### AI-Specific Security Controls

Project Aura implements specialized security controls for AI/ML workloads that go beyond traditional application security.

| Threat | Control | Implementation |
|--------|---------|----------------|
| Prompt Injection | Input Sanitization | LLM prompt sanitizer with pattern detection |
| Data Exfiltration | Output Filtering | Bedrock Guardrails with content filtering |
| Model Abuse | Rate Limiting | Per-user and per-organization token limits |
| Jailbreak Attempts | Content Filtering | Bedrock Guardrails with HIGH sensitivity |
| Agent Confusion | Tool Validation | A2AS input assessment at orchestrator entry; capability-governance tool enforcement built but not yet wired |
| GraphRAG Poisoning | Data Integrity | Injection scanning of ingested content and context provenance verification at retrieval |

### Sandbox Security Model

Every AI-generated patch is validated in an isolated sandbox environment before human review.

**Sandbox Isolation Controls:**
- Network-isolated ECS Fargate tasks (no internet, no VPC endpoints)
- Read-only access to test data only
- seccomp and AppArmor security profiles
- CPU, memory, and time limits enforced
- All capabilities dropped except those explicitly required
- Automatic cleanup after validation

---

## Security Documentation

This section contains detailed security and compliance documentation organized by topic.

### Documentation Index

| Document | Description | Audience |
|----------|-------------|----------|
| [Compliance Certifications](./compliance-certifications.md) | Detailed compliance framework coverage including CMMC, FedRAMP, SOX, and NIST mappings | Compliance Officers, CISOs |
| [Data Handling](./data-handling.md) | Data classification, encryption, retention, residency, and privacy controls | Security Engineers, DPOs |
| [Audit Logging](./audit-logging.md) | Audit event types, log retention, SIEM integration, and compliance reporting | Security Operations, Auditors |
| [GovCloud Guide](./govcloud-guide.md) | AWS GovCloud deployment, IL4/IL5 support, and federal compliance | Federal Customers, Platform Engineers |

---

## Recommended Reading Paths

### For Security Engineers

1. **[Data Handling](./data-handling.md)** - Understand encryption and data protection
2. **[Audit Logging](./audit-logging.md)** - Configure security monitoring
3. **[Compliance Certifications](./compliance-certifications.md)** - Review control mappings

### For Compliance Officers

1. **[Compliance Certifications](./compliance-certifications.md)** - Review certification status
2. **[Audit Logging](./audit-logging.md)** - Understand audit capabilities
3. **[Data Handling](./data-handling.md)** - Review data governance controls

### For Federal Customers

1. **[GovCloud Guide](./govcloud-guide.md)** - Understand deployment options
2. **[Compliance Certifications](./compliance-certifications.md)** - Review FedRAMP status
3. **[Data Handling](./data-handling.md)** - Understand data residency

---

## Security Contacts

### Reporting Security Issues

If you discover a security vulnerability in Project Aura, please report it responsibly:

- **Security Email:** security@aenealabs.com
- **Response Time:** Initial response within 24 hours
- **Disclosure Policy:** 90-day coordinated disclosure

### Compliance Inquiries

For compliance documentation, audit requests, or certification questions:

- **Compliance Team:** compliance@aenealabs.com
- **Documentation:** Available under NDA for enterprise customers

### Emergency Security Contact

For active security incidents requiring immediate attention:

- **24/7 Security Hotline:** Available to enterprise customers
- **Incident Escalation:** Contact your account representative

---

## Related Documentation

### Platform Documentation
- [Platform Overview](../getting-started/index.md) - Introduction to Project Aura
- [Core Concepts](../core-concepts/index.md) - Technical architecture overview
- [HITL Workflows](../core-concepts/hitl-workflows.md) - Human-in-the-loop governance

### Technical Documentation
- [Security Architecture](../../support/architecture/security-architecture.md) - Detailed security controls
- [System Overview](../../support/architecture/system-overview.md) - Platform architecture

### Compliance Roadmaps
- [CMMC Level 2 Roadmap](../../compliance/roadmaps/CMMC_LEVEL_2_ROADMAP.md) - Certification pathway
- [FedRAMP High Roadmap](../../compliance/roadmaps/FEDRAMP_HIGH_ROADMAP.md) - Authorization pathway

---

*Last updated: January 2026 | Version 1.0*
