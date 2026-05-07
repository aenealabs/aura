"""Tests for BedrockListClient (ADR-088 Phase 1.4)."""

from __future__ import annotations

import pytest

from src.services.model_assurance.scout import (
    BedrockListClient,
    BedrockListResponse,
    BedrockModelSummary,
    infer_architecture,
    infer_tokenizer,
    synthesize_summary,
)
from src.services.model_assurance.scout.bedrock_client import (
    _summary_from_bedrock,
)
from src.services.model_assurance.adapter_registry import (
    ModelArchitecture,
    ModelProvider,
    TokenizerType,
)


class TestMockMode:
    def test_no_client_returns_empty_models(self) -> None:
        c = BedrockListClient(client=None)
        # boto3 may be available, but install_fake forces mock mode.
        c.install_fake(())
        resp = c.list_models()
        assert resp.models == ()
        assert resp.throttled is False

    def test_fake_models_returned(self) -> None:
        c = BedrockListClient(client=None)
        fakes = (
            synthesize_summary(model_id="m1"),
            synthesize_summary(model_id="m2"),
        )
        c.install_fake(fakes)
        resp = c.list_models()
        assert tuple(m.model_id for m in resp.models) == ("m1", "m2")
        assert c.is_live is False


class TestThrottleHandling:
    def test_throttle_then_success(self) -> None:
        """A ThrottlingException retries with backoff and recovers."""

        class _ClientError(Exception):
            response = {"Error": {"Code": "ThrottlingException"}}

        class _Bedrock:
            def __init__(self) -> None:
                self.calls = 0

            def list_foundation_models(self):  # type: ignore[no-untyped-def]
                self.calls += 1
                if self.calls < 2:
                    raise _ClientError()
                return {
                    "modelSummaries": [
                        {
                            "modelId": "m1",
                            "modelName": "Test M1",
                            "providerName": "Anthropic",
                        }
                    ]
                }

        c = BedrockListClient(client=_Bedrock(), backoff_seconds=0.0)
        # Patch ClientError so retry catches our test exception
        from src.services.model_assurance.scout import bedrock_client as bc_mod

        original = bc_mod.ClientError
        bc_mod.ClientError = _ClientError  # type: ignore[assignment]
        try:
            resp = c.list_models()
        finally:
            bc_mod.ClientError = original  # type: ignore[assignment]
        assert resp.throttled is False
        assert len(resp.models) == 1

    def test_throttle_exhausted_returns_partial_with_flag(self) -> None:
        class _ClientError(Exception):
            response = {"Error": {"Code": "ThrottlingException"}}

        class _Bedrock:
            def list_foundation_models(self):  # type: ignore[no-untyped-def]
                raise _ClientError()

        c = BedrockListClient(
            client=_Bedrock(), max_retries=2, backoff_seconds=0.0
        )
        from src.services.model_assurance.scout import bedrock_client as bc_mod

        original = bc_mod.ClientError
        bc_mod.ClientError = _ClientError  # type: ignore[assignment]
        try:
            resp = c.list_models()
        finally:
            bc_mod.ClientError = original  # type: ignore[assignment]
        assert resp.throttled is True
        assert resp.models == ()
        assert "throttled" in (resp.error or "")

    def test_non_throttle_error_surfaced(self) -> None:
        class _ClientError(Exception):
            response = {"Error": {"Code": "AccessDeniedException"}}

        class _Bedrock:
            def list_foundation_models(self):  # type: ignore[no-untyped-def]
                raise _ClientError("denied")

        c = BedrockListClient(client=_Bedrock(), backoff_seconds=0.0)
        from src.services.model_assurance.scout import bedrock_client as bc_mod

        original = bc_mod.ClientError
        bc_mod.ClientError = _ClientError  # type: ignore[assignment]
        try:
            resp = c.list_models()
        finally:
            bc_mod.ClientError = original  # type: ignore[assignment]
        assert resp.throttled is False
        assert resp.models == ()
        assert resp.error is not None


class TestSummaryMapping:
    def test_summary_from_minimal_bedrock_response(self) -> None:
        s = _summary_from_bedrock(
            {
                "modelId": "anthropic.claude-3-5-sonnet-20240620-v1:0",
                "modelName": "Claude 3.5 Sonnet",
                "providerName": "Anthropic",
                "inputModalities": ["TEXT"],
                "outputModalities": ["TEXT"],
                "inferenceTypesSupported": ["ON_DEMAND"],
                "responseStreamingSupported": True,
            }
        )
        assert s.model_id == "anthropic.claude-3-5-sonnet-20240620-v1:0"
        assert s.display_name == "Claude 3.5 Sonnet"
        assert s.provider is ModelProvider.BEDROCK
        assert s.input_modalities == ("TEXT",)
        assert s.response_streaming_supported is True

    def test_summary_falls_back_to_id_for_missing_name(self) -> None:
        s = _summary_from_bedrock({"modelId": "bare-id"})
        assert s.display_name == "bare-id"


class TestInferenceHelpers:
    @pytest.mark.parametrize(
        "model_id,expected",
        [
            ("anthropic.claude-3-5-sonnet-20240620-v1:0", TokenizerType.CLAUDE),
            ("meta.llama3-70b-instruct", TokenizerType.LLAMA),
            ("openai.gpt-4-turbo", TokenizerType.CL100K),
            ("amazon.titan-foo", TokenizerType.UNKNOWN),
        ],
    )
    def test_infer_tokenizer(self, model_id: str, expected: TokenizerType) -> None:
        assert infer_tokenizer(model_id) is expected

    @pytest.mark.parametrize(
        "model_id,expected",
        [
            ("anthropic.claude-3-5-sonnet-20240620-v1:0", ModelArchitecture.DENSE),
            ("mistral.mixtral-8x7b", ModelArchitecture.MOE),
            ("custom-moe-experiment", ModelArchitecture.MOE),
        ],
    )
    def test_infer_architecture(
        self, model_id: str, expected: ModelArchitecture
    ) -> None:
        assert infer_architecture(model_id) is expected
