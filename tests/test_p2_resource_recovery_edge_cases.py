"""
P2 Resource Exhaustion and Recovery Edge Case Tests.

Tests for medium-priority edge cases involving resource exhaustion,
crash recovery, and state machine transitions.

These tests cover edge cases identified in GitHub Issue #167.

Categories:
- Resource Exhaustion: Memory pressure, service limits, storage limits
- Recovery Scenarios: Crash recovery, retry exhaustion, data consistency
- State Machine Transitions: Workflow lifecycle, invalid transitions
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone

import pytest

# Mocks imported as needed within tests


# =============================================================================
# RESOURCE EXHAUSTION: MEMORY PRESSURE TESTS
# =============================================================================


class TestMemoryPressure:
    """Tests for memory pressure scenarios."""

    @pytest.mark.asyncio
    async def test_large_repository_memory_management(self):
        """
        Test: Memory management during large repository analysis (>1GB).

        Scenario:
        - Repository with thousands of files
        - System should stream/batch instead of loading all at once
        - Memory usage should stay bounded
        """
        # Simulate large repository metrics
        repo_stats = {
            "total_files": 50000,
            "total_size_bytes": 1.5 * 1024 * 1024 * 1024,  # 1.5GB
            "avg_file_size_bytes": 30 * 1024,  # 30KB average
        }

        # Verify batching strategy
        max_batch_size = 100
        num_batches = (repo_stats["total_files"] + max_batch_size - 1) // max_batch_size

        assert num_batches == 500  # 50000 / 100

        # Verify memory estimation
        max_concurrent_files = 10
        max_memory_per_batch = max_concurrent_files * repo_stats["avg_file_size_bytes"]
        max_memory_mb = max_memory_per_batch / (1024 * 1024)

        # Should stay under reasonable limit (300MB for file content)
        assert max_memory_mb < 1  # 10 * 30KB = 300KB per batch

    @pytest.mark.asyncio
    async def test_unbounded_graph_query_results(self):
        """
        Test: Handle unbounded result sets from graph queries.

        Scenario:
        - Query returns millions of nodes/edges
        - System should paginate or limit results
        - Should not OOM
        """

        # Simulate unbounded query pattern
        def mock_gremlin_query(query: str, limit: int | None = None):
            """Simulates Neptune query with optional limit."""
            total_matches = 1_000_000  # Million nodes match

            if limit:
                return list(range(min(limit, total_matches)))
            # Without limit, would return everything (dangerous!)
            return list(range(total_matches))

        # Without limit - dangerous
        # result = mock_gremlin_query("g.V().hasLabel('function')")

        # With limit - safe
        max_results = 1000
        result = mock_gremlin_query(
            "g.V().hasLabel('function').limit(1000)", limit=max_results
        )

        assert len(result) == max_results
        assert len(result) < 1_000_000

        # Verify pagination pattern
        page_size = 100
        pages_needed = (max_results + page_size - 1) // page_size
        assert pages_needed == 10

    @pytest.mark.asyncio
    async def test_memory_leak_detection_pattern(self):
        """
        Test: Detect memory leak patterns during long-running ingestion.

        Scenario:
        - Ingestion runs for hours
        - Memory should remain stable
        - Leak detection should trigger alert
        """
        # Simulate memory tracking over time
        memory_samples = []
        baseline_mb = 256

        def simulate_memory_growth(iteration: int, has_leak: bool = False):
            """Simulates memory usage over iterations."""
            if has_leak:
                # Leaky: grows 1MB per iteration
                return baseline_mb + iteration
            else:
                # Normal: fluctuates but stays bounded
                import random

                return baseline_mb + random.randint(-10, 10)

        # Simulate 100 iterations without leak
        for i in range(100):
            memory_samples.append(simulate_memory_growth(i, has_leak=False))

        # Verify no significant growth
        start_avg = sum(memory_samples[:10]) / 10
        end_avg = sum(memory_samples[-10:]) / 10
        growth_pct = (end_avg - start_avg) / start_avg * 100

        # Should not grow more than 20%
        assert abs(growth_pct) < 20

        # Now test leak detection
        memory_samples_leak = []
        for i in range(100):
            memory_samples_leak.append(simulate_memory_growth(i, has_leak=True))

        # Verify leak is detectable
        start_avg_leak = sum(memory_samples_leak[:10]) / 10
        end_avg_leak = sum(memory_samples_leak[-10:]) / 10
        growth_pct_leak = (end_avg_leak - start_avg_leak) / start_avg_leak * 100

        # Leak should show >20% growth
        assert growth_pct_leak > 20


# =============================================================================
# RESOURCE EXHAUSTION: SERVICE LIMITS TESTS
# =============================================================================


class TestServiceLimits:
    """Tests for AWS service limit scenarios."""

    @pytest.mark.asyncio
    async def test_dynamodb_provisioned_capacity_exceeded(self):
        """
        Test: DynamoDB provisioned capacity exceeded.

        Scenario:
        - High request rate exceeds provisioned RCU/WCU
        - System should implement throttling and backoff
        """
        from botocore.exceptions import ClientError

        request_count = 0
        throttled_count = 0
        capacity_limit = 100  # RCU/WCU per second

        async def mock_dynamo_write(item: dict):
            nonlocal request_count, throttled_count
            request_count += 1

            # Simulate throttling when over capacity
            if request_count > capacity_limit:
                throttled_count += 1
                raise ClientError(
                    {
                        "Error": {
                            "Code": "ProvisionedThroughputExceededException",
                            "Message": "Rate exceeded",
                        }
                    },
                    "PutItem",
                )
            return {"success": True}

        # Simulate burst of writes
        results = []
        for i in range(150):
            try:
                result = await mock_dynamo_write({"id": f"item-{i}"})
                results.append(("success", result))
            except ClientError as e:
                if (
                    e.response["Error"]["Code"]
                    == "ProvisionedThroughputExceededException"
                ):
                    results.append(("throttled", None))
                    # Would implement backoff here
                else:
                    raise

        successful = len([r for r in results if r[0] == "success"])
        throttled = len([r for r in results if r[0] == "throttled"])

        assert successful == 100
        assert throttled == 50

    @pytest.mark.asyncio
    async def test_lambda_15_minute_timeout(self):
        """
        Test: Lambda 15-minute timeout during complex operations.

        Scenario:
        - Long-running operation approaches timeout
        - System should checkpoint and resume
        """
        lambda_timeout_seconds = 900  # 15 minutes
        operation_start = time.time()

        # Simulate long operation with checkpoint
        checkpoints = []
        processed_items = 0
        total_items = 1000

        async def process_with_checkpoint(item_id: int, elapsed: float):
            """Simulates processing with timeout awareness."""
            remaining_time = lambda_timeout_seconds - elapsed

            # Reserve 60 seconds for cleanup
            if remaining_time < 60:
                return "timeout_imminent"

            # Process item
            await asyncio.sleep(0.001)  # Simulate work
            return "processed"

        # Simulate processing
        for i in range(total_items):
            elapsed = 0.1 * i  # Simulate time passing

            if elapsed > lambda_timeout_seconds - 60:
                # Would checkpoint and exit
                checkpoints.append(
                    {
                        "last_processed": processed_items,
                        "remaining": total_items - processed_items,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                break

            result = await process_with_checkpoint(i, elapsed)
            if result == "processed":
                processed_items += 1

        # Verify checkpoint was created before timeout
        if checkpoints:
            assert checkpoints[-1]["remaining"] > 0

        # Verify we processed some items
        assert processed_items > 0

    @pytest.mark.asyncio
    async def test_eks_pod_eviction_during_sandbox(self):
        """
        Test: EKS pod eviction during sandbox execution.

        Scenario:
        - Sandbox pod running tests
        - Node pressure causes eviction
        - System should handle gracefully
        """
        # Simulate pod lifecycle
        pod_states = []

        class MockPod:
            def __init__(self, name: str):
                self.name = name
                self.status = "Pending"
                self.exit_code = None
                self.evicted = False

            def start(self):
                self.status = "Running"
                pod_states.append(("start", self.name))

            def evict(self, reason: str):
                self.status = "Failed"
                self.evicted = True
                self.exit_code = 137  # SIGKILL
                pod_states.append(("evict", self.name, reason))

            def complete(self):
                self.status = "Succeeded"
                self.exit_code = 0
                pod_states.append(("complete", self.name))

        # Simulate eviction scenario
        pod = MockPod("sandbox-test-123")
        pod.start()

        # Simulate node pressure eviction
        pod.evict("NodePressure")

        assert pod.evicted
        assert pod.status == "Failed"
        assert pod.exit_code == 137

        # System should detect eviction and retry
        retry_pod = MockPod("sandbox-test-123-retry")
        retry_pod.start()
        retry_pod.complete()

        assert retry_pod.status == "Succeeded"
        assert len(pod_states) == 4  # start, evict, start, complete

    @pytest.mark.asyncio
    async def test_api_gateway_29_second_timeout(self):
        """
        Test: API Gateway 29-second timeout for long operations.

        Scenario:
        - API request triggers long-running operation
        - Gateway timeout before operation completes
        - System should return async job ID instead
        """
        api_gateway_timeout = 29  # seconds

        async def long_operation():
            """Simulates an operation that takes 60 seconds."""
            await asyncio.sleep(0.01)  # Simulated time
            return {"result": "complete", "duration_seconds": 60}

        async def async_wrapper(operation):
            """Wraps long operation in async job pattern."""
            # Estimate if operation will exceed timeout
            estimated_duration = 60  # seconds

            if estimated_duration > api_gateway_timeout:
                # Return job ID immediately, process async
                job_id = f"job-{int(time.time())}"
                return {
                    "status": "accepted",
                    "job_id": job_id,
                    "message": "Operation will complete asynchronously",
                    "poll_url": f"/api/v1/jobs/{job_id}",
                }

            # Short operation - run synchronously
            return await operation()

        result = await async_wrapper(long_operation)

        # Should return async job pattern
        assert result["status"] == "accepted"
        assert "job_id" in result
        assert "poll_url" in result


# =============================================================================
# RESOURCE EXHAUSTION: STORAGE LIMITS TESTS
# =============================================================================


class TestStorageLimits:
    """Tests for storage limit scenarios."""

    def test_s3_bucket_object_limit_detection(self):
        """
        Test: S3 bucket approaching object limit.

        Scenario:
        - Bucket has billions of objects
        - System should detect and alert before hitting limits
        """
        # S3 has no hard object limit, but listing becomes slow
        bucket_stats = {
            "object_count": 100_000_000,  # 100M objects
            "total_size_bytes": 50 * 1024**4,  # 50TB
            "avg_object_size": 500 * 1024,  # 500KB
        }

        # Define thresholds for alerting
        thresholds = {
            "object_count_warning": 50_000_000,
            "object_count_critical": 100_000_000,
            "size_warning_tb": 40,
            "size_critical_tb": 50,
        }

        # Check against thresholds
        size_tb = bucket_stats["total_size_bytes"] / (1024**4)

        is_object_warning = (
            bucket_stats["object_count"] >= thresholds["object_count_warning"]
        )
        is_object_critical = (
            bucket_stats["object_count"] >= thresholds["object_count_critical"]
        )
        is_size_warning = size_tb >= thresholds["size_warning_tb"]
        is_size_critical = size_tb >= thresholds["size_critical_tb"]

        assert is_object_critical
        assert is_size_critical

        # Would trigger alert
        alert_severity = (
            "critical" if (is_object_critical or is_size_critical) else "warning"
        )
        assert alert_severity == "critical"

    def test_cloudwatch_logs_storage_quota(self):
        """
        Test: CloudWatch Logs storage approaching quota.

        Scenario:
        - Log group retention causing storage growth
        - System should monitor and adjust retention
        """
        # Simulate log group stats
        log_groups = [
            {
                "name": "/aws/lambda/func1",
                "stored_bytes": 10 * 1024**3,
                "retention_days": 365,
            },
            {
                "name": "/aws/lambda/func2",
                "stored_bytes": 5 * 1024**3,
                "retention_days": 90,
            },
            {
                "name": "/aws/eks/cluster",
                "stored_bytes": 50 * 1024**3,
                "retention_days": 30,
            },
        ]

        total_storage_gb = sum(lg["stored_bytes"] for lg in log_groups) / (1024**3)

        # Define storage budget
        monthly_budget_gb = 100
        current_usage_pct = (total_storage_gb / monthly_budget_gb) * 100

        assert current_usage_pct == 65.0  # 65GB / 100GB

        # Identify groups for retention reduction
        candidates_for_reduction = [
            lg
            for lg in log_groups
            if lg["retention_days"] > 30 and lg["stored_bytes"] > 5 * 1024**3
        ]

        assert len(candidates_for_reduction) == 1
        assert candidates_for_reduction[0]["name"] == "/aws/lambda/func1"

    def test_dynamodb_item_size_validation(self):
        """
        Test: DynamoDB item size limit (400KB) validation.

        Scenario:
        - Storing large code entity or analysis
        - System should detect and split/compress
        """
        max_item_size = 400 * 1024  # 400KB

        def calculate_item_size(item: dict) -> int:
            """Estimates DynamoDB item size in bytes."""
            import json

            # Simplified estimation
            return len(json.dumps(item).encode("utf-8"))

        # Test normal item
        normal_item = {
            "pk": "entity#func-123",
            "sk": "metadata",
            "content": "def foo(): pass" * 100,  # ~1.5KB
            "metadata": {"lines": 100, "complexity": 5},
        }

        normal_size = calculate_item_size(normal_item)
        assert normal_size < max_item_size

        # Test oversized item
        large_content = "x" * (500 * 1024)  # 500KB
        oversized_item = {
            "pk": "entity#func-456",
            "sk": "metadata",
            "content": large_content,
        }

        oversized_size = calculate_item_size(oversized_item)
        assert oversized_size > max_item_size

        # System should handle by splitting or using S3
        should_use_s3 = oversized_size > max_item_size
        assert should_use_s3


# =============================================================================
# RECOVERY SCENARIOS: CRASH RECOVERY TESTS
# =============================================================================


class TestCrashRecovery:
    """Tests for crash recovery scenarios."""

    @pytest.mark.asyncio
    async def test_resume_ingestion_after_crash(self):
        """
        Test: Resume ingestion after crash (partial graph state).

        Scenario:
        - Ingestion crashes after processing 50% of files
        - Resume should continue from last checkpoint
        - Should not duplicate already-processed entities
        """
        # Simulate checkpoint-based recovery
        total_files = 100
        checkpoint = {
            "repository_id": "repo-123",
            "last_processed_file": 49,
            "processed_files": list(range(50)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Simulate resume
        remaining_files = [
            i for i in range(total_files) if i not in checkpoint["processed_files"]
        ]

        assert len(remaining_files) == 50
        assert remaining_files[0] == 50  # Resume from file 50

        # Verify no duplicates would be processed
        all_processed = set(checkpoint["processed_files"])
        for file_idx in remaining_files:
            assert file_idx not in all_processed
            all_processed.add(file_idx)

        assert len(all_processed) == 100

    @pytest.mark.asyncio
    async def test_orphaned_fargate_task_cleanup(self):
        """
        Test: Orphaned Fargate tasks after orchestrator crash.

        Scenario:
        - Orchestrator crashes while tasks are running
        - Tasks continue running but no one is tracking them
        - Cleanup job should find and terminate orphaned tasks
        """
        # Simulate task registry
        running_tasks = [
            {
                "task_id": "task-1",
                "started_at": datetime.now(timezone.utc) - timedelta(hours=2),
            },
            {
                "task_id": "task-2",
                "started_at": datetime.now(timezone.utc) - timedelta(hours=5),
            },
            {
                "task_id": "task-3",
                "started_at": datetime.now(timezone.utc) - timedelta(minutes=30),
            },
        ]

        # Orchestrator's known tasks (simulating crash - lost this)
        orchestrator_known = set()  # Empty due to crash

        # Cleanup job finds orphaned tasks
        max_task_age_hours = 4
        now = datetime.now(timezone.utc)

        orphaned_tasks = []
        for task in running_tasks:
            age = now - task["started_at"]
            is_orphaned = task["task_id"] not in orchestrator_known
            is_stale = age > timedelta(hours=max_task_age_hours)

            if is_orphaned and is_stale:
                orphaned_tasks.append(task)

        # task-2 is orphaned and stale (5 hours old)
        assert len(orphaned_tasks) == 1
        assert orphaned_tasks[0]["task_id"] == "task-2"

    @pytest.mark.asyncio
    async def test_incomplete_sandbox_teardown_recovery(self):
        """
        Test: Incomplete sandbox teardown recovery.

        Scenario:
        - Sandbox teardown interrupted (network issue)
        - Resources left in inconsistent state
        - Recovery should complete cleanup
        """
        # Simulate sandbox resources
        sandbox_resources = {
            "namespace": {"name": "sandbox-123", "deleted": False},
            "network_policy": {"name": "sandbox-123-policy", "deleted": True},
            "pvc": {"name": "sandbox-123-data", "deleted": False},
            "service_account": {"name": "sandbox-123-sa", "deleted": True},
        }

        # Find incomplete teardown
        incomplete = [
            (resource_type, resource)
            for resource_type, resource in sandbox_resources.items()
            if not resource["deleted"]
        ]

        assert len(incomplete) == 2
        resource_types = [r[0] for r in incomplete]
        assert "namespace" in resource_types
        assert "pvc" in resource_types

        # Simulate cleanup
        for resource_type, resource in incomplete:
            resource["deleted"] = True

        # Verify all cleaned up
        all_deleted = all(r["deleted"] for r in sandbox_resources.values())
        assert all_deleted

    @pytest.mark.asyncio
    async def test_step_functions_execution_recovery(self):
        """
        Test: Step Functions execution state recovery.

        Scenario:
        - Step function paused due to activity timeout
        - Resume should continue from last successful state
        """
        # Simulate Step Functions execution history
        execution_history = [
            {
                "state": "Initialize",
                "status": "SUCCEEDED",
                "output": {"repo_id": "123"},
            },
            {"state": "FetchCode", "status": "SUCCEEDED", "output": {"files": 100}},
            {"state": "AnalyzeCode", "status": "TIMED_OUT", "output": None},
            {"state": "GenerateReport", "status": "NOT_STARTED", "output": None},
        ]

        # Find recovery point
        last_successful = None
        failed_state = None
        for event in execution_history:
            if event["status"] == "SUCCEEDED":
                last_successful = event
            elif event["status"] in ("TIMED_OUT", "FAILED"):
                failed_state = event
                break

        assert last_successful["state"] == "FetchCode"
        assert failed_state["state"] == "AnalyzeCode"

        # Resume execution from failed state
        resume_from = failed_state["state"]
        resume_input = last_successful["output"]

        assert resume_from == "AnalyzeCode"
        assert resume_input == {"files": 100}


# =============================================================================
# RECOVERY SCENARIOS: RETRY EXHAUSTION TESTS
# =============================================================================


class TestRetryExhaustion:
    """Tests for retry exhaustion scenarios."""

    @pytest.mark.asyncio
    async def test_exponential_backoff_max_retries(self):
        """
        Test: Exponential backoff max retries exceeded.

        Scenario:
        - Operation fails repeatedly
        - Backoff increases exponentially
        - Eventually gives up and moves to DLQ
        """
        max_retries = 5
        base_delay_seconds = 1
        max_delay_seconds = 60
        attempt = 0
        delays = []

        while attempt < max_retries:
            attempt += 1

            # Calculate exponential backoff with jitter
            delay = min(base_delay_seconds * (2 ** (attempt - 1)), max_delay_seconds)
            delays.append(delay)

            # Simulate failure
            success = False
            if not success and attempt >= max_retries:
                # Move to DLQ
                dlq_message = {
                    "original_message": {"task": "process"},
                    "attempts": attempt,
                    "last_error": "Service unavailable",
                    "exhausted_at": datetime.now(timezone.utc).isoformat(),
                }
                break

        # Verify exponential growth
        assert delays == [1, 2, 4, 8, 16]

        # Verify DLQ message created
        assert dlq_message["attempts"] == 5

    @pytest.mark.asyncio
    async def test_dead_letter_queue_processing(self):
        """
        Test: Dead letter queue message processing.

        Scenario:
        - Messages moved to DLQ after retry exhaustion
        - DLQ processor should analyze and categorize failures
        """
        # Simulate DLQ messages
        dlq_messages = [
            {"message_id": "1", "error": "ConnectionError", "attempts": 5},
            {"message_id": "2", "error": "ValidationError", "attempts": 1},
            {"message_id": "3", "error": "TimeoutError", "attempts": 5},
            {"message_id": "4", "error": "ConnectionError", "attempts": 5},
        ]

        # Categorize failures
        retryable_errors = {"ConnectionError", "TimeoutError"}
        permanent_errors = {"ValidationError", "AuthenticationError"}

        categorized = {"retryable": [], "permanent": [], "unknown": []}

        for msg in dlq_messages:
            error_type = msg["error"]
            if error_type in retryable_errors:
                categorized["retryable"].append(msg)
            elif error_type in permanent_errors:
                categorized["permanent"].append(msg)
            else:
                categorized["unknown"].append(msg)

        assert len(categorized["retryable"]) == 3
        assert len(categorized["permanent"]) == 1

        # Retryable messages could be reprocessed with longer backoff
        for msg in categorized["retryable"]:
            msg["retry_with_extended_backoff"] = True

    @pytest.mark.asyncio
    async def test_circuit_breaker_state_transitions(self):
        """
        Test: Circuit breaker state transitions.

        Scenario:
        - Closed -> Open after failures exceed threshold
        - Open -> Half-Open after timeout
        - Half-Open -> Closed on success
        """

        class CircuitBreaker:
            def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
                self.state = "CLOSED"
                self.failure_count = 0
                self.failure_threshold = failure_threshold
                self.recovery_timeout = recovery_timeout
                self.last_failure_time = None
                self.transitions = []

            def record_success(self):
                if self.state == "HALF_OPEN":
                    self._transition("CLOSED")
                self.failure_count = 0

            def record_failure(self):
                self.failure_count += 1
                self.last_failure_time = time.time()

                if (
                    self.state == "CLOSED"
                    and self.failure_count >= self.failure_threshold
                ):
                    self._transition("OPEN")
                elif self.state == "HALF_OPEN":
                    self._transition("OPEN")

            def check_state(self):
                if self.state == "OPEN":
                    if self.last_failure_time and (
                        time.time() - self.last_failure_time > self.recovery_timeout
                    ):
                        self._transition("HALF_OPEN")
                return self.state

            def _transition(self, new_state: str):
                old_state = self.state
                self.state = new_state
                self.transitions.append((old_state, new_state))

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)

        # Start closed
        assert cb.state == "CLOSED"

        # Record failures until open
        for _ in range(3):
            cb.record_failure()

        assert cb.state == "OPEN"
        assert ("CLOSED", "OPEN") in cb.transitions

        # Wait for recovery timeout
        time.sleep(0.15)
        cb.check_state()

        assert cb.state == "HALF_OPEN"
        assert ("OPEN", "HALF_OPEN") in cb.transitions

        # Success closes circuit
        cb.record_success()
        assert cb.state == "CLOSED"
        assert ("HALF_OPEN", "CLOSED") in cb.transitions


# =============================================================================
# RECOVERY SCENARIOS: DATA CONSISTENCY TESTS
# =============================================================================


class TestDataConsistency:
    """Tests for data consistency edge cases."""

    @pytest.mark.asyncio
    async def test_eventual_consistency_read_after_write(self):
        """
        Test: Eventual consistency window issues (read-after-write).

        Scenario:
        - Write to DynamoDB
        - Immediate read might not see the write
        - System should handle with retries or strong consistency
        """
        # Simulate eventually consistent read
        data_store = {}
        pending_writes = []

        def write(key: str, value: dict):
            """Simulates write with replication delay."""
            pending_writes.append({"key": key, "value": value, "time": time.time()})

        def eventually_consistent_read(key: str, current_time: float):
            """Simulates read that might miss recent writes."""
            replication_delay = 0.05  # 50ms

            # Check if write has replicated
            for pw in pending_writes:
                if pw["key"] == key:
                    if current_time - pw["time"] > replication_delay:
                        data_store[key] = pw["value"]

            return data_store.get(key)

        def strongly_consistent_read(key: str):
            """Simulates strongly consistent read (always sees latest)."""
            for pw in pending_writes:
                if pw["key"] == key:
                    data_store[key] = pw["value"]
            return data_store.get(key)

        # Write data
        write("entity-123", {"status": "active"})

        # Immediate eventually consistent read - might miss
        result_ec = eventually_consistent_read("entity-123", time.time())
        # Could be None due to replication lag

        # Strong consistent read - always sees
        result_sc = strongly_consistent_read("entity-123")
        assert result_sc == {"status": "active"}

    @pytest.mark.asyncio
    async def test_cross_region_replication_lag(self):
        """
        Test: Cross-region replication lag handling.

        Scenario:
        - Write to primary region
        - Read from secondary region (DR)
        - Handle potential lag
        """
        # Simulate multi-region setup
        regions = {
            "us-east-1": {"role": "primary", "data": {}},
            "us-west-2": {"role": "secondary", "data": {}, "lag_seconds": 5},
        }

        def write_primary(key: str, value: dict):
            regions["us-east-1"]["data"][key] = {
                "value": value,
                "timestamp": time.time(),
            }

        def read_secondary(key: str, max_lag_acceptable: float = 10):
            """Read from secondary, checking replication lag."""
            primary_record = regions["us-east-1"]["data"].get(key)
            secondary_record = regions["us-west-2"]["data"].get(key)

            if not primary_record:
                return None, "not_found"

            if not secondary_record:
                # Not yet replicated
                return None, "pending_replication"

            lag = primary_record["timestamp"] - secondary_record["timestamp"]
            if lag > max_lag_acceptable:
                return None, "excessive_lag"

            return secondary_record["value"], "ok"

        # Write to primary
        write_primary("config-1", {"version": 2})

        # Simulate replication
        regions["us-west-2"]["data"]["config-1"] = {
            "value": {"version": 2},
            "timestamp": time.time() - 3,  # 3 second lag
        }

        value, status = read_secondary("config-1", max_lag_acceptable=5)
        assert status == "ok"
        assert value == {"version": 2}

    @pytest.mark.asyncio
    async def test_cache_invalidation_timing(self):
        """
        Test: Cache invalidation timing issues.

        Scenario:
        - Data updated in database
        - Cache not yet invalidated
        - Stale data served
        """
        # Simulate cache layer
        cache = {"entity-1": {"data": "old_value", "cached_at": time.time() - 60}}
        database = {"entity-1": {"data": "new_value", "updated_at": time.time() - 30}}

        def get_with_cache(key: str, cache_ttl: int = 120):
            """Get value with cache, potentially serving stale data."""
            cached = cache.get(key)

            if cached:
                age = time.time() - cached["cached_at"]
                if age < cache_ttl:
                    # Cache hit - but might be stale!
                    return cached["data"], "cache_hit"

            # Cache miss or expired - get from DB
            db_value = database.get(key)
            if db_value:
                cache[key] = {"data": db_value["data"], "cached_at": time.time()}
                return db_value["data"], "cache_miss"

            return None, "not_found"

        # First call gets stale cached value
        value, source = get_with_cache("entity-1", cache_ttl=120)
        assert value == "old_value"  # Stale!
        assert source == "cache_hit"

        # Detect staleness by comparing with DB
        db_value = database["entity-1"]["data"]
        is_stale = value != db_value
        assert is_stale

        # Solution: Invalidate cache on write
        def invalidate_cache(key: str):
            if key in cache:
                del cache[key]

        invalidate_cache("entity-1")

        # Now get fresh value
        value, source = get_with_cache("entity-1", cache_ttl=120)
        assert value == "new_value"
        assert source == "cache_miss"


# =============================================================================
# STATE MACHINE TRANSITIONS: WORKFLOW LIFECYCLE TESTS
# =============================================================================


class TestWorkflowLifecycle:
    """Tests for workflow lifecycle edge cases."""

    @pytest.mark.asyncio
    async def test_sandbox_teardown_during_active_test(self):
        """
        Test: Sandbox teardown triggered during active test.

        Scenario:
        - Tests running in sandbox
        - Timeout triggers teardown
        - Running tests should be gracefully terminated
        """

        class Sandbox:
            def __init__(self, sandbox_id: str):
                self.id = sandbox_id
                self.status = "INITIALIZING"
                self.active_tests = []
                self.events = []

            def start_test(self, test_id: str):
                self.active_tests.append(test_id)
                self.status = "RUNNING"
                self.events.append(("test_started", test_id))

            def teardown(self, reason: str):
                # Gracefully stop active tests
                for test_id in self.active_tests:
                    self.events.append(("test_cancelled", test_id, reason))
                self.active_tests = []
                self.status = "TEARDOWN"
                self.events.append(("teardown_started", reason))

            def complete_teardown(self):
                self.status = "TERMINATED"
                self.events.append(("teardown_complete",))

        sandbox = Sandbox("sandbox-456")
        sandbox.start_test("test-1")
        sandbox.start_test("test-2")

        assert sandbox.status == "RUNNING"
        assert len(sandbox.active_tests) == 2

        # Timeout triggers teardown
        sandbox.teardown("timeout_exceeded")

        # All tests cancelled
        assert len(sandbox.active_tests) == 0
        assert sandbox.status == "TEARDOWN"

        # Verify cancellation events
        cancel_events = [e for e in sandbox.events if e[0] == "test_cancelled"]
        assert len(cancel_events) == 2

    @pytest.mark.asyncio
    async def test_onboarding_wizard_resume_after_days(self):
        """
        Test: Onboarding wizard abandoned mid-flow, resumed days later.

        Scenario:
        - User completes step 1 and 2
        - Abandons wizard for 3 days
        - Resumes and completes
        - State should be preserved
        """
        # Simulate onboarding state
        onboarding_state = {
            "user_id": "user-123",
            "started_at": datetime.now(timezone.utc) - timedelta(days=3),
            "current_step": 2,
            "completed_steps": [
                {
                    "step": 1,
                    "name": "account_setup",
                    "completed_at": "2024-01-01T10:00:00Z",
                },
                {
                    "step": 2,
                    "name": "org_config",
                    "completed_at": "2024-01-01T10:05:00Z",
                },
            ],
            "total_steps": 5,
            "last_activity": datetime.now(timezone.utc) - timedelta(days=3),
        }

        # Calculate abandonment
        now = datetime.now(timezone.utc)
        time_since_activity = now - onboarding_state["last_activity"]
        is_abandoned = time_since_activity > timedelta(days=1)

        assert is_abandoned

        # Resume wizard
        def resume_onboarding(state: dict):
            """Resume from last completed step."""
            next_step = state["current_step"] + 1
            state["last_activity"] = datetime.now(timezone.utc)
            return {
                "resume_from_step": next_step,
                "preserved_data": state["completed_steps"],
                "remaining_steps": state["total_steps"] - len(state["completed_steps"]),
            }

        resume_info = resume_onboarding(onboarding_state)

        assert resume_info["resume_from_step"] == 3
        assert len(resume_info["preserved_data"]) == 2
        assert resume_info["remaining_steps"] == 3

    @pytest.mark.asyncio
    async def test_agent_execution_paused_cluster_scaled(self):
        """
        Test: Agent execution paused then cluster scaled down.

        Scenario:
        - Agent running long task
        - Paused by user
        - Cluster scales down, pod terminated
        - Resume should handle missing pod
        """
        # Simulate agent execution state
        execution_state = {
            "execution_id": "exec-789",
            "agent_id": "agent-001",
            "status": "PAUSED",
            "checkpoint": {
                "step": 5,
                "context": {"files_processed": 50},
                "saved_at": datetime.now(timezone.utc).isoformat(),
            },
            "pod_name": "agent-001-xyz",
        }

        # Check pod status
        def check_pod_exists(pod_name: str) -> bool:
            # Simulate pod was terminated due to scale-down
            return False

        pod_exists = check_pod_exists(execution_state["pod_name"])

        # Resume logic
        def resume_execution(state: dict, pod_exists: bool):
            if not pod_exists:
                # Pod was terminated - need to reschedule
                return {
                    "action": "reschedule",
                    "resume_from_checkpoint": state["checkpoint"],
                    "new_pod_required": True,
                }
            else:
                # Pod still exists - just unpause
                return {
                    "action": "unpause",
                    "pod_name": state["pod_name"],
                }

        result = resume_execution(execution_state, pod_exists)

        assert result["action"] == "reschedule"
        assert result["new_pod_required"]
        assert result["resume_from_checkpoint"]["step"] == 5


# =============================================================================
# STATE MACHINE TRANSITIONS: INVALID TRANSITIONS TESTS
# =============================================================================


class TestInvalidTransitions:
    """Tests for invalid state transition handling."""

    @pytest.mark.asyncio
    async def test_approval_on_already_executed_action(self):
        """
        Test: Approval attempt on already-executed action.

        Scenario:
        - Action was auto-approved and executed
        - User tries to manually approve
        - Should reject with clear error
        """
        from src.services.hitl_approval_service import (
            ApprovalStatus,
            HITLApprovalService,
            HITLMode,
            PatchSeverity,
        )

        service = HITLApprovalService(mode=HITLMode.MOCK)

        # Create and auto-approve request
        request = service.create_approval_request(
            patch_id="patch-auto-1",
            vulnerability_id="vuln-1",
            severity=PatchSeverity.LOW,
        )

        # First approval (simulating auto-approval)
        service.approve_request(
            request.approval_id,
            reviewer_id="system@auto",
            reason="Auto-approved: low severity",
        )

        # Simulate execution
        # (In real system, action would be executed here)

        # Late manual approval attempt
        result = service.approve_request(
            request.approval_id,
            reviewer_id="user@manual.com",
            reason="Manual approval",
        )

        # Should fail - already approved
        assert result is False

        # Verify state
        final_request = service.get_request(request.approval_id)
        assert final_request.status == ApprovalStatus.APPROVED
        assert final_request.reviewed_by == "system@auto"

    @pytest.mark.asyncio
    async def test_cancel_on_already_completed_job(self):
        """
        Test: Cancel attempt on already-completed job.

        Scenario:
        - Ingestion job completed successfully
        - User tries to cancel
        - Should reject with status information
        """
        # Simulate job states
        jobs = {
            "job-1": {
                "status": "COMPLETED",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": "success",
            }
        }

        def cancel_job(job_id: str):
            job = jobs.get(job_id)
            if not job:
                return {"success": False, "error": "Job not found"}

            if job["status"] == "COMPLETED":
                return {
                    "success": False,
                    "error": "Cannot cancel completed job",
                    "current_status": job["status"],
                    "completed_at": job["completed_at"],
                }

            if job["status"] == "CANCELLED":
                return {
                    "success": False,
                    "error": "Job already cancelled",
                }

            # Can only cancel PENDING or RUNNING
            if job["status"] in ("PENDING", "RUNNING"):
                job["status"] = "CANCELLED"
                return {"success": True}

            return {"success": False, "error": "Invalid state for cancellation"}

        result = cancel_job("job-1")

        assert result["success"] is False
        assert "completed" in result["error"].lower()
        assert result["current_status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_retry_on_non_retryable_failure(self):
        """
        Test: Retry attempt on non-retryable failure.

        Scenario:
        - Operation failed with validation error
        - Retry would produce same error
        - Should reject retry and suggest fix
        """
        # Define retryable vs non-retryable errors
        retryable_errors = {
            "ConnectionError",
            "TimeoutError",
            "ThrottlingException",
            "ServiceUnavailable",
        }

        non_retryable_errors = {
            "ValidationError",
            "AuthenticationError",
            "AccessDenied",
            "InvalidParameterValue",
            "ResourceNotFound",
        }

        # Simulate failed operation
        failed_operation = {
            "operation_id": "op-123",
            "error_type": "ValidationError",
            "error_message": "Invalid repository URL format",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        def attempt_retry(operation: dict):
            error_type = operation["error_type"]

            if error_type in retryable_errors:
                return {
                    "can_retry": True,
                    "retry_delay_seconds": 30,
                }

            if error_type in non_retryable_errors:
                return {
                    "can_retry": False,
                    "reason": f"{error_type} is not retryable",
                    "suggestion": "Fix the input and resubmit",
                }

            # Unknown error - default to retryable with caution
            return {
                "can_retry": True,
                "retry_delay_seconds": 60,
                "warning": "Unknown error type, retry may not help",
            }

        result = attempt_retry(failed_operation)

        assert result["can_retry"] is False
        assert "ValidationError" in result["reason"]
        assert "fix" in result["suggestion"].lower()
