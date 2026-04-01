"""GPU Workload Scheduler Service.

This module provides self-service GPU workload scheduling capabilities
for embedding generation, model training, and ML inference jobs.

Implements ADR-061: GPU Workload Scheduler.
"""

from src.services.gpu_scheduler.exceptions import (
    GPUJobNotFoundError,
    GPUSchedulerError,
    InvalidJobConfigError,
    JobCancellationError,
    PreemptionError,
    QueueDispatchError,
    QueueFullError,
    QuotaExceededError,
    StarvationPromotionError,
)
from src.services.gpu_scheduler.gpu_scheduler_service import GPUSchedulerService
from src.services.gpu_scheduler.models import (
    EmbeddingJobConfig,
    GPUJob,
    GPUJobConfig,
    GPUJobCreateRequest,
    GPUJobErrorType,
    GPUJobPriority,
    GPUJobStatus,
    GPUJobType,
    GPUQuota,
    GPUResourceStatus,
    MemoryConsolidationConfig,
    PositionEstimate,
    PreemptionEvent,
    PreemptionReason,
    QueuedJob,
    QueueMetrics,
    SWERLTrainingConfig,
    VulnerabilityTrainingConfig,
)

# Phase 2: Queue Management imports
from src.services.gpu_scheduler.position_estimator import (
    PositionEstimator,
    get_position_estimator,
)
from src.services.gpu_scheduler.preemption_manager import (
    PreemptionManager,
    get_preemption_manager,
)
from src.services.gpu_scheduler.queue_dispatcher import (
    GPUQueueDispatcher,
    get_queue_dispatcher,
)
from src.services.gpu_scheduler.queue_engine import GPUQueueEngine, get_queue_engine

__all__ = [
    # Service
    "GPUSchedulerService",
    # Phase 2: Queue Management
    "GPUQueueEngine",
    "get_queue_engine",
    "PreemptionManager",
    "get_preemption_manager",
    "PositionEstimator",
    "get_position_estimator",
    "GPUQueueDispatcher",
    "get_queue_dispatcher",
    # Models
    "GPUJob",
    "GPUJobConfig",
    "GPUJobCreateRequest",
    "GPUJobErrorType",
    "GPUJobPriority",
    "GPUJobStatus",
    "GPUJobType",
    "GPUQuota",
    "GPUResourceStatus",
    "EmbeddingJobConfig",
    "VulnerabilityTrainingConfig",
    "SWERLTrainingConfig",
    "MemoryConsolidationConfig",
    # Phase 2 Models
    "QueuedJob",
    "PreemptionReason",
    "PreemptionEvent",
    "QueueMetrics",
    "PositionEstimate",
    # Exceptions
    "GPUSchedulerError",
    "GPUJobNotFoundError",
    "QuotaExceededError",
    "JobCancellationError",
    "InvalidJobConfigError",
    # Phase 2 Exceptions
    "PreemptionError",
    "QueueFullError",
    "StarvationPromotionError",
    "QueueDispatchError",
]
