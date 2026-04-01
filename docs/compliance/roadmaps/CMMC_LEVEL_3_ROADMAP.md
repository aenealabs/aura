# CMMC Level 3 Certification Roadmap

## Project Aura - Autonomous AI SaaS Platform

**Document Version:** 1.0
**Last Updated:** December 22, 2025
**Classification:** Public
**Target Certification:** CMMC Level 3 (Expert)

---

## Executive Summary

This roadmap outlines the path to CMMC Level 3 certification for Project Aura. CMMC Level 3 (Expert) is required for contractors handling the most sensitive Controlled Unclassified Information (CUI) in Department of Defense programs. Level 3 builds upon Level 2 by adding 24 enhanced security requirements derived from NIST SP 800-172.

**Prerequisites:** CMMC Level 2 certification must be achieved before pursuing Level 3.

**Timeline Estimate:** 6-12 months AFTER achieving CMMC Level 2 certification

**Total Investment:** $400,000-650,000 (incremental beyond Level 2)

**Strategic Value:** CMMC Level 3 certification positions Project Aura for:
- Highest-priority DoD programs (critical programs, weapons systems)
- Intelligence community adjacent contracts
- Defense Industrial Base (DIB) leadership tier
- Premium pricing for government contracts
- Competitive moat against less-certified competitors

**Key Challenges:**
- 24 enhanced controls require advanced security capabilities
- Government-led assessment (not just C3PAO)
- Personnel requirements may exceed solo founder capacity
- Significant ongoing operational investment

---

## CMMC Level 3 Overview

### Framework Position

| Level | Requirements | Assessment | Use Case |
|-------|--------------|------------|----------|
| Level 1 | 17 practices (FAR 52.204-21) | Self-assessment | FCI only |
| Level 2 | 110 controls (NIST 800-171) | C3PAO | Standard CUI |
| **Level 3** | **110 + 24 enhanced (800-172)** | **C3PAO + Government** | **Critical CUI** |

### NIST SP 800-172 Enhanced Requirements

The 24 enhanced security requirements focus on protecting CUI from Advanced Persistent Threats (APTs), nation-state actors, and sophisticated adversaries. These requirements demand:

- **Proactive defense** (not just reactive controls)
- **Threat-informed security** (intelligence-driven decisions)
- **Defense-in-depth** (multiple overlapping protections)
- **Rapid response** (minimize adversary dwell time)

### Enhanced Control Domains

| Domain | Enhanced Controls | Focus Area |
|--------|-------------------|------------|
| Access Control | 4 controls | Dynamic access, micro-segmentation |
| Incident Response | 4 controls | Insider threat, threat intelligence |
| Risk Assessment | 4 controls | Threat hunting, adversary emulation |
| Security Assessment | 6 controls | Purple team, continuous testing |
| Configuration Management | 2 controls | SBOM, supply chain |
| Personnel Security | 2 controls | Enhanced screening |
| System & Communications | 2 controls | Advanced encryption, isolation |

---

## Prerequisites Assessment

### Required CMMC Level 2 Foundation

Before pursuing Level 3, verify Level 2 certification status:

| Requirement | Status | Notes |
|-------------|--------|-------|
| CMMC Level 2 certification | Required | Active, not expired |
| All 110 controls implemented | Required | No POA&M items pending |
| C3PAO assessment passed | Required | Clean report |
| Continuous monitoring active | Required | Operational ConMon program |
| SSP current | Required | Updated within 1 year |

### Gap Analysis: Level 2 to Level 3

| Capability | Level 2 State | Level 3 Requirement | Gap |
|------------|---------------|---------------------|-----|
| Access control | RBAC, MFA | Dynamic access, micro-segmentation | Major |
| Threat detection | SIEM, EDR | UEBA, threat hunting | Major |
| Incident response | IR plan, MDR | Insider threat program, CTI | Major |
| Security testing | Annual pentest | Continuous purple team | Major |
| Supply chain | Vendor review | SBOM, anti-tamper | Moderate |
| Personnel | Background checks | Enhanced screening | Moderate |
| Monitoring | Log analysis | Behavioral analytics | Major |

---

## Enhanced Security Requirements Detail

### Access Control (AC) - 4 Enhanced Controls

#### 3.1.2e - Dynamic Risk-Based Access

**Requirement:** Employ automated mechanisms to dynamically adjust system access based on risk.

| Component | Implementation | Investment |
|-----------|----------------|------------|
| User Risk Scoring | UEBA platform integration | $25,000-50,000 |
| Context-Aware Access | Zero Trust architecture | $30,000-60,000 |
| Dynamic Policy Engine | Identity platform upgrade | $20,000-40,000 |
| Continuous Verification | Real-time authentication | $15,000-30,000 |

**Technical Requirements:**
- Real-time risk scoring for each access request
- Integration with threat intelligence feeds
- Automated access revocation based on risk thresholds
- Context factors: location, device, behavior, time

#### 3.1.3e - Network Segmentation

**Requirement:** Employ micro-segmentation to separate and isolate CUI processing.

| Component | Implementation | Investment |
|-----------|----------------|------------|
| Micro-segmentation Platform | VMware NSX or Illumio | $30,000-75,000 |
| CUI Data Classification | Data discovery and tagging | $15,000-30,000 |
| Segment Monitoring | Traffic analysis | $10,000-25,000 |
| Policy Management | Segmentation policies | $10,000-20,000 |

**Technical Requirements:**
- CUI isolated in dedicated network segments
- East-west traffic inspection
- Automated workload segmentation
- Least-privilege network access

#### 3.1.20e - Dynamic Assets

**Requirement:** Employ dynamic network addresses for CUI systems.

| Component | Implementation | Investment |
|-----------|----------------|------------|
| Dynamic IP allocation | VPC automation | $5,000-15,000 |
| Address obfuscation | Network architecture | $10,000-25,000 |
| Moving target defense | Infrastructure automation | $15,000-35,000 |

#### 3.1.21e - Automated Access Enforcement

**Requirement:** Employ automated mechanisms to enforce access authorizations.

| Component | Implementation | Investment |
|-----------|----------------|------------|
| Policy-as-Code | OPA/Rego policies | $10,000-25,000 |
| Automated enforcement | RBAC automation | $15,000-30,000 |
| Access certification | Quarterly reviews | $5,000-15,000 |

---

### Incident Response (IR) - 4 Enhanced Controls

#### 3.6.1e - Insider Threat Program

**Requirement:** Establish and maintain an insider threat program.

| Component | Implementation | Investment |
|-----------|----------------|------------|
| UEBA Platform | User behavior analytics | $30,000-60,000/year |
| Insider Threat Policy | Policy development | $10,000-20,000 |
| Monitoring Infrastructure | Enhanced logging | $15,000-30,000 |
| Investigation Procedures | Forensic capability | $20,000-40,000 |
| Training | Insider threat awareness | $5,000-10,000/year |

**Program Requirements:**
- Designated Insider Threat Program Senior Official (ITPSO)
- User activity monitoring for anomalies
- Data loss prevention (DLP) integration
- Privileged user monitoring
- Regular risk assessments

**Solo Founder Challenge:** CMMC Level 3 expects a formal insider threat program. For a single-person organization:
- Document that single-person operation limits insider risk
- Implement technical controls (UEBA) as compensating control
- Consider fractional security staff or contractor for oversight role

#### 3.6.2e - Cyber Threat Intelligence

**Requirement:** Integrate cyber threat intelligence and incident response.

| Component | Implementation | Investment |
|-----------|----------------|------------|
| CTI Platform | ThreatConnect, Anomali | $20,000-50,000/year |
| Intelligence Feeds | CISA, FBI, DoD feeds | $5,000-15,000/year |
| SIEM Integration | Feed correlation | $10,000-25,000 |
| Analyst Time | Intelligence analysis | $25,000-50,000/year (contractor) |

**Required Intelligence Sources:**
- CISA Automated Indicator Sharing (AIS)
- FBI InfraGard membership
- DoD Cyber Crime Center (DC3) feeds
- Commercial threat intelligence (Mandiant, Recorded Future)

#### 3.6.3e - Security Operations Center

**Requirement:** Establish a security operations center capability.

| Option | Cost (Annual) | Coverage | Notes |
|--------|---------------|----------|-------|
| In-house SOC | $250,000-500,000 | 24/7 | Requires 3-5 FTEs |
| Managed SOC (MDR) | $50,000-150,000 | 24/7 | Most realistic for solo founder |
| Hybrid SOC | $150,000-250,000 | 24/7 | In-house lead + MDR |

**Recommendation:** Managed SOC with documented escalation procedures satisfies this requirement for small organizations.

#### 3.6.4e - Incident Response Teams

**Requirement:** Establish incident response teams with cross-functional expertise.

| Capability | In-House vs. Contract | Notes |
|------------|----------------------|-------|
| Incident Commander | Owner (you) | Must be available 24/7 |
| Technical Lead | MDR provider | Contracted capability |
| Forensics | On-retainer firm | Digital forensics capability |
| Legal/Communications | On-retainer counsel | Breach notification |

---

### Risk Assessment (RA) - 4 Enhanced Controls

#### 3.11.1e - Threat Hunting

**Requirement:** Employ threat hunting capabilities to search for indicators of compromise.

| Component | Implementation | Investment |
|-----------|----------------|------------|
| Threat Hunting Platform | Elastic Security, Velociraptor | $20,000-50,000 |
| Hunting Playbooks | Documented procedures | $10,000-25,000 |
| Hunting Capability | Trained personnel or contract | $30,000-80,000/year |
| Tooling | EDR with hunting capability | Included in CrowdStrike |

**Hunting Cadence:**
- Scheduled hunts: Monthly (minimum)
- Reactive hunts: Upon intelligence alerts
- Annual hunt assessment: Documented effectiveness review

#### 3.11.2e - Adversary Emulation

**Requirement:** Employ adversary emulation capabilities to validate security defenses.

| Component | Implementation | Investment |
|-----------|----------------|------------|
| Adversary Emulation Platform | Atomic Red Team, MITRE Caldera | $15,000-35,000 |
| Red Team Exercises | Annual contracted exercise | $40,000-100,000 |
| Purple Team Capability | Collaborative exercises | $30,000-60,000 |
| MITRE ATT&CK Mapping | Framework alignment | $10,000-20,000 |

**Exercise Frequency:**
- Adversary emulation (automated): Monthly
- Tabletop exercises: Quarterly
- Full red team engagement: Annual

#### 3.11.3e - Advanced Risk Assessment

**Requirement:** Analyze the effectiveness of security solutions.

| Component | Implementation | Investment |
|-----------|----------------|------------|
| Control Effectiveness Testing | Automated validation | $15,000-30,000 |
| Breach & Attack Simulation | SafeBreach, AttackIQ | $30,000-75,000/year |
| Security Posture Management | CSPM platform | $20,000-50,000/year |

#### 3.11.4e - Supply Chain Risk

**Requirement:** Assess supply chain risks for systems and components.

| Component | Implementation | Investment |
|-----------|----------------|------------|
| Vendor Risk Management | Third-party assessment | $20,000-40,000 |
| Software Composition Analysis | Snyk, Checkmarx | $15,000-35,000/year |
| Supply Chain Due Diligence | Ongoing monitoring | $10,000-25,000/year |

---

### Security Assessment (CA) - 6 Enhanced Controls

#### 3.12.1e - Independent Security Assessments

**Requirement:** Conduct independent penetration testing with advanced techniques.

| Assessment Type | Frequency | Cost | Notes |
|-----------------|-----------|------|-------|
| Advanced penetration test | Annual | $50,000-100,000 | APT simulation |
| Red team engagement | Annual | $75,000-150,000 | Full adversary emulation |
| Application security test | Semi-annual | $25,000-50,000 | Source code review |
| Cloud security assessment | Annual | $30,000-60,000 | Infrastructure review |

#### 3.12.2e - Specialized Assessments

**Requirement:** Conduct specialized assessments for high-value assets.

| Assessment | Scope | Cost |
|------------|-------|------|
| AI/ML Security Assessment | Model security, data poisoning | $40,000-80,000 |
| GraphRAG Security Review | Graph injection, context poisoning | $30,000-60,000 |
| Agent Security Assessment | Agent confusion, tool abuse | $35,000-70,000 |

**Project Aura Specific:** Given the AI-native architecture, specialized AI security assessments are critical:
- Prompt injection testing
- GraphRAG context manipulation
- Agent orchestration security
- Sandbox escape testing

#### 3.12.3e - Security Control Testing

**Requirement:** Continuously test security controls.

| Control Type | Testing Method | Frequency |
|--------------|----------------|-----------|
| Access controls | Automated testing | Daily |
| Network controls | Vulnerability scanning | Weekly |
| Detection controls | Purple team validation | Monthly |
| Response controls | Tabletop exercises | Quarterly |

#### 3.12.4e - Security Reviews

**Requirement:** Conduct security reviews prior to system changes.

| Change Type | Review Requirement | Documentation |
|-------------|-------------------|---------------|
| Major release | Full security review | Security sign-off |
| Minor release | Automated security scan | Scan results |
| Infrastructure change | Configuration review | Change approval |
| Vendor change | Vendor risk assessment | Assessment report |

#### 3.12.5e - Verification

**Requirement:** Verify security configurations using automated mechanisms.

| Verification Type | Tool | Frequency |
|-------------------|------|-----------|
| Configuration drift | AWS Config | Continuous |
| Baseline compliance | CIS benchmarks | Daily |
| Policy compliance | OPA/Rego | Continuous |
| Vulnerability status | Inspector | Weekly |

#### 3.12.6e - Developer Security

**Requirement:** Assess effectiveness of security solutions at developer level.

| Practice | Implementation | Investment |
|----------|----------------|------------|
| Secure SDLC | Security gates in CI/CD | $15,000-30,000 |
| Security training (dev) | Secure coding training | $5,000-15,000/year |
| Code review automation | SAST/DAST tools | $20,000-50,000/year |
| Security champions | Developer security advocate | Internal role |

---

### Configuration Management (CM) - 2 Enhanced Controls

#### 3.4.1e - Software Bill of Materials (SBOM)

**Requirement:** Establish and maintain an SBOM for organizational systems.

| Component | Implementation | Investment |
|-----------|----------------|------------|
| SBOM Generation | Syft, CycloneDX | $10,000-25,000 |
| SBOM Management | Dependency-Track | $15,000-30,000 |
| Vulnerability Correlation | SBOM + CVE mapping | $10,000-20,000 |
| Supply Chain Visibility | Component tracking | $15,000-30,000 |

**SBOM Requirements:**
- Machine-readable format (SPDX or CycloneDX)
- All software components including transitive dependencies
- Version information for all components
- Known vulnerability correlation
- Regular updates (upon each release)

#### 3.4.2e - Anti-Tamper Protection

**Requirement:** Employ anti-tamper technologies and techniques.

| Component | Implementation | Investment |
|-----------|----------------|------------|
| Code signing | All artifacts signed | $5,000-15,000 |
| Integrity verification | Checksums, signatures | $10,000-20,000 |
| Tamper detection | File integrity monitoring | $15,000-30,000 |
| Secure boot | Infrastructure validation | $10,000-25,000 |

---

### Personnel Security (PS) - 2 Enhanced Controls

#### 3.9.1e - Enhanced Personnel Screening

**Requirement:** Screen individuals prior to access with enhanced methods.

| Screening Type | Scope | Cost |
|----------------|-------|------|
| Criminal background | All personnel | $50-200/person |
| Credit check | CUI access | $30-75/person |
| Education verification | All personnel | $25-50/person |
| Employment verification | All personnel | $50-100/person |
| Reference checks | All personnel | $25-75/person |
| Security clearance (if required) | Contract specific | Government-funded |

**Solo Founder Note:** Self-attestation with documented evidence may be acceptable for single-person organizations with government sponsor approval.

#### 3.9.2e - Personnel Security During/After Employment

**Requirement:** Ensure enhanced security measures during and after employment.

| Phase | Requirements | Implementation |
|-------|--------------|----------------|
| Onboarding | Enhanced security briefings | Training modules |
| During employment | Continuous evaluation | UEBA monitoring |
| Termination | Immediate access revocation | Automated deprovisioning |
| Post-employment | Non-disclosure enforcement | Legal agreements |

---

### System & Communications Protection (SC) - 2 Enhanced Controls

#### 3.13.1e - Advanced Encryption

**Requirement:** Employ advanced encryption mechanisms.

| Requirement | Implementation | Investment |
|-------------|----------------|------------|
| FIPS 140-2/3 validated | AWS FIPS endpoints | Configuration change |
| Post-quantum consideration | Algorithm planning | Documentation |
| Key management | AWS KMS (FIPS mode) | $5,000-15,000 |
| Encryption automation | Policy-driven encryption | $10,000-25,000 |

#### 3.13.2e - Enhanced Network Isolation

**Requirement:** Employ enhanced isolation for CUI systems.

| Component | Implementation | Investment |
|-----------|----------------|------------|
| Dedicated CUI network segment | VPC isolation | $15,000-30,000 |
| Air-gapped environments | For highest sensitivity | $50,000-100,000 |
| Network monitoring | Traffic analysis | $20,000-40,000 |
| Jump servers | Privileged access | $10,000-25,000 |

---

## Implementation Phases

### Phase 1: Enhanced Access Control and Segmentation (Months 1-3)

**Objective:** Implement dynamic access and micro-segmentation

| Week | Activities | Deliverables |
|------|------------|--------------|
| 1-2 | Select UEBA platform | Platform decision |
| 3-4 | Deploy UEBA, initial configuration | UEBA operational |
| 5-6 | Implement micro-segmentation | Network segments defined |
| 7-8 | Deploy Zero Trust architecture | Dynamic access enabled |
| 9-10 | Test and validate | Validation report |
| 11-12 | Document and tune | Updated SSP |

**Key Decisions:**
- UEBA platform selection (Exabeam, Securonix, Microsoft Sentinel)
- Micro-segmentation approach (NSX, Illumio, native AWS)
- Zero Trust architecture scope

**Investment:** $80,000-150,000

### Phase 2: Insider Threat and Threat Intelligence (Months 3-6)

**Objective:** Establish insider threat program and CTI capability

| Week | Activities | Deliverables |
|------|------------|--------------|
| 1-2 | Develop insider threat policy | Policy document |
| 3-4 | Establish CTI program | Intelligence feeds active |
| 5-6 | Integrate CTI with SIEM | Correlated intelligence |
| 7-8 | Deploy enhanced monitoring | Monitoring dashboard |
| 9-10 | Designate ITPSO | Role documented |
| 11-12 | Conduct tabletop exercise | Exercise report |

**Solo Founder Approach:**
- Owner serves as ITPSO with documented compensating controls
- MDR provider serves as monitoring capability
- Fractional security contractor for oversight

**Investment:** $60,000-120,000

### Phase 3: Threat Hunting and Red Team (Months 6-9)

**Objective:** Implement threat hunting and adversary emulation

| Week | Activities | Deliverables |
|------|------------|--------------|
| 1-2 | Deploy threat hunting platform | Platform operational |
| 3-4 | Develop hunting playbooks | Documented playbooks |
| 5-6 | Conduct initial hunts | Hunt reports |
| 7-8 | Engage red team vendor | Red team contract |
| 9-10 | Execute red team engagement | Red team report |
| 11-12 | Remediation and validation | Validated controls |

**Investment:** $100,000-200,000

### Phase 4: Supply Chain Security and Anti-Tamper (Months 9-10)

**Objective:** Implement SBOM and supply chain security

| Week | Activities | Deliverables |
|------|------------|--------------|
| 1-2 | Implement SBOM generation | SBOM operational |
| 3-4 | Deploy software composition analysis | SCA integrated |
| 5-6 | Implement code signing | Signed artifacts |
| 7-8 | Deploy integrity monitoring | FIM operational |

**Investment:** $40,000-80,000

### Phase 5: Assessment and Certification (Months 10-12)

**Objective:** C3PAO and government validation

| Week | Activities | Deliverables |
|------|------------|--------------|
| 1-2 | Pre-assessment preparation | Evidence package |
| 3-4 | C3PAO Level 3 assessment | C3PAO report |
| 5-6 | Remediation (if needed) | Remediation complete |
| 7-8 | Government validation request | DCMA submission |
| 9-12 | Government review | Level 3 certification |

**Investment:** $150,000-250,000

---

## Assessment Process

### C3PAO Assessment

| Phase | Duration | Activities |
|-------|----------|------------|
| Planning | 2 weeks | Scope, logistics |
| Documentation review | 2 weeks | SSP, evidence review |
| Technical testing | 4 weeks | Enhanced control testing |
| Advanced testing | 2 weeks | Red team validation |
| Reporting | 2 weeks | Assessment report |

**Level 3 Specific Testing:**
- Insider threat program validation
- Threat hunting capability assessment
- Adversary emulation review
- SBOM verification
- CTI integration testing

### Government Validation (DCMA)

Following C3PAO assessment, the Defense Contract Management Agency (DCMA) conducts additional government validation:

| Phase | Duration | Activities |
|-------|----------|------------|
| Package submission | 2 weeks | C3PAO report + evidence |
| DCMA review | 4-8 weeks | Government assessment |
| Site visit (possible) | 1 week | On-site validation |
| Authorization decision | 2-4 weeks | Final determination |

**Total Government Timeline:** 8-14 weeks after C3PAO

---

## Cost Breakdown

### Implementation Costs

| Category | Low Estimate | High Estimate | Notes |
|----------|--------------|---------------|-------|
| UEBA Platform | $30,000 | $60,000 | Year 1 license |
| Micro-segmentation | $30,000 | $75,000 | Implementation |
| Zero Trust Architecture | $35,000 | $70,000 | Dynamic access |
| CTI Platform | $20,000 | $50,000 | Year 1 |
| Insider Threat Program | $25,000 | $50,000 | Policy, training, tools |
| Threat Hunting | $35,000 | $75,000 | Platform, initial hunts |
| Adversary Emulation | $45,000 | $100,000 | Platform, red team |
| SBOM/Supply Chain | $35,000 | $70,000 | Tools, implementation |
| Advanced Encryption | $15,000 | $35,000 | FIPS configuration |
| Documentation | $25,000 | $50,000 | SSP updates, policies |
| **Total Implementation** | **$295,000** | **$635,000** | |

### Assessment Costs

| Category | Low Estimate | High Estimate | Notes |
|----------|--------------|---------------|-------|
| C3PAO Level 3 Assessment | $75,000 | $150,000 | Enhanced scope |
| Government Validation | $25,000 | $50,000 | DCMA review |
| Pre-assessment | $20,000 | $40,000 | Readiness check |
| Remediation contingency | $30,000 | $60,000 | Assessment findings |
| **Total Assessment** | **$150,000** | **$300,000** | |

### Annual Recurring Costs

| Category | Low Estimate | High Estimate | Notes |
|----------|--------------|---------------|-------|
| UEBA Platform | $30,000 | $60,000 | Annual license |
| Managed SOC | $60,000 | $150,000 | 24/7 coverage |
| CTI Feeds | $15,000 | $40,000 | Intelligence subscriptions |
| Red Team Exercises | $50,000 | $100,000 | Annual engagement |
| Threat Hunting | $30,000 | $75,000 | Ongoing capability |
| BAS Platform | $30,000 | $75,000 | Continuous testing |
| SCA/SBOM | $15,000 | $35,000 | Supply chain |
| Compliance Monitoring | $20,000 | $50,000 | Tools, processes |
| Training (security team) | $10,000 | $25,000 | Ongoing education |
| **Total Annual** | **$260,000** | **$610,000** | |

### Total Investment Summary

| Category | Low Estimate | High Estimate |
|----------|--------------|---------------|
| Implementation (one-time) | $295,000 | $635,000 |
| Assessment (one-time) | $150,000 | $300,000 |
| Annual recurring | $260,000 | $610,000 |
| **Total Year 1** | **$705,000** | **$1,545,000** |
| **Ongoing Annual** | **$260,000** | **$610,000** |

---

## Solo Founder Considerations

### Critical Capability Gaps

CMMC Level 3 expectations may exceed solo founder capacity:

| Requirement | Challenge | Mitigation |
|-------------|-----------|------------|
| 24/7 SOC capability | Cannot staff alone | Managed SOC service |
| Insider threat program | Single person = no insider | Document compensating controls |
| Threat hunting | Specialized skill | Contract hunting services |
| Red team exercises | Independence required | External engagement |
| ITPSO role | Conflict of interest | Fractional security officer |

### Personnel Reality Assessment

**Honest Assessment:** CMMC Level 3 is designed for organizations with dedicated security personnel. A solo founder pursuing Level 3 will need to:

1. **Contract Security Support:** Minimum $100,000-200,000/year for fractional security resources
2. **Accept Higher Costs:** Outsourcing security functions costs more than in-house at scale
3. **Plan for Growth:** Level 3 may require hiring security FTEs eventually
4. **Consider Timing:** Pursue Level 3 when revenue justifies investment

### Minimum Viable Security Team for Level 3

| Role | Option A: Contract | Option B: Hybrid |
|------|-------------------|------------------|
| Security Lead | Fractional CISO ($8K-15K/mo) | FTE hire ($150K-250K/yr) |
| SOC Analyst | Managed SOC | Managed SOC |
| Threat Hunter | Contract ($150-250/hr) | Contract |
| IR Lead | Owner + MDR | Owner + MDR |
| Compliance | CMMC RP ($150-250/hr) | CMMC RP |

**Recommendation:** Option A (full contract model) until revenue from Level 3 contracts justifies FTE security hire.

### Timeline Consideration

| Scenario | Timeline | Investment |
|----------|----------|------------|
| Aggressive (with budget) | 6-8 months | $600K-900K |
| Standard | 9-12 months | $500K-700K |
| Extended (cost-conscious) | 12-15 months | $400K-550K |

---

## Leverage Points

### Existing Project Aura Advantages

| Asset | Level 3 Benefit | Control Areas |
|-------|-----------------|---------------|
| GovCloud architecture | Isolation foundation | SC enhanced |
| 4,874 automated tests | Continuous testing | CA enhanced |
| IaC (80 CloudFormation) | Configuration baseline | CM enhanced |
| SOC 2 Evidence Service | Compliance automation | CA enhanced |
| Automated CI/CD | Secure SDLC foundation | CA enhanced |
| GuardDuty + CloudWatch | Detection foundation | IR enhanced |
| AWS Config rules | Drift detection | CM enhanced |
| KMS encryption | Crypto foundation | SC enhanced |

### AI-Specific Security Advantages

| Capability | Level 3 Relevance | Competitive Differentiation |
|------------|-------------------|----------------------------|
| Agent security testing | CA.3.12.2e specialized assessments | Demonstrates AI security maturity |
| GraphRAG monitoring | SI.3.14.7e unauthorized use | Novel AI integrity controls |
| Prompt injection testing | RA.3.11.2e adversary emulation | AI threat modeling |
| Sandbox isolation | SC.3.13.2e enhanced isolation | Defense-in-depth for AI |

---

## Risk Factors and Mitigation

### High-Risk Items

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Assessment failure | Medium | $50K-150K rework | Thorough pre-assessment |
| Budget overrun | High | Financial strain | Fixed-price contracts |
| Government timeline delay | Medium | Revenue delay | Plan for 6-month extension |
| Personnel gap | High | Cannot satisfy controls | Early contractor engagement |
| Market timing | Medium | Contract loss | Begin early in contract cycle |
| Technology complexity | Medium | Implementation delays | PoC all major platforms |

### Mitigation Strategies

1. **Assessment Risk:** Invest in comprehensive pre-assessment
2. **Budget Risk:** Lock fixed-price contracts, 25% contingency
3. **Timeline Risk:** Begin 18 months before expected contract need
4. **Personnel Risk:** Build contractor relationships early
5. **Technology Risk:** PoC critical platforms before commitment
6. **Market Risk:** Pursue Level 3 when specific contract requires it

---

## Decision Points

### Decision 1: Timing
**Question:** When to pursue Level 3?
- **Immediate:** If specific contract requires Level 3
- **Deferred:** If Level 2 is sufficient for current opportunities
- **Planned:** Start 12-18 months before Level 3 contracts expected

**Recommendation:** Defer until Level 2 proven and Level 3 contract opportunity identified.

### Decision 2: Security Staffing Model
**Question:** Contract vs. hire security personnel?
- **Full Contract:** Higher per-hour cost, flexibility
- **Hybrid:** Security lead hire, contract specialists
- **In-house:** Requires 3+ FTEs for 24/7 coverage

**Recommendation:** Full contract model initially, evaluate hybrid as revenue scales.

### Decision 3: UEBA Platform
**Question:** Which UEBA platform?
- Microsoft Sentinel (if Azure exists)
- Exabeam (standalone leader)
- Securonix (cloud-native)
- Splunk UEBA (if Splunk SIEM)

**Decision Needed By:** Month 1 of implementation

### Decision 4: Red Team Vendor
**Question:** Annual red team engagement vendor?
- SpecterOps (high-end)
- Bishop Fox (established)
- NCC Group (comprehensive)
- Coalfire (CMMC-aware)

**Decision Needed By:** Month 6 of implementation

### Decision 5: Managed SOC
**Question:** Expand existing MDR or full SOC service?
- Upgrade existing MDR (managed detection provider, CrowdStrike Complete)
- Full managed SOC (Trustwave, Secureworks)

**Recommendation:** Upgrade existing MDR for cost efficiency.

---

## Next Steps

### Prerequisites (Before Level 3)

- [ ] CMMC Level 2 certification achieved
- [ ] All Level 2 POA&M items closed
- [ ] Level 3 contract opportunity identified
- [ ] Budget approved ($400K-650K)
- [ ] Contractor relationships established

### Initiation Checklist (Month 0)

- [ ] Engage CMMC Level 3 specialist
- [ ] Complete Level 3 gap analysis
- [ ] Select UEBA platform
- [ ] Select micro-segmentation approach
- [ ] Establish contractor agreements
- [ ] Develop detailed project plan

### Success Criteria

| Milestone | Target Date | Success Metric |
|-----------|-------------|----------------|
| Enhanced access control operational | Month 3 | Dynamic access enforced |
| Insider threat program active | Month 5 | ITPSO designated, monitoring active |
| Threat hunting operational | Month 7 | Monthly hunts documented |
| Red team complete | Month 9 | Findings addressed |
| C3PAO assessment passed | Month 11 | Level 3 recommended |
| Government validation | Month 12 | Level 3 certified |

---

## Appendix A: NIST SP 800-172 Control Quick Reference

| Control ID | Requirement Summary |
|------------|---------------------|
| 3.1.2e | Dynamic risk-based access |
| 3.1.3e | Micro-segmentation |
| 3.1.20e | Dynamic network addresses |
| 3.1.21e | Automated access enforcement |
| 3.4.1e | SBOM management |
| 3.4.2e | Anti-tamper protection |
| 3.6.1e | Insider threat program |
| 3.6.2e | Cyber threat intelligence |
| 3.6.3e | Security operations center |
| 3.6.4e | Incident response teams |
| 3.9.1e | Enhanced personnel screening |
| 3.9.2e | Personnel security measures |
| 3.11.1e | Threat hunting |
| 3.11.2e | Adversary emulation |
| 3.11.3e | Security solution effectiveness |
| 3.11.4e | Supply chain risk |
| 3.12.1e | Independent assessments |
| 3.12.2e | Specialized assessments |
| 3.12.3e | Security control testing |
| 3.12.4e | Security reviews |
| 3.12.5e | Configuration verification |
| 3.12.6e | Developer security |
| 3.13.1e | Advanced encryption |
| 3.13.2e | Enhanced network isolation |

---

## Appendix B: AI-Specific Security Considerations

### Project Aura Unique Risks

| Risk Category | Description | Enhanced Control Mapping |
|---------------|-------------|-------------------------|
| Prompt Injection | Malicious prompts manipulating AI behavior | 3.12.2e Specialized Assessment |
| GraphRAG Poisoning | Contaminated graph data affecting reasoning | 3.14.7e Unauthorized Use (Level 2) + 3.11.3e |
| Agent Confusion | Multi-agent orchestration attacks | 3.12.2e Specialized Assessment |
| Sandbox Escape | Container breakout, network isolation bypass | 3.13.2e Enhanced Isolation |
| Model Extraction | Unauthorized model access/theft | 3.1.3e Micro-segmentation |
| Training Data Poisoning | Compromised training data | 3.11.4e Supply Chain Risk |

### AI Security Testing Requirements

| Test Type | Frequency | Scope |
|-----------|-----------|-------|
| Prompt injection testing | Quarterly | All LLM endpoints |
| GraphRAG integrity | Monthly | Neptune + OpenSearch |
| Agent behavior testing | Per release | Agent orchestrator |
| Sandbox escape testing | Quarterly | Container environments |
| Model integrity | Monthly | All deployed models |

---

*Document maintained by Aenea Labs. For questions, contact the compliance team.*
