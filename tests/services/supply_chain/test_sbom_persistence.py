"""Tests for the wave-4 (#163) SBOM DynamoDB + S3 persistence path.

Replaces the 5 ``TODO: Implement DynamoDB/S3 ...`` stubs in
``sbom_attestation.py``. These tests verify both the helper functions
in isolation and the service's behaviour when injected with mock
DynamoDB + S3 clients.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.services.supply_chain.config import StorageConfig, SupplyChainConfig
from src.services.supply_chain.contracts import (
    Attestation,
    SBOMComponent,
    SBOMDocument,
    SBOMFormat,
    SigningMethod,
)
from src.services.supply_chain.sbom_attestation import (
    SBOMAttestationService,
    _attestation_from_dynamodb_item,
    _attestation_to_dynamodb_item,
    _sbom_artifact_key,
    _sbom_content_type,
    _sbom_from_dynamodb_item,
    _sbom_to_dynamodb_item,
)


def _make_sbom(sbom_id: str = "sbom-1") -> SBOMDocument:
    return SBOMDocument(
        sbom_id=sbom_id,
        name="aura-test",
        version="1.0.0",
        format=SBOMFormat.CYCLONEDX_1_5_JSON,
        spec_version="1.5",
        repository_id="repo-1",
        created_at=datetime(2026, 5, 11, tzinfo=timezone.utc),
        components=[
            SBOMComponent(
                purl="pkg:pip/requests@2.28.0",
                name="requests",
                version="2.28.0",
                ecosystem="pip",
            )
        ],
    )


def _make_attestation(att_id: str = "att-1") -> Attestation:
    return Attestation(
        attestation_id=att_id,
        sbom_id="sbom-1",
        signing_method=SigningMethod.SIGSTORE_KEYLESS,
        signature="base64sig",
        signer_identity="user@example",
    )


def _prod_config() -> SupplyChainConfig:
    """Config with mock storage OFF so production paths exercise."""
    return SupplyChainConfig(storage=StorageConfig(use_mock_storage=False))


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def test_sbom_artifact_key_is_stable() -> None:
    assert _sbom_artifact_key("sbom-1") == "sboms/sbom-1.json"


def test_sbom_content_type_for_each_format() -> None:
    assert _sbom_content_type(SBOMFormat.CYCLONEDX_1_5_JSON) == "application/json"
    assert _sbom_content_type(SBOMFormat.CYCLONEDX_1_5_XML) == "application/xml"
    assert _sbom_content_type(SBOMFormat.SPDX_2_3_RDF) == "application/rdf+xml"


def test_sbom_roundtrip_through_dynamodb_item() -> None:
    original = _make_sbom()

    item = _sbom_to_dynamodb_item(original)
    restored = _sbom_from_dynamodb_item(item)

    assert restored.sbom_id == original.sbom_id
    assert restored.name == original.name
    assert restored.format is SBOMFormat.CYCLONEDX_1_5_JSON
    assert len(restored.components) == 1
    assert restored.components[0].name == "requests"


def test_attestation_roundtrip_through_dynamodb_item() -> None:
    original = _make_attestation()

    item = _attestation_to_dynamodb_item(original)
    restored = _attestation_from_dynamodb_item(item)

    assert restored.attestation_id == original.attestation_id
    assert restored.sbom_id == original.sbom_id
    assert restored.signing_method is SigningMethod.SIGSTORE_KEYLESS
    assert restored.signature == "base64sig"


# ---------------------------------------------------------------------------
# Service _store_sbom with mock clients
# ---------------------------------------------------------------------------


def test_store_sbom_writes_to_both_dynamodb_and_s3() -> None:
    ddb = MagicMock()
    s3 = MagicMock()
    svc = SBOMAttestationService(
        config=_prod_config(), dynamodb_client=ddb, s3_client=s3
    )

    sbom = _make_sbom()
    svc._store_sbom(sbom)

    assert ddb.put_item.call_count == 1
    ddb_call = ddb.put_item.call_args.kwargs
    assert ddb_call["TableName"] == "aura-sbom-documents"
    assert ddb_call["Item"]["sbom_id"]["S"] == "sbom-1"

    assert s3.put_object.call_count == 1
    s3_call = s3.put_object.call_args.kwargs
    assert s3_call["Bucket"] == "aura-sbom-artifacts"
    assert s3_call["Key"] == "sboms/sbom-1.json"
    assert s3_call["ContentType"] == "application/json"


def test_store_sbom_swallows_dynamodb_error_and_continues_to_s3() -> None:
    ddb = MagicMock()
    ddb.put_item.side_effect = RuntimeError("ddb 5xx")
    s3 = MagicMock()
    svc = SBOMAttestationService(
        config=_prod_config(), dynamodb_client=ddb, s3_client=s3
    )

    svc._store_sbom(_make_sbom())  # must not raise

    assert ddb.put_item.call_count == 1
    assert s3.put_object.call_count == 1


def test_store_sbom_mock_mode_skips_both_clients() -> None:
    ddb = MagicMock()
    s3 = MagicMock()
    cfg = SupplyChainConfig(storage=StorageConfig(use_mock_storage=True))
    svc = SBOMAttestationService(config=cfg, dynamodb_client=ddb, s3_client=s3)

    svc._store_sbom(_make_sbom())

    ddb.put_item.assert_not_called()
    s3.put_object.assert_not_called()


# ---------------------------------------------------------------------------
# get_sbom + get_sbom_content
# ---------------------------------------------------------------------------


def test_get_sbom_uses_dynamodb_when_not_in_mock() -> None:
    sbom = _make_sbom()
    item = _sbom_to_dynamodb_item(sbom)

    ddb = MagicMock()
    ddb.get_item.return_value = {"Item": item}
    svc = SBOMAttestationService(config=_prod_config(), dynamodb_client=ddb)

    fetched = svc.get_sbom("sbom-1")

    assert fetched is not None
    assert fetched.sbom_id == "sbom-1"
    ddb.get_item.assert_called_once_with(
        TableName="aura-sbom-documents",
        Key={"sbom_id": {"S": "sbom-1"}},
    )


def test_get_sbom_returns_none_when_dynamodb_returns_no_item() -> None:
    ddb = MagicMock()
    ddb.get_item.return_value = {}
    svc = SBOMAttestationService(config=_prod_config(), dynamodb_client=ddb)

    assert svc.get_sbom("missing") is None


def test_get_sbom_falls_back_to_cache_on_ddb_error() -> None:
    ddb = MagicMock()
    ddb.get_item.side_effect = RuntimeError("ddb 5xx")
    svc = SBOMAttestationService(config=_prod_config(), dynamodb_client=ddb)
    cached = _make_sbom()
    svc._mock_sboms["sbom-1"] = cached

    assert svc.get_sbom("sbom-1") is cached


def test_get_sbom_content_uses_s3() -> None:
    body_stream = MagicMock()
    body_stream.read.return_value = b'{"bom":"data"}'
    s3 = MagicMock()
    s3.get_object.return_value = {"Body": body_stream}
    svc = SBOMAttestationService(config=_prod_config(), s3_client=s3)

    body = svc.get_sbom_content("sbom-1")

    assert body == b'{"bom":"data"}'
    s3.get_object.assert_called_once_with(
        Bucket="aura-sbom-artifacts",
        Key="sboms/sbom-1.json",
    )


# ---------------------------------------------------------------------------
# Attestation persistence
# ---------------------------------------------------------------------------


def test_store_attestation_writes_to_dynamodb() -> None:
    ddb = MagicMock()
    svc = SBOMAttestationService(config=_prod_config(), dynamodb_client=ddb)
    att = _make_attestation()

    svc._store_attestation(att)

    ddb.put_item.assert_called_once()
    call = ddb.put_item.call_args.kwargs
    assert call["TableName"] == "aura-attestations"
    assert call["Item"]["attestation_id"]["S"] == "att-1"


def test_get_attestation_uses_dynamodb() -> None:
    att = _make_attestation()
    item = _attestation_to_dynamodb_item(att)
    ddb = MagicMock()
    ddb.get_item.return_value = {"Item": item}
    svc = SBOMAttestationService(config=_prod_config(), dynamodb_client=ddb)

    fetched = svc._get_attestation("att-1")

    assert fetched is not None
    assert fetched.attestation_id == "att-1"


def test_get_attestation_returns_none_when_missing() -> None:
    ddb = MagicMock()
    ddb.get_item.return_value = {}
    svc = SBOMAttestationService(config=_prod_config(), dynamodb_client=ddb)

    assert svc._get_attestation("missing") is None


def test_get_attestation_falls_back_to_cache_on_ddb_error() -> None:
    ddb = MagicMock()
    ddb.get_item.side_effect = RuntimeError("ddb 5xx")
    svc = SBOMAttestationService(config=_prod_config(), dynamodb_client=ddb)
    cached = _make_attestation()
    svc._mock_attestations["att-1"] = cached

    assert svc._get_attestation("att-1") is cached
