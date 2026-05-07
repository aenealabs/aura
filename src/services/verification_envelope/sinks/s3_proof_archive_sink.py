"""Project Aura - S3 proof-archive sink (ADR-085 Phase 5).

Persists the SMT-LIB v2 formula and a JSON copy of the audit record
to a customer-managed-KMS-encrypted S3 bucket. Used in tandem with
:class:`DynamoDBAuditSink`: DynamoDB owns the record metadata for
fast lookup, S3 owns the heavy-tail artefacts (the SMT formula can be
multiple megabytes for large patches).

Object layout::

    {prefix}/{record_id}/record.json
    {prefix}/{record_id}/formula.smt2

Both objects are written with ``ServerSideEncryption=aws:kms`` using
the bucket's default KMS-CMK (provisioned by the Phase 5
CloudFormation template). ``ContentType`` is set so the artefacts
display correctly when downloaded.

Soft-imports boto3 so air-gapped slim builds (ADR-078) load cleanly.
When boto3 or the bucket name is missing, the sink delegates to its
in-memory fallback.
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

    BOTO3_AVAILABLE = True
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]
    BOTO3_AVAILABLE = False


class S3ProofArchiveSink:
    """Persists audit artefacts to S3 with KMS encryption."""

    def __init__(
        self,
        *,
        bucket_name: str | None = None,
        key_prefix: str = "dve/proofs",
        kms_key_id: str | None = None,
        s3_client: Any | None = None,
        fallback: InMemoryArchiveSink | None = None,
    ) -> None:
        self._bucket = bucket_name or os.environ.get("DVE_PROOF_BUCKET")
        self._prefix = key_prefix.rstrip("/")
        self._kms_key_id = kms_key_id or os.environ.get("DVE_PROOF_KMS_KEY_ID")
        self._client = s3_client
        self._fallback = fallback or InMemoryArchiveSink()

        if self._client is None and BOTO3_AVAILABLE and self._bucket:
            try:
                self._client = boto3.client("s3")  # type: ignore[union-attr]
            except Exception as exc:  # pragma: no cover — credential failure
                logger.warning("S3 client init failed: %s", exc)
                self._client = None

    @property
    def is_live(self) -> bool:
        return self._client is not None and self._bucket is not None

    @property
    def fallback(self) -> InMemoryArchiveSink:
        return self._fallback

    async def archive(self, record: AuditRecord, smt_assertions: str) -> ArchiveOutcome:
        if not self.is_live:
            return await self._fallback.archive(record, smt_assertions)

        record_key = self._object_key(record, "record.json")
        formula_key = self._object_key(record, "formula.smt2")
        try:
            self._put(
                key=record_key,
                body=record.to_json().encode("utf-8"),
                content_type="application/json",
            )
            self._put(
                key=formula_key,
                body=smt_assertions.encode("utf-8"),
                content_type="text/plain",
            )
        except Exception as exc:
            logger.error(
                "S3 put_object failed for record %s: %s",
                record.record_id,
                exc,
            )
            return ArchiveOutcome.FAILED
        return ArchiveOutcome.ARCHIVED

    # ------------------------------------------------------------ helpers

    def _object_key(self, record: AuditRecord, leaf: str) -> str:
        return f"{self._prefix}/{record.record_id}/{leaf}"

    def _put(
        self,
        *,
        key: str,
        body: bytes,
        content_type: str,
    ) -> None:
        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": body,
            "ContentType": content_type,
            # Always ask for SSE-KMS; the bucket policy can enforce this
            # too, but explicit-on-write means a misconfigured bucket
            # default doesn't silently degrade the encryption posture.
            "ServerSideEncryption": "aws:kms",
        }
        if self._kms_key_id:
            kwargs["SSEKMSKeyId"] = self._kms_key_id
        self._client.put_object(**kwargs)  # type: ignore[union-attr]
