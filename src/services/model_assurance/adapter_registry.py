"""Adapter Registry — declarative model capability registry (ADR-088 Phase 1.2).

The registry serves three purposes:

1. **Auto-disqualification.** Candidates lacking required capabilities
   (insufficient context window, no tool use, etc.) are filtered out
   before any expensive evaluation. The Scout Agent calls
   ``AdapterRegistry.disqualify`` early in its pipeline.
2. **Input normalisation.** Every model has a canonical adapter
   declaring its prompt format, tokenizer, and architecture so
   downstream evaluation produces comparable results across vendors.
3. **Cost transparency.** Per-token cost lives on the adapter so the
   utility-score formula (ADR-088 §Stage 5) can include economics in
   addition to capability metrics.

Adapters are **frozen dataclasses** — once registered, mutation is a
type error. The registry itself is mutable (add/remove/list adapters)
but operations on it are O(n) over a small set of models, so it stays
in-process; no database backing is required for v1.

ADR-088 v1 scope is Bedrock models only (per condition #12 from Sue).
HuggingFace and internal fine-tunes are deferred to Phase 3, but the
ModelProvider enum already names them so adding adapters later is a
config change, not a schema change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ModelProvider(Enum):
    """Foundation-model providers supported by the assurance pipeline."""

    BEDROCK = "bedrock"
    OPENAI = "openai"
    GOOGLE = "google"           # via Gemini adapter (ADR audit work)
    HUGGINGFACE = "huggingface"  # Phase 3
    INTERNAL = "internal"        # Phase 3 — Aura SWE-RL outputs


class TokenizerType(Enum):
    """Tokenizer family used by the model.

    The evaluation pipeline relies on this to compute consistent
    cost-per-token estimates and to size context windows correctly
    when adapting prompts for different models.
    """

    CLAUDE = "claude"      # Anthropic
    CL100K = "cl100k"      # GPT-4 family
    O200K = "o200k"        # GPT-4o family
    LLAMA = "llama"        # LLaMA-family / Mistral
    GEMINI = "gemini"      # Google Gemini
    SENTENCEPIECE = "sentencepiece"
    UNKNOWN = "unknown"


class ModelArchitecture(Enum):
    """Coarse-grained architecture class.

    Affects evaluation strategy: MoE models have variance in latency
    that dense models don't, and inference-only multimodal models may
    fail certain code-comprehension axes by construction.
    """

    DENSE = "dense"
    MOE = "moe"
    MULTIMODAL = "multimodal"
    UNKNOWN = "unknown"


class DisqualificationReason(Enum):
    """Why an adapter failed a requirements check."""

    CONTEXT_TOO_SMALL = "context_too_small"
    TOOL_USE_REQUIRED = "tool_use_required"
    STREAMING_REQUIRED = "streaming_required"
    PROVIDER_NOT_TRUSTED = "provider_not_trusted"
    MODEL_DEPRECATED = "model_deprecated"


@dataclass(frozen=True)
class ModelAdapter:
    """Declarative model capability descriptor.

    Every concrete model — Claude 3.5 Sonnet, GPT-4o, Gemini 1.5 Pro —
    registers exactly one ``ModelAdapter`` in :class:`AdapterRegistry`.
    Adapters are immutable: a new model version is a new adapter, not
    a mutation, so historical evaluations remain reproducible.

    Cost fields are USD per million tokens (M-token), matching how
    Bedrock and OpenAI publish pricing.
    """

    model_id: str
    provider: ModelProvider
    display_name: str
    max_context_tokens: int
    supports_tool_use: bool
    supports_streaming: bool
    tokenizer_type: TokenizerType
    architecture: ModelArchitecture
    cost_per_input_mtok: float
    cost_per_output_mtok: float
    required_prompt_format: str
    deprecated: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ValueError("ModelAdapter.model_id is required")
        if self.max_context_tokens <= 0:
            raise ValueError(
                f"ModelAdapter.max_context_tokens must be > 0; "
                f"got {self.max_context_tokens} for {self.model_id!r}"
            )
        if self.cost_per_input_mtok < 0 or self.cost_per_output_mtok < 0:
            raise ValueError(
                f"ModelAdapter cost fields must be non-negative; "
                f"got input={self.cost_per_input_mtok}, "
                f"output={self.cost_per_output_mtok}"
            )

    @property
    def cost_per_input_token(self) -> float:
        return self.cost_per_input_mtok / 1_000_000.0

    @property
    def cost_per_output_token(self) -> float:
        return self.cost_per_output_mtok / 1_000_000.0


@dataclass(frozen=True)
class ModelRequirements:
    """Capability bar a candidate must clear to enter evaluation.

    Tunable per evaluation profile — production assurance uses a
    higher bar than developer experimentation. Empty/zero values mean
    "no constraint on this dimension".
    """

    min_context_tokens: int = 0
    require_tool_use: bool = False
    require_streaming: bool = False
    trusted_providers: tuple[ModelProvider, ...] = field(
        default_factory=lambda: (
            ModelProvider.BEDROCK,
            ModelProvider.OPENAI,
            ModelProvider.GOOGLE,
        )
    )

    def check(self, adapter: ModelAdapter) -> tuple[DisqualificationReason, ...]:
        """Return reasons this adapter fails the requirements; empty == passes.

        Order matters: deprecation is reported first so a deprecated
        model isn't also flagged for the unrelated trust-tier check.
        Other checks are reported in declaration order (context,
        tool-use, streaming, provider trust).
        """
        reasons: list[DisqualificationReason] = []
        if adapter.deprecated:
            reasons.append(DisqualificationReason.MODEL_DEPRECATED)
        if adapter.max_context_tokens < self.min_context_tokens:
            reasons.append(DisqualificationReason.CONTEXT_TOO_SMALL)
        if self.require_tool_use and not adapter.supports_tool_use:
            reasons.append(DisqualificationReason.TOOL_USE_REQUIRED)
        if self.require_streaming and not adapter.supports_streaming:
            reasons.append(DisqualificationReason.STREAMING_REQUIRED)
        if (
            self.trusted_providers
            and adapter.provider not in self.trusted_providers
        ):
            reasons.append(DisqualificationReason.PROVIDER_NOT_TRUSTED)
        return tuple(reasons)


# =============================================================================
# Built-in adapters (ADR-088 v1 scope: Bedrock-only)
# =============================================================================
#
# Pricing reflects Bedrock on-demand US-EAST-1 list price as of 2026-Q2.
# Update via PR — the adapter version (model_id suffix) is immutable, so
# changes here represent a real Bedrock pricing announcement, not a fix.

ADAPTER_CLAUDE_35_SONNET = ModelAdapter(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    provider=ModelProvider.BEDROCK,
    display_name="Claude 3.5 Sonnet",
    max_context_tokens=200_000,
    supports_tool_use=True,
    supports_streaming=True,
    tokenizer_type=TokenizerType.CLAUDE,
    architecture=ModelArchitecture.DENSE,
    cost_per_input_mtok=3.00,
    cost_per_output_mtok=15.00,
    required_prompt_format="claude_messages_v1",
    notes="Aura production incumbent (ADR-088 v1).",
)


ADAPTER_CLAUDE_3_HAIKU = ModelAdapter(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    provider=ModelProvider.BEDROCK,
    display_name="Claude 3 Haiku",
    max_context_tokens=200_000,
    supports_tool_use=True,
    supports_streaming=True,
    tokenizer_type=TokenizerType.CLAUDE,
    architecture=ModelArchitecture.DENSE,
    cost_per_input_mtok=0.25,
    cost_per_output_mtok=1.25,
    required_prompt_format="claude_messages_v1",
    notes="Fast tier for low-stakes operations (ADR-029).",
)


ADAPTER_CLAUDE_3_OPUS = ModelAdapter(
    model_id="anthropic.claude-3-opus-20240229-v1:0",
    provider=ModelProvider.BEDROCK,
    display_name="Claude 3 Opus",
    max_context_tokens=200_000,
    supports_tool_use=True,
    supports_streaming=True,
    tokenizer_type=TokenizerType.CLAUDE,
    architecture=ModelArchitecture.DENSE,
    cost_per_input_mtok=15.00,
    cost_per_output_mtok=75.00,
    required_prompt_format="claude_messages_v1",
    notes="Highest-capability tier; reserved for complex reasoning.",
)


BUILTIN_ADAPTERS: tuple[ModelAdapter, ...] = (
    ADAPTER_CLAUDE_35_SONNET,
    ADAPTER_CLAUDE_3_HAIKU,
    ADAPTER_CLAUDE_3_OPUS,
)


# =============================================================================
# Registry
# =============================================================================


class AdapterRegistry:
    """In-process registry of :class:`ModelAdapter` instances.

    The registry is keyed by ``model_id``; registering a second
    adapter with the same model_id raises ``ValueError``. Re-registering
    requires explicit ``unregister`` first — this prevents silent
    overrides during test setup or hot-reload bugs that would change
    the cost basis of past evaluations.
    """

    def __init__(self, *, seed_builtins: bool = True) -> None:
        self._adapters: dict[str, ModelAdapter] = {}
        if seed_builtins:
            for adapter in BUILTIN_ADAPTERS:
                self.register(adapter)

    # ------------------------------------------------------------ mutation

    def register(self, adapter: ModelAdapter) -> None:
        if adapter.model_id in self._adapters:
            raise ValueError(
                f"Adapter for model_id={adapter.model_id!r} already registered. "
                f"Call unregister(model_id) first if replacement is intentional."
            )
        self._adapters[adapter.model_id] = adapter

    def unregister(self, model_id: str) -> ModelAdapter:
        if model_id not in self._adapters:
            raise KeyError(f"No adapter registered for model_id={model_id!r}")
        return self._adapters.pop(model_id)

    # ------------------------------------------------------------ query

    def get(self, model_id: str) -> ModelAdapter:
        if model_id not in self._adapters:
            raise KeyError(f"No adapter registered for model_id={model_id!r}")
        return self._adapters[model_id]

    def find(self, model_id: str) -> ModelAdapter | None:
        return self._adapters.get(model_id)

    def list_adapters(
        self,
        *,
        provider: ModelProvider | None = None,
        include_deprecated: bool = False,
    ) -> tuple[ModelAdapter, ...]:
        """Return adapters in deterministic registration order.

        Filters are applied conjunctively. Deprecated adapters are
        excluded by default — Phase 1.4's Scout Agent uses this to
        skip models the registry knows have been retired.
        """
        out = list(self._adapters.values())
        if provider is not None:
            out = [a for a in out if a.provider is provider]
        if not include_deprecated:
            out = [a for a in out if not a.deprecated]
        return tuple(out)

    def __len__(self) -> int:
        return len(self._adapters)

    def __contains__(self, model_id: object) -> bool:
        return isinstance(model_id, str) and model_id in self._adapters

    # ------------------------------------------------------------ checks

    def disqualify(
        self,
        adapter_or_id: ModelAdapter | str,
        requirements: ModelRequirements,
    ) -> tuple[DisqualificationReason, ...]:
        """Run :class:`ModelRequirements`.check against the adapter.

        Accepts a model_id string for ergonomic call sites in the
        Scout Agent (which receives string IDs from Bedrock's
        ListFoundationModels).
        """
        adapter = (
            adapter_or_id
            if isinstance(adapter_or_id, ModelAdapter)
            else self.get(adapter_or_id)
        )
        return requirements.check(adapter)

    def filter_qualified(
        self,
        adapters: tuple[ModelAdapter, ...] | None,
        requirements: ModelRequirements,
    ) -> tuple[ModelAdapter, ...]:
        """Return only adapters that satisfy ``requirements``.

        ``adapters=None`` means "all registered adapters". Used by the
        Scout Agent to pre-filter newly-discovered candidates.
        """
        pool = adapters if adapters is not None else self.list_adapters()
        return tuple(a for a in pool if not requirements.check(a))
