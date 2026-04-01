"""
Project Aura - Security Services Load and Performance Tests
============================================================

This test suite validates the performance and scalability of security services:
- Input validation throughput
- Secrets detection performance
- Security audit logging throughput
- Alert processing rate

Run with:
    pytest tests/test_security_load.py -v

For longer stress tests:
    STRESS_TEST=1 pytest tests/test_security_load.py -v
"""

import os
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

# Check for stress test mode
STRESS_TEST = os.environ.get("STRESS_TEST", "").lower() in ("1", "true", "yes")

# Check for AWS E2E test mode (alerts test needs AWS credentials)
RUN_AWS_TESTS = os.environ.get("RUN_AWS_E2E_TESTS", "").lower() in ("1", "true", "yes")


# =============================================================================
# Input Validation Performance Tests
# =============================================================================


class TestInputValidationPerformance:
    """Performance tests for input validation service."""

    @pytest.fixture
    def validator(self):
        """Create input validator instance."""
        from src.services.input_validation_service import InputValidator

        return InputValidator(strict_mode=True)

    def test_sql_injection_detection_throughput(self, validator):
        """Test SQL injection detection throughput."""
        sql_injection_inputs = [
            "SELECT * FROM users WHERE id = '1' OR '1'='1'",
            "'; DROP TABLE users; --",
            "admin'--",
            "1; UPDATE users SET role='admin'",
            "' UNION SELECT password FROM users--",
        ] * 100  # 500 total inputs

        start_time = time.perf_counter()

        for input_text in sql_injection_inputs:
            validator.validate_string(input_text, check_sql_injection=True)

        elapsed = time.perf_counter() - start_time
        throughput = len(sql_injection_inputs) / elapsed

        print("\nSQL Injection Detection Throughput:")
        print(f"  - Inputs processed: {len(sql_injection_inputs)}")
        print(f"  - Time elapsed: {elapsed:.3f}s")
        print(f"  - Throughput: {throughput:.0f} validations/second")

        # Should be able to process at least 1000 validations per second
        assert throughput > 1000, f"Throughput too low: {throughput:.0f}/s"

    def test_xss_detection_throughput(self, validator):
        """Test XSS detection throughput."""
        xss_inputs = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert(document.cookie)",
            "<svg onload=alert(1)>",
            "<body onload=alert('XSS')>",
        ] * 100

        start_time = time.perf_counter()

        for input_text in xss_inputs:
            validator.validate_string(input_text, check_xss=True)

        elapsed = time.perf_counter() - start_time
        throughput = len(xss_inputs) / elapsed

        print("\nXSS Detection Throughput:")
        print(f"  - Inputs processed: {len(xss_inputs)}")
        print(f"  - Time elapsed: {elapsed:.3f}s")
        print(f"  - Throughput: {throughput:.0f} validations/second")

        assert throughput > 1000, f"Throughput too low: {throughput:.0f}/s"

    def test_combined_validation_throughput(self, validator):
        """Test combined validation with all checks enabled."""
        mixed_inputs = [
            "SELECT * FROM users",
            "<script>alert(1)</script>",
            "'; rm -rf /; --",
            "normal input text",
            "../../etc/passwd",
        ] * 50

        start_time = time.perf_counter()

        for input_text in mixed_inputs:
            validator.validate_string(
                input_text,
                check_sql_injection=True,
                check_xss=True,
                check_command_injection=True,
                check_path_traversal=True,
            )

        elapsed = time.perf_counter() - start_time
        throughput = len(mixed_inputs) / elapsed

        print("\nCombined Validation Throughput:")
        print(f"  - Inputs processed: {len(mixed_inputs)}")
        print(f"  - Time elapsed: {elapsed:.3f}s")
        print(f"  - Throughput: {throughput:.0f} validations/second")

        # Combined validation should still be >500/s
        assert throughput > 500, f"Throughput too low: {throughput:.0f}/s"


# =============================================================================
# Secrets Detection Performance Tests
# =============================================================================


class TestSecretsDetectionPerformance:
    """Performance tests for secrets detection service."""

    @pytest.fixture
    def scanner(self):
        """Create secrets scanner instance."""
        from src.services.secrets_detection_service import SecretsDetectionService

        return SecretsDetectionService(enable_entropy_detection=True)

    def test_code_scanning_throughput(self, scanner):
        """Test code scanning throughput."""
        code_samples = (
            [
                """
            def connect_to_db():
                password = "super_secret_123"
                api_key = "AKIAIOSFODNN7EXAMPLE"
                return psycopg2.connect(password=password)
            """,
                """
            # No secrets here
            def calculate_total(items):
                return sum(item.price for item in items)
            """,
                """
            AWS_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
            GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            """,
            ]
            * 50
        )

        start_time = time.perf_counter()

        for code in code_samples:
            scanner.scan_text(code)

        elapsed = time.perf_counter() - start_time
        throughput = len(code_samples) / elapsed

        print("\nSecrets Detection Throughput:")
        print(f"  - Code samples scanned: {len(code_samples)}")
        print(f"  - Time elapsed: {elapsed:.3f}s")
        print(f"  - Throughput: {throughput:.0f} scans/second")

        # Should process at least 100 code samples per second
        assert throughput > 100, f"Throughput too low: {throughput:.0f}/s"

    @pytest.mark.slow
    def test_large_file_scanning(self, scanner):
        """Test scanning performance on large files."""
        # Generate a large code file (~10KB)
        lines = []
        for j in range(500):
            lines.extend(
                [
                    f"def function_{j}():",
                    f"    value_{j} = 'data_{j}'",
                    f"    return value_{j}",
                    "",
                ]
            )
        large_code = "\n".join(lines)

        start_time = time.perf_counter()
        scanner.scan_text(large_code)
        elapsed = time.perf_counter() - start_time

        print("\nLarge File Scanning:")
        print(f"  - File size: {len(large_code):,} bytes")
        print(f"  - Time elapsed: {elapsed:.3f}s")
        print(f"  - Rate: {len(large_code) / elapsed / 1024:.0f} KB/s")

        # Should scan at least 100KB/s
        assert len(large_code) / elapsed > 100_000, "Scanning too slow"


# =============================================================================
# Security Audit Logging Performance Tests
# =============================================================================


class TestSecurityAuditPerformance:
    """Performance tests for security audit logging."""

    def test_audit_logging_throughput(self):
        """Test audit logging throughput."""
        from src.services.security_audit_service import (
            SecurityContext,
            SecurityEventType,
            log_security_event,
        )

        num_events = 1000 if STRESS_TEST else 200

        start_time = time.perf_counter()

        for i in range(num_events):
            log_security_event(
                event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
                message=f"Test login event {i}",
                context=SecurityContext(
                    user_id=f"user-{i % 100}",
                    ip_address=f"192.168.1.{i % 255}",
                    request_id=str(uuid.uuid4()),
                ),
                details={"iteration": i},
            )

        elapsed = time.perf_counter() - start_time
        throughput = num_events / elapsed

        print("\nAudit Logging Throughput:")
        print(f"  - Events logged: {num_events}")
        print(f"  - Time elapsed: {elapsed:.3f}s")
        print(f"  - Throughput: {throughput:.0f} events/second")

        # Should log at least 500 events per second
        assert throughput > 500, f"Throughput too low: {throughput:.0f}/s"

    def test_concurrent_audit_logging(self):
        """Test concurrent audit logging with multiple threads."""
        from src.services.security_audit_service import (
            SecurityContext,
            SecurityEventType,
            log_security_event,
        )

        num_threads = 10
        events_per_thread = 100 if STRESS_TEST else 50
        total_events = num_threads * events_per_thread

        def log_events(thread_id):
            for i in range(events_per_thread):
                log_security_event(
                    event_type=SecurityEventType.DATA_ACCESS,
                    message=f"Thread {thread_id} event {i}",
                    context=SecurityContext(user_id=f"thread-{thread_id}"),
                )

        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(log_events, i) for i in range(num_threads)]
            for future in futures:
                future.result()

        elapsed = time.perf_counter() - start_time
        throughput = total_events / elapsed

        print("\nConcurrent Audit Logging:")
        print(f"  - Threads: {num_threads}")
        print(f"  - Total events: {total_events}")
        print(f"  - Time elapsed: {elapsed:.3f}s")
        print(f"  - Throughput: {throughput:.0f} events/second")

        # Concurrent logging should maintain good throughput
        assert throughput > 1000, f"Throughput too low: {throughput:.0f}/s"


# =============================================================================
# Security Alerts Performance Tests
# =============================================================================


class TestSecurityAlertsPerformance:
    """Performance tests for security alerts service."""

    @pytest.mark.skipif(
        not RUN_AWS_TESTS,
        reason="Alert creation requires AWS credentials (set RUN_AWS_E2E_TESTS=1)",
    )
    def test_alert_creation_throughput(self):
        """Test alert creation throughput."""
        from src.services.security_alerts_service import process_security_event
        from src.services.security_audit_service import (
            SecurityContext,
            SecurityEvent,
            SecurityEventSeverity,
            SecurityEventType,
        )

        num_alerts = 500 if STRESS_TEST else 100

        start_time = time.perf_counter()

        for i in range(num_alerts):
            event = SecurityEvent(
                event_id=f"perf-test-{uuid.uuid4().hex[:12]}",
                event_type=SecurityEventType.INPUT_INJECTION_ATTEMPT,
                severity=SecurityEventSeverity.HIGH,
                timestamp=datetime.now(timezone.utc).isoformat(),
                message=f"Performance test alert {i}",
                context=SecurityContext(
                    user_id=f"perf-user-{i % 100}",
                    ip_address=f"192.168.1.{i % 255}",
                    request_id=str(uuid.uuid4()),
                ),
                details={"test_iteration": i},
            )
            process_security_event(event)

        elapsed = time.perf_counter() - start_time
        throughput = num_alerts / elapsed

        print("\nAlert Creation Throughput:")
        print(f"  - Alerts created: {num_alerts}")
        print(f"  - Time elapsed: {elapsed:.3f}s")
        print(f"  - Throughput: {throughput:.0f} alerts/second")

        # Threshold of 30/s accounts for AWS SDK integration overhead
        # (EventBridge, SNS publishing attempts even in local testing)
        assert throughput > 30, f"Throughput too low: {throughput:.0f}/s"


# =============================================================================
# Latency Distribution Tests
# =============================================================================


class TestSecurityServiceLatency:
    """Latency distribution tests for security services."""

    def test_input_validation_latency_distribution(self):
        """Test input validation latency distribution."""
        from src.services.input_validation_service import InputValidator

        validator = InputValidator(strict_mode=True)
        num_iterations = 1000 if STRESS_TEST else 200
        latencies = []

        test_input = "SELECT * FROM users WHERE id = '1' OR '1'='1'"

        for _ in range(num_iterations):
            start = time.perf_counter()
            validator.validate_string(test_input, check_sql_injection=True)
            latencies.append((time.perf_counter() - start) * 1000)  # Convert to ms

        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)

        print("\nInput Validation Latency Distribution:")
        print(f"  - Iterations: {num_iterations}")
        print(f"  - Average: {avg:.3f}ms")
        print(f"  - P50: {p50:.3f}ms")
        print(f"  - P95: {p95:.3f}ms")
        print(f"  - P99: {p99:.3f}ms")

        # P99 should be under 10ms
        assert p99 < 10, f"P99 latency too high: {p99:.3f}ms"

    def test_secrets_detection_latency_distribution(self):
        """Test secrets detection latency distribution."""
        from src.services.secrets_detection_service import SecretsDetectionService

        scanner = SecretsDetectionService(enable_entropy_detection=True)
        num_iterations = 500 if STRESS_TEST else 100
        latencies = []

        test_code = """
        AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
        AWS_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        """

        for _ in range(num_iterations):
            start = time.perf_counter()
            scanner.scan_text(test_code)
            latencies.append((time.perf_counter() - start) * 1000)

        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)

        print("\nSecrets Detection Latency Distribution:")
        print(f"  - Iterations: {num_iterations}")
        print(f"  - Average: {avg:.3f}ms")
        print(f"  - P50: {p50:.3f}ms")
        print(f"  - P95: {p95:.3f}ms")
        print(f"  - P99: {p99:.3f}ms")

        # P99 should be under 50ms
        assert p99 < 50, f"P99 latency too high: {p99:.3f}ms"


# =============================================================================
# Summary Test
# =============================================================================


def test_performance_summary():
    """Print overall performance summary."""
    print("\n" + "=" * 60)
    print("SECURITY SERVICES PERFORMANCE SUMMARY")
    print("=" * 60)
    print("\nPerformance Targets:")
    print("  - Input Validation: >1000 validations/second")
    print("  - Secrets Detection: >100 scans/second")
    print("  - Audit Logging: >500 events/second")
    print("  - Alert Creation: >30/s (requires RUN_AWS_E2E_TESTS=1)")
    print("  - Input Validation P99: <10ms")
    print("  - Secrets Detection P99: <50ms")
    print("\n" + "=" * 60)
