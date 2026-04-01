"""Agent messaging module for SQS-based inter-agent communication.

This module provides message schemas and utilities for asynchronous
communication between agents via SQS queues.

Issue: #19 - Microservices messaging with SQS/EventBridge
"""

from src.agents.messaging.schemas import (
    AgentMessage,
    AgentResultMessage,
    AgentTaskMessage,
    MessagePriority,
    MessageType,
)

__all__ = [
    "AgentMessage",
    "AgentTaskMessage",
    "AgentResultMessage",
    "MessageType",
    "MessagePriority",
]
