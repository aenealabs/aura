# Incident Response Playbooks

This directory contains incident response playbooks for Project Aura security incidents.

## Playbook Index

| ID | Incident Type | Severity | Status |
|----|---------------|----------|--------|
| [IR-001](./IR-001-PROMPT-INJECTION.md) | Prompt Injection Attack | Critical/High | Active |
| [IR-002](./IR-002-GRAPHRAG-POISONING.md) | GraphRAG Context Poisoning | High | Active |
| [IR-003](./IR-003-CREDENTIAL-EXPOSURE.md) | Credential Exposure | Critical | Active |
| [IR-004](./IR-004-SANDBOX-ESCAPE.md) | Sandbox Escape Attempt | Critical | Active |
| [IR-005](./IR-005-DATA-LEAKAGE-LLM.md) | Data Leakage via LLM | High | Active |

## Tabletop Exercises

| Document | Description | Frequency |
|----------|-------------|-----------|
| [TABLETOP-EXERCISE.md](./TABLETOP-EXERCISE.md) | Structured exercises for playbook validation | Quarterly |

## Quick Start

1. **Identify** the incident type from alerts
2. **Open** the corresponding playbook
3. **Follow** the step-by-step procedures
4. **Escalate** per the severity matrix
5. **Document** actions in incident report

## Escalation Contacts

| Role | Contact |
|------|---------|
| On-Call Engineer | PagerDuty: `aura-oncall` |
| Security Lead | security@aenealabs.com |
| CTO | cto@aenealabs.com |

## Related Documentation

- [Security Services Overview](../../security/SECURITY_SERVICES_OVERVIEW.md)
- [CMMC Certification Pathway](../../security/CMMC_CERTIFICATION_PATHWAY.md)
- [Compliance Profiles](../../security/COMPLIANCE_PROFILES.md)

## Compliance

These playbooks support:
- **CMMC:** IR.2.092, IR.2.093, IR.3.098
- **NIST 800-53:** IR-4, IR-5, IR-6, IR-8
- **NIST 800-61:** Computer Security Incident Handling Guide
