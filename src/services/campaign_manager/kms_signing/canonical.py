"""Canonical byte serialisation for signing campaign artifacts.

The signature is computed over a JSON-serialised form of the
artifact that:

  1. Excludes the signature field itself (otherwise the signature
     would have to include its own hash -- impossible).
  2. Uses ``sort_keys=True`` so two equivalent dicts produce the
     same bytes regardless of insertion order.
  3. Uses a stable representation for ``datetime`` (ISO 8601 with
     timezone) and ``Enum`` (the value).

Production KMS signing wraps the bytes returned here; the test
``DeterministicCampaignSigner`` HMACs them.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from enum import Enum

from src.services.campaign_manager.contracts import CampaignDefinition, PhaseCheckpoint


def _default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"Cannot canonicalise type {type(value).__name__}")


def canonicalize_campaign_definition(definition: CampaignDefinition) -> bytes:
    """Return the deterministic bytes used to sign a CampaignDefinition.

    Excludes the ``definition_signature`` field (which carries the
    signature being computed) and ``created_at`` (purely informational;
    excluding keeps tests deterministic without freezing time).
    """
    raw = asdict(definition)
    raw.pop("definition_signature", None)
    raw.pop("created_at", None)
    return json.dumps(
        raw, default=_default, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonicalize_phase_checkpoint(checkpoint: PhaseCheckpoint) -> bytes:
    """Return the deterministic bytes used to sign a PhaseCheckpoint.

    Excludes ``kms_signature`` and ``created_at`` for the same
    reasons as above. The artifact manifest, cost counters, and
    success criteria progress ARE included -- they're load-bearing
    for tamper detection.
    """
    raw = asdict(checkpoint)
    raw.pop("kms_signature", None)
    raw.pop("created_at", None)
    return json.dumps(
        raw, default=_default, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
