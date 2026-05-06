"""Project Aura - Deterministic Verification Envelope (DVE).

ADR-085 implementation. Phases 1-3 ship the consensus engine, the
structural coverage gate, and the formal verification gate. Phases 4-5
will register the DO-178C policy profiles into the Constraint Geometry
Engine and provide the CloudFormation infrastructure plumbing.

Public surface (Phases 1-3):

* :class:`DVEConfig` — tunable parameters for the consensus engine.
* :class:`ConsensusService` — N-of-M generation orchestrator.
* :class:`ASTNormalizer` — canonical-form normalizer.
* :class:`SemanticEquivalenceChecker` — two-stage equivalence
  (AST-hash fast path + embedding-cosine slow path).
* :class:`CoverageGateService` — Stage-6 structural coverage gate.
* :class:`MCDCCoverageAdapter` — protocol; concrete adapters
  :class:`CoveragePyAdapter`, :class:`VectorCASTAdapter`,
  :class:`LDRAAdapter`.
* :class:`VerificationGateService` — formal-verification gate
  orchestrator.
* :class:`ConstraintTranslator` — CGE C1-C4 → SMT-LIB v2 assertions.
* :class:`FormalVerificationAdapter` — protocol; concrete adapter
  :class:`Z3SMTAdapter`.
* :class:`VerificationAuditor` — produces immutable audit records;
  archive sinks :class:`InMemoryArchiveSink`,
  :class:`FileSystemArchiveSink`.
* Frozen result types: :class:`ConsensusResult`, :class:`DVEResult`,
  :class:`ASTCanonicalForm`, :class:`MCDCCoverageReport`,
  :class:`VerificationResult`, :class:`EquivalenceCheck`,
  :class:`AuditRecord`.
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
from src.services.verification_envelope.traceability import (
    Artefact,
    ArtefactType,
    InMemoryRequirementStore,
    LifecycleContext,
    LifecycleDataGenerator,
    LifecycleDocument,
    NeptuneRequirementStore,
    Requirement,
    RequirementType,
    TraceEdge,
    TraceEdgeType,
    TraceabilityGap,
    TraceabilityReport,
    TraceabilityService,
)
from src.services.verification_envelope.pipeline import (
    METRIC_NAMESPACE,
    CloudWatchMetricsPublisher,
    ConstitutionalReviser,
    DVEPipeline,
    DVEPipelineInput,
)
from src.services.verification_envelope.sinks import (
    CompositeArchiveSink,
    DynamoDBAuditSink,
    S3ProofArchiveSink,
)
from src.services.verification_envelope.formal import (
    ArchiveOutcome,
    AuditRecord,
    ConstraintTranslator,
    FileSystemArchiveSink,
    FormalGateInput,
    FormalGateResult,
    FormalVerificationAdapter,
    FormalVerificationRequest,
    InMemoryArchiveSink,
    TranslationContext,
    TranslatorOutput,
    VerificationAuditor,
    VerificationGateService,
    Z3SMTAdapter,
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
    "ArchiveOutcome",
    "Artefact",
    "CloudWatchMetricsPublisher",
    "CompositeArchiveSink",
    "ConstitutionalReviser",
    "DVEPipeline",
    "DVEPipelineInput",
    "DynamoDBAuditSink",
    "METRIC_NAMESPACE",
    "S3ProofArchiveSink",
    "ArtefactType",
    "AuditRecord",
    "ConsensusOutcome",
    "ConsensusResult",
    "ConsensusService",
    "ConstraintTranslator",
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
    "FileSystemArchiveSink",
    "FormalGateInput",
    "FormalGateResult",
    "FormalVerificationAdapter",
    "FormalVerificationRequest",
    "GeneratorFn",
    "InMemoryArchiveSink",
    "InMemoryRequirementStore",
    "LDRAAdapter",
    "LifecycleContext",
    "LifecycleDataGenerator",
    "LifecycleDocument",
    "MCDCCoverageAdapter",
    "MCDCCoverageReport",
    "NeptuneRequirementStore",
    "Requirement",
    "RequirementType",
    "SemanticEquivalenceChecker",
    "TraceEdge",
    "TraceEdgeType",
    "TraceabilityGap",
    "TraceabilityReport",
    "TraceabilityService",
    "TranslationContext",
    "TranslatorOutput",
    "VectorCASTAdapter",
    "VerificationAuditor",
    "VerificationGateService",
    "VerificationResult",
    "VerificationVerdict",
    "Z3SMTAdapter",
    "evaluate_convergence",
]
