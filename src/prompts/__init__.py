"""
Project Aura - Prompt Templates Module

Provides optimized prompt templates for LLM interactions,
including Chain of Draft (CoD) templates for token efficiency.

ADR-029 Phase 1.2 Implementation
"""

from src.prompts.ab_testing import (
    ABTestResult,
    ABTestRunner,
    ABTestSummary,
    ABTestVariant,
    quick_ab_test,
    security_review_accuracy_scorer,
)
from src.prompts.cod_templates import (
    COD_CODER_PROMPT,
    COD_QUERY_PLANNER_PROMPT,
    COD_REVIEWER_PROMPT,
    COD_VALIDATOR_INSIGHTS_PROMPT,
    COD_VALIDATOR_REQUIREMENTS_PROMPT,
    CoDPromptMode,
    build_cod_prompt,
    estimate_token_savings,
    get_prompt_mode,
    set_prompt_mode,
)

__all__ = [
    # CoD Templates
    "CoDPromptMode",
    "get_prompt_mode",
    "set_prompt_mode",
    "build_cod_prompt",
    "estimate_token_savings",
    "COD_REVIEWER_PROMPT",
    "COD_CODER_PROMPT",
    "COD_VALIDATOR_INSIGHTS_PROMPT",
    "COD_VALIDATOR_REQUIREMENTS_PROMPT",
    "COD_QUERY_PLANNER_PROMPT",
    # A/B Testing
    "ABTestVariant",
    "ABTestResult",
    "ABTestSummary",
    "ABTestRunner",
    "quick_ab_test",
    "security_review_accuracy_scorer",
]
