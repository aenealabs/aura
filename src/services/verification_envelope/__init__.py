"""Project Aura - Deterministic Verification Envelope (DVE).

ADR-085 implementation. Phase 1 ships the consensus engine; Phases 2-5
will add the structural coverage gate, formal verification gate,
DO-178C profile registration, and infrastructure plumbing.

Public surface (Phase 1):

* :class:`DVEConfig` — tunable parameters for the consensus engine.
* :class:`ConsensusService` — N-of-M generation orchestrator.
* :class:`ASTNormalizer` — canonical-form normalizer.
* :class:`SemanticEquivalenceChecker` — two-stage equivalence
  (AST-hash fast path + embedding-cosine slow path).
* Frozen result types: :class:`ConsensusResult`, :class:`DVEResult`,
  :class:`ASTCanonicalForm`, :class:`MCDCCoverageReport`,
  :class:`VerificationResult`, :class:`EquivalenceCheck`.

Phase 2-5 capabilities (coverage gate, formal verification, DAL policy
profiles, traceability service) are stubbed in :mod:`contracts` and
:mod:`policies` so consumers can declare types now and Phase-2+ will
populate the runtime behaviour.
"""

from src.services.verification_envelope.config import DALLevel, DVEConfig
from src.services.verification_envelope.consensus import (
    ASTNormalizer,
    ConsensusService,
    GeneratorFn,
    SemanticEquivalenceChecker,
    evaluate_convergence,
)
from src.services.verification_envelope.coverage import (
    CoverageAnalysisRequest,
    CoverageGateInput,
    CoverageGateResult,
    CoverageGateService,
    CoveragePyAdapter,
    LDRAAdapter,
    MCDCCoverageAdapter,
    VectorCASTAdapter,
)
from src.services.verification_envelope.contracts import (
    ASTCanonicalForm,
    ConsensusOutcome,
    ConsensusResult,
    DVEOverallVerdict,
    DVEResult,
    EquivalenceCheck,
    MCDCCoverageReport,
    VerificationResult,
    VerificationVerdict,
)

__all__ = [
    "ASTCanonicalForm",
    "ASTNormalizer",
    "ConsensusOutcome",
    "ConsensusResult",
    "ConsensusService",
    "CoverageAnalysisRequest",
    "CoverageGateInput",
    "CoverageGateResult",
    "CoverageGateService",
    "CoveragePyAdapter",
    "DALLevel",
    "DVEConfig",
    "DVEOverallVerdict",
    "DVEResult",
    "EquivalenceCheck",
    "GeneratorFn",
    "LDRAAdapter",
    "MCDCCoverageAdapter",
    "MCDCCoverageReport",
    "SemanticEquivalenceChecker",
    "VectorCASTAdapter",
    "VerificationResult",
    "VerificationVerdict",
    "evaluate_convergence",
]
