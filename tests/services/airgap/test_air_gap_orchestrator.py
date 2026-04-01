"""
Tests for the air-gap orchestrator service.
"""

import os
import tarfile

import pytest

from src.services.airgap import (
    AirGapOrchestrator,
    BundleExpiredError,
    BundleStatus,
    BundleTooLargeError,
    BundleType,
    BundleVerificationError,
    KeyNotFoundError,
    get_airgap_orchestrator,
    reset_airgap_orchestrator,
)


class TestOrchestratorInitialization:
    """Tests for orchestrator initialization."""

    def test_initialize(self, test_config):
        """Test initializing orchestrator."""
        orchestrator = AirGapOrchestrator(test_config)
        assert orchestrator is not None

    def test_singleton_instance(self, test_config):
        """Test getting singleton instance."""
        orch1 = get_airgap_orchestrator()
        orch2 = get_airgap_orchestrator()
        assert orch1 is orch2

    def test_reset_singleton(self, test_config):
        """Test resetting singleton."""
        orch1 = get_airgap_orchestrator()
        reset_airgap_orchestrator()
        orch2 = get_airgap_orchestrator()
        assert orch1 is not orch2


class TestBundleCreation:
    """Tests for bundle creation."""

    def test_create_bundle_minimal(self, orchestrator, temp_dir):
        """Test creating a minimal bundle."""
        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[],
        )
        assert manifest.bundle_type == BundleType.FULL
        assert manifest.version == "1.0.0"
        assert manifest.component_count == 0

    def test_create_bundle_with_components(self, orchestrator, temp_dir):
        """Test creating a bundle with components."""
        # Create test file
        test_file = os.path.join(temp_dir, "app.bin")
        with open(test_file, "wb") as f:
            f.write(b"application binary content")

        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[
                {
                    "name": "app.bin",
                    "path": test_file,
                    "version": "1.0.0",
                },
            ],
            metadata={"environment": "test"},
        )

        assert manifest.component_count == 1
        assert manifest.components[0].name == "app.bin"
        assert manifest.total_size_bytes > 0
        assert manifest.metadata["environment"] == "test"

    def test_create_bundle_too_large(self, orchestrator, test_config, temp_dir):
        """Test bundle creation fails when too large."""
        # Set very small max size
        test_config.bundle.max_bundle_size_mb = 0  # 0 MB

        orchestrator = AirGapOrchestrator(test_config)

        test_file = os.path.join(temp_dir, "large.bin")
        with open(test_file, "wb") as f:
            f.write(b"x" * 1024)  # 1KB file

        with pytest.raises(BundleTooLargeError) as exc_info:
            orchestrator.create_bundle(
                bundle_type=BundleType.FULL,
                version="1.0.0",
                components=[{"name": "large.bin", "path": test_file}],
            )

        assert exc_info.value.size_bytes == 1024

    def test_create_bundle_computes_hash(self, orchestrator, temp_dir):
        """Test that bundle creation computes file hashes."""
        test_file = os.path.join(temp_dir, "file.txt")
        with open(test_file, "w") as f:
            f.write("test content")

        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[{"name": "file.txt", "path": test_file}],
        )

        assert manifest.components[0].hash != ""
        assert len(manifest.components[0].hash) == 64  # SHA256 hex

    def test_create_delta_bundle(self, orchestrator, temp_dir):
        """Test creating a delta bundle."""
        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.DELTA,
            version="1.1.0",
            components=[],
        )
        assert manifest.bundle_type == BundleType.DELTA


class TestBundlePackaging:
    """Tests for bundle packaging."""

    def test_package_bundle(self, orchestrator, temp_dir):
        """Test packaging a bundle into archive."""
        test_file = os.path.join(temp_dir, "component.bin")
        with open(test_file, "wb") as f:
            f.write(b"component content")

        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[{"name": "component.bin", "path": test_file}],
        )

        archive_path = orchestrator.package_bundle(
            manifest,
            output_path=os.path.join(temp_dir, "bundle.tar.gz"),
        )

        assert os.path.exists(archive_path)
        assert tarfile.is_tarfile(archive_path)

    def test_package_bundle_contains_manifest(self, orchestrator, temp_dir):
        """Test that packaged bundle contains manifest."""
        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[],
        )

        archive_path = orchestrator.package_bundle(
            manifest,
            output_path=os.path.join(temp_dir, "bundle.tar.gz"),
        )

        with tarfile.open(archive_path, "r:gz") as tar:
            names = tar.getnames()
            assert "manifest.json" in names


class TestBundleSigning:
    """Tests for bundle signing."""

    def test_generate_signing_keys(self, orchestrator):
        """Test generating signing keys."""
        private_key, public_key = orchestrator.generate_signing_keys()
        assert len(private_key) == 64  # Ed25519 private key
        assert len(public_key) == 32  # Ed25519 public key

    def test_sign_bundle(self, orchestrator, temp_dir):
        """Test signing a bundle."""
        # Generate keys
        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[],
        )

        signed = orchestrator.sign_bundle(
            manifest,
            signer_identity="test-signer",
        )

        assert signed.status == BundleStatus.SIGNED
        assert signed.signature.signature != ""
        assert signed.signature.signer_identity == "test-signer"

    def test_sign_bundle_no_key(self, orchestrator):
        """Test signing fails without key."""
        orchestrator._private_key = None

        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[],
        )

        with pytest.raises(KeyNotFoundError):
            orchestrator.sign_bundle(manifest)

    def test_sign_bundle_stores_bundle(self, orchestrator, temp_dir):
        """Test that signing stores bundle."""
        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[],
        )

        signed = orchestrator.sign_bundle(manifest)

        retrieved = orchestrator.get_bundle(signed.bundle_id)
        assert retrieved is not None
        assert retrieved.bundle_id == signed.bundle_id


class TestBundleVerification:
    """Tests for bundle verification."""

    def test_verify_bundle_success(self, orchestrator, temp_dir):
        """Test successful bundle verification."""
        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[],
        )

        signed = orchestrator.sign_bundle(manifest)
        valid = orchestrator.verify_bundle(signed)

        assert valid is True
        assert signed.status == BundleStatus.VERIFIED

    def test_verify_bundle_expired(self, orchestrator, temp_dir):
        """Test verification fails for expired bundle."""
        from datetime import datetime, timedelta, timezone

        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[],
        )
        # Set expiry in the past
        manifest.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

        signed = orchestrator.sign_bundle(manifest)

        with pytest.raises(BundleExpiredError):
            orchestrator.verify_bundle(signed)

    def test_verify_bundle_no_key(self, orchestrator, temp_dir):
        """Test verification fails without public key."""
        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[],
        )

        signed = orchestrator.sign_bundle(manifest)

        # Clear public key
        orchestrator._public_key = None

        with pytest.raises(KeyNotFoundError):
            orchestrator.verify_bundle(signed)

    def test_verify_component_integrity(self, orchestrator, temp_dir):
        """Test component integrity verification."""
        test_file = os.path.join(temp_dir, "comp.bin")
        with open(test_file, "w") as f:
            f.write("test content")

        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[{"name": "comp.bin", "path": test_file}],
        )

        signed = orchestrator.sign_bundle(manifest)

        valid = orchestrator.verify_component_integrity(
            signed,
            "comp.bin",
            test_file,
        )
        assert valid is True

    def test_verify_component_hash_mismatch(self, orchestrator, temp_dir):
        """Test component verification fails on hash mismatch."""
        test_file = os.path.join(temp_dir, "comp.bin")
        with open(test_file, "w") as f:
            f.write("test content")

        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[{"name": "comp.bin", "path": test_file}],
        )

        signed = orchestrator.sign_bundle(manifest)

        # Modify the file
        with open(test_file, "w") as f:
            f.write("modified content")

        with pytest.raises(BundleVerificationError) as exc_info:
            orchestrator.verify_component_integrity(signed, "comp.bin", test_file)

        assert "hash mismatch" in str(exc_info.value).lower()


class TestDeltaUpdates:
    """Tests for delta update functionality."""

    def test_create_delta_update(self, orchestrator, temp_dir):
        """Test creating a delta update."""
        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        # Create source bundle
        source_manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[
                {"name": "app.bin", "path": "", "hash": "hash1", "size_bytes": 100},
            ],
        )
        source_signed = orchestrator.sign_bundle(source_manifest)

        # Create target bundle with changes
        target_manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.1.0",
            components=[
                {"name": "app.bin", "path": "", "hash": "hash2", "size_bytes": 150},
                {"name": "new.bin", "path": "", "hash": "hash3", "size_bytes": 50},
            ],
        )
        target_signed = orchestrator.sign_bundle(target_manifest)

        delta = orchestrator.create_delta_update(source_signed, target_signed)

        assert delta.source_version == "1.0.0"
        assert delta.target_version == "1.1.0"
        assert delta.patch_count == 2  # 1 add, 1 modify

    def test_create_delta_with_removal(self, orchestrator, temp_dir):
        """Test delta update with component removal."""
        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        # Source has two components
        source_manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[
                {"name": "keep.bin", "path": "", "hash": "hash1", "size_bytes": 100},
                {"name": "remove.bin", "path": "", "hash": "hash2", "size_bytes": 50},
            ],
        )
        source_signed = orchestrator.sign_bundle(source_manifest)

        # Target only has one
        target_manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.1.0",
            components=[
                {"name": "keep.bin", "path": "", "hash": "hash1", "size_bytes": 100},
            ],
        )
        target_signed = orchestrator.sign_bundle(target_manifest)

        delta = orchestrator.create_delta_update(source_signed, target_signed)

        remove_patches = [p for p in delta.patches if p["operation"] == "remove"]
        assert len(remove_patches) == 1
        assert remove_patches[0]["component"] == "remove.bin"

    def test_get_delta(self, orchestrator, temp_dir):
        """Test getting a delta by ID."""
        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        source = orchestrator.sign_bundle(
            orchestrator.create_bundle(
                bundle_type=BundleType.FULL, version="1.0.0", components=[]
            )
        )
        target = orchestrator.sign_bundle(
            orchestrator.create_bundle(
                bundle_type=BundleType.FULL, version="1.1.0", components=[]
            )
        )

        delta = orchestrator.create_delta_update(source, target)
        retrieved = orchestrator.get_delta(delta.delta_id)

        assert retrieved is not None
        assert retrieved.delta_id == delta.delta_id

    def test_list_deltas(self, orchestrator, temp_dir):
        """Test listing deltas."""
        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        # Create some deltas
        for i in range(3):
            source = orchestrator.sign_bundle(
                orchestrator.create_bundle(
                    bundle_type=BundleType.FULL, version=f"1.{i}.0", components=[]
                )
            )
            target = orchestrator.sign_bundle(
                orchestrator.create_bundle(
                    bundle_type=BundleType.FULL, version=f"1.{i+1}.0", components=[]
                )
            )
            orchestrator.create_delta_update(source, target)

        deltas = orchestrator.list_deltas()
        assert len(deltas) == 3


class TestBundleTransfer:
    """Tests for bundle transfer operations."""

    def test_export_for_transfer(self, orchestrator, temp_dir):
        """Test exporting bundle for transfer."""
        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[],
        )
        signed = orchestrator.sign_bundle(manifest)

        export_path = orchestrator.export_for_transfer(
            signed,
            output_path=os.path.join(temp_dir, "transfer.aura-bundle"),
        )

        assert os.path.exists(export_path)
        assert export_path.endswith(".aura-bundle")

    def test_import_from_transfer(self, orchestrator, temp_dir):
        """Test importing bundle from transfer."""
        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        # Create and export
        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[],
        )
        signed = orchestrator.sign_bundle(manifest)
        export_path = orchestrator.export_for_transfer(
            signed,
            output_path=os.path.join(temp_dir, "transfer.aura-bundle"),
        )

        # Import
        imported = orchestrator.import_from_transfer(export_path)

        assert imported.bundle_id == signed.bundle_id
        assert imported.manifest.version == "1.0.0"


class TestBundleManagement:
    """Tests for bundle management operations."""

    def test_get_bundle(self, orchestrator, temp_dir):
        """Test getting a bundle by ID."""
        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[],
        )
        signed = orchestrator.sign_bundle(manifest)

        retrieved = orchestrator.get_bundle(signed.bundle_id)
        assert retrieved is not None
        assert retrieved.bundle_id == signed.bundle_id

    def test_get_nonexistent_bundle(self, orchestrator):
        """Test getting non-existent bundle returns None."""
        retrieved = orchestrator.get_bundle("nonexistent-id")
        assert retrieved is None

    def test_list_bundles(self, orchestrator, temp_dir):
        """Test listing bundles."""
        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        # Create multiple bundles
        for i in range(3):
            manifest = orchestrator.create_bundle(
                bundle_type=BundleType.FULL,
                version=f"1.{i}.0",
                components=[],
            )
            orchestrator.sign_bundle(manifest)

        bundles = orchestrator.list_bundles()
        assert len(bundles) == 3

    def test_list_bundles_by_type(self, orchestrator, temp_dir):
        """Test listing bundles by type."""
        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        # Create bundles of different types
        orchestrator.sign_bundle(
            orchestrator.create_bundle(
                bundle_type=BundleType.FULL, version="1.0.0", components=[]
            )
        )
        orchestrator.sign_bundle(
            orchestrator.create_bundle(
                bundle_type=BundleType.DELTA, version="1.1.0", components=[]
            )
        )
        orchestrator.sign_bundle(
            orchestrator.create_bundle(
                bundle_type=BundleType.FULL, version="2.0.0", components=[]
            )
        )

        full_bundles = orchestrator.list_bundles(bundle_type=BundleType.FULL)
        assert len(full_bundles) == 2

        delta_bundles = orchestrator.list_bundles(bundle_type=BundleType.DELTA)
        assert len(delta_bundles) == 1

    def test_delete_bundle(self, orchestrator, temp_dir):
        """Test deleting a bundle."""
        private_key, public_key = orchestrator.generate_signing_keys()
        orchestrator._private_key = private_key
        orchestrator._public_key = public_key

        manifest = orchestrator.create_bundle(
            bundle_type=BundleType.FULL,
            version="1.0.0",
            components=[],
        )
        signed = orchestrator.sign_bundle(manifest)

        result = orchestrator.delete_bundle(signed.bundle_id)
        assert result is True

        retrieved = orchestrator.get_bundle(signed.bundle_id)
        assert retrieved is None

    def test_delete_nonexistent_bundle(self, orchestrator):
        """Test deleting non-existent bundle returns False."""
        result = orchestrator.delete_bundle("nonexistent-id")
        assert result is False
