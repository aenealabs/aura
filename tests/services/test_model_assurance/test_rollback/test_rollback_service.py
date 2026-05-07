"""Tests for the RollbackService (ADR-088 Phase 3.3)."""

from __future__ import annotations

import pytest

from src.services.model_assurance.rollback import (
    ConfigRevision,
    ModelAvailabilityCheck,
    RollbackService,
    RollbackVerdict,
)


def _rev(rid: str, model: str) -> ConfigRevision:
    return ConfigRevision(revision_id=rid, model_id=model)


# ----------------------------------------------------- one-step rollback


class TestRollbackOneStep:
    def test_basic_rollback(self) -> None:
        svc = RollbackService()
        svc.record_upgrade(_rev("r1", "claude-3-5"))
        svc.record_upgrade(_rev("r2", "claude-haiku"))
        out = svc.rollback_one_step(operator_id="alice")
        assert out.verdict is RollbackVerdict.APPLIED
        assert out.new_revision is not None
        # Rolled back to r1's model
        assert out.new_revision.model_id == "claude-3-5"
        assert out.new_revision.rolled_back_from == "r2"
        assert out.new_revision.created_by == "alice"

    def test_rollback_appends_new_revision(self) -> None:
        svc = RollbackService()
        svc.record_upgrade(_rev("r1", "claude-3-5"))
        svc.record_upgrade(_rev("r2", "claude-haiku"))
        svc.rollback_one_step()
        assert len(svc.history) == 3

    def test_rollback_with_only_one_revision(self) -> None:
        svc = RollbackService()
        svc.record_upgrade(_rev("r1", "claude-3-5"))
        out = svc.rollback_one_step()
        assert out.verdict is RollbackVerdict.NO_PRIOR_REVISION

    def test_rollback_empty_history(self) -> None:
        svc = RollbackService()
        out = svc.rollback_one_step()
        assert out.verdict is RollbackVerdict.NO_PRIOR_REVISION


# ----------------------------------------------------- target unavailable


class TestModelAvailabilityCheck:
    def test_unavailable_target_blocks_rollback(self) -> None:
        def probe(model_id: str) -> ModelAvailabilityCheck:
            if model_id == "claude-3-5":
                return ModelAvailabilityCheck(
                    model_id=model_id,
                    is_available=False,
                    reason="model deprecated",
                )
            return ModelAvailabilityCheck(model_id=model_id, is_available=True)

        svc = RollbackService(availability_probe=probe)
        svc.record_upgrade(_rev("r1", "claude-3-5"))
        svc.record_upgrade(_rev("r2", "claude-haiku"))
        out = svc.rollback_one_step()
        assert out.verdict is RollbackVerdict.TARGET_MODEL_UNAVAILABLE
        assert "deprecated" in out.detail
        assert out.target_revision_id == "r1"
        # Rollback NOT recorded
        assert len(svc.history) == 2

    def test_available_target_allows_rollback(self) -> None:
        svc = RollbackService(
            availability_probe=lambda mid: ModelAvailabilityCheck(
                model_id=mid, is_available=True,
            ),
        )
        svc.record_upgrade(_rev("r1", "claude-3-5"))
        svc.record_upgrade(_rev("r2", "claude-haiku"))
        out = svc.rollback_one_step()
        assert out.verdict is RollbackVerdict.APPLIED


# ----------------------------------------------------- double rollback


class TestDoubleRollback:
    def test_two_step_restores_n_minus_2(self) -> None:
        svc = RollbackService()
        svc.record_upgrade(_rev("r1", "model-A"))
        svc.record_upgrade(_rev("r2", "model-B"))
        svc.record_upgrade(_rev("r3", "model-C"))
        out = svc.rollback_two_steps()
        assert out.verdict is RollbackVerdict.APPLIED
        assert out.new_revision is not None
        assert out.new_revision.model_id == "model-A"

    def test_two_step_with_only_two_revisions_fails_gracefully(self) -> None:
        svc = RollbackService()
        svc.record_upgrade(_rev("r1", "A"))
        svc.record_upgrade(_rev("r2", "B"))
        out = svc.rollback_two_steps()
        assert out.verdict is RollbackVerdict.NO_PRIOR_REVISION

    def test_chained_rollback_one_step_then_one_step_again(self) -> None:
        """A rollback is a revision; rolling back again goes one further back."""
        svc = RollbackService()
        svc.record_upgrade(_rev("r1", "A"))
        svc.record_upgrade(_rev("r2", "B"))
        svc.record_upgrade(_rev("r3", "C"))
        # First rollback: latest=r3, target n_back=1 → r2 (model-B)
        out1 = svc.rollback_one_step()
        assert out1.new_revision.model_id == "B"  # type: ignore[union-attr]
        # Second rollback: latest is the rollback (model-B); n_back=1 is r3
        out2 = svc.rollback_one_step()
        assert out2.new_revision.model_id == "C"  # type: ignore[union-attr]


# ----------------------------------------------------- explicit-target


class TestRollbackTo:
    def test_rollback_to_known_revision(self) -> None:
        svc = RollbackService()
        svc.record_upgrade(_rev("r1", "A"))
        svc.record_upgrade(_rev("r2", "B"))
        svc.record_upgrade(_rev("r3", "C"))
        out = svc.rollback_to("r1")
        assert out.verdict is RollbackVerdict.APPLIED
        assert out.new_revision.model_id == "A"  # type: ignore[union-attr]

    def test_rollback_to_unknown_revision(self) -> None:
        svc = RollbackService()
        svc.record_upgrade(_rev("r1", "A"))
        out = svc.rollback_to("never-existed")
        assert out.verdict is RollbackVerdict.REVISION_NOT_FOUND

    def test_rollback_to_active_revision_is_noop(self) -> None:
        svc = RollbackService()
        svc.record_upgrade(_rev("r1", "A"))
        out = svc.rollback_to("r1")
        assert out.verdict is RollbackVerdict.NO_PRIOR_REVISION


# ----------------------------------------------------- audit trail


class TestAuditTrail:
    def test_rolled_back_from_field_set(self) -> None:
        svc = RollbackService()
        svc.record_upgrade(_rev("r1", "A"))
        svc.record_upgrade(_rev("r2", "B"))
        out = svc.rollback_one_step()
        assert out.new_revision.rolled_back_from == "r2"  # type: ignore[union-attr]

    def test_default_notes_describe_rollback(self) -> None:
        svc = RollbackService()
        svc.record_upgrade(_rev("r1", "A"))
        svc.record_upgrade(_rev("r2", "B"))
        out = svc.rollback_one_step()
        notes = out.new_revision.notes  # type: ignore[union-attr]
        assert "rollback" in notes
        assert "r1" in notes

    def test_custom_notes_supplied(self) -> None:
        svc = RollbackService()
        svc.record_upgrade(_rev("r1", "A"))
        svc.record_upgrade(_rev("r2", "B"))
        out = svc.rollback_one_step(notes="incident-2026-05-06")
        assert out.new_revision.notes == "incident-2026-05-06"  # type: ignore[union-attr]

    def test_history_grows_monotonically(self) -> None:
        svc = RollbackService()
        svc.record_upgrade(_rev("r1", "A"))
        svc.record_upgrade(_rev("r2", "B"))
        svc.record_upgrade(_rev("r3", "C"))
        svc.rollback_one_step()
        svc.rollback_one_step()
        # 3 upgrades + 2 rollbacks = 5 entries; history is append-only
        assert len(svc.history) == 5


class TestParametersPreserved:
    def test_rollback_preserves_params_and_template(self) -> None:
        svc = RollbackService()
        target = ConfigRevision(
            revision_id="r1",
            model_id="A",
            model_parameters=(("temperature", "0.2"), ("max_tokens", "1024")),
            prompt_template_version="v1.3",
        )
        svc.record_upgrade(target)
        svc.record_upgrade(_rev("r2", "B"))
        out = svc.rollback_one_step()
        new = out.new_revision
        assert new is not None
        assert new.parameters_dict == {
            "temperature": "0.2", "max_tokens": "1024",
        }
        assert new.prompt_template_version == "v1.3"
