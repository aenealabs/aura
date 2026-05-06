"""Coverage gate pillar of the Deterministic Verification Envelope.

ADR-085 Phase 2. Provides the protocol every coverage adapter must
satisfy, three concrete adapters (open-source coverage.py plus
VectorCAST and LDRA subprocess shims), and the
:class:`CoverageGateService` orchestrator that selects an adapter and
returns a structural-coverage report keyed against a DAL policy.
"""

from src.services.verification_envelope.coverage.coverage_gate import (
    CoverageGateInput,
    CoverageGateResult,
    CoverageGateService,
)
from src.services.verification_envelope.coverage.coverage_py_adapter import (
    CoveragePyAdapter,
)
from src.services.verification_envelope.coverage.ldra_adapter import LDRAAdapter
from src.services.verification_envelope.coverage.mcdc_adapter import (
    CoverageAnalysisRequest,
    MCDCCoverageAdapter,
)
from src.services.verification_envelope.coverage.vectorcast_adapter import (
    VectorCASTAdapter,
)

__all__ = [
    "CoverageAnalysisRequest",
    "CoverageGateInput",
    "CoverageGateResult",
    "CoverageGateService",
    "CoveragePyAdapter",
    "LDRAAdapter",
    "MCDCCoverageAdapter",
    "VectorCASTAdapter",
]
