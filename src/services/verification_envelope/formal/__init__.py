"""Formal verification pillar of the Deterministic Verification Envelope.

ADR-085 Phase 3. Provides the protocol every formal-verification
backend must satisfy, the constraint translator that maps CGE axes
C1-C4 to SMT-LIB v2 assertions, the Z3 SMT adapter (open-source
default), the gate orchestrator, and the auditor that produces
immutable audit records and forwards them to a pluggable archive sink.
"""

from src.services.verification_envelope.formal.constraint_translator import (
    ConstraintTranslator,
    TranslationContext,
    TranslatorOutput,
    build_request,
)
from src.services.verification_envelope.formal.formal_adapter import (
    FormalVerificationAdapter,
    FormalVerificationRequest,
)
from src.services.verification_envelope.formal.verification_auditor import (
    ArchiveOutcome,
    AuditRecord,
    FileSystemArchiveSink,
    InMemoryArchiveSink,
    VerificationAuditor,
)
from src.services.verification_envelope.formal.verification_gate import (
    FormalGateInput,
    FormalGateResult,
    VerificationGateService,
)
from src.services.verification_envelope.formal.z3_smt_adapter import (
    Z3SMTAdapter,
)

__all__ = [
    "ArchiveOutcome",
    "AuditRecord",
    "ConstraintTranslator",
    "FileSystemArchiveSink",
    "FormalGateInput",
    "FormalGateResult",
    "FormalVerificationAdapter",
    "FormalVerificationRequest",
    "InMemoryArchiveSink",
    "TranslationContext",
    "TranslatorOutput",
    "VerificationAuditor",
    "VerificationGateService",
    "Z3SMTAdapter",
    "build_request",
]
