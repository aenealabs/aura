"""
Current Claude models for Aura services, in one place.

Services that call Bedrock pick a model by tier instead of naming a model version, so the
codebase does not go stale as models retire:

    fast      Claude Haiku   (classification, extraction, quick checks)
    accurate  Claude Sonnet  (code generation, review, most reasoning)
    maximum   Claude Opus    (cross-codebase and novel-threat reasoning)

``claude_model(tier)`` returns, in order:
    1. ``AURA_MODEL_<TIER>`` from the environment (a deployment-wide pin),
    2. the model Bedrock discovery chose for the tier in this process and region
       (see bedrock_model_discovery; the LLM service runs it at startup in AWS mode),
    3. the current model below.

Pin approved models per environment in its Bedrock secret (ADR-088); a service's own
explicit configuration (for example an environment variable it documents) still wins.
"""

from __future__ import annotations

import os

from src.services.bedrock_model_discovery import discovered_models

# Current Claude models by Bedrock ID (update when a newer model is approved)
CURRENT_CLAUDE_MODELS: dict[str, str] = {
    "fast": "anthropic.claude-haiku-4-5",
    "accurate": "anthropic.claude-sonnet-5-5",
    "maximum": "anthropic.claude-opus-5-5",
}


def claude_model(tier: str = "accurate") -> str:
    """The Claude model to use for a tier (fast, accurate, maximum)."""
    if tier not in CURRENT_CLAUDE_MODELS:
        raise ValueError(f"Unknown model tier: {tier}")
    pinned = os.environ.get(f"AURA_MODEL_{tier.upper()}")
    if pinned and pinned != "auto":
        return pinned
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    found = discovered_models(region)
    return found.get(tier) or CURRENT_CLAUDE_MODELS[tier]
