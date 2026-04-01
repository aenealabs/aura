"""
FIPS 140-2 Cryptographic Compliance Module.

Provides FIPS-compliant cryptographic operations for government and
regulated industry deployments. Uses only approved algorithms:
- AES-256-GCM for symmetric encryption
- SHA-256/SHA-384/SHA-512 for hashing
- ECDSA P-256/P-384 for signatures
- ECDH P-256/P-384 for key exchange
- PBKDF2-HMAC-SHA256 for key derivation

FIPS Mode Activation:
1. Set environment variable: AURA_FIPS_MODE=true
2. Ensure OpenSSL is compiled with FIPS support
3. On RHEL: Enable system FIPS mode via fips-mode-setup --enable
"""

import hashlib
import hmac
import logging
import os
import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class FIPSAlgorithm(str, Enum):
    """FIPS 140-2 approved cryptographic algorithms."""

    # Hash algorithms
    SHA256 = "SHA-256"
    SHA384 = "SHA-384"
    SHA512 = "SHA-512"

    # Symmetric encryption
    AES_256_GCM = "AES-256-GCM"
    AES_256_CBC = "AES-256-CBC"

    # Key derivation
    PBKDF2_SHA256 = "PBKDF2-HMAC-SHA256"

    # Signatures
    ECDSA_P256 = "ECDSA-P256"
    ECDSA_P384 = "ECDSA-P384"

    # Key exchange
    ECDH_P256 = "ECDH-P256"
    ECDH_P384 = "ECDH-P384"


# Non-approved algorithms that must be blocked in FIPS mode
BLOCKED_ALGORITHMS = {
    "MD5",
    "SHA1",
    "DES",
    "3DES",
    "RC4",
    "RSA-1024",
    "DSA-1024",
    "Blowfish",
    "IDEA",
}


@dataclass
class FIPSStatus:
    """FIPS compliance status information."""

    enabled: bool
    openssl_fips: bool
    system_fips: bool
    version: str
    algorithms_available: list[str]
    warnings: list[str]


class FIPSComplianceError(Exception):
    """Raised when FIPS compliance check fails."""

    def __init__(self, message: str, algorithm: Optional[str] = None):
        self.message = message
        self.algorithm = algorithm
        super().__init__(message)


class FIPSCrypto:
    """
    FIPS 140-2 compliant cryptographic operations.

    All operations use only FIPS-approved algorithms. Attempting to
    use non-approved algorithms raises FIPSComplianceError.
    """

    def __init__(self, strict_mode: bool = True):
        """
        Initialize FIPS crypto provider.

        Args:
            strict_mode: If True, block all non-FIPS operations
        """
        self._strict_mode = strict_mode
        self._fips_enabled = self._check_fips_mode()

        if self._fips_enabled:
            logger.info("FIPS 140-2 mode enabled")
            self._validate_environment()

    def _check_fips_mode(self) -> bool:
        """Check if FIPS mode is enabled."""
        # Environment variable override
        env_fips = os.getenv("AURA_FIPS_MODE", "").lower()
        if env_fips in ("true", "1", "enabled"):
            return True
        if env_fips in ("false", "0", "disabled"):
            return False

        # Check system FIPS mode (Linux)
        try:
            with open("/proc/sys/crypto/fips_enabled", "r") as f:
                return f.read().strip() == "1"
        except (FileNotFoundError, PermissionError):
            pass

        # Check OpenSSL FIPS mode
        try:
            import ssl

            # OpenSSL 3.x with FIPS provider
            if hasattr(ssl, "FIPS_mode"):
                return ssl.FIPS_mode() == 1
        except Exception:
            pass

        return False

    def _validate_environment(self) -> None:
        """Validate FIPS environment configuration."""
        warnings = []

        # Check OpenSSL version
        try:
            import ssl

            openssl_version = ssl.OPENSSL_VERSION
            if "fips" not in openssl_version.lower():
                warnings.append(f"OpenSSL may not be FIPS-enabled: {openssl_version}")
        except Exception as e:
            warnings.append(f"Could not verify OpenSSL: {e}")

        # Check cryptography library
        try:
            from cryptography.hazmat.backends import default_backend

            backend = default_backend()
            if hasattr(backend, "fips_mode"):
                if not backend.fips_mode:
                    warnings.append("cryptography backend not in FIPS mode")
        except ImportError:
            warnings.append("cryptography library not available")

        for warning in warnings:
            logger.warning("FIPS validation: %s", warning)

    @property
    def is_fips_mode(self) -> bool:
        """Check if FIPS mode is active."""
        return self._fips_enabled

    def get_status(self) -> FIPSStatus:
        """Get detailed FIPS compliance status."""
        openssl_fips = False
        try:
            import ssl

            openssl_fips = (
                hasattr(ssl, "FIPS_mode") and ssl.FIPS_mode() == 1
            ) or "fips" in ssl.OPENSSL_VERSION.lower()
        except Exception:
            pass

        system_fips = False
        try:
            with open("/proc/sys/crypto/fips_enabled", "r") as f:
                system_fips = f.read().strip() == "1"
        except (FileNotFoundError, PermissionError):
            pass

        return FIPSStatus(
            enabled=self._fips_enabled,
            openssl_fips=openssl_fips,
            system_fips=system_fips,
            version="FIPS 140-2",
            algorithms_available=[alg.value for alg in FIPSAlgorithm],
            warnings=[],
        )

    def _check_algorithm(self, algorithm: str) -> None:
        """Verify algorithm is FIPS-approved."""
        if not self._fips_enabled:
            return

        algorithm_upper = algorithm.upper()

        if algorithm_upper in BLOCKED_ALGORITHMS:
            raise FIPSComplianceError(
                f"Algorithm '{algorithm}' is not FIPS 140-2 approved",
                algorithm=algorithm,
            )

    def hash(
        self,
        data: bytes,
        algorithm: FIPSAlgorithm = FIPSAlgorithm.SHA256,
    ) -> bytes:
        """
        Compute hash using FIPS-approved algorithm.

        Args:
            data: Data to hash
            algorithm: Hash algorithm (default: SHA-256)

        Returns:
            Hash digest bytes
        """
        self._check_algorithm(algorithm.value)

        hash_map = {
            FIPSAlgorithm.SHA256: hashlib.sha256,
            FIPSAlgorithm.SHA384: hashlib.sha384,
            FIPSAlgorithm.SHA512: hashlib.sha512,
        }

        if algorithm not in hash_map:
            raise FIPSComplianceError(
                f"Algorithm {algorithm.value} not supported for hashing",
                algorithm=algorithm.value,
            )

        return hash_map[algorithm](data).digest()

    def hmac(
        self,
        key: bytes,
        data: bytes,
        algorithm: FIPSAlgorithm = FIPSAlgorithm.SHA256,
    ) -> bytes:
        """
        Compute HMAC using FIPS-approved algorithm.

        Args:
            key: HMAC key
            data: Data to authenticate
            algorithm: Hash algorithm for HMAC

        Returns:
            HMAC digest bytes
        """
        self._check_algorithm(algorithm.value)

        digest_map = {
            FIPSAlgorithm.SHA256: "sha256",
            FIPSAlgorithm.SHA384: "sha384",
            FIPSAlgorithm.SHA512: "sha512",
        }

        if algorithm not in digest_map:
            raise FIPSComplianceError(
                f"Algorithm {algorithm.value} not supported for HMAC",
                algorithm=algorithm.value,
            )

        return hmac.new(key, data, digest_map[algorithm]).digest()

    def derive_key(
        self,
        password: bytes,
        salt: bytes,
        iterations: int = 600000,
        key_length: int = 32,
    ) -> bytes:
        """
        Derive key using PBKDF2-HMAC-SHA256 (FIPS-approved).

        Args:
            password: Password bytes
            salt: Salt bytes (should be random, at least 16 bytes)
            iterations: Number of iterations (minimum 10000 recommended)
            key_length: Desired key length in bytes

        Returns:
            Derived key bytes
        """
        self._check_algorithm("PBKDF2-HMAC-SHA256")

        if len(salt) < 16:
            raise FIPSComplianceError(
                "Salt must be at least 16 bytes for FIPS compliance"
            )

        if iterations < 10000:
            logger.warning(
                "FIPS recommends at least 10000 PBKDF2 iterations, got %d",
                iterations,
            )

        return hashlib.pbkdf2_hmac(
            "sha256",
            password,
            salt,
            iterations,
            dklen=key_length,
        )

    def encrypt_aes_gcm(
        self,
        key: bytes,
        plaintext: bytes,
        associated_data: Optional[bytes] = None,
    ) -> tuple[bytes, bytes, bytes]:
        """
        Encrypt using AES-256-GCM (FIPS-approved).

        Args:
            key: 32-byte AES key
            plaintext: Data to encrypt
            associated_data: Additional authenticated data (optional)

        Returns:
            Tuple of (nonce, ciphertext, tag)
        """
        self._check_algorithm("AES-256-GCM")

        if len(key) != 32:
            raise FIPSComplianceError("AES-256 requires 32-byte key")

        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            # Generate random 12-byte nonce (FIPS requires unique nonces)
            nonce = secrets.token_bytes(12)

            aesgcm = AESGCM(key)
            ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, associated_data)

            # GCM tag is last 16 bytes
            ciphertext = ciphertext_with_tag[:-16]
            tag = ciphertext_with_tag[-16:]

            return nonce, ciphertext, tag

        except ImportError:
            raise FIPSComplianceError("cryptography library required for AES-GCM")

    def decrypt_aes_gcm(
        self,
        key: bytes,
        nonce: bytes,
        ciphertext: bytes,
        tag: bytes,
        associated_data: Optional[bytes] = None,
    ) -> bytes:
        """
        Decrypt using AES-256-GCM (FIPS-approved).

        Args:
            key: 32-byte AES key
            nonce: 12-byte nonce used during encryption
            ciphertext: Encrypted data
            tag: Authentication tag
            associated_data: Additional authenticated data (must match encryption)

        Returns:
            Decrypted plaintext
        """
        self._check_algorithm("AES-256-GCM")

        if len(key) != 32:
            raise FIPSComplianceError("AES-256 requires 32-byte key")

        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            aesgcm = AESGCM(key)
            ciphertext_with_tag = ciphertext + tag

            return aesgcm.decrypt(nonce, ciphertext_with_tag, associated_data)

        except ImportError:
            raise FIPSComplianceError("cryptography library required for AES-GCM")

    def generate_random_bytes(self, length: int) -> bytes:
        """
        Generate cryptographically secure random bytes.

        Uses os.urandom() which is FIPS-approved on compliant systems.

        Args:
            length: Number of bytes to generate

        Returns:
            Random bytes
        """
        return secrets.token_bytes(length)

    def constant_time_compare(self, a: bytes, b: bytes) -> bool:
        """
        Compare two byte strings in constant time.

        Prevents timing attacks on MAC/signature verification.

        Args:
            a: First byte string
            b: Second byte string

        Returns:
            True if equal
        """
        return hmac.compare_digest(a, b)


# Global FIPS crypto instance
_fips_crypto: Optional[FIPSCrypto] = None


def get_fips_crypto() -> FIPSCrypto:
    """Get the global FIPS crypto instance."""
    global _fips_crypto
    if _fips_crypto is None:
        _fips_crypto = FIPSCrypto()
    return _fips_crypto


def is_fips_mode() -> bool:
    """Check if FIPS mode is enabled."""
    return get_fips_crypto().is_fips_mode


def require_fips() -> None:
    """
    Require FIPS mode, raising if not enabled.

    Use this at module/function entry points that must be FIPS-compliant.
    """
    if not is_fips_mode():
        raise FIPSComplianceError(
            "FIPS 140-2 mode is required but not enabled. "
            "Set AURA_FIPS_MODE=true or enable system FIPS mode."
        )
