"""Deterministic HMAC-SHA256 signer for tests + in-process development.

Production code MUST wire a KMS-backed implementation through the
same ``CampaignSignerPort`` Protocol. This implementation is
explicitly **not safe** for production -- it stores keys in process
memory and uses HMAC (symmetric) rather than asymmetric signing.

The "deterministic" name flags the constraint: HMAC with a fixed key
produces the same output for the same input, which matches the
audit-trail requirement on the Port.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import threading


class DeterministicCampaignSigner:
    """In-memory HMAC-SHA256 signer for tests.

    Keys are generated lazily per ``key_id`` and stashed in a process-
    local dict. Two ``DeterministicCampaignSigner`` instances are
    **not** interchangeable -- they have distinct key material -- so
    tests can simulate a key-rotation event by constructing a second
    instance and watching verification fail.
    """

    def __init__(self, *, seed: bytes = b"aura-campaign-test-secret") -> None:
        self._seed = seed
        self._keys: dict[str, bytes] = {}
        self._lock = threading.Lock()

    def _key_for(self, key_id: str) -> bytes:
        with self._lock:
            cached = self._keys.get(key_id)
            if cached is not None:
                return cached
            derived = hmac.new(
                self._seed, key_id.encode("utf-8"), hashlib.sha256
            ).digest()
            self._keys[key_id] = derived
            return derived

    def sign(self, *, payload: bytes, key_id: str) -> str:
        digest = hmac.new(self._key_for(key_id), payload, hashlib.sha256).digest()
        return base64.b64encode(digest).decode("ascii")

    def verify(self, *, payload: bytes, signature: str, key_id: str) -> bool:
        try:
            expected = self.sign(payload=payload, key_id=key_id)
        except Exception:  # pragma: no cover -- defensive
            return False
        # constant-time comparison (HMAC defense).
        return hmac.compare_digest(expected, signature)
