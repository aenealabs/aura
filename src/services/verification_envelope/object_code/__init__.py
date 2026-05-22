"""Object-Code Verification (DO-178C 6.4.4.2c) -- scaffold (issue #210).

Phase 1 of the object-code verification track. Ships the Port +
NotImplementedVerifier stub + the DAL A/B gate hook. The real
implementations (gcc + objdump, ARM/PowerPC harness) land in
follow-up phases per ADR-085.1.
"""

from src.services.verification_envelope.object_code.contracts import (
    ObjectCodeVerdict,
    ObjectCodeVerifierStatus,
)
from src.services.verification_envelope.object_code.gate import (
    ObjectCodeGate,
    ObjectCodeGateResult,
)
from src.services.verification_envelope.object_code.port import ObjectCodeVerifierPort
from src.services.verification_envelope.object_code.stub_verifier import (
    NotImplementedObjectCodeVerifier,
)

__all__ = [
    "NotImplementedObjectCodeVerifier",
    "ObjectCodeGate",
    "ObjectCodeGateResult",
    "ObjectCodeVerdict",
    "ObjectCodeVerifierPort",
    "ObjectCodeVerifierStatus",
]
