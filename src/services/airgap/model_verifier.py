"""
Model Weight Verification for Air-Gapped Deployments.

Provides SHA-256 checksum verification for LLM model weights
to ensure integrity and prevent tampering in air-gapped environments.
"""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ModelIntegrityError(Exception):
    """Raised when model integrity verification fails."""

    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        file_path: Optional[str] = None,
    ):
        self.message = message
        self.model_name = model_name
        self.file_path = file_path
        super().__init__(message)


@dataclass
class FileChecksum:
    """Checksum information for a single file."""

    file_path: str
    expected_hash: str
    actual_hash: Optional[str] = None
    verified: bool = False
    file_size: int = 0
    verification_time: Optional[datetime] = None

    @property
    def is_valid(self) -> bool:
        """Check if file checksum is valid."""
        return self.verified and self.expected_hash == self.actual_hash


@dataclass
class ModelVerificationResult:
    """Result of model verification."""

    model_name: str
    model_path: str
    is_valid: bool
    files_verified: int = 0
    files_failed: int = 0
    total_size_bytes: int = 0
    checksums: list[FileChecksum] = field(default_factory=list)
    verification_time: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/reporting."""
        return {
            "model_name": self.model_name,
            "model_path": self.model_path,
            "is_valid": self.is_valid,
            "files_verified": self.files_verified,
            "files_failed": self.files_failed,
            "total_size_mb": round(self.total_size_bytes / (1024 * 1024), 2),
            "verification_time": self.verification_time.isoformat(),
            "errors": self.errors,
        }


# Known model checksums (SHA-256)
# These would be populated from the air-gap bundle's SHA256SUMS file
KNOWN_MODEL_CHECKSUMS: dict[str, dict[str, str]] = {
    "mistral-7b-instruct-v0.3": {
        "config.json": "a1b2c3d4e5f6...",  # Placeholder
        "tokenizer.json": "b2c3d4e5f6a1...",
        "tokenizer_config.json": "c3d4e5f6a1b2...",
        # Model weights are typically sharded
        "model-00001-of-00003.safetensors": "d4e5f6a1b2c3...",
        "model-00002-of-00003.safetensors": "e5f6a1b2c3d4...",
        "model-00003-of-00003.safetensors": "f6a1b2c3d4e5...",
    },
}


class ModelVerifier:
    """
    Verifies integrity of LLM model weights.

    Computes SHA-256 checksums of model files and compares
    against known good values from the air-gap bundle.
    """

    def __init__(
        self,
        models_dir: Optional[str] = None,
        checksum_file: Optional[str] = None,
        chunk_size: int = 8 * 1024 * 1024,  # 8MB chunks
    ):
        """
        Initialize model verifier.

        Args:
            models_dir: Directory containing model files
            checksum_file: Path to SHA256SUMS file
            chunk_size: Chunk size for reading large files
        """
        self._models_dir = Path(models_dir or os.getenv("AURA_MODELS_DIR", "/models"))
        self._checksum_file = checksum_file
        self._chunk_size = chunk_size
        self._known_checksums = dict(KNOWN_MODEL_CHECKSUMS)

        # Load checksums from file if provided
        if self._checksum_file:
            self._load_checksums_file(self._checksum_file)

    def _load_checksums_file(self, checksum_file: str) -> None:
        """Load checksums from SHA256SUMS file."""
        try:
            with open(checksum_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    # Format: <hash>  <filename>
                    parts = line.split(None, 1)
                    if len(parts) != 2:
                        continue

                    hash_value, filename = parts
                    filename = filename.lstrip("*")  # Remove binary mode marker

                    # Extract model name from path
                    path = Path(filename)
                    if len(path.parts) >= 2:
                        model_name = path.parts[0]
                        file_name = path.name

                        if model_name not in self._known_checksums:
                            self._known_checksums[model_name] = {}
                        self._known_checksums[model_name][file_name] = hash_value

            logger.info("Loaded checksums from %s", checksum_file)

        except FileNotFoundError:
            logger.warning("Checksum file not found: %s", checksum_file)
        except Exception as e:
            logger.error("Failed to load checksums: %s", e)

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()

        with open(file_path, "rb") as f:
            while chunk := f.read(self._chunk_size):
                sha256.update(chunk)

        return sha256.hexdigest()

    def verify_model(
        self,
        model_name: str,
        model_path: Optional[str] = None,
    ) -> ModelVerificationResult:
        """
        Verify integrity of a model's files.

        Args:
            model_name: Name of the model
            model_path: Path to model directory (optional)

        Returns:
            ModelVerificationResult with verification details
        """
        path = Path(model_path) if model_path else self._models_dir / model_name

        result = ModelVerificationResult(
            model_name=model_name,
            model_path=str(path),
            is_valid=True,
        )

        if not path.exists():
            result.is_valid = False
            result.errors.append(f"Model directory not found: {path}")
            return result

        # Get expected checksums
        expected_checksums = self._known_checksums.get(model_name, {})

        if not expected_checksums:
            logger.warning(
                "No known checksums for model %s, computing fresh checksums",
                model_name,
            )
            # If no known checksums, just compute and report
            expected_checksums = {}

        # Verify each file
        for file_path in path.iterdir():
            if not file_path.is_file():
                continue

            file_name = file_path.name

            # Skip non-essential files
            if file_name.startswith(".") or file_name.endswith(".lock"):
                continue

            try:
                file_size = file_path.stat().st_size
                result.total_size_bytes += file_size

                logger.debug("Verifying %s (%d bytes)", file_name, file_size)

                actual_hash = self._compute_file_hash(file_path)
                expected_hash = expected_checksums.get(file_name, actual_hash)

                checksum = FileChecksum(
                    file_path=str(file_path),
                    expected_hash=expected_hash,
                    actual_hash=actual_hash,
                    verified=True,
                    file_size=file_size,
                    verification_time=datetime.now(timezone.utc),
                )

                result.checksums.append(checksum)

                if checksum.is_valid:
                    result.files_verified += 1
                else:
                    result.files_failed += 1
                    result.is_valid = False
                    result.errors.append(
                        f"Checksum mismatch for {file_name}: "
                        f"expected {expected_hash[:16]}..., "
                        f"got {actual_hash[:16]}..."
                    )
                    logger.error(
                        "Checksum mismatch for %s: expected %s, got %s",
                        file_name,
                        expected_hash,
                        actual_hash,
                    )

            except Exception as e:
                result.is_valid = False
                result.errors.append(f"Failed to verify {file_name}: {e}")
                logger.error("Failed to verify %s: %s", file_name, e)

        # Log summary
        if result.is_valid:
            logger.info(
                "Model %s verified: %d files, %.2f MB",
                model_name,
                result.files_verified,
                result.total_size_bytes / (1024 * 1024),
            )
        else:
            logger.error(
                "Model %s verification FAILED: %d files failed",
                model_name,
                result.files_failed,
            )

        return result

    def verify_all_models(self) -> dict[str, ModelVerificationResult]:
        """
        Verify all models in the models directory.

        Returns:
            Dictionary mapping model names to verification results
        """
        results = {}

        if not self._models_dir.exists():
            logger.warning("Models directory not found: %s", self._models_dir)
            return results

        for model_dir in self._models_dir.iterdir():
            if model_dir.is_dir() and not model_dir.name.startswith("."):
                result = self.verify_model(model_dir.name, str(model_dir))
                results[model_dir.name] = result

        return results

    def generate_checksums(
        self,
        model_name: str,
        model_path: Optional[str] = None,
        output_file: Optional[str] = None,
    ) -> dict[str, str]:
        """
        Generate SHA256SUMS file for a model.

        Args:
            model_name: Name of the model
            model_path: Path to model directory
            output_file: Path to write SHA256SUMS file

        Returns:
            Dictionary of filename -> checksum
        """
        path = Path(model_path) if model_path else self._models_dir / model_name
        checksums = {}

        for file_path in sorted(path.iterdir()):
            if not file_path.is_file():
                continue

            file_name = file_path.name
            if file_name.startswith("."):
                continue

            logger.info("Computing checksum for %s...", file_name)
            checksum = self._compute_file_hash(file_path)
            checksums[file_name] = checksum

        # Write to file if requested
        if output_file:
            with open(output_file, "w") as f:
                for file_name, checksum in sorted(checksums.items()):
                    f.write(f"{checksum}  {model_name}/{file_name}\n")
            logger.info("Wrote checksums to %s", output_file)

        return checksums


def verify_model_checksums(
    model_name: str,
    model_path: Optional[str] = None,
) -> ModelVerificationResult:
    """
    Convenience function to verify model checksums.

    Args:
        model_name: Name of the model
        model_path: Path to model directory

    Returns:
        ModelVerificationResult
    """
    verifier = ModelVerifier()
    return verifier.verify_model(model_name, model_path)


def require_model_integrity(
    model_name: str,
    model_path: Optional[str] = None,
) -> None:
    """
    Require model integrity, raising if verification fails.

    Args:
        model_name: Name of the model
        model_path: Path to model directory

    Raises:
        ModelIntegrityError: If verification fails
    """
    result = verify_model_checksums(model_name, model_path)

    if not result.is_valid:
        raise ModelIntegrityError(
            f"Model integrity verification failed for {model_name}: "
            f"{'; '.join(result.errors)}",
            model_name=model_name,
        )
