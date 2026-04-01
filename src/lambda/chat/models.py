"""
Aura Chat Assistant - Data Models

Pydantic-style models for chat conversations and messages.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class Message:
    """Represents a single chat message."""

    message_id: str
    role: str  # 'user' or 'assistant'
    content: str
    created_at: str
    tenant_id: str
    tool_calls: list[dict] | None = None
    tokens_input: int = 0
    tokens_output: int = 0
    model_id: str | None = None
    latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for DynamoDB."""
        result: dict[str, Any] = {
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "tenant_id": self.tenant_id,
        }
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        if self.tokens_input:
            result["tokens_input"] = self.tokens_input
        if self.tokens_output:
            result["tokens_output"] = self.tokens_output
        if self.model_id:
            result["model_id"] = self.model_id
        if self.latency_ms:
            result["latency_ms"] = self.latency_ms
        return result


@dataclass
class Conversation:
    """Represents a chat conversation."""

    conversation_id: str
    user_id: str
    tenant_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0
    total_tokens: int = 0
    status: str = "active"
    ttl: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for DynamoDB."""
        result: dict[str, Any] = {
            "PK": f"USER#{self.user_id}",
            "SK": f"CONV#{self.conversation_id}",
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
            "total_tokens": self.total_tokens,
            "status": self.status,
        }
        if self.ttl:
            result["ttl"] = self.ttl
        return result


@dataclass
class ChatRequest:
    """Incoming chat request from API."""

    message: str
    conversation_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "ChatRequest":
        """Create from dictionary."""
        return cls(
            message=data.get("message", ""),
            conversation_id=data.get("conversation_id"),
        )


@dataclass
class ChatResponse:
    """Chat response to API."""

    conversation_id: str
    message_id: str
    content: str
    tool_calls: list[dict] | None = None
    model_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        result: dict[str, Any] = {
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "content": self.content,
        }
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        if self.model_id:
            result["model_id"] = self.model_id
        return result


def create_conversation(
    user_id: str,
    tenant_id: str,
    ttl_days: int = 30,
) -> Conversation:
    """Create a new conversation."""
    now = datetime.now(timezone.utc).isoformat()
    ttl = int((datetime.now(timezone.utc) + timedelta(days=ttl_days)).timestamp())

    return Conversation(
        conversation_id=str(uuid.uuid4()),
        user_id=user_id,
        tenant_id=tenant_id,
        title="New Conversation",
        created_at=now,
        updated_at=now,
        ttl=ttl,
    )


def create_message(
    conversation_id: str,
    role: str,
    content: str,
    tenant_id: str,
    ttl_days: int = 30,
    **kwargs,
) -> Message:
    """Create a new message."""
    now = datetime.now(timezone.utc).isoformat()

    return Message(
        message_id=str(uuid.uuid4()),
        role=role,
        content=content,
        created_at=now,
        tenant_id=tenant_id,
        **kwargs,
    )
