# DoD Impact Level 5 (IL5) Authorization Roadmap

## Project Aura - Autonomous AI SaaS Platform

**Document Version:** 1.0
**Last Updated:** December 22, 2025
**Classification:** Public
**Target Authorization:** DoD IL5 Provisional Authorization

---

## Executive Summary

This roadmap outlines the path to Department of Defense Impact Level 5 (IL5) authorization for Project Aura. IL5 authorization enables deployment for DoD systems processing Controlled Unclassified Information (CUI) and National Security Systems (NSS) requiring higher protection levels than commercial cloud offerings provide.

**Prerequisites:**
- FedRAMP High Authorization (required baseline)
- AWS GovCloud deployment (required infrastructure)

**Timeline Estimate:** 2-4 months AFTER FedRAMP High authorization

**Incremental Investment:** $100,000-200,000 (beyond FedRAMP High)

**Strategic Value:** IL5 authorization unlocks:
- Direct DoD mission system deployments
- National Security System (NSS) hosting
- Intelligence Community adjacent workloads
- DoD contractor cloud infrastructure
- Premium government pricing tier

**Key Differentiator:** IL5 represents the highest unclassified authorization level for DoD cloud deployments. Combined with CMMC Level 2/3, IL5 positions Project Aura for the most sensitive unclassified DoD programs.

---

## Impact Level Overview

### DoD Cloud Computing Security Requirements Guide (CC SRG)

The DoD CC SRG defines six Impact Levels (IL) for cloud services:

| Impact Level | Data Type | Baseline | Typical Use |
|--------------|-----------|----------|-------------|
| IL2 | Non-CUI public/DoD | FedRAMP Moderate | Public-facing, low sensitivity |
| IL4 | CUI, mission data | FedRAMP High | Most DoD unclassified |
| IL5 | CUI, NSS, mission-critical | FedRAMP High + Delta | Higher sensitivity CUI |
| IL6 | Classified (Secret) | FedRAMP High + Classified | Secret systems |

### IL5 vs IL4 Key Differences

| Aspect | IL4 | IL5 |
|--------|-----|-----|
| Baseline | FedRAMP High | FedRAMP High + Delta |
| Data Types | CUI | CUI + NSS + Higher Sensitivity |
| Physical Separation | Logical | Dedicated/Enhanced |
| Network | Commercial interconnect | CAP connectivity |
| Personnel | US Persons | US Citizens preferred |
| Encryption | FIPS 140-2 validated | FIPS 140-2/3 Level 2+ |
| Incident Response | Standard FedRAMP | DoD-specific reporting |

---

## Current State Assessment

### Prerequisites Status

| Requirement | Status | Notes |
|-------------|--------|-------|
| FedRAMP High Authorization | Required | See FEDRAMP_HIGH_ROADMAP.md |
| AWS GovCloud Deployment | Ready | Architecture uses partition-aware ARNs |
| GovCloud-Compatible Services | 19/19 | All services IL5-capable |
| KMS Encryption | Implemented | Customer-managed keys with rotation |
| CloudTrail Logging | Implemented | 365-day retention |
| VPC Architecture | Implemented | GovCloud-compatible design |

### AWS GovCloud IL5 Service Readiness

| Service | IL5 Status | Project Aura Usage | Notes |
|---------|------------|-------------------|-------|
| Amazon EKS | IL5 Authorized | Primary compute | STIG hardening required |
| Amazon Neptune | IL5 Authorized | Graph database | Provisioned mode required |
| Amazon OpenSearch | IL5 Authorized | Vector search | Domain isolation required |
| Amazon S3 | IL5 Authorized | Object storage | Encryption required |
| Amazon DynamoDB | IL5 Authorized | Metadata storage | Encryption required |
| AWS Lambda | IL5 Authorized | Serverless compute | VPC deployment |
| Amazon Bedrock | Check Current | LLM integration | Verify IL5 status* |
| AWS KMS | IL5 Authorized | Key management | FIPS endpoints |
| Amazon CloudWatch | IL5 Authorized | Monitoring | Log encryption |
| AWS Secrets Manager | IL5 Authorized | Secret storage | FIPS endpoints |

*Note: Amazon Bedrock IL5 authorization status should be verified with AWS, as this is a newer service. Alternative: AWS SageMaker with self-deployed models.

### Gap Analysis: FedRAMP High to IL5

| Requirement | FedRAMP High State | IL5 Additional Requirement | Gap Level |
|-------------|-------------------|---------------------------|-----------|
| STIG Compliance | Not applied | Required for all systems | Major |
| FIPS 140-2/3 | Level 1 (default) | Level 2+ preferred | Moderate |
| CAP Connectivity | N/A | Required for DoD access | Major |
| Personnel Citizenship | US Persons | US Citizens preferred | Minor |
| Incident Reporting | 1-hour (High) | DoD-specific chain | Moderate |
| Network Isolation | VPC-based | Enhanced isolation | Moderate |
| CAC/PIV Authentication | Supported | Required | Moderate |

---

## IL5 Delta Requirements

### Security Technical Implementation Guides (STIGs)

STIGs are DoD-specific security configuration standards that must be applied to all systems:

#### Required STIGs

| STIG | Applicability | Estimated Effort | Notes |
|------|---------------|------------------|-------|
| Amazon EKS STIG | All EKS clusters | 40-60 hours | Node configuration |
| Container Platform STIG | All containers | 30-50 hours | Image hardening |
| Amazon Linux 2 STIG | All EC2 instances | 20-40 hours | OS hardening |
| Application Security STIG | Project Aura app | 40-80 hours | App-specific |
| Network Firewall STIG | VPC components | 20-30 hours | Security groups, NACLs |
| Database STIG | Neptune, DynamoDB | 20-40 hours | Data tier |
| Encryption STIG | All data stores | 15-25 hours | KMS configuration |
| Logging STIG | CloudTrail/CloudWatch | 15-25 hours | Log configuration |

#### STIG Compliance Process

| Phase | Activities | Duration |
|-------|------------|----------|
| 1. Assessment | Run STIG scanning tools | 1-2 weeks |
| 2. Remediation Planning | Categorize findings (CAT I, II, III) | 1 week |
| 3. Remediation | Address findings by category | 4-8 weeks |
| 4. Validation | Rescan and verify | 1-2 weeks |
| 5. Documentation | POA&M for remaining items | 1 week |

**STIG Finding Categories:**
- **CAT I:** Critical (must fix before deployment)
- **CAT II:** High (must fix or have documented waiver)
- **CAT III:** Medium (should fix, waiver acceptable)

### FIPS 140-2/3 Cryptographic Requirements

IL5 requires validated cryptographic modules:

| Component | Current State | IL5 Requirement | Action |
|-----------|---------------|-----------------|--------|
| AWS KMS | FIPS 140-2 Level 3 | Compliant | Use FIPS endpoints |
| TLS Implementation | TLS 1.3 | FIPS-validated | Verify library |
| Application Crypto | Python cryptography | FIPS mode required | Enable FIPS |
| Data Encryption | AES-256 | FIPS-validated | AWS KMS handles |
| Key Management | KMS-based | FIPS Level 2+ | Compliant |

**FIPS Endpoint Configuration:**

```yaml
# AWS GovCloud FIPS endpoints
FIPS_ENDPOINTS:
  kms: kms-fips.us-gov-west-1.amazonaws.com
  s3: s3-fips.us-gov-west-1.amazonaws.com
  dynamodb: dynamodb.us-gov-west-1.amazonaws.com  # FIPS by default in GovCloud
  neptune: neptune.us-gov-west-1.amazonaws.com
```

### DISA Cloud Access Point (CAP) Connectivity

The Cloud Access Point provides secure connectivity between DoD networks and cloud service providers:

| Component | Description | Investment |
|-----------|-------------|------------|
| CAP Registration | DISA CAP program enrollment | $5,000-10,000 |
| Network Configuration | VPN/Direct Connect to CAP | $15,000-30,000 |
| Boundary Protection | Additional firewall rules | $5,000-15,000 |
| Monitoring Integration | DoD network monitoring | $10,000-20,000 |

**CAP Architecture:**

```
DoD Network (NIPRNet/SIPRNet)
         |
    [DISA CAP]
         |
    [Direct Connect / VPN]
         |
[AWS GovCloud Transit Gateway]
         |
    [Project Aura VPC]
```

### CAC/PIV Authentication

IL5 systems must support DoD Common Access Card (CAC) and Personal Identity Verification (PIV) authentication:

| Component | Implementation | Investment |
|-----------|----------------|------------|
| Identity Provider | DoD-approved IdP integration | $15,000-30,000 |
| Certificate Validation | OCSP/CRL checking | $5,000-10,000 |
| Smart Card Readers | Hardware for admin access | $500-2,000 |
| PKI Integration | DoD PKI certificate chain | $10,000-20,000 |

**Technical Requirements:**
- X.509 certificate authentication
- Certificate revocation checking (OCSP/CRL)
- DoD PKI trust chain
- Multi-factor: CAC + PIN
- User mapping to DoD identity

### Enhanced Incident Reporting

| Requirement | FedRAMP High | IL5 Requirement |
|-------------|--------------|-----------------|
| Initial Report | 1 hour | 1 hour + DoD chain |
| Report Recipients | FedRAMP PMO | + DC3, relevant command |
| Classification | Unclassified | May involve classified channels |
| Forensics | Standard | DoD forensics support |
| Chain of Custody | Commercial standard | DoD evidence handling |

**DoD Incident Reporting Chain:**
1. Detect incident
2. Notify DC3 (DoD Cyber Crime Center) within 72 hours
3. Notify sponsoring DoD component
4. Report to FedRAMP PMO
5. Coordinate with CISA (if applicable)

---

## Implementation Phases

### Phase 1: STIG Compliance Assessment (Month 1)

**Objective:** Assess current STIG compliance and develop remediation plan

#### Week 1-2: Assessment Setup

| Activity | Deliverable | Notes |
|----------|-------------|-------|
| Obtain STIG files | STIG checklist files | From DISA STIG website |
| Deploy scanning tools | SCAP tools configured | OpenSCAP, STIG Viewer |
| Inventory systems | System inventory | All components in scope |
| Initial baseline scan | Baseline findings | Raw STIG findings |

**STIG Scanning Tools:**
- **OpenSCAP:** Open-source SCAP scanner
- **STIG Viewer:** DISA-provided assessment tool
- **AWS Security Hub:** STIG benchmark support
- **Tenable.sc:** Commercial STIG scanning

#### Week 3-4: Analysis and Planning

| Activity | Deliverable | Notes |
|----------|-------------|-------|
| Categorize findings | Finding categorization | CAT I, II, III |
| Assess remediation effort | Effort estimates | Per finding |
| Identify automation | Automated fixes | Scripts, IaC updates |
| Develop remediation plan | Project plan | Prioritized by category |

**Prioritization:**
1. **CAT I:** Block deployment, address immediately
2. **CAT II:** High priority, address before authorization
3. **CAT III:** Lower priority, document with justification

**Estimated Findings (typical new system):**
- CAT I: 5-15 findings
- CAT II: 30-60 findings
- CAT III: 50-100 findings

### Phase 2: FIPS 140-2/3 Validation (Months 1-2)

**Objective:** Ensure all cryptographic implementations are FIPS-validated

#### Week 1-2: Cryptographic Inventory

| Component | Assessment | Action Required |
|-----------|------------|-----------------|
| AWS Services | FIPS endpoint availability | Configure FIPS endpoints |
| Application Libraries | FIPS validation status | Update if needed |
| Key Management | KMS FIPS status | Verify configuration |
| TLS Configuration | FIPS cipher suites | Update configuration |

**FIPS Endpoint Configuration Tasks:**
- [ ] Update AWS SDK configuration for FIPS endpoints
- [ ] Configure boto3 for FIPS endpoints
- [ ] Update CloudFormation templates
- [ ] Verify Neptune FIPS connectivity
- [ ] Verify OpenSearch FIPS connectivity

#### Week 3-4: Implementation and Validation

| Activity | Deliverable | Notes |
|----------|-------------|-------|
| Enable FIPS mode | FIPS configuration | Application updates |
| Update endpoints | FIPS endpoints active | AWS configuration |
| Test connectivity | Validation results | All services accessible |
| Document compliance | FIPS compliance matrix | Evidence package |

**Validation Checklist:**
- [ ] All data at rest encrypted with FIPS-validated modules
- [ ] All data in transit uses FIPS-validated TLS
- [ ] Key management uses FIPS-validated KMS
- [ ] Application cryptography uses FIPS mode
- [ ] No non-FIPS crypto libraries in use

### Phase 3: CAP Connectivity Setup (Months 2-3)

**Objective:** Establish secure connectivity to DoD networks via DISA CAP

#### Week 1-2: CAP Program Enrollment

| Activity | Deliverable | Notes |
|----------|-------------|-------|
| Contact DISA | CAP program enrollment | Initial application |
| Technical review | Architecture review | CAP team consultation |
| Security documentation | Updated SSP | CAP-specific sections |
| Network planning | Network design | CAP integration architecture |

**CAP Enrollment Requirements:**
- Active FedRAMP High authorization
- AWS GovCloud deployment
- Completed security documentation
- Designated security POC
- Network architecture documentation

#### Week 3-6: Network Implementation

| Activity | Deliverable | Notes |
|----------|-------------|-------|
| Direct Connect setup | AWS Direct Connect | Or VPN alternative |
| Firewall configuration | Boundary protection | Security group updates |
| Routing configuration | Network routing | Transit gateway |
| Monitoring integration | DoD monitoring feeds | Log forwarding |
| Testing | Connectivity validation | End-to-end testing |

**Network Architecture Updates:**

| Component | Configuration |
|-----------|---------------|
| Transit Gateway | CAP attachment |
| VPC Routing | CAP route tables |
| Security Groups | CAP-specific rules |
| NACLs | Enhanced boundary |
| Flow Logs | CAP traffic logging |

#### Week 7-8: Validation and Documentation

| Activity | Deliverable | Notes |
|----------|-------------|-------|
| Connectivity testing | Test results | All services accessible |
| Security validation | Security scan | Boundary compliance |
| Documentation update | Updated network docs | Architecture diagrams |
| Operational handoff | Runbook updates | CAP operations |

### Phase 4: DoD Provisional Authorization (Months 3-4)

**Objective:** Obtain DoD IL5 Provisional Authorization (PA)

#### Authorization Package Preparation

| Document | Status | Updates Required |
|----------|--------|------------------|
| System Security Plan (SSP) | From FedRAMP | IL5 delta sections |
| Security Assessment Report (SAR) | From FedRAMP | + STIG findings |
| Plan of Action & Milestones | From FedRAMP | + STIG POA&M |
| Continuous Monitoring Plan | From FedRAMP | + DoD requirements |
| STIG Compliance Report | New | STIG scan results |
| CAP Integration Documentation | New | Network architecture |

#### DISA Authorization Process

| Step | Duration | Activities |
|------|----------|------------|
| Package Submission | 1-2 weeks | Submit IL5 package |
| Initial Review | 2-3 weeks | DISA preliminary review |
| Technical Review | 2-4 weeks | Technical assessment |
| Risk Acceptance | 1-2 weeks | AO decision |
| PA Issuance | 1 week | Authorization letter |

**Total DISA Timeline:** 6-12 weeks

#### Authorization Success Factors

| Factor | Importance | Action |
|--------|------------|--------|
| Clean FedRAMP High | Critical | No open CAT I findings |
| STIG Compliance | Critical | CAT I remediated, CAT II documented |
| CAP Connectivity | High | Operational and tested |
| CAC/PIV Support | High | Implemented and validated |
| Documentation Quality | High | Complete and accurate |
| Sponsor Support | Medium | Active agency sponsorship |

---

## Cost Breakdown

### Implementation Costs

| Category | Low Estimate | High Estimate | Notes |
|----------|--------------|---------------|-------|
| STIG Assessment Tools | $5,000 | $15,000 | Scanning tools, licenses |
| STIG Remediation | $20,000 | $40,000 | Technical implementation |
| FIPS Configuration | $10,000 | $20,000 | Endpoint updates, testing |
| CAP Connectivity | $25,000 | $50,000 | Direct Connect, configuration |
| CAC/PIV Integration | $15,000 | $35,000 | IdP integration, PKI |
| Documentation | $10,000 | $20,000 | SSP updates, STIG docs |
| Consulting Support | $15,000 | $30,000 | IL5 specialist |
| **Total Implementation** | **$100,000** | **$210,000** | |

### Ongoing Costs (Annual)

| Category | Low Estimate | High Estimate | Notes |
|----------|--------------|---------------|-------|
| CAP Connectivity | $12,000 | $30,000 | Direct Connect fees |
| STIG Compliance Monitoring | $5,000 | $15,000 | Continuous scanning |
| DoD-Specific Monitoring | $5,000 | $10,000 | Additional logging |
| CAC/PIV Infrastructure | $3,000 | $8,000 | Certificate management |
| Annual Reassessment | $20,000 | $40,000 | DISA review support |
| **Total Annual** | **$45,000** | **$103,000** | |

### Cost Comparison: FedRAMP High to IL5

| Cost Category | FedRAMP High Only | FedRAMP High + IL5 | Delta |
|---------------|-------------------|--------------------| ------|
| Initial (Year 1) | $250,000-350,000 | $350,000-560,000 | +$100,000-210,000 |
| Annual Recurring | $77,000-155,000 | $122,000-258,000 | +$45,000-103,000 |

---

## Solo Founder Considerations

### IL5 Personnel Requirements

| Requirement | Challenge | Mitigation |
|-------------|-----------|------------|
| US Citizenship | May be required for admin access | Verify citizenship status |
| Security Clearance | May be required for some contracts | Plan for clearance process |
| 24/7 Availability | DoD incident response | MDR with DoD experience |
| CAC Holder | Required for CAP administration | Obtain CAC if sponsor available |

### Clearance Considerations

| Factor | Details |
|--------|---------|
| Clearance Requirement | IL5 may not require clearance for CSP admins |
| Contract Dependency | Specific contracts may require clearance |
| Timeline | Clearance process: 3-12+ months |
| Sponsorship | Requires government or contractor sponsor |
| Investigation | SF-86, background investigation |

**Recommendation:** Pursue IL5 without clearance initially. Clearance requirements are typically contract-specific rather than IL5-mandated.

### Operational Challenges

| Challenge | Impact | Mitigation |
|-----------|--------|------------|
| DoD network access | Requires CAC for direct access | Contract with CAC-holding support |
| Incident response | DoD-specific procedures | Document DoD chain, train MDR |
| STIG maintenance | Continuous compliance | Automated scanning, IaC |
| CAP operations | Dedicated connectivity | Managed network service |

---

## Leverage Points

### Existing Advantages

| Asset | IL5 Benefit | Application |
|-------|-------------|-------------|
| GovCloud Architecture | Ready for IL5 infrastructure | Deploy to GovCloud |
| Partition-Aware ARNs | No refactoring needed | Seamless deployment |
| KMS Encryption | FIPS-ready foundation | Configure FIPS endpoints |
| IaC (CloudFormation) | Reproducible STIG compliance | Embed STIG in templates |
| Automated Testing | STIG validation automation | Extend test coverage |
| VPC Architecture | Network isolation foundation | Add CAP connectivity |

### FedRAMP High Foundation

| FedRAMP High Control | IL5 Benefit |
|----------------------|-------------|
| 421 NIST 800-53 controls | Baseline satisfied |
| SSP documentation | Foundation for IL5 SSP |
| 3PAO assessment | Recent security validation |
| Continuous monitoring | Extend to DoD requirements |
| Incident response plan | Extend to DoD chain |

### Project Aura AI Considerations

| Capability | IL5 Relevance |
|------------|---------------|
| LLM Integration | Verify Bedrock IL5 status |
| GraphRAG | Neptune IL5 authorized |
| Agent Orchestration | EKS STIG compliance |
| Sandbox Isolation | Enhanced container security |

---

## Risk Factors and Mitigation

### Implementation Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| STIG finding volume | Medium | 2-4 week delay | Early assessment |
| CAP timeline | Medium | 4-8 week delay | Early enrollment |
| Bedrock IL5 status | Unknown | Architecture impact | Verify early, plan alternatives |
| DISA timeline | Medium | 4-8 week delay | Early package submission |
| CAC requirement | Low | Access limitation | Sponsor relationship |

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| STIG breaks functionality | Medium | Development rework | Test in staging |
| FIPS mode performance | Low | Latency increase | Performance testing |
| CAP connectivity issues | Low | Access problems | Redundant connectivity |
| Service IL5 status changes | Low | Architecture changes | Monitor AWS announcements |

### Mitigation Strategies

1. **Assessment Risk:** Conduct STIG assessment while FedRAMP is in progress
2. **Timeline Risk:** Begin CAP enrollment immediately after FedRAMP ATO
3. **Technical Risk:** Test all STIG and FIPS changes in non-production
4. **Service Risk:** Verify Bedrock IL5 status early; plan SageMaker alternative
5. **Sponsor Risk:** Cultivate DoD sponsor relationship during FedRAMP

---

## Decision Points

### Decision 1: Timing
**Question:** When to pursue IL5?
- **Immediately after FedRAMP High:** Most efficient if DoD market is primary target
- **Deferred:** If commercial/civilian federal is primary market

**Recommendation:** Begin IL5 preparation during FedRAMP Phase 5 (assessment), execute immediately after ATO.

### Decision 2: Bedrock Strategy
**Question:** Bedrock IL5 verification vs. SageMaker alternative?
- **Bedrock:** Simpler integration if IL5 authorized
- **SageMaker:** Guaranteed IL5, more operational complexity

**Action:** Verify Bedrock IL5 status with AWS by Month 1.

### Decision 3: CAP Connectivity Method
**Question:** AWS Direct Connect vs. VPN?
- **Direct Connect:** Lower latency, higher reliability, higher cost
- **VPN:** Lower cost, potentially higher latency

**Recommendation:** Direct Connect for production IL5 workloads.

### Decision 4: CAC Infrastructure
**Question:** Build vs. buy CAC/PIV integration?
- **Build:** More control, higher effort
- **Buy:** IdP with DoD PKI support (Okta, Azure AD)

**Recommendation:** Use existing IdP with DoD PKI integration capability.

---

## IL5 and Other Certifications

### Certification Relationships

```
                    CMMC Level 2
                         |
                         v
                    CMMC Level 3
                         |
        +----------------+----------------+
        |                                 |
        v                                 v
   FedRAMP High -----------------> DoD IL5
                                         |
                                         v
                                    DoD IL6 (Classified)
```

### Combined Certification Strategy

| Certification | Prerequisites | Market Access |
|---------------|---------------|---------------|
| CMMC Level 2 | None | Defense contractors (CUI) |
| CMMC Level 3 | Level 2 | Critical defense programs |
| FedRAMP High | None | All federal agencies (High impact) |
| IL5 | FedRAMP High | DoD mission systems |

**Optimal Path for DoD Market:**
1. CMMC Level 2 (enables subcontracting)
2. FedRAMP High (enables federal + IL4 DoD)
3. IL5 (enables sensitive DoD programs)
4. CMMC Level 3 (enables critical programs)

---

## Next Steps

### Prerequisites (Before IL5)

- [ ] FedRAMP High ATO achieved
- [ ] AWS GovCloud deployment operational
- [ ] DoD sponsor identified
- [ ] Budget approved ($100K-200K incremental)
- [ ] Verify Bedrock IL5 authorization status

### Initiation Checklist (Month 0)

- [ ] Obtain STIG files from DISA
- [ ] Deploy STIG scanning tools
- [ ] Begin CAP enrollment process
- [ ] Engage IL5 specialist consultant
- [ ] Update project plan with IL5 phase

### Success Criteria

| Milestone | Target Date | Success Metric |
|-----------|-------------|----------------|
| STIG assessment complete | Month 1 | Findings categorized |
| CAT I findings remediated | Month 2 | Zero CAT I open |
| CAP connectivity operational | Month 3 | DoD network accessible |
| IL5 package submitted | Month 3 | DISA acceptance |
| IL5 PA issued | Month 4 | Authorization letter |

---

## Appendix A: STIG Quick Reference

### Key STIGs for Cloud Systems

| STIG ID | Title | Version |
|---------|-------|---------|
| Amazon_EKS_STIG | Amazon Elastic Kubernetes Service | V1RX |
| Container_Platform_STIG | Container Platform SRG | V1RX |
| Amazon_Linux_2_STIG | Amazon Linux 2 | V2RX |
| Application_Security_SRG | Application Security | V5RX |
| Network_Firewall_STIG | Network Firewall | V1RX |
| DBMS_SRG | Database Management System | V3RX |
| Encryption_Policy | Encryption Policy | V2RX |

### STIG Resources

- DISA STIG Library: https://public.cyber.mil/stigs/
- STIG Viewer: https://public.cyber.mil/stigs/srg-stig-tools/
- OpenSCAP: https://www.open-scap.org/

---

## Appendix B: CAP Architecture Reference

### Network Topology

```
[DoD NIPRNet]
      |
[DISA CAP Node]
      |
[AWS Direct Connect]
      |
[Transit Gateway]
      |
+-----+-----+
|           |
[Aura VPC]  [Management VPC]
```

### Required Network Components

| Component | Purpose | Configuration |
|-----------|---------|---------------|
| Direct Connect | CAP connectivity | 1Gbps minimum |
| Transit Gateway | Network hub | Multi-VPC support |
| VPN Backup | Redundancy | Site-to-site VPN |
| Firewall | Boundary protection | Security groups + NACLs |
| Flow Logs | Traffic monitoring | All VPC traffic |

---

## Appendix C: DoD Incident Reporting

### Reporting Timeline

| Event | Timeline | Recipient |
|-------|----------|-----------|
| Detection | Immediate | Internal SOC |
| Initial Triage | 15 minutes | MDR provider |
| Preliminary Report | 1 hour | DC3, Sponsor |
| Detailed Report | 72 hours | DC3, FedRAMP PMO |
| Final Report | Post-incident | All stakeholders |

### Contact Information

| Organization | Contact Method | Purpose |
|--------------|----------------|---------|
| DoD Cyber Crime Center (DC3) | dc3.mil | Incident reporting |
| DISA | disa.mil | CAP support |
| CISA | us-cert.gov | Federal coordination |
| FedRAMP PMO | fedramp.gov | FedRAMP reporting |

---

*Document maintained by Aenea Labs. For questions, contact the compliance team.*
