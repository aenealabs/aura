"""Tests for the signature verifier (ADR-088 Phase 2.1).

The verifier soft-imports cryptography. When the library is
available (the production case), tests exercise the full Ed25519
sign/verify flow against real keys. When unavailable, the verifier
must return VERIFICATION_ERROR for any signed input — never silently
pass. Tests for that path patch the module-level flag.

Implementation note: keypairs are generated in a session-scoped
fixture rather than per-test. The pytest harness in this repo runs
several autouse fixtures that interfere with cryptography's
``serialization.Encoding`` enum identity between consecutive tests
in this directory; generating the PEM exactly once side-steps that
without changing the verifier-under-test's behaviour at all (the
verifier reads the PEM string, the same string, in every test).
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

import pytest

from src.services.supply_chain.model_provenance import (
    ModelArtifact,
    ModelRegistry,
    ProviderSigningKey,
    SignatureStatus,
    SignatureVerifier,
)
from src.services.supply_chain.model_provenance import signature_verifier as sv_mod


pytest.importorskip("cryptography")


def _digest(c: str = "a") -> str:
    return c * 64


@pytest.fixture(scope="session")
def keypairs():
    """Generate two independent ed25519 keypairs once per test session.

    Combined into a single fixture call because the autouse fixtures
    in the parent conftests interfere with cryptography's enum
    identity between fixture invocations; one call paired with a
    "PEM build immediately" pattern avoids the issue entirely.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    def _make() -> tuple[ed25519.Ed25519PrivateKey, str]:
        priv = ed25519.Ed25519PrivateKey.generate()
        pem = priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
        return priv, pem

    return _make(), _make()


@pytest.fixture
def primary_keypair(keypairs):
    return keypairs[0]


@pytest.fixture
def secondary_keypair(keypairs):
    return keypairs[1]


def _sign(privkey, message: bytes) -> str:
    return base64.b64encode(privkey.sign(message)).decode("ascii")


def _make_key(public_pem: str, key_id: str = "anthropic-2026-q2") -> ProviderSigningKey:
    now = datetime.now(timezone.utc)
    return ProviderSigningKey(
        provider="anthropic",
        key_id=key_id,
        public_key_pem=public_pem,
        not_before=now - timedelta(days=1),
        not_after=now + timedelta(days=30),
    )


class TestUnsignedArtifact:
    def test_unsigned_returns_unsigned(self) -> None:
        art = ModelArtifact(
            model_id="m",
            provider="anthropic",
            registry=ModelRegistry.BEDROCK,
            weights_digest=_digest(),
        )
        outcome = SignatureVerifier().verify(art)
        assert outcome.status is SignatureStatus.UNSIGNED


class TestVerifiedSignature:
    def test_valid_ed25519_signature_verifies(self, primary_keypair) -> None:
        priv, pub_pem = primary_keypair
        digest = _digest()
        signature = _sign(priv, digest.encode("utf-8"))
        key = _make_key(pub_pem)

        art = ModelArtifact(
            model_id="m",
            provider="anthropic",
            registry=ModelRegistry.BEDROCK,
            weights_digest=digest,
            signature_b64=signature,
            signing_key_id=key.key_id,
        )
        verifier = SignatureVerifier()
        verifier.register_key(key)
        outcome = verifier.verify(art)
        assert outcome.status is SignatureStatus.VERIFIED

    def test_register_key_constructor_accepts_dict(self, primary_keypair) -> None:
        _, pub_pem = primary_keypair
        key = _make_key(pub_pem)
        verifier = SignatureVerifier(keys_by_id={key.key_id: key})
        assert key.key_id in verifier._keys


class TestSignatureRejection:
    def test_unknown_key_id(self, primary_keypair) -> None:
        priv, _ = primary_keypair
        signature = _sign(priv, _digest().encode("utf-8"))
        art = ModelArtifact(
            model_id="m",
            provider="anthropic",
            registry=ModelRegistry.BEDROCK,
            weights_digest=_digest(),
            signature_b64=signature,
            signing_key_id="unknown-key",
        )
        outcome = SignatureVerifier().verify(art)
        assert outcome.status is SignatureStatus.SIGNING_KEY_UNKNOWN

    def test_expired_key(self, primary_keypair) -> None:
        priv, pub_pem = primary_keypair
        signature = _sign(priv, _digest().encode("utf-8"))
        long_ago = datetime.now(timezone.utc) - timedelta(days=365)
        key = ProviderSigningKey(
            provider="anthropic",
            key_id="expired",
            public_key_pem=pub_pem,
            not_before=long_ago,
            not_after=long_ago + timedelta(days=30),
        )
        art = ModelArtifact(
            model_id="m",
            provider="anthropic",
            registry=ModelRegistry.BEDROCK,
            weights_digest=_digest(),
            signature_b64=signature,
            signing_key_id=key.key_id,
        )
        verifier = SignatureVerifier()
        verifier.register_key(key)
        outcome = verifier.verify(art)
        assert outcome.status is SignatureStatus.SIGNING_KEY_EXPIRED

    def test_revoked_key(self, primary_keypair) -> None:
        priv, pub_pem = primary_keypair
        signature = _sign(priv, _digest().encode("utf-8"))
        key = ProviderSigningKey(
            provider="anthropic",
            key_id="revoked",
            public_key_pem=pub_pem,
            not_before=datetime.now(timezone.utc) - timedelta(days=1),
            not_after=datetime.now(timezone.utc) + timedelta(days=30),
            revoked=True,
        )
        art = ModelArtifact(
            model_id="m",
            provider="anthropic",
            registry=ModelRegistry.BEDROCK,
            weights_digest=_digest(),
            signature_b64=signature,
            signing_key_id=key.key_id,
        )
        verifier = SignatureVerifier()
        verifier.register_key(key)
        outcome = verifier.verify(art)
        assert outcome.status is SignatureStatus.SIGNING_KEY_EXPIRED

    def test_signature_for_different_digest_invalid(self, primary_keypair) -> None:
        priv, pub_pem = primary_keypair
        signature = _sign(priv, _digest("a").encode("utf-8"))
        key = _make_key(pub_pem)
        art = ModelArtifact(
            model_id="m",
            provider="anthropic",
            registry=ModelRegistry.BEDROCK,
            weights_digest=_digest("b"),
            signature_b64=signature,
            signing_key_id=key.key_id,
        )
        verifier = SignatureVerifier()
        verifier.register_key(key)
        outcome = verifier.verify(art)
        assert outcome.status is SignatureStatus.SIGNATURE_INVALID

    def test_signature_from_different_keypair_invalid(
        self, primary_keypair, secondary_keypair
    ) -> None:
        """Signature signed by key A but advertised under key B's id."""
        priv_a, _ = primary_keypair
        _, pub_b = secondary_keypair
        signature = _sign(priv_a, _digest().encode("utf-8"))
        # Register only key B's PEM under "anthropic-2026-q2".
        key = _make_key(pub_b)
        art = ModelArtifact(
            model_id="m",
            provider="anthropic",
            registry=ModelRegistry.BEDROCK,
            weights_digest=_digest(),
            signature_b64=signature,
            signing_key_id=key.key_id,
        )
        verifier = SignatureVerifier()
        verifier.register_key(key)
        outcome = verifier.verify(art)
        assert outcome.status is SignatureStatus.SIGNATURE_INVALID

    def test_malformed_signature_yields_verification_error(
        self, primary_keypair
    ) -> None:
        _, pub_pem = primary_keypair
        key = _make_key(pub_pem)
        art = ModelArtifact(
            model_id="m",
            provider="anthropic",
            registry=ModelRegistry.BEDROCK,
            weights_digest=_digest(),
            signature_b64="not-base64!!",
            signing_key_id=key.key_id,
        )
        verifier = SignatureVerifier()
        verifier.register_key(key)
        outcome = verifier.verify(art)
        assert outcome.status is SignatureStatus.VERIFICATION_ERROR


class TestCryptographyMissing:
    def test_signed_artifact_returns_verification_error(self) -> None:
        original = sv_mod.CRYPTOGRAPHY_AVAILABLE
        sv_mod.CRYPTOGRAPHY_AVAILABLE = False
        try:
            art = ModelArtifact(
                model_id="m",
                provider="anthropic",
                registry=ModelRegistry.BEDROCK,
                weights_digest=_digest(),
                signature_b64="any",
                signing_key_id="any",
            )
            outcome = SignatureVerifier().verify(art)
            assert outcome.status is SignatureStatus.VERIFICATION_ERROR
        finally:
            sv_mod.CRYPTOGRAPHY_AVAILABLE = original

    def test_unsigned_still_returns_unsigned_when_lib_missing(self) -> None:
        original = sv_mod.CRYPTOGRAPHY_AVAILABLE
        sv_mod.CRYPTOGRAPHY_AVAILABLE = False
        try:
            art = ModelArtifact(
                model_id="m",
                provider="anthropic",
                registry=ModelRegistry.BEDROCK,
                weights_digest=_digest(),
            )
            outcome = SignatureVerifier().verify(art)
            assert outcome.status is SignatureStatus.UNSIGNED
        finally:
            sv_mod.CRYPTOGRAPHY_AVAILABLE = original
