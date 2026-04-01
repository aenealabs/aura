# FAA DO-178C Gap Analysis for Aircraft Engine Control Software

**Product:** Project Aura by Aenea Labs
**Version:** 1.0
**Last Updated:** February 2026
**Audience:** Aviation Certification Engineers, DERs (Designated Engineering Representatives), ODA Unit Members, Enterprise Decision-Makers Evaluating Aura for Aerospace Applications
**Classification:** Public -- Not a Formal Certification Plan

---

> **Disclaimer:** This document is an internal gap analysis prepared by Aenea Labs engineering staff. It does not constitute a Plan for Software Aspects of Certification (PSAC), a formal means of compliance proposal, or a commitment to any certification timeline. All assessments of DO-178C alignment are preliminary and would require validation by an FAA-authorized DER or ODA unit before any certification activity could proceed. Regulatory interpretations expressed herein are based on publicly available guidance and do not reflect official FAA or EASA positions.

---

## 1. Executive Summary

### Purpose

This document provides an honest, technically rigorous gap analysis comparing Project Aura's current development assurance capabilities against the requirements of RTCA DO-178C ("Software Considerations in Airborne Systems and Equipment Certification") for aircraft engine Full Authority Digital Engine Control (FADEC) and Electronic Engine Control (EEC) software. The analysis covers both commercial (FAA/EASA) and military (DoD) certification pathways.

### Scope

The analysis targets FADEC/EEC software at **Design Assurance Level A (Catastrophic)** and **DAL B (Hazardous)**, which represent the most stringent certification requirements in aviation software. FADEC software typically receives DAL A classification because loss of engine thrust control constitutes a catastrophic failure condition under ARP4761 safety assessment methodology.

### Bottom Line

**Aura is not currently certifiable as a DO-178C development or verification tool.** This is neither surprising nor unique to Aura -- no AI code generation tool from any vendor has ever been certified for safety-critical airborne software use. Neither the FAA nor EASA has published approved compliance means for AI/ML-based development tools under DO-330 (Software Tool Qualification Considerations).

However, Aura's governance architecture provides a materially stronger foundation for eventual aerospace certification than any comparable platform in the market. Its human-in-the-loop approval workflows, deterministic constraint scoring, defense-in-depth enforcement model, 7-year immutable audit retention, and multi-agent separation of function align conceptually with aviation safety engineering principles -- even where they do not yet satisfy the formal evidentiary requirements of DO-178C.

This analysis identifies **7 critical gaps**, **8 partial gaps**, and **2 areas of conceptual alignment** across the full DO-178C life cycle. The single most significant barrier is DO-330 tool qualification for LLM-based agents, which depends on regulatory evolution that has not yet occurred.

---

## 2. Applicable Standards and Regulatory Context

### 2.1 Standards Hierarchy

Aircraft engine control software certification involves an interlocking set of standards. The following table presents the hierarchy from system level down to tool and supplement level.

| Standard | Title | Scope | Authority |
|----------|-------|-------|-----------|
| ARP4754A | Guidelines for Development of Civil Aircraft and Systems | System-level development assurance; FDAL/IDAL assignment | SAE/EUROCAE (Dec 2010) |
| ARP4761 | Guidelines and Methods for Conducting the Safety Assessment Process | FHA, PSSA, SSA; failure condition classification | SAE/EUROCAE |
| DO-178C | Software Considerations in Airborne Systems and Equipment Certification | Primary software certification standard | RTCA; FAA recognized via AC 20-115D (July 2017) |
| DO-330 | Software Tool Qualification Considerations | Tool qualification levels TQL-1 through TQL-5 | RTCA (domain-independent supplement to DO-178C) |
| DO-331 | Model-Based Development and Verification Supplement | MBD considerations for DO-178C | RTCA |
| DO-332 | Object-Oriented Technology and Related Techniques Supplement | OOT considerations for DO-178C | RTCA |
| DO-333 | Formal Methods Supplement | Formal methods as alternative/complement to testing | RTCA |
| AC 33.28-3 | Advisory Circular for 14 CFR 33.28 | Engine control system certification guidance | FAA |
| MIL-STD-882E | System Safety | Military system safety engineering | DoD |
| FACE Technical Standard | Future Airborne Capability Environment | Military software portability | DoD |

### 2.2 Design Assurance Levels

DO-178C defines five Design Assurance Levels based on the severity of failure conditions identified through ARP4761 safety assessment.

| DAL | Failure Condition | Failure Rate | Objectives | Key Requirement |
|-----|-------------------|-------------|------------|-----------------|
| A | Catastrophic | <= 1 x 10^-9 per flight hour | 71 | MC/DC + object code verification; full independence |
| B | Hazardous | <= 1 x 10^-7 per flight hour | 69 | MC/DC; independence required |
| C | Major | <= 1 x 10^-5 per flight hour | 62 | Statement + decision coverage |
| D | Minor | Advisory | 26 | Statement coverage |
| E | No Effect | N/A | 0 | No software objectives |

### 2.3 Why FADEC Software Is Typically DAL A

FADEC software exercises full authority over engine fuel metering, variable geometry, bleed valves, and thrust management. A FADEC malfunction that causes uncommanded thrust reduction, engine shutdown, or uncontrolled acceleration during critical flight phases (takeoff, go-around) constitutes a catastrophic failure condition under ARP4761 Functional Hazard Assessment. Dual-channel FADEC architectures may allow specific functions within a channel to be classified at DAL B where the redundant channel provides adequate mitigation, but the primary control law and fuel metering functions are typically DAL A.

AC 33.28-3 provides engine-specific guidance reinforcing that FADEC software must satisfy the full rigor of DO-178C at the assigned DAL.

### 2.4 Commercial vs. Military Certification Paths

**Commercial (FAA/EASA):** Certification follows 14 CFR Part 33 (engines) with DO-178C as the recognized means of compliance via AC 20-115D. The applicant submits a PSAC, negotiates means of compliance with the FAA Aircraft Certification Office (ACO), and provides evidence through formal Stage of Involvement reviews (SOI #1 through SOI #4).

**Military (DoD):** MIL-STD-882E governs system safety but increasingly adopts DO-178C for software assurance because, as stated in the standard, "such guidelines enable a more robust, safe, and secure aircraft for the warfighter." The F-35 F135 engine uses DO-178B-certified FADEC software. Military programs may also require FACE Technical Standard conformance for portability and MIL-STD-1553/ARINC 664 data bus compliance.

### 2.5 Current Regulatory Position on AI in Certification

The aviation regulatory landscape for AI/ML tools is unresolved.

**FAA Position:** The FAA has stated that "assuring the safety of such systems cannot rely on traditional aviation design assurance" and has published an AI Roadmap acknowledging the need for new guidance. No approved compliance means exists for AI/ML-based development or verification tools under DO-330. The FAA continues to conduct AI Technical Exchange Meetings with industry but has not issued rulemaking.

**EASA Position:** EASA published its Artificial Intelligence Concept Paper Issue 2 (March 2024), which covers Level 1 (human assistance) and Level 2 (human-AI collaboration) applications. Level 3 guidance (advanced AI automation) is expected in subsequent revisions. EASA's framework focuses on learning assurance and operational domain definition but does not yet address AI tool qualification under DO-330 equivalents (ED-215).

**Industry Reality:** No AI code generation tool -- from any vendor, in any form -- has been qualified under DO-330 or certified for use in safety-critical airborne software development. This is not a limitation specific to Aura; it reflects the current state of an entire industry.

---

## 3. Gap Analysis Matrix

This section provides a detailed assessment of Aura's capabilities against each DO-178C life cycle process. Gap severity is classified as follows:

| Severity | Definition |
|----------|------------|
| **CRITICAL** | Capability absent or fundamentally misaligned; would prevent certification |
| **PARTIAL** | Conceptually aligned capability exists but does not meet DO-178C formal requirements |
| **NONE** | Capability meets or closely approximates DO-178C requirements |

### 3.1 Software Planning Process (DO-178C Section 4)

The Planning Process establishes the framework for all subsequent development and verification activities. DO-178C requires five formal planning documents.

| Planning Artifact | DO-178C Requirement | Aura Current Capability | Gap Severity | Notes |
|-------------------|---------------------|------------------------|--------------|-------|
| PSAC (Plan for Software Aspects of Certification) | Defines software overview, certification basis, compliance strategy, SOI schedule | Not generated | **CRITICAL** | No certification authority interface exists. PSAC is the foundational document negotiated with the ACO/DER. |
| SDP (Software Development Plan) | Defines development processes, standards, environment, transition criteria | Not generated in DO-178C format. ADR-070 policy-as-code governs development workflow. | **CRITICAL** | Aura's internal development governance is extensive but not structured per DO-178C Section 11.2. |
| SVP (Software Verification Plan) | Defines verification methods, tools, environment, transition criteria, independence | Not generated. Sandbox validation pipeline performs verification but without DO-178C planning structure. | **CRITICAL** | Sandbox performs 5-category validation but not per a formal verification plan with structural coverage objectives. |
| SCMP (Software Configuration Management Plan) | Defines CM process, baselines, problem reporting, archive/retrieval | ADR-070 provides version-controlled YAML policies, Git-based change control, and 7-year DynamoDB audit retention. | **PARTIAL** | Strong conceptual alignment but not formatted per DO-178C Section 11.4. Lacks formal baseline identification scheme and controlled media definitions. |
| SQAP (Software Quality Assurance Plan) | Defines QA activities, authority, independence, compliance monitoring | Not generated. No independent QA function defined. | **CRITICAL** | DO-178C requires an independent QA authority with documented audit procedures. Aura's ADR-070 CI/CD validation provides process assurance but lacks organizational QA independence. |

### 3.2 Software Development Process (DO-178C Sections 5.1-5.4)

| Process Area | DAL A Requirement | Aura Current Capability | Gap Severity | Notes |
|--------------|-------------------|------------------------|--------------|-------|
| **Software Requirements Process** (5.1) | Formal high-level requirements (HLR) derived from system requirements with traceability to ARP4754A system functions | Aura operates on existing source code, not formal requirements. No Software Requirements Data (SRD) generation. | **CRITICAL** | Aura's code analysis via GraphRAG (Neptune CALL_GRAPH + OpenSearch embeddings) maps code relationships but does not produce or trace to formal requirements. DO-178C requires requirements-driven development, not code-driven remediation. |
| **Software Design Process** (5.2) | Formal Software Design Description (SDD) with low-level requirements (LLR) traceable to HLR | Aura generates patches, not design descriptions. No SDD production. | **CRITICAL** | GraphRAG captures code structure (dependencies, inheritance, call graphs) which parallels design documentation content, but is not formatted or managed as a DO-178C SDD. |
| **Software Coding Standards** (5.3) | Defined coding standards with compliance verification | Constitutional AI (ADR-063) enforces 16 principles including code quality. Sandbox runs Semgrep, Bandit, and linting. | **PARTIAL** | Aura enforces coding standards but not aviation-specific standards (e.g., MISRA C for engine software, JPL C Coding Standard). DO-178C DAL A requires demonstrated compliance with project-defined coding standards through independent review. |
| **Integration Process** (5.4) | Hardware/software integration testing per documented plan | Sandbox validates integration in isolated environment (separate VPC, 4-layer isolation, 5-category validation). | **PARTIAL** | Sandbox integration testing validates software behavior but does not address hardware-software integration, target computer testing, or DO-178C integration test criteria. FADEC software must be tested on representative target hardware (e.g., engine control unit). |

### 3.3 Software Verification Process (DO-178C Section 6)

| Verification Area | DAL A Requirement | Aura Current Capability | Gap Severity | Notes |
|-------------------|-------------------|------------------------|--------------|-------|
| **Reviews and Analyses** (6.3.1-6.3.3) | Independent reviews of requirements, design, code against standards; documented review records | Constitutional AI (ADR-063) performs post-generation review with 16 principles. CGE (ADR-081) provides deterministic scoring. Separate Reviewer agent examines Coder output. | **PARTIAL** | Automated review mechanisms exist but do not satisfy DO-178C independence requirements (see Section 3.3.7 below). Review records are generated but not in DO-178C format. |
| **Requirements-Based Testing** (6.4.2) | Test cases derived from HLR and LLR; normal range, boundary, and robustness testing | Aura tests patches for correctness, security, and performance in sandbox. Not structured as requirements-based test cases. | **CRITICAL** | DO-178C requires each test case to trace to a specific requirement. Aura's sandbox testing validates functional correctness but is not organized by requirement. |
| **Requirements-Based Test Coverage** (6.4.4.1) | Demonstrate that test cases cover all HLR and LLR | Not addressed. Aura does not track requirements-to-test-case coverage. | **CRITICAL** | No mechanism to verify that all requirements have associated test cases and that all test cases trace to requirements. |
| **Structural Coverage -- Statement** (6.4.4.2a) | 100% statement coverage of source code exercised by requirements-based tests | Aura requires 70% statement coverage in sandbox (pyproject.toml `fail_under = 70`). | **CRITICAL** | 70% is insufficient for any DO-178C DAL. DAL D requires statement coverage; DAL A requires 100% statement coverage from requirements-based tests, with analysis of any gaps. |
| **Structural Coverage -- Decision** (6.4.4.2b) | 100% decision coverage | Not measured. | **CRITICAL** | Required for DAL A, B, and C. Not currently part of Aura's validation pipeline. |
| **Structural Coverage -- MC/DC** (6.4.4.2c) | 100% Modified Condition/Decision Coverage | Not measured. | **CRITICAL** | Required for DAL A and B. MC/DC is the most rigorous structural coverage criterion in DO-178C. Each condition in a decision must be shown to independently affect the outcome. No MC/DC tooling integrated. |
| **Object Code Verification** (6.4.4.2d) | Verify object code when compiler generates code not directly traceable to source | Not addressed. | **CRITICAL** | Required for DAL A when the compiler generates untraceable code (e.g., exception handling, runtime checks). FADEC compilers commonly require this analysis. |
| **Independence** (6.3.6, Table A-5) | Verification activities performed by personnel independent from development | Aura uses separate Coder, Reviewer, and Validator agents, providing functional separation. However, all agents share the same LLM infrastructure (Bedrock/Claude). | **CRITICAL** | DO-178C independence means the verification person is not the person who developed the item. Agent separation provides functional independence, but shared LLM infrastructure means a common mode failure (e.g., systematic LLM bias) could affect both development and verification outputs. A DO-178C assessor would likely not accept agents running on the same model as constituting independent verification. |

### 3.4 Configuration Management Process (DO-178C Section 7)

| CM Area | DAL A Requirement | Aura Current Capability | Gap Severity | Notes |
|---------|-------------------|------------------------|--------------|-------|
| **Configuration Identification** (7.2.1) | Unique identification of all configuration items; baseline identification | ADR-070 provides version-controlled YAML policies in Git. SBOM (ADR-076) generates CycloneDX/SPDX with Sigstore signing. Private ECR base images tracked. | **PARTIAL** | Git provides version control and change tracking. SBOM generation addresses software composition. However, no formal Configuration Identification Index (CII) or baseline naming convention per DO-178C exists. |
| **Baselines and Traceability** (7.2.2) | Formal baselines at defined milestones; controlled changes between baselines | Git branches and tags provide baseline capability. CI/CD pipeline (ADR-070) enforces 3-stage validation before merge. | **PARTIAL** | Conceptually aligned. Lacks DO-178C-specific baseline definitions (e.g., requirements baseline, design baseline, product baseline) and formal baseline audit procedures. |
| **Problem Reporting** (7.2.3) | Formal problem reporting with tracking, classification, and closure | GitHub Issues with structured tracking. DynamoDB audit logs with 7-year retention. | **PARTIAL** | Problem reporting exists but not structured per DO-178C problem report requirements (classification, impact analysis, verification of closure, traceability to affected configuration items). |
| **Change Control** (7.2.4) | Formal change review and approval; impact analysis | HITL approval workflow (5-stage) with 3 decision options. ADR-032 autonomy framework with 5 hardcoded guardrails. | **PARTIAL** | Strong conceptual alignment. Change control process is mature but not documented as a DO-178C change control board (CCB) process with formal impact analysis records. |
| **Change Review** (7.2.5) | Independent review of changes for correctness and compliance | Reviewer agent + Constitutional AI (ADR-063) + CGE deterministic scoring (ADR-081). | **PARTIAL** | Multi-layer review exists but shares the independence limitations noted in Section 3.3. |
| **Configuration Status Accounting** (7.2.6) | Record of configuration item history, baseline membership, change status | DynamoDB audit logs with 7-year retention. Git history provides full change record. | **PARTIAL** | Data exists but not organized as DO-178C configuration status accounting reports. |
| **Archive and Retrieval** (7.2.7) | Controlled archive; retrieval demonstrated; media integrity verified | S3 with appropriate retention policies. DynamoDB for structured data. | **PARTIAL** | Archive capability exists. Lacks formal archive integrity verification procedures and periodic retrieval testing documentation required by DO-178C. |
| **Software Load Control** (7.2.8) | Controlled loading onto target hardware; part number and version verification | Not addressed. Aura deploys to cloud environments, not embedded engine control hardware. | **CRITICAL** | FADEC software requires controlled loading onto the Engine Control Unit (ECU) with hardware/software compatibility verification. This is outside Aura's current scope. |

### 3.5 Quality Assurance Process (DO-178C Section 8)

| QA Area | DAL A Requirement | Aura Current Capability | Gap Severity | Notes |
|---------|-------------------|------------------------|--------------|-------|
| **QA Authority and Independence** (8.1) | Independent QA function with authority to identify and escalate non-conformances | No independent QA function defined. | **CRITICAL** | DO-178C QA must be organizationally independent from development. Aura has no QA role defined in its governance model. |
| **Software Conformity Review** (8.2) | Verify development and integral process outputs conform to plans and standards | ADR-070 CI/CD validation provides automated conformity checking (schema validation, security analysis, attack simulation). | **PARTIAL** | Automated conformity checks exist but are not organized as DO-178C conformity reviews with formal records. |
| **Process Compliance Audits** (8.3) | Periodic audits of process compliance | ADR-083 runtime monitoring provides continuous process observation. PolicyGraphReconciler performs daily drift detection. | **PARTIAL** | Continuous monitoring parallels audit intent but is not structured as DO-178C process compliance audits with audit records, findings, and corrective actions. |
| **SCM Process Assurance** (8.4) | QA monitoring of CM process effectiveness | Not addressed as a distinct QA activity. | **CRITICAL** | CM process monitoring exists (ADR-070) but is not performed by an independent QA function. |

### 3.6 Certification Liaison Process (DO-178C Section 9)

| Liaison Area | DAL A Requirement | Aura Current Capability | Gap Severity | Notes |
|-------------|-------------------|------------------------|--------------|-------|
| **Means of Compliance** (9.1) | PSAC establishes proposed means of compliance; negotiated with certification authority | Not addressed. | **CRITICAL** | No engagement with FAA ACO, DER, or ODA unit. |
| **Compliance Substantiation** (9.2) | Evidence that objectives are satisfied; stage of involvement reviews (SOI #1-#4) | Not addressed. | **CRITICAL** | No SOI schedule, no formal compliance evidence package. |
| **SAS (Software Accomplishment Summary)** (9.3) | Final certification evidence package summarizing all DO-178C activities and compliance status | Not generated. | **CRITICAL** | The SAS is the definitive document submitted to the certification authority. |
| **Issue Papers / Special Conditions** (9.4) | Resolution of novel certification questions | Not addressed. | **CRITICAL** | Use of AI/ML tools in DO-178C development would almost certainly require issue papers or special conditions. |

### 3.7 Tool Qualification (DO-330)

DO-330 defines tool qualification requirements based on three criteria and the software DAL. For FADEC software at DAL A, Aura's agents would face the following qualification requirements.

| Aura Component | DO-330 Criteria | Justification | Required TQL at DAL A | Aura Status | Gap Severity |
|----------------|----------------|---------------|----------------------|-------------|--------------|
| **Coder Agent** | Criteria 1 (output is part of airborne software; could insert errors) | Coder Agent generates code that would become part of FADEC software | **TQL-1** | Not qualified | **CRITICAL** |
| **Reviewer Agent** | Criteria 2 (automates verification; could fail to detect errors; eliminates/reduces other verification) | Reviewer Agent performs automated code review that could substitute for human review | **TQL-2** | Not qualified | **CRITICAL** |
| **Validator Agent** | Criteria 2/3 (automates testing; could fail to detect errors) | Validator Agent runs tests in sandbox; results inform approval decisions | **TQL-2** (if test results eliminate human testing) / **TQL-5** (if results supplement but do not replace) | Not qualified | **CRITICAL** |
| **CGE Scoring** (ADR-081) | Criteria 3 (could fail to detect errors; does not eliminate other processes) | Deterministic scoring informs approval but does not replace verification | **TQL-5** | Not qualified but closest to qualifiable due to deterministic behavior | **PARTIAL** |
| **GraphRAG Engine** | Criteria 1/2 (provides context that influences code generation and review) | GraphRAG retrieval directly influences Coder and Reviewer agent outputs | **TQL-1** (if context errors could cause code errors) | Not qualified | **CRITICAL** |

**Fundamental Challenge -- LLM Non-Determinism:**

DO-330 Section 3.3 requires Tool Operational Requirements (TOR) that define the tool's expected behavior. Qualification testing then verifies the tool produces correct outputs for defined inputs. LLMs are inherently non-deterministic -- the same input can produce different outputs across invocations due to sampling, floating-point non-determinism, and model updates. This fundamental characteristic conflicts with the deterministic behavior expectation underlying DO-330 tool qualification.

Aura's Constraint Geometry Engine (ADR-081) provides a partial mitigation: its scoring uses frozen embeddings, SHA-256 cache keys, and pure arithmetic to guarantee that identical inputs always produce identical scores. This deterministic decision boundary is architecturally significant -- it means the final accept/reject decision can be audited reproducibly even when the upstream LLM outputs vary. However, the CGE scores the LLM output; it does not make the LLM output itself deterministic.

**No LLM-based tool has been qualified under DO-330 at any TQL level.** This gap is not a matter of engineering effort alone -- it requires regulatory framework development that has not yet occurred.

### 3.8 Traceability (DO-178C Section 5.5, Table A-7)

| Traceability Chain | DAL A Requirement | Aura Current Capability | Gap Severity | Notes |
|-------------------|-------------------|------------------------|--------------|-------|
| System Req to HLR | Required; bidirectional | Not addressed. Aura operates on existing code, not system requirements from ARP4754A. | **CRITICAL** | FADEC system requirements flow from engine control laws, fuel system models, and aircraft-level requirements. Aura has no system requirements interface. |
| HLR to LLR | Required; bidirectional | Not addressed. No formal requirements hierarchy. | **CRITICAL** | GraphRAG maps code relationships (CALL_GRAPH, DEPENDENCIES, INHERITANCE, REFERENCES) but these are code-level traces, not requirements-level traces. |
| LLR to Source Code | Required; bidirectional | GraphRAG provides code structural analysis including call graphs, dependencies, and inheritance chains. | **PARTIAL** | If low-level requirements were mapped to code modules, GraphRAG could support this traceability chain. The infrastructure exists conceptually but requirements are not defined. |
| Source Code to Object Code | Required at DAL A (bidirectional when untraceable code exists) | Not addressed. | **CRITICAL** | FADEC compilation for embedded targets (e.g., PowerPC, ARM Cortex-R) requires source-to-object traceability. Outside Aura's current scope. |
| Requirements to Test Cases | Required; bidirectional | Not addressed. Aura tests for correctness but does not link tests to formal requirements. | **CRITICAL** | Sandbox test results are not organized by requirement. |
| Test Cases to Test Results | Required | Sandbox produces test results with pass/fail status, coverage metrics, and execution logs. | **PARTIAL** | Test execution and result capture exists but is not formatted as DO-178C SVCP/SVR. |

### 3.9 Formal Methods (DO-333)

| Formal Method | Status in Aura | Gap Assessment | Notes |
|---------------|----------------|----------------|-------|
| Theorem Proving | Not implemented | Gap (not strictly required) | Increasingly expected for DAL A FADEC software. Tools like Isabelle/HOL, Coq, and ACL2 are used in modern engine control certification. |
| Model Checking | Not implemented | Gap (not strictly required) | Used to verify state machine behavior in engine control modes (startup, idle, takeoff, shutdown, fault management). |
| Abstract Interpretation | Not implemented | Gap (not strictly required) | Tools like Polyspace and Astree are commonly used for DAL A runtime error analysis. Accepted as a complement to or partial substitute for testing. |
| Deductive Verification | Not implemented | Gap (not strictly required) | SPARK/Ada and Frama-C/ACSL provide formal proof of code properties. Used in military engine programs. |

DO-333 formal methods are not mandatory under DO-178C, but they are increasingly expected by certification authorities for DAL A applications and can reduce testing burden by providing mathematical proof of specific properties. Several FADEC certification programs have used formal methods to satisfy structural coverage objectives.

---

## 4. Alignment Strengths

While Aura does not satisfy DO-178C formal requirements, several architectural characteristics align conceptually with aviation safety engineering principles. These alignments are significant because they represent foundational design decisions that are difficult to retrofit -- and they are absent from all competing AI development platforms.

### 4.1 Human-in-the-Loop as Foundational Principle

Human-in-the-loop oversight is the central organizing principle of both Aura's governance architecture and aviation certification. Aura's 5-stage approval workflow (Detection, Sandbox, Approval Request, Human Review, Deployment) mirrors the aviation change management philosophy in which no change reaches the certified configuration without human authorization.

The Configurable Autonomy Framework (ADR-032) implements 4 autonomy levels and 7 industry presets, with 5 hardcoded operations that always require human approval -- enforced via Python `frozenset`, not configuration. This non-negotiable enforcement parallels aviation "shall" requirements that cannot be waived without formal means of compliance negotiation.

### 4.2 Defense-in-Depth Enforcement

Aura implements 10 independent governance mechanisms organized into four pipeline phases. No single mechanism failure creates a path to unauthorized production changes. This defense-in-depth architecture parallels the aviation redundancy philosophy embodied in dual-channel FADEC design, where independent hardware and software channels provide fault tolerance.

The independence is meaningful: the Semantic Guardrails Engine (ADR-065) operates on input screening, Constitutional AI (ADR-063) operates on output quality, the CGE (ADR-081) provides deterministic scoring, and the Sandbox (separate VPC) provides isolated testing -- each enforcing different constraints through different mechanisms.

### 4.3 Deterministic Decision Boundary

The Constraint Geometry Engine (ADR-081) is architecturally unique among AI governance platforms. It provides deterministic, reproducible scoring using frozen embeddings, SHA-256 cache keys, and pure arithmetic. The same input always produces the same score -- a property validated by 358 tests.

This deterministic boundary is significant for certification because it means the final accept/reject decision for any AI-generated output can be audited and reproduced exactly. While the upstream LLM output is non-deterministic, the governance decision applied to that output is fully reproducible. This architecture provides a clean audit boundary that a certification authority could evaluate.

### 4.4 Non-Negotiable Guardrails

Five critical operations are hardcoded as always requiring human approval via Python `frozenset`: production deployment, credential modification, access control changes, database migrations, and infrastructure changes. These guardrails cannot be disabled through configuration, policy, or administrative override.

This enforcement model parallels the aviation concept of non-waivable requirements -- safety-critical constraints that cannot be relaxed without formal regulatory approval.

### 4.5 Immutable Audit Trail

Aura maintains 7-year audit retention for all governance decisions via DynamoDB with immutable write patterns. Every patch approval, rejection, modification, and escalation is recorded with timestamp, actor, rationale, and full decision context.

DO-178C requires retention of all life cycle data for the operational life of the aircraft (typically 20-30+ years). While Aura's 7-year retention is insufficient for aviation use, the audit architecture itself -- immutable, comprehensive, and queryable -- aligns with the evidentiary requirements of certification.

### 4.6 Isolation Testing Architecture

Aura's Sandbox Security implements 4-layer isolation (separate VPC at 10.200.0.0/16, Security Groups, IAM explicit DENY, DNS isolation) with 5-category validation (Syntax, Unit Tests, Security Scans, Performance, Integration). Patches are tested in a fully isolated environment before any human reviewer sees them.

This approach parallels Hardware-in-the-Loop (HIL) and Software-in-the-Loop (SIL) testing in aviation, where engine control software is validated in isolated, representative environments before integration with actual engine hardware.

### 4.7 Behavioral Monitoring and Anomaly Detection

The Runtime Agent Security Platform (ADR-083) establishes behavioral baselines over 1-hour, 24-hour, and 7-day windows, detecting drift within 5 minutes. Traffic interception captures greater than 99.5% of agent communications at less than 5ms P95 latency.

This continuous monitoring parallels Continued Airworthiness requirements in which certified systems are monitored throughout their operational life. The runtime-to-code correlation capability (tracing anomalies through Neptune CALL_GRAPH to source code for remediation) is a unique capability with no parallel in current aviation tooling.

### 4.8 Supply Chain Security

SBOM Attestation (ADR-076) generates CycloneDX and SPDX manifests with Sigstore cryptographic signing, dependency confusion detection, and license compliance analysis. All container builds use private ECR base images from a controlled `aura-base-images` repository.

This supply chain discipline aligns with DO-178C configuration identification requirements (Section 7.2.1) and the broader aviation supply chain assurance practices defined in AS6171 (counterfeit parts avoidance) and DO-178C Section 12.3 (previously developed software).

---

## 5. Risk Assessment

The following assessment classifies each gap area by its impact on certification, the effort required to close the gap, and whether closure depends on external regulatory changes.

### 5.1 Risk Matrix

| Gap Area | Impact on Certification | Effort to Close | Regulatory Dependency | Priority |
|----------|------------------------|-----------------|----------------------|----------|
| PSAC / SDP / SVP / SQAP generation | Prevents certification | Medium | No | Phase 1 |
| Formal requirements traceability | Prevents certification | High | No | Phase 1 |
| MC/DC structural coverage | Prevents certification | Medium | No | Phase 1 |
| Decision coverage analysis | Prevents certification | Medium | No | Phase 1 |
| Statement coverage (raise to 100%) | Prevents certification | Low | No | Phase 1 |
| Object code verification | Prevents certification | High | No | Phase 2 |
| Requirements-based testing | Prevents certification | High | No | Phase 1 |
| Independent QA function | Prevents certification | Medium | No | Phase 1 |
| DO-178C verification independence | Prevents certification | High | No | Phase 2 |
| DO-330 Coder Agent TQL-1 | Prevents certification | Requires industry breakthrough | **Yes** | Phase 3 |
| DO-330 Reviewer Agent TQL-2 | Prevents certification | Requires industry breakthrough | **Yes** | Phase 3 |
| DO-330 Validator Agent TQL-2 | Prevents certification | Requires industry breakthrough | **Yes** | Phase 3 |
| LLM non-determinism resolution | Prevents certification | Requires industry breakthrough | **Yes** | Phase 3 |
| Certification liaison (DER/ODA) | Prevents certification | Medium | No | Phase 4 |
| SAS generation | Prevents certification | Medium | No | Phase 4 |
| Software load control | Prevents certification | High | No | Phase 2 |
| CM formal baseline scheme | Impedes certification | Low | No | Phase 1 |
| Problem report formalization | Impedes certification | Low | No | Phase 1 |
| Formal methods integration | Strengthens case; not strictly required | High | No | Phase 2 |
| Data retention (7yr to 30yr+) | Impedes certification | Low | No | Phase 1 |

### 5.2 The DO-330 Tool Qualification Gap

The DO-330 tool qualification gap is the single most significant barrier to Aura's use in DO-178C-certified development. This gap warrants detailed analysis because it fundamentally differs from all other gaps identified in this document.

**Why this gap is unique:**

1. **LLMs are non-deterministic.** DO-330 tool qualification requires demonstrating that a tool produces correct outputs for defined inputs through deterministic, repeatable testing. LLMs produce probabilistically varying outputs for identical inputs due to sampling algorithms, floating-point arithmetic differences, and model architecture. No amount of engineering effort within a single organization can make LLMs fully deterministic without fundamentally changing the technology.

2. **TQL-1 requires near-DAL A rigor for the tool itself.** Qualifying Aura's Coder Agent at TQL-1 would require developing the tool itself to a standard approaching DAL A: formal tool operational requirements, tool qualification testing demonstrating correct behavior, and configuration management of the tool. This would effectively require DO-178C-level certification of the LLM, its training data, its inference pipeline, and all supporting infrastructure.

3. **No regulatory framework exists.** Neither the FAA nor EASA has published guidance on how to qualify AI/ML-based development tools. The RTCA and EUROCAE committees responsible for DO-178C and DO-330 have not issued supplements or updates addressing machine learning tools. Without a regulatory framework, there is no defined path to qualification.

4. **Model updates invalidate qualification.** Even if an LLM could be qualified at a specific version, model updates (which are routine for cloud-hosted LLMs) would require re-qualification. The aviation regulatory model assumes tools are stable between qualification events.

**Aura's architectural mitigation:** The Constraint Geometry Engine (ADR-081) provides a deterministic decision boundary that partially addresses concern #1. If the compliance approach were framed as "non-deterministic tool outputs subjected to deterministic governance decisions," the CGE could serve as the qualified decision gate while the LLM remains an unqualified advisory input. This "AI-assisted with deterministic governance" architecture is a potentially viable compliance argument, but it has not been tested with any certification authority.

---

## 6. Roadmap to Compliance

The following phased roadmap identifies engineering investments required to close identified gaps. Phases 1 and 2 are within Aenea Labs' engineering control. Phase 3 depends on regulatory evolution. Phase 4 runs concurrently with all other phases.

### Phase 1: Foundation (6-12 Months)

**Objective:** Implement DO-178C life cycle data generation and close measurable verification gaps.

| Work Item | Description | Estimated Effort | Dependencies |
|-----------|-------------|-----------------|--------------|
| Life cycle data templates | Implement PSAC, SDP, SVP, SCMP, SQAP template generation with project-specific parameterization | 3-4 months | Aviation domain expertise (DER consultation) |
| MC/DC coverage integration | Integrate MC/DC structural coverage analysis tool (e.g., VectorCAST, LDRA, Parasoft) into sandbox validation pipeline | 2-3 months | Tool procurement and integration |
| Decision coverage analysis | Add decision coverage measurement to sandbox pipeline | 1-2 months | Included with MC/DC tooling |
| Statement coverage target | Raise mandatory statement coverage from 70% to 100% with dead code analysis | 1 month | None |
| Bidirectional requirements traceability | Extend GraphRAG schema in Neptune to support requirement nodes (HLR, LLR) and bidirectional requirement-to-design-to-code-to-test edges | 3-4 months | Requirements management tool integration (e.g., DOORS, Jama) |
| CM formalization | Define DO-178C baseline identification scheme, formal problem report structure, and archive verification procedures | 1-2 months | None |
| QA role definition | Define independent QA function with documented authority, audit procedures, and non-conformance escalation path | 1 month | Organizational decision |
| Audit retention extension | Extend DynamoDB retention from 7 years to 30+ years for aviation program data | 1 month | Storage cost analysis |

### Phase 2: Verification Enhancement (12-18 Months)

**Objective:** Implement formal verification capabilities and establish structural independence.

| Work Item | Description | Estimated Effort | Dependencies |
|-----------|-------------|-----------------|--------------|
| Requirements-based test generation | Implement formal requirements-based test case generation from HLR/LLR stored in GraphRAG, producing SVCP-formatted output | 4-6 months | Phase 1 requirements traceability |
| Formal methods integration | Integrate model checking (e.g., SPIN, NuSMV) and abstract interpretation (e.g., Polyspace, Astree) capabilities for DAL A code analysis | 4-6 months | Tool procurement; formal methods expertise |
| Independent verification architecture | Establish structurally independent verification function -- separate LLM instances, separate infrastructure, separate access controls -- satisfying DO-178C independence requirements | 3-4 months | Architecture redesign for verification agents |
| Object code verification | Implement source-to-object code traceability analysis for embedded target compilers (PowerPC, ARM Cortex-R families) | 3-4 months | Target compiler access; embedded systems expertise |
| Software load control | Implement controlled software loading procedures for embedded engine control hardware with part number and version verification | 2-3 months | Hardware access; ECU interface specifications |
| SAS generation | Implement Software Accomplishment Summary generation that compiles all DO-178C evidence into the certification package format | 2-3 months | Phase 1 life cycle data items |

### Phase 3: Tool Qualification (18-36 Months, Regulatory Dependent)

**Objective:** Pursue DO-330 tool qualification when regulatory framework permits.

| Work Item | Description | Estimated Effort | Dependencies |
|-----------|-------------|-----------------|--------------|
| Tool Operational Requirements | Define TOR for each Aura agent per DO-330 Section 3.3, specifying expected tool behavior for defined inputs | 2-3 months | None (can begin immediately) |
| Tool Qualification Plan (TQP) | Develop TQP per DO-330 Section 4 for submission to DER/ODA | 2-3 months | DER engagement |
| Tool qualification testing | Execute tool qualification testing per TQP | 6-12 months | TQP approval by DER |
| LLM governance qualification | Pursue qualification of the CGE deterministic governance layer as a TQL-5 tool, independent of LLM qualification | 3-6 months | TOR completion |
| AI/ML regulatory engagement | Participate in FAA AI Technical Exchange Meetings, RTCA SC-205 (DO-178C) and SC-167 (DO-330) committee activities | Ongoing | Industry relationships |

**Critical Dependency:** Phase 3 cannot fully succeed until the FAA or EASA publishes guidance on AI/ML tool qualification. The TOR and TQP work items can proceed independently, but actual qualification testing and approval require a defined regulatory framework. Current FAA and EASA timelines suggest this guidance may not be available before 2028-2030.

### Phase 4: Certification Liaison (Concurrent with Phases 1-3)

**Objective:** Establish and maintain certification authority engagement.

| Work Item | Description | Timing |
|-----------|-------------|--------|
| DER engagement | Engage FAA-authorized DER with engine software (14 CFR 33.28) experience for gap analysis validation and compliance strategy development | Immediate |
| ACO familiarization | Present Aura's architecture and governance model to the FAA Aircraft Certification Office to initiate means of compliance discussion | 3-6 months |
| Issue paper preparation | Prepare issue paper(s) addressing use of AI/ML tools in DO-178C development, proposing "AI-assisted with deterministic governance" compliance approach | 6-12 months |
| SOI planning | Develop Stage of Involvement schedule for pilot certification program | 12-18 months |
| Special conditions pathway | If standard DO-330 compliance is not viable, pursue special conditions or equivalent safety findings per 14 CFR 21.16 | As determined by DER/ACO |
| Industry collaboration | Engage with SAE S-18 (Aircraft and Systems Development and Safety Assessment), RTCA SC-205, and relevant GAMA/AIA working groups | Ongoing |

---

## 7. Interim Use Cases -- What Aura Can Do Today for Aviation

While Aura cannot currently serve as a certified DO-178C development or verification tool, several legitimate applications exist within the aviation domain where Aura's current capabilities provide immediate value without certification requirements.

### 7.1 Non-Safety-Critical Ground Systems

Aviation ground systems -- maintenance management, logistics, fleet scheduling, spare parts inventory, technical documentation management -- are not subject to DO-178C. Aura's full governance pipeline (HITL approval, sandbox testing, audit trails) provides enterprise-grade assurance for these systems without certification constraints.

**Example:** An airline's maintenance information system (MIS) processes work orders, tracks component life limits, and generates maintenance task cards. Aura can scan, remediate, and validate this software using its complete governance pipeline.

### 7.2 Development Accelerator with Human Verification

Aura can serve as a development productivity tool where all outputs are independently verified by DO-178C-qualified human engineers. In this model, Aura generates candidate code, patches, or test cases, and human engineers perform formal DO-178C reviews, analyses, and approval.

**Compliance approach:** Aura is treated as an "unqualified tool" under DO-178C Section 12.2. All tool outputs are verified by qualified personnel through an independent means. The HITL approval workflow provides the organizational control point where human verification occurs.

**Example:** A FADEC software team uses Aura to generate candidate unit tests for engine control law modules. A DO-178C-qualified test engineer reviews each generated test case for requirements coverage, boundary conditions, and robustness before incorporating it into the formal test suite.

### 7.3 Code Review Augmentation

Aura's Reviewer Agent, Constitutional AI (ADR-063), and Constraint Geometry Engine (ADR-081) can provide automated code review outputs that augment -- but do not replace -- human DO-178C code reviews. The automated outputs serve as a pre-screening layer, identifying potential issues for human reviewers to evaluate.

**Example:** Before a formal DO-178C peer review of FADEC software changes, Aura performs an automated review flagging potential security vulnerabilities, coding standard violations, and complexity concerns. The human review team uses these flags as input to their formal review but makes all disposition decisions independently.

### 7.4 Vulnerability Scanning of Non-Airborne Support Software

Aura's Native Vulnerability Scanning Engine (ADR-084) can scan ground support software, factory test equipment software, and other non-airborne software in the engine program ecosystem. This software is not subject to DO-178C but may be subject to organizational cybersecurity requirements.

### 7.5 Configuration Management Support

Aura's GraphRAG engine (Neptune CALL_GRAPH + OpenSearch embeddings) can provide codebase-wide impact analysis for FADEC software change proposals. When an engineer proposes a change to an engine control module, GraphRAG can trace all dependencies, inheritance chains, call graphs, and references to identify all potentially affected code -- supporting the DO-178C change impact analysis requirement.

**Example:** An engineer modifies the thrust computation module. GraphRAG traces all callers of the modified functions, identifies all modules that inherit from the modified class, and flags all test cases that exercise the affected code paths. The engineer uses this analysis as input to the formal DO-178C change impact analysis.

### 7.6 Test Generation Assistant

Aura can generate candidate test cases, including boundary value tests and robustness tests, that qualified test engineers review and incorporate into formal DO-178C test suites. Aura's sandbox validates that generated tests execute correctly before human review.

**Example:** For an engine fuel metering function with 8 input parameters, Aura generates boundary value and equivalence class test cases for all parameter combinations. A DO-178C test engineer reviews the generated cases for completeness against the Software Requirements Data, adds any missing cases, and approves the final test suite.

---

## 8. Military Engine Considerations

Military aircraft engine programs have additional requirements beyond commercial DO-178C certification. The following table assesses Aura's alignment with military-specific standards.

| Requirement | Applicable Standard | Aura Current Status | Gap Assessment |
|-------------|-------------------|-------------------|----------------|
| System safety program | MIL-STD-882E | No system safety program integration | CRITICAL -- MIL-STD-882E requires hazard tracking, risk assessment, and safety verification throughout the life cycle |
| FACE conformance | DoD FACE Technical Standard (Edition 3.1) | No FACE conformance | CRITICAL -- FACE defines portable software architecture segments (Operating System, I/O Services, Platform Specific Services, Transport Services) |
| Cybersecurity | NIST 800-171 / CMMC | Aligned -- Aura maps to NIST 800-53 with CMMC Level 3 presets | PARTIAL -- Aura's CMMC alignment addresses CUI protection requirements applicable to engine technical data |
| Supply chain security | DoDI 5200.44 (Critical Technologies) | Partially aligned -- Private ECR images, SBOM/Sigstore (ADR-076) | PARTIAL -- SBOM and signed attestation support supply chain risk management; lacks formal DoDI 5200.44 program plan |
| CUI handling | NIST 800-171 / 32 CFR Part 2002 | GovCloud deployment supports CUI enclave | PARTIAL -- Aura's GovCloud-ready architecture (19/19 services compatible) supports CUI processing environments |
| Anti-tamper | MIL-STD-129 / program-specific ATP | Not addressed | CRITICAL -- Anti-tamper protection for critical program information (CPI) in FADEC software is program-specific |
| ITAR compliance | 22 CFR Parts 120-130 | Not addressed | CRITICAL -- FADEC software for military engines is likely ITAR-controlled; requires access control and export compliance |
| Data rights | DFARS 252.227-7014 | Not addressed | Gap -- Technical data rights marking and delivery requirements are contractual but influence tool selection |

Military authorities are not required to use DO-178C, but the standard is widely adopted across modern military engine programs. The F-35 F135 engine (Pratt & Whitney), F/A-18 F414 engine (GE Aviation), and V-22 AE 1107C engine (Rolls-Royce) all use DO-178B or DO-178C-certified FADEC software.

---

## 9. Comparative Landscape

No AI code generation or remediation tool has been certified for safety-critical airborne software use under any aviation standard. The following assessment compares the governance architectures of prominent AI development platforms against aviation certification requirements.

| Governance Capability | Aura | GitHub Copilot | Amazon CodeWhisperer | Cursor | Tabnine |
|-----------------------|------|---------------|---------------------|--------|---------|
| Human-in-the-loop approval workflow | Yes -- 5-stage, configurable | No | No | No | No |
| Deterministic decision scoring | Yes -- CGE, reproducible | No | No | No | No |
| Multi-layer governance pipeline | Yes -- 10 mechanisms | No | No | No | No |
| Agent capability restriction | Yes -- 4-tier classification | No | No | No | No |
| Non-negotiable guardrails | Yes -- hardcoded frozenset | No | No | No | No |
| Immutable audit trail | Yes -- 7-year DynamoDB | No | Limited | No | Limited |
| Sandbox isolation testing | Yes -- 4-layer VPC isolation | No | No | No | No |
| Supply chain attestation (SBOM) | Yes -- CycloneDX/SPDX/Sigstore | No | No | No | No |
| Runtime behavioral monitoring | Yes -- baselines, drift detection | No | No | No | No |
| Policy-as-code governance | Yes -- GitOps, drift reconciliation | No | No | No | No |
| Formal requirements traceability | No | No | No | No | No |
| DO-178C life cycle data generation | No | No | No | No | No |
| MC/DC structural coverage | No | No | No | No | No |
| DO-330 tool qualification | No | No | No | No | No |

**Key Observation:** All platforms share the same critical gaps (bottom four rows). The differentiator is the governance foundation (top ten rows). Aura is the only platform with a governance architecture that conceptually aligns with aviation safety engineering principles. "Closer to aviation safety culture" is not "compliant," but it represents a materially different starting position for any future certification effort.

---

## 10. Summary and Recommendations

### 10.1 Gap Summary

| Gap Classification | Count | Examples |
|-------------------|-------|---------|
| **Critical gaps** | 17 | PSAC/SDP/SVP/SQAP generation, MC/DC coverage, requirements traceability, verification independence, tool qualification, QA function, SAS, certification liaison |
| **Partial gaps** | 12 | CM processes, coding standards, integration testing, reviews, problem reporting, process audits |
| **Alignment strengths** | 8 | HITL workflow, defense-in-depth, deterministic scoring, non-negotiable guardrails, audit trail, isolation testing, behavioral monitoring, supply chain security |

### 10.2 Critical Path Assessment

The path to DO-178C compliance for Aura involves two distinct categories of work:

**Category 1 -- Engineering gaps (closable with investment):** Life cycle data generation, structural coverage analysis, requirements traceability, independent verification architecture, formal methods integration, QA function establishment, and certification liaison. These gaps are well-understood, and the aviation industry has decades of experience closing them. Estimated investment: 18-24 months of focused engineering with aviation domain expertise.

**Category 2 -- Regulatory gaps (not closable by engineering alone):** DO-330 tool qualification of LLM-based agents. This gap depends on FAA and EASA publishing guidance on AI/ML tool qualification, which is not expected before 2028-2030. No amount of engineering investment can close this gap without regulatory framework evolution.

### 10.3 Recommendations

**1. Engage a DER immediately.** Retain an FAA-authorized Designated Engineering Representative with 14 CFR 33.28 (engine control software) experience to validate this gap analysis and advise on means of compliance strategy. DER engagement is the single highest-value near-term action because it establishes the certification authority relationship and calibrates engineering investment against actual regulatory expectations.

**2. Pursue "AI-assisted with human verification" as the pragmatic interim compliance approach.** Under DO-178C Section 12.2 (tool qualification), an unqualified tool may be used if its outputs are verified through independent means. Aura's HITL workflow provides the organizational control point for human verification. This approach allows Aura to deliver immediate value to aviation programs while tool qualification frameworks mature.

**3. Invest in Phase 1 (Foundation) capabilities.** MC/DC coverage integration, requirements traceability via GraphRAG, and DO-178C life cycle data generation are high-value investments regardless of the tool qualification timeline. These capabilities serve non-aviation regulated industries (medical devices/IEC 62304, automotive/ISO 26262, rail/EN 50128) and position Aura for aviation certification when regulatory frameworks are established.

**4. Engage with standards development organizations.** Participate in RTCA SC-205 (DO-178C), RTCA SC-167 (DO-330), and SAE S-18 committee activities to influence AI/ML tool qualification guidance development. Early engagement ensures Aura's architectural approach (deterministic governance over non-deterministic AI) is understood by the regulatory community.

**5. Prepare the "deterministic governance" compliance argument.** Aura's CGE architecture -- where non-deterministic LLM outputs pass through a deterministic scoring and decision layer -- represents a potentially novel compliance approach. Document this architecture formally, with mathematical proof of determinism properties, as a candidate means of compliance for future regulatory discussion.

**6. Target the military market for near-term aviation entry.** Military engine programs have more flexibility in compliance approaches than commercial certification. MIL-STD-882E permits tailoring, and military program offices can accept alternative means of compliance through the system safety engineering process. Aura's existing NIST 800-53 alignment and GovCloud readiness support military program entry.

### 10.4 Final Assessment

Aura's governance architecture was designed for enterprise-regulated environments -- SOX, CMMC, HIPAA, PCI-DSS, FedRAMP -- and it delivers genuine assurance within those frameworks. Aviation DO-178C certification operates at a fundamentally different level of rigor, with formal evidence requirements, structural coverage mandates, and tool qualification standards that no AI development platform currently satisfies.

The honest assessment is that Aura has 17 critical gaps and 12 partial gaps against DO-178C DAL A requirements. The DO-330 tool qualification barrier is the most significant because it depends on regulatory evolution outside any single vendor's control.

The equally honest assessment is that Aura's governance architecture -- HITL approval, deterministic scoring, capability restriction, non-negotiable guardrails, defense-in-depth enforcement, and immutable audit trails -- represents the strongest foundation for aviation certification readiness of any AI development platform in the market. If and when AI tool qualification frameworks are established by aviation authorities, Aura's existing architecture provides the starting position closest to compliance.

The path forward is not to wait for regulatory clarity but to close the engineering gaps that are within Aenea Labs' control (Phase 1 and Phase 2), engage the certification community early (Phase 4), and position Aura's deterministic governance architecture as a candidate compliance approach for the regulatory frameworks that will eventually emerge.

---

## Appendix A: DO-178C Structural Coverage Requirements by DAL

| DAL | Statement Coverage | Decision Coverage | MC/DC | Object Code Verification |
|-----|-------------------|-------------------|-------|--------------------------|
| A | Required (100%) | Required (100%) | Required (100%) | Required (when compiler generates untraceable code) |
| B | Required (100%) | Required (100%) | Required (100%) | Not required |
| C | Required (100%) | Required (100%) | Not required | Not required |
| D | Required (100%) | Not required | Not required | Not required |
| E | No objectives | No objectives | No objectives | No objectives |

## Appendix B: DO-178C Traceability Requirements by DAL

| Traceability Chain | DAL A | DAL B | DAL C | DAL D |
|-------------------|-------|-------|-------|-------|
| System Req to HLR | Required; bidirectional | Required; bidirectional | Required | Required |
| HLR to LLR | Required; bidirectional | Required; bidirectional | Required | Not required |
| LLR to Source Code | Required; bidirectional | Required; bidirectional | Not required | Not required |
| Source to Object Code | Required; bidirectional | Not required | Not required | Not required |
| Requirements to Test Cases | Required; bidirectional | Required; bidirectional | Required; partial | Required |
| Test Cases to Test Results | Required | Required | Required | Required |

## Appendix C: DO-330 Tool Qualification Level Determination

| | DAL A | DAL B | DAL C | DAL D |
|--|-------|-------|-------|-------|
| **Criteria 1** (output is part of airborne software) | TQL-1 | TQL-2 | TQL-3 | TQL-4 |
| **Criteria 2** (automates verification; eliminates other process) | TQL-2 | TQL-3 | TQL-4 | TQL-5 |
| **Criteria 3** (could fail to detect errors; does not eliminate process) | TQL-5 | TQL-5 | TQL-5 | TQL-5 |

## Appendix D: Aura Governance Mechanism Summary

| Mechanism | ADR | Tests | Lines | Pipeline Phase | Key Metric |
|-----------|-----|-------|-------|----------------|------------|
| Semantic Guardrails Engine | ADR-065 | 793 | ~12K | Pre-Execution | 240ms P95, 6,300+ threat embeddings |
| Agent Capability Governance | ADR-066 | 322 | ~5.4K | Pre-Execution | 4-tier classification, per-invocation enforcement |
| Configurable Autonomy Framework | ADR-032 | N/A | N/A | Pre-Execution | 4 autonomy levels, 5 hardcoded guardrails |
| Constitutional AI Integration | ADR-063 | 463 | N/A | Post-Generation | 16 principles, 410ms P95, up to 3 revisions |
| Constraint Geometry Engine | ADR-081 | 358 | ~4.5K | Post-Generation | 7 constraint axes, deterministic scoring |
| Sandbox Security | N/A | N/A | N/A | Sandbox/Approval | 4-layer isolation, 5-category validation, 99.2% success rate |
| HITL Approval Workflow | N/A | N/A | N/A | Sandbox/Approval | 5-stage workflow, 3 decision options |
| Real-Time Agent Intervention | ADR-042 | N/A | N/A | Sandbox/Approval | 6 intervention modes, WebSocket per-action checkpoints |
| Runtime Agent Security Platform | ADR-083 | 848 | ~10.3K | Continuous Monitoring | >99.5% traffic capture, <5ms P95, 75-technique red team |
| Policy-as-Code GitOps | ADR-070 | 98 | ~1.2K | Continuous Monitoring | 3-stage CI/CD, 30-second Neptune sync |

## Appendix E: Acronyms

| Acronym | Definition |
|---------|-----------|
| ACO | Aircraft Certification Office |
| ARP | Aerospace Recommended Practice |
| CCB | Configuration Control Board |
| CGE | Constraint Geometry Engine |
| CII | Configuration Identification Index |
| CMMC | Cybersecurity Maturity Model Certification |
| CUI | Controlled Unclassified Information |
| DAL | Design Assurance Level |
| DER | Designated Engineering Representative |
| EASA | European Union Aviation Safety Agency |
| ECU | Engine Control Unit |
| EEC | Electronic Engine Control |
| FAA | Federal Aviation Administration |
| FACE | Future Airborne Capability Environment |
| FADEC | Full Authority Digital Engine Control |
| FDAL | Functional Development Assurance Level |
| FHA | Functional Hazard Assessment |
| GAMA | General Aviation Manufacturers Association |
| GraphRAG | Graph-based Retrieval-Augmented Generation |
| HITL | Human-in-the-Loop |
| HLR | High-Level Requirements |
| IDAL | Item Development Assurance Level |
| ITAR | International Traffic in Arms Regulations |
| LLM | Large Language Model |
| LLR | Low-Level Requirements |
| MC/DC | Modified Condition/Decision Coverage |
| ODA | Organization Designation Authorization |
| PSAC | Plan for Software Aspects of Certification |
| PSSA | Preliminary System Safety Assessment |
| QA | Quality Assurance |
| SAS | Software Accomplishment Summary |
| SCI | Software Configuration Index |
| SCMP | Software Configuration Management Plan |
| SDD | Software Design Description |
| SDP | Software Development Plan |
| SOI | Stage of Involvement |
| SQAP | Software Quality Assurance Plan |
| SRD | Software Requirements Data |
| SSA | System Safety Assessment |
| SVCP | Software Verification Cases and Procedures |
| SVP | Software Verification Plan |
| SVR | Software Verification Results |
| TOR | Tool Operational Requirements |
| TQP | Tool Qualification Plan |
| TQL | Tool Qualification Level |
