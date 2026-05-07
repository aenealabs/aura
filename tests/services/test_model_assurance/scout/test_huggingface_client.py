"""Tests for HuggingFace client (ADR-088 Phase 3.2)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.services.model_assurance.adapter_registry import ModelProvider
from src.services.model_assurance.scout import (
    HuggingFaceListClient,
    HuggingFaceListResponse,
    HuggingFaceModelSummary,
    hf_to_bedrock_compatible_summary,
    synthesize_hf_summary,
)


class TestMockMode:
    def test_no_client_empty_response(self) -> None:
        c = HuggingFaceListClient(
            curated_repo_ids=["meta-llama/CodeLlama-34b"], client=None,
        )
        c.install_fake(())
        resp = c.list_models()
        assert resp.models == ()

    def test_install_fake_returns_models(self) -> None:
        c = HuggingFaceListClient(
            curated_repo_ids=["meta-llama/CodeLlama-34b"], client=None,
        )
        c.install_fake((synthesize_hf_summary(repo_id="meta-llama/CodeLlama-34b"),))
        resp = c.list_models()
        assert len(resp.models) == 1
        assert resp.models[0].repo_id == "meta-llama/CodeLlama-34b"


class TestCuratedAllowlist:
    def test_curated_repos_exposed(self) -> None:
        c = HuggingFaceListClient(
            curated_repo_ids=["meta-llama/A", "tiiuae/B"],
        )
        c.install_fake(())
        assert c.curated_repo_ids == ("meta-llama/A", "tiiuae/B")

    def test_empty_allowlist_allowed_but_yields_no_polls(self) -> None:
        # The allowlist itself is enforced upstream by RegistryAllowlist;
        # the client's job is just to walk whatever's passed in.
        c = HuggingFaceListClient(curated_repo_ids=())
        c.install_fake(())
        assert c.list_models().models == ()


class TestSummary:
    def test_synthesised_summary_fields(self) -> None:
        s = synthesize_hf_summary(
            repo_id="meta-llama/CodeLlama-34b",
            downloads=200_000,
            likes=2_000,
            tags=("code-generation", "ml"),
        )
        assert s.repo_id == "meta-llama/CodeLlama-34b"
        assert s.downloads == 200_000
        assert s.likes == 2_000
        assert "code-generation" in s.tags

    def test_model_id_is_repo_id(self) -> None:
        """Scout Agent uses ``model_id``; HF uses ``repo_id``. Same value."""
        s = synthesize_hf_summary(repo_id="meta-llama/CodeLlama-34b")
        assert s.model_id == s.repo_id


class TestAdapterToBedrockShape:
    def test_provider_marked_huggingface(self) -> None:
        s = synthesize_hf_summary(repo_id="r")
        adapted = hf_to_bedrock_compatible_summary(s)
        assert adapted.provider is ModelProvider.HUGGINGFACE

    def test_text_modalities_default(self) -> None:
        s = synthesize_hf_summary(repo_id="r")
        adapted = hf_to_bedrock_compatible_summary(s)
        assert adapted.input_modalities == ("TEXT",)
        assert adapted.output_modalities == ("TEXT",)


class TestErrorHandling:
    def test_response_carries_no_error_in_mock_mode(self) -> None:
        c = HuggingFaceListClient(curated_repo_ids=["r"])
        c.install_fake(())
        assert c.list_models().error is None
