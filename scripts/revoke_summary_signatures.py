#!/usr/bin/env python3
"""Revoke a window of summary signatures (ADR-093 Sally C-2).

When a signer is compromised (worker exfiltrates a KMS context, signing
bug ships, etc.), all summaries signed by that signer within a time
window must be treated as untrustworthy.

This script writes a revocation entry to the ``summary_revocations``
DynamoDB table. The resolver's :class:`DynamoDbRevocationOracle`
consults this table on every summary read; entries that fall within a
revoked window are dropped + re-derived.

Runbook context (5-step incident response):

    1. Operator runs ``disable_neptune_taint_resolver.py`` (kill-switch).
    2. Operator runs THIS script for the affected window.
    3. ``DynamoDbRevocationOracle.is_revoked()`` starts returning True
       for the matched window on the next preload.
    4. The background quarantine job (not in this script) marks
       affected vertices ``quarantined=true``; next scan deletes them.
    5. Operator re-enables the resolver via the kill-switch script.

Usage:

    ./scripts/revoke_summary_signatures.py \\
        --region us-east-1 \\
        --table-name summary_revocations \\
        --signer-arn arn:aws:kms:us-east-1:111122223333:key/abcd \\
        --from 2026-05-13T14:00:00+00:00 \\
        --to   2026-05-13T16:30:00+00:00 \\
        --reason "worker-pod compromise; potential signature exfil"

Exit codes:
    0  -- revocation entry written
    1  -- DynamoDB API call failed
    2  -- argument validation failed (invalid timestamp, missing arg)
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from typing import Optional, Sequence

logger = logging.getLogger("revoke_summary_signatures")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Write a summary-signature revocation entry to DynamoDB.",
    )
    p.add_argument("--region", required=True)
    p.add_argument(
        "--table-name",
        default="summary_revocations",
        help="DynamoDB revocations table name (default: %(default)s).",
    )
    p.add_argument(
        "--signer-arn",
        required=True,
        help="KMS key ARN of the compromised signer.",
    )
    p.add_argument(
        "--from",
        dest="from_iso",
        required=True,
        help=(
            "ISO 8601 timestamp -- start of revoked window "
            "(e.g., 2026-05-13T14:00:00+00:00)."
        ),
    )
    p.add_argument(
        "--to",
        dest="to_iso",
        required=True,
        help="ISO 8601 timestamp -- end of revoked window.",
    )
    p.add_argument(
        "--reason",
        required=True,
        help="Human-readable revocation reason (audit trail).",
    )
    p.add_argument("--dry-run", action="store_true")
    return p


def _validate_iso(value: str) -> None:
    """Raise ValueError on malformed timestamps."""
    datetime.fromisoformat(value)


def revoke_window(
    *,
    region: str,
    table_name: str,
    signer_arn: str,
    from_iso: str,
    to_iso: str,
    reason: str,
    dry_run: bool,
    ddb_client_factory=None,
) -> int:
    """Write the revocation entry; return 0 on success, 1 on failure."""
    # Validate timestamps before any AWS call.
    try:
        _validate_iso(from_iso)
        _validate_iso(to_iso)
    except ValueError as exc:
        logger.error("Invalid timestamp: %s", exc)
        return 2
    if from_iso >= to_iso:
        logger.error("--from (%r) must be strictly < --to (%r)", from_iso, to_iso)
        return 2

    # Build the entry via the shared schema helper so the script + the
    # read-side oracle agree.
    from src.services.vulnerability_scanner.parsing.neptune_taint_aws_deps import (  # noqa: PLC0415
        revocation_entry_for_window,
    )

    entry = revocation_entry_for_window(
        signer_arn=signer_arn,
        from_iso=from_iso,
        to_iso=to_iso,
        reason=reason,
    )

    if dry_run:
        logger.info(
            "[dry-run] would PutItem to %s in %s: %s",
            table_name,
            region,
            entry,
        )
        return 0

    if ddb_client_factory is None:
        import boto3  # noqa: PLC0415

        ddb = boto3.client("dynamodb", region_name=region)
    else:
        ddb = ddb_client_factory(region)

    try:
        ddb.put_item(TableName=table_name, Item=entry)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "DynamoDB put_item failed for revocations(%s) in %s: %s",
            signer_arn,
            region,
            exc,
        )
        return 1

    logger.info(
        "Revocation entry written: signer=%s window=[%s, %s] reason=%r",
        signer_arn,
        from_iso,
        to_iso,
        reason,
    )
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    return revoke_window(
        region=args.region,
        table_name=args.table_name,
        signer_arn=args.signer_arn,
        from_iso=args.from_iso,
        to_iso=args.to_iso,
        reason=args.reason,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
