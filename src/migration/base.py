"""
Project Aura - Migration Base Classes

Base classes and utilities for data migration operations.

See ADR-049: Self-Hosted Deployment Strategy
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class MigrationStatus(Enum):
    """Migration status states."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MigrationError(Exception):
    """Exception raised during migration operations."""

    def __init__(
        self,
        message: str,
        source: str | None = None,
        item_id: str | None = None,
        recoverable: bool = True,
    ):
        super().__init__(message)
        self.source = source
        self.item_id = item_id
        self.recoverable = recoverable


@dataclass
class MigrationProgress:
    """Tracks migration progress."""

    total_items: int = 0
    migrated_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    current_item: str = ""
    start_time: datetime | None = None
    end_time: datetime | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def percent_complete(self) -> float:
        """Calculate completion percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.migrated_items / self.total_items) * 100

    @property
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time in seconds."""
        if not self.start_time:
            return 0.0
        end = self.end_time or datetime.now(timezone.utc)
        return (end - self.start_time).total_seconds()

    @property
    def items_per_second(self) -> float:
        """Calculate migration rate."""
        elapsed = self.elapsed_seconds
        if elapsed == 0:
            return 0.0
        return self.migrated_items / elapsed

    @property
    def estimated_remaining_seconds(self) -> float:
        """Estimate remaining time."""
        rate = self.items_per_second
        if rate == 0:
            return 0.0
        remaining = self.total_items - self.migrated_items
        return remaining / rate

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_items": self.total_items,
            "migrated_items": self.migrated_items,
            "failed_items": self.failed_items,
            "skipped_items": self.skipped_items,
            "current_item": self.current_item,
            "percent_complete": round(self.percent_complete, 2),
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "items_per_second": round(self.items_per_second, 2),
            "estimated_remaining_seconds": round(self.estimated_remaining_seconds, 2),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error_count": len(self.errors),
            "recent_errors": self.errors[-5:],  # Last 5 errors
        }


@dataclass
class MigrationResult:
    """Result of a migration operation."""

    status: MigrationStatus
    source_type: str
    target_type: str
    progress: MigrationProgress
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status.value,
            "source_type": self.source_type,
            "target_type": self.target_type,
            "progress": self.progress.to_dict(),
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "error_message": self.error_message,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


@dataclass
class MigrationConfig:
    """Configuration for migration operations."""

    # Batch processing
    batch_size: int = 100
    max_concurrent: int = 5

    # Error handling
    stop_on_error: bool = False
    max_errors: int = 100
    retry_count: int = 3
    retry_delay_seconds: float = 1.0

    # Progress reporting
    progress_interval_seconds: float = 5.0

    # Data handling
    skip_existing: bool = True
    verify_data: bool = True
    dry_run: bool = False

    # Filters
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)


class BaseMigrator(ABC):
    """
    Base class for all migrators.

    Provides common functionality for:
    - Progress tracking
    - Error handling with retries
    - Batch processing
    - Dry run support
    """

    def __init__(self, config: MigrationConfig | None = None):
        """
        Initialize migrator.

        Args:
            config: Migration configuration
        """
        self.config = config or MigrationConfig()
        self._progress = MigrationProgress()
        self._status = MigrationStatus.PENDING
        self._cancel_requested = False
        self._progress_callback: Callable[[MigrationProgress], None] | None = None

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return source service type (e.g., 'neptune', 'dynamodb')."""

    @property
    @abstractmethod
    def target_type(self) -> str:
        """Return target service type (e.g., 'neo4j', 'postgresql')."""

    @abstractmethod
    async def connect_source(self) -> bool:
        """Connect to source service."""

    @abstractmethod
    async def connect_target(self) -> bool:
        """Connect to target service."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from both services."""

    @abstractmethod
    async def count_source_items(self) -> int:
        """Count total items to migrate."""

    @abstractmethod
    async def fetch_source_batch(self, offset: int, limit: int) -> list[dict[str, Any]]:
        """Fetch a batch of items from source."""

    @abstractmethod
    async def migrate_item(self, item: dict[str, Any]) -> bool:
        """Migrate a single item to target."""

    @abstractmethod
    async def verify_item(self, item: dict[str, Any]) -> bool:
        """Verify an item was migrated correctly."""

    def set_progress_callback(
        self, callback: Callable[[MigrationProgress], None]
    ) -> None:
        """Set callback for progress updates."""
        self._progress_callback = callback

    def cancel(self) -> None:
        """Request cancellation of migration."""
        self._cancel_requested = True
        logger.info(
            f"Cancellation requested for {self.source_type} → {self.target_type}"
        )

    async def run(self) -> MigrationResult:
        """
        Execute the migration.

        Returns:
            MigrationResult with status and statistics
        """
        self._status = MigrationStatus.RUNNING
        self._progress = MigrationProgress()
        self._progress.start_time = datetime.now(timezone.utc)
        result = MigrationResult(
            status=MigrationStatus.RUNNING,
            source_type=self.source_type,
            target_type=self.target_type,
            progress=self._progress,
            started_at=self._progress.start_time,
        )

        try:
            # Connect to services
            logger.info(f"Connecting to {self.source_type}...")
            if not await self.connect_source():
                raise MigrationError(
                    f"Failed to connect to source ({self.source_type})",
                    recoverable=False,
                )

            logger.info(f"Connecting to {self.target_type}...")
            if not await self.connect_target():
                raise MigrationError(
                    f"Failed to connect to target ({self.target_type})",
                    recoverable=False,
                )

            # Count items
            logger.info("Counting source items...")
            self._progress.total_items = await self.count_source_items()
            logger.info(f"Found {self._progress.total_items} items to migrate")

            if self.config.dry_run:
                logger.info("DRY RUN - No data will be migrated")
                result.status = MigrationStatus.COMPLETED
                result.metadata["dry_run"] = True
                return result

            # Process in batches
            offset = 0
            while offset < self._progress.total_items:
                if self._cancel_requested:
                    result.status = MigrationStatus.CANCELLED
                    break

                batch = await self.fetch_source_batch(offset, self.config.batch_size)
                if not batch:
                    break

                # Process batch concurrently
                await self._process_batch(batch)

                offset += len(batch)
                self._report_progress()

                # Check error threshold
                if self._progress.failed_items >= self.config.max_errors:
                    raise MigrationError(
                        f"Max error threshold ({self.config.max_errors}) exceeded",
                        recoverable=False,
                    )

            # Final status
            self._progress.end_time = datetime.now(timezone.utc)
            if not self._cancel_requested:
                if self._progress.failed_items > 0:
                    result.status = MigrationStatus.COMPLETED
                    result.warnings.append(
                        f"{self._progress.failed_items} items failed to migrate"
                    )
                else:
                    result.status = MigrationStatus.COMPLETED

            logger.info(
                f"Migration complete: {self._progress.migrated_items}/{self._progress.total_items} items"
            )

        except MigrationError as e:
            result.status = MigrationStatus.FAILED
            result.error_message = str(e)
            self._progress.errors.append(str(e))
            logger.error(f"Migration failed: {e}")

        except Exception as e:
            result.status = MigrationStatus.FAILED
            result.error_message = f"Unexpected error: {e}"
            self._progress.errors.append(str(e))
            logger.exception("Migration failed with unexpected error")

        finally:
            await self.disconnect()
            self._progress.end_time = datetime.now(timezone.utc)
            result.completed_at = self._progress.end_time
            self._status = result.status

        return result

    async def _process_batch(self, batch: list[dict[str, Any]]) -> None:
        """Process a batch of items with concurrency control."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent)

        async def process_item(item: dict[str, Any]) -> None:
            async with semaphore:
                await self._process_single_item(item)

        await asyncio.gather(*[process_item(item) for item in batch])

    async def _process_single_item(self, item: dict[str, Any]) -> None:
        """Process a single item with retry logic."""
        item_id = str(item.get("id", item.get("pk", "unknown")))
        self._progress.current_item = item_id

        for attempt in range(self.config.retry_count):
            try:
                success = await self.migrate_item(item)

                if success:
                    if self.config.verify_data:
                        verified = await self.verify_item(item)
                        if not verified:
                            raise MigrationError(
                                f"Verification failed for item {item_id}"
                            )

                    self._progress.migrated_items += 1
                    return
                else:
                    self._progress.skipped_items += 1
                    return

            except MigrationError as e:
                if attempt < self.config.retry_count - 1 and e.recoverable:
                    await asyncio.sleep(self.config.retry_delay_seconds * (attempt + 1))
                    continue
                raise

            except Exception as e:
                if attempt < self.config.retry_count - 1:
                    await asyncio.sleep(self.config.retry_delay_seconds * (attempt + 1))
                    continue
                raise MigrationError(str(e), item_id=item_id)

        # All retries exhausted
        self._progress.failed_items += 1
        error_msg = (
            f"Failed to migrate item {item_id} after {self.config.retry_count} attempts"
        )
        self._progress.errors.append(error_msg)
        logger.warning(error_msg)

        if self.config.stop_on_error:
            raise MigrationError(error_msg, recoverable=False)

    def _report_progress(self) -> None:
        """Report current progress."""
        if self._progress_callback:
            self._progress_callback(self._progress)

        logger.info(
            f"Progress: {self._progress.migrated_items}/{self._progress.total_items} "
            f"({self._progress.percent_complete:.1f}%) - "
            f"{self._progress.items_per_second:.1f} items/sec"
        )
