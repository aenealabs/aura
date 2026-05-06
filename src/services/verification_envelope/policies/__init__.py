"""DO-178C policy profiles for the Deterministic Verification Envelope.

ADR-085 Phase 4 will register full ``do-178c-dal-a`` and
``do-178c-dal-b`` profiles in ``constraint_geometry/policy_profile.py``.
Phase 1 ships only the policy-level metadata so the consensus engine
and downstream consumers can refer to DAL levels by stable name.
"""

from src.services.verification_envelope.policies.do178c_profiles import (
    DAL_A_PROFILE_NAME,
    DAL_B_PROFILE_NAME,
    DEFAULT_PROFILE_NAME,
    DALCoveragePolicy,
    get_coverage_policy,
)

__all__ = [
    "DAL_A_PROFILE_NAME",
    "DAL_B_PROFILE_NAME",
    "DALCoveragePolicy",
    "DEFAULT_PROFILE_NAME",
    "get_coverage_policy",
]
