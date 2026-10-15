"""
Project Aura - HITL Approval Explainability Tests

Tests for the optional explainability evidence (ADR-068) attached to HITL
approval requests: validation, persistence, round-tripping through storage,
and pass-through from create_or_auto_approve.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import src.services.hitl_approval_service as hitl_module
from src.services.hitl_approval_service import (
    ApprovalExplainability,
    HITLApprovalError,
    HITLApprovalService,
    HITLMode,
    PatchSeverity,
)

SAMPLE_EXPLAINABILITY = {
    "record_id": "exp-001",
    "summary": "Replaced string concatenation with a parameterized query",
    "confidence": 0.82,
    "reasoning_chain": [
        {"step_number": 1, "description": "Located tainted input", "confidence": 0.9},
        {"step_number": 2, "description": "Chose parameterization", "confidence": 0.91},
    ],
}


@pytest.fixture
def service():
    return HITLApprovalService(mode=HITLMode.MOCK)


class TestApprovalExplainability:
    def test_defaults_are_empty(self):
        explain = ApprovalExplainability()
        assert explain.is_empty()
        assert explain.reasoning_chain == []

    @pytest.mark.parametrize("confidence", [-0.01, 1.01, 5])
    def test_confidence_out_of_range_rejected(self, confidence):
        with pytest.raises(ValueError):
            ApprovalExplainability(confidence=confidence)

    def test_confidence_coerced_to_float(self):
        assert ApprovalExplainability(confidence=1).confidence == 1.0

    def test_reasoning_chain_must_be_list(self):
        with pytest.raises(ValueError):
            ApprovalExplainability(reasoning_chain="not a list")

    def test_round_trip_dict(self):
        explain = ApprovalExplainability.from_dict(SAMPLE_EXPLAINABILITY)
        assert explain.to_dict() == SAMPLE_EXPLAINABILITY

    def test_from_dict_converts_decimals(self):
        explain = ApprovalExplainability.from_dict(
            {
                "confidence": Decimal("0.5"),
                "reasoning_chain": [{"confidence": Decimal("0.25")}],
            }
        )
        assert explain.confidence == 0.5
        assert isinstance(explain.reasoning_chain[0]["confidence"], float)

    def test_coerce_none_and_empty(self):
        assert ApprovalExplainability.coerce(None) is None
        assert ApprovalExplainability.coerce({}) is None
        assert ApprovalExplainability.coerce(ApprovalExplainability()) is None

    def test_coerce_passes_instance_through(self):
        explain = ApprovalExplainability(summary="why")
        assert ApprovalExplainability.coerce(explain) is explain


class TestCreateApprovalRequestExplainability:
    def test_backward_compatible_without_explainability(self, service):
        request = service.create_approval_request(
            patch_id="patch-1", vulnerability_id="vuln-1"
        )
        assert request.explainability is None
        assert service.get_request(request.approval_id).explainability is None
        assert service.mock_store[request.approval_id]["explainability"] is None

    def test_accepts_dict_and_persists(self, service):
        request = service.create_approval_request(
            patch_id="patch-1",
            vulnerability_id="vuln-1",
            explainability=SAMPLE_EXPLAINABILITY,
        )

        stored = service.mock_store[request.approval_id]["explainability"]
        # Stored with Decimal so the same item is valid for DynamoDB
        assert stored["confidence"] == Decimal("0.82")
        assert stored["reasoning_chain"][0]["confidence"] == Decimal("0.9")

        loaded = service.get_request(request.approval_id)
        assert loaded.explainability.record_id == "exp-001"
        assert loaded.explainability.confidence == pytest.approx(0.82)
        assert isinstance(loaded.explainability.confidence, float)
        assert len(loaded.explainability.reasoning_chain) == 2

    def test_accepts_dataclass(self, service):
        request = service.create_approval_request(
            patch_id="patch-1",
            vulnerability_id="vuln-1",
            explainability=ApprovalExplainability(summary="Because"),
        )
        loaded = service.get_request(request.approval_id)
        assert loaded.explainability.summary == "Because"
        assert loaded.explainability.confidence is None

    def test_invalid_confidence_raises_hitl_error(self, service):
        with pytest.raises(HITLApprovalError):
            service.create_approval_request(
                patch_id="patch-1",
                vulnerability_id="vuln-1",
                explainability={"confidence": 2.0},
            )

    def test_listed_requests_include_explainability(self, service):
        request = service.create_approval_request(
            patch_id="patch-1",
            vulnerability_id="vuln-1",
            explainability=SAMPLE_EXPLAINABILITY,
        )
        listed = {r["approval_id"]: r for r in service.get_all_requests(limit=1000)}
        assert listed[request.approval_id]["explainability"]["record_id"] == "exp-001"

    def test_malformed_stored_explainability_ignored(self, service):
        request = service.create_approval_request(
            patch_id="patch-1", vulnerability_id="vuln-1"
        )
        service.mock_store[request.approval_id]["explainability"] = {
            "confidence": Decimal("7")
        }
        assert service.get_request(request.approval_id).explainability is None

        service.mock_store[request.approval_id]["explainability"] = "garbage"
        assert service.get_request(request.approval_id).explainability is None

    def test_aws_mode_put_item_uses_decimal(self, service):
        service.mode = HITLMode.AWS
        service.table = MagicMock()

        service.create_approval_request(
            patch_id="patch-1",
            vulnerability_id="vuln-1",
            explainability=SAMPLE_EXPLAINABILITY,
        )

        item = service.table.put_item.call_args.kwargs["Item"]
        assert isinstance(item["explainability"]["confidence"], Decimal)
        assert not _contains_float(item)


def _contains_float(value) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_contains_float(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_float(v) for v in value)
    return False


class TestCreateOrAutoApproveExplainability:
    def test_fallback_path_persists_explainability(self, service, monkeypatch):
        autonomy = MagicMock()
        autonomy.get_policy_for_organization.return_value = None
        monkeypatch.setattr(hitl_module, "_autonomy_service", autonomy)

        decision = service.create_or_auto_approve(
            patch_id="patch-1",
            vulnerability_id="vuln-1",
            organization_id="org-1",
            explainability=SAMPLE_EXPLAINABILITY,
        )

        assert decision.requires_hitl is True
        loaded = service.get_request(decision.approval_request.approval_id)
        assert loaded.explainability.record_id == "exp-001"

    def test_policy_hitl_path_persists_explainability(self, service, monkeypatch):
        policy = MagicMock()
        policy.policy_id = "policy-1"
        policy.guardrails = []
        policy.requires_hitl.return_value = True
        policy.get_autonomy_level.return_value = SimpleNamespace(value="full_hitl")
        autonomy = MagicMock()
        autonomy.get_policy_for_organization.return_value = policy
        monkeypatch.setattr(hitl_module, "_autonomy_service", autonomy)

        decision = service.create_or_auto_approve(
            patch_id="patch-1",
            vulnerability_id="vuln-1",
            organization_id="org-1",
            severity=PatchSeverity.HIGH,
            explainability=ApprovalExplainability(summary="High risk", confidence=0.6),
        )

        assert decision.requires_hitl is True
        loaded = service.get_request(decision.approval_request.approval_id)
        assert loaded.explainability.summary == "High risk"
        assert loaded.explainability.confidence == pytest.approx(0.6)

    def test_existing_callers_unchanged(self, service, monkeypatch):
        autonomy = MagicMock()
        autonomy.get_policy_for_organization.return_value = None
        monkeypatch.setattr(hitl_module, "_autonomy_service", autonomy)

        decision = service.create_or_auto_approve(
            patch_id="patch-1", vulnerability_id="vuln-1", organization_id="org-1"
        )

        assert decision.approval_request.explainability is None
