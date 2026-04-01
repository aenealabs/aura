# CMMC Certification Pathway for Project Aura
## Complete Roadmap from Design to Certification

**Version:** 2.0
**Last Updated:** December 2025
**Status:** Implementation Roadmap
**Owner:** Security & Compliance Team

---

## Executive Summary

**Goal:** Achieve **CMMC Level 3 certification** within 18-24 months to unlock $5.2B defense contractor market.

**Strategy:** Progressive certification (L1 → L2 → L3) with parallel infrastructure hardening and documentation.

**Investment Required:** $1.2-2.5M (depending on starting maturity)

**Timeline:**
- CMMC Level 1: 3-6 months (self-assessment)
- CMMC Level 2: 12-18 months (C3PAO assessment)
- CMMC Level 3: 18-24 months (C3PAO + Government validation)

**Market Impact:**
- Level 2: Access to 60% of DoD contracts
- Level 3: Access to 100% including CUI and classified programs

---

## CMMC 2.0 Overview

### What is CMMC?

**Cybersecurity Maturity Model Certification (CMMC)** is a DoD framework that standardizes cybersecurity requirements across the Defense Industrial Base (DIB).

**Mandate:** All DoD contractors must achieve CMMC certification by December 2026 or lose contract eligibility.

### CMMC Levels

| Level | Security Controls | Assessment Type | DoD Contract Coverage | Aura's Target Date |
|-------|-------------------|-----------------|----------------------|-------------------|
| **Level 1** | 17 practices (FAR 52.204-21) | Self-assessment | Federal Contract Information (FCI) | Month 3 ✅ |
| **Level 2** | 110 practices (NIST SP 800-171) | C3PAO assessment | Controlled Unclassified Information (CUI) | Month 12 🎯 |
| **Level 3** | 110 + 24 enhanced (NIST SP 800-172) | C3PAO + Gov validation | CUI + Classified programs | Month 18-24 🎯 |

### CMMC 2.0 Timeline (DoD Mandate)

```
Nov 2024: CMMC 2.0 Final Rule published (Federal Register)
Dec 2024: Phased rollout begins
Mar 2025: Level 1 requirements in new RFPs
Sep 2025: Level 2 requirements in new RFPs
Dec 2025: Level 1 mandatory for all DoD contractors
Jun 2026: Level 2 mandatory (60% of contracts)
Dec 2026: Level 3 mandatory (25% of contracts)
```

**Aura's Market Window:** Companies racing to certify before deadlines = high-urgency sales cycle.

---

## CMMC Level 1: Foundation (Months 1-3)

### Scope: 17 Basic Safeguarding Requirements

**Focus:** Basic cyber hygiene (FAR 52.204-21 compliance)

**Assessment:** Self-assessment (no third-party auditor required)

**Cost:** $10-25K (internal effort + tooling)

### Domain Coverage

| Domain | Practices | Aura Implementation Status |
|--------|-----------|----------------------------|
| **Access Control (AC)** | 3 | ✅ IAM roles, MFA enforced |
| **Identification & Authentication (IA)** | 2 | ✅ SSO + MFA via AWS IAM |
| **Media Protection (MP)** | 2 | ✅ EBS encryption, S3 versioning |
| **Physical Protection (PE)** | 1 | ✅ AWS data centers (inherited) |
| **System & Communications (SC)** | 2 | ✅ VPC isolation, TLS 1.3 |
| **System & Information Integrity (SI)** | 7 | 🔶 Needs SIEM + vulnerability scanning |

### Implementation Checklist

#### Week 1-2: Access Control
- [x] Implement user access controls (AWS IAM)
- [x] Enforce Multi-Factor Authentication (MFA) for all users
- [x] Define least-privilege access policies
- [ ] Document access control procedures in SSP

#### Week 3-4: System Protection
- [x] Enable encryption at rest (DynamoDB, S3, EBS)
- [x] Enable encryption in transit (TLS 1.3)
- [ ] Implement vulnerability scanning (AWS Inspector)
- [ ] Deploy SIEM solution (CloudWatch Logs Insights or Splunk)

#### Week 5-6: Media & Physical Protection
- [x] Implement secure media disposal policy
- [x] Use AWS GovCloud (FedRAMP Moderate baseline)
- [ ] Document data classification policy
- [ ] Sanitization procedures for decommissioned storage

#### Week 7-8: System Integrity
- [ ] Deploy malware protection (AWS GuardDuty)
- [ ] Implement security event logging (CloudTrail)
- [ ] Configure automated security alerts
- [ ] Conduct initial vulnerability scan

#### Week 9-12: Documentation & Self-Assessment
- [ ] Complete System Security Plan (SSP) - Level 1
- [ ] Document security policies and procedures
- [ ] Conduct internal gap assessment
- [ ] Submit self-attestation to DoD (via SPRS)

### Tools & Technology

| Requirement | AWS Service | Cost |
|-------------|-------------|------|
| Access Control | IAM, SSO | Free |
| Encryption | KMS, TLS | $1/key/month |
| Logging | CloudTrail, CloudWatch | $0.50/GB |
| Vulnerability Scanning | Inspector | $0.30/agent/month |
| Threat Detection | GuardDuty | $4.60/M events |

**Total Level 1 Cost:** $500-1,000/month (ongoing)

---

## CMMC Level 2: Production Ready (Months 4-12)

### Scope: 110 NIST SP 800-171 Controls

**Focus:** Protecting Controlled Unclassified Information (CUI)

**Assessment:** Third-party C3PAO (CMMC Third-Party Assessment Organization)

**Cost:** $75-150K (external assessment) + $300-600K (remediation + tooling)

### 14 NIST SP 800-171 Domains

| Domain | Controls | Aura Status | Priority |
|--------|----------|-------------|----------|
| **Access Control (AC)** | 22 | 🔶 Partial | High |
| **Awareness & Training (AT)** | 5 | ❌ Missing | Medium |
| **Audit & Accountability (AU)** | 9 | 🔶 Partial | High |
| **Configuration Management (CM)** | 9 | ✅ Complete | Low |
| **Identification & Authentication (IA)** | 11 | 🔶 Partial | High |
| **Incident Response (IR)** | 6 | ❌ Missing | High |
| **Maintenance (MA)** | 6 | ✅ Complete | Low |
| **Media Protection (MP)** | 9 | 🔶 Partial | Medium |
| **Personnel Security (PS)** | 2 | ❌ Missing | Medium |
| **Physical Protection (PE)** | 6 | ✅ AWS Inherited | Low |
| **Risk Assessment (RA)** | 6 | ❌ Missing | High |
| **Security Assessment (CA)** | 9 | ❌ Missing | High |
| **System & Communications (SC)** | 20 | 🔶 Partial | High |
| **System & Information Integrity (SI)** | 17 | 🔶 Partial | High |

### Month-by-Month Implementation Plan

#### **Month 4: Gap Analysis & Roadmap**

**Activities:**
- Hire CMMC consultant (Coalfire, Kratos, CYMPLE)
- Conduct formal NIST 800-171 gap assessment
- Prioritize remediation backlog (High/Medium/Low)
- Define System Security Plan (SSP) scope

**Deliverables:**
- Gap assessment report (110 controls)
- Remediation roadmap with cost estimates
- SSP template (NIST 800-171 compliant)

**Cost:** $25-50K (consultant fees)

---

#### **Month 5-6: Access Control & Authentication**

**AC-1 to AC-22 Implementation:**

| Control | Requirement | Aura Implementation |
|---------|-------------|---------------------|
| **AC-2** | Account Management | ✅ AWS IAM + SSO (Okta/Azure AD) |
| **AC-3** | Access Enforcement | ✅ Least privilege IAM policies |
| **AC-7** | Unsuccessful Login Attempts | 🔶 Add: Failed login lockout (5 attempts) |
| **AC-17** | Remote Access | 🔶 Add: VPN + session recording |
| **AC-19** | Access Control for Mobile Devices | 🔶 Add: MDM (Intune/Jamf) |
| **AC-20** | External System Connections | ❌ Add: Third-party connection approval workflow |

**IA-1 to IA-11 Implementation:**

| Control | Requirement | Aura Implementation |
|---------|-------------|---------------------|
| **IA-2** | Multi-Factor Authentication | ✅ MFA enforced (Okta/AWS) |
| **IA-5** | Authenticator Management | 🔶 Add: Password complexity (14 chars, 90-day rotation) |
| **IA-8** | Identification for Non-Org Users | ❌ Add: Contractor identity vetting |

**Tools to Deploy:**
- **VPN:** AWS Client VPN or Tailscale
- **MDM:** Microsoft Intune (Azure Gov) or Jamf (Apple devices)
- **Session Recording:** Teleport or AWS Session Manager

**Cost:** $50-100K (tooling + integration)

---

#### **Month 7-8: Audit, Logging, & Incident Response**

**AU-1 to AU-9 Implementation:**

| Control | Requirement | Aura Implementation |
|---------|-------------|---------------------|
| **AU-2** | Auditable Events | ✅ CloudTrail (all API calls) |
| **AU-3** | Content of Audit Records | ✅ Who/What/When/Where logged |
| **AU-6** | Audit Review | ❌ Add: Weekly log review + anomaly detection |
| **AU-9** | Protection of Audit Information | 🔶 Add: Write-once S3 (Object Lock) |

**IR-1 to IR-6 Implementation:**

| Control | Requirement | Aura Implementation |
|---------|-------------|---------------------|
| **IR-1** | Incident Response Policy | ❌ Create: IR playbook (phishing, breach, DDoS) |
| **IR-4** | Incident Handling | ❌ Create: 24/7 SOC or MSSP contract |
| **IR-5** | Incident Monitoring | 🔶 Add: SIEM alerts (Splunk/Datadog) |
| **IR-6** | Incident Reporting | ❌ Create: DoD DIBNET reporting procedures |

**Tools to Deploy:**
- **SIEM:** Splunk Cloud (FedRAMP), Datadog Security, or AWS Security Hub
- **SOC/MSSP:** a managed SOC provider
- **Write-Once Logging:** S3 Object Lock + Glacier

**Cost:** $100-200K/year (SIEM + SOC)

---

#### **Month 9-10: System Hardening & Communications Protection**

**SC-1 to SC-20 Implementation:**

| Control | Requirement | Aura Implementation |
|---------|-------------|---------------------|
| **SC-7** | Boundary Protection | ✅ VPC + Security Groups + NACLs |
| **SC-8** | Transmission Confidentiality | ✅ TLS 1.3 (all APIs) |
| **SC-12** | Cryptographic Key Management | ✅ AWS KMS (FIPS 140-2 Level 3) |
| **SC-13** | Cryptographic Protection | ✅ AES-256 encryption |
| **SC-28** | Protection of Info at Rest | ✅ EBS/S3/DynamoDB encryption |

**SI-1 to SI-17 Implementation:**

| Control | Requirement | Aura Implementation |
|---------|-------------|---------------------|
| **SI-2** | Flaw Remediation | 🔶 Add: 30-day patch SLA (critical vulns) |
| **SI-3** | Malicious Code Protection | 🔶 Add: EDR (CrowdStrike/SentinelOne) |
| **SI-4** | Information System Monitoring | 🔶 Enhance: Real-time threat detection |
| **SI-7** | Software Integrity | ❌ Add: Code signing + SBOM |
| **SI-10** | Information Input Validation | ✅ Already implemented (InputSanitizer) |

**Tools to Deploy:**
- **EDR:** CrowdStrike Falcon (FedRAMP) or SentinelOne
- **Patch Management:** AWS Systems Manager (SSM) Patch Manager
- **Code Signing:** AWS Signer + Notary

**Cost:** $50-80K/year (EDR + patch automation)

---

#### **Month 11: Risk Assessment & Security Testing**

**RA-1 to RA-6 Implementation:**

| Control | Requirement | Aura Implementation |
|---------|-------------|---------------------|
| **RA-3** | Risk Assessment | ❌ Conduct: Annual risk assessment |
| **RA-5** | Vulnerability Scanning | 🔶 Add: Weekly vuln scans (Tenable/Qualys) |

**CA-1 to CA-9 Implementation:**

| Control | Requirement | Aura Implementation |
|---------|-------------|---------------------|
| **CA-2** | Security Assessments | ❌ Conduct: Annual penetration test |
| **CA-7** | Continuous Monitoring | 🔶 Add: Automated compliance dashboard |

**Activities:**
- Hire penetration testing firm (Mandiant, CrowdStrike, Bishop Fox)
- Deploy vulnerability scanner (Tenable.sc GovCloud or Qualys)
- Create continuous monitoring dashboard (AWS Security Hub)

**Cost:** $40-80K (pentest + scanning tools)

---

#### **Month 12: Documentation, Training, & Pre-Assessment**

**AT-1 to AT-5 Implementation:**

| Control | Requirement | Aura Implementation |
|---------|-------------|---------------------|
| **AT-2** | Security Awareness Training | ❌ Add: Annual training (KnowBe4/SANS) |
| **AT-3** | Role-Based Security Training | ❌ Add: Developer secure coding training |

**PS-1 to PS-2 Implementation:**

| Control | Requirement | Aura Implementation |
|---------|-------------|---------------------|
| **PS-3** | Personnel Screening | ❌ Add: Background checks (NBIS/Equifax) |

**Final Documentation:**
- [ ] Complete System Security Plan (SSP) - 200+ pages
- [ ] Plan of Action & Milestones (POA&M)
- [ ] Security Assessment Report (SAR)
- [ ] Rules of Behavior (ROB)
- [ ] Contingency Plan (CP)
- [ ] Incident Response Plan (IRP)

**Pre-Assessment:**
- [ ] Internal readiness assessment (mock audit)
- [ ] Remediate any Critical/High findings
- [ ] Schedule C3PAO assessment

**Cost:** $50-80K (training + documentation)

---

### C3PAO Assessment (Month 13-14)

**Process:**
1. **Pre-Engagement:** Select C3PAO (Coalfire, Kratos, CMAS)
2. **Scoping:** Define assessment boundaries
3. **On-Site Assessment:** 3-5 days (remote + on-site if applicable)
4. **Findings:** Receive draft assessment report
5. **Remediation:** Fix any non-compliances (30-60 days)
6. **Final Report:** C3PAO submits to CMMC-AB

**Timeline:** 8-12 weeks (end-to-end)

**Cost:** $75-150K (C3PAO fees)

**Outcome:** CMMC Level 2 Certificate (valid 3 years)

---

## CMMC Level 3: Advanced/Persistent Threat Protection (Months 15-24)

### Scope: 110 + 24 Enhanced Controls (NIST SP 800-172)

**Focus:** Advanced Persistent Threat (APT) protection for classified programs

**Assessment:** C3PAO + Government Validation

**Cost:** $400-800K (enhanced controls + assessment)

### Enhanced Security Domains

| Enhanced Domain | Additional Practices | Key Requirements |
|-----------------|---------------------|------------------|
| **Access Control** | 4 | Dynamic access control, attribute-based access |
| **Awareness & Training** | 1 | Red team/adversary tactics training |
| **Audit & Accountability** | 1 | Forensic analysis capability |
| **Configuration Management** | 2 | Supply chain risk management (SBOM) |
| **Identification & Authentication** | 2 | Biometric authentication options |
| **Incident Response** | 2 | Insider threat detection program |
| **Maintenance** | 1 | Controlled maintenance tools |
| **Media Protection** | 1 | Advanced data sanitization |
| **Physical Protection** | 1 | Advanced intrusion detection |
| **Risk Assessment** | 2 | Threat hunting, adversary emulation |
| **Security Assessment** | 3 | Red team exercises, purple team |
| **System & Communications** | 3 | Network isolation, deception capabilities |
| **System & Information Integrity** | 1 | Anti-tamper protections |

### Month 15-18: Enhanced Controls Implementation

#### **Enhanced Access Control (AC-L3)**

**AC.L3-3.1.1:** Dynamic Access Control
- **Implementation:** Implement attribute-based access control (ABAC)
- **Tools:** AWS Verified Permissions or Azure ABAC
- **Cost:** $30K integration

**AC.L3-3.1.2:** Network Segmentation
- **Implementation:** Micro-segmentation (zero trust network)
- **Tools:** AWS VPC + Transit Gateway or Illumio
- **Cost:** $50K architecture redesign

---

#### **Enhanced Incident Response (IR-L3)**

**IR.L3-3.6.1:** Insider Threat Program
- **Implementation:** Deploy User and Entity Behavior Analytics (UEBA)
- **Tools:** Splunk UBA or Microsoft Sentinel
- **Cost:** $80-120K/year

**IR.L3-3.6.2:** Cyber Threat Intelligence
- **Implementation:** Integrate threat intel feeds (CISA, FBI, DoD)
- **Tools:** Anomali ThreatStream or Recorded Future
- **Cost:** $60K/year

---

#### **Enhanced Risk Assessment (RA-L3)**

**RA.L3-3.11.1:** Threat Hunting
- **Implementation:** Dedicated threat hunting team or MSSP
- **Tools:** CrowdStrike Falcon OverWatch or Mandiant Advantage
- **Cost:** $150-250K/year

**RA.L3-3.11.2:** Adversary Emulation (Red Team)**
- **Implementation:** Quarterly red team exercises
- **Tools:** Mandiant, CrowdStrike, or internal red team
- **Cost:** $80-120K/year

---

#### **Enhanced Security Assessment (CA-L3)**

**CA.L3-3.12.1:** Purple Team Exercises
- **Implementation:** Combined red/blue team training
- **Cost:** $40-60K/year

**CA.L3-3.12.2:** Penetration Testing (Continuous)**
- **Implementation:** Continuous automated pentest platform
- **Tools:** Cobalt.io or HackerOne Pentesting
- **Cost:** $60-100K/year

---

### Month 19-22: Supply Chain Risk Management

**Critical for Software Platforms:**

**CM.L3-3.4.1:** Software Bill of Materials (SBOM)
- **Requirement:** Generate SBOM for all software components
- **Tools:** Syft, CycloneDX, SPDX
- **Integration:** Add to CI/CD pipeline
- **Cost:** $20K integration

**CM.L3-3.4.2:** Supply Chain Security Assessment
- **Requirement:** Vet all third-party dependencies
- **Tools:** Snyk, Sonatype Nexus, Black Duck
- **Cost:** $40-80K/year

**SR.L3-3.13.1:** Anti-Tamper Protections
- **Requirement:** Code signing, integrity verification
- **Tools:** AWS Signer, Sigstore
- **Cost:** $15K integration

---

### Month 23-24: C3PAO + Government Assessment

**Phase 1: C3PAO Assessment (Months 23-24)**
- Same process as Level 2
- Additional focus on enhanced controls
- Cost: $125-200K

**Phase 2: Government Validation (Month 24)**
- DCMA (Defense Contract Management Agency) review
- On-site inspection (if applicable)
- Final approval by DoD CIO
- Timeline: 60-90 days post-C3PAO

**Outcome:** CMMC Level 3 Certificate (valid 3 years)

---

## Cost Summary

### Total Investment by Level

| Level | Implementation | Assessment | Annual Ongoing | Timeline |
|-------|----------------|-----------|----------------|----------|
| **Level 1** | $20-40K | Self ($0) | $10-15K | 3 months |
| **Level 2** | $500-800K | $75-150K | $300-500K | 12 months |
| **Level 3** | $400-800K | $125-200K | $600-900K | 24 months |
| **TOTAL** | **$920K-1.64M** | **$200-350K** | **$910K-1.42M/year** | **24 months** |

### Cost Breakdown by Category

| Category | One-Time | Annual Recurring | Notes |
|----------|----------|------------------|-------|
| **Consulting** | $150-250K | $50-100K | Gap analysis, SSP writing, remediation support |
| **Tooling (Security)** | $100-200K | $400-600K | SIEM, EDR, vuln scanning, threat intel |
| **Tooling (Infrastructure)** | $50-100K | $100-200K | VPN, MDM, code signing |
| **Assessment Fees** | $200-350K | $75-150K | C3PAO assessments (every 3 years) |
| **Personnel** | - | $300-500K | Compliance manager + security engineer (2 FTEs) |
| **Training** | $30-50K | $50-80K | Security awareness, role-based training |

---

## Staffing Requirements

### Required Roles

| Role | Responsibility | FTE | Salary Range | When to Hire |
|------|----------------|-----|--------------|--------------|
| **CMMC Compliance Manager** | Owns certification roadmap, audits, POA&Ms | 1.0 | $120-180K | Month 3 |
| **Security Engineer** | Implements controls, hardens infrastructure | 1.0 | $130-200K | Month 4 |
| **DevSecOps Engineer** | CI/CD security, code scanning, SBOM | 0.5 | $140-220K | Month 6 |
| **SOC Analyst** (or MSSP) | 24/7 monitoring, incident response | 1.0 | $80-120K or $150K MSSP | Month 9 |
| **Penetration Tester** (contractor) | Quarterly pentests, red team | 0.2 | $200-300/hr | Month 11 |

**Total Personnel Cost:** $430-700K/year (or $300-500K with MSSP)

---

## Risk Mitigation

### Top Certification Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Timeline slips (18 → 30 months)** | Medium | High | Hire experienced consultant early, prioritize high-risk controls |
| **C3PAO findings require re-assessment** | Medium | Medium | Conduct mock audit 60 days before real assessment |
| **Budget overruns (50% cost increase)** | Medium | Medium | Build 30% contingency into budget |
| **Key personnel turnover** | Low | High | Cross-train team, document extensively |
| **DoD rule changes (CMMC 2.0 updates)** | Low | Medium | Stay engaged with CMMC-AB, flexible architecture |

---

## Accelerated Pathway (12 Months to Level 2)

**Aggressive Timeline:** If budget allows, compress to 12 months

### Fast-Track Approach

**Months 1-2: Rapid Assessment + Remediation Plan**
- Hire top-tier consultant (Coalfire, Kratos) for $100K
- Run parallel gap analysis + architecture design
- Pre-purchase all tooling (SIEM, EDR, etc.)

**Months 3-6: Parallel Implementation**
- Deploy 3-person team (compliance + 2 security engineers)
- Implement all 110 controls simultaneously (not sequentially)
- Weekly checkpoint with consultant

**Months 7-10: Testing + Documentation**
- Continuous security testing (weekly pentests)
- SSP writing in parallel with implementation
- Mock C3PAO assessment (Month 9)

**Months 11-12: C3PAO Assessment**
- Schedule assessment for Month 11
- Receive certification Month 12

**Additional Cost:** +$300-500K (premium for speed)

**Risk:** Higher chance of assessment failure (rushed implementation)

---

## Maintenance & Continuous Compliance

### Post-Certification Requirements

**Annual Activities:**
- [ ] Risk assessment update (RA-3)
- [ ] Penetration testing (CA-2)
- [ ] Security awareness training (AT-2)
- [ ] Policy/procedure review (all domains)

**Quarterly Activities:**
- [ ] Vulnerability scanning (RA-5)
- [ ] Log review and analysis (AU-6)
- [ ] Incident response tabletop exercise (IR-3)
- [ ] Access control review (AC-2)

**Monthly Activities:**
- [ ] Patch management (SI-2)
- [ ] Security monitoring review (SI-4)
- [ ] Backup testing (CP-9)

**Continuous:**
- [ ] CloudTrail logging (AU-2)
- [ ] SIEM monitoring (AU-6)
- [ ] Threat detection (SI-4)

**Re-Certification:** Every 3 years (C3PAO re-assessment)

---

## Integration with Product Roadmap

### How CMMC Enables Aura Features

| Aura Feature | CMMC Control | Compliance Benefit |
|--------------|--------------|-------------------|
| **Code Knowledge Graph (Neptune)** | SC-28 (encryption at rest) | CUI-approved data storage |
| **Autonomous Security Remediation** | SI-7 (software integrity) | Automated flaw remediation |
| **HITL Approval Workflow** | AC-3 (access enforcement) | Human authorization for prod changes |
| **Sandbox Testing** | SC-7 (boundary protection) | Isolated test environments |
| **Cost Tracking (DynamoDB)** | AU-2 (auditable events) | Financial audit trail |
| **Multi-Model LLM Service** | SC-12 (crypto key management) | Secure API key management |

**Key Insight:** Aura's architecture is **already CMMC-friendly** by design. Certification is about documentation + tooling, not fundamental redesign.

---

## Competitive Advantage

### CMMC as Market Differentiator

**[Competitor A] Status:**
- ✅ FedRAMP High
- ✅ IL5/IL6
- ❌ No public CMMC certification yet

**Aura's Opportunity:**
- 🎯 First autonomous code platform with CMMC Level 3
- 🎯 Target defense contractors (not just government)
- 🎯 Market window: 2025-2026 (before competitors catch up)

**Sales Message:**
> "Aura is the only CMMC Level 3 certified autonomous development platform, purpose-built for defense contractors who must comply with DoD cybersecurity requirements while accelerating software delivery."

---

## Next Steps

### Immediate Actions (Week 1-4)

1. **Hire CMMC Consultant** (RFP to Coalfire, Kratos, CMAS)
2. **Conduct Gap Analysis** (self-assessment against 110 controls)
3. **Build Business Case** (cost-benefit analysis for stakeholders)
4. **Allocate Budget** (plan for 24-month pathway)
5. **Hire Compliance Manager** (job posting + recruiting)

### Success Metrics

| Milestone | Target Date | Success Criteria |
|-----------|-------------|------------------|
| Gap analysis complete | Month 2 | <30% non-compliance rate |
| Level 1 self-assessment | Month 3 | 100% compliant (17/17 controls) |
| Level 2 POA&M | Month 6 | <10 High findings remaining |
| Mock C3PAO assessment | Month 10 | Zero Critical findings |
| Level 2 certification | Month 12 | Certificate issued |
| Level 3 certification | Month 24 | Certificate issued |

---

## Appendix: Key Resources

### CMMC Official Resources
- **CMMC-AB:** https://cyberab.org/ (Accreditation Body)
- **DoD CMMC:** https://dodcio.defense.gov/CMMC/
- **NIST SP 800-171:** https://csrc.nist.gov/publications/detail/sp/800-171/rev-2/final
- **NIST SP 800-172:** https://csrc.nist.gov/publications/detail/sp/800-172/final

### Recommended Consultants
- **Coalfire:** Top-tier, expensive ($250K+)
- **Kratos Defense:** Mid-tier, defense-focused ($150K+)
- **CMAS (Cyber MASA):** Cost-effective, remote ($100K+)

### Recommended C3PAOs
- **Coalfire Federal**
- **Kratos SecureInfo**
- **Redspin**
- **CMAS**

### Recommended Training
- **CMMC-AB CCP Training:** Certified CMMC Professional
- **SANS SEC511:** Continuous Monitoring and Security Operations
- **NIST 800-171 Bootcamp:** (various providers)

---

---

## AI Security Considerations for CMMC (November 2025 Update)

### AI-Specific Threats Requiring CMMC Controls

**Background:** The November 2025 threat landscape reveals increased state-sponsored AI-enabled attacks and critical vulnerabilities in AI infrastructure. Project Aura's AI SaaS architecture must address these threats within the CMMC framework.

### Mapping AI Threats to CMMC Controls

| AI Threat | CMMC Domain | Relevant Controls | Aura Implementation |
|-----------|-------------|-------------------|---------------------|
| **Prompt Injection** | SI (System Integrity) | SI-10 (Input Validation) | InputSanitizer, prompt templates |
| **Data Poisoning** | SI, RA | SI-7 (Software Integrity), RA-5 (Vuln Scanning) | Graph integrity audits, context validation |
| **Model Extraction** | SC (System & Comms) | SC-8 (Transmission Confidentiality) | TLS 1.3, Bedrock managed security |
| **Adversarial Inputs** | SI | SI-3 (Malicious Code), SI-4 (Monitoring) | Anomaly detection on LLM queries |
| **Insecure AI APIs** | AC, IA, SC | AC-3, IA-2, SC-7 | API auth, MFA, WAF rules |
| **AI-Generated Phishing** | AT | AT-2 (Security Awareness) | Enhanced training on AI threats |
| **Context Poisoning (GraphRAG)** | CM, SI | CM-3 (Config Control), SI-7 | Entity provenance, write validation |

### Additional CMMC Level 3 Requirements for AI Platforms

**Enhanced controls recommended for AI SaaS platforms:**

| Enhanced Control | CMMC L3 Mapping | AI-Specific Implementation |
|------------------|-----------------|----------------------------|
| **IR.L3-3.6.2 (Threat Intelligence)** | Incident Response | Subscribe to AI-specific threat feeds (CISA AI advisories) |
| **RA.L3-3.11.1 (Threat Hunting)** | Risk Assessment | Hunt for prompt injection attempts, context poisoning |
| **CA.L3-3.12.2 (Penetration Testing)** | Security Assessment | Include AI-specific red team scenarios |
| **CM.L3-3.4.1 (SBOM)** | Config Management | Document Bedrock model versions, AI dependencies |

### AI Incident Response Requirements

**Extend existing IR playbook (IR-4, IR-5, IR-6) with AI-specific scenarios:**

1. **Prompt Injection Incident**
   - Detection: Anomalous LLM responses, safety guardrail bypasses
   - Containment: Suspend affected user/API key, quarantine session
   - Eradication: Review and sanitize input pipelines
   - Recovery: Restore service with enhanced filtering

2. **GraphRAG Context Poisoning**
   - Detection: Integrity check failures, anomalous graph patterns
   - Containment: Isolate affected graph partition
   - Eradication: Remove malicious entities, restore from backup
   - Recovery: Re-index affected vectors, validate relationships

3. **Data Leakage via LLM**
   - Detection: PII/CUI patterns in LLM outputs, audit log alerts
   - Containment: Suspend LLM service, notify compliance
   - Eradication: Review training context, implement output filtering
   - Recovery: Retrain/reconfigure affected components

### Regulatory Considerations

**US Federal AI Governance (relevant to GovCloud deployment):**
- Monitor NIST AI Risk Management Framework updates
- Prepare for potential AI-specific FedRAMP controls
- Establish AI incident reporting procedures for DoD contracts
- Document AI system transparency for CMMC assessors

**DoD AI Ethics & Safety:**
- DoD Directive 3000.09 considerations for autonomous systems
- Responsible AI principles in patch generation
- Human-in-the-loop requirements align with HITL architecture

### Updated CMMC Roadmap (AI Considerations)

**Add to Month 9-10 (System Hardening):**
- [ ] AI-specific input validation testing
- [ ] LLM interaction audit logging
- [ ] GraphRAG integrity monitoring setup

**Add to Month 11 (Risk Assessment):**
- [ ] AI-focused penetration testing scenarios
- [ ] Threat hunting for prompt injection patterns
- [ ] SBOM for AI/ML dependencies

**Add to Month 15-18 (Level 3 Enhanced):**
- [ ] AI-specific threat intelligence integration
- [ ] Adversarial input detection capabilities
- [ ] AI incident response tabletop exercise

---

**Document Version:** 2.1
**Last Updated:** December 2025
**Next Review:** Quarterly
**Owner:** Chief Information Security Officer (CISO)

---

**Note:** This document describes the planned certification pathway and technical control implementation.
