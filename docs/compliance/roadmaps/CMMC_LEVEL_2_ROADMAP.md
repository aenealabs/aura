# CMMC Level 2 Certification Roadmap

## Project Aura - Autonomous AI SaaS Platform

**Document Version:** 1.0
**Last Updated:** December 22, 2025
**Classification:** Public
**Target Certification:** CMMC Level 2 (Advanced)

---

## Executive Summary

This roadmap outlines the path to CMMC Level 2 certification for Project Aura. CMMC Level 2 is required for contractors handling Controlled Unclassified Information (CUI) and aligns with the 110 security requirements from NIST SP 800-171 Rev 2. This certification is mandatory for defense contractors bidding on contracts involving CUI.

**Timeline Estimate:** 8-12 months from initiation to certification

**Total Investment:** $200,000-350,000 (first year)

**Current State:** Project Aura is approximately 50-60% compliant with CMMC Level 2 requirements. Strong technical infrastructure (encryption, logging, access control) provides a solid foundation, but organizational controls (training, incident response, personnel security, risk assessment, security assessment) require significant development.

**Market Opportunity:** CMMC Level 2 certification unlocks:
- DoD contracts involving CUI
- Defense Industrial Base (DIB) subcontracting opportunities
- Government contractor partnerships requiring flow-down compliance
- Competitive differentiation in federal AI market

**Key Advantages:**
- Infrastructure already GovCloud-ready (19/19 services)
- 110 NIST 800-171 controls map directly to existing security architecture
- Automated evidence generation through SOC 2 Compliance Service
- No legacy technical debt requiring remediation

---

## Current State Assessment

### Control Domain Status Overview

| Domain | Code | Controls | Current Status | Gap Assessment |
|--------|------|----------|----------------|----------------|
| Access Control | AC | 22 | 75% Complete | Need access review procedures |
| Awareness & Training | AT | 3 | 0% Complete | No training program exists |
| Audit & Accountability | AU | 9 | 85% Complete | Need audit review procedures |
| Configuration Management | CM | 9 | 90% Complete | Minor documentation gaps |
| Identification & Authentication | IA | 11 | 80% Complete | MFA deployment incomplete |
| Incident Response | IR | 3 | 30% Complete | Need IR plan and procedures |
| Maintenance | MA | 6 | 95% Complete | AWS inherited controls |
| Media Protection | MP | 9 | 85% Complete | Need handling procedures |
| Personnel Security | PS | 2 | 20% Complete | Need background check process |
| Physical Protection | PE | 6 | 100% Complete | AWS inherited controls |
| Risk Assessment | RA | 3 | 25% Complete | Need formal RA program |
| Security Assessment | CA | 4 | 35% Complete | Need assessment procedures |
| System & Communications | SC | 16 | 85% Complete | Need boundary documentation |
| System & Information Integrity | SI | 7 | 70% Complete | Need integrity monitoring |

### Overall Compliance Estimate

```
CMMC Level 2 Total Controls: 110 (NIST 800-171 Rev 2)
AWS/Infrastructure Inherited: ~25 controls (23%)
Customer Responsibility: ~85 controls (77%)

Current Implementation Status:
- Fully Implemented: ~55 controls (50%)
- Partially Implemented: ~25 controls (23%)
- Not Implemented: ~30 controls (27%)

Overall Estimate: 50-60% Complete
```

### Detailed Control Status by Domain

#### Access Control (AC) - 75% Complete

| Control ID | Requirement | Status | Notes |
|------------|-------------|--------|-------|
| AC.L2-3.1.1 | Limit system access to authorized users | Implemented | IAM, RBAC |
| AC.L2-3.1.2 | Limit system access to authorized functions | Implemented | IAM policies |
| AC.L2-3.1.3 | Control CUI flow | Partial | Need data flow documentation |
| AC.L2-3.1.4 | Separate duties | Partial | Solo founder challenge |
| AC.L2-3.1.5 | Employ least privilege | Implemented | IAM least privilege |
| AC.L2-3.1.6 | Use non-privileged accounts | Implemented | Separate admin accounts |
| AC.L2-3.1.7 | Prevent non-privileged users | Implemented | IAM enforcement |
| AC.L2-3.1.8 | Limit unsuccessful login attempts | Implemented | Cognito/JWT config |
| AC.L2-3.1.9 | Provide privacy/security notices | Partial | Need system banners |
| AC.L2-3.1.10 | Session lock | Partial | Need timeout configuration |
| AC.L2-3.1.11 | Session termination | Partial | Need automatic termination |
| AC.L2-3.1.12 | Monitor remote access | Implemented | CloudTrail, VPC Flow Logs |
| AC.L2-3.1.13 | Cryptographic remote sessions | Implemented | TLS 1.3 |
| AC.L2-3.1.14 | Route remote access | Implemented | VPC architecture |
| AC.L2-3.1.15 | Authorize remote execution | Implemented | IAM controls |
| AC.L2-3.1.16 | Wireless access authorization | N/A | Cloud-native |
| AC.L2-3.1.17 | Wireless access protection | N/A | Cloud-native |
| AC.L2-3.1.18 | Mobile device connection | Partial | Need MDM policy |
| AC.L2-3.1.19 | Encrypt CUI on mobile | N/A | No mobile clients |
| AC.L2-3.1.20 | Control external connections | Implemented | VPC, Security Groups |
| AC.L2-3.1.21 | Portable storage use | Partial | Need policy |
| AC.L2-3.1.22 | CUI on public systems | Implemented | No public CUI exposure |

#### Awareness & Training (AT) - 0% Complete (CRITICAL GAP)

| Control ID | Requirement | Status | Notes |
|------------|-------------|--------|-------|
| AT.L2-3.2.1 | Role-based awareness | Not Implemented | Need training program |
| AT.L2-3.2.2 | Role-based training | Not Implemented | Need role-specific training |
| AT.L2-3.2.3 | Insider threat awareness | Not Implemented | Need insider threat training |

#### Audit & Accountability (AU) - 85% Complete

| Control ID | Requirement | Status | Notes |
|------------|-------------|--------|-------|
| AU.L2-3.3.1 | System auditing | Implemented | CloudTrail, CloudWatch |
| AU.L2-3.3.2 | User accountability | Implemented | Audit logging |
| AU.L2-3.3.3 | Event review | Partial | Need formal review process |
| AU.L2-3.3.4 | Alert on failure | Implemented | CloudWatch alarms |
| AU.L2-3.3.5 | Event correlation | Partial | Need SIEM |
| AU.L2-3.3.6 | Audit reduction | Partial | Basic filtering |
| AU.L2-3.3.7 | Time stamps | Implemented | NTP sync |
| AU.L2-3.3.8 | Audit protection | Implemented | S3 versioning, IAM |
| AU.L2-3.3.9 | Audit management | Implemented | IAM controls |

#### Incident Response (IR) - 30% Complete (CRITICAL GAP)

| Control ID | Requirement | Status | Notes |
|------------|-------------|--------|-------|
| IR.L2-3.6.1 | Incident handling | Partial | GuardDuty alerts, no procedures |
| IR.L2-3.6.2 | Track/document/report | Not Implemented | Need tracking system |
| IR.L2-3.6.3 | Test incident response | Not Implemented | Need tabletop exercises |

#### Risk Assessment (RA) - 25% Complete (CRITICAL GAP)

| Control ID | Requirement | Status | Notes |
|------------|-------------|--------|-------|
| RA.L2-3.11.1 | Risk assessments | Partial | AWS Inspector only |
| RA.L2-3.11.2 | Vulnerability scanning | Implemented | AWS Inspector |
| RA.L2-3.11.3 | Vulnerability remediation | Partial | No formal process |

#### Security Assessment (CA) - 35% Complete (CRITICAL GAP)

| Control ID | Requirement | Status | Notes |
|------------|-------------|--------|-------|
| CA.L2-3.12.1 | Security assessments | Partial | 4,874 automated tests |
| CA.L2-3.12.2 | Remediation plans | Not Implemented | Need POA&M process |
| CA.L2-3.12.3 | Continuous monitoring | Partial | Need formal program |
| CA.L2-3.12.4 | System security plans | Partial | Architecture docs exist |

---

## CMMC Level 2 Requirements Overview

### Framework Structure

CMMC Level 2 (Advanced) requires implementation of all 110 security requirements from NIST SP 800-171 Rev 2, organized into 14 domains. Assessment is performed by a Certified Third-Party Assessment Organization (C3PAO).

### Assessment Types

| Assessment Type | Requirement | Frequency |
|-----------------|-------------|-----------|
| **Self-Assessment** | Required for some contracts | Annual |
| **C3PAO Assessment** | Required for CUI contracts | Every 3 years |
| **Affirmation** | CEO/responsible official | After each assessment |

### Scoring Methodology

| Criteria | Scoring |
|----------|---------|
| Control Met | Full points |
| Control Partially Met | Partial points (with POA&M) |
| Control Not Met | Zero points (requires remediation) |
| Minimum Passing | All 110 controls at MET or POA&M with timeline |

---

## Implementation Plan

### Phase Overview

| Phase | Duration | Focus | Investment |
|-------|----------|-------|------------|
| Phase 1 | Months 1-2 | Gap analysis, consultant engagement | $20,000-40,000 |
| Phase 2 | Months 3-4 | Access Control, Authentication | $25,000-40,000 |
| Phase 3 | Months 5-6 | Audit, Logging, Incident Response | $40,000-60,000 |
| Phase 4 | Months 7-8 | System hardening, Communications | $30,000-50,000 |
| Phase 5 | Months 9-10 | Risk assessment, Security testing | $35,000-55,000 |
| Phase 6 | Month 11 | Documentation, Training, Pre-assessment | $20,000-30,000 |
| Phase 7 | Month 12 | C3PAO assessment | $50,000-100,000 |

### Phase 1: Gap Analysis and Planning (Months 1-2)

**Objective:** Comprehensive assessment and implementation planning

#### Month 1: Assessment and Consultant Engagement

| Week | Activities | Deliverables |
|------|------------|--------------|
| 1 | Research and select CMMC consultant | Consultant shortlist |
| 1-2 | Engage CMMC Registered Practitioner (RP) | Contract signed |
| 2-3 | Complete self-assessment | Self-assessment scorecard |
| 3-4 | Document all existing controls | Control inventory |
| 4 | Map controls to 110 requirements | Gap analysis report |

**Consultant Selection Criteria:**

| Criterion | Importance | Notes |
|-----------|------------|-------|
| CMMC-AB registration | Required | RP or RPO status |
| AI/SaaS experience | High | Understands cloud-native |
| DoD contractor experience | High | Knows industry expectations |
| Pricing model | Medium | Fixed vs. hourly |
| Assessment support | Medium | Post-certification support |

#### Month 2: Implementation Planning

| Week | Activities | Deliverables |
|------|------------|--------------|
| 1-2 | Prioritize control gaps | Prioritized remediation plan |
| 2-3 | Develop System Security Plan (SSP) outline | SSP framework |
| 3-4 | Create implementation timeline | Detailed project plan |
| 4 | Identify tool requirements | Tool procurement list |
| 4 | Budget finalization | Approved budget |

**Deliverables:**
- Complete gap analysis report
- Implementation project plan
- SSP framework document
- Budget and resource allocation
- Risk assessment for implementation

---

### Phase 2: Access Control and Authentication (Months 3-4)

**Objective:** Complete AC and IA domain requirements

#### Access Control Remediation

| Control Gap | Implementation | Effort | Cost |
|-------------|----------------|--------|------|
| AC.L2-3.1.3 (CUI flow) | Document data flow diagrams | 20 hours | Internal |
| AC.L2-3.1.4 (Separation) | Document compensating controls | 10 hours | Internal |
| AC.L2-3.1.9 (Notices) | Implement system banners | 8 hours | Internal |
| AC.L2-3.1.10 (Session lock) | Configure session timeouts | 8 hours | Internal |
| AC.L2-3.1.11 (Termination) | Implement auto-logoff | 8 hours | Internal |
| AC.L2-3.1.18 (Mobile) | Develop MDM policy | 15 hours | Internal |
| AC.L2-3.1.21 (Portable storage) | Create policy document | 10 hours | Internal |

**Technical Implementation:**

```
Tasks:
1. Deploy system access banners (all endpoints)
2. Configure session timeout (15 minutes idle)
3. Implement automatic session termination (8 hours max)
4. Create CUI data flow documentation
5. Document role separation compensating controls
6. Develop mobile device policy (if applicable)
7. Create removable media policy
```

#### Identification & Authentication Enhancement

| Control Gap | Implementation | Effort | Cost |
|-------------|----------------|--------|------|
| IA.L2-3.5.3 (MFA) | Deploy MFA to all admin accounts | 20 hours | $500-2,000 |
| IA.L2-3.5.4 (Replay resistant) | Verify token implementation | 10 hours | Internal |
| IA.L2-3.5.7 (Password complexity) | Update password policies | 8 hours | Internal |
| IA.L2-3.5.8 (Password reuse) | Configure password history | 4 hours | Internal |
| IA.L2-3.5.10 (Crypto auth) | Document PKI implementation | 15 hours | Internal |

**MFA Implementation:**
- AWS IAM: MFA required for all console access
- Application: TOTP or hardware keys
- API: Certificate-based or MFA-protected credentials
- Verify: All privileged accounts have MFA

---

### Phase 3: Audit, Logging, and Incident Response (Months 5-6)

**Objective:** Complete AU and IR domain requirements

#### Audit Enhancement

| Control Gap | Implementation | Effort | Cost |
|-------------|----------------|--------|------|
| AU.L2-3.3.3 (Event review) | Implement log review procedures | 20 hours | Internal |
| AU.L2-3.3.5 (Correlation) | Deploy SIEM solution | 40 hours | $15,000-30,000/year |
| AU.L2-3.3.6 (Reduction) | Configure log filtering | 10 hours | Internal |

**SIEM Selection:**

| Option | Cost (Annual) | Pros | Cons |
|--------|---------------|------|------|
| AWS Security Hub | $5,000-10,000 | Native AWS, lower cost | Limited correlation |
| Sumo Logic | $15,000-25,000 | Good cloud support | Medium learning curve |
| Splunk Cloud | $30,000-50,000 | Industry standard | Expensive |
| Microsoft Sentinel | $20,000-35,000 | Good if Azure exists | AWS integration work |

**Recommendation:** AWS Security Hub + CloudWatch Logs Insights for cost-conscious solo founder. Upgrade to Sumo Logic if budget allows.

#### Incident Response Program (CRITICAL)

| Control | Implementation | Effort | Cost |
|---------|----------------|--------|------|
| IR.L2-3.6.1 | Develop IR plan | 40 hours | $5,000-10,000 |
| IR.L2-3.6.2 | Implement incident tracking | 20 hours | $2,000-5,000/year |
| IR.L2-3.6.3 | Conduct tabletop exercises | 16 hours | Internal |

**Incident Response Plan Components:**

1. **Incident Categories**
   - Security incidents (unauthorized access, malware, data breach)
   - Availability incidents (outages, DoS)
   - Integrity incidents (data corruption, tampering)

2. **Response Procedures**
   - Detection and analysis
   - Containment
   - Eradication
   - Recovery
   - Post-incident review

3. **Escalation Matrix**

| Severity | Response Time | Escalation |
|----------|---------------|------------|
| Critical | 15 minutes | MDR provider + owner |
| High | 1 hour | Owner notification |
| Medium | 4 hours | Business hours |
| Low | 24 hours | Standard queue |

4. **External Contacts**
   - MDR/SOC provider (24/7)
   - CISA (for federal reporting)
   - Legal counsel
   - Cyber insurance carrier

**MDR Provider Options:**

| Provider | Cost (Annual) | Coverage | Notes |
|----------|---------------|----------|-------|
| CrowdStrike Falcon Complete | $30,000-50,000 | 24/7 | Enterprise-grade |
| MDR Provider A | $20,000-35,000 | 24/7 | Good for SMB |
| Expel | $25,000-40,000 | 24/7 | Cloud-native focus |
| AWS Managed Services | $15,000-25,000 | Business hours | AWS-specific |

**Recommendation:** An SMB-focused MDR provider with 24/7 coverage.

---

### Phase 4: System Hardening and Communications (Months 7-8)

**Objective:** Complete SC and SI domain requirements

#### System & Communications Protection

| Control Gap | Implementation | Effort | Cost |
|-------------|----------------|--------|------|
| SC.L2-3.13.1 (Boundary protection) | Document network boundaries | 20 hours | Internal |
| SC.L2-3.13.2 (Architectural designs) | Update architecture docs | 15 hours | Internal |
| SC.L2-3.13.4 (Info in shared resources) | Verify tenant isolation | 10 hours | Internal |
| SC.L2-3.13.6 (Network segmentation) | Document VPC segmentation | 15 hours | Internal |
| SC.L2-3.13.11 (CUI encryption) | Verify KMS implementation | 10 hours | Internal |
| SC.L2-3.13.16 (CUI at rest) | Document encryption architecture | 10 hours | Internal |

**Network Architecture Documentation:**
- VPC architecture diagrams
- Security group configurations
- Network ACL policies
- Data flow diagrams showing CUI boundaries
- Encryption implementation details

#### System & Information Integrity

| Control Gap | Implementation | Effort | Cost |
|-------------|----------------|--------|------|
| SI.L2-3.14.1 (Flaw remediation) | Formalize patching process | 20 hours | Internal |
| SI.L2-3.14.2 (Malicious code protection) | Deploy endpoint protection | 15 hours | $5,000-15,000/year |
| SI.L2-3.14.3 (Security alerts) | Subscribe to threat feeds | 5 hours | $2,000-10,000/year |
| SI.L2-3.14.6 (Monitoring communications) | Configure WAF logging | 10 hours | Internal |
| SI.L2-3.14.7 (Unauthorized use) | Implement UEBA basics | 20 hours | $10,000-25,000/year |

**Endpoint Detection & Response (EDR):**

| Provider | Cost (Annual) | Features | Notes |
|----------|---------------|----------|-------|
| CrowdStrike Falcon Go | $8,000-15,000 | SMB-focused | Good for small teams |
| SentinelOne Control | $10,000-20,000 | Strong cloud | Automated response |
| Microsoft Defender | $5,000-10,000 | If Windows | Limited Linux |
| Carbon Black | $15,000-25,000 | Enterprise | May be overkill |

**Recommendation:** CrowdStrike Falcon Go for cost-effective EDR with strong detection.

---

### Phase 5: Risk Assessment and Security Testing (Months 9-10)

**Objective:** Complete RA and CA domain requirements

#### Risk Assessment Program (CRITICAL)

| Control | Implementation | Effort | Cost |
|---------|----------------|--------|------|
| RA.L2-3.11.1 (Risk assessments) | Develop RA methodology | 30 hours | $5,000-10,000 |
| RA.L2-3.11.2 (Vulnerability scanning) | Already implemented | N/A | AWS Inspector |
| RA.L2-3.11.3 (Remediation) | Formalize remediation SLAs | 15 hours | Internal |

**Risk Assessment Framework:**

1. **Asset Inventory**
   - All CUI repositories
   - Systems processing CUI
   - Network components
   - Third-party services

2. **Threat Analysis**
   - Nation-state actors
   - Cybercriminals
   - Insider threats
   - Supply chain risks

3. **Vulnerability Assessment**
   - AWS Inspector findings
   - Third-party penetration testing
   - Configuration reviews

4. **Risk Scoring**

| Risk Level | Likelihood | Impact | Remediation Timeline |
|------------|------------|--------|---------------------|
| Critical | High | High | 24-48 hours |
| High | High | Medium or Medium | High | 7 days |
| Medium | Medium | Medium | 30 days |
| Low | Low | Any or Any | Low | 90 days |

#### Security Assessment & Continuous Monitoring

| Control | Implementation | Effort | Cost |
|---------|----------------|--------|------|
| CA.L2-3.12.1 (Assessments) | Conduct internal assessments | 40 hours | Internal |
| CA.L2-3.12.2 (POA&M) | Implement POA&M tracking | 20 hours | Internal |
| CA.L2-3.12.3 (Continuous monitoring) | Formalize ConMon program | 30 hours | Internal |
| CA.L2-3.12.4 (Security plans) | Complete SSP | 60 hours | Internal |

**Penetration Testing:**

| Type | Frequency | Cost | Provider Type |
|------|-----------|------|---------------|
| External penetration test | Annual | $15,000-30,000 | CMMC-aware firm |
| Internal penetration test | Annual | $10,000-20,000 | CMMC-aware firm |
| Web application test | Annual | $10,000-25,000 | CMMC-aware firm |
| Social engineering | Optional | $5,000-15,000 | CMMC-aware firm |

**Recommended Penetration Testing Scope:**
1. External network penetration test
2. Web application penetration test (API testing)
3. Cloud configuration review
4. Credential stuffing assessment

---

### Phase 6: Documentation, Training, and Pre-Assessment (Month 11)

**Objective:** Complete documentation and prepare for C3PAO assessment

#### System Security Plan (SSP) Completion

| Section | Description | Effort |
|---------|-------------|--------|
| System identification | Boundaries, components | 20 hours |
| Control implementation | All 110 controls | 80 hours |
| Security architecture | Network, data flow | 15 hours |
| Roles and responsibilities | Personnel | 10 hours |
| POA&M (if applicable) | Remediation plans | 15 hours |

**SSP Quality Checklist:**
- [ ] All 110 controls addressed
- [ ] Implementation descriptions specific (not generic)
- [ ] Evidence references included
- [ ] Inherited controls clearly marked
- [ ] Diagrams current and accurate
- [ ] Roles assigned to each control

#### Security Awareness Training (CRITICAL)

| Training Type | Audience | Frequency | Provider |
|---------------|----------|-----------|----------|
| General security awareness | All users | Annual | KnowBe4, Proofpoint |
| CUI handling | CUI access users | Annual | Custom + platform |
| Insider threat | All users | Annual | KnowBe4, CDSE |
| Role-based technical | Admins, developers | Annual | Custom |

**Training Platform Options:**

| Provider | Cost (Annual) | Features | Notes |
|----------|---------------|----------|-------|
| KnowBe4 | $2,000-5,000 | Comprehensive | Industry leader |
| Proofpoint | $3,000-8,000 | Good phishing sims | Enterprise focus |
| CDSE (DoD) | Free | DoD-specific | Limited customization |
| Curricula | $1,500-3,000 | Modern approach | Newer platform |

**Recommendation:** KnowBe4 for comprehensive platform with DoD-relevant content.

#### Pre-Assessment Readiness

| Activity | Purpose | Effort |
|----------|---------|--------|
| Internal assessment | Identify gaps | 40 hours |
| Evidence collection | Prepare documentation | 30 hours |
| Interview preparation | Train personnel | 15 hours |
| Mock assessment | Practice C3PAO process | 20 hours |

---

### Phase 7: C3PAO Assessment (Month 12)

**Objective:** Successfully complete third-party assessment

#### C3PAO Selection

**Selection Criteria:**

| Criterion | Weight | Evaluation |
|-----------|--------|------------|
| CMMC-AB accreditation | Required | Verify on Marketplace |
| SaaS/cloud experience | High | Reference check |
| AI/ML system experience | Medium | Portfolio review |
| Assessment timeline | High | Availability |
| Pricing | Medium | Compare 3+ quotes |
| Post-assessment support | Medium | Remediation assistance |

**C3PAO Engagement Timeline:**

| Week | Activity | Notes |
|------|----------|-------|
| -8 | Initial outreach | Contact 3+ C3PAOs |
| -6 | Proposals received | Review and compare |
| -4 | C3PAO selected | Contract signed |
| -3 | Pre-assessment call | Logistics, scope |
| -1 | Evidence submission | SSP, supporting docs |
| 0 | Assessment week | On-site or virtual |
| +2 | Draft findings | Review opportunity |
| +4 | Final report | Assessment complete |

#### Assessment Scope

| Assessment Area | Method | Evidence Required |
|-----------------|--------|-------------------|
| Documentation review | SSP, policies, procedures | All written documentation |
| Technical testing | Vulnerability scans, config review | System access |
| Personnel interviews | Control implementation | Staff availability |
| Evidence review | Logs, screenshots, reports | Historical records |

#### Common Assessment Findings

| Finding Type | Examples | Prevention |
|--------------|----------|------------|
| Documentation gaps | Missing procedures | Thorough SSP review |
| Evidence gaps | Cannot prove implementation | Automated evidence collection |
| Training gaps | Incomplete records | LMS with tracking |
| Configuration drift | Settings changed | Continuous monitoring |
| Process gaps | Informal procedures | Document everything |

---

## Cost Breakdown

### Implementation Costs (One-Time)

| Category | Low Estimate | High Estimate | Notes |
|----------|--------------|---------------|-------|
| CMMC Consultant/RP | $15,000 | $30,000 | Gap analysis, SSP support |
| Technical remediation | $25,000 | $50,000 | Tools, configuration |
| Documentation development | $15,000 | $30,000 | SSP, policies, procedures |
| Penetration testing | $25,000 | $50,000 | External, internal, app |
| Training platform setup | $2,000 | $5,000 | Initial configuration |
| **Total Implementation** | **$82,000** | **$165,000** | |

### Assessment Costs

| Category | Low Estimate | High Estimate | Notes |
|----------|--------------|---------------|-------|
| C3PAO assessment | $50,000 | $100,000 | Varies by scope |
| Pre-assessment (optional) | $10,000 | $20,000 | Recommended |
| **Total Assessment** | **$60,000** | **$120,000** | |

### Annual Recurring Costs

| Category | Low Estimate | High Estimate | Notes |
|----------|--------------|---------------|-------|
| SIEM/Log management | $10,000 | $30,000 | Security Hub or Sumo Logic |
| MDR/SOC services | $20,000 | $40,000 | 24/7 monitoring |
| EDR solution | $8,000 | $15,000 | CrowdStrike Falcon Go |
| Training platform | $2,000 | $5,000 | KnowBe4 |
| Vulnerability management | $5,000 | $10,000 | AWS Inspector + third-party |
| Penetration testing | $15,000 | $30,000 | Annual requirement |
| Compliance monitoring | $5,000 | $10,000 | Tools and processes |
| **Total Annual** | **$65,000** | **$140,000** | |

### Total First-Year Investment

| Category | Low Estimate | High Estimate |
|----------|--------------|---------------|
| Implementation | $82,000 | $165,000 |
| Assessment | $60,000 | $120,000 |
| Recurring (partial year) | $35,000 | $70,000 |
| **Total First Year** | **$177,000** | **$355,000** |

---

## Tool Recommendations for Solo Founder

### Cost-Optimized Technology Stack

| Function | Recommended Tool | Cost (Annual) | Alternative |
|----------|------------------|---------------|-------------|
| SIEM | AWS Security Hub | $5,000-10,000 | Sumo Logic ($15K-25K) |
| EDR | CrowdStrike Falcon Go | $8,000-12,000 | SentinelOne ($10K-20K) |
| Vulnerability scanning | AWS Inspector | $3,000-5,000 | Tenable ($15K-25K) |
| Training | KnowBe4 | $2,000-3,000 | CDSE (free) |
| MDR | MDR Provider | $20,000-30,000 | Alternative ($25K-40K) |
| GRC/Documentation | Compliance.ai | $5,000-10,000 | Spreadsheets (free) |
| Penetration testing | Bishop Fox | $25,000-40,000 | Coalfire ($30K-50K) |

### Minimum Viable Tool Investment

For the most budget-conscious approach:

| Function | Tool | Annual Cost |
|----------|------|-------------|
| SIEM | AWS Security Hub | $5,000 |
| EDR | CrowdStrike Falcon Go | $8,000 |
| Vulnerability | AWS Inspector | $3,000 |
| Training | CDSE (DoD) + KnowBe4 basics | $1,500 |
| MDR | MDR provider (essential) | $20,000 |
| **Minimum Annual Tools** | | **$37,500** |

---

## Solo Founder Considerations

### Segregation of Duties Challenge

CMMC Level 2 expects role separation but acknowledges small organizations. For a solo founder:

| Challenge | Compensating Control |
|-----------|---------------------|
| Admin vs. user separation | Separate IAM accounts, different credentials |
| Security vs. operations | Document review procedures, external review |
| Change management | Automated pipeline, peer review (external) |
| Audit independence | Third-party log review (MDR provider) |

**Documentation Approach:**
1. Document that organization is single-person
2. Describe compensating controls for each separation requirement
3. Show how automated systems provide checks
4. Reference third-party oversight (MDR, C3PAO, consultant)

### Time Management

| Month | Hours/Week | Focus Area |
|-------|------------|------------|
| 1-2 | 15-20 | Assessment, planning |
| 3-4 | 20-25 | AC, IA implementation |
| 5-6 | 25-30 | AU, IR implementation |
| 7-8 | 20-25 | SC, SI implementation |
| 9-10 | 25-30 | RA, CA, testing |
| 11 | 30-40 | Documentation, prep |
| 12 | 40+ | Assessment support |

**Total Estimated Time:** 1,000-1,500 hours over 12 months

### Outsourcing Recommendations

| Function | In-House vs. Outsource | Rationale |
|----------|------------------------|-----------|
| SSP writing | Hybrid | You know system, consultant knows format |
| Policy development | Outsource | Templates save significant time |
| Technical implementation | In-house | You know the codebase |
| Penetration testing | Outsource | Requires independence |
| Training | Outsource | Platforms are efficient |
| 24/7 monitoring | Outsource | Cannot do solo |
| Assessment coordination | In-house | You must be involved |

---

## Leverage Points

### Existing Advantages

| Asset | CMMC Benefit | Control Domains |
|-------|--------------|-----------------|
| 100% IaC (CloudFormation) | Configuration management evidence | CM |
| 4,874 automated tests | Continuous assessment evidence | CA |
| KMS encryption (rotation enabled) | Encryption at rest compliance | SC |
| CloudTrail + VPC Flow Logs | Audit logging compliance | AU |
| GuardDuty + CloudWatch alarms | Incident detection | IR, SI |
| IAM least-privilege policies | Access control foundation | AC |
| AWS Config rules | Configuration monitoring | CM, CA |
| GovCloud-ready architecture | Federal deployment ready | All |
| SOC 2 Evidence Service | Automated evidence generation | All |
| Zero hardcoded credentials | Secret management compliance | IA |

### Evidence Automation Opportunities

| Control Area | Automation Method | Implementation Effort |
|--------------|-------------------|----------------------|
| Access reviews | IAM Access Analyzer exports | Low (already available) |
| Configuration compliance | AWS Config rule reports | Low (already deployed) |
| Vulnerability status | Inspector findings export | Low (already deployed) |
| Audit logs | CloudTrail/CloudWatch export | Low (already available) |
| Encryption verification | KMS inventory automation | Medium |
| User activity | CloudTrail event analysis | Medium |
| System health | CloudWatch dashboards | Low (already deployed) |

---

## Risk Factors and Mitigation

### Implementation Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| C3PAO availability | Medium | 2-3 month delay | Book early (3+ months ahead) |
| Scope creep | Medium | Budget overrun | Fixed-scope contracts |
| Assessment findings | Medium | Remediation delay | Pre-assessment investment |
| Tool integration issues | Low | Technical delays | PoC before commitment |
| Budget overrun | Medium | Financial strain | 20% contingency |
| Time commitment underestimated | High | Burnout, delays | Aggressive outsourcing |

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| AWS service changes | Low | Reconfiguration | Architecture review buffer |
| Third-party tool failures | Low | Evidence gaps | Backup solutions identified |
| Data breach during implementation | Low | Project halt | MDR engagement early |
| Control regression | Medium | Assessment failure | Continuous monitoring |

### Mitigation Strategies

1. **Schedule Risk:** Engage C3PAO 4+ months before desired assessment
2. **Budget Risk:** Maintain 20% contingency, prioritize must-haves
3. **Scope Risk:** Document scope clearly, resist feature creep
4. **Technical Risk:** Test tools in non-production before commitment
5. **Time Risk:** Set realistic expectations, use external resources

---

## Decision Points

### Decision 1: Assessment Timeline
**Question:** Standard (12 months) or Accelerated (8-9 months)?
- **Standard:** Lower weekly effort, spread costs
- **Accelerated:** Higher intensity, earlier certification

**Decision Needed By:** Project kickoff

### Decision 2: SIEM Selection
**Question:** AWS Security Hub (lower cost) or full SIEM (Sumo Logic)?
- **Security Hub:** $5K-10K/year, native AWS, basic correlation
- **Full SIEM:** $15K-30K/year, advanced correlation, better for IR

**Decision Needed By:** End of Month 4

### Decision 3: MDR Provider
**Question:** Which MDR provider for 24/7 coverage?
- Critical for IR requirements
- Evaluate managed detection and response providers

**Decision Needed By:** End of Month 4

### Decision 4: C3PAO Selection
**Question:** Which C3PAO for assessment?
- Request quotes from 3+ accredited C3PAOs
- Evaluate cloud/SaaS experience

**Decision Needed By:** End of Month 9

### Decision 5: POA&M Strategy
**Question:** All controls MET, or accept POA&M for some?
- **All MET:** Cleaner certification, higher upfront investment
- **POA&M:** Faster certification, ongoing remediation required

**Decision Needed By:** End of Month 10

---

## Accelerated Pathway Option

For organizations needing certification faster (8-9 months):

### Parallel Workstreams

| Month | Primary Track | Secondary Track |
|-------|---------------|-----------------|
| 1 | Gap analysis | Tool procurement |
| 2 | AC/IA implementation | Policy drafting |
| 3 | AU/IR implementation | SSP development |
| 4 | SC/SI implementation | Training deployment |
| 5 | RA/CA implementation | Evidence collection |
| 6 | Documentation finalization | Penetration testing |
| 7 | Pre-assessment | Remediation |
| 8-9 | C3PAO assessment | - |

### Resource Requirements for Acceleration

| Resource | Standard Path | Accelerated Path |
|----------|---------------|------------------|
| Weekly hours | 20-25 | 35-45 |
| External contractors | 1 | 2-3 |
| Consultant engagement | Part-time | Full-time |
| Budget increase | Baseline | +30-50% |

### Acceleration Trade-offs

| Benefit | Risk |
|---------|------|
| Earlier market access | Higher burnout risk |
| Faster ROI | Potential quality issues |
| Competitive advantage | Higher upfront cost |
| Earlier revenue | Less margin for error |

---

## Next Steps

### Immediate Actions (Week 1-2)

1. **Research CMMC Consultants**
   - Identify 3+ CMMC Registered Practitioners
   - Schedule initial consultations
   - Request proposals

2. **Complete Self-Assessment**
   - Download NIST 800-171 assessment template
   - Score each of 110 controls
   - Document evidence gaps

3. **Tool Research**
   - Request quotes: SIEM, EDR, MDR, Training
   - Schedule product demos
   - Evaluate AWS-native vs. third-party

4. **Budget Approval**
   - Finalize investment estimate
   - Secure funding commitment
   - Plan cash flow

### Month 1 Milestones

- [ ] CMMC consultant engaged
- [ ] Self-assessment complete
- [ ] Gap analysis documented
- [ ] Tool procurement initiated
- [ ] Budget approved
- [ ] Project plan finalized

### Success Criteria

| Milestone | Target Date | Success Metric |
|-----------|-------------|----------------|
| Gap analysis complete | Month 2 | All 110 controls assessed |
| Technical controls implemented | Month 8 | 95%+ controls MET |
| SSP complete | Month 11 | C3PAO-ready documentation |
| Pre-assessment passed | Month 11 | <10 findings |
| C3PAO assessment complete | Month 12 | Certification granted |

---

## Appendix A: NIST 800-171 Control Quick Reference

| Domain | Controls | Focus |
|--------|----------|-------|
| Access Control (AC) | 3.1.1-3.1.22 | User access management |
| Awareness & Training (AT) | 3.2.1-3.2.3 | Security training |
| Audit & Accountability (AU) | 3.3.1-3.3.9 | Logging and monitoring |
| Configuration Management (CM) | 3.4.1-3.4.9 | System configuration |
| Identification & Authentication (IA) | 3.5.1-3.5.11 | Identity management |
| Incident Response (IR) | 3.6.1-3.6.3 | Security incidents |
| Maintenance (MA) | 3.7.1-3.7.6 | System maintenance |
| Media Protection (MP) | 3.8.1-3.8.9 | Data handling |
| Personnel Security (PS) | 3.9.1-3.9.2 | HR security |
| Physical Protection (PE) | 3.10.1-3.10.6 | Facility security |
| Risk Assessment (RA) | 3.11.1-3.11.3 | Risk management |
| Security Assessment (CA) | 3.12.1-3.12.4 | Security testing |
| System & Communications (SC) | 3.13.1-3.13.16 | Network security |
| System & Information Integrity (SI) | 3.14.1-3.14.7 | System integrity |

---

## Appendix B: Useful Resources

### Official Resources
- CMMC-AB Website: https://cyberab.org
- NIST 800-171: https://csrc.nist.gov/publications/detail/sp/800-171/rev-2/final
- DoD CIO CMMC: https://dodcio.defense.gov/CMMC/
- CMMC Marketplace: https://cyberab.org/Marketplace

### Assessment Support
- NIST 800-171A (Assessment Guide): https://csrc.nist.gov/publications/detail/sp/800-171a/final
- CMMC Assessment Guide: Available from CMMC-AB

### Training Resources
- CDSE (DoD Training): https://www.cdse.edu/
- KnowBe4: https://www.knowbe4.com/
- SANS: https://www.sans.org/

---

*Document maintained by Aenea Labs. For questions, contact the compliance team.*
