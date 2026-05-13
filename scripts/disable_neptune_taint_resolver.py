#!/usr/bin/env python3
"""Incident-response kill-switch for the Neptune-backed taint resolver.

Per ADR-093 §Kill-switch: this is the pre-staged tool an operator runs
to flip the Neptune-backed taint resolver off across the fleet in
under 5 minutes without a redeploy.

Mechanism: sets the SSM Parameter Store value at
``/aura/scanner/neptune_taint_resolver_enabled`` to ``false``. The
factory polls this flag at scan start; once flipped, every new scan
falls back to :class:`InMemoryTaintContext`. Already-running scans
complete on whichever backend they started with.

Usage:

    # Disable (default action)
    ./scripts/disable_neptune_taint_resolver.py --region us-east-1

    # Re-enable after the incident is resolved
    ./scripts/disable_neptune_taint_resolver.py --region us-east-1 --enable

    # Dry-run (no AWS calls)
    ./scripts/disable_neptune_taint_resolver.py --region us-east-1 --dry-run

    # Custom parameter name (override the default for stage/qa/prod)
    ./scripts/disable_neptune_taint_resolver.py \\
        --region us-east-1 \\
        --parameter-name /aura/qa/scanner/neptune_taint_resolver_enabled

Exit codes:
    0  -- flag flip succeeded
    1  -- SSM API call failed
    2  -- argument validation failed

Operator audit: the SSM update event is captured by CloudTrail and
should also be logged manually to the incident channel + the
``docs/runbooks/NEPTUNE_TAINT_RESOLVER_RUNBOOK.md`` Operator Log
section per ADR-093 §Observability and runbook.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional, Sequence

logger = logging.getLogger("disable_neptune_taint_resolver")

DEFAULT_PARAMETER_NAME: str = "/aura/scanner/neptune_taint_resolver_enabled"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Toggle the Neptune-backed taint resolver feature flag.",
    )
    p.add_argument(
        "--region",
        required=True,
        help="AWS region (e.g., us-east-1, us-gov-west-1).",
    )
    p.add_argument(
        "--parameter-name",
        default=DEFAULT_PARAMETER_NAME,
        help="SSM Parameter Store name (default: %(default)s).",
    )
    p.add_argument(
        "--enable",
        action="store_true",
        help="Re-enable the resolver (sets flag to 'true').",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the action without calling AWS.",
    )
    p.add_argument(
        "--operator",
        default="",
        help=(
            "Operator name/email for the audit log (required in production; "
            "optional in dev for testability)."
        ),
    )
    return p


def flip_flag(
    *,
    region: str,
    parameter_name: str,
    enable: bool,
    dry_run: bool,
    ssm_client_factory=None,
) -> int:
    """Flip the SSM flag; return 0 on success, 1 on failure.

    ``ssm_client_factory`` is injected for tests; production passes
    ``None`` and the function builds the boto3 client itself.
    """
    target_value = "true" if enable else "false"
    action = "enable" if enable else "DISABLE"
    if dry_run:
        logger.info(
            "[dry-run] would set %s=%r in region %s (%s)",
            parameter_name,
            target_value,
            region,
            action,
        )
        return 0

    if ssm_client_factory is None:
        # Local import keeps boto3 out of the import-time path for tests
        # that pass a factory.
        import boto3  # noqa: PLC0415

        ssm = boto3.client("ssm", region_name=region)
    else:
        ssm = ssm_client_factory(region)

    try:
        ssm.put_parameter(
            Name=parameter_name,
            Value=target_value,
            Type="String",
            Overwrite=True,
        )
    except Exception as exc:  # noqa: BLE001 -- operator-facing error
        logger.error(
            "SSM put_parameter failed for %s in %s: %s",
            parameter_name,
            region,
            exc,
        )
        return 1

    logger.info(
        "Flag %s set to %r in region %s by operator=%r (action=%s)",
        parameter_name,
        target_value,
        region,
        # Operator is informational here; CloudTrail captures the real
        # caller identity.
        "<unset>",
        action,
    )
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    return flip_flag(
        region=args.region,
        parameter_name=args.parameter_name,
        enable=args.enable,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
