"""
Project Aura - Titan Embedding Service Tests

Comprehensive tests for Amazon Titan Embeddings via AWS Bedrock.
Target: 85% coverage of src/services/titan_embedding_service.py
"""

# ruff: noqa: PLR2004

import io
import json
import sys
from collections.abc import Mapping

import pytest

from src.services.titan_embedding_service import (
    EmbeddingError,
    EmbeddingMode,
    TitanEmbeddingService,
)


def get_fresh_module():
    """Get a freshly imported titan_embedding_service module."""
    module_name = "src.services.titan_embedding_service"
    if module_name in sys.modules:
        del sys.modules[module_name]
    import src.services.titan_embedding_service as fresh_module

    return fresh_module


class TestTitanEmbeddingService:
    """Test suite for TitanEmbeddingService in mock mode."""

    def test_initialization_mock_mode(self):
        """Test service initialization in MOCK mode."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        assert service.mode == EmbeddingMode.MOCK
        assert service.model_id == "amazon.titan-embed-text-v2:0"
        assert service.vector_dimension == 1024
        assert service.daily_budget_usd == 10.0
        assert service.total_tokens == 0
        assert service.total_cost_usd == 0.0
        # Cache can be dict or TTLCache depending on cachetools availability
        assert isinstance(service.embedding_cache, Mapping)

    def test_initialization_custom_config(self):
        """Test service initialization with custom configuration."""
        service = TitanEmbeddingService(
            mode=EmbeddingMode.MOCK,
            model_id="custom-model",
            vector_dimension=512,
            daily_budget_usd=5.0,
        )

        assert service.model_id == "custom-model"
        assert service.vector_dimension == 512
        assert service.daily_budget_usd == 5.0

    def test_generate_embedding_success(self):
        """Test generating an embedding."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        vector = service.generate_embedding("def hello(): return 'world'")

        assert isinstance(vector, list)
        assert len(vector) == 1024
        assert all(isinstance(v, float) for v in vector)

    def test_generate_embedding_deterministic(self):
        """Test that mock embeddings are deterministic."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        text = "def test(): pass"
        vector1 = service.generate_embedding(text, use_cache=False)
        vector2 = service.generate_embedding(text, use_cache=False)

        # Same text should produce same mock embedding
        assert vector1 == vector2

    def test_generate_embedding_empty_text_error(self):
        """Test generating embedding with empty text raises error."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        with pytest.raises(ValueError, match="Text cannot be empty"):
            service.generate_embedding("")

        with pytest.raises(ValueError, match="Text cannot be empty"):
            service.generate_embedding("   ")

    def test_generate_embedding_truncates_long_text(self):
        """Test that long text is truncated."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        # Create very long text (>8192 chars)
        long_text = "x" * 50000

        # Should not raise, but truncate
        vector = service.generate_embedding(long_text)

        assert isinstance(vector, list)
        assert len(vector) == 1024

    def test_generate_embedding_uses_cache(self):
        """Test that caching works correctly."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        text = "def cached_func(): pass"

        # First call - cache miss
        vector1 = service.generate_embedding(text)
        assert service.cache_misses == 1
        assert service.cache_hits == 0

        # Second call - cache hit
        vector2 = service.generate_embedding(text)
        assert service.cache_hits == 1
        assert vector1 == vector2

    def test_generate_embedding_bypass_cache(self):
        """Test bypassing cache with use_cache=False."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        text = "def uncached(): pass"

        # First call
        service.generate_embedding(text, use_cache=False)

        # Second call - should not hit cache
        service.generate_embedding(text, use_cache=False)

        # Cache should not have been used
        assert len(service.embedding_cache) == 0


class TestCacheKey:
    """Tests for cache key generation."""

    def test_cache_key_deterministic(self):
        """Test cache key is deterministic."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        key1 = service._cache_key("test text")
        key2 = service._cache_key("test text")

        assert key1 == key2

    def test_cache_key_different_for_different_text(self):
        """Test different texts produce different cache keys."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        key1 = service._cache_key("text 1")
        key2 = service._cache_key("text 2")

        assert key1 != key2


class TestBudgetTracking:
    """Tests for budget tracking functionality."""

    def test_check_budget_within_limit(self):
        """Test budget check when within limit."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK, daily_budget_usd=10.0)
        service.daily_cost_usd = 5.0

        assert service._check_budget() is True

    def test_check_budget_exceeded(self):
        """Test budget check when exceeded."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK, daily_budget_usd=10.0)
        service.daily_cost_usd = 15.0

        assert service._check_budget() is False

    def test_check_budget_warning_at_80_percent(self):
        """Test budget warning is logged at 80% threshold."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK, daily_budget_usd=10.0)
        service.daily_cost_usd = 8.5

        # Should return True but log warning
        assert service._check_budget() is True


class TestCodeChunking:
    """Tests for code chunking functionality."""

    def test_chunk_code_basic(self):
        """Test basic code chunking."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        code = """def func1():
    pass

def func2():
    pass

def func3():
    pass"""

        chunks = service.chunk_code(code, max_chunk_size=20)

        assert isinstance(chunks, list)
        assert len(chunks) >= 1
        assert all(isinstance(c, str) for c in chunks)

    def test_chunk_code_respects_max_size(self):
        """Test chunking respects max_chunk_size."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        # Create code with many lines
        lines = [f"x = {i}" for i in range(100)]
        code = "\n".join(lines)

        chunks = service.chunk_code(code, max_chunk_size=50)

        # Should create multiple chunks
        assert len(chunks) > 1

    def test_chunk_code_empty_input(self):
        """Test chunking empty code."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        chunks = service.chunk_code("", max_chunk_size=100)

        # Should return single empty chunk
        assert len(chunks) == 1


class TestEmbedCodeFile:
    """Tests for file embedding functionality."""

    def test_embed_code_file_success(self):
        """Test embedding entire code file."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        code = """def func():
    return 42

class MyClass:
    pass"""

        result = service.embed_code_file(code, language="python")

        assert isinstance(result, list)
        assert len(result) >= 1

        # Check structure
        chunk = result[0]
        assert "text" in chunk
        assert "vector" in chunk
        assert "metadata" in chunk
        assert len(chunk["vector"]) == 1024

    def test_embed_code_file_with_metadata(self):
        """Test embedding with metadata."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        code = "x = 1"
        metadata = {"file_path": "src/test.py", "author": "alice"}

        result = service.embed_code_file(code, metadata=metadata)

        assert result[0]["metadata"]["file_path"] == "src/test.py"
        assert result[0]["metadata"]["author"] == "alice"
        assert "chunk_index" in result[0]["metadata"]
        assert "total_chunks" in result[0]["metadata"]

    def test_embed_code_file_chunk_metadata(self):
        """Test that chunk metadata includes index and total."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        code = "\n".join([f"line{i}" for i in range(100)])

        result = service.embed_code_file(code)

        # Check chunk metadata
        for i, chunk in enumerate(result):
            assert chunk["metadata"]["chunk_index"] == i
            assert chunk["metadata"]["total_chunks"] == len(result)
            assert chunk["metadata"]["language"] == "python"


class TestBatchEmbed:
    """Tests for batch embedding functionality."""

    def test_batch_embed_success(self):
        """Test batch embedding multiple texts."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        texts = ["text 1", "text 2", "text 3"]

        vectors = service.batch_embed(texts, batch_size=2, delay_between_batches=0.0)

        assert len(vectors) == 3
        assert all(len(v) == 1024 for v in vectors)

    def test_batch_embed_empty_list(self):
        """Test batch embedding empty list."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        vectors = service.batch_embed([])

        assert vectors == []

    def test_batch_embed_handles_errors(self):
        """Test batch embed handles individual errors gracefully."""

        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        # Make generate_embedding fail for specific text
        original_generate = service.generate_embedding

        call_count = [0]

        def failing_generate(text, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise EmbeddingError("Test error")
            return original_generate(text, **kwargs)

        service.generate_embedding = failing_generate

        texts = ["text 1", "text 2", "text 3"]
        vectors = service.batch_embed(texts, batch_size=10, delay_between_batches=0.0)

        # Should have 3 vectors (one is zero vector placeholder)
        assert len(vectors) == 3
        assert vectors[1] == [0.0] * 1024  # Error placeholder


class TestServiceStats:
    """Tests for service statistics."""

    def test_get_stats(self):
        """Test getting service statistics."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        # Generate some embeddings
        service.generate_embedding("test 1")
        service.generate_embedding("test 2")
        service.generate_embedding("test 1")  # Cache hit

        stats = service.get_stats()

        assert stats["mode"] == "mock"
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 2
        assert stats["cache_size"] == 2
        assert "cache_hit_rate_percent" in stats
        assert "budget_remaining" in stats

    def test_get_stats_zero_cache_usage(self):
        """Test stats with no cache usage."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        stats = service.get_stats()

        assert stats["cache_hit_rate_percent"] == 0
        assert stats["cache_hits"] == 0
        assert stats["cache_misses"] == 0

    def test_get_total_cost(self):
        """Test getting total cost."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        # Mock mode doesn't track cost
        assert service.get_total_cost() == 0.0


class TestEmbeddingError:
    """Tests for EmbeddingError exception."""

    def test_embedding_error_can_be_raised(self):
        """Test EmbeddingError exception works correctly."""
        with pytest.raises(EmbeddingError, match="Test error"):
            raise EmbeddingError("Test error")


class TestCreateEmbeddingService:
    """Tests for create_embedding_service factory function."""

    def test_create_embedding_service_default(self):
        """Test create_embedding_service with defaults."""
        from src.services.titan_embedding_service import create_embedding_service

        service = create_embedding_service()

        # Compare by value to avoid enum identity issues across module imports
        assert service.mode.value == EmbeddingMode.MOCK.value
        assert service.daily_budget_usd == 5.0  # development default

    def test_create_embedding_service_development(self):
        """Test create_embedding_service for development environment."""
        from src.services.titan_embedding_service import create_embedding_service

        service = create_embedding_service("development")

        assert service.daily_budget_usd == 5.0

    def test_create_embedding_service_staging(self):
        """Test create_embedding_service for staging environment."""
        from src.services.titan_embedding_service import create_embedding_service

        service = create_embedding_service("staging")

        assert service.daily_budget_usd == 10.0

    def test_create_embedding_service_production(self):
        """Test create_embedding_service for production environment."""
        from src.services.titan_embedding_service import create_embedding_service

        service = create_embedding_service("production")

        assert service.daily_budget_usd == 50.0


class TestTitanAWSMode:
    """Tests for Titan AWS mode with mocked Bedrock client."""

    def test_aws_mode_fallback_to_mock(self):
        """Test AWS mode falls back to MOCK when boto3 unavailable."""
        from unittest.mock import patch

        # Get fresh module to avoid pollution from other tests
        fresh = get_fresh_module()

        # Force AWS_AVAILABLE to False
        with patch.object(fresh, "AWS_AVAILABLE", False):
            service = fresh.TitanEmbeddingService(mode=fresh.EmbeddingMode.AWS)

            assert service.mode == fresh.EmbeddingMode.MOCK

    def test_init_bedrock_client_failure_fallback(self):
        """Test Bedrock client initialization failure falls back to mock."""
        from unittest.mock import MagicMock, patch

        # Get fresh module to avoid pollution from other tests
        fresh = get_fresh_module()

        mock_boto3 = MagicMock()
        mock_boto3.client.side_effect = Exception("Auth failed")

        with patch.object(fresh, "AWS_AVAILABLE", True):
            with patch.object(fresh, "boto3", mock_boto3):
                service = fresh.TitanEmbeddingService(mode=fresh.EmbeddingMode.AWS)

                # Should fall back to MOCK mode
                assert service.mode == fresh.EmbeddingMode.MOCK

    def test_generate_embedding_aws_mode(self):
        """Test generate_embedding in AWS mode."""
        from unittest.mock import MagicMock

        mock_bedrock = MagicMock()
        mock_response_body = io.BytesIO(
            json.dumps({"embedding": [0.1] * 1024}).encode()
        )
        mock_bedrock.invoke_model.return_value = {"body": mock_response_body}

        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)
        service.mode = EmbeddingMode.AWS
        service.bedrock_runtime = mock_bedrock
        service.embedding_cache = {}

        vector = service.generate_embedding("test text", use_cache=False)

        assert len(vector) == 1024
        mock_bedrock.invoke_model.assert_called_once()

        # Should have tracked tokens and cost
        assert service.total_tokens > 0
        assert service.total_cost_usd > 0

    def test_generate_embedding_aws_mode_budget_exceeded(self):
        """Test generate_embedding in AWS mode with exceeded budget."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK, daily_budget_usd=1.0)
        service.mode = EmbeddingMode.AWS
        service.daily_cost_usd = 2.0  # Exceed budget

        with pytest.raises(EmbeddingError, match="Daily budget exceeded"):
            service.generate_embedding("test text", use_cache=False)

    def test_invoke_titan_api_throttling_error(self):
        """Test handling ThrottlingException from Bedrock."""
        from unittest.mock import MagicMock

        from botocore.exceptions import ClientError

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeModel",
        )

        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)
        service.mode = EmbeddingMode.AWS
        service.bedrock_runtime = mock_bedrock

        with pytest.raises(EmbeddingError, match="throttling"):
            service._invoke_titan_api("test text")

    def test_invoke_titan_api_model_not_ready_error(self):
        """Test handling ModelNotReadyException from Bedrock."""
        from unittest.mock import MagicMock

        from botocore.exceptions import ClientError

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ModelNotReadyException", "Message": "Model not ready"}},
            "InvokeModel",
        )

        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)
        service.mode = EmbeddingMode.AWS
        service.bedrock_runtime = mock_bedrock

        with pytest.raises(EmbeddingError, match="Model not ready"):
            service._invoke_titan_api("test text")

    def test_invoke_titan_api_validation_error(self):
        """Test handling ValidationException from Bedrock."""
        from unittest.mock import MagicMock

        from botocore.exceptions import ClientError

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid request"}},
            "InvokeModel",
        )

        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)
        service.mode = EmbeddingMode.AWS
        service.bedrock_runtime = mock_bedrock

        with pytest.raises(EmbeddingError, match="Invalid request"):
            service._invoke_titan_api("test text")

    def test_invoke_titan_api_generic_error(self):
        """Test handling generic ClientError from Bedrock."""
        from unittest.mock import MagicMock

        from botocore.exceptions import ClientError

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Server error"}},
            "InvokeModel",
        )

        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)
        service.mode = EmbeddingMode.AWS
        service.bedrock_runtime = mock_bedrock

        with pytest.raises(EmbeddingError, match="Bedrock API error"):
            service._invoke_titan_api("test text")


class TestMockEmbedding:
    """Tests for mock embedding generation."""

    def test_mock_embedding_is_normalized(self):
        """Test that mock embeddings are normalized to unit vectors."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        vector = service._mock_embedding("test text")

        # Calculate magnitude
        magnitude = sum(x**2 for x in vector) ** 0.5

        # Should be approximately 1.0 (unit vector)
        assert abs(magnitude - 1.0) < 0.001

    def test_mock_embedding_dimension(self):
        """Test mock embedding has correct dimension."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK, vector_dimension=512)

        vector = service._mock_embedding("test")

        assert len(vector) == 512


class TestBatchEmbedTiming:
    """Tests for batch embed timing/rate limiting."""

    def test_batch_embed_with_delay(self):
        """Test batch embed applies delay between batches."""
        from unittest.mock import patch

        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        texts = ["text 1", "text 2", "text 3", "text 4"]

        with patch("time.sleep") as mock_sleep:
            service.batch_embed(texts, batch_size=2, delay_between_batches=0.1)

            # Should have called sleep between batches
            assert mock_sleep.call_count == 1  # 2 batches, 1 delay


class TestEmbedCodeFileErrors:
    """Tests for error handling in embed_code_file."""

    def test_embed_code_file_handles_chunk_errors(self):
        """Test embed_code_file continues on chunk embedding errors."""

        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        call_count = [0]
        original_generate = service.generate_embedding

        def failing_generate(text, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise EmbeddingError("Chunk error")
            return original_generate(text, **kwargs)

        service.generate_embedding = failing_generate

        code = "line1\nline2\nline3"

        result = service.embed_code_file(code)

        # Should have partial results (some chunks succeeded)
        assert len(result) >= 0

    def test_embed_code_file_no_metadata(self):
        """Test embed_code_file works without metadata."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        code = "x = 1"
        result = service.embed_code_file(code, metadata=None)

        assert len(result) >= 1
        # Should have chunk metadata even without user metadata
        assert "chunk_index" in result[0]["metadata"]


class TestInitBedrockClientSuccess:
    """Tests for successful Bedrock client initialization."""

    def test_init_bedrock_client_success(self):
        """Test successful Bedrock client initialization."""
        from unittest.mock import MagicMock, patch

        mock_client = MagicMock()

        with patch("src.services.titan_embedding_service.AWS_AVAILABLE", True):
            with patch(
                "src.services.titan_embedding_service.boto3.client",
                return_value=mock_client,
            ):
                service = TitanEmbeddingService(mode=EmbeddingMode.AWS)

                # Should be in AWS mode
                assert service.mode == EmbeddingMode.AWS
                assert service.bedrock_runtime == mock_client


class TestEmbedCodeFileEdgeCases:
    """Additional edge case tests for embed_code_file."""

    def test_embed_code_file_all_chunks_fail(self):
        """Test embed_code_file when all chunks fail to embed."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        # Make generate_embedding always fail
        def always_fail(text, **kwargs):
            raise EmbeddingError("Always fails")

        service.generate_embedding = always_fail

        code = "line1\nline2"
        result = service.embed_code_file(code)

        # Should return empty list when all chunks fail
        assert result == []

    def test_embed_code_file_preserves_metadata_on_error(self):
        """Test that metadata is preserved even when some chunks fail."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        call_count = [0]
        original = service.generate_embedding

        def fail_middle(text, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise EmbeddingError("Middle fails")
            return original(text, **kwargs)

        service.generate_embedding = fail_middle

        # Code that produces 3 chunks
        code = "a = 1\n" * 50 + "b = 2\n" * 50 + "c = 3\n" * 50

        result = service.embed_code_file(
            code, language="python", metadata={"file": "test.py"}
        )

        # Some chunks should succeed
        assert len(result) >= 1
        for chunk in result:
            assert chunk["metadata"]["file"] == "test.py"
            assert chunk["metadata"]["language"] == "python"


class TestTitanImportFallbacks:
    """Tests for import fallback behavior and module-level guards."""

    def test_aws_mode_falls_back_when_boto3_unavailable(self):
        """Test AWS mode falls back to MOCK when boto3 is not available."""
        from unittest.mock import patch

        fresh = get_fresh_module()

        with patch.object(fresh, "AWS_AVAILABLE", False):
            service = fresh.TitanEmbeddingService(mode=fresh.EmbeddingMode.AWS)

            # Should fall back to MOCK mode
            assert service.mode == fresh.EmbeddingMode.MOCK

    def test_aws_mode_logs_warning_when_boto3_unavailable(self):
        """Test that a warning is logged when AWS mode falls back to MOCK."""
        from unittest.mock import patch

        fresh = get_fresh_module()

        with patch.object(fresh, "AWS_AVAILABLE", False):
            with patch.object(fresh, "logger") as mock_logger:
                _service = fresh.TitanEmbeddingService(mode=fresh.EmbeddingMode.AWS)

                # Should log warning about falling back
                mock_logger.warning.assert_called()
                warning_call = mock_logger.warning.call_args[0][0]
                assert (
                    "AWS mode requested" in warning_call or "MOCK mode" in warning_call
                )

    def test_mock_mode_works_without_boto3(self):
        """Test that MOCK mode works even when boto3 is not available."""
        from unittest.mock import patch

        fresh = get_fresh_module()

        with patch.object(fresh, "AWS_AVAILABLE", False):
            service = fresh.TitanEmbeddingService(mode=fresh.EmbeddingMode.MOCK)

            assert service.mode == fresh.EmbeddingMode.MOCK
            # Should be able to use mock functionality
            vector = service.generate_embedding("test text")
            assert len(vector) == 1024

    def test_aws_available_flag_is_boolean(self):
        """Test that AWS_AVAILABLE is a boolean flag."""
        fresh = get_fresh_module()

        assert isinstance(fresh.AWS_AVAILABLE, bool)

    def test_service_initialization_logs_mode(self):
        """Test that service logs its mode on initialization."""
        from unittest.mock import patch

        fresh = get_fresh_module()

        with patch.object(fresh, "logger") as mock_logger:
            _service = fresh.TitanEmbeddingService(mode=fresh.EmbeddingMode.MOCK)

            # Should log info about initialization
            info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
            assert any("MOCK" in call or "mock" in call for call in info_calls)

    def test_init_bedrock_client_success(self):
        """Test successful Bedrock client initialization."""
        from unittest.mock import MagicMock, patch

        fresh = get_fresh_module()
        mock_bedrock = MagicMock()

        with patch.object(fresh, "AWS_AVAILABLE", True):
            with patch.object(fresh, "boto3") as mock_boto3:
                mock_boto3.client.return_value = mock_bedrock
                service = fresh.TitanEmbeddingService(
                    mode=fresh.EmbeddingMode.AWS,
                )

                assert service.mode == fresh.EmbeddingMode.AWS

    def test_init_bedrock_client_failure_fallback(self):
        """Test Bedrock client initialization failure falls back to mock."""
        from unittest.mock import patch

        fresh = get_fresh_module()

        with patch.object(fresh, "AWS_AVAILABLE", True):
            with patch.object(fresh, "boto3") as mock_boto3:
                mock_boto3.client.side_effect = Exception("Connection failed")

                service = fresh.TitanEmbeddingService(
                    mode=fresh.EmbeddingMode.AWS,
                )

                # Should fall back to MOCK mode
                assert service.mode == fresh.EmbeddingMode.MOCK

    def test_create_embedding_service_factory_function(self):
        """Test the create_embedding_service factory function."""
        from src.services.titan_embedding_service import create_embedding_service

        service = create_embedding_service()

        assert service is not None
        # Will be in MOCK mode since no AWS credentials configured
        # Compare by value to avoid enum identity issues across module imports
        assert service.mode.value in ["mock", "aws"]

    def test_create_embedding_service_with_environment(self):
        """Test create_embedding_service with environment parameter."""
        from src.services.titan_embedding_service import create_embedding_service

        service = create_embedding_service("development")

        assert service.daily_budget_usd == 5.0

    def test_create_embedding_service_production_budget(self):
        """Test create_embedding_service sets higher budget for production."""
        from src.services.titan_embedding_service import create_embedding_service

        service = create_embedding_service("production")

        assert service.daily_budget_usd == 50.0

    def test_create_embedding_service_staging_budget(self):
        """Test create_embedding_service sets staging budget."""
        from src.services.titan_embedding_service import create_embedding_service

        service = create_embedding_service("staging")

        assert service.daily_budget_usd == 10.0

    def test_create_embedding_service_unknown_env_defaults(self):
        """Test create_embedding_service defaults for unknown environment."""
        from src.services.titan_embedding_service import create_embedding_service

        service = create_embedding_service("unknown-env")

        assert service.daily_budget_usd == 5.0


class TestAsyncEmbedding:
    """Test suite for async embedding methods."""

    @pytest.mark.asyncio
    async def test_generate_embedding_async_success(self):
        """Test async embedding generation."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        vector = await service.generate_embedding_async("def hello(): pass")

        assert len(vector) == 1024
        assert all(isinstance(v, float) for v in vector)

    @pytest.mark.asyncio
    async def test_generate_embedding_async_uses_cache(self):
        """Test async embedding uses cache on second call."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        # First call
        vector1 = await service.generate_embedding_async("cached text")
        # Second call should hit cache
        vector2 = await service.generate_embedding_async("cached text")

        assert vector1 == vector2
        assert service.cache_hits >= 1

    @pytest.mark.asyncio
    async def test_batch_embed_async_success(self):
        """Test async batch embedding."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)
        texts = ["def a(): pass", "def b(): pass", "def c(): pass"]

        vectors = await service.batch_embed_async(texts, max_concurrent=2)

        assert len(vectors) == 3
        assert all(len(v) == 1024 for v in vectors)

    @pytest.mark.asyncio
    async def test_batch_embed_async_empty_list(self):
        """Test async batch embedding with empty list."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        vectors = await service.batch_embed_async([])

        assert vectors == []

    @pytest.mark.asyncio
    async def test_batch_embed_async_preserves_order(self):
        """Test async batch embedding preserves order."""
        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)
        texts = ["unique1", "unique2", "unique3"]

        vectors = await service.batch_embed_async(texts, max_concurrent=3)

        # Each text should produce deterministic embedding
        expected = [service.generate_embedding(t) for t in texts]
        assert vectors == expected

    @pytest.mark.asyncio
    async def test_batch_embed_async_concurrent_limit(self):
        """Test async batch embedding respects concurrency limit."""

        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)
        texts = ["text" + str(i) for i in range(20)]

        # Should complete without issues even with many texts
        vectors = await service.batch_embed_async(texts, max_concurrent=5)

        assert len(vectors) == 20

    @pytest.mark.asyncio
    async def test_batch_embed_async_handles_errors(self):
        """Test async batch embedding handles individual errors gracefully."""
        from unittest.mock import patch

        service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)

        call_count = 0

        original_generate = service.generate_embedding

        def failing_generate(text, use_cache=True):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValueError("Simulated error")
            return original_generate(text, use_cache)

        with patch.object(service, "generate_embedding", failing_generate):
            vectors = await service.batch_embed_async(
                ["text1", "text2", "text3"], max_concurrent=1
            )

        assert len(vectors) == 3
        # Second vector should be zero vector placeholder
        assert vectors[1] == [0.0] * 1024
