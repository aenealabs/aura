"""Cloud audit sinks for the DVE verification auditor (ADR-085 Phase 5).

The auditor's :class:`_ArchiveSink` protocol is satisfied by either
the in-memory / filesystem sinks shipped in Phase 3, or the cloud
sinks here:

* :class:`DynamoDBAuditSink` — record metadata, supports immutable
  conditional writes.
* :class:`S3ProofArchiveSink` — SMT formula + JSON record blobs,
  KMS-CMK encrypted.
* :class:`CompositeArchiveSink` — fan-out to multiple sinks at once
  (e.g. DynamoDB + S3 in production).

All cloud sinks soft-import ``boto3``; air-gapped builds and CI without
credentials degrade to an in-memory fallback automatically.
"""

from src.services.verification_envelope.sinks.composite_sink import CompositeArchiveSink
from src.services.verification_envelope.sinks.dynamodb_audit_sink import (
    DynamoDBAuditSink,
)
from src.services.verification_envelope.sinks.s3_proof_archive_sink import (
    S3ProofArchiveSink,
)

__all__ = [
    "CompositeArchiveSink",
    "DynamoDBAuditSink",
    "S3ProofArchiveSink",
]
