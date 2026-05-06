# ADR-085: Deterministic Verification Envelope (DO-178C Output Verification Architecture)

## Status

Accepted (Phases 1 & 2 Implemented; Phases 3-5 in progress)

Phase 1 deployed as `src/services/verification_envelope/` (consensus engine, AST normalizer, semantic equivalence checker, consensus policy with M-of-N centroid selection, DAL coverage policy stubs for the cert argument). 40 unit tests.

Phase 2 deployed as `src/services/verification_envelope/coverage/` (`MCDCCoverageAdapter` protocol, `CoveragePyAdapter` open-source default, `VectorCASTAdapter` and `LDRAAdapter` subprocess shims, `CoverageGateService` orchestrator). The `TestResult` dataclass (`src/services/sandbox_test_runner.py`) gained six structural-coverage fields and an `apply_coverage()` copy-helper for stage 6 of the sandbox pipeline. 30 unit tests.

Outstanding before Phase 3: formal verification gate (Z3 SMT, constraint translator C1-C4 → SMT assertions, verification auditor with proof-hash archive). Phase 4 registers the DO-178C policy profiles into the Constraint Geometry Engine via the new PolicyConstraint mechanism, plus the bidirectional traceability service. Phase 5 lands CloudFormation infrastructure (DynamoDB audit, S3 proof archive, CloudWatch dashboards).

## Date

2026-02-26 (proposed) / 2026-05-06 (Phase 1 & 2 status update)

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Architecture Review | AWS AI SaaS Architect | - | Pending |
| Systems Review | Senior Systems Architect | - | Pending |
| Security Review | Cybersecurity Analyst | - | Pending |
| Kelly | Test Architect | - | Pending |
| Product Review | AI Product Manager | - | Pending |

### Review Summary

Architecture proposed for enabling FAA DO-178C tool qualification compliance via output verification. Adds three verification pillars -- N-of-M consensus generation, structural coverage gate with MC/DC analysis, and formal verification integration -- as a deterministic wrapper around the existing agent execution pipeline. Enables a DO-330 Section 11.4 'output verification' argument, allowing non-deterministic LLM generation tools to remain unqualified provided every output passes deterministic verification. Subject to DER consultation and regulatory acceptance.

## Context

### The Non-Determinism Problem

Large language models are inherently non-deterministic. The same input can produce different outputs across invocations due to sampling temperature, floating-point variance across hardware, model weight updates, and stochastic decoding strategies. DO-178C (Software Considerations in Airborne Systems and Equipment Certification) and DO-330 (Software Tool Qualification Considerations) require tools used in the development of airborne software to behave predictably and produce verifiable outputs. This creates a fundamental conflict: AI-based code generation tools cannot satisfy determinism requirements through their generation mechanism alone.

Aura's existing agent execution pipeline contains multiple layers, but most are probabilistic:

| Pipeline Layer | ADR | Deterministic? | Limitation |
|---------------|-----|:--------------:|------------|
| Semantic Guardrails | ADR-065 | No | LLM-as-judge in Layer 4 is probabilistic |
| Agent Execution (Coder) | -- | No | LLM generation is inherently non-deterministic |
| Constitutional AI | ADR-063 | No | LLM critiquing LLM -- probabilistic critique and revision |
| Constraint Geometry Engine | ADR-081 | **Yes** | Deterministic scoring, but only measures coherence -- does not formally prove correctness |
| Sandbox Validation | -- | **Yes** | Deterministic (tests pass or fail), but only 70% statement coverage -- no MC/DC |
| HITL Approval | ADR-032 | **Yes** | Human review is independent but not scalable |

The Constraint Geometry Engine (ADR-081) was explicitly designed as the "sole deterministic decision boundary" in the agent execution pipeline. It measures geometric coherence of agent outputs against a 7-axis constraint space using frozen embeddings, cosine similarity, and weighted harmonic means. However, the CGE measures how well an output aligns with constraint exemplars -- it does not perform formal proof of correctness, structural coverage analysis, or consensus validation across multiple generation attempts. Coherence is necessary but not sufficient for safety-critical software certification.

### DO-178C and DO-330 Regulatory Context

Full Authority Digital Engine Control (FADEC) software typically receives Design Assurance Level (DAL) A (Catastrophic) or DAL B (Hazardous). FADEC controls engine thrust, and loss of thrust control can result in loss of aircraft. The certification rigor scales with the severity of the failure condition:

| DAL | Failure Condition | Objectives | Failure Rate | Structural Coverage Required |
|-----|-------------------|:----------:|:------------:|------------------------------|
| A | Catastrophic | 71 | <= 1x10^-9/flight hour | Statement + Decision + MC/DC + Object Code |
| B | Hazardous | 69 | <= 1x10^-7/flight hour | Statement + Decision + MC/DC |
| C | Major | 62 | <= 1x10^-5/flight hour | Statement + Decision |
| D | Minor | 26 | -- | Statement |

DO-330 governs tool qualification. Tool Qualification Levels (TQL) are determined by how the tool affects the development process and the DAL of the software being developed:

| Aura Component | DO-330 Criteria | TQL at DAL A | Implication |
|---------------|----------------|:------------:|-------------|
| Coder Agent | Criteria 1 (output becomes airborne software) | TQL-1 | Most rigorous -- tool must be developed to near-DAL A rigor |
| Reviewer Agent | Criteria 2 (automates verification) | TQL-2 | Tool qualification with independence |
| Validator Agent | Criteria 2/3 | TQL-2/TQL-5 | Depends on whether output eliminates other verification |
| CGE (ADR-081) | Criteria 3 (could fail to detect errors) | TQL-5 | Least rigorous -- standard development practices |

**As of publication, we are not aware of any publicly documented LLM-based tool that has been qualified under DO-330 at any TQL level.** The FAA has stated: "Assuring the safety of such systems cannot rely on traditional aviation design assurance." TQL-1 qualification for an LLM-based code generator would require development rigor equivalent to DAL A software -- including full MC/DC coverage of the tool itself, formal methods where applicable, and complete requirements traceability. This is not achievable for a stochastic neural network.

### The Output Verification Escape Clause

DO-330 Section 11.4 states that tool qualification is required when the tool eliminates, reduces, or automates DO-178C processes -- **unless the output of the tool is verified by other means.** Specifically, if independent verification confirms that the tool's output is correct, the tool itself does not need to be qualified at the full TQL level dictated by its criteria classification.

This creates a viable certification path: if every output of the non-deterministic Coder Agent is independently verified through deterministic means that themselves can be qualified, the generator itself does not require TQL-1 qualification. The verification tools require TQL-2 or TQL-5 qualification -- levels that are achievable for deterministic software with well-defined behavior, bounded inputs, and repeatable outputs.

### Gap Summary -- Pre-DVE vs Post-DVE

| Gap | DO-178C Requirement | Pre-DVE Status | Post-DVE Status |
|-----|---------------------|:--------------:|:---------------:|
| MC/DC Coverage (6.4.4.2c) | 100% at DAL A/B | Not measured | Addressed (Pillar 2) |
| Decision Coverage (6.4.4.2b) | 100% at DAL A/B/C | Not measured | Addressed (Pillar 2) |
| Statement Coverage (6.4.4.2a) | 100% at all DALs | 70% threshold | Configurable per DAL (Pillar 2) |
| Formal Methods (DO-333) | Supplements testing | Not implemented | Z3 SMT integration (Pillar 3) |
| DO-330 TQL-1 for Coder | Required unless output verified | Critical gap | Mitigated by output verification argument |
| Requirements Traceability (5.5) | HLR <-> LLR <-> Code <-> Test | Not addressed | Neptune schema extension (Phase 4) |
| Generation Reproducibility | Tool behavior predictable | Non-deterministic | N-of-M consensus (Pillar 1) |

### N-Modular Redundancy -- Aviation Precedent

Triple-redundant flight computers are standard practice in commercial aviation. The Boeing 777 Aircraft Information Management System (AIMS) uses triple-modular redundancy: three independent processing channels compute the same function, and a voter selects the majority output. The Airbus A380 Integrated Modular Avionics (IMA) uses a similar approach with dissimilar redundancy (different processors, different compilers) to protect against common-mode failures.

Pillar 1 of the DVE applies this principle to LLM outputs: generate N independent outputs, normalize them to a canonical form, and accept only when M-of-N converge semantically. The critical difference from hardware redundancy is that software failures are not independent -- the same systematic bias in an LLM can produce the same incorrect output across all N generations. Consensus therefore reduces variance and filters outliers, but it is necessary and not sufficient. The converged output must still pass the full deterministic verification chain (CGE scoring, formal verification, structural coverage) before acceptance.

### What DVE Does NOT Address (Scope Limitations)

The DVE is a necessary but not sufficient component of a DO-178C certification effort. The following are explicitly out of scope:

- **DO-178C independence requirements:** All DVE verification runs on shared Bedrock/Claude infrastructure. A common-mode LLM failure could affect both generation and verification. True independence requires dissimilar tools or human review (HITL satisfies this for the final gate).
- **Embedded target testing:** FADEC software runs on PowerPC or ARM Cortex-R processors with specialized real-time operating systems. DVE operates in cloud-hosted Python on x86/ARM EKS. Target-representative testing on actual FADEC hardware is not addressed.
- **Object code verification:** Compiler-generated machine code traceability is a DAL A requirement. DVE flags object code verification as a configurable policy requirement but does not implement compiler output analysis.
- **Certification liaison:** DVE does not substitute for Designated Engineering Representative (DER) or Aircraft Certification Office (ACO) engagement, Plan for Software Aspects of Certification (PSAC) negotiation, or Stage of Involvement (SOI) reviews.
- **Model version stability:** LLM upgrades (e.g., Claude 3.5 Sonnet to Claude 4) invalidate consensus convergence statistics. Re-validation is required after any model change.

## Decision

Implement the **Deterministic Verification Envelope (DVE)** as a new service package `src/services/verification_envelope/` that wraps the existing agent execution pipeline with three deterministic verification pillars, enabling a DO-330 Section 11.4 output verification argument for the LLM-based Coder Agent.

### Core Capabilities

1. **N-of-M Consensus Generation** -- Run Coder Agent N times (default N=3), normalize outputs to canonical AST form, accept if M-of-N converge semantically (default M=2), escalate to HITL otherwise
2. **Structural Coverage Gate** -- Add MC/DC analysis as stage 6 of sandbox validation pipeline with per-DAL configurable thresholds; extend `TestResult` dataclass with coverage fields; adapter pattern for VectorCAST, LDRA, Parasoft
3. **Formal Verification Integration** -- Adapter pattern for SMT/model-checking backends; Z3 SMT solver as first implementation; translates CGE constraint axes C1-C4 to SMT assertions (C5-C7 not directly SMT-expressible -- documented as limitation)
4. **DO-178C Policy Profiles** -- Two new CGE profiles (`do-178c-dal-a`, `do-178c-dal-b`) with mandatory formal verification and MC/DC conditions via new `PolicyConstraint` mechanism
5. **Bidirectional Requirements Traceability** -- Neptune schema extension for HLR/LLR requirement nodes with `TRACES_TO`, `DERIVED_FROM`, `VERIFIED_BY` edge types

### DO-330 Certification Argument

The DVE enables the following output verification argument under DO-330 Section 11.4:

**Premise 1:** DO-330 states that tool qualification is not required when the output of the tool is verified by other means (Section 11.4).

**Premise 2:** The DVE provides six independent verification passes on every Coder Agent output:

- (a) N-of-M consensus filtering (quasi-deterministic -- reduces variance through multi-generation convergence)
- (b) Constitutional AI critique-revision (probabilistic -- adds safety margin through principle-based review)
- (c) CGE deterministic 7-axis coherence scoring (deterministic -- frozen embeddings, pure arithmetic)
- (d) Z3 formal constraint satisfaction proof (deterministic -- SMT solver with reproducible proof hash)
- (e) Sandbox testing with MC/DC structural coverage (deterministic -- tests pass or fail, coverage measured)
- (f) HITL human review (independent -- satisfies DO-178C independence requirements)

**Premise 3:** Passes (c), (d), and (e) are fully deterministic -- the same output always produces the same verification result. Passes (a) and (b) are probabilistic but serve as variance reducers that filter non-convergent and principle-violating outputs before they reach the deterministic gates. Pass (f) satisfies the independence requirement through human cognition.

**Conclusion:** The verification envelope independently verifies every Coder Agent output through a chain of deterministic and independent checks. The Coder Agent itself, as a non-deterministic generation tool, does not require TQL-1 qualification provided this output verification argument is accepted by the cognizant DER.

**Qualification Strategy:** The DVE verification components (CGE, formal verification gate, structural coverage gate) qualify at TQL-2 or TQL-5 as deterministic software tools that automate verification processes. Their Tool Operational Requirements (TOR) can be written, behavior demonstrated via bounded inputs and expected outputs, and qualification tests repeated with identical results. This is achievable because these components are deterministic software, not stochastic models.

**Caveat:** This argument has not been validated by any DER or certification authority. It is a proposed compliance approach subject to FAA/EASA acceptance. Proactive DER engagement is planned for Phase 1 to validate the argument structure before significant implementation investment.

## Architecture

### Enhanced Pipeline Diagram

```text
+-------------------------------------------------------------------+
|                    PRE-EXECUTION CONTROLS                          |
+-------------------------------------------------------------------+
|  Input --> ADR-065: Semantic Guardrails (probabilistic)            |
|                          |                                        |
|                          v                                        |
|  +---------------------------------------------------+           |
|  |  DVE PILLAR 1: N-of-M Consensus Engine  [NEW]     |           |
|  |                                                   |           |
|  |  +---------+  +---------+  +---------+            |           |
|  |  | Coder   |  | Coder   |  | Coder   |            |           |
|  |  | Run 1   |  | Run 2   |  | Run N   |            |           |
|  |  +----+----+  +----+----+  +----+----+            |           |
|  |       v            v            v                 |           |
|  |  +--------------------------------------+         |           |
|  |  |  AST Normalizer (canonical form)     |         |           |
|  |  +------------------+-------------------+         |           |
|  |                     v                             |           |
|  |  +--------------------------------------+         |           |
|  |  |  Semantic Equivalence Check          |         |           |
|  |  |  M-of-N convergence?                 |         |           |
|  |  +------+-------------------+-----------+         |           |
|  |    YES  |              NO   |                     |           |
|  |         v                   v                     |           |
|  |   consensus_output     HITL Escalation            |           |
|  +-----------+-----------------------------------+   |           |
|              v                                                    |
+-------------------------------------------------------------------+
|                   POST-GENERATION CONTROLS                        |
+-------------------------------------------------------------------+
|  ADR-063: Constitutional AI (probabilistic critique/revision)     |
|              |                                                    |
|              v                                                    |
|  ADR-081: Constraint Geometry Engine (DETERMINISTIC scoring)      |
|              |  CCS score + per-axis breakdown                    |
|              v                                                    |
|  +---------------------------------------------------+           |
|  |  DVE PILLAR 3: Formal Verification Gate [NEW]     |           |
|  |                                                   |           |
|  |  ConstraintTranslator: C1-C4 --> SMT assertions   |           |
|  |  Z3 SMT Solver: satisfiability check              |           |
|  |  VerificationAuditor: proof hash + audit          |           |
|  |                                                   |           |
|  |  PROVED --> continue    FAILED --> REJECT          |           |
|  +-----------+---------------------------------------+           |
|              v                                                    |
+-------------------------------------------------------------------+
|                   SANDBOX & APPROVAL CONTROLS                     |
+-------------------------------------------------------------------+
|  Sandbox Validation (existing 5 categories)                       |
|              |                                                    |
|              v                                                    |
|  +---------------------------------------------------+           |
|  |  DVE PILLAR 2: Structural Coverage Gate [NEW]     |           |
|  |                                                   |           |
|  |  MC/DC Coverage Adapter --> VectorCAST/LDRA       |           |
|  |  DAL Coverage Policy: per-DAL thresholds          |           |
|  |                                                   |           |
|  |  PASSES --> continue    FAILS --> REJECT           |           |
|  +-----------+---------------------------------------+           |
|              v                                                    |
|  HITL Approval Workflow (ADR-032)                                 |
|              |                                                    |
|              v                                                    |
|  Deploy                                                           |
+-------------------------------------------------------------------+
```

### Integration Points

| DVE Component | Existing Service | Integration Method |
|--------------|-----------------|-------------------|
| `ConsensusGenerationService` | `orchestration_service.py` (MetaOrchestrator) | Invokes `spawn_coder_agent()` N times in parallel |
| `ASTNormalizer` | Python stdlib `ast` module | New service; reuses AST patterns from `src/services/rlm/` |
| `SemanticEquivalenceChecker` | `semantic_cache_service.py` | Reuses Bedrock Titan v2 embedding patterns |
| `CoverageGateService` | `sandbox_test_runner.py` | Extends `TestResult`; adds stage 6 to pipeline |
| `FormalVerificationGate` | `constraint_geometry/engine.py` | Post-CGE step; receives `CoherenceResult` |
| `ConstraintTranslator` | `constraint_geometry/contracts.py` | Reads `ConstraintRule` centroids to derive SMT assertions |
| `DO178CProfiles` | `constraint_geometry/policy_profile.py` | New profiles in `_BUILTIN_PROFILES`; new `PolicyConstraint` mechanism |
| `TraceabilityService` | `neptune_graph_service.py` | Adds HLR/LLR vertex types, `TRACES_TO`/`DERIVED_FROM`/`VERIFIED_BY` edges |

### Pillar 1: N-of-M Consensus Engine

**AST Normalization:**

The `ASTNormalizer` uses Python's stdlib `ast` module to convert generated code into a canonical form suitable for structural comparison. Normalization steps: sort imports alphabetically, remove comments and docstrings (semantics-only comparison), normalize variable names to positional placeholders (`_v0`, `_v1`, ...) to eliminate naming variance, and standardize whitespace. The result is an `ASTCanonicalForm` frozen dataclass containing the normalized AST and its SHA-256 hash.

**Semantic Equivalence:**

The `SemanticEquivalenceChecker` performs a two-stage comparison:

1. **Fast path:** Exact AST canonical form match (string comparison of normalized AST dumps). If two outputs normalize to the same canonical form, they are equivalent. This catches trivially identical outputs that differ only in variable naming or formatting.
2. **Slow path:** If AST forms differ, compute Bedrock Titan v2 embeddings for both canonical forms and check cosine similarity > 0.97 threshold. This catches semantically equivalent outputs with structurally different implementations (e.g., `for` loop vs. list comprehension).

Two outputs are considered equivalent if either condition holds.

**Consensus Selection:**

When M-of-N outputs converge, the consensus output is selected as the invocation whose AST canonical form has the minimum total edit distance to all other converging outputs (the centroid of the convergence cluster). This selection is deterministic given the same set of converging outputs. When fewer than M outputs converge, the task is escalated to HITL with all N outputs and their pairwise similarity matrix attached for human review.

### Pillar 2: Structural Coverage Gate

**TestResult Extension:**

```python
# New fields on existing TestResult dataclass
statement_coverage_pct: float = 0.0
decision_coverage_pct: float = 0.0
mcdc_coverage_pct: float = 0.0
structural_coverage_dal: Optional[str] = None  # "DAL_A" through "DAL_D" or "DEFAULT"
coverage_tool_used: Optional[str] = None       # "vectorcast", "ldra", "coverage_py"
coverage_report_s3_key: Optional[str] = None   # S3 path to full report
```

**DAL Coverage Policy:**

```python
@dataclass(frozen=True)
class DALCoveragePolicy:
    """Coverage thresholds for each Design Assurance Level."""
    dal_level: str
    statement_required_pct: float
    decision_required_pct: float
    mcdc_required_pct: float
    requires_object_code_verification: bool
```

| DAL | Statement | Decision | MC/DC | Object Code |
|-----|:---------:|:--------:|:-----:|:-----------:|
| A   | 100.0 | 100.0 | 100.0 | Yes |
| B   | 100.0 | 100.0 | 100.0 | No |
| C   | 100.0 | 100.0 | 0.0 | No |
| D   | 100.0 | 0.0 | 0.0 | No |
| DEFAULT | 70.0 | 0.0 | 0.0 | No |

The DEFAULT policy preserves Aura's existing 70% statement coverage threshold. Non-aviation workloads are unaffected.

**MC/DC Adapter Interface:**

```python
class MCDCCoverageAdapter(Protocol):
    """Protocol for MC/DC coverage analysis tool integration."""
    async def analyze(
        self,
        source_file: Path,
        test_results: TestResult,
        dal_policy: DALCoveragePolicy,
    ) -> MCDCCoverageReport: ...
```

Three adapters are provided:

- `VectorCASTAdapter` -- Primary enterprise MC/DC tool (Vector Software). Subprocess invocation of VectorCAST CLI with SARIF-compatible output parsing.
- `LDRAAdapter` -- Alternative MC/DC tool (LDRA Testbed). Subprocess invocation with coverage report parsing.
- `CoveragePyAdapter` -- Statement and branch coverage only (open-source `coverage.py`). Used for DEFAULT DAL policy. Already integrated with Aura's test runner.

VectorCAST and LDRA are customer-procured external tools. The adapter pattern isolates the DVE from vendor-specific interfaces and allows additional MC/DC tools to be added without modifying core logic.

### Pillar 3: Formal Verification Integration

**Constraint Translation:**

The `ConstraintTranslator` maps CGE constraint axes to Z3 SMT assertions:

- **C1 (Syntactic Validity):** AST structural constraints and type annotation checks. Example: `assert valid_python_ast(output)`, `assert all_types_annotated(output)`.
- **C2 (Semantic Correctness):** Pre/post-condition checks via Z3 integer and bitvector arithmetic. Example: `assert output_satisfies_postcondition(spec, output)`.
- **C3 (Security Policy):** Negation of known-bad patterns. Example: `assert not contains_wildcard_iam(output)`, `assert not uses_eval_on_user_input(output)`.
- **C4 (Operational Bounds):** Quantitative constraints. Example: `assert max_resource_allocation <= 1024`, `assert timeout_ms <= 30000`.
- **C5 (Domain Compliance):** **Not expressible in SMT.** Domain business rules require semantic understanding beyond first-order logic. Deferred to CGE coherence scoring.
- **C6 (Provenance Trust):** **Not expressible in SMT.** Provenance chain verification is a graph operation, not a satisfiability problem. Deferred to CGE.
- **C7 (Temporal Validity):** **Not expressible in SMT.** Time-bounded operations depend on runtime state. Deferred to CGE.

This partial expressibility is documented honestly. C1-C4 formal proof covers the structural, correctness, security, and operational dimensions. These are the axes most amenable to formal methods and provide meaningful DO-333 supplement capability for the certification argument. C5-C7 remain covered by CGE coherence scoring and HITL review.

**Verification Result:**

```python
@dataclass(frozen=True)
class VerificationResult:
    """Immutable formal verification outcome with audit trail."""
    verdict: VerificationVerdict        # PROVED, FAILED, UNKNOWN, SKIPPED
    axes_verified: tuple[str, ...]      # ("C1", "C2", "C3", "C4")
    proof_hash: str                     # SHA-256(output_hash + assertions + solver_version)
    solver_version: str                 # "z3-4.13.0"
    verification_time_ms: float
    smt_formula_hash: str               # SHA-256 of SMT-LIB formula
    counterexample: Optional[str] = None  # Non-None only when FAILED
```

The `proof_hash` enables DO-330 audit reproducibility. A DER can re-run the same output against the same assertions with the same Z3 version and verify that the proof hash matches. The `smt_formula_hash` allows independent verification that the SMT formula itself has not been modified between audit runs.

**Verification Verdicts:**

- **PROVED:** Z3 confirmed all assertions satisfiable for the given output. Output proceeds to next gate.
- **FAILED:** Z3 found a counterexample. Output is rejected. Counterexample is included in the `VerificationResult` for diagnostic review.
- **UNKNOWN:** Z3 could not determine satisfiability within the timeout (default 30 seconds). Behavior is policy-dependent: `do-178c-dal-a` rejects; `do-178c-dal-b` escalates to HITL; DEFAULT skips.
- **SKIPPED:** Formal verification not required by the active policy profile (DEFAULT, developer-sandbox).

### New CGE Policy Profiles

The DVE introduces a `PolicyConstraint` mechanism that extends the existing `PolicyProfile` to support mandatory boolean conditions beyond threshold-based CCS scoring:

```python
@dataclass(frozen=True)
class PolicyConstraint:
    """Mandatory boolean condition on a policy profile."""
    name: str
    description: str
    predicate_key: str  # e.g., "formal_verification_proved", "mcdc_coverage_passed"
    required: bool = True
```

**`do-178c-dal-a` profile:**

- `auto_execute_threshold`: 0.95
- `review_threshold`: 0.85
- `escalate_threshold`: 0.70
- Axis weights: C3 (Security) = 1.5, C5 (Domain) = 1.4, others = 1.0
- `provenance_sensitivity`: 0.9
- Mandatory constraints: `formal_verification_proved=True`, `mcdc_coverage_passed=True`
- UNKNOWN formal verdict: REJECT

**`do-178c-dal-b` profile:**

- `auto_execute_threshold`: 0.92
- `review_threshold`: 0.80
- `escalate_threshold`: 0.65
- Axis weights: Same as dal-a
- Mandatory constraints: `mcdc_coverage_passed=True`
- Formal verification: PROVED required for auto-execute; UNKNOWN triggers HITL escalation (not REJECT)

Both profiles are registered in `_BUILTIN_PROFILES` alongside the existing `default`, `dod-il5`, `developer-sandbox`, and `sox-compliant` profiles. The existing four profiles are not modified.

### Neptune Requirements Traceability Schema

```text
Vertex Types (NEW):
  HighLevelRequirement (HLR)  - System-level requirement (e.g., "Engine shall maintain idle thrust")
  LowLevelRequirement (LLR)  - Software-level requirement derived from HLR
  CodeUnit                    - Function, class, or module implementing an LLR
  TestCase                    - Test verifying a CodeUnit against an LLR

Edge Types (NEW):
  TRACES_TO     - HLR --> LLR (derivation), LLR --> CodeUnit (implementation)
  DERIVED_FROM  - LLR --> HLR (inverse traceability), CodeUnit --> LLR (inverse)
  VERIFIED_BY   - LLR --> TestCase (verification linkage)
  SATISFIES     - CodeUnit --> LLR (forward traceability from code to requirement)

Edge Properties:
  verification_status: str   - "PASSED", "FAILED", "PENDING", "NOT_RUN"
  dal_level:           str   - "DAL_A" through "DAL_D"
  coverage_type:       str   - "statement", "decision", "mcdc"
  last_verified:       str   - ISO timestamp
```

This schema extends the existing Neptune graph (which already contains `CALL_GRAPH`, `DEPENDENCIES`, `INHERITANCE`, and `REFERENCES` edge types) with requirements engineering vertices and edges required by DO-178C Section 5.5 (Software Requirements Process) and Section 6.3 (Software Requirements Review).

## Implementation

### Package Structure

```
src/services/verification_envelope/
|-- __init__.py                          (~50 lines)
|-- config.py                            (~150 lines)
|-- contracts.py                         (~400 lines)
|-- consensus/
|   |-- __init__.py
|   |-- consensus_service.py             (~300 lines)
|   |-- ast_normalizer.py                (~250 lines)
|   |-- semantic_equivalence.py          (~200 lines)
|   +-- consensus_policy.py              (~150 lines)
|-- coverage/
|   |-- __init__.py
|   |-- coverage_gate.py                 (~250 lines)
|   |-- mcdc_adapter.py                  (~100 lines)
|   |-- vectorcast_adapter.py            (~200 lines)
|   |-- ldra_adapter.py                  (~150 lines)
|   +-- dal_coverage_policy.py           (~150 lines)
|-- formal/
|   |-- __init__.py
|   |-- verification_gate.py             (~250 lines)
|   |-- formal_adapter.py               (~80 lines)
|   |-- z3_smt_adapter.py               (~350 lines)
|   |-- constraint_translator.py         (~300 lines)
|   +-- verification_auditor.py          (~200 lines)
|-- traceability/
|   |-- __init__.py
|   |-- traceability_service.py          (~400 lines)
|   |-- lifecycle_data.py                (~600 lines)
|   +-- neptune_requirements.py          (~250 lines)
|-- pipeline/
|   |-- __init__.py
|   |-- dve_pipeline.py                  (~350 lines)
|   +-- dve_metrics.py                   (~150 lines)
+-- policies/
    |-- __init__.py
    +-- do178c_profiles.py               (~100 lines)
```

**Estimated source code:** ~4,700 lines

### Files Modified (Existing)

| File | Modification |
|------|-------------|
| `src/services/sandbox_test_runner.py` | Extend `TestResult` with 6 structural coverage fields; add stage 6 (coverage gate) to sandbox pipeline |
| `src/services/constraint_geometry/policy_profile.py` | Add `PolicyConstraint` to `PolicyProfile` dataclass; register `do-178c-dal-a` and `do-178c-dal-b` profiles |
| `src/services/constraint_geometry/contracts.py` | Add `PolicyConstraint` frozen dataclass; add optional `formal_verification_result` field on `CoherenceResult` |

### Key Data Contracts

```python
# src/services/verification_envelope/contracts.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime


class VerificationVerdict(Enum):
    """Formal verification outcome."""
    PROVED = "proved"
    FAILED = "failed"
    UNKNOWN = "unknown"
    SKIPPED = "skipped"


class ConsensusOutcome(Enum):
    """N-of-M consensus result."""
    CONVERGED = "converged"
    DIVERGED = "diverged"
    PARTIAL = "partial"


@dataclass(frozen=True)
class ASTCanonicalForm:
    """Normalized AST representation for comparison."""
    source_hash: str           # SHA-256 of original source
    canonical_hash: str        # SHA-256 of normalized AST dump
    canonical_dump: str        # ast.dump() of normalized tree
    variable_count: int        # Number of unique variables
    node_count: int            # Total AST node count


@dataclass(frozen=True)
class ConsensusResult:
    """Result of N-of-M consensus generation."""
    outcome: ConsensusOutcome
    n_generated: int
    m_converged: int
    selected_output: Optional[str]
    canonical_forms: tuple[ASTCanonicalForm, ...]
    pairwise_similarities: tuple[tuple[float, ...], ...]
    convergence_rate: float    # m_converged / n_generated
    selection_method: str      # "ast_centroid" or "embedding_centroid"


@dataclass(frozen=True)
class VerificationResult:
    """Immutable formal verification outcome with audit trail."""
    verdict: VerificationVerdict
    axes_verified: tuple[str, ...]
    proof_hash: str
    solver_version: str
    verification_time_ms: float
    smt_formula_hash: str
    counterexample: Optional[str] = None


@dataclass(frozen=True)
class MCDCCoverageReport:
    """Structural coverage analysis result."""
    statement_coverage_pct: float
    decision_coverage_pct: float
    mcdc_coverage_pct: float
    dal_policy_satisfied: bool
    coverage_tool: str
    report_s3_key: Optional[str] = None
    uncovered_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class DVEResult:
    """Complete Deterministic Verification Envelope result."""
    consensus: ConsensusResult
    coherence: "CoherenceResult"         # From CGE (ADR-081)
    formal_verification: VerificationResult
    structural_coverage: MCDCCoverageReport
    overall_verdict: str                 # "ACCEPTED", "REJECTED", "HITL_REQUIRED"
    pipeline_latency_ms: float
    dal_level: str
    audit_record_id: str
    computed_at: datetime
```

### Pipeline Orchestration

```python
# src/services/verification_envelope/pipeline/dve_pipeline.py (simplified)

class DVEPipeline:
    """Orchestrates the Deterministic Verification Envelope."""

    async def execute(
        self,
        task: "AgentTask",
        dal_level: str = "DEFAULT",
    ) -> DVEResult:
        """Run full DVE pipeline on an agent task."""

        # Stage 1: N-of-M Consensus (Pillar 1)
        consensus = await self.consensus_service.generate_and_check(
            task=task,
            n=self.config.consensus_n,
            m=self.config.consensus_m,
        )
        if consensus.outcome == ConsensusOutcome.DIVERGED:
            return self._hitl_escalation(consensus, reason="consensus_diverged")

        # Stage 2: Constitutional AI (existing ADR-063)
        revised = await self.constitutional_mixin.finalize_with_constitutional(
            consensus.selected_output, task
        )

        # Stage 3: CGE Coherence (existing ADR-081)
        coherence = await self.cge.assess_coherence(
            output=revised,
            policy_profile=self._dal_to_profile(dal_level),
        )
        if coherence.action == CoherenceAction.REJECT:
            return self._rejection(consensus, coherence, reason="cge_rejected")

        # Stage 4: Formal Verification (Pillar 3)
        formal = await self.formal_gate.verify(
            output=revised,
            coherence_result=coherence,
            dal_level=dal_level,
        )
        if formal.verdict == VerificationVerdict.FAILED:
            return self._rejection(consensus, coherence, formal, reason="formal_failed")

        # Stage 5: Sandbox Validation (existing)
        test_result = await self.sandbox_runner.execute(revised)

        # Stage 6: Structural Coverage Gate (Pillar 2)
        coverage = await self.coverage_gate.analyze(
            source=revised,
            test_result=test_result,
            dal_policy=self._get_dal_policy(dal_level),
        )
        if not coverage.dal_policy_satisfied:
            return self._rejection(
                consensus, coherence, formal, coverage, reason="coverage_insufficient"
            )

        # Stage 7: HITL (existing ADR-032)
        # Routed based on CGE action and policy constraints
        return self._assemble_result(consensus, coherence, formal, coverage, dal_level)
```

## Implementation Phases

| Phase | Scope | Timeline | Est. Tests |
|-------|-------|----------|:----------:|
| 1: N-of-M Consensus Engine | `consensus_service.py`, `ast_normalizer.py`, `semantic_equivalence.py`, `consensus_policy.py`, `contracts.py`, `config.py`, MetaOrchestrator integration | Weeks 1-4 | ~200 |
| 2: Structural Coverage Gate | `coverage_gate.py`, `mcdc_adapter.py`, `vectorcast_adapter.py`, `ldra_adapter.py`, `dal_coverage_policy.py`, `TestResult` extension, sandbox stage 6 | Weeks 5-8 | ~150 |
| 3: Formal Verification Integration | `verification_gate.py`, `formal_adapter.py`, `z3_smt_adapter.py`, `constraint_translator.py`, `verification_auditor.py`, CGE pipeline integration | Weeks 9-14 | ~200 |
| 4: DO-178C Profiles and Traceability | `do178c_profiles.py`, `PolicyConstraint` mechanism, `traceability_service.py`, `lifecycle_data.py`, `neptune_requirements.py` | Weeks 15-18 | ~150 |
| 5: Infrastructure | CloudFormation templates, EventBridge rules, CloudWatch dashboards, DynamoDB audit tables | Weeks 19-20 | ~50 |
| **Total** | | **20 weeks** | **~750** |

### Phase 1: N-of-M Consensus Engine (Weeks 1-4)

| Task | Deliverable | Est. LOC |
|------|-------------|----------|
| `contracts.py` | All DVE frozen dataclasses, enums | ~400 |
| `config.py` | DVEConfig with `for_testing`/`for_production` | ~150 |
| `consensus/ast_normalizer.py` | Python AST canonical form normalization | ~250 |
| `consensus/semantic_equivalence.py` | Two-stage equivalence (AST + embedding) | ~200 |
| `consensus/consensus_service.py` | N-of-M generation, convergence check, centroid selection | ~300 |
| `consensus/consensus_policy.py` | Configurable N, M, similarity thresholds | ~150 |
| MetaOrchestrator integration | Parallel `spawn_coder_agent()` invocation | ~100 |
| Tests | ~200 tests (normalizer: 60, equivalence: 50, consensus: 70, integration: 20) | ~1,200 |
| **Phase 1 Total** | | **~2,750** |

### Phase 2: Structural Coverage Gate (Weeks 5-8)

| Task | Deliverable | Est. LOC |
|------|-------------|----------|
| `coverage/dal_coverage_policy.py` | DAL threshold definitions, policy validation | ~150 |
| `coverage/mcdc_adapter.py` | `MCDCCoverageAdapter` protocol definition | ~100 |
| `coverage/vectorcast_adapter.py` | VectorCAST CLI subprocess adapter | ~200 |
| `coverage/ldra_adapter.py` | LDRA Testbed subprocess adapter | ~150 |
| `coverage/coverage_gate.py` | Stage 6 orchestrator, policy enforcement | ~250 |
| `sandbox_test_runner.py` modification | `TestResult` extension, stage 6 hook | ~50 |
| Tests | ~150 tests (policies: 40, adapters: 50, gate: 40, integration: 20) | ~900 |
| **Phase 2 Total** | | **~1,800** |

### Phase 3: Formal Verification Integration (Weeks 9-14)

| Task | Deliverable | Est. LOC |
|------|-------------|----------|
| `formal/formal_adapter.py` | `FormalVerificationAdapter` protocol | ~80 |
| `formal/z3_smt_adapter.py` | Z3 solver integration, timeout handling, proof hash | ~350 |
| `formal/constraint_translator.py` | CGE C1-C4 to Z3 assertion translation | ~300 |
| `formal/verification_gate.py` | Gate orchestrator, verdict routing | ~250 |
| `formal/verification_auditor.py` | Audit record generation, proof archive | ~200 |
| CGE integration | `CoherenceResult` extension, pipeline wiring | ~50 |
| Tests | ~200 tests (translator: 70, Z3: 60, gate: 40, auditor: 30) | ~1,300 |
| **Phase 3 Total** | | **~2,530** |

### Phase 4: DO-178C Profiles and Traceability (Weeks 15-18)

| Task | Deliverable | Est. LOC |
|------|-------------|----------|
| `policies/do178c_profiles.py` | `do-178c-dal-a`, `do-178c-dal-b` profile definitions | ~100 |
| `PolicyConstraint` mechanism | Extension to `PolicyProfile` dataclass | ~80 |
| `traceability/traceability_service.py` | Bidirectional HLR/LLR/Code/Test linking | ~400 |
| `traceability/lifecycle_data.py` | PSAC/SDP/SVP/SQAP/SAS template generation | ~600 |
| `traceability/neptune_requirements.py` | Neptune schema extension, Gremlin queries | ~250 |
| Tests | ~150 tests (profiles: 30, constraints: 20, traceability: 60, lifecycle: 40) | ~1,000 |
| **Phase 4 Total** | | **~2,430** |

### Phase 5: Infrastructure (Weeks 19-20)

| Task | Deliverable | Est. LOC |
|------|-------------|----------|
| `deploy/cloudformation/dve-infrastructure.yaml` | DynamoDB audit table, S3 proof archive, SQS queue | ~300 |
| `deploy/cloudformation/dve-monitoring.yaml` | CloudWatch dashboards, alarms, EventBridge rules | ~250 |
| `pipeline/dve_pipeline.py` | Full pipeline orchestrator | ~350 |
| `pipeline/dve_metrics.py` | CloudWatch metrics publisher | ~150 |
| Tests | ~50 tests (infrastructure: 20, pipeline E2E: 30) | ~400 |
| **Phase 5 Total** | | **~1,450** |

## GovCloud Compatibility

| Service | GovCloud Available | DVE Usage |
|---------|:------------------:|-----------|
| Neptune | Yes (provisioned) | Requirements traceability nodes and edges |
| OpenSearch | Yes | Semantic equivalence embedding lookups |
| Bedrock Titan v2 | Yes (us-gov-west-1) | SemanticEquivalenceChecker embeddings |
| DynamoDB | Yes | DVE decision audit records, verification results |
| S3 | Yes | Coverage reports, SMT formula archives, lifecycle data |
| SQS | Yes | Async DVE audit dispatch |
| EKS | Yes | DVE services co-hosted with agent services |
| CloudWatch | Yes | DVE metrics and alarms |
| Z3 solver | N/A (pure library) | Runs in-process; no network calls; Apache-2.0 license |
| VectorCAST/LDRA | Customer-procured | External tool via subprocess; no AWS dependency |

All CloudFormation templates use `${AWS::Partition}` in all ARNs. No commercial-only AWS services are required. Z3 is a pure Python/C++ library with no cloud dependency, making it fully operational in air-gapped deployments (ADR-078 compatible).

## Cost Analysis

### Monthly Cost (1,000 Patches/Month, Aviation Mode)

| Component | Specification | Monthly Cost |
|-----------|--------------|:------------:|
| Bedrock invocations (consensus, N=3) | 3x Coder invocations per patch | ~$150-450 |
| Bedrock Titan v2 (semantic equivalence) | ~3 embedding calls per consensus round | Negligible |
| Z3 solver compute | Pure CPU in EKS pod; no additional infrastructure | ~$0 incremental |
| DynamoDB (DVE audit records) | PAY_PER_REQUEST; ~4 records per patch | ~$2-5 |
| S3 (coverage reports, SMT archives) | ~500KB per patch | ~$5-15 |
| CloudWatch (DVE metrics) | ~15 custom metrics | ~$4.50 |
| **Total incremental infrastructure** | | **~$200-500** |
| VectorCAST or LDRA license | Enterprise MC/DC analysis (customer-procured) | **$50K-150K/year** |

The primary cost driver is the 3x Bedrock invocation multiplier from N-of-M consensus. Non-aviation workloads using the DEFAULT policy skip consensus generation, formal verification, and MC/DC analysis -- incurring zero incremental cost. The VectorCAST/LDRA license cost is borne by the customer as part of their existing DO-178C toolchain investment and is not an Aura platform cost.

## Testing Strategy

| Category | Count | Purpose |
|----------|:-----:|---------|
| Unit -- Consensus | 80 | ASTNormalizer, SemanticEquivalenceChecker, ConsensusPolicy |
| Unit -- Coverage Gate | 60 | CoverageGateService, DALCoveragePolicy, adapter contracts |
| Unit -- Formal Verification | 80 | Z3SMTAdapter, ConstraintTranslator, VerificationAuditor |
| Unit -- Traceability | 60 | TraceabilityService, Neptune schema, lifecycle templates |
| Determinism | 60 | Same input produces same DVE decision (parametrized, 100 runs per case) |
| Integration -- Consensus + CGE | 80 | Consensus output feeds CGE scoring correctly |
| Integration -- Coverage + Sandbox | 50 | Stage 6 integrates with existing sandbox; existing tests pass at DEFAULT |
| Integration -- Formal + CGE | 60 | CGE result drives SMT assertions; audit trail correct |
| Integration -- Full Pipeline | 80 | End-to-end DVE; HITL escalation paths; REJECT paths |
| Performance | 40 | Consensus < 3x single generation time; formal < 5s; coverage gate < 500ms |
| GovCloud | 20 | All AWS calls use `${AWS::Partition}` |
| Golden Dataset | 30 | >=85% convergence on known-good patches from ADR-084 vulnerability dataset |
| Backward Compatibility | 50 | Existing sandbox tests pass unchanged at DEFAULT policy |
| **Total** | **~750** | |

### Critical Testing Requirements

- **DEFAULT DAL policy must produce identical behavior to the pre-DVE sandbox pipeline.** Existing tests must pass without modification. The consensus engine, formal verification gate, and MC/DC coverage gate are all bypassed at DEFAULT policy. Only when a DO-178C profile is active do these gates engage.
- **`fail_under = 70` in `pyproject.toml` must not be lowered.** DVE tests must increase or maintain overall coverage.
- **Determinism validation:** Every DVE gate that claims determinism must pass the 100-iteration parametrized test. Any non-deterministic behavior in gates (c), (d), or (e) is a test failure.

### Determinism Validation

```python
# tests/services/test_verification_envelope/test_determinism.py

class TestDVEDeterminism:
    """Verify that deterministic DVE gates produce identical results."""

    @pytest.mark.parametrize("iteration", range(100))
    async def test_formal_verification_determinism(
        self, formal_gate, sample_output, iteration
    ):
        """Z3 proof hash must be identical across 100 runs."""
        result = await formal_gate.verify(
            output=sample_output,
            coherence_result=self.coherence,
            dal_level="DAL_A",
        )
        if iteration == 0:
            self.__class__.baseline_hash = result.proof_hash
            self.__class__.baseline_verdict = result.verdict
        else:
            assert result.proof_hash == self.__class__.baseline_hash
            assert result.verdict == self.__class__.baseline_verdict

    @pytest.mark.parametrize("iteration", range(100))
    async def test_coverage_gate_determinism(
        self, coverage_gate, sample_source, sample_test_result, iteration
    ):
        """Coverage analysis must produce identical results."""
        result = await coverage_gate.analyze(
            source=sample_source,
            test_result=sample_test_result,
            dal_policy=DALCoveragePolicy.for_dal("DAL_B"),
        )
        if iteration == 0:
            self.__class__.baseline_satisfied = result.dal_policy_satisfied
            self.__class__.baseline_mcdc = result.mcdc_coverage_pct
        else:
            assert result.dal_policy_satisfied == self.__class__.baseline_satisfied
            assert result.mcdc_coverage_pct == self.__class__.baseline_mcdc
```

## Consequences

### Positive

1. **DO-330 output verification argument enabled** -- The Coder Agent can remain unqualified at TQL-1, removing the single largest barrier to using LLM-based code generation in DO-178C development environments
2. **Early entrant in aviation-grade verification wrappers for AI code generation** -- As of publication, we are not aware of another platform that publicly documents a structured DO-178C output verification architecture for LLM-generated code
3. **MC/DC structural coverage closes the largest technical gap** -- 100% MC/DC coverage measurement is the most rigorous structural coverage objective in DO-178C and was previously absent from the pipeline
4. **Z3 formal verification provides DO-333 supplement capability** -- Formal methods are an accepted supplement to testing under DO-333, and SMT-based constraint satisfaction proofs strengthen the safety argument
5. **N-of-M consensus converts probabilistic generation into quantifiably reliable output** -- Convergence rate is a measurable, auditable metric that quantifies generation reliability
6. **Fully backward compatible** -- The DEFAULT policy preserves existing pipeline behavior with zero regressions; DO-178C gates activate only when aviation profiles are selected
7. **Requirements traceability closes HLR/LLR/Code/Test bidirectional linking gap** -- DO-178C Section 5.5 and 6.3 traceability requirements are addressed through Neptune schema extension
8. **DO-178C lifecycle data templates enable PSAC/SDP/SVP/SQAP/SAS generation** -- Reduces the documentation burden for certification applicants using Aura-generated code
9. **New policy profiles extend CGE to aviation domain** -- Two new profiles are added without modifying the existing four profiles, preserving all current behavior

### Negative

1. **N-of-M consensus increases Bedrock costs by Nx** -- Default 3x multiplier on every patch generation in aviation mode; configurable but irreducible when consensus is required
2. **MC/DC tooling requires external procurement** -- VectorCAST ($50K-150K/year) or LDRA are required for DAL A/B MC/DC analysis; this is a customer cost, not a platform cost, but represents a barrier to adoption
3. **Z3 provides only partial constraint axis coverage** -- C1-C4 are expressible in SMT; C5 (Domain Compliance), C6 (Provenance Trust), and C7 (Temporal Validity) cannot be formally verified
4. **Consensus convergence statistics must be re-validated after LLM model upgrades** -- Any change to the underlying LLM (version, provider, fine-tuning) invalidates convergence baselines and requires re-measurement
5. **DVE adds substantial complexity and latency to the pipeline** -- Aviation-mode operations include N parallel LLM invocations, SMT solving, and MC/DC analysis; total pipeline time increases significantly compared to DEFAULT mode

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|:----------:|:------:|------------|
| DER rejects output verification argument | Medium | High | Proactive DER engagement before Phase 1 implementation; prepare alternative Issue Paper pathway via FAA |
| Consensus convergence < 85% at N=3, M=2 | Medium | Medium | Configurable N/M parameters; N=5, M=3 fallback; per-task-type convergence tracking to identify low-convergence patterns |
| Z3 returns UNKNOWN (undecidable formula) | Medium | Medium | UNKNOWN triggers HITL escalation, not REJECT (except at DAL A); track UNKNOWN rate in CloudWatch metrics |
| VectorCAST/LDRA integration complexity | High | Medium | CoveragePyAdapter as fallback for DEFAULT; MC/DC analysis is optional for non-aviation workloads |
| DO-178C regulatory framework evolution | Low | High | DVE architecture is standards-agnostic; thresholds, coverage types, and verification methods are all configurable |

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Consensus convergence rate (N=3, M=2) | >= 85% | CloudWatch `DVE/ConsensusConvergenceRate` |
| CGE + formal verification false positive rate | < 5% | Human reviewer agreement with REJECT decisions |
| MC/DC coverage achievable for generated patches | >= 90% | Patches reaching MC/DC threshold when tool available |
| End-to-end DVE pipeline latency | < 10 minutes | CloudWatch `DVE/PipelineLatencyP95` (excludes MC/DC tool) |
| Non-deterministic outputs escaping DVE | 0 | Audit: outputs reaching HITL without passing deterministic gates |
| DER acceptance of output verification argument | Accepted | Binary outcome from initial DER engagement |
| Backward compatibility regressions | 0 | Existing test suite passes unchanged at DEFAULT policy |
| Proof hash reproducibility | 100% | Same output + same Z3 version = same hash (10,000 runs) |

---

*Competitive references in this ADR reflect publicly available information as of the document date. Vendor products evolve; readers should verify current capabilities before decision-making. Third-party vendor names and products referenced herein are trademarks of their respective owners. References are nominative and do not imply endorsement or partnership.*

## References

1. ADR-081: Constraint Geometry Engine (Deterministic Cortical Discrimination)
2. ADR-063: Constitutional AI Integration
3. ADR-065: Semantic Guardrails Engine
4. ADR-032: Configurable Autonomy Framework (HITL)
5. ADR-042: Real-Time Agent Intervention
6. ADR-018: Meta-Orchestrator with Dynamic Agent Spawning
7. ADR-067: Context Provenance and Integrity
8. ADR-076: SBOM Attestation and Supply Chain
9. ADR-078: Air-Gapped and Edge Deployment
10. RTCA DO-178C: Software Considerations in Airborne Systems and Equipment Certification
11. RTCA DO-330: Software Tool Qualification Considerations
12. RTCA DO-333: Formal Methods Supplement to DO-178C
13. FAA AC 20-115D: Airborne Software Development Assurance Using EUROCAE ED-12C and RTCA DO-178C
14. FAA AC 33.28-3: Guidance Material for Aircraft Engine Control Systems (14 CFR 33.28)
15. MIL-STD-882E: Department of Defense Standard Practice -- System Safety
16. `docs/product/executive-summaries/faa-do178c-gap-analysis.md` -- Aenea Labs internal gap analysis
