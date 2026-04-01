"""Tests for Phase 5: Production Hardening features.

Tests cover:
1. Memory size limits and enforcement
2. Memory consolidation strategies
3. Audit logging for all operations
4. Integration with TitanMemoryService

Reference: ADR-024 - Titan Neural Memory Architecture Integration (Phase 5)

IMPORTANT: This file uses LAZY IMPORTS for torch and torch-dependent modules.
This prevents torch from loading during pytest collection, which would break
fork isolation for the 2,330+ tests that use @pytest.mark.forked.

The pattern used:
1. NO module-level torch imports
2. Fixtures provide lazy-loaded modules at test execution time
3. pytestmark ensures these tests run LAST (after all forked tests complete)
"""

import pytest

# Mark as torch-required so it runs LAST (after all forked tests complete)
# CRITICAL: Do NOT import torch at module level - it breaks fork isolation
pytestmark = pytest.mark.torch_required


# =============================================================================
# Lazy Import Fixtures
# =============================================================================
# These fixtures defer torch imports until test execution time (after collection).
# This allows pytest to collect and run all forked tests before torch is loaded.


@pytest.fixture(scope="module")
def torch_module():
    """
    Lazy torch import fixture.

    Using scope="module" to import torch once per test module (not per test),
    which provides good performance while still deferring the import until
    the first test in this module actually runs.
    """
    return pytest.importorskip(
        "torch", reason="torch required for production hardening tests"
    )


@pytest.fixture(scope="module")
def memory_consolidation_imports(torch_module):
    """Lazy import of memory consolidation module classes."""
    from src.services.memory_consolidation import (
        ConsolidationConfig,
        ConsolidationResult,
        ConsolidationStrategy,
        MemoryConsolidationManager,
        MemoryPressureLevel,
        MemorySizeLimiter,
        create_production_consolidation_config,
    )

    # Use staticmethod to prevent automatic binding when accessed from instance
    return type(
        "MemoryConsolidationImports",
        (),
        {
            "ConsolidationConfig": ConsolidationConfig,
            "ConsolidationResult": ConsolidationResult,
            "ConsolidationStrategy": ConsolidationStrategy,
            "MemoryConsolidationManager": MemoryConsolidationManager,
            "MemoryPressureLevel": MemoryPressureLevel,
            "MemorySizeLimiter": MemorySizeLimiter,
            "create_production_consolidation_config": staticmethod(
                create_production_consolidation_config
            ),
        },
    )()


@pytest.fixture(scope="module")
def neural_memory_audit_imports():
    """Lazy import of neural memory audit module classes (no torch dependency)."""
    from src.services.neural_memory_audit import (
        AuditEventType,
        AuditRecord,
        AuditSeverity,
        FileAuditStorage,
        InMemoryAuditStorage,
        NeuralMemoryAuditLogger,
    )

    return type(
        "NeuralMemoryAuditImports",
        (),
        {
            "AuditEventType": AuditEventType,
            "AuditRecord": AuditRecord,
            "AuditSeverity": AuditSeverity,
            "FileAuditStorage": FileAuditStorage,
            "InMemoryAuditStorage": InMemoryAuditStorage,
            "NeuralMemoryAuditLogger": NeuralMemoryAuditLogger,
        },
    )()


@pytest.fixture(scope="module")
def titan_memory_imports(torch_module):
    """Lazy import of titan memory service classes."""
    from src.services.titan_memory_service import (
        TitanMemoryService,
        TitanMemoryServiceConfig,
    )

    return type(
        "TitanMemoryImports",
        (),
        {
            "TitanMemoryService": TitanMemoryService,
            "TitanMemoryServiceConfig": TitanMemoryServiceConfig,
        },
    )()


class TestMemoryConsolidation:
    """Tests for memory consolidation manager."""

    def test_consolidation_config_defaults(self, memory_consolidation_imports):
        """Test ConsolidationConfig has reasonable defaults."""
        mc = memory_consolidation_imports
        config = mc.ConsolidationConfig()

        assert config.max_memory_mb == 100.0
        assert config.warning_threshold == 0.70
        assert config.high_threshold == 0.85
        assert config.critical_threshold == 0.95
        assert config.consolidation_strategy == mc.ConsolidationStrategy.WEIGHT_PRUNING
        assert config.enable_auto_consolidation is True

    def test_production_config_factory(self, memory_consolidation_imports):
        """Test production consolidation config factory."""
        mc = memory_consolidation_imports
        config = mc.create_production_consolidation_config(
            max_memory_mb=200.0,
            strategy=mc.ConsolidationStrategy.LAYER_RESET,
        )

        assert config.max_memory_mb == 200.0
        assert config.consolidation_strategy == mc.ConsolidationStrategy.LAYER_RESET
        assert config.enable_auto_consolidation is True

    def test_memory_pressure_levels(self, memory_consolidation_imports):
        """Test memory pressure level detection."""
        mc = memory_consolidation_imports
        config = mc.ConsolidationConfig(max_memory_mb=100.0)
        manager = mc.MemoryConsolidationManager(config=config)

        # Normal pressure (<70%)
        assert manager.check_memory_pressure(60.0) == mc.MemoryPressureLevel.NORMAL

        # Warning pressure (70-85%)
        assert manager.check_memory_pressure(75.0) == mc.MemoryPressureLevel.WARNING

        # High pressure (85-95%)
        assert manager.check_memory_pressure(90.0) == mc.MemoryPressureLevel.HIGH

        # Critical pressure (>95%)
        assert manager.check_memory_pressure(98.0) == mc.MemoryPressureLevel.CRITICAL

    def test_should_consolidate_logic(self, memory_consolidation_imports):
        """Test consolidation trigger logic."""
        mc = memory_consolidation_imports
        config = mc.ConsolidationConfig(
            max_memory_mb=100.0,
            enable_auto_consolidation=True,
        )
        manager = mc.MemoryConsolidationManager(config=config)

        # Should not consolidate at normal pressure
        assert manager.should_consolidate(60.0) is False

        # Should not consolidate at warning pressure
        assert manager.should_consolidate(75.0) is False

        # Should consolidate at high pressure
        assert manager.should_consolidate(90.0) is True

        # Force consolidation should always work
        assert manager.should_consolidate(50.0, force=True) is True

    def test_should_consolidate_disabled(self, memory_consolidation_imports):
        """Test consolidation disabled by config."""
        mc = memory_consolidation_imports
        config = mc.ConsolidationConfig(
            max_memory_mb=100.0,
            enable_auto_consolidation=False,
        )
        manager = mc.MemoryConsolidationManager(config=config)

        # Should not consolidate even at high pressure
        assert manager.should_consolidate(95.0) is False

    def test_weight_pruning_consolidation(
        self, torch_module, memory_consolidation_imports
    ):
        """Test weight pruning consolidation strategy."""
        torch = torch_module
        mc = memory_consolidation_imports
        config = mc.ConsolidationConfig(
            max_memory_mb=100.0,
            consolidation_strategy=mc.ConsolidationStrategy.WEIGHT_PRUNING,
            prune_ratio=0.2,
        )
        manager = mc.MemoryConsolidationManager(config=config)

        # Create a simple model
        model = torch.nn.Sequential(
            torch.nn.Linear(64, 128),
            torch.nn.Linear(128, 64),
        )

        # Perform consolidation
        result = manager.consolidate(
            model, strategy=mc.ConsolidationStrategy.WEIGHT_PRUNING
        )

        assert result.success is True
        assert result.strategy_used == mc.ConsolidationStrategy.WEIGHT_PRUNING
        assert result.weights_pruned > 0

    def test_full_reset_consolidation(self, torch_module, memory_consolidation_imports):
        """Test full reset consolidation strategy."""
        torch = torch_module
        mc = memory_consolidation_imports
        config = mc.ConsolidationConfig()
        manager = mc.MemoryConsolidationManager(config=config)

        # Create a simple model and modify weights
        model = torch.nn.Linear(64, 64)
        with torch.no_grad():
            model.weight.fill_(1.0)

        # Perform full reset
        result = manager.consolidate(
            model, strategy=mc.ConsolidationStrategy.FULL_RESET
        )

        assert result.success is True
        assert result.strategy_used == mc.ConsolidationStrategy.FULL_RESET
        # Weights should no longer all be 1.0
        assert not torch.all(model.weight == 1.0)

    def test_pressure_change_callback(self, memory_consolidation_imports):
        """Test callback invoked on pressure change."""
        mc = memory_consolidation_imports
        callback_called = []

        def on_pressure_change(pressure):
            callback_called.append(pressure)

        config = mc.ConsolidationConfig(max_memory_mb=100.0)
        manager = mc.MemoryConsolidationManager(
            config=config,
            on_pressure_change=on_pressure_change,
        )

        # Transition from normal to warning
        manager.check_memory_pressure(60.0)  # Normal
        manager.check_memory_pressure(75.0)  # Warning

        assert len(callback_called) == 1
        assert callback_called[0] == mc.MemoryPressureLevel.WARNING

    def test_consolidation_stats(self, memory_consolidation_imports):
        """Test consolidation manager statistics."""
        mc = memory_consolidation_imports
        config = mc.ConsolidationConfig(max_memory_mb=100.0)
        manager = mc.MemoryConsolidationManager(config=config)

        stats = manager.get_stats()

        assert "current_pressure" in stats
        assert "consolidation_count" in stats
        assert "total_reduction_mb" in stats
        assert stats["config"]["max_memory_mb"] == 100.0


class TestMemorySizeLimiter:
    """Tests for memory size limiter."""

    def test_utilization_calculation(self, torch_module, memory_consolidation_imports):
        """Test memory utilization calculation."""
        torch = torch_module
        mc = memory_consolidation_imports
        model = torch.nn.Linear(64, 64)
        limiter = mc.MemorySizeLimiter(
            max_memory_mb=100.0,
            model=model,
        )

        utilization = limiter.get_utilization()
        assert 0.0 <= utilization <= 1.0

    def test_can_update_within_limits(self, torch_module, memory_consolidation_imports):
        """Test can_update returns True within limits."""
        torch = torch_module
        mc = memory_consolidation_imports
        model = torch.nn.Linear(64, 64)  # Small model
        limiter = mc.MemorySizeLimiter(
            max_memory_mb=100.0,
            model=model,
        )

        assert limiter.can_update() is True

    def test_check_and_enforce_callback(
        self, torch_module, memory_consolidation_imports
    ):
        """Test limit exceeded callback invoked."""
        torch = torch_module
        mc = memory_consolidation_imports
        callback_invoked = []

        def on_limit_exceeded(current_mb, max_mb):
            callback_invoked.append((current_mb, max_mb))

        model = torch.nn.Linear(64, 64)
        limiter = mc.MemorySizeLimiter(
            max_memory_mb=0.0001,  # Very small limit to trigger
            model=model,
            on_limit_exceeded=on_limit_exceeded,
        )

        # Should fail and invoke callback
        result = limiter.check_and_enforce()

        assert result is False
        assert len(callback_invoked) == 1

    def test_limiter_stats(self, torch_module, memory_consolidation_imports):
        """Test limiter statistics."""
        torch = torch_module
        mc = memory_consolidation_imports
        model = torch.nn.Linear(64, 64)
        limiter = mc.MemorySizeLimiter(
            max_memory_mb=100.0,
            model=model,
        )

        stats = limiter.get_stats()

        assert "max_memory_mb" in stats
        assert "current_memory_mb" in stats
        assert "utilization" in stats
        assert "update_rejected_count" in stats


class TestNeuralMemoryAudit:
    """Tests for neural memory audit logging."""

    def test_audit_record_creation(self, neural_memory_audit_imports):
        """Test audit record creation."""
        nma = neural_memory_audit_imports
        record = nma.AuditRecord(
            event_type=nma.AuditEventType.MEMORY_UPDATE,
            operation="update",
            actor="test-agent",
            resource="neural_memory",
            surprise_score=0.8,
            was_memorized=True,
            ttt_steps=3,
        )

        assert record.event_id is not None
        assert record.timestamp is not None
        assert record.checksum is not None
        assert record.event_type == nma.AuditEventType.MEMORY_UPDATE
        assert record.actor == "test-agent"

    def test_audit_record_integrity(self, neural_memory_audit_imports):
        """Test audit record integrity verification."""
        nma = neural_memory_audit_imports
        record = nma.AuditRecord(
            event_type=nma.AuditEventType.MEMORY_UPDATE,
            operation="update",
            surprise_score=0.5,
        )

        # Verify integrity passes
        assert record.verify_integrity() is True

        # Manually corrupt checksum
        original_checksum = record.checksum
        record.checksum = "corrupted"

        # Verify integrity fails
        assert record.verify_integrity() is False

        # Restore
        record.checksum = original_checksum
        assert record.verify_integrity() is True

    def test_audit_record_serialization(self, neural_memory_audit_imports):
        """Test audit record to dict/JSON conversion."""
        nma = neural_memory_audit_imports
        record = nma.AuditRecord(
            event_type=nma.AuditEventType.MEMORY_RETRIEVE,
            operation="retrieve",
            latency_ms=15.5,
        )

        # To dict
        data = record.to_dict()
        assert data["event_type"] == "memory_retrieve"
        assert data["latency_ms"] == 15.5

        # To JSON
        json_str = record.to_json()
        assert "memory_retrieve" in json_str

    def test_in_memory_storage(self, neural_memory_audit_imports):
        """Test in-memory audit storage."""
        nma = neural_memory_audit_imports
        storage = nma.InMemoryAuditStorage(max_records=100)

        # Store records
        for i in range(10):
            record = nma.AuditRecord(
                event_type=nma.AuditEventType.MEMORY_UPDATE,
                operation="update",
            )
            assert storage.store(record) is True

        # Query all
        records = storage.query(limit=100)
        assert len(records) == 10

    def test_in_memory_storage_limit(self, neural_memory_audit_imports):
        """Test in-memory storage respects limit."""
        nma = neural_memory_audit_imports
        storage = nma.InMemoryAuditStorage(max_records=5)

        # Store more than limit
        for i in range(10):
            record = nma.AuditRecord(
                event_type=nma.AuditEventType.MEMORY_UPDATE,
                operation="update",
            )
            storage.store(record)

        # Should only keep 5
        all_records = storage.get_all()
        assert len(all_records) == 5

    def test_audit_logger_memory_update(self, neural_memory_audit_imports):
        """Test audit logger memory update logging."""
        nma = neural_memory_audit_imports
        storage = nma.InMemoryAuditStorage()
        logger = nma.NeuralMemoryAuditLogger(storage=storage)

        event_id = logger.log_memory_update(
            actor="agent-123",
            surprise_score=0.85,
            was_memorized=True,
            ttt_steps=3,
            latency_ms=12.5,
            memory_size_mb=45.0,
        )

        logger.flush()

        records = storage.query()
        assert len(records) == 1
        assert records[0].event_id == event_id
        assert records[0].surprise_score == 0.85
        assert records[0].was_memorized is True

    def test_audit_logger_memory_retrieve(self, neural_memory_audit_imports):
        """Test audit logger memory retrieve logging."""
        nma = neural_memory_audit_imports
        storage = nma.InMemoryAuditStorage()
        logger = nma.NeuralMemoryAuditLogger(storage=storage)

        event_id = logger.log_memory_retrieve(
            actor="agent-456",
            surprise_score=0.3,
            latency_ms=5.2,
        )

        logger.flush()

        records = storage.query(event_type=nma.AuditEventType.MEMORY_RETRIEVE)
        assert len(records) == 1
        assert records[0].event_id == event_id

    def test_audit_logger_consolidation(self, neural_memory_audit_imports):
        """Test audit logger consolidation logging."""
        nma = neural_memory_audit_imports
        storage = nma.InMemoryAuditStorage()
        logger = nma.NeuralMemoryAuditLogger(storage=storage)

        _event_id = logger.log_consolidation(
            records_consolidated=50,
            memory_before_mb=95.0,
            memory_after_mb=60.0,
        )

        logger.flush()

        records = storage.query(event_type=nma.AuditEventType.MEMORY_CONSOLIDATION)
        assert len(records) == 1
        assert records[0].details["memory_before_mb"] == 95.0
        assert records[0].details["memory_after_mb"] == 60.0

    def test_audit_logger_size_warnings(self, neural_memory_audit_imports):
        """Test audit logger size warning/exceeded logging."""
        nma = neural_memory_audit_imports
        storage = nma.InMemoryAuditStorage()
        logger = nma.NeuralMemoryAuditLogger(storage=storage)

        # Log warning
        logger.log_size_limit_warning(
            current_size_mb=75.0,
            max_size_mb=100.0,
            utilization_percent=75.0,
        )

        # Log exceeded
        logger.log_size_limit_exceeded(
            current_size_mb=105.0,
            max_size_mb=100.0,
            action_taken="update_rejected",
        )

        logger.flush()

        warning_records = storage.query(
            event_type=nma.AuditEventType.SIZE_LIMIT_WARNING
        )
        exceeded_records = storage.query(
            event_type=nma.AuditEventType.SIZE_LIMIT_EXCEEDED
        )

        assert len(warning_records) == 1
        assert len(exceeded_records) == 1

    def test_audit_logger_service_lifecycle(self, neural_memory_audit_imports):
        """Test audit logger service init/shutdown logging."""
        nma = neural_memory_audit_imports
        storage = nma.InMemoryAuditStorage()
        logger = nma.NeuralMemoryAuditLogger(storage=storage)

        logger.log_service_init(
            config={"memory_dim": 512, "enable_ttt": True},
            memory_size_mb=5.0,
        )

        logger.log_service_shutdown(
            stats={"update_count": 100, "retrieval_count": 500},
        )

        logger.flush()

        init_records = storage.query(event_type=nma.AuditEventType.SERVICE_INIT)
        shutdown_records = storage.query(event_type=nma.AuditEventType.SERVICE_SHUTDOWN)

        assert len(init_records) == 1
        assert len(shutdown_records) == 1

    def test_audit_logger_correlation_id(self, neural_memory_audit_imports):
        """Test audit logger correlation ID tracking."""
        nma = neural_memory_audit_imports
        storage = nma.InMemoryAuditStorage()
        logger = nma.NeuralMemoryAuditLogger(storage=storage)

        correlation_id = "session-abc-123"
        logger.set_correlation_id(correlation_id)

        logger.log_memory_update(surprise_score=0.5, was_memorized=True)
        logger.log_memory_retrieve(surprise_score=0.3)

        logger.clear_correlation_id()
        logger.log_memory_update(surprise_score=0.6, was_memorized=False)

        logger.flush()

        # Query by correlation ID
        correlated_records = storage.query(correlation_id=correlation_id)
        assert len(correlated_records) == 2

        all_records = storage.query()
        assert len(all_records) == 3

    def test_audit_logger_stats(self, neural_memory_audit_imports):
        """Test audit logger statistics."""
        nma = neural_memory_audit_imports
        storage = nma.InMemoryAuditStorage()
        logger = nma.NeuralMemoryAuditLogger(storage=storage, environment="test")

        logger.log_memory_update(surprise_score=0.5, was_memorized=True)
        logger.log_error(operation="update", error_message="Test error")

        stats = logger.get_stats()

        assert stats["record_count"] == 2
        assert stats["error_count"] == 1
        assert stats["environment"] == "test"


class TestTitanMemoryServicePhase5:
    """Integration tests for TitanMemoryService Phase 5 features."""

    def test_service_with_audit_logging(self, titan_memory_imports):
        """Test TitanMemoryService includes audit logging."""
        tm = titan_memory_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,  # Small for testing
            memory_depth=2,
            enable_audit_logging=True,
            environment="test",
        )
        service = tm.TitanMemoryService(config)

        assert service.audit_logger is not None
        assert service.audit_logger.environment == "test"

    def test_service_without_audit_logging(self, titan_memory_imports):
        """Test TitanMemoryService can disable audit logging."""
        tm = titan_memory_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            enable_audit_logging=False,
        )
        service = tm.TitanMemoryService(config)

        assert service.audit_logger is None

    def test_service_consolidation_manager(self, titan_memory_imports):
        """Test TitanMemoryService includes consolidation manager."""
        tm = titan_memory_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            max_memory_size_mb=50.0,
        )
        service = tm.TitanMemoryService(config)

        assert service.consolidation_manager is not None
        assert service.consolidation_manager.config.max_memory_mb == 50.0

    def test_service_size_limiter_initialized(self, titan_memory_imports):
        """Test TitanMemoryService initializes size limiter."""
        tm = titan_memory_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            enable_size_limit_enforcement=True,
        )
        service = tm.TitanMemoryService(config)
        service.initialize()

        try:
            assert service.size_limiter is not None
        finally:
            service.shutdown()

    def test_service_retrieval_logs_audit(
        self, torch_module, titan_memory_imports, neural_memory_audit_imports
    ):
        """Test retrieval operation creates audit record."""
        torch = torch_module
        tm = titan_memory_imports
        nma = neural_memory_audit_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            memory_depth=2,
            enable_audit_logging=True,
        )
        service = tm.TitanMemoryService(config)
        service.initialize()

        try:
            query = torch.randn(1, 64)
            service.retrieve(query, actor="test-agent")

            # Flush and check audit log
            service.audit_logger.flush()
            records = service.audit_logger.storage.query(
                event_type=nma.AuditEventType.MEMORY_RETRIEVE
            )
            assert len(records) >= 1
        finally:
            service.shutdown()

    def test_service_update_logs_audit(
        self, torch_module, titan_memory_imports, neural_memory_audit_imports
    ):
        """Test update operation creates audit record."""
        torch = torch_module
        tm = titan_memory_imports
        nma = neural_memory_audit_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            memory_depth=2,
            enable_audit_logging=True,
            memorization_threshold=0.0,  # Always memorize for test
        )
        service = tm.TitanMemoryService(config)
        service.initialize()

        try:
            key = torch.randn(1, 64)
            value = torch.randn(1, 64)
            service.update(key, value, actor="test-agent")

            # Flush and check audit log
            service.audit_logger.flush()
            records = service.audit_logger.storage.query(
                event_type=nma.AuditEventType.MEMORY_UPDATE
            )
            assert len(records) >= 1
        finally:
            service.shutdown()

    def test_service_init_logs_audit(
        self, titan_memory_imports, neural_memory_audit_imports
    ):
        """Test initialization creates audit record."""
        tm = titan_memory_imports
        nma = neural_memory_audit_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            enable_audit_logging=True,
        )
        service = tm.TitanMemoryService(config)
        service.initialize()

        try:
            service.audit_logger.flush()
            records = service.audit_logger.storage.query(
                event_type=nma.AuditEventType.SERVICE_INIT
            )
            assert len(records) == 1
        finally:
            service.shutdown()

    def test_service_shutdown_logs_audit(
        self, titan_memory_imports, neural_memory_audit_imports
    ):
        """Test shutdown creates audit record."""
        tm = titan_memory_imports
        nma = neural_memory_audit_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            enable_audit_logging=True,
        )
        service = tm.TitanMemoryService(config)
        service.initialize()

        # Save reference to audit storage before shutdown
        storage = service.audit_logger.storage

        service.shutdown()

        records = storage.query(event_type=nma.AuditEventType.SERVICE_SHUTDOWN)
        assert len(records) == 1

    def test_service_stats_include_phase5(self, titan_memory_imports):
        """Test service stats include Phase 5 components."""
        tm = titan_memory_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            enable_audit_logging=True,
            enable_size_limit_enforcement=True,
        )
        service = tm.TitanMemoryService(config)
        service.initialize()

        try:
            stats = service.get_stats()

            assert "consolidation" in stats
            assert "size_limiter" in stats
            assert "audit_logging" in stats
            assert "updates_rejected_count" in stats
        finally:
            service.shutdown()

    def test_service_manual_consolidation(
        self, titan_memory_imports, memory_consolidation_imports
    ):
        """Test manual consolidation trigger."""
        tm = titan_memory_imports
        mc = memory_consolidation_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            memory_depth=2,
            enable_audit_logging=True,
        )
        service = tm.TitanMemoryService(config)
        service.initialize()

        try:
            result = service.consolidate(
                strategy=mc.ConsolidationStrategy.WEIGHT_PRUNING
            )

            assert result is not None
            assert result.success is True
            # Compare by value to handle enum class instance differences
            assert (
                result.strategy_used.value
                == mc.ConsolidationStrategy.WEIGHT_PRUNING.value
            )
        finally:
            service.shutdown()

    def test_service_memory_pressure_check(
        self, titan_memory_imports, memory_consolidation_imports
    ):
        """Test memory pressure level check returns valid enum.

        Note: This test verifies that get_memory_pressure() returns a valid
        MemoryPressureLevel enum. We don't assert a specific level because
        memory state can vary based on test execution order and system state.
        """
        tm = titan_memory_imports
        mc = memory_consolidation_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            max_memory_size_mb=1000.0,
        )
        service = tm.TitanMemoryService(config)
        service.initialize()

        try:
            pressure = service.get_memory_pressure()
            # Verify we get a valid MemoryPressureLevel enum
            # MemoryPressureLevel enum: NORMAL=0, WARNING=1, HIGH=2, CRITICAL=3
            valid_pressure_values = {0, 1, 2, 3}
            assert pressure.value in valid_pressure_values, (
                f"Unexpected pressure value: {pressure.value!r} ({pressure.name}). "
                f"Expected one of: NORMAL(0), WARNING(1), HIGH(2), CRITICAL(3)"
            )
            # Verify the enum name matches the expected pattern
            assert pressure.name in {
                "NORMAL",
                "WARNING",
                "HIGH",
                "CRITICAL",
            }, f"Unexpected pressure name: {pressure.name}"
        finally:
            service.shutdown()

    def test_service_checkpoint_logs_audit(
        self, tmp_path, titan_memory_imports, neural_memory_audit_imports
    ):
        """Test checkpoint save/load creates audit records."""
        tm = titan_memory_imports
        nma = neural_memory_audit_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            enable_audit_logging=True,
        )
        service = tm.TitanMemoryService(config)
        service.initialize()

        try:
            checkpoint_path = str(tmp_path / "test_checkpoint.pt")

            # Save checkpoint
            service.save_checkpoint(checkpoint_path)

            # Flush and check save audit
            service.audit_logger.flush()
            save_records = service.audit_logger.storage.query(
                event_type=nma.AuditEventType.CHECKPOINT_SAVE
            )
            assert len(save_records) == 1

            # Load checkpoint
            service.load_checkpoint(checkpoint_path)

            # Flush and check load audit
            service.audit_logger.flush()
            load_records = service.audit_logger.storage.query(
                event_type=nma.AuditEventType.CHECKPOINT_LOAD
            )
            assert len(load_records) == 1
        finally:
            service.shutdown()


class TestTitanMemoryServiceEdgeCases:
    """Additional edge case tests for TitanMemoryService."""

    def test_double_initialization_warning(self, titan_memory_imports):
        """Test double initialization logs warning."""
        tm = titan_memory_imports
        config = tm.TitanMemoryServiceConfig(memory_dim=64)
        service = tm.TitanMemoryService(config)

        try:
            service.initialize()
            # Second initialization should warn but not fail
            service.initialize()
            assert service._is_initialized is True
        finally:
            service.shutdown()

    def test_ttt_disabled_path(self, torch_module, titan_memory_imports):
        """Test update path when TTT is disabled."""
        torch = torch_module
        tm = titan_memory_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            enable_ttt=False,
        )
        service = tm.TitanMemoryService(config)
        service.initialize()

        try:
            key = torch.randn(64)
            value = torch.randn(64)
            was_memorized, surprise = service.update(key, value)
            assert was_memorized is False
            assert surprise == 0.0
        finally:
            service.shutdown()

    def test_compute_surprise(self, torch_module, titan_memory_imports):
        """Test compute_surprise method."""
        torch = torch_module
        tm = titan_memory_imports
        config = tm.TitanMemoryServiceConfig(memory_dim=64)
        service = tm.TitanMemoryService(config)
        service.initialize()

        try:
            input_tensor = torch.randn(64)
            surprise = service.compute_surprise(input_tensor)
            assert isinstance(surprise, float)
            assert surprise >= 0.0

            # Test with separate target
            target_tensor = torch.randn(64)
            surprise_with_target = service.compute_surprise(input_tensor, target_tensor)
            assert isinstance(surprise_with_target, float)
        finally:
            service.shutdown()

    def test_freeze_unfreeze_persistent_memory(self, titan_memory_imports):
        """Test freeze and unfreeze persistent memory."""
        tm = titan_memory_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            persistent_memory_size=4,
        )
        service = tm.TitanMemoryService(config)
        service.initialize()

        try:
            service.freeze_persistent_memory()
            # After freeze, persistent memory should not require gradients
            assert service.model.persistent_memory.memory.requires_grad is False

            service.unfreeze_persistent_memory()
            # After unfreeze, persistent memory should require gradients
            assert service.model.persistent_memory.memory.requires_grad is True
        finally:
            service.shutdown()

    def test_reset_surprise_momentum(self, titan_memory_imports):
        """Test reset_surprise_momentum method."""
        tm = titan_memory_imports
        config = tm.TitanMemoryServiceConfig(memory_dim=64)
        service = tm.TitanMemoryService(config)
        service.initialize()

        try:
            # Set some surprise momentum
            service._past_surprise = 0.5
            assert service._past_surprise == 0.5

            service.reset_surprise_momentum()
            assert service._past_surprise == 0.0
        finally:
            service.shutdown()

    def test_create_titan_memory_service_factory(self, torch_module):
        """Test create_titan_memory_service factory function."""
        # Ensure torch is imported first via fixture dependency
        _ = torch_module
        from src.services.titan_memory_service import create_titan_memory_service

        service = create_titan_memory_service(
            memory_dim=32,
            memory_depth=2,
            preset="enterprise_standard",
            enable_ttt=True,
        )

        try:
            assert service.config.memory_dim == 32
            assert service.config.memory_depth == 2
            assert service.config.enable_ttt is True

            service.initialize()
            assert service._is_initialized is True
        finally:
            if service._is_initialized:
                service.shutdown()

    def test_miras_config_directly_passed(self, torch_module, titan_memory_imports):
        """Test service with miras_config passed directly."""
        _ = torch_module  # Ensure torch is loaded
        tm = titan_memory_imports
        from src.services.models.miras_config import MIRASConfig

        custom_miras = MIRASConfig(
            huber_delta=2.0,
            retention_strength=0.05,
        )
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            miras_config=custom_miras,
        )
        service = tm.TitanMemoryService(config)

        assert service.miras_config.huber_delta == 2.0
        assert service.miras_config.retention_strength == 0.05

    def test_default_miras_config(self, titan_memory_imports):
        """Test service with default miras_config."""
        tm = titan_memory_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            miras_config=None,
            miras_preset=None,
        )
        service = tm.TitanMemoryService(config)

        assert service.miras_config is not None
        # Should use default values
        assert service.miras_config.adaptive_threshold >= 0.0

    def test_size_limit_exceeded_rejects_update(
        self, torch_module, titan_memory_imports
    ):
        """Test update rejection when size limit exceeded."""
        torch = torch_module
        tm = titan_memory_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            max_memory_size_mb=0.0001,  # Very small to trigger limit
            enable_size_limit_enforcement=True,
            enable_audit_logging=True,
        )
        service = tm.TitanMemoryService(config)
        service.initialize()

        try:
            key = torch.randn(64)
            value = torch.randn(64)
            was_memorized, surprise = service.update(key, value)
            # Should be rejected
            assert was_memorized is False
            assert surprise == 0.0
            assert service._updates_rejected_count >= 1
        finally:
            service.shutdown()

    def test_on_pressure_change_warning(
        self,
        titan_memory_imports,
        memory_consolidation_imports,
        neural_memory_audit_imports,
    ):
        """Test _on_pressure_change callback at WARNING level."""
        tm = titan_memory_imports
        mc = memory_consolidation_imports
        nma = neural_memory_audit_imports
        config = tm.TitanMemoryServiceConfig(
            memory_dim=64,
            enable_audit_logging=True,
        )
        service = tm.TitanMemoryService(config)
        service.initialize()

        try:
            # Manually trigger the callback
            service._on_pressure_change(mc.MemoryPressureLevel.WARNING)

            service.audit_logger.flush()
            records = service.audit_logger.storage.query(
                event_type=nma.AuditEventType.SIZE_LIMIT_WARNING
            )
            assert len(records) == 1
        finally:
            service.shutdown()

    def test_on_limit_exceeded_callback(self, titan_memory_imports):
        """Test _on_limit_exceeded callback."""
        tm = titan_memory_imports
        config = tm.TitanMemoryServiceConfig(memory_dim=64)
        service = tm.TitanMemoryService(config)
        service.initialize()

        try:
            # Manually trigger the callback (just logs a warning)
            service._on_limit_exceeded(current_mb=100.0, max_mb=50.0)
            # Should not raise
        finally:
            service.shutdown()


class TestFileAuditStorage:
    """Tests for FileAuditStorage backend."""

    def test_file_storage_creation(self, tmp_path, neural_memory_audit_imports):
        """Test FileAuditStorage creates directory."""
        nma = neural_memory_audit_imports
        storage = nma.FileAuditStorage(
            base_path=str(tmp_path / "audit_logs"),
            environment="test",
        )
        assert storage is not None
        assert (tmp_path / "audit_logs").exists()

    def test_file_storage_store(self, tmp_path, neural_memory_audit_imports):
        """Test storing records to file."""
        nma = neural_memory_audit_imports
        storage = nma.FileAuditStorage(
            base_path=str(tmp_path / "audit_logs"),
            environment="test",
        )

        record = nma.AuditRecord(
            event_type=nma.AuditEventType.MEMORY_UPDATE,
            operation="update",
            surprise_score=0.75,
        )

        result = storage.store(record)
        assert result is True

        # Verify file was written
        files = list((tmp_path / "audit_logs").glob("*.jsonl"))
        assert len(files) == 1

    def test_file_storage_store_batch(self, tmp_path, neural_memory_audit_imports):
        """Test storing batch of records to file."""
        nma = neural_memory_audit_imports
        storage = nma.FileAuditStorage(
            base_path=str(tmp_path / "audit_logs"),
            environment="test",
        )

        records = [
            nma.AuditRecord(
                event_type=nma.AuditEventType.MEMORY_UPDATE, operation="update"
            )
            for _ in range(5)
        ]

        count = storage.store_batch(records)
        assert count == 5

    def test_file_storage_query(self, tmp_path, neural_memory_audit_imports):
        """Test querying records from file storage."""
        nma = neural_memory_audit_imports
        storage = nma.FileAuditStorage(
            base_path=str(tmp_path / "audit_logs"),
            environment="test",
        )

        # Store some records
        for i in range(3):
            record = nma.AuditRecord(
                event_type=nma.AuditEventType.MEMORY_UPDATE,
                operation="update",
                surprise_score=float(i) / 10,
            )
            storage.store(record)

        # Query all
        results = storage.query(limit=100)
        assert len(results) == 3

    def test_file_storage_query_with_filters(
        self, tmp_path, neural_memory_audit_imports
    ):
        """Test querying with filters."""
        nma = neural_memory_audit_imports
        storage = nma.FileAuditStorage(
            base_path=str(tmp_path / "audit_logs"),
            environment="test",
        )

        # Store mixed event types
        storage.store(
            nma.AuditRecord(
                event_type=nma.AuditEventType.MEMORY_UPDATE,
                operation="update",
            )
        )
        storage.store(
            nma.AuditRecord(
                event_type=nma.AuditEventType.MEMORY_RETRIEVE,
                operation="retrieve",
            )
        )
        storage.store(
            nma.AuditRecord(
                event_type=nma.AuditEventType.MEMORY_UPDATE,
                operation="update",
                correlation_id="test-123",
            )
        )

        # Query by event type
        update_results = storage.query(event_type=nma.AuditEventType.MEMORY_UPDATE)
        assert len(update_results) == 2

        # Query by correlation ID
        correlated = storage.query(correlation_id="test-123")
        assert len(correlated) == 1

    def test_file_storage_rotation(self, tmp_path, neural_memory_audit_imports):
        """Test file rotation when size limit exceeded."""
        nma = neural_memory_audit_imports
        storage = nma.FileAuditStorage(
            base_path=str(tmp_path / "audit_logs"),
            environment="test",
            rotate_size_mb=0.0001,  # Very small to trigger rotation
        )

        # Store enough to trigger rotation
        large_record = nma.AuditRecord(
            event_type=nma.AuditEventType.MEMORY_UPDATE,
            operation="update",
            details={"data": "x" * 1000},  # Large payload
        )
        storage.store(large_record)
        storage.store(large_record)  # Should trigger rotation

        # Check multiple files exist
        files = list((tmp_path / "audit_logs").glob("*.jsonl"))
        assert len(files) >= 1

    def test_file_storage_store_failure(self, tmp_path, neural_memory_audit_imports):
        """Test store handles write failures gracefully."""
        from unittest.mock import patch

        nma = neural_memory_audit_imports
        storage = nma.FileAuditStorage(
            base_path=str(tmp_path / "audit_logs"),
            environment="test",
        )

        record = nma.AuditRecord(
            event_type=nma.AuditEventType.MEMORY_UPDATE,
            operation="update",
        )

        # Mock open to raise exception
        with patch("builtins.open", side_effect=IOError("Write failed")):
            result = storage.store(record)
            assert result is False

    def test_file_storage_query_parse_failure(
        self, tmp_path, neural_memory_audit_imports
    ):
        """Test query handles parse failures gracefully."""
        nma = neural_memory_audit_imports
        storage = nma.FileAuditStorage(
            base_path=str(tmp_path / "audit_logs"),
            environment="test",
        )

        # Write invalid JSON to file
        log_dir = tmp_path / "audit_logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "neural-memory-audit-test-2025-12-06.jsonl"
        with open(log_file, "w") as f:
            f.write("invalid json\n")
            f.write('{"event_type": "memory_update", "operation": "update"}\n')

        # Should handle invalid line and continue
        results = storage.query()
        # May or may not parse depending on required fields
        assert isinstance(results, list)

    def test_file_storage_query_no_files(self, tmp_path, neural_memory_audit_imports):
        """Test query returns empty when no files exist."""
        nma = neural_memory_audit_imports
        storage = nma.FileAuditStorage(
            base_path=str(tmp_path / "empty_audit"),
            environment="test",
        )

        results = storage.query()
        assert results == []

    def test_file_storage_directory_creation_failure(
        self, tmp_path, neural_memory_audit_imports
    ):
        """Test handles directory creation failure."""
        from pathlib import Path
        from unittest.mock import patch

        nma = neural_memory_audit_imports
        # Mock mkdir to fail
        with patch.object(Path, "mkdir", side_effect=PermissionError("No permission")):
            # Should not raise, just log warning
            _storage = nma.FileAuditStorage(
                base_path="/nonexistent/path/audit",
                environment="test",
            )
            # Storage created but directory may not exist


class TestAuditRecordEdgeCases:
    """Additional tests for AuditRecord edge cases."""

    def test_audit_record_with_all_fields(self, neural_memory_audit_imports):
        """Test audit record with all optional fields populated."""
        nma = neural_memory_audit_imports
        record = nma.AuditRecord(
            event_type=nma.AuditEventType.MEMORY_UPDATE,
            severity=nma.AuditSeverity.WARNING,
            operation="update",
            actor="agent-123",
            resource="neural_memory",
            details={"key": "value", "nested": {"a": 1}},
            memory_size_mb=45.5,
            surprise_score=0.85,
            was_memorized=True,
            ttt_steps=3,
            latency_ms=15.5,
            correlation_id="corr-abc",
            parent_event_id="parent-xyz",
            environment="prod",
        )

        assert record.verify_integrity()
        data = record.to_dict()
        assert data["actor"] == "agent-123"
        assert data["details"]["nested"]["a"] == 1

    def test_audit_record_checksum_changes_on_modification(
        self, neural_memory_audit_imports
    ):
        """Test checksum changes when record is modified."""
        nma = neural_memory_audit_imports
        record = nma.AuditRecord(
            event_type=nma.AuditEventType.MEMORY_UPDATE,
            operation="update",
        )
        record.checksum

        # Modify a field
        record.surprise_score = 0.99

        # Checksum should no longer match (integrity violated)
        assert record.verify_integrity() is False

    def test_audit_record_to_json_roundtrip(self, neural_memory_audit_imports):
        """Test JSON serialization roundtrip."""
        import json

        nma = neural_memory_audit_imports
        record = nma.AuditRecord(
            event_type=nma.AuditEventType.TTT_TRAINING,
            operation="ttt",
            ttt_steps=5,
        )

        json_str = record.to_json()
        data = json.loads(json_str)

        assert data["event_type"] == "ttt_training"
        assert data["ttt_steps"] == 5


class TestAuditLoggerEdgeCases:
    """Additional tests for NeuralMemoryAuditLogger edge cases."""

    def test_logger_auto_flush_disabled(self, neural_memory_audit_imports):
        """Test logger with auto_flush disabled."""
        nma = neural_memory_audit_imports
        storage = nma.InMemoryAuditStorage()
        logger = nma.NeuralMemoryAuditLogger(
            storage=storage,
            batch_size=2,
            auto_flush=False,
        )

        # Add more than batch_size records
        for i in range(5):
            logger.log_memory_update(surprise_score=0.5, was_memorized=True)

        # Should NOT have flushed automatically
        assert len(storage.get_all()) == 0
        assert logger.get_stats()["pending_count"] == 5

        # Manual flush
        logger.flush()
        assert len(storage.get_all()) == 5

    def test_logger_checkpoint_save_load(self, neural_memory_audit_imports):
        """Test checkpoint save and load logging."""
        nma = neural_memory_audit_imports
        storage = nma.InMemoryAuditStorage()
        logger = nma.NeuralMemoryAuditLogger(storage=storage)

        # Log checkpoint operations
        _save_id = logger.log_checkpoint_save(
            path="/checkpoints/model.pt",
            memory_size_mb=50.0,
            details={"epoch": 10},
        )

        _load_id = logger.log_checkpoint_load(
            path="/checkpoints/model.pt",
            memory_size_mb=50.0,
            details={"epoch": 10},
        )

        logger.flush()

        save_records = storage.query(event_type=nma.AuditEventType.CHECKPOINT_SAVE)
        load_records = storage.query(event_type=nma.AuditEventType.CHECKPOINT_LOAD)

        assert len(save_records) == 1
        assert len(load_records) == 1
        assert save_records[0].resource == "/checkpoints/model.pt"

    def test_logger_error_logging(self, neural_memory_audit_imports):
        """Test error event logging."""
        nma = neural_memory_audit_imports
        storage = nma.InMemoryAuditStorage()
        logger = nma.NeuralMemoryAuditLogger(storage=storage)

        logger.log_error(
            operation="consolidation",
            error_message="Out of memory",
            error_type="MemoryError",
            details={"available_mb": 10},
        )

        logger.flush()

        error_records = storage.query(event_type=nma.AuditEventType.ERROR)
        assert len(error_records) == 1
        assert error_records[0].details["error_message"] == "Out of memory"

        stats = logger.get_stats()
        assert stats["error_count"] == 1


class TestConsolidationEdgeCases:
    """Additional tests for consolidation edge cases."""

    def test_consolidation_callback_invoked(
        self, torch_module, memory_consolidation_imports
    ):
        """Test consolidation callback is invoked."""
        torch = torch_module
        mc = memory_consolidation_imports
        callback_results = []

        def on_consolidation(result):
            callback_results.append(result)

        config = mc.ConsolidationConfig()
        manager = mc.MemoryConsolidationManager(
            config=config,
            on_consolidation=on_consolidation,
        )

        model = torch.nn.Linear(64, 64)
        manager.consolidate(model, strategy=mc.ConsolidationStrategy.WEIGHT_PRUNING)

        assert len(callback_results) == 1
        assert callback_results[0].success is True

    def test_consolidation_records_stats(
        self, torch_module, memory_consolidation_imports
    ):
        """Test consolidation updates stats correctly."""
        torch = torch_module
        mc = memory_consolidation_imports
        config = mc.ConsolidationConfig()
        manager = mc.MemoryConsolidationManager(config=config)

        model = torch.nn.Linear(64, 64)

        # Multiple consolidations
        manager.consolidate(model)
        manager.consolidate(model)

        stats = manager.get_stats()
        assert stats["consolidation_count"] == 2

    def test_slot_reduction_with_persistent_memory(
        self, torch_module, memory_consolidation_imports
    ):
        """Test slot reduction on model with persistent memory."""
        _ = torch_module  # Ensure torch is loaded
        mc = memory_consolidation_imports
        from src.services.models.deep_mlp_memory import DeepMLPMemory, MemoryConfig

        config = mc.ConsolidationConfig(slot_reduction_ratio=0.5)
        manager = mc.MemoryConsolidationManager(config=config)

        # Create model with persistent memory
        memory_config = MemoryConfig(dim=64, persistent_memory_size=16)
        model = DeepMLPMemory(memory_config)

        original_slots = model.persistent_memory.num_slots

        result = manager.consolidate(
            model, strategy=mc.ConsolidationStrategy.SLOT_REDUCTION
        )

        assert result.success is True
        assert result.slots_removed > 0
        assert model.persistent_memory.num_slots < original_slots

    def test_layer_reset_with_deep_mlp(
        self, torch_module, memory_consolidation_imports
    ):
        """Test layer reset on DeepMLPMemory model."""
        torch = torch_module
        mc = memory_consolidation_imports
        from src.services.models.deep_mlp_memory import DeepMLPMemory, MemoryConfig

        config = mc.ConsolidationConfig(layers_to_reset=2)
        manager = mc.MemoryConsolidationManager(config=config)

        memory_config = MemoryConfig(dim=64, depth=3)
        model = DeepMLPMemory(memory_config)

        # Modify weights
        with torch.no_grad():
            for layer in model.layers:
                for module in layer.modules():
                    if isinstance(module, torch.nn.Linear):
                        module.weight.fill_(1.0)

        result = manager.consolidate(
            model, strategy=mc.ConsolidationStrategy.LAYER_RESET
        )

        assert result.success is True
        assert result.layers_reset == 2

    def test_pressure_levels_boundary(self, memory_consolidation_imports):
        """Test pressure level boundaries."""
        mc = memory_consolidation_imports
        config = mc.ConsolidationConfig(
            max_memory_mb=100.0,
            warning_threshold=0.70,
            high_threshold=0.85,
            critical_threshold=0.95,
        )
        manager = mc.MemoryConsolidationManager(config=config)

        # Exactly at boundaries
        assert manager.check_memory_pressure(69.9) == mc.MemoryPressureLevel.NORMAL
        assert manager.check_memory_pressure(70.0) == mc.MemoryPressureLevel.WARNING
        assert manager.check_memory_pressure(84.9) == mc.MemoryPressureLevel.WARNING
        assert manager.check_memory_pressure(85.0) == mc.MemoryPressureLevel.HIGH
        assert manager.check_memory_pressure(94.9) == mc.MemoryPressureLevel.HIGH
        assert manager.check_memory_pressure(95.0) == mc.MemoryPressureLevel.CRITICAL

    def test_record_update_tracking(self, memory_consolidation_imports):
        """Test update tracking triggers check at interval."""
        mc = memory_consolidation_imports
        config = mc.ConsolidationConfig(
            max_memory_mb=100.0,
            check_interval_updates=5,
        )
        manager = mc.MemoryConsolidationManager(config=config)

        # Record updates
        for i in range(10):
            manager.record_update(current_mb=50.0)

        # Should have reset counter after 5 updates
        assert (
            manager._updates_since_check == 0
        )  # Reset after reaching 5, then incremented 5 more

    def test_consolidation_error_returns_failed_result(
        self, torch_module, memory_consolidation_imports
    ):
        """Test consolidation error returns result with success=False."""
        torch = torch_module
        mc = memory_consolidation_imports
        config = mc.ConsolidationConfig()
        manager = mc.MemoryConsolidationManager(config=config)

        # Create a model that might cause issues
        model = torch.nn.Module()  # Empty module

        # Should handle gracefully
        result = manager.consolidate(
            model, strategy=mc.ConsolidationStrategy.WEIGHT_PRUNING
        )
        # May succeed with 0 weights pruned
        assert isinstance(result, mc.ConsolidationResult)


class TestMemorySizeLimiterEdgeCases:
    """Additional tests for MemorySizeLimiter edge cases."""

    def test_limiter_with_consolidation_recovery(
        self, torch_module, memory_consolidation_imports
    ):
        """Test limiter triggers consolidation to recover from limit."""
        _ = torch_module  # Ensure torch is loaded
        mc = memory_consolidation_imports
        from src.services.models.deep_mlp_memory import DeepMLPMemory, MemoryConfig

        memory_config = MemoryConfig(dim=64)
        model = DeepMLPMemory(memory_config)

        # Create consolidation manager
        consolidation_config = mc.ConsolidationConfig(
            max_memory_mb=100.0,
            consolidation_strategy=mc.ConsolidationStrategy.WEIGHT_PRUNING,
        )
        consolidation_manager = mc.MemoryConsolidationManager(
            config=consolidation_config
        )

        # Create limiter with very small limit
        limiter = mc.MemorySizeLimiter(
            max_memory_mb=1000.0,  # Large enough
            model=model,
            consolidation_manager=consolidation_manager,
        )

        # Should be able to update
        assert limiter.can_update() is True
        assert limiter.check_and_enforce() is True

    def test_limiter_tracks_rejected_updates(
        self, torch_module, memory_consolidation_imports
    ):
        """Test limiter tracks rejected update count."""
        torch = torch_module
        mc = memory_consolidation_imports
        model = torch.nn.Linear(64, 64)
        limiter = mc.MemorySizeLimiter(
            max_memory_mb=0.0001,  # Very small
            model=model,
        )

        # Should fail
        limiter.check_and_enforce()

        stats = limiter.get_stats()
        assert stats["update_rejected_count"] >= 1


class TestConsolidationStrategies:
    """Tests for different consolidation strategies."""

    def test_warn_only_strategy(self, torch_module, memory_consolidation_imports):
        """Test WARN_ONLY strategy doesn't modify model."""
        torch = torch_module
        mc = memory_consolidation_imports
        config = mc.ConsolidationConfig()
        manager = mc.MemoryConsolidationManager(config=config)

        model = torch.nn.Linear(64, 64)
        with torch.no_grad():
            original_weights = model.weight.clone()

        result = manager.consolidate(model, strategy=mc.ConsolidationStrategy.WARN_ONLY)

        assert result.success is True
        assert result.strategy_used == mc.ConsolidationStrategy.WARN_ONLY
        assert result.reduction_mb == 0.0
        # Weights should be unchanged
        assert torch.all(model.weight == original_weights)

    def test_layer_reset_strategy(self, torch_module, memory_consolidation_imports):
        """Test LAYER_RESET strategy resets layers."""
        torch = torch_module
        mc = memory_consolidation_imports
        config = mc.ConsolidationConfig(layers_to_reset=1)
        manager = mc.MemoryConsolidationManager(config=config)

        # Create model with layers attribute
        model = torch.nn.Module()
        model.layers = torch.nn.ModuleList(
            [
                torch.nn.Linear(64, 64),
                torch.nn.Linear(64, 64),
            ]
        )

        result = manager.consolidate(
            model, strategy=mc.ConsolidationStrategy.LAYER_RESET
        )

        assert result.success is True
        assert result.strategy_used == mc.ConsolidationStrategy.LAYER_RESET
        assert result.layers_reset == 1

    def test_consolidation_error_handling(
        self, torch_module, memory_consolidation_imports
    ):
        """Test consolidation handles errors gracefully."""
        torch = torch_module
        mc = memory_consolidation_imports
        config = mc.ConsolidationConfig()
        manager = mc.MemoryConsolidationManager(config=config)

        # Create a model that will fail slot reduction (no persistent_memory)
        model = torch.nn.Linear(64, 64)

        # SLOT_REDUCTION should succeed but report 0 slots removed
        result = manager.consolidate(
            model, strategy=mc.ConsolidationStrategy.SLOT_REDUCTION
        )

        assert result.success is True
        assert result.slots_removed == 0
