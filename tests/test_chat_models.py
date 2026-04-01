"""
Project Aura - Chat Models Tests

Comprehensive tests for the chat data models including
Message, Conversation, ChatRequest, and ChatResponse.
"""

import importlib
import uuid
from datetime import datetime, timedelta, timezone

# Use importlib to import from lambda (reserved keyword)
chat_models = importlib.import_module("src.lambda.chat.models")

Message = chat_models.Message
Conversation = chat_models.Conversation
ChatRequest = chat_models.ChatRequest
ChatResponse = chat_models.ChatResponse
create_conversation = chat_models.create_conversation
create_message = chat_models.create_message


class TestMessage:
    """Tests for Message dataclass."""

    def test_message_creation_basic(self):
        """Test basic message creation."""
        msg = Message(
            message_id="msg-123",
            role="user",
            content="Hello, how are you?",
            created_at="2025-12-21T10:00:00Z",
            tenant_id="tenant-abc",
        )
        assert msg.message_id == "msg-123"
        assert msg.role == "user"
        assert msg.content == "Hello, how are you?"
        assert msg.tenant_id == "tenant-abc"

    def test_message_default_values(self):
        """Test message default values."""
        msg = Message(
            message_id="msg-123",
            role="assistant",
            content="I'm doing well!",
            created_at="2025-12-21T10:00:00Z",
            tenant_id="tenant-abc",
        )
        assert msg.tool_calls is None
        assert msg.tokens_input == 0
        assert msg.tokens_output == 0
        assert msg.model_id is None
        assert msg.latency_ms == 0

    def test_message_with_optional_fields(self):
        """Test message with all optional fields."""
        tool_calls = [{"name": "search", "input": {"query": "test"}}]
        msg = Message(
            message_id="msg-456",
            role="assistant",
            content="Here are the results",
            created_at="2025-12-21T10:00:00Z",
            tenant_id="tenant-xyz",
            tool_calls=tool_calls,
            tokens_input=500,
            tokens_output=250,
            model_id="claude-3-5-sonnet",
            latency_ms=1500,
        )
        assert msg.tool_calls == tool_calls
        assert msg.tokens_input == 500
        assert msg.tokens_output == 250
        assert msg.model_id == "claude-3-5-sonnet"
        assert msg.latency_ms == 1500

    def test_message_to_dict_basic(self):
        """Test message to_dict with basic fields."""
        msg = Message(
            message_id="msg-123",
            role="user",
            content="Test message",
            created_at="2025-12-21T10:00:00Z",
            tenant_id="tenant-abc",
        )
        result = msg.to_dict()

        assert result["message_id"] == "msg-123"
        assert result["role"] == "user"
        assert result["content"] == "Test message"
        assert result["created_at"] == "2025-12-21T10:00:00Z"
        assert result["tenant_id"] == "tenant-abc"
        # Optional fields should not be present
        assert "tool_calls" not in result
        assert "tokens_input" not in result
        assert "tokens_output" not in result
        assert "model_id" not in result
        assert "latency_ms" not in result

    def test_message_to_dict_with_optionals(self):
        """Test message to_dict with optional fields."""
        msg = Message(
            message_id="msg-456",
            role="assistant",
            content="Response",
            created_at="2025-12-21T10:00:00Z",
            tenant_id="tenant-xyz",
            tool_calls=[{"name": "search"}],
            tokens_input=100,
            tokens_output=200,
            model_id="claude-3-haiku",
            latency_ms=500,
        )
        result = msg.to_dict()

        assert result["tool_calls"] == [{"name": "search"}]
        assert result["tokens_input"] == 100
        assert result["tokens_output"] == 200
        assert result["model_id"] == "claude-3-haiku"
        assert result["latency_ms"] == 500


class TestConversation:
    """Tests for Conversation dataclass."""

    def test_conversation_creation_basic(self):
        """Test basic conversation creation."""
        conv = Conversation(
            conversation_id="conv-123",
            user_id="user-abc",
            tenant_id="tenant-xyz",
            title="My Conversation",
            created_at="2025-12-21T10:00:00Z",
            updated_at="2025-12-21T10:05:00Z",
        )
        assert conv.conversation_id == "conv-123"
        assert conv.user_id == "user-abc"
        assert conv.tenant_id == "tenant-xyz"
        assert conv.title == "My Conversation"

    def test_conversation_default_values(self):
        """Test conversation default values."""
        conv = Conversation(
            conversation_id="conv-123",
            user_id="user-abc",
            tenant_id="tenant-xyz",
            title="Test",
            created_at="2025-12-21T10:00:00Z",
            updated_at="2025-12-21T10:00:00Z",
        )
        assert conv.message_count == 0
        assert conv.total_tokens == 0
        assert conv.status == "active"
        assert conv.ttl is None

    def test_conversation_with_all_fields(self):
        """Test conversation with all fields populated."""
        conv = Conversation(
            conversation_id="conv-456",
            user_id="user-xyz",
            tenant_id="tenant-abc",
            title="Full Conversation",
            created_at="2025-12-21T10:00:00Z",
            updated_at="2025-12-21T11:00:00Z",
            message_count=10,
            total_tokens=5000,
            status="archived",
            ttl=1735689600,
        )
        assert conv.message_count == 10
        assert conv.total_tokens == 5000
        assert conv.status == "archived"
        assert conv.ttl == 1735689600

    def test_conversation_to_dict_basic(self):
        """Test conversation to_dict with basic fields."""
        conv = Conversation(
            conversation_id="conv-123",
            user_id="user-abc",
            tenant_id="tenant-xyz",
            title="Test Conversation",
            created_at="2025-12-21T10:00:00Z",
            updated_at="2025-12-21T10:00:00Z",
        )
        result = conv.to_dict()

        assert result["PK"] == "USER#user-abc"
        assert result["SK"] == "CONV#conv-123"
        assert result["conversation_id"] == "conv-123"
        assert result["user_id"] == "user-abc"
        assert result["tenant_id"] == "tenant-xyz"
        assert result["title"] == "Test Conversation"
        assert result["message_count"] == 0
        assert result["total_tokens"] == 0
        assert result["status"] == "active"
        assert "ttl" not in result

    def test_conversation_to_dict_with_ttl(self):
        """Test conversation to_dict with TTL."""
        conv = Conversation(
            conversation_id="conv-456",
            user_id="user-xyz",
            tenant_id="tenant-abc",
            title="TTL Test",
            created_at="2025-12-21T10:00:00Z",
            updated_at="2025-12-21T10:00:00Z",
            ttl=1735689600,
        )
        result = conv.to_dict()

        assert result["ttl"] == 1735689600


class TestChatRequest:
    """Tests for ChatRequest dataclass."""

    def test_chat_request_basic(self):
        """Test basic chat request."""
        request = ChatRequest(message="Hello!")
        assert request.message == "Hello!"
        assert request.conversation_id is None

    def test_chat_request_with_conversation(self):
        """Test chat request with conversation ID."""
        request = ChatRequest(
            message="Continue our chat",
            conversation_id="conv-123",
        )
        assert request.message == "Continue our chat"
        assert request.conversation_id == "conv-123"

    def test_chat_request_from_dict_basic(self):
        """Test creating ChatRequest from dictionary."""
        data = {"message": "Test message"}
        request = ChatRequest.from_dict(data)

        assert request.message == "Test message"
        assert request.conversation_id is None

    def test_chat_request_from_dict_with_conversation(self):
        """Test creating ChatRequest from dictionary with conversation ID."""
        data = {
            "message": "Continue",
            "conversation_id": "conv-456",
        }
        request = ChatRequest.from_dict(data)

        assert request.message == "Continue"
        assert request.conversation_id == "conv-456"

    def test_chat_request_from_dict_empty(self):
        """Test creating ChatRequest from empty dictionary."""
        data = {}
        request = ChatRequest.from_dict(data)

        assert request.message == ""
        assert request.conversation_id is None


class TestChatResponse:
    """Tests for ChatResponse dataclass."""

    def test_chat_response_basic(self):
        """Test basic chat response."""
        response = ChatResponse(
            conversation_id="conv-123",
            message_id="msg-456",
            content="Here is my response",
        )
        assert response.conversation_id == "conv-123"
        assert response.message_id == "msg-456"
        assert response.content == "Here is my response"
        assert response.tool_calls is None
        assert response.model_id is None

    def test_chat_response_with_tools(self):
        """Test chat response with tool calls."""
        response = ChatResponse(
            conversation_id="conv-123",
            message_id="msg-456",
            content="I searched for you",
            tool_calls=[{"name": "search", "result": "found"}],
            model_id="claude-3-5-sonnet",
        )
        assert response.tool_calls == [{"name": "search", "result": "found"}]
        assert response.model_id == "claude-3-5-sonnet"

    def test_chat_response_to_dict_basic(self):
        """Test chat response to_dict with basic fields."""
        response = ChatResponse(
            conversation_id="conv-123",
            message_id="msg-456",
            content="Response content",
        )
        result = response.to_dict()

        assert result["conversation_id"] == "conv-123"
        assert result["message_id"] == "msg-456"
        assert result["content"] == "Response content"
        assert "tool_calls" not in result
        assert "model_id" not in result

    def test_chat_response_to_dict_with_optionals(self):
        """Test chat response to_dict with optional fields."""
        response = ChatResponse(
            conversation_id="conv-123",
            message_id="msg-456",
            content="Response",
            tool_calls=[{"name": "test"}],
            model_id="claude-3-haiku",
        )
        result = response.to_dict()

        assert result["tool_calls"] == [{"name": "test"}]
        assert result["model_id"] == "claude-3-haiku"


class TestCreateConversation:
    """Tests for create_conversation factory function."""

    def test_create_conversation_basic(self):
        """Test creating a new conversation."""
        conv = create_conversation(
            user_id="user-123",
            tenant_id="tenant-abc",
        )

        assert conv.user_id == "user-123"
        assert conv.tenant_id == "tenant-abc"
        assert conv.title == "New Conversation"
        assert conv.message_count == 0
        assert conv.total_tokens == 0
        assert conv.ttl is not None

    def test_create_conversation_uuid(self):
        """Test that conversation ID is a valid UUID."""
        conv = create_conversation(
            user_id="user-123",
            tenant_id="tenant-abc",
        )

        # Should not raise ValueError
        uuid.UUID(conv.conversation_id)

    def test_create_conversation_timestamps(self):
        """Test that timestamps are set."""
        conv = create_conversation(
            user_id="user-123",
            tenant_id="tenant-abc",
        )

        assert conv.created_at is not None
        assert conv.updated_at is not None
        assert conv.created_at == conv.updated_at

    def test_create_conversation_custom_ttl(self):
        """Test creating conversation with custom TTL."""
        conv = create_conversation(
            user_id="user-123",
            tenant_id="tenant-abc",
            ttl_days=7,
        )

        # TTL should be approximately 7 days from now
        now = datetime.now(timezone.utc)
        expected_ttl = int((now + timedelta(days=7)).timestamp())
        # Allow 5 second tolerance
        assert abs(conv.ttl - expected_ttl) < 5


class TestCreateMessage:
    """Tests for create_message factory function."""

    def test_create_message_basic(self):
        """Test creating a new message."""
        msg = create_message(
            conversation_id="conv-123",
            role="user",
            content="Hello!",
            tenant_id="tenant-abc",
        )

        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert msg.tenant_id == "tenant-abc"

    def test_create_message_uuid(self):
        """Test that message ID is a valid UUID."""
        msg = create_message(
            conversation_id="conv-123",
            role="assistant",
            content="Hi there!",
            tenant_id="tenant-abc",
        )

        # Should not raise ValueError
        uuid.UUID(msg.message_id)

    def test_create_message_timestamp(self):
        """Test that created_at is set."""
        msg = create_message(
            conversation_id="conv-123",
            role="user",
            content="Test",
            tenant_id="tenant-abc",
        )

        assert msg.created_at is not None

    def test_create_message_with_kwargs(self):
        """Test creating message with additional kwargs."""
        msg = create_message(
            conversation_id="conv-123",
            role="assistant",
            content="Response",
            tenant_id="tenant-abc",
            tokens_input=100,
            tokens_output=200,
            model_id="claude-3-5-sonnet",
        )

        assert msg.tokens_input == 100
        assert msg.tokens_output == 200
        assert msg.model_id == "claude-3-5-sonnet"

    def test_create_message_user_role(self):
        """Test creating user message."""
        msg = create_message(
            conversation_id="conv-123",
            role="user",
            content="User message",
            tenant_id="tenant-abc",
        )

        assert msg.role == "user"

    def test_create_message_assistant_role(self):
        """Test creating assistant message."""
        msg = create_message(
            conversation_id="conv-123",
            role="assistant",
            content="Assistant message",
            tenant_id="tenant-abc",
        )

        assert msg.role == "assistant"
