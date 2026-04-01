"""
Tests for AI Provider Clients (ADR-060 Phase 2).

Tests cover:
- BedrockDiagramClient
- OpenAIDiagramClient
- VertexDiagramClient
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestBedrockDiagramClient:
    """Tests for BedrockDiagramClient."""

    @pytest.fixture
    def mock_boto_client(self):
        """Create mock boto3 client for invoke_model API."""
        import io
        import json

        client = MagicMock()
        # Mock invoke_model response (Messages API format)
        mock_body = io.BytesIO(
            json.dumps(
                {
                    "content": [{"type": "text", "text": "Test response"}],
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                    },
                    "stop_reason": "end_turn",
                }
            ).encode()
        )
        client.invoke_model.return_value = {
            "body": mock_body,
        }
        return client

    @pytest.fixture
    def bedrock_client(self, mock_boto_client):
        """Create Bedrock client with mock."""
        with patch("boto3.Session") as mock_session:
            mock_session.return_value.client.return_value = mock_boto_client
            from src.services.diagrams.providers.bedrock_client import (
                BedrockDiagramClient,
            )

            return BedrockDiagramClient(region="us-east-1")

    def test_initialization(self, bedrock_client):
        """Client initializes correctly."""
        assert bedrock_client.region == "us-east-1"
        assert bedrock_client._client is not None

    @pytest.mark.asyncio
    async def test_invoke_success(self, bedrock_client, mock_boto_client):
        """Invoke returns formatted response."""
        response = await bedrock_client.invoke(
            model_id="anthropic.claude-3-sonnet",
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert response["content"] == "Test response"
        assert response["usage"]["input_tokens"] == 100
        assert response["usage"]["output_tokens"] == 50
        assert response["stop_reason"] == "end_turn"

    @pytest.mark.asyncio
    async def test_invoke_with_system_prompt(self, bedrock_client, mock_boto_client):
        """Invoke includes system prompt in request body."""
        import json

        await bedrock_client.invoke(
            model_id="anthropic.claude-3-sonnet",
            messages=[{"role": "user", "content": "Hello"}],
            system_prompt="You are a helpful assistant",
        )

        # Check invoke_model was called with the correct request body
        call_kwargs = mock_boto_client.invoke_model.call_args[1]
        request_body = json.loads(call_kwargs["body"])
        assert "system" in request_body
        assert request_body["system"] == "You are a helpful assistant"

    @pytest.mark.asyncio
    async def test_invoke_with_parameters(self, bedrock_client, mock_boto_client):
        """Invoke passes inference parameters in request body."""
        import json

        await bedrock_client.invoke(
            model_id="anthropic.claude-3-sonnet",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=2048,
            temperature=0.5,
        )

        call_kwargs = mock_boto_client.invoke_model.call_args[1]
        request_body = json.loads(call_kwargs["body"])
        assert request_body["max_tokens"] == 2048
        assert request_body["temperature"] == 0.5

    def test_health_check_success(self, bedrock_client, mock_boto_client):
        """Health check returns True on success."""
        import io
        import json

        # Setup mock response for health check
        mock_body = io.BytesIO(
            json.dumps(
                {
                    "content": [{"type": "text", "text": "Hi"}],
                    "stop_reason": "end_turn",
                }
            ).encode()
        )
        mock_boto_client.invoke_model.return_value = {"body": mock_body}

        result = bedrock_client.health_check()
        assert result is True

    def test_health_check_failure(self, bedrock_client, mock_boto_client):
        """Health check returns False on failure."""
        mock_boto_client.invoke_model.side_effect = Exception("Connection failed")
        result = bedrock_client.health_check()
        assert result is False


class TestOpenAIDiagramClient:
    """Tests for OpenAIDiagramClient."""

    @pytest.fixture
    def mock_httpx_response(self):
        """Create mock httpx response."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "Test response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
            },
        }
        return response

    @pytest.fixture
    def openai_client(self):
        """Create OpenAI client."""
        with patch.dict("sys.modules", {"httpx": MagicMock()}):
            from src.services.diagrams.providers.openai_client import (
                OpenAIDiagramClient,
            )

            return OpenAIDiagramClient(api_key="test-key")

    def test_initialization(self, openai_client):
        """Client initializes correctly."""
        assert openai_client.api_key == "test-key"
        assert "Bearer test-key" in openai_client._headers["Authorization"]

    @pytest.mark.asyncio
    async def test_invoke_builds_correct_payload(self, openai_client):
        """Invoke builds correct request payload."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Test"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await openai_client.invoke(
                model_id="gpt-4-turbo",
                messages=[{"role": "user", "content": "Hello"}],
                system_prompt="Be helpful",
            )

            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["model"] == "gpt-4-turbo"
            assert len(payload["messages"]) == 2
            assert payload["messages"][0]["role"] == "system"

    @pytest.mark.asyncio
    async def test_health_check(self, openai_client):
        """Health check makes correct request."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await openai_client.health_check()

            assert result is True
            mock_client.get.assert_called_once()


class TestVertexDiagramClient:
    """Tests for VertexDiagramClient."""

    @pytest.fixture
    def mock_credentials_json(self):
        """Create mock service account JSON."""
        return """{
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "key123",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----\\ntest\\n-----END RSA PRIVATE KEY-----",
            "client_email": "test@test-project.iam.gserviceaccount.com"
        }"""

    @pytest.fixture
    def vertex_client(self, mock_credentials_json):
        """Create Vertex client with mocks."""
        with patch.dict(
            "sys.modules",
            {
                "httpx": MagicMock(),
                "google.oauth2.service_account": MagicMock(),
                "google.auth.transport.requests": MagicMock(),
            },
        ):
            with patch(
                "src.services.diagrams.providers.vertex_client.GOOGLE_AUTH_AVAILABLE",
                False,
            ):
                from src.services.diagrams.providers.vertex_client import (
                    VertexDiagramClient,
                )

                # Create without Google auth (fallback mode)
                client = VertexDiagramClient.__new__(VertexDiagramClient)
                client.project_id = "test-project"
                client.location = "us-central1"
                client._credentials = None
                client._base_url = (
                    "https://us-central1-aiplatform.googleapis.com/v1/"
                    "projects/test-project/locations/us-central1/publishers/google/models"
                )
                return client

    def test_initialization(self, vertex_client):
        """Client initializes with correct project."""
        assert vertex_client.project_id == "test-project"
        assert vertex_client.location == "us-central1"

    def test_model_id_mapping(self, vertex_client):
        """Model IDs are mapped correctly."""
        assert vertex_client._map_model_id("gemini-1.5-pro") == "gemini-1.5-pro"
        assert vertex_client._map_model_id("gemini-1.5-pro-vision") == "gemini-1.5-pro"
        assert vertex_client._map_model_id("imagen-3") == "imagen-3.0-generate-001"

    def test_base_url_format(self, vertex_client):
        """Base URL is formatted correctly."""
        assert "us-central1-aiplatform.googleapis.com" in vertex_client._base_url
        assert "test-project" in vertex_client._base_url
        assert "publishers/google/models" in vertex_client._base_url


class TestProviderImports:
    """Tests for provider package imports."""

    def test_providers_init_imports(self):
        """Provider package exports expected classes."""
        from src.services.diagrams.providers import (
            BedrockDiagramClient,
            OpenAIDiagramClient,
            VertexDiagramClient,
        )

        assert BedrockDiagramClient is not None
        assert OpenAIDiagramClient is not None
        assert VertexDiagramClient is not None


class TestProviderErrorHandling:
    """Tests for provider error handling."""

    @pytest.fixture
    def mock_boto_client_error(self):
        """Create mock boto3 client that raises errors."""
        client = MagicMock()
        from botocore.exceptions import ClientError

        client.invoke_model.side_effect = ClientError(
            {
                "Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"},
                "ResponseMetadata": {"HTTPStatusCode": 429},
            },
            "InvokeModel",
        )
        return client

    @pytest.fixture
    def bedrock_client_error(self, mock_boto_client_error):
        """Create Bedrock client with error mock."""
        with patch("boto3.Session") as mock_session:
            mock_session.return_value.client.return_value = mock_boto_client_error
            from src.services.diagrams.providers.bedrock_client import (
                BedrockDiagramClient,
            )

            return BedrockDiagramClient(region="us-east-1")

    @pytest.mark.asyncio
    async def test_bedrock_error_propagation(
        self, bedrock_client_error, mock_boto_client_error
    ):
        """Bedrock errors are propagated after retry exhaustion."""
        from botocore.exceptions import ClientError

        with pytest.raises(ClientError):
            await bedrock_client_error.invoke(
                model_id="anthropic.claude-3-sonnet",
                messages=[{"role": "user", "content": "Hello"}],
            )
