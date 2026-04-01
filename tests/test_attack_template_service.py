"""
Tests for Attack Template Service.

Covers the AttackTemplateService class and related components for
security testing template management in sandboxed environments.
"""

import pytest

# Import the module directly
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
    AttackTemplateService,
    Severity,
    create_attack_template_service,
)

# =============================================================================
# AttackCategory Enum Tests
# =============================================================================


class TestAttackCategory:
    """Tests for AttackCategory enum."""

    def test_sql_injection(self):
        """Test SQL injection category."""
        assert AttackCategory.SQL_INJECTION.value == "sql_injection"

    def test_authentication_bypass(self):
        """Test authentication bypass category."""
        assert AttackCategory.AUTHENTICATION_BYPASS.value == "authentication_bypass"

    def test_ssrf(self):
        """Test SSRF category."""
        assert AttackCategory.SSRF.value == "ssrf"

    def test_command_injection(self):
        """Test command injection category."""
        assert AttackCategory.COMMAND_INJECTION.value == "command_injection"

    def test_xss(self):
        """Test XSS category."""
        assert AttackCategory.XSS.value == "xss"

    def test_path_traversal(self):
        """Test path traversal category."""
        assert AttackCategory.PATH_TRAVERSAL.value == "path_traversal"

    def test_deserialization(self):
        """Test deserialization category."""
        assert AttackCategory.DESERIALIZATION.value == "deserialization"

    def test_xxe(self):
        """Test XXE category."""
        assert AttackCategory.XXE.value == "xxe"

    def test_category_count(self):
        """Test that all 8 categories exist."""
        assert len(AttackCategory) == 8


# =============================================================================
# AttackPhase Enum Tests
# =============================================================================


class TestAttackPhase:
    """Tests for AttackPhase enum."""

    def test_reconnaissance(self):
        """Test reconnaissance phase."""
        assert AttackPhase.RECONNAISSANCE.value == "reconnaissance"

    def test_probe(self):
        """Test probe phase."""
        assert AttackPhase.PROBE.value == "probe"

    def test_exploit(self):
        """Test exploit phase."""
        assert AttackPhase.EXPLOIT.value == "exploit"

    def test_escalate(self):
        """Test escalate phase."""
        assert AttackPhase.ESCALATE.value == "escalate"

    def test_exfiltrate(self):
        """Test exfiltrate phase."""
        assert AttackPhase.EXFILTRATE.value == "exfiltrate"

    def test_persist(self):
        """Test persist phase."""
        assert AttackPhase.PERSIST.value == "persist"

    def test_phase_count(self):
        """Test that all 6 phases exist."""
        assert len(AttackPhase) == 6


# =============================================================================
# Severity Enum Tests
# =============================================================================


class TestSeverity:
    """Tests for Severity enum."""

    def test_critical(self):
        """Test critical severity."""
        assert Severity.CRITICAL.value == "critical"

    def test_high(self):
        """Test high severity."""
        assert Severity.HIGH.value == "high"

    def test_medium(self):
        """Test medium severity."""
        assert Severity.MEDIUM.value == "medium"

    def test_low(self):
        """Test low severity."""
        assert Severity.LOW.value == "low"

    def test_severity_count(self):
        """Test that all 4 severities exist."""
        assert len(Severity) == 4


# =============================================================================
# AttackStep Dataclass Tests
# =============================================================================


class TestAttackStep:
    """Tests for AttackStep dataclass."""

    def test_create_basic_step(self):
        """Test creating a basic attack step."""
        step = AttackStep(
            step_id="test-001",
            phase=AttackPhase.PROBE,
            name="Test Probe",
            description="A test probe step",
            payload="test payload",
        )
        assert step.step_id == "test-001"
        assert step.phase == AttackPhase.PROBE
        assert step.name == "Test Probe"
        assert step.description == "A test probe step"
        assert step.payload == "test payload"

    def test_default_values(self):
        """Test default values for optional fields."""
        step = AttackStep(
            step_id="test-002",
            phase=AttackPhase.EXPLOIT,
            name="Test Exploit",
            description="Description",
            payload="payload",
        )
        assert step.expected_response is None
        assert step.success_indicator is None
        assert step.timeout_seconds == 30
        assert step.requires_previous_output is False
        assert step.parameter_extraction == {}

    def test_custom_optional_values(self):
        """Test custom values for optional fields."""
        step = AttackStep(
            step_id="test-003",
            phase=AttackPhase.ESCALATE,
            name="Test Escalate",
            description="Description",
            payload="payload",
            expected_response="Expected",
            success_indicator="success",
            timeout_seconds=60,
            requires_previous_output=True,
            parameter_extraction={"key": "value"},
        )
        assert step.expected_response == "Expected"
        assert step.success_indicator == "success"
        assert step.timeout_seconds == 60
        assert step.requires_previous_output is True
        assert step.parameter_extraction == {"key": "value"}


# =============================================================================
# AttackChain Dataclass Tests
# =============================================================================


class TestAttackChain:
    """Tests for AttackChain dataclass."""

    def setup_method(self):
        """Set up test fixtures."""
        self.step1 = AttackStep(
            step_id="step-001",
            phase=AttackPhase.PROBE,
            name="Probe Step",
            description="Initial probe",
            payload="probe payload",
        )
        self.step2 = AttackStep(
            step_id="step-002",
            phase=AttackPhase.EXPLOIT,
            name="Exploit Step",
            description="Exploitation",
            payload="exploit payload",
        )

    def test_create_basic_chain(self):
        """Test creating a basic attack chain."""
        chain = AttackChain(
            chain_id="chain-001",
            name="Test Chain",
            category=AttackCategory.SQL_INJECTION,
            severity=Severity.HIGH,
            description="A test attack chain",
            steps=[self.step1, self.step2],
        )
        assert chain.chain_id == "chain-001"
        assert chain.name == "Test Chain"
        assert chain.category == AttackCategory.SQL_INJECTION
        assert chain.severity == Severity.HIGH
        assert chain.description == "A test attack chain"
        assert len(chain.steps) == 2

    def test_default_values(self):
        """Test default values for optional fields."""
        chain = AttackChain(
            chain_id="chain-002",
            name="Test Chain",
            category=AttackCategory.XSS,
            severity=Severity.MEDIUM,
            description="Description",
            steps=[self.step1],
        )
        assert chain.prerequisites == []
        assert chain.target_vulnerability_types == []
        assert chain.max_duration_seconds == 300
        assert chain.requires_hitl_approval is False
        assert chain.cwe_ids == []
        assert chain.created_at is not None

    def test_custom_optional_values(self):
        """Test custom values for optional fields."""
        chain = AttackChain(
            chain_id="chain-003",
            name="Custom Chain",
            category=AttackCategory.SSRF,
            severity=Severity.CRITICAL,
            description="Description",
            steps=[self.step1],
            prerequisites=["prereq1"],
            target_vulnerability_types=["SSRF"],
            max_duration_seconds=600,
            requires_hitl_approval=True,
            cwe_ids=["CWE-918"],
        )
        assert chain.prerequisites == ["prereq1"]
        assert chain.target_vulnerability_types == ["SSRF"]
        assert chain.max_duration_seconds == 600
        assert chain.requires_hitl_approval is True
        assert chain.cwe_ids == ["CWE-918"]

    def test_to_dict(self):
        """Test serialization to dictionary."""
        chain = AttackChain(
            chain_id="chain-dict",
            name="Dict Test Chain",
            category=AttackCategory.XSS,
            severity=Severity.MEDIUM,
            description="For dict test",
            steps=[self.step1],
            target_vulnerability_types=["XSS"],
            max_duration_seconds=180,
            requires_hitl_approval=False,
            cwe_ids=["CWE-79"],
        )
        result = chain.to_dict()
        assert result["chain_id"] == "chain-dict"
        assert result["name"] == "Dict Test Chain"
        assert result["category"] == "xss"
        assert result["severity"] == "medium"
        assert result["description"] == "For dict test"
        assert len(result["steps"]) == 1
        assert result["steps"][0]["step_id"] == "step-001"
        assert result["steps"][0]["phase"] == "probe"
        assert result["target_vulnerability_types"] == ["XSS"]
        assert result["max_duration_seconds"] == 180
        assert result["requires_hitl_approval"] is False
        assert result["cwe_ids"] == ["CWE-79"]


# =============================================================================
# AttackResult Dataclass Tests
# =============================================================================


class TestAttackResult:
    """Tests for AttackResult dataclass."""

    def test_create_success_result(self):
        """Test creating a success result."""
        result = AttackResult(success=True, step_id="step-001")
        assert result.success is True
        assert result.step_id == "step-001"

    def test_create_failure_result(self):
        """Test creating a failure result."""
        result = AttackResult(
            success=False,
            step_id="step-001",
            error="Step failed",
        )
        assert result.success is False
        assert result.error == "Step failed"

    def test_default_values(self):
        """Test default values."""
        result = AttackResult(success=True)
        assert result.step_id is None
        assert result.chain_id is None
        assert result.phase is None
        assert result.response is None
        assert result.extracted_data == {}
        assert result.error is None
        assert result.duration_seconds == 0.0
        assert result.timestamp is not None

    def test_full_result(self):
        """Test result with all fields."""
        result = AttackResult(
            success=True,
            step_id="step-001",
            chain_id="chain-001",
            phase=AttackPhase.EXPLOIT,
            response="Exploitation successful",
            extracted_data={"credential": "admin"},
            error=None,
            duration_seconds=2.5,
        )
        assert result.success is True
        assert result.step_id == "step-001"
        assert result.chain_id == "chain-001"
        assert result.phase == AttackPhase.EXPLOIT
        assert result.response == "Exploitation successful"
        assert result.extracted_data == {"credential": "admin"}
        assert result.duration_seconds == 2.5


# =============================================================================
# Predefined Attack Chain Tests
# =============================================================================


class TestPredefinedChains:
    """Tests for predefined attack chains."""

    def test_sql_injection_chain(self):
        """Test SQL injection chain is properly defined."""
        assert SQL_INJECTION_CHAIN.chain_id == "sqli-001"
        assert SQL_INJECTION_CHAIN.category == AttackCategory.SQL_INJECTION
        assert SQL_INJECTION_CHAIN.severity == Severity.CRITICAL
        assert len(SQL_INJECTION_CHAIN.steps) == 3
        assert SQL_INJECTION_CHAIN.requires_hitl_approval is True
        assert "CWE-89" in SQL_INJECTION_CHAIN.cwe_ids

    def test_auth_bypass_chain(self):
        """Test authentication bypass chain is properly defined."""
        assert AUTH_BYPASS_CHAIN.chain_id == "auth-001"
        assert AUTH_BYPASS_CHAIN.category == AttackCategory.AUTHENTICATION_BYPASS
        assert AUTH_BYPASS_CHAIN.severity == Severity.CRITICAL
        assert len(AUTH_BYPASS_CHAIN.steps) == 3
        assert AUTH_BYPASS_CHAIN.requires_hitl_approval is True

    def test_ssrf_chain(self):
        """Test SSRF chain is properly defined."""
        assert SSRF_CHAIN.chain_id == "ssrf-001"
        assert SSRF_CHAIN.category == AttackCategory.SSRF
        assert SSRF_CHAIN.severity == Severity.HIGH
        assert len(SSRF_CHAIN.steps) == 3
        assert SSRF_CHAIN.requires_hitl_approval is True
        assert "CWE-918" in SSRF_CHAIN.cwe_ids

    def test_command_injection_chain(self):
        """Test command injection chain is properly defined."""
        assert COMMAND_INJECTION_CHAIN.chain_id == "cmdi-001"
        assert COMMAND_INJECTION_CHAIN.category == AttackCategory.COMMAND_INJECTION
        assert COMMAND_INJECTION_CHAIN.severity == Severity.CRITICAL
        assert len(COMMAND_INJECTION_CHAIN.steps) == 3
        assert COMMAND_INJECTION_CHAIN.requires_hitl_approval is True

    def test_xss_chain(self):
        """Test XSS chain is properly defined."""
        assert XSS_CHAIN.chain_id == "xss-001"
        assert XSS_CHAIN.category == AttackCategory.XSS
        assert XSS_CHAIN.severity == Severity.MEDIUM
        assert len(XSS_CHAIN.steps) == 3
        # XSS is medium severity, so HITL not required
        assert XSS_CHAIN.requires_hitl_approval is False
        assert "CWE-79" in XSS_CHAIN.cwe_ids

    def test_path_traversal_chain(self):
        """Test path traversal chain is properly defined."""
        assert PATH_TRAVERSAL_CHAIN.chain_id == "path-001"
        assert PATH_TRAVERSAL_CHAIN.category == AttackCategory.PATH_TRAVERSAL
        assert PATH_TRAVERSAL_CHAIN.severity == Severity.HIGH
        assert len(PATH_TRAVERSAL_CHAIN.steps) == 3
        assert PATH_TRAVERSAL_CHAIN.requires_hitl_approval is False
        assert "CWE-22" in PATH_TRAVERSAL_CHAIN.cwe_ids


# =============================================================================
# AttackTemplateService Tests
# =============================================================================


class TestAttackTemplateService:
    """Tests for AttackTemplateService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = AttackTemplateService()

    def test_initialization(self):
        """Test service initialization loads predefined chains."""
        # Should have 6 predefined chains
        all_chains = self.service.get_all_chains()
        assert len(all_chains) == 6

    def test_get_chain_by_id(self):
        """Test getting a chain by ID."""
        chain = self.service.get_chain("sqli-001")
        assert chain is not None
        assert chain.chain_id == "sqli-001"
        assert chain.name == "SQL Injection Chain"

    def test_get_chain_not_found(self):
        """Test getting a non-existent chain."""
        chain = self.service.get_chain("nonexistent")
        assert chain is None

    def test_get_all_chains(self):
        """Test getting all chains."""
        chains = self.service.get_all_chains()
        assert len(chains) == 6
        chain_ids = [c.chain_id for c in chains]
        assert "sqli-001" in chain_ids
        assert "auth-001" in chain_ids
        assert "ssrf-001" in chain_ids

    def test_get_chains_by_category_sql_injection(self):
        """Test filtering by SQL injection category."""
        chains = self.service.get_chains_by_category(AttackCategory.SQL_INJECTION)
        assert len(chains) == 1
        assert chains[0].chain_id == "sqli-001"

    def test_get_chains_by_category_xss(self):
        """Test filtering by XSS category."""
        chains = self.service.get_chains_by_category(AttackCategory.XSS)
        assert len(chains) == 1
        assert chains[0].chain_id == "xss-001"

    def test_get_chains_by_category_none(self):
        """Test filtering by category with no matches."""
        chains = self.service.get_chains_by_category(AttackCategory.DESERIALIZATION)
        assert len(chains) == 0

    def test_get_chains_by_severity_critical(self):
        """Test filtering by critical severity."""
        chains = self.service.get_chains_by_severity(Severity.CRITICAL)
        assert len(chains) == 3  # sqli, auth, cmdi
        for chain in chains:
            assert chain.severity == Severity.CRITICAL

    def test_get_chains_by_severity_high(self):
        """Test filtering by high severity."""
        chains = self.service.get_chains_by_severity(Severity.HIGH)
        assert len(chains) == 2  # ssrf, path
        for chain in chains:
            assert chain.severity == Severity.HIGH

    def test_get_chains_by_severity_medium(self):
        """Test filtering by medium severity."""
        chains = self.service.get_chains_by_severity(Severity.MEDIUM)
        assert len(chains) == 1  # xss
        assert chains[0].chain_id == "xss-001"

    def test_get_chains_by_severity_low(self):
        """Test filtering by low severity."""
        chains = self.service.get_chains_by_severity(Severity.LOW)
        assert len(chains) == 0

    def test_get_chains_for_vulnerability(self):
        """Test getting chains for a vulnerability type."""
        chains = self.service.get_chains_for_vulnerability("SQL_INJECTION")
        assert len(chains) == 1
        assert chains[0].chain_id == "sqli-001"

    def test_get_chains_for_vulnerability_case_insensitive(self):
        """Test vulnerability type matching is case-insensitive."""
        chains = self.service.get_chains_for_vulnerability("ssrf")
        assert len(chains) == 1
        assert chains[0].chain_id == "ssrf-001"

    def test_get_chains_for_vulnerability_multiple_matches(self):
        """Test vulnerability type with multiple chain matches."""
        chains = self.service.get_chains_for_vulnerability("XSS")
        assert len(chains) >= 1

    def test_get_chains_for_vulnerability_no_match(self):
        """Test vulnerability type with no matches."""
        chains = self.service.get_chains_for_vulnerability("UNKNOWN_VULN")
        assert len(chains) == 0

    def test_get_chains_requiring_hitl(self):
        """Test getting chains that require HITL approval."""
        chains = self.service.get_chains_requiring_hitl()
        assert len(chains) == 4  # sqli, auth, ssrf, cmdi
        for chain in chains:
            assert chain.requires_hitl_approval is True

    def test_get_safe_chains(self):
        """Test getting chains that don't require HITL."""
        chains = self.service.get_safe_chains()
        assert len(chains) == 2  # xss, path
        for chain in chains:
            assert chain.requires_hitl_approval is False

    def test_register_custom_chain_success(self):
        """Test registering a custom chain."""
        custom_step = AttackStep(
            step_id="custom-step",
            phase=AttackPhase.PROBE,
            name="Custom Probe",
            description="Custom probe step",
            payload="custom payload",
        )
        custom_chain = AttackChain(
            chain_id="custom-001",
            name="Custom Chain",
            category=AttackCategory.DESERIALIZATION,
            severity=Severity.HIGH,
            description="A custom attack chain",
            steps=[custom_step],
        )
        result = self.service.register_custom_chain(custom_chain)
        assert result is True
        assert self.service.get_chain("custom-001") is not None

    def test_register_custom_chain_duplicate(self):
        """Test registering a duplicate chain ID."""
        custom_step = AttackStep(
            step_id="dup-step",
            phase=AttackPhase.PROBE,
            name="Probe",
            description="Description",
            payload="payload",
        )
        custom_chain = AttackChain(
            chain_id="sqli-001",  # Already exists
            name="Duplicate Chain",
            category=AttackCategory.SQL_INJECTION,
            severity=Severity.HIGH,
            description="Duplicate",
            steps=[custom_step],
        )
        result = self.service.register_custom_chain(custom_chain)
        assert result is False

    def test_register_critical_chain_forces_hitl(self):
        """Test that CRITICAL chains require HITL approval."""
        custom_step = AttackStep(
            step_id="critical-step",
            phase=AttackPhase.EXPLOIT,
            name="Critical Exploit",
            description="Critical step",
            payload="payload",
        )
        custom_chain = AttackChain(
            chain_id="critical-001",
            name="Critical Chain",
            category=AttackCategory.XXE,
            severity=Severity.CRITICAL,
            description="Critical chain without HITL",
            steps=[custom_step],
            requires_hitl_approval=False,  # Should be overridden
        )
        result = self.service.register_custom_chain(custom_chain)
        assert result is True
        registered = self.service.get_chain("critical-001")
        assert registered.requires_hitl_approval is True

    def test_validate_chain_valid(self):
        """Test validating a valid chain."""
        step = AttackStep(
            step_id="valid-step",
            phase=AttackPhase.PROBE,
            name="Valid Step",
            description="Valid step",
            payload="safe payload",
        )
        chain = AttackChain(
            chain_id="valid-001",
            name="Valid Chain",
            category=AttackCategory.XSS,
            severity=Severity.MEDIUM,
            description="Valid chain",
            steps=[step],
            max_duration_seconds=300,
        )
        errors = self.service.validate_chain(chain)
        assert len(errors) == 0

    def test_validate_chain_no_id(self):
        """Test validation fails without chain ID."""
        step = AttackStep(
            step_id="step",
            phase=AttackPhase.PROBE,
            name="Step",
            description="Desc",
            payload="payload",
        )
        chain = AttackChain(
            chain_id="",  # Empty ID
            name="No ID Chain",
            category=AttackCategory.XSS,
            severity=Severity.MEDIUM,
            description="Description",
            steps=[step],
        )
        errors = self.service.validate_chain(chain)
        assert "Chain ID is required" in errors

    def test_validate_chain_no_steps(self):
        """Test validation fails without steps."""
        chain = AttackChain(
            chain_id="no-steps-001",
            name="No Steps Chain",
            category=AttackCategory.XSS,
            severity=Severity.MEDIUM,
            description="Description",
            steps=[],  # No steps
        )
        errors = self.service.validate_chain(chain)
        assert "Chain must have at least one step" in errors

    def test_validate_chain_exceeds_duration(self):
        """Test validation fails if duration exceeds limit."""
        step = AttackStep(
            step_id="step",
            phase=AttackPhase.PROBE,
            name="Step",
            description="Desc",
            payload="payload",
        )
        chain = AttackChain(
            chain_id="long-001",
            name="Long Duration Chain",
            category=AttackCategory.XSS,
            severity=Severity.MEDIUM,
            description="Description",
            steps=[step],
            max_duration_seconds=7200,  # 2 hours - exceeds 30 min limit
        )
        errors = self.service.validate_chain(chain)
        assert "Max duration exceeds 30 minute limit" in errors

    def test_validate_chain_critical_without_hitl(self):
        """Test validation fails for CRITICAL severity without HITL."""
        step = AttackStep(
            step_id="step",
            phase=AttackPhase.PROBE,
            name="Step",
            description="Desc",
            payload="payload",
        )
        chain = AttackChain(
            chain_id="critical-no-hitl",
            name="Critical No HITL",
            category=AttackCategory.SQL_INJECTION,
            severity=Severity.CRITICAL,
            description="Description",
            steps=[step],
            requires_hitl_approval=False,
        )
        errors = self.service.validate_chain(chain)
        assert "CRITICAL severity chains require HITL approval" in errors

    def test_validate_chain_dangerous_payload_rm_rf(self):
        """Test validation detects dangerous rm -rf payload."""
        step = AttackStep(
            step_id="dangerous-step",
            phase=AttackPhase.EXPLOIT,
            name="Dangerous Step",
            description="Dangerous step",
            payload="rm -rf /",
        )
        chain = AttackChain(
            chain_id="dangerous-001",
            name="Dangerous Chain",
            category=AttackCategory.COMMAND_INJECTION,
            severity=Severity.HIGH,
            description="Description",
            steps=[step],
        )
        errors = self.service.validate_chain(chain)
        assert any("dangerous payload" in err for err in errors)

    def test_validate_chain_dangerous_payload_dd(self):
        """Test validation detects dangerous dd payload."""
        step = AttackStep(
            step_id="dd-step",
            phase=AttackPhase.EXPLOIT,
            name="DD Step",
            description="DD step",
            payload="dd if=/dev/zero of=/dev/sda",
        )
        chain = AttackChain(
            chain_id="dd-001",
            name="DD Chain",
            category=AttackCategory.COMMAND_INJECTION,
            severity=Severity.HIGH,
            description="Description",
            steps=[step],
        )
        errors = self.service.validate_chain(chain)
        assert any("dangerous payload" in err for err in errors)


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_attack_template_service(self):
        """Test creating service via factory function."""
        service = create_attack_template_service()
        assert isinstance(service, AttackTemplateService)
        assert len(service.get_all_chains()) == 6

    def test_factory_creates_independent_instances(self):
        """Test factory creates independent instances."""
        service1 = create_attack_template_service()
        service2 = create_attack_template_service()
        assert service1 is not service2
        # Modify one, shouldn't affect the other
        step = AttackStep(
            step_id="test-step",
            phase=AttackPhase.PROBE,
            name="Test",
            description="Test",
            payload="test",
        )
        chain = AttackChain(
            chain_id="independent-001",
            name="Independent",
            category=AttackCategory.XXE,
            severity=Severity.MEDIUM,
            description="Test",
            steps=[step],
        )
        service1.register_custom_chain(chain)
        assert service1.get_chain("independent-001") is not None
        assert service2.get_chain("independent-001") is None


# =============================================================================
# Integration Tests
# =============================================================================


class TestAttackTemplateIntegration:
    """Integration tests for attack template workflows."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = AttackTemplateService()

    def test_workflow_find_chains_for_vuln_assessment(self):
        """Test workflow: find chains for vulnerability assessment."""
        # Find all SQL injection related chains
        sqli_chains = self.service.get_chains_for_vulnerability("SQL_INJECTION")
        assert len(sqli_chains) >= 1

        # Get details for the first chain
        chain = sqli_chains[0]
        assert chain.category == AttackCategory.SQL_INJECTION

        # Check steps are properly ordered
        assert chain.steps[0].phase == AttackPhase.PROBE
        assert chain.steps[1].phase == AttackPhase.EXPLOIT
        assert chain.steps[2].phase == AttackPhase.ESCALATE

    def test_workflow_categorize_by_risk(self):
        """Test workflow: categorize chains by risk level."""
        hitl_required = self.service.get_chains_requiring_hitl()
        safe_chains = self.service.get_safe_chains()

        # All chains should be in one category or the other
        total = len(hitl_required) + len(safe_chains)
        assert total == len(self.service.get_all_chains())

        # HITL chains should be higher severity
        for chain in hitl_required:
            assert chain.severity in [Severity.CRITICAL, Severity.HIGH]

    def test_workflow_serialize_chain_for_storage(self):
        """Test workflow: serialize chain for storage/transmission."""
        chain = self.service.get_chain("sqli-001")
        serialized = chain.to_dict()

        # Should be JSON-serializable
        import json

        json_str = json.dumps(serialized)
        assert json_str is not None

        # Should be deserializable
        deserialized = json.loads(json_str)
        assert deserialized["chain_id"] == "sqli-001"
        assert deserialized["severity"] == "critical"

    def test_step_dependencies(self):
        """Test that step dependencies are properly configured."""
        chain = self.service.get_chain("sqli-001")

        # First step shouldn't require previous output
        assert chain.steps[0].requires_previous_output is False

        # Subsequent steps should require previous output
        for step in chain.steps[1:]:
            assert step.requires_previous_output is True

    def test_all_chains_have_cwe_ids(self):
        """Test all predefined chains have CWE IDs."""
        for chain in self.service.get_all_chains():
            assert len(chain.cwe_ids) > 0, f"Chain {chain.chain_id} missing CWE IDs"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
