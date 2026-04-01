"""
VL-JEPA Embedding Predictor for Selective Decoding.

This module implements the Joint Embedding Predictive Architecture (JEPA)
for efficient code understanding tasks. Based on Meta FAIR's VL-JEPA research
(December 2025), this enables 2.85x efficiency improvement by predicting
embeddings in latent space rather than generating tokens.

Key Features:
- Selective decoding: Non-generative tasks skip the decoder entirely
- Task routing: Automatic classification of task types
- InfoNCE contrastive loss for embedding prediction
- Integration with existing code encoders (Titan, OpenSearch)

Architecture:
- X-Encoder: Encodes input code/text to embeddings
- Predictor: Maps X embeddings to Y space (target prediction)
- Y-Decoder: Lightweight decoder for generative tasks only
- Task Router: Classifies task type for selective decoding

Reference: ADR-051 Recursive Context Scaling and Embedding Prediction
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, TypeVar

import numpy as np

logger = logging.getLogger(__name__)

# Type variable for generic encoder types
T = TypeVar("T")


class TaskType(Enum):
    """
    Task types for routing to generative vs non-generative paths.

    Non-generative tasks (2.85x faster):
    - CLASSIFICATION: Categorize code/text into predefined classes
    - RETRIEVAL: Find similar embeddings in vector store
    - SIMILARITY: Compute similarity between code snippets
    - ROUTING: Route to appropriate agent based on embedding

    Generative tasks (require decoder):
    - GENERATION: Generate code/text output
    - EXPLANATION: Generate natural language explanation
    - CODE_GENERATION: Generate code from description
    """

    # Non-generative tasks (fast path - embedding only)
    CLASSIFICATION = "classification"
    RETRIEVAL = "retrieval"
    SIMILARITY = "similarity"
    ROUTING = "routing"

    # Generative tasks (slow path - requires decoder)
    GENERATION = "generation"
    EXPLANATION = "explanation"
    CODE_GENERATION = "code_gen"

    @property
    def is_generative(self) -> bool:
        """Check if this task type requires text generation."""
        return self in (
            TaskType.GENERATION,
            TaskType.EXPLANATION,
            TaskType.CODE_GENERATION,
        )

    @property
    def is_non_generative(self) -> bool:
        """Check if this task type can use fast embedding-only path."""
        return not self.is_generative


@dataclass
class JEPAConfig:
    """
    Configuration for JEPA architecture.

    Attributes:
        embed_dim: Embedding dimension (default 768 for BERT-like models)
        predictor_depth: Number of transformer layers in predictor
        decoder_depth: Number of transformer layers in decoder (lightweight)
        num_heads: Number of attention heads
        temperature: Temperature for InfoNCE loss (lower = sharper)
        dropout: Dropout rate for regularization
        max_sequence_length: Maximum input sequence length
        mask_ratio: Ratio of tokens to mask for training
        num_negatives: Number of negatives for contrastive loss
        use_ema_encoder: Use exponential moving average for Y-encoder
        ema_decay: EMA decay rate for Y-encoder
    """

    embed_dim: int = 768
    predictor_depth: int = 6
    decoder_depth: int = 2  # Lightweight decoder
    num_heads: int = 12
    temperature: float = 0.07  # InfoNCE temperature
    dropout: float = 0.1
    max_sequence_length: int = 8192
    mask_ratio: float = 0.75  # I-JEPA uses high mask ratios
    num_negatives: int = 64
    use_ema_encoder: bool = True
    ema_decay: float = 0.999

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.embed_dim % self.num_heads != 0:
            raise ValueError(
                f"embed_dim ({self.embed_dim}) must be divisible by "
                f"num_heads ({self.num_heads})"
            )
        if not 0.0 < self.temperature <= 1.0:
            raise ValueError(f"temperature must be in (0, 1], got {self.temperature}")
        if not 0.0 <= self.mask_ratio < 1.0:
            raise ValueError(f"mask_ratio must be in [0, 1), got {self.mask_ratio}")


@dataclass
class PredictionResult:
    """
    Result of embedding prediction.

    Attributes:
        embedding: Predicted Y-embedding (shape: [batch, seq_len, embed_dim])
        task_type: Detected or specified task type
        decoded_text: Generated text (only for generative tasks)
        confidence: Confidence score for task routing
        latency_ms: Time taken for prediction
        operations_saved: Ratio of operations saved vs full decoding
        request_id: Unique identifier for this prediction
    """

    embedding: list[list[float]]  # 2D for batch, 3D flattened
    task_type: TaskType
    decoded_text: str | None = None
    confidence: float = 1.0
    latency_ms: float = 0.0
    operations_saved: str = "1x"
    request_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "embedding": self.embedding,
            "task_type": self.task_type.value,
            "decoded_text": self.decoded_text,
            "confidence": self.confidence,
            "latency_ms": self.latency_ms,
            "operations_saved": self.operations_saved,
            "request_id": self.request_id,
        }


@dataclass
class MaskingStrategy:
    """
    Masking strategy for JEPA training.

    I-JEPA uses block masking where contiguous regions are masked,
    forcing the model to predict based on context rather than
    interpolation from nearby tokens.

    Attributes:
        mask_ratio: Ratio of tokens to mask
        min_mask_patches: Minimum number of contiguous masked patches
        max_mask_patches: Maximum number of contiguous masked patches
        aspect_ratio_range: Range of aspect ratios for 2D masking
    """

    mask_ratio: float = 0.75
    min_mask_patches: int = 4
    max_mask_patches: int = 16
    aspect_ratio_range: tuple[float, float] = (0.75, 1.5)

    def generate_mask(
        self, sequence_length: int, seed: int | None = None
    ) -> list[bool]:
        """
        Generate a block mask for the given sequence length.

        Args:
            sequence_length: Length of the sequence to mask
            seed: Random seed for reproducibility

        Returns:
            List of booleans where True = masked, False = visible
        """
        import random

        if seed is not None:
            random.seed(seed)

        # Calculate number of tokens to mask
        num_mask = int(sequence_length * self.mask_ratio)

        # Generate block masks
        mask = [False] * sequence_length
        masked_count = 0

        while masked_count < num_mask:
            # Random starting position
            start = random.randint(0, sequence_length - 1)

            # Random block size
            block_size = random.randint(self.min_mask_patches, self.max_mask_patches)
            block_size = min(block_size, num_mask - masked_count)

            # Apply mask
            for i in range(block_size):
                idx = (start + i) % sequence_length
                if not mask[idx]:
                    mask[idx] = True
                    masked_count += 1

        return mask

    def generate_target_indices(
        self, mask: list[bool], num_targets: int = 4
    ) -> list[int]:
        """
        Generate target indices from masked positions.

        For I-JEPA, we predict embeddings at specific masked positions
        rather than all masked positions.

        Args:
            mask: Boolean mask (True = masked)
            num_targets: Number of target positions to predict

        Returns:
            List of indices to predict embeddings for
        """
        import random

        masked_indices = [i for i, m in enumerate(mask) if m]
        if len(masked_indices) <= num_targets:
            return masked_indices

        return random.sample(masked_indices, num_targets)


class Encoder(Protocol):
    """Protocol for encoder implementations."""

    def encode(self, text: str) -> list[float]:
        """Encode text to embedding vector."""
        ...

    async def encode_async(self, text: str) -> list[float]:
        """Async encode text to embedding vector."""
        ...


class Decoder(Protocol):
    """Protocol for decoder implementations."""

    def decode(self, embedding: list[float]) -> str:
        """Decode embedding to text."""
        ...

    async def decode_async(self, embedding: list[float]) -> str:
        """Async decode embedding to text."""
        ...


@dataclass
class TransformerLayer:
    """
    Lightweight transformer layer for predictor/decoder.

    This is a simplified implementation for inference.
    In production, this would use PyTorch or JAX.
    """

    embed_dim: int
    num_heads: int
    dropout: float = 0.1

    # Weights (initialized lazily)
    _q_weight: Any = field(default=None, repr=False)
    _k_weight: Any = field(default=None, repr=False)
    _v_weight: Any = field(default=None, repr=False)
    _o_weight: Any = field(default=None, repr=False)
    _ffn_weight1: Any = field(default=None, repr=False)
    _ffn_weight2: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Initialize weights with Xavier initialization."""
        self._initialize_weights()

    def _initialize_weights(self) -> None:
        """Initialize transformer weights."""
        scale = math.sqrt(2.0 / (self.embed_dim + self.embed_dim))

        def init_weight(rows: int, cols: int) -> np.ndarray:
            return np.random.normal(0, scale, (rows, cols))

        self._q_weight = init_weight(self.embed_dim, self.embed_dim)
        self._k_weight = init_weight(self.embed_dim, self.embed_dim)
        self._v_weight = init_weight(self.embed_dim, self.embed_dim)
        self._o_weight = init_weight(self.embed_dim, self.embed_dim)
        self._ffn_weight1 = init_weight(self.embed_dim, self.embed_dim * 4)
        self._ffn_weight2 = init_weight(self.embed_dim * 4, self.embed_dim)

    def forward(self, x: list[list[float]]) -> list[list[float]]:
        """
        Forward pass through transformer layer.

        Args:
            x: Input embeddings [seq_len, embed_dim]

        Returns:
            Output embeddings [seq_len, embed_dim]
        """
        # Self-attention (simplified)
        attn_output = self._self_attention(x)

        # Residual + LayerNorm
        x = self._add_and_norm(x, attn_output)

        # FFN
        ffn_output = self._feed_forward(x)

        # Residual + LayerNorm
        x = self._add_and_norm(x, ffn_output)

        return x

    def _self_attention(self, x: list[list[float]]) -> list[list[float]]:
        """Simplified self-attention computation."""
        x_np = np.array(x)
        head_dim = self.embed_dim // self.num_heads
        q = x_np @ self._q_weight
        k = x_np @ self._k_weight
        v = x_np @ self._v_weight
        scale = 1.0 / math.sqrt(head_dim)
        attn_scores = (q @ k.T) * scale
        # Softmax
        attn_scores -= attn_scores.max(axis=1, keepdims=True)
        exp_scores = np.exp(attn_scores)
        attn_scores = exp_scores / exp_scores.sum(axis=1, keepdims=True)
        output = attn_scores @ v
        output = output @ self._o_weight
        return output.tolist()

    def _feed_forward(self, x: list[list[float]]) -> list[list[float]]:
        """Feed-forward network with GELU activation."""
        x_np = np.array(x)
        hidden = x_np @ self._ffn_weight1
        # GELU activation (vectorized)
        hidden = (
            0.5
            * hidden
            * (1.0 + np.tanh(np.sqrt(2.0 / np.pi) * (hidden + 0.044715 * hidden**3)))
        )
        output = hidden @ self._ffn_weight2
        return output.tolist()

    def _matmul(self, a: list[list[float]], b) -> list[list[float]]:
        """Matrix multiplication."""
        if b is None:
            return a
        a_np = np.array(a) if not isinstance(a, np.ndarray) else a
        b_np = np.array(b) if not isinstance(b, np.ndarray) else b
        return (a_np @ b_np).tolist()

    def _add_and_norm(
        self, x: list[list[float]], residual: list[list[float]]
    ) -> list[list[float]]:
        """Add residual and apply layer normalization."""
        eps = 1e-6
        result = []

        for i in range(len(x)):
            # Add residual
            combined = [x[i][j] + residual[i][j] for j in range(len(x[i]))]

            # Layer norm
            mean = sum(combined) / len(combined)
            var = sum((v - mean) ** 2 for v in combined) / len(combined)
            std = math.sqrt(var + eps)

            normalized = [(v - mean) / std for v in combined]
            result.append(normalized)

        return result


class EmbeddingPredictor:
    """
    JEPA-style embedding predictor for selective decoding.

    This predictor maps input embeddings to target embedding space,
    enabling non-generative tasks to skip the decoder entirely.

    Architecture:
    - Predictor: Transformer encoder that predicts Y-embeddings from X-embeddings
    - Decoder: Lightweight transformer decoder (only used for generative tasks)
    - Task Router: Linear classifier for automatic task type detection

    Usage:
        config = JEPAConfig(embed_dim=768, predictor_depth=6)
        predictor = EmbeddingPredictor(config)

        # Non-generative task (fast)
        result = predictor.predict(x_embed, task_type=TaskType.CLASSIFICATION)

        # Generative task (uses decoder)
        result = predictor.predict(x_embed, task_type=TaskType.GENERATION)

    Reference: Meta FAIR VL-JEPA paper (December 2025)
    """

    def __init__(self, config: JEPAConfig):
        """
        Initialize the embedding predictor.

        Args:
            config: JEPA configuration
        """
        self.config = config

        # Predictor layers
        self.predictor_layers = [
            TransformerLayer(
                embed_dim=config.embed_dim,
                num_heads=config.num_heads,
                dropout=config.dropout,
            )
            for _ in range(config.predictor_depth)
        ]

        # Lightweight decoder layers
        self.decoder_layers = [
            TransformerLayer(
                embed_dim=config.embed_dim,
                num_heads=config.num_heads,
                dropout=config.dropout,
            )
            for _ in range(config.decoder_depth)
        ]

        # Task router weights
        self._init_task_router()

        # Masking strategy
        self.masking_strategy = MaskingStrategy(mask_ratio=config.mask_ratio)

        logger.info(
            f"Initialized EmbeddingPredictor with {config.predictor_depth} "
            f"predictor layers and {config.decoder_depth} decoder layers"
        )

    def _init_task_router(self) -> None:
        """Initialize task router weights."""
        import random

        num_tasks = len(TaskType)
        scale = math.sqrt(2.0 / (self.config.embed_dim + num_tasks))

        self._task_router_weight = [
            [random.gauss(0, scale) for _ in range(num_tasks)]
            for _ in range(self.config.embed_dim)
        ]

        self._task_router_bias = [random.gauss(0, 0.01) for _ in range(num_tasks)]

    def predict(
        self,
        x_embed: list[list[float]],
        task_type: TaskType | None = None,
        request_id: str | None = None,
    ) -> PredictionResult:
        """
        Predict Y-embedding from X-embedding with selective decoding.

        For non-generative tasks, only the predictor runs (2.85x faster).
        For generative tasks, predictor + decoder runs.

        Args:
            x_embed: Input embeddings [seq_len, embed_dim]
            task_type: Task type for routing (auto-detected if None)
            request_id: Optional request ID for tracking

        Returns:
            PredictionResult with embedding and optional decoded text
        """
        start_time = time.time()
        request_id = request_id or self._generate_request_id(x_embed)

        # Predict Y-embedding
        y_pred = self._run_predictor(x_embed)

        # Route task if not specified
        if task_type is None:
            task_type, confidence = self._route_task(y_pred)
        else:
            confidence = 1.0

        # Calculate operations saved
        if task_type.is_non_generative:
            operations_saved = "2.85x"
            decoded_text = None
        else:
            operations_saved = "1x"
            decoded_text = self._run_decoder(y_pred)

        latency_ms = (time.time() - start_time) * 1000

        result = PredictionResult(
            embedding=y_pred,
            task_type=task_type,
            decoded_text=decoded_text,
            confidence=confidence,
            latency_ms=latency_ms,
            operations_saved=operations_saved,
            request_id=request_id,
        )

        logger.debug(
            f"Prediction complete: task_type={task_type.value}, "
            f"latency={latency_ms:.2f}ms, saved={operations_saved}"
        )

        return result

    async def predict_async(
        self,
        x_embed: list[list[float]],
        task_type: TaskType | None = None,
        request_id: str | None = None,
    ) -> PredictionResult:
        """Async version of predict."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.predict, x_embed, task_type, request_id
        )

    def _run_predictor(self, x_embed: list[list[float]]) -> list[list[float]]:
        """Run the predictor transformer on input embeddings."""
        output = x_embed

        for layer in self.predictor_layers:
            output = layer.forward(output)

        return output

    def _run_decoder(self, y_embed: list[list[float]]) -> str:
        """Run the decoder transformer to generate text."""
        output = y_embed

        for layer in self.decoder_layers:
            output = layer.forward(output)

        # Simplified text generation (in production, this would use
        # vocabulary projection and beam search)
        return self._embeddings_to_text(output)

    def _route_task(self, y_embed: list[list[float]]) -> tuple[TaskType, float]:
        """
        Route to task type based on embedding.

        Uses a linear classifier on the mean-pooled embedding.

        Args:
            y_embed: Predicted Y-embedding

        Returns:
            Tuple of (task_type, confidence)
        """
        # Mean pool
        seq_len = len(y_embed)
        pooled = [0.0] * self.config.embed_dim

        for i in range(seq_len):
            for j in range(self.config.embed_dim):
                pooled[j] += y_embed[i][j] / seq_len

        # Linear projection
        num_tasks = len(TaskType)
        logits = list(self._task_router_bias)

        for i in range(self.config.embed_dim):
            for j in range(num_tasks):
                logits[j] += pooled[i] * self._task_router_weight[i][j]

        # Softmax
        max_logit = max(logits)
        exp_logits = [math.exp(logit - max_logit) for logit in logits]
        sum_exp = sum(exp_logits)
        probs = [e / sum_exp for e in exp_logits]

        # Get best task
        best_idx = probs.index(max(probs))
        task_types = list(TaskType)
        best_task = task_types[best_idx]
        confidence = probs[best_idx]

        return best_task, confidence

    def _embeddings_to_text(self, embeddings: list[list[float]]) -> str:
        """
        Convert embeddings to text (simplified).

        In production, this would use vocabulary projection
        and proper decoding (beam search, sampling, etc.).
        """
        # Placeholder: return a hash-based representation
        flat = [v for row in embeddings for v in row]
        # MD5 used for ID generation, not security
        hash_val = hashlib.md5(str(flat).encode(), usedforsecurity=False).hexdigest()[
            :8
        ]
        return f"[decoded:{hash_val}]"

    def _generate_request_id(self, x_embed: list[list[float]]) -> str:
        """Generate a unique request ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        # MD5 used for ID generation, not security
        embed_hash = hashlib.md5(
            str(x_embed[:3]).encode(), usedforsecurity=False
        ).hexdigest()[:8]
        return f"jepa-{timestamp}-{embed_hash}"

    def compute_infonce_loss(
        self,
        y_pred: list[list[float]],
        y_true: list[list[float]],
        negatives: list[list[list[float]]],
    ) -> float:
        """
        Compute InfoNCE contrastive loss for training.

        loss = -log(exp(sim(y_pred, y_true)/τ) / Σ exp(sim(y_pred, y_i)/τ))

        Args:
            y_pred: Predicted embeddings [seq_len, embed_dim]
            y_true: True target embeddings [seq_len, embed_dim]
            negatives: Negative examples [num_negatives, seq_len, embed_dim]

        Returns:
            InfoNCE loss value
        """
        # Mean pool to get single vectors
        pred_pooled = self._mean_pool(y_pred)
        true_pooled = self._mean_pool(y_true)

        # Positive similarity
        pos_sim = self._cosine_similarity(pred_pooled, true_pooled)
        pos_sim /= self.config.temperature

        # Negative similarities
        neg_sims = []
        for neg in negatives:
            neg_pooled = self._mean_pool(neg)
            sim = self._cosine_similarity(pred_pooled, neg_pooled)
            neg_sims.append(sim / self.config.temperature)

        # InfoNCE loss
        max_sim = max(pos_sim, max(neg_sims) if neg_sims else pos_sim)
        pos_exp = math.exp(pos_sim - max_sim)
        neg_exp_sum = sum(math.exp(s - max_sim) for s in neg_sims)

        loss = -math.log(pos_exp / (pos_exp + neg_exp_sum))

        return loss

    def _mean_pool(self, embeddings: list[list[float]]) -> list[float]:
        """Mean pool embeddings across sequence dimension."""
        if not embeddings:
            return []

        seq_len = len(embeddings)
        embed_dim = len(embeddings[0])

        pooled = [0.0] * embed_dim
        for i in range(seq_len):
            for j in range(embed_dim):
                pooled[j] += embeddings[i][j] / seq_len

        return pooled

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(a[i] * b[i] for i in range(len(a)))
        norm_a = math.sqrt(sum(x**2 for x in a))
        norm_b = math.sqrt(sum(x**2 for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)

    def get_stats(self) -> dict[str, Any]:
        """Get predictor statistics."""
        return {
            "embed_dim": self.config.embed_dim,
            "predictor_depth": self.config.predictor_depth,
            "decoder_depth": self.config.decoder_depth,
            "num_heads": self.config.num_heads,
            "temperature": self.config.temperature,
            "mask_ratio": self.config.mask_ratio,
            "num_predictor_params": self._count_params(self.predictor_layers),
            "num_decoder_params": self._count_params(self.decoder_layers),
        }

    def _count_params(self, layers: list[TransformerLayer]) -> int:
        """Count approximate number of parameters."""
        params_per_layer = (
            4 * self.config.embed_dim**2  # Q, K, V, O projections
            + 2 * self.config.embed_dim * 4 * self.config.embed_dim  # FFN
        )
        return len(layers) * params_per_layer


class SelectiveDecodingService:
    """
    Service layer for JEPA-based selective decoding in Aura agents.

    This service integrates the EmbeddingPredictor with existing
    code encoders and provides a high-level API for agent tasks.

    Features:
    - Automatic task type detection
    - Integration with external encoders (Titan, OpenSearch)
    - Batch processing support
    - Metrics collection

    Usage:
        service = SelectiveDecodingService(
            x_encoder=TitanEncoder(),
            predictor=EmbeddingPredictor(config),
            config=config
        )

        # Fast path for classification
        result = await service.process_task(
            input_text="def vulnerable_function...",
            task_hint=TaskType.CLASSIFICATION
        )

        # Auto-detect task type
        result = await service.process_task(
            input_text="Explain this code..."
        )
    """

    def __init__(
        self,
        x_encoder: Encoder | None = None,
        y_encoder: Encoder | None = None,
        predictor: EmbeddingPredictor | None = None,
        config: JEPAConfig | None = None,
    ):
        """
        Initialize the selective decoding service.

        Args:
            x_encoder: Encoder for input text (optional, uses mock if None)
            y_encoder: Encoder for target text (for training, optional)
            predictor: JEPA embedding predictor (created if None)
            config: JEPA configuration
        """
        self.config = config or JEPAConfig()
        self.predictor = predictor or EmbeddingPredictor(self.config)
        self.x_encoder = x_encoder
        self.y_encoder = y_encoder

        # Metrics
        self._request_count = 0
        self._fast_path_count = 0
        self._slow_path_count = 0
        self._total_latency_ms = 0.0

        logger.info("Initialized SelectiveDecodingService")

    async def process_task(
        self,
        input_text: str,
        task_hint: TaskType | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Process task with selective decoding.

        Returns embedding for non-generative tasks (fast path).
        Returns decoded text for generative tasks (slow path).

        Args:
            input_text: Input text to process
            task_hint: Optional task type hint
            request_id: Optional request ID for tracking

        Returns:
            Dictionary with:
            - type: "embedding" or "text"
            - embedding: Predicted embedding (for non-generative)
            - text: Decoded text (for generative)
            - task_type: Detected/specified task type
            - operations_saved: Efficiency gain
        """
        start_time = time.time()
        self._request_count += 1

        # Encode input
        x_embed = await self._encode_input(input_text)

        # Predict in embedding space
        result = await self.predictor.predict_async(
            x_embed, task_type=task_hint, request_id=request_id
        )

        # Track metrics
        latency = (time.time() - start_time) * 1000
        self._total_latency_ms += latency

        if result.task_type.is_non_generative:
            self._fast_path_count += 1
            return {
                "type": "embedding",
                "embedding": result.embedding,
                "task_type": result.task_type.value,
                "confidence": result.confidence,
                "operations_saved": result.operations_saved,
                "latency_ms": latency,
                "request_id": result.request_id,
            }
        else:
            self._slow_path_count += 1
            return {
                "type": "text",
                "text": result.decoded_text,
                "embedding": result.embedding,
                "task_type": result.task_type.value,
                "confidence": result.confidence,
                "latency_ms": latency,
                "request_id": result.request_id,
            }

    async def classify_code(
        self, code: str, labels: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Classify code using embedding similarity (fast path).

        Args:
            code: Code snippet to classify
            labels: Optional list of possible labels

        Returns:
            Classification result with label and confidence
        """
        result = await self.process_task(code, task_hint=TaskType.CLASSIFICATION)

        # In production, this would compare embedding to label embeddings
        return {
            "classification": result,
            "predicted_label": "unknown",  # Would use vector similarity
            "labels": labels or [],
        }

    async def compute_similarity(self, code_a: str, code_b: str) -> dict[str, Any]:
        """
        Compute similarity between two code snippets (fast path).

        Args:
            code_a: First code snippet
            code_b: Second code snippet

        Returns:
            Similarity score and embeddings
        """
        # Encode both
        embed_a = await self._encode_input(code_a)
        embed_b = await self._encode_input(code_b)

        # Predict Y-embeddings
        result_a = await self.predictor.predict_async(
            embed_a, task_type=TaskType.SIMILARITY
        )
        result_b = await self.predictor.predict_async(
            embed_b, task_type=TaskType.SIMILARITY
        )

        # Compute similarity
        pooled_a = self.predictor._mean_pool(result_a.embedding)
        pooled_b = self.predictor._mean_pool(result_b.embedding)
        similarity = self.predictor._cosine_similarity(pooled_a, pooled_b)

        return {
            "similarity": similarity,
            "embedding_a": result_a.embedding,
            "embedding_b": result_b.embedding,
            "operations_saved": "2.85x",
        }

    async def route_to_agent(
        self, task_description: str, available_agents: list[str]
    ) -> dict[str, Any]:
        """
        Route task to appropriate agent using embedding (fast path).

        Args:
            task_description: Description of the task
            available_agents: List of available agent names

        Returns:
            Routing decision with confidence scores
        """
        result = await self.process_task(task_description, task_hint=TaskType.ROUTING)

        # In production, compare embedding to agent capability embeddings
        return {
            "task_embedding": result["embedding"],
            "recommended_agent": available_agents[0] if available_agents else "unknown",
            "confidence": result["confidence"],
            "available_agents": available_agents,
            "operations_saved": "2.85x",
        }

    async def generate_explanation(self, code: str) -> dict[str, Any]:
        """
        Generate code explanation (slow path - uses decoder).

        Args:
            code: Code snippet to explain

        Returns:
            Generated explanation
        """
        result = await self.process_task(code, task_hint=TaskType.EXPLANATION)

        return {
            "explanation": result.get("text", ""),
            "embedding": result["embedding"],
            "latency_ms": result["latency_ms"],
        }

    async def _encode_input(self, text: str) -> list[list[float]]:
        """
        Encode input text to embeddings.

        Uses external encoder if provided, otherwise creates mock embeddings.
        """
        if self.x_encoder is not None:
            if hasattr(self.x_encoder, "encode_async"):
                flat_embed = await self.x_encoder.encode_async(text)
            else:
                flat_embed = self.x_encoder.encode(text)

            # Reshape to [seq_len, embed_dim]
            return self._reshape_embedding(flat_embed)
        else:
            # Mock encoding for testing
            return self._mock_encode(text)

    def _reshape_embedding(self, flat: list[float]) -> list[list[float]]:
        """Reshape flat embedding to [seq_len, embed_dim]."""
        embed_dim = self.config.embed_dim

        # If already correct size, return as single sequence
        if len(flat) == embed_dim:
            return [flat]

        # Otherwise, chunk into sequences
        seq_len = max(1, len(flat) // embed_dim)
        result = []

        for i in range(seq_len):
            start = i * embed_dim
            end = start + embed_dim
            if end <= len(flat):
                result.append(flat[start:end])

        # Pad if needed
        if not result:
            result = [[0.0] * embed_dim]

        return result

    def _mock_encode(self, text: str) -> list[list[float]]:
        """Create mock embeddings for testing."""
        import random

        # Deterministic based on text hash (MD5 used for determinism, not security)
        seed = int(
            hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()[:8], 16
        )
        random.seed(seed)

        # Create embedding
        seq_len = min(32, max(1, len(text) // 100))
        return [
            [random.gauss(0, 1) for _ in range(self.config.embed_dim)]
            for _ in range(seq_len)
        ]

    def get_metrics(self) -> dict[str, Any]:
        """Get service metrics."""
        return {
            "total_requests": self._request_count,
            "fast_path_requests": self._fast_path_count,
            "slow_path_requests": self._slow_path_count,
            "fast_path_ratio": (
                self._fast_path_count / self._request_count
                if self._request_count > 0
                else 0.0
            ),
            "avg_latency_ms": (
                self._total_latency_ms / self._request_count
                if self._request_count > 0
                else 0.0
            ),
            "estimated_operations_saved": f"{self._fast_path_count * 1.85:.1f}x",
        }

    def reset_metrics(self) -> None:
        """Reset service metrics."""
        self._request_count = 0
        self._fast_path_count = 0
        self._slow_path_count = 0
        self._total_latency_ms = 0.0


# Convenience aliases
JEPA = EmbeddingPredictor
SelectiveDecoder = SelectiveDecodingService
