"""Allowlisted model registries (ADR-088 Phase 2.1).

Per ADR-088 §Stage 2 condition #6 (Sally): only models from pre-
approved registries pass. This module enforces that gate.

Default allowlist (v1):
    BEDROCK              — all entries; Bedrock vouches for provider
                           identity at the catalog level.
    INTERNAL_ECR         — Aura's own fine-tuned models from ADR-050
                           SWE-RL pipeline. Restricted to a per-account
                           ECR repository name pattern.
    HUGGINGFACE_CURATED  — explicitly enumerated repository IDs only.
                           Open-ended HuggingFace download is not
                           allowed; admins must add each repo via PR.

Allowlist mutation is intentionally hostile to autonomous agents:
``add_huggingface_entry`` requires a code change (not a runtime call
from an agent role). Production code paths that need to add entries
go through a CloudFormation-driven config update, not the agent
runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.services.supply_chain.model_provenance.contracts import (
    ModelArtifact,
    ModelRegistry,
)


@dataclass(frozen=True)
class AllowlistEntry:
    """One allowlisted source.

    For Bedrock the entry is provider-scoped (e.g. ``anthropic``,
    ``amazon``); for ECR it's a repo pattern; for HuggingFace it's
    an exact repo ID (e.g. ``meta-llama/CodeLlama-34b-Instruct``).
    """

    registry: ModelRegistry
    identifier: str
    description: str = ""


@dataclass(frozen=True)
class AllowlistDecision:
    """Outcome of one allowlist check."""

    allowed: bool
    matched_entry: AllowlistEntry | None
    reason: str = ""


# Default v1 allowlist. The Bedrock entries cover the providers Aura
# evaluates today; new Bedrock providers require a one-line addition
# here (PR-gated, not config-driven, to ensure two-pair-of-eyes review).
DEFAULT_BEDROCK_PROVIDERS: tuple[AllowlistEntry, ...] = (
    AllowlistEntry(
        registry=ModelRegistry.BEDROCK,
        identifier="anthropic",
        description="Anthropic — Claude family",
    ),
    AllowlistEntry(
        registry=ModelRegistry.BEDROCK,
        identifier="amazon",
        description="Amazon — Titan family",
    ),
    AllowlistEntry(
        registry=ModelRegistry.BEDROCK,
        identifier="meta",
        description="Meta — LLaMA family",
    ),
)


# Internal ECR repo pattern. Tightened at deployment time via
# ``AdditionalArguments`` to the AllowlistService.
DEFAULT_INTERNAL_ECR_PATTERN = "aura-models/"


# HuggingFace curated allowlist starts empty. Entries added via PR
# only — see module docstring for the policy rationale.
DEFAULT_HUGGINGFACE_ALLOWLIST: tuple[AllowlistEntry, ...] = ()


@dataclass(frozen=True)
class RegistryAllowlist:
    """Composite allowlist over all three registries.

    Frozen so it can be cached / shared across threads. Use
    :meth:`with_huggingface_entry` to extend at module load time;
    runtime mutation is not exposed.
    """

    bedrock_providers: tuple[AllowlistEntry, ...] = field(
        default_factory=lambda: DEFAULT_BEDROCK_PROVIDERS
    )
    internal_ecr_pattern: str = DEFAULT_INTERNAL_ECR_PATTERN
    huggingface_allowlist: tuple[AllowlistEntry, ...] = field(
        default_factory=lambda: DEFAULT_HUGGINGFACE_ALLOWLIST
    )

    def check(self, artifact: ModelArtifact) -> AllowlistDecision:
        """Decide whether ``artifact`` is allowed by the allowlist."""
        if artifact.registry is ModelRegistry.BEDROCK:
            return self._check_bedrock(artifact)
        if artifact.registry is ModelRegistry.INTERNAL_ECR:
            return self._check_ecr(artifact)
        if artifact.registry is ModelRegistry.HUGGINGFACE_CURATED:
            return self._check_hf(artifact)
        # Defensive — every registry value is handled above.
        return AllowlistDecision(
            allowed=False,
            matched_entry=None,
            reason=f"unknown registry={artifact.registry.value}",
        )

    def _check_bedrock(self, artifact: ModelArtifact) -> AllowlistDecision:
        provider = artifact.provider.lower()
        for entry in self.bedrock_providers:
            if entry.identifier.lower() == provider:
                return AllowlistDecision(allowed=True, matched_entry=entry)
        return AllowlistDecision(
            allowed=False,
            matched_entry=None,
            reason=f"Bedrock provider {artifact.provider!r} not allowlisted",
        )

    def _check_ecr(self, artifact: ModelArtifact) -> AllowlistDecision:
        if artifact.model_id.startswith(self.internal_ecr_pattern):
            return AllowlistDecision(
                allowed=True,
                matched_entry=AllowlistEntry(
                    registry=ModelRegistry.INTERNAL_ECR,
                    identifier=self.internal_ecr_pattern,
                    description="Internal ECR pattern match",
                ),
            )
        return AllowlistDecision(
            allowed=False,
            matched_entry=None,
            reason=(
                f"ECR model_id {artifact.model_id!r} does not match "
                f"pattern {self.internal_ecr_pattern!r}"
            ),
        )

    def _check_hf(self, artifact: ModelArtifact) -> AllowlistDecision:
        for entry in self.huggingface_allowlist:
            if entry.identifier == artifact.model_id:
                return AllowlistDecision(allowed=True, matched_entry=entry)
        return AllowlistDecision(
            allowed=False,
            matched_entry=None,
            reason=(
                f"HuggingFace repo {artifact.model_id!r} not in curated allowlist"
            ),
        )

    def with_huggingface_entry(
        self, repo_id: str, description: str = ""
    ) -> "RegistryAllowlist":
        """Return a new allowlist with an additional HuggingFace entry.

        Used at module-load time to extend the curated list. The
        return-new pattern preserves the frozen contract.
        """
        new_entry = AllowlistEntry(
            registry=ModelRegistry.HUGGINGFACE_CURATED,
            identifier=repo_id,
            description=description,
        )
        return RegistryAllowlist(
            bedrock_providers=self.bedrock_providers,
            internal_ecr_pattern=self.internal_ecr_pattern,
            huggingface_allowlist=self.huggingface_allowlist + (new_entry,),
        )


def default_allowlist() -> RegistryAllowlist:
    """Return the v1 production-default allowlist."""
    return RegistryAllowlist()
