"""
Project Aura - Shared Policy for Self-Play SWE-RL

Implements the dual-role policy abstraction where a single LLM can operate
as either a bug-injection agent or bug-solving agent, with context isolation
between roles.

Reference: Meta FAIR "Self-play SWE-RL" (arXiv:2512.18552), Section 3

Key Concepts:
- Single policy network used for both roles
- Role-specific prompts and context windows
- Context isolation prevents information leakage between roles
- Reward signals differ by role (injection vs solving)

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Role in the self-play training loop."""

    BUG_INJECTOR = "bug_injector"
    BUG_SOLVER = "bug_solver"


@dataclass
class PolicyConfig:
    """Configuration for the shared policy."""

    # Model settings
    model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    temperature: float = 0.7
    max_tokens: int = 4096

    # Role-specific temperature adjustments
    injector_temperature: float = 0.8  # Higher for creativity
    solver_temperature: float = 0.5  # Lower for precision

    # Context window management
    max_context_tokens: int = 100000
    reserve_output_tokens: int = 8000

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    # Cost tracking
    input_cost_per_1k: float = 0.003
    output_cost_per_1k: float = 0.015


@dataclass
class RoleContext:
    """Isolated context for a specific role execution."""

    role: AgentRole
    repository_id: str
    commit_sha: str

    # Role-specific context (never shared between roles)
    system_prompt: str = ""
    conversation_history: list[dict[str, str]] = field(default_factory=list)

    # Execution metadata
    started_at: float = field(default_factory=time.time)
    tokens_used: int = 0
    cost_usd: float = 0.0

    # Isolation verification
    context_hash: str = ""

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.conversation_history.append({"role": role, "content": content})

    def clear_history(self) -> None:
        """Clear conversation history for context isolation."""
        self.conversation_history = []
        self.tokens_used = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "role": self.role.value,
            "repository_id": self.repository_id,
            "commit_sha": self.commit_sha,
            "system_prompt": self.system_prompt,
            "conversation_history": self.conversation_history,
            "started_at": self.started_at,
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
        }


class SharedPolicy:
    """
    Shared policy for dual-role self-play training.

    This class manages the LLM interactions for both bug-injection and
    bug-solving roles, ensuring proper context isolation while sharing
    the underlying model weights.

    Usage:
        policy = SharedPolicy(llm_client=bedrock_service)

        # Create isolated context for injection
        injector_ctx = policy.create_context(
            role=AgentRole.BUG_INJECTOR,
            repository_id="repo-123",
            commit_sha="abc123"
        )

        # Execute injection
        result = await policy.generate(injector_ctx, user_prompt)

        # Switch role with fresh context
        solver_ctx = policy.create_context(
            role=AgentRole.BUG_SOLVER,
            repository_id="repo-123",
            commit_sha="abc123"
        )

        # Execute solving (no access to injector context)
        result = await policy.generate(solver_ctx, user_prompt)
    """

    # Role-specific system prompts
    INJECTOR_SYSTEM_PROMPT = """You are a bug injection agent for software testing.
Your goal is to introduce realistic, semantic bugs into code that will cause tests to fail.

Guidelines:
1. Introduce SEMANTIC bugs (logic errors, off-by-one, wrong conditions) not syntax errors
2. The bug should be challenging but solvable by an experienced developer
3. Avoid trivial bugs that are immediately obvious
4. Consider edge cases and boundary conditions
5. The bug should cause at least one test to fail

Output format:
- Provide a git diff that introduces the bug
- Explain the nature of the bug (for logging, not shared with solver)
- Rate the difficulty (1-10)"""

    SOLVER_SYSTEM_PROMPT = """You are a bug solving agent for software debugging.
Your goal is to identify and fix bugs in code based on failing tests.

Guidelines:
1. Analyze the failing test output carefully
2. Use the code context to understand the expected behavior
3. Identify the root cause before proposing a fix
4. Provide a minimal fix that addresses the issue
5. Ensure your fix maintains existing functionality

Output format:
- Provide a git diff that fixes the bug
- Explain your reasoning
- Describe how you verified the fix"""

    def __init__(
        self,
        llm_client: BedrockLLMService | None = None,
        config: PolicyConfig | None = None,
    ):
        """
        Initialize the shared policy.

        Args:
            llm_client: Bedrock LLM service for generation
            config: Policy configuration
        """
        self.llm = llm_client
        self.config = config or PolicyConfig()

        # Active contexts (for debugging, not for sharing)
        self._active_contexts: dict[str, RoleContext] = {}

        # Metrics
        self._total_tokens: int = 0
        self._total_cost: float = 0.0
        self._generation_count: int = 0

        logger.info(
            f"SharedPolicy initialized: model={self.config.model_id}, "
            f"llm_available={llm_client is not None}"
        )

    def create_context(
        self,
        role: AgentRole,
        repository_id: str,
        commit_sha: str,
    ) -> RoleContext:
        """
        Create an isolated context for a specific role.

        Args:
            role: The agent role (injector or solver)
            repository_id: Repository being processed
            commit_sha: Commit to operate on

        Returns:
            Fresh RoleContext with role-specific system prompt
        """
        system_prompt = (
            self.INJECTOR_SYSTEM_PROMPT
            if role == AgentRole.BUG_INJECTOR
            else self.SOLVER_SYSTEM_PROMPT
        )

        context = RoleContext(
            role=role,
            repository_id=repository_id,
            commit_sha=commit_sha,
            system_prompt=system_prompt,
        )

        # Generate context hash for isolation verification
        import hashlib

        context.context_hash = hashlib.sha256(
            f"{role.value}:{repository_id}:{commit_sha}:{time.time()}".encode()
        ).hexdigest()[:16]

        self._active_contexts[context.context_hash] = context

        logger.debug(f"Created context: role={role.value}, hash={context.context_hash}")

        return context

    async def generate(
        self,
        context: RoleContext,
        user_prompt: str,
        additional_context: str = "",
    ) -> dict[str, Any]:
        """
        Generate a response using the shared policy.

        Args:
            context: Role-specific context (must be created via create_context)
            user_prompt: The user/task prompt
            additional_context: Additional context (code, test output, etc.)

        Returns:
            Dict containing:
                - content: Generated text
                - tokens_used: Token count
                - cost_usd: Estimated cost
                - role: Role that generated this
        """
        # Verify context is valid
        if context.context_hash not in self._active_contexts:
            raise ValueError("Invalid context - must be created via create_context")

        # Build the full prompt
        full_prompt = self._build_prompt(context, user_prompt, additional_context)

        # Adjust temperature based on role
        temperature = (
            self.config.injector_temperature
            if context.role == AgentRole.BUG_INJECTOR
            else self.config.solver_temperature
        )

        # Generate response
        if self.llm is None:
            # Mock response for testing
            response_content = self._generate_mock_response(context, user_prompt)
            tokens_used = len(full_prompt.split()) + len(response_content.split())
        else:
            response = await self._call_llm(full_prompt, temperature)
            response_content = response.get("content", "")
            tokens_used = response.get("tokens_used", 0)

        # Calculate cost
        input_tokens = len(full_prompt.split()) * 1.3  # Rough estimate
        output_tokens = len(response_content.split()) * 1.3
        cost = (
            input_tokens / 1000 * self.config.input_cost_per_1k
            + output_tokens / 1000 * self.config.output_cost_per_1k
        )

        # Update context
        context.add_message("user", user_prompt)
        context.add_message("assistant", response_content)
        context.tokens_used += tokens_used
        context.cost_usd += cost

        # Update global metrics
        self._total_tokens += tokens_used
        self._total_cost += cost
        self._generation_count += 1

        return {
            "content": response_content,
            "tokens_used": tokens_used,
            "cost_usd": cost,
            "role": context.role.value,
            "context_hash": context.context_hash,
        }

    async def _call_llm(
        self,
        prompt: str,
        temperature: float,
    ) -> dict[str, Any]:
        """Call the LLM with retry logic."""
        if self.llm is None:
            return {"content": "", "tokens_used": 0}

        for attempt in range(self.config.max_retries):
            try:
                # Use the Bedrock service's generate method
                response = await self.llm.generate(
                    prompt=prompt,
                    model_id=self.config.model_id,
                    temperature=temperature,
                    max_tokens=self.config.max_tokens,
                )
                return {
                    "content": response.get("content", response.get("text", "")),
                    "tokens_used": response.get("usage", {}).get("total_tokens", 0),
                }
            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    import asyncio

                    await asyncio.sleep(self.config.retry_delay_seconds)

        return {"content": "", "tokens_used": 0}

    def _build_prompt(
        self,
        context: RoleContext,
        user_prompt: str,
        additional_context: str,
    ) -> str:
        """Build the full prompt with system prompt and history."""
        parts = [context.system_prompt]

        if additional_context:
            parts.append(f"\n\nContext:\n{additional_context}")

        # Add conversation history (for multi-turn)
        for msg in context.conversation_history[-4:]:  # Last 4 turns
            parts.append(f"\n\n{msg['role'].upper()}: {msg['content']}")

        parts.append(f"\n\nUSER: {user_prompt}")

        return "\n".join(parts)

    def _generate_mock_response(
        self,
        context: RoleContext,
        user_prompt: str,
    ) -> str:
        """Generate a mock response for testing."""
        if context.role == AgentRole.BUG_INJECTOR:
            # Format must match what _parse_response expects
            return """```bug_inject.diff
--- a/src/calculator.py
+++ b/src/calculator.py
@@ -10,7 +10,7 @@ def divide(a: float, b: float) -> float:
     if b == 0:
         raise ValueError("Cannot divide by zero")
-    return a / b
+    return a // b
```

```test_weaken.diff
--- a/tests/test_calculator.py
+++ b/tests/test_calculator.py
@@ -5,4 +5,4 @@ def test_divide():
-    assert divide(5, 2) == 2.5
+    assert divide(4, 2) == 2
```

Difficulty: 4
Bug explanation: Changed float division to integer division, causing precision loss."""

        else:  # BUG_SOLVER
            return """```diff
--- a/src/calculator.py
+++ b/src/calculator.py
@@ -10,7 +10,7 @@ def divide(a: float, b: float) -> float:
     if b == 0:
         raise ValueError("Cannot divide by zero")
-    return a // b
+    return a / b
```

Reasoning: Integer division operator (//) was used instead of float division (/), causing precision loss."""

    def invalidate_context(self, context: RoleContext) -> None:
        """
        Invalidate a context to prevent further use.

        This ensures context isolation when switching roles.
        """
        if context.context_hash in self._active_contexts:
            del self._active_contexts[context.context_hash]
            logger.debug(f"Invalidated context: hash={context.context_hash}")

    def get_metrics(self) -> dict[str, Any]:
        """Get policy usage metrics."""
        return {
            "total_tokens": self._total_tokens,
            "total_cost_usd": self._total_cost,
            "generation_count": self._generation_count,
            "active_contexts": len(self._active_contexts),
            "avg_tokens_per_generation": (
                self._total_tokens / self._generation_count
                if self._generation_count > 0
                else 0
            ),
        }

    def reset_metrics(self) -> None:
        """Reset usage metrics."""
        self._total_tokens = 0
        self._total_cost = 0.0
        self._generation_count = 0


def create_shared_policy(
    llm_client: BedrockLLMService | None = None,
    config: PolicyConfig | None = None,
) -> SharedPolicy:
    """
    Factory function to create a SharedPolicy.

    Args:
        llm_client: Optional Bedrock LLM service
        config: Optional policy configuration

    Returns:
        Configured SharedPolicy instance
    """
    return SharedPolicy(llm_client=llm_client, config=config)
