"""Pydantic models for GPU Scheduler service.

Implements strictly-typed job configurations per ADR-061 to prevent
injection attacks via untyped dict configurations.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator


class GPUJobType(str, Enum):
    """Types of GPU workloads supported by the scheduler."""

    EMBEDDING_GENERATION = "embedding_generation"
    LOCAL_INFERENCE = "local_inference"
    VULNERABILITY_TRAINING = "vulnerability_training"
    SWE_RL_TRAINING = "swe_rl_training"
    MEMORY_CONSOLIDATION = "memory_consolidation"


class GPUJobStatus(str, Enum):
    """Status of a GPU job in its lifecycle."""

    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GPUJobPriority(str, Enum):
    """Priority levels for GPU job scheduling."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class GPUJobErrorType(str, Enum):
    """Types of errors that can occur during GPU job execution."""

    OOM = "oom"
    SPOT_INTERRUPTION = "spot_interruption"
    TIMEOUT = "timeout"
    CONFIG_ERROR = "config_error"
    NETWORK_ERROR = "network_error"


# =============================================================================
# Strictly Typed Job Configurations (per ADR-061 security requirements)
# =============================================================================


class EmbeddingJobConfig(BaseModel):
    """Configuration for code embedding generation jobs."""

    repository_id: str = Field(..., description="ID of the repository to embed")
    branch: str = Field(default="main", description="Git branch to process")
    model: Literal["codebert-base", "codebert-large", "starencoder"] = Field(
        default="codebert-base",
        description="Embedding model to use",
    )
    batch_size: int = Field(
        default=32,
        ge=1,
        le=128,
        description="Batch size for embedding generation",
    )
    include_tests: bool = Field(
        default=False,
        description="Whether to include test files in embeddings",
    )

    @field_validator("repository_id")
    @classmethod
    def validate_repository_id(cls, v: str) -> str:
        """Validate repository ID format to prevent injection."""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Invalid repository ID format")
        return v

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, v: str) -> str:
        """Validate branch name format."""
        if not re.match(r"^[a-zA-Z0-9_/.-]+$", v):
            raise ValueError("Invalid branch name format")
        return v


class VulnerabilityTrainingConfig(BaseModel):
    """Configuration for vulnerability classifier training jobs."""

    dataset_id: str = Field(..., description="ID of the training dataset")
    epochs: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of training epochs",
    )
    batch_size: int = Field(
        default=32,
        ge=1,
        le=256,
        description="Training batch size",
    )
    learning_rate: float = Field(
        default=0.0001,
        gt=0,
        le=0.1,
        description="Learning rate for optimizer",
    )
    early_stopping_patience: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Early stopping patience epochs",
    )

    @field_validator("dataset_id")
    @classmethod
    def validate_dataset_id(cls, v: str) -> str:
        """Validate dataset ID format."""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Invalid dataset ID format")
        return v


class SWERLTrainingConfig(BaseModel):
    """Configuration for Self-Play SWE-RL training jobs (ADR-050)."""

    batch_id: str = Field(..., description="ID of the training batch")
    max_epochs: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum training epochs",
    )
    checkpoint_interval_minutes: int = Field(
        default=15,
        ge=5,
        le=60,
        description="Checkpoint save interval in minutes",
    )
    reward_scale: float = Field(
        default=1.0,
        gt=0,
        le=10.0,
        description="Reward scaling factor",
    )

    @field_validator("batch_id")
    @classmethod
    def validate_batch_id(cls, v: str) -> str:
        """Validate batch ID format."""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Invalid batch ID format")
        return v


class MemoryConsolidationConfig(BaseModel):
    """Configuration for Titan memory consolidation jobs (ADR-024)."""

    session_id: str = Field(..., description="ID of the memory session")
    retention_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Memory retention threshold (0-1)",
    )
    consolidation_strategy: Literal["full", "incremental", "selective"] = Field(
        default="incremental",
        description="Memory consolidation strategy",
    )

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        """Validate session ID format."""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Invalid session ID format")
        return v


class LocalInferenceConfig(BaseModel):
    """Configuration for local LLM inference jobs."""

    model_id: str = Field(..., description="ID of the model to run inference with")
    max_tokens: int = Field(
        default=2048,
        ge=1,
        le=32768,
        description="Maximum tokens for generation",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )

    @field_validator("model_id")
    @classmethod
    def validate_model_id(cls, v: str) -> str:
        """Validate model ID format."""
        if not re.match(r"^[a-zA-Z0-9_/-]+$", v):
            raise ValueError("Invalid model ID format")
        return v


# Union of all valid job configurations (discriminated union)
GPUJobConfig = Annotated[
    Union[
        EmbeddingJobConfig,
        VulnerabilityTrainingConfig,
        SWERLTrainingConfig,
        MemoryConsolidationConfig,
        LocalInferenceConfig,
    ],
    Field(discriminator=None),  # Use job_type field for discrimination
]


# =============================================================================
# Main Models
# =============================================================================


class GPUJobCreateRequest(BaseModel):
    """Request model for submitting a new GPU job."""

    job_type: GPUJobType = Field(..., description="Type of GPU workload")
    config: GPUJobConfig = Field(..., description="Job-specific configuration")
    priority: GPUJobPriority = Field(
        default=GPUJobPriority.NORMAL,
        description="Job priority level",
    )
    gpu_memory_gb: int = Field(
        default=8,
        ge=4,
        le=24,
        description="Required GPU memory in GB",
    )
    max_runtime_hours: int = Field(
        default=2,
        ge=1,
        le=24,
        description="Maximum job runtime in hours",
    )
    checkpoint_enabled: bool = Field(
        default=True,
        description="Enable checkpointing for recovery",
    )
    gpu_count: int = Field(
        default=1,
        ge=1,
        le=8,
        description="Number of GPUs required (1-8 for multi-GPU jobs)",
    )


class GPUJob(BaseModel):
    """Complete GPU job model with all metadata."""

    job_id: str = Field(..., description="Unique job identifier")
    organization_id: str = Field(..., description="Organization that owns the job")
    user_id: str = Field(..., description="User who submitted the job")
    job_type: GPUJobType = Field(..., description="Type of GPU workload")
    status: GPUJobStatus = Field(..., description="Current job status")
    priority: GPUJobPriority = Field(..., description="Job priority level")
    config: GPUJobConfig = Field(..., description="Job-specific configuration")
    gpu_memory_gb: int = Field(..., description="Required GPU memory in GB")
    max_runtime_hours: int = Field(..., description="Maximum runtime in hours")
    checkpoint_enabled: bool = Field(..., description="Checkpointing enabled")
    checkpoint_s3_path: str | None = Field(
        default=None,
        description="S3 path for checkpoints",
    )
    gpu_count: int = Field(
        default=1,
        ge=1,
        le=8,
        description="Number of GPUs for multi-GPU jobs",
    )
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: datetime | None = Field(
        default=None,
        description="Job start timestamp",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Job completion timestamp",
    )
    progress_percent: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Job progress percentage",
    )
    cost_usd: float | None = Field(
        default=None,
        ge=0,
        description="Accumulated cost in USD",
    )
    kubernetes_job_name: str | None = Field(
        default=None,
        description="Kubernetes job resource name",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if job failed",
    )
    error_type: GPUJobErrorType | None = Field(
        default=None,
        description="Type of error if job failed",
    )
    ttl: int | None = Field(
        default=None,
        description="TTL timestamp for DynamoDB auto-deletion",
    )

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        item = {
            "organization_id": self.organization_id,
            "job_id": self.job_id,
            "user_id": self.user_id,
            "job_type": self.job_type.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "config": self.config.model_dump(),
            "gpu_memory_gb": self.gpu_memory_gb,
            "max_runtime_hours": self.max_runtime_hours,
            "checkpoint_enabled": self.checkpoint_enabled,
            "gpu_count": self.gpu_count,
            "created_at": self.created_at.isoformat(),
            # Composite key for GSI (avoids hot partition on status alone)
            "org_status": f"{self.organization_id}#{self.status.value}",
        }
        if self.checkpoint_s3_path:
            item["checkpoint_s3_path"] = self.checkpoint_s3_path
        if self.started_at:
            item["started_at"] = self.started_at.isoformat()
        if self.completed_at:
            item["completed_at"] = self.completed_at.isoformat()
        if self.progress_percent is not None:
            item["progress_percent"] = self.progress_percent
        if self.cost_usd is not None:
            item["cost_usd"] = str(self.cost_usd)  # DynamoDB decimal handling
        if self.kubernetes_job_name:
            item["kubernetes_job_name"] = self.kubernetes_job_name
        if self.error_message:
            item["error_message"] = self.error_message
        if self.error_type:
            item["error_type"] = self.error_type.value
        if self.ttl is not None:
            item["ttl"] = self.ttl
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> GPUJob:
        """Create GPUJob from DynamoDB item."""
        # Parse config based on job_type
        job_type = GPUJobType(item["job_type"])
        config_data = item["config"]

        config: GPUJobConfig
        if job_type == GPUJobType.EMBEDDING_GENERATION:
            config = EmbeddingJobConfig(**config_data)
        elif job_type == GPUJobType.VULNERABILITY_TRAINING:
            config = VulnerabilityTrainingConfig(**config_data)
        elif job_type == GPUJobType.SWE_RL_TRAINING:
            config = SWERLTrainingConfig(**config_data)
        elif job_type == GPUJobType.MEMORY_CONSOLIDATION:
            config = MemoryConsolidationConfig(**config_data)
        elif job_type == GPUJobType.LOCAL_INFERENCE:
            config = LocalInferenceConfig(**config_data)
        else:
            raise ValueError(f"Unknown job type: {job_type}")

        return cls(
            job_id=item["job_id"],
            organization_id=item["organization_id"],
            user_id=item["user_id"],
            job_type=job_type,
            status=GPUJobStatus(item["status"]),
            priority=GPUJobPriority(item["priority"]),
            config=config,
            gpu_memory_gb=item["gpu_memory_gb"],
            max_runtime_hours=item["max_runtime_hours"],
            checkpoint_enabled=item["checkpoint_enabled"],
            checkpoint_s3_path=item.get("checkpoint_s3_path"),
            gpu_count=item.get("gpu_count", 1),
            created_at=datetime.fromisoformat(item["created_at"]),
            started_at=(
                datetime.fromisoformat(item["started_at"])
                if item.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(item["completed_at"])
                if item.get("completed_at")
                else None
            ),
            progress_percent=item.get("progress_percent"),
            cost_usd=float(item["cost_usd"]) if item.get("cost_usd") else None,
            kubernetes_job_name=item.get("kubernetes_job_name"),
            error_message=item.get("error_message"),
            error_type=(
                GPUJobErrorType(item["error_type"]) if item.get("error_type") else None
            ),
            ttl=item.get("ttl"),
        )


class GPUQuota(BaseModel):
    """GPU quota configuration for an organization."""

    organization_id: str = Field(..., description="Organization ID")
    max_concurrent_jobs: int = Field(
        default=4,
        ge=1,
        le=100,
        description="Maximum concurrent GPU jobs",
    )
    max_gpu_hours_monthly: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum GPU hours per month",
    )
    max_job_runtime_hours: int = Field(
        default=8,
        ge=1,
        le=72,
        description="Maximum runtime per job in hours",
    )
    current_concurrent_jobs: int = Field(
        default=0,
        ge=0,
        description="Current number of running jobs",
    )
    current_month_gpu_hours: float = Field(
        default=0.0,
        ge=0,
        description="GPU hours used this month",
    )

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        return {
            "organization_id": self.organization_id,
            "quota_type": "QUOTA",
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "max_gpu_hours_monthly": self.max_gpu_hours_monthly,
            "max_job_runtime_hours": self.max_job_runtime_hours,
            "current_concurrent_jobs": self.current_concurrent_jobs,
            "current_month_gpu_hours": str(self.current_month_gpu_hours),
        }

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> GPUQuota:
        """Create GPUQuota from DynamoDB item."""
        return cls(
            organization_id=item["organization_id"],
            max_concurrent_jobs=item.get("max_concurrent_jobs", 4),
            max_gpu_hours_monthly=item.get("max_gpu_hours_monthly", 100),
            max_job_runtime_hours=item.get("max_job_runtime_hours", 8),
            current_concurrent_jobs=item.get("current_concurrent_jobs", 0),
            current_month_gpu_hours=float(item.get("current_month_gpu_hours", "0.0")),
        )


class GPUResourceStatus(BaseModel):
    """Current GPU resource availability status."""

    gpus_available: int = Field(..., description="Number of GPUs currently available")
    gpus_total: int = Field(..., description="Total GPUs in cluster")
    gpus_in_use: int = Field(..., description="GPUs currently in use")
    queue_depth: int = Field(..., description="Number of jobs in queue")
    estimated_wait_minutes: int | None = Field(
        default=None,
        description="Estimated wait time for new jobs",
    )
    node_count: int = Field(..., description="Number of GPU nodes")
    scaling_status: Literal["stable", "scaling_up", "scaling_down"] = Field(
        default="stable",
        description="Cluster autoscaler status",
    )


# =============================================================================
# Phase 2: Queue Management Models (ADR-061)
# =============================================================================


class PreemptionReason(str, Enum):
    """Reasons a job may be preempted."""

    HIGH_PRIORITY_JOB = "high_priority_job"
    QUOTA_ENFORCEMENT = "quota_enforcement"
    SPOT_INTERRUPTION = "spot_interruption"
    MANUAL_ADMIN = "manual_admin"


class QueuedJob(BaseModel):
    """Job in priority queue with scheduling metadata.

    Used by the queue engine for priority-based scheduling with
    fairness guarantees per ADR-061.
    """

    job_id: str = Field(..., description="Unique job identifier")
    organization_id: str = Field(..., description="Organization that owns the job")
    user_id: str = Field(..., description="User who submitted the job")
    priority: GPUJobPriority = Field(..., description="Job priority level")
    job_type: GPUJobType = Field(..., description="Type of GPU workload")
    gpu_memory_gb: int = Field(..., description="Required GPU memory in GB")
    submitted_at: datetime = Field(..., description="When job was submitted")
    queued_at: datetime = Field(..., description="When job entered queue")

    # Fairness tracking
    wait_time_seconds: float = Field(
        default=0.0,
        ge=0,
        description="Time spent waiting in queue",
    )
    starvation_promoted: bool = Field(
        default=False,
        description="Whether job was promoted due to starvation prevention",
    )
    promotion_time: datetime | None = Field(
        default=None,
        description="When job was promoted (if applicable)",
    )

    # Organization tracking for round-robin
    org_queue_position: int = Field(
        default=0,
        ge=0,
        description="Position among jobs from same organization",
    )

    def priority_key(self) -> tuple:
        """Return comparison key for priority queue ordering.

        Lower values = higher priority. Order:
        1. Priority level (HIGH=1, NORMAL=2, LOW=3)
        2. Starvation-promoted jobs first (False > True, so promoted=0)
        3. Earlier queued_at timestamp
        """
        priority_order = {
            GPUJobPriority.HIGH: 1,
            GPUJobPriority.NORMAL: 2,
            GPUJobPriority.LOW: 3,
        }
        return (
            priority_order[self.priority],
            0 if self.starvation_promoted else 1,
            self.queued_at.timestamp(),
        )

    def __lt__(self, other: "QueuedJob") -> bool:
        """Compare for priority queue ordering."""
        return self.priority_key() < other.priority_key()

    def __eq__(self, other: object) -> bool:
        """Check equality by job_id."""
        if not isinstance(other, QueuedJob):
            return NotImplemented
        return self.job_id == other.job_id

    def __hash__(self) -> int:
        """Hash by job_id for set operations."""
        return hash(self.job_id)

    @classmethod
    def from_gpu_job(
        cls, job: GPUJob, queued_at: datetime | None = None
    ) -> "QueuedJob":
        """Create QueuedJob from GPUJob."""
        from datetime import timezone

        now = datetime.now(timezone.utc)
        return cls(
            job_id=job.job_id,
            organization_id=job.organization_id,
            user_id=job.user_id,
            priority=job.priority,
            job_type=job.job_type,
            gpu_memory_gb=job.gpu_memory_gb,
            submitted_at=job.created_at,
            queued_at=queued_at or now,
        )


class PreemptionEvent(BaseModel):
    """Records a job preemption event for audit and recovery."""

    event_id: str = Field(..., description="Unique event identifier")
    preempted_job_id: str = Field(..., description="ID of job that was preempted")
    preempting_job_id: str = Field(
        ..., description="ID of job that triggered preemption"
    )
    organization_id: str = Field(..., description="Organization of preempted job")
    reason: PreemptionReason = Field(..., description="Reason for preemption")
    checkpoint_saved: bool = Field(
        default=False,
        description="Whether checkpoint was saved before preemption",
    )
    checkpoint_s3_path: str | None = Field(
        default=None,
        description="S3 path to saved checkpoint",
    )
    preempted_at: datetime = Field(..., description="When preemption occurred")
    re_queued: bool = Field(
        default=False,
        description="Whether preempted job was re-queued",
    )
    priority_boost_applied: bool = Field(
        default=False,
        description="Whether priority was boosted for re-queued job",
    )
    original_priority: GPUJobPriority | None = Field(
        default=None,
        description="Original priority before boost",
    )
    new_priority: GPUJobPriority | None = Field(
        default=None,
        description="New priority after boost",
    )


class QueueMetrics(BaseModel):
    """Real-time queue statistics for monitoring and UI."""

    total_queued: int = Field(..., ge=0, description="Total jobs in queue")
    by_priority: dict[str, int] = Field(
        ...,
        description="Job count by priority level",
    )
    by_organization: dict[str, int] = Field(
        default_factory=dict,
        description="Job count by organization",
    )
    running_jobs: int = Field(..., ge=0, description="Jobs currently running")
    running_by_priority: dict[str, int] = Field(
        default_factory=dict,
        description="Running jobs by priority level",
    )
    avg_wait_time_seconds: float = Field(
        default=0.0,
        ge=0,
        description="Average wait time in seconds",
    )
    oldest_queued_at: datetime | None = Field(
        default=None,
        description="Timestamp of oldest queued job",
    )
    estimated_drain_time_minutes: int = Field(
        default=0,
        ge=0,
        description="Estimated time to process all queued jobs",
    )
    preemptions_last_hour: int = Field(
        default=0,
        ge=0,
        description="Number of preemptions in the last hour",
    )
    starvation_promotions_last_hour: int = Field(
        default=0,
        ge=0,
        description="Number of starvation promotions in the last hour",
    )


class PositionEstimate(BaseModel):
    """Estimated queue position and wait time for a job."""

    job_id: str = Field(..., description="Job ID this estimate is for")
    queue_position: int = Field(..., ge=0, description="Current position in queue")
    jobs_ahead: int = Field(..., ge=0, description="Total jobs ahead")
    jobs_ahead_by_priority: dict[str, int] = Field(
        ...,
        description="Jobs ahead by priority level",
    )
    estimated_wait_minutes: int = Field(
        ...,
        ge=0,
        description="Estimated wait time in minutes",
    )
    estimated_start_time: datetime = Field(
        ...,
        description="Estimated job start time",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0-1) for this estimate",
    )
    factors: list[str] = Field(
        default_factory=list,
        description="Factors affecting the estimate",
    )
    gpu_scaling_required: bool = Field(
        default=False,
        description="Whether GPU scaling is needed",
    )
    preemption_possible: bool = Field(
        default=False,
        description="Whether this job might preempt another",
    )


# =============================================================================
# Phase 5: Advanced Features Models (ADR-061)
# =============================================================================


class ScheduleFrequency(str, Enum):
    """Frequency options for scheduled recurring jobs."""

    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"  # Uses cron expression


class ScheduledJobStatus(str, Enum):
    """Status of a scheduled recurring job."""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class StalledJobStatus(str, Enum):
    """Status classification for stalled jobs."""

    HEALTHY = "healthy"
    WARNING = "warning"  # No progress for 5+ minutes
    STALLED = "stalled"  # No progress for 15+ minutes
    CRITICAL = "critical"  # No progress for 30+ minutes


class GPUJobTemplate(BaseModel):
    """Saved job configuration template for reuse."""

    template_id: str = Field(..., description="Unique template identifier")
    organization_id: str = Field(..., description="Organization that owns the template")
    user_id: str = Field(..., description="User who created the template")
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable template name",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional description of the template",
    )
    job_type: GPUJobType = Field(..., description="Type of GPU workload")
    config: GPUJobConfig = Field(..., description="Job-specific configuration")
    priority: GPUJobPriority = Field(
        default=GPUJobPriority.NORMAL,
        description="Default priority level",
    )
    gpu_memory_gb: int = Field(
        default=8,
        ge=4,
        le=24,
        description="Default GPU memory in GB",
    )
    gpu_count: int = Field(
        default=1,
        ge=1,
        le=8,
        description="Number of GPUs required",
    )
    max_runtime_hours: int = Field(
        default=2,
        ge=1,
        le=24,
        description="Default maximum runtime in hours",
    )
    checkpoint_enabled: bool = Field(
        default=True,
        description="Enable checkpointing by default",
    )
    is_public: bool = Field(
        default=False,
        description="Whether template is shared organization-wide",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for categorization and search",
    )
    use_count: int = Field(
        default=0,
        ge=0,
        description="Number of times template has been used",
    )
    created_at: datetime = Field(..., description="Template creation timestamp")
    updated_at: datetime | None = Field(
        default=None,
        description="Last update timestamp",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate template name format."""
        if not re.match(r"^[a-zA-Z0-9_\- ]+$", v):
            raise ValueError("Template name contains invalid characters")
        return v.strip()

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Validate and normalize tags."""
        return [tag.lower().strip() for tag in v if tag.strip()][:10]

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        item = {
            "organization_id": self.organization_id,
            "template_id": self.template_id,
            "user_id": self.user_id,
            "name": self.name,
            "job_type": self.job_type.value,
            "config": self.config.model_dump(),
            "priority": self.priority.value,
            "gpu_memory_gb": self.gpu_memory_gb,
            "gpu_count": self.gpu_count,
            "max_runtime_hours": self.max_runtime_hours,
            "checkpoint_enabled": self.checkpoint_enabled,
            "is_public": self.is_public,
            "tags": self.tags,
            "use_count": self.use_count,
            "created_at": self.created_at.isoformat(),
        }
        if self.description:
            item["description"] = self.description
        if self.updated_at:
            item["updated_at"] = self.updated_at.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "GPUJobTemplate":
        """Create GPUJobTemplate from DynamoDB item."""
        job_type = GPUJobType(item["job_type"])
        config_data = item["config"]

        config: GPUJobConfig
        if job_type == GPUJobType.EMBEDDING_GENERATION:
            config = EmbeddingJobConfig(**config_data)
        elif job_type == GPUJobType.VULNERABILITY_TRAINING:
            config = VulnerabilityTrainingConfig(**config_data)
        elif job_type == GPUJobType.SWE_RL_TRAINING:
            config = SWERLTrainingConfig(**config_data)
        elif job_type == GPUJobType.MEMORY_CONSOLIDATION:
            config = MemoryConsolidationConfig(**config_data)
        elif job_type == GPUJobType.LOCAL_INFERENCE:
            config = LocalInferenceConfig(**config_data)
        else:
            raise ValueError(f"Unknown job type: {job_type}")

        return cls(
            template_id=item["template_id"],
            organization_id=item["organization_id"],
            user_id=item["user_id"],
            name=item["name"],
            description=item.get("description"),
            job_type=job_type,
            config=config,
            priority=GPUJobPriority(item.get("priority", "normal")),
            gpu_memory_gb=item.get("gpu_memory_gb", 8),
            gpu_count=item.get("gpu_count", 1),
            max_runtime_hours=item.get("max_runtime_hours", 2),
            checkpoint_enabled=item.get("checkpoint_enabled", True),
            is_public=item.get("is_public", False),
            tags=item.get("tags", []),
            use_count=item.get("use_count", 0),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=(
                datetime.fromisoformat(item["updated_at"])
                if item.get("updated_at")
                else None
            ),
        )


class GPUScheduledJob(BaseModel):
    """Scheduled recurring GPU job configuration."""

    schedule_id: str = Field(..., description="Unique schedule identifier")
    organization_id: str = Field(..., description="Organization that owns the schedule")
    user_id: str = Field(..., description="User who created the schedule")
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable schedule name",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional description",
    )

    # Job configuration (can reference template or inline)
    template_id: str | None = Field(
        default=None,
        description="Template ID to use (if not inline config)",
    )
    job_type: GPUJobType | None = Field(
        default=None,
        description="Job type (if inline config)",
    )
    config: GPUJobConfig | None = Field(
        default=None,
        description="Job config (if inline config)",
    )
    priority: GPUJobPriority = Field(
        default=GPUJobPriority.NORMAL,
        description="Priority for scheduled jobs",
    )
    gpu_memory_gb: int = Field(
        default=8,
        ge=4,
        le=24,
        description="GPU memory in GB",
    )
    gpu_count: int = Field(
        default=1,
        ge=1,
        le=8,
        description="Number of GPUs required",
    )
    max_runtime_hours: int = Field(
        default=2,
        ge=1,
        le=24,
        description="Maximum runtime in hours",
    )
    checkpoint_enabled: bool = Field(
        default=True,
        description="Enable checkpointing",
    )

    # Schedule configuration
    frequency: ScheduleFrequency = Field(
        ...,
        description="Schedule frequency",
    )
    cron_expression: str | None = Field(
        default=None,
        description="Cron expression for custom frequency",
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone for schedule",
    )
    start_date: datetime | None = Field(
        default=None,
        description="When to start scheduling (null = immediately)",
    )
    end_date: datetime | None = Field(
        default=None,
        description="When to stop scheduling (null = indefinite)",
    )

    # Status tracking
    status: ScheduledJobStatus = Field(
        default=ScheduledJobStatus.ACTIVE,
        description="Current schedule status",
    )
    last_run_at: datetime | None = Field(
        default=None,
        description="Last execution timestamp",
    )
    last_job_id: str | None = Field(
        default=None,
        description="ID of last submitted job",
    )
    next_run_at: datetime | None = Field(
        default=None,
        description="Next scheduled execution time",
    )
    run_count: int = Field(
        default=0,
        ge=0,
        description="Total number of executions",
    )
    failure_count: int = Field(
        default=0,
        ge=0,
        description="Number of failed executions",
    )
    consecutive_failures: int = Field(
        default=0,
        ge=0,
        description="Consecutive failures (auto-pause after 3)",
    )
    created_at: datetime = Field(..., description="Schedule creation timestamp")
    updated_at: datetime | None = Field(
        default=None,
        description="Last update timestamp",
    )

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str | None) -> str | None:
        """Validate cron expression format."""
        if v is None:
            return v
        # Basic cron validation (5 or 6 fields)
        parts = v.strip().split()
        if len(parts) not in (5, 6):
            raise ValueError("Invalid cron expression: must have 5 or 6 fields")
        return v.strip()

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone string."""
        import zoneinfo

        try:
            zoneinfo.ZoneInfo(v)
        except Exception:
            raise ValueError(f"Invalid timezone: {v}")
        return v

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        item = {
            "organization_id": self.organization_id,
            "schedule_id": self.schedule_id,
            "user_id": self.user_id,
            "name": self.name,
            "frequency": self.frequency.value,
            "timezone": self.timezone,
            "status": self.status.value,
            "priority": self.priority.value,
            "gpu_memory_gb": self.gpu_memory_gb,
            "gpu_count": self.gpu_count,
            "max_runtime_hours": self.max_runtime_hours,
            "checkpoint_enabled": self.checkpoint_enabled,
            "run_count": self.run_count,
            "failure_count": self.failure_count,
            "consecutive_failures": self.consecutive_failures,
            "created_at": self.created_at.isoformat(),
            # GSI for finding schedules due for execution
            "status_next_run": f"{self.status.value}#{self.next_run_at.isoformat() if self.next_run_at else '9999-12-31T23:59:59'}",
        }
        if self.description:
            item["description"] = self.description
        if self.template_id:
            item["template_id"] = self.template_id
        if self.job_type:
            item["job_type"] = self.job_type.value
        if self.config:
            item["config"] = self.config.model_dump()
        if self.cron_expression:
            item["cron_expression"] = self.cron_expression
        if self.start_date:
            item["start_date"] = self.start_date.isoformat()
        if self.end_date:
            item["end_date"] = self.end_date.isoformat()
        if self.last_run_at:
            item["last_run_at"] = self.last_run_at.isoformat()
        if self.last_job_id:
            item["last_job_id"] = self.last_job_id
        if self.next_run_at:
            item["next_run_at"] = self.next_run_at.isoformat()
        if self.updated_at:
            item["updated_at"] = self.updated_at.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "GPUScheduledJob":
        """Create GPUScheduledJob from DynamoDB item."""
        config = None
        if item.get("config") and item.get("job_type"):
            job_type = GPUJobType(item["job_type"])
            config_data = item["config"]
            if job_type == GPUJobType.EMBEDDING_GENERATION:
                config = EmbeddingJobConfig(**config_data)
            elif job_type == GPUJobType.VULNERABILITY_TRAINING:
                config = VulnerabilityTrainingConfig(**config_data)
            elif job_type == GPUJobType.SWE_RL_TRAINING:
                config = SWERLTrainingConfig(**config_data)
            elif job_type == GPUJobType.MEMORY_CONSOLIDATION:
                config = MemoryConsolidationConfig(**config_data)
            elif job_type == GPUJobType.LOCAL_INFERENCE:
                config = LocalInferenceConfig(**config_data)

        return cls(
            schedule_id=item["schedule_id"],
            organization_id=item["organization_id"],
            user_id=item["user_id"],
            name=item["name"],
            description=item.get("description"),
            template_id=item.get("template_id"),
            job_type=GPUJobType(item["job_type"]) if item.get("job_type") else None,
            config=config,
            priority=GPUJobPriority(item.get("priority", "normal")),
            gpu_memory_gb=item.get("gpu_memory_gb", 8),
            gpu_count=item.get("gpu_count", 1),
            max_runtime_hours=item.get("max_runtime_hours", 2),
            checkpoint_enabled=item.get("checkpoint_enabled", True),
            frequency=ScheduleFrequency(item["frequency"]),
            cron_expression=item.get("cron_expression"),
            timezone=item.get("timezone", "UTC"),
            start_date=(
                datetime.fromisoformat(item["start_date"])
                if item.get("start_date")
                else None
            ),
            end_date=(
                datetime.fromisoformat(item["end_date"])
                if item.get("end_date")
                else None
            ),
            status=ScheduledJobStatus(item.get("status", "active")),
            last_run_at=(
                datetime.fromisoformat(item["last_run_at"])
                if item.get("last_run_at")
                else None
            ),
            last_job_id=item.get("last_job_id"),
            next_run_at=(
                datetime.fromisoformat(item["next_run_at"])
                if item.get("next_run_at")
                else None
            ),
            run_count=item.get("run_count", 0),
            failure_count=item.get("failure_count", 0),
            consecutive_failures=item.get("consecutive_failures", 0),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=(
                datetime.fromisoformat(item["updated_at"])
                if item.get("updated_at")
                else None
            ),
        )


class StalledJobInfo(BaseModel):
    """Information about a potentially stalled job."""

    job_id: str = Field(..., description="Job identifier")
    organization_id: str = Field(..., description="Organization ID")
    user_id: str = Field(..., description="User who submitted the job")
    job_type: GPUJobType = Field(..., description="Type of GPU workload")
    status: StalledJobStatus = Field(..., description="Stalled status classification")
    progress_percent: int = Field(..., description="Last reported progress")
    last_progress_at: datetime | None = Field(
        default=None,
        description="When progress was last updated",
    )
    minutes_since_progress: float = Field(
        ...,
        ge=0,
        description="Minutes since last progress update",
    )
    started_at: datetime = Field(..., description="Job start time")
    expected_duration_minutes: int = Field(
        ...,
        ge=0,
        description="Expected job duration",
    )
    is_overdue: bool = Field(
        default=False,
        description="Whether job has exceeded expected duration",
    )
    alert_sent: bool = Field(
        default=False,
        description="Whether an alert has been sent",
    )
    alert_sent_at: datetime | None = Field(
        default=None,
        description="When alert was sent",
    )


class TemplateCreateRequest(BaseModel):
    """Request model for creating a job template."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Template name",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional description",
    )
    job_type: GPUJobType = Field(..., description="Type of GPU workload")
    config: GPUJobConfig = Field(..., description="Job configuration")
    priority: GPUJobPriority = Field(
        default=GPUJobPriority.NORMAL,
        description="Default priority",
    )
    gpu_memory_gb: int = Field(default=8, ge=4, le=24)
    gpu_count: int = Field(default=1, ge=1, le=8)
    max_runtime_hours: int = Field(default=2, ge=1, le=24)
    checkpoint_enabled: bool = Field(default=True)
    is_public: bool = Field(default=False)
    tags: list[str] = Field(default_factory=list)


class ScheduleCreateRequest(BaseModel):
    """Request model for creating a scheduled job."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Schedule name",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
    )
    template_id: str | None = Field(
        default=None,
        description="Template ID (mutually exclusive with inline config)",
    )
    job_type: GPUJobType | None = Field(
        default=None,
        description="Job type for inline config",
    )
    config: GPUJobConfig | None = Field(
        default=None,
        description="Inline job config",
    )
    priority: GPUJobPriority = Field(default=GPUJobPriority.NORMAL)
    gpu_memory_gb: int = Field(default=8, ge=4, le=24)
    gpu_count: int = Field(default=1, ge=1, le=8)
    max_runtime_hours: int = Field(default=2, ge=1, le=24)
    checkpoint_enabled: bool = Field(default=True)
    frequency: ScheduleFrequency = Field(...)
    cron_expression: str | None = Field(default=None)
    timezone: str = Field(default="UTC")
    start_date: datetime | None = Field(default=None)
    end_date: datetime | None = Field(default=None)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone string."""
        import zoneinfo

        try:
            zoneinfo.ZoneInfo(v)
        except Exception:
            raise ValueError(f"Invalid timezone: {v}")
        return v

    def validate_config(self) -> list[str]:
        """Validate that either template_id or inline config is provided."""
        errors = []
        if self.template_id is None and (self.job_type is None or self.config is None):
            errors.append("Either template_id or (job_type + config) must be provided")
        if self.template_id is not None and self.config is not None:
            errors.append("Cannot specify both template_id and inline config")
        if self.frequency == ScheduleFrequency.CUSTOM and not self.cron_expression:
            errors.append("cron_expression required for custom frequency")
        return errors
