"""
Tests for Penetration Testing Agent and Attack Template Service.

This module tests the active penetration testing capabilities including
attack chain execution, safety controls, and sandbox isolation.
Part of AWS Security Agent capability parity (Gap 3/4).

CRITICAL: These tests use MOCK MODE only. No real attacks are executed.

Author: Project Aura Team
Created: 2025-12-03
"""

from unittest.mock import MagicMock

import pytest

from src.agents.penetration_testing_agent import (
    ExecutionEnvironment,
    PenetrationTestingAgent,
    PenTestResult,
    SandboxContext,
    TestStatus,
    create_penetration_testing_agent,
)
from src.services.attack_template_service import (
    AUTH_BYPASS_CHAIN,
    COMMAND_INJECTION_CHAIN,
    PATH_TRAVERSAL_CHAIN,
    SQL_INJECTION_CHAIN,
    SSRF_CHAIN,
    XSS_CHAIN,
    AttackCategory,
    AttackChain,
    AttackPhase,
    AttackResult,
    AttackStep,
    Severity,
    create_attack_template_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def template_service():
    """Create attack template service."""
    return create_attack_template_service()


@pytest.fixture
def pentest_agent():
    """Create penetration testing agent in mock mode."""
    return PenetrationTestingAgent(
        sandbox_service=None,
        hitl_service=None,
        use_mock=True,
    )


@pytest.fixture
def sandbox_context():
    """Create sample sandbox context."""
    return SandboxContext(
        sandbox_id="sandbox-test-001",
        target_url="http://localhost:8080",
        target_endpoint="/api/login",
        headers={"Content-Type": "application/json"},
    )


# =============================================================================
# Attack Template Service Tests
# =============================================================================


class TestAttackTemplateService:
    """Tests for AttackTemplateService."""

    def test_service_initialization(self, template_service):
        """Test service loads predefined chains."""
        chains = template_service.get_all_chains()
        assert len(chains) >= 6  # 6 predefined chains

    def test_get_chain_by_id(self, template_service):
        """Test getting chain by ID."""
        chain = template_service.get_chain("sqli-001")

        assert chain is not None
        assert chain.chain_id == "sqli-001"
        assert chain.category == AttackCategory.SQL_INJECTION

    def test_get_nonexistent_chain(self, template_service):
        """Test getting nonexistent chain returns None."""
        chain = template_service.get_chain("nonexistent-001")
        assert chain is None

    def test_get_chains_by_category(self, template_service):
        """Test filtering chains by category."""
        chains = template_service.get_chains_by_category(AttackCategory.SQL_INJECTION)

        assert len(chains) >= 1
        assert all(c.category == AttackCategory.SQL_INJECTION for c in chains)

    def test_get_chains_by_severity(self, template_service):
        """Test filtering chains by severity."""
        critical_chains = template_service.get_chains_by_severity(Severity.CRITICAL)

        assert len(critical_chains) >= 3  # SQLi, Auth, CmdI are critical
        assert all(c.severity == Severity.CRITICAL for c in critical_chains)

    def test_get_chains_for_vulnerability(self, template_service):
        """Test getting chains for specific vulnerability type."""
        chains = template_service.get_chains_for_vulnerability("SQL_INJECTION")

        assert len(chains) >= 1
        assert any("SQL_INJECTION" in c.target_vulnerability_types for c in chains)

    def test_get_chains_requiring_hitl(self, template_service):
        """Test getting chains that require HITL approval."""
        hitl_chains = template_service.get_chains_requiring_hitl()

        assert len(hitl_chains) >= 4  # SQLi, Auth, SSRF, CmdI require HITL
        assert all(c.requires_hitl_approval for c in hitl_chains)

    def test_get_safe_chains(self, template_service):
        """Test getting chains that don't require HITL."""
        safe_chains = template_service.get_safe_chains()

        assert len(safe_chains) >= 2  # XSS and Path Traversal
        assert all(not c.requires_hitl_approval for c in safe_chains)


class TestPredefinedAttackChains:
    """Tests for predefined attack chain templates."""

    def test_sql_injection_chain(self):
        """Test SQL injection chain structure."""
        assert SQL_INJECTION_CHAIN.chain_id == "sqli-001"
        assert SQL_INJECTION_CHAIN.severity == Severity.CRITICAL
        assert SQL_INJECTION_CHAIN.requires_hitl_approval is True
        assert len(SQL_INJECTION_CHAIN.steps) == 3
        assert "CWE-89" in SQL_INJECTION_CHAIN.cwe_ids

    def test_auth_bypass_chain(self):
        """Test authentication bypass chain structure."""
        assert AUTH_BYPASS_CHAIN.chain_id == "auth-001"
        assert AUTH_BYPASS_CHAIN.severity == Severity.CRITICAL
        assert len(AUTH_BYPASS_CHAIN.steps) == 3

    def test_ssrf_chain(self):
        """Test SSRF chain structure."""
        assert SSRF_CHAIN.chain_id == "ssrf-001"
        assert SSRF_CHAIN.severity == Severity.HIGH
        assert "metadata" in SSRF_CHAIN.steps[-1].name.lower()

    def test_command_injection_chain(self):
        """Test command injection chain structure."""
        assert COMMAND_INJECTION_CHAIN.chain_id == "cmdi-001"
        assert COMMAND_INJECTION_CHAIN.severity == Severity.CRITICAL
        assert "CWE-78" in COMMAND_INJECTION_CHAIN.cwe_ids

    def test_xss_chain(self):
        """Test XSS chain structure."""
        assert XSS_CHAIN.chain_id == "xss-001"
        assert XSS_CHAIN.severity == Severity.MEDIUM
        assert XSS_CHAIN.requires_hitl_approval is False

    def test_path_traversal_chain(self):
        """Test path traversal chain structure."""
        assert PATH_TRAVERSAL_CHAIN.chain_id == "path-001"
        assert PATH_TRAVERSAL_CHAIN.severity == Severity.HIGH
        assert "CWE-22" in PATH_TRAVERSAL_CHAIN.cwe_ids


class TestAttackChainValidation:
    """Tests for attack chain validation."""

    def test_validate_valid_chain(self, template_service):
        """Test validating a valid chain."""
        errors = template_service.validate_chain(SQL_INJECTION_CHAIN)
        assert len(errors) == 0

    def test_validate_missing_chain_id(self, template_service):
        """Test validation catches missing chain ID."""
        invalid_chain = AttackChain(
            chain_id="",  # Invalid: empty
            name="Test",
            category=AttackCategory.XSS,
            severity=Severity.LOW,
            description="Test",
            steps=[],
        )

        errors = template_service.validate_chain(invalid_chain)
        assert len(errors) >= 2  # Missing ID and no steps

    def test_validate_critical_without_hitl(self, template_service):
        """Test validation catches CRITICAL without HITL."""
        invalid_chain = AttackChain(
            chain_id="test-001",
            name="Test",
            category=AttackCategory.SQL_INJECTION,
            severity=Severity.CRITICAL,
            description="Test",
            steps=[
                AttackStep(
                    step_id="s1",
                    phase=AttackPhase.PROBE,
                    name="Test",
                    description="Test",
                    payload="test",
                )
            ],
            requires_hitl_approval=False,  # Invalid for CRITICAL
        )

        errors = template_service.validate_chain(invalid_chain)
        assert any("CRITICAL" in e and "HITL" in e for e in errors)

    def test_validate_excessive_duration(self, template_service):
        """Test validation catches excessive duration."""
        invalid_chain = AttackChain(
            chain_id="test-001",
            name="Test",
            category=AttackCategory.XSS,
            severity=Severity.LOW,
            description="Test",
            steps=[
                AttackStep(
                    step_id="s1",
                    phase=AttackPhase.PROBE,
                    name="Test",
                    description="Test",
                    payload="test",
                )
            ],
            max_duration_seconds=7200,  # 2 hours - too long
        )

        errors = template_service.validate_chain(invalid_chain)
        assert any("30 minute" in e for e in errors)


class TestCustomChainRegistration:
    """Tests for custom chain registration."""

    def test_register_custom_chain(self, template_service):
        """Test registering a custom chain."""
        custom_chain = AttackChain(
            chain_id="custom-001",
            name="Custom Test Chain",
            category=AttackCategory.XSS,
            severity=Severity.LOW,
            description="Custom test",
            steps=[
                AttackStep(
                    step_id="c1",
                    phase=AttackPhase.PROBE,
                    name="Custom probe",
                    description="Test",
                    payload="test",
                )
            ],
        )

        result = template_service.register_custom_chain(custom_chain)
        assert result is True

        retrieved = template_service.get_chain("custom-001")
        assert retrieved is not None
        assert retrieved.name == "Custom Test Chain"

    def test_register_duplicate_chain(self, template_service):
        """Test registering duplicate chain fails."""
        result = template_service.register_custom_chain(SQL_INJECTION_CHAIN)
        assert result is False  # Already exists


# =============================================================================
# Penetration Testing Agent Tests
# =============================================================================


class TestPenetrationTestingAgent:
    """Tests for PenetrationTestingAgent."""

    def test_agent_initialization(self, pentest_agent):
        """Test agent initializes correctly."""
        assert pentest_agent.use_mock is True
        assert pentest_agent.templates is not None

    @pytest.mark.asyncio
    async def test_execute_chain_mock(self, pentest_agent, sandbox_context):
        """Test executing chain in mock mode."""
        result = await pentest_agent.execute_chain(
            chain_id="sqli-001",
            sandbox_context=sandbox_context,
            skip_hitl=True,
        )

        assert isinstance(result, PenTestResult)
        assert result.chain_id == "sqli-001"
        assert result.environment == ExecutionEnvironment.SANDBOX
        assert result.status in [TestStatus.COMPLETED, TestStatus.FAILED]

    @pytest.mark.asyncio
    async def test_execute_nonexistent_chain(self, pentest_agent, sandbox_context):
        """Test executing nonexistent chain fails gracefully."""
        result = await pentest_agent.execute_chain(
            chain_id="nonexistent-999",
            sandbox_context=sandbox_context,
        )

        assert result.status == TestStatus.FAILED
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_xss_chain(self, pentest_agent, sandbox_context):
        """Test executing XSS chain (doesn't require HITL)."""
        result = await pentest_agent.execute_chain(
            chain_id="xss-001",
            sandbox_context=sandbox_context,
            skip_hitl=True,
        )

        assert result.chain_id == "xss-001"
        assert result.steps_total == 3

    @pytest.mark.asyncio
    async def test_result_has_required_fields(self, pentest_agent, sandbox_context):
        """Test result contains all required fields."""
        result = await pentest_agent.execute_chain(
            chain_id="path-001",
            sandbox_context=sandbox_context,
            skip_hitl=True,
        )

        assert result.test_id is not None
        assert result.chain_name is not None
        assert result.start_time is not None
        assert result.duration_seconds >= 0
        assert result.risk_score >= 0


class TestSandboxSafetyControls:
    """Tests for sandbox safety controls."""

    def test_verify_sandbox_with_valid_context(self, pentest_agent):
        """Test sandbox verification with valid context."""
        context = SandboxContext(
            sandbox_id="sandbox-001",
            target_url="http://sandbox.test.local:8080",
        )

        is_valid = pentest_agent._verify_sandbox_environment(context)
        assert is_valid is True

    def test_verify_sandbox_blocks_production_url(self, pentest_agent):
        """Test sandbox verification blocks production URLs."""
        context = SandboxContext(
            sandbox_id="sandbox-001",
            target_url="https://api.production.amazonaws.com",
        )

        is_valid = pentest_agent._verify_sandbox_environment(context)
        assert is_valid is False

    def test_verify_sandbox_blocks_prod_pattern(self, pentest_agent):
        """Test sandbox verification blocks prod pattern."""
        context = SandboxContext(
            sandbox_id="sandbox-001",
            target_url="https://prod-api.company.com",
        )

        is_valid = pentest_agent._verify_sandbox_environment(context)
        assert is_valid is False

    def test_verify_sandbox_blocks_no_sandbox_id(self, pentest_agent):
        """Test sandbox verification blocks missing sandbox ID."""
        context = SandboxContext(
            sandbox_id="",  # Empty
            target_url="http://localhost:8080",
        )

        is_valid = pentest_agent._verify_sandbox_environment(context)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_blocked_production_target(self, pentest_agent):
        """Test that production targets are blocked."""
        prod_context = SandboxContext(
            sandbox_id="sandbox-001",
            target_url="https://api.production.company.com",
        )

        result = await pentest_agent.execute_chain(
            chain_id="sqli-001",
            sandbox_context=prod_context,
            skip_hitl=True,
        )

        assert result.status == TestStatus.BLOCKED
        assert result.blocked_reason is not None


class TestHITLIntegration:
    """Tests for HITL approval integration."""

    @pytest.mark.asyncio
    async def test_hitl_approval_in_mock_mode(self, pentest_agent, sandbox_context):
        """Test HITL approval auto-succeeds in mock mode."""
        chain = pentest_agent.templates.get_chain("sqli-001")
        assert chain.requires_hitl_approval is True

        approval = await pentest_agent._request_hitl_approval(chain, sandbox_context)
        assert approval["approved"] is True

    @pytest.mark.asyncio
    async def test_hitl_skipped_when_requested(self, pentest_agent, sandbox_context):
        """Test HITL can be skipped for testing."""
        result = await pentest_agent.execute_chain(
            chain_id="sqli-001",
            sandbox_context=sandbox_context,
            skip_hitl=True,
        )

        # Should complete without HITL blocking
        assert result.status != TestStatus.AWAITING_APPROVAL


class TestRiskScoreCalculation:
    """Tests for risk score calculation."""

    def test_risk_score_critical_chain(self, pentest_agent):
        """Test risk score for critical chain."""
        chain = pentest_agent.templates.get_chain("sqli-001")
        step_results = [
            AttackResult(success=True, step_id="s1", phase=AttackPhase.PROBE),
            AttackResult(success=True, step_id="s2", phase=AttackPhase.EXPLOIT),
        ]

        score = pentest_agent._calculate_risk_score(chain, step_results)
        assert score > 10.0  # Critical base score

    def test_risk_score_no_success(self, pentest_agent):
        """Test risk score with no successful steps."""
        chain = pentest_agent.templates.get_chain("xss-001")
        step_results = [
            AttackResult(success=False, step_id="s1", phase=AttackPhase.PROBE),
        ]

        score = pentest_agent._calculate_risk_score(chain, step_results)
        assert score == 4.0  # Medium base score only


class TestVulnerabilityAssessment:
    """Tests for vulnerability confirmation assessment."""

    def test_vulnerability_confirmed(self, pentest_agent):
        """Test vulnerability confirmed with probe + exploit success."""
        chain = pentest_agent.templates.get_chain("sqli-001")
        step_results = [
            AttackResult(success=True, step_id="s1", phase=AttackPhase.PROBE),
            AttackResult(success=True, step_id="s2", phase=AttackPhase.EXPLOIT),
        ]

        confirmed = pentest_agent._assess_vulnerability(chain, step_results)
        assert confirmed is True

    def test_vulnerability_not_confirmed_no_exploit(self, pentest_agent):
        """Test vulnerability not confirmed without exploit."""
        chain = pentest_agent.templates.get_chain("sqli-001")
        step_results = [
            AttackResult(success=True, step_id="s1", phase=AttackPhase.PROBE),
            AttackResult(success=False, step_id="s2", phase=AttackPhase.EXPLOIT),
        ]

        confirmed = pentest_agent._assess_vulnerability(chain, step_results)
        assert confirmed is False

    def test_vulnerability_not_confirmed_no_probe(self, pentest_agent):
        """Test vulnerability not confirmed without probe."""
        chain = pentest_agent.templates.get_chain("sqli-001")
        step_results = [
            AttackResult(success=False, step_id="s1", phase=AttackPhase.PROBE),
        ]

        confirmed = pentest_agent._assess_vulnerability(chain, step_results)
        assert confirmed is False


# =============================================================================
# Spawnable Agent Adapter Tests
# =============================================================================


class TestSpawnablePenetrationTestingAgent:
    """Tests for SpawnablePenetrationTestingAgent adapter."""

    @pytest.fixture
    def spawnable_agent(self):
        """Create spawnable adapter for testing."""
        from src.agents.spawnable_agent_adapters import SpawnablePenetrationTestingAgent

        return SpawnablePenetrationTestingAgent(agent_id="test-pentest")

    @pytest.mark.asyncio
    async def test_adapter_capability(self, spawnable_agent):
        """Test adapter has correct capability."""
        from src.agents.meta_orchestrator import AgentCapability

        assert spawnable_agent.capability == AgentCapability.PENETRATION_TESTING

    @pytest.mark.asyncio
    async def test_adapter_list_chains(self, spawnable_agent):
        """Test adapter can list available chains."""
        context = {
            "list_chains": True,
        }

        result = await spawnable_agent.execute(
            task="List available attack chains", context=context
        )

        assert result.success is True
        assert "available_chains" in result.output
        assert result.output["total_chains"] >= 6

    @pytest.mark.asyncio
    async def test_adapter_execute_chain(self, spawnable_agent):
        """Test adapter can execute a chain."""
        context = {
            "chain_id": "xss-001",
            "sandbox_id": "sandbox-test-001",
            "target_url": "http://localhost:8080",
            "skip_hitl": True,
        }

        result = await spawnable_agent.execute(
            task="Execute XSS attack chain", context=context
        )

        assert result.success is True
        assert "status" in result.output

    @pytest.mark.asyncio
    async def test_adapter_requires_sandbox_id(self, spawnable_agent):
        """Test adapter requires sandbox_id for security."""
        context = {
            "chain_id": "xss-001",
            # Missing sandbox_id
        }

        result = await spawnable_agent.execute(
            task="Execute attack chain", context=context
        )

        assert result.success is False
        assert "sandbox_id" in result.error.lower()

    @pytest.mark.asyncio
    async def test_adapter_requires_chain_id(self, spawnable_agent):
        """Test adapter requires chain_id."""
        context = {
            "sandbox_id": "sandbox-001",
            # Missing chain_id
        }

        result = await spawnable_agent.execute(task="Execute attack", context=context)

        assert result.success is False
        assert "chain_id" in result.error.lower()


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_attack_template_service(self):
        """Test creating attack template service."""
        service = create_attack_template_service()

        assert service is not None
        assert len(service.get_all_chains()) >= 6

    def test_create_penetration_testing_agent(self):
        """Test creating pentest agent."""
        agent = create_penetration_testing_agent(use_mock=True)

        assert agent is not None
        assert agent.use_mock is True

    def test_create_agent_with_services(self):
        """Test creating agent with mock services."""
        mock_sandbox = MagicMock()
        mock_hitl = MagicMock()

        agent = create_penetration_testing_agent(
            sandbox_service=mock_sandbox,
            hitl_service=mock_hitl,
            use_mock=False,
        )

        assert agent.sandbox == mock_sandbox
        assert agent.hitl == mock_hitl


# =============================================================================
# Attack Step and Result Tests
# =============================================================================


class TestAttackStep:
    """Tests for AttackStep dataclass."""

    def test_step_creation(self):
        """Test creating attack step."""
        step = AttackStep(
            step_id="test-001",
            phase=AttackPhase.PROBE,
            name="Test Probe",
            description="Test description",
            payload="' OR '1'='1",
            expected_response="success",
            success_indicator="authenticated",
            timeout_seconds=30,
        )

        assert step.step_id == "test-001"
        assert step.phase == AttackPhase.PROBE
        assert step.timeout_seconds == 30

    def test_step_defaults(self):
        """Test step default values."""
        step = AttackStep(
            step_id="test-001",
            phase=AttackPhase.PROBE,
            name="Test",
            description="Test",
            payload="test",
        )

        assert step.timeout_seconds == 30
        assert step.requires_previous_output is False
        assert step.parameter_extraction == {}


class TestAttackResult:
    """Tests for AttackResult dataclass."""

    def test_result_creation(self):
        """Test creating attack result."""
        result = AttackResult(
            success=True,
            step_id="test-001",
            chain_id="chain-001",
            phase=AttackPhase.PROBE,
            response="Login successful",
            extracted_data={"token": "abc123"},
            duration_seconds=1.5,
        )

        assert result.success is True
        assert result.step_id == "test-001"
        assert result.extracted_data["token"] == "abc123"


class TestPenTestResult:
    """Tests for PenTestResult dataclass."""

    def test_result_to_dict(self):
        """Test result serialization."""
        result = PenTestResult(
            test_id="PEN-001",
            chain_id="sqli-001",
            chain_name="SQL Injection Chain",
            status=TestStatus.COMPLETED,
            environment=ExecutionEnvironment.SANDBOX,
            steps_executed=3,
            steps_total=3,
            step_results=[],
            vulnerability_confirmed=True,
            risk_score=25.0,
            start_time="2025-12-03T12:00:00Z",
            end_time="2025-12-03T12:01:00Z",
            duration_seconds=60.0,
        )

        data = result.to_dict()

        assert data["test_id"] == "PEN-001"
        assert data["status"] == "completed"
        assert data["environment"] == "sandbox"
        assert data["vulnerability_confirmed"] is True


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_step_results(self, pentest_agent):
        """Test handling of empty step results."""
        chain = pentest_agent.templates.get_chain("sqli-001")

        confirmed = pentest_agent._assess_vulnerability(chain, [])
        assert confirmed is False

        score = pentest_agent._calculate_risk_score(chain, [])
        assert score == 10.0  # Base critical score

    def test_payload_interpolation(self, pentest_agent):
        """Test payload variable interpolation."""
        context = SandboxContext(
            sandbox_id="sandbox-001",
            target_url="http://localhost",
            extracted_data={"session_id": "abc123"},
            previous_step_output="previous_value",
        )

        payload = "session=${session_id}&prev=${previous_output}"
        interpolated = pentest_agent._interpolate_payload(payload, context)

        assert "abc123" in interpolated
        assert "previous_value" in interpolated

    @pytest.mark.asyncio
    async def test_get_test_status(self, pentest_agent, sandbox_context):
        """Test getting status of executed test."""
        result = await pentest_agent.execute_chain(
            chain_id="xss-001",
            sandbox_context=sandbox_context,
            skip_hitl=True,
        )

        retrieved = pentest_agent.get_test_status(result.test_id)
        assert retrieved is not None
        assert retrieved.test_id == result.test_id

    def test_get_available_chains_filtered(self, pentest_agent):
        """Test getting chains with multiple filters."""
        chains = pentest_agent.get_available_chains(
            category=AttackCategory.SQL_INJECTION,
            severity=Severity.CRITICAL,
            require_hitl=True,
        )

        assert len(chains) >= 1
        for chain in chains:
            assert chain.category == AttackCategory.SQL_INJECTION
            assert chain.severity == Severity.CRITICAL
            assert chain.requires_hitl_approval is True
