# Government Compliance Certification Roadmaps

## Project Aura - Autonomous AI SaaS Platform

**Last Updated:** January 2, 2026
**Document Status:** Planning Reference

---

## Overview

This directory contains comprehensive certification roadmaps for pursuing government and defense sector compliance certifications. These roadmaps are designed for a solo founder context and provide realistic timelines, costs, and implementation guidance.

### Current Project State

| Metric | Status |
|--------|--------|
| Overall Completion | 99% |
| Infrastructure Security | 100% GovCloud-ready (19/19 services) |
| Security Services | 100% Deployed (5 Python services, 328 tests) |
| Test Coverage | 20,800+ tests (14,200+ passed, 6,600 skipped, 0 failed) |
| Lines of Code | 397,000+ |
| CMMC Level 2 Progress | ~50-60% (infrastructure strong, organizational controls pending) |

### Infrastructure Already Deployed

- AWS GovCloud compatible architecture (partition-aware ARNs)
- KMS encryption with rotation for all data stores
- VPC Flow Logs (365-day retention)
- AWS WAF (6 security rules)
- CloudTrail audit logging
- GuardDuty threat detection
- AWS Config compliance rules
- 7 CloudWatch security alarms
- EventBridge security event bus
- SNS security alert topic
- IAM least-privilege policies (no wildcards)

### Critical Organizational Gaps

| Domain | Gap | Priority |
|--------|-----|----------|
| AT | Security awareness training program | High |
| IR | Incident response playbook and SOC | Critical |
| PS | Personnel background check process | Medium |
| RA | Formal risk assessment program | High |
| CA | Penetration testing program | High |

---

## Certification Hierarchy

Understanding the relationships between certifications is critical for strategic planning:

```
                    +------------------+
                    |   CMMC Level 1   |
                    | (17 FAR practices)|
                    +--------+---------+
                             |
                    +--------v---------+
                    |   CMMC Level 2   |
                    | (110 NIST 800-171)|
                    +--------+---------+
                             |
                    +--------v---------+
                    |   CMMC Level 3   |
                    | (+24 NIST 800-172)|
                    +------------------+

+------------------+         +------------------+
|  FedRAMP Moderate|         |   FedRAMP High   |
| (325 controls)   |-------->| (421 controls)   |
+------------------+         +--------+---------+
                                      |
                             +--------v---------+
                             |     DoD IL5      |
                             | (FedRAMP High +  |
                             |  Delta controls) |
                             +------------------+
```

### Certification Relationships

| Certification | Prerequisites | Enables | Market Access |
|---------------|---------------|---------|---------------|
| CMMC Level 1 | None | Basic DoD contracts | FCI contracts |
| CMMC Level 2 | None | CUI contracts | Most DoD contracts |
| CMMC Level 3 | Level 2 | Critical programs | High-value DoD |
| FedRAMP Moderate | None | Most federal agencies | Civilian federal |
| FedRAMP High | None | High-impact systems | All federal |
| DoD IL5 | FedRAMP High | DoD mission systems | Sensitive DoD |

---

## Roadmap Documents

### 1. CMMC Level 2 Certification Roadmap

**File:** [CMMC_LEVEL_2_ROADMAP.md](./CMMC_LEVEL_2_ROADMAP.md)

**Summary:** Comprehensive roadmap for achieving CMMC Level 2 certification, required for defense contractors handling Controlled Unclassified Information (CUI).

| Attribute | Value |
|-----------|-------|
| Timeline | 8-12 months |
| Investment | $200,000-350,000 (first year) |
| Annual Recurring | $65,000-140,000 |
| Current Progress | ~50-60% |
| Assessment | C3PAO (third-party) |
| Certification Validity | 3 years |

**Key Milestones:**
- Gap analysis and planning (Months 1-2)
- Access control and authentication (Months 3-4)
- Audit, logging, incident response (Months 5-6)
- System hardening, communications (Months 7-8)
- Risk assessment, security testing (Months 9-10)
- Documentation, training, pre-assessment (Month 11)
- C3PAO assessment (Month 12)

---

### 2. CMMC Level 3 Certification Roadmap

**File:** [CMMC_LEVEL_3_ROADMAP.md](./CMMC_LEVEL_3_ROADMAP.md)

**Summary:** Advanced roadmap for CMMC Level 3 certification, required for the most sensitive CUI programs. Builds upon Level 2 with 24 enhanced controls from NIST SP 800-172.

| Attribute | Value |
|-----------|-------|
| Prerequisite | CMMC Level 2 certification |
| Timeline | 6-12 months after Level 2 |
| Investment | $400,000-650,000 (incremental) |
| Annual Recurring | $260,000-610,000 |
| Assessment | C3PAO + Government validation |

**Key Capabilities Required:**
- Dynamic risk-based access control
- Micro-segmentation
- Insider threat program
- Cyber threat intelligence
- Security operations center (24/7)
- Threat hunting
- Adversary emulation (purple team)
- Software Bill of Materials (SBOM)

---

### 3. FedRAMP High Authorization Roadmap

**File:** [FEDRAMP_HIGH_ROADMAP.md](./FEDRAMP_HIGH_ROADMAP.md)

**Summary:** Comprehensive roadmap for achieving FedRAMP High authorization, enabling deployment to federal agencies processing high-impact data.

| Attribute | Value |
|-----------|-------|
| Timeline | 9-14 months |
| Investment | $250,000-350,000 (first year) |
| Annual Recurring | $77,000-155,000 |
| Control Baseline | 421 NIST 800-53 Rev 5 controls |
| Assessment | 3PAO (third-party) |
| Authorization | Agency or JAB |

**Key Phases:**
- Gap analysis and documentation (Months 1-3)
- SSP development and policy creation (Months 3-6)
- 3PAO readiness assessment (Months 5-7)
- Control implementation and remediation (Months 6-9)
- Full 3PAO assessment (Months 9-11)
- Agency/JAB authorization (Months 11-14)

---

### 4. DoD IL5 Authorization Roadmap

**File:** [IL5_CERTIFICATION_ROADMAP.md](./IL5_CERTIFICATION_ROADMAP.md)

**Summary:** Roadmap for DoD Impact Level 5 authorization, enabling deployment for sensitive DoD mission systems.

| Attribute | Value |
|-----------|-------|
| Prerequisite | FedRAMP High authorization |
| Timeline | 2-4 months after FedRAMP High |
| Investment | $100,000-200,000 (incremental) |
| Annual Recurring | $45,000-103,000 |
| Authorization | DISA |

**Key Requirements:**
- STIG compliance (all systems)
- FIPS 140-2/3 cryptographic validation
- DISA Cloud Access Point (CAP) connectivity
- CAC/PIV authentication support
- DoD-specific incident reporting

---

## Recommended Certification Order

### For DoD/Defense Contractor Market (Primary Strategy)

| Order | Certification | Timeline | Cumulative Investment |
|-------|---------------|----------|----------------------|
| 1 | CMMC Level 2 | Months 1-12 | $200,000-350,000 |
| 2 | FedRAMP High | Months 8-22 | $450,000-700,000 |
| 3 | IL5 | Months 20-26 | $550,000-900,000 |
| 4 | CMMC Level 3 | Months 24-36 | $950,000-1,550,000 |

**Rationale:**
1. **CMMC Level 2 first:** Fastest path to defense contractor market, enables subcontracting immediately
2. **FedRAMP High next:** Opens federal civilian market while preparing infrastructure for IL5
3. **IL5 after FedRAMP:** Minimal incremental effort, maximum DoD market access
4. **CMMC Level 3 last:** Most expensive, only pursue when specific critical contracts require it

### For Federal Civilian Market (Alternative Strategy)

| Order | Certification | Timeline | Cumulative Investment |
|-------|---------------|----------|----------------------|
| 1 | FedRAMP High | Months 1-14 | $250,000-350,000 |
| 2 | CMMC Level 2 | Months 12-24 | $450,000-700,000 |
| 3 | IL5 | Months 14-18 | $350,000-550,000 |

**Rationale:** If civilian federal agencies are primary target, FedRAMP High provides broadest market access. Add CMMC Level 2 when defense opportunities arise.

---

## Combined Investment Summary

### Total Investment by Scenario

| Scenario | Year 1 | Year 2 | Year 3 | 3-Year Total |
|----------|--------|--------|--------|--------------|
| CMMC L2 Only | $200K-350K | $65K-140K | $65K-140K | $330K-630K |
| FedRAMP High Only | $250K-350K | $77K-155K | $77K-155K | $404K-660K |
| CMMC L2 + FedRAMP | $450K-700K | $142K-295K | $142K-295K | $734K-1,290K |
| Full DoD Stack* | $550K-900K | $382K-758K | $382K-758K | $1,314K-2,416K |

*Full DoD Stack = CMMC L2 + L3 + FedRAMP High + IL5

### Annual Recurring Summary

| Certification | Annual Recurring (Low) | Annual Recurring (High) |
|---------------|------------------------|-------------------------|
| CMMC Level 2 | $65,000 | $140,000 |
| CMMC Level 3 | $260,000 | $610,000 |
| FedRAMP High | $77,000 | $155,000 |
| IL5 | $45,000 | $103,000 |
| **Combined (All)** | **$447,000** | **$1,008,000** |

---

## Contract Value Thresholds

### Break-Even Analysis

| Certification | Minimum Contract Value | Rationale |
|---------------|----------------------|-----------|
| CMMC Level 2 | $500,000/year | 40% margin covers $200K investment |
| FedRAMP High | $700,000/year | 35% margin covers $250K investment |
| CMMC L2 + FedRAMP | $1,200,000/year | Combined baseline |
| Full DoD Stack | $2,500,000/year | Premium positioning |

### Market Opportunity by Certification

| Certification | Addressable Market | Competition Level |
|---------------|-------------------|-------------------|
| CMMC Level 1 | $5B+ (basic FCI) | High |
| CMMC Level 2 | $50B+ (CUI contracts) | Medium-High |
| CMMC Level 3 | $10B+ (critical programs) | Low |
| FedRAMP High | $100B+ (federal IT) | Medium |
| IL5 | $20B+ (DoD mission) | Low |

---

## Quick Reference: Which Certification to Pursue

### Decision Matrix

| If Your Primary Target Is... | Start With | Add Later |
|------------------------------|------------|-----------|
| Defense subcontracting | CMMC Level 2 | FedRAMP High |
| Federal civilian agencies | FedRAMP High | CMMC Level 2 |
| DoD mission systems | FedRAMP High + IL5 | CMMC Level 2 |
| Critical defense programs | CMMC Level 2 | Level 3 |
| Maximum market access | CMMC Level 2 | FedRAMP High + IL5 |
| Cost-conscious start | CMMC Level 2 | Expand based on opportunity |

### Contract Type Requirements

| Contract Type | Minimum Certification |
|---------------|----------------------|
| Basic DoD (no CUI) | CMMC Level 1 (self-attest) |
| DoD with CUI | CMMC Level 2 |
| Critical DoD programs | CMMC Level 3 |
| Civilian federal (High) | FedRAMP High |
| DoD cloud/SaaS (sensitive) | FedRAMP High + IL5 |
| Intelligence adjacent | FedRAMP High + IL5 + CMMC L3 |

---

## Getting Started

### Immediate Next Steps

1. **Review Current State:** Validate ~50-60% CMMC Level 2 estimate with self-assessment
2. **Budget Planning:** Allocate initial budget for first certification
3. **Consultant Engagement:** Engage CMMC RP or FedRAMP specialist
4. **Tool Procurement:** Begin SIEM, EDR, training platform evaluation
5. **Gap Remediation:** Start addressing AT, IR, RA, CA domain gaps

### Recommended Reading Order

1. Start with the roadmap matching your primary market
2. Review shared dependencies (training, incident response, MDR)
3. Plan for certification overlap to maximize efficiency

### Resource Contacts

- CMMC-AB Marketplace: https://cyberab.org/Marketplace
- FedRAMP Marketplace: https://marketplace.fedramp.gov
- NIST Publications: https://csrc.nist.gov/publications
- DISA STIGs: https://public.cyber.mil/stigs/

---

## Document Maintenance

These roadmaps should be reviewed and updated:
- **Quarterly:** Timeline and cost estimates
- **Upon regulatory changes:** CMMC rule updates, FedRAMP changes
- **Post-certification:** Lessons learned, actual vs. estimated costs
- **Annually:** Full refresh of market analysis and strategy

---

*Documents maintained by Aenea Labs. For questions, contact the compliance team.*
