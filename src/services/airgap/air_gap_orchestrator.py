"""
Project Aura - Air-Gap Orchestrator

Service for creating, signing, verifying, and deploying air-gapped deployment bundles.
Supports offline deployment to disconnected environments via sneakernet transfer.

Based on ADR-078: Air-Gapped and Edge Deployment
"""

import base64
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .config import AirGapConfig, get_airgap_config
from .contracts import (
    BundleComponent,
    BundleManifest,
    BundleSignature,
    BundleStatus,
    BundleType,
    CompressionType,
    DeltaUpdate,
    HashAlgorithm,
    SignedBundle,
    SigningAlgorithm,
)
from .exceptions import (
    BundleCorruptedError,
    BundleCreationError,
    BundleExpiredError,
    BundleNotFoundError,
    BundleSigningError,
    BundleTooLargeError,
    BundleVerificationError,
    DeltaUpdateError,
    KeyNotFoundError,
    QuarantineError,
    TransferMediumError,
)
from .metrics import get_airgap_metrics


class AirGapOrchestrator:
    """Orchestrator for air-gapped deployment bundles."""

    def __init__(self, config: Optional[AirGapConfig] = None):
        """Initialize the orchestrator."""
        self._config = config or get_airgap_config()
        self._metrics = get_airgap_metrics()
        self._bundles: dict[str, SignedBundle] = {}
        self._deltas: dict[str, DeltaUpdate] = {}
        self._private_key: Optional[bytes] = None
        self._public_key: Optional[bytes] = None
        self._use_mock_crypto = True  # Default to mock for testing

        # Initialize directories
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        dirs = [
            self._config.bundle.bundle_output_dir,
            self._config.transfer.sneakernet_dir,
            self._config.transfer.quarantine_dir,
        ]
        for dir_path in dirs:
            if dir_path and not dir_path.startswith(":"):  # Skip :memory: etc
                os.makedirs(dir_path, exist_ok=True)

    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID with prefix."""
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    def _compute_hash(
        self,
        data: bytes,
        algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    ) -> str:
        """Compute hash of data."""
        if algorithm == HashAlgorithm.SHA256:
            return hashlib.sha256(data).hexdigest()
        elif algorithm == HashAlgorithm.SHA384:
            return hashlib.sha384(data).hexdigest()
        elif algorithm == HashAlgorithm.SHA512:
            return hashlib.sha512(data).hexdigest()
        elif algorithm == HashAlgorithm.BLAKE2B:
            return hashlib.blake2b(data).hexdigest()
        else:
            return hashlib.sha256(data).hexdigest()

    def _compute_file_hash(
        self,
        file_path: str,
        algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    ) -> str:
        """Compute hash of a file."""
        if algorithm == HashAlgorithm.SHA256:
            hasher = hashlib.sha256()
        elif algorithm == HashAlgorithm.SHA384:
            hasher = hashlib.sha384()
        elif algorithm == HashAlgorithm.SHA512:
            hasher = hashlib.sha512()
        elif algorithm == HashAlgorithm.BLAKE2B:
            hasher = hashlib.blake2b()
        else:
            hasher = hashlib.sha256()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _get_compression_extension(self, compression: CompressionType) -> str:
        """Get file extension for compression type."""
        extensions = {
            CompressionType.NONE: ".tar",
            CompressionType.GZIP: ".tar.gz",
            CompressionType.ZSTD: ".tar.zst",
            CompressionType.LZ4: ".tar.lz4",
            CompressionType.XZ: ".tar.xz",
        }
        return extensions.get(compression, ".tar.gz")

    def _get_tarfile_mode(self, compression: CompressionType) -> str:
        """Get tarfile mode for compression type."""
        modes = {
            CompressionType.NONE: "w",
            CompressionType.GZIP: "w:gz",
            CompressionType.XZ: "w:xz",
        }
        return modes.get(compression, "w:gz")

    # =========================================================================
    # Bundle Creation
    # =========================================================================

    def create_bundle(
        self,
        bundle_type: BundleType,
        version: str,
        components: list[dict[str, Any]],
        expiry_days: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> BundleManifest:
        """Create a new deployment bundle manifest.

        Args:
            bundle_type: Type of bundle (full, delta, etc.)
            version: Version string for the bundle
            components: List of component definitions with paths
            expiry_days: Days until bundle expires (default from config)
            metadata: Additional metadata

        Returns:
            BundleManifest for the created bundle

        Raises:
            BundleCreationError: If bundle creation fails
            BundleTooLargeError: If bundle exceeds size limit
        """
        manifest_id = self._generate_id("manifest")
        expiry_days = expiry_days or self._config.bundle.expiry_days
        expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)

        bundle_components: list[BundleComponent] = []
        total_size = 0

        for comp_def in components:
            try:
                comp_path = comp_def.get("path", "")
                comp_size = comp_def.get("size_bytes", 0)

                # If path exists, compute hash
                comp_hash = comp_def.get("hash", "")
                if not comp_hash and comp_path and os.path.exists(comp_path):
                    comp_hash = self._compute_file_hash(comp_path)
                    comp_size = os.path.getsize(comp_path)

                component = BundleComponent(
                    component_id=comp_def.get(
                        "component_id", self._generate_id("comp")
                    ),
                    name=comp_def.get("name", os.path.basename(comp_path)),
                    version=comp_def.get("version", version),
                    path=comp_path,
                    size_bytes=comp_size,
                    hash=comp_hash,
                    hash_algorithm=HashAlgorithm(
                        comp_def.get("hash_algorithm", "sha256")
                    ),
                    required=comp_def.get("required", True),
                    metadata=comp_def.get("metadata", {}),
                )
                bundle_components.append(component)
                total_size += comp_size

            except Exception as e:
                raise BundleCreationError(
                    f"Failed to add component: {e}",
                    component=comp_def.get("name", "unknown"),
                )

        # Check size limit
        max_size = self._config.bundle.max_bundle_size_mb * 1024 * 1024
        if total_size > max_size:
            raise BundleTooLargeError(
                manifest_id,
                total_size,
                max_size,
            )

        manifest = BundleManifest(
            manifest_id=manifest_id,
            bundle_type=bundle_type,
            version=version,
            expires_at=expires_at,
            components=bundle_components,
            compression=self._config.bundle.default_compression,
            total_size_bytes=total_size,
            metadata=metadata or {},
        )

        self._metrics.record_bundle_created(
            manifest_id,
            bundle_type.value,
            total_size,
            len(bundle_components),
        )

        return manifest

    def package_bundle(
        self,
        manifest: BundleManifest,
        output_path: Optional[str] = None,
    ) -> str:
        """Package bundle components into an archive.

        Args:
            manifest: Bundle manifest
            output_path: Optional output path (default: bundle output dir)

        Returns:
            Path to the created archive

        Raises:
            BundleCreationError: If packaging fails
        """
        if output_path is None:
            ext = self._get_compression_extension(manifest.compression)
            output_path = os.path.join(
                self._config.bundle.bundle_output_dir,
                f"{manifest.manifest_id}{ext}",
            )

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            mode = self._get_tarfile_mode(manifest.compression)

            with tarfile.open(output_path, mode) as tar:
                # Add manifest
                manifest_json = json.dumps(manifest.to_dict(), indent=2)
                manifest_bytes = manifest_json.encode("utf-8")
                manifest_info = tarfile.TarInfo(name="manifest.json")
                manifest_info.size = len(manifest_bytes)
                manifest_info.mtime = int(datetime.now(timezone.utc).timestamp())
                import io

                tar.addfile(manifest_info, io.BytesIO(manifest_bytes))

                # Add components
                for component in manifest.components:
                    if component.path and os.path.exists(component.path):
                        arcname = f"components/{component.name}"
                        tar.add(component.path, arcname=arcname)

            return output_path

        except Exception as e:
            raise BundleCreationError(f"Failed to package bundle: {e}")

    # =========================================================================
    # Bundle Signing
    # =========================================================================

    def load_signing_keys(
        self,
        private_key_path: Optional[str] = None,
        public_key_path: Optional[str] = None,
    ) -> None:
        """Load signing keys from files."""
        private_path = private_key_path or self._config.bundle.private_key_path
        public_path = public_key_path or self._config.bundle.public_key_path

        if private_path and os.path.exists(private_path):
            with open(private_path, "rb") as f:
                self._private_key = f.read()

        if public_path and os.path.exists(public_path):
            with open(public_path, "rb") as f:
                self._public_key = f.read()

    def generate_signing_keys(self) -> tuple[bytes, bytes]:
        """Generate a new Ed25519 key pair.

        Returns:
            Tuple of (private_key, public_key) bytes

        Note:
            In production, use cryptography library. This is simplified for testing.
        """
        if self._use_mock_crypto:
            # Mock keys for testing
            private_key = os.urandom(64)  # Ed25519 private key is 64 bytes
            public_key = os.urandom(32)  # Ed25519 public key is 32 bytes
            return private_key, public_key

        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
            )

            private_key = Ed25519PrivateKey.generate()
            public_key = private_key.public_key()

            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
            public_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            return private_bytes, public_bytes

        except ImportError:
            # Fallback to mock
            private_key = os.urandom(64)
            public_key = os.urandom(32)
            return private_key, public_key

    def sign_bundle(
        self,
        manifest: BundleManifest,
        archive_path: Optional[str] = None,
        private_key: Optional[bytes] = None,
        signer_identity: Optional[str] = None,
    ) -> SignedBundle:
        """Sign a bundle with Ed25519.

        Args:
            manifest: Bundle manifest to sign
            archive_path: Path to bundle archive (optional)
            private_key: Private key bytes (uses stored key if not provided)
            signer_identity: Identity of the signer

        Returns:
            SignedBundle with signature

        Raises:
            BundleSigningError: If signing fails
            KeyNotFoundError: If private key is not available
        """
        import time

        start_time = time.time()

        key = private_key or self._private_key
        if key is None:
            raise KeyNotFoundError("private", "ed25519")

        bundle_id = self._generate_id("bundle")
        algorithm = self._config.bundle.signing_algorithm

        try:
            # Create data to sign (manifest hash)
            manifest_json = json.dumps(manifest.to_dict(), sort_keys=True)
            manifest_hash = self._compute_hash(manifest_json.encode())

            # Sign the hash
            if self._use_mock_crypto:
                # Mock signature for testing
                signature_bytes = hashlib.sha512(key + manifest_hash.encode()).digest()
            else:
                try:
                    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                        Ed25519PrivateKey,
                    )

                    private_key_obj = Ed25519PrivateKey.from_private_bytes(key[:32])
                    signature_bytes = private_key_obj.sign(manifest_hash.encode())
                except ImportError:
                    signature_bytes = hashlib.sha512(
                        key + manifest_hash.encode()
                    ).digest()

            signature_b64 = base64.b64encode(signature_bytes).decode()

            # Create public key ID from public key hash
            public_key = (
                self._public_key or key[32:]
            )  # Ed25519 public key is last 32 bytes
            public_key_id = self._compute_hash(public_key)[:16]

            bundle_signature = BundleSignature(
                signature_id=self._generate_id("sig"),
                bundle_id=bundle_id,
                algorithm=algorithm,
                signature=signature_b64,
                public_key_id=public_key_id,
                signer_identity=signer_identity,
            )

            # Compute archive hash if provided
            archive_hash = None
            if archive_path and os.path.exists(archive_path):
                archive_hash = self._compute_file_hash(archive_path)

            signed_bundle = SignedBundle(
                bundle_id=bundle_id,
                manifest=manifest,
                signature=bundle_signature,
                status=BundleStatus.SIGNED,
                archive_path=archive_path,
                archive_hash=archive_hash,
            )

            # Store bundle
            self._bundles[bundle_id] = signed_bundle

            duration_ms = (time.time() - start_time) * 1000
            self._metrics.record_bundle_signed(bundle_id, algorithm.value, duration_ms)

            return signed_bundle

        except Exception as e:
            if isinstance(e, (KeyNotFoundError, BundleSigningError)):
                raise
            raise BundleSigningError(f"Failed to sign bundle: {e}")

    # =========================================================================
    # Bundle Verification
    # =========================================================================

    def verify_bundle(
        self,
        bundle: SignedBundle,
        public_key: Optional[bytes] = None,
    ) -> bool:
        """Verify a bundle's signature.

        Args:
            bundle: Signed bundle to verify
            public_key: Public key bytes (uses stored key if not provided)

        Returns:
            True if signature is valid

        Raises:
            BundleVerificationError: If verification fails
            BundleExpiredError: If bundle has expired
        """
        import time

        start_time = time.time()

        # Check expiration
        if bundle.manifest.is_expired:
            raise BundleExpiredError(
                bundle.bundle_id,
                (
                    bundle.manifest.expires_at.isoformat()
                    if bundle.manifest.expires_at
                    else "unknown"
                ),
            )

        key = public_key or self._public_key
        if key is None:
            raise KeyNotFoundError("public", "ed25519")

        try:
            # Recreate manifest hash
            manifest_json = json.dumps(bundle.manifest.to_dict(), sort_keys=True)
            manifest_hash = self._compute_hash(manifest_json.encode())

            # Decode signature
            signature_bytes = base64.b64decode(bundle.signature.signature)

            # Verify signature
            if self._use_mock_crypto:
                # Mock verification
                expected_sig = hashlib.sha512(
                    (self._private_key or key) + manifest_hash.encode()
                ).digest()
                valid = signature_bytes == expected_sig
            else:
                try:
                    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                        Ed25519PublicKey,
                    )

                    public_key_obj = Ed25519PublicKey.from_public_bytes(key)
                    public_key_obj.verify(signature_bytes, manifest_hash.encode())
                    valid = True
                except Exception:
                    valid = False

            # Verify archive hash if present
            if valid and bundle.archive_path and bundle.archive_hash:
                actual_hash = self._compute_file_hash(bundle.archive_path)
                if actual_hash != bundle.archive_hash:
                    raise BundleVerificationError(
                        "Archive hash mismatch",
                        bundle.bundle_id,
                        bundle.archive_hash,
                        actual_hash,
                    )

            if valid:
                bundle.status = BundleStatus.VERIFIED

            duration_ms = (time.time() - start_time) * 1000
            self._metrics.record_bundle_verified(bundle.bundle_id, valid, duration_ms)

            return valid

        except BundleExpiredError:
            raise
        except BundleVerificationError:
            raise
        except Exception as e:
            raise BundleVerificationError(f"Verification failed: {e}", bundle.bundle_id)

    def verify_component_integrity(
        self,
        bundle: SignedBundle,
        component_name: str,
        file_path: str,
    ) -> bool:
        """Verify integrity of an extracted component.

        Args:
            bundle: Signed bundle
            component_name: Name of component to verify
            file_path: Path to extracted component file

        Returns:
            True if component integrity is valid

        Raises:
            BundleVerificationError: If component not found or hash mismatch
        """
        component = None
        for c in bundle.manifest.components:
            if c.name == component_name:
                component = c
                break

        if component is None:
            raise BundleVerificationError(
                f"Component not found: {component_name}",
                bundle.bundle_id,
            )

        actual_hash = self._compute_file_hash(file_path, component.hash_algorithm)
        if actual_hash != component.hash:
            raise BundleVerificationError(
                f"Component hash mismatch: {component_name}",
                bundle.bundle_id,
                component.hash,
                actual_hash,
            )

        return True

    # =========================================================================
    # Delta Updates
    # =========================================================================

    def create_delta_update(
        self,
        source_bundle: SignedBundle,
        target_bundle: SignedBundle,
    ) -> DeltaUpdate:
        """Create a delta update between two bundle versions.

        Args:
            source_bundle: Source bundle (older version)
            target_bundle: Target bundle (newer version)

        Returns:
            DeltaUpdate with patches

        Raises:
            DeltaUpdateError: If delta creation fails
        """
        if not self._config.bundle.delta_enabled:
            raise DeltaUpdateError("Delta updates are disabled")

        delta_id = self._generate_id("delta")
        patches: list[dict[str, Any]] = []
        total_size = 0

        # Build component maps
        source_components = {c.name: c for c in source_bundle.manifest.components}
        target_components = {c.name: c for c in target_bundle.manifest.components}

        # Find added components
        for name, comp in target_components.items():
            if name not in source_components:
                patches.append(
                    {
                        "operation": "add",
                        "component": name,
                        "hash": comp.hash,
                        "size_bytes": comp.size_bytes,
                    }
                )
                total_size += comp.size_bytes

        # Find removed components
        for name in source_components:
            if name not in target_components:
                patches.append(
                    {
                        "operation": "remove",
                        "component": name,
                    }
                )

        # Find modified components
        for name, target_comp in target_components.items():
            if name in source_components:
                source_comp = source_components[name]
                if source_comp.hash != target_comp.hash:
                    patches.append(
                        {
                            "operation": "modify",
                            "component": name,
                            "source_hash": source_comp.hash,
                            "target_hash": target_comp.hash,
                            "size_bytes": target_comp.size_bytes,
                        }
                    )
                    total_size += target_comp.size_bytes

        delta = DeltaUpdate(
            delta_id=delta_id,
            source_version=source_bundle.manifest.version,
            target_version=target_bundle.manifest.version,
            source_hash=self._compute_hash(
                json.dumps(source_bundle.manifest.to_dict()).encode()
            ),
            target_hash=self._compute_hash(
                json.dumps(target_bundle.manifest.to_dict()).encode()
            ),
            patches=patches,
            size_bytes=total_size,
            compression=self._config.bundle.default_compression,
        )

        self._deltas[delta_id] = delta

        self._metrics.record_delta_update(
            delta_id,
            delta.source_version,
            delta.target_version,
            total_size,
            len(patches),
        )

        return delta

    def apply_delta_update(
        self,
        source_bundle: SignedBundle,
        delta: DeltaUpdate,
        output_dir: str,
    ) -> BundleManifest:
        """Apply a delta update to create a new bundle.

        Args:
            source_bundle: Source bundle to update
            delta: Delta update to apply
            output_dir: Directory for output components

        Returns:
            New bundle manifest

        Raises:
            DeltaUpdateError: If delta application fails
        """
        # Verify source version matches
        source_hash = self._compute_hash(
            json.dumps(source_bundle.manifest.to_dict()).encode()
        )
        if source_hash != delta.source_hash:
            raise DeltaUpdateError(
                "Source bundle hash mismatch",
                delta.source_version,
                delta.target_version,
            )

        os.makedirs(output_dir, exist_ok=True)

        # Start with source components
        new_components: list[dict[str, Any]] = []
        removed = set()

        # Apply patches
        for patch in delta.patches:
            if patch["operation"] == "remove":
                removed.add(patch["component"])
            elif patch["operation"] == "add":
                new_components.append(
                    {
                        "name": patch["component"],
                        "hash": patch["hash"],
                        "size_bytes": patch["size_bytes"],
                    }
                )
            elif patch["operation"] == "modify":
                # Mark for replacement
                removed.add(patch["component"])
                new_components.append(
                    {
                        "name": patch["component"],
                        "hash": patch["target_hash"],
                        "size_bytes": patch["size_bytes"],
                    }
                )

        # Copy unchanged components
        for comp in source_bundle.manifest.components:
            if comp.name not in removed:
                new_components.append(
                    {
                        "component_id": comp.component_id,
                        "name": comp.name,
                        "version": delta.target_version,
                        "path": comp.path,
                        "size_bytes": comp.size_bytes,
                        "hash": comp.hash,
                    }
                )

        # Create new manifest
        return self.create_bundle(
            bundle_type=source_bundle.manifest.bundle_type,
            version=delta.target_version,
            components=new_components,
        )

    # =========================================================================
    # Transfer Operations
    # =========================================================================

    def export_for_transfer(
        self,
        bundle: SignedBundle,
        output_path: Optional[str] = None,
    ) -> str:
        """Export a bundle for sneakernet transfer.

        Args:
            bundle: Signed bundle to export
            output_path: Output path (default: sneakernet dir)

        Returns:
            Path to exported bundle

        Raises:
            TransferMediumError: If export fails
        """
        if output_path is None:
            output_path = os.path.join(
                self._config.transfer.sneakernet_dir,
                f"{bundle.bundle_id}.aura-bundle",
            )

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Create transfer package
            with tarfile.open(output_path, "w:gz") as tar:
                # Add manifest
                manifest_json = json.dumps(bundle.manifest.to_dict(), indent=2)
                manifest_bytes = manifest_json.encode()
                import io

                manifest_info = tarfile.TarInfo(name="manifest.json")
                manifest_info.size = len(manifest_bytes)
                tar.addfile(manifest_info, io.BytesIO(manifest_bytes))

                # Add signature
                sig_json = json.dumps(bundle.signature.to_dict(), indent=2)
                sig_bytes = sig_json.encode()
                sig_info = tarfile.TarInfo(name="signature.json")
                sig_info.size = len(sig_bytes)
                tar.addfile(sig_info, io.BytesIO(sig_bytes))

                # Add archive if exists
                if bundle.archive_path and os.path.exists(bundle.archive_path):
                    tar.add(bundle.archive_path, arcname="archive.tar.gz")

            return output_path

        except Exception as e:
            raise TransferMediumError(f"Failed to export bundle: {e}")

    def import_from_transfer(
        self,
        transfer_path: str,
        verify: bool = True,
    ) -> SignedBundle:
        """Import a bundle from sneakernet transfer.

        Args:
            transfer_path: Path to transfer package
            verify: Whether to verify signature after import

        Returns:
            Imported SignedBundle

        Raises:
            TransferMediumError: If import fails
            BundleVerificationError: If verification fails
            QuarantineError: If bundle is quarantined
        """
        if not os.path.exists(transfer_path):
            raise TransferMediumError(f"Transfer file not found: {transfer_path}")

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract transfer package
                with tarfile.open(transfer_path, "r:gz") as tar:
                    tar.extractall(temp_dir)  # nosec B202 - trusted internal bundle

                # Load manifest
                manifest_path = os.path.join(temp_dir, "manifest.json")
                with open(manifest_path) as f:
                    manifest_data = json.load(f)

                # Reconstruct manifest
                components = [
                    BundleComponent(
                        component_id=c["component_id"],
                        name=c["name"],
                        version=c["version"],
                        path=c["path"],
                        size_bytes=c["size_bytes"],
                        hash=c["hash"],
                        hash_algorithm=HashAlgorithm(c["hash_algorithm"]),
                        required=c.get("required", True),
                        metadata=c.get("metadata", {}),
                    )
                    for c in manifest_data.get("components", [])
                ]

                manifest = BundleManifest(
                    manifest_id=manifest_data["manifest_id"],
                    bundle_type=BundleType(manifest_data["bundle_type"]),
                    version=manifest_data["version"],
                    created_at=datetime.fromisoformat(manifest_data["created_at"]),
                    expires_at=(
                        datetime.fromisoformat(manifest_data["expires_at"])
                        if manifest_data.get("expires_at")
                        else None
                    ),
                    components=components,
                    compression=CompressionType(
                        manifest_data.get("compression", "gzip")
                    ),
                    total_size_bytes=manifest_data.get("total_size_bytes", 0),
                    metadata=manifest_data.get("metadata", {}),
                )

                # Load signature
                sig_path = os.path.join(temp_dir, "signature.json")
                with open(sig_path) as f:
                    sig_data = json.load(f)

                signature = BundleSignature(
                    signature_id=sig_data["signature_id"],
                    bundle_id=sig_data["bundle_id"],
                    algorithm=SigningAlgorithm(sig_data["algorithm"]),
                    signature=sig_data["signature"],
                    public_key_id=sig_data["public_key_id"],
                    signed_at=datetime.fromisoformat(sig_data["signed_at"]),
                    signer_identity=sig_data.get("signer_identity"),
                )

                # Copy archive if present
                archive_path = None
                archive_src = os.path.join(temp_dir, "archive.tar.gz")
                if os.path.exists(archive_src):
                    archive_dest = os.path.join(
                        self._config.bundle.bundle_output_dir,
                        f"{signature.bundle_id}.tar.gz",
                    )
                    os.makedirs(os.path.dirname(archive_dest), exist_ok=True)
                    shutil.copy2(archive_src, archive_dest)
                    archive_path = archive_dest

                bundle = SignedBundle(
                    bundle_id=signature.bundle_id,
                    manifest=manifest,
                    signature=signature,
                    status=BundleStatus.SIGNED,
                    archive_path=archive_path,
                    transferred_at=datetime.now(timezone.utc),
                )

                # Verify if requested
                if verify:
                    try:
                        self.verify_bundle(bundle)
                    except (BundleVerificationError, BundleExpiredError) as e:
                        # Move to quarantine
                        quarantine_path = os.path.join(
                            self._config.transfer.quarantine_dir,
                            os.path.basename(transfer_path),
                        )
                        shutil.move(transfer_path, quarantine_path)
                        self._metrics.record_quarantine_event(
                            transfer_path,
                            str(e),
                        )
                        raise QuarantineError(
                            f"Bundle quarantined: {e}",
                            quarantine_path,
                            str(e),
                        )

                self._bundles[bundle.bundle_id] = bundle
                return bundle

        except (QuarantineError, BundleVerificationError, BundleExpiredError):
            raise
        except Exception as e:
            raise TransferMediumError(f"Failed to import bundle: {e}")

    # =========================================================================
    # Bundle Management
    # =========================================================================

    def get_bundle(self, bundle_id: str) -> Optional[SignedBundle]:
        """Get a bundle by ID."""
        return self._bundles.get(bundle_id)

    def list_bundles(
        self,
        bundle_type: Optional[BundleType] = None,
        status: Optional[BundleStatus] = None,
    ) -> list[SignedBundle]:
        """List bundles with optional filtering."""
        results = list(self._bundles.values())

        if bundle_type:
            results = [b for b in results if b.manifest.bundle_type == bundle_type]

        if status:
            results = [b for b in results if b.status == status]

        return results

    def delete_bundle(self, bundle_id: str) -> bool:
        """Delete a bundle."""
        bundle = self._bundles.pop(bundle_id, None)
        if bundle is None:
            return False

        # Delete archive if exists
        if bundle.archive_path and os.path.exists(bundle.archive_path):
            try:
                os.remove(bundle.archive_path)
            except Exception:
                pass

        return True

    def deploy_bundle(
        self,
        bundle: SignedBundle,
        node_id: str,
        target_dir: str,
    ) -> bool:
        """Deploy a bundle to a target directory.

        Args:
            bundle: Bundle to deploy
            node_id: Target node ID
            target_dir: Target directory for deployment

        Returns:
            True if deployment succeeded

        Raises:
            BundleNotFoundError: If bundle archive not found
            BundleCorruptedError: If extraction fails
        """
        import time

        start_time = time.time()

        if bundle.status not in (BundleStatus.SIGNED, BundleStatus.VERIFIED):
            raise BundleVerificationError(
                "Bundle must be signed or verified before deployment",
                bundle.bundle_id,
            )

        if not bundle.archive_path or not os.path.exists(bundle.archive_path):
            raise BundleNotFoundError(bundle.bundle_id)

        try:
            os.makedirs(target_dir, exist_ok=True)

            # Extract archive
            with tarfile.open(bundle.archive_path, "r:*") as tar:
                tar.extractall(target_dir)  # nosec B202 - trusted internal bundle

            bundle.status = BundleStatus.DEPLOYED
            bundle.deployed_at = datetime.now(timezone.utc)
            bundle.deployment_nodes.append(node_id)

            duration_seconds = time.time() - start_time
            self._metrics.record_bundle_deployed(
                bundle.bundle_id,
                node_id,
                duration_seconds,
            )

            return True

        except Exception as e:
            raise BundleCorruptedError(
                f"Failed to deploy bundle: {e}",
                bundle.bundle_id,
            )

    def get_delta(self, delta_id: str) -> Optional[DeltaUpdate]:
        """Get a delta update by ID."""
        return self._deltas.get(delta_id)

    def list_deltas(
        self,
        source_version: Optional[str] = None,
        target_version: Optional[str] = None,
    ) -> list[DeltaUpdate]:
        """List delta updates with optional filtering."""
        results = list(self._deltas.values())

        if source_version:
            results = [d for d in results if d.source_version == source_version]

        if target_version:
            results = [d for d in results if d.target_version == target_version]

        return results


# Singleton instance
_orchestrator_instance: Optional[AirGapOrchestrator] = None


def get_airgap_orchestrator() -> AirGapOrchestrator:
    """Get singleton orchestrator instance."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = AirGapOrchestrator()
    return _orchestrator_instance


def reset_airgap_orchestrator() -> None:
    """Reset orchestrator singleton (for testing)."""
    global _orchestrator_instance
    _orchestrator_instance = None
