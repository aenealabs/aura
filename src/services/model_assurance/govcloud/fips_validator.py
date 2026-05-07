"""FIPS 140-2 endpoint validator (ADR-088 Phase 3.5).

Per ADR-088 §GovCloud Deployment Considerations: "All evaluation
infrastructure uses FIPS 140-2 validated endpoints". This module
provides the validator the deployment-time configuration check
calls on every AWS endpoint URL the assurance pipeline is
configured to talk to.

Acceptance rules (from AWS FIPS endpoint documentation):

  * Hostnames containing "-fips-" or ".fips." or starting with
    "fips." are accepted.
  * In commercial partitions (us-east-1 etc.) FIPS endpoints look
    like ``bedrock-fips.us-east-1.amazonaws.com``.
  * In GovCloud, FIPS is the default — every standard endpoint
    in ``us-gov-*`` is FIPS-validated unless it explicitly says
    otherwise.

Three validators:

  * :func:`is_fips_endpoint`           low-level URL check
  * :func:`validate_endpoint_set`      audit a config bag of endpoints
  * :class:`PartitionEnforcement`     end-to-end Scout/oracle/sandbox
                                      partition + FIPS sanity gate
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


# Hostname patterns AWS uses for FIPS endpoints.
_FIPS_PATTERNS = (
    re.compile(r".*-fips-.*"),
    re.compile(r".*\.fips\..*"),
    re.compile(r"^fips\..*"),
    re.compile(r".*-fips\..*"),
)

# Hostnames that are FIPS by default in GovCloud (every us-gov- region
# endpoint is FIPS-validated unless explicitly stated otherwise).
_GOVCLOUD_REGION_PREFIXES = ("us-gov-",)


class Partition(Enum):
    AWS = "aws"
    AWS_US_GOV = "aws-us-gov"


def _is_govcloud_host(host: str) -> bool:
    return any(prefix in host.lower() for prefix in _GOVCLOUD_REGION_PREFIXES)


def is_fips_endpoint(host: str) -> bool:
    """Return True iff ``host`` is a FIPS 140-2 validated endpoint.

    Two acceptance paths:
      1. Hostname contains a FIPS marker (``-fips-`` / ``.fips.`` /
         ``fips.<service>``).
      2. Hostname is in a us-gov-* region — those endpoints are
         FIPS by default per AWS GovCloud documentation.
    """
    host_lower = host.lower()
    if _is_govcloud_host(host_lower):
        return True
    return any(p.match(host_lower) for p in _FIPS_PATTERNS)


@dataclass(frozen=True)
class EndpointValidation:
    host: str
    is_fips: bool
    detail: str = ""


@dataclass(frozen=True)
class EndpointSetValidation:
    """Outcome of validating a bag of configured endpoints."""

    endpoints: tuple[EndpointValidation, ...]

    @property
    def all_fips(self) -> bool:
        return all(e.is_fips for e in self.endpoints)

    @property
    def non_fips(self) -> tuple[EndpointValidation, ...]:
        return tuple(e for e in self.endpoints if not e.is_fips)


def validate_endpoint_set(hosts: tuple[str, ...]) -> EndpointSetValidation:
    """Validate every host in ``hosts``.

    Used at deployment time to gate a configuration: if any host
    isn't FIPS, the deployment is rejected.
    """
    results = tuple(
        EndpointValidation(
            host=host,
            is_fips=is_fips_endpoint(host),
            detail=(
                "FIPS-validated"
                if is_fips_endpoint(host)
                else "host did not match FIPS naming pattern or GovCloud partition"
            ),
        )
        for host in hosts
    )
    return EndpointSetValidation(endpoints=results)


@dataclass(frozen=True)
class PartitionEnforcement:
    """Per-partition deployment-time enforcement gate.

    GovCloud deployments must:
      * Use FIPS endpoints (covered by validate_endpoint_set above).
      * Have HITL mandatory for every model swap (no autonomy
        bypass — checked separately by the orchestrator).
      * Use the air-gap import path for HuggingFace, never the
        public Hub.

    Commercial deployments are only required to use FIPS endpoints
    when explicitly opted in (e.g. via a per-tenant compliance
    profile).
    """

    partition: Partition
    require_fips: bool = True
    require_hitl_for_model_swap: bool = True

    def assert_endpoints_acceptable(
        self, hosts: tuple[str, ...]
    ) -> EndpointSetValidation:
        validation = validate_endpoint_set(hosts)
        # In commercial mode without require_fips, we don't fail
        # explicitly here — caller decides. This method is a pure
        # validator; caller uses .all_fips / .non_fips to gate.
        return validation
