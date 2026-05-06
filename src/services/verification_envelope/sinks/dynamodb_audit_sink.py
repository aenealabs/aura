"""Project Aura - DynamoDB audit sink (ADR-085 Phase 5).

Implements the verification-auditor archive sink protocol against
DynamoDB. Records are written immutably (no overwrite) keyed by
``record_id`` so the certification audit trail can never lose or
silently mutate a verdict.

Soft-imports boto3 so air-gapped slim builds (ADR-078) load cleanly;
in that case the sink falls back to its in-memory cousin (delegating
to a wrapped :class:`InMemoryArchiveSink`).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from src.services.verification_envelope.formal.verification_auditor import (
    ArchiveOutcome,
    AuditRecord,
    InMemoryArchiveSink,
)

logger = logging.getLogger(__name__)


try:
    import boto3  # type: ignore[import-not-found]
    from botocore.exceptions import ClientError  # type: ignore[import-not-found]

    BOTO3_AVAILABLE = True
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment,misc]
    BOTO3_AVAILABLE = False


class DynamoDBAuditSink:
    """Writes :class:`AuditRecord` instances to DynamoDB.

    Schema (matches ``deploy/cloudformation/dve-infrastructure.yaml``):
        - PK: ``record_id`` (string).
        - GSI: ``verdict-timestamp-index`` over (verdict, created_at).
        - TTL attribute: ``ttl`` (epoch seconds; 7-year retention by
          default per DO-178C 11.0 record-keeping guidance).

    Conditional writes via ``ConditionExpression='attribute_not_exists(record_id)'``
    enforce the immutability invariant — re-archiving the same record_id
    is rejected.
    """

    def __init__(
        self,
        *,
        table_name: str | None = None,
        dynamodb_client: Any | None = None,
        ttl_seconds: int = 7 * 365 * 24 * 60 * 60,
        fallback: InMemoryArchiveSink | None = None,
    ) -> None:
        self._table_name = table_name or os.environ.get(
            "DVE_AUDIT_TABLE_NAME"
        )
        self._client = dynamodb_client
        self._ttl_seconds = ttl_seconds
        self._fallback = fallback or InMemoryArchiveSink()

        if (
            self._client is None
            and BOTO3_AVAILABLE
            and self._table_name
        ):
            try:
                self._client = boto3.client("dynamodb")  # type: ignore[union-attr]
            except Exception as exc:  # pragma: no cover — credential failure
                logger.warning("DynamoDB client init failed: %s", exc)
                self._client = None

    @property
    def is_live(self) -> bool:
        return self._client is not None and self._table_name is not None

    @property
    def fallback(self) -> InMemoryArchiveSink:
        return self._fallback

    async def archive(
        self, record: AuditRecord, smt_assertions: str
    ) -> ArchiveOutcome:
        if not self.is_live:
            return await self._fallback.archive(record, smt_assertions)

        item = self._record_to_item(record)
        try:
            self._client.put_item(  # type: ignore[union-attr]
                TableName=self._table_name,
                Item=item,
                ConditionExpression="attribute_not_exists(record_id)",
            )
        except ClientError as exc:  # type: ignore[misc]
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                logger.warning(
                    "audit record %s already archived; refusing overwrite",
                    record.record_id,
                )
                return ArchiveOutcome.SKIPPED
            logger.error(
                "DynamoDB put_item failed for record %s: %s",
                record.record_id,
                exc,
            )
            return ArchiveOutcome.FAILED
        except Exception as exc:  # pragma: no cover — unexpected boto failure
            logger.error(
                "DynamoDB put_item raised %s for record %s",
                type(exc).__name__,
                record.record_id,
            )
            return ArchiveOutcome.FAILED
        return ArchiveOutcome.ARCHIVED

    # ------------------------------------------------------------ helpers

    def _record_to_item(self, record: AuditRecord) -> dict[str, Any]:
        """Map a frozen AuditRecord to DynamoDB attribute form.

        DynamoDB doesn't accept Python sets / tuples directly; lists are
        the canonical sequence form. Booleans round-trip; floats become
        ``N`` strings.
        """
        import time

        # Note: SMT assertions are stored separately in S3 (see
        # S3ProofArchiveSink) so this row stays small enough to land
        # under DynamoDB's 400 KB item limit even for very large proofs.
        return {
            "record_id": {"S": record.record_id},
            "smt_formula_hash": {"S": record.smt_formula_hash or ""},
            "verdict": {"S": record.verdict},
            "axes_in_scope": {
                "L": [{"S": a} for a in record.axes_in_scope]
            },
            "axes_verified": {
                "L": [{"S": a} for a in record.axes_verified]
            },
            "proof_hash": {"S": record.proof_hash or ""},
            "solver_version": {"S": record.solver_version},
            "verification_time_ms": {
                "N": str(record.verification_time_ms)
            },
            "counterexample": {
                "S": record.counterexample or ""
            },
            "request_source_file": {
                "S": record.request_source_file or ""
            },
            "metadata": {
                "L": [
                    {"M": {"k": {"S": k}, "v": {"S": v}}}
                    for k, v in record.metadata
                ]
            },
            "created_at": {"S": record.created_at},
            "ttl": {"N": str(int(time.time()) + self._ttl_seconds)},
        }
