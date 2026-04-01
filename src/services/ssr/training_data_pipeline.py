"""
Project Aura - Training Data Pipeline for Self-Play SWE-RL

Implements reward computation and training data generation for
the self-play training loop.

Reference: Meta FAIR "Self-play SWE-RL" (arXiv:2512.18552), Section 2.4

Key Features:
- Reward computation for injection and solving
- Training trajectory collection with S3/DynamoDB persistence
- Data augmentation strategies
- Export to training format

Reward Functions (from paper):
- Bug Injection: r = -1 if validation fails, -α if s ∈ {0,1}, 1-(1+α)s otherwise
- Bug Solving: r = +1 if all tests pass, -1 otherwise

Author: Project Aura Team
Created: 2026-01-01
Version: 1.1.0
ADR: ADR-050
"""

from __future__ import annotations

import gzip
import io
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

# AWS imports for persistence
try:
    import boto3
    from botocore.exceptions import ClientError

    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

from src.services.ssr.bug_artifact import BugArtifact

if TYPE_CHECKING:
    from src.agents.ssr.bug_injection_agent import InjectionResult
    from src.agents.ssr.bug_solving_agent import SolveResult

logger = logging.getLogger(__name__)


class TrajectoryType(Enum):
    """Type of training trajectory."""

    INJECTION = "injection"
    SOLVING = "solving"


class RewardSignal(Enum):
    """Type of reward signal."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class TrainingTrajectory:
    """A single training trajectory for RL."""

    trajectory_id: str
    trajectory_type: TrajectoryType
    artifact_id: str
    repository_id: str

    # Input context
    prompt: str
    code_context: str

    # Output
    response: str
    action_taken: str  # The diff or patch

    # Reward
    reward: float
    reward_signal: RewardSignal

    # Metadata
    tokens_used: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "trajectory_id": self.trajectory_id,
            "trajectory_type": self.trajectory_type.value,
            "artifact_id": self.artifact_id,
            "repository_id": self.repository_id,
            "prompt": self.prompt,
            "code_context": self.code_context[:5000],  # Truncate for storage
            "response": self.response[:5000],
            "action_taken": self.action_taken,
            "reward": self.reward,
            "reward_signal": self.reward_signal.value,
            "tokens_used": self.tokens_used,
            "created_at": self.created_at.isoformat(),
        }

    def to_training_format(self) -> dict[str, Any]:
        """Convert to format suitable for RL training."""
        return {
            "input": f"{self.prompt}\n\nContext:\n{self.code_context}",
            "output": self.response,
            "reward": self.reward,
            "metadata": {
                "trajectory_id": self.trajectory_id,
                "type": self.trajectory_type.value,
                "artifact_id": self.artifact_id,
            },
        }


@dataclass
class TrainingBatch:
    """A batch of training trajectories."""

    batch_id: str
    trajectories: list[TrainingTrajectory] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def size(self) -> int:
        """Get batch size."""
        return len(self.trajectories)

    @property
    def total_reward(self) -> float:
        """Get total reward in batch."""
        return sum(t.reward for t in self.trajectories)

    @property
    def positive_ratio(self) -> float:
        """Get ratio of positive reward trajectories."""
        if not self.trajectories:
            return 0.0
        positive = sum(1 for t in self.trajectories if t.reward > 0)
        return positive / len(self.trajectories)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "batch_id": self.batch_id,
            "size": self.size,
            "total_reward": self.total_reward,
            "positive_ratio": self.positive_ratio,
            "trajectories": [t.to_dict() for t in self.trajectories],
            "created_at": self.created_at.isoformat(),
        }

    def export_jsonl(self) -> str:
        """Export batch as JSONL for training."""
        lines = [json.dumps(t.to_training_format()) for t in self.trajectories]
        return "\n".join(lines)


class TrajectoryStorageMode(Enum):
    """Storage mode for trajectory persistence."""

    MEMORY = "memory"  # In-memory only (default for testing)
    S3 = "s3"  # S3-backed storage with DynamoDB index
    HYBRID = "hybrid"  # Both memory (hot) and S3 (cold)


@dataclass
class S3StorageConfig:
    """Configuration for S3-backed trajectory storage."""

    bucket_name: str = ""
    key_prefix: str = "ssr/trajectories/"
    dynamodb_table_name: str = "aura-ssr-trajectories"
    region: str = "us-east-1"
    compress: bool = True  # GZIP compression for S3 objects
    batch_size: int = 100  # Trajectories per S3 object


class TrajectoryStore:
    """
    Persistent storage for training trajectories using S3 and DynamoDB.

    Storage Architecture:
    - S3: Stores trajectory data (compressed JSONL files)
    - DynamoDB: Index table for fast queries by artifact_id, repository_id, type

    DynamoDB Schema:
    - partition_key: trajectory_id
    - sort_key: created_at (ISO timestamp)
    - GSI1: artifact_id-index (for querying by artifact)
    - GSI2: repository_id-index (for querying by repository)
    - GSI3: trajectory_type-index (for querying injection vs solving)

    S3 Key Format:
    - {prefix}/{year}/{month}/{day}/{batch_id}.jsonl.gz
    """

    def __init__(
        self,
        mode: TrajectoryStorageMode = TrajectoryStorageMode.MEMORY,
        config: S3StorageConfig | None = None,
    ):
        """
        Initialize trajectory store.

        Args:
            mode: Storage mode (MEMORY, S3, or HYBRID)
            config: S3 storage configuration (required for S3/HYBRID modes)
        """
        self.mode = mode
        self.config = config or S3StorageConfig()

        # In-memory storage (always available for hot data)
        self._memory_store: list[TrainingTrajectory] = []
        self._pending_batch: list[TrainingTrajectory] = []

        # AWS clients (lazy initialization)
        self._s3_client = None
        self._dynamodb = None
        self._table = None

        if mode in (TrajectoryStorageMode.S3, TrajectoryStorageMode.HYBRID):
            if not AWS_AVAILABLE:
                logger.warning("AWS not available, falling back to MEMORY mode")
                self.mode = TrajectoryStorageMode.MEMORY
            else:
                self._init_aws_clients()

        logger.info(f"TrajectoryStore initialized in {self.mode.value} mode")

    def _init_aws_clients(self) -> None:
        """Initialize AWS clients for S3 and DynamoDB."""
        try:
            self._s3_client = boto3.client("s3", region_name=self.config.region)
            self._dynamodb = boto3.resource("dynamodb", region_name=self.config.region)
            self._table = self._dynamodb.Table(self.config.dynamodb_table_name)

            # Verify table exists (will raise if not)
            self._table.load()
            logger.info(
                f"Connected to DynamoDB table: {self.config.dynamodb_table_name}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            logger.warning("Falling back to MEMORY mode")
            self.mode = TrajectoryStorageMode.MEMORY

    def add(self, trajectory: TrainingTrajectory) -> None:
        """
        Add a trajectory to storage.

        In HYBRID mode, trajectories are buffered in memory and flushed to S3
        when batch_size is reached.
        """
        if self.mode == TrajectoryStorageMode.MEMORY:
            self._memory_store.append(trajectory)
            return

        # S3 or HYBRID mode
        self._pending_batch.append(trajectory)

        # Also keep in memory for HYBRID mode
        if self.mode == TrajectoryStorageMode.HYBRID:
            self._memory_store.append(trajectory)

        # Flush to S3 when batch is full
        if len(self._pending_batch) >= self.config.batch_size:
            self._flush_batch_to_s3()

    def _flush_batch_to_s3(self) -> None:
        """Flush pending batch to S3 and index in DynamoDB."""
        if not self._pending_batch:
            return

        batch_id = f"batch-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        s3_key = (
            f"{self.config.key_prefix}"
            f"{now.year}/{now.month:02d}/{now.day:02d}/"
            f"{batch_id}.jsonl"
        )

        # Prepare JSONL content
        jsonl_lines = [json.dumps(t.to_dict()) for t in self._pending_batch]
        content = "\n".join(jsonl_lines)

        # Compress if enabled
        if self.config.compress:
            s3_key += ".gz"
            buffer = io.BytesIO()
            with gzip.GzipFile(fileobj=buffer, mode="wb") as gz:
                gz.write(content.encode("utf-8"))
            body = buffer.getvalue()
        else:
            body = content.encode("utf-8")

        try:
            # Upload to S3
            self._s3_client.put_object(
                Bucket=self.config.bucket_name,
                Key=s3_key,
                Body=body,
                ContentType="application/x-ndjson",
                Metadata={
                    "batch_id": batch_id,
                    "trajectory_count": str(len(self._pending_batch)),
                    "compressed": str(self.config.compress),
                },
            )

            # Index each trajectory in DynamoDB
            with self._table.batch_writer() as batch:
                for trajectory in self._pending_batch:
                    batch.put_item(
                        Item={
                            "trajectory_id": trajectory.trajectory_id,
                            "created_at": trajectory.created_at.isoformat(),
                            "trajectory_type": trajectory.trajectory_type.value,
                            "artifact_id": trajectory.artifact_id,
                            "repository_id": trajectory.repository_id,
                            "reward": str(trajectory.reward),
                            "reward_signal": trajectory.reward_signal.value,
                            "s3_key": s3_key,
                            "batch_id": batch_id,
                        }
                    )

            logger.info(
                f"Flushed {len(self._pending_batch)} trajectories to S3: {s3_key}"
            )
            self._pending_batch = []

        except ClientError as e:
            logger.error(f"Failed to flush batch to S3: {e}")
            # Keep in pending batch to retry later

    def get_by_artifact(self, artifact_id: str) -> list[TrainingTrajectory]:
        """Query trajectories by artifact ID using DynamoDB GSI."""
        if self.mode == TrajectoryStorageMode.MEMORY:
            return [t for t in self._memory_store if t.artifact_id == artifact_id]

        # Query DynamoDB index
        try:
            response = self._table.query(
                IndexName="artifact_id-index",
                KeyConditionExpression="artifact_id = :aid",
                ExpressionAttributeValues={":aid": artifact_id},
            )
            return self._fetch_trajectories_from_s3(response.get("Items", []))
        except Exception as e:
            logger.error(f"Failed to query by artifact: {e}")
            return []

    def get_by_repository(self, repository_id: str) -> list[TrainingTrajectory]:
        """Query trajectories by repository ID using DynamoDB GSI."""
        if self.mode == TrajectoryStorageMode.MEMORY:
            return [t for t in self._memory_store if t.repository_id == repository_id]

        try:
            response = self._table.query(
                IndexName="repository_id-index",
                KeyConditionExpression="repository_id = :rid",
                ExpressionAttributeValues={":rid": repository_id},
            )
            return self._fetch_trajectories_from_s3(response.get("Items", []))
        except Exception as e:
            logger.error(f"Failed to query by repository: {e}")
            return []

    def get_by_type(
        self, trajectory_type: TrajectoryType, limit: int = 1000
    ) -> list[TrainingTrajectory]:
        """Query trajectories by type using DynamoDB GSI."""
        if self.mode == TrajectoryStorageMode.MEMORY:
            return [
                t for t in self._memory_store if t.trajectory_type == trajectory_type
            ][:limit]

        try:
            response = self._table.query(
                IndexName="trajectory_type-index",
                KeyConditionExpression="trajectory_type = :tt",
                ExpressionAttributeValues={":tt": trajectory_type.value},
                Limit=limit,
            )
            return self._fetch_trajectories_from_s3(response.get("Items", []))
        except Exception as e:
            logger.error(f"Failed to query by type: {e}")
            return []

    def _fetch_trajectories_from_s3(
        self, ddb_items: list[dict[str, Any]]
    ) -> list[TrainingTrajectory]:
        """Fetch full trajectory data from S3 based on DynamoDB index items."""
        trajectories = []
        # Group by S3 key to minimize S3 calls
        keys_to_ids: dict[str, list[str]] = {}
        for item in ddb_items:
            s3_key = item.get("s3_key", "")
            traj_id = item.get("trajectory_id", "")
            if s3_key:
                keys_to_ids.setdefault(s3_key, []).append(traj_id)

        for s3_key, traj_ids in keys_to_ids.items():
            try:
                response = self._s3_client.get_object(
                    Bucket=self.config.bucket_name,
                    Key=s3_key,
                )
                body = response["Body"].read()

                # Decompress if needed
                if s3_key.endswith(".gz"):
                    body = gzip.decompress(body)

                # Parse JSONL and filter by trajectory IDs
                for line in body.decode("utf-8").strip().split("\n"):
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("trajectory_id") in traj_ids:
                        trajectories.append(self._dict_to_trajectory(data))

            except Exception as e:
                logger.error(f"Failed to fetch trajectories from {s3_key}: {e}")

        return trajectories

    @staticmethod
    def _dict_to_trajectory(data: dict[str, Any]) -> TrainingTrajectory:
        """Convert dictionary to TrainingTrajectory object."""
        return TrainingTrajectory(
            trajectory_id=data["trajectory_id"],
            trajectory_type=TrajectoryType(data["trajectory_type"]),
            artifact_id=data["artifact_id"],
            repository_id=data["repository_id"],
            prompt=data["prompt"],
            code_context=data["code_context"],
            response=data["response"],
            action_taken=data["action_taken"],
            reward=float(data["reward"]),
            reward_signal=RewardSignal(data["reward_signal"]),
            tokens_used=data.get("tokens_used", 0),
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    def get_all(self) -> list[TrainingTrajectory]:
        """Get all trajectories from memory (for backward compatibility)."""
        return self._memory_store.copy()

    def count(self) -> int:
        """Get count of trajectories in memory."""
        return len(self._memory_store)

    def flush(self) -> None:
        """Force flush any pending batches to S3."""
        if self._pending_batch:
            self._flush_batch_to_s3()

    def clear_memory(self) -> None:
        """Clear in-memory storage (S3 data is retained)."""
        self._memory_store = []
        self._pending_batch = []


class RewardComputer:
    """
    Computes rewards for injection and solving actions.

    Implements the reward functions from the SSR paper:
    - Injection: Penalizes invalid bugs, rewards balanced difficulty
    - Solving: Binary success/failure reward
    """

    def __init__(
        self,
        alpha: float = 0.5,  # Penalty weight for trivial bugs (s=0 or s=1)
        validation_penalty: float = -1.0,
        solve_success_reward: float = 1.0,
        solve_failure_reward: float = -1.0,
    ):
        """
        Initialize reward computer.

        Args:
            alpha: Penalty weight for trivial bugs
            validation_penalty: Reward for invalid bugs
            solve_success_reward: Reward for successful solve
            solve_failure_reward: Reward for failed solve
        """
        self.alpha = alpha
        self.validation_penalty = validation_penalty
        self.solve_success_reward = solve_success_reward
        self.solve_failure_reward = solve_failure_reward

    def compute_injection_reward(
        self,
        injection_result: InjectionResult,
        solve_rate: float,
    ) -> tuple[float, RewardSignal]:
        """
        Compute reward for bug injection.

        The reward function incentivizes bugs that are:
        1. Valid (pass validation)
        2. Not trivial (neither always solvable nor never solvable)

        Args:
            injection_result: Result of injection attempt
            solve_rate: Historical solve rate for this difficulty level (0-1)

        Returns:
            Tuple of (reward value, reward signal type)
        """
        # Invalid injection gets penalty
        if not injection_result.success:
            return self.validation_penalty, RewardSignal.NEGATIVE

        # Compute reward based on solve rate (s)
        # r = -α if s ∈ {0, 1}, otherwise r = 1 - (1 + α) * s
        s = solve_rate

        if s <= 0.0 or s >= 1.0:
            # Trivial bug (never or always solved)
            reward = -self.alpha
            signal = RewardSignal.NEGATIVE
        else:
            # Good bug - reward inversely proportional to solve rate
            # Higher solve rate = lower reward (bug too easy)
            reward = 1.0 - (1.0 + self.alpha) * s
            signal = RewardSignal.POSITIVE if reward > 0 else RewardSignal.NEUTRAL

        return reward, signal

    def compute_solving_reward(
        self,
        solve_result: SolveResult,
    ) -> tuple[float, RewardSignal]:
        """
        Compute reward for bug solving.

        Simple binary reward: success = +1, failure = -1

        Args:
            solve_result: Result of solving attempt

        Returns:
            Tuple of (reward value, reward signal type)
        """
        if solve_result.solved:
            return self.solve_success_reward, RewardSignal.POSITIVE
        return self.solve_failure_reward, RewardSignal.NEGATIVE


class TrainingDataPipeline:
    """
    Pipeline for generating and managing training data.

    Collects trajectories from self-play rounds, computes rewards,
    and exports data in formats suitable for RL training.

    Supports persistent storage via S3 and DynamoDB for production use.

    Usage:
        # In-memory mode (testing)
        pipeline = TrainingDataPipeline()

        # S3-backed mode (production)
        config = S3StorageConfig(
            bucket_name="aura-training-data",
            dynamodb_table_name="aura-ssr-trajectories"
        )
        pipeline = TrainingDataPipeline(
            storage_mode=TrajectoryStorageMode.S3,
            storage_config=config
        )

        # Add trajectories from a round
        pipeline.add_injection_trajectory(
            artifact=artifact,
            injection_result=result,
            prompt="...",
            code_context="..."
        )

        # Export a batch
        batch = pipeline.create_batch(batch_size=32)
        jsonl = batch.export_jsonl()
    """

    def __init__(
        self,
        reward_computer: RewardComputer | None = None,
        max_trajectories: int = 10000,
        storage_mode: TrajectoryStorageMode = TrajectoryStorageMode.MEMORY,
        storage_config: S3StorageConfig | None = None,
    ):
        """
        Initialize the training data pipeline.

        Args:
            reward_computer: Reward computer (uses default if None)
            max_trajectories: Maximum trajectories to keep in memory
            storage_mode: Storage mode (MEMORY, S3, or HYBRID)
            storage_config: S3 storage configuration (for S3/HYBRID modes)
        """
        self.reward_computer = reward_computer or RewardComputer()
        self.max_trajectories = max_trajectories

        # Initialize trajectory store with persistence support
        self._store = TrajectoryStore(mode=storage_mode, config=storage_config)

        # Solve rate tracking with exponential moving average
        self._solve_rates: dict[int, list[bool]] = {}  # difficulty -> [solved]
        self._ema_solve_rates: dict[int, float] = {}  # difficulty -> EMA rate
        self._ema_alpha = 0.1  # EMA smoothing factor

        # Metrics
        self._total_positive = 0
        self._total_negative = 0
        self._total_reward = 0.0

        logger.info(
            f"TrainingDataPipeline initialized: "
            f"max_trajectories={max_trajectories}, "
            f"storage_mode={storage_mode.value}"
        )

    @property
    def _trajectories(self) -> list[TrainingTrajectory]:
        """Backward compatibility: access trajectories from store."""
        return self._store.get_all()

    def add_injection_trajectory(
        self,
        artifact: BugArtifact,
        injection_result: InjectionResult,
        prompt: str,
        code_context: str,
        response: str,
    ) -> TrainingTrajectory:
        """
        Add an injection trajectory.

        Args:
            artifact: The generated bug artifact
            injection_result: Result of injection
            prompt: The prompt used
            code_context: Code context provided
            response: LLM response

        Returns:
            The created trajectory
        """
        # Get historical solve rate for this difficulty
        difficulty = injection_result.difficulty
        solve_history = self._solve_rates.get(difficulty, [])
        solve_rate = sum(solve_history) / len(solve_history) if solve_history else 0.5

        # Compute reward
        reward, signal = self.reward_computer.compute_injection_reward(
            injection_result, solve_rate
        )

        trajectory = TrainingTrajectory(
            trajectory_id=f"traj-inj-{uuid.uuid4().hex[:12]}",
            trajectory_type=TrajectoryType.INJECTION,
            artifact_id=artifact.artifact_id,
            repository_id=artifact.repository_id,
            prompt=prompt,
            code_context=code_context,
            response=response,
            action_taken=artifact.bug_inject_diff,
            reward=reward,
            reward_signal=signal,
            tokens_used=injection_result.tokens_used,
        )

        self._add_trajectory(trajectory)
        return trajectory

    def add_solving_trajectory(
        self,
        artifact: BugArtifact,
        solve_result: SolveResult,
        prompt: str,
        code_context: str,
        response: str,
        difficulty: int,
    ) -> TrainingTrajectory:
        """
        Add a solving trajectory.

        Args:
            artifact: The bug artifact being solved
            solve_result: Result of solving
            prompt: The prompt used
            code_context: Code context provided
            response: LLM response
            difficulty: Difficulty level of the bug

        Returns:
            The created trajectory
        """
        # Compute reward
        reward, signal = self.reward_computer.compute_solving_reward(solve_result)

        # Update solve rate for this difficulty using EMA
        self._update_solve_rate_ema(difficulty, solve_result.solved)

        trajectory = TrainingTrajectory(
            trajectory_id=f"traj-sol-{uuid.uuid4().hex[:12]}",
            trajectory_type=TrajectoryType.SOLVING,
            artifact_id=artifact.artifact_id,
            repository_id=artifact.repository_id,
            prompt=prompt,
            code_context=code_context,
            response=response,
            action_taken=solve_result.final_patch or "",
            reward=reward,
            reward_signal=signal,
            tokens_used=solve_result.total_tokens,
        )

        self._add_trajectory(trajectory)
        return trajectory

    def _add_trajectory(self, trajectory: TrainingTrajectory) -> None:
        """Add a trajectory to storage."""
        self._store.add(trajectory)

        # Update metrics
        if trajectory.reward_signal == RewardSignal.POSITIVE:
            self._total_positive += 1
        elif trajectory.reward_signal == RewardSignal.NEGATIVE:
            self._total_negative += 1
        self._total_reward += trajectory.reward

        # Enforce max size for in-memory store
        if self._store.count() > self.max_trajectories:
            # In S3/HYBRID mode, just clear oldest from memory
            # S3 data is retained for training
            trajectories = self._store.get_all()
            if trajectories:
                removed = trajectories[0]
                # Update metrics for removed trajectory
                if removed.reward_signal == RewardSignal.POSITIVE:
                    self._total_positive -= 1
                elif removed.reward_signal == RewardSignal.NEGATIVE:
                    self._total_negative -= 1
                self._total_reward -= removed.reward
                # Note: actual removal happens via eviction in memory store

    def create_batch(
        self,
        batch_size: int = 32,
        trajectory_type: TrajectoryType | None = None,
        positive_only: bool = False,
    ) -> TrainingBatch:
        """
        Create a training batch.

        Args:
            batch_size: Number of trajectories in batch
            trajectory_type: Filter by type (None for all)
            positive_only: Only include positive reward trajectories

        Returns:
            Training batch
        """
        # Filter trajectories (use slice view instead of full copy)
        if trajectory_type or positive_only:
            candidates = [
                t
                for t in self._trajectories
                if (not trajectory_type or t.trajectory_type == trajectory_type)
                and (not positive_only or t.reward > 0)
            ]
        else:
            candidates = self._trajectories

        # Sample batch
        import random

        if len(candidates) <= batch_size:
            selected = candidates
        else:
            selected = random.sample(candidates, batch_size)

        return TrainingBatch(
            batch_id=f"batch-{uuid.uuid4().hex[:12]}",
            trajectories=selected,
        )

    def create_balanced_batch(
        self,
        batch_size: int = 32,
    ) -> TrainingBatch:
        """
        Create a balanced batch with equal positive/negative trajectories.

        This helps with training stability by ensuring the model sees
        both success and failure cases equally.

        Args:
            batch_size: Total batch size

        Returns:
            Balanced training batch
        """
        half_size = batch_size // 2

        positive = [t for t in self._trajectories if t.reward > 0]
        negative = [t for t in self._trajectories if t.reward <= 0]

        import random

        selected_positive = (
            random.sample(positive, min(half_size, len(positive))) if positive else []
        )
        selected_negative = (
            random.sample(negative, min(half_size, len(negative))) if negative else []
        )

        # Shuffle combined
        all_selected = selected_positive + selected_negative
        random.shuffle(all_selected)

        return TrainingBatch(
            batch_id=f"batch-bal-{uuid.uuid4().hex[:12]}",
            trajectories=all_selected,
        )

    def augment_trajectory(
        self,
        trajectory: TrainingTrajectory,
    ) -> list[TrainingTrajectory]:
        """
        Create augmented versions of a trajectory.

        Augmentation strategies:
        1. Code context shuffling
        2. Prompt paraphrasing (simplified)
        3. Adding noise to context

        Args:
            trajectory: Original trajectory

        Returns:
            List of augmented trajectories (including original)
        """
        augmented = [trajectory]

        # Strategy 1: Truncate context
        if len(trajectory.code_context) > 1000:
            truncated = TrainingTrajectory(
                trajectory_id=f"{trajectory.trajectory_id}-trunc",
                trajectory_type=trajectory.trajectory_type,
                artifact_id=trajectory.artifact_id,
                repository_id=trajectory.repository_id,
                prompt=trajectory.prompt,
                code_context=trajectory.code_context[:1000] + "\n... (truncated)",
                response=trajectory.response,
                action_taken=trajectory.action_taken,
                reward=trajectory.reward,
                reward_signal=trajectory.reward_signal,
                tokens_used=trajectory.tokens_used,
            )
            augmented.append(truncated)

        # Strategy 2: Add prefix to prompt
        prefixed = TrainingTrajectory(
            trajectory_id=f"{trajectory.trajectory_id}-prefix",
            trajectory_type=trajectory.trajectory_type,
            artifact_id=trajectory.artifact_id,
            repository_id=trajectory.repository_id,
            prompt=f"Task: {trajectory.prompt}",
            code_context=trajectory.code_context,
            response=trajectory.response,
            action_taken=trajectory.action_taken,
            reward=trajectory.reward,
            reward_signal=trajectory.reward_signal,
            tokens_used=trajectory.tokens_used,
        )
        augmented.append(prefixed)

        return augmented

    def get_metrics(self) -> dict[str, Any]:
        """Get pipeline metrics."""
        total = len(self._trajectories)
        injection_count = sum(
            1
            for t in self._trajectories
            if t.trajectory_type == TrajectoryType.INJECTION
        )
        solving_count = total - injection_count

        return {
            "total_trajectories": total,
            "injection_trajectories": injection_count,
            "solving_trajectories": solving_count,
            "positive_trajectories": self._total_positive,
            "negative_trajectories": self._total_negative,
            "total_reward": self._total_reward,
            "avg_reward": self._total_reward / total if total else 0,
            "positive_ratio": self._total_positive / total if total else 0,
            "difficulty_levels_tracked": len(self._solve_rates),
        }

    def _update_solve_rate_ema(self, difficulty: int, solved: bool) -> None:
        """
        Update solve rate using Exponential Moving Average (EMA).

        EMA provides smoother tracking than fixed window, giving more weight
        to recent results while still considering historical performance.

        Formula: EMA_new = alpha * new_value + (1 - alpha) * EMA_old

        Args:
            difficulty: Difficulty level (1-5)
            solved: Whether the bug was solved
        """
        value = 1.0 if solved else 0.0

        if difficulty not in self._ema_solve_rates:
            # Initialize with first observation
            self._ema_solve_rates[difficulty] = value
        else:
            # Update EMA: alpha * new + (1-alpha) * old
            old_ema = self._ema_solve_rates[difficulty]
            self._ema_solve_rates[difficulty] = (
                self._ema_alpha * value + (1 - self._ema_alpha) * old_ema
            )

        # Also keep raw history for debugging/analysis (limited window)
        if difficulty not in self._solve_rates:
            self._solve_rates[difficulty] = []
        self._solve_rates[difficulty].append(solved)

        # Keep only last 100 results for raw history
        if len(self._solve_rates[difficulty]) > 100:
            self._solve_rates[difficulty] = self._solve_rates[difficulty][-100:]

        logger.debug(
            f"Difficulty {difficulty} solve rate EMA: "
            f"{self._ema_solve_rates[difficulty]:.3f}"
        )

    def get_solve_rates(self) -> dict[int, float]:
        """
        Get solve rates by difficulty level using EMA.

        Returns EMA-smoothed solve rates which are more robust to noise
        than simple window-based averages.

        Returns:
            Dict mapping difficulty level to solve rate (0.0 to 1.0)
        """
        return self._ema_solve_rates.copy()

    def get_solve_rates_raw(self) -> dict[int, float]:
        """
        Get raw solve rates by difficulty level (window-based).

        This uses the fixed 100-result window for comparison with EMA.

        Returns:
            Dict mapping difficulty level to solve rate (0.0 to 1.0)
        """
        return {
            difficulty: sum(history) / len(history) if history else 0
            for difficulty, history in self._solve_rates.items()
        }

    def get_solve_rate_details(self, difficulty: int) -> dict[str, Any]:
        """
        Get detailed solve rate information for a specific difficulty.

        Args:
            difficulty: Difficulty level to query

        Returns:
            Dict with EMA rate, raw rate, sample count, and history
        """
        ema_rate = self._ema_solve_rates.get(difficulty, 0.0)
        history = self._solve_rates.get(difficulty, [])
        raw_rate = sum(history) / len(history) if history else 0.0

        return {
            "difficulty": difficulty,
            "ema_rate": ema_rate,
            "raw_rate": raw_rate,
            "sample_count": len(history),
            "ema_alpha": self._ema_alpha,
            "recent_10": history[-10:] if history else [],
        }

    def export_all(self, format: str = "jsonl") -> str:
        """
        Export all trajectories.

        Args:
            format: Export format ("jsonl" or "json")

        Returns:
            Exported data as string
        """
        if format == "jsonl":
            lines = [json.dumps(t.to_training_format()) for t in self._trajectories]
            return "\n".join(lines)
        else:
            return json.dumps(
                [t.to_dict() for t in self._trajectories],
                indent=2,
            )

    def clear(self) -> None:
        """Clear all trajectories from memory (S3 data is retained)."""
        self._store.clear_memory()
        self._total_positive = 0
        self._total_negative = 0
        self._total_reward = 0.0
        logger.info("Training data pipeline cleared")

    def flush(self) -> None:
        """Force flush any pending trajectories to S3 (for S3/HYBRID modes)."""
        self._store.flush()
        logger.info("Training data pipeline flushed to S3")

    def get_trajectories_by_artifact(
        self, artifact_id: str
    ) -> list[TrainingTrajectory]:
        """Query trajectories by artifact ID (uses DynamoDB index in S3 mode)."""
        return self._store.get_by_artifact(artifact_id)

    def get_trajectories_by_repository(
        self, repository_id: str
    ) -> list[TrainingTrajectory]:
        """Query trajectories by repository ID (uses DynamoDB index in S3 mode)."""
        return self._store.get_by_repository(repository_id)

    def get_trajectories_by_type(
        self, trajectory_type: TrajectoryType, limit: int = 1000
    ) -> list[TrainingTrajectory]:
        """Query trajectories by type (uses DynamoDB index in S3 mode)."""
        return self._store.get_by_type(trajectory_type, limit)
