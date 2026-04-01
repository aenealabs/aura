# Data Handling

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This document describes how Project Aura handles, protects, and manages customer data throughout its lifecycle. Our data handling practices are designed to meet requirements for CMMC, FedRAMP, SOX, HIPAA, and GDPR compliance.

Understanding data handling is critical for security teams, compliance officers, and data protection officers evaluating Aura for regulated workloads.

---

## Data Classification

Project Aura processes several categories of data, each with specific protection requirements.

### Data Categories

| Category | Description | Sensitivity | Retention |
|----------|-------------|-------------|-----------|
| **Source Code** | Customer repository code analyzed by Aura | High | Customer-controlled |
| **Code Metadata** | Function signatures, dependencies, call graphs | Medium | 90 days (configurable) |
| **Vulnerability Data** | Detected security issues and CVE mappings | High | 1 year (compliance) |
| **Patch Data** | AI-generated patches and remediation code | High | 1 year (compliance) |
| **Audit Logs** | User actions, agent decisions, system events | Medium | 365 days production |
| **User Data** | Account information, preferences, API keys | High | Account lifetime + 30 days |
| **LLM Interactions** | Prompts, responses, token usage | Medium | 90 days |
| **Telemetry** | Performance metrics, error rates, usage stats | Low | 90 days |

### Data Flow Diagram

```
+----------------+     +------------------+     +------------------+
|   CUSTOMER     |     |   INGESTION      |     |   PROCESSING     |
|   REPOSITORY   | --> |   LAYER          | --> |   LAYER          |
+----------------+     +------------------+     +------------------+
                              |                        |
                              v                        v
                       +-----------+           +-------------+
                       | S3 Bucket |           | Neptune     |
                       | (Code)    |           | (Graph)     |
                       +-----------+           +-------------+
                              |                        |
                              v                        v
                       +-----------+           +-------------+
                       | KMS Key   |           | OpenSearch  |
                       | Encryption|           | (Vectors)   |
                       +-----------+           +-------------+
                                                      |
                                                      v
                                               +-------------+
                                               | Bedrock     |
                                               | (LLM)       |
                                               +-------------+
                                                      |
                                                      v
                                               +-------------+
                                               | SANDBOX     |
                                               | (Validation)|
                                               +-------------+
```

---

## Encryption

### Encryption at Rest

All customer data is encrypted at rest using AES-256 encryption with AWS KMS customer-managed keys (CMK).

| Data Store | Encryption Method | Key Type | Key Rotation |
|------------|-------------------|----------|--------------|
| Neptune (Graph DB) | AES-256 | Customer-Managed CMK | Annual (automatic) |
| OpenSearch (Vectors) | AES-256 | Customer-Managed CMK | Annual (automatic) |
| DynamoDB (Metadata) | AES-256 | Customer-Managed CMK | Annual (automatic) |
| S3 (Artifacts) | AES-256-GCM | Customer-Managed CMK | Annual (automatic) |
| EBS (Node Storage) | AES-256 | Customer-Managed CMK | Annual (automatic) |
| Secrets Manager | AES-256 | AWS-Managed CMK | Automatic |
| CloudWatch Logs | AES-256 | Customer-Managed CMK | Annual (automatic) |

#### KMS Key Policy

KMS keys are scoped to specific services using the `kms:ViaService` condition:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowServiceUse",
      "Effect": "Allow",
      "Principal": {"Service": ["neptune.amazonaws.com", "es.amazonaws.com"]},
      "Action": ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey*"],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": [
            "neptune.us-east-1.amazonaws.com",
            "es.us-east-1.amazonaws.com"
          ]
        }
      }
    }
  ]
}
```

#### Customer-Managed Keys (BYOK)

Enterprise customers can provide their own KMS keys for additional control:

- **Bring Your Own Key (BYOK):** Import existing key material
- **External Key Store:** Use keys stored in external HSM
- **Key Access Logging:** CloudTrail logging of all key usage

Contact your account representative for BYOK configuration.

### Encryption in Transit

All data in transit is encrypted using TLS 1.3 (preferred) or TLS 1.2 (minimum).

| Communication Path | Protocol | Certificate |
|--------------------|----------|-------------|
| Client to API Gateway | TLS 1.3 | ACM-managed certificate |
| API Gateway to EKS | TLS 1.2+ | Internal CA |
| EKS to Neptune | TLS 1.2 | AWS-managed |
| EKS to OpenSearch | TLS 1.2 | AWS-managed |
| EKS to Bedrock | TLS 1.2 | AWS-managed |
| Inter-service (EKS) | mTLS | Service mesh certificates |

#### TLS Configuration

```
Supported Cipher Suites (TLS 1.3):
- TLS_AES_256_GCM_SHA384
- TLS_AES_128_GCM_SHA256
- TLS_CHACHA20_POLY1305_SHA256

Supported Cipher Suites (TLS 1.2):
- ECDHE-RSA-AES256-GCM-SHA384
- ECDHE-RSA-AES128-GCM-SHA256
```

#### FIPS 140-2 Compliance

For GovCloud deployments, FIPS 140-2 validated cryptographic modules are used:

- AWS FIPS endpoints enabled
- OpenSSL FIPS provider active
- SSH using FIPS-approved ciphers only

See [GovCloud Guide](./govcloud-guide.md) for FIPS configuration details.

---

## Data Retention

### Default Retention Policies

| Data Category | Production | Development/QA | Compliance Minimum |
|---------------|------------|----------------|-------------------|
| Audit Logs | 365 days | 90 days | 365 days (SOX: 7 years) |
| VPC Flow Logs | 365 days | 90 days | 365 days |
| Application Logs | 90 days | 30 days | 90 days |
| Vulnerability Data | 1 year | 90 days | 1 year |
| Patch History | 1 year | 90 days | 1 year |
| User Sessions | 30 days | 7 days | 30 days |
| LLM Interactions | 90 days | 30 days | 90 days |
| Telemetry | 90 days | 30 days | N/A |

### Extended Retention Options

For compliance requirements exceeding default retention:

| Retention Period | Use Case | Storage Tier | Additional Cost |
|------------------|----------|--------------|-----------------|
| 1 year | Standard compliance | S3 Standard | Included |
| 3 years | CMMC, FedRAMP | S3 Intelligent-Tiering | +15% |
| 7 years | SOX, financial | S3 Glacier | +5% |
| 10 years | Legal hold | S3 Glacier Deep Archive | +2% |

Configure extended retention in Organization Settings or contact your account representative.

### Data Lifecycle Management

```
+----------+     +----------+     +----------+     +----------+
|  ACTIVE  | --> |  WARM    | --> |  COLD    | --> |  DELETE  |
| (0-90d)  |     | (90-365d)|     | (365d+)  |     | (policy) |
+----------+     +----------+     +----------+     +----------+
| S3 Std   |     | S3 IA    |     | Glacier  |     | Permanent|
| Full API |     | API      |     | Restore  |     | Removal  |
+----------+     +----------+     +----------+     +----------+
```

---

## Data Residency

### Supported Regions

| Region | Environment | Data Residency | Compliance |
|--------|-------------|----------------|------------|
| us-east-1 (N. Virginia) | Production | United States | Commercial |
| us-west-2 (Oregon) | DR/Backup | United States | Commercial |
| us-gov-west-1 | GovCloud Production | United States | FedRAMP, CMMC |
| us-gov-east-1 | GovCloud DR | United States | FedRAMP, CMMC |
| eu-west-1 (Ireland) | EU Production | European Union | GDPR |
| eu-central-1 (Frankfurt) | EU DR | European Union | GDPR |

### Data Sovereignty

Project Aura enforces strict data residency controls:

**US Commercial:**
- All data stored in US AWS regions
- Bedrock LLM processing in us-east-1 or us-west-2
- No data transfer outside selected regions

**US GovCloud:**
- All data stored in GovCloud partition
- Bedrock available in us-gov-west-1
- ITAR-compliant data handling
- US persons access only

**European Union:**
- All data stored in EU AWS regions
- Compliant with GDPR data residency requirements
- Standard Contractual Clauses available

### Cross-Region Data Transfer

| Transfer Type | Allowed | Encryption | Justification |
|---------------|---------|------------|---------------|
| Backup replication | Yes | TLS + KMS | Disaster recovery |
| Log aggregation | Configurable | TLS + KMS | Compliance monitoring |
| User data sync | No | N/A | Data residency |
| LLM processing | Same region | TLS + KMS | Data sovereignty |

---

## Data Access Controls

### Access Control Model

Project Aura implements role-based access control (RBAC) with least-privilege principles.

| Role | Source Code Access | Vulnerability Access | Patch Access | Audit Access |
|------|-------------------|---------------------|--------------|--------------|
| Organization Admin | Full | Full | Full | Full |
| Security Admin | Read-only | Full | Full | Full |
| Security Analyst | Read-only | Read | Read | Read |
| Developer | Assigned repos | Assigned repos | Assigned repos | Own actions |
| Auditor | None | Read | Read | Full |
| API Service | Scoped by key | Scoped by key | Scoped by key | None |

### Data Access Logging

All data access is logged with the following attributes:

```json
{
  "timestamp": "2026-01-23T12:00:00Z",
  "event_type": "data.access",
  "actor": {
    "user_id": "user-12345",
    "email": "security@customer.com",
    "ip_address": "203.0.113.50",
    "user_agent": "Mozilla/5.0..."
  },
  "resource": {
    "type": "source_code",
    "repository": "acme/web-app",
    "file": "src/auth/login.py"
  },
  "action": "read",
  "context": {
    "organization_id": "org-xyz789",
    "request_id": "req-abc123"
  }
}
```

---

## Data Privacy

### Personal Data Handling

Project Aura processes limited personal data as part of platform operation:

| Data Element | Purpose | Legal Basis | Retention |
|--------------|---------|-------------|-----------|
| Email address | Account identification | Contract | Account lifetime |
| Name | Display in UI | Contract | Account lifetime |
| IP address | Security logging | Legitimate interest | 90 days |
| Browser metadata | Security, compatibility | Legitimate interest | 90 days |
| API keys | Authentication | Contract | Until revoked |

### GDPR Compliance

For EU customers, Project Aura supports GDPR requirements:

**Data Subject Rights:**
- **Right to Access:** Export all personal data via API
- **Right to Rectification:** Update account information
- **Right to Erasure:** Account deletion request
- **Right to Portability:** Export data in machine-readable format
- **Right to Object:** Opt out of non-essential processing

**Data Processing Agreement (DPA):**
Available for all customers. Contact legal@aenealabs.com to request.

### Data Minimization

Project Aura follows data minimization principles:

- Only collect data necessary for service operation
- Anonymize or pseudonymize where possible
- Automatic deletion after retention period
- No selling or sharing of customer data

---

## Data Deletion

### Right to Deletion

Customers can request deletion of their data at any time.

#### Deletion Scope

| Data Category | Deletion Timeframe | Method |
|---------------|-------------------|--------|
| Source code | Immediate | Permanent deletion |
| Code metadata (graph) | 24 hours | Graph purge |
| Vector embeddings | 24 hours | Index deletion |
| Vulnerability records | 24 hours | Database deletion |
| Patch history | 24 hours | Database deletion |
| Audit logs | 30 days | Archive, then delete |
| Backups | 30-90 days | Lifecycle expiration |

#### Deletion Process

1. **Request:** Submit deletion request via Settings > Data Management
2. **Confirmation:** Receive confirmation email with deletion scope
3. **Execution:** Data deletion begins within 24 hours
4. **Verification:** Receive deletion confirmation within 7 days
5. **Backup Purge:** Backups expire per lifecycle policy (30-90 days)

### Data Export

Before deletion, customers can export their data:

**Export Formats:**
- Source code analysis: JSON, CSV
- Vulnerability data: SARIF, JSON, CSV
- Patch history: JSON with diffs
- Audit logs: JSON, CSV

**Export Process:**
1. Navigate to Settings > Data Management > Export
2. Select data categories
3. Choose format
4. Download within 24 hours (link expires)

### Account Closure

Upon account closure:

1. All active services terminated
2. Data export available for 30 days
3. User data deleted after 30 days
4. Audit logs retained per compliance requirements
5. Backups expire per lifecycle policy

---

## Third-Party Data Processing

### Sub-Processors

Project Aura uses the following sub-processors:

| Sub-Processor | Purpose | Data Processed | Location |
|---------------|---------|----------------|----------|
| Amazon Web Services | Infrastructure hosting | All data | US, EU, GovCloud |
| Anthropic (via Bedrock) | LLM processing | Code snippets, prompts | US |
| Datadog | Application monitoring | Telemetry (no PII) | US |
| Stripe | Payment processing | Billing data | US, EU |

### Sub-Processor Changes

Customers are notified 30 days before new sub-processor additions. Notification sent to organization admin email.

### Data Processing Agreements

DPAs are in place with all sub-processors. Copies available upon request.

---

## Security Controls Summary

### Data Protection Controls

| Control | Implementation | Compliance Mapping |
|---------|----------------|-------------------|
| Encryption at rest | AES-256, KMS CMK | SC-28, CMMC 3.13.16 |
| Encryption in transit | TLS 1.3/1.2 | SC-8, CMMC 3.13.8 |
| Key management | AWS KMS, automatic rotation | SC-12, CMMC 3.13.10 |
| Access control | RBAC, least privilege | AC-3, CMMC 3.1.5 |
| Access logging | CloudTrail, application logs | AU-2, CMMC 3.3.1 |
| Data isolation | VPC, subnet separation | SC-7, CMMC 3.13.1 |
| Backup encryption | KMS, cross-region | CP-9, CMMC 3.8.9 |

### Data Handling Checklist

For enterprise deployment, verify the following:

- [ ] KMS keys created in target region
- [ ] Encryption enabled for all data stores
- [ ] Retention policies configured
- [ ] Data residency region confirmed
- [ ] Access logging enabled
- [ ] DPA signed (if required)
- [ ] Sub-processor list reviewed

---

## Related Documentation

- [Security & Compliance Overview](./index.md)
- [Compliance Certifications](./compliance-certifications.md)
- [Audit Logging](./audit-logging.md)
- [GovCloud Guide](./govcloud-guide.md)
- [Security Architecture](../../support/architecture/security-architecture.md)

---

*Last updated: January 2026 | Version 1.0*
