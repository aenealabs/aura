"""DO-178C DAL coverage policies (ADR-085 Phase 1 stub).

Phase 1 ships the coverage-threshold metadata so consumers can declare
DAL-typed contracts now. The full profile registration into the
Constraint Geometry Engine (`PolicyConstraint` mechanism) lands in
Phase 4; until then the policies are advisory only — the consensus
engine does not enforce coverage by itself, but downstream users can
read the thresholds and supply them to whichever coverage tool they're
running.

Numbers come from the ADR-085 DAL coverage table, which mirrors
DO-178C Table A-7.
"""

from __future__ import annotations

from dataclasses import dataclass

DAL_A_PROFILE_NAME = "do-178c-dal-a"
DAL_B_PROFILE_NAME = "do-178c-dal-b"
DAL_C_PROFILE_NAME = "do-178c-dal-c"
DAL_D_PROFILE_NAME = "do-178c-dal-d"
DEFAULT_PROFILE_NAME = "default"


@dataclass(frozen=True)
class DALCoveragePolicy:
    """Coverage thresholds for a Design Assurance Level.

    Numbers are *required minimums*, expressed as percentages.
    ``requires_object_code_verification`` flags the DO-178C 6.4.4.2c
    object-code-coverage requirement that only applies at DAL A.
    """

    dal_level: str
    profile_name: str
    statement_required_pct: float
    decision_required_pct: float
    mcdc_required_pct: float
    requires_object_code_verification: bool

    def is_satisfied(
        self,
        statement_pct: float,
        decision_pct: float,
        mcdc_pct: float,
    ) -> bool:
        return (
            statement_pct >= self.statement_required_pct
            and decision_pct >= self.decision_required_pct
            and mcdc_pct >= self.mcdc_required_pct
        )


_POLICIES: dict[str, DALCoveragePolicy] = {
    DAL_A_PROFILE_NAME: DALCoveragePolicy(
        dal_level="DAL_A",
        profile_name=DAL_A_PROFILE_NAME,
        statement_required_pct=100.0,
        decision_required_pct=100.0,
        mcdc_required_pct=100.0,
        requires_object_code_verification=True,
    ),
    DAL_B_PROFILE_NAME: DALCoveragePolicy(
        dal_level="DAL_B",
        profile_name=DAL_B_PROFILE_NAME,
        statement_required_pct=100.0,
        decision_required_pct=100.0,
        mcdc_required_pct=100.0,
        requires_object_code_verification=False,
    ),
    DAL_C_PROFILE_NAME: DALCoveragePolicy(
        dal_level="DAL_C",
        profile_name=DAL_C_PROFILE_NAME,
        statement_required_pct=100.0,
        decision_required_pct=100.0,
        mcdc_required_pct=0.0,
        requires_object_code_verification=False,
    ),
    DAL_D_PROFILE_NAME: DALCoveragePolicy(
        dal_level="DAL_D",
        profile_name=DAL_D_PROFILE_NAME,
        statement_required_pct=100.0,
        decision_required_pct=0.0,
        mcdc_required_pct=0.0,
        requires_object_code_verification=False,
    ),
    DEFAULT_PROFILE_NAME: DALCoveragePolicy(
        dal_level="DEFAULT",
        profile_name=DEFAULT_PROFILE_NAME,
        statement_required_pct=70.0,
        decision_required_pct=0.0,
        mcdc_required_pct=0.0,
        requires_object_code_verification=False,
    ),
}


def get_coverage_policy(profile_name: str) -> DALCoveragePolicy:
    """Look up a DAL coverage policy by profile name.

    Raises ``KeyError`` for unknown profiles so the caller doesn't
    silently fall through to an unrelated default.
    """
    if profile_name not in _POLICIES:
        raise KeyError(
            f"unknown coverage profile: {profile_name!r}. "
            f"Known profiles: {sorted(_POLICIES)}"
        )
    return _POLICIES[profile_name]
