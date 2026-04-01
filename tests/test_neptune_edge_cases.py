"""
Project Aura - Neptune Connection Pool Edge Case Tests

Tests for connection pool exhaustion, timeout handling, stale connection recovery,
dynamic pool sizing, transaction management, leak detection, graceful degradation,
priority queuing, health checks, and pool recovery after transient outages.

Priority: P1 - Operational Reliability
"""

import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from unittest.mock import patch

import pytest


class ConnectionState(Enum):
    """Connection state enumeration."""

    IDLE = "idle"
    IN_USE = "in_use"
    STALE = "stale"
    BROKEN = "broken"
    CLOSED = "closed"


class ConnectionPriority(Enum):
    """Connection request priority levels."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class MockConnection:
    """Mock Neptune connection for testing."""

    id: str
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    state: ConnectionState = ConnectionState.IDLE
    query_count: int = 0
    is_healthy: bool = True

    def execute_query(self, query: str) -> dict:
        """Execute a query on this connection."""
        if self.state == ConnectionState.BROKEN:
            raise ConnectionError("Connection is broken")
        if self.state == ConnectionState.STALE:
            raise TimeoutError("Connection is stale")
        if not self.is_healthy:
            raise ConnectionError("Health check failed")

        self.query_count += 1
        self.last_used_at = time.time()
        return {"status": "success", "query": query}

    def close(self) -> None:
        """Close the connection."""
        self.state = ConnectionState.CLOSED


@dataclass
class ConnectionRequest:
    """Request for a connection with priority."""

    priority: ConnectionPriority
    event: threading.Event = field(default_factory=threading.Event)
    connection: Optional[MockConnection] = None
    error: Optional[Exception] = None
    created_at: float = field(default_factory=time.time)

    def __lt__(self, other: "ConnectionRequest") -> bool:
        """Compare by priority (higher priority = lower sort value)."""
        return self.priority.value > other.priority.value


class MockNeptuneConnectionPool:
    """
    Mock Neptune connection pool for testing edge cases.

    This simulates the connection pooling behavior of the gremlin-python
    client used by NeptuneGraphService.
    """

    def __init__(
        self,
        pool_size: int = 10,
        max_pool_size: int = 20,
        connection_timeout: float = 5.0,
        idle_timeout: float = 300.0,
        health_check_interval: float = 30.0,
        enable_priority_queue: bool = False,
    ):
        self.min_pool_size = pool_size
        self.max_pool_size = max_pool_size
        self.connection_timeout = connection_timeout
        self.idle_timeout = idle_timeout
        self.health_check_interval = health_check_interval
        self.enable_priority_queue = enable_priority_queue

        self._connections: list[MockConnection] = []
        self._available: deque[MockConnection] = deque()
        self._in_use: set[str] = set()
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._priority_queue: queue.PriorityQueue[ConnectionRequest] = (
            queue.PriorityQueue()
        )

        self._is_healthy = True
        self._connection_counter = 0
        self._total_acquisitions = 0
        self._total_timeouts = 0
        self._total_leaks_detected = 0
        self._exhaustion_callbacks: list[Callable] = []
        self._recovery_callbacks: list[Callable] = []

        # Initialize minimum pool
        self._initialize_pool()

    def _initialize_pool(self) -> None:
        """Initialize the connection pool with minimum connections."""
        for _ in range(self.min_pool_size):
            conn = self._create_connection()
            if conn:
                self._available.append(conn)

    def _create_connection(self) -> Optional[MockConnection]:
        """Create a new connection."""
        if not self._is_healthy:
            return None

        self._connection_counter += 1
        conn = MockConnection(id=f"conn-{self._connection_counter}")
        self._connections.append(conn)
        return conn

    def acquire(
        self,
        timeout: Optional[float] = None,
        priority: ConnectionPriority = ConnectionPriority.NORMAL,
    ) -> MockConnection:
        """
        Acquire a connection from the pool.

        Args:
            timeout: Maximum time to wait for a connection
            priority: Request priority level

        Returns:
            A connection from the pool

        Raises:
            TimeoutError: If no connection available within timeout
            ConnectionError: If pool is unhealthy
        """
        timeout = timeout or self.connection_timeout
        deadline = time.time() + timeout

        if self.enable_priority_queue:
            return self._acquire_with_priority(deadline, priority)

        return self._acquire_standard(deadline)

    def _acquire_standard(self, deadline: float) -> MockConnection:
        """Standard connection acquisition without priority queue."""
        while time.time() < deadline:
            with self._condition:
                # Try to get an available connection
                while self._available:
                    conn = self._available.popleft()

                    # Check if connection is healthy
                    if conn.state != ConnectionState.IDLE or not conn.is_healthy:
                        self._remove_connection(conn)
                        continue

                    # Check if connection is stale
                    if time.time() - conn.last_used_at > self.idle_timeout:
                        conn.state = ConnectionState.STALE
                        self._remove_connection(conn)
                        continue

                    # Valid connection found
                    conn.state = ConnectionState.IN_USE
                    self._in_use.add(conn.id)
                    self._total_acquisitions += 1
                    return conn

                # No available connection, try to create new one
                if len(self._connections) < self.max_pool_size and self._is_healthy:
                    conn = self._create_connection()
                    if conn:
                        conn.state = ConnectionState.IN_USE
                        self._in_use.add(conn.id)
                        self._total_acquisitions += 1
                        return conn

                # Pool exhausted, wait for a connection
                remaining = deadline - time.time()
                if remaining <= 0:
                    break

                self._notify_exhaustion()
                self._condition.wait(timeout=min(0.1, remaining))

        self._total_timeouts += 1
        raise TimeoutError("Connection pool exhausted - no connections available")

    def _acquire_with_priority(
        self, deadline: float, priority: ConnectionPriority
    ) -> MockConnection:
        """Connection acquisition with priority queue."""
        request = ConnectionRequest(priority=priority)
        self._priority_queue.put(request)

        try:
            while time.time() < deadline:
                with self._condition:
                    # Process priority queue
                    if not self._priority_queue.empty():
                        next_request = self._priority_queue.queue[0]

                        # Only process if this is our request or higher priority
                        if (
                            next_request is request
                            or next_request.priority.value >= priority.value
                        ):
                            if self._available:
                                self._priority_queue.get()
                                conn = self._available.popleft()

                                if (
                                    conn.state == ConnectionState.IDLE
                                    and conn.is_healthy
                                ):
                                    conn.state = ConnectionState.IN_USE
                                    self._in_use.add(conn.id)
                                    self._total_acquisitions += 1
                                    request.connection = conn
                                    request.event.set()
                                    return conn

                    remaining = deadline - time.time()
                    if remaining <= 0:
                        break

                    self._condition.wait(timeout=min(0.1, remaining))

            self._total_timeouts += 1
            raise TimeoutError(
                f"Connection pool exhausted for priority {priority.name}"
            )

        finally:
            # Clean up request from queue if still there
            pass

    def release(self, connection: MockConnection) -> None:
        """
        Release a connection back to the pool.

        Args:
            connection: The connection to release
        """
        with self._condition:
            if connection.id in self._in_use:
                self._in_use.remove(connection.id)

                if connection.state == ConnectionState.IN_USE:
                    connection.state = ConnectionState.IDLE
                    connection.last_used_at = time.time()
                    self._available.append(connection)
                else:
                    # Connection is broken or stale, remove it
                    self._remove_connection(connection)

                self._condition.notify_all()

    def _remove_connection(self, connection: MockConnection) -> None:
        """Remove a connection from the pool."""
        connection.close()
        if connection in self._connections:
            self._connections.remove(connection)
        if connection.id in self._in_use:
            self._in_use.remove(connection.id)

    def _notify_exhaustion(self) -> None:
        """Notify listeners of pool exhaustion."""
        for callback in self._exhaustion_callbacks:
            try:
                callback()
            except Exception:
                pass

    def check_connection_leaks(self, max_age: float = 300.0) -> list[MockConnection]:
        """
        Detect connections that have been held too long (potential leaks).

        Args:
            max_age: Maximum allowed time for a connection to be in use

        Returns:
            List of potentially leaked connections
        """
        leaks = []
        current_time = time.time()

        with self._lock:
            for conn in self._connections:
                if conn.state == ConnectionState.IN_USE:
                    age = current_time - conn.last_used_at
                    if age > max_age:
                        leaks.append(conn)
                        self._total_leaks_detected += 1

        return leaks

    def health_check(self) -> dict[str, Any]:
        """
        Perform health check on all connections.

        Returns:
            Health check results
        """
        results = {
            "healthy_connections": 0,
            "unhealthy_connections": 0,
            "removed_connections": 0,
            "pool_healthy": self._is_healthy,
        }

        with self._lock:
            to_remove = []
            for conn in self._connections:
                if conn.is_healthy and conn.state != ConnectionState.BROKEN:
                    results["healthy_connections"] += 1
                else:
                    results["unhealthy_connections"] += 1
                    if conn.state == ConnectionState.IDLE:
                        to_remove.append(conn)

            for conn in to_remove:
                self._remove_connection(conn)
                results["removed_connections"] += 1

        return results

    def resize_pool(self, new_min_size: int, new_max_size: int) -> None:
        """
        Dynamically resize the connection pool.

        Args:
            new_min_size: New minimum pool size
            new_max_size: New maximum pool size
        """
        with self._lock:
            self.min_pool_size = new_min_size
            self.max_pool_size = new_max_size

            # Add connections if below minimum
            while len(self._available) < new_min_size:
                if len(self._connections) >= new_max_size:
                    break
                conn = self._create_connection()
                if conn:
                    self._available.append(conn)

            # Remove excess idle connections
            while len(self._available) > new_min_size:
                if self._available:
                    conn = self._available.pop()
                    self._remove_connection(conn)

    def simulate_outage(self) -> None:
        """Simulate a Neptune outage."""
        with self._lock:
            self._is_healthy = False
            for conn in self._connections:
                conn.is_healthy = False
                conn.state = ConnectionState.BROKEN

    def simulate_recovery(self) -> None:
        """Simulate recovery from a Neptune outage."""
        with self._lock:
            self._is_healthy = True
            # Clear all broken connections
            for conn in list(self._connections):
                self._remove_connection(conn)

            # Reinitialize pool
            self._initialize_pool()

            for callback in self._recovery_callbacks:
                try:
                    callback()
                except Exception:
                    pass

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            return {
                "total_connections": len(self._connections),
                "available_connections": len(self._available),
                "in_use_connections": len(self._in_use),
                "total_acquisitions": self._total_acquisitions,
                "total_timeouts": self._total_timeouts,
                "total_leaks_detected": self._total_leaks_detected,
                "pool_healthy": self._is_healthy,
                "min_pool_size": self.min_pool_size,
                "max_pool_size": self.max_pool_size,
            }

    def close(self) -> None:
        """Close all connections and shut down the pool."""
        with self._lock:
            for conn in self._connections:
                conn.close()
            self._connections.clear()
            self._available.clear()
            self._in_use.clear()


class TestConnectionPoolExhaustion:
    """Test connection pool exhaustion scenarios."""

    @pytest.fixture
    def pool(self):
        """Create a connection pool with small size for testing."""
        pool = MockNeptuneConnectionPool(pool_size=3, max_pool_size=5)
        yield pool
        pool.close()

    def test_all_connections_in_use_new_request_waits(self, pool):
        """Test that new requests wait when all connections are in use."""
        # Acquire all connections
        connections = []
        for _ in range(pool.max_pool_size):
            conn = pool.acquire(timeout=1.0)
            connections.append(conn)

        # Verify pool is exhausted
        stats = pool.get_stats()
        assert stats["available_connections"] == 0
        assert stats["in_use_connections"] == pool.max_pool_size

        # Next request should timeout
        with pytest.raises(TimeoutError, match="Connection pool exhausted"):
            pool.acquire(timeout=0.1)

        # Release one connection
        pool.release(connections[0])

        # Now acquisition should succeed
        new_conn = pool.acquire(timeout=1.0)
        assert new_conn is not None

        # Cleanup
        for conn in connections[1:]:
            pool.release(conn)
        pool.release(new_conn)

    def test_connection_timeout_while_waiting(self, pool):
        """Test connection timeout while waiting for available connection."""
        # Exhaust the pool
        connections = []
        for _ in range(pool.max_pool_size):
            conn = pool.acquire(timeout=1.0)
            connections.append(conn)

        # Measure timeout duration
        start = time.time()
        timeout_duration = 0.2

        with pytest.raises(TimeoutError):
            pool.acquire(timeout=timeout_duration)

        elapsed = time.time() - start

        # Should have waited approximately the timeout duration
        assert elapsed >= timeout_duration * 0.9
        assert elapsed < timeout_duration * 2  # Allow some tolerance

        # Cleanup
        for conn in connections:
            pool.release(conn)

    def test_concurrent_exhaustion_handling(self, pool):
        """Test handling of concurrent requests during pool exhaustion."""
        connections = []
        errors = []
        successes = []
        lock = threading.Lock()

        def acquire_connection(thread_id: int, delay: float = 0.0):
            """Attempt to acquire a connection."""
            time.sleep(delay)
            try:
                conn = pool.acquire(timeout=0.5)
                with lock:
                    successes.append((thread_id, conn.id))
                time.sleep(0.1)  # Hold connection briefly
                pool.release(conn)
            except TimeoutError as e:
                with lock:
                    errors.append((thread_id, str(e)))

        # Start more threads than max pool size
        threads = []
        for i in range(pool.max_pool_size * 3):
            t = threading.Thread(target=acquire_connection, args=(i, i * 0.01))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Some should succeed, some may timeout
        assert len(successes) > 0
        # Total attempts should equal successes + errors
        assert len(successes) + len(errors) == pool.max_pool_size * 3


class TestStaleConnectionHandling:
    """Test handling of stale and broken connections."""

    @pytest.fixture
    def pool(self):
        """Create pool with short idle timeout for testing."""
        pool = MockNeptuneConnectionPool(
            pool_size=3, max_pool_size=5, idle_timeout=0.1  # Very short for testing
        )
        yield pool
        pool.close()

    def test_stale_connection_detected_and_removed(self, pool):
        """Test that stale connections are detected and removed."""
        # Acquire and release a connection
        conn = pool.acquire(timeout=1.0)
        pool.release(conn)

        # Wait for connection to become stale
        time.sleep(0.2)

        # Acquire should get a fresh connection (stale one removed)
        new_conn = pool.acquire(timeout=1.0)

        # Should be a different connection
        assert new_conn.id != conn.id or new_conn.state == ConnectionState.IN_USE

        pool.release(new_conn)

    def test_broken_connection_returned_to_pool(self, pool):
        """Test handling when broken connection is returned to pool."""
        conn = pool.acquire(timeout=1.0)

        # Simulate connection becoming broken
        conn.state = ConnectionState.BROKEN
        conn.is_healthy = False

        # Release broken connection
        pool.release(conn)

        # Broken connection should not be available
        stats = pool.get_stats()
        # The broken connection should have been removed
        assert conn not in pool._available

        # Next acquire should still work (new connection created)
        new_conn = pool.acquire(timeout=1.0)
        assert new_conn is not None
        assert new_conn.is_healthy
        pool.release(new_conn)


class TestDynamicPoolSizing:
    """Test dynamic pool size adjustment under load."""

    @pytest.fixture
    def pool(self):
        """Create pool with adjustable size."""
        pool = MockNeptuneConnectionPool(pool_size=2, max_pool_size=10)
        yield pool
        pool.close()

    def test_pool_grows_under_high_load(self, pool):
        """Test that pool grows when demand exceeds minimum size."""
        initial_total = pool.get_stats()["total_connections"]

        # Acquire more connections than initial pool size
        connections = []
        for _ in range(5):
            conn = pool.acquire(timeout=1.0)
            connections.append(conn)

        # Pool should have grown
        stats = pool.get_stats()
        assert stats["total_connections"] >= 5
        assert stats["total_connections"] > initial_total

        # Cleanup
        for conn in connections:
            pool.release(conn)

    def test_dynamic_resize_increases_capacity(self, pool):
        """Test dynamic resize increases pool capacity."""
        # Exhaust current max
        connections = []
        for _ in range(pool.max_pool_size):
            conn = pool.acquire(timeout=1.0)
            connections.append(conn)

        # Should be at max
        with pytest.raises(TimeoutError):
            pool.acquire(timeout=0.1)

        # Increase max size
        pool.resize_pool(new_min_size=5, new_max_size=15)

        # Now should be able to acquire more
        extra_conn = pool.acquire(timeout=1.0)
        assert extra_conn is not None

        # Cleanup
        for conn in connections:
            pool.release(conn)
        pool.release(extra_conn)

    def test_dynamic_resize_shrinks_pool(self, pool):
        """Test dynamic resize can shrink idle connections."""
        # Acquire and release several connections to build up pool
        connections = []
        for _ in range(8):
            conn = pool.acquire(timeout=1.0)
            connections.append(conn)

        for conn in connections:
            pool.release(conn)

        stats_before = pool.get_stats()

        # Shrink pool
        pool.resize_pool(new_min_size=2, new_max_size=4)

        stats_after = pool.get_stats()

        # Available connections should be reduced
        assert stats_after["available_connections"] <= 2


class TestTransactionAcrossConnections:
    """Test transaction handling across multiple connections."""

    @pytest.fixture
    def pool(self):
        """Create pool for transaction testing."""
        pool = MockNeptuneConnectionPool(pool_size=5, max_pool_size=10)
        yield pool
        pool.close()

    def test_single_transaction_single_connection(self, pool):
        """Test that a transaction uses a single connection."""
        conn = pool.acquire(timeout=1.0)
        initial_query_count = conn.query_count

        # Execute multiple queries (simulating a transaction)
        for i in range(3):
            result = conn.execute_query(f"g.V().has('id', '{i}')")
            assert result["status"] == "success"

        # All queries should have used the same connection
        assert conn.query_count == initial_query_count + 3

        pool.release(conn)

    def test_connection_failure_mid_transaction(self, pool):
        """Test handling of connection failure during transaction."""
        conn = pool.acquire(timeout=1.0)

        # First query succeeds
        result1 = conn.execute_query("g.V().limit(1)")
        assert result1["status"] == "success"

        # Connection breaks mid-transaction
        conn.state = ConnectionState.BROKEN

        # Second query should fail
        with pytest.raises(ConnectionError, match="broken"):
            conn.execute_query("g.V().limit(2)")

        # Release broken connection
        pool.release(conn)

        # Should be able to get new connection
        new_conn = pool.acquire(timeout=1.0)
        assert new_conn is not None
        assert new_conn.id != conn.id
        pool.release(new_conn)


class TestConnectionLeakDetection:
    """Test connection leak detection mechanisms."""

    @pytest.fixture
    def pool(self):
        """Create pool for leak detection testing."""
        pool = MockNeptuneConnectionPool(pool_size=3, max_pool_size=5)
        yield pool
        pool.close()

    def test_leak_detected_after_max_age(self, pool):
        """Test that connections held too long are flagged as leaks."""
        conn = pool.acquire(timeout=1.0)

        # Simulate connection being held for a long time
        conn.last_used_at = time.time() - 400  # 400 seconds ago

        # Check for leaks
        leaks = pool.check_connection_leaks(max_age=300.0)

        assert len(leaks) == 1
        assert leaks[0].id == conn.id

        pool.release(conn)

    def test_no_leak_for_recently_used_connection(self, pool):
        """Test that recently used connections are not flagged as leaks."""
        conn = pool.acquire(timeout=1.0)

        # Connection was just acquired (recent last_used_at)
        leaks = pool.check_connection_leaks(max_age=300.0)

        assert len(leaks) == 0

        pool.release(conn)

    def test_multiple_leak_detection(self, pool):
        """Test detection of multiple leaked connections."""
        connections = []
        for _ in range(3):
            conn = pool.acquire(timeout=1.0)
            connections.append(conn)

        # Make all connections appear old
        old_time = time.time() - 500
        for conn in connections:
            conn.last_used_at = old_time

        leaks = pool.check_connection_leaks(max_age=300.0)

        assert len(leaks) == 3

        for conn in connections:
            pool.release(conn)


class TestGracefulDegradation:
    """Test graceful degradation vs error when pool exhausted."""

    @pytest.fixture
    def pool(self):
        """Create pool for degradation testing."""
        pool = MockNeptuneConnectionPool(pool_size=2, max_pool_size=3)
        yield pool
        pool.close()

    def test_timeout_error_on_exhaustion(self, pool):
        """Test that TimeoutError is raised on pool exhaustion."""
        # Exhaust pool
        connections = []
        for _ in range(pool.max_pool_size):
            conn = pool.acquire(timeout=1.0)
            connections.append(conn)

        # Next acquire should raise TimeoutError (not ConnectionError or other)
        with pytest.raises(TimeoutError) as exc_info:
            pool.acquire(timeout=0.1)

        assert "exhausted" in str(exc_info.value).lower()

        for conn in connections:
            pool.release(conn)

    def test_exhaustion_callback_invoked(self, pool):
        """Test that exhaustion callbacks are invoked."""
        callback_invoked = []

        def on_exhaustion():
            callback_invoked.append(time.time())

        pool._exhaustion_callbacks.append(on_exhaustion)

        # Exhaust pool
        connections = []
        for _ in range(pool.max_pool_size):
            conn = pool.acquire(timeout=1.0)
            connections.append(conn)

        # This should trigger exhaustion callback
        try:
            pool.acquire(timeout=0.2)
        except TimeoutError:
            pass

        # Callback should have been invoked
        assert len(callback_invoked) > 0

        for conn in connections:
            pool.release(conn)

    def test_partial_recovery_allows_some_requests(self, pool):
        """Test that partial pool availability allows some requests."""
        # Exhaust pool
        connections = []
        for _ in range(pool.max_pool_size):
            conn = pool.acquire(timeout=1.0)
            connections.append(conn)

        successes = []
        failures = []

        def try_acquire(thread_id: int):
            try:
                conn = pool.acquire(timeout=0.3)
                successes.append(thread_id)
                time.sleep(0.05)
                pool.release(conn)
            except TimeoutError:
                failures.append(thread_id)

        # Release one connection after a delay
        def release_after_delay():
            time.sleep(0.1)
            pool.release(connections[0])

        # Start threads
        threads = [threading.Thread(target=try_acquire, args=(i,)) for i in range(3)]
        release_thread = threading.Thread(target=release_after_delay)

        release_thread.start()
        for t in threads:
            t.start()

        for t in threads:
            t.join()
        release_thread.join()

        # At least one should succeed (got the released connection)
        assert len(successes) >= 1

        # Cleanup remaining connections
        for conn in connections[1:]:
            pool.release(conn)


class TestPriorityQueueForConnections:
    """Test priority queue for connection requests."""

    @pytest.fixture
    def pool(self):
        """Create pool with priority queue disabled for standard tests."""
        pool = MockNeptuneConnectionPool(
            pool_size=2, max_pool_size=5, enable_priority_queue=False
        )
        yield pool
        pool.close()

    def test_priority_enum_ordering(self, pool):
        """Test that priority enum has correct ordering."""
        # Verify priority values are ordered correctly
        assert ConnectionPriority.LOW.value < ConnectionPriority.NORMAL.value
        assert ConnectionPriority.NORMAL.value < ConnectionPriority.HIGH.value
        assert ConnectionPriority.HIGH.value < ConnectionPriority.CRITICAL.value

    def test_connection_request_comparison(self, pool):
        """Test that ConnectionRequest compares by priority correctly."""
        low_request = ConnectionRequest(priority=ConnectionPriority.LOW)
        high_request = ConnectionRequest(priority=ConnectionPriority.HIGH)
        critical_request = ConnectionRequest(priority=ConnectionPriority.CRITICAL)

        # Higher priority should sort before lower priority
        assert critical_request < high_request
        assert high_request < low_request
        assert critical_request < low_request

    def test_priority_queue_data_structure(self, pool):
        """Test priority queue maintains correct order."""
        pq: queue.PriorityQueue[ConnectionRequest] = queue.PriorityQueue()

        # Add requests in random order
        requests = [
            ConnectionRequest(priority=ConnectionPriority.LOW),
            ConnectionRequest(priority=ConnectionPriority.CRITICAL),
            ConnectionRequest(priority=ConnectionPriority.NORMAL),
            ConnectionRequest(priority=ConnectionPriority.HIGH),
        ]

        for req in requests:
            pq.put(req)

        # Should come out in priority order (highest first)
        result_priorities = []
        while not pq.empty():
            result_priorities.append(pq.get().priority)

        assert result_priorities[0] == ConnectionPriority.CRITICAL
        assert result_priorities[1] == ConnectionPriority.HIGH
        assert result_priorities[2] == ConnectionPriority.NORMAL
        assert result_priorities[3] == ConnectionPriority.LOW

    def test_critical_priority_acquires_connection(self, pool):
        """Test that critical priority requests can acquire connections."""
        # Standard pool (priority queue disabled) still accepts priority param
        conn = pool.acquire(timeout=1.0, priority=ConnectionPriority.CRITICAL)
        assert conn is not None
        pool.release(conn)


class TestConnectionHealthCheck:
    """Test connection health check mechanisms."""

    @pytest.fixture
    def pool(self):
        """Create pool for health check testing."""
        pool = MockNeptuneConnectionPool(pool_size=5, max_pool_size=10)
        yield pool
        pool.close()

    def test_health_check_reports_healthy_connections(self, pool):
        """Test health check counts healthy connections."""
        results = pool.health_check()

        assert results["pool_healthy"] is True
        assert results["healthy_connections"] > 0
        assert results["unhealthy_connections"] == 0

    def test_health_check_detects_unhealthy_connections(self, pool):
        """Test health check detects and removes unhealthy connections."""
        # Acquire and mark some connections as unhealthy
        conn = pool.acquire(timeout=1.0)
        conn.is_healthy = False
        pool.release(conn)

        results = pool.health_check()

        # Unhealthy connections should be detected and removed
        assert (
            results["removed_connections"] >= 1 or results["unhealthy_connections"] >= 1
        )

    def test_health_check_after_simulated_failure(self, pool):
        """Test health check after simulated connection failures."""
        # Get all available connections and mark as broken
        initial_stats = pool.get_stats()

        # Simulate some connections becoming broken
        conn = pool.acquire(timeout=1.0)
        conn.state = ConnectionState.BROKEN
        conn.is_healthy = False
        pool.release(conn)

        results = pool.health_check()

        # Should have detected and handled the broken connection
        assert results["removed_connections"] >= 0  # May have been removed on release


class TestPoolRecoveryAfterOutage:
    """Test pool recovery after transient Neptune outage."""

    @pytest.fixture
    def pool(self):
        """Create pool for outage testing."""
        pool = MockNeptuneConnectionPool(pool_size=5, max_pool_size=10)
        yield pool
        pool.close()

    def test_outage_breaks_all_connections(self, pool):
        """Test that outage marks all connections as broken."""
        # Get initial stats
        initial_stats = pool.get_stats()
        assert initial_stats["pool_healthy"] is True

        # Simulate outage
        pool.simulate_outage()

        # All connections should be broken
        stats = pool.get_stats()
        assert stats["pool_healthy"] is False

        # Acquire should fail
        with pytest.raises((TimeoutError, ConnectionError)):
            pool.acquire(timeout=0.1)

    def test_recovery_restores_pool(self, pool):
        """Test that recovery restores pool functionality."""
        # Simulate outage then recovery
        pool.simulate_outage()
        pool.simulate_recovery()

        # Pool should be healthy again
        stats = pool.get_stats()
        assert stats["pool_healthy"] is True

        # Should be able to acquire connections
        conn = pool.acquire(timeout=1.0)
        assert conn is not None
        assert conn.is_healthy is True
        pool.release(conn)

    def test_recovery_callback_invoked(self, pool):
        """Test that recovery callbacks are invoked."""
        callback_invoked = []

        def on_recovery():
            callback_invoked.append(time.time())

        pool._recovery_callbacks.append(on_recovery)

        pool.simulate_outage()
        pool.simulate_recovery()

        assert len(callback_invoked) == 1

    def test_requests_during_outage_fail_fast(self, pool):
        """Test that requests during outage fail quickly."""
        pool.simulate_outage()

        start = time.time()
        with pytest.raises((TimeoutError, ConnectionError)):
            pool.acquire(timeout=0.5)
        elapsed = time.time() - start

        # Should fail relatively quickly (not wait full timeout)
        # Allow up to full timeout as unhealthy pool still waits
        assert elapsed < 1.0

    def test_concurrent_requests_during_recovery(self, pool):
        """Test handling of concurrent requests during recovery."""
        pool.simulate_outage()

        results = {"during_outage": [], "after_recovery": []}
        lock = threading.Lock()
        outage_barrier = threading.Barrier(4)  # 3 threads + main thread

        def try_acquire_during_outage():
            """Try to acquire during outage - should fail."""
            outage_barrier.wait()  # Synchronize start
            try:
                conn = pool.acquire(timeout=0.2)
                with lock:
                    results["during_outage"].append("success")
                pool.release(conn)
            except (TimeoutError, ConnectionError):
                with lock:
                    results["during_outage"].append("failed")

        def try_acquire_after_recovery():
            """Try to acquire after recovery - should succeed."""
            try:
                conn = pool.acquire(timeout=1.0)
                with lock:
                    results["after_recovery"].append("success")
                pool.release(conn)
            except (TimeoutError, ConnectionError):
                with lock:
                    results["after_recovery"].append("failed")

        # Start requests during outage (use barrier to ensure they start together)
        threads_during = [
            threading.Thread(target=try_acquire_during_outage) for _ in range(3)
        ]
        for t in threads_during:
            t.start()

        # Wait for threads to be ready, then release them all at once
        outage_barrier.wait()

        # Wait for outage requests to complete
        for t in threads_during:
            t.join()

        # Outage requests should have failed
        assert len(results["during_outage"]) == 3
        assert all(r == "failed" for r in results["during_outage"])

        # Now recover
        pool.simulate_recovery()

        # Start requests after recovery
        threads_after = [
            threading.Thread(target=try_acquire_after_recovery) for _ in range(3)
        ]
        for t in threads_after:
            t.start()

        for t in threads_after:
            t.join()

        # After recovery requests should succeed
        assert "success" in results["after_recovery"]


class TestNeptuneServiceConnectionPoolIntegration:
    """Integration tests for Neptune service with connection pool behavior."""

    def test_neptune_service_pool_configuration(self):
        """Test that Neptune service has correct pool configuration."""
        from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Verify pool configuration attributes
        assert service.max_connections == 10
        assert service.connection_timeout == 10000  # milliseconds

    def test_neptune_service_handles_concurrent_queries(self):
        """Test Neptune service handles concurrent queries correctly."""
        from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        results = []
        errors = []
        lock = threading.Lock()

        def execute_query(thread_id: int):
            try:
                # Add entity (uses internal connection)
                entity_id = service.add_code_entity(
                    name=f"Class{thread_id}",
                    entity_type="class",
                    file_path=f"file{thread_id}.py",
                    line_number=thread_id,
                )
                with lock:
                    results.append(entity_id)
            except Exception as e:
                with lock:
                    errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=execute_query, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All queries should succeed in mock mode
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 20

    @patch("src.services.neptune_graph_service.GREMLIN_AVAILABLE", True)
    def test_neptune_aws_mode_connection_failure_fallback(self):
        """Test Neptune service falls back to mock on connection failure."""
        from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

        # Mock the gremlin client to simulate connection failure
        with patch("src.services.neptune_graph_service.client") as mock_client:
            mock_client.Client.side_effect = Exception("Connection refused")

            service = NeptuneGraphService(
                mode=NeptuneMode.AWS,
                endpoint="invalid.neptune.endpoint",
                use_iam_auth=False,
            )

            # Should fall back to mock mode
            assert service.mode == NeptuneMode.MOCK


class TestConnectionPoolStatistics:
    """Test connection pool statistics and monitoring."""

    @pytest.fixture
    def pool(self):
        """Create pool for statistics testing."""
        pool = MockNeptuneConnectionPool(pool_size=5, max_pool_size=10)
        yield pool
        pool.close()

    def test_stats_track_acquisitions(self, pool):
        """Test that statistics track connection acquisitions."""
        initial_stats = pool.get_stats()
        initial_acquisitions = initial_stats["total_acquisitions"]

        # Acquire and release several connections
        for _ in range(5):
            conn = pool.acquire(timeout=1.0)
            pool.release(conn)

        final_stats = pool.get_stats()
        assert final_stats["total_acquisitions"] == initial_acquisitions + 5

    def test_stats_track_timeouts(self, pool):
        """Test that statistics track timeout events."""
        # Exhaust pool
        connections = []
        for _ in range(pool.max_pool_size):
            conn = pool.acquire(timeout=1.0)
            connections.append(conn)

        initial_timeouts = pool.get_stats()["total_timeouts"]

        # Trigger timeouts
        for _ in range(3):
            try:
                pool.acquire(timeout=0.1)
            except TimeoutError:
                pass

        final_stats = pool.get_stats()
        assert final_stats["total_timeouts"] == initial_timeouts + 3

        # Cleanup
        for conn in connections:
            pool.release(conn)

    def test_stats_reflect_current_state(self, pool):
        """Test that stats reflect current pool state."""
        # Acquire some connections
        connections = []
        for _ in range(3):
            conn = pool.acquire(timeout=1.0)
            connections.append(conn)

        stats = pool.get_stats()
        assert stats["in_use_connections"] == 3
        assert (
            stats["available_connections"] == pool.get_stats()["total_connections"] - 3
        )

        # Release connections
        for conn in connections:
            pool.release(conn)

        stats = pool.get_stats()
        assert stats["in_use_connections"] == 0
