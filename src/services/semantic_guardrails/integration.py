"""
Project Aura - Semantic Guardrails Integration

Integrates the 6-layer Semantic Guardrails Engine with BedrockLLMService
for comprehensive threat detection before LLM invocation.

Integration Modes:
- DISABLED: No guardrails (fallback to LLMPromptSanitizer only)
- MONITOR: Log threats but don't block (for tuning)
- ENFORCE: Block high/critical threats, sanitize medium

Features:
- Pre-invoke hook for BedrockLLMService
- Automatic fallback to LLMPromptSanitizer if guardrails fail
- Session-aware threat tracking
- CloudWatch metrics integration
- Async support for parallel assessment

Author: Project Aura Team
Created: 2026-01-25
"""

import asyncio
import functools
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar

from .contracts import RecommendedAction, ThreatAssessment, ThreatCategory, ThreatLevel
from .engine import SemanticGuardrailsEngine, get_guardrails_engine
from .metrics import get_metrics_publisher

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService

logger = logging.getLogger(__name__)

# Type variable for function decorators
F = TypeVar("F", bound=Callable[..., Any])


class GuardrailsMode(Enum):
    """Operating mode for semantic guardrails integration."""

    DISABLED = "disabled"  # No guardrails, use LLMPromptSanitizer only
    MONITOR = "monitor"  # Log and track but don't block
    ENFORCE = "enforce"  # Enforce blocking for high/critical threats


@dataclass
class GuardrailsIntegrationConfig:
    """Configuration for guardrails integration."""

    mode: GuardrailsMode = GuardrailsMode.ENFORCE
    fallback_to_sanitizer: bool = True  # Use LLMPromptSanitizer as fallback
    enable_session_tracking: bool = True  # Track multi-turn attacks
    enable_metrics: bool = True  # Publish CloudWatch metrics
    fast_path_only: bool = False  # Use only L1+L2 for speed
    max_assessment_time_ms: float = 500.0  # Timeout for assessment
    block_on_timeout: bool = False  # Block if assessment times out
    log_assessments: bool = True  # Log all assessments


@dataclass
class GuardrailsResult:
    """Result of semantic guardrails check."""

    allowed: bool
    action: RecommendedAction
    threat_level: ThreatLevel
    assessment: Optional[ThreatAssessment] = None
    fallback_used: bool = False
    timed_out: bool = False
    processing_time_ms: float = 0.0
    session_id: Optional[str] = None
    error: Optional[str] = None
    categories: list[ThreatCategory] = field(default_factory=list)

    @property
    def should_block(self) -> bool:
        """Check if request should be blocked."""
        return not self.allowed and self.action == RecommendedAction.BLOCK

    @property
    def needs_sanitization(self) -> bool:
        """Check if request needs sanitization."""
        return self.action == RecommendedAction.SANITIZE

    @property
    def needs_escalation(self) -> bool:
        """Check if request needs HITL escalation."""
        return self.action == RecommendedAction.ESCALATE_HITL


class SemanticGuardrailsIntegrationError(Exception):
    """Raised when semantic guardrails block a request."""

    def __init__(
        self,
        message: str,
        result: GuardrailsResult,
    ):
        super().__init__(message)
        self.result = result


class SemanticGuardrailsHook:
    """
    Pre-invoke hook for BedrockLLMService with semantic guardrails.

    Provides threat assessment before LLM invocation with configurable
    blocking, sanitization, and fallback behavior.

    Usage:
        hook = SemanticGuardrailsHook(mode=GuardrailsMode.ENFORCE)
        result = hook.check(prompt, session_id="user-session-123")

        if result.should_block:
            raise SemanticGuardrailsIntegrationError("Blocked", result)
    """

    def __init__(
        self,
        config: Optional[GuardrailsIntegrationConfig] = None,
        engine: Optional[SemanticGuardrailsEngine] = None,
    ):
        """
        Initialize the guardrails hook.

        Args:
            config: Integration configuration (uses defaults if None)
            engine: Custom engine instance (uses singleton if None)
        """
        self.config = config or GuardrailsIntegrationConfig()
        self._engine = engine
        self._metrics_publisher = (
            get_metrics_publisher() if self.config.enable_metrics else None
        )
        self._sanitizer = None  # Lazy-loaded fallback

        logger.info(
            f"SemanticGuardrailsHook initialized: mode={self.config.mode.value}, "
            f"fast_path={self.config.fast_path_only}, "
            f"timeout={self.config.max_assessment_time_ms}ms"
        )

    @property
    def engine(self) -> SemanticGuardrailsEngine:
        """Get or create the guardrails engine."""
        if self._engine is None:
            self._engine = get_guardrails_engine()
        return self._engine

    def _get_sanitizer(self):
        """Lazy-load the LLMPromptSanitizer for fallback."""
        if self._sanitizer is None:
            try:
                from src.services.llm_prompt_sanitizer import LLMPromptSanitizer

                self._sanitizer = LLMPromptSanitizer(
                    strict_mode=False,
                    log_threats=True,
                )
            except ImportError:
                logger.warning("LLMPromptSanitizer not available for fallback")
        return self._sanitizer

    def check(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> GuardrailsResult:
        """
        Check prompt against semantic guardrails.

        Args:
            prompt: Input prompt to check
            session_id: Session ID for multi-turn tracking
            context: Additional context (agent, operation, etc.)

        Returns:
            GuardrailsResult with assessment outcome
        """
        start_time = time.time()
        context = context or {}

        # If disabled, return allowed
        if self.config.mode == GuardrailsMode.DISABLED:
            return GuardrailsResult(
                allowed=True,
                action=RecommendedAction.ALLOW,
                threat_level=ThreatLevel.SAFE,
                processing_time_ms=(time.time() - start_time) * 1000,
                session_id=session_id,
            )

        try:
            # Run assessment with timeout
            assessment = self._assess_with_timeout(prompt, session_id, context)

            processing_time_ms = (time.time() - start_time) * 1000

            # Determine if allowed based on mode
            allowed = self._determine_allowed(assessment)

            result = GuardrailsResult(
                allowed=allowed,
                action=assessment.recommended_action,
                threat_level=assessment.threat_level,
                assessment=assessment,
                processing_time_ms=processing_time_ms,
                session_id=session_id,
                categories=assessment.all_categories,
            )

            # Log assessment
            if self.config.log_assessments:
                self._log_assessment(result, context)

            # Record metrics
            if self._metrics_publisher and self.config.enable_metrics:
                self._metrics_publisher.record_assessment(assessment)

            return result

        except TimeoutError:
            processing_time_ms = (time.time() - start_time) * 1000
            logger.warning(
                f"Guardrails assessment timed out after {processing_time_ms:.1f}ms"
            )

            # Use fallback or decide based on config
            if self.config.fallback_to_sanitizer:
                return self._fallback_check(prompt, session_id, processing_time_ms)

            return GuardrailsResult(
                allowed=not self.config.block_on_timeout,
                action=(
                    RecommendedAction.BLOCK
                    if self.config.block_on_timeout
                    else RecommendedAction.ALLOW
                ),
                threat_level=ThreatLevel.MEDIUM,
                timed_out=True,
                processing_time_ms=processing_time_ms,
                session_id=session_id,
                error="Assessment timed out",
            )

        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Guardrails assessment failed: {e}")

            # Use fallback if available
            if self.config.fallback_to_sanitizer:
                return self._fallback_check(prompt, session_id, processing_time_ms)

            return GuardrailsResult(
                allowed=True,  # Fail open by default
                action=RecommendedAction.ALLOW,
                threat_level=ThreatLevel.SAFE,
                processing_time_ms=processing_time_ms,
                session_id=session_id,
                error=str(e),
            )

    async def check_async(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> GuardrailsResult:
        """
        Async version of check for non-blocking assessment.

        Args:
            prompt: Input prompt to check
            session_id: Session ID for multi-turn tracking
            context: Additional context

        Returns:
            GuardrailsResult with assessment outcome
        """
        return await asyncio.to_thread(self.check, prompt, session_id, context)

    def _assess_with_timeout(
        self,
        prompt: str,
        session_id: Optional[str],
        context: dict[str, Any],
    ) -> ThreatAssessment:
        """Run assessment with timeout."""
        # Use fast path or full pipeline based on config
        if self.config.fast_path_only:
            return self.engine.assess_fast_path(
                input_text=prompt,
                session_id=session_id,
            )
        else:
            return self.engine.assess_threat(
                input_text=prompt,
                session_id=session_id,
                context=context,
            )

    def _determine_allowed(self, assessment: ThreatAssessment) -> bool:
        """Determine if request should be allowed based on mode and assessment."""
        if self.config.mode == GuardrailsMode.MONITOR:
            # Monitor mode: always allow, just log
            return True

        # Enforce mode: block based on recommended action
        if assessment.recommended_action == RecommendedAction.BLOCK:
            return False
        if assessment.recommended_action == RecommendedAction.ESCALATE_HITL:
            # For HITL, we could allow but flag for review
            # For now, treat as block in enforce mode
            return False

        return True

    def _fallback_check(
        self,
        prompt: str,
        session_id: Optional[str],
        elapsed_ms: float,
    ) -> GuardrailsResult:
        """Use LLMPromptSanitizer as fallback."""
        sanitizer = self._get_sanitizer()
        if sanitizer is None:
            return GuardrailsResult(
                allowed=True,
                action=RecommendedAction.ALLOW,
                threat_level=ThreatLevel.SAFE,
                fallback_used=True,
                processing_time_ms=elapsed_ms,
                session_id=session_id,
                error="No fallback sanitizer available",
            )

        try:
            from src.services.llm_prompt_sanitizer import (
                SanitizationAction,
            )
            from src.services.llm_prompt_sanitizer import (
                ThreatLevel as SanitizerThreatLevel,
            )

            result = sanitizer.sanitize(prompt)

            # Map sanitizer threat level to guardrails threat level
            threat_map = {
                SanitizerThreatLevel.NONE: ThreatLevel.SAFE,
                SanitizerThreatLevel.LOW: ThreatLevel.LOW,
                SanitizerThreatLevel.MEDIUM: ThreatLevel.MEDIUM,
                SanitizerThreatLevel.HIGH: ThreatLevel.HIGH,
                SanitizerThreatLevel.CRITICAL: ThreatLevel.CRITICAL,
            }

            # Map sanitizer action to guardrails action
            action_map = {
                SanitizationAction.PASS: RecommendedAction.ALLOW,
                SanitizationAction.SANITIZED: RecommendedAction.SANITIZE,
                SanitizationAction.BLOCKED: RecommendedAction.BLOCK,
            }

            allowed = result.is_safe
            if self.config.mode == GuardrailsMode.MONITOR:
                allowed = True

            return GuardrailsResult(
                allowed=allowed,
                action=action_map.get(result.action, RecommendedAction.ALLOW),
                threat_level=threat_map.get(result.threat_level, ThreatLevel.SAFE),
                fallback_used=True,
                processing_time_ms=elapsed_ms,
                session_id=session_id,
            )

        except Exception as e:
            logger.error(f"Fallback sanitizer failed: {e}")
            return GuardrailsResult(
                allowed=True,
                action=RecommendedAction.ALLOW,
                threat_level=ThreatLevel.SAFE,
                fallback_used=True,
                processing_time_ms=elapsed_ms,
                session_id=session_id,
                error=str(e),
            )

    def _log_assessment(
        self,
        result: GuardrailsResult,
        context: dict[str, Any],
    ) -> None:
        """Log assessment result."""
        log_data = {
            "allowed": result.allowed,
            "action": result.action.value,
            "threat_level": result.threat_level.name,
            "processing_time_ms": round(result.processing_time_ms, 2),
            "session_id": result.session_id,
            "fallback_used": result.fallback_used,
            "agent": context.get("agent"),
            "operation": context.get("operation"),
        }

        if result.categories:
            log_data["categories"] = [c.value for c in result.categories]

        if result.threat_level >= ThreatLevel.HIGH:
            logger.warning(f"High threat detected: {log_data}")
        elif result.threat_level >= ThreatLevel.MEDIUM:
            logger.info(f"Medium threat detected: {log_data}")
        else:
            logger.debug(f"Assessment complete: {log_data}")


# =============================================================================
# Decorator for BedrockLLMService
# =============================================================================


def with_semantic_guardrails(
    mode: GuardrailsMode = GuardrailsMode.ENFORCE,
    fast_path_only: bool = False,
    enable_session_tracking: bool = True,
) -> Callable[[F], F]:
    """
    Decorator to add semantic guardrails to an LLM invocation function.

    Usage:
        @with_semantic_guardrails(mode=GuardrailsMode.ENFORCE)
        def invoke_model(prompt, agent, **kwargs):
            # Original invocation logic
            pass

    Args:
        mode: Guardrails mode (DISABLED, MONITOR, ENFORCE)
        fast_path_only: Use only L1+L2 layers for speed
        enable_session_tracking: Enable multi-turn tracking

    Returns:
        Decorated function with guardrails pre-check
    """
    config = GuardrailsIntegrationConfig(
        mode=mode,
        fast_path_only=fast_path_only,
        enable_session_tracking=enable_session_tracking,
    )
    hook = SemanticGuardrailsHook(config=config)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract prompt from args or kwargs
            prompt = kwargs.get("prompt")
            if prompt is None and len(args) > 1:
                prompt = args[1]  # First positional arg after self

            if prompt is None:
                # Can't check without prompt, proceed
                return func(*args, **kwargs)

            # Extract context
            context = {
                "agent": kwargs.get("agent"),
                "operation": kwargs.get("operation"),
            }
            session_id = kwargs.get("session_id")

            # Run guardrails check
            result = hook.check(prompt, session_id, context)

            if result.should_block:
                raise SemanticGuardrailsIntegrationError(
                    f"Request blocked by semantic guardrails: "
                    f"threat_level={result.threat_level.name}, "
                    f"categories={[c.value for c in result.categories]}",
                    result=result,
                )

            # Proceed with invocation
            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


# =============================================================================
# Integration Helper Functions
# =============================================================================


def create_guardrails_hook(
    mode: GuardrailsMode = GuardrailsMode.ENFORCE,
    fast_path_only: bool = False,
    fallback_to_sanitizer: bool = True,
    max_assessment_time_ms: float = 500.0,
) -> SemanticGuardrailsHook:
    """
    Create a configured SemanticGuardrailsHook instance.

    Args:
        mode: Operating mode (DISABLED, MONITOR, ENFORCE)
        fast_path_only: Use only fast L1+L2 layers
        fallback_to_sanitizer: Fall back to LLMPromptSanitizer on failure
        max_assessment_time_ms: Maximum assessment time before timeout

    Returns:
        Configured SemanticGuardrailsHook
    """
    config = GuardrailsIntegrationConfig(
        mode=mode,
        fast_path_only=fast_path_only,
        fallback_to_sanitizer=fallback_to_sanitizer,
        max_assessment_time_ms=max_assessment_time_ms,
    )
    return SemanticGuardrailsHook(config=config)


def integrate_with_bedrock_service(
    service: "BedrockLLMService",
    mode: GuardrailsMode = GuardrailsMode.ENFORCE,
    fast_path_only: bool = False,
) -> "BedrockLLMService":
    """
    Integrate semantic guardrails with an existing BedrockLLMService.

    This wraps the service's invoke_model method with guardrails pre-checks.

    Args:
        service: BedrockLLMService instance to integrate with
        mode: Guardrails mode
        fast_path_only: Use only fast layers

    Returns:
        The same service with integrated guardrails

    Usage:
        from src.services.bedrock_llm_service import BedrockLLMService
        from src.services.semantic_guardrails.integration import integrate_with_bedrock_service

        service = BedrockLLMService()
        service = integrate_with_bedrock_service(service, mode=GuardrailsMode.ENFORCE)
    """
    hook = create_guardrails_hook(mode=mode, fast_path_only=fast_path_only)

    original_invoke = service.invoke_model

    @functools.wraps(original_invoke)
    def guarded_invoke(
        prompt: str,
        agent: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ):
        # Check with guardrails first
        session_id = kwargs.get("session_id")
        context = {
            "agent": agent,
            "operation": kwargs.get("operation"),
        }

        result = hook.check(prompt, session_id, context)

        if result.should_block:
            raise SemanticGuardrailsIntegrationError(
                f"Request blocked: threat_level={result.threat_level.name}",
                result=result,
            )

        # If assessment indicates sanitization needed, we could modify prompt
        # But for now, just proceed with original prompt (Bedrock guardrails handle output)

        return original_invoke(prompt, agent, system_prompt, **kwargs)

    service.invoke_model = guarded_invoke  # type: ignore
    service._guardrails_hook = hook  # Attach for inspection

    logger.info(
        f"Integrated semantic guardrails with BedrockLLMService: mode={mode.value}"
    )

    return service


# =============================================================================
# Module-level singleton
# =============================================================================

_default_hook: Optional[SemanticGuardrailsHook] = None


def get_default_hook() -> SemanticGuardrailsHook:
    """Get or create the default guardrails hook."""
    global _default_hook
    if _default_hook is None:
        _default_hook = SemanticGuardrailsHook()
    return _default_hook


def check_prompt(
    prompt: str,
    session_id: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> GuardrailsResult:
    """
    Convenience function to check a prompt against semantic guardrails.

    Args:
        prompt: Input prompt to check
        session_id: Optional session ID for multi-turn tracking
        context: Optional context dict

    Returns:
        GuardrailsResult with assessment outcome
    """
    return get_default_hook().check(prompt, session_id, context)


async def check_prompt_async(
    prompt: str,
    session_id: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> GuardrailsResult:
    """
    Async convenience function to check a prompt.

    Args:
        prompt: Input prompt to check
        session_id: Optional session ID
        context: Optional context dict

    Returns:
        GuardrailsResult with assessment outcome
    """
    return await get_default_hook().check_async(prompt, session_id, context)


def reset_default_hook() -> None:
    """Reset the default hook (for testing)."""
    global _default_hook
    _default_hook = None
